# Data Collectors

This directory contains all data collector implementations for the Crypto-Stock Platform.

## Overview

Collectors are responsible for gathering real-time and delayed market data from various exchanges and data providers. All collectors extend the `BaseCollector` abstract class and implement dynamic symbol loading from the database.

## Architecture

```
BaseCollector (Abstract)
├── Circuit Breaker Integration
├── Exponential Backoff Reconnection
├── Health Status Tracking
├── Prometheus Metrics
└── Dynamic Symbol Loading

    ├── BinanceCollector (WebSocket)
    └── YahooCollector (Polling)
```

## Collectors

### 1. BinanceCollector
**Status:** ✅ Implemented  
**Type:** WebSocket (Real-time)  
**Exchange:** Binance  
**Asset Class:** Cryptocurrency

**Features:**
- Real-time trade and kline data via WebSocket
- Dynamic symbol loading from database
- 24-hour connection refresh mechanism
- Multiple timeframe support (1m, 5m, 15m, 1h)
- Rate limiting (1200 req/min)
- Circuit breaker protection

**Configuration:** `config/exchanges.yaml` → `binance`

---

### 2. YahooCollector
**Status:** ✅ Implemented  
**Type:** Polling (5-minute interval)  
**Exchange:** Yahoo Finance  
**Asset Class:** Stocks & ETFs (Global Markets)

**Features:**
- 5-minute polling interval
- Dynamic symbol loading from database
- Global market support (US, EU, Asia, etc.)
- Timezone handling (configurable)
- Rate limiting (60 req/min)
- Exponential backoff on errors
- Direct OHLC data (no tick-to-bar conversion)
- Circuit breaker protection
- Support for stocks, ETFs, indices

**Configuration:** `config/exchanges.yaml` → `yahoo`

---

## Dynamic Symbol Management

All collectors load symbols dynamically from the `symbols` database table using `SymbolManager`:

```python
# Symbols are loaded at runtime
symbols = await self.symbol_manager.get_symbols_by_exchange(self.exchange)

# No hardcoded symbol lists!
```

**Benefits:**
- Add/remove symbols without code changes
- No deployment required for symbol updates
- Centralized symbol management
- Support for symbol metadata (display_name, asset_class, etc.)

---

## Common Features (Inherited from BaseCollector)

### Circuit Breaker Pattern
Protects against cascading failures:
- Configurable failure threshold
- Automatic recovery attempts
- Half-open state for testing
- Prometheus metrics

### Exponential Backoff
Reconnection strategy:
- Initial delay: 1s
- Max delay: 60s
- Multiplier: 2x
- Prevents overwhelming failed services

### Health Status Tracking
Real-time health monitoring:
- Connection status
- Trade count
- Error count
- Reconnection count
- Circuit breaker state
- Stored in Redis `system:health`

### Prometheus Metrics
Comprehensive observability:
- `trades_received_total` - Total trades by exchange/symbol
- `collector_errors_total` - Errors by exchange/type
- `websocket_reconnections_total` - Reconnection count
- `collector_status` - Current status (0=down, 1=up)
- `last_trade_timestamp` - Last trade timestamp

---

## Usage

### Running a Collector

```python
from collectors.yahoo_collector import YahooCollector
from storage.redis_cache import RedisCacheManager
from storage.symbol_manager import SymbolManager
import yaml

# Load configuration
with open('config/exchanges.yaml') as f:
    config = yaml.safe_load(f)

# Initialize dependencies
redis_client = RedisCacheManager(redis_url="redis://localhost:6379")
symbol_manager = SymbolManager(db_connection)

# Create collector
collector = YahooCollector(
    config=config['yahoo'],
    redis_client=redis_client,
    symbol_manager=symbol_manager
)

# Start collecting
await collector.start()
```

### Adding a New Symbol

```sql
-- Add new symbol to database
INSERT INTO symbols (asset_class, symbol, display_name, exchange, is_active)
VALUES ('BIST', 'ASELS.IS', 'Aselsan', 'yahoo', true);

-- Collector will automatically start collecting data for this symbol
-- No restart required!
```

---

## Configuration

### Exchange Configuration
Located in `config/exchanges.yaml`:

```yaml
yahoo:
  name: "Yahoo Finance"
  type: "stocks"
  enabled: true
  polling:
    interval: 300  # 5 minutes
    timeout: 30
  rest:
    rate_limit:
      requests_per_minute: 60
      backoff:
        initial_delay: 10
        max_delay: 300
        multiplier: 2
  market_hours:
    timezone: "Europe/Istanbul"
    open: "09:40"
    close: "18:10"
    days: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
  circuit_breaker:
    failure_threshold: 3
    timeout: 120
    success_threshold: 2
```

---

## Testing

Unit tests are located in `tests/unit/`:
- `test_binance_collector.py`
- `test_alpaca_collector.py`
- `test_yahoo_collector.py`
- `test_circuit_breaker.py`

Run tests:
```bash
pytest tests/unit/test_yahoo_collector.py -v
```

---

## Monitoring

### Health Check
```bash
# Check collector health in Redis
redis-cli HGETALL system:health
```

### Prometheus Metrics
```bash
# View metrics
curl http://localhost:9090/metrics | grep collector
```

### Logs
```bash
# View collector logs
tail -f logs/yahoo_collector.log
```

---

## Troubleshooting

### Collector Not Starting
1. Check database connection
2. Verify symbols table has active symbols
3. Check API credentials in `.env`
4. Review logs for errors

### No Data Received
1. Check market hours (for Alpaca/Yahoo)
2. Verify symbols are active in database
3. Check rate limiting
4. Review circuit breaker state

### Circuit Breaker Open
1. Check external service status
2. Review error logs
3. Wait for timeout period
4. Verify network connectivity

---

## Future Enhancements

- [ ] Add more exchanges (Coinbase, Kraken, etc.)
- [ ] Implement symbol hot-reloading (no restart)
- [ ] Add data quality validation
- [ ] Support for options and futures
- [ ] Multi-region deployment
- [ ] Advanced retry strategies

---

## Related Documentation

- [Base Collector](base_collector.py) - Abstract base class
- [Circuit Breaker](circuit_breaker.py) - Fault tolerance pattern
- [Symbol Manager](../storage/symbol_manager.py) - Dynamic symbol management
- [Redis Cache](../storage/redis_cache.py) - Caching and pub/sub
- [Design Document](../.kiro/specs/crypto-stock-platform/design.md)
- [Requirements](../.kiro/specs/crypto-stock-platform/requirements.md)
