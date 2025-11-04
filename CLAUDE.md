# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **production-ready, event-driven real-time financial data platform** (v1.0.0) that collects, processes, and serves market data for both cryptocurrencies and stocks. The system handles 10,000+ bars/second with sub-100ms latency.

## Common Commands

### Quick Start
```bash
./scripts/start_all.sh        # One-command startup with health checks
./scripts/smoke_test.sh        # Quick 30-second health verification (run after startup)
./scripts/run_integration_tests.sh  # Full test suite (5-10 minutes)
```

### Development
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api              # API server logs
docker-compose logs -f binance-collector  # Binance data collector
docker-compose logs -f processor        # Data processing

# Check service health
docker-compose ps
curl http://localhost:8000/health       # API health check

# Run tests
pytest tests/unit/ -v                   # Unit tests
pytest tests/integration/ -v            # Integration tests
pytest -k test_name                     # Run specific test
```

### Database
```bash
# Access TimescaleDB
docker exec -it crypto-stock-platform-timescaledb-1 psql -U postgres -d trading

# Migrations run automatically on first start
# Located in: storage/migrations/*.sql

# Common queries
SELECT * FROM bars WHERE symbol = 'BTCUSDT' ORDER BY timestamp DESC LIMIT 10;
SELECT * FROM indicators WHERE symbol = 'AAPL' AND timeframe = '1h' ORDER BY timestamp DESC LIMIT 5;
```

### Monitoring
```bash
# Access monitoring dashboards
http://localhost:3000  # Grafana (admin/admin)
http://localhost:9090  # Prometheus

# Check metrics directly
curl http://localhost:8000/metrics
```

## Architecture

### High-Level Data Flow

```
External APIs (Binance WebSocket / Yahoo Finance REST)
    ↓
Collectors (with Circuit Breaker pattern)
    ↓ Publish to Redis channels
Data Quality Checker (validates all incoming data)
    ↓
Bar Builder (tick → OHLC aggregation)
    ↓ Store in TimescaleDB
Indicator Calculator (13 technical indicators)
    ↓
ML Feature Store (60+ features)
    ↓ Cache in Redis + Store in TimescaleDB
FastAPI (REST + WebSocket endpoints)
    ↓
React Frontend (real-time charts via Lightweight Charts)
```

### Six Architectural Layers

1. **Data Collection Layer** (`collectors/`)
   - `binance_collector.py` - WebSocket streaming for crypto (BTC, ETH, BNB)
   - `yahoo_collector.py` - Polling for stocks (AAPL, GOOGL, MSFT, etc.)
   - Base collector with circuit breaker for fault tolerance

2. **Processing Layer** (`processors/`)
   - `bar_builder.py` - Tick-to-OHLC conversion with multi-timeframe aggregation (1m → 5m, 15m, 1h, 4h, 1d)
   - `indicator_calculator.py` - 13 technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands, etc.)
   - `ml_features.py` - 60+ ML features for backtesting
   - `data_quality_checker.py` - Validates data before processing

3. **Storage Layer** (`storage/`)
   - **TimescaleDB** - Primary time-series database with hypertables and continuous aggregates
   - **Redis** - Caching (85% hit rate) + pub/sub messaging
   - Schema: `bars`, `indicators`, `ml_features` tables with automatic partitioning

4. **API Layer** (`api/`)
   - **REST API** - FastAPI with JWT authentication, rate limiting
   - **WebSocket** - Real-time market data streaming (throttled to 1/sec)
   - Key endpoints: `/bars/{symbol}`, `/indicators/{symbol}`, `/ws/subscribe`

5. **Frontend Layer** (`frontend/`)
   - React 18 + TypeScript + Vite
   - Lightweight Charts library for 60 FPS real-time charting
   - WebSocket client for live updates

6. **Monitoring Layer** (`monitoring/`)
   - Prometheus metrics (60+ custom metrics)
   - 4 Grafana dashboards: System Overview, Collector Health, Processor Performance, API Metrics
   - Structured JSON logging via Loguru

### Critical Architectural Patterns

**Dynamic Symbol Management**
- Symbols are loaded from database, NOT hardcoded
- To add new symbols: insert into `symbols` table, restart collector
- Location: `storage/timescale_manager.py:load_symbols()`

**Circuit Breaker Pattern**
- Protects against cascading failures
- Configuration in `config/exchanges.yaml`
- Auto-recovery after configurable timeout
- Location: `collectors/base_collector.py:circuit_breaker()`

**Multi-Timeframe Aggregation**
- Base 1m bars aggregated in-memory (BarBuilder) and via database continuous aggregates
- Supported timeframes: 1m, 5m, 15m, 1h, 4h, 1d
- Location: `processors/bar_builder.py:aggregate_bar()`

**Batch Operations**
- All database writes are batched for performance (10k+ bars/sec)
- Location: `storage/timescale_manager.py:batch_write()`

**Data Quality First**
- All data validated before processing
- Anomaly detection with configurable thresholds
- Location: `processors/data_quality_checker.py`

## Configuration

### Environment Variables
Key variables in `.env` (use `.env.example` as template):

```bash
# Database
DB_HOST=timescaledb
DB_PORT=5432
DB_NAME=trading
DB_USER=postgres
DB_PASSWORD=postgres

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# APIs
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
# Yahoo Finance requires no API keys

# Auth
JWT_SECRET=change_this_in_production

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
```

### Config Files

**`config/exchanges.yaml`** - Exchange-specific settings
- Rate limits per exchange
- Circuit breaker thresholds (failure_threshold, recovery_timeout)
- Retry policies
- WebSocket reconnection settings

**`config/settings.py`** - Application settings
- Loads from environment variables
- Validation via Pydantic
- Single source of truth for configuration

### Database Schema

**Hypertables** (auto-partitioned by time):
- `bars` - OHLCV data (timestamp, symbol, timeframe, open, high, low, close, volume)
- `indicators` - Technical indicators (timestamp, symbol, timeframe, indicator_name, value)
- `ml_features` - ML features (timestamp, symbol, feature_name, value)

**Regular Tables**:
- `symbols` - Available symbols (symbol, exchange, asset_type, is_active)
- `users` - User accounts with JWT authentication

**Continuous Aggregates**:
- Auto-aggregation from 1m → 5m, 15m, 1h, 4h, 1d bars
- Location: `storage/migrations/002_continuous_aggregates.sql`

## Docker Services

11 containers orchestrated via `docker-compose.yml`:

**Infrastructure**:
- `timescaledb` - PostgreSQL 16 + TimescaleDB extension
- `redis` - Redis 7 for cache and pub/sub
- `prometheus` - Metrics collection
- `grafana` - Dashboards (includes 4 pre-configured dashboards)
- `backup` - Automated daily backups with 7-day retention

**Application**:
- `binance-collector` - Crypto data collection via WebSocket
- `yahoo-collector` - Stock data collection via REST polling
- `processor` - Bar building + indicator calculation
- `api` - FastAPI REST + WebSocket server
- `frontend` - React app served via Nginx (production only)

### Docker Build Process

Multi-stage Dockerfiles for optimization:
- `docker/Dockerfile.api` - FastAPI backend
- `docker/Dockerfile.collector` - Data collectors
- `docker/Dockerfile.processor` - Data processing
- `docker/Dockerfile.frontend` - React app with Nginx

## Performance Targets

The system is designed to meet these benchmarks:

- **Bar Completion**: < 100ms (typical: ~50ms)
- **Indicator Calculation**: < 200ms (typical: ~150ms)
- **API Response**: < 100ms (typical: ~50ms)
- **Database Write**: > 10,000 bars/sec (typical: ~15,000)
- **Cache Hit Rate**: > 80% (typical: ~85%)
- **WebSocket Latency**: < 500ms (typical: ~200ms)

## Key Files to Understand

### Core Application
- `api/main.py` - FastAPI app entry point with lifespan management
- `collectors/base_collector.py` - Abstract collector with circuit breaker
- `collectors/binance_collector.py` - Binance WebSocket implementation
- `collectors/yahoo_collector.py` - Yahoo Finance REST polling
- `processors/bar_builder.py` - Tick-to-OHLC conversion
- `processors/indicator_calculator.py` - Technical indicator calculations
- `storage/timescale_manager.py` - Database operations and connection pooling
- `storage/redis_cache.py` - Caching and pub/sub messaging

### Configuration & Deployment
- `config/exchanges.yaml` - Exchange-specific settings
- `config/settings.py` - Application settings loader
- `.env.example` - Environment variables template
- `docker-compose.yml` - Service orchestration
- `scripts/start_all.sh` - Automated startup with health checks

### Database
- `storage/migrations/001_init_schema.sql` - Initial schema with hypertables
- `storage/migrations/002_continuous_aggregates.sql` - Multi-timeframe aggregates
- `storage/migrations/003_indexes.sql` - Performance indexes

## Testing Strategy

### Test Structure
- `tests/unit/` - Unit tests for individual components
- `tests/integration/` - Integration tests for service interactions
- `tests/fixtures/` - Shared test fixtures

### Running Tests
```bash
# All tests
pytest

# Specific test types
pytest tests/unit/
pytest tests/integration/

# With coverage
pytest --cov=. --cov-report=html

# Specific test
pytest -k test_bar_builder
```

### Integration Test Flow
The `./scripts/run_integration_tests.sh` script:
1. Starts all Docker services
2. Waits for health checks
3. Runs comprehensive tests
4. Validates data flow end-to-end
5. Tears down services

## Troubleshooting

### Common Issues

**Collectors not receiving data**
- Check API keys in `.env`
- Verify circuit breaker status: `docker-compose logs -f binance-collector | grep circuit`
- Check Redis connectivity: `docker exec -it redis redis-cli ping`

**Database connection errors**
- Ensure TimescaleDB is healthy: `docker-compose ps timescaledb`
- Check migrations ran: `docker exec timescaledb psql -U postgres -d trading -c "\dt"`
- Verify connection pool: Check API logs for "connection pool exhausted"

**WebSocket disconnections**
- Check rate limits in `config/exchanges.yaml`
- Verify network stability
- Review reconnection logic in collector logs

**Slow API responses**
- Check Redis cache hit rate: `curl http://localhost:8000/metrics | grep cache_hit`
- Review database query performance: Enable query logging in `config/settings.py`
- Check Grafana dashboards for bottlenecks

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
docker-compose up -d

# Watch structured logs
docker-compose logs -f api | jq .
```

## Development Workflow

### Adding a New Symbol

1. Insert into database:
```sql
INSERT INTO symbols (symbol, exchange, asset_type, is_active)
VALUES ('ETHUSDT', 'binance', 'crypto', true);
```

2. Restart collector:
```bash
docker-compose restart binance-collector
```

3. Verify in logs:
```bash
docker-compose logs binance-collector | grep ETHUSDT
```

### Adding a New Indicator

1. Add calculation to `processors/indicator_calculator.py`
2. Use pandas-ta (not TA-Lib for ARM compatibility)
3. Add to `calculate_all_indicators()` method
4. Write unit test in `tests/unit/test_indicator_calculator.py`
5. Restart processor service

### Modifying API Endpoints

1. Edit `api/main.py` or create new router in `api/routes/`
2. Add Pydantic models in `api/models/`
3. Update OpenAPI docs (automatic via FastAPI)
4. Add tests in `tests/unit/test_api.py`
5. Restart API service

## Important Notes

- **ARM Compatibility**: Uses pandas-ta instead of TA-Lib for cross-platform support
- **No Hardcoded Symbols**: All symbols loaded from database for dynamic management
- **Graceful Shutdown**: All services handle SIGTERM for clean shutdown
- **Health Checks**: Every service has health checks in docker-compose.yml
- **Automated Backups**: Daily backups with 7-day retention (configurable)
- **Rate Limiting**: API has rate limiting to prevent abuse
- **JWT Authentication**: All protected endpoints require JWT tokens
- **CORS**: Configured for frontend access, adjust in `api/main.py` if needed

## Resources

- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **Monitoring**: http://localhost:3000 (Grafana)
- **Metrics**: http://localhost:9090 (Prometheus)
- **Documentation**: See `docs/` directory and `*_GUIDE.md` files
