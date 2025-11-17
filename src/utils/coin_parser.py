# coding: utf-8
"""
Utility for parsing and normalizing cryptocurrency names
"""
from typing import Optional, List
import re


# Mapping of common coin names/symbols to CoinGecko IDs
COIN_ID_MAPPING = {
    # Major coins
    "btc": "bitcoin",
    "bitcoin": "bitcoin",
    "биткоин": "bitcoin",
    "битка": "bitcoin",
    "eth": "ethereum",
    "ethereum": "ethereum",
    "ether": "ethereum",
    "эфир": "ethereum",
    "эфириум": "ethereum",
    "usdt": "tether",
    "tether": "tether",
    "usdc": "usd-coin",
    "bnb": "binancecoin",
    "binance": "binancecoin",
    "xrp": "ripple",
    "ripple": "ripple",
    "ada": "cardano",
    "cardano": "cardano",
    "sol": "solana",
    "solana": "solana",
    "солана": "solana",
    "doge": "dogecoin",
    "dogecoin": "dogecoin",
    "доге": "dogecoin",
    "dot": "polkadot",
    "polkadot": "polkadot",
    "matic": "matic-network",
    "polygon": "matic-network",
    "avax": "avalanche-2",
    "avalanche": "avalanche-2",
    "link": "chainlink",
    "chainlink": "chainlink",
    "atom": "cosmos",
    "cosmos": "cosmos",
    "ltc": "litecoin",
    "litecoin": "litecoin",
    "bch": "bitcoin-cash",
    "bitcoincash": "bitcoin-cash",
    "near": "near",
    "uni": "uniswap",
    "uniswap": "uniswap",
    "xlm": "stellar",
    "stellar": "stellar",
    "etc": "ethereum-classic",
    "trx": "tron",
    "tron": "tron",
    "algo": "algorand",
    "algorand": "algorand",
    "apt": "aptos",
    "aptos": "aptos",
    "arb": "arbitrum",
    "arbitrum": "arbitrum",
    "op": "optimism",
    "optimism": "optimism",
    "sui": "sui",
    "ton": "the-open-network",
    "toncoin": "the-open-network",
    "icp": "internet-computer",
    "fil": "filecoin",
    "filecoin": "filecoin",
    "shib": "shiba-inu",
    "shiba": "shiba-inu",
}


def normalize_coin_name(coin_name: str) -> Optional[str]:
    """
    Normalize coin name to CoinGecko ID

    Args:
        coin_name: Coin name or symbol (e.g., "BTC", "Bitcoin", "btc/usd")

    Returns:
        CoinGecko ID or None if not found
    """
    if not coin_name:
        return None

    # Clean the input
    coin_name = coin_name.lower().strip()

    # Remove common suffixes (USD, USDT, BTC pairs)
    coin_name = re.sub(
        r"[/\-_\s]+(usd|usdt|btc|eth|eur|perp|perpetual).*$", "", coin_name
    )

    # Remove special characters but keep Cyrillic (а-яА-Я)
    coin_name = re.sub(r"[^a-z0-9а-я]", "", coin_name)

    # Direct lookup
    if coin_name in COIN_ID_MAPPING:
        return COIN_ID_MAPPING[coin_name]

    # Try with common suffixes removed
    for suffix in ["usd", "usdt", "btc", "perp"]:
        if coin_name.endswith(suffix):
            base = coin_name[: -len(suffix)]
            if base in COIN_ID_MAPPING:
                return COIN_ID_MAPPING[base]

    return None


def extract_coin_from_text(text: str) -> List[str]:
    """
    Extract potential coin names from text

    Args:
        text: Text that may contain coin names

    Returns:
        List of potential CoinGecko IDs
    """
    if not text:
        return []

    text_lower = text.lower()
    found_coins = []

    # Look for exact matches of known coins
    for key, coin_id in COIN_ID_MAPPING.items():
        # Match whole words only
        pattern = r"\b" + re.escape(key) + r"\b"
        if re.search(pattern, text_lower):
            if coin_id not in found_coins:
                found_coins.append(coin_id)

    return found_coins


def format_coin_name(coin_id: str) -> str:
    """
    Format CoinGecko ID to readable name

    Args:
        coin_id: CoinGecko ID (e.g., "bitcoin")

    Returns:
        Formatted name (e.g., "Bitcoin (BTC)")
    """
    # Reverse lookup for symbol
    symbol = None
    for key, value in COIN_ID_MAPPING.items():
        if value == coin_id and len(key) <= 5 and key.upper() == key or len(key) <= 4:
            symbol = key.upper()
            break

    # Format name
    name = coin_id.replace("-", " ").title()

    if symbol:
        return f"{name} ({symbol})"
    return name


if __name__ == "__main__":
    # Tests
    print("Coin Parser Tests:\n")

    test_cases = [
        "BTC",
        "BTCUSDT",
        "Bitcoin",
        "btc/usd",
        "ETHUSDT",
        "Ethereum",
        "SOLUSDT PERP",
        "dogecoin",
    ]

    for test in test_cases:
        result = normalize_coin_name(test)
        print(f"{test:20} → {result}")

    print("\n\nText extraction test:")
    text = "Looking at BTCUSDT and ETHUSDT charts, Bitcoin is bullish"
    coins = extract_coin_from_text(text)
    print(f"Text: {text}")
    print(f"Found coins: {coins}")
