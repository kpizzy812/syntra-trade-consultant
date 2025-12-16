"""
Confidence Calibrator

Калибровка AI confidence на основе реальных результатов.
Использует bucket-based подход с Laplace smoothing.

Формулы:
- raw_winrate = wins / total
- smoothed_winrate = (wins + 1) / (total + 2)  # Laplace smoothing
- calibration_offset = smoothed_winrate - bucket_midpoint
- calibrated_confidence = raw + offset (clamped to 0.05-0.95)
"""
from datetime import datetime, UTC
from typing import Optional, List, Dict

from loguru import logger
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    TradeOutcome,
    ConfidenceBucket,
    TradeOutcomeLabel,
)


class ConfidenceCalibrator:
    """
    Калибратор confidence на основе bucket статистики.

    Buckets:
    - very_low: 0.00 - 0.40
    - low: 0.40 - 0.55
    - medium: 0.55 - 0.70
    - high: 0.70 - 0.85
    - very_high: 0.85 - 1.01
    """

    # Minimum sample size for calibration
    MIN_SAMPLE_SIZE = 20

    # Clamp bounds
    MIN_CONFIDENCE = 0.05
    MAX_CONFIDENCE = 0.95

    async def calibrate(
        self,
        session: AsyncSession,
        raw_confidence: float,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> float:
        """
        Калибровать raw confidence.

        Args:
            session: DB session
            raw_confidence: Original AI confidence (0-1)
            symbol: Optional symbol filter
            timeframe: Optional timeframe filter

        Returns:
            Calibrated confidence (clamped to 0.05-0.95)
        """
        # Find the bucket
        bucket = await self._get_bucket(session, raw_confidence)

        if not bucket or bucket.sample_size < self.MIN_SAMPLE_SIZE:
            # Insufficient data - return raw
            return raw_confidence

        # Apply offset
        calibrated = raw_confidence + bucket.calibration_offset

        # Clamp
        calibrated = max(self.MIN_CONFIDENCE, min(self.MAX_CONFIDENCE, calibrated))

        logger.debug(
            f"Confidence calibrated: {raw_confidence:.2f} -> {calibrated:.2f} "
            f"(offset={bucket.calibration_offset:.2f}, bucket={bucket.bucket_name})"
        )

        return calibrated

    async def recalculate_buckets(
        self,
        session: AsyncSession,
        include_testnet: bool = False
    ) -> Dict[str, any]:
        """
        Пересчитать все confidence buckets.

        Args:
            session: DB session
            include_testnet: Include testnet trades

        Returns:
            Dict with recalculation stats
        """
        logger.info("Starting confidence bucket recalculation")

        # Get all buckets
        stmt = select(ConfidenceBucket).order_by(ConfidenceBucket.confidence_min)
        result = await session.execute(stmt)
        buckets = list(result.scalars().all())

        stats = {
            "buckets_updated": 0,
            "total_trades_processed": 0,
        }

        for bucket in buckets:
            # Get trades in this bucket
            conditions = [
                TradeOutcome.confidence_raw >= bucket.confidence_min,
                TradeOutcome.confidence_raw < bucket.confidence_max,
            ]

            if not include_testnet:
                conditions.append(TradeOutcome.is_testnet == False)

            stmt = select(TradeOutcome).where(and_(*conditions))
            result = await session.execute(stmt)
            trades = list(result.scalars().all())

            total = len(trades)
            wins = sum(1 for t in trades if t.label == TradeOutcomeLabel.WIN)
            losses = sum(1 for t in trades if t.label == TradeOutcomeLabel.LOSS)
            breakevens = total - wins - losses

            # Calculate winrates
            raw_winrate = wins / total if total > 0 else 0.5
            smoothed_winrate = (wins + 1) / (total + 2)  # Laplace smoothing

            # Bucket midpoint
            midpoint = (bucket.confidence_min + bucket.confidence_max) / 2

            # Calibration offset
            calibration_offset = smoothed_winrate - midpoint

            # Calculate average metrics
            avg_pnl_r = sum(t.pnl_r or 0 for t in trades) / total if total > 0 else 0
            avg_mae_r = sum(t.mae_r or 0 for t in trades) / total if total > 0 else 0
            avg_mfe_r = sum(t.mfe_r or 0 for t in trades) / total if total > 0 else 0

            # Update bucket
            bucket.total_trades = total
            bucket.wins = wins
            bucket.losses = losses
            bucket.breakevens = breakevens
            bucket.actual_winrate_raw = raw_winrate
            bucket.actual_winrate_smoothed = smoothed_winrate
            bucket.avg_pnl_r = avg_pnl_r
            bucket.avg_mae_r = avg_mae_r
            bucket.avg_mfe_r = avg_mfe_r
            bucket.calibration_offset = calibration_offset
            bucket.sample_size = total
            bucket.last_calculated_at = datetime.now(UTC)

            stats["buckets_updated"] += 1
            stats["total_trades_processed"] += total

            logger.debug(
                f"Bucket {bucket.bucket_name}: total={total}, "
                f"winrate={smoothed_winrate:.2%}, offset={calibration_offset:.3f}"
            )

        await session.commit()

        logger.info(
            f"Confidence recalculation complete: "
            f"{stats['buckets_updated']} buckets, "
            f"{stats['total_trades_processed']} trades"
        )

        return stats

    async def get_calibration_report(
        self,
        session: AsyncSession
    ) -> List[Dict]:
        """
        Получить отчёт по калибровке.

        Returns:
            List of bucket stats with calibration info
        """
        stmt = select(ConfidenceBucket).order_by(ConfidenceBucket.confidence_min)
        result = await session.execute(stmt)
        buckets = list(result.scalars().all())

        report = []
        for b in buckets:
            midpoint = (b.confidence_min + b.confidence_max) / 2

            report.append({
                "bucket": b.bucket_name,
                "range": f"{b.confidence_min:.0%}-{b.confidence_max:.0%}",
                "midpoint": f"{midpoint:.0%}",
                "total_trades": b.total_trades,
                "wins": b.wins,
                "losses": b.losses,
                "raw_winrate": f"{b.actual_winrate_raw:.1%}" if b.total_trades > 0 else "N/A",
                "smoothed_winrate": f"{b.actual_winrate_smoothed:.1%}",
                "calibration_offset": f"{b.calibration_offset:+.2f}",
                "calibration_status": self._get_calibration_status(b),
            })

        return report

    async def _get_bucket(
        self,
        session: AsyncSession,
        confidence: float
    ) -> Optional[ConfidenceBucket]:
        """Get bucket for a given confidence value."""
        stmt = select(ConfidenceBucket).where(
            and_(
                ConfidenceBucket.confidence_min <= confidence,
                ConfidenceBucket.confidence_max > confidence
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    def _get_calibration_status(self, bucket: ConfidenceBucket) -> str:
        """Get human-readable calibration status."""
        if bucket.sample_size < self.MIN_SAMPLE_SIZE:
            return "insufficient_data"

        offset = abs(bucket.calibration_offset)
        if offset < 0.05:
            return "well_calibrated"
        elif offset < 0.10:
            return "slightly_off"
        elif offset < 0.20:
            return "needs_adjustment"
        else:
            return "significantly_off"


# Singleton instance
confidence_calibrator = ConfidenceCalibrator()
