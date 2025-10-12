"""
Unit tests for Bar Builder
"""

import pytest
from datetime import datetime, timedelta
from processors.bar_builder import BarBuilder
from storage.models import Trade, Candle


class TestBarBuilder:
    """Test bar building logic"""
    
    @pytest.fixture
    def bar_builder(self):
        """Create bar builder instance"""
        return BarBuilder(
            db_manager=None,  # Mock in tests
            redis_manager=None,
            timeframes=['1m', '5m', '15m']
        )
    
    def test_get_bucket_time_1m(self, bar_builder):
        """Test 1-minute bucket time calculation"""
        timestamp = datetime(2024, 1, 15, 10, 30, 45)
        bucket = bar_builder._get_bucket_time(timestamp, '1m')
        
        assert bucket == datetime(2024, 1, 15, 10, 30, 0)
    
    def test_get_bucket_time_5m(self, bar_builder):
        """Test 5-minute bucket time calculation"""
        timestamp = datetime(2024, 1, 15, 10, 33, 45)
        bucket = bar_builder._get_bucket_time(timestamp, '5m')
        
        assert bucket == datetime(2024, 1, 15, 10, 30, 0)
    
    def test_get_bucket_time_15m(self, bar_builder):
        """Test 15-minute bucket time calculation"""
        timestamp = datetime(2024, 1, 15, 10, 47, 30)
        bucket = bar_builder._get_bucket_time(timestamp, '15m')
        
        assert bucket == datetime(2024, 1, 15, 10, 45, 0)
    
    def test_get_bucket_time_1h(self, bar_builder):
        """Test 1-hour bucket time calculation"""
        timestamp = datetime(2024, 1, 15, 10, 47, 30)
        bucket = bar_builder._get_bucket_time(timestamp, '1h')
        
        assert bucket == datetime(2024, 1, 15, 10, 0, 0)
    
    def test_init_bar(self, bar_builder):
        """Test bar initialization"""
        trade = Trade(
            symbol='BTCUSDT',
            price=50000.0,
            quantity=1.5,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            is_buyer_maker=False
        )
        
        bar = bar_builder._init_bar(trade, '1m')
        
        assert bar.symbol == 'BTCUSDT'
        assert bar.timeframe == '1m'
        assert bar.open == 50000.0
        assert bar.high == 50000.0
        assert bar.low == 50000.0
        assert bar.close == 50000.0
        assert bar.volume == 1.5
    
    def test_update_bar(self, bar_builder):
        """Test bar update with new trade"""
        # Initialize bar
        trade1 = Trade(
            symbol='BTCUSDT',
            price=50000.0,
            quantity=1.0,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            is_buyer_maker=False
        )
        bar = bar_builder._init_bar(trade1, '1m')
        
        # Update with higher price
        trade2 = Trade(
            symbol='BTCUSDT',
            price=50100.0,
            quantity=0.5,
            timestamp=datetime(2024, 1, 15, 10, 30, 30),
            is_buyer_maker=False
        )
        bar_builder._update_bar(bar, trade2)
        
        assert bar.high == 50100.0
        assert bar.close == 50100.0
        assert bar.volume == 1.5
        
        # Update with lower price
        trade3 = Trade(
            symbol='BTCUSDT',
            price=49900.0,
            quantity=0.3,
            timestamp=datetime(2024, 1, 15, 10, 30, 45),
            is_buyer_maker=False
        )
        bar_builder._update_bar(bar, trade3)
        
        assert bar.low == 49900.0
        assert bar.close == 49900.0
        assert bar.volume == 1.8
    
    def test_ohlc_validation(self, bar_builder):
        """Test OHLC validation"""
        # Valid bar
        valid_bar = Candle(
            time=datetime(2024, 1, 15, 10, 30, 0),
            symbol='BTCUSDT',
            timeframe='1m',
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=10.0
        )
        assert bar_builder._validate_ohlc(valid_bar) is True
        
        # Invalid: high < open
        invalid_bar1 = Candle(
            time=datetime(2024, 1, 15, 10, 30, 0),
            symbol='BTCUSDT',
            timeframe='1m',
            open=50000.0,
            high=49900.0,  # Invalid
            low=49800.0,
            close=49900.0,
            volume=10.0
        )
        assert bar_builder._validate_ohlc(invalid_bar1) is False
        
        # Invalid: low > close
        invalid_bar2 = Candle(
            time=datetime(2024, 1, 15, 10, 30, 0),
            symbol='BTCUSDT',
            timeframe='1m',
            open=50000.0,
            high=50100.0,
            low=50050.0,  # Invalid
            close=50000.0,
            volume=10.0
        )
        assert bar_builder._validate_ohlc(invalid_bar2) is False
    
    def test_bar_completion_on_time_boundary(self, bar_builder):
        """Test bar completion when time bucket changes"""
        # First trade in bucket
        trade1 = Trade(
            symbol='BTCUSDT',
            price=50000.0,
            quantity=1.0,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            is_buyer_maker=False
        )
        
        # Trade in next bucket (should trigger completion)
        trade2 = Trade(
            symbol='BTCUSDT',
            price=50100.0,
            quantity=1.0,
            timestamp=datetime(2024, 1, 15, 10, 31, 0),
            is_buyer_maker=False
        )
        
        # Simulate processing
        bucket1 = bar_builder._get_bucket_time(trade1.timestamp, '1m')
        bucket2 = bar_builder._get_bucket_time(trade2.timestamp, '1m')
        
        assert bucket1 != bucket2
        assert bucket2 > bucket1
    
    def test_multiple_timeframes(self, bar_builder):
        """Test processing same trade for multiple timeframes"""
        trade = Trade(
            symbol='BTCUSDT',
            price=50000.0,
            quantity=1.0,
            timestamp=datetime(2024, 1, 15, 10, 33, 45),
            is_buyer_maker=False
        )
        
        # Get buckets for different timeframes
        bucket_1m = bar_builder._get_bucket_time(trade.timestamp, '1m')
        bucket_5m = bar_builder._get_bucket_time(trade.timestamp, '5m')
        bucket_15m = bar_builder._get_bucket_time(trade.timestamp, '15m')
        
        assert bucket_1m == datetime(2024, 1, 15, 10, 33, 0)
        assert bucket_5m == datetime(2024, 1, 15, 10, 30, 0)
        assert bucket_15m == datetime(2024, 1, 15, 10, 30, 0)
    
    def test_aggregate_higher_timeframes(self, bar_builder):
        """Test aggregation of 1m bars to higher timeframes"""
        # Create 5 consecutive 1m bars
        bars_1m = []
        base_time = datetime(2024, 1, 15, 10, 30, 0)
        
        for i in range(5):
            bar = Candle(
                time=base_time + timedelta(minutes=i),
                symbol='BTCUSDT',
                timeframe='1m',
                open=50000.0 + i * 10,
                high=50010.0 + i * 10,
                low=49990.0 + i * 10,
                close=50005.0 + i * 10,
                volume=1.0
            )
            bars_1m.append(bar)
        
        # Aggregate to 5m
        bar_5m = bar_builder._aggregate_bars(bars_1m, '5m')
        
        assert bar_5m.time == base_time
        assert bar_5m.open == bars_1m[0].open
        assert bar_5m.close == bars_1m[-1].close
        assert bar_5m.high == max(b.high for b in bars_1m)
        assert bar_5m.low == min(b.low for b in bars_1m)
        assert bar_5m.volume == sum(b.volume for b in bars_1m)
    
    def test_negative_volume_rejected(self, bar_builder):
        """Test that negative volume is rejected"""
        bar = Candle(
            time=datetime(2024, 1, 15, 10, 30, 0),
            symbol='BTCUSDT',
            timeframe='1m',
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=-1.0  # Invalid
        )
        
        assert bar_builder._validate_ohlc(bar) is False
    
    def test_zero_volume_accepted(self, bar_builder):
        """Test that zero volume is accepted"""
        bar = Candle(
            time=datetime(2024, 1, 15, 10, 30, 0),
            symbol='BTCUSDT',
            timeframe='1m',
            open=50000.0,
            high=50000.0,
            low=50000.0,
            close=50000.0,
            volume=0.0  # Valid (no trades)
        )
        
        assert bar_builder._validate_ohlc(bar) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
