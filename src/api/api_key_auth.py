# coding: utf-8
"""
API Key Authentication

Простая защита endpoints для трейдинг-ботов через API ключи.

Usage:
    @router.post("/protected-endpoint")
    async def protected(api_key: str = Depends(verify_api_key)):
        # Only accessible with valid API key
        pass
"""
from fastapi import Header, HTTPException, Depends
from typing import Optional

from loguru import logger
from config.config import TRADING_BOT_API_KEY


async def verify_api_key(
    x_api_key: Optional[str] = Header(None, description="API key for trading bot")
) -> str:
    """
    Verify API key from request header

    Headers:
        X-API-Key: your-secret-api-key

    Raises:
        HTTPException 401: If API key is missing or invalid

    Returns:
        API key if valid
    """
    if not x_api_key:
        logger.warning("API key missing in request")
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide X-API-Key header."
        )

    # Check if API key is configured
    if not TRADING_BOT_API_KEY:
        logger.error("TRADING_BOT_API_KEY not configured in .env")
        raise HTTPException(
            status_code=500,
            detail="API key authentication not configured"
        )

    # Verify API key
    if x_api_key != TRADING_BOT_API_KEY:
        logger.warning(f"Invalid API key attempt: {x_api_key[:8]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    logger.debug("API key verified successfully")
    return x_api_key


async def verify_api_key_optional(
    x_api_key: Optional[str] = Header(None, description="API key for trading bot (optional)")
) -> Optional[str]:
    """
    Verify API key (optional)

    Returns None if no key provided, validates if provided

    Useful for endpoints that work both with and without auth
    """
    if not x_api_key:
        return None

    # If provided, must be valid
    return await verify_api_key(x_api_key)
