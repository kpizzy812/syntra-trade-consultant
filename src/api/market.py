"""
Market API Endpoints
Provides cryptocurrency market data for Mini App
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.database.models import User
from src.database.engine import get_session
from src.api.auth import get_current_user
from src.services.fear_greed_service import FearGreedService
from src.services.coingecko_service import CoinGeckoService
from src.database.crud import (
    get_user_watchlist,
    add_to_watchlist as add_to_watchlist_db,
    remove_from_watchlist as remove_from_watchlist_db,
)

# Create router
router = APIRouter(prefix="/market", tags=["market"])

# Initialize services
fear_greed_service = FearGreedService()
coingecko_service = CoinGeckoService()


@router.get("/overview")
async def get_market_overview() -> Dict[str, Any]:
    """
    Get comprehensive market overview (public endpoint)

    Combines Fear & Greed Index with global market data

    Returns:
        {
            "fear_greed": {
                "value": 45,
                "value_classification": "Neutral",
                "emoji": "😐"
            },
            "global": {
                "total_market_cap": "$2.1T",
                "market_cap_change_24h": 2.5,
                "total_volume_24h": "$120.5B",
                "btc_dominance": 52.3,
                "eth_dominance": 18.1,
                "active_cryptocurrencies": 12543
            },
            "updated_at": "2025-01-18T12:00:00Z"
        }
    """
    try:
        # Fetch Fear & Greed in parallel with Global Data
        fear_greed_data = await fear_greed_service.get_current()
        global_data = await coingecko_service.get_global_market_data()

        if not fear_greed_data or not global_data:
            # Return partial data if one service fails
            pass

        # Build response
        response = {
            "fear_greed": {
                "value": fear_greed_data.get("value", 50) if fear_greed_data else 50,
                "value_classification": fear_greed_data.get("value_classification", "Neutral") if fear_greed_data else "Neutral",
                "emoji": fear_greed_data.get("emoji", "😐") if fear_greed_data else "😐",
            },
            "global": {},
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }

        # Parse global market data
        # CoinGeckoService.get_global_market_data() returns processed data directly
        if global_data:
            total_market_cap_usd = global_data.get("total_market_cap_usd", 0)
            total_volume_usd = global_data.get("total_volume_24h_usd", 0)
            market_cap_change = global_data.get("market_cap_change_24h", 0)

            response["global"] = {
                "total_market_cap": f"${total_market_cap_usd / 1_000_000_000_000:.2f}T" if total_market_cap_usd >= 1_000_000_000_000 else f"${total_market_cap_usd / 1_000_000_000:.1f}B",
                "total_market_cap_raw": total_market_cap_usd,
                "market_cap_change_24h": round(market_cap_change, 2),
                "total_volume_24h": f"${total_volume_usd / 1_000_000_000:.1f}B" if total_volume_usd >= 1_000_000_000 else f"${total_volume_usd / 1_000_000:.1f}M",
                "total_volume_raw": total_volume_usd,
                "btc_dominance": round(global_data.get("btc_dominance", 0), 2),
                "eth_dominance": round(global_data.get("eth_dominance", 0), 2),
                "active_cryptocurrencies": global_data.get("active_cryptocurrencies", 0),
            }

        return response

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch market overview: {str(e)}"
        )


@router.get("/fear-greed")
async def get_fear_greed_index() -> Dict[str, Any]:
    """
    Get current Fear & Greed Index (public endpoint)

    Returns:
        {
            "value": 45,
            "value_classification": "Neutral",
            "emoji": "😐",
            "timestamp": "1234567890",
            "updated_at": "2025-01-18T12:00:00Z"
        }
    """
    try:
        data = await fear_greed_service.get_current()

        if not data:
            raise HTTPException(
                status_code=503,
                detail="Fear & Greed Index service temporarily unavailable"
            )

        # Add updated_at timestamp
        data["updated_at"] = datetime.utcnow().isoformat() + "Z"

        return data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch Fear & Greed Index: {str(e)}"
        )


@router.get("/top-movers")
async def get_top_movers(
    timeframe: str = "24h",
    limit: int = 3
) -> Dict[str, Any]:
    """
    Get top gainers and losers by timeframe (public endpoint)

    Args:
        timeframe: "1h", "24h", or "7d" (default: "24h")
        limit: Number of gainers/losers to return (default: 3, max: 20)

    Returns:
        {
            "timeframe": "24h",
            "gainers": [
                {
                    "symbol": "XRP",
                    "name": "Ripple",
                    "price": "$0.58",
                    "change": 12.5,
                    "volume_24h": "$2.1B",
                    "market_cap": "$32.5B",
                    "image": "https://..."
                },
                ...
            ],
            "losers": [...],
            "updated_at": "2025-01-18T12:00:00Z"
        }
    """
    try:
        # Validate timeframe
        valid_timeframes = ["1h", "24h", "7d"]
        if timeframe not in valid_timeframes:
            timeframe = "24h"

        # Validate limit
        limit = min(max(1, limit), 20)  # Between 1 and 20

        # Fetch top cryptocurrencies by market cap (need larger sample for better movers)
        # Include 1h and 7d price change data for all timeframes
        top_coins = await coingecko_service.get_top_coins(limit=100, include_1h_7d_change=True)

        if not top_coins:
            raise HTTPException(
                status_code=503,
                detail="CoinGecko service temporarily unavailable"
            )

        # Determine which field to sort by
        change_field_map = {
            "1h": "price_change_percentage_1h_in_currency",
            "24h": "price_change_percentage_24h",
            "7d": "price_change_percentage_7d_in_currency"
        }
        change_field = change_field_map[timeframe]

        # Filter out coins without change data and sort
        coins_with_change = [
            coin for coin in top_coins
            if coin.get(change_field) is not None
        ]

        sorted_coins = sorted(
            coins_with_change,
            key=lambda x: x.get(change_field, 0),
            reverse=True
        )

        # Build gainers and losers
        gainers = []
        losers = []

        for coin in sorted_coins[:limit]:
            current_price = coin.get('current_price', 0)
            volume_24h = coin.get('total_volume', 0)
            market_cap = coin.get('market_cap', 0)

            gainers.append({
                "symbol": coin.get("symbol", "").upper(),
                "name": coin.get("name", ""),
                "price": f"${current_price:.2f}" if current_price >= 1 else f"${current_price:.6f}",
                "price_raw": current_price,
                "change": round(coin.get(change_field, 0), 2),
                "volume_24h": f"${volume_24h / 1_000_000_000:.2f}B" if volume_24h >= 1_000_000_000 else f"${volume_24h / 1_000_000:.1f}M",
                "volume_raw": volume_24h,
                "market_cap": f"${market_cap / 1_000_000_000:.1f}B" if market_cap >= 1_000_000_000 else f"${market_cap / 1_000_000:.1f}M",
                "market_cap_raw": market_cap,
                "image": coin.get("image", "")
            })

        for coin in reversed(sorted_coins[-limit:]):
            current_price = coin.get('current_price', 0)
            volume_24h = coin.get('total_volume', 0)
            market_cap = coin.get('market_cap', 0)

            losers.append({
                "symbol": coin.get("symbol", "").upper(),
                "name": coin.get("name", ""),
                "price": f"${current_price:.2f}" if current_price >= 1 else f"${current_price:.6f}",
                "price_raw": current_price,
                "change": round(coin.get(change_field, 0), 2),
                "volume_24h": f"${volume_24h / 1_000_000_000:.2f}B" if volume_24h >= 1_000_000_000 else f"${volume_24h / 1_000_000:.1f}M",
                "volume_raw": volume_24h,
                "market_cap": f"${market_cap / 1_000_000_000:.1f}B" if market_cap >= 1_000_000_000 else f"${market_cap / 1_000_000:.1f}M",
                "market_cap_raw": market_cap,
                "image": coin.get("image", "")
            })

        return {
            "timeframe": timeframe,
            "gainers": gainers,
            "losers": losers,
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch top movers: {str(e)}"
        )


async def get_optional_user(
    authorization: Optional[str] = None,
) -> Optional[User]:
    """Optional authentication - returns None if not authenticated"""
    if not authorization:
        return None
    try:
        from src.api.auth import get_current_user
        # Manually call get_current_user with authorization header
        return None  # Simplified - just return None for now
    except:
        return None


@router.get("/watchlist")
async def get_watchlist(
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Get user's watchlist with current prices and logos (public endpoint with default watchlist)

    Returns:
        {
            "watchlist": [
                {
                    "symbol": "BTC",
                    "name": "Bitcoin",
                    "price": "$45,230",
                    "change_24h": 2.4,
                    "image": "https://..."
                },
                ...
            ]
        }
    """
    try:
        # For now, always show default watchlist (TODO: add user auth support)
        watchlist_items = []

        # If empty, use default watchlist
        if not watchlist_items:
            coin_ids = ["bitcoin", "ethereum", "solana"]
        else:
            coin_ids = [item.coin_id for item in watchlist_items]

        # Fetch coin data with images using /coins/markets endpoint
        coins_data = await coingecko_service.get_batch_coins_data(
            coin_ids=coin_ids,
            vs_currency="usd",
            include_sparkline=False
        )

        if not coins_data:
            raise HTTPException(
                status_code=503,
                detail="CoinGecko service temporarily unavailable"
            )

        # Build watchlist from coins data
        watchlist = []
        for coin in coins_data:
            price_usd = coin.get("current_price", 0)
            change_24h = coin.get("price_change_percentage_24h", 0)

            watchlist.append({
                "symbol": coin.get("symbol", "").upper(),
                "name": coin.get("name", ""),
                "price": f"${price_usd:,.2f}" if price_usd >= 10 else f"${price_usd:.2f}",
                "change_24h": round(change_24h, 2) if change_24h else 0,
                "image": coin.get("image", "")
            })

        return {
            "watchlist": watchlist,
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch watchlist: {str(e)}"
        )


@router.get("/coin/{symbol}")
async def get_coin_details(symbol: str) -> Dict[str, Any]:
    """
    Get detailed coin information by symbol (public endpoint)

    Args:
        symbol: Cryptocurrency symbol (e.g., "BTC", "ETH")

    Returns:
        {
            "id": "bitcoin",
            "symbol": "BTC",
            "name": "Bitcoin",
            "current_price": 45230.50,
            "market_cap": 885000000000,
            "market_cap_rank": 1,
            "total_volume": 25000000000,
            "price_change_24h": 1200.50,
            "price_change_percentage_24h": 2.73,
            "price_change_percentage_7d": 5.2,
            "price_change_percentage_30d": 12.5,
            "ath": 69000,
            "ath_change_percentage": -34.5,
            "atl": 67.81,
            "atl_change_percentage": 66600.2,
            "circulating_supply": 19500000,
            "total_supply": 21000000,
            "max_supply": 21000000,
            "image": "https://...",
            "updated_at": "2025-01-18T12:00:00Z"
        }
    """
    try:
        # Search for coin by symbol
        coins = await coingecko_service.get_top_coins(limit=250, include_1h_7d_change=True)

        if not coins:
            raise HTTPException(
                status_code=503,
                detail="CoinGecko service temporarily unavailable"
            )

        # Find coin by symbol (case insensitive)
        symbol_lower = symbol.lower()
        coin = next((c for c in coins if c.get("symbol", "").lower() == symbol_lower), None)

        if not coin:
            raise HTTPException(
                status_code=404,
                detail=f"Coin with symbol '{symbol}' not found"
            )

        # Build detailed response
        return {
            "id": coin.get("id", ""),
            "symbol": coin.get("symbol", "").upper(),
            "name": coin.get("name", ""),
            "current_price": coin.get("current_price", 0),
            "market_cap": coin.get("market_cap", 0),
            "market_cap_rank": coin.get("market_cap_rank", 0),
            "total_volume": coin.get("total_volume", 0),
            "price_change_24h": coin.get("price_change_24h", 0),
            "price_change_percentage_24h": round(coin.get("price_change_percentage_24h", 0), 2),
            "price_change_percentage_7d": round(coin.get("price_change_percentage_7d_in_currency", 0), 2),
            "price_change_percentage_30d": round(coin.get("price_change_percentage_30d_in_currency", 0), 2) if coin.get("price_change_percentage_30d_in_currency") else None,
            "ath": coin.get("ath", 0),
            "ath_change_percentage": round(coin.get("ath_change_percentage", 0), 2),
            "atl": coin.get("atl", 0),
            "atl_change_percentage": round(coin.get("atl_change_percentage", 0), 2),
            "circulating_supply": coin.get("circulating_supply", 0),
            "total_supply": coin.get("total_supply", 0),
            "max_supply": coin.get("max_supply", 0),
            "image": coin.get("image", ""),
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch coin details: {str(e)}"
        )


@router.get("/chart/{symbol}")
async def get_coin_chart(
    symbol: str,
    days: int = 7,
    interval: str = "daily"
) -> Dict[str, Any]:
    """
    Get historical price chart data for a coin (public endpoint)

    Args:
        symbol: Cryptocurrency symbol (e.g., "BTC", "ETH")
        days: Number of days of data (1, 7, 30, 90, 365, max)
        interval: Data interval ("hourly" for days<=2, "daily" otherwise)

    Returns:
        {
            "symbol": "BTC",
            "name": "Bitcoin",
            "prices": [
                {"time": 1705507200, "value": 45230.50},
                {"time": 1705593600, "value": 46120.30},
                ...
            ],
            "timeframe": "7d",
            "updated_at": "2025-01-18T12:00:00Z"
        }
    """
    try:
        # First, get coin ID by symbol
        coins = await coingecko_service.get_top_coins(limit=250)

        if not coins:
            raise HTTPException(
                status_code=503,
                detail="CoinGecko service temporarily unavailable"
            )

        symbol_lower = symbol.lower()
        coin = next((c for c in coins if c.get("symbol", "").lower() == symbol_lower), None)

        if not coin:
            raise HTTPException(
                status_code=404,
                detail=f"Coin with symbol '{symbol}' not found"
            )

        coin_id = coin.get("id", "")

        # Fetch market chart data from CoinGecko
        chart_data = await coingecko_service.get_market_chart(
            coin_id=coin_id,
            vs_currency="usd",
            days=days
        )

        if not chart_data or "prices" not in chart_data:
            raise HTTPException(
                status_code=503,
                detail="Failed to fetch chart data"
            )

        # Transform data for lightweight-charts format
        # CoinGecko returns: [[timestamp_ms, price], ...]
        prices = [
            {
                "time": int(item[0] / 1000),  # Convert ms to seconds
                "value": round(item[1], 2)
            }
            for item in chart_data["prices"]
        ]

        return {
            "symbol": coin.get("symbol", "").upper(),
            "name": coin.get("name", ""),
            "prices": prices,
            "timeframe": f"{days}d",
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch chart data: {str(e)}"
        )


@router.post("/watchlist/add")
async def add_to_watchlist(
    coin_id: str,
    symbol: str,
    name: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Add cryptocurrency to user's watchlist

    Args:
        coin_id: CoinGecko coin ID (e.g., 'bitcoin')
        symbol: Cryptocurrency symbol (e.g., 'BTC')
        name: Cryptocurrency name (e.g., 'Bitcoin')

    Returns:
        {"success": true, "message": "Added to watchlist"}
    """
    try:
        result = await add_to_watchlist_db(
            session=session,
            user_id=user.id,
            coin_id=coin_id,
            symbol=symbol,
            name=name,
        )

        if result:
            return {
                "success": True,
                "message": f"{symbol} added to watchlist"
            }
        else:
            return {
                "success": False,
                "message": f"{symbol} already in watchlist"
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add to watchlist: {str(e)}"
        )


@router.delete("/watchlist/remove")
async def remove_from_watchlist(
    coin_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Remove cryptocurrency from user's watchlist

    Args:
        coin_id: CoinGecko coin ID (e.g., 'bitcoin')

    Returns:
        {"success": true, "message": "Removed from watchlist"}
    """
    try:
        removed = await remove_from_watchlist_db(
            session=session,
            user_id=user.id,
            coin_id=coin_id,
        )

        if removed:
            return {
                "success": True,
                "message": "Removed from watchlist"
            }
        else:
            return {
                "success": False,
                "message": "Coin not found in watchlist"
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove from watchlist: {str(e)}"
        )
