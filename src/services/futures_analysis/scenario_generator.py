# coding: utf-8
"""
Scenario Generator - генерация торговых сценариев через LLM.

Основной AI-driven engine системы анализа фьючерсов.
"""
import json
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

from .constants import (
    MAX_ENTRY_DISTANCE_PCT_BY_TF,
    MAX_ENTRY_DISTANCE_PCT_DEFAULT,
    filter_levels_by_distance,
)

# Config imports
from config.config import MODEL_SCENARIO_GENERATOR
FUTURES_MODEL = MODEL_SCENARIO_GENERATOR

# Service imports
from src.services.trading_modes import get_mode_config, build_mode_profile_block, get_mode_notes_schema
from src.services.level_quality_service import level_quality_service
from src.services.scenario_metrics_service import scenario_metrics_service


class ScenarioGenerator:
    """
    AI-driven генератор торговых сценариев.

    Отвечает за:
    - Подготовку данных для LLM
    - Вызов OpenAI для генерации сценариев
    - Post-processing ответа LLM
    """

    def __init__(self, openai_service=None):
        """
        Args:
            openai_service: OpenAIService instance (инжектируется оркестратором)
        """
        self.openai = openai_service
        logger.debug("ScenarioGenerator initialized")

    async def generate(
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
        klines_df: Optional[pd.DataFrame] = None,
        validator: "ScenarioValidator" = None,
        calibrator: "LearningCalibrator" = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict]]:
        """
        Генерация торговых сценариев.

        Returns:
            (scenarios, no_trade_signal)
        """
        logger.info("Generating scenarios with AI (not rule-based formulas)...")

        try:
            scenarios, no_trade_signal = await self.ai_generate(
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

            logger.info(f"AI generated {len(scenarios)} scenarios")
            if no_trade_signal:
                logger.info(f"NO-TRADE signal received: {no_trade_signal.get('category')}")

            # VALIDATION: Проверяем что LLM использовал NEAR уровни
            atr = indicators.get("atr", 0)
            max_dist_pct = MAX_ENTRY_DISTANCE_PCT_BY_TF.get(timeframe, MAX_ENTRY_DISTANCE_PCT_DEFAULT)

            # Get mode config for min_tp1_rr threshold
            mode_config_for_rr = get_mode_config(mode)

            # Collect all levels
            all_resistances = list(key_levels.get("resistance", []))
            all_supports = list(key_levels.get("support", []))
            if price_structure:
                all_resistances.extend([sh["price"] for sh in price_structure.get("swing_highs", []) if sh.get("price")])
                all_supports.extend([sl["price"] for sl in price_structure.get("swing_lows", []) if sl.get("price")])

            # Filter to near + macro (macro нужен для auto-repair TP1)
            resistance_near, resistance_macro = filter_levels_by_distance(
                list(set(all_resistances)), current_price, max_dist_pct, side="short"
            )
            support_near, support_macro = filter_levels_by_distance(
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

            # 🔧 Candidates для валидатора: near + macro (для auto-repair TP1)
            candidates = {
                "supports": support_near + dynamic_levels,
                "resistances": resistance_near + dynamic_levels,
                # 🆕 Добавляем macro для fallback при auto-repair TP1
                "supports_macro": support_macro,
                "resistances_macro": resistance_macro,
            }

            # 🔍 ДИАГНОСТИКА: Логируем доступные уровни для анализа
            logger.debug(
                f"📊 TP candidates available: "
                f"R_near={len(resistance_near)}, R_macro={len(resistance_macro)}, "
                f"S_near={len(support_near)}, S_macro={len(support_macro)}"
            )

            # Validate scenarios
            if validator:
                validated_scenarios = validator.validate(
                    scenarios=scenarios,
                    candidates=candidates,
                    atr=atr,
                    current_price=current_price,
                    timeframe=timeframe
                )

                # Рассчитываем RR в Python (не доверяем LLM математику!)
                # 🔧 Передаём candidates для auto-repair TP1
                final_scenarios = validator.calculate_rr(
                    scenarios=validated_scenarios,
                    current_price=current_price,
                    atr=atr,
                    min_tp1_rr=mode_config_for_rr.min_tp1_rr,
                    candidates=candidates  # near + macro для auto-repair
                )
            else:
                final_scenarios = scenarios

            # Нормализуем веса и вычисляем final_score (Python > LLM)
            final_scenarios = scenario_metrics_service.normalize_weights(final_scenarios)
            scores_info = [
                f"#{s.get('id')}:score={s.get('final_score', 0):.2f}(w={s.get('weight_raw', 0):.2f},c={s.get('confidence', 0):.2f})"
                for s in final_scenarios
            ]
            logger.info(f"Final scores: {scores_info}")

            # Learning calibration (если доступен calibrator)
            if calibrator:
                final_scenarios = await calibrator.apply_calibration(
                    scenarios=final_scenarios,
                    symbol=symbol,
                    timeframe=timeframe,
                )

                # EV calculation
                volatility = market_context.get("volatility", "normal")
                final_scenarios = await calibrator.apply_ev_calculation(
                    scenarios=final_scenarios,
                    timeframe=timeframe,
                    volatility_regime=volatility,
                )

                # Class stats context gates
                final_scenarios = await calibrator.apply_class_stats(
                    scenarios=final_scenarios,
                    symbol=symbol,
                    timeframe=timeframe,
                    market_context=market_context,
                )

            return final_scenarios, no_trade_signal

        except Exception as e:
            logger.error(f"AI scenario generation failed: {e}")
            raise RuntimeError(f"Failed to generate AI scenarios: {e}")

    async def ai_generate(
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
    ) -> Tuple[List[Dict], Optional[Dict]]:
        """
        MAIN AI ENGINE: LLM анализирует рынок и генерирует торговые сценарии.

        Returns:
            (scenarios, no_trade_signal)
        """
        # Форматируем данные для LLM
        supports = key_levels.get("support", [])
        resistances = key_levels.get("resistance", [])
        atr = indicators.get("atr")
        atr_pct = indicators.get("atr_percent", 2.0)
        ema_levels = key_levels.get("ema_levels", {})
        vwap = key_levels.get("vwap", {})

        # Fallback candidates из swing points если основные пустые
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

        # PRE-FILTER: Split levels into near (actionable) and macro (context)
        max_dist_pct = MAX_ENTRY_DISTANCE_PCT_BY_TF.get(timeframe, MAX_ENTRY_DISTANCE_PCT_DEFAULT)

        # Collect all resistance sources
        all_resistances = list(resistances)
        if price_structure:
            all_resistances.extend([sh["price"] for sh in price_structure.get("swing_highs", []) if sh.get("price")])

        # Collect all support sources
        all_supports = list(supports)
        if price_structure:
            all_supports.extend([sl["price"] for sl in price_structure.get("swing_lows", []) if sl.get("price")])

        # Filter into near/macro
        resistance_near, resistance_macro = filter_levels_by_distance(
            list(set(all_resistances)), current_price, max_dist_pct, side="short"
        )
        support_near, support_macro = filter_levels_by_distance(
            list(set(all_supports)), current_price, max_dist_pct, side="long"
        )

        logger.debug(
            f"Level filtering ({timeframe}, max {max_dist_pct}%): "
            f"R_near={len(resistance_near)}, R_macro={len(resistance_macro)}, "
            f"S_near={len(support_near)}, S_macro={len(support_macro)}"
        )

        # 🔧 ROBUST FIX: Расширение near до минимума через macro fallback
        MIN_TP_CANDIDATES = 3

        # Расширяем resistance_near если мало кандидатов
        if len(resistance_near) < MIN_TP_CANDIDATES and resistance_macro:
            # Берём ближайшие macro levels (отсортированы по расстоянию)
            resistance_macro_sorted = sorted(resistance_macro, key=lambda x: abs(x - current_price))
            needed = MIN_TP_CANDIDATES - len(resistance_near)
            resistance_near_extended = resistance_near + resistance_macro_sorted[:needed]
            logger.info(
                f"🔧 Extended resistance_near: {len(resistance_near)} → {len(resistance_near_extended)} "
                f"(added {needed} from macro)"
            )
            resistance_near = resistance_near_extended

        # Расширяем support_near если мало кандидатов
        if len(support_near) < MIN_TP_CANDIDATES and support_macro:
            support_macro_sorted = sorted(support_macro, key=lambda x: abs(x - current_price))
            needed = MIN_TP_CANDIDATES - len(support_near)
            support_near_extended = support_near + support_macro_sorted[:needed]
            logger.info(
                f"🔧 Extended support_near: {len(support_near)} → {len(support_near_extended)} "
                f"(added {needed} from macro)"
            )
            support_near = support_near_extended

        # Build quality-filtered level candidates with level_id
        levels_meta = enriched_data.get("levels_meta", {}) if enriched_data else {}
        support_meta = levels_meta.get("support", []) if isinstance(levels_meta.get("support"), list) else []
        resistance_meta = levels_meta.get("resistance", []) if isinstance(levels_meta.get("resistance"), list) else []

        level_candidates = level_quality_service.build_level_candidates(
            support_near=support_near,
            resistance_near=resistance_near,
            support_meta=support_meta,
            resistance_meta=resistance_meta,
            htf_levels=key_levels.get("htf_levels", []),
            current_price=current_price,
            atr=atr if atr else 0,
            klines=klines_df,
            ema_20=ema_levels.get("ema_20", {}).get("price") if ema_levels else None,
            ema_50=ema_levels.get("ema_50", {}).get("price") if ema_levels else None,
            ema_200=ema_levels.get("ema_200", {}).get("price") if ema_levels else None,
            vwap=vwap.get("price") if vwap else None,
        )

        # Build pre-calculated metrics for prompt
        base_metrics = scenario_metrics_service.build_metrics_for_prompt(
            current_price=current_price,
            atr=atr if atr else 0,
        )

        # PRE-CALCULATE path blockers and entry squeeze for BOTH directions
        # This gives LLM actionable constraints BEFORE generation
        all_levels = (
            level_candidates.support_near +
            level_candidates.resistance_near +
            level_candidates.swing_highs +
            level_candidates.swing_lows +
            level_candidates.htf_levels
        )

        # Potential TP1 targets for pre-calculation
        # Long: nearest resistance above current_price
        # Short: nearest support below current_price
        resistances_above = sorted([
            l["price"] for l in all_levels
            if l.get("level_type") == "resistance" and l["price"] > current_price
        ])
        supports_below = sorted([
            l["price"] for l in all_levels
            if l.get("level_type") == "support" and l["price"] < current_price
        ], reverse=True)

        potential_tp1_long = resistances_above[0] if resistances_above else current_price * 1.02
        potential_tp1_short = supports_below[0] if supports_below else current_price * 0.98

        # Estimate R using typical stop distance (1 ATR)
        estimated_R = atr if atr and atr > 0 else current_price * 0.01

        # Calculate pre-gates for LONG
        long_path_blockers = level_quality_service.calculate_path_blockers(
            entry=current_price,
            tp1=potential_tp1_long,
            all_levels=all_levels,
            bias="long",
        )
        long_entry_squeeze = level_quality_service.calculate_entry_squeeze(
            entry=current_price,
            R=estimated_R,
            all_levels=all_levels,
            bias="long",
        )

        # Calculate pre-gates for SHORT
        short_path_blockers = level_quality_service.calculate_path_blockers(
            entry=current_price,
            tp1=potential_tp1_short,
            all_levels=all_levels,
            bias="short",
        )
        short_entry_squeeze = level_quality_service.calculate_entry_squeeze(
            entry=current_price,
            R=estimated_R,
            all_levels=all_levels,
            bias="short",
        )

        # Get mode configuration early (needed for pre_gates)
        mode_config = get_mode_config(mode)

        # Build pre-gates dict for prompt
        pre_gates = {
            "long": {
                "path_blockers": [b["level_id"] for b in long_path_blockers.blockers],
                "path_clear": long_path_blockers.path_clear,
                "entry_squeezed": long_entry_squeeze.entry_is_squeezed,
                "squeeze_distance_R": long_entry_squeeze.nearest_opposing_distance_R,
                "potential_tp1": round(potential_tp1_long, 2),
            },
            "short": {
                "path_blockers": [b["level_id"] for b in short_path_blockers.blockers],
                "path_clear": short_path_blockers.path_clear,
                "entry_squeezed": short_entry_squeeze.entry_is_squeezed,
                "squeeze_distance_R": short_entry_squeeze.nearest_opposing_distance_R,
                "potential_tp1": round(potential_tp1_short, 2),
            },
            "estimated_R": round(estimated_R, 2),
            # 🆕 Min RR threshold from mode config
            "min_tp1_rr": mode_config.min_tp1_rr,
        }

        logger.debug(
            f"Level candidates: support={len(level_candidates.support_near)}, "
            f"resistance={len(level_candidates.resistance_near)}, "
            f"swings={len(level_candidates.swing_highs) + len(level_candidates.swing_lows)}"
        )
        logger.debug(
            f"Pre-gates: LONG path_clear={long_path_blockers.path_clear}, squeeze={long_entry_squeeze.entry_is_squeezed}; "
            f"SHORT path_clear={short_path_blockers.path_clear}, squeeze={short_entry_squeeze.entry_is_squeezed}"
        )

        # Собираем все данные в один JSON объект
        market_data = self._build_market_data(
            symbol=symbol,
            timeframe=timeframe,
            current_price=current_price,
            market_context=market_context,
            indicators=indicators,
            price_structure=price_structure,
            resistance_near=resistance_near,
            resistance_macro=resistance_macro,
            support_near=support_near,
            support_macro=support_macro,
            ema_levels=ema_levels,
            vwap=vwap,
            liquidation_clusters=liquidation_clusters,
            funding=funding,
            ls_ratio=ls_ratio,
            patterns=patterns,
            enriched_data=enriched_data,
            level_candidates=level_candidates,
            base_metrics=base_metrics,
            pre_gates=pre_gates,
            atr=atr,
            atr_pct=atr_pct,
        )

        # Build MODE PROFILE block (mode_config already obtained above)
        mode_profile_block = build_mode_profile_block(mode_config)

        # Build prompt
        prompt = self._build_prompt(market_data, mode_profile_block, max_scenarios, timeframe)

        logger.debug("Sending market data to AI for scenario generation...")

        # JSON Schema для ГАРАНТИРОВАННОГО валидного ответа
        json_schema = self._build_json_schema()

        # Вызываем LLM с ГАРАНТИЕЙ валидного JSON
        ai_result = await self.openai.structured_completion(
            prompt=prompt,
            json_schema=json_schema,
            model=FUTURES_MODEL
        )

        scenarios = ai_result.get("scenarios", [])
        no_trade_raw = ai_result.get("no_trade")

        logger.info(f"AI Market Summary: {ai_result.get('market_summary', 'N/A')}")
        if no_trade_raw and no_trade_raw.get("should_not_trade"):
            logger.warning(f"NO-TRADE SIGNAL: {no_trade_raw.get('category')} - {no_trade_raw.get('reasons', [])}")
        logger.info(f"AI generated {len(scenarios)} scenarios, primary: #{ai_result.get('primary_scenario_id')}")

        # Адаптируем структуру под API Pydantic модели
        adapted_scenarios = self._adapt_scenarios(
            scenarios=scenarios,
            atr=atr,
            atr_pct=atr_pct,
            timeframe=timeframe,
        )

        # Гарантируем diversity (min 1 long + 1 short)
        final_scenarios = self._ensure_diversity(adapted_scenarios, max_scenarios)

        return final_scenarios, no_trade_raw

    def _build_market_data(
        self,
        symbol: str,
        timeframe: str,
        current_price: float,
        market_context: Dict,
        indicators: Dict,
        price_structure: Optional[Dict],
        resistance_near: List,
        resistance_macro: List,
        support_near: List,
        support_macro: List,
        ema_levels: Dict,
        vwap: Dict,
        liquidation_clusters: Optional[Dict],
        funding: Optional[Dict],
        ls_ratio: Optional[Dict],
        patterns: Optional[Dict],
        enriched_data: Optional[Dict],
        level_candidates,
        base_metrics: Dict,
        pre_gates: Dict,
        atr: Optional[float],
        atr_pct: float,
    ) -> Dict:
        """Собрать все market данные в один JSON объект."""
        return {
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

            # Price Structure (сжатая структура цены)
            "structure": price_structure if price_structure else {},

            # Key Levels: SPLIT into near (actionable) vs macro (context)
            "levels": {
                "resistance_near": resistance_near[:5],
                "support_near": support_near[:5],
                "resistance_macro": resistance_macro[:3],
                "support_macro": support_macro[:3],
                "ema_20": ema_levels.get("ema_20", {}).get("price") if ema_levels else None,
                "ema_50": ema_levels.get("ema_50", {}).get("price") if ema_levels else None,
                "ema_200": ema_levels.get("ema_200", {}).get("price") if ema_levels else None,
                "vwap": vwap.get("price") if vwap else None,
                "bb_upper": indicators.get("bb_upper"),
                "bb_lower": indicators.get("bb_lower")
            },

            # Technical Indicators
            "indicators": {
                "rsi": round(indicators.get("rsi", 50), 1),
                "adx": round(indicators.get("adx", 20), 1),
                "atr": round(atr, 2) if atr else None,
                "atr_percent": round(atr_pct, 2),
                "macd_signal": indicators.get("macd_signal"),
                "macd_histogram": round(indicators.get("macd_histogram", 0), 4)
            },

            # Liquidation Clusters
            "liquidation": liquidation_clusters if liquidation_clusters else {
                "clusters_above": [],
                "clusters_below": [],
                "liq_pressure_bias": "neutral"
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

            # Enriched Market Data
            "positioning": enriched_data.get("positioning") if enriched_data else None,
            "microstructure": enriched_data.get("microstructure") if enriched_data else None,
            "volatility_context": enriched_data.get("volatility_context") if enriched_data else None,
            "levels_meta": enriched_data.get("levels_meta") if enriched_data else None,
            "oi": enriched_data.get("oi") if enriched_data else None,

            # Quality-filtered level candidates
            "level_candidates": {
                "support_near": level_candidates.support_near,
                "resistance_near": level_candidates.resistance_near,
                "swing_highs": level_candidates.swing_highs,
                "swing_lows": level_candidates.swing_lows,
                "htf_levels": level_candidates.htf_levels,
                "range_high": level_candidates.range_high,
                "range_low": level_candidates.range_low,
            },

            # Pre-calculated metrics
            "metrics": base_metrics,

            # PRE-GENERATION GATES (Python-calculated constraints)
            "pre_gates": pre_gates,
        }

    def _build_prompt(self, market_data: Dict, mode_profile_block: str, max_scenarios: int, timeframe: str) -> str:
        """Build the prompt for LLM."""
        return f"""You are a professional futures trader with 10+ years of experience. Analyze the market data and generate trading scenarios with EXECUTION PLANS.

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

⚠️ **CRITICAL INVALIDATION RULES**:
- LONG: invalidation_price <= entry_min - buffer (buffer = max(0.5*ATR, 0.6%))
- SHORT: invalidation_price >= entry_max + buffer
- stop_loss MUST be between invalidation and entry (gap from invalidation >= 0.25 ATR)
- Hierarchy LONG: invalidation < stop_loss < entry_min
- Hierarchy SHORT: entry_max < stop_loss < invalidation
- cancel_if.close_below (LONG) = entry_min (cancel pending orders if level lost)
- Invalidation CANNOT equal any entry price — this is a logical contradiction!

🎯 **CRITICAL TARGET RULES (TP1 minimum R:R)**:
TP1 is about risk reduction, partial profit, and giving trade a chance to reach TP2/TP3.

**⚠️ MINIMUM TP1 RR: See `market_data.pre_gates.min_tp1_rr`** (mode-dependent threshold)
This is a HARD MINIMUM - scenarios below this will be REJECTED by validator!

**BEFORE finalizing each scenario, YOU MUST verify:**
```
entry_avg = average of entry_plan.orders[].price (weighted by size_pct)
risk = |entry_avg - stop_loss.recommended|
reward_tp1 = |targets[0].price - entry_avg|
tp1_rr = reward_tp1 / risk

IF tp1_rr < market_data.pre_gates.min_tp1_rr → DO NOT CREATE THIS SCENARIO
```

**Why this matters:** If TP1 RR is too low and user moves SL to breakeven → EV dies.

**Ideal if setup allows:** 1.0-1.5R+ for TP1

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

4. **cancel_if[]**: Conditions to abort the plan
5. **time_valid_hours**: Plan validity (adapt to timeframe)

🎯 **REQUIREMENTS**:
1. Generate MAX 2 scenarios (1 best LONG + 1 best SHORT, or just 1 if other direction blocked by pre_gates)
2. Each entry_plan.orders[].price MUST reference a real level from market_data.levels
3. Use price_structure.swing_highs/swing_lows for entry/stop selection
4. Consider liquidation.clusters_above/below for targets
5. Adapt time_valid_hours to timeframe {timeframe}
6. Account for contradictions (e.g., bullish trend + RSI 80 + high funding = overheated)
7. CHECK pre_gates BEFORE creating each scenario — skip if HARD GATES violated

🎯 **ARCHETYPE SELECTION** (REQUIRED):
Each scenario MUST select exactly ONE archetype:
1. "range_reclaim" — Mean reversion после ложного пробоя рейнджа
2. "breakout_retest" — Пробой + ретест уровня как новой поддержки/сопротивления
3. "sweep_reclaim" — Sweep ликвидности + возврат в структуру
4. "trend_pullback" — Откат к EMA/VWAP в трендовом рынке
5. "failed_breakdown" — Ложный пробой вниз → разворот
6. "failed_breakout" — Ложный пробой вверх → разворот
7. "momentum_continuation" — Продолжение после консолидации
8. "liquidity_grab" — Захват ликвидности перед движением

📌 **ENTRY TYPE RULES**:
Each scenario MUST specify entry_type:
1. "limit_pullback" — Limit order on pullback to level
2. "trigger_breakout" — Stop-limit on breakout above/below level
3. "trigger_reclaim" — Stop-limit on reclaim back into structure

🚨 **PRE-GENERATION GATES** (MANDATORY - Python has pre-calculated these):
Check market_data.pre_gates BEFORE creating each scenario:

**HARD GATES (scenario MUST NOT be created if violated):**
1. If pre_gates.{{bias}}.entry_squeezed = true AND entry_type = "limit_pullback":
   → DO NOT create this scenario (opposing level too close, no room to profit)
   → Only "trigger_*" entry types allowed when squeezed

2. If pre_gates.{{bias}}.path_blockers has 2+ levels:
   → TP1 MUST be at or before FIRST blocker
   → If no valid TP1 exists → DO NOT create this scenario

3. If BOTH long AND short have entry_squeezed = true:
   → Market is choppy → Prefer NO-TRADE signal over weak scenarios

**SOFT GATES (reduce confidence if violated):**
- path_blockers has 1 level: confidence -= 0.10
- squeeze_distance_R < 1.0: confidence -= 0.05
- path_clear = false: confidence -= 0.05

**QUALITY OVER QUANTITY:**
- Generate MAX 2 scenarios total (not 3-5)
- If one direction has pre_gates violations → skip it entirely
- Better 1 excellent scenario than 2 mediocre ones

📊 **OUTCOME PROBS PRIORS** (baseline by archetype):
| Archetype          | prob_sl | prob_tp1 | prob_tp2 | prob_tp3 | prob_be |
|--------------------|---------|----------|----------|----------|---------|
| sweep_reclaim      | 0.32    | 0.28     | 0.18     | 0.10     | 0.12    |
| breakout_retest    | 0.38    | 0.25     | 0.16     | 0.08     | 0.13    |
| trend_pullback     | 0.30    | 0.30     | 0.20     | 0.10     | 0.10    |
| (others similar)   | ~0.33   | ~0.28    | ~0.18    | ~0.09    | ~0.12   |

⚠️ CRITICAL RULES for outcome_probs_raw:
1. sl + tp1 + tp2 + tp3 + be = 1.0 EXACTLY
2. tp2 <= tp1 (fewer trades reach TP2 than TP1)
3. tp3 <= tp2 (even fewer reach TP3)
4. be = probability of breakeven exit / chop / manual close

🚫 **NO-TRADE SIGNAL** (optional but IMPORTANT):
If market conditions are UNFAVORABLE, add `no_trade` object with:
- should_not_trade: true
- confidence: 0.3-1.0 (how certain you are)
- reasons: ["ADX < 20 = chop zone", "Funding extreme + crowded", "ATR compression before news"]
- category: "chop" | "extreme_sentiment" | "low_liquidity" | "news_risk" | "technical_conflict" | "overextended"
- wait_for: ["ADX > 25", "Funding normalize", "Breakout from range"]
- estimated_wait_hours: 4-168

**STILL return scenarios** even with no_trade — they serve as reference. The no_trade signal WARNS the user.

Return strict JSON format."""

    def _build_json_schema(self) -> Dict:
        """Build JSON schema for LLM structured output."""
        return {
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
                                "archetype": {
                                    "type": "string",
                                    "enum": [
                                        "range_reclaim", "breakout_retest", "sweep_reclaim",
                                        "trend_pullback", "failed_breakdown", "failed_breakout",
                                        "momentum_continuation", "liquidity_grab"
                                    ],
                                },
                                "archetype_criteria_met": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "minItems": 2,
                                    "maxItems": 5,
                                },
                                "entry_type": {
                                    "type": "string",
                                    "enum": ["limit_pullback", "trigger_breakout", "trigger_reclaim"],
                                },
                                "entry_type_justification": {"type": "string"},
                                "entry_plan": {
                                    "type": "object",
                                    "properties": {
                                        "mode": {"type": "string", "enum": ["ladder", "single", "dca"]},
                                        "orders": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "price": {"type": "number"},
                                                    "size_pct": {"type": "integer", "minimum": 1, "maximum": 100},
                                                    "type": {"type": "string", "enum": ["limit", "stop_limit"]},
                                                    "tag": {"type": "string"},
                                                    "source_level": {"type": "string"}
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
                                        "cancel_if": {"type": "array", "items": {"type": "string"}},
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
                                            "partial_close_pct": {"type": "integer", "minimum": 0, "maximum": 100},
                                            "reason": {"type": "string"}
                                        },
                                        "required": ["level", "price", "partial_close_pct", "reason"],
                                        "additionalProperties": False
                                    }
                                },
                                "confidence": {"type": "number", "minimum": 0.05, "maximum": 0.95},
                                "confidence_factors": {"type": "array", "items": {"type": "string"}},
                                "risks": {"type": "array", "items": {"type": "string"}},
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
                                "conditions": {"type": "array", "items": {"type": "string"}},
                                "outcome_probs_raw": {
                                    "type": "object",
                                    "properties": {
                                        "sl": {"type": "number", "minimum": 0.01, "maximum": 0.95},
                                        "tp1": {"type": "number", "minimum": 0.01, "maximum": 0.95},
                                        "tp2": {"type": "number", "minimum": 0, "maximum": 0.95},
                                        "tp3": {"type": "number", "minimum": 0, "maximum": 0.95},
                                        "be": {"type": "number", "minimum": 0.01, "maximum": 0.35}
                                    },
                                    "required": ["sl", "tp1", "tp2", "tp3", "be"],
                                    "additionalProperties": False
                                },
                                "mode_notes": get_mode_notes_schema(),
                                "confluence": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "type": {"type": "string", "enum": ["structure", "momentum", "context"]},
                                            "reason": {"type": "string"},
                                            "evidence_ref": {"type": "string"}
                                        },
                                        "required": ["type", "reason", "evidence_ref"],
                                        "additionalProperties": False
                                    },
                                    "minItems": 1,
                                    "maxItems": 3,
                                },
                                "chase_check": {
                                    "type": "object",
                                    "properties": {
                                        "chase_distance_R": {"type": "number"},
                                        "is_chase": {"type": "boolean"},
                                        "allowed_reason": {"type": ["string", "null"]},
                                        "action": {"type": "string", "enum": ["ALLOWED", "REJECTED"]}
                                    },
                                    "required": ["chase_distance_R", "is_chase", "allowed_reason", "action"],
                                    "additionalProperties": False
                                },
                                "weight_factors": {
                                    "type": "object",
                                    "properties": {
                                        "confluence_count": {"type": "integer", "minimum": 0, "maximum": 3},
                                        "htf_alignment": {"type": "integer", "enum": [-1, 0, 1]},
                                        "path_clear": {"type": "boolean"},
                                        "invalidation_distance_R": {"type": "number"},
                                        "tp1_rr": {"type": "number"}
                                    },
                                    "required": ["confluence_count", "htf_alignment", "path_clear", "invalidation_distance_R", "tp1_rr"],
                                    "additionalProperties": False
                                },
                                "scenario_weight": {
                                    "type": "number",
                                    "minimum": 0.10,
                                    "maximum": 0.90,
                                }
                            },
                            "required": ["id", "name", "bias", "archetype", "archetype_criteria_met", "entry_type", "entry_type_justification", "entry_plan", "stop_loss", "targets", "confidence", "confidence_factors", "risks", "leverage", "invalidation_price", "conditions", "outcome_probs_raw", "mode_notes", "confluence", "chase_check", "weight_factors", "scenario_weight"],
                            "additionalProperties": False
                        }
                    },
                    "market_summary": {"type": "string"},
                    "primary_scenario_id": {"type": "integer"},
                    "risk_level": {"type": "string", "enum": ["low", "medium", "high", "very_high"]},
                    "no_trade": {
                        "type": "object",
                        "properties": {
                            "should_not_trade": {"type": "boolean"},
                            "confidence": {"type": "number", "minimum": 0.3, "maximum": 1.0},
                            "reasons": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                            "category": {
                                "type": "string",
                                "enum": ["chop", "extreme_sentiment", "low_liquidity", "news_risk", "technical_conflict", "overextended"],
                            },
                            "wait_for": {"type": "array", "items": {"type": "string"}},
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

    def _adapt_scenarios(
        self,
        scenarios: List[Dict],
        atr: Optional[float],
        atr_pct: float,
        timeframe: str,
    ) -> List[Dict]:
        """Адаптировать структуру сценариев под API Pydantic модели."""
        adapted_scenarios = []

        for sc in scenarios:
            # Адаптируем leverage структуру
            leverage = sc.get("leverage", {})
            adapted_leverage = {
                "recommended": leverage.get("recommended", "5x-8x"),
                "max_safe": leverage.get("max_safe", "10x"),
                "volatility_adjusted": True,
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

            # Рассчитываем дополнительные метрики из entry_plan
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

            # Calculate time_valid_hours
            time_valid_hours = self._calculate_time_valid(
                timeframe=timeframe,
                entry_mid=entry_mid,
                targets=sc.get("targets", []),
                atr=atr_value,
            )

            # Entry trigger
            conditions = sc.get("conditions", [])
            entry_trigger = conditions[0] if conditions else "Enter at specified price zone"

            # No-trade conditions
            no_trade_conditions = [f"Avoid if {risk.lower()}" for risk in risks[:2]] if risks else []

            # Создаем адаптированный сценарий
            adapted_sc = {
                "id": sc.get("id"),
                "name": sc.get("name"),
                "bias": sc.get("bias"),
                "confidence": sc.get("confidence"),
                "entry_plan": entry_plan,
                "entry": legacy_entry,
                "stop_loss": sc.get("stop_loss"),
                "targets": sc.get("targets"),
                "leverage": adapted_leverage,
                "invalidation": adapted_invalidation,
                "why": adapted_why,
                "conditions": sc.get("conditions", []),
                "stop_pct_of_entry": round(stop_pct_of_entry, 2),
                "atr_multiple_stop": round(atr_multiple_stop, 2) if atr_multiple_stop else None,
                "time_valid_hours": entry_plan.get("time_valid_hours", time_valid_hours),
                "entry_trigger": entry_trigger,
                "no_trade_conditions": no_trade_conditions,
                "mode_notes": sc.get("mode_notes", []),
                "scenario_weight": sc.get("scenario_weight", 0),
                # Pass through additional fields
                "archetype": sc.get("archetype"),
                "primary_archetype": sc.get("archetype"),
                "archetype_criteria_met": sc.get("archetype_criteria_met"),
                "entry_type": sc.get("entry_type"),
                "outcome_probs_raw": sc.get("outcome_probs_raw"),
                "confluence": sc.get("confluence"),
                "chase_check": sc.get("chase_check"),
                "weight_factors": sc.get("weight_factors"),
            }

            adapted_scenarios.append(adapted_sc)

        # Сортируем по confidence
        return sorted(adapted_scenarios, key=lambda x: x["confidence"], reverse=True)

    def _calculate_time_valid(
        self,
        timeframe: str,
        entry_mid: float,
        targets: List[Dict],
        atr: float,
    ) -> int:
        """Calculate time_valid_hours based on volatility."""
        # Parse timeframe в часы
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
            tf_hours = 24

        # Calculate volatility-based validity
        if targets and atr > 0 and entry_mid > 0:
            last_tp = targets[-1].get("price", 0) if targets else 0
            target_distance = abs(last_tp - entry_mid)

            atr_per_hour = atr / tf_hours if tf_hours > 0 else atr

            if atr_per_hour > 0:
                estimated_hours = (target_distance / atr_per_hour) * 1.5
                time_valid_hours = round(estimated_hours)
            else:
                time_valid_hours = round(tf_hours * 12)
        else:
            time_valid_hours = round(tf_hours * 12)

        # Cap минимум/максимум
        return max(2, min(time_valid_hours, 336))

    def _ensure_diversity(self, scenarios: List[Dict], max_scenarios: int) -> List[Dict]:
        """Гарантировать diversity (min 1 long + 1 short)."""
        if len(scenarios) <= max_scenarios:
            return scenarios

        final_scenarios = []

        # Разделяем на long/short
        long_scenarios = [sc for sc in scenarios if sc["bias"] == "long"]
        short_scenarios = [sc for sc in scenarios if sc["bias"] == "short"]

        # Берём лучший long и лучший short
        if long_scenarios:
            final_scenarios.append(long_scenarios[0])
        if short_scenarios:
            final_scenarios.append(short_scenarios[0])

        # Добираем до max_scenarios лучшими по confidence
        remaining_slots = max_scenarios - len(final_scenarios)
        if remaining_slots > 0:
            added_ids = {sc["id"] for sc in final_scenarios}
            remaining = [sc for sc in scenarios if sc["id"] not in added_ids]
            final_scenarios.extend(remaining[:remaining_slots])

        # Сортируем финальный список по confidence
        return sorted(final_scenarios, key=lambda x: x["confidence"], reverse=True)

    async def llm_validate(
        self,
        scenarios: List[Dict],
        market_context: Dict,
        candidates: Dict,
        current_price: float,
    ) -> List[Dict]:
        """
        LLM-based validation of scenario logical coherence.

        NOTE: Currently disabled in main flow - Python validation is sufficient.
        """
        from src.services.scenario_validator import scenario_validator

        if not scenarios:
            return scenarios

        # Normalize probs
        def normalize_probs(probs: Dict[str, float]) -> Dict[str, float]:
            if not probs:
                return probs

            values = list(probs.values())
            if any(v > 1.0 for v in values):
                probs = {k: v / 100.0 for k, v in probs.items()}

            total = sum(probs.values())
            if total == 0:
                return probs

            if abs(total - 1.0) > 0.01:
                probs = {k: round(v / total, 4) for k, v in probs.items()}
                logger.debug(f"Normalized probs: sum was {total:.3f}, now 1.0")

            return probs

        for scenario in scenarios:
            if "outcome_probs_raw" in scenario:
                scenario["outcome_probs_raw"] = normalize_probs(scenario["outcome_probs_raw"])

        logger.info(f"LLM validating {len(scenarios)} scenarios...")

        validated = []
        rejected_count = 0

        for scenario in scenarios:
            try:
                all_valid_levels = list(candidates.get("supports", [])) + list(candidates.get("resistances", []))

                candidate_levels = {
                    "support_near": candidates.get("supports", []),
                    "resistance_near": candidates.get("resistances", []),
                    "all_valid": sorted(set(all_valid_levels)),
                }

                validation_context = {
                    "current_price": current_price,
                    "trend": market_context.get("trend", "unknown"),
                    "atr_percent": market_context.get("atr_percent", 2.0),
                }

                result = await scenario_validator.validate(
                    scenario=scenario,
                    market_context=validation_context,
                    candidate_levels=candidate_levels,
                )

                if result.hard_violation:
                    logger.warning(f"Scenario #{scenario.get('id')} REJECTED: {result.hard_violation}")
                    rejected_count += 1
                    continue

                scenario["validator_flags"] = result.issues
                scenario["validator_suggestions"] = result.suggestions

                old_conf = scenario.get("confidence", 0.5)
                new_conf = max(0.1, min(0.95, old_conf + result.confidence_adjustment))
                scenario["confidence"] = new_conf

                if result.confidence_adjustment != 0:
                    logger.info(
                        f"Scenario #{scenario.get('id')} confidence: "
                        f"{old_conf:.2f} → {new_conf:.2f} (adj: {result.confidence_adjustment:+.2f})"
                    )

                validated.append(scenario)

            except Exception as e:
                logger.error(f"LLM validation error for scenario #{scenario.get('id')}: {e}")
                scenario["validator_flags"] = [f"Validation error: {str(e)}"]
                validated.append(scenario)

        if rejected_count > 0:
            logger.warning(f"LLM validation rejected {rejected_count} scenarios")

        logger.info(f"LLM validation complete: {len(validated)} scenarios passed")

        return validated
