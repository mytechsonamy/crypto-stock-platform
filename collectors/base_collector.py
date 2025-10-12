"""
Base Collector Abstract Class.

Provides common functionality for all data collectors:
- Circuit breaker integration
- Exponential backoff reconnection
- Redis publishing
- Health status tracking
- Metrics and logging
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime

from loguru import logger

from collectors.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpenError
from storage.redis_cache import RedisCacheManager
from storage.symbol_manager import SymbolManager
from monitoring.metrics import (
    trades_received_total,
    collector_errors_total,
    websocket_reconnections_total,
    collector_status,
    last_trade_timestamp
)


class BaseCollector(ABC):
    """
    Abstract base class for all data collectors.
    
    Provides:
    - Connection management with circuit breaker
    - Automatic reconnection with exponential backoff
    - Trade publishing to Redis
    - Health status tracking
    - Metrics and structured logging
    
    Subclasses must implement:
    - connect(): Establish connection to data source
    - subscribe(symbols): Subscribe to symbol streams
    - handle_message(message): Process incoming messages
    - disconnect(): Clean up connections
    """
    
    def __init__(
        self,
        exchange: str,
        config: Dict,
        redis_client: RedisCacheManager,
        symbol_manager: SymbolManager
    ):
        """
        Initialize base collector.
        
        Args:
            exchange: Exchange name (binance, alpaca, yahoo)
            config: Exchange-specific configuration
            redis_client: Redis client for publishing
            symbol_manager: Symbol manager for dynamic symbol loading
        """
        self.exchange = exchange
        self.config = config
        self.redis = redis_client
        self.symbol_manager = symbol_manager
        
        # State management
        self.is_running = False
        self.is_connected = False
        
        # Reconnection settings
        self.reconnect_delay = config.get('reconnect', {}).get('initial_delay', 1)
        self.max_reconnect_delay = config.get('reconnect', {}).get('max_delay', 60)
        self.reconnect_multiplier = config.get('reconnect', {}).get('multiplier', 2)
        self.current_reconnect_delay = self.reconnect_delay
        
        # Circuit breaker
        circuit_config = CircuitBreakerConfig(
            failure_threshold=config.get('circuit_breaker', {}).get('failure_threshold', 5),
            timeout=config.get('circuit_breaker', {}).get('timeout', 60),
            success_threshold=config.get('circuit_breaker', {}).get('success_threshold', 2)
        )
        self.circuit_breaker = CircuitBreaker(f"{exchange}_collector", circuit_config)
        
        # Statistics
        self.trades_received = 0
        self.errors_count = 0
        self.reconnections_count = 0
        self.start_time = datetime.now()
        
        # Logger
        self.logger = logger.bind(component=f"{exchange}_collector")
        
        self.logger.info(
            f"Initialized {exchange} collector with circuit breaker "
            f"(threshold={circuit_config.failure_threshold}, timeout={circuit_config.timeout}s)"
        )
    
    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to data source.
        
        Must be implemented by subclasses.
        Raises exception on failure.
        """
        pass
    
    @abstractmethod
    async def subscribe(self, symbols: List[str]) -> None:
        """
        Subscribe to symbol streams.
        
        Args:
            symbols: List of symbols to subscribe to
            
        Must be implemented by subclasses.
        """
        pass
    
    @abstractmethod
    async def handle_message(self, message: Dict) -> None:
        """
        Process incoming message.
        
        Args:
            message: Message data from exchange
            
        Must be implemented by subclasses.
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Clean up connections and resources.
        
        Must be implemented by subclasses.
        """
        pass
    
    async def connect_with_circuit_breaker(self) -> None:
        """
        Connect to exchange with circuit breaker protection.
        
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Connection errors
        """
        await self.circuit_breaker.call(self._connect_internal)
    
    async def _connect_internal(self) -> None:
        """Internal connection method wrapped by circuit breaker."""
        self.logger.info(f"Connecting to {self.exchange}...")
        
        await self.connect()
        self.is_connected = True
        
        # Reset reconnect delay on successful connection
        self.current_reconnect_delay = self.reconnect_delay
        
        # Update metrics
        collector_status.labels(exchange=self.exchange).set(1)
        
        self.logger.success(f"Connected to {self.exchange}")
    
    async def reconnect(self) -> None:
        """
        Reconnect with exponential backoff.
        
        Automatically increases delay between reconnection attempts.
        """
        self.reconnections_count += 1
        websocket_reconnections_total.labels(exchange=self.exchange).inc()
        
        self.logger.warning(
            f"Reconnecting to {self.exchange} "
            f"(attempt #{self.reconnections_count}, delay={self.current_reconnect_delay}s)"
        )
        
        # Wait before reconnecting
        await asyncio.sleep(self.current_reconnect_delay)
        
        # Increase delay for next time (exponential backoff)
        self.current_reconnect_delay = min(
            self.current_reconnect_delay * self.reconnect_multiplier,
            self.max_reconnect_delay
        )
        
        try:
            await self.connect_with_circuit_breaker()
        except CircuitBreakerOpenError as e:
            self.logger.error(f"Circuit breaker is open: {e}")
            # Wait for circuit breaker timeout
            await asyncio.sleep(e.retry_after)
        except Exception as e:
            self.logger.error(f"Reconnection failed: {e}")
            # Will retry in next iteration
    
    async def publish_trade(self, trade_data: Dict) -> None:
        """
        Publish trade event to Redis.
        
        Args:
            trade_data: Trade data dictionary
        """
        try:
            # Add timestamp if not present
            if 'timestamp' not in trade_data:
                trade_data['timestamp'] = int(datetime.now().timestamp() * 1000)
            
            # Publish to Redis channel
            channel = f"trades:{self.exchange}"
            await self.redis.publish(channel, json.dumps(trade_data))
            
            # Update statistics
            self.trades_received += 1
            
            # Update metrics
            trades_received_total.labels(
                exchange=self.exchange,
                symbol=trade_data.get('symbol', 'unknown')
            ).inc()
            
            last_trade_timestamp.labels(
                exchange=self.exchange,
                symbol=trade_data.get('symbol', 'unknown')
            ).set(trade_data['timestamp'] / 1000)
            
            self.logger.debug(
                f"Published trade: {trade_data.get('symbol')} @ {trade_data.get('price')}"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to publish trade: {e}")
            self.errors_count += 1
            collector_errors_total.labels(
                exchange=self.exchange,
                error_type='publish_error'
            ).inc()
    
    async def update_health_status(self) -> None:
        """Update health status in Redis."""
        try:
            health_data = {
                'status': 'running' if self.is_running else 'stopped',
                'connected': self.is_connected,
                'last_update': int(datetime.now().timestamp()),
                'trades_received': self.trades_received,
                'errors_count': self.errors_count,
                'reconnections_count': self.reconnections_count,
                'circuit_breaker_state': self.circuit_breaker.get_state().name,
                'uptime_seconds': (datetime.now() - self.start_time).total_seconds()
            }
            
            await self.redis.update_health(
                f"{self.exchange}_collector",
                health_data
            )
            
        except Exception as e:
            self.logger.error(f"Failed to update health status: {e}")
    
    async def start(self) -> None:
        """
        Start collector with automatic reconnection.
        
        Main loop that handles connection, reconnection, and error recovery.
        """
        self.is_running = True
        self.logger.info(f"Starting {self.exchange} collector...")
        
        while self.is_running:
            try:
                # Connect with circuit breaker
                await self.connect_with_circuit_breaker()
                
                # Get symbols from database
                symbols = await self.symbol_manager.get_symbols_by_exchange(self.exchange)
                if not symbols:
                    self.logger.warning("No active symbols found in database")
                    await asyncio.sleep(10)
                    continue
                
                self.logger.info(f"Loaded {len(symbols)} symbols from database")
                
                # Subscribe to symbols
                await self.subscribe(symbols)
                
                # Update health status periodically
                health_task = asyncio.create_task(self._health_update_loop())
                
                # Run collector (implemented by subclass)
                await self.run()
                
                # Cancel health task
                health_task.cancel()
                
            except CircuitBreakerOpenError as e:
                self.logger.error(f"Circuit breaker open: {e}")
                await asyncio.sleep(e.retry_after)
                
            except Exception as e:
                self.logger.error(f"Collector error: {e}", exc_info=True)
                self.errors_count += 1
                collector_errors_total.labels(
                    exchange=self.exchange,
                    error_type=type(e).__name__
                ).inc()
                
                # Mark as disconnected
                self.is_connected = False
                collector_status.labels(exchange=self.exchange).set(0)
                
                # Attempt reconnection
                if self.is_running:
                    await self.reconnect()
        
        # Cleanup
        await self.stop()
    
    async def run(self) -> None:
        """
        Main collector loop.
        
        Can be overridden by subclasses for custom behavior.
        Default implementation just keeps running.
        """
        while self.is_running and self.is_connected:
            await asyncio.sleep(1)
    
    async def _health_update_loop(self) -> None:
        """Periodically update health status."""
        while self.is_running:
            await self.update_health_status()
            await asyncio.sleep(30)  # Update every 30 seconds
    
    async def stop(self) -> None:
        """Stop collector and cleanup."""
        self.logger.info(f"Stopping {self.exchange} collector...")
        self.is_running = False
        
        try:
            await self.disconnect()
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
        
        self.is_connected = False
        collector_status.labels(exchange=self.exchange).set(0)
        
        # Final health update
        await self.update_health_status()
        
        self.logger.info(f"{self.exchange} collector stopped")
    
    def get_stats(self) -> Dict:
        """
        Get collector statistics.
        
        Returns:
            Dictionary with current stats
        """
        return {
            'exchange': self.exchange,
            'is_running': self.is_running,
            'is_connected': self.is_connected,
            'trades_received': self.trades_received,
            'errors_count': self.errors_count,
            'reconnections_count': self.reconnections_count,
            'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
            'circuit_breaker': self.circuit_breaker.get_stats()
        }
