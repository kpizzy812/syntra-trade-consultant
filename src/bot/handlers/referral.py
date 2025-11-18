# coding: utf-8
"""
Referral system handlers

Handles:
- /referral - Show referral menu
- /balance - Show and manage balance
- Referral statistics
- Leaderboard
- Balance withdrawal and spending
"""
import logging
from datetime import datetime, UTC

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import crud
from src.database.models import User
from src.utils.i18n import i18n


logger = logging.getLogger(__name__)

# Create router
router = Router(name="referral")


@router.message(Command("referral"))
async def cmd_referral(
    message: Message,
    session: AsyncSession,
    user: User,
    user_language: str = "ru",
) -> None:
    """
    Show referral system menu

    Args:
        message: Telegram message
        session: Database session
        user: User model
        user_language: User's language
    """
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
    bot_username = (await message.bot.me()).username
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

    # Keyboard
    keyboard = get_referral_menu_keyboard(user_language)

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("balance"))
async def cmd_balance(
    message: Message,
    session: AsyncSession,
    user: User,
    user_language: str = "ru",
) -> None:
    """
    Show balance menu

    Args:
        message: Telegram message
        session: Database session
        user: User model
        user_language: User's language
    """
    # Get balance
    balance = await crud.get_or_create_balance(session, user.id)

    # Calculate revenue share for last 30 days
    revenue_data = await crud.calculate_revenue_share(session, user.id)

    # Build text
    text = (
        f"{i18n.get('balance.title', user_language)}\n\n"
        f"{i18n.get('balance.current', user_language)}: <b>${balance.balance_usd:.2f}</b>\n"
        f"{i18n.get('balance.earned_total', user_language)}: ${balance.earned_total_usd:.2f}\n"
        f"{i18n.get('balance.withdrawn_total', user_language)}: ${balance.withdrawn_total_usd:.2f}\n"
        f"{i18n.get('balance.spent_total', user_language)}: ${balance.spent_total_usd:.2f}\n\n"
        f"{i18n.get('balance.revenue_share_30d', user_language)}: ${revenue_data['revenue_share_amount']:.2f}\n"
    )

    # Add withdrawal info if balance > 0
    if balance.balance_usd >= 10:
        text += f"\n{i18n.get('balance.can_withdraw', user_language)}"
    elif balance.balance_usd > 0:
        text += f"\n{i18n.get('balance.minimum_withdrawal', user_language)}"

    # Keyboard
    keyboard = get_balance_menu_keyboard(user_language, balance.balance_usd)

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


def get_referral_menu_keyboard(user_language: str = "ru") -> InlineKeyboardMarkup:
    """Get keyboard for referral menu"""
    buttons = [
        [
            InlineKeyboardButton(
                text=i18n.get('referral.share_button', user_language),
                switch_inline_query=i18n.get('referral.share_text', user_language),
            )
        ],
        [
            InlineKeyboardButton(
                text=i18n.get('referral.stats_button', user_language),
                callback_data="ref_stats",
            )
        ],
        [
            InlineKeyboardButton(
                text=i18n.get('referral.tiers_button', user_language),
                callback_data="ref_tiers",
            )
        ],
        [
            InlineKeyboardButton(
                text=i18n.get('referral.leaderboard_button', user_language),
                callback_data="ref_leaderboard",
            )
        ],
        [
            InlineKeyboardButton(
                text=i18n.get('referral.balance_button', user_language),
                callback_data="ref_balance",
            )
        ],
        [
            InlineKeyboardButton(
                text=i18n.get('back', user_language), callback_data="main_menu"
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_balance_menu_keyboard(
    user_language: str = "ru", balance: float = 0
) -> InlineKeyboardMarkup:
    """Get keyboard for balance menu"""
    buttons = []

    # Withdraw button (if balance >= $10)
    if balance >= 10:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=i18n.get('balance.withdraw_button', user_language),
                    callback_data="balance_withdraw",
                )
            ]
        )

    # Use balance button (if balance > $0)
    if balance > 0:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=i18n.get('balance.use_button', user_language),
                    callback_data="balance_use",
                )
            ]
        )

    # History button
    buttons.append(
        [
            InlineKeyboardButton(
                text=i18n.get('balance.history_button', user_language),
                callback_data="balance_history",
            )
        ]
    )

    # Back button
    buttons.append(
        [
            InlineKeyboardButton(
                text=i18n.get('back', user_language), callback_data="ref_menu"
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "ref_stats")
async def show_referral_stats(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    user_language: str = "ru",
) -> None:
    """Show detailed referral statistics"""
    stats = await crud.get_referral_stats(session, user.id)

    # Build detailed text
    tier_name = i18n.get(f'tier_names.{stats["tier"]}', user_language)
    text = (
        f"{i18n.get('referral_stats.title', user_language)}\n\n"
        f"{i18n.get('referral_stats.total', user_language)}: {stats['total_referrals']}\n"
        f"{i18n.get('referral_stats.active', user_language)}: {stats['active_referrals']}\n"
        f"{i18n.get('referral_stats.premium_converted', user_language)}: {stats['premium_conversions']}\n"
        f"{i18n.get('referral_stats.conversion_rate', user_language)}: {stats['conversion_rate']:.1f}%\n\n"
        f"{i18n.get('referral_stats.current_tier', user_language)}: {tier_name}\n"
    )

    # Next tier info
    next_tier_info = {
        "bronze": ("silver", 5),
        "silver": ("gold", 15),
        "gold": ("platinum", 50),
    }

    if stats['tier'] in next_tier_info:
        next_tier, needed = next_tier_info[stats['tier']]
        remaining = needed - stats['active_referrals']
        text += f"{i18n.get('referral_stats.next_tier', user_language)}: {i18n.get(f'tier_names.{next_tier}', user_language)} ({i18n.get('referral_stats.need_more', user_language).format(remaining)})\n"

    # Back button
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.get('back', user_language), callback_data="ref_menu"
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "ref_tiers")
async def show_tier_info(
    callback: CallbackQuery,
    user_language: str = "ru",
) -> None:
    """Show information about all tiers"""
    text = (
        f"{i18n.get('referral_tiers.title', user_language)}\n\n"
        f"🥉 <b>{i18n.get('tier_names.bronze', user_language)}</b> (0-4 {i18n.get('referral_tiers.referrals', user_language)})\n"
        f"{i18n.get('referral_tiers.bronze_desc', user_language)}\n\n"
        f"🥈 <b>{i18n.get('tier_names.silver', user_language)}</b> (5-14 {i18n.get('referral_tiers.referrals', user_language)})\n"
        f"{i18n.get('referral_tiers.silver_desc', user_language)}\n\n"
        f"🥇 <b>{i18n.get('tier_names.gold', user_language)}</b> (15-49 {i18n.get('referral_tiers.referrals', user_language)})\n"
        f"{i18n.get('referral_tiers.gold_desc', user_language)}\n\n"
        f"💎 <b>{i18n.get('tier_names.platinum', user_language)}</b> (50+ {i18n.get('referral_tiers.referrals', user_language)})\n"
        f"{i18n.get('referral_tiers.platinum_desc', user_language)}\n"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.get('back', user_language), callback_data="ref_menu"
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "ref_leaderboard")
async def show_leaderboard(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    user_language: str = "ru",
) -> None:
    """Show referral leaderboard"""
    leaderboard = await crud.get_leaderboard(session, limit=10)

    text = f"{i18n.get('referral_leaderboard.title', user_language)}\n\n"

    # Medals for top 3
    medals = ["🥇", "🥈", "🥉"]

    for entry in leaderboard[:10]:
        rank = entry['rank']
        medal = medals[rank - 1] if rank <= 3 else f"{rank}."
        username = entry['username'] or entry['first_name'] or "Anonymous"

        tier_emoji = {"bronze": "🥉", "silver": "🥈", "gold": "🥇", "platinum": "💎"}.get(
            entry['tier'], "🥉"
        )

        text += f"{medal} @{username} — {entry['active_referrals']} {tier_emoji}\n"

    # User's rank
    user_rank = await crud.get_leaderboard_rank(session, user.id)
    if user_rank and user_rank > 10:
        stats = await crud.get_referral_stats(session, user.id)
        text += f"\n...\n{user_rank}. {i18n.get('referral_leaderboard.you', user_language)} — {stats['active_referrals']}"

    text += f"\n\n{i18n.get('referral_leaderboard.rewards', user_language)}"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.get('back', user_language), callback_data="ref_menu"
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "ref_balance")
async def show_balance_from_ref(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    user_language: str = "ru",
) -> None:
    """Show balance from referral menu"""
    # Get balance
    balance = await crud.get_or_create_balance(session, user.id)

    # Calculate revenue share
    revenue_data = await crud.calculate_revenue_share(session, user.id)

    text = (
        f"{i18n.get('balance.title', user_language)}\n\n"
        f"{i18n.get('balance.current', user_language)}: <b>${balance.balance_usd:.2f}</b>\n"
        f"{i18n.get('balance.earned_total', user_language)}: ${balance.earned_total_usd:.2f}\n"
        f"{i18n.get('balance.revenue_share_30d', user_language)}: ${revenue_data['revenue_share_amount']:.2f}\n\n"
    )

    if balance.balance_usd >= 10:
        text += f"{i18n.get('balance.can_withdraw', user_language)}"
    elif balance.balance_usd > 0:
        text += f"{i18n.get('balance.minimum_withdrawal', user_language)}"

    keyboard = get_balance_menu_keyboard(user_language, balance.balance_usd)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "balance_withdraw")
async def request_withdrawal(
    callback: CallbackQuery,
    user_language: str = "ru",
) -> None:
    """Request balance withdrawal"""
    text = (
        f"{i18n.get('balance_withdrawal.title', user_language)}\n\n"
        f"{i18n.get('balance_withdrawal.instructions', user_language)}\n\n"
        f"{i18n.get('balance_withdrawal.minimum', user_language)}: $10\n"
        f"{i18n.get('balance_withdrawal.fee', user_language)}: 5%\n"
        f"{i18n.get('balance_withdrawal.supported', user_language)}: TON, USDT (TON)\n\n"
        f"{i18n.get('balance_withdrawal.coming_soon', user_language)}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.get('back', user_language), callback_data="ref_balance"
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "balance_use")
async def use_balance_for_subscription(
    callback: CallbackQuery,
    user_language: str = "ru",
) -> None:
    """Use balance for subscription purchase"""
    text = (
        f"{i18n.get('balance_use.title', user_language)}\n\n"
        f"{i18n.get('balance_use.bonus_discount', user_language)}: +20%\n\n"
        f"{i18n.get('balance_use.instructions', user_language)}\n\n"
        f"{i18n.get('balance_use.coming_soon', user_language)}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.get('back', user_language), callback_data="ref_balance"
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "balance_history")
async def show_balance_history(
    callback: CallbackQuery,
    user_language: str = "ru",
) -> None:
    """Show balance transaction history"""
    text = (
        f"{i18n.get('balance_history.title', user_language)}\n\n"
        f"{i18n.get('balance_history.coming_soon', user_language)}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.get('back', user_language), callback_data="ref_balance"
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "ref_menu")
async def back_to_referral_menu(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    user_language: str = "ru",
) -> None:
    """Go back to referral menu"""
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

    # Build text
    tier_name = i18n.get(f'tier_names.{stats["tier"]}', user_language)
    text = (
        f"{i18n.get('referral.title', user_language)}\n\n"
        f"{i18n.get('referral.your_code', user_language)}: <code>{user.referral_code}</code>\n"
        f"{i18n.get('referral.your_link', user_language)}:\n<code>{ref_link}</code>\n\n"
        f"{tier_emoji} {i18n.get('referral.tier', user_language)}: <b>{tier_name}</b>\n"
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

    # Keyboard
    keyboard = get_referral_menu_keyboard(user_language)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
