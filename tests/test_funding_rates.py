# coding: utf-8
"""
Tests for Binance Funding Rates

Tests funding rate fetching and sentiment analysis.
Note: These are integration tests that make real API calls.
"""

import pytest
import asyncio

from src.services.binance_service import BinanceService


class TestBinanceFundingRates:
    """Test suite for Binance funding rates functionality"""

    @pytest.fixture
    def binance_service(self):
        """Create Binance service instance"""
        return BinanceService()

    @pytest.mark.asyncio
    async def test_get_funding_rate(self, binance_service):
        """Test fetching funding rate history"""
        # Fetch last 10 funding rates for BTCUSDT
        df = await binance_service.get_funding_rate("BTCUSDT", limit=10)

        # Should return DataFrame
        assert df is not None
        assert len(df) > 0

        # Verify columns
        assert "symbol" in df.columns
        assert "funding_rate" in df.columns
        assert "funding_time" in df.columns

        # Verify data types
        assert df["funding_rate"].dtype == float

        # Verify reasonable values
        # Funding rates typically between -0.01 and 0.01 (-1% to 1%)
        assert df["funding_rate"].abs().max() < 0.01

    @pytest.mark.asyncio
    async def test_get_latest_funding_rate(self, binance_service):
        """Test fetching latest funding rate"""
        result = await binance_service.get_latest_funding_rate("BTCUSDT")

        # Should return dict with funding rate info
        assert result is not None
        assert "symbol" in result
        assert "funding_rate" in result
        assert "funding_rate_pct" in result
        assert "funding_time" in result
        assert "sentiment" in result

        # Verify symbol
        assert result["symbol"] == "BTCUSDT"

        # Verify sentiment is valid
        valid_sentiments = ["very_bullish", "bullish", "bearish", "very_bearish"]
        assert result["sentiment"] in valid_sentiments

        # Verify percentage calculation
        assert abs(result["funding_rate_pct"] - result["funding_rate"] * 100) < 0.0001

    @pytest.mark.asyncio
    async def test_get_open_interest(self, binance_service):
        """Test fetching open interest"""
        result = await binance_service.get_open_interest("BTCUSDT")

        # Should return dict with OI data
        assert result is not None
        assert "symbol" in result
        assert "open_interest" in result
        assert "timestamp" in result

        # Verify values
        assert result["symbol"] == "BTCUSDT"
        assert result["open_interest"] > 0  # OI should be positive

    @pytest.mark.asyncio
    async def test_format_funding_rate(self, binance_service):
        """Test funding rate formatting"""
        # Create test funding data
        funding_data = {
            "symbol": "BTCUSDT",
            "funding_rate": 0.0001,
            "funding_rate_pct": 0.01,
            "sentiment": "bullish"
        }

        formatted = await binance_service.format_funding_rate(funding_data)

        # Should contain key information
        assert "Funding Rate" in formatted
        assert "BTCUSDT" in formatted
        assert "0.01" in formatted  # Percentage
        assert "bullish" in formatted.lower()

    @pytest.mark.asyncio
    async def test_funding_rate_for_eth(self, binance_service):
        """Test funding rate for ETHUSDT"""
        result = await binance_service.get_latest_funding_rate("ETHUSDT")

        # Should work for ETH as well
        assert result is not None
        assert result["symbol"] == "ETHUSDT"
        assert "funding_rate" in result

    @pytest.mark.asyncio
    async def test_funding_rate_sentiment_logic(self, binance_service):
        """Test sentiment determination logic"""
        # Get real funding rate
        result = await binance_service.get_latest_funding_rate("BTCUSDT")

        assert result is not None

        rate = result["funding_rate"]
        sentiment = result["sentiment"]

        # Verify sentiment matches rate
        if rate > 0.0005:
            assert sentiment == "very_bullish"
        elif rate > 0:
            assert sentiment == "bullish"
        elif rate < -0.0005:
            assert sentiment == "very_bearish"
        else:
            assert sentiment == "bearish"

    @pytest.mark.asyncio
    async def test_invalid_symbol(self, binance_service):
        """Test handling of invalid symbol"""
        result = await binance_service.get_latest_funding_rate("INVALIDUSDT")

        # Should return None or handle gracefully
        assert result is None

    @pytest.mark.asyncio
    async def test_funding_rate_multiple_symbols(self, binance_service):
        """Test funding rates for multiple popular symbols"""
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

        results = await asyncio.gather(
            *[binance_service.get_latest_funding_rate(symbol) for symbol in symbols]
        )

        # All should return valid results
        for i, result in enumerate(results):
            assert result is not None
            assert result["symbol"] == symbols[i]
            assert "funding_rate" in result
