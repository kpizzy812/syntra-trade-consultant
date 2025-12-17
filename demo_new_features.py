# coding: utf-8
"""
Demo script for new analytics features

Demonstrates:
1. Binance Funding Rates (sentiment indicator)
2. Rainbow Chart (cycle analysis)
3. CoinMetrics On-Chain metrics (network health)

Run: python demo_new_features.py
"""

import asyncio
from datetime import datetime

from src.services.binance_service import BinanceService
from src.services.cycle_analysis_service import CycleAnalysisService
from src.services.coinmetrics_service import CoinMetricsService

# Setup logging with loguru
from loguru import logger
import sys

# Configure loguru for demo (simple console output)
logger.remove()  # Remove default handler
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


async def demo_funding_rates():
    """Demo: Binance Funding Rates"""
    print("\n" + "="*80)
    print("🎯 DEMO 1: Binance Funding Rates (Trader Sentiment)")
    print("="*80)

    binance = BinanceService()

    # Get latest funding rate for BTC
    funding = await binance.get_latest_funding_rate("BTCUSDT")

    if funding:
        print(f"\n💰 Symbol: {funding['symbol']}")
        print(f"📊 Funding Rate: {funding['funding_rate_pct']:.4f}%")
        print(f"🎭 Sentiment: {funding['sentiment']}")
        print(f"⏰ Time: {funding['funding_time']}")

        if funding['funding_rate'] > 0:
            print(f"\n📌 Interpretation: Longs paying shorts → Bullish market sentiment")
        else:
            print(f"\n📌 Interpretation: Shorts paying longs → Bearish market sentiment")

        # Get Open Interest
        oi = await binance.get_open_interest("BTCUSDT")
        if oi:
            print(f"\n📈 Open Interest: {oi['open_interest']:,.2f} BTC")
    else:
        print("❌ Could not fetch funding rate data")


async def demo_rainbow_chart():
    """Demo: Bitcoin Rainbow Chart"""
    print("\n" + "="*80)
    print("🌈 DEMO 2: Bitcoin Rainbow Chart (Cycle Analysis)")
    print("="*80)

    cycle_service = CycleAnalysisService()

    # Use current BTC price (example: $94,000)
    current_price = 94000

    # Get Rainbow Chart data
    rainbow_data = cycle_service.get_rainbow_chart_data(current_price)

    print(f"\n💰 Current BTC Price: ${rainbow_data['current_price']:,.0f}")
    print(f"📅 Days since genesis: {rainbow_data['days_since_genesis']}")
    print(f"\n🌈 Current Band: {rainbow_data['current_band'].replace('_', ' ').title()}")
    print(f"💭 Market Sentiment: {rainbow_data['sentiment'].replace('_', ' ').title()}")

    print(f"\n📊 Key Price Levels:")
    bands = rainbow_data['bands']
    print(f"   🔴 Maximum Bubble: ${bands['maximum_bubble']:,.0f}")
    print(f"   🟠 Sell Zone: ${bands['sell']:,.0f}")
    print(f"   🟡 FOMO Zone: ${bands['fomo_intensifies']:,.0f}")
    print(f"   🔵 HODL (Fair Value): ${bands['hodl']:,.0f}")
    print(f"   🟢 Buy Zone: ${bands['buy']:,.0f}")
    print(f"   🟢 Fire Sale: ${bands['basically_a_fire_sale']:,.0f}")

    # Interpretation
    print(f"\n📌 Interpretation:")
    if rainbow_data['current_band'] in ['buy', 'accumulate', 'basically_a_fire_sale']:
        print("   → Good buying opportunity! Price in accumulation zone.")
    elif rainbow_data['current_band'] == 'hodl':
        print("   → Fair value. Good time to hold and wait.")
    elif rainbow_data['current_band'] in ['sell', 'maximum_bubble']:
        print("   → Caution! Price near cycle top. Consider taking profits.")


async def demo_onchain_metrics():
    """Demo: CoinMetrics On-Chain Analysis"""
    print("\n" + "="*80)
    print("📊 DEMO 3: CoinMetrics On-Chain Metrics (Network Health)")
    print("="*80)

    coinmetrics = CoinMetricsService()

    # Get Bitcoin network health
    health = await coinmetrics.get_network_health("bitcoin")

    if health:
        print(f"\n🪙 Asset: {health['asset'].upper()}")
        print(f"📅 Date: {health['timestamp']}")
        print(f"\n📊 Network Metrics:")
        print(f"   👥 Active Addresses (24h): {health['active_addresses']:,.0f}")
        print(f"   💸 Transactions (24h): {health['transaction_count']:,.0f}")

        if 'hash_rate' in health:
            eh_rate = health['hash_rate'] / 1e18
            print(f"   ⚡ Hash Rate: {eh_rate:.2f} EH/s")

        print(f"\n📌 Interpretation:")
        print(f"   → Active addresses show network adoption and usage")
        print(f"   → High transaction count indicates active network")
        print(f"   → Hash rate reflects network security (PoW chains)")
    else:
        print("❌ Could not fetch on-chain data")

    # Get Exchange Flows
    print(f"\n🔄 Exchange Flows Analysis:")
    flows = await coinmetrics.get_exchange_flows("bitcoin")

    if flows:
        print(f"   📥 Inflow: {flows['inflow']:,.2f} BTC")
        print(f"   📤 Outflow: {flows['outflow']:,.2f} BTC")
        print(f"   📊 Net Flow: {flows['net_flow']:,.2f} BTC")

        if flows['net_flow'] > 0:
            print(f"   🐻 Bearish Signal: Coins moving TO exchanges (potential selling)")
        else:
            print(f"   🐂 Bullish Signal: Coins moving FROM exchanges (accumulation)")
    else:
        print("   ❌ Exchange flow data not available")


async def main():
    """Run all demos"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║              🚀 SYNTRA TRADE CONSULTANT - NEW FEATURES DEMO 🚀              ║
║                                                                              ║
║  Demonstrating new FREE analytics capabilities:                             ║
║  • Funding Rates (Binance Futures)                                          ║
║  • Rainbow Chart (Bitcoin Cycle Analysis)                                   ║
║  • On-Chain Metrics (CoinMetrics Community)                                 ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    try:
        # Demo 1: Funding Rates
        await demo_funding_rates()

        # Demo 2: Rainbow Chart
        await demo_rainbow_chart()

        # Demo 3: On-Chain Metrics
        await demo_onchain_metrics()

        print("\n" + "="*80)
        print("✅ All demos completed successfully!")
        print("="*80)

        print("""
📚 Next Steps:
1. Integrate these features into bot handlers
2. Add commands: /funding, /rainbow, /onchain
3. Combine multiple indicators for comprehensive analysis
4. Store historical data for trend analysis
        """)

    except Exception as e:
        logger.exception(f"Error in demo: {e}")
        print(f"\n❌ Demo error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
