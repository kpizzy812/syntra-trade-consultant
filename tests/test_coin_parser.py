"""
Unit tests for coin parser utilities
"""
import pytest

from src.utils.coin_parser import (
    normalize_coin_name,
    extract_coin_from_text,
    format_coin_name,
    COIN_ID_MAPPING
)


def test_normalize_coin_name_basic():
    """Test basic coin name normalization"""
    assert normalize_coin_name("BTC") == "bitcoin"
    assert normalize_coin_name("btc") == "bitcoin"
    assert normalize_coin_name("Bitcoin") == "bitcoin"
    assert normalize_coin_name("биткоин") == "bitcoin"


def test_normalize_coin_name_with_pairs():
    """Test coin name normalization with trading pairs"""
    # Should strip USD/USDT/BTC pairs
    assert normalize_coin_name("BTCUSDT") == "bitcoin"
    assert normalize_coin_name("BTC/USD") == "bitcoin"
    assert normalize_coin_name("ETH-USDT") == "ethereum"
    assert normalize_coin_name("btc/usd") == "bitcoin"


def test_normalize_coin_name_ethereum():
    """Test Ethereum name normalization"""
    assert normalize_coin_name("ETH") == "ethereum"
    assert normalize_coin_name("Ethereum") == "ethereum"
    assert normalize_coin_name("ETHUSDT") == "ethereum"
    assert normalize_coin_name("эфир") == "ethereum"


def test_normalize_coin_name_altcoins():
    """Test altcoin name normalization"""
    assert normalize_coin_name("SOL") == "solana"
    assert normalize_coin_name("SOLUSDT") == "solana"
    assert normalize_coin_name("DOGE") == "dogecoin"
    assert normalize_coin_name("ADA") == "cardano"
    assert normalize_coin_name("XRP") == "ripple"


def test_normalize_coin_name_perpetual():
    """Test normalization with perpetual futures"""
    assert normalize_coin_name("SOLUSDT PERP") == "solana"
    assert normalize_coin_name("BTCPERP") == "bitcoin"
    assert normalize_coin_name("ETH-PERPETUAL") == "ethereum"


def test_normalize_coin_name_empty_input():
    """Test normalization with empty input"""
    assert normalize_coin_name("") is None
    assert normalize_coin_name(None) is None


def test_normalize_coin_name_unknown():
    """Test normalization with unknown coin"""
    assert normalize_coin_name("UNKNOWNCOIN123") is None
    assert normalize_coin_name("XYZ") is None


def test_extract_coin_from_text_single():
    """Test extracting single coin from text"""
    text = "What's the price of Bitcoin today?"
    coins = extract_coin_from_text(text)
    assert "bitcoin" in coins


def test_extract_coin_from_text_multiple():
    """Test extracting multiple coins from text"""
    text = "Looking at BTC and ETH price, Bitcoin is bullish"
    coins = extract_coin_from_text(text)

    assert "bitcoin" in coins
    assert "ethereum" in coins


def test_extract_coin_from_text_russian():
    """Test extracting coins from Russian text"""
    text = "Биткоин растёт, а эфир падает"
    coins = extract_coin_from_text(text)

    assert "bitcoin" in coins
    assert "ethereum" in coins


def test_extract_coin_from_text_symbols():
    """Test extracting coins by symbols"""
    text = "BTC and ETH are the top coins"
    coins = extract_coin_from_text(text)

    assert "bitcoin" in coins
    assert "ethereum" in coins


def test_extract_coin_from_text_no_duplicates():
    """Test that extracted coins have no duplicates"""
    text = "BTC Bitcoin btc bitcoin BTC"
    coins = extract_coin_from_text(text)

    # Should only have one entry for bitcoin
    assert coins.count("bitcoin") == 1


def test_extract_coin_from_text_empty():
    """Test extraction from empty text"""
    assert extract_coin_from_text("") == []
    assert extract_coin_from_text(None) == []


def test_extract_coin_from_text_no_coins():
    """Test extraction when no coins mentioned"""
    text = "This text has no cryptocurrency mentions"
    coins = extract_coin_from_text(text)
    assert coins == []


def test_format_coin_name():
    """Test coin name formatting"""
    # Bitcoin should format nicely
    result = format_coin_name("bitcoin")
    assert "Bitcoin" in result

    # Test with hyphenated names
    result = format_coin_name("ethereum-classic")
    assert "Ethereum Classic" in result or "Ethereum-Classic" in result


def test_format_coin_name_with_symbol():
    """Test coin name formatting with symbol"""
    result = format_coin_name("bitcoin")
    # Should contain Bitcoin and potentially BTC
    assert "Bitcoin" in result


def test_coin_id_mapping_completeness():
    """Test that COIN_ID_MAPPING has expected coins"""
    # Major coins should be present
    assert "btc" in COIN_ID_MAPPING
    assert "eth" in COIN_ID_MAPPING
    assert "sol" in COIN_ID_MAPPING
    assert "doge" in COIN_ID_MAPPING

    # Should have Russian translations
    assert "биткоин" in COIN_ID_MAPPING
    assert "эфир" in COIN_ID_MAPPING


def test_normalize_coin_name_case_insensitive():
    """Test that normalization is case insensitive"""
    assert normalize_coin_name("BTC") == normalize_coin_name("btc")
    assert normalize_coin_name("Bitcoin") == normalize_coin_name("BITCOIN")
    assert normalize_coin_name("ETH") == normalize_coin_name("eth")
