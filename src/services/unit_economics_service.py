# coding: utf-8
"""
Unit Economics Service

Комплексные расчеты unit economics для платформы:
- Маржа по тарифам с учетом комиссий платежек
- Free tier экономика
- Trial экономика
- Реферальная экономика
- Сценарии при разных % использования
"""

from datetime import datetime, timedelta, UTC
from typing import Dict, Any, Optional
from dataclasses import dataclass

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    User,
    Payment,
    Subscription,
    Referral,
    BonusRequest,
    ReferralBalance,
    Chat,
    ChatMessage,
    SubscriptionTier,
    PaymentStatus,
    ReferralStatus,
)
from config.unit_economics import (
    get_payment_fee,
    get_weighted_payment_fee,
    TIER_API_COSTS,
    BONUS_REQUEST_COST,
)
from config.limits import TIER_LIMITS, COST_PER_REQUEST


@dataclass
class TierMarginData:
    """Данные о марже тарифа"""
    tier: str
    users_count: int
    gross_revenue: float
    payment_fees: float
    payment_fee_percent: float
    net_revenue: float
    api_costs: float
    revshare_costs: float
    total_costs: float
    margin_usd: float
    margin_percent: float
    avg_usage_percent: float
    avg_requests_per_user: float


@dataclass
class FreeEconomicsData:
    """Данные об экономике FREE тира"""
    total_free_users: int
    active_free_users: int
    total_requests: int
    total_cost: float
    avg_cost_per_user: float
    conversion_to_trial: float
    conversion_to_paid: float


@dataclass
class TrialEconomicsData:
    """Данные об экономике trial"""
    active_trials: int
    completed_trials: int
    trial_requests: int
    trial_cost: float
    avg_trial_cost_per_user: float
    trials_converted: int
    conversion_rate: float
    revenue_from_converted: float
    roi: float


@dataclass
class ReferralEconomicsData:
    """Данные о реферальной экономике"""
    total_referrals: int
    active_referrals: int
    pending_referrals: int
    bonus_requests_granted: int
    bonus_requests_cost: float
    revshare_paid: float
    referral_revenue: float
    effective_revshare_rate: float
    roi: float


# ============================================================================
# МАРЖА ПО ТАРИФАМ
# ============================================================================

async def get_tier_margin_with_fees(
    session: AsyncSession,
    days: int = 30,
) -> Dict[str, TierMarginData]:
    """
    Рассчитать маржу по каждому тарифу с учетом комиссий платежек

    Args:
        session: DB session
        days: Период анализа в днях

    Returns:
        Dict с данными по каждому тарифу
    """
    start_date = datetime.now(UTC) - timedelta(days=days)
    result = {}

    tiers = [SubscriptionTier.BASIC, SubscriptionTier.PREMIUM, SubscriptionTier.VIP]
    for tier in tiers:
        tier_data = await _calculate_tier_margin(session, tier, start_date, days)
        if tier_data:
            result[tier.value] = tier_data

    return result


async def _calculate_tier_margin(
    session: AsyncSession,
    tier: SubscriptionTier,
    start_date: datetime,
    days: int,
) -> Optional[TierMarginData]:
    """Рассчитать маржу для конкретного тарифа"""

    # 1. Получить пользователей тарифа
    stmt = (
        select(User.id)
        .join(Subscription)
        .where(Subscription.tier == tier.value)
        .where(Subscription.is_active.is_(True))
    )
    result = await session.execute(stmt)
    user_ids = [row[0] for row in result.fetchall()]

    if not user_ids:
        return None

    users_count = len(user_ids)

    # 2. Получить доход с разбивкой по провайдерам
    stmt = (
        select(
            Payment.provider,
            func.sum(Payment.amount).label('total_amount'),
        )
        .where(Payment.user_id.in_(user_ids))
        .where(Payment.status == PaymentStatus.COMPLETED.value)
        .where(Payment.completed_at >= start_date)
        .group_by(Payment.provider)
    )
    result = await session.execute(stmt)
    payments_by_provider = {
        row.provider: float(row.total_amount or 0)
        for row in result.fetchall()
    }

    gross_revenue = sum(payments_by_provider.values())

    # 3. Рассчитать комиссии платежек
    if gross_revenue > 0:
        weighted_fee = get_weighted_payment_fee(payments_by_provider)
        payment_fees = gross_revenue * weighted_fee
        payment_fee_percent = weighted_fee * 100
    else:
        # Если нет платежей за период, используем теоретический доход
        tier_config = TIER_LIMITS.get(tier, {})
        gross_revenue = tier_config.get("price_usd", 0) * users_count
        payment_fees = gross_revenue * 0.05  # Усредненная комиссия 5%
        payment_fee_percent = 5.0

    net_revenue = gross_revenue - payment_fees

    # 4. Получить API расходы (через Chat -> ChatMessage)
    # ChatMessage связан с Chat, Chat связан с User
    stmt = (
        select(func.count(ChatMessage.id).label('request_count'))
        .join(Chat, ChatMessage.chat_id == Chat.id)
        .where(Chat.user_id.in_(user_ids))
        .where(ChatMessage.timestamp >= start_date)
        .where(ChatMessage.role == 'assistant')  # Только ответы AI
    )
    result = await session.execute(stmt)
    request_count = result.scalar() or 0
    # Расчет стоимости на основе тира
    tier_cost = TIER_API_COSTS.get(tier.value, 0.01)
    api_costs = request_count * tier_cost

    # 5. Получить revenue share выплаты для этих пользователей
    # (пользователи тарифа которые являются рефералами кого-то)
    stmt = (
        select(func.sum(ReferralBalance.earned_total_usd))
        .join(User, ReferralBalance.user_id == User.id)
        .join(Subscription, User.id == Subscription.user_id)
        .where(Subscription.tier == tier.value)
    )
    result = await session.execute(stmt)
    revshare_costs = float(result.scalar() or 0)
    # Пропорционируем по дням
    revshare_costs = revshare_costs * (days / 30) if revshare_costs > 0 else 0

    # 6. Рассчитать метрики
    total_costs = api_costs + revshare_costs
    margin_usd = net_revenue - total_costs
    margin_percent = (margin_usd / net_revenue * 100) if net_revenue > 0 else 0

    # Рассчитать % использования лимитов
    tier_config = TIER_LIMITS.get(tier, {})
    daily_limit = tier_config.get("text_per_day", 1)
    expected_requests = daily_limit * days * users_count
    avg_usage_percent = (
        (request_count / expected_requests * 100) if expected_requests > 0 else 0
    )
    avg_requests_per_user = request_count / users_count if users_count > 0 else 0

    return TierMarginData(
        tier=tier.value,
        users_count=users_count,
        gross_revenue=round(gross_revenue, 2),
        payment_fees=round(payment_fees, 2),
        payment_fee_percent=round(payment_fee_percent, 1),
        net_revenue=round(net_revenue, 2),
        api_costs=round(api_costs, 2),
        revshare_costs=round(revshare_costs, 2),
        total_costs=round(total_costs, 2),
        margin_usd=round(margin_usd, 2),
        margin_percent=round(margin_percent, 1),
        avg_usage_percent=round(avg_usage_percent, 1),
        avg_requests_per_user=round(avg_requests_per_user, 1),
    )


# ============================================================================
# FREE TIER ЭКОНОМИКА
# ============================================================================

async def get_free_tier_economics(
    session: AsyncSession,
    days: int = 30,
) -> FreeEconomicsData:
    """
    Анализ экономики FREE тира

    Args:
        session: DB session
        days: Период анализа

    Returns:
        FreeEconomicsData
    """
    start_date = datetime.now(UTC) - timedelta(days=days)

    # 1. Всего FREE пользователей
    stmt = (
        select(func.count(User.id))
        .join(Subscription)
        .where(Subscription.tier == SubscriptionTier.FREE.value)
    )
    result = await session.execute(stmt)
    total_free_users = result.scalar() or 0

    # 2. Активные FREE (делали запросы за период)
    # Chat -> User -> Subscription
    stmt = (
        select(func.count(func.distinct(Chat.user_id)))
        .join(User, Chat.user_id == User.id)
        .join(Subscription, User.id == Subscription.user_id)
        .join(ChatMessage, ChatMessage.chat_id == Chat.id)
        .where(Subscription.tier == SubscriptionTier.FREE.value)
        .where(ChatMessage.timestamp >= start_date)
    )
    result = await session.execute(stmt)
    active_free_users = result.scalar() or 0

    # 3. Запросы и расходы от FREE
    stmt = (
        select(func.count(ChatMessage.id).label('request_count'))
        .join(Chat, ChatMessage.chat_id == Chat.id)
        .join(User, Chat.user_id == User.id)
        .join(Subscription, User.id == Subscription.user_id)
        .where(Subscription.tier == SubscriptionTier.FREE.value)
        .where(ChatMessage.timestamp >= start_date)
        .where(ChatMessage.role == 'assistant')  # Только ответы AI
    )
    result = await session.execute(stmt)
    total_requests = result.scalar() or 0
    # FREE tier cost
    free_cost = TIER_API_COSTS.get("free", 0.003)
    total_cost = total_requests * free_cost

    avg_cost_per_user = total_cost / active_free_users if active_free_users > 0 else 0

    # 4. Конверсия FREE -> Trial
    # Пользователи которые были FREE и получили trial за период
    stmt = (
        select(func.count(Subscription.id))
        .where(Subscription.is_trial.is_(True))
        .where(Subscription.trial_start >= start_date)
    )
    result = await session.execute(stmt)
    converted_to_trial = result.scalar() or 0

    conversion_to_trial = (
        (converted_to_trial / total_free_users * 100) if total_free_users > 0 else 0
    )

    # 5. Конверсия FREE -> Paid (напрямую, без trial)
    stmt = (
        select(func.count(func.distinct(Payment.user_id)))
        .join(Subscription, Payment.user_id == Subscription.user_id)
        .where(Payment.status == PaymentStatus.COMPLETED.value)
        .where(Payment.completed_at >= start_date)
        .where(Subscription.tier != SubscriptionTier.FREE.value)
        .where(Subscription.is_trial.is_(False))
    )
    result = await session.execute(stmt)
    converted_to_paid = result.scalar() or 0

    conversion_to_paid = (
        (converted_to_paid / total_free_users * 100) if total_free_users > 0 else 0
    )

    return FreeEconomicsData(
        total_free_users=total_free_users,
        active_free_users=active_free_users,
        total_requests=total_requests,
        total_cost=round(total_cost, 2),
        avg_cost_per_user=round(avg_cost_per_user, 4),
        conversion_to_trial=round(conversion_to_trial, 1),
        conversion_to_paid=round(conversion_to_paid, 1),
    )


# ============================================================================
# TRIAL ЭКОНОМИКА
# ============================================================================

async def get_trial_economics(
    session: AsyncSession,
    days: int = 30,
) -> TrialEconomicsData:
    """
    Анализ экономики trial периода

    Args:
        session: DB session
        days: Период анализа

    Returns:
        TrialEconomicsData
    """
    start_date = datetime.now(UTC) - timedelta(days=days)

    # 1. Активные триалы сейчас
    stmt = (
        select(func.count(Subscription.id))
        .where(Subscription.is_trial.is_(True))
        .where(Subscription.is_active.is_(True))
    )
    result = await session.execute(stmt)
    active_trials = result.scalar() or 0

    # 2. Завершившиеся триалы за период
    stmt = (
        select(func.count(Subscription.id))
        .where(Subscription.is_trial.is_(False))
        .where(Subscription.trial_end.isnot(None))
        .where(Subscription.trial_end >= start_date)
    )
    result = await session.execute(stmt)
    completed_trials = result.scalar() or 0

    # 3. Запросы от trial пользователей
    stmt = (
        select(func.count(ChatMessage.id).label('request_count'))
        .join(Chat, ChatMessage.chat_id == Chat.id)
        .join(User, Chat.user_id == User.id)
        .join(Subscription, User.id == Subscription.user_id)
        .where(Subscription.is_trial.is_(True))
        .where(ChatMessage.timestamp >= start_date)
        .where(ChatMessage.role == 'assistant')  # Только ответы AI
    )
    result = await session.execute(stmt)
    trial_requests = result.scalar() or 0
    # Trial users get PREMIUM tier access
    premium_cost = TIER_API_COSTS.get("premium", 0.018)
    trial_cost = trial_requests * premium_cost

    avg_trial_cost = trial_cost / active_trials if active_trials > 0 else 0

    # 4. Конверсия trial -> paid
    # Пользователи у которых trial закончился и они оплатили
    stmt = (
        select(func.count(func.distinct(Payment.user_id)))
        .join(User, Payment.user_id == User.id)
        .join(Subscription, User.id == Subscription.user_id)
        .where(Payment.status == PaymentStatus.COMPLETED.value)
        .where(Payment.completed_at >= start_date)
        .where(Subscription.trial_end.isnot(None))  # Был trial
    )
    result = await session.execute(stmt)
    trials_converted = result.scalar() or 0

    total_trials_ended = completed_trials + trials_converted
    conversion_rate = (
        (trials_converted / total_trials_ended * 100)
        if total_trials_ended > 0 else 0
    )

    # 5. Доход от конвертировавшихся
    stmt = (
        select(func.sum(Payment.amount))
        .join(User, Payment.user_id == User.id)
        .join(Subscription, User.id == Subscription.user_id)
        .where(Payment.status == PaymentStatus.COMPLETED.value)
        .where(Payment.completed_at >= start_date)
        .where(Subscription.trial_end.isnot(None))
    )
    result = await session.execute(stmt)
    revenue_from_converted = float(result.scalar() or 0)

    # 6. ROI = (Revenue - Cost) / Cost * 100
    total_trial_cost = trial_cost
    if total_trial_cost > 0:
        roi = ((revenue_from_converted - total_trial_cost) / total_trial_cost) * 100
    else:
        roi = 0

    return TrialEconomicsData(
        active_trials=active_trials,
        completed_trials=completed_trials,
        trial_requests=trial_requests,
        trial_cost=round(trial_cost, 2),
        avg_trial_cost_per_user=round(avg_trial_cost, 2),
        trials_converted=trials_converted,
        conversion_rate=round(conversion_rate, 1),
        revenue_from_converted=round(revenue_from_converted, 2),
        roi=round(roi, 1),
    )


# ============================================================================
# РЕФЕРАЛЬНАЯ ЭКОНОМИКА
# ============================================================================

async def get_referral_economics(
    session: AsyncSession,
    days: int = 30,
) -> ReferralEconomicsData:
    """
    Анализ реферальной экономики

    Args:
        session: DB session
        days: Период анализа

    Returns:
        ReferralEconomicsData
    """
    start_date = datetime.now(UTC) - timedelta(days=days)

    # 1. Всего рефералов
    stmt = select(func.count(Referral.id))
    result = await session.execute(stmt)
    total_referrals = result.scalar() or 0

    # 2. Активные рефералы (status=active)
    stmt = (
        select(func.count(Referral.id))
        .where(Referral.status == ReferralStatus.ACTIVE.value)
    )
    result = await session.execute(stmt)
    active_referrals = result.scalar() or 0

    # 3. Pending рефералы
    stmt = (
        select(func.count(Referral.id))
        .where(Referral.status == ReferralStatus.PENDING.value)
    )
    result = await session.execute(stmt)
    pending_referrals = result.scalar() or 0

    # 4. Бонусные запросы за период
    referral_sources = [
        'REFERRAL_SIGNUP', 'REFERRAL_ACTIVATION',
        'referral_signup', 'referral_activation'
    ]
    stmt = (
        select(func.sum(BonusRequest.amount))
        .where(BonusRequest.created_at >= start_date)
        .where(BonusRequest.source.in_(referral_sources))
    )
    result = await session.execute(stmt)
    bonus_requests_granted = int(result.scalar() or 0)
    bonus_requests_cost = bonus_requests_granted * BONUS_REQUEST_COST

    # 5. Revenue share выплачено за период
    stmt = (
        select(func.sum(ReferralBalance.earned_total_usd))
    )
    result = await session.execute(stmt)
    total_revshare = float(result.scalar() or 0)
    # Пропорционально периоду
    revshare_paid = total_revshare * (days / 30) if total_revshare > 0 else 0

    # 6. Доход от рефералов (платежи от referee)
    stmt = (
        select(func.sum(Payment.amount))
        .join(User, Payment.user_id == User.id)
        .where(Payment.status == PaymentStatus.COMPLETED.value)
        .where(Payment.completed_at >= start_date)
        .where(User.referred_by_id.isnot(None))
    )
    result = await session.execute(stmt)
    referral_revenue = float(result.scalar() or 0)

    # 7. Эффективный % ревшара
    effective_revshare_rate = (
        (revshare_paid / referral_revenue * 100) if referral_revenue > 0 else 0
    )

    # 8. ROI реферальной программы
    total_referral_costs = bonus_requests_cost + revshare_paid
    if total_referral_costs > 0:
        roi = ((referral_revenue - total_referral_costs) / total_referral_costs) * 100
    else:
        roi = 0

    return ReferralEconomicsData(
        total_referrals=total_referrals,
        active_referrals=active_referrals,
        pending_referrals=pending_referrals,
        bonus_requests_granted=bonus_requests_granted,
        bonus_requests_cost=round(bonus_requests_cost, 2),
        revshare_paid=round(revshare_paid, 2),
        referral_revenue=round(referral_revenue, 2),
        effective_revshare_rate=round(effective_revshare_rate, 1),
        roi=round(roi, 1),
    )


# ============================================================================
# СЦЕНАРИИ МАРЖИ
# ============================================================================

async def get_margin_scenarios(
    session: AsyncSession,
) -> Dict[str, Dict[str, Any]]:
    """
    Рассчитать маржу при разных сценариях использования лимитов

    Returns:
        {
            'scenario_30': {...},  # 30% использования
            'scenario_50': {...},  # 50% использования
            'scenario_70': {...},  # 70% использования
            'scenario_100': {...}, # 100% использования
        }
    """
    scenarios = {}

    tiers = [SubscriptionTier.BASIC, SubscriptionTier.PREMIUM, SubscriptionTier.VIP]
    for usage_percent in [30, 50, 70, 100]:
        scenario_data = {}

        for tier in tiers:
            tier_config = TIER_LIMITS.get(tier, {})
            price = tier_config.get("price_usd", 0)

            # Рассчитать расходы при заданном % использования
            daily_limit = tier_config.get("text_per_day", 1)
            chart_limit = tier_config.get("charts_per_day", 0)
            vision_limit = tier_config.get("vision_per_day", 0)

            # Себестоимость
            text_cost = TIER_API_COSTS.get(tier.value, 0.01)
            chart_cost = COST_PER_REQUEST.get("chart", 0.002)
            vision_cost = COST_PER_REQUEST.get("vision", 0.02)

            # Расходы за месяц при данном usage%
            daily_cost = (
                daily_limit * text_cost +
                chart_limit * chart_cost +
                vision_limit * vision_cost
            ) * (usage_percent / 100)

            monthly_cost = daily_cost * 30

            # Комиссия платежек (усредненная 5%)
            payment_fee = price * 0.05
            net_revenue = price - payment_fee

            # Маржа
            margin_usd = net_revenue - monthly_cost
            margin_percent = (margin_usd / net_revenue * 100) if net_revenue > 0 else 0

            scenario_data[tier.value] = {
                "price": price,
                "monthly_cost": round(monthly_cost, 2),
                "payment_fee": round(payment_fee, 2),
                "net_revenue": round(net_revenue, 2),
                "margin_usd": round(margin_usd, 2),
                "margin_percent": round(margin_percent, 1),
                "is_profitable": margin_usd > 0,
            }

        # Общая маржа по всем тарифам (взвешенная)
        total_net_revenue = sum(d["net_revenue"] for d in scenario_data.values())
        total_margin = sum(d["margin_usd"] for d in scenario_data.values())
        overall_margin_percent = (
            (total_margin / total_net_revenue * 100)
            if total_net_revenue > 0 else 0
        )

        scenarios[f"scenario_{usage_percent}"] = {
            "usage_percent": usage_percent,
            "tiers": scenario_data,
            "overall_margin_percent": round(overall_margin_percent, 1),
        }

    return scenarios


# ============================================================================
# СВОДНЫЙ ДАШБОРД
# ============================================================================

async def get_unit_economics_dashboard(
    session: AsyncSession,
    days: int = 30,
) -> Dict[str, Any]:
    """
    Получить сводный дашборд unit economics

    Args:
        session: DB session
        days: Период анализа

    Returns:
        Полные данные для дашборда
    """
    start_date = datetime.now(UTC) - timedelta(days=days)

    # 1. Общий доход с разбивкой по провайдерам
    stmt = (
        select(
            Payment.provider,
            func.sum(Payment.amount).label('total_amount'),
            func.count(Payment.id).label('payment_count'),
        )
        .where(Payment.status == PaymentStatus.COMPLETED.value)
        .where(Payment.completed_at >= start_date)
        .group_by(Payment.provider)
    )
    result = await session.execute(stmt)
    payments_by_provider = {
        row.provider: {
            "amount": float(row.total_amount or 0),
            "count": int(row.payment_count or 0),
        }
        for row in result.fetchall()
    }

    gross_revenue = sum(p["amount"] for p in payments_by_provider.values())

    # Рассчитать комиссии
    payment_fees_total = sum(
        p["amount"] * get_payment_fee(provider)
        for provider, p in payments_by_provider.items()
    )
    net_revenue = gross_revenue - payment_fees_total

    # 2. Общие API расходы (считаем по количеству запросов)
    # Используем средневзвешенную стоимость
    stmt = (
        select(func.count(ChatMessage.id))
        .where(ChatMessage.timestamp >= start_date)
        .where(ChatMessage.role == 'assistant')  # Только ответы AI
    )
    result = await session.execute(stmt)
    total_requests = result.scalar() or 0
    # Средняя стоимость запроса (между free и premium)
    avg_request_cost = 0.01  # ~$0.01 усредненная стоимость
    api_costs = total_requests * avg_request_cost

    # 3. Revenue share
    stmt = select(func.sum(ReferralBalance.earned_total_usd))
    result = await session.execute(stmt)
    total_revshare = float(result.scalar() or 0)
    revshare_costs = total_revshare * (days / 30)

    # 4. Итоговые расчеты
    total_costs = api_costs + revshare_costs
    net_profit = net_revenue - total_costs
    margin_percent = (net_profit / net_revenue * 100) if net_revenue > 0 else 0

    # 5. Ключевые метрики
    # LTV (простой расчет - средний доход с платящего)
    stmt = (
        select(func.count(func.distinct(Payment.user_id)))
        .where(Payment.status == PaymentStatus.COMPLETED.value)
    )
    result = await session.execute(stmt)
    paying_users = result.scalar() or 1

    stmt = (
        select(func.sum(Payment.amount))
        .where(Payment.status == PaymentStatus.COMPLETED.value)
    )
    result = await session.execute(stmt)
    total_revenue_all_time = float(result.scalar() or 0)
    ltv = total_revenue_all_time / paying_users if paying_users > 0 else 0

    # CAC (через FREE tier)
    free_economics = await get_free_tier_economics(session, days)
    cac = (
        free_economics.total_cost / free_economics.active_free_users
        if free_economics.active_free_users > 0 else 0
    )

    ltv_cac_ratio = ltv / cac if cac > 0 else 0

    # Trial конверсия
    trial_economics = await get_trial_economics(session, days)

    return {
        "period_days": days,

        # Общая картина
        "gross_revenue": round(gross_revenue, 2),
        "payment_fees": round(payment_fees_total, 2),
        "payment_fee_percent": round(
            (payment_fees_total / gross_revenue * 100) if gross_revenue > 0 else 0,
            1
        ),
        "net_revenue": round(net_revenue, 2),
        "api_costs": round(api_costs, 2),
        "revshare_costs": round(revshare_costs, 2),
        "total_costs": round(total_costs, 2),
        "net_profit": round(net_profit, 2),
        "margin_percent": round(margin_percent, 1),

        # Платежи по провайдерам
        "payments_by_provider": payments_by_provider,

        # Ключевые метрики
        "ltv": round(ltv, 2),
        "cac": round(cac, 2),
        "ltv_cac_ratio": round(ltv_cac_ratio, 1),
        "trial_conversion_rate": trial_economics.conversion_rate,
        "free_conversion_rate": free_economics.conversion_to_paid,

        # Counts
        "paying_users": paying_users,
        "free_users": free_economics.total_free_users,
        "active_trials": trial_economics.active_trials,
    }
