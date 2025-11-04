"""
Polygon.io Collector Implementation.

Collects US stock market data from Polygon.io REST API.

Features:
- REST API polling (free tier: 5 requests/minute)
- US market hours detection
- Rate limiting and exponential backoff
- Circuit breaker integration
- Direct OHLC data (aggregates/bars endpoint)
"""

import asyncio
import json
from typing import Dict, List
from datetime import datetime, timedelta, time as dt_time
import pytz
import aiohttp
from loguru import logger

from collectors.base_collector import BaseCollector
from storage.redis_cache import RedisCacheManager
from storage.symbol_manager import SymbolManager
from monitoring.metrics import trades_received_total


class PolygonCollector(BaseCollector):
    """
    Polygon.io US stock data collector.

    Features:
    - REST API polling (aggregates endpoint)
    - US market hours detection (09:30-16:00 ET)
    - Rate limiting with exponential backoff
    - Free tier: 5 requests/minute
    """

    def __init__(
        self,
        config: Dict,
        redis_client: RedisCacheManager,
        symbol_manager: SymbolManager
    ):
        """
        Initialize Polygon.io collector.

        Args:
            config: Polygon.io configuration
            redis_client: Redis client for publishing
            symbol_manager: Symbol manager for dynamic symbol loading
        """
        super().__init__("polygon", config, redis_client, symbol_manager)

        # API configuration
        self.api_key = config.get('api_key', '')
        self.base_url = config.get('rest', {}).get('base_url', 'https://api.polygon.io')

        # Polling configuration
        polling_config = config.get('polling', {})
        self.polling_interval = polling_config.get('interval', 60)  # 1 minute
        self.polling_timeout = polling_config.get('timeout', 30)

        # Market hours configuration
        market_config = config.get('market_hours', {})
        self.timezone = pytz.timezone(market_config.get('timezone', 'America/New_York'))
        self.market_open_time = self._parse_time(market_config.get('open', '09:30'))
        self.market_close_time = self._parse_time(market_config.get('close', '16:00'))
        self.market_days = market_config.get('days', [
            'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'
        ])

        # Rate limiting (free tier: 5 requests/minute)
        rate_config = config.get('rest', {}).get('rate_limit', {})
        self.requests_per_minute = rate_config.get('requests_per_minute', 5)
        self.backoff_config = rate_config.get('backoff', {})
        self.initial_delay = self.backoff_config.get('initial_delay', 10)
        self.max_delay = self.backoff_config.get('max_delay', 300)
        self.multiplier = self.backoff_config.get('multiplier', 2)

        # State
        self.current_backoff_delay = self.initial_delay
        self.request_count = 0
        self.request_window_start = datetime.now()
        self.last_poll_time = None
        self.session: aiohttp.ClientSession = None

        self.logger.info(
            f"Polygon collector initialized: "
            f"polling_interval={self.polling_interval}s, "
            f"market_hours={self.market_open_time}-{self.market_close_time} ET, "
            f"rate_limit={self.requests_per_minute} req/min"
        )

    def _parse_time(self, time_str: str) -> dt_time:
        """Parse time string (HH:MM) to time object."""
        hour, minute = map(int, time_str.split(':'))
        return dt_time(hour, minute)

    def _is_market_hours(self) -> bool:
        """
        Check if current time is within US market hours.

        Returns:
            True if US market is open, False otherwise
        """
        now = datetime.now(self.timezone)

        # Check if weekend
        if now.strftime('%A') not in self.market_days:
            return False

        # Check time
        current_time = now.time()
        return self.market_open_time <= current_time <= self.market_close_time

    async def connect(self) -> None:
        """Initialize Polygon.io connection."""
        try:
            if not self.api_key or self.api_key == 'your_polygon_api_key':
                raise Exception("Polygon.io API key not configured")

            # Create aiohttp session
            self.session = aiohttp.ClientSession()

            # Test API with a simple request
            test_url = f"{self.base_url}/v2/aggs/ticker/AAPL/range/1/minute/2024-01-01/2024-01-02"
            params = {'apiKey': self.api_key, 'limit': 1}

            async with self.session.get(test_url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status') == 'OK':
                        self.logger.success("Connected to Polygon.io API")
                        return
                    else:
                        raise Exception(f"Polygon.io API error: {data.get('error', 'Unknown error')}")
                else:
                    raise Exception(f"Polygon.io API returned status {response.status}")

        except Exception as e:
            if self.session:
                await self.session.close()
                self.session = None
            self.logger.error(f"Failed to connect to Polygon.io: {e}")
            raise

    async def subscribe(self, symbols: List[str]) -> None:
        """
        Set up polling for symbols (Polygon.io doesn't have subscriptions).

        Args:
            symbols: List of stock symbols (e.g., ['AAPL', 'GOOGL'])
        """
        self.logger.info(
            f"Set up polling for {len(symbols)} stock symbols: {', '.join(symbols[:5])}{'...' if len(symbols) > 5 else ''}"
        )

    async def handle_message(self, message: Dict) -> None:
        """
        Process message (not used for Polygon.io polling).

        Args:
            message: Message data (not applicable for Polygon.io)
        """
        pass

    async def disconnect(self) -> None:
        """Clean up Polygon.io connections."""
        if self.session:
            await self.session.close()
            self.session = None
        self.logger.info("Polygon.io collector disconnected")

    async def run(self) -> None:
        """
        Main polling loop with market hours handling.

        Polls data during market hours, reduces frequency during market close.
        """
        while self.is_running:
            try:
                # Get symbols from database
                symbols = await self.symbol_manager.get_symbols_by_exchange(self.exchange)

                if not symbols:
                    self.logger.warning("No stock symbols found in database")
                    await asyncio.sleep(60)
                    continue

                # Poll previous close data regardless of market hours
                # (previous close endpoint provides historical data)
                await self._poll_data(symbols)
                await asyncio.sleep(self.polling_interval)

            except Exception as e:
                self.logger.error(f"Error in Polygon polling loop: {e}")
                await self._handle_error()

    async def _poll_data(self, symbols: List[str]) -> None:
        """
        Poll data for all symbols using Polygon.io snapshot endpoint.

        Free/Starter tier provides 15-minute delayed data.
        Rate limit: 5 requests/minute

        Args:
            symbols: List of symbols to poll
        """
        self.logger.debug(f"Polling data for {len(symbols)} symbols...")

        for symbol in symbols:
            try:
                # Check rate limit
                await self._check_rate_limit()

                # Use previous close endpoint (available on free tier)
                url = f"{self.base_url}/v2/aggs/ticker/{symbol}/prev"
                params = {
                    'apiKey': self.api_key,
                    'adjusted': 'true'
                }

                async with self.session.get(url, params=params, timeout=self.polling_timeout) as response:
                    self.request_count += 1

                    if response.status == 200:
                        data = await response.json()

                        if data.get('status') == 'OK' and data.get('results'):
                            # Previous close endpoint returns an array of results
                            results = data['results']

                            if results and len(results) > 0:
                                bar = results[0]

                                # Create bar data from previous day's OHLC
                                bar_data = {
                                    'exchange': 'polygon',
                                    'symbol': symbol,
                                    'timeframe': '1d',  # Daily bar
                                    'time': bar.get('t'),  # Timestamp from API
                                    'open': float(bar.get('o', 0)),
                                    'high': float(bar.get('h', 0)),
                                    'low': float(bar.get('l', 0)),
                                    'close': float(bar.get('c', 0)),
                                    'volume': float(bar.get('v', 0)),
                                    'completed': True  # Previous day data is completed
                                }

                                # Publish as completed bar
                                self.logger.debug(f"Publishing bar for {symbol} to bars:completed channel")
                                await self.redis.publish('bars:completed', json.dumps(bar_data))
                                self.logger.debug(f"Published bar for {symbol}")

                                # Also publish as trade for consistency
                                trade_data = {
                                    'exchange': 'polygon',
                                    'symbol': symbol,
                                    'price': float(bar.get('c', 0)),
                                    'quantity': float(bar.get('v', 0)),
                                    'timestamp': bar.get('t')
                                }

                                await self.publish_trade(trade_data)

                                self.logger.info(
                                    f"✅ Polled {symbol}: ${bar['c']:.2f} "
                                    f"Vol: {bar['v']:,.0f} (prev close) - Published to Redis"
                                )

                                # Reset backoff on success
                                self.current_backoff_delay = self.initial_delay
                            else:
                                self.logger.debug(f"No results for {symbol}")

                        else:
                            self.logger.debug(f"No data for {symbol}: {data.get('status')}")

                    elif response.status == 429:
                        self.logger.warning(f"Rate limit hit for {symbol}, backing off...")
                        await self._handle_error()
                        break  # Stop processing symbols to avoid more rate limit errors

                    elif response.status == 403:
                        error_data = await response.json()
                        self.logger.error(f"Access forbidden for {symbol}: {error_data.get('error', 'Unknown error')}")
                        # Don't retry on 403
                        continue

                    else:
                        self.logger.warning(f"HTTP {response.status} for {symbol}")

            except Exception as e:
                self.logger.error(f"Error polling {symbol}: {e}")
                await self._handle_symbol_error(symbol)

        self.last_poll_time = datetime.now()

    async def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting."""
        now = datetime.now()
        elapsed = (now - self.request_window_start).total_seconds()

        # Reset window if 1 minute passed
        if elapsed >= 60:
            self.request_count = 0
            self.request_window_start = now
            return

        # Check if limit exceeded
        if self.request_count >= self.requests_per_minute:
            # Wait until window resets
            wait_time = 60 - elapsed
            self.logger.warning(
                f"Rate limit reached ({self.requests_per_minute} req/min). "
                f"Waiting {wait_time:.1f}s..."
            )
            await asyncio.sleep(wait_time)
            self.request_count = 0
            self.request_window_start = datetime.now()

    async def _handle_error(self) -> None:
        """Handle general errors with exponential backoff."""
        self.logger.warning(
            f"Applying exponential backoff: {self.current_backoff_delay}s"
        )

        await asyncio.sleep(self.current_backoff_delay)

        # Increase backoff delay
        self.current_backoff_delay = min(
            self.current_backoff_delay * self.multiplier,
            self.max_delay
        )

    async def _handle_symbol_error(self, symbol: str) -> None:
        """
        Handle symbol-specific errors.

        Args:
            symbol: Symbol that encountered error
        """
        # For now, just log and continue
        pass
