"""
FastAPI Application Main Entry Point.

Features:
- CORS middleware
- Dependency injection
- Startup/shutdown handlers
- Global error handling
- OpenAPI/Swagger documentation
- Prometheus metrics
"""

from contextlib import asynccontextmanager
from typing import Dict, Optional
import asyncio
import json
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from loguru import logger
from prometheus_client import make_asgi_app
from prometheus_fastapi_instrumentator import Instrumentator

from storage.timescale_manager import TimescaleManager
from storage.redis_cache import RedisCacheManager
from storage.symbol_manager import SymbolManager


# Global managers (will be initialized in lifespan)
db_manager: Optional[TimescaleManager] = None
redis_manager: Optional[RedisCacheManager] = None
symbol_manager: Optional[SymbolManager] = None
alert_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting up FastAPI application...")
    
    global db_manager, redis_manager, symbol_manager, rate_limiter, alert_manager
    
    try:
        # Load settings
        from config.settings import Settings
        settings = Settings()
        
        # Initialize database manager
        logger.info("Initializing database connection...")
        db_manager = TimescaleManager(
            host=settings.database.host,
            port=settings.database.port,
            database=settings.database.database,
            user=settings.database.user,
            password=settings.database.password,
            min_size=settings.database.min_pool_size,
            max_size=settings.database.max_pool_size
        )
        await db_manager.connect()
        logger.success("Database connected")
        
        # Initialize Redis manager
        logger.info("Initializing Redis connection...")
        redis_manager = RedisCacheManager(
            host=settings.redis.host,
            port=settings.redis.port,
            password=settings.redis.password,
            db=settings.redis.db,
            max_connections=50
        )
        await redis_manager.connect()
        logger.success("Redis connected")
        
        # Initialize symbol manager
        logger.info("Initializing symbol manager...")
        symbol_manager = SymbolManager(db_manager.pool)
        logger.success("Symbol manager initialized")
        
        # Initialize alert manager
        logger.info("Initializing alert manager...")
        from api.alert_manager import AlertManager
        alert_manager = AlertManager(
            db_manager=db_manager,
            redis_manager=redis_manager,
            smtp_config=None,  # TODO: Configure SMTP
            slack_webhook_url=None  # TODO: Configure Slack
        )
        app.state.alert_manager = alert_manager
        logger.success("Alert manager initialized")
        
        # Initialize rate limiter
        logger.info("Initializing rate limiter...")
        from api.rate_limiter import TokenBucketRateLimiter
        from api.middleware import RateLimitMiddleware
        
        rate_limiter = TokenBucketRateLimiter(
            redis_manager=redis_manager,
            rate=100,  # 100 requests
            period=60  # per 60 seconds
        )

        # Store rate limiter in app state for use in endpoints
        app.state.rate_limiter = rate_limiter
        logger.success("Rate limiter initialized")
        
        # Start WebSocket background tasks
        logger.info("Starting WebSocket background tasks...")
        from api.websocket import connection_manager, start_redis_listener

        # Start batch flusher
        asyncio.create_task(connection_manager.start_batch_flusher())

        # Start Redis listener for real-time updates
        asyncio.create_task(start_redis_listener(redis_manager))

        logger.success("WebSocket background tasks started")
        
        logger.success("FastAPI application started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI application...")
    
    try:
        if redis_manager:
            await redis_manager.disconnect()
            logger.info("Redis disconnected")
        
        if db_manager:
            await db_manager.disconnect()
            logger.info("Database disconnected")
        
        logger.success("FastAPI application shut down successfully")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title="Crypto-Stock Platform API",
    description="""
    Real-time cryptocurrency and stock market data platform.
    
    ## Features
    
    * **Real-time Data Collection**: Binance (crypto), Alpaca (US stocks), Yahoo Finance (BIST stocks)
    * **Technical Indicators**: RSI, MACD, Bollinger Bands, SMA, EMA, and more
    * **ML Features**: 60+ engineered features for machine learning
    * **Data Quality**: Automated validation and quality scoring
    * **WebSocket**: Real-time chart updates
    * **REST API**: Historical data and analytics
    
    ## Data Sources
    
    * **Binance**: Real-time cryptocurrency data (WebSocket)
    * **Alpaca**: US stock market data (WebSocket, IEX feed)
    * **Yahoo Finance**: BIST stock data (5-minute polling)
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React frontend
        "http://localhost:3001",  # Alternative frontend port
        "http://localhost:3002",  # Development frontend port
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware (will be initialized in lifespan)
rate_limiter = None

# Add Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Instrument FastAPI with Prometheus
Instrumentator().instrument(app).expose(app, endpoint="/api/metrics")


# ==================== DEPENDENCY INJECTION ====================

def get_db_manager() -> TimescaleManager:
    """Get database manager dependency."""
    if db_manager is None:
        raise RuntimeError("Database manager not initialized")
    return db_manager


def get_redis_manager() -> RedisCacheManager:
    """Get Redis manager dependency."""
    if redis_manager is None:
        raise RuntimeError("Redis manager not initialized")
    return redis_manager


def get_symbol_manager() -> SymbolManager:
    """Get symbol manager dependency."""
    if symbol_manager is None:
        raise RuntimeError("Symbol manager not initialized")
    return symbol_manager


# ==================== ERROR HANDLERS ====================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle validation errors.
    
    Returns 400 Bad Request with error details.
    """
    logger.warning(
        f"Validation error: {exc.errors()}",
        extra={'path': request.url.path, 'method': request.method}
    )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Validation Error",
            "message": "Invalid request parameters",
            "details": exc.errors()
        }
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """
    Handle value errors.
    
    Returns 400 Bad Request.
    """
    logger.warning(
        f"Value error: {str(exc)}",
        extra={'path': request.url.path, 'method': request.method}
    )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Bad Request",
            "message": str(exc)
        }
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """
    Handle 404 Not Found errors.
    """
    logger.warning(
        f"Not found: {request.url.path}",
        extra={'path': request.url.path, 'method': request.method}
    )
    
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "Not Found",
            "message": f"Resource not found: {request.url.path}"
        }
    )


@app.exception_handler(429)
async def rate_limit_handler(request: Request, exc):
    """
    Handle 429 Too Many Requests errors.
    """
    logger.warning(
        f"Rate limit exceeded: {request.client.host}",
        extra={'path': request.url.path, 'method': request.method, 'client': request.client.host}
    )
    
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "Too Many Requests",
            "message": "Rate limit exceeded. Please try again later.",
            "retry_after": 60
        },
        headers={"Retry-After": "60"}
    )


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    """
    Handle 500 Internal Server Error.
    """
    logger.error(
        f"Internal server error: {str(exc)}",
        extra={'path': request.url.path, 'method': request.method},
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later."
        }
    )


@app.exception_handler(503)
async def service_unavailable_handler(request: Request, exc):
    """
    Handle 503 Service Unavailable errors.
    """
    logger.error(
        f"Service unavailable: {str(exc)}",
        extra={'path': request.url.path, 'method': request.method}
    )
    
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "Service Unavailable",
            "message": "Service is temporarily unavailable. Please try again later."
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for uncaught exceptions.
    """
    logger.error(
        f"Unhandled exception: {str(exc)}",
        extra={'path': request.url.path, 'method': request.method},
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later."
        }
    )


# ==================== HEALTH CHECK ENDPOINTS ====================

@app.get("/", tags=["Health"])
async def root():
    """
    Root endpoint.
    
    Returns basic API information.
    """
    return {
        "name": "Crypto-Stock Platform API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    
    Checks status of all components:
    - Database connection
    - Redis connection
    - Overall system health
    """
    health_status = {
        "status": "healthy",
        "components": {}
    }
    
    # Check database
    if db_manager:
        db_health = await db_manager.health_check()
        health_status["components"]["database"] = db_health
        if db_health.get("status") != "healthy":
            health_status["status"] = "degraded"
    else:
        health_status["components"]["database"] = {"status": "not_initialized"}
        health_status["status"] = "unhealthy"
    
    # Check Redis
    if redis_manager:
        redis_health = await redis_manager.health_check()
        health_status["components"]["redis"] = redis_health
        if redis_health.get("status") != "healthy":
            health_status["status"] = "degraded"
    else:
        health_status["components"]["redis"] = {"status": "not_initialized"}
        health_status["status"] = "unhealthy"
    
    # Set appropriate status code
    status_code = status.HTTP_200_OK
    if health_status["status"] == "degraded":
        status_code = status.HTTP_200_OK  # Still operational
    elif health_status["status"] == "unhealthy":
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return JSONResponse(
        status_code=status_code,
        content=health_status
    )


# ==================== API ROUTES ====================

# Import and include routers
from api.v1 import router as v1_router
app.include_router(v1_router, prefix="/api/v1")


# ==================== WEBSOCKET ENDPOINT ====================

from fastapi import WebSocket, WebSocketDisconnect, Query as WSQuery
from api.websocket import connection_manager
from api.auth import auth_manager


@app.websocket("/ws/{symbol}")
async def websocket_endpoint(
    websocket: WebSocket,
    symbol: str,
    token: str = WSQuery(None)
):
    """
    WebSocket endpoint for real-time chart updates.
    
    Args:
        websocket: WebSocket connection
        symbol: Trading symbol
        token: JWT authentication token
        
    Features:
    - JWT authentication
    - Initial chart data on connect
    - Real-time updates from Redis
    - Throttling and batching
    - Automatic reconnection support
    """
    try:
        # Authenticate
        user = await auth_manager.authenticate_websocket(token)
        
        # Connect
        await connection_manager.connect(
            websocket,
            symbol,
            {'user_id': user.user_id, 'username': user.username}
        )
        
        # Send initial chart data
        try:
            # Get recent bars
            bars = await db_manager.get_recent_candles(symbol, '1m', 100)
            
            # Get indicators
            indicators = await redis_manager.get_cached_indicators(symbol, '1m')
            
            initial_data = {
                'type': 'initial',
                'symbol': symbol,
                'bars': bars,
                'indicators': indicators
            }
            
            await connection_manager.send_personal_message(
                json.dumps(initial_data, default=str),
                websocket
            )
            
        except Exception as e:
            logger.error(f"Error sending initial data: {e}")
        
        # Keep connection alive and handle messages
        while True:
            try:
                # Receive messages (ping/pong, commands, etc.)
                data = await websocket.receive_text()
                
                # Handle client messages
                try:
                    message = json.loads(data)
                    message_type = message.get('type')
                    
                    if message_type == 'ping':
                        await websocket.send_text(json.dumps({'type': 'pong'}))
                    elif message_type == 'subscribe':
                        # Handle subscription changes
                        pass
                    
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from client: {data}")
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}")
                break
        
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass
    
    finally:
        # Disconnect
        await connection_manager.disconnect(websocket, symbol)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
