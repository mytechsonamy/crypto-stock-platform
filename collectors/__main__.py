"""
Collector Entry Point.

This module serves as the entry point when running collectors via `python -m collectors`.
It determines which collector to start based on the COLLECTOR_TYPE environment variable.
"""

import asyncio
import os
import sys
import yaml
from pathlib import Path
from loguru import logger

from storage.timescale_manager import TimescaleManager
from storage.redis_cache import RedisCacheManager
from storage.symbol_manager import SymbolManager
from config.settings import Settings


async def main():
    """Main entry point for collectors."""

    # Get collector type from environment
    collector_type = os.getenv('COLLECTOR_TYPE', '').lower()

    if not collector_type:
        logger.error("COLLECTOR_TYPE environment variable not set")
        sys.exit(1)

    logger.info(f"Starting {collector_type} collector...")

    # Load settings
    settings = Settings()

    # Load exchange configuration
    config_path = Path(__file__).parent.parent / "config" / "exchanges.yaml"
    with open(config_path) as f:
        exchanges_config = yaml.safe_load(f)

    if collector_type not in exchanges_config:
        logger.error(f"Unknown collector type: {collector_type}")
        logger.error(f"Available collectors: {', '.join(exchanges_config.keys())}")
        sys.exit(1)

    config = exchanges_config[collector_type]

    # Check if collector is enabled
    if not config.get('enabled', True):
        logger.warning(f"{collector_type} collector is disabled in configuration")
        sys.exit(0)

    # Initialize database manager
    logger.info("Connecting to TimescaleDB...")
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
    logger.success("Connected to TimescaleDB")

    # Initialize Redis manager
    logger.info("Connecting to Redis...")
    redis_manager = RedisCacheManager(
        host=settings.redis.host,
        port=settings.redis.port,
        password=settings.redis.password,
        db=settings.redis.db,
        max_connections=settings.redis.max_connections
    )
    await redis_manager.connect()
    logger.success("Connected to Redis")

    # Initialize symbol manager
    symbol_manager = SymbolManager(db_manager.pool)

    # Import and instantiate the appropriate collector
    collector = None

    if collector_type == 'binance':
        from collectors.binance_collector import BinanceCollector

        # Add API credentials to config
        config['api_key'] = settings.binance_api_key
        config['api_secret'] = settings.binance_api_secret

        collector = BinanceCollector(config, redis_manager, symbol_manager)

    elif collector_type == 'yahoo':
        from collectors.yahoo_collector import YahooCollector

        collector = YahooCollector(config, redis_manager, symbol_manager)

    elif collector_type == 'polygon':
        from collectors.polygon_collector import PolygonCollector

        # Add API key to config from environment
        polygon_api_key = os.getenv('POLYGON_API_KEY', '')
        if polygon_api_key and polygon_api_key != 'your_polygon_api_key':
            config['api_key'] = polygon_api_key
        else:
            logger.error("POLYGON_API_KEY not set or invalid. Get a free API key from https://polygon.io")
            sys.exit(1)

        collector = PolygonCollector(config, redis_manager, symbol_manager)

    else:
        logger.error(f"Collector implementation not found for: {collector_type}")
        sys.exit(1)

    # Start the collector
    try:
        logger.info(f"Starting {collector_type} collector...")
        await collector.start()

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")

    except Exception as e:
        logger.error(f"Collector error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Cleanup
        logger.info("Shutting down...")
        try:
            await collector.stop()
        except:
            pass

        try:
            await redis_manager.disconnect()
        except:
            pass

        try:
            await db_manager.disconnect()
        except:
            pass

        logger.info("Collector stopped")


if __name__ == "__main__":
    # Configure logger
    logger.remove()  # Remove default handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=os.getenv("LOG_LEVEL", "INFO")
    )

    # Run the collector
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Collector stopped by user")
