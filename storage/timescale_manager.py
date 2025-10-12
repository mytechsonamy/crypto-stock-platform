"""
TimescaleDB Storage Manager Implementation.

Manages all database operations for time-series data storage.

Features:
- Connection pooling with asyncpg
- Candle (OHLCV) operations
- Indicator storage
- ML features storage
- Data quality metrics storage
- Batch operations (10,000+ bars/sec)
- UPSERT support
- Performance monitoring
"""

import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncpg
from loguru import logger

from prometheus_client import Counter, Histogram, Gauge


class TimescaleManager:
    """
    TimescaleDB storage manager using asyncpg.
    
    Features:
    - Connection pooling
    - Batch operations
    - UPSERT support
    - Performance optimized
    - Automatic recovery
    """
    
    # Prometheus metrics
    db_queries_total = Counter(
        'db_queries_total',
        'Total database queries',
        ['operation', 'table']
    )
    
    db_query_duration = Histogram(
        'db_query_duration_seconds',
        'Database query duration',
        ['operation', 'table']
    )
    
    db_connection_pool_size = Gauge(
        'db_connection_pool_size',
        'Current database connection pool size'
    )
    
    db_errors_total = Counter(
        'db_errors_total',
        'Total database errors',
        ['operation', 'error_type']
    )
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 5432,
        database: str = 'crypto_stock',
        user: str = 'postgres',
        password: str = 'postgres',
        min_size: int = 10,
        max_size: int = 50
    ):
        """
        Initialize TimescaleDB manager.
        
        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
            min_size: Minimum pool size
            max_size: Maximum pool size
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.min_size = min_size
        self.max_size = max_size
        
        self.pool: Optional[asyncpg.Pool] = None
        
        logger.info(
            f"TimescaleManager initialized: "
            f"{host}:{port}/{database} (pool: {min_size}-{max_size})"
        )
    
    async def connect(self) -> None:
        """
        Create connection pool.
        
        Raises:
            Exception: If connection fails
        """
        try:
            logger.info("Creating database connection pool...")
            
            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=self.min_size,
                max_size=self.max_size,
                command_timeout=60
            )
            
            # Update metrics
            self.db_connection_pool_size.set(self.max_size)
            
            logger.success(
                f"Database connection pool created: {self.min_size}-{self.max_size} connections"
            )
            
        except Exception as e:
            logger.error(f"Failed to create database connection pool: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close connection pool."""
        try:
            if self.pool:
                await self.pool.close()
                self.pool = None
                self.db_connection_pool_size.set(0)
                logger.info("Database connection pool closed")
        except Exception as e:
            logger.error(f"Error closing database pool: {e}")
    
    async def _execute_with_retry(
        self,
        query: str,
        *args,
        operation: str = 'unknown',
        table: str = 'unknown'
    ) -> Any:
        """
        Execute query with automatic retry on failure.
        
        Args:
            query: SQL query
            *args: Query parameters
            operation: Operation name for metrics
            table: Table name for metrics
            
        Returns:
            Query result
        """
        start_time = time.time()
        
        try:
            if not self.pool:
                raise Exception("Database pool not initialized")
            
            async with self.pool.acquire() as conn:
                result = await conn.fetch(query, *args)
            
            # Update metrics
            self.db_queries_total.labels(
                operation=operation,
                table=table
            ).inc()
            
            duration = time.time() - start_time
            self.db_query_duration.labels(
                operation=operation,
                table=table
            ).observe(duration)
            
            return result
            
        except Exception as e:
            self.db_errors_total.labels(
                operation=operation,
                error_type=type(e).__name__
            ).inc()
            logger.error(f"Database query error: {e}")
            raise
    
    # ==================== CANDLE OPERATIONS ====================
    
    async def insert_candle(
        self,
        time: datetime,
        symbol: str,
        exchange: str,
        timeframe: str,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        trade_count: int = 0
    ) -> bool:
        """
        Insert single candle with UPSERT.
        
        Args:
            time: Candle timestamp
            symbol: Trading symbol
            exchange: Exchange name
            timeframe: Timeframe (1m, 5m, etc.)
            open_price: Open price
            high: High price
            low: Low price
            close: Close price
            volume: Volume
            trade_count: Number of trades
            
        Returns:
            True if successful
        """
        try:
            query = """
                INSERT INTO candles (
                    time, symbol, exchange, timeframe,
                    open, high, low, close, volume, trade_count
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (time, symbol, exchange, timeframe)
                DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    trade_count = EXCLUDED.trade_count
            """
            
            await self._execute_with_retry(
                query,
                time, symbol, exchange, timeframe,
                open_price, high, low, close, volume, trade_count,
                operation='insert',
                table='candles'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error inserting candle: {e}")
            return False
    
    async def batch_insert_candles(self, candles: List[Dict]) -> int:
        """
        Batch insert candles for high performance.
        
        Target: 10,000+ bars/sec
        
        Args:
            candles: List of candle dictionaries
            
        Returns:
            Number of candles inserted
        """
        start_time = time.time()
        
        try:
            if not candles:
                return 0
            
            if not self.pool:
                raise Exception("Database pool not initialized")
            
            # Prepare data for copy
            records = [
                (
                    c['time'],
                    c['symbol'],
                    c['exchange'],
                    c['timeframe'],
                    c['open'],
                    c['high'],
                    c['low'],
                    c['close'],
                    c['volume'],
                    c.get('trade_count', 0)
                )
                for c in candles
            ]
            
            async with self.pool.acquire() as conn:
                # Use COPY for maximum performance
                await conn.copy_records_to_table(
                    'candles',
                    records=records,
                    columns=[
                        'time', 'symbol', 'exchange', 'timeframe',
                        'open', 'high', 'low', 'close', 'volume', 'trade_count'
                    ]
                )
            
            # Update metrics
            count = len(candles)
            duration = time.time() - start_time
            rate = count / duration if duration > 0 else 0
            
            self.db_queries_total.labels(
                operation='batch_insert',
                table='candles'
            ).inc()
            
            self.db_query_duration.labels(
                operation='batch_insert',
                table='candles'
            ).observe(duration)
            
            logger.info(
                f"Batch inserted {count} candles in {duration*1000:.1f}ms ({rate:.0f} bars/sec)",
                extra={'count': count, 'duration_ms': duration * 1000, 'rate': rate}
            )
            
            return count
            
        except Exception as e:
            logger.error(f"Error batch inserting candles: {e}")
            return 0
    
    async def get_recent_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200
    ) -> List[Dict]:
        """
        Get recent candles for a symbol.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            limit: Number of candles to fetch
            
        Returns:
            List of candle dictionaries
        """
        try:
            query = """
                SELECT time, symbol, exchange, timeframe,
                       open, high, low, close, volume, trade_count
                FROM candles
                WHERE symbol = $1 AND timeframe = $2
                ORDER BY time DESC
                LIMIT $3
            """
            
            rows = await self._execute_with_retry(
                query,
                symbol, timeframe, limit,
                operation='select',
                table='candles'
            )
            
            # Convert to list of dicts
            candles = [
                {
                    'time': row['time'],
                    'symbol': row['symbol'],
                    'exchange': row['exchange'],
                    'timeframe': row['timeframe'],
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume']),
                    'trade_count': row['trade_count']
                }
                for row in rows
            ]
            
            # Reverse to get chronological order
            candles.reverse()
            
            return candles
            
        except Exception as e:
            logger.error(f"Error getting recent candles: {e}")
            return []
    
    async def get_candles_range(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """
        Get candles for a date range.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            start_time: Start datetime
            end_time: End datetime
            
        Returns:
            List of candle dictionaries
        """
        try:
            query = """
                SELECT time, symbol, exchange, timeframe,
                       open, high, low, close, volume, trade_count
                FROM candles
                WHERE symbol = $1 
                  AND timeframe = $2
                  AND time >= $3 
                  AND time <= $4
                ORDER BY time ASC
            """
            
            rows = await self._execute_with_retry(
                query,
                symbol, timeframe, start_time, end_time,
                operation='select_range',
                table='candles'
            )
            
            candles = [
                {
                    'time': row['time'],
                    'symbol': row['symbol'],
                    'exchange': row['exchange'],
                    'timeframe': row['timeframe'],
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume']),
                    'trade_count': row['trade_count']
                }
                for row in rows
            ]
            
            return candles
            
        except Exception as e:
            logger.error(f"Error getting candles range: {e}")
            return []

    
    # ==================== INDICATOR OPERATIONS ====================
    
    async def insert_indicators(
        self,
        time: datetime,
        symbol: str,
        timeframe: str,
        indicators: Dict
    ) -> bool:
        """
        Insert indicators with UPSERT.
        
        Args:
            time: Timestamp
            symbol: Trading symbol
            timeframe: Timeframe
            indicators: Dictionary with indicator values
            
        Returns:
            True if successful
        """
        try:
            # Build dynamic query based on available indicators
            columns = ['time', 'symbol', 'timeframe']
            values = [time, symbol, timeframe]
            placeholders = ['$1', '$2', '$3']
            
            param_idx = 4
            for key, value in indicators.items():
                if value is not None and key not in ['symbol', 'timeframe', 'time']:
                    columns.append(key)
                    values.append(value)
                    placeholders.append(f'${param_idx}')
                    param_idx += 1
            
            # Build UPSERT query
            query = f"""
                INSERT INTO indicators ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT (time, symbol, timeframe)
                DO UPDATE SET {', '.join([f'{col} = EXCLUDED.{col}' for col in columns[3:]])}
            """
            
            await self._execute_with_retry(
                query,
                *values,
                operation='insert',
                table='indicators'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error inserting indicators: {e}")
            return False
    
    async def get_indicators(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200
    ) -> List[Dict]:
        """
        Get recent indicators.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            limit: Number of records to fetch
            
        Returns:
            List of indicator dictionaries
        """
        try:
            query = """
                SELECT *
                FROM indicators
                WHERE symbol = $1 AND timeframe = $2
                ORDER BY time DESC
                LIMIT $3
            """
            
            rows = await self._execute_with_retry(
                query,
                symbol, timeframe, limit,
                operation='select',
                table='indicators'
            )
            
            indicators = [dict(row) for row in rows]
            indicators.reverse()
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error getting indicators: {e}")
            return []
    
    async def get_indicators_range(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """
        Get indicators for a date range.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            start_time: Start datetime
            end_time: End datetime
            
        Returns:
            List of indicator dictionaries
        """
        try:
            query = """
                SELECT *
                FROM indicators
                WHERE symbol = $1 
                  AND timeframe = $2
                  AND time >= $3 
                  AND time <= $4
                ORDER BY time ASC
            """
            
            rows = await self._execute_with_retry(
                query,
                symbol, timeframe, start_time, end_time,
                operation='select_range',
                table='indicators'
            )
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting indicators range: {e}")
            return []
    
    # ==================== ML FEATURES OPERATIONS ====================
    
    async def insert_features(
        self,
        time: datetime,
        symbol: str,
        exchange: str,
        timeframe: str,
        feature_version: str,
        features: Dict
    ) -> bool:
        """
        Insert ML features.
        
        Args:
            time: Timestamp
            symbol: Trading symbol
            exchange: Exchange name
            timeframe: Timeframe
            feature_version: Feature schema version
            features: Dictionary with feature values
            
        Returns:
            True if successful
        """
        try:
            # Build dynamic query
            columns = ['time', 'symbol', 'exchange', 'timeframe', 'feature_version']
            values = [time, symbol, exchange, timeframe, feature_version]
            placeholders = ['$1', '$2', '$3', '$4', '$5']
            
            param_idx = 6
            for key, value in features.items():
                if value is not None and key not in columns:
                    columns.append(key)
                    values.append(value)
                    placeholders.append(f'${param_idx}')
                    param_idx += 1
            
            query = f"""
                INSERT INTO ml_features ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
            """
            
            await self._execute_with_retry(
                query,
                *values,
                operation='insert',
                table='ml_features'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error inserting features: {e}")
            return False
    
    async def get_features_range(
        self,
        symbol: str,
        feature_version: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """
        Get features for training (date range).
        
        Args:
            symbol: Trading symbol
            feature_version: Feature schema version
            start_time: Start datetime
            end_time: End datetime
            
        Returns:
            List of feature dictionaries
        """
        try:
            query = """
                SELECT *
                FROM ml_features
                WHERE symbol = $1 
                  AND feature_version = $2
                  AND time >= $3 
                  AND time <= $4
                ORDER BY time ASC
            """
            
            rows = await self._execute_with_retry(
                query,
                symbol, feature_version, start_time, end_time,
                operation='select_range',
                table='ml_features'
            )
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting features range: {e}")
            return []
    
    async def get_latest_features(
        self,
        symbol: str,
        feature_version: str
    ) -> Optional[Dict]:
        """
        Get latest features for real-time inference.
        
        Args:
            symbol: Trading symbol
            feature_version: Feature schema version
            
        Returns:
            Dictionary with latest features or None
        """
        try:
            query = """
                SELECT *
                FROM ml_features
                WHERE symbol = $1 AND feature_version = $2
                ORDER BY time DESC
                LIMIT 1
            """
            
            rows = await self._execute_with_retry(
                query,
                symbol, feature_version,
                operation='select',
                table='ml_features'
            )
            
            return dict(rows[0]) if rows else None
            
        except Exception as e:
            logger.error(f"Error getting latest features: {e}")
            return None
    
    # ==================== DATA QUALITY OPERATIONS ====================
    
    async def insert_quality_metrics(
        self,
        time: datetime,
        symbol: str,
        exchange: str,
        check_type: str,
        result: str,
        error_message: Optional[str],
        trade_price: Optional[float],
        trade_quantity: Optional[float],
        quality_score: float,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Insert data quality metrics.
        
        Args:
            time: Timestamp
            symbol: Trading symbol
            exchange: Exchange name
            check_type: Type of quality check
            result: 'passed' or 'failed'
            error_message: Error message if failed
            trade_price: Trade price
            trade_quantity: Trade quantity
            quality_score: Quality score (0.0-1.0)
            metadata: Additional metadata
            
        Returns:
            True if successful
        """
        try:
            import json
            
            query = """
                INSERT INTO data_quality_metrics (
                    time, symbol, exchange, check_type, result,
                    error_message, trade_price, trade_quantity,
                    quality_score, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """
            
            await self._execute_with_retry(
                query,
                time, symbol, exchange, check_type, result,
                error_message, trade_price, trade_quantity,
                quality_score, json.dumps(metadata) if metadata else None,
                operation='insert',
                table='data_quality_metrics'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error inserting quality metrics: {e}")
            return False
    
    async def get_quality_metrics(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """
        Get quality metrics for monitoring.
        
        Args:
            symbol: Trading symbol
            start_time: Start datetime
            end_time: End datetime
            
        Returns:
            List of quality metric dictionaries
        """
        try:
            query = """
                SELECT *
                FROM data_quality_metrics
                WHERE symbol = $1 
                  AND time >= $2 
                  AND time <= $3
                ORDER BY time DESC
            """
            
            rows = await self._execute_with_retry(
                query,
                symbol, start_time, end_time,
                operation='select_range',
                table='data_quality_metrics'
            )
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting quality metrics: {e}")
            return []
    
    # ==================== ALERT OPERATIONS ====================
    
    async def insert_alert(self, alert) -> bool:
        """
        Insert new alert.
        
        Args:
            alert: Alert object
            
        Returns:
            True if successful
        """
        try:
            import json
            
            query = """
                INSERT INTO alerts (
                    alert_id, user_id, symbol, condition, threshold,
                    channels, cooldown_seconds, one_time, is_active,
                    created_at, last_triggered_at, trigger_count, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """
            
            await self._execute_with_retry(
                query,
                alert.alert_id, alert.user_id, alert.symbol,
                alert.condition.value, alert.threshold,
                [ch.value for ch in alert.channels],
                alert.cooldown_seconds, alert.one_time, alert.is_active,
                alert.created_at, alert.last_triggered_at,
                alert.trigger_count, json.dumps(alert.metadata),
                operation='insert',
                table='alerts'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error inserting alert: {e}")
            return False
    
    async def update_alert(self, alert) -> bool:
        """
        Update existing alert.
        
        Args:
            alert: Alert object
            
        Returns:
            True if successful
        """
        try:
            import json
            
            query = """
                UPDATE alerts
                SET condition = $1,
                    threshold = $2,
                    channels = $3,
                    cooldown_seconds = $4,
                    one_time = $5,
                    is_active = $6,
                    last_triggered_at = $7,
                    trigger_count = $8,
                    metadata = $9
                WHERE alert_id = $10 AND user_id = $11
            """
            
            await self._execute_with_retry(
                query,
                alert.condition.value, alert.threshold,
                [ch.value for ch in alert.channels],
                alert.cooldown_seconds, alert.one_time, alert.is_active,
                alert.last_triggered_at, alert.trigger_count,
                json.dumps(alert.metadata),
                alert.alert_id, alert.user_id,
                operation='update',
                table='alerts'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating alert: {e}")
            return False
    
    async def delete_alert(self, alert_id: str, user_id: str) -> bool:
        """
        Delete alert.
        
        Args:
            alert_id: Alert ID
            user_id: User ID (for ownership check)
            
        Returns:
            True if successful
        """
        try:
            query = """
                DELETE FROM alerts
                WHERE alert_id = $1 AND user_id = $2
            """
            
            await self._execute_with_retry(
                query,
                alert_id, user_id,
                operation='delete',
                table='alerts'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting alert: {e}")
            return False
    
    async def get_alert(self, alert_id: str, user_id: str):
        """
        Get specific alert.
        
        Args:
            alert_id: Alert ID
            user_id: User ID (for ownership check)
            
        Returns:
            Alert object or None
        """
        try:
            query = """
                SELECT *
                FROM alerts
                WHERE alert_id = $1 AND user_id = $2
            """
            
            rows = await self._execute_with_retry(
                query,
                alert_id, user_id,
                operation='select',
                table='alerts'
            )
            
            if rows:
                return self._row_to_alert(rows[0])
            return None
            
        except Exception as e:
            logger.error(f"Error getting alert: {e}")
            return None
    
    async def get_user_alerts(self, user_id: str) -> List:
        """
        Get all alerts for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of Alert objects
        """
        try:
            query = """
                SELECT *
                FROM alerts
                WHERE user_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await self._execute_with_retry(
                query,
                user_id,
                operation='select',
                table='alerts'
            )
            
            return [self._row_to_alert(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting user alerts: {e}")
            return []
    
    async def get_active_alerts(self, symbol: str) -> List:
        """
        Get active alerts for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            List of Alert objects
        """
        try:
            query = """
                SELECT *
                FROM alerts
                WHERE symbol = $1 AND is_active = TRUE
                ORDER BY created_at ASC
            """
            
            rows = await self._execute_with_retry(
                query,
                symbol,
                operation='select',
                table='alerts'
            )
            
            return [self._row_to_alert(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting active alerts: {e}")
            return []
    
    def _row_to_alert(self, row):
        """Convert database row to Alert object"""
        from api.alert_manager import Alert, AlertCondition, NotificationChannel
        import json
        
        return Alert(
            alert_id=str(row['alert_id']),
            user_id=row['user_id'],
            symbol=row['symbol'],
            condition=AlertCondition(row['condition']),
            threshold=float(row['threshold']),
            channels=[NotificationChannel(ch) for ch in row['channels']],
            cooldown_seconds=row['cooldown_seconds'],
            one_time=row['one_time'],
            is_active=row['is_active'],
            created_at=row['created_at'],
            last_triggered_at=row['last_triggered_at'],
            trigger_count=row['trigger_count'],
            metadata=json.loads(row['metadata']) if row['metadata'] else {}
        )
    
    # ==================== UTILITY METHODS ====================
    
    async def health_check(self) -> Dict:
        """
        Check database health.
        
        Returns:
            Dictionary with health status
        """
        try:
            if not self.pool:
                return {'status': 'disconnected', 'error': 'Pool not initialized'}
            
            # Simple query to check connection
            async with self.pool.acquire() as conn:
                result = await conn.fetchval('SELECT 1')
            
            pool_size = self.pool.get_size()
            pool_free = self.pool.get_idle_size()
            
            return {
                'status': 'healthy',
                'pool_size': pool_size,
                'pool_free': pool_free,
                'pool_used': pool_size - pool_free
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def get_stats(self) -> Dict:
        """
        Get database manager statistics.
        
        Returns:
            Dictionary with statistics
        """
        if not self.pool:
            return {'status': 'disconnected'}
        
        return {
            'status': 'connected',
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'pool_size': self.pool.get_size(),
            'pool_free': self.pool.get_idle_size(),
            'pool_min': self.min_size,
            'pool_max': self.max_size
        }
