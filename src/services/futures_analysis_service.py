# coding: utf-8
"""
Futures Analysis Service

Специализированный ИИ-движок для анализа фьючерсных контрактов и генерации
структурированных торговых сценариев с конкретными уровнями входа/выхода.

Используется для автоматизации трейдинга через API endpoint.

Возвращает:
- 2-3 сценария (bullish/bearish/neutral) с confidence scoring
- Конкретные уровни: entry, stop-loss, targets (TP1, TP2, TP3)
- RR calculation, leverage recommendations
- Structured reasoning (почему этот сценарий валидный)
- Market context (trend, phase, sentiment, volatility)
"""
import json
import time
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger

from src.services.binance_service import BinanceService
from src.services.bybit_service import bybit_service
from src.services.candlestick_patterns import CandlestickPatterns
from src.services.fear_greed_service import FearGreedService
from src.services.openai_service import OpenAIService
from src.services.price_levels_service import PriceLevelsService
from src.services.session_detector import session_detector
from src.services.technical_indicators import TechnicalIndicators
from src.services.volume_analyzer import volume_analyzer
from src.services.trading_modes import (
    ModeConfig,
    get_mode_config,
    build_mode_profile_block,
    get_mode_notes_schema,
)
from src.services.market_data_enricher import market_data_enricher

# Learning system integration
from src.learning import confidence_calibrator, sltp_optimizer, ev_calculator
from src.learning import (
    class_stats_analyzer,
    build_class_key,
    ClassKey,
    CONFIDENCE_MIN,
    CONFIDENCE_MAX,
)
from src.learning.constants import DEFAULT_WINDOW_DAYS
from src.database.engine import get_session_maker


# ==============================================================================
# FUTURES MODEL CONFIGURATION
# ==============================================================================
# Heavy model for scenario generation (deep analysis, best reasoning)
# Configured via config.py: MODEL_SCENARIO_GENERATOR (default: gpt-5.2)
from config.config import MODEL_SCENARIO_GENERATOR
FUTURES_MODEL = MODEL_SCENARIO_GENERATOR  # gpt-5.2 for best reasoning quality

# Bias factor caps (max contribution per factor)
BIAS_CAPS = {
    "trend": 3,        # max ±3 from trend
    "rsi": 2,          # max ±2 from RSI
    "fear_greed": 4,   # max ±4 from F&G (high weight on large TFs)
    "funding": 2,      # max ±2 from funding
    "ls_ratio": 2,     # max ±2 from long/short ratio
}

# Max distance from current price for entry zone (adaptive by timeframe)
MAX_ENTRY_DISTANCE_PCT_BY_TF = {
    "15m": 3.0,
    "1h": 5.0,
    "4h": 8.0,
    "1d": 15.0,
    "1w": 25.0,
}
MAX_ENTRY_DISTANCE_PCT_DEFAULT = 10.0  # fallback

# ATR multiplier for max entry distance (hybrid approach)
# entry_distance <= min(MAX_PCT_BY_TF, ATR * K / price * 100)
ATR_ENTRY_MULTIPLIER_BY_TF = {
    "15m": 2.0,
    "1h": 3.0,
    "4h": 5.0,
    "1d": 8.0,
    "1w": 12.0,
}
ATR_ENTRY_MULTIPLIER_DEFAULT = 5.0


def _filter_levels_by_distance(
    levels: List[float],
    current_price: float,
    max_distance_pct: float,
    side: str = "both"
) -> tuple[List[float], List[float]]:
    """
    Split price levels into near (actionable) and macro (context only).

    Args:
        levels: List of price levels
        current_price: Current market price
        max_distance_pct: Max % distance for "near" classification
        side: "long" (levels below), "short" (levels above), "both"

    Returns:
        (near_levels, macro_levels) - sorted lists
    """
    near = []
    macro = []

    for lvl in levels:
        if not lvl or lvl <= 0:
            continue

        dist_pct = abs(lvl - current_price) / current_price * 100

        # Side filter
        if side == "short" and lvl <= current_price:
            continue  # For short, we only want levels ABOVE current
        if side == "long" and lvl >= current_price:
            continue  # For long, we only want levels BELOW current

        # Distance filter
        if dist_pct <= max_distance_pct:
            near.append(round(lvl, 2))
        else:
            macro.append(round(lvl, 2))

    # Sort: near by proximity, macro by distance
    near = sorted(near, key=lambda x: abs(x - current_price))
    macro = sorted(macro, key=lambda x: abs(x - current_price))

    return near, macro


class FuturesAnalysisService:
    """
    Главный движок для анализа фьючерсов и генерации торговых сценариев

    Алгоритм:
    1. Собрать все данные (price, volume, funding, OI, liquidations, indicators)
    2. Определить market context (trend, phase, sentiment)
    3. Сгенерировать 2-3 сценария с confidence scoring
    4. Вернуть структурированный JSON для автоматизации
    """

    def __init__(self):
        """Initialize services"""
        self.bybit = bybit_service  # Primary source
        self.binance = BinanceService()  # Fallback
        self.technical = TechnicalIndicators()
        self.patterns = CandlestickPatterns()
        self.price_levels = PriceLevelsService()
        self.fear_greed = FearGreedService()
        self.openai = OpenAIService()

        logger.info("FuturesAnalysisService initialized (Bybit primary, Binance fallback)")

    # ========================================================================
    # DATA FETCHING WITH FALLBACK (Bybit -> Binance)
    # ========================================================================

    async def _get_current_price(self, symbol: str) -> float | None:
        """Get current price: Bybit first, Binance fallback."""
        # Try Bybit first
        price = await self.bybit.get_current_price(symbol)
        if price:
            logger.debug(f"Price for {symbol} from Bybit: {price}")
            return price

        # Fallback to Binance
        logger.info(f"Bybit price failed for {symbol}, trying Binance...")
        price = await self.binance.get_current_price(symbol)
        if price:
            logger.debug(f"Price for {symbol} from Binance: {price}")
        return price

    async def _get_klines(
        self, symbol: str, interval: str, limit: int = 200
    ) -> pd.DataFrame | None:
        """Get klines: Bybit first, Binance fallback."""
        # Try Bybit first
        df = await self.bybit.get_klines(symbol, interval, limit)
        if df is not None and len(df) > 0:
            logger.debug(f"Klines for {symbol} from Bybit: {len(df)} candles")
            return df

        # Fallback to Binance
        logger.info(f"Bybit klines failed for {symbol}, trying Binance...")
        df = await self.binance.get_klines(symbol, interval, limit)
        if df is not None:
            logger.debug(f"Klines for {symbol} from Binance: {len(df)} candles")
        return df

    async def _get_funding_rate(self, symbol: str) -> dict | None:
        """Get funding rate: Bybit first, Binance fallback."""
        # Try Bybit first
        rate = await self.bybit.get_funding_rate(symbol)
        if rate is not None:
            return {
                "funding_rate": rate,
                "funding_rate_pct": rate * 100,  # Convert to percentage
                "source": "bybit"
            }

        # Fallback to Binance
        data = await self.binance.get_latest_funding_rate(symbol)
        if data:
            data["source"] = "binance"
        return data

    async def _get_open_interest(self, symbol: str) -> dict | None:
        """Get open interest: Bybit first, Binance fallback."""
        # Try Bybit first
        oi = await self.bybit.get_open_interest(symbol)
        if oi:
            oi["source"] = "bybit"
            return oi

        # Fallback to Binance
        data = await self.binance.get_open_interest(symbol)
        if data:
            data["source"] = "binance"
        return data

    async def _get_long_short_ratio(self, symbol: str, period: str = "5m") -> dict | None:
        """Get long/short ratio: Bybit first, Binance fallback."""
        # Map period for Bybit (uses different format)
        bybit_period_map = {"5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h"}
        bybit_period = bybit_period_map.get(period, "1h")

        # Try Bybit first
        ratio = await self.bybit.get_long_short_ratio(symbol, bybit_period)
        if ratio:
            ratio["source"] = "bybit"
            return ratio

        # Fallback to Binance
        data = await self.binance.get_long_short_ratio(symbol, period, limit=30)
        if data is not None and not data.empty:
            latest = data.iloc[-1]
            return {
                "buyRatio": float(latest.get("longAccount", 0.5)),
                "sellRatio": float(latest.get("shortAccount", 0.5)),
                "source": "binance"
            }
        return None

    # =========================================================================
    # HISTORY METHODS FOR ENRICHMENT
    # =========================================================================

    async def _get_funding_history(
        self,
        symbol: str,
        limit: int = 12
    ) -> list | None:
        """Get funding rate history: Binance (has history), Bybit fallback."""
        # Binance has better history API
        try:
            data = await self.binance.get_funding_rate(symbol, limit=limit)
            if data is not None and not data.empty:
                return [
                    {
                        "funding_rate": float(row.get("fundingRate", 0)),
                        "timestamp": int(row.get("fundingTime", 0))
                    }
                    for _, row in data.iterrows()
                ]
        except Exception as e:
            logger.warning(f"Binance funding history error: {e}")

        # No good fallback for history, return None
        return None

    async def _get_oi_history(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 24
    ) -> list | None:
        """Get OI history: Bybit first, Binance fallback."""
        # Try Bybit first
        data = await self.bybit.get_open_interest_history(symbol, interval, limit)
        if data:
            return data

        # Fallback to Binance
        binance_period_map = {"1h": "1h", "4h": "4h", "1d": "1d"}
        period = binance_period_map.get(interval, "1h")
        data = await self.binance.get_open_interest_history(symbol, period, limit)
        return data

    async def _get_ls_ratio_history(
        self,
        symbol: str,
        period: str = "1h",
        limit: int = 12
    ) -> list | None:
        """Get LS ratio history: Bybit first, Binance fallback."""
        # Try Bybit first
        data = await self.bybit.get_long_short_ratio_history(symbol, period, limit)
        if data:
            return data

        # Fallback to Binance
        binance_period_map = {"1h": "1h", "4h": "4h", "1d": "1d"}
        period = binance_period_map.get(period, "1h")
        data = await self.binance.get_long_short_ratio_history(symbol, period, limit)
        return data

    async def analyze_symbol(
        self,
        symbol: str,
        timeframe: str = "4h",
        max_scenarios: int = 3,
        mode: str = "standard"  # 🆕 Trading mode
    ) -> Dict[str, Any]:
        """
        Полный анализ фьючерсного контракта с генерацией торговых сценариев

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            timeframe: Primary timeframe for analysis ('1h', '4h', '1d')
            max_scenarios: Maximum number of scenarios to generate (2-3)
            mode: Trading mode ('conservative', 'standard', 'high_risk', 'meme')

        Returns:
            Структурированный JSON со сценариями для автоматизации

        Example output:
            {
                "symbol": "BTCUSDT",
                "analysis_timestamp": "2025-01-15T12:00:00Z",
                "current_price": 95234.5,
                "market_context": {...},
                "scenarios": [...],
                "key_levels": {...},
                "data_quality": {...}
            }
        """
        try:
            logger.info(f"Starting futures analysis for {symbol} on {timeframe} [mode={mode}]")

            # ====================================================================
            # 1. СБОР ДАННЫХ (Bybit primary, Binance fallback)
            # ====================================================================

            # 1.1 Получить current price
            current_price = await self._get_current_price(symbol)
            if not current_price:
                return {
                    "success": False,
                    "error": f"Failed to fetch current price for {symbol} (both Bybit and Binance failed)"
                }

            # 1.2 Получить OHLCV данные (200 свечей для индикаторов)
            klines_df = await self._get_klines(symbol, timeframe, limit=200)

            if klines_df is None or len(klines_df) < 50:
                return {
                    "success": False,
                    "error": f"Insufficient candlestick data for {symbol}"
                }

            # 1.3 Получить multi-timeframe данные для контекста
            mtf_data = await self._get_multi_timeframe_data(symbol)

            # 1.4 Получить funding rate
            funding_data = await self._get_funding_rate(symbol)

            # 1.5 Получить Open Interest
            oi_data = await self._get_open_interest(symbol)

            # 1.6 Получить Long/Short ratio
            ls_ratio = await self._get_long_short_ratio(symbol, period="5m")

            # 1.7 Получить liquidation history
            # Note: Bybit REST API не предоставляет публичные ликвидации
            # Fallback на Binance если есть credentials
            liquidation_data = None
            if self.binance.has_credentials:
                end_time = int(time.time() * 1000)
                if timeframe in ["1d", "1w"]:
                    days = 7
                elif timeframe in ["4h", "6h", "8h", "12h"]:
                    days = 5
                else:
                    days = 3

                start_time = end_time - (days * 24 * 60 * 60 * 1000)

                liquidation_data = await self.binance.get_liquidation_history(
                    symbol=symbol,
                    start_time=start_time,
                    end_time=end_time,
                    limit=1000
                )

            # 1.8 Получить Fear & Greed Index
            fear_greed = await self.fear_greed.get_current()

            # 1.9 Получить history данные для enrichment (параллельно)
            import asyncio
            funding_history, ls_history, oi_history = await asyncio.gather(
                self._get_funding_history(symbol, limit=12),
                self._get_ls_ratio_history(symbol, period="1h", limit=12),
                self._get_oi_history(symbol, interval="1h", limit=24),
            )

            # ====================================================================
            # 2. РАСЧЁТ ИНДИКАТОРОВ
            # ====================================================================

            indicators = self.technical.calculate_all_indicators(klines_df)
            candlestick_patterns = self.patterns.detect_all_patterns(klines_df)

            # ====================================================================
            # 3. MARKET CONTEXT ANALYSIS
            # ====================================================================

            # Get mode config early (needed for bias thresholds)
            mode_config = get_mode_config(mode)

            market_context = self._analyze_market_context(
                price=current_price,
                klines=klines_df,
                indicators=indicators,
                funding=funding_data,
                oi=oi_data,
                ls_ratio=ls_ratio,
                fear_greed=fear_greed,
                mtf_data=mtf_data,
                timeframe=timeframe,
                mode_config=mode_config  # For funding_extreme threshold
            )

            # ====================================================================
            # 4. KEY LEVELS CALCULATION
            # ====================================================================

            key_levels = await self._calculate_key_levels(
                symbol=symbol,
                current_price=current_price,
                klines=klines_df,
                indicators=indicators
            )

            # ====================================================================
            # 4.5 🔥 NEW: PRICE STRUCTURE & LIQUIDATION CLUSTERS
            # ====================================================================

            # Рассчитываем сжатую структуру цены для LLM
            price_structure = self._calculate_price_structure(
                klines=klines_df,
                current_price=current_price,
                indicators=indicators,
                timeframe=timeframe
            )

            # Агрегируем liquidation data в clusters
            liquidation_clusters = self._aggregate_liquidation_clusters(
                liquidation_data=liquidation_data,
                current_price=current_price
            )

            logger.info(
                f"📊 Price structure: range {price_structure.get('range_low'):.2f} - "
                f"{price_structure.get('range_high'):.2f}, "
                f"volatility: {price_structure.get('volatility_regime')}"
            )

            if liquidation_clusters.get("total_volume_usd", 0) > 0:
                logger.info(
                    f"💥 Liquidations: ${liquidation_clusters.get('total_volume_usd'):,.0f} total, "
                    f"bias: {liquidation_clusters.get('net_liq_bias')}, "
                    f"spike: {liquidation_clusters.get('spike_magnitude')}"
                )

            # ====================================================================
            # 4.6 🔥 NEW: MARKET DATA ENRICHMENT
            # ====================================================================

            # Получаем support_near и resistance_near из key_levels
            support_near = key_levels.get("support", [])[:5]
            resistance_near = key_levels.get("resistance", [])[:5]

            # Вызываем enricher (mode_config already defined above)
            enriched_data = market_data_enricher.enrich(
                klines=klines_df,
                funding_history=funding_history,
                ls_ratio_history=ls_history,
                oi_history=oi_history,
                support_near=support_near,
                resistance_near=resistance_near,
                current_price=current_price,
                current_atr=indicators.get("atr", 0),
                timeframe=timeframe,
                mode_config=mode_config,
            )

            logger.debug(
                f"📈 Enriched data: positioning={enriched_data.get('positioning')}, "
                f"stop_hunt={enriched_data.get('microstructure', {}).get('stop_hunt', {}).get('detected')}"
            )

            # ====================================================================
            # 5. SCENARIO GENERATION
            # ====================================================================

            scenarios, no_trade_signal = await self._generate_scenarios(
                symbol=symbol,
                timeframe=timeframe,
                current_price=current_price,
                market_context=market_context,
                indicators=indicators,
                key_levels=key_levels,
                funding=funding_data,
                ls_ratio=ls_ratio,
                liquidation_data=liquidation_data,
                patterns=candlestick_patterns,
                max_scenarios=max_scenarios,
                price_structure=price_structure,
                liquidation_clusters=liquidation_clusters,
                mode=mode,
                enriched_data=enriched_data  # 🆕 Enriched market data
            )

            # ====================================================================
            # 6. DATA QUALITY ASSESSMENT
            # ====================================================================

            data_quality = self._assess_data_quality(
                klines=klines_df,
                indicators=indicators,
                funding=funding_data,
                oi=oi_data,
                liquidation_data=liquidation_data
            )

            # ====================================================================
            # 7. FINAL RESULT
            # ====================================================================

            # Generate unique analysis_id for feedback tracking
            analysis_id = str(uuid.uuid4())

            result = {
                "success": True,
                "symbol": symbol,
                "timeframe": timeframe,
                "analysis_timestamp": datetime.utcnow().isoformat() + "Z",
                "analysis_id": analysis_id,  # 🆕 For feedback loop tracking
                "current_price": round(current_price, 2),
                "market_context": market_context,
                "scenarios": scenarios,
                "key_levels": key_levels,
                "data_quality": data_quality,
                # 🆕 NO-TRADE signal (first-class citizen)
                "no_trade": no_trade_signal,
                "metadata": {
                    "has_liquidation_data": liquidation_data is not None,
                    "funding_available": funding_data is not None,
                    "candles_analyzed": len(klines_df),
                    "timeframes_analyzed": list(mtf_data.keys()) if mtf_data else []
                }
            }

            logger.info(
                f"Analysis complete for {symbol}: "
                f"{len(scenarios)} scenarios, "
                f"quality={data_quality['completeness']}%"
            )

            # 🆕 LOG: Логируем генерацию сценариев для class stats
            await self._log_scenario_generation(
                analysis_id=analysis_id,
                scenarios=scenarios,
                symbol=symbol,
                timeframe=timeframe,
                market_context=market_context,
            )

            # 🔧 Convert numpy types to native Python for JSON serialization
            result = self._convert_numpy_types(result)

            return result

        except Exception as e:
            logger.exception(f"Error in futures analysis for {symbol}: {e}")
            return {
                "success": False,
                "error": str(e),
                "symbol": symbol
            }

    async def _get_multi_timeframe_data(
        self,
        symbol: str
    ) -> Dict[str, pd.DataFrame]:
        """
        Получить данные с нескольких таймфреймов для контекста

        Используется для определения:
        - Макро-тренда (1D, 1W)
        - Среднесрочного тренда (4H)
        - Микро-структуры (1H)
        """
        mtf_data = {}
        timeframes = ["1h", "4h", "1d"]

        for tf in timeframes:
            try:
                df = await self._get_klines(symbol, tf, limit=100)
                if df is not None and len(df) >= 20:
                    mtf_data[tf] = df
            except Exception as e:
                logger.warning(f"Failed to fetch {tf} data for {symbol}: {e}")

        return mtf_data

    def _analyze_market_context(
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
        mode_config: Optional["ModeConfig"] = None  # For funding_extreme threshold
    ) -> Dict[str, Any]:
        """
        Определить текущий контекст рынка

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
        _atr_pct = indicators.get("atr_percent", 2.0)  # Reserved for future use
        context["volatility"] = indicators.get("volatility", "medium")

        # === BIAS CALCULATION с CAPS и LOGGING ===
        # 🔧 IMPROVED: Каждый фактор ограничен cap'ом для предотвращения перекоса
        bias_components = {}  # Для логирования вклада каждого фактора
        bias_score = 0

        # Helper function для применения cap
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
        # Use mode_config.funding_extreme as threshold (risk philosophy)
        funding_threshold = mode_config.funding_extreme if mode_config else 0.001
        funding_contribution = 0
        if funding:
            funding_rate = funding.get("funding_rate_pct", 0)
            # 🔍 DEBUG: логируем raw значения funding
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
            # 🔍 DEBUG: логируем raw значения ls_ratio
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

        # === SESSION DETECTION (NEW!) ===
        session_info = session_detector.get_current_session()
        context["session"] = {
            "current": session_info["session_name"],
            "is_overlap": session_info["is_overlap"],
            "volatility_expected": session_info["volatility_expected"],
            "recommendation": session_detector.get_session_recommendation(session_info)
        }

        # === VOLUME ANALYSIS (NEW!) ===
        volume_analysis = volume_analyzer.analyze(klines)
        if volume_analysis:
            context["volume"] = {
                "relative_volume": volume_analysis.get("relative_volume", 1.0),
                "classification": volume_analysis.get("volume_classification", "normal"),
                "trend": volume_analysis.get("volume_trend", "stable"),
                "spike": volume_analysis.get("volume_spike", False)
            }

        return context

    async def _calculate_key_levels(
        self,
        symbol: str,
        current_price: float,
        klines: pd.DataFrame,
        indicators: Dict
    ) -> Dict[str, Any]:
        """
        Рассчитать ключевые уровни для сценариев

        Returns:
            {
                "support": [price1, price2, price3],
                "resistance": [price1, price2, price3],
                "ema_levels": {...},
                "vwap": price,
                "liquidation_clusters": {...}
            }
        """
        levels = {}

        # Support/Resistance from OHLC
        ohlc_data = klines[['high', 'low', 'close', 'volume']].to_dict('records')
        sr_data = self.price_levels.calculate_support_resistance_from_ohlc(
            ohlc_data=ohlc_data,
            current_price=current_price,
            lookback_periods=90
        )

        if sr_data.get("success"):
            levels["support"] = sr_data.get("support_levels", [])[:3]
            levels["resistance"] = sr_data.get("resistance_levels", [])[:3]
        else:
            levels["support"] = []
            levels["resistance"] = []

        # EMA levels
        ema_levels = {}
        for ema_type in ["ema_20", "ema_50", "ema_200"]:
            ema_value = indicators.get(ema_type)
            if ema_value:
                ema_levels[ema_type] = {
                    "price": round(ema_value, 2),
                    "distance_pct": round(((current_price - ema_value) / current_price) * 100, 2)
                }
        levels["ema_levels"] = ema_levels

        # VWAP
        vwap = indicators.get("vwap")
        if vwap:
            levels["vwap"] = {
                "price": round(vwap, 2),
                "distance_pct": round(((current_price - vwap) / current_price) * 100, 2)
            }

        # Bollinger Bands
        bb_upper = indicators.get("bb_upper")
        bb_lower = indicators.get("bb_lower")
        if bb_upper and bb_lower:
            levels["bollinger_bands"] = {
                "upper": round(bb_upper, 2),
                "lower": round(bb_lower, 2)
            }

        return levels

    def _calculate_price_structure(
        self,
        klines: pd.DataFrame,
        current_price: float,
        indicators: Dict,
        timeframe: str
    ) -> Dict[str, Any]:
        """
        🔥 NEW: Рассчитать сжатую структуру цены для LLM

        Вместо того чтобы давать LLM 200 свечей, даём ему:
        - Swing points (последние 5 highs/lows)
        - Range (high/low за N свечей)
        - Trend state по таймфреймам
        - Volatility regime
        - Distance to key levels

        Returns:
            {
                "swing_highs": [{price: 96500, distance_pct: 1.2}],
                "swing_lows": [{price: 93800, distance_pct: -1.5}],
                "range_high": 96500,
                "range_low": 93800,
                "range_size_pct": 2.8,
                "current_position_in_range": 0.65,
                "trend_state": {"1h": "bullish_strong"},
                "volatility_regime": "expansion"
            }
        """
        structure = {}

        # 1. Swing points detection с ATR threshold
        # 🔧 IMPROVED: Swing не просто выше/ниже соседей, а выше на threshold
        # Это фильтрует шумные swing points

        window = 5  # Смотрим на 5 свечей влево и вправо

        highs = klines['high'].values
        lows = klines['low'].values

        # ATR threshold для значимости swing point
        atr = indicators.get("atr", 0)
        # Минимальный порог: 0.3*ATR или 0.3% от цены (что больше)
        min_threshold_pct = 0.003  # 0.3%
        min_threshold = max(atr * 0.3, current_price * min_threshold_pct) if atr else current_price * min_threshold_pct

        swing_highs = []
        swing_lows = []

        # Проходим по свечам (исключая края)
        for i in range(window, len(highs) - window):
            # Swing high: если high[i] выше всех соседей НА threshold
            left_highs = highs[i-window:i]
            right_highs = highs[i+1:i+window+1]

            # 🔧 NEW: Проверяем что swing ЗНАЧИМО выше соседей
            left_max = max(left_highs) if len(left_highs) > 0 else 0
            right_max = max(right_highs) if len(right_highs) > 0 else 0
            prominence_high = highs[i] - max(left_max, right_max)

            if (all(highs[i] > h for h in left_highs) and
                all(highs[i] > h for h in right_highs) and
                prominence_high >= min_threshold):
                price = highs[i]
                distance_pct = ((price - current_price) / current_price) * 100
                swing_highs.append({
                    "price": round(price, 2),
                    "distance_pct": round(distance_pct, 2),
                    "prominence": round(prominence_high, 2),
                    "idx": i
                })

            # Swing low: если low[i] ниже всех соседей НА threshold
            left_lows = lows[i-window:i]
            right_lows = lows[i+1:i+window+1]

            # 🔧 NEW: Проверяем что swing ЗНАЧИМО ниже соседей
            left_min = min(left_lows) if len(left_lows) > 0 else float('inf')
            right_min = min(right_lows) if len(right_lows) > 0 else float('inf')
            prominence_low = min(left_min, right_min) - lows[i]

            if (all(lows[i] < low for low in left_lows) and
                all(lows[i] < low for low in right_lows) and
                prominence_low >= min_threshold):
                price = lows[i]
                # Use abs() for support distance - always positive (how far below current)
                distance_pct = abs((price - current_price) / current_price) * 100
                swing_lows.append({
                    "price": round(price, 2),
                    "distance_pct": round(distance_pct, 2),
                    "prominence": round(prominence_low, 2),
                    "idx": i
                })

        # Берём ПОСЛЕДНИЕ 5 swing points (по времени), сортируя по prominence как вторичный критерий
        structure["swing_highs"] = sorted(
            swing_highs,
            key=lambda x: (x["idx"], x.get("prominence", 0)),
            reverse=True
        )[:5]
        structure["swing_lows"] = sorted(
            swing_lows,
            key=lambda x: (x["idx"], x.get("prominence", 0)),
            reverse=True
        )[:5]

        # Log swing detection stats
        logger.debug(
            f"Swing detection: {len(swing_highs)} highs, {len(swing_lows)} lows "
            f"(threshold={min_threshold:.2f}, ATR={(atr or 0):.2f})"
        )

        # 2. Range high/low (последние N свечей)
        lookback = 50 if timeframe in ["1h", "4h"] else 30
        recent_data = klines.tail(lookback)

        range_high = recent_data['high'].max()
        range_low = recent_data['low'].min()
        range_size_pct = ((range_high - range_low) / range_low) * 100 if range_low > 0 else 0

        structure["range_high"] = round(range_high, 2)
        structure["range_low"] = round(range_low, 2)
        structure["range_size_pct"] = round(range_size_pct, 2)

        # Position in range
        if range_high > range_low:
            position_in_range = (current_price - range_low) / (range_high - range_low)
            structure["current_position_in_range"] = round(position_in_range, 2)
        else:
            structure["current_position_in_range"] = 0.5

        # 3. Trend state (используя EMA cross + ADX)
        ema_20 = indicators.get("ema_20")
        ema_50 = indicators.get("ema_50")
        adx = indicators.get("adx", 20)

        trend_state = {}

        if ema_20 and ema_50:
            if current_price > ema_20 > ema_50:
                trend = "bullish"
                strength = "strong" if adx > 30 else "weak"
            elif current_price < ema_20 < ema_50:
                trend = "bearish"
                strength = "strong" if adx > 30 else "weak"
            else:
                trend = "sideways"
                strength = "weak"

            trend_state[timeframe] = f"{trend}_{strength}"

        structure["trend_state"] = trend_state

        # 4. Volatility regime
        atr_pct = indicators.get("atr_percent", 2.0)

        # 🔧 FIX: Правильный порядок условий (от меньшего к большему для <)
        if atr_pct > 3.0:
            volatility_regime = "very_high"
        elif atr_pct > 2.5:
            volatility_regime = "expansion"
        elif atr_pct < 1.0:  # Сначала очень низкий
            volatility_regime = "very_low"
        elif atr_pct < 1.5:  # Потом просто низкий
            volatility_regime = "compression"
        else:
            volatility_regime = "normal"

        structure["volatility_regime"] = volatility_regime

        # 5. Distance to nearest support/resistance
        # (будет полезно для быстрой оценки)
        if structure["swing_highs"]:
            nearest_resistance = min(
                [sh for sh in structure["swing_highs"] if sh["price"] > current_price],
                key=lambda x: abs(x["distance_pct"]),
                default=None
            )
            if nearest_resistance:
                structure["distance_to_resistance_pct"] = nearest_resistance["distance_pct"]

        if structure["swing_lows"]:
            nearest_support = min(
                [sl for sl in structure["swing_lows"] if sl["price"] < current_price],
                key=lambda x: abs(x["distance_pct"]),
                default=None
            )
            if nearest_support:
                structure["distance_to_support_pct"] = nearest_support["distance_pct"]

        # Convert numpy types to native Python types for JSON serialization
        structure = self._convert_numpy_types(structure)

        logger.debug(f"Price structure calculated: {structure}")
        return structure

    def _convert_numpy_types(self, obj: Any) -> Any:
        """Recursively convert numpy types to native Python types"""
        import numpy as np

        if isinstance(obj, dict):
            return {k: self._convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    def _aggregate_liquidation_clusters(
        self,
        liquidation_data: Optional[Dict],
        current_price: float
    ) -> Dict[str, Any]:
        """
        🔥 NEW: Агрегировать liquidation data в clusters для LLM

        Вместо сырых liquidation данных, даём LLM:
        - Clusters выше/ниже текущей цены
        - Spike detection (последние 1h vs среднее)
        - Net bias (long/short liquidations)

        Returns:
            {
                "clusters_above": [{price: 96000, intensity: "high", volume_usd: 5M}],
                "clusters_below": [{price: 93500, intensity: "medium", volume_usd: 2M}],
                "last_24h_liq_spike": True,
                "spike_magnitude": "large",
                "net_liq_bias": "long"
            }
        """
        if not liquidation_data or not liquidation_data.get("liquidations"):
            return {
                "clusters_above": [],
                "clusters_below": [],
                "last_24h_liq_spike": False,
                "spike_magnitude": "none",
                "liq_pressure_bias": "neutral"  # 🔧 FIX: Renamed from net_liq_bias
            }

        liquidations = liquidation_data.get("liquidations", [])

        if not liquidations:
            return {
                "clusters_above": [],
                "clusters_below": [],
                "last_24h_liq_spike": False,
                "spike_magnitude": "none",
                "liq_pressure_bias": "neutral"  # 🔧 FIX: Renamed from net_liq_bias
            }

        # Разделяем на longs/shorts
        # side="BUY" = Long liquidation (цена упала, long'и ликвидированы)
        # side="SELL" = Short liquidation (цена выросла, short'ы ликвидированы)
        long_liqs = [liq for liq in liquidations if liq.get("side") == "BUY"]
        short_liqs = [liq for liq in liquidations if liq.get("side") == "SELL"]

        # Агрегируем по ценовым зонам (bins по 0.5% для крупных монет)
        bin_size = current_price * 0.005  # 0.5% bins

        def aggregate_to_bins(liqs):
            """Агрегация ликвидаций в ценовые bins"""
            bins = defaultdict(lambda: {"volume": 0, "count": 0})

            for liq in liqs:
                price = liq.get("price", 0)
                quantity = liq.get("quantity", 0)

                if price <= 0:
                    continue

                # USD value
                volume = quantity * price

                # 🔧 FIX: Используем bin_center вместо floor
                # round к ближайшему bin center для точной визуализации уровня
                bin_index = round(price / bin_size)
                bin_center = bin_index * bin_size
                bins[bin_center]["volume"] += volume
                bins[bin_center]["count"] += 1

            # Сортируем по volume
            sorted_bins = sorted(
                bins.items(),
                key=lambda x: x[1]["volume"],
                reverse=True
            )

            # Топ 5 clusters
            clusters = []
            for bin_center, data in sorted_bins[:5]:
                volume_usd = data["volume"]

                # Определяем intensity
                if volume_usd > 5000000:  # > $5M
                    intensity = "very_high"
                elif volume_usd > 2000000:  # > $2M
                    intensity = "high"
                elif volume_usd > 1000000:  # > $1M
                    intensity = "medium"
                else:
                    intensity = "low"

                clusters.append({
                    "price": round(bin_center, 2),
                    "intensity": intensity,
                    "volume_usd": round(volume_usd, 0)
                })

            return clusters

        # Clusters выше текущей цены (short liquidations)
        all_short_clusters = aggregate_to_bins(short_liqs)
        clusters_above = [c for c in all_short_clusters if c["price"] > current_price]

        # Clusters ниже текущей цены (long liquidations)
        all_long_clusters = aggregate_to_bins(long_liqs)
        clusters_below = [c for c in all_long_clusters if c["price"] < current_price]

        # Spike detection (последние 1h vs средний за 24h)
        now = time.time() * 1000
        one_hour_ago = now - (60 * 60 * 1000)

        recent_liqs = [liq for liq in liquidations if liq.get("time", 0) > one_hour_ago]

        # Считаем volume
        def calc_liq_volume(liqs):
            return sum([liq.get("quantity", 0) * liq.get("price", 0) for liq in liqs])

        recent_volume = calc_liq_volume(recent_liqs)
        total_volume = calc_liq_volume(liquidations)

        # Средний hourly volume (за 24h)
        hours_in_data = (now - min([liq.get("time", now) for liq in liquidations])) / (60 * 60 * 1000)
        # 🔧 FIX: Минимум 1 час, чтобы избежать взрывных значений
        hours_in_data = max(hours_in_data, 1.0)
        avg_hourly_volume = total_volume / hours_in_data if hours_in_data > 0 else 0

        # Spike если recent > 3x average
        spike = recent_volume > avg_hourly_volume * 3

        # Magnitude
        if recent_volume > avg_hourly_volume * 5:
            spike_magnitude = "extreme"
        elif recent_volume > avg_hourly_volume * 3:
            spike_magnitude = "large"
        elif recent_volume > avg_hourly_volume * 2:
            spike_magnitude = "medium"
        else:
            spike_magnitude = "low"

        # 🔧 FIX: Переименовываем net_liq_bias в liq_pressure_bias для ясности
        long_liq_volume = calc_liq_volume(long_liqs)
        short_liq_volume = calc_liq_volume(short_liqs)

        total_liq_volume = long_liq_volume + short_liq_volume

        if total_liq_volume > 0:
            long_liq_pct = (long_liq_volume / total_liq_volume) * 100
            short_liq_pct = (short_liq_volume / total_liq_volume) * 100

            # Если много long liquidations = цена падала = bearish давление
            # Если много short liquidations = цена росла = bullish давление
            if long_liq_volume > short_liq_volume * 1.5:
                liq_pressure = "bearish"  # Много long'ов ликвидировано
            elif short_liq_volume > long_liq_volume * 1.5:
                liq_pressure = "bullish"  # Много short'ов ликвидировано
            else:
                liq_pressure = "neutral"
        else:
            long_liq_pct = 0
            short_liq_pct = 0
            liq_pressure = "neutral"

        result = {
            "clusters_above": clusters_above[:3],  # Топ 3
            "clusters_below": clusters_below[:3],  # Топ 3
            "last_24h_liq_spike": spike,
            "spike_magnitude": spike_magnitude,
            "liq_pressure_bias": liq_pressure,  # 🔧 RENAMED from net_liq_bias
            "long_liq_pct": round(long_liq_pct, 1),
            "short_liq_pct": round(short_liq_pct, 1),
            "total_volume_usd": round(total_liq_volume, 0)
        }

        logger.debug(f"Liquidation clusters: {result}")
        return result

    async def _generate_scenarios(
        self,
        symbol: str,
        timeframe: str,
        current_price: float,
        market_context: Dict,
        indicators: Dict,
        key_levels: Dict,
        funding: Optional[Dict],
        ls_ratio: Optional[Dict],
        liquidation_data: Optional[Dict],
        patterns: Dict,
        max_scenarios: int = 3,
        price_structure: Optional[Dict] = None,
        liquidation_clusters: Optional[Dict] = None,
        mode: str = "standard",
        enriched_data: Optional[Dict] = None  # 🆕 Enriched market data
    ) -> List[Dict[str, Any]]:
        """
        🤖 AI-DRIVEN: LLM генерирует торговые сценарии с анализом полного контекста

        Вместо rule-based формул (entry = price * 1.015), LLM:
        - Анализирует ВСЕ данные (indicators, patterns, funding, levels)
        - Создает сценарии на основе S/R levels и market context
        - Определяет entry zones, stop losses, targets
        - Рассчитывает вероятности с учетом противоречий
        - Объясняет reasoning каждого сценария

        Returns:
            List of AI-generated scenarios sorted by confidence
        """
        logger.info("🤖 Generating scenarios with AI (not rule-based formulas)...")

        try:
            scenarios, no_trade_signal = await self._ai_generate_scenarios(
                symbol=symbol,
                timeframe=timeframe,
                current_price=current_price,
                market_context=market_context,
                indicators=indicators,
                key_levels=key_levels,
                patterns=patterns,
                funding=funding,
                ls_ratio=ls_ratio,
                max_scenarios=max_scenarios,
                price_structure=price_structure,
                liquidation_clusters=liquidation_clusters,
                mode=mode,
                enriched_data=enriched_data  # 🆕 Enriched market data
            )

            logger.info(f"✅ AI generated {len(scenarios)} scenarios")
            if no_trade_signal:
                logger.info(f"🚫 NO-TRADE signal received: {no_trade_signal.get('category')}")

            # 🔥 VALIDATION: Проверяем что LLM использовал NEAR уровни
            atr = indicators.get("atr", 0)
            max_dist_pct = MAX_ENTRY_DISTANCE_PCT_BY_TF.get(timeframe, MAX_ENTRY_DISTANCE_PCT_DEFAULT)

            # Collect all levels
            all_resistances = list(key_levels.get("resistance", []))
            all_supports = list(key_levels.get("support", []))
            if price_structure:
                all_resistances.extend([sh["price"] for sh in price_structure.get("swing_highs", []) if sh.get("price")])
                all_supports.extend([sl["price"] for sl in price_structure.get("swing_lows", []) if sl.get("price")])

            # Filter to near only for validation
            resistance_near, _ = _filter_levels_by_distance(
                list(set(all_resistances)), current_price, max_dist_pct, side="short"
            )
            support_near, _ = _filter_levels_by_distance(
                list(set(all_supports)), current_price, max_dist_pct, side="long"
            )

            # Add EMA/VWAP as valid candidates (they're always near-ish)
            ema_levels = key_levels.get("ema_levels", {})
            vwap = key_levels.get("vwap", {})
            dynamic_levels = []
            for ema in ["ema_20", "ema_50", "ema_200"]:
                ema_val = ema_levels.get(ema, {}).get("price") if ema_levels else None
                if ema_val:
                    dynamic_levels.append(ema_val)
            if vwap and vwap.get("price"):
                dynamic_levels.append(vwap.get("price"))

            candidates = {
                "supports": support_near + dynamic_levels,
                "resistances": resistance_near + dynamic_levels,
            }

            validated_scenarios = self._validate_scenarios(
                scenarios=scenarios,
                candidates=candidates,
                atr=atr,
                current_price=current_price,
                timeframe=timeframe
            )

            # 🔥 Рассчитываем RR в Python (не доверяем LLM математику!)
            final_scenarios = self._calculate_rr_and_validate(
                scenarios=validated_scenarios,
                current_price=current_price,
                atr=atr
            )

            # 🆕 LLM VALIDATION: Проверяем логическую coherence сценариев
            final_scenarios = await self._llm_validate_scenarios(
                scenarios=final_scenarios,
                market_context=market_context,
                candidates=candidates,
                current_price=current_price,
            )

            # 🆕 LEARNING: Калибровка confidence и SL/TP suggestions
            final_scenarios = await self._apply_learning_calibration(
                scenarios=final_scenarios,
                symbol=symbol,
                timeframe=timeframe,
            )

            # 📊 EV: Expected Value calculation и финальная сортировка
            volatility = market_context.get("volatility", "normal")
            final_scenarios = await self._apply_ev_calculation(
                scenarios=final_scenarios,
                timeframe=timeframe,
                volatility_regime=volatility,
            )

            # 🆕 CLASS STATS: Context gates (kill switch / boost)
            final_scenarios = await self._apply_class_stats(
                scenarios=final_scenarios,
                symbol=symbol,
                timeframe=timeframe,
                market_context=market_context,
            )

            return final_scenarios, no_trade_signal

        except Exception as e:
            logger.error(f"❌ AI scenario generation failed: {e}")
            raise RuntimeError(f"Failed to generate AI scenarios: {e}")

    async def _ai_generate_scenarios(
        self,
        symbol: str,
        timeframe: str,
        current_price: float,
        market_context: Dict,
        indicators: Dict,
        key_levels: Dict,
        patterns: Optional[Dict],
        funding: Optional[Dict],
        ls_ratio: Optional[Dict],
        max_scenarios: int = 3,
        price_structure: Optional[Dict] = None,
        liquidation_clusters: Optional[Dict] = None,
        mode: str = "standard",
        enriched_data: Optional[Dict] = None  # 🆕 Enriched market data
    ) -> List[Dict]:
        """
        🤖 **MAIN AI ENGINE**: LLM анализирует рынок и генерирует торговые сценарии

        ПОЛНОСТЬЮ AI-DRIVEN подход:
        - Отправляет ВСЕ данные в LLM
        - LLM сам решает какие сценарии создать
        - LLM определяет entry/stop/targets на основе S/R analysis
        - LLM рассчитывает вероятности с учетом противоречий
        - LLM объясняет reasoning

        Returns:
            List[Dict]: Полностью готовые сценарии от AI
        """

        # 🔥 НОВЫЙ ПОДХОД: Передаём данные в JSON вместо текста!
        # Форматируем данные для LLM в структурированном виде
        supports = key_levels.get("support", [])
        resistances = key_levels.get("resistance", [])
        atr = indicators.get("atr")
        atr_pct = indicators.get("atr_percent", 2.0)
        ema_levels = key_levels.get("ema_levels", {})
        vwap = key_levels.get("vwap", {})

        # 🔧 FIX: Fallback candidates из swing points если основные пустые
        if not supports and price_structure:
            swing_lows = price_structure.get("swing_lows", [])
            supports = [sl["price"] for sl in swing_lows if sl.get("price")]

        if not resistances and price_structure:
            swing_highs = price_structure.get("swing_highs", [])
            resistances = [sh["price"] for sh in swing_highs if sh.get("price")]

        # Дополнительные fallback из range/ema/vwap
        if not supports:
            fallback_supports = []
            if price_structure:
                range_low = price_structure.get("range_low")
                if range_low:
                    fallback_supports.append(range_low)
            if ema_levels:
                for ema in ["ema_20", "ema_50", "ema_200"]:
                    ema_val = ema_levels.get(ema, {}).get("price")
                    if ema_val and ema_val < current_price:
                        fallback_supports.append(ema_val)
            supports = sorted(fallback_supports, reverse=True)[:5] if fallback_supports else []

        if not resistances:
            fallback_resistances = []
            if price_structure:
                range_high = price_structure.get("range_high")
                if range_high:
                    fallback_resistances.append(range_high)
            if ema_levels:
                for ema in ["ema_20", "ema_50", "ema_200"]:
                    ema_val = ema_levels.get(ema, {}).get("price")
                    if ema_val and ema_val > current_price:
                        fallback_resistances.append(ema_val)
            resistances = sorted(fallback_resistances)[:5] if fallback_resistances else []

        # 🔥 PRE-FILTER: Split levels into near (actionable) and macro (context)
        # Get TF-based max distance for filtering
        max_dist_pct = MAX_ENTRY_DISTANCE_PCT_BY_TF.get(timeframe, MAX_ENTRY_DISTANCE_PCT_DEFAULT)

        # Collect all resistance sources
        all_resistances = list(resistances)
        if price_structure:
            all_resistances.extend([sh["price"] for sh in price_structure.get("swing_highs", []) if sh.get("price")])

        # Collect all support sources
        all_supports = list(supports)
        if price_structure:
            all_supports.extend([sl["price"] for sl in price_structure.get("swing_lows", []) if sl.get("price")])

        # Filter into near/macro (resistance = above price for shorts)
        resistance_near, resistance_macro = _filter_levels_by_distance(
            list(set(all_resistances)), current_price, max_dist_pct, side="short"
        )
        # Filter into near/macro (support = below price for longs)
        support_near, support_macro = _filter_levels_by_distance(
            list(set(all_supports)), current_price, max_dist_pct, side="long"
        )

        logger.debug(
            f"📊 Level filtering ({timeframe}, max {max_dist_pct}%): "
            f"R_near={len(resistance_near)}, R_macro={len(resistance_macro)}, "
            f"S_near={len(support_near)}, S_macro={len(support_macro)}"
        )

        # Собираем все данные в один JSON объект
        market_data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": round(current_price, 2),

            # Market Context
            "context": {
                "trend": market_context.get("trend", "unknown"),
                "bias": market_context.get("bias", "neutral"),
                "strength": round(market_context.get("strength", 0.5), 2),
                "sentiment": market_context.get("sentiment", "unknown"),
                "phase": market_context.get("phase", "unknown")
            },

            # 🔥 NEW: Price Structure (сжатая структура цены)
            "structure": price_structure if price_structure else {},

            # 🔥 Key Levels: SPLIT into near (actionable) vs macro (context)
            "levels": {
                # NEAR = actionable for entry/SL/TP (within max_dist_pct)
                "resistance_near": resistance_near[:5],
                "support_near": support_near[:5],
                # MACRO = context only, DO NOT use for entry!
                "resistance_macro": resistance_macro[:3],
                "support_macro": support_macro[:3],
                # Dynamic levels (always near)
                "ema_20": ema_levels.get("ema_20", {}).get("price") if ema_levels else None,
                "ema_50": ema_levels.get("ema_50", {}).get("price") if ema_levels else None,
                "ema_200": ema_levels.get("ema_200", {}).get("price") if ema_levels else None,
                "vwap": vwap.get("price") if vwap else None,
                "bb_upper": indicators.get("bb_upper"),
                "bb_lower": indicators.get("bb_lower")
            },

            # Technical Indicators (только главные)
            "indicators": {
                "rsi": round(indicators.get("rsi", 50), 1),
                "adx": round(indicators.get("adx", 20), 1),
                "atr": round(atr, 2) if atr else None,
                "atr_percent": round(atr_pct, 2),
                "macd_signal": indicators.get("macd_signal"),
                "macd_histogram": round(indicators.get("macd_histogram", 0), 4)
            },

            # 🔥 NEW: Liquidation Clusters
            "liquidation": liquidation_clusters if liquidation_clusters else {
                "clusters_above": [],
                "clusters_below": [],
                "liq_pressure_bias": "neutral"  # 🔧 FIX: Updated naming
            },

            # Funding & Sentiment
            "funding": {
                "rate_pct": round(funding.get("funding_rate_pct", 0), 4) if funding else None,
                "long_short_ratio": round(ls_ratio.get("long_short_ratio", 1.0), 2) if ls_ratio else None,
                "long_pct": round(ls_ratio.get("long_account", 50), 1) if ls_ratio else None,
                "short_pct": round(ls_ratio.get("short_account", 50), 1) if ls_ratio else None
            },

            # Candlestick Patterns
            "patterns": {
                "signal": patterns.get("pattern_signal") if patterns else None,
                "last_pattern": patterns.get("last_pattern") if patterns else None,
                "strength": round(patterns.get("strength", 0), 2) if patterns else 0
            },

            # 🔥 NEW: Enriched Market Data (5 blocks)
            "positioning": enriched_data.get("positioning") if enriched_data else None,
            "microstructure": enriched_data.get("microstructure") if enriched_data else None,
            "volatility_context": enriched_data.get("volatility_context") if enriched_data else None,
            "levels_meta": enriched_data.get("levels_meta") if enriched_data else None,
            "oi": enriched_data.get("oi") if enriched_data else None
        }

        # 🆕 Get mode configuration and build MODE PROFILE block
        mode_config = get_mode_config(mode)
        mode_profile_block = build_mode_profile_block(mode_config)

        # Короткий промпт с инструкциями
        prompt = f"""You are a professional futures trader with 10+ years of experience. Analyze the market data and generate trading scenarios with EXECUTION PLANS.

{mode_profile_block}

🔥 **CRITICAL: USE ONLY _near LEVELS FOR ENTRY/SL/TP!**
- Entry orders: ONLY from resistance_near (shorts) or support_near (longs), ema_20/50/200, vwap
- Stop losses: ONLY from support_near - ATR (longs) or resistance_near + ATR (shorts)
- Targets: ONLY from resistance_near (longs) or support_near (shorts)
- _macro levels are FOR CONTEXT/NARRATIVE ONLY - DO NOT use them for entry!
- DO NOT make up arbitrary prices! Select from provided levels.

📈 **ENRICHED DATA RULES** (use positioning, microstructure, volatility_context, levels_meta, oi):
1. **Crowding + Stop-hunt combo**: If positioning.crowding_score > 0.7 AND microstructure.stop_hunt.detected=true → Prefer counter-trend. Breakout requires extra confirmation.
2. **Extreme volatility**: If volatility_context.atr_vs_30d = "extreme" → Tighten no_trade conditions. DO NOT propose tight SL (<0.5x ATR).
3. **OI divergence**: If oi.trend = "falling" during price impulse → Treat as move on closing/flush, be cautious with continuation.
4. **Level freshness**: Prefer levels with age_hours < 24 and touches >= 2 from levels_meta. Stale levels (age > 72h, touches = 1) are weaker.

📊 **MARKET DATA** (JSON):
```json
{json.dumps(market_data, indent=2, ensure_ascii=False)}
```

⏰ **TIMEFRAME ADAPTATION** ({timeframe}):
- 15m-1h: Stops 0.3-0.5% (~0.5x ATR), Leverage 10x-15x, Valid 4-6h
- 4h: Stops 0.8-1.5% (~1.0x ATR), Leverage 5x-8x, Valid 1-3 days
- 1d: Stops 2-3% (~2.0x ATR), Leverage 3x-5x, Valid 1-2 weeks

⚠️ **CRITICAL STOP-LOSS RULES**:
- LONG scenarios: stop_loss MUST be BELOW entry_min (stop < min(entry_plan.orders[].price))
- SHORT scenarios: stop_loss MUST be ABOVE entry_max (stop > max(entry_plan.orders[].price))
- DO NOT calculate RR - Python will compute it from your levels. Just provide prices.

📋 **ENTRY PLAN STRUCTURE** (instead of simple entry zone):
Each scenario MUST have an `entry_plan` with:

1. **mode**: "ladder" (2-3 limit orders), "single" (one entry), "dca"
2. **orders[]**: Array of 1-5 orders, each with:
   - price: FROM _near levels ONLY! (support_near, resistance_near, ema_20/50, vwap)
   - size_pct: Position % (all orders MUST sum to 100%)
   - type: "limit" or "stop_limit"
   - tag: "E1_zone_top", "E2_mid", "E3_support"
   - source_level: "support_near_0", "resistance_near_1", "ema_50" (MUST reference _near level!)

3. **activation**: When to start placing orders
   - type: "touch" | "break" | "close_above" | "close_below"
   - level: activation price (first entry level)
   - max_distance_pct: 0.1-5% (don't activate if price is too far)

4. **cancel_if[]**: Conditions to abort the plan:
   - "break_below 94500 (invalidation)"
   - "time_valid_hours exceeded"
   - "RSI exceeds 80"

5. **time_valid_hours**: Plan validity (adapt to timeframe)

**EXAMPLE for LONG on 4h**:
```json
"entry_plan": {{
  "mode": "ladder",
  "orders": [
    {{"price": 94800, "size_pct": 40, "type": "limit", "tag": "E1_ema20", "source_level": "ema_20"}},
    {{"price": 94200, "size_pct": 35, "type": "limit", "tag": "E2_support", "source_level": "support_1"}},
    {{"price": 93800, "size_pct": 25, "type": "limit", "tag": "E3_swing_low", "source_level": "swing_low_1"}}
  ],
  "activation": {{"type": "touch", "level": 94800, "max_distance_pct": 0.5}},
  "cancel_if": ["break_below 93500", "time_valid_hours exceeded"],
  "time_valid_hours": 48
}}
```

🎯 **REQUIREMENTS**:
1. Generate {max_scenarios} diverse scenarios (min 1 LONG + min 1 SHORT)
2. Each entry_plan.orders[].price MUST reference a real level from market_data.levels
3. Use price_structure.swing_highs/swing_lows for entry/stop selection
4. Consider liquidation.clusters_above/below for targets
5. Adapt time_valid_hours to timeframe {timeframe}
6. Account for contradictions (e.g., bullish trend + RSI 80 + high funding = overheated)

📊 **SCENARIO WEIGHT** (scenario_weight):
Assign probability weight to each scenario based on how likely it is to play out:
- scenario_weight: Float 0.10-0.90 (probability this scenario plays out vs others)
- All scenario_weights across all scenarios MUST sum to exactly 1.0!
- Example: 2 scenarios (LONG 60%, SHORT 40%) = weights [0.60, 0.40]
- Example: 3 scenarios (LONG 50%, SHORT 30%, Range 20%) = weights [0.50, 0.30, 0.20]
- Base this on: trend alignment, support/resistance proximity, market structure, momentum

📊 **OUTCOME PROBABILITIES** (outcome_probs_raw):
Estimate terminal outcome probabilities for EV calculation. These are TERMINAL outcomes = MAX TP level reached, NOT exit reason!
- sl: P(price hits SL before ANY TP) — typical 0.30-0.50
- tp1: P(reaches TP1 but NOT TP2) — typical 0.20-0.35
- tp2: P(reaches TP2 but NOT TP3) — typical 0.10-0.25 (set 0 if only 1-2 targets)
- tp3: P(reaches TP3) — typical 0.05-0.15 (set 0 if less than 3 targets)
- other: P(manual exit/timeout BEFORE any TP) — typical 0.02-0.10

⚠️ CRITICAL: sl + tp1 + tp2 + tp3 + other = 1.0 EXACTLY!
Base estimates on: trend strength, entry quality, volatility, support/resistance proximity.

🚫 **NO-TRADE SIGNAL** (optional but IMPORTANT):
If market conditions are UNFAVORABLE, add `no_trade` object with:
- should_not_trade: true
- confidence: 0.3-1.0 (how certain you are)
- reasons: ["ADX < 20 = chop zone", "Funding extreme + crowded", "ATR compression before news"]
- category: "chop" | "extreme_sentiment" | "low_liquidity" | "news_risk" | "technical_conflict" | "overextended"
- wait_for: ["ADX > 25", "Funding normalize", "Breakout from range"]
- estimated_wait_hours: 4-168

**When to recommend NO-TRADE:**
- ADX < 20 AND no clear breakout setup = "chop"
- Funding > 0.1% OR < -0.1% with crowded positioning = "extreme_sentiment"
- RSI > 80 OR < 20 extended for 3+ candles = "overextended"
- Multiple conflicting signals (bullish trend + bearish divergence + extreme funding) = "technical_conflict"
- Low ATR + tight range before known news = "news_risk"

**STILL return scenarios** even with no_trade — they serve as reference. The no_trade signal WARNS the user.

Return strict JSON format."""

        logger.debug("Sending market data to AI for scenario generation...")

        # JSON Schema для ГАРАНТИРОВАННОГО валидного ответа
        json_schema = {
            "name": "trading_scenarios",
            "schema": {
                "type": "object",
                "properties": {
                    "scenarios": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                                "bias": {"type": "string", "enum": ["long", "short"]},
                                # 🔥 NEW: Entry Plan (execution plan with ladder orders)
                                "entry_plan": {
                                    "type": "object",
                                    "properties": {
                                        "mode": {
                                            "type": "string",
                                            "enum": ["ladder", "single", "dca"],
                                            "description": "Entry mode: 'ladder' (multiple limits), 'single', 'dca'"
                                        },
                                        "orders": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "price": {"type": "number", "description": "Order price from candidate levels"},
                                                    "size_pct": {"type": "integer", "minimum": 1, "maximum": 100, "description": "% of total position"},
                                                    "type": {"type": "string", "enum": ["limit", "stop_limit"]},
                                                    "tag": {"type": "string", "description": "E.g., 'E1_zone_top', 'E2_support'"},
                                                    "source_level": {"type": "string", "description": "Source: 'swing_low_1', 'ema_20', 'support_1'"}
                                                },
                                                "required": ["price", "size_pct", "type", "tag", "source_level"],
                                                "additionalProperties": False
                                            },
                                            "minItems": 1,
                                            "maxItems": 5
                                        },
                                        "activation": {
                                            "type": "object",
                                            "properties": {
                                                "type": {"type": "string", "enum": ["touch", "break", "close_above", "close_below"]},
                                                "level": {"type": "number"},
                                                "max_distance_pct": {"type": "number", "minimum": 0.1, "maximum": 5.0}
                                            },
                                            "required": ["type", "level", "max_distance_pct"],
                                            "additionalProperties": False
                                        },
                                        "cancel_if": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "Conditions to cancel the plan"
                                        },
                                        "time_valid_hours": {"type": "integer", "minimum": 1, "maximum": 336}
                                    },
                                    "required": ["mode", "orders", "activation", "cancel_if", "time_valid_hours"],
                                    "additionalProperties": False
                                },
                                "stop_loss": {
                                    "type": "object",
                                    "properties": {
                                        "conservative": {"type": "number"},
                                        "aggressive": {"type": "number"},
                                        "recommended": {"type": "number"},
                                        "reason": {"type": "string"}
                                    },
                                    "required": ["conservative", "aggressive", "recommended", "reason"],
                                    "additionalProperties": False
                                },
                                "targets": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "level": {"type": "integer"},
                                            "price": {"type": "number"},
                                            "partial_close_pct": {"type": "integer", "minimum": 0, "maximum": 100, "description": "Процент закрытия позиции (0-100, не дробь!)"},
                                            "reason": {"type": "string"}
                                        },
                                        "required": ["level", "price", "partial_close_pct", "reason"],
                                        "additionalProperties": False
                                    }
                                },
                                "confidence": {"type": "number", "minimum": 0.05, "maximum": 0.95},
                                "confidence_factors": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "risks": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "leverage": {
                                    "type": "object",
                                    "properties": {
                                        "recommended": {"type": "string"},
                                        "max_safe": {"type": "string"},
                                        "reason": {"type": "string"}
                                    },
                                    "required": ["recommended", "max_safe", "reason"],
                                    "additionalProperties": False
                                },
                                "invalidation_price": {"type": "number"},
                                "conditions": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                # 🆕 EV: Terminal outcome probabilities (optional, LLM estimate)
                                "outcome_probs_raw": {
                                    "type": "object",
                                    "description": "Terminal outcome probabilities (must sum to 1.0)",
                                    "properties": {
                                        "sl": {"type": "number", "minimum": 0.01, "maximum": 0.95, "description": "P(hit SL before any TP)"},
                                        "tp1": {"type": "number", "minimum": 0.01, "maximum": 0.95, "description": "P(reach TP1 but not TP2)"},
                                        "tp2": {"type": "number", "minimum": 0, "maximum": 0.95, "description": "P(reach TP2 but not TP3)"},
                                        "tp3": {"type": "number", "minimum": 0, "maximum": 0.95, "description": "P(reach TP3)"},
                                        "other": {"type": "number", "minimum": 0.01, "maximum": 0.35, "description": "P(manual/timeout before any TP)"}
                                    },
                                    "required": ["sl", "tp1", "tp2", "tp3", "other"],
                                    "additionalProperties": False
                                },
                                # 🆕 Trading mode notes (how LLM applied mode params)
                                "mode_notes": get_mode_notes_schema(),
                                # 🆕 Scenario weight - probability this scenario plays out vs others
                                "scenario_weight": {
                                    "type": "number",
                                    "minimum": 0.10,
                                    "maximum": 0.90,
                                    "description": "Probability weight (0.10-0.90). All weights across scenarios must sum to 1.0"
                                }
                            },
                            "required": ["id", "name", "bias", "entry_plan", "stop_loss", "targets", "confidence", "confidence_factors", "risks", "leverage", "invalidation_price", "conditions", "outcome_probs_raw", "mode_notes", "scenario_weight"],
                            "additionalProperties": False
                        }
                    },
                    "market_summary": {"type": "string"},
                    "primary_scenario_id": {"type": "integer"},
                    "risk_level": {"type": "string", "enum": ["low", "medium", "high", "very_high"]},
                    # 🆕 NO-TRADE signal (first-class citizen)
                    "no_trade": {
                        "type": "object",
                        "description": "NO-TRADE signal when market conditions are unfavorable",
                        "properties": {
                            "should_not_trade": {"type": "boolean", "description": "true = recommend NOT trading"},
                            "confidence": {"type": "number", "minimum": 0.3, "maximum": 1.0, "description": "Confidence in no-trade recommendation"},
                            "reasons": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 1,
                                "description": "Specific reasons NOT to trade"
                            },
                            "category": {
                                "type": "string",
                                "enum": ["chop", "extreme_sentiment", "low_liquidity", "news_risk", "technical_conflict", "overextended"],
                                "description": "Primary category of no-trade signal"
                            },
                            "wait_for": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "What to wait for before trading resumes"
                            },
                            "estimated_wait_hours": {"type": "integer", "minimum": 1, "maximum": 168}
                        },
                        "required": ["should_not_trade", "confidence", "reasons", "category", "wait_for", "estimated_wait_hours"],
                        "additionalProperties": False
                    }
                },
                "required": ["scenarios", "market_summary", "primary_scenario_id", "risk_level", "no_trade"],
                "additionalProperties": False
            },
            "strict": True
        }

        # 🎯 Вызываем LLM с ГАРАНТИЕЙ валидного JSON
        # Note: gpt-5-mini is reasoning model, doesn't support temperature
        ai_result = await self.openai.structured_completion(
            prompt=prompt,
            json_schema=json_schema,
            model=FUTURES_MODEL  # gpt-5-mini supports structured outputs
        )

        scenarios = ai_result.get("scenarios", [])
        no_trade_raw = ai_result.get("no_trade")  # 🆕 NO-TRADE signal

        logger.info(f"🤖 AI Market Summary: {ai_result.get('market_summary', 'N/A')}")
        if no_trade_raw and no_trade_raw.get("should_not_trade"):
            logger.warning(f"🚫 NO-TRADE SIGNAL: {no_trade_raw.get('category')} - {no_trade_raw.get('reasons', [])}")
        logger.info(f"🤖 AI generated {len(scenarios)} scenarios, primary: #{ai_result.get('primary_scenario_id')}")

        # 🔄 Адаптируем структуру под API Pydantic модели
        adapted_scenarios = []
        for sc in scenarios:
            # Адаптируем leverage структуру
            leverage = sc.get("leverage", {})
            adapted_leverage = {
                "recommended": leverage.get("recommended", "5x-8x"),
                "max_safe": leverage.get("max_safe", "10x"),
                "volatility_adjusted": True,  # Всегда True, так как учитываем ATR
                "atr_pct": round(atr_pct, 2) if atr_pct else None
            }

            # Адаптируем invalidation структуру
            adapted_invalidation = {
                "price": sc.get("invalidation_price", 0),
                "condition": f"Break {'above' if sc.get('bias') == 'short' else 'below'} ${sc.get('invalidation_price', 0):.2f}"
            }

            # Адаптируем why структуру
            confidence_factors = sc.get("confidence_factors", [])
            risks = sc.get("risks", [])
            bias = sc.get("bias")

            adapted_why = {
                "bullish_factors": confidence_factors if bias == "long" else None,
                "bearish_factors": confidence_factors if bias == "short" else None,
                "risks": risks
            }

            # 🔥 NEW: Рассчитываем дополнительные метрики из entry_plan
            entry_plan = sc.get("entry_plan", {})
            entry_orders = entry_plan.get("orders", [])

            # Рассчитываем entry_mid из orders (weighted average по size_pct)
            if entry_orders:
                total_weight = sum(order.get("size_pct", 0) for order in entry_orders)
                if total_weight > 0:
                    entry_mid = sum(
                        order.get("price", 0) * order.get("size_pct", 0)
                        for order in entry_orders
                    ) / total_weight
                else:
                    entry_mid = entry_orders[0].get("price", 0) if entry_orders else 0

                # Legacy entry zone (для обратной совместимости)
                entry_prices = [order.get("price", 0) for order in entry_orders if order.get("price", 0) > 0]
                legacy_entry = {
                    "price_min": min(entry_prices) if entry_prices else 0,
                    "price_max": max(entry_prices) if entry_prices else 0,
                    "type": "ladder_limit" if len(entry_orders) > 1 else "limit",
                    "reason": f"Entry plan with {len(entry_orders)} order(s)"
                }
            else:
                entry_mid = 0
                legacy_entry = {"price_min": 0, "price_max": 0, "type": "unknown", "reason": "No orders"}

            recommended_stop = sc.get("stop_loss", {}).get("recommended", 0)

            # Stop % от entry
            stop_pct_of_entry = abs((recommended_stop - entry_mid) / entry_mid) * 100 if entry_mid > 0 else 0

            # ATR multiple stop
            atr_value = atr if atr else 0
            atr_multiple_stop = abs(entry_mid - recommended_stop) / atr_value if atr_value > 0 else None

            # 🔧 IMPROVED: Validity на основе волатильности вместо "timeframe * 12"
            # Формула: time_valid ~ target_distance / ATR_per_hour

            # Парсим timeframe в часы
            if timeframe.endswith("m"):
                minutes = int(timeframe[:-1])
                tf_hours = minutes / 60.0
            elif timeframe.endswith("h"):
                tf_hours = int(timeframe[:-1])
            elif timeframe.endswith("d"):
                days = int(timeframe[:-1])
                tf_hours = days * 24
            elif timeframe.endswith("w"):
                weeks = int(timeframe[:-1])
                tf_hours = weeks * 168
            else:
                tf_hours = 24  # Default

            # Calculate volatility-based validity
            targets = sc.get("targets", [])
            if targets and atr_value > 0 and entry_mid > 0:
                # Берём последний TP для расчёта максимального времени
                last_tp = targets[-1].get("price", 0) if targets else 0
                target_distance = abs(last_tp - entry_mid)

                # ATR per hour (грубо: ATR за период / часов в периоде)
                atr_per_hour = atr_value / tf_hours if tf_hours > 0 else atr_value

                # Время = дистанция / скорость (ATR/час)
                # С коэффициентом 1.5 для консервативности (рынок не всегда движется с макс скоростью)
                if atr_per_hour > 0:
                    estimated_hours = (target_distance / atr_per_hour) * 1.5
                    time_valid_hours = round(estimated_hours)
                else:
                    # Fallback к старой логике
                    time_valid_hours = round(tf_hours * 12)
            else:
                # Fallback к старой логике если нет данных
                time_valid_hours = round(tf_hours * 12)

            # Cap минимум/максимум
            time_valid_hours = max(2, min(time_valid_hours, 336))  # От 2ч до 2 недель

            # Entry trigger (первое условие или дефолтное)
            conditions = sc.get("conditions", [])
            entry_trigger = conditions[0] if conditions else "Enter at specified price zone"

            # No-trade conditions (из рисков)
            no_trade_conditions = [f"Avoid if {risk.lower()}" for risk in risks[:2]] if risks else []

            # Создаем адаптированный сценарий
            adapted_sc = {
                "id": sc.get("id"),
                "name": sc.get("name"),
                "bias": sc.get("bias"),
                "confidence": sc.get("confidence"),

                # 🔥 NEW: Entry Plan (execution plan with ladder orders)
                "entry_plan": entry_plan,

                # Legacy entry (for backwards compatibility)
                "entry": legacy_entry,

                "stop_loss": sc.get("stop_loss"),
                "targets": sc.get("targets"),
                "leverage": adapted_leverage,
                "invalidation": adapted_invalidation,
                "why": adapted_why,
                "conditions": sc.get("conditions", []),

                # 🆕 Additional metrics
                "stop_pct_of_entry": round(stop_pct_of_entry, 2),
                "atr_multiple_stop": round(atr_multiple_stop, 2) if atr_multiple_stop else None,
                "time_valid_hours": entry_plan.get("time_valid_hours", time_valid_hours),
                "entry_trigger": entry_trigger,
                "no_trade_conditions": no_trade_conditions,

                # 🆕 Trading mode notes
                "mode_notes": sc.get("mode_notes", []),

                # 🆕 Scenario weight - probability this scenario plays out vs others
                "scenario_weight": sc.get("scenario_weight", 0),
            }

            adapted_scenarios.append(adapted_sc)

        # Сортируем по confidence
        adapted_scenarios = sorted(adapted_scenarios, key=lambda x: x["confidence"], reverse=True)

        # 🔥 УЛУЧШЕННАЯ ЛОГИКА: Гарантируем diversity (min 1 long + 1 short)
        if len(adapted_scenarios) > max_scenarios:
            # Отбираем топ сценарии, но обеспечиваем разнообразие
            final_scenarios = []

            # Разделяем на long/short
            long_scenarios = [sc for sc in adapted_scenarios if sc["bias"] == "long"]
            short_scenarios = [sc for sc in adapted_scenarios if sc["bias"] == "short"]

            # Берём лучший long и лучший short
            if long_scenarios:
                final_scenarios.append(long_scenarios[0])
            if short_scenarios:
                final_scenarios.append(short_scenarios[0])

            # Добираем до max_scenarios лучшими по confidence
            remaining_slots = max_scenarios - len(final_scenarios)
            if remaining_slots > 0:
                # Исключаем уже добавленные
                added_ids = {sc["id"] for sc in final_scenarios}
                remaining = [sc for sc in adapted_scenarios if sc["id"] not in added_ids]
                final_scenarios.extend(remaining[:remaining_slots])

            # Сортируем финальный список по confidence
            final_scenarios = sorted(final_scenarios, key=lambda x: x["confidence"], reverse=True)

            return final_scenarios, no_trade_raw
        else:
            # Если сценариев меньше max_scenarios, возвращаем все
            return adapted_scenarios, no_trade_raw

    # =========================================================================
    # 🆕 LLM SCENARIO VALIDATION
    # =========================================================================

    async def _llm_validate_scenarios(
        self,
        scenarios: List[Dict],
        market_context: Dict,
        candidates: Dict,
        current_price: float,
    ) -> List[Dict]:
        """
        LLM-based validation of scenario logical coherence.

        Uses fast model (gpt-5-mini) to validate:
        - SL/entry logic (SL below entry for long, above for short)
        - Entry alignment with real levels
        - Target placement logic
        - Overall scenario coherence

        Modes:
        - ADJUST (default): Add flags, adjust confidence
        - STRICT: Reject scenario on hard violations

        Args:
            scenarios: Scenarios to validate
            market_context: Market context dict
            candidates: Available price levels
            current_price: Current price

        Returns:
            Validated scenarios (some may be rejected on STRICT violations)
        """
        from src.services.scenario_validator import scenario_validator

        if not scenarios:
            return scenarios

        # =====================================================================
        # NORMALIZE PROBS before validation (fix common LLM output issues)
        # =====================================================================
        def normalize_probs(probs: Dict[str, float]) -> Dict[str, float]:
            """Normalize outcome_probs to sum to 1.0"""
            if not probs:
                return probs

            # Convert percentages to fractions if needed (e.g., 35 -> 0.35)
            values = list(probs.values())
            if any(v > 1.0 for v in values):
                probs = {k: v / 100.0 for k, v in probs.items()}

            total = sum(probs.values())
            if total == 0:
                return probs

            # Normalize if sum is not ~1.0 (tolerance: 0.01)
            if abs(total - 1.0) > 0.01:
                probs = {k: round(v / total, 4) for k, v in probs.items()}
                logger.debug(f"📊 Normalized probs: sum was {total:.3f}, now 1.0")

            return probs

        # Apply normalization to all scenarios
        for scenario in scenarios:
            if "outcome_probs_raw" in scenario:
                scenario["outcome_probs_raw"] = normalize_probs(
                    scenario["outcome_probs_raw"]
                )

        logger.info(f"🔍 LLM validating {len(scenarios)} scenarios...")

        validated = []
        rejected_count = 0

        for scenario in scenarios:
            try:
                # Build candidate levels for validator
                candidate_levels = {
                    "support_near": candidates.get("supports", []),
                    "resistance_near": candidates.get("resistances", []),
                }

                # Add market context info
                validation_context = {
                    "current_price": current_price,
                    "trend": market_context.get("trend", "unknown"),
                    "atr_percent": market_context.get("volatility_atr_pct", 0),
                }

                # Validate with LLM
                result = await scenario_validator.validate(
                    scenario=scenario,
                    market_context=validation_context,
                    candidate_levels=candidate_levels,
                )

                # STRICT: Reject on hard violations
                if result.hard_violation:
                    logger.warning(
                        f"❌ Scenario #{scenario.get('id')} REJECTED: "
                        f"{result.hard_violation}"
                    )
                    rejected_count += 1
                    continue

                # ADJUST: Add flags and adjust confidence
                scenario["validator_flags"] = result.issues
                scenario["validator_suggestions"] = result.suggestions

                # Apply confidence adjustment (clamped to 0.1-0.95)
                old_conf = scenario.get("confidence", 0.5)
                new_conf = max(0.1, min(0.95, old_conf + result.confidence_adjustment))
                scenario["confidence"] = new_conf

                if result.confidence_adjustment != 0:
                    logger.info(
                        f"📊 Scenario #{scenario.get('id')} confidence: "
                        f"{old_conf:.2f} → {new_conf:.2f} "
                        f"(adj: {result.confidence_adjustment:+.2f})"
                    )

                validated.append(scenario)

            except Exception as e:
                logger.error(f"LLM validation error for scenario #{scenario.get('id')}: {e}")
                # On error, keep scenario but add warning
                scenario["validator_flags"] = [f"Validation error: {str(e)}"]
                validated.append(scenario)

        if rejected_count > 0:
            logger.warning(f"🚫 LLM validation rejected {rejected_count} scenarios")

        logger.info(f"✅ LLM validation complete: {len(validated)} scenarios passed")

        return validated

    # =========================================================================
    # 🆕 LEARNING SYSTEM INTEGRATION
    # =========================================================================

    async def _apply_learning_calibration(
        self,
        scenarios: List[Dict],
        symbol: str,
        timeframe: str,
    ) -> List[Dict]:
        """
        Применить калибровку confidence и SL/TP suggestions из learning системы.

        1. Калибрует raw confidence на основе исторической статистики
        2. Добавляет suggested SL/TP из archetype статистики
        3. Сохраняет оба значения: confidence_raw и confidence (calibrated)

        Args:
            scenarios: Scenarios to calibrate
            symbol: Trading pair
            timeframe: Timeframe

        Returns:
            Calibrated scenarios with learning insights
        """
        try:
            async with get_session_maker()() as session:
                for sc in scenarios:
                    raw_confidence = sc.get("confidence", 0.5)

                    # 1. Калибровка confidence
                    calibrated = await confidence_calibrator.calibrate(
                        session,
                        raw_confidence,
                        symbol=symbol,
                        timeframe=timeframe,
                    )

                    # Сохраняем оба значения
                    sc["confidence_raw"] = raw_confidence
                    sc["confidence"] = calibrated

                    # 2. SL/TP suggestions (если есть archetype)
                    archetype = sc.get("primary_archetype")
                    if archetype:
                        suggestion = await sltp_optimizer.get_suggestions(
                            session,
                            archetype=archetype,
                            symbol=symbol,
                            timeframe=timeframe,
                        )

                        if suggestion.based_on_trades > 0:
                            sc["learning_suggestions"] = {
                                "sl_atr_mult": suggestion.sl_atr_mult,
                                "tp1_r": suggestion.tp1_r,
                                "tp2_r": suggestion.tp2_r,
                                "based_on_trades": suggestion.based_on_trades,
                                "confidence": suggestion.confidence,
                            }

                # Re-sort by calibrated confidence
                scenarios = sorted(scenarios, key=lambda x: x["confidence"], reverse=True)

                logger.debug(f"Learning calibration applied to {len(scenarios)} scenarios")

        except Exception as e:
            logger.warning(f"Learning calibration failed (using raw values): {e}")
            # Return scenarios unchanged on error

        return scenarios

    # =========================================================================
    # 📊 EV CALCULATION (Expected Value для каждого сценария)
    # =========================================================================

    async def _apply_ev_calculation(
        self,
        scenarios: List[Dict],
        timeframe: str,
        volatility_regime: str = "normal",
    ) -> List[Dict]:
        """
        Рассчитать Expected Value для каждого сценария.

        EV_R = Σ(P_TPk * payout_TPk) + P_SL * payout_SL + P_OTHER * payout_OTHER

        Args:
            scenarios: Сценарии после learning calibration
            timeframe: Timeframe
            volatility_regime: low/normal/high

        Returns:
            Сценарии с EV метриками, отсортированные по scenario_score
        """
        try:
            async with get_session_maker()() as session:
                for sc in scenarios:
                    targets = sc.get("targets", [])
                    if not targets:
                        continue

                    side = sc.get("bias", "long")
                    archetype = sc.get("primary_archetype")
                    confidence = sc.get("confidence", 0.5)

                    # Рассчитываем EV
                    probs, metrics = await ev_calculator.calculate_ev(
                        session=session,
                        targets=targets,
                        side=side,
                        archetype=archetype,
                        timeframe=timeframe,
                        volatility_regime=volatility_regime,
                        confidence=confidence,
                        llm_probs=sc.get("outcome_probs_raw"),  # если LLM предоставил
                    )

                    # Gate: TP1 RR < 1.0 при BE
                    tp1_rr = targets[0].get("rr", 0) if targets else 0
                    ev_multiplier = 1.0
                    ev_flags = list(metrics.flags)

                    if tp1_rr < 0.8:
                        # Hard reject - помечаем как мусорный
                        ev_flags.append("tp1_rr_too_low_reject")
                        sc["rejected"] = True
                        sc["reject_reason"] = f"TP1 RR {tp1_rr:.2f} < 0.8 (BE enabled)"
                    elif tp1_rr < 1.0:
                        # Penalty zone
                        ev_flags.append("tp1_rr_penalty_zone")
                        ev_multiplier = 0.7  # -30% к EV

                    # Применяем penalty
                    adjusted_ev = (metrics.ev_r or 0) * ev_multiplier
                    adjusted_score = (metrics.scenario_score or 0) * ev_multiplier

                    if ev_multiplier < 1.0:
                        ev_flags.append(f"ev_adjusted_{ev_multiplier}")

                    # Добавляем в сценарий (V2 формат)
                    sc["outcome_probs"] = {
                        "sl_early": probs.sl_early,
                        "be_after_tp1": probs.be_after_tp1,
                        "stop_in_profit": probs.stop_in_profit,
                        "tp1_final": probs.tp1_final,
                        "tp2_final": probs.tp2_final,
                        "tp3_final": probs.tp3_final,
                        "other": probs.other,
                        "source": probs.source,
                        "sample_size": probs.sample_size,
                        "n_targets": probs.n_targets,
                    }

                    sc["ev_metrics"] = {
                        "ev_r": round(adjusted_ev, 4),
                        "ev_r_after_tp1": metrics.ev_r_after_tp1,
                        "fees_r": metrics.fees_r,
                        "ev_grade": metrics.ev_grade,
                        "scenario_score": round(adjusted_score, 4),
                        "n_targets": metrics.n_targets,
                        "flags": ev_flags,
                    }

                # Фильтруем rejected сценарии и сортируем по scenario_score
                valid_scenarios = [sc for sc in scenarios if not sc.get("rejected")]
                rejected_scenarios = [sc for sc in scenarios if sc.get("rejected")]

                scenarios = sorted(
                    valid_scenarios,
                    key=lambda x: x.get("ev_metrics", {}).get("scenario_score", 0),
                    reverse=True
                )

                # Логируем rejected
                if rejected_scenarios:
                    logger.info(f"Rejected {len(rejected_scenarios)} scenarios due to low TP1 RR")

                logger.debug(
                    f"EV calculation applied to {len(scenarios)} scenarios, "
                    f"top score: {scenarios[0].get('ev_metrics', {}).get('scenario_score', 0):.3f}"
                    if scenarios else ""
                )

        except Exception as e:
            logger.warning(f"EV calculation failed: {e}")
            # Return scenarios unchanged on error

        return scenarios

    # =========================================================================
    # 🆕 CLASS STATS (Context Gates: Kill Switch / Boost)
    # =========================================================================

    async def _apply_class_stats(
        self,
        scenarios: List[Dict],
        symbol: str,
        timeframe: str,
        market_context: Dict,
    ) -> List[Dict]:
        """
        Применить context gates из class stats системы.

        1. Строит ClassKey для каждого сценария
        2. Получает class_stats с L2 -> L1 fallback
        3. Применяет modifiers (confidence, warnings)
        4. Clamp confidence в пределах [0.05, 0.95]

        Args:
            scenarios: Сценарии после EV calculation
            symbol: Trading pair
            timeframe: Timeframe
            market_context: Market context с factors для buckets

        Returns:
            Сценарии с class_stats метаданными и скорректированным confidence
        """
        try:
            async with get_session_maker()() as session:
                # Извлекаем factors для bucketization
                factors = {
                    "trend": market_context.get("trend", "sideways"),
                    "trend_strength": market_context.get("trend_strength", 0),
                    "volatility_regime": market_context.get("volatility", "normal"),
                    "funding_rate": market_context.get("funding_rate"),
                    "sentiment": market_context.get("sentiment"),
                    "fear_greed": market_context.get("fear_greed"),
                }

                for sc in scenarios:
                    archetype = sc.get("primary_archetype")
                    if not archetype:
                        continue

                    side = sc.get("bias", "long").lower()

                    # Строим ClassKey
                    class_key = build_class_key(
                        archetype=archetype,
                        side=side,
                        timeframe=timeframe,
                        factors=factors,
                        level=2,  # Сначала L2, fallback на L1
                    )

                    # Получаем stats с fallback
                    lookup_result = await class_stats_analyzer.get_class_stats(
                        session=session,
                        class_key=class_key,
                        allow_fallback=True,
                    )

                    if lookup_result.stats:
                        stats = lookup_result.stats

                        # Сохраняем raw confidence
                        raw_confidence = sc.get("confidence", 0.5)
                        sc["confidence_raw"] = raw_confidence

                        # Применяем modifier
                        new_confidence = raw_confidence + stats.confidence_modifier

                        # Если класс disabled - штраф
                        if not stats.is_enabled:
                            new_confidence *= 0.5
                            sc["class_warning"] = stats.disable_reason

                        # Clamp confidence
                        sc["confidence"] = max(
                            CONFIDENCE_MIN,
                            min(CONFIDENCE_MAX, new_confidence)
                        )

                        # Добавляем class_stats метаданные
                        sc["class_stats"] = {
                            "class_key": class_key.key_string,
                            "class_key_hash": class_key.key_hash,
                            "class_level": f"L{stats.class_level}",
                            "sample_size": stats.total_trades,
                            "sample_status": stats.get_sample_status(),
                            "is_enabled": stats.is_enabled,
                            "disable_reason": stats.disable_reason,
                            "preliminary_warning": stats.preliminary_warning,
                            "winrate": round(stats.winrate, 3),
                            "winrate_lower_ci": round(stats.winrate_lower_ci, 3),
                            "avg_pnl_r": round(stats.avg_pnl_r, 2),
                            "avg_ev_r": round(stats.avg_ev_r, 2),
                            "ev_lower_ci": round(stats.ev_lower_ci, 2),
                            "max_drawdown_r": round(stats.max_drawdown_r, 2),
                            "conversion_rate": round(stats.conversion_rate, 3),
                            "confidence_modifier": stats.confidence_modifier,
                            "window_days": stats.window_days,
                            # Fallback metadata
                            "fallback_used": lookup_result.fallback_used,
                            "fallback_from": lookup_result.fallback_from,
                            "fallback_reason": lookup_result.fallback_reason,
                        }

                        # Preliminary warning
                        if stats.preliminary_warning:
                            sc["class_warning"] = stats.preliminary_warning

                logger.debug(
                    f"Class stats applied to {len(scenarios)} scenarios"
                )

        except Exception as e:
            logger.warning(f"Class stats application failed: {e}")
            # Return scenarios unchanged on error

        return scenarios

    async def _log_scenario_generation(
        self,
        analysis_id: str,
        scenarios: List[Dict],
        symbol: str,
        timeframe: str,
        market_context: Dict,
        user_id: int = 0,
        is_testnet: bool = False,
    ):
        """
        Залогировать генерацию сценариев для class stats conversion tracking.

        Логирует каждый сценарий в scenario_generation_log с идемпотентностью
        по (analysis_id, scenario_local_id).

        Args:
            analysis_id: UUID анализа
            scenarios: Список сценариев
            symbol: Trading pair
            timeframe: Timeframe
            market_context: Market context для buckets
            user_id: User ID (0 = API call без auth)
            is_testnet: Testnet flag
        """
        try:
            async with get_session_maker()() as session:
                # Извлекаем factors для bucketization
                factors = {
                    "trend": market_context.get("trend", "sideways"),
                    "trend_strength": market_context.get("trend_strength", 0),
                    "volatility_regime": market_context.get("volatility", "normal"),
                    "funding_rate": market_context.get("funding_rate"),
                    "sentiment": market_context.get("sentiment"),
                    "fear_greed": market_context.get("fear_greed"),
                }

                logged_count = 0
                for idx, sc in enumerate(scenarios, start=1):
                    archetype = sc.get("primary_archetype")
                    if not archetype:
                        continue

                    side = sc.get("bias", "long").lower()

                    # Строим ClassKey
                    class_key = build_class_key(
                        archetype=archetype,
                        side=side,
                        timeframe=timeframe,
                        factors=factors,
                        level=2,
                    )

                    # Логируем (идемпотентно)
                    is_new = await class_stats_analyzer.log_scenario_generation(
                        session=session,
                        analysis_id=analysis_id,
                        scenario_local_id=idx,
                        user_id=user_id,
                        symbol=symbol,
                        timeframe=timeframe,
                        class_key=class_key,
                        is_testnet=is_testnet,
                    )

                    if is_new:
                        logged_count += 1

                await session.commit()

                if logged_count > 0:
                    logger.debug(
                        f"Logged {logged_count} scenario generations for analysis {analysis_id}"
                    )

        except Exception as e:
            logger.warning(f"Scenario generation logging failed: {e}")
            # Non-critical, don't raise

    # =========================================================================
    # 🔥 SCENARIO VALIDATION (маст-хэв для контроля LLM галлюцинаций)
    # =========================================================================

    def _validate_scenarios(
        self,
        scenarios: List[Dict],
        candidates: Dict[str, List[float]],
        atr: float,
        current_price: float,
        timeframe: str = "4h"
    ) -> List[Dict]:
        """
        Валидатор сценариев: проверяет что LLM использовал реальные уровни

        Правила:
        1. entry_min/max должны быть в пределах δ (1.5% или 1.5*ATR) от любого candidate
        2. TP должны совпадать с candidates (± 1% buffer)
        3. SL должен быть candidate ± ATR
        4. 🆕 Entry distance от current_price <= min(MAX_PCT_BY_TF, ATR * K)

        Если не проходит - корректируем к ближайшему валидному уровню.
        Если entry слишком далеко от текущей цены - сценарий INVALID.

        Args:
            scenarios: Сценарии от LLM
            candidates: {
                "supports": [price1, price2, ...],   # NEAR levels only (filtered)
                "resistances": [price1, price2, ...] # NEAR levels only (filtered)
            }
            atr: ATR value
            current_price: Current price for % calculations
            timeframe: Timeframe for adaptive distance limits

        Returns:
            Validated/fixed scenarios with validation_status field
        """
        if not scenarios:
            return scenarios

        # Собираем все candidates в один set (already filtered to near)
        all_candidates = set()
        for key in ["supports", "resistances"]:
            for price in candidates.get(key, []):
                if price and price > 0:
                    all_candidates.add(round(price, 2))

        # Добавляем current_price как валидный уровень
        all_candidates.add(round(current_price, 2))

        if not all_candidates:
            logger.warning("No candidates for validation, skipping")
            for sc in scenarios:
                sc["validation_status"] = "skipped_no_candidates"
            return scenarios

        # Tolerance: 1.5% от цены или 1.5*ATR (что больше)
        pct_tolerance = current_price * 0.015
        atr_tolerance = atr * 1.5 if atr else pct_tolerance
        tolerance = max(pct_tolerance, atr_tolerance)

        validated_scenarios = []

        for sc in scenarios:
            validation_issues = []
            fixed_fields = []

            # 1. Validate entry_plan orders
            entry_plan = sc.get("entry_plan", {})
            entry_orders = entry_plan.get("orders", [])

            for i, order in enumerate(entry_orders):
                order_price = order.get("price", 0)
                source_level = order.get("source_level", "unknown")

                if order_price > 0:
                    nearest_to_order = min(all_candidates, key=lambda x: abs(x - order_price))
                    order_delta = abs(nearest_to_order - order_price)

                    if order_delta > tolerance:
                        validation_issues.append(
                            f"Order[{i}] price {order_price:.2f} (source: {source_level}) "
                            f"too far from nearest candidate {nearest_to_order:.2f} "
                            f"(delta={order_delta:.2f}, tol={tolerance:.2f})"
                        )
                        # Fix: snap to nearest candidate
                        sc["entry_plan"]["orders"][i]["price"] = round(nearest_to_order, 2)
                        fixed_fields.append(f"order_{i}")

            # Validate that size_pct sums to 100
            total_size_pct = sum(order.get("size_pct", 0) for order in entry_orders)
            if entry_orders and abs(total_size_pct - 100) > 5:
                validation_issues.append(
                    f"Orders size_pct sum to {total_size_pct}%, should be 100%"
                )
                # Fix: normalize to 100%
                if total_size_pct > 0:
                    for i, order in enumerate(entry_orders):
                        normalized = round((order.get("size_pct", 0) / total_size_pct) * 100)
                        sc["entry_plan"]["orders"][i]["size_pct"] = normalized
                    fixed_fields.append("size_pct_normalized")

            # 1.5. CRITICAL: Validate entry distance from current price
            # HYBRID approach: entry_distance <= min(MAX_PCT_BY_TF, ATR * K / price * 100)
            entry_unrealistic = False
            if entry_orders:
                order_prices = [o.get("price", 0) for o in entry_orders if o.get("price", 0) > 0]
                if order_prices:
                    entry_avg = sum(order_prices) / len(order_prices)
                    entry_distance_pct = abs(entry_avg - current_price) / current_price * 100

                    # Get TF-based max distance
                    max_pct_by_tf = MAX_ENTRY_DISTANCE_PCT_BY_TF.get(
                        timeframe, MAX_ENTRY_DISTANCE_PCT_DEFAULT
                    )

                    # Get ATR-based max distance
                    atr_multiplier = ATR_ENTRY_MULTIPLIER_BY_TF.get(
                        timeframe, ATR_ENTRY_MULTIPLIER_DEFAULT
                    )
                    max_pct_by_atr = (atr * atr_multiplier / current_price * 100) if atr > 0 else max_pct_by_tf

                    # HYBRID: use minimum of both (more conservative)
                    max_entry_distance_pct = min(max_pct_by_tf, max_pct_by_atr)

                    if entry_distance_pct > max_entry_distance_pct:
                        entry_unrealistic = True
                        validation_issues.append(
                            f"CRITICAL: Entry avg {entry_avg:.2f} is {entry_distance_pct:.1f}% "
                            f"away from current price {current_price:.2f} "
                            f"(max allowed: {max_entry_distance_pct:.1f}% "
                            f"[TF={max_pct_by_tf}%, ATR={max_pct_by_atr:.1f}%])"
                        )
                        logger.warning(
                            f"🚫 Scenario '{sc.get('name')}' INVALID ({timeframe}): "
                            f"entry {entry_avg:.2f} is {entry_distance_pct:.1f}% from current {current_price:.2f} "
                            f"(max: {max_entry_distance_pct:.1f}%)"
                        )

            # 2. Validate stop loss
            stop_loss = sc.get("stop_loss", {})
            recommended_sl = stop_loss.get("recommended", 0)

            if recommended_sl > 0:
                # SL должен быть candidate ± ATR
                sl_tolerance = atr * 2.0 if atr else tolerance
                nearest_to_sl = min(all_candidates, key=lambda x: abs(x - recommended_sl))
                sl_delta = abs(nearest_to_sl - recommended_sl)

                if sl_delta > sl_tolerance:
                    validation_issues.append(
                        f"SL {recommended_sl:.2f} too far from nearest candidate "
                        f"{nearest_to_sl:.2f} (delta={sl_delta:.2f})"
                    )
                    # Fix: adjust to candidate ± ATR
                    bias = sc.get("bias", "long")
                    atr_offset = atr if atr else current_price * 0.01
                    if bias == "long":
                        sc["stop_loss"]["recommended"] = round(nearest_to_sl - atr_offset, 2)
                    else:
                        sc["stop_loss"]["recommended"] = round(nearest_to_sl + atr_offset, 2)
                    fixed_fields.append("stop_loss")

            # 3. Validate targets (only TP1 - TP2/TP3 can be at distant levels)
            targets = sc.get("targets", [])
            tp1_tolerance = tolerance * 3.0  # TP1 может быть дальше от ближайшего уровня

            # Валидируем только TP1 на близость к уровню
            # TP2/TP3 могут быть на дальних целях - это нормальная торговая практика
            if targets and len(targets) > 0:
                tp1 = targets[0]
                tp1_price = tp1.get("price", 0)
                if tp1_price > 0:
                    nearest_to_tp1 = min(all_candidates, key=lambda x: abs(x - tp1_price))
                    tp1_delta = abs(nearest_to_tp1 - tp1_price)

                    if tp1_delta > tp1_tolerance:
                        validation_issues.append(
                            f"TP1 {tp1_price:.2f} too far from nearest candidate "
                            f"{nearest_to_tp1:.2f}"
                        )
                        # Fix: snap TP1 to nearest candidate
                        sc["targets"][0]["price"] = round(nearest_to_tp1, 2)
                        fixed_fields.append("TP1")

            # Set validation status
            if entry_unrealistic:
                # CRITICAL: Entry too far from current price - scenario is INVALID
                sc["validation_status"] = "invalid:entry_unrealistic"
                logger.error(
                    f"🚫 Scenario '{sc.get('name')}' REJECTED: entry too far from current price"
                )
                # Do NOT add to validated_scenarios - skip this scenario entirely
                continue
            elif not validation_issues:
                sc["validation_status"] = "valid"
            elif fixed_fields:
                sc["validation_status"] = f"fixed:{','.join(fixed_fields)}"
                logger.warning(
                    f"Scenario '{sc.get('name')}' validation issues: {validation_issues}"
                )
            else:
                sc["validation_status"] = "warning"

            validated_scenarios.append(sc)

        # Log validation summary
        valid_count = sum(1 for sc in validated_scenarios if sc.get("validation_status") == "valid")
        fixed_count = sum(1 for sc in validated_scenarios if sc.get("validation_status", "").startswith("fixed"))
        invalid_count = len(scenarios) - len(validated_scenarios)

        logger.info(
            f"✅ Validation: {valid_count} valid, {fixed_count} fixed, "
            f"{len(validated_scenarios) - valid_count - fixed_count} warnings, "
            f"{invalid_count} rejected (unrealistic entry)"
        )

        return validated_scenarios

    # =========================================================================
    # 🔥 RR CALCULATION & SANITY VALIDATION (Python > LLM для математики!)
    # =========================================================================

    def _calculate_rr_and_validate(
        self,
        scenarios: List[Dict],
        current_price: float,
        atr: float
    ) -> List[Dict]:
        """
        Рассчитать RR в Python + санити-проверки (LLM не считает RR).

        Формулы:
            entry_ref = P_avg (взвешенная средняя из entry_plan.orders)
                        или avg(entry_min, entry_max) для legacy
            risk_per_unit = |entry_ref - stop|
            reward_per_unit = |tp - entry_ref|
            RR = reward / risk

        Санити-проверки:
            1. LONG: stop < entry_min (стоп должен быть ниже зоны входа)
            2. SHORT: stop > entry_max (стоп должен быть выше зоны входа)
            3. entry_min < entry_max
            4. TP в правильном направлении (LONG: tp > entry_ref, SHORT: tp < entry_ref)
            5. RR адекватность: RR_TP1 > 10 на 4H = outlier (warning)
            6. risk_per_unit > 0 (иначе invalid)

        Args:
            scenarios: Сценарии после _validate_scenarios
            current_price: Текущая цена
            atr: ATR для авто-фиксов

        Returns:
            Сценарии с пересчитанным RR и статусом валидации
        """
        if not scenarios:
            return scenarios

        validated = []

        for sc in scenarios:
            issues = []
            bias = sc.get("bias", "long").lower()
            is_long = bias == "long"

            # === 1. Определяем entry_ref ===
            entry_plan = sc.get("entry_plan", {})
            entry_orders = entry_plan.get("orders", [])

            if entry_orders:
                # P_avg = Σ(w_i * p_i) где w_i = size_pct / 100
                total_weight = sum(o.get("size_pct", 0) for o in entry_orders)
                if total_weight > 0:
                    entry_ref = sum(
                        o.get("price", 0) * (o.get("size_pct", 0) / total_weight)
                        for o in entry_orders
                    )
                else:
                    entry_ref = entry_orders[0].get("price", current_price)

                # entry_min/max из orders
                order_prices = [o.get("price", 0) for o in entry_orders if o.get("price", 0) > 0]
                entry_min = min(order_prices) if order_prices else current_price
                entry_max = max(order_prices) if order_prices else current_price
            else:
                # Legacy fallback: entry zone
                entry = sc.get("entry", {})
                entry_min = entry.get("price_min", current_price)
                entry_max = entry.get("price_max", current_price)
                entry_ref = (entry_min + entry_max) / 2

            # === 2. Получаем stop ===
            stop_loss = sc.get("stop_loss", {})
            stop = stop_loss.get("recommended", 0)

            if stop <= 0:
                issues.append("invalid_stop: stop <= 0")
                # Fallback: рассчитываем RR с default 1% stop
                stop = entry_ref * (0.99 if is_long else 1.01)
                issues.append(f"fallback_stop_1pct={stop:.2f}")

            # === 3. Санити: stop vs entry zone ===
            if is_long:
                # LONG: stop должен быть ниже entry_min
                if stop >= entry_min:
                    issues.append(
                        f"stop_inside_entry_zone: stop={stop:.2f} >= entry_min={entry_min:.2f}"
                    )
                    # Auto-fix: ставим stop на ATR ниже entry_min
                    atr_offset = atr if atr else current_price * 0.01
                    fixed_stop = round(entry_min - atr_offset, 2)
                    sc["stop_loss"]["recommended"] = fixed_stop
                    sc["stop_loss"]["conservative"] = round(fixed_stop - atr_offset * 0.5, 2)
                    sc["stop_loss"]["aggressive"] = round(entry_min - atr_offset * 0.5, 2)
                    stop = fixed_stop
                    issues.append(f"auto_fixed_stop_to={fixed_stop:.2f}")
            else:
                # SHORT: stop должен быть выше entry_max
                if stop <= entry_max:
                    issues.append(
                        f"stop_inside_entry_zone: stop={stop:.2f} <= entry_max={entry_max:.2f}"
                    )
                    # Auto-fix: ставим stop на ATR выше entry_max
                    atr_offset = atr if atr else current_price * 0.01
                    fixed_stop = round(entry_max + atr_offset, 2)
                    sc["stop_loss"]["recommended"] = fixed_stop
                    sc["stop_loss"]["conservative"] = round(fixed_stop + atr_offset * 0.5, 2)
                    sc["stop_loss"]["aggressive"] = round(entry_max + atr_offset * 0.5, 2)
                    stop = fixed_stop
                    issues.append(f"auto_fixed_stop_to={fixed_stop:.2f}")

            # === 4. Вычисляем risk_per_unit ===
            risk_per_unit = abs(entry_ref - stop)

            if risk_per_unit <= 0:
                issues.append(f"zero_risk: entry_ref={entry_ref:.2f}, stop={stop:.2f}")
                # Fallback: используем 1% от entry как risk
                risk_per_unit = entry_ref * 0.01
                issues.append(f"fallback_risk_1pct={risk_per_unit:.4f}")

            # === 5. Пересчитываем RR для каждого TP ===
            targets = sc.get("targets", [])
            rr_outlier = False

            for i, tp in enumerate(targets):
                tp_price = tp.get("price", 0)

                if tp_price <= 0:
                    # Invalid price - ставим RR = 0
                    sc["targets"][i]["rr"] = 0.0
                    issues.append(f"TP{i+1}_invalid_price=0")
                    continue

                # Санити: TP в правильном направлении
                if is_long and tp_price <= entry_ref:
                    issues.append(f"TP{i+1}_wrong_direction: {tp_price:.2f} <= entry_ref={entry_ref:.2f}")
                    # Не фиксим автоматически - LLM должен дать правильные уровни
                elif not is_long and tp_price >= entry_ref:
                    issues.append(f"TP{i+1}_wrong_direction: {tp_price:.2f} >= entry_ref={entry_ref:.2f}")

                # Вычисляем reward и RR
                reward_per_unit = abs(tp_price - entry_ref)
                rr = round(reward_per_unit / risk_per_unit, 2)

                # Добавляем RR (LLM не считает, только Python)
                sc["targets"][i]["rr"] = rr

                # RR outlier check (для 4H: RR > 10 на TP1 = подозрительно)
                if i == 0 and rr > 10:
                    rr_outlier = True
                    issues.append(f"TP1_rr_outlier: RR={rr:.1f} (>10)")

            # === 6. Добавляем метаданные расчёта ===
            sc["rr_calculation"] = {
                "entry_ref": round(entry_ref, 2),
                "entry_min": round(entry_min, 2),
                "entry_max": round(entry_max, 2),
                "stop": round(stop, 2),
                "risk_per_unit": round(risk_per_unit, 2),
                "risk_pct": round((risk_per_unit / entry_ref) * 100, 2) if entry_ref > 0 else 0
            }

            # === 7. Итоговый статус ===
            if not issues:
                sc["rr_validation"] = "valid"
            elif rr_outlier:
                sc["rr_validation"] = "warning_outlier"
            else:
                sc["rr_validation"] = "fixed"

            sc["rr_issues"] = issues if issues else None

            validated.append(sc)

        # Логируем результаты
        valid_count = sum(1 for s in validated if s.get("rr_validation") == "valid")
        fixed_count = sum(1 for s in validated if s.get("rr_validation") == "fixed")
        invalid_count = sum(1 for s in validated if s.get("rr_validation") == "invalid")

        logger.info(
            f"📐 RR recalculation: {valid_count} valid, {fixed_count} fixed, "
            f"{invalid_count} invalid out of {len(validated)}"
        )

        # Фильтруем invalid сценарии
        return [s for s in validated if s.get("rr_validation") != "invalid"]

    # =========================================================================
    # 🗑️ OLD RULE-BASED METHODS REMOVED (700+ lines)
    # =========================================================================
    # Удалены методы:
    # - _ai_adjust_scenario_probabilities() - не нужен, AI сразу генерирует правильные вероятности
    # - _rule_based_adjustment() - fallback не нужен
    # - _generate_bullish_scenario() - заменен на AI-driven генерацию
    # - _generate_bearish_scenario() - заменен на AI-driven генерацию
    # - _generate_range_scenario() - заменен на AI-driven генерацию
    #
    # Теперь вся генерация сценариев происходит в _ai_generate_scenarios()
    # который отправляет ВСЕ данные в LLM и получает готовые сценарии
    # =========================================================================

    def _assess_data_quality(
        self,
        klines: pd.DataFrame,
        indicators: Dict,
        funding: Optional[Dict],
        oi: Optional[Dict],
        liquidation_data: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        Оценить качество данных для анализа

        Returns:
            {
                "completeness": 0-100,
                "sources": [...],
                "warnings": [...]
            }
        """
        completeness = 0
        sources = []
        warnings = []

        # Klines data
        if klines is not None and len(klines) >= 100:
            completeness += 25
            sources.append("candlestick_data")
        else:
            warnings.append("Insufficient candlestick data")

        # Technical indicators
        if indicators and len(indicators) >= 10:
            completeness += 25
            sources.append("technical_indicators")
        else:
            warnings.append("Limited technical indicators")

        # Funding rate
        if funding:
            completeness += 20
            sources.append("funding_rates")
        else:
            warnings.append("Funding rate unavailable")

        # Open Interest
        if oi:
            completeness += 15
            sources.append("open_interest")
        else:
            warnings.append("Open Interest unavailable")

        # Liquidation data
        if liquidation_data and liquidation_data.get("total_liquidations", 0) > 0:
            completeness += 15
            sources.append("liquidation_history")
        else:
            warnings.append("Liquidation data unavailable (requires API keys)")

        return {
            "completeness": completeness,
            "sources": sources,
            "warnings": warnings if warnings else None
        }


# Singleton instance
futures_analysis_service = FuturesAnalysisService()
