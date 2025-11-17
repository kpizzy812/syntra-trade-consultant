# coding: utf-8
"""
Analytics Aggregator Service

Собирает ВСЮ доступную аналитику по криптовалюте:
- Текущая цена и изменения (CoinGecko)
- Funding rates (Binance Futures)
- Rainbow Chart / Cycle analysis (только для BTC)
- On-chain метрики (CoinMetrics)
- Технические индикаторы (если есть исторические данные)

Используется для обогащения AI-промптов полным контекстом.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from src.services.coingecko_service import CoinGeckoService
from src.services.binance_service import BinanceService
from src.services.cycle_analysis_service import CycleAnalysisService
from src.services.coinmetrics_service import CoinMetricsService
from src.services.fear_greed_service import FearGreedService

logger = logging.getLogger(__name__)


class AnalyticsAggregator:
    """
    Агрегатор всей доступной аналитики по криптовалюте

    Собирает данные из:
    - CoinGecko (цена, изменения, market cap)
    - Binance (funding rates, open interest)
    - CoinMetrics (on-chain метрики)
    - Cycle Analysis (Rainbow Chart для BTC)
    - Fear & Greed Index
    """

    def __init__(self):
        self.coingecko = CoinGeckoService()
        self.binance = BinanceService()
        self.cycle_service = CycleAnalysisService()
        self.coinmetrics = CoinMetricsService()
        self.fear_greed = FearGreedService()

    async def get_full_analytics(self, coin_id: str) -> Dict[str, Any]:
        """
        Собрать ВСЮ доступную аналитику по монете

        Args:
            coin_id: CoinGecko coin ID (bitcoin, ethereum, xrp, etc.)

        Returns:
            Dict со всеми метриками

        Example output:
        {
            "coin_id": "bitcoin",
            "price_data": {...},
            "funding_data": {...},
            "cycle_data": {...},  # только для BTC
            "onchain_data": {...},
            "fear_greed": {...},
            "summary": "текстовое описание для AI"
        }
        """
        logger.info(f"Aggregating analytics for {coin_id}")

        result = {
            "coin_id": coin_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # 1. Базовая рыночная информация (CoinGecko)
        try:
            price_data = await self.coingecko.get_price(coin_id)
            if price_data:
                result["price_data"] = {
                    "current_price": price_data.get("current_price"),
                    "price_change_24h": price_data.get("price_change_24h"),
                    "price_change_percentage_24h": price_data.get(
                        "price_change_percentage_24h"
                    ),
                    "market_cap": price_data.get("market_cap"),
                    "total_volume": price_data.get("total_volume"),
                    "high_24h": price_data.get("high_24h"),
                    "low_24h": price_data.get("low_24h"),
                }
                logger.info(f"Price data fetched for {coin_id}")
        except Exception as e:
            logger.warning(f"Failed to fetch price data for {coin_id}: {e}")
            result["price_data"] = None

        # 2. Funding Rates (Binance Futures) - индикатор sentiment трейдеров
        try:
            symbol = self.binance.get_symbol(coin_id)
            if symbol:
                funding = await self.binance.get_latest_funding_rate(symbol)
                if funding:
                    result["funding_data"] = {
                        "funding_rate_pct": funding["funding_rate_pct"],
                        "sentiment": funding["sentiment"],
                        "interpretation": self._interpret_funding(
                            funding["funding_rate"]
                        ),
                    }
                    logger.info(f"Funding data fetched for {coin_id}")

                    # Open Interest
                    oi = await self.binance.get_open_interest(symbol)
                    if oi:
                        result["funding_data"]["open_interest"] = oi[
                            "open_interest"
                        ]
        except Exception as e:
            logger.warning(f"Failed to fetch funding data for {coin_id}: {e}")
            result["funding_data"] = None

        # 3. Rainbow Chart / Cycle Analysis (только для Bitcoin)
        if coin_id.lower() == "bitcoin":
            try:
                if result.get("price_data") and result["price_data"]["current_price"]:
                    current_price = result["price_data"]["current_price"]
                    rainbow_data = self.cycle_service.get_rainbow_chart_data(
                        current_price
                    )

                    result["cycle_data"] = {
                        "current_band": rainbow_data["current_band"],
                        "sentiment": rainbow_data["sentiment"],
                        "days_since_genesis": rainbow_data["days_since_genesis"],
                        "interpretation": self._interpret_rainbow(
                            rainbow_data["current_band"], rainbow_data["sentiment"]
                        ),
                    }
                    logger.info(f"Cycle data calculated for Bitcoin")
            except Exception as e:
                logger.warning(f"Failed to calculate cycle data for Bitcoin: {e}")
                result["cycle_data"] = None

        # 4. On-Chain метрики (CoinMetrics)
        try:
            # Network health
            health = await self.coinmetrics.get_network_health(coin_id)
            if health:
                result["onchain_data"] = {
                    "active_addresses": health.get("active_addresses"),
                    "transaction_count": health.get("transaction_count"),
                    "interpretation": self._interpret_network_health(health),
                }

                # Exchange flows
                flows = await self.coinmetrics.get_exchange_flows(coin_id)
                if flows:
                    result["onchain_data"]["exchange_flows"] = {
                        "net_flow": flows["net_flow"],
                        "sentiment": flows["sentiment"],
                        "interpretation": self._interpret_exchange_flows(flows),
                    }

                logger.info(f"On-chain data fetched for {coin_id}")
        except Exception as e:
            logger.warning(f"Failed to fetch on-chain data for {coin_id}: {e}")
            result["onchain_data"] = None

        # 5. Fear & Greed Index (общий sentiment рынка)
        try:
            fg_data = await self.fear_greed.get_fear_greed_index()
            if fg_data:
                result["fear_greed"] = {
                    "value": fg_data.get("value"),
                    "classification": fg_data.get("value_classification"),
                }
                logger.info("Fear & Greed Index fetched")
        except Exception as e:
            logger.warning(f"Failed to fetch Fear & Greed Index: {e}")
            result["fear_greed"] = None

        # 6. Создать summary для AI
        result["summary"] = self._generate_summary(result)

        return result

    def _interpret_funding(self, rate: float) -> str:
        """Интерпретация funding rate"""
        if rate > 0.001:  # > 0.1%
            return "Очень высокий funding rate - возможен перегрев лонгов, риск коррекции"
        elif rate > 0.0005:  # > 0.05%
            return "Повышенный funding rate - сильный bullish sentiment"
        elif rate > 0:
            return "Положительный funding rate - умеренный bullish sentiment"
        elif rate < -0.001:
            return "Очень низкий funding rate - возможен перегрев шортов"
        elif rate < -0.0005:
            return "Отрицательный funding rate - сильный bearish sentiment"
        else:
            return "Близкий к нулю funding rate - нейтральный sentiment"

    def _interpret_rainbow(self, band: str, sentiment: str) -> str:
        """Интерпретация Rainbow Chart"""
        interpretations = {
            "buy": "ОТЛИЧНАЯ цена для покупки - исторически низкий уровень",
            "basically_a_fire_sale": "ЭКСТРЕМАЛЬНО выгодная цена - распродажа",
            "accumulate": "Хорошая зона для накопления",
            "hodl": "Справедливая цена - hold позиции",
            "still_cheap": "Всё ещё недооценён относительно цикла",
            "is_this_a_bubble": "Начинается перегрев - осторожно",
            "fomo_intensifies": "Сильный FOMO - риск вершины близко",
            "sell": "ЗОНА ПРОДАЖ - исторически высокий уровень",
            "maximum_bubble": "МАКСИМАЛЬНЫЙ ПУЗЫРЬ - критическая зона",
        }
        return interpretations.get(band, "Анализ Rainbow Chart недоступен")

    def _interpret_network_health(self, health: Dict[str, Any]) -> str:
        """Интерпретация on-chain метрик"""
        active_addr = health.get("active_addresses", 0)
        tx_count = health.get("transaction_count", 0)

        if active_addr > 500000:  # Для BTC
            health_status = "Высокая активность сети - сильное использование"
        elif active_addr > 300000:
            health_status = "Нормальная активность сети"
        else:
            health_status = "Низкая активность сети - слабый интерес"

        return health_status

    def _interpret_exchange_flows(self, flows: Dict[str, Any]) -> str:
        """Интерпретация exchange flows"""
        net_flow = flows.get("net_flow", 0)

        if net_flow > 1000:  # Для BTC
            return "Сильный приток на биржи - возможное давление продаж (bearish)"
        elif net_flow > 0:
            return "Приток на биржи - умеренное давление продаж (слабо bearish)"
        elif net_flow < -1000:
            return "Сильный отток с бирж - накопление (очень bullish)"
        else:
            return "Отток с бирж - накопление (bullish)"

    def _generate_summary(self, data: Dict[str, Any]) -> str:
        """
        Генерирует текстовое резюме для AI

        Это резюме будет добавлено в промпт для OpenAI
        """
        coin_id = data.get("coin_id", "").upper()
        summary_parts = [f"📊 ПОЛНАЯ АНАЛИТИКА: {coin_id}\n"]

        # Price data
        if data.get("price_data"):
            price = data["price_data"]
            change = price.get("price_change_percentage_24h", 0)
            emoji = "📈" if change > 0 else "📉"
            summary_parts.append(
                f"{emoji} Цена: ${price.get('current_price', 0):,.2f} ({change:+.2f}% за 24ч)"
            )

        # Funding data
        if data.get("funding_data"):
            funding = data["funding_data"]
            summary_parts.append(
                f"💰 Funding Rate: {funding['funding_rate_pct']:.4f}% ({funding['sentiment']})"
            )
            summary_parts.append(f"   → {funding['interpretation']}")

        # Cycle data (Bitcoin only)
        if data.get("cycle_data"):
            cycle = data["cycle_data"]
            summary_parts.append(
                f"🌈 Rainbow Chart: {cycle['current_band'].replace('_', ' ').title()}"
            )
            summary_parts.append(f"   → {cycle['interpretation']}")

        # On-chain data
        if data.get("onchain_data"):
            onchain = data["onchain_data"]
            summary_parts.append(
                f"⛓️ Активные адреса: {onchain.get('active_addresses', 0):,}"
            )
            summary_parts.append(f"   → {onchain['interpretation']}")

            if onchain.get("exchange_flows"):
                flows = onchain["exchange_flows"]
                summary_parts.append(
                    f"🔄 Exchange Flows: {flows['net_flow']:,.2f} ({flows['sentiment']})"
                )
                summary_parts.append(f"   → {flows['interpretation']}")

        # Fear & Greed
        if data.get("fear_greed"):
            fg = data["fear_greed"]
            summary_parts.append(
                f"😱 Fear & Greed: {fg['value']}/100 ({fg['classification']})"
            )

        return "\n".join(summary_parts)


# Singleton instance
analytics_aggregator = AnalyticsAggregator()
