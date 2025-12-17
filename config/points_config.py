# coding: utf-8
"""
$SYNTRA Points System Configuration

Centralized configuration for points earning and spending rules.
Allows easy adjustments without code changes.
"""

from typing import Dict
from src.database.models import PointsTransactionType, SubscriptionTier


# =======================
# POINTS EARNING RATES
# =======================

# Базовые начисления поинтов за действия (без учета множителей)
BASE_POINTS_EARNING: Dict[str, int] = {
    # За запросы к AI
    PointsTransactionType.EARN_TEXT_REQUEST: 10,  # За текстовый анализ
    PointsTransactionType.EARN_CHART_REQUEST: 15,  # За технический анализ/график
    PointsTransactionType.EARN_VISION_REQUEST: 20,  # За vision анализ (дороже)

    # За подписку (одноразово при покупке)
    PointsTransactionType.EARN_SUBSCRIPTION: 0,  # Настраивается по тарифу (см. SUBSCRIPTION_BONUSES)

    # За реферальную систему
    PointsTransactionType.EARN_REFERRAL_SIGNUP: 500,  # За регистрацию реферала
    PointsTransactionType.EARN_REFERRAL_PURCHASE: 1000,  # За покупку подписки рефералом

    # За ежедневную активность
    PointsTransactionType.EARN_DAILY_LOGIN: 50,  # Базовый бонус за вход

    # За достижения (настраивается отдельно)
    PointsTransactionType.EARN_ACHIEVEMENT: 0,  # Зависит от достижения

    # Админские начисления
    PointsTransactionType.EARN_ADMIN_GRANT: 0,  # Произвольно
}


# =======================
# SUBSCRIPTION BONUSES
# =======================

# Одноразовые бонусы за покупку подписки (зависят от тарифа и длительности)
SUBSCRIPTION_BONUSES: Dict[str, Dict[int, int]] = {
    # Tier -> {duration_months: points}
    SubscriptionTier.BASIC: {
        1: 100,   # 1 месяц BASIC = 100 поинтов
        3: 400,   # 3 месяца BASIC = 400 поинтов (экономия 33%)
        12: 2000,  # 12 месяцев BASIC = 2000 поинтов (экономия 67%)
    },
    SubscriptionTier.PREMIUM: {
        1: 500,   # 1 месяц PREMIUM = 500 поинтов
        3: 2000,  # 3 месяца PREMIUM = 2000 поинтов (экономия 33%)
        12: 10000, # 12 месяцев PREMIUM = 10000 поинтов (экономия 67%)
    },
    SubscriptionTier.VIP: {
        1: 1500,  # 1 месяц VIP = 1500 поинтов
        3: 6000,  # 3 месяца VIP = 6000 поинтов (экономия 33%)
        12: 30000, # 12 месяцев VIP = 30000 поинтов (экономия 67%)
    },
}


# Множители заработка для подписчиков (применяются ко всем начислениям)
SUBSCRIPTION_EARNING_MULTIPLIERS: Dict[str, float] = {
    SubscriptionTier.FREE: 1.0,      # 100% - базовая ставка
    SubscriptionTier.BASIC: 1.2,     # 120% - бонус 20%
    SubscriptionTier.PREMIUM: 1.5,   # 150% - бонус 50%
    SubscriptionTier.VIP: 2.0,       # 200% - бонус 100%
}


# =======================
# DAILY STREAK BONUSES
# =======================

# Бонусы за streak (ежедневные входы подряд)
STREAK_BONUSES: Dict[int, int] = {
    1: 50,     # 1 день
    3: 150,    # 3 дня подряд = бонус 150 (вместо 50)
    7: 500,    # Неделя подряд = бонус 500 (вместо 50)
    14: 1200,  # 2 недели = бонус 1200 (вместо 50)
    30: 3000,  # Месяц подряд = бонус 3000 (вместо 50)
    100: 15000, # 100 дней подряд = мега бонус 15000
}


def get_streak_bonus(streak: int) -> int:
    """
    Получить бонус за текущий streak

    Args:
        streak: Количество дней подряд

    Returns:
        Количество поинтов за streak
    """
    # Ищем максимальный порог, который достигнут
    for threshold in sorted(STREAK_BONUSES.keys(), reverse=True):
        if streak >= threshold:
            return STREAK_BONUSES[threshold]

    return STREAK_BONUSES[1]  # Минимальный бонус


# =======================
# POINTS SPENDING
# =======================

# Стоимость в поинтах (что можно купить за поинты)
POINTS_SPENDING_RATES: Dict[str, int] = {
    # Покупка подписки за поинты (скидка 20% от цены в USD)
    # Например, PREMIUM за $24.99 -> стоит 2000 поинтов (курс ~80 поинтов = $1)
    PointsTransactionType.SPEND_SUBSCRIPTION: 0,  # Зависит от тарифа (см. SUBSCRIPTION_POINTS_COST)

    # Покупка дополнительных запросов (бонус на день)
    PointsTransactionType.SPEND_BONUS_REQUESTS: 100,  # 100 поинтов = +10 запросов на день
}


# Стоимость подписок в поинтах (альтернатива оплате в USD)
SUBSCRIPTION_POINTS_COST: Dict[str, Dict[int, int]] = {
    # Tier -> {duration_months: points}
    # Курс примерно 80 поинтов = $1 (скидка 20% от USD цены)
    SubscriptionTier.BASIC: {
        1: 400,    # $4.99 -> 400 поинтов
        3: 1200,   # $14.99 -> 1200 поинтов
        12: 4800,  # $59.99 -> 4800 поинтов
    },
    SubscriptionTier.PREMIUM: {
        1: 2000,   # $24.99 -> 2000 поинтов
        3: 6000,   # $74.99 -> 6000 поинтов
        12: 24000, # $299.99 -> 24000 поинтов
    },
    SubscriptionTier.VIP: {
        1: 4000,   # $49.99 -> 4000 поинтов
        3: 12000,  # $149.99 -> 12000 поинтов
        12: 48000, # $599.99 -> 48000 поинтов
    },
}


# =======================
# GAMIFICATION SETTINGS
# =======================

# Максимальное количество поинтов за день (защита от абьюза)
MAX_DAILY_POINTS_EARNING = 10000  # 10к поинтов в день максимум

# Минимальный интервал между начислениями одного типа (защита от спама)
MIN_EARNING_INTERVAL_SECONDS: Dict[str, int] = {
    PointsTransactionType.EARN_TEXT_REQUEST: 5,      # Минимум 5 секунд между запросами
    PointsTransactionType.EARN_CHART_REQUEST: 10,    # 10 секунд между графиками
    PointsTransactionType.EARN_VISION_REQUEST: 15,   # 15 секунд между vision
    PointsTransactionType.EARN_DAILY_LOGIN: 86400,   # 1 день (24 часа)
}


# Экспирация поинтов (опционально, можно включить позже)
POINTS_EXPIRATION_ENABLED = False  # Пока отключено
POINTS_EXPIRATION_DAYS = 365  # Поинты истекают через год


# =======================
# DISPLAY SETTINGS
# =======================

# Отображение поинтов
POINTS_DISPLAY_NAME = "$SYNTRA"  # Название валюты
POINTS_EMOJI = "💎"  # Emoji для поинтов


# =======================
# HELPER FUNCTIONS
# =======================

def get_points_for_action(
    action_type: str,
    user_level_multiplier: float = 1.0,
    subscription_tier: str = SubscriptionTier.FREE,
) -> int:
    """
    Рассчитать количество поинтов за действие с учетом множителей

    Args:
        action_type: Тип действия (PointsTransactionType)
        user_level_multiplier: Множитель от уровня пользователя
        subscription_tier: Тариф подписки пользователя

    Returns:
        Количество поинтов к начислению
    """
    base_points = BASE_POINTS_EARNING.get(action_type, 0)

    if base_points == 0:
        return 0

    # Применяем множитель от уровня
    points = base_points * user_level_multiplier

    # Применяем множитель от подписки
    subscription_multiplier = SUBSCRIPTION_EARNING_MULTIPLIERS.get(subscription_tier, 1.0)
    points *= subscription_multiplier

    return int(points)


def get_subscription_bonus(tier: str, duration_months: int) -> int:
    """
    Получить бонус поинтов за покупку подписки

    Args:
        tier: Тариф (BASIC, PREMIUM, VIP)
        duration_months: Длительность в месяцах

    Returns:
        Количество бонусных поинтов
    """
    return SUBSCRIPTION_BONUSES.get(tier, {}).get(duration_months, 0)


def get_subscription_cost_in_points(tier: str, duration_months: int) -> int:
    """
    Получить стоимость подписки в поинтах

    Args:
        tier: Тариф (BASIC, PREMIUM, VIP)
        duration_months: Длительность в месяцах

    Returns:
        Стоимость в поинтах
    """
    return SUBSCRIPTION_POINTS_COST.get(tier, {}).get(duration_months, 0)


if __name__ == "__main__":
    # Тестирование конфигурации
    print("🎮 $SYNTRA Points System Configuration\n")

    print("📊 Базовые начисления:")
    for action, points in BASE_POINTS_EARNING.items():
        print(f"  {action}: {points} поинтов")

    print("\n💰 Бонусы за подписку (PREMIUM, 3 месяца):")
    print(f"  {get_subscription_bonus(SubscriptionTier.PREMIUM, 3)} поинтов")

    print("\n🔥 Примеры расчета с множителями:")
    print(f"  FREE user, level 1: {get_points_for_action(PointsTransactionType.EARN_TEXT_REQUEST, 1.0, SubscriptionTier.FREE)} поинтов за текст")
    print(f"  PREMIUM user, level 3: {get_points_for_action(PointsTransactionType.EARN_TEXT_REQUEST, 1.2, SubscriptionTier.PREMIUM)} поинтов за текст")
    print(f"  VIP user, level 6: {get_points_for_action(PointsTransactionType.EARN_TEXT_REQUEST, 2.0, SubscriptionTier.VIP)} поинтов за текст")

    print("\n🎯 Streak бонусы:")
    for days in [1, 3, 7, 14, 30]:
        print(f"  {days} дней подряд: {get_streak_bonus(days)} поинтов")
