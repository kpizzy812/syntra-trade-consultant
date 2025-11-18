"""
FastAPI Router для Telegram Mini App API
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from src.database.crud import get_user_by_telegram_id
from src.database.engine import get_session
from src.database.models import User
from src.api.auth import validate_telegram_init_data, get_current_user
from src.api.dev_auth import get_current_user_dev
from config.config import BOT_TOKEN, ENVIRONMENT

# Import sub-routers
from src.api.chat import router as chat_router
from src.api.analytics import router as analytics_router
from src.api.profile import router as profile_router
from src.api.referral import router as referral_router
from src.api.market import router as market_router
from src.api.payment import router as payment_router


# Создаем главный router
router = APIRouter(tags=["mini-app"])

# Include sub-routers (они уже имеют префиксы)
router.include_router(chat_router)
router.include_router(analytics_router)
router.include_router(profile_router)
router.include_router(referral_router)
router.include_router(market_router)
router.include_router(payment_router)


@router.post("/auth/telegram")
async def authenticate_telegram(
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Authenticate user via Telegram initData

    Headers:
        Authorization: tma <initDataRaw>

    Returns:
        {
            "success": true,
            "user": {
                "id": 1,
                "telegram_id": 123456,
                "username": "john_doe",
                "first_name": "John",
                "language": "ru",
                "is_premium": false,
                "balance": 0
            }
        }

    Errors:
        401: Invalid or expired initData
        404: User not found
    """
    # Проверяем формат
    if not authorization.startswith('tma '):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header"
        )

    init_data_raw = authorization[4:]

    # Валидируем initData
    try:
        init_data = validate_telegram_init_data(init_data_raw, BOT_TOKEN)
    except HTTPException as e:
        return {
            "success": False,
            "error": e.detail
        }

    # Получаем пользователя
    if not init_data.get('user'):
        return {
            "success": False,
            "error": "No user data in init data"
        }

    telegram_id = init_data['user']['id']
    user = await get_user_by_telegram_id(session, telegram_id)

    if not user:
        return {
            "success": False,
            "error": f"User not found (telegram_id: {telegram_id})"
        }

    return {
        "success": True,
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language": user.language,
            "is_premium": user.is_premium,
            "balance": 0,  # TODO: реальный баланс когда будет реализован
        }
    }


@router.get("/user/profile")
async def get_user_profile(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get current user profile

    Requires: Authorization header with valid initData

    Returns:
        {
            "id": 1,
            "telegram_id": 123456,
            "username": "john_doe",
            "first_name": "John",
            "language": "ru",
            "is_premium": false,
            "created_at": "2025-01-18T00:00:00"
        }
    """
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language": user.language,
        "is_premium": user.is_premium,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.get("/analytics/{symbol}")
async def get_analytics(
    symbol: str,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get trading analytics for cryptocurrency symbol

    Args:
        symbol: Cryptocurrency symbol (e.g., BTC, ETH, SOL)

    Returns:
        {
            "symbol": "BTC",
            "price": 45230.50,
            "change_24h": 2.4,
            "volume_24h": 28500000000,
            "indicators": {...}
        }
    """
    # TODO: Интеграция с существующими сервисами
    # from src.services.binance_service import BinanceService
    # from src.services.technical_indicators import TechnicalIndicators

    # Placeholder data
    return {
        "symbol": symbol.upper(),
        "price": 45230.50,
        "change_24h": 2.4,
        "change_7d": 5.2,
        "volume_24h": 28500000000,
        "market_cap": 880000000000,
        "indicators": {
            "rsi": 65.4,
            "macd": {
                "macd": 120.5,
                "signal": 115.2,
                "histogram": 5.3
            }
        }
    }


@router.post("/chat")
async def chat_message(
    message: str,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Send message to AI trading assistant

    Body:
        {
            "message": "What's the trend for BTC?"
        }

    Returns:
        {
            "message": "AI response...",
            "analytics": {...}
        }
    """
    # TODO: Интеграция с OpenAI service
    # from src.services.openai_service import OpenAIService

    # Placeholder response
    return {
        "message": f"AI Assistant received your message: {message}",
        "suggestions": [
            "Check BTC price levels",
            "Analyze market trend",
            "View technical indicators"
        ]
    }


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint (no auth required)
    """
    return {
        "status": "ok",
        "service": "Syntra Mini App API"
    }
