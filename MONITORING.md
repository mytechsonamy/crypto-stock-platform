# Monitoring Guide

Comprehensive monitoring setup for the Crypto-Stock Platform using Prometheus and Grafana.

## Table of Contents

- [Overview](#overview)
- [Prometheus Setup](#prometheus-setup)
- [Grafana Setup](#grafana-setup)
- [Available Metrics](#available-metrics)
- [Dashboards](#dashboards)
- [Alert Rules](#alert-rules)
- [Log Aggregation](#log-aggregation)
- [Performance Monitoring](#performance-monitoring)
- [Troubleshooting](#troubleshooting)

## Overview

The monitoring stack consists of:
- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and dashboards
- **Loguru**: Structured logging
- **AlertManager**: Alert routing and notification

### Architecture

```
Application → Prometheus Metrics → Prometheus → Grafana
                                        ↓
                                  AlertManager → Notifications
                                        ↓
                                  (Email, Slack, Webhook)
```

## Prometheus Setup

### Configuration

Prometheus is configured via `monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'crypto-stock-platform'
    environment: 'production'

# Alert manager configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

# Load alert rules
rule_files:
  - 'alerts/*.yml'

# Scrape configurations
scrape_configs:
  # API Server
  - job_name: 'api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s

  # Collectors
  - job_name: 'collectors'
    static_configs:
      - targets: ['collector:9090']
    scrape_interval: 15s

  # Processors
  - job_name: 'processors'
    static_configs:
      - targets: ['processor:9090']
    scrape_interval: 15s

  # Database
  - job_name: 'timescaledb'
    static_configs:
      - targets: ['timescaledb:9187']
    scrape_interval: 30s

  # Redis
  - job_name: 'redis'
    static_configs:
      - targets: ['redis:9121']
    scrape_interval: 30s

  # Prometheus itself
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

### Access Prometheus

- **URL**: http://localhost:9090
- **Query Interface**: http://localhost:9090/graph
- **Targets**: http://localhost:9090/targets
- **Alerts**: http://localhost:9090/alerts

### Common Queries

```promql
# API request rate
rate(http_requests_total[5m])

# API error rate
rate(http_requests_total{status=~"5.."}[5m])

# API latency (95th percentile)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Database query rate
rate(db_queries_total[5m])

# Cache hit rate
rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))

# Circuit breaker state
circuit_breaker_state

# Collector errors
rate(collector_errors_total[5m])
```

## Grafana Setup

### Configuration

Grafana is configured via provisioning files in `monitoring/grafana/`:

```
monitoring/grafana/
├── dashboards/
│   ├── operational-dashboard.json
│   ├── data-quality-dashboard.json
│   ├── circuit-breaker-dashboard.json
│   └── database-cache-dashboard.json
├── datasources/
│   └── prometheus.yml
└── README.md
```

### Access Grafana

- **URL**: http://localhost:3001
- **Default Credentials**: admin/admin (change on first login)

### Datasource Configuration

`monitoring/grafana/datasources/prometheus.yml`:

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

## Available Metrics

### Collector Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `trades_received_total` | Counter | Total trades received from exchange |
| `collector_errors_total` | Counter | Total collector errors |
| `websocket_reconnections_total` | Counter | Total WebSocket reconnections |
| `collector_health_status` | Gauge | Collector health (1=healthy, 0=unhealthy) |
| `data_collection_lag_seconds` | Gauge | Data collection lag in seconds |

**Labels**: `exchange`, `symbol`, `error_type`

**Example Queries**:
```promql
# Trades per second by exchange
rate(trades_received_total[1m])

# Error rate by exchange
rate(collector_errors_total[5m])

# Reconnection frequency
rate(websocket_reconnections_total[1h])
```

### Processing Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `bars_completed_total` | Counter | Total bars completed |
| `bar_completion_duration_seconds` | Histogram | Bar completion time |
| `indicator_calculation_duration_seconds` | Histogram | Indicator calculation time |
| `features_calculated_total` | Counter | Total ML features calculated |
| `feature_calculation_duration_seconds` | Histogram | Feature calculation time |
| `data_quality_score` | Gauge | Data quality score (0-100) |
| `data_quality_checks_failed_total` | Counter | Failed quality checks |

**Labels**: `symbol`, `timeframe`, `indicator`, `check_type`

**Example Queries**:
```promql
# Bar completion rate
rate(bars_completed_total[5m])

# Average bar completion time
rate(bar_completion_duration_seconds_sum[5m]) / rate(bar_completion_duration_seconds_count[5m])

# 95th percentile indicator calculation time
histogram_quantile(0.95, rate(indicator_calculation_duration_seconds_bucket[5m]))

# Quality score by symbol
avg(data_quality_score) by (symbol)
```

### Database Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `db_queries_total` | Counter | Total database queries |
| `db_query_duration_seconds` | Histogram | Query execution time |
| `db_connection_pool_size` | Gauge | Connection pool size |
| `db_connection_pool_available` | Gauge | Available connections |
| `db_errors_total` | Counter | Database errors |

**Labels**: `operation`, `table`, `error_type`

**Example Queries**:
```promql
# Query rate
rate(db_queries_total[5m])

# Average query time
rate(db_query_duration_seconds_sum[5m]) / rate(db_query_duration_seconds_count[5m])

# Connection pool utilization
(db_connection_pool_size - db_connection_pool_available) / db_connection_pool_size
```

### Cache Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `cache_hits_total` | Counter | Total cache hits |
| `cache_misses_total` | Counter | Total cache misses |
| `cache_operations_total` | Counter | Total cache operations |
| `cache_memory_bytes` | Gauge | Cache memory usage |
| `cache_evictions_total` | Counter | Total cache evictions |

**Labels**: `operation`, `key_pattern`

**Example Queries**:
```promql
# Cache hit rate
rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))

# Cache memory usage
cache_memory_bytes / 1024 / 1024  # Convert to MB

# Eviction rate
rate(cache_evictions_total[5m])
```

### API Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total HTTP requests |
| `http_request_duration_seconds` | Histogram | Request duration |
| `http_requests_in_progress` | Gauge | Requests in progress |
| `websocket_connections` | Gauge | Active WebSocket connections |
| `websocket_messages_sent_total` | Counter | WebSocket messages sent |
| `rate_limit_exceeded_total` | Counter | Rate limit violations |

**Labels**: `method`, `endpoint`, `status`, `symbol`

**Example Queries**:
```promql
# Request rate by endpoint
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])

# 99th percentile latency
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# Active WebSocket connections
websocket_connections

# Rate limit violations
rate(rate_limit_exceeded_total[5m])
```

### Circuit Breaker Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `circuit_breaker_state` | Gauge | Circuit state (0=closed, 1=open, 2=half-open) |
| `circuit_breaker_transitions_total` | Counter | State transitions |
| `circuit_breaker_failures_total` | Counter | Failures tracked |
| `circuit_breaker_successes_total` | Counter | Successes tracked |

**Labels**: `collector`, `from_state`, `to_state`

**Example Queries**:
```promql
# Circuit breaker state by collector
circuit_breaker_state

# Transition rate
rate(circuit_breaker_transitions_total[5m])

# Failure rate
rate(circuit_breaker_failures_total[5m])
```

## Dashboards

### 1. Operational Dashboard

**Purpose**: System overview and health monitoring

**Panels**:
- System Health Status
- Request Rate (RPS)
- Error Rate
- API Latency (p50, p95, p99)
- Active WebSocket Connections
- Database Query Rate
- Cache Hit Rate
- Collector Health Status

**Access**: http://localhost:3001/d/operational

### 2. Data Quality Dashboard

**Purpose**: Monitor data quality and validation

**Panels**:
- Quality Score by Symbol
- Failed Quality Checks
- Data Freshness
- Price Anomalies Detected
- Volume Anomalies Detected
- Quality Check Distribution
- Data Collection Lag

**Access**: http://localhost:3001/d/data-quality

### 3. Circuit Breaker Dashboard

**Purpose**: Monitor fault tolerance and resilience

**Panels**:
- Circuit Breaker States
- State Transitions
- Failure Rate by Collector
- Recovery Time
- Open Circuit Duration
- Half-Open Attempts

**Access**: http://localhost:3001/d/circuit-breaker

### 4. Database & Cache Dashboard

**Purpose**: Monitor storage performance

**Panels**:
- Database Query Rate
- Query Latency
- Connection Pool Utilization
- Cache Hit Rate
- Cache Memory Usage
- Cache Eviction Rate
- Database Size
- Redis Memory Usage

**Access**: http://localhost:3001/d/database-cache

## Alert Rules

### Critical Alerts

`monitoring/alerts/critical.yml`:

```yaml
groups:
  - name: critical
    interval: 30s
    rules:
      # API is down
      - alert: APIDown
        expr: up{job="api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "API is down"
          description: "API has been down for more than 1 minute"

      # High error rate
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High API error rate"
          description: "Error rate is {{ $value | humanizePercentage }}"

      # Database is down
      - alert: DatabaseDown
        expr: up{job="timescaledb"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Database is down"
          description: "Database has been down for more than 1 minute"

      # Redis is down
      - alert: RedisDown
        expr: up{job="redis"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Redis is down"
          description: "Redis has been down for more than 1 minute"
```

### Warning Alerts

`monitoring/alerts/warning.yml`:

```yaml
groups:
  - name: warning
    interval: 1m
    rules:
      # High API latency
      - alert: HighAPILatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API latency"
          description: "95th percentile latency is {{ $value }}s"

      # Low cache hit rate
      - alert: LowCacheHitRate
        expr: rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m])) < 0.7
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low cache hit rate"
          description: "Cache hit rate is {{ $value | humanizePercentage }}"

      # Circuit breaker open
      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state == 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Circuit breaker is open"
          description: "Circuit breaker for {{ $labels.collector }} is open"

      # High data collection lag
      - alert: HighDataCollectionLag
        expr: data_collection_lag_seconds > 60
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High data collection lag"
          description: "Data collection lag is {{ $value }}s for {{ $labels.symbol }}"

      # Low data quality score
      - alert: LowDataQualityScore
        expr: avg(data_quality_score) by (symbol) < 70
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low data quality score"
          description: "Quality score for {{ $labels.symbol }} is {{ $value }}"
```

### AlertManager Configuration

`monitoring/alertmanager.yml`:

```yaml
global:
  resolve_timeout: 5m
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@yourdomain.com'
  smtp_auth_username: 'alerts@yourdomain.com'
  smtp_auth_password: '<PASSWORD>'

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical'
      continue: true
    - match:
        severity: warning
      receiver: 'warning'

receivers:
  - name: 'default'
    email_configs:
      - to: 'team@yourdomain.com'

  - name: 'critical'
    email_configs:
      - to: 'oncall@yourdomain.com'
        headers:
          Subject: '[CRITICAL] {{ .GroupLabels.alertname }}'
    slack_configs:
      - api_url: '<SLACK_WEBHOOK_URL>'
        channel: '#alerts-critical'
        title: '[CRITICAL] {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

  - name: 'warning'
    email_configs:
      - to: 'team@yourdomain.com'
        headers:
          Subject: '[WARNING] {{ .GroupLabels.alertname }}'
    slack_configs:
      - api_url: '<SLACK_WEBHOOK_URL>'
        channel: '#alerts-warning'
```

## Log Aggregation

### Structured Logging

Logs are structured in JSON format for easy parsing:

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "collectors.binance",
  "message": "Trade received",
  "symbol": "BTCUSDT",
  "price": 50000.0,
  "volume": 1.5,
  "exchange": "binance"
}
```

### Log Levels

- **DEBUG**: Detailed information for debugging
- **INFO**: General informational messages
- **WARNING**: Warning messages for potential issues
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical errors requiring immediate attention

### Log Rotation

Logs are rotated daily and compressed:

```python
# monitoring/logger.py
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="00:00",  # Rotate at midnight
    retention="30 days",  # Keep for 30 days
    compression="gz",  # Compress old logs
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}",
    level="INFO"
)
```

### Viewing Logs

```bash
# Docker Compose
docker-compose logs -f api
docker-compose logs -f collector
docker-compose logs -f --tail=100 api

# Kubernetes
kubectl logs -f -n crypto-stock -l app=api
kubectl logs -f -n crypto-stock -l app=collector --tail=100

# Local files
tail -f logs/app_2024-01-15.log
zcat logs/app_2024-01-14.log.gz | grep ERROR
```

## Performance Monitoring

### Key Performance Indicators (KPIs)

| KPI | Target | Alert Threshold |
|-----|--------|-----------------|
| API Latency (p95) | < 100ms | > 500ms |
| API Error Rate | < 1% | > 5% |
| Bar Completion Time | < 100ms | > 200ms |
| Indicator Calculation | < 200ms | > 500ms |
| Database Query Time | < 50ms | > 200ms |
| Cache Hit Rate | > 80% | < 70% |
| WebSocket Update Rate | 1/sec | N/A |
| Data Collection Lag | < 10s | > 60s |

### Performance Queries

```promql
# API throughput (requests per second)
sum(rate(http_requests_total[5m]))

# API latency percentiles
histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))  # p50
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))  # p95
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))  # p99

# Database throughput (queries per second)
sum(rate(db_queries_total[5m]))

# Cache efficiency
sum(rate(cache_hits_total[5m])) / (sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))

# System resource usage
process_resident_memory_bytes / 1024 / 1024  # Memory in MB
rate(process_cpu_seconds_total[5m])  # CPU usage
```

## Troubleshooting

### High Memory Usage

**Symptoms**: OOM errors, slow performance

**Diagnosis**:
```promql
# Check memory usage
process_resident_memory_bytes

# Check cache memory
cache_memory_bytes
```

**Solutions**:
- Increase container memory limits
- Reduce cache size
- Optimize query patterns
- Check for memory leaks

### High API Latency

**Symptoms**: Slow response times, timeouts

**Diagnosis**:
```promql
# Check latency distribution
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Check database query time
histogram_quantile(0.95, rate(db_query_duration_seconds_bucket[5m]))

# Check cache hit rate
rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))
```

**Solutions**:
- Optimize database queries
- Increase cache TTL
- Add database indexes
- Scale API servers

### Circuit Breaker Frequently Opening

**Symptoms**: Circuit breaker state = 1 (open)

**Diagnosis**:
```promql
# Check circuit breaker state
circuit_breaker_state

# Check failure rate
rate(circuit_breaker_failures_total[5m])

# Check collector errors
rate(collector_errors_total[5m])
```

**Solutions**:
- Check external API status
- Increase failure threshold
- Increase timeout period
- Check network connectivity

### Low Cache Hit Rate

**Symptoms**: Cache hit rate < 70%

**Diagnosis**:
```promql
# Check hit rate
rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))

# Check eviction rate
rate(cache_evictions_total[5m])
```

**Solutions**:
- Increase cache memory
- Increase TTL
- Optimize cache key patterns
- Pre-warm cache

## Best Practices

1. **Set up alerts for critical metrics**
2. **Review dashboards regularly**
3. **Monitor trends over time**
4. **Set realistic alert thresholds**
5. **Document alert response procedures**
6. **Use structured logging**
7. **Aggregate logs centrally**
8. **Monitor resource usage**
9. **Test alert notifications**
10. **Keep dashboards up to date**

## Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Guide](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Dashboard Best Practices](https://grafana.com/docs/grafana/latest/best-practices/)
