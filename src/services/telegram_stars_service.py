# coding: utf-8
"""
Telegram Stars Payment Service

Handles Telegram Stars payments for premium subscriptions using Telegram's built-in payment system.

Features:
- Invoice creation for subscription plans
- Pre-checkout validation
- Payment processing
- Refund handling (within 3 weeks)
- Transaction logging

Documentation:
- https://core.telegram.org/bots/payments-stars
- https://docs.aiogram.dev/en/latest/api/methods/send_invoice.html
"""
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, UTC

from aiogram import Bot
from aiogram.types import LabeledPrice, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import SubscriptionTier, PaymentProvider, PaymentStatus
from src.database.crud import (
    create_payment,
    get_payment_by_provider_id,
    update_payment_status,
    activate_subscription,
    complete_payment,
)


logger = logging.getLogger(__name__)


# Telegram Stars pricing configuration
# 1 Star ≈ $0.013 USD (as of 2024-2025)
STAR_TO_USD = 0.013
USD_TO_STAR = 1 / STAR_TO_USD  # ~76.9 Stars per $1


# Subscription plans with Stars pricing
SUBSCRIPTION_PLANS = {
    SubscriptionTier.BASIC: {
        "1": {"usd": 4.99, "stars": 384, "discount": 0},  # Monthly
        "3": {"usd": 12.72, "stars": 978, "discount": 15},  # Quarterly (-15%)
        "12": {"usd": 44.91, "stars": 3453, "discount": 25},  # Yearly (-25%)
    },
    SubscriptionTier.PREMIUM: {
        "1": {"usd": 24.99, "stars": 1923, "discount": 0},
        "3": {"usd": 63.72, "stars": 4899, "discount": 15},
        "12": {"usd": 224.91, "stars": 17298, "discount": 25},
    },
    SubscriptionTier.VIP: {
        "1": {"usd": 49.99, "stars": 3845, "discount": 0},
        "3": {"usd": 127.47, "stars": 9802, "discount": 15},
        "12": {"usd": 449.91, "stars": 34597, "discount": 25},
    },
}


class TelegramStarsService:
    """
    Service for handling Telegram Stars payments

    Implements full payment flow:
    1. Create invoice
    2. Validate pre-checkout
    3. Process successful payment
    4. Handle refunds

    Usage:
        service = TelegramStarsService()
        await service.create_subscription_invoice(
            message, user_id, tier="premium", duration_months=1
        )
    """

    def __init__(self):
        """Initialize Telegram Stars service"""
        self.provider = PaymentProvider.TELEGRAM_STARS

    def get_plan_details(
        self, tier: SubscriptionTier, duration_months: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get subscription plan details

        Args:
            tier: Subscription tier (BASIC, PREMIUM, VIP)
            duration_months: Duration in months (1, 3, 12)

        Returns:
            Dict with plan details or None if invalid
        """
        if tier not in SUBSCRIPTION_PLANS:
            return None

        duration_str = str(duration_months)
        if duration_str not in SUBSCRIPTION_PLANS[tier]:
            return None

        plan = SUBSCRIPTION_PLANS[tier][duration_str].copy()
        plan["tier"] = tier
        plan["duration_months"] = duration_months

        return plan

    def generate_payment_payload(
        self, user_id: int, tier: SubscriptionTier, duration_months: int
    ) -> str:
        """
        Generate unique payment payload for identification

        Args:
            user_id: User's database ID
            tier: Subscription tier
            duration_months: Duration in months

        Returns:
            Payload string (max 128 bytes)
        """
        # Format: "sub_{user_id}_{tier}_{months}_{timestamp}"
        timestamp = int(datetime.now(UTC).timestamp())
        payload = f"sub_{user_id}_{tier.value}_{duration_months}_{timestamp}"

        # Ensure payload is within 128 bytes limit
        if len(payload.encode("utf-8")) > 128:
            # Fallback to shorter format if needed
            payload = f"sub_{user_id}_{tier.value}_{duration_months}"

        return payload

    async def create_subscription_invoice(
        self,
        message: Message,
        user_id: int,
        tier: SubscriptionTier,
        duration_months: int,
        user_language: str = "ru",
    ) -> bool:
        """
        Create and send invoice for subscription purchase

        IMPORTANT:
        - currency MUST be "XTR" for Telegram Stars
        - provider_token MUST be empty string
        - prices MUST contain ONLY ONE LabeledPrice
        - amount is specified DIRECTLY in Stars (not in cents!)

        Args:
            message: Telegram message to reply to
            user_id: User's database ID
            tier: Subscription tier
            duration_months: Duration (1, 3, or 12 months)
            user_language: User's language code

        Returns:
            True if invoice sent successfully
        """
        try:
            # Get plan details
            plan = self.get_plan_details(tier, duration_months)
            if not plan:
                logger.error(f"Invalid plan: tier={tier}, duration={duration_months}")
                return False

            # Generate unique payload
            payload = self.generate_payment_payload(user_id, tier, duration_months)

            # Prepare invoice data
            tier_names = {
                SubscriptionTier.BASIC: "BASIC" if user_language == "en" else "БАЗОВЫЙ",
                SubscriptionTier.PREMIUM: "PREMIUM" if user_language == "en" else "ПРЕМИУМ",
                SubscriptionTier.VIP: "VIP",
            }

            duration_names = {
                1: "1 month" if user_language == "en" else "1 месяц",
                3: "3 months" if user_language == "en" else "3 месяца",
                12: "1 year" if user_language == "en" else "1 год",
            }

            title = f"Syntra {tier_names[tier]} - {duration_names[duration_months]}"

            # Build description
            if user_language == "ru":
                description = (
                    f"Подписка {tier_names[tier]} на {duration_names[duration_months]}\n"
                    f"💫 Цена: {plan['stars']} Stars"
                )
                if plan["discount"] > 0:
                    description += f"\n🎁 Скидка: {plan['discount']}%"
            else:
                description = (
                    f"{tier_names[tier]} subscription for {duration_names[duration_months]}\n"
                    f"💫 Price: {plan['stars']} Stars"
                )
                if plan["discount"] > 0:
                    description += f"\n🎁 Discount: {plan['discount']}%"

            # Create invoice
            # CRITICAL: For Telegram Stars:
            # - currency MUST be "XTR"
            # - provider_token MUST be empty string ""
            # - prices MUST have ONLY ONE element
            # - amount is in Stars directly (not cents!)
            await message.answer_invoice(
                title=title,
                description=description,
                prices=[
                    LabeledPrice(
                        label=tier_names[tier],
                        amount=plan["stars"],  # Direct Stars amount!
                    )
                ],
                payload=payload,
                currency="XTR",  # Telegram Stars currency code
                provider_token="",  # MUST be empty for Stars!
                photo_url="https://i.ibb.co/ymkfW6vP/SYNTRABOT.png",
            )

            logger.info(
                f"Invoice created: user={user_id}, tier={tier.value}, "
                f"duration={duration_months}, stars={plan['stars']}, payload={payload}"
            )

            return True

        except TelegramBadRequest as e:
            logger.error(f"Failed to create invoice: {e}")
            return False
        except Exception as e:
            logger.exception(f"Error creating invoice: {e}")
            return False

    async def validate_pre_checkout(
        self,
        user_id: int,
        payload: str,
        total_amount: int,
        session: AsyncSession,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate pre-checkout query

        CRITICAL: Must respond within 10 seconds!

        Args:
            user_id: User's database ID
            payload: Payment payload from invoice
            total_amount: Total amount in Stars
            session: Database session

        Returns:
            Tuple of (is_valid, error_message)
            - (True, None) if valid
            - (False, "error message") if invalid
        """
        try:
            # Parse payload: "sub_{user_id}_{tier}_{months}_{timestamp}"
            parts = payload.split("_")
            if len(parts) < 4 or parts[0] != "sub":
                return False, "Invalid payment payload"

            payload_user_id = int(parts[1])
            tier_value = parts[2]
            duration_months = int(parts[3])

            # Verify user ID matches
            if payload_user_id != user_id:
                logger.warning(
                    f"User ID mismatch: payload={payload_user_id}, actual={user_id}"
                )
                return False, "Invalid user"

            # Verify tier is valid
            try:
                tier = SubscriptionTier(tier_value)
            except ValueError:
                return False, "Invalid subscription tier"

            # Verify amount matches plan
            plan = self.get_plan_details(tier, duration_months)
            if not plan:
                return False, "Invalid subscription plan"

            if total_amount != plan["stars"]:
                logger.warning(
                    f"Amount mismatch: expected={plan['stars']}, got={total_amount}"
                )
                return False, "Invalid payment amount"

            # Additional business logic checks can go here:
            # - Check if user already has active subscription
            # - Check if user is banned
            # - etc.

            return True, None

        except Exception as e:
            logger.exception(f"Error validating pre-checkout: {e}")
            return False, "Payment validation failed"

    async def process_successful_payment(
        self,
        user_id: int,
        telegram_user_id: int,
        payment_data: Dict[str, Any],
        session: AsyncSession,
    ) -> bool:
        """
        Process successful payment and activate subscription

        IMPORTANT: Only call this after receiving successful_payment event!

        Args:
            user_id: User's database ID
            telegram_user_id: User's Telegram ID
            payment_data: Data from SuccessfulPayment event
            session: Database session

        Returns:
            True if processed successfully
        """
        try:
            # Extract payment info
            charge_id = payment_data["telegram_payment_charge_id"]
            provider_charge_id = payment_data.get("provider_payment_charge_id", "")
            total_amount = payment_data["total_amount"]
            currency = payment_data["currency"]
            payload = payment_data["invoice_payload"]

            # Parse subscription details from payload
            parts = payload.split("_")
            tier_value = parts[2]
            duration_months = int(parts[3])
            tier = SubscriptionTier(tier_value)

            # Get plan details
            plan = self.get_plan_details(tier, duration_months)
            if not plan:
                logger.error(f"Invalid plan in successful payment: {payload}")
                return False

            # Create payment record in database
            payment_record = await create_payment(
                session=session,
                user_id=user_id,
                provider=PaymentProvider.TELEGRAM_STARS.value,
                amount=plan["usd"],  # Store in USD
                currency="USD",  # Store as USD for consistency
                tier=tier.value,
                duration_months=duration_months,
                subscription_id=None,  # Will be set when payment is completed
                provider_payment_id=charge_id,
                provider_data=json.dumps({
                    "stars_amount": total_amount,
                    "stars_currency": currency,
                    "provider_charge_id": provider_charge_id,
                    "payload": payload,
                }),
            )

            # Complete payment and activate subscription
            # This will:
            # 1. Create/update subscription
            # 2. Set expires_at based on duration
            # 3. Update payment status to COMPLETED
            # 4. Link payment to subscription
            updated_payment = await complete_payment(session, payment_record.id)

            # Process referral revenue share if user was referred
            from src.database.crud import get_referrer, get_referral_tier, add_revenue_share
            from config.referral_config import get_tier_config

            referrer = await get_referrer(session, user_id)
            if referrer:
                # Get referrer's tier to determine revenue share percentage
                referrer_tier = await get_referral_tier(session, referrer.id)

                if referrer_tier:
                    # Get revenue share % from config (гибкая настройка без миграций)
                    tier_config = get_tier_config(referrer_tier.tier)
                    revenue_share_percent = tier_config.get("revenue_share_percent", 0)

                    if revenue_share_percent > 0:
                        # Calculate revenue share
                        revenue_share_amount = plan["usd"] * (revenue_share_percent / 100)

                        # Add revenue share to referrer
                        await add_revenue_share(
                            session=session,
                            referrer_id=referrer.id,
                            referee_id=user_id,
                            amount=revenue_share_amount,
                            payment_id=payment_record.id
                        )

                        logger.info(
                            f"Revenue share credited: referrer={referrer.id}, "
                            f"referee={user_id}, amount=${revenue_share_amount:.2f}, "
                            f"percent={revenue_share_percent}% (config)"
                        )

            logger.info(
                f"Payment processed successfully: "
                f"user={user_id}, tier={tier.value}, duration={duration_months}m, "
                f"amount={total_amount} Stars, charge_id={charge_id}"
            )

            return True

        except Exception as e:
            logger.exception(f"Error processing successful payment: {e}")
            return False

    async def refund_payment(
        self,
        bot: Bot,
        user_id: int,
        telegram_user_id: int,
        charge_id: str,
        session: AsyncSession,
    ) -> tuple[bool, Optional[str]]:
        """
        Refund a Telegram Stars payment

        LIMITATIONS:
        - Refunds only possible within 3 weeks of payment
        - Can only refund once per payment

        Args:
            bot: Bot instance
            user_id: User's database ID
            telegram_user_id: User's Telegram ID
            charge_id: telegram_payment_charge_id from payment
            session: Database session

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get payment from database
            payment = await get_payment_by_provider_id(session, charge_id)
            if not payment:
                return False, "Payment not found"

            # Check if already refunded
            if payment.status == PaymentStatus.REFUNDED:
                return False, "Payment already refunded"

            # Check refund period (3 weeks)
            now = datetime.now(UTC)
            payment_age = now - payment.created_at
            if payment_age > timedelta(weeks=3):
                return False, "Refund period expired (max 3 weeks)"

            # Execute refund via Telegram API
            success = await bot.refund_star_payment(
                user_id=telegram_user_id, telegram_payment_charge_id=charge_id
            )

            if not success:
                return False, "Refund failed"

            # Update payment status in database
            await update_payment_status(
                session=session,
                payment_id=payment.id,
                status=PaymentStatus.REFUNDED,
                completed_at=now,
            )

            # Deactivate associated subscription
            if payment.subscription_id:
                from src.database.crud import deactivate_subscription

                await deactivate_subscription(session, user_id)

            logger.info(f"Refund successful: user={user_id}, charge_id={charge_id}")

            return True, None

        except TelegramBadRequest as e:
            error_str = str(e)

            if "CHARGE_ALREADY_REFUNDED" in error_str:
                # Update our database to match
                await update_payment_status(
                    session=session,
                    payment_id=payment.id,
                    status=PaymentStatus.REFUNDED,
                )
                return False, "Payment already refunded"

            elif "CHARGE_NOT_FOUND" in error_str:
                return False, "Payment not found in Telegram system"

            else:
                logger.error(f"Telegram refund error: {e}")
                return False, f"Refund error: {error_str}"

        except Exception as e:
            logger.exception(f"Error processing refund: {e}")
            return False, "Refund processing failed"

    def get_plan_keyboard(
        self, tier: SubscriptionTier, user_language: str = "ru"
    ) -> InlineKeyboardMarkup:
        """
        Get inline keyboard for duration selection

        Args:
            tier: Selected subscription tier
            user_language: User's language

        Returns:
            InlineKeyboardMarkup with duration options
        """
        buttons = []

        for duration in [1, 3, 12]:
            plan = self.get_plan_details(tier, duration)
            if not plan:
                continue

            # Duration labels
            duration_labels = {
                1: "1 month" if user_language == "en" else "1 месяц",
                3: "3 months" if user_language == "en" else "3 месяца",
                12: "1 year" if user_language == "en" else "1 год",
            }

            label = f"{duration_labels[duration]} - {plan['stars']}⭐"
            if plan["discount"] > 0:
                label += f" (-{plan['discount']}%)"

            buttons.append(
                [
                    InlineKeyboardButton(
                        text=label,
                        callback_data=f"buy_{tier.value}_{duration}",
                    )
                ]
            )

        # Add back button
        back_text = "« Back" if user_language == "en" else "« Назад"
        buttons.append(
            [InlineKeyboardButton(text=back_text, callback_data="premium_menu")]
        )

        return InlineKeyboardMarkup(inline_keyboard=buttons)
