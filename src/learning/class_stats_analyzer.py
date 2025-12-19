"""
Class Stats Analyzer

Анализатор статистики по классам сценариев для context gates.
Класс = archetype + side + timeframe + [trend + vol + funding + sentiment]

Функционал:
- Группировка trades по ClassKey (L1 coarse, L2 fine)
- Rolling window статистика (90 дней)
- Context gates: kill switch, boost, cooldown
- Lookup с fallback L2 -> L1
"""
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict
from dataclasses import dataclass

from loguru import logger
from sqlalchemy import select, and_, func, delete, String
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

from src.database.models import (
    TradeOutcome,
    TradeOutcomeLabel,
    ScenarioClassStats,
    ScenarioGenerationLog,
)
from src.learning.class_key import ClassKey, build_class_key_from_trade
from src.learning.constants import (
    ANY_BUCKET,
    DEFAULT_WINDOW_DAYS,
    MIN_TRADES_FOR_GATES,
    MIN_TRADES_PRELIMINARY,
    MIN_TRADES_INSUFFICIENT,
    KILL_SWITCH_EV_THRESHOLD,
    KILL_SWITCH_PF_THRESHOLD,
    MAX_DRAWDOWN_THRESHOLD,
    MAX_DRAWDOWN_PRELIMINARY,
    BOOST_EV_THRESHOLD,
    BOOST_WINRATE_THRESHOLD,
    BOOST_MAX_DD_THRESHOLD,
    BOOST_CONFIDENCE_MODIFIER,
    BOOST_EV_PRIOR,
    PRELIMINARY_CONFIDENCE_PENALTY,
    COOLDOWN_HOURS,
)
from src.learning.drawdown_calculator import calculate_max_drawdown
from src.learning.confidence_intervals import (
    wilson_score_lower,
    ev_lower_ci,
    ev_confidence_interval,
)


@dataclass
class ClassStatsLookupResult:
    """Результат lookup class stats с metadata."""
    stats: Optional[ScenarioClassStats]
    fallback_used: bool
    fallback_from: Optional[str]    # "L2" if L2 -> L1 fallback
    fallback_reason: Optional[str]  # "insufficient_sample" / "not_found"
    requested_level: int            # 1 or 2


class ClassStatsAnalyzer:
    """
    Анализатор статистики по классам сценариев.

    Паттерны из archetype_analyzer.py:
    - _group_trades() → defaultdict по ClassKey
    - _calculate_class_stats() → numpy для метрик
    - _upsert_stats() → select + update/insert
    - Singleton instance
    """

    async def recalculate_stats(
        self,
        session: AsyncSession,
        window_days: int = DEFAULT_WINDOW_DAYS,
        include_testnet: bool = False,
    ) -> Dict[str, Any]:
        """
        Пересчитать статистику по всем классам.

        Args:
            session: AsyncSession
            window_days: Rolling window в днях
            include_testnet: Включать testnet trades

        Returns:
            Dict с результатами пересчёта
        """
        logger.info(f"Starting class stats recalculation (window={window_days} days)")

        # 1. Загрузить trades за rolling window
        cutoff_date = datetime.now(UTC) - timedelta(days=window_days)

        conditions = [
            TradeOutcome.created_at >= cutoff_date,
            TradeOutcome.primary_archetype.isnot(None),
        ]
        if not include_testnet:
            conditions.append(TradeOutcome.is_testnet == False)

        stmt = select(TradeOutcome).where(and_(*conditions)).order_by(
            TradeOutcome.created_at.asc()
        )
        result = await session.execute(stmt)
        trades = list(result.scalars().all())

        if not trades:
            logger.warning("No trades found for class stats recalculation")
            return {"classes_updated": 0, "total_trades": 0}

        # 2. Загрузить generated counts за rolling window
        generated_counts = await self._get_generated_counts(
            session, cutoff_date, include_testnet
        )

        # 3. Группировать trades по ClassKey
        groups = self._group_trades(trades)

        # 4. Рассчитать статистику для каждой группы
        stats_records = []
        for class_key, group_trades in groups.items():
            if len(group_trades) < MIN_TRADES_INSUFFICIENT:
                continue

            # Рассчитать метрики
            stats_data = self._calculate_class_stats(
                class_key=class_key,
                trades=group_trades,
                generated_counts=generated_counts,
                window_days=window_days,
            )

            # Применить context gates
            self._apply_context_gates(stats_data, group_trades)

            stats_records.append(stats_data)

        # 5. Upsert в БД
        await self._upsert_stats(session, stats_records)

        logger.info(
            f"Class stats recalculation complete: "
            f"{len(stats_records)} classes updated from {len(trades)} trades"
        )

        return {
            "classes_updated": len(stats_records),
            "total_trades": len(trades),
            "l1_classes": sum(1 for s in stats_records if s["class_key"].level == 1),
            "l2_classes": sum(1 for s in stats_records if s["class_key"].level == 2),
        }

    async def get_class_stats(
        self,
        session: AsyncSession,
        class_key: ClassKey,
        allow_fallback: bool = True,
    ) -> ClassStatsLookupResult:
        """
        Получить статистику для класса с fallback.

        Args:
            session: AsyncSession
            class_key: ClassKey для поиска
            allow_fallback: Разрешить L2 -> L1 fallback

        Returns:
            ClassStatsLookupResult с stats и metadata
        """
        # Сначала ищем точное совпадение
        stats = await self._lookup_by_hash(session, class_key.key_hash)

        if stats:
            # Проверяем sample size
            if stats.total_trades >= MIN_TRADES_INSUFFICIENT:
                return ClassStatsLookupResult(
                    stats=stats,
                    fallback_used=False,
                    fallback_from=None,
                    fallback_reason=None,
                    requested_level=class_key.level,
                )
            # Insufficient sample - пробуем fallback
            if allow_fallback and class_key.level == 2:
                l1_key = class_key.to_l1_key()
                l1_stats = await self._lookup_by_hash(session, l1_key.key_hash)
                if l1_stats and l1_stats.total_trades >= MIN_TRADES_INSUFFICIENT:
                    return ClassStatsLookupResult(
                        stats=l1_stats,
                        fallback_used=True,
                        fallback_from="L2",
                        fallback_reason="insufficient_sample",
                        requested_level=2,
                    )
            return ClassStatsLookupResult(
                stats=stats,
                fallback_used=False,
                fallback_from=None,
                fallback_reason=None,
                requested_level=class_key.level,
            )

        # Не найдено - пробуем L1 fallback
        if allow_fallback and class_key.level == 2:
            l1_key = class_key.to_l1_key()
            l1_stats = await self._lookup_by_hash(session, l1_key.key_hash)
            if l1_stats:
                return ClassStatsLookupResult(
                    stats=l1_stats,
                    fallback_used=True,
                    fallback_from="L2",
                    fallback_reason="not_found",
                    requested_level=2,
                )

        return ClassStatsLookupResult(
            stats=None,
            fallback_used=False,
            fallback_from=None,
            fallback_reason="not_found",
            requested_level=class_key.level,
        )

    async def log_scenario_generation(
        self,
        session: AsyncSession,
        analysis_id: str,
        scenario_local_id: int,
        user_id: int,
        symbol: str,
        timeframe: str,
        class_key: ClassKey,
        is_testnet: bool = False,
    ) -> bool:
        """
        Залогировать генерацию сценария (идемпотентно).

        Args:
            session: AsyncSession
            analysis_id: UUID анализа от Syntra
            scenario_local_id: 1..N в рамках analysis
            user_id: User ID
            symbol: Trading symbol
            timeframe: Timeframe
            class_key: ClassKey сценария
            is_testnet: Testnet flag

        Returns:
            True если новая запись, False если уже существует
        """
        # Проверяем существование
        stmt = select(ScenarioGenerationLog).where(
            and_(
                ScenarioGenerationLog.analysis_id == analysis_id,
                ScenarioGenerationLog.scenario_local_id == scenario_local_id,
            )
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return False

        # Создаём новую запись
        log_entry = ScenarioGenerationLog(
            analysis_id=analysis_id,
            scenario_local_id=scenario_local_id,
            user_id=user_id,
            symbol=symbol,
            timeframe=timeframe,
            class_key_hash=class_key.key_hash,
            archetype=class_key.archetype,
            side=class_key.side,
            is_testnet=is_testnet,
        )
        session.add(log_entry)
        await session.flush()

        return True

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    async def _lookup_by_hash(
        self,
        session: AsyncSession,
        key_hash: str,
    ) -> Optional[ScenarioClassStats]:
        """Lookup по hash."""
        stmt = select(ScenarioClassStats).where(
            ScenarioClassStats.class_key_hash == key_hash
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_generated_counts(
        self,
        session: AsyncSession,
        cutoff_date: datetime,
        include_testnet: bool,
    ) -> Dict[str, int]:
        """Получить generated counts по class_key_hash."""
        conditions = [ScenarioGenerationLog.created_at >= cutoff_date]
        if not include_testnet:
            conditions.append(ScenarioGenerationLog.is_testnet == False)

        stmt = select(
            ScenarioGenerationLog.class_key_hash,
            func.count(func.distinct(
                ScenarioGenerationLog.analysis_id + '_' +
                func.cast(ScenarioGenerationLog.scenario_local_id, String)
            )).label('count')
        ).where(
            and_(*conditions)
        ).group_by(ScenarioGenerationLog.class_key_hash)

        result = await session.execute(stmt)
        return {row.class_key_hash: row.count for row in result}

    def _group_trades(
        self,
        trades: List[TradeOutcome],
    ) -> Dict[ClassKey, List[TradeOutcome]]:
        """
        Группировать trades по ClassKey.

        Создаёт группы для:
        - L2 (fine): полный class key с buckets
        - L1 (coarse): archetype + side + timeframe
        """
        groups: Dict[ClassKey, List[TradeOutcome]] = defaultdict(list)

        for trade in trades:
            archetype = trade.primary_archetype
            side = trade.side.lower() if trade.side else "long"
            timeframe = trade.timeframe or "4h"

            # Строим L2 key из attribution_data
            l2_key = build_class_key_from_trade(
                archetype=archetype,
                side=side,
                timeframe=timeframe,
                attribution_data=trade.attribution_data,
            )

            # Добавляем в L2 группу
            groups[l2_key].append(trade)

            # Добавляем в L1 группу
            l1_key = l2_key.to_l1_key()
            if l1_key != l2_key:  # Только если L2 != L1
                groups[l1_key].append(trade)

        return groups

    def _calculate_class_stats(
        self,
        class_key: ClassKey,
        trades: List[TradeOutcome],
        generated_counts: Dict[str, int],
        window_days: int,
    ) -> Dict[str, Any]:
        """Рассчитать статистику для группы trades."""
        total = len(trades)
        wins = sum(1 for t in trades if t.label == TradeOutcomeLabel.WIN)
        losses = sum(1 for t in trades if t.label == TradeOutcomeLabel.LOSS)

        # === PROFITABILITY ===
        winrate = wins / total if total > 0 else 0

        # Wilson score lower CI
        winrate_lower = wilson_score_lower(wins, total)

        # PnL metrics
        pnl_values = [t.pnl_r or 0 for t in trades]
        avg_pnl_r = float(np.mean(pnl_values)) if pnl_values else 0

        # EV metrics
        avg_ev_r = avg_pnl_r  # В простом случае EV = avg PnL
        ev_ci = ev_confidence_interval(pnl_values)
        ev_lower = ev_ci.lower

        # Profit factor
        gross_profit = sum(p for p in pnl_values if p > 0)
        gross_loss = abs(sum(p for p in pnl_values if p < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # === CONVERSION ===
        generated_count = generated_counts.get(class_key.key_hash, 0)
        traded_count = total
        conversion_rate = traded_count / generated_count if generated_count > 0 else 0

        # === TERMINAL OUTCOMES ===
        exit_sl_count = sum(1 for t in trades if t.terminal_outcome == "sl")
        exit_tp1_count = sum(1 for t in trades if t.terminal_outcome == "tp1")
        exit_tp2_count = sum(1 for t in trades if t.terminal_outcome == "tp2")
        exit_tp3_count = sum(1 for t in trades if t.terminal_outcome == "tp3")
        exit_other_count = sum(1 for t in trades if t.terminal_outcome == "other")

        other_trades = [t for t in trades if t.terminal_outcome == "other"]
        other_pnl = [t.pnl_r or 0 for t in other_trades]
        avg_pnl_r_other = float(np.mean(other_pnl)) if other_pnl else 0

        # === RISK ===
        # Max drawdown (trades должны быть отсортированы по времени!)
        sorted_pnl = [t.pnl_r or 0 for t in sorted(trades, key=lambda x: x.created_at)]
        dd_result = calculate_max_drawdown(sorted_pnl)
        max_drawdown_r = dd_result.max_drawdown_r

        # MAE/MFE
        mae_values = [t.mae_r or 0 for t in trades if t.mae_r is not None]
        mfe_values = [t.mfe_r or 0 for t in trades if t.mfe_r is not None]

        avg_mae_r = float(np.mean(mae_values)) if mae_values else 0
        avg_mfe_r = float(np.mean(mfe_values)) if mfe_values else 0
        p75_mae_r = float(np.percentile(mae_values, 75)) if mae_values else 0
        p90_mae_r = float(np.percentile(mae_values, 90)) if mae_values else 0

        # Time in trade
        time_values = [t.time_in_trade_min or 0 for t in trades if t.time_in_trade_min]
        avg_time_in_trade_min = float(np.mean(time_values)) if time_values else 0

        # === EXECUTION ===
        # fill_rate пока 1.0 (позже интегрируем с selected trades)
        fill_rate = 1.0

        # Slippage (заглушка, нужны данные execution)
        avg_slippage_r = 0.0

        # Other exit rate
        other_exit_rate = exit_other_count / total if total > 0 else 0

        return {
            "class_key": class_key,
            # Key fields
            "class_key_hash": class_key.key_hash,
            "class_key_string": class_key.key_string,
            "archetype": class_key.archetype,
            "side": class_key.side,
            "timeframe": class_key.timeframe,
            "trend_bucket": class_key.trend_bucket,
            "vol_bucket": class_key.vol_bucket,
            "funding_bucket": class_key.funding_bucket,
            "sentiment_bucket": class_key.sentiment_bucket,
            # Profitability
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "winrate": winrate,
            "winrate_lower_ci": winrate_lower,
            "avg_pnl_r": avg_pnl_r,
            "avg_ev_r": avg_ev_r,
            "ev_lower_ci": ev_lower,
            "profit_factor": profit_factor,
            # Conversion
            "generated_count": generated_count,
            "traded_count": traded_count,
            "conversion_rate": conversion_rate,
            # Terminal outcomes
            "exit_sl_count": exit_sl_count,
            "exit_tp1_count": exit_tp1_count,
            "exit_tp2_count": exit_tp2_count,
            "exit_tp3_count": exit_tp3_count,
            "exit_other_count": exit_other_count,
            "avg_pnl_r_other": avg_pnl_r_other,
            # Risk
            "max_drawdown_r": max_drawdown_r,
            "avg_mae_r": avg_mae_r,
            "avg_mfe_r": avg_mfe_r,
            "p75_mae_r": p75_mae_r,
            "p90_mae_r": p90_mae_r,
            "avg_time_in_trade_min": avg_time_in_trade_min,
            # Execution
            "fill_rate": fill_rate,
            "avg_slippage_r": avg_slippage_r,
            "other_exit_rate": other_exit_rate,
            # Meta
            "window_days": window_days,
            "last_calculated_at": datetime.now(UTC),
        }

    def _apply_context_gates(
        self,
        stats_data: Dict[str, Any],
        trades: List[TradeOutcome],
    ):
        """
        Применить context gates логику.

        Kill switch (sample >= 50, с CI):
        - EV < 0 AND ev_lower_ci < 0 AND profit_factor < 0.8

        Excessive drawdown (sample >= 50):
        - max_drawdown_r > 5.0R

        Preliminary warning (20-49 trades):
        - EV < 0 OR max_dd > 4.0R (НЕ hard disable)

        Boost (sample >= 50):
        - EV >= 0.5R AND winrate >= 55% AND max_dd < 3R
        """
        total = stats_data["total_trades"]
        avg_ev_r = stats_data["avg_ev_r"]
        ev_lower = stats_data["ev_lower_ci"]
        profit_factor = stats_data["profit_factor"]
        max_dd = stats_data["max_drawdown_r"]
        winrate = stats_data["winrate"]

        # Defaults
        is_enabled = True
        disable_reason = None
        preliminary_warning = None
        confidence_modifier = 0.0
        ev_prior_boost = 0.0
        disabled_until = None

        # === RELIABLE SAMPLE (>= 50) ===
        if total >= MIN_TRADES_FOR_GATES:
            # Kill switch check
            if (avg_ev_r < KILL_SWITCH_EV_THRESHOLD and
                ev_lower < KILL_SWITCH_EV_THRESHOLD and
                profit_factor < KILL_SWITCH_PF_THRESHOLD):
                is_enabled = False
                disable_reason = (
                    f"kill_switch: EV={avg_ev_r:.2f}R (CI<0), PF={profit_factor:.2f}"
                )
                disabled_until = datetime.now(UTC) + timedelta(hours=COOLDOWN_HOURS)

            # Excessive drawdown check
            elif max_dd > MAX_DRAWDOWN_THRESHOLD:
                is_enabled = False
                disable_reason = f"excessive_drawdown: {max_dd:.2f}R"
                disabled_until = datetime.now(UTC) + timedelta(hours=COOLDOWN_HOURS)

            # Boost check (только если не disabled)
            elif (avg_ev_r >= BOOST_EV_THRESHOLD and
                  winrate >= BOOST_WINRATE_THRESHOLD and
                  max_dd < BOOST_MAX_DD_THRESHOLD):
                confidence_modifier = BOOST_CONFIDENCE_MODIFIER
                ev_prior_boost = BOOST_EV_PRIOR

        # === PRELIMINARY SAMPLE (20-49) ===
        elif total >= MIN_TRADES_PRELIMINARY:
            # Warning only, не hard disable
            if avg_ev_r < KILL_SWITCH_EV_THRESHOLD or max_dd > MAX_DRAWDOWN_PRELIMINARY:
                preliminary_warning = (
                    f"preliminary_negative: EV={avg_ev_r:.2f}R, DD={max_dd:.2f}R"
                )
            # Penalty для preliminary
            confidence_modifier = PRELIMINARY_CONFIDENCE_PENALTY

        # === INSUFFICIENT SAMPLE (< 20) ===
        else:
            # Нет gates, но можно дать penalty
            confidence_modifier = PRELIMINARY_CONFIDENCE_PENALTY * 2

        # Записываем в stats_data
        stats_data["is_enabled"] = is_enabled
        stats_data["disable_reason"] = disable_reason
        stats_data["preliminary_warning"] = preliminary_warning
        stats_data["confidence_modifier"] = confidence_modifier
        stats_data["ev_prior_boost"] = ev_prior_boost
        stats_data["disabled_until"] = disabled_until

    async def _upsert_stats(
        self,
        session: AsyncSession,
        stats_records: List[Dict[str, Any]],
    ):
        """Upsert class stats records."""
        for record in stats_records:
            class_key = record.pop("class_key")

            # Lookup existing
            stmt = select(ScenarioClassStats).where(
                ScenarioClassStats.class_key_hash == record["class_key_hash"]
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Check cooldown before updating is_enabled
                now = datetime.now(UTC)
                if (existing.is_enabled == False and
                    existing.disabled_until and
                    now < existing.disabled_until):
                    # В cooldown - не меняем is_enabled
                    record["is_enabled"] = existing.is_enabled
                    record["disable_reason"] = existing.disable_reason
                    record["disabled_until"] = existing.disabled_until
                else:
                    # Можно менять is_enabled
                    if existing.is_enabled != record["is_enabled"]:
                        record["last_state_change_at"] = now

                # Update existing
                for key, value in record.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                # Create new
                new_stats = ScenarioClassStats(**record)
                new_stats.last_state_change_at = datetime.now(UTC)
                session.add(new_stats)

        await session.commit()

    async def cleanup_old_stats(
        self,
        session: AsyncSession,
        window_days: int = DEFAULT_WINDOW_DAYS,
    ) -> int:
        """
        Удалить stats для классов без trades за window.

        Returns:
            Количество удалённых записей
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=window_days)

        # Находим class_key_hash с trades за период
        active_stmt = select(
            func.distinct(TradeOutcome.primary_archetype)
        ).where(TradeOutcome.created_at >= cutoff_date)

        # Это упрощённая версия - полноценный cleanup требует
        # джойна с trades и проверки конкретных hash'ей

        logger.info(f"Cleanup of old class stats (older than {window_days} days)")
        return 0  # Пока не реализован полный cleanup

    # =========================================================================
    # PAPER TRADING INTEGRATION
    # =========================================================================

    async def apply_paper_outcomes(
        self,
        session: AsyncSession,
        outcomes: List[Dict[str, Any]],
        weight: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Применить paper outcomes к статистике классов.

        Paper trades имеют меньший вес чем real trades.
        Gates разблокируются при достижении порогов:
        - paper_wr_gate (N>=30): WR калибровка
        - paper_ev_gate (N>=50): EV калибровка
        - paper_sl_opt_gate (N>=200): SL/TP suggestions

        Args:
            session: AsyncSession
            outcomes: List of outcome dicts with:
                - archetype: str
                - side: str (long/short)
                - timeframe: str
                - result: str (win/loss/breakeven/expired)
                - total_r: float
                - mae_r: Optional[float]
                - mfe_r: Optional[float]
            weight: Weight of paper trades vs real (default 0.3)

        Returns:
            Dict with stats: {updated: N, created: N}
        """
        from src.learning.class_key import ClassKey
        from src.services.forward_test.config import get_config

        config = get_config()
        updated = 0
        created = 0
        now = datetime.now(UTC)

        # Group outcomes by L1 class key (archetype + side + timeframe)
        groups: Dict[str, List[Dict]] = defaultdict(list)
        for outcome in outcomes:
            key = f"{outcome['archetype']}|{outcome['side']}|{outcome['timeframe']}"
            groups[key].append(outcome)

        for key_str, group_outcomes in groups.items():
            archetype, side, timeframe = key_str.split("|")

            # Build L1 class key (coarse level)
            class_key = ClassKey.create_l1(
                archetype=archetype,
                side=side,
                timeframe=timeframe,
            )

            # Calculate paper metrics
            wins = sum(1 for o in group_outcomes if o["result"] == "win")
            losses = sum(1 for o in group_outcomes if o["result"] == "loss")
            total_trades = len(group_outcomes)
            total_r = sum(o["total_r"] for o in group_outcomes)

            paper_entered = total_trades
            paper_wins = wins
            paper_losses = losses
            paper_wr = wins / (wins + losses) if (wins + losses) > 0 else None
            paper_ev_r = total_r / total_trades if total_trades > 0 else None

            mae_values = [o["mae_r"] for o in group_outcomes if o.get("mae_r") is not None]
            mfe_values = [o["mfe_r"] for o in group_outcomes if o.get("mfe_r") is not None]
            paper_mae_r_avg = sum(mae_values) / len(mae_values) if mae_values else None
            paper_mfe_r_avg = sum(mfe_values) / len(mfe_values) if mfe_values else None

            # Find or create stats record
            stmt = select(ScenarioClassStats).where(
                ScenarioClassStats.class_key_hash == class_key.key_hash
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Accumulate paper stats
                existing.paper_entered += paper_entered
                existing.paper_wins += paper_wins
                existing.paper_losses += paper_losses

                # Recalculate derived metrics
                total_paper = existing.paper_entered
                total_wins = existing.paper_wins
                total_losses = existing.paper_losses

                if total_wins + total_losses > 0:
                    existing.paper_wr = total_wins / (total_wins + total_losses)

                # Rolling average for R and MAE/MFE
                if paper_ev_r is not None:
                    if existing.paper_ev_r is not None:
                        # Weighted average
                        old_weight = (total_paper - paper_entered) / total_paper
                        new_weight = paper_entered / total_paper
                        existing.paper_ev_r = (
                            existing.paper_ev_r * old_weight +
                            paper_ev_r * new_weight
                        )
                    else:
                        existing.paper_ev_r = paper_ev_r

                if paper_mae_r_avg is not None:
                    if existing.paper_mae_r_avg is not None:
                        old_weight = (total_paper - paper_entered) / total_paper
                        new_weight = paper_entered / total_paper
                        existing.paper_mae_r_avg = (
                            existing.paper_mae_r_avg * old_weight +
                            paper_mae_r_avg * new_weight
                        )
                    else:
                        existing.paper_mae_r_avg = paper_mae_r_avg

                if paper_mfe_r_avg is not None:
                    if existing.paper_mfe_r_avg is not None:
                        old_weight = (total_paper - paper_entered) / total_paper
                        new_weight = paper_entered / total_paper
                        existing.paper_mfe_r_avg = (
                            existing.paper_mfe_r_avg * old_weight +
                            paper_mfe_r_avg * new_weight
                        )
                    else:
                        existing.paper_mfe_r_avg = paper_mfe_r_avg

                existing.paper_last_updated = now
                updated += 1

                logger.info(
                    f"[ClassStats] Updated paper stats for {archetype}|{side}|{timeframe}: "
                    f"entered={existing.paper_entered}, wr={existing.paper_wr:.1%}"
                )
            else:
                # Create new record with paper stats only
                new_stats = ScenarioClassStats(
                    class_key_hash=class_key.key_hash,
                    class_key_string=class_key.key_string,
                    archetype=archetype,
                    side=side,
                    timeframe=timeframe,
                    trend_bucket=ANY_BUCKET,
                    vol_bucket=ANY_BUCKET,
                    funding_bucket=ANY_BUCKET,
                    sentiment_bucket=ANY_BUCKET,
                    # Initialize paper stats
                    paper_entered=paper_entered,
                    paper_wins=paper_wins,
                    paper_losses=paper_losses,
                    paper_wr=paper_wr,
                    paper_ev_r=paper_ev_r,
                    paper_mae_r_avg=paper_mae_r_avg,
                    paper_mfe_r_avg=paper_mfe_r_avg,
                    paper_last_updated=now,
                    # Leave real stats at defaults
                    created_at=now,
                    last_state_change_at=now,
                )
                session.add(new_stats)
                created += 1

                logger.info(
                    f"[ClassStats] Created paper stats for {archetype}|{side}|{timeframe}: "
                    f"entered={paper_entered}"
                )

        await session.commit()

        return {
            "updated": updated,
            "created": created,
            "total_outcomes": len(outcomes),
            "weight": weight,
        }

    def check_paper_gates(
        self,
        stats: ScenarioClassStats,
    ) -> Dict[str, bool]:
        """
        Проверить какие gates разблокированы paper данными.

        Learning Gates:
        - paper_wr_gate (N>=30): WR калибровка
        - paper_ev_gate (N>=50): EV калибровка
        - paper_sl_opt_gate (N>=200): SL/TP suggestions

        Args:
            stats: ScenarioClassStats with paper_* fields

        Returns:
            Dict with gate statuses
        """
        from src.services.forward_test.config import get_config
        config = get_config()

        paper_entered = stats.paper_entered or 0

        return {
            "wr_gate_unlocked": paper_entered >= config.learning_gates.paper_wr_gate,
            "ev_gate_unlocked": paper_entered >= config.learning_gates.paper_ev_gate,
            "sl_opt_gate_unlocked": paper_entered >= config.learning_gates.paper_sl_opt_gate,
            "paper_entered": paper_entered,
            "wr_gate_threshold": config.learning_gates.paper_wr_gate,
            "ev_gate_threshold": config.learning_gates.paper_ev_gate,
            "sl_opt_gate_threshold": config.learning_gates.paper_sl_opt_gate,
        }

    def get_effective_wr(
        self,
        stats: ScenarioClassStats,
        prior_wr: float = 0.5,
    ) -> float:
        """
        Получить effective winrate с учётом paper данных.

        Логика смешивания:
        - Если есть real >= 10: использовать real (override)
        - Если есть paper >= 30: paper * 0.7 + prior * 0.3
        - Иначе: prior

        Args:
            stats: ScenarioClassStats
            prior_wr: Prior winrate (default 0.5)

        Returns:
            Effective winrate
        """
        from src.services.forward_test.config import get_config
        config = get_config()

        real_entered = stats.total_trades or 0
        paper_entered = stats.paper_entered or 0

        # Real override
        if real_entered >= config.learning_gates.real_override_gate:
            return stats.winrate

        # Paper + prior blend
        if paper_entered >= config.learning_gates.paper_wr_gate:
            paper_wr = stats.paper_wr or prior_wr
            return paper_wr * 0.7 + prior_wr * 0.3

        # Only prior
        return prior_wr


# Singleton instance
class_stats_analyzer = ClassStatsAnalyzer()
