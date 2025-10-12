#!/bin/bash

# Integration Test Runner
# Starts the system, runs integration tests, and generates report

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
TEST_REPORT_DIR="test_reports"
TIMESTAMP=$(date +'%Y%m%d_%H%M%S')
REPORT_FILE="$TEST_REPORT_DIR/integration_test_$TIMESTAMP.html"

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

# Create report directory
mkdir -p "$TEST_REPORT_DIR"

# Check if system is running
check_system() {
    log "Checking if system is running..."
    
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        log_error "System is not running. Please start it first with:"
        echo "  ./scripts/start_all.sh"
        exit 1
    fi
    
    log_success "System is running"
}

# Install test dependencies
install_dependencies() {
    log "Installing test dependencies..."
    
    pip install -q pytest pytest-asyncio pytest-html aiohttp websockets redis asyncpg
    
    log_success "Dependencies installed"
}

# Run integration tests
run_tests() {
    log "Running integration tests..."
    echo
    
    # Run pytest with HTML report
    if pytest tests/integration/test_data_flow.py \
        -v \
        -s \
        --html="$REPORT_FILE" \
        --self-contained-html \
        --tb=short; then
        
        log_success "All tests passed!"
        return 0
    else
        log_error "Some tests failed"
        return 1
    fi
}

# Generate summary
generate_summary() {
    local exit_code=$1
    
    echo
    echo "============================================"
    echo "📊 Integration Test Summary"
    echo "============================================"
    echo
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✓ All tests passed${NC}"
    else
        echo -e "${RED}✗ Some tests failed${NC}"
    fi
    
    echo
    echo "📄 Test Report: $REPORT_FILE"
    echo
    echo "🔍 View detailed results:"
    echo "  open $REPORT_FILE"
    echo
    echo "============================================"
}

# Main execution
main() {
    echo
    echo "🧪 Integration Test Runner"
    echo "=========================="
    echo
    
    check_system
    install_dependencies
    
    # Run tests and capture exit code
    if run_tests; then
        exit_code=0
    else
        exit_code=1
    fi
    
    generate_summary $exit_code
    
    exit $exit_code
}

# Handle interruption
trap 'log_error "Test run interrupted"; exit 1' INT TERM

# Run main
main "$@"
