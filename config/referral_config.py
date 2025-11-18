# coding: utf-8
"""
Referral System Configuration

Centralized configuration for referral tiers and revenue sharing.
Allows easy adjustments without database migrations.
"""

# =======================
# REFERRAL TIER SETTINGS
# =======================

REFERRAL_TIERS = {
    "bronze": {
        "min_referrals": 0,
        "max_referrals": 4,
        "revenue_share_percent": 0.0,
        "monthly_bonus": 0,
        "discount_percent": 0.0,
        "display_emoji": "🥉",
        "display_name_ru": "Бронза",
        "display_name_en": "Bronze",
    },
    "silver": {
        "min_referrals": 5,
        "max_referrals": 14,
        "revenue_share_percent": 5.0,
        "monthly_bonus": 50,
        "discount_percent": 10.0,
        "display_emoji": "🥈",
        "display_name_ru": "Серебро",
        "display_name_en": "Silver",
    },
    "gold": {
        "min_referrals": 15,
        "max_referrals": 49,
        "revenue_share_percent": 10.0,  # Можно менять без миграции БД
        "monthly_bonus": 150,
        "discount_percent": 20.0,
        "display_emoji": "🥇",
        "display_name_ru": "Золото",
        "display_name_en": "Gold",
    },
    "platinum": {
        "min_referrals": 50,
        "max_referrals": None,  # Безлимит
        "revenue_share_percent": 15.0,
        "monthly_bonus": 500,
        "discount_percent": 30.0,
        "display_emoji": "💎",
        "display_name_ru": "Платина",
        "display_name_en": "Platinum",
    },
}


# =======================
# DYNAMIC OPTIMIZATION
# =======================

# Target margins (минимальная маржа которую хотим сохранить)
TARGET_MARGIN_PERCENT = 50.0  # 50% - целевая маржа после ревшара

# Maximum revenue share (потолок, чтобы не обанкротиться)
MAX_REVENUE_SHARE_PERCENT = 20.0  # Максимум 20% от выручки

# Minimum revenue share for active tiers
MIN_REVENUE_SHARE_PERCENT = 5.0  # Минимум 5% чтобы мотивировать


# =======================
# QUALITY MULTIPLIERS
# =======================

# Бонусы за качество рефералов (будущая фича)
QUALITY_MULTIPLIERS = {
    "high_retention": 1.2,      # +20% если retention > 80%
    "high_ltv": 1.15,           # +15% если LTV > средний
    "fast_conversion": 1.1,     # +10% если конверсия < 7 дней
}


# =======================
# HELPER FUNCTIONS
# =======================

def get_tier_config(tier_name: str) -> dict:
    """Get configuration for specific tier"""
    return REFERRAL_TIERS.get(tier_name, REFERRAL_TIERS["bronze"])


def calculate_optimal_revenue_share(
    tier: str,
    avg_usage_percent: float = 0.4,  # Средний % использования (40%)
    avg_cost_per_request: float = 0.00648,  # Из расчетов выше
    subscription_price: float = 24.99,  # PREMIUM
    requests_limit: int = 100,
) -> float:
    """
    Динамически рассчитывает оптимальный процент ревшара
    на основе реальных метрик

    Args:
        tier: Tier name
        avg_usage_percent: Средний % использования лимита (0.0-1.0)
        avg_cost_per_request: Средняя стоимость запроса в USD
        subscription_price: Цена подписки в USD
        requests_limit: Лимит запросов в день

    Returns:
        Оптимальный процент ревшара
    """
    # Фактические расходы на пользователя в месяц
    monthly_requests = requests_limit * 30 * avg_usage_percent
    monthly_cost = monthly_requests * avg_cost_per_request

    # Фактическая маржа
    actual_margin = subscription_price - monthly_cost
    margin_percent = (actual_margin / subscription_price) * 100

    # Доступная маржа для ревшара (сверх целевой маржи)
    available_margin = margin_percent - TARGET_MARGIN_PERCENT

    # Процент ревшара = 50% от доступной маржи (остальное - подушка безопасности)
    revenue_share = available_margin * 0.5

    # Применяем границы
    revenue_share = max(MIN_REVENUE_SHARE_PERCENT, revenue_share)
    revenue_share = min(MAX_REVENUE_SHARE_PERCENT, revenue_share)

    return round(revenue_share, 2)


def get_tier_by_referral_count(referral_count: int) -> str:
    """
    Определить tier на основе количества рефералов

    Args:
        referral_count: Количество активных рефералов

    Returns:
        Tier name
    """
    for tier_name, config in REFERRAL_TIERS.items():
        min_refs = config["min_referrals"]
        max_refs = config["max_referrals"]

        if max_refs is None:  # Platinum (безлимит)
            if referral_count >= min_refs:
                return tier_name
        else:
            if min_refs <= referral_count <= max_refs:
                return tier_name

    return "bronze"  # Default


# =======================
# ANALYTICS THRESHOLDS
# =======================

# Пороги для аналитики и алертов
ALERT_THRESHOLDS = {
    "low_margin": 30.0,         # Алерт если маржа < 30%
    "high_churn": 20.0,          # Алерт если churn > 20%
    "low_conversion": 5.0,       # Алерт если конверсия < 5%
}


if __name__ == "__main__":
    # Тестирование расчетов
    print("🧮 Referral Revenue Share Calculator\n")

    subscriptions = [
        ("BASIC", 4.99, 20),
        ("PREMIUM", 24.99, 100),
        ("VIP", 49.99, 200),
    ]

    for name, price, limit in subscriptions:
        optimal_share = calculate_optimal_revenue_share(
            tier="gold",
            subscription_price=price,
            requests_limit=limit,
        )
        print(f"{name} (${price}/mo, {limit} req/day):")
        print(f"  Optimal revenue share: {optimal_share}%")
        print(f"  Revenue share amount: ${price * (optimal_share / 100):.2f}\n")
