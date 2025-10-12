"""
Unit tests for Indicator Calculator
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from processors.indicators import IndicatorCalculator


class TestIndicatorCalculator:
    """Test indicator calculations"""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data"""
        dates = pd.date_range(start='2024-01-01', periods=200, freq='1H')
        
        # Generate realistic price data
        np.random.seed(42)
        close_prices = 50000 + np.cumsum(np.random.randn(200) * 100)
        
        df = pd.DataFrame({
            'time': dates,
            'symbol': 'BTCUSDT',
            'timeframe': '1h',
            'open': close_prices + np.random.randn(200) * 50,
            'high': close_prices + np.abs(np.random.randn(200) * 100),
            'low': close_prices - np.abs(np.random.randn(200) * 100),
            'close': close_prices,
            'volume': np.random.uniform(100, 1000, 200)
        })
        
        return df
    
    @pytest.fixture
    def indicator_calculator(self):
        """Create indicator calculator instance"""
        return IndicatorCalculator(
            db_manager=None,
            redis_manager=None
        )
    
    def test_calculate_rsi(self, indicator_calculator, sample_data):
        """Test RSI calculation"""
        indicators = indicator_calculator.calculate_indicators(sample_data)
        
        # RSI should be between 0 and 100
        assert indicators['rsi'].min() >= 0
        assert indicators['rsi'].max() <= 100
        
        # RSI should have values (not all NaN)
        assert indicators['rsi'].notna().sum() > 0
        
        # First 14 values should be NaN (RSI period)
        assert indicators['rsi'].iloc[:14].isna().all()
    
    def test_calculate_macd(self, indicator_calculator, sample_data):
        """Test MACD calculation"""
        indicators = indicator_calculator.calculate_indicators(sample_data)
        
        # MACD components should exist
        assert 'macd' in indicators.columns
        assert 'macd_signal' in indicators.columns
        assert 'macd_histogram' in indicators.columns
        
        # MACD histogram = MACD - Signal
        macd_hist_calc = indicators['macd'] - indicators['macd_signal']
        assert np.allclose(
            indicators['macd_histogram'].dropna(),
            macd_hist_calc.dropna(),
            rtol=1e-5
        )
    
    def test_calculate_bollinger_bands(self, indicator_calculator, sample_data):
        """Test Bollinger Bands calculation"""
        indicators = indicator_calculator.calculate_indicators(sample_data)
        
        # BB components should exist
        assert 'bb_upper' in indicators.columns
        assert 'bb_middle' in indicators.columns
        assert 'bb_lower' in indicators.columns
        
        # Upper > Middle > Lower
        valid_rows = indicators[['bb_upper', 'bb_middle', 'bb_lower']].notna().all(axis=1)
        assert (indicators.loc[valid_rows, 'bb_upper'] >= 
                indicators.loc[valid_rows, 'bb_middle']).all()
        assert (indicators.loc[valid_rows, 'bb_middle'] >= 
                indicators.loc[valid_rows, 'bb_lower']).all()
    
    def test_calculate_sma(self, indicator_calculator, sample_data):
        """Test SMA calculation"""
        indicators = indicator_calculator.calculate_indicators(sample_data)
        
        # SMA periods should exist
        assert 'sma_20' in indicators.columns
        assert 'sma_50' in indicators.columns
        assert 'sma_100' in indicators.columns
        assert 'sma_200' in indicators.columns
        
        # First N-1 values should be NaN
        assert indicators['sma_20'].iloc[:19].isna().all()
        assert indicators['sma_50'].iloc[:49].isna().all()
        
        # SMA should be close to price
        price_mean = sample_data['close'].mean()
        sma_mean = indicators['sma_20'].mean()
        assert abs(sma_mean - price_mean) < price_mean * 0.1  # Within 10%
    
    def test_calculate_ema(self, indicator_calculator, sample_data):
        """Test EMA calculation"""
        indicators = indicator_calculator.calculate_indicators(sample_data)
        
        # EMA periods should exist
        assert 'ema_12' in indicators.columns
        assert 'ema_26' in indicators.columns
        assert 'ema_50' in indicators.columns
        
        # EMA should respond faster than SMA
        # (This is a property of EMA vs SMA)
        assert indicators['ema_12'].notna().sum() > 0
    
    def test_calculate_vwap(self, indicator_calculator, sample_data):
        """Test VWAP calculation"""
        indicators = indicator_calculator.calculate_indicators(sample_data)
        
        assert 'vwap' in indicators.columns
        
        # VWAP should be close to typical price
        typical_price = (sample_data['high'] + sample_data['low'] + sample_data['close']) / 3
        assert abs(indicators['vwap'].mean() - typical_price.mean()) < typical_price.mean() * 0.1
    
    def test_calculate_stochastic(self, indicator_calculator, sample_data):
        """Test Stochastic oscillator calculation"""
        indicators = indicator_calculator.calculate_indicators(sample_data)
        
        assert 'stoch_k' in indicators.columns
        assert 'stoch_d' in indicators.columns
        
        # Stochastic should be between 0 and 100
        assert indicators['stoch_k'].min() >= 0
        assert indicators['stoch_k'].max() <= 100
        assert indicators['stoch_d'].min() >= 0
        assert indicators['stoch_d'].max() <= 100
    
    def test_calculate_atr(self, indicator_calculator, sample_data):
        """Test ATR calculation"""
        indicators = indicator_calculator.calculate_indicators(sample_data)
        
        assert 'atr' in indicators.columns
        
        # ATR should be positive
        assert (indicators['atr'].dropna() > 0).all()
        
        # ATR should be reasonable relative to price
        avg_price = sample_data['close'].mean()
        avg_atr = indicators['atr'].mean()
        assert avg_atr < avg_price * 0.1  # ATR should be < 10% of price
    
    def test_calculate_adx(self, indicator_calculator, sample_data):
        """Test ADX calculation"""
        indicators = indicator_calculator.calculate_indicators(sample_data)
        
        assert 'adx' in indicators.columns
        
        # ADX should be between 0 and 100
        assert indicators['adx'].min() >= 0
        assert indicators['adx'].max() <= 100
    
    def test_calculate_volume_sma(self, indicator_calculator, sample_data):
        """Test Volume SMA calculation"""
        indicators = indicator_calculator.calculate_indicators(sample_data)
        
        assert 'volume_sma' in indicators.columns
        
        # Volume SMA should be positive
        assert (indicators['volume_sma'].dropna() > 0).all()
        
        # Should be close to average volume
        avg_volume = sample_data['volume'].mean()
        avg_volume_sma = indicators['volume_sma'].mean()
        assert abs(avg_volume_sma - avg_volume) < avg_volume * 0.1
    
    def test_insufficient_data(self, indicator_calculator):
        """Test handling of insufficient data"""
        # Create data with only 10 rows (insufficient for most indicators)
        dates = pd.date_range(start='2024-01-01', periods=10, freq='1H')
        df = pd.DataFrame({
            'time': dates,
            'symbol': 'BTCUSDT',
            'timeframe': '1h',
            'open': [50000] * 10,
            'high': [50100] * 10,
            'low': [49900] * 10,
            'close': [50000] * 10,
            'volume': [100] * 10
        })
        
        indicators = indicator_calculator.calculate_indicators(df)
        
        # Should return DataFrame with NaN values
        assert isinstance(indicators, pd.DataFrame)
        assert len(indicators) == 10
        
        # Most indicators should be NaN
        assert indicators['sma_20'].isna().all()
        assert indicators['sma_50'].isna().all()
    
    def test_all_indicators_calculated(self, indicator_calculator, sample_data):
        """Test that all expected indicators are calculated"""
        indicators = indicator_calculator.calculate_indicators(sample_data)
        
        expected_indicators = [
            'rsi', 'macd', 'macd_signal', 'macd_histogram',
            'bb_upper', 'bb_middle', 'bb_lower',
            'sma_20', 'sma_50', 'sma_100', 'sma_200',
            'ema_12', 'ema_26', 'ema_50',
            'vwap', 'stoch_k', 'stoch_d',
            'atr', 'adx', 'volume_sma'
        ]
        
        for indicator in expected_indicators:
            assert indicator in indicators.columns, f"Missing indicator: {indicator}"
    
    def test_calculation_performance(self, indicator_calculator, sample_data):
        """Test that calculation completes within time limit"""
        import time
        
        start_time = time.time()
        indicators = indicator_calculator.calculate_indicators(sample_data)
        duration = time.time() - start_time
        
        # Should complete within 200ms for 200 bars
        assert duration < 0.2, f"Calculation took {duration:.3f}s, expected < 0.2s"
    
    def test_nan_handling(self, indicator_calculator):
        """Test handling of NaN values in input data"""
        dates = pd.date_range(start='2024-01-01', periods=50, freq='1H')
        df = pd.DataFrame({
            'time': dates,
            'symbol': 'BTCUSDT',
            'timeframe': '1h',
            'open': [50000] * 50,
            'high': [50100] * 50,
            'low': [49900] * 50,
            'close': [50000] * 50,
            'volume': [100] * 50
        })
        
        # Introduce some NaN values
        df.loc[10:15, 'close'] = np.nan
        
        indicators = indicator_calculator.calculate_indicators(df)
        
        # Should handle NaN gracefully
        assert isinstance(indicators, pd.DataFrame)
        assert len(indicators) == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
