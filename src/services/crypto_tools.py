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
import time
from typing import Dict, Any, List
from datetime import datetime

import pandas as pd
import numpy as np

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


from loguru import logger


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
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
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
from config.config import COINMARKETCAP_API_KEY, RateLimits

coingecko_service = CoinGeckoService(rate_limit=RateLimits.COINGECKO_CALLS_PER_MINUTE)
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
    {
        "type": "function",
        "function": {
            "name": "get_coins_by_category",
            "description": (
                "Get cryptocurrencies by specific category (Layer-1, DeFi, Gaming, etc.). "
                "Use this when user asks about specific categories like: "
                "'show me Layer-1 coins', 'what are the best DeFi projects', "
                "'gaming tokens', 'which Layer-2 solutions exist', etc. "
                "Popular categories: layer-1, smart-contract-platform, decentralized-finance-defi, "
                "layer-2, gaming, metaverse, ethereum-ecosystem, solana-ecosystem, "
                "binance-smart-chain, polygon-ecosystem, avalanche-ecosystem, "
                "decentralized-exchange, lending-borrowing, yield-farming, "
                "oracle, privacy-coins, meme-token, infrastructure. "
                "Returns top coins in that category by market cap, excluding BTC/ETH."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": (
                            "Category ID. Popular categories:\n"
                            "- layer-1: Layer 1 blockchains (SOL, ADA, AVAX, DOT)\n"
                            "- smart-contract-platform: Smart contract platforms\n"
                            "- decentralized-finance-defi: DeFi projects (UNI, AAVE, MKR)\n"
                            "- layer-2: Layer 2 solutions (ARB, OP, MATIC)\n"
                            "- gaming: Gaming & Metaverse (AXS, SAND, MANA)\n"
                            "- ethereum-ecosystem: Ethereum ecosystem projects\n"
                            "- solana-ecosystem: Solana ecosystem projects\n"
                            "- decentralized-exchange: DEX tokens (UNI, SUSHI, CAKE)\n"
                            "- lending-borrowing: Lending protocols (AAVE, COMP)\n"
                            "- oracle: Oracle networks (LINK, BAND)\n"
                            "- meme-token: Meme coins (DOGE, SHIB, PEPE)\n"
                            "If unsure, use closest match (e.g., 'layer-1' for 'L1')."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of coins to return (5-20). Default: 10",
                        "default": 10,
                        "minimum": 5,
                        "maximum": 20,
                    },
                },
                "required": ["category"],
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


async def get_top_cryptos(limit: int = 10, altcoins_only: bool = False) -> Dict[str, Any]:
    """
    Get top cryptocurrencies by market cap

    Args:
        limit: Number of coins (5-20)
        altcoins_only: If True, exclude BTC and ETH (default: False)

    Returns:
        Dict with top coins data or error
    """
    try:
        # Validate limit
        limit = max(5, min(limit, 20))

        # OPTIMIZATION: Use new get_top_altcoins if altcoins_only requested
        if altcoins_only:
            top_coins = await coingecko_service.get_top_altcoins(
                limit=limit,
                exclude_stablecoins=True
            )
        else:
            # Get all top coins including BTC/ETH
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


async def get_coins_by_category(category: str, limit: int = 10) -> Dict[str, Any]:
    """
    Get cryptocurrencies by category

    Args:
        category: Category ID (e.g., 'layer-1', 'decentralized-finance-defi')
        limit: Number of coins (5-20)

    Returns:
        Dict with coins data or error
    """
    try:
        # Validate limit
        limit = max(5, min(limit, 20))

        # Get coins by category
        coins = await coingecko_service.get_coins_by_category(
            category=category,
            per_page=limit,
            exclude_btc_eth=True
        )

        if not coins:
            return {
                "success": False,
                "error": f"No coins found for category '{category}' or category doesn't exist"
            }

        # Format data
        formatted_coins = []
        for coin in coins:
            formatted_coins.append(
                {
                    "name": coin.get("name", "Unknown"),
                    "symbol": coin.get("symbol", "").upper(),
                    "price_usd": coin.get("current_price", 0),
                    "change_24h_percent": coin.get("price_change_percentage_24h", 0),
                    "market_cap_usd": coin.get("market_cap", 0),
                    "rank": coin.get("market_cap_rank", 0),
                    "ath_usd": coin.get("ath", 0),
                    "ath_change_percent": coin.get("ath_change_percentage", 0),
                }
            )

        return {
            "success": True,
            "category": category,
            "coins": formatted_coins,
            "count": len(formatted_coins),
        }

    except Exception as e:
        logger.error(f"Error in get_coins_by_category for {category}: {e}")
        return {"success": False, "error": f"Failed to fetch coins for category: {str(e)}"}


# Cache for market overview results (to avoid rate limits)
_market_overview_cache = None
_market_overview_cache_time = 0
MARKET_OVERVIEW_CACHE_TTL = 120  # 2 minutes cache


async def get_market_overview() -> Dict[str, Any]:
    """
    Get comprehensive crypto market overview with BTC/ETH prices, technical analysis, and relevant news

    Uses aggressive caching (2 minutes) to prevent rate limit issues when multiple users
    request market data simultaneously.

    Returns:
        Dict with structured market data:
        {
            "btc": {"price", "change_24h", "rsi", "support", "resistance", "tf"},
            "eth": {"price", "change_24h"},
            "market": {"btc_dominance", "dominance_change_24h", "fear_greed_index", "total_mcap_change_24h", "trend"},
            "news": [{"title", "summary", "sentiment", "source", "url"}]
        }
    """
    global _market_overview_cache, _market_overview_cache_time

    # Check cache first
    current_time = time.time()
    if _market_overview_cache and (current_time - _market_overview_cache_time) < MARKET_OVERVIEW_CACHE_TTL:
        cache_age = int(current_time - _market_overview_cache_time)
        logger.info(f"📦 Returning cached market overview (age: {cache_age}s, TTL: {MARKET_OVERVIEW_CACHE_TTL}s)")
        return _market_overview_cache

    try:
        logger.info("Starting comprehensive market overview collection...")

        # ========== 1. GET BTC PRICE + TECHNICAL ANALYSIS ==========
        btc_data = {}
        try:
            # Get BTC price
            btc_price_result = await get_crypto_price("bitcoin")
            if btc_price_result.get("success"):
                btc_price = btc_price_result.get("price_usd", 0)
                btc_change_24h = btc_price_result.get("change_24h_percent", 0)

                # Get brief TA for BTC (1d timeframe)
                btc_ta = await get_technical_analysis("bitcoin", "1d")

                # Extract key TA data
                rsi = None
                support = None
                resistance = None

                if btc_ta.get("success"):
                    # Extract technical indicators
                    indicators = btc_ta.get("technical_indicators", {})
                    rsi = indicators.get("rsi")
                    macd = indicators.get("macd")  # MACD signal
                    ema_20 = indicators.get("ema_20")
                    ema_50 = indicators.get("ema_50")

                    # Get support/resistance from scenario levels
                    scenario_levels = btc_ta.get("scenario_levels", {})
                    if scenario_levels and scenario_levels.get("success"):
                        key_levels = scenario_levels.get("key_levels", {})
                        # Try immediate levels first, fallback to major levels
                        support = key_levels.get("immediate_support") or key_levels.get("major_support")
                        resistance = key_levels.get("immediate_resistance") or key_levels.get("major_resistance")

                    # Fallback to fibonacci levels if scenario levels not available
                    if not support or not resistance:
                        fib_levels = btc_ta.get("fibonacci_levels", {})
                        if fib_levels and fib_levels.get("success"):
                            # Use nearest support/resistance from fibonacci
                            nearest_support = fib_levels.get("nearest_support")
                            nearest_resistance = fib_levels.get("nearest_resistance")
                            if nearest_support:
                                support = nearest_support.get("price")
                            if nearest_resistance:
                                resistance = nearest_resistance.get("price")

                    # Extract funding data (futures sentiment)
                    funding_data = btc_ta.get("funding_data")
                    funding_rate = None
                    funding_sentiment = None
                    if funding_data:
                        funding_rate = funding_data.get("funding_rate_pct")
                        funding_sentiment = funding_data.get("sentiment")

                    # Extract long/short ratio (liquidation zones)
                    long_short_data = btc_ta.get("long_short_data")
                    long_short_ratio = None
                    ls_sentiment = None
                    if long_short_data:
                        long_short_ratio = long_short_data.get("long_short_ratio")
                        ls_sentiment = long_short_data.get("sentiment")

                    # Extract cycle data (Rainbow Chart + Pi Cycle - market phase)
                    cycle_data = btc_ta.get("cycle_data")
                    market_phase = None
                    pi_cycle_signal = None
                    pi_cycle_distance = None
                    ma_200w_distance = None

                    if cycle_data:
                        market_phase = cycle_data.get("current_band")  # e.g., "Buy zone", "Accumulate", "HODL", "Sell zone"

                        # Pi Cycle Top indicator
                        pi_cycle = cycle_data.get("pi_cycle")
                        if pi_cycle:
                            pi_cycle_signal = pi_cycle.get("signal")  # "top_signal", "overheated", "bullish"
                            pi_cycle_distance = pi_cycle.get("distance_to_top_pct")

                        # 200 Week MA distance
                        ma_200w_distance = cycle_data.get("distance_from_200w_pct")

                    # Extract ATH data from extended market data
                    extended_data = btc_ta.get("extended_market_data", {})
                    ath = extended_data.get("ath", 0)
                    ath_change_pct = extended_data.get("ath_change_percentage", 0)

                btc_data = {
                    "price": btc_price,
                    "change_24h": btc_change_24h,
                    "ath": ath,
                    "ath_change_pct": ath_change_pct,
                    "rsi": rsi,
                    "macd": macd,
                    "ema_20": ema_20,
                    "ema_50": ema_50,
                    "support": support,
                    "resistance": resistance,
                    "funding_rate": funding_rate,
                    "funding_sentiment": funding_sentiment,
                    "long_short_ratio": long_short_ratio,
                    "ls_sentiment": ls_sentiment,
                    "market_phase": market_phase,  # Rainbow Chart band
                    "pi_cycle_signal": pi_cycle_signal,  # Pi Cycle Top signal
                    "pi_cycle_distance": pi_cycle_distance,  # Distance to top %
                    "ma_200w_distance": ma_200w_distance,  # Distance from 200W MA floor %
                    "tf": "1d"
                }
                logger.info(f"BTC data collected: ${btc_price:,.2f} ({btc_change_24h:+.2f}%)")
        except Exception as e:
            logger.warning(f"Failed to get BTC data: {e}")
            btc_data = {"error": str(e)}

        # ========== 2. GET ETH + TOP ALTCOINS DATA DYNAMICALLY ==========
        eth_data = {}
        alts_data = []

        try:
            # OPTIMIZATION: Use dynamic top altcoins method instead of hardcoded list
            # This gets the most relevant altcoins by market cap, excluding BTC, ETH and stablecoins
            logger.info("Fetching top altcoins dynamically from CoinGecko...")

            # Get top 30 altcoins (we'll process top 15-20 for overview)
            top_altcoins = await coingecko_service.get_top_altcoins(
                vs_currency="usd",
                limit=30,
                exclude_stablecoins=True
            )

            if top_altcoins:
                logger.info(f"✅ Got {len(top_altcoins)} top altcoins in 1 API call")

                # Process altcoins data
                for coin in top_altcoins[:15]:  # Use top 15 for analysis
                    coin_info = {
                        "id": coin.get("id"),
                        "symbol": coin.get("symbol", "").upper(),
                        "price": coin.get("current_price", 0),
                        "change_24h": coin.get("price_change_percentage_24h", 0),
                        "ath": coin.get("ath", 0),
                        "ath_change_pct": coin.get("ath_change_percentage", 0),
                    }
                    alts_data.append(coin_info)

                # Calculate average drawdown from ATH for altcoins
                if alts_data:
                    avg_drawdown = sum(alt["ath_change_pct"] for alt in alts_data) / len(alts_data)
                    median_drawdown = sorted([alt["ath_change_pct"] for alt in alts_data])[len(alts_data) // 2]
                    logger.info(
                        f"Alts data: {len(alts_data)} coins, "
                        f"avg drawdown: {avg_drawdown:.1f}%, median: {median_drawdown:.1f}%"
                    )

            # Get ETH data separately (simple price check)
            eth_price_result = await get_crypto_price("ethereum")
            if eth_price_result.get("success"):
                # Get extended data for ATH from the markets call if available
                # Otherwise make separate request
                eth_market_data = next(
                    (coin for coin in top_altcoins if coin.get("id") == "ethereum"),
                    None
                ) if top_altcoins else None

                if eth_market_data:
                    eth_data = {
                        "price": eth_market_data.get("current_price", 0),
                        "change_24h": eth_market_data.get("price_change_percentage_24h", 0),
                        "ath": eth_market_data.get("ath", 0),
                        "ath_change_pct": eth_market_data.get("ath_change_percentage", 0),
                    }
                else:
                    # Fallback to extended market data
                    eth_extended = await coingecko_service.get_extended_market_data("ethereum")
                    eth_data = {
                        "price": eth_price_result.get("price_usd", 0),
                        "change_24h": eth_price_result.get("change_24h_percent", 0),
                        "ath": eth_extended.get("ath", 0) if eth_extended else 0,
                        "ath_change_pct": eth_extended.get("ath_change_percentage", 0) if eth_extended else 0,
                    }
                logger.info(f"ETH data collected: ${eth_data['price']:,.2f} ({eth_data['change_24h']:+.2f}%)")

        except Exception as e:
            logger.warning(f"Failed to get dynamic altcoins data: {e}")
            # Fallback: try to get at least ETH data
            try:
                eth_price_result = await get_crypto_price("ethereum")
                if eth_price_result.get("success"):
                    eth_extended = await coingecko_service.get_extended_market_data("ethereum")
                    eth_data = {
                        "price": eth_price_result.get("price_usd", 0),
                        "change_24h": eth_price_result.get("change_24h_percent", 0),
                        "ath": eth_extended.get("ath", 0) if eth_extended else 0,
                        "ath_change_pct": eth_extended.get("ath_change_percentage", 0) if eth_extended else 0,
                    }
                    logger.info(f"ETH data collected (fallback): ${eth_data['price']:,.2f}")
            except Exception as fallback_error:
                logger.warning(f"Fallback ETH fetch also failed: {fallback_error}")
                eth_data = {"error": str(fallback_error)}

        # ========== 4. GET GLOBAL MARKET DATA ==========
        market_data = {}
        try:
            global_data = await coingecko_service.get_global_market_data()

            if not global_data:
                logger.warning("CoinGecko API returned no global data (API error, rate limit, or network issue)")

            if global_data:
                # Extract dominance data (coingecko_service now returns enhanced metrics)
                # NEW: Now includes stablecoin_dominance, total2/total3, and real altcoin_dominance
                btc_dominance = global_data.get("btc_dominance", 0)
                eth_dominance = global_data.get("eth_dominance", 0)
                stablecoin_dominance = global_data.get("stablecoin_dominance", 0)
                altcoin_dominance = global_data.get("altcoin_dominance", 0)  # Now excludes stablecoins
                total2_dominance = global_data.get("total2_dominance", 0)
                total3_dominance = global_data.get("total3_dominance", 0)

                # Log warning if dominance values are missing or zero
                if btc_dominance == 0 or eth_dominance == 0:
                    logger.warning(
                        f"Missing dominance data from coingecko_service: BTC={btc_dominance}, ETH={eth_dominance}"
                    )

                # Calculate dominance change (we don't have historical, so estimate from BTC vs market change)
                total_mcap_change = global_data.get("market_cap_change_percentage_24h_usd", 0)
                btc_change = btc_data.get("change_24h", 0)

                # Rough estimation: if BTC grows faster than market, dominance increases
                dominance_change_24h = 0
                if btc_change and total_mcap_change:
                    dominance_change_24h = (btc_change - total_mcap_change) * 0.1  # Scale factor

                # Get Fear & Greed Index
                fear_greed = await fear_greed_service.get_current()
                fear_greed_value = fear_greed.get("value", 50) if fear_greed else 50

                # Determine market trend based on multiple factors
                trend = "sideways"
                if btc_change > 2 and total_mcap_change > 1:
                    trend = "bullish"
                elif btc_change < -2 and total_mcap_change < -1:
                    trend = "bearish"

                # Determine market phase for altseason detection
                # Altseason indicators:
                # - BTC dominance declining
                # - Real Alts dominance rising (excluding stablecoins)
                # - TOTAL3 dominance rising
                market_phase = "btc_season"  # Default
                if altcoin_dominance > 25 and total3_dominance > 35:
                    market_phase = "alt_season"
                elif eth_dominance > 15 and btc_dominance < 50:
                    market_phase = "eth_season"
                elif stablecoin_dominance > 12:
                    market_phase = "risk_off"  # Capital flowing to stablecoins

                market_data = {
                    # Core dominance metrics
                    "btc_dominance": btc_dominance,
                    "eth_dominance": eth_dominance,
                    "stablecoin_dominance": stablecoin_dominance,
                    "altcoin_dominance": altcoin_dominance,  # Real alts (excludes stablecoins)
                    # TradingView-style metrics
                    "total2_dominance": total2_dominance,  # All except BTC
                    "total3_dominance": total3_dominance,  # All except BTC & ETH
                    # Market metrics
                    "dominance_change_24h": dominance_change_24h,
                    "fear_greed_index": fear_greed_value,
                    "total_mcap_change_24h": total_mcap_change,
                    "trend": trend,
                    "market_phase": market_phase,  # NEW: alt_season/btc_season/eth_season/risk_off
                }
                # Log enhanced market data
                logger.info(
                    f"Market data: BTC {btc_dominance:.2f}%, ETH {eth_dominance:.2f}%, "
                    f"Stables {stablecoin_dominance:.2f}%, Real Alts {altcoin_dominance:.2f}% | "
                    f"TOTAL2 {total2_dominance:.2f}%, TOTAL3 {total3_dominance:.2f}% | "
                    f"F&G: {fear_greed_value}, Phase: {market_phase}, Trend: {trend}"
                )
        except Exception as e:
            logger.warning(f"Failed to get market data: {e}")
            market_data = {"error": str(e)}

        # ========== 4. GET RELEVANT NEWS ==========
        news_data = []
        try:
            btc_change = btc_data.get("change_24h", 0)
            news_data = await cryptopanic_service.get_relevant_market_news(
                btc_change_24h=btc_change,
                limit=3
            )
            logger.info(f"Got {len(news_data)} relevant news items")
        except Exception as e:
            logger.warning(f"Failed to get relevant news: {e}")
            # Fallback to trending news
            try:
                news_items = await cryptopanic_service.get_trending_news(limit=3)
                news_data = []
                for item in news_items:
                    news_data.append({
                        "title": item.get("title", "No title"),
                        "summary": item.get("title", ""),  # Use title as summary
                        "sentiment": "neutral",
                        "source": item.get("source", "Unknown"),
                        "url": item.get("url", "")
                    })
            except:
                pass

        # ========== 5. CACHE AND RETURN STRUCTURED DATA ==========
        result = {
            "success": True,
            "btc": btc_data,
            "eth": eth_data,
            "alts": alts_data,  # Top altcoins with ATH data for risk/reward analysis
            "market": market_data,
            "news": news_data
        }

        # Cache the result
        _market_overview_cache = result
        _market_overview_cache_time = time.time()
        logger.info(f"✅ Market overview cached for {MARKET_OVERVIEW_CACHE_TTL}s")

        return result

    except Exception as e:
        logger.error(f"Error in get_market_overview: {e}")

        # If we have cached data, return it even if expired (graceful degradation)
        if _market_overview_cache:
            cache_age = int(time.time() - _market_overview_cache_time)
            logger.warning(f"⚠️ Error occurred, returning stale cache (age: {cache_age}s)")
            return _market_overview_cache

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
                    # Convert funding_time to string if it's a Timestamp
                    funding_time = funding.get("funding_time")
                    if funding_time and hasattr(funding_time, 'isoformat'):
                        funding_time = funding_time.isoformat()

                    funding_data = {
                        "funding_rate_pct": funding["funding_rate_pct"],
                        "sentiment": funding["sentiment"],
                        "funding_time": funding_time,
                    }
                    # Get Open Interest
                    oi = await binance_service.get_open_interest(symbol)
                    if oi:
                        funding_data["open_interest"] = oi["open_interest"]
                        # Convert timestamp to string if present
                        if "timestamp" in oi and hasattr(oi["timestamp"], 'isoformat'):
                            funding_data["open_interest_timestamp"] = oi["timestamp"].isoformat()
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
                    # timestamp уже строка из binance_service (строка 618)
                    long_short_data = {
                        "long_account": ls_ratio["long_account"],
                        "short_account": ls_ratio["short_account"],
                        "long_short_ratio": ls_ratio["long_short_ratio"],
                        "sentiment": ls_ratio["sentiment"],
                        "timestamp": ls_ratio.get("timestamp"),  # Already a string
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
                    # Rainbow Chart
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

                    # Pi Cycle Top Indicator (requires 350+ days of data)
                    # Загружаем исторические данные только для Pi Cycle
                    try:
                        pi_cycle_klines = await binance_service.get_klines_by_coin_id(
                            "bitcoin",
                            interval="1d",  # Daily candles
                            limit=400,      # 400 days for Pi Cycle (350 needed + buffer)
                        )

                        if pi_cycle_klines is not None and len(pi_cycle_klines) >= 350:
                            pi_cycle_result = cycle_service.calculate_pi_cycle_top(pi_cycle_klines)

                            if "error" not in pi_cycle_result:
                                cycle_data["pi_cycle"] = {
                                    "ma_111": pi_cycle_result["ma_111"],
                                    "ma_350_x2": pi_cycle_result["ma_350_x2"],
                                    "signal": pi_cycle_result["signal"],
                                    "distance_to_top_pct": pi_cycle_result["distance_to_top_pct"],
                                }
                                logger.info(
                                    f"Bitcoin Pi Cycle: {pi_cycle_result['signal']} "
                                    f"(distance: {pi_cycle_result['distance_to_top_pct']:.2f}%)"
                                )
                            else:
                                logger.warning(f"Pi Cycle insufficient data: {pi_cycle_result.get('error')}")
                        else:
                            logger.warning(
                                f"Not enough historical data for Pi Cycle "
                                f"(got {len(pi_cycle_klines) if pi_cycle_klines is not None else 0} days, need 350+)"
                            )
                    except Exception as pi_error:
                        logger.warning(f"Could not calculate Pi Cycle for Bitcoin: {pi_error}")
                        # Pi Cycle is optional, continue without it

                    # 200 Week MA (requires ~1400 days)
                    try:
                        ma_200w_klines = await binance_service.get_klines_by_coin_id(
                            "bitcoin",
                            interval="1d",
                            limit=1500,  # ~1500 days = ~214 weeks
                        )

                        if ma_200w_klines is not None and len(ma_200w_klines) >= 1400:
                            ma_200w = cycle_service.calculate_200_week_ma(ma_200w_klines)

                            if ma_200w:
                                cycle_data["ma_200w"] = ma_200w
                                distance_from_ma = ((current_price - ma_200w) / ma_200w) * 100
                                cycle_data["distance_from_200w_pct"] = distance_from_ma
                                logger.info(
                                    f"Bitcoin 200W MA: ${ma_200w:,.0f} "
                                    f"(current price {distance_from_ma:+.1f}% from floor)"
                                )
                        else:
                            logger.debug("Not enough data for 200 Week MA")
                    except Exception as ma_error:
                        logger.warning(f"Could not calculate 200W MA for Bitcoin: {ma_error}")
                        # 200W MA is optional, continue without it

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

        # 7.1 🕯️ MULTI-TIMEFRAME CANDLES for comprehensive analysis
        # Load candles from multiple timeframes to give AI complete picture:
        # - 1M = macro trend (≈20 months = almost 2 years)
        # - 1w = medium-term trend (≈5 months)
        # - 1d = current context (≈20 days)
        # - 4h = intraday structure
        # - 1h = micro movements
        multi_tf_candles = {}
        timeframes_to_fetch = ['1M', '1w', '1d', '4h', '1h']

        logger.info(f"Fetching multi-timeframe candles for {normalized_id}: {timeframes_to_fetch}")

        for tf in timeframes_to_fetch:
            try:
                tf_klines = await binance_service.get_klines_by_coin_id(
                    normalized_id,
                    interval=tf,
                    limit=20  # 20 candles per timeframe as requested
                )

                if tf_klines is not None and len(tf_klines) >= 20:
                    # Extract OHLCV columns and convert to serializable format
                    candles_df = tf_klines.tail(20)[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()

                    # Convert timestamp to ISO string for JSON serialization
                    candles_df['timestamp'] = candles_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

                    multi_tf_candles[tf] = {
                        "count": len(candles_df),
                        "candles": candles_df.to_dict(orient="records")
                    }
                    logger.info(f"✓ Loaded {len(candles_df)} candles for {tf} timeframe")
                else:
                    logger.warning(f"✗ Insufficient data for {tf} timeframe (got {len(tf_klines) if tf_klines is not None else 0} candles)")

            except Exception as e:
                logger.error(f"Error fetching {tf} candles for {normalized_id}: {e}")
                # Continue with other timeframes even if one fails

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
        indicators = None  # Initialize to prevent UnboundLocalError
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

            # 🕯️ ADD MULTI-TIMEFRAME CANDLES for comprehensive price action analysis
            if multi_tf_candles:
                result["multi_timeframe_candles"] = multi_tf_candles
                result["data_sources"].append("multi_timeframe_candles")

                total_candles = sum(tf_data["count"] for tf_data in multi_tf_candles.values())
                logger.info(
                    f"Technical analysis complete for {normalized_id}: "
                    f"{len(indicators or {})} indicators, "
                    f"{len(patterns.get('patterns_found', []))} patterns, "
                    f"{total_candles} candles across {len(multi_tf_candles)} timeframes {list(multi_tf_candles.keys())}"
                )
            else:
                logger.warning(f"No multi-timeframe candles loaded for {normalized_id}")
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

                        # Extract EMA and ATR from indicators for scenario generation
                        ema_data = None
                        atr = None
                        if indicators:
                            ema_data = {
                                "ema_20": indicators.get("ema_20"),
                                "ema_50": indicators.get("ema_50"),
                                "ema_200": indicators.get("ema_200"),
                            }
                            atr = indicators.get("atr")

                        # Generate scenario-specific price levels
                        scenario_levels = price_levels_service.generate_scenario_levels(
                            current_price=current_price,
                            ath_price=ath_price,
                            atl_price=atl_price,
                            fibonacci_data=fibonacci_data,
                            support_resistance_data=support_resistance_data,
                            ema_data=ema_data,
                            atr=atr
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


def check_tool_access(tool_name: str, user_tier: str) -> tuple[bool, str | None]:
    """
    Check if user's tier has access to a specific tool/feature

    Args:
        tool_name: Name of the tool to check
        user_tier: User's subscription tier (free, basic, premium, vip)

    Returns:
        Tuple of (has_access: bool, reason: str | None)
    """
    from config.limits import has_feature
    from src.database.models import SubscriptionTier

    try:
        tier_enum = SubscriptionTier(user_tier)
    except ValueError:
        tier_enum = SubscriptionTier.FREE

    # Map tools to required features
    # NOTE: get_technical_analysis is available for ALL tiers (FREE gets basic indicators only)
    TOOL_FEATURE_MAP = {
        # "get_technical_analysis" removed - available for FREE (with filtering)
        "get_candlestick_patterns": "candlestick_patterns",  # BASIC+
        "get_funding_rates": "funding_rates",  # BASIC+
        "get_liquidation_history": "liquidations",  # PREMIUM+
        "get_onchain_metrics": "onchain_metrics",  # PREMIUM+
        "get_market_cycle_analysis": "cycle_analysis",  # PREMIUM+
    }

    # Check if tool requires specific feature
    required_feature = TOOL_FEATURE_MAP.get(tool_name)
    if required_feature:
        if not has_feature(tier_enum, required_feature):
            tier_names = {
                "advanced_indicators": "BASIC",
                "candlestick_patterns": "BASIC",
                "funding_rates": "BASIC",
                "liquidations": "PREMIUM",
                "onchain_metrics": "PREMIUM",
                "cycle_analysis": "PREMIUM",
            }
            required_tier = tier_names.get(required_feature, "PREMIUM")
            reason = (
                f"🔒 This feature requires {required_tier}+ subscription. "
                f"Upgrade to unlock advanced analytics!"
            )
            return False, reason

    # All other tools are available for FREE users
    return True, None


async def execute_tool(tool_name: str, arguments: Dict[str, Any], user_tier: str = "free") -> str:
    """
    Execute a tool (function) and return JSON result

    🚨 TIER GATING: Some tools require paid subscription!

    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments as dict or JSON string
        user_tier: User's subscription tier (for feature gating)

    Returns:
        JSON string with result
    """
    try:
        # Import tier utilities
        from config.limits import has_feature
        from src.database.models import SubscriptionTier

        logger.info(f"Executing tool: {tool_name} with args: {arguments}, tier: {user_tier}")

        # Convert user_tier string to enum
        try:
            tier_enum = SubscriptionTier(user_tier)
        except ValueError:
            tier_enum = SubscriptionTier.FREE

        # Check tier access BEFORE executing
        has_access, reason = check_tool_access(tool_name, user_tier)
        if not has_access:
            logger.warning(f"Tool {tool_name} blocked for tier {user_tier}: {reason}")
            return json.dumps(
                {"success": False, "error": reason, "upgrade_required": True},
                ensure_ascii=False
            )

        # Parse JSON if arguments is a string (e.g., from OpenAI API)
        if isinstance(arguments, str):
            arguments = json.loads(arguments)

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

            # 🔒 FREE TIER FILTERING: Only basic indicators (RSI, MACD, EMA)
            # FREE users get limited analysis to keep costs down
            if tier_enum == SubscriptionTier.FREE:
                logger.info(f"Filtering technical analysis for FREE tier user")

                # Keep only basic data for FREE tier
                filtered_result = {
                    "success": result.get("success", True),
                    "coin_id": result.get("coin_id"),
                    "timeframe": result.get("timeframe"),
                    "data_sources": [],
                }

                # ✅ ALLOWED: Basic market data (price, market cap, volume)
                if "extended_data" in result:
                    filtered_result["extended_data"] = result["extended_data"]
                    filtered_result["data_sources"].append("extended_market_data")

                # ✅ ALLOWED: Fear & Greed Index
                if "fear_greed" in result:
                    filtered_result["fear_greed"] = result["fear_greed"]
                    filtered_result["data_sources"].append("fear_greed_index")

                # ✅ ALLOWED: News
                if "news" in result:
                    filtered_result["news"] = result["news"]
                    filtered_result["data_sources"].append("news")

                # ✅ ALLOWED: Basic technical indicators ONLY (RSI, MACD, EMA)
                if "technical_indicators" in result and result["technical_indicators"]:
                    indicators = result["technical_indicators"]
                    filtered_result["technical_indicators"] = {
                        # Basic indicators available in FREE
                        "rsi": indicators.get("rsi"),
                        "macd": indicators.get("macd"),
                        "macd_signal": indicators.get("macd_signal"),
                        "macd_histogram": indicators.get("macd_histogram"),
                        "ema_20": indicators.get("ema_20"),
                        "ema_50": indicators.get("ema_50"),
                        "ema_200": indicators.get("ema_200"),
                    }
                    filtered_result["data_sources"].append("technical_indicators")
                    logger.info("FREE tier: Returning basic indicators (RSI, MACD, EMA)")

                # ❌ BLOCKED: Advanced indicators, patterns, on-chain, etc.
                # Add upgrade message if advanced data was available
                blocked_features = []
                if result.get("candlestick_patterns"):
                    blocked_features.append("Candlestick Patterns")
                if result.get("funding_data"):
                    blocked_features.append("Funding Rates")
                if result.get("long_short_data"):
                    blocked_features.append("Long/Short Ratio")
                if result.get("liquidation_data"):
                    blocked_features.append("Liquidation Data")
                if result.get("onchain_data"):
                    blocked_features.append("On-Chain Metrics")
                if result.get("cycle_data"):
                    blocked_features.append("Cycle Analysis")

                if blocked_features:
                    filtered_result["upgrade_message"] = (
                        f"🔓 Unlock {', '.join(blocked_features)} with BASIC+ subscription!\n\n"
                        "💎 BASIC ($9.99/mo) includes:\n"
                        "   • Candlestick Patterns\n"
                        "   • Funding Rates & Long/Short Ratio\n"
                        "   • All Advanced Indicators\n"
                        "   • 15 requests/day\n\n"
                        "🚀 Try 7-day FREE trial!"
                    )

                result = filtered_result

            # 🔒 PREMIUM FEATURE GATING: Filter Pi Cycle for non-PREMIUM users
            # Pi Cycle Top Indicator requires PREMIUM+ subscription
            if not has_feature(tier_enum, "cycle_analysis"):
                if "cycle_data" in result and result["cycle_data"]:
                    cycle_data = result["cycle_data"]

                    # Keep basic Rainbow Chart data (available for BASIC+)
                    filtered_cycle = {
                        "current_band": cycle_data.get("current_band"),
                        "sentiment": cycle_data.get("sentiment"),
                        "days_since_genesis": cycle_data.get("days_since_genesis"),
                        "bands": cycle_data.get("bands", {}),
                    }

                    # 🔒 Block Pi Cycle Top Indicator (PREMIUM+ only)
                    if "pi_cycle" in cycle_data:
                        filtered_cycle["pi_cycle"] = {
                            "locked": True,
                            "tier_required": "PREMIUM",
                            "message": (
                                "🔒 Pi Cycle Top Indicator requires PREMIUM+ subscription.\n\n"
                                "💎 This indicator has PERFECTLY predicted Bitcoin tops in:\n"
                                "   • 2013 cycle\n"
                                "   • 2017 cycle ($20k top)\n"
                                "   • 2021 cycle ($69k top)\n\n"
                                "⚠️ Median correction after 'top_signal': -50% to -80%\n\n"
                                "Upgrade to PREMIUM to unlock this powerful market timing tool!"
                            ),
                        }

                    # 🔒 Block 200 Week MA (PREMIUM+ only)
                    if "ma_200w" in cycle_data:
                        filtered_cycle["ma_200w_locked"] = True

                    result["cycle_data"] = filtered_cycle

        elif tool_name == "get_coins_by_category":
            result = await get_coins_by_category(**arguments)
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
