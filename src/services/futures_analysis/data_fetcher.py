# coding: utf-8
"""
Data Fetcher - получение данных с бирж с fallback механизмом.

Bybit - primary source
Binance - fallback
"""
from typing import Any, Dict, Optional

import pandas as pd
from loguru import logger

from src.services.binance_service import BinanceService
from src.services.bybit_service import bybit_service


class FuturesDataFetcher:
    """
    Получение рыночных данных с Bybit (primary) и Binance (fallback).
    """

    def __init__(self):
        self.bybit = bybit_service
        self.binance = BinanceService()
        logger.debug("FuturesDataFetcher initialized (Bybit primary, Binance fallback)")

    # =========================================================================
    # CURRENT DATA
    # =========================================================================

    async def get_current_price(self, symbol: str) -> float | None:
        """Get current price: Bybit first, Binance fallback."""
        # Try Bybit first
        price = await self.bybit.get_current_price(symbol)
        if price:
            logger.debug(f"Price for {symbol} from Bybit: {price}")
            return price

        # Fallback to Binance
        logger.info(f"Bybit price failed for {symbol}, trying Binance...")
        price = await self.binance.get_current_price(symbol)
        if price:
            logger.debug(f"Price for {symbol} from Binance: {price}")
        return price

    async def get_klines(
        self, symbol: str, interval: str, limit: int = 200
    ) -> pd.DataFrame | None:
        """Get klines: Bybit first, Binance fallback."""
        # Try Bybit first
        df = await self.bybit.get_klines(symbol, interval, limit)
        if df is not None and len(df) > 0:
            logger.debug(f"Klines for {symbol} from Bybit: {len(df)} candles")
            return df

        # Fallback to Binance
        logger.info(f"Bybit klines failed for {symbol}, trying Binance...")
        df = await self.binance.get_klines(symbol, interval, limit)
        if df is not None:
            logger.debug(f"Klines for {symbol} from Binance: {len(df)} candles")
        return df

    async def get_funding_rate(self, symbol: str) -> dict | None:
        """Get funding rate: Bybit first, Binance fallback."""
        # Try Bybit first
        rate = await self.bybit.get_funding_rate(symbol)
        if rate is not None:
            return {
                "funding_rate": rate,
                "funding_rate_pct": rate * 100,  # Convert to percentage
                "source": "bybit"
            }

        # Fallback to Binance
        data = await self.binance.get_latest_funding_rate(symbol)
        if data:
            data["source"] = "binance"
        return data

    async def get_open_interest(self, symbol: str) -> dict | None:
        """Get open interest: Bybit first, Binance fallback."""
        # Try Bybit first
        oi = await self.bybit.get_open_interest(symbol)
        if oi:
            oi["source"] = "bybit"
            return oi

        # Fallback to Binance
        data = await self.binance.get_open_interest(symbol)
        if data:
            data["source"] = "binance"
        return data

    async def get_long_short_ratio(self, symbol: str, period: str = "5m") -> dict | None:
        """Get long/short ratio: Bybit first, Binance fallback."""
        # Map period for Bybit (uses different format)
        bybit_period_map = {"5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h"}
        bybit_period = bybit_period_map.get(period, "1h")

        # Try Bybit first
        ratio = await self.bybit.get_long_short_ratio(symbol, bybit_period)
        if ratio:
            ratio["source"] = "bybit"
            return ratio

        # Fallback to Binance
        data = await self.binance.get_long_short_ratio(symbol, period, limit=30)
        if data is not None and not data.empty:
            latest = data.iloc[-1]
            return {
                "buyRatio": float(latest.get("longAccount", 0.5)),
                "sellRatio": float(latest.get("shortAccount", 0.5)),
                "source": "binance"
            }
        return None

    # =========================================================================
    # HISTORY METHODS FOR ENRICHMENT
    # =========================================================================

    async def get_funding_history(
        self,
        symbol: str,
        limit: int = 12
    ) -> list | None:
        """Get funding rate history: Binance (has history), Bybit fallback."""
        # Binance has better history API
        try:
            data = await self.binance.get_funding_rate(symbol, limit=limit)
            if data is not None and not data.empty:
                return [
                    {
                        "funding_rate": float(row.get("fundingRate", 0)),
                        "timestamp": int(row.get("fundingTime", 0))
                    }
                    for _, row in data.iterrows()
                ]
        except Exception as e:
            logger.warning(f"Binance funding history error: {e}")

        # No good fallback for history, return None
        return None

    async def get_oi_history(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 24
    ) -> list | None:
        """Get OI history: Bybit first, Binance fallback."""
        # Try Bybit first
        data = await self.bybit.get_open_interest_history(symbol, interval, limit)
        if data:
            return data

        # Fallback to Binance
        binance_period_map = {"1h": "1h", "4h": "4h", "1d": "1d"}
        period = binance_period_map.get(interval, "1h")
        data = await self.binance.get_open_interest_history(symbol, period, limit)
        return data

    async def get_ls_ratio_history(
        self,
        symbol: str,
        period: str = "1h",
        limit: int = 12
    ) -> list | None:
        """Get LS ratio history: Bybit first, Binance fallback."""
        # Try Bybit first
        data = await self.bybit.get_long_short_ratio_history(symbol, period, limit)
        if data:
            return data

        # Fallback to Binance
        binance_period_map = {"1h": "1h", "4h": "4h", "1d": "1d"}
        period = binance_period_map.get(period, "1h")
        data = await self.binance.get_long_short_ratio_history(symbol, period, limit)
        return data

    # =========================================================================
    # MULTI-TIMEFRAME DATA
    # =========================================================================

    async def get_multi_timeframe_data(
        self,
        symbol: str
    ) -> Dict[str, pd.DataFrame]:
        """
        Получить данные с нескольких таймфреймов для контекста.

        Используется для определения:
        - Макро-тренда (1D, 1W)
        - Среднесрочного тренда (4H)
        - Микро-структуры (1H)
        """
        mtf_data = {}
        timeframes = ["1h", "4h", "1d"]

        for tf in timeframes:
            try:
                df = await self.get_klines(symbol, tf, limit=100)
                if df is not None and len(df) >= 20:
                    mtf_data[tf] = df
            except Exception as e:
                logger.warning(f"Failed to fetch {tf} data for {symbol}: {e}")

        return mtf_data

    @property
    def has_binance_credentials(self) -> bool:
        """Check if Binance has API credentials for private endpoints."""
        return self.binance.has_credentials
