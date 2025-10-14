# Crypto-Stock Platform

A production-ready real-time cryptocurrency and stock market data platform with advanced technical analysis, ML features, and comprehensive monitoring.

## 🚀 Features

### Data Collection
- **Multi-Exchange Support**: Binance (crypto), Yahoo Finance (stocks & ETFs)
- **Real-time Data**: WebSocket for crypto, polling for stocks
- **Circuit Breaker**: Fault-tolerant data collection with exponential backoff
- **Dynamic Symbol Management**: Database-driven symbol configuration
- **Historical Backfill**: Script for loading historical data

### Data Processing
- **OHLC Bar Building**: Real-time tick-to-bar conversion
- **Higher Timeframe Aggregation**: 1m → 5m, 15m, 1h, 4h, 1d
- **Technical Indicators**: RSI, MACD, Bollinger Bands, SMA, EMA, VWAP, Stochastic, ATR, ADX
- **ML Feature Engineering**: 60+ engineered features for machine learning
- **Data Quality Validation**: Automated quality checks and scoring

### Storage & Caching
- **TimescaleDB**: High-performance time-series database
- **Redis**: Caching and pub/sub for real-time updates
- **Connection Pooling**: Optimized database connections
- **Batch Operations**: 10,000+ bars/second throughput

### API & Real-time
- **REST API**: FastAPI with OpenAPI/Swagger documentation
- **WebSocket Server**: Real-time chart updates with throttling
- **Authentication**: JWT-based authentication with RBAC
- **Rate Limiting**: Token bucket algorithm with Redis backend
- **CORS Support**: Configurable cross-origin requests

### Monitoring & Alerts
- **Prometheus Metrics**: Comprehensive system metrics
- **Grafana Dashboards**: 4 pre-built dashboards
- **Alert System**: Price, RSI, MACD, volume alerts
- **Multi-channel Notifications**: WebSocket, Email, Webhook, Slack
- **Health Checks**: Component-level health monitoring

### Frontend
- **React + TypeScript**: Modern, type-safe UI
- **Lightweight Charts**: High-performance charting library
- **Real-time Updates**: WebSocket integration with throttling
- **Symbol Selector**: Dynamic symbol loading from API
- **Indicator Panel**: Toggle indicators on/off
- **Dark Theme**: Modern, professional UI

### DevOps
- **Docker Compose**: Complete containerized setup
- **Automated Backups**: Daily backups with retention policy
- **Disaster Recovery**: Comprehensive DR procedures
- **Configuration Management**: Hot-reload configuration
- **CI/CD Ready**: Prepared for automated deployment

## 📋 Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+ (for frontend)
- PostgreSQL 16 (via Docker)
- Redis 7 (via Docker)

## 🛠️ Quick Start

### 1. Clone Repository

```bash
git clone <repository-url>
cd crypto-stock-platform
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Required environment variables:
```env
# Database
DB_PASSWORD=your_secure_password
DB_NAME=crypto_stock
DB_USER=admin

# Exchange API Keys
BINANCE_API_KEY=your_binance_key
BINANCE_API_SECRET=your_binance_secret
# Yahoo Finance requires no API key

# JWT
JWT_SECRET=your_jwt_secret

# Optional: Cloud Storage
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
```

### 3. Start All Services (Automated)

```bash
# One-command startup with health checks
./scripts/start_all.sh
```

This script will:
- Start all Docker services
- Run database migrations
- Verify system health
- Test data flow
- Display service URLs

**Or start manually:**

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 4. Verify System Health

```bash
# Quick smoke test (30 seconds)
./scripts/smoke_test.sh

# Full integration test (5-10 minutes)
./scripts/run_integration_tests.sh
```

### 5. Access Services

- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090

## 📚 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [API Documentation](http://localhost:8000/docs)
- [Disaster Recovery](DISASTER_RECOVERY.md)
- [Configuration Management](config/README.md)
- [Monitoring Guide](monitoring/README.md)
- [Frontend Guide](frontend/README.md)

## 🧪 Testing

### Quick Health Check

```bash
# Smoke test - verifies all components (30 seconds)
./scripts/smoke_test.sh
```

### Integration Tests

```bash
# Full integration test suite (5-10 minutes)
./scripts/run_integration_tests.sh
```

This will test:
- Complete data flow (collector → database → API)
- Bar building and indicator calculation
- ML feature engineering
- WebSocket real-time updates
- API endpoints with authentication
- System resilience and error handling

### Unit Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/test_circuit_breaker.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

### Test Reports

Integration tests generate HTML reports:
```bash
# View latest test report
open test_reports/integration_test_*.html
```

See [Testing Guide](tests/README.md) for detailed information.

## 🔧 Development

### Backend Development

```bash
# Install dependencies
pip install -r requirements.txt

# Install test dependencies
pip install -r tests/requirements.txt

# Run tests
pytest tests/

# Run linting
black .
flake8 .
mypy .

# Start API server (development)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run linting
npm run lint
```

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│              React + TypeScript + Vite                       │
│           Lightweight Charts + WebSocket                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ HTTP/WebSocket
                     │
┌────────────────────▼────────────────────────────────────────┐
│                      FastAPI Server                          │
│         REST API + WebSocket + Authentication                │
└─────┬──────────────────────────────────────────┬────────────┘
      │                                           │
      │                                           │
┌─────▼──────────┐                    ┌──────────▼────────────┐
│  TimescaleDB   │                    │       Redis           │
│  Time-series   │                    │  Cache + Pub/Sub      │
│    Database    │                    │                       │
└────────────────┘                    └───────────────────────┘
      ▲                                           ▲
      │                                           │
      │                                           │
┌─────┴───────────────────────────────────────────┴───────────┐
│                    Data Processors                           │
│     Bar Builder + Indicators + ML Features                   │
└─────▲───────────────────────────────────────────────────────┘
      │
      │
┌─────┴───────────────────────────────────────────────────────┐
│                   Data Collectors                            │
│        Binance + Alpaca + Yahoo Finance                      │
└──────────────────────────────────────────────────────────────┘
```

## 🔐 Security

- JWT-based authentication
- Password hashing with bcrypt
- Rate limiting per client
- CORS configuration
- Environment variable secrets
- SQL injection protection
- Input validation

## 📈 Performance

- **Throughput**: 10,000+ bars/second
- **Latency**: <100ms bar completion
- **Indicators**: <200ms calculation
- **API Response**: <100ms (cached)
- **WebSocket**: 60 FPS updates
- **Database**: Connection pooling (10-50 connections)

## 🔄 Backup & Recovery

### Automated Backups

- **Schedule**: Daily at 2 AM UTC
- **Retention**: 7 daily, 4 weekly, 6 monthly
- **Location**: Local + S3/GCS
- **Encryption**: AES-256

### Restore Procedures

```bash
# Verify backup
python scripts/verify_backup.py --backup-dir ./backups

# Upload to cloud
python scripts/upload_backup.py --provider s3 --bucket my-bucket

# Test restore
python scripts/restore_test.py --test-env staging
```

See [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md) for detailed procedures.

## 📦 Scripts

### Historical Data Backfill

```bash
python scripts/backfill.py \
  --exchange binance \
  --symbol BTCUSDT \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --timeframe 1h
```

### Backup Verification

```bash
python scripts/verify_backup.py \
  --backup-dir ./backups \
  --host localhost \
  --port 5432
```

### Backup Upload

```bash
python scripts/upload_backup.py \
  --provider s3 \
  --bucket my-backups \
  --retention-days 90
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=. --cov-report=html tests/

# Run specific test
pytest tests/unit/test_circuit_breaker.py

# Run integration tests
pytest tests/integration/
```

## 📊 Monitoring

### Grafana Dashboards

1. **Operational Dashboard**: System performance and health
2. **Data Quality Dashboard**: Data validation metrics
3. **Circuit Breaker Dashboard**: Fault tolerance monitoring
4. **Database & Cache Dashboard**: Storage performance

### Prometheus Metrics

- Collector metrics (trades, errors, reconnections)
- Processing metrics (bars, indicators, features)
- Database metrics (queries, connections)
- Cache metrics (hits, misses)
- API metrics (requests, latency)
- Alert metrics (triggers, notifications)

## 🚀 Deployment

### Production Checklist

- [ ] Set strong passwords and secrets
- [ ] Configure SSL/TLS certificates
- [ ] Set up firewall rules
- [ ] Configure backup storage
- [ ] Set up monitoring alerts
- [ ] Test disaster recovery
- [ ] Configure log rotation
- [ ] Set resource limits
- [ ] Enable security headers
- [ ] Configure rate limits

### Docker Compose Production

```bash
# Use production compose file
docker-compose -f docker-compose.prod.yml up -d

# Scale services
docker-compose -f docker-compose.prod.yml up -d --scale collector=3
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## 📝 License

[Your License Here]

## 👥 Team

- DevOps Team
- Backend Team
- Frontend Team
- Data Team

## 📞 Support

- Documentation: [docs/](docs/)
- Issues: [GitHub Issues]
- Email: support@example.com

## 🎯 Roadmap

- [ ] Machine learning model training
- [ ] Advanced charting features
- [ ] Mobile app
- [ ] Additional exchanges
- [ ] Social trading features
- [ ] Portfolio management
- [ ] Backtesting engine

## 🙏 Acknowledgments

- TradingView for Lightweight Charts
- FastAPI framework
- TimescaleDB team
- Redis team
- All open-source contributors

---

**Built with ❤️ by the Crypto-Stock Platform Team**
