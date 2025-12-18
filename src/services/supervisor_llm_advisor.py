"""
Supervisor LLM Advisor

Hybrid approach: Rules trigger events -> LLM analyzes -> Guardrails validate

This module:
1. Builds MarketContextPack for LLM
2. Calls LLM with structured prompt
3. Parses and validates LLM response
4. Falls back to rule-based recommendations on error
"""
import json
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

from loguru import logger

from src.database.models import (
    SupervisorEvent,
    SupervisorUrgency,
    RecommendationType,
)
from src.services.binance_service import binance_service
from src.services.openai_service import OpenAIService
from config.config import OPENAI_MODEL

# Create instance for LLM calls
_openai_service = OpenAIService()


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass
class OHLCVSummary:
    """Aggregated OHLCV data for a timeframe"""
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    change_pct: float
    candles_count: int


@dataclass
class MarketContextPack:
    """
    Complete market context for LLM analysis.

    Contains everything LLM needs to make informed decision.
    """
    # Position info
    trade_id: str
    symbol: str
    side: str  # "Long" / "Short"
    entry_price: float
    mark_price: float
    qty: float
    leverage: int
    unrealized_pnl: float
    pnl_pct: float
    liq_price: Optional[float]
    sl_current: Optional[float]
    tp_current: Optional[List[Dict]]

    # Scenario info (from registration)
    invalidation_price: float
    stop_loss_original: float
    take_profits: List[Dict]  # [{level, price, pct}]
    scenario_bias: str
    scenario_confidence: float
    time_valid_left_min: int
    timeframe: str

    # Market data
    ohlcv_1h: Optional[OHLCVSummary] = None
    ohlcv_4h: Optional[OHLCVSummary] = None
    ohlcv_1d: Optional[OHLCVSummary] = None

    # Technical context
    atr_pct: Optional[float] = None  # ATR as % of price
    volume_ratio: Optional[float] = None  # Current vs avg volume
    trend_1h: Optional[str] = None  # "up" / "down" / "ranging"
    trend_4h: Optional[str] = None

    # Events that triggered this analysis
    events: List[str] = field(default_factory=list)
    event_urgency: str = "low"

    # Timestamp
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_llm_prompt_json(self) -> str:
        """Format as compact JSON for LLM prompt"""
        # Remove None values and format nicely
        data = {k: v for k, v in self.to_dict().items() if v is not None}
        return json.dumps(data, indent=2)


@dataclass
class LLMRecommendation:
    """Single recommendation from LLM"""
    type: str  # RecommendationType value
    params: Dict[str, Any]
    urgency: str
    confidence: int
    reason_bullets: List[str]

    @classmethod
    def from_dict(cls, data: Dict) -> 'LLMRecommendation':
        return cls(
            type=data.get('type', 'hold'),
            params=data.get('params', {}),
            urgency=data.get('urgency', 'low'),
            confidence=data.get('confidence', 50),
            reason_bullets=data.get('reason_bullets', [])
        )


@dataclass
class LLMAdviceResponse:
    """Parsed LLM response"""
    recommendations: List[LLMRecommendation]
    summary: str
    market_assessment: str
    scenario_still_valid: bool
    risk_level: str

    @classmethod
    def from_dict(cls, data: Dict) -> 'LLMAdviceResponse':
        recs = [LLMRecommendation.from_dict(r) for r in data.get('recommendations', [])]
        return cls(
            recommendations=recs,
            summary=data.get('summary', ''),
            market_assessment=data.get('market_assessment', ''),
            scenario_still_valid=data.get('scenario_still_valid', True),
            risk_level=data.get('risk_level', 'medium')
        )


# ============================================================================
# LLM ADVISOR
# ============================================================================


class SupervisorLLMAdvisor:
    """
    LLM-powered advisor for position management.

    Called when rule-based triggers detect significant events.
    Provides context-aware recommendations with explanations.
    """

    def __init__(self):
        self.binance = binance_service
        self.openai = _openai_service
        self.model = OPENAI_MODEL
        logger.info("SupervisorLLMAdvisor initialized")

    # ========================================================================
    # MARKET CONTEXT BUILDING
    # ========================================================================

    async def build_market_context(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        position_data: Dict,
        scenario_data: Dict,
        events: List[SupervisorEvent]
    ) -> MarketContextPack:
        """
        Build complete market context pack for LLM.

        Args:
            position_data: Current position from exchange
            scenario_data: Original scenario from DB
            events: Triggered events

        Returns:
            MarketContextPack ready for LLM
        """
        # Get OHLCV data
        ohlcv_1h = await self._get_ohlcv_summary(symbol, "1h", limit=24)
        ohlcv_4h = await self._get_ohlcv_summary(symbol, "4h", limit=12)
        ohlcv_1d = await self._get_ohlcv_summary(symbol, "1d", limit=7)

        # Calculate technical context
        atr_pct = await self._calculate_atr_pct(symbol)
        volume_ratio = await self._calculate_volume_ratio(symbol)

        # Determine trends
        trend_1h = self._determine_trend(ohlcv_1h) if ohlcv_1h else None
        trend_4h = self._determine_trend(ohlcv_4h) if ohlcv_4h else None

        # Determine max urgency from events
        event_urgency = self._get_max_urgency(events)

        return MarketContextPack(
            # Position
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            entry_price=position_data.get('entry_price', 0),
            mark_price=position_data.get('mark_price', 0),
            qty=position_data.get('qty', 0),
            leverage=position_data.get('leverage', 1),
            unrealized_pnl=position_data.get('unrealized_pnl', 0),
            pnl_pct=position_data.get('pnl_pct', 0),
            liq_price=position_data.get('liq_price'),
            sl_current=position_data.get('sl_current'),
            tp_current=position_data.get('tp_current'),

            # Scenario
            invalidation_price=scenario_data.get('invalidation_price', 0),
            stop_loss_original=scenario_data.get('stop_loss', 0),
            take_profits=scenario_data.get('take_profits', []),
            scenario_bias=scenario_data.get('bias', 'unknown'),
            scenario_confidence=scenario_data.get('confidence', 0.5),
            time_valid_left_min=scenario_data.get('time_valid_left_min', 0),
            timeframe=scenario_data.get('timeframe', '4h'),

            # Market data
            ohlcv_1h=ohlcv_1h,
            ohlcv_4h=ohlcv_4h,
            ohlcv_1d=ohlcv_1d,

            # Technical
            atr_pct=atr_pct,
            volume_ratio=volume_ratio,
            trend_1h=trend_1h,
            trend_4h=trend_4h,

            # Events
            events=[e.value for e in events],
            event_urgency=event_urgency,
        )

    async def _get_ohlcv_summary(
        self, symbol: str, interval: str, limit: int = 24
    ) -> Optional[OHLCVSummary]:
        """Get OHLCV summary for timeframe"""
        try:
            klines = await self.binance.get_klines(symbol, interval, limit)
            if klines is None or klines.empty:
                return None

            # Calculate aggregates (klines is a DataFrame)
            opens = klines['open'].astype(float).tolist()
            highs = klines['high'].astype(float).tolist()
            lows = klines['low'].astype(float).tolist()
            closes = klines['close'].astype(float).tolist()
            volumes = klines['volume'].astype(float).tolist()

            first_open = opens[0]
            last_close = closes[-1]
            change_pct = ((last_close - first_open) / first_open) * 100

            return OHLCVSummary(
                timeframe=interval,
                open=first_open,
                high=max(highs),
                low=min(lows),
                close=last_close,
                volume=sum(volumes),
                change_pct=round(change_pct, 2),
                candles_count=len(klines)
            )
        except Exception as e:
            logger.warning(f"Failed to get OHLCV for {symbol} {interval}: {e}")
            return None

    async def _calculate_atr_pct(self, symbol: str) -> Optional[float]:
        """Calculate ATR as percentage of price"""
        try:
            klines = await self.binance.get_klines(symbol, "1h", 14)
            if klines is None or klines.empty or len(klines) < 14:
                return None

            trs = []
            for i in range(1, len(klines)):
                high = float(klines.iloc[i]['high'])
                low = float(klines.iloc[i]['low'])
                prev_close = float(klines.iloc[i-1]['close'])
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                trs.append(tr)

            atr = sum(trs) / len(trs)
            current_price = float(klines.iloc[-1]['close'])
            return round((atr / current_price) * 100, 3)
        except Exception as e:
            logger.warning(f"Failed to calculate ATR: {e}")
            return None

    async def _calculate_volume_ratio(self, symbol: str) -> Optional[float]:
        """Calculate current volume vs average"""
        try:
            klines = await self.binance.get_klines(symbol, "1h", 24)
            if klines is None or klines.empty or len(klines) < 24:
                return None

            volumes = klines['volume'].astype(float).tolist()
            avg_volume = sum(volumes[:-1]) / (len(volumes) - 1)
            current_volume = volumes[-1]

            if avg_volume == 0:
                return None

            return round(current_volume / avg_volume, 2)
        except Exception as e:
            logger.warning(f"Failed to calculate volume ratio: {e}")
            return None

    def _determine_trend(self, ohlcv: OHLCVSummary) -> str:
        """Simple trend determination"""
        if ohlcv.change_pct > 1:
            return "up"
        elif ohlcv.change_pct < -1:
            return "down"
        return "ranging"

    def _get_max_urgency(self, events: List[SupervisorEvent]) -> str:
        """Get maximum urgency from events"""
        critical = {
            SupervisorEvent.INVALIDATION_HIT,
            SupervisorEvent.LIQ_CRITICAL,
        }
        high = {
            SupervisorEvent.INVALIDATION_THREAT,
            SupervisorEvent.TP1_HIT,
            SupervisorEvent.TP2_HIT,
            SupervisorEvent.TIME_EXPIRED,
            SupervisorEvent.LIQ_WARNING,
        }
        medium = {
            SupervisorEvent.TP_NEAR,
            SupervisorEvent.TIME_WARNING,
            SupervisorEvent.PROFIT_MILESTONE,
            SupervisorEvent.STRUCTURE_BREAK,
            SupervisorEvent.MOMENTUM_FADE,
        }

        for event in events:
            if event in critical:
                return "critical"
        for event in events:
            if event in high:
                return "high"
        for event in events:
            if event in medium:
                return "med"

        return "low"

    # ========================================================================
    # LLM CALL
    # ========================================================================

    async def get_advice(
        self,
        context: MarketContextPack,
        timeout: int = 30
    ) -> Optional[LLMAdviceResponse]:
        """
        Get advice from LLM based on market context.

        Args:
            context: MarketContextPack with all data
            timeout: Max seconds to wait

        Returns:
            LLMAdviceResponse or None on error
        """
        try:
            # Build full prompt with system + user
            system_prompt = self._get_system_prompt()
            user_prompt = self._build_prompt(context)
            full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

            # JSON schema for structured output
            json_schema = {
                "name": "supervisor_advice",
                "schema": {
                    "type": "object",
                    "properties": {
                        "recommendations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "enum": ["move_sl", "set_break_even", "take_partial", "close_position", "reduce_position", "hold"]},
                                    "params": {"type": "object"},
                                    "urgency": {"type": "string", "enum": ["low", "med", "high", "critical"]},
                                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                                    "reason_bullets": {"type": "array", "items": {"type": "string"}}
                                },
                                "required": ["type", "params", "urgency", "confidence", "reason_bullets"]
                            }
                        },
                        "market_assessment": {"type": "string"},
                        "scenario_still_valid": {"type": "boolean"},
                        "risk_level": {"type": "string", "enum": ["safe", "medium", "high", "critical"]},
                        "summary": {"type": "string"}
                    },
                    "required": ["recommendations", "market_assessment", "scenario_still_valid", "risk_level", "summary"]
                },
                "strict": True
            }

            response = await self.openai.structured_completion(
                prompt=full_prompt,
                json_schema=json_schema,
                model=self.model,
                temperature=0.3
            )

            if not response:
                logger.warning("Empty LLM response")
                return None

            # Parse JSON response
            advice = LLMAdviceResponse.from_dict(response)

            logger.info(
                f"LLM advice for {context.trade_id}: "
                f"{len(advice.recommendations)} recommendations, "
                f"risk={advice.risk_level}"
            )

            return advice

        except Exception as e:
            logger.error(f"LLM advice error: {e}")
            return None

    def _get_system_prompt(self) -> str:
        """System prompt for LLM"""
        return """You are a professional futures trading advisor. Your role is to analyze open positions and provide actionable recommendations.

CRITICAL RULES:
1. NEVER recommend widening stop loss (moving SL further from entry = more risk)
2. For LONG: new_sl must be >= current_sl (can only move UP)
3. For SHORT: new_sl must be <= current_sl (can only move DOWN)
4. Always prioritize capital preservation over profit maximization
5. If invalidation is breached, recommend closing or reducing position
6. If scenario is expired with loss, recommend closing

RESPONSE FORMAT (strict JSON):
{
  "recommendations": [
    {
      "type": "move_sl|set_break_even|take_partial|close_position|reduce_position|hold",
      "params": {"new_sl": 123.45, "percent": 25},
      "urgency": "low|med|high|critical",
      "confidence": 0-100,
      "reason_bullets": ["reason 1", "reason 2"]
    }
  ],
  "summary": "1-2 sentence summary for trader",
  "market_assessment": "Brief market context",
  "scenario_still_valid": true|false,
  "risk_level": "safe|medium|high|critical"
}

Be concise. Focus on actionable advice. Max 3 recommendations."""

    def _build_prompt(self, context: MarketContextPack) -> str:
        """Build user prompt with context"""
        return f"""Analyze this position and provide recommendations.

POSITION DATA:
{context.to_llm_prompt_json()}

TRIGGERED EVENTS: {', '.join(context.events)}
EVENT URGENCY: {context.event_urgency}

Provide your analysis and recommendations in JSON format."""


# ============================================================================
# GUARDRAILS
# ============================================================================


class SupervisorGuardrails:
    """
    Validates and sanitizes LLM recommendations.

    Ensures safety rules are never violated:
    - SL cannot widen risk
    - Prices must respect tick size
    - Min distances must be maintained
    """

    def __init__(self):
        self.min_sl_distance_pct = 0.1  # 0.1% min distance from price

    def validate_recommendations(
        self,
        recommendations: List[LLMRecommendation],
        position: Dict,
        scenario: Dict
    ) -> List[LLMRecommendation]:
        """
        Validate and filter recommendations.

        Args:
            recommendations: Raw LLM recommendations
            position: Current position data
            scenario: Original scenario data

        Returns:
            Validated recommendations (may be empty)
        """
        validated = []

        for rec in recommendations:
            try:
                if rec.type == RecommendationType.MOVE_SL.value:
                    if self._validate_sl_move(rec, position):
                        validated.append(rec)
                    else:
                        logger.warning(f"Rejected SL move: {rec.params}")

                elif rec.type == RecommendationType.SET_BREAK_EVEN.value:
                    if self._validate_breakeven(rec, position):
                        validated.append(rec)
                    else:
                        logger.warning(f"Rejected breakeven: {rec.params}")

                elif rec.type == RecommendationType.TAKE_PARTIAL.value:
                    if self._validate_partial(rec, position):
                        validated.append(rec)

                elif rec.type == RecommendationType.CLOSE_POSITION.value:
                    # Always allow close
                    validated.append(rec)

                elif rec.type == RecommendationType.REDUCE_POSITION.value:
                    if self._validate_reduce(rec, position):
                        validated.append(rec)

                elif rec.type == RecommendationType.HOLD.value:
                    validated.append(rec)

                else:
                    logger.warning(f"Unknown recommendation type: {rec.type}")

            except Exception as e:
                logger.error(f"Validation error for {rec.type}: {e}")

        return validated

    def _validate_sl_move(
        self, rec: LLMRecommendation, position: Dict
    ) -> bool:
        """Validate SL move doesn't widen risk"""
        new_sl = rec.params.get('new_sl')
        if not new_sl:
            return False

        current_sl = position.get('sl_current')
        side = position.get('side', 'Long')
        mark_price = position.get('mark_price', 0)

        # Check min distance from price
        distance_pct = abs(new_sl - mark_price) / mark_price * 100
        if distance_pct < self.min_sl_distance_pct:
            logger.warning(f"SL too close to price: {distance_pct:.2f}%")
            return False

        # If no current SL, allow setting one
        if not current_sl:
            return True

        # CRITICAL: SL cannot widen risk
        if side == "Long":
            # Long: new SL must be >= current SL (higher = tighter)
            if new_sl < current_sl:
                logger.warning(
                    f"Long SL would widen risk: {new_sl} < {current_sl}"
                )
                return False
        else:
            # Short: new SL must be <= current SL (lower = tighter)
            if new_sl > current_sl:
                logger.warning(
                    f"Short SL would widen risk: {new_sl} > {current_sl}"
                )
                return False

        return True

    def _validate_breakeven(
        self, rec: LLMRecommendation, position: Dict
    ) -> bool:
        """Validate breakeven setting"""
        new_sl = rec.params.get('new_sl')
        if not new_sl:
            return False

        entry = position.get('entry_price', 0)
        side = position.get('side', 'Long')

        # BE should be near entry (within 1%)
        distance_pct = abs(new_sl - entry) / entry * 100
        if distance_pct > 1:
            logger.warning(f"BE too far from entry: {distance_pct:.2f}%")
            return False

        # Must still pass SL validation
        return self._validate_sl_move(rec, position)

    def _validate_partial(
        self, rec: LLMRecommendation, position: Dict
    ) -> bool:
        """Validate partial close"""
        percent = rec.params.get('percent', 0)

        # Reasonable range: 10-90%
        if percent < 10 or percent > 90:
            logger.warning(f"Invalid partial percent: {percent}")
            return False

        return True

    def _validate_reduce(
        self, rec: LLMRecommendation, position: Dict
    ) -> bool:
        """Validate position reduction"""
        percent = rec.params.get('percent', 0)

        # Reasonable range: 10-80%
        if percent < 10 or percent > 80:
            logger.warning(f"Invalid reduce percent: {percent}")
            return False

        return True


# ============================================================================
# SINGLETON
# ============================================================================

supervisor_llm_advisor = SupervisorLLMAdvisor()
supervisor_guardrails = SupervisorGuardrails()
