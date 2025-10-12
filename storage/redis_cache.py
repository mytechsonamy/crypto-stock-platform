"""
Redis Cache Manager Implementation.

Provides Redis operations for caching and pub/sub messaging.

Features:
- Connection pooling
- Caching with TTL
- Sorted sets for bars
- Hashes for indicators/features
- Pub/Sub messaging
- Health status tracking
- LRU eviction policy
- Performance monitoring
"""

import time
import json
from typing import Dict, List, Optional, Any, Callable
import redis.asyncio as redis
from loguru import logger

from prometheus_client import Counter, Histogram, Gauge


class RedisCacheManager:
    """
    Redis cache manager using redis.asyncio.
    
    Features:
    - Async operations
    - Connection pooling
    - Caching strategies
    - Pub/Sub support
    - Health tracking
    """
    
    # Prometheus metrics
    cache_hits_total = Counter(
        'cache_hits_total',
        'Total cache hits',
        ['cache_type']
    )
    
    cache_misses_total = Counter(
        'cache_misses_total',
        'Total cache misses',
        ['cache_type']
    )
    
    cache_operations_total = Counter(
        'cache_operations_total',
        'Total cache operations',
        ['operation']
    )
    
    cache_operation_duration = Histogram(
        'cache_operation_duration_seconds',
        'Cache operation duration',
        ['operation']
    )
    
    redis_connections_gauge = Gauge(
        'redis_connections',
        'Current Redis connections'
    )
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6379,
        password: Optional[str] = None,
        db: int = 0,
        max_connections: int = 50
    ):
        """
        Initialize Redis cache manager.
        
        Args:
            host: Redis host
            port: Redis port
            password: Redis password
            db: Redis database number
            max_connections: Maximum connections in pool
        """
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.max_connections = max_connections
        
        self.client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        
        logger.info(
            f"RedisCacheManager initialized: {host}:{port}/{db} "
            f"(max_connections: {max_connections})"
        )
    
    async def connect(self) -> None:
        """
        Create Redis connection.
        
        Raises:
            Exception: If connection fails
        """
        try:
            logger.info("Connecting to Redis...")
            
            self.client = await redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                max_connections=self.max_connections,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True
            )
            
            # Test connection
            await self.client.ping()
            
            # Update metrics
            self.redis_connections_gauge.set(1)
            
            logger.success(f"Connected to Redis: {self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        try:
            if self.pubsub:
                await self.pubsub.close()
                self.pubsub = None
            
            if self.client:
                await self.client.close()
                self.client = None
                self.redis_connections_gauge.set(0)
            
            logger.info("Redis connection closed")
            
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
    
    # ==================== CACHING OPERATIONS ====================
    
    async def cache_bars(
        self,
        symbol: str,
        timeframe: str,
        bars: List[Dict],
        max_size: int = 1000
    ) -> bool:
        """
        Cache bars using sorted sets.
        
        Uses timestamp as score for automatic ordering.
        Keeps last N bars per symbol.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            bars: List of bar dictionaries
            max_size: Maximum bars to keep
            
        Returns:
            True if successful
        """
        start_time = time.time()
        
        try:
            if not self.client:
                return False
            
            cache_key = f"bars:{symbol}:{timeframe}"
            
            # Add bars to sorted set (score = timestamp)
            for bar in bars:
                timestamp = bar.get('time')
                if isinstance(timestamp, str):
                    # Parse if string
                    from datetime import datetime
                    timestamp = datetime.fromisoformat(timestamp).timestamp()
                elif hasattr(timestamp, 'timestamp'):
                    timestamp = timestamp.timestamp()
                
                bar_json = json.dumps(bar, default=str)
                await self.client.zadd(cache_key, {bar_json: timestamp})
            
            # Keep only last N bars
            await self.client.zremrangebyrank(cache_key, 0, -(max_size + 1))
            
            # Update metrics
            self.cache_operations_total.labels(operation='cache_bars').inc()
            
            duration = time.time() - start_time
            self.cache_operation_duration.labels(operation='cache_bars').observe(duration)
            
            logger.debug(f"Cached {len(bars)} bars for {symbol} {timeframe}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error caching bars: {e}")
            return False
    
    async def get_cached_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get cached bars from sorted set.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            limit: Number of bars to retrieve
            
        Returns:
            List of bar dictionaries
        """
        start_time = time.time()
        
        try:
            if not self.client:
                self.cache_misses_total.labels(cache_type='bars').inc()
                return []
            
            cache_key = f"bars:{symbol}:{timeframe}"
            
            # Get last N bars (most recent)
            bars_json = await self.client.zrange(cache_key, -limit, -1)
            
            if not bars_json:
                self.cache_misses_total.labels(cache_type='bars').inc()
                return []
            
            # Parse JSON
            bars = [json.loads(bar_json) for bar_json in bars_json]
            
            # Update metrics
            self.cache_hits_total.labels(cache_type='bars').inc()
            
            duration = time.time() - start_time
            self.cache_operation_duration.labels(operation='get_bars').observe(duration)
            
            logger.debug(f"Retrieved {len(bars)} cached bars for {symbol} {timeframe}")
            
            return bars
            
        except Exception as e:
            logger.error(f"Error getting cached bars: {e}")
            self.cache_misses_total.labels(cache_type='bars').inc()
            return []
    
    async def cache_indicators(
        self,
        symbol: str,
        timeframe: str,
        indicators: Dict,
        ttl: int = 300
    ) -> bool:
        """
        Cache indicators using hash with TTL.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicators: Dictionary with indicator values
            ttl: Time to live in seconds (default: 5 minutes)
            
        Returns:
            True if successful
        """
        start_time = time.time()
        
        try:
            if not self.client:
                return False
            
            cache_key = f"indicators:{symbol}:{timeframe}"
            
            # Convert values to strings
            indicator_data = {}
            for key, value in indicators.items():
                if value is not None:
                    indicator_data[key] = json.dumps(value, default=str)
            
            # Store in hash
            await self.client.hset(cache_key, mapping=indicator_data)
            
            # Set TTL
            await self.client.expire(cache_key, ttl)
            
            # Update metrics
            self.cache_operations_total.labels(operation='cache_indicators').inc()
            
            duration = time.time() - start_time
            self.cache_operation_duration.labels(operation='cache_indicators').observe(duration)
            
            logger.debug(f"Cached indicators for {symbol} {timeframe} (TTL: {ttl}s)")
            
            return True
            
        except Exception as e:
            logger.error(f"Error caching indicators: {e}")
            return False
    
    async def get_cached_indicators(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[Dict]:
        """
        Get cached indicators from hash.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            
        Returns:
            Dictionary with indicators or None
        """
        start_time = time.time()
        
        try:
            if not self.client:
                self.cache_misses_total.labels(cache_type='indicators').inc()
                return None
            
            cache_key = f"indicators:{symbol}:{timeframe}"
            
            # Get all fields from hash
            indicator_data = await self.client.hgetall(cache_key)
            
            if not indicator_data:
                self.cache_misses_total.labels(cache_type='indicators').inc()
                return None
            
            # Parse JSON values
            indicators = {}
            for key, value in indicator_data.items():
                try:
                    indicators[key] = json.loads(value)
                except:
                    indicators[key] = value
            
            # Update metrics
            self.cache_hits_total.labels(cache_type='indicators').inc()
            
            duration = time.time() - start_time
            self.cache_operation_duration.labels(operation='get_indicators').observe(duration)
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error getting cached indicators: {e}")
            self.cache_misses_total.labels(cache_type='indicators').inc()
            return None
    
    async def cache_features(
        self,
        symbol: str,
        features: Dict,
        ttl: int = 300
    ) -> bool:
        """
        Cache ML features using hash with TTL.
        
        Args:
            symbol: Trading symbol
            features: Dictionary with feature values
            ttl: Time to live in seconds (default: 5 minutes)
            
        Returns:
            True if successful
        """
        start_time = time.time()
        
        try:
            if not self.client:
                return False
            
            cache_key = f"features:{symbol}:latest"
            
            # Convert values to strings
            feature_data = {}
            for key, value in features.items():
                if value is not None:
                    feature_data[key] = json.dumps(value, default=str)
            
            # Store in hash
            await self.client.hset(cache_key, mapping=feature_data)
            
            # Set TTL
            await self.client.expire(cache_key, ttl)
            
            # Update metrics
            self.cache_operations_total.labels(operation='cache_features').inc()
            
            duration = time.time() - start_time
            self.cache_operation_duration.labels(operation='cache_features').observe(duration)
            
            logger.debug(f"Cached features for {symbol} (TTL: {ttl}s)")
            
            return True
            
        except Exception as e:
            logger.error(f"Error caching features: {e}")
            return False
    
    async def get_cached_features(self, symbol: str) -> Optional[Dict]:
        """
        Get cached ML features from hash.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with features or None
        """
        start_time = time.time()
        
        try:
            if not self.client:
                self.cache_misses_total.labels(cache_type='features').inc()
                return None
            
            cache_key = f"features:{symbol}:latest"
            
            # Get all fields from hash
            feature_data = await self.client.hgetall(cache_key)
            
            if not feature_data:
                self.cache_misses_total.labels(cache_type='features').inc()
                return None
            
            # Parse JSON values
            features = {}
            for key, value in feature_data.items():
                try:
                    features[key] = json.loads(value)
                except:
                    features[key] = value
            
            # Update metrics
            self.cache_hits_total.labels(cache_type='features').inc()
            
            duration = time.time() - start_time
            self.cache_operation_duration.labels(operation='get_features').observe(duration)
            
            return features
            
        except Exception as e:
            logger.error(f"Error getting cached features: {e}")
            self.cache_misses_total.labels(cache_type='features').inc()
            return None
    
    # ==================== PUB/SUB OPERATIONS ====================
    
    async def publish(self, channel: str, message: str) -> bool:
        """
        Publish message to channel.
        
        Args:
            channel: Channel name
            message: Message to publish (JSON string)
            
        Returns:
            True if successful
        """
        try:
            if not self.client:
                return False
            
            await self.client.publish(channel, message)
            
            self.cache_operations_total.labels(operation='publish').inc()
            
            logger.debug(f"Published message to {channel}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return False
    
    async def subscribe(
        self,
        channels: List[str],
        handler: Callable[[str, str], None]
    ) -> None:
        """
        Subscribe to channels with message handler.
        
        Args:
            channels: List of channel names
            handler: Async function to handle messages (channel, message)
        """
        try:
            if not self.client:
                raise Exception("Redis client not initialized")
            
            self.pubsub = self.client.pubsub()
            await self.pubsub.subscribe(*channels)
            
            logger.info(f"Subscribed to channels: {', '.join(channels)}")
            
            # Listen for messages
            async for message in self.pubsub.listen():
                if message['type'] == 'message':
                    channel = message['channel']
                    data = message['data']
                    
                    try:
                        await handler(channel, data)
                    except Exception as e:
                        logger.error(f"Error in message handler: {e}")
            
        except Exception as e:
            logger.error(f"Error in subscribe: {e}")
    
    # ==================== HEALTH STATUS TRACKING ====================
    
    async def update_health(self, component: str, health_data: Dict) -> bool:
        """
        Update component health status.
        
        Args:
            component: Component name (e.g., 'binance_collector')
            health_data: Dictionary with health information
            
        Returns:
            True if successful
        """
        try:
            if not self.client:
                return False
            
            cache_key = "system:health"
            
            # Convert to JSON
            health_json = json.dumps(health_data, default=str)
            
            # Store in hash
            await self.client.hset(cache_key, component, health_json)
            
            logger.debug(f"Updated health status for {component}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating health status: {e}")
            return False
    
    async def get_health(self, component: Optional[str] = None) -> Optional[Dict]:
        """
        Get health status.
        
        Args:
            component: Optional component name (returns all if None)
            
        Returns:
            Dictionary with health status or None
        """
        try:
            if not self.client:
                return None
            
            cache_key = "system:health"
            
            if component:
                # Get specific component
                health_json = await self.client.hget(cache_key, component)
                if not health_json:
                    return None
                return json.loads(health_json)
            else:
                # Get all components
                health_data = await self.client.hgetall(cache_key)
                if not health_data:
                    return None
                
                # Parse JSON for each component
                health_status = {}
                for comp, health_json in health_data.items():
                    try:
                        health_status[comp] = json.loads(health_json)
                    except:
                        health_status[comp] = health_json
                
                return health_status
            
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return None
    
    # ==================== UTILITY METHODS ====================
    
    async def health_check(self) -> Dict:
        """
        Check Redis health.
        
        Returns:
            Dictionary with health status
        """
        try:
            if not self.client:
                return {'status': 'disconnected', 'error': 'Client not initialized'}
            
            # Ping Redis
            await self.client.ping()
            
            # Get info
            info = await self.client.info()
            
            return {
                'status': 'healthy',
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': info.get('used_memory_human', 'unknown'),
                'uptime_seconds': info.get('uptime_in_seconds', 0)
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def get_stats(self) -> Dict:
        """
        Get Redis manager statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            'host': self.host,
            'port': self.port,
            'db': self.db,
            'max_connections': self.max_connections,
            'connected': self.client is not None
        }
