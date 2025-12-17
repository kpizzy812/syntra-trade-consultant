"""
Menu callback handlers - handle inline keyboard button clicks
"""

import asyncio
from pathlib import Path

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    InputMediaPhoto,
)
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import (
    get_user_by_telegram_id,
    check_request_limit,
    update_user_language,
)
from src.utils.i18n import i18n
router = Router(name="menu")


def get_back_to_menu_button(language: str = "ru") -> InlineKeyboardMarkup:
    """
    Create 'Back to menu' button

    Args:
        language: User language

    Returns:
        InlineKeyboardMarkup with back button
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.get("menu.back", language), callback_data="menu_back"
                )
            ]
        ]
    )
    return keyboard


async def safe_edit_or_resend(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup = None,
    with_photo: bool = False,
    photo_path: str = "assets/images/start.png",
):
    """
    Safely edit message or delete and resend if editing fails

    Args:
        callback: Callback query
        text: Message text or caption
        reply_markup: Keyboard markup
        with_photo: Whether to include photo
        photo_path: Path to photo file
    """
    try:
        if with_photo:
            # Try to edit with media
            image_path = Path(photo_path)
            if image_path.exists():
                photo = FSInputFile(image_path)
                media = InputMediaPhoto(media=photo, caption=text)
                await callback.message.edit_media(
                    media=media, reply_markup=reply_markup
                )
            else:
                # No image, just edit text
                await callback.message.edit_text(text, reply_markup=reply_markup)
        else:
            # Try to edit text only
            await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        # If editing fails (e.g., photo -> text), delete and resend
        logger.debug(f"Edit failed, deleting and resending: {e}")
        try:
            await callback.message.delete()
        except Exception:
            pass

        if with_photo:
            image_path = Path(photo_path)
            if image_path.exists():
                photo = FSInputFile(image_path)
                await callback.message.answer_photo(
                    photo=photo, caption=text, reply_markup=reply_markup
                )
            else:
                await callback.message.answer(text, reply_markup=reply_markup)
        else:
            await callback.message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "menu_help")
async def menu_help_callback(callback: CallbackQuery, user_language: str = "ru"):
    """
    Handle 'Help' button click - show help information
    """
    from config.config import (
        TERMS_OF_SERVICE_URL_RU,
        TERMS_OF_SERVICE_URL_EN,
        PRIVACY_POLICY_URL_RU,
        PRIVACY_POLICY_URL_EN,
    )

    # Get URLs based on language
    terms_url = TERMS_OF_SERVICE_URL_RU if user_language == "ru" else TERMS_OF_SERVICE_URL_EN
    privacy_url = PRIVACY_POLICY_URL_RU if user_language == "ru" else PRIVACY_POLICY_URL_EN

    # Build help text from translations
    help_text = f"""{i18n.get('help.title', user_language)}

{i18n.get('help.commands_title', user_language)}
{i18n.get('help.command_start', user_language)}
{i18n.get('help.command_help', user_language)}

{i18n.get('help.features_title', user_language)}

{i18n.get('help.feature_charts', user_language)}

{i18n.get('help.feature_price', user_language)}

{i18n.get('help.feature_news', user_language)}

{i18n.get('help.feature_analysis', user_language)}

{i18n.get('help.features_list_title', user_language)}
{i18n.get('help.features_list', user_language)}

{i18n.get('help.disclaimer', user_language)}

{i18n.get('help.limits_title', user_language)}
{i18n.get('help.limits_text', user_language)}

{i18n.get('help.footer', user_language)}
{i18n.get('help.legal_documents', user_language, terms_url=terms_url, privacy_url=privacy_url)}
"""

    await safe_edit_or_resend(
        callback, help_text, reply_markup=get_back_to_menu_button(user_language)
    )
    await callback.answer()
    logger.info(f"Help shown to user {callback.from_user.id} via menu")


@router.callback_query(F.data == "menu_profile")
async def menu_profile_callback(
    callback: CallbackQuery, session: AsyncSession, user_language: str = "ru"
):
    """
    Handle 'Profile' button click - show user profile and statistics
    """
    user = await get_user_by_telegram_id(session, callback.from_user.id)

    if not user:
        await callback.answer(
            i18n.get("profile.error_not_found", user_language), show_alert=True
        )
        return

    # Get request limits
    _, current_count, limit = await check_request_limit(session, user)
    remaining = limit - current_count

    # Format registration date
    reg_date = user.created_at.strftime("%d.%m.%Y")

    # Language display
    lang_display = (
        i18n.get("profile.language_ru", user_language)
        if user.language == "ru"
        else i18n.get("profile.language_en", user_language)
    )

    # Status display - check subscription
    await session.refresh(user, ["subscription", "referral_balance"])
    subscription = user.subscription

    if subscription and subscription.is_active and subscription.tier != "free":
        tier_name = i18n.get(f"tier_names.{subscription.tier}", user_language)
        status_display = f"⭐ {tier_name}"
    else:
        status_display = i18n.get("profile.status_free", user_language)

    # Get referral balance
    balance = float(user.referral_balance.balance_usd if user.referral_balance else 0)
    total_earned = float(user.referral_balance.earned_total_usd if user.referral_balance else 0)

    profile_text = f"""{i18n.get('profile.title', user_language)}

{i18n.get('profile.name', user_language, name=user.first_name or i18n.get('errors.no_value', user_language))}
{i18n.get('profile.username', user_language, username=user.username or i18n.get('errors.no_value', user_language))}
{i18n.get('profile.registration', user_language, date=reg_date)}
{i18n.get('profile.language', user_language, lang=lang_display)}

{i18n.get('profile.usage_title', user_language)}

{i18n.get('profile.requests', user_language, current=remaining, limit=limit)}

{i18n.get('profile.status', user_language, status=status_display)}"""

    # Add referral balance if user has earnings
    if total_earned > 0:
        profile_text += f"""

{i18n.get('profile.referral_balance_title', user_language)}
{i18n.get('profile.referral_balance', user_language, balance=f"{balance:.2f}")}
{i18n.get('profile.referral_earned', user_language, earned=f"{total_earned:.2f}")}"""

    profile_text += f"""

{i18n.get('profile.premium_hint', user_language)}
"""

    # Add language change button
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.get("profile.change_language", user_language),
                    callback_data="change_language",
                )
            ],
            [
                InlineKeyboardButton(
                    text=i18n.get("menu.back", user_language), callback_data="menu_back"
                )
            ],
        ]
    )

    await safe_edit_or_resend(callback, profile_text, reply_markup=keyboard)
    await callback.answer()
    logger.info(f"Profile shown to user {callback.from_user.id}")


@router.callback_query(F.data == "change_language")
async def change_language_callback(callback: CallbackQuery, user_language: str = "ru"):
    """
    Handle 'Change Language' button click - show language selection
    """
    language_text = i18n.get("language.select", user_language)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.get("language.russian", user_language),
                    callback_data="set_language_ru",
                )
            ],
            [
                InlineKeyboardButton(
                    text=i18n.get("language.english", user_language),
                    callback_data="set_language_en",
                )
            ],
            [
                InlineKeyboardButton(
                    text=i18n.get("menu.back", user_language),
                    callback_data="menu_profile",
                )
            ],
        ]
    )

    await safe_edit_or_resend(callback, language_text, reply_markup=keyboard)
    await callback.answer()
    logger.info(f"Language selection shown to user {callback.from_user.id}")


@router.callback_query(F.data.startswith("set_language_"))
async def set_language_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Handle language selection
    """
    # Extract language code from callback data (set_language_ru -> ru)
    new_language = callback.data.split("_")[-1]

    # Update user language in database
    await update_user_language(session, callback.from_user.id, new_language)

    # Show confirmation
    lang_name = (
        i18n.get("language.russian", new_language)
        if new_language == "ru"
        else i18n.get("language.english", new_language)
    )
    await callback.answer(
        i18n.get("language.changed", new_language, lang=lang_name), show_alert=True
    )

    # Return to profile with new language
    user = await get_user_by_telegram_id(session, callback.from_user.id)
    _, current_count, limit = await check_request_limit(session, user)
    remaining = limit - current_count
    reg_date = user.created_at.strftime("%d.%m.%Y")
    lang_display = (
        i18n.get("profile.language_ru", new_language)
        if user.language == "ru"
        else i18n.get("profile.language_en", new_language)
    )
    status_display = (
        i18n.get("profile.status_premium", new_language)
        if user.is_admin
        else i18n.get("profile.status_free", new_language)
    )

    profile_text = f"""{i18n.get('profile.title', new_language)}

{i18n.get('profile.name', new_language, name=user.first_name or i18n.get('errors.no_value', new_language))}
{i18n.get('profile.username', new_language, username=user.username or i18n.get('errors.no_value', new_language))}
{i18n.get('profile.registration', new_language, date=reg_date)}
{i18n.get('profile.language', new_language, lang=lang_display)}

{i18n.get('profile.usage_title', new_language)}

{i18n.get('profile.requests', new_language, current=remaining, limit=limit)}

{i18n.get('profile.status', new_language, status=status_display)}

{i18n.get('profile.premium_hint', new_language)}
"""

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.get("profile.change_language", new_language),
                    callback_data="change_language",
                )
            ],
            [
                InlineKeyboardButton(
                    text=i18n.get("menu.back", new_language), callback_data="menu_back"
                )
            ],
        ]
    )

    await safe_edit_or_resend(callback, profile_text, reply_markup=keyboard)
    logger.info(f"User {callback.from_user.id} language changed to {new_language}")


@router.callback_query(F.data == "menu_referral")
async def menu_referral_callback(
    callback: CallbackQuery, session: AsyncSession, user_language: str = "ru"
):
    """
    Handle 'Referral System' button click
    """
    from src.database import crud
    from src.bot.handlers.referral import get_referral_menu_keyboard

    user = await get_user_by_telegram_id(session, callback.from_user.id)

    if not user:
        await callback.answer(
            i18n.get("profile.error_not_found", user_language), show_alert=True
        )
        return

    # Ensure user has referral code
    if not user.referral_code:
        user.referral_code = await crud.generate_referral_code(session, user.id)
        await session.commit()

    # Get referral stats
    stats = await crud.get_referral_stats(session, user.id)

    # Get tier emoji
    tier_emojis = {
        "bronze": "🥉",
        "silver": "🥈",
        "gold": "🥇",
        "platinum": "💎",
    }
    tier_emoji = tier_emojis.get(stats['tier'], "🥉")

    # Get referral link
    bot_username = (await callback.bot.me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user.referral_code}"

    # Get referrer info (who invited this user)
    referrer = await crud.get_referrer(session, user.id)

    # Build text
    tier_name = i18n.get(f'tier_names.{stats["tier"]}', user_language)
    text = (
        f"{i18n.get('referral.title', user_language)}\n\n"
        f"{i18n.get('referral.your_code', user_language)}: <code>{user.referral_code}</code>\n"
        f"{i18n.get('referral.your_link', user_language)}:\n<code>{ref_link}</code>"
    )

    # Add referrer info
    if referrer:
        if referrer.username:
            text += i18n.get('referral.invited_by', user_language, username=referrer.username)
        else:
            text += i18n.get('referral.invited_by_unknown', user_language, name=referrer.first_name or "Unknown")
    else:
        text += i18n.get('referral.not_invited', user_language)

    text += (
        f"\n\n{tier_emoji} {i18n.get('referral.tier', user_language)}: <b>{tier_name}</b>\n"
        f"{i18n.get('referral.total_referrals', user_language)}: {stats['total_referrals']}\n"
        f"{i18n.get('referral.active_referrals', user_language)}: {stats['active_referrals']}\n\n"
        f"{i18n.get('referral.rewards', user_language)}:\n"
    )

    # Add rewards info
    if stats['monthly_bonus'] > 0:
        text += f"• {i18n.get('referral.monthly_bonus', user_language)}: +{stats['monthly_bonus']} {i18n.get('referral.requests', user_language)}\n"

    if stats['discount_percent'] > 0:
        text += f"• {i18n.get('referral.discount', user_language)}: {stats['discount_percent']}%\n"

    if stats['revenue_share_percent'] > 0:
        text += f"• {i18n.get('referral.revenue_share', user_language)}: {stats['revenue_share_percent']}%\n"

    # Add leaderboard rank
    if stats['leaderboard_rank']:
        text += f"\n{i18n.get('referral.leaderboard_rank', user_language)}: #{stats['leaderboard_rank']}"

    # Keyboard with additional options
    keyboard = get_referral_menu_keyboard(user_language)

    await safe_edit_or_resend(callback, text, reply_markup=keyboard)
    await callback.answer()
    logger.info(f"Referral info shown to user {callback.from_user.id}")


@router.callback_query(F.data == "menu_premium")
async def menu_premium_callback(callback: CallbackQuery, user_language: str = "ru"):
    """
    Handle 'Premium' button click - show premium subscription tiers

    Shows real premium plans with Telegram Stars pricing
    """
    # Use tier selection from premium.py
    from src.bot.handlers.premium import get_tier_selection_keyboard
    from src.services.telegram_stars_service import SUBSCRIPTION_PLANS
    from src.database.models import SubscriptionTier

    keyboard = get_tier_selection_keyboard(user_language)

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

    await safe_edit_or_resend(callback, text, reply_markup=keyboard)
    await callback.answer()
    logger.info(f"Premium tiers shown to user {callback.from_user.id}")


@router.callback_query(F.data == "premium_subscribe")
async def premium_subscribe_callback(
    callback: CallbackQuery, user_language: str = "ru"
):
    """
    Handle premium subscription attempt - redirect to tier selection
    """
    # Redirect to tier selection (same as menu_premium)
    await menu_premium_callback(callback, user_language)


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(
    callback: CallbackQuery, session: AsyncSession, user_language: str = "ru"
):
    """
    Handle 'Check Subscription' button - verify and grant access
    """
    from config.config import (
        REQUIRED_CHANNEL,
        TERMS_OF_SERVICE_URL_RU,
        TERMS_OF_SERVICE_URL_EN,
        PRIVACY_POLICY_URL_RU,
        PRIVACY_POLICY_URL_EN,
    )
    from aiogram.enums import ChatMemberStatus, ParseMode
    from src.bot.handlers.start import get_main_menu
    from src.database.models import User
    from src.database.crud import create_referral

    try:
        # Get user from database for language
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        lang = user.language if user else user_language

        # Check subscription
        member = await callback.bot.get_chat_member(
            chat_id=REQUIRED_CHANNEL, user_id=callback.from_user.id
        )

        if member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }:
            # User is subscribed - answer callback first
            await callback.answer(i18n.get("subscription.verified_alert", lang))
            logger.info(f"User {callback.from_user.id} subscription verified")

            # Process pending referral code if exists
            if user.pending_referral_code:
                referral_code = user.pending_referral_code
                logger.info(f"Processing pending referral code {referral_code} for user {user.id}")

                # Find referrer by code
                from sqlalchemy import select
                stmt = select(User).where(User.referral_code == referral_code)
                result = await session.execute(stmt)
                referrer = result.scalar_one_or_none()

                if referrer and referrer.id != user.id:
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
                                f"Referral created: {referrer.id} (@{referrer.username}) "
                                f"referred {user.id} (@{user.username})"
                            )

                            # Send notification to referrer about new referral
                            try:
                                from src.database.crud import get_referral_stats

                                # Get referrer's language
                                referrer_lang = referrer.language or "ru"

                                # Get total referrals count
                                stats = await get_referral_stats(session, referrer.id)

                                # Format user display
                                user_display = f"@{user.username}" if user.username else user.first_name or "Anonymous"

                                # Format date
                                from datetime import datetime
                                current_date = datetime.now().strftime("%d.%m.%Y %H:%M")

                                # Build notification text
                                notification_text = (
                                    f"{i18n.get('referral_notifications.new_referral_title', referrer_lang)}\n\n"
                                    f"{i18n.get('referral_notifications.new_referral_text', referrer_lang, user_display=user_display, date=current_date, total=stats['total_referrals'])}"
                                )

                                # Send notification to referrer
                                await callback.bot.send_message(
                                    chat_id=referrer.telegram_id,
                                    text=notification_text,
                                    parse_mode="HTML"
                                )

                                logger.info(f"Notification sent to referrer {referrer.id} about new referral {user.id}")
                            except Exception as notif_error:
                                logger.error(f"Failed to send referral notification: {notif_error}")
                    except Exception as e:
                        logger.error(f"Failed to create referral: {e}")

                # Clear pending referral code
                user.pending_referral_code = None
                await session.commit()
                logger.info(f"Cleared pending referral code for user {user.id}")

            # Check if privacy policy was already shown
            if not user.privacy_policy_shown:
                # Show privacy policy message ONCE with both URLs
                terms_url = TERMS_OF_SERVICE_URL_RU if lang == "ru" else TERMS_OF_SERVICE_URL_EN
                privacy_url = PRIVACY_POLICY_URL_RU if lang == "ru" else PRIVACY_POLICY_URL_EN
                privacy_message = i18n.get(
                    "privacy.policy_message", lang, terms_url=terms_url, privacy_url=privacy_url
                )

                # Send privacy policy as separate message
                await callback.message.answer(
                    privacy_message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )

                # Update user to mark privacy policy as shown
                user.privacy_policy_shown = True
                await session.commit()

                # Wait 3 seconds before showing main menu
                await asyncio.sleep(3)

            # Show main menu
            greeting = i18n.get(
                "subscription.verified", lang, name=callback.from_user.first_name
            )

            await safe_edit_or_resend(
                callback, greeting, reply_markup=get_main_menu(lang), with_photo=True
            )
        else:
            await callback.answer(
                i18n.get("subscription.not_found", lang), show_alert=True
            )

    except Exception as e:
        logger.error(
            f"Error verifying subscription for user {callback.from_user.id}: {e}"
        )
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        lang = user.language if user else user_language
        await callback.answer(i18n.get("subscription.error", lang), show_alert=True)


@router.callback_query(F.data == "menu_back")
async def menu_back_callback(
    callback: CallbackQuery, session: AsyncSession, user_language: str = "ru"
):
    """
    Handle 'Back to menu' button - return to main menu
    """
    from src.bot.handlers.start import get_main_menu

    # Get user language from database
    user = await get_user_by_telegram_id(session, callback.from_user.id)
    lang = user.language if user else user_language

    greeting = i18n.get("menu.back_text", lang, name=callback.from_user.first_name)

    await safe_edit_or_resend(
        callback, greeting, reply_markup=get_main_menu(lang), with_photo=True
    )
    await callback.answer()
    logger.info(f"User {callback.from_user.id} returned to main menu")
