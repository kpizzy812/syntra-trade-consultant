# coding: utf-8
"""
Liquidation Analyzer - анализ ликвидаций и формирование clusters.
"""
import time
from collections import defaultdict
from typing import Any, Dict, Optional

from loguru import logger


class LiquidationAnalyzer:
    """
    Агрегирует liquidation data в clusters для LLM.
    """

    def aggregate_clusters(
        self,
        liquidation_data: Optional[Dict],
        current_price: float
    ) -> Dict[str, Any]:
        """
        Агрегировать liquidation data в clusters для LLM.

        Вместо сырых liquidation данных, даём LLM:
        - Clusters выше/ниже текущей цены
        - Spike detection (последние 1h vs среднее)
        - Net bias (long/short liquidations)

        Returns:
            {
                "clusters_above": [{price: 96000, intensity: "high", volume_usd: 5M}],
                "clusters_below": [{price: 93500, intensity: "medium", volume_usd: 2M}],
                "last_24h_liq_spike": True,
                "spike_magnitude": "large",
                "liq_pressure_bias": "long"
            }
        """
        if not liquidation_data or not liquidation_data.get("liquidations"):
            return {
                "clusters_above": [],
                "clusters_below": [],
                "last_24h_liq_spike": False,
                "spike_magnitude": "none",
                "liq_pressure_bias": "neutral"
            }

        liquidations = liquidation_data.get("liquidations", [])

        if not liquidations:
            return {
                "clusters_above": [],
                "clusters_below": [],
                "last_24h_liq_spike": False,
                "spike_magnitude": "none",
                "liq_pressure_bias": "neutral"
            }

        # Разделяем на longs/shorts
        # side="BUY" = Long liquidation (цена упала, long'и ликвидированы)
        # side="SELL" = Short liquidation (цена выросла, short'ы ликвидированы)
        long_liqs = [liq for liq in liquidations if liq.get("side") == "BUY"]
        short_liqs = [liq for liq in liquidations if liq.get("side") == "SELL"]

        # Агрегируем по ценовым зонам (bins по 0.5% для крупных монет)
        bin_size = current_price * 0.005  # 0.5% bins

        # Clusters выше текущей цены (short liquidations)
        all_short_clusters = self._aggregate_to_bins(short_liqs, bin_size)
        clusters_above = [c for c in all_short_clusters if c["price"] > current_price]

        # Clusters ниже текущей цены (long liquidations)
        all_long_clusters = self._aggregate_to_bins(long_liqs, bin_size)
        clusters_below = [c for c in all_long_clusters if c["price"] < current_price]

        # Spike detection и pressure calculation
        spike, spike_magnitude = self._detect_spike(liquidations)
        liq_pressure, long_liq_pct, short_liq_pct, total_volume = self._calculate_pressure(
            long_liqs, short_liqs
        )

        result = {
            "clusters_above": clusters_above[:3],  # Топ 3
            "clusters_below": clusters_below[:3],  # Топ 3
            "last_24h_liq_spike": spike,
            "spike_magnitude": spike_magnitude,
            "liq_pressure_bias": liq_pressure,
            "long_liq_pct": round(long_liq_pct, 1),
            "short_liq_pct": round(short_liq_pct, 1),
            "total_volume_usd": round(total_volume, 0)
        }

        logger.debug(f"Liquidation clusters: {result}")
        return result

    def _aggregate_to_bins(self, liqs: list, bin_size: float) -> list:
        """Агрегация ликвидаций в ценовые bins."""
        bins = defaultdict(lambda: {"volume": 0, "count": 0})

        for liq in liqs:
            price = liq.get("price", 0)
            quantity = liq.get("quantity", 0)

            if price <= 0:
                continue

            # USD value
            volume = quantity * price

            # round к ближайшему bin center для точной визуализации уровня
            bin_index = round(price / bin_size)
            bin_center = bin_index * bin_size
            bins[bin_center]["volume"] += volume
            bins[bin_center]["count"] += 1

        # Сортируем по volume
        sorted_bins = sorted(
            bins.items(),
            key=lambda x: x[1]["volume"],
            reverse=True
        )

        # Топ 5 clusters
        clusters = []
        for bin_center, data in sorted_bins[:5]:
            volume_usd = data["volume"]

            # Определяем intensity
            if volume_usd > 5000000:  # > $5M
                intensity = "very_high"
            elif volume_usd > 2000000:  # > $2M
                intensity = "high"
            elif volume_usd > 1000000:  # > $1M
                intensity = "medium"
            else:
                intensity = "low"

            clusters.append({
                "price": round(bin_center, 2),
                "intensity": intensity,
                "volume_usd": round(volume_usd, 0)
            })

        return clusters

    def _detect_spike(self, liquidations: list) -> tuple[bool, str]:
        """Обнаружить spike ликвидаций (последние 1h vs средний за 24h)."""
        now = time.time() * 1000
        one_hour_ago = now - (60 * 60 * 1000)

        recent_liqs = [liq for liq in liquidations if liq.get("time", 0) > one_hour_ago]

        # Считаем volume
        def calc_liq_volume(liqs):
            return sum([liq.get("quantity", 0) * liq.get("price", 0) for liq in liqs])

        recent_volume = calc_liq_volume(recent_liqs)
        total_volume = calc_liq_volume(liquidations)

        # Средний hourly volume (за 24h)
        hours_in_data = (now - min([liq.get("time", now) for liq in liquidations])) / (60 * 60 * 1000)
        # Минимум 1 час, чтобы избежать взрывных значений
        hours_in_data = max(hours_in_data, 1.0)
        avg_hourly_volume = total_volume / hours_in_data if hours_in_data > 0 else 0

        # Spike если recent > 3x average
        spike = recent_volume > avg_hourly_volume * 3

        # Magnitude
        if recent_volume > avg_hourly_volume * 5:
            spike_magnitude = "extreme"
        elif recent_volume > avg_hourly_volume * 3:
            spike_magnitude = "large"
        elif recent_volume > avg_hourly_volume * 2:
            spike_magnitude = "medium"
        else:
            spike_magnitude = "low"

        return spike, spike_magnitude

    def _calculate_pressure(
        self, long_liqs: list, short_liqs: list
    ) -> tuple[str, float, float, float]:
        """
        Рассчитать pressure bias.

        Returns:
            (liq_pressure, long_liq_pct, short_liq_pct, total_volume)
        """
        def calc_liq_volume(liqs):
            return sum([liq.get("quantity", 0) * liq.get("price", 0) for liq in liqs])

        long_liq_volume = calc_liq_volume(long_liqs)
        short_liq_volume = calc_liq_volume(short_liqs)
        total_liq_volume = long_liq_volume + short_liq_volume

        if total_liq_volume > 0:
            long_liq_pct = (long_liq_volume / total_liq_volume) * 100
            short_liq_pct = (short_liq_volume / total_liq_volume) * 100

            # Если много long liquidations = цена падала = bearish давление
            # Если много short liquidations = цена росла = bullish давление
            if long_liq_volume > short_liq_volume * 1.5:
                liq_pressure = "bearish"  # Много long'ов ликвидировано
            elif short_liq_volume > long_liq_volume * 1.5:
                liq_pressure = "bullish"  # Много short'ов ликвидировано
            else:
                liq_pressure = "neutral"
        else:
            long_liq_pct = 0
            short_liq_pct = 0
            liq_pressure = "neutral"

        return liq_pressure, long_liq_pct, short_liq_pct, total_liq_volume
