"""
Level Quality Service — фильтрация и обогащение уровней ДО передачи в LLM.

Принцип: LLM не должен сам решать какие уровни "хорошие".
Мы передаём ТОЛЬКО качественные уровни с обязательными ID.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class QualityLevel:
    """Уровень с метаданными качества."""
    level_id: str
    price: float
    level_type: str  # "support" | "resistance"
    source: str  # "near" | "htf" | "swing" | "range" | "ema" | "vwap"
    strength: str  # "strong" | "moderate" | "weak"
    touches: int
    age_hours: int
    distance_atr: float
    quality_score: float
    has_invalidation_structure: bool = False
    tf: Optional[str] = None  # для HTF levels


@dataclass
class StructureAnchors:
    """Структурные якоря для сценариев."""
    swing_highs: List[Dict]  # последние 2-3 swing high
    swing_lows: List[Dict]  # последние 2-3 swing low
    range_high: Optional[float] = None
    range_low: Optional[float] = None
    is_in_range: bool = False


@dataclass
class PathBlockers:
    """Уровни, блокирующие путь к TP."""
    blockers: List[Dict]
    path_clear: bool


@dataclass
class EntrySqueeze:
    """Информация о сжатии entry."""
    entry_is_squeezed: bool
    nearest_opposing_distance_R: Optional[float]
    nearest_opposing_level_id: Optional[str] = None


@dataclass
class LevelCandidates:
    """Полный набор кандидатов уровней для LLM."""
    support_near: List[Dict]
    resistance_near: List[Dict]
    swing_highs: List[Dict]
    swing_lows: List[Dict]
    htf_levels: List[Dict]
    range_high: Optional[float]
    range_low: Optional[float]
    ema_20: Optional[float]
    ema_50: Optional[float]
    ema_200: Optional[float]
    vwap: Optional[float]
    # Pre-calculated для каждого bias
    path_blockers_long: List[Dict] = field(default_factory=list)
    path_blockers_short: List[Dict] = field(default_factory=list)
    entry_squeeze_long: Dict = field(default_factory=dict)
    entry_squeeze_short: Dict = field(default_factory=dict)


class LevelQualityService:
    """
    Сервис для фильтрации и обогащения уровней.

    Ответственность:
    1. Фильтрация по качеству (age, touches, distance)
    2. Добавление level_id к каждому уровню
    3. Расчёт quality_score и strength
    4. Извлечение structure anchors (swings, range)
    5. Расчёт path_blockers и entry_squeeze
    """

    # Константы фильтрации
    MAX_AGE_HOURS = 72
    MIN_TOUCHES = 2
    MAX_DISTANCE_ATR = 2.0

    # Веса для quality_score
    WEIGHTS = {
        "touches": 0.3,
        "freshness": 0.3,
        "distance": 0.2,
        "has_structure": 0.2,
    }

    def filter_quality_levels(
        self,
        levels: List[float],
        levels_meta: List[Dict],
        current_price: float,
        atr: float,
        level_type: str,  # "support" | "resistance"
        source: str = "near",
    ) -> List[Dict]:
        """
        Отфильтровать уровни по качеству.

        Args:
            levels: Список цен уровней
            levels_meta: Метаданные от MarketDataEnricher
            current_price: Текущая цена
            atr: ATR для расчёта distance
            level_type: "support" или "resistance"
            source: Источник уровней

        Returns:
            Список качественных уровней с level_id
        """
        if not levels or atr <= 0:
            return []

        filtered = []

        for i, level_price in enumerate(levels):
            if not level_price or level_price <= 0:
                continue

            # Получаем метаданные
            meta = {}
            if i < len(levels_meta):
                meta = levels_meta[i] if isinstance(levels_meta[i], dict) else {}

            touches = meta.get("touches", 1)
            age_hours = meta.get("age_hours", 999)

            # Distance gate
            distance_atr = abs(level_price - current_price) / atr
            if distance_atr > self.MAX_DISTANCE_ATR:
                continue

            # Quality filters
            if age_hours > self.MAX_AGE_HOURS:
                continue
            if touches < self.MIN_TOUCHES:
                continue

            # Strength classification
            strength = self._classify_strength(touches, age_hours)
            if strength == "weak":
                continue

            # Quality score
            quality_score = self._calculate_quality_score(
                touches=touches,
                age_hours=age_hours,
                distance_atr=distance_atr,
            )

            # Level ID
            level_id = f"{level_type}_{source}_{i}"

            filtered.append({
                "level_id": level_id,
                "price": round(level_price, 2),
                "level_type": level_type,
                "source": source,
                "strength": strength,
                "touches": touches,
                "age_hours": age_hours,
                "distance_atr": round(distance_atr, 2),
                "quality_score": round(quality_score, 2),
            })

        # Сортируем по proximity к текущей цене
        filtered.sort(key=lambda x: x["distance_atr"])

        return filtered[:5]  # Максимум 5 уровней

    def _classify_strength(self, touches: int, age_hours: int) -> str:
        """Классифицировать силу уровня."""
        if touches >= 4 and age_hours <= 24:
            return "strong"
        elif touches >= 2 and age_hours <= 48:
            return "moderate"
        else:
            return "weak"

    def _calculate_quality_score(
        self,
        touches: int,
        age_hours: int,
        distance_atr: float,
    ) -> float:
        """Рассчитать quality score (0-1)."""
        # Touches component (более = лучше)
        touches_score = min(touches / 6, 1.0)

        # Freshness component (меньше age = лучше)
        freshness_score = max(0, 1 - (age_hours / self.MAX_AGE_HOURS))

        # Distance component (ближе = лучше)
        distance_score = max(0, 1 - (distance_atr / self.MAX_DISTANCE_ATR))

        return (
            self.WEIGHTS["touches"] * touches_score +
            self.WEIGHTS["freshness"] * freshness_score +
            self.WEIGHTS["distance"] * distance_score
        )

    def extract_structure_anchors(
        self,
        klines: pd.DataFrame,
        current_price: float,
        atr: float,
    ) -> StructureAnchors:
        """
        Извлечь структурные якоря из OHLC данных.

        Returns:
            StructureAnchors с swing high/low и range boundaries
        """
        if klines is None or len(klines) < 20:
            return StructureAnchors(swing_highs=[], swing_lows=[])

        # Swing detection (простой алгоритм)
        swing_highs = []
        swing_lows = []

        lookback = min(50, len(klines))
        data = klines.iloc[-lookback:]

        for i in range(2, len(data) - 2):
            high = data.iloc[i]["high"]
            low = data.iloc[i]["low"]

            # Swing High: выше 2 свечей слева и справа
            if (high > data.iloc[i-1]["high"] and
                high > data.iloc[i-2]["high"] and
                high > data.iloc[i+1]["high"] and
                high > data.iloc[i+2]["high"]):
                age_candles = len(data) - 1 - i
                swing_highs.append({
                    "level_id": f"swing_high_{len(swing_highs)}",
                    "price": round(high, 2),
                    "age_candles": age_candles,
                })

            # Swing Low: ниже 2 свечей слева и справа
            if (low < data.iloc[i-1]["low"] and
                low < data.iloc[i-2]["low"] and
                low < data.iloc[i+1]["low"] and
                low < data.iloc[i+2]["low"]):
                age_candles = len(data) - 1 - i
                swing_lows.append({
                    "level_id": f"swing_low_{len(swing_lows)}",
                    "price": round(low, 2),
                    "age_candles": age_candles,
                })

        # Берём последние 3 swing high/low, ближайшие к текущей цене
        swing_highs = sorted(
            swing_highs,
            key=lambda x: (x["age_candles"], abs(x["price"] - current_price))
        )[:3]
        swing_lows = sorted(
            swing_lows,
            key=lambda x: (x["age_candles"], abs(x["price"] - current_price))
        )[:3]

        # Range detection
        range_high, range_low, is_in_range = self._detect_range(
            klines=klines,
            current_price=current_price,
            atr=atr,
        )

        return StructureAnchors(
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            range_high=range_high,
            range_low=range_low,
            is_in_range=is_in_range,
        )

    def _detect_range(
        self,
        klines: pd.DataFrame,
        current_price: float,
        atr: float,
        lookback: int = 30,
    ) -> tuple:
        """
        Определить рейндж (если есть).

        Returns:
            (range_high, range_low, is_in_range)
        """
        if len(klines) < lookback:
            return None, None, False

        data = klines.iloc[-lookback:]
        high = data["high"].max()
        low = data["low"].min()

        # Range width в ATR
        range_width_atr = (high - low) / atr if atr > 0 else 999

        # Считаем рейнджем если width < 4 ATR и цена внутри
        is_in_range = (
            range_width_atr < 4.0 and
            low < current_price < high
        )

        if is_in_range:
            return round(high, 2), round(low, 2), True
        return None, None, False

    def calculate_path_blockers(
        self,
        entry: float,
        tp1: float,
        all_levels: List[Dict],
        bias: str,
    ) -> PathBlockers:
        """
        Найти уровни между entry и TP1.

        Args:
            entry: Цена входа
            tp1: Первый тейк-профит
            all_levels: Все уровни (support_near + resistance_near + htf)
            bias: "long" или "short"

        Returns:
            PathBlockers с blockers и path_clear
        """
        blockers = []

        for level in all_levels:
            price = level.get("price", 0)
            strength = level.get("strength", "weak")
            # HTF levels считаем strong по дефолту
            if level.get("source") == "htf" or level.get("tf"):
                strength = "strong"

            # Для long: ищем сопротивления между entry и tp1
            if bias == "long":
                if level.get("level_type") != "resistance":
                    continue
                if not (entry < price < tp1):
                    continue
            # Для short: ищем поддержки между entry и tp1
            else:
                if level.get("level_type") != "support":
                    continue
                if not (tp1 < price < entry):
                    continue

            # Только strong/moderate блокируют
            if strength not in ["strong", "moderate"]:
                continue

            blockers.append({
                "level_id": level.get("level_id", f"unknown_{price}"),
                "price": price,
                "strength": strength,
                "source": level.get("source", "unknown"),
            })

        # Сортируем по proximity к entry
        blockers.sort(key=lambda x: abs(x["price"] - entry))

        return PathBlockers(
            blockers=blockers,
            path_clear=len(blockers) == 0,
        )

    def calculate_entry_squeeze(
        self,
        entry: float,
        R: float,
        all_levels: List[Dict],
        bias: str,
    ) -> EntrySqueeze:
        """
        Проверить: есть ли сильный opposing level близко к entry?

        Args:
            entry: Цена входа
            R: Risk (|entry - stop|)
            all_levels: Все уровни
            bias: "long" или "short"

        Returns:
            EntrySqueeze с информацией о сжатии
        """
        if R <= 0:
            return EntrySqueeze(entry_is_squeezed=False, nearest_opposing_distance_R=None)

        # Для long: ищем сопротивление сверху
        # Для short: ищем поддержку снизу
        opposing = []

        for level in all_levels:
            price = level.get("price", 0)
            strength = level.get("strength", "weak")

            if bias == "long":
                if level.get("level_type") != "resistance":
                    continue
                if price <= entry:
                    continue
            else:
                if level.get("level_type") != "support":
                    continue
                if price >= entry:
                    continue

            # Только strong levels сжимают
            if strength != "strong" and level.get("source") != "htf":
                continue

            opposing.append(level)

        if not opposing:
            return EntrySqueeze(entry_is_squeezed=False, nearest_opposing_distance_R=None)

        # Ближайший opposing level
        nearest = min(opposing, key=lambda x: abs(x["price"] - entry))
        distance_R = abs(nearest["price"] - entry) / R

        return EntrySqueeze(
            entry_is_squeezed=distance_R < 0.6,
            nearest_opposing_distance_R=round(distance_R, 2),
            nearest_opposing_level_id=nearest.get("level_id"),
        )

    def build_level_candidates(
        self,
        support_near: List[float],
        resistance_near: List[float],
        support_meta: List[Dict],
        resistance_meta: List[Dict],
        htf_levels: List[Dict],
        current_price: float,
        atr: float,
        klines: Optional[pd.DataFrame] = None,
        ema_20: Optional[float] = None,
        ema_50: Optional[float] = None,
        ema_200: Optional[float] = None,
        vwap: Optional[float] = None,
    ) -> LevelCandidates:
        """
        Построить полный набор кандидатов уровней для LLM.

        Returns:
            LevelCandidates со всеми отфильтрованными уровнями
        """
        # 1. Filter quality levels
        filtered_support = self.filter_quality_levels(
            levels=support_near,
            levels_meta=support_meta,
            current_price=current_price,
            atr=atr,
            level_type="support",
            source="near",
        )

        filtered_resistance = self.filter_quality_levels(
            levels=resistance_near,
            levels_meta=resistance_meta,
            current_price=current_price,
            atr=atr,
            level_type="resistance",
            source="near",
        )

        # 2. Extract structure anchors (if klines available)
        if klines is not None and len(klines) >= 20:
            anchors = self.extract_structure_anchors(
                klines=klines,
                current_price=current_price,
                atr=atr,
            )
        else:
            anchors = StructureAnchors(swing_highs=[], swing_lows=[])

        # 3. Process HTF levels (добавляем level_id и strength=strong)
        processed_htf = []
        for i, htf in enumerate(htf_levels[:4]):  # максимум 4 HTF
            processed_htf.append({
                "level_id": f"htf_{htf.get('tf', '1D')}_{i}",
                "price": htf.get("price"),
                "level_type": htf.get("type", "resistance"),
                "source": "htf",
                "strength": "strong",  # HTF = strong по дефолту
                "tf": htf.get("tf"),
            })

        return LevelCandidates(
            support_near=filtered_support,
            resistance_near=filtered_resistance,
            swing_highs=anchors.swing_highs,
            swing_lows=anchors.swing_lows,
            htf_levels=processed_htf,
            range_high=anchors.range_high,
            range_low=anchors.range_low,
            ema_20=round(ema_20, 2) if ema_20 else None,
            ema_50=round(ema_50, 2) if ema_50 else None,
            ema_200=round(ema_200, 2) if ema_200 else None,
            vwap=round(vwap, 2) if vwap else None,
        )


# Singleton instance
level_quality_service = LevelQualityService()
