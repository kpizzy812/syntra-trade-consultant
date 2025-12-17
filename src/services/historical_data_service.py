# coding: utf-8
"""
Historical Data Service

Aggregates and stores historical price data for long-term analysis:
- Fetches OHLCV data from CoinGecko and Binance
- Stores in database for quick access
- Provides historical comparisons
- Enables cycle analysis
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, UTC
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from src.database.models import HistoricalPrice
from src.services.coingecko_service import CoinGeckoService
from src.services.binance_service import BinanceService


from loguru import logger


class HistoricalDataService:
    """
    Service for managing historical cryptocurrency data

    Features:
    - Fetch and store OHLCV data
    - Historical price lookups
    - Price comparisons (current vs historical)
    - Data aggregation for cycle analysis
    """

    def __init__(self):
        self.coingecko = CoinGeckoService()
        self.binance = BinanceService()

    async def fetch_and_store_historical(
        self,
        session: AsyncSession,
        coin_id: str,
        days: int = 365,
        timeframe: str = "1d",
    ) -> int:
        """
        Fetch historical data from CoinGecko and store in database

        Args:
            session: Database session
            coin_id: CoinGecko coin ID (bitcoin, ethereum, etc.)
            days: Number of days of history (max 365 for free tier)
            timeframe: Timeframe (1d, 1h, etc.)

        Returns:
            Number of data points stored
        """
        try:
            # Fetch OHLC data from CoinGecko
            ohlc_data = await self.coingecko.get_ohlc_data(coin_id, days=days)

            if not ohlc_data:
                logger.warning(f"No OHLC data fetched for {coin_id}")
                return 0

            stored_count = 0

            for data_point in ohlc_data:
                timestamp = datetime.fromtimestamp(data_point[0] / 1000)

                # Check if data point already exists
                stmt = select(HistoricalPrice).where(
                    and_(
                        HistoricalPrice.coin_id == coin_id,
                        HistoricalPrice.timestamp == timestamp,
                        HistoricalPrice.timeframe == timeframe,
                    )
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if not existing:
                    # Create new record
                    historical_price = HistoricalPrice(
                        coin_id=coin_id,
                        timestamp=timestamp,
                        timeframe=timeframe,
                        open=data_point[1],
                        high=data_point[2],
                        low=data_point[3],
                        close=data_point[4],
                        volume=0,  # CoinGecko OHLC doesn't include volume
                    )
                    session.add(historical_price)
                    stored_count += 1

            await session.commit()
            logger.info(
                f"Stored {stored_count} historical data points for {coin_id}"
            )
            return stored_count

        except Exception as e:
            logger.exception(f"Error fetching/storing historical data for {coin_id}: {e}")
            await session.rollback()
            return 0

    async def get_historical_price(
        self,
        session: AsyncSession,
        coin_id: str,
        target_date: datetime,
        timeframe: str = "1d",
    ) -> Optional[Dict[str, Any]]:
        """
        Get historical price for a specific date

        Args:
            session: Database session
            coin_id: CoinGecko coin ID
            target_date: Target date
            timeframe: Timeframe

        Returns:
            Dict with price data or None
        """
        try:
            stmt = (
                select(HistoricalPrice)
                .where(
                    and_(
                        HistoricalPrice.coin_id == coin_id,
                        HistoricalPrice.timeframe == timeframe,
                        HistoricalPrice.timestamp >= target_date - timedelta(days=1),
                        HistoricalPrice.timestamp <= target_date + timedelta(days=1),
                    )
                )
                .order_by(HistoricalPrice.timestamp.asc())
                .limit(1)
            )

            result = await session.execute(stmt)
            price_data = result.scalar_one_or_none()

            if price_data:
                return {
                    "coin_id": price_data.coin_id,
                    "timestamp": price_data.timestamp,
                    "open": price_data.open,
                    "high": price_data.high,
                    "low": price_data.low,
                    "close": price_data.close,
                    "volume": price_data.volume,
                }

            return None

        except Exception as e:
            logger.exception(
                f"Error fetching historical price for {coin_id} at {target_date}: {e}"
            )
            return None

    async def get_price_at_time(
        self,
        session: AsyncSession,
        coin_id: str,
        days_ago: int,
    ) -> Optional[float]:
        """
        Get price X days ago

        Args:
            session: Database session
            coin_id: CoinGecko coin ID
            days_ago: Number of days ago

        Returns:
            Price at that time or None
        """
        target_date = datetime.now(UTC) - timedelta(days=days_ago)
        data = await self.get_historical_price(session, coin_id, target_date)

        if data:
            return data["close"]

        return None

    async def get_price_change_since(
        self,
        session: AsyncSession,
        coin_id: str,
        days_ago: int,
        current_price: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate price change since X days ago

        Args:
            session: Database session
            coin_id: CoinGecko coin ID
            days_ago: Number of days ago
            current_price: Current price

        Returns:
            Dict with price change info or None

        Example:
        {
            "days_ago": 365,
            "old_price": 30000,
            "current_price": 45000,
            "change_usd": 15000,
            "change_pct": 50.0
        }
        """
        old_price = await self.get_price_at_time(session, coin_id, days_ago)

        if old_price:
            change_usd = current_price - old_price
            change_pct = (change_usd / old_price) * 100

            return {
                "days_ago": days_ago,
                "old_price": old_price,
                "current_price": current_price,
                "change_usd": change_usd,
                "change_pct": change_pct,
            }

        return None

    async def get_historical_range(
        self,
        session: AsyncSession,
        coin_id: str,
        days: int = 365,
    ) -> Optional[pd.DataFrame]:
        """
        Get historical price range for analysis

        Args:
            session: Database session
            coin_id: CoinGecko coin ID
            days: Number of days to fetch

        Returns:
            pandas DataFrame with historical data or None
        """
        try:
            start_date = datetime.now(UTC) - timedelta(days=days)

            stmt = (
                select(HistoricalPrice)
                .where(
                    and_(
                        HistoricalPrice.coin_id == coin_id,
                        HistoricalPrice.timeframe == "1d",
                        HistoricalPrice.timestamp >= start_date,
                    )
                )
                .order_by(HistoricalPrice.timestamp.asc())
            )

            result = await session.execute(stmt)
            prices = result.scalars().all()

            if not prices:
                return None

            # Convert to DataFrame
            data = [
                {
                    "timestamp": p.timestamp,
                    "open": p.open,
                    "high": p.high,
                    "low": p.low,
                    "close": p.close,
                    "volume": p.volume,
                }
                for p in prices
            ]

            df = pd.DataFrame(data)
            df.set_index("timestamp", inplace=True)

            return df

        except Exception as e:
            logger.exception(f"Error fetching historical range for {coin_id}: {e}")
            return None

    async def format_historical_comparison(
        self, comparison_data: Dict[str, Any]
    ) -> str:
        """
        Format historical price comparison for Telegram

        Args:
            comparison_data: Dict with comparison data

        Returns:
            Formatted string
        """
        if not comparison_data:
            return "❌ Historical comparison data not available"

        days_ago = comparison_data.get("days_ago")
        old_price = comparison_data.get("old_price")
        current_price = comparison_data.get("current_price")
        change_usd = comparison_data.get("change_usd")
        change_pct = comparison_data.get("change_pct")

        emoji = "📈" if change_pct > 0 else "📉"

        text = f"📅 **Price {days_ago} days ago vs Today**\n\n"
        text += f"🕐 {days_ago} days ago: ${old_price:,.2f}\n"
        text += f"🕐 Today: ${current_price:,.2f}\n\n"
        text += f"{emoji} Change: ${change_usd:,.2f} ({change_pct:+.2f}%)\n"

        return text
