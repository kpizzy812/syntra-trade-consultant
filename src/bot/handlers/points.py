# coding: utf-8
"""
Handlers for $SYNTRA Points commands (/points, /level)
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User
from src.services.points_service import PointsService
from src.utils.i18n import i18n

router = Router(name="points")


@router.message(Command("points"))
async def cmd_points(
    message: Message,
    session: AsyncSession,
    user: User,
    user_language: str = "ru",
):
    """
    Show user's $SYNTRA points balance and level

    Args:
        message: Incoming message
        session: Database session (provided by DatabaseMiddleware)
        user: Database user object (provided by DatabaseMiddleware)
        user_language: User language (provided by LanguageMiddleware)
    """
    telegram_user = message.from_user
    logger.info(f"User {telegram_user.id} requested /points")

    try:
        # Get balance info
        balance_info = await PointsService.get_balance(session, user.id)

        if not balance_info:
            await message.answer(
                i18n.get("points.not_found", user_language),
                parse_mode="HTML"
            )
            return

        # Build response
        balance = balance_info["balance"]
        lifetime_earned = balance_info["lifetime_earned"]
        lifetime_spent = balance_info["lifetime_spent"]
        level = balance_info["level"]
        level_name = balance_info["level_name"]
        level_icon = balance_info["level_icon"]
        multiplier = balance_info["earning_multiplier"]
        current_streak = balance_info["current_streak"]
        longest_streak = balance_info["longest_streak"]
        next_level_points = balance_info["next_level_points"]
        progress = balance_info["progress_to_next_level"]

        # Build progress bar
        progress_bar_length = 10
        filled = int(progress * progress_bar_length)
        progress_bar = "▰" * filled + "▱" * (progress_bar_length - filled)

        # Response text
        response = f"💎 <b>$SYNTRA Points</b>\n\n"
        response += f"{level_icon} <b>Уровень {level}: {level_name}</b>\n"
        response += f"🎯 <b>Баланс:</b> {balance:,} поинтов\n"
        response += f"📈 <b>Множитель:</b> {multiplier}x\n\n"

        response += f"📊 <b>Статистика:</b>\n"
        response += f"   • Всего заработано: {lifetime_earned:,}\n"
        response += f"   • Всего потрачено: {lifetime_spent:,}\n\n"

        if current_streak > 0:
            streak_emoji = "🔥" if current_streak >= 7 else "⭐"
            response += f"{streak_emoji} <b>Streak:</b> {current_streak} дней подряд\n"
            response += f"🏆 <b>Лучший streak:</b> {longest_streak} дней\n\n"

        if next_level_points:
            response += f"<b>Прогресс до следующего уровня:</b>\n"
            response += f"{progress_bar} {int(progress * 100)}%\n"
            response += f"Осталось: {next_level_points:,} поинтов\n\n"
        else:
            response += f"🎉 <b>Вы достигли максимального уровня!</b>\n\n"

        response += f"<i>💡 Зарабатывайте поинты за запросы, покупки и рефералов!</i>"

        # Add inline buttons
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📜 История",
                        callback_data="points_history"
                    ),
                    InlineKeyboardButton(
                        text="🏆 Рейтинг",
                        callback_data="points_leaderboard"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="📊 Как заработать",
                        callback_data="points_how_to_earn"
                    ),
                ],
            ]
        )

        await message.answer(response, reply_markup=keyboard, parse_mode="HTML")

        logger.info(f"Points balance sent to user {user.id}: {balance} points, level {level}")

    except Exception as e:
        logger.exception(f"Error in /points command for user {user.id}: {e}")
        await message.answer(
            i18n.get("error.generic", user_language),
            parse_mode="HTML"
        )


@router.message(Command("level"))
async def cmd_level(
    message: Message,
    session: AsyncSession,
    user: User,
    user_language: str = "ru",
):
    """
    Show all available levels

    Args:
        message: Incoming message
        session: Database session
        user: Database user object
        user_language: User language
    """
    telegram_user = message.from_user
    logger.info(f"User {telegram_user.id} requested /level")

    try:
        from sqlalchemy import select
        from src.database.models import PointsLevel

        # Get all levels
        stmt = select(PointsLevel).order_by(PointsLevel.level)
        result = await session.execute(stmt)
        levels = result.scalars().all()

        # Get user's current level
        balance_info = await PointsService.get_balance(session, user.id)
        current_level = balance_info["level"] if balance_info else 1

        # Build response
        response = "🎯 <b>Уровни $SYNTRA Points</b>\n\n"

        for level in levels:
            level_marker = "👉 " if level.level == current_level else "   "
            level_status = " <b>(Ваш уровень)</b>" if level.level == current_level else ""

            response += f"{level_marker}{level.icon} <b>Уровень {level.level}: {level.name_ru}</b>{level_status}\n"
            response += f"   • Требуется: {level.points_required:,} поинтов\n"
            response += f"   • Множитель: {level.earning_multiplier}x\n"

            if level.description_ru:
                response += f"   • {level.description_ru}\n"

            response += "\n"

        response += "<i>💡 Повышайте уровень, чтобы получать больше поинтов!</i>"

        await message.answer(response, parse_mode="HTML")

        logger.info(f"Levels list sent to user {user.id}")

    except Exception as e:
        logger.exception(f"Error in /level command for user {user.id}: {e}")
        await message.answer(
            i18n.get("error.generic", user_language),
            parse_mode="HTML"
        )
