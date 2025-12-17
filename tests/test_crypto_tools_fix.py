"""
Тест исправления проблемы с market data в crypto_tools
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.crypto_tools import get_market_overview
from loguru import logger


async def test_market_overview():
    """Тестируем получение market overview с исправленным кодом"""

    logger.info("=" * 60)
    logger.info("ТЕСТ: Market Overview (после исправления)")
    logger.info("=" * 60)

    try:
        result = await get_market_overview()

        logger.info(f"\n✅ РЕЗУЛЬТАТ:")
        logger.info(f"Success: {result.get('success')}")

        if result.get('success'):
            # Проверяем BTC data (ключ "btc", не "btc_data")
            btc_data = result.get('btc', {})
            logger.info(f"\n📊 BTC DATA:")
            logger.info(f"  Price: ${btc_data.get('price', 0):,.2f}")
            logger.info(f"  Change 24h: {btc_data.get('change_24h', 0):+.2f}%")

            # Проверяем ETH data (ключ "eth", не "eth_data")
            eth_data = result.get('eth', {})
            logger.info(f"\n📊 ETH DATA:")
            logger.info(f"  Price: ${eth_data.get('price', 0):,.2f}")
            logger.info(f"  Change 24h: {eth_data.get('change_24h', 0):+.2f}%")

            # Проверяем Market data (ключ "market", не "market_data")
            market_data = result.get('market', {})
            logger.info(f"\n📊 MARKET DATA (исправлено):")
            logger.info(f"  BTC dominance: {market_data.get('btc_dominance', 0):.2f}%")
            logger.info(f"  ETH dominance: {market_data.get('eth_dominance', 0):.2f}%")
            logger.info(f"  Altcoin dominance: {market_data.get('altcoin_dominance', 0):.2f}%")
            logger.info(f"  Fear & Greed: {market_data.get('fear_greed_index', 0)}")
            logger.info(f"  Market trend: {market_data.get('trend', 'N/A')}")

            # Проверяем что значения НЕ None и НЕ 0
            btc_dom = market_data.get('btc_dominance', 0)
            eth_dom = market_data.get('eth_dominance', 0)

            if btc_dom > 0 and eth_dom > 0:
                logger.info(f"\n✅ ДАННЫЕ ПОЛУЧЕНЫ КОРРЕКТНО!")
                logger.info(f"   BTC dominance: {btc_dom:.2f}% (ожидаем ~56-58%)")
                logger.info(f"   ETH dominance: {eth_dom:.2f}% (ожидаем ~11-12%)")
            else:
                logger.error(f"\n❌ ДАННЫЕ ВСЁ ЕЩЁ НЕКОРРЕКТНЫ!")
                logger.error(f"   BTC: {btc_dom}, ETH: {eth_dom}")

            # Новости (ключ "news", не "news_data")
            news_data = result.get('news', [])
            logger.info(f"\n📰 NEWS: {len(news_data)} items")

        else:
            logger.error(f"❌ ОШИБКА: {result.get('error')}")

    except Exception as e:
        logger.exception(f"❌ EXCEPTION: {e}")

    logger.info("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(test_market_overview())
