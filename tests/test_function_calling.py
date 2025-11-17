#!/usr/bin/env python
# coding: utf-8
"""
Integration test for OpenAI Function Calling with Crypto Tools

Tests the complete flow:
1. User asks about a cryptocurrency
2. AI decides to call get_technical_analysis tool
3. Tool executes and returns data
4. AI uses the data to generate a response
"""
import asyncio
import sys

sys.path.insert(0, ".")

from src.services.openai_service import OpenAIService
from src.database.engine import async_session
from src.database.models import User
from sqlalchemy import select


async def get_or_create_test_user(session):
    """Get or create test user"""
    result = await session.execute(select(User).where(User.telegram_id == 999999999))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            telegram_id=999999999,
            username="test_user",
            first_name="Test",
            language="ru",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return user


async def test_function_calling():
    """Test OpenAI Function Calling integration"""
    print("=" * 70)
    print("🧪 Testing OpenAI Function Calling Integration")
    print("=" * 70)

    openai_service = OpenAIService()

    # Test queries
    test_queries = [
        {
            "query": "Проанализируй Bitcoin, дай полный технический анализ",
            "description": "Should trigger get_technical_analysis tool",
        },
        {
            "query": "Сравни Bitcoin и Ethereum",
            "description": "Should trigger compare_cryptos tool",
        },
        {
            "query": "Какая цена у Solana?",
            "description": "Should trigger get_crypto_price tool",
        },
    ]

    async with async_session() as session:
        # Get or create test user
        user = await get_or_create_test_user(session)
        print(f"\n✅ Test user created/retrieved: ID={user.id}\n")

        for i, test in enumerate(test_queries, 1):
            print(f"\n{'='*70}")
            print(f"Test {i}/{len(test_queries)}: {test['description']}")
            print(f"Query: \"{test['query']}\"")
            print(f"{'='*70}\n")

            try:
                # Stream the response
                print("🤖 Syntra's response:\n")

                full_response = ""
                async for chunk in openai_service.stream_completion(
                    session=session,
                    user_id=user.id,
                    user_message=test["query"],
                    user_language="ru",
                    use_tools=True,
                ):
                    if chunk:
                        print(chunk, end="", flush=True)
                        full_response += chunk

                print("\n")

                if full_response:
                    print(f"\n✅ Test {i} completed successfully")
                    print(f"Response length: {len(full_response)} characters\n")
                else:
                    print(f"\n❌ Test {i} failed - empty response\n")

            except Exception as e:
                print(f"\n❌ Test {i} failed with error: {e}\n")
                import traceback

                traceback.print_exc()

            # Wait between tests
            if i < len(test_queries):
                print("\n⏳ Waiting 3 seconds before next test...\n")
                await asyncio.sleep(3)

    print("\n" + "=" * 70)
    print("✅ All Function Calling Tests Completed!")
    print("=" * 70)


async def test_tool_execution_directly():
    """Test direct tool execution without OpenAI"""
    print("\n" + "=" * 70)
    print("🧪 Testing Direct Tool Execution")
    print("=" * 70 + "\n")

    from src.services.crypto_tools import execute_tool
    import json

    # Test 1: get_technical_analysis
    print("Test 1: get_technical_analysis for Bitcoin")
    print("-" * 70)
    result = await execute_tool(
        "get_technical_analysis", {"coin_id": "bitcoin", "timeframe": "4h"}
    )
    parsed = json.loads(result)

    if parsed.get("success"):
        print("✅ SUCCESS!")
        print(f"  Data sources: {', '.join(parsed.get('data_sources', []))}")

        if parsed.get("extended_data"):
            ext = parsed["extended_data"]
            print(f"\n  📊 Extended Data:")
            if ext.get("ath"):
                print(f"    ATH: ${ext['ath']:,.2f}")
            if ext.get("atl"):
                print(f"    ATL: ${ext['atl']:,.2f}")

        if parsed.get("fear_greed"):
            fg = parsed["fear_greed"]
            print(
                f"\n  😱 Fear & Greed: {fg.get('value')}/100 ({fg.get('value_classification')})"
            )

        if parsed.get("technical_indicators"):
            ind = parsed["technical_indicators"]
            print(f"\n  📈 Technical Indicators:")
            if ind.get("rsi"):
                print(f"    RSI: {ind['rsi']} ({ind.get('rsi_signal')})")
            if ind.get("macd"):
                print(f"    MACD: {ind.get('macd_crossover')}")

        if parsed.get("candlestick_patterns") and parsed["candlestick_patterns"].get(
            "patterns_found"
        ):
            patterns = parsed["candlestick_patterns"]
            print(f"\n  🕯️ Patterns: {', '.join(patterns['patterns_found'])}")
    else:
        print(f"❌ FAILED: {parsed.get('error')}")

    print("\n" + "=" * 70)
    print("✅ Direct Tool Execution Test Completed!")
    print("=" * 70)


if __name__ == "__main__":
    print("\n🚀 Starting OpenAI Function Calling Tests\n")

    # First test tools directly
    asyncio.run(test_tool_execution_directly())

    # Then test full integration with OpenAI
    print("\n\n")
    asyncio.run(test_function_calling())

    print("\n✅ All tests completed!\n")
