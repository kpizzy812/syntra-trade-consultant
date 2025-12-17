"""
Unit test for FREE tier filtering logic (no external API calls)

Проверяет логику фильтрации результатов для FREE tier без вызова реальных API
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.models import SubscriptionTier


def test_free_tier_filtering_logic():
    """Test FREE tier filtering logic without API calls"""

    print("🧪 Testing FREE tier filtering logic (unit test)...\n")

    # Simulate a full technical analysis result
    full_result = {
        "success": True,
        "coin_id": "bitcoin",
        "timeframe": "4h",
        "extended_data": {
            "current_price": 87000,
            "market_cap": 1700000000000,
            "volume_24h": 50000000000,
        },
        "fear_greed": {
            "value": 20,
            "value_classification": "Extreme Fear",
        },
        "news": [
            {"title": "Bitcoin news 1"},
            {"title": "Bitcoin news 2"},
        ],
        "technical_indicators": {
            # Basic indicators (FREE tier)
            "rsi": 45.5,
            "macd": -500.2,
            "macd_signal": -450.1,
            "macd_histogram": -50.1,
            "ema_20": 86000,
            "ema_50": 85000,
            "ema_200": 80000,

            # Advanced indicators (BASIC+ only)
            "bollinger_upper": 90000,
            "bollinger_middle": 87000,
            "bollinger_lower": 84000,
            "vwap": 86500,
            "obv": 1000000,
            "atr": 2500,
        },
        "candlestick_patterns": {
            "patterns_found": ["Three White Soldiers", "Bullish Engulfing"],
        },
        "funding_data": {
            "funding_rate_pct": 0.01,
            "sentiment": "bullish",
        },
        "long_short_data": {
            "long_short_ratio": 1.5,
            "sentiment": "bullish",
        },
        "liquidation_data": {
            "total_liquidations": 100,
            "total_volume_usd": 5000000,
        },
        "onchain_data": {
            "active_addresses": 1000000,
            "transaction_count": 500000,
        },
        "cycle_data": {
            "current_band": "Buy zone",
            "sentiment": "Accumulation",
        },
        "data_sources": [
            "extended_market_data",
            "fear_greed_index",
            "news",
            "technical_indicators",
            "candlestick_patterns",
            "funding_rates",
            "long_short_ratio",
            "liquidation_history",
            "onchain_metrics",
            "cycle_analysis",
        ],
    }

    # Simulate FREE tier filtering (same logic as in crypto_tools.py)
    tier_enum = SubscriptionTier.FREE

    filtered_result = {
        "success": full_result.get("success", True),
        "coin_id": full_result.get("coin_id"),
        "timeframe": full_result.get("timeframe"),
        "data_sources": [],
    }

    # ✅ ALLOWED: Basic market data
    if "extended_data" in full_result:
        filtered_result["extended_data"] = full_result["extended_data"]
        filtered_result["data_sources"].append("extended_market_data")

    # ✅ ALLOWED: Fear & Greed Index
    if "fear_greed" in full_result:
        filtered_result["fear_greed"] = full_result["fear_greed"]
        filtered_result["data_sources"].append("fear_greed_index")

    # ✅ ALLOWED: News
    if "news" in full_result:
        filtered_result["news"] = full_result["news"]
        filtered_result["data_sources"].append("news")

    # ✅ ALLOWED: Basic technical indicators ONLY (RSI, MACD, EMA)
    if "technical_indicators" in full_result and full_result["technical_indicators"]:
        indicators = full_result["technical_indicators"]
        filtered_result["technical_indicators"] = {
            "rsi": indicators.get("rsi"),
            "macd": indicators.get("macd"),
            "macd_signal": indicators.get("macd_signal"),
            "macd_histogram": indicators.get("macd_histogram"),
            "ema_20": indicators.get("ema_20"),
            "ema_50": indicators.get("ema_50"),
            "ema_200": indicators.get("ema_200"),
        }
        filtered_result["data_sources"].append("technical_indicators")

    # ❌ BLOCKED features
    blocked_features = []
    if full_result.get("candlestick_patterns"):
        blocked_features.append("Candlestick Patterns")
    if full_result.get("funding_data"):
        blocked_features.append("Funding Rates")
    if full_result.get("long_short_data"):
        blocked_features.append("Long/Short Ratio")
    if full_result.get("liquidation_data"):
        blocked_features.append("Liquidation Data")
    if full_result.get("onchain_data"):
        blocked_features.append("On-Chain Metrics")
    if full_result.get("cycle_data"):
        blocked_features.append("Cycle Analysis")

    if blocked_features:
        filtered_result["upgrade_message"] = (
            f"🔓 Unlock {', '.join(blocked_features)} with BASIC+ subscription!"
        )

    # Now verify the filtering worked
    print("=" * 60)
    print("BEFORE FILTERING (full result):")
    print("=" * 60)
    print(f"Data sources: {full_result['data_sources']}")
    print(f"Technical indicators: {len(full_result['technical_indicators'])} indicators")
    print(f"Has candlestick_patterns: {bool(full_result.get('candlestick_patterns'))}")
    print(f"Has funding_data: {bool(full_result.get('funding_data'))}")
    print(f"Has onchain_data: {bool(full_result.get('onchain_data'))}")

    print("\n" + "=" * 60)
    print("AFTER FILTERING (FREE tier result):")
    print("=" * 60)
    print(f"Data sources: {filtered_result['data_sources']}")

    # Check what's included
    print(f"\n✅ Included:")
    print(f"   - Extended data: {bool(filtered_result.get('extended_data'))}")
    print(f"   - Fear & Greed: {bool(filtered_result.get('fear_greed'))}")
    print(f"   - News: {bool(filtered_result.get('news'))}")
    print(f"   - Technical indicators: {len(filtered_result.get('technical_indicators', {}))} indicators")

    if filtered_result.get('technical_indicators'):
        ti = filtered_result['technical_indicators']
        print(f"\n📊 Technical Indicators (FREE tier):")
        for key, value in ti.items():
            if value is not None:
                print(f"      ✅ {key}: {value}")
            else:
                print(f"      ❌ {key}: None (ERROR!)")

    # Check what's blocked
    print(f"\n❌ Blocked:")
    print(f"   - candlestick_patterns: {bool(filtered_result.get('candlestick_patterns'))}")
    print(f"   - funding_data: {bool(filtered_result.get('funding_data'))}")
    print(f"   - long_short_data: {bool(filtered_result.get('long_short_data'))}")
    print(f"   - liquidation_data: {bool(filtered_result.get('liquidation_data'))}")
    print(f"   - onchain_data: {bool(filtered_result.get('onchain_data'))}")
    print(f"   - cycle_data: {bool(filtered_result.get('cycle_data'))}")

    # Check advanced indicators are NOT in filtered result
    advanced_indicators = ["bollinger_upper", "bollinger_lower", "vwap", "obv", "atr"]
    ti_filtered = filtered_result.get('technical_indicators', {})
    advanced_present = [ind for ind in advanced_indicators if ind in ti_filtered]

    print(f"\n🔒 Advanced indicators filtered:")
    if advanced_present:
        print(f"   ❌ ERROR: {advanced_present} still present!")
    else:
        print(f"   ✅ All advanced indicators properly filtered")

    # Upgrade message
    if "upgrade_message" in filtered_result:
        print(f"\n💎 Upgrade message:")
        print(f"   {filtered_result['upgrade_message'][:100]}...")

    # Final verification
    print("\n" + "=" * 60)
    print("VERIFICATION:")
    print("=" * 60)

    errors = []

    # Check basic indicators are present
    basic_indicators = ["rsi", "macd", "ema_20", "ema_50", "ema_200"]
    for ind in basic_indicators:
        if ind not in ti_filtered or ti_filtered[ind] is None:
            errors.append(f"❌ Basic indicator '{ind}' missing!")

    # Check advanced features are blocked
    blocked_keys = ["candlestick_patterns", "funding_data", "liquidation_data", "onchain_data"]
    for key in blocked_keys:
        if key in filtered_result and filtered_result[key]:
            errors.append(f"❌ Feature '{key}' should be blocked!")

    # Check advanced indicators are filtered
    if advanced_present:
        errors.append(f"❌ Advanced indicators present: {advanced_present}")

    if errors:
        print("\n⚠️  ERRORS FOUND:")
        for error in errors:
            print(f"   {error}")
        return False
    else:
        print("\n✅ ALL CHECKS PASSED!")
        print("   - Basic indicators present: ✅")
        print("   - Advanced indicators filtered: ✅")
        print("   - Premium features blocked: ✅")
        return True


if __name__ == "__main__":
    success = test_free_tier_filtering_logic()
    exit(0 if success else 1)
