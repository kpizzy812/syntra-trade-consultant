# coding: utf-8
"""
Quick integration test for new analytics in get_technical_analysis()

Tests that the function correctly integrates:
- Funding rates (Binance Futures)
- Cycle analysis (Bitcoin Rainbow Chart)
- On-chain metrics (CoinMetrics)
"""

import asyncio
import logging
from src.services.crypto_tools import get_technical_analysis

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_bitcoin_analysis():
    """Test Bitcoin analysis - should include ALL data sources"""
    print("\n" + "=" * 80)
    print("🔍 Testing Bitcoin Analysis (should include cycle data)")
    print("=" * 80)

    result = await get_technical_analysis("bitcoin", timeframe="1d")

    if result.get("success"):
        print("\n✅ Analysis successful!")
        print(f"\n📊 Data sources: {', '.join(result['data_sources'])}")

        # Check if we got new data
        if result.get("funding_data"):
            funding = result["funding_data"]
            print(f"\n💰 Funding Rate: {funding.get('funding_rate_pct', 'N/A'):.4f}%")
            print(f"   Sentiment: {funding.get('sentiment', 'N/A')}")
            if funding.get("open_interest"):
                print(f"   Open Interest: {funding['open_interest']:,.2f} BTC")

        if result.get("cycle_data"):
            cycle = result["cycle_data"]
            print(f"\n🌈 Rainbow Chart:")
            print(f"   Current Band: {cycle.get('current_band', 'N/A')}")
            print(f"   Sentiment: {cycle.get('sentiment', 'N/A')}")
            print(f"   Days since genesis: {cycle.get('days_since_genesis', 'N/A')}")

        if result.get("onchain_data"):
            onchain = result["onchain_data"]
            print(f"\n📊 On-Chain Metrics:")
            if onchain.get("active_addresses"):
                print(f"   Active Addresses: {onchain['active_addresses']:,.0f}")
            if onchain.get("transaction_count"):
                print(f"   Transactions: {onchain['transaction_count']:,.0f}")
            if onchain.get("exchange_flows"):
                flows = onchain["exchange_flows"]
                print(f"   Exchange Net Flow: {flows.get('net_flow', 'N/A'):.2f} BTC")
                print(f"   Flow Sentiment: {flows.get('sentiment', 'N/A')}")

        print(f"\n✅ Bitcoin analysis complete with {len(result['data_sources'])} data sources!")
    else:
        print(f"\n❌ Error: {result.get('error')}")


async def test_ethereum_analysis():
    """Test Ethereum analysis - should include funding + on-chain (no cycle)"""
    print("\n" + "=" * 80)
    print("🔍 Testing Ethereum Analysis (no cycle data, but funding + on-chain)")
    print("=" * 80)

    result = await get_technical_analysis("ethereum", timeframe="4h")

    if result.get("success"):
        print("\n✅ Analysis successful!")
        print(f"\n📊 Data sources: {', '.join(result['data_sources'])}")

        # Check data sources
        has_funding = "funding_rates" in result["data_sources"]
        has_onchain = "onchain_metrics" in result["data_sources"]
        has_cycle = "cycle_analysis" in result["data_sources"]

        print(f"\n📋 Data availability:")
        print(f"   Funding rates: {'✅' if has_funding else '❌'}")
        print(f"   On-chain metrics: {'✅' if has_onchain else '❌'}")
        print(f"   Cycle analysis: {'❌ (Bitcoin only)' if not has_cycle else '✅'}")

        if result.get("funding_data"):
            funding = result["funding_data"]
            print(f"\n💰 ETH Funding: {funding.get('funding_rate_pct', 'N/A'):.4f}%")

        print(f"\n✅ Ethereum analysis complete!")
    else:
        print(f"\n❌ Error: {result.get('error')}")


async def test_xrp_analysis():
    """Test XRP analysis - typical altcoin"""
    print("\n" + "=" * 80)
    print("🔍 Testing XRP Analysis")
    print("=" * 80)

    result = await get_technical_analysis("ripple", timeframe="4h")

    if result.get("success"):
        print("\n✅ Analysis successful!")
        print(f"\n📊 Data sources: {', '.join(result['data_sources'])}")

        if result.get("funding_data"):
            funding = result["funding_data"]
            print(f"\n💰 XRP Funding: {funding.get('funding_rate_pct', 'N/A'):.4f}%")
            print(f"   Sentiment: {funding.get('sentiment', 'N/A')}")

        print(f"\n✅ XRP analysis complete!")
    else:
        print(f"\n❌ Error: {result.get('error')}")


async def main():
    """Run all integration tests"""
    print(
        """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║              🧪 INTEGRATION TEST - NEW ANALYTICS SOURCES 🧪                 ║
║                                                                              ║
║  Testing that get_technical_analysis() correctly integrates:                ║
║  • Funding Rates (Binance Futures)                                          ║
║  • Rainbow Chart Cycle Analysis (Bitcoin only)                              ║
║  • On-Chain Metrics (CoinMetrics)                                           ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    )

    try:
        # Test 1: Bitcoin (should have ALL data sources)
        await test_bitcoin_analysis()

        # Test 2: Ethereum (funding + on-chain, no cycle)
        await test_ethereum_analysis()

        # Test 3: XRP (typical altcoin)
        await test_xrp_analysis()

        print("\n" + "=" * 80)
        print("✅ All integration tests completed!")
        print("=" * 80)

    except Exception as e:
        logger.exception(f"Error in integration test: {e}")
        print(f"\n❌ Test error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
