#!/usr/bin/env python
# coding: utf-8
"""
Simple test for crypto tools - no database required
"""
import asyncio
import sys
import json
sys.path.insert(0, '.')


async def test_all_tools():
    """Test all crypto tools directly"""
    from src.services.crypto_tools import execute_tool

    print("=" * 70)
    print("🧪 Testing All Crypto Tools")
    print("=" * 70)

    tests = [
        {
            "name": "get_crypto_price",
            "args": {"coin_id": "bitcoin"},
            "description": "Get Bitcoin price"
        },
        {
            "name": "get_technical_analysis",
            "args": {"coin_id": "bitcoin", "timeframe": "4h"},
            "description": "Get Bitcoin technical analysis (4h)"
        },
        {
            "name": "get_crypto_news",
            "args": {"coin_symbol": "BTC", "limit": 3},
            "description": "Get Bitcoin news"
        },
        {
            "name": "compare_cryptos",
            "args": {"coin_ids": ["bitcoin", "ethereum"]},
            "description": "Compare Bitcoin and Ethereum"
        },
        {
            "name": "get_top_cryptos",
            "args": {"limit": 5},
            "description": "Get top 5 cryptocurrencies"
        },
        {
            "name": "get_market_overview",
            "args": {},
            "description": "Get market overview"
        }
    ]

    for i, test in enumerate(tests, 1):
        print(f"\n{'='*70}")
        print(f"Test {i}/{len(tests)}: {test['description']}")
        print(f"Tool: {test['name']}")
        print(f"Args: {test['args']}")
        print(f"{'='*70}\n")

        try:
            result_json = await execute_tool(test['name'], test['args'])
            result = json.loads(result_json)

            if result.get("success"):
                print("✅ SUCCESS!\n")

                # Pretty print relevant data based on tool
                if test['name'] == "get_crypto_price":
                    print(f"  💰 Price: ${result.get('price_usd', 0):,.2f}")
                    print(f"  📊 24h Change: {result.get('change_24h_percent', 0):+.2f}%")
                    print(f"  💎 Market Cap: ${result.get('market_cap_usd', 0):,.0f}")

                elif test['name'] == "get_technical_analysis":
                    print(f"  Coin: {result.get('coin_id')}")
                    print(f"  Timeframe: {result.get('timeframe')}")
                    print(f"  Data sources: {', '.join(result.get('data_sources', []))}")

                    if result.get('extended_data', {}).get('ath'):
                        print(f"  ATH: ${result['extended_data']['ath']:,.2f}")

                    if result.get('fear_greed', {}).get('value'):
                        fg = result['fear_greed']
                        print(f"  Fear & Greed: {fg['value']}/100 ({fg.get('value_classification')})")

                    if result.get('technical_indicators', {}).get('rsi'):
                        ind = result['technical_indicators']
                        print(f"  RSI: {ind['rsi']} ({ind.get('rsi_signal')})")

                    if result.get('candlestick_patterns', {}).get('patterns_found'):
                        patterns = result['candlestick_patterns']['patterns_found']
                        if patterns:
                            print(f"  Patterns: {', '.join(patterns)}")

                elif test['name'] == "get_crypto_news":
                    news_count = result.get('count', 0)
                    print(f"  📰 Found {news_count} news articles")
                    if news_count > 0:
                        for idx, item in enumerate(result.get('news', [])[:3], 1):
                            print(f"    {idx}. {item.get('title', 'No title')[:60]}...")

                elif test['name'] == "compare_cryptos":
                    coins = result.get('coins', [])
                    print(f"  Comparing {len(coins)} coins:\n")
                    for coin in coins:
                        print(f"  {coin.get('symbol')}: ${coin.get('price_usd', 0):,.2f} ({coin.get('change_24h_percent', 0):+.2f}%)")

                elif test['name'] == "get_top_cryptos":
                    coins = result.get('coins', [])
                    print(f"  Top {len(coins)} coins by market cap:\n")
                    for idx, coin in enumerate(coins, 1):
                        print(f"  {idx}. {coin.get('name')} ({coin.get('symbol')}): ${coin.get('price_usd', 0):,.2f}")

                elif test['name'] == "get_market_overview":
                    news_count = result.get('news_count', 0)
                    print(f"  📰 {news_count} trending news items")

            else:
                print(f"❌ FAILED: {result.get('error', 'Unknown error')}")

        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()

        print()

    print("=" * 70)
    print("✅ All Tool Tests Completed!")
    print("=" * 70)


if __name__ == '__main__':
    asyncio.run(test_all_tools())
