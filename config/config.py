"""
Configuration module for Syntra Trade Consultant Bot

Loads configuration from environment variables using python-dotenv
"""

import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load .env file (override=True ensures .env has priority over shell environment)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)


# Telegram Bot Configuration
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "SyntraAI_bot")
REQUIRED_CHANNEL: str = os.getenv("REQUIRED_CHANNEL", "")
ADMIN_IDS: List[int] = [
    int(admin_id.strip())
    for admin_id in os.getenv("ADMIN_IDS", "").split(",")
    if admin_id.strip()
]

# Official Channel ID for auto-repost feature
# Can be username (@channel_name) or numeric ID (-1001234567890)
OFFICIAL_CHANNEL_ID: Optional[int] = None
_channel_id = os.getenv("OFFICIAL_CHANNEL_ID", "")
if _channel_id:
    try:
        OFFICIAL_CHANNEL_ID = int(_channel_id)
    except ValueError:
        pass  # Keep as None if not a valid number

# Legal Documents URLs (Telegraph articles)
# Terms of Service
TERMS_OF_SERVICE_URL_RU: str = os.getenv(
    "TERMS_OF_SERVICE_URL_RU", "https://telegra.ph/Pravila-ispolzovaniya-Syntra-AI-RU"
)
TERMS_OF_SERVICE_URL_EN: str = os.getenv(
    "TERMS_OF_SERVICE_URL_EN", "https://telegra.ph/Terms-of-Service-Syntra-AI-EN"
)

# Privacy Policy
PRIVACY_POLICY_URL_RU: str = os.getenv(
    "PRIVACY_POLICY_URL_RU", "https://telegra.ph/Politika-konfidencialnosti-Syntra-AI-RU"
)
PRIVACY_POLICY_URL_EN: str = os.getenv(
    "PRIVACY_POLICY_URL_EN", "https://telegra.ph/Privacy-Policy-Syntra-AI-EN"
)

# Database Configuration
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://syntra:password@localhost:5432/syntra_bot"
)

# AI API Keys (both providers initialized, selection is dynamic based on user tier)
# OpenAI API (GPT-4o, GPT-4o-mini, Vision)
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# =============================================================================
# MULTI-MODEL CONFIGURATION
# =============================================================================
# Heavy model for scenario generation (deep analysis, best reasoning)
MODEL_SCENARIO_GENERATOR: str = os.getenv("MODEL_SCENARIO_GENERATOR", "gpt-5.2")

# Fast model for validation, supervisor, quick decisions
MODEL_FAST: str = os.getenv("MODEL_FAST", "gpt-5-mini")

# Legacy (for backwards compatibility with chat/general use)
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", MODEL_FAST)

# DeepSeek API
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

# CoinGecko API
COINGECKO_API_KEY: str = os.getenv("COINGECKO_API_KEY", "")

# CoinMarketCap API
COINMARKETCAP_API_KEY: str = os.getenv("COINMARKETCAP_API_KEY", "")

# CryptoPanic API
CRYPTOPANIC_TOKEN: str = os.getenv("CRYPTOPANIC_TOKEN", "")

# Binance API
BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")

# Trading Bot API Key (for protecting futures endpoints)
TRADING_BOT_API_KEY: str = os.getenv("TRADING_BOT_API_KEY", "")

# Bot Configuration
REQUEST_LIMIT_PER_DAY: int = int(os.getenv("REQUEST_LIMIT_PER_DAY", "5"))
CACHE_TTL_COINGECKO: int = int(os.getenv("CACHE_TTL_COINGECKO", "60"))
# CryptoPanic: ОЧЕНЬ жесткие лимиты (~3 запроса/день), кеш на 8 часов
CACHE_TTL_CRYPTOPANIC: int = int(os.getenv("CACHE_TTL_CRYPTOPANIC", "28800"))

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

# API Base URL (for serving static files like screenshots)
API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")

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

    # OpenAI models (Standard tier pricing)
    GPT_5_1 = "gpt-5.1"              # Latest flagship model (2025)
    GPT_5_MINI = "gpt-5-mini"        # Economical GPT-5 variant
    GPT_4O = "gpt-4o"                # Previous flagship
    GPT_4O_MINI = "gpt-4o-mini"      # Economical GPT-4o

    # OpenAI Reasoning models
    O4_MINI = "o4-mini"              # UltraThink: Reasoning model
    O3_MINI = "o3-mini"              # Alternative reasoning model

    # DeepSeek models
    DEEPSEEK_CHAT = "deepseek-chat"          # Main model (fast, cheap)
    DEEPSEEK_REASONER = "deepseek-reasoner"  # Thinking Mode (reasoning)

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

    # ⚠️ DEPRECATED: Use config/limits.py and config/model_router.py instead
    # Model selection is now tier-based, not global
    # These methods are kept for backward compatibility only


# API Rate Limits
class RateLimits:
    """Rate limits for external APIs"""

    # CoinGecko rate limits (updated Jan 2025)
    # Public API (no key, no registration): 5-15 calls/min (unstable, shared)
    # Demo API (free registration): 30 calls/min, 10k calls/month, requires free API key
    # Pro API (paid): 500+ calls/min
    # По умолчанию 25 calls/min для Demo API (оставляет буфер 5 запросов)
    COINGECKO_CALLS_PER_MINUTE = int(os.getenv("COINGECKO_RATE_LIMIT", "25"))

    # OpenAI (depends on tier, these are conservative estimates)
    OPENAI_RPM = 500  # requests per minute
    OPENAI_TPM = 500_000  # tokens per minute


# Resend Email Service (for Magic Link authentication)
RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL: str = os.getenv("RESEND_FROM_EMAIL", "noreply@syntratrade.xyz")
RESEND_FROM_NAME: str = os.getenv("RESEND_FROM_NAME", "Syntra AI")

# NextAuth JWT Secret (must match frontend)
NEXTAUTH_SECRET: str = os.getenv("NEXTAUTH_SECRET", "your-nextauth-secret-here")


# Pricing (for cost tracking)
class Pricing:
    """Pricing for API calls (per 1M tokens) - Standard Tier, updated Nov 2025"""

    # GPT-5 models (2025 flagship)
    GPT_5_1_INPUT = 1.25  # $ per 1M tokens
    GPT_5_1_INPUT_CACHED = 0.125  # $ per 1M tokens (90% cheaper!)
    GPT_5_1_OUTPUT = 10.0  # $ per 1M tokens

    GPT_5_MINI_INPUT = 0.25  # $ per 1M tokens
    GPT_5_MINI_INPUT_CACHED = 0.025  # $ per 1M tokens
    GPT_5_MINI_OUTPUT = 2.0  # $ per 1M tokens

    # GPT-4o models (legacy, but still good)
    GPT_4O_INPUT = 2.50  # $ per 1M tokens
    GPT_4O_INPUT_CACHED = 1.25  # $ per 1M tokens
    GPT_4O_OUTPUT = 10.0  # $ per 1M tokens

    GPT_4O_MINI_INPUT = 0.15  # $ per 1M tokens
    GPT_4O_MINI_INPUT_CACHED = 0.075  # $ per 1M tokens
    GPT_4O_MINI_OUTPUT = 0.60  # $ per 1M tokens

    # Reasoning models (UltraThink)
    O4_MINI_INPUT = 1.10  # $ per 1M tokens
    O4_MINI_INPUT_CACHED = 0.275  # $ per 1M tokens
    O4_MINI_OUTPUT = 4.40  # $ per 1M tokens

    O3_MINI_INPUT = 1.10  # $ per 1M tokens
    O3_MINI_INPUT_CACHED = 0.55  # $ per 1M tokens
    O3_MINI_OUTPUT = 4.40  # $ per 1M tokens

    # OpenAI Vision (same as GPT-4o/GPT-5.1)
    GPT_4O_VISION_INPUT = 2.50  # $ per 1M tokens
    GPT_4O_VISION_OUTPUT = 10.0  # $ per 1M tokens

    # DeepSeek models (super cheap!)
    # Both deepseek-chat and deepseek-reasoner use same pricing
    DEEPSEEK_INPUT = 0.28  # $ per 1M tokens (cache miss)
    DEEPSEEK_INPUT_CACHED = 0.028  # $ per 1M tokens (cache hit) - 10x cheaper!
    DEEPSEEK_OUTPUT = 0.42  # $ per 1M tokens

    # Cost comparison (input/output):
    # DeepSeek ($0.28/$0.42) - CHEAPEST ⭐
    # GPT-4o-mini ($0.15/$0.60)
    # GPT-5-mini ($0.25/$2.00)
    # o4-mini ($1.10/$4.40) - UltraThink reasoning
    # GPT-5.1 ($1.25/$10.00) - Latest flagship
    # GPT-4o ($2.50/$10.00)


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
