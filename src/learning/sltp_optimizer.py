"""
SL/TP Optimizer

Оптимизация Stop Loss и Take Profit на основе MAE/MFE анализа.
Группирует данные по архетипу, символу, таймфрейму и волатильности.
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ArchetypeStats


@dataclass
class SLTPSuggestion:
    """Рекомендации по SL/TP."""
    sl_atr_mult: float
    tp1_r: float
    tp2_r: float
    tp3_r: Optional[float] = None

    confidence: float = 0.5  # How confident we are in these suggestions
    based_on_trades: int = 0
    archetype: Optional[str] = None


class SLTPOptimizer:
    """
    Оптимизатор SL/TP на основе исторических данных.

    Использует MAE/MFE percentiles для расчёта оптимальных уровней:
    - SL: P90 MAE + buffer (чтобы избежать преждевременных стопов)
    - TP1: P50 MFE * 0.8 (консервативная первая цель)
    - TP2: Avg MFE winning trades
    - TP3: P75 MFE winning trades (амбициозная цель)
    """

    # Default values when insufficient data
    DEFAULT_SL_ATR_MULT = 1.5
    DEFAULT_TP1_R = 1.5
    DEFAULT_TP2_R = 2.5
    DEFAULT_TP3_R = 4.0

    # Minimum trades for reliable suggestions
    MIN_TRADES = 15

    async def get_suggestions(
        self,
        session: AsyncSession,
        archetype: str,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        volatility_regime: Optional[str] = None,
    ) -> SLTPSuggestion:
        """
        Получить оптимальные SL/TP для заданных условий.

        Ищет наиболее специфичную группу с достаточным количеством данных.

        Args:
            session: DB session
            archetype: Trade archetype
            symbol: Trading pair
            timeframe: Timeframe
            volatility_regime: low/normal/high

        Returns:
            SLTPSuggestion with optimized values
        """
        # Try progressively less specific queries
        search_configs = [
            # Most specific first
            {"archetype": archetype, "symbol": symbol, "timeframe": timeframe, "volatility_regime": volatility_regime},
            {"archetype": archetype, "symbol": symbol, "timeframe": timeframe, "volatility_regime": None},
            {"archetype": archetype, "symbol": symbol, "timeframe": None, "volatility_regime": None},
            {"archetype": archetype, "symbol": None, "timeframe": timeframe, "volatility_regime": None},
            {"archetype": archetype, "symbol": None, "timeframe": None, "volatility_regime": None},
        ]

        for config in search_configs:
            stats = await self._find_stats(session, **config)

            if stats and stats.total_trades >= self.MIN_TRADES:
                # Calculate confidence based on sample size
                confidence = min(0.95, 0.5 + (stats.total_trades - self.MIN_TRADES) * 0.01)

                return SLTPSuggestion(
                    sl_atr_mult=stats.suggested_sl_atr_mult,
                    tp1_r=stats.suggested_tp1_r,
                    tp2_r=stats.suggested_tp2_r,
                    tp3_r=stats.suggested_tp2_r * 1.5,  # Derive TP3 from TP2
                    confidence=confidence,
                    based_on_trades=stats.total_trades,
                    archetype=archetype,
                )

        # No sufficient data found - return defaults
        logger.debug(f"No stats found for {archetype}, using defaults")
        return SLTPSuggestion(
            sl_atr_mult=self.DEFAULT_SL_ATR_MULT,
            tp1_r=self.DEFAULT_TP1_R,
            tp2_r=self.DEFAULT_TP2_R,
            tp3_r=self.DEFAULT_TP3_R,
            confidence=0.3,
            based_on_trades=0,
            archetype=archetype,
        )

    async def get_all_suggestions(
        self,
        session: AsyncSession,
        min_trades: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Получить все SL/TP рекомендации.

        Returns:
            List of suggestions for all archetypes with sufficient data
        """
        stmt = select(ArchetypeStats).where(
            and_(
                ArchetypeStats.total_trades >= min_trades,
                ArchetypeStats.symbol == None,  # Global stats only
                ArchetypeStats.timeframe == None,
            )
        ).order_by(ArchetypeStats.profit_factor.desc())

        result = await session.execute(stmt)
        all_stats = list(result.scalars().all())

        suggestions = []
        for stats in all_stats:
            suggestions.append({
                "archetype": stats.archetype,
                "trades": stats.total_trades,
                "winrate": f"{stats.winrate:.1%}",
                "profit_factor": round(stats.profit_factor, 2),
                "suggested_sl": {
                    "atr_mult": round(stats.suggested_sl_atr_mult, 2),
                    "based_on": f"P90 MAE = {stats.p90_mae_r:.2f}R",
                },
                "suggested_tp1": {
                    "r_multiple": round(stats.suggested_tp1_r, 2),
                    "based_on": f"P50 MFE = {stats.p50_mfe_r:.2f}R",
                },
                "suggested_tp2": {
                    "r_multiple": round(stats.suggested_tp2_r, 2),
                    "based_on": f"Avg winning MFE",
                },
                "mae_mfe_analysis": {
                    "avg_mae_r": round(stats.avg_mae_r, 2),
                    "p75_mae_r": round(stats.p75_mae_r, 2),
                    "p90_mae_r": round(stats.p90_mae_r, 2),
                    "avg_mfe_r": round(stats.avg_mfe_r, 2),
                    "p50_mfe_r": round(stats.p50_mfe_r, 2),
                },
            })

        return suggestions

    async def compare_current_vs_optimal(
        self,
        session: AsyncSession,
        archetype: str,
        current_sl_r: float,
        current_tp_r: float,
    ) -> Dict[str, Any]:
        """
        Сравнить текущие SL/TP с оптимальными.

        Args:
            archetype: Trade archetype
            current_sl_r: Current SL in R
            current_tp_r: Current TP in R

        Returns:
            Dict with comparison and recommendations
        """
        suggestion = await self.get_suggestions(session, archetype)

        sl_diff = current_sl_r - suggestion.sl_atr_mult
        tp_diff = current_tp_r - suggestion.tp1_r

        analysis = {
            "current": {
                "sl_r": current_sl_r,
                "tp_r": current_tp_r,
            },
            "suggested": {
                "sl_atr_mult": suggestion.sl_atr_mult,
                "tp1_r": suggestion.tp1_r,
                "tp2_r": suggestion.tp2_r,
            },
            "differences": {
                "sl_diff": round(sl_diff, 2),
                "tp_diff": round(tp_diff, 2),
            },
            "recommendations": [],
            "confidence": suggestion.confidence,
            "based_on_trades": suggestion.based_on_trades,
        }

        # Generate recommendations
        if sl_diff < -0.3:
            analysis["recommendations"].append(
                f"SL is too tight. Consider widening to {suggestion.sl_atr_mult:.1f}x ATR "
                f"to reduce premature stops."
            )
        elif sl_diff > 0.5:
            analysis["recommendations"].append(
                f"SL is too wide. Consider tightening to {suggestion.sl_atr_mult:.1f}x ATR "
                f"to reduce losses."
            )

        if tp_diff < -0.5:
            analysis["recommendations"].append(
                f"TP target is conservative. Historical data shows P50 MFE of "
                f"{suggestion.tp1_r:.1f}R is achievable."
            )
        elif tp_diff > 1.0:
            analysis["recommendations"].append(
                f"TP target may be too ambitious. Consider {suggestion.tp1_r:.1f}R "
                f"as first target."
            )

        if not analysis["recommendations"]:
            analysis["recommendations"].append("Current SL/TP settings are well-calibrated.")

        return analysis

    async def _find_stats(
        self,
        session: AsyncSession,
        archetype: str,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        volatility_regime: Optional[str] = None,
    ) -> Optional[ArchetypeStats]:
        """Find archetype stats for given criteria."""
        stmt = select(ArchetypeStats).where(
            and_(
                ArchetypeStats.archetype == archetype,
                ArchetypeStats.symbol == symbol,
                ArchetypeStats.timeframe == timeframe,
                ArchetypeStats.volatility_regime == volatility_regime,
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


# Singleton instance
sltp_optimizer = SLTPOptimizer()
