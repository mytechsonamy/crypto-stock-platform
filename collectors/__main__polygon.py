"""
Polygon.io Collector Entry Point.

Starts the Polygon.io stock data collector service.
"""

import asyncio
import os
import signal
import sys
from loguru import logger

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.polygon_collector import PolygonCollector
from config.config_manager import ConfigManager
from storage.redis_cache import RedisCacheManager
from storage.timescale_manager import TimescaleManager
from storage.symbol_manager import SymbolManager


# Global collector instance for signal handling
collector_instance = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    if collector_instance:
        asyncio.create_task(collector_instance.stop())


async def main():
    """Main entry point for Polygon.io collector."""
    global collector_instance

    logger.info("=" * 60)
    logger.info("Polygon.io Stock Data Collector")
    logger.info("=" * 60)

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.get_exchange_config('polygon')

    if not config:
        logger.error("Polygon.io configuration not found in exchanges.yaml")
        return

    if not config.get('enabled', False):
        logger.warning("Polygon.io collector is disabled in configuration")
        return

    # Get API key from environment
    api_key = os.getenv('POLYGON_API_KEY', '')
    if api_key and api_key != 'your_polygon_api_key':
        config['api_key'] = api_key
        logger.info("Polygon.io API key loaded from environment")
    else:
        logger.error(
            "POLYGON_API_KEY not set in environment. "
            "Please get a free API key from https://polygon.io and set it in .env file"
        )
        return

    # Initialize database connection
    logger.info("Connecting to TimescaleDB...")
    db_manager = TimescaleManager(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 5432)),
        database=os.getenv('DB_NAME', 'crypto_stock'),
        user=os.getenv('DB_USER', 'admin'),
        password=os.getenv('DB_PASSWORD', 'password')
    )

    try:
        await db_manager.connect()
        logger.success("Connected to TimescaleDB")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return

    # Initialize Redis connection
    logger.info("Connecting to Redis...")
    redis_client = RedisCacheManager(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=0
    )

    try:
        await redis_client.connect()
        logger.success("Connected to Redis")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        await db_manager.disconnect()
        return

    # Initialize symbol manager
    symbol_manager = SymbolManager(db_manager)

    # Create and start collector
    try:
        collector_instance = PolygonCollector(
            config=config,
            redis_client=redis_client,
            symbol_manager=symbol_manager
        )

        logger.info("Starting polygon collector...")
        await collector_instance.start()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Collector error: {e}", exc_info=True)
    finally:
        # Cleanup
        if collector_instance:
            await collector_instance.stop()

        await redis_client.disconnect()
        await db_manager.disconnect()

        logger.info("Polygon.io collector stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
