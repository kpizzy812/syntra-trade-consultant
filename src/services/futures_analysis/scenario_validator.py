# coding: utf-8
"""
Scenario Validator - валидация и коррекция сценариев.

Проверяет что LLM использовал реальные уровни, корректирует RR.
"""
from typing import Any, Dict, List

from loguru import logger

from .constants import (
    MAX_ENTRY_DISTANCE_PCT_BY_TF,
    MAX_ENTRY_DISTANCE_PCT_DEFAULT,
    ATR_ENTRY_MULTIPLIER_BY_TF,
    ATR_ENTRY_MULTIPLIER_DEFAULT,
)

# Import for outcome_probs validation
from config.archetype_priors import validate_outcome_probs


class ScenarioValidator:
    """
    Валидатор сценариев от LLM.

    Проверяет:
    - Entry/SL/TP соответствуют реальным уровням
    - Entry не слишком далеко от текущей цены
    - RR рассчитан корректно
    """

    def validate(
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
        4. Entry distance от current_price <= min(MAX_PCT_BY_TF, ATR * K)

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
                            f"Scenario '{sc.get('name')}' INVALID ({timeframe}): "
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
                    f"Scenario '{sc.get('name')}' REJECTED: entry too far from current price"
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
            f"Validation: {valid_count} valid, {fixed_count} fixed, "
            f"{len(validated_scenarios) - valid_count - fixed_count} warnings, "
            f"{invalid_count} rejected (unrealistic entry)"
        )

        return validated_scenarios

    def calculate_rr(
        self,
        scenarios: List[Dict],
        current_price: float,
        atr: float,
        min_tp1_rr: float = 0.7,
        candidates: Dict = None
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
            7. TP1 RR >= min_tp1_rr (hard reject if below)

        Args:
            scenarios: Сценарии после validate()
            current_price: Текущая цена
            atr: ATR для авто-фиксов
            min_tp1_rr: Minimum TP1 RR threshold (from mode config)

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

            # === 3.5 CRITICAL: Validate invalidation vs entry ===
            invalidation_price = sc.get("invalidation_price", 0)
            fixes_applied = sc.get("fixes_applied", [])

            if invalidation_price > 0:
                # Buffer = max(0.5*ATR, 0.6% of price)
                entry_inv_buffer = max(0.5 * atr, current_price * 0.006) if atr else current_price * 0.006
                reject_threshold = 1.5 * atr if atr else current_price * 0.015

                if is_long:
                    # LONG: invalidation must be BELOW entry_min - buffer
                    required_invalidation = entry_min - entry_inv_buffer
                    if invalidation_price >= entry_min:
                        # Need fix: invalidation is at or above entry
                        fix_distance = (invalidation_price - entry_min) + entry_inv_buffer

                        if fix_distance > reject_threshold:
                            # Too much fix needed - reject scenario
                            issues.append(
                                f"CRITICAL: invalidation_unreliable: {invalidation_price:.2f} >= entry_min={entry_min:.2f}, "
                                f"fix_distance={fix_distance:.2f} > threshold={reject_threshold:.2f}"
                            )
                            sc["validation_status"] = "invalid:invalidation_unreliable"
                            continue  # Skip this scenario
                        else:
                            # Auto-fix: move invalidation below entry_min - buffer
                            sc["invalidation_price"] = round(required_invalidation, 2)
                            fixes_applied.append("invalidation_moved")
                            issues.append(
                                f"auto_fixed_invalidation: {invalidation_price:.2f} -> {required_invalidation:.2f} "
                                f"(entry_min={entry_min:.2f}, buffer={entry_inv_buffer:.2f})"
                            )
                    elif invalidation_price > required_invalidation:
                        # Invalidation is below entry_min but not enough buffer
                        sc["invalidation_price"] = round(required_invalidation, 2)
                        fixes_applied.append("invalidation_buffer_adjusted")
                        issues.append(
                            f"adjusted_invalidation_buffer: {invalidation_price:.2f} -> {required_invalidation:.2f}"
                        )
                else:
                    # SHORT: invalidation must be ABOVE entry_max + buffer
                    required_invalidation = entry_max + entry_inv_buffer
                    if invalidation_price <= entry_max:
                        # Need fix: invalidation is at or below entry
                        fix_distance = (entry_max - invalidation_price) + entry_inv_buffer

                        if fix_distance > reject_threshold:
                            issues.append(
                                f"CRITICAL: invalidation_unreliable: {invalidation_price:.2f} <= entry_max={entry_max:.2f}, "
                                f"fix_distance={fix_distance:.2f} > threshold={reject_threshold:.2f}"
                            )
                            sc["validation_status"] = "invalid:invalidation_unreliable"
                            continue
                        else:
                            sc["invalidation_price"] = round(required_invalidation, 2)
                            fixes_applied.append("invalidation_moved")
                            issues.append(
                                f"auto_fixed_invalidation: {invalidation_price:.2f} -> {required_invalidation:.2f} "
                                f"(entry_max={entry_max:.2f}, buffer={entry_inv_buffer:.2f})"
                            )
                    elif invalidation_price < required_invalidation:
                        sc["invalidation_price"] = round(required_invalidation, 2)
                        fixes_applied.append("invalidation_buffer_adjusted")
                        issues.append(
                            f"adjusted_invalidation_buffer: {invalidation_price:.2f} -> {required_invalidation:.2f}"
                        )

                sc["fixes_applied"] = fixes_applied

                # Check max fixes limit
                MAX_FIXES_PER_SCENARIO = 2
                if len(fixes_applied) > MAX_FIXES_PER_SCENARIO:
                    issues.append(
                        f"CRITICAL: too_many_fixes ({len(fixes_applied)} > {MAX_FIXES_PER_SCENARIO}): {fixes_applied}"
                    )
                    sc["validation_status"] = "invalid:too_many_fixes"
                    continue

            # === 3.6 Sync cancel_if with entry_min/invalidation ===
            # Rule: cancel_if.close_below (LONG) = entry_min
            #       cancel_if.close_above (SHORT) = entry_max
            # This cancels pending limit orders if level is lost
            cancel_conditions = entry_plan.get("cancel_if", [])
            updated_cancel_if = []
            cancel_synced = False

            for cond in cancel_conditions:
                cond_lower = cond.lower()
                if is_long and ("close_below" in cond_lower or "break_below" in cond_lower):
                    # Extract price from condition like "close_below 93500"
                    parts = cond.split()
                    if len(parts) >= 2:
                        try:
                            cancel_price = float(parts[1].replace(",", ""))
                            # cancel_price should be >= invalidation_price and ideally == entry_min
                            final_invalidation = sc.get("invalidation_price", 0)
                            if cancel_price > entry_min or cancel_price < final_invalidation:
                                # Fix: set to entry_min
                                new_cond = f"{parts[0]} {entry_min:.2f} (entry_min)"
                                updated_cancel_if.append(new_cond)
                                cancel_synced = True
                                issues.append(
                                    f"synced_cancel_if: '{cond}' -> '{new_cond}'"
                                )
                            else:
                                updated_cancel_if.append(cond)
                        except ValueError:
                            updated_cancel_if.append(cond)
                    else:
                        updated_cancel_if.append(cond)
                elif not is_long and ("close_above" in cond_lower or "break_above" in cond_lower):
                    parts = cond.split()
                    if len(parts) >= 2:
                        try:
                            cancel_price = float(parts[1].replace(",", ""))
                            final_invalidation = sc.get("invalidation_price", 0)
                            if cancel_price < entry_max or cancel_price > final_invalidation:
                                new_cond = f"{parts[0]} {entry_max:.2f} (entry_max)"
                                updated_cancel_if.append(new_cond)
                                cancel_synced = True
                                issues.append(
                                    f"synced_cancel_if: '{cond}' -> '{new_cond}'"
                                )
                            else:
                                updated_cancel_if.append(cond)
                        except ValueError:
                            updated_cancel_if.append(cond)
                    else:
                        updated_cancel_if.append(cond)
                else:
                    updated_cancel_if.append(cond)

            if cancel_synced:
                sc["entry_plan"]["cancel_if"] = updated_cancel_if
                if "cancel_if_synced" not in fixes_applied:
                    fixes_applied.append("cancel_if_synced")
                    sc["fixes_applied"] = fixes_applied

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

                # 🆕 TP1 minimum RR check - mark as LOW QUALITY (not hard reject)
                if i == 0 and rr < min_tp1_rr:
                    sc["quality_tier"] = "low"
                    # Add to quality_issues for UI display
                    if "quality_issues" not in sc:
                        sc["quality_issues"] = []
                    sc["quality_issues"].append({
                        "code": "tp1_rr_too_low",
                        "severity": "warning",
                        "message": f"TP1 RR слишком низкий: {rr:.2f}R (минимум {min_tp1_rr}R)",
                        "details": f"При переводе SL в безубыток EV становится отрицательным"
                    })
                    issues.append(f"TP1_rr_too_low: RR={rr:.2f} < {min_tp1_rr}")

                    # 🔍 ДИАГНОСТИКА: Детальное логирование для анализа
                    r_atr_mult = round(risk_per_unit / atr, 2) if atr and atr > 0 else 0
                    logger.warning(
                        f"🚨 Scenario #{sc.get('id')} LOW QUALITY: TP1 RR {rr:.2f} < {min_tp1_rr} | "
                        f"entry={entry_ref:.2f}, stop={stop:.2f}, R={risk_per_unit:.2f} ({r_atr_mult}x ATR), "
                        f"TP1={tp_price:.2f}"
                    )

                    # 🔧 AUTO-REPAIR: Попытка заменить TP1 на подходящий уровень
                    if candidates:
                        # Собираем все доступные TP-кандидаты (near + macro)
                        if is_long:
                            all_tp_candidates = list(candidates.get("resistances", []))
                            all_tp_candidates.extend(candidates.get("resistances_macro", []))
                        else:
                            all_tp_candidates = list(candidates.get("supports", []))
                            all_tp_candidates.extend(candidates.get("supports_macro", []))

                        # Фильтруем только подходящие по направлению
                        valid_candidates = [
                            c for c in all_tp_candidates
                            if (c > entry_ref if is_long else c < entry_ref)
                        ]

                        # Сортируем от ближайшего к дальнему
                        valid_candidates_sorted = sorted(
                            valid_candidates,
                            key=lambda x: abs(x - entry_ref)
                        )

                        # Ищем первый уровень который даёт RR >= min_tp1_rr
                        repaired = False
                        for candidate_price in valid_candidates_sorted:
                            candidate_reward = abs(candidate_price - entry_ref)
                            candidate_rr = round(candidate_reward / risk_per_unit, 2)

                            if candidate_rr >= min_tp1_rr:
                                # ✅ Нашли подходящий уровень!
                                logger.info(
                                    f"🔧 Scenario #{sc.get('id')}: TP1 auto-repaired "
                                    f"{tp_price:.2f} (RR {rr:.2f}) → {candidate_price:.2f} (RR {candidate_rr:.2f})"
                                )
                                sc["targets"][0]["price"] = round(candidate_price, 2)
                                sc["targets"][0]["rr"] = candidate_rr
                                sc["targets"][0]["reason"] += f" (auto-adjusted from {tp_price:.2f})"

                                # Обновляем quality_tier на acceptable
                                sc["quality_tier"] = "acceptable"

                                # Добавляем в fixes_applied
                                fixes_applied = sc.get("fixes_applied", [])
                                if "tp1_repaired" not in fixes_applied:
                                    fixes_applied.append("tp1_repaired")
                                sc["fixes_applied"] = fixes_applied

                                # Обновляем rr и убираем low quality
                                rr = candidate_rr
                                tp_price = candidate_price
                                repaired = True
                                break

                        if not repaired:
                            # ❌ Нет подходящего уровня - остаётся low quality
                            logger.warning(
                                f"⚠️ Scenario #{sc.get('id')}: No valid TP1 found "
                                f"(all {len(valid_candidates_sorted)} candidates give RR < {min_tp1_rr})"
                            )

            # === 6. Добавляем метаданные расчёта ===
            sc["rr_calculation"] = {
                "entry_ref": round(entry_ref, 2),
                "entry_min": round(entry_min, 2),
                "entry_max": round(entry_max, 2),
                "stop": round(stop, 2),
                "risk_per_unit": round(risk_per_unit, 2),
                "risk_pct": round((risk_per_unit / entry_ref) * 100, 2) if entry_ref > 0 else 0
            }

            # === 7. Валидация outcome_probs + ЖЁСТКИЕ ОГРАНИЧЕНИЯ ===
            outcome_probs = sc.get("outcome_probs_raw", {})
            archetype = sc.get("archetype", "")
            probs_confidence_penalty = 0.0

            if outcome_probs:
                # Преобразуем к нужному формату для validate_outcome_probs
                probs_dict = {
                    "prob_sl": outcome_probs.get("sl", 0),
                    "prob_tp1": outcome_probs.get("tp1", 0),
                    "prob_tp2": outcome_probs.get("tp2", 0),
                    "prob_tp3": outcome_probs.get("tp3", 0),
                    "prob_be": outcome_probs.get("be", 0),
                }

                probs_validation = validate_outcome_probs(probs_dict, archetype)
                sc["probs_validation"] = probs_validation

                # Hard errors -> confidence cap + issues
                if not probs_validation["is_valid"]:
                    for err in probs_validation["errors"]:
                        issues.append(f"probs_error: {err}")
                    # HARD PENALTY: invalid probs = untrusted scenario
                    probs_confidence_penalty += 0.20
                    sc["probs_penalty_reason"] = "invalid_probs"

                # Warnings -> confidence penalty proportional to deviation count
                if probs_validation["warnings"]:
                    sc["probs_warnings"] = probs_validation["warnings"]
                    warning_count = len(probs_validation["warnings"])
                    # Each warning = -0.05 confidence, max -0.15
                    probs_confidence_penalty += min(0.15, 0.05 * warning_count)

                # Apply confidence cap if probs deviate too much
                if probs_confidence_penalty > 0:
                    old_conf = sc.get("confidence", 0.5)
                    # Cap confidence: subtract penalty and clamp to max 0.65 if any probs issues
                    new_conf = max(0.10, old_conf - probs_confidence_penalty)
                    if probs_confidence_penalty >= 0.15:
                        new_conf = min(new_conf, 0.65)  # Hard cap for significant deviations
                    sc["confidence"] = round(new_conf, 2)
                    sc["confidence_adjustment_probs"] = round(-probs_confidence_penalty, 2)
                    logger.debug(
                        f"Scenario #{sc.get('id')}: probs penalty {probs_confidence_penalty:.2f}, "
                        f"confidence {old_conf:.2f} → {new_conf:.2f}"
                    )

            # === 8. Итоговый статус ===
            # Set quality_tier if not already set (e.g., by TP1 RR check)
            if "quality_tier" not in sc:
                if not issues:
                    sc["quality_tier"] = "high"
                elif rr_outlier:
                    sc["quality_tier"] = "acceptable"  # outlier warning but usable
                else:
                    sc["quality_tier"] = "acceptable"  # fixed issues

            # Legacy field for backward compatibility
            if sc["quality_tier"] == "low":
                sc["rr_validation"] = "low_quality"
            elif not issues:
                sc["rr_validation"] = "valid"
            elif rr_outlier:
                sc["rr_validation"] = "warning_outlier"
            else:
                sc["rr_validation"] = "fixed"

            sc["rr_issues"] = issues if issues else None

            validated.append(sc)

        # Логируем результаты
        high_count = sum(1 for s in validated if s.get("quality_tier") == "high")
        acceptable_count = sum(1 for s in validated if s.get("quality_tier") == "acceptable")
        low_count = sum(1 for s in validated if s.get("quality_tier") == "low")

        logger.info(
            f"RR recalculation: {high_count} high, {acceptable_count} acceptable, "
            f"{low_count} low quality out of {len(validated)}"
        )

        # 🆕 Return ALL scenarios (no filtering) - let service/API separate them
        return validated

    def get_max_entry_distance(self, timeframe: str, atr: float, current_price: float) -> float:
        """
        Получить максимальное расстояние entry от текущей цены.

        Hybrid approach: min(% by TF, ATR * multiplier)
        """
        max_pct = MAX_ENTRY_DISTANCE_PCT_BY_TF.get(timeframe, MAX_ENTRY_DISTANCE_PCT_DEFAULT)
        atr_mult = ATR_ENTRY_MULTIPLIER_BY_TF.get(timeframe, ATR_ENTRY_MULTIPLIER_DEFAULT)

        if atr and current_price:
            atr_pct = (atr * atr_mult / current_price) * 100
            return min(max_pct, atr_pct)
        return max_pct
