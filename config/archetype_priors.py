"""
Archetype Priors — глобальные priors по архетипам сетапов.

Используется для:
1. Валидации outcome_probs от LLM (должны быть близки к priors)
2. Калибровки вероятностей на основе исторических данных
3. Проверки что сумма probs = 1.0
"""

from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass


class ScenarioArchetype(str, Enum):
    """
    Архетипы торговых сценариев.

    LLM ОБЯЗАН выбрать один из этих архетипов для каждого сценария.
    """
    RANGE_RECLAIM = "range_reclaim"           # Mean reversion после ложного пробоя рейнджа
    BREAKOUT_RETEST = "breakout_retest"       # Пробой + ретест уровня
    SWEEP_RECLAIM = "sweep_reclaim"           # Sweep ликвидности + возврат в структуру
    TREND_PULLBACK = "trend_pullback"         # Откат к EMA/VWAP в трендовом рынке
    FAILED_BREAKDOWN = "failed_breakdown"     # Ложный пробой вниз → разворот
    FAILED_BREAKOUT = "failed_breakout"       # Ложный пробой вверх → разворот
    MOMENTUM_CONTINUATION = "momentum_continuation"  # Продолжение после консолидации
    LIQUIDITY_GRAB = "liquidity_grab"         # Захват ликвидности перед движением


@dataclass
class ArchetypePriors:
    """Priors для одного архетипа."""
    prob_sl: float      # Вероятность стопа
    prob_tp1: float     # Вероятность TP1
    prob_tp2: float     # Вероятность TP2
    prob_tp3: float     # Вероятность TP3
    prob_be: float      # Вероятность breakeven/manual close

    # Метаданные для калибровки
    typical_rr: float = 1.5      # Типичный RR для архетипа
    avg_hold_hours: float = 4.0  # Среднее время в позиции

    def validate(self) -> bool:
        """Проверить что probs валидны."""
        total = self.prob_sl + self.prob_tp1 + self.prob_tp2 + self.prob_tp3 + self.prob_be
        if abs(total - 1.0) > 0.001:
            return False
        if self.prob_tp2 > self.prob_tp1:
            return False
        if self.prob_tp3 > self.prob_tp2:
            return False
        return True

    def to_dict(self) -> Dict:
        """Преобразовать в dict для промпта."""
        return {
            "prob_sl": self.prob_sl,
            "prob_tp1": self.prob_tp1,
            "prob_tp2": self.prob_tp2,
            "prob_tp3": self.prob_tp3,
            "prob_be": self.prob_be,
        }


# =============================================================================
# GLOBAL PRIORS TABLE
# =============================================================================
# Эти значения — baseline для LLM. Модель может отклоняться, но должна
# объяснить причину в "prob_deviation_reason".
#
# Источник: анализ исторических данных + экспертная оценка.
# Будут уточняться по мере накопления реальных данных.
# =============================================================================

GLOBAL_ARCHETYPE_PRIORS: Dict[ScenarioArchetype, ArchetypePriors] = {

    # Range Reclaim: Mean reversion после ложного пробоя
    # Высокий prob_sl потому что range может сломаться
    ScenarioArchetype.RANGE_RECLAIM: ArchetypePriors(
        prob_sl=0.35,
        prob_tp1=0.28,
        prob_tp2=0.17,
        prob_tp3=0.08,
        prob_be=0.12,
        typical_rr=1.8,
        avg_hold_hours=6.0,
    ),

    # Breakout Retest: Пробой + ретест
    # Самый высокий prob_sl — много false breakouts
    ScenarioArchetype.BREAKOUT_RETEST: ArchetypePriors(
        prob_sl=0.38,
        prob_tp1=0.25,
        prob_tp2=0.16,
        prob_tp3=0.08,
        prob_be=0.13,
        typical_rr=2.0,
        avg_hold_hours=8.0,
    ),

    # Sweep Reclaim: Sweep ликвидности + возврат
    # Хороший сетап, но требует точного тайминга
    ScenarioArchetype.SWEEP_RECLAIM: ArchetypePriors(
        prob_sl=0.32,
        prob_tp1=0.28,
        prob_tp2=0.18,
        prob_tp3=0.10,
        prob_be=0.12,
        typical_rr=2.2,
        avg_hold_hours=4.0,
    ),

    # Trend Pullback: Откат в тренде
    # Лучший сетап — тренд на стороне трейдера
    ScenarioArchetype.TREND_PULLBACK: ArchetypePriors(
        prob_sl=0.30,
        prob_tp1=0.30,
        prob_tp2=0.20,
        prob_tp3=0.10,
        prob_be=0.10,
        typical_rr=2.5,
        avg_hold_hours=6.0,
    ),

    # Failed Breakdown: Ложный пробой вниз
    ScenarioArchetype.FAILED_BREAKDOWN: ArchetypePriors(
        prob_sl=0.35,
        prob_tp1=0.28,
        prob_tp2=0.17,
        prob_tp3=0.08,
        prob_be=0.12,
        typical_rr=1.8,
        avg_hold_hours=4.0,
    ),

    # Failed Breakout: Ложный пробой вверх
    ScenarioArchetype.FAILED_BREAKOUT: ArchetypePriors(
        prob_sl=0.35,
        prob_tp1=0.28,
        prob_tp2=0.17,
        prob_tp3=0.08,
        prob_be=0.12,
        typical_rr=1.8,
        avg_hold_hours=4.0,
    ),

    # Momentum Continuation: Продолжение импульса
    # Высокий риск, но и высокий потенциал
    ScenarioArchetype.MOMENTUM_CONTINUATION: ArchetypePriors(
        prob_sl=0.38,
        prob_tp1=0.24,
        prob_tp2=0.16,
        prob_tp3=0.10,
        prob_be=0.12,
        typical_rr=2.0,
        avg_hold_hours=3.0,
    ),

    # Liquidity Grab: Захват ликвидности
    ScenarioArchetype.LIQUIDITY_GRAB: ArchetypePriors(
        prob_sl=0.33,
        prob_tp1=0.28,
        prob_tp2=0.18,
        prob_tp3=0.09,
        prob_be=0.12,
        typical_rr=2.0,
        avg_hold_hours=4.0,
    ),
}


# =============================================================================
# ARCHETYPE CRITERIA
# =============================================================================
# Критерии для проверки что архетип выбран корректно.
# LLM должен указать какие criteria_met выполнены.
# =============================================================================

ARCHETYPE_CRITERIA: Dict[ScenarioArchetype, list] = {
    ScenarioArchetype.RANGE_RECLAIM: [
        "price_in_range",           # Цена внутри рейнджа
        "false_breakout_occurred",  # Был ложный пробой
        "reclaim_above_range_low",  # Возврат выше low рейнджа (для long)
    ],

    ScenarioArchetype.BREAKOUT_RETEST: [
        "breakout_confirmed",       # Пробой подтверждён (close выше уровня)
        "retest_in_progress",       # Ретест происходит
        "volume_on_breakout",       # Объём на пробое был выше среднего
    ],

    ScenarioArchetype.SWEEP_RECLAIM: [
        "sweep_below_swing",        # Свип ниже swing low (для long)
        "reclaim_above",            # Возврат выше структуры
        "volume_spike",             # Всплеск объёма на свипе
    ],

    ScenarioArchetype.TREND_PULLBACK: [
        "trend_confirmed",          # Тренд подтверждён (EMA alignment)
        "pullback_to_support",      # Откат к поддержке (EMA/VWAP/level)
        "no_trend_break",           # Тренд не сломан
    ],

    ScenarioArchetype.FAILED_BREAKDOWN: [
        "breakdown_attempt",        # Попытка пробоя вниз
        "quick_reclaim",            # Быстрый возврат
        "trapped_shorts",           # Шорты в ловушке (funding/OI)
    ],

    ScenarioArchetype.FAILED_BREAKOUT: [
        "breakout_attempt",         # Попытка пробоя вверх
        "quick_rejection",          # Быстрый отказ
        "trapped_longs",            # Лонги в ловушке (funding/OI)
    ],

    ScenarioArchetype.MOMENTUM_CONTINUATION: [
        "strong_move",              # Сильное движение перед консолидацией
        "consolidation",            # Консолидация (low ATR)
        "continuation_setup",       # Сетап на продолжение
    ],

    ScenarioArchetype.LIQUIDITY_GRAB: [
        "liquidity_cluster",        # Кластер ликвидности рядом
        "grab_expected",            # Ожидается захват
        "reversal_setup",           # Сетап на разворот после захвата
    ],
}


def get_archetype_priors(archetype: str) -> Optional[ArchetypePriors]:
    """
    Получить priors для архетипа.

    Args:
        archetype: Название архетипа (string или enum)

    Returns:
        ArchetypePriors или None если архетип не найден
    """
    try:
        if isinstance(archetype, str):
            archetype_enum = ScenarioArchetype(archetype)
        else:
            archetype_enum = archetype
        return GLOBAL_ARCHETYPE_PRIORS.get(archetype_enum)
    except ValueError:
        return None


def get_archetype_criteria(archetype: str) -> list:
    """
    Получить список критериев для архетипа.

    Args:
        archetype: Название архетипа

    Returns:
        Список критериев или пустой список
    """
    try:
        if isinstance(archetype, str):
            archetype_enum = ScenarioArchetype(archetype)
        else:
            archetype_enum = archetype
        return ARCHETYPE_CRITERIA.get(archetype_enum, [])
    except ValueError:
        return []


def validate_outcome_probs(probs: Dict[str, float], archetype: str) -> Dict:
    """
    Валидировать outcome_probs от LLM.

    Args:
        probs: {"prob_sl": 0.3, "prob_tp1": 0.3, ...}
        archetype: Название архетипа

    Returns:
        {
            "is_valid": bool,
            "errors": [...],
            "warnings": [...],
        }
    """
    errors = []
    warnings = []

    # 1. Проверка суммы = 1.0
    total = sum(probs.values())
    if abs(total - 1.0) > 0.01:
        errors.append(f"Sum of probs = {total:.3f}, expected 1.0")

    # 2. Проверка ordering (tp2 <= tp1, tp3 <= tp2)
    if probs.get("prob_tp2", 0) > probs.get("prob_tp1", 0):
        errors.append("prob_tp2 > prob_tp1 (invalid)")
    if probs.get("prob_tp3", 0) > probs.get("prob_tp2", 0):
        errors.append("prob_tp3 > prob_tp2 (invalid)")

    # 3. Проверка отклонения от priors
    prior = get_archetype_priors(archetype)
    if prior:
        prior_dict = prior.to_dict()
        for key, prior_val in prior_dict.items():
            llm_val = probs.get(key, 0)
            deviation = abs(llm_val - prior_val)
            if deviation > 0.15:
                warnings.append(
                    f"{key}: LLM={llm_val:.2f} vs prior={prior_val:.2f} "
                    f"(deviation {deviation:.2f} > 0.15)"
                )

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def build_priors_prompt_block(archetype: str) -> str:
    """
    Построить блок промпта с priors для архетипа.

    Args:
        archetype: Название архетипа

    Returns:
        Строка для вставки в промпт
    """
    prior = get_archetype_priors(archetype)
    if not prior:
        return ""

    return f"""📊 **OUTCOME PROBS PRIORS** for {archetype}:
- prob_sl: {prior.prob_sl:.2f}
- prob_tp1: {prior.prob_tp1:.2f}
- prob_tp2: {prior.prob_tp2:.2f}
- prob_tp3: {prior.prob_tp3:.2f}
- prob_be: {prior.prob_be:.2f}

⚠️ RULES:
1. Sum MUST = 1.0 exactly
2. prob_tp2 <= prob_tp1
3. prob_tp3 <= prob_tp2
4. If deviating from priors, explain in "prob_deviation_reason"
"""
