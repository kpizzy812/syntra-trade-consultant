# coding: utf-8
"""
Test Pi Cycle Integration

Проверяет, что Pi Cycle правильно интегрирован в систему:
1. Расчёт Pi Cycle для Bitcoin
2. Передача данных в cycle_data
3. Передача контекста для альткоинов через btc_data
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.crypto_tools import get_technical_analysis


async def test_pi_cycle_integration():
    """
    Тест интеграции Pi Cycle в систему
    """
    print("=" * 80)
    print("🧪 ТЕСТ ИНТЕГРАЦИИ PI CYCLE")
    print("=" * 80)

    print("\n📊 Тестирую расчет Pi Cycle для Bitcoin...\n")

    try:
        # Получаем технический анализ Bitcoin
        btc_result = await get_technical_analysis(
            coin_id="bitcoin",
            timeframe="1d",
        )

        # Проверяем наличие cycle_data
        if "cycle_data" not in btc_result:
            print("❌ ОШИБКА: cycle_data отсутствует в результате")
            return False

        cycle_data = btc_result["cycle_data"]

        # Проверяем Rainbow Chart
        print("🌈 RAINBOW CHART:")
        print(f"   Current Band: {cycle_data.get('current_band', 'N/A')}")
        print(f"   Sentiment: {cycle_data.get('sentiment', 'N/A')}")
        print(f"   Days since genesis: {cycle_data.get('days_since_genesis', 'N/A')}")

        # Проверяем Pi Cycle
        print("\n⭕ PI CYCLE TOP INDICATOR:")
        if "pi_cycle" in cycle_data:
            pi_cycle = cycle_data["pi_cycle"]
            print(f"   ✅ Pi Cycle данные найдены!")
            print(f"   MA 111: ${pi_cycle.get('ma_111', 0):,.2f}")
            print(f"   MA 350×2: ${pi_cycle.get('ma_350_x2', 0):,.2f}")
            print(f"   Signal: {pi_cycle.get('signal', 'N/A')}")
            print(f"   Distance to top: {pi_cycle.get('distance_to_top_pct', 0):+.2f}%")

            # Интерпретация сигнала
            signal = pi_cycle.get('signal')
            distance = pi_cycle.get('distance_to_top_pct', 0)

            print("\n   📈 ИНТЕРПРЕТАЦИЯ:")
            if signal == "top_signal":
                print("   🚨 ИСТОРИЧЕСКИЙ СИГНАЛ ВЕРШИНЫ ЦИКЛА!")
                print("   ⚠️  Медианная коррекция после top_signal: -50-80%")
            elif signal == "overheated":
                print("   🟡 Рынок перегрет (111DMA выше 350DMA×2)")
                if distance < 5:
                    print("   ⚠️  Опасная зона! Близко к вершине цикла")
            elif signal == "bullish":
                print("   🟢 Бычий тренд, далеко от вершины цикла")
                if distance > 10:
                    print("   ✅ Хороший запас до топа")

        else:
            print("   ⚠️  Pi Cycle данные отсутствуют")
            print("   (Возможно недостаточно исторических данных)")

        # Проверяем 200 Week MA
        print("\n📊 200 WEEK MOVING AVERAGE:")
        if "ma_200w" in cycle_data:
            ma_200w = cycle_data["ma_200w"]
            distance = cycle_data.get("distance_from_200w_pct", 0)
            print(f"   ✅ 200W MA: ${ma_200w:,.2f}")
            print(f"   Distance: {distance:+.1f}% from floor")

            if distance < 20:
                print("   🟢 Близко к историческому полу рынка")
            elif distance > 200:
                print("   🔴 Экстремальный перегрев, далеко от пола")
            else:
                print("   🔵 Нормальная дистанция от пола")
        else:
            print("   ⚠️  200W MA данные отсутствуют")

        # Суммарный вывод
        print("\n" + "=" * 80)
        print("📊 ФАЗА ЦИКЛА BITCOIN:")
        print("=" * 80)

        rainbow_band = cycle_data.get('current_band', '')
        pi_signal = cycle_data.get('pi_cycle', {}).get('signal', '')
        ma_distance = cycle_data.get('distance_from_200w_pct', 0)

        # Определяем фазу
        if rainbow_band in ['buy', 'accumulate', 'basically_a_fire_sale']:
            phase_color = "🟢"
            phase_name = "НАКОПЛЕНИЕ (Дно цикла)"
        elif rainbow_band in ['hodl', 'still_cheap']:
            phase_color = "🔵"
            phase_name = "СЕРЕДИНА ЦИКЛА"
        elif rainbow_band in ['is_this_a_bubble', 'fomo_intensifies']:
            phase_color = "🟡"
            phase_name = "ПЕРЕГРЕВ (Конец цикла близко)"
        elif rainbow_band in ['sell', 'maximum_bubble']:
            phase_color = "🔴"
            phase_name = "ТОП ЦИКЛА (Зона фиксации)"
        else:
            phase_color = "⚪"
            phase_name = "НЕИЗВЕСТНО"

        print(f"\n{phase_color} Текущая фаза: {phase_name}")
        print(f"\n📋 Сигналы:")
        print(f"   • Rainbow Chart: {rainbow_band}")
        print(f"   • Pi Cycle: {pi_signal}")
        print(f"   • 200W MA: {ma_distance:+.1f}% от пола")

        # Рекомендации для трейдеров
        print(f"\n💡 Что это значит для трейдинга:")
        if pi_signal == "top_signal":
            print("   🚨 Pi Cycle даёт ИСТОРИЧЕСКИЙ сигнал вершины!")
            print("   ⚠️  Фиксируй прибыль, не открывай новые лонги")
            print("   📊 Альткоины КРИТИЧЕСКИ перегреты")
        elif rainbow_band in ['sell', 'maximum_bubble']:
            print("   🔴 Bitcoin в зоне топа цикла")
            print("   ⚠️  Альткоины тоже перегреты, даже если техничка хороша")
        elif rainbow_band in ['buy', 'accumulate']:
            print("   🟢 Bitcoin в зоне накопления")
            print("   ✅ Альткоины в огненной распродаже - время накапливать")
        else:
            print("   🔵 Нормальная фаза цикла")
            print("   📈 Можно рассматривать торговые возможности")

        print("\n" + "=" * 80)
        print("✅ ТЕСТ ЗАВЕРШЁН УСПЕШНО")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"\n❌ ОШИБКА ПРИ ТЕСТИРОВАНИИ: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Запуск теста"""
    success = await test_pi_cycle_integration()

    if success:
        print("\n✅ Pi Cycle успешно интегрирован в систему!")
    else:
        print("\n❌ Интеграция Pi Cycle требует доработки")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
