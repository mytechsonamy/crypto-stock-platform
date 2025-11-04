"""
Technical Indicator Calculator Implementation.

Calculates technical indicators on OHLC bar data using pandas-ta.

Features:
- RSI, MACD, Bollinger Bands
- SMA, EMA, VWAP
- Stochastic, ATR, ADX
- Volume indicators
- Pandas/NumPy vectorized operations
- Rolling window processing (200 bars)
- Performance monitoring (target: 200ms)
"""

import time
from typing import Dict, Optional, List
from datetime import datetime
import pandas as pd
import numpy as np
from loguru import logger

# Try to import pandas_ta, fall back to manual calculations if not available
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
    logger.info("pandas_ta imported successfully")
except ImportError as e:
    HAS_PANDAS_TA = False
    logger.warning(f"pandas_ta not available, using manual calculations: {e}")

from prometheus_client import Counter, Histogram, Gauge


class IndicatorCalculator:
    """
    Technical indicator calculator using pandas-ta.

    Features:
    - Multiple indicator support
    - Vectorized calculations
    - Rolling window processing
    - Performance optimized
    - Graceful handling of insufficient data
    """
    
    # Prometheus metrics
    indicators_calculated_total = Counter(
        'indicators_calculated_total',
        'Total indicators calculated',
        ['symbol', 'timeframe']
    )
    
    indicator_calculation_duration = Histogram(
        'indicator_calculation_duration_seconds',
        'Time to calculate indicators',
        ['symbol', 'timeframe']
    )
    
    indicator_errors_total = Counter(
        'indicator_errors_total',
        'Total indicator calculation errors',
        ['symbol', 'error_type']
    )
    
    bars_processed_gauge = Gauge(
        'indicator_bars_processed',
        'Number of bars processed for indicators',
        ['symbol', 'timeframe']
    )
    
    def __init__(
        self,
        config: Dict,
        db_manager=None,
        redis_manager=None,
        alert_manager=None
    ):
        """
        Initialize indicator calculator.
        
        Args:
            config: Indicator configuration from symbols.yaml
            db_manager: Database manager for fetching bars
            redis_manager: Redis manager for caching
            alert_manager: Alert manager for checking alerts (optional)
        """
        self.config = config
        self.db_manager = db_manager
        self.redis = redis_manager
        self.alert_manager = alert_manager
        
        # Configuration
        self.rsi_config = config.get('rsi', {})
        self.macd_config = config.get('macd', {})
        self.bb_config = config.get('bollinger_bands', {})
        self.sma_config = config.get('sma', {})
        self.ema_config = config.get('ema', {})
        self.stoch_config = config.get('stochastic', {})
        self.atr_config = config.get('atr', {})
        self.adx_config = config.get('adx', {})
        self.volume_sma_config = config.get('volume_sma', {})

        # Check pandas_ta availability
        if not HAS_PANDAS_TA:
            logger.warning("pandas_ta not available - indicator calculations will be skipped")
            logger.warning("Install pandas_ta with numpy>=2.2.6 to enable indicator calculations")

        # Rolling window size
        self.rolling_window_size = 200
        
        logger.info(
            f"IndicatorCalculator initialized with rolling window: {self.rolling_window_size}"
        )
    
    async def process_completed_bar(
        self,
        symbol: str,
        timeframe: str,
        completed_bar: Dict
    ) -> Optional[Dict]:
        """
        Process completed bar and calculate indicators.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            completed_bar: Completed bar data
            
        Returns:
            Dictionary with calculated indicators or None
        """
        start_time = time.time()
        
        try:
            # Fetch recent bars from database
            bars = await self._fetch_recent_bars(symbol, timeframe)
            
            if bars is None or len(bars) == 0:
                logger.warning(f"No bars found for {symbol} {timeframe}")
                return None
            
            # Convert to DataFrame
            df = self._bars_to_dataframe(bars)
            
            if df is None or len(df) < 2:
                logger.warning(f"Insufficient data for {symbol} {timeframe}: {len(df) if df is not None else 0} bars")
                return None
            
            # Update gauge
            self.bars_processed_gauge.labels(
                symbol=symbol,
                timeframe=timeframe
            ).set(len(df))
            
            # Calculate all indicators
            indicators = self._calculate_indicators(df)
            
            # Get latest indicator values
            latest_indicators = self._get_latest_values(indicators)
            
            # Add metadata
            latest_indicators['symbol'] = symbol
            latest_indicators['timeframe'] = timeframe
            latest_indicators['time'] = completed_bar.get('time')
            latest_indicators['bar_time'] = completed_bar.get('bucket_time')
            
            # Store in database
            if self.db_manager:
                await self._store_indicators(latest_indicators)
            
            # Cache in Redis
            if self.redis:
                await self._cache_indicators(latest_indicators)
            
            # Publish chart update
            if self.redis:
                await self._publish_chart_update(completed_bar, latest_indicators)
            
            # Check alerts (if alert_manager is configured)
            if hasattr(self, 'alert_manager') and self.alert_manager:
                try:
                    price = completed_bar.get('close', 0)
                    await self.alert_manager.check_alerts(
                        symbol=symbol,
                        price=price,
                        indicators=latest_indicators
                    )
                except Exception as e:
                    logger.error(f"Error checking alerts: {e}")
            
            # Update metrics
            self.indicators_calculated_total.labels(
                symbol=symbol,
                timeframe=timeframe
            ).inc()
            
            duration = time.time() - start_time
            self.indicator_calculation_duration.labels(
                symbol=symbol,
                timeframe=timeframe
            ).observe(duration)
            
            logger.info(
                f"Indicators calculated for {symbol} {timeframe} in {duration*1000:.1f}ms",
                extra={
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'bars_count': len(df),
                    'duration_ms': duration * 1000
                }
            )
            
            return latest_indicators
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}", exc_info=True)
            self.indicator_errors_total.labels(
                symbol=symbol,
                error_type=type(e).__name__
            ).inc()
            return None
    
    async def _fetch_recent_bars(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[List[Dict]]:
        """
        Fetch recent bars from database.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            
        Returns:
            List of bar dictionaries or None
        """
        try:
            if not self.db_manager:
                logger.warning("No database manager configured")
                return None

            # Fetch last N bars from database
            logger.debug(f"Fetching {self.rolling_window_size} bars for {symbol} {timeframe}")

            bars = await self.db_manager.get_recent_candles(
                symbol=symbol,
                timeframe=timeframe,
                limit=self.rolling_window_size
            )

            if bars:
                logger.debug(f"Fetched {len(bars)} bars for {symbol} {timeframe}")

            return bars

        except Exception as e:
            logger.error(f"Error fetching bars: {e}")
            return None
    
    def _bars_to_dataframe(self, bars: List[Dict]) -> Optional[pd.DataFrame]:
        """
        Convert bars to pandas DataFrame.
        
        Args:
            bars: List of bar dictionaries
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            if not bars:
                return None
            
            df = pd.DataFrame(bars)
            
            # Ensure required columns
            required_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                logger.error(f"Missing required columns. Have: {df.columns.tolist()}")
                return None
            
            # Set time as index
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'])
                df.set_index('time', inplace=True)
            
            # Sort by time
            df.sort_index(inplace=True)
            
            # Convert to float
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            return df
            
        except Exception as e:
            logger.error(f"Error converting bars to DataFrame: {e}")
            return None
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """
        Calculate all technical indicators.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Dictionary with indicator arrays
        """
        indicators = {}

        try:
            # Skip indicator calculations if pandas_ta is not available
            if not HAS_PANDAS_TA:
                logger.debug("Skipping indicator calculations - pandas_ta not available")
                return indicators

            # Extract OHLCV arrays
            open_prices = df['open'].values
            high_prices = df['high'].values
            low_prices = df['low'].values
            close_prices = df['close'].values
            volume = df['volume'].values
            
            # RSI
            indicators['rsi'] = self._calculate_rsi(close_prices)
            
            # MACD
            macd_result = self._calculate_macd(close_prices)
            indicators.update(macd_result)
            
            # Bollinger Bands
            bb_result = self._calculate_bollinger_bands(close_prices)
            indicators.update(bb_result)
            
            # SMA
            sma_result = self._calculate_sma(close_prices)
            indicators.update(sma_result)
            
            # EMA
            ema_result = self._calculate_ema(close_prices)
            indicators.update(ema_result)
            
            # VWAP
            indicators['vwap'] = self._calculate_vwap(high_prices, low_prices, close_prices, volume)
            
            # Stochastic
            stoch_result = self._calculate_stochastic(high_prices, low_prices, close_prices)
            indicators.update(stoch_result)
            
            # ATR
            indicators['atr'] = self._calculate_atr(high_prices, low_prices, close_prices)
            
            # ADX
            indicators['adx'] = self._calculate_adx(high_prices, low_prices, close_prices)
            
            # Volume SMA
            indicators['volume_sma'] = self._calculate_volume_sma(volume)
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}
    
    def _calculate_rsi(self, close: np.ndarray) -> Optional[np.ndarray]:
        """Calculate RSI indicator using pandas-ta."""
        try:
            period = self.rsi_config.get('period', 14)
            if len(close) < period:
                return None
            # pandas-ta expects a Series
            close_series = pd.Series(close)
            rsi = ta.rsi(close_series, length=period)
            return rsi.values if rsi is not None else None
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return None
    
    def _calculate_macd(self, close: np.ndarray) -> Dict:
        """Calculate MACD indicator using pandas-ta."""
        try:
            fast = self.macd_config.get('fast_period', 12)
            slow = self.macd_config.get('slow_period', 26)
            signal = self.macd_config.get('signal_period', 9)

            if len(close) < slow:
                return {'macd': None, 'macd_signal': None, 'macd_hist': None}

            # pandas-ta expects a Series
            close_series = pd.Series(close)
            macd_df = ta.macd(close_series, fast=fast, slow=slow, signal=signal)

            if macd_df is not None and not macd_df.empty:
                return {
                    'macd': macd_df[f'MACD_{fast}_{slow}_{signal}'].values,
                    'macd_signal': macd_df[f'MACDs_{fast}_{slow}_{signal}'].values,
                    'macd_hist': macd_df[f'MACDh_{fast}_{slow}_{signal}'].values
                }
            else:
                return {'macd': None, 'macd_signal': None, 'macd_hist': None}
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return {'macd': None, 'macd_signal': None, 'macd_hist': None}
    
    def _calculate_bollinger_bands(self, close: np.ndarray) -> Dict:
        """Calculate Bollinger Bands using pandas-ta."""
        try:
            period = self.bb_config.get('period', 20)
            std_dev = self.bb_config.get('std_dev', 2)

            if len(close) < period:
                return {'bb_upper': None, 'bb_middle': None, 'bb_lower': None}

            # pandas-ta expects a Series
            close_series = pd.Series(close)
            bb_df = ta.bbands(close_series, length=period, std=std_dev)

            if bb_df is not None and not bb_df.empty:
                return {
                    'bb_upper': bb_df[f'BBU_{period}_{std_dev}.0'].values,
                    'bb_middle': bb_df[f'BBM_{period}_{std_dev}.0'].values,
                    'bb_lower': bb_df[f'BBL_{period}_{std_dev}.0'].values
                }
            else:
                return {'bb_upper': None, 'bb_middle': None, 'bb_lower': None}
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return {'bb_upper': None, 'bb_middle': None, 'bb_lower': None}
    
    def _calculate_sma(self, close: np.ndarray) -> Dict:
        """Calculate SMA for multiple periods using pandas-ta."""
        result = {}
        try:
            periods = self.sma_config.get('periods', [20, 50, 100, 200])
            close_series = pd.Series(close)

            for period in periods:
                if len(close) >= period:
                    sma = ta.sma(close_series, length=period)
                    result[f'sma_{period}'] = sma.values if sma is not None else None
                else:
                    result[f'sma_{period}'] = None

            return result
        except Exception as e:
            logger.error(f"Error calculating SMA: {e}")
            return {f'sma_{p}': None for p in self.sma_config.get('periods', [20, 50, 100, 200])}
    
    def _calculate_ema(self, close: np.ndarray) -> Dict:
        """Calculate EMA for multiple periods using pandas-ta."""
        result = {}
        try:
            periods = self.ema_config.get('periods', [12, 26, 50])
            close_series = pd.Series(close)

            for period in periods:
                if len(close) >= period:
                    ema = ta.ema(close_series, length=period)
                    result[f'ema_{period}'] = ema.values if ema is not None else None
                else:
                    result[f'ema_{period}'] = None

            return result
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            return {f'ema_{p}': None for p in self.ema_config.get('periods', [12, 26, 50])}
    
    def _calculate_vwap(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray
    ) -> Optional[np.ndarray]:
        """Calculate VWAP (Volume Weighted Average Price) manually."""
        try:
            if len(close) < 1:
                return None
            
            # Typical price
            typical_price = (high + low + close) / 3
            
            # VWAP = cumsum(typical_price * volume) / cumsum(volume)
            vwap = np.cumsum(typical_price * volume) / np.cumsum(volume)
            
            return vwap
        except Exception as e:
            logger.error(f"Error calculating VWAP: {e}")
            return None
    
    def _calculate_stochastic(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray
    ) -> Dict:
        """Calculate Stochastic oscillator using pandas-ta."""
        try:
            k_period = self.stoch_config.get('k_period', 14)
            d_period = self.stoch_config.get('d_period', 3)
            smooth_k = self.stoch_config.get('smooth_k', 3)

            if len(close) < k_period:
                return {'stoch_k': None, 'stoch_d': None}

            # pandas-ta expects Series
            high_series = pd.Series(high)
            low_series = pd.Series(low)
            close_series = pd.Series(close)

            stoch_df = ta.stoch(high_series, low_series, close_series,
                               k=k_period, d=d_period, smooth_k=smooth_k)

            if stoch_df is not None and not stoch_df.empty:
                return {
                    'stoch_k': stoch_df[f'STOCHk_{k_period}_{d_period}_{smooth_k}'].values,
                    'stoch_d': stoch_df[f'STOCHd_{k_period}_{d_period}_{smooth_k}'].values
                }
            else:
                return {'stoch_k': None, 'stoch_d': None}
        except Exception as e:
            logger.error(f"Error calculating Stochastic: {e}")
            return {'stoch_k': None, 'stoch_d': None}
    
    def _calculate_atr(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray
    ) -> Optional[np.ndarray]:
        """Calculate ATR (Average True Range) using pandas-ta."""
        try:
            period = self.atr_config.get('period', 14)

            if len(close) < period:
                return None

            # pandas-ta expects Series
            high_series = pd.Series(high)
            low_series = pd.Series(low)
            close_series = pd.Series(close)

            atr = ta.atr(high_series, low_series, close_series, length=period)
            return atr.values if atr is not None else None
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return None
    
    def _calculate_adx(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray
    ) -> Optional[np.ndarray]:
        """Calculate ADX (Average Directional Index) using pandas-ta."""
        try:
            period = self.adx_config.get('period', 14)

            if len(close) < period:
                return None

            # pandas-ta expects Series
            high_series = pd.Series(high)
            low_series = pd.Series(low)
            close_series = pd.Series(close)

            adx_df = ta.adx(high_series, low_series, close_series, length=period)
            if adx_df is not None and not adx_df.empty:
                return adx_df[f'ADX_{period}'].values
            return None
        except Exception as e:
            logger.error(f"Error calculating ADX: {e}")
            return None
    
    def _calculate_volume_sma(self, volume: np.ndarray) -> Optional[np.ndarray]:
        """Calculate Volume SMA."""
        try:
            period = self.volume_sma_config.get('period', 20)

            if len(volume) < period:
                return None

            # pandas-ta expects a Series
            volume_series = pd.Series(volume)
            vol_sma = ta.sma(volume_series, length=period)
            return vol_sma.values if vol_sma is not None else None
        except Exception as e:
            logger.error(f"Error calculating Volume SMA: {e}")
            return None
    
    def _get_latest_values(self, indicators: Dict) -> Dict:
        """
        Extract latest values from indicator arrays.
        
        Args:
            indicators: Dictionary with indicator arrays
            
        Returns:
            Dictionary with latest indicator values
        """
        latest = {}
        
        for key, value in indicators.items():
            if value is None:
                latest[key] = None
            elif isinstance(value, np.ndarray):
                # Get last non-NaN value
                valid_values = value[~np.isnan(value)]
                latest[key] = float(valid_values[-1]) if len(valid_values) > 0 else None
            else:
                latest[key] = value
        
        return latest
    
    async def _store_indicators(self, indicators: Dict) -> None:
        """
        Store indicators in database.

        Args:
            indicators: Indicator values
        """
        try:
            if not self.db_manager:
                return

            symbol = indicators.get('symbol')
            timeframe = indicators.get('timeframe')
            time = indicators.get('time')

            if not all([symbol, timeframe, time]):
                logger.warning(f"Missing required fields for indicator storage: {indicators.keys()}")
                return

            # Remove metadata fields before storing
            indicator_data = {k: v for k, v in indicators.items()
                            if k not in ['symbol', 'timeframe', 'time', 'bar_time']}

            # Store in database
            success = await self.db_manager.insert_indicators(
                time=time,
                symbol=symbol,
                timeframe=timeframe,
                indicators=indicator_data
            )

            if success:
                logger.debug(f"Stored {len(indicator_data)} indicators for {symbol} {timeframe}")

        except Exception as e:
            logger.error(f"Error storing indicators: {e}")
    
    async def _cache_indicators(self, indicators: Dict) -> None:
        """
        Cache indicators in Redis with TTL.
        
        Args:
            indicators: Indicator values
        """
        try:
            if not self.redis:
                return
            
            import json
            
            symbol = indicators.get('symbol')
            timeframe = indicators.get('timeframe')
            cache_key = f"indicators:{symbol}:{timeframe}"
            
            # Cache with 5-minute TTL
            ttl = 300
            
            # Placeholder for Redis caching
            logger.debug(f"Caching indicators: {cache_key} (TTL: {ttl}s)")
            
        except Exception as e:
            logger.error(f"Error caching indicators: {e}")
    
    async def _publish_chart_update(self, bar: Dict, indicators: Dict) -> None:
        """
        Publish chart update with bar + indicators.
        
        Args:
            bar: Completed bar data
            indicators: Calculated indicators
        """
        try:
            if not self.redis:
                return
            
            import json
            
            # Combine bar and indicators
            chart_update = {
                'symbol': bar.get('symbol'),
                'timeframe': bar.get('timeframe'),
                'time': int(bar.get('bucket_time', 0) * 1000),
                'bar': {
                    'open': bar.get('open'),
                    'high': bar.get('high'),
                    'low': bar.get('low'),
                    'close': bar.get('close'),
                    'volume': bar.get('volume')
                },
                'indicators': {k: v for k, v in indicators.items() 
                              if k not in ['symbol', 'timeframe', 'time', 'bar_time']}
            }
            
            # Publish to chart_updates channel
            # await self.redis.publish('chart_updates', json.dumps(chart_update))
            
            logger.debug(f"Published chart update for {bar.get('symbol')} {bar.get('timeframe')}")
            
        except Exception as e:
            logger.error(f"Error publishing chart update: {e}")
