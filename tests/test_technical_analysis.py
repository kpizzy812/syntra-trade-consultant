# coding: utf-8
"""
Tests for new technical analysis services
"""
import pytest
import asyncio
from src.services.coingecko_service import CoinGeckoService
from src.services.binance_service import BinanceService
from src.services.fear_greed_service import FearGreedService
from src.services.technical_indicators import TechnicalIndicators
from src.services.candlestick_patterns import CandlestickPatterns


@pytest.mark.asyncio
async def test_coingecko_extended_data():
    """Test CoinGecko extended market data"""
    service = CoinGeckoService()

    # Test with Bitcoin
    data = await service.get_extended_market_data("bitcoin")

    assert data is not None, "Should return data for Bitcoin"
    assert "ath" in data, "Should include ATH"
    assert "atl" in data, "Should include ATL"
    assert "price_change_7d" in data, "Should include 7d price change"
    assert "total_supply" in data, "Should include total supply"
    assert "circulating_supply" in data, "Should include circulating supply"
    assert "volume_to_market_cap" in data, "Should include volume/market cap ratio"

    print(f"\n✅ CoinGecko Extended Data Test PASSED")
    print(f"  ATH: ${data['ath']:,.2f}" if data["ath"] else "  ATH: N/A")
    print(f"  ATL: ${data['atl']:,.2f}" if data["atl"] else "  ATL: N/A")
    print(
        f"  7d Change: {data['price_change_7d']:.2f}%"
        if data["price_change_7d"]
        else "  7d Change: N/A"
    )
    print(
        f"  Circulating Supply: {data['circulating_supply']:,.0f}"
        if data["circulating_supply"]
        else "  Circulating Supply: N/A"
    )


@pytest.mark.asyncio
async def test_fear_greed_index():
    """Test Fear & Greed Index"""
    service = FearGreedService()

    data = await service.get_current()

    assert data is not None, "Should return Fear & Greed data"
    assert "value" in data, "Should include value"
    assert "value_classification" in data, "Should include classification"
    assert "emoji" in data, "Should include emoji"

    assert 0 <= data["value"] <= 100, "Value should be between 0 and 100"

    print(f"\n✅ Fear & Greed Index Test PASSED")
    print(f"  Value: {data['value']}/100")
    print(f"  Classification: {data['value_classification']}")
    print(f"  {data['emoji']}")


@pytest.mark.asyncio
async def test_binance_klines():
    """Test Binance klines (candlestick data)"""
    service = BinanceService()

    # Test with Bitcoin
    df = await service.get_klines_by_coin_id("bitcoin", interval="1h", limit=50)

    assert df is not None, "Should return DataFrame for Bitcoin"
    assert len(df) > 0, "DataFrame should have data"
    assert "open" in df.columns, "Should have 'open' column"
    assert "high" in df.columns, "Should have 'high' column"
    assert "low" in df.columns, "Should have 'low' column"
    assert "close" in df.columns, "Should have 'close' column"
    assert "volume" in df.columns, "Should have 'volume' column"

    print(f"\n✅ Binance Klines Test PASSED")
    print(f"  Fetched {len(df)} candlesticks")
    print(f"  Latest Close: ${df['close'].iloc[-1]:,.2f}")
    print(f"  Latest Volume: {df['volume'].iloc[-1]:,.2f}")


@pytest.mark.asyncio
async def test_technical_indicators():
    """Test technical indicators calculation"""
    service = BinanceService()
    indicators_service = TechnicalIndicators()

    # Get klines data
    df = await service.get_klines_by_coin_id("bitcoin", interval="4h", limit=200)

    assert df is not None, "Should get klines data"

    # Calculate indicators
    indicators = indicators_service.calculate_all_indicators(df)

    assert indicators is not None, "Should return indicators"
    assert "rsi" in indicators, "Should include RSI"
    assert "macd" in indicators, "Should include MACD"
    assert "ema_20" in indicators, "Should include EMA 20"
    assert "bb_upper" in indicators, "Should include Bollinger Bands"

    print(f"\n✅ Technical Indicators Test PASSED")
    print(
        f"  RSI: {indicators['rsi']:.2f} ({indicators.get('rsi_signal', 'N/A')})"
        if indicators.get("rsi")
        else "  RSI: N/A"
    )
    print(
        f"  MACD: {indicators.get('macd_crossover', 'N/A')}"
        if indicators.get("macd")
        else "  MACD: N/A"
    )
    print(
        f"  EMA 20: ${indicators['ema_20']:,.2f}"
        if indicators.get("ema_20")
        else "  EMA 20: N/A"
    )
    print(
        f"  BB Position: {indicators.get('bb_position', 'N/A')}"
        if indicators.get("bb_upper")
        else "  BB Position: N/A"
    )


@pytest.mark.asyncio
async def test_candlestick_patterns():
    """Test candlestick pattern detection"""
    service = BinanceService()
    patterns_service = CandlestickPatterns()

    # Get klines data
    df = await service.get_klines_by_coin_id("bitcoin", interval="1d", limit=10)

    assert df is not None, "Should get klines data"

    # Detect patterns
    patterns = patterns_service.detect_all_patterns(df)

    assert patterns is not None, "Should return patterns dict"
    assert "patterns_found" in patterns, "Should include patterns_found list"
    assert "pattern_signal" in patterns, "Should include pattern_signal"

    print(f"\n✅ Candlestick Patterns Test PASSED")
    if patterns.get("patterns_found"):
        print(f"  Detected patterns: {', '.join(patterns['patterns_found'])}")
        print(f"  Signal: {patterns.get('pattern_signal', 'N/A')}")
    else:
        print(f"  No patterns detected (this is normal)")


@pytest.mark.asyncio
async def test_full_technical_analysis():
    """Test complete technical analysis integration"""
    from src.services.crypto_tools import get_technical_analysis

    # Test with Bitcoin
    result = await get_technical_analysis("bitcoin", timeframe="4h")

    assert result is not None, "Should return result"
    assert result.get(
        "success"
    ), f"Should be successful, but got error: {result.get('error')}"
    assert "extended_data" in result, "Should include extended_data"
    assert "fear_greed" in result, "Should include fear_greed"
    assert "technical_indicators" in result, "Should include technical_indicators"
    assert "candlestick_patterns" in result, "Should include candlestick_patterns"
    assert "data_sources" in result, "Should include data_sources"

    print(f"\n✅ Full Technical Analysis Test PASSED")
    print(f"  Coin: {result['coin_id']}")
    print(f"  Timeframe: {result['timeframe']}")
    print(f"  Data sources: {', '.join(result['data_sources'])}")

    # Check extended data
    if result["extended_data"]:
        print(f"\n  📊 Extended Data:")
        ext = result["extended_data"]
        if ext.get("ath"):
            print(f"    ATH: ${ext['ath']:,.2f}")
        if ext.get("price_change_7d"):
            print(f"    7d Change: {ext['price_change_7d']:.2f}%")

    # Check Fear & Greed
    if result["fear_greed"]:
        fg = result["fear_greed"]
        print(
            f"\n  😱 Fear & Greed: {fg.get('value')}/100 ({fg.get('value_classification')})"
        )

    # Check indicators
    if result["technical_indicators"]:
        ind = result["technical_indicators"]
        print(f"\n  📈 Technical Indicators:")
        if ind.get("rsi"):
            print(f"    RSI: {ind['rsi']:.2f} ({ind.get('rsi_signal')})")
        if ind.get("macd"):
            print(f"    MACD: {ind.get('macd_crossover')}")

    # Check patterns
    if result["candlestick_patterns"] and result["candlestick_patterns"].get(
        "patterns_found"
    ):
        patterns = result["candlestick_patterns"]
        print(f"\n  🕯️ Patterns: {', '.join(patterns['patterns_found'])}")


if __name__ == "__main__":
    """Run tests manually"""
    print("=" * 60)
    print("🧪 Testing New Technical Analysis Services")
    print("=" * 60)

    asyncio.run(test_coingecko_extended_data())
    asyncio.run(test_fear_greed_index())
    asyncio.run(test_binance_klines())
    asyncio.run(test_technical_indicators())
    asyncio.run(test_candlestick_patterns())
    asyncio.run(test_full_technical_analysis())

    print("\n" + "=" * 60)
    print("✅ All Tests Completed!")
    print("=" * 60)
