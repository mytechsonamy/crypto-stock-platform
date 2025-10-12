# Requirements Document

## Introduction

Bu proje, kripto para ve hisse senedi piyasalarından real-time ve gecikmeli veri toplayan, teknik indikatörlerle analiz eden ve profesyonel grafiklerde görselleştiren production-ready bir finansal veri platformudur. Platform üç farklı veri kaynağından (Binance, Alpaca, Yahoo Finance) veri toplayarak TimescaleDB'de saklayacak, Redis cache ile hızlı erişim sağlayacak ve React tabanlı bir frontend üzerinden TradingView benzeri grafiklerle kullanıcılara sunacaktır. Gelecekte AI/ML modelleri için veri altyapısı sağlayacak şekilde tasarlanmıştır.

## Requirements

### Requirement 1: Binance Real-time Veri Toplama

**User Story:** As a platform user, I want to receive real-time cryptocurrency trade data from Binance, so that I can monitor live price movements and trading activity.

#### Acceptance Criteria

1. WHEN the system starts THEN the Binance collector SHALL establish WebSocket connections for BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, and ADA/USDT trading pairs
2. WHEN a trade event is received via WebSocket THEN the system SHALL parse the trade data (price, quantity, timestamp) within 50ms
3. WHEN a WebSocket connection is established THEN the system SHALL subscribe to both trade streams and kline/candlestick streams (1m, 5m, 15m, 1h timeframes)
4. IF the WebSocket connection drops THEN the system SHALL automatically reconnect using exponential backoff strategy
5. WHEN the WebSocket connection has been active for 24 hours THEN the system SHALL proactively refresh the connection
6. WHEN historical data is needed THEN the system SHALL use Binance REST API to fetch historical kline data with respect to rate limits (1200 req/min)
7. WHEN rate limit is approached THEN the system SHALL queue requests and implement throttling mechanism

### Requirement 2: Alpaca Real-time Veri Toplama

**User Story:** As a platform user, I want to receive real-time US stock market data from Alpaca, so that I can track stock prices during market hours.

#### Acceptance Criteria

1. WHEN the system starts THEN the Alpaca collector SHALL establish WebSocket connections for AAPL, TSLA, NVDA, MSFT, GOOGL, AMZN, and META stocks
2. WHEN a trade event is received THEN the system SHALL process trade stream, quote stream, and bar stream data
3. WHEN market hours are active (09:30-16:00 ET, Mon-Fri) THEN the system SHALL receive and process real-time data
4. WHEN market is closed THEN the system SHALL handle the absence of data gracefully and implement reconnection logic for next market open
5. IF WebSocket connection fails THEN the system SHALL reconnect automatically with exponential backoff
6. WHEN historical data is needed THEN the system SHALL use Alpaca REST API v2 to fetch historical bars
7. WHEN using IEX data feed THEN the system SHALL handle free tier limitations appropriately

### Requirement 3: Yahoo Finance Gecikmeli Veri Toplama

**User Story:** As a platform user, I want to receive BIST stock data with 5-minute delay from Yahoo Finance, so that I can monitor Turkish stock market.

#### Acceptance Criteria

1. WHEN the system starts THEN the Yahoo collector SHALL initialize polling mechanism for THYAO.IS, GARAN.IS, ISCTR.IS, AKBNK.IS, and SISE.IS symbols
2. WHEN polling interval triggers (every 5 minutes) THEN the system SHALL fetch latest OHLC data using yfinance library
3. WHEN BIST market hours are active (09:40-18:10 TRT, Mon-Fri) THEN the system SHALL poll data actively
4. IF rate limiting occurs THEN the system SHALL implement exponential backoff and retry logic
5. WHEN API request fails THEN the system SHALL log the error and continue with next polling cycle without crashing
6. WHEN market is closed THEN the system SHALL reduce polling frequency or pause polling

### Requirement 4: Bar Builder ve OHLC Oluşturma

**User Story:** As a data processor, I want to convert individual trade ticks into OHLC candlestick bars, so that I can create standardized time-series data for analysis.

#### Acceptance Criteria

1. WHEN a trade tick is received THEN the system SHALL assign it to appropriate 1-minute time bucket based on timestamp
2. WHEN processing trades within a time bucket THEN the system SHALL calculate Open (first trade), High (maximum price), Low (minimum price), Close (last trade), and Volume (sum of quantities)
3. WHEN a time bucket completes THEN the system SHALL mark the bar as "completed" within 100ms
4. WHEN a bar is completed THEN the system SHALL write it to TimescaleDB and update Redis cache
5. WHEN building bars for multiple timeframes (1m, 5m, 15m, 1h) THEN the system SHALL aggregate 1-minute bars into higher timeframes
6. IF invalid or out-of-order trades are received THEN the system SHALL log and skip them without crashing
7. WHEN current bar is being built THEN the system SHALL maintain it in Redis for real-time access

### Requirement 5: Teknik İndikatör Hesaplama

**User Story:** As a trader, I want to see technical indicators calculated on price data, so that I can perform technical analysis.

#### Acceptance Criteria

1. WHEN a bar is completed THEN the system SHALL calculate technical indicators using TA-Lib library within 200ms
2. WHEN calculating indicators THEN the system SHALL compute RSI (14), MACD (12,26,9), Bollinger Bands (20,2), SMA (20,50,100,200), EMA (12,26,50), VWAP, and Stochastic (14,3,3)
3. WHEN calculating indicators THEN the system SHALL use a rolling window of last 200 bars for memory efficiency
4. WHEN indicators are calculated THEN the system SHALL store results in TimescaleDB indicators table
5. WHEN indicators are calculated THEN the system SHALL cache results in Redis with 5-minute TTL
6. WHEN insufficient data exists for indicator calculation THEN the system SHALL return null values gracefully
7. WHEN using vectorized operations THEN the system SHALL leverage pandas/numpy for batch calculations

### Requirement 6: TimescaleDB Veri Saklama

**User Story:** As a system administrator, I want to store time-series financial data efficiently, so that I can query historical data quickly and manage storage effectively.

#### Acceptance Criteria

1. WHEN the database is initialized THEN the system SHALL create hypertables for 'candles' and 'indicators' tables
2. WHEN storing candle data THEN the system SHALL include time, symbol, exchange, timeframe, open, high, low, close, and volume fields
3. WHEN storing indicator data THEN the system SHALL include time, symbol, and all calculated indicator values
4. WHEN writing data THEN the system SHALL support batch inserts of 10,000+ bars per second
5. WHEN data is older than 365 days THEN the system SHALL automatically delete it based on retention policy
6. WHEN querying data THEN the system SHALL use time-based indexes for optimal performance
7. WHEN database connection fails THEN the system SHALL implement connection pool recovery mechanism

### Requirement 7: Redis Cache ve Pub/Sub

**User Story:** As a system component, I want to use Redis for caching and real-time messaging, so that I can deliver low-latency data access and real-time updates.

#### Acceptance Criteria

1. WHEN a bar is completed THEN the system SHALL cache last 1000 bars per symbol in Redis hash structure
2. WHEN indicators are calculated THEN the system SHALL cache results in Redis with appropriate TTL
3. WHEN real-time trades arrive THEN the system SHALL publish them to Redis Pub/Sub channel 'trades:{exchange}'
4. WHEN processed chart data is ready THEN the system SHALL publish to 'chart_updates' channel for client consumption
5. WHEN system health check is performed THEN the system SHALL read collector statuses from 'system:health' hash
6. WHEN Redis connection fails THEN the system SHALL fall back to database queries and attempt reconnection
7. WHEN cache is queried THEN the system SHALL return data within 10ms

### Requirement 8: FastAPI REST ve WebSocket Server

**User Story:** As a frontend application, I want to access historical data via REST API and receive real-time updates via WebSocket, so that I can display live charts to users.

#### Acceptance Criteria

1. WHEN the API server starts THEN it SHALL expose REST endpoints: GET /charts, GET /symbols, GET /health
2. WHEN GET /charts is called with symbol and timeframe parameters THEN the system SHALL return historical OHLC and indicator data within 100ms
3. WHEN GET /symbols is called THEN the system SHALL return list of available symbols grouped by exchange
4. WHEN a WebSocket client connects THEN the system SHALL establish connection and wait for subscription requests
5. WHEN a client subscribes to a symbol THEN the system SHALL push real-time updates for that symbol
6. WHEN chart data updates THEN the system SHALL push updates to subscribed clients within 50ms
7. IF WebSocket connection is lost THEN the client SHALL be able to reconnect and resume subscription
8. WHEN API receives excessive requests THEN the system SHALL implement rate limiting per client
9. WHEN API documentation is accessed THEN the system SHALL serve Swagger/OpenAPI documentation

### Requirement 9: React Frontend ve Lightweight Charts

**User Story:** As an end user, I want to view professional trading charts with technical indicators, so that I can analyze market data visually.

#### Acceptance Criteria

1. WHEN the application loads THEN it SHALL display a candlestick chart using Lightweight Charts library
2. WHEN a symbol is selected from dropdown THEN the chart SHALL load historical data and switch to that symbol
3. WHEN a timeframe button is clicked (1m, 5m, 15m, 1h, 4h, 1d) THEN the chart SHALL reload data for that timeframe
4. WHEN displaying candlestick chart THEN it SHALL show OHLC data with zoom, pan, crosshair, and tooltip features
5. WHEN overlay indicators are enabled THEN the chart SHALL display Bollinger Bands, SMA, EMA, and VWAP on main chart
6. WHEN sub-panel indicators are enabled THEN the chart SHALL display Volume, RSI, MACD, and Stochastic in separate panels below
7. WHEN real-time data arrives via WebSocket THEN the chart SHALL update smoothly at 60 FPS
8. WHEN WebSocket sends updates THEN the frontend SHALL throttle updates to maximum 1 per second
9. WHEN multiple updates arrive within 100ms THEN the system SHALL batch them into single chart update
10. WHEN the application is responsive THEN it SHALL work on desktop and tablet screen sizes

### Requirement 10: Hata Yönetimi ve Logging

**User Story:** As a system administrator, I want comprehensive error handling and logging, so that I can monitor system health and troubleshoot issues.

#### Acceptance Criteria

1. WHEN any error occurs THEN the system SHALL log it using loguru with appropriate log level (ERROR, WARNING, INFO)
2. WHEN WebSocket disconnects THEN the system SHALL log the event and attempt reconnection without crashing
3. WHEN API rate limit is hit THEN the system SHALL log the event and implement backoff strategy
4. WHEN database connection fails THEN the system SHALL log the error and attempt connection pool recovery
5. WHEN invalid data is received THEN the system SHALL log and skip it without stopping the collector
6. WHEN critical errors occur THEN the system SHALL send alerts (optional: email, Slack, PagerDuty)
7. WHEN logs are written THEN they SHALL include timestamp, log level, component name, and contextual information
8. WHEN log files grow large THEN the system SHALL implement log rotation policy

### Requirement 11: Timezone ve Piyasa Saatleri Yönetimi

**User Story:** As a system component, I want to handle different timezones correctly, so that data timestamps are accurate across different markets.

#### Acceptance Criteria

1. WHEN storing timestamps THEN the system SHALL store all timestamps in UTC format
2. WHEN displaying timestamps in frontend THEN the system SHALL convert to user's local timezone
3. WHEN checking NYSE/NASDAQ market hours THEN the system SHALL use Eastern Time (ET) and handle DST transitions
4. WHEN checking BIST market hours THEN the system SHALL use Turkey Time (TRT) and handle DST transitions
5. WHEN market is closed THEN the system SHALL handle absence of data appropriately for each exchange
6. WHEN converting timezones THEN the system SHALL use reliable timezone libraries (pytz for Python, date-fns-tz for JavaScript)

### Requirement 12: Docker ve Deployment

**User Story:** As a DevOps engineer, I want to deploy the platform using Docker containers, so that I can ensure consistent environments and easy scaling.

#### Acceptance Criteria

1. WHEN deploying the platform THEN the system SHALL provide separate Dockerfiles for collector, processor, API, and frontend services
2. WHEN using docker-compose THEN the system SHALL orchestrate TimescaleDB, Redis, collectors, processors, API, and frontend containers
3. WHEN containers start THEN they SHALL read configuration from environment variables and .env file
4. WHEN database container starts THEN it SHALL automatically run migrations and create hypertables
5. WHEN scaling collectors THEN the system SHALL support horizontal scaling by symbol distribution
6. WHEN using Nginx THEN it SHALL act as reverse proxy for API and serve frontend static files
7. WHEN deploying to production THEN the system SHALL use production-optimized Docker images with multi-stage builds

### Requirement 13: Performans ve Ölçeklenebilirlik

**User Story:** As a platform operator, I want the system to handle high throughput and low latency, so that users receive real-time data without delays.

#### Acceptance Criteria

1. WHEN measuring WebSocket latency THEN it SHALL be less than 50ms from trade event to client delivery
2. WHEN completing a bar THEN the calculation and database write SHALL complete within 100ms
3. WHEN calculating indicators for 200 bars THEN it SHALL complete within 200ms
4. WHEN querying historical data via API THEN the response time SHALL be less than 100ms
5. WHEN rendering charts THEN the frontend SHALL maintain 60 FPS for smooth animations
6. WHEN processing trades THEN each collector SHALL use less than 2GB of memory
7. WHEN writing to database THEN the system SHALL support 10,000+ bars per second using batch inserts
8. WHEN handling concurrent users THEN the system SHALL support 1000+ concurrent WebSocket connections

### Requirement 14: Güvenlik ve Konfigürasyon

**User Story:** As a security-conscious operator, I want API keys and credentials to be stored securely, so that sensitive information is not exposed.

#### Acceptance Criteria

1. WHEN storing API keys THEN they SHALL be stored in environment variables, not hardcoded in source code
2. WHEN storing database credentials THEN they SHALL use Docker secrets or environment variables
3. WHEN configuring CORS THEN it SHALL be properly configured to allow only authorized origins
4. WHEN exposing public endpoints THEN they SHALL implement rate limiting to prevent abuse
5. WHEN authentication is required (optional) THEN it SHALL use JWT tokens or API keys
6. WHEN configuration changes THEN they SHALL be externalized in .env files or YAML configuration files
7. WHEN deploying to production THEN sensitive files (.env, credentials) SHALL be excluded from version control

### Requirement 15: Historical Data Backfill

**User Story:** As a platform operator, I want to backfill historical data when initializing the system, so that charts have sufficient historical context.

#### Acceptance Criteria

1. WHEN running backfill script THEN it SHALL fetch historical data from Binance REST API for specified date range
2. WHEN running backfill script THEN it SHALL fetch historical data from Alpaca REST API for specified date range
3. WHEN backfilling data THEN it SHALL respect API rate limits and implement throttling
4. WHEN backfill completes THEN it SHALL calculate and store indicators for all historical bars
5. WHEN backfill is interrupted THEN it SHALL be resumable from last successful point
6. WHEN backfill script runs THEN it SHALL log progress and completion status
7. WHEN backfilled data is stored THEN it SHALL be immediately available for querying via API
