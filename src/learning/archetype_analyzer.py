"""
Archetype Analyzer

Анализ статистики по архетипам сетапов.
Группировка по: archetype, symbol, timeframe, volatility_regime.
"""
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any
from collections import defaultdict

from loguru import logger
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

from src.database.models import (
    TradeOutcome,
    ArchetypeStats,
    TradeOutcomeLabel,
)


class ArchetypeAnalyzer:
    """
    Анализатор статистики по архетипам.

    Группирует сделки по:
    - archetype (primary_archetype)
    - symbol (опционально)
    - timeframe (опционально)
    - volatility_regime (опционально)

    Рассчитывает:
    - Winrate, profit factor
    - MAE/MFE percentiles
    - Оптимальные SL/TP
    """

    # Minimum trades for statistical significance
    MIN_TRADES_FOR_STATS = 10

    async def recalculate_stats(
        self,
        session: AsyncSession,
        include_testnet: bool = False
    ) -> Dict[str, Any]:
        """
        Пересчитать статистику по всем архетипам.

        Returns:
            Dict with recalculation stats
        """
        logger.info("Starting archetype stats recalculation")

        # Get all non-testnet trades
        conditions = []
        if not include_testnet:
            conditions.append(TradeOutcome.is_testnet == False)

        stmt = select(TradeOutcome)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        result = await session.execute(stmt)
        trades = list(result.scalars().all())

        if not trades:
            logger.warning("No trades found for archetype analysis")
            return {"groups_updated": 0}

        # Group trades
        groups = self._group_trades(trades)

        # Calculate stats for each group
        stats_records = []
        for key, group_trades in groups.items():
            if len(group_trades) < self.MIN_TRADES_FOR_STATS:
                continue

            archetype, side, symbol, timeframe, volatility = key
            stats = self._calculate_group_stats(group_trades)

            stats_records.append({
                "archetype": archetype,
                "side": side,
                "symbol": symbol,
                "timeframe": timeframe,
                "volatility_regime": volatility,
                **stats,
            })

        # Update database
        await self._upsert_stats(session, stats_records)

        logger.info(
            f"Archetype recalculation complete: "
            f"{len(stats_records)} groups updated"
        )

        return {
            "groups_updated": len(stats_records),
            "total_trades": len(trades),
        }

    async def get_archetype_ranking(
        self,
        session: AsyncSession,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        min_trades: int = 10,
    ) -> List[Dict]:
        """
        Получить рейтинг архетипов по profit factor.

        Returns:
            List of archetypes sorted by profit factor
        """
        conditions = [ArchetypeStats.total_trades >= min_trades]

        if symbol:
            conditions.append(ArchetypeStats.symbol == symbol)
        if timeframe:
            conditions.append(ArchetypeStats.timeframe == timeframe)

        stmt = select(ArchetypeStats).where(
            and_(*conditions)
        ).order_by(ArchetypeStats.profit_factor.desc())

        result = await session.execute(stmt)
        stats = list(result.scalars().all())

        return [
            {
                "rank": i + 1,
                "archetype": s.archetype,
                "symbol": s.symbol or "all",
                "timeframe": s.timeframe or "all",
                "volatility": s.volatility_regime or "all",
                "trades": s.total_trades,
                "winrate": f"{s.winrate:.1%}",
                "profit_factor": round(s.profit_factor, 2),
                "avg_pnl_r": round(s.avg_pnl_r, 2),
                "avg_mae_r": round(s.avg_mae_r, 2),
                "avg_mfe_r": round(s.avg_mfe_r, 2),
            }
            for i, s in enumerate(stats)
        ]

    async def get_archetype_suggestions(
        self,
        session: AsyncSession,
        archetype: str,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        volatility_regime: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Получить рекомендации по SL/TP для архетипа.

        Returns:
            Dict with suggested_sl_atr_mult, suggested_tp1_r, suggested_tp2_r
        """
        conditions = [ArchetypeStats.archetype == archetype]

        if symbol:
            conditions.append(ArchetypeStats.symbol == symbol)
        if timeframe:
            conditions.append(ArchetypeStats.timeframe == timeframe)
        if volatility_regime:
            conditions.append(ArchetypeStats.volatility_regime == volatility_regime)

        stmt = select(ArchetypeStats).where(and_(*conditions))
        result = await session.execute(stmt)
        stats = result.scalar_one_or_none()

        if not stats:
            return None

        return {
            "archetype": stats.archetype,
            "suggested_sl_atr_mult": stats.suggested_sl_atr_mult,
            "suggested_tp1_r": stats.suggested_tp1_r,
            "suggested_tp2_r": stats.suggested_tp2_r,
            "based_on_trades": stats.total_trades,
            "avg_mae_r": stats.avg_mae_r,
            "p90_mae_r": stats.p90_mae_r,
            "p50_mfe_r": stats.p50_mfe_r,
        }

    def _group_trades(
        self,
        trades: List[TradeOutcome]
    ) -> Dict[tuple, List[TradeOutcome]]:
        """Group trades by archetype, side, symbol, timeframe, volatility."""
        groups = defaultdict(list)

        for trade in trades:
            archetype = trade.primary_archetype or "unknown"
            side = trade.side.lower() if trade.side else "long"

            # Extract volatility from attribution_data
            volatility = None
            if trade.attribution_data:
                factors = trade.attribution_data.get("factors", {})
                volatility = factors.get("volatility_regime")

            # Create keys for different groupings (side теперь в ключе!)
            # 1. Global (archetype + side)
            groups[(archetype, side, None, None, None)].append(trade)

            # 2. By symbol
            groups[(archetype, side, trade.symbol, None, None)].append(trade)

            # 3. By timeframe
            groups[(archetype, side, None, trade.timeframe, None)].append(trade)

            # 4. By symbol + timeframe
            groups[(archetype, side, trade.symbol, trade.timeframe, None)].append(trade)

            # 5. By volatility
            if volatility:
                groups[(archetype, side, None, None, volatility)].append(trade)

            # 6. Full grouping
            if volatility:
                groups[(archetype, side, trade.symbol, trade.timeframe, volatility)].append(trade)

        return groups

    def _calculate_group_stats(
        self,
        trades: List[TradeOutcome]
    ) -> Dict[str, Any]:
        """Calculate statistics for a group of trades."""
        total = len(trades)
        wins = sum(1 for t in trades if t.label == TradeOutcomeLabel.WIN)
        losses = sum(1 for t in trades if t.label == TradeOutcomeLabel.LOSS)

        # Winrate
        winrate = wins / total if total > 0 else 0

        # PnL metrics
        pnl_values = [t.pnl_r or 0 for t in trades]
        avg_pnl_r = np.mean(pnl_values) if pnl_values else 0

        # Profit factor
        gross_profit = sum(p for p in pnl_values if p > 0)
        gross_loss = abs(sum(p for p in pnl_values if p < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Terminal outcome counts (для EV)
        exit_sl_count = sum(1 for t in trades if t.terminal_outcome == "sl")
        exit_tp1_count = sum(1 for t in trades if t.terminal_outcome == "tp1")
        exit_tp2_count = sum(1 for t in trades if t.terminal_outcome == "tp2")
        exit_tp3_count = sum(1 for t in trades if t.terminal_outcome == "tp3")
        exit_other_count = sum(1 for t in trades if t.terminal_outcome == "other")

        # avg_pnl_r_other для payout_other
        other_trades = [t for t in trades if t.terminal_outcome == "other"]
        other_pnl_values = [t.pnl_r or 0 for t in other_trades]
        avg_pnl_r_other = np.mean(other_pnl_values) if other_pnl_values else 0

        # MAE metrics
        mae_values = [t.mae_r or 0 for t in trades if t.mae_r is not None]
        avg_mae_r = np.mean(mae_values) if mae_values else 0
        p75_mae_r = np.percentile(mae_values, 75) if mae_values else 0
        p90_mae_r = np.percentile(mae_values, 90) if mae_values else 0

        # MFE metrics
        mfe_values = [t.mfe_r or 0 for t in trades if t.mfe_r is not None]
        avg_mfe_r = np.mean(mfe_values) if mfe_values else 0
        p50_mfe_r = np.percentile(mfe_values, 50) if mfe_values else 0

        # SL/TP suggestions based on MAE/MFE
        # SL: P90 MAE + small buffer (to avoid premature stops)
        suggested_sl_atr_mult = max(1.0, p90_mae_r * 1.1) if p90_mae_r > 0 else 1.0

        # TP1: Median MFE (50% of trades reach this)
        suggested_tp1_r = max(1.0, p50_mfe_r * 0.8) if p50_mfe_r > 0 else 1.5

        # TP2: Average MFE (for winning trades)
        winning_mfe = [t.mfe_r or 0 for t in trades if t.label == TradeOutcomeLabel.WIN and t.mfe_r]
        suggested_tp2_r = np.mean(winning_mfe) if winning_mfe else suggested_tp1_r * 1.5

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "winrate": winrate,
            "avg_pnl_r": avg_pnl_r,
            "profit_factor": profit_factor,
            # Terminal outcome counts
            "exit_sl_count": exit_sl_count,
            "exit_tp1_count": exit_tp1_count,
            "exit_tp2_count": exit_tp2_count,
            "exit_tp3_count": exit_tp3_count,
            "exit_other_count": exit_other_count,
            "avg_pnl_r_other": avg_pnl_r_other,
            # MAE/MFE
            "avg_mae_r": avg_mae_r,
            "avg_mfe_r": avg_mfe_r,
            "p75_mae_r": p75_mae_r,
            "p90_mae_r": p90_mae_r,
            "p50_mfe_r": p50_mfe_r,
            "suggested_sl_atr_mult": suggested_sl_atr_mult,
            "suggested_tp1_r": suggested_tp1_r,
            "suggested_tp2_r": suggested_tp2_r,
            "last_calculated_at": datetime.now(UTC),
        }

    async def _upsert_stats(
        self,
        session: AsyncSession,
        stats_records: List[Dict]
    ):
        """Upsert archetype stats records."""
        for record in stats_records:
            # Try to find existing (включая side!)
            stmt = select(ArchetypeStats).where(
                and_(
                    ArchetypeStats.archetype == record["archetype"],
                    ArchetypeStats.side == record.get("side"),
                    ArchetypeStats.symbol == record.get("symbol"),
                    ArchetypeStats.timeframe == record.get("timeframe"),
                    ArchetypeStats.volatility_regime == record.get("volatility_regime"),
                )
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update
                for key, value in record.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                # Create new
                new_stats = ArchetypeStats(**record)
                session.add(new_stats)

        await session.commit()


# Singleton instance
archetype_analyzer = ArchetypeAnalyzer()
