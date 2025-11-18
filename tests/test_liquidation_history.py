#!/usr/bin/env python3
# coding: utf-8
"""
Test Binance Liquidation History API

This script tests the liquidation data retrieval with your Binance API keys.
Requires BINANCE_API_KEY and BINANCE_API_SECRET in .env file.
"""
import asyncio
import logging
import os
from dotenv import load_dotenv
from src.services.binance_service import BinanceService

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def test_liquidation_history():
    """Test liquidation history retrieval"""
    print("=" * 80)
    print("TESTING BINANCE LIQUIDATION HISTORY API")
    print("=" * 80)

    # Check if credentials are set
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")

    if not api_key or not api_secret:
        print("\n❌ ERROR: Binance API credentials not found!")
        print("\n📝 Please add your API keys to .env file:")
        print("   BINANCE_API_KEY=your_key_here")
        print("   BINANCE_API_SECRET=your_secret_here")
        print("\n📚 See docs/BINANCE_API_SETUP.md for detailed instructions")
        return

    print(f"\n✅ API Key found: {api_key[:8]}...{api_key[-4:]}")
    print(f"✅ API Secret found: {api_secret[:8]}...{'*' * 8}")

    # Initialize service
    binance_service = BinanceService()

    if not binance_service.has_credentials:
        print("\n❌ ERROR: Credentials not loaded properly")
        return

    print("\n✅ Binance Service initialized in authenticated mode")

    # Test with Bitcoin
    symbol = "BTCUSDT"
    print(f"\n🔍 Fetching liquidation history for {symbol} (last 24 hours)...\n")

    result = await binance_service.get_liquidation_history(symbol, limit=1000)

    if not result:
        print("❌ Failed to fetch liquidation data")
        print("\n💡 Possible reasons:")
        print("   1. API keys are incorrect")
        print("   2. API keys don't have Futures Read permission")
        print("   3. Network/API connectivity issue")
        print("\n📚 Check logs above for detailed error message")
        return

    print("✅ Liquidation data retrieved successfully!")
    print("\n" + "=" * 80)
    print(f"📊 LIQUIDATION SUMMARY FOR {symbol}")
    print("=" * 80)

    total_liq = result.get("total_liquidations", 0)
    total_volume = result.get("total_volume_usd", 0)
    long_liq = result.get("long_liquidations_usd", 0)
    short_liq = result.get("short_liquidations_usd", 0)
    period_start = result.get("period_start", "N/A")
    period_end = result.get("period_end", "N/A")

    print(f"Period:                 {period_start} → {period_end}")
    print(f"Total Liquidations:     {total_liq:,} events")
    print(f"Total Volume:           ${total_volume:,.2f}")
    print()
    print(f"Long Liquidations:      ${long_liq:,.2f}", end="")
    if total_volume > 0:
        long_pct = (long_liq / total_volume) * 100
        print(f" ({long_pct:.1f}%)")
    else:
        print()

    print(f"Short Liquidations:     ${short_liq:,.2f}", end="")
    if total_volume > 0:
        short_pct = (short_liq / total_volume) * 100
        print(f" ({short_pct:.1f}%)")
    else:
        print()

    print("\n" + "=" * 80)
    print("💡 INTERPRETATION")
    print("=" * 80)

    if long_liq > short_liq:
        ratio = long_liq / short_liq if short_liq > 0 else float("inf")
        print(f"🔴 More longs liquidated (ratio: {ratio:.2f}x)")
        print("   → Indicates downward price movement / long squeeze")
        if long_pct > 70:
            print("   → STRONG bearish pressure")
    elif short_liq > long_liq:
        ratio = short_liq / long_liq if long_liq > 0 else float("inf")
        print(f"🟢 More shorts liquidated (ratio: {ratio:.2f}x)")
        print("   → Indicates upward price movement / short squeeze")
        if short_pct > 70:
            print("   → STRONG bullish pressure")
    else:
        print("🟡 Balanced liquidations")
        print("   → Mixed market conditions")

    # Severity assessment
    print()
    if total_volume > 1_000_000_000:
        print("🔥 EXTREME liquidation event (> $1B)")
    elif total_volume > 500_000_000:
        print("🟠 Major liquidation event ($500M - $1B)")
    elif total_volume > 100_000_000:
        print("🟡 Significant liquidation event ($100M - $500M)")
    elif total_volume > 10_000_000:
        print("🟢 Normal liquidation activity ($10M - $100M)")
    else:
        print("⚪ Low liquidation activity (< $10M)")

    # Show top 5 largest liquidations
    liquidations = result.get("liquidations", [])
    if liquidations:
        print("\n" + "=" * 80)
        print("🏆 TOP 5 LARGEST LIQUIDATIONS")
        print("=" * 80)

        # Sort by value
        sorted_liqs = sorted(liquidations, key=lambda x: x["value_usd"], reverse=True)[
            :5
        ]

        for i, liq in enumerate(sorted_liqs, 1):
            side_emoji = "🔴" if liq["side"] == "SELL" else "🟢"
            side_text = "LONG" if liq["side"] == "SELL" else "SHORT"
            print(
                f"{i}. {side_emoji} {side_text:5s} ${liq['value_usd']:>12,.2f}  "
                f"@ ${liq['price']:,.2f}  ({liq['time']})"
            )

    print("\n" + "=" * 80)
    print("✅ TEST COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print("\n💡 Your Binance API credentials are working correctly!")
    print("   The bot can now provide liquidation data in analysis.")


if __name__ == "__main__":
    asyncio.run(test_liquidation_history())
