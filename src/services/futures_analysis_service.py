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
from src.services.level_quality_service import level_quality_service
from src.services.scenario_metrics_service import scenario_metrics_service
from config.archetype_priors import validate_outcome_probs, ScenarioArchetype

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

# Modular components (refactored)
from src.services.futures_analysis.price_structure import PriceStructureAnalyzer
from src.services.futures_analysis.liquidation_analyzer import LiquidationAnalyzer
from src.services.futures_analysis.scenario_validator import ScenarioValidator
from src.services.futures_analysis.learning_calibrator import LearningCalibrator
from src.services.futures_analysis.scenario_generator import ScenarioGenerator


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

        # Modular components (refactored)
        self._price_structure_analyzer = PriceStructureAnalyzer()
        self._liquidation_analyzer = LiquidationAnalyzer()
        self._scenario_validator = ScenarioValidator()
        self._learning_calibrator = LearningCalibrator()
        self._scenario_generator = ScenarioGenerator(openai_service=self.openai)

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
                enriched_data=enriched_data,
                klines_df=klines_df,  # 🆕 For level quality service
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

            # 🆕 Separate scenarios by quality tier
            # "high" and "acceptable" → main scenarios (for auto-trading)
            # "low" → low_quality scenarios (for manual review / learning)
            scenarios_valid = [
                s for s in scenarios
                if s.get("quality_tier") in ("high", "acceptable", None)
            ]
            scenarios_low_quality = [
                s for s in scenarios
                if s.get("quality_tier") == "low"
            ]

            result = {
                "success": True,
                "symbol": symbol,
                "timeframe": timeframe,
                "analysis_timestamp": datetime.utcnow().isoformat() + "Z",
                "analysis_id": analysis_id,  # 🆕 For feedback loop tracking
                "current_price": round(current_price, 2),
                "market_context": market_context,
                "scenarios": scenarios_valid,  # Only high/acceptable quality
                "scenarios_low_quality": scenarios_low_quality,  # 🆕 For UI display / learning
                "key_levels": key_levels,
                "data_quality": data_quality,
                # 🆕 NO-TRADE signal (first-class citizen)
                "no_trade": no_trade_signal,
                "metadata": {
                    "has_liquidation_data": liquidation_data is not None,
                    "funding_available": funding_data is not None,
                    "candles_analyzed": len(klines_df),
                    "timeframes_analyzed": list(mtf_data.keys()) if mtf_data else [],
                    "total_scenarios_generated": len(scenarios),  # 🆕 Total before split
                    "low_quality_count": len(scenarios_low_quality)
                }
            }

            logger.info(
                f"Analysis complete for {symbol}: "
                f"{len(scenarios_valid)} valid + {len(scenarios_low_quality)} low quality scenarios, "
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
        atr_pct = indicators.get("atr_percent", 2.0)
        context["volatility"] = indicators.get("volatility", "medium")
        context["atr_percent"] = atr_pct  # Числовое значение для LLM валидатора

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
        Рассчитать сжатую структуру цены для LLM.

        Делегирует к PriceStructureAnalyzer (backward compatibility wrapper).
        """
        return self._price_structure_analyzer.calculate(
            klines=klines,
            current_price=current_price,
            indicators=indicators,
            timeframe=timeframe
        )

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
        Агрегировать liquidation data в clusters для LLM.

        Делегирует к LiquidationAnalyzer (backward compatibility wrapper).
        """
        return self._liquidation_analyzer.aggregate_clusters(
            liquidation_data=liquidation_data,
            current_price=current_price
        )

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
        enriched_data: Optional[Dict] = None,
        klines_df: Optional[pd.DataFrame] = None,  # 🆕 For level quality service
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
                enriched_data=enriched_data,
                klines_df=klines_df,  # 🆕 For level quality service
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
            # Get mode config for min_tp1_rr threshold
            from src.services.trading_modes import get_mode_config
            mode_config = get_mode_config(mode)

            final_scenarios = self._calculate_rr_and_validate(
                scenarios=validated_scenarios,
                current_price=current_price,
                atr=atr,
                min_tp1_rr=mode_config.min_tp1_rr
            )

            # 📊 Нормализуем веса сценариев (Python > LLM)
            final_scenarios = scenario_metrics_service.normalize_weights(final_scenarios)
            weights_info = [f"{s.get('id')}={s.get('scenario_weight', 0):.2f}" for s in final_scenarios]
            logger.info(f"📊 Weights normalized: {weights_info}")

            # 🆕 LLM VALIDATION: DISABLED - Python validation is sufficient
            # TODO: Можно включить позже для дополнительных проверок
            # final_scenarios = await self._llm_validate_scenarios(
            #     scenarios=final_scenarios,
            #     market_context=market_context,
            #     candidates=candidates,
            #     current_price=current_price,
            # )

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
        enriched_data: Optional[Dict] = None,
        klines_df: Optional[pd.DataFrame] = None,
    ) -> tuple:
        """Делегирует к ScenarioGenerator.ai_generate()"""
        return await self._scenario_generator.ai_generate(
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
            enriched_data=enriched_data,
            klines_df=klines_df,
        )

    # === END OF _ai_generate_scenarios DELEGATION ===
    # OLD CODE REMOVED (820+ lines) - now in ScenarioGenerator.ai_generate()
    # =========================================================================
    # 🆕 LLM SCENARIO VALIDATION (делегирует к ScenarioGenerator)
    # =========================================================================

    async def _llm_validate_scenarios(
        self,
        scenarios: List[Dict],
        market_context: Dict,
        candidates: Dict,
        current_price: float,
    ) -> List[Dict]:
        """Делегирует к ScenarioGenerator.llm_validate()"""
        return await self._scenario_generator.llm_validate(
            scenarios=scenarios,
            market_context=market_context,
            candidates=candidates,
            current_price=current_price
        )

    # =========================================================================
    # 🆕 LEARNING SYSTEM INTEGRATION (делегирует к LearningCalibrator)
    # =========================================================================

    async def _apply_learning_calibration(
        self,
        scenarios: List[Dict],
        symbol: str,
        timeframe: str,
    ) -> List[Dict]:
        """Делегирует к LearningCalibrator.apply_calibration()"""
        return await self._learning_calibrator.apply_calibration(
            scenarios=scenarios,
            symbol=symbol,
            timeframe=timeframe
        )

    async def _apply_ev_calculation(
        self,
        scenarios: List[Dict],
        timeframe: str,
        volatility_regime: str = "normal",
    ) -> List[Dict]:
        """Делегирует к LearningCalibrator.apply_ev_calculation()"""
        return await self._learning_calibrator.apply_ev_calculation(
            scenarios=scenarios,
            timeframe=timeframe,
            volatility_regime=volatility_regime
        )

    async def _apply_class_stats(
        self,
        scenarios: List[Dict],
        symbol: str,
        timeframe: str,
        market_context: Dict,
    ) -> List[Dict]:
        """Делегирует к LearningCalibrator.apply_class_stats()"""
        return await self._learning_calibrator.apply_class_stats(
            scenarios=scenarios,
            symbol=symbol,
            timeframe=timeframe,
            market_context=market_context
        )

    async def _log_scenario_generation(
        self,
        analysis_id: str,
        scenarios: List[Dict],
        symbol: str,
        timeframe: str,
        market_context: Dict,
        user_id: int = 0,
        is_testnet: bool = False,
    ) -> None:
        """Делегирует к LearningCalibrator.log_generation()"""
        await self._learning_calibrator.log_generation(
            analysis_id=analysis_id,
            scenarios=scenarios,
            symbol=symbol,
            timeframe=timeframe,
            market_context=market_context,
            user_id=user_id,
            is_testnet=is_testnet
        )

    # =========================================================================
    # 🔥 SCENARIO VALIDATION (делегирует к ScenarioValidator)
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
        Валидатор сценариев - делегирует к ScenarioValidator.

        Backward compatibility wrapper.
        """
        return self._scenario_validator.validate(
            scenarios=scenarios,
            candidates=candidates,
            atr=atr,
            current_price=current_price,
            timeframe=timeframe
        )

    # =========================================================================
    # 🔥 RR CALCULATION (делегирует к ScenarioValidator)
    # =========================================================================

    def _calculate_rr_and_validate(
        self,
        scenarios: List[Dict],
        current_price: float,
        atr: float,
        min_tp1_rr: float = 0.7
    ) -> List[Dict]:
        """
        Рассчитать RR в Python - делегирует к ScenarioValidator.

        Backward compatibility wrapper.
        """
        return self._scenario_validator.calculate_rr(
            scenarios=scenarios,
            current_price=current_price,
            atr=atr,
            min_tp1_rr=min_tp1_rr
        )

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
