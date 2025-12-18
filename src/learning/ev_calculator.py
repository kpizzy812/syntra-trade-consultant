"""
EV Calculator

Расчёт Expected Value для сценариев на основе:
- Terminal outcome probabilities (Dirichlet smoothed)
- Cumulative payouts с учётом partial TPs
- Fees/slippage
"""
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ArchetypeStats


# =============================================================================
# CONSTANTS
# =============================================================================

# Default outcome probabilities (terminal outcomes) - V2 with path probs
# ⚠️ ВАЖНО: Это OPTIMISTIC PRIOR (tp2+ = ~55%)
# Real probs ВСЕГДА переопределяются learning при sample_size >= 30
# Без learning paper EV будет завышен!
DEFAULT_PROBS_LONG = {
    "sl_early": 0.28,        # SL до TP1 (полный лосс)
    "be_after_tp1": 0.07,    # BE hit после TP1
    "stop_in_profit": 0.05,  # Trail profit после TP1
    "tp1_final": 0.25,       # Финал на TP1
    "tp2_final": 0.20,       # Финал на TP2
    "tp3_final": 0.10,       # Финал на TP3
    "other": 0.05,
}
DEFAULT_PROBS_SHORT = {
    "sl_early": 0.30,
    "be_after_tp1": 0.07,
    "stop_in_profit": 0.05,
    "tp1_final": 0.23,
    "tp2_final": 0.20,
    "tp3_final": 0.10,
    "other": 0.05,
}

# Dirichlet prior strength (как будто N виртуальных сделок)
PRIOR_STRENGTH = 6

# Minimum trades for reliable probabilities
MIN_TRADES_FOR_PROBS = 30

# Default fees in R
DEFAULT_FEES_R = 0.05  # Снижено с 0.15 (более реалистично для Bybit)

# Stop in profit heuristic (V1 placeholder)
# TODO: replace with empirical avg_r_stop_in_profit from Real EV
STOP_IN_PROFIT_HEURISTIC_R = 0.5

# Sanity check thresholds
MIN_PROB_FLOOR = 0.01
MAX_PROB_CAP = 0.95


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class OutcomeProbs:
    """Вероятности terminal outcomes (V2 с path probs)."""
    sl_early: float         # SL до любого TP (полный лосс -1R)
    be_after_tp1: float     # BE hit после TP1 (payout = RR1*w1)
    stop_in_profit: float   # Trail/lock profit после TP1 (payout > RR1*w1)
    tp1_final: float        # Финал на TP1
    tp2_final: float        # Финал на TP2
    tp3_final: Optional[float]
    other: float
    source: str  # "learning" | "llm" | "default"
    sample_size: int
    n_targets: int
    flags: List[str]


@dataclass
class EVMetrics:
    """Результат EV расчёта."""
    ev_r: float             # Net EV (fees уже в payouts)
    ev_r_after_tp1: float   # Conditional EV после TP1 (NEW!)
    fees_r: float           # Комиссии в R
    ev_grade: str           # A/B/C/D
    scenario_score: float   # Normalized score
    n_targets: int
    flags: List[str]


# =============================================================================
# EV CALCULATOR
# =============================================================================

class EVCalculator:
    """
    Калькулятор Expected Value для сценариев (V2 с path probabilities).

    Учитывает Break-Even механику:
    - sl_early: SL до TP1 = -1R
    - be_after_tp1: BE hit после TP1 = RR1*w1 (остальное 0)
    - stop_in_profit: Trail/lock после TP1 = RR1*w1 + bonus
    - tp*_final: Кумулятивные payouts

    Формула:
    EV_R = Σ(P_outcome * payout_outcome) для всех outcomes
    """

    async def calculate_ev(
        self,
        session: AsyncSession,
        targets: List[Dict[str, Any]],
        side: str,
        archetype: Optional[str] = None,
        timeframe: Optional[str] = None,
        volatility_regime: Optional[str] = None,
        confidence: float = 0.5,
        llm_probs: Optional[Dict[str, float]] = None,
        fees_r: float = DEFAULT_FEES_R,
    ) -> Tuple[OutcomeProbs, EVMetrics]:
        """
        Рассчитать EV для сценария.

        Args:
            session: DB session
            targets: Список targets [{price, rr, partial_close_pct}, ...]
            side: "long" | "short"
            archetype: Trade archetype
            timeframe: Timeframe
            volatility_regime: low/normal/high
            confidence: AI confidence (для scenario_score)
            llm_probs: LLM-generated outcome probs (опционально)
            fees_r: Комиссии в R

        Returns:
            (OutcomeProbs, EVMetrics)
        """
        flags = []
        n_targets = len(targets)

        if n_targets == 0:
            flags.append("no_targets")
            return self._default_result(side, confidence, flags)

        if n_targets < 3:
            flags.append(f"reduced_targets_{n_targets}")

        # 1. Получаем вероятности
        probs = await self._get_outcome_probs(
            session=session,
            side=side,
            archetype=archetype,
            timeframe=timeframe,
            volatility_regime=volatility_regime,
            llm_probs=llm_probs,
            n_targets=n_targets,
        )
        flags.extend(probs.flags)

        # 2. Нормализуем веса targets
        weights = self._normalize_weights(targets)
        if weights is None:
            flags.append("invalid_weights")
            return self._default_result(side, confidence, flags)

        # 3. Рассчитываем payouts
        payouts = self._calculate_payouts(targets, weights, fees_r)

        # 4. Рассчитываем EV (fees уже в payouts!)
        ev_r = self._calculate_ev(probs, payouts)

        # 5. Рассчитываем EV после TP1 (conditional)
        ev_r_after_tp1 = self._calculate_ev_after_tp1(probs, payouts, weights[0])

        # 6. Sanity checks
        if ev_r > 2.5:
            flags.append("fantasy_ev")
        if fees_r > 0.30:
            flags.append("high_fees_impact")

        # 7. EV Grade
        ev_grade = self._get_ev_grade(ev_r)

        # 8. Scenario Score (clamp EV для нормализации)
        ev_clamped = max(-1.0, min(1.0, ev_r))
        scenario_score = 0.6 * ev_clamped + 0.4 * confidence

        metrics = EVMetrics(
            ev_r=round(ev_r, 4),
            ev_r_after_tp1=round(ev_r_after_tp1, 4),
            fees_r=fees_r,
            ev_grade=ev_grade,
            scenario_score=round(scenario_score, 4),
            n_targets=n_targets,
            flags=flags,
        )

        return probs, metrics

    async def _get_outcome_probs(
        self,
        session: AsyncSession,
        side: str,
        archetype: Optional[str],
        timeframe: Optional[str],
        volatility_regime: Optional[str],
        llm_probs: Optional[Dict[str, float]],
        n_targets: int,
    ) -> OutcomeProbs:
        """Получить outcome probs с fallback (V2 с path probs)."""
        side_lower = side.lower()
        flags = []

        # 1. Пробуем Learning Module (V2 с новыми полями)
        if archetype:
            stats = await self._get_archetype_stats(
                session, archetype, side_lower, timeframe, volatility_regime
            )
            if stats and stats.total_trades >= MIN_TRADES_FOR_PROBS:
                probs = self._dirichlet_smooth_v2(stats, side_lower)
                probs = self._adapt_probs_to_targets(probs, n_targets, flags)
                return self._create_outcome_probs(probs, "learning", stats.total_trades, n_targets, flags)

        # 2. Пробуем LLM probs (конвертируем в V2 формат)
        if llm_probs:
            validated = self._validate_and_convert_llm_probs(llm_probs)
            if validated:
                validated = self._adapt_probs_to_targets(validated, n_targets, flags)
                return self._create_outcome_probs(validated, "llm", 0, n_targets, flags)
            else:
                flags.append("llm_probs_rejected")

        # 3. Defaults
        defaults = DEFAULT_PROBS_LONG if side_lower == "long" else DEFAULT_PROBS_SHORT
        adapted = self._adapt_probs_to_targets(defaults.copy(), n_targets, flags)
        flags.append("using_defaults")

        return self._create_outcome_probs(adapted, "default", 0, n_targets, flags)

    def _create_outcome_probs(
        self,
        probs: Dict[str, float],
        source: str,
        sample_size: int,
        n_targets: int,
        flags: List[str],
    ) -> OutcomeProbs:
        """Создать OutcomeProbs из dict."""
        return OutcomeProbs(
            sl_early=probs.get("sl_early", 0.0),
            be_after_tp1=probs.get("be_after_tp1", 0.0),
            stop_in_profit=probs.get("stop_in_profit", 0.0),
            tp1_final=probs.get("tp1_final", 0.0),
            tp2_final=probs.get("tp2_final", 0.0),
            tp3_final=probs.get("tp3_final"),
            other=probs.get("other", 0.05),
            source=source,
            sample_size=sample_size,
            n_targets=n_targets,
            flags=flags,
        )

    async def _get_archetype_stats(
        self,
        session: AsyncSession,
        archetype: str,
        side: str,
        timeframe: Optional[str],
        volatility_regime: Optional[str],
    ) -> Optional[ArchetypeStats]:
        """
        Получить stats с fallback по специфичности.

        Fallback:
        1. archetype + side + tf + vol (самый точный)
        2. archetype + side + tf
        3. archetype + side
        4. side only (общий)
        """
        search_configs = [
            {"archetype": archetype, "side": side, "timeframe": timeframe, "volatility_regime": volatility_regime},
            {"archetype": archetype, "side": side, "timeframe": timeframe, "volatility_regime": None},
            {"archetype": archetype, "side": side, "timeframe": None, "volatility_regime": None},
        ]

        for config in search_configs:
            stmt = select(ArchetypeStats).where(
                and_(
                    ArchetypeStats.archetype == config["archetype"],
                    ArchetypeStats.side == config["side"],
                    ArchetypeStats.timeframe == config.get("timeframe"),
                    ArchetypeStats.volatility_regime == config.get("volatility_regime"),
                    ArchetypeStats.symbol == None,  # Global stats
                )
            )
            result = await session.execute(stmt)
            stats = result.scalar_one_or_none()
            if stats and stats.total_trades >= MIN_TRADES_FOR_PROBS:
                return stats

        return None

    def _dirichlet_smooth_v2(self, stats: ArchetypeStats, side: str) -> Dict[str, float]:
        """
        Применить Dirichlet smoothing к counts (V2 с path probs).

        P_i = (count_i + α_i) / (N + Σα)
        где α_i = default_i * PRIOR_STRENGTH
        """
        defaults = DEFAULT_PROBS_LONG if side == "long" else DEFAULT_PROBS_SHORT
        alpha = {k: v * PRIOR_STRENGTH for k, v in defaults.items()}

        # V2 counts - если новые поля есть, используем их
        # Иначе fallback на legacy с флагом
        has_v2_counts = hasattr(stats, "exit_sl_early_count") and stats.exit_sl_early_count is not None

        if has_v2_counts:
            counts = {
                "sl_early": getattr(stats, "exit_sl_early_count", 0) or 0,
                "be_after_tp1": getattr(stats, "exit_be_after_tp1_count", 0) or 0,
                "stop_in_profit": getattr(stats, "exit_stop_in_profit_count", 0) or 0,
                "tp1_final": getattr(stats, "exit_tp1_count", 0) or 0,
                "tp2_final": getattr(stats, "exit_tp2_count", 0) or 0,
                "tp3_final": getattr(stats, "exit_tp3_count", 0) or 0,
                "other": getattr(stats, "exit_other_count", 0) or 0,
            }
        else:
            # Legacy fallback - НЕ выдумываем 75/25!
            # Просто используем defaults, learning пропускаем
            logger.debug("Legacy stats without V2 counts, using defaults")
            return defaults.copy()

        N = sum(counts.values())
        sum_alpha = PRIOR_STRENGTH

        probs = {}
        for key in defaults.keys():
            count = counts.get(key, 0)
            probs[key] = (count + alpha[key]) / (N + sum_alpha)

        return probs

    def _validate_and_convert_llm_probs(self, probs: Dict[str, float]) -> Optional[Dict[str, float]]:
        """Валидация LLM probs и конвертация в V2 формат."""
        # Проверяем что есть базовые ключи (V1 или V2)
        has_v1 = "sl" in probs and "tp1" in probs
        has_v2 = "sl_early" in probs and "tp1_final" in probs

        if not has_v1 and not has_v2:
            return None

        # Конвертируем V1 → V2 если нужно
        if has_v1 and not has_v2:
            # Конвертация: sl → sl_early + be_after_tp1
            sl_total = probs.get("sl", 0.4)
            probs = {
                "sl_early": sl_total * 0.75,       # 75% SL до TP1
                "be_after_tp1": sl_total * 0.20,   # 20% BE после TP1
                "stop_in_profit": sl_total * 0.05, # 5% trail profit
                "tp1_final": probs.get("tp1", 0.25),
                "tp2_final": probs.get("tp2", 0.15),
                "tp3_final": probs.get("tp3", 0.10),
                "other": probs.get("other", 0.05),
            }

        # Проверяем сумму
        all_keys = ["sl_early", "be_after_tp1", "stop_in_profit", "tp1_final", "tp2_final", "tp3_final", "other"]
        total = sum(probs.get(k, 0) for k in all_keys)
        if abs(total - 1.0) > 0.15:
            return None

        # Применяем floor/cap
        validated = {}
        for key in all_keys:
            val = probs.get(key, 0)
            if val > 0:
                val = max(MIN_PROB_FLOOR, min(MAX_PROB_CAP, val))
            validated[key] = val

        # Ренормализация
        total = sum(validated.values())
        if total > 0:
            validated = {k: v / total for k, v in validated.items()}

        # Sanity checks - sl_early должен быть в разумных пределах
        total_sl = validated.get("sl_early", 0) + validated.get("be_after_tp1", 0) + validated.get("stop_in_profit", 0)
        if total_sl < 0.05 or total_sl > 0.90:
            return None

        return validated

    def _adapt_probs_to_targets(
        self,
        probs: Dict[str, float],
        n_targets: int,
        flags: List[str]
    ) -> Dict[str, float]:
        """Перераспределить probs под количество targets (V2)."""
        if n_targets >= 3:
            return probs

        adapted = probs.copy()

        if n_targets == 2:
            # TP3 → TP2
            adapted["tp2_final"] = probs.get("tp2_final", 0) + probs.get("tp3_final", 0)
            adapted["tp3_final"] = None
            flags.append("probs_redistributed_2tp")

        elif n_targets == 1:
            # TP2 + TP3 → TP1
            adapted["tp1_final"] = (
                probs.get("tp1_final", 0) +
                probs.get("tp2_final", 0) +
                probs.get("tp3_final", 0)
            )
            adapted["tp2_final"] = None
            adapted["tp3_final"] = None
            flags.append("probs_redistributed_1tp")

        return adapted

    def _normalize_weights(self, targets: List[Dict[str, Any]]) -> Optional[List[float]]:
        """Нормализовать веса targets."""
        weights = []
        for t in targets:
            pct = t.get("partial_close_pct", 0)
            if pct is None:
                pct = 100 / len(targets)  # Equal distribution
            weights.append(pct / 100.0)

        total = sum(weights)
        if total <= 0:
            return None

        if abs(total - 1.0) > 0.01:
            weights = [w / total for w in weights]

        return weights

    def _calculate_payouts(
        self,
        targets: List[Dict[str, Any]],
        weights: List[float],
        fees_r: float,
    ) -> Dict[str, float]:
        """Рассчитать payouts для каждого terminal outcome (V2)."""
        payouts = {}
        # .get() не защищает от явного None - нужна проверка
        rr1_raw = targets[0].get("rr")
        rr1 = rr1_raw if rr1_raw is not None else 1.5
        w1 = weights[0]

        # SL до TP1 = полный лосс
        payouts["sl_early"] = -1.0 - fees_r

        # BE после TP1 = профит от TP1, остальное 0
        payouts["be_after_tp1"] = (rr1 * w1) - fees_r

        # Stop in profit после TP1 = TP1 + ~0.5R на остаток
        # TODO: replace with empirical avg_r_stop_in_profit from Real EV
        payouts["stop_in_profit"] = (rr1 * w1) + STOP_IN_PROFIT_HEURISTIC_R * (1 - w1) - fees_r

        # TP1 final = только TP1
        payouts["tp1_final"] = (rr1 * w1) - fees_r

        # TP2 final = TP1 + TP2
        cumulative = rr1 * w1
        if len(targets) >= 2:
            rr2_raw = targets[1].get("rr")
            rr2 = rr2_raw if rr2_raw is not None else 2.0
            cumulative += rr2 * weights[1]
        payouts["tp2_final"] = cumulative - fees_r

        # TP3 final = TP1 + TP2 + TP3
        if len(targets) >= 3:
            rr3_raw = targets[2].get("rr")
            rr3 = rr3_raw if rr3_raw is not None else 3.0
            cumulative += rr3 * weights[2]
        payouts["tp3_final"] = cumulative - fees_r

        payouts["other"] = 0.0 - fees_r

        return payouts

    def _calculate_ev(self, probs: OutcomeProbs, payouts: Dict[str, float]) -> float:
        """Рассчитать EV (fees уже в payouts!)."""
        return (
            probs.sl_early * payouts["sl_early"] +
            probs.be_after_tp1 * payouts["be_after_tp1"] +
            probs.stop_in_profit * payouts["stop_in_profit"] +
            probs.tp1_final * payouts["tp1_final"] +
            probs.tp2_final * payouts["tp2_final"] +
            (probs.tp3_final or 0.0) * payouts.get("tp3_final", 0.0) +
            probs.other * payouts["other"]
        )
        # НЕТ + fees_r! Fees уже в payouts

    def _calculate_ev_after_tp1(
        self,
        probs: OutcomeProbs,
        payouts: Dict[str, float],
        w1: float,
    ) -> float:
        """
        Conditional EV оставшейся позиции (1-w1) после TP1.
        Риск = 0 (BE активен), апсайд = TP2/TP3.
        """
        # Вероятности УСЛОВНЫЕ (при условии что TP1 уже сработал)
        p_reach_tp1 = (
            probs.be_after_tp1 +
            probs.stop_in_profit +
            probs.tp1_final +
            probs.tp2_final +
            (probs.tp3_final or 0)
        )

        if p_reach_tp1 < 0.01:
            return 0.0

        # Conditional probs после TP1
        p_be_given_tp1 = probs.be_after_tp1 / p_reach_tp1
        p_sip_given_tp1 = probs.stop_in_profit / p_reach_tp1
        p_tp2_given_tp1 = probs.tp2_final / p_reach_tp1
        p_tp3_given_tp1 = (probs.tp3_final or 0) / p_reach_tp1

        # Payouts для ОСТАВШЕЙСЯ позиции
        remaining = 1 - w1
        if remaining <= 0.01:
            return 0.0

        ev_after = (
            p_be_given_tp1 * 0 +  # BE = 0R на остаток
            p_sip_given_tp1 * STOP_IN_PROFIT_HEURISTIC_R +  # ~0.5R
            p_tp2_given_tp1 * (payouts["tp2_final"] - payouts["tp1_final"]) / remaining +
            p_tp3_given_tp1 * (payouts.get("tp3_final", 0) - payouts["tp1_final"]) / remaining
        )
        return ev_after

    def _get_ev_grade(self, ev_r: float) -> str:
        """Получить буквенную оценку EV."""
        if ev_r >= 0.5:
            return "A"
        elif ev_r >= 0.2:
            return "B"
        elif ev_r >= 0:
            return "C"
        else:
            return "D"

    def _default_result(
        self,
        side: str,
        confidence: float,
        flags: List[str]
    ) -> Tuple[OutcomeProbs, EVMetrics]:
        """Вернуть дефолтный результат при ошибке."""
        defaults = DEFAULT_PROBS_LONG if side.lower() == "long" else DEFAULT_PROBS_SHORT

        probs = OutcomeProbs(
            sl_early=defaults["sl_early"],
            be_after_tp1=defaults["be_after_tp1"],
            stop_in_profit=defaults["stop_in_profit"],
            tp1_final=defaults["tp1_final"],
            tp2_final=defaults["tp2_final"],
            tp3_final=defaults["tp3_final"],
            other=defaults["other"],
            source="default",
            sample_size=0,
            n_targets=0,
            flags=flags,
        )

        metrics = EVMetrics(
            ev_r=0.0,
            ev_r_after_tp1=0.0,
            fees_r=DEFAULT_FEES_R,
            ev_grade="D",
            scenario_score=0.4 * confidence,
            n_targets=0,
            flags=flags,
        )

        return probs, metrics


# Singleton instance
ev_calculator = EVCalculator()
