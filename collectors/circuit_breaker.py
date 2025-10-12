"""
Circuit Breaker Pattern Implementation.

Provides fault tolerance by preventing cascading failures.
Automatically opens circuit after consecutive failures and
attempts recovery after timeout.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Circuit is open, requests fail immediately
- HALF_OPEN: Testing if service recovered, limited requests allowed
"""

import asyncio
import time
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass
from loguru import logger

from monitoring.metrics import (
    circuit_breaker_state,
    circuit_breaker_transitions_total,
    circuit_breaker_failures_total
)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = 0  # Normal operation
    OPEN = 1  # Circuit is open, fail fast
    HALF_OPEN = 0.5  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5  # Failures before opening
    timeout: float = 60.0  # Seconds before attempting recovery
    success_threshold: int = 2  # Successes in half-open before closing
    exponential_backoff: bool = True
    max_timeout: float = 300.0  # Maximum timeout (5 minutes)


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    
    def __init__(self, component: str, retry_after: float):
        self.component = component
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker is open for {component}. "
            f"Retry after {retry_after:.1f} seconds."
        )


class CircuitBreaker:
    """
    Circuit Breaker implementation for fault tolerance.
    
    Tracks failures and automatically opens circuit to prevent
    cascading failures. Attempts recovery after timeout period.
    
    Example:
        circuit_breaker = CircuitBreaker("binance_collector")
        
        async def risky_operation():
            return await circuit_breaker.call(some_async_function, arg1, arg2)
    """
    
    def __init__(
        self,
        component: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Initialize circuit breaker.
        
        Args:
            component: Component name for logging and metrics
            config: Circuit breaker configuration
        """
        self.component = component
        self.config = config or CircuitBreakerConfig()
        
        # State management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.opened_at: Optional[float] = None
        
        # Exponential backoff
        self.current_timeout = self.config.timeout
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Initialize metrics
        self._update_metrics()
        
        logger.info(
            f"Circuit breaker initialized for {component}: "
            f"failure_threshold={self.config.failure_threshold}, "
            f"timeout={self.config.timeout}s"
        )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Original exception from function
        """
        async with self._lock:
            # Check if circuit should transition to half-open
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    retry_after = self._get_retry_after()
                    raise CircuitBreakerOpenError(self.component, retry_after)
        
        # Execute function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
            
        except Exception as e:
            await self._on_failure(e)
            raise
    
    async def _on_success(self):
        """Handle successful execution."""
        async with self._lock:
            self.failure_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                
                if self.success_count >= self.config.success_threshold:
                    self._transition_to_closed()
            
            elif self.state == CircuitState.CLOSED:
                # Reset timeout on success in closed state
                self.current_timeout = self.config.timeout
    
    async def _on_failure(self, exception: Exception):
        """Handle failed execution."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            # Track failure in metrics
            circuit_breaker_failures_total.labels(
                component=self.component
            ).inc()
            
            logger.warning(
                f"Circuit breaker failure #{self.failure_count} "
                f"for {self.component}: {type(exception).__name__}"
            )
            
            # Check if should open circuit
            if self.state == CircuitState.CLOSED:
                if self.failure_count >= self.config.failure_threshold:
                    self._transition_to_open()
            
            elif self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open state reopens circuit
                self._transition_to_open()
    
    def _transition_to_open(self):
        """Transition circuit to OPEN state."""
        old_state = self.state
        self.state = CircuitState.OPEN
        self.opened_at = time.time()
        self.success_count = 0
        
        # Apply exponential backoff
        if self.config.exponential_backoff:
            self.current_timeout = min(
                self.current_timeout * 2,
                self.config.max_timeout
            )
        
        self._log_transition(old_state, CircuitState.OPEN)
        self._update_metrics()
        
        logger.error(
            f"Circuit breaker OPENED for {self.component} "
            f"after {self.failure_count} failures. "
            f"Timeout: {self.current_timeout:.1f}s"
        )
    
    def _transition_to_half_open(self):
        """Transition circuit to HALF_OPEN state."""
        old_state = self.state
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        self.failure_count = 0
        
        self._log_transition(old_state, CircuitState.HALF_OPEN)
        self._update_metrics()
        
        logger.info(
            f"Circuit breaker HALF-OPEN for {self.component}. "
            f"Testing recovery..."
        )
    
    def _transition_to_closed(self):
        """Transition circuit to CLOSED state."""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.opened_at = None
        
        # Reset timeout on successful recovery
        self.current_timeout = self.config.timeout
        
        self._log_transition(old_state, CircuitState.CLOSED)
        self._update_metrics()
        
        logger.success(
            f"Circuit breaker CLOSED for {self.component}. "
            f"Service recovered."
        )
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.opened_at is None:
            return False
        
        elapsed = time.time() - self.opened_at
        return elapsed >= self.current_timeout
    
    def _get_retry_after(self) -> float:
        """Get seconds until retry is allowed."""
        if self.opened_at is None:
            return 0.0
        
        elapsed = time.time() - self.opened_at
        return max(0.0, self.current_timeout - elapsed)
    
    def _log_transition(self, from_state: CircuitState, to_state: CircuitState):
        """Log state transition and update metrics."""
        circuit_breaker_transitions_total.labels(
            component=self.component,
            from_state=from_state.name,
            to_state=to_state.name
        ).inc()
    
    def _update_metrics(self):
        """Update Prometheus metrics."""
        circuit_breaker_state.labels(
            component=self.component
        ).set(self.state.value)
    
    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state
    
    def get_stats(self) -> dict:
        """
        Get circuit breaker statistics.
        
        Returns:
            Dictionary with current stats
        """
        return {
            "component": self.component,
            "state": self.state.name,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "current_timeout": self.current_timeout,
            "retry_after": self._get_retry_after() if self.state == CircuitState.OPEN else 0,
            "opened_at": self.opened_at
        }
    
    async def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        async with self._lock:
            logger.info(f"Manually resetting circuit breaker for {self.component}")
            self._transition_to_closed()
