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
from typing import Dict, Any, List, Optional

from src.services.coingecko_service import CoinGeckoService
from src.services.cryptopanic_service import CryptoPanicService
from src.services.binance_service import BinanceService
from src.services.fear_greed_service import FearGreedService
from src.services.technical_indicators import TechnicalIndicators
from src.services.candlestick_patterns import CandlestickPatterns
from src.utils.coin_parser import normalize_coin_name


logger = logging.getLogger(__name__)

# Initialize services
coingecko_service = CoinGeckoService()
cryptopanic_service = CryptoPanicService()
binance_service = BinanceService()
fear_greed_service = FearGreedService()
technical_indicators = TechnicalIndicators()
candlestick_patterns = CandlestickPatterns()


# ============================================================================
# TOOL DEFINITIONS (OpenAI Format)
# ============================================================================

CRYPTO_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_crypto_price",
            "description": (
                "Get current price and market data for a cryptocurrency. "
                "Use this when user asks about price, cost, or 'how much is X'. "
                "Returns: current price (USD), 24h change (%), market cap, volume."
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
                        )
                    }
                },
                "required": ["coin_id"],
                "additionalProperties": False
            }
        }
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
                        )
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of news items to return (1-10). Default: 5",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": ["coin_symbol"],
                "additionalProperties": False
            }
        }
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
                        "maxItems": 3
                    }
                },
                "required": ["coin_ids"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_cryptos",
            "description": (
                "Get top cryptocurrencies by market capitalization. "
                "Use this when user asks about 'top coins', 'market overview', or 'what's trending'. "
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
                        "maximum": 20
                    }
                },
                "required": [],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_overview",
            "description": (
                "Get general crypto market overview with trending news. "
                "Use this when user asks general questions like 'what's happening in crypto', "
                "'market update', or 'crypto news today'. "
                "Returns: trending news and market sentiment."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_technical_analysis",
            "description": (
                "Get comprehensive technical analysis for a cryptocurrency. "
                "Use this when user asks for 'analysis', 'indicators', 'technical analysis', or 'TA'. "
                "Returns: RSI, MACD, EMAs, Bollinger Bands, candlestick patterns, ATH/ATL, "
                "Fear & Greed Index, and extended market metrics. "
                "This is the MOST POWERFUL tool for deep crypto analysis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "coin_id": {
                        "type": "string",
                        "description": (
                            "Cryptocurrency identifier. Use CoinGecko ID format: "
                            "'bitcoin', 'ethereum', 'solana', etc."
                        )
                    },
                    "timeframe": {
                        "type": "string",
                        "description": (
                            "Timeframe for technical indicators. Options: "
                            "'1h' (hourly), '4h' (4 hours), '1d' (daily). "
                            "Default: '4h' for balanced analysis."
                        ),
                        "enum": ["1h", "4h", "1d"],
                        "default": "4h"
                    }
                },
                "required": ["coin_id"],
                "additionalProperties": False
            }
        }
    }
]


# ============================================================================
# TOOL IMPLEMENTATIONS
# ============================================================================

async def get_crypto_price(coin_id: str) -> Dict[str, Any]:
    """
    Get current price and market data for a cryptocurrency

    Args:
        coin_id: CoinGecko coin ID (e.g., 'bitcoin', 'ethereum')

    Returns:
        Dict with price data or error
    """
    try:
        # Normalize coin name
        normalized_id = normalize_coin_name(coin_id) or coin_id.lower()

        # Get comprehensive price data
        price_data = await coingecko_service.get_price(
            normalized_id,
            include_24h_change=True,
            include_market_cap=True,
            include_24h_volume=True
        )

        if not price_data or normalized_id not in price_data:
            return {
                "success": False,
                "error": f"Cryptocurrency '{coin_id}' not found. Check the ID and try again."
            }

        data = price_data[normalized_id]

        # Get coin details for proper name
        coin_details = await coingecko_service.get_coin_data(normalized_id)
        coin_name = coin_details.get('name', normalized_id.title()) if coin_details else normalized_id.title()
        symbol = coin_details.get('symbol', '').upper() if coin_details else ''

        return {
            "success": True,
            "coin_id": normalized_id,
            "name": coin_name,
            "symbol": symbol,
            "price_usd": data.get('usd', 0),
            "change_24h_percent": data.get('usd_24h_change', 0),
            "market_cap_usd": data.get('usd_market_cap', 0),
            "volume_24h_usd": data.get('usd_24h_vol', 0)
        }

    except Exception as e:
        logger.error(f"Error in get_crypto_price for {coin_id}: {e}")
        return {
            "success": False,
            "error": f"Failed to fetch data for {coin_id}: {str(e)}"
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
            coin_symbol.upper(),
            limit=limit
        )

        if not news_items:
            return {
                "success": True,
                "coin_symbol": coin_symbol.upper(),
                "news": [],
                "message": f"No recent news found for {coin_symbol}"
            }

        # Format news
        formatted_news = []
        for item in news_items:
            formatted_news.append({
                "title": item.get('title', 'No title'),
                "source": item.get('source', 'Unknown'),
                "published_at": item.get('published_at', ''),
                "url": item.get('url', ''),
                "votes": item.get('votes', {})
            })

        return {
            "success": True,
            "coin_symbol": coin_symbol.upper(),
            "news": formatted_news,
            "count": len(formatted_news)
        }

    except Exception as e:
        logger.error(f"Error in get_crypto_news for {coin_symbol}: {e}")
        return {
            "success": False,
            "error": f"Failed to fetch news for {coin_symbol}: {str(e)}"
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
            return {
                "success": False,
                "error": "Please provide 2-3 coins to compare"
            }

        # Get data for each coin
        comparison_data = []

        for coin_id in coin_ids:
            price_result = await get_crypto_price(coin_id)
            if price_result.get('success'):
                comparison_data.append(price_result)

        if not comparison_data:
            return {
                "success": False,
                "error": "Failed to fetch data for any of the specified coins"
            }

        return {
            "success": True,
            "coins": comparison_data,
            "count": len(comparison_data)
        }

    except Exception as e:
        logger.error(f"Error in compare_cryptos for {coin_ids}: {e}")
        return {
            "success": False,
            "error": f"Failed to compare cryptos: {str(e)}"
        }


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
            return {
                "success": False,
                "error": "Failed to fetch top cryptocurrencies"
            }

        # Format data
        formatted_coins = []
        for coin in top_coins:
            formatted_coins.append({
                "name": coin.get('name', 'Unknown'),
                "symbol": coin.get('symbol', '').upper(),
                "price_usd": coin.get('current_price', 0),
                "change_24h_percent": coin.get('price_change_percentage_24h', 0),
                "market_cap_usd": coin.get('market_cap', 0),
                "rank": coin.get('market_cap_rank', 0)
            })

        return {
            "success": True,
            "coins": formatted_coins,
            "count": len(formatted_coins)
        }

    except Exception as e:
        logger.error(f"Error in get_top_cryptos: {e}")
        return {
            "success": False,
            "error": f"Failed to fetch top cryptos: {str(e)}"
        }


async def get_market_overview() -> Dict[str, Any]:
    """
    Get general crypto market overview

    Returns:
        Dict with market overview data or error
    """
    try:
        # Get trending news
        news_items = await cryptopanic_service.get_trending_news(limit=10)

        # Format news
        formatted_news = []
        for item in news_items[:5]:  # Top 5 news
            formatted_news.append({
                "title": item.get('title', 'No title'),
                "source": item.get('source', 'Unknown'),
                "currencies": item.get('currencies', [])
            })

        return {
            "success": True,
            "trending_news": formatted_news,
            "news_count": len(formatted_news)
        }

    except Exception as e:
        logger.error(f"Error in get_market_overview: {e}")
        return {
            "success": False,
            "error": f"Failed to fetch market overview: {str(e)}"
        }


async def get_technical_analysis(coin_id: str, timeframe: str = "4h") -> Dict[str, Any]:
    """
    Get comprehensive technical analysis for a cryptocurrency

    Combines:
    - Extended market data (ATH/ATL, price changes, tokenomics)
    - Fear & Greed Index
    - Technical indicators (RSI, MACD, EMAs, Bollinger Bands, etc.)
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

        # 3. Get candlestick data from Binance
        klines_df = await binance_service.get_klines_by_coin_id(
            normalized_id,
            interval=timeframe,
            limit=200  # Need enough data for indicators
        )

        # Initialize result dict
        result = {
            "success": True,
            "coin_id": normalized_id,
            "timeframe": timeframe,
            "extended_data": extended_data or {},
            "fear_greed": fear_greed or {},
            "technical_indicators": {},
            "candlestick_patterns": {},
            "data_sources": []
        }

        # Track what data we got
        if extended_data:
            result["data_sources"].append("extended_market_data")
        if fear_greed:
            result["data_sources"].append("fear_greed_index")

        # 4. Calculate technical indicators (if klines available)
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
            logger.warning(
                f"Insufficient klines data for {normalized_id} on Binance. "
                f"Technical indicators and patterns unavailable."
            )
            result["note"] = (
                f"Coin '{normalized_id}' not available on Binance or insufficient data. "
                f"Only extended market data and Fear & Greed Index provided."
            )

        return result

    except Exception as e:
        logger.exception(f"Error in get_technical_analysis for {coin_id}: {e}")
        return {
            "success": False,
            "error": f"Failed to perform technical analysis for {coin_id}: {str(e)}"
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
            result = {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }

        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Error executing tool {tool_name}: {e}")
        return json.dumps({
            "success": False,
            "error": f"Tool execution failed: {str(e)}"
        }, ensure_ascii=False)
