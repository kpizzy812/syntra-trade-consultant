# coding: utf-8
"""
Константы и утилитарные функции для futures analysis.
"""
from typing import List


# ==============================================================================
# BIAS FACTOR CAPS
# ==============================================================================
# Max contribution per factor to prevent single-factor bias domination
BIAS_CAPS = {
    "trend": 3,        # max ±3 from trend
    "rsi": 2,          # max ±2 from RSI
    "fear_greed": 4,   # max ±4 from F&G (high weight on large TFs)
    "funding": 2,      # max ±2 from funding
    "ls_ratio": 2,     # max ±2 from long/short ratio
}


# ==============================================================================
# ENTRY DISTANCE LIMITS
# ==============================================================================
# Max distance from current price for entry zone (adaptive by timeframe)
MAX_ENTRY_DISTANCE_PCT_BY_TF = {
    "15m": 3.0,
    "1h": 5.0,
    "4h": 8.0,
    "1d": 15.0,
    "1w": 25.0,
}
MAX_ENTRY_DISTANCE_PCT_DEFAULT = 10.0  # fallback


# ==============================================================================
# ATR MULTIPLIERS
# ==============================================================================
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


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================
def filter_levels_by_distance(
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
