# coding: utf-8
"""
CoinMetrics Community API Service

Provides FREE on-chain metrics for cryptocurrency analysis:
- Network health (active addresses, transaction count)
- Market indicators (exchange flows)
- Profitability metrics

API Documentation: https://docs.coinmetrics.io/api/v4/
Community endpoint: https://community-api.coinmetrics.io/v4
Rate limit: 10 requests per 6 seconds (1.6 RPS)
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, UTC
import aiohttp

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)


logger = logging.getLogger(__name__)


class CoinMetricsService:
    """
    Service for fetching on-chain metrics from CoinMetrics Community API

    Features:
    - FREE access to on-chain data (no API key required)
    - Network health metrics
    - Market data
    - Automatic retries on failures
    - Rate limit compliance (10 req/6sec)
    """

    BASE_URL = "https://community-api.coinmetrics.io/v4"

    # Asset mapping (CoinGecko ID -> CoinMetrics asset)
    ASSET_MAP = {
        "bitcoin": "btc",
        "ethereum": "eth",
        "solana": "sol",
        "cardano": "ada",
        "ripple": "xrp",
        "polkadot": "dot",
        "dogecoin": "doge",
        "avalanche": "avax",
        "polygon": "matic",
        "chainlink": "link",
        "litecoin": "ltc",
        "uniswap": "uni",
        "stellar": "xlm",
        "algorand": "algo",
    }

    # Popular on-chain metrics available in Community API
    POPULAR_METRICS = [
        "AdrActCnt",  # Active addresses count
        "TxCnt",  # Transaction count
        "TxTfrValAdjUSD",  # Transfer value (USD)
        "FlowOutExNtv",  # Exchange outflow (native units)
        "FlowInExNtv",  # Exchange inflow (native units)
        "HashRate",  # Network hash rate (PoW)
        "FeeTotNtv",  # Total fees (native)
        "IssueTotNtv",  # Total issuance (native)
        "SplyCur",  # Current supply
    ]

    def __init__(self):
        """Initialize CoinMetrics service"""
        pass

    def get_asset_id(self, coin_id: str) -> Optional[str]:
        """
        Convert CoinGecko ID to CoinMetrics asset ID

        Args:
            coin_id: CoinGecko ID (e.g., 'bitcoin', 'ethereum')

        Returns:
            CoinMetrics asset ID (e.g., 'btc', 'eth') or None
        """
        return self.ASSET_MAP.get(coin_id.lower())

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def get_asset_metrics(
        self,
        asset: str,
        metrics: List[str],
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        frequency: str = "1d",
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get on-chain metrics for an asset

        Args:
            asset: Asset ID (btc, eth, sol, etc.)
            metrics: List of metric names (e.g., ['AdrActCnt', 'TxCnt'])
            start_time: Start time (ISO 8601 format: 2024-01-01)
            end_time: End time (ISO 8601 format)
            frequency: Data frequency (1d, 1h, etc.)

        Returns:
            List of metric data points or None

        Example response:
        [
            {
                "time": "2024-01-01T00:00:00.000000000Z",
                "AdrActCnt": "12345",
                "TxCnt": "234567"
            }
        ]
        """
        try:
            # Default to last 30 days if no time range specified
            if not end_time:
                end_time = datetime.now(UTC).strftime("%Y-%m-%d")
            if not start_time:
                start_date = datetime.now(UTC) - timedelta(days=30)
                start_time = start_date.strftime("%Y-%m-%d")

            # Build URL
            metrics_param = ",".join(metrics)
            url = f"{self.BASE_URL}/timeseries/asset-metrics"

            params = {
                "assets": asset,
                "metrics": metrics_param,
                "frequency": frequency,
                "start_time": start_time,
                "end_time": end_time,
                "pretty": "false",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Extract data from response
                        if "data" in data and len(data["data"]) > 0:
                            metric_data = data["data"]
                            logger.info(
                                f"Fetched {len(metric_data)} data points for {asset}"
                            )
                            return metric_data
                        else:
                            logger.warning(f"No data returned for {asset}")
                            return None

                    elif response.status == 400:
                        error_data = await response.json()
                        logger.warning(
                            f"CoinMetrics API error for {asset}: {error_data}"
                        )
                        return None
                    else:
                        logger.error(f"CoinMetrics API error: {response.status}")
                        return None

        except Exception as e:
            logger.exception(f"Error fetching metrics for {asset}: {e}")
            return None

    async def get_latest_metrics(
        self, asset: str, metrics: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest on-chain metrics for an asset

        Args:
            asset: Asset ID (btc, eth, etc.)
            metrics: List of metric names

        Returns:
            Dict with latest metric values or None

        Example:
        {
            "time": "2024-11-17",
            "AdrActCnt": 950000,
            "TxCnt": 320000,
            "HashRate": 5.5e20
        }
        """
        data = await self.get_asset_metrics(
            asset=asset, metrics=metrics, frequency="1d"
        )

        if data and len(data) > 0:
            # Return the most recent data point
            latest = data[-1]

            # Convert string values to float where possible
            result = {"time": latest.get("time")}
            for metric in metrics:
                value = latest.get(metric)
                if value:
                    try:
                        result[metric] = float(value)
                    except (ValueError, TypeError):
                        result[metric] = value

            return result

        return None

    async def get_network_health(self, coin_id: str) -> Optional[Dict[str, Any]]:
        """
        Get network health metrics for a cryptocurrency

        Args:
            coin_id: CoinGecko coin ID (bitcoin, ethereum, etc.)

        Returns:
            Dict with network health indicators or None

        Metrics:
        - active_addresses: Number of active addresses (24h)
        - transaction_count: Number of transactions (24h)
        - hash_rate: Network hash rate (PoW chains)
        """
        asset = self.get_asset_id(coin_id)
        if not asset:
            logger.warning(f"Asset mapping not found for {coin_id}")
            return None

        # Select appropriate metrics based on chain type
        metrics = ["AdrActCnt", "TxCnt"]

        # Add HashRate for PoW chains
        if asset in ["btc", "ltc", "doge"]:
            metrics.append("HashRate")

        data = await self.get_latest_metrics(asset, metrics)

        if data:
            result = {
                "asset": asset,
                "timestamp": data.get("time"),
                "active_addresses": data.get("AdrActCnt"),
                "transaction_count": data.get("TxCnt"),
            }

            if "HashRate" in data:
                result["hash_rate"] = data.get("HashRate")

            return result

        return None

    async def get_exchange_flows(self, coin_id: str) -> Optional[Dict[str, Any]]:
        """
        Get exchange flow metrics (inflows/outflows)

        Positive net flow = coins moving TO exchanges (potential sell pressure)
        Negative net flow = coins moving FROM exchanges (potential accumulation)

        Args:
            coin_id: CoinGecko coin ID

        Returns:
            Dict with exchange flow data or None

        Metrics:
        - inflow: Coins flowing into exchanges
        - outflow: Coins flowing out of exchanges
        - net_flow: inflow - outflow
        """
        asset = self.get_asset_id(coin_id)
        if not asset:
            return None

        metrics = ["FlowInExNtv", "FlowOutExNtv"]
        data = await self.get_latest_metrics(asset, metrics)

        if data:
            inflow = data.get("FlowInExNtv", 0)
            outflow = data.get("FlowOutExNtv", 0)

            return {
                "asset": asset,
                "timestamp": data.get("time"),
                "inflow": inflow,
                "outflow": outflow,
                "net_flow": inflow - outflow,
                "sentiment": "bearish" if inflow > outflow else "bullish",
            }

        return None

    async def format_network_health(self, health_data: Dict[str, Any]) -> str:
        """
        Format network health data for Telegram display

        Args:
            health_data: Network health metrics dict

        Returns:
            Formatted string for Telegram
        """
        if not health_data:
            return "❌ Network health data not available"

        asset = health_data.get("asset", "").upper()
        active_addr = health_data.get("active_addresses")
        tx_count = health_data.get("transaction_count")
        hash_rate = health_data.get("hash_rate")

        text = f"📊 **Network Health: {asset}**\n\n"

        if active_addr:
            text += f"👥 Active Addresses: {active_addr:,.0f}\n"

        if tx_count:
            text += f"💸 Transactions (24h): {tx_count:,.0f}\n"

        if hash_rate:
            # Convert to EH/s (exahashes) for readability
            eh_rate = hash_rate / 1e18
            text += f"⚡ Hash Rate: {eh_rate:.2f} EH/s\n"

        return text

    async def format_exchange_flows(self, flow_data: Dict[str, Any]) -> str:
        """
        Format exchange flow data for Telegram display

        Args:
            flow_data: Exchange flow metrics dict

        Returns:
            Formatted string for Telegram
        """
        if not flow_data:
            return "❌ Exchange flow data not available"

        asset = flow_data.get("asset", "").upper()
        inflow = flow_data.get("inflow", 0)
        outflow = flow_data.get("outflow", 0)
        net_flow = flow_data.get("net_flow", 0)
        sentiment = flow_data.get("sentiment", "neutral")

        emoji = "🐻" if sentiment == "bearish" else "🐂"

        text = f"🔄 **Exchange Flows: {asset}**\n\n"
        text += f"📥 Inflow: {inflow:,.2f} {asset}\n"
        text += f"📤 Outflow: {outflow:,.2f} {asset}\n"
        text += f"📊 Net Flow: {net_flow:,.2f} {asset}\n\n"

        if net_flow > 0:
            text += f"{emoji} Positive flow → coins moving TO exchanges (potential sell pressure)\n"
        else:
            text += f"{emoji} Negative flow → coins moving FROM exchanges (accumulation signal)\n"

        return text
