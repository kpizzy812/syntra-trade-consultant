# coding: utf-8
"""
CryptoPanic API Service for fetching cryptocurrency news

CryptoPanic API: https://cryptopanic.com/developers/api/
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

import aiohttp
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
)

from config.config import CRYPTOPANIC_TOKEN, CACHE_TTL_CRYPTOPANIC


logger = logging.getLogger(__name__)


class CryptoPanicService:
    """
    Service for fetching cryptocurrency news from CryptoPanic API

    Features:
    - Fetch latest news
    - Filter by coins/currencies
    - Filter by sentiment (positive, negative, neutral)
    - Cache news with TTL
    - Error handling and retries
    """

    BASE_URL = "https://cryptopanic.com/api/v1"

    def __init__(self, api_token: str = CRYPTOPANIC_TOKEN):
        """
        Initialize CryptoPanic service

        Args:
            api_token: CryptoPanic API token
        """
        self.api_token = api_token
        self.cache: Dict[str, tuple[Any, datetime]] = {}
        self.cache_ttl = timedelta(seconds=CACHE_TTL_CRYPTOPANIC)  # Use config TTL

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """
        Get data from cache if not expired

        Args:
            key: Cache key

        Returns:
            Cached data or None
        """
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.cache_ttl:
                return data
            # Expired - remove
            del self.cache[key]
        return None

    def _set_cache(self, key: str, value: Any):
        """
        Set data in cache

        Args:
            key: Cache key
            value: Data to cache
        """
        self.cache[key] = (value, datetime.now())

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        wait=wait_random_exponential(min=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make API request to CryptoPanic

        Args:
            endpoint: API endpoint (e.g., '/posts/')
            params: Query parameters

        Returns:
            Response JSON data

        Raises:
            aiohttp.ClientError: If request fails
        """
        if params is None:
            params = {}

        # Add auth token
        params["auth_token"] = self.api_token

        url = f"{self.BASE_URL}{endpoint}"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data
            except aiohttp.ClientError as e:
                logger.error(f"CryptoPanic API error: {e}")
                raise
            except Exception as e:
                logger.exception(f"Unexpected error in CryptoPanic request: {e}")
                raise

    async def get_news(
        self,
        currencies: Optional[List[str]] = None,
        filter_by: str = "hot",
        kind: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get cryptocurrency news

        Args:
            currencies: List of currency codes (e.g., ['BTC', 'ETH'])
            filter_by: Filter type - 'hot', 'rising', 'bullish', 'bearish', 'important', 'saved', 'lol'
            kind: News kind - 'news', 'media', 'all'
            limit: Maximum number of news items

        Returns:
            List of news items
        """
        # Check cache
        cache_key = f"news_{currencies}_{filter_by}_{kind}_{limit}"
        cached = self._get_from_cache(cache_key)
        if cached:
            logger.info("Returning cached news")
            return cached

        try:
            params: Dict[str, Any] = {"public": "true", "filter": filter_by}

            if currencies:
                params["currencies"] = ",".join(currencies).upper()

            if kind:
                params["kind"] = kind

            data = await self._make_request("/posts/", params)

            # Extract news items
            results = data.get("results", [])

            # Limit results
            news_items = results[:limit]

            # Process news items
            processed_news = []
            for item in news_items:
                news_obj = {
                    "title": item.get("title", ""),
                    "published_at": item.get("published_at", ""),
                    "url": item.get("url", ""),
                    "source": item.get("source", {}).get("title", "Unknown"),
                    "currencies": [
                        c.get("code", "") for c in item.get("currencies", [])
                    ],
                    "kind": item.get("kind", "news"),
                    "votes": {
                        "positive": item.get("votes", {}).get("positive", 0),
                        "negative": item.get("votes", {}).get("negative", 0),
                        "important": item.get("votes", {}).get("important", 0),
                        "liked": item.get("votes", {}).get("liked", 0),
                        "disliked": item.get("votes", {}).get("disliked", 0),
                    },
                }
                processed_news.append(news_obj)

            # Cache results
            self._set_cache(cache_key, processed_news)

            logger.info(f"Fetched {len(processed_news)} news items from CryptoPanic")
            return processed_news

        except Exception as e:
            logger.exception(f"Error fetching news: {e}")
            return []

    async def get_news_for_coin(
        self, coin_id: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get news for specific coin

        Args:
            coin_id: Coin ID/symbol (e.g., 'BTC', 'ETH')
            limit: Maximum number of news items

        Returns:
            List of news items
        """
        return await self.get_news(
            currencies=[coin_id.upper()], filter_by="hot", limit=limit
        )

    async def get_trending_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get trending/hot news

        Args:
            limit: Maximum number of news items

        Returns:
            List of news items
        """
        return await self.get_news(filter_by="hot", limit=limit)

    async def get_bullish_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get bullish news

        Args:
            limit: Maximum number of news items

        Returns:
            List of news items
        """
        return await self.get_news(filter_by="bullish", limit=limit)

    async def get_bearish_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get bearish news

        Args:
            limit: Maximum number of news items

        Returns:
            List of news items
        """
        return await self.get_news(filter_by="bearish", limit=limit)

    def format_news_for_display(
        self, news_items: List[Dict[str, Any]], max_items: int = 5
    ) -> str:
        """
        Format news items for display in Telegram

        Args:
            news_items: List of news items
            max_items: Maximum items to display

        Returns:
            Formatted text
        """
        if not news_items:
            return "📰 Нет свежих новостей"

        text = "📰 <b>Последние новости:</b>\n\n"

        for i, item in enumerate(news_items[:max_items], 1):
            title = item["title"]
            source = item["source"]
            url = item["url"]

            # Get sentiment emoji based on votes
            votes = item["votes"]
            positive = votes.get("positive", 0)
            negative = votes.get("negative", 0)

            if positive > negative:
                emoji = "🟢"
            elif negative > positive:
                emoji = "🔴"
            else:
                emoji = "⚪"

            # Format timestamp
            published = item.get("published_at", "")
            if published:
                try:
                    dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    time_ago = self._format_time_ago(dt)
                except:
                    time_ago = ""
            else:
                time_ago = ""

            text += f'{emoji} <b>{i}.</b> <a href="{url}">{title}</a>\n'
            text += f"   <i>{source}</i>"
            if time_ago:
                text += f" • {time_ago}"
            text += "\n\n"

        return text.strip()

    def _format_time_ago(self, dt: datetime) -> str:
        """
        Format datetime as 'X ago'

        Args:
            dt: Datetime object

        Returns:
            Formatted string (e.g., '2 hours ago')
        """
        now = datetime.now(dt.tzinfo)
        delta = now - dt

        if delta.days > 0:
            return f"{delta.days}д назад"
        elif delta.seconds >= 3600:
            hours = delta.seconds // 3600
            return f"{hours}ч назад"
        elif delta.seconds >= 60:
            minutes = delta.seconds // 60
            return f"{minutes}м назад"
        else:
            return "только что"


# For async import compatibility
import asyncio


# Example usage
if __name__ == "__main__":

    async def test():
        service = CryptoPanicService()

        # Test getting Bitcoin news
        print("Bitcoin News:")
        btc_news = await service.get_news_for_coin("BTC", limit=3)
        print(service.format_news_for_display(btc_news))

        # Test getting trending news
        print("\n\nTrending News:")
        trending = await service.get_trending_news(limit=3)
        print(service.format_news_for_display(trending))

    asyncio.run(test())
