# coding: utf-8
"""
Level Calculator - расчёт ключевых уровней S/R, EMA, VWAP, BB.
"""
from typing import Any, Dict

import pandas as pd
from loguru import logger

from src.services.price_levels_service import PriceLevelsService


class LevelCalculator:
    """
    Расчёт ключевых технических уровней для сценариев.
    """

    def __init__(self):
        self.price_levels = PriceLevelsService()

    async def calculate(
        self,
        symbol: str,
        current_price: float,
        klines: pd.DataFrame,
        indicators: Dict
    ) -> Dict[str, Any]:
        """
        Рассчитать ключевые уровни для сценариев.

        Returns:
            {
                "support": [price1, price2, price3],
                "resistance": [price1, price2, price3],
                "ema_levels": {...},
                "vwap": price,
                "bollinger_bands": {...}
            }
        """
        levels = {}

        # Support/Resistance from OHLC
        ohlc_data = klines[['high', 'low', 'close', 'volume']].to_dict('records')
        sr_data = self.price_levels.calculate_support_resistance_from_ohlc(
            ohlc_data=ohlc_data,
            current_price=current_price,
            lookback_periods=90
        )

        if sr_data.get("success"):
            levels["support"] = sr_data.get("support_levels", [])[:3]
            levels["resistance"] = sr_data.get("resistance_levels", [])[:3]
        else:
            levels["support"] = []
            levels["resistance"] = []

        # EMA levels
        ema_levels = {}
        for ema_type in ["ema_20", "ema_50", "ema_200"]:
            ema_value = indicators.get(ema_type)
            if ema_value:
                ema_levels[ema_type] = {
                    "price": round(ema_value, 2),
                    "distance_pct": round(((current_price - ema_value) / current_price) * 100, 2)
                }
        levels["ema_levels"] = ema_levels

        # VWAP
        vwap = indicators.get("vwap")
        if vwap:
            levels["vwap"] = {
                "price": round(vwap, 2),
                "distance_pct": round(((current_price - vwap) / current_price) * 100, 2)
            }

        # Bollinger Bands
        bb_upper = indicators.get("bb_upper")
        bb_lower = indicators.get("bb_lower")
        if bb_upper and bb_lower:
            levels["bollinger_bands"] = {
                "upper": round(bb_upper, 2),
                "lower": round(bb_lower, 2)
            }

        return levels
