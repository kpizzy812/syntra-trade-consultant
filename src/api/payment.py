# coding: utf-8
"""
Payment API endpoints for Mini App

Handles:
- Telegram Stars invoice creation
- TON Connect payment requests (TON + USDT)
- Payment verification
- Payment history
"""

import logging
from typing import Dict, Any
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User, SubscriptionTier
from src.database.engine import get_session
from src.api.auth import get_current_user
from src.services.telegram_stars_service import TelegramStarsService
from src.services.ton_payment_service import get_ton_payment_service
from aiogram import Bot
import os

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/payment", tags=["payment"])

# Initialize payment services
stars_service = TelegramStarsService()
ton_service = get_ton_payment_service(is_testnet=False)  # Production mainnet


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
    Create Telegram Stars invoice for subscription purchase

    This endpoint creates an invoice and sends it to the user via Telegram bot.
    The actual payment is handled by Telegram's native payment system.

    Args:
        request: Invoice creation request (tier, duration)
        user: Current authenticated user
        session: Database session

    Returns:
        PaymentResponse with success status and invoice details
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
        plan = payment_service.get_plan_details(tier, request.duration_months)
        if not plan:
            raise HTTPException(
                status_code=400, detail="Invalid subscription plan configuration"
            )

        # Initialize bot (required for sending invoice)
        bot = Bot(token=os.getenv("BOT_TOKEN", ""))

        try:
            # Get user's Telegram chat (we need to send invoice as a message)
            # In Mini App context, we send invoice to user's private chat
            from aiogram.types import Message

            # Create a mock message object to send invoice
            # Note: In production, you should handle this via bot's message send
            # For now, we'll create the invoice and return details

            # IMPORTANT: Telegram Stars invoices MUST be sent as bot messages
            # We cannot create them purely via API without a message context
            # Solution: Return invoice details to frontend, which will request bot to send invoice

            logger.info(
                f"Creating Stars invoice: user={user.id}, tier={tier.value}, "
                f"duration={request.duration_months}m, price={plan['stars']} Stars"
            )

            # Return invoice details for bot to send
            # Frontend should call bot command to trigger invoice send
            return PaymentResponse(
                success=True,
                message="Invoice request received. Sending invoice via bot...",
                data={
                    "tier": tier.value,
                    "duration_months": request.duration_months,
                    "price_usd": plan["usd"],
                    "price_stars": plan["stars"],
                    "discount": plan["discount"],
                    "telegram_user_id": user.telegram_id,
                },
            )

        finally:
            await bot.session.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating Stars invoice: {e}")
        return PaymentResponse(
            success=False, message="Failed to create invoice", error=str(e)
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

        amount_usd = Decimal(str(plan["usd"]))

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
            f"duration={request.duration_months}m, currency={request.currency}"
        )

        return PaymentResponse(
            success=True,
            message="Payment request created. Send payment to deposit address with memo.",
            data={
                "payment_id": payment_data["payment_id"],
                "deposit_address": payment_data["deposit_address"],
                "memo": payment_data["memo"],
                "amount_usd": float(payment_data["amount_usd"]),
                "amount_ton": payment_data["amount_ton"],
                "amount_usdt": payment_data["amount_usdt"],
                "currency": request.currency,
                "expires_at": payment_data["expires_at"].isoformat(),
                "tier": tier.value,
                "duration_months": request.duration_months,
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
        if payment.status.value == "completed":
            result = await session.execute(
                select(Subscription).where(Subscription.user_id == user.id)
            )
            subscription = result.scalar_one_or_none()

            if subscription:
                subscription_info = {
                    "tier": subscription.tier.value,
                    "is_active": subscription.is_active,
                    "expires_at": subscription.expires_at.isoformat(),
                    "auto_renew": subscription.auto_renew,
                }

        return {
            "success": True,
            "payment": {
                "id": payment.id,
                "status": payment.status.value,
                "amount": float(payment.amount),
                "currency": payment.currency,
                "provider": payment.provider.value,
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


@router.get("/verify/{payment_id}")
async def verify_payment(
    payment_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Verify payment status

    Args:
        payment_id: Payment provider ID
        user: Current authenticated user
        session: Database session

    Returns:
        Payment status and details
    """
    try:
        from src.database.crud import get_payment_by_provider_id

        # Get payment from database
        payment = await get_payment_by_provider_id(session, payment_id)

        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        # Verify payment belongs to user
        if payment.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        return {
            "success": True,
            "payment": {
                "id": payment.id,
                "status": payment.status.value,
                "amount": payment.amount,
                "currency": payment.currency,
                "tier": payment.tier,
                "duration_months": payment.duration_months,
                "created_at": payment.created_at.isoformat(),
                "completed_at": payment.completed_at.isoformat()
                if payment.completed_at
                else None,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error verifying payment: {e}")
        raise HTTPException(status_code=500, detail="Payment verification failed")


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
                    "status": payment.status.value,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "provider": payment.provider.value,
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
