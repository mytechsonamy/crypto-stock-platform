"""
Yahoo Finance Collector Implementation.

Collects BIST stock market data from Yahoo Finance API with 5-minute delay.

Features:
- Polling mechanism (every 5 minutes)
- BIST market hours detection
- Rate limiting and exponential backoff
- Circuit breaker integration
- Direct OHLC data (no tick-to-bar conversion)
"""

import asyncio
import json
from typing import Dict, List
from datetime import datetime, time as dt_time
import pytz
import yfinance as yf
from loguru import logger

from collectors.base_collector import BaseCollector
from storage.redis_cache import RedisCacheManager
from storage.symbol_manager import SymbolManager
from monitoring.metrics import trades_received_total


class YahooCollector(BaseCollector):
    """
    Yahoo Finance BIST stock data collector.
    
    Features:
    - 5-minute polling interval
    - BIST market hours detection (09:40-18:10 TRT)
    - Rate limiting with exponential backoff
    - Direct OHLC data processing
    """
    
    def __init__(
        self,
        config: Dict,
        redis_client: RedisCacheManager,
        symbol_manager: SymbolManager
    ):
        """
        Initialize Yahoo Finance collector.
        
        Args:
            config: Yahoo Finance configuration
            redis_client: Redis client for publishing
            symbol_manager: Symbol manager for dynamic symbol loading
        """
        super().__init__("yahoo", config, redis_client, symbol_manager)
        
        # Polling configuration
        polling_config = config.get('polling', {})
        self.polling_interval = polling_config.get('interval', 300)  # 5 minutes
        self.polling_timeout = polling_config.get('timeout', 30)
        
        # Market hours configuration
        market_config = config.get('market_hours', {})
        self.timezone = pytz.timezone(market_config.get('timezone', 'Europe/Istanbul'))
        self.market_open_time = self._parse_time(market_config.get('open', '09:40'))
        self.market_close_time = self._parse_time(market_config.get('close', '18:10'))
        self.market_days = market_config.get('days', [
            'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'
        ])
        
        # Rate limiting
        rate_config = config.get('rest', {}).get('rate_limit', {})
        self.requests_per_minute = rate_config.get('requests_per_minute', 60)
        self.backoff_config = rate_config.get('backoff', {})
        self.initial_delay = self.backoff_config.get('initial_delay', 10)
        self.max_delay = self.backoff_config.get('max_delay', 300)
        self.multiplier = self.backoff_config.get('multiplier', 2)
        
        # State
        self.current_backoff_delay = self.initial_delay
        self.request_count = 0
        self.request_window_start = datetime.now()
        self.last_poll_time = None
        
        self.logger.info(
            f"Yahoo collector initialized: "
            f"polling_interval={self.polling_interval}s, "
            f"market_hours={self.market_open_time}-{self.market_close_time} TRT"
        )
    
    def _parse_time(self, time_str: str) -> dt_time:
        """Parse time string (HH:MM) to time object."""
        hour, minute = map(int, time_str.split(':'))
        return dt_time(hour, minute)
    
    def _is_market_hours(self) -> bool:
        """
        Check if current time is within BIST market hours.
        
        Returns:
            True if BIST market is open, False otherwise
        """
        now = datetime.now(self.timezone)
        
        # Check if weekend
        if now.strftime('%A') not in self.market_days:
            return False
        
        # Check time
        current_time = now.time()
        return self.market_open_time <= current_time <= self.market_close_time
    
    async def connect(self) -> None:
        """Initialize Yahoo Finance connection (no persistent connection needed)."""
        try:
            # Yahoo Finance doesn't require authentication or persistent connection
            # Test with commonly available US stock symbols
            test_symbols = ["AAPL", "MSFT", "GOOGL"]

            for test_symbol in test_symbols:
                try:
                    test_ticker = yf.Ticker(test_symbol)
                    test_data = test_ticker.history(period="1d", interval="1m")

                    if not test_data.empty:
                        self.logger.success(f"Connected to Yahoo Finance API (tested with {test_symbol})")
                        return
                except Exception as e:
                    self.logger.debug(f"Test failed for {test_symbol}: {e}")
                    continue

            # If all tests failed, raise error
            raise Exception("Failed to fetch test data from Yahoo Finance with any test symbol")

        except Exception as e:
            self.logger.error(f"Failed to connect to Yahoo Finance: {e}")
            raise
    
    async def subscribe(self, symbols: List[str]) -> None:
        """
        Set up polling for symbols (Yahoo Finance doesn't have subscriptions).
        
        Args:
            symbols: List of BIST symbols (e.g., ['THYAO.IS', 'GARAN.IS'])
        """
        self.logger.info(
            f"Set up polling for {len(symbols)} BIST symbols: {', '.join(symbols[:5])}{'...' if len(symbols) > 5 else ''}"
        )
    
    async def handle_message(self, message: Dict) -> None:
        """
        Process message (not used for Yahoo Finance polling).
        
        Args:
            message: Message data (not applicable for Yahoo Finance)
        """
        pass
    
    async def disconnect(self) -> None:
        """Clean up Yahoo Finance connections (no persistent connection to close)."""
        self.logger.info("Yahoo Finance collector disconnected")
    
    async def run(self) -> None:
        """
        Main polling loop with market hours handling.
        
        Polls data every 5 minutes during market hours,
        reduces frequency during market close.
        """
        while self.is_running:
            try:
                # Get symbols from database
                symbols = await self.symbol_manager.get_symbols_by_exchange(self.exchange)
                
                if not symbols:
                    self.logger.warning("No BIST symbols found in database")
                    await asyncio.sleep(60)
                    continue
                
                # Check market hours
                if self._is_market_hours():
                    # Market is open - poll actively
                    await self._poll_data(symbols)
                    await asyncio.sleep(self.polling_interval)
                else:
                    # Market is closed - poll less frequently
                    self.logger.debug("BIST market closed, reducing polling frequency")
                    await asyncio.sleep(self.polling_interval * 2)  # 10 minutes
                    
            except Exception as e:
                self.logger.error(f"Error in Yahoo polling loop: {e}")
                await self._handle_error()
    
    async def _poll_data(self, symbols: List[str]) -> None:
        """
        Poll data for all symbols.
        
        Args:
            symbols: List of symbols to poll
        """
        self.logger.debug(f"Polling data for {len(symbols)} symbols...")
        
        for symbol in symbols:
            try:
                # Check rate limit
                await self._check_rate_limit()
                
                # Fetch data
                ticker = yf.Ticker(symbol)
                data = ticker.history(period="1d", interval="1m")
                
                self.request_count += 1
                
                if not data.empty:
                    # Get latest bar
                    latest = data.iloc[-1]
                    timestamp = int(data.index[-1].timestamp() * 1000)
                    
                    # Create bar data
                    bar_data = {
                        'exchange': 'yahoo',
                        'symbol': symbol,
                        'timeframe': '1m',
                        'time': timestamp,
                        'open': float(latest['Open']),
                        'high': float(latest['High']),
                        'low': float(latest['Low']),
                        'close': float(latest['Close']),
                        'volume': float(latest['Volume']),
                        'completed': True
                    }
                    
                    # Publish as completed bar (Yahoo gives OHLC directly)
                    await self.redis.publish('completed_bars', json.dumps(bar_data))
                    
                    # Also publish as trade for consistency
                    trade_data = {
                        'exchange': 'yahoo',
                        'symbol': symbol,
                        'price': float(latest['Close']),
                        'quantity': float(latest['Volume']),
                        'timestamp': timestamp
                    }
                    
                    await self.publish_trade(trade_data)
                    
                    self.logger.debug(
                        f"Polled {symbol}: {latest['Close']:.2f} (Volume: {latest['Volume']:.0f})"
                    )
                    
                    # Reset backoff on success
                    self.current_backoff_delay = self.initial_delay
                    
                else:
                    self.logger.warning(f"No data received for {symbol}")
                    
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
        # Could implement per-symbol circuit breakers in the future
        pass
