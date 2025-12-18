"""
Market Data Enricher — обогащение market_data для LLM.

5 калькуляторов:
1. calculate_positioning_trends() — funding/LS ratio trends + crowding
2. detect_stop_hunt() — детекция свипов (только на NEAR уровнях)
3. calculate_volatility_context() — ATR vs baseline
4. calculate_levels_meta() — touches/age уровней
5. calculate_oi_analysis() — Open Interest анализ
"""

import logging
from statistics import median, stdev, mean
from typing import Dict, List, Optional, Any

import pandas as pd

logger = logging.getLogger(__name__)


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Ограничить значение в пределах [min_val, max_val]."""
    return max(min_val, min(max_val, value))


class MarketDataEnricher:
    """Обогащение market_data дополнительной аналитикой для LLM."""

    # Маппинг таймфреймов в часы
    TF_HOURS = {
        "15m": 0.25,
        "1h": 1.0,
        "4h": 4.0,
        "1d": 24.0,
        "1w": 168.0,
    }

    # Свечей в день по таймфреймам
    CANDLES_PER_DAY = {
        "15m": 96,
        "1h": 24,
        "4h": 6,
        "1d": 1,
    }

    def enrich(
        self,
        klines: pd.DataFrame,
        funding_history: Optional[List[Dict]],
        ls_ratio_history: Optional[List[Dict]],
        oi_history: Optional[List[Dict]],
        support_near: List[float],
        resistance_near: List[float],
        current_price: float,
        current_atr: float,
        timeframe: str,
        mode_config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Главный метод — собирает все 5 блоков enrichment.

        Returns:
            Dict с ключами: positioning, microstructure, volatility_context,
                           levels_meta, oi
        """
        mode_config = mode_config or {}
        tf_hours = self.TF_HOURS.get(timeframe, 4.0)

        # 1. Positioning trends
        positioning = self.calculate_positioning_trends(
            funding_history=funding_history,
            ls_ratio_history=ls_ratio_history,
            mode_config=mode_config,
        )

        # 2. Stop-hunt detection
        microstructure = self.detect_stop_hunt(
            klines=klines,
            support_near=support_near,
            resistance_near=resistance_near,
            current_price=current_price,
            current_atr=current_atr,
        )

        # 3. Volatility context
        volatility_context = self.calculate_volatility_context(
            klines=klines,
            current_atr=current_atr,
            timeframe=timeframe,
        )

        # 4. Levels meta
        levels_meta = self.calculate_levels_meta(
            klines=klines,
            support_near=support_near,
            resistance_near=resistance_near,
            tf_hours=tf_hours,
        )

        # 5. OI analysis
        current_oi = oi_history[-1]["openInterest"] if oi_history else 0
        oi = self.calculate_oi_analysis(
            oi_history=oi_history,
            current_oi=current_oi,
        )

        return {
            "positioning": positioning,
            "microstructure": microstructure,
            "volatility_context": volatility_context,
            "levels_meta": levels_meta,
            "oi": oi,
        }

    # -------------------------------------------------------------------------
    # 1. POSITIONING TRENDS
    # -------------------------------------------------------------------------
    def calculate_positioning_trends(
        self,
        funding_history: Optional[List[Dict]],
        ls_ratio_history: Optional[List[Dict]],
        mode_config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Рассчитать тренды позиционирования.

        Returns:
            {
                "funding_trend_24h": "rising|falling|flat|unknown",
                "ls_ratio_trend_12h": "increasing_longs|increasing_shorts|neutral|unknown",
                "crowding_score": 0.0-1.0,
                "crowding_side": "long|short|none"
            }
        """
        mode_config = mode_config or {}

        # Funding trend
        funding_trend = self._calculate_funding_trend(funding_history)

        # LS ratio trend
        ls_trend = self._calculate_ls_trend(ls_ratio_history)

        # Crowding score & side
        crowding_score, crowding_side = self._calculate_crowding(
            funding_history=funding_history,
            ls_ratio_history=ls_ratio_history,
            mode_config=mode_config,
        )

        return {
            "funding_trend_24h": funding_trend,
            "ls_ratio_trend_12h": ls_trend,
            "crowding_score": crowding_score,
            "crowding_side": crowding_side,
        }

    def _calculate_funding_trend(
        self,
        funding_history: Optional[List[Dict]],
    ) -> str:
        """Рассчитать тренд funding rate за 24h."""
        if not funding_history or len(funding_history) < 4:
            return "unknown"

        try:
            # Берём последние 12 точек (или меньше)
            values = [
                float(f.get("funding_rate", 0) or f.get("fundingRate", 0))
                for f in funding_history[-12:]
            ]

            if len(values) < 2:
                return "unknown"

            # Считаем slope через median of diffs
            diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
            slope = median(diffs)

            # Порог в rate (0.00005 ≈ 0.005%)
            eps = 0.00005
            if slope > eps:
                return "rising"
            elif slope < -eps:
                return "falling"
            else:
                return "flat"

        except Exception as e:
            logger.warning(f"Error calculating funding trend: {e}")
            return "unknown"

    def _calculate_ls_trend(
        self,
        ls_ratio_history: Optional[List[Dict]],
    ) -> str:
        """Рассчитать тренд LS ratio за 12h."""
        if not ls_ratio_history or len(ls_ratio_history) < 4:
            return "unknown"

        try:
            # Нормализуем ratio
            ratios = [self._normalize_ls_ratio(item) for item in ls_ratio_history[-12:]]

            if len(ratios) < 2:
                return "unknown"

            first_ratio = ratios[0]
            last_ratio = ratios[-1]
            diff = last_ratio - first_ratio

            # Порог изменения
            if diff > 0.1:  # +0.1 = увеличение лонгов
                return "increasing_longs"
            elif diff < -0.1:  # -0.1 = увеличение шортов
                return "increasing_shorts"
            else:
                return "neutral"

        except Exception as e:
            logger.warning(f"Error calculating LS trend: {e}")
            return "unknown"

    def _normalize_ls_ratio(self, data: Dict) -> float:
        """
        Приводим к единому формату: >1 = больше лонгов, <1 = больше шортов.
        """
        try:
            if "long_short_ratio" in data:
                return float(data["long_short_ratio"])
            if "longShortRatio" in data:
                return float(data["longShortRatio"])
            if "buyRatio" in data and "sellRatio" in data:
                buy = float(data["buyRatio"])
                sell = float(data["sellRatio"])
                return buy / sell if sell > 0 else 1.0
            return 1.0
        except (ValueError, TypeError):
            return 1.0

    def _calculate_crowding(
        self,
        funding_history: Optional[List[Dict]],
        ls_ratio_history: Optional[List[Dict]],
        mode_config: Optional[Dict] = None,
    ) -> tuple:
        """
        Рассчитать crowding score и side.

        Returns:
            (crowding_score, crowding_side)
        """
        mode_config = mode_config or {}

        # Текущий funding rate
        funding_rate = 0.0
        if funding_history:
            last_funding = funding_history[-1]
            funding_rate = float(
                last_funding.get("funding_rate", 0) or
                last_funding.get("fundingRate", 0)
            )

        # Текущий LS ratio
        ls_ratio = 1.0
        if ls_ratio_history:
            ls_ratio = self._normalize_ls_ratio(ls_ratio_history[-1])

        # funding_extreme from mode config (risk philosophy)
        funding_extreme = mode_config.funding_extreme

        # Компоненты
        ls_component = clamp(abs(ls_ratio - 1.0) / 1.0, 0, 1)
        fund_component = clamp(abs(funding_rate) / funding_extreme, 0, 1)

        # Финальный score
        crowding_score = round(0.6 * ls_component + 0.4 * fund_component, 2)

        # Side (оба сигнала должны согласоваться)
        if funding_rate > 0.0003 and ls_ratio > 1.2:
            crowding_side = "long"
        elif funding_rate < -0.0003 and ls_ratio < 0.8:
            crowding_side = "short"
        else:
            crowding_side = "none"

        return crowding_score, crowding_side

    # -------------------------------------------------------------------------
    # 2. STOP-HUNT DETECTION
    # -------------------------------------------------------------------------
    def detect_stop_hunt(
        self,
        klines: pd.DataFrame,
        support_near: List[float],
        resistance_near: List[float],
        current_price: float,
        current_atr: float,
    ) -> Dict[str, Any]:
        """
        Детектировать stop-hunt / sweep.

        Проверяем последние 5 свечей, возвращаем самый сильный сигнал.
        Только на NEAR уровнях!

        Returns:
            {
                "stop_hunt": {"detected": bool, "side": str, "strength": float},
                "reclaim_level": float|None
            }
        """
        if klines is None or len(klines) < 2:
            return {
                "stop_hunt": {"detected": False, "side": None, "strength": 0},
                "reclaim_level": None,
            }

        # tiny_buffer от ATR, не от цены
        tiny_buffer = max(current_price * 0.001, current_atr * 0.15)
        window = 5

        best_signal = {
            "detected": False,
            "side": None,
            "strength": 0,
            "reclaim_level": None,
        }

        for i in range(-window, 0):
            if abs(i) > len(klines):
                continue

            candle = klines.iloc[i]
            # Защита от body=0 / doji
            body = max(abs(candle["close"] - candle["open"]), 1e-9)
            lower_wick = min(candle["open"], candle["close"]) - candle["low"]
            upper_wick = candle["high"] - max(candle["open"], candle["close"])

            # DOWN SWEEP: проверяем support_near
            for level in support_near:
                # Вариант 1: reclaim внутри свечи
                if (candle["low"] < level - tiny_buffer and
                    candle["close"] > level and
                    lower_wick > body * 2):
                    strength = self._calc_strength(lower_wick, body, i, True)
                    if strength > best_signal["strength"]:
                        best_signal = {
                            "detected": True,
                            "side": "down_sweep",
                            "strength": strength,
                            "reclaim_level": level,
                        }

                # Вариант 2: reclaim на следующей свече
                elif (candle["low"] < level - tiny_buffer and
                      candle["close"] < level and
                      i < -1):
                    next_candle = klines.iloc[i + 1]
                    if next_candle["close"] > level:
                        strength = self._calc_strength(lower_wick, body, i, False)
                        if strength > best_signal["strength"]:
                            best_signal = {
                                "detected": True,
                                "side": "down_sweep",
                                "strength": strength,
                                "reclaim_level": level,
                            }

            # UP SWEEP: проверяем resistance_near
            for level in resistance_near:
                if (candle["high"] > level + tiny_buffer and
                    candle["close"] < level and
                    upper_wick > body * 2):
                    strength = self._calc_strength(upper_wick, body, i, True)
                    if strength > best_signal["strength"]:
                        best_signal = {
                            "detected": True,
                            "side": "up_sweep",
                            "strength": strength,
                            "reclaim_level": level,
                        }

                # Reclaim на следующей свече
                elif (candle["high"] > level + tiny_buffer and
                      candle["close"] > level and
                      i < -1):
                    next_candle = klines.iloc[i + 1]
                    if next_candle["close"] < level:
                        strength = self._calc_strength(upper_wick, body, i, False)
                        if strength > best_signal["strength"]:
                            best_signal = {
                                "detected": True,
                                "side": "up_sweep",
                                "strength": strength,
                                "reclaim_level": level,
                            }

        return {
            "stop_hunt": {
                "detected": best_signal["detected"],
                "side": best_signal["side"],
                "strength": best_signal["strength"],
            },
            "reclaim_level": best_signal["reclaim_level"],
        }

    def _calc_strength(
        self,
        wick: float,
        body: float,
        recency_idx: int,
        reclaim_same_candle: bool = True,
    ) -> float:
        """
        Рассчитать силу stop-hunt сигнала.

        recency_idx: -1 = последняя свеча (сильнее), -5 = старая (слабее)
        reclaim_same_candle: False = -30% penalty
        """
        wick_ratio = min(wick / body, 5) / 5  # 0-1
        recency_bonus = (6 + recency_idx) / 5  # -1 → 1.0, -5 → 0.2
        reclaim_penalty = 1.0 if reclaim_same_candle else 0.7
        return round(wick_ratio * recency_bonus * reclaim_penalty, 2)

    # -------------------------------------------------------------------------
    # 3. VOLATILITY CONTEXT
    # -------------------------------------------------------------------------
    def calculate_volatility_context(
        self,
        klines: pd.DataFrame,
        current_atr: float,
        timeframe: str,
    ) -> Dict[str, str]:
        """
        Рассчитать контекст волатильности vs 30d baseline.

        Returns:
            {
                "atr_vs_30d": "low|normal|high|extreme",
                "volatility_trend": "expanding|stable|contracting"
            }
        """
        if klines is None or len(klines) < 14 or current_atr <= 0:
            return {"atr_vs_30d": "normal", "volatility_trend": "stable"}

        try:
            # Адаптивный лимит: min(30d в свечах, 200)
            cpd = self.CANDLES_PER_DAY.get(timeframe, 6)
            baseline_candles = min(cpd * 30, 200, len(klines))

            # Считаем ATR серию
            atr_series = self._calculate_atr_series(klines.iloc[-baseline_candles:])

            if not atr_series or len(atr_series) < 5:
                return {"atr_vs_30d": "normal", "volatility_trend": "stable"}

            avg_atr = mean(atr_series)

            # Ratio
            ratio = current_atr / avg_atr if avg_atr > 0 else 1.0

            if ratio < 0.6:
                atr_vs_30d = "low"
            elif ratio < 1.2:
                atr_vs_30d = "normal"
            elif ratio < 2.0:
                atr_vs_30d = "high"
            else:
                atr_vs_30d = "extreme"

            # Trend: last 5 vs prev 5
            recent_5 = mean(atr_series[-5:])
            prev_5 = mean(atr_series[-10:-5]) if len(atr_series) >= 10 else recent_5

            if recent_5 > prev_5 * 1.15:
                volatility_trend = "expanding"
            elif recent_5 < prev_5 * 0.85:
                volatility_trend = "contracting"
            else:
                volatility_trend = "stable"

            return {"atr_vs_30d": atr_vs_30d, "volatility_trend": volatility_trend}

        except Exception as e:
            logger.warning(f"Error calculating volatility context: {e}")
            return {"atr_vs_30d": "normal", "volatility_trend": "stable"}

    def _calculate_atr_series(
        self,
        klines: pd.DataFrame,
        period: int = 14,
    ) -> List[float]:
        """Рассчитать серию ATR значений."""
        if len(klines) < period:
            return []

        atr_values = []
        for i in range(period, len(klines)):
            window = klines.iloc[i - period:i]
            high = window["high"].max()
            low = window["low"].min()
            prev_close = klines.iloc[i - 1]["close"]

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )
            atr_values.append(tr)

        return atr_values

    # -------------------------------------------------------------------------
    # 4. LEVELS META
    # -------------------------------------------------------------------------
    def calculate_levels_meta(
        self,
        klines: pd.DataFrame,
        support_near: List[float],
        resistance_near: List[float],
        tf_hours: float,
    ) -> Dict[str, List[Dict]]:
        """
        Рассчитать метаданные уровней (touches, age).

        Returns:
            {
                "support_near": [{"price": float, "touches": int, "age_hours": int}],
                "resistance_near": [{"price": float, "touches": int, "age_hours": int}]
            }
        """
        if klines is None or len(klines) == 0:
            return {"support_near": [], "resistance_near": []}

        result = {"support_near": [], "resistance_near": []}

        for level in support_near:
            touches = self._count_touches(klines, level)
            age = self._find_last_touch_age(klines, level, tf_hours)
            result["support_near"].append({
                "price": round(level, 2),
                "touches": touches,
                "age_hours": age,
            })

        for level in resistance_near:
            touches = self._count_touches(klines, level)
            age = self._find_last_touch_age(klines, level, tf_hours)
            result["resistance_near"].append({
                "price": round(level, 2),
                "touches": touches,
                "age_hours": age,
            })

        return result

    def _count_touches(
        self,
        klines: pd.DataFrame,
        level: float,
        tolerance: float = 0.002,
    ) -> int:
        """Подсчитать касания уровня."""
        level_range = level * tolerance
        touches = 0
        for _, candle in klines.iterrows():
            if candle["low"] <= level + level_range and candle["high"] >= level - level_range:
                touches += 1
        return touches

    def _find_last_touch_age(
        self,
        klines: pd.DataFrame,
        level: float,
        tf_hours: float,
        tolerance: float = 0.002,
    ) -> int:
        """
        Найти сколько часов прошло с ПОСЛЕДНЕГО касания.
        Freshness важнее, чем первое появление.
        """
        level_range = level * tolerance
        for i in range(len(klines) - 1, -1, -1):
            candle = klines.iloc[i]
            if candle["low"] <= level + level_range and candle["high"] >= level - level_range:
                return int((len(klines) - 1 - i) * tf_hours)
        return int(len(klines) * tf_hours)  # очень старый

    # -------------------------------------------------------------------------
    # 5. OI ANALYSIS
    # -------------------------------------------------------------------------
    def calculate_oi_analysis(
        self,
        oi_history: Optional[List[Dict]],
        current_oi: float,
    ) -> Dict[str, Any]:
        """
        Анализ Open Interest.

        Returns:
            {
                "current": float,
                "change_1h_pct": float,
                "change_4h_pct": float,
                "trend": "rising|falling|flat|unknown"
            }
        """
        if not oi_history or len(oi_history) < 4:
            return {
                "current": current_oi,
                "change_1h_pct": 0,
                "change_4h_pct": 0,
                "trend": "unknown",
            }

        try:
            # Сортируем по времени
            sorted_oi = sorted(oi_history, key=lambda x: x.get("timestamp", 0))
            values = [float(x.get("openInterest", 0)) for x in sorted_oi]

            current = values[-1]
            oi_1h_ago = values[-2] if len(values) >= 2 else current
            oi_4h_ago = values[-5] if len(values) >= 5 else values[0]

            # Защита от low base
            MIN_OI_BASE = 1000
            if oi_1h_ago < MIN_OI_BASE or oi_4h_ago < MIN_OI_BASE:
                return {
                    "current": current,
                    "change_1h_pct": 0,
                    "change_4h_pct": 0,
                    "trend": "unknown",
                }

            change_1h_pct = ((current - oi_1h_ago) / oi_1h_ago * 100)
            change_4h_pct = ((current - oi_4h_ago) / oi_4h_ago * 100)

            # Адаптивный порог
            if len(values) >= 5:
                diffs = [
                    abs(values[i + 1] - values[i]) / values[i] * 100
                    for i in range(len(values) - 1)
                    if values[i] > MIN_OI_BASE
                ]
                oi_std = stdev(diffs) if len(diffs) > 1 else 5.0
                threshold = max(5.0, 1.5 * oi_std)
            else:
                threshold = 5.0

            # Trend classification
            if change_4h_pct > threshold:
                trend = "rising"
            elif change_4h_pct < -threshold:
                trend = "falling"
            else:
                trend = "flat"

            return {
                "current": current,
                "change_1h_pct": round(change_1h_pct, 2),
                "change_4h_pct": round(change_4h_pct, 2),
                "trend": trend,
            }

        except Exception as e:
            logger.warning(f"Error calculating OI analysis: {e}")
            return {
                "current": current_oi,
                "change_1h_pct": 0,
                "change_4h_pct": 0,
                "trend": "unknown",
            }


# Singleton instance
market_data_enricher = MarketDataEnricher()
