"""
Symbol Manager for dynamic symbol configuration.

This module provides methods to manage symbols from the database
instead of hardcoded configuration files.
"""

from typing import List, Optional, Dict
import asyncpg
from loguru import logger

from storage.models import Symbol, AssetClass


class SymbolManager:
    """
    Manages symbols dynamically from database.
    
    Provides methods to:
    - Fetch active symbols by exchange or asset class
    - Add/remove symbols
    - Enable/disable symbols
    - Get symbol metadata
    """
    
    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize SymbolManager.
        
        Args:
            db_pool: AsyncPG connection pool
        """
        self.pool = db_pool
        
    async def get_active_symbols(
        self, 
        exchange: Optional[str] = None,
        asset_class: Optional[AssetClass] = None
    ) -> List[Symbol]:
        """
        Get all active symbols, optionally filtered by exchange or asset class.
        
        Args:
            exchange: Filter by exchange (binance, alpaca, yahoo)
            asset_class: Filter by asset class (CRYPTO, BIST, NASDAQ, NYSE)
            
        Returns:
            List of Symbol objects
        """
        query = "SELECT * FROM symbols WHERE is_active = true"
        params = []
        
        if exchange:
            query += " AND exchange = $1"
            params.append(exchange)
            
        if asset_class:
            param_num = len(params) + 1
            query += f" AND asset_class = ${param_num}"
            params.append(asset_class.value)
            
        query += " ORDER BY asset_class, symbol"
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
        symbols = [Symbol(**dict(row)) for row in rows]
        logger.info(f"Fetched {len(symbols)} active symbols (exchange={exchange}, asset_class={asset_class})")
        
        return symbols
    
    async def get_symbols_by_exchange(self, exchange: str) -> List[str]:
        """
        Get list of active symbol strings for a specific exchange.
        
        Args:
            exchange: Exchange name (binance, alpaca, yahoo)
            
        Returns:
            List of symbol strings (e.g., ['BTCUSDT', 'ETHUSDT'])
        """
        symbols = await self.get_active_symbols(exchange=exchange)
        return [s.symbol for s in symbols]
    
    async def get_symbols_by_asset_class(self, asset_class: AssetClass) -> List[Symbol]:
        """
        Get all active symbols for a specific asset class.
        
        Args:
            asset_class: Asset class enum
            
        Returns:
            List of Symbol objects
        """
        return await self.get_active_symbols(asset_class=asset_class)
    
    async def get_symbol(self, symbol: str, exchange: str) -> Optional[Symbol]:
        """
        Get a specific symbol by symbol string and exchange.
        
        Args:
            symbol: Symbol string (e.g., 'BTCUSDT')
            exchange: Exchange name
            
        Returns:
            Symbol object or None if not found
        """
        query = """
            SELECT * FROM symbols 
            WHERE symbol = $1 AND exchange = $2
        """
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, symbol, exchange)
            
        if row:
            return Symbol(**dict(row))
        return None
    
    async def add_symbol(self, symbol: Symbol) -> int:
        """
        Add a new symbol to the database.
        
        Args:
            symbol: Symbol object to add
            
        Returns:
            ID of the created symbol
        """
        query = """
            INSERT INTO symbols (asset_class, symbol, display_name, exchange, is_active, metadata)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (asset_class, symbol, exchange) DO UPDATE
            SET display_name = EXCLUDED.display_name,
                is_active = EXCLUDED.is_active,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            RETURNING id
        """
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                symbol.asset_class.value,
                symbol.symbol,
                symbol.display_name,
                symbol.exchange,
                symbol.is_active,
                symbol.metadata
            )
            
        symbol_id = row['id']
        logger.info(f"Added/updated symbol: {symbol.symbol} (ID: {symbol_id})")
        return symbol_id
    
    async def enable_symbol(self, symbol: str, exchange: str) -> bool:
        """
        Enable data collection for a symbol.
        
        Args:
            symbol: Symbol string
            exchange: Exchange name
            
        Returns:
            True if successful
        """
        query = """
            UPDATE symbols 
            SET is_active = true, updated_at = NOW()
            WHERE symbol = $1 AND exchange = $2
        """
        
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, symbol, exchange)
            
        success = result.split()[-1] == '1'
        if success:
            logger.info(f"Enabled symbol: {symbol} on {exchange}")
        return success
    
    async def disable_symbol(self, symbol: str, exchange: str) -> bool:
        """
        Disable data collection for a symbol.
        
        Args:
            symbol: Symbol string
            exchange: Exchange name
            
        Returns:
            True if successful
        """
        query = """
            UPDATE symbols 
            SET is_active = false, updated_at = NOW()
            WHERE symbol = $1 AND exchange = $2
        """
        
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, symbol, exchange)
            
        success = result.split()[-1] == '1'
        if success:
            logger.info(f"Disabled symbol: {symbol} on {exchange}")
        return success
    
    async def get_all_symbols_grouped(self) -> Dict[str, List[Symbol]]:
        """
        Get all active symbols grouped by exchange.
        
        Returns:
            Dictionary with exchange names as keys and symbol lists as values
        """
        symbols = await self.get_active_symbols()
        
        grouped = {}
        for symbol in symbols:
            if symbol.exchange not in grouped:
                grouped[symbol.exchange] = []
            grouped[symbol.exchange].append(symbol)
            
        return grouped
    
    async def get_symbol_count(self) -> Dict[str, int]:
        """
        Get count of active symbols by exchange.
        
        Returns:
            Dictionary with exchange names and counts
        """
        query = """
            SELECT exchange, COUNT(*) as count
            FROM symbols
            WHERE is_active = true
            GROUP BY exchange
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
            
        return {row['exchange']: row['count'] for row in rows}
