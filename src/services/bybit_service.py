# coding: utf-8
"""
Bybit Service для SyntraAI

Основной источник рыночных данных для фьючерсов.
Binance используется как fallback.
"""
import aiohttp
import pandas as pd
from typing import Optional, List, Dict, Any
from loguru import logger

from src.cache import get_redis_manager, CacheKeyBuilder
from config.cache_config import CacheTTL


class BybitService:
    """
    Сервис для получения данных с Bybit API.

    Поддерживает:
    - Текущие цены (tickers)
    - OHLCV данные (klines)
    - Информация об инструментах
    - Данные о ликвидациях
    """

    BASE_URL = "https://api.bybit.com"

    # Маппинг timeframe -> Bybit interval
    INTERVAL_MAP = {
        "1m": "1",
        "3m": "3",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "2h": "120",
        "4h": "240",
        "6h": "360",
        "12h": "720",
        "1d": "D",
        "1w": "W",
        "1M": "M",
    }

    def __init__(self):
        self._redis = None
        logger.info("BybitService initialized")

    def _get_klines_ttl(self, interval: str) -> int:
        """Get appropriate TTL for klines based on interval"""
        interval_ttl_map = {
            "1m": CacheTTL.BINANCE_KLINES_1M,
            "5m": CacheTTL.BINANCE_KLINES_5M,
            "15m": CacheTTL.BINANCE_KLINES_15M,
            "1h": CacheTTL.BINANCE_KLINES_1H,
            "4h": CacheTTL.BINANCE_KLINES_4H,
            "1d": CacheTTL.BINANCE_KLINES_1D,
        }
        return interval_ttl_map.get(interval, CacheTTL.BINANCE_KLINES_1H)

    @property
    def redis(self):
        if self._redis is None:
            self._redis = get_redis_manager()
        return self._redis

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Получить текущую цену символа.

        Args:
            symbol: Торговая пара (BTCUSDT)

        Returns:
            Текущая цена или None
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/v5/market/tickers"
                params = {"category": "linear", "symbol": symbol}

                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()

                        if data.get("retCode") != 0:
                            logger.warning(f"Bybit API error: {data.get('retMsg')}")
                            return None

                        tickers = data.get("result", {}).get("list", [])
                        if not tickers:
                            logger.warning(f"Symbol {symbol} not found on Bybit")
                            return None

                        return float(tickers[0].get("lastPrice", 0))

                    logger.warning(f"Bybit API status {response.status}")
                    return None

        except Exception as e:
            logger.error(f"Error fetching Bybit price for {symbol}: {e}")
            return None

    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Получить полную информацию о тикере.

        Returns:
            Dict с полями: lastPrice, price24hPcnt, highPrice24h, lowPrice24h,
            turnover24h, volume24h, bid1Price, ask1Price, fundingRate
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/v5/market/tickers"
                params = {"category": "linear", "symbol": symbol}

                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()

                        if data.get("retCode") != 0:
                            return None

                        tickers = data.get("result", {}).get("list", [])
                        if not tickers:
                            return None

                        return tickers[0]
                    return None

        except Exception as e:
            logger.error(f"Error fetching Bybit ticker for {symbol}: {e}")
            return None

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 200
    ) -> Optional[pd.DataFrame]:
        """
        Получить OHLCV данные (свечи).

        Args:
            symbol: Торговая пара
            interval: Временной интервал (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Количество свечей (макс 1000)

        Returns:
            DataFrame с колонками: open, high, low, close, volume, timestamp
        """
        cache_key = CacheKeyBuilder.build("bybit", "klines", {"interval": interval, "limit": limit, "symbol": symbol})

        # Проверяем кэш
        try:
            cached = await self.redis.get(cache_key)
            if cached:
                df = pd.DataFrame(cached)
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    if col in df.columns:
                        df[col] = df[col].astype(float)
                return df
        except Exception as e:
            logger.warning(f"Redis cache error: {e}")

        try:
            bybit_interval = self.INTERVAL_MAP.get(interval, interval)

            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/v5/market/kline"
                params = {
                    "category": "linear",
                    "symbol": symbol,
                    "interval": bybit_interval,
                    "limit": min(limit, 1000)
                }

                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.warning(f"Bybit klines API status {response.status}")
                        return None

                    data = await response.json()

                    if data.get("retCode") != 0:
                        logger.warning(f"Bybit klines error: {data.get('retMsg')}")
                        return None

                    klines = data.get("result", {}).get("list", [])
                    if not klines:
                        return None

                    # Bybit возвращает: [startTime, open, high, low, close, volume, turnover]
                    rows = []
                    for k in klines:
                        rows.append({
                            "timestamp": int(k[0]),
                            "open": float(k[1]),
                            "high": float(k[2]),
                            "low": float(k[3]),
                            "close": float(k[4]),
                            "volume": float(k[5]),
                        })

                    # Сортировка по времени (старые первыми)
                    rows.sort(key=lambda x: x["timestamp"])
                    df = pd.DataFrame(rows)

                    # Кэшируем
                    ttl = self._get_klines_ttl(interval)
                    try:
                        await self.redis.set(cache_key, rows, ttl=ttl)
                    except Exception as e:
                        logger.warning(f"Redis cache set error: {e}")

                    return df

        except Exception as e:
            logger.error(f"Error fetching Bybit klines for {symbol}: {e}")
            return None

    async def get_instrument_info(self, symbol: str) -> Optional[Dict]:
        """
        Получить информацию об инструменте (tick size, lot size, leverage).
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/v5/market/instruments-info"
                params = {"category": "linear", "symbol": symbol}

                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()

                        if data.get("retCode") != 0:
                            return None

                        instruments = data.get("result", {}).get("list", [])
                        if not instruments:
                            return None

                        return instruments[0]
                    return None

        except Exception as e:
            logger.error(f"Error fetching Bybit instrument info for {symbol}: {e}")
            return None

    async def symbol_exists(self, symbol: str) -> bool:
        """Проверить существует ли символ на Bybit."""
        info = await self.get_instrument_info(symbol)
        return info is not None and info.get("status") == "Trading"

    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        """Получить текущую ставку финансирования."""
        ticker = await self.get_ticker(symbol)
        if ticker:
            rate = ticker.get("fundingRate")
            if rate:
                return float(rate)
        return None

    async def get_open_interest(self, symbol: str) -> Optional[Dict]:
        """
        Получить открытый интерес по символу.

        Returns:
            Dict с openInterest и openInterestValue
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/v5/market/open-interest"
                params = {
                    "category": "linear",
                    "symbol": symbol,
                    "intervalTime": "5min",
                    "limit": 1
                }

                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()

                        if data.get("retCode") != 0:
                            return None

                        oi_list = data.get("result", {}).get("list", [])
                        if oi_list:
                            return {
                                "openInterest": float(oi_list[0].get("openInterest", 0)),
                                "timestamp": int(oi_list[0].get("timestamp", 0))
                            }
                    return None

        except Exception as e:
            logger.error(f"Error fetching Bybit OI for {symbol}: {e}")
            return None

    async def get_recent_liquidations(
        self,
        symbol: str,
        limit: int = 50
    ) -> Optional[List[Dict]]:
        """
        Получить недавние ликвидации.

        ВАЖНО: Bybit публичный API не предоставляет прямой endpoint для ликвидаций.
        Используем альтернативный подход через large trades или WebSocket.

        Returns:
            List ликвидаций с полями: side, qty, price, time
        """
        # Bybit V5 API не имеет публичного endpoint для ликвидаций
        # Ликвидации можно получить только через WebSocket stream
        # Возвращаем None - в будущем можно добавить WebSocket интеграцию
        logger.debug(f"Liquidations API not available for {symbol} via REST")
        return None

    async def get_long_short_ratio(
        self,
        symbol: str,
        period: str = "1h"
    ) -> Optional[Dict]:
        """
        Получить соотношение long/short позиций.

        Args:
            symbol: Торговая пара
            period: Период (5min, 15min, 30min, 1h, 4h, 1d)

        Returns:
            Dict с buyRatio, sellRatio, timestamp
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/v5/market/account-ratio"
                params = {
                    "category": "linear",
                    "symbol": symbol,
                    "period": period,
                    "limit": 1
                }

                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()

                        if data.get("retCode") != 0:
                            return None

                        ratio_list = data.get("result", {}).get("list", [])
                        if ratio_list:
                            return {
                                "buyRatio": float(ratio_list[0].get("buyRatio", 0)),
                                "sellRatio": float(ratio_list[0].get("sellRatio", 0)),
                                "timestamp": int(ratio_list[0].get("timestamp", 0))
                            }
                    return None

        except Exception as e:
            logger.error(f"Error fetching Bybit L/S ratio for {symbol}: {e}")
            return None

    async def get_open_interest_history(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 24
    ) -> Optional[List[Dict]]:
        """
        Получить историю открытого интереса.

        Args:
            symbol: Торговая пара (e.g., "BTCUSDT")
            interval: Интервал (5min, 15min, 30min, 1h, 4h, 1d)
            limit: Количество точек (1-200)

        Returns:
            List of {openInterest, timestamp} dicts
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/v5/market/open-interest"
                params = {
                    "category": "linear",
                    "symbol": symbol,
                    "intervalTime": interval,
                    "limit": min(limit, 200)
                }

                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()

                        if data.get("retCode") != 0:
                            logger.warning(f"Bybit OI history error: {data.get('retMsg')}")
                            return None

                        oi_list = data.get("result", {}).get("list", [])
                        if oi_list:
                            return [
                                {
                                    "openInterest": float(item.get("openInterest", 0)),
                                    "timestamp": int(item.get("timestamp", 0))
                                }
                                for item in oi_list
                            ]
                    return None

        except Exception as e:
            logger.error(f"Error fetching Bybit OI history for {symbol}: {e}")
            return None

    async def get_long_short_ratio_history(
        self,
        symbol: str,
        period: str = "1h",
        limit: int = 12
    ) -> Optional[List[Dict]]:
        """
        Получить историю соотношения long/short позиций.

        Args:
            symbol: Торговая пара
            period: Период (5min, 15min, 30min, 1h, 4h, 1d)
            limit: Количество точек (1-500)

        Returns:
            List of {buyRatio, sellRatio, timestamp} dicts
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/v5/market/account-ratio"
                params = {
                    "category": "linear",
                    "symbol": symbol,
                    "period": period,
                    "limit": min(limit, 500)
                }

                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()

                        if data.get("retCode") != 0:
                            logger.warning(f"Bybit LS ratio history error: {data.get('retMsg')}")
                            return None

                        ratio_list = data.get("result", {}).get("list", [])
                        if ratio_list:
                            return [
                                {
                                    "buyRatio": float(item.get("buyRatio", 0)),
                                    "sellRatio": float(item.get("sellRatio", 0)),
                                    "timestamp": int(item.get("timestamp", 0))
                                }
                                for item in ratio_list
                            ]
                    return None

        except Exception as e:
            logger.error(f"Error fetching Bybit LS ratio history for {symbol}: {e}")
            return None


# Singleton instance
bybit_service = BybitService()
