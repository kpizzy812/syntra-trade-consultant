# coding: utf-8
"""
NOWPayments Webhook Handler (IPN Callbacks)

Обрабатывает уведомления от NOWPayments при изменении статуса платежа.

Security:
- Верифицируем HMAC-SHA512 signature от NOWPayments
- Проверяем x-nowpayments-sig header
- Используем raw request body для signature verification

IPN статусы:
- waiting → confirming → confirmed → sending → finished ✅
- failed ❌
- expired ❌
- refunded ❌
- partially_paid ⚠️
"""

from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.engine import get_session
from src.services.nowpayments_service import get_nowpayments_service
from loguru import logger


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/nowpayments")
async def nowpayments_ipn_callback(
    request: Request,
    session: AsyncSession = Depends(get_session),
    x_nowpayments_sig: str | None = Header(None),
):
    """
    IPN Callback от NOWPayments

    Вызывается при изменении статуса платежа:
    - waiting: Ожидание оплаты от клиента
    - confirming: Транзакция обрабатывается на блокчейне
    - confirmed: Подтверждено блокчейном
    - sending: Средства отправляются на ваш кошелек
    - finished: Платеж завершен ✅
    - failed: Ошибка платежа ❌
    - refunded: Средства возвращены ❌
    - expired: Истек срок оплаты (7 дней) ❌
    - partially_paid: Клиент заплатил меньше ⚠️

    Security: Верифицируем HMAC-SHA512 signature

    Args:
        request: FastAPI request object
        session: Database session
        x_nowpayments_sig: Signature header from NOWPayments

    Returns:
        {"status": "ok"} если успешно обработан
    """
    try:
        # Читаем raw body (нужно для signature verification)
        body = await request.body()

        # Парсим JSON
        ipn_data = await request.json()

        logger.info(
            f"📨 NOWPayments IPN: payment_id={ipn_data.get('payment_id')}, "
            f"invoice_id={ipn_data.get('invoice_id')}, "
            f"status={ipn_data.get('payment_status')}"
        )

        # Верифицируем signature (SECURITY!)
        service = get_nowpayments_service()

        if not x_nowpayments_sig:
            logger.error("❌ Missing x-nowpayments-sig header!")
            raise HTTPException(status_code=403, detail="Missing signature header")

        if not service.verify_ipn_signature(body, x_nowpayments_sig):
            logger.error("❌ Invalid IPN signature!")
            raise HTTPException(status_code=403, detail="Invalid signature")

        # Обрабатываем callback
        success = await service.process_ipn_callback(session, ipn_data)

        if success:
            return {"status": "ok"}
        else:
            raise HTTPException(status_code=400, detail="Failed to process IPN")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"❌ Ошибка обработки NOWPayments IPN: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
