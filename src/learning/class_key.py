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

    Класс = archetype + side + timeframe + [trend + vol + funding + sentiment]

    Levels:
    - Level 1 (coarse): archetype + side + timeframe (все buckets = '__any__')
    - Level 2 (fine): + конкретные bucket values
    """
    archetype: str
    side: str
    timeframe: str
    trend_bucket: str = field(default=ANY_BUCKET)
    vol_bucket: str = field(default=ANY_BUCKET)
    funding_bucket: str = field(default=ANY_BUCKET)
    sentiment_bucket: str = field(default=ANY_BUCKET)

    def __post_init__(self):
        """Нормализация значений."""
        self.archetype = self.archetype.upper()
        self.side = self.side.lower()
        self.timeframe = self.timeframe.lower()
        self.trend_bucket = self.trend_bucket.lower()
        self.vol_bucket = self.vol_bucket.lower()
        self.funding_bucket = self.funding_bucket.lower()
        self.sentiment_bucket = self.sentiment_bucket.lower()

    @property
    def level(self) -> int:
        """
        Уровень ключа.

        Returns:
            1 = coarse (все buckets = __any__)
            2 = fine (хотя бы один bucket != __any__)
        """
        if all(
            b == ANY_BUCKET for b in [
                self.trend_bucket, self.vol_bucket,
                self.funding_bucket, self.sentiment_bucket
            ]
        ):
            return 1
        return 2

    @property
    def key_string(self) -> str:
        """
        Canonical string representation.

        Format: ARCHETYPE|SIDE|TF|TREND|VOL|FUND|SENT
        Example: PULLBACK_TO_EMA50|LONG|4H|BULLISH|NORMAL|NEGATIVE|NEUTRAL
        """
        parts = [
            self.archetype.upper(),
            self.side.upper(),
            self.timeframe.upper(),
            self.trend_bucket.upper(),
            self.vol_bucket.upper(),
            self.funding_bucket.upper(),
            self.sentiment_bucket.upper(),
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

        Все bucket dimensions становятся '__any__'.
        """
        return ClassKey(
            archetype=self.archetype,
            side=self.side,
            timeframe=self.timeframe,
            trend_bucket=ANY_BUCKET,
            vol_bucket=ANY_BUCKET,
            funding_bucket=ANY_BUCKET,
            sentiment_bucket=ANY_BUCKET,
        )

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
            "class_key_hash": self.key_hash,
            "class_key_string": self.key_string,
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


def build_class_key(
    archetype: str,
    side: str,
    timeframe: str,
    factors: Optional[Dict[str, Any]] = None,
    level: int = 2,
) -> ClassKey:
    """
    Создать ClassKey из параметров сценария.

    Args:
        archetype: Setup archetype name
        side: "long" or "short"
        timeframe: "1h", "4h", "1d", etc.
        factors: Market context factors (для L2)
        level: 1 = coarse (ignore factors), 2 = fine (use factors)

    Returns:
        ClassKey instance
    """
    if level == 1 or not factors:
        return ClassKey(
            archetype=archetype,
            side=side,
            timeframe=timeframe,
        )

    # Level 2: извлекаем buckets из factors
    buckets = get_all_buckets(factors)

    return ClassKey(
        archetype=archetype,
        side=side,
        timeframe=timeframe,
        trend_bucket=buckets["trend_bucket"],
        vol_bucket=buckets["vol_bucket"],
        funding_bucket=buckets["funding_bucket"],
        sentiment_bucket=buckets["sentiment_bucket"],
    )


def build_class_key_from_trade(
    archetype: str,
    side: str,
    timeframe: str,
    attribution_data: Optional[Dict[str, Any]] = None,
) -> ClassKey:
    """
    Создать ClassKey из данных TradeOutcome.

    Args:
        archetype: primary_archetype from TradeOutcome
        side: trade side
        timeframe: trade timeframe
        attribution_data: TradeOutcome.attribution_data

    Returns:
        ClassKey instance (L2 если есть factors, иначе L1)
    """
    factors = None
    if attribution_data:
        factors = attribution_data.get("factors", {})

    if not factors:
        return ClassKey(
            archetype=archetype,
            side=side,
            timeframe=timeframe,
        )

    return build_class_key(
        archetype=archetype,
        side=side,
        timeframe=timeframe,
        factors=factors,
        level=2,
    )
