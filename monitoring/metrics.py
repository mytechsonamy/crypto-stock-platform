"""
Prometheus metrics definitions for Crypto-Stock Platform.

Defines all metrics for monitoring:
- Collector metrics (trades, errors, reconnections)
- Processing metrics (bars, indicators, features)
- Database metrics (queries, connections)
- Cache metrics (hits, misses)
- API metrics (requests, latency)
- Circuit breaker metrics (state, transitions)
"""

from prometheus_client import (
    Counter, Gauge, Histogram, Summary, Info,
    CollectorRegistry, start_http_server
)
from typing import Dict
import time
from functools import wraps


# Create custom registry
registry = CollectorRegistry()

# ============================================================================
# COLLECTOR METRICS
# ============================================================================

# Trade events received
trades_received_total = Counter(
    'trades_received_total',
    'Total number of trade events received',
    ['exchange', 'symbol'],
    registry=registry
)

# Collector errors
collector_errors_total = Counter(
    'collector_errors_total',
    'Total number of collector errors',
    ['exchange', 'error_type'],
    registry=registry
)

# WebSocket reconnections
websocket_reconnections_total = Counter(
    'websocket_reconnections_total',
    'Total number of WebSocket reconnections',
    ['exchange'],
    registry=registry
)

# Collector status
collector_status = Gauge(
    'collector_status',
    'Collector status (1=running, 0=stopped)',
    ['exchange'],
    registry=registry
)

# Last trade timestamp
last_trade_timestamp = Gauge(
    'last_trade_timestamp',
    'Timestamp of last received trade',
    ['exchange', 'symbol'],
    registry=registry
)

# ============================================================================
# PROCESSING METRICS
# ============================================================================

# Bars completed
bars_completed_total = Counter(
    'bars_completed_total',
    'Total number of completed bars',
    ['symbol', 'timeframe'],
    registry=registry
)

# Bar completion duration
bar_completion_duration = Histogram(
    'bar_completion_duration_seconds',
    'Time taken to complete a bar',
    ['symbol', 'timeframe'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=registry
)

# Indicator calculation duration
indicator_calculation_duration = Histogram(
    'indicator_calculation_duration_seconds',
    'Time taken to calculate indicators',
    ['symbol'],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
    registry=registry
)

# Features calculated
features_calculated_total = Counter(
    'features_calculated_total',
    'Total number of ML features calculated',
    ['symbol'],
    registry=registry
)

# Feature calculation duration
feature_calculation_duration = Histogram(
    'feature_calculation_duration_seconds',
    'Time taken to calculate ML features',
    ['symbol'],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0],
    registry=registry
)

# ============================================================================
# DATABASE METRICS
# ============================================================================

# Database queries
db_queries_total = Counter(
    'db_queries_total',
    'Total number of database queries',
    ['operation', 'table'],
    registry=registry
)

# Query duration
db_query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['operation', 'table'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
    registry=registry
)

# Connection pool size
db_connection_pool_size = Gauge(
    'db_connection_pool_size',
    'Current database connection pool size',
    registry=registry
)

# Available connections
db_connections_available = Gauge(
    'db_connections_available',
    'Number of available database connections',
    registry=registry
)

# ============================================================================
# CACHE METRICS
# ============================================================================

# Cache hits
cache_hits_total = Counter(
    'cache_hits_total',
    'Total number of cache hits',
    ['cache_type'],
    registry=registry
)

# Cache misses
cache_misses_total = Counter(
    'cache_misses_total',
    'Total number of cache misses',
    ['cache_type'],
    registry=registry
)

# Cache size
cache_size_bytes = Gauge(
    'cache_size_bytes',
    'Current cache size in bytes',
    ['cache_type'],
    registry=registry
)

# ============================================================================
# API METRICS
# ============================================================================

# HTTP requests
http_requests_total = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=registry
)

# Request duration
http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=registry
)

# WebSocket connections
websocket_connections = Gauge(
    'websocket_connections',
    'Number of active WebSocket connections',
    ['symbol'],
    registry=registry
)

# WebSocket messages sent
websocket_messages_sent_total = Counter(
    'websocket_messages_sent_total',
    'Total number of WebSocket messages sent',
    ['symbol', 'message_type'],
    registry=registry
)

# Rate limit exceeded
rate_limit_exceeded_total = Counter(
    'rate_limit_exceeded_total',
    'Total number of rate limit violations',
    ['client_id'],
    registry=registry
)

# ============================================================================
# CIRCUIT BREAKER METRICS
# ============================================================================

# Circuit breaker state (0=closed, 1=open, 0.5=half-open)
circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state',
    ['component'],
    registry=registry
)

# Circuit breaker transitions
circuit_breaker_transitions_total = Counter(
    'circuit_breaker_transitions_total',
    'Total number of circuit breaker state transitions',
    ['component', 'from_state', 'to_state'],
    registry=registry
)

# Circuit breaker failures
circuit_breaker_failures_total = Counter(
    'circuit_breaker_failures_total',
    'Total number of failures tracked by circuit breaker',
    ['component'],
    registry=registry
)

# ============================================================================
# DATA QUALITY METRICS
# ============================================================================

# Quality score
data_quality_score = Gauge(
    'data_quality_score',
    'Data quality score (0-1)',
    ['symbol'],
    registry=registry
)

# Quality checks
data_quality_checks_total = Counter(
    'data_quality_checks_total',
    'Total number of data quality checks',
    ['symbol', 'check_type', 'result'],
    registry=registry
)

# Anomalies detected
data_anomalies_detected_total = Counter(
    'data_anomalies_detected_total',
    'Total number of data anomalies detected',
    ['symbol', 'anomaly_type'],
    registry=registry
)

# ============================================================================
# ALERT METRICS
# ============================================================================

# Alerts triggered
alerts_triggered_total = Counter(
    'alerts_triggered_total',
    'Total number of alerts triggered',
    ['symbol', 'condition'],
    registry=registry
)

# Alert check duration
alert_check_duration = Histogram(
    'alert_check_duration_seconds',
    'Time taken to check alerts',
    ['symbol'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1],
    registry=registry
)

# Notifications sent
notifications_sent_total = Counter(
    'notifications_sent_total',
    'Total number of notifications sent',
    ['channel', 'alert_id'],
    registry=registry
)

# Notification failures
notification_failures_total = Counter(
    'notification_failures_total',
    'Total number of notification failures',
    ['channel', 'alert_id'],
    registry=registry
)

# Active alerts
active_alerts_total = Gauge(
    'active_alerts_total',
    'Number of active alerts',
    ['symbol'],
    registry=registry
)

# ============================================================================
# SYSTEM METRICS
# ============================================================================

# Application info
app_info = Info(
    'app',
    'Application information',
    registry=registry
)

# Uptime
app_uptime_seconds = Gauge(
    'app_uptime_seconds',
    'Application uptime in seconds',
    ['component'],
    registry=registry
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def track_time(metric: Histogram):
    """Decorator to track execution time."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                metric.observe(duration)
        return wrapper
    return decorator


def increment_counter(metric: Counter, labels: Dict[str, str]):
    """Safely increment a counter with labels."""
    try:
        metric.labels(**labels).inc()
    except Exception:
        pass  # Ignore metric errors


def set_gauge(metric: Gauge, value: float, labels: Dict[str, str] = None):
    """Safely set a gauge value."""
    try:
        if labels:
            metric.labels(**labels).set(value)
        else:
            metric.set(value)
    except Exception:
        pass


def start_metrics_server(port: int = 9090):
    """
    Start Prometheus metrics HTTP server.
    
    Args:
        port: Port to listen on (default: 9090)
    """
    start_http_server(port, registry=registry)
    print(f"📊 Metrics server started on port {port}")


# Set application info
app_info.info({
    'version': '1.0.0',
    'environment': 'production'
})


# ============================================================================
# ARBITRAGE METRICS
# ============================================================================

# Arbitrage opportunities detected
arbitrage_opportunities_total = Counter(
    'arbitrage_opportunities_total',
    'Total arbitrage opportunities detected',
    ['symbol', 'buy_exchange', 'sell_exchange'],
    registry=registry
)
