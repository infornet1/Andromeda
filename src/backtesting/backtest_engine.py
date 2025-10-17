#!/usr/bin/env python3
"""
Backtest Engine for ADX Strategy v2.0
Tests strategy against historical data
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Historical Backtesting Engine

    Features:
    - Test strategy on historical data
    - Simulate realistic trading
    - Track performance metrics
    - Generate detailed reports
    - Support for different timeframes
    """

    def __init__(self,
                 initial_capital: float = 100.0,
                 leverage: int = 5,
                 commission: float = 0.0005,
                 slippage: float = 0.0002):
        """
        Initialize backtest engine

        Args:
            initial_capital: Starting capital
            leverage: Leverage multiplier
            commission: Trading commission (0.05%)
            slippage: Slippage per trade (0.02%)
        """
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.commission = commission
        self.slippage = slippage

        # Backtest state
        self.capital = initial_capital
        self.peak_capital = initial_capital
        self.equity_curve = []
        self.trades = []
        self.open_position = None

        # Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_commission_paid = 0
        self.total_slippage_cost = 0

        logger.info(f"Backtest Engine initialized: ${initial_capital} @ {leverage}× leverage")

    def run_backtest(self,
                    data: pd.DataFrame,
                    signals: List[Dict],
                    strategy_name: str = "ADX_v2") -> Dict:
        """
        Run backtest on historical data

        Args:
            data: DataFrame with OHLCV data
            signals: List of trading signals
            strategy_name: Name of strategy

        Returns:
            Backtest results dictionary
        """
        logger.info(f"Starting backtest: {strategy_name}")
        logger.info(f"Data: {len(data)} candles, {len(signals)} signals")

        # Reset state
        self._reset_state()

        # Process each signal
        for signal in signals:
            self._process_signal(signal, data)

        # Close any remaining position
        if self.open_position:
            last_price = data.iloc[-1]['close']
            self._close_position(last_price, 'BACKTEST_END', data.iloc[-1])

        # Calculate final metrics
        results = self._calculate_results(strategy_name, data)

        logger.info(f"Backtest complete: {self.total_trades} trades, "
                   f"{self.winning_trades}W/{self.losing_trades}L")

        return results

    def _reset_state(self):
        """Reset backtest state"""
        self.capital = self.initial_capital
        self.peak_capital = self.initial_capital
        self.equity_curve = [{'timestamp': datetime.now(), 'equity': self.initial_capital}]
        self.trades = []
        self.open_position = None
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_commission_paid = 0
        self.total_slippage_cost = 0

    def _process_signal(self, signal: Dict, data: pd.DataFrame):
        """Process trading signal"""
        # If position open, check exit conditions
        if self.open_position:
            self._check_exit_conditions(signal, data)
        # If no position, check entry signal
        elif signal.get('action') == 'ENTRY':
            self._open_position(signal, data)

    def _open_position(self, signal: Dict, data: pd.DataFrame):
        """Open new position from signal"""
        entry_price = signal['entry_price']
        side = signal['side']

        # Apply slippage
        if side == 'LONG':
            entry_price = entry_price * (1 + self.slippage)
        else:
            entry_price = entry_price * (1 - self.slippage)

        # Calculate position size (2% risk)
        risk_amount = self.capital * 0.02
        stop_distance = abs(entry_price - signal['stop_loss'])
        stop_distance_pct = stop_distance / entry_price

        position_size_usd = risk_amount / stop_distance_pct
        position_size_btc = position_size_usd / entry_price

        # Apply leverage limit
        max_position = self.capital * self.leverage
        if position_size_usd > max_position * 0.2:  # Max 20% of leveraged capital
            position_size_usd = max_position * 0.2
            position_size_btc = position_size_usd / entry_price

        # Calculate commission
        commission = position_size_usd * self.commission
        self.total_commission_paid += commission

        # Create position
        self.open_position = {
            'entry_time': signal.get('timestamp', datetime.now()),
            'entry_price': entry_price,
            'side': side,
            'size_btc': position_size_btc,
            'size_usd': position_size_usd,
            'stop_loss': signal['stop_loss'],
            'take_profit': signal['take_profit'],
            'commission': commission,
            'signal_data': signal
        }

        logger.debug(f"Position opened: {side} {position_size_btc:.5f} BTC @ ${entry_price:,.2f}")

    def _check_exit_conditions(self, signal: Dict, data: pd.DataFrame):
        """Check if position should be closed"""
        if not self.open_position:
            return

        # Get signal timestamp and find corresponding candle
        signal_time = signal.get('timestamp')
        if signal_time:
            # Find candle at signal time
            candle = data[data['timestamp'] == signal_time]
            if candle.empty:
                return

            candle = candle.iloc[0]

            # Check SL/TP hit (intrabar)
            if self.open_position['side'] == 'LONG':
                # Check stop loss
                if candle['low'] <= self.open_position['stop_loss']:
                    self._close_position(self.open_position['stop_loss'], 'STOP_LOSS', candle)
                    return
                # Check take profit
                elif candle['high'] >= self.open_position['take_profit']:
                    self._close_position(self.open_position['take_profit'], 'TAKE_PROFIT', candle)
                    return
            else:  # SHORT
                # Check stop loss
                if candle['high'] >= self.open_position['stop_loss']:
                    self._close_position(self.open_position['stop_loss'], 'STOP_LOSS', candle)
                    return
                # Check take profit
                elif candle['low'] <= self.open_position['take_profit']:
                    self._close_position(self.open_position['take_profit'], 'TAKE_PROFIT', candle)
                    return

        # Check for exit signal
        if signal.get('action') == 'EXIT':
            exit_price = signal.get('exit_price', candle['close'])
            self._close_position(exit_price, signal.get('reason', 'SIGNAL'), candle)

    def _close_position(self, exit_price: float, reason: str, candle: pd.Series):
        """Close open position"""
        if not self.open_position:
            return

        pos = self.open_position
        side = pos['side']

        # Apply slippage
        if side == 'LONG':
            exit_price = exit_price * (1 - self.slippage)
        else:
            exit_price = exit_price * (1 + self.slippage)

        # Calculate P&L
        if side == 'LONG':
            price_change = exit_price - pos['entry_price']
        else:
            price_change = pos['entry_price'] - exit_price

        pnl = price_change * pos['size_btc']
        pnl_with_leverage = pnl * self.leverage

        # Subtract commission
        exit_commission = pos['size_usd'] * self.commission
        self.total_commission_paid += exit_commission

        net_pnl = pnl_with_leverage - pos['commission'] - exit_commission

        # Update capital
        self.capital += net_pnl

        # Track peak
        if self.capital > self.peak_capital:
            self.peak_capital = self.capital

        # Record trade
        trade = {
            'entry_time': pos['entry_time'],
            'exit_time': candle.get('timestamp', datetime.now()),
            'side': side,
            'entry_price': pos['entry_price'],
            'exit_price': exit_price,
            'size_btc': pos['size_btc'],
            'size_usd': pos['size_usd'],
            'pnl': net_pnl,
            'pnl_percent': (net_pnl / self.initial_capital) * 100,
            'exit_reason': reason,
            'hold_bars': 0,  # Could calculate from timestamps
            'commission': pos['commission'] + exit_commission
        }

        self.trades.append(trade)
        self.total_trades += 1

        if net_pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        # Update equity curve
        self.equity_curve.append({
            'timestamp': trade['exit_time'],
            'equity': self.capital
        })

        logger.debug(f"Position closed: {reason}, P&L: ${net_pnl:+.2f}")

        # Clear position
        self.open_position = None

    def _calculate_results(self, strategy_name: str, data: pd.DataFrame) -> Dict:
        """Calculate comprehensive backtest results"""

        # Basic metrics
        total_return = self.capital - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100

        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0

        # P&L analysis
        winning_pnls = [t['pnl'] for t in self.trades if t['pnl'] > 0]
        losing_pnls = [abs(t['pnl']) for t in self.trades if t['pnl'] < 0]

        avg_win = sum(winning_pnls) / len(winning_pnls) if winning_pnls else 0
        avg_loss = sum(losing_pnls) / len(losing_pnls) if losing_pnls else 0
        profit_factor = sum(winning_pnls) / sum(losing_pnls) if losing_pnls else 0

        # Drawdown analysis
        max_dd, max_dd_pct = self._calculate_max_drawdown()

        # Sharpe ratio
        sharpe = self._calculate_sharpe_ratio()

        # Expectancy
        expectancy = (win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss)

        # Exit reasons
        exit_reasons = {}
        for trade in self.trades:
            reason = trade['exit_reason']
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

        # Time analysis
        if len(data) > 0:
            start_date = data.iloc[0]['timestamp']
            end_date = data.iloc[-1]['timestamp']
            duration_days = (end_date - start_date).total_seconds() / 86400
        else:
            start_date = end_date = datetime.now()
            duration_days = 0

        return {
            'strategy_name': strategy_name,
            'start_date': start_date,
            'end_date': end_date,
            'duration_days': duration_days,
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'peak_capital': self.peak_capital,
            'max_drawdown': max_dd,
            'max_drawdown_pct': max_dd_pct,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'expectancy': expectancy,
            'total_commission': self.total_commission_paid,
            'total_slippage': self.total_slippage_cost,
            'exit_reasons': exit_reasons,
            'equity_curve': self.equity_curve,
            'trades': self.trades
        }

    def _calculate_max_drawdown(self) -> tuple:
        """Calculate maximum drawdown"""
        if not self.equity_curve:
            return 0, 0

        peak = self.initial_capital
        max_dd = 0
        max_dd_pct = 0

        for point in self.equity_curve:
            equity = point['equity']
            if equity > peak:
                peak = equity

            dd = peak - equity
            dd_pct = (dd / peak * 100) if peak > 0 else 0

            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct

        return max_dd, max_dd_pct

    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio"""
        if len(self.trades) < 2:
            return 0

        returns = [t['pnl_percent'] for t in self.trades]
        avg_return = sum(returns) / len(returns)

        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5

        sharpe = avg_return / std_dev if std_dev > 0 else 0

        return sharpe

    def generate_report(self, results: Dict) -> str:
        """Generate human-readable backtest report"""

        report = f"""
{'='*80}
{'BACKTEST REPORT':^80}
{'='*80}
Strategy:         {results['strategy_name']}
Period:           {results['start_date'].strftime('%Y-%m-%d')} to {results['end_date'].strftime('%Y-%m-%d')}
Duration:         {results['duration_days']:.1f} days

{'='*80}
CAPITAL & RETURNS
{'='*80}
Initial Capital:  ${results['initial_capital']:,.2f}
Final Capital:    ${results['final_capital']:,.2f}
Total Return:     ${results['total_return']:+,.2f} ({results['total_return_pct']:+.2f}%)
Peak Capital:     ${results['peak_capital']:,.2f}
Max Drawdown:     ${results['max_drawdown']:,.2f} ({results['max_drawdown_pct']:.2f}%)

{'='*80}
TRADE STATISTICS
{'='*80}
Total Trades:     {results['total_trades']}
Winning Trades:   {results['winning_trades']}
Losing Trades:    {results['losing_trades']}
Win Rate:         {results['win_rate']:.2f}%

Avg Win:          ${results['avg_win']:,.2f}
Avg Loss:         ${results['avg_loss']:,.2f}
Profit Factor:    {results['profit_factor']:.2f}
Expectancy:       ${results['expectancy']:+,.2f}

{'='*80}
RISK METRICS
{'='*80}
Sharpe Ratio:     {results['sharpe_ratio']:.2f}
Max Drawdown:     {results['max_drawdown_pct']:.2f}%

{'='*80}
COSTS
{'='*80}
Total Commission: ${results['total_commission']:,.2f}
Total Slippage:   ${results['total_slippage']:,.2f}

{'='*80}
EXIT REASONS
{'='*80}
"""

        for reason, count in results['exit_reasons'].items():
            pct = (count / results['total_trades'] * 100) if results['total_trades'] > 0 else 0
            report += f"{reason:<20} {count:>4} ({pct:.1f}%)\n"

        report += f"\n{'='*80}\n"

        return report


if __name__ == "__main__":
    # Test script
    import numpy as np

    print("Testing Backtest Engine...")

    # Create synthetic data
    dates = pd.date_range(start='2025-01-01', periods=1000, freq='5min')
    np.random.seed(42)

    prices = 112000 + np.cumsum(np.random.randn(1000) * 100)

    data = pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': prices + np.random.rand(1000) * 50,
        'low': prices - np.random.rand(1000) * 50,
        'close': prices + np.random.randn(1000) * 20,
        'volume': np.random.rand(1000) * 1000
    })

    # Create test signals
    signals = []
    for i in range(0, 900, 100):
        # Entry signal
        signals.append({
            'timestamp': data.iloc[i]['timestamp'],
            'action': 'ENTRY',
            'side': 'LONG' if i % 200 == 0 else 'SHORT',
            'entry_price': data.iloc[i]['close'],
            'stop_loss': data.iloc[i]['close'] * 0.995,
            'take_profit': data.iloc[i]['close'] * 1.01
        })

    # Initialize and run backtest
    engine = BacktestEngine(initial_capital=100.0, leverage=5)
    results = engine.run_backtest(data, signals, "Test_Strategy")

    # Print report
    print(engine.generate_report(results))

    print(f"\n✅ Backtest Engine test complete!")
    print(f"Processed {len(data)} candles, {len(signals)} signals")
    print(f"Result: ${results['final_capital']:.2f} ({results['total_return_pct']:+.2f}%)")
