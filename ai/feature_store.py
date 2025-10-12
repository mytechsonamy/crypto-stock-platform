"""
Feature Store Implementation for ML/AI.

Engineers features from OHLCV data and technical indicators for machine learning models.

Features:
- Price features (returns, momentum)
- Volatility features (rolling std, high-low ratio)
- Volume features (change, momentum, ratios)
- Technical features (RSI zones, MACD crossovers, BB position)
- Time features (hour, day_of_week, market hours)
- Trend features (SMA distance, price position)
- Feature versioning
- Batch and real-time serving
"""

import time
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from loguru import logger

from prometheus_client import Counter, Histogram, Gauge


class FeatureStore:
    """
    Feature engineering and storage for ML models.
    
    Features:
    - Automated feature engineering
    - Feature versioning
    - Batch and real-time serving
    - TimescaleDB and Redis storage
    """
    
    # Prometheus metrics
    features_calculated_total = Counter(
        'features_calculated_total',
        'Total features calculated',
        ['symbol', 'version']
    )
    
    feature_calculation_duration = Histogram(
        'feature_calculation_duration_seconds',
        'Time to calculate features',
        ['symbol']
    )
    
    features_stored_total = Counter(
        'features_stored_total',
        'Total features stored',
        ['symbol', 'storage_type']
    )
    
    feature_serving_duration = Histogram(
        'feature_serving_duration_seconds',
        'Time to serve features',
        ['mode']  # batch or realtime
    )
    
    def __init__(
        self,
        db_manager=None,
        redis_manager=None,
        feature_version: str = "v1.0"
    ):
        """
        Initialize feature store.
        
        Args:
            db_manager: Database manager for storing features
            redis_manager: Redis manager for caching
            feature_version: Feature schema version
        """
        self.db_manager = db_manager
        self.redis = redis_manager
        self.feature_version = feature_version
        
        logger.info(f"FeatureStore initialized with version: {feature_version}")
    
    async def engineer_features(
        self,
        symbol: str,
        bars_df: pd.DataFrame,
        indicators: Dict
    ) -> Optional[pd.DataFrame]:
        """
        Engineer features from bars and indicators.
        
        Args:
            symbol: Trading symbol
            bars_df: DataFrame with OHLCV data
            indicators: Dictionary with calculated indicators
            
        Returns:
            DataFrame with engineered features
        """
        start_time = time.time()
        
        try:
            if bars_df is None or len(bars_df) < 2:
                logger.warning(f"Insufficient data for feature engineering: {symbol}")
                return None
            
            # Create features DataFrame
            features_df = bars_df.copy()
            
            # Price features
            features_df = self._add_price_features(features_df)
            
            # Volatility features
            features_df = self._add_volatility_features(features_df)
            
            # Volume features
            features_df = self._add_volume_features(features_df)
            
            # Technical features (from indicators)
            features_df = self._add_technical_features(features_df, indicators)
            
            # Time features
            features_df = self._add_time_features(features_df)
            
            # Trend features
            features_df = self._add_trend_features(features_df, indicators)
            
            # Clean NaN values
            features_df = self._clean_nan_values(features_df)
            
            # Add metadata
            features_df['symbol'] = symbol
            features_df['feature_version'] = self.feature_version
            features_df['engineered_at'] = datetime.now()
            
            # Update metrics
            self.features_calculated_total.labels(
                symbol=symbol,
                version=self.feature_version
            ).inc()
            
            duration = time.time() - start_time
            self.feature_calculation_duration.labels(symbol=symbol).observe(duration)
            
            logger.info(
                f"Features engineered for {symbol}: {len(features_df.columns)} features in {duration*1000:.1f}ms",
                extra={
                    'symbol': symbol,
                    'feature_count': len(features_df.columns),
                    'row_count': len(features_df),
                    'duration_ms': duration * 1000
                }
            )
            
            return features_df
            
        except Exception as e:
            logger.error(f"Error engineering features: {e}", exc_info=True)
            return None
    
    def _add_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add price-based features.
        
        Features:
        - Returns (1, 5, 10 periods)
        - Log returns
        - Price momentum
        """
        try:
            close = df['close']
            
            # Returns
            df['return_1'] = close.pct_change(1)
            df['return_5'] = close.pct_change(5)
            df['return_10'] = close.pct_change(10)
            
            # Log returns
            df['log_return'] = np.log(close / close.shift(1))
            
            # Price momentum (rate of change)
            df['price_momentum_5'] = (close - close.shift(5)) / close.shift(5)
            df['price_momentum_10'] = (close - close.shift(10)) / close.shift(10)
            
            # Price acceleration (change in momentum)
            df['price_acceleration'] = df['return_1'].diff()
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding price features: {e}")
            return df
    
    def _add_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add volatility features.
        
        Features:
        - Rolling standard deviation (5, 10, 20 periods)
        - High-low ratio
        - True range
        """
        try:
            close = df['close']
            high = df['high']
            low = df['low']
            
            # Rolling standard deviation
            df['volatility_5'] = close.rolling(window=5).std()
            df['volatility_10'] = close.rolling(window=10).std()
            df['volatility_20'] = close.rolling(window=20).std()
            
            # High-low ratio
            df['high_low_ratio'] = (high - low) / close
            
            # True range (for ATR calculation)
            df['true_range'] = np.maximum(
                high - low,
                np.maximum(
                    abs(high - close.shift(1)),
                    abs(low - close.shift(1))
                )
            )
            
            # Volatility trend
            df['volatility_trend'] = df['volatility_10'] / df['volatility_20']
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding volatility features: {e}")
            return df
    
    def _add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add volume features.
        
        Features:
        - Volume change
        - Volume momentum
        - Volume ratio
        - Volume-price trend
        """
        try:
            volume = df['volume']
            close = df['close']
            
            # Volume change
            df['volume_change'] = volume.pct_change(1)
            
            # Volume momentum
            df['volume_momentum_5'] = (volume - volume.shift(5)) / volume.shift(5)
            df['volume_momentum_10'] = (volume - volume.shift(10)) / volume.shift(10)
            
            # Volume ratio (current vs average)
            df['volume_ratio_5'] = volume / volume.rolling(window=5).mean()
            df['volume_ratio_20'] = volume / volume.rolling(window=20).mean()
            
            # Volume-price trend (OBV-like)
            df['volume_price_trend'] = (
                volume * np.sign(close - close.shift(1))
            ).cumsum()
            
            # Normalized volume-price trend
            df['volume_price_trend_norm'] = (
                df['volume_price_trend'] / df['volume_price_trend'].rolling(window=20).std()
            )
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding volume features: {e}")
            return df
    
    def _add_technical_features(
        self,
        df: pd.DataFrame,
        indicators: Dict
    ) -> pd.DataFrame:
        """
        Add technical indicator features.
        
        Features:
        - RSI zones (oversold, neutral, overbought)
        - MACD crossovers
        - Bollinger Band position and squeeze
        """
        try:
            # RSI zones
            if 'rsi' in indicators and indicators['rsi'] is not None:
                rsi = indicators['rsi']
                if isinstance(rsi, np.ndarray):
                    rsi = rsi[-len(df):]  # Match DataFrame length
                    df['rsi'] = rsi
                    df['rsi_oversold'] = (rsi < 30).astype(int)
                    df['rsi_overbought'] = (rsi > 70).astype(int)
                    df['rsi_neutral'] = ((rsi >= 30) & (rsi <= 70)).astype(int)
            
            # MACD crossovers
            if 'macd' in indicators and 'macd_signal' in indicators:
                macd = indicators['macd']
                signal = indicators['macd_signal']
                if isinstance(macd, np.ndarray) and isinstance(signal, np.ndarray):
                    macd = macd[-len(df):]
                    signal = signal[-len(df):]
                    df['macd'] = macd
                    df['macd_signal'] = signal
                    df['macd_diff'] = macd - signal
                    df['macd_crossover'] = (
                        (df['macd_diff'] > 0) & (df['macd_diff'].shift(1) <= 0)
                    ).astype(int)
                    df['macd_crossunder'] = (
                        (df['macd_diff'] < 0) & (df['macd_diff'].shift(1) >= 0)
                    ).astype(int)
            
            # Bollinger Bands
            if all(k in indicators for k in ['bb_upper', 'bb_middle', 'bb_lower']):
                bb_upper = indicators['bb_upper']
                bb_middle = indicators['bb_middle']
                bb_lower = indicators['bb_lower']
                
                if all(isinstance(x, np.ndarray) for x in [bb_upper, bb_middle, bb_lower]):
                    bb_upper = bb_upper[-len(df):]
                    bb_middle = bb_middle[-len(df):]
                    bb_lower = bb_lower[-len(df):]
                    
                    df['bb_upper'] = bb_upper
                    df['bb_middle'] = bb_middle
                    df['bb_lower'] = bb_lower
                    
                    # BB position (0 = at lower band, 1 = at upper band)
                    df['bb_position'] = (
                        (df['close'] - bb_lower) / (bb_upper - bb_lower)
                    )
                    
                    # BB squeeze (narrow bands indicate low volatility)
                    df['bb_width'] = (bb_upper - bb_lower) / bb_middle
                    df['bb_squeeze'] = (df['bb_width'] < df['bb_width'].rolling(window=20).mean()).astype(int)
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding technical features: {e}")
            return df
    
    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add time-based features.
        
        Features:
        - Hour of day
        - Day of week
        - Is market open (placeholder)
        """
        try:
            # Ensure index is datetime
            if not isinstance(df.index, pd.DatetimeIndex):
                return df
            
            # Hour of day
            df['hour'] = df.index.hour
            
            # Day of week (0 = Monday, 6 = Sunday)
            df['day_of_week'] = df.index.dayofweek
            
            # Is weekend
            df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
            
            # Market session (placeholder - needs exchange-specific logic)
            # For crypto: always open
            # For stocks: 9:30-16:00 ET
            df['is_market_open'] = 1  # Placeholder
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding time features: {e}")
            return df
    
    def _add_trend_features(
        self,
        df: pd.DataFrame,
        indicators: Dict
    ) -> pd.DataFrame:
        """
        Add trend features.
        
        Features:
        - SMA distance
        - Price above/below SMA
        - Trend strength
        """
        try:
            close = df['close']
            
            # SMA distance
            for period in [20, 50, 100, 200]:
                sma_key = f'sma_{period}'
                if sma_key in indicators and indicators[sma_key] is not None:
                    sma = indicators[sma_key]
                    if isinstance(sma, np.ndarray):
                        sma = sma[-len(df):]
                        df[sma_key] = sma
                        df[f'sma_{period}_distance'] = (close - sma) / sma
                        df[f'price_above_sma_{period}'] = (close > sma).astype(int)
            
            # Trend strength (using multiple SMAs)
            if 'sma_20' in df.columns and 'sma_50' in df.columns:
                df['trend_strength'] = (df['sma_20'] - df['sma_50']) / df['sma_50']
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding trend features: {e}")
            return df
    
    def _clean_nan_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean NaN values using backfill strategy.
        
        Args:
            df: DataFrame with features
            
        Returns:
            Cleaned DataFrame
        """
        try:
            # Backfill NaN values
            df = df.fillna(method='bfill')
            
            # Forward fill remaining NaNs
            df = df.fillna(method='ffill')
            
            # Fill any remaining NaNs with 0
            df = df.fillna(0)
            
            return df
            
        except Exception as e:
            logger.error(f"Error cleaning NaN values: {e}")
            return df

    
    async def store_features(
        self,
        features_df: pd.DataFrame,
        storage_type: str = 'both'
    ) -> bool:
        """
        Store features in database and/or Redis.
        
        Args:
            features_df: DataFrame with features
            storage_type: 'database', 'redis', or 'both'
            
        Returns:
            True if successful
        """
        try:
            symbol = features_df['symbol'].iloc[0] if 'symbol' in features_df.columns else 'unknown'
            
            success = True
            
            # Store in database
            if storage_type in ['database', 'both'] and self.db_manager:
                db_success = await self._store_features_database(features_df)
                success = success and db_success
                if db_success:
                    self.features_stored_total.labels(
                        symbol=symbol,
                        storage_type='database'
                    ).inc()
            
            # Store in Redis
            if storage_type in ['redis', 'both'] and self.redis:
                redis_success = await self._store_features_redis(features_df)
                success = success and redis_success
                if redis_success:
                    self.features_stored_total.labels(
                        symbol=symbol,
                        storage_type='redis'
                    ).inc()
            
            return success
            
        except Exception as e:
            logger.error(f"Error storing features: {e}")
            return False
    
    async def _store_features_database(self, features_df: pd.DataFrame) -> bool:
        """Store features in TimescaleDB ml_features table."""
        try:
            if not self.db_manager:
                return False
            
            symbol = features_df['symbol'].iloc[0]
            
            # Placeholder for database storage
            logger.debug(f"Storing {len(features_df)} feature rows for {symbol} in database")
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing features in database: {e}")
            return False
    
    async def _store_features_redis(self, features_df: pd.DataFrame) -> bool:
        """Store latest features in Redis with TTL."""
        try:
            if not self.redis:
                return False
            
            symbol = features_df['symbol'].iloc[0]
            
            # Get latest row
            latest_features = features_df.iloc[-1].to_dict()
            
            # Convert to JSON-serializable format
            for key, value in latest_features.items():
                if isinstance(value, (np.integer, np.floating)):
                    latest_features[key] = float(value)
                elif isinstance(value, pd.Timestamp):
                    latest_features[key] = value.isoformat()
            
            import json
            cache_key = f"features:{symbol}:latest"
            ttl = 300  # 5 minutes
            
            # Placeholder for Redis storage
            logger.debug(f"Caching latest features for {symbol} (TTL: {ttl}s)")
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing features in Redis: {e}")
            return False
    
    async def get_features_batch(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Get features for training (batch mode).
        
        Args:
            symbol: Trading symbol
            start_time: Start datetime
            end_time: End datetime
            
        Returns:
            DataFrame with features for the time range
        """
        start = time.time()
        
        try:
            if not self.db_manager:
                logger.warning("No database manager configured")
                return None
            
            # Placeholder for database query
            logger.debug(
                f"Fetching batch features for {symbol} "
                f"from {start_time} to {end_time}"
            )
            
            # This would query ml_features table
            # features_df = await self.db_manager.get_features_range(
            #     symbol, start_time, end_time
            # )
            
            duration = time.time() - start
            self.feature_serving_duration.labels(mode='batch').observe(duration)
            
            logger.info(
                f"Batch features served for {symbol} in {duration*1000:.1f}ms",
                extra={'symbol': symbol, 'duration_ms': duration * 1000}
            )
            
            return None  # Placeholder
            
        except Exception as e:
            logger.error(f"Error getting batch features: {e}")
            return None
    
    async def get_features_realtime(self, symbol: str) -> Optional[Dict]:
        """
        Get latest features for inference (real-time mode).
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with latest features
        """
        start = time.time()
        
        try:
            if not self.redis:
                logger.warning("No Redis manager configured")
                return None
            
            import json
            cache_key = f"features:{symbol}:latest"
            
            # Placeholder for Redis retrieval
            logger.debug(f"Fetching real-time features for {symbol}")
            
            # This would get from Redis
            # features_json = await self.redis.get(cache_key)
            # features = json.loads(features_json) if features_json else None
            
            duration = time.time() - start
            self.feature_serving_duration.labels(mode='realtime').observe(duration)
            
            if duration * 1000 > 100:
                logger.warning(
                    f"Real-time feature serving exceeded target: {duration*1000:.1f}ms"
                )
            
            logger.debug(
                f"Real-time features served for {symbol} in {duration*1000:.1f}ms"
            )
            
            return None  # Placeholder
            
        except Exception as e:
            logger.error(f"Error getting real-time features: {e}")
            return None
    
    def get_feature_names(self) -> List[str]:
        """
        Get list of all feature names.
        
        Returns:
            List of feature column names
        """
        # This would return all feature names based on the engineering logic
        feature_names = [
            # Price features
            'return_1', 'return_5', 'return_10',
            'log_return', 'price_momentum_5', 'price_momentum_10',
            'price_acceleration',
            
            # Volatility features
            'volatility_5', 'volatility_10', 'volatility_20',
            'high_low_ratio', 'true_range', 'volatility_trend',
            
            # Volume features
            'volume_change', 'volume_momentum_5', 'volume_momentum_10',
            'volume_ratio_5', 'volume_ratio_20',
            'volume_price_trend', 'volume_price_trend_norm',
            
            # Technical features
            'rsi', 'rsi_oversold', 'rsi_overbought', 'rsi_neutral',
            'macd', 'macd_signal', 'macd_diff',
            'macd_crossover', 'macd_crossunder',
            'bb_upper', 'bb_middle', 'bb_lower',
            'bb_position', 'bb_width', 'bb_squeeze',
            
            # Time features
            'hour', 'day_of_week', 'is_weekend', 'is_market_open',
            
            # Trend features
            'sma_20', 'sma_50', 'sma_100', 'sma_200',
            'sma_20_distance', 'sma_50_distance',
            'sma_100_distance', 'sma_200_distance',
            'price_above_sma_20', 'price_above_sma_50',
            'price_above_sma_100', 'price_above_sma_200',
            'trend_strength'
        ]
        
        return feature_names
    
    def get_stats(self) -> Dict:
        """
        Get feature store statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            'feature_version': self.feature_version,
            'feature_count': len(self.get_feature_names()),
            'feature_names': self.get_feature_names()
        }
