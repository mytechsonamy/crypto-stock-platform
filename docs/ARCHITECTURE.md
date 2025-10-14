# System Architecture

## Overview

The Crypto-Stock Platform is a production-ready, real-time market data platform designed for high-throughput data collection, processing, and serving. The system follows an event-driven architecture with microservices pattern, ensuring scalability, fault tolerance, and real-time performance.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Frontend Layer                             │
│                    React + TypeScript + Vite                         │
│              Lightweight Charts + WebSocket Client                   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         │ HTTP/WebSocket (Port 3000)
                         │
┌────────────────────────▼────────────────────────────────────────────┐
│                         API Gateway Layer                            │
│                    FastAPI + WebSocket Server                        │
│         Authentication + Rate Limiting + CORS                        │
└─────┬──────────────────────────────────────────────┬────────────────┘
      │                                               │
      │ Async I/O                                     │ Pub/Sub
      │                                               │
┌─────▼──────────┐                          ┌────────▼───────────────┐
│  TimescaleDB   │                          │       Redis            │
│  Time-series   │◄─────────────────────────┤  Cache + Pub/Sub       │
│    Database    │      Query Cache         │   Message Broker       │
└────────────────┘                          └────────▲───────────────┘
      ▲                                               │
      │                                               │
      │ Write                                         │ Publish
      │                                               │
┌─────┴───────────────────────────────────────────────┴───────────────┐
│                      Processing Layer                                │
│         Bar Builder + Indicators + ML Features                       │
│              Data Quality Checker                                    │
└─────▲───────────────────────────────────────────────────────────────┘
      │
      │ Trade Events
      │
┌─────┴───────────────────────────────────────────────────────────────┐
│                    Data Collection Layer                             │
│            Binance + Yahoo Finance Collectors                        │
│              Circuit Breaker + Retry Logic                           │
└──────────────────────────────────────────────────────────────────────┘
      ▲
      │
      │ WebSocket/REST API
      │
┌─────┴───────────────────────────────────────────────────────────────┐
│                      External Data Sources                           │
│              Binance API + Yahoo Finance                             │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                      Monitoring & Observability                      │
│         Prometheus + Grafana + Structured Logging                    │
└──────────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. Data Collection Layer

**Purpose:** Collect real-time market data from multiple exchanges

**Components:**
- **BaseCollector**: Abstract base class with circuit breaker integration
- **BinanceCollector**: WebSocket client for Binance crypto data
- **YahooCollector**: Polling client for stock & ETF data (Yahoo Finance)

**Key Features:**
- Circuit breaker pattern for fault tolerance
- Exponential backoff reconnection
- Health status tracking
- Dynamic symbol management from database
- Rate limiting and request throttling

**Data Flow:**
```
External API → Collector → Circuit Breaker → Redis Pub/Sub → Processors
                    ↓
              Health Status → Redis
```

### 2. Processing Layer

**Purpose:** Transform raw trade data into OHLC bars, indicators, and ML features

**Components:**
- **BarBuilder**: Converts tick data to OHLC bars
- **IndicatorCalculator**: Calculates technical indicators
- **FeatureStore**: Engineers ML features
- **DataQualityChecker**: Validates data quality

**Key Features:**
- In-memory bar tracking for performance
- Time bucket rounding for multiple timeframes
- Vectorized indicator calculations with TA-Lib
- 60+ engineered features for ML
- Quality scoring and anomaly detection

**Data Flow:**
```
Trade Event → Data Quality Check → Bar Builder → Database
                                        ↓
                                  Bar Complete Event
                                        ↓
                              Indicator Calculator
                                        ↓
                                  Feature Store
                                        ↓
                              Database + Redis Cache
                                        ↓
                              Chart Update Event → WebSocket
```

### 3. Storage Layer

**Purpose:** Persist and cache time-series data efficiently

**Components:**
- **TimescaleDB**: Primary time-series database
- **Redis**: Cache and message broker
- **TimescaleManager**: Database connection pool and operations
- **RedisCacheManager**: Cache operations and pub/sub

**Key Features:**
- Hypertables for time-series optimization
- Continuous aggregates for higher timeframes
- Connection pooling (10-50 connections)
- Batch operations (10,000+ bars/sec)
- LRU cache eviction
- Pub/sub for real-time updates

**Database Schema:**

```sql
-- Symbols (Dynamic symbol management)
symbols (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE,
    exchange VARCHAR(20),
    asset_type VARCHAR(20),
    active BOOLEAN,
    created_at TIMESTAMPTZ
)

-- Candles (Hypertable)
candles (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    PRIMARY KEY (time, symbol, timeframe)
)

-- Indicators (Hypertable)
indicators (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    rsi DOUBLE PRECISION,
    macd DOUBLE PRECISION,
    macd_signal DOUBLE PRECISION,
    macd_histogram DOUBLE PRECISION,
    bb_upper DOUBLE PRECISION,
    bb_middle DOUBLE PRECISION,
    bb_lower DOUBLE PRECISION,
    sma_20 DOUBLE PRECISION,
    sma_50 DOUBLE PRECISION,
    sma_100 DOUBLE PRECISION,
    sma_200 DOUBLE PRECISION,
    ema_12 DOUBLE PRECISION,
    ema_26 DOUBLE PRECISION,
    ema_50 DOUBLE PRECISION,
    vwap DOUBLE PRECISION,
    stoch_k DOUBLE PRECISION,
    stoch_d DOUBLE PRECISION,
    atr DOUBLE PRECISION,
    adx DOUBLE PRECISION,
    volume_sma DOUBLE PRECISION,
    PRIMARY KEY (time, symbol, timeframe)
)

-- ML Features (Hypertable)
ml_features (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    feature_version VARCHAR(10),
    features JSONB,
    PRIMARY KEY (time, symbol, timeframe)
)

-- Data Quality Metrics (Hypertable)
data_quality_metrics (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    quality_score DOUBLE PRECISION,
    checks_passed INTEGER,
    checks_failed INTEGER,
    anomalies JSONB,
    PRIMARY KEY (time, symbol)
)

-- Alerts
alerts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    symbol VARCHAR(20),
    condition VARCHAR(50),
    threshold DOUBLE PRECISION,
    channel VARCHAR(20),
    active BOOLEAN,
    cooldown INTEGER,
    one_time BOOLEAN,
    last_triggered TIMESTAMPTZ,
    created_at TIMESTAMPTZ
)
```

**Redis Data Structures:**

```
# Cached bars (Sorted Set)
bars:{symbol}:{timeframe} → ZSET (score=timestamp, value=bar_json)

# Cached indicators (Hash)
indicators:{symbol}:{timeframe}:latest → HASH (field=indicator, value=value)

# Cached features (Hash)
features:{symbol}:latest → HASH (field=feature, value=value)

# Health status (Hash)
system:health → HASH (field=collector, value=status_json)

# Rate limiting (String)
rate_limit:{client_id} → STRING (value=tokens, TTL=60s)

# Pub/Sub Channels
trades:{exchange} → Trade events
completed_bars → Bar completion events
chart_updates → Chart update events
alerts → Alert notifications
```

### 4. API Layer

**Purpose:** Serve data via REST and WebSocket APIs

**Components:**
- **FastAPI Application**: Main API server
- **AuthManager**: JWT authentication
- **RateLimiter**: Token bucket rate limiting
- **ConnectionManager**: WebSocket connection management
- **AlertManager**: Alert system

**Key Features:**
- RESTful API with versioning (/api/v1)
- WebSocket for real-time updates
- JWT authentication with RBAC
- Rate limiting (100 req/min per client)
- CORS support
- OpenAPI/Swagger documentation

**API Endpoints:**

```
# Authentication
POST   /api/v1/auth/login
POST   /api/v1/auth/register
POST   /api/v1/auth/refresh

# Data
GET    /api/v1/symbols
GET    /api/v1/charts/{symbol}
GET    /api/v1/features/{symbol}
GET    /api/v1/quality/{symbol}

# Alerts
POST   /api/v1/alerts
GET    /api/v1/alerts
PUT    /api/v1/alerts/{id}
DELETE /api/v1/alerts/{id}

# Health
GET    /health
GET    /api/v1/health

# WebSocket
WS     /ws/{symbol}
```

### 5. Frontend Layer

**Purpose:** Visualize real-time market data

**Components:**
- **React Application**: Main UI framework
- **Lightweight Charts**: High-performance charting
- **Zustand Store**: State management
- **WebSocket Client**: Real-time updates

**Key Features:**
- Real-time chart updates (60 FPS)
- Multiple timeframes
- Technical indicators overlay
- Symbol selector
- Connection status indicator
- Responsive design

### 6. Monitoring Layer

**Purpose:** Observe system health and performance

**Components:**
- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboards
- **Loguru**: Structured logging

**Key Metrics:**
- Collector metrics (trades, errors, reconnections)
- Processing metrics (bars, indicators, features)
- Database metrics (queries, connections, latency)
- Cache metrics (hits, misses, memory)
- API metrics (requests, latency, errors)
- Circuit breaker metrics (state, transitions)

**Dashboards:**
1. Operational Dashboard - System overview
2. Data Quality Dashboard - Quality metrics
3. Circuit Breaker Dashboard - Fault tolerance
4. Database & Cache Dashboard - Storage performance

## Design Patterns

### 1. Circuit Breaker Pattern

**Purpose:** Prevent cascading failures from external API issues

**Implementation:**
- Three states: CLOSED, OPEN, HALF_OPEN
- Configurable failure threshold (default: 5)
- Timeout period (default: 60s)
- Success threshold for recovery (default: 2)

**Benefits:**
- Fail fast when external service is down
- Automatic recovery when service is back
- Prevents resource exhaustion

### 2. Event-Driven Architecture

**Purpose:** Decouple components and enable real-time processing

**Implementation:**
- Redis Pub/Sub for event distribution
- Async event handlers
- Event types: trades, completed_bars, chart_updates, alerts

**Benefits:**
- Loose coupling between components
- Scalable processing pipeline
- Real-time data flow

### 3. Repository Pattern

**Purpose:** Abstract data access logic

**Implementation:**
- TimescaleManager for database operations
- RedisCacheManager for cache operations
- SymbolManager for symbol management

**Benefits:**
- Testable data access
- Consistent interface
- Easy to swap implementations

### 4. Dependency Injection

**Purpose:** Manage component dependencies

**Implementation:**
- FastAPI dependency injection
- Shared database and cache connections
- Configurable components

**Benefits:**
- Testable components
- Flexible configuration
- Resource management

## Data Flow Sequences

### Real-time Data Collection

```
1. External API → Collector receives trade
2. Collector → Circuit Breaker checks health
3. Circuit Breaker → Data Quality Checker validates
4. Data Quality Checker → Bar Builder processes
5. Bar Builder → Database stores candle
6. Bar Builder → Redis publishes completed_bar event
7. Indicator Calculator → Subscribes to event
8. Indicator Calculator → Calculates indicators
9. Indicator Calculator → Database stores indicators
10. Indicator Calculator → Redis caches indicators
11. Indicator Calculator → Redis publishes chart_update
12. WebSocket Server → Broadcasts to clients
13. Frontend → Updates chart in real-time
```

### API Request Flow

```
1. Client → HTTP request to API
2. Middleware → Rate limiter checks limit
3. Middleware → Auth manager verifies JWT
4. Handler → Checks Redis cache
5. Handler → Falls back to database if cache miss
6. Handler → Returns data to client
7. Metrics → Records request latency
```

### WebSocket Connection Flow

```
1. Client → Connects to /ws/{symbol}
2. Server → Authenticates JWT token
3. Server → Registers connection
4. Server → Sends initial chart data
5. Server → Subscribes to chart_updates channel
6. Redis → Publishes chart update
7. Server → Filters by symbol
8. Server → Throttles updates (1/sec)
9. Server → Broadcasts to client
10. Client → Updates chart
```

## Scalability Considerations

### Horizontal Scaling

**Collectors:**
- Run multiple collector instances
- Each instance handles subset of symbols
- Load balance via symbol distribution

**API Servers:**
- Run multiple API instances behind load balancer
- Stateless design enables easy scaling
- WebSocket connections distributed across instances

**Processors:**
- Run multiple processor instances
- Each subscribes to Redis pub/sub
- Parallel processing of different symbols

### Vertical Scaling

**Database:**
- Increase connection pool size
- Add read replicas for queries
- Partition by symbol or time range

**Redis:**
- Increase memory allocation
- Use Redis Cluster for sharding
- Separate cache and pub/sub instances

**API:**
- Increase worker processes
- Tune connection limits
- Optimize query performance

## Performance Targets

| Component | Metric | Target | Actual |
|-----------|--------|--------|--------|
| Bar Builder | Completion Time | < 100ms | ~50ms |
| Indicator Calculator | Calculation Time | < 200ms | ~150ms |
| API | Response Time | < 100ms | ~50ms |
| WebSocket | Update Frequency | 1/sec | 1/sec |
| Database | Write Throughput | 10k bars/sec | 15k bars/sec |
| Cache | Hit Rate | > 80% | ~85% |

## Security Architecture

### Authentication
- JWT tokens with 60-minute expiration
- Refresh token mechanism
- Role-based access control (RBAC)

### Authorization
- Protected API endpoints
- WebSocket authentication
- User-specific data access

### Data Protection
- Environment variable secrets
- SQL injection prevention (parameterized queries)
- Input validation with Pydantic
- CORS configuration

### Network Security
- HTTPS/WSS in production
- Rate limiting per client
- DDoS protection via rate limiting

## Fault Tolerance

### Circuit Breaker
- Prevents cascading failures
- Automatic recovery
- Exponential backoff

### Retry Logic
- Configurable retry attempts
- Exponential backoff
- Jitter to prevent thundering herd

### Health Checks
- Component-level health monitoring
- Automatic service restart
- Graceful degradation

### Data Quality
- Anomaly detection
- Quality scoring
- Quarantine suspect data

## Deployment Architecture

### Development
```
Docker Compose
├── timescaledb (1 instance)
├── redis (1 instance)
├── collector (1 instance)
├── api (1 instance)
├── frontend (1 instance)
├── prometheus (1 instance)
└── grafana (1 instance)
```

### Production
```
Kubernetes Cluster
├── Database Tier
│   ├── TimescaleDB (3 replicas)
│   └── Redis Cluster (3 nodes)
├── Application Tier
│   ├── Collectors (3+ replicas)
│   ├── Processors (3+ replicas)
│   └── API (3+ replicas)
├── Frontend Tier
│   └── React App (CDN)
└── Monitoring Tier
    ├── Prometheus (HA)
    └── Grafana (HA)
```

## Technology Stack

### Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Database**: TimescaleDB (PostgreSQL)
- **Cache**: Redis
- **Async**: asyncio, asyncpg, aiohttp

### Frontend
- **Framework**: React 18
- **Language**: TypeScript
- **Charts**: Lightweight Charts
- **State**: Zustand
- **Build**: Vite

### DevOps
- **Containers**: Docker, Docker Compose
- **Monitoring**: Prometheus, Grafana
- **Logging**: Loguru
- **Testing**: pytest, pytest-asyncio

### External APIs
- **Binance**: python-binance (crypto data)
- **Yahoo Finance**: yfinance (stock & ETF data)

## Key Design Decisions

### Why TimescaleDB?
- Optimized for time-series data
- PostgreSQL compatibility
- Automatic partitioning
- Continuous aggregates
- Better performance than vanilla PostgreSQL

### Why Redis?
- In-memory speed for caching
- Pub/sub for real-time events
- Sorted sets for time-ordered data
- Simple data structures
- High availability options

### Why FastAPI?
- Async support out of the box
- Automatic OpenAPI documentation
- Type safety with Pydantic
- High performance
- Modern Python features

### Why Lightweight Charts?
- High performance (60 FPS)
- Small bundle size
- Mobile-friendly
- Customizable
- Active development

### Why Event-Driven?
- Loose coupling
- Real-time processing
- Scalable architecture
- Easy to add new features
- Fault isolation

## Future Enhancements

1. **Machine Learning Models**
   - Price prediction
   - Anomaly detection
   - Pattern recognition

2. **Advanced Features**
   - Backtesting engine
   - Portfolio management
   - Social trading

3. **Scalability**
   - Kubernetes deployment
   - Multi-region support
   - CDN for frontend

4. **Monitoring**
   - Distributed tracing
   - Log aggregation
   - APM integration

## References

- [TimescaleDB Documentation](https://docs.timescale.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Redis Documentation](https://redis.io/documentation)
- [Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
