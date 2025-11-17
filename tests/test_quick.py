#!/usr/bin/env python
# coding: utf-8
"""Quick test for new services"""
import asyncio
import sys

sys.path.insert(0, ".")

from src.services.fear_greed_service import FearGreedService


async def test_fear_greed():
    print("Testing Fear & Greed Index...")
    service = FearGreedService()
    data = await service.get_current()

    if data:
        print(f"✅ SUCCESS!")
        print(f"  Value: {data['value']}/100")
        print(f"  Classification: {data['value_classification']}")
        print(f"  {data['emoji']}")
    else:
        print("❌ FAILED")


if __name__ == "__main__":
    asyncio.run(test_fear_greed())
