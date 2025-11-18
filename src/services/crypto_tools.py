# coding: utf-8
"""
Crypto Tools for OpenAI Function Calling

This module defines tools (functions) that AI can call to get crypto data.
Following OpenAI best practices 2025:
- Clear schemas with detailed descriptions
- Limited number of tools (< 15)
- Proper error handling
- Validation
"""
import json
import logging
from typing import Dict, Any, List
from datetime import datetime

import pandas as pd

from src.services.coingecko_service import CoinGeckoService
from src.services.cryptopanic_service import CryptoPanicService
from src.services.binance_service import BinanceService
from src.services.fear_greed_service import FearGreedService
from src.services.technical_indicators import TechnicalIndicators
from src.services.candlestick_patterns import CandlestickPatterns
from src.services.cycle_analysis_service import CycleAnalysisService
from src.services.coinmetrics_service import CoinMetricsService
from src.services.price_levels_service import PriceLevelsService
from src.utils.coin_parser import normalize_coin_name


logger = logging.getLogger(__name__)


def convert_to_serializable(obj: Any) -> Any:
    """
    Convert non-JSON-serializable objects to serializable format

    Args:
        obj: Object to convert (can be dict, list, or any type)

    Returns:
        JSON-serializable version of the object
    """
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: convert_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_to_serializable(item) for item in obj)
    elif pd.isna(obj):
        return None
    else:
        return obj

# Initialize services
from src.services.dexscreener_service import DexScreenerService
from src.services.coinmarketcap_service import CoinMarketCapService
from config.config import COINMARKETCAP_API_KEY

coingecko_service = CoinGeckoService()
dexscreener_service = DexScreenerService()
coinmarketcap_service = CoinMarketCapService(api_key=COINMARKETCAP_API_KEY)
cryptopanic_service = CryptoPanicService()
binance_service = BinanceService()
fear_greed_service = FearGreedService()
technical_indicators = TechnicalIndicators()
candlestick_patterns = CandlestickPatterns()
cycle_service = CycleAnalysisService()
coinmetrics_service = CoinMetricsService()
price_levels_service = PriceLevelsService()


# ============================================================================
# TOOL DEFINITIONS (OpenAI Format)
# ============================================================================

CRYPTO_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_crypto_price",
            "description": (
                "Get current price and market data for ANY cryptocurrency including DEX tokens. "
                "Use this when user asks about price, cost, or 'how much is X'. "
                "Supports: CoinGecko coins, DEX tokens (Solana/Raydium, BSC/PancakeSwap, etc.), "
                "and smaller CEX listings (KuCoin, BingX, Gate.io). "
                "Automatically tries multiple data sources: CoinGecko → CoinMarketCap → DexScreener. "
                "IMPORTANT: If multiple variants found (same name, different chains), return ALL options "
                "and ask user to specify which one. "
                "CRITICAL: If volume_24h_usd < $1000, this is a RED FLAG - warn user about extremely low "
                "liquidity and high risk of scam/rug pull. Be sarcastic about ultra-low volume tokens."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "coin_id": {
                        "type": "string",
                        "description": (
                            "Cryptocurrency identifier. Use CoinGecko ID format: "
                            "'bitcoin', 'ethereum', 'solana', etc. "
                            "If user says BTC, use 'bitcoin'. ETH -> 'ethereum'. "
                            "SOL -> 'solana', DOGE -> 'dogecoin', etc."
                        ),
                    }
                },
                "required": ["coin_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_crypto_news",
            "description": (
                "Get latest cryptocurrency news from CryptoPanic. "
                "Use this when user asks about news, updates, or 'what's happening with X'. "
                "Returns: latest news articles with titles, sources, and sentiment."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "coin_symbol": {
                        "type": "string",
                        "description": (
                            "Cryptocurrency symbol (ticker). Use UPPERCASE: "
                            "'BTC', 'ETH', 'SOL', 'DOGE', etc. "
                            "Bitcoin -> BTC, Ethereum -> ETH, Solana -> SOL."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of news items to return (1-10). Default: 5",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10,
                    },
                },
                "required": ["coin_symbol"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_cryptos",
            "description": (
                "Compare 2-3 cryptocurrencies side-by-side. "
                "Use this when user asks to compare coins or asks 'X or Y which is better'. "
                "Returns: prices, market caps, 24h changes for comparison."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "coin_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Array of 2-3 cryptocurrency IDs to compare. "
                            "Use CoinGecko format: ['bitcoin', 'ethereum'], etc."
                        ),
                        "minItems": 2,
                        "maxItems": 3,
                    }
                },
                "required": ["coin_ids"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_cryptos",
            "description": (
                "Get top cryptocurrencies by market capitalization. "
                "Use this when user asks about 'top coins', "
                "'market overview', or 'what's trending'. "
                "Returns: list of top coins with prices and market data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of top coins to return (5-20). Default: 10",
                        "default": 10,
                        "minimum": 5,
                        "maximum": 20,
                    }
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_overview",
            "description": (
                "Get comprehensive crypto market overview. "
                "Use this when user asks general questions like 'what's happening in crypto', "
                "'market update', 'crypto news today', 'BTC dominance', 'alt season', or "
                "'is it Bitcoin season or altcoin season?'. "
                "Returns: BTC/ETH/Altcoin dominance, total market cap, volume, trending news, "
                "and market sentiment. Essential for understanding market phases."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_technical_analysis",
            "description": (
                "Get comprehensive technical analysis for ANY cryptocurrency (CEX or DEX). "
                "Use this when user asks for 'analysis', 'indicators', "
                "'technical analysis', 'potential', 'should I buy', "
                "questions about market cycle/phase, token fundamentals, or perspectives. "
                "CRITICAL: This tool works for BOTH major coins AND small DEX tokens. "
                "Returns different data based on availability: "
                "- For major coins (CEX): RSI, MACD, EMAs, Bollinger Bands, VWAP, OBV, ATR, "
                "candlestick patterns, ATH/ATL, funding rates, long/short ratio, liquidation history, "
                "on-chain metrics, cycle analysis (Bitcoin), Fear & Greed Index, news. "
                "- For DEX-only tokens: liquidity analysis, volume trends (1h/6h/24h), "
                "price action patterns, transaction counts, market cap/FDV, chain/dex info, "
                "Fear & Greed Index, news. "
                "IMPORTANT: Even without technical indicators, this tool provides valuable "
                "market context, risk assessment, and phase analysis (early/growth/mature/declining). "
                "This is the MOST POWERFUL tool for deep crypto analysis with ALL data sources."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "coin_id": {
                        "type": "string",
                        "description": (
                            "Cryptocurrency identifier. Use CoinGecko ID format: "
                            "'bitcoin', 'ethereum', 'solana', etc."
                        ),
                    },
                    "timeframe": {
                        "type": "string",
                        "description": (
                            "Timeframe for technical indicators. Options: "
                            "'1h' (hourly), '4h' (4 hours), '1d' (daily). "
                            "Default: '4h' for balanced analysis."
                        ),
                        "enum": ["1h", "4h", "1d"],
                        "default": "4h",
                    },
                },
                "required": ["coin_id"],
                "additionalProperties": False,
            },
        },
    },
]


# ============================================================================
# TOOL IMPLEMENTATIONS
# ============================================================================


async def get_crypto_price(coin_id: str) -> Dict[str, Any]:
    """
    Get current price and market data for ANY cryptocurrency with fallback logic

    Tries multiple data sources in order:
    1. CoinGecko (major coins, CEX)
    2. DexScreener (DEX tokens: Solana, BSC, ETH, etc.)
    3. CoinMarketCap (smaller CEX: KuCoin, BingX, Gate.io)

    Args:
        coin_id: Cryptocurrency identifier (name, symbol, or address)

    Returns:
        Dict with price data and data source, or error
    """
    try:
        # Normalize coin name
        normalized_id = normalize_coin_name(coin_id) or coin_id.lower()

        logger.info(f"🔍 Searching price for '{coin_id}' (normalized: '{normalized_id}')")

        # ============================================================================
        # 1. TRY COINGECKO (PRIMARY SOURCE - major coins, established projects)
        # ============================================================================
        try:
            logger.debug(f"Trying CoinGecko for '{normalized_id}'...")
            price_data = await coingecko_service.get_price(
                normalized_id,
                include_24h_change=True,
                include_market_cap=True,
                include_24h_volume=True,
            )

            if price_data and normalized_id in price_data:
                data = price_data[normalized_id]

                # Get coin details for proper name
                coin_details = await coingecko_service.get_coin_data(normalized_id)
                coin_name = (
                    coin_details.get("name", normalized_id.title())
                    if coin_details
                    else normalized_id.title()
                )
                symbol = coin_details.get("symbol", "").upper() if coin_details else ""

                logger.info(f"✅ Found on CoinGecko: {coin_name} ({symbol})")

                return {
                    "success": True,
                    "data_source": "CoinGecko",
                    "coin_id": normalized_id,
                    "name": coin_name,
                    "symbol": symbol,
                    "price_usd": data.get("usd", 0),
                    "change_24h_percent": data.get("usd_24h_change", 0),
                    "market_cap_usd": data.get("usd_market_cap", 0),
                    "volume_24h_usd": data.get("usd_24h_vol", 0),
                }
        except Exception as e:
            logger.debug(f"CoinGecko failed for '{normalized_id}': {e}")

        # ============================================================================
        # 2. TRY COINMARKETCAP (SECONDARY - CEX tokens: KuCoin, BingX, Gate.io)
        # ============================================================================
        try:
            # Only try if API key is configured
            if coinmarketcap_service.api_key:
                logger.debug(f"Trying CoinMarketCap for '{coin_id}'...")
                cmc_data = await coinmarketcap_service.get_quote_by_symbol(coin_id)

                if cmc_data:
                    logger.info(f"✅ Found on CoinMarketCap: {cmc_data['name']} ({cmc_data['symbol']})")

                    return {
                        "success": True,
                        "data_source": "CoinMarketCap",
                        "name": cmc_data["name"],
                        "symbol": cmc_data["symbol"],
                        "price_usd": cmc_data["price"],
                        "change_24h_percent": cmc_data["percent_change_24h"],
                        "market_cap_usd": cmc_data["market_cap"],
                        "volume_24h_usd": cmc_data["volume_24h"],
                        "cmc_rank": cmc_data.get("cmc_rank"),
                        "circulating_supply": cmc_data.get("circulating_supply"),
                        "max_supply": cmc_data.get("max_supply"),
                    }
            else:
                logger.debug("CoinMarketCap API key not configured, skipping")
        except Exception as e:
            logger.debug(f"CoinMarketCap failed for '{coin_id}': {e}")

        # ============================================================================
        # 3. TRY DEXSCREENER (TERTIARY - DEX tokens: Solana, BSC, ETH, etc.)
        # Check for MULTIPLE variants with same name!
        # ============================================================================
        try:
            logger.debug(f"Trying DexScreener for '{coin_id}'...")

            # Get ALL variants first
            dex_variants = await dexscreener_service.get_all_token_variants(coin_id, top_n=3)

            if dex_variants and len(dex_variants) > 0:
                # If multiple variants with significant differences, return all
                if len(dex_variants) > 1:
                    # Check if variants have significantly different market caps
                    market_caps = [v.get("market_cap_usd", 0) for v in dex_variants if v.get("market_cap_usd")]

                    # If market caps differ by more than 10x, show multiple options
                    if market_caps and max(market_caps) > min(market_caps) * 10:
                        logger.info(
                            f"✅ Found {len(dex_variants)} variants on DexScreener - returning multiple options"
                        )

                        return {
                            "success": True,
                            "data_source": "DexScreener (multiple variants)",
                            "multiple_variants": True,
                            "variants": dex_variants,
                            "message": (
                                f"Found {len(dex_variants)} different tokens named '{coin_id}'. "
                                "Please specify which one you're interested in by chain/dex or market cap."
                            )
                        }

                # Single variant or similar market caps - return best one
                best_variant = dex_variants[0]
                logger.info(
                    f"✅ Found on DexScreener: {best_variant['name']} ({best_variant['symbol']}) "
                    f"on {best_variant['chain']}/{best_variant['dex']}"
                )

                return {
                    "success": True,
                    "data_source": f"DexScreener ({best_variant['chain']}/{best_variant['dex']})",
                    "name": best_variant["name"],
                    "symbol": best_variant["symbol"],
                    "price_usd": best_variant["price_usd"],
                    "change_24h_percent": best_variant["price_change_24h"],
                    "market_cap_usd": best_variant["market_cap_usd"],
                    "volume_24h_usd": best_variant["volume_24h_usd"],
                    "liquidity_usd": best_variant["liquidity_usd"],
                    "chain": best_variant["chain"],
                    "dex": best_variant["dex"],
                    "pair_address": best_variant["pair_address"],
                    "token_address": best_variant["token_address"],
                }
        except Exception as e:
            logger.debug(f"DexScreener failed for '{coin_id}': {e}")

        # ============================================================================
        # ALL SOURCES FAILED
        # ============================================================================
        logger.warning(f"❌ Token '{coin_id}' not found in any data source")

        return {
            "success": False,
            "error": (
                f"Cryptocurrency '{coin_id}' not found in any data source. "
                f"Tried: CoinGecko"
                f"{', CoinMarketCap' if coinmarketcap_service.api_key else ''}"
                f", DexScreener. "
                f"Please check the name/symbol and try again."
            ),
            "tried_sources": [
                "CoinGecko",
                "CoinMarketCap" if coinmarketcap_service.api_key else None,
                "DexScreener",
            ],
        }

    except Exception as e:
        logger.exception(f"Error in get_crypto_price for {coin_id}: {e}")
        return {
            "success": False,
            "error": f"Failed to fetch data for {coin_id}: {str(e)}",
        }


async def get_crypto_news(coin_symbol: str, limit: int = 5) -> Dict[str, Any]:
    """
    Get latest cryptocurrency news

    Args:
        coin_symbol: Cryptocurrency symbol (e.g., 'BTC', 'ETH')
        limit: Number of news items (1-10)

    Returns:
        Dict with news data or error
    """
    try:
        # Validate limit
        limit = max(1, min(limit, 10))

        # Get news
        news_items = await cryptopanic_service.get_news_for_coin(
            coin_symbol.upper(), limit=limit
        )

        if not news_items:
            return {
                "success": True,
                "coin_symbol": coin_symbol.upper(),
                "news": [],
            }

        # Format news
        formatted_news = []
        for item in news_items:
            formatted_news.append(
                {
                    "title": item.get("title", "No title"),
                    "source": item.get("source", "Unknown"),
                    "published_at": item.get("published_at", ""),
                    "url": item.get("url", ""),
                    "votes": item.get("votes", {}),
                }
            )

        return {
            "success": True,
            "coin_symbol": coin_symbol.upper(),
            "news": formatted_news,
            "count": len(formatted_news),
        }

    except Exception as e:
        logger.error(f"Error in get_crypto_news for {coin_symbol}: {e}")
        return {
            "success": False,
            "error": f"Failed to fetch news for {coin_symbol}: {str(e)}",
        }


async def compare_cryptos(coin_ids: List[str]) -> Dict[str, Any]:
    """
    Compare multiple cryptocurrencies

    Args:
        coin_ids: List of 2-3 coin IDs to compare

    Returns:
        Dict with comparison data or error
    """
    try:
        # Validate input
        if len(coin_ids) < 2 or len(coin_ids) > 3:
            return {"success": False, "error": "Please provide 2-3 coins to compare"}

        # Get data for each coin
        comparison_data = []

        for coin_id in coin_ids:
            price_result = await get_crypto_price(coin_id)
            if price_result.get("success"):
                comparison_data.append(price_result)

        if not comparison_data:
            return {
                "success": False,
                "error": "Failed to fetch data for any of the specified coins",
            }

        return {
            "success": True,
            "coins": comparison_data,
            "count": len(comparison_data),
        }

    except Exception as e:
        logger.error(f"Error in compare_cryptos for {coin_ids}: {e}")
        return {"success": False, "error": f"Failed to compare cryptos: {str(e)}"}


async def get_top_cryptos(limit: int = 10) -> Dict[str, Any]:
    """
    Get top cryptocurrencies by market cap

    Args:
        limit: Number of coins (5-20)

    Returns:
        Dict with top coins data or error
    """
    try:
        # Validate limit
        limit = max(5, min(limit, 20))

        # Get top coins
        top_coins = await coingecko_service.get_trending_coins(limit=limit)

        if not top_coins:
            return {"success": False, "error": "Failed to fetch top cryptocurrencies"}

        # Format data
        formatted_coins = []
        for coin in top_coins:
            formatted_coins.append(
                {
                    "name": coin.get("name", "Unknown"),
                    "symbol": coin.get("symbol", "").upper(),
                    "price_usd": coin.get("current_price", 0),
                    "change_24h_percent": coin.get("price_change_percentage_24h", 0),
                    "market_cap_usd": coin.get("market_cap", 0),
                    "rank": coin.get("market_cap_rank", 0),
                }
            )

        return {
            "success": True,
            "coins": formatted_coins,
            "count": len(formatted_coins),
        }

    except Exception as e:
        logger.error(f"Error in get_top_cryptos: {e}")
        return {"success": False, "error": f"Failed to fetch top cryptos: {str(e)}"}


async def get_market_overview() -> Dict[str, Any]:
    """
    Get general crypto market overview

    Returns:
        Dict with market overview data or error
    """
    try:
        # Get global market data (dominance, total market cap, etc.)
        global_data = await coingecko_service.get_global_market_data()

        # Get trending news
        news_items = await cryptopanic_service.get_trending_news(limit=10)

        # Format news
        formatted_news = []
        for item in news_items[:5]:  # Top 5 news
            formatted_news.append(
                {
                    "title": item.get("title", "No title"),
                    "source": item.get("source", "Unknown"),
                    "currencies": item.get("currencies", []),
                }
            )

        return {
            "success": True,
            "global_data": global_data or {},
            "trending_news": formatted_news,
            "news_count": len(formatted_news),
        }

    except Exception as e:
        logger.error(f"Error in get_market_overview: {e}")
        return {"success": False, "error": f"Failed to fetch market overview: {str(e)}"}


async def get_technical_analysis(coin_id: str, timeframe: str = "4h") -> Dict[str, Any]:
    """
    Get comprehensive technical analysis for a cryptocurrency

    Combines:
    - Extended market data (ATH/ATL, price changes, tokenomics)
    - Fear & Greed Index
    - Latest news (24h delay, cached for 24h)
    - Funding rates (Binance Futures - trader sentiment)
    - Long/Short ratio (Binance Futures - liquidation zones, account positioning)
    - Liquidation history (Binance API keys required - real liquidation data, volumes)
    - Cycle analysis (Bitcoin only - Rainbow Chart, market phase)
    - On-chain metrics (CoinMetrics - network health, exchange flows)
    - Technical indicators (RSI, MACD, EMAs, Bollinger Bands, VWAP, OBV, ATR, etc.)
    - Candlestick patterns

    Args:
        coin_id: CoinGecko coin ID (e.g., 'bitcoin', 'ethereum')
        timeframe: Timeframe for indicators ('1h', '4h', '1d')

    Returns:
        Dict with comprehensive technical analysis or error
    """
    try:
        # Normalize coin name
        normalized_id = normalize_coin_name(coin_id) or coin_id.lower()

        logger.info(f"Starting technical analysis for {normalized_id} ({timeframe})")

        # 1. Get extended market data (ATH/ATL, tokenomics, etc.)
        extended_data = await coingecko_service.get_extended_market_data(normalized_id)

        # 2. Get Fear & Greed Index
        fear_greed = await fear_greed_service.get_current()

        # 3. Get latest news (24h delay, cached for 24h - perfect!)
        news = []
        coin_symbol = None
        try:
            coin_details = await coingecko_service.get_coin_data(normalized_id)
            coin_symbol = (
                coin_details.get("symbol", "").upper()
                if coin_details
                else normalized_id.upper()
            )
            news = await cryptopanic_service.get_news_for_coin(coin_symbol, limit=5)
        except Exception as e:
            logger.warning(f"Could not fetch news for {normalized_id}: {e}")
            # News are optional, continue without them

        # 4. Get Funding Rates from Binance Futures (trader sentiment)
        funding_data = None
        try:
            # Get Binance symbol for this coin
            symbol = binance_service.get_symbol(normalized_id)
            if symbol:
                funding = await binance_service.get_latest_funding_rate(symbol)
                if funding:
                    funding_data = {
                        "funding_rate_pct": funding["funding_rate_pct"],
                        "sentiment": funding["sentiment"],
                        "funding_time": funding.get("funding_time"),
                    }
                    # Get Open Interest
                    oi = await binance_service.get_open_interest(symbol)
                    if oi:
                        funding_data["open_interest"] = oi["open_interest"]
                    logger.info(
                        f"Got funding rate for {symbol}: {funding['funding_rate_pct']:.4f}%"
                    )
        except Exception as e:
            logger.warning(f"Could not fetch funding data for {normalized_id}: {e}")
            # Funding data is optional, continue without it

        # 4.5. Get Long/Short Ratio from Binance Futures (liquidation zones)
        long_short_data = None
        try:
            # Get Binance symbol for this coin
            symbol = binance_service.get_symbol(normalized_id)
            if symbol:
                ls_ratio = await binance_service.get_long_short_ratio(
                    symbol, period="5m", limit=30
                )
                if ls_ratio:
                    long_short_data = {
                        "long_account": ls_ratio["long_account"],
                        "short_account": ls_ratio["short_account"],
                        "long_short_ratio": ls_ratio["long_short_ratio"],
                        "sentiment": ls_ratio["sentiment"],
                        "timestamp": ls_ratio.get("timestamp"),
                    }
                    logger.info(
                        f"Got Long/Short ratio for {symbol}: "
                        f"{ls_ratio['long_short_ratio']:.2f} "
                        f"({ls_ratio['sentiment']})"
                    )
        except Exception as e:
            logger.warning(f"Could not fetch Long/Short ratio for {normalized_id}: {e}")
            # Long/Short data is optional, continue without it

        # 4.6. Get Liquidation History (REQUIRES API KEYS)
        liquidation_data = None
        try:
            # Only fetch if API keys are configured
            if binance_service.has_credentials:
                symbol = binance_service.get_symbol(normalized_id)
                if symbol:
                    # Get last 24h liquidations
                    liq_history = await binance_service.get_liquidation_history(
                        symbol, limit=1000
                    )
                    if liq_history and liq_history.get("total_liquidations", 0) > 0:
                        liquidation_data = {
                            "total_liquidations": liq_history["total_liquidations"],
                            "total_volume_usd": liq_history["total_volume_usd"],
                            "long_liquidations_usd": liq_history[
                                "long_liquidations_usd"
                            ],
                            "short_liquidations_usd": liq_history[
                                "short_liquidations_usd"
                            ],
                            "period_start": liq_history["period_start"],
                            "period_end": liq_history["period_end"],
                        }
                        logger.info(
                            f"Got liquidation history for {symbol}: "
                            f"${liq_history['total_volume_usd']:,.0f} "
                            f"({liq_history['total_liquidations']} events)"
                        )
        except Exception as e:
            logger.warning(
                f"Could not fetch liquidation history for {normalized_id}: {e}"
            )
            # Liquidation data is optional, continue without it

        # 5. Get Cycle Analysis (Bitcoin only - Rainbow Chart, Pi Cycle)
        cycle_data = None
        if normalized_id == "bitcoin" and extended_data:
            try:
                current_price = extended_data.get("current_price")
                if current_price:
                    rainbow = cycle_service.get_rainbow_chart_data(current_price)
                    cycle_data = {
                        "current_band": rainbow["current_band"],
                        "sentiment": rainbow["sentiment"],
                        "bands": {
                            "hodl": rainbow["bands"]["hodl"],
                            "buy": rainbow["bands"]["buy"],
                            "sell": rainbow["bands"]["sell"],
                            "maximum_bubble": rainbow["bands"]["maximum_bubble"],
                        },
                        "days_since_genesis": rainbow["days_since_genesis"],
                    }
                    logger.info(
                        f"Bitcoin Rainbow Chart: {rainbow['current_band']} band"
                    )
            except Exception as e:
                logger.warning(f"Could not calculate cycle data for Bitcoin: {e}")
                # Cycle data is optional, continue without it

        # 6. Get On-Chain Metrics from CoinMetrics (network health)
        onchain_data = None
        try:
            # CoinMetrics uses different IDs (bitcoin -> btc, ethereum -> eth, etc.)
            coinmetrics_id = coinmetrics_service.get_asset_id(normalized_id)
            if not coinmetrics_id:
                logger.debug(f"No CoinMetrics mapping for {normalized_id}")
            else:
                health = await coinmetrics_service.get_network_health(coinmetrics_id)
                if health and not health.get("error"):
                    onchain_data = {
                        "active_addresses": health.get("active_addresses"),
                        "transaction_count": health.get("transaction_count"),
                    }
                    if "hash_rate" in health:
                        onchain_data["hash_rate"] = health["hash_rate"]

                    # Get Exchange Flows
                    flows = await coinmetrics_service.get_exchange_flows(coinmetrics_id)
                    if flows and not flows.get("error"):
                        onchain_data["exchange_flows"] = {
                            "net_flow": flows["net_flow"],
                            "sentiment": flows["sentiment"],
                        }
                    logger.info(
                        f"Got on-chain metrics for {coinmetrics_id}: "
                        f"{health.get('active_addresses')} addresses"
                    )
        except Exception as e:
            logger.warning(f"Could not fetch on-chain data for {normalized_id}: {e}")
            # On-chain data is optional, continue without it

        # 7. Get candlestick data from Binance
        klines_df = await binance_service.get_klines_by_coin_id(
            normalized_id,
            interval=timeframe,
            limit=200,  # Need enough data for indicators
        )

        # Initialize result dict
        result = {
            "success": True,
            "coin_id": normalized_id,
            "timeframe": timeframe,
            "extended_data": extended_data or {},
            "fear_greed": fear_greed or {},
            "news": news or [],
            "funding_data": funding_data or {},
            "long_short_data": long_short_data or {},
            "liquidation_data": liquidation_data or {},
            "cycle_data": cycle_data or {},
            "onchain_data": onchain_data or {},
            "dex_data": {},  # NEW: DEX data for small tokens
            "technical_indicators": {},
            "candlestick_patterns": {},
            "data_sources": [],
        }

        # Track what data we got
        if extended_data:
            result["data_sources"].append("extended_market_data")
        if fear_greed:
            result["data_sources"].append("fear_greed_index")
        if news:
            result["data_sources"].append("news")
        if funding_data:
            result["data_sources"].append("funding_rates")
        if long_short_data:
            result["data_sources"].append("long_short_ratio")
        if liquidation_data:
            result["data_sources"].append("liquidation_history")
        if cycle_data:
            result["data_sources"].append("cycle_analysis")
        if onchain_data:
            result["data_sources"].append("onchain_metrics")

        # 8. Calculate technical indicators (if klines available)
        if klines_df is not None and len(klines_df) >= 20:
            result["data_sources"].append("technical_indicators")
            result["data_sources"].append("candlestick_patterns")

            # Calculate all indicators
            indicators = technical_indicators.calculate_all_indicators(klines_df)
            if indicators:
                result["technical_indicators"] = indicators

            # Detect candlestick patterns
            patterns = candlestick_patterns.detect_all_patterns(klines_df)
            if patterns:
                result["candlestick_patterns"] = patterns

            logger.info(
                f"Technical analysis complete for {normalized_id}: "
                f"{len(indicators or {})} indicators, "
                f"{len(patterns.get('patterns_found', []))} patterns"
            )
        else:
            # 9. FALLBACK: Try DEXScreener for small/new tokens not on major CEX
            logger.warning(
                f"Insufficient klines data for {normalized_id} on Binance. "
                f"Trying DEXScreener as fallback..."
            )

            try:
                # Get DEX data with more context
                dex_token = await dexscreener_service.get_best_pair(normalized_id)

                if dex_token:
                    # Extract useful DEX metrics
                    current_price = float(dex_token.get("priceUsd", 0))

                    result["dex_data"] = {
                        # Basic info
                        "chain": dex_token.get("chainId", ""),
                        "dex": dex_token.get("dexId", ""),

                        # Price data
                        "price_usd": current_price,
                        "price_native": dex_token.get("priceNative", 0),

                        # Liquidity & Volume
                        "liquidity_usd": dex_token.get("liquidity", {}).get("usd", 0),
                        "volume_24h": dex_token.get("volume", {}).get("h24", 0),
                        "volume_6h": dex_token.get("volume", {}).get("h6", 0),
                        "volume_1h": dex_token.get("volume", {}).get("h1", 0),

                        # Price changes
                        "price_change_5m": dex_token.get("priceChange", {}).get("m5", 0),
                        "price_change_1h": dex_token.get("priceChange", {}).get("h1", 0),
                        "price_change_6h": dex_token.get("priceChange", {}).get("h6", 0),
                        "price_change_24h": dex_token.get("priceChange", {}).get("h24", 0),

                        # Market cap
                        "fdv": dex_token.get("fdv"),
                        "market_cap": dex_token.get("marketCap"),

                        # Additional context
                        "pair_created_at": dex_token.get("pairCreatedAt"),
                        "txns_24h": dex_token.get("txns", {}).get("h24", {}),
                        "txns_6h": dex_token.get("txns", {}).get("h6", {}),
                        "txns_1h": dex_token.get("txns", {}).get("h1", {}),

                        # Buys/Sells ratio (important for momentum)
                        "buys_24h": dex_token.get("txns", {}).get("h24", {}).get("buys", 0),
                        "sells_24h": dex_token.get("txns", {}).get("h24", {}).get("sells", 0),
                    }
                    result["data_sources"].append("dexscreener")

                    logger.info(
                        f"DEXScreener data found for {normalized_id}: "
                        f"${result['dex_data']['liquidity_usd']:,.0f} liquidity, "
                        f"${result['dex_data']['volume_24h']:,.0f} volume 24h"
                    )

                    result["note"] = (
                        f"Token '{normalized_id}' is a DEX token ({result['dex_data']['chain']}/{result['dex_data']['dex']}). "
                        f"Analysis based on DEX metrics: liquidity, volume trends, and price action. "
                        f"Traditional technical indicators (RSI, MACD) unavailable for DEX-only tokens."
                    )
                else:
                    result["note"] = (
                        f"Token '{normalized_id}' not found on major CEX (Binance) or DEX (DexScreener). "
                        f"Limited to market data and news analysis only."
                    )
            except Exception as e:
                logger.error(f"DEXScreener fallback failed for {normalized_id}: {e}")
                result["note"] = (
                    f"Token '{normalized_id}' not available on Binance or DEXScreener. "
                    f"Analysis limited to available market data and Fear & Greed Index."
                )

        # 10. Calculate Price Levels (Fibonacci, Support/Resistance, Scenario Levels)
        if extended_data:
            try:
                current_price = extended_data.get("current_price")
                ath_price = extended_data.get("ath")
                atl_price = extended_data.get("atl")

                if current_price and ath_price:
                    # Calculate Fibonacci retracement levels
                    fibonacci_data = price_levels_service.calculate_fibonacci_retracement(
                        current_price=current_price,
                        ath_price=ath_price,
                        atl_price=atl_price
                    )

                    if fibonacci_data.get("success"):
                        result["fibonacci_levels"] = fibonacci_data
                        result["data_sources"].append("fibonacci_retracement")
                        logger.info(
                            f"Fibonacci levels calculated for {normalized_id}: "
                            f"Current zone: {fibonacci_data.get('current_zone')}"
                        )

                        # Calculate Support/Resistance from OHLC if available
                        support_resistance_data = None
                        if klines_df is not None and len(klines_df) >= 20:
                            # Convert klines_df to list of dicts for S/R calculation
                            ohlc_data = klines_df[['high', 'low', 'close', 'volume']].to_dict('records')
                            support_resistance_data = price_levels_service.calculate_support_resistance_from_ohlc(
                                ohlc_data=ohlc_data,
                                current_price=current_price,
                                lookback_periods=90
                            )
                            if support_resistance_data.get("success"):
                                result["support_resistance"] = support_resistance_data
                                result["data_sources"].append("support_resistance")
                                logger.info(
                                    f"S/R levels calculated for {normalized_id}: "
                                    f"{len(support_resistance_data.get('support_levels', []))} support, "
                                    f"{len(support_resistance_data.get('resistance_levels', []))} resistance"
                                )

                        # Generate scenario-specific price levels
                        scenario_levels = price_levels_service.generate_scenario_levels(
                            current_price=current_price,
                            ath_price=ath_price,
                            atl_price=atl_price,
                            fibonacci_data=fibonacci_data,
                            support_resistance_data=support_resistance_data
                        )

                        if scenario_levels.get("success"):
                            result["scenario_levels"] = scenario_levels
                            result["data_sources"].append("scenario_levels")
                            logger.info(
                                f"Scenario levels generated for {normalized_id}: "
                                f"Fibonacci zone: {scenario_levels.get('fibonacci_zone')}"
                            )

            except Exception as e:
                logger.warning(f"Could not calculate price levels for {normalized_id}: {e}")
                # Price levels are optional, continue without them

        return result

    except Exception as e:
        logger.exception(f"Error in get_technical_analysis for {coin_id}: {e}")
        return {
            "success": False,
            "error": f"Failed to perform technical analysis for {coin_id}: {str(e)}",
        }


# ============================================================================
# TOOL EXECUTOR
# ============================================================================


async def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Execute a tool (function) and return JSON result

    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments as dict

    Returns:
        JSON string with result
    """
    try:
        logger.info(f"Executing tool: {tool_name} with args: {arguments}")

        # Route to appropriate function
        if tool_name == "get_crypto_price":
            result = await get_crypto_price(**arguments)
        elif tool_name == "get_crypto_news":
            result = await get_crypto_news(**arguments)
        elif tool_name == "compare_cryptos":
            result = await compare_cryptos(**arguments)
        elif tool_name == "get_top_cryptos":
            result = await get_top_cryptos(**arguments)
        elif tool_name == "get_market_overview":
            result = await get_market_overview(**arguments)
        elif tool_name == "get_technical_analysis":
            result = await get_technical_analysis(**arguments)
        else:
            result = {"success": False, "error": f"Unknown tool: {tool_name}"}

        # Convert pandas Timestamp and other non-serializable objects
        result = convert_to_serializable(result)
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Error executing tool {tool_name}: {e}")
        return json.dumps(
            {"success": False, "error": f"Tool execution failed: {str(e)}"},
            ensure_ascii=False,
        )
