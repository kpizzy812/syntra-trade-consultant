# coding: utf-8
"""
LLM-based Scenario Validator

Быстрая валидация логической coherence сценария после Python-валидации.
Использует gpt-5-mini (MODEL_FAST) для скорости.

Режимы:
- ADJUST (default): Показывает сценарий с flags и confidence_adjustment
- STRICT: Отклоняет ТОЛЬКО на hard safety violations

МОЖЕТ:
- Ставить validator_flags (issues)
- Делать confidence_adjustment (±0.15 max)
- Предлагать suggestions текстом
- STRICT reject на hard violations

НЕ МОЖЕТ:
- Придумывать новые уровни
- Переписывать entry_plan
- Менять prices в сценарии
"""
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from loguru import logger

from config.config import MODEL_FAST
from src.services.openai_service import OpenAIService


# ==============================================================================
# VALIDATION RESULT
# ==============================================================================


@dataclass
class ValidationResult:
    """Result of LLM validation pass"""

    # Mode: "adjust" or "strict"
    mode: str = "adjust"

    # Is scenario valid (False only on hard violations)
    is_valid: bool = True

    # Hard violation code (triggers STRICT rejection)
    hard_violation: Optional[str] = None

    # Issues found (informational, always populated)
    issues: List[str] = field(default_factory=list)

    # Suggestions for improvement (informational)
    suggestions: List[str] = field(default_factory=list)

    # Confidence adjustment (-0.15 to +0.10)
    confidence_adjustment: float = 0.0

    # LLM reasoning (for debugging)
    reasoning: str = ""

    def to_dict(self) -> Dict:
        return {
            "mode": self.mode,
            "is_valid": self.is_valid,
            "hard_violation": self.hard_violation,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "confidence_adjustment": self.confidence_adjustment,
            "reasoning": self.reasoning,
        }


# ==============================================================================
# HARD VIOLATIONS (STRICT mode triggers)
# ==============================================================================

STRICT_VIOLATIONS = [
    "sl_above_entry_long",      # SL выше entry в лонге
    "sl_below_entry_short",     # SL ниже entry в шорте
    "entry_level_not_exists",   # Entry на уровне которого нет в данных
    "targets_below_entry_long", # Targets ниже entry в лонге
    "targets_above_entry_short", # Targets выше entry в шорте
    # "probs_sum_invalid" - REMOVED: outcome_probs часто пустые, не критичная проверка
]


# ==============================================================================
# JSON SCHEMA FOR LLM RESPONSE
# ==============================================================================

VALIDATION_SCHEMA = {
    "name": "scenario_validation",
    "schema": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["adjust", "strict"],
                "description": "adjust=issues only, strict=hard violation found"
            },
            "is_valid": {
                "type": "boolean",
                "description": "False only on hard violations"
            },
            "hard_violation": {
                "type": ["string", "null"],
                "enum": [None] + STRICT_VIOLATIONS,
                "description": "Hard violation code or null"
            },
            "issues": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of issues found (informational)"
            },
            "suggestions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Suggestions for improvement"
            },
            "confidence_adjustment": {
                "type": "number",
                "minimum": -0.15,
                "maximum": 0.10,
                "description": "Confidence adjustment (-0.15 to +0.10)"
            },
            "reasoning": {
                "type": "string",
                "description": "Brief reasoning for validation result"
            }
        },
        "required": [
            "mode", "is_valid", "hard_violation", "issues",
            "suggestions", "confidence_adjustment", "reasoning"
        ],
        "additionalProperties": False
    },
    "strict": True
}


# ==============================================================================
# SCENARIO VALIDATOR
# ==============================================================================


class ScenarioValidator:
    """
    LLM-based scenario validator.

    Validates scenarios for logical coherence after Python validation.
    Uses fast model (gpt-5-mini) for quick validation.
    """

    def __init__(self):
        self.openai = OpenAIService()
        self.model = MODEL_FAST
        logger.info(f"ScenarioValidator initialized with model={self.model}")

    async def validate(
        self,
        scenario: Dict[str, Any],
        market_context: Dict[str, Any],
        candidate_levels: Dict[str, Any],
    ) -> ValidationResult:
        """
        Validate scenario for logical coherence.

        Args:
            scenario: Scenario dict from generator
            market_context: Market context (trend, bias, etc.)
            candidate_levels: Available price levels (support, resistance, etc.)

        Returns:
            ValidationResult with issues, suggestions, and confidence_adjustment
        """
        try:
            # Build validation prompt
            prompt = self._build_validation_prompt(
                scenario, market_context, candidate_levels
            )

            # Debug: log scenario data being validated
            entry_plan = scenario.get("entry_plan", {})
            orders = entry_plan.get("orders", [])
            entry_prices = [o.get("price", 0) for o in orders]
            targets = scenario.get("targets", [])
            target_prices = [t.get("price", 0) for t in targets]
            logger.debug(
                f"🔍 Validating scenario #{scenario.get('id')}: "
                f"bias={scenario.get('bias')}, "
                f"entry={entry_prices}, "
                f"targets={target_prices}, "
                f"sl={scenario.get('stop_loss', {}).get('recommended')}"
            )

            # Call LLM with structured output
            response = await self.openai.structured_completion(
                prompt=prompt,
                json_schema=VALIDATION_SCHEMA,
                model=self.model,
                temperature=0.2,  # Low temperature for consistent validation
            )

            if not response:
                logger.warning("Empty response from validator LLM")
                return ValidationResult(
                    mode="adjust",
                    is_valid=True,
                    issues=["Validator returned empty response"],
                    reasoning="Fallback to valid due to empty response"
                )

            # Debug: log raw LLM response
            logger.debug(
                f"🔍 Validator LLM response for #{scenario.get('id')}: "
                f"mode={response.get('mode')}, is_valid={response.get('is_valid')}, "
                f"hard_violation={response.get('hard_violation')}, "
                f"reasoning={response.get('reasoning', '')[:100]}"
            )

            # Parse response into ValidationResult
            result = ValidationResult(
                mode=response.get("mode", "adjust"),
                is_valid=response.get("is_valid", True),
                hard_violation=response.get("hard_violation"),
                issues=response.get("issues", []),
                suggestions=response.get("suggestions", []),
                confidence_adjustment=self._clamp_adjustment(
                    response.get("confidence_adjustment", 0.0)
                ),
                reasoning=response.get("reasoning", "")
            )

            # Log validation result
            if result.hard_violation:
                logger.warning(
                    f"STRICT violation: {result.hard_violation} - "
                    f"scenario {scenario.get('id')} rejected"
                )
            elif result.issues:
                logger.info(
                    f"Validation issues for scenario {scenario.get('id')}: "
                    f"{result.issues}, adjustment={result.confidence_adjustment:+.2f}"
                )
            else:
                logger.debug(f"Scenario {scenario.get('id')} validated OK")

            return result

        except Exception as e:
            logger.error(f"Validator error: {e}")
            # Fallback: don't reject on validator errors
            return ValidationResult(
                mode="adjust",
                is_valid=True,
                issues=[f"Validator error: {str(e)}"],
                reasoning="Fallback to valid due to validator error"
            )

    def _build_validation_prompt(
        self,
        scenario: Dict[str, Any],
        market_context: Dict[str, Any],
        candidate_levels: Dict[str, Any],
    ) -> str:
        """Build validation prompt for LLM"""

        # Extract key scenario data
        scenario_id = scenario.get("id", "?")
        bias = scenario.get("bias", "unknown")
        confidence = scenario.get("confidence", 0)

        # Entry plan
        entry_plan = scenario.get("entry_plan", {})
        orders = entry_plan.get("orders", [])
        entry_prices = [o.get("price", 0) for o in orders]
        entry_min = min(entry_prices) if entry_prices else 0
        entry_max = max(entry_prices) if entry_prices else 0

        # Stop loss
        stop_loss = scenario.get("stop_loss", {})
        sl_recommended = stop_loss.get("recommended", 0)

        # Targets
        targets = scenario.get("targets", [])
        target_prices = [t.get("price", 0) for t in targets]

        # Market context
        current_price = market_context.get("current_price", 0)
        trend = market_context.get("trend", "unknown")
        atr_pct = market_context.get("atr_percent", 0)

        # Candidate levels (for reference)
        support_near = candidate_levels.get("support_near", [])
        resistance_near = candidate_levels.get("resistance_near", [])
        all_valid = candidate_levels.get("all_valid", [])

        prompt = f"""You are a trading scenario validator. Your job is to check if a scenario is logically coherent.

SCENARIO #{scenario_id}:
- Bias: {bias}
- Confidence: {confidence:.2f}
- Entry zone: ${entry_min:.2f} - ${entry_max:.2f}
- Stop loss: ${sl_recommended:.2f}
- Targets: {[f"${t:.2f}" for t in target_prices]}

MARKET CONTEXT:
- Current price: ${current_price:.2f}
- Trend: {trend}
- ATR%: {atr_pct:.2f}%

AVAILABLE LEVELS (entry can use ANY of these):
- Support (near): {[f"${s:.2f}" for s in support_near[:5]]}
- Resistance (near): {[f"${r:.2f}" for r in resistance_near[:5]]}
- All valid levels (S/R + EMA + VWAP): {[f"${v:.2f}" for v in all_valid[:10]]}

YOUR TASK:

1. Check for HARD VIOLATIONS (mode="strict", is_valid=false):
   - sl_above_entry_long: For LONG, SL must be BELOW entry zone
   - sl_below_entry_short: For SHORT, SL must be ABOVE entry zone
   - entry_level_not_exists: Entry prices should reference levels from "All valid levels" list
   - targets_below_entry_long: For LONG, targets must be ABOVE entry
   - targets_above_entry_short: For SHORT, targets must be BELOW entry

2. If no hard violations, check for ISSUES (mode="adjust"):
   - Entry zone too wide for ATR (>3x ATR)
   - Entry zone too far from current price
   - Confidence seems too high/low for setup
   - Any logical inconsistencies
   NOTE: Do NOT penalize for R:R - Python handles TP1 RR validation separately.

3. Suggest confidence_adjustment:
   - Negative (-0.15 to 0): If issues reduce reliability
   - Positive (0 to +0.10): If setup is exceptionally clean
   - Zero: If no significant adjustments needed

IMPORTANT RULES:
- Do NOT invent new price levels
- Do NOT rewrite the entry plan
- Do NOT change prices
- ONLY validate and report issues

Return JSON with your validation result."""

        return prompt

    def _clamp_adjustment(self, adjustment: float) -> float:
        """Clamp confidence adjustment to valid range"""
        return max(-0.15, min(0.10, adjustment))


# ==============================================================================
# SINGLETON INSTANCE
# ==============================================================================

scenario_validator = ScenarioValidator()
