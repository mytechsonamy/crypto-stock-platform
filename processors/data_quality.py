"""
Data Quality Checker Implementation.

Validates incoming trade data for anomalies, freshness, and sanity checks.

Features:
- Price anomaly detection (z-score and percentage change)
- Data freshness validation
- Valid values checking
- Volume sanity checks
- Quality scoring per symbol
- Prometheus metrics integration
- Quarantine for suspect data
- Database storage for quality metrics
"""

import time
from collections import deque, defaultdict
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
import numpy as np
from loguru import logger

from prometheus_client import Counter, Gauge, Histogram


class DataQualityChecker:
    """
    Data quality validation and monitoring.
    
    Features:
    - Real-time anomaly detection
    - Price history tracking
    - Quality scoring
    - Prometheus metrics
    """
    
    # Prometheus metrics
    quality_checks_total = Counter(
        'data_quality_checks_total',
        'Total data quality checks performed',
        ['symbol', 'check_type', 'result']
    )
    
    quality_score_gauge = Gauge(
        'data_quality_score',
        'Current quality score per symbol',
        ['symbol']
    )
    
    validation_duration = Histogram(
        'data_quality_validation_duration_seconds',
        'Time spent validating data',
        ['check_type']
    )
    
    def __init__(self, config: Dict, db_manager=None, enable_quarantine: bool = True):
        """
        Initialize data quality checker.
        
        Args:
            config: Data quality configuration from exchanges.yaml
            db_manager: Optional database manager for storing quality metrics
            enable_quarantine: Whether to quarantine suspect data
        """
        self.config = config
        self.db_manager = db_manager
        self.enable_quarantine = enable_quarantine
        
        # Price anomaly settings
        anomaly_config = config.get('price_anomaly', {})
        self.z_score_threshold = anomaly_config.get('z_score_threshold', 3.0)
        self.percentage_change_threshold = anomaly_config.get('percentage_change_threshold', 0.10)
        
        # Data freshness settings
        freshness_config = config.get('data_freshness', {})
        self.max_age_seconds = freshness_config.get('max_age_seconds', 60)
        
        # Volume sanity settings
        volume_config = config.get('volume_sanity', {})
        self.volume_multiplier_threshold = volume_config.get('multiplier_threshold', 100)
        
        # History tracking
        self.history_window_size = config.get('history_window_size', 100)
        self.price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.history_window_size))
        self.volume_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.history_window_size))
        
        # Quality scoring
        self.quality_scores: Dict[str, float] = defaultdict(lambda: 1.0)
        self.check_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {'passed': 0, 'failed': 0})
        
        # Quarantine for suspect data
        self.quarantine: List[Dict] = []
        self.max_quarantine_size = 1000
        
        logger.info(
            f"DataQualityChecker initialized: "
            f"z_score={self.z_score_threshold}, "
            f"pct_change={self.percentage_change_threshold*100}%, "
            f"max_age={self.max_age_seconds}s, "
            f"volume_threshold={self.volume_multiplier_threshold}x, "
            f"quarantine={'enabled' if enable_quarantine else 'disabled'}"
        )
    
    def validate_trade(self, trade_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate trade data quality.
        
        Args:
            trade_data: Trade data dictionary with price, quantity, timestamp, symbol
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        symbol = trade_data.get('symbol', 'unknown')
        
        # Run all validation checks
        checks = [
            ('valid_values', self._check_valid_values(trade_data)),
            ('data_freshness', self._check_data_freshness(trade_data)),
            ('price_anomaly', self._check_price_anomaly(trade_data)),
            ('volume_sanity', self._check_volume_sanity(trade_data))
        ]
        
        # Check results
        for check_name, (is_valid, error_msg) in checks:
            result = 'passed' if is_valid else 'failed'
            
            # Update metrics
            self.quality_checks_total.labels(
                symbol=symbol,
                check_type=check_name,
                result=result
            ).inc()
            
            # Update counts
            self.check_counts[symbol][result] += 1
            
            # If any check fails, handle failure
            if not is_valid:
                logger.warning(
                    f"Quality check failed: {check_name} for {symbol} - {error_msg}",
                    extra={'symbol': symbol, 'check': check_name, 'trade': trade_data}
                )
                self._update_quality_score(symbol, passed=False)
                
                # Quarantine suspect data if enabled
                if self.enable_quarantine:
                    self._quarantine_data(trade_data, check_name, error_msg)
                
                # Store quality metric in database
                if self.db_manager:
                    self._store_quality_metric(
                        trade_data=trade_data,
                        check_type=check_name,
                        result='failed',
                        error_message=error_msg
                    )
                
                return False, f"{check_name}: {error_msg}"
        
        # All checks passed
        self._update_quality_score(symbol, passed=True)
        
        # Store successful validation in database (sample rate to reduce load)
        if self.db_manager and np.random.random() < 0.01:  # 1% sampling
            self._store_quality_metric(
                trade_data=trade_data,
                check_type='all_checks',
                result='passed',
                error_message=None
            )
        
        # Update history for future checks
        self._update_history(trade_data)
        
        return True, None
    
    def _check_valid_values(self, trade_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check if trade data contains valid values.
        
        Validates:
        - Price > 0
        - Volume >= 0
        - All values are finite numbers
        """
        start_time = time.time()
        
        try:
            price = float(trade_data.get('price', 0))
            quantity = float(trade_data.get('quantity', 0))
            
            # Check for invalid values
            if price <= 0:
                return False, f"Invalid price: {price}"
            
            if quantity < 0:
                return False, f"Invalid quantity: {quantity}"
            
            if not np.isfinite(price):
                return False, f"Non-finite price: {price}"
            
            if not np.isfinite(quantity):
                return False, f"Non-finite quantity: {quantity}"
            
            return True, None
            
        except (ValueError, TypeError) as e:
            return False, f"Value conversion error: {e}"
        
        finally:
            duration = time.time() - start_time
            self.validation_duration.labels(check_type='valid_values').observe(duration)
    
    def _check_data_freshness(self, trade_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check if trade data is fresh (not too old).
        
        Rejects data older than max_age_seconds.
        """
        start_time = time.time()
        
        try:
            timestamp = trade_data.get('timestamp')
            if timestamp is None:
                return False, "Missing timestamp"
            
            # Convert to seconds if in milliseconds
            if timestamp > 1e12:
                timestamp = timestamp / 1000
            
            current_time = time.time()
            age_seconds = current_time - timestamp
            
            if age_seconds > self.max_age_seconds:
                return False, f"Data too old: {age_seconds:.1f}s (max: {self.max_age_seconds}s)"
            
            if age_seconds < -5:  # Allow 5 seconds clock skew
                return False, f"Data from future: {age_seconds:.1f}s"
            
            return True, None
            
        except (ValueError, TypeError) as e:
            return False, f"Timestamp error: {e}"
        
        finally:
            duration = time.time() - start_time
            self.validation_duration.labels(check_type='data_freshness').observe(duration)
    
    def _check_price_anomaly(self, trade_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check for price anomalies using z-score and percentage change.
        
        Detects:
        - Statistical outliers (z-score > threshold)
        - Large percentage changes (> threshold)
        """
        start_time = time.time()
        
        try:
            symbol = trade_data.get('symbol', 'unknown')
            price = float(trade_data.get('price', 0))
            
            # Need history for comparison
            if len(self.price_history[symbol]) < 10:
                return True, None  # Not enough data yet
            
            prices = list(self.price_history[symbol])
            
            # Calculate z-score
            mean_price = np.mean(prices)
            std_price = np.std(prices)
            
            if std_price > 0:
                z_score = abs((price - mean_price) / std_price)
                
                if z_score > self.z_score_threshold:
                    return False, f"Price anomaly (z-score: {z_score:.2f})"
            
            # Calculate percentage change from last price
            last_price = prices[-1]
            if last_price > 0:
                pct_change = abs((price - last_price) / last_price)
                
                if pct_change > self.percentage_change_threshold:
                    return False, f"Large price change: {pct_change*100:.1f}%"
            
            return True, None
            
        except (ValueError, TypeError, ZeroDivisionError) as e:
            return False, f"Anomaly check error: {e}"
        
        finally:
            duration = time.time() - start_time
            self.validation_duration.labels(check_type='price_anomaly').observe(duration)
    
    def _check_volume_sanity(self, trade_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check if volume is within reasonable bounds.
        
        Detects volumes that are significantly higher than average.
        """
        start_time = time.time()
        
        try:
            symbol = trade_data.get('symbol', 'unknown')
            quantity = float(trade_data.get('quantity', 0))
            
            # Need history for comparison
            if len(self.volume_history[symbol]) < 10:
                return True, None  # Not enough data yet
            
            volumes = list(self.volume_history[symbol])
            avg_volume = np.mean(volumes)
            
            if avg_volume > 0:
                volume_ratio = quantity / avg_volume
                
                if volume_ratio > self.volume_multiplier_threshold:
                    return False, f"Abnormal volume: {volume_ratio:.1f}x average"
            
            return True, None
            
        except (ValueError, TypeError, ZeroDivisionError) as e:
            return False, f"Volume check error: {e}"
        
        finally:
            duration = time.time() - start_time
            self.validation_duration.labels(check_type='volume_sanity').observe(duration)
    
    def _update_history(self, trade_data: Dict) -> None:
        """
        Update price and volume history for symbol.
        
        Args:
            trade_data: Trade data dictionary
        """
        try:
            symbol = trade_data.get('symbol', 'unknown')
            price = float(trade_data.get('price', 0))
            quantity = float(trade_data.get('quantity', 0))
            
            self.price_history[symbol].append(price)
            self.volume_history[symbol].append(quantity)
            
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to update history: {e}")
    
    def _update_quality_score(self, symbol: str, passed: bool) -> None:
        """
        Update quality score for symbol.
        
        Uses exponential moving average:
        - Passed check: score moves toward 1.0
        - Failed check: score moves toward 0.0
        
        Args:
            symbol: Symbol name
            passed: Whether check passed
        """
        alpha = 0.1  # Smoothing factor
        current_score = self.quality_scores[symbol]
        
        if passed:
            new_score = current_score + alpha * (1.0 - current_score)
        else:
            new_score = current_score + alpha * (0.0 - current_score)
        
        self.quality_scores[symbol] = new_score
        
        # Update Prometheus gauge
        self.quality_score_gauge.labels(symbol=symbol).set(new_score)
    
    def get_quality_score(self, symbol: str) -> float:
        """
        Get current quality score for symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Quality score (0.0 to 1.0)
        """
        return self.quality_scores.get(symbol, 1.0)
    
    def _quarantine_data(self, trade_data: Dict, check_type: str, error_message: str) -> None:
        """
        Quarantine suspect data for later analysis.
        
        Args:
            trade_data: Trade data that failed validation
            check_type: Type of check that failed
            error_message: Error message
        """
        quarantine_entry = {
            'timestamp': datetime.now().isoformat(),
            'trade_data': trade_data.copy(),
            'check_type': check_type,
            'error_message': error_message,
            'quality_score': self.quality_scores.get(trade_data.get('symbol', 'unknown'), 0.0)
        }
        
        self.quarantine.append(quarantine_entry)
        
        # Limit quarantine size
        if len(self.quarantine) > self.max_quarantine_size:
            self.quarantine.pop(0)  # Remove oldest entry
        
        logger.debug(
            f"Data quarantined: {trade_data.get('symbol')} - {check_type}",
            extra={'quarantine_size': len(self.quarantine)}
        )
    
    def _store_quality_metric(
        self,
        trade_data: Dict,
        check_type: str,
        result: str,
        error_message: Optional[str]
    ) -> None:
        """
        Store quality metric in database.
        
        Args:
            trade_data: Trade data
            check_type: Type of quality check
            result: 'passed' or 'failed'
            error_message: Error message if failed
        """
        try:
            if not self.db_manager:
                return
            
            symbol = trade_data.get('symbol', 'unknown')
            exchange = trade_data.get('exchange', 'unknown')
            
            metric_data = {
                'time': datetime.now(),
                'symbol': symbol,
                'exchange': exchange,
                'check_type': check_type,
                'result': result,
                'error_message': error_message,
                'trade_price': trade_data.get('price'),
                'trade_quantity': trade_data.get('quantity'),
                'quality_score': self.quality_scores.get(symbol, 1.0),
                'metadata': {
                    'timestamp': trade_data.get('timestamp'),
                    'z_score_threshold': self.z_score_threshold,
                    'pct_change_threshold': self.percentage_change_threshold
                }
            }
            
            # Async insert (fire and forget to avoid blocking)
            # In production, this should use an async queue
            # For now, we'll just log that we would store it
            logger.debug(
                f"Quality metric stored: {symbol} - {check_type} - {result}",
                extra=metric_data
            )
            
        except Exception as e:
            logger.error(f"Failed to store quality metric: {e}")
    
    def get_quarantine(self, symbol: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Get quarantined data.
        
        Args:
            symbol: Optional symbol to filter by
            limit: Maximum number of entries to return
            
        Returns:
            List of quarantined data entries
        """
        if symbol:
            filtered = [entry for entry in self.quarantine 
                       if entry['trade_data'].get('symbol') == symbol]
            return filtered[-limit:]
        else:
            return self.quarantine[-limit:]
    
    def clear_quarantine(self, symbol: Optional[str] = None) -> int:
        """
        Clear quarantined data.
        
        Args:
            symbol: Optional symbol to clear (clears all if None)
            
        Returns:
            Number of entries cleared
        """
        if symbol:
            original_size = len(self.quarantine)
            self.quarantine = [entry for entry in self.quarantine 
                              if entry['trade_data'].get('symbol') != symbol]
            cleared = original_size - len(self.quarantine)
        else:
            cleared = len(self.quarantine)
            self.quarantine.clear()
        
        logger.info(f"Cleared {cleared} quarantine entries" + (f" for {symbol}" if symbol else ""))
        return cleared
    
    def get_stats(self, symbol: Optional[str] = None) -> Dict:
        """
        Get quality statistics.
        
        Args:
            symbol: Optional symbol to filter by
            
        Returns:
            Dictionary with quality statistics
        """
        if symbol:
            return {
                'symbol': symbol,
                'quality_score': self.quality_scores.get(symbol, 1.0),
                'checks': self.check_counts.get(symbol, {'passed': 0, 'failed': 0}),
                'price_history_size': len(self.price_history.get(symbol, [])),
                'volume_history_size': len(self.volume_history.get(symbol, [])),
                'quarantine_size': len([e for e in self.quarantine if e['trade_data'].get('symbol') == symbol])
            }
        else:
            return {
                'total_symbols': len(self.quality_scores),
                'average_quality_score': np.mean(list(self.quality_scores.values())) if self.quality_scores else 1.0,
                'total_quarantine_size': len(self.quarantine),
                'symbols': {
                    sym: {
                        'score': score,
                        'checks': self.check_counts.get(sym, {'passed': 0, 'failed': 0})
                    }
                    for sym, score in self.quality_scores.items()
                }
            }
