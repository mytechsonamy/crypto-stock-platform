"""
Rate Limiting System using Token Bucket Algorithm.

Features:
- Token bucket algorithm
- Redis backend for distributed rate limiting
- Per-client rate limiting
- Configurable rate and period
- Prometheus metrics
- Retry-After header support
"""

import time
from typing import Optional, Tuple
from loguru import logger

from storage.redis_cache import RedisCacheManager
from prometheus_client import Counter


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter with Redis backend.
    
    Features:
    - Distributed rate limiting
    - Token bucket algorithm
    - Automatic token refill
    - Per-client tracking
    """
    
    # Prometheus metrics
    rate_limit_exceeded_total = Counter(
        'rate_limit_exceeded_total',
        'Total rate limit violations',
        ['client_id']
    )
    
    rate_limit_requests_total = Counter(
        'rate_limit_requests_total',
        'Total rate limit checks',
        ['client_id', 'result']
    )
    
    def __init__(
        self,
        redis_manager: RedisCacheManager,
        rate: int = 100,
        period: int = 60
    ):
        """
        Initialize rate limiter.
        
        Args:
            redis_manager: Redis manager for storage
            rate: Number of requests allowed
            period: Time period in seconds
        """
        self.redis = redis_manager
        self.rate = rate
        self.period = period
        self.refill_rate = rate / period  # Tokens per second
        
        logger.info(
            f"TokenBucketRateLimiter initialized: "
            f"{rate} requests per {period} seconds"
        )
    
    async def is_allowed(
        self,
        client_id: str,
        cost: int = 1
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if request is allowed under rate limit.
        
        Implements token bucket algorithm:
        1. Calculate tokens to add based on time elapsed
        2. Add tokens (up to bucket capacity)
        3. Check if enough tokens available
        4. Consume tokens if allowed
        
        Args:
            client_id: Client identifier (IP or user_id)
            cost: Number of tokens to consume (default: 1)
            
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        try:
            if not self.redis.client:
                # Fallback: allow if Redis unavailable
                logger.warning("Redis unavailable, allowing request")
                return True, None
            
            current_time = time.time()
            key = f"rate_limit:{client_id}"
            
            # Get current bucket state from Redis
            bucket_data = await self.redis.client.hgetall(key)
            
            if not bucket_data:
                # First request - initialize bucket
                tokens = self.rate - cost
                last_refill = current_time
                
                await self.redis.client.hset(
                    key,
                    mapping={
                        'tokens': str(tokens),
                        'last_refill': str(last_refill)
                    }
                )
                await self.redis.client.expire(key, self.period * 2)
                
                # Update metrics
                self.rate_limit_requests_total.labels(
                    client_id=client_id,
                    result='allowed'
                ).inc()
                
                logger.debug(f"Rate limit initialized for {client_id}")
                return True, None
            
            # Parse bucket state
            tokens = float(bucket_data.get('tokens', self.rate))
            last_refill = float(bucket_data.get('last_refill', current_time))
            
            # Calculate tokens to add
            time_elapsed = current_time - last_refill
            tokens_to_add = time_elapsed * self.refill_rate
            
            # Refill tokens (up to capacity)
            tokens = min(self.rate, tokens + tokens_to_add)
            
            # Check if enough tokens
            if tokens >= cost:
                # Consume tokens
                tokens -= cost
                
                # Update bucket state
                await self.redis.client.hset(
                    key,
                    mapping={
                        'tokens': str(tokens),
                        'last_refill': str(current_time)
                    }
                )
                await self.redis.client.expire(key, self.period * 2)
                
                # Update metrics
                self.rate_limit_requests_total.labels(
                    client_id=client_id,
                    result='allowed'
                ).inc()
                
                return True, None
            else:
                # Rate limit exceeded
                # Calculate retry after time
                tokens_needed = cost - tokens
                retry_after = int(tokens_needed / self.refill_rate) + 1
                
                # Update metrics
                self.rate_limit_exceeded_total.labels(
                    client_id=client_id
                ).inc()
                
                self.rate_limit_requests_total.labels(
                    client_id=client_id,
                    result='denied'
                ).inc()
                
                logger.warning(
                    f"Rate limit exceeded for {client_id}: "
                    f"tokens={tokens:.2f}, needed={cost}, "
                    f"retry_after={retry_after}s"
                )
                
                return False, retry_after
            
        except Exception as e:
            logger.error(f"Error in rate limiter: {e}")
            # Fallback: allow on error
            return True, None
    
    async def reset(self, client_id: str) -> bool:
        """
        Reset rate limit for a client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            True if successful
        """
        try:
            if not self.redis.client:
                return False
            
            key = f"rate_limit:{client_id}"
            await self.redis.client.delete(key)
            
            logger.info(f"Rate limit reset for {client_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")
            return False
    
    async def get_status(self, client_id: str) -> dict:
        """
        Get rate limit status for a client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            Dictionary with rate limit status
        """
        try:
            if not self.redis.client:
                return {
                    'available': False,
                    'error': 'Redis unavailable'
                }
            
            key = f"rate_limit:{client_id}"
            bucket_data = await self.redis.client.hgetall(key)
            
            if not bucket_data:
                return {
                    'tokens': self.rate,
                    'capacity': self.rate,
                    'refill_rate': self.refill_rate,
                    'period': self.period
                }
            
            current_time = time.time()
            tokens = float(bucket_data.get('tokens', self.rate))
            last_refill = float(bucket_data.get('last_refill', current_time))
            
            # Calculate current tokens
            time_elapsed = current_time - last_refill
            tokens_to_add = time_elapsed * self.refill_rate
            current_tokens = min(self.rate, tokens + tokens_to_add)
            
            return {
                'tokens': current_tokens,
                'capacity': self.rate,
                'refill_rate': self.refill_rate,
                'period': self.period,
                'last_refill': last_refill
            }
            
        except Exception as e:
            logger.error(f"Error getting rate limit status: {e}")
            return {
                'available': False,
                'error': str(e)
            }
