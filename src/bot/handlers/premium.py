# coding: utf-8
"""
Premium subscription handlers

Handles:
- /premium - Show subscription plans
- Tier and duration selection
- Invoice creation
- Pre-checkout validation
- Successful payment processing
- /subscription - Show current subscription
- /cancel_subscription - Cancel auto-renewal
"""
import logging
from datetime import datetime, UTC

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    PreCheckoutQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import SubscriptionTier
from src.database.crud import get_subscription, update_subscription
from src.services.telegram_stars_service import TelegramStarsService
from src.utils.i18n import i18n


logger = logging.getLogger(__name__)

# Create router
router = Router(name="premium")

# Initialize payment service
payment_service = TelegramStarsService()


@router.message(Command("premium"))
async def cmd_premium(message: Message, user_language: str = "ru") -> None:
    """
    Show premium subscription plans

    Args:
        message: Telegram message
        user_language: User's language (from LanguageMiddleware)
    """
    # Get tier selection keyboard
    keyboard = get_tier_selection_keyboard(user_language)

    # Import pricing to show in description
    from src.services.telegram_stars_service import SUBSCRIPTION_PLANS

    # Get prices from config
    basic_price = SUBSCRIPTION_PLANS[SubscriptionTier.BASIC]["1"]["usd"]
    premium_price = SUBSCRIPTION_PLANS[SubscriptionTier.PREMIUM]["1"]["usd"]
    vip_price = SUBSCRIPTION_PLANS[SubscriptionTier.VIP]["1"]["usd"]

    # Build text using i18n with prices
    text = (
        f"{i18n.get('premium.title', user_language)}\n\n"
        f"{i18n.get('premium.choose_plan', user_language)}\n\n"
        f"{i18n.get('premium_plans.basic.emoji', user_language)} <b>{i18n.get('premium_plans.basic.name', user_language)}</b> ({i18n.get('premium_plans.basic.limit', user_language)}) - <b>${basic_price:.2f}/мес</b>\n"
        f"{i18n.get('premium_plans.basic.feature_1', user_language)}\n"
        f"{i18n.get('premium_plans.basic.feature_2', user_language)}\n"
        f"{i18n.get('premium_plans.basic.feature_3', user_language)}\n\n"
        f"{i18n.get('premium_plans.premium.emoji', user_language)} <b>{i18n.get('premium_plans.premium.name', user_language)}</b> ({i18n.get('premium_plans.premium.limit', user_language)}) - <b>${premium_price:.2f}/мес</b>\n"
        f"{i18n.get('premium_plans.premium.feature_1', user_language)}\n"
        f"{i18n.get('premium_plans.premium.feature_2', user_language)}\n"
        f"{i18n.get('premium_plans.premium.feature_3', user_language)}\n"
        f"{i18n.get('premium_plans.premium.feature_4', user_language)}\n\n"
        f"{i18n.get('premium_plans.vip.emoji', user_language)} <b>{i18n.get('premium_plans.vip.name', user_language)}</b> ({i18n.get('premium_plans.vip.limit', user_language)}) - <b>${vip_price:.2f}/мес</b>\n"
        f"{i18n.get('premium_plans.vip.feature_1', user_language)}\n"
        f"{i18n.get('premium_plans.vip.feature_2', user_language)}\n"
        f"{i18n.get('premium_plans.vip.feature_3', user_language)}\n"
        f"{i18n.get('premium_plans.vip.feature_4', user_language)}\n\n"
        f"{i18n.get('premium.select_below', user_language)}"
    )

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


def get_tier_selection_keyboard(user_language: str = "ru") -> InlineKeyboardMarkup:
    """Get keyboard for tier selection"""
    # Build tier labels using i18n
    tier_labels = {
        "basic": f"{i18n.get('premium_plans.basic.emoji', user_language)} {i18n.get('tier_names.basic', user_language)}",
        "premium": f"{i18n.get('premium_plans.premium.emoji', user_language)} {i18n.get('tier_names.premium', user_language)}",
        "vip": f"{i18n.get('premium_plans.vip.emoji', user_language)} {i18n.get('tier_names.vip', user_language)}",
    }

    buttons = [
        [
            InlineKeyboardButton(
                text=tier_labels["basic"], callback_data="tier_basic"
            )
        ],
        [
            InlineKeyboardButton(
                text=tier_labels["premium"], callback_data="tier_premium"
            )
        ],
        [InlineKeyboardButton(text=tier_labels["vip"], callback_data="tier_vip")],
        [
            InlineKeyboardButton(
                text=i18n.get("menu.back", user_language),
                callback_data="menu_back"
            )
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("tier_"))
async def select_tier(
    callback: CallbackQuery, user_language: str = "ru"
) -> None:
    """
    Handle tier selection, show duration options

    Args:
        callback: Callback query
        user_language: User's language (from LanguageMiddleware)
    """
    # Parse tier from callback data
    tier_value = callback.data.split("_")[1]  # "tier_basic" -> "basic"
    tier = SubscriptionTier(tier_value)

    # Get duration selection keyboard
    keyboard = payment_service.get_plan_keyboard(tier, user_language)

    # Build tier info message using i18n
    tier_name = i18n.get(f"tier_names.{tier_value}", user_language)
    tier_limit = i18n.get(f"premium_plans.{tier_value}.limit", user_language)

    text = (
        f"{i18n.get('premium_selection.tier_selected', user_language, tier=tier_name)}\n\n"
        f"{i18n.get('premium_selection.limit_label', user_language)} {tier_limit}\n\n"
        f"{i18n.get('premium_selection.select_duration', user_language)}\n"
        f"{i18n.get('premium_selection.longer_better', user_language)}"
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "premium_menu")
async def back_to_premium_menu(
    callback: CallbackQuery, user_language: str = "ru"
) -> None:
    """Go back to premium menu"""
    keyboard = get_tier_selection_keyboard(user_language)
    text = i18n.get("premium.back_to_menu", user_language)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("buy_"))
async def process_purchase(
    callback: CallbackQuery,
    user: "User",  # From DatabaseMiddleware
    session: AsyncSession,  # From DatabaseMiddleware
    user_language: str = "ru",  # From LanguageMiddleware
) -> None:
    """
    Process purchase - create and send invoice

    Callback data format: "buy_{tier}_{duration}"
    Example: "buy_premium_3"

    Args:
        callback: Callback query
        user: User from database
        session: Database session
        user_language: User's language
    """
    # Parse callback data
    parts = callback.data.split("_")  # ["buy", "premium", "3"]
    tier_value = parts[1]
    duration_months = int(parts[2])

    tier = SubscriptionTier(tier_value)

    # Create invoice
    success = await payment_service.create_subscription_invoice(
        message=callback.message,
        user_id=user.id,
        tier=tier,
        duration_months=duration_months,
        user_language=user_language,
    )

    if success:
        # Answer callback
        await callback.answer(
            i18n.get("premium_purchase.invoice_created", user_language),
            show_alert=False
        )
    else:
        # Error creating invoice
        await callback.answer(
            i18n.get("premium_purchase.invoice_error", user_language),
            show_alert=True
        )


@router.pre_checkout_query()
async def process_pre_checkout(
    pre_checkout_query: PreCheckoutQuery,
    user: "User",  # From DatabaseMiddleware
    session: AsyncSession,  # From DatabaseMiddleware
) -> None:
    """
    Process pre-checkout query

    CRITICAL:
    - MUST respond within 10 seconds!
    - Validates payment before it's processed
    - If ok=False, payment is cancelled

    Args:
        pre_checkout_query: Pre-checkout query from Telegram
        user: User from database
        session: Database session
    """
    logger.info(
        f"Pre-checkout: user={user.id}, "
        f"payload={pre_checkout_query.invoice_payload}, "
        f"amount={pre_checkout_query.total_amount} Stars"
    )

    # Validate payment
    is_valid, error_message = await payment_service.validate_pre_checkout(
        user_id=user.id,
        payload=pre_checkout_query.invoice_payload,
        total_amount=pre_checkout_query.total_amount,
        session=session,
    )

    if is_valid:
        # Approve payment
        await pre_checkout_query.answer(ok=True)
        logger.info(f"Pre-checkout approved for user {user.id}")
    else:
        # Reject payment
        await pre_checkout_query.answer(ok=False, error_message=error_message)
        logger.warning(
            f"Pre-checkout rejected for user {user.id}: {error_message}"
        )


@router.message(F.successful_payment)
async def process_successful_payment(
    message: Message,
    user: "User",  # From DatabaseMiddleware
    session: AsyncSession,  # From DatabaseMiddleware
    user_language: str = "ru",  # From LanguageMiddleware
) -> None:
    """
    Process successful payment

    IMPORTANT:
    - Only triggered after successful payment
    - This is where we activate the subscription
    - Save telegram_payment_charge_id for refunds!

    Args:
        message: Message with successful_payment
        user: User from database
        session: Database session
        user_language: User's language
    """
    payment = message.successful_payment

    logger.info(
        f"Successful payment: user={user.id} (telegram_id={user.telegram_id}), "
        f"amount={payment.total_amount} {payment.currency}, "
        f"charge_id={payment.telegram_payment_charge_id}"
    )

    # Extract payment data
    payment_data = {
        "telegram_payment_charge_id": payment.telegram_payment_charge_id,
        "provider_payment_charge_id": payment.provider_payment_charge_id,
        "total_amount": payment.total_amount,
        "currency": payment.currency,
        "invoice_payload": payment.invoice_payload,
    }

    # Process payment and activate subscription
    success = await payment_service.process_successful_payment(
        user_id=user.id,
        telegram_user_id=user.telegram_id,
        payment_data=payment_data,
        session=session,
    )

    if success:
        # Get updated subscription info
        subscription = await get_subscription(session, user.id)

        # Build success message using i18n
        tier_name = i18n.get(f"tier_names.{subscription.tier}", user_language)

        text = (
            f"{i18n.get('premium_payment.success', user_language)}\n\n"
            f"{i18n.get('premium_payment.activated', user_language)} {tier_name}\n"
            f"{i18n.get('premium_payment.active_until', user_language)} {subscription.expires_at.strftime('%d.%m.%Y')}\n"
            f"{i18n.get('premium_payment.paid', user_language)} {payment.total_amount} {i18n.get('premium_payment.stars', user_language)}\n\n"
            f"<code>ID: {payment.telegram_payment_charge_id}</code>\n\n"
            f"{i18n.get('premium_payment.thank_you', user_language)}"
        )

        await message.answer(text, parse_mode="HTML")
    else:
        # Payment processing failed
        text = (
            f"{i18n.get('premium_payment.activation_error', user_language)}\n\n"
            f"{i18n.get('premium_payment.activation_error_text', user_language)}"
        )

        await message.answer(text)


@router.message(Command("subscription"))
async def cmd_subscription(
    message: Message,
    user: "User",  # From DatabaseMiddleware
    session: AsyncSession,  # From DatabaseMiddleware
    user_language: str = "ru",  # From LanguageMiddleware
) -> None:
    """
    Show current subscription status

    Args:
        message: Telegram message
        user: User from database
        session: Database session
        user_language: User's language
    """
    # Refresh user to load subscription
    await session.refresh(user, ["subscription"])

    subscription = user.subscription

    # Check if user has subscription
    if not subscription or not subscription.is_active:
        text = (
            f"{i18n.get('premium_subscription.no_active', user_language)}\n\n"
            f"{i18n.get('premium_subscription.use_premium', user_language)}"
        )
        await message.answer(text)
        return

    # Check if expired
    now = datetime.now(UTC)
    if subscription.expires_at and subscription.expires_at < now:
        text = (
            f"{i18n.get('premium_subscription.expired', user_language)}\n\n"
            f"{i18n.get('premium_subscription.use_renew', user_language)}"
        )
        await message.answer(text)
        return

    # Calculate days left
    if subscription.expires_at:
        days_left = (subscription.expires_at - now).days
    else:
        days_left = None  # Free tier

    # Build status message using i18n
    tier_name = i18n.get(f"tier_names.{subscription.tier}", user_language)
    request_limit = user.get_request_limit()

    text = (
        f"{i18n.get('premium_subscription.your_subscription', user_language)}\n\n"
        f"{i18n.get('premium_subscription.plan', user_language)} {tier_name}\n"
        f"{i18n.get('premium_subscription.limit', user_language)} {request_limit} {i18n.get('premium_selection.requests_per_day', user_language)}\n"
    )

    if days_left is not None:
        text += (
            f"{i18n.get('premium_subscription.expires', user_language)} {subscription.expires_at.strftime('%d.%m.%Y')}\n"
            f"{i18n.get('premium_subscription.days_left', user_language)} {days_left}\n"
        )

    auto_renew_status = i18n.get(
        'premium_subscription.enabled' if subscription.auto_renew else 'premium_subscription.disabled',
        user_language
    )
    text += f"\n{i18n.get('premium_subscription.auto_renewal', user_language)} {auto_renew_status}"

    # Add keyboard
    buttons = []

    if subscription.tier != SubscriptionTier.FREE:
        # Add upgrade/change plan button
        buttons.append([
            InlineKeyboardButton(
                text=i18n.get("premium_subscription.change_plan", user_language),
                callback_data="premium_menu"
            )
        ])

    # Add back to menu button
    buttons.append([
        InlineKeyboardButton(
            text=i18n.get("menu.back", user_language),
            callback_data="menu_back"
        )
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("cancel_subscription"))
async def cmd_cancel_subscription(
    message: Message,
    user: "User",  # From DatabaseMiddleware
    session: AsyncSession,  # From DatabaseMiddleware
    user_language: str = "ru",  # From LanguageMiddleware
) -> None:
    """
    Cancel auto-renewal (subscription remains active until expiry)

    Args:
        message: Telegram message
        user: User from database
        session: Database session
        user_language: User's language
    """
    # Refresh user to load subscription
    await session.refresh(user, ["subscription"])

    subscription = user.subscription

    # Check if user has active subscription
    if not subscription or not subscription.is_active:
        await message.answer(i18n.get("premium_cancel.no_active", user_language))
        return

    # Check if FREE tier
    if subscription.tier == SubscriptionTier.FREE:
        await message.answer(i18n.get("premium_cancel.free_tier", user_language))
        return

    # Check if auto-renewal is already disabled
    if not subscription.auto_renew:
        text = (
            f"{i18n.get('premium_cancel.already_disabled', user_language)}\n\n"
            f"{i18n.get('premium_cancel.active_until', user_language)} {subscription.expires_at.strftime('%d.%m.%Y')}"
        )
        await message.answer(text)
        return

    # Disable auto-renewal
    await update_subscription(session, user.id, auto_renew=False)

    text = (
        f"{i18n.get('premium_cancel.auto_renewal_disabled', user_language)}\n\n"
        f"{i18n.get('premium_cancel.remains_active', user_language)} {subscription.expires_at.strftime('%d.%m.%Y')}\n"
        f"{i18n.get('premium_cancel.will_return', user_language)}"
    )

    await message.answer(text)
