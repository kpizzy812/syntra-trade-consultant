# coding: utf-8
"""
Trading Modes - SyntraAI Side

Minimal mode configuration для генерации сценариев.
Содержит параметры которые влияют на LLM prompt и валидацию.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ModeConfig:
    """Mode configuration для scenario generation."""
    mode_id: str
    name: str
    emoji: str
    # Leverage limits
    max_leverage: int
    default_leverage: int
    # SL ATR bands
    sl_atr_min: float
    sl_atr_max: float
    # Position sizing
    position_size_mult: float
    # Hold time
    max_hold_hours: int
    # Behavior flags
    trust_levels: bool  # False for meme = levels are unreliable
    aggressive_entries: bool
    # Prompt additions
    prompt_rules: List[str]
    prompt_context: str
    # 🆕 Supervisor thresholds
    liq_proximity_warn_pct: float = 10.0  # Warn if price within X% of liquidation
    liq_proximity_critical_pct: float = 5.0  # Critical if within X%
    invalidation_threat_pct: float = 2.0  # Warn if within X% of invalidation
    advice_expiration_min: int = 30  # How long advice is valid
    default_cooldown_min: int = 15  # Cooldown after advice
    # 🆕 Funding rate thresholds (risk philosophy)
    funding_extreme: float = 0.001  # Threshold for "extreme" funding (0.1% default)
    # 🆕 Minimum TP1 RR threshold (reject scenarios below this)
    min_tp1_rr: float = 0.7  # Default minimum TP1 R:R


# =============================================================================
# MODE PRESETS
# =============================================================================

CONSERVATIVE_MODE = ModeConfig(
    mode_id="conservative",
    name="Conservative",
    emoji="🛡️",
    max_leverage=5,
    default_leverage=3,
    sl_atr_min=0.5,
    sl_atr_max=1.0,
    position_size_mult=1.0,
    max_hold_hours=168,  # 7 days
    trust_levels=True,
    aggressive_entries=False,
    prompt_rules=[
        "- Only enter on STRONG support/resistance levels",
        "- Require multiple confirmations (structure + momentum + volume)",
        "- Prefer counter-trend setups near key levels",
        "- Tight stops (0.5-1.0x ATR) to minimize risk",
        "- NO aggressive entries on breakouts",
        "- Higher confidence threshold: min 0.65",
    ],
    prompt_context="CONSERVATIVE: Wait for perfect setups. Quality over quantity.",
    # Supervisor: wider safety margins
    liq_proximity_warn_pct=15.0,
    liq_proximity_critical_pct=8.0,
    invalidation_threat_pct=1.5,
    advice_expiration_min=120,
    default_cooldown_min=60,
    # Risk philosophy: catch overheating early
    funding_extreme=0.0005,  # 0.05% - very sensitive
    # Conservative requires higher RR
    min_tp1_rr=0.8,
)

STANDARD_MODE = ModeConfig(
    mode_id="standard",
    name="Standard",
    emoji="⚖️",
    max_leverage=10,
    default_leverage=5,
    sl_atr_min=1.0,
    sl_atr_max=1.5,
    position_size_mult=1.0,
    max_hold_hours=120,  # 5 days
    trust_levels=True,
    aggressive_entries=False,
    prompt_rules=[
        "- Balance between risk and reward",
        "- Standard confirmation requirements",
        "- Both trend-following and counter-trend allowed",
        "- ATR-based stop placement (1.0-1.5x ATR)",
    ],
    prompt_context="STANDARD: Balanced approach. Trust levels, normal risk.",
    # Supervisor: default thresholds
    liq_proximity_warn_pct=10.0,
    liq_proximity_critical_pct=5.0,
    invalidation_threat_pct=2.0,
    advice_expiration_min=60,
    default_cooldown_min=30,
    # Risk philosophy: market default
    funding_extreme=0.001,  # 0.10% - standard threshold
)

HIGH_RISK_MODE = ModeConfig(
    mode_id="high_risk",
    name="High Risk",
    emoji="🔥",
    max_leverage=50,
    default_leverage=20,
    sl_atr_min=0.8,
    sl_atr_max=1.5,
    position_size_mult=1.0,
    max_hold_hours=48,
    trust_levels=True,
    aggressive_entries=True,
    prompt_rules=[
        "- TIGHT stops (0.8-1.5x ATR) to avoid liquidation cascade",
        "- Momentum-first entries preferred",
        "- Higher leverage requires stricter no-trade conditions",
        "- Invalidation must be VERY clear",
        "- Prefer volatile market conditions",
        "- Quick profit-taking recommended",
        "- If funding is extreme (>0.05%) - reduce leverage or skip",
    ],
    prompt_context=(
        "HIGH_RISK: Aggressive but disciplined. "
        "Tight stops are CRITICAL to prevent liquidation on high leverage. "
        "Better to get stopped out early than lose big."
    ),
    # Supervisor: tighter thresholds (high leverage = faster reactions)
    liq_proximity_warn_pct=8.0,
    liq_proximity_critical_pct=4.0,
    invalidation_threat_pct=1.0,
    advice_expiration_min=30,
    default_cooldown_min=15,
    # Risk philosophy: allows skew, expects impulse
    funding_extreme=0.002,  # 0.20% - less sensitive
    # High risk allows lower RR for momentum plays
    min_tp1_rr=0.6,
)

MEME_MODE = ModeConfig(
    mode_id="meme",
    name="Meme",
    emoji="🎰",
    max_leverage=20,
    default_leverage=10,
    sl_atr_min=2.0,
    sl_atr_max=5.0,
    position_size_mult=0.5,  # Reduced position size
    max_hold_hours=24,
    trust_levels=False,  # Levels are unreliable for memecoins
    aggressive_entries=True,
    prompt_rules=[
        "- Levels are UNRELIABLE for memecoins - treat as suggestions only",
        "- Use WIDE stops (2-5x ATR) as price often overshoots levels",
        "- Position size is automatically REDUCED by 50%",
        "- Momentum and hype matter more than technicals",
        "- Very short holding periods recommended (< 24h)",
        "- High funding rate = increased risk",
        "- Expect high volatility and wild swings",
        "- Don't trust support/resistance - they break easily",
    ],
    prompt_context=(
        "MEME MODE: Memecoins are unpredictable. "
        "Support/resistance levels WILL be broken. "
        "Wide stops are REQUIRED to avoid getting stopped out on noise. "
        "Position size is reduced. Fast trades only."
    ),
    # Supervisor: wider invalidation (volatile), but quick expiration
    liq_proximity_warn_pct=12.0,
    liq_proximity_critical_pct=6.0,
    invalidation_threat_pct=3.0,  # Wider due to volatility
    advice_expiration_min=20,
    default_cooldown_min=20,
    # Risk philosophy: memes often have 0.2-0.5% funding, that's normal
    funding_extreme=0.003,  # 0.30% - very tolerant
    # Meme allows lowest RR due to unpredictability
    min_tp1_rr=0.5,
)


# Mode registry
MODE_REGISTRY: Dict[str, ModeConfig] = {
    "conservative": CONSERVATIVE_MODE,
    "standard": STANDARD_MODE,
    "high_risk": HIGH_RISK_MODE,
    "meme": MEME_MODE,
}


def get_mode_config(mode_id: Optional[str]) -> ModeConfig:
    """Get mode config by ID, default to STANDARD."""
    if not mode_id:
        return STANDARD_MODE
    return MODE_REGISTRY.get(mode_id.lower(), STANDARD_MODE)


# =============================================================================
# MODE PROMPT BUILDER
# =============================================================================


def build_mode_profile_block(mode: ModeConfig) -> str:
    """
    Build MODE PROFILE block for LLM prompt injection.

    Returns:
        String block to insert into the scenario generation prompt
    """
    rules_text = "\n".join(mode.prompt_rules)

    profile = f"""
=== 🎯 MODE PROFILE: {mode.name} ({mode.emoji}) ===

TRADING PARAMETERS FOR THIS MODE:
- Mode: {mode.mode_id.upper()}
- Max Leverage: {mode.max_leverage}x
- Default Leverage: {mode.default_leverage}x
- SL Distance: {mode.sl_atr_min}x - {mode.sl_atr_max}x ATR
- Position Size Mult: {mode.position_size_mult}x
- Max Hold Time: {mode.max_hold_hours}h
- Trust Levels: {"YES" if mode.trust_levels else "NO (levels are unreliable!)"}
- Aggressive Entries: {"YES" if mode.aggressive_entries else "NO (wait for confirmation)"}

MODE-SPECIFIC RULES:
{rules_text}

{mode.prompt_context}

⚠️ IMPORTANT: Your scenarios MUST reflect these {mode.mode_id.upper()} mode parameters:
1. Leverage recommendations should not exceed {mode.max_leverage}x
2. Stop losses should be in {mode.sl_atr_min}x - {mode.sl_atr_max}x ATR range
3. {"DO NOT trust support/resistance levels blindly - they break easily in meme territory" if not mode.trust_levels else "Trust S/R levels normally"}
4. {"Prefer momentum/aggressive entries" if mode.aggressive_entries else "Wait for proper confirmations"}

You MUST include "mode_notes" array (2-4 items) in EACH scenario explaining how you applied {mode.mode_id.upper()} mode parameters.
===
"""
    return profile.strip()


def get_mode_notes_schema() -> dict:
    """
    Get JSON schema for mode_notes field.

    Returns:
        Schema dict for mode_notes
    """
    return {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 2,
        "maxItems": 4,
        "description": "Brief notes explaining how this scenario reflects the trading mode parameters"
    }
