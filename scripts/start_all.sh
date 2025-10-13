#!/bin/bash

# Crypto-Stock Platform - Complete System Startup Script
# This script starts all services and verifies the complete data flow

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MAX_WAIT_TIME=300  # 5 minutes
HEALTH_CHECK_INTERVAL=5
LOG_DIR="logs"
TEST_SYMBOL="BTCUSDT"

# Create logs directory
mkdir -p "$LOG_DIR"

# Logging functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✓${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ✗${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    if [ ! -f ".env" ]; then
        log_error ".env file not found. Please copy .env.example to .env and configure it."
        exit 1
    fi
    
    if [ ! -f "docker-compose.yml" ]; then
        log_error "docker-compose.yml not found"
        exit 1
    fi
    
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Clean up existing containers
cleanup() {
    log "Cleaning up existing containers..."
    docker-compose down -v --remove-orphans > /dev/null 2>&1 || true
    log_success "Cleanup completed"
}

# Start infrastructure services
start_infrastructure() {
    log "Starting infrastructure services..."
    
    docker-compose up -d timescaledb redis
    
    log "Waiting for TimescaleDB..."
    local waited=0
    while [ $waited -lt $MAX_WAIT_TIME ]; do
        if docker-compose exec -T timescaledb pg_isready > /dev/null 2>&1; then
            log_success "TimescaleDB is ready"
            break
        fi
        sleep $HEALTH_CHECK_INTERVAL
        waited=$((waited + HEALTH_CHECK_INTERVAL))
    done
    
    log "Waiting for Redis..."
    waited=0
    while [ $waited -lt $MAX_WAIT_TIME ]; do
        if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
            log_success "Redis is ready"
            break
        fi
        sleep $HEALTH_CHECK_INTERVAL
        waited=$((waited + HEALTH_CHECK_INTERVAL))
    done
    
    log_success "Infrastructure services started"
}

# Run database migrations
run_migrations() {
    log "Running database migrations..."
    
    sleep 5
    
    local migrations=(
        "001_create_symbols_table.sql"
        "002_create_candles_table.sql"
        "003_create_data_quality_metrics_table.sql"
        "004_create_ml_features_table.sql"
        "005_create_alerts_table.sql"
    )
    
    for migration in "${migrations[@]}"; do
        log "Running migration: $migration"
        if docker-compose exec -T timescaledb psql -U admin -d crypto_stock -f "/docker-entrypoint-initdb.d/$migration" > "$LOG_DIR/migration_$migration.log" 2>&1; then
            log_success "Migration $migration completed"
        else
            log_warning "Migration $migration may have already been applied"
        fi
    done
    
    log_success "Database migrations completed"
}

# Start monitoring services
start_monitoring() {
    log "Starting monitoring services..."
    
    docker-compose up -d prometheus grafana
    
    log "Waiting for Prometheus..."
    local waited=0
    while [ $waited -lt $MAX_WAIT_TIME ]; do
        if curl -s http://localhost:9090/-/ready > /dev/null 2>&1; then
            log_success "Prometheus is ready"
            break
        fi
        sleep $HEALTH_CHECK_INTERVAL
        waited=$((waited + HEALTH_CHECK_INTERVAL))
    done
    
    log "Waiting for Grafana..."
    waited=0
    while [ $waited -lt $MAX_WAIT_TIME ]; do
        if curl -s http://localhost:3001/api/health > /dev/null 2>&1; then
            log_success "Grafana is ready"
            break
        fi
        sleep $HEALTH_CHECK_INTERVAL
        waited=$((waited + HEALTH_CHECK_INTERVAL))
    done
    
    log_success "Monitoring services started"
}

# Start application services
start_application() {
    log "Starting application services..."
    
    docker-compose up -d api processor binance-collector alpaca-collector yahoo-collector
    
    log "Waiting for API server..."
    local waited=0
    while [ $waited -lt $MAX_WAIT_TIME ]; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            log_success "API server is ready"
            break
        fi
        sleep $HEALTH_CHECK_INTERVAL
        waited=$((waited + HEALTH_CHECK_INTERVAL))
    done
    
    log_success "Application services started"
}

# Start frontend
start_frontend() {
    log "Starting frontend..."
    
    docker-compose up -d frontend
    
    log "Waiting for frontend..."
    local waited=0
    while [ $waited -lt $MAX_WAIT_TIME ]; do
        if curl -s http://localhost:3000 > /dev/null 2>&1; then
            log_success "Frontend is ready"
            break
        fi
        sleep $HEALTH_CHECK_INTERVAL
        waited=$((waited + HEALTH_CHECK_INTERVAL))
    done
    
    log_success "Frontend started"
}

# Verify system health
verify_system_health() {
    log "Verifying system health..."
    
    if ! curl -s http://localhost:8000/health | grep -q '"status":"healthy"'; then
        log_error "API health check failed"
        return 1
    fi
    log_success "API health check passed"
    
    if ! docker-compose exec -T timescaledb psql -U admin -d crypto_stock -c "SELECT 1;" > /dev/null 2>&1; then
        log_error "Database connection failed"
        return 1
    fi
    log_success "Database connection verified"
    
    if ! docker-compose exec -T redis redis-cli ping | grep -q "PONG"; then
        log_error "Redis connection failed"
        return 1
    fi
    log_success "Redis connection verified"
    
    log_success "System health verification completed"
}

# Test data flow
test_data_flow() {
    log "Testing end-to-end data flow..."
    
    log "Waiting for data collection to start..."
    sleep 30
    
    local candle_count=$(docker-compose exec -T timescaledb psql -U admin -d crypto_stock -t -c "SELECT COUNT(*) FROM candles WHERE time > NOW() - INTERVAL '1 hour';" 2>/dev/null | tr -d ' \n' || echo "0")
    
    if [ "$candle_count" -gt "0" ]; then
        log_success "Data flow verified: $candle_count recent candles found"
    else
        log_warning "No recent candles found. Data collection may take some time to start."
    fi
}

# Display service URLs
show_service_urls() {
    echo
    echo "============================================"
    echo "🚀 Crypto-Stock Platform is now running!"
    echo "============================================"
    echo
    echo "📊 Service URLs:"
    echo "  Frontend:    http://localhost:3000"
    echo "  API:         http://localhost:8000"
    echo "  API Docs:    http://localhost:8000/docs"
    echo "  Grafana:     http://localhost:3001 (admin/admin)"
    echo "  Prometheus:  http://localhost:9090"
    echo
    echo "📋 Useful Commands:"
    echo "  View logs:        docker-compose logs -f"
    echo "  Stop services:    docker-compose down"
    echo "  Restart service:  docker-compose restart <service>"
    echo "  Check status:     docker-compose ps"
    echo
    echo "🔍 Health Checks:"
    echo "  API Health:       curl http://localhost:8000/health"
    echo "  System Status:    curl http://localhost:8000/api/v1/health"
    echo "  Smoke Test:       ./scripts/smoke_test.sh"
    echo
    echo "🧪 Testing:"
    echo "  Run smoke test:   ./scripts/smoke_test.sh"
    echo "  Run full tests:   ./scripts/run_integration_tests.sh"
    echo
    echo "📝 Logs are saved in: $LOG_DIR/"
    echo "============================================"
}

# Main execution
main() {
    echo
    echo "🚀 Starting Crypto-Stock Platform..."
    echo "====================================="
    echo
    
    local start_time=$(date +%s)
    
    check_prerequisites
    cleanup
    start_infrastructure
    run_migrations
    start_monitoring
    start_application
    start_frontend
    verify_system_health
    test_data_flow
    
    local end_time=$(date +%s)
    local total_time=$((end_time - start_time))
    
    log_success "System startup completed in ${total_time} seconds"
    
    show_service_urls
}

# Handle interruption
trap 'log_error "Script interrupted"; exit 1' INT TERM

# Run main
main "$@"
