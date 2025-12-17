# coding: utf-8
"""
Сервис для работы с Crypto Pay API (CryptoBot)

Функционал:
- Создание инвойсов для оплаты подписки
- Обработка webhook уведомлений от CryptoBot
- Активация подписки после оплаты
- Управление статусами платежей

Документация API: https://help.crypt.bot/crypto-pay-api
"""

import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, UTC
from typing import Optional

from aiocryptopay import AioCryptoPay, Networks
from aiogram import Bot
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import CryptoInvoice, User, Subscription, SubscriptionTier


# =============================================
# CONFIGURATION
# =============================================

# CryptoBot API tokens
CRYPTO_PAY_TOKEN_TESTNET = os.getenv("CRYPTO_PAY_TOKEN_TESTNET", "")
CRYPTO_PAY_TOKEN_MAINNET = os.getenv("CRYPTO_PAY_TOKEN_MAINNET", "")
CRYPTO_PAY_TESTNET = os.getenv("CRYPTO_PAY_TESTNET", "true").lower() == "true"

# Supported cryptocurrencies
CRYPTO_PAY_ASSETS = ["USDT", "TON", "BTC", "ETH", "LTC", "BNB", "TRX", "USDC"]

# Invoice expiration time (30 minutes)
CRYPTO_PAY_INVOICE_EXPIRES_IN = 1800


def get_crypto_pay_token() -> str:
    """Get active CryptoBot API token based on environment"""
    if CRYPTO_PAY_TESTNET:
        return CRYPTO_PAY_TOKEN_TESTNET
    return CRYPTO_PAY_TOKEN_MAINNET


# =============================================
# SERVICE CLASS
# =============================================


class CryptoPayService:
    """
    Сервис для работы с Crypto Pay API

    Использует aiocryptopay для async взаимодействия с API
    """

    def __init__(self):
        """Инициализация AioCryptoPay клиента"""
        token = get_crypto_pay_token()
        if not token:
            logger.warning("⚠️ CRYPTO_PAY_TOKEN не настроен! CryptoBot платежи недоступны.")
            self.client = None
            return

        # Выбираем сеть
        network = Networks.TEST_NET if CRYPTO_PAY_TESTNET else Networks.MAIN_NET

        self.client = AioCryptoPay(token=token, network=network)
        logger.info(f"✅ CryptoPayService инициализирован (network={network.value})")

    async def get_me(self) -> Optional[dict]:
        """Получить информацию о приложении (проверка токена)"""
        if not self.client:
            return None

        try:
            app_info = await self.client.get_me()
            return {
                "app_id": app_info.app_id,
                "name": app_info.name,
                "payment_processing_bot_username": app_info.payment_processing_bot_username,
            }
        except Exception as e:
            logger.error(f"❌ Ошибка при получении информации о приложении: {e}")
            return None

    async def get_exchange_rates(self) -> dict:
        """Получить актуальные курсы обмена"""
        if not self.client:
            return {}

        try:
            rates = await self.client.get_exchange_rates()
            result = {}
            for rate in rates:
                key = f"{rate.source}_{rate.target}"
                result[key] = float(rate.rate)
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка при получении курсов: {e}")
            return {}

    async def create_invoice(
        self,
        session: AsyncSession,
        user: User,
        tier: SubscriptionTier,
        duration_months: int,
        amount_usd: float,
        asset: str = "USDT",
        description: Optional[str] = None,
    ) -> Optional[CryptoInvoice]:
        """
        Создать инвойс для оплаты подписки

        Args:
            session: Database session
            user: User model
            tier: Subscription tier
            duration_months: Subscription duration
            amount_usd: Amount in USD
            asset: Cryptocurrency (default USDT)
            description: Payment description

        Returns:
            CryptoInvoice model or None on error
        """
        if not self.client:
            logger.error("❌ CryptoBot client не инициализирован")
            return None

        try:
            # Validate asset
            if asset not in CRYPTO_PAY_ASSETS:
                raise ValueError(f"Неподдерживаемая валюта: {asset}. Доступны: {CRYPTO_PAY_ASSETS}")

            # Get exchange rate and calculate crypto amount
            rates = await self.get_exchange_rates()
            rate_key = f"{asset}_USD"

            if asset in ["USDT", "USDC"]:
                # Stablecoins ≈ USD
                amount_crypto = amount_usd
            elif rate_key in rates:
                amount_crypto = amount_usd / rates[rate_key]
            else:
                raise ValueError(f"Курс {rate_key} недоступен")

            # Create description
            if not description:
                description = f"Syntra AI {tier.value.capitalize()} - {duration_months}mo (${amount_usd:.2f})"

            # Payload for webhook
            payload_data = {
                "user_id": user.id,
                "telegram_id": user.telegram_id,
                "tier": tier.value,
                "duration_months": duration_months,
                "amount_usd": amount_usd,
            }
            payload = json.dumps(payload_data)

            # Create invoice via CryptoBot API
            invoice = await self.client.create_invoice(
                asset=asset,
                amount=amount_crypto,
                description=description,
                expires_in=CRYPTO_PAY_INVOICE_EXPIRES_IN,
                payload=payload,
                allow_comments=True,
                allow_anonymous=False,
            )

            logger.info(
                f"✅ CryptoBot invoice создан: invoice_id={invoice.invoice_id}, "
                f"amount={amount_crypto:.6f} {asset}, user_id={user.id}"
            )

            # Save to database
            db_invoice = CryptoInvoice(
                user_id=user.id,
                invoice_id=invoice.invoice_id,
                hash=invoice.hash,
                amount_usd=amount_usd,
                asset=asset,
                amount_crypto=amount_crypto,
                tier=tier.value,
                duration_months=duration_months,
                status=invoice.status,
                created_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(seconds=CRYPTO_PAY_INVOICE_EXPIRES_IN),
                bot_invoice_url=invoice.bot_invoice_url,
                mini_app_invoice_url=getattr(invoice, "mini_app_invoice_url", None),
                web_app_invoice_url=getattr(invoice, "web_app_invoice_url", None),
                payload=payload,
                processed=False,
            )

            session.add(db_invoice)
            await session.commit()
            await session.refresh(db_invoice)

            return db_invoice

        except Exception as e:
            logger.exception(f"❌ Ошибка при создании инвойса: {e}")
            await session.rollback()
            return None

    async def check_invoice_status(
        self, session: AsyncSession, invoice_id: int
    ) -> Optional[CryptoInvoice]:
        """
        Проверить статус инвойса и обновить в БД

        Args:
            session: Database session
            invoice_id: CryptoBot invoice ID

        Returns:
            Updated CryptoInvoice or None
        """
        if not self.client:
            return None

        try:
            # Find in database
            result = await session.execute(
                select(CryptoInvoice).where(CryptoInvoice.invoice_id == invoice_id)
            )
            db_invoice = result.scalar_one_or_none()

            if not db_invoice:
                logger.warning(f"⚠️ Invoice {invoice_id} не найден в БД")
                return None

            # Get status from CryptoBot API
            invoices = await self.client.get_invoices(invoice_ids=str(invoice_id))

            if not invoices:
                logger.warning(f"⚠️ Invoice {invoice_id} не найден в CryptoBot API")
                return db_invoice

            api_invoice = invoices[0]

            # Update status if changed
            if db_invoice.status != api_invoice.status:
                logger.info(
                    f"📝 Invoice {invoice_id}: {db_invoice.status} → {api_invoice.status}"
                )
                db_invoice.status = api_invoice.status

                # If paid - save payment data
                if api_invoice.status == "paid" and not db_invoice.paid_at:
                    db_invoice.paid_at = datetime.now(UTC)
                    db_invoice.paid_asset = getattr(api_invoice, "paid_asset", api_invoice.asset)
                    db_invoice.paid_amount = float(
                        getattr(api_invoice, "paid_amount", api_invoice.amount)
                    )
                    if hasattr(api_invoice, "paid_usd_rate"):
                        db_invoice.paid_usd_rate = float(api_invoice.paid_usd_rate)
                    if hasattr(api_invoice, "fee_amount"):
                        db_invoice.fee_amount = float(api_invoice.fee_amount)
                    if hasattr(api_invoice, "fee_asset"):
                        db_invoice.fee_asset = api_invoice.fee_asset
                    if hasattr(api_invoice, "comment"):
                        db_invoice.comment = api_invoice.comment
                    if hasattr(api_invoice, "paid_anonymously"):
                        db_invoice.paid_anonymously = api_invoice.paid_anonymously

                await session.commit()

            return db_invoice

        except Exception as e:
            logger.exception(f"❌ Ошибка при проверке статуса инвойса: {e}")
            return None

    async def process_paid_invoice(
        self,
        session: AsyncSession,
        invoice_id: int,
        bot: Optional[Bot] = None,
    ) -> bool:
        """
        Обработать оплаченный инвойс: активировать подписку

        Args:
            session: Database session
            invoice_id: CryptoBot invoice ID
            bot: Telegram Bot for notifications

        Returns:
            bool: Success
        """
        try:
            # Get invoice
            result = await session.execute(
                select(CryptoInvoice).where(CryptoInvoice.invoice_id == invoice_id)
            )
            db_invoice = result.scalar_one_or_none()

            if not db_invoice:
                logger.error(f"❌ Invoice {invoice_id} не найден")
                return False

            if db_invoice.status != "paid":
                logger.warning(f"⚠️ Invoice {invoice_id} не оплачен (статус: {db_invoice.status})")
                return False

            if db_invoice.processed:
                logger.warning(f"⚠️ Invoice {invoice_id} уже обработан")
                return False

            # Get user
            user_result = await session.execute(
                select(User).where(User.id == db_invoice.user_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                logger.error(f"❌ User {db_invoice.user_id} не найден")
                return False

            # Activate subscription
            tier = SubscriptionTier(db_invoice.tier)
            duration_months = db_invoice.duration_months

            # Get or create subscription
            sub_result = await session.execute(
                select(Subscription).where(Subscription.user_id == user.id)
            )
            subscription = sub_result.scalar_one_or_none()

            now = datetime.now(UTC)
            if subscription:
                # Extend existing subscription
                if subscription.is_active and subscription.expires_at and subscription.expires_at > now:
                    # Add to existing
                    new_expires = subscription.expires_at + timedelta(days=30 * duration_months)
                else:
                    # Start fresh
                    new_expires = now + timedelta(days=30 * duration_months)

                subscription.tier = tier.value
                subscription.is_active = True
                subscription.expires_at = new_expires
                subscription.updated_at = now
            else:
                # Create new subscription
                subscription = Subscription(
                    user_id=user.id,
                    tier=tier.value,
                    started_at=now,
                    expires_at=now + timedelta(days=30 * duration_months),
                    is_active=True,
                    auto_renew=False,
                )
                session.add(subscription)

            # Mark invoice as processed
            db_invoice.processed = True
            await session.commit()

            logger.info(
                f"✅ Подписка активирована: user_id={user.id}, tier={tier.value}, "
                f"duration={duration_months}mo, invoice_id={invoice_id}"
            )

            # Send notification
            if bot and user.telegram_id:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            f"✅ <b>Оплата получена!</b>\n\n"
                            f"💳 Сумма: <b>${db_invoice.amount_usd:.2f}</b>\n"
                            f"🪙 Оплачено: <b>{db_invoice.paid_amount} {db_invoice.paid_asset}</b>\n"
                            f"📊 Тариф: <b>{tier.value.capitalize()}</b>\n"
                            f"⏱ Срок: <b>{duration_months} мес.</b>\n\n"
                            f"Спасибо за покупку! 🚀"
                        ),
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.error(f"⚠️ Ошибка отправки уведомления: {e}")

            return True

        except Exception as e:
            logger.exception(f"❌ Ошибка обработки инвойса: {e}")
            await session.rollback()
            return False

    async def delete_invoice(self, session: AsyncSession, invoice_id: int) -> bool:
        """
        Удалить неоплаченный инвойс

        Args:
            session: Database session
            invoice_id: CryptoBot invoice ID

        Returns:
            bool: Success
        """
        if not self.client:
            return False

        try:
            result = await session.execute(
                select(CryptoInvoice).where(CryptoInvoice.invoice_id == invoice_id)
            )
            db_invoice = result.scalar_one_or_none()

            if not db_invoice:
                return False

            if db_invoice.status == "paid":
                logger.error(f"❌ Нельзя удалить оплаченный инвойс {invoice_id}")
                return False

            # Delete via API
            deleted = await self.client.delete_invoice(invoice_id=invoice_id)

            if deleted:
                db_invoice.status = "cancelled"
                await session.commit()
                logger.info(f"✅ Invoice {invoice_id} удален")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Ошибка удаления инвойса: {e}")
            return False

    @staticmethod
    def verify_webhook_signature(signature: str, body: bytes) -> bool:
        """
        Верифицировать подпись webhook от CryptoBot

        Args:
            signature: Signature from crypto-pay-api-signature header
            body: Raw request body (bytes)

        Returns:
            bool: Is signature valid
        """
        try:
            token = get_crypto_pay_token()
            if not token:
                return False

            # Secret key = SHA256(API_TOKEN)
            secret_key = hashlib.sha256(token.encode()).digest()

            # Calculate HMAC-SHA256
            expected_signature = hmac.new(secret_key, body, hashlib.sha256).hexdigest()

            # Constant-time comparison
            is_valid = hmac.compare_digest(signature, expected_signature)

            if not is_valid:
                logger.warning(f"❌ Invalid webhook signature")

            return is_valid

        except Exception as e:
            logger.error(f"❌ Ошибка верификации подписи: {e}")
            return False

    @staticmethod
    def verify_request_date(request_date: str, max_age_seconds: int = 300) -> bool:
        """
        Проверить что webhook не старше max_age_seconds (защита от replay атак)

        Args:
            request_date: ISO 8601 date string
            max_age_seconds: Max request age (default 5 minutes)

        Returns:
            bool: Is request date valid
        """
        try:
            # Parse date
            if request_date.endswith("Z"):
                request_date = request_date[:-1] + "+00:00"

            req_time = datetime.fromisoformat(request_date)

            if req_time.tzinfo is None:
                req_time = req_time.replace(tzinfo=UTC)

            now = datetime.now(UTC)
            age_seconds = abs((now - req_time).total_seconds())

            if age_seconds > max_age_seconds:
                logger.warning(f"❌ Request too old: {age_seconds:.1f}s (max {max_age_seconds}s)")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка проверки request_date: {e}")
            return False

    async def close(self):
        """Close API connection"""
        if self.client:
            try:
                await self.client.close()
                logger.info("✅ CryptoPayService соединение закрыто")
            except Exception as e:
                logger.error(f"⚠️ Ошибка закрытия соединения: {e}")


# =============================================
# SINGLETON
# =============================================

_crypto_pay_service: Optional[CryptoPayService] = None


def get_crypto_pay_service() -> CryptoPayService:
    """Get global CryptoPayService instance (singleton)"""
    global _crypto_pay_service

    if _crypto_pay_service is None:
        _crypto_pay_service = CryptoPayService()

    return _crypto_pay_service


async def cleanup_crypto_pay_service():
    """Cleanup global service instance (call on shutdown)"""
    global _crypto_pay_service

    if _crypto_pay_service is not None:
        await _crypto_pay_service.close()
        _crypto_pay_service = None
