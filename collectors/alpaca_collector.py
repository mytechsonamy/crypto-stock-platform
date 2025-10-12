"""
Alpaca Collector Implementation.

Collects real-time US stock market data from Alpaca WebSocket API.

Features:
- Trade and bar stream subscriptions
- Market hours detection (NYSE/NASDAQ)
- Graceful handling of market close
- Circuit breaker integration
"""

import asyncio
import json
from typing import Dict, List
from datetime import datetime, time as dt_time
import pytz
from alpaca_trade_api.stream import Stream
from alpaca_trade_api.rest import REST
from loguru import logger

from collectors.base_collector import BaseCollector
from storage.redis_cache import RedisCacheManager
from storage.symbol_manager import SymbolManager
from monitoring.metrics import trades_received_total


class AlpacaCollector(BaseCollector):
    """
    Alpaca US stock market data collector.
    
    Subscribes to:
    - Trade streams (real-time trades)
    - Bar streams (minute bars)
    
    Features:
    - Market hours detection (NYSE/NASDAQ: 09:30-16:00 ET)
    - Automatic pause during market close
    - Circuit breaker during non-market hours
    """
    
    def __init__(
        self,
        config: Dict,
        redis_client: RedisCacheManager,
        symbol_manager: SymbolManager
    ):
        """
        Initialize Alpaca collector.
        
        Args:
            config: Alpaca configuration
            redis_client: Redis client for publishing
            symbol_manager: Symbol manager for dynamic symbol loading
        """
        super().__init__("alpaca", config, redis_client, symbol_manager)
        
        self.stream: Stream = None
        self.rest_client: REST = None
        
        # Market hours configuration
        market_config = config.get('market_hours', {})
        self.timezone = pytz.timezone(market_config.get('timezone', 'US/Eastern'))
        self.market_open_time = self._parse_time(market_config.get('open', '09:30'))
        self.market_close_time = self._parse_time(market_config.get('close', '16:00'))
        self.market_days = market_config.get('days', [
            'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'
        ])
        
        # Data feed (IEX free or SIP paid)
        self.data_feed = config.get('websocket', {}).get('data_feed', 'iex')
        
        self.logger.info(
            f"Alpaca collector initialized: "
            f"market_hours={self.market_open_time}-{self.market_close_time} ET, "
            f"data_feed={self.data_feed}"
        )
    
    def _parse_time(self, time_str: str) -> dt_time:
        """Parse time string (HH:MM) to time object."""
        hour, minute = map(int, time_str.split(':'))
        return dt_time(hour, minute)
    
    def _is_market_hours(self) -> bool:
        """
        Check if current time is within market hours.
        
        Returns:
            True if market is open, False otherwise
        """
        now = datetime.now(self.timezone)
        
        # Check if weekend
        if now.strftime('%A') not in self.market_days:
            return False
        
        # Check time
        current_time = now.time()
        return self.market_open_time <= current_time <= self.market_close_time
    
    async def connect(self) -> None:
        """Establish connection to Alpaca WebSocket API."""
        try:
            api_key = self.config.get('api_key')
            secret_key = self.config.get('secret_key')
            
            # Create stream client
            self.stream = Stream(
                key_id=api_key,
                secret_key=secret_key,
                data_feed=self.data_feed,
                raw_data=False
            )
            
            # Create REST client for historical data
            self.rest_client = REST(
                key_id=api_key,
                secret_key=secret_key
            )
            
            self.logger.success(f"Connected to Alpaca API (feed: {self.data_feed})")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Alpaca: {e}")
            raise
    
    async def subscribe(self, symbols: List[str]) -> None:
        """
        Subscribe to trade and bar streams for symbols.
        
        Args:
            symbols: List of stock symbols (e.g., ['AAPL', 'TSLA'])
        """
        try:
            # Subscribe to trades
            self.stream.subscribe_trades(
                self._handle_trade_callback,
                *symbols
            )
            
            # Subscribe to bars (minute bars)
            self.stream.subscribe_bars(
                self._handle_bar_callback,
                *symbols
            )
            
            self.logger.info(
                f"Subscribed to Alpaca streams for {len(symbols)} symbols"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to subscribe to Alpaca streams: {e}")
            raise
    
    async def _handle_trade_callback(self, trade):
        """
        Callback for trade events.
        
        Args:
            trade: Trade object from Alpaca
        """
        try:
            # Check market hours
            if not self._is_market_hours():
                self.logger.debug(f"Trade outside market hours: {trade.symbol}")
                return
            
            trade_data = {
                'exchange': 'alpaca',
                'symbol': trade.symbol,
                'price': float(trade.price),
                'quantity': float(trade.size),
                'timestamp': int(trade.timestamp.timestamp() * 1000),
                'conditions': trade.conditions if hasattr(trade, 'conditions') else []
            }
            
            await self.publish_trade(trade_data)
            
        except Exception as e:
            self.logger.error(f"Error handling Alpaca trade: {e}")
    
    async def _handle_bar_callback(self, bar):
        """
        Callback for bar events.
        
        Args:
            bar: Bar object from Alpaca
        """
        try:
            bar_data = {
                'exchange': 'alpaca',
                'symbol': bar.symbol,
                'timeframe': '1m',
                'time': int(bar.timestamp.timestamp() * 1000),
                'open': float(bar.open),
                'high': float(bar.high),
                'low': float(bar.low),
                'close': float(bar.close),
                'volume': float(bar.volume),
                'completed': True
            }
            
            # Publish completed bar
            await self.redis.publish('completed_bars', json.dumps(bar_data))
            
            self.logger.debug(
                f"Completed bar: {bar.symbol} @ {bar_data['close']}"
            )
            
        except Exception as e:
            self.logger.error(f"Error handling Alpaca bar: {e}")
    
    async def handle_message(self, message: Dict) -> None:
        """
        Process incoming message from Alpaca.
        
        Note: Alpaca uses callbacks, so this method is not directly used.
        Kept for interface compatibility.
        """
        pass
    
    async def disconnect(self) -> None:
        """Clean up Alpaca connections."""
        try:
            if self.stream:
                await self.stream.stop_ws()
            
            self.logger.info("Disconnected from Alpaca")
            
        except Exception as e:
            self.logger.error(f"Error disconnecting from Alpaca: {e}")
    
    async def run(self) -> None:
        """
        Main collector loop with market hours handling.
        
        Pauses during market close and resumes on market open.
        """
        while self.is_running:
            # Check if market is open
            if self._is_market_hours():
                if not self.is_connected:
                    self.logger.info("Market is open, starting stream...")
                    await self.connect_with_circuit_breaker()
                    
                    # Get symbols from database
                    symbols = await self.symbol_manager.get_symbols_by_exchange(self.exchange)
                    await self.subscribe(symbols)
                    
                    # Start stream
                    try:
                        await self.stream.run()
                    except Exception as e:
                        self.logger.error(f"Stream error: {e}")
                        self.is_connected = False
                        raise
            else:
                # Market is closed
                if self.is_connected:
                    self.logger.info("Market closed, pausing stream...")
                    await self.disconnect()
                    self.is_connected = False
                    
                    # Open circuit breaker during market close
                    # This prevents unnecessary reconnection attempts
                    self.logger.info("Opening circuit breaker during market close")
                
                # Wait and check again
                await asyncio.sleep(60)  # Check every minute
    
    async def fetch_historical(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str
    ) -> List[Dict]:
        """
        Fetch historical bar data from Alpaca REST API.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            timeframe: Bar timeframe (e.g., '1Min', '5Min', '1Hour')
            start: Start date (ISO format: 'YYYY-MM-DD')
            end: End date (ISO format: 'YYYY-MM-DD')
            
        Returns:
            List of bar dictionaries
        """
        try:
            bars = self.rest_client.get_bars(
                symbol,
                timeframe,
                start=start,
                end=end
            ).df
            
            # Convert to list of dicts
            parsed_bars = []
            for index, row in bars.iterrows():
                parsed_bars.append({
                    'exchange': 'alpaca',
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'time': int(index.timestamp() * 1000),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume'])
                })
            
            self.logger.info(
                f"Fetched {len(parsed_bars)} historical bars for {symbol} {timeframe}"
            )
            
            return parsed_bars
            
        except Exception as e:
            self.logger.error(f"Failed to fetch historical data: {e}")
            raise
    
    def get_next_market_open(self) -> datetime:
        """
        Get next market open time.
        
        Returns:
            Datetime of next market open
        """
        now = datetime.now(self.timezone)
        
        # If market is currently open, return now
        if self._is_market_hours():
            return now
        
        # Find next market day
        next_open = now.replace(
            hour=self.market_open_time.hour,
            minute=self.market_open_time.minute,
            second=0,
            microsecond=0
        )
        
        # If today's market open has passed, move to next day
        if now.time() > self.market_open_time:
            next_open += timedelta(days=1)
        
        # Skip weekends
        while next_open.strftime('%A') not in self.market_days:
            next_open += timedelta(days=1)
        
        return next_open
    
    def get_time_until_market_open(self) -> float:
        """
        Get seconds until next market open.
        
        Returns:
            Seconds until market opens
        """
        next_open = self.get_next_market_open()
        now = datetime.now(self.timezone)
        return (next_open - now).total_seconds()
