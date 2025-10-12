"""
Structured logging configuration using loguru.

Provides consistent logging across all components with:
- JSON formatting for machine parsing
- Log rotation and retention
- Multiple log levels
- Contextual information
"""

import sys
from pathlib import Path
from loguru import logger
from config.settings import settings


def setup_logging():
    """
    Configure loguru logger with structured logging.
    
    Features:
    - Console output with colors
    - File output with rotation
    - JSON format for production
    - Contextual fields (component, symbol, etc.)
    """
    
    # Remove default handler
    logger.remove()
    
    # Console handler (human-readable)
    if settings.is_development():
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                   "<level>{message}</level>",
            level=settings.log_level,
            colorize=True,
            backtrace=True,
            diagnose=True
        )
    else:
        # Production: JSON format
        logger.add(
            sys.stdout,
            format="{message}",
            level=settings.log_level,
            serialize=True  # JSON output
        )
    
    # File handler with rotation
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        backtrace=True,
        diagnose=True
    )
    
    # Error log file (errors only)
    logger.add(
        log_dir / "error_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="ERROR",
        backtrace=True,
        diagnose=True
    )
    
    logger.info(f"Logging configured: level={settings.log_level}, format={settings.log_format}")


def get_logger(component: str):
    """
    Get a logger with component context.
    
    Args:
        component: Component name (e.g., 'binance_collector', 'bar_builder')
        
    Returns:
        Logger instance with component context
    """
    return logger.bind(component=component)


# Logging utilities
class LogContext:
    """Context manager for adding temporary context to logs."""
    
    def __init__(self, **kwargs):
        self.context = kwargs
        self.token = None
    
    def __enter__(self):
        self.token = logger.contextualize(**self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            logger.remove(self.token)


def log_trade(symbol: str, price: float, quantity: float, exchange: str):
    """Log trade event with structured data."""
    logger.bind(
        event_type="trade",
        symbol=symbol,
        price=price,
        quantity=quantity,
        exchange=exchange
    ).debug(f"Trade: {symbol} @ {price} x {quantity}")


def log_bar_completed(symbol: str, timeframe: str, bar_data: dict):
    """Log completed bar with structured data."""
    logger.bind(
        event_type="bar_completed",
        symbol=symbol,
        timeframe=timeframe,
        open=bar_data.get('open'),
        high=bar_data.get('high'),
        low=bar_data.get('low'),
        close=bar_data.get('close'),
        volume=bar_data.get('volume')
    ).info(f"Bar completed: {symbol} {timeframe}")


def log_indicator_calculated(symbol: str, indicators: dict):
    """Log indicator calculation with structured data."""
    logger.bind(
        event_type="indicator_calculated",
        symbol=symbol,
        **{k: v for k, v in indicators.items() if v is not None}
    ).debug(f"Indicators calculated: {symbol}")


def log_error(component: str, error: Exception, context: dict = None):
    """Log error with full context."""
    logger.bind(
        event_type="error",
        component=component,
        error_type=type(error).__name__,
        **(context or {})
    ).error(f"Error in {component}: {str(error)}")


def log_performance(operation: str, duration_ms: float, **kwargs):
    """Log performance metrics."""
    logger.bind(
        event_type="performance",
        operation=operation,
        duration_ms=duration_ms,
        **kwargs
    ).info(f"Performance: {operation} took {duration_ms:.2f}ms")


def log_health_check(component: str, status: str, details: dict = None):
    """Log health check result."""
    logger.bind(
        event_type="health_check",
        component=component,
        status=status,
        **(details or {})
    ).info(f"Health check: {component} is {status}")


# Initialize logging on import
setup_logging()
