"""
/start command handler
"""

from pathlib import Path

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    WebAppInfo,
)
from aiogram.enums import ChatMemberStatus
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import create_referral, grant_referee_bonus
from src.database.models import User
from src.services.posthog_service import track_user_registered, identify_user
from src.utils.i18n import i18n
from config.config import WEBAPP_URL, REQUIRED_CHANNEL
from sqlalchemy import select
router = Router(name="start")


def get_main_menu(language: str = "ru") -> InlineKeyboardMarkup:
    """
    Create main menu inline keyboard

    Args:
        language: User language (ru or en)

    Returns:
        InlineKeyboardMarkup with main navigation buttons
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            # Row 1: Web App button
            [
                InlineKeyboardButton(
                    text=i18n.get("menu.open_app", language),
                    web_app=WebAppInfo(url=WEBAPP_URL)
                ),
            ],
            # Row 2: Help and Profile
            [
                InlineKeyboardButton(
                    text=i18n.get("menu.help", language), callback_data="menu_help"
                ),
                InlineKeyboardButton(
                    text=i18n.get("menu.profile", language),
                    callback_data="menu_profile",
                ),
            ],
            # Row 3: Referral and Premium
            [
                InlineKeyboardButton(
                    text=i18n.get("menu.referral", language),
                    callback_data="menu_referral",
                ),
                InlineKeyboardButton(
                    text=i18n.get("menu.premium", language),
                    callback_data="menu_premium",
                ),
            ],
        ]
    )
    return keyboard


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    session: AsyncSession,
    user: User,
    is_new_user: bool = False,
    user_language: str = "ru"
):
    """
    Handle /start command - welcome message and user registration

    Args:
        message: Incoming message
        session: Database session (provided by DatabaseMiddleware)
        user: Database user object (provided by DatabaseMiddleware)
        is_new_user: Flag if user is new (provided by DatabaseMiddleware)
        user_language: User language (provided by LanguageMiddleware)
    """
    telegram_user = message.from_user

    # Use user's saved language from database
    lang = user.language

    logger.info(f"User {telegram_user.id} (@{telegram_user.username}): is_new={is_new_user}, message='{message.text}'")

    # For new users, check subscription FIRST before any other logic
    if is_new_user:
        # Extract and save startapp parameter from deep link
        if message.text and len(message.text.split()) > 1:
            deep_link_param = message.text.split()[1]
            # Check if it's NOT a referral code (doesn't start with ref_)
            if not deep_link_param.startswith("ref_"):
                # Save as startapp parameter
                user.startapp_param = deep_link_param
                await session.commit()
                logger.info(f"Saved startapp parameter '{deep_link_param}' for user {user.id}")

        # Check if user is subscribed to required channel
        try:
            member = await message.bot.get_chat_member(
                chat_id=REQUIRED_CHANNEL, user_id=telegram_user.id
            )
            is_subscribed = member.status in {
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.CREATOR,
            }
        except Exception as e:
            logger.error(f"Failed to check subscription for user {telegram_user.id}: {e}")
            is_subscribed = False

        # If NOT subscribed, save referral code (if any) and show subscription prompt
        if not is_subscribed:
            # Extract referral code from deep link (e.g., /start ref_ABC123XYZ)
            if message.text and len(message.text.split()) > 1:
                referral_param = message.text.split()[1]
                if referral_param.startswith("ref_"):
                    referral_code = referral_param[4:]  # Remove "ref_" prefix
                    # Save to pending_referral_code for processing after subscription
                    user.pending_referral_code = referral_code
                    await session.commit()
                    logger.info(f"Saved pending referral code {referral_code} for user {user.id}")

            # Show subscription prompt
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"📢 {i18n.get('subscription.subscribe_button', lang)}",
                            url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=i18n.get("subscription.check_button", lang),
                            callback_data="check_subscription",
                        )
                    ],
                ]
            )

            subscription_text = i18n.get(
                "subscription.required",
                lang,
                channel=f"@{REQUIRED_CHANNEL.lstrip('@')}",
            )

            await message.answer(subscription_text, reply_markup=keyboard)
            logger.info(f"New user {telegram_user.id} not subscribed - showing subscription prompt")
            return  # Don't show welcome message or main menu yet

    # Handle referral code from deep link (e.g., /start ref_ABC123XYZ)
    # Only for subscribed new users or when is_new_user is True
    if is_new_user and message.text and len(message.text.split()) > 1:
        referral_param = message.text.split()[1]
        if referral_param.startswith("ref_"):
            referral_code = referral_param[4:]  # Remove "ref_" prefix

            # Find referrer by code
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

                        # IMMEDIATELY grant welcome bonus to referee (+15 requests)
                        try:
                            bonus_granted = await grant_referee_bonus(session, referral.id)
                            if bonus_granted:
                                logger.info(f"Welcome bonus granted to referee {user.id}: +15 requests")
                            else:
                                logger.warning(f"Failed to grant welcome bonus to referee {user.id}")
                        except Exception as bonus_error:
                            logger.error(f"Error granting welcome bonus to referee {user.id}: {bonus_error}")

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
                            await message.bot.send_message(
                                chat_id=referrer.telegram_id,
                                text=notification_text,
                                parse_mode="HTML"
                            )

                            logger.info(f"Notification sent to referrer {referrer.id} about new referral {user.id}")
                        except Exception as notif_error:
                            logger.error(f"Failed to send referral notification: {notif_error}")
                except Exception as e:
                    logger.error(f"Failed to create referral: {e}")

    if is_new_user:
        logger.info(
            f"New user registered: {telegram_user.id} (@{telegram_user.username}) with language: {lang}"
        )

        # 📊 Track user registration in PostHog
        # Find referrer ID if exists
        referrer_id = None
        if message.text and len(message.text.split()) > 1:
            referral_param = message.text.split()[1]
            if referral_param.startswith("ref_"):
                referral_code = referral_param[4:]
                stmt = select(User).where(User.referral_code == referral_code)
                result = await session.execute(stmt)
                referrer = result.scalar_one_or_none()
                if referrer:
                    referrer_id = referrer.id

        track_user_registered(user.id, lang, referrer_id)
        identify_user(
            user.id,
            user.telegram_id,
            user.username,
            "free",  # New users start with FREE tier (7-day Premium trial)
            lang,
            user.created_at.isoformat() if user.created_at else ""
        )

        # New users get trial welcome message with 7-day Premium trial announcement
        greeting = i18n.get("trial.welcome_new_user", lang)
    else:
        logger.info(f"Returning user: {telegram_user.id} (@{telegram_user.username})")
        greeting = i18n.get("start.welcome_back", lang, name=telegram_user.first_name or "User")

    # 💎 Process daily login bonus (streak system)
    try:
        from src.services.points_service import PointsService

        daily_login_transaction = await PointsService.process_daily_login(
            session=session,
            user_id=user.id
        )

        if daily_login_transaction and daily_login_transaction.amount > 0:
            # Get streak info from metadata
            import json
            metadata = json.loads(daily_login_transaction.metadata_json) if daily_login_transaction.metadata_json else {}
            streak = metadata.get("streak", 1)
            longest_streak = metadata.get("longest_streak", 1)

            logger.info(
                f"💎 Daily login bonus: user {user.id} earned {daily_login_transaction.amount} points "
                f"(streak: {streak} days, balance: {daily_login_transaction.balance_after})"
            )

            # Add streak notification to greeting (if earned points)
            if streak > 1:
                streak_emoji = "🔥" if streak >= 7 else "⭐"
                greeting += f"\n\n{streak_emoji} <b>Streak бонус: {streak} дней подряд!</b>\n💎 +{daily_login_transaction.amount} $SYNTRA поинтов"
    except Exception as daily_error:
        # Don't fail /start if daily login fails
        logger.error(f"Failed to process daily login for user {user.id}: {daily_error}")

    # Try to send with image, fallback to text if image not found
    image_path = Path("assets/images/start.png")
    if image_path.exists():
        photo = FSInputFile(image_path)
        await message.answer_photo(
            photo=photo, caption=greeting, reply_markup=get_main_menu(lang)
        )
    else:
        await message.answer(greeting, reply_markup=get_main_menu(lang))
