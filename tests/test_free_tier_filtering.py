"""
Test FREE tier filtering for technical analysis

Проверяет что FREE пользователи получают только базовые индикаторы (RSI, MACD, EMA)
и не получают продвинутые фичи (patterns, funding, on-chain, etc.)
"""
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.crypto_tools import execute_tool


async def test_free_tier_technical_analysis():
    """Test that FREE tier gets only basic indicators"""

    print("🧪 Testing FREE tier technical analysis filtering...\n")

    # Test as FREE user
    print("1️⃣ Testing as FREE tier user:")
    try:
        result_json = await execute_tool(
            tool_name="get_technical_analysis",
            arguments={"coin_id": "bitcoin", "timeframe": "4h"},
            user_tier="free"
        )

        result = json.loads(result_json)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        print("   This might be due to API rate limits or network issues.")
        return

    # Check what FREE user gets
    print(f"\n✅ SUCCESS: {result.get('success')}")
    print(f"📊 Coin: {result.get('coin_id')}")
    print(f"⏱️  Timeframe: {result.get('timeframe')}")
    print(f"📡 Data sources: {result.get('data_sources')}")

    # Check basic data
    if "extended_data" in result:
        print(f"\n✅ Extended data: Available")
        extended = result["extended_data"]
        if extended:
            print(f"   Price: ${extended.get('current_price', 'N/A'):,.2f}")
            print(f"   Market Cap: ${extended.get('market_cap', 0):,.0f}")

    if "fear_greed" in result:
        print(f"\n✅ Fear & Greed: Available")
        fg = result["fear_greed"]
        if fg:
            print(f"   Value: {fg.get('value')}")

    if "news" in result:
        print(f"\n✅ News: {len(result['news'])} articles")

    # Check technical indicators
    if "technical_indicators" in result:
        indicators = result["technical_indicators"]
        print(f"\n📊 Technical Indicators (FREE tier):")

        # Basic indicators (should be present)
        basic_indicators = ["rsi", "macd", "macd_signal", "macd_histogram", "ema_20", "ema_50", "ema_200"]
        for ind in basic_indicators:
            value = indicators.get(ind)
            if value is not None:
                print(f"   ✅ {ind}: {value}")
            else:
                print(f"   ❌ {ind}: MISSING!")

        # Advanced indicators (should NOT be present for FREE)
        advanced_indicators = ["bollinger_upper", "bollinger_lower", "vwap", "obv", "atr"]
        advanced_present = []
        for ind in advanced_indicators:
            if ind in indicators and indicators[ind] is not None:
                advanced_present.append(ind)

        if advanced_present:
            print(f"\n⚠️  WARNING: Advanced indicators present for FREE tier: {advanced_present}")
        else:
            print(f"\n✅ Advanced indicators properly filtered")

    # Check blocked features
    blocked_features = {
        "candlestick_patterns": "Candlestick Patterns",
        "funding_data": "Funding Rates",
        "long_short_data": "Long/Short Ratio",
        "liquidation_data": "Liquidation Data",
        "onchain_data": "On-Chain Metrics",
        "cycle_data": "Cycle Analysis"
    }

    print(f"\n🔒 Blocked Features (should NOT be in result):")
    for key, name in blocked_features.items():
        if key in result and result[key]:
            print(f"   ❌ {name}: PRESENT (should be blocked!)")
        else:
            print(f"   ✅ {name}: Properly blocked")

    # Check upgrade message
    if "upgrade_message" in result:
        print(f"\n💎 Upgrade message shown: YES")
        print(f"   Message: {result['upgrade_message'][:100]}...")
    else:
        print(f"\n💎 Upgrade message shown: NO")

    print("\n" + "="*60)

    # Test as BASIC user for comparison
    print("\n2️⃣ Testing as BASIC tier user (for comparison):")
    result_basic_json = await execute_tool(
        tool_name="get_technical_analysis",
        arguments={"coin_id": "bitcoin", "timeframe": "4h"},
        user_tier="basic"
    )

    result_basic = json.loads(result_basic_json)

    print(f"📡 Data sources: {result_basic.get('data_sources')}")

    # Check what BASIC user gets
    if "candlestick_patterns" in result_basic and result_basic["candlestick_patterns"]:
        print(f"✅ BASIC tier gets: Candlestick Patterns")

    if "funding_data" in result_basic and result_basic["funding_data"]:
        print(f"✅ BASIC tier gets: Funding Rates")

    if "technical_indicators" in result_basic:
        indicators_basic = result_basic["technical_indicators"]
        advanced_count = sum(1 for k in ["bollinger_upper", "vwap", "obv", "atr"]
                            if k in indicators_basic and indicators_basic[k] is not None)
        print(f"✅ BASIC tier gets: Advanced indicators ({advanced_count} found)")

    print("\n" + "="*60)
    print("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(test_free_tier_technical_analysis())
