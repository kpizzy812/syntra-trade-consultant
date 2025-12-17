# coding: utf-8
"""
Trading Session Detector

Определяет текущую торговую сессию (Asia/London/NY) и характеристики волатильности
для каждой сессии.

ВАЖНО: Фьючерсы торгуются 24/7, но волатильность и ликвидность зависят от сессий!
"""
from typing import Dict, Any
from datetime import datetime, timezone
import pytz

from loguru import logger


class SessionDetector:
    """
    Детектор торговых сессий с timezone-aware анализом

    Sessions:
    - ASIA:   00:00-09:00 UTC (Tokyo, Hong Kong, Singapore)
    - LONDON: 08:00-17:00 UTC (London, Frankfurt)
    - NY:     13:00-22:00 UTC (New York)

    Overlap zones (highest volume):
    - London/Asia: 08:00-09:00 UTC
    - London/NY:   13:00-17:00 UTC (MOST LIQUID!)
    """

    # Session times (UTC)
    SESSIONS = {
        "asia": {
            "start": 0,   # 00:00 UTC
            "end": 9,     # 09:00 UTC
            "name": "Asia",
            "cities": ["Tokyo", "Hong Kong", "Singapore"],
            "volatility": "medium",
            "characteristics": [
                "Lower volume than London/NY",
                "Range-bound trading common",
                "Good for scalping"
            ]
        },
        "london": {
            "start": 8,   # 08:00 UTC
            "end": 17,    # 17:00 UTC
            "name": "London",
            "cities": ["London", "Frankfurt", "Zurich"],
            "volatility": "high",
            "characteristics": [
                "High volume and volatility",
                "Trend setups common",
                "EUR/GBP pairs most active"
            ]
        },
        "ny": {
            "start": 13,  # 13:00 UTC
            "end": 22,    # 22:00 UTC
            "name": "New York",
            "cities": ["New York", "Chicago"],
            "volatility": "high",
            "characteristics": [
                "Highest USD volume",
                "Major news releases (FOMC, NFP)",
                "Best liquidity 13:00-17:00 UTC (London overlap)"
            ]
        }
    }

    def __init__(self):
        logger.info("SessionDetector initialized")

    def get_current_session(self, timestamp: datetime = None) -> Dict[str, Any]:
        """
        Определить текущую торговую сессию

        Args:
            timestamp: Timestamp (UTC), если None - используется текущее время

        Returns:
            {
                "current_session": "london" | "ny" | "asia",
                "session_name": "London",
                "hour_utc": 14,
                "is_overlap": true,
                "overlap_sessions": ["london", "ny"],
                "volatility_expected": "very_high",
                "characteristics": [...],
                "next_session": {
                    "name": "New York",
                    "starts_in_hours": 2
                }
            }
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Get hour UTC
        hour_utc = timestamp.hour

        # Find active sessions
        active_sessions = []
        for session_key, session_info in self.SESSIONS.items():
            start = session_info["start"]
            end = session_info["end"]

            # Check if current hour is in session range
            if start <= hour_utc < end:
                active_sessions.append(session_key)

        # Determine primary session
        if not active_sessions:
            # Dead zone (22:00-00:00 UTC) - считаем как Asia
            primary_session = "asia"
        elif len(active_sessions) == 1:
            primary_session = active_sessions[0]
        else:
            # Overlap - выбираем по приоритету (NY > London > Asia)
            if "ny" in active_sessions:
                primary_session = "ny"
            elif "london" in active_sessions:
                primary_session = "london"
            else:
                primary_session = "asia"

        session_info = self.SESSIONS[primary_session]

        # Determine volatility
        is_overlap = len(active_sessions) > 1
        if is_overlap:
            volatility = "very_high"  # Overlap = highest volatility
        else:
            volatility = session_info["volatility"]

        # Next session
        next_session_info = self._get_next_session(hour_utc)

        result = {
            "current_session": primary_session,
            "session_name": session_info["name"],
            "hour_utc": hour_utc,
            "is_overlap": is_overlap,
            "overlap_sessions": active_sessions if is_overlap else None,
            "volatility_expected": volatility,
            "characteristics": session_info["characteristics"],
            "cities": session_info["cities"],
            "next_session": next_session_info
        }

        return result

    def _get_next_session(self, current_hour: int) -> Dict[str, Any]:
        """Get info about next session"""

        # Determine next session based on current hour
        if current_hour < 8:
            # Before London -> London next
            next_session = "london"
            hours_until = 8 - current_hour
        elif current_hour < 13:
            # Before NY -> NY next
            next_session = "ny"
            hours_until = 13 - current_hour
        elif current_hour < 22:
            # Before Asia -> Asia next (at midnight)
            next_session = "asia"
            hours_until = 24 - current_hour
        else:
            # Late NY -> Asia soon
            next_session = "asia"
            hours_until = 24 - current_hour

        return {
            "name": self.SESSIONS[next_session]["name"],
            "starts_in_hours": hours_until
        }

    def get_session_recommendation(self, session_data: Dict[str, Any]) -> str:
        """
        Получить рекомендацию по торговле для текущей сессии

        Args:
            session_data: Output from get_current_session()

        Returns:
            Trading recommendation string
        """
        session = session_data["current_session"]
        is_overlap = session_data["is_overlap"]

        if is_overlap:
            overlap = session_data["overlap_sessions"]
            if "london" in overlap and "ny" in overlap:
                return (
                    "🔥 LONDON/NY OVERLAP (13:00-17:00 UTC) - BEST TIME TO TRADE!\n"
                    "• Highest liquidity and volume\n"
                    "• Clear trends and breakouts\n"
                    "• Tight spreads, fast execution\n"
                    "• Recommended: Breakout strategies, trend following"
                )
            elif "london" in overlap and "asia" in overlap:
                return (
                    "⚡ LONDON/ASIA OVERLAP (08:00-09:00 UTC)\n"
                    "• Moderate volume increase\n"
                    "• Tokyo close + London open\n"
                    "• Watch for direction change"
                )

        elif session == "london":
            return (
                "🇬🇧 LONDON SESSION (08:00-17:00 UTC)\n"
                "• High volatility, good trends\n"
                "• EUR, GBP pairs most active\n"
                "• Recommended: Trend trading, breakouts"
            )

        elif session == "ny":
            return (
                "🇺🇸 NEW YORK SESSION (13:00-22:00 UTC)\n"
                "• High USD volume\n"
                "• Major news releases (FOMC, NFP, etc.)\n"
                "• Recommended: News trading, trend continuation"
            )

        else:  # asia
            return (
                "🌏 ASIA SESSION (00:00-09:00 UTC)\n"
                "• Lower volume, range-bound\n"
                "• Good for: Scalping, mean reversion\n"
                "• Avoid: Large positions, breakout trades"
            )


# Singleton instance
session_detector = SessionDetector()
