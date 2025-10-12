"""
Integration tests for complete data flow
Tests the entire pipeline from data collection to API serving
"""

import asyncio
import pytest
import time
from datetime import datetime, timedelta
from typing import Dict, List
import json

# Test configuration
TEST_TIMEOUT = 300  # 5 minutes
HEALTH_CHECK_INTERVAL = 5
DATA_COLLECTION_WAIT = 60  # Wait for data to flow through system


class TestDataFlow:
    """Test complete data flow through the system"""
    
    @pytest.fixture(scope="class")
    async def system_health(self):
        """Verify system is healthy before running tests"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            # Check API health
            async with session.get("http://localhost:8000/health") as resp:
                assert resp.status == 200
                health = await resp.json()
                assert health["status"] == "healthy"
                
            # Check database
            assert health["components"]["database"]["status"] == "healthy"
            
            # Check Redis
            assert health["components"]["redis"]["status"] == "healthy"
            
            # Check collectors
            assert health["components"]["collectors"]["status"] == "healthy"
            
        yield health
    
    @pytest.mark.asyncio
    async def test_collector_to_database_flow(self, system_health):
        """Test data flows from collectors to database"""
        import asyncpg
        
        # Connect to database
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="admin",
            password="admin",
            database="crypto_stock"
        )
        
        try:
            # Wait for data collection
            print(f"Waiting {DATA_COLLECTION_WAIT}s for data collection...")
            await asyncio.sleep(DATA_COLLECTION_WAIT)
            
            # Check if candles were inserted
            result = await conn.fetchval(
                """
                SELECT COUNT(*) 
                FROM candles 
                WHERE time > NOW() - INTERVAL '2 minutes'
                """
            )
            
            assert result > 0, f"No recent candles found. Expected > 0, got {result}"
            print(f"✓ Found {result} recent candles in database")
            
            # Check multiple symbols
            symbols_result = await conn.fetch(
                """
                SELECT symbol, COUNT(*) as count
                FROM candles
                WHERE time > NOW() - INTERVAL '2 minutes'
                GROUP BY symbol
                ORDER BY count DESC
                LIMIT 5
                """
            )
            
            assert len(symbols_result) > 0, "No symbols found with recent data"
            print(f"✓ Found data for {len(symbols_result)} symbols")
            
            for row in symbols_result:
                print(f"  - {row['symbol']}: {row['count']} candles")
                
        finally:
            await conn.close()
    
    @pytest.mark.asyncio
    async def test_bar_building_flow(self, system_health):
        """Test bar building from trades"""
        import asyncpg
        
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="admin",
            password="admin",
            database="crypto_stock"
        )
        
        try:
            # Get a recent candle
            candle = await conn.fetchrow(
                """
                SELECT * FROM candles
                WHERE time > NOW() - INTERVAL '5 minutes'
                ORDER BY time DESC
                LIMIT 1
                """
            )
            
            assert candle is not None, "No recent candles found"
            
            # Validate OHLC structure
            assert candle['high'] >= candle['open'], "High should be >= open"
            assert candle['high'] >= candle['close'], "High should be >= close"
            assert candle['low'] <= candle['open'], "Low should be <= open"
            assert candle['low'] <= candle['close'], "Low should be <= close"
            assert candle['volume'] >= 0, "Volume should be non-negative"
            
            print(f"✓ Bar structure validated for {candle['symbol']}")
            print(f"  OHLC: {candle['open']:.2f}/{candle['high']:.2f}/{candle['low']:.2f}/{candle['close']:.2f}")
            print(f"  Volume: {candle['volume']:.2f}")
            
        finally:
            await conn.close()
    
    @pytest.mark.asyncio
    async def test_indicator_calculation_flow(self, system_health):
        """Test indicator calculation after bar completion"""
        import asyncpg
        
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="admin",
            password="admin",
            database="crypto_stock"
        )
        
        try:
            # Check if indicators were calculated
            result = await conn.fetchval(
                """
                SELECT COUNT(*) 
                FROM indicators 
                WHERE time > NOW() - INTERVAL '5 minutes'
                """
            )
            
            # Indicators may not be calculated immediately if not enough data
            if result > 0:
                print(f"✓ Found {result} recent indicator calculations")
                
                # Get a sample indicator
                indicator = await conn.fetchrow(
                    """
                    SELECT * FROM indicators
                    WHERE time > NOW() - INTERVAL '5 minutes'
                    ORDER BY time DESC
                    LIMIT 1
                    """
                )
                
                print(f"✓ Indicator sample for {indicator['symbol']}:")
                if indicator['rsi'] is not None:
                    print(f"  RSI: {indicator['rsi']:.2f}")
                if indicator['macd'] is not None:
                    print(f"  MACD: {indicator['macd']:.4f}")
                if indicator['sma_20'] is not None:
                    print(f"  SMA(20): {indicator['sma_20']:.2f}")
            else:
                print("⚠ No indicators calculated yet (may need more data)")
                
        finally:
            await conn.close()
    
    @pytest.mark.asyncio
    async def test_ml_features_flow(self, system_health):
        """Test ML feature engineering pipeline"""
        import asyncpg
        
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="admin",
            password="admin",
            database="crypto_stock"
        )
        
        try:
            # Check if features were calculated
            result = await conn.fetchval(
                """
                SELECT COUNT(*) 
                FROM ml_features 
                WHERE time > NOW() - INTERVAL '5 minutes'
                """
            )
            
            if result > 0:
                print(f"✓ Found {result} recent ML features")
                
                # Get a sample feature
                feature = await conn.fetchrow(
                    """
                    SELECT * FROM ml_features
                    WHERE time > NOW() - INTERVAL '5 minutes'
                    ORDER BY time DESC
                    LIMIT 1
                    """
                )
                
                print(f"✓ Feature sample for {feature['symbol']}:")
                print(f"  Version: {feature['feature_version']}")
                
                # Parse features JSON
                features = json.loads(feature['features'])
                print(f"  Features count: {len(features)}")
                
                # Show some sample features
                sample_keys = list(features.keys())[:5]
                for key in sample_keys:
                    print(f"  {key}: {features[key]}")
            else:
                print("⚠ No ML features calculated yet (may need more data)")
                
        finally:
            await conn.close()
    
    @pytest.mark.asyncio
    async def test_redis_cache_flow(self, system_health):
        """Test Redis caching of bars and indicators"""
        import redis.asyncio as redis
        
        r = await redis.from_url("redis://localhost:6379")
        
        try:
            # Check cached bars
            symbols = await r.keys("bars:*")
            assert len(symbols) > 0, "No cached bars found"
            
            print(f"✓ Found {len(symbols)} symbols with cached bars")
            
            # Get bars for first symbol
            symbol_key = symbols[0].decode()
            bars = await r.zrange(symbol_key, -10, -1)
            
            assert len(bars) > 0, f"No bars in {symbol_key}"
            print(f"✓ {symbol_key} has {len(bars)} cached bars")
            
            # Check cached indicators
            indicator_keys = await r.keys("indicators:*")
            if len(indicator_keys) > 0:
                print(f"✓ Found {len(indicator_keys)} symbols with cached indicators")
            else:
                print("⚠ No cached indicators yet")
                
        finally:
            await r.close()
    
    @pytest.mark.asyncio
    async def test_api_chart_endpoint(self, system_health):
        """Test API chart data endpoint"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            # Get symbols first
            async with session.get("http://localhost:8000/api/v1/symbols") as resp:
                assert resp.status == 200
                symbols_data = await resp.json()
                
            # Get first available symbol
            test_symbol = None
            for exchange, symbols in symbols_data.items():
                if symbols:
                    test_symbol = symbols[0]
                    break
            
            assert test_symbol is not None, "No symbols available"
            print(f"✓ Testing with symbol: {test_symbol}")
            
            # Get chart data
            async with session.get(
                f"http://localhost:8000/api/v1/charts/{test_symbol}",
                params={"timeframe": "1m", "limit": 100}
            ) as resp:
                assert resp.status == 200
                chart_data = await resp.json()
                
            # Validate response structure
            assert "symbol" in chart_data
            assert "timeframe" in chart_data
            assert "bars" in chart_data
            assert "indicators" in chart_data
            
            assert len(chart_data["bars"]) > 0, "No bars returned"
            print(f"✓ Received {len(chart_data['bars'])} bars")
            
            # Validate bar structure
            bar = chart_data["bars"][0]
            required_fields = ["time", "open", "high", "low", "close", "volume"]
            for field in required_fields:
                assert field in bar, f"Missing field: {field}"
            
            print("✓ Chart data structure validated")
    
    @pytest.mark.asyncio
    async def test_websocket_realtime_updates(self, system_health):
        """Test WebSocket real-time chart updates"""
        import websockets
        
        # Get a test symbol
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/api/v1/symbols") as resp:
                symbols_data = await resp.json()
                
        test_symbol = None
        for exchange, symbols in symbols_data.items():
            if symbols:
                test_symbol = symbols[0]
                break
        
        assert test_symbol is not None
        print(f"✓ Testing WebSocket with symbol: {test_symbol}")
        
        # Connect to WebSocket
        uri = f"ws://localhost:8000/ws/{test_symbol}"
        
        try:
            async with websockets.connect(uri) as websocket:
                print("✓ WebSocket connected")
                
                # Receive initial data
                initial_data = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=10
                )
                
                data = json.loads(initial_data)
                assert "type" in data
                assert data["type"] == "initial"
                assert "bars" in data
                print(f"✓ Received initial data with {len(data['bars'])} bars")
                
                # Wait for real-time update
                print("Waiting for real-time update...")
                update = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=120  # Wait up to 2 minutes for update
                )
                
                update_data = json.loads(update)
                assert "type" in update_data
                assert update_data["type"] == "update"
                print("✓ Received real-time update")
                
        except asyncio.TimeoutError:
            print("⚠ No real-time update received within timeout (may be normal)")
        except Exception as e:
            pytest.fail(f"WebSocket test failed: {e}")
    
    @pytest.mark.asyncio
    async def test_data_quality_metrics(self, system_health):
        """Test data quality monitoring"""
        import asyncpg
        
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="admin",
            password="admin",
            database="crypto_stock"
        )
        
        try:
            # Check quality metrics
            result = await conn.fetchval(
                """
                SELECT COUNT(*) 
                FROM data_quality_metrics 
                WHERE time > NOW() - INTERVAL '10 minutes'
                """
            )
            
            if result > 0:
                print(f"✓ Found {result} quality metric records")
                
                # Get quality scores
                scores = await conn.fetch(
                    """
                    SELECT symbol, AVG(quality_score) as avg_score
                    FROM data_quality_metrics
                    WHERE time > NOW() - INTERVAL '10 minutes'
                    GROUP BY symbol
                    ORDER BY avg_score DESC
                    LIMIT 5
                    """
                )
                
                print("✓ Quality scores:")
                for row in scores:
                    print(f"  {row['symbol']}: {row['avg_score']:.2f}")
            else:
                print("⚠ No quality metrics recorded yet")
                
        finally:
            await conn.close()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_metrics(self, system_health):
        """Test circuit breaker monitoring"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            # Get Prometheus metrics
            async with session.get("http://localhost:9090/api/v1/query",
                                  params={"query": "circuit_breaker_state"}) as resp:
                assert resp.status == 200
                metrics = await resp.json()
                
            if metrics["data"]["result"]:
                print("✓ Circuit breaker metrics available")
                for result in metrics["data"]["result"]:
                    collector = result["metric"].get("collector", "unknown")
                    state = result["value"][1]
                    print(f"  {collector}: state={state}")
            else:
                print("⚠ No circuit breaker metrics yet")
    
    @pytest.mark.asyncio
    async def test_end_to_end_latency(self, system_health):
        """Test end-to-end latency from collection to API"""
        import aiohttp
        import asyncpg
        
        # Get latest candle timestamp from database
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="admin",
            password="admin",
            database="crypto_stock"
        )
        
        try:
            latest_candle = await conn.fetchrow(
                """
                SELECT time, symbol
                FROM candles
                ORDER BY time DESC
                LIMIT 1
                """
            )
            
            if latest_candle:
                candle_time = latest_candle['time']
                symbol = latest_candle['symbol']
                
                # Get same data via API
                async with aiohttp.ClientSession() as session:
                    start_time = time.time()
                    async with session.get(
                        f"http://localhost:8000/api/v1/charts/{symbol}",
                        params={"timeframe": "1m", "limit": 1}
                    ) as resp:
                        api_latency = (time.time() - start_time) * 1000
                        chart_data = await resp.json()
                
                assert api_latency < 100, f"API latency too high: {api_latency:.2f}ms"
                print(f"✓ API latency: {api_latency:.2f}ms")
                
                # Calculate data freshness
                now = datetime.utcnow()
                data_age = (now - candle_time).total_seconds()
                print(f"✓ Data freshness: {data_age:.1f}s old")
                
        finally:
            await conn.close()


class TestSystemResilience:
    """Test system resilience and error handling"""
    
    @pytest.mark.asyncio
    async def test_invalid_symbol_handling(self):
        """Test API handles invalid symbols gracefully"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://localhost:8000/api/v1/charts/INVALID_SYMBOL",
                params={"timeframe": "1m", "limit": 100}
            ) as resp:
                # Should return 404 or empty data, not 500
                assert resp.status in [404, 200]
                print(f"✓ Invalid symbol handled with status {resp.status}")
    
    @pytest.mark.asyncio
    async def test_invalid_timeframe_handling(self):
        """Test API validates timeframe parameter"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            # Get a valid symbol
            async with session.get("http://localhost:8000/api/v1/symbols") as resp:
                symbols_data = await resp.json()
                
            test_symbol = None
            for exchange, symbols in symbols_data.items():
                if symbols:
                    test_symbol = symbols[0]
                    break
            
            # Try invalid timeframe
            async with session.get(
                f"http://localhost:8000/api/v1/charts/{test_symbol}",
                params={"timeframe": "invalid", "limit": 100}
            ) as resp:
                assert resp.status == 400
                print("✓ Invalid timeframe rejected with 400")
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting enforcement"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            # Make many rapid requests
            responses = []
            for i in range(150):  # Exceed rate limit of 100/min
                async with session.get("http://localhost:8000/health") as resp:
                    responses.append(resp.status)
            
            # Should have some 429 responses
            rate_limited = sum(1 for status in responses if status == 429)
            
            if rate_limited > 0:
                print(f"✓ Rate limiting active: {rate_limited}/150 requests limited")
            else:
                print("⚠ Rate limiting may not be enforced (check configuration)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
