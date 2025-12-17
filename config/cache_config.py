# coding: utf-8
"""
Cache configuration for Redis TTL (Time To Live) settings

Defines cache expiration times for different data types based on:
- Data update frequency
- API rate limits
- User experience requirements
"""
import os


class CacheTTL:
    """
    Time-to-live (TTL) settings for different cache types in seconds

    Optimized based on:
    - API rate limits (CoinGecko: 30/min, CoinMarketCap: 333/day)
    - Data volatility (prices change frequently, metadata rarely)
    - User expectations (balance between freshness and performance)
    """

    # ===========================
    # CoinGecko API TTLs
    # ===========================
    # Rate limit: 30 calls/min (Demo API)

    COINGECKO_PRICE = int(os.getenv("CACHE_TTL_COINGECKO_PRICE", "90"))
    """Current price data - 90s (balances freshness with API limits)"""

    COINGECKO_COIN_DATA = int(os.getenv("CACHE_TTL_COINGECKO_COIN_DATA", "3600"))
    """Coin metadata (name, description, etc.) - 1 hour (rarely changes)"""

    COINGECKO_MARKET_DATA = int(os.getenv("CACHE_TTL_COINGECKO_MARKET_DATA", "300"))
    """Market stats (volume, mcap, etc.) - 5 minutes"""

    COINGECKO_MARKET_CHART = int(os.getenv("CACHE_TTL_COINGECKO_MARKET_CHART", "600"))
    """Historical price charts - 10 minutes (historical data doesn't change)"""

    COINGECKO_TRENDING = int(os.getenv("CACHE_TTL_COINGECKO_TRENDING", "900"))
    """Trending coins - 15 minutes (top lists change slowly)"""

    COINGECKO_GLOBAL = int(os.getenv("CACHE_TTL_COINGECKO_GLOBAL", "300"))
    """Global market data - 5 minutes"""

    COINGECKO_SEARCH = int(os.getenv("CACHE_TTL_COINGECKO_SEARCH", "1800"))
    """Search results - 30 minutes (coin lists rarely change)"""

    # ===========================
    # Binance API TTLs
    # ===========================
    # Rate limit: 6000 weight/min (klines = 2 weight, ~3000 calls/min)
    # Good limits, but caching still beneficial for performance

    BINANCE_KLINES_1M = int(os.getenv("CACHE_TTL_BINANCE_KLINES_1M", "60"))
    """1-minute candles - 1 minute"""

    BINANCE_KLINES_5M = int(os.getenv("CACHE_TTL_BINANCE_KLINES_5M", "180"))
    """5-minute candles - 3 minutes"""

    BINANCE_KLINES_15M = int(os.getenv("CACHE_TTL_BINANCE_KLINES_15M", "300"))
    """15-minute candles - 5 minutes"""

    BINANCE_KLINES_1H = int(os.getenv("CACHE_TTL_BINANCE_KLINES_1H", "600"))
    """Hourly candles - 10 minutes"""

    BINANCE_KLINES_4H = int(os.getenv("CACHE_TTL_BINANCE_KLINES_4H", "1800"))
    """4-hour candles - 30 minutes"""

    BINANCE_KLINES_1D = int(os.getenv("CACHE_TTL_BINANCE_KLINES_1D", "3600"))
    """Daily candles - 1 hour"""

    BINANCE_CURRENT_PRICE = int(os.getenv("CACHE_TTL_BINANCE_CURRENT_PRICE", "30"))
    """Current price - 30 seconds (for ticker data)"""

    BINANCE_FUNDING_RATE = int(os.getenv("CACHE_TTL_BINANCE_FUNDING_RATE", "3600"))
    """Funding rate - 1 hour (updates every 8 hours)"""

    BINANCE_OPEN_INTEREST = int(os.getenv("CACHE_TTL_BINANCE_OPEN_INTEREST", "300"))
    """Open interest - 5 minutes"""

    BINANCE_LONG_SHORT_RATIO = int(os.getenv("CACHE_TTL_BINANCE_LONG_SHORT_RATIO", "600"))
    """Long/short ratio - 10 minutes"""

    # ===========================
    # DexScreener API TTLs
    # ===========================
    # Rate limit: 300 calls/min (DEX endpoints)

    DEXSCREENER_SEARCH = int(os.getenv("CACHE_TTL_DEXSCREENER_SEARCH", "300"))
    """Token search - 5 minutes"""

    DEXSCREENER_TOKEN_PAIRS = int(os.getenv("CACHE_TTL_DEXSCREENER_TOKEN_PAIRS", "300"))
    """Token pairs - 5 minutes"""

    DEXSCREENER_TOKEN_PRICE = int(os.getenv("CACHE_TTL_DEXSCREENER_TOKEN_PRICE", "60"))
    """Token price - 1 minute"""

    # ===========================
    # CoinMarketCap API TTLs
    # ===========================
    # Rate limit: ~333 calls/day (CRITICAL - must cache aggressively)

    COINMARKETCAP_QUOTE = int(os.getenv("CACHE_TTL_COINMARKETCAP_QUOTE", "300"))
    """Price quotes - 5 minutes (save daily limit)"""

    COINMARKETCAP_SEARCH = int(os.getenv("CACHE_TTL_COINMARKETCAP_SEARCH", "3600"))
    """Search results - 1 hour"""

    COINMARKETCAP_GLOBAL = int(os.getenv("CACHE_TTL_COINMARKETCAP_GLOBAL", "600"))
    """Global metrics - 10 minutes"""

    # ===========================
    # Other APIs TTLs
    # ===========================

    CRYPTOPANIC_NEWS = int(os.getenv("CACHE_TTL_CRYPTOPANIC_NEWS", "900"))
    """Crypto news - 15 minutes"""

    FEAR_GREED_INDEX = int(os.getenv("CACHE_TTL_FEAR_GREED_INDEX", "3600"))
    """Fear & Greed Index - 1 hour (updates once per day)"""

    # ===========================
    # Computed/Derived Data TTLs
    # ===========================

    TECHNICAL_INDICATORS = int(os.getenv("CACHE_TTL_TECHNICAL_INDICATORS", "300"))
    """Technical indicators (RSI, MACD, etc.) - 5 minutes"""

    PRICE_LEVELS = int(os.getenv("CACHE_TTL_PRICE_LEVELS", "600"))
    """Support/resistance levels - 10 minutes"""

    CYCLE_ANALYSIS = int(os.getenv("CACHE_TTL_CYCLE_ANALYSIS", "3600"))
    """Market cycle analysis - 1 hour"""

    # ===========================
    # Default TTL
    # ===========================

    DEFAULT = int(os.getenv("CACHE_TTL_DEFAULT", "300"))
    """Default TTL for unspecified data - 5 minutes"""


class CacheConfig:
    """
    Redis connection and behavior configuration
    """

    # Redis connection
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    """Redis connection URL"""

    REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))
    """Maximum connections in pool"""

    REDIS_SOCKET_TIMEOUT = int(os.getenv("REDIS_SOCKET_TIMEOUT", "5"))
    """Socket timeout in seconds"""

    REDIS_SOCKET_CONNECT_TIMEOUT = int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5"))
    """Socket connect timeout in seconds"""

    # Cache behavior
    CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    """Enable/disable caching (useful for debugging)"""

    CACHE_NAMESPACE = os.getenv("CACHE_NAMESPACE", "syntra")
    """Namespace prefix for all cache keys"""

    CACHE_KEY_SEPARATOR = ":"
    """Separator for cache key components"""

    # Fallback behavior
    CACHE_FALLBACK_TO_MEMORY = os.getenv("CACHE_FALLBACK_TO_MEMORY", "true").lower() == "true"
    """Use in-memory cache if Redis is unavailable"""

    CACHE_RAISE_ON_ERROR = os.getenv("CACHE_RAISE_ON_ERROR", "false").lower() == "true"
    """Raise exception if cache fails (false = graceful degradation)"""

    # Monitoring
    CACHE_LOG_HITS = os.getenv("CACHE_LOG_HITS", "false").lower() == "true"
    """Log cache hits (verbose, useful for debugging)"""

    CACHE_LOG_MISSES = os.getenv("CACHE_LOG_MISSES", "true").lower() == "true"
    """Log cache misses (important for monitoring)"""


# Helper function to get TTL by data type
def get_ttl(data_type: str) -> int:
    """
    Get TTL for a specific data type

    Args:
        data_type: Data type identifier (e.g., 'coingecko_price', 'binance_klines_1h')

    Returns:
        TTL in seconds

    Examples:
        >>> get_ttl('coingecko_price')
        90
        >>> get_ttl('binance_klines_1h')
        600
        >>> get_ttl('unknown_type')
        300  # Returns DEFAULT
    """
    # Convert to uppercase and try to get from CacheTTL
    attr_name = data_type.upper()
    return getattr(CacheTTL, attr_name, CacheTTL.DEFAULT)


if __name__ == "__main__":
    # Test configuration
    print("Cache Configuration:")
    print(f"Redis URL: {CacheConfig.REDIS_URL}")
    print(f"Cache Enabled: {CacheConfig.CACHE_ENABLED}")
    print(f"Namespace: {CacheConfig.CACHE_NAMESPACE}")
    print("\nSample TTLs:")
    print(f"CoinGecko Price: {CacheTTL.COINGECKO_PRICE}s")
    print(f"Binance 1h Klines: {CacheTTL.BINANCE_KLINES_1H}s")
    print(f"Fear & Greed: {CacheTTL.FEAR_GREED_INDEX}s")
    print(f"Default: {CacheTTL.DEFAULT}s")
