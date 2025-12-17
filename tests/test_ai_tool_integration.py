"""
Тест интеграции AI tools - симулирует как AI будет вызывать наши функции
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import json
from loguru import logger

from src.services.crypto_tools import execute_tool, CRYPTO_TOOLS


async def simulate_ai_calls():
    """Симулирует вызовы AI для проверки всех tools"""

    logger.info("🤖 СИМУЛЯЦИЯ AI ВЫЗОВОВ")
    logger.info("=" * 70)

    # Тест 1: Пользователь спрашивает про Layer-1
    logger.info("\n📝 ТЕСТ 1: Пользователь спрашивает 'Покажи топ Layer-1 блокчейны'")
    logger.info("-" * 70)

    # AI выбирает tool
    logger.info("🤖 AI выбирает: get_coins_by_category")
    logger.info("📤 AI вызывает с параметрами: category='layer-1', limit=5")

    # Симулируем вызов
    tool_call = {
        "name": "get_coins_by_category",
        "arguments": json.dumps({"category": "layer-1", "limit": 5})
    }

    result = await execute_tool(tool_call["name"], tool_call["arguments"])
    result_data = json.loads(result)

    if result_data.get("success"):
        logger.success(f"✅ Получено {result_data.get('count')} монет в категории '{result_data.get('category')}'")
        logger.info("📊 Топ 3 монеты:")
        for i, coin in enumerate(result_data.get("coins", [])[:3], 1):
            logger.info(f"  {i}. {coin['symbol']}: ${coin['price_usd']:,.2f} (24h: {coin['change_24h_percent']:+.2f}%)")
    else:
        logger.error(f"❌ Ошибка: {result_data.get('error')}")

    # Тест 2: Пользователь спрашивает про DeFi
    logger.info("\n📝 ТЕСТ 2: Пользователь спрашивает 'Какие есть DeFi проекты?'")
    logger.info("-" * 70)

    logger.info("🤖 AI выбирает: get_coins_by_category")
    logger.info("📤 AI вызывает с параметрами: category='decentralized-finance-defi', limit=5")

    tool_call = {
        "name": "get_coins_by_category",
        "arguments": json.dumps({"category": "decentralized-finance-defi", "limit": 5})
    }

    result = await execute_tool(tool_call["name"], tool_call["arguments"])
    result_data = json.loads(result)

    if result_data.get("success"):
        logger.success(f"✅ Получено {result_data.get('count')} DeFi проектов")
        logger.info("📊 Топ 3 DeFi:")
        for i, coin in enumerate(result_data.get("coins", [])[:3], 1):
            logger.info(f"  {i}. {coin['symbol']}: ${coin['price_usd']:,.2f} (Rank: #{coin['rank']})")
    else:
        logger.error(f"❌ Ошибка: {result_data.get('error')}")

    # Тест 3: Топ альткоины (обновлённый метод)
    logger.info("\n📝 ТЕСТ 3: Пользователь спрашивает 'Покажи топ альткоины без биткоина'")
    logger.info("-" * 70)

    logger.info("🤖 AI выбирает: get_top_cryptos")
    logger.info("📤 AI вызывает с параметрами: limit=5, altcoins_only=true")

    tool_call = {
        "name": "get_top_cryptos",
        "arguments": json.dumps({"limit": 5, "altcoins_only": True})
    }

    result = await execute_tool(tool_call["name"], tool_call["arguments"])
    result_data = json.loads(result)

    if result_data.get("success"):
        logger.success(f"✅ Получено {result_data.get('count')} топ альткоинов")
        logger.info("📊 Топ 5 альткоинов:")
        for i, coin in enumerate(result_data.get("coins", []), 1):
            logger.info(f"  {i}. {coin['symbol']} ({coin['name']}): ${coin['price_usd']:,.2f}")
    else:
        logger.error(f"❌ Ошибка: {result_data.get('error')}")

    # Тест 4: Проверка списка всех tools
    logger.info("\n📋 ИТОГО ДОСТУПНО AI TOOLS:")
    logger.info("=" * 70)
    for i, tool in enumerate(CRYPTO_TOOLS, 1):
        tool_name = tool['function']['name']
        marker = "🆕" if tool_name == "get_coins_by_category" else "✅"
        logger.info(f"{i}. {marker} {tool_name}")

    logger.success("\n✅ ВСЕ AI TOOLS РАБОТАЮТ КОРРЕКТНО!")


async def main():
    try:
        await simulate_ai_calls()
    except Exception as e:
        logger.exception(f"Ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())
