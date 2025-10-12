# Testing Guide

This directory contains all tests for the Crypto-Stock Platform.

## Test Structure

```
tests/
├── unit/                    # Unit tests for individual components
│   ├── test_circuit_breaker.py
│   ├── test_bar_builder.py
│   ├── test_indicators.py
│   └── ...
├── integration/             # Integration tests for complete flows
│   └── test_data_flow.py
└── README.md               # This file
```

## Test Types

### Unit Tests

Unit tests verify individual components in isolation:
- Circuit breaker logic
- Bar building algorithms
- Indicator calculations
- Data quality checks
- Authentication and authorization
- Rate limiting

**Run unit tests:**
```bash
pytest tests/unit/ -v
```

### Integration Tests

Integration tests verify complete data flows through the system:
- Data collection → Database → API
- Bar building → Indicator calculation → ML features
- WebSocket real-time updates
- API endpoints with authentication
- System resilience and error handling

**Run integration tests:**
```bash
./scripts/run_integration_tests.sh
```

This script will:
1. Check if the system is running
2. Install test dependencies
3. Run all integration tests
4. Generate an HTML report

### Smoke Tests

Quick health checks to verify all critical components are working:
- Docker containers status
- Database connectivity
- Redis connectivity
- API health
- Prometheus metrics
- Grafana dashboard
- Frontend accessibility

**Run smoke test:**
```bash
./scripts/smoke_test.sh
```

## Running Tests

### Prerequisites

1. **System must be running:**
   ```bash
   ./scripts/start_all.sh
   ```

2. **Wait for data collection:**
   - Integration tests require some data to be collected
   - Wait at least 2-3 minutes after startup
   - Check with smoke test first

### Quick Test (Smoke Test)

```bash
# Quick health check (30 seconds)
./scripts/smoke_test.sh
```

### Full Integration Test

```bash
# Complete integration test suite (5-10 minutes)
./scripts/run_integration_tests.sh
```

### Unit Tests Only

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/test_circuit_breaker.py -v

# Run specific test
pytest tests/unit/test_circuit_breaker.py::TestCircuitBreaker::test_state_transitions -v
```

## Test Reports

Integration tests generate HTML reports in `test_reports/`:

```bash
# View latest report
open test_reports/integration_test_*.html
```

Reports include:
- Test results (pass/fail)
- Execution time
- Error details and stack traces
- System logs during test execution

## Writing Tests

### Unit Test Example

```python
import pytest
from collectors.circuit_breaker import CircuitBreaker

class TestCircuitBreaker:
    @pytest.fixture
    def circuit_breaker(self):
        return CircuitBreaker(
            failure_threshold=3,
            timeout=60,
            success_threshold=2
        )
    
    @pytest.mark.asyncio
    async def test_state_transitions(self, circuit_breaker):
        # Test logic here
        assert circuit_breaker.state == "CLOSED"
```

### Integration Test Example

```python
import pytest
import aiohttp

class TestDataFlow:
    @pytest.mark.asyncio
    async def test_api_endpoint(self):
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/api/v1/symbols") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert len(data) > 0
```

## Test Coverage

Generate coverage report:

```bash
# Run tests with coverage
pytest tests/ --cov=. --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Continuous Integration

Tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Start services
  run: ./scripts/start_all.sh

- name: Wait for system
  run: sleep 60

- name: Run smoke test
  run: ./scripts/smoke_test.sh

- name: Run integration tests
  run: ./scripts/run_integration_tests.sh
```

## Troubleshooting

### Tests Fail with "System not running"

**Solution:** Start the system first:
```bash
./scripts/start_all.sh
```

### Tests Fail with "No data found"

**Solution:** Wait longer for data collection:
```bash
# Check if data is being collected
docker-compose logs -f collector

# Wait 2-3 minutes, then retry
./scripts/smoke_test.sh
```

### WebSocket Tests Timeout

**Solution:** Check WebSocket connectivity:
```bash
# Install wscat if needed
npm install -g wscat

# Test WebSocket manually
wscat -c ws://localhost:8000/ws/BTCUSDT
```

### Database Connection Errors

**Solution:** Verify database is running:
```bash
docker-compose ps timescaledb
docker-compose logs timescaledb

# Restart if needed
docker-compose restart timescaledb
```

### Redis Connection Errors

**Solution:** Verify Redis is running:
```bash
docker-compose ps redis
docker-compose exec redis redis-cli ping

# Should return PONG
```

## Performance Benchmarks

Integration tests verify performance targets:

| Metric | Target | Test |
|--------|--------|------|
| API Latency | < 100ms | `test_end_to_end_latency` |
| Bar Completion | < 100ms | `test_bar_building_flow` |
| Indicator Calculation | < 200ms | `test_indicator_calculation_flow` |
| WebSocket Update | < 1s | `test_websocket_realtime_updates` |

## Test Data

Tests use live data from running collectors. For deterministic tests:

1. Use fixtures with mock data
2. Seed database with known data
3. Use time-based queries for recent data

## Best Practices

1. **Isolation:** Each test should be independent
2. **Cleanup:** Clean up test data after tests
3. **Timeouts:** Use reasonable timeouts for async operations
4. **Assertions:** Use descriptive assertion messages
5. **Logging:** Log test progress for debugging
6. **Fixtures:** Reuse common setup with fixtures
7. **Mocking:** Mock external services in unit tests
8. **Real Services:** Use real services in integration tests

## Test Maintenance

### Adding New Tests

1. Create test file in appropriate directory
2. Follow naming convention: `test_*.py`
3. Use pytest fixtures for setup
4. Add docstrings explaining test purpose
5. Update this README if needed

### Updating Tests

1. Keep tests in sync with code changes
2. Update assertions when behavior changes
3. Add tests for new features
4. Remove tests for deprecated features

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [aiohttp testing](https://docs.aiohttp.org/en/stable/testing.html)
- [WebSocket testing](https://websockets.readthedocs.io/en/stable/intro/tutorial3.html)
