# coding: utf-8
"""
Unit Economics Configuration

Комиссии платежных систем и настройки для расчета unit economics.
"""

from typing import Dict


# ============================================================================
# КОМИССИИ ПЛАТЕЖНЫХ СИСТЕМ
# ============================================================================

PAYMENT_FEES: Dict[str, float] = {
    "telegram_stars": 0.10,   # 10% - Apple/Google берут свой %
    "crypto_bot": 0.03,       # 3%
    "ton_connect": 0.00,      # 0% - только gas
    "nowpayments": 0.01,      # 1%
}


def get_payment_fee(provider: str) -> float:
    """
    Получить комиссию платежной системы

    Args:
        provider: Название провайдера (telegram_stars, crypto_bot и др.)

    Returns:
        Комиссия как доля (0.10 = 10%)
    """
    # Нормализуем название провайдера
    provider_lower = provider.lower().replace("-", "_").replace(" ", "_")
    return PAYMENT_FEES.get(provider_lower, 0.05)  # По умолчанию 5%


def get_weighted_payment_fee(payments_by_provider: Dict[str, float]) -> float:
    """
    Рассчитать средневзвешенную комиссию на основе сумм платежей

    Args:
        payments_by_provider: {provider: total_amount}

    Returns:
        Средневзвешенная комиссия
    """
    total_amount = sum(payments_by_provider.values())
    if total_amount == 0:
        return 0.05  # По умолчанию 5%

    weighted_fee = sum(
        amount * get_payment_fee(provider)
        for provider, amount in payments_by_provider.items()
    )
    return weighted_fee / total_amount


# ============================================================================
# РЕФЕРАЛЬНЫЕ БОНУСЫ (для расчета затрат)
# ============================================================================

REFERRAL_BONUS_COSTS = {
    "signup_bonus": 5,        # +5 запросов рефери при регистрации
    "activation_bonus": 10,   # +10 запросов рефереру при активации
}

# Себестоимость бонусного запроса (используем FREE tier cost)
BONUS_REQUEST_COST = 0.003  # $0.003 за запрос


def calculate_referral_bonus_cost(signup_count: int, activation_count: int) -> float:
    """
    Рассчитать затраты на реферальные бонусы

    Args:
        signup_count: Количество новых регистраций по рефке
        activation_count: Количество активаций рефералов

    Returns:
        Общие затраты на бонусы в USD
    """
    signup_requests = signup_count * REFERRAL_BONUS_COSTS["signup_bonus"]
    activation_requests = activation_count * REFERRAL_BONUS_COSTS["activation_bonus"]

    total_requests = signup_requests + activation_requests
    return total_requests * BONUS_REQUEST_COST


# ============================================================================
# TRIAL КОНФИГУРАЦИЯ
# ============================================================================

TRIAL_CONFIG = {
    "tier": "premium",
    "duration_days": 7,
    "cost_per_request": 0.018,  # PREMIUM tier cost
}


# ============================================================================
# СЕБЕСТОИМОСТЬ ПО ТИРАМ (дублируется из limits.py для удобства)
# ============================================================================

TIER_API_COSTS = {
    "free": 0.003,
    "basic": 0.005,
    "premium": 0.018,
    "vip": 0.030,
}

# Дополнительные типы запросов
CHART_COST = 0.002
VISION_COST = 0.020
