"""
Analytics API Endpoints
Provides detailed cryptocurrency analytics for Mini App
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from datetime import datetime

from src.database.models import User
from src.database.engine import get_session
from src.api.auth import get_current_user
from src.services.binance_service import BinanceService
from src.services.coingecko_service import CoinGeckoService
from src.services.technical_indicators import TechnicalIndicators

# Create router
router = APIRouter(prefix="/analytics", tags=["analytics"])

# Initialize services
binance_service = BinanceService()
coingecko_service = CoinGeckoService()


@router.get("/{symbol}")
async def get_symbol_analytics(
    symbol: str,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get comprehensive analytics for cryptocurrency symbol

    Args:
        symbol: Cryptocurrency symbol (e.g., BTC, ETH, SOL)

    Returns:
        {
            "symbol": "BTC",
            "price": 45230.50,
            "change_24h": 2.4,
            "change_7d": 5.2,
            "volume_24h": 28500000000,
            "market_cap": 880000000000,
            "indicators": {
                "rsi": 65.4,
                "macd": {...},
                "moving_averages": {...}
            }
        }
    """
    try:
        # Normalize symbol to uppercase
        symbol_upper = symbol.upper()

        # Map common symbols to trading pairs
        symbol_map = {
            "BTC": "BTCUSDT",
            "ETH": "ETHUSDT",
            "SOL": "SOLUSDT",
            "BNB": "BNBUSDT",
            "ADA": "ADAUSDT",
            "AVAX": "AVAXUSDT",
            "MATIC": "MATICUSDT",
            "DOT": "DOTUSDT",
            "LINK": "LINKUSDT",
            "UNI": "UNIUSDT",
        }

        trading_pair = symbol_map.get(symbol_upper, f"{symbol_upper}USDT")

        # Get current price from Binance
        current_price = await binance_service.get_symbol_price(trading_pair)

        # Get 24h ticker stats
        ticker_24h = await binance_service.get_24h_ticker(trading_pair)

        # Get candlestick data for technical indicators
        klines = await binance_service.get_klines(
            symbol=trading_pair,
            interval="1h",
            limit=100
        )

        # Calculate technical indicators if we have data
        indicators = {}
        if klines and len(klines) > 0:
            # Extract close prices
            closes = [float(k[4]) for k in klines]

            # Calculate indicators
            tech_indicators = TechnicalIndicators(closes)

            # RSI
            rsi_values = tech_indicators.rsi(period=14)
            if rsi_values and len(rsi_values) > 0:
                indicators["rsi"] = round(rsi_values[-1], 2)

            # MACD
            macd_result = tech_indicators.macd()
            if macd_result:
                macd_line, signal_line, histogram = macd_result
                if len(macd_line) > 0:
                    indicators["macd"] = {
                        "macd": round(macd_line[-1], 2),
                        "signal": round(signal_line[-1], 2),
                        "histogram": round(histogram[-1], 2)
                    }

            # Moving Averages
            ma_20 = tech_indicators.sma(period=20)
            ma_50 = tech_indicators.sma(period=50)

            if ma_20 and len(ma_20) > 0:
                indicators["ma_20"] = round(ma_20[-1], 2)
            if ma_50 and len(ma_50) > 0:
                indicators["ma_50"] = round(ma_50[-1], 2)

        # Build response
        return {
            "symbol": symbol_upper,
            "price": current_price or 0,
            "change_24h": round(float(ticker_24h.get("priceChangePercent", 0)), 2) if ticker_24h else 0,
            "volume_24h": float(ticker_24h.get("volume", 0)) if ticker_24h else 0,
            "high_24h": float(ticker_24h.get("highPrice", 0)) if ticker_24h else 0,
            "low_24h": float(ticker_24h.get("lowPrice", 0)) if ticker_24h else 0,
            "indicators": indicators,
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch analytics for {symbol}: {str(e)}"
        )


@router.get("/{symbol}/chart")
async def get_symbol_chart(
    symbol: str,
    interval: str = "1h",
    limit: int = 24,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get candlestick chart data for symbol

    Args:
        symbol: Cryptocurrency symbol (e.g., BTC, ETH)
        interval: Candlestick interval (1m, 5m, 15m, 1h, 4h, 1d)
        limit: Number of candlesticks (max 1000)

    Returns:
        {
            "symbol": "BTC",
            "interval": "1h",
            "data": [
                {
                    "time": 1234567890000,
                    "open": 45000,
                    "high": 45500,
                    "low": 44800,
                    "close": 45230,
                    "volume": 1500
                },
                ...
            ]
        }
    """
    try:
        symbol_upper = symbol.upper()
        symbol_map = {
            "BTC": "BTCUSDT",
            "ETH": "ETHUSDT",
            "SOL": "SOLUSDT",
            "BNB": "BNBUSDT",
            "ADA": "ADAUSDT",
            "AVAX": "AVAXUSDT",
            "MATIC": "MATICUSDT",
        }

        trading_pair = symbol_map.get(symbol_upper, f"{symbol_upper}USDT")

        # Get candlestick data
        klines = await binance_service.get_klines(
            symbol=trading_pair,
            interval=interval,
            limit=min(limit, 1000)  # Cap at 1000
        )

        # Format data
        chart_data = []
        if klines:
            for k in klines:
                chart_data.append({
                    "time": k[0],  # Open time
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5])
                })

        return {
            "symbol": symbol_upper,
            "interval": interval,
            "data": chart_data,
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch chart data for {symbol}: {str(e)}"
        )
