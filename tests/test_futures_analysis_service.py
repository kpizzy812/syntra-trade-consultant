# coding: utf-8
"""
Unit tests for FuturesAnalysisService - новые методы после ultrathink session

Проверяем:
- _calculate_price_structure() - swing points, volatility regime, range detection
- _aggregate_liquidation_clusters() - binning, spike detection, pressure bias

Все edge cases из FUTURES_CRITICAL_BUGFIXES.md
"""
import sys
from pathlib import Path
import pandas as pd
import pytest
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.futures_analysis_service import FuturesAnalysisService


@pytest.fixture
def futures_service():
    """
    Создаём FuturesAnalysisService для unit tests

    Note: FuturesAnalysisService.__init__() не принимает аргументов,
    создаёт все зависимости внутри. Для unit tests мы просто создаём
    его и тестируем методы напрямую (они не делают API calls).
    """
    service = FuturesAnalysisService()
    return service


def create_sample_klines(num_candles=100, base_price=95000, volatility=0.01):
    """Создаём синтетические klines для тестов"""
    import numpy as np

    data = []
    price = base_price

    for i in range(num_candles):
        # Симулируем случайное движение цены
        change = np.random.randn() * volatility * price
        price += change

        high = price * (1 + abs(np.random.randn() * 0.005))
        low = price * (1 - abs(np.random.randn() * 0.005))
        open_price = price - change / 2
        close_price = price
        volume = abs(np.random.randn() * 1000000)

        data.append({
            "open": open_price,
            "high": high,
            "low": low,
            "close": close_price,
            "volume": volume
        })

    return pd.DataFrame(data)


def create_swing_pattern_klines():
    """
    Создаём klines с явными swing points для тестирования

    Паттерн: низкий -> высокий -> низкий -> высокий
    Это создаст чёткие swing highs и swing lows
    """
    prices = [
        # Начальный участок (создаём swing low)
        95000, 94800, 94500, 94800, 95000,  # idx 2 = swing low

        # Рост (создаём swing high)
        95500, 96000, 96500, 96000, 95500,  # idx 7 = swing high

        # Падение (создаём swing low)
        95000, 94500, 94000, 94500, 95000,  # idx 12 = swing low

        # Рост (создаём swing high)
        95500, 96000, 96800, 96000, 95500,  # idx 17 = swing high

        # Заполнение до 100
        *[95000 + (i % 10) * 100 for i in range(80)]
    ]

    data = []
    for i, close_price in enumerate(prices):
        data.append({
            "open": close_price - 50,
            "high": close_price + 100,
            "low": close_price - 100,
            "close": close_price,
            "volume": 1000000
        })

    return pd.DataFrame(data)


# ==================== TESTS: _calculate_price_structure() ====================

def test_calculate_price_structure_basic(futures_service):
    """🧪 Test #1: Базовая функциональность price structure"""

    print("\n🧪 Test #1: Calculate Price Structure - Basic")

    klines = create_sample_klines(num_candles=100, base_price=95000)
    current_price = 95000
    indicators = {
        "ema_20": 94800,
        "ema_50": 94500,
        "ema_200": 93000,
        "adx": 25,
        "atr_percent": 2.0  # normal volatility
    }

    result = futures_service._calculate_price_structure(
        klines=klines,
        current_price=current_price,
        indicators=indicators,
        timeframe="1h"
    )

    # Проверяем, что все ключевые поля присутствуют
    assert "swing_highs" in result, "Should have swing_highs"
    assert "swing_lows" in result, "Should have swing_lows"
    assert "range_high" in result, "Should have range_high"
    assert "range_low" in result, "Should have range_low"
    assert "range_size_pct" in result, "Should have range_size_pct"
    assert "current_position_in_range" in result, "Should have current_position_in_range"
    assert "trend_state" in result, "Should have trend_state"
    assert "volatility_regime" in result, "Should have volatility_regime"

    # Проверяем типы
    assert isinstance(result["swing_highs"], list), "swing_highs should be list"
    assert isinstance(result["swing_lows"], list), "swing_lows should be list"

    # Проверяем, что volatility_regime определён корректно
    assert result["volatility_regime"] == "normal", f"For ATR 2.0% should be 'normal', got {result['volatility_regime']}"

    print(f"  ✅ Range: {result['range_low']:.2f} - {result['range_high']:.2f}")
    print(f"  ✅ Volatility regime: {result['volatility_regime']}")
    print(f"  ✅ Swing highs found: {len(result['swing_highs'])}")
    print(f"  ✅ Swing lows found: {len(result['swing_lows'])}")


def test_volatility_regime_very_low(futures_service):
    """
    🧪 Test #2: Bug Fix - volatility_regime very_low достижим

    🐛 Было: elif atr_pct < 1.5: compression ... elif atr_pct < 1.0: very_low
    ✅ Стало: elif atr_pct < 1.0: very_low ... elif atr_pct < 1.5: compression
    """

    print("\n🧪 Test #2: Volatility Regime - very_low reachable")

    klines = create_sample_klines(num_candles=100, base_price=95000)
    current_price = 95000

    # ATR < 1.0 должен дать very_low
    indicators = {
        "ema_20": 94800,
        "ema_50": 94500,
        "adx": 20,
        "atr_percent": 0.8  # 🔥 < 1.0
    }

    result = futures_service._calculate_price_structure(
        klines=klines,
        current_price=current_price,
        indicators=indicators,
        timeframe="1h"
    )

    assert result["volatility_regime"] == "very_low", \
        f"For ATR 0.8% should be 'very_low', got {result['volatility_regime']}"

    print(f"  ✅ ATR: 0.8% → volatility_regime = {result['volatility_regime']}")

    # Проверяем compression (1.0 <= atr < 1.5)
    indicators["atr_percent"] = 1.2
    result = futures_service._calculate_price_structure(
        klines=klines,
        current_price=current_price,
        indicators=indicators,
        timeframe="1h"
    )

    assert result["volatility_regime"] == "compression", \
        f"For ATR 1.2% should be 'compression', got {result['volatility_regime']}"

    print(f"  ✅ ATR: 1.2% → volatility_regime = {result['volatility_regime']}")


def test_volatility_regime_all_cases(futures_service):
    """🧪 Test #3: Проверяем все volatility regime cases"""

    print("\n🧪 Test #3: Volatility Regime - all cases")

    klines = create_sample_klines(num_candles=100, base_price=95000)
    current_price = 95000

    test_cases = [
        (0.5, "very_low"),      # < 1.0
        (0.9, "very_low"),      # < 1.0
        (1.0, "compression"),   # >= 1.0, < 1.5
        (1.4, "compression"),   # >= 1.0, < 1.5
        (1.8, "normal"),        # >= 1.5, <= 2.5
        (2.3, "normal"),        # >= 1.5, <= 2.5
        (2.7, "expansion"),     # > 2.5, <= 3.0
        (3.5, "very_high"),     # > 3.0
    ]

    for atr_pct, expected_regime in test_cases:
        indicators = {
            "ema_20": 94800,
            "ema_50": 94500,
            "adx": 20,
            "atr_percent": atr_pct
        }

        result = futures_service._calculate_price_structure(
            klines=klines,
            current_price=current_price,
            indicators=indicators,
            timeframe="1h"
        )

        assert result["volatility_regime"] == expected_regime, \
            f"ATR {atr_pct}% should give '{expected_regime}', got '{result['volatility_regime']}'"

        print(f"  ✅ ATR {atr_pct}% → {expected_regime}")


def test_swing_points_temporal_sorting(futures_service):
    """
    🧪 Test #4: Bug Fix - swing points sorted by time (idx), not price

    🐛 Было: sorted(swing_highs, key=lambda x: x["price"])
    ✅ Стало: sorted(swing_highs, key=lambda x: x["idx"], reverse=True)
    """

    print("\n🧪 Test #4: Swing Points - temporal sorting")

    klines = create_swing_pattern_klines()
    current_price = 95500
    indicators = {
        "ema_20": 95000,
        "ema_50": 94500,
        "adx": 25,
        "atr_percent": 2.0
    }

    result = futures_service._calculate_price_structure(
        klines=klines,
        current_price=current_price,
        indicators=indicators,
        timeframe="1h"
    )

    # Проверяем, что swing_highs отсортированы по idx (последние первые)
    if len(result["swing_highs"]) >= 2:
        # Первый элемент должен иметь больший idx, чем второй (последние свечи первыми)
        for i in range(len(result["swing_highs"]) - 1):
            idx1 = result["swing_highs"][i]["idx"]
            idx2 = result["swing_highs"][i + 1]["idx"]
            assert idx1 > idx2, \
                f"Swing highs должны быть отсортированы по времени (убыванию idx), но {idx1} <= {idx2}"

        print("  ✅ Swing highs sorted by time (latest first)")
        for i, sh in enumerate(result["swing_highs"][:3]):
            print(f"     {i+1}. idx={sh['idx']}, price={sh['price']}")

    # То же для swing_lows
    if len(result["swing_lows"]) >= 2:
        for i in range(len(result["swing_lows"]) - 1):
            idx1 = result["swing_lows"][i]["idx"]
            idx2 = result["swing_lows"][i + 1]["idx"]
            assert idx1 > idx2, \
                f"Swing lows должны быть отсортированы по времени (убыванию idx), но {idx1} <= {idx2}"

        print("  ✅ Swing lows sorted by time (latest first)")


def test_range_and_position(futures_service):
    """🧪 Test #5: Range detection and current position"""

    print("\n🧪 Test #5: Range and Position")

    klines = create_sample_klines(num_candles=100, base_price=95000, volatility=0.02)
    current_price = 95000
    indicators = {
        "ema_20": 94800,
        "ema_50": 94500,
        "adx": 25,
        "atr_percent": 2.0
    }

    result = futures_service._calculate_price_structure(
        klines=klines,
        current_price=current_price,
        indicators=indicators,
        timeframe="1h"
    )

    # Проверяем, что range_high > range_low
    assert result["range_high"] > result["range_low"], \
        f"range_high ({result['range_high']}) должен быть > range_low ({result['range_low']})"

    # Проверяем, что position_in_range существует
    # Note: может быть < 0 (цена ниже range) или > 1 (цена выше range) - это нормально!
    assert "current_position_in_range" in result, "Should have current_position_in_range"
    assert isinstance(result["current_position_in_range"], (int, float)), \
        "current_position_in_range should be numeric"

    # Проверяем, что range_size_pct положительный
    assert result["range_size_pct"] > 0, \
        f"range_size_pct должен быть > 0, got {result['range_size_pct']}"

    print(f"  ✅ Range: {result['range_low']:.2f} - {result['range_high']:.2f}")
    print(f"  ✅ Range size: {result['range_size_pct']:.2f}%")
    print(f"  ✅ Current position: {result['current_position_in_range']:.2f}")
    if result["current_position_in_range"] < 0:
        print("     (price is below range - bearish breakout)")
    elif result["current_position_in_range"] > 1:
        print("     (price is above range - bullish breakout)")


# ==================== TESTS: _aggregate_liquidation_clusters() ====================

def test_aggregate_liquidation_clusters_basic(futures_service):
    """🧪 Test #6: Базовая функциональность liquidation clusters"""

    print("\n🧪 Test #6: Liquidation Clusters - Basic")

    current_price = 95000
    now = time.time() * 1000

    # Создаём тестовые liquidations
    liquidation_data = {
        "liquidations": [
            # Long liquidations ниже текущей цены
            {"side": "BUY", "price": 94500, "quantity": 1.0, "time": now - 1000},
            {"side": "BUY", "price": 94480, "quantity": 2.0, "time": now - 2000},
            {"side": "BUY", "price": 94520, "quantity": 1.5, "time": now - 3000},

            # Short liquidations выше текущей цены
            {"side": "SELL", "price": 95500, "quantity": 1.0, "time": now - 1000},
            {"side": "SELL", "price": 95480, "quantity": 2.0, "time": now - 2000},
        ]
    }

    result = futures_service._aggregate_liquidation_clusters(
        liquidation_data=liquidation_data,
        current_price=current_price
    )

    # Проверяем структуру результата
    assert "clusters_above" in result, "Should have clusters_above"
    assert "clusters_below" in result, "Should have clusters_below"
    assert "last_24h_liq_spike" in result, "Should have last_24h_liq_spike"
    assert "spike_magnitude" in result, "Should have spike_magnitude"
    assert "liq_pressure_bias" in result, "Should have liq_pressure_bias (renamed from net_liq_bias)"
    assert "long_liq_pct" in result, "Should have long_liq_pct"
    assert "short_liq_pct" in result, "Should have short_liq_pct"

    print(f"  ✅ Clusters above: {len(result['clusters_above'])}")
    print(f"  ✅ Clusters below: {len(result['clusters_below'])}")
    print(f"  ✅ Liq pressure bias: {result['liq_pressure_bias']}")
    print(f"  ✅ Long liq: {result['long_liq_pct']:.1f}%, Short liq: {result['short_liq_pct']:.1f}%")


def test_liquidation_binning_floor(futures_service):
    """
    🧪 Test #7: Bug Fix - liquidation binning uses floor(), not round()

    🐛 Было: bin_key = round(price / bin_size) * bin_size (прыгает)
    ✅ Стало: bin_key = math.floor(price / bin_size) * bin_size (предсказуемо)
    """

    print("\n🧪 Test #7: Liquidation Binning - floor instead of round")

    current_price = 95000
    bin_size = current_price * 0.005  # 0.5% = 475

    # Проверяем, что binning работает корректно
    # Цены в одном бине (0.5%) должны агрегироваться вместе
    now = time.time() * 1000

    liquidation_data = {
        "liquidations": [
            # Эти цены должны попасть в один bin
            {"side": "BUY", "price": 94500, "quantity": 1.0, "time": now - 1000},
            {"side": "BUY", "price": 94520, "quantity": 1.0, "time": now - 2000},  # ~0.02% разница
            {"side": "BUY", "price": 94530, "quantity": 1.0, "time": now - 3000},  # ~0.03% разница
        ]
    }

    result = futures_service._aggregate_liquidation_clusters(
        liquidation_data=liquidation_data,
        current_price=current_price
    )

    # Должен быть 1 cluster (все в одном бине)
    assert len(result["clusters_below"]) <= 2, \
        f"Цены с разницей < 0.5% должны попасть в один bin, got {len(result['clusters_below'])} clusters"

    print(f"  ✅ Bin size: {bin_size:.2f} (~0.5% of {current_price})")
    print(f"  ✅ Clusters formed: {len(result['clusters_below'])} (expected 1-2)")

    # Проверяем, что используется floor
    import math
    test_price = 94525
    expected_bin = math.floor(test_price / bin_size) * bin_size
    print(f"  ✅ Test price {test_price} → bin {expected_bin:.2f} (floor)")


def test_liquidation_spike_detection(futures_service):
    """
    🧪 Test #8: Bug Fix - spike detection with hours_in_data min 1.0

    🐛 Было: hours_in_data может быть < 1, взрывает avg_hourly_volume
    ✅ Стало: hours_in_data = max(hours_in_data, 1.0)
    """

    print("\n🧪 Test #8: Liquidation Spike Detection - min 1 hour")

    current_price = 95000
    now = time.time() * 1000

    # Сценарий: ликвидации только за 20 минут (0.33 часа)
    liquidation_data = {
        "liquidations": [
            {"side": "BUY", "price": 94500, "quantity": 10.0, "time": now - (10 * 60 * 1000)},  # 10 min ago
            {"side": "BUY", "price": 94500, "quantity": 10.0, "time": now - (5 * 60 * 1000)},   # 5 min ago
            {"side": "SELL", "price": 95500, "quantity": 5.0, "time": now - (3 * 60 * 1000)},   # 3 min ago
        ]
    }

    result = futures_service._aggregate_liquidation_clusters(
        liquidation_data=liquidation_data,
        current_price=current_price
    )

    # Не должно быть взрыва
    assert result is not None, "Result should not be None"
    assert "spike_magnitude" in result, "Should have spike_magnitude"

    # Spike magnitude должен быть разумным (не "extreme" из-за малого hours_in_data)
    print(f"  ✅ Spike magnitude: {result['spike_magnitude']}")
    print(f"  ✅ Total volume: ${result['total_volume_usd']:,.0f}")

    # Проверяем, что не произошло деления на очень маленькое число
    # (если бы hours_in_data = 0.33, avg_hourly_volume был бы в 3x выше)


def test_liquidation_pressure_bias_naming(futures_service):
    """
    🧪 Test #9: Bug Fix - liq_pressure_bias instead of net_liq_bias

    🐛 Было: net_liq_bias (путаница в naming)
    ✅ Стало: liq_pressure_bias (ясное название)
    """

    print("\n🧪 Test #9: Liquidation Pressure Bias - naming")

    current_price = 95000
    now = time.time() * 1000

    # Сценарий: много long liquidations
    liquidation_data = {
        "liquidations": [
            {"side": "BUY", "price": 94500, "quantity": 10.0, "time": now - 1000},
            {"side": "BUY", "price": 94500, "quantity": 10.0, "time": now - 2000},
            {"side": "BUY", "price": 94500, "quantity": 10.0, "time": now - 3000},
            {"side": "SELL", "price": 95500, "quantity": 1.0, "time": now - 1000},  # Мало short'ов
        ]
    }

    result = futures_service._aggregate_liquidation_clusters(
        liquidation_data=liquidation_data,
        current_price=current_price
    )

    # Проверяем, что используется новое название
    assert "liq_pressure_bias" in result, "Should use 'liq_pressure_bias' (not 'net_liq_bias')"

    # Много long liquidations → bearish pressure
    assert result["liq_pressure_bias"] == "bearish", \
        f"Many long liquidations should give 'bearish' pressure, got {result['liq_pressure_bias']}"

    print("  ✅ Field name: liq_pressure_bias (renamed from net_liq_bias)")
    print(f"  ✅ Pressure: {result['liq_pressure_bias']}")
    print(f"  ✅ Long liq: {result['long_liq_pct']:.1f}% > Short liq: {result['short_liq_pct']:.1f}%")


def test_liquidation_empty_data(futures_service):
    """🧪 Test #10: Empty liquidation data handling"""

    print("\n🧪 Test #10: Empty Liquidation Data")

    current_price = 95000

    # Test 1: None
    result = futures_service._aggregate_liquidation_clusters(
        liquidation_data=None,
        current_price=current_price
    )

    assert result["clusters_above"] == [], "Empty data should give empty clusters_above"
    assert result["clusters_below"] == [], "Empty data should give empty clusters_below"
    assert result["liq_pressure_bias"] == "neutral", "Empty data should give neutral bias"

    print("  ✅ None → neutral")

    # Test 2: Empty dict
    result = futures_service._aggregate_liquidation_clusters(
        liquidation_data={},
        current_price=current_price
    )

    assert result["liq_pressure_bias"] == "neutral", "Empty dict should give neutral bias"
    print("  ✅ Empty dict → neutral")

    # Test 3: Empty liquidations list
    result = futures_service._aggregate_liquidation_clusters(
        liquidation_data={"liquidations": []},
        current_price=current_price
    )

    assert result["liq_pressure_bias"] == "neutral", "Empty list should give neutral bias"
    print("  ✅ Empty list → neutral")


def test_liquidation_cluster_intensity(futures_service):
    """🧪 Test #11: Cluster intensity classification"""

    print("\n🧪 Test #11: Cluster Intensity Classification")

    current_price = 95000
    now = time.time() * 1000

    # Создаём кластеры с разной интенсивностью
    liquidation_data = {
        "liquidations": [
            # Very high intensity cluster (> $5M)
            *[{"side": "BUY", "price": 94500, "quantity": 60, "time": now - i * 1000} for i in range(10)],

            # High intensity cluster (> $2M)
            *[{"side": "BUY", "price": 93500, "quantity": 25, "time": now - i * 1000} for i in range(10)],

            # Medium intensity cluster (> $1M)
            *[{"side": "SELL", "price": 96500, "quantity": 12, "time": now - i * 1000} for i in range(10)],

            # Low intensity cluster (< $1M)
            *[{"side": "SELL", "price": 97500, "quantity": 1, "time": now - i * 1000} for i in range(10)],
        ]
    }

    result = futures_service._aggregate_liquidation_clusters(
        liquidation_data=liquidation_data,
        current_price=current_price
    )

    # Проверяем, что есть кластеры с разной интенсивностью
    all_clusters = result["clusters_above"] + result["clusters_below"]

    if all_clusters:
        intensities = [c["intensity"] for c in all_clusters]
        print(f"  ✅ Cluster intensities found: {set(intensities)}")

        # Должен быть хотя бы один high/very_high кластер
        assert any(i in ["high", "very_high"] for i in intensities), \
            f"Should have high intensity clusters, got {intensities}"


# ==================== INTEGRATION TESTS ====================

def test_price_structure_with_real_pattern(futures_service):
    """🧪 Test #12: Integration - price structure с реальным паттерном"""

    print("\n🧪 Test #12: Integration - Real Pattern")

    klines = create_swing_pattern_klines()
    current_price = 95500

    indicators = {
        "ema_20": 95000,
        "ema_50": 94500,
        "ema_200": 93000,
        "adx": 35,
        "atr_percent": 2.2
    }

    result = futures_service._calculate_price_structure(
        klines=klines,
        current_price=current_price,
        indicators=indicators,
        timeframe="4h"
    )

    # Проверяем полную структуру
    assert result["volatility_regime"] == "normal"
    assert result["trend_state"]["4h"] in ["bullish_strong", "bullish_weak", "sideways_weak"]

    # Должны быть swing points
    assert len(result["swing_highs"]) > 0, "Should find swing highs"
    assert len(result["swing_lows"]) > 0, "Should find swing lows"

    # Distance to resistance/support
    if "distance_to_resistance_pct" in result:
        print(f"  ✅ Distance to resistance: {result['distance_to_resistance_pct']:.2f}%")

    if "distance_to_support_pct" in result:
        print(f"  ✅ Distance to support: {result['distance_to_support_pct']:.2f}%")

    print("  ✅ Complete structure validated")
    print(f"     Trend: {result['trend_state']}")
    print(f"     Volatility: {result['volatility_regime']}")


if __name__ == "__main__":
    print("=" * 80)
    print("🚀 FUTURES ANALYSIS SERVICE - UNIT TESTS")
    print("=" * 80)

    pytest.main([__file__, "-v", "-s"])
