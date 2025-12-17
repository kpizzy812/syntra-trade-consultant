"""
Тест для проверки CoinGecko API и выявления проблемы с market_cap_percentage
"""
import asyncio
import sys
import os

# Добавляем путь к src для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.coingecko_service import CoinGeckoService
from loguru import logger


async def test_global_market_data():
    """Тестируем получение global market data от CoinGecko API"""

    logger.info("=" * 60)
    logger.info("ТЕСТ: CoinGecko API - Global Market Data")
    logger.info("=" * 60)

    # Инициализируем сервис
    service = CoinGeckoService(rate_limit=25)

    # Тест 1: Прямой запрос к /global endpoint
    logger.info("\n1️⃣ ПРЯМОЙ ЗАПРОС К /global ENDPOINT:")
    raw_data = await service._make_request("/global")

    if raw_data:
        logger.info(f"✅ RAW DATA получен")
        logger.info(f"Ключи верхнего уровня: {list(raw_data.keys())}")

        if "data" in raw_data:
            market_data = raw_data["data"]
            logger.info(f"\nКлючи в 'data': {list(market_data.keys())[:10]}...")

            # Проверяем наличие market_cap_percentage
            if "market_cap_percentage" in market_data:
                mcp = market_data["market_cap_percentage"]
                logger.info(f"\n✅ market_cap_percentage НАЙДЕН!")
                logger.info(f"Тип: {type(mcp)}")
                logger.info(f"Содержимое: {mcp}")
                logger.info(f"\nBTC: {mcp.get('btc')}")
                logger.info(f"ETH: {mcp.get('eth')}")
            else:
                logger.error("\n❌ market_cap_percentage НЕ НАЙДЕН в ответе!")
                logger.info(f"Доступные ключи: {list(market_data.keys())}")
    else:
        logger.error("❌ RAW DATA = None (API не ответил)")

    # Тест 2: Через метод get_global_market_data()
    logger.info("\n\n2️⃣ ЧЕРЕЗ МЕТОД get_global_market_data():")
    global_data = await service.get_global_market_data()

    if global_data:
        logger.info(f"✅ global_data получен")
        logger.info(f"Ключи: {list(global_data.keys())}")
        logger.info(f"\nBTC dominance: {global_data.get('btc_dominance')}")
        logger.info(f"ETH dominance: {global_data.get('eth_dominance')}")
        logger.info(f"Altcoin dominance: {global_data.get('altcoin_dominance')}")

        # Проверяем наличие market_cap_percentage
        if "market_cap_percentage" in global_data:
            logger.info(f"\n✅ market_cap_percentage есть в обработанных данных")
        else:
            logger.warning(f"\n⚠️ market_cap_percentage НЕТ в обработанных данных")
            logger.info("Это ожидаемо - метод возвращает уже обработанные btc_dominance/eth_dominance")
    else:
        logger.error("❌ global_data = None")

    # Тест 3: Проверка rate limiter
    logger.info("\n\n3️⃣ СТАТИСТИКА СЕРВИСА:")
    stats = service.get_usage_stats()
    logger.info(f"Rate limiter: {stats['rate_limiter']}")
    logger.info(f"Cache: {stats['cache']}")

    logger.info("\n" + "=" * 60)


async def main():
    try:
        await test_global_market_data()
    except Exception as e:
        logger.exception(f"Ошибка при тестировании: {e}")


if __name__ == "__main__":
    asyncio.run(main())