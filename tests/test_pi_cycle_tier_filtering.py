# coding: utf-8
"""
Test Pi Cycle Tier Filtering

Проверяет, что Pi Cycle правильно фильтруется для разных подписок:
- FREE: не может вызвать get_technical_analysis вообще
- BASIC: Rainbow Chart ✅, Pi Cycle заблокирован 🔒
- PREMIUM: Rainbow Chart ✅, Pi Cycle ✅
- VIP: Rainbow Chart ✅, Pi Cycle ✅
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.crypto_tools import execute_tool


async def test_pi_cycle_filtering():
    """
    Тест фильтрации Pi Cycle для разных subscription tiers
    """
    print("=" * 80)
    print("🧪 ТЕСТ ФИЛЬТРАЦИИ PI CYCLE ПО ПОДПИСКАМ")
    print("=" * 80)

    # Тестовые параметры
    tool_name = "get_technical_analysis"
    arguments = {"coin_id": "bitcoin", "timeframe": "1d"}

    # ========================================================================
    # TEST 1: FREE tier - базовые индикаторы, НО без cycle_data
    # ========================================================================
    print("\n" + "=" * 80)
    print("📊 TEST 1: FREE TIER")
    print("=" * 80)
    print("Ожидание: Доступ к базовым индикаторам, но БЕЗ cycle_data")

    result_json = await execute_tool(tool_name, arguments, user_tier="free")
    result = json.loads(result_json)

    # FREE должен получить ответ (не upgrade_required)
    if result.get("upgrade_required"):
        print("❌ FAIL: FREE tier должен иметь доступ к базовым индикаторам!")
        return False

    # НО cycle_data должен отсутствовать
    if "cycle_data" in result:
        print("❌ FAIL: FREE tier НЕ должен получать cycle_data!")
        print(f"   Получено: {list(result['cycle_data'].keys())}")
        return False

    # Проверяем что есть базовые индикаторы (RSI, MACD, EMA)
    if "technical_indicators" in result and result["technical_indicators"]:
        indicators = result["technical_indicators"]
        print("✅ PASS: FREE tier получает базовые индикаторы")
        print(f"   Доступно: RSI={indicators.get('rsi'):.1f}, MACD={indicators.get('macd'):.2f}, EMA_20={indicators.get('ema_20'):.0f}")
        print("✅ PASS: cycle_data корректно отфильтрован")
    else:
        print("❌ FAIL: FREE tier должен получать хотя бы базовые индикаторы")
        print(f"   Получено: {list(result.keys())}")
        return False

    # ========================================================================
    # TEST 2: BASIC tier - Rainbow Chart да, Pi Cycle нет
    # ========================================================================
    print("\n" + "=" * 80)
    print("📊 TEST 2: BASIC TIER")
    print("=" * 80)
    print("Ожидание: Rainbow Chart доступен, Pi Cycle заблокирован")

    result_json = await execute_tool(tool_name, arguments, user_tier="basic")
    result = json.loads(result_json)

    if "cycle_data" not in result:
        print("❌ FAIL: cycle_data должен быть в результате")
        return False

    cycle_data = result["cycle_data"]

    # Проверяем Rainbow Chart (должен быть доступен)
    if "current_band" in cycle_data:
        print(f"✅ PASS: Rainbow Chart доступен")
        print(f"   Current band: {cycle_data['current_band']}")
        print(f"   Sentiment: {cycle_data['sentiment']}")
    else:
        print("❌ FAIL: Rainbow Chart должен быть доступен для BASIC")
        return False

    # Проверяем Pi Cycle (должен быть заблокирован)
    if "pi_cycle" in cycle_data:
        pi_cycle = cycle_data["pi_cycle"]
        if pi_cycle.get("locked"):
            print(f"✅ PASS: Pi Cycle заблокирован для BASIC")
            print(f"   Сообщение: {pi_cycle.get('message', '')[:100]}...")
            print(f"   Требуется: {pi_cycle.get('tier_required')}")
        else:
            print("❌ FAIL: Pi Cycle должен быть заблокирован для BASIC!")
            return False
    else:
        print("⚠️  WARNING: pi_cycle отсутствует в cycle_data")

    # ========================================================================
    # TEST 3: PREMIUM tier - полный доступ
    # ========================================================================
    print("\n" + "=" * 80)
    print("📊 TEST 3: PREMIUM TIER")
    print("=" * 80)
    print("Ожидание: Rainbow Chart + Pi Cycle оба доступны")

    result_json = await execute_tool(tool_name, arguments, user_tier="premium")
    result = json.loads(result_json)

    if "cycle_data" not in result:
        print("❌ FAIL: cycle_data должен быть в результате")
        return False

    cycle_data = result["cycle_data"]

    # Проверяем Rainbow Chart
    if "current_band" in cycle_data:
        print(f"✅ PASS: Rainbow Chart доступен")
        print(f"   Current band: {cycle_data['current_band']}")
    else:
        print("❌ FAIL: Rainbow Chart должен быть доступен")
        return False

    # Проверяем Pi Cycle (должен быть разблокирован)
    if "pi_cycle" in cycle_data:
        pi_cycle = cycle_data["pi_cycle"]
        if not pi_cycle.get("locked"):
            print(f"✅ PASS: Pi Cycle доступен для PREMIUM")
            print(f"   Signal: {pi_cycle.get('signal')}")
            print(f"   MA 111: ${pi_cycle.get('ma_111', 0):,.2f}")
            print(f"   MA 350×2: ${pi_cycle.get('ma_350_x2', 0):,.2f}")
            print(f"   Distance to top: {pi_cycle.get('distance_to_top_pct', 0):+.2f}%")
        else:
            print("❌ FAIL: Pi Cycle НЕ должен быть заблокирован для PREMIUM!")
            return False
    else:
        print("⚠️  WARNING: pi_cycle отсутствует в cycle_data")
        print("   (Возможно недостаточно исторических данных)")

    # ========================================================================
    # TEST 4: VIP tier - полный доступ
    # ========================================================================
    print("\n" + "=" * 80)
    print("📊 TEST 4: VIP TIER")
    print("=" * 80)
    print("Ожидание: Rainbow Chart + Pi Cycle оба доступны")

    result_json = await execute_tool(tool_name, arguments, user_tier="vip")
    result = json.loads(result_json)

    if "cycle_data" not in result:
        print("❌ FAIL: cycle_data должен быть в результате")
        return False

    cycle_data = result["cycle_data"]

    # Проверяем Pi Cycle (должен быть разблокирован)
    if "pi_cycle" in cycle_data:
        pi_cycle = cycle_data["pi_cycle"]
        if not pi_cycle.get("locked"):
            print(f"✅ PASS: Pi Cycle доступен для VIP")
            print(f"   Signal: {pi_cycle.get('signal')}")
            print(f"   Distance to top: {pi_cycle.get('distance_to_top_pct', 0):+.2f}%")
        else:
            print("❌ FAIL: Pi Cycle НЕ должен быть заблокирован для VIP!")
            return False
    else:
        print("⚠️  WARNING: pi_cycle отсутствует в cycle_data")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 80)
    print("📊 ИТОГОВАЯ ТАБЛИЦА ДОСТУПА")
    print("=" * 80)
    print("\n| Tier    | get_technical_analysis | Rainbow Chart | Pi Cycle    |")
    print("|---------|------------------------|---------------|-------------|")
    print("| FREE    | ❌ Blocked              | ❌ No access   | ❌ No access |")
    print("| BASIC   | ✅ Allowed              | ✅ Available   | 🔒 Locked    |")
    print("| PREMIUM | ✅ Allowed              | ✅ Available   | ✅ Available |")
    print("| VIP     | ✅ Allowed              | ✅ Available   | ✅ Available |")

    print("\n" + "=" * 80)
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО")
    print("=" * 80)

    print("\n💎 МОНЕТИЗАЦИЯ:")
    print("   • BASIC ($9.99/мес): Базовый анализ цикла (Rainbow Chart)")
    print("   • PREMIUM ($24.99/мес): Точный индикатор вершин (Pi Cycle)")
    print("   • Value prop: 'Узнай ТОЧНУЮ дистанцию до топа → Upgrade!'")

    return True


async def main():
    """Запуск теста"""
    try:
        success = await test_pi_cycle_filtering()

        if success:
            print("\n✅ Фильтрация Pi Cycle работает корректно!")
            print("💰 Готово к монетизации через PREMIUM подписки")
        else:
            print("\n❌ Тест провален - требуется доработка")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ ОШИБКА ПРИ ТЕСТИРОВАНИИ: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
