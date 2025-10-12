"""
Binance Collector Implementation.

Collects real-time cryptocurrency data from Binance WebSocket API.

Features:
- Trade and kline stream subscriptions
- 24-hour connection refresh
- Historical data fetching via REST API
- Rate limiting and circuit breaker integration
"""

import asyncio
import json
from typing import Dict, List
from datetime import datetime, timedelta
from binance import AsyncClient, BinanceSocketManager
from loguru import logger

from collectors.base_collector import BaseCollector
from storage.redis_cache import RedisCacheManager
from storage.symbol_manager import SymbolManager
from monitoring.metrics import trades_received_total


class BinanceCollector(BaseCollector):
    """
    Binance cryptocurrency data collector.
    
    Subscribes to:
    - Trade streams (real-time trades)
    - Kline streams (1m, 5m, 15m, 1h candlesticks)
    
    Features:
    - Automatic 24-hour connection refresh
    - Historical data backfill
    - Rate limit tracking (1200 req/min)
    """
    
    def __init__(
        self,
        config: Dict,
        redis_client: RedisCacheManager,
        symbol_manager: SymbolManager
    ):
        """
        Initialize Binance collector.
        
        Args:
            config: Binance configuration
            redis_client: Redis client for publishing
            symbol_manager: Symbol manager for dynamic symbol loading
        """
        super().__init__("binance", config, redis_client, symbol_manager)
        
        self.client: AsyncClient = None
        self.bsm: BinanceSocketManager = None
        self.trade_socket = None
        self.kline_socket = None
        
        # Connection refresh timer (24 hours)
        self.refresh_interval = config.get('websocket', {}).get('refresh_interval', 86400)
        self.last_refresh = None
        self.refresh_task = None
        
        # Rate limiting
        self.rate_limit = config.get('rest', {}).get('rate_limit', {})
        self.requests_per_minute = self.rate_limit.get('requests_per_minute', 1200)
        self.request_count = 0
        self.request_window_start = datetime.now()
        
        self.logger.info(
            f"Binance collector initialized: "
            f"refresh_interval={self.refresh_interval}s, "
            f"rate_limit={self.requests_per_minute} req/min"
        )
    
    async def connect(self) -> None:
        """Establish connection to Binance WebSocket API."""
        try:
            # Create async client
            api_key = self.config.get('api_key')
            api_secret = self.config.get('api_secret')
            
            self.client = await AsyncClient.create(
                api_key=api_key,
                api_secret=api_secret
            )
            
            # Create socket manager
            self.bsm = BinanceSocketManager(self.client)
            
            self.last_refresh = datetime.now()
            self.logger.success("Connected to Binance WebSocket API")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Binance: {e}")
            raise
    
    async def subscribe(self, symbols: List[str]) -> None:
        """
        Subscribe to trade and kline streams for symbols.
        
        Args:
            symbols: List of trading pairs (e.g., ['BTCUSDT', 'ETHUSDT'])
        """
        try:
            # Subscribe to trade streams
            trade_streams = [f"{symbol.lower()}@trade" for symbol in symbols]
            self.trade_socket = self.bsm.multiplex_socket(trade_streams)
            
            # Subscribe to kline streams (multiple timeframes)
            timeframes = self.config.get('websocket', {}).get('streams', [])
            kline_timeframes = [tf.replace('kline_', '') for tf in timeframes if 'kline' in tf]
            
            kline_streams = [
                f"{symbol.lower()}@kline_{tf}"
                for symbol in symbols
                for tf in kline_timeframes
            ]
            
            if kline_streams:
                self.kline_socket = self.bsm.multiplex_socket(kline_streams)
            
            self.logger.info(
                f"Subscribed to Binance streams: "
                f"{len(trade_streams)} trade streams, "
                f"{len(kline_streams)} kline streams"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to subscribe to Binance streams: {e}")
            raise
    
    async def handle_message(self, message: Dict) -> None:
        """
        Process incoming message from Binance.
        
        Args:
            message: Message data from Binance WebSocket
        """
        try:
            if message.get('e') == 'trade':
                await self._handle_trade(message)
            elif message.get('e') == 'kline':
                await self._handle_kline(message)
                
        except Exception as e:
            self.logger.error(f"Error handling Binance message: {e}")
    
    async def _handle_trade(self, message: Dict) -> None:
        """Handle trade event."""
        trade_data = {
            'exchange': 'binance',
            'symbol': message['s'],
            'price': float(message['p']),
            'quantity': float(message['q']),
            'timestamp': message['T'],
            'is_buyer_maker': message['m']
        }
        
        await self.publish_trade(trade_data)
    
    async def _handle_kline(self, message: Dict) -> None:
        """Handle kline (candlestick) event."""
        kline = message['k']
        
        # Only process completed klines
        if kline['x']:  # is_closed
            bar_data = {
                'exchange': 'binance',
                'symbol': message['s'],
                'timeframe': kline['i'],
                'time': kline['t'],
                'open': float(kline['o']),
                'high': float(kline['h']),
                'low': float(kline['l']),
                'close': float(kline['c']),
                'volume': float(kline['v']),
                'completed': True
            }
            
            # Publish completed bar
            await self.redis.publish('completed_bars', json.dumps(bar_data))
            
            self.logger.debug(
                f"Completed kline: {message['s']} {kline['i']} @ {bar_data['close']}"
            )
    
    async def disconnect(self) -> None:
        """Clean up Binance connections."""
        try:
            if self.trade_socket:
                await self.trade_socket.close()
            
            if self.kline_socket:
                await self.kline_socket.close()
            
            if self.client:
                await self.client.close_connection()
            
            if self.refresh_task:
                self.refresh_task.cancel()
            
            self.logger.info("Disconnected from Binance")
            
        except Exception as e:
            self.logger.error(f"Error disconnecting from Binance: {e}")
    
    async def run(self) -> None:
        """Main collector loop with connection refresh."""
        # Start connection refresh task
        self.refresh_task = asyncio.create_task(self._connection_refresh_loop())
        
        # Start listening to streams
        tasks = []
        
        if self.trade_socket:
            tasks.append(asyncio.create_task(self._listen_trade_stream()))
        
        if self.kline_socket:
            tasks.append(asyncio.create_task(self._listen_kline_stream()))
        
        # Wait for all tasks
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _listen_trade_stream(self) -> None:
        """Listen to trade stream."""
        try:
            async with self.trade_socket as stream:
                while self.is_running and self.is_connected:
                    message = await stream.recv()
                    await self.handle_message(message)
        except Exception as e:
            self.logger.error(f"Trade stream error: {e}")
            raise
    
    async def _listen_kline_stream(self) -> None:
        """Listen to kline stream."""
        try:
            async with self.kline_socket as stream:
                while self.is_running and self.is_connected:
                    message = await stream.recv()
                    await self.handle_message(message)
        except Exception as e:
            self.logger.error(f"Kline stream error: {e}")
            raise
    
    async def _connection_refresh_loop(self) -> None:
        """
        Periodically refresh WebSocket connection (24 hours).
        
        Binance best practice: refresh connection every 24 hours.
        """
        while self.is_running:
            await asyncio.sleep(self.refresh_interval)
            
            if self.is_running:
                self.logger.info("Refreshing Binance WebSocket connection (24h timer)")
                
                try:
                    # Disconnect and reconnect
                    await self.disconnect()
                    await asyncio.sleep(5)  # Brief pause
                    await self.connect_with_circuit_breaker()
                    
                    # Re-subscribe with symbols from database
                    symbols = await self.symbol_manager.get_symbols_by_exchange(self.exchange)
                    await self.subscribe(symbols)
                    
                    self.last_refresh = datetime.now()
                    self.logger.success("Connection refreshed successfully")
                    
                except Exception as e:
                    self.logger.error(f"Failed to refresh connection: {e}")
                    # Will retry in next iteration
    
    async def fetch_historical(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int
    ) -> List[Dict]:
        """
        Fetch historical kline data from Binance REST API.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Kline interval (e.g., '1m', '5m', '1h')
            start_time: Start timestamp (milliseconds)
            end_time: End timestamp (milliseconds)
            
        Returns:
            List of kline dictionaries
        """
        # Check rate limit
        await self._check_rate_limit()
        
        try:
            klines = await self.client.get_historical_klines(
                symbol,
                interval,
                start_time,
                end_time
            )
            
            self.request_count += 1
            
            # Parse klines
            parsed_klines = []
            for kline in klines:
                parsed_klines.append({
                    'exchange': 'binance',
                    'symbol': symbol,
                    'timeframe': interval,
                    'time': kline[0],
                    'open': float(kline[1]),
                    'high': float(kline[2]),
                    'low': float(kline[3]),
                    'close': float(kline[4]),
                    'volume': float(kline[5])
                })
            
            self.logger.info(
                f"Fetched {len(parsed_klines)} historical klines for {symbol} {interval}"
            )
            
            return parsed_klines
            
        except Exception as e:
            self.logger.error(f"Failed to fetch historical data: {e}")
            raise
    
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
