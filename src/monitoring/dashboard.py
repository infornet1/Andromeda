#!/usr/bin/env python3
"""
Real-time Monitoring Dashboard for Scalping Strategy v2.0
Displays current positions, orders, balance, and risk status
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/scalping_v2')

from typing import Dict, List, Optional
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Dashboard:
    """
    Real-time Monitoring Dashboard

    Features:
    - Current positions display
    - Open orders tracking
    - Balance and equity monitoring
    - Risk status overview
    - Recent trades history
    - System status
    """

    def __init__(self,
                 paper_trader=None,
                 position_manager=None,
                 order_executor=None,
                 risk_manager=None,
                 refresh_interval: int = 5):
        """
        Initialize dashboard

        Args:
            paper_trader: PaperTrader instance
            position_manager: PositionManager instance
            order_executor: OrderExecutor instance
            risk_manager: RiskManager instance
            refresh_interval: Dashboard refresh interval in seconds
        """
        self.trader = paper_trader
        self.position_mgr = position_manager
        self.executor = order_executor
        self.risk_mgr = risk_manager
        self.refresh_interval = refresh_interval

        self.last_update = None
        self.update_count = 0

        logger.info("Dashboard initialized")

    def get_snapshot(self) -> Dict:
        """
        Get complete system snapshot

        Returns:
            Dictionary with all current data
        """
        snapshot = {
            'timestamp': datetime.now(),
            'account': self._get_account_data(),
            'positions': self._get_positions_data(),
            'orders': self._get_orders_data(),
            'risk': self._get_risk_data(),
            'recent_trades': self._get_recent_trades(),
            'system': self._get_system_status()
        }

        self.last_update = datetime.now()
        self.update_count += 1

        return snapshot

    def _get_account_data(self) -> Dict:
        """Get account balance and equity data"""
        if not self.trader:
            return {}

        account = self.trader.get_account_status()
        perf = self.trader.get_performance_stats()

        return {
            'balance': account['balance'],
            'equity': account['equity'],
            'available': account['margin_available'],
            'margin_used': account['margin_used'],
            'unrealized_pnl': account['unrealized_pnl'],
            'total_pnl': perf['total_pnl'],
            'total_return_percent': perf['total_return_percent'],
            'peak_balance': perf['peak_balance'],
            'max_drawdown': perf['max_drawdown_percent']
        }

    def _get_positions_data(self) -> List[Dict]:
        """Get current open positions"""
        if not self.position_mgr:
            return []

        positions = self.position_mgr.get_open_positions()

        position_data = []
        for pos in positions:
            position_data.append({
                'id': pos['position_id'],
                'side': pos['side'],
                'symbol': pos['symbol'],
                'entry_price': pos['entry_price'],
                'current_price': pos['current_price'],
                'quantity': pos['quantity'],
                'stop_loss': pos['stop_loss'],
                'take_profit': pos['take_profit'],
                'pnl': pos['pnl'],
                'pnl_percent': pos['pnl_percent'],
                'hold_duration': pos['hold_duration'],
                'margin_required': pos['margin_required']
            })

        return position_data

    def _get_orders_data(self) -> List[Dict]:
        """Get current orders"""
        if not self.executor:
            return []

        pending = self.executor.get_all_orders(status='PENDING')

        order_data = []
        for order in pending[:10]:  # Last 10 orders
            order_data.append({
                'id': order['order_id'],
                'type': order['type'],
                'side': order['side'],
                'quantity': order['quantity'],
                'status': order['status'],
                'created_at': order['created_at']
            })

        return order_data

    def _get_risk_data(self) -> Dict:
        """Get risk manager status"""
        if not self.risk_mgr:
            return {}

        status = self.risk_mgr.get_risk_status()

        return {
            'daily_pnl': status['daily_pnl'],
            'daily_loss_percent': status['daily_loss_percent'],
            'daily_loss_limit': status['daily_loss_limit'],
            'daily_loss_remaining': status['daily_loss_remaining'],
            'drawdown_percent': status['drawdown_percent'],
            'drawdown_limit': status['drawdown_limit'],
            'open_positions': status['open_positions'],
            'max_positions': status['max_positions'],
            'consecutive_losses': status['consecutive_losses'],
            'consecutive_loss_limit': status['consecutive_loss_limit'],
            'circuit_breaker_active': status['circuit_breaker_active'],
            'circuit_breaker_reason': status['circuit_breaker_reason'],
            'can_trade': status['can_trade']
        }

    def _get_recent_trades(self) -> List[Dict]:
        """Get recent closed positions - simplified format for snapshot"""
        # Try to get from database first (persistent storage)
        try:
            from src.persistence.trade_database import TradeDatabase
            db = TradeDatabase()
            db_trades = db.get_all_trades(limit=10)

            if db_trades:
                # Convert database trades to dashboard format
                trade_data = []
                for trade in db_trades:
                    trade_data.append({
                        'id': trade.get('id'),
                        'side': trade.get('side'),
                        'entry_price': trade.get('entry_price'),
                        'exit_price': trade.get('exit_price'),
                        'pnl': trade.get('pnl'),
                        'pnl_percent': trade.get('pnl_percent'),
                        'exit_reason': trade.get('exit_reason'),
                        'hold_duration': trade.get('hold_duration'),
                        'closed_at': trade.get('closed_at')
                    })
                return trade_data
        except Exception as e:
            logger.warning(f"Could not read from database: {e}")

        # Fallback to position manager (in-memory, current session only)
        if not self.position_mgr:
            return []

        closed = self.position_mgr.get_closed_positions(limit=10)

        # Simplify format to avoid circular references
        trade_data = []
        for pos in closed:
            trade_data.append({
                'id': pos.get('position_id'),
                'side': pos.get('side'),
                'entry_price': pos.get('entry_price'),
                'exit_price': pos.get('exit_price'),
                'pnl': pos.get('pnl'),
                'pnl_percent': pos.get('pnl_percent'),
                'exit_reason': pos.get('exit_reason'),
                'hold_duration': pos.get('hold_duration'),
                'closed_at': pos.get('closed_at')
            })

        return trade_data

    def _get_system_status(self) -> Dict:
        """Get system health status"""
        return {
            'last_update': self.last_update,
            'update_count': self.update_count,
            'components': {
                'paper_trader': self.trader is not None,
                'position_manager': self.position_mgr is not None,
                'order_executor': self.executor is not None,
                'risk_manager': self.risk_mgr is not None
            }
        }

    def display(self, clear_screen: bool = True):
        """
        Display dashboard in terminal

        Args:
            clear_screen: Clear terminal before display
        """
        if clear_screen:
            os.system('clear' if os.name != 'nt' else 'cls')

        snapshot = self.get_snapshot()

        print(self._format_dashboard(snapshot))

    def _format_dashboard(self, snapshot: Dict) -> str:
        """Format snapshot as readable dashboard"""

        # Header
        output = f"""
{'='*80}
{'SCALPING STRATEGY v2.0 - REAL-TIME DASHBOARD':^80}
{'='*80}
Last Update: {snapshot['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}
Update Count: {snapshot['system']['update_count']}
{'='*80}

"""

        # Account Section
        account = snapshot['account']
        if account:
            output += f"""
┌─ ACCOUNT STATUS {'─'*60}┐
│ Balance:          ${account['balance']:>10,.2f}     Equity:         ${account['equity']:>10,.2f} │
│ Available:        ${account['available']:>10,.2f}     Margin Used:    ${account['margin_used']:>10,.2f} │
│ Unrealized P&L:   ${account['unrealized_pnl']:>10,.2f}     Total P&L:      ${account['total_pnl']:>+10,.2f} │
│ Total Return:     {account['total_return_percent']:>9,.2f}%     Max Drawdown:   {account['max_drawdown']:>9,.2f}% │
└{'─'*78}┘

"""

        # Positions Section
        positions = snapshot['positions']
        output += f"""
┌─ OPEN POSITIONS ({len(positions)}) {'─'*58}┐
"""
        if positions:
            for pos in positions:
                pnl_sign = '+' if pos['pnl'] >= 0 else ''
                output += f"""│ {pos['id']:<25} {pos['side']:<5} {pos['symbol']}
│   Entry: ${pos['entry_price']:>10,.2f}  Current: ${pos['current_price']:>10,.2f}  Qty: {pos['quantity']:.5f} BTC
│   SL: ${pos['stop_loss']:>10,.2f}  TP: ${pos['take_profit']:>10,.2f}  P&L: {pnl_sign}${abs(pos['pnl']):>8,.2f} ({pnl_sign}{pos['pnl_percent']:.2f}%)
│   Hold: {pos['hold_duration']:.1f}m  Margin: ${pos['margin_required']:.2f}
│ {'─'*76}
"""
        else:
            output += "│ No open positions\n"

        output += f"└{'─'*78}┘\n\n"

        # Risk Status Section
        risk = snapshot['risk']
        if risk:
            breaker_status = '🚨 ACTIVE' if risk['circuit_breaker_active'] else '✅ Inactive'
            trade_status = '✅ YES' if risk['can_trade'] else '❌ NO'

            output += f"""
┌─ RISK CONTROLS {'─'*63}┐
│ Daily P&L:        ${risk['daily_pnl']:>+9,.2f} ({risk['daily_loss_percent']:>+6.2f}% / {risk['daily_loss_limit']:.2f}% limit)
│   Remaining:      {risk['daily_loss_remaining']:>9.2f}%
│
│ Drawdown:         {risk['drawdown_percent']:>9.2f}% / {risk['drawdown_limit']:.2f}% limit
│
│ Positions:        {risk['open_positions']:>2} / {risk['max_positions']} (max)
│ Consecutive Loss: {risk['consecutive_losses']:>2} / {risk['consecutive_loss_limit']} (max)
│
│ Circuit Breaker:  {breaker_status}
"""
            if risk['circuit_breaker_active']:
                output += f"│   Reason: {risk['circuit_breaker_reason']}\n"

            output += f"│ Can Trade:        {trade_status}\n"
            output += f"└{'─'*78}┘\n\n"

        # Recent Trades Section
        trades = snapshot['recent_trades']
        output += f"""
┌─ RECENT TRADES (Last {len(trades)}) {'─'*57}┐
"""
        if trades:
            for trade in trades:
                pnl_sign = '+' if trade['pnl'] >= 0 else ''
                emoji = '✅' if trade['pnl'] > 0 else '❌'
                # Format timestamp with date and time
                from datetime import datetime
                closed_time = trade['closed_at']
                if isinstance(closed_time, str):
                    closed_time = datetime.fromisoformat(closed_time)
                time_str = closed_time.strftime('%Y-%m-%d %H:%M:%S')

                # Handle None values safely
                trade_id = str(trade.get('id') or 'N/A')
                pnl = trade.get('pnl') or 0
                pnl_percent = trade.get('pnl_percent') or 0
                entry_price = trade.get('entry_price') or 0
                exit_price = trade.get('exit_price') or 0
                exit_reason = trade.get('exit_reason') or 'UNKNOWN'
                hold_duration = trade.get('hold_duration') or 0

                output += f"""│ {emoji} {trade_id:<25} {trade['side']:<5} {pnl_sign}${abs(pnl):>8,.2f} ({pnl_sign}{pnl_percent:.2f}%)
│    Entry: ${entry_price:>10,.2f} → Exit: ${exit_price:>10,.2f}  Reason: {exit_reason}
│    Hold: {hold_duration:.1f}m  Closed: {time_str}
│ {'─'*76}
"""
        else:
            output += "│ No closed trades yet\n"

        output += f"└{'─'*78}┘\n\n"

        # System Status
        system = snapshot['system']
        components = system['components']

        output += f"""
┌─ SYSTEM STATUS {'─'*63}┐
│ Components:
│   Paper Trader:     {'✅ Online' if components['paper_trader'] else '❌ Offline'}
│   Position Manager: {'✅ Online' if components['position_manager'] else '❌ Offline'}
│   Order Executor:   {'✅ Online' if components['order_executor'] else '❌ Offline'}
│   Risk Manager:     {'✅ Online' if components['risk_manager'] else '❌ Offline'}
└{'─'*78}┘

{'='*80}
"""

        return output

    def get_status_bar(self) -> str:
        """Get compact status bar (one-line summary)"""
        snapshot = self.get_snapshot()

        account = snapshot['account']
        risk = snapshot['risk']
        positions = snapshot['positions']

        balance = account.get('balance', 0)
        pnl = account.get('total_pnl', 0)
        pnl_pct = account.get('total_return_percent', 0)
        open_pos = len(positions)

        pnl_sign = '+' if pnl >= 0 else ''
        status = '✅' if risk.get('can_trade', False) else '🚨'

        return (f"{status} Balance: ${balance:.2f} | P&L: {pnl_sign}${pnl:.2f} ({pnl_sign}{pnl_pct:.2f}%) | "
                f"Positions: {open_pos} | Circuit: {'ACTIVE' if risk.get('circuit_breaker_active') else 'OK'}")

    def export_snapshot(self, filepath: str):
        """Export current snapshot to JSON file"""
        import json

        snapshot = self.get_snapshot()

        # Convert datetime objects to strings
        def serialize(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        with open(filepath, 'w') as f:
            json.dump(snapshot, f, default=serialize, indent=2)

        logger.info(f"Snapshot exported to {filepath}")

    def watch(self, duration_seconds: int = 60, interval: int = None):
        """
        Watch mode - continuous monitoring

        Args:
            duration_seconds: How long to watch (seconds)
            interval: Refresh interval (uses default if None)
        """
        import time

        interval = interval or self.refresh_interval
        iterations = duration_seconds // interval

        logger.info(f"Starting watch mode: {duration_seconds}s, refresh every {interval}s")

        try:
            for i in range(iterations):
                self.display(clear_screen=True)
                print(f"\nRefreshing in {interval}s... (Ctrl+C to stop)")
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\nWatch mode stopped by user")

        print("\n✅ Watch mode complete")


if __name__ == "__main__":
    # Test script
    from src.execution.paper_trader import PaperTrader
    from src.execution.position_manager import PositionManager
    from src.execution.order_executor import OrderExecutor
    from src.risk.risk_manager import RiskManager

    print("Testing Dashboard...")

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

    # Initialize dashboard
    dashboard = Dashboard(
        paper_trader=trader,
        position_manager=position_mgr,
        order_executor=executor,
        risk_manager=risk_mgr
    )

    print("\n1. Empty Dashboard")
    dashboard.display(clear_screen=False)

    # Execute some trades
    print("\n2. Executing test trades...")

    from src.risk.position_sizer import PositionSizer
    sizer = PositionSizer(initial_capital=100.0, leverage=5)

    # Trade 1: LONG
    signal_1 = {
        'signal_id': 'TEST_001',
        'side': 'LONG',
        'confidence': 0.85,
        'stop_loss': 111500,
        'take_profit': 113000
    }
    pos_size_1 = sizer.calculate_position_size(112000, 111500)
    trader.execute_signal(signal_1, 112000, pos_size_1)

    # Trade 2: SHORT
    signal_2 = {
        'signal_id': 'TEST_002',
        'side': 'SHORT',
        'confidence': 0.75,
        'stop_loss': 113500,
        'take_profit': 112000
    }
    pos_size_2 = sizer.calculate_position_size(113000, 113500)
    trader.execute_signal(signal_2, 113000, pos_size_2)

    print("\n3. Dashboard with Open Positions")
    dashboard.display(clear_screen=False)

    # Update positions
    trader.monitor_positions(112500)
    trader.monitor_positions(113000)

    print("\n4. Dashboard with Updated Positions")
    dashboard.display(clear_screen=False)

    # Status bar
    print("\n5. Status Bar")
    print(dashboard.get_status_bar())

    # Export snapshot
    print("\n6. Exporting snapshot...")
    dashboard.export_snapshot('/tmp/dashboard_snapshot.json')
    print("✅ Snapshot exported to /tmp/dashboard_snapshot.json")

    print("\n✅ Dashboard test complete!")
