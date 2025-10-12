# Monitoring & Observability

This directory contains monitoring and observability configuration for the Crypto-Stock Platform.

## Components

### 1. Logging (Loguru)

**File:** `logger.py`

**Features:**
- Structured logging with JSON format
- Console output (colored for development)
- File output with rotation (daily, 30-day retention)
- Separate error log file
- Contextual logging (component, symbol, etc.)

**Usage:**
```python
from monitoring.logger import get_logger, log_trade, log_performance

logger = get_logger("binance_collector")
logger.info("Collector started")

log_trade("BTCUSDT", 42000.50, 1.5, "binance")
log_performance("bar_completion", 85.5, symbol="BTCUSDT")
```

**Log Levels:**
- `DEBUG`: Detailed information for debugging
- `INFO`: General informational messages
- `WARNING`: Warning messages
- `ERROR`: Error messages with stack traces

**Log Files:**
- `logs/app_YYYY-MM-DD.log` - All logs
- `logs/error_YYYY-MM-DD.log` - Errors only

---

### 2. Metrics (Prometheus)

**File:** `metrics.py`

**Metrics Categories:**

#### Collector Metrics
- `trades_received_total` - Total trades received
- `collector_errors_total` - Collector errors
- `websocket_reconnections_total` - WebSocket reconnections
- `collector_status` - Collector status (1=running, 0=stopped)
- `last_trade_timestamp` - Last trade timestamp

#### Processing Metrics
- `bars_completed_total` - Completed bars
- `bar_completion_duration_seconds` - Bar completion time
- `indicator_calculation_duration_seconds` - Indicator calculation time
- `features_calculated_total` - ML features calculated
- `feature_calculation_duration_seconds` - Feature calculation time

#### Database Metrics
- `db_queries_total` - Database queries
- `db_query_duration_seconds` - Query duration
- `db_connection_pool_size` - Connection pool size
- `db_connections_available` - Available connections

#### Cache Metrics
- `cache_hits_total` - Cache hits
- `cache_misses_total` - Cache misses
- `cache_size_bytes` - Cache size

#### API Metrics
- `http_requests_total` - HTTP requests
- `http_request_duration_seconds` - Request duration
- `websocket_connections` - Active WebSocket connections
- `websocket_messages_sent_total` - WebSocket messages sent
- `rate_limit_exceeded_total` - Rate limit violations

#### Circuit Breaker Metrics
- `circuit_breaker_state` - Circuit breaker state
- `circuit_breaker_transitions_total` - State transitions
- `circuit_breaker_failures_total` - Failures tracked

#### Data Quality Metrics
- `data_quality_score` - Quality score (0-1)
- `data_quality_checks_total` - Quality checks
- `data_anomalies_detected_total` - Anomalies detected

**Usage:**
```python
from monitoring.metrics import (
    trades_received_total,
    bar_completion_duration,
    track_time
)

# Increment counter
trades_received_total.labels(exchange="binance", symbol="BTCUSDT").inc()

# Track duration
@track_time(bar_completion_duration.labels(symbol="BTCUSDT", timeframe="1m"))
async def complete_bar():
    # ... bar completion logic
    pass
```

**Metrics Endpoint:** `http://localhost:9091/metrics`

---

### 3. Prometheus Configuration

**File:** `prometheus.yml`

**Scrape Jobs:**
- `prometheus` - Self-monitoring (15s interval)
- `api` - FastAPI backend (15s interval)
- `collectors` - Data collectors (30s interval)
- `processor` - Data processor (15s interval)
- `timescaledb` - Database metrics (30s interval)
- `redis` - Cache metrics (30s interval)
- `node` - System metrics (30s interval)

**Access:** `http://localhost:9090`

---

### 4. Grafana Dashboards

**Directory:** `grafana/dashboards/`

**Dashboards:**
1. **Main Operational Dashboard**
   - Trades per second
   - Bar completion latency (p95)
   - Indicator calculation latency (p99)
   - API request rate
   - WebSocket connections
   - Error rate by component

2. **Data Quality Dashboard**
   - Quality score per symbol
   - Quality checks (passed vs failed)
   - Anomalies detected over time
   - Volume sanity check failures

3. **Circuit Breaker Dashboard**
   - Circuit breaker states
   - State transitions over time
   - Circuit open duration

4. **Database & Cache Dashboard**
   - Database query latency
   - Connection pool metrics
   - Cache hit rate
   - Redis memory usage

**Access:** `http://localhost:3001`
**Default Credentials:** admin / admin

---

## Quick Start

### 1. Start Monitoring Stack

```bash
docker-compose up -d prometheus grafana
```

### 2. Start Metrics Server in Application

```python
from monitoring.metrics import start_metrics_server

# Start metrics HTTP server
start_metrics_server(port=9091)
```

### 3. Access Dashboards

- **Prometheus:** http://localhost:9090
- **Grafana:** http://localhost:3001

---

## Queries

### Prometheus Queries

#### Trades per Second
```promql
rate(trades_received_total[1m])
```

#### Bar Completion Latency (p95)
```promql
histogram_quantile(0.95, rate(bar_completion_duration_seconds_bucket[5m]))
```

#### API Request Rate by Endpoint
```promql
sum(rate(http_requests_total[1m])) by (endpoint, status)
```

#### Cache Hit Rate
```promql
sum(rate(cache_hits_total[5m])) / (sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))
```

#### Circuit Breaker Open Count
```promql
sum(circuit_breaker_state == 1) by (component)
```

---

## Alerting

### Alert Rules (Optional)

Create `monitoring/alerts/rules.yml`:

```yaml
groups:
  - name: crypto_stock_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(collector_errors_total[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in {{ $labels.exchange }}"
          
      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state == 1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Circuit breaker open for {{ $labels.component }}"
          
      - alert: LowDataQuality
        expr: data_quality_score < 0.8
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low data quality for {{ $labels.symbol }}"
```

---

## Best Practices

1. **Use Labels Wisely** - Don't create too many unique label combinations
2. **Set Appropriate Scrape Intervals** - Balance between freshness and load
3. **Use Histograms for Latency** - Better than averages
4. **Monitor Your Monitors** - Check Prometheus/Grafana health
5. **Set Up Alerts** - Don't just collect metrics, act on them
6. **Use Dashboards** - Visualize trends and patterns
7. **Log Context** - Include relevant context in logs
8. **Correlate Logs and Metrics** - Use timestamps to correlate

---

## Troubleshooting

### Metrics Not Showing Up

1. Check if metrics server is running:
   ```bash
   curl http://localhost:9091/metrics
   ```

2. Check Prometheus targets:
   - Go to http://localhost:9090/targets
   - Verify all targets are "UP"

3. Check Prometheus logs:
   ```bash
   docker logs crypto-stock-prometheus
   ```

### High Memory Usage

1. Reduce retention period in `prometheus.yml`
2. Reduce scrape frequency
3. Use recording rules for expensive queries

### Missing Dashboards

1. Check Grafana provisioning:
   ```bash
   docker logs crypto-stock-grafana
   ```

2. Verify datasource configuration:
   - Go to Configuration > Data Sources
   - Test Prometheus connection

---

## Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Loguru Documentation](https://loguru.readthedocs.io/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
