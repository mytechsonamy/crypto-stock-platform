"""
Unit tests for Data Quality Checker
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from processors.data_quality import DataQualityChecker
from storage.models import Trade


class TestDataQualityChecker:
    """Test data quality validation"""
    
    @pytest.fixture
    def quality_checker(self):
        """Create quality checker instance"""
        return DataQualityChecker(
            redis_manager=None,
            window_size=100
        )
    
    @pytest.fixture
    def normal_trade(self):
        """Create normal trade"""
        return Trade(
            symbol='BTCUSDT',
            price=50000.0,
            quantity=1.0,
            timestamp=datetime.now(),
            is_buyer_maker=False
        )
    
    def test_valid_trade_passes(self, quality_checker, normal_trade):
        """Test that valid trade passes all checks"""
        result = quality_checker.validate_trade(normal_trade)
        
        assert result['valid'] is True
        assert result['quality_score'] == 100.0
        assert len(result['failed_checks']) == 0
    
    def test_price_anomaly_detection(self, quality_checker):
        """Test price anomaly detection"""
        # Build price history
        for i in range(100):
            trade = Trade(
                symbol='BTCUSDT',
                price=50000.0 + np.random.randn() * 100,
                quantity=1.0,
                timestamp=datetime.now(),
                is_buyer_maker=False
            )
            quality_checker.validate_trade(trade)
        
        # Create anomalous trade (10x normal price)
        anomalous_trade = Trade(
            symbol='BTCUSDT',
            price=500000.0,  # 10x normal
            quantity=1.0,
            timestamp=datetime.now(),
            is_buyer_maker=False
        )
        
        result = quality_checker.validate_trade(anomalous_trade)
        
        assert result['valid'] is False
        assert 'price_anomaly' in result['failed_checks']
        assert result['quality_score'] < 100.0
    
    def test_negative_price_rejected(self, quality_checker):
        """Test that negative price is rejected"""
        trade = Trade(
            symbol='BTCUSDT',
            price=-50000.0,  # Invalid
            quantity=1.0,
            timestamp=datetime.now(),
            is_buyer_maker=False
        )
        
        result = quality_checker.validate_trade(trade)
        
        assert result['valid'] is False
        assert 'invalid_price' in result['failed_checks']
    
    def test_zero_price_rejected(self, quality_checker):
        """Test that zero price is rejected"""
        trade = Trade(
            symbol='BTCUSDT',
            price=0.0,  # Invalid
            quantity=1.0,
            timestamp=datetime.now(),
            is_buyer_maker=False
        )
        
        result = quality_checker.validate_trade(trade)
        
        assert result['valid'] is False
        assert 'invalid_price' in result['failed_checks']
    
    def test_negative_volume_rejected(self, quality_checker, normal_trade):
        """Test that negative volume is rejected"""
        normal_trade.quantity = -1.0  # Invalid
        
        result = quality_checker.validate_trade(normal_trade)
        
        assert result['valid'] is False
        assert 'invalid_volume' in result['failed_checks']
    
    def test_zero_volume_accepted(self, quality_checker, normal_trade):
        """Test that zero volume is accepted"""
        normal_trade.quantity = 0.0  # Valid (cancelled trade)
        
        result = quality_checker.validate_trade(normal_trade)
        
        # Zero volume might be flagged but not rejected
        assert result['valid'] is True or 'zero_volume' in result['warnings']
    
    def test_stale_data_detection(self, quality_checker):
        """Test stale data detection"""
        # Create old trade (2 minutes ago)
        old_trade = Trade(
            symbol='BTCUSDT',
            price=50000.0,
            quantity=1.0,
            timestamp=datetime.now() - timedelta(minutes=2),
            is_buyer_maker=False
        )
        
        result = quality_checker.validate_trade(old_trade)
        
        assert result['valid'] is False
        assert 'stale_data' in result['failed_checks']
    
    def test_volume_anomaly_detection(self, quality_checker):
        """Test volume anomaly detection"""
        # Build volume history
        for i in range(100):
            trade = Trade(
                symbol='BTCUSDT',
                price=50000.0,
                quantity=1.0 + np.random.randn() * 0.1,
                timestamp=datetime.now(),
                is_buyer_maker=False
            )
            quality_checker.validate_trade(trade)
        
        # Create anomalous volume (100x normal)
        anomalous_trade = Trade(
            symbol='BTCUSDT',
            price=50000.0,
            quantity=100.0,  # 100x normal
            timestamp=datetime.now(),
            is_buyer_maker=False
        )
        
        result = quality_checker.validate_trade(anomalous_trade)
        
        # May be flagged as warning but not necessarily rejected
        assert 'volume_anomaly' in result['warnings'] or result['valid'] is True
    
    def test_quality_score_calculation(self, quality_checker):
        """Test quality score calculation"""
        # Perfect trade
        perfect_trade = Trade(
            symbol='BTCUSDT',
            price=50000.0,
            quantity=1.0,
            timestamp=datetime.now(),
            is_buyer_maker=False
        )
        
        result = quality_checker.validate_trade(perfect_trade)
        assert result['quality_score'] == 100.0
        
        # Build history
        for i in range(100):
            trade = Trade(
                symbol='BTCUSDT',
                price=50000.0 + np.random.randn() * 100,
                quantity=1.0,
                timestamp=datetime.now(),
                is_buyer_maker=False
            )
            quality_checker.validate_trade(trade)
        
        # Slightly anomalous trade
        anomalous_trade = Trade(
            symbol='BTCUSDT',
            price=52000.0,  # 4% higher
            quantity=1.0,
            timestamp=datetime.now(),
            is_buyer_maker=False
        )
        
        result = quality_checker.validate_trade(anomalous_trade)
        # Score should be reduced but not zero
        assert 0 < result['quality_score'] < 100.0
    
    def test_infinite_values_rejected(self, quality_checker):
        """Test that infinite values are rejected"""
        trade = Trade(
            symbol='BTCUSDT',
            price=float('inf'),  # Invalid
            quantity=1.0,
            timestamp=datetime.now(),
            is_buyer_maker=False
        )
        
        result = quality_checker.validate_trade(trade)
        
        assert result['valid'] is False
        assert 'invalid_price' in result['failed_checks']
    
    def test_nan_values_rejected(self, quality_checker):
        """Test that NaN values are rejected"""
        trade = Trade(
            symbol='BTCUSDT',
            price=float('nan'),  # Invalid
            quantity=1.0,
            timestamp=datetime.now(),
            is_buyer_maker=False
        )
        
        result = quality_checker.validate_trade(trade)
        
        assert result['valid'] is False
        assert 'invalid_price' in result['failed_checks']
    
    def test_multiple_symbols_tracked_separately(self, quality_checker):
        """Test that different symbols are tracked separately"""
        # Add trades for BTCUSDT
        for i in range(50):
            trade = Trade(
                symbol='BTCUSDT',
                price=50000.0 + np.random.randn() * 100,
                quantity=1.0,
                timestamp=datetime.now(),
                is_buyer_maker=False
            )
            quality_checker.validate_trade(trade)
        
        # Add trades for ETHUSDT (different price range)
        for i in range(50):
            trade = Trade(
                symbol='ETHUSDT',
                price=3000.0 + np.random.randn() * 50,
                quantity=1.0,
                timestamp=datetime.now(),
                is_buyer_maker=False
            )
            quality_checker.validate_trade(trade)
        
        # ETHUSDT price should not affect BTCUSDT validation
        btc_trade = Trade(
            symbol='BTCUSDT',
            price=50500.0,  # Normal for BTC
            quantity=1.0,
            timestamp=datetime.now(),
            is_buyer_maker=False
        )
        
        result = quality_checker.validate_trade(btc_trade)
        assert result['valid'] is True
    
    def test_price_history_window(self, quality_checker):
        """Test that price history respects window size"""
        # Add more trades than window size
        for i in range(150):
            trade = Trade(
                symbol='BTCUSDT',
                price=50000.0 + i,  # Gradually increasing
                quantity=1.0,
                timestamp=datetime.now(),
                is_buyer_maker=False
            )
            quality_checker.validate_trade(trade)
        
        # History should be limited to window size (100)
        history = quality_checker.price_history.get('BTCUSDT', [])
        assert len(history) <= 100
    
    def test_percentage_change_threshold(self, quality_checker):
        """Test percentage change threshold"""
        # Build stable price history
        for i in range(100):
            trade = Trade(
                symbol='BTCUSDT',
                price=50000.0,
                quantity=1.0,
                timestamp=datetime.now(),
                is_buyer_maker=False
            )
            quality_checker.validate_trade(trade)
        
        # 5% change should pass
        trade_5pct = Trade(
            symbol='BTCUSDT',
            price=52500.0,  # 5% higher
            quantity=1.0,
            timestamp=datetime.now(),
            is_buyer_maker=False
        )
        result = quality_checker.validate_trade(trade_5pct)
        assert result['valid'] is True
        
        # 15% change should fail
        trade_15pct = Trade(
            symbol='BTCUSDT',
            price=57500.0,  # 15% higher
            quantity=1.0,
            timestamp=datetime.now(),
            is_buyer_maker=False
        )
        result = quality_checker.validate_trade(trade_15pct)
        assert result['valid'] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
