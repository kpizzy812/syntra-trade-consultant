"""
Monitor Service

State machine для мониторинга активных сценариев по 1m OHLC.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from typing import List, Optional, Dict, Any, Tuple

import redis.asyncio as redis
from loguru import logger
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.forward_test.config import get_config
from src.services.forward_test.enums import (
    ScenarioState,
    TerminalState,
    OutcomeResult,
    PnLClass,
    Bias,
    EventType,
)
from src.services.forward_test.models import (
    ForwardTestSnapshot,
    ForwardTestMonitorState,
    ForwardTestEvent,
    ForwardTestOutcome,
)
from src.services.forward_test.fill_simulator import (
    FillSimulator,
    Candle1m,
    EntryOrder,
    SimulatedFill,
    fill_simulator,
)
from src.services.bybit_service import BybitService


@dataclass
class StateTransition:
    """Результат перехода состояния."""
    snapshot_id: str
    from_state: ScenarioState
    to_state: ScenarioState
    price: float
    candle_ts: datetime


class MonitorService:
    """
    State machine для мониторинга активных сценариев по 1m OHLC.

    Каждые 60 сек:
    1. Acquire distributed lock
    2. Получить все active snapshots
    3. Для каждого symbol получить пропущенные 1m свечи
    4. Проиграть каждую свечу последовательно
    5. При terminal state → создать outcome
    6. Release lock
    """

    LOCK_KEY = "forward_test:monitor_lock"
    LOCK_TTL_SEC = 90

    def __init__(self):
        self.config = get_config()
        self.fill_sim = fill_simulator
        self.bybit = BybitService()
        self._redis: Optional[redis.Redis] = None

    async def tick(self, session: AsyncSession) -> List[StateTransition]:
        """
        Один тик мониторинга.

        Returns:
            Список произошедших transitions
        """
        # Acquire lock
        if not await self._acquire_lock():
            logger.debug("Monitor lock not acquired, skipping tick")
            return []

        try:
            transitions: List[StateTransition] = []

            # Получить active snapshots
            active_states = await self._get_active_states(session)
            if not active_states:
                return []

            # Группировать по symbol
            by_symbol: Dict[str, List[Tuple[ForwardTestSnapshot, ForwardTestMonitorState]]] = {}
            for snapshot, state in active_states:
                symbol = snapshot.symbol
                if symbol not in by_symbol:
                    by_symbol[symbol] = []
                by_symbol[symbol].append((snapshot, state))

            # Обработать каждый symbol
            for symbol, items in by_symbol.items():
                try:
                    symbol_transitions = await self._process_symbol(
                        session, symbol, items
                    )
                    transitions.extend(symbol_transitions)
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")

            await session.commit()
            return transitions

        finally:
            await self._release_lock()

    async def _get_active_states(
        self,
        session: AsyncSession
    ) -> List[Tuple[ForwardTestSnapshot, ForwardTestMonitorState]]:
        """Получить все active snapshots с их state."""
        active_state_values = [s.value for s in ScenarioState.active_states()]

        query = (
            select(ForwardTestSnapshot, ForwardTestMonitorState)
            .join(
                ForwardTestMonitorState,
                ForwardTestSnapshot.snapshot_id == ForwardTestMonitorState.snapshot_id
            )
            .where(ForwardTestMonitorState.state.in_(active_state_values))
        )

        result = await session.execute(query)
        return list(result.all())

    async def _process_symbol(
        self,
        session: AsyncSession,
        symbol: str,
        items: List[Tuple[ForwardTestSnapshot, ForwardTestMonitorState]]
    ) -> List[StateTransition]:
        """Обработать все сценарии для одного symbol."""
        transitions: List[StateTransition] = []

        # Найти самый старый last_checked_candle_ts
        oldest_ts: Optional[datetime] = None
        for snapshot, state in items:
            if state.last_checked_candle_ts:
                if oldest_ts is None or state.last_checked_candle_ts < oldest_ts:
                    oldest_ts = state.last_checked_candle_ts

        # Получить пропущенные свечи
        candles = await self._get_candles(symbol, oldest_ts)
        if not candles:
            return []

        # Обработать каждый сценарий по каждой свече
        for snapshot, state in items:
            try:
                scenario_transitions = await self._process_scenario_candles(
                    session, snapshot, state, candles
                )
                transitions.extend(scenario_transitions)
            except Exception as e:
                logger.error(f"Error processing scenario {snapshot.snapshot_id[:8]}: {e}")

        return transitions

    async def _process_scenario_candles(
        self,
        session: AsyncSession,
        snapshot: ForwardTestSnapshot,
        state: ForwardTestMonitorState,
        candles: List[Candle1m]
    ) -> List[StateTransition]:
        """Обработать все свечи для одного сценария."""
        transitions: List[StateTransition] = []

        for candle in candles:
            # Пропустить уже проверенные свечи
            if state.last_checked_candle_ts and candle.ts <= state.last_checked_candle_ts:
                continue

            # Проверить expiration
            if datetime.now(UTC) > snapshot.expires_at and state.state in (
                ScenarioState.ARMED, ScenarioState.TRIGGERED
            ):
                transition = await self._handle_expiration(session, snapshot, state, candle)
                if transition:
                    transitions.append(transition)
                break

            # Обработать свечу
            transition = await self._process_single_candle(
                session, snapshot, state, candle
            )

            state.last_checked_candle_ts = candle.ts
            state.candle_source = "bybit"

            if transition:
                transitions.append(transition)
                if ScenarioState(transition.to_state).is_terminal():
                    break

        return transitions

    async def _process_single_candle(
        self,
        session: AsyncSession,
        snapshot: ForwardTestSnapshot,
        state: ForwardTestMonitorState,
        candle: Candle1m
    ) -> Optional[StateTransition]:
        """
        Обработать одну свечу для одного сценария.

        Порядок (same-bar rules):
        - LONG: сначала low (entry/SL), потом high (TP)
        - SHORT: сначала high (entry/SL), потом low (TP)
        """
        bias = Bias(state.bias_final)
        current_state = ScenarioState(state.state)

        # ARMED → TRIGGERED
        if current_state == ScenarioState.ARMED:
            # MVP: без activation condition → сразу triggered
            return await self._transition_to_triggered(session, snapshot, state, candle)

        # TRIGGERED → ENTERED
        if current_state == ScenarioState.TRIGGERED:
            return await self._check_entry(session, snapshot, state, candle, bias)

        # ENTERED / TP1 → TP/SL/BE
        if current_state in (ScenarioState.ENTERED, ScenarioState.TP1):
            return await self._check_tp_sl(session, snapshot, state, candle, bias)

        return None

    async def _transition_to_triggered(
        self,
        session: AsyncSession,
        snapshot: ForwardTestSnapshot,
        state: ForwardTestMonitorState,
        candle: Candle1m
    ) -> StateTransition:
        """Перевести в TRIGGERED."""
        old_state = ScenarioState(state.state)
        state.state = ScenarioState.TRIGGERED
        state.state_updated_at = candle.ts
        state.triggered_at = candle.ts

        # Event
        event = ForwardTestEvent(
            snapshot_id=snapshot.snapshot_id,
            ts=candle.ts,
            event_type=EventType.TRIGGER_HIT,
            price=candle.close,
            details_json={}
        )
        session.add(event)

        return StateTransition(
            snapshot_id=snapshot.snapshot_id,
            from_state=old_state,
            to_state=ScenarioState.TRIGGERED,
            price=candle.close,
            candle_ts=candle.ts
        )

    async def _check_entry(
        self,
        session: AsyncSession,
        snapshot: ForwardTestSnapshot,
        state: ForwardTestMonitorState,
        candle: Candle1m,
        bias: Bias
    ) -> Optional[StateTransition]:
        """Проверить entry fills."""
        # Получить entry orders из normalized_json
        entry_orders = self._get_entry_orders(snapshot)
        if not entry_orders:
            # Fallback: один order по entry_price_avg
            entry_orders = [EntryOrder(idx=0, price=snapshot.entry_price_avg, size_pct=100)]

        # Проверить fills
        new_fills: List[SimulatedFill] = []
        filled_orders = state.filled_orders_json or []
        filled_indices = {o.get("order_idx") for o in filled_orders}

        for order in entry_orders:
            if order.idx in filled_indices:
                continue

            fill = self.fill_sim.check_entry_fill(order, candle, bias)
            if fill:
                new_fills.append(fill)
                filled_orders.append({
                    "order_idx": fill.order_idx,
                    "order_price": fill.order_price,
                    "size_pct": fill.size_pct,
                    "fill_price_after_slippage": fill.fill_price,
                    "fill_candle_ts": fill.fill_candle_ts.isoformat()
                })

        if not new_fills:
            return None

        # Update state
        state.filled_orders_json = filled_orders
        all_fills = [
            SimulatedFill(
                order_idx=o["order_idx"],
                order_price=o["order_price"],
                size_pct=o["size_pct"],
                fill_price=o["fill_price_after_slippage"],
                fill_candle_ts=datetime.fromisoformat(o["fill_candle_ts"])
            )
            for o in filled_orders
        ]
        state.avg_entry_price = self.fill_sim.calculate_weighted_entry(all_fills)
        state.fill_pct = self.fill_sim.calculate_fill_pct(all_fills)

        # Если есть хотя бы один fill → ENTERED
        if state.fill_pct > 0 and ScenarioState(state.state) == ScenarioState.TRIGGERED:
            old_state = ScenarioState(state.state)
            state.state = ScenarioState.ENTERED
            state.state_updated_at = candle.ts
            state.entered_at = candle.ts

            # Зафиксировать initial_sl и initial_risk
            state.initial_sl = snapshot.stop_loss
            state.initial_risk_per_unit = abs(state.avg_entry_price - snapshot.stop_loss)
            state.current_sl = snapshot.stop_loss

            # Events для каждого fill
            for fill in new_fills:
                event = ForwardTestEvent(
                    snapshot_id=snapshot.snapshot_id,
                    ts=fill.fill_candle_ts,
                    event_type=EventType.ENTRY_FILL,
                    price=fill.fill_price,
                    details_json={
                        "order_idx": fill.order_idx,
                        "size_pct": fill.size_pct,
                        "avg_entry": state.avg_entry_price,
                        "fill_pct": state.fill_pct
                    }
                )
                session.add(event)

            return StateTransition(
                snapshot_id=snapshot.snapshot_id,
                from_state=old_state,
                to_state=ScenarioState.ENTERED,
                price=state.avg_entry_price,
                candle_ts=candle.ts
            )

        return None

    async def _check_tp_sl(
        self,
        session: AsyncSession,
        snapshot: ForwardTestSnapshot,
        state: ForwardTestMonitorState,
        candle: Candle1m,
        bias: Bias
    ) -> Optional[StateTransition]:
        """
        Проверить TP и SL.

        Same-bar rules:
        - LONG: low → high (SL проверяем первым)
        - SHORT: high → low (SL проверяем первым)
        """
        current_sl = state.current_sl or snapshot.stop_loss

        # Update MAE/MFE
        state.mae_price = self.fill_sim.get_mae_price(candle, bias, state.mae_price)
        state.mfe_price = self.fill_sim.get_mfe_price(candle, bias, state.mfe_price)

        if state.initial_risk_per_unit and state.initial_risk_per_unit > 0:
            if state.mae_price and state.avg_entry_price:
                state.mae_r = self.fill_sim.calculate_r_multiple(
                    state.avg_entry_price, state.mae_price,
                    state.initial_risk_per_unit, bias
                )
            if state.mfe_price and state.avg_entry_price:
                state.mfe_r = self.fill_sim.calculate_r_multiple(
                    state.avg_entry_price, state.mfe_price,
                    state.initial_risk_per_unit, bias
                )

        # Same-bar order
        if bias == Bias.LONG:
            # 1. Check SL by low
            sl_hit = self.fill_sim.check_sl_touch(current_sl, candle, bias)
            if sl_hit:
                return await self._handle_sl_or_be(session, snapshot, state, candle, bias)

            # 2. Check TPs by high
            return await self._check_tp_levels(session, snapshot, state, candle, bias)
        else:
            # 1. Check SL by high
            sl_hit = self.fill_sim.check_sl_touch(current_sl, candle, bias)
            if sl_hit:
                return await self._handle_sl_or_be(session, snapshot, state, candle, bias)

            # 2. Check TPs by low
            return await self._check_tp_levels(session, snapshot, state, candle, bias)

    async def _check_tp_levels(
        self,
        session: AsyncSession,
        snapshot: ForwardTestSnapshot,
        state: ForwardTestMonitorState,
        candle: Candle1m,
        bias: Bias
    ) -> Optional[StateTransition]:
        """Проверить TP уровни."""
        tp_prices = [
            (1, snapshot.tp1_price),
            (2, snapshot.tp2_price),
            (3, snapshot.tp3_price),
        ]

        for tp_num, tp_price in tp_prices:
            if not tp_price or tp_num <= state.tp_progress:
                continue

            if self.fill_sim.check_tp_touch(tp_price, candle, bias):
                if tp_num == 1:
                    return await self._handle_tp1(session, snapshot, state, candle, bias, tp_price)
                else:
                    return await self._handle_terminal_tp(session, snapshot, state, candle, bias, tp_num, tp_price)

        return None

    async def _handle_tp1(
        self,
        session: AsyncSession,
        snapshot: ForwardTestSnapshot,
        state: ForwardTestMonitorState,
        candle: Candle1m,
        bias: Bias,
        tp_price: float
    ) -> Optional[StateTransition]:
        """
        Обработать TP1 hit (milestone, не terminal!).

        - Partial close
        - Сдвинуть SL в BE если be_after_tp1
        - Обновить realized_r_so_far
        """
        old_state = ScenarioState(state.state)
        partial_close_pct = self.config.tp1_partial_close_pct

        # Рассчитать realized R от partial close
        if state.initial_risk_per_unit and state.initial_risk_per_unit > 0:
            exit_price = self.fill_sim.calculate_exit_price(tp_price, bias, is_tp=True)
            r_this_tp = self.fill_sim.calculate_r_multiple(
                state.avg_entry_price, exit_price,
                state.initial_risk_per_unit, bias
            )
            realized_r = r_this_tp * (partial_close_pct / 100)
            state.realized_r_so_far += realized_r
        else:
            realized_r = 0

        state.remaining_position_pct = 100 - partial_close_pct
        state.tp_progress = 1
        state.tp1_hit_at = candle.ts
        state.state = ScenarioState.TP1
        state.state_updated_at = candle.ts

        # BE logic
        if snapshot.be_after_tp1:
            state.current_sl = snapshot.be_price or state.avg_entry_price
            state.sl_moved_to_be = True

            # Event for BE move
            be_event = ForwardTestEvent(
                snapshot_id=snapshot.snapshot_id,
                ts=candle.ts,
                event_type=EventType.BE_MOVED,
                price=state.current_sl,
                details_json={"new_sl": state.current_sl}
            )
            session.add(be_event)

        # TP1 event
        event = ForwardTestEvent(
            snapshot_id=snapshot.snapshot_id,
            ts=candle.ts,
            event_type=EventType.TP1_HIT,
            price=tp_price,
            details_json={
                "partial_close_pct": partial_close_pct,
                "realized_r": realized_r,
                "remaining_pct": state.remaining_position_pct
            }
        )
        session.add(event)

        return StateTransition(
            snapshot_id=snapshot.snapshot_id,
            from_state=old_state,
            to_state=ScenarioState.TP1,
            price=tp_price,
            candle_ts=candle.ts
        )

    async def _handle_terminal_tp(
        self,
        session: AsyncSession,
        snapshot: ForwardTestSnapshot,
        state: ForwardTestMonitorState,
        candle: Candle1m,
        bias: Bias,
        tp_num: int,
        tp_price: float
    ) -> StateTransition:
        """Обработать terminal TP (TP2/TP3)."""
        old_state = ScenarioState(state.state)
        terminal_state = TerminalState.TP2 if tp_num == 2 else TerminalState.TP3
        new_state = ScenarioState.TP2 if tp_num == 2 else ScenarioState.TP3

        exit_price = self.fill_sim.calculate_exit_price(tp_price, bias, is_tp=True)
        state.exit_price = exit_price
        state.exit_reason = terminal_state.value
        state.exit_at = candle.ts
        state.state = new_state
        state.state_updated_at = candle.ts

        # Event
        event_type = EventType.TP2_HIT if tp_num == 2 else EventType.TP3_HIT
        event = ForwardTestEvent(
            snapshot_id=snapshot.snapshot_id,
            ts=candle.ts,
            event_type=event_type,
            price=tp_price,
            details_json={}
        )
        session.add(event)

        # Create outcome
        await self._create_outcome(
            session, snapshot, state, terminal_state, exit_price, candle.ts
        )

        return StateTransition(
            snapshot_id=snapshot.snapshot_id,
            from_state=old_state,
            to_state=new_state,
            price=exit_price,
            candle_ts=candle.ts
        )

    async def _handle_sl_or_be(
        self,
        session: AsyncSession,
        snapshot: ForwardTestSnapshot,
        state: ForwardTestMonitorState,
        candle: Candle1m,
        bias: Bias
    ) -> StateTransition:
        """Обработать SL или BE hit."""
        old_state = ScenarioState(state.state)

        # Определить тип выхода
        if state.sl_moved_to_be:
            terminal_state = TerminalState.BE
            new_state = ScenarioState.BE
            event_type = EventType.BE_HIT
        else:
            terminal_state = TerminalState.SL
            new_state = ScenarioState.SL
            event_type = EventType.SL_HIT

        sl_price = state.current_sl or snapshot.stop_loss
        exit_price = self.fill_sim.calculate_exit_price(sl_price, bias, is_tp=False)

        state.exit_price = exit_price
        state.exit_reason = terminal_state.value
        state.exit_at = candle.ts
        state.state = new_state
        state.state_updated_at = candle.ts

        # Event
        event = ForwardTestEvent(
            snapshot_id=snapshot.snapshot_id,
            ts=candle.ts,
            event_type=event_type,
            price=sl_price,
            details_json={"sl_moved_to_be": state.sl_moved_to_be}
        )
        session.add(event)

        # Create outcome
        await self._create_outcome(
            session, snapshot, state, terminal_state, exit_price, candle.ts
        )

        return StateTransition(
            snapshot_id=snapshot.snapshot_id,
            from_state=old_state,
            to_state=new_state,
            price=exit_price,
            candle_ts=candle.ts
        )

    async def _handle_expiration(
        self,
        session: AsyncSession,
        snapshot: ForwardTestSnapshot,
        state: ForwardTestMonitorState,
        candle: Candle1m
    ) -> StateTransition:
        """Обработать expiration."""
        old_state = ScenarioState(state.state)

        state.state = ScenarioState.EXPIRED
        state.state_updated_at = candle.ts
        state.exit_at = candle.ts
        state.exit_reason = "expired"

        # Event
        event = ForwardTestEvent(
            snapshot_id=snapshot.snapshot_id,
            ts=candle.ts,
            event_type=EventType.EXPIRED,
            price=candle.close,
            details_json={}
        )
        session.add(event)

        # Create outcome только если был вход
        if state.entered_at:
            await self._create_outcome(
                session, snapshot, state, TerminalState.EXPIRED, candle.close, candle.ts
            )

        return StateTransition(
            snapshot_id=snapshot.snapshot_id,
            from_state=old_state,
            to_state=ScenarioState.EXPIRED,
            price=candle.close,
            candle_ts=candle.ts
        )

    async def _create_outcome(
        self,
        session: AsyncSession,
        snapshot: ForwardTestSnapshot,
        state: ForwardTestMonitorState,
        terminal_state: TerminalState,
        exit_price: float,
        exit_ts: datetime
    ):
        """Создать outcome при terminal state."""
        bias = Bias(state.bias_final)

        # Рассчитать remaining R
        remaining_r = 0.0
        if state.initial_risk_per_unit and state.initial_risk_per_unit > 0 and state.avg_entry_price:
            remaining_r = self.fill_sim.calculate_r_multiple(
                state.avg_entry_price, exit_price,
                state.initial_risk_per_unit, bias
            ) * (state.remaining_position_pct / 100)

        total_r = state.realized_r_so_far + remaining_r

        # Определить result
        is_profit = total_r > 0
        pnl_class = PnLClass.from_r(total_r)

        if terminal_state in (TerminalState.TP2, TerminalState.TP3):
            result = OutcomeResult.WIN
        elif terminal_state == TerminalState.SL:
            result = OutcomeResult.LOSS
        elif terminal_state == TerminalState.BE:
            # BE после TP1 = WIN!
            result = OutcomeResult.WIN if is_profit else OutcomeResult.BREAKEVEN
        else:
            result = OutcomeResult.EXPIRED

        # Timing
        time_to_trigger = None
        time_to_entry = None
        time_to_exit = None
        hold_time = None

        if state.triggered_at:
            time_to_trigger = int((state.triggered_at - snapshot.generated_at).total_seconds())
        if state.entered_at:
            time_to_entry = int((state.entered_at - snapshot.generated_at).total_seconds())
        if exit_ts:
            time_to_exit = int((exit_ts - snapshot.generated_at).total_seconds())
        if state.entered_at and exit_ts:
            hold_time = int((exit_ts - state.entered_at).total_seconds())

        # Trace JSON
        trace_json = {
            "triggered_ts": state.triggered_at.isoformat() if state.triggered_at else None,
            "entered_ts": state.entered_at.isoformat() if state.entered_at else None,
            "tp1_ts": state.tp1_hit_at.isoformat() if state.tp1_hit_at else None,
            "exit_ts": exit_ts.isoformat() if exit_ts else None,
            "exit_candle_ts": state.last_checked_candle_ts.isoformat() if state.last_checked_candle_ts else None,
            "same_bar_rule": "low_first" if bias == Bias.LONG else "high_first",
        }

        outcome = ForwardTestOutcome(
            snapshot_id=snapshot.snapshot_id,
            result=result,
            terminal_state=terminal_state,
            is_profit=is_profit,
            pnl_class=pnl_class,
            realized_r_from_tp1=state.realized_r_so_far,
            remaining_r=remaining_r,
            total_r=total_r,
            fill_pct_at_exit=state.fill_pct,
            mae_r=state.mae_r,
            mfe_r=state.mfe_r,
            time_to_trigger_sec=time_to_trigger,
            time_to_entry_sec=time_to_entry,
            time_to_exit_sec=time_to_exit,
            hold_time_sec=hold_time,
            fill_model=state.fill_model,
            slippage_bps=self.config.slippage.entry_bps,
            fees_bps=self.config.slippage.fees_bps,
            trace_json=trace_json
        )
        session.add(outcome)

    def _get_entry_orders(self, snapshot: ForwardTestSnapshot) -> List[EntryOrder]:
        """Извлечь entry orders из snapshot."""
        normalized = snapshot.normalized_json or {}
        entry_plan = normalized.get("entry_plan", {})
        orders_data = entry_plan.get("orders", [])

        orders = []
        for i, o in enumerate(orders_data):
            price = o.get("price")
            size_pct = o.get("size_pct", 0)
            if price and size_pct > 0:
                orders.append(EntryOrder(idx=i, price=float(price), size_pct=float(size_pct)))

        return orders

    async def _get_candles(
        self,
        symbol: str,
        since: Optional[datetime]
    ) -> List[Candle1m]:
        """Получить 1m свечи от Bybit."""
        try:
            # Определить сколько свечей нужно
            if since:
                minutes_ago = int((datetime.now(UTC) - since).total_seconds() / 60)
                limit = min(max(minutes_ago + 5, 10), 200)  # +5 buffer, max 200
            else:
                limit = 5

            df = await self.bybit.get_klines(symbol, "1", limit=limit)
            if df is None or df.empty:
                return []

            candles = []
            for _, row in df.iterrows():
                ts = row.get("timestamp") or row.get("open_time")
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                elif not isinstance(ts, datetime):
                    ts = datetime.fromtimestamp(ts / 1000, UTC)

                candles.append(Candle1m(
                    ts=ts,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0))
                ))

            # Сортировать по времени
            candles.sort(key=lambda c: c.ts)

            # Убрать текущую незакрытую свечу
            now = datetime.now(UTC)
            candles = [c for c in candles if c.ts < now - timedelta(minutes=1)]

            return candles

        except Exception as e:
            logger.error(f"Failed to get candles for {symbol}: {e}")
            return []

    async def _acquire_lock(self) -> bool:
        """Acquire distributed lock."""
        try:
            if not self._redis:
                self._redis = redis.from_url("redis://localhost:6379")

            result = await self._redis.set(
                self.LOCK_KEY,
                "1",
                nx=True,
                ex=self.LOCK_TTL_SEC
            )
            return result is not None
        except Exception as e:
            logger.warning(f"Redis lock failed, proceeding without lock: {e}")
            return True  # Fallback: proceed without lock

    async def _release_lock(self):
        """Release distributed lock."""
        try:
            if self._redis:
                await self._redis.delete(self.LOCK_KEY)
        except Exception:
            pass


# Singleton
monitor_service = MonitorService()
