"""
Test multi-timeframe candles loading in crypto_tools
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.crypto_tools import get_technical_analysis
from loguru import logger


async def test_multi_tf_candles():
    """Test that multi-timeframe candles are loaded correctly"""

    logger.info("=" * 80)
    logger.info("Testing multi-timeframe candles loading for BTC")
    logger.info("=" * 80)

    # Test with Bitcoin
    result = await get_technical_analysis(
        coin_id="bitcoin",
        timeframe="1d"
    )

    if not result["success"]:
        logger.error("❌ Analysis failed!")
        return False

    # Check if multi_timeframe_candles exists
    if "multi_timeframe_candles" not in result:
        logger.error("❌ multi_timeframe_candles NOT found in result!")
        logger.info(f"Available keys: {list(result.keys())}")
        return False

    mtf_candles = result["multi_timeframe_candles"]
    logger.info(f"✅ multi_timeframe_candles found with {len(mtf_candles)} timeframes")

    # Expected timeframes
    expected_tfs = ['1M', '1w', '1d', '4h', '1h']

    # Check each timeframe
    for tf in expected_tfs:
        if tf in mtf_candles:
            candles_count = mtf_candles[tf]["count"]
            logger.info(f"  ✓ {tf}: {candles_count} candles loaded")

            # Show first and last candle as sample
            if candles_count > 0:
                first_candle = mtf_candles[tf]["candles"][0]
                last_candle = mtf_candles[tf]["candles"][-1]
                logger.info(f"    First: {first_candle['timestamp']} | O:{first_candle['open']:.2f} H:{first_candle['high']:.2f} L:{first_candle['low']:.2f} C:{first_candle['close']:.2f}")
                logger.info(f"    Last:  {last_candle['timestamp']} | O:{last_candle['open']:.2f} H:{last_candle['high']:.2f} L:{last_candle['low']:.2f} C:{last_candle['close']:.2f}")
        else:
            logger.warning(f"  ✗ {tf}: NOT found in result")

    # Check data_sources
    if "multi_timeframe_candles" in result.get("data_sources", []):
        logger.info("✅ 'multi_timeframe_candles' listed in data_sources")
    else:
        logger.warning("⚠️ 'multi_timeframe_candles' NOT in data_sources")
        logger.info(f"data_sources: {result.get('data_sources', [])}")

    logger.info("=" * 80)
    logger.info("Test completed successfully!")
    logger.info("=" * 80)

    return True


if __name__ == "__main__":
    asyncio.run(test_multi_tf_candles())
