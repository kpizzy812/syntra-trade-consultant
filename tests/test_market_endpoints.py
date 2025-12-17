"""
Test Market API Endpoints
Tests Top Movers and Market Overview for all timeframes
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.coingecko_service import CoinGeckoService


async def test_top_movers():
    """Test top movers for all timeframes"""
    print("\n" + "="*60)
    print("Testing Top Movers API")
    print("="*60)

    service = CoinGeckoService()

    for timeframe in ["1h", "24h", "7d"]:
        print(f"\n📊 Testing timeframe: {timeframe}")
        print("-" * 60)

        try:
            # Get top coins with all price change data
            coins = await service.get_top_coins(limit=100, include_1h_7d_change=True)

            if not coins:
                print(f"❌ No data returned for {timeframe}")
                continue

            # Determine which field to check
            change_field_map = {
                "1h": "price_change_percentage_1h_in_currency",
                "24h": "price_change_percentage_24h",
                "7d": "price_change_percentage_7d_in_currency"
            }
            change_field = change_field_map[timeframe]

            # Check if the field exists in first coin
            sample_coin = coins[0]
            print(f"Sample coin: {sample_coin.get('name')}")
            print(f"Fields available: {list(sample_coin.keys())}")

            if change_field not in sample_coin:
                print(f"⚠️  WARNING: {change_field} not found in API response")
                print(f"Available fields: {list(sample_coin.keys())}")
                continue

            # Filter coins with change data
            coins_with_change = [c for c in coins if c.get(change_field) is not None]
            print(f"✅ Found {len(coins_with_change)}/{len(coins)} coins with {timeframe} change data")

            # Sort by change
            sorted_coins = sorted(coins_with_change, key=lambda x: x.get(change_field, 0), reverse=True)

            # Show top 3 gainers
            print(f"\n🔥 Top 3 Gainers ({timeframe}):")
            for i, coin in enumerate(sorted_coins[:3], 1):
                change = coin.get(change_field, 0)
                print(f"  {i}. {coin['symbol'].upper()}: {change:+.2f}%")

            # Show top 3 losers
            print(f"\n📉 Top 3 Losers ({timeframe}):")
            for i, coin in enumerate(reversed(sorted_coins[-3:]), 1):
                change = coin.get(change_field, 0)
                print(f"  {i}. {coin['symbol'].upper()}: {change:+.2f}%")

        except Exception as e:
            print(f"❌ Error testing {timeframe}: {e}")
            import traceback
            traceback.print_exc()


async def test_market_overview():
    """Test market overview endpoint"""
    print("\n" + "="*60)
    print("Testing Market Overview API")
    print("="*60)

    service = CoinGeckoService()

    try:
        # Test global market data
        global_data = await service.get_global_market_data()

        if not global_data:
            print("❌ No global market data returned")
            return

        print("\n✅ Global Market Data:")
        # CoinGeckoService.get_global_market_data() returns processed data directly
        total_market_cap = global_data.get("total_market_cap_usd", 0)
        total_volume = global_data.get("total_volume_24h_usd", 0)
        btc_dom = global_data.get("btc_dominance", 0)
        eth_dom = global_data.get("eth_dominance", 0)
        market_cap_change = global_data.get("market_cap_change_24h", 0)

        print(f"  Total Market Cap: ${total_market_cap:,.0f}")
        print(f"  24h Volume: ${total_volume:,.0f}")
        print(f"  24h Change: {market_cap_change:+.2f}%")
        print(f"  BTC Dominance: {btc_dom:.2f}%")
        print(f"  ETH Dominance: {eth_dom:.2f}%")

        if total_market_cap == 0:
            print("⚠️  WARNING: Total market cap is 0!")
        if total_volume == 0:
            print("⚠️  WARNING: Total volume is 0!")
        if btc_dom == 0:
            print("⚠️  WARNING: BTC dominance is 0!")

    except Exception as e:
        print(f"❌ Error testing market overview: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests"""
    print("\n🔍 Starting Market API Tests")
    print("This will test if the API returns correct data for all timeframes")

    await test_top_movers()
    await test_market_overview()

    print("\n" + "="*60)
    print("✅ Tests completed!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
