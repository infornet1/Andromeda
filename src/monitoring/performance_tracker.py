#!/usr/bin/env python3
"""
Performance Tracker for ADX Strategy v2.0
Tracks and analyzes trading performance metrics
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceTracker:
    """
    Performance Analytics and Tracking

    Features:
    - Trade performance metrics
    - Win rate analysis
    - Profit factor calculation
    - Drawdown tracking
    - Time-based analytics
    - Performance charts (text-based)
    """

    def __init__(self,
                 paper_trader=None,
                 position_manager=None,
                 risk_manager=None):
        """
        Initialize performance tracker

        Args:
            paper_trader: PaperTrader instance
            position_manager: PositionManager instance
            risk_manager: RiskManager instance
        """
        self.trader = paper_trader
        self.position_mgr = position_manager
        self.risk_mgr = risk_manager

        # Performance history
        self.snapshots = []
        self.performance_log = []

        logger.info("Performance Tracker initialized")

    def capture_snapshot(self):
        """Capture current performance snapshot"""
        snapshot = {
            'timestamp': datetime.now(),
            'balance': self.trader.balance if self.trader else 0,
            'equity': self._calculate_equity(),
            'total_pnl': self._calculate_total_pnl(),
            'open_positions': len(self.position_mgr.get_open_positions()) if self.position_mgr else 0,
            'total_trades': self.position_mgr.get_position_stats()['total_positions'] if self.position_mgr else 0
        }

        self.snapshots.append(snapshot)
        return snapshot

    def _calculate_equity(self) -> float:
        """Calculate total equity (balance + unrealized P&L)"""
        if not self.trader or not self.position_mgr:
            return 0

        balance = self.trader.balance
        unrealized = sum(
            p.get('unrealized_pnl', 0)
            for p in self.position_mgr.get_open_positions()
        )

        return balance + unrealized

    def _calculate_total_pnl(self) -> float:
        """Calculate total realized P&L"""
        if not self.trader:
            return 0

        return self.trader.balance - self.trader.initial_balance

    def get_performance_metrics(self) -> Dict:
        """
        Get comprehensive performance metrics

        Returns:
            Dictionary with all performance metrics
        """
        if not self.position_mgr:
            return {}

        stats = self.position_mgr.get_position_stats()
        closed_positions = self.position_mgr.get_closed_positions()

        # Basic metrics
        total_trades = stats['total_positions']
        wins = stats['winning_positions']
        losses = stats['losing_positions']
        win_rate = stats['win_rate']

        # P&L metrics
        total_pnl = stats['total_pnl']
        avg_win = stats['avg_win']
        avg_loss = stats['avg_loss']
        profit_factor = stats['profit_factor']

        # Calculate additional metrics
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0

        # Win/loss streaks
        current_streak, max_win_streak, max_loss_streak = self._calculate_streaks(closed_positions)

        # Hold time analysis
        avg_hold_time, avg_win_hold, avg_loss_hold = self._calculate_hold_times(closed_positions)

        # Drawdown analysis
        max_dd, current_dd = self._calculate_drawdown()

        # Risk-adjusted returns
        sharpe_ratio = self._calculate_sharpe_ratio()
        expectancy = self._calculate_expectancy(win_rate, avg_win, avg_loss)

        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': round(avg_pnl, 2),
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'current_streak': current_streak,
            'max_win_streak': max_win_streak,
            'max_loss_streak': max_loss_streak,
            'avg_hold_time': round(avg_hold_time, 2),
            'avg_win_hold': round(avg_win_hold, 2),
            'avg_loss_hold': round(avg_loss_hold, 2),
            'max_drawdown': round(max_dd, 2),
            'current_drawdown': round(current_dd, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'expectancy': round(expectancy, 2)
        }

    def _calculate_streaks(self, positions: List[Dict]) -> tuple:
        """Calculate win/loss streaks"""
        if not positions:
            return 0, 0, 0

        # Sort by closed time
        sorted_pos = sorted(positions, key=lambda x: x['closed_at'])

        current_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        current_win_streak = 0
        current_loss_streak = 0

        for pos in sorted_pos:
            if pos['pnl'] > 0:
                current_win_streak += 1
                current_loss_streak = 0
                max_win_streak = max(max_win_streak, current_win_streak)
                current_streak = current_win_streak
            elif pos['pnl'] < 0:
                current_loss_streak += 1
                current_win_streak = 0
                max_loss_streak = max(max_loss_streak, current_loss_streak)
                current_streak = -current_loss_streak

        return current_streak, max_win_streak, max_loss_streak

    def _calculate_hold_times(self, positions: List[Dict]) -> tuple:
        """Calculate average hold times"""
        if not positions:
            return 0, 0, 0

        all_holds = [p['hold_duration'] for p in positions]
        win_holds = [p['hold_duration'] for p in positions if p['pnl'] > 0]
        loss_holds = [p['hold_duration'] for p in positions if p['pnl'] < 0]

        avg_hold = sum(all_holds) / len(all_holds) if all_holds else 0
        avg_win_hold = sum(win_holds) / len(win_holds) if win_holds else 0
        avg_loss_hold = sum(loss_holds) / len(loss_holds) if loss_holds else 0

        return avg_hold, avg_win_hold, avg_loss_hold

    def _calculate_drawdown(self) -> tuple:
        """Calculate maximum and current drawdown"""
        if not self.trader:
            return 0, 0

        peak = self.trader.peak_balance
        current = self.trader.balance

        current_dd = ((peak - current) / peak * 100) if peak > 0 else 0
        max_dd = self.trader.max_drawdown

        return max_dd, current_dd

    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio (risk-adjusted returns)"""
        if not self.position_mgr:
            return 0

        positions = self.position_mgr.get_closed_positions()
        if len(positions) < 2:
            return 0

        returns = [p['pnl_percent'] for p in positions]
        avg_return = sum(returns) / len(returns)

        # Calculate standard deviation
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5

        # Sharpe = (avg return - risk free rate) / std dev
        # Assuming 0 risk-free rate for simplicity
        sharpe = avg_return / std_dev if std_dev > 0 else 0

        return sharpe

    def _calculate_expectancy(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Calculate expectancy (expected value per trade)"""
        if win_rate == 0:
            return 0

        win_rate_decimal = win_rate / 100
        loss_rate = 1 - win_rate_decimal

        expectancy = (win_rate_decimal * avg_win) - (loss_rate * avg_loss)

        return expectancy

    def get_trade_analysis(self) -> Dict:
        """Get detailed trade analysis"""
        if not self.position_mgr:
            return {}

        positions = self.position_mgr.get_closed_positions()

        # Exit reason breakdown
        exit_reasons = {}
        for pos in positions:
            reason = pos['exit_reason']
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

        # Side analysis (LONG vs SHORT)
        long_trades = [p for p in positions if p['side'] == 'LONG']
        short_trades = [p for p in positions if p['side'] == 'SHORT']

        long_wins = len([p for p in long_trades if p['pnl'] > 0])
        short_wins = len([p for p in short_trades if p['pnl'] > 0])

        long_wr = (long_wins / len(long_trades) * 100) if long_trades else 0
        short_wr = (short_wins / len(short_trades) * 100) if short_trades else 0

        long_pnl = sum(p['pnl'] for p in long_trades)
        short_pnl = sum(p['pnl'] for p in short_trades)

        return {
            'exit_reasons': exit_reasons,
            'long_trades': len(long_trades),
            'long_wins': long_wins,
            'long_win_rate': round(long_wr, 2),
            'long_pnl': round(long_pnl, 2),
            'short_trades': len(short_trades),
            'short_wins': short_wins,
            'short_win_rate': round(short_wr, 2),
            'short_pnl': round(short_pnl, 2)
        }

    def get_time_analysis(self, period: str = 'all') -> Dict:
        """
        Get time-based performance analysis

        Args:
            period: 'hour', 'day', 'week', or 'all'

        Returns:
            Time-based metrics
        """
        if not self.position_mgr:
            return {}

        positions = self.position_mgr.get_closed_positions()

        if period != 'all':
            # Filter by time period
            now = datetime.now()
            if period == 'hour':
                cutoff = now - timedelta(hours=1)
            elif period == 'day':
                cutoff = now - timedelta(days=1)
            elif period == 'week':
                cutoff = now - timedelta(weeks=1)
            else:
                cutoff = None

            if cutoff:
                positions = [p for p in positions if p['closed_at'] > cutoff]

        if not positions:
            return {'period': period, 'trades': 0}

        total_pnl = sum(p['pnl'] for p in positions)
        wins = len([p for p in positions if p['pnl'] > 0])
        win_rate = (wins / len(positions) * 100) if positions else 0

        return {
            'period': period,
            'trades': len(positions),
            'wins': wins,
            'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2)
        }

    def generate_equity_curve(self, width: int = 60) -> str:
        """
        Generate text-based equity curve

        Args:
            width: Width of chart in characters

        Returns:
            Text chart
        """
        if not self.snapshots or len(self.snapshots) < 2:
            return "Not enough data for equity curve"

        balances = [s['balance'] for s in self.snapshots]
        min_balance = min(balances)
        max_balance = max(balances)

        # Normalize to 0-10 range
        height = 10
        chart_lines = [[] for _ in range(height + 1)]

        for balance in balances:
            if max_balance == min_balance:
                normalized = height // 2
            else:
                normalized = int((balance - min_balance) / (max_balance - min_balance) * height)

            # Add point to chart
            for i in range(height + 1):
                if i == (height - normalized):
                    chart_lines[i].append('●')
                else:
                    chart_lines[i].append(' ')

        # Build chart
        chart = f"\nEquity Curve (${min_balance:.2f} - ${max_balance:.2f})\n"
        chart += "─" * (width + 10) + "\n"

        for i, line in enumerate(chart_lines):
            value = max_balance - (i * (max_balance - min_balance) / height)
            chart += f"${value:>6.2f} │ {''.join(line[:width])}\n"

        chart += " " * 8 + "└" + "─" * width + "\n"
        chart += " " * 10 + f"Snapshots: {len(balances)}\n"

        return chart

    def generate_performance_report(self) -> str:
        """Generate comprehensive performance report"""
        metrics = self.get_performance_metrics()
        analysis = self.get_trade_analysis()

        if not metrics:
            return "No performance data available"

        report = f"""
{'='*80}
{'PERFORMANCE REPORT':^80}
{'='*80}

┌─ OVERALL PERFORMANCE {'─'*56}┐
│ Total Trades:     {metrics['total_trades']:>4}
│ Wins / Losses:    {metrics['wins']:>4} / {metrics['losses']:<4}
│ Win Rate:         {metrics['win_rate']:>6.2f}%
│ Total P&L:        ${metrics['total_pnl']:>+10,.2f}
│ Avg P&L:          ${metrics['avg_pnl']:>+10,.2f}
│ Profit Factor:    {metrics['profit_factor']:>10.2f}
│ Expectancy:       ${metrics['expectancy']:>+10,.2f}
└{'─'*78}┘

┌─ WIN/LOSS ANALYSIS {'─'*57}┐
│ Avg Win:          ${metrics['avg_win']:>10,.2f}
│ Avg Loss:         ${metrics['avg_loss']:>10,.2f}
│ Win/Loss Ratio:   {(metrics['avg_win'] / metrics['avg_loss']) if metrics['avg_loss'] > 0 else 0:>10.2f}
│
│ Current Streak:   {metrics['current_streak']:>+4} {'wins' if metrics['current_streak'] > 0 else 'losses' if metrics['current_streak'] < 0 else 'none'}
│ Max Win Streak:   {metrics['max_win_streak']:>4}
│ Max Loss Streak:  {metrics['max_loss_streak']:>4}
└{'─'*78}┘

┌─ HOLD TIME ANALYSIS {'─'*55}┐
│ Avg Hold Time:    {metrics['avg_hold_time']:>8.1f} minutes
│ Avg Win Hold:     {metrics['avg_win_hold']:>8.1f} minutes
│ Avg Loss Hold:    {metrics['avg_loss_hold']:>8.1f} minutes
└{'─'*78}┘

┌─ RISK METRICS {'─'*62}┐
│ Max Drawdown:     {metrics['max_drawdown']:>8.2f}%
│ Current Drawdown: {metrics['current_drawdown']:>8.2f}%
│ Sharpe Ratio:     {metrics['sharpe_ratio']:>8.2f}
└{'─'*78}┘

┌─ TRADE BREAKDOWN {'─'*60}┐
│ LONG Trades:      {analysis['long_trades']:>4}  ({analysis['long_wins']} wins, {analysis['long_win_rate']:.1f}% WR)  P&L: ${analysis['long_pnl']:+.2f}
│ SHORT Trades:     {analysis['short_trades']:>4}  ({analysis['short_wins']} wins, {analysis['short_win_rate']:.1f}% WR)  P&L: ${analysis['short_pnl']:+.2f}
│
│ Exit Reasons:
"""

        for reason, count in analysis['exit_reasons'].items():
            report += f"│   {reason:<18} {count:>4}\n"

        report += f"└{'─'*78}┘\n"
        report += f"\n{'='*80}\n"

        return report


if __name__ == "__main__":
    # Test script
    from src.execution.paper_trader import PaperTrader
    from src.execution.position_manager import PositionManager
    from src.execution.order_executor import OrderExecutor
    from src.risk.risk_manager import RiskManager
    from src.risk.position_sizer import PositionSizer

    print("Testing Performance Tracker...")

    # Initialize components
    executor = OrderExecutor(enable_live_trading=False)
    position_mgr = PositionManager(order_executor=executor)
    risk_mgr = RiskManager(initial_capital=100.0)
    trader = PaperTrader(
        initial_balance=100.0,
        leverage=5,
        order_executor=executor,
        position_manager=position_mgr,
        risk_manager=risk_mgr
    )

    # Initialize performance tracker
    perf = PerformanceTracker(
        paper_trader=trader,
        position_manager=position_mgr,
        risk_manager=risk_mgr
    )

    print("\n1. Initial snapshot")
    perf.capture_snapshot()

    # Execute some trades
    sizer = PositionSizer(initial_capital=100.0, leverage=5)

    trades = [
        {'side': 'LONG', 'entry': 112000, 'sl': 111500, 'tp': 113000, 'exit': 113000, 'reason': 'TAKE_PROFIT'},
        {'side': 'SHORT', 'entry': 113000, 'sl': 113500, 'tp': 112000, 'exit': 113500, 'reason': 'STOP_LOSS'},
        {'side': 'LONG', 'entry': 112500, 'sl': 112000, 'tp': 114000, 'exit': 112700, 'reason': 'MANUAL'},
    ]

    for i, trade in enumerate(trades):
        signal = {
            'signal_id': f'TEST_{i:03d}',
            'side': trade['side'],
            'confidence': 0.80,
            'stop_loss': trade['sl'],
            'take_profit': trade['tp']
        }

        pos_size = sizer.calculate_position_size(trade['entry'], trade['sl'])
        result = trader.execute_signal(signal, trade['entry'], pos_size)

        if result:
            # Update and close
            trader.monitor_positions(trade['exit'])

        perf.capture_snapshot()

    print("\n2. Performance Metrics")
    metrics = perf.get_performance_metrics()
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    print("\n3. Trade Analysis")
    analysis = perf.get_trade_analysis()
    for key, value in analysis.items():
        print(f"  {key}: {value}")

    print("\n4. Performance Report")
    print(perf.generate_performance_report())

    print("\n5. Equity Curve")
    print(perf.generate_equity_curve())

    print("\n✅ Performance Tracker test complete!")
