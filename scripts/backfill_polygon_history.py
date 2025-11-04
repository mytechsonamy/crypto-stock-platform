#!/usr/bin/env python3
"""
Historical Data Backfill Script for Polygon.io

Downloads historical OHLC data for stock symbols from Polygon.io.
Free tier provides 2 years of daily data with 5 requests/minute limit.

Usage:
    python scripts/backfill_polygon_history.py --days 730 --symbol AAPL
    python scripts/backfill_polygon_history.py --days 365 --all
"""

import asyncio
import argparse
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict
import aiohttp
from loguru import logger

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.timescale_manager import TimescaleManager
from storage.symbol_manager import SymbolManager


class PolygonHistoricalBackfill:
    """Downloads historical data from Polygon.io."""

    def __init__(self, api_key: str, db_manager: TimescaleManager):
        """
        Initialize backfill tool.

        Args:
            api_key: Polygon.io API key
            db_manager: Database manager instance
        """
        self.api_key = api_key
        self.db_manager = db_manager
        self.base_url = "https://api.polygon.io"
        self.session: aiohttp.ClientSession = None
        self.request_count = 0
        self.request_window_start = datetime.now()
        self.requests_per_minute = 5  # Free tier limit

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def _check_rate_limit(self):
        """Enforce rate limiting."""
        now = datetime.now()
        elapsed = (now - self.request_window_start).total_seconds()

        # Reset window if 1 minute passed
        if elapsed >= 60:
            self.request_count = 0
            self.request_window_start = now
            return

        # Check if limit exceeded
        if self.request_count >= self.requests_per_minute:
            wait_time = 60 - elapsed
            logger.warning(f"Rate limit reached. Waiting {wait_time:.1f}s...")
            await asyncio.sleep(wait_time)
            self.request_count = 0
            self.request_window_start = datetime.now()

    async def fetch_historical_data(
        self,
        symbol: str,
        from_date: str,
        to_date: str,
        timespan: str = "day",
        multiplier: int = 1
    ) -> List[Dict]:
        """
        Fetch historical OHLC data from Polygon.io.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            timespan: Time window (minute, hour, day, week, month)
            multiplier: Size of timespan multiplier

        Returns:
            List of OHLC bars
        """
        await self._check_rate_limit()

        url = f"{self.base_url}/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
        params = {
            'apiKey': self.api_key,
            'adjusted': 'true',
            'sort': 'asc',
            'limit': 50000  # Max allowed
        }

        try:
            async with self.session.get(url, params=params, timeout=30) as response:
                self.request_count += 1

                if response.status == 200:
                    data = await response.json()

                    if data.get('status') == 'OK' and data.get('results'):
                        results = data['results']
                        logger.info(
                            f"Fetched {len(results)} bars for {symbol} "
                            f"({from_date} to {to_date})"
                        )
                        return results
                    else:
                        logger.warning(f"No data for {symbol}: {data.get('status')}")
                        return []

                elif response.status == 429:
                    logger.error("Rate limit exceeded!")
                    return []

                elif response.status == 403:
                    error_data = await response.json()
                    logger.error(f"Access forbidden: {error_data.get('error', 'Unknown')}")
                    return []

                else:
                    logger.error(f"HTTP {response.status} for {symbol}")
                    return []

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return []

    async def save_bars_to_db(self, symbol: str, bars: List[Dict], timeframe: str):
        """
        Save bars to database.

        Args:
            symbol: Stock symbol
            bars: List of OHLC bars
            timeframe: Timeframe (1d, 1h, etc.)
        """
        if not bars:
            return

        saved_count = 0
        for bar in bars:
            try:
                bar_time = datetime.fromtimestamp(bar['t'] / 1000)

                await self.db_manager.insert_candle(
                    time=bar_time,
                    symbol=symbol,
                    exchange='polygon',
                    timeframe=timeframe,
                    open_price=float(bar['o']),
                    high=float(bar['h']),
                    low=float(bar['l']),
                    close=float(bar['c']),
                    volume=float(bar['v'])
                )
                saved_count += 1

            except Exception as e:
                logger.error(f"Error saving bar for {symbol}: {e}")

        logger.success(f"Saved {saved_count}/{len(bars)} bars for {symbol}")

    async def backfill_symbol(
        self,
        symbol: str,
        days_back: int = 730,
        timespan: str = "day"
    ):
        """
        Backfill historical data for a symbol.

        Args:
            symbol: Stock symbol
            days_back: Number of days to go back (default: 730 = 2 years)
            timespan: Timespan for data (day, hour, minute)
        """
        logger.info(f"Starting backfill for {symbol} ({days_back} days)")

        # Calculate date range
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days_back)

        from_str = from_date.strftime('%Y-%m-%d')
        to_str = to_date.strftime('%Y-%m-%d')

        # Fetch data
        bars = await self.fetch_historical_data(
            symbol=symbol,
            from_date=from_str,
            to_date=to_str,
            timespan=timespan
        )

        # Save to database
        if bars:
            timeframe_map = {
                'minute': '1m',
                'hour': '1h',
                'day': '1d',
                'week': '1w',
                'month': '1M'
            }
            timeframe = timeframe_map.get(timespan, '1d')
            await self.save_bars_to_db(symbol, bars, timeframe)

    async def backfill_all_symbols(self, days_back: int = 730):
        """
        Backfill all active Polygon symbols.

        Args:
            days_back: Number of days to backfill
        """
        symbol_manager = SymbolManager(self.db_manager.pool)
        symbols = await symbol_manager.get_symbols_by_exchange('polygon')

        logger.info(f"Starting backfill for {len(symbols)} symbols")

        for i, symbol in enumerate(symbols, 1):
            logger.info(f"[{i}/{len(symbols)}] Processing {symbol}")
            await self.backfill_symbol(symbol, days_back)

        logger.success(f"Backfill complete for {len(symbols)} symbols")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Backfill historical data from Polygon.io'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=730,
        help='Number of days to backfill (default: 730 = 2 years, max: 730 for free tier)'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        help='Specific symbol to backfill (e.g., AAPL)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Backfill all active symbols'
    )
    parser.add_argument(
        '--timespan',
        type=str,
        default='day',
        choices=['minute', 'hour', 'day', 'week', 'month'],
        help='Timespan for historical data (default: day)'
    )

    args = parser.parse_args()

    # Validate args
    if not args.symbol and not args.all:
        parser.error("Must specify either --symbol or --all")

    # Get API key
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key or api_key == 'your_polygon_api_key':
        logger.error("POLYGON_API_KEY not set in environment")
        sys.exit(1)

    # Free tier limit
    if args.days > 730:
        logger.warning("Free tier limited to 2 years (730 days). Adjusting...")
        args.days = 730

    logger.info(f"Backfilling {args.days} days of {args.timespan} data")

    # Initialize database
    db_manager = TimescaleManager(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 5432)),
        database=os.getenv('DB_NAME', 'crypto_stock'),
        user=os.getenv('DB_USER', 'admin'),
        password=os.getenv('DB_PASSWORD', 'password')
    )

    try:
        await db_manager.connect()
        logger.success("Connected to database")

        async with PolygonHistoricalBackfill(api_key, db_manager) as backfill:
            if args.symbol:
                await backfill.backfill_symbol(
                    args.symbol,
                    args.days,
                    args.timespan
                )
            elif args.all:
                await backfill.backfill_all_symbols(args.days)

    except KeyboardInterrupt:
        logger.info("Backfill cancelled by user")
    except Exception as e:
        logger.error(f"Backfill error: {e}", exc_info=True)
    finally:
        await db_manager.disconnect()
        logger.info("Backfill complete")


if __name__ == "__main__":
    # Configure logger
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )

    asyncio.run(main())
