"""
Backtesting Framework
Test trading strategies on historical data
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class OrderType(Enum):
    """Order types"""
    BUY = "buy"
    SELL = "sell"


@dataclass
class Trade:
    """Trade record"""
    timestamp: datetime
    symbol: str
    order_type: OrderType
    price: float
    quantity: float
    commission: float = 0.0


@dataclass
class Position:
    """Current position"""
    symbol: str
    quantity: float
    entry_price: float
    entry_time: datetime


class BacktestResult:
    """Backtest results and metrics"""
    
    def __init__(self, trades: List[Trade], equity_curve: pd.Series, initial_capital: float):
        self.trades = trades
        self.equity_curve = equity_curve
        self.initial_capital = initial_capital
        self.final_capital = equity_curve.iloc[-1] if len(equity_curve) > 0 else initial_capital
        
        self._calculate_metrics()
    
    def _calculate_metrics(self):
        """Calculate performance metrics"""
        # Total return
        self.total_return = (self.final_capital - self.initial_capital) / self.initial_capital
        self.total_return_pct = self.total_return * 100
        
        # Number of trades
        self.num_trades = len(self.trades)
        
        # Win rate
        if self.num_trades > 0:
            buy_trades = [t for t in self.trades if t.order_type == OrderType.BUY]
            sell_trades = [t for t in self.trades if t.order_type == OrderType.SELL]
            
            if len(buy_trades) > 0 and len(sell_trades) > 0:
                profits = []
                for i in range(min(len(buy_trades), len(sell_trades))):
                    profit = (sell_trades[i].price - buy_trades[i].price) * buy_trades[i].quantity
                    profits.append(profit)
                
                self.winning_trades = sum(1 for p in profits if p > 0)
                self.losing_trades = sum(1 for p in profits if p < 0)
                self.win_rate = self.winning_trades / len(profits) if len(profits) > 0 else 0
                
                self.avg_win = np.mean([p for p in profits if p > 0]) if self.winning_trades > 0 else 0
                self.avg_loss = np.mean([p for p in profits if p < 0]) if self.losing_trades > 0 else 0
                self.profit_factor = abs(self.avg_win / self.avg_loss) if self.avg_loss != 0 else 0
            else:
                self.winning_trades = 0
                self.losing_trades = 0
                self.win_rate = 0
                self.avg_win = 0
                self.avg_loss = 0
                self.profit_factor = 0
        else:
            self.winning_trades = 0
            self.losing_trades = 0
            self.win_rate = 0
            self.avg_win = 0
            self.avg_loss = 0
            self.profit_factor = 0
        
        # Sharpe ratio
        if len(self.equity_curve) > 1:
            returns = self.equity_curve.pct_change().dropna()
            if len(returns) > 0 and returns.std() > 0:
                self.sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)  # Annualized
            else:
                self.sharpe_ratio = 0
        else:
            self.sharpe_ratio = 0
        
        # Maximum drawdown
        if len(self.equity_curve) > 0:
            cummax = self.equity_curve.cummax()
            drawdown = (self.equity_curve - cummax) / cummax
            self.max_drawdown = drawdown.min()
            self.max_drawdown_pct = self.max_drawdown * 100
        else:
            self.max_drawdown = 0
            self.max_drawdown_pct = 0
    
    def summary(self) -> Dict:
        """Get summary statistics"""
        return {
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "total_return": self.total_return,
            "total_return_pct": self.total_return_pct,
            "num_trades": self.num_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "profit_factor": self.profit_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct
        }
    
    def print_summary(self):
        """Print formatted summary"""
        print("\n" + "="*50)
        print("BACKTEST RESULTS")
        print("="*50)
        print(f"Initial Capital:    ${self.initial_capital:,.2f}")
        print(f"Final Capital:      ${self.final_capital:,.2f}")
        print(f"Total Return:       {self.total_return_pct:.2f}%")
        print(f"\nNumber of Trades:   {self.num_trades}")
        print(f"Winning Trades:     {self.winning_trades}")
        print(f"Losing Trades:      {self.losing_trades}")
        print(f"Win Rate:           {self.win_rate*100:.2f}%")
        print(f"\nAverage Win:        ${self.avg_win:.2f}")
        print(f"Average Loss:       ${self.avg_loss:.2f}")
        print(f"Profit Factor:      {self.profit_factor:.2f}")
        print(f"\nSharpe Ratio:       {self.sharpe_ratio:.2f}")
        print(f"Max Drawdown:       {self.max_drawdown_pct:.2f}%")
        print("="*50 + "\n")


class Backtester:
    """
    Backtesting engine for trading strategies
    
    Example:
        def my_strategy(data, position):
            # Buy when RSI < 30
            if data['rsi'].iloc[-1] < 30 and position is None:
                return 'buy', 1.0
            # Sell when RSI > 70
            elif data['rsi'].iloc[-1] > 70 and position is not None:
                return 'sell', position.quantity
            return None, 0
        
        backtester = Backtester(initial_capital=10000, commission=0.001)
        result = backtester.run(data, my_strategy)
        result.print_summary()
    """
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission: float = 0.001,  # 0.1%
        slippage: float = 0.0005  # 0.05%
    ):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        
        self.capital = initial_capital
        self.position: Optional[Position] = None
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
    
    def run(
        self,
        data: pd.DataFrame,
        strategy: Callable[[pd.DataFrame, Optional[Position]], tuple]
    ) -> BacktestResult:
        """
        Run backtest on historical data
        
        Args:
            data: DataFrame with OHLCV and indicator data
            strategy: Strategy function that returns (action, quantity)
                     action: 'buy', 'sell', or None
                     quantity: number of shares/contracts
        
        Returns:
            BacktestResult with performance metrics
        """
        # Reset state
        self.capital = self.initial_capital
        self.position = None
        self.trades = []
        self.equity_curve = []
        
        # Iterate through data
        for i in range(len(data)):
            # Get current data window
            current_data = data.iloc[:i+1]
            current_row = data.iloc[i]
            
            # Calculate current equity
            equity = self.capital
            if self.position is not None:
                equity += self.position.quantity * current_row['close']
            self.equity_curve.append(equity)
            
            # Skip if not enough data
            if i < 20:  # Need minimum data for indicators
                continue
            
            # Call strategy
            action, quantity = strategy(current_data, self.position)
            
            # Execute action
            if action == 'buy' and self.position is None:
                self._execute_buy(current_row, quantity)
            elif action == 'sell' and self.position is not None:
                self._execute_sell(current_row, quantity)
        
        # Close any open position at end
        if self.position is not None:
            self._execute_sell(data.iloc[-1], self.position.quantity)
        
        # Create result
        equity_series = pd.Series(self.equity_curve, index=data.index[:len(self.equity_curve)])
        return BacktestResult(self.trades, equity_series, self.initial_capital)
    
    def _execute_buy(self, row: pd.Series, quantity: float):
        """Execute buy order"""
        # Apply slippage
        price = row['close'] * (1 + self.slippage)
        
        # Calculate cost
        cost = price * quantity
        commission_cost = cost * self.commission
        total_cost = cost + commission_cost
        
        # Check if enough capital
        if total_cost > self.capital:
            quantity = (self.capital / (price * (1 + self.commission)))
            cost = price * quantity
            commission_cost = cost * self.commission
            total_cost = cost + commission_cost
        
        if quantity > 0:
            # Update capital
            self.capital -= total_cost
            
            # Create position
            self.position = Position(
                symbol=row['symbol'],
                quantity=quantity,
                entry_price=price,
                entry_time=row['time']
            )
            
            # Record trade
            trade = Trade(
                timestamp=row['time'],
                symbol=row['symbol'],
                order_type=OrderType.BUY,
                price=price,
                quantity=quantity,
                commission=commission_cost
            )
            self.trades.append(trade)
    
    def _execute_sell(self, row: pd.Series, quantity: float):
        """Execute sell order"""
        if self.position is None:
            return
        
        # Limit quantity to position size
        quantity = min(quantity, self.position.quantity)
        
        # Apply slippage
        price = row['close'] * (1 - self.slippage)
        
        # Calculate proceeds
        proceeds = price * quantity
        commission_cost = proceeds * self.commission
        net_proceeds = proceeds - commission_cost
        
        # Update capital
        self.capital += net_proceeds
        
        # Update or close position
        self.position.quantity -= quantity
        if self.position.quantity <= 0:
            self.position = None
        
        # Record trade
        trade = Trade(
            timestamp=row['time'],
            symbol=row['symbol'],
            order_type=OrderType.SELL,
            price=price,
            quantity=quantity,
            commission=commission_cost
        )
        self.trades.append(trade)


# Example strategies

def rsi_strategy(data: pd.DataFrame, position: Optional[Position]) -> tuple:
    """
    Simple RSI strategy
    Buy when RSI < 30, Sell when RSI > 70
    """
    if len(data) < 20:
        return None, 0
    
    rsi = data['rsi'].iloc[-1]
    
    # Buy signal
    if rsi < 30 and position is None:
        return 'buy', 1.0
    
    # Sell signal
    if rsi > 70 and position is not None:
        return 'sell', position.quantity
    
    return None, 0


def macd_crossover_strategy(data: pd.DataFrame, position: Optional[Position]) -> tuple:
    """
    MACD crossover strategy
    Buy on bullish crossover, Sell on bearish crossover
    """
    if len(data) < 30:
        return None, 0
    
    macd = data['macd'].iloc[-1]
    macd_signal = data['macd_signal'].iloc[-1]
    prev_macd = data['macd'].iloc[-2]
    prev_signal = data['macd_signal'].iloc[-2]
    
    # Bullish crossover
    if prev_macd <= prev_signal and macd > macd_signal and position is None:
        return 'buy', 1.0
    
    # Bearish crossover
    if prev_macd >= prev_signal and macd < macd_signal and position is not None:
        return 'sell', position.quantity
    
    return None, 0


def moving_average_crossover_strategy(data: pd.DataFrame, position: Optional[Position]) -> tuple:
    """
    Moving average crossover strategy
    Buy when SMA(20) crosses above SMA(50)
    Sell when SMA(20) crosses below SMA(50)
    """
    if len(data) < 50:
        return None, 0
    
    sma_20 = data['sma_20'].iloc[-1]
    sma_50 = data['sma_50'].iloc[-1]
    prev_sma_20 = data['sma_20'].iloc[-2]
    prev_sma_50 = data['sma_50'].iloc[-2]
    
    # Golden cross
    if prev_sma_20 <= prev_sma_50 and sma_20 > sma_50 and position is None:
        return 'buy', 1.0
    
    # Death cross
    if prev_sma_20 >= prev_sma_50 and sma_20 < sma_50 and position is not None:
        return 'sell', position.quantity
    
    return None, 0
