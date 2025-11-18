"""
Configuration module for Syntra Trade Consultant Bot

Loads configuration from environment variables using python-dotenv
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Load .env file (override=True ensures .env has priority over shell environment)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)


# Telegram Bot Configuration
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
REQUIRED_CHANNEL: str = os.getenv("REQUIRED_CHANNEL", "")
ADMIN_IDS: List[int] = [
    int(admin_id.strip())
    for admin_id in os.getenv("ADMIN_IDS", "").split(",")
    if admin_id.strip()
]

# Database Configuration
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://syntra:password@localhost:5432/syntra_bot"
)

# OpenAI API (includes Vision)
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# CoinGecko API
COINGECKO_API_KEY: str = os.getenv("COINGECKO_API_KEY", "")

# CoinMarketCap API
COINMARKETCAP_API_KEY: str = os.getenv("COINMARKETCAP_API_KEY", "")

# CryptoPanic API
CRYPTOPANIC_TOKEN: str = os.getenv("CRYPTOPANIC_TOKEN", "")

# Bot Configuration
REQUEST_LIMIT_PER_DAY: int = int(os.getenv("REQUEST_LIMIT_PER_DAY", "5"))
CACHE_TTL_COINGECKO: int = int(os.getenv("CACHE_TTL_COINGECKO", "60"))
CACHE_TTL_CRYPTOPANIC: int = int(os.getenv("CACHE_TTL_CRYPTOPANIC", "300"))

# Subscription Check
# In development: set to 'true' to skip subscription checks when bot is not channel admin
# In production: MUST be 'false' or unset (default) for security
SKIP_SUBSCRIPTION_CHECK: bool = (
    os.getenv("SKIP_SUBSCRIPTION_CHECK", "false").lower() == "true"
)

# Environment
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Mini App URL
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "http://localhost:3000")

# Optional: Redis
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Optional: Sentry
SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")

# OpenAI Optimizations
# Prompt Caching: OpenAI автоматически кеширует system prompts >1024 токенов
# Экономия ~50% на input tokens (наш system prompt: RU=1466, EN=1114 токенов)
ENABLE_PROMPT_CACHING: bool = (
    os.getenv("ENABLE_PROMPT_CACHING", "true").lower() == "true"
)


# Validation
def validate_config() -> bool:
    """Validate required configuration variables"""
    errors = []

    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is required")

    if not DATABASE_URL:
        errors.append("DATABASE_URL is required")

    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY is required")

    # Optional for now (features not implemented yet)
    # if not CRYPTOPANIC_TOKEN:
    #     errors.append('CRYPTOPANIC_TOKEN is required')

    if not REQUIRED_CHANNEL:
        errors.append("REQUIRED_CHANNEL is required")

    if not ADMIN_IDS:
        errors.append("ADMIN_IDS is required (at least one admin)")

    if errors:
        error_message = "\n".join(f"  - {error}" for error in errors)
        raise ValueError(
            f"Configuration validation failed:\n{error_message}\n\n"
            "Please check your .env file and ensure all required variables are set."
        )

    return True


# Model configuration
class ModelConfig:
    """Configuration for AI models"""

    # OpenAI models
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"

    # Token thresholds for model routing
    # If total tokens in prompt > threshold, use GPT-4O, else use GPT-4O-MINI
    # Optimized: raised from 500 to 1500 for 25-35% cost savings
    MODEL_ROUTING_THRESHOLD = 1500

    # Token limits
    # Raised to 1500 to allow full analysis + personality without cutoff
    # 1000 was cutting off catchphrases and sarcasm at the end
    MAX_TOKENS_RESPONSE = 1500
    MAX_TOKENS_VISION = 1500

    # Temperature
    # Raised to 0.85 for better personality and creative sarcasm
    # 0.7 was too conservative for Syntra's character
    DEFAULT_TEMPERATURE = 0.85

    # Vision settings
    VISION_DETAIL_LEVEL = "high"  # 'low', 'high', or 'auto'
    VISION_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


# API Rate Limits
class RateLimits:
    """Rate limits for external APIs"""

    # CoinGecko (free tier)
    COINGECKO_CALLS_PER_MINUTE = 10

    # OpenAI (depends on tier, these are conservative estimates)
    OPENAI_RPM = 500  # requests per minute
    OPENAI_TPM = 500_000  # tokens per minute


# Pricing (for cost tracking)
class Pricing:
    """Pricing for API calls (per 1M tokens)"""

    # OpenAI Text models (updated Jan 2025)
    GPT_4O_INPUT = 2.50  # $ per 1M tokens (updated from 3.0)
    GPT_4O_OUTPUT = 10.0  # $ per 1M tokens
    GPT_4O_MINI_INPUT = 0.15  # $ per 1M tokens
    GPT_4O_MINI_OUTPUT = 0.60  # $ per 1M tokens

    # OpenAI Vision (same as GPT-4O, but includes image tokens)
    GPT_4O_VISION_INPUT = 2.50  # $ per 1M tokens (updated from 3.0)
    GPT_4O_VISION_OUTPUT = 10.0  # $ per 1M tokens


if __name__ == "__main__":
    # Test configuration loading
    print("Configuration loaded successfully!")
    print(f"Environment: {ENVIRONMENT}")
    print(f"Log Level: {LOG_LEVEL}")
    print(f"Database: {DATABASE_URL[:30]}...")  # Don't print full URL
    print(f"Bot Token: {BOT_TOKEN[:10]}..." if BOT_TOKEN else "Not set")
    print(f"OpenAI Key: {OPENAI_API_KEY[:10]}..." if OPENAI_API_KEY else "Not set")
    print(f"Required Channel: {REQUIRED_CHANNEL}")
    print(f"Admin IDs: {ADMIN_IDS}")
    print(f"Request Limit: {REQUEST_LIMIT_PER_DAY}/day")

    try:
        validate_config()
        print("\n✅ Configuration validation passed!")
    except ValueError as e:
        print(f"\n❌ {e}")
