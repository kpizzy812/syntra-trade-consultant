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
from src.api.chats import router as chats_router
from src.api.analytics import router as analytics_router
from src.api.profile import router as profile_router
from src.api.referral import router as referral_router
from src.api.market import router as market_router
from src.api.payment import router as payment_router
from src.api.magic_auth import router as magic_auth_router
from src.api.config import router as config_router
from src.api.crypto_pay import router as crypto_pay_router, webhook_router as crypto_pay_webhook_router
from src.api.webhooks_nowpayments import router as nowpayments_webhook_router
from src.api.ads import router as ads_router
from src.api.fraud_admin import router as fraud_admin_router
from src.api.points import router as points_router
from src.api.tasks import router as tasks_router
from src.api.tasks_admin import router as tasks_admin_router
from src.api.startapp_admin import router as startapp_admin_router
from src.api.futures_scenarios import router as futures_scenarios_router
from src.api.futures_signals import router as futures_signals_router
from src.api.supervisor import router as supervisor_router
from src.api.feedback import router as feedback_router


# Создаем главный router
router = APIRouter(tags=["mini-app"])

# Include sub-routers (они уже имеют префиксы)
router.include_router(chat_router)
router.include_router(chats_router)  # Chat management (create, list, delete chats)
router.include_router(analytics_router)
router.include_router(profile_router)
router.include_router(referral_router)
router.include_router(market_router)
router.include_router(payment_router)
router.include_router(magic_auth_router)  # Magic link authentication for web
router.include_router(config_router)  # Public config endpoints (pricing, limits)
router.include_router(crypto_pay_router)  # CryptoBot payment endpoints
router.include_router(crypto_pay_webhook_router)  # CryptoBot webhook (public)
router.include_router(nowpayments_webhook_router)  # NOWPayments webhook (public)
router.include_router(ads_router)  # Ads and promotional banners
router.include_router(fraud_admin_router)  # Fraud detection admin panel
router.include_router(points_router)  # $SYNTRA points system
router.include_router(tasks_router)  # Social tasks for earning points
router.include_router(tasks_admin_router)  # Social tasks admin management
router.include_router(startapp_admin_router)  # Startapp parameter tracking admin
router.include_router(futures_scenarios_router)  # Futures trading scenarios API (API Key auth)
router.include_router(futures_signals_router)  # Futures signals for users (tma/JWT auth)
router.include_router(supervisor_router)  # Syntra Supervisor API
router.include_router(feedback_router)  # Trade feedback and learning API


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

    # Process start_param from Telegram Mini App
    start_param = init_data.get('start_param')

    # Save startapp parameter if it's NOT a referral code
    if start_param and not start_param.startswith('ref_') and not user.startapp_param:
        from loguru import logger
        user.startapp_param = start_param
        await session.commit()
        logger.info(f"[Mini App] Saved startapp parameter '{start_param}' for user {user.id}")

    # Process referral code from start_param (for Telegram Mini App)
    # Format: ref_CODE (e.g., ref_ABC123)
    if start_param and start_param.startswith('ref_'):
        referral_code = start_param[4:]  # Remove "ref_" prefix

        from src.database.crud import create_referral, grant_referee_bonus
        from sqlalchemy import select
        from src.database.models import User as UserModel
        from loguru import logger

        # Find referrer by code
        stmt = select(UserModel).where(UserModel.referral_code == referral_code)
        result = await session.execute(stmt)
        referrer = result.scalar_one_or_none()

        if referrer and referrer.id != user.id:
            # Check if referral already exists (avoid duplicates)
            from src.database.models import Referral
            existing_stmt = select(Referral).where(
                Referral.referrer_id == referrer.id,
                Referral.referee_id == user.id
            )
            existing_result = await session.execute(existing_stmt)
            existing_referral = existing_result.scalar_one_or_none()

            if not existing_referral:
                # Create referral relationship
                try:
                    referral = await create_referral(
                        session,
                        referrer_id=referrer.id,
                        referee_id=user.id,
                        referral_code=referral_code
                    )
                    if referral:
                        logger.info(
                            f"[Mini App] Referral created: {referrer.id} (@{referrer.username}) "
                            f"referred {user.id} (@{user.username})"
                        )

                        # Grant welcome bonus to referee (+15 requests)
                        try:
                            bonus_granted = await grant_referee_bonus(session, referral.id)
                            if bonus_granted:
                                logger.info(f"[Mini App] Welcome bonus granted to referee {user.id}: +15 requests")
                        except Exception as bonus_error:
                            logger.error(f"[Mini App] Error granting welcome bonus: {bonus_error}")

                        await session.commit()
                except Exception as e:
                    logger.error(f"[Mini App] Failed to create referral: {e}")
                    await session.rollback()
            else:
                logger.info(f"[Mini App] Referral already exists for user {user.id}")
        elif referrer and referrer.id == user.id:
            logger.warning(f"[Mini App] User {user.id} tried to use own referral code")
        else:
            logger.warning(f"[Mini App] Invalid referral code: {referral_code}")

    # Build subscription data
    subscription_data = None
    if user.subscription:
        subscription_data = {
            "tier": user.subscription.tier,
            "is_active": user.subscription.is_active,
            "expires_at": user.subscription.expires_at.isoformat() if user.subscription.expires_at else None,
        }
    else:
        # Default FREE tier
        subscription_data = {
            "tier": "free",
            "is_active": True,
            "expires_at": None,
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
            "subscription": subscription_data,
        }
    }


@router.get("/user/profile")
async def get_user_profile(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get current user profile

    Requires: Authorization header with valid initData or JWT token

    Returns:
        {
            "user": {
                "id": 1,
                "telegram_id": 123456,
                "username": "john_doe",
                "first_name": "John",
                "language": "ru",
                "is_premium": false,
                "created_at": "2025-01-18T00:00:00"
            }
        }
    """
    return {
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language": user.language,
            "is_premium": user.is_premium,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
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
