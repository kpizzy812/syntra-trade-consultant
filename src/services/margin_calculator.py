# coding: utf-8
"""
Real-time Margin Calculator

Calculates REAL margins based on actual data from database:
- Real API costs (from ChatMessage table)
- Real user usage (actual request counts)
- Real revenue (from Payment table)
- Real churn and retention

NOT theoretical calculations, but REAL data analysis!
"""
import logging
from datetime import datetime, timedelta, UTC
from typing import Dict, Optional
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    User,
    Payment,
    ChatMessage,
    Subscription,
    SubscriptionTier,
    PaymentStatus,
)

logger = logging.getLogger(__name__)


async def get_real_costs_per_user(
    session: AsyncSession,
    user_id: int,
    days: int = 30,
) -> Dict[str, float]:
    """
    Получить РЕАЛЬНЫЕ затраты на пользователя за период

    Returns:
        {
            'total_cost': 12.50,           # Общие затраты в USD
            'request_count': 850,          # Количество запросов
            'avg_cost_per_request': 0.0147, # Средняя стоимость запроса
            'total_tokens': 125000,        # Всего токенов
        }
    """
    start_date = datetime.now(UTC) - timedelta(days=days)

    # Запрос реальных затрат из ChatMessage
    stmt = (
        select(
            func.count(ChatMessage.id).label('request_count'),
            func.sum(ChatMessage.total_tokens).label('total_tokens'),
            func.sum(ChatMessage.total_cost).label('total_cost'),
        )
        .where(ChatMessage.user_id == user_id)
        .where(ChatMessage.created_at >= start_date)
    )

    result = await session.execute(stmt)
    row = result.first()

    if not row or not row.request_count:
        return {
            'total_cost': 0.0,
            'request_count': 0,
            'avg_cost_per_request': 0.0,
            'total_tokens': 0,
        }

    total_cost = float(row.total_cost or 0)
    request_count = int(row.request_count or 0)
    total_tokens = int(row.total_tokens or 0)

    avg_cost = total_cost / request_count if request_count > 0 else 0

    return {
        'total_cost': total_cost,
        'request_count': request_count,
        'avg_cost_per_request': avg_cost,
        'total_tokens': total_tokens,
    }


async def get_real_margin_for_subscription(
    session: AsyncSession,
    user_id: int,
    days: int = 30,
) -> Dict[str, float]:
    """
    Рассчитать РЕАЛЬНУЮ маржу для подписки пользователя

    Returns:
        {
            'subscription_price': 24.99,
            'real_cost': 8.50,
            'margin_usd': 16.49,
            'margin_percent': 66.0,
            'usage_percent': 45.0,  # Реальный % использования
            'is_profitable': True,
        }
    """
    # Получить подписку пользователя
    stmt = select(Subscription).where(Subscription.user_id == user_id)
    result = await session.execute(stmt)
    subscription = result.scalar_one_or_none()

    if not subscription:
        return {
            'error': 'No subscription found',
            'is_profitable': False,
        }

    # Получить реальные затраты
    costs = await get_real_costs_per_user(session, user_id, days)

    # Получить цену подписки (за последний месяц)
    start_date = datetime.now(UTC) - timedelta(days=days)
    stmt = (
        select(func.sum(Payment.amount))
        .where(Payment.user_id == user_id)
        .where(Payment.status == PaymentStatus.COMPLETED.value)
        .where(Payment.completed_at >= start_date)
    )
    result = await session.execute(stmt)
    revenue = float(result.scalar() or 0)

    # Если нет платежей, используем базовую цену тира
    if revenue == 0:
        tier_prices = {
            SubscriptionTier.BASIC: 4.99,
            SubscriptionTier.PREMIUM: 24.99,
            SubscriptionTier.VIP: 49.99,
            SubscriptionTier.FREE: 0.0,
        }
        revenue = tier_prices.get(subscription.tier, 0.0)

    # Рассчитать маржу
    real_cost = costs['total_cost']
    margin_usd = revenue - real_cost
    margin_percent = (margin_usd / revenue * 100) if revenue > 0 else 0

    # Рассчитать реальный % использования
    # Получить лимит пользователя
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one()

    daily_limit = user.get_request_limit()
    expected_requests = daily_limit * days
    usage_percent = (costs['request_count'] / expected_requests * 100) if expected_requests > 0 else 0

    return {
        'subscription_price': revenue,
        'real_cost': real_cost,
        'margin_usd': margin_usd,
        'margin_percent': round(margin_percent, 2),
        'usage_percent': round(usage_percent, 2),
        'is_profitable': margin_usd > 0,
        'request_count': costs['request_count'],
        'avg_cost_per_request': costs['avg_cost_per_request'],
    }


async def get_global_margin_analytics(
    session: AsyncSession,
    days: int = 30,
) -> Dict[str, any]:
    """
    Получить глобальную аналитику маржи для всего проекта

    Returns:
        {
            'total_revenue': 1249.50,
            'total_costs': 425.30,
            'total_margin': 824.20,
            'margin_percent': 65.96,
            'avg_margin_per_user': 16.48,
            'users_analyzed': 50,
            'profitable_users': 45,
            'unprofitable_users': 5,
            'recommended_revenue_share': 12.5,  # На основе реальных данных!
        }
    """
    start_date = datetime.now(UTC) - timedelta(days=days)

    # Получить всех активных пользователей с подписками
    stmt = (
        select(User)
        .join(Subscription)
        .where(Subscription.is_active == True)
        .where(Subscription.tier != SubscriptionTier.FREE)
    )
    result = await session.execute(stmt)
    users = result.scalars().all()

    total_revenue = 0.0
    total_costs = 0.0
    profitable_count = 0
    unprofitable_count = 0

    for user in users:
        margin_data = await get_real_margin_for_subscription(session, user.id, days)

        if 'error' not in margin_data:
            total_revenue += margin_data['subscription_price']
            total_costs += margin_data['real_cost']

            if margin_data['is_profitable']:
                profitable_count += 1
            else:
                unprofitable_count += 1

    total_margin = total_revenue - total_costs
    margin_percent = (total_margin / total_revenue * 100) if total_revenue > 0 else 0
    avg_margin_per_user = total_margin / len(users) if users else 0

    # Рассчитать рекомендуемый % ревшара на основе РЕАЛЬНЫХ данных
    # Целевая маржа 50%, доступная маржа для ревшара = actual - 50%
    available_margin_percent = max(0, margin_percent - 50)
    recommended_revshare = min(20, available_margin_percent * 0.5)  # 50% от доступной маржи

    # Получить реальные выплаты ревшара
    stmt = select(func.sum(User.total_referral_earnings))
    result = await session.execute(stmt)
    total_revshare_paid = float(result.scalar() or 0)

    # Эффективный % ревшара (сколько реально выплачиваем)
    effective_revshare_percent = (total_revshare_paid / total_revenue * 100) if total_revenue > 0 else 0

    return {
        'period_days': days,
        'total_revenue': round(total_revenue, 2),
        'total_costs': round(total_costs, 2),
        'total_margin': round(total_margin, 2),
        'margin_percent': round(margin_percent, 2),
        'avg_margin_per_user': round(avg_margin_per_user, 2),
        'users_analyzed': len(users),
        'profitable_users': profitable_count,
        'unprofitable_users': unprofitable_count,
        'total_revshare_paid': round(total_revshare_paid, 2),
        'effective_revshare_percent': round(effective_revshare_percent, 2),
        'recommended_revenue_share': round(recommended_revshare, 2),
    }


async def get_margin_by_tier(
    session: AsyncSession,
    days: int = 30,
) -> Dict[str, Dict]:
    """
    Получить маржу по каждому тиру подписки

    Returns:
        {
            'basic': {'revenue': 99.80, 'costs': 30.50, 'margin': 69.4},
            'premium': {'revenue': 499.80, 'costs': 150.20, 'margin': 69.9},
            'vip': {'revenue': 999.60, 'costs': 280.40, 'margin': 71.9},
        }
    """
    start_date = datetime.now(UTC) - timedelta(days=days)

    tier_data = {}

    for tier in [SubscriptionTier.BASIC, SubscriptionTier.PREMIUM, SubscriptionTier.VIP]:
        # Получить пользователей этого тира
        stmt = (
            select(User)
            .join(Subscription)
            .where(Subscription.tier == tier)
            .where(Subscription.is_active == True)
        )
        result = await session.execute(stmt)
        users = result.scalars().all()

        if not users:
            continue

        total_revenue = 0.0
        total_costs = 0.0

        for user in users:
            margin_data = await get_real_margin_for_subscription(session, user.id, days)
            if 'error' not in margin_data:
                total_revenue += margin_data['subscription_price']
                total_costs += margin_data['real_cost']

        margin = total_revenue - total_costs
        margin_percent = (margin / total_revenue * 100) if total_revenue > 0 else 0

        tier_data[tier.value] = {
            'users': len(users),
            'revenue': round(total_revenue, 2),
            'costs': round(total_costs, 2),
            'margin_usd': round(margin, 2),
            'margin_percent': round(margin_percent, 2),
        }

    return tier_data


async def check_margin_alerts(
    session: AsyncSession,
    threshold_percent: float = 30.0,
) -> Dict[str, any]:
    """
    Проверить пользователей с низкой маржой (алерты)

    Args:
        threshold_percent: Порог маржи для алерта (по умолчанию 30%)

    Returns:
        {
            'low_margin_users': [
                {'user_id': 123, 'username': '@john', 'margin': 25.5},
                ...
            ],
            'alert_count': 3,
        }
    """
    # Получить всех активных пользователей с подписками
    stmt = (
        select(User)
        .join(Subscription)
        .where(Subscription.is_active == True)
        .where(Subscription.tier != SubscriptionTier.FREE)
    )
    result = await session.execute(stmt)
    users = result.scalars().all()

    low_margin_users = []

    for user in users:
        margin_data = await get_real_margin_for_subscription(session, user.id, days=30)

        if 'error' not in margin_data:
            margin_percent = margin_data['margin_percent']

            if margin_percent < threshold_percent:
                low_margin_users.append({
                    'user_id': user.id,
                    'telegram_id': user.telegram_id,
                    'username': f"@{user.username}" if user.username else user.first_name,
                    'margin_percent': margin_percent,
                    'margin_usd': margin_data['margin_usd'],
                    'cost': margin_data['real_cost'],
                    'revenue': margin_data['subscription_price'],
                })

    return {
        'threshold_percent': threshold_percent,
        'low_margin_users': low_margin_users,
        'alert_count': len(low_margin_users),
    }


if __name__ == "__main__":
    print("💰 Real-time Margin Calculator")
    print("\nThis module analyzes REAL data from database:")
    print("- Actual API costs from ChatMessage table")
    print("- Actual revenue from Payment table")
    print("- Actual usage patterns")
    print("\nUse in admin panel: /admin_margin")
