"""
Confidence Intervals

Расчёт доверительных интервалов для Scenario Class Stats:
- Wilson score для winrate CI
- EV lower CI (нормальное приближение, позже bootstrap)
"""
import math
from typing import List, Tuple, Optional
from dataclasses import dataclass
import numpy as np

from src.learning.constants import CI_Z_SCORE


@dataclass
class WilsonResult:
    """Результат Wilson score interval."""
    lower: float    # Lower bound
    upper: float    # Upper bound
    center: float   # Observed proportion (winrate)


@dataclass
class EVConfidenceResult:
    """Результат CI для EV."""
    mean: float         # Mean EV
    lower: float        # Lower bound
    upper: float        # Upper bound
    std: float          # Standard deviation
    se: float           # Standard error


def wilson_score_interval(
    wins: int,
    total: int,
    z: float = CI_Z_SCORE
) -> WilsonResult:
    """
    Wilson score interval для биномиальной пропорции (winrate).

    Wilson score более точен чем normal approximation,
    особенно для малых выборок и крайних значений p.

    Args:
        wins: Количество побед
        total: Общее количество сделок
        z: Z-score (1.96 для 95% CI, 1.645 для 90% CI)

    Returns:
        WilsonResult с lower, upper, center

    Formula:
        center = (p + z²/2n) / (1 + z²/n)
        spread = z * sqrt((p(1-p) + z²/4n) / n) / (1 + z²/n)
        lower = center - spread
        upper = center + spread
    """
    if total == 0:
        return WilsonResult(lower=0.0, upper=1.0, center=0.5)

    p = wins / total
    n = total
    z2 = z ** 2

    denominator = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denominator

    spread_term = (p * (1 - p) + z2 / (4 * n)) / n
    spread = z * math.sqrt(spread_term) / denominator

    lower = max(0.0, center - spread)
    upper = min(1.0, center + spread)

    return WilsonResult(lower=lower, upper=upper, center=p)


def wilson_score_lower(
    wins: int,
    total: int,
    z: float = CI_Z_SCORE
) -> float:
    """
    Получить только lower bound Wilson score.

    Удобная функция для kill switch логики.

    Args:
        wins: Количество побед
        total: Общее количество сделок
        z: Z-score (default 1.96 для 95% CI)

    Returns:
        Lower bound winrate
    """
    return wilson_score_interval(wins, total, z).lower


def ev_confidence_interval(
    pnl_values: List[float],
    z: float = CI_Z_SCORE
) -> EVConfidenceResult:
    """
    Доверительный интервал для EV (нормальное приближение).

    CI = mean ± z * (std / sqrt(n))

    Это грубая оценка. Для более точного CI использовать bootstrap.

    Args:
        pnl_values: Список PnL значений в R
        z: Z-score (default 1.96 для 95% CI)

    Returns:
        EVConfidenceResult с mean, lower, upper, std, se
    """
    if len(pnl_values) < 2:
        mean_val = pnl_values[0] if pnl_values else 0.0
        return EVConfidenceResult(
            mean=mean_val,
            lower=mean_val,
            upper=mean_val,
            std=0.0,
            se=0.0,
        )

    mean_val = float(np.mean(pnl_values))
    std_val = float(np.std(pnl_values, ddof=1))  # sample std
    n = len(pnl_values)
    se = std_val / math.sqrt(n)

    lower = mean_val - z * se
    upper = mean_val + z * se

    return EVConfidenceResult(
        mean=mean_val,
        lower=lower,
        upper=upper,
        std=std_val,
        se=se,
    )


def ev_lower_ci(
    pnl_values: List[float],
    z: float = CI_Z_SCORE
) -> float:
    """
    Получить только lower bound EV CI.

    Удобная функция для kill switch логики.

    Args:
        pnl_values: Список PnL значений в R
        z: Z-score (default 1.96 для 95% CI)

    Returns:
        Lower bound EV
    """
    return ev_confidence_interval(pnl_values, z).lower


def bootstrap_ev_ci(
    pnl_values: List[float],
    n_bootstrap: int = 10000,
    confidence: float = 0.95,
) -> Tuple[float, float]:
    """
    Bootstrap доверительный интервал для EV.

    Более точный чем нормальное приближение, особенно
    для non-normal distributions.

    Args:
        pnl_values: Список PnL значений в R
        n_bootstrap: Количество bootstrap samples
        confidence: Уровень confidence (0.95 = 95% CI)

    Returns:
        (lower, upper) bounds
    """
    if len(pnl_values) < 5:
        # Слишком мало данных для bootstrap
        result = ev_confidence_interval(pnl_values)
        return result.lower, result.upper

    pnl_array = np.array(pnl_values)
    n = len(pnl_array)

    # Generate bootstrap samples
    bootstrap_means = []
    for _ in range(n_bootstrap):
        sample = np.random.choice(pnl_array, size=n, replace=True)
        bootstrap_means.append(np.mean(sample))

    # Calculate percentiles
    alpha = (1 - confidence) / 2
    lower = float(np.percentile(bootstrap_means, alpha * 100))
    upper = float(np.percentile(bootstrap_means, (1 - alpha) * 100))

    return lower, upper


def calculate_effect_size(
    group1: List[float],
    group2: List[float],
) -> float:
    """
    Рассчитать Cohen's d effect size между двумя группами.

    d = (mean1 - mean2) / pooled_std

    Интерпретация:
    - |d| < 0.2: negligible
    - 0.2 <= |d| < 0.5: small
    - 0.5 <= |d| < 0.8: medium
    - |d| >= 0.8: large

    Args:
        group1: PnL значения первой группы
        group2: PnL значения второй группы

    Returns:
        Cohen's d
    """
    if len(group1) < 2 or len(group2) < 2:
        return 0.0

    mean1 = np.mean(group1)
    mean2 = np.mean(group2)

    std1 = np.std(group1, ddof=1)
    std2 = np.std(group2, ddof=1)
    n1 = len(group1)
    n2 = len(group2)

    # Pooled standard deviation
    pooled_std = math.sqrt(
        ((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2)
    )

    if pooled_std == 0:
        return 0.0

    return (mean1 - mean2) / pooled_std


def is_statistically_significant(
    wins: int,
    total: int,
    threshold: float = 0.5,
    z: float = CI_Z_SCORE
) -> bool:
    """
    Проверить статистически значимое отличие winrate от threshold.

    Используется для kill switch: если верхняя граница CI < threshold,
    то класс статистически значимо хуже threshold.

    Args:
        wins: Количество побед
        total: Общее количество сделок
        threshold: Threshold для сравнения (default 0.5)
        z: Z-score

    Returns:
        True если winrate статистически значимо НИЖЕ threshold
    """
    result = wilson_score_interval(wins, total, z)
    return result.upper < threshold


def is_ev_significantly_negative(
    pnl_values: List[float],
    z: float = CI_Z_SCORE
) -> bool:
    """
    Проверить статистически значимо отрицательный EV.

    Используется для kill switch: если верхняя граница CI < 0,
    то EV статистически значимо отрицателен.

    Args:
        pnl_values: Список PnL значений
        z: Z-score

    Returns:
        True если EV статистически значимо < 0
    """
    if len(pnl_values) < 5:
        return False

    result = ev_confidence_interval(pnl_values, z)
    return result.upper < 0
