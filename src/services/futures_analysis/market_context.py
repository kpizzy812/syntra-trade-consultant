# coding: utf-8
"""
Market Context Analyzer - анализ рыночного контекста.

Определяет trend, phase, sentiment, volatility, bias.
"""
from typing import Any, Dict, Optional

import pandas as pd
from loguru import logger

from src.services.session_detector import session_detector
from src.services.volume_analyzer import volume_analyzer
from src.services.trading_modes import ModeConfig

from .constants import BIAS_CAPS


class MarketContextAnalyzer:
    """
    Анализ рыночного контекста для торговых сценариев.
    """

    def analyze(
        self,
        price: float,
        klines: pd.DataFrame,
        indicators: Dict,
        funding: Optional[Dict],
        oi: Optional[Dict],
        ls_ratio: Optional[Dict],
        fear_greed: Optional[Dict],
        mtf_data: Dict[str, pd.DataFrame],
        timeframe: str = "4h",
        mode_config: Optional[ModeConfig] = None
    ) -> Dict[str, Any]:
        """
        Определить текущий контекст рынка.

        Returns:
            {
                "trend": "bullish" | "bearish" | "sideways",
                "phase": "continuation" | "reversal" | "accumulation" | "distribution",
                "sentiment": "extreme_greed" | "greed" | "neutral" | "fear" | "extreme_fear",
                "volatility": "very_low" | "low" | "medium" | "high" | "very_high",
                "bias": "long" | "short" | "neutral",
                "strength": 0.0 - 1.0
            }
        """
        context = {}

        # === TREND DETECTION ===
        ema_20 = indicators.get("ema_20")
        ema_50 = indicators.get("ema_50")
        _sma_200 = indicators.get("sma_200")  # Reserved for future use

        if ema_20 and ema_50:
            if price > ema_20 > ema_50:
                context["trend"] = "bullish"
            elif price < ema_20 < ema_50:
                context["trend"] = "bearish"
            else:
                context["trend"] = "sideways"
        else:
            context["trend"] = "unknown"

        # === PHASE DETECTION ===
        rsi = indicators.get("rsi", 50)
        adx = indicators.get("adx", 20)

        if adx and adx > 25:
            # Strong trend
            if rsi > 70:
                context["phase"] = "distribution"  # Overbought in uptrend
            elif rsi < 30:
                context["phase"] = "accumulation"  # Oversold in downtrend
            else:
                context["phase"] = "continuation"  # Trend continues
        else:
            # Weak trend / range
            if rsi > 60:
                context["phase"] = "distribution"
            elif rsi < 40:
                context["phase"] = "accumulation"
            else:
                context["phase"] = "consolidation"

        # === SENTIMENT (Fear & Greed) ===
        if fear_greed:
            fg_value = fear_greed.get("value", 50)
            if fg_value >= 75:
                context["sentiment"] = "extreme_greed"
            elif fg_value >= 60:
                context["sentiment"] = "greed"
            elif fg_value >= 40:
                context["sentiment"] = "neutral"
            elif fg_value >= 25:
                context["sentiment"] = "fear"
            else:
                context["sentiment"] = "extreme_fear"
        else:
            context["sentiment"] = "unknown"

        # === VOLATILITY ===
        atr_pct = indicators.get("atr_percent", 2.0)
        context["volatility"] = indicators.get("volatility", "medium")
        context["atr_percent"] = atr_pct  # Числовое значение для LLM валидатора

        # === BIAS CALCULATION с CAPS и LOGGING ===
        bias_components, bias_score = self._calculate_bias(
            context=context,
            rsi=rsi,
            adx=adx,
            fear_greed=fear_greed,
            funding=funding,
            ls_ratio=ls_ratio,
            timeframe=timeframe,
            mode_config=mode_config
        )

        # Log bias components для отладки
        logger.info(
            f"📊 Bias components: {bias_components} → total={bias_score}"
        )

        # Determine final bias
        if bias_score >= 2:
            context["bias"] = "long"
            context["strength"] = min(abs(bias_score) / 5.0, 1.0)
        elif bias_score <= -2:
            context["bias"] = "short"
            context["strength"] = min(abs(bias_score) / 5.0, 1.0)
        else:
            context["bias"] = "neutral"
            context["strength"] = 0.3

        # Store bias components in context for transparency
        context["bias_components"] = bias_components

        # === ADDITIONAL CONTEXT ===
        context["rsi"] = round(rsi, 1) if rsi else None
        context["funding_rate_pct"] = round(funding.get("funding_rate_pct", 0), 4) if funding else None
        context["long_short_ratio"] = round(ls_ratio.get("long_short_ratio", 1.0), 2) if ls_ratio else None

        # === SESSION DETECTION ===
        session_info = session_detector.get_current_session()
        context["session"] = {
            "current": session_info["session_name"],
            "is_overlap": session_info["is_overlap"],
            "volatility_expected": session_info["volatility_expected"],
            "recommendation": session_detector.get_session_recommendation(session_info)
        }

        # === VOLUME ANALYSIS ===
        volume_analysis = volume_analyzer.analyze(klines)
        if volume_analysis:
            context["volume"] = {
                "relative_volume": volume_analysis.get("relative_volume", 1.0),
                "classification": volume_analysis.get("volume_classification", "normal"),
                "trend": volume_analysis.get("volume_trend", "stable"),
                "spike": volume_analysis.get("volume_spike", False)
            }

        return context

    def _calculate_bias(
        self,
        context: Dict,
        rsi: float,
        adx: float,
        fear_greed: Optional[Dict],
        funding: Optional[Dict],
        ls_ratio: Optional[Dict],
        timeframe: str,
        mode_config: Optional[ModeConfig]
    ) -> tuple[Dict[str, int], int]:
        """
        Рассчитать bias score с caps по каждому фактору.

        Returns:
            (bias_components, total_bias_score)
        """
        bias_components = {}
        bias_score = 0

        def apply_cap(value: int, factor: str) -> int:
            cap = BIAS_CAPS.get(factor, 3)
            return max(-cap, min(cap, value))

        # 1. Trend bias (capped)
        trend_contribution = 0
        if context["trend"] == "bullish":
            trend_contribution = 2
        elif context["trend"] == "bearish":
            trend_contribution = -2
        trend_contribution = apply_cap(trend_contribution, "trend")
        bias_components["trend"] = trend_contribution
        bias_score += trend_contribution

        # 2. RSI bias (capped)
        rsi_contribution = 0
        if rsi and rsi < 30:
            rsi_contribution = 1  # Oversold = bullish bias
        elif rsi and rsi > 70:
            rsi_contribution = -1  # Overbought = bearish bias
        rsi_contribution = apply_cap(rsi_contribution, "rsi")
        bias_components["rsi"] = rsi_contribution
        bias_score += rsi_contribution

        # 3. Fear & Greed bias (contrarian) - ДИНАМИЧЕСКИЙ ВЕС! (capped)
        fg_contribution = 0
        if fear_greed:
            fg_value = fear_greed.get("value", 50)

            # DYNAMIC WEIGHT: зависит от таймфрейма и тренда
            base_weight = 1.0

            # Вес по таймфрейму
            if timeframe in ["1d", "1w"]:
                tf_multiplier = 2.0  # Для больших TF вес выше
            elif timeframe in ["4h", "6h", "8h", "12h"]:
                tf_multiplier = 1.5  # Для средних TF средний вес
            else:
                tf_multiplier = 0.5  # Для малых TF (1h, 15m) вес ниже - часто шум!

            # Снижаем вес на сильном тренде (contrarian опаснее)
            if adx and adx > 35:
                trend_multiplier = 0.5  # На сильном тренде не торгуем против
            elif adx and adx > 25:
                trend_multiplier = 0.75
            else:
                trend_multiplier = 1.0

            final_weight = base_weight * tf_multiplier * trend_multiplier

            # Применяем вес
            if fg_value < 20:  # Extreme Fear = BUY OPPORTUNITY
                fg_contribution = round(3 * final_weight)
            elif fg_value < 30:  # Fear
                fg_contribution = round(2 * final_weight)
            elif fg_value > 80:  # Extreme Greed = SELL SIGNAL
                fg_contribution = -round(3 * final_weight)
            elif fg_value > 70:  # Greed
                fg_contribution = -round(2 * final_weight)

        fg_contribution = apply_cap(fg_contribution, "fear_greed")
        bias_components["fear_greed"] = fg_contribution
        bias_score += fg_contribution

        # 4. Funding bias (contrarian, capped)
        funding_threshold = mode_config.funding_extreme if mode_config else 0.001
        funding_contribution = 0
        if funding:
            funding_rate = funding.get("funding_rate_pct", 0)
            # DEBUG: логируем raw значения funding
            passes = abs(funding_rate) > funding_threshold
            logger.debug(
                f"🔍 Funding DEBUG: raw={funding}, "
                f"funding_rate_pct={funding_rate}, "
                f"threshold={funding_threshold}, passes={passes}"
            )
            if funding_rate > funding_threshold:  # High positive funding
                funding_contribution = -1  # Too many longs = bearish bias
            elif funding_rate < -funding_threshold:  # High negative funding
                funding_contribution = 1  # Too many shorts = bullish bias
        else:
            logger.warning("⚠️ Funding data is None in bias calculation!")
        funding_contribution = apply_cap(funding_contribution, "funding")
        bias_components["funding"] = funding_contribution
        bias_score += funding_contribution

        # 5. Long/Short ratio bias (contrarian, capped)
        ls_contribution = 0
        if ls_ratio:
            ratio = ls_ratio.get("long_short_ratio", 1.0)
            long_pct = ls_ratio.get("long_account", 0)
            # DEBUG: логируем raw значения ls_ratio
            logger.debug(
                f"🔍 LS Ratio DEBUG: long_short_ratio={ratio}, "
                f"long_account={long_pct}, threshold=2.0, "
                f"passes_long={ratio > 2.0}, passes_short={ratio < 0.5}"
            )
            if ratio > 2.0:  # Too many longs
                ls_contribution = -1
            elif ratio < 0.5:  # Too many shorts
                ls_contribution = 1
        else:
            logger.warning("⚠️ LS Ratio data is None in bias calculation!")
        ls_contribution = apply_cap(ls_contribution, "ls_ratio")
        bias_components["ls_ratio"] = ls_contribution
        bias_score += ls_contribution

        return bias_components, bias_score
