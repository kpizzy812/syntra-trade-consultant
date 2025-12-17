# coding: utf-8
"""
Payment API endpoints for Mini App

Handles:
- Telegram Stars invoice creation
- TON Connect payment requests (TON + USDT)
- Payment verification
- Payment history
"""

from typing import Dict, Any
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User, SubscriptionTier
from src.database.engine import get_session
from src.api.auth import get_current_user
from src.database.crud import get_referral_stats
from src.services.telegram_stars_service import TelegramStarsService
from src.services.ton_payment_service import get_ton_payment_service
from src.services.nowpayments_service import get_nowpayments_service
from src.services.posthog_service import track_payment_started
from aiogram import Bot
import os

from loguru import logger

# Create router
router = APIRouter(prefix="/payment", tags=["payment"])

# Initialize payment services
stars_service = TelegramStarsService()
ton_service = get_ton_payment_service(is_testnet=False)  # Production mainnet
nowpayments_service = get_nowpayments_service()


# ===========================
# REQUEST MODELS
# ===========================


class CreateStarsInvoiceRequest(BaseModel):
    """Request to create Telegram Stars invoice"""

    tier: str  # "basic" | "premium" | "vip"
    duration_months: int  # 1, 3, or 12


class CreateTonPaymentRequest(BaseModel):
    """Request to create TON Connect payment"""

    tier: str  # "basic" | "premium" | "vip"
    duration_months: int  # 1, 3, or 12
    currency: str = "usdt"  # "ton" | "usdt"


class CreateNOWPaymentsInvoiceRequest(BaseModel):
    """Request to create NOWPayments invoice"""

    tier: str  # "basic" | "premium" | "vip"
    duration_months: int  # 1, 3, or 12
    pay_currency: str | None = None  # "btc" | "eth" | "usdt" etc, или None для выбора пользователем


class PaymentResponse(BaseModel):
    """Generic payment response"""

    success: bool
    message: str
    error: str | None = None
    data: Dict[str, Any] | None = None


# ===========================
# ENDPOINTS
# ===========================


@router.post("/stars/create-invoice", response_model=PaymentResponse)
async def create_stars_invoice(
    request: CreateStarsInvoiceRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Create Telegram Stars invoice link for Mini App payment

    This endpoint creates an invoice link using Bot API's createInvoiceLink method.
    The frontend will open this link using WebApp.openInvoice() method.

    Args:
        request: Invoice creation request (tier, duration)
        user: Current authenticated user
        session: Database session

    Returns:
        PaymentResponse with invoice URL to open in Mini App
    """
    try:
        # Validate tier
        try:
            tier = SubscriptionTier(request.tier)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tier: {request.tier}. Must be one of: basic, premium, vip",
            )

        # Validate duration
        if request.duration_months not in [1, 3, 12]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid duration: {request.duration_months}. Must be 1, 3, or 12",
            )

        # Get plan details
        plan = stars_service.get_plan_details(tier, request.duration_months)
        if not plan:
            raise HTTPException(
                status_code=400, detail="Invalid subscription plan configuration"
            )

        # Get referral discount for user
        referral_discount_percent = 0
        try:
            referral_stats = await get_referral_stats(session, user.id)
            referral_discount_percent = referral_stats.get('discount_percent', 0)
        except Exception as e:
            logger.warning(f"Failed to get referral discount for user {user.id}: {e}")

        # Calculate final price with referral discount
        original_stars = plan["stars"]
        original_usd = plan["usd"]

        if referral_discount_percent > 0:
            final_stars = int(original_stars * (100 - referral_discount_percent) / 100)
            final_usd = round(original_usd * (100 - referral_discount_percent) / 100, 2)
        else:
            final_stars = original_stars
            final_usd = original_usd

        # Initialize bot (required for creating invoice link)
        bot = Bot(token=os.getenv("BOT_TOKEN", ""))

        try:
            # Create invoice link for Mini App
            # This link can be opened using WebApp.openInvoice(url)
            invoice_url = await stars_service.create_invoice_link(
                bot=bot,
                user_id=user.id,
                tier=tier,
                duration_months=request.duration_months,
                user_language=user.language or "ru",
                referral_discount_percent=referral_discount_percent,
            )

            if not invoice_url:
                raise HTTPException(
                    status_code=500, detail="Failed to create invoice link"
                )

            logger.info(
                f"Stars invoice link created: user={user.id}, tier={tier.value}, "
                f"duration={request.duration_months}m, price={final_stars} Stars "
                f"(original={original_stars}, referral_discount={referral_discount_percent}%)"
            )

            # 📊 Track payment started
            track_payment_started(
                user.id,
                tier.value,
                request.duration_months,
                final_usd,
                "telegram_stars"
            )

            # Return invoice URL for Mini App to open
            return PaymentResponse(
                success=True,
                message="Invoice link created successfully",
                data={
                    "invoice_url": invoice_url,
                    "tier": tier.value,
                    "duration_months": request.duration_months,
                    "price_usd": final_usd,
                    "price_usd_original": original_usd,
                    "price_stars": final_stars,
                    "price_stars_original": original_stars,
                    "discount": plan["discount"],
                    "referral_discount": referral_discount_percent,
                },
            )

        finally:
            await bot.session.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating Stars invoice link: {e}")
        return PaymentResponse(
            success=False, message="Failed to create invoice link", error=str(e)
        )


@router.post("/ton/create-payment", response_model=PaymentResponse)
async def create_ton_payment(
    request: CreateTonPaymentRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Create TON Connect payment request for subscription purchase

    This endpoint creates a payment request and returns deposit details.
    User pays via TON Connect wallet, and backend monitors incoming transactions.

    Supports:
    - Native TON transfers
    - USDT (Jetton) transfers

    Args:
        request: Payment creation request (tier, duration, currency)
        user: Current authenticated user
        session: Database session

    Returns:
        PaymentResponse with deposit address, memo, and amounts
    """
    try:
        # Validate tier
        try:
            tier = SubscriptionTier(request.tier)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tier: {request.tier}. Must be one of: basic, premium, vip",
            )

        # Validate duration
        if request.duration_months not in [1, 3, 12]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid duration: {request.duration_months}. Must be 1, 3, or 12",
            )

        # Validate currency
        if request.currency not in ["ton", "usdt"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid currency: {request.currency}. Must be 'ton' or 'usdt'",
            )

        # Get plan price from Stars service (same pricing)
        plan = stars_service.get_plan_details(tier, request.duration_months)
        if not plan:
            raise HTTPException(
                status_code=400, detail="Invalid subscription plan configuration"
            )

        # Get referral discount for user
        referral_discount_percent = 0
        try:
            referral_stats = await get_referral_stats(session, user.id)
            referral_discount_percent = referral_stats.get('discount_percent', 0)
        except Exception as e:
            logger.warning(f"Failed to get referral discount for user {user.id}: {e}")

        # Calculate final price with referral discount
        original_usd = Decimal(str(plan["usd"]))
        if referral_discount_percent > 0:
            amount_usd = original_usd * (100 - referral_discount_percent) / 100
        else:
            amount_usd = original_usd

        # SECURITY: Validate payment amount
        # Проверка минимальной суммы ($0.50)
        if amount_usd < Decimal("0.50"):
            raise HTTPException(
                status_code=400,
                detail=f"Payment amount too low: ${amount_usd}. Minimum is $0.50"
            )

        # Проверка максимальной суммы ($10,000 для защиты от ошибок)
        if amount_usd > Decimal("10000.00"):
            raise HTTPException(
                status_code=400,
                detail=f"Payment amount too high: ${amount_usd}. Maximum is $10,000"
            )

        # Проверка что сумма положительная
        if amount_usd <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid payment amount: ${amount_usd}. Must be positive"
            )

        # Create TON payment request
        payment_data = await ton_service.create_ton_payment_request(
            session=session,
            user_id=user.id,
            tier=tier,
            duration_months=request.duration_months,
            amount_usd=amount_usd,
        )

        logger.info(
            f"TON payment request created: user={user.id}, tier={tier.value}, "
            f"duration={request.duration_months}m, currency={request.currency}, "
            f"amount=${amount_usd} (original=${original_usd}, referral_discount={referral_discount_percent}%)"
        )

        return PaymentResponse(
            success=True,
            message="Payment request created. Send payment to deposit address with memo.",
            data={
                "payment_id": payment_data["payment_id"],
                "deposit_address": payment_data["deposit_address"],
                "memo": payment_data["memo"],
                "amount_usd": float(payment_data["amount_usd"]),
                "amount_usd_original": float(original_usd),
                "amount_ton": payment_data["amount_ton"],
                "amount_usdt": payment_data["amount_usdt"],
                "currency": request.currency,
                "expires_at": payment_data["expires_at"].isoformat(),
                "tier": tier.value,
                "duration_months": request.duration_months,
                "referral_discount": referral_discount_percent,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating TON payment request: {e}")
        return PaymentResponse(
            success=False, message="Failed to create payment request", error=str(e)
        )


@router.get("/status/{payment_id}")
async def get_payment_status(
    payment_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get payment status (for polling after TON/USDT send)

    This endpoint is called by frontend to check if payment was processed.
    Used for polling mechanism after user sends TON/USDT via TON Connect.

    Args:
        payment_id: Payment database ID (not memo!)
        user: Current authenticated user
        session: Database session

    Returns:
        Payment status, subscription info, and processing details
    """
    try:
        from sqlalchemy import select
        from src.database.models import Payment, Subscription

        # Get payment from database by ID
        result = await session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()

        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        # Verify payment belongs to user
        if payment.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get subscription if payment completed
        subscription_info = None
        if payment.status == "completed":
            result = await session.execute(
                select(Subscription).where(Subscription.user_id == user.id)
            )
            subscription = result.scalar_one_or_none()

            if subscription:
                subscription_info = {
                    "tier": subscription.tier,
                    "is_active": subscription.is_active,
                    "expires_at": subscription.expires_at.isoformat(),
                    "auto_renew": subscription.auto_renew,
                }

        return {
            "success": True,
            "payment": {
                "id": payment.id,
                "status": payment.status,
                "amount": float(payment.amount),
                "currency": payment.currency,
                "provider": payment.provider,
                "tier": payment.tier,
                "duration_months": payment.duration_months,
                "created_at": payment.created_at.isoformat(),
                "completed_at": payment.completed_at.isoformat()
                if payment.completed_at
                else None,
                "metadata": payment.metadata,
            },
            "subscription": subscription_info,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting payment status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get payment status")


# Removed: /verify endpoint (duplicate of /status)
# Use /status/{payment_id} instead for unified payment status checking


@router.get("/history")
async def get_payment_history(
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get user's payment history

    Args:
        limit: Maximum number of payments to return
        user: Current authenticated user
        session: Database session

    Returns:
        List of user's payments
    """
    try:
        from src.database.crud import get_user_payments

        # Get user's payments
        payments = await get_user_payments(session, user.id, limit=limit)

        return {
            "success": True,
            "payments": [
                {
                    "id": payment.id,
                    "status": payment.status,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "provider": payment.provider,
                    "tier": payment.tier,
                    "duration_months": payment.duration_months,
                    "created_at": payment.created_at.isoformat(),
                    "completed_at": payment.completed_at.isoformat()
                    if payment.completed_at
                    else None,
                }
                for payment in payments
            ],
        }

    except Exception as e:
        logger.exception(f"Error getting payment history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get payment history")


@router.post("/nowpayments/create-invoice", response_model=PaymentResponse)
async def create_nowpayments_invoice(
    request: CreateNOWPaymentsInvoiceRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Create NOWPayments invoice for subscription purchase

    User can choose from 300+ cryptocurrencies on the payment page.
    Alternatively, pay_currency can be specified to pre-select currency.

    Args:
        request: Invoice creation request (tier, duration, pay_currency)
        user: Current authenticated user
        session: Database session

    Returns:
        PaymentResponse with invoice URL to open in browser
    """
    try:
        # Validate tier
        try:
            tier = SubscriptionTier(request.tier)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tier: {request.tier}. Must be one of: basic, premium, vip",
            )

        # Validate duration
        if request.duration_months not in [1, 3, 12]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid duration: {request.duration_months}. Must be 1, 3, or 12",
            )

        # Get plan details (используем те же цены что и для Telegram Stars)
        plan = stars_service.get_plan_details(tier, request.duration_months)
        if not plan:
            raise HTTPException(
                status_code=400, detail="Invalid subscription plan configuration"
            )

        # Get referral discount for user
        referral_discount_percent = 0
        try:
            referral_stats = await get_referral_stats(session, user.id)
            referral_discount_percent = referral_stats.get('discount_percent', 0)
        except Exception as e:
            logger.warning(f"Failed to get referral discount for user {user.id}: {e}")

        # Calculate final price with referral discount
        original_usd = Decimal(str(plan["usd"]))
        if referral_discount_percent > 0:
            amount_usd = original_usd * (100 - referral_discount_percent) / 100
        else:
            amount_usd = original_usd

        # Create invoice
        invoice = await nowpayments_service.create_invoice(
            session=session,
            user_id=user.id,
            tier=tier,
            duration_months=request.duration_months,
            amount_usd=amount_usd,
            pay_currency=request.pay_currency,
        )

        if not invoice:
            raise HTTPException(
                status_code=500, detail="Failed to create invoice"
            )

        logger.info(
            f"NOWPayments invoice created: user={user.id}, tier={tier.value}, "
            f"duration={request.duration_months}m, amount=${amount_usd}, "
            f"invoice_id={invoice['invoice_id']}"
        )

        # Track payment started
        track_payment_started(
            user.id,
            tier.value,
            request.duration_months,
            float(amount_usd),
            "nowpayments"
        )

        return PaymentResponse(
            success=True,
            message="Invoice created successfully",
            data={
                "invoice_id": invoice["invoice_id"],
                "invoice_url": invoice["invoice_url"],
                "payment_id": invoice["db_payment_id"],  # For polling status
                "amount_usd": float(amount_usd),
                "amount_usd_original": float(original_usd),
                "tier": tier.value,
                "duration_months": request.duration_months,
                "pay_currency": invoice.get("pay_currency"),
                "discount": plan["discount"],
                "referral_discount": referral_discount_percent,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating NOWPayments invoice: {e}")
        return PaymentResponse(
            success=False,
            message="Failed to create invoice",
            error=str(e)
        )
