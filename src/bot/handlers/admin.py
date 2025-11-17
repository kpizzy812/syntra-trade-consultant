# coding: utf-8
"""
Admin panel handlers - statistics, user management, cost monitoring
"""
import logging
from datetime import datetime, timedelta, date, UTC
from typing import Optional

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command, CommandObject
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import (
    get_detailed_user_stats,
    get_total_costs,
    get_costs_by_service,
    get_costs_by_day,
    get_top_users_by_cost,
    get_all_users,
    get_users_count,
    search_users,
    get_user_by_telegram_id,
    reset_request_limit,
    log_admin_action,
)
from src.database.models import User


logger = logging.getLogger(__name__)
router = Router(name="admin")


def get_admin_main_menu() -> InlineKeyboardMarkup:
    """
    Create admin panel main menu keyboard

    Returns:
        InlineKeyboardMarkup with admin menu buttons
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
                InlineKeyboardButton(
                    text="👥 Пользователи", callback_data="admin_users_page_0"
                ),
            ],
            [
                InlineKeyboardButton(text="💰 Расходы", callback_data="admin_costs"),
                InlineKeyboardButton(text="📈 Графики", callback_data="admin_charts"),
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Настройки", callback_data="admin_settings"
                ),
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_refresh"),
            ],
        ]
    )
    return keyboard


def get_period_selector(callback_prefix: str) -> InlineKeyboardMarkup:
    """
    Create period selector keyboard

    Args:
        callback_prefix: Prefix for callback data

    Returns:
        InlineKeyboardMarkup with period buttons
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Сегодня", callback_data=f"{callback_prefix}_today"
                ),
                InlineKeyboardButton(
                    text="7 дней", callback_data=f"{callback_prefix}_7d"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="30 дней", callback_data=f"{callback_prefix}_30d"
                ),
                InlineKeyboardButton(
                    text="Все время", callback_data=f"{callback_prefix}_all"
                ),
            ],
            [
                InlineKeyboardButton(text="« Назад", callback_data="admin_refresh"),
            ],
        ]
    )
    return keyboard


@router.message(Command("admin", "admin_stats"))
async def cmd_admin(message: Message, session: AsyncSession):
    """
    Main admin panel command - show statistics and menu

    Usage: /admin or /admin_stats
    """
    user_id = message.from_user.id
    logger.info(f"Admin panel accessed by {user_id} (@{message.from_user.username})")

    try:
        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            # Get detailed statistics
            stats = await get_detailed_user_stats(session, days=7)

            # Get costs for today
            today_start = datetime.combine(date.today(), datetime.min.time())
            today_costs = await get_total_costs(session, start_date=today_start)

            # Get costs for last 7 days
            week_start = datetime.now(UTC) - timedelta(days=7)
            week_costs = await get_total_costs(session, start_date=week_start)

            # Format message
            response = "🔐 <b>Админ-панель Syntra</b>\n\n"

            response += "👥 <b>Пользователи:</b>\n"
            response += f"├ Всего: <b>{stats['total_users']}</b>\n"
            response += f"├ Подписанных: <b>{stats['subscribed_users']}</b>\n"
            response += f"├ Активных сегодня: <b>{stats['active_today']}</b>\n"
            response += f"├ Активных за 7д: <b>{stats['active_last_7d']}</b>\n"
            response += f"├ Новых за 7д: <b>{stats['new_users_7d']}</b>\n"
            response += f"└ Неактивных >7д: <b>{stats['inactive_7d']}</b>\n\n"

            response += "💰 <b>Расходы сегодня:</b>\n"
            response += f"├ Запросов: <b>{today_costs['request_count']}</b>\n"
            response += f"├ Токенов: <b>{today_costs['total_tokens']:,}</b>\n"
            response += f"└ Стоимость: <b>${today_costs['total_cost']:.4f}</b>\n\n"

            response += "📊 <b>Расходы за 7 дней:</b>\n"
            response += f"├ Запросов: <b>{week_costs['request_count']}</b>\n"
            response += f"├ Токенов: <b>{week_costs['total_tokens']:,}</b>\n"
            response += f"└ Стоимость: <b>${week_costs['total_cost']:.4f}</b>\n\n"

            response += (
                f"<i>Обновлено: {datetime.now(UTC).strftime('%H:%M:%S UTC')}</i>"
            )

            await message.answer(response, reply_markup=get_admin_main_menu())

            # Log admin action
            await log_admin_action(
                session,
                admin_id=user_id,
                action="view_stats",
                details="Viewed admin panel",
            )

    except Exception as e:
        logger.exception(f"Error in admin panel for user {user_id}: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при загрузке админ-панели</b>\n\n"
            "Попробуйте позже или обратитесь к разработчику."
        )


@router.callback_query(F.data == "admin_refresh")
async def admin_refresh_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Refresh admin panel - same as /admin command but for callback
    """
    user_id = callback.from_user.id

    try:
        # Get detailed statistics
        stats = await get_detailed_user_stats(session, days=7)

        # Get costs for today
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_costs = await get_total_costs(session, start_date=today_start)

        # Get costs for last 7 days
        week_start = datetime.now(UTC) - timedelta(days=7)
        week_costs = await get_total_costs(session, start_date=week_start)

        # Format message
        response = "🔐 <b>Админ-панель Syntra</b>\n\n"

        response += "👥 <b>Пользователи:</b>\n"
        response += f"├ Всего: <b>{stats['total_users']}</b>\n"
        response += f"├ Подписанных: <b>{stats['subscribed_users']}</b>\n"
        response += f"├ Активных сегодня: <b>{stats['active_today']}</b>\n"
        response += f"├ Активных за 7д: <b>{stats['active_last_7d']}</b>\n"
        response += f"├ Новых за 7д: <b>{stats['new_users_7d']}</b>\n"
        response += f"└ Неактивных >7д: <b>{stats['inactive_7d']}</b>\n\n"

        response += "💰 <b>Расходы сегодня:</b>\n"
        response += f"├ Запросов: <b>{today_costs['request_count']}</b>\n"
        response += f"├ Токенов: <b>{today_costs['total_tokens']:,}</b>\n"
        response += f"└ Стоимость: <b>${today_costs['total_cost']:.4f}</b>\n\n"

        response += "📊 <b>Расходы за 7 дней:</b>\n"
        response += f"├ Запросов: <b>{week_costs['request_count']}</b>\n"
        response += f"├ Токенов: <b>{week_costs['total_tokens']:,}</b>\n"
        response += f"└ Стоимость: <b>${week_costs['total_cost']:.4f}</b>\n\n"

        response += f"<i>Обновлено: {datetime.now(UTC).strftime('%H:%M:%S UTC')}</i>"

        await callback.message.edit_text(response, reply_markup=get_admin_main_menu())
        await callback.answer("✅ Обновлено")

    except Exception as e:
        logger.exception(f"Error refreshing admin panel for user {user_id}: {e}")
        await callback.answer("❌ Ошибка при обновлении", show_alert=True)


@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Show detailed statistics with period selector
    """
    response = "📊 <b>Детальная статистика</b>\n\n"
    response += "Выберите период для просмотра статистики:"

    await callback.message.edit_text(
        response, reply_markup=get_period_selector("admin_stats_period")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_stats_period_"))
async def admin_stats_period_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Show statistics for selected period
    """
    period = callback.data.split("_")[-1]
    user_id = callback.from_user.id

    try:
        # Determine date range based on period
        if period == "today":
            start_date = datetime.combine(date.today(), datetime.min.time())
            period_name = "сегодня"
            days = 1
        elif period == "7d":
            start_date = datetime.now(UTC) - timedelta(days=7)
            period_name = "за 7 дней"
            days = 7
        elif period == "30d":
            start_date = datetime.now(UTC) - timedelta(days=30)
            period_name = "за 30 дней"
            days = 30
        else:  # all
            start_date = None
            period_name = "за все время"
            days = 365

        # Get statistics
        stats = await get_detailed_user_stats(session, days=days)
        costs = await get_total_costs(session, start_date=start_date)
        costs_by_service = await get_costs_by_service(session, start_date=start_date)

        # Format message
        response = f"📊 <b>Статистика {period_name}</b>\n\n"

        response += "👥 <b>Пользователи:</b>\n"
        response += f"├ Всего: <b>{stats['total_users']}</b>\n"
        response += f"├ Подписанных: <b>{stats['subscribed_users']}</b>\n"
        response += f"└ Активных: <b>{stats.get(f'active_last_{days}d', stats['active_today'])}</b>\n\n"

        response += "💰 <b>Общие расходы:</b>\n"
        response += f"├ Запросов: <b>{costs['request_count']}</b>\n"
        response += f"├ Токенов: <b>{costs['total_tokens']:,}</b>\n"
        response += f"└ Стоимость: <b>${costs['total_cost']:.4f}</b>\n\n"

        if costs_by_service:
            response += "📈 <b>По сервисам:</b>\n"
            for service_data in costs_by_service:
                service = service_data["service"]
                model = service_data["model"] or "N/A"
                cost = service_data["total_cost"]
                response += f"├ {service} ({model}): <b>${cost:.4f}</b>\n"
            response += "\n"

        # Average cost per request
        if costs["request_count"] > 0:
            avg_cost = costs["total_cost"] / costs["request_count"]
            response += f"💵 <b>Средняя стоимость запроса:</b> ${avg_cost:.4f}\n\n"

        response += f"<i>Обновлено: {datetime.now(UTC).strftime('%H:%M:%S UTC')}</i>"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="« Назад к выбору периода", callback_data="admin_stats"
                    )
                ],
                [InlineKeyboardButton(text="« В меню", callback_data="admin_refresh")],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

        # Log admin action
        await log_admin_action(
            session,
            admin_id=user_id,
            action="view_stats_period",
            details=f"Period: {period}",
        )

    except Exception as e:
        logger.exception(f"Error showing stats for period {period}: {e}")
        await callback.answer("❌ Ошибка при загрузке статистики", show_alert=True)


@router.callback_query(F.data.startswith("admin_users_page_"))
async def admin_users_page_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Show users list with pagination and clickable user buttons
    """
    try:
        page = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        page = 0

    try:
        # Get users
        users_per_page = 5  # Reduced to fit buttons
        offset = page * users_per_page
        users = await get_all_users(
            session, offset=offset, limit=users_per_page, order_by="last_activity"
        )
        total_users = await get_users_count(session)
        total_pages = (total_users + users_per_page - 1) // users_per_page

        if not users:
            await callback.answer("Пользователи не найдены", show_alert=True)
            return

        # Format message
        response = f"👥 <b>Пользователи (страница {page+1}/{total_pages})</b>\n\n"
        response += "Нажмите на пользователя для управления:\n\n"

        # Build keyboard with user buttons
        buttons = []
        for i, user in enumerate(users, start=1):
            status = "✅" if user.is_subscribed else "❌"
            last_active = (
                user.last_activity.strftime("%d.%m %H:%M")
                if user.last_activity
                else "Никогда"
            )

            # Display info in message
            response += f"{status} <b>{i}.</b> "
            if user.first_name:
                response += f"{user.first_name} "
            if user.username:
                response += f"(@{user.username})"
            response += f"\n"
            response += f"   ID: <code>{user.telegram_id}</code> • {last_active}\n\n"

            # Add button for user
            user_label = user.first_name or user.username or f"ID {user.telegram_id}"
            user_label = user_label[:20]  # Limit label length
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"{status} {user_label}",
                        callback_data=f"admin_user_view_{user.id}",
                    )
                ]
            )

        response += f"<i>Всего пользователей: {total_users}</i>"

        # Navigation buttons
        nav_row = []
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"admin_users_page_{page-1}"
                )
            )
        nav_row.append(
            InlineKeyboardButton(
                text=f"{page+1}/{total_pages}", callback_data="admin_users_noop"
            )
        )
        if page < total_pages - 1:
            nav_row.append(
                InlineKeyboardButton(
                    text="➡️", callback_data=f"admin_users_page_{page+1}"
                )
            )
        buttons.append(nav_row)

        # Action buttons
        buttons.append(
            [
                InlineKeyboardButton(
                    text="🔍 Поиск", callback_data="admin_users_search"
                ),
                InlineKeyboardButton(text="« В меню", callback_data="admin_refresh"),
            ]
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing users page {page}: {e}")
        await callback.answer("❌ Ошибка при загрузке пользователей", show_alert=True)


@router.callback_query(F.data == "admin_users_noop")
async def admin_users_noop_callback(callback: CallbackQuery):
    """
    No-op callback for current page indicator
    """
    await callback.answer()


@router.callback_query(F.data == "admin_costs")
async def admin_costs_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Show costs overview with period selector
    """
    response = "💰 <b>Мониторинг расходов</b>\n\n"
    response += "Выберите период для просмотра расходов:"

    await callback.message.edit_text(
        response, reply_markup=get_period_selector("admin_costs_period")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_costs_period_"))
async def admin_costs_period_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Show costs for selected period
    """
    period = callback.data.split("_")[-1]
    user_id = callback.from_user.id

    try:
        # Determine date range
        if period == "today":
            start_date = datetime.combine(date.today(), datetime.min.time())
            period_name = "сегодня"
            days = 1
        elif period == "7d":
            start_date = datetime.now(UTC) - timedelta(days=7)
            period_name = "за 7 дней"
            days = 7
        elif period == "30d":
            start_date = datetime.now(UTC) - timedelta(days=30)
            period_name = "за 30 дней"
            days = 30
        else:  # all
            start_date = None
            period_name = "за все время"
            days = 7

        # Get costs data
        total_costs = await get_total_costs(session, start_date=start_date)
        costs_by_service = await get_costs_by_service(session, start_date=start_date)
        top_users = await get_top_users_by_cost(session, limit=5, start_date=start_date)

        if period != "all" and days <= 30:
            daily_costs = await get_costs_by_day(session, days=days)
        else:
            daily_costs = []

        # Format message
        response = f"💰 <b>Расходы {period_name}</b>\n\n"

        response += "📊 <b>Общая статистика:</b>\n"
        response += f"├ Запросов: <b>{total_costs['request_count']}</b>\n"
        response += f"├ Токенов: <b>{total_costs['total_tokens']:,}</b>\n"
        response += f"└ Стоимость: <b>${total_costs['total_cost']:.4f}</b>\n\n"

        if costs_by_service:
            response += "🔧 <b>По сервисам:</b>\n"
            for service_data in costs_by_service[:5]:  # Top 5
                service = service_data["service"]
                model = service_data["model"] or "Unknown"
                cost = service_data["total_cost"]
                tokens = service_data["total_tokens"]
                count = service_data["request_count"]
                response += f"├ <b>{service}</b> ({model})\n"
                response += f"│  ├ Запросов: {count}\n"
                response += f"│  ├ Токенов: {tokens:,}\n"
                response += f"│  └ Стоимость: ${cost:.4f}\n"
            response += "\n"

        if top_users:
            response += "👑 <b>Топ пользователей по расходам:</b>\n"
            for i, user_data in enumerate(top_users, start=1):
                name = user_data["first_name"] or user_data["username"] or "Unknown"
                cost = user_data["total_cost"]
                requests = user_data["request_count"]
                response += f"{i}. {name}: <b>${cost:.4f}</b> ({requests} зап.)\n"
            response += "\n"

        if daily_costs and len(daily_costs) > 1:
            response += "📅 <b>По дням (последние 5):</b>\n"
            for day_data in daily_costs[:5]:
                day_date = day_data["date"]
                day_cost = day_data["total_cost"]
                day_requests = day_data["request_count"]
                response += f"├ {day_date}: ${day_cost:.4f} ({day_requests} зап.)\n"
            response += "\n"

        # Average cost per request
        if total_costs["request_count"] > 0:
            avg_cost = total_costs["total_cost"] / total_costs["request_count"]
            avg_tokens = total_costs["total_tokens"] / total_costs["request_count"]
            response += "💵 <b>Средние показатели:</b>\n"
            response += f"├ За запрос: <b>${avg_cost:.4f}</b>\n"
            response += f"└ Токенов за запрос: <b>{avg_tokens:.0f}</b>\n\n"

        response += f"<i>Обновлено: {datetime.now(UTC).strftime('%H:%M:%S UTC')}</i>"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="« Назад к выбору периода", callback_data="admin_costs"
                    )
                ],
                [InlineKeyboardButton(text="« В меню", callback_data="admin_refresh")],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

        # Log admin action
        await log_admin_action(
            session, admin_id=user_id, action="view_costs", details=f"Period: {period}"
        )

    except Exception as e:
        logger.exception(f"Error showing costs for period {period}: {e}")
        await callback.answer("❌ Ошибка при загрузке расходов", show_alert=True)


@router.callback_query(F.data == "admin_charts")
async def admin_charts_callback(callback: CallbackQuery):
    """
    Placeholder for charts view
    """
    response = "📈 <b>Графики и аналитика</b>\n\n"
    response += "⚙️ <i>Функция в разработке</i>\n\n"
    response += "Скоро здесь будут доступны:\n"
    response += "• График расходов по дням\n"
    response += "• График активности пользователей\n"
    response += "• Распределение запросов по времени\n"
    response += "• Статистика использования моделей\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« В меню", callback_data="admin_refresh")]
        ]
    )

    await callback.message.edit_text(response, reply_markup=keyboard)
    await callback.answer("Функция скоро будет доступна", show_alert=True)


@router.callback_query(F.data == "admin_settings")
async def admin_settings_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Settings panel - global limits and configuration
    """
    from config.config import REQUEST_LIMIT_PER_DAY

    response = "⚙️ <b>Настройки бота</b>\n\n"
    response += "📊 <b>Глобальные параметры:</b>\n"
    response += (
        f"├ Лимит запросов (по умолчанию): <b>{REQUEST_LIMIT_PER_DAY}</b>/день\n"
    )
    response += f"└ Активных пользователей: <b>{await get_users_count(session)}</b>\n\n"

    response += "💡 <i>Здесь можно настроить глобальные параметры бота</i>"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📈 Изменить глобальный лимит",
                    callback_data="admin_settings_global_limit",
                ),
            ],
            [
                InlineKeyboardButton(text="« В меню", callback_data="admin_refresh"),
            ],
        ]
    )

    await callback.message.edit_text(response, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_settings_global_limit")
async def admin_settings_global_limit_callback(callback: CallbackQuery):
    """
    Show instructions for changing global limit
    """
    from config.config import REQUEST_LIMIT_PER_DAY

    response = "📈 <b>Изменение глобального лимита</b>\n\n"
    response += f"Текущий лимит: <b>{REQUEST_LIMIT_PER_DAY}</b> запросов/день\n\n"
    response += "⚙️ <b>Как изменить:</b>\n"
    response += "1. Откройте файл <code>.env</code>\n"
    response += "2. Найдите параметр <code>REQUEST_LIMIT_PER_DAY</code>\n"
    response += (
        "3. Измените значение (например: <code>REQUEST_LIMIT_PER_DAY=10</code>)\n"
    )
    response += "4. Перезапустите бота\n\n"
    response += "💡 <i>Новый лимит будет применен для всех новых пользователей.\n"
    response += (
        "Для существующих пользователей нужно установить индивидуальный лимит.</i>"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Назад", callback_data="admin_settings")],
            [InlineKeyboardButton(text="« В меню", callback_data="admin_refresh")],
        ]
    )

    await callback.message.edit_text(response, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_user_view_"))
async def admin_user_view_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Detailed user view with management actions
    """
    try:
        user_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID пользователя", show_alert=True)
        return

    try:
        from src.database.crud import check_request_limit, get_user_stats

        # Get user by internal ID
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Get user stats
        has_remaining, current_count, limit = await check_request_limit(
            session, user.id
        )
        remaining = limit - current_count

        # Format message
        response = "👤 <b>Профиль пользователя</b>\n\n"

        # Basic info
        response += "📝 <b>Основная информация:</b>\n"
        response += f"├ Имя: {user.first_name or 'N/A'}\n"
        if user.username:
            response += f"├ Username: @{user.username}\n"
        response += f"├ Telegram ID: <code>{user.telegram_id}</code>\n"
        response += f"├ Язык: {user.language.upper()}\n"
        response += f"└ Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"

        # Status
        response += "📊 <b>Статус:</b>\n"
        status_emoji = "✅" if user.is_subscribed else "❌"
        response += f"├ Подписка: {status_emoji} {'Активна' if user.is_subscribed else 'Неактивна'}\n"
        admin_emoji = "👑" if user.is_admin else "👤"
        response += f"├ Роль: {admin_emoji} {'Администратор' if user.is_admin else 'Пользователь'}\n"

        last_activity_str = (
            user.last_activity.strftime("%d.%m.%Y %H:%M")
            if user.last_activity
            else "Никогда"
        )
        response += f"└ Последняя активность: {last_activity_str}\n\n"

        # Limits
        response += "📈 <b>Лимиты (сегодня):</b>\n"
        response += f"├ Использовано: <b>{current_count} из {limit}</b>\n"
        response += f"├ Осталось: <b>{remaining}</b> запросов\n"

        if has_remaining:
            response += f"└ Статус: ✅ <b>Активен</b>\n"
        else:
            response += f"└ Статус: 🔴 <b>Исчерпан</b>\n"

        # Build action buttons
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Сбросить лимиты",
                        callback_data=f"admin_user_reset_{user.id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="📝 Установить лимит: 5",
                        callback_data=f"admin_user_setlimit_{user.id}_5",
                    ),
                    InlineKeyboardButton(
                        text="10", callback_data=f"admin_user_setlimit_{user.id}_10"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="15", callback_data=f"admin_user_setlimit_{user.id}_15"
                    ),
                    InlineKeyboardButton(
                        text="20", callback_data=f"admin_user_setlimit_{user.id}_20"
                    ),
                    InlineKeyboardButton(
                        text="50", callback_data=f"admin_user_setlimit_{user.id}_50"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="♾️ Безлимит (999)",
                        callback_data=f"admin_user_setlimit_{user.id}_999",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="« К списку", callback_data="admin_users_page_0"
                    ),
                    InlineKeyboardButton(
                        text="« В меню", callback_data="admin_refresh"
                    ),
                ],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error viewing user {user_id}: {e}")
        await callback.answer("❌ Ошибка при загрузке пользователя", show_alert=True)


@router.callback_query(F.data.startswith("admin_user_reset_"))
async def admin_user_reset_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Reset user limits via button
    """
    try:
        user_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID", show_alert=True)
        return

    try:
        # Get user
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Reset limits
        await reset_request_limit(session, user.id)

        # Log action
        await log_admin_action(
            session,
            admin_id=callback.from_user.id,
            action="reset_limits",
            target_user_id=user.telegram_id,
            details=f"Reset limits via button for {user.telegram_id} (@{user.username})",
        )

        await callback.answer("✅ Лимиты сброшены!", show_alert=True)

        # Refresh user view
        await admin_user_view_callback(
            CallbackQuery(
                id=callback.id,
                from_user=callback.from_user,
                chat_instance=callback.chat_instance,
                message=callback.message,
                data=f"admin_user_view_{user_id}",
            ),
            session,
        )

    except Exception as e:
        logger.exception(f"Error resetting user limits: {e}")
        await callback.answer("❌ Ошибка при сбросе лимитов", show_alert=True)


@router.callback_query(F.data.startswith("admin_user_setlimit_"))
async def admin_user_setlimit_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Set custom limit for user via button
    """
    try:
        parts = callback.data.split("_")
        user_id = int(parts[-2])
        new_limit = int(parts[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        return

    try:
        # Get user
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Set custom limit
        from src.database.crud import set_user_limit

        await set_user_limit(session, user.id, new_limit)

        # Log action
        await log_admin_action(
            session,
            admin_id=callback.from_user.id,
            action="set_limit",
            target_user_id=user.telegram_id,
            details=f"Set limit to {new_limit} for {user.telegram_id} (@{user.username})",
        )

        limit_text = "Безлимит" if new_limit >= 999 else f"{new_limit} запросов/день"
        await callback.answer(f"✅ Установлен лимит: {limit_text}", show_alert=True)

        # Refresh user view
        await admin_user_view_callback(
            CallbackQuery(
                id=callback.id,
                from_user=callback.from_user,
                chat_instance=callback.chat_instance,
                message=callback.message,
                data=f"admin_user_view_{user_id}",
            ),
            session,
        )

    except Exception as e:
        logger.exception(f"Error setting user limit: {e}")
        await callback.answer("❌ Ошибка при установке лимита", show_alert=True)


@router.message(Command("admin_limits"))
async def cmd_admin_limits(
    message: Message, command: CommandObject, session: AsyncSession
):
    """
    Manage user request limits

    Usage: /admin_limits <telegram_id> [reset]
    Example: /admin_limits 123456789
    Example: /admin_limits 123456789 reset
    """
    admin_id = message.from_user.id

    if not command.args:
        await message.answer(
            "📋 <b>Управление лимитами</b>\n\n"
            "Использование:\n"
            "<code>/admin_limits &lt;telegram_id&gt; [reset]</code>\n\n"
            "Примеры:\n"
            "• <code>/admin_limits 123456789</code> - посмотреть лимиты\n"
            "• <code>/admin_limits 123456789 reset</code> - сбросить лимиты\n\n"
            "Где <code>&lt;telegram_id&gt;</code> - ID пользователя в Telegram"
        )
        return

    args = command.args.strip().split()
    try:
        telegram_id = int(args[0])
    except (ValueError, IndexError):
        await message.answer(
            "❌ Неверный формат команды\n\n"
            "Telegram ID должен быть числом.\n"
            "Пример: <code>/admin_limits 123456789</code>"
        )
        return

    action = args[1].lower() if len(args) > 1 else "view"

    try:
        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            # Get user
            user = await get_user_by_telegram_id(session, telegram_id)

            if not user:
                await message.answer(
                    f"❌ Пользователь с ID <code>{telegram_id}</code> не найден в базе данных."
                )
                return

            # Get current limits
            from src.database.crud import check_request_limit

            has_remaining, current_count, limit = await check_request_limit(
                session, user.id
            )
            remaining = limit - current_count

            if action == "reset":
                # Reset user limits
                await reset_request_limit(session, user.id)

                # Log admin action
                await log_admin_action(
                    session,
                    admin_id=admin_id,
                    action="reset_limits",
                    target_user_id=telegram_id,
                    details=f"Reset limits for user {telegram_id} (@{user.username})",
                )

                response = f"✅ <b>Лимиты сброшены</b>\n\n"
                response += f"👤 Пользователь: {user.first_name or 'N/A'}"
                if user.username:
                    response += f" (@{user.username})"
                response += f"\n"
                response += f"🆔 Telegram ID: <code>{telegram_id}</code>\n\n"
                response += f"📊 Новые лимиты:\n"
                response += f"├ Использовано: <b>0 из {limit}</b>\n"
                response += f"└ Осталось: <b>{limit}</b> запросов\n\n"
                response += f"<i>Лимиты сброшены администратором</i>"

                await message.answer(response)
                logger.info(f"Admin {admin_id} reset limits for user {telegram_id}")

            else:  # view
                # Show current limits
                response = f"📊 <b>Лимиты пользователя</b>\n\n"
                response += f"👤 Пользователь: {user.first_name or 'N/A'}"
                if user.username:
                    response += f" (@{user.username})"
                response += f"\n"
                response += f"🆔 Telegram ID: <code>{telegram_id}</code>\n"
                response += (
                    f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n\n"
                )

                response += f"📈 <b>Текущие лимиты:</b>\n"
                response += f"├ Использовано: <b>{current_count} из {limit}</b>\n"
                response += f"├ Осталось: <b>{remaining}</b> запросов\n"

                if has_remaining:
                    response += f"└ Статус: ✅ <b>Активен</b>\n\n"
                else:
                    response += f"└ Статус: 🔴 <b>Исчерпан</b>\n\n"

                response += f"⚙️ <b>Действия:</b>\n"
                response += f"Для сброса лимитов используйте:\n"
                response += f"<code>/admin_limits {telegram_id} reset</code>"

                await message.answer(response)

                # Log admin action
                await log_admin_action(
                    session,
                    admin_id=admin_id,
                    action="view_limits",
                    target_user_id=telegram_id,
                    details=f"Viewed limits for user {telegram_id}",
                )

    except Exception as e:
        logger.exception(f"Error in admin limits command: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Попробуйте позже или проверьте правильность команды."
        )


@router.message(Command("admin_users"))
async def cmd_admin_users(
    message: Message, command: CommandObject, session: AsyncSession
):
    """
    Search users by ID or username

    Usage: /admin_users [search_query]
    Example: /admin_users 123456789
    Example: /admin_users @username
    """
    user_id = message.from_user.id

    if not command.args:
        # No search query - show first page of all users
        await message.answer("Перехожу к списку пользователей...")
        # Simulate callback
        from aiogram.types import CallbackQuery as FakeCallback

        # This is a workaround - better to refactor into a shared function
        await admin_users_page_callback(
            CallbackQuery(
                id="fake",
                from_user=message.from_user,
                chat_instance="fake",
                message=message,
                data="admin_users_page_0",
            ),
            session,
        )
        return

    search_query = command.args.strip()
    logger.info(f"Admin user search by {user_id}: {search_query}")

    try:
        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            # Search users
            users = await search_users(session, search_query, limit=10)

            if not users:
                await message.answer(
                    f"❌ Пользователи не найдены по запросу: <b>{search_query}</b>\n\n"
                    "Попробуйте другой запрос или используйте /admin_users для просмотра всех."
                )
                return

            # Format response
            response = f"🔍 <b>Результаты поиска: {search_query}</b>\n\n"
            response += f"Найдено пользователей: <b>{len(users)}</b>\n\n"

            for i, user in enumerate(users, start=1):
                status = "✅" if user.is_subscribed else "❌"
                last_active = (
                    user.last_activity.strftime("%d.%m.%Y %H:%M")
                    if user.last_activity
                    else "Никогда"
                )

                response += f"{status} <b>{i}.</b> "
                if user.first_name:
                    response += f"{user.first_name} "
                if user.username:
                    response += f"(@{user.username})"
                response += f"\n"
                response += f"   ID: <code>{user.telegram_id}</code>\n"
                response += f"   Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n"
                response += f"   Активность: {last_active}\n\n"

            await message.answer(response)

            # Log admin action
            await log_admin_action(
                session,
                admin_id=user_id,
                action="search_users",
                details=f"Query: {search_query}, Found: {len(users)}",
            )

    except Exception as e:
        logger.exception(f"Error in admin user search: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при поиске пользователей</b>\n\n"
            "Попробуйте позже."
        )
