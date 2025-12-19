"""
Scenario Metrics Service — Python pre-calc для метрик сценариев.

Принцип: LLM не должен вычислять R, RR, chase_distance и т.д.
Python считает всё заранее, LLM только использует готовые числа.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class ScenarioMetrics:
    """Pre-calculated метрики для одного сценария."""
    R: float  # Risk = |entry - stop|
    tp1_rr: float  # TP1 distance in R
    tp2_rr: Optional[float]  # TP2 distance in R
    tp3_rr: Optional[float]  # TP3 distance in R
    chase_distance_R: float  # |entry - current| / R
    invalidation_distance_R: float  # |entry - invalidation| / R
    distance_atr: float  # |entry - current| / ATR
    R_atr_ratio: float  # R / ATR (для проверки valid R)
    is_valid_R: bool  # R в допустимом диапазоне
    r_validation_error: Optional[str]  # Причина невалидности


@dataclass
class ChaseCheck:
    """Результат проверки на chase."""
    chase_distance_R: float
    is_chase: bool
    allowed_reason: Optional[str]
    action: str  # "ALLOWED" | "REJECTED"


class ScenarioMetricsService:
    """
    Сервис для расчёта метрик сценариев в Python.

    Все вычисления делаются здесь, LLM получает готовые числа.
    """

    # Валидные диапазоны R в ATR
    MIN_R_ATR = 0.15  # Стоп слишком узкий (шум)
    MAX_R_ATR = 2.5   # Стоп слишком широкий (fuzzy setup)

    # Порог для chase
    CHASE_THRESHOLD_R = 0.25

    def calculate_scenario_metrics(
        self,
        entry: float,
        stop: float,
        tp1: float,
        tp2: Optional[float],
        tp3: Optional[float],
        invalidation: float,
        current_price: float,
        atr: float,
    ) -> ScenarioMetrics:
        """
        Рассчитать все метрики для сценария.

        Args:
            entry: Цена входа (weighted average для ladder)
            stop: Стоп-лосс
            tp1, tp2, tp3: Take profits
            invalidation: Цена инвалидации сценария
            current_price: Текущая цена
            atr: ATR

        Returns:
            ScenarioMetrics с готовыми расчётами
        """
        # R (Risk)
        R = abs(entry - stop)

        # Защита от деления на 0
        if R <= 0 or atr <= 0:
            logger.debug(f"Invalid inputs: R={R}, ATR={atr}, entry={entry}, stop={stop}")
            return ScenarioMetrics(
                R=0,
                tp1_rr=0,
                tp2_rr=None,
                tp3_rr=None,
                chase_distance_R=0,
                invalidation_distance_R=0,
                distance_atr=0,
                R_atr_ratio=0,
                is_valid_R=False,
                r_validation_error="Invalid inputs: R<=0 or ATR<=0",
            )

        # RR для targets
        tp1_rr = abs(tp1 - entry) / R
        tp2_rr = abs(tp2 - entry) / R if tp2 is not None else None
        tp3_rr = abs(tp3 - entry) / R if tp3 is not None else None

        # Chase distance
        chase_distance_R = abs(entry - current_price) / R

        # Invalidation distance
        invalidation_distance_R = abs(entry - invalidation) / R

        # Distance в ATR
        distance_atr = abs(entry - current_price) / atr

        # R/ATR ratio для валидации
        R_atr_ratio = R / atr

        # Валидация R
        is_valid_R = True
        r_validation_error = None

        if R_atr_ratio < self.MIN_R_ATR:
            is_valid_R = False
            r_validation_error = f"R too tight: {R_atr_ratio:.2f} ATR < {self.MIN_R_ATR}"
        elif R_atr_ratio > self.MAX_R_ATR:
            is_valid_R = False
            r_validation_error = f"R too wide: {R_atr_ratio:.2f} ATR > {self.MAX_R_ATR}"

        return ScenarioMetrics(
            R=round(R, 2),
            tp1_rr=round(tp1_rr, 2),
            tp2_rr=round(tp2_rr, 2) if tp2_rr is not None else None,
            tp3_rr=round(tp3_rr, 2) if tp3_rr is not None else None,
            chase_distance_R=round(chase_distance_R, 2),
            invalidation_distance_R=round(invalidation_distance_R, 2),
            distance_atr=round(distance_atr, 2),
            R_atr_ratio=round(R_atr_ratio, 2),
            is_valid_R=is_valid_R,
            r_validation_error=r_validation_error,
        )

    def check_chase(
        self,
        chase_distance_R: float,
        entry_type: str,
        has_trigger: bool = False,
        has_confirmation: bool = False,
    ) -> ChaseCheck:
        """
        Проверить на chase.

        Args:
            chase_distance_R: |entry - current| / R
            entry_type: "limit_pullback" | "trigger_breakout" | "trigger_reclaim"
            has_trigger: Есть activation trigger
            has_confirmation: Есть подтверждение (reclaim occurred)

        Returns:
            ChaseCheck с результатом
        """
        is_chase = chase_distance_R < self.CHASE_THRESHOLD_R

        if not is_chase:
            return ChaseCheck(
                chase_distance_R=chase_distance_R,
                is_chase=False,
                allowed_reason="distance >= 0.25R",
                action="ALLOWED",
            )

        # Chase detected — проверяем исключения
        allowed_reason = None

        # Entry type = trigger_* → allowed
        if entry_type in ["trigger_breakout", "trigger_reclaim"]:
            allowed_reason = f"has activation trigger ({entry_type})"

        # Entry type = limit_pullback + confirmation → allowed
        elif entry_type == "limit_pullback" and has_confirmation:
            allowed_reason = "reclaim already occurred, waiting pullback"

        # Explicit trigger flag
        elif has_trigger:
            allowed_reason = "has explicit activation trigger"

        if allowed_reason:
            return ChaseCheck(
                chase_distance_R=chase_distance_R,
                is_chase=True,
                allowed_reason=allowed_reason,
                action="ALLOWED",
            )

        return ChaseCheck(
            chase_distance_R=chase_distance_R,
            is_chase=True,
            allowed_reason=None,
            action="REJECTED",
        )

    def calculate_weighted_entry(
        self,
        orders: List[Dict],
    ) -> float:
        """
        Рассчитать weighted average entry для ladder orders.

        Args:
            orders: [{"price": float, "size_pct": int}, ...]

        Returns:
            Weighted average price
        """
        if not orders:
            return 0

        total_weight = sum(o.get("size_pct", 0) for o in orders)
        if total_weight <= 0:
            return orders[0].get("price", 0)

        weighted_sum = sum(
            o.get("price", 0) * o.get("size_pct", 0)
            for o in orders
        )

        return weighted_sum / total_weight

    def validate_scenario_metrics(
        self,
        metrics: ScenarioMetrics,
        bias: str,
        entry: float,
        stop: float,
    ) -> Dict[str, Any]:
        """
        Полная валидация сценария.

        Returns:
            {
                "is_valid": bool,
                "hard_rejects": [...],
                "soft_penalties": [...],
            }
        """
        hard_rejects = []
        soft_penalties = []

        # Hard reject: invalid R
        if not metrics.is_valid_R:
            hard_rejects.append(metrics.r_validation_error)

        # Hard reject: TP1 < 0.8R
        if metrics.tp1_rr < 0.8:
            hard_rejects.append(f"TP1 at {metrics.tp1_rr}R < minimum 0.8R")

        # Hard reject: SL on wrong side
        if bias == "long" and stop >= entry:
            hard_rejects.append("LONG: stop must be BELOW entry")
        elif bias == "short" and stop <= entry:
            hard_rejects.append("SHORT: stop must be ABOVE entry")

        # Soft penalty: invalidation too close
        if metrics.invalidation_distance_R < 0.8:
            soft_penalties.append({
                "reason": f"invalidation_distance_R={metrics.invalidation_distance_R} < 0.8",
                "confidence_penalty": 0.05,
            })

        return {
            "is_valid": len(hard_rejects) == 0,
            "hard_rejects": hard_rejects,
            "soft_penalties": soft_penalties,
        }

    def calculate_weight_raw(self, factors: Dict[str, Any]) -> float:
        """
        Рассчитать weight_raw из weight_factors.

        Args:
            factors: {
                "confluence_count": 0-3,
                "htf_alignment": -1/0/+1,
                "path_clear": bool,
                "invalidation_distance_R": float,
                "tp1_rr": float
            }

        Returns:
            weight_raw в диапазоне [0.05, 0.85]
        """
        # Base score
        base = 0.25

        # Positive factors
        confluence = factors.get("confluence_count", 0)
        base += 0.10 * min(confluence, 3)  # max +0.30

        if factors.get("path_clear", False):
            base += 0.10

        if factors.get("htf_alignment", 0) > 0:
            base += 0.10

        # Penalties
        penalty = 0.0

        if factors.get("htf_alignment", 0) < 0:
            penalty += 0.10

        if factors.get("invalidation_distance_R", 999) < 0.8:
            penalty += 0.10

        if factors.get("tp1_rr", 999) < 0.8:
            penalty += 0.10

        # Clamp to [0.05, 0.85]
        return max(0.05, min(0.85, base - penalty))

    def normalize_weights(self, scenarios: List[Dict]) -> List[Dict]:
        """
        Нормализовать веса сценариев (сумма = 1.0).

        Args:
            scenarios: Список сценариев с weight_factors

        Returns:
            Сценарии с пересчитанными scenario_weight
        """
        if not scenarios:
            return scenarios

        # Рассчитываем weight_raw для каждого сценария
        weights_raw = []
        for sc in scenarios:
            factors = sc.get("weight_factors", {})
            weight_raw = self.calculate_weight_raw(factors)
            weights_raw.append(weight_raw)
            sc["weight_raw"] = round(weight_raw, 3)

        # Нормализуем
        total = sum(weights_raw)
        if total > 0:
            for i, sc in enumerate(scenarios):
                sc["scenario_weight"] = round(weights_raw[i] / total, 3)
        else:
            # Равный вес если все = 0
            equal_weight = round(1.0 / len(scenarios), 3)
            for sc in scenarios:
                sc["scenario_weight"] = equal_weight

        return scenarios

    def build_metrics_for_prompt(
        self,
        current_price: float,
        atr: float,
    ) -> Dict[str, Any]:
        """
        Подготовить базовые pre-calculated данные для промпта.

        Эти данные пойдут в market_data.metrics.
        Уровни передаются отдельно через LevelQualityService.

        Returns:
            Dict с ready-to-use метриками (цена, ATR, границы R)
        """
        return {
            "current_price": round(current_price, 2),
            "atr": round(atr, 2),
            "atr_pct": round(atr / current_price * 100, 3) if current_price > 0 else 0,
            "min_valid_R": round(self.MIN_R_ATR * atr, 2),
            "max_valid_R": round(self.MAX_R_ATR * atr, 2),
            "chase_threshold_R": self.CHASE_THRESHOLD_R,
            # Примерные значения для LLM reference
            "typical_stop_distance": {
                "tight": round(0.5 * atr, 2),
                "normal": round(1.0 * atr, 2),
                "wide": round(2.0 * atr, 2),
            },
        }


# Singleton instance
scenario_metrics_service = ScenarioMetricsService()
