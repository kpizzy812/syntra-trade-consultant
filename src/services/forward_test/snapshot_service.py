"""
Snapshot Service

Генерация snapshots AI-сценариев для forward testing.
Запускается каждые 6 часов (00/06/12/18 UTC).
"""
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from typing import Dict, Any, List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.forward_test.config import get_config
from src.services.forward_test.enums import Bias, ScenarioState, FillModel
from src.services.forward_test.models import (
    ForwardTestSnapshot,
    ForwardTestMonitorState,
)
from src.services.forward_test.portfolio_manager import portfolio_manager
from src.services.forward_test.epoch_manager import get_current_epoch
from src.services.futures_analysis_service import FuturesAnalysisService


@dataclass
class BatchResult:
    """Результат генерации batch."""
    batch_id: str
    batch_ts: datetime
    total_generated: int
    by_symbol: Dict[str, int]
    errors: List[str]


class SnapshotService:
    """
    Генерация snapshots при каждом запуске.

    Для каждого (symbol, timeframe, mode) из universe:
    1. Вызвать FuturesAnalysisService.analyze_symbol()
    2. Получить scenarios + market_context
    3. Сохранить ForwardTestSnapshot (raw + normalized)
    4. Создать ForwardTestMonitorState (state=armed)
    """

    def __init__(self):
        self.config = get_config()
        self.futures_service = FuturesAnalysisService()
        self._version_hash: Optional[str] = None
        self._prompt_version = "v2.0.0"  # TODO: получать из конфига
        self._schema_version = 1

    async def generate_batch(self, session: AsyncSession) -> BatchResult:
        """
        Генерация полного batch сценариев.

        Returns:
            BatchResult с статистикой
        """
        batch_id = str(uuid.uuid4())
        batch_ts = datetime.now(UTC)
        errors: List[str] = []
        by_symbol: Dict[str, int] = {}

        version_hash = self._get_version_hash()

        universe = self.config.universe
        total_generated = 0

        for symbol in universe.symbols:
            for timeframe in universe.timeframes:
                for mode in universe.modes:
                    try:
                        count = await self._generate_for_scope(
                            session=session,
                            symbol=symbol,
                            timeframe=timeframe,
                            mode=mode,
                            batch_id=batch_id,
                            batch_ts=batch_ts,
                            version_hash=version_hash
                        )
                        by_symbol[symbol] = by_symbol.get(symbol, 0) + count
                        total_generated += count
                    except Exception as e:
                        error_msg = f"{symbol}/{timeframe}/{mode}: {e}"
                        logger.error(f"Snapshot generation failed: {error_msg}")
                        errors.append(error_msg)

        await session.commit()

        logger.info(
            f"Batch {batch_id[:8]} generated: "
            f"{total_generated} snapshots, {len(errors)} errors"
        )

        return BatchResult(
            batch_id=batch_id,
            batch_ts=batch_ts,
            total_generated=total_generated,
            by_symbol=by_symbol,
            errors=errors
        )

    async def _generate_for_scope(
        self,
        session: AsyncSession,
        symbol: str,
        timeframe: str,
        mode: str,
        batch_id: str,
        batch_ts: datetime,
        version_hash: str
    ) -> int:
        """
        Генерация для конкретного scope.

        Returns:
            Количество созданных snapshots
        """
        batch_scope = f"{symbol}:{timeframe}:{mode}"

        # Получить анализ от FuturesAnalysisService
        analysis = await self.futures_service.analyze_symbol(
            symbol=symbol,
            timeframe=timeframe,
            max_scenarios=3,
            mode=mode
        )

        if not analysis or "error" in analysis:
            logger.warning(f"No analysis for {batch_scope}: {analysis.get('error', 'unknown')}")
            return 0

        scenarios = analysis.get("scenarios", [])
        market_context = analysis.get("market_context", {})
        current_price = float(analysis.get("current_price", 0))

        # Get current epoch for new snapshots
        current_epoch = await get_current_epoch()

        count = 0
        for idx, scenario in enumerate(scenarios):
            try:
                snapshot_id = str(uuid.uuid4())

                # Извлечь ключевые данные
                bias_str = scenario.get("side", "").lower()
                if bias_str not in ("long", "short"):
                    # Попробовать альтернативные поля
                    bias_str = scenario.get("bias", "").lower()
                if bias_str not in ("long", "short"):
                    logger.warning(f"Invalid bias in scenario {idx}: {bias_str}")
                    continue

                bias = Bias.LONG if bias_str == "long" else Bias.SHORT

                # Entry план
                entry_plan = scenario.get("entry_plan", {})
                entry_orders = entry_plan.get("orders", [])
                if not entry_orders:
                    # Fallback на entry_zone
                    entry_low = float(scenario.get("entry_zone_low", 0))
                    entry_high = float(scenario.get("entry_zone_high", 0))
                    entry_avg = (entry_low + entry_high) / 2 if entry_low and entry_high else current_price
                else:
                    # Weighted average от orders
                    total_pct = sum(o.get("size_pct", 0) for o in entry_orders)
                    if total_pct > 0:
                        entry_avg = sum(
                            o.get("price", 0) * o.get("size_pct", 0)
                            for o in entry_orders
                        ) / total_pct
                    else:
                        entry_avg = current_price

                # Take profits (поле называется "targets" в scenario_generator)
                targets = scenario.get("targets", [])
                tp1_price = float(targets[0].get("price", 0)) if len(targets) > 0 else 0
                tp2_price = float(targets[1].get("price", 0)) if len(targets) > 1 else None
                tp3_price = float(targets[2].get("price", 0)) if len(targets) > 2 else None

                # stop_loss может быть dict или float
                stop_loss_data = scenario.get("stop_loss", 0)
                if isinstance(stop_loss_data, dict):
                    stop_loss = float(stop_loss_data.get("recommended", 0))
                else:
                    stop_loss = float(stop_loss_data) if stop_loss_data else 0.0

                # Confidence и EV
                confidence = float(scenario.get("confidence", 0.5))
                # EV может быть на верхнем уровне или внутри ev_metrics
                ev_r = scenario.get("ev_r")
                if ev_r is None:
                    ev_metrics = scenario.get("ev_metrics", {})
                    ev_r = ev_metrics.get("ev_r") if ev_metrics else None
                if ev_r is not None:
                    ev_r = float(ev_r)

                # Archetype
                archetype = scenario.get("archetype", "unknown")

                # Timing
                time_valid_hours = int(scenario.get("time_valid_hours", 24))
                expires_at = batch_ts + timedelta(hours=time_valid_hours)

                # BE логика
                be_after_tp1 = self.config.be_after_tp1_default
                be_price = entry_avg if be_after_tp1 else None

                # Создать snapshot
                snapshot = ForwardTestSnapshot(
                    snapshot_id=snapshot_id,
                    batch_id=batch_id,
                    batch_ts=batch_ts,
                    batch_scope=batch_scope,
                    symbol=symbol,
                    timeframe=timeframe,
                    mode=mode,
                    scenario_local_id=idx + 1,
                    bias=bias,
                    archetype=archetype,
                    raw_json=scenario,
                    normalized_json=self._normalize_scenario(scenario),
                    market_context_json=market_context,
                    version_hash=version_hash,
                    prompt_version=self._prompt_version,
                    schema_version=self._schema_version,
                    current_price=current_price,
                    entry_price_avg=entry_avg,
                    stop_loss=stop_loss,
                    tp1_price=tp1_price,
                    tp2_price=tp2_price,
                    tp3_price=tp3_price,
                    be_after_tp1=be_after_tp1,
                    be_price=be_price,
                    confidence=confidence,
                    ev_r=ev_r,
                    generated_at=batch_ts,
                    expires_at=expires_at,
                    time_valid_hours=time_valid_hours,
                    epoch=current_epoch,
                )
                session.add(snapshot)
                await session.flush()  # Гарантирует INSERT snapshot до monitor_state (FK)

                # Создать monitor state
                monitor_state = ForwardTestMonitorState(
                    snapshot_id=snapshot_id,
                    state=ScenarioState.ARMED,
                    state_updated_at=batch_ts,
                    bias_final=bias,
                    direction_sign=bias.direction_sign(),
                    fill_pct=0.0,
                    sl_moved_to_be=False,
                    fill_model=FillModel.TOUCH_FILL,
                    tp_progress=0,
                    realized_r_so_far=0.0,
                    remaining_position_pct=100.0,
                    entry_was_hit=False,  # FIX #15: явно False
                )
                session.add(monitor_state)

                # === PORTFOLIO MODE: добавить кандидата в пул ===
                if self.config.portfolio.enabled:
                    # FIX: Используем nested transaction для изоляции IntegrityError
                    # Savepoint автоматически rollback'ится при exception и commit'ится при успехе
                    try:
                        async with session.begin_nested():
                            candidate, status = await portfolio_manager.add_candidate_to_pool(
                                session=session,
                                snapshot=snapshot,
                                rank_in_batch=idx + 1,
                            )
                            logger.debug(
                                f"Portfolio candidate {candidate.candidate_id}: "
                                f"{symbol} {bias_str} → {status}"
                            )
                    except IntegrityError as e:
                        # Ожидаемая ситуация: дублирующийся кандидат для символа в батче
                        # Savepoint уже откатился автоматически, продолжаем обработку
                        logger.warning(
                            f"Duplicate candidate for {symbol} (scenario {idx}): "
                            f"likely multiple scenarios for same symbol in batch"
                        )
                    except Exception as e:
                        logger.error(f"Failed to add portfolio candidate: {e}")

                count += 1

            except Exception as e:
                logger.error(f"Failed to create snapshot for scenario {idx}: {e}")

        return count

    def _normalize_scenario(self, raw_scenario: Dict[str, Any]) -> Dict[str, Any]:
        """
        Нормализовать сценарий в единый формат.

        TODO: добавить полную нормализацию через ScenarioValidator
        """
        # Пока просто возвращаем как есть
        # В будущем можно добавить валидацию и нормализацию
        return raw_scenario

    def _get_version_hash(self) -> str:
        """Получить git commit hash для версионирования."""
        if self._version_hash:
            return self._version_hash

        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self._version_hash = result.stdout.strip()[:40]
            else:
                self._version_hash = "unknown"
        except Exception:
            self._version_hash = "unknown"

        return self._version_hash


# Singleton
snapshot_service = SnapshotService()
