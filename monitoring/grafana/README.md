# Grafana Dashboards

This directory contains Grafana dashboard configurations for the Crypto-Stock Platform.

## Overview

The platform includes 4 comprehensive dashboards for monitoring different aspects of the system:

1. **Operational Dashboard** - Overall system performance and health
2. **Data Quality Dashboard** - Data validation and quality metrics
3. **Circuit Breaker Dashboard** - Fault tolerance and resilience monitoring
4. **Database & Cache Dashboard** - Storage and caching performance

## Setup

### Automatic Provisioning

Dashboards are automatically provisioned when Grafana starts via Docker Compose:

```yaml
volumes:
  - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
  - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources:ro
```

### Manual Import

If you need to manually import dashboards:

1. Access Grafana at `http://localhost:3001`
2. Login with credentials (default: admin/admin)
3. Go to Dashboards → Import
4. Upload the JSON file from `monitoring/grafana/dashboards/`

## Dashboards

### 1. Operational Dashboard

**UID:** `crypto-stock-operational`

Monitors core system operations and performance:

- **Trades Per Second**: Real-time trade ingestion rate by exchange and symbol
- **Bar Completion Latency (p95)**: Time to complete OHLC bars (target: <100ms)
- **Indicator Calculation Latency (p99)**: Technical indicator computation time (target: <200ms)
- **API Request Rate**: HTTP requests by endpoint and status code
- **WebSocket Connections**: Active real-time connections
- **Error Rate by Component**: Errors across collectors, processors, and API

**Use Cases:**
- Monitor system throughput and latency
- Identify performance bottlenecks
- Track API usage patterns
- Detect error spikes

### 2. Data Quality Dashboard

**UID:** `crypto-stock-data-quality`

Tracks data validation and quality metrics:

- **Data Quality Score**: Per-symbol quality score (0-1 scale)
- **Quality Checks: Passed vs Failed**: Validation results by check type
- **Anomalies Detected Over Time**: Price and volume anomalies
- **Volume Sanity Check Failures**: Unusual volume patterns
- **All Quality Checks Rate**: Comprehensive view of all validation checks

**Use Cases:**
- Monitor data integrity
- Detect anomalies and outliers
- Track quality trends over time
- Identify problematic symbols or exchanges

### 3. Circuit Breaker Dashboard

**UID:** `crypto-stock-circuit-breaker`

Monitors fault tolerance and resilience:

- **Circuit Breaker States**: Current state of each circuit breaker (CLOSED/HALF-OPEN/OPEN)
- **Circuit Breaker State Over Time**: State transitions timeline
- **State Transitions**: Frequency of state changes
- **Circuit Open Duration**: How long circuits remain open
- **Failure Rate by Component**: Failures triggering circuit breakers

**Use Cases:**
- Monitor system resilience
- Track external service reliability
- Identify components with frequent failures
- Optimize circuit breaker thresholds

### 4. Database & Cache Dashboard

**UID:** `crypto-stock-database-cache`

Tracks storage and caching performance:

- **Database Query Latency**: Query performance by operation and table (p95, p99)
- **Database Connection Pool**: Pool size and available connections
- **Cache Hit Rate**: Percentage of cache hits vs misses
- **Cache Hits vs Misses**: Detailed cache performance by type
- **Redis Memory Usage**: Memory consumption by cache type
- **Database Query Rate**: Query throughput by operation

**Use Cases:**
- Optimize database queries
- Monitor connection pool health
- Track cache effectiveness
- Identify memory issues

## Metrics Reference

### Collector Metrics
- `trades_received_total` - Total trades received
- `collector_errors_total` - Collector errors
- `websocket_reconnections_total` - WebSocket reconnections
- `collector_status` - Collector status (1=running, 0=stopped)

### Processing Metrics
- `bars_completed_total` - Completed OHLC bars
- `bar_completion_duration_seconds` - Bar completion time
- `indicator_calculation_duration_seconds` - Indicator calculation time
- `features_calculated_total` - ML features calculated

### Database Metrics
- `db_queries_total` - Database queries
- `db_query_duration_seconds` - Query duration
- `db_connection_pool_size` - Connection pool size
- `db_connections_available` - Available connections

### Cache Metrics
- `cache_hits_total` - Cache hits
- `cache_misses_total` - Cache misses
- `cache_size_bytes` - Cache size

### API Metrics
- `http_requests_total` - HTTP requests
- `http_request_duration_seconds` - Request duration
- `websocket_connections` - Active WebSocket connections
- `rate_limit_exceeded_total` - Rate limit violations

### Circuit Breaker Metrics
- `circuit_breaker_state` - Circuit state (0=closed, 0.5=half-open, 1=open)
- `circuit_breaker_transitions_total` - State transitions
- `circuit_breaker_failures_total` - Failures tracked

### Data Quality Metrics
- `data_quality_score` - Quality score (0-1)
- `data_quality_checks_total` - Quality checks
- `data_anomalies_detected_total` - Anomalies detected

### Alert Metrics
- `alerts_triggered_total` - Alerts triggered
- `alert_check_duration_seconds` - Alert check time
- `notifications_sent_total` - Notifications sent
- `notification_failures_total` - Notification failures

## Customization

### Adding New Panels

1. Edit the dashboard JSON file
2. Add a new panel object to the `panels` array
3. Configure the panel with appropriate queries and visualization
4. Restart Grafana or wait for auto-reload

### Modifying Queries

All queries use PromQL (Prometheus Query Language). Common patterns:

```promql
# Rate of counter over 1 minute
rate(metric_name[1m])

# Histogram quantile (p95)
histogram_quantile(0.95, sum(rate(metric_bucket[5m])) by (le, label))

# Percentage calculation
sum(metric_a) / (sum(metric_a) + sum(metric_b)) * 100
```

### Thresholds

Adjust thresholds in the `fieldConfig.defaults.thresholds` section:

```json
"thresholds": {
  "mode": "absolute",
  "steps": [
    {"color": "green", "value": null},
    {"color": "yellow", "value": 50},
    {"color": "red", "value": 100}
  ]
}
```

## Alerting

Grafana supports alerting based on dashboard queries. To set up alerts:

1. Edit a panel
2. Go to the Alert tab
3. Configure alert conditions
4. Set notification channels (email, Slack, webhook, etc.)

## Best Practices

1. **Refresh Rate**: Dashboards auto-refresh every 10 seconds
2. **Time Range**: Default is last 1 hour, adjustable in top-right
3. **Variables**: Use template variables for dynamic filtering
4. **Annotations**: Add annotations for deployments and incidents
5. **Folders**: Organize dashboards by team or service

## Troubleshooting

### Dashboard Not Loading

1. Check Grafana logs: `docker logs crypto-stock-grafana`
2. Verify Prometheus is running: `http://localhost:9090`
3. Check datasource configuration in Grafana UI

### No Data in Panels

1. Verify metrics are being collected: `http://localhost:9090/targets`
2. Check metric names match in queries
3. Ensure time range includes data
4. Verify Prometheus scrape configuration

### Performance Issues

1. Reduce query complexity
2. Increase scrape intervals
3. Use recording rules for expensive queries
4. Limit time range for heavy dashboards

## Resources

- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Documentation](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Dashboard Best Practices](https://grafana.com/docs/grafana/latest/best-practices/)
