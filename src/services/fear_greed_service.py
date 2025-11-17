# coding: utf-8
"""
Fear & Greed Index Service

Provides crypto market sentiment data from Alternative.me API
The Fear & Greed Index is a measure of market sentiment ranging from 0-100:
- 0-24: Extreme Fear
- 25-44: Fear
- 45-55: Neutral
- 56-75: Greed
- 76-100: Extreme Greed
"""
import logging
from typing import Optional, Dict, Any
import aiohttp

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)


logger = logging.getLogger(__name__)


class FearGreedService:
    """
    Service for fetching Fear & Greed Index from Alternative.me

    Features:
    - Current market sentiment
    - Historical sentiment data
    - Sentiment classification
    - Automatic retries on failures
    """

    BASE_URL = "https://api.alternative.me/fng/"

    def __init__(self):
        """Initialize Fear & Greed service"""
        pass

    @staticmethod
    def classify_sentiment(value: int) -> str:
        """
        Classify sentiment based on Fear & Greed value

        Args:
            value: Fear & Greed index (0-100)

        Returns:
            Sentiment classification string
        """
        if value <= 24:
            return "Extreme Fear"
        elif value <= 44:
            return "Fear"
        elif value <= 55:
            return "Neutral"
        elif value <= 75:
            return "Greed"
        else:
            return "Extreme Greed"

    @staticmethod
    def get_emoji(value: int) -> str:
        """
        Get emoji for sentiment value

        Args:
            value: Fear & Greed index (0-100)

        Returns:
            Emoji string
        """
        if value <= 24:
            return "😱"  # Extreme Fear
        elif value <= 44:
            return "😰"  # Fear
        elif value <= 55:
            return "😐"  # Neutral
        elif value <= 75:
            return "😃"  # Greed
        else:
            return "🤑"  # Extreme Greed

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def get_current(self) -> Optional[Dict[str, Any]]:
        """
        Get current Fear & Greed Index with automatic retries

        Retries up to 3 times with exponential backoff for network errors.

        Returns:
            Dict with current sentiment data or None

        Example:
            {
                "value": 45,
                "value_classification": "Neutral",
                "emoji": "😐",
                "timestamp": "1234567890"
            }
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}?limit=1") as response:
                    if response.status == 200:
                        data = await response.json()

                        # Extract data from API response
                        if data and "data" in data and len(data["data"]) > 0:
                            fng_data = data["data"][0]
                            value = int(fng_data.get("value", 50))
                            classification = fng_data.get("value_classification", "Unknown")
                            timestamp = fng_data.get("timestamp", "")

                            result = {
                                "value": value,
                                "value_classification": classification,
                                "emoji": self.get_emoji(value),
                                "timestamp": timestamp
                            }

                            logger.info(f"Fear & Greed Index: {value} ({classification})")
                            return result
                        else:
                            logger.warning("Fear & Greed API returned empty data")
                            return None
                    else:
                        logger.error(f"Fear & Greed API error: {response.status}")
                        return None

        except Exception as e:
            logger.exception(f"Error fetching Fear & Greed Index: {e}")
            return None

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def get_historical(self, limit: int = 7) -> Optional[list]:
        """
        Get historical Fear & Greed Index data with automatic retries

        Args:
            limit: Number of days to fetch (max 30)

        Returns:
            List of historical sentiment data or None

        Example:
            [
                {"value": 45, "classification": "Neutral", "timestamp": "..."},
                {"value": 50, "classification": "Neutral", "timestamp": "..."},
                ...
            ]
        """
        try:
            # Limit to max 30 days
            limit = min(max(1, limit), 30)

            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}?limit={limit}") as response:
                    if response.status == 200:
                        data = await response.json()

                        if data and "data" in data:
                            historical = []
                            for item in data["data"]:
                                value = int(item.get("value", 50))
                                historical.append({
                                    "value": value,
                                    "classification": item.get("value_classification", "Unknown"),
                                    "emoji": self.get_emoji(value),
                                    "timestamp": item.get("timestamp", "")
                                })

                            logger.info(f"Fetched {len(historical)} days of Fear & Greed historical data")
                            return historical
                        else:
                            logger.warning("Fear & Greed API returned empty historical data")
                            return None
                    else:
                        logger.error(f"Fear & Greed API error: {response.status}")
                        return None

        except Exception as e:
            logger.exception(f"Error fetching historical Fear & Greed Index: {e}")
            return None

    def format_sentiment_message(self, sentiment_data: Dict[str, Any]) -> str:
        """
        Format Fear & Greed data into readable message

        Args:
            sentiment_data: Data from get_current()

        Returns:
            Formatted message string
        """
        if not sentiment_data:
            return "❌ Не удалось получить данные Fear & Greed Index"

        value = sentiment_data.get("value", 50)
        classification = sentiment_data.get("value_classification", "Unknown")
        emoji = sentiment_data.get("emoji", "😐")

        return (
            f"{emoji} <b>Fear & Greed Index</b>\n"
            f"Значение: <b>{value}/100</b>\n"
            f"Состояние: <b>{classification}</b>\n\n"
            f"<i>Индикатор настроения криптовалютного рынка</i>"
        )
