"""
Unit tests for CoinGecko service
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import time

from src.services.coingecko_service import CoinGeckoService


@pytest.fixture
def coingecko_service():
    """Create CoinGecko service instance for testing"""
    service = CoinGeckoService()
    # Clear cache for each test
    service.cache.clear()
    return service


def test_get_cache_key(coingecko_service):
    """Test cache key generation"""
    endpoint = "/simple/price"
    params = {"ids": "bitcoin", "vs_currencies": "usd"}

    key = coingecko_service._get_cache_key(endpoint, params)

    assert isinstance(key, str)
    assert endpoint in key
    assert "bitcoin" in key
    assert "usd" in key


def test_get_cache_key_sorted_params(coingecko_service):
    """Test that cache keys are consistent regardless of param order"""
    endpoint = "/simple/price"
    params1 = {"ids": "bitcoin", "vs_currencies": "usd"}
    params2 = {"vs_currencies": "usd", "ids": "bitcoin"}

    key1 = coingecko_service._get_cache_key(endpoint, params1)
    key2 = coingecko_service._get_cache_key(endpoint, params2)

    # Should be identical
    assert key1 == key2


def test_cache_set_and_get(coingecko_service):
    """Test caching functionality"""
    cache_key = "test_key"
    data = {"price": 50000}

    # Set cache
    coingecko_service._set_cache(cache_key, data)

    # Get cache
    cached_data = coingecko_service._get_cached(cache_key)

    assert cached_data == data


def test_cache_expiration(coingecko_service):
    """Test that cache expires after TTL"""
    # Set very short TTL for testing
    coingecko_service.cache_ttl = 0.1  # 100ms

    cache_key = "test_key"
    data = {"price": 50000}

    # Set cache
    coingecko_service._set_cache(cache_key, data)

    # Should be in cache immediately
    assert coingecko_service._get_cached(cache_key) == data

    # Wait for expiration
    time.sleep(0.2)

    # Should be expired
    assert coingecko_service._get_cached(cache_key) is None


def test_cache_miss(coingecko_service):
    """Test cache miss returns None"""
    result = coingecko_service._get_cached("non_existent_key")
    assert result is None


@pytest.mark.asyncio
async def test_get_price_mock(coingecko_service):
    """Test get_price with mocked API response"""
    mock_response = {
        "bitcoin": {
            "usd": 50000,
            "usd_24h_change": 5.2
        }
    }

    # Mock the _make_request method
    with patch.object(coingecko_service, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response

        result = await coingecko_service.get_price("bitcoin", "usd")

        assert result == mock_response
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_get_price_with_cache(coingecko_service):
    """Test that get_price uses cache"""
    mock_response = {
        "bitcoin": {
            "usd": 50000,
            "usd_24h_change": 5.2
        }
    }

    # Manually set cache to test caching behavior (use correct parameter name!)
    cache_key = coingecko_service._get_cache_key(
        "/simple/price",
        {
            "ids": "bitcoin",
            "vs_currencies": "usd",
            "include_24hr_change": "true"  # Note: "24hr" not "24h"
        }
    )
    coingecko_service._set_cache(cache_key, mock_response)

    # This call should use cache
    result = await coingecko_service.get_price("bitcoin", "usd")
    assert result == mock_response


@pytest.mark.asyncio
async def test_make_request_success():
    """Test successful API request"""
    service = CoinGeckoService()
    service.cache.clear()  # Clear cache for clean test

    mock_response_data = {"bitcoin": {"usd": 50000}}

    # Create properly structured mock
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_response_data)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock()

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()

    with patch('aiohttp.ClientSession', return_value=mock_session):
        result = await service._make_request("/simple/price", {"ids": "bitcoin"})

        assert result == mock_response_data


@pytest.mark.asyncio
async def test_make_request_error():
    """Test API request with error response"""
    service = CoinGeckoService()

    # Create mock response with error
    mock_response = AsyncMock()
    mock_response.status = 404
    mock_response.text = AsyncMock(return_value="Not found")

    # Create mock session
    mock_session = AsyncMock()
    mock_session.get = AsyncMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response

    with patch('aiohttp.ClientSession', return_value=mock_session):
        result = await service._make_request("/simple/price", {"ids": "invalid"})

        assert result is None


def test_initialization(coingecko_service):
    """Test service initialization"""
    assert coingecko_service.BASE_URL == "https://api.coingecko.com/api/v3"
    assert isinstance(coingecko_service.cache, dict)
    assert coingecko_service.cache_ttl > 0


def test_cache_multiple_entries(coingecko_service):
    """Test caching multiple different entries"""
    # Add multiple cache entries
    coingecko_service._set_cache("key1", {"data": 1})
    coingecko_service._set_cache("key2", {"data": 2})
    coingecko_service._set_cache("key3", {"data": 3})

    # All should be retrievable
    assert coingecko_service._get_cached("key1") == {"data": 1}
    assert coingecko_service._get_cached("key2") == {"data": 2}
    assert coingecko_service._get_cached("key3") == {"data": 3}


def test_api_key_handling():
    """Test API key is properly set"""
    service = CoinGeckoService()

    # If API key is configured, it should be set
    if service.api_key:
        assert isinstance(service.api_key, str)
        assert len(service.api_key) > 0
