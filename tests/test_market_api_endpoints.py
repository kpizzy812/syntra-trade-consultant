"""
Test Market API Endpoints via HTTP
Tests the actual FastAPI endpoints
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx


async def test_market_overview_endpoint():
    """Test /api/market/overview endpoint"""
    print("\n" + "="*60)
    print("Testing /api/market/overview")
    print("="*60)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/api/market/overview")
            response.raise_for_status()
            data = response.json()

            print("\n✅ API Response:")
            print(f"  Fear & Greed: {data['fear_greed']['value']} - {data['fear_greed']['value_classification']}")
            print(f"  Total Market Cap: {data['global']['total_market_cap']}")
            print(f"  24h Volume: {data['global']['total_volume_24h']}")
            print(f"  Market Cap Change: {data['global']['market_cap_change_24h']:+.2f}%")
            print(f"  BTC Dominance: {data['global']['btc_dominance']:.2f}%")
            print(f"  ETH Dominance: {data['global']['eth_dominance']:.2f}%")

            # Validate no zeros
            if data['global']['btc_dominance'] == 0:
                print("⚠️  WARNING: BTC dominance is 0!")
            if data['global']['eth_dominance'] == 0:
                print("⚠️  WARNING: ETH dominance is 0!")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()


async def test_top_movers_endpoint():
    """Test /api/market/top-movers endpoint for all timeframes"""
    print("\n" + "="*60)
    print("Testing /api/market/top-movers")
    print("="*60)

    async with httpx.AsyncClient() as client:
        for timeframe in ["1h", "24h", "7d"]:
            print(f"\n📊 Timeframe: {timeframe}")
            print("-" * 60)

            try:
                response = await client.get(
                    f"http://localhost:8000/api/market/top-movers",
                    params={"timeframe": timeframe, "limit": 3}
                )
                response.raise_for_status()
                data = response.json()

                print(f"✅ Got {len(data['gainers'])} gainers and {len(data['losers'])} losers")

                # Show top 3 gainers
                print(f"\n🔥 Top 3 Gainers ({timeframe}):")
                for i, coin in enumerate(data['gainers'], 1):
                    print(f"  {i}. {coin['symbol']}: {coin['change']:+.2f}% @ {coin['price']}")

                # Show top 3 losers
                print(f"\n📉 Top 3 Losers ({timeframe}):")
                for i, coin in enumerate(data['losers'], 1):
                    print(f"  {i}. {coin['symbol']}: {coin['change']:+.2f}% @ {coin['price']}")

                # Validate data
                if len(data['gainers']) == 0:
                    print(f"⚠️  WARNING: No gainers for {timeframe}!")
                if len(data['losers']) == 0:
                    print(f"⚠️  WARNING: No losers for {timeframe}!")

            except Exception as e:
                print(f"❌ Error testing {timeframe}: {e}")
                import traceback
                traceback.print_exc()


async def main():
    """Run all API endpoint tests"""
    print("\n🌐 Testing Market API Endpoints via HTTP")
    print("Make sure the API server is running on http://localhost:8000")

    await test_market_overview_endpoint()
    await test_top_movers_endpoint()

    print("\n" + "="*60)
    print("✅ All API endpoint tests completed!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
