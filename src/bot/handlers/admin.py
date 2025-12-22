# coding: utf-8
"""
Admin panel handlers - statistics, user management, cost monitoring
"""
from datetime import datetime, timedelta, date, UTC
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.chat_action import ChatActionSender
from aiogram.exceptions import TelegramBadRequest
from loguru import logger
from sqlalchemy import select, func, Integer, case, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


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
    get_business_metrics,
    get_mrr,
    get_profit_loss,
    get_churn_rate,
    get_revenue_stats,
    get_subscription_stats,
    get_subscription,
    activate_subscription,
    deactivate_subscription,
    update_subscription,
    get_expiring_subscriptions,
    get_expired_subscriptions,
    get_all_payments,
)
from src.database.models import User, Subscription, Payment, SubscriptionTier, PaymentStatus, Referral, ReferralBalance
from src.services.unit_economics_service import (
    get_unit_economics_dashboard,
    get_tier_margin_with_fees,
    get_free_tier_economics,
    get_trial_economics,
    get_referral_economics,
    get_margin_scenarios,
)

router = Router(name="admin")


# ===========================
# FSM States
# ===========================

class AdminUserStates(StatesGroup):
    """FSM states for admin user management"""
    waiting_for_limit = State()  # Ожидание ввода лимита


def get_user_display_name(user: User) -> str:
    """Get display name for user (first_name, username, email part, or ID)"""
    if user.first_name:
        return user.first_name
    if user.username:
        return user.username
    if user.email:
        return user.email.split('@')[0]
    return f"ID {user.id}"


def get_user_identifier(user: User) -> str:
    """Get user identifier string (telegram_id or email)"""
    if user.telegram_id:
        return f"TG: <code>{user.telegram_id}</code>"
    if user.email:
        return f"📧 {user.email}"
    return f"ID: <code>{user.id}</code>"


async def safe_edit_message(
    callback: CallbackQuery, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None
) -> bool:
    """
    Safely edit message, handling "message is not modified" error

    Args:
        callback: Callback query
        text: New message text
        reply_markup: Optional keyboard

    Returns:
        bool: True if message was edited, False if it was already the same
    """
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return False
        raise


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
                InlineKeyboardButton(text="💎 Подписки", callback_data="admin_subscriptions"),
                InlineKeyboardButton(text="💳 Платежи", callback_data="admin_payments"),
            ],
            [
                InlineKeyboardButton(text="💰 Расходы", callback_data="admin_costs"),
                InlineKeyboardButton(text="📈 Графики", callback_data="admin_charts"),
            ],
            [
                InlineKeyboardButton(
                    text="📢 Рассылка", callback_data="admin_broadcast"
                ),
                InlineKeyboardButton(
                    text="📊 Unit Economics", callback_data="admin_unit_economics"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🚨 Fraud Detection", callback_data="admin_fraud"
                ),
                InlineKeyboardButton(
                    text="📋 Задания", callback_data="admin_tasks"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔗 Startapp Stats", callback_data="admin_startapp"
                ),
                InlineKeyboardButton(
                    text="⚙️ Настройки", callback_data="admin_settings"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📚 Class Stats", callback_data="admin_class_stats"
                ),
                InlineKeyboardButton(
                    text="🧠 Learning", callback_data="admin_learning"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🧪 Forward Test", callback_data="admin_forward_test"
                ),
                InlineKeyboardButton(
                    text="📊 Portfolio", callback_data="admin_portfolio"
                ),
            ],
            [
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

            # Referral stats
            from src.database.crud import get_referral_conversion_rate
            from sqlalchemy import func

            # Get total referrals count
            stmt = select(func.count(Referral.id))
            result = await session.execute(stmt)
            total_referrals = result.scalar() or 0

            # Get active referrals count
            stmt = select(func.count(Referral.id)).where(Referral.status == "active")
            result = await session.execute(stmt)
            active_referrals = result.scalar() or 0

            # Get total referral earnings
            stmt = select(func.sum(ReferralBalance.earned_total_usd))
            result = await session.execute(stmt)
            total_earnings = result.scalar() or 0

            response += "🤝 <b>Реферальная система:</b>\n"
            response += f"├ Всего рефералов: <b>{total_referrals}</b>\n"
            response += f"├ Активных: <b>{active_referrals}</b>\n"
            response += f"└ Выплачено: <b>${total_earnings:.2f}</b>\n\n"

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

        was_edited = await safe_edit_message(callback, response, get_admin_main_menu())
        if was_edited:
            await callback.answer("✅ Обновлено")
        else:
            await callback.answer("✅ Уже актуально")

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
            start_date = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=UTC)
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
            # Check premium subscription status (not channel subscription!)
            has_active_premium = False
            if user.subscription and user.subscription.is_active:
                # Active if: tier is not FREE OR (FREE and no expiry) OR not expired
                if user.subscription.tier != SubscriptionTier.FREE:
                    has_active_premium = True
                elif user.subscription.expires_at is None or user.subscription.expires_at > datetime.now(UTC):
                    has_active_premium = True

            status = "✅" if has_active_premium else "❌"
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
            # Show telegram_id or email for web users
            if user.telegram_id:
                response += f"   TG: <code>{user.telegram_id}</code> • {last_active}\n\n"
            elif user.email:
                response += f"   📧 {user.email} • {last_active}\n\n"
            else:
                response += f"   ID: <code>{user.id}</code> • {last_active}\n\n"

            # Add button for user - handle email users
            user_label = user.first_name or user.username or (user.email.split('@')[0] if user.email else f"ID {user.id}")
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
            start_date = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=UTC)
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
                # Support web users (email) and telegram users (first_name/username)
                email = user_data.get("email")
                name = user_data["first_name"] or user_data["username"] or (email.split('@')[0] if email else "Unknown")
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
async def admin_charts_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Business metrics dashboard with period selector
    """
    response = "📈 <b>Бизнес-метрики и аналитика</b>\n\n"
    response += "Выберите период для просмотра финансовых показателей:"

    await callback.message.edit_text(
        response, reply_markup=get_period_selector("admin_charts_period")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_charts_period_"))
async def admin_charts_period_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Show business metrics for selected period
    """
    period = callback.data.split("_")[-1]
    user_id = callback.from_user.id

    try:
        # Determine date range based on period
        if period == "today":
            start_date = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=UTC)
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

        # Get business metrics
        mrr_data = await get_mrr(session)
        profit_data = await get_profit_loss(session, start_date=start_date)
        churn_data = await get_churn_rate(session, days=days)
        subscription_stats = await get_subscription_stats(session)
        revenue_data = await get_revenue_stats(session, start_date=start_date)
        user_stats = await get_detailed_user_stats(session, days=days)

        # Calculate additional metrics
        total_users = user_stats["total_users"]
        paying_users = subscription_stats["total_active"]
        conversion_rate = (paying_users / total_users * 100) if total_users > 0 else 0
        arpu = (mrr_data["total_mrr"] / paying_users) if paying_users > 0 else 0

        # Get revenue share data
        stmt_revshare = select(func.sum(ReferralBalance.earned_total_usd))
        result_revshare = await session.execute(stmt_revshare)
        total_revshare = float(result_revshare.scalar() or 0)

        # Format response
        response = f"📈 <b>Бизнес-метрики {period_name}</b>\n\n"

        # Financial overview
        response += "💰 <b>Финансовые показатели:</b>\n"
        response += f"├ Ежемесячный доход (MRR): <b>${mrr_data['total_mrr']:.2f}</b>\n"
        response += f"├ Доход за период: <b>${revenue_data['total_revenue']:.2f}</b>\n"
        response += f"├ Расходы (API): <b>${profit_data['costs']:.2f}</b>\n"
        response += f"├ Ревшар выплачено: <b>${total_revshare:.2f}</b>\n"

        # Profit/Loss with visual indicator (INCLUDING revshare)
        profit_before_revshare = profit_data["profit"]
        profit_after_revshare = profit_before_revshare - total_revshare
        margin = (profit_after_revshare / revenue_data['total_revenue'] * 100) if revenue_data['total_revenue'] > 0 else 0
        is_profitable = profit_after_revshare >= 0

        if is_profitable:
            profit_status = f"<b>+${profit_after_revshare:.2f}</b> ✅"
            margin_emoji = "📈"
        else:
            profit_status = f"<b>-${abs(profit_after_revshare):.2f}</b> ❌"
            margin_emoji = "📉"

        response += f"└ Чистая прибыль: {profit_status} ({margin_emoji} {margin:.1f}% рентабельность)\n\n"

        # Overall status
        if is_profitable:
            response += "🎯 <b>Статус:</b> <b>В ПЛЮСЕ</b> ✅\n\n"
        else:
            response += "⚠️ <b>Статус:</b> <b>В МИНУСЕ</b> ❌\n\n"

        # Key metrics
        response += "📊 <b>Ключевые метрики:</b>\n"
        response += f"├ Средний доход с юзера: <b>${arpu:.2f}</b>/мес\n"
        response += f"├ Конверсия (free→paid): <b>{conversion_rate:.1f}%</b> ({paying_users}/{total_users})\n"
        response += f"├ Отток (Churn): <b>{churn_data['churn_rate_percent']:.1f}%</b>\n"
        response += f"└ Платящих юзеров: <b>{paying_users}</b>\n\n"

        # Subscription breakdown
        if mrr_data["by_tier"]:
            response += "💎 <b>Распределение по тарифам:</b>\n"

            # Import prices dynamically to avoid hardcoding
            from src.services.telegram_stars_service import SUBSCRIPTION_PLANS
            from src.database.models import SubscriptionTier

            tier_names = {
                "free": "FREE",
                "basic": f"BASIC (${SUBSCRIPTION_PLANS[SubscriptionTier.BASIC]['1']['usd']:.2f})",
                "premium": f"PREMIUM (${SUBSCRIPTION_PLANS[SubscriptionTier.PREMIUM]['1']['usd']:.2f})",
                "vip": f"VIP (${SUBSCRIPTION_PLANS[SubscriptionTier.VIP]['1']['usd']:.2f})"
            }
            for tier, tier_data in mrr_data["by_tier"].items():
                tier_name = tier_names.get(tier, tier.upper())
                count = tier_data["count"]
                mrr_tier = tier_data["mrr"]
                if mrr_tier > 0:  # Only show paid tiers
                    response += f"├ {tier_name}: {count} юз. → <b>${mrr_tier:.2f}</b>/мес\n"
            response += "\n"

        # User activity
        response += "👥 <b>Активность пользователей:</b>\n"
        response += f"├ Всего: <b>{total_users}</b>\n"
        response += f"├ Подписанных на канал: <b>{user_stats['subscribed_users']}</b>\n"
        if days == 1:
            response += f"└ Активных сегодня: <b>{user_stats['active_today']}</b>\n\n"
        else:
            response += f"└ Активных за период: <b>{user_stats.get(f'active_last_{days}d', 0)}</b>\n\n"

        # Help section
        response += "━━━━━━━━━━━━━━━━━━━\n"
        response += "📖 <b>Расшифровка:</b>\n"
        response += "• <b>MRR</b> — Monthly Recurring Revenue (повторяющийся доход/мес)\n"
        response += "• <b>Churn</b> — процент отменивших подписку\n"
        response += "• <b>Рентабельность</b> — доля прибыли от дохода\n\n"

        response += f"<i>Обновлено: {datetime.now(UTC).strftime('%H:%M:%S UTC')}</i>"

        # Navigation keyboard
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="« Назад к выбору периода", callback_data="admin_charts"
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
            action="view_business_metrics",
            details=f"Period: {period}",
        )

    except Exception as e:
        logger.exception(f"Error showing business metrics for period {period}: {e}")
        await callback.answer("❌ Ошибка при загрузке метрик", show_alert=True)


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
async def admin_user_view_callback(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
):
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

        # Get user by internal ID with eager loading for relationships
        stmt = (
            select(User)
            .options(
                selectinload(User.subscription),
                selectinload(User.payments)
            )
            .where(User.id == user_id)
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Get subscription from eager-loaded relationship
        subscription = user.subscription

        # Get referral balance separately
        stmt_bal = select(ReferralBalance).where(ReferralBalance.user_id == user.id)
        result_bal = await session.execute(stmt_bal)
        referral_balance = result_bal.scalar_one_or_none()

        # Get user stats
        has_remaining, current_count, limit = await check_request_limit(
            session, user
        )
        remaining = limit - current_count

        # Format message
        response = "👤 <b>Профиль пользователя</b>\n\n"

        # Basic info
        response += "📝 <b>Основная информация:</b>\n"
        response += f"├ Имя: {user.first_name or 'N/A'}\n"
        if user.username:
            response += f"├ Username: @{user.username}\n"
        # Show telegram_id or email depending on registration type
        if user.telegram_id:
            response += f"├ Telegram ID: <code>{user.telegram_id}</code>\n"
        if user.email:
            verified = "✅" if user.email_verified else "❌"
            response += f"├ Email: {user.email} {verified}\n"
        # Show registration platform for clarity
        platform_icons = {"telegram": "📱", "web": "🌐", "ios": "🍎", "android": "🤖"}
        platform_icon = platform_icons.get(user.registration_platform, "📱")
        response += f"├ Платформа: {platform_icon} {user.registration_platform.upper()}\n"
        response += f"├ Язык: {user.language.upper()}\n"
        response += f"└ Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"

        # Status
        response += "📊 <b>Статус:</b>\n"

        # Check premium subscription status (not channel subscription!)
        # subscription уже загружен выше отдельным запросом
        has_active_premium = False
        if subscription and subscription.is_active:
            # Active if: tier is not FREE OR (FREE and no expiry) OR not expired
            if subscription.tier != SubscriptionTier.FREE:
                has_active_premium = True
            elif subscription.expires_at is None or subscription.expires_at > datetime.now(UTC):
                has_active_premium = True

        status_emoji = "✅" if has_active_premium else "❌"
        response += f"├ Подписка: {status_emoji} {'Активна' if has_active_premium else 'Неактивна'}\n"
        admin_emoji = "👑" if user.is_admin else "👤"
        response += f"├ Роль: {admin_emoji} {'Администратор' if user.is_admin else 'Пользователь'}\n"
        if user.is_banned:
            response += f"├ Статус: 🚫 <b>ЗАБАНЕН</b>\n"

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

        # Show custom limit if set
        if user.custom_daily_limit is not None:
            response += f"├ Кастомный лимит: <b>{user.custom_daily_limit}</b> ✏️\n"

        if has_remaining:
            response += f"└ Статус: ✅ <b>Активен</b>\n\n"
        else:
            response += f"└ Статус: 🔴 <b>Исчерпан</b>\n\n"

        # Subscription info
        if subscription:
            tier_emoji = {
                "free": "🆓",
                "basic": "⭐",
                "premium": "💎",
                "vip": "👑",
            }
            emoji = tier_emoji.get(
                subscription.tier.value if hasattr(subscription.tier, 'value') else subscription.tier,
                "💎"
            )

            response += "💎 <b>Подписка:</b>\n"
            response += f"├ Тариф: {emoji} <b>{subscription.tier.upper()}</b>\n"

            if subscription.expires_at:
                days_left = (subscription.expires_at - datetime.now(UTC)).days
                response += f"├ Истекает: {subscription.expires_at.strftime('%d.%m.%Y')}"
                if days_left >= 0:
                    response += f" (через {days_left} дн.)\n"
                else:
                    response += f" (истекла)\n"
            else:
                response += f"├ Период: Бессрочно (FREE)\n"

            auto_renew_text = "Да" if subscription.auto_renew else "Нет"
            response += f"└ Автопродление: {auto_renew_text}\n\n"

            # Recent payments - use eager-loaded relationship
            user_payments = sorted(
                user.payments,
                key=lambda p: p.created_at,
                reverse=True
            )[:3]
            if user_payments:
                response += "💳 <b>Последние платежи:</b>\n"
                for payment in user_payments:
                    status_emoji = {
                        "completed": "✅",
                        "pending": "⏳",
                        "failed": "❌",
                    }
                    p_emoji = status_emoji.get(
                        payment.status.value if hasattr(payment.status, 'value') else payment.status,
                        "💳"
                    )
                    response += f"├ {p_emoji} ${payment.amount:.2f} • {payment.created_at.strftime('%d.%m.%Y')}\n"
                response += "\n"

        # Referral info
        from src.database.crud import get_referral_stats, get_referrer

        referral_stats = await get_referral_stats(session, user.id)
        referrer = await get_referrer(session, user.id)

        response += "🤝 <b>Реферальная система:</b>\n"

        # Referrer info
        if referrer:
            referrer_name = f"@{referrer.username}" if referrer.username else referrer.first_name or "Unknown"
            response += f"├ Пригласитель: {referrer_name}\n"
        else:
            response += f"├ Пригласитель: Нет (самостоятельно)\n"

        # Referral stats
        response += f"├ Всего рефералов: <b>{referral_stats['total_referrals']}</b>\n"
        response += f"├ Активных: <b>{referral_stats['active_referrals']}</b>\n"

        # Tier
        tier_emojis = {
            "bronze": "🥉",
            "silver": "🥈",
            "gold": "🥇",
            "platinum": "💎",
        }
        tier_emoji = tier_emojis.get(referral_stats['tier'], "🥉")
        response += f"├ Уровень: {tier_emoji} <b>{referral_stats['tier'].upper()}</b>\n"

        # Balance
        balance = float(referral_balance.balance_usd if referral_balance else 0)
        total_earned = float(referral_balance.earned_total_usd if referral_balance else 0)
        response += f"├ Баланс: <b>${balance:.2f}</b>\n"
        response += f"└ Всего заработано: <b>${total_earned:.2f}</b>\n\n"

        # Build compact action buttons
        buttons = []

        # Row 1: Subscription + Limit input
        buttons.append([
            InlineKeyboardButton(
                text="💎 Подписка",
                callback_data=f"admin_user_sub_menu_{user.id}"
            ),
            InlineKeyboardButton(
                text="📝 Задать лимит",
                callback_data=f"admin_user_input_limit_{user.id}"
            ),
        ])

        # Row 2: Reset limits + clear custom limit (if set)
        limit_row = [
            InlineKeyboardButton(
                text="🔄 Сбросить счётчик",
                callback_data=f"admin_user_reset_{user.id}",
            ),
        ]
        # Show "К тарифу" button only if custom limit is set
        if user.custom_daily_limit is not None:
            limit_row.append(
                InlineKeyboardButton(
                    text="🗑 К тарифу",
                    callback_data=f"admin_user_clear_limit_{user.id}",
                )
            )
        buttons.append(limit_row)

        # Row 3: Admin toggle + Ban toggle
        admin_btn_text = "👤 Снять админа" if user.is_admin else "👑 Сделать админом"
        ban_btn_text = "✅ Разбанить" if user.is_banned else "🚫 Забанить"

        buttons.append([
            InlineKeyboardButton(
                text=admin_btn_text,
                callback_data=f"admin_user_toggle_admin_{user.id}"
            ),
            InlineKeyboardButton(
                text=ban_btn_text,
                callback_data=f"admin_user_toggle_ban_{user.id}"
            ),
        ])

        # Row 4: Navigation
        buttons.append([
            InlineKeyboardButton(
                text="« К списку", callback_data="admin_users_page_0"
            ),
            InlineKeyboardButton(
                text="« В меню", callback_data="admin_refresh"
            ),
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(response, reply_markup=keyboard)

        # Try to answer callback (may already be answered if called from another handler)
        try:
            await callback.answer()
        except Exception:
            pass  # Callback already answered

    except Exception as e:
        logger.exception(f"Error viewing user {user_id}: {e}")
        try:
            await callback.answer("❌ Ошибка при загрузке пользователя", show_alert=True)
        except Exception:
            pass  # Callback already answered


@router.callback_query(F.data.startswith("admin_user_reset_"))
async def admin_user_reset_callback(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
):
    """
    Reset user limits via button
    """
    try:
        user_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID", show_alert=True)
        return

    try:
        # Get user with eager loading
        stmt = select(User).options(selectinload(User.subscription)).where(User.id == user_id)
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

        # Refresh user view - update callback data and reuse the callback
        original_data = callback.data
        callback.data = f"admin_user_view_{user_id}"
        await admin_user_view_callback(callback, session, bot)
        callback.data = original_data  # Restore original data

    except Exception as e:
        logger.exception(f"Error resetting user limits: {e}")
        await callback.answer("❌ Ошибка при сбросе лимитов", show_alert=True)


@router.callback_query(F.data.startswith("admin_user_setlimit_"))
async def admin_user_setlimit_callback(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
):
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
        # Get user with eager loading
        stmt = select(User).options(selectinload(User.subscription)).where(User.id == user_id)
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

        # Refresh user view - update callback data and reuse the callback
        original_data = callback.data
        callback.data = f"admin_user_view_{user_id}"
        await admin_user_view_callback(callback, session, bot)
        callback.data = original_data  # Restore original data

    except Exception as e:
        logger.exception(f"Error setting user limit: {e}")
        await callback.answer("❌ Ошибка при установке лимита", show_alert=True)


# ===========================
# FSM: Input limit
# ===========================

@router.callback_query(F.data.startswith("admin_user_input_limit_"))
async def admin_user_input_limit_callback(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """Start FSM for limit input"""
    try:
        user_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID", show_alert=True)
        return

    # Save user_id to state
    await state.set_state(AdminUserStates.waiting_for_limit)
    await state.update_data(target_user_id=user_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_user_view_{user_id}")]
    ])

    await callback.message.edit_text(
        "📝 <b>Введите новый дневной лимит запросов</b>\n\n"
        "Отправьте число от 1 до 999\n"
        "999 = безлимит",
        reply_markup=keyboard
    )
    await callback.answer()


@router.message(StateFilter(AdminUserStates.waiting_for_limit))
async def process_limit_input(
    message: Message, session: AsyncSession, state: FSMContext
):
    """Process limit input from FSM"""
    data = await state.get_data()
    user_id = data.get("target_user_id")

    if not user_id:
        await state.clear()
        await message.answer("❌ Ошибка: пользователь не найден")
        return

    # Validate input
    try:
        new_limit = int(message.text.strip())
        if new_limit < 1 or new_limit > 999:
            raise ValueError("Invalid range")
    except ValueError:
        await message.answer("❌ Введите число от 1 до 999")
        return

    try:
        # Get user
        stmt = select(User).options(selectinload(User.subscription)).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await state.clear()
            await message.answer("❌ Пользователь не найден")
            return

        # Set limit
        from src.database.crud import set_user_limit
        await set_user_limit(session, user.id, new_limit)

        # Log action
        await log_admin_action(
            session,
            admin_id=message.from_user.id,
            action="set_limit",
            target_user_id=user.telegram_id or user.id,
            details=f"Set limit to {new_limit} for user {user.id} via FSM",
        )

        await state.clear()

        limit_text = "Безлимит" if new_limit >= 999 else f"{new_limit} запросов/день"
        await message.answer(f"✅ Установлен лимит: {limit_text}")

        # Show user card again
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Вернуться к карточке", callback_data=f"admin_user_view_{user_id}")]
        ])
        await message.answer("Нажмите для возврата:", reply_markup=keyboard)

    except Exception as e:
        logger.exception(f"Error setting limit via FSM: {e}")
        await state.clear()
        await message.answer("❌ Ошибка при установке лимита")


# ===========================
# Subscription submenu
# ===========================

@router.callback_query(F.data.startswith("admin_user_sub_menu_"))
async def admin_user_sub_menu_callback(
    callback: CallbackQuery, session: AsyncSession
):
    """Show subscription management submenu"""
    try:
        user_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID", show_alert=True)
        return

    try:
        # Get user with subscription
        stmt = select(User).options(selectinload(User.subscription)).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        subscription = user.subscription
        current_tier = subscription.tier if subscription else "free"

        # Build response
        response = f"💎 <b>Управление подпиской</b>\n"
        response += f"👤 {get_user_display_name(user)}\n\n"

        tier_emojis = {"free": "🆓", "basic": "⭐", "premium": "💎", "vip": "👑"}
        current_emoji = tier_emojis.get(current_tier.lower() if isinstance(current_tier, str) else current_tier.value, "🆓")

        response += f"Текущий тариф: {current_emoji} <b>{current_tier.upper() if isinstance(current_tier, str) else current_tier.value.upper()}</b>\n"

        if subscription and subscription.expires_at:
            days_left = (subscription.expires_at - datetime.now(UTC)).days
            response += f"Истекает: {subscription.expires_at.strftime('%d.%m.%Y')} ({days_left} дн.)\n"

        response += "\n<b>Выберите действие:</b>"

        # Build buttons
        buttons = []

        # Tier selection row
        buttons.append([
            InlineKeyboardButton(text="🆓 FREE", callback_data=f"admin_sub_set_{user_id}_free"),
            InlineKeyboardButton(text="⭐ BASIC", callback_data=f"admin_sub_set_{user_id}_basic"),
        ])
        buttons.append([
            InlineKeyboardButton(text="💎 PREMIUM", callback_data=f"admin_sub_set_{user_id}_premium"),
            InlineKeyboardButton(text="👑 VIP", callback_data=f"admin_sub_set_{user_id}_vip"),
        ])

        # Duration row (for paid tiers)
        buttons.append([
            InlineKeyboardButton(text="➕ 1 мес", callback_data=f"admin_sub_extend_{user_id}_1"),
            InlineKeyboardButton(text="➕ 3 мес", callback_data=f"admin_sub_extend_{user_id}_3"),
            InlineKeyboardButton(text="➕ 12 мес", callback_data=f"admin_sub_extend_{user_id}_12"),
        ])

        # Cancel subscription (if has paid sub)
        if subscription and current_tier.lower() != "free" if isinstance(current_tier, str) else current_tier != SubscriptionTier.FREE:
            buttons.append([
                InlineKeyboardButton(text="❌ Отменить подписку", callback_data=f"admin_sub_cancel_{user_id}")
            ])

        # Back button
        buttons.append([
            InlineKeyboardButton(text="« Назад", callback_data=f"admin_user_view_{user_id}")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing subscription menu: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)


@router.callback_query(F.data.startswith("admin_sub_set_"))
async def admin_sub_set_callback(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
):
    """Set subscription tier directly"""
    try:
        parts = callback.data.split("_")
        user_id = int(parts[-2])
        new_tier = parts[-1].lower()
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный формат", show_alert=True)
        return

    if new_tier not in ["free", "basic", "premium", "vip"]:
        await callback.answer("❌ Неверный тариф", show_alert=True)
        return

    try:
        # Get user
        stmt = select(User).options(selectinload(User.subscription)).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        subscription = user.subscription

        if new_tier == "free":
            # Deactivate subscription
            if subscription:
                subscription.tier = SubscriptionTier.FREE
                subscription.is_active = False
                subscription.expires_at = None
                await session.commit()
        else:
            # Activate/upgrade subscription
            if not subscription:
                from src.database.crud import create_subscription
                subscription = await create_subscription(
                    session,
                    user_id=user.id,
                    tier=new_tier,
                    duration_months=1
                )
            else:
                subscription.tier = SubscriptionTier(new_tier)
                subscription.is_active = True
                if not subscription.expires_at or subscription.expires_at < datetime.now(UTC):
                    subscription.expires_at = datetime.now(UTC) + timedelta(days=30)
                await session.commit()

        # Log action
        await log_admin_action(
            session,
            admin_id=callback.from_user.id,
            action="set_subscription_tier",
            target_user_id=user.telegram_id or user.id,
            details=f"Set tier to {new_tier.upper()} for user {user.id}",
        )

        tier_emojis = {"free": "🆓", "basic": "⭐", "premium": "💎", "vip": "👑"}
        await callback.answer(f"✅ Установлен тариф: {tier_emojis[new_tier]} {new_tier.upper()}", show_alert=True)

        # Return to user card
        callback.data = f"admin_user_view_{user_id}"
        await admin_user_view_callback(callback, session, bot)

    except Exception as e:
        logger.exception(f"Error setting subscription tier: {e}")
        await callback.answer("❌ Ошибка при изменении тарифа", show_alert=True)


# ===========================
# Admin/Ban toggles
# ===========================

@router.callback_query(F.data.startswith("admin_user_toggle_admin_"))
async def admin_user_toggle_admin_callback(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
):
    """Toggle admin status for user"""
    try:
        user_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID", show_alert=True)
        return

    try:
        stmt = select(User).options(selectinload(User.subscription)).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Don't allow removing admin from self
        if user.telegram_id == callback.from_user.id and user.is_admin:
            await callback.answer("❌ Нельзя снять админа с себя", show_alert=True)
            return

        # Toggle admin status
        user.is_admin = not user.is_admin
        await session.commit()

        # Log action
        action = "grant_admin" if user.is_admin else "revoke_admin"
        await log_admin_action(
            session,
            admin_id=callback.from_user.id,
            action=action,
            target_user_id=user.telegram_id or user.id,
            details=f"{'Granted' if user.is_admin else 'Revoked'} admin for user {user.id}",
        )

        status = "👑 Теперь админ" if user.is_admin else "👤 Админ снят"
        await callback.answer(f"✅ {status}", show_alert=True)

        # Refresh user view
        callback.data = f"admin_user_view_{user_id}"
        await admin_user_view_callback(callback, session, bot)

    except Exception as e:
        logger.exception(f"Error toggling admin: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin_user_toggle_ban_"))
async def admin_user_toggle_ban_callback(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
):
    """Toggle ban status for user"""
    try:
        user_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID", show_alert=True)
        return

    try:
        stmt = select(User).options(selectinload(User.subscription)).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Don't allow banning admins
        if user.is_admin:
            await callback.answer("❌ Нельзя забанить админа", show_alert=True)
            return

        # Don't allow banning self
        if user.telegram_id == callback.from_user.id:
            await callback.answer("❌ Нельзя забанить себя", show_alert=True)
            return

        # Toggle ban status
        user.is_banned = not user.is_banned
        await session.commit()

        # Log action
        action = "ban_user" if user.is_banned else "unban_user"
        await log_admin_action(
            session,
            admin_id=callback.from_user.id,
            action=action,
            target_user_id=user.telegram_id or user.id,
            details=f"{'Banned' if user.is_banned else 'Unbanned'} user {user.id}",
        )

        status = "🚫 Забанен" if user.is_banned else "✅ Разбанен"
        await callback.answer(f"{status}", show_alert=True)

        # Refresh user view
        callback.data = f"admin_user_view_{user_id}"
        await admin_user_view_callback(callback, session, bot)

    except Exception as e:
        logger.exception(f"Error toggling ban: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin_user_clear_limit_"))
async def admin_user_clear_limit_callback(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
):
    """Clear custom limit for user (revert to tier-based)"""
    try:
        user_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID", show_alert=True)
        return

    try:
        from src.database.crud import clear_user_custom_limit

        user = await clear_user_custom_limit(session, user_id)

        # Log action
        await log_admin_action(
            session,
            admin_id=callback.from_user.id,
            action="clear_custom_limit",
            target_user_id=user.telegram_id or user.id,
            details=f"Cleared custom limit for user {user.id}, reverted to tier-based",
        )

        await callback.answer("✅ Лимит сброшен к тарифу", show_alert=True)

        # Refresh user view
        callback.data = f"admin_user_view_{user_id}"
        await admin_user_view_callback(callback, session, bot)

    except Exception as e:
        logger.exception(f"Error clearing custom limit: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


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
                session, user
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
                # Check premium subscription status (not channel subscription!)
                has_active_premium = False
                if user.subscription and user.subscription.is_active:
                    # Active if: tier is not FREE OR (FREE and no expiry) OR not expired
                    if user.subscription.tier != SubscriptionTier.FREE:
                        has_active_premium = True
                    elif user.subscription.expires_at is None or user.subscription.expires_at > datetime.now(UTC):
                        has_active_premium = True

                status = "✅" if has_active_premium else "❌"
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
                response += f"   {get_user_identifier(user)}\n"
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


@router.message(Command("admin_margin"))
async def cmd_admin_margin(message: Message, session: AsyncSession):
    """
    Show real-time margin analytics based on actual database data

    Usage: /admin_margin
    """
    user_id = message.from_user.id
    logger.info(f"Admin margin analytics accessed by {user_id} (@{message.from_user.username})")

    try:
        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            from src.services.margin_calculator import (
                get_global_margin_analytics,
                get_margin_by_tier,
                check_margin_alerts,
            )

            # Get global margin analytics for last 30 days
            analytics = await get_global_margin_analytics(session, days=30)

            # Get margin by tier
            tier_margins = await get_margin_by_tier(session, days=30)

            # Check margin alerts (users with <30% margin)
            alerts = await check_margin_alerts(session, threshold_percent=30.0)

            # Format message
            response = "💰 <b>Real-time Margin Analytics</b>\n"
            response += f"<i>Период: последние {analytics['period_days']} дней</i>\n\n"

            # Global metrics
            response += "📊 <b>Глобальные метрики:</b>\n"
            response += f"├ Выручка: <b>${analytics['total_revenue']:.2f}</b>\n"
            response += f"├ Расходы: <b>${analytics['total_costs']:.2f}</b>\n"
            response += f"├ Маржа: <b>${analytics['total_margin']:.2f}</b> ({analytics['margin_percent']:.1f}%)\n"
            response += f"├ Средняя маржа/юзер: <b>${analytics['avg_margin_per_user']:.2f}</b>\n"
            response += f"└ Пользователей: <b>{analytics['users_analyzed']}</b> ({analytics['profitable_users']} прибыльных)\n\n"

            # Revenue share metrics
            response += "🤝 <b>Revenue Share:</b>\n"
            response += f"├ Выплачено: <b>${analytics['total_revshare_paid']:.2f}</b>\n"
            response += f"├ Эффективный %: <b>{analytics['effective_revshare_percent']:.2f}%</b>\n"
            response += f"└ Рекомендуемый %: <b>{analytics['recommended_revenue_share']:.2f}%</b>\n"
            response += f"   <i>(на основе реальных данных)</i>\n\n"

            # Margin by tier
            if tier_margins:
                response += "🎯 <b>Маржа по тирам:</b>\n"

                tier_emojis = {
                    'basic': '🟢',
                    'premium': '🟡',
                    'vip': '🔴',
                }

                for tier_name, data in tier_margins.items():
                    emoji = tier_emojis.get(tier_name, '⚪')
                    response += f"{emoji} <b>{tier_name.upper()}</b> ({data['users']} users):\n"
                    response += f"   Revenue: ${data['revenue']:.2f} | Costs: ${data['costs']:.2f}\n"
                    response += f"   Margin: <b>${data['margin_usd']:.2f}</b> ({data['margin_percent']:.1f}%)\n\n"

            # Alerts
            if alerts['alert_count'] > 0:
                response += f"⚠️ <b>Алерты (маржа <{alerts['threshold_percent']}%):</b>\n"
                response += f"Найдено пользователей: <b>{alerts['alert_count']}</b>\n\n"

                # Show top 5 low-margin users
                for user_data in alerts['low_margin_users'][:5]:
                    # Support both telegram_id and email users
                    user_id_str = user_data.get('telegram_id') or user_data.get('email') or f"ID {user_data.get('id', '?')}"
                    response += f"├ {user_data['username']} ({user_id_str})\n"
                    response += f"│  Маржа: <b>{user_data['margin_percent']:.1f}%</b> (${user_data['margin_usd']:.2f})\n"
                    response += f"│  Revenue: ${user_data['revenue']:.2f} | Cost: ${user_data['cost']:.2f}\n\n"

                if alerts['alert_count'] > 5:
                    response += f"└ ...и ещё {alerts['alert_count'] - 5} пользователей\n\n"
            else:
                response += "✅ <b>Алертов нет</b> - все пользователи прибыльны!\n\n"

            response += f"<i>Обновлено: {datetime.now(UTC).strftime('%H:%M:%S UTC')}</i>"

            await message.answer(response)

            # Log admin action
            await log_admin_action(
                session,
                admin_id=user_id,
                action="view_margin_analytics",
                details=f"Viewed margin analytics (margin: {analytics['margin_percent']:.1f}%, revshare: {analytics['effective_revshare_percent']:.2f}%)",
            )

    except Exception as e:
        logger.exception(f"Error in admin margin analytics: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка при загрузке margin analytics</b>\n\n"
            "Попробуйте позже или обратитесь к разработчику."
        )


# ===========================
# SOCIAL TASKS MANAGEMENT
# ===========================


@router.callback_query(F.data == "admin_tasks")
async def admin_tasks_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Show social tasks admin panel with pending reviews and task list
    """
    from src.services.social_tasks_service import SocialTasksService
    from src.database.models import TaskCompletion, TaskCompletionStatus

    try:
        # Get pending reviews count
        pending = await SocialTasksService.get_pending_reviews(session)
        pending_count = len(pending)

        # Get active tasks count
        tasks = await SocialTasksService.get_all_tasks(session, status_filter="active")
        active_count = len(tasks)

        # Get total tasks count
        all_tasks = await SocialTasksService.get_all_tasks(session)
        total_count = len(all_tasks)

        # Get completed today
        from sqlalchemy import func, and_
        from datetime import datetime, UTC

        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(func.count(TaskCompletion.id)).where(
            and_(
                TaskCompletion.status == TaskCompletionStatus.COMPLETED.value,
                TaskCompletion.completed_at >= today_start
            )
        )
        result = await session.execute(stmt)
        completed_today = result.scalar() or 0

        response = "📋 <b>Управление заданиями</b>\n\n"
        response += f"📊 <b>Статистика:</b>\n"
        response += f"├ Всего заданий: <b>{total_count}</b>\n"
        response += f"├ Активных: <b>{active_count}</b>\n"
        response += f"├ Выполнено сегодня: <b>{completed_today}</b>\n"
        response += f"└ На проверке: <b>{pending_count}</b>\n\n"

        if pending_count > 0:
            response += f"⚠️ <b>{pending_count} скриншотов ожидают проверки!</b>\n\n"

        response += "Выберите действие:"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"📸 На проверке ({pending_count})",
                        callback_data="admin_tasks_pending"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="✅ Активные задания",
                        callback_data="admin_tasks_list_active"
                    ),
                    InlineKeyboardButton(
                        text="📝 Все задания",
                        callback_data="admin_tasks_list_all"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="➕ Создать задание",
                        callback_data="admin_tasks_create"
                    ),
                ],
                [
                    InlineKeyboardButton(text="« В меню", callback_data="admin_refresh"),
                ],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error in admin tasks panel: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)


@router.callback_query(F.data == "admin_tasks_pending")
async def admin_tasks_pending_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Show pending screenshot reviews with approve/reject buttons
    """
    from src.services.social_tasks_service import SocialTasksService

    try:
        pending = await SocialTasksService.get_pending_reviews(session)

        if not pending:
            await callback.answer("✅ Нет скриншотов на проверке", show_alert=True)
            return

        # Show first pending item with action buttons
        completion = pending[0]
        user = completion.user
        task = completion.task
        user_name = user.first_name or user.username or f"ID {user.id}"

        response = f"📸 <b>На проверке ({len(pending)})</b>\n\n"
        response += f"📋 <b>{task.title_ru if task else 'Unknown'}</b>\n"
        response += f"👤 {user_name}"
        if user.username:
            response += f" (@{user.username})"
        response += f"\n💰 Награда: +{task.reward_points} $SYNTRA\n"

        if completion.screenshot_url:
            response += f"\n🔗 <a href='{completion.screenshot_url}'>Открыть скриншот</a>"

        if len(pending) > 1:
            response += f"\n\n<i>Ещё {len(pending) - 1} на проверке</i>"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Одобрить",
                        callback_data=f"task_approve:{completion.id}"
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=f"task_reject:{completion.id}"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔗 Скриншот",
                        url=completion.screenshot_url or "https://example.com"
                    ),
                ] if completion.screenshot_url else [],
                [
                    InlineKeyboardButton(
                        text="⏭ Пропустить",
                        callback_data="admin_tasks_pending_skip"
                    ),
                ],
                [
                    InlineKeyboardButton(text="« Назад", callback_data="admin_tasks"),
                ],
            ]
        )

        # Remove empty rows
        keyboard.inline_keyboard = [
            row for row in keyboard.inline_keyboard if row
        ]

        await callback.message.edit_text(
            response,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing pending tasks: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)


@router.callback_query(F.data == "admin_tasks_pending_skip")
async def admin_tasks_pending_skip(callback: CallbackQuery, session: AsyncSession):
    """Skip current pending review and show next"""
    # Just refresh the pending list - items are ordered so next one shows
    await callback.answer("⏭ Пропущено")
    await admin_tasks_pending_callback(callback, session)


@router.callback_query(F.data.startswith("admin_tasks_list_"))
async def admin_tasks_list_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Show tasks list (active or all)
    """
    from src.services.social_tasks_service import SocialTasksService

    filter_type = callback.data.split("_")[-1]  # "active" or "all"

    try:
        if filter_type == "active":
            tasks = await SocialTasksService.get_all_tasks(session, status_filter="active")
            title = "Активные задания"
        else:
            tasks = await SocialTasksService.get_all_tasks(session)
            title = "Все задания"

        if not tasks:
            await callback.answer(f"📋 Нет заданий", show_alert=True)
            return

        response = f"📋 <b>{title} ({len(tasks)})</b>\n\n"

        for task in tasks[:15]:
            status_emoji = {
                "active": "✅",
                "draft": "📝",
                "paused": "⏸",
                "completed": "🏁",
                "expired": "⏰"
            }.get(task.status, "❓")

            response += f"{status_emoji} <b>{task.title_ru}</b>\n"
            response += f"   💰 +{task.reward_points} | "
            response += f"👥 {task.current_completions}"
            if task.max_completions:
                response += f"/{task.max_completions}"
            response += "\n\n"

        if len(tasks) > 15:
            response += f"<i>...и ещё {len(tasks) - 15}</i>\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="« Назад", callback_data="admin_tasks"),
                ],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing tasks list: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)


@router.callback_query(F.data == "admin_tasks_create")
async def admin_tasks_create_callback(callback: CallbackQuery):
    """
    Show task creation guide
    """
    response = (
        "➕ <b>Создание задания</b>\n\n"
        "Используйте команду <code>/task_add</code>\n\n"
        "Выберите тип для подробной инструкции:"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✈️ Telegram канал",
                    callback_data="admin_tasks_new_telegram_channel"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💬 Telegram чат",
                    callback_data="admin_tasks_new_telegram_chat"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🐦 Twitter подписка",
                    callback_data="admin_tasks_new_twitter"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📖 Полный гайд",
                    callback_data="admin_tasks_guide"
                ),
            ],
            [
                InlineKeyboardButton(text="« Назад", callback_data="admin_tasks"),
            ],
        ]
    )

    await callback.message.edit_text(response, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_tasks_new_"))
async def admin_tasks_new_type_callback(callback: CallbackQuery):
    """
    Show instructions for creating task via command
    """
    task_type = callback.data.replace("admin_tasks_new_", "")

    type_info = {
        "telegram_channel": (
            "✈️ <b>Задание: Подписка на Telegram канал</b>\n\n"
            "<b>Публичный канал:</b>\n"
            "<code>/task_add telegram_channel @channel 100</code>\n\n"
            "<b>Приватный канал:</b>\n"
            "<code>/task_add telegram_channel -1001234567890 https://t.me/+AbCdEfG 100</code>\n"
            "<code>/task_add telegram_channel -1001234567890 https://t.me/+AbCdEfG 100 \"Syntra News\"</code>\n\n"
            "Где:\n"
            "• @channel или ID канала\n"
            "• invite ссылка (для приватных)\n"
            "• 100 - награда в $SYNTRA\n"
            "• (опционально) штраф за отписку\n"
            "• \"Название\" - для красивого отображения приватных"
        ),
        "telegram_chat": (
            "💬 <b>Задание: Вступление в Telegram чат</b>\n\n"
            "<b>Публичный чат:</b>\n"
            "<code>/task_add telegram_chat @chat 100</code>\n\n"
            "<b>Приватный чат:</b>\n"
            "<code>/task_add telegram_chat -1001234567890 https://t.me/+XyZ123 100</code>\n"
            "<code>/task_add telegram_chat -1001234567890 https://t.me/+XyZ123 100 \"VIP Chat\"</code>\n\n"
            "Где:\n"
            "• @chat или ID чата\n"
            "• invite ссылка (для приватных)\n"
            "• 100 - награда в $SYNTRA\n"
            "• (опционально) штраф за отписку\n"
            "• \"Название\" - для красивого отображения приватных"
        ),
        "twitter": (
            "🐦 <b>Задание: Подписка на Twitter</b>\n\n"
            "<code>/task_add twitter @username 100</code>\n\n"
            "Где:\n"
            "• @username - Twitter username\n"
            "• 100 - награда в $SYNTRA\n"
            "• (опционально) штраф за отписку\n\n"
            "⚠️ Проверка через скриншот (вручную)"
        ),
    }

    response = type_info.get(task_type, "❌ Неизвестный тип")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="« Назад", callback_data="admin_tasks_create"),
            ],
        ]
    )

    await callback.message.edit_text(response, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_tasks_guide")
async def admin_tasks_guide_callback(callback: CallbackQuery):
    """
    Show full guide for task_add command
    """
    guide = """📖 <b>Полный гайд по созданию заданий</b>

<b>Команда:</b> <code>/task_add</code>

━━━━━━━━━━━━━━━━━━━━

✈️ <b>TELEGRAM КАНАЛ</b>

<b>Публичный канал (с @username):</b>
<code>/task_add telegram_channel @channel 100</code>
<code>/task_add telegram_channel @channel 100 50</code>

<b>Приватный канал (с ID и invite):</b>
<code>/task_add telegram_channel -1001234567890 https://t.me/+AbCdEfG 100</code>
<code>/task_add telegram_channel -1001234567890 https://t.me/+AbCdEfG 100 "Название канала"</code>

💡 ID канала можно узнать:
• Переслав сообщение из канала боту @getmyid_bot
• Или в URL: t.me/c/<b>1234567890</b>/123

━━━━━━━━━━━━━━━━━━━━

💬 <b>TELEGRAM ЧАТ</b>

<b>Публичный чат:</b>
<code>/task_add telegram_chat @chat 100</code>

<b>Приватный чат:</b>
<code>/task_add telegram_chat -1001234567890 https://t.me/+XyZ123 100</code>
<code>/task_add telegram_chat -1001234567890 https://t.me/+XyZ123 100 "VIP Chat"</code>

━━━━━━━━━━━━━━━━━━━━

🐦 <b>TWITTER</b>

<code>/task_add twitter @username 100</code>
<code>/task_add twitter @elonmusk 150 75</code>

⚠️ Проверка через скриншот (вручную)
Админу придёт уведомление для одобрения

━━━━━━━━━━━━━━━━━━━━

<b>ПАРАМЕТРЫ:</b>

• <b>Тип</b>: telegram_channel | telegram_chat | twitter
• <b>Цель</b>: @username или ID канала
• <b>Invite</b>: ссылка t.me/+... (для приватных)
• <b>Награда</b>: кол-во $SYNTRA за выполнение
• <b>Штраф</b>: снимается при отписке (по умолчанию 50% награды)
• <b>Название</b>: "в кавычках" для приватных (опционально)

━━━━━━━━━━━━━━━━━━━━

<b>ПРИМЕРЫ:</b>

<code>/task_add telegram_channel @syntra_news 100</code>
→ Подписка на публичный канал, +100 pts, штраф 50

<code>/task_add telegram_channel -1001999888777 https://t.me/+AbC123 200 100</code>
→ Приватный канал, +200 pts, штраф 100

<code>/task_add telegram_chat -1001234 https://t.me/+xyz 100 "Syntra VIP"</code>
→ Приватный чат с названием "Syntra VIP"

<code>/task_add twitter @syntratrade 150</code>
→ Twitter подписка, +150 pts, штраф 75"""

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="« Назад", callback_data="admin_tasks_create"),
            ],
        ]
    )

    await callback.message.edit_text(guide, reply_markup=keyboard)
    await callback.answer()


# ===========================
# SUBSCRIPTIONS MANAGEMENT
# ===========================


@router.callback_query(F.data == "admin_subscriptions")
async def admin_subscriptions_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Show subscriptions overview with filter options
    """
    response = "💎 <b>Управление подписками</b>\n\n"
    response += "Выберите категорию для просмотра:"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Активные", callback_data="admin_subs_filter_active"
                ),
                InlineKeyboardButton(
                    text="⏰ Истекающие", callback_data="admin_subs_filter_expiring"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Истекшие", callback_data="admin_subs_filter_expired"
                ),
                InlineKeyboardButton(
                    text="📊 Все подписки", callback_data="admin_subs_filter_all"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📈 Статистика", callback_data="admin_subs_stats"
                ),
            ],
            [
                InlineKeyboardButton(text="« В меню", callback_data="admin_refresh"),
            ],
        ]
    )

    await callback.message.edit_text(response, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_subs_filter_"))
async def admin_subs_filter_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Show filtered subscriptions list
    """
    filter_type = callback.data.split("_")[-1]
    user_id = callback.from_user.id

    try:
        # Get subscriptions based on filter
        if filter_type == "active":
            # Active paid subscriptions
            stmt = (
                select(Subscription)
                .join(User)
                .where(
                    Subscription.is_active == True,
                    Subscription.tier != SubscriptionTier.FREE,
                )
                .order_by(Subscription.expires_at)
                .limit(20)
            )
            title = "✅ Активные подписки"
        elif filter_type == "expiring":
            # Expiring in next 7 days
            expiring_subs = await get_expiring_subscriptions(session, days=7)
            stmt = None
            title = "⏰ Истекающие подписки (7 дней)"
        elif filter_type == "expired":
            # Expired subscriptions
            expired_subs = await get_expired_subscriptions(session)
            stmt = None
            title = "❌ Истекшие подписки"
        else:  # all
            stmt = (
                select(Subscription)
                .join(User)
                .order_by(Subscription.created_at.desc())
                .limit(20)
            )
            title = "📊 Все подписки"

        # Execute query
        if stmt is not None:
            result = await session.execute(stmt)
            subscriptions = list(result.scalars().all())
        elif filter_type == "expiring":
            subscriptions = expiring_subs
        else:
            subscriptions = expired_subs

        # Format response
        response = f"<b>{title}</b>\n\n"

        if not subscriptions:
            response += "Подписки не найдены.\n"
        else:
            response += f"Найдено: <b>{len(subscriptions)}</b>\n\n"

            for i, sub in enumerate(subscriptions[:10], start=1):
                # Load user relationship
                await session.refresh(sub, ["user"])
                user = sub.user

                tier_emoji = {
                    "free": "🆓",
                    "basic": "⭐",
                    "premium": "💎",
                    "vip": "👑",
                }
                emoji = tier_emoji.get(sub.tier.value if hasattr(sub.tier, 'value') else sub.tier, "💎")

                status = "✅" if sub.is_active else "❌"
                name = get_user_display_name(user)

                response += f"{status} <b>{i}.</b> {emoji} {sub.tier.upper()}\n"
                response += f"   👤 {name}\n"

                if sub.expires_at:
                    days_left = (sub.expires_at - datetime.now(UTC)).days
                    response += f"   📅 Истекает: {sub.expires_at.strftime('%d.%m.%Y')}"
                    if days_left >= 0:
                        response += f" (через {days_left} дн.)\n"
                    else:
                        response += f" (истекла {abs(days_left)} дн. назад)\n"

                response += f"   🆔 {get_user_identifier(user)}\n\n"

            if len(subscriptions) > 10:
                response += f"\n<i>Показано первые 10 из {len(subscriptions)}</i>"

        # Navigation keyboard
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="« Назад", callback_data="admin_subscriptions"
                    ),
                    InlineKeyboardButton(text="« В меню", callback_data="admin_refresh"),
                ],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

        # Log action
        await log_admin_action(
            session,
            admin_id=user_id,
            action="view_subscriptions",
            details=f"Filter: {filter_type}, Count: {len(subscriptions)}",
        )

    except Exception as e:
        logger.exception(f"Error showing subscriptions filter {filter_type}: {e}")
        await callback.answer("❌ Ошибка при загрузке подписок", show_alert=True)


@router.callback_query(F.data == "admin_subs_stats")
async def admin_subs_stats_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Show detailed subscription statistics
    """
    user_id = callback.from_user.id

    try:
        # Get subscription stats
        sub_stats = await get_subscription_stats(session)
        mrr_data = await get_mrr(session)

        # Format response
        response = "📈 <b>Статистика подписок</b>\n\n"

        # Overview
        response += "📊 <b>Общая информация:</b>\n"
        response += f"├ Всего активных: <b>{sub_stats['total_active']}</b>\n"
        response += f"├ FREE: {sub_stats['by_tier'].get('free', {}).get('count', 0)}\n"
        response += f"├ BASIC: {sub_stats['by_tier'].get('basic', {}).get('count', 0)}\n"
        response += f"├ PREMIUM: {sub_stats['by_tier'].get('premium', {}).get('count', 0)}\n"
        response += f"└ VIP: {sub_stats['by_tier'].get('vip', {}).get('count', 0)}\n\n"

        # Revenue
        response += "💰 <b>Доходы (MRR):</b>\n"
        response += f"├ Всего: <b>${mrr_data['total_mrr']:.2f}/мес</b>\n"
        if mrr_data['by_tier']:
            for tier, tier_data in mrr_data['by_tier'].items():
                if tier != 'free' and tier_data['mrr'] > 0:
                    tier_label = tier.upper()
                    response += f"├ {tier_label}: ${tier_data['mrr']:.2f} ({tier_data['count']} юз.)\n"
        response += "\n"

        # Expiring soon
        expiring_7d = await get_expiring_subscriptions(session, days=7)
        expiring_3d = await get_expiring_subscriptions(session, days=3)

        response += "⏰ <b>Истекающие подписки:</b>\n"
        response += f"├ В течение 7 дней: <b>{len(expiring_7d)}</b>\n"
        response += f"└ В течение 3 дней: <b>{len(expiring_3d)}</b>\n\n"

        # Conversion rate
        total_users = sub_stats['by_tier'].get('free', {}).get('count', 0) + sub_stats['total_active']
        paying_users = sub_stats['total_active'] - sub_stats['by_tier'].get('free', {}).get('count', 0)
        conversion_rate = (paying_users / total_users * 100) if total_users > 0 else 0

        response += f"📈 <b>Конверсия:</b> {conversion_rate:.1f}% ({paying_users}/{total_users})\n\n"

        response += f"<i>Обновлено: {datetime.now(UTC).strftime('%H:%M:%S UTC')}</i>"

        # Keyboard
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="« Назад", callback_data="admin_subscriptions"
                    ),
                    InlineKeyboardButton(text="« В меню", callback_data="admin_refresh"),
                ],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

        # Log action
        await log_admin_action(
            session,
            admin_id=user_id,
            action="view_subscription_stats",
            details="Viewed subscription statistics",
        )

    except Exception as e:
        logger.exception(f"Error showing subscription stats: {e}")
        await callback.answer("❌ Ошибка при загрузке статистики", show_alert=True)


# ===========================
# PAYMENTS MANAGEMENT
# ===========================


@router.callback_query(F.data == "admin_payments")
async def admin_payments_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Show recent payments with filtering options
    """
    response = "💳 <b>Управление платежами</b>\n\n"
    response += "Выберите категорию для просмотра:"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Успешные", callback_data="admin_payments_filter_completed"
                ),
                InlineKeyboardButton(
                    text="⏳ Ожидают", callback_data="admin_payments_filter_pending"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Неудачные", callback_data="admin_payments_filter_failed"
                ),
                InlineKeyboardButton(
                    text="📊 Все", callback_data="admin_payments_filter_all"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📈 Статистика", callback_data="admin_payments_stats"
                ),
            ],
            [
                InlineKeyboardButton(text="« В меню", callback_data="admin_refresh"),
            ],
        ]
    )

    await callback.message.edit_text(response, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_payments_filter_"))
async def admin_payments_filter_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Show filtered payments list
    """
    filter_type = callback.data.split("_")[-1]
    user_id = callback.from_user.id

    try:
        # Get payments based on filter
        if filter_type == "completed":
            status_filter = PaymentStatus.COMPLETED
            title = "✅ Успешные платежи"
        elif filter_type == "pending":
            status_filter = PaymentStatus.PENDING
            title = "⏳ Ожидающие платежи"
        elif filter_type == "failed":
            status_filter = PaymentStatus.FAILED
            title = "❌ Неудачные платежи"
        else:  # all
            status_filter = None
            title = "📊 Все платежи"

        # Get payments
        payments = await get_all_payments(
            session,
            status=status_filter,
            limit=20
        )

        # Format response
        response = f"<b>{title}</b>\n\n"

        if not payments:
            response += "Платежи не найдены.\n"
        else:
            total_amount = sum(p.amount for p in payments if p.status == PaymentStatus.COMPLETED)
            response += f"Найдено: <b>{len(payments)}</b>\n"
            if filter_type == "completed":
                response += f"Сумма: <b>${total_amount:.2f}</b>\n\n"
            else:
                response += "\n"

            for i, payment in enumerate(payments[:10], start=1):
                # Load relationships
                await session.refresh(payment, ["user"])
                user = payment.user

                status_emoji = {
                    "completed": "✅",
                    "pending": "⏳",
                    "failed": "❌",
                    "refunded": "🔄",
                    "cancelled": "🚫",
                }
                emoji = status_emoji.get(payment.status.value if hasattr(payment.status, 'value') else payment.status, "💳")

                tier_emoji = {
                    "basic": "⭐",
                    "premium": "💎",
                    "vip": "👑",
                }
                tier_icon = tier_emoji.get(payment.tier.value if hasattr(payment.tier, 'value') else payment.tier, "💎")

                name = get_user_display_name(user)

                response += f"{emoji} <b>{i}.</b> ${payment.amount:.2f} • {tier_icon} {payment.tier.upper()}\n"
                response += f"   👤 {name}\n"
                response += f"   📅 {payment.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                response += f"   🔧 {payment.provider.upper()}\n"

                if payment.duration_months:
                    response += f"   ⏱ {payment.duration_months} мес.\n"

                response += "\n"

            if len(payments) > 10:
                response += f"<i>Показано первые 10 из {len(payments)}</i>"

        # Navigation keyboard
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="« Назад", callback_data="admin_payments"
                    ),
                    InlineKeyboardButton(text="« В меню", callback_data="admin_refresh"),
                ],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

        # Log action
        await log_admin_action(
            session,
            admin_id=user_id,
            action="view_payments",
            details=f"Filter: {filter_type}, Count: {len(payments)}",
        )

    except Exception as e:
        logger.exception(f"Error showing payments filter {filter_type}: {e}")
        await callback.answer("❌ Ошибка при загрузке платежей", show_alert=True)


@router.callback_query(F.data == "admin_payments_stats")
async def admin_payments_stats_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Show payment statistics
    """
    user_id = callback.from_user.id

    try:
        # Get payments for stats
        all_payments = await get_all_payments(session, limit=1000)

        # Calculate stats
        total_payments = len(all_payments)
        completed = [p for p in all_payments if p.status == PaymentStatus.COMPLETED]
        pending = [p for p in all_payments if p.status == PaymentStatus.PENDING]
        failed = [p for p in all_payments if p.status == PaymentStatus.FAILED]

        total_revenue = sum(p.amount for p in completed)

        # Success rate
        success_rate = (len(completed) / total_payments * 100) if total_payments > 0 else 0

        # By provider
        by_provider = {}
        for p in completed:
            provider = p.provider.value if hasattr(p.provider, 'value') else p.provider
            if provider not in by_provider:
                by_provider[provider] = {"count": 0, "amount": 0}
            by_provider[provider]["count"] += 1
            by_provider[provider]["amount"] += p.amount

        # Format response
        response = "📈 <b>Статистика платежей</b>\n\n"

        response += "📊 <b>Общая информация:</b>\n"
        response += f"├ Всего платежей: <b>{total_payments}</b>\n"
        response += f"├ Успешных: <b>{len(completed)}</b>\n"
        response += f"├ Ожидающих: <b>{len(pending)}</b>\n"
        response += f"└ Неудачных: <b>{len(failed)}</b>\n\n"

        response += "💰 <b>Доходы:</b>\n"
        response += f"└ Всего получено: <b>${total_revenue:.2f}</b>\n\n"

        response += f"✅ <b>Success Rate:</b> {success_rate:.1f}%\n\n"

        if by_provider:
            response += "🔧 <b>По провайдерам:</b>\n"
            for provider, data in by_provider.items():
                provider_name = provider.replace("_", " ").title()
                response += f"├ {provider_name}: ${data['amount']:.2f} ({data['count']} плат.)\n"
            response += "\n"

        # Recent 24h
        last_24h = datetime.now(UTC) - timedelta(hours=24)
        recent = [p for p in completed if p.created_at >= last_24h]
        recent_revenue = sum(p.amount for p in recent)

        response += "🕐 <b>За последние 24 часа:</b>\n"
        response += f"├ Платежей: <b>{len(recent)}</b>\n"
        response += f"└ Доход: <b>${recent_revenue:.2f}</b>\n\n"

        response += f"<i>Обновлено: {datetime.now(UTC).strftime('%H:%M:%S UTC')}</i>"

        # Keyboard
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="« Назад", callback_data="admin_payments"
                    ),
                    InlineKeyboardButton(text="« В меню", callback_data="admin_refresh"),
                ],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

        # Log action
        await log_admin_action(
            session,
            admin_id=user_id,
            action="view_payment_stats",
            details="Viewed payment statistics",
        )

    except Exception as e:
        logger.exception(f"Error showing payment stats: {e}")
        await callback.answer("❌ Ошибка при загрузке статистики", show_alert=True)


# ===========================
# SUBSCRIPTION ACTIONS
# ===========================


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    """No-op callback for separator buttons"""
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sub_extend_"))
async def admin_sub_extend_callback(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
):
    """
    Extend user subscription by N months
    """
    try:
        parts = callback.data.split("_")
        user_id = int(parts[-2])
        months = int(parts[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        return

    try:
        # Get user with eager loading
        stmt = (
            select(User)
            .options(selectinload(User.subscription))
            .where(User.id == user_id)
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Get subscription from eager-loaded relationship
        subscription = user.subscription

        if not subscription:
            await callback.answer("❌ У пользователя нет подписки", show_alert=True)
            return

        # Extend subscription
        from dateutil.relativedelta import relativedelta

        if subscription.expires_at:
            # Extend from current expiration date
            new_expires_at = subscription.expires_at + relativedelta(months=months)
        else:
            # First time setting expiration (for FREE tier)
            new_expires_at = datetime.now(UTC) + relativedelta(months=months)

        subscription.expires_at = new_expires_at
        subscription.is_active = True

        await session.commit()
        await session.refresh(subscription)

        # Log action
        await log_admin_action(
            session,
            admin_id=callback.from_user.id,
            action="extend_subscription",
            target_user_id=user.telegram_id,
            details=f"Extended subscription by {months} months for user {user.telegram_id} (@{user.username}). New expiry: {new_expires_at.strftime('%Y-%m-%d')}",
        )

        await callback.answer(
            f"✅ Подписка продлена на {months} мес. до {new_expires_at.strftime('%d.%m.%Y')}",
            show_alert=True,
        )

        # Refresh user view
        original_data = callback.data
        callback.data = f"admin_user_view_{user_id}"
        await admin_user_view_callback(callback, session, bot)
        callback.data = original_data

    except Exception as e:
        logger.exception(f"Error extending subscription: {e}")
        await callback.answer("❌ Ошибка при продлении подписки", show_alert=True)


@router.callback_query(F.data.startswith("admin_sub_upgrade_"))
async def admin_sub_upgrade_callback(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
):
    """
    Upgrade user subscription tier
    """
    try:
        parts = callback.data.split("_")
        user_id = int(parts[-2])
        new_tier = parts[-1]
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        return

    try:
        # Get user with eager loading
        stmt = (
            select(User)
            .options(selectinload(User.subscription))
            .where(User.id == user_id)
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Get subscription from eager-loaded relationship
        subscription = user.subscription

        if not subscription:
            await callback.answer("❌ У пользователя нет подписки", show_alert=True)
            return

        old_tier = subscription.tier.value if hasattr(subscription.tier, 'value') else subscription.tier
        subscription.tier = new_tier

        await session.commit()
        await session.refresh(subscription)

        # Log action
        await log_admin_action(
            session,
            admin_id=callback.from_user.id,
            action="upgrade_subscription",
            target_user_id=user.telegram_id,
            details=f"Upgraded subscription from {old_tier.upper()} to {new_tier.upper()} for user {user.telegram_id} (@{user.username})",
        )

        await callback.answer(
            f"✅ Тариф повышен: {old_tier.upper()} → {new_tier.upper()}",
            show_alert=True,
        )

        # Refresh user view
        original_data = callback.data
        callback.data = f"admin_user_view_{user_id}"
        await admin_user_view_callback(callback, session, bot)
        callback.data = original_data

    except Exception as e:
        logger.exception(f"Error upgrading subscription: {e}")
        await callback.answer("❌ Ошибка при повышении тарифа", show_alert=True)


@router.callback_query(F.data.startswith("admin_sub_downgrade_"))
async def admin_sub_downgrade_callback(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
):
    """
    Downgrade user subscription tier
    """
    try:
        parts = callback.data.split("_")
        user_id = int(parts[-2])
        new_tier = parts[-1]
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        return

    try:
        # Get user with eager loading
        stmt = (
            select(User)
            .options(selectinload(User.subscription))
            .where(User.id == user_id)
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Get subscription from eager-loaded relationship
        subscription = user.subscription

        if not subscription:
            await callback.answer("❌ У пользователя нет подписки", show_alert=True)
            return

        old_tier = subscription.tier.value if hasattr(subscription.tier, 'value') else subscription.tier
        subscription.tier = new_tier

        await session.commit()
        await session.refresh(subscription)

        # Log action
        await log_admin_action(
            session,
            admin_id=callback.from_user.id,
            action="downgrade_subscription",
            target_user_id=user.telegram_id,
            details=f"Downgraded subscription from {old_tier.upper()} to {new_tier.upper()} for user {user.telegram_id} (@{user.username})",
        )

        await callback.answer(
            f"✅ Тариф понижен: {old_tier.upper()} → {new_tier.upper()}",
            show_alert=True,
        )

        # Refresh user view
        original_data = callback.data
        callback.data = f"admin_user_view_{user_id}"
        await admin_user_view_callback(callback, session, bot)
        callback.data = original_data

    except Exception as e:
        logger.exception(f"Error downgrading subscription: {e}")
        await callback.answer("❌ Ошибка при понижении тарифа", show_alert=True)


@router.callback_query(F.data.startswith("admin_sub_cancel_"))
async def admin_sub_cancel_callback(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
):
    """
    Cancel user subscription (downgrade to FREE)
    """
    try:
        user_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID пользователя", show_alert=True)
        return

    try:
        # Get user with eager loading
        stmt = select(User).options(selectinload(User.subscription)).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Cancel subscription
        await deactivate_subscription(session, user.id)

        # Log action
        await log_admin_action(
            session,
            admin_id=callback.from_user.id,
            action="cancel_subscription",
            target_user_id=user.telegram_id,
            details=f"Cancelled subscription for user {user.telegram_id} (@{user.username})",
        )

        await callback.answer("✅ Подписка отменена, пользователь переведён на FREE", show_alert=True)

        # Refresh user view
        original_data = callback.data
        callback.data = f"admin_user_view_{user_id}"
        await admin_user_view_callback(callback, session, bot)
        callback.data = original_data

    except Exception as e:
        logger.exception(f"Error cancelling subscription: {e}")
        await callback.answer("❌ Ошибка при отмене подписки", show_alert=True)


@router.callback_query(F.data.startswith("admin_sub_activate_"))
async def admin_sub_activate_callback(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
):
    """
    Activate paid subscription for FREE tier user
    """
    try:
        parts = callback.data.split("_")
        user_id = int(parts[-3])
        tier = parts[-2]
        months = int(parts[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        return

    try:
        # Get user with eager loading
        stmt = select(User).options(selectinload(User.subscription)).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Activate subscription
        await activate_subscription(session, user.id, tier, months)

        # Log action
        await log_admin_action(
            session,
            admin_id=callback.from_user.id,
            action="activate_subscription",
            target_user_id=user.telegram_id,
            details=f"Activated {tier.upper()} subscription for {months} months for user {user.telegram_id} (@{user.username})",
        )

        await callback.answer(
            f"✅ Активирована подписка {tier.upper()} на {months} мес.",
            show_alert=True,
        )

        # Refresh user view
        original_data = callback.data
        callback.data = f"admin_user_view_{user_id}"
        await admin_user_view_callback(callback, session, bot)
        callback.data = original_data

    except Exception as e:
        logger.exception(f"Error activating subscription: {e}")
        await callback.answer("❌ Ошибка при активации подписки", show_alert=True)


# ===========================
# UNIT ECONOMICS HANDLERS
# ===========================

def get_unit_economics_menu() -> InlineKeyboardMarkup:
    """Create Unit Economics submenu keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💎 По тарифам", callback_data="admin_ue_tiers"),
                InlineKeyboardButton(text="🆓 Free tier", callback_data="admin_ue_free"),
            ],
            [
                InlineKeyboardButton(text="🎁 Trial", callback_data="admin_ue_trial"),
                InlineKeyboardButton(text="🤝 Рефералы", callback_data="admin_ue_referral"),
            ],
            [
                InlineKeyboardButton(text="📈 Сценарии", callback_data="admin_ue_scenarios"),
            ],
            [
                InlineKeyboardButton(text="« В меню", callback_data="admin_refresh"),
            ],
        ]
    )


@router.callback_query(F.data == "admin_unit_economics")
async def admin_unit_economics_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Main Unit Economics dashboard
    """
    try:
        dashboard = await get_unit_economics_dashboard(session, days=30)

        response = "📊 <b>Unit Economics Dashboard</b>\n"
        response += f"<i>Период: последние 30 дней</i>\n\n"

        response += "💰 <b>Общая картина:</b>\n"
        response += f"├ Gross Revenue: <b>${dashboard['gross_revenue']:,.2f}</b>\n"
        response += f"├ Payment Fees: <b>${dashboard['payment_fees']:,.2f}</b> ({dashboard['payment_fee_percent']:.1f}%)\n"
        response += f"├ Net Revenue: <b>${dashboard['net_revenue']:,.2f}</b>\n"
        response += f"├ API Costs: <b>${dashboard['api_costs']:,.2f}</b>\n"
        response += f"├ RevShare: <b>${dashboard['revshare_costs']:,.2f}</b>\n"
        response += f"├ Total Costs: <b>${dashboard['total_costs']:,.2f}</b>\n"
        response += f"├ NET PROFIT: <b>${dashboard['net_profit']:,.2f}</b>\n"
        response += f"└ Margin: <b>{dashboard['margin_percent']:.1f}%</b>\n\n"

        response += "🎯 <b>Ключевые метрики:</b>\n"
        response += f"├ LTV: <b>${dashboard['ltv']:,.2f}</b>\n"
        response += f"├ CAC: <b>${dashboard['cac']:,.2f}</b>\n"
        response += f"├ LTV/CAC: <b>{dashboard['ltv_cac_ratio']:.1f}x</b>\n"
        response += f"├ Trial→Paid: <b>{dashboard['trial_conversion_rate']:.1f}%</b>\n"
        response += f"└ Free→Paid: <b>{dashboard['free_conversion_rate']:.1f}%</b>\n\n"

        response += "👥 <b>Пользователи:</b>\n"
        response += f"├ Платящих: <b>{dashboard['paying_users']}</b>\n"
        response += f"├ FREE: <b>{dashboard['free_users']}</b>\n"
        response += f"└ На trial: <b>{dashboard['active_trials']}</b>\n\n"

        # Платежи по провайдерам
        if dashboard.get('payments_by_provider'):
            response += "💳 <b>По провайдерам:</b>\n"
            for provider, data in dashboard['payments_by_provider'].items():
                response += f"├ {provider}: ${data['amount']:,.2f} ({data['count']} платежей)\n"

        await callback.message.edit_text(
            response,
            reply_markup=get_unit_economics_menu(),
        )
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error loading unit economics: {e}")
        await callback.answer("❌ Ошибка при загрузке unit economics", show_alert=True)


@router.callback_query(F.data == "admin_ue_tiers")
async def admin_ue_tiers_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Margin by subscription tiers
    """
    try:
        tiers_data = await get_tier_margin_with_fees(session, days=30)

        response = "💎 <b>Unit Economics по тарифам</b>\n"
        response += f"<i>Период: последние 30 дней</i>\n\n"

        tier_emojis = {"basic": "⭐", "premium": "💎", "vip": "👑"}

        for tier_name, data in tiers_data.items():
            emoji = tier_emojis.get(tier_name, "📊")
            response += f"{emoji} <b>{tier_name.upper()}</b>\n"
            response += f"├ Юзеров: <b>{data.users_count}</b>\n"
            response += f"├ Использование: <b>{data.avg_usage_percent:.1f}%</b> лимитов\n"
            response += f"├ Gross Revenue: ${data.gross_revenue:,.2f}\n"
            response += f"├ Payment Fees: ${data.payment_fees:,.2f} ({data.payment_fee_percent:.1f}%)\n"
            response += f"├ Net Revenue: ${data.net_revenue:,.2f}\n"
            response += f"├ API Costs: ${data.api_costs:,.2f}\n"
            response += f"├ RevShare: ${data.revshare_costs:,.2f}\n"
            response += f"├ Margin: <b>${data.margin_usd:,.2f}</b>\n"
            response += f"└ Margin %: <b>{data.margin_percent:.1f}%</b>\n\n"

        if not tiers_data:
            response += "<i>Нет данных по платным подпискам</i>\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Назад", callback_data="admin_unit_economics")],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error loading tier margins: {e}")
        await callback.answer("❌ Ошибка при загрузке маржи по тарифам", show_alert=True)


@router.callback_query(F.data == "admin_ue_free")
async def admin_ue_free_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Free tier economics
    """
    try:
        free_data = await get_free_tier_economics(session, days=30)

        response = "🆓 <b>Free Tier Экономика</b>\n"
        response += f"<i>Период: последние 30 дней</i>\n\n"

        response += "📊 <b>Пользователи:</b>\n"
        response += f"├ Всего FREE: <b>{free_data.total_free_users}</b>\n"
        response += f"└ Активных: <b>{free_data.active_free_users}</b>\n\n"

        response += "💸 <b>Расходы:</b>\n"
        response += f"├ Запросов: <b>{free_data.total_requests}</b>\n"
        response += f"├ Общие затраты: <b>${free_data.total_cost:,.2f}</b>\n"
        response += f"└ На пользователя: <b>${free_data.avg_cost_per_user:.4f}</b>\n\n"

        response += "📈 <b>Конверсия:</b>\n"
        response += f"├ → Trial: <b>{free_data.conversion_to_trial:.1f}%</b>\n"
        response += f"└ → Paid: <b>{free_data.conversion_to_paid:.1f}%</b>\n\n"

        response += "💡 <i>Free tier - это воронка для привлечения платящих</i>"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Назад", callback_data="admin_unit_economics")],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error loading free tier economics: {e}")
        await callback.answer("❌ Ошибка при загрузке free tier экономики", show_alert=True)


@router.callback_query(F.data == "admin_ue_trial")
async def admin_ue_trial_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Trial economics
    """
    try:
        trial_data = await get_trial_economics(session, days=30)

        response = "🎁 <b>Trial Экономика</b>\n"
        response += f"<i>7 дней бесплатного PREMIUM</i>\n\n"

        response += "📊 <b>Статистика:</b>\n"
        response += f"├ Активных триалов: <b>{trial_data.active_trials}</b>\n"
        response += f"└ Завершилось: <b>{trial_data.completed_trials}</b>\n\n"

        response += "💸 <b>Расходы на триалы:</b>\n"
        response += f"├ Запросов: <b>{trial_data.trial_requests}</b>\n"
        response += f"├ Общие затраты: <b>${trial_data.trial_cost:,.2f}</b>\n"
        response += f"└ На юзера: <b>${trial_data.avg_trial_cost_per_user:.2f}</b>\n\n"

        response += "📈 <b>Конверсия:</b>\n"
        response += f"├ Конвертировались: <b>{trial_data.trials_converted}</b>\n"
        response += f"├ Конверсия: <b>{trial_data.conversion_rate:.1f}%</b>\n"
        response += f"└ Доход от конвертов: <b>${trial_data.revenue_from_converted:,.2f}</b>\n\n"

        response += "💰 <b>ROI Trial программы:</b>\n"
        if trial_data.roi > 0:
            response += f"└ ROI: <b>+{trial_data.roi:.0f}%</b> ✅\n"
        else:
            response += f"└ ROI: <b>{trial_data.roi:.0f}%</b> ⚠️\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Назад", callback_data="admin_unit_economics")],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error loading trial economics: {e}")
        await callback.answer("❌ Ошибка при загрузке trial экономики", show_alert=True)


@router.callback_query(F.data == "admin_ue_referral")
async def admin_ue_referral_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Referral economics
    """
    try:
        ref_data = await get_referral_economics(session, days=30)

        response = "🤝 <b>Реферальная Экономика</b>\n"
        response += f"<i>Период: последние 30 дней</i>\n\n"

        response += "📊 <b>Рефералы:</b>\n"
        response += f"├ Всего: <b>{ref_data.total_referrals}</b>\n"
        response += f"├ Активных: <b>{ref_data.active_referrals}</b>\n"
        response += f"└ Pending: <b>{ref_data.pending_referrals}</b>\n\n"

        response += "💸 <b>Расходы:</b>\n"
        response += f"├ Бонусные запросы: <b>{ref_data.bonus_requests_granted}</b>\n"
        response += f"├ Стоимость бонусов: <b>${ref_data.bonus_requests_cost:,.2f}</b>\n"
        response += f"└ Revenue Share: <b>${ref_data.revshare_paid:,.2f}</b>\n\n"

        response += "💰 <b>Доходы от рефералов:</b>\n"
        response += f"├ Доход: <b>${ref_data.referral_revenue:,.2f}</b>\n"
        response += f"└ Effective RevShare: <b>{ref_data.effective_revshare_rate:.1f}%</b>\n\n"

        response += "📈 <b>ROI:</b>\n"
        if ref_data.roi > 0:
            response += f"└ ROI: <b>+{ref_data.roi:.0f}%</b> ✅"
        else:
            response += f"└ ROI: <b>{ref_data.roi:.0f}%</b> ⚠️"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Назад", callback_data="admin_unit_economics")],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error loading referral economics: {e}")
        await callback.answer("❌ Ошибка при загрузке реферальной экономики", show_alert=True)


@router.callback_query(F.data == "admin_ue_scenarios")
async def admin_ue_scenarios_callback(callback: CallbackQuery, session: AsyncSession):
    """
    Margin scenarios at different usage percentages
    """
    try:
        scenarios = await get_margin_scenarios(session)

        response = "📈 <b>Сценарии маржи</b>\n"
        response += f"<i>При разном % использования лимитов</i>\n\n"

        scenario_labels = {
            "scenario_30": ("🟢", "30% (оптимистичный)"),
            "scenario_50": ("🟡", "50% (реалистичный)"),
            "scenario_70": ("🟠", "70% (пессимистичный)"),
            "scenario_100": ("🔴", "100% (worst case)"),
        }

        tier_emojis = {"basic": "⭐", "premium": "💎", "vip": "👑"}

        for scenario_key, (emoji, label) in scenario_labels.items():
            data = scenarios.get(scenario_key, {})
            if not data:
                continue

            response += f"{emoji} <b>{label}:</b>\n"

            tiers = data.get("tiers", {})
            for tier_name, tier_data in tiers.items():
                t_emoji = tier_emojis.get(tier_name, "📊")
                margin_pct = tier_data.get("margin_percent", 0)

                # Status indicator
                if margin_pct >= 60:
                    status = "✅"
                elif margin_pct >= 40:
                    status = "⚠️"
                elif margin_pct > 0:
                    status = "⚠️"
                else:
                    status = "❌"

                response += f"├ {t_emoji} {tier_name.upper()}: {margin_pct:.1f}% {status}\n"

            overall = data.get("overall_margin_percent", 0)
            response += f"└ Общая: <b>{overall:.1f}%</b>\n\n"

        response += "💡 <i>Маржа зависит от % использования лимитов пользователями</i>"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Назад", callback_data="admin_unit_economics")],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error loading scenarios: {e}")
        await callback.answer("❌ Ошибка при загрузке сценариев", show_alert=True)


# ===========================
# FRAUD DETECTION HANDLERS
# ===========================


@router.callback_query(F.data == "admin_fraud")
async def admin_fraud_menu(callback: CallbackQuery, session: AsyncSession):
    """Show fraud detection main menu with summary"""
    try:
        from src.services.fraud_detection_service import get_abuse_summary_for_admin

        summary = await get_abuse_summary_for_admin(session, days=30)

        response = "🚨 <b>Fraud Detection</b>\n\n"

        # Status counts
        status_counts = summary.get("status_counts", {})
        detected = status_counts.get("detected", 0)
        confirmed = status_counts.get("confirmed_abuse", 0)
        false_pos = status_counts.get("false_positive", 0)
        ignored = status_counts.get("ignored", 0)

        response += "📊 <b>Статистика (30 дней):</b>\n"
        response += f"├ 🔍 Обнаружено: <b>{detected}</b>\n"
        response += f"├ ✅ Подтверждено: <b>{confirmed}</b>\n"
        response += f"├ ❌ Ложные: <b>{false_pos}</b>\n"
        response += f"└ ⏭️ Игнорируется: <b>{ignored}</b>\n\n"

        # Type counts
        type_counts = summary.get("type_counts", {})
        ip_match = type_counts.get("ip_match", 0)
        fp_match = type_counts.get("fingerprint_match", 0)
        self_ref = type_counts.get("self_referral", 0)
        multi_trial = type_counts.get("multi_trial", 0)

        response += "🔗 <b>По типу:</b>\n"
        response += f"├ 🌐 IP совпадение: <b>{ip_match}</b>\n"
        response += f"├ 🖥️ Fingerprint: <b>{fp_match}</b>\n"
        response += f"├ 🔄 Self-referral: <b>{self_ref}</b>\n"
        response += f"└ 🎁 Multi-trial: <b>{multi_trial}</b>\n\n"

        # Pending review
        pending = summary.get("pending_review_count", 0)
        if pending > 0:
            response += f"⚠️ <b>Ожидает ревью: {pending}</b>\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔍 Связи", callback_data="admin_fraud_list_0"
                    ),
                    InlineKeyboardButton(
                        text="⚠️ Ревью", callback_data="admin_fraud_pending_0"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🌐 По IP", callback_data="admin_fp_by_ip"
                    ),
                    InlineKeyboardButton(
                        text="🖥️ По Fingerprint", callback_data="admin_fp_by_fp"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🎁 Multi-trial", callback_data="admin_fraud_type_multi_trial_0"
                    ),
                    InlineKeyboardButton(
                        text="🔄 Self-ref", callback_data="admin_fraud_type_self_referral_0"
                    ),
                ],
                [
                    InlineKeyboardButton(text="« Назад", callback_data="admin_refresh"),
                ],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error loading fraud summary: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)


@router.callback_query(F.data.startswith("admin_fraud_list_"))
async def admin_fraud_list(callback: CallbackQuery, session: AsyncSession):
    """Show list of all linked accounts with pagination"""
    try:
        from src.services.fraud_detection_service import get_linked_accounts_with_users

        # Parse page number
        page = int(callback.data.split("_")[-1])
        per_page = 5

        links = await get_linked_accounts_with_users(
            session,
            min_confidence=0.3,
            limit=per_page + 1,  # +1 to check if more pages
        )

        # Simple offset emulation (for demo)
        start_idx = page * per_page
        has_more = len(links) > per_page
        links = links[:per_page]

        if not links:
            await callback.answer("Нет связанных аккаунтов", show_alert=True)
            return

        response = "🔗 <b>Связанные аккаунты</b>\n\n"

        for link in links:
            user_a = link.get("user_a") or {}
            user_b = link.get("user_b") or {}

            # User identifiers
            a_name = user_a.get("email") or f"TG:{user_a.get('telegram_id')}" or f"ID:{user_a.get('id')}"
            b_name = user_b.get("email") or f"TG:{user_b.get('telegram_id')}" or f"ID:{user_b.get('id')}"

            # Status emoji
            status = link.get("status", "detected")
            status_emoji = {
                "detected": "🔍",
                "confirmed_abuse": "🚨",
                "false_positive": "✅",
                "ignored": "⏭️",
            }.get(status, "❓")

            # Type emoji
            link_type = link.get("link_type", "")
            type_emoji = {
                "ip_match": "🌐",
                "fingerprint_match": "🖥️",
                "self_referral": "🔄",
                "multi_trial": "🎁",
            }.get(link_type, "🔗")

            confidence = link.get("confidence_score", 0) * 100

            response += f"{status_emoji} {type_emoji} <b>#{link.get('id')}</b> ({confidence:.0f}%)\n"
            response += f"├ A: <code>{a_name[:20]}</code>\n"
            response += f"├ B: <code>{b_name[:20]}</code>\n"

            # Show shared data
            shared_ips = link.get("shared_ips", [])
            if shared_ips and len(shared_ips) > 0:
                response += f"├ IP: <code>{shared_ips[0]}</code>\n"

            response += f"└ {link_type}\n\n"

        # Pagination
        buttons = []
        if page > 0:
            buttons.append(
                InlineKeyboardButton(
                    text="« Назад", callback_data=f"admin_fraud_list_{page-1}"
                )
            )
        if has_more:
            buttons.append(
                InlineKeyboardButton(
                    text="Вперёд »", callback_data=f"admin_fraud_list_{page+1}"
                )
            )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                buttons if buttons else [],
                [InlineKeyboardButton(text="« Меню Fraud", callback_data="admin_fraud")],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error loading fraud list: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)


@router.callback_query(F.data.startswith("admin_fraud_pending_"))
async def admin_fraud_pending(callback: CallbackQuery, session: AsyncSession):
    """Show pending fraud cases for review"""
    try:
        from src.services.fraud_detection_service import get_linked_accounts_with_users

        links = await get_linked_accounts_with_users(
            session,
            status="detected",
            min_confidence=0.5,
            limit=10,
        )

        if not links:
            await callback.answer("Нет кейсов на проверку! 🎉", show_alert=True)
            return

        response = "⚠️ <b>Ожидают проверки</b>\n\n"

        for link in links:
            user_a = link.get("user_a") or {}
            user_b = link.get("user_b") or {}

            a_name = user_a.get("email") or f"TG:{user_a.get('telegram_id')}"
            b_name = user_b.get("email") or f"TG:{user_b.get('telegram_id')}"

            link_type = link.get("link_type", "")
            confidence = link.get("confidence_score", 0) * 100

            type_labels = {
                "ip_match": "🌐 IP",
                "fingerprint_match": "🖥️ FP",
                "self_referral": "🔄 SelfRef",
                "multi_trial": "🎁 Trial",
            }

            response += f"<b>#{link.get('id')}</b> • {type_labels.get(link_type, link_type)} • {confidence:.0f}%\n"
            response += f"├ {a_name[:25]}\n"
            response += f"└ {b_name[:25]}\n\n"

        response += "\n<i>Используй /fraud_review ID для ревью</i>"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Меню Fraud", callback_data="admin_fraud")],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error loading pending: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin_fraud_type_"))
async def admin_fraud_by_type(callback: CallbackQuery, session: AsyncSession):
    """Show fraud cases filtered by type"""
    try:
        from src.services.fraud_detection_service import get_all_linked_accounts
        from src.database.models import LinkedAccount

        # Parse type from callback (e.g., admin_fraud_type_multi_trial_0)
        parts = callback.data.split("_")
        fraud_type = "_".join(parts[3:-1])  # multi_trial or self_referral
        page = int(parts[-1])

        type_labels = {
            "multi_trial": "🎁 Multi-trial Abuse",
            "self_referral": "🔄 Self-referral",
        }

        # Get from DB directly
        stmt = (
            select(LinkedAccount)
            .where(LinkedAccount.link_type == fraud_type)
            .order_by(LinkedAccount.created_at.desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        links = result.scalars().all()

        if not links:
            await callback.answer(f"Нет кейсов типа {fraud_type}", show_alert=True)
            return

        response = f"<b>{type_labels.get(fraud_type, fraud_type)}</b>\n\n"

        for link in links:
            status_emoji = {
                "detected": "🔍",
                "confirmed_abuse": "🚨",
                "false_positive": "✅",
                "ignored": "⏭️",
            }.get(link.status, "❓")

            confidence = link.confidence_score * 100

            response += f"{status_emoji} <b>#{link.id}</b> • {confidence:.0f}%\n"
            response += f"├ User A: <code>{link.user_id_a}</code>\n"
            response += f"├ User B: <code>{link.user_id_b}</code>\n"
            response += f"└ {link.status}\n\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Меню Fraud", callback_data="admin_fraud")],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error loading by type: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.message(Command("fraud_review"))
async def cmd_fraud_review(message: Message, session: AsyncSession, command: CommandObject):
    """
    Review a specific fraud case

    Usage: /fraud_review <link_id> <action>
    Actions: confirm, reject, ignore, ban
    """
    from src.services.fraud_detection_service import (
        update_linked_account_status,
        ban_linked_accounts,
    )
    from src.database.models import LinkedAccountStatus

    if not command.args:
        await message.reply(
            "📋 <b>Fraud Review</b>\n\n"
            "Использование:\n"
            "<code>/fraud_review ID action</code>\n\n"
            "Actions:\n"
            "• <code>confirm</code> - подтвердить abuse\n"
            "• <code>reject</code> - ложное срабатывание\n"
            "• <code>ignore</code> - игнорировать\n"
            "• <code>ban</code> - забанить оба аккаунта\n\n"
            "Пример: <code>/fraud_review 42 confirm</code>"
        )
        return

    args = command.args.split()
    if len(args) < 2:
        await message.reply("❌ Укажите ID и action")
        return

    try:
        link_id = int(args[0])
        action = args[1].lower()
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return

    # Get admin user
    admin = await get_user_by_telegram_id(session, message.from_user.id)
    if not admin:
        await message.reply("❌ Админ не найден")
        return

    action_map = {
        "confirm": LinkedAccountStatus.CONFIRMED_ABUSE.value,
        "reject": LinkedAccountStatus.FALSE_POSITIVE.value,
        "ignore": LinkedAccountStatus.IGNORED.value,
    }

    if action == "ban":
        result = await ban_linked_accounts(session, link_id, admin.id, ban_both=True)
        if result["success"]:
            await message.reply(
                f"🚨 <b>Аккаунты забанены!</b>\n\n"
                f"Link ID: {link_id}\n"
                f"Banned users: {result['banned_users']}"
            )
        else:
            await message.reply(f"❌ Ошибка: {result.get('error')}")

    elif action in action_map:
        updated = await update_linked_account_status(
            session,
            link_id=link_id,
            status=action_map[action],
            admin_user_id=admin.id,
        )
        if updated:
            await message.reply(
                f"✅ <b>Статус обновлён!</b>\n\n"
                f"Link ID: {link_id}\n"
                f"New status: {action_map[action]}"
            )
        else:
            await message.reply(f"❌ Link #{link_id} не найден")
    else:
        await message.reply(f"❌ Неизвестный action: {action}")


# ===========================
# FINGERPRINT GROUPING HANDLERS
# ===========================


@router.callback_query(F.data == "admin_fp_by_ip")
async def admin_fingerprints_by_ip(callback: CallbackQuery, session: AsyncSession):
    """Show fingerprints grouped by IP address - find shared IPs"""
    try:
        from src.database.models import DeviceFingerprint, User

        # Find IPs used by multiple users
        stmt = (
            select(
                DeviceFingerprint.ip_address,
                func.count(func.distinct(DeviceFingerprint.user_id)).label("user_count"),
                func.array_agg(func.distinct(DeviceFingerprint.user_id)).label("user_ids"),
            )
            .where(DeviceFingerprint.ip_address != "unknown")
            .where(DeviceFingerprint.ip_address != "internal")
            .group_by(DeviceFingerprint.ip_address)
            .having(func.count(func.distinct(DeviceFingerprint.user_id)) > 1)
            .order_by(func.count(func.distinct(DeviceFingerprint.user_id)).desc())
            .limit(15)
        )
        result = await session.execute(stmt)
        rows = result.all()

        if not rows:
            await callback.answer("Нет общих IP адресов", show_alert=True)
            return

        response = "🌐 <b>Общие IP адреса</b>\n"
        response += "<i>IP используемые несколькими аккаунтами</i>\n\n"

        for row in rows:
            ip = row.ip_address
            user_count = row.user_count
            user_ids = row.user_ids[:5] if row.user_ids else []

            # Get user info
            users_info = []
            for uid in user_ids:
                user_stmt = select(User).where(User.id == uid)
                user_result = await session.execute(user_stmt)
                user = user_result.scalar_one_or_none()
                if user:
                    name = user.email or f"TG:{user.telegram_id}" or f"ID:{uid}"
                    users_info.append(f"<code>{name[:15]}</code>")

            response += f"🔴 <b>{ip}</b> ({user_count} юзеров)\n"
            response += f"└ {', '.join(users_info)}\n\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Fraud Menu", callback_data="admin_fraud")],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error loading fingerprints by IP: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)


@router.callback_query(F.data == "admin_fp_by_fp")
async def admin_fingerprints_by_fingerprint(callback: CallbackQuery, session: AsyncSession):
    """Show fingerprints grouped by visitor_id - find shared browser fingerprints"""
    try:
        from src.database.models import DeviceFingerprint, User

        # Find visitor_ids used by multiple users
        stmt = (
            select(
                DeviceFingerprint.visitor_id,
                func.count(func.distinct(DeviceFingerprint.user_id)).label("user_count"),
                func.array_agg(func.distinct(DeviceFingerprint.user_id)).label("user_ids"),
            )
            .where(DeviceFingerprint.visitor_id.isnot(None))
            .where(DeviceFingerprint.visitor_id != "")
            .group_by(DeviceFingerprint.visitor_id)
            .having(func.count(func.distinct(DeviceFingerprint.user_id)) > 1)
            .order_by(func.count(func.distinct(DeviceFingerprint.user_id)).desc())
            .limit(15)
        )
        result = await session.execute(stmt)
        rows = result.all()

        if not rows:
            await callback.answer("Нет общих fingerprints", show_alert=True)
            return

        response = "🖥️ <b>Общие Fingerprints</b>\n"
        response += "<i>Браузеры используемые несколькими аккаунтами</i>\n\n"

        for row in rows:
            visitor_id = row.visitor_id
            user_count = row.user_count
            user_ids = row.user_ids[:5] if row.user_ids else []

            # Shorten visitor_id for display
            short_vid = f"{visitor_id[:8]}...{visitor_id[-4:]}" if len(visitor_id) > 16 else visitor_id

            # Get user info
            users_info = []
            for uid in user_ids:
                user_stmt = select(User).where(User.id == uid)
                user_result = await session.execute(user_stmt)
                user = user_result.scalar_one_or_none()
                if user:
                    name = user.email or f"TG:{user.telegram_id}" or f"ID:{uid}"
                    users_info.append(f"<code>{name[:15]}</code>")

            response += f"🔴 <b>{short_vid}</b> ({user_count} юзеров)\n"
            response += f"└ {', '.join(users_info)}\n\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Fraud Menu", callback_data="admin_fraud")],
            ]
        )

        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error loading fingerprints: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)


@router.message(Command("fp_user"))
async def cmd_fingerprints_by_user(message: Message, session: AsyncSession, command: CommandObject):
    """
    Show all fingerprints for a specific user

    Usage: /fp_user <user_id or telegram_id>
    """
    from src.database.models import DeviceFingerprint, User

    if not command.args:
        await message.reply(
            "📋 <b>User Fingerprints</b>\n\n"
            "Использование:\n"
            "<code>/fp_user USER_ID</code>\n\n"
            "Пример: <code>/fp_user 123</code>"
        )
        return

    try:
        user_id = int(command.args.strip())
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return

    # Try to find user by ID or telegram_id
    user_stmt = select(User).where(
        (User.id == user_id) | (User.telegram_id == user_id)
    )
    user_result = await session.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        await message.reply(f"❌ Пользователь {user_id} не найден")
        return

    # Get fingerprints
    fp_stmt = (
        select(DeviceFingerprint)
        .where(DeviceFingerprint.user_id == user.id)
        .order_by(DeviceFingerprint.created_at.desc())
        .limit(20)
    )
    fp_result = await session.execute(fp_stmt)
    fingerprints = fp_result.scalars().all()

    if not fingerprints:
        await message.reply(f"📭 Нет fingerprints для пользователя {user.id}")
        return

    user_name = user.email or f"TG:{user.telegram_id}" or f"ID:{user.id}"
    response = f"🖥️ <b>Fingerprints пользователя</b>\n"
    response += f"👤 {user_name}\n\n"

    # Collect unique IPs and fingerprints
    unique_ips = set()
    unique_fps = set()

    for fp in fingerprints:
        unique_ips.add(fp.ip_address)
        if fp.visitor_id:
            unique_fps.add(fp.visitor_id)

    response += f"📊 Всего записей: {len(fingerprints)}\n"
    response += f"🌐 Уникальных IP: {len(unique_ips)}\n"
    response += f"🖥️ Уникальных FP: {len(unique_fps)}\n\n"

    response += "<b>Последние события:</b>\n"
    for fp in fingerprints[:10]:
        event = fp.event_type
        ip = fp.ip_address
        platform = fp.platform
        date = fp.created_at.strftime("%d.%m %H:%M")

        event_emoji = {
            "registration": "🆕",
            "login": "🔑",
            "referral_use": "🔗",
            "payment": "💳",
        }.get(event, "📝")

        response += f"{event_emoji} {date} • {platform} • <code>{ip}</code>\n"

    await message.reply(response)


# ===========================
# TASK CREATION COMMAND
# ===========================


@router.message(Command("task_add"))
async def cmd_task_add(message: Message, command: CommandObject, session: AsyncSession):
    """
    Create social task via command

    Usage:
    /task_add telegram_channel @channel 100 [penalty]
    /task_add telegram_channel -1001234567890 https://t.me/+AbCdEfG 100 [penalty]
    /task_add telegram_chat @chat 100 [penalty]
    /task_add telegram_chat -1001234567890 https://t.me/+XyZ123 100 [penalty]
    /task_add twitter @username 100 [penalty]

    Args:
    - type: telegram_channel, telegram_chat, twitter
    - target: @username, chat ID, или invite link
    - reward: награда в $SYNTRA
    - penalty: штраф за отписку (по умолчанию 50% от reward)
    """
    import re
    from config.config import ADMIN_IDS
    from src.services.social_tasks_service import SocialTasksService
    from src.database.models import TaskType, TaskStatus, VerificationType

    # Check admin
    if message.from_user.id not in ADMIN_IDS:
        return

    if not command.args:
        await message.reply(
            "❌ <b>Использование:</b>\n\n"
            "<b>Публичный канал/чат:</b>\n"
            "<code>/task_add telegram_channel @channel 100</code>\n"
            "<code>/task_add telegram_chat @chat 100</code>\n\n"
            "<b>Приватный канал/чат:</b>\n"
            "<code>/task_add telegram_channel -1001234567890 https://t.me/+AbCdEfG 100</code>\n"
            "<code>/task_add telegram_chat -1001234567890 https://t.me/+XyZ 100</code>\n\n"
            "<b>Twitter:</b>\n"
            "<code>/task_add twitter @username 100</code>\n\n"
            "Параметры:\n"
            "• тип задания\n"
            "• @username или ID канала\n"
            "• (для приватных) invite ссылка\n"
            "• награда в $SYNTRA\n"
            "• (опционально) штраф за отписку"
        )
        return

    args = command.args.split()

    if len(args) < 3:
        await message.reply(
            "❌ Недостаточно аргументов!\n\n"
            "Публичный: <code>/task_add telegram_channel @syntra_news 100</code>\n"
            "Приватный: <code>/task_add telegram_channel -100123 https://t.me/+abc 100</code>"
        )
        return

    task_type_str = args[0].lower()
    target = args[1]

    # Map type string to TaskType and VerificationType
    type_mapping = {
        "telegram_channel": (
            TaskType.TELEGRAM_SUBSCRIBE_CHANNEL.value,
            VerificationType.AUTO_TELEGRAM.value,
            "✈️ Подписка на канал",
            "📢",
        ),
        "telegram_chat": (
            TaskType.TELEGRAM_SUBSCRIBE_CHAT.value,
            VerificationType.AUTO_TELEGRAM.value,
            "💬 Вступление в чат",
            "💬",
        ),
        "twitter": (
            TaskType.TWITTER_FOLLOW.value,
            VerificationType.MANUAL_SCREENSHOT.value,
            "🐦 Подписка на Twitter",
            "🐦",
        ),
    }

    if task_type_str not in type_mapping:
        await message.reply(
            "❌ Неизвестный тип задания!\n\n"
            "Доступные типы:\n"
            "• telegram_channel\n"
            "• telegram_chat\n"
            "• twitter"
        )
        return

    task_type, verification_type, title_base, icon = type_mapping[task_type_str]

    # Parse arguments based on type
    invite_url = None
    channel_id = None
    target_display = None
    custom_name = None

    if task_type_str in ["telegram_channel", "telegram_chat"]:
        # Check if target is numeric ID (private channel/chat)
        if target.lstrip("-").isdigit():
            channel_id = target
            # Next arg should be invite URL
            if len(args) < 4:
                await message.reply(
                    "❌ Для приватного канала/чата нужна invite ссылка!\n\n"
                    "Пример: <code>/task_add telegram_channel -1001234567890 https://t.me/+AbCdEfG 100</code>\n"
                    "С названием: <code>/task_add telegram_channel -1001234567890 https://t.me/+AbCdEfG 100 \"Название канала\"</code>"
                )
                return

            invite_url = args[2]
            # Validate invite URL
            if not re.match(r'https?://t\.me/(\+[\w-]+|joinchat/[\w-]+)', invite_url):
                await message.reply(
                    "❌ Неверный формат invite ссылки!\n\n"
                    "Ожидается: https://t.me/+AbCdEfG или https://t.me/joinchat/AbCdEfG"
                )
                return

            try:
                reward = int(args[3])
            except ValueError:
                await message.reply("❌ Награда должна быть числом!")
                return

            penalty = int(args[4]) if len(args) > 4 else reward // 2

            # Check for custom name in quotes in original args
            full_args = command.args
            name_match = re.search(r'"([^"]+)"', full_args)
            if name_match:
                custom_name = name_match.group(1)
                target_display = custom_name
            else:
                target_display = f"Приватный ({channel_id})"

        else:
            # Public channel/chat with username
            target_clean = target.replace("@", "")
            channel_id = target_clean
            invite_url = f"https://t.me/{target_clean}"
            target_display = f"@{target_clean}"

            try:
                reward = int(args[2])
            except ValueError:
                await message.reply("❌ Награда должна быть числом!")
                return

            penalty = int(args[3]) if len(args) > 3 else reward // 2

    else:
        # Twitter
        target_clean = target.replace("@", "")
        target_display = f"@{target_clean}"

        try:
            reward = int(args[2])
        except ValueError:
            await message.reply("❌ Награда должна быть числом!")
            return

        penalty = int(args[3]) if len(args) > 3 else reward // 2

    # Prepare task data
    title_ru = f"{title_base}: {target_display}"
    title_en = f"{title_base}: {target_display}"

    task_data = {
        "title_ru": title_ru,
        "title_en": title_en,
        "description_ru": f"Подпишитесь и получите {reward} $SYNTRA",
        "description_en": f"Subscribe and get {reward} $SYNTRA",
        "icon": icon,
        "task_type": task_type,
        "verification_type": verification_type,
        "reward_points": reward,
        "unsubscribe_penalty": penalty,
        "status": TaskStatus.ACTIVE.value,
    }

    # Set target based on type
    if task_type_str in ["telegram_channel", "telegram_chat"]:
        task_data["telegram_channel_id"] = channel_id
        task_data["telegram_channel_url"] = invite_url
    else:
        # Twitter
        task_data["twitter_target_username"] = target_clean

    try:
        task = await SocialTasksService.create_task(
            session=session,
            admin_telegram_id=message.from_user.id,
            task_data=task_data,
        )

        response = (
            f"✅ <b>Задание создано!</b>\n\n"
            f"ID: <code>{task.id}</code>\n"
            f"Тип: {icon} {task_type_str}\n"
            f"Цель: {target_display}\n"
        )

        if invite_url and task_type_str != "twitter":
            response += f"Ссылка: {invite_url}\n"

        response += (
            f"Награда: {reward} $SYNTRA\n"
            f"Штраф: {penalty} $SYNTRA\n"
            f"Статус: 🟢 Активно\n\n"
            f"Задание сразу доступно пользователям!"
        )

        await message.reply(response)

        logger.info(
            f"Admin {message.from_user.id} created task {task.id}: "
            f"{task_type_str} {target_display} +{reward} SYNTRA"
        )

    except Exception as e:
        logger.exception(f"Error creating task: {e}")
        await message.reply(f"❌ Ошибка создания задания: {e}")


# ===========================
# STARTAPP PARAMETER TRACKING
# ===========================


@router.callback_query(F.data == "admin_startapp")
async def admin_startapp_stats(callback: CallbackQuery, session: AsyncSession):
    """Show startapp parameter statistics"""
    try:
        # Get total users with startapp parameter
        stmt_with = select(func.count(User.id)).where(User.startapp_param.isnot(None))
        result_with = await session.execute(stmt_with)
        total_with_startapp = result_with.scalar() or 0

        # Get total users without startapp parameter
        stmt_without = select(func.count(User.id)).where(User.startapp_param.is_(None))
        result_without = await session.execute(stmt_without)
        total_without_startapp = result_without.scalar() or 0

        # Get breakdown by startapp parameter
        stmt = (
            select(
                User.startapp_param,
                func.count(User.id).label("user_count"),
                func.min(User.created_at).label("first_seen"),
                func.max(User.created_at).label("last_seen"),
            )
            .where(User.startapp_param.isnot(None))
            .group_by(User.startapp_param)
            .order_by(func.count(User.id).desc())
            .limit(20)
        )

        result = await session.execute(stmt)
        rows = result.all()

        response = "🔗 <b>Startapp Parameter Statistics</b>\n\n"
        response += "📊 <b>Общая статистика:</b>\n"
        response += f"├ С параметром: <b>{total_with_startapp}</b>\n"
        response += f"└ Без параметра: <b>{total_without_startapp}</b>\n\n"

        if rows:
            response += "📈 <b>Топ источников (до 20):</b>\n\n"
            for i, row in enumerate(rows, 1):
                param = row.startapp_param
                count = row.user_count
                first_date = row.first_seen.strftime("%d.%m.%Y") if row.first_seen else "—"
                last_date = row.last_seen.strftime("%d.%m.%Y") if row.last_seen else "—"

                response += f"{i}. <code>{param}</code>\n"
                response += f"   👥 Пользователей: <b>{count}</b>\n"
                response += f"   📅 Первый: {first_date} | Последний: {last_date}\n\n"
        else:
            response += "ℹ️ Нет данных о startapp параметрах"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_startapp"),
                    InlineKeyboardButton(text="◀️ Назад", callback_data="admin_refresh"),
                ]
            ]
        )

        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing startapp stats: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# ===========================
# CLASS STATS (CONTEXT GATES)
# ===========================


@router.callback_query(F.data == "admin_class_stats")
async def admin_class_stats_menu(callback: CallbackQuery, session: AsyncSession):
    """Show class stats main menu with summary"""
    try:
        from src.database.models import ScenarioClassStats

        # Get counts
        stmt_total = select(func.count(ScenarioClassStats.id))
        result_total = await session.execute(stmt_total)
        total_classes = result_total.scalar() or 0

        stmt_enabled = select(func.count(ScenarioClassStats.id)).where(
            ScenarioClassStats.is_enabled == True
        )
        result_enabled = await session.execute(stmt_enabled)
        enabled_count = result_enabled.scalar() or 0

        stmt_disabled = select(func.count(ScenarioClassStats.id)).where(
            ScenarioClassStats.is_enabled == False
        )
        result_disabled = await session.execute(stmt_disabled)
        disabled_count = result_disabled.scalar() or 0

        # Get L1/L2 counts
        stmt_l1 = select(func.count(ScenarioClassStats.id)).where(
            ScenarioClassStats.trend_bucket == "__any__"
        )
        result_l1 = await session.execute(stmt_l1)
        l1_count = result_l1.scalar() or 0

        l2_count = total_classes - l1_count

        # Get top performers
        stmt_top = (
            select(ScenarioClassStats)
            .where(ScenarioClassStats.total_trades >= 20)
            .order_by(ScenarioClassStats.avg_ev_r.desc())
            .limit(5)
        )
        result_top = await session.execute(stmt_top)
        top_classes = result_top.scalars().all()

        # Get worst performers (disabled)
        stmt_worst = (
            select(ScenarioClassStats)
            .where(ScenarioClassStats.is_enabled == False)
            .order_by(ScenarioClassStats.avg_ev_r.asc())
            .limit(5)
        )
        result_worst = await session.execute(stmt_worst)
        worst_classes = result_worst.scalars().all()

        response = "📚 <b>Scenario Class Statistics</b>\n\n"

        response += "📊 <b>Общая статистика:</b>\n"
        response += f"├ Всего классов: <b>{total_classes}</b>\n"
        response += f"├ ✅ Enabled: <b>{enabled_count}</b>\n"
        response += f"├ ❌ Disabled: <b>{disabled_count}</b>\n"
        response += f"├ L1 (coarse): <b>{l1_count}</b>\n"
        response += f"└ L2 (fine): <b>{l2_count}</b>\n\n"

        if top_classes:
            response += "🏆 <b>Top Performers (EV):</b>\n"
            for c in top_classes:
                wr = c.winrate * 100
                response += f"├ {c.archetype[:15]}|{c.side[:1].upper()}|{c.timeframe}\n"
                response += f"│  EV: <b>{c.avg_ev_r:+.2f}R</b> WR: {wr:.0f}% ({c.total_trades})\n"
            response += "\n"

        if worst_classes:
            response += "💀 <b>Disabled Classes:</b>\n"
            for c in worst_classes:
                reason = (c.disable_reason or "")[:25]
                response += f"├ {c.archetype[:15]}|{c.side[:1].upper()}|{c.timeframe}\n"
                response += f"│  EV: <b>{c.avg_ev_r:+.2f}R</b> | {reason}\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📈 По EV", callback_data="admin_cs_by_ev_0"
                    ),
                    InlineKeyboardButton(
                        text="📊 По WR", callback_data="admin_cs_by_wr_0"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Disabled", callback_data="admin_cs_disabled_0"
                    ),
                    InlineKeyboardButton(
                        text="🎯 По архетипу", callback_data="admin_cs_archetypes"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔄 Пересчитать", callback_data="admin_cs_recalculate"
                    ),
                ],
                [
                    InlineKeyboardButton(text="◀️ Назад", callback_data="admin_refresh"),
                ],
            ]
        )

        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing class stats: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("admin_cs_by_ev_"))
async def admin_class_stats_by_ev(callback: CallbackQuery, session: AsyncSession):
    """Show classes sorted by EV with pagination"""
    try:
        from src.database.models import ScenarioClassStats

        page = int(callback.data.split("_")[-1])
        per_page = 10
        offset = page * per_page

        stmt = (
            select(ScenarioClassStats)
            .where(ScenarioClassStats.total_trades >= 10)
            .order_by(ScenarioClassStats.avg_ev_r.desc())
            .offset(offset)
            .limit(per_page + 1)
        )
        result = await session.execute(stmt)
        classes = result.scalars().all()

        has_more = len(classes) > per_page
        classes = classes[:per_page]

        response = f"📈 <b>Classes by EV</b> (стр. {page + 1})\n\n"

        for c in classes:
            status = "✅" if c.is_enabled else "❌"
            wr = c.winrate * 100
            level = "L1" if c.trend_bucket == "__any__" else "L2"
            response += f"{status} <b>{c.archetype[:12]}</b>|{c.side[:1].upper()}|{c.timeframe} [{level}]\n"
            response += f"   EV: <b>{c.avg_ev_r:+.3f}R</b> WR: {wr:.0f}% | n={c.total_trades}\n"

        buttons = []
        nav_row = []
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(text="◀️", callback_data=f"admin_cs_by_ev_{page - 1}")
            )
        if has_more:
            nav_row.append(
                InlineKeyboardButton(text="▶️", callback_data=f"admin_cs_by_ev_{page + 1}")
            )
        if nav_row:
            buttons.append(nav_row)

        buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_class_stats")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing classes by EV: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("admin_cs_by_wr_"))
async def admin_class_stats_by_wr(callback: CallbackQuery, session: AsyncSession):
    """Show classes sorted by winrate with pagination"""
    try:
        from src.database.models import ScenarioClassStats

        page = int(callback.data.split("_")[-1])
        per_page = 10
        offset = page * per_page

        stmt = (
            select(ScenarioClassStats)
            .where(ScenarioClassStats.total_trades >= 10)
            .order_by(ScenarioClassStats.winrate.desc())
            .offset(offset)
            .limit(per_page + 1)
        )
        result = await session.execute(stmt)
        classes = result.scalars().all()

        has_more = len(classes) > per_page
        classes = classes[:per_page]

        response = f"📊 <b>Classes by Winrate</b> (стр. {page + 1})\n\n"

        for c in classes:
            status = "✅" if c.is_enabled else "❌"
            wr = c.winrate * 100
            wr_ci = c.winrate_lower_ci * 100
            level = "L1" if c.trend_bucket == "__any__" else "L2"
            response += f"{status} <b>{c.archetype[:12]}</b>|{c.side[:1].upper()}|{c.timeframe} [{level}]\n"
            response += f"   WR: <b>{wr:.0f}%</b> (CI: {wr_ci:.0f}%) | n={c.total_trades}\n"

        buttons = []
        nav_row = []
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(text="◀️", callback_data=f"admin_cs_by_wr_{page - 1}")
            )
        if has_more:
            nav_row.append(
                InlineKeyboardButton(text="▶️", callback_data=f"admin_cs_by_wr_{page + 1}")
            )
        if nav_row:
            buttons.append(nav_row)

        buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_class_stats")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing classes by WR: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("admin_cs_disabled_"))
async def admin_class_stats_disabled(callback: CallbackQuery, session: AsyncSession):
    """Show disabled classes with reasons"""
    try:
        from src.database.models import ScenarioClassStats

        page = int(callback.data.split("_")[-1])
        per_page = 8
        offset = page * per_page

        stmt = (
            select(ScenarioClassStats)
            .where(ScenarioClassStats.is_enabled == False)
            .order_by(ScenarioClassStats.avg_ev_r.asc())
            .offset(offset)
            .limit(per_page + 1)
        )
        result = await session.execute(stmt)
        classes = result.scalars().all()

        has_more = len(classes) > per_page
        classes = classes[:per_page]

        response = f"❌ <b>Disabled Classes</b> (стр. {page + 1})\n\n"

        if not classes:
            response += "✅ Нет отключённых классов!"
        else:
            for c in classes:
                wr = c.winrate * 100
                reason = c.disable_reason or "—"
                response += f"<b>{c.archetype[:15]}</b>|{c.side[:1].upper()}|{c.timeframe}\n"
                response += f"├ EV: {c.avg_ev_r:+.3f}R | WR: {wr:.0f}%\n"
                response += f"├ Trades: {c.total_trades}\n"
                response += f"└ Reason: <i>{reason[:40]}</i>\n\n"

        buttons = []
        nav_row = []
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(text="◀️", callback_data=f"admin_cs_disabled_{page - 1}")
            )
        if has_more:
            nav_row.append(
                InlineKeyboardButton(text="▶️", callback_data=f"admin_cs_disabled_{page + 1}")
            )
        if nav_row:
            buttons.append(nav_row)

        buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_class_stats")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing disabled classes: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin_cs_archetypes")
async def admin_class_stats_archetypes(callback: CallbackQuery, session: AsyncSession):
    """Show stats grouped by archetype"""
    try:
        from src.database.models import ScenarioClassStats

        # Aggregate by archetype
        stmt = (
            select(
                ScenarioClassStats.archetype,
                func.count(ScenarioClassStats.id).label("class_count"),
                func.sum(ScenarioClassStats.total_trades).label("total_trades"),
                func.avg(ScenarioClassStats.winrate).label("avg_wr"),
                func.avg(ScenarioClassStats.avg_ev_r).label("avg_ev"),
                func.sum(
                    case((ScenarioClassStats.is_enabled == False, 1), else_=0)
                ).label("disabled_count"),
            )
            .group_by(ScenarioClassStats.archetype)
            .order_by(func.sum(ScenarioClassStats.total_trades).desc())
        )

        result = await session.execute(stmt)
        rows = result.all()

        response = "🎯 <b>Stats by Archetype</b>\n\n"

        for row in rows:
            wr = (row.avg_wr or 0) * 100
            ev = row.avg_ev or 0
            disabled = row.disabled_count or 0

            status = "❌" if disabled > 0 else "✅"
            response += f"{status} <b>{row.archetype}</b>\n"
            response += f"├ Classes: {row.class_count} (disabled: {disabled})\n"
            response += f"├ Trades: {row.total_trades or 0}\n"
            response += f"└ Avg EV: {ev:+.2f}R | WR: {wr:.0f}%\n\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_class_stats")]
            ]
        )

        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing archetype stats: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin_cs_recalculate")
async def admin_class_stats_recalculate(callback: CallbackQuery, session: AsyncSession):
    """Manually trigger class stats recalculation"""
    try:
        await callback.answer("⏳ Запускаю пересчёт...", show_alert=False)

        from src.learning.class_stats_analyzer import class_stats_analyzer

        stats = await class_stats_analyzer.recalculate_stats(
            session,
            include_testnet=False
        )

        response = "✅ <b>Пересчёт завершён!</b>\n\n"
        response += f"├ Классов обновлено: <b>{stats.get('classes_updated', 0)}</b>\n"
        response += f"├ L1 (coarse): {stats.get('l1_classes', 0)}\n"
        response += f"├ L2 (fine): {stats.get('l2_classes', 0)}\n"
        response += f"├ Сделок обработано: {stats.get('trades_processed', 0)}\n"
        response += f"└ Disabled: {stats.get('disabled_count', 0)}"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_class_stats")]
            ]
        )

        await safe_edit_message(callback, response, keyboard)

    except Exception as e:
        logger.exception(f"Error recalculating class stats: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# ===========================
# LEARNING SYSTEM STATS
# ===========================


@router.callback_query(F.data == "admin_learning")
async def admin_learning_menu(callback: CallbackQuery, session: AsyncSession):
    """Show learning system main menu with overview"""
    try:
        from src.database.models import (
            TradeOutcome, ConfidenceBucket, ArchetypeStats
        )

        # Feedback stats
        stmt_trades = select(func.count(TradeOutcome.id))
        result_trades = await session.execute(stmt_trades)
        total_trades = result_trades.scalar() or 0

        stmt_wins = select(func.count(TradeOutcome.id)).where(
            TradeOutcome.label == "win"
        )
        result_wins = await session.execute(stmt_wins)
        total_wins = result_wins.scalar() or 0

        overall_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0

        # Avg PnL
        stmt_pnl = select(func.avg(TradeOutcome.pnl_r)).where(
            TradeOutcome.pnl_r.isnot(None)
        )
        result_pnl = await session.execute(stmt_pnl)
        avg_pnl = result_pnl.scalar() or 0

        # Confidence buckets stats
        stmt_buckets = select(func.count(ConfidenceBucket.id))
        result_buckets = await session.execute(stmt_buckets)
        bucket_count = result_buckets.scalar() or 0

        stmt_bucket_samples = select(func.sum(ConfidenceBucket.sample_size))
        result_samples = await session.execute(stmt_bucket_samples)
        bucket_samples = result_samples.scalar() or 0

        # Archetype stats
        stmt_archetypes = select(func.count(ArchetypeStats.id))
        result_archetypes = await session.execute(stmt_archetypes)
        archetype_count = result_archetypes.scalar() or 0

        response = "🧠 <b>Learning System</b>\n\n"

        response += "📊 <b>Feedback Data:</b>\n"
        response += f"├ Всего сделок: <b>{total_trades}</b>\n"
        response += f"├ Winrate: <b>{overall_wr:.1f}%</b>\n"
        response += f"└ Avg PnL: <b>{avg_pnl:+.3f}R</b>\n\n"

        response += "🎯 <b>Calibration:</b>\n"
        response += f"├ Confidence buckets: <b>{bucket_count}</b>\n"
        response += f"└ Samples: <b>{bucket_samples}</b>\n\n"

        response += "📈 <b>Archetype Stats:</b>\n"
        response += f"└ Groups: <b>{archetype_count}</b>\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🎯 Confidence", callback_data="admin_learn_confidence"
                    ),
                    InlineKeyboardButton(
                        text="📈 Archetypes", callback_data="admin_learn_archetypes_0"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="📊 EV Distribution", callback_data="admin_learn_ev_dist"
                    ),
                    InlineKeyboardButton(
                        text="📋 Recent Trades", callback_data="admin_learn_recent_0"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔄 Recalculate All", callback_data="admin_learn_recalc"
                    ),
                ],
                [
                    InlineKeyboardButton(text="◀️ Назад", callback_data="admin_refresh"),
                ],
            ]
        )

        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing learning menu: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin_learn_confidence")
async def admin_learning_confidence(callback: CallbackQuery, session: AsyncSession):
    """Show confidence calibration buckets"""
    try:
        from src.database.models import ConfidenceBucket

        stmt = (
            select(ConfidenceBucket)
            .order_by(ConfidenceBucket.confidence_min)
        )
        result = await session.execute(stmt)
        buckets = result.scalars().all()

        response = "🎯 <b>Confidence Calibration</b>\n\n"

        if not buckets:
            response += "⚠️ Нет данных калибровки.\n"
            response += "Запустите пересчёт после накопления сделок."
        else:
            response += "Bucket │ Sample │ AI Conf │ Real WR │ Offset\n"
            response += "───────┼────────┼─────────┼─────────┼───────\n"

            for b in buckets:
                bucket_mid = (b.confidence_min + b.confidence_max) / 2
                real_wr = b.actual_winrate_smoothed * 100
                offset_pct = b.calibration_offset * 100

                # Visual indicator
                if b.calibration_offset > 0.05:
                    indicator = "📈"  # AI underconfident
                elif b.calibration_offset < -0.05:
                    indicator = "📉"  # AI overconfident
                else:
                    indicator = "✅"  # Well calibrated

                response += (
                    f"{indicator} {b.bucket_name:6} │ "
                    f"{b.sample_size:6} │ "
                    f"{bucket_mid*100:5.0f}% │ "
                    f"{real_wr:5.1f}% │ "
                    f"{offset_pct:+5.1f}%\n"
                )

            response += "\n<i>📈 = AI недооценивает, 📉 = переоценивает</i>"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_learning")]
            ]
        )

        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing confidence: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("admin_learn_archetypes_"))
async def admin_learning_archetypes(callback: CallbackQuery, session: AsyncSession):
    """Show archetype statistics with probabilities"""
    try:
        from src.database.models import ArchetypeStats

        page = int(callback.data.split("_")[-1])
        per_page = 8
        offset = page * per_page

        # Get unique archetypes with aggregated stats
        stmt = (
            select(ArchetypeStats)
            .where(ArchetypeStats.total_trades >= 10)
            .order_by(ArchetypeStats.total_trades.desc())
            .offset(offset)
            .limit(per_page + 1)
        )
        result = await session.execute(stmt)
        stats = result.scalars().all()

        has_more = len(stats) > per_page
        stats = stats[:per_page]

        response = f"📈 <b>Archetype Stats</b> (стр. {page + 1})\n\n"

        if not stats:
            response += "⚠️ Нет данных по архетипам.\n"
        else:
            for s in stats:
                wr = s.winrate * 100
                side_str = s.side[0].upper() if s.side else "?"

                # Calculate probabilities
                total = s.total_trades
                p_sl = s.exit_sl_count / total * 100 if total > 0 else 0
                p_tp1 = s.exit_tp1_count / total * 100 if total > 0 else 0
                p_tp2 = s.exit_tp2_count / total * 100 if total > 0 else 0
                p_tp3 = s.exit_tp3_count / total * 100 if total > 0 else 0

                response += f"<b>{s.archetype[:15]}</b> ({side_str})\n"
                response += f"├ Trades: {total} | WR: {wr:.0f}% | PF: {s.profit_factor:.2f}\n"
                response += f"├ P(SL): {p_sl:.0f}% P(TP1): {p_tp1:.0f}%\n"
                response += f"├ P(TP2): {p_tp2:.0f}% P(TP3): {p_tp3:.0f}%\n"
                response += f"└ MAE: {s.avg_mae_r:.2f}R MFE: {s.avg_mfe_r:.2f}R\n\n"

        buttons = []
        nav_row = []
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(text="◀️", callback_data=f"admin_learn_archetypes_{page - 1}")
            )
        if has_more:
            nav_row.append(
                InlineKeyboardButton(text="▶️", callback_data=f"admin_learn_archetypes_{page + 1}")
            )
        if nav_row:
            buttons.append(nav_row)

        buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_learning")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing archetypes: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin_learn_ev_dist")
async def admin_learning_ev_distribution(callback: CallbackQuery, session: AsyncSession):
    """Show EV distribution from historical trades"""
    try:
        from src.database.models import TradeOutcome
        import numpy as np

        # Get PnL distribution
        stmt = (
            select(TradeOutcome.pnl_r)
            .where(TradeOutcome.pnl_r.isnot(None))
            .order_by(TradeOutcome.closed_at.desc())
            .limit(500)
        )
        result = await session.execute(stmt)
        pnl_values = [r[0] for r in result.all()]

        response = "📊 <b>EV Distribution</b>\n\n"

        if len(pnl_values) < 10:
            response += "⚠️ Недостаточно данных (нужно >= 10 сделок)"
        else:
            pnl_arr = np.array(pnl_values)

            mean_pnl = np.mean(pnl_arr)
            median_pnl = np.median(pnl_arr)
            std_pnl = np.std(pnl_arr)
            p10 = np.percentile(pnl_arr, 10)
            p25 = np.percentile(pnl_arr, 25)
            p75 = np.percentile(pnl_arr, 75)
            p90 = np.percentile(pnl_arr, 90)

            # Histogram buckets
            bins = [-3, -2, -1, -0.5, 0, 0.5, 1, 2, 3, 5, 10]
            hist, _ = np.histogram(pnl_arr, bins=bins)

            response += f"📈 <b>Статистика ({len(pnl_values)} trades):</b>\n"
            response += f"├ Mean EV: <b>{mean_pnl:+.3f}R</b>\n"
            response += f"├ Median: {median_pnl:+.3f}R\n"
            response += f"├ Std Dev: {std_pnl:.3f}R\n"
            response += f"├ P10: {p10:+.2f}R | P90: {p90:+.2f}R\n"
            response += f"└ P25: {p25:+.2f}R | P75: {p75:+.2f}R\n\n"

            response += "📊 <b>Distribution:</b>\n"
            max_count = max(hist) if max(hist) > 0 else 1

            for i, count in enumerate(hist):
                if i < len(bins) - 1:
                    label = f"{bins[i]:+.1f} to {bins[i+1]:+.1f}"
                    bar_len = int(count / max_count * 10)
                    bar = "█" * bar_len + "░" * (10 - bar_len)
                    response += f"{label:12} {bar} {count}\n"

            # Win/Loss ratio
            wins = sum(1 for p in pnl_arr if p > 0)
            losses = sum(1 for p in pnl_arr if p < 0)
            wr = wins / len(pnl_arr) * 100

            response += f"\n✅ Wins: {wins} | ❌ Losses: {losses} | WR: {wr:.1f}%"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_learning")]
            ]
        )

        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing EV distribution: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("admin_learn_recent_"))
async def admin_learning_recent_trades(callback: CallbackQuery, session: AsyncSession):
    """Show recent trades for learning"""
    try:
        from src.database.models import TradeOutcome

        page = int(callback.data.split("_")[-1])
        per_page = 10
        offset = page * per_page

        stmt = (
            select(TradeOutcome)
            .where(TradeOutcome.closed_at.isnot(None))
            .order_by(TradeOutcome.closed_at.desc())
            .offset(offset)
            .limit(per_page + 1)
        )
        result = await session.execute(stmt)
        trades = result.scalars().all()

        has_more = len(trades) > per_page
        trades = trades[:per_page]

        response = f"📋 <b>Recent Trades</b> (стр. {page + 1})\n\n"

        if not trades:
            response += "⚠️ Нет закрытых сделок"
        else:
            for t in trades:
                # Outcome emoji
                if t.label == "win":
                    emoji = "✅"
                elif t.label == "loss":
                    emoji = "❌"
                else:
                    emoji = "⚪"

                pnl = t.pnl_r or 0
                arch = (t.primary_archetype or "?")[:12]
                side = (t.side or "?")[0].upper()

                closed = t.closed_at.strftime("%d.%m %H:%M") if t.closed_at else "?"

                response += f"{emoji} <b>{t.symbol}</b> {side} | {arch}\n"
                response += f"   PnL: <b>{pnl:+.2f}R</b> | {closed}\n"

        buttons = []
        nav_row = []
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(text="◀️", callback_data=f"admin_learn_recent_{page - 1}")
            )
        if has_more:
            nav_row.append(
                InlineKeyboardButton(text="▶️", callback_data=f"admin_learn_recent_{page + 1}")
            )
        if nav_row:
            buttons.append(nav_row)

        buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_learning")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing recent trades: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin_learn_recalc")
async def admin_learning_recalculate(callback: CallbackQuery, session: AsyncSession):
    """Manually trigger full learning recalculation"""
    try:
        await callback.answer("⏳ Запускаю пересчёт всех систем...", show_alert=False)

        from src.learning.scheduler import learning_scheduler

        # Trigger all recalculations
        await learning_scheduler.trigger_recalculation(include_testnet=False)

        response = "✅ <b>Пересчёт завершён!</b>\n\n"
        response += "Обновлено:\n"
        response += "├ Confidence Calibration\n"
        response += "├ Archetype Statistics\n"
        response += "└ Class Stats (Context Gates)"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_learning")]
            ]
        )

        await safe_edit_message(callback, response, keyboard)

    except Exception as e:
        logger.exception(f"Error recalculating learning: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# =============================================================================
# Forward Test Admin Section
# =============================================================================


@router.callback_query(F.data == "admin_forward_test")
async def admin_forward_test_menu(callback: CallbackQuery, session: AsyncSession):
    """Show Forward Test main menu with active trades"""
    try:
        from datetime import date, timedelta
        from src.services.forward_test.models import (
            ForwardTestSnapshot,
            ForwardTestMonitorState,
            ForwardTestOutcome,
        )
        from src.services.forward_test.enums import ScenarioState, OutcomeResult
        from src.services.forward_test.scheduler import forward_test_scheduler
        from src.services.forward_test.epoch_manager import get_current_epoch

        # Get current epoch
        current_epoch = await get_current_epoch()

        # Scheduler status
        status = forward_test_scheduler.get_status()
        enabled = status.get("enabled", True)
        enabled_emoji = "✅" if enabled else "⏸️"

        today = date.today()
        start_dt = datetime.combine(today, datetime.min.time())
        end_dt = datetime.combine(today, datetime.max.time())

        # Funnel stats for today
        gen_q = select(func.count()).select_from(ForwardTestSnapshot).where(
            and_(
                ForwardTestSnapshot.epoch == current_epoch,
                ForwardTestSnapshot.generated_at >= start_dt,
                ForwardTestSnapshot.generated_at <= end_dt
            )
        )
        generated = (await session.execute(gen_q)).scalar() or 0

        # Active trades (entered but not finished)
        active_states = [
            ScenarioState.ENTERED.value,
            ScenarioState.TP1.value,
        ]

        # Count ALL active trades first
        active_count_q = select(func.count()).select_from(ForwardTestMonitorState).join(
            ForwardTestSnapshot,
            ForwardTestMonitorState.snapshot_id == ForwardTestSnapshot.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.epoch == current_epoch,
                ForwardTestMonitorState.state.in_(active_states)
            )
        )
        active_count = (await session.execute(active_count_q)).scalar() or 0

        # Get trades for display (limit 25 to fit in message)
        active_q = (
            select(ForwardTestMonitorState, ForwardTestSnapshot)
            .join(
                ForwardTestSnapshot,
                ForwardTestMonitorState.snapshot_id == ForwardTestSnapshot.snapshot_id
            )
            .where(
                and_(
                    ForwardTestSnapshot.epoch == current_epoch,
                    ForwardTestMonitorState.state.in_(active_states)
                )
            )
            .order_by(ForwardTestMonitorState.entered_at.desc())
            .limit(25)
        )
        active_result = await session.execute(active_q)
        active_trades = active_result.all()

        # Count expired scenarios (never entered) - today only
        expired_before_entry_q = select(func.count()).select_from(ForwardTestMonitorState).join(
            ForwardTestSnapshot,
            ForwardTestMonitorState.snapshot_id == ForwardTestSnapshot.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.epoch == current_epoch,
                ForwardTestSnapshot.generated_at >= start_dt,
                ForwardTestSnapshot.generated_at <= end_dt,
                ForwardTestMonitorState.state == ScenarioState.EXPIRED.value,
                ForwardTestMonitorState.entered_at.is_(None)  # Never entered
            )
        )
        expired_before_entry = (await session.execute(expired_before_entry_q)).scalar() or 0

        # Waiting entry (triggered but not entered)
        waiting_entry_states = [
            ScenarioState.ARMED.value,
            ScenarioState.TRIGGERED.value,
        ]
        waiting_q = select(func.count()).select_from(ForwardTestMonitorState).join(
            ForwardTestSnapshot,
            ForwardTestMonitorState.snapshot_id == ForwardTestSnapshot.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.epoch == current_epoch,
                ForwardTestMonitorState.state.in_(waiting_entry_states)
            )
        )
        waiting_count = (await session.execute(waiting_q)).scalar() or 0

        # Finished today
        finished_q = select(func.count()).select_from(ForwardTestOutcome).join(
            ForwardTestSnapshot,
            ForwardTestOutcome.snapshot_id == ForwardTestSnapshot.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.epoch == current_epoch,
                ForwardTestSnapshot.generated_at >= start_dt,
                ForwardTestSnapshot.generated_at <= end_dt
            )
        )
        finished = (await session.execute(finished_q)).scalar() or 0

        # All-time stats (quick)
        alltime_q = select(
            func.count(),
            func.sum(ForwardTestOutcome.total_r),
        ).select_from(ForwardTestOutcome)
        alltime_result = await session.execute(alltime_q)
        alltime_row = alltime_result.one()
        alltime_count = alltime_row[0] or 0
        alltime_r = alltime_row[1] or 0.0

        # Build response
        response = f"🧪 <b>Forward Test</b> {enabled_emoji}\n\n"

        # All-time summary (closed trades only)
        if alltime_count > 0:
            response += f"📊 <b>Закрытых:</b> {alltime_count} сделок | <b>{alltime_r:+.1f}R</b>\n\n"

        response += f"📅 <b>Сегодня:</b>\n"
        response += f"├ Сгенерировано: {generated}\n"
        response += f"├ Ждут входа: {waiting_count}\n"
        response += f"├ В позиции: <b>{active_count}</b>\n"
        response += f"├ Завершено: {finished}\n"
        response += f"└ Не дошли до entry: {expired_before_entry}\n\n"

        # Active trades summary
        if active_count > 0:
            # Summary stats from sample
            total_mfe = sum((m.mfe_r or 0) for m, s in active_trades)
            total_mae = sum((m.mae_r or 0) for m, s in active_trades)
            longs = sum(1 for m, s in active_trades if s.bias == "long")
            shorts = len(active_trades) - longs

            response += f"📈 <b>Открытые позиции ({active_count}):</b>\n"
            response += f"├ Long/Short: {longs}/{shorts}\n"
            response += f"├ Σ MFE: {total_mfe:+.2f}R\n"
            response += f"└ Σ MAE: {total_mae:.2f}R\n\n"

            # List active trades (sample 8)
            for monitor, snapshot in active_trades:
                side_emoji = "🟢" if snapshot.bias == "long" else "🔴"
                state_emoji = "⏳" if monitor.state == ScenarioState.ENTERED.value else "✅1"
                symbol_short = snapshot.symbol.replace("USDT", "")
                mfe = monitor.mfe_r or 0

                response += f"{side_emoji} <b>{symbol_short}</b> {state_emoji} "
                response += f"MFE: {mfe:+.2f}R\n"

            if active_count > 25:
                response += f"<i>... и ещё {active_count - 25}</i>\n"
        else:
            response += "📭 <i>Нет активных сделок</i>\n"

        # Toggle button text
        toggle_text = "⏸️ Выключить" if enabled else "▶️ Включить"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=toggle_text, callback_data="admin_ft_toggle"
                    ),
                    InlineKeyboardButton(
                        text="📊 All-Time", callback_data="admin_ft_alltime"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="📋 Открытые", callback_data="admin_ft_open_0"
                    ),
                    InlineKeyboardButton(
                        text="📜 История", callback_data="admin_ft_history_0"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="📊 Daily", callback_data="admin_ft_daily"
                    ),
                    InlineKeyboardButton(
                        text="📈 7 Days", callback_data="admin_ft_7d"
                    ),
                    InlineKeyboardButton(
                        text="🏆 Archetypes", callback_data="admin_ft_archetypes"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔄 Обновить", callback_data="admin_forward_test"
                    ),
                    InlineKeyboardButton(
                        text="🗑 Очистить", callback_data="admin_ft_reset_confirm"
                    ),
                ],
                [
                    InlineKeyboardButton(text="◀️ Назад", callback_data="admin_refresh"),
                ],
            ]
        )

        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing forward test menu: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin_ft_toggle")
async def admin_ft_toggle(callback: CallbackQuery, session: AsyncSession):
    """Toggle forward test on/off"""
    try:
        from src.services.forward_test.scheduler import forward_test_scheduler

        current = forward_test_scheduler.is_enabled()
        forward_test_scheduler.set_enabled(not current)

        new_state = "включен" if not current else "выключен"
        await callback.answer(f"Forward Test {new_state}", show_alert=True)

        # Refresh menu by re-calling the handler
        callback.data = "admin_forward_test"
        await admin_forward_test_menu(callback, session)

    except Exception as e:
        logger.exception(f"Error toggling forward test: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin_ft_alltime")
async def admin_ft_alltime(callback: CallbackQuery, session: AsyncSession):
    """Show all-time forward test statistics"""
    try:
        from src.services.forward_test.models import ForwardTestOutcome, ForwardTestSnapshot
        from src.services.forward_test.enums import OutcomeResult
        from src.services.forward_test.epoch_manager import get_current_epoch

        current_epoch = await get_current_epoch()

        # All-time stats
        outcomes_q = select(ForwardTestOutcome).join(
            ForwardTestSnapshot,
            ForwardTestOutcome.snapshot_id == ForwardTestSnapshot.snapshot_id
        ).where(ForwardTestSnapshot.epoch == current_epoch)
        result = await session.execute(outcomes_q)
        outcomes = result.scalars().all()

        if not outcomes:
            response = "📊 <b>All-Time Stats</b>\n\n"
            response += "📭 <i>Нет данных</i>"
        else:
            wins = sum(1 for o in outcomes if o.result == OutcomeResult.WIN.value)
            losses = sum(1 for o in outcomes if o.result == OutcomeResult.LOSS.value)
            be = len(outcomes) - wins - losses
            total_r = sum(o.total_r or 0 for o in outcomes)
            avg_r = total_r / len(outcomes)
            winrate = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0

            # By terminal state (values are lowercase in enum)
            tp1_count = sum(1 for o in outcomes if o.terminal_state == "tp1")
            tp2_count = sum(1 for o in outcomes if o.terminal_state == "tp2")
            tp3_count = sum(1 for o in outcomes if o.terminal_state == "tp3")
            sl_count = sum(1 for o in outcomes if o.terminal_state == "sl")
            be_count = sum(1 for o in outcomes if o.terminal_state == "be")
            expired_count = sum(1 for o in outcomes if o.terminal_state == "expired")

            # Average MAE/MFE
            avg_mae = sum(o.mae_r or 0 for o in outcomes) / len(outcomes)
            avg_mfe = sum(o.mfe_r or 0 for o in outcomes) / len(outcomes)

            # First/last trade dates
            sorted_outcomes = sorted(outcomes, key=lambda x: x.created_at or datetime.min)
            first_date = sorted_outcomes[0].created_at.strftime("%d.%m.%Y") if sorted_outcomes else "N/A"
            last_date = sorted_outcomes[-1].created_at.strftime("%d.%m.%Y") if sorted_outcomes else "N/A"

            response = "📊 <b>All-Time Stats</b>\n\n"
            response += f"📅 Период: {first_date} — {last_date}\n\n"
            response += f"<b>📈 Performance:</b>\n"
            response += f"├ Всего сделок: <b>{len(outcomes)}</b>\n"
            response += f"├ Winrate: <b>{winrate:.1f}%</b>\n"
            response += f"├ Net R: <b>{total_r:+.2f}R</b>\n"
            response += f"└ Avg R: <b>{avg_r:+.3f}R</b>\n\n"

            response += f"<b>📊 Outcomes:</b>\n"
            response += f"├ Wins: {wins} ({wins/len(outcomes)*100:.0f}%)\n"
            response += f"├ Losses: {losses} ({losses/len(outcomes)*100:.0f}%)\n"
            response += f"└ BE/Other: {be} ({be/len(outcomes)*100:.0f}%)\n\n"

            response += f"<b>🎯 Terminal States:</b>\n"
            response += f"├ TP1: {tp1_count} | TP2: {tp2_count} | TP3: {tp3_count}\n"
            response += f"├ SL: {sl_count} | BE: {be_count}\n"
            response += f"└ Expired: {expired_count}\n\n"

            response += f"<b>📉 Risk Metrics:</b>\n"
            response += f"├ Avg MAE: {avg_mae:.2f}R\n"
            response += f"└ Avg MFE: {avg_mfe:+.2f}R\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_forward_test")]
            ]
        )

        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing alltime stats: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("admin_ft_open_"))
async def admin_ft_open_trades(callback: CallbackQuery, session: AsyncSession):
    """Show open trades grouped by symbol"""
    try:
        from src.services.forward_test.models import (
            ForwardTestSnapshot,
            ForwardTestMonitorState,
        )
        from src.services.forward_test.enums import ScenarioState
        from src.services.forward_test.epoch_manager import get_current_epoch
        from src.services.bybit_service import BybitService
        from collections import defaultdict

        current_epoch = await get_current_epoch()

        active_states = [
            ScenarioState.ENTERED.value,
            ScenarioState.TP1.value,
        ]

        # Get ALL active trades
        all_active_q = (
            select(ForwardTestMonitorState, ForwardTestSnapshot)
            .join(
                ForwardTestSnapshot,
                ForwardTestMonitorState.snapshot_id == ForwardTestSnapshot.snapshot_id
            )
            .where(
                and_(
                    ForwardTestSnapshot.epoch == current_epoch,
                    ForwardTestMonitorState.state.in_(active_states)
                )
            )
            .order_by(ForwardTestMonitorState.entered_at.desc())
        )
        all_result = await session.execute(all_active_q)
        all_trades = all_result.all()

        if not all_trades:
            response = "📋 <b>Открытые сделки</b>\n\n"
            response += "📭 <i>Нет открытых сделок</i>"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_forward_test")]
            ])
            await safe_edit_message(callback, response, keyboard)
            await callback.answer()
            return

        # Group by symbol
        by_symbol = defaultdict(list)
        for monitor, snapshot in all_trades:
            by_symbol[snapshot.symbol].append((monitor, snapshot))

        # Calculate summary stats
        total_trades = len(all_trades)
        longs = sum(1 for m, s in all_trades if s.bias == "long")
        shorts = total_trades - longs

        # Get current prices for unrealized R calculation
        bybit = BybitService()
        symbols = list(by_symbol.keys())
        current_prices = {}
        for symbol in symbols:
            try:
                price = await bybit.get_current_price(symbol)
                if price:
                    current_prices[symbol] = price
            except Exception:
                pass

        # Calculate unrealized R for each trade
        total_unrealized_r = 0.0
        in_profit_count = 0
        in_loss_count = 0
        symbol_stats = {}  # {symbol: {unrealized_r, count, longs, shorts}}

        for symbol, trades in by_symbol.items():
            sym_unrealized = 0.0
            sym_in_profit = 0
            sym_in_loss = 0
            sym_longs = 0
            sym_shorts = 0

            for monitor, snapshot in trades:
                if snapshot.bias == "long":
                    sym_longs += 1
                else:
                    sym_shorts += 1

                if symbol in current_prices and monitor.avg_entry_price and monitor.initial_risk_per_unit:
                    current_price = current_prices[symbol]
                    direction = 1 if snapshot.bias == "long" else -1
                    unrealized_r = (current_price - monitor.avg_entry_price) * direction / monitor.initial_risk_per_unit
                    unrealized_r += (monitor.realized_r_so_far or 0)
                    sym_unrealized += unrealized_r
                    total_unrealized_r += unrealized_r

                    if unrealized_r >= 0:
                        in_profit_count += 1
                        sym_in_profit += 1
                    else:
                        in_loss_count += 1
                        sym_in_loss += 1

            symbol_stats[symbol] = {
                "unrealized_r": sym_unrealized,
                "count": len(trades),
                "longs": sym_longs,
                "shorts": sym_shorts,
                "in_profit": sym_in_profit,
                "in_loss": sym_in_loss,
            }

        total_mfe = sum((m.mfe_r or 0) for m, s in all_trades)
        total_mae = sum((m.mae_r or 0) for m, s in all_trades)
        total_realized = sum((m.realized_r_so_far or 0) for m, s in all_trades)
        tp1_hit = sum(1 for m, s in all_trades if m.state == ScenarioState.TP1.value)

        # Build response
        status_emoji = "🟢" if total_unrealized_r > 0 else ("🔴" if total_unrealized_r < 0 else "⚪")

        response = "📋 <b>Открытые сделки</b>\n\n"
        response += f"<b>📊 Summary ({total_trades} сделок):</b>\n"
        response += f"├ Long/Short: {longs}/{shorts}\n"
        response += f"├ Сейчас +R/-R: <b>{in_profit_count}/{in_loss_count}</b>\n"
        response += f"├ {status_emoji} <b>Unrealized: {total_unrealized_r:+.2f}R</b>\n"
        if tp1_hit > 0:
            response += f"├ TP1 hit: {tp1_hit} (profit locked)\n"
        if total_realized != 0:
            response += f"├ Realized: {total_realized:+.2f}R\n"
        response += f"├ Best (MFE): {total_mfe:+.2f}R\n"
        response += f"└ Worst (MAE): {total_mae:.2f}R\n"
        response += "\n"

        # List symbols with stats
        response += f"<b>📊 По тикерам ({len(symbols)}):</b>\n"

        # Sort by unrealized R desc
        sorted_symbols = sorted(symbols, key=lambda s: symbol_stats[s]["unrealized_r"], reverse=True)

        for symbol in sorted_symbols:
            stats = symbol_stats[symbol]
            sym_short = symbol.replace("USDT", "")
            r_emoji = "🟢" if stats["unrealized_r"] >= 0 else "🔴"

            response += f"{r_emoji} <b>{sym_short}</b> ({stats['count']}) "
            response += f"<b>{stats['unrealized_r']:+.2f}R</b>\n"

        # Build keyboard with symbol buttons (3 per row)
        buttons = []
        row = []
        for symbol in sorted_symbols:
            sym_short = symbol.replace("USDT", "")[:5]
            stats = symbol_stats[symbol]
            btn_text = f"{sym_short} ({stats['count']})"
            row.append(InlineKeyboardButton(
                text=btn_text,
                callback_data=f"admin_ft_sym_{symbol}"
            ))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        # Refresh and back
        buttons.append([
            InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_ft_open_0"),
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_forward_test")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing open trades: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("admin_ft_sym_"))
async def admin_ft_symbol_trades(callback: CallbackQuery, session: AsyncSession):
    """Show all trades for a specific symbol"""
    try:
        from src.services.forward_test.models import (
            ForwardTestSnapshot,
            ForwardTestMonitorState,
        )
        from src.services.forward_test.enums import ScenarioState
        from src.services.bybit_service import BybitService
        from src.services.forward_test.epoch_manager import get_current_epoch

        symbol = callback.data.replace("admin_ft_sym_", "")
        current_epoch = await get_current_epoch()
        symbol_short = symbol.replace("USDT", "")

        active_states = [
            ScenarioState.ENTERED.value,
            ScenarioState.TP1.value,
        ]

        # Get all trades for this symbol (filter by current epoch)
        trades_q = (
            select(ForwardTestMonitorState, ForwardTestSnapshot)
            .join(
                ForwardTestSnapshot,
                ForwardTestMonitorState.snapshot_id == ForwardTestSnapshot.snapshot_id
            )
            .where(
                and_(
                    ForwardTestSnapshot.epoch == current_epoch,
                    ForwardTestMonitorState.state.in_(active_states),
                    ForwardTestSnapshot.symbol == symbol
                )
            )
            .order_by(ForwardTestMonitorState.entered_at.desc())
        )
        result = await session.execute(trades_q)
        trades = result.all()

        if not trades:
            await callback.answer(f"Нет сделок по {symbol_short}", show_alert=True)
            return

        # Get current price
        bybit = BybitService()
        current_price = None
        try:
            current_price = await bybit.get_current_price(symbol)
        except Exception:
            pass

        # Build response
        response = f"📋 <b>{symbol_short}</b> — {len(trades)} сделок\n"
        if current_price:
            response += f"📈 Цена: <b>{current_price:.4f}</b>\n"
        response += "\n"

        # Summary for this symbol
        total_unrealized = 0.0
        total_mfe = 0.0
        total_mae = 0.0
        longs = sum(1 for m, s in trades if s.bias == "long")
        shorts = len(trades) - longs

        for monitor, snapshot in trades:
            total_mfe += (monitor.mfe_r or 0)
            total_mae += (monitor.mae_r or 0)

            if current_price and monitor.avg_entry_price and monitor.initial_risk_per_unit:
                direction = 1 if snapshot.bias == "long" else -1
                unr = (current_price - monitor.avg_entry_price) * direction / monitor.initial_risk_per_unit
                unr += (monitor.realized_r_so_far or 0)
                total_unrealized += unr

        status_emoji = "🟢" if total_unrealized >= 0 else "🔴"
        response += f"<b>Summary:</b>\n"
        response += f"├ Long/Short: {longs}/{shorts}\n"
        response += f"├ {status_emoji} Unrealized: <b>{total_unrealized:+.2f}R</b>\n"
        response += f"├ MFE: {total_mfe:+.2f}R\n"
        response += f"└ MAE: {total_mae:.2f}R\n\n"

        # List each trade
        for i, (monitor, snapshot) in enumerate(trades, 1):
            side_emoji = "🟢" if snapshot.bias == "long" else "🔴"
            state_text = "TP1✅" if monitor.state == ScenarioState.TP1.value else ""

            # Calculate current R
            current_r = None
            if current_price and monitor.avg_entry_price and monitor.initial_risk_per_unit:
                direction = 1 if snapshot.bias == "long" else -1
                current_r = (current_price - monitor.avg_entry_price) * direction / monitor.initial_risk_per_unit
                current_r += (monitor.realized_r_so_far or 0)

            r_text = f"<b>{current_r:+.2f}R</b>" if current_r is not None else "—"
            r_emoji = "✅" if current_r and current_r >= 0 else ("❌" if current_r else "")

            response += f"{i}. {side_emoji} {r_emoji} {r_text} {state_text}\n"
            response += f"├ {snapshot.archetype[:30]}\n"

            if monitor.entered_at:
                duration = datetime.now() - monitor.entered_at.replace(tzinfo=None)
                hours = duration.total_seconds() / 3600
                entry_text = f"Entry: {monitor.avg_entry_price:.4f}" if monitor.avg_entry_price else ""
                response += f"├ {entry_text} | {hours:.1f}h\n"

            if monitor.mae_r is not None:
                response += f"└ MAE: {monitor.mae_r:.2f}R | MFE: {monitor.mfe_r or 0:+.2f}R\n"

            response += "\n"

        # Build keyboard with card buttons
        buttons = []
        row = []
        for i, (monitor, snapshot) in enumerate(trades, 1):
            row.append(InlineKeyboardButton(
                text=f"📄 #{i}",
                callback_data=f"admin_ft_card_{snapshot.snapshot_id}"
            ))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([
            InlineKeyboardButton(text="◀️ К тикерам", callback_data="admin_ft_open_0")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing symbol trades: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("admin_ft_card_"))
async def admin_ft_trade_card(callback: CallbackQuery, session: AsyncSession):
    """Show detailed trade card with entry/SL/TPs/leverage/PnL"""
    try:
        from src.services.forward_test.models import (
            ForwardTestSnapshot,
            ForwardTestMonitorState,
            ForwardTestEvent,
        )
        from src.services.forward_test.enums import ScenarioState

        snapshot_id = callback.data.replace("admin_ft_card_", "")

        # Get snapshot and monitor state
        q = (
            select(ForwardTestMonitorState, ForwardTestSnapshot)
            .join(
                ForwardTestSnapshot,
                ForwardTestMonitorState.snapshot_id == ForwardTestSnapshot.snapshot_id
            )
            .where(ForwardTestSnapshot.snapshot_id == snapshot_id)
        )
        result = await session.execute(q)
        row = result.first()

        if not row:
            await callback.answer("Сделка не найдена", show_alert=True)
            return

        monitor, snapshot = row
        side_emoji = "🟢 LONG" if snapshot.bias == "long" else "🔴 SHORT"
        symbol_short = snapshot.symbol.replace("USDT", "")

        # Use normalized_json for extra details, direct fields for key prices
        scenario = snapshot.normalized_json or {}
        leverage = scenario.get("leverage", "?")

        response = f"📄 <b>Trade Card: {symbol_short}</b>\n\n"
        response += f"{side_emoji}\n"
        response += f"├ Archetype: <b>{snapshot.archetype}</b>\n"
        response += f"├ Timeframe: {snapshot.timeframe}\n"
        response += f"└ Leverage: {leverage}x\n\n"

        # Entry - use direct fields
        response += f"<b>📥 Entry:</b>\n"
        response += f"├ Plan: {snapshot.entry_price_avg}\n"
        response += f"└ Actual: {monitor.avg_entry_price or 'N/A'}"
        if monitor.fill_pct:
            response += f" ({monitor.fill_pct:.0f}%)"
        response += "\n\n"

        # Stop Loss - use direct field
        response += f"<b>🛑 Stop Loss:</b>\n"
        response += f"├ Initial: {snapshot.stop_loss}\n"
        if monitor.current_sl and monitor.current_sl != snapshot.stop_loss:
            response += f"└ Current: {monitor.current_sl} (BE)\n\n"
        else:
            response += "\n"

        # Targets - use direct fields
        response += f"<b>🎯 Targets:</b>\n"
        tp1_hit = "✅" if monitor.state == ScenarioState.TP1.value else "⏳"
        response += f"├ TP1: {snapshot.tp1_price} {tp1_hit}\n"
        if snapshot.tp2_price:
            response += f"├ TP2: {snapshot.tp2_price} ⏳\n"
        if snapshot.tp3_price:
            response += f"├ TP3: {snapshot.tp3_price} ⏳\n"
        response += "\n"

        # Current State
        state_map = {
            ScenarioState.ENTERED.value: "⏳ В позиции",
            ScenarioState.TP1.value: "✅ TP1 достигнут",
        }
        state_text = state_map.get(monitor.state, monitor.state)
        response += f"<b>📊 Status:</b> {state_text}\n"

        if monitor.mae_r is not None:
            response += f"├ MAE: {monitor.mae_r:.2f}R (worst drawdown)\n"
        if monitor.mfe_r is not None:
            response += f"├ MFE: {monitor.mfe_r:+.2f}R (best unrealized)\n"
        if monitor.realized_r_so_far:
            response += f"├ Realized: {monitor.realized_r_so_far:+.2f}R\n"

        if monitor.entered_at:
            duration = datetime.now() - monitor.entered_at.replace(tzinfo=None)
            hours = duration.total_seconds() / 3600
            response += f"└ Duration: {hours:.1f}h\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ К списку", callback_data="admin_ft_open_0")],
                [InlineKeyboardButton(text="◀️ Главная", callback_data="admin_forward_test")],
            ]
        )

        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing trade card: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin_ft_daily")
async def admin_ft_daily_report(callback: CallbackQuery, session: AsyncSession):
    """Show daily forward test report"""
    try:
        from src.services.forward_test.telegram_reporter import TelegramReporter

        reporter = TelegramReporter()
        report_html = await reporter._build_daily_report(session, date.today())

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_forward_test")]
            ]
        )

        await safe_edit_message(callback, report_html, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing daily report: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin_ft_7d")
async def admin_ft_7d_report(callback: CallbackQuery, session: AsyncSession):
    """Show 7-day forward test summary"""
    try:
        from src.services.forward_test.models import ForwardTestOutcome, ForwardTestSnapshot
        from src.services.forward_test.enums import OutcomeResult
        from src.services.forward_test.epoch_manager import get_current_epoch

        current_epoch = await get_current_epoch()
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=7)

        # Get outcomes (filter by current epoch)
        outcomes_q = select(ForwardTestOutcome).join(
            ForwardTestSnapshot,
            ForwardTestOutcome.snapshot_id == ForwardTestSnapshot.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.epoch == current_epoch,
                ForwardTestSnapshot.generated_at >= start_dt
            )
        )
        result = await session.execute(outcomes_q)
        outcomes = result.scalars().all()

        if not outcomes:
            response = "🧪 <b>Forward Test — 7 дней</b>\n\n"
            response += "📭 <i>Нет данных за период</i>"
        else:
            wins = sum(1 for o in outcomes if o.result == OutcomeResult.WIN.value)
            losses = sum(1 for o in outcomes if o.result == OutcomeResult.LOSS.value)
            total_r = sum(o.total_r for o in outcomes)
            avg_r = total_r / len(outcomes)
            winrate = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0

            response = "🧪 <b>Forward Test — 7 дней</b>\n\n"
            response += f"📊 <b>Всего сделок:</b> {len(outcomes)}\n"
            response += f"├ Wins: {wins}\n"
            response += f"├ Losses: {losses}\n"
            response += f"└ Breakeven: {len(outcomes) - wins - losses}\n\n"
            response += f"📈 <b>Performance:</b>\n"
            response += f"├ Winrate: <b>{winrate:.1f}%</b>\n"
            response += f"├ Net R: <b>{total_r:+.2f}R</b>\n"
            response += f"└ Avg R: <b>{avg_r:+.2f}R</b>\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_forward_test")]
            ]
        )

        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing 7d report: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin_ft_archetypes")
async def admin_ft_archetypes(callback: CallbackQuery, session: AsyncSession):
    """Show best and worst archetypes"""
    try:
        from src.services.forward_test.models import ForwardTestOutcome, ForwardTestSnapshot
        from src.services.forward_test.epoch_manager import get_current_epoch

        current_epoch = await get_current_epoch()
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=30)

        q = select(
            ForwardTestSnapshot.archetype,
            func.count().label('count'),
            func.avg(ForwardTestOutcome.total_r).label('avg_r'),
            func.sum(ForwardTestOutcome.total_r).label('total_r')
        ).join(
            ForwardTestOutcome,
            ForwardTestSnapshot.snapshot_id == ForwardTestOutcome.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.epoch == current_epoch,
                ForwardTestSnapshot.generated_at >= start_dt
            )
        ).group_by(ForwardTestSnapshot.archetype).having(func.count() >= 3)

        result = await session.execute(q)
        rows = result.all()

        if not rows:
            response = "🧪 <b>Archetypes — 30 дней</b>\n\n"
            response += "📭 <i>Недостаточно данных</i>"
        else:
            # Sort by avg_r
            sorted_rows = sorted(rows, key=lambda x: x[2] or 0, reverse=True)

            response = "🏆 <b>Best Archetypes (30d)</b>\n\n"
            for row in sorted_rows[:5]:
                arch, count, avg_r, total_r = row
                emoji = "✅" if (avg_r or 0) > 0 else "❌"
                response += f"{emoji} <b>{arch[:20]}</b>\n"
                response += f"   n={count} | avg: {avg_r:+.2f}R | total: {total_r:+.2f}R\n"

            response += "\n💀 <b>Worst Archetypes (30d)</b>\n\n"
            for row in sorted_rows[-5:]:
                arch, count, avg_r, total_r = row
                if (avg_r or 0) >= 0:
                    continue
                emoji = "❌"
                response += f"{emoji} <b>{arch[:20]}</b>\n"
                response += f"   n={count} | avg: {avg_r:+.2f}R | total: {total_r:+.2f}R\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_forward_test")]
            ]
        )

        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing archetypes: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("admin_ft_history_"))
async def admin_ft_history(callback: CallbackQuery, session: AsyncSession):
    """Show finished trades history with pagination"""
    try:
        from src.services.forward_test.models import ForwardTestOutcome, ForwardTestSnapshot
        from src.services.forward_test.epoch_manager import get_current_epoch

        current_epoch = await get_current_epoch()
        page = int(callback.data.split("_")[-1])
        per_page = 10
        offset = page * per_page

        q = (
            select(ForwardTestOutcome, ForwardTestSnapshot)
            .join(
                ForwardTestSnapshot,
                ForwardTestOutcome.snapshot_id == ForwardTestSnapshot.snapshot_id
            )
            .where(ForwardTestSnapshot.epoch == current_epoch)
            .order_by(ForwardTestOutcome.created_at.desc())
            .offset(offset)
            .limit(per_page + 1)
        )
        result = await session.execute(q)
        rows = result.all()

        has_more = len(rows) > per_page
        rows = rows[:per_page]

        response = f"📜 <b>History</b> (стр. {page + 1})\n\n"

        for outcome, snapshot in rows:
            side_emoji = "🟢" if snapshot.bias == "long" else "🔴"
            result_emoji = "✅" if outcome.total_r > 0 else "❌" if outcome.total_r < 0 else "➖"
            symbol_short = snapshot.symbol.replace("USDT", "")

            response += f"{side_emoji}{result_emoji} <b>{symbol_short}</b> "
            response += f"<b>{outcome.total_r:+.2f}R</b>\n"
            response += f"   {snapshot.archetype[:18]}\n"
            response += f"   {outcome.terminal_state} | {outcome.created_at.strftime('%m/%d %H:%M')}\n\n"

        buttons = []
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                text="◀️ Prev", callback_data=f"admin_ft_history_{page - 1}"
            ))
        if has_more:
            nav_row.append(InlineKeyboardButton(
                text="Next ▶️", callback_data=f"admin_ft_history_{page + 1}"
            ))
        if nav_row:
            buttons.append(nav_row)

        buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_forward_test")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing history: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# ============================================================================
# Reset / Epoch handlers (очистка данных)
# ============================================================================


@router.callback_query(F.data == "admin_ft_reset_confirm")
async def admin_ft_reset_confirm(callback: CallbackQuery, session: AsyncSession):
    """Show confirmation for Forward Test data reset"""
    try:
        from src.services.forward_test.models import ForwardTestSnapshot
        from src.services.forward_test.epoch_manager import get_current_epoch

        current_epoch = await get_current_epoch()

        # Count current epoch records
        count_q = select(func.count()).select_from(ForwardTestSnapshot).where(
            ForwardTestSnapshot.epoch == current_epoch
        )
        count = (await session.execute(count_q)).scalar() or 0

        response = (
            "⚠️ <b>Очистить Forward Test данные?</b>\n\n"
            f"Текущая эпоха: <b>{current_epoch}</b>\n"
            f"Будет скрыто <b>{count}</b> сценариев.\n"
            f"Новая эпоха: <b>{current_epoch + 1}</b>\n\n"
            "Данные не удаляются, начинается новая эпоха."
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, очистить", callback_data="admin_ft_reset_execute"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_forward_test"),
            ],
        ])

        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing FT reset confirm: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin_ft_reset_execute")
async def admin_ft_reset_execute(callback: CallbackQuery, session: AsyncSession):
    """Execute Forward Test data reset (increment epoch)"""
    try:
        from src.services.forward_test.epoch_manager import get_current_epoch, increment_epoch

        old_epoch = await get_current_epoch()
        new_epoch = await increment_epoch()

        await callback.answer(f"✅ Эпоха {old_epoch} → {new_epoch}", show_alert=True)

        # Return to FT menu
        callback.data = "admin_forward_test"
        await admin_forward_test_menu(callback, session)

    except Exception as e:
        logger.exception(f"Error executing FT reset: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin_portfolio_reset_confirm")
async def admin_portfolio_reset_confirm(callback: CallbackQuery, session: AsyncSession):
    """Show confirmation for Portfolio data reset"""
    try:
        from src.services.forward_test.models import (
            PortfolioCandidate,
            PortfolioPosition,
            PortfolioEquitySnapshot,
        )

        # Count records
        candidates_q = select(func.count()).select_from(PortfolioCandidate)
        positions_q = select(func.count()).select_from(PortfolioPosition)
        equity_q = select(func.count()).select_from(PortfolioEquitySnapshot)

        candidates = (await session.execute(candidates_q)).scalar() or 0
        positions = (await session.execute(positions_q)).scalar() or 0
        equity = (await session.execute(equity_q)).scalar() or 0

        response = (
            "⚠️ <b>Очистить Portfolio данные?</b>\n\n"
            f"• Candidates: <b>{candidates}</b>\n"
            f"• Positions: <b>{positions}</b>\n"
            f"• Equity snapshots: <b>{equity}</b>\n\n"
            "⚠️ <b>Данные будут УДАЛЕНЫ!</b>\n"
            "Это действие нельзя отменить."
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, очистить", callback_data="admin_portfolio_reset_execute"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_portfolio"),
            ],
        ])

        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing portfolio reset confirm: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin_portfolio_reset_execute")
async def admin_portfolio_reset_execute(callback: CallbackQuery, session: AsyncSession):
    """Execute Portfolio data reset (delete all)"""
    try:
        from src.services.forward_test.models import (
            PortfolioCandidate,
            PortfolioPosition,
            PortfolioEquitySnapshot,
        )
        from sqlalchemy import delete

        # Delete in correct order (FK constraints)
        await session.execute(delete(PortfolioEquitySnapshot))
        await session.execute(delete(PortfolioPosition))
        await session.execute(delete(PortfolioCandidate))
        await session.commit()

        await callback.answer("✅ Portfolio данные очищены", show_alert=True)

        # Return to portfolio menu
        callback.data = "admin_portfolio"
        await admin_portfolio_menu(callback, session)

    except Exception as e:
        logger.exception(f"Error executing portfolio reset: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# ============================================================================
# Portfolio Mode Handlers
# ============================================================================


@router.callback_query(F.data == "admin_portfolio")
async def admin_portfolio_menu(callback: CallbackQuery, session: AsyncSession):
    """Show Portfolio Mode main menu with equity stats"""
    try:
        from src.services.forward_test.config import get_config
        from src.services.forward_test.models import (
            PortfolioCandidate,
            PortfolioPosition,
            PortfolioEquitySnapshot,
            ForwardTestMonitorState,
            ForwardTestSnapshot,
        )
        from src.services.forward_test.epoch_manager import get_current_epoch

        current_epoch = await get_current_epoch()
        config = get_config()
        portfolio_cfg = config.portfolio

        if not portfolio_cfg.enabled:
            response = "📊 <b>Portfolio Mode</b>\n\n"
            response += "⚠️ <i>Portfolio Mode отключен в конфиге</i>"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_refresh")]
                ]
            )
            await safe_edit_message(callback, response, keyboard)
            await callback.answer()
            return

        # Get equity stats
        last_equity_q = (
            select(PortfolioEquitySnapshot)
            .order_by(PortfolioEquitySnapshot.ts.desc())
            .limit(1)
        )
        last_equity_result = await session.execute(last_equity_q)
        last_equity = last_equity_result.scalar_one_or_none()

        # Count active candidates (filter by current epoch)
        active_candidates_q = select(func.count()).select_from(PortfolioCandidate).join(
            ForwardTestSnapshot,
            PortfolioCandidate.snapshot_id == ForwardTestSnapshot.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.epoch == current_epoch,
                PortfolioCandidate.status.in_(["active", "active_waiting_slot"])
            )
        )
        active_candidates = (await session.execute(active_candidates_q)).scalar() or 0

        # Get open positions with monitors for unrealized stats (filter by current epoch)
        open_positions_q = select(PortfolioPosition).join(
            ForwardTestSnapshot,
            PortfolioPosition.snapshot_id == ForwardTestSnapshot.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.epoch == current_epoch,
                PortfolioPosition.status == "open"
            )
        )
        open_result = await session.execute(open_positions_q)
        open_positions_list = open_result.scalars().all()
        open_positions = len(open_positions_list)

        # Calculate unrealized stats
        total_risk = 0.0
        total_mfe = 0.0
        total_mae = 0.0
        total_unrealized_r = 0.0
        longs = 0
        shorts = 0

        for p in open_positions_list:
            total_risk += p.risk_r_filled
            if p.side == "long":
                longs += 1
            else:
                shorts += 1

            monitor_q = select(ForwardTestMonitorState).where(
                ForwardTestMonitorState.snapshot_id == p.snapshot_id
            )
            monitor_result = await session.execute(monitor_q)
            monitor = monitor_result.scalar_one_or_none()
            if monitor:
                total_mfe += (monitor.mfe_r or 0)
                total_mae += (monitor.mae_r or 0)
                total_unrealized_r += (monitor.realized_r_so_far or 0)

        # Build response
        response = "📊 <b>Portfolio Mode</b>\n\n"

        # Current state with unrealized
        response += f"📈 <b>Open Positions</b> ({open_positions}/{portfolio_cfg.max_open_positions})\n"
        if open_positions > 0:
            response += f"├ Long/Short: {longs}/{shorts}\n"
            response += f"├ Risk: {total_risk:.2f}R / {portfolio_cfg.max_total_risk_r:.1f}R\n"
            response += f"├ Σ MFE: <b>{total_mfe:+.2f}R</b>\n"
            response += f"├ Σ MAE: {total_mae:.2f}R\n"
            response += f"└ <b>Unrealized: {total_unrealized_r:+.2f}R</b>\n\n"
        else:
            response += f"└ <i>No open positions</i>\n\n"

        response += f"📋 <b>Candidates:</b> {active_candidates}/{portfolio_cfg.max_active_candidates}\n\n"

        if last_equity:
            equity_change = last_equity.equity_pct_from_initial
            equity_emoji = "🟢" if equity_change >= 0 else "🔴"

            response += f"💰 <b>Equity:</b>\n"
            response += f"├ Current: ${last_equity.equity_usd:,.2f}\n"
            response += f"├ P&L: {equity_emoji} {equity_change:+.2f}%\n"
            response += f"├ Peak: ${last_equity.equity_peak_usd:,.2f}\n"
            response += f"├ DD: -{last_equity.current_drawdown_pct:.2f}%\n"
            response += f"└ Max DD: -{last_equity.max_drawdown_pct:.2f}%\n\n"

            # Cumulative stats
            if last_equity.total_trades > 0:
                win_rate = (last_equity.win_count / last_equity.total_trades) * 100
                avg_r = last_equity.total_r_realized / last_equity.total_trades
                response += f"📊 <b>Performance:</b>\n"
                response += f"├ Trades: {last_equity.total_trades}\n"
                response += f"├ Win/Loss: {last_equity.win_count}/{last_equity.loss_count} ({win_rate:.0f}%)\n"
                response += f"├ Total R: <b>{last_equity.total_r_realized:+.2f}R</b>\n"
                response += f"└ Avg R/trade: {avg_r:+.2f}R\n"
        else:
            response += f"💰 <b>Equity:</b>\n"
            response += f"└ Initial: ${portfolio_cfg.initial_capital:,.2f}\n"
            response += "\n📭 <i>Нет данных equity</i>"

        # Config at bottom (compact)
        response += f"\n\n<i>Config: {portfolio_cfg.max_open_positions} pos, {portfolio_cfg.max_total_risk_r}R risk, 1R={portfolio_cfg.r_to_pct*100:.0f}%</i>"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📋 Candidates", callback_data="admin_portfolio_candidates_0"
                    ),
                    InlineKeyboardButton(
                        text="📈 Positions", callback_data="admin_portfolio_positions_0"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="📜 History", callback_data="admin_portfolio_history_0"
                    ),
                    InlineKeyboardButton(
                        text="📊 Equity", callback_data="admin_portfolio_equity"
                    ),
                ],
                [
                    InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_portfolio"),
                    InlineKeyboardButton(text="🗑 Очистить", callback_data="admin_portfolio_reset_confirm"),
                ],
                [
                    InlineKeyboardButton(text="◀️ Назад", callback_data="admin_refresh"),
                ],
            ]
        )

        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing portfolio menu: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("admin_portfolio_candidates_"))
async def admin_portfolio_candidates(callback: CallbackQuery, session: AsyncSession):
    """Show active portfolio candidates with pagination"""
    try:
        from src.services.forward_test.models import PortfolioCandidate, ForwardTestSnapshot
        from src.services.forward_test.epoch_manager import get_current_epoch

        current_epoch = await get_current_epoch()
        page = int(callback.data.split("_")[-1])
        per_page = 10
        offset = page * per_page

        # Get active candidates (filter by current epoch)
        candidates_q = (
            select(PortfolioCandidate)
            .join(ForwardTestSnapshot, PortfolioCandidate.snapshot_id == ForwardTestSnapshot.snapshot_id)
            .where(
                and_(
                    ForwardTestSnapshot.epoch == current_epoch,
                    PortfolioCandidate.status.in_(["active", "active_waiting_slot"])
                )
            )
            .order_by(PortfolioCandidate.priority_score.desc())
            .offset(offset)
            .limit(per_page + 1)
        )
        result = await session.execute(candidates_q)
        candidates = result.scalars().all()

        has_more = len(candidates) > per_page
        candidates = candidates[:per_page]

        # Total count (filter by current epoch)
        total_q = select(func.count()).select_from(PortfolioCandidate).join(
            ForwardTestSnapshot, PortfolioCandidate.snapshot_id == ForwardTestSnapshot.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.epoch == current_epoch,
                PortfolioCandidate.status.in_(["active", "active_waiting_slot"])
            )
        )
        total = (await session.execute(total_q)).scalar() or 0

        response = f"📋 <b>Active Candidates</b> ({total})\n"
        response += f"<i>Page {page + 1}</i>\n\n"

        if not candidates:
            response += "📭 <i>Нет активных кандидатов</i>"
        else:
            for c in candidates:
                side_emoji = "🟢" if c.side == "long" else "🔴"
                status_emoji = "⏳" if c.status == "active" else "🔄"  # active_waiting_slot
                symbol_short = c.symbol.replace("USDT", "")

                response += f"{side_emoji}{status_emoji} <b>{symbol_short}</b> "
                response += f"Score: {c.priority_score:.2f}\n"
                response += f"   EV: {c.ev_component:.2f} | Conf: {c.conf_component:.2f}\n"

                if c.had_fill_attempt:
                    response += f"   ⚠️ Fill attempt: {c.last_fill_reject_reason or 'pending'}\n"

                if c.expires_at:
                    from datetime import datetime, UTC
                    remaining = c.expires_at - datetime.now(UTC)
                    hours_left = remaining.total_seconds() / 3600
                    if hours_left > 0:
                        response += f"   ⏱️ TTL: {hours_left:.1f}h\n"
                    else:
                        response += f"   ⏱️ <i>Expired</i>\n"
                response += "\n"

        # Navigation buttons
        buttons = []
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                text="◀️ Prev", callback_data=f"admin_portfolio_candidates_{page - 1}"
            ))
        if has_more:
            nav_row.append(InlineKeyboardButton(
                text="Next ▶️", callback_data=f"admin_portfolio_candidates_{page + 1}"
            ))
        if nav_row:
            buttons.append(nav_row)

        buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_portfolio")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing candidates: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("admin_portfolio_positions_"))
async def admin_portfolio_positions(callback: CallbackQuery, session: AsyncSession):
    """Show open portfolio positions with pagination"""
    try:
        from src.services.forward_test.models import PortfolioPosition, ForwardTestMonitorState, ForwardTestSnapshot
        from src.services.forward_test.config import get_config
        from src.services.forward_test.epoch_manager import get_current_epoch

        current_epoch = await get_current_epoch()
        config = get_config()
        page = int(callback.data.split("_")[-1])
        per_page = 8
        offset = page * per_page

        # Get ALL open positions for summary (filter by current epoch)
        all_positions_q = (
            select(PortfolioPosition)
            .join(ForwardTestSnapshot, PortfolioPosition.snapshot_id == ForwardTestSnapshot.snapshot_id)
            .where(
                and_(
                    ForwardTestSnapshot.epoch == current_epoch,
                    PortfolioPosition.status == "open"
                )
            )
        )
        all_result = await session.execute(all_positions_q)
        all_positions = all_result.scalars().all()

        total = len(all_positions)
        total_risk = sum(p.risk_r_filled for p in all_positions)

        # Get monitors for all positions to calculate unrealized stats
        total_mfe = 0.0
        total_mae = 0.0
        total_unrealized_r = 0.0
        longs = 0
        shorts = 0

        position_monitors = {}
        for p in all_positions:
            monitor_q = select(ForwardTestMonitorState).where(
                ForwardTestMonitorState.snapshot_id == p.snapshot_id
            )
            monitor_result = await session.execute(monitor_q)
            monitor = monitor_result.scalar_one_or_none()
            position_monitors[p.snapshot_id] = monitor

            if monitor:
                total_mfe += (monitor.mfe_r or 0)
                total_mae += (monitor.mae_r or 0)
                total_unrealized_r += (monitor.realized_r_so_far or 0)

            if p.side == "long":
                longs += 1
            else:
                shorts += 1

        # Paginate
        positions = all_positions[offset:offset + per_page]
        has_more = len(all_positions) > offset + per_page

        response = f"📈 <b>Open Positions</b> ({total}/{config.portfolio.max_open_positions})\n\n"

        # Summary stats
        if total > 0:
            response += f"<b>Summary:</b>\n"
            response += f"├ Long/Short: {longs}/{shorts}\n"
            response += f"├ Risk: {total_risk:.2f}R / {config.portfolio.max_total_risk_r:.1f}R\n"
            response += f"├ Σ MFE: <b>{total_mfe:+.2f}R</b>\n"
            response += f"├ Σ MAE: {total_mae:.2f}R\n"
            response += f"└ Unrealized: <b>{total_unrealized_r:+.2f}R</b>\n\n"

        response += f"<i>Page {page + 1}</i>\n\n"

        if not positions:
            response += "📭 <i>Нет открытых позиций</i>"
        else:
            for p in positions:
                side_emoji = "🟢" if p.side == "long" else "🔴"
                symbol_short = p.symbol.replace("USDT", "")
                monitor = position_monitors.get(p.snapshot_id)

                response += f"{side_emoji} <b>{symbol_short}</b>"

                if monitor:
                    state_emoji = "⏳"
                    if monitor.state == "TP1":
                        state_emoji = "✅1"
                    elif monitor.state == "TP2":
                        state_emoji = "✅2"
                    response += f" {state_emoji}\n"

                    mfe = monitor.mfe_r or 0
                    mae = monitor.mae_r or 0
                    unrealized = monitor.realized_r_so_far or 0

                    response += f"   Entry: ${p.avg_fill_price:.4f} | Risk: {p.risk_r_filled:.2f}R\n"
                    response += f"   MFE: {mfe:+.2f}R | MAE: {mae:.2f}R\n"
                    response += f"   <b>Unrealized: {unrealized:+.2f}R</b>\n"
                else:
                    response += "\n"
                    response += f"   Entry: ${p.avg_fill_price:.4f} | Risk: {p.risk_r_filled:.2f}R\n"

                filled_str = p.filled_at.strftime("%m/%d %H:%M") if p.filled_at else "?"
                response += f"   Filled: {filled_str}\n\n"

        # Navigation buttons
        buttons = []
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                text="◀️ Prev", callback_data=f"admin_portfolio_positions_{page - 1}"
            ))
        if has_more:
            nav_row.append(InlineKeyboardButton(
                text="Next ▶️", callback_data=f"admin_portfolio_positions_{page + 1}"
            ))
        if nav_row:
            buttons.append(nav_row)

        buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_portfolio")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing positions: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("admin_portfolio_history_"))
async def admin_portfolio_history(callback: CallbackQuery, session: AsyncSession):
    """Show closed portfolio positions history"""
    try:
        from src.services.forward_test.models import PortfolioPosition, ForwardTestSnapshot
        from src.services.forward_test.epoch_manager import get_current_epoch

        current_epoch = await get_current_epoch()
        page = int(callback.data.split("_")[-1])
        per_page = 10
        offset = page * per_page

        # Get closed positions (filter by current epoch)
        positions_q = (
            select(PortfolioPosition)
            .join(ForwardTestSnapshot, PortfolioPosition.snapshot_id == ForwardTestSnapshot.snapshot_id)
            .where(
                and_(
                    ForwardTestSnapshot.epoch == current_epoch,
                    PortfolioPosition.status == "closed"
                )
            )
            .order_by(PortfolioPosition.closed_at.desc())
            .offset(offset)
            .limit(per_page + 1)
        )
        result = await session.execute(positions_q)
        positions = result.scalars().all()

        has_more = len(positions) > per_page
        positions = positions[:per_page]

        # Total count (filter by current epoch)
        total_q = select(func.count()).select_from(PortfolioPosition).join(
            ForwardTestSnapshot, PortfolioPosition.snapshot_id == ForwardTestSnapshot.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.epoch == current_epoch,
                PortfolioPosition.status == "closed"
            )
        )
        total = (await session.execute(total_q)).scalar() or 0

        response = f"📜 <b>Closed Positions</b> ({total})\n"
        response += f"<i>Page {page + 1}</i>\n\n"

        if not positions:
            response += "📭 <i>Нет закрытых позиций</i>"
        else:
            for p in positions:
                side_emoji = "🟢" if p.side == "long" else "🔴"
                r_mult = p.r_mult_realized or 0
                result_emoji = "✅" if r_mult > 0 else "❌" if r_mult < 0 else "⚪"
                symbol_short = p.symbol.replace("USDT", "")

                response += f"{side_emoji}{result_emoji} <b>{symbol_short}</b> "
                response += f"<b>{r_mult:+.2f}R</b>\n"

                if p.pnl_usd_realized is not None:
                    response += f"   P&L: ${p.pnl_usd_realized:+.2f} ({(p.pnl_pct_realized or 0)*100:+.2f}%)\n"

                closed_str = p.closed_at.strftime("%m/%d %H:%M") if p.closed_at else "?"
                response += f"   Closed: {closed_str}\n\n"

        # Navigation buttons
        buttons = []
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                text="◀️ Prev", callback_data=f"admin_portfolio_history_{page - 1}"
            ))
        if has_more:
            nav_row.append(InlineKeyboardButton(
                text="Next ▶️", callback_data=f"admin_portfolio_history_{page + 1}"
            ))
        if nav_row:
            buttons.append(nav_row)

        buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_portfolio")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing history: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin_portfolio_equity")
async def admin_portfolio_equity(callback: CallbackQuery, session: AsyncSession):
    """Show detailed equity chart data"""
    try:
        from src.services.forward_test.models import PortfolioEquitySnapshot
        from src.services.forward_test.config import get_config
        from datetime import datetime, UTC, timedelta

        config = get_config()

        # Get last 20 equity snapshots
        snapshots_q = (
            select(PortfolioEquitySnapshot)
            .order_by(PortfolioEquitySnapshot.ts.desc())
            .limit(20)
        )
        result = await session.execute(snapshots_q)
        snapshots = list(reversed(result.scalars().all()))

        response = "📊 <b>Equity History</b>\n\n"

        if not snapshots:
            response += f"💰 Initial: ${config.portfolio.initial_capital:,.2f}\n"
            response += "📭 <i>Нет данных</i>"
        else:
            latest = snapshots[-1]

            # Summary
            response += f"💰 <b>Current:</b> ${latest.equity_usd:,.2f}\n"
            response += f"📈 <b>Peak:</b> ${latest.equity_peak_usd:,.2f}\n"
            response += f"📉 <b>Max DD:</b> -{latest.max_drawdown_pct:.2f}%\n\n"

            # Timeline
            response += "<b>Timeline:</b>\n"
            for snap in snapshots[-10:]:
                ts_str = snap.ts.strftime("%m/%d %H:%M")
                pnl = snap.equity_pct_from_initial
                emoji = "🟢" if pnl >= 0 else "🔴"
                dd_str = f"-{snap.current_drawdown_pct:.1f}%" if snap.current_drawdown_pct > 0 else ""

                response += f"{emoji} {ts_str}: ${snap.equity_usd:,.0f} "
                response += f"({pnl:+.1f}%) {dd_str}\n"
                response += f"   ├ {snap.trigger}\n"
                response += f"   └ Pos: {snap.open_positions_count} | Risk: {snap.total_risk_r:.2f}R\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_portfolio")]
            ]
        )

        await safe_edit_message(callback, response, keyboard)
        await callback.answer()

    except Exception as e:
        logger.exception(f"Error showing equity: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
