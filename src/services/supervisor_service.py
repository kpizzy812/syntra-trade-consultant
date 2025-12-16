"""
Syntra Supervisor Service

HYBRID APPROACH: Rules detect events -> LLM analyzes -> Guardrails validate

Advisory service for managing open positions:
- Rules detect events (invalidation, TP hit, liq risk, etc.)
- LLM provides context-aware recommendations
- Guardrails validate safety (SL never widens risk)
- Fallback to rule-based on LLM error
- Anti-spam cooldowns
"""
import json
import uuid
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    ScenarioSnapshot,
    SupervisorAdvice,
    SupervisorAction,
    SupervisorUrgency,
    SupervisorRiskState,
    RecommendationType,
    RecommendationStatus,
    SupervisorEvent,
)
from src.services.binance_service import binance_service
from src.services.supervisor_llm_advisor import (
    supervisor_llm_advisor,
    supervisor_guardrails,
)


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class PositionSnapshot:
    """Position state from trading bot"""
    trade_id: str
    symbol: str
    side: str  # "Long" / "Short"
    qty: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    pnl_pct: float
    leverage: int
    liq_price: Optional[float]
    sl_current: Optional[float]
    tp_current: Optional[List[Dict]]
    updated_at: str


@dataclass
class Recommendation:
    """Single recommendation"""
    action_id: str
    type: str  # RecommendationType value
    params: Dict[str, Any]
    urgency: str  # SupervisorUrgency value
    confidence: int  # 0-100
    reason_bullets: List[str]
    guards: List[str]
    expires_at: str  # ISO datetime


@dataclass
class AdvicePack:
    """Full advice package for a trade"""
    pack_id: str
    trade_id: str
    user_id: int
    symbol: str
    market_summary: str
    scenario_valid: bool
    time_valid_left_min: int
    risk_state: str  # SupervisorRiskState value
    recommendations: List[Dict]
    cooldown_until: Optional[str]
    price_at_creation: float
    created_at: str
    expires_at: str


# ============================================================================
# CONSTANTS
# ============================================================================

# Cooldown settings
DEFAULT_COOLDOWN_MINUTES = 15
MIN_COOLDOWN_MINUTES = 5

# Risk thresholds
LIQ_PROXIMITY_WARN_PCT = 15  # Warn if price within 15% of liquidation
LIQ_PROXIMITY_CRITICAL_PCT = 8  # Critical if within 8%
INVALIDATION_THREAT_PCT = 2  # Warn if within 2% of invalidation

# Advice expiration
ADVICE_EXPIRATION_MINUTES = 30

# LLM settings
LLM_ENABLED = True  # Set to False to use pure rules
LLM_MIN_URGENCY = "med"  # Minimum urgency to trigger LLM (low/med/high/critical)
LLM_TIMEOUT_SECONDS = 30


# ============================================================================
# SUPERVISOR SERVICE
# ============================================================================


class SupervisorService:
    """
    Main supervisor service for position management advice.

    Responsibilities:
    1. Register new trades with scenario snapshots
    2. Evaluate positions against scenarios
    3. Generate recommendations
    4. Validate recommendations (safety!)
    5. Track actions and cooldowns
    """

    def __init__(self):
        self.binance = binance_service
        logger.info("SupervisorService initialized")

    # ========================================================================
    # SCENARIO REGISTRATION
    # ========================================================================

    async def register_scenario(
        self,
        session: AsyncSession,
        trade_id: str,
        user_id: int,
        symbol: str,
        timeframe: str,
        side: str,
        scenario_data: Dict[str, Any]
    ) -> ScenarioSnapshot:
        """
        Register a new trade with its scenario snapshot.

        Args:
            trade_id: Unique trade ID from trading bot
            user_id: Telegram user ID
            symbol: Trading pair (e.g., BTCUSDT)
            timeframe: Analysis timeframe (1h, 4h, 1d)
            side: Position side (Long/Short)
            scenario_data: Full scenario from futures-scenarios API

        Returns:
            Created ScenarioSnapshot
        """
        # Extract scenario fields
        entry_plan = scenario_data.get("entry_plan", {})
        orders = entry_plan.get("orders", [])

        # Calculate entry zone from orders
        if orders:
            prices = [o["price"] for o in orders]
            entry_zone_low = min(prices)
            entry_zone_high = max(prices)
        else:
            # Fallback to legacy entry
            entry = scenario_data.get("entry", {})
            entry_zone_low = entry.get("price_min", 0)
            entry_zone_high = entry.get("price_max", 0)

        # Get stop loss
        stop_loss_data = scenario_data.get("stop_loss", {})
        stop_loss = stop_loss_data.get("recommended", 0)

        # Get invalidation price (KEY!)
        invalidation = scenario_data.get("invalidation", {})
        invalidation_price = invalidation.get("price", stop_loss)

        # Get take profits
        targets = scenario_data.get("targets", [])
        take_profits = [
            {
                "level": t.get("level"),
                "price": t.get("price"),
                "pct": t.get("partial_close_pct"),
                "rr": t.get("rr")
            }
            for t in targets
        ]

        # Get conditions
        conditions = scenario_data.get("conditions", [])

        # Calculate valid_until
        time_valid_hours = scenario_data.get("time_valid_hours", 48)
        valid_until = datetime.now(UTC) + timedelta(hours=time_valid_hours)

        # Create snapshot
        snapshot = ScenarioSnapshot(
            trade_id=trade_id,
            user_id=user_id,
            symbol=symbol,
            timeframe=timeframe,
            side=side,
            bias=scenario_data.get("bias", "unknown"),
            confidence=scenario_data.get("confidence", 0.5),
            entry_zone_low=entry_zone_low,
            entry_zone_high=entry_zone_high,
            stop_loss=stop_loss,
            invalidation_price=invalidation_price,
            take_profits_json=json.dumps(take_profits),
            conditions_json=json.dumps(conditions),
            valid_until=valid_until,
            source="syntra",
            is_active=True,
        )

        session.add(snapshot)
        await session.commit()
        await session.refresh(snapshot)

        logger.info(
            f"Registered scenario for trade {trade_id}: "
            f"{symbol} {side}, invalidation={invalidation_price}"
        )

        return snapshot

    async def deactivate_scenario(
        self,
        session: AsyncSession,
        trade_id: str,
        reason: str = "position_closed"
    ) -> bool:
        """Deactivate scenario when position is closed."""
        stmt = select(ScenarioSnapshot).where(
            ScenarioSnapshot.trade_id == trade_id
        )
        result = await session.execute(stmt)
        snapshot = result.scalar_one_or_none()

        if not snapshot:
            logger.warning(f"Scenario not found for trade {trade_id}")
            return False

        snapshot.is_active = False
        snapshot.deactivated_reason = reason
        snapshot.deactivated_at = datetime.now(UTC)

        await session.commit()
        logger.info(f"Deactivated scenario for trade {trade_id}: {reason}")

        return True

    # ========================================================================
    # POSITION SYNC & EVALUATION
    # ========================================================================

    async def sync_positions(
        self,
        session: AsyncSession,
        user_id: int,
        positions: List[Dict[str, Any]]
    ) -> List[AdvicePack]:
        """
        Sync positions from trading bot and generate advice.

        Args:
            user_id: Telegram user ID
            positions: List of PositionSnapshot dicts from trading bot

        Returns:
            List of AdvicePack for positions that need attention
        """
        advice_packs = []

        for pos_data in positions:
            position = PositionSnapshot(**pos_data)

            # Get scenario for this trade
            stmt = select(ScenarioSnapshot).where(
                and_(
                    ScenarioSnapshot.trade_id == position.trade_id,
                    ScenarioSnapshot.is_active == True
                )
            )
            result = await session.execute(stmt)
            scenario = result.scalar_one_or_none()

            if not scenario:
                logger.debug(f"No active scenario for trade {position.trade_id}")
                continue

            # Check cooldown
            if await self._is_in_cooldown(session, position.trade_id):
                logger.debug(f"Trade {position.trade_id} in cooldown")
                continue

            # Evaluate and generate advice
            advice = await self._evaluate_position(
                session, scenario, position, user_id
            )

            if advice and advice.recommendations:
                advice_packs.append(advice)

        return advice_packs

    async def _evaluate_position(
        self,
        session: AsyncSession,
        scenario: ScenarioSnapshot,
        position: PositionSnapshot,
        user_id: int
    ) -> Optional[AdvicePack]:
        """
        HYBRID evaluation: Rules detect events -> LLM analyzes -> Guardrails validate.

        Flow:
        1. Rules detect events (invalidation, TP hit, etc.)
        2. If urgency >= threshold, call LLM for smart recommendations
        3. Guardrails validate LLM output
        4. Fallback to rule-based if LLM fails
        """
        # Parse scenario data
        take_profits = json.loads(scenario.take_profits_json)
        time_left_min = self._get_time_left_minutes(scenario.valid_until)

        price = position.mark_price
        entry = position.entry_price
        side = position.side

        # ====================================================================
        # STEP 1: DETECT EVENTS (rule-based triggers)
        # ====================================================================
        events = self._detect_events(scenario, position, take_profits, time_left_min)

        if not events:
            # No events = HOLD, no action needed
            return None

        # Determine max urgency
        max_urgency = self._get_max_event_urgency(events)

        logger.info(
            f"Events detected for {position.trade_id}: "
            f"{[e.value for e in events]}, urgency={max_urgency}"
        )

        # ====================================================================
        # STEP 2: DECIDE LLM vs RULES
        # ====================================================================
        use_llm = (
            LLM_ENABLED and
            self._urgency_meets_threshold(max_urgency, LLM_MIN_URGENCY)
        )

        recommendations = []
        market_summary = ""
        scenario_valid = True

        if use_llm:
            # ================================================================
            # STEP 3a: LLM PATH
            # ================================================================
            logger.info(f"Calling LLM for {position.trade_id}")

            try:
                # Build market context
                position_data = {
                    'entry_price': entry,
                    'mark_price': price,
                    'qty': position.qty,
                    'leverage': position.leverage,
                    'unrealized_pnl': position.unrealized_pnl,
                    'pnl_pct': position.pnl_pct,
                    'liq_price': position.liq_price,
                    'sl_current': position.sl_current,
                    'tp_current': position.tp_current,
                    'side': side,
                }

                scenario_data = {
                    'invalidation_price': scenario.invalidation_price,
                    'stop_loss': scenario.stop_loss,
                    'take_profits': take_profits,
                    'bias': scenario.bias,
                    'confidence': scenario.confidence,
                    'time_valid_left_min': time_left_min,
                    'timeframe': scenario.timeframe,
                }

                context = await supervisor_llm_advisor.build_market_context(
                    trade_id=position.trade_id,
                    symbol=position.symbol,
                    side=side,
                    position_data=position_data,
                    scenario_data=scenario_data,
                    events=events
                )

                # Call LLM
                llm_response = await supervisor_llm_advisor.get_advice(
                    context, timeout=LLM_TIMEOUT_SECONDS
                )

                if llm_response and llm_response.recommendations:
                    # Validate through guardrails
                    validated_recs = supervisor_guardrails.validate_recommendations(
                        llm_response.recommendations,
                        position_data,
                        scenario_data
                    )

                    if validated_recs:
                        # Convert to Recommendation dataclass
                        recommendations = [
                            Recommendation(
                                action_id=str(uuid.uuid4())[:8],
                                type=rec.type,
                                params=rec.params,
                                urgency=rec.urgency,
                                confidence=rec.confidence,
                                reason_bullets=rec.reason_bullets,
                                guards=["guardrails_passed"],
                                expires_at=(datetime.now(UTC) + timedelta(minutes=30)).isoformat()
                            )
                            for rec in validated_recs
                        ]
                        market_summary = llm_response.summary or llm_response.market_assessment
                        scenario_valid = llm_response.scenario_still_valid

                        logger.info(
                            f"LLM returned {len(recommendations)} validated recommendations"
                        )
                    else:
                        logger.warning("All LLM recommendations rejected by guardrails, using fallback")
                        recommendations = []
                else:
                    logger.warning("LLM returned no recommendations, using fallback")

            except Exception as e:
                logger.error(f"LLM error, using fallback: {e}")

        # ====================================================================
        # STEP 3b: FALLBACK TO RULES (if LLM disabled, failed, or empty)
        # ====================================================================
        if not recommendations:
            logger.info(f"Using rule-based fallback for {position.trade_id}")
            recommendations = self._generate_rule_based_recommendations(
                scenario, position, events, take_profits, time_left_min
            )
            market_summary = self._build_market_summary(scenario, position, events)
            scenario_valid = not self._check_invalidation(scenario.invalidation_price, price, side) and time_left_min > 0

        if not recommendations:
            return None

        # ====================================================================
        # STEP 4: BUILD ADVICE PACK
        # ====================================================================
        risk_state = self._determine_risk_state(events, position)

        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=ADVICE_EXPIRATION_MINUTES)
        cooldown_until = now + timedelta(minutes=DEFAULT_COOLDOWN_MINUTES)

        advice = AdvicePack(
            pack_id=str(uuid.uuid4())[:8],
            trade_id=position.trade_id,
            user_id=user_id,
            symbol=position.symbol,
            market_summary=market_summary,
            scenario_valid=scenario_valid,
            time_valid_left_min=max(0, time_left_min),
            risk_state=risk_state.value,
            recommendations=[asdict(r) for r in recommendations],
            cooldown_until=cooldown_until.isoformat(),
            price_at_creation=price,
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
        )

        # Save to DB
        await self._save_advice(session, scenario, advice)

        return advice

    # ========================================================================
    # EVENT DETECTION (rule-based)
    # ========================================================================

    def _detect_events(
        self,
        scenario: ScenarioSnapshot,
        position: PositionSnapshot,
        take_profits: List[Dict],
        time_left_min: int
    ) -> List[SupervisorEvent]:
        """Detect all relevant events based on rules."""
        events = []

        price = position.mark_price
        entry = position.entry_price
        side = position.side

        # CRITICAL: Invalidation hit
        if self._check_invalidation(scenario.invalidation_price, price, side):
            events.append(SupervisorEvent.INVALIDATION_HIT)
        # HIGH: Invalidation threat (approaching)
        elif self._check_invalidation_threat(scenario.invalidation_price, price, side):
            events.append(SupervisorEvent.INVALIDATION_THREAT)

        # CRITICAL: Liquidation risk
        liq_risk = self._check_liq_proximity(position)
        if liq_risk == "critical":
            events.append(SupervisorEvent.LIQ_CRITICAL)
        elif liq_risk == "high":
            events.append(SupervisorEvent.LIQ_WARNING)

        # Time validity
        if time_left_min <= 0:
            events.append(SupervisorEvent.TIME_EXPIRED)
        elif time_left_min <= 30:
            events.append(SupervisorEvent.TIME_WARNING)

        # TP zones
        tp_reached = self._check_tp_zones(take_profits, price, side, entry)
        if tp_reached:
            tp_level, _ = tp_reached
            if tp_level == 1:
                events.append(SupervisorEvent.TP1_HIT)
            elif tp_level >= 2:
                events.append(SupervisorEvent.TP2_HIT)
        elif self._check_tp_near(take_profits, price, side):
            events.append(SupervisorEvent.TP_NEAR)

        # Profit milestones
        if position.pnl_pct >= 5:
            events.append(SupervisorEvent.PROFIT_MILESTONE)
        elif position.pnl_pct >= 2:
            events.append(SupervisorEvent.PROFIT_MILESTONE)
        elif position.pnl_pct >= 1:
            events.append(SupervisorEvent.PROFIT_MILESTONE)

        return events

    def _check_invalidation_threat(
        self, invalidation_price: float, current_price: float, side: str
    ) -> bool:
        """Check if price is approaching invalidation (within 2%)."""
        if invalidation_price == 0:
            return False

        distance_pct = abs(current_price - invalidation_price) / current_price * 100

        if side == "Long":
            # For long, invalidation is below price
            return current_price > invalidation_price and distance_pct <= INVALIDATION_THREAT_PCT
        else:
            # For short, invalidation is above price
            return current_price < invalidation_price and distance_pct <= INVALIDATION_THREAT_PCT

    def _check_tp_near(
        self, take_profits: List[Dict], price: float, side: str
    ) -> bool:
        """Check if price is approaching any TP (within 1%)."""
        for tp in take_profits:
            tp_price = tp.get("price", 0)
            if tp_price == 0:
                continue

            distance_pct = abs(price - tp_price) / price * 100

            if side == "Long" and price < tp_price and distance_pct <= 1:
                return True
            elif side == "Short" and price > tp_price and distance_pct <= 1:
                return True

        return False

    def _get_max_event_urgency(self, events: List[SupervisorEvent]) -> str:
        """Get maximum urgency from events list."""
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

    def _urgency_meets_threshold(self, urgency: str, threshold: str) -> bool:
        """Check if urgency meets minimum threshold for LLM."""
        levels = {"low": 0, "med": 1, "high": 2, "critical": 3}
        return levels.get(urgency, 0) >= levels.get(threshold, 1)

    # ========================================================================
    # RULE-BASED FALLBACK
    # ========================================================================

    def _generate_rule_based_recommendations(
        self,
        scenario: ScenarioSnapshot,
        position: PositionSnapshot,
        events: List[SupervisorEvent],
        take_profits: List[Dict],
        time_left_min: int
    ) -> List[Recommendation]:
        """Generate recommendations using pure rule-based logic (fallback)."""
        recommendations = []

        price = position.mark_price
        entry = position.entry_price
        side = position.side

        # CRITICAL: Invalidation hit -> Close
        if SupervisorEvent.INVALIDATION_HIT in events:
            recommendations.append(self._create_close_recommendation(
                position, "Invalidation price breached"
            ))

        # CRITICAL: Liquidation risk -> Reduce
        if SupervisorEvent.LIQ_CRITICAL in events:
            recommendations.append(self._create_reduce_recommendation(
                position, 50, "Liquidation risk critical"
            ))

        # Time expired with loss -> Close
        if SupervisorEvent.TIME_EXPIRED in events and position.pnl_pct < 0:
            recommendations.append(self._create_close_recommendation(
                position, "Scenario expired with negative PnL"
            ))

        # TP hit -> Partial + BE
        tp_events = {SupervisorEvent.TP1_HIT, SupervisorEvent.TP2_HIT}
        if events and any(e in tp_events for e in events):
            tp_reached = self._check_tp_zones(take_profits, price, side, entry)
            if tp_reached:
                tp_level, tp_price = tp_reached
                recommendations.append(self._create_partial_recommendation(
                    position, tp_level, tp_price
                ))

                # Suggest breakeven if SL not already at entry
                if position.sl_current:
                    if side == "Long" and position.sl_current < entry:
                        recommendations.append(self._create_be_recommendation(position, entry))
                    elif side == "Short" and position.sl_current > entry:
                        recommendations.append(self._create_be_recommendation(position, entry))

        # Profit protection - tighter SL
        if SupervisorEvent.PROFIT_MILESTONE in events and position.pnl_pct > 1:
            sl_suggestion = self._suggest_tighter_sl(position, scenario)
            if sl_suggestion:
                recommendations.append(sl_suggestion)

        return recommendations

    def _build_market_summary(
        self,
        scenario: ScenarioSnapshot,
        position: PositionSnapshot,
        events: List[SupervisorEvent]
    ) -> str:
        """Build short market summary for rule-based path."""
        parts = []

        # PnL status
        if position.pnl_pct >= 0:
            parts.append(f"In profit +{position.pnl_pct:.1f}%")
        else:
            parts.append(f"In loss {position.pnl_pct:.1f}%")

        # Main event
        if events:
            main_event = events[0]
            if main_event == SupervisorEvent.INVALIDATION_HIT:
                parts.append("Invalidation breached!")
            elif main_event == SupervisorEvent.INVALIDATION_THREAT:
                parts.append("Approaching invalidation")
            elif main_event in {SupervisorEvent.TP1_HIT, SupervisorEvent.TP2_HIT}:
                parts.append("TP zone reached")
            elif main_event == SupervisorEvent.LIQ_CRITICAL:
                parts.append("Liquidation risk!")
            elif main_event == SupervisorEvent.TIME_EXPIRED:
                parts.append("Scenario expired")

        return ". ".join(parts)

    # ========================================================================
    # TRIGGER CHECKS
    # ========================================================================

    def _check_invalidation(
        self, invalidation_price: float, current_price: float, side: str
    ) -> bool:
        """Check if invalidation price is breached."""
        if side == "Long":
            return current_price <= invalidation_price
        else:
            return current_price >= invalidation_price

    def _get_time_left_minutes(self, valid_until: datetime) -> int:
        """Get minutes left until scenario expires."""
        now = datetime.now(UTC)
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=UTC)
        delta = valid_until - now
        return int(delta.total_seconds() / 60)

    def _check_liq_proximity(self, position: PositionSnapshot) -> Optional[str]:
        """Check proximity to liquidation price."""
        if not position.liq_price or position.liq_price == 0:
            return None

        price = position.mark_price
        liq = position.liq_price

        distance_pct = abs(price - liq) / price * 100

        if distance_pct <= LIQ_PROXIMITY_CRITICAL_PCT:
            return "critical"
        elif distance_pct <= LIQ_PROXIMITY_WARN_PCT:
            return "high"

        return None

    def _check_tp_zones(
        self,
        take_profits: List[Dict],
        price: float,
        side: str,
        entry: float
    ) -> Optional[tuple]:
        """Check if any TP zone is reached."""
        for tp in take_profits:
            tp_price = tp.get("price", 0)
            tp_level = tp.get("level", 1)

            # Check if price reached TP zone (within 0.5%)
            if side == "Long":
                if price >= tp_price * 0.995:
                    return (tp_level, tp_price)
            else:
                if price <= tp_price * 1.005:
                    return (tp_level, tp_price)

        return None

    def _suggest_tighter_sl(
        self,
        position: PositionSnapshot,
        scenario: ScenarioSnapshot
    ) -> Optional[Recommendation]:
        """Suggest tighter SL if position is in profit."""
        if not position.sl_current:
            return None

        price = position.mark_price
        entry = position.entry_price
        current_sl = position.sl_current
        side = position.side

        # Calculate suggested SL (trail by 50% of profit)
        profit_distance = abs(price - entry)
        trail_distance = profit_distance * 0.5

        if side == "Long":
            new_sl = price - trail_distance
            # Must be tighter than current (higher for long)
            if new_sl <= current_sl:
                return None
        else:
            new_sl = price + trail_distance
            # Must be tighter than current (lower for short)
            if new_sl >= current_sl:
                return None

        return Recommendation(
            action_id=str(uuid.uuid4())[:8],
            type=RecommendationType.MOVE_SL.value,
            params={"new_sl": round(new_sl, 2)},
            urgency=SupervisorUrgency.MED.value,
            confidence=70,
            reason_bullets=[
                f"Position in {position.pnl_pct:.1f}% profit",
                f"Trail SL to lock in gains",
                f"New SL: ${new_sl:.2f}"
            ],
            guards=["sl_not_wider", "min_distance_ok"],
            expires_at=(datetime.now(UTC) + timedelta(minutes=30)).isoformat()
        )

    # ========================================================================
    # RECOMMENDATION BUILDERS
    # ========================================================================

    def _create_close_recommendation(
        self,
        position: PositionSnapshot,
        reason: str
    ) -> Recommendation:
        """Create CLOSE_POSITION recommendation."""
        return Recommendation(
            action_id=str(uuid.uuid4())[:8],
            type=RecommendationType.CLOSE_POSITION.value,
            params={},
            urgency=SupervisorUrgency.CRITICAL.value,
            confidence=90,
            reason_bullets=[reason, "Scenario no longer valid"],
            guards=["position_exists"],
            expires_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat()
        )

    def _create_reduce_recommendation(
        self,
        position: PositionSnapshot,
        percent: int,
        reason: str
    ) -> Recommendation:
        """Create REDUCE_POSITION recommendation."""
        return Recommendation(
            action_id=str(uuid.uuid4())[:8],
            type=RecommendationType.REDUCE_POSITION.value,
            params={"percent": percent},
            urgency=SupervisorUrgency.CRITICAL.value,
            confidence=85,
            reason_bullets=[reason, f"Reduce position by {percent}%"],
            guards=["min_qty_ok"],
            expires_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat()
        )

    def _create_partial_recommendation(
        self,
        position: PositionSnapshot,
        tp_level: int,
        tp_price: float
    ) -> Recommendation:
        """Create TAKE_PARTIAL recommendation."""
        # Standard partial close percentages by TP level
        pct_map = {1: 25, 2: 35, 3: 40}
        percent = pct_map.get(tp_level, 25)

        return Recommendation(
            action_id=str(uuid.uuid4())[:8],
            type=RecommendationType.TAKE_PARTIAL.value,
            params={"percent": percent, "target_price": tp_price},
            urgency=SupervisorUrgency.HIGH.value,
            confidence=80,
            reason_bullets=[
                f"TP{tp_level} zone reached (${tp_price:.2f})",
                f"Take {percent}% profit",
                f"Current PnL: {position.pnl_pct:.1f}%"
            ],
            guards=["min_qty_ok"],
            expires_at=(datetime.now(UTC) + timedelta(minutes=20)).isoformat()
        )

    def _create_be_recommendation(
        self,
        position: PositionSnapshot,
        entry_price: float
    ) -> Recommendation:
        """Create SET_BREAK_EVEN recommendation."""
        # Add small buffer to avoid exact breakeven
        buffer = entry_price * 0.001  # 0.1%

        if position.side == "Long":
            be_price = entry_price + buffer
        else:
            be_price = entry_price - buffer

        return Recommendation(
            action_id=str(uuid.uuid4())[:8],
            type=RecommendationType.SET_BREAK_EVEN.value,
            params={"new_sl": round(be_price, 2)},
            urgency=SupervisorUrgency.HIGH.value,
            confidence=85,
            reason_bullets=[
                "Move SL to breakeven",
                "Protect position from loss",
                f"New SL: ${be_price:.2f}"
            ],
            guards=["sl_not_wider"],
            expires_at=(datetime.now(UTC) + timedelta(minutes=20)).isoformat()
        )

    # ========================================================================
    # HELPERS
    # ========================================================================

    def _determine_risk_state(
        self,
        events: List[SupervisorEvent],
        position: PositionSnapshot
    ) -> SupervisorRiskState:
        """Determine overall risk state based on events."""
        critical_events = {
            SupervisorEvent.INVALIDATION_HIT,
            SupervisorEvent.LIQ_CRITICAL,
        }
        high_events = {
            SupervisorEvent.INVALIDATION_THREAT,
            SupervisorEvent.LIQ_WARNING,
            SupervisorEvent.TIME_EXPIRED,
        }

        for event in events:
            if event in critical_events:
                return SupervisorRiskState.CRITICAL

        for event in events:
            if event in high_events:
                return SupervisorRiskState.HIGH

        if position.pnl_pct < -2:
            return SupervisorRiskState.HIGH
        if position.pnl_pct < 0:
            return SupervisorRiskState.MEDIUM

        return SupervisorRiskState.SAFE

    async def _is_in_cooldown(
        self, session: AsyncSession, trade_id: str
    ) -> bool:
        """Check if trade is in cooldown period."""
        stmt = select(SupervisorAdvice).where(
            SupervisorAdvice.trade_id == trade_id
        ).order_by(SupervisorAdvice.created_at.desc()).limit(1)

        result = await session.execute(stmt)
        last_advice = result.scalar_one_or_none()

        if not last_advice or not last_advice.cooldown_until:
            return False

        cooldown = last_advice.cooldown_until
        if cooldown.tzinfo is None:
            cooldown = cooldown.replace(tzinfo=UTC)

        return datetime.now(UTC) < cooldown

    async def _save_advice(
        self,
        session: AsyncSession,
        scenario: ScenarioSnapshot,
        advice: AdvicePack
    ) -> SupervisorAdvice:
        """Save advice pack to database."""
        db_advice = SupervisorAdvice(
            scenario_id=scenario.id,
            trade_id=advice.trade_id,
            user_id=advice.user_id,
            market_summary=advice.market_summary,
            scenario_valid=advice.scenario_valid,
            time_valid_left_min=advice.time_valid_left_min,
            risk_state=advice.risk_state,
            price_at_creation=advice.price_at_creation,
            recommendations_json=json.dumps(advice.recommendations),
            cooldown_until=datetime.fromisoformat(advice.cooldown_until) if advice.cooldown_until else None,
            expires_at=datetime.fromisoformat(advice.expires_at),
        )

        session.add(db_advice)
        await session.commit()

        return db_advice

    # ========================================================================
    # ACTION TRACKING
    # ========================================================================

    async def log_action_result(
        self,
        session: AsyncSession,
        trade_id: str,
        action_id: str,
        status: str,
        result: Optional[Dict] = None
    ) -> bool:
        """Log result of action execution."""
        # Find the advice containing this action
        stmt = select(SupervisorAdvice).where(
            SupervisorAdvice.trade_id == trade_id
        ).order_by(SupervisorAdvice.created_at.desc()).limit(1)

        result_db = await session.execute(stmt)
        advice = result_db.scalar_one_or_none()

        if not advice:
            logger.warning(f"No advice found for trade {trade_id}")
            return False

        # Find action in recommendations
        recommendations = json.loads(advice.recommendations_json)
        action_found = None
        for rec in recommendations:
            if rec.get("action_id") == action_id:
                action_found = rec
                break

        if not action_found:
            logger.warning(f"Action {action_id} not found in advice")
            return False

        # Create action log
        action_log = SupervisorAction(
            advice_id=advice.id,
            trade_id=trade_id,
            user_id=advice.user_id,
            action_id=action_id,
            action_type=action_found.get("type", "unknown"),
            params_json=json.dumps(action_found.get("params", {})),
            status=status,
            executed_at=datetime.now(UTC) if status == RecommendationStatus.APPLIED.value else None,
            execution_result=json.dumps(result) if result else None,
        )

        session.add(action_log)
        await session.commit()

        logger.info(f"Logged action {action_id} for trade {trade_id}: {status}")

        return True

    async def get_active_scenarios(
        self, session: AsyncSession, user_id: int
    ) -> List[ScenarioSnapshot]:
        """Get all active scenarios for a user."""
        stmt = select(ScenarioSnapshot).where(
            and_(
                ScenarioSnapshot.user_id == user_id,
                ScenarioSnapshot.is_active == True
            )
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


# Singleton instance
supervisor_service = SupervisorService()
