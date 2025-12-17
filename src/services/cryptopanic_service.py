# coding: utf-8
"""
CryptoPanic API Service for fetching cryptocurrency news

CryptoPanic API: https://cryptopanic.com/developers/api/
"""
import asyncio
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


from loguru import logger


class RateLimitError(Exception):
    """Raised when API returns 429 Too Many Requests"""
    pass


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

    BASE_URL = "https://cryptopanic.com/api/developer/v2"

    def __init__(self, api_token: str = CRYPTOPANIC_TOKEN):
        """
        Initialize CryptoPanic service

        Args:
            api_token: CryptoPanic API token
        """
        self.api_token = api_token
        self.cache: Dict[str, tuple[Any, datetime]] = {}
        self.stale_cache: Dict[str, Any] = {}  # Fallback при 429 ошибках
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
        # Также сохраняем в stale_cache для fallback при 429 ошибках
        self.stale_cache[key] = value

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        wait=wait_random_exponential(min=2, max=30),
        stop=stop_after_attempt(1),  # Только 1 попытка из-за жестких лимитов
        reraise=True,  # Re-raise exceptions properly
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
                    # Handle rate limit gracefully (no retry, no traceback)
                    if response.status == 429:
                        logger.warning(
                            "⚠️ CryptoPanic rate limit (429) - using cached data"
                        )
                        raise RateLimitError("CryptoPanic API rate limit exceeded")

                    response.raise_for_status()
                    data = await response.json()
                    return data
            except RateLimitError:
                # Re-raise without logging traceback
                raise
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

        except RateLimitError:
            # Rate limit - return stale cache without traceback
            if cache_key in self.stale_cache:
                logger.info("📰 Using cached news (rate limited)")
                return self.stale_cache[cache_key]
            logger.warning("📰 No cached news available during rate limit")
            return []
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            # При других ошибках пытаемся вернуть stale cache
            if cache_key in self.stale_cache:
                logger.warning(
                    f"⚠️ API недоступен, возвращаем stale cache для {cache_key}"
                )
                return self.stale_cache[cache_key]
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

    async def get_relevant_market_news(
        self, btc_change_24h: float, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get relevant market news based on BTC price movement

        Filters news by sentiment (bullish/bearish/neutral) based on BTC 24h change,
        prioritizes recent news (last 24h) and important votes.

        Args:
            btc_change_24h: BTC price change in % over 24h
            limit: Maximum number of news items (default: 3)

        Returns:
            List of news items with structure:
            [{"title", "summary", "sentiment", "source", "url"}]
        """
        # Кешируем на уровне метода для экономии запросов
        cache_key = f"relevant_news_{btc_change_24h:.1f}_{limit}"
        cached = self._get_from_cache(cache_key)
        if cached:
            logger.info("✅ Returning cached relevant market news")
            return cached

        try:
            # Determine sentiment based on BTC movement
            if abs(btc_change_24h) < 0.5:
                sentiment_filter = "rising"  # Neutral/general news
                sentiment_label = "neutral"
            elif btc_change_24h > 0:
                sentiment_filter = "bullish"
                sentiment_label = "bullish"
            else:
                sentiment_filter = "bearish"
                sentiment_label = "bearish"

            logger.info(
                f"Fetching {sentiment_label} news for BTC change {btc_change_24h:+.2f}%"
            )

            # Get news with sentiment filter
            news_items = await self.get_news(
                filter_by=sentiment_filter, limit=limit * 2
            )

            # Filter by time (last 24 hours) and important votes
            now = datetime.now()
            filtered_news = []

            for item in news_items:
                # Check if published within last 24 hours
                published_at = item.get("published_at", "")
                if published_at:
                    try:
                        published_dt = datetime.fromisoformat(
                            published_at.replace("Z", "+00:00")
                        )
                        # Convert to naive datetime for comparison
                        published_dt_naive = published_dt.replace(tzinfo=None)
                        age_hours = (now - published_dt_naive).total_seconds() / 3600

                        # Only include news from last 24 hours
                        if age_hours > 24:
                            continue
                    except Exception:
                        # If parsing fails, skip time filter
                        pass

                # Add importance score for sorting
                votes = item.get("votes", {})
                importance_score = votes.get("important", 0)

                filtered_news.append({
                    "item": item,
                    "importance": importance_score
                })

            # Sort by importance
            filtered_news.sort(key=lambda x: x["importance"], reverse=True)

            # Format output
            result = []
            for entry in filtered_news[:limit]:
                item = entry["item"]
                result.append({
                    "title": item.get("title", "No title"),
                    "summary": item.get("title", ""),  # Use title as summary
                    "sentiment": sentiment_label,
                    "source": item.get("source", "Unknown"),
                    "url": item.get("url", "")
                })

            # НЕ делаем fallback к neutral news - экономим запросы!
            # Жесткие лимиты API (~3 запроса/день)

            logger.info(f"Returning {len(result)} relevant news items")

            # Сохраняем в кеш
            self._set_cache(cache_key, result)

            return result

        except Exception as e:
            logger.error(f"Error in get_relevant_market_news: {e}")
            # При ошибке возвращаем stale cache вместо fallback запроса
            if cache_key in self.stale_cache:
                logger.warning(
                    "⚠️ Возвращаем stale cache для relevant_market_news"
                )
                return self.stale_cache[cache_key]
            return []

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
                except Exception:
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


# Example usage
if __name__ == "__main__":

    async def test():
        service = CryptoPanicService()

        # Test getting Bitcoin news
        logger.debug("Bitcoin News:")
        btc_news = await service.get_news_for_coin("BTC", limit=3)
        logger.debug(service.format_news_for_display(btc_news))

        # Test getting trending news
        logger.debug("Trending News:")
        trending = await service.get_trending_news(limit=3)
        logger.debug(service.format_news_for_display(trending))

    asyncio.run(test())
