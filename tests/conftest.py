"""
Pytest configuration and shared fixtures
"""

import pytest
import asyncio
import os
from typing import AsyncGenerator
import aiohttp
import asyncpg
import redis.asyncio as redis


# Configure asyncio event loop
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# System configuration
@pytest.fixture(scope="session")
def system_config():
    """System configuration for tests"""
    return {
        "api_url": os.getenv("API_URL", "http://localhost:8000"),
        "ws_url": os.getenv("WS_URL", "ws://localhost:8000"),
        "db_host": os.getenv("DB_HOST", "localhost"),
        "db_port": int(os.getenv("DB_PORT", "5432")),
        "db_user": os.getenv("DB_USER", "admin"),
        "db_password": os.getenv("DB_PASSWORD", "admin"),
        "db_name": os.getenv("DB_NAME", "crypto_stock"),
        "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379"),
        "prometheus_url": os.getenv("PROMETHEUS_URL", "http://localhost:9090"),
        "grafana_url": os.getenv("GRAFANA_URL", "http://localhost:3001"),
    }


# HTTP client fixture
@pytest.fixture
async def http_client(system_config) -> AsyncGenerator[aiohttp.ClientSession, None]:
    """Async HTTP client for API testing"""
    async with aiohttp.ClientSession(
        base_url=system_config["api_url"],
        timeout=aiohttp.ClientTimeout(total=30)
    ) as session:
        yield session


# Database connection fixture
@pytest.fixture
async def db_connection(system_config) -> AsyncGenerator[asyncpg.Connection, None]:
    """Async database connection for testing"""
    conn = await asyncpg.connect(
        host=system_config["db_host"],
        port=system_config["db_port"],
        user=system_config["db_user"],
        password=system_config["db_password"],
        database=system_config["db_name"],
    )
    yield conn
    await conn.close()


# Redis connection fixture
@pytest.fixture
async def redis_client(system_config) -> AsyncGenerator[redis.Redis, None]:
    """Async Redis client for testing"""
    client = await redis.from_url(system_config["redis_url"])
    yield client
    await client.close()


# Test symbol fixture
@pytest.fixture
async def test_symbol(http_client) -> str:
    """Get a test symbol from the API"""
    async with http_client.get("/api/v1/symbols") as resp:
        if resp.status == 200:
            symbols_data = await resp.json()
            # Get first available symbol
            for exchange, symbols in symbols_data.items():
                if symbols:
                    return symbols[0]
    
    # Fallback to default
    return "BTCUSDT"


# System health check fixture
@pytest.fixture(scope="session")
async def ensure_system_running(system_config):
    """Ensure system is running before tests"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{system_config['api_url']}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    pytest.skip("System is not healthy")
                
                health = await resp.json()
                if health.get("status") != "healthy":
                    pytest.skip("System is not healthy")
                    
        except Exception as e:
            pytest.skip(f"System is not running: {e}")


# Cleanup fixture
@pytest.fixture(autouse=True)
async def cleanup_test_data(db_connection):
    """Cleanup test data after each test"""
    yield
    
    # Add cleanup logic here if needed
    # For example, delete test records created during tests
    pass


# Mock data fixtures
@pytest.fixture
def sample_candle():
    """Sample candle data for testing"""
    return {
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "time": "2024-01-01T00:00:00Z",
        "open": 50000.0,
        "high": 50100.0,
        "low": 49900.0,
        "close": 50050.0,
        "volume": 100.5,
    }


@pytest.fixture
def sample_trade():
    """Sample trade data for testing"""
    return {
        "symbol": "BTCUSDT",
        "price": 50000.0,
        "quantity": 1.5,
        "timestamp": 1704067200000,
        "is_buyer_maker": False,
    }


@pytest.fixture
def sample_indicators():
    """Sample indicator data for testing"""
    return {
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "time": "2024-01-01T00:00:00Z",
        "rsi": 55.5,
        "macd": 10.5,
        "macd_signal": 8.3,
        "macd_histogram": 2.2,
        "bb_upper": 51000.0,
        "bb_middle": 50000.0,
        "bb_lower": 49000.0,
        "sma_20": 50000.0,
        "sma_50": 49500.0,
        "ema_12": 50100.0,
        "ema_26": 49900.0,
    }


# Performance tracking fixture
@pytest.fixture
def track_performance():
    """Track test performance metrics"""
    import time
    
    metrics = {}
    
    def track(name: str):
        start = time.time()
        
        def stop():
            duration = (time.time() - start) * 1000  # ms
            metrics[name] = duration
            return duration
        
        return stop
    
    yield track
    
    # Print performance summary
    if metrics:
        print("\n=== Performance Metrics ===")
        for name, duration in metrics.items():
            print(f"{name}: {duration:.2f}ms")


# Pytest hooks
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual components"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests for complete flows"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take a long time to run"
    )
    config.addinivalue_line(
        "markers", "smoke: Quick smoke tests for system health"
    )
    config.addinivalue_line(
        "markers", "requires_system: Tests that require the system to be running"
    )
    config.addinivalue_line(
        "markers", "requires_data: Tests that require data to be collected"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically"""
    for item in items:
        # Add markers based on test location
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.requires_system)
        elif "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        
        # Add slow marker for tests with long timeouts
        if hasattr(item, "get_closest_marker"):
            if item.get_closest_marker("timeout"):
                timeout = item.get_closest_marker("timeout").args[0]
                if timeout > 60:
                    item.add_marker(pytest.mark.slow)


def pytest_report_header(config):
    """Add custom header to pytest report"""
    return [
        "Crypto-Stock Platform Test Suite",
        "=" * 50,
    ]
