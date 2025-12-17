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

# Default outcome probabilities (terminal outcomes)
DEFAULT_PROBS_LONG = {
    "sl": 0.40,
    "tp1": 0.30,
    "tp2": 0.18,
    "tp3": 0.07,
    "other": 0.05,
}
DEFAULT_PROBS_SHORT = {
    "sl": 0.42,
    "tp1": 0.28,
    "tp2": 0.17,
    "tp3": 0.07,
    "other": 0.06,
}

# Dirichlet prior strength (как будто N виртуальных сделок)
PRIOR_STRENGTH = 6

# Minimum trades for reliable probabilities
MIN_TRADES_FOR_PROBS = 30

# Default fees in R (conservative)
DEFAULT_FEES_R = 0.15

# Sanity check thresholds
MIN_PROB_FLOOR = 0.01
MAX_PROB_CAP = 0.95


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class OutcomeProbs:
    """Вероятности terminal outcomes."""
    sl: float
    tp1: float
    tp2: Optional[float]
    tp3: Optional[float]
    other: float
    source: str  # "learning" | "llm" | "default"
    sample_size: int
    n_targets: int
    flags: List[str]


@dataclass
class EVMetrics:
    """Результат EV расчёта."""
    ev_r: float           # Net EV (с учётом fees)
    ev_r_gross: float     # Gross EV (без fees)
    fees_r: float         # Комиссии в R
    ev_grade: str         # A/B/C/D
    scenario_score: float # Normalized score
    n_targets: int
    flags: List[str]


# =============================================================================
# EV CALCULATOR
# =============================================================================

class EVCalculator:
    """
    Калькулятор Expected Value для сценариев.

    Формула:
    EV_R = Σ(P_TPk * payout_TPk) + P_SL * payout_SL + P_OTHER * payout_OTHER

    Где payouts кумулятивные:
    - payout_tp1 = RR1 * w1 - fees_r
    - payout_tp2 = RR1 * w1 + RR2 * w2 - fees_r
    - payout_tp3 = RR1 * w1 + RR2 * w2 + RR3 * w3 - fees_r
    - payout_sl = -1.0 - fees_r
    - payout_other = avg_pnl_r_other - fees_r
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
        payouts = self._calculate_payouts(targets, weights, fees_r, probs)

        # 4. Рассчитываем EV
        ev_r_gross = self._calculate_ev_gross(probs, payouts, fees_r)
        ev_r = ev_r_gross - fees_r  # Net EV

        # 5. Sanity checks
        if ev_r > 2.5:
            flags.append("fantasy_ev")
        if fees_r > 0.30:
            flags.append("high_fees_impact")

        # 6. EV Grade
        ev_grade = self._get_ev_grade(ev_r)

        # 7. Scenario Score (clamp EV для нормализации)
        ev_clamped = max(-1.0, min(1.0, ev_r))
        scenario_score = 0.6 * ev_clamped + 0.4 * confidence

        metrics = EVMetrics(
            ev_r=round(ev_r, 4),
            ev_r_gross=round(ev_r_gross, 4),
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
        """Получить outcome probs с fallback."""
        side_lower = side.lower()
        flags = []

        # 1. Пробуем Learning Module
        if archetype:
            stats = await self._get_archetype_stats(
                session, archetype, side_lower, timeframe, volatility_regime
            )
            if stats and stats.total_trades >= MIN_TRADES_FOR_PROBS:
                probs = self._dirichlet_smooth(stats, side_lower)
                probs = self._adapt_probs_to_targets(probs, n_targets, flags)
                return OutcomeProbs(
                    sl=probs["sl"],
                    tp1=probs["tp1"],
                    tp2=probs.get("tp2"),
                    tp3=probs.get("tp3"),
                    other=probs["other"],
                    source="learning",
                    sample_size=stats.total_trades,
                    n_targets=n_targets,
                    flags=flags,
                )

        # 2. Пробуем LLM probs
        if llm_probs:
            validated = self._validate_llm_probs(llm_probs)
            if validated:
                validated = self._adapt_probs_to_targets(validated, n_targets, flags)
                return OutcomeProbs(
                    sl=validated["sl"],
                    tp1=validated["tp1"],
                    tp2=validated.get("tp2"),
                    tp3=validated.get("tp3"),
                    other=validated["other"],
                    source="llm",
                    sample_size=0,
                    n_targets=n_targets,
                    flags=flags,
                )
            else:
                flags.append("llm_probs_rejected")

        # 3. Defaults
        defaults = DEFAULT_PROBS_LONG if side_lower == "long" else DEFAULT_PROBS_SHORT
        adapted = self._adapt_probs_to_targets(defaults.copy(), n_targets, flags)
        flags.append("using_defaults")

        return OutcomeProbs(
            sl=adapted["sl"],
            tp1=adapted["tp1"],
            tp2=adapted.get("tp2"),
            tp3=adapted.get("tp3"),
            other=adapted["other"],
            source="default",
            sample_size=0,
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

    def _dirichlet_smooth(self, stats: ArchetypeStats, side: str) -> Dict[str, float]:
        """
        Применить Dirichlet smoothing к counts.

        P_i = (count_i + α_i) / (N + Σα)
        где α_i = default_i * PRIOR_STRENGTH
        """
        defaults = DEFAULT_PROBS_LONG if side == "long" else DEFAULT_PROBS_SHORT
        alpha = {k: v * PRIOR_STRENGTH for k, v in defaults.items()}

        counts = {
            "sl": stats.exit_sl_count,
            "tp1": stats.exit_tp1_count,
            "tp2": stats.exit_tp2_count,
            "tp3": stats.exit_tp3_count,
            "other": stats.exit_other_count,
        }

        N = sum(counts.values())
        sum_alpha = PRIOR_STRENGTH

        probs = {}
        for key in ["sl", "tp1", "tp2", "tp3", "other"]:
            probs[key] = (counts[key] + alpha[key]) / (N + sum_alpha)

        return probs

    def _validate_llm_probs(self, probs: Dict[str, float]) -> Optional[Dict[str, float]]:
        """Валидация LLM probs."""
        required = ["sl", "tp1", "other"]
        for key in required:
            if key not in probs:
                return None

        # Проверяем сумму
        total = sum(probs.get(k, 0) for k in ["sl", "tp1", "tp2", "tp3", "other"])
        if abs(total - 1.0) > 0.1:
            return None

        # Применяем floor/cap
        validated = {}
        for key in ["sl", "tp1", "tp2", "tp3", "other"]:
            val = probs.get(key, 0)
            if val > 0:
                val = max(MIN_PROB_FLOOR, min(MAX_PROB_CAP, val))
            validated[key] = val

        # Ренормализация
        total = sum(validated.values())
        if total > 0:
            validated = {k: v / total for k, v in validated.items()}

        # Sanity checks
        if validated["sl"] < 0.05 or validated["sl"] > 0.90:
            return None

        return validated

    def _adapt_probs_to_targets(
        self,
        probs: Dict[str, float],
        n_targets: int,
        flags: List[str]
    ) -> Dict[str, float]:
        """Перераспределить probs под количество targets."""
        if n_targets >= 3:
            return probs

        adapted = probs.copy()

        if n_targets == 2:
            # TP3 → TP2
            adapted["tp2"] = probs.get("tp2", 0) + probs.get("tp3", 0)
            adapted["tp3"] = None
            flags.append("probs_redistributed_2tp")

        elif n_targets == 1:
            # TP2 + TP3 → TP1
            adapted["tp1"] = (
                probs.get("tp1", 0) +
                probs.get("tp2", 0) +
                probs.get("tp3", 0)
            )
            adapted["tp2"] = None
            adapted["tp3"] = None
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
        probs: OutcomeProbs,
    ) -> Dict[str, float]:
        """Рассчитать payouts для каждого terminal outcome."""
        n = len(targets)
        payouts = {}

        # Кумулятивные payouts
        cumulative = 0.0
        for i in range(n):
            rr = targets[i].get("rr", 1.5)
            w = weights[i]
            cumulative += rr * w
            payouts[f"tp{i + 1}"] = cumulative - fees_r

        payouts["sl"] = -1.0 - fees_r
        payouts["other"] = 0.0 - fees_r  # avg_pnl_r_other можно добавить

        return payouts

    def _calculate_ev_gross(
        self,
        probs: OutcomeProbs,
        payouts: Dict[str, float],
        fees_r: float,
    ) -> float:
        """Рассчитать gross EV (без вычитания fees)."""
        ev = probs.sl * payouts["sl"]
        ev += probs.other * payouts["other"]

        if probs.tp1:
            ev += probs.tp1 * payouts.get("tp1", 0)
        if probs.tp2:
            ev += probs.tp2 * payouts.get("tp2", 0)
        if probs.tp3:
            ev += probs.tp3 * payouts.get("tp3", 0)

        return ev + fees_r  # Add back fees to get gross

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
            sl=defaults["sl"],
            tp1=defaults["tp1"],
            tp2=defaults["tp2"],
            tp3=defaults["tp3"],
            other=defaults["other"],
            source="default",
            sample_size=0,
            n_targets=0,
            flags=flags,
        )

        metrics = EVMetrics(
            ev_r=0.0,
            ev_r_gross=0.0,
            fees_r=DEFAULT_FEES_R,
            ev_grade="D",
            scenario_score=0.4 * confidence,
            n_targets=0,
            flags=flags,
        )

        return probs, metrics


# Singleton instance
ev_calculator = EVCalculator()
