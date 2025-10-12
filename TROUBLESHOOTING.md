# Troubleshooting Guide

Common issues and solutions for the Crypto-Stock Platform.

## Table of Contents

- [System Won't Start](#system-wont-start)
- [Database Issues](#database-issues)
- [Redis Issues](#redis-issues)
- [Collector Issues](#collector-issues)
- [API Issues](#api-issues)
- [Frontend Issues](#frontend-issues)
- [Performance Issues](#performance-issues)
- [WebSocket Issues](#websocket-issues)
- [Monitoring Issues](#monitoring-issues)
- [Data Quality Issues](#data-quality-issues)

## System Won't Start

### Docker Daemon Not Running

**Symptoms**:
```
Cannot connect to the Docker daemon
```

**Solution**:
```bash
# macOS
open -a Docker

# Linux
sudo systemctl start docker

# Verify
docker info
```

### Port Already in Use

**Symptoms**:
```
Error: bind: address already in use
```

**Solution**:
```bash
# Find process using port
lsof -i :8000  # Replace with your port
netstat -tulpn | grep 8000

# Kill process
kill -9 <PID>

# Or change port in docker-compose.yml
ports:
  - "8001:8000"  # Use different host port
```

### Insufficient Resources

**Symptoms**:
```
Error: not enough memory
Container keeps restarting
```

**Solution**:
```bash
# Check Docker resources
docker system df
docker stats

# Increase Docker resources (Docker Desktop)
# Settings → Resources → Increase Memory/CPU

# Or reduce resource usage
docker-compose down
docker system prune -a
```

### Environment Variables Not Set

**Symptoms**:
```
KeyError: 'DB_PASSWORD'
Configuration error
```

**Solution**:
```bash
# Check .env file exists
ls -la .env

# Copy from example
cp .env.example .env

# Edit with your values
nano .env

# Verify variables are loaded
docker-compose config
```

## Database Issues

### Cannot Connect to Database

**Symptoms**:
```
could not connect to server
Connection refused
```

**Diagnosis**:
```bash
# Check if database is running
docker-compose ps timescaledb

# Check logs
docker-compose logs timescaledb

# Check network
docker network ls
docker network inspect crypto-stock-network
```

**Solution**:
```bash
# Restart database
docker-compose restart timescaledb

# Wait for database to be ready
docker-compose exec timescaledb pg_isready -U admin

# Test connection
docker-compose exec timescaledb psql -U admin -d crypto_stock -c "SELECT 1;"
```

### Database Migrations Failed

**Symptoms**:
```
relation "candles" does not exist
Table not found
```

**Solution**:
```bash
# Check if migrations ran
docker-compose exec timescaledb psql -U admin -d crypto_stock -c "\dt"

# Run migrations manually
docker-compose exec timescaledb psql -U admin -d crypto_stock -f /docker-entrypoint-initdb.d/001_create_symbols_table.sql
docker-compose exec timescaledb psql -U admin -d crypto_stock -f /docker-entrypoint-initdb.d/002_create_candles_table.sql
# ... repeat for all migrations

# Or use migration script
./scripts/run_migrations.sh
```

### Database Out of Space

**Symptoms**:
```
ERROR: could not extend file
No space left on device
```

**Solution**:
```bash
# Check disk usage
df -h
docker system df

# Clean up old data
docker-compose exec timescaledb psql -U admin -d crypto_stock -c "
  DELETE FROM candles WHERE time < NOW() - INTERVAL '365 days';
  VACUUM FULL;
"

# Or increase volume size
# Edit docker-compose.yml and recreate volume
```

### Slow Queries

**Symptoms**:
- API responses taking > 1 second
- High database CPU usage

**Diagnosis**:
```sql
-- Check slow queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '1 second'
  AND state = 'active';

-- Check missing indexes
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname = 'public'
  AND tablename IN ('candles', 'indicators')
ORDER BY abs(correlation) DESC;
```

**Solution**:
```sql
-- Add indexes
CREATE INDEX IF NOT EXISTS idx_candles_symbol_time ON candles(symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_indicators_symbol_time ON indicators(symbol, time DESC);

-- Analyze tables
ANALYZE candles;
ANALYZE indicators;

-- Vacuum tables
VACUUM ANALYZE candles;
VACUUM ANALYZE indicators;
```

## Redis Issues

### Cannot Connect to Redis

**Symptoms**:
```
Error connecting to Redis
Connection refused
```

**Diagnosis**:
```bash
# Check if Redis is running
docker-compose ps redis

# Check logs
docker-compose logs redis

# Test connection
docker-compose exec redis redis-cli ping
```

**Solution**:
```bash
# Restart Redis
docker-compose restart redis

# Check Redis configuration
docker-compose exec redis redis-cli CONFIG GET maxmemory

# Test connection from API
docker-compose exec api python -c "
import redis
r = redis.Redis(host='redis', port=6379)
print(r.ping())
"
```

### Redis Out of Memory

**Symptoms**:
```
OOM command not allowed
Redis memory usage at 100%
```

**Diagnosis**:
```bash
# Check memory usage
docker-compose exec redis redis-cli INFO memory

# Check eviction policy
docker-compose exec redis redis-cli CONFIG GET maxmemory-policy
```

**Solution**:
```bash
# Increase memory limit
# Edit config/redis.conf
maxmemory 2gb

# Or flush cache
docker-compose exec redis redis-cli FLUSHDB

# Restart Redis
docker-compose restart redis
```

### Cache Not Working

**Symptoms**:
- Low cache hit rate
- API always queries database

**Diagnosis**:
```bash
# Check cache keys
docker-compose exec redis redis-cli KEYS "bars:*"

# Check TTL
docker-compose exec redis redis-cli TTL "bars:BTCUSDT:1m"

# Monitor cache operations
docker-compose exec redis redis-cli MONITOR
```

**Solution**:
```bash
# Verify cache is being written
docker-compose logs api | grep "cache"

# Check cache configuration
# Increase TTL in code if needed

# Clear and rebuild cache
docker-compose exec redis redis-cli FLUSHDB
docker-compose restart api
```

## Collector Issues

### No Data Being Collected

**Symptoms**:
- No recent candles in database
- Collector logs show no activity

**Diagnosis**:
```bash
# Check collector status
docker-compose ps collector
docker-compose logs collector

# Check database for recent data
docker-compose exec timescaledb psql -U admin -d crypto_stock -c "
  SELECT symbol, MAX(time) as latest
  FROM candles
  GROUP BY symbol
  ORDER BY latest DESC;
"

# Check collector health
curl http://localhost:8000/api/v1/health | jq '.components.collectors'
```

**Solution**:
```bash
# Restart collectors
docker-compose restart collector

# Check API keys are valid
# Edit .env and verify:
# - BINANCE_API_KEY
# - ALPACA_API_KEY

# Check symbols are active
docker-compose exec timescaledb psql -U admin -d crypto_stock -c "
  SELECT * FROM symbols WHERE active = true;
"

# Add symbols if needed
docker-compose exec timescaledb psql -U admin -d crypto_stock -c "
  INSERT INTO symbols (symbol, exchange, asset_type, active)
  VALUES ('BTCUSDT', 'binance', 'crypto', true);
"
```

### Collector Keeps Reconnecting

**Symptoms**:
```
WebSocket disconnected
Reconnecting...
Circuit breaker opened
```

**Diagnosis**:
```bash
# Check collector logs
docker-compose logs collector | grep -i "reconnect\|error"

# Check circuit breaker metrics
curl http://localhost:9090/api/v1/query?query=circuit_breaker_state

# Check network connectivity
docker-compose exec collector ping -c 3 api.binance.com
```

**Solution**:
```bash
# Check API rate limits
# Binance: 1200 requests/minute
# Alpaca: 200 requests/minute

# Increase circuit breaker thresholds
# Edit collectors/circuit_breaker.py
failure_threshold = 10  # Increase from 5
timeout = 120  # Increase from 60

# Check for API key issues
# Verify keys are valid and have correct permissions

# Restart collector
docker-compose restart collector
```

### Market Hours Issues (Alpaca/Yahoo)

**Symptoms**:
- No data during market hours
- Data collected outside market hours

**Diagnosis**:
```bash
# Check current time and market hours
docker-compose exec collector python -c "
from datetime import datetime
import pytz

now = datetime.now(pytz.timezone('America/New_York'))
print(f'Current time (ET): {now}')
print(f'Hour: {now.hour}')
print(f'Market open: {9 <= now.hour < 16}')
"
```

**Solution**:
```bash
# Verify timezone configuration
# Check collectors/alpaca_collector.py
# Ensure timezone is set correctly

# For testing outside market hours, disable market hours check
# Edit collector code temporarily

# Check for holidays
# Verify holiday calendar is up to date
```

## API Issues

### API Not Responding

**Symptoms**:
```
Connection refused
Timeout
502 Bad Gateway
```

**Diagnosis**:
```bash
# Check API status
docker-compose ps api
docker-compose logs api

# Test API health
curl http://localhost:8000/health

# Check if port is accessible
nc -zv localhost 8000
```

**Solution**:
```bash
# Restart API
docker-compose restart api

# Check for errors in logs
docker-compose logs api | grep -i "error"

# Verify dependencies are running
docker-compose ps timescaledb redis

# Test API manually
docker-compose exec api python -c "
from api.main import app
print('API loaded successfully')
"
```

### High API Latency

**Symptoms**:
- Requests taking > 1 second
- Timeouts

**Diagnosis**:
```bash
# Check API metrics
curl http://localhost:9090/api/v1/query?query=http_request_duration_seconds

# Check database query time
curl http://localhost:9090/api/v1/query?query=db_query_duration_seconds

# Check cache hit rate
curl http://localhost:9090/api/v1/query?query=cache_hits_total
```

**Solution**:
```bash
# Scale API servers
docker-compose up -d --scale api=3

# Optimize database queries
# Add indexes, use caching

# Increase cache TTL
# Edit storage/redis_cache.py

# Check for slow endpoints
docker-compose logs api | grep "duration"
```

### Rate Limiting Issues

**Symptoms**:
```
429 Too Many Requests
Rate limit exceeded
```

**Solution**:
```bash
# Check rate limit configuration
# Edit .env
RATE_LIMIT_REQUESTS=200  # Increase from 100
RATE_LIMIT_PERIOD=60

# Or disable rate limiting temporarily
# Edit api/middleware.py

# Check which client is hitting limit
docker-compose logs api | grep "429"

# Clear rate limit for specific client
docker-compose exec redis redis-cli DEL "rate_limit:192.168.1.100"
```

## Frontend Issues

### Frontend Not Loading

**Symptoms**:
- Blank page
- 404 errors
- Build errors

**Diagnosis**:
```bash
# Check frontend status
docker-compose ps frontend
docker-compose logs frontend

# Check if frontend is accessible
curl http://localhost:3000

# Check browser console for errors
# Open DevTools → Console
```

**Solution**:
```bash
# Rebuild frontend
cd frontend
npm install
npm run build

# Or rebuild Docker image
docker-compose build frontend
docker-compose up -d frontend

# Check environment variables
# Edit frontend/.env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

### Charts Not Updating

**Symptoms**:
- Static charts
- No real-time updates
- WebSocket errors

**Diagnosis**:
```bash
# Check WebSocket connection in browser console
# Should see: WebSocket connection established

# Check API WebSocket endpoint
wscat -c ws://localhost:8000/ws/BTCUSDT

# Check for errors
docker-compose logs api | grep -i "websocket"
```

**Solution**:
```bash
# Verify WebSocket URL is correct
# Check frontend/src/hooks/useWebSocket.ts

# Check CORS configuration
# Edit api/main.py
allow_origins=["http://localhost:3000"]

# Restart API
docker-compose restart api

# Clear browser cache
# Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
```

## Performance Issues

### High CPU Usage

**Diagnosis**:
```bash
# Check container CPU usage
docker stats

# Check which process is using CPU
docker-compose exec api top

# Check for infinite loops in logs
docker-compose logs api | tail -100
```

**Solution**:
```bash
# Limit CPU usage
# Edit docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '2'

# Optimize code
# Profile slow functions
# Reduce polling frequency

# Scale horizontally
docker-compose up -d --scale api=3
```

### High Memory Usage

**Diagnosis**:
```bash
# Check memory usage
docker stats

# Check for memory leaks
docker-compose logs api | grep -i "memory\|oom"

# Check cache size
docker-compose exec redis redis-cli INFO memory
```

**Solution**:
```bash
# Increase memory limits
# Edit docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4G

# Reduce cache size
# Edit config/redis.conf
maxmemory 1gb

# Restart services
docker-compose restart
```

## WebSocket Issues

### WebSocket Connection Fails

**Symptoms**:
```
WebSocket connection failed
Error 1006
Connection closed
```

**Diagnosis**:
```bash
# Test WebSocket manually
wscat -c ws://localhost:8000/ws/BTCUSDT

# Check API logs
docker-compose logs api | grep -i "websocket"

# Check authentication
wscat -c "ws://localhost:8000/ws/BTCUSDT?token=YOUR_TOKEN"
```

**Solution**:
```bash
# Verify WebSocket endpoint is correct
# Check API is running
curl http://localhost:8000/health

# Check authentication token
# Get new token from /api/v1/auth/login

# Check firewall/proxy settings
# Ensure WebSocket traffic is allowed

# Increase timeout
# Edit api/websocket.py
timeout = 300  # 5 minutes
```

### WebSocket Disconnects Frequently

**Symptoms**:
- Connection drops every few minutes
- Reconnection loops

**Solution**:
```bash
# Increase ping/pong interval
# Edit api/websocket.py
ping_interval = 30
ping_timeout = 10

# Check network stability
ping -c 100 localhost

# Implement reconnection logic
# Check frontend/src/hooks/useWebSocket.ts

# Check load balancer timeout
# If using nginx/load balancer, increase timeout
proxy_read_timeout 300s;
```

## Monitoring Issues

### Prometheus Not Scraping

**Symptoms**:
- No metrics in Prometheus
- Targets showing as down

**Diagnosis**:
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Check if metrics endpoint is accessible
curl http://localhost:8000/metrics

# Check Prometheus logs
docker-compose logs prometheus
```

**Solution**:
```bash
# Verify Prometheus configuration
cat monitoring/prometheus.yml

# Restart Prometheus
docker-compose restart prometheus

# Check network connectivity
docker-compose exec prometheus wget -O- http://api:8000/metrics
```

### Grafana Dashboards Not Loading

**Symptoms**:
- Empty dashboards
- No data points
- Datasource errors

**Diagnosis**:
```bash
# Check Grafana logs
docker-compose logs grafana

# Test Prometheus datasource
curl http://localhost:3001/api/datasources

# Check if Prometheus is accessible from Grafana
docker-compose exec grafana wget -O- http://prometheus:9090/api/v1/query?query=up
```

**Solution**:
```bash
# Verify datasource configuration
cat monitoring/grafana/datasources/prometheus.yml

# Restart Grafana
docker-compose restart grafana

# Re-import dashboards
# Grafana UI → Dashboards → Import
# Upload JSON files from monitoring/grafana/dashboards/
```

## Data Quality Issues

### Anomalous Data

**Symptoms**:
- Unrealistic prices
- Negative volumes
- Missing data points

**Diagnosis**:
```bash
# Check data quality metrics
curl http://localhost:8000/api/v1/quality/BTCUSDT

# Query database for anomalies
docker-compose exec timescaledb psql -U admin -d crypto_stock -c "
  SELECT * FROM data_quality_metrics
  WHERE quality_score < 70
  ORDER BY time DESC
  LIMIT 10;
"
```

**Solution**:
```bash
# Check data quality checker configuration
# Edit processors/data_quality.py

# Adjust thresholds
price_anomaly_threshold = 0.10  # 10% change
volume_anomaly_threshold = 100  # 100x average

# Delete bad data
docker-compose exec timescaledb psql -U admin -d crypto_stock -c "
  DELETE FROM candles
  WHERE symbol = 'BTCUSDT'
    AND (high < low OR volume < 0);
"

# Restart collectors
docker-compose restart collector
```

## Getting Help

If you can't resolve the issue:

1. **Check logs**: `docker-compose logs -f`
2. **Check health**: `./scripts/smoke_test.sh`
3. **Search issues**: [GitHub Issues](https://github.com/yourrepo/issues)
4. **Ask community**: [Discord/Slack]
5. **Contact support**: support@yourdomain.com

### Providing Information

When reporting issues, include:

```bash
# System information
uname -a
docker --version
docker-compose --version

# Service status
docker-compose ps

# Recent logs
docker-compose logs --tail=100 > logs.txt

# Configuration (remove secrets!)
docker-compose config > config.yml
```

## Preventive Maintenance

### Regular Tasks

**Daily**:
- Check system health
- Review error logs
- Monitor disk space

**Weekly**:
- Review performance metrics
- Check for updates
- Verify backups

**Monthly**:
- Update dependencies
- Review security
- Optimize database

### Health Check Script

```bash
#!/bin/bash
# health_check.sh

echo "=== System Health Check ==="

# Check services
docker-compose ps

# Check disk space
df -h | grep -E "/$|/var"

# Check database size
docker-compose exec timescaledb psql -U admin -d crypto_stock -c "
  SELECT pg_size_pretty(pg_database_size('crypto_stock'));
"

# Check recent errors
docker-compose logs --since 1h | grep -i "error" | wc -l

# Check API health
curl -s http://localhost:8000/health | jq '.status'

echo "=== Health Check Complete ==="
```

Run daily:
```bash
chmod +x health_check.sh
./health_check.sh
```
