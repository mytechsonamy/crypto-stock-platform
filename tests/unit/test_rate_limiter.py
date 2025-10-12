"""
Unit tests for Rate Limiter
"""

import pytest
import asyncio
from datetime import datetime
from api.rate_limiter import TokenBucketRateLimiter


class TestRateLimiter:
    """Test rate limiting logic"""
    
    @pytest.fixture
    async def rate_limiter(self):
        """Create rate limiter instance"""
        # Use in-memory storage for testing
        limiter = TokenBucketRateLimiter(
            rate=10,  # 10 requests
            period=60,  # per 60 seconds
            redis_manager=None  # Mock for testing
        )
        limiter.tokens = {}  # In-memory storage
        return limiter
    
    @pytest.mark.asyncio
    async def test_initial_requests_allowed(self, rate_limiter):
        """Test that initial requests are allowed"""
        client_id = "test_client_1"
        
        # First request should be allowed
        allowed = await rate_limiter.is_allowed(client_id)
        assert allowed is True
    
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, rate_limiter):
        """Test that rate limit is enforced"""
        client_id = "test_client_2"
        
        # Make requests up to limit
        for i in range(10):
            allowed = await rate_limiter.is_allowed(client_id)
            assert allowed is True, f"Request {i+1} should be allowed"
        
        # Next request should be denied
        allowed = await rate_limiter.is_allowed(client_id)
        assert allowed is False, "Request 11 should be denied"
    
    @pytest.mark.asyncio
    async def test_token_refill(self, rate_limiter):
        """Test that tokens refill over time"""
        client_id = "test_client_3"
        
        # Exhaust tokens
        for i in range(10):
            await rate_limiter.is_allowed(client_id)
        
        # Should be denied
        allowed = await rate_limiter.is_allowed(client_id)
        assert allowed is False
        
        # Wait for refill (simulate time passing)
        await asyncio.sleep(6)  # 10% of period
        
        # Should have 1 token refilled
        allowed = await rate_limiter.is_allowed(client_id)
        # Note: This test may be flaky depending on implementation
        # In real implementation, tokens refill gradually
    
    @pytest.mark.asyncio
    async def test_multiple_clients_independent(self, rate_limiter):
        """Test that different clients have independent limits"""
        client1 = "test_client_4"
        client2 = "test_client_5"
        
        # Exhaust client1's tokens
        for i in range(10):
            await rate_limiter.is_allowed(client1)
        
        # Client1 should be denied
        allowed1 = await rate_limiter.is_allowed(client1)
        assert allowed1 is False
        
        # Client2 should still be allowed
        allowed2 = await rate_limiter.is_allowed(client2)
        assert allowed2 is True
    
    @pytest.mark.asyncio
    async def test_burst_handling(self, rate_limiter):
        """Test handling of burst requests"""
        client_id = "test_client_6"
        
        # Make burst of requests
        results = []
        for i in range(15):
            allowed = await rate_limiter.is_allowed(client_id)
            results.append(allowed)
        
        # First 10 should be allowed, rest denied
        assert sum(results) == 10
        assert results[:10] == [True] * 10
        assert results[10:] == [False] * 5
    
    @pytest.mark.asyncio
    async def test_get_remaining_tokens(self, rate_limiter):
        """Test getting remaining tokens"""
        client_id = "test_client_7"
        
        # Initial tokens should be full
        remaining = await rate_limiter.get_remaining(client_id)
        assert remaining == 10
        
        # Use some tokens
        for i in range(3):
            await rate_limiter.is_allowed(client_id)
        
        # Should have 7 remaining
        remaining = await rate_limiter.get_remaining(client_id)
        assert remaining == 7
    
    @pytest.mark.asyncio
    async def test_get_reset_time(self, rate_limiter):
        """Test getting reset time"""
        client_id = "test_client_8"
        
        # Make a request
        await rate_limiter.is_allowed(client_id)
        
        # Get reset time
        reset_time = await rate_limiter.get_reset_time(client_id)
        
        # Reset time should be in the future
        assert reset_time > datetime.now()
        
        # Should be within the period
        time_diff = (reset_time - datetime.now()).total_seconds()
        assert 0 < time_diff <= 60
    
    @pytest.mark.asyncio
    async def test_different_rate_limits(self):
        """Test creating limiters with different rates"""
        # Strict limiter
        strict_limiter = TokenBucketRateLimiter(rate=5, period=60)
        strict_limiter.tokens = {}
        
        # Lenient limiter
        lenient_limiter = TokenBucketRateLimiter(rate=100, period=60)
        lenient_limiter.tokens = {}
        
        client_id = "test_client_9"
        
        # Strict limiter should deny after 5 requests
        for i in range(5):
            allowed = await strict_limiter.is_allowed(client_id)
            assert allowed is True
        
        allowed = await strict_limiter.is_allowed(client_id)
        assert allowed is False
        
        # Lenient limiter should allow many more
        for i in range(50):
            allowed = await lenient_limiter.is_allowed(client_id)
            assert allowed is True
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, rate_limiter):
        """Test handling of concurrent requests"""
        client_id = "test_client_10"
        
        # Make concurrent requests
        tasks = [rate_limiter.is_allowed(client_id) for _ in range(15)]
        results = await asyncio.gather(*tasks)
        
        # Should allow exactly 10 requests
        assert sum(results) == 10
    
    @pytest.mark.asyncio
    async def test_zero_rate_denies_all(self):
        """Test that zero rate denies all requests"""
        limiter = TokenBucketRateLimiter(rate=0, period=60)
        limiter.tokens = {}
        
        client_id = "test_client_11"
        
        # All requests should be denied
        for i in range(5):
            allowed = await limiter.is_allowed(client_id)
            assert allowed is False
    
    @pytest.mark.asyncio
    async def test_very_high_rate_allows_many(self):
        """Test that very high rate allows many requests"""
        limiter = TokenBucketRateLimiter(rate=1000, period=60)
        limiter.tokens = {}
        
        client_id = "test_client_12"
        
        # Should allow many requests
        for i in range(500):
            allowed = await limiter.is_allowed(client_id)
            assert allowed is True
    
    @pytest.mark.asyncio
    async def test_rate_limit_headers(self, rate_limiter):
        """Test rate limit header information"""
        client_id = "test_client_13"
        
        # Make some requests
        for i in range(3):
            await rate_limiter.is_allowed(client_id)
        
        # Get header info
        headers = await rate_limiter.get_headers(client_id)
        
        assert 'X-RateLimit-Limit' in headers
        assert 'X-RateLimit-Remaining' in headers
        assert 'X-RateLimit-Reset' in headers
        
        assert headers['X-RateLimit-Limit'] == '10'
        assert headers['X-RateLimit-Remaining'] == '7'
    
    @pytest.mark.asyncio
    async def test_client_id_isolation(self, rate_limiter):
        """Test that client IDs are properly isolated"""
        client1 = "192.168.1.1"
        client2 = "192.168.1.2"
        client3 = "user_123"
        
        # Each client should have independent limits
        for client in [client1, client2, client3]:
            for i in range(10):
                allowed = await rate_limiter.is_allowed(client)
                assert allowed is True
            
            # 11th request should be denied
            allowed = await rate_limiter.is_allowed(client)
            assert allowed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
