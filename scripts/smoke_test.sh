#!/bin/bash

# Smoke Test - Quick system health check
# Verifies all critical components are working

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

FAILED_TESTS=0
PASSED_TESTS=0

log() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    PASSED_TESTS=$((PASSED_TESTS + 1))
}

fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    FAILED_TESTS=$((FAILED_TESTS + 1))
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Test API health endpoint
test_api_health() {
    log "Testing API health endpoint..."
    
    if response=$(curl -s http://localhost:8000/health); then
        if echo "$response" | grep -q '"status":"healthy"'; then
            pass "API is healthy"
            return 0
        else
            fail "API returned unhealthy status"
            echo "$response"
            return 1
        fi
    else
        fail "Cannot connect to API"
        return 1
    fi
}

# Test database connection
test_database() {
    log "Testing database connection..."
    
    if docker-compose exec -T timescaledb psql -U admin -d crypto_stock -c "SELECT 1;" > /dev/null 2>&1; then
        pass "Database is accessible"
        
        # Check if tables exist
        table_count=$(docker-compose exec -T timescaledb psql -U admin -d crypto_stock -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' \n')
        
        if [ "$table_count" -gt "0" ]; then
            pass "Database has $table_count tables"
        else
            fail "No tables found in database"
        fi
        
        return 0
    else
        fail "Cannot connect to database"
        return 1
    fi
}

# Test Redis connection
test_redis() {
    log "Testing Redis connection..."
    
    if docker-compose exec -T redis redis-cli ping | grep -q "PONG"; then
        pass "Redis is responding"
        
        # Check memory usage
        memory=$(docker-compose exec -T redis redis-cli INFO memory | grep "used_memory_human" | cut -d: -f2 | tr -d '\r')
        pass "Redis memory usage: $memory"
        
        return 0
    else
        fail "Cannot connect to Redis"
        return 1
    fi
}

# Test data collection
test_data_collection() {
    log "Testing data collection..."
    
    candle_count=$(docker-compose exec -T timescaledb psql -U admin -d crypto_stock -t -c "SELECT COUNT(*) FROM candles WHERE time > NOW() - INTERVAL '5 minutes';" 2>/dev/null | tr -d ' \n' || echo "0")
    
    if [ "$candle_count" -gt "0" ]; then
        pass "Data collection active: $candle_count recent candles"
        return 0
    else
        warn "No recent candles (may need more time)"
        return 0
    fi
}

# Test API endpoints
test_api_endpoints() {
    log "Testing API endpoints..."
    
    # Test symbols endpoint
    if curl -s http://localhost:8000/api/v1/symbols > /dev/null; then
        pass "Symbols endpoint responding"
    else
        fail "Symbols endpoint not responding"
    fi
    
    # Test health endpoint
    if curl -s http://localhost:8000/api/v1/health > /dev/null; then
        pass "Health endpoint responding"
    else
        fail "Health endpoint not responding"
    fi
}

# Test Prometheus
test_prometheus() {
    log "Testing Prometheus..."
    
    if curl -s http://localhost:9090/-/ready > /dev/null 2>&1; then
        pass "Prometheus is ready"
        
        # Check if metrics are being collected
        if curl -s "http://localhost:9090/api/v1/query?query=up" | grep -q '"status":"success"'; then
            pass "Prometheus is collecting metrics"
        else
            warn "Prometheus may not be collecting metrics yet"
        fi
        
        return 0
    else
        fail "Cannot connect to Prometheus"
        return 1
    fi
}

# Test Grafana
test_grafana() {
    log "Testing Grafana..."
    
    if curl -s http://localhost:3001/api/health > /dev/null 2>&1; then
        pass "Grafana is accessible"
        return 0
    else
        fail "Cannot connect to Grafana"
        return 1
    fi
}

# Test frontend
test_frontend() {
    log "Testing frontend..."
    
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        pass "Frontend is accessible"
        return 0
    else
        fail "Cannot connect to frontend"
        return 1
    fi
}

# Test Docker containers
test_containers() {
    log "Testing Docker containers..."
    
    # Get container status
    containers=$(docker-compose ps --format json 2>/dev/null || echo "[]")
    
    if [ "$containers" != "[]" ]; then
        # Count running containers
        running=$(docker-compose ps | grep -c "Up" || echo "0")
        total=$(docker-compose ps | tail -n +2 | wc -l | tr -d ' ')
        
        if [ "$running" -eq "$total" ]; then
            pass "All $total containers are running"
        else
            warn "$running/$total containers are running"
        fi
    else
        fail "No containers found"
    fi
}

# Test collector health
test_collectors() {
    log "Testing collectors..."
    
    # Check collector health from Redis
    if docker-compose exec -T redis redis-cli HGETALL "system:health" > /dev/null 2>&1; then
        pass "Collector health tracking active"
    else
        warn "Collector health not available yet"
    fi
}

# Test WebSocket
test_websocket() {
    log "Testing WebSocket..."
    
    # Check if wscat is installed
    if command -v wscat > /dev/null 2>&1; then
        # Get a test symbol
        symbol=$(curl -s http://localhost:8000/api/v1/symbols | grep -o '"[A-Z]*"' | head -1 | tr -d '"' || echo "BTCUSDT")
        
        if timeout 5 wscat -c "ws://localhost:8000/ws/$symbol" -x '{"type":"ping"}' > /dev/null 2>&1; then
            pass "WebSocket connection successful"
        else
            warn "WebSocket connection test inconclusive"
        fi
    else
        warn "wscat not installed, skipping WebSocket test"
    fi
}

# Main execution
main() {
    echo
    echo "🔥 Smoke Test - Quick System Health Check"
    echo "=========================================="
    echo
    
    # Run all tests
    test_containers
    test_database
    test_redis
    test_api_health
    test_api_endpoints
    test_data_collection
    test_prometheus
    test_grafana
    test_frontend
    test_collectors
    test_websocket
    
    # Summary
    echo
    echo "=========================================="
    echo "📊 Test Summary"
    echo "=========================================="
    echo
    
    TOTAL_TESTS=$((PASSED_TESTS + FAILED_TESTS))
    
    echo -e "${GREEN}Passed:${NC} $PASSED_TESTS"
    echo -e "${RED}Failed:${NC} $FAILED_TESTS"
    echo "Total:  $TOTAL_TESTS"
    echo
    
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "${GREEN}✓ All smoke tests passed!${NC}"
        echo
        return 0
    else
        echo -e "${RED}✗ Some tests failed${NC}"
        echo
        echo "Run full integration tests for details:"
        echo "  ./scripts/run_integration_tests.sh"
        echo
        return 1
    fi
}

# Run main
if main; then
    exit 0
else
    exit 1
fi
