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
async def get_top_movers() -> Dict[str, Any]:
    """
    Get top gainers and losers (24h change) (public endpoint)

    Returns:
        {
            "gainers": [
                {"symbol": "XRP", "name": "Ripple", "price": 0.58, "change_24h": 12.5},
                ...
            ],
            "losers": [
                {"symbol": "DOGE", "name": "Dogecoin", "price": 0.082, "change_24h": -8.2},
                ...
            ]
        }
    """
    try:
        # Fetch top cryptocurrencies by market cap
        top_coins = await coingecko_service.get_top_coins(limit=50)

        if not top_coins:
            raise HTTPException(
                status_code=503,
                detail="CoinGecko service temporarily unavailable"
            )

        # Sort by 24h change
        sorted_coins = sorted(
            top_coins,
            key=lambda x: x.get("price_change_percentage_24h", 0),
            reverse=True
        )

        # Get top 3 gainers and losers
        gainers = []
        losers = []

        for coin in sorted_coins[:3]:
            gainers.append({
                "symbol": coin.get("symbol", "").upper(),
                "name": coin.get("name", ""),
                "price": f"${coin.get('current_price', 0):.2f}" if coin.get('current_price', 0) >= 1 else f"${coin.get('current_price', 0):.6f}",
                "change_24h": round(coin.get("price_change_percentage_24h", 0), 2)
            })

        for coin in reversed(sorted_coins[-3:]):
            losers.append({
                "symbol": coin.get("symbol", "").upper(),
                "name": coin.get("name", ""),
                "price": f"${coin.get('current_price', 0):.2f}" if coin.get('current_price', 0) >= 1 else f"${coin.get('current_price', 0):.6f}",
                "change_24h": round(coin.get("price_change_percentage_24h", 0), 2)
            })

        return {
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
    Get user's watchlist with current prices (public endpoint with default watchlist)

    Returns:
        {
            "watchlist": [
                {
                    "symbol": "BTC",
                    "name": "Bitcoin",
                    "price": "$45,230",
                    "change_24h": 2.4
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
            coin_ids_str = "bitcoin,ethereum,solana"
        else:
            coin_ids_str = ",".join([item.coin_id for item in watchlist_items])

        # Fetch current prices
        prices = await coingecko_service.get_price(
            coin_id=coin_ids_str,
            vs_currency="usd",
            include_24h_change=True
        )

        if not prices:
            raise HTTPException(
                status_code=503,
                detail="CoinGecko service temporarily unavailable"
            )

        watchlist = []

        # If using default coins (user has no saved watchlist)
        if not watchlist_items:
            symbol_map = {
                "bitcoin": {"symbol": "BTC", "name": "Bitcoin"},
                "ethereum": {"symbol": "ETH", "name": "Ethereum"},
                "solana": {"symbol": "SOL", "name": "Solana"}
            }
            for coin_id in ["bitcoin", "ethereum", "solana"]:
                if coin_id in prices:
                    price_data = prices[coin_id]
                    price_usd = price_data.get("usd", 0)
                    change_24h = price_data.get("usd_24h_change", 0)

                    watchlist.append({
                        "symbol": symbol_map[coin_id]["symbol"],
                        "name": symbol_map[coin_id]["name"],
                        "price": f"${price_usd:,.2f}" if price_usd >= 10 else f"${price_usd:.2f}",
                        "change_24h": round(change_24h, 2)
                    })
        else:
            # Use user's saved watchlist
            for item in watchlist_items:
                if item.coin_id in prices:
                    price_data = prices[item.coin_id]
                    price_usd = price_data.get("usd", 0)
                    change_24h = price_data.get("usd_24h_change", 0)

                    watchlist.append({
                        "symbol": item.symbol,
                        "name": item.name,
                        "price": f"${price_usd:,.2f}" if price_usd >= 10 else f"${price_usd:.2f}",
                        "change_24h": round(change_24h, 2)
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
