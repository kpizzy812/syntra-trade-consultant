# coding: utf-8
"""
Tests for Cycle Analysis Service

Tests Rainbow Chart calculations, Pi Cycle Top, and market cycle detection.
"""

import pytest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from src.services.cycle_analysis_service import CycleAnalysisService


class TestCycleAnalysisService:
    """Test suite for Cycle Analysis Service"""

    @pytest.fixture
    def cycle_service(self):
        """Create Cycle Analysis service instance"""
        return CycleAnalysisService()

    def test_calculate_days_since_genesis(self, cycle_service):
        """Test days calculation since Bitcoin genesis"""
        # Bitcoin genesis: 2009-01-09
        # Test date: 2025-01-09 (16 years later)
        test_date = datetime(2025, 1, 9)
        days = cycle_service.calculate_days_since_genesis(test_date)

        # Should be approximately 16 * 365 = 5840 days (+ leap years)
        assert days > 5800
        assert days < 5900

    def test_calculate_rainbow_price_center_line(self, cycle_service):
        """Test Rainbow Chart price calculation (HODL line)"""
        # Test with 5000 days since genesis
        days = 5000
        price = cycle_service.calculate_rainbow_price(days, band="hodl")

        # Price should be positive and reasonable
        assert price > 0
        assert price > 1000  # Should be above $1000
        assert price < 1000000  # Should be below $1M

    def test_calculate_rainbow_price_bands(self, cycle_service):
        """Test that rainbow bands maintain correct order"""
        days = 5000

        # Calculate all bands
        hodl_price = cycle_service.calculate_rainbow_price(days, "hodl")
        buy_price = cycle_service.calculate_rainbow_price(days, "buy")
        sell_price = cycle_service.calculate_rainbow_price(days, "sell")
        bubble_price = cycle_service.calculate_rainbow_price(days, "maximum_bubble")

        # Verify order: buy < hodl < sell < bubble
        assert buy_price < hodl_price
        assert hodl_price < sell_price
        assert sell_price < bubble_price

    def test_get_rainbow_chart_data(self, cycle_service):
        """Test complete Rainbow Chart data generation"""
        current_price = 45000
        target_date = datetime(2024, 11, 1)

        data = cycle_service.get_rainbow_chart_data(current_price, target_date)

        # Verify structure
        assert "days_since_genesis" in data
        assert "current_price" in data
        assert "bands" in data
        assert "current_band" in data
        assert "sentiment" in data

        # Verify bands dictionary
        bands = data["bands"]
        assert "hodl" in bands
        assert "buy" in bands
        assert "sell" in bands

        # Verify current price is set correctly
        assert data["current_price"] == 45000

    def test_determine_current_band(self, cycle_service):
        """Test band determination for given price"""
        days = 5000

        # Generate band prices
        bands = {
            "maximum_bubble": 100000,
            "sell": 80000,
            "hodl": 50000,
            "buy": 30000,
            "basically_a_fire_sale": 10000,
        }

        # Test different price points
        # Price at or above a band level falls into that band
        assert cycle_service.determine_current_band(90000, bands) == "sell"
        assert cycle_service.determine_current_band(55000, bands) == "hodl"
        assert cycle_service.determine_current_band(35000, bands) == "buy"
        assert cycle_service.determine_current_band(25000, bands) == "basically_a_fire_sale"
        assert cycle_service.determine_current_band(5000, bands) == "basically_a_fire_sale"

    def test_get_sentiment_from_band(self, cycle_service):
        """Test sentiment mapping from bands"""
        assert cycle_service.get_sentiment_from_band("buy") == "buy_zone"
        assert cycle_service.get_sentiment_from_band("hodl") == "fair_value"
        assert cycle_service.get_sentiment_from_band("sell") == "sell_zone"
        assert cycle_service.get_sentiment_from_band("maximum_bubble") == "extreme_greed"

    def test_calculate_pi_cycle_top_insufficient_data(self, cycle_service):
        """Test Pi Cycle with insufficient data"""
        # Create DataFrame with only 100 days
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        prices = pd.DataFrame({
            "close": np.random.uniform(40000, 50000, 100)
        }, index=dates)

        result = cycle_service.calculate_pi_cycle_top(prices)

        # Should return error
        assert "error" in result
        assert result["error"] == "insufficient_data"

    def test_calculate_pi_cycle_top_with_data(self, cycle_service):
        """Test Pi Cycle with sufficient data"""
        # Create DataFrame with 400 days of data
        dates = pd.date_range(start="2023-01-01", periods=400, freq="D")

        # Create uptrend data
        prices = pd.DataFrame({
            "close": np.linspace(30000, 50000, 400) + np.random.normal(0, 1000, 400)
        }, index=dates)

        result = cycle_service.calculate_pi_cycle_top(prices)

        # Should return valid result
        assert "ma_111" in result
        assert "ma_350_x2" in result
        assert "signal" in result
        assert "distance_to_top_pct" in result

        # Values should be reasonable
        assert result["ma_111"] > 0
        assert result["ma_350_x2"] > 0

    def test_calculate_200_week_ma_insufficient_data(self, cycle_service):
        """Test 200 Week MA with insufficient data"""
        # Create DataFrame with only 500 days (~71 weeks)
        dates = pd.date_range(start="2023-01-01", periods=500, freq="D")
        prices = pd.DataFrame({
            "close": np.random.uniform(40000, 50000, 500)
        }, index=dates)

        result = cycle_service.calculate_200_week_ma(prices)

        # Should return None
        assert result is None

    def test_calculate_200_week_ma_with_data(self, cycle_service):
        """Test 200 Week MA with sufficient data"""
        # Create DataFrame with 1500 days (~214 weeks)
        dates = pd.date_range(start="2020-01-01", periods=1500, freq="D")
        prices = pd.DataFrame({
            "close": np.linspace(10000, 50000, 1500)
        }, index=dates)

        result = cycle_service.calculate_200_week_ma(prices)

        # Should return a value
        assert result is not None
        assert result > 0
        assert result < 100000  # Reasonable range

    def test_detect_market_cycle_phase(self, cycle_service):
        """Test market cycle phase detection"""
        current_price = 45000

        # Create rainbow data (fair value)
        rainbow_data = {
            "current_band": "hodl",
            "sentiment": "fair_value"
        }

        # Create pi cycle data (bullish)
        pi_cycle_data = {
            "signal": "bullish"
        }

        # 200W MA
        ma_200w = 30000

        result = cycle_service.detect_market_cycle_phase(
            current_price, rainbow_data, pi_cycle_data, ma_200w
        )

        # Verify structure
        assert "phase" in result
        assert "confidence" in result
        assert "signals" in result
        assert "phase_scores" in result

        # Verify phase is one of expected values
        assert result["phase"] in ["accumulation", "markup", "distribution", "markdown"]

        # Verify signals list
        assert isinstance(result["signals"], list)
        assert len(result["signals"]) > 0

    def test_format_rainbow_chart(self, cycle_service):
        """Test Rainbow Chart formatting"""
        rainbow_data = {
            "current_price": 45000,
            "current_band": "hodl",
            "sentiment": "fair_value",
            "bands": {
                "hodl": 45000,
                "buy": 30000,
                "sell": 80000
            }
        }

        formatted = cycle_service.format_rainbow_chart(rainbow_data)

        # Should contain key information
        assert "Rainbow Chart" in formatted
        assert "45000" in formatted or "45,000" in formatted
        assert "hodl" in formatted.lower() or "HODL" in formatted

    def test_format_cycle_analysis(self, cycle_service):
        """Test cycle analysis formatting"""
        cycle_data = {
            "phase": "markup",
            "confidence": 3,
            "signals": [
                "Rainbow: Fair value zone",
                "Pi Cycle: Bullish"
            ]
        }
        current_price = 45000

        formatted = cycle_service.format_cycle_analysis(cycle_data, current_price)

        # Should contain key information
        assert "Market Cycle" in formatted
        assert "markup" in formatted.lower()
        assert "45000" in formatted or "45,000" in formatted
        assert "Rainbow" in formatted

    def test_rainbow_prices_increase_with_time(self, cycle_service):
        """Test that Rainbow Chart prices increase over time"""
        # Calculate prices for different time periods
        price_5000_days = cycle_service.calculate_rainbow_price(5000, "hodl")
        price_6000_days = cycle_service.calculate_rainbow_price(6000, "hodl")

        # Later date should have higher price (logarithmic growth)
        assert price_6000_days > price_5000_days
