"""
Тест адаптации параметров сценариев под разные таймфреймы

Проверяет что AI корректно адаптирует:
- Stop Loss размеры (tight для 1h, wide для 1d)
- Take Profit цели (R:R зависит от TF)
- Leverage рекомендации
- Invalidation timing
"""
import asyncio
from src.services.futures_analysis_service import futures_analysis_service


async def test_timeframe_adaptation():
    """
    Тестируем что AI адаптирует параметры под разные таймфреймы
    """

    symbol = "BTCUSDT"
    timeframes = ["1h", "4h", "1d"]

    print("=" * 80)
    print("🧪 ТЕСТ АДАПТАЦИИ ПОД ТАЙМФРЕЙМЫ")
    print("=" * 80)
    print()

    results = {}

    for tf in timeframes:
        print(f"\n📊 Анализ {symbol} на таймфрейме {tf}...")
        print("-" * 80)

        try:
            # Получаем сценарии для данного таймфрейма
            result = await futures_analysis_service.analyze_symbol(
                symbol=symbol,
                timeframe=tf,
                max_scenarios=2
            )

            if not result.get("success"):
                print(f"❌ Ошибка: {result.get('error')}")
                continue

            scenarios = result.get("scenarios", [])
            current_price = result.get("current_price", 0)

            print(f"✅ Получено сценариев: {len(scenarios)}")
            print(f"💰 Текущая цена: ${current_price:,.2f}")
            print()

            # Анализируем первый сценарий (самый вероятный)
            if scenarios:
                sc = scenarios[0]

                # Рассчитываем размер стопа в %
                entry_mid = (sc["entry"]["price_min"] + sc["entry"]["price_max"]) / 2
                stop = sc["stop_loss"]["recommended"]

                stop_pct = abs((stop - entry_mid) / entry_mid * 100)

                # Анализируем targets
                targets = sc.get("targets", [])
                rr_values = [t.get("rr", 0) for t in targets]

                # Leverage
                leverage = sc.get("leverage", {}).get("recommended", "N/A")

                # Сохраняем результаты
                results[tf] = {
                    "name": sc.get("name"),
                    "bias": sc.get("bias"),
                    "confidence": sc.get("confidence"),
                    "entry_mid": entry_mid,
                    "stop_pct": stop_pct,
                    "rr_values": rr_values,
                    "leverage": leverage,
                    "conditions": sc.get("conditions", [])
                }

                print(f"🎯 Сценарий: {sc.get('name')} ({sc.get('bias').upper()})")
                print(f"   Confidence: {sc.get('confidence')*100:.1f}%")
                print(f"   Entry: ${entry_mid:,.2f}")
                print(f"   Stop Loss: ${stop:,.2f} ({stop_pct:.2f}%)")
                print(f"   Risk:Reward: {', '.join([f'{r:.1f}R' for r in rr_values])}")
                print(f"   Leverage: {leverage}")
                print(f"   Conditions: {len(sc.get('conditions', []))} условий")

                # Проверяем временные условия
                time_conditions = [c for c in sc.get("conditions", []) if "течение" in c.lower() or "часов" in c.lower() or "дней" in c.lower() or "недел" in c.lower()]
                if time_conditions:
                    print(f"   ⏰ Время жизни: {time_conditions[0]}")

        except Exception as e:
            print(f"❌ Ошибка при анализе {tf}: {e}")
            import traceback
            traceback.print_exc()

    # Сравнительный анализ
    print("\n" + "=" * 80)
    print("📈 СРАВНИТЕЛЬНЫЙ АНАЛИЗ АДАПТАЦИИ")
    print("=" * 80)
    print()

    if len(results) >= 2:
        print("Таймфрейм | Stop % | Max R:R | Leverage | Оценка")
        print("-" * 80)

        for tf in timeframes:
            if tf in results:
                r = results[tf]
                max_rr = max(r["rr_values"]) if r["rr_values"] else 0

                # Оценка корректности адаптации
                assessment = ""
                if tf in ["15m", "1h"]:
                    # Для 1h ожидаем: tight stop (0.3-0.5%), leverage 10x-15x, max RR до 4
                    if r["stop_pct"] <= 0.7 and max_rr <= 5:
                        assessment = "✅ Correct"
                    else:
                        assessment = "⚠️ Check"
                elif tf == "4h":
                    # Для 4h ожидаем: medium stop (0.8-1.5%), leverage 5x-8x, max RR до 6
                    if 0.6 <= r["stop_pct"] <= 2.0 and max_rr <= 7:
                        assessment = "✅ Correct"
                    else:
                        assessment = "⚠️ Check"
                elif tf == "1d":
                    # Для 1d ожидаем: wide stop (2-3%), leverage 3x-5x, max RR до 10
                    if r["stop_pct"] >= 1.5 and max_rr >= 5:
                        assessment = "✅ Correct"
                    else:
                        assessment = "⚠️ Check"

                print(f"{tf:9s} | {r['stop_pct']:5.2f}% | {max_rr:6.1f}R | {r['leverage']:8s} | {assessment}")

        print()
        print("💡 ВЫВОДЫ:")
        print("-" * 80)

        # Проверяем что стопы увеличиваются с таймфреймом
        if "1h" in results and "1d" in results:
            if results["1d"]["stop_pct"] > results["1h"]["stop_pct"]:
                print("✅ Стопы корректно масштабируются: 1d > 1h")
            else:
                print("⚠️ ПРОБЛЕМА: Стопы на 1d должны быть шире чем на 1h!")

        # Проверяем что R:R увеличивается с таймфреймом
        if "1h" in results and "1d" in results:
            max_rr_1h = max(results["1h"]["rr_values"]) if results["1h"]["rr_values"] else 0
            max_rr_1d = max(results["1d"]["rr_values"]) if results["1d"]["rr_values"] else 0

            if max_rr_1d > max_rr_1h:
                print("✅ Risk:Reward корректно масштабируется: 1d > 1h")
            else:
                print("⚠️ ПРОБЛЕМА: R:R на 1d должен быть выше чем на 1h!")

        # Проверяем временные условия
        print()
        print("⏰ ВРЕМЕННЫЕ УСЛОВИЯ:")
        for tf in timeframes:
            if tf in results:
                time_conds = [c for c in results[tf]["conditions"] if "течение" in c.lower() or "часов" in c.lower() or "дней" in c.lower() or "недел" in c.lower()]
                if time_conds:
                    print(f"   {tf}: {time_conds[0]}")
                else:
                    print(f"   {tf}: ⚠️ Нет временных условий!")

    print("\n" + "=" * 80)
    print("🎉 ТЕСТ ЗАВЕРШЁН")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_timeframe_adaptation())
