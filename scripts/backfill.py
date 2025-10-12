#!/usr/bin/env python3
"""
Historical Data Backfill Script
Fetches historical data from exchanges and stores in database
"""

import os
import sys
import asyncio
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import json
from loguru import logger
from tqdm import tqdm
import signal

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.timescale_manager import TimescaleManager
from storage.redis_cache import RedisCacheManager
from collectors.circuit_breaker import CircuitBreaker
from processors.indicators import IndicatorCalculator


class BackfillManager:
    """Manages historical data backfill operations"""
    
    def __init__(
        self,
        exchange: str,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str,
        db_manager: TimescaleManager,
        redis_manager: RedisCacheManager,
        checkpoint_file: Optional[Path] = None
    ):
        self.exchange = exchange
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.timeframe = timeframe
        self.db = db_manager
        self.redis = redis_manager
        self.checkpoint_file = checkpoint_file or Path(f"checkpoints/backfill_{exchange}_{symbol}_{timeframe}.json")
        
        # Circuit breaker for rate limiting
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2
        )
        
        # Progress tracking
        self.total_bars = 0
        self.fetched_bars = 0
        self.stored_bars = 0
        self.last_timestamp = None
        self.interrupted = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle interrupt signals"""
        logger.warning("Interrupt received, saving checkpoint...")
        self.interrupted = True
        self.save_checkpoint()
    
    def load_checkpoint(self) -> Optional[datetime]:
        """Load checkpoint from file"""
        if not self.checkpoint_file.exists():
            return None
        
        try:
            with open(self.checkpoint_file, 'r') as f:
                data = json.load(f)
            
            last_timestamp = datetime.fromisoformat(data['last_timestamp'])
            self.fetched_bars = data.get('fetched_bars', 0)
            self.stored_bars = data.get('stored_bars', 0)
            
            logger.info(f"Loaded checkpoint: {last_timestamp}")
            logger.info(f"Progress: {self.fetched_bars} bars fetched, {self.stored_bars} bars stored")
            
            return last_timestamp
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def save_checkpoint(self):
        """Save checkpoint to file"""
        if not self.last_timestamp:
            return
        
        try:
            self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'exchange': self.exchange,
                'symbol': self.symbol,
                'timeframe': self.timeframe,
                'last_timestamp': self.last_timestamp.isoformat(),
                'fetched_bars': self.fetched_bars,
                'stored_bars': self.stored_bars,
                'updated_at': datetime.now().isoformat()
            }
            
            with open(self.checkpoint_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Checkpoint saved: {self.last_timestamp}")
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    async def fetch_binance_data(self, start_ms: int, end_ms: int, limit: int = 1000) -> List[Dict]:
        """Fetch data from Binance"""
        from binance.client import Client
        
        try:
            client = Client(
                api_key=os.getenv('BINANCE_API_KEY'),
                api_secret=os.getenv('BINANCE_API_SECRET')
            )
            
            # Map timeframe
            interval_map = {
                '1m': Client.KLINE_INTERVAL_1MINUTE,
                '5m': Client.KLINE_INTERVAL_5MINUTE,
                '15m': Client.KLINE_INTERVAL_15MINUTE,
                '1h': Client.KLINE_INTERVAL_1HOUR,
                '4h': Client.KLINE_INTERVAL_4HOUR,
                '1d': Client.KLINE_INTERVAL_1DAY,
            }
            
            interval = interval_map.get(self.timeframe, Client.KLINE_INTERVAL_1MINUTE)
            
            # Fetch klines
            klines = client.get_historical_klines(
                symbol=self.symbol,
                interval=interval,
                start_str=start_ms,
                end_str=end_ms,
                limit=limit
            )
            
            # Convert to standard format
            bars = []
            for k in klines:
                bars.append({
                    'time': datetime.fromtimestamp(k[0] / 1000),
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5]),
                    'symbol': self.symbol,
                    'exchange': 'binance',
                    'timeframe': self.timeframe,
                    'trade_count': k[8]
                })
            
            return bars
            
        except Exception as e:
            logger.error(f"Binance fetch error: {e}")
            raise
    
    async def fetch_alpaca_data(self, start: datetime, end: datetime) -> List[Dict]:
        """Fetch data from Alpaca"""
        import alpaca_trade_api as tradeapi
        
        try:
            api = tradeapi.REST(
                key_id=os.getenv('ALPACA_API_KEY'),
                secret_key=os.getenv('ALPACA_SECRET_KEY'),
                base_url='https://paper-api.alpaca.markets'
            )
            
            # Map timeframe
            timeframe_map = {
                '1m': '1Min',
                '5m': '5Min',
                '15m': '15Min',
                '1h': '1Hour',
                '4h': '4Hour',
                '1d': '1Day',
            }
            
            tf = timeframe_map.get(self.timeframe, '1Min')
            
            # Fetch bars
            barset = api.get_bars(
                self.symbol,
                tf,
                start=start.isoformat(),
                end=end.isoformat(),
                limit=10000
            )
            
            # Convert to standard format
            bars = []
            for bar in barset:
                bars.append({
                    'time': bar.t,
                    'open': float(bar.o),
                    'high': float(bar.h),
                    'low': float(bar.l),
                    'close': float(bar.c),
                    'volume': float(bar.v),
                    'symbol': self.symbol,
                    'exchange': 'alpaca',
                    'timeframe': self.timeframe,
                    'trade_count': bar.n if hasattr(bar, 'n') else 0
                })
            
            return bars
            
        except Exception as e:
            logger.error(f"Alpaca fetch error: {e}")
            raise
    
    async def fetch_yahoo_data(self, start: datetime, end: datetime) -> List[Dict]:
        """Fetch data from Yahoo Finance"""
        import yfinance as yf
        
        try:
            ticker = yf.Ticker(self.symbol)
            
            # Map timeframe
            interval_map = {
                '1m': '1m',
                '5m': '5m',
                '15m': '15m',
                '1h': '1h',
                '1d': '1d',
            }
            
            interval = interval_map.get(self.timeframe, '1d')
            
            # Fetch data
            df = ticker.history(
                start=start,
                end=end,
                interval=interval
            )
            
            # Convert to standard format
            bars = []
            for index, row in df.iterrows():
                bars.append({
                    'time': index.to_pydatetime(),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': float(row['Volume']),
                    'symbol': self.symbol,
                    'exchange': 'yahoo',
                    'timeframe': self.timeframe,
                    'trade_count': 0
                })
            
            return bars
            
        except Exception as e:
            logger.error(f"Yahoo fetch error: {e}")
            raise
    
    async def fetch_data(self, start: datetime, end: datetime) -> List[Dict]:
        """Fetch data from appropriate exchange"""
        
        async def fetch_with_circuit_breaker():
            if self.exchange == 'binance':
                start_ms = int(start.timestamp() * 1000)
                end_ms = int(end.timestamp() * 1000)
                return await self.fetch_binance_data(start_ms, end_ms)
            elif self.exchange == 'alpaca':
                return await self.fetch_alpaca_data(start, end)
            elif self.exchange == 'yahoo':
                return await self.fetch_yahoo_data(start, end)
            else:
                raise ValueError(f"Unknown exchange: {self.exchange}")
        
        # Use circuit breaker
        return await self.circuit_breaker.call(fetch_with_circuit_breaker)
    
    async def calculate_indicators(self, bars: List[Dict]) -> List[Dict]:
        """Calculate indicators for bars"""
        if not bars:
            return []
        
        # Create indicator calculator
        config = {
            'rsi': {'period': 14},
            'macd': {'fast': 12, 'slow': 26, 'signal': 9},
            'bollinger_bands': {'period': 20, 'std_dev': 2},
            'sma': {'periods': [20, 50, 100, 200]},
            'ema': {'periods': [12, 26, 50]},
        }
        
        calculator = IndicatorCalculator(config, self.db, self.redis)
        
        # Calculate indicators
        # Note: This is simplified - actual implementation would use the full calculator
        return bars
    
    async def store_bars(self, bars: List[Dict]):
        """Store bars in database"""
        if not bars:
            return
        
        # Batch insert
        await self.db.batch_insert_candles(bars)
        self.stored_bars += len(bars)
        
        logger.debug(f"Stored {len(bars)} bars")
    
    async def run(self):
        """Run backfill process"""
        logger.info("=" * 80)
        logger.info("HISTORICAL DATA BACKFILL")
        logger.info("=" * 80)
        logger.info(f"Exchange: {self.exchange}")
        logger.info(f"Symbol: {self.symbol}")
        logger.info(f"Timeframe: {self.timeframe}")
        logger.info(f"Start: {self.start_date}")
        logger.info(f"End: {self.end_date}")
        logger.info("=" * 80)
        
        # Load checkpoint
        checkpoint = self.load_checkpoint()
        current_start = checkpoint if checkpoint else self.start_date
        
        if checkpoint:
            logger.info(f"Resuming from checkpoint: {checkpoint}")
        
        # Calculate total bars estimate
        delta = self.end_date - current_start
        timeframe_minutes = {
            '1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440
        }
        minutes = timeframe_minutes.get(self.timeframe, 1)
        self.total_bars = int(delta.total_seconds() / 60 / minutes)
        
        logger.info(f"Estimated bars to fetch: {self.total_bars:,}")
        
        # Progress bar
        pbar = tqdm(total=self.total_bars, desc="Fetching", unit="bars")
        pbar.update(self.fetched_bars)
        
        # Fetch in chunks
        chunk_size = 1000
        current = current_start
        
        while current < self.end_date and not self.interrupted:
            # Calculate chunk end
            chunk_end = min(
                current + timedelta(minutes=chunk_size * minutes),
                self.end_date
            )
            
            try:
                # Fetch data
                bars = await self.fetch_data(current, chunk_end)
                
                if bars:
                    self.fetched_bars += len(bars)
                    self.last_timestamp = bars[-1]['time']
                    
                    # Calculate indicators
                    bars_with_indicators = await self.calculate_indicators(bars)
                    
                    # Store in database
                    await self.store_bars(bars_with_indicators)
                    
                    # Update progress
                    pbar.update(len(bars))
                    
                    # Save checkpoint periodically
                    if self.fetched_bars % 10000 == 0:
                        self.save_checkpoint()
                
                # Move to next chunk
                current = chunk_end
                
                # Rate limiting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error fetching chunk: {e}")
                await asyncio.sleep(5)  # Wait before retry
        
        pbar.close()
        
        # Final checkpoint
        self.save_checkpoint()
        
        # Update Redis cache
        logger.info("Updating Redis cache...")
        # TODO: Implement cache update
        
        logger.success("=" * 80)
        logger.success("BACKFILL COMPLETED")
        logger.success(f"Fetched: {self.fetched_bars:,} bars")
        logger.success(f"Stored: {self.stored_bars:,} bars")
        logger.success("=" * 80)


async def main():
    parser = argparse.ArgumentParser(description="Historical data backfill")
    parser.add_argument('--exchange', type=str, required=True, choices=['binance', 'alpaca', 'yahoo'])
    parser.add_argument('--symbol', type=str, required=True)
    parser.add_argument('--start-date', type=str, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--timeframe', type=str, default='1d', choices=['1m', '5m', '15m', '1h', '4h', '1d'])
    parser.add_argument('--db-host', type=str, default='localhost')
    parser.add_argument('--db-port', type=int, default=5432)
    parser.add_argument('--db-name', type=str, default='crypto_stock')
    parser.add_argument('--db-user', type=str, default='admin')
    parser.add_argument('--db-password', type=str)
    parser.add_argument('--redis-host', type=str, default='localhost')
    parser.add_argument('--redis-port', type=int, default=6379)
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    
    args = parser.parse_args()
    
    # Setup logging
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add("logs/backfill_{time}.log", rotation="100 MB")
    
    # Parse dates
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    
    # Get password
    db_password = args.db_password or os.getenv('DB_PASSWORD')
    if not db_password:
        logger.error("Database password required")
        sys.exit(1)
    
    # Initialize managers
    db_manager = TimescaleManager(
        host=args.db_host,
        port=args.db_port,
        database=args.db_name,
        user=args.db_user,
        password=db_password
    )
    await db_manager.connect()
    
    redis_manager = RedisCacheManager(
        host=args.redis_host,
        port=args.redis_port
    )
    await redis_manager.connect()
    
    # Run backfill
    backfill = BackfillManager(
        exchange=args.exchange,
        symbol=args.symbol,
        start_date=start_date,
        end_date=end_date,
        timeframe=args.timeframe,
        db_manager=db_manager,
        redis_manager=redis_manager
    )
    
    try:
        await backfill.run()
    finally:
        await db_manager.disconnect()
        await redis_manager.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
