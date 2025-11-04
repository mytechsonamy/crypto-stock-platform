"""
Data Processor Entry Point.

This module coordinates the bar builder, indicator calculator, and data quality checker.
Subscribes to Redis channels and processes incoming market data.
"""

import asyncio
import json
import os
import sys
from loguru import logger

from storage.timescale_manager import TimescaleManager
from storage.redis_cache import RedisCacheManager
from processors.bar_builder import BarBuilder
from processors.indicators import IndicatorCalculator
from processors.data_quality import DataQualityChecker
from config.settings import Settings
from config.config_manager import config_manager


async def main():
    """Main entry point for data processor."""

    logger.info("Starting data processor...")

    # Load settings
    settings = Settings()

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

    # Initialize processors
    logger.info("Initializing data processors...")

    # Configuration for processors
    processor_config = {
        'batch_size': int(os.getenv('PROCESSOR_BATCH_SIZE', '100')),
        'flush_interval': int(os.getenv('PROCESSOR_FLUSH_INTERVAL', '5')),
        'enable_ml_features': os.getenv('ENABLE_ML_FEATURES', 'false').lower() == 'true',
        'timeframes': ['1m', '5m', '15m', '1h', '4h', '1d']
    }

    # Data quality checker
    enable_data_quality = os.getenv('ENABLE_DATA_QUALITY_CHECKS', 'true').lower() == 'true'
    data_quality_checker = None
    if enable_data_quality:
        # Load data quality configuration from exchanges.yaml
        data_quality_config = config_manager.get('data_quality', filename='exchanges.yaml', default={})
        data_quality_checker = DataQualityChecker(
            config=data_quality_config,
            db_manager=db_manager,
            enable_quarantine=True
        )
        logger.info("Data quality checks enabled")

    # Bar builder
    bar_builder = BarBuilder(
        config=processor_config,
        db_manager=db_manager,
        redis_manager=redis_manager,
        quality_checker=data_quality_checker
    )

    # Indicator calculator
    indicator_calculator = IndicatorCalculator(
        config=processor_config,
        db_manager=db_manager,
        redis_manager=redis_manager,
        alert_manager=None  # Can be added later if needed
    )

    logger.success("Processors initialized")

    # Start processors
    try:
        logger.info("Starting bar builder and indicator calculator...")
        logger.info("Subscribing to Redis channels...")

        # Subscribe to trade channel for bar building
        pubsub = redis_manager.client.pubsub()
        await pubsub.subscribe('trades')

        # Subscribe to completed bars channel for indicator calculation
        await pubsub.subscribe('bars:completed')

        logger.success("Subscribed to Redis channels")
        logger.info("Processing market data...")

        # Main processing loop
        async for message in pubsub.listen():
            try:
                if message['type'] != 'message':
                    continue

                # Handle both bytes and strings from Redis
                channel = message['channel']
                if isinstance(channel, bytes):
                    channel = channel.decode('utf-8')

                if channel == 'trades':
                    # Process trade tick for bar building
                    trade_data = json.loads(message['data'])
                    await bar_builder.process_trade(trade_data)

                elif channel == 'bars:completed':
                    # Process completed bar
                    bar_data = json.loads(message['data'])

                    # Save completed bar to database
                    # Convert timestamp from milliseconds to datetime
                    from datetime import datetime
                    bar_time = datetime.fromtimestamp(bar_data['time'] / 1000)

                    await db_manager.insert_candle(
                        time=bar_time,
                        symbol=bar_data['symbol'],
                        exchange=bar_data['exchange'],
                        timeframe=bar_data['timeframe'],
                        open_price=bar_data['open'],
                        high=bar_data['high'],
                        low=bar_data['low'],
                        close=bar_data['close'],
                        volume=bar_data['volume']
                    )

                    # Calculate indicators
                    await indicator_calculator.process_completed_bar(
                        symbol=bar_data['symbol'],
                        timeframe=bar_data['timeframe'],
                        completed_bar=bar_data
                    )

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")

    except Exception as e:
        logger.error(f"Processor error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Cleanup
        logger.info("Shutting down processors...")

        try:
            await pubsub.unsubscribe()
            await pubsub.close()
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

        logger.info("Processors stopped")


if __name__ == "__main__":
    # Configure logger
    logger.remove()  # Remove default handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=os.getenv("LOG_LEVEL", "INFO")
    )

    # Run the processor
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Processor stopped by user")
