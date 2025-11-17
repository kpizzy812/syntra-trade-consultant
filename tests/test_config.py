"""
Unit tests for configuration
"""

import os
import pytest


def test_config_loading():
    """Test that configuration loads correctly"""
    from config.config import (
        REQUEST_LIMIT_PER_DAY,
        CACHE_TTL_COINGECKO,
        CACHE_TTL_CRYPTOPANIC,
        SKIP_SUBSCRIPTION_CHECK,
        ModelConfig,
        Pricing,
    )

    # Test default values
    assert REQUEST_LIMIT_PER_DAY == 5
    assert CACHE_TTL_COINGECKO == 60
    assert CACHE_TTL_CRYPTOPANIC == 86400  # 24 hours in seconds
    assert SKIP_SUBSCRIPTION_CHECK is False  # default is False

    # Test model config
    assert ModelConfig.GPT_4O == "gpt-4o"
    assert ModelConfig.GPT_4O_MINI == "gpt-4o-mini"
    assert ModelConfig.MODEL_ROUTING_THRESHOLD == 1500  # Updated threshold

    # Test pricing (updated Jan 2025)
    assert Pricing.GPT_4O_INPUT == 2.50  # Updated pricing
    assert Pricing.GPT_4O_OUTPUT == 10.0
    assert Pricing.GPT_4O_MINI_INPUT == 0.15
    assert Pricing.GPT_4O_MINI_OUTPUT == 0.60


def test_skip_subscription_check_parsing():
    """Test SKIP_SUBSCRIPTION_CHECK parsing"""
    # Test that it parses 'true' correctly
    os.environ["SKIP_SUBSCRIPTION_CHECK"] = "true"
    from importlib import reload
    import config.config as cfg

    reload(cfg)
    assert cfg.SKIP_SUBSCRIPTION_CHECK is True

    # Test that it parses 'false' correctly
    os.environ["SKIP_SUBSCRIPTION_CHECK"] = "false"
    reload(cfg)
    assert cfg.SKIP_SUBSCRIPTION_CHECK is False

    # Test default (unset)
    if "SKIP_SUBSCRIPTION_CHECK" in os.environ:
        del os.environ["SKIP_SUBSCRIPTION_CHECK"]
    reload(cfg)
    assert cfg.SKIP_SUBSCRIPTION_CHECK is False
