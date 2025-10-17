#!/usr/bin/env python3
"""
Paper Trading Simulator for ADX Strategy v2.0
Simulates realistic trading with virtual balance, slippage, and fees
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from typing import Dict, Optional, List
from datetime import datetime
import logging

from src.persistence.trade_database import TradeDatabase

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PaperTrader:
    """
    Paper Trading Simulator

    Features:
    - Virtual balance tracking
    - Realistic slippage simulation
    - Trading fee calculation
    - Full trade lifecycle
    - Integration with OrderExecutor + PositionManager
    - Performance metrics
    """

    def __init__(self,
                 initial_balance: float = 100.0,
                 leverage: int = 5,
                 taker_fee_percent: float = 0.05,
                 maker_fee_percent: float = 0.02,
                 slippage_percent: float = 0.02,
                 order_executor=None,
                 position_manager=None,
                 risk_manager=None):
        """
        Initialize paper trader

        Args:
            initial_balance: Starting balance in USDT
            leverage: Leverage multiplier
            taker_fee_percent: Taker fee (market orders)
            maker_fee_percent: Maker fee (limit orders)
            slippage_percent: Average slippage %
            order_executor: OrderExecutor instance
            position_manager: PositionManager instance
            risk_manager: RiskManager instance
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.leverage = leverage
        self.taker_fee_percent = taker_fee_percent / 100
        self.maker_fee_percent = maker_fee_percent / 100
        self.slippage_percent = slippage_percent / 100

        self.executor = order_executor
        self.position_manager = position_manager
        self.risk_manager = risk_manager

        # Trading history
        self.trade_history = []
        self.balance_history = [{'timestamp': datetime.now(), 'balance': initial_balance}]

        # Statistics
        self.total_fees_paid = 0.0
        self.total_slippage_cost = 0.0
        self.peak_balance = initial_balance
        self.max_drawdown = 0.0

        # Database for persistent trade storage
        try:
            self.trade_db = TradeDatabase()
            logger.info("✅ Trade database initialized")

            # Restore balance from database if trades exist
            stats = self.trade_db.get_performance_stats()
            if stats['total_trades'] > 0:
                # Calculate actual balance from database
                restored_balance = initial_balance + stats['total_pnl']
                self.balance = restored_balance
                self.peak_balance = max(initial_balance, restored_balance)
                logger.info(f"💾 Restored balance from database: ${restored_balance:.2f} "
                           f"({stats['total_trades']} trades, ${stats['total_pnl']:.2f} P&L)")

        except Exception as e:
            logger.warning(f"⚠️ Could not initialize trade database: {e}")
            self.trade_db = None

        logger.info(f"📊 Paper Trader initialized: ${self.balance:.2f} @ {leverage}× leverage")

    def execute_signal(self,
                      signal: Dict,
                      current_price: float,
                      position_size_data: Dict) -> Optional[Dict]:
        """
        Execute trading signal in paper trading mode

        Args:
            signal: Signal dictionary from signal generator
            current_price: Current market price
            position_size_data: Position sizing from position_sizer

        Returns:
            Trade result dictionary or None if rejected
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 Executing Paper Trade Signal")
        logger.info(f"{'='*60}")

        # Pre-trade validation with risk manager
        if self.risk_manager:
            can_trade, reason = self.risk_manager.can_open_position()
            if not can_trade:
                logger.warning(f"❌ Trade rejected by risk manager: {reason}")
                return None

            is_valid, warnings = self.risk_manager.validate_trade_risk(position_size_data)
            if not is_valid:
                logger.warning(f"❌ Trade failed risk validation:")
                for warning in warnings:
                    logger.warning(f"   - {warning}")
                return None

        # Check available balance
        margin_required = position_size_data['margin_required']
        if margin_required > self.balance * 0.8:  # Max 80% margin usage
            logger.warning(f"❌ Insufficient balance: Need ${margin_required:.2f}, Have ${self.balance:.2f}")
            return None

        # Calculate entry with slippage
        side = signal['side']
        entry_price = self._apply_slippage(current_price, side, 'entry')

        # Calculate fees
        notional_value = position_size_data['position_size_usd']
        fee = notional_value * self.taker_fee_percent

        logger.info(f"Signal: {side} @ ${current_price:,.2f}")
        logger.info(f"Entry (with slippage): ${entry_price:,.2f}")
        logger.info(f"Position size: {position_size_data['position_size_btc']:.5f} BTC (${notional_value:,.2f})")
        logger.info(f"Margin required: ${margin_required:.2f}")
        logger.info(f"Fee: ${fee:.2f}")

        # Place order via executor
        order_result = None
        if self.executor:
            order_result = self.executor.place_market_order(
                side=side,
                quantity=position_size_data['position_size_btc'],
                metadata={'signal_id': signal.get('signal_id'), 'confidence': signal.get('confidence')}
            )

        # Open position via position manager
        position = None
        if self.position_manager:
            position = self.position_manager.open_position(
                side=side,
                entry_price=entry_price,
                quantity=position_size_data['position_size_btc'],
                stop_loss=signal['stop_loss'],
                take_profit=signal['take_profit'],
                leverage=self.leverage,
                margin_required=margin_required,
                signal_data=signal,
                order_id=order_result['order_id'] if order_result else None
            )

        # Deduct margin and fees from balance
        self.balance -= (margin_required + fee)
        self.total_fees_paid += fee
        self._update_balance_history()

        # Register with risk manager
        if self.risk_manager:
            self.risk_manager.add_open_position(
                position['position_id'] if position else 'unknown',
                position_size_data
            )

        # Record trade
        trade_record = {
            'timestamp': datetime.now(),
            'signal': signal,
            'position': position,
            'order': order_result,
            'entry_price': entry_price,
            'fee': fee,
            'margin_used': margin_required,
            'balance_after': self.balance
        }
        self.trade_history.append(trade_record)

        logger.info(f"✅ Trade executed successfully")
        logger.info(f"Balance: ${self.balance:.2f} (margin locked: ${margin_required:.2f})")
        logger.info(f"{'='*60}\n")

        return trade_record

    def close_position(self,
                      position_id: str,
                      current_price: float,
                      exit_reason: str = 'MANUAL') -> Optional[Dict]:
        """
        Close position in paper trading mode

        Args:
            position_id: Position ID to close
            current_price: Current market price
            exit_reason: Reason for exit

        Returns:
            Exit result dictionary
        """
        if not self.position_manager:
            logger.warning("No position manager available")
            return None

        position = self.position_manager.get_position(position_id)
        if not position:
            logger.warning(f"Position {position_id} not found")
            return None

        logger.info(f"\n{'='*60}")
        logger.info(f"🔒 Closing Position: {position_id}")
        logger.info(f"{'='*60}")

        # Calculate exit with slippage
        # For exits, slippage works opposite (SELL if was LONG, BUY if was SHORT)
        exit_side = 'SELL' if position['side'] == 'LONG' else 'BUY'
        exit_price = self._apply_slippage(current_price, exit_side, 'exit')

        # Calculate exit fee
        notional_value = position['quantity'] * exit_price
        fee = notional_value * self.taker_fee_percent

        logger.info(f"Exit price (with slippage): ${exit_price:,.2f}")
        logger.info(f"Exit reason: {exit_reason}")

        # Close position via position manager
        closed_position = self.position_manager.close_position(
            position_id=position_id,
            exit_price=exit_price,
            exit_reason=exit_reason
        )

        # Calculate P&L
        pnl = closed_position['pnl']
        margin_returned = position['margin_required']

        # Update balance
        self.balance += (margin_returned + pnl - fee)
        self.total_fees_paid += fee
        self._update_balance_history()

        # Update peak and drawdown
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance

        drawdown = self.peak_balance - self.balance
        drawdown_percent = (drawdown / self.peak_balance) * 100

        if drawdown_percent > self.max_drawdown:
            self.max_drawdown = drawdown_percent

        # Update risk manager
        if self.risk_manager:
            self.risk_manager.remove_open_position(position_id)

            outcome = 'WIN' if pnl > 0 else 'LOSS' if pnl < 0 else 'BREAKEVEN'
            self.risk_manager.record_trade_result(pnl, outcome)
            self.risk_manager.update_capital(self.balance)

        logger.info(f"P&L: ${pnl:.2f} ({closed_position['pnl_percent']:+.2f}%)")
        logger.info(f"Fee: ${fee:.2f}")
        logger.info(f"Balance: ${self.balance:.2f}")
        logger.info(f"{'='*60}\n")

        exit_record = {
            'timestamp': datetime.now(),
            'position_id': position_id,
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'pnl': pnl,
            'fee': fee,
            'balance_after': self.balance
        }

        # Save closed trade to database
        if self.trade_db:
            try:
                self.trade_db.save_trade(closed_position)
                logger.info(f"💾 Trade saved to database: {position_id}")
            except Exception as e:
                logger.warning(f"⚠️  Could not save trade to database: {e}")

        return exit_record

    def monitor_positions(self, current_price: float):
        """
        Monitor open positions and check exit conditions

        Args:
            current_price: Current market price
        """
        if not self.position_manager:
            return

        open_positions = self.position_manager.get_open_positions()

        for position in open_positions:
            # Update position with current price
            self.position_manager.update_position_price(
                position['position_id'],
                current_price
            )

            # Check if SL/TP hit
            should_exit, reason = self.position_manager.check_exit_conditions(
                position['position_id'],
                current_price
            )

            if should_exit:
                logger.info(f"🎯 Exit condition triggered: {reason}")
                self.close_position(position['position_id'], current_price, reason)

    def _apply_slippage(self, price: float, side: str, order_type: str) -> float:
        """
        Apply realistic slippage to price

        Args:
            price: Base price
            side: BUY or SELL
            order_type: entry or exit

        Returns:
            Price with slippage
        """
        import random

        # Random slippage between 0 and max slippage
        slippage = random.uniform(0, self.slippage_percent)

        # BUY = pay more, SELL = receive less
        if side == 'BUY':
            slipped_price = price * (1 + slippage)
        else:
            slipped_price = price * (1 - slippage)

        slippage_cost = abs(slipped_price - price) * (1 if side == 'BUY' else -1)
        self.total_slippage_cost += slippage_cost

        return slipped_price

    def _update_balance_history(self):
        """Update balance history"""
        self.balance_history.append({
            'timestamp': datetime.now(),
            'balance': self.balance
        })

    def get_account_status(self) -> Dict:
        """Get current account status"""
        open_positions = self.position_manager.get_open_positions() if self.position_manager else []
        total_margin_used = sum(p['margin_required'] for p in open_positions)
        available_balance = self.balance
        total_equity = self.balance + sum(p.get('unrealized_pnl', 0) for p in open_positions)

        return {
            'balance': round(self.balance, 2),
            'equity': round(total_equity, 2),
            'available_balance': round(available_balance, 2),
            'margin_used': round(total_margin_used, 2),
            'margin_available': round(self.balance - total_margin_used, 2),
            'open_positions': len(open_positions),
            'unrealized_pnl': round(sum(p.get('unrealized_pnl', 0) for p in open_positions), 2)
        }

    def get_performance_stats(self) -> Dict:
        """Get performance statistics"""
        total_pnl = self.balance - self.initial_balance
        total_return_percent = (total_pnl / self.initial_balance) * 100

        position_stats = self.position_manager.get_position_stats() if self.position_manager else {}

        return {
            'initial_balance': round(self.initial_balance, 2),
            'current_balance': round(self.balance, 2),
            'total_pnl': round(total_pnl, 2),
            'total_return_percent': round(total_return_percent, 2),
            'peak_balance': round(self.peak_balance, 2),
            'max_drawdown_percent': round(self.max_drawdown, 2),
            'total_fees_paid': round(self.total_fees_paid, 2),
            'total_slippage_cost': round(self.total_slippage_cost, 2),
            'total_trades': len(self.trade_history),
            'win_rate': position_stats.get('win_rate', 0),
            'profit_factor': position_stats.get('profit_factor', 0)
        }

    def get_paper_trading_summary(self) -> str:
        """Generate human-readable paper trading summary"""
        account = self.get_account_status()
        perf = self.get_performance_stats()
        risk_status = self.risk_manager.get_risk_status() if self.risk_manager else {}

        return f"""
{'='*60}
Paper Trading Account Summary
{'='*60}
Account Status:
  Balance:          ${account['balance']:,.2f}
  Equity:           ${account['equity']:,.2f}
  Margin Used:      ${account['margin_used']:,.2f}
  Available:        ${account['margin_available']:,.2f}
  Open Positions:   {account['open_positions']}
  Unrealized P&L:   ${account['unrealized_pnl']:+,.2f}

Performance:
  Initial Balance:  ${perf['initial_balance']:,.2f}
  Current Balance:  ${perf['current_balance']:,.2f}
  Total P&L:        ${perf['total_pnl']:+,.2f} ({perf['total_return_percent']:+.2f}%)
  Peak Balance:     ${perf['peak_balance']:,.2f}
  Max Drawdown:     {perf['max_drawdown_percent']:.2f}%

Costs:
  Fees Paid:        ${perf['total_fees_paid']:,.2f}
  Slippage Cost:    ${perf['total_slippage_cost']:,.2f}
  Total Costs:      ${perf['total_fees_paid'] + perf['total_slippage_cost']:,.2f}

Trading Stats:
  Total Trades:     {perf['total_trades']}
  Win Rate:         {perf['win_rate']:.1f}%
  Profit Factor:    {perf['profit_factor']:.2f}

Risk Controls:
  Daily Loss:       {risk_status.get('daily_loss_percent', 0):.2f}% / {risk_status.get('daily_loss_limit', 5):.2f}%
  Drawdown:         {risk_status.get('drawdown_percent', 0):.2f}% / {risk_status.get('drawdown_limit', 15):.2f}%
  Circuit Breaker:  {'🚨 ACTIVE' if risk_status.get('circuit_breaker_active') else '✅ Inactive'}
{'='*60}
"""

    def reset_account(self):
        """Reset paper trading account to initial state"""
        logger.warning("🔄 Resetting paper trading account...")

        self.balance = self.initial_balance
        self.trade_history = []
        self.balance_history = [{'timestamp': datetime.now(), 'balance': self.initial_balance}]
        self.total_fees_paid = 0.0
        self.total_slippage_cost = 0.0
        self.peak_balance = self.initial_balance
        self.max_drawdown = 0.0

        if self.position_manager:
            # Close all positions
            open_pos = self.position_manager.get_open_positions()
            for pos in open_pos:
                self.position_manager.close_position(pos['position_id'], pos['entry_price'], 'RESET')

        if self.risk_manager:
            self.risk_manager.update_capital(self.initial_balance)
            self.risk_manager.reset_daily_tracking()
            if self.risk_manager.circuit_breaker_active:
                self.risk_manager.deactivate_circuit_breaker()

        logger.info("✅ Account reset complete")


if __name__ == "__main__":
    # Test script
    from src.execution.order_executor import OrderExecutor
    from src.execution.position_manager import PositionManager
    from src.risk.risk_manager import RiskManager

    print("Testing Paper Trader...")

    # Initialize components
    executor = OrderExecutor(enable_live_trading=False)
    position_mgr = PositionManager(order_executor=executor)
    risk_mgr = RiskManager(initial_capital=100.0)

    # Initialize paper trader
    trader = PaperTrader(
        initial_balance=100.0,
        leverage=5,
        order_executor=executor,
        position_manager=position_mgr,
        risk_manager=risk_mgr
    )

    print("\n1. Initial Account Status")
    print(trader.get_paper_trading_summary())

    # Test 2: Execute signal
    print("\n2. Executing trade signal")
    signal = {
        'signal_id': 'TEST_001',
        'side': 'LONG',
        'confidence': 0.85,
        'stop_loss': 111500,
        'take_profit': 113000
    }

    position_size = {
        'position_size_btc': 0.00089,
        'position_size_usd': 100.0,
        'margin_required': 20.0,
        'risk_amount': 2.0,
        'actual_risk_percent': 2.0,
        'is_valid': True
    }

    trade = trader.execute_signal(signal, 112000, position_size)

    print("\n3. Monitoring position")
    # Simulate price movement
    prices = [112100, 112300, 112500, 112800, 113000]

    for price in prices:
        trader.monitor_positions(price)
        print(f"   Price: ${price:,.2f}")

    print("\n4. Final Account Status")
    print(trader.get_paper_trading_summary())

    print("\n✅ Paper Trader test complete!")
