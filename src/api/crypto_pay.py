# coding: utf-8
"""
API эндпоинты для Crypto Pay (CryptoBot)

Функционал:
- POST /cryptopay/invoice - создать инвойс для оплаты
- GET /cryptopay/invoice/{invoice_id} - проверить статус инвойса
- GET /cryptopay/assets - список поддерживаемых криптовалют
- DELETE /cryptopay/invoice/{invoice_id} - отменить инвойс
- POST /webhook/cryptopay - webhook от CryptoBot (публичный)
"""

import json
import os
from typing import Optional

from aiogram import Bot
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.database.engine import get_session
from src.database.models import User, SubscriptionTier, CryptoInvoice
from src.services.crypto_pay_service import (
    get_crypto_pay_service,
    CryptoPayService,
    CRYPTO_PAY_ASSETS,
)
from src.services.telegram_stars_service import TelegramStarsService
from src.database.crud import get_referral_stats

# Router for authenticated endpoints
router = APIRouter(prefix="/cryptopay", tags=["CryptoPay"])

# Router for public webhook (no prefix)
webhook_router = APIRouter(tags=["CryptoPay Webhook"])

# Stars service for pricing
stars_service = TelegramStarsService()


# ===========================
# REQUEST/RESPONSE MODELS
# ===========================


class CreateCryptoInvoiceRequest(BaseModel):
    """Request to create CryptoBot invoice"""

    tier: str = Field(..., description="Subscription tier: basic, premium, vip")
    duration_months: int = Field(..., description="Duration: 1, 3, or 12 months")
    asset: str = Field(default="USDT", description="Cryptocurrency: USDT, TON, BTC, ETH, etc.")


class CryptoInvoiceResponse(BaseModel):
    """Response with created invoice"""

    success: bool
    message: str
    data: Optional[dict] = None
    error: Optional[str] = None


class SupportedAssetsResponse(BaseModel):
    """List of supported cryptocurrencies"""

    assets: list[str]
    default_asset: str = "USDT"


# ===========================
# ENDPOINTS
# ===========================


@router.post("/invoice", response_model=CryptoInvoiceResponse)
async def create_crypto_invoice(
    request: CreateCryptoInvoiceRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Create CryptoBot invoice for subscription payment

    Args:
        request: Invoice creation request (tier, duration, asset)
        user: Current authenticated user
        session: Database session

    Returns:
        CryptoInvoiceResponse with invoice URL
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

        # Validate asset
        if request.asset not in CRYPTO_PAY_ASSETS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid asset: {request.asset}. Supported: {CRYPTO_PAY_ASSETS}",
            )

        # Get plan price
        plan = stars_service.get_plan_details(tier, request.duration_months)
        if not plan:
            raise HTTPException(status_code=400, detail="Invalid plan configuration")

        # Get referral discount
        referral_discount_percent = 0
        try:
            referral_stats = await get_referral_stats(session, user.id)
            referral_discount_percent = referral_stats.get("discount_percent", 0)
        except Exception as e:
            logger.warning(f"Failed to get referral discount: {e}")

        # Calculate final price
        original_usd = plan["usd"]
        if referral_discount_percent > 0:
            amount_usd = round(original_usd * (100 - referral_discount_percent) / 100, 2)
        else:
            amount_usd = original_usd

        # Create invoice via service
        service = get_crypto_pay_service()
        invoice = await service.create_invoice(
            session=session,
            user=user,
            tier=tier,
            duration_months=request.duration_months,
            amount_usd=amount_usd,
            asset=request.asset,
        )

        if not invoice:
            raise HTTPException(status_code=500, detail="Failed to create invoice")

        logger.info(
            f"CryptoBot invoice created: user={user.id}, tier={tier.value}, "
            f"duration={request.duration_months}m, amount=${amount_usd}, asset={request.asset}"
        )

        return CryptoInvoiceResponse(
            success=True,
            message="Invoice created successfully",
            data={
                "invoice_id": invoice.invoice_id,
                "hash": invoice.hash,
                "amount_usd": invoice.amount_usd,
                "amount_usd_original": original_usd,
                "amount_crypto": invoice.amount_crypto,
                "asset": invoice.asset,
                "tier": invoice.tier,
                "duration_months": invoice.duration_months,
                "bot_invoice_url": invoice.bot_invoice_url,
                "mini_app_invoice_url": invoice.mini_app_invoice_url,
                "web_app_invoice_url": invoice.web_app_invoice_url,
                "status": invoice.status,
                "expires_at": invoice.expires_at.isoformat() if invoice.expires_at else None,
                "referral_discount": referral_discount_percent,
                "plan_discount": plan["discount"],
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating CryptoBot invoice: {e}")
        return CryptoInvoiceResponse(
            success=False, message="Failed to create invoice", error=str(e)
        )


@router.get("/invoice/{invoice_id}", response_model=CryptoInvoiceResponse)
async def check_invoice_status(
    invoice_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Check CryptoBot invoice status

    Auto-processes paid but unprocessed invoices (fallback if webhook failed)

    Args:
        invoice_id: CryptoBot invoice ID
        user: Current authenticated user
        session: Database session

    Returns:
        CryptoInvoiceResponse with current status
    """
    try:
        service = get_crypto_pay_service()

        # Check and update status
        invoice = await service.check_invoice_status(session=session, invoice_id=invoice_id)

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Verify ownership
        if invoice.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Auto-process paid but unprocessed invoices
        if invoice.status == "paid" and not invoice.processed:
            logger.info(f"🔄 Auto-processing paid invoice {invoice_id}")

            bot = Bot(token=os.getenv("BOT_TOKEN", ""))
            try:
                success = await service.process_paid_invoice(
                    session=session,
                    invoice_id=invoice_id,
                    bot=bot,
                )
                if success:
                    logger.info(f"✅ Invoice {invoice_id} auto-processed")
                    await session.refresh(invoice)
            finally:
                await bot.session.close()

        return CryptoInvoiceResponse(
            success=True,
            message="Invoice status retrieved",
            data={
                "invoice_id": invoice.invoice_id,
                "status": invoice.status,
                "amount_usd": invoice.amount_usd,
                "asset": invoice.asset,
                "tier": invoice.tier,
                "duration_months": invoice.duration_months,
                "created_at": invoice.created_at.isoformat(),
                "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
                "processed": invoice.processed,
                "paid_amount": invoice.paid_amount,
                "paid_asset": invoice.paid_asset,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error checking invoice status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/invoice/{invoice_id}", response_model=CryptoInvoiceResponse)
async def cancel_invoice(
    invoice_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Cancel unpaid CryptoBot invoice

    Can only cancel invoices with status 'active'

    Args:
        invoice_id: CryptoBot invoice ID
        user: Current authenticated user
        session: Database session

    Returns:
        CryptoInvoiceResponse with result
    """
    try:
        # Verify ownership
        result = await session.execute(
            select(CryptoInvoice).where(
                CryptoInvoice.invoice_id == invoice_id,
                CryptoInvoice.user_id == user.id,
            )
        )
        invoice = result.scalar_one_or_none()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        service = get_crypto_pay_service()
        success = await service.delete_invoice(session=session, invoice_id=invoice_id)

        if success:
            return CryptoInvoiceResponse(
                success=True, message=f"Invoice {invoice_id} cancelled"
            )
        else:
            return CryptoInvoiceResponse(
                success=False, message="Failed to cancel invoice"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error cancelling invoice: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/assets", response_model=SupportedAssetsResponse)
async def get_supported_assets():
    """
    Get list of supported cryptocurrencies

    Returns:
        SupportedAssetsResponse with asset list
    """
    return SupportedAssetsResponse(assets=CRYPTO_PAY_ASSETS, default_asset="USDT")


@router.get("/invoices")
async def get_user_invoices(
    status: Optional[str] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get user's CryptoBot invoices

    Args:
        status: Filter by status (optional)
        limit: Max results (default 50)
        user: Current authenticated user
        session: Database session

    Returns:
        List of user's invoices
    """
    try:
        query = select(CryptoInvoice).where(CryptoInvoice.user_id == user.id)

        if status:
            query = query.where(CryptoInvoice.status == status)

        query = query.order_by(CryptoInvoice.created_at.desc()).limit(min(limit, 100))

        result = await session.execute(query)
        invoices = result.scalars().all()

        return {
            "success": True,
            "invoices": [
                {
                    "invoice_id": inv.invoice_id,
                    "hash": inv.hash,
                    "amount_usd": inv.amount_usd,
                    "asset": inv.asset,
                    "tier": inv.tier,
                    "duration_months": inv.duration_months,
                    "status": inv.status,
                    "created_at": inv.created_at.isoformat(),
                    "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
                    "bot_invoice_url": inv.bot_invoice_url,
                }
                for inv in invoices
            ],
            "total": len(invoices),
        }

    except Exception as e:
        logger.exception(f"Error getting invoices: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ===========================
# WEBHOOK (PUBLIC)
# ===========================


@webhook_router.post("/webhook/cryptopay")
async def cryptopay_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    crypto_pay_api_signature: Optional[str] = Header(None),
):
    """
    Webhook from CryptoBot for payment notifications

    ⚠️ This endpoint is PUBLIC and must be accessible from internet
    ⚠️ Signature verification is REQUIRED

    Setup in @CryptoBot:
    1. Open @CryptoBot
    2. Go to Crypto Pay → App Settings
    3. Enable Webhooks
    4. URL: https://yourdomain.com/webhook/cryptopay
    """
    try:
        # Get raw body for signature verification
        body = await request.body()

        # 1. Verify signature (CRITICAL!)
        if not crypto_pay_api_signature:
            logger.warning("❌ Webhook without signature")
            raise HTTPException(status_code=400, detail="No signature provided")

        if not CryptoPayService.verify_webhook_signature(crypto_pay_api_signature, body):
            logger.warning("❌ Invalid webhook signature")
            raise HTTPException(status_code=403, detail="Invalid signature")

        logger.info("✅ Webhook signature verified")

        # 2. Verify request_date (replay protection)
        data = json.loads(body)
        request_date = data.get("request_date")

        if not request_date:
            raise HTTPException(status_code=400, detail="No request_date")

        if not CryptoPayService.verify_request_date(request_date, max_age_seconds=300):
            raise HTTPException(status_code=400, detail="Request too old")

        # 3. Parse data
        update_type = data.get("update_type")
        payload = data.get("payload", {})

        logger.info(f"📥 Webhook: type={update_type}, invoice_id={payload.get('invoice_id')}")

        # 4. Process paid invoices
        if update_type == "invoice_paid":
            invoice_id = payload.get("invoice_id")

            if not invoice_id:
                raise HTTPException(status_code=400, detail="Missing invoice_id")

            bot = Bot(token=os.getenv("BOT_TOKEN", ""))

            try:
                service = get_crypto_pay_service()
                success = await service.process_paid_invoice(
                    session=session,
                    invoice_id=invoice_id,
                    bot=bot,
                )

                if success:
                    logger.info(f"✅ Webhook processed: invoice_id={invoice_id}")
                    return {"ok": True, "message": "Invoice processed"}
                else:
                    logger.warning(f"⚠️ Failed to process invoice: {invoice_id}")
                    return {"ok": False, "message": "Processing failed"}

            finally:
                await bot.session.close()

        else:
            logger.info(f"⚠️ Unknown webhook type: {update_type}")
            return {"ok": True, "message": f"Unknown type: {update_type}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"❌ Webhook error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Export both routers
__all__ = ["router", "webhook_router"]
