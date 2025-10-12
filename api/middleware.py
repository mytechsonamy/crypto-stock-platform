"""
API Middleware.

Features:
- Rate limiting middleware
- Request logging
- Performance monitoring
"""

from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

from api.rate_limiter import TokenBucketRateLimiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware.
    
    Features:
    - Per-client rate limiting
    - Skip health checks
    - Use IP or user_id as identifier
    - Return 429 with Retry-After header
    """
    
    def __init__(
        self,
        app,
        rate_limiter: TokenBucketRateLimiter,
        skip_paths: list = None
    ):
        """
        Initialize rate limit middleware.
        
        Args:
            app: FastAPI application
            rate_limiter: Rate limiter instance
            skip_paths: Paths to skip rate limiting
        """
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.skip_paths = skip_paths or [
            "/health",
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/metrics",
            "/api/metrics"
        ]
        
        logger.info(
            f"RateLimitMiddleware initialized: "
            f"skip_paths={self.skip_paths}"
        )
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Process request with rate limiting.
        
        Args:
            request: HTTP request
            call_next: Next middleware/endpoint
            
        Returns:
            HTTP response
        """
        # Skip rate limiting for certain paths
        if request.url.path in self.skip_paths:
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Check rate limit
        is_allowed, retry_after = await self.rate_limiter.is_allowed(client_id)
        
        if not is_allowed:
            # Rate limit exceeded
            logger.warning(
                f"Rate limit exceeded: {client_id} on {request.url.path}",
                extra={
                    'client_id': client_id,
                    'path': request.url.path,
                    'method': request.method,
                    'retry_after': retry_after
                }
            )
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Too Many Requests",
                    "message": "Rate limit exceeded. Please try again later.",
                    "retry_after": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        rate_status = await self.rate_limiter.get_status(client_id)
        if rate_status.get('available', True):
            response.headers["X-RateLimit-Limit"] = str(self.rate_limiter.rate)
            response.headers["X-RateLimit-Remaining"] = str(int(rate_status.get('tokens', 0)))
            response.headers["X-RateLimit-Reset"] = str(int(rate_status.get('last_refill', 0) + self.rate_limiter.period))
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """
        Get client identifier from request.
        
        Priority:
        1. Authenticated user_id (from token)
        2. Client IP address
        
        Args:
            request: HTTP request
            
        Returns:
            Client identifier
        """
        # Try to get user_id from auth token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                # Extract user_id from token (simplified)
                # In production, decode JWT properly
                token = auth_header.split(" ")[1]
                # For now, use token hash as identifier
                import hashlib
                user_hash = hashlib.md5(token.encode()).hexdigest()[:8]
                return f"user:{user_hash}"
            except:
                pass
        
        # Fallback to IP address
        # Check for forwarded IP (behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        return f"ip:{client_ip}"
