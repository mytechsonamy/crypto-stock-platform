"""
Unit tests for Circuit Breaker implementation.

Tests state transitions, failure handling, and recovery logic.
"""

import pytest
import asyncio
from collectors.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerOpenError
)


class TestCircuitBreaker:
    """Test suite for CircuitBreaker class."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration with short timeouts."""
        return CircuitBreakerConfig(
            failure_threshold=3,
            timeout=0.5,  # 500ms for faster tests
            success_threshold=2,
            exponential_backoff=True,
            max_timeout=2.0
        )
    
    @pytest.fixture
    def circuit_breaker(self, config):
        """Create circuit breaker instance."""
        return CircuitBreaker("test_component", config)
    
    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self, circuit_breaker):
        """Test that circuit breaker starts in CLOSED state."""
        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_successful_call_in_closed_state(self, circuit_breaker):
        """Test successful function call in CLOSED state."""
        async def success_func():
            return "success"
        
        result = await circuit_breaker.call(success_func)
        assert result == "success"
        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_failure_increments_counter(self, circuit_breaker):
        """Test that failures increment failure counter."""
        async def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.get_state() == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self, circuit_breaker):
        """Test that circuit opens after failure threshold."""
        async def failing_func():
            raise ValueError("Test error")
        
        # Trigger failures up to threshold
        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)
        
        # Circuit should now be OPEN
        assert circuit_breaker.get_state() == CircuitState.OPEN
        assert circuit_breaker.opened_at is not None
    
    @pytest.mark.asyncio
    async def test_circuit_open_fails_fast(self, circuit_breaker):
        """Test that OPEN circuit fails immediately without calling function."""
        async def failing_func():
            raise ValueError("Should not be called")
        
        # Open the circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)
        
        # Next call should fail immediately with CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await circuit_breaker.call(failing_func)
        
        assert exc_info.value.component == "test_component"
        assert exc_info.value.retry_after > 0
    
    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open(self, circuit_breaker):
        """Test transition from OPEN to HALF_OPEN after timeout."""
        async def failing_func():
            raise ValueError("Test error")
        
        # Open the circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.get_state() == CircuitState.OPEN
        
        # Wait for timeout
        await asyncio.sleep(circuit_breaker.config.timeout + 0.1)
        
        # Next call should transition to HALF_OPEN
        async def success_func():
            return "success"
        
        result = await circuit_breaker.call(success_func)
        assert result == "success"
        assert circuit_breaker.get_state() == CircuitState.HALF_OPEN
    
    @pytest.mark.asyncio
    async def test_half_open_closes_after_successes(self, circuit_breaker):
        """Test that HALF_OPEN closes after success threshold."""
        async def failing_func():
            raise ValueError("Test error")
        
        async def success_func():
            return "success"
        
        # Open the circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)
        
        # Wait for timeout
        await asyncio.sleep(circuit_breaker.config.timeout + 0.1)
        
        # Transition to HALF_OPEN with first success
        await circuit_breaker.call(success_func)
        assert circuit_breaker.get_state() == CircuitState.HALF_OPEN
        
        # Second success should close circuit
        await circuit_breaker.call(success_func)
        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_half_open_reopens_on_failure(self, circuit_breaker):
        """Test that HALF_OPEN reopens on any failure."""
        async def failing_func():
            raise ValueError("Test error")
        
        async def success_func():
            return "success"
        
        # Open the circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)
        
        # Wait for timeout and transition to HALF_OPEN
        await asyncio.sleep(circuit_breaker.config.timeout + 0.1)
        await circuit_breaker.call(success_func)
        assert circuit_breaker.get_state() == CircuitState.HALF_OPEN
        
        # Failure should reopen circuit
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.get_state() == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self, circuit_breaker):
        """Test exponential backoff increases timeout."""
        async def failing_func():
            raise ValueError("Test error")
        
        initial_timeout = circuit_breaker.current_timeout
        
        # Open circuit first time
        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)
        
        first_timeout = circuit_breaker.current_timeout
        assert first_timeout == initial_timeout * 2
        
        # Wait and reopen
        await asyncio.sleep(first_timeout + 0.1)
        
        # Transition to HALF_OPEN and fail again
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)
        
        second_timeout = circuit_breaker.current_timeout
        assert second_timeout == first_timeout * 2
        assert second_timeout <= circuit_breaker.config.max_timeout
    
    @pytest.mark.asyncio
    async def test_manual_reset(self, circuit_breaker):
        """Test manual circuit reset."""
        async def failing_func():
            raise ValueError("Test error")
        
        # Open the circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.get_state() == CircuitState.OPEN
        
        # Manual reset
        await circuit_breaker.reset()
        
        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.opened_at is None
    
    @pytest.mark.asyncio
    async def test_get_stats(self, circuit_breaker):
        """Test getting circuit breaker statistics."""
        stats = circuit_breaker.get_stats()
        
        assert stats["component"] == "test_component"
        assert stats["state"] == "CLOSED"
        assert stats["failure_count"] == 0
        assert stats["success_count"] == 0
        assert "current_timeout" in stats
        assert "retry_after" in stats
    
    @pytest.mark.asyncio
    async def test_concurrent_calls(self, circuit_breaker):
        """Test circuit breaker with concurrent calls."""
        call_count = 0
        
        async def counting_func():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return call_count
        
        # Execute concurrent calls
        results = await asyncio.gather(
            circuit_breaker.call(counting_func),
            circuit_breaker.call(counting_func),
            circuit_breaker.call(counting_func),
            return_exceptions=True
        )
        
        # All should succeed
        assert len(results) == 3
        assert all(isinstance(r, int) for r in results)
        assert circuit_breaker.get_state() == CircuitState.CLOSED
