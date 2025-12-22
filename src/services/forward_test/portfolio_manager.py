"""
Portfolio Manager для Forward Test

Управление пулом кандидатов с:
- Scoring (EV-weighted)
- Anti-duplication
- Replacement логикой
- Фильтрами

FIX #1-#28 применены.
"""
from datetime import datetime, timedelta, UTC
from typing import Tuple, Optional, List

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.forward_test.config import get_config, PortfolioConfig
from src.services.forward_test.models import (
    ForwardTestSnapshot,
    PortfolioCandidate,
    PortfolioPosition,
    ForwardTestAnomaly,
)


# Reject reasons по категориям
REQUIRES_REPLACEMENT_REASONS = frozenset({
    "pool_full",
    "replaced_by_better",
    "replaced_by_better_same_symbol",
    "replaced_by_better_symbol",
})


class PortfolioManager:
    """
    Управление candidate pool и scoring.

    Responsibilities:
    - Scoring кандидатов (EV-weighted)
    - Anti-duplication (candidates + positions)
    - Replacement worst by score
    - Фильтры (min_ev, min_confidence)
    """

    def __init__(self):
        self.config: PortfolioConfig = get_config().portfolio

    def compute_score(self, snapshot: ForwardTestSnapshot) -> Tuple[float, float, float, float]:
        """
        Вычислить priority score для кандидата.

        Returns:
            (priority_score, ev_component, conf_component, quality_component)
        """
        ev = snapshot.ev_r or 0.0
        confidence = snapshot.confidence or 0.0
        # Quality placeholder — в v2 будет invalidation_distance
        quality = 1.0

        ev_comp = ev * self.config.ev_weight
        conf_comp = confidence * self.config.confidence_weight
        quality_comp = quality * self.config.quality_weight

        priority_score = ev_comp + conf_comp + quality_comp

        return priority_score, ev_comp, conf_comp, quality_comp

    async def add_candidate_to_pool(
        self,
        session: AsyncSession,
        snapshot: ForwardTestSnapshot,
        rank_in_batch: int,
    ) -> Tuple[PortfolioCandidate, str]:
        """
        Добавить кандидата в пул.

        Returns:
            (candidate, status) где status:
            - "active" — успешно добавлен
            - "rejected" — отклонён (фильтры/дубликат)
            - "replaced_*" — заменил худшего

        FIX #1: flush() ПЕРЕД присвоением replaced_by_candidate_id
        FIX #6: Проверяем max_per_symbol И max_per_symbol_side
        FIX #12+#21: Replacement для active candidates по symbol
        FIX #23: FOR UPDATE на replacement target
        """
        if not self.config.enabled:
            candidate = self._create_rejected(snapshot, rank_in_batch, "portfolio_disabled")
            session.add(candidate)
            return candidate, "rejected"

        # Calculate score
        priority_score, ev_comp, conf_comp, quality_comp = self.compute_score(snapshot)

        # === ФИЛЬТРЫ ===
        if (snapshot.ev_r or 0) < self.config.min_ev_r:
            candidate = self._create_rejected(snapshot, rank_in_batch, "low_ev")
            session.add(candidate)
            return candidate, "rejected"

        if (snapshot.confidence or 0) < self.config.min_confidence:
            candidate = self._create_rejected(snapshot, rank_in_batch, "low_conf")
            session.add(candidate)
            return candidate, "rejected"

        symbol, side = snapshot.symbol, snapshot.bias

        # === ANTI-DUP: Open Positions ===

        # Check 1: max_per_symbol (любой side) — open positions
        symbol_pos_count = await session.scalar(
            select(func.count()).select_from(PortfolioPosition).where(
                PortfolioPosition.symbol == symbol,
                PortfolioPosition.status == "open"
            )
        )
        if symbol_pos_count >= self.config.max_per_symbol:
            candidate = self._create_rejected(snapshot, rank_in_batch, "duplicate_symbol_any_side")
            session.add(candidate)
            return candidate, "rejected"

        # Check 2: max_per_symbol_side — open positions
        symbol_side_pos_count = await session.scalar(
            select(func.count()).select_from(PortfolioPosition).where(
                PortfolioPosition.symbol == symbol,
                PortfolioPosition.side == side,
                PortfolioPosition.status == "open"
            )
        )
        if symbol_side_pos_count >= self.config.max_per_symbol_side:
            candidate = self._create_rejected(snapshot, rank_in_batch, "duplicate_open_position")
            session.add(candidate)
            return candidate, "rejected"

        # === ANTI-DUP: Active Candidates ===

        # FIX #12+#21+#23: Check 3 — max_per_symbol для active candidates
        active_symbol_count = await session.scalar(
            select(func.count()).select_from(PortfolioCandidate).where(
                PortfolioCandidate.symbol == symbol,
                PortfolioCandidate.status.in_(["active", "active_waiting_slot"])
            )
        )
        if active_symbol_count >= self.config.max_per_symbol:
            # FIX #23: FOR UPDATE на worst чтобы race не сломал replacement
            existing_symbol_result = await session.execute(
                select(PortfolioCandidate)
                .where(
                    PortfolioCandidate.symbol == symbol,
                    PortfolioCandidate.status.in_(["active", "active_waiting_slot"])
                )
                .order_by(PortfolioCandidate.priority_score.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            worst_symbol = existing_symbol_result.scalar_one_or_none()

            if worst_symbol and priority_score > worst_symbol.priority_score:
                # FIX #21: СРАЗУ делаем replacement
                new_candidate = self._create_active(
                    snapshot, rank_in_batch, priority_score, ev_comp, conf_comp, quality_comp
                )
                session.add(new_candidate)
                # FIX #1: flush() ПЕРЕД присвоением ID
                await session.flush()

                worst_symbol.status = "rejected"
                worst_symbol.reject_reason = "replaced_by_better_symbol"
                worst_symbol.replaced_by_candidate_id = new_candidate.candidate_id

                logger.debug(
                    f"Portfolio: replaced {worst_symbol.candidate_id} "
                    f"(score={worst_symbol.priority_score:.2f}) "
                    f"with {new_candidate.candidate_id} (score={priority_score:.2f}) on {symbol}"
                )
                return new_candidate, "replaced_symbol"
            else:
                candidate = self._create_rejected(snapshot, rank_in_batch, "duplicate_candidate_symbol")
                session.add(candidate)
                return candidate, "rejected"

        # Check 4: active candidates по (symbol, side)
        active_dup_result = await session.execute(
            select(PortfolioCandidate)
            .where(
                PortfolioCandidate.symbol == symbol,
                PortfolioCandidate.side == side,
                PortfolioCandidate.status.in_(["active", "active_waiting_slot"])
            )
            .order_by(PortfolioCandidate.priority_score.desc())
            .limit(1)
        )
        existing_dup = active_dup_result.scalar_one_or_none()

        if existing_dup:
            if priority_score > existing_dup.priority_score:
                new_candidate = self._create_active(
                    snapshot, rank_in_batch, priority_score, ev_comp, conf_comp, quality_comp
                )
                session.add(new_candidate)
                # FIX #1: flush() ПЕРЕД присвоением
                await session.flush()

                existing_dup.status = "rejected"
                existing_dup.reject_reason = "replaced_by_better_same_symbol"
                existing_dup.replaced_by_candidate_id = new_candidate.candidate_id

                logger.debug(
                    f"Portfolio: replaced {existing_dup.candidate_id} with {new_candidate.candidate_id} "
                    f"on {symbol}/{side}"
                )
                return new_candidate, "replaced_same_symbol"
            else:
                candidate = self._create_rejected(snapshot, rank_in_batch, "duplicate_candidate_worse")
                session.add(candidate)
                return candidate, "rejected"

        # === POOL SIZE CHECK ===
        active_count = await session.scalar(
            select(func.count()).select_from(PortfolioCandidate).where(
                PortfolioCandidate.status.in_(["active", "active_waiting_slot"])
            )
        )

        if active_count < self.config.max_active_candidates:
            new_candidate = self._create_active(
                snapshot, rank_in_batch, priority_score, ev_comp, conf_comp, quality_comp
            )
            session.add(new_candidate)
            return new_candidate, "active"

        # === POOL FULL: Try replace worst ===
        worst_result = await session.execute(
            select(PortfolioCandidate)
            .where(PortfolioCandidate.status.in_(["active", "active_waiting_slot"]))
            .order_by(PortfolioCandidate.priority_score.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        worst_candidate = worst_result.scalar_one_or_none()

        if worst_candidate and priority_score > worst_candidate.priority_score:
            new_candidate = self._create_active(
                snapshot, rank_in_batch, priority_score, ev_comp, conf_comp, quality_comp
            )
            session.add(new_candidate)
            # FIX #1: flush() ПЕРЕД присвоением
            await session.flush()

            worst_candidate.status = "rejected"
            worst_candidate.reject_reason = "replaced_by_better"
            worst_candidate.replaced_by_candidate_id = new_candidate.candidate_id

            logger.debug(
                f"Portfolio: replaced worst {worst_candidate.candidate_id} "
                f"(score={worst_candidate.priority_score:.2f}) with {new_candidate.candidate_id}"
            )
            return new_candidate, "replaced_worst"
        else:
            candidate = self._create_rejected(snapshot, rank_in_batch, "pool_full")
            session.add(candidate)
            return candidate, "rejected"

    def _create_active(
        self,
        snapshot: ForwardTestSnapshot,
        rank_in_batch: int,
        priority_score: float,
        ev_comp: float,
        conf_comp: float,
        quality_comp: float,
    ) -> PortfolioCandidate:
        """Создать активного кандидата."""
        # FIX #17: planned_risk_r = base_risk при создании
        base_risk = self.config.max_total_risk_r / self.config.max_open_positions

        # Extract entry zone from normalized_json
        entry_zone = snapshot.normalized_json.get("entry_zone", {})
        entry_prices = entry_zone.get("prices", [snapshot.entry_price_avg])
        entry_min = min(entry_prices) if entry_prices else snapshot.entry_price_avg
        entry_max = max(entry_prices) if entry_prices else snapshot.entry_price_avg

        return PortfolioCandidate(
            snapshot_id=snapshot.snapshot_id,
            symbol=snapshot.symbol,
            side=snapshot.bias,
            timeframe=snapshot.timeframe,
            archetype=snapshot.archetype,
            entry_min=entry_min,
            entry_max=entry_max,
            batch_id=snapshot.batch_id,
            expires_at=datetime.now(UTC) + timedelta(hours=self.config.candidate_ttl_hours),
            priority_score=priority_score,
            ev_component=ev_comp,
            conf_component=conf_comp,
            quality_component=quality_comp,
            rank_in_batch=rank_in_batch,
            planned_risk_r=base_risk,
            status="active",
        )

    def _create_rejected(
        self,
        snapshot: ForwardTestSnapshot,
        rank_in_batch: int,
        reject_reason: str,
    ) -> PortfolioCandidate:
        """Создать отклонённого кандидата (для tracking)."""
        priority_score, ev_comp, conf_comp, quality_comp = self.compute_score(snapshot)
        base_risk = self.config.max_total_risk_r / self.config.max_open_positions

        # Extract entry zone
        entry_zone = snapshot.normalized_json.get("entry_zone", {})
        entry_prices = entry_zone.get("prices", [snapshot.entry_price_avg])
        entry_min = min(entry_prices) if entry_prices else snapshot.entry_price_avg
        entry_max = max(entry_prices) if entry_prices else snapshot.entry_price_avg

        return PortfolioCandidate(
            snapshot_id=snapshot.snapshot_id,
            symbol=snapshot.symbol,
            side=snapshot.bias,
            timeframe=snapshot.timeframe,
            archetype=snapshot.archetype,
            entry_min=entry_min,
            entry_max=entry_max,
            batch_id=snapshot.batch_id,
            expires_at=datetime.now(UTC) + timedelta(hours=self.config.candidate_ttl_hours),
            priority_score=priority_score,
            ev_component=ev_comp,
            conf_component=conf_comp,
            quality_component=quality_comp,
            rank_in_batch=rank_in_batch,
            planned_risk_r=base_risk,
            status="rejected",
            reject_reason=reject_reason,
            # FIX #18: Ставим флаг requires_replacement сразу
            counterfactual_requires_replacement=reject_reason in REQUIRES_REPLACEMENT_REASONS,
        )

    async def expire_stale_candidates(self, session: AsyncSession) -> int:
        """
        Пометить просроченных кандидатов как expired.

        Returns:
            Количество expired кандидатов
        """
        now = datetime.now(UTC)

        result = await session.execute(
            select(PortfolioCandidate).where(
                PortfolioCandidate.status.in_(["active", "active_waiting_slot"]),
                PortfolioCandidate.expires_at < now
            )
        )
        expired_candidates = result.scalars().all()

        for candidate in expired_candidates:
            candidate.status = "expired"

        if expired_candidates:
            logger.info(f"Portfolio: expired {len(expired_candidates)} candidates")

        return len(expired_candidates)

    async def get_pool_stats(self, session: AsyncSession) -> dict:
        """Получить статистику пула."""
        active_count = await session.scalar(
            select(func.count()).select_from(PortfolioCandidate).where(
                PortfolioCandidate.status == "active"
            )
        ) or 0

        waiting_count = await session.scalar(
            select(func.count()).select_from(PortfolioCandidate).where(
                PortfolioCandidate.status == "active_waiting_slot"
            )
        ) or 0

        open_positions = await session.scalar(
            select(func.count()).select_from(PortfolioPosition).where(
                PortfolioPosition.status == "open"
            )
        ) or 0

        # Total risk
        total_risk_result = await session.execute(
            select(func.sum(PortfolioPosition.risk_r_filled)).where(
                PortfolioPosition.status == "open"
            )
        )
        total_risk = total_risk_result.scalar() or 0.0

        return {
            "active_candidates": active_count,
            "waiting_slot_candidates": waiting_count,
            "open_positions": open_positions,
            "total_risk_r": total_risk,
            "max_candidates": self.config.max_active_candidates,
            "max_positions": self.config.max_open_positions,
            "max_risk_r": self.config.max_total_risk_r,
            "risk_utilization_pct": (total_risk / self.config.max_total_risk_r * 100)
            if self.config.max_total_risk_r > 0 else 0,
        }


async def log_data_anomaly(
    session: AsyncSession,
    bug_type: str,
    snapshot_id: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    """
    Логируем аномалию в таблицу (FIX #28).

    Алерт каждые 10 записей за последний час.
    """
    anomaly = ForwardTestAnomaly(
        bug_type=bug_type,
        snapshot_id=snapshot_id,
        details=details,
    )
    session.add(anomaly)

    # Считаем за последний час
    hour_ago = datetime.now(UTC) - timedelta(hours=1)
    count = await session.scalar(
        select(func.count()).select_from(ForwardTestAnomaly).where(
            ForwardTestAnomaly.bug_type == bug_type,
            ForwardTestAnomaly.ts > hour_ago
        )
    )
    if count and count % 10 == 0:
        logger.error(f"DATA_BUG_ALERT: {bug_type} count={count}/hour")


# Singleton
portfolio_manager = PortfolioManager()
