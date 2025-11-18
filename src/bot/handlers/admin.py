# coding: utf-8
"""
Admin panel handlers - statistics, user management, cost monitoring
"""
import logging
from datetime import datetime, timedelta, date, UTC
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command, CommandObject
from aiogram.utils.chat_action import ChatActionSender
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select, func
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
    get_user_payments,
)
from src.database.models import User, Subscription, Payment, SubscriptionTier, PaymentStatus, Referral, ReferralBalance


logger = logging.getLogger(__name__)
router = Router(name="admin")


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

        # Get user by internal ID
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Get subscription separately to avoid MissingGreenlet error
        stmt_sub = select(Subscription).where(Subscription.user_id == user.id)
        result_sub = await session.execute(stmt_sub)
        subscription = result_sub.scalar_one_or_none()

        # Get referral balance separately to avoid MissingGreenlet error
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
        response += f"├ Telegram ID: <code>{user.telegram_id}</code>\n"
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

            # Recent payments
            user_payments = await get_user_payments(session, user.id, limit=3)
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

        # Build action buttons
        buttons = []

        # Subscription management buttons (if user has subscription)
        if subscription:
            sub_buttons = []

            # Extend subscription button
            sub_buttons.append([
                InlineKeyboardButton(
                    text="➕ Продлить на 1 мес",
                    callback_data=f"admin_sub_extend_{user.id}_1"
                ),
                InlineKeyboardButton(
                    text="3 мес",
                    callback_data=f"admin_sub_extend_{user.id}_3"
                ),
            ])

            # Change tier buttons (if not FREE)
            if subscription.tier != SubscriptionTier.FREE:
                tier_buttons = []

                # Upgrade options
                if subscription.tier == SubscriptionTier.BASIC:
                    tier_buttons.append(
                        InlineKeyboardButton(
                            text="⬆️ → PREMIUM",
                            callback_data=f"admin_sub_upgrade_{user.id}_premium"
                        )
                    )
                    tier_buttons.append(
                        InlineKeyboardButton(
                            text="⬆️ → VIP",
                            callback_data=f"admin_sub_upgrade_{user.id}_vip"
                        )
                    )
                elif subscription.tier == SubscriptionTier.PREMIUM:
                    tier_buttons.append(
                        InlineKeyboardButton(
                            text="⬆️ → VIP",
                            callback_data=f"admin_sub_upgrade_{user.id}_vip"
                        )
                    )
                    tier_buttons.append(
                        InlineKeyboardButton(
                            text="⬇️ → BASIC",
                            callback_data=f"admin_sub_downgrade_{user.id}_basic"
                        )
                    )
                elif subscription.tier == SubscriptionTier.VIP:
                    tier_buttons.append(
                        InlineKeyboardButton(
                            text="⬇️ → PREMIUM",
                            callback_data=f"admin_sub_downgrade_{user.id}_premium"
                        )
                    )
                    tier_buttons.append(
                        InlineKeyboardButton(
                            text="⬇️ → BASIC",
                            callback_data=f"admin_sub_downgrade_{user.id}_basic"
                        )
                    )

                if tier_buttons:
                    sub_buttons.append(tier_buttons)

                # Cancel subscription button
                sub_buttons.append([
                    InlineKeyboardButton(
                        text="❌ Отменить подписку",
                        callback_data=f"admin_sub_cancel_{user.id}"
                    )
                ])
            else:
                # If FREE, offer upgrade
                sub_buttons.append([
                    InlineKeyboardButton(
                        text="⬆️ Активировать BASIC",
                        callback_data=f"admin_sub_activate_{user.id}_basic_1"
                    ),
                    InlineKeyboardButton(
                        text="PREMIUM",
                        callback_data=f"admin_sub_activate_{user.id}_premium_1"
                    ),
                ])

            buttons.extend(sub_buttons)

            # Separator
            buttons.append([
                InlineKeyboardButton(text="─────────────", callback_data="noop")
            ])

        # Request limit management buttons
        buttons.extend([
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

        # Refresh user view - update callback data and reuse the callback
        original_data = callback.data
        callback.data = f"admin_user_view_{user_id}"
        await admin_user_view_callback(callback, session, bot)
        callback.data = original_data  # Restore original data

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
                    response += f"├ {user_data['username']} (ID: {user_data['telegram_id']})\n"
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
                name = user.first_name or user.username or f"ID {user.telegram_id}"

                response += f"{status} <b>{i}.</b> {emoji} {sub.tier.upper()}\n"
                response += f"   👤 {name}\n"

                if sub.expires_at:
                    days_left = (sub.expires_at - datetime.now(UTC)).days
                    response += f"   📅 Истекает: {sub.expires_at.strftime('%d.%m.%Y')}"
                    if days_left >= 0:
                        response += f" (через {days_left} дн.)\n"
                    else:
                        response += f" (истекла {abs(days_left)} дн. назад)\n"

                response += f"   🆔 User ID: <code>{user.telegram_id}</code>\n\n"

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

                name = user.first_name or user.username or f"ID {user.telegram_id}"

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
        # Get user
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Get subscription separately to avoid MissingGreenlet
        stmt_sub = select(Subscription).where(Subscription.user_id == user.id)
        result_sub = await session.execute(stmt_sub)
        subscription = result_sub.scalar_one_or_none()

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
        # Get user
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Get subscription separately to avoid MissingGreenlet
        stmt_sub = select(Subscription).where(Subscription.user_id == user.id)
        result_sub = await session.execute(stmt_sub)
        subscription = result_sub.scalar_one_or_none()

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
        # Get user
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Get subscription separately to avoid MissingGreenlet
        stmt_sub = select(Subscription).where(Subscription.user_id == user.id)
        result_sub = await session.execute(stmt_sub)
        subscription = result_sub.scalar_one_or_none()

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
        # Get user
        stmt = select(User).where(User.id == user_id)
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
        # Get user
        stmt = select(User).where(User.id == user_id)
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
