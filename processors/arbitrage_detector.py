"""
Arbitrage Opportunity Detector
Detects price differences across exchanges for the same asset
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from monitoring.logger import logger
from monitoring.metrics import arbitrage_opportunities_total


@dataclass
class Price:
    """Price information"""
    exchange: str
    symbol: str
    price: float
    timestamp: datetime
    volume: float


@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity"""
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    spread: float
    spread_pct: float
    profit_potential: float
    timestamp: datetime
    
    def __str__(self):
        return (
            f"Arbitrage: {self.symbol} | "
            f"Buy {self.buy_exchange} @ ${self.buy_price:.2f} | "
            f"Sell {self.sell_exchange} @ ${self.sell_price:.2f} | "
            f"Spread: {self.spread_pct:.2f}% | "
            f"Profit: ${self.profit_potential:.2f}"
        )


class ArbitrageDetector:
    """
    Detects arbitrage opportunities across exchanges
    
    Example:
        detector = ArbitrageDetector(
            min_spread_pct=0.5,  # Minimum 0.5% spread
            min_profit=10.0      # Minimum $10 profit
        )
        
        # Add prices from different exchanges
        detector.update_price('binance', 'BTCUSDT', 50000.0, 100.0)
        detector.update_price('alpaca', 'BTCUSD', 50300.0, 50.0)
        
        # Check for opportunities
        opportunities = detector.detect_opportunities()
    """
    
    def __init__(
        self,
        min_spread_pct: float = 0.5,  # Minimum spread percentage
        min_profit: float = 10.0,  # Minimum profit in USD
        max_age_seconds: int = 60,  # Maximum price age
        trading_fee: float = 0.001,  # 0.1% trading fee per side
        redis_manager=None,
        alert_manager=None
    ):
        self.min_spread_pct = min_spread_pct
        self.min_profit = min_profit
        self.max_age_seconds = max_age_seconds
        self.trading_fee = trading_fee
        self.redis = redis_manager
        self.alert_manager = alert_manager
        
        # Store latest prices by exchange and symbol
        self.prices: Dict[str, Dict[str, Price]] = {}
        
        # Track detected opportunities
        self.opportunities: List[ArbitrageOpportunity] = []
    
    def update_price(
        self,
        exchange: str,
        symbol: str,
        price: float,
        volume: float,
        timestamp: Optional[datetime] = None
    ):
        """Update price for an exchange/symbol pair"""
        if timestamp is None:
            timestamp = datetime.now()
        
        # Normalize symbol (remove exchange-specific suffixes)
        normalized_symbol = self._normalize_symbol(symbol)
        
        # Store price
        if exchange not in self.prices:
            self.prices[exchange] = {}
        
        self.prices[exchange][normalized_symbol] = Price(
            exchange=exchange,
            symbol=normalized_symbol,
            price=price,
            timestamp=timestamp,
            volume=volume
        )
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol across exchanges"""
        # Remove common suffixes
        symbol = symbol.replace('USDT', 'USD')
        symbol = symbol.replace('BUSD', 'USD')
        symbol = symbol.replace('USDC', 'USD')
        
        return symbol
    
    def detect_opportunities(self) -> List[ArbitrageOpportunity]:
        """Detect arbitrage opportunities"""
        opportunities = []
        
        # Get all symbols that exist on multiple exchanges
        all_symbols = set()
        for exchange_prices in self.prices.values():
            all_symbols.update(exchange_prices.keys())
        
        # Check each symbol
        for symbol in all_symbols:
            # Get prices from all exchanges for this symbol
            symbol_prices = []
            for exchange, exchange_prices in self.prices.items():
                if symbol in exchange_prices:
                    price_info = exchange_prices[symbol]
                    
                    # Check if price is not stale
                    age = (datetime.now() - price_info.timestamp).total_seconds()
                    if age <= self.max_age_seconds:
                        symbol_prices.append(price_info)
            
            # Need at least 2 exchanges
            if len(symbol_prices) < 2:
                continue
            
            # Find best buy and sell prices
            symbol_prices.sort(key=lambda x: x.price)
            buy_price_info = symbol_prices[0]  # Lowest price
            sell_price_info = symbol_prices[-1]  # Highest price
            
            # Calculate spread
            spread = sell_price_info.price - buy_price_info.price
            spread_pct = (spread / buy_price_info.price) * 100
            
            # Calculate profit after fees
            # Buy at lowest price + fee, sell at highest price - fee
            buy_cost = buy_price_info.price * (1 + self.trading_fee)
            sell_proceeds = sell_price_info.price * (1 - self.trading_fee)
            profit_per_unit = sell_proceeds - buy_cost
            
            # Assume 1 unit for profit calculation
            profit_potential = profit_per_unit
            
            # Check if opportunity meets criteria
            if spread_pct >= self.min_spread_pct and profit_potential >= self.min_profit:
                opportunity = ArbitrageOpportunity(
                    symbol=symbol,
                    buy_exchange=buy_price_info.exchange,
                    sell_exchange=sell_price_info.exchange,
                    buy_price=buy_price_info.price,
                    sell_price=sell_price_info.price,
                    spread=spread,
                    spread_pct=spread_pct,
                    profit_potential=profit_potential,
                    timestamp=datetime.now()
                )
                
                opportunities.append(opportunity)
                
                # Log opportunity
                logger.info(f"Arbitrage opportunity detected: {opportunity}")
                
                # Emit metric
                arbitrage_opportunities_total.labels(
                    symbol=symbol,
                    buy_exchange=buy_price_info.exchange,
                    sell_exchange=sell_price_info.exchange
                ).inc()
                
                # Send alert if alert manager is available
                if self.alert_manager:
                    asyncio.create_task(self._send_alert(opportunity))
        
        self.opportunities = opportunities
        return opportunities
    
    async def _send_alert(self, opportunity: ArbitrageOpportunity):
        """Send alert for arbitrage opportunity"""
        try:
            await self.alert_manager.send_alert(
                alert_type='arbitrage',
                symbol=opportunity.symbol,
                message=str(opportunity),
                data={
                    'buy_exchange': opportunity.buy_exchange,
                    'sell_exchange': opportunity.sell_exchange,
                    'buy_price': opportunity.buy_price,
                    'sell_price': opportunity.sell_price,
                    'spread_pct': opportunity.spread_pct,
                    'profit_potential': opportunity.profit_potential
                }
            )
        except Exception as e:
            logger.error(f"Failed to send arbitrage alert: {e}")
    
    def get_opportunities(self, symbol: Optional[str] = None) -> List[ArbitrageOpportunity]:
        """Get current arbitrage opportunities"""
        if symbol:
            return [opp for opp in self.opportunities if opp.symbol == symbol]
        return self.opportunities
    
    def get_best_opportunity(self) -> Optional[ArbitrageOpportunity]:
        """Get opportunity with highest profit potential"""
        if not self.opportunities:
            return None
        
        return max(self.opportunities, key=lambda x: x.profit_potential)
    
    def clear_stale_prices(self):
        """Remove stale prices"""
        now = datetime.now()
        
        for exchange in list(self.prices.keys()):
            for symbol in list(self.prices[exchange].keys()):
                price_info = self.prices[exchange][symbol]
                age = (now - price_info.timestamp).total_seconds()
                
                if age > self.max_age_seconds:
                    del self.prices[exchange][symbol]
            
            # Remove exchange if no symbols left
            if not self.prices[exchange]:
                del self.prices[exchange]
    
    def get_price_comparison(self, symbol: str) -> Dict[str, float]:
        """Get price comparison across exchanges for a symbol"""
        normalized_symbol = self._normalize_symbol(symbol)
        
        comparison = {}
        for exchange, exchange_prices in self.prices.items():
            if normalized_symbol in exchange_prices:
                price_info = exchange_prices[normalized_symbol]
                
                # Check if not stale
                age = (datetime.now() - price_info.timestamp).total_seconds()
                if age <= self.max_age_seconds:
                    comparison[exchange] = price_info.price
        
        return comparison
    
    def get_statistics(self) -> Dict:
        """Get arbitrage detection statistics"""
        total_opportunities = len(self.opportunities)
        
        if total_opportunities == 0:
            return {
                'total_opportunities': 0,
                'avg_spread_pct': 0,
                'max_spread_pct': 0,
                'avg_profit': 0,
                'max_profit': 0
            }
        
        spreads = [opp.spread_pct for opp in self.opportunities]
        profits = [opp.profit_potential for opp in self.opportunities]
        
        return {
            'total_opportunities': total_opportunities,
            'avg_spread_pct': sum(spreads) / len(spreads),
            'max_spread_pct': max(spreads),
            'avg_profit': sum(profits) / len(profits),
            'max_profit': max(profits),
            'symbols': list(set(opp.symbol for opp in self.opportunities))
        }


# Example usage
async def example():
    """Example usage of arbitrage detector"""
    detector = ArbitrageDetector(
        min_spread_pct=0.5,
        min_profit=10.0
    )
    
    # Simulate price updates from different exchanges
    detector.update_price('binance', 'BTCUSDT', 50000.0, 100.0)
    detector.update_price('alpaca', 'BTCUSD', 50300.0, 50.0)
    detector.update_price('yahoo', 'BTC-USD', 50250.0, 75.0)
    
    # Detect opportunities
    opportunities = detector.detect_opportunities()
    
    print(f"\nFound {len(opportunities)} arbitrage opportunities:\n")
    for opp in opportunities:
        print(opp)
    
    # Get statistics
    stats = detector.get_statistics()
    print(f"\nStatistics:")
    print(f"  Total opportunities: {stats['total_opportunities']}")
    print(f"  Average spread: {stats['avg_spread_pct']:.2f}%")
    print(f"  Max spread: {stats['max_spread_pct']:.2f}%")
    print(f"  Average profit: ${stats['avg_profit']:.2f}")
    print(f"  Max profit: ${stats['max_profit']:.2f}")


if __name__ == "__main__":
    asyncio.run(example())
