# coding: utf-8
"""
Utility for calculating vision tokens for OpenAI Vision API

Based on OpenAI's token calculation formula:
https://platform.openai.com/docs/guides/vision
"""
import math
from typing import Tuple
from PIL import Image
from io import BytesIO


def calculate_image_tokens(image_bytes: bytes, detail: str = "high") -> int:
    """
    Calculate token cost for an image based on OpenAI's formula

    Args:
        image_bytes: Image file content as bytes
        detail: "low", "high", or "auto"

    Returns:
        Number of tokens the image will consume

    Formula:
        - Low detail: 85 tokens (fixed)
        - High detail: 85 + (170 * number_of_tiles)
          where tiles are 512x512 chunks after scaling to max 2048x2048
    """
    if detail == "low":
        return 85

    # Load image to get dimensions
    try:
        image = Image.open(BytesIO(image_bytes))
        width, height = image.size
    except Exception:
        # If we can't open image, estimate conservatively
        return 765  # Estimate for ~1024x1024 image

    if detail == "auto":
        # Auto mode uses low detail for small images
        if width <= 512 and height <= 512:
            return 85
        detail = "high"

    # High detail calculation
    return _calculate_high_detail_tokens(width, height)


def _calculate_high_detail_tokens(width: int, height: int) -> int:
    """
    Calculate tokens for high detail mode

    OpenAI's algorithm:
    1. Scale image to fit within 2048x2048 (maintain aspect ratio)
    2. Scale shortest side to 768px (maintain aspect ratio)
    3. Count how many 512px tiles needed to cover the image
    4. Each tile costs 170 tokens + 85 base tokens
    """
    # Step 1: Scale to fit within 2048x2048
    max_dim = 2048
    if width > max_dim or height > max_dim:
        scale = max_dim / max(width, height)
        width = int(width * scale)
        height = int(height * scale)

    # Step 2: Scale shortest side to 768px
    min_dim = 768
    scale = min_dim / min(width, height)
    width = int(width * scale)
    height = int(height * scale)

    # Step 3: Count tiles
    tiles_width = math.ceil(width / 512)
    tiles_height = math.ceil(height / 512)
    num_tiles = tiles_width * tiles_height

    # Step 4: Calculate tokens
    tokens = 85 + (170 * num_tiles)

    return tokens


def estimate_vision_cost(
    image_bytes: bytes,
    detail: str = "high",
    prompt_tokens: int = 100,
    response_tokens: int = 200,
) -> Tuple[int, float]:
    """
    Estimate total tokens and cost for a vision API call

    Args:
        image_bytes: Image file content
        detail: Detail level
        prompt_tokens: Estimated tokens in text prompt
        response_tokens: Estimated tokens in response

    Returns:
        Tuple of (total_input_tokens, estimated_cost_usd)
    """
    # GPT-4o pricing (per 1M tokens) - updated Jan 2025
    INPUT_PRICE = 2.50  # $2.50 per 1M input tokens (updated from 3.0)
    OUTPUT_PRICE = 10.0  # $10 per 1M output tokens

    # Calculate image tokens
    image_tokens = calculate_image_tokens(image_bytes, detail)

    # Total input tokens
    total_input_tokens = image_tokens + prompt_tokens

    # Calculate cost
    input_cost = (total_input_tokens / 1_000_000) * INPUT_PRICE
    output_cost = (response_tokens / 1_000_000) * OUTPUT_PRICE
    total_cost = input_cost + output_cost

    return total_input_tokens, total_cost


def get_optimal_detail_level(image_bytes: bytes) -> str:
    """
    Determine optimal detail level based on image size

    Returns:
        "low" for small/simple images, "high" for detailed charts
    """
    try:
        image = Image.open(BytesIO(image_bytes))
        width, height = image.size

        # Small images don't benefit from high detail
        if width <= 512 and height <= 512:
            return "low"

        # Large, detailed images need high detail
        return "high"

    except Exception:
        # Default to high for charts
        return "high"


if __name__ == "__main__":
    # Test examples
    logger.debug("Vision Token Calculator Examples:\n")

    # Example 1: Small image (low detail)
    logger.debug("512x512 image (low detail):")
    logger.debug(f"  Tokens: {calculate_image_tokens(b'', 'low')}")

    # Example 2: Common chart sizes
    test_sizes = [
        (1024, 768, "Common chart size"),
        (1920, 1080, "Full HD screenshot"),
        (2560, 1440, "2K screenshot"),
        (512, 512, "Small image"),
    ]

    for width, height, desc in test_sizes:
        tokens = _calculate_high_detail_tokens(width, height)
        cost = (tokens + 100 + 200) / 1_000_000 * (3.0 + 10.0 * 200 / (tokens + 100))
        logger.debug(f"\n{desc} ({width}x{height}):")
        logger.debug(f"  Tokens: {tokens}")
        logger.debug(f"  Est. cost per analysis: ${cost:.4f}")
