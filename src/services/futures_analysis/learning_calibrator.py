# coding: utf-8
"""
Learning Calibrator - интеграция с learning system.

Калибровка confidence, SL/TP suggestions, EV calculation, class stats.
"""
from typing import Any, Dict, List, Optional

from loguru import logger

# Learning system integration
from src.learning import confidence_calibrator, sltp_optimizer, ev_calculator
from src.learning import (
    class_stats_analyzer,
    build_class_key,
    ClassKey,
    CONFIDENCE_MIN,
    CONFIDENCE_MAX,
)
from src.database.engine import get_session_maker


class LearningCalibrator:
    """
    Интеграция с learning system для калибровки сценариев.

    Функции:
    - Калибровка confidence на основе исторических данных
    - SL/TP suggestions из archetype статистики
    - EV calculation
    - Class stats context gates
    """

    async def apply_calibration(
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

    async def apply_ev_calculation(
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

                    # EV adjustments based on quality_tier (set by validator)
                    # No hard reject here - just apply EV penalties
                    tp1_rr = targets[0].get("rr", 0) if targets else 0
                    ev_multiplier = 1.0
                    ev_flags = list(metrics.flags)

                    quality_tier = sc.get("quality_tier", "high")
                    healthy_rr = 0.8  # Healthy minimum for all modes

                    # Apply EV penalty based on quality tier
                    if quality_tier == "low":
                        # Low quality scenarios get significant EV penalty
                        ev_flags.append("low_quality_scenario")
                        ev_multiplier = 0.5  # -50% к EV (makes it less attractive)
                    elif tp1_rr < healthy_rr:
                        # Penalty zone (below 0.8R but above mode minimum)
                        ev_flags.append("tp1_rr_penalty_zone")
                        ev_multiplier = 0.8  # -20% к EV
                    elif tp1_rr < 1.0:
                        # Acceptable but not ideal
                        ev_flags.append("tp1_rr_acceptable")
                        ev_multiplier = 0.9  # -10% к EV

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

                # Sort ALL scenarios by scenario_score (low quality will have lower scores)
                scenarios = sorted(
                    scenarios,
                    key=lambda x: x.get("ev_metrics", {}).get("scenario_score", 0),
                    reverse=True
                )

                # Log quality distribution
                high_count = sum(1 for s in scenarios if s.get("quality_tier") == "high")
                low_count = sum(1 for s in scenarios if s.get("quality_tier") == "low")

                logger.debug(
                    f"EV calculation applied to {len(scenarios)} scenarios "
                    f"({high_count} high, {low_count} low quality), "
                    f"top score: {scenarios[0].get('ev_metrics', {}).get('scenario_score', 0):.3f}"
                    if scenarios else ""
                )

        except Exception as e:
            logger.warning(f"EV calculation failed: {e}")
            # Return scenarios unchanged on error

        return scenarios

    async def apply_class_stats(
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

    async def log_generation(
        self,
        analysis_id: str,
        scenarios: List[Dict],
        symbol: str,
        timeframe: str,
        market_context: Dict,
        user_id: int = 0,
        is_testnet: bool = False,
    ) -> None:
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
