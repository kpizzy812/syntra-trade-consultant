"""
Class Key

Идентификатор класса сценария для backtesting.
Включает SHA1 hash для быстрого lookup в БД.
"""
import hashlib
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from src.learning.constants import ANY_BUCKET
from src.learning.bucketizer import get_all_buckets


@dataclass
class ClassKey:
    """
    Ключ класса сценария.

    Класс = archetype + side + timeframe + [trend + vol + funding + sentiment] + [mode]

    Levels (3-tier fallback):
    - Level 3 (finest): все buckets + mode (most specific)
    - Level 2 (fine): все buckets + mode_family (fallback by mode family)
    - Level 1 (coarse): все buckets, без mode (backward compatible)

    Mode families:
    - "cautious": conservative
    - "balanced": standard
    - "speculative": high_risk, meme
    """
    archetype: str
    side: str
    timeframe: str
    trend_bucket: str = field(default=ANY_BUCKET)
    vol_bucket: str = field(default=ANY_BUCKET)
    funding_bucket: str = field(default=ANY_BUCKET)
    sentiment_bucket: str = field(default=ANY_BUCKET)
    # Trading mode dimension
    mode: str = field(default=ANY_BUCKET)  # "conservative", "standard", "high_risk", "meme" or "__any__"
    mode_family: str = field(default=ANY_BUCKET)  # "cautious", "balanced", "speculative" or "__any__"

    def __post_init__(self):
        """Нормализация значений."""
        self.archetype = self.archetype.upper()
        self.side = self.side.lower()
        self.timeframe = self.timeframe.lower()
        self.trend_bucket = self.trend_bucket.lower()
        self.vol_bucket = self.vol_bucket.lower()
        self.funding_bucket = self.funding_bucket.lower()
        self.sentiment_bucket = self.sentiment_bucket.lower()
        self.mode = self.mode.lower()
        self.mode_family = self.mode_family.lower()

    @property
    def level(self) -> int:
        """
        Уровень ключа (3-tier fallback).

        Returns:
            3 = finest (buckets + mode) - most specific
            2 = fine (buckets + mode_family) - fallback by family
            1 = coarse (buckets only, no mode) - backward compatible
        """
        has_mode = self.mode != ANY_BUCKET
        has_mode_family = self.mode_family != ANY_BUCKET

        if has_mode:
            return 3  # Most specific: with exact mode
        elif has_mode_family:
            return 2  # Fallback: with mode family
        else:
            return 1  # Coarse: no mode info (backward compatible)

    @property
    def key_string(self) -> str:
        """
        Canonical string representation.

        Format: ARCHETYPE|SIDE|TF|TREND|VOL|FUND|SENT|MODE|MODE_FAMILY
        Example: PULLBACK_TO_EMA50|LONG|4H|BULLISH|NORMAL|NEGATIVE|NEUTRAL|HIGH_RISK|SPECULATIVE
        """
        parts = [
            self.archetype.upper(),
            self.side.upper(),
            self.timeframe.upper(),
            self.trend_bucket.upper(),
            self.vol_bucket.upper(),
            self.funding_bucket.upper(),
            self.sentiment_bucket.upper(),
            self.mode.upper(),
            self.mode_family.upper(),
        ]
        return "|".join(parts)

    @property
    def key_hash(self) -> str:
        """
        SHA1 hash для быстрого lookup в БД.

        Returns:
            40-character hex string
        """
        return hashlib.sha1(self.key_string.encode()).hexdigest()

    def to_l1_key(self) -> "ClassKey":
        """
        Конвертировать в Level 1 (coarse) ключ.

        Убирает mode и mode_family (backward compatible).
        Сохраняет buckets как есть.
        """
        return ClassKey(
            archetype=self.archetype,
            side=self.side,
            timeframe=self.timeframe,
            trend_bucket=self.trend_bucket,
            vol_bucket=self.vol_bucket,
            funding_bucket=self.funding_bucket,
            sentiment_bucket=self.sentiment_bucket,
            mode=ANY_BUCKET,
            mode_family=ANY_BUCKET,
        )

    def to_l2_key(self) -> "ClassKey":
        """
        Конвертировать в Level 2 (fine) ключ.

        Использует mode_family вместо конкретного mode.
        """
        return ClassKey(
            archetype=self.archetype,
            side=self.side,
            timeframe=self.timeframe,
            trend_bucket=self.trend_bucket,
            vol_bucket=self.vol_bucket,
            funding_bucket=self.funding_bucket,
            sentiment_bucket=self.sentiment_bucket,
            mode=ANY_BUCKET,
            mode_family=self.mode_family,
        )

    def get_fallback_keys(self) -> list["ClassKey"]:
        """
        Получить иерархию fallback ключей: L3 → L2 → L1.

        Returns:
            Список ключей от самого специфичного к общему
        """
        keys = []

        # L3: с конкретным mode (если есть)
        if self.mode != ANY_BUCKET:
            keys.append(self)

        # L2: с mode_family (если есть)
        if self.mode_family != ANY_BUCKET:
            keys.append(self.to_l2_key())

        # L1: без mode (всегда)
        keys.append(self.to_l1_key())

        return keys

    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в dict для DB."""
        return {
            "archetype": self.archetype.upper(),
            "side": self.side.lower(),
            "timeframe": self.timeframe.lower(),
            "trend_bucket": self.trend_bucket.lower(),
            "vol_bucket": self.vol_bucket.lower(),
            "funding_bucket": self.funding_bucket.lower(),
            "sentiment_bucket": self.sentiment_bucket.lower(),
            "mode": self.mode.lower(),
            "mode_family": self.mode_family.lower(),
            "class_key_hash": self.key_hash,
            "class_key_string": self.key_string,
            "level": self.level,
        }

    def __hash__(self) -> int:
        """Hash для использования в sets/dicts."""
        return hash(self.key_string)

    def __eq__(self, other: object) -> bool:
        """Equality check."""
        if not isinstance(other, ClassKey):
            return False
        return self.key_string == other.key_string

    def __repr__(self) -> str:
        return f"<ClassKey L{self.level}: {self.key_string}>"


# Mode to mode_family mapping
MODE_FAMILIES = {
    "conservative": "cautious",
    "standard": "balanced",
    "high_risk": "speculative",
    "meme": "speculative",
}


def get_mode_family(mode: str) -> str:
    """Get mode family for a given mode."""
    return MODE_FAMILIES.get(mode.lower(), "balanced")


def build_class_key(
    archetype: str,
    side: str,
    timeframe: str,
    factors: Optional[Dict[str, Any]] = None,
    mode: Optional[str] = None,
    level: int = 3,
) -> ClassKey:
    """
    Создать ClassKey из параметров сценария.

    Args:
        archetype: Setup archetype name
        side: "long" or "short"
        timeframe: "1h", "4h", "1d", etc.
        factors: Market context factors
        mode: Trading mode (conservative, standard, high_risk, meme)
        level: 1 = no mode, 2 = mode_family, 3 = full mode

    Returns:
        ClassKey instance
    """
    # Извлекаем buckets из factors
    if factors:
        buckets = get_all_buckets(factors)
    else:
        buckets = {
            "trend_bucket": ANY_BUCKET,
            "vol_bucket": ANY_BUCKET,
            "funding_bucket": ANY_BUCKET,
            "sentiment_bucket": ANY_BUCKET,
        }

    # Определяем mode и mode_family
    mode_val = ANY_BUCKET
    mode_family_val = ANY_BUCKET

    if mode and level >= 2:
        mode_family_val = get_mode_family(mode)
        if level >= 3:
            mode_val = mode.lower()

    return ClassKey(
        archetype=archetype,
        side=side,
        timeframe=timeframe,
        trend_bucket=buckets["trend_bucket"],
        vol_bucket=buckets["vol_bucket"],
        funding_bucket=buckets["funding_bucket"],
        sentiment_bucket=buckets["sentiment_bucket"],
        mode=mode_val,
        mode_family=mode_family_val,
    )


def build_class_key_from_trade(
    archetype: str,
    side: str,
    timeframe: str,
    attribution_data: Optional[Dict[str, Any]] = None,
    mode: Optional[str] = None,
) -> ClassKey:
    """
    Создать ClassKey из данных TradeOutcome.

    Args:
        archetype: primary_archetype from TradeOutcome
        side: trade side
        timeframe: trade timeframe
        attribution_data: TradeOutcome.attribution_data
        mode: Trading mode (conservative, standard, high_risk, meme)

    Returns:
        ClassKey instance (L3 если есть mode, L2 если mode_family, L1 fallback)
    """
    factors = None
    if attribution_data:
        factors = attribution_data.get("factors", {})
        # Try to extract mode from attribution_data if not provided
        if not mode:
            mode = attribution_data.get("mode")

    return build_class_key(
        archetype=archetype,
        side=side,
        timeframe=timeframe,
        factors=factors,
        mode=mode,
        level=3,
    )
