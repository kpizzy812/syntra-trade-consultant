# coding: utf-8
"""
Admin handlers for $SYNTRA Points system
Analytics, configuration, and management
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from datetime import datetime, timedelta, UTC

from src.database.models import (
    User,
    PointsBalance,
    PointsTransaction,
    PointsLevel,
    PointsTransactionType,
)
from src.services.points_service import PointsService
from config.points_config import (
    BASE_POINTS_EARNING,
    SUBSCRIPTION_EARNING_MULTIPLIERS,
    STREAK_BONUSES,
    MAX_DAILY_POINTS_EARNING,
    MIN_EARNING_INTERVAL_SECONDS,
)

router = Router(name="points_admin")


@router.message(Command("points_analytics"))
async def cmd_points_analytics(
    message: Message,
    session: AsyncSession,
    user: User,
):
    """
    Подробнейшая аналитика системы поинтов (только для админов)

    Args:
        message: Incoming message
        session: Database session
        user: Database user object
    """
    if not user.is_admin:
        await message.answer("⛔ Эта команда доступна только администраторам.")
        return

    telegram_user = message.from_user
    logger.info(f"Admin {telegram_user.id} requested points analytics")

    try:
        # === ОБЩАЯ СТАТИСТИКА ===

        # Total users with points
        stmt_total_users = select(func.count(PointsBalance.id))
        total_users = (await session.execute(stmt_total_users)).scalar()

        # Total points in circulation
        stmt_total_points = select(func.sum(PointsBalance.balance))
        total_points = (await session.execute(stmt_total_points)).scalar() or 0

        # Total earned all time
        stmt_total_earned = select(func.sum(PointsBalance.lifetime_earned))
        total_earned = (await session.execute(stmt_total_earned)).scalar() or 0

        # Total spent all time
        stmt_total_spent = select(func.sum(PointsBalance.lifetime_spent))
        total_spent = (await session.execute(stmt_total_spent)).scalar() or 0

        # Average balance
        avg_balance = total_points / total_users if total_users > 0 else 0

        # === ТРАНЗАКЦИИ ЗА ПОСЛЕДНИЕ 24 ЧАСА ===

        yesterday = datetime.now(UTC) - timedelta(days=1)

        # Transactions last 24h
        stmt_24h = select(func.count(PointsTransaction.id)).where(
            PointsTransaction.created_at >= yesterday
        )
        transactions_24h = (await session.execute(stmt_24h)).scalar()

        # Points earned last 24h
        stmt_earned_24h = select(func.sum(PointsTransaction.amount)).where(
            and_(
                PointsTransaction.created_at >= yesterday,
                PointsTransaction.amount > 0
            )
        )
        earned_24h = (await session.execute(stmt_earned_24h)).scalar() or 0

        # Points spent last 24h
        stmt_spent_24h = select(func.sum(PointsTransaction.amount)).where(
            and_(
                PointsTransaction.created_at >= yesterday,
                PointsTransaction.amount < 0
            )
        )
        spent_24h = abs((await session.execute(stmt_spent_24h)).scalar() or 0)

        # === BREAKDOWN BY TRANSACTION TYPE ===

        stmt_breakdown = select(
            PointsTransaction.transaction_type,
            func.count(PointsTransaction.id).label('count'),
            func.sum(PointsTransaction.amount).label('total')
        ).where(
            PointsTransaction.amount > 0
        ).group_by(
            PointsTransaction.transaction_type
        ).order_by(desc('total'))

        breakdown_result = await session.execute(stmt_breakdown)
        breakdown = breakdown_result.all()

        # === LEVEL DISTRIBUTION ===

        stmt_levels = select(
            PointsBalance.level,
            func.count(PointsBalance.id).label('count')
        ).group_by(PointsBalance.level).order_by(PointsBalance.level)

        levels_result = await session.execute(stmt_levels)
        level_distribution = levels_result.all()

        # === STREAK STATISTICS ===

        stmt_max_streak = select(func.max(PointsBalance.current_streak))
        max_streak = (await session.execute(stmt_max_streak)).scalar() or 0

        stmt_avg_streak = select(func.avg(PointsBalance.current_streak))
        avg_streak = (await session.execute(stmt_avg_streak)).scalar() or 0

        stmt_users_with_streak = select(func.count(PointsBalance.id)).where(
            PointsBalance.current_streak > 0
        )
        users_with_streak = (await session.execute(stmt_users_with_streak)).scalar()

        # === TOP EARNERS ===

        stmt_top_earners = select(
            PointsBalance.user_id,
            User.username,
            User.first_name,
            PointsBalance.balance,
            PointsBalance.level,
            PointsBalance.lifetime_earned
        ).join(User, PointsBalance.user_id == User.id).order_by(
            desc(PointsBalance.balance)
        ).limit(5)

        top_earners_result = await session.execute(stmt_top_earners)
        top_earners = top_earners_result.all()

        # === BUILD RESPONSE ===

        response = "📊 <b>ПОДРОБНАЯ АНАЛИТИКА $SYNTRA POINTS</b>\n\n"

        response += "═══ 💎 ОБЩАЯ СТАТИСТИКА ═══\n"
        response += f"👥 Всего пользователей: <b>{total_users:,}</b>\n"
        response += f"💰 Поинтов в обращении: <b>{int(total_points):,}</b>\n"
        response += f"📈 Всего заработано: <b>{int(total_earned):,}</b>\n"
        response += f"📉 Всего потрачено: <b>{int(total_spent):,}</b>\n"
        response += f"📊 Средний баланс: <b>{int(avg_balance):,}</b>\n\n"

        response += "═══ 🕐 ПОСЛЕДНИЕ 24 ЧАСА ═══\n"
        response += f"🔄 Транзакций: <b>{transactions_24h:,}</b>\n"
        response += f"➕ Заработано: <b>{int(earned_24h):,}</b>\n"
        response += f"➖ Потрачено: <b>{int(spent_24h):,}</b>\n"
        response += f"💹 Баланс 24ч: <b>{int(earned_24h - spent_24h):,}</b>\n\n"

        response += "═══ 📋 ТОП ТИПОВ ТРАНЗАКЦИЙ ═══\n"
        for tx_type, count, total in breakdown[:5]:
            type_name = tx_type.replace("earn_", "").replace("_", " ").title()
            response += f"• {type_name}: <b>{count:,}</b> раз, <b>{int(total):,}</b> pts\n"
        response += "\n"

        response += "═══ 🎯 РАСПРЕДЕЛЕНИЕ ПО УРОВНЯМ ═══\n"
        for level, count in level_distribution:
            percentage = (count / total_users * 100) if total_users > 0 else 0
            response += f"Level {level}: <b>{count:,}</b> ({percentage:.1f}%)\n"
        response += "\n"

        response += "═══ 🔥 СТАТИСТИКА STREAKS ═══\n"
        response += f"🏆 Макс. streak: <b>{max_streak}</b> дней\n"
        response += f"📊 Средний streak: <b>{avg_streak:.1f}</b> дней\n"
        response += f"⭐ Активных streak: <b>{users_with_streak:,}</b>\n\n"

        response += "═══ 👑 ТОП-5 ИГРОКОВ ═══\n"
        for rank, (user_id, username, first_name, balance, level, lifetime) in enumerate(top_earners, 1):
            user_display = f"@{username}" if username else first_name or f"ID{user_id}"
            response += f"{rank}. {user_display}\n"
            response += f"   💎 {int(balance):,} pts (Level {level})\n"
            response += f"   📈 Всего: {int(lifetime):,}\n"

        # Add keyboard for detailed analytics
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📊 Экспорт данных",
                        callback_data="points_admin_export"
                    ),
                    InlineKeyboardButton(
                        text="⚙️ Настройки",
                        callback_data="points_admin_config"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="📈 Графики",
                        callback_data="points_admin_charts"
                    ),
                    InlineKeyboardButton(
                        text="🔍 Детали",
                        callback_data="points_admin_details"
                    ),
                ],
            ]
        )

        await message.answer(response, reply_markup=keyboard, parse_mode="HTML")

        logger.info(f"Points analytics sent to admin {user.id}")

    except Exception as e:
        logger.exception(f"Error in points analytics for admin {user.id}: {e}")
        await message.answer("❌ Ошибка при получении аналитики. Проверьте логи.")


@router.message(Command("points_config"))
async def cmd_points_config(
    message: Message,
    session: AsyncSession,
    user: User,
):
    """
    Показать текущую конфигурацию системы поинтов (только для админов)

    Args:
        message: Incoming message
        session: Database session
        user: Database user object
    """
    if not user.is_admin:
        await message.answer("⛔ Эта команда доступна только администраторам.")
        return

    telegram_user = message.from_user
    logger.info(f"Admin {telegram_user.id} requested points config")

    try:
        response = "⚙️ <b>КОНФИГУРАЦИЯ $SYNTRA POINTS</b>\n\n"

        response += "═══ 💰 БАЗОВЫЕ СТАВКИ ═══\n"
        for tx_type, points in BASE_POINTS_EARNING.items():
            type_name = str(tx_type).replace("PointsTransactionType.", "").replace("EARN_", "")
            response += f"• {type_name}: <b>{points}</b> pts\n"
        response += "\n"

        response += "═══ 📈 МНОЖИТЕЛИ ПОДПИСОК ═══\n"
        for tier, multiplier in SUBSCRIPTION_EARNING_MULTIPLIERS.items():
            tier_name = str(tier).replace("SubscriptionTier.", "")
            response += f"• {tier_name}: <b>{multiplier}x</b>\n"
        response += "\n"

        response += "═══ 🔥 БОНУСЫ ЗА STREAK ═══\n"
        for days, bonus in sorted(STREAK_BONUSES.items()):
            response += f"• {days} дней: <b>+{bonus}</b> pts\n"
        response += "\n"

        response += "═══ 🛡️ БЕЗОПАСНОСТЬ ═══\n"
        response += f"• Max daily earning: <b>{MAX_DAILY_POINTS_EARNING:,}</b>\n"
        response += "• Rate limits:\n"
        for tx_type, seconds in MIN_EARNING_INTERVAL_SECONDS.items():
            type_name = tx_type.replace("earn_", "").replace("_", " ")
            response += f"  - {type_name}: <b>{seconds}s</b>\n"
        response += "\n"

        # Get levels from DB
        stmt = select(PointsLevel).order_by(PointsLevel.level)
        result = await session.execute(stmt)
        levels = result.scalars().all()

        response += "═══ 🎯 УРОВНИ ═══\n"
        for level in levels:
            response += f"{level.icon} <b>Level {level.level}: {level.name_ru}</b>\n"
            response += f"   • Требуется: {level.points_required:,} pts\n"
            response += f"   • Множитель: {level.earning_multiplier}x\n"

        response += "\n<i>💡 Настройки в: config/points_config.py</i>"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✏️ Изменить ставки",
                        callback_data="points_admin_edit_rates"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔢 Изменить лимиты",
                        callback_data="points_admin_edit_limits"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🎯 Изменить уровни",
                        callback_data="points_admin_edit_levels"
                    ),
                ],
            ]
        )

        await message.answer(response, reply_markup=keyboard, parse_mode="HTML")

        logger.info(f"Points config sent to admin {user.id}")

    except Exception as e:
        logger.exception(f"Error in points config for admin {user.id}: {e}")
        await message.answer("❌ Ошибка при получении конфигурации. Проверьте логи.")


@router.message(Command("points_grant"))
async def cmd_points_grant(
    message: Message,
    session: AsyncSession,
    user: User,
):
    """
    Вручную начислить поинты пользователю (только для админов)

    Usage: /points_grant <user_id> <amount> [description]
    Example: /points_grant 123 1000 Bonus for testing

    Args:
        message: Incoming message
        session: Database session
        user: Database user object
    """
    if not user.is_admin:
        await message.answer("⛔ Эта команда доступна только администраторам.")
        return

    parts = message.text.split(maxsplit=3)
    if len(parts) < 3:
        await message.answer(
            "📝 <b>Использование:</b>\n"
            "/points_grant &lt;user_id&gt; &lt;amount&gt; [description]\n\n"
            "<b>Пример:</b>\n"
            "/points_grant 123 1000 Bonus for testing",
            parse_mode="HTML"
        )
        return

    try:
        target_user_id = int(parts[1])
        amount = int(parts[2])
        description = parts[3] if len(parts) > 3 else "Admin grant"

        # Grant points
        points_transaction = await PointsService.earn_points(
            session=session,
            user_id=target_user_id,
            transaction_type=PointsTransactionType.EARN_ADMIN_GRANT,
            amount=amount,
            description=description,
            metadata={"admin_id": user.id, "admin_username": user.username},
            transaction_id=f"admin_grant:{target_user_id}:{datetime.now(UTC).timestamp()}",
        )

        if points_transaction:
            await message.answer(
                f"✅ <b>Начислено {amount:,} поинтов</b>\n\n"
                f"👤 Пользователю: <code>{target_user_id}</code>\n"
                f"💎 Новый баланс: <b>{points_transaction.balance_after:,}</b>\n"
                f"📝 Описание: {description}",
                parse_mode="HTML"
            )
            logger.info(
                f"Admin {user.id} granted {amount} points to user {target_user_id}"
            )
        else:
            await message.answer("❌ Не удалось начислить поинты. Проверьте логи.")

    except ValueError:
        await message.answer("❌ Неверный формат. user_id и amount должны быть числами.")
    except Exception as e:
        logger.exception(f"Error granting points: {e}")
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("points_deduct"))
async def cmd_points_deduct(
    message: Message,
    session: AsyncSession,
    user: User,
):
    """
    Вручную списать поинты у пользователя (только для админов)

    Usage: /points_deduct <user_id> <amount> [description]
    Example: /points_deduct 123 500 Penalty for abuse

    Args:
        message: Incoming message
        session: Database session
        user: Database user object
    """
    if not user.is_admin:
        await message.answer("⛔ Эта команда доступна только администраторам.")
        return

    parts = message.text.split(maxsplit=3)
    if len(parts) < 3:
        await message.answer(
            "📝 <b>Использование:</b>\n"
            "/points_deduct &lt;user_id&gt; &lt;amount&gt; [description]\n\n"
            "<b>Пример:</b>\n"
            "/points_deduct 123 500 Penalty for abuse",
            parse_mode="HTML"
        )
        return

    try:
        target_user_id = int(parts[1])
        amount = int(parts[2])
        description = parts[3] if len(parts) > 3 else "Admin deduction"

        # Deduct points
        points_transaction = await PointsService.spend_points(
            session=session,
            user_id=target_user_id,
            transaction_type=PointsTransactionType.SPEND_ADMIN_DEDUCT,
            amount=amount,
            description=description,
            metadata={"admin_id": user.id, "admin_username": user.username},
        )

        if points_transaction:
            await message.answer(
                f"✅ <b>Списано {amount:,} поинтов</b>\n\n"
                f"👤 У пользователя: <code>{target_user_id}</code>\n"
                f"💎 Новый баланс: <b>{points_transaction.balance_after:,}</b>\n"
                f"📝 Описание: {description}",
                parse_mode="HTML"
            )
            logger.info(
                f"Admin {user.id} deducted {amount} points from user {target_user_id}"
            )
        else:
            await message.answer("❌ Не удалось списать поинты. Проверьте баланс.")

    except ValueError:
        await message.answer("❌ Неверный формат. user_id и amount должны быть числами.")
    except Exception as e:
        logger.exception(f"Error deducting points: {e}")
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("points_user"))
async def cmd_points_user(
    message: Message,
    session: AsyncSession,
    user: User,
):
    """
    Подробная информация о поинтах конкретного пользователя (только для админов)

    Usage: /points_user <user_id>
    Example: /points_user 123

    Args:
        message: Incoming message
        session: Database session
        user: Database user object
    """
    if not user.is_admin:
        await message.answer("⛔ Эта команда доступна только администраторам.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "📝 <b>Использование:</b>\n"
            "/points_user &lt;user_id&gt;\n\n"
            "<b>Пример:</b>\n"
            "/points_user 123",
            parse_mode="HTML"
        )
        return

    try:
        target_user_id = int(parts[1])

        # Get balance info
        balance_info = await PointsService.get_balance(session, target_user_id)

        if not balance_info:
            await message.answer(f"❌ Пользователь {target_user_id} не найден в системе поинтов.")
            return

        # Get user info
        stmt_user = select(User).where(User.id == target_user_id)
        user_result = await session.execute(stmt_user)
        target_user = user_result.scalar_one_or_none()

        if not target_user:
            await message.answer(f"❌ Пользователь {target_user_id} не найден.")
            return

        # Get recent transactions
        transactions = await PointsService.get_transaction_history(
            session=session,
            user_id=target_user_id,
            limit=10,
        )

        # Build response
        user_display = f"@{target_user.username}" if target_user.username else target_user.first_name or f"ID{target_user_id}"

        response = f"👤 <b>Пользователь: {user_display}</b>\n"
        response += f"🆔 ID: <code>{target_user_id}</code>\n\n"

        response += "💎 <b>БАЛАНС И УРОВЕНЬ:</b>\n"
        response += f"• Баланс: <b>{balance_info['balance']:,}</b> pts\n"
        response += f"• Уровень: {balance_info['level_icon']} <b>{balance_info['level']}: {balance_info['level_name']}</b>\n"
        response += f"• Множитель: <b>{balance_info['earning_multiplier']}x</b>\n\n"

        response += "📊 <b>СТАТИСТИКА:</b>\n"
        response += f"• Всего заработано: <b>{balance_info['lifetime_earned']:,}</b>\n"
        response += f"• Всего потрачено: <b>{balance_info['lifetime_spent']:,}</b>\n"
        response += f"• Текущий streak: <b>{balance_info['current_streak']}</b> дней\n"
        response += f"• Лучший streak: <b>{balance_info['longest_streak']}</b> дней\n\n"

        if balance_info['next_level_points']:
            response += f"📈 До Level {balance_info['level'] + 1}: <b>{balance_info['next_level_points']:,}</b> pts\n\n"

        response += "📜 <b>ПОСЛЕДНИЕ 10 ТРАНЗАКЦИЙ:</b>\n"
        for tx in transactions[:10]:
            tx_icon = "+" if tx.amount > 0 else "-"
            response += f"{tx_icon}{abs(tx.amount)} • {tx.transaction_type.replace('earn_', '').replace('spend_', '').replace('_', ' ')}\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💎 Начислить поинты",
                        callback_data=f"points_admin_grant:{target_user_id}"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="➖ Списать поинты",
                        callback_data=f"points_admin_deduct:{target_user_id}"
                    ),
                ],
            ]
        )

        await message.answer(response, reply_markup=keyboard, parse_mode="HTML")

        logger.info(f"Admin {user.id} checked points for user {target_user_id}")

    except ValueError:
        await message.answer("❌ Неверный формат. user_id должен быть числом.")
    except Exception as e:
        logger.exception(f"Error getting user points: {e}")
        await message.answer(f"❌ Ошибка: {e}")


# ====================================
# CALLBACK HANDLERS (Inline buttons)
# ====================================


@router.callback_query(lambda c: c.data == "points_admin_export")
async def callback_points_export(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
):
    """
    Экспорт аналитики в CSV формат
    """
    if not user.is_admin:
        await callback.answer("⛔ Доступно только админам", show_alert=True)
        return

    await callback.answer("🔜 Экспорт в разработке", show_alert=True)
    logger.info(f"Admin {user.id} requested data export")


@router.callback_query(lambda c: c.data == "points_admin_config")
async def callback_points_config(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
):
    """
    Показать меню настроек
    """
    if not user.is_admin:
        await callback.answer("⛔ Доступно только админам", show_alert=True)
        return

    response = "⚙️ <b>НАСТРОЙКИ СИСТЕМЫ</b>\n\n"
    response += "Выберите что хотите изменить:"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить ставки",
                    callback_data="points_admin_edit_rates"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔢 Изменить лимиты",
                    callback_data="points_admin_edit_limits"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Изменить уровни",
                    callback_data="points_admin_edit_levels"
                ),
            ],
        ]
    )

    await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "points_admin_charts")
async def callback_points_charts(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
):
    """
    Показать графики и визуализацию
    """
    if not user.is_admin:
        await callback.answer("⛔ Доступно только админам", show_alert=True)
        return

    await callback.answer("🔜 Графики в разработке", show_alert=True)
    logger.info(f"Admin {user.id} requested charts")


@router.callback_query(lambda c: c.data == "points_admin_details")
async def callback_points_details(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
):
    """
    Детальная статистика по всем типам транзакций
    """
    if not user.is_admin:
        await callback.answer("⛔ Доступно только админам", show_alert=True)
        return

    try:
        # Детальный breakdown по ВСЕМ типам транзакций
        stmt_all_types = select(
            PointsTransaction.transaction_type,
            func.count(PointsTransaction.id).label('count'),
            func.sum(PointsTransaction.amount).label('total'),
            func.avg(PointsTransaction.amount).label('avg_amount')
        ).group_by(
            PointsTransaction.transaction_type
        ).order_by(desc('count'))

        result = await session.execute(stmt_all_types)
        all_types = result.all()

        response = "🔍 <b>ДЕТАЛЬНАЯ СТАТИСТИКА ПО ТИПАМ</b>\n\n"

        earn_types = []
        spend_types = []

        for tx_type, count, total, avg_amount in all_types:
            if "earn" in tx_type.lower():
                earn_types.append((tx_type, count, total, avg_amount))
            else:
                spend_types.append((tx_type, count, total, avg_amount))

        if earn_types:
            response += "📈 <b>ЗАРАБОТОК:</b>\n"
            for tx_type, count, total, avg_amount in earn_types:
                type_name = tx_type.replace("earn_", "").replace("_", " ").title()
                response += f"\n<b>{type_name}</b>\n"
                response += f"  • Транзакций: {count:,}\n"
                response += f"  • Всего: {int(total or 0):,} pts\n"
                response += f"  • Средняя: {int(avg_amount or 0):,} pts\n"

        if spend_types:
            response += "\n\n📉 <b>ТРАТЫ:</b>\n"
            for tx_type, count, total, avg_amount in spend_types:
                type_name = tx_type.replace("spend_", "").replace("_", " ").title()
                response += f"\n<b>{type_name}</b>\n"
                response += f"  • Транзакций: {count:,}\n"
                response += f"  • Всего: {int(abs(total or 0)):,} pts\n"
                response += f"  • Средняя: {int(abs(avg_amount or 0)):,} pts\n"

        await callback.message.edit_text(response, parse_mode="HTML")
        await callback.answer()

        logger.info(f"Admin {user.id} viewed detailed stats")

    except Exception as e:
        logger.exception(f"Error in detailed stats: {e}")
        await callback.answer("❌ Ошибка при получении деталей", show_alert=True)


@router.callback_query(lambda c: c.data == "points_admin_edit_rates")
async def callback_edit_rates(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
):
    """
    Изменить базовые ставки начисления
    """
    if not user.is_admin:
        await callback.answer("⛔ Доступно только админам", show_alert=True)
        return

    response = "✏️ <b>ИЗМЕНЕНИЕ СТАВОК</b>\n\n"
    response += "⚠️ Для изменения ставок отредактируйте:\n"
    response += "<code>config/points_config.py</code>\n\n"
    response += "Параметр: <code>BASE_POINTS_EARNING</code>\n\n"
    response += "После изменения перезапустите бота:\n"
    response += "<code>./manage.sh restart bot</code>"

    await callback.message.edit_text(response, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "points_admin_edit_limits")
async def callback_edit_limits(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
):
    """
    Изменить лимиты и ограничения
    """
    if not user.is_admin:
        await callback.answer("⛔ Доступно только админам", show_alert=True)
        return

    response = "🔢 <b>ИЗМЕНЕНИЕ ЛИМИТОВ</b>\n\n"
    response += "⚠️ Для изменения лимитов отредактируйте:\n"
    response += "<code>config/points_config.py</code>\n\n"
    response += "<b>Параметры:</b>\n"
    response += "• <code>MAX_DAILY_POINTS_EARNING</code>\n"
    response += "• <code>MIN_EARNING_INTERVAL_SECONDS</code>\n\n"
    response += "После изменения перезапустите бота:\n"
    response += "<code>./manage.sh restart bot</code>"

    await callback.message.edit_text(response, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "points_admin_edit_levels")
async def callback_edit_levels(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
):
    """
    Изменить уровни (требует изменения БД)
    """
    if not user.is_admin:
        await callback.answer("⛔ Доступно только админам", show_alert=True)
        return

    response = "🎯 <b>ИЗМЕНЕНИЕ УРОВНЕЙ</b>\n\n"
    response += "⚠️ Уровни хранятся в базе данных.\n\n"
    response += "<b>Для изменения:</b>\n"
    response += "1. Создайте Alembic миграцию\n"
    response += "2. Обновите таблицу <code>points_levels</code>\n"
    response += "3. Примените миграцию:\n"
    response += "   <code>alembic upgrade head</code>\n\n"
    response += "Или используйте SQL напрямую:\n"
    response += "<code>UPDATE points_levels SET ...</code>"

    await callback.message.edit_text(response, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("points_admin_grant:"))
async def callback_grant_points(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
):
    """
    Начислить поинты через callback (из /points_user)
    """
    if not user.is_admin:
        await callback.answer("⛔ Доступно только админам", show_alert=True)
        return

    target_user_id = int(callback.data.split(":")[1])

    response = "💎 <b>НАЧИСЛЕНИЕ ПОИНТОВ</b>\n\n"
    response += f"👤 Пользователь ID: <code>{target_user_id}</code>\n\n"
    response += "Используйте команду:\n"
    response += f"<code>/points_grant {target_user_id} [amount] [description]</code>\n\n"
    response += "<b>Пример:</b>\n"
    response += f"<code>/points_grant {target_user_id} 1000 Bonus</code>"

    await callback.message.edit_text(response, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("points_admin_deduct:"))
async def callback_deduct_points(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
):
    """
    Списать поинты через callback (из /points_user)
    """
    if not user.is_admin:
        await callback.answer("⛔ Доступно только админам", show_alert=True)
        return

    target_user_id = int(callback.data.split(":")[1])

    response = "➖ <b>СПИСАНИЕ ПОИНТОВ</b>\n\n"
    response += f"👤 Пользователь ID: <code>{target_user_id}</code>\n\n"
    response += "Используйте команду:\n"
    response += f"<code>/points_deduct {target_user_id} [amount] [description]</code>\n\n"
    response += "<b>Пример:</b>\n"
    response += f"<code>/points_deduct {target_user_id} 500 Penalty</code>"

    await callback.message.edit_text(response, parse_mode="HTML")
    await callback.answer()
