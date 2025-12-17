"""
Тест оптимизаций для предотвращения rate limit в CoinGecko API

Проверяет:
1. Batch методы (get_batch_prices, get_batch_coins_data, get_top_altcoins)
2. Кэширование market_overview
3. Динамическое получение топ альткоинов
4. Rate limiter с max_wait
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import time
from loguru import logger

from src.services.coingecko_service import CoinGeckoService
from src.services.crypto_tools import get_market_overview


async def test_batch_methods():
    """Тест batch методов"""
    logger.info("=" * 60)
    logger.info("ТЕСТ 1: Batch методы")
    logger.info("=" * 60)

    service = CoinGeckoService(rate_limit=25)

    # 1. Test get_batch_prices
    logger.info("\n📊 Тестируем get_batch_prices...")
    coin_ids = ["bitcoin", "ethereum", "solana", "cardano", "polkadot"]

    start_time = time.time()
    prices = await service.get_batch_prices(coin_ids, include_market_cap=True)
    elapsed = time.time() - start_time

    if prices:
        logger.success(f"✅ Получили цены для {len(prices)} монет за {elapsed:.2f}с (1 API call)")
        for coin_id, data in list(prices.items())[:3]:
            logger.info(f"  • {coin_id}: ${data.get('usd', 0):,.2f}")
    else:
        logger.error("❌ Не удалось получить batch prices")

    # 2. Test get_batch_coins_data
    logger.info("\n📊 Тестируем get_batch_coins_data...")

    start_time = time.time()
    batch_data = await service.get_batch_coins_data(coin_ids)
    elapsed = time.time() - start_time

    if batch_data:
        logger.success(f"✅ Получили детальные данные для {len(batch_data)} монет за {elapsed:.2f}с (1 API call)")
        for coin in batch_data[:3]:
            logger.info(
                f"  • {coin['symbol'].upper()}: ${coin['current_price']:,.2f} "
                f"(ATH: ${coin['ath']:,.2f}, {coin['ath_change_percentage']:+.1f}%)"
            )
    else:
        logger.error("❌ Не удалось получить batch coins data")

    # 3. Test get_top_altcoins
    logger.info("\n📊 Тестируем get_top_altcoins...")

    start_time = time.time()
    top_alts = await service.get_top_altcoins(limit=20, exclude_stablecoins=True)
    elapsed = time.time() - start_time

    if top_alts:
        logger.success(f"✅ Получили {len(top_alts)} топ альткоинов за {elapsed:.2f}с (1 API call)")
        logger.info("  Топ 5 альткоинов:")
        for i, coin in enumerate(top_alts[:5], 1):
            logger.info(
                f"  {i}. {coin['symbol'].upper()} ({coin['id']}): "
                f"${coin['current_price']:,.2f} (MCap rank: {coin.get('market_cap_rank', 'N/A')})"
            )
    else:
        logger.error("❌ Не удалось получить top altcoins")

    # Show rate limiter stats
    stats = service.get_usage_stats()
    logger.info(f"\n📈 Rate Limiter Stats: {stats['rate_limiter']}")
    logger.info(f"📦 Cache Stats: {stats['cache']}")


async def test_market_overview_caching():
    """Тест кэширования market_overview"""
    logger.info("\n" + "=" * 60)
    logger.info("ТЕСТ 2: Кэширование market_overview")
    logger.info("=" * 60)

    # Первый вызов - будет делать реальные запросы
    logger.info("\n🔄 Первый вызов (должен делать API запросы)...")
    start_time = time.time()
    result1 = await get_market_overview()
    elapsed1 = time.time() - start_time

    if result1.get("success"):
        logger.success(f"✅ Первый вызов выполнен за {elapsed1:.2f}с")
        logger.info(f"  • BTC: ${result1['btc'].get('price', 0):,.2f}")
        logger.info(f"  • ETH: ${result1['eth'].get('price', 0):,.2f}")
        logger.info(f"  • Альткоинов: {len(result1.get('alts', []))}")
    else:
        logger.error(f"❌ Первый вызов failed: {result1.get('error')}")
        return

    # Второй вызов сразу после - должен вернуть кэш
    logger.info("\n🔄 Второй вызов сразу после (должен вернуть кэш)...")
    start_time = time.time()
    result2 = await get_market_overview()
    elapsed2 = time.time() - start_time

    if result2.get("success"):
        logger.success(f"✅ Второй вызов выполнен за {elapsed2:.2f}с")
        if elapsed2 < 0.1:
            logger.success(f"  🎯 Кэш работает! Время < 0.1с")
        else:
            logger.warning(f"  ⚠️ Возможно, кэш не сработал (время: {elapsed2:.2f}с)")
    else:
        logger.error(f"❌ Второй вызов failed")

    # Третий вызов через 3 секунды - всё ещё кэш
    logger.info("\n⏳ Ждём 3 секунды...")
    await asyncio.sleep(3)

    logger.info("🔄 Третий вызов через 3с (кэш всё ещё валиден)...")
    start_time = time.time()
    result3 = await get_market_overview()
    elapsed3 = time.time() - start_time

    if result3.get("success"):
        logger.success(f"✅ Третий вызов выполнен за {elapsed3:.2f}с")
        if elapsed3 < 0.1:
            logger.success(f"  🎯 Кэш всё ещё работает!")
        else:
            logger.warning(f"  ⚠️ Кэш мог истечь")


async def test_dynamic_altcoins():
    """Тест динамического получения альткоинов"""
    logger.info("\n" + "=" * 60)
    logger.info("ТЕСТ 3: Динамическое получение альткоинов")
    logger.info("=" * 60)

    service = CoinGeckoService(rate_limit=25)

    # Get categories
    logger.info("\n📂 Получаем доступные категории...")
    categories = await service.get_categories_list()

    if categories:
        logger.success(f"✅ Получено {len(categories)} категорий")
        logger.info("  Примеры категорий:")
        for cat in categories[:5]:
            logger.info(f"  • {cat.get('category_id')}: {cat.get('name')}")

    # Get coins by category
    logger.info("\n📊 Получаем монеты категории 'layer-1'...")
    layer1_coins = await service.get_coins_by_category(
        category="layer-1",
        per_page=10,
        exclude_btc_eth=True
    )

    if layer1_coins:
        logger.success(f"✅ Получено {len(layer1_coins)} Layer-1 монет")
        logger.info("  Топ 5 Layer-1 альткоинов:")
        for i, coin in enumerate(layer1_coins[:5], 1):
            logger.info(
                f"  {i}. {coin['symbol'].upper()}: ${coin['current_price']:,.2f} "
                f"(24h: {coin.get('price_change_percentage_24h', 0):+.2f}%)"
            )


async def test_rate_limiter_max_wait():
    """Тест rate limiter с max_wait"""
    logger.info("\n" + "=" * 60)
    logger.info("ТЕСТ 4: Rate Limiter с max_wait")
    logger.info("=" * 60)

    service = CoinGeckoService(rate_limit=5)  # Низкий лимит для теста

    logger.info("\n🔥 Делаем 6 быстрых запросов (лимит: 5/min)...")

    for i in range(6):
        try:
            start = time.time()
            result = await service.get_price("bitcoin")
            elapsed = time.time() - start

            if result:
                logger.info(f"  {i+1}. ✅ Запрос выполнен за {elapsed:.2f}с")
            else:
                logger.warning(f"  {i+1}. ⚠️ Запрос вернул None (возможно, кэш при rate limit)")
        except Exception as e:
            logger.error(f"  {i+1}. ❌ Ошибка: {e}")

    stats = service.get_usage_stats()
    logger.info(f"\n📈 Финальные stats: {stats['rate_limiter']}")


async def main():
    """Запуск всех тестов"""
    logger.info("🚀 Начинаем тестирование оптимизаций CoinGecko API")

    try:
        await test_batch_methods()
        await asyncio.sleep(2)

        await test_market_overview_caching()
        await asyncio.sleep(2)

        await test_dynamic_altcoins()
        await asyncio.sleep(2)

        await test_rate_limiter_max_wait()

        logger.success("\n" + "=" * 60)
        logger.success("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ!")
        logger.success("=" * 60)

    except Exception as e:
        logger.exception(f"❌ Ошибка в тестах: {e}")


if __name__ == "__main__":
    asyncio.run(main())
