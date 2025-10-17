#!/usr/bin/env python3
"""
Position Manager for ADX Strategy v2.0
Tracks open positions, monitors SL/TP, handles position lifecycle
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from typing import Dict, Optional, List
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PositionManager:
    """
    Position Management System

    Features:
    - Open position tracking
    - Stop loss / Take profit monitoring
    - Position P&L calculation
    - Breakeven adjustment
    - Trailing stop logic
    - Position closure
    """

    def __init__(self,
                 order_executor=None,
                 enable_trailing_stop: bool = False,
                 trailing_stop_activation: float = 0.5,
                 trailing_stop_distance: float = 0.3):
        """
        Initialize position manager

        Args:
            order_executor: OrderExecutor instance
            enable_trailing_stop: Enable trailing stop loss
            trailing_stop_activation: % profit to activate trailing (0.5% default)
            trailing_stop_distance: % distance for trailing stop (0.3% default)
        """
        self.executor = order_executor
        self.enable_trailing_stop = enable_trailing_stop
        self.trailing_stop_activation = trailing_stop_activation
        self.trailing_stop_distance = trailing_stop_distance

        # Position tracking
        self.open_positions = {}
        self.closed_positions = {}
        self.position_id_counter = 5000

        # Statistics
        self.total_positions = 0
        self.winning_positions = 0
        self.losing_positions = 0
        self.total_pnl = 0.0

        logger.info("Position Manager initialized")

    def generate_position_id(self) -> str:
        """Generate unique position ID"""
        position_id = f"POS_{self.position_id_counter}_{int(datetime.now().timestamp())}"
        self.position_id_counter += 1
        return position_id

    def open_position(self,
                     side: str,
                     entry_price: float,
                     quantity: float,
                     stop_loss: float,
                     take_profit: float,
                     symbol: str = "BTC-USDT",
                     leverage: int = 5,
                     margin_required: float = 0,
                     signal_data: Optional[Dict] = None,
                     order_id: Optional[str] = None) -> Dict:
        """
        Open new position

        Args:
            side: LONG or SHORT
            entry_price: Entry price
            quantity: Position size in BTC
            stop_loss: Stop loss price
            take_profit: Take profit price
            symbol: Trading symbol
            leverage: Leverage multiplier
            margin_required: Margin amount
            signal_data: Signal metadata
            order_id: Associated order ID

        Returns:
            Position dictionary
        """
        position_id = self.generate_position_id()

        logger.info(f"📈 Opening {side} position: {quantity:.5f} BTC @ ${entry_price:,.2f}")

        position = {
            'position_id': position_id,
            'order_id': order_id,
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'quantity': quantity,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'current_price': entry_price,
            'leverage': leverage,
            'margin_required': margin_required,
            'opened_at': datetime.now(),
            'status': 'OPEN',
            'pnl': 0.0,
            'pnl_percent': 0.0,
            'unrealized_pnl': 0.0,
            'highest_price': entry_price if side == 'LONG' else None,
            'lowest_price': entry_price if side == 'SHORT' else None,
            'trailing_stop_active': False,
            'signal_data': signal_data or {},
            'hold_duration': 0,
            'exit_reason': None
        }

        self.open_positions[position_id] = position
        self.total_positions += 1

        # Place SL/TP orders if executor provided
        if self.executor:
            self._place_sl_tp_orders(position)

        logger.info(f"   SL: ${stop_loss:,.2f}, TP: ${take_profit:,.2f}")
        logger.info(f"   Margin: ${margin_required:,.2f} ({leverage}× leverage)")

        return position

    def _place_sl_tp_orders(self, position: Dict):
        """Place stop loss and take profit orders"""
        try:
            # Place stop loss
            sl_order = self.executor.place_stop_loss_order(
                position_id=position['position_id'],
                stop_price=position['stop_loss'],
                quantity=position['quantity'],
                symbol=position['symbol']
            )
            position['sl_order_id'] = sl_order['order_id']

            # Place take profit
            tp_order = self.executor.place_take_profit_order(
                position_id=position['position_id'],
                take_profit_price=position['take_profit'],
                quantity=position['quantity'],
                symbol=position['symbol']
            )
            position['tp_order_id'] = tp_order['order_id']

            logger.info(f"   ✅ SL/TP orders placed: {sl_order['order_id']}, {tp_order['order_id']}")

        except Exception as e:
            logger.error(f"   ❌ Failed to place SL/TP orders: {e}")

    def update_position_price(self, position_id: str, current_price: float):
        """
        Update position with current market price

        Args:
            position_id: Position ID
            current_price: Current market price
        """
        if position_id not in self.open_positions:
            return

        position = self.open_positions[position_id]
        position['current_price'] = current_price

        # Calculate unrealized P&L
        self._calculate_pnl(position)

        # Track highest/lowest prices
        if position['side'] == 'LONG':
            if position['highest_price'] is None or current_price > position['highest_price']:
                position['highest_price'] = current_price
        else:  # SHORT
            if position['lowest_price'] is None or current_price < position['lowest_price']:
                position['lowest_price'] = current_price

        # Check trailing stop
        if self.enable_trailing_stop:
            self._check_trailing_stop(position)

        # Update hold duration
        position['hold_duration'] = (datetime.now() - position['opened_at']).total_seconds() / 60

    def _calculate_pnl(self, position: Dict):
        """Calculate position P&L"""
        entry = position['entry_price']
        current = position['current_price']
        quantity = position['quantity']
        side = position['side']

        if side == 'LONG':
            price_change = current - entry
        else:  # SHORT
            price_change = entry - current

        # P&L in USDT
        pnl = price_change * quantity
        pnl_percent = (price_change / entry) * 100

        # Account for leverage
        pnl_with_leverage = pnl * position['leverage']
        pnl_percent_with_leverage = pnl_percent * position['leverage']

        position['unrealized_pnl'] = pnl_with_leverage
        position['pnl'] = pnl_with_leverage
        position['pnl_percent'] = pnl_percent_with_leverage

    def _check_trailing_stop(self, position: Dict):
        """Check and update trailing stop"""
        if position['trailing_stop_active']:
            return

        # Check if profit reached activation threshold
        if position['pnl_percent'] >= self.trailing_stop_activation:
            logger.info(f"🔄 Activating trailing stop for {position['position_id']}")
            position['trailing_stop_active'] = True

            # Adjust stop loss to trailing distance
            if position['side'] == 'LONG':
                new_sl = position['current_price'] * (1 - self.trailing_stop_distance / 100)
            else:
                new_sl = position['current_price'] * (1 + self.trailing_stop_distance / 100)

            position['stop_loss'] = new_sl
            logger.info(f"   New trailing SL: ${new_sl:,.2f}")

    def check_exit_conditions(self, position_id: str, current_price: float) -> tuple[bool, Optional[str]]:
        """
        Check if position should be closed

        Args:
            position_id: Position ID
            current_price: Current market price

        Returns:
            (should_close, reason) tuple
        """
        if position_id not in self.open_positions:
            return False, None

        position = self.open_positions[position_id]
        side = position['side']
        sl = position['stop_loss']
        tp = position['take_profit']

        # Check stop loss hit
        if side == 'LONG' and current_price <= sl:
            return True, 'STOP_LOSS'
        elif side == 'SHORT' and current_price >= sl:
            return True, 'STOP_LOSS'

        # Check take profit hit
        if side == 'LONG' and current_price >= tp:
            return True, 'TAKE_PROFIT'
        elif side == 'SHORT' and current_price <= tp:
            return True, 'TAKE_PROFIT'

        return False, None

    def close_position(self,
                      position_id: str,
                      exit_price: float,
                      exit_reason: str = 'MANUAL',
                      exit_order_id: Optional[str] = None) -> Dict:
        """
        Close open position

        Args:
            position_id: Position ID
            exit_price: Exit price
            exit_reason: Reason for exit (STOP_LOSS, TAKE_PROFIT, MANUAL, TIMEOUT)
            exit_order_id: Associated exit order ID

        Returns:
            Closed position dictionary
        """
        if position_id not in self.open_positions:
            logger.warning(f"⚠️  Position {position_id} not found")
            return None

        position = self.open_positions[position_id]

        logger.info(f"🔒 Closing {position['side']} position: {position_id}")
        logger.info(f"   Exit: ${exit_price:,.2f}, Reason: {exit_reason}")

        # Calculate final P&L
        position['current_price'] = exit_price
        self._calculate_pnl(position)

        # Update position
        position['exit_price'] = exit_price
        position['exit_reason'] = exit_reason
        position['exit_order_id'] = exit_order_id
        position['closed_at'] = datetime.now()
        position['status'] = 'CLOSED'
        position['hold_duration'] = (position['closed_at'] - position['opened_at']).total_seconds() / 60

        # Update statistics
        if position['pnl'] > 0:
            self.winning_positions += 1
            logger.info(f"   ✅ WIN: +${position['pnl']:.2f} (+{position['pnl_percent']:.2f}%)")
        else:
            self.losing_positions += 1
            logger.info(f"   ❌ LOSS: ${position['pnl']:.2f} ({position['pnl_percent']:.2f}%)")

        self.total_pnl += position['pnl']

        # Move to closed positions
        self.closed_positions[position_id] = position
        del self.open_positions[position_id]

        # Cancel any remaining SL/TP orders
        if self.executor:
            if 'sl_order_id' in position:
                self.executor.cancel_order(position['sl_order_id'])
            if 'tp_order_id' in position:
                self.executor.cancel_order(position['tp_order_id'])

        logger.info(f"   Hold time: {position['hold_duration']:.1f} minutes")

        return position

    def close_all_positions(self, current_price: float, reason: str = 'EMERGENCY_STOP'):
        """
        Close all open positions (emergency stop)

        Args:
            current_price: Current market price
            reason: Reason for mass closure
        """
        logger.critical(f"🚨 CLOSING ALL POSITIONS: {reason}")

        position_ids = list(self.open_positions.keys())

        for position_id in position_ids:
            self.close_position(position_id, current_price, reason)

        logger.info(f"✅ Closed {len(position_ids)} positions")

    def adjust_stop_loss(self, position_id: str, new_stop_loss: float):
        """
        Adjust stop loss for position (e.g., breakeven)

        Args:
            position_id: Position ID
            new_stop_loss: New stop loss price
        """
        if position_id not in self.open_positions:
            return

        position = self.open_positions[position_id]
        old_sl = position['stop_loss']
        position['stop_loss'] = new_stop_loss

        logger.info(f"🔄 SL adjusted for {position_id}: ${old_sl:,.2f} → ${new_stop_loss:,.2f}")

        # Update SL order if executor provided
        if self.executor and 'sl_order_id' in position:
            # Cancel old SL order
            self.executor.cancel_order(position['sl_order_id'])

            # Place new SL order
            sl_order = self.executor.place_stop_loss_order(
                position_id=position_id,
                stop_price=new_stop_loss,
                quantity=position['quantity'],
                symbol=position['symbol']
            )
            position['sl_order_id'] = sl_order['order_id']

    def move_to_breakeven(self, position_id: str, threshold_percent: float = 0.5):
        """
        Move stop loss to breakeven when profit threshold reached

        Args:
            position_id: Position ID
            threshold_percent: Profit % to trigger breakeven (0.5% default)
        """
        if position_id not in self.open_positions:
            return

        position = self.open_positions[position_id]

        if position['pnl_percent'] >= threshold_percent:
            entry_price = position['entry_price']

            logger.info(f"🎯 Moving to breakeven: {position_id}")
            self.adjust_stop_loss(position_id, entry_price)

    def get_position(self, position_id: str) -> Optional[Dict]:
        """Get position by ID"""
        if position_id in self.open_positions:
            return self.open_positions[position_id]
        elif position_id in self.closed_positions:
            return self.closed_positions[position_id]
        return None

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions"""
        return list(self.open_positions.values())

    def get_closed_positions(self, limit: Optional[int] = None) -> List[Dict]:
        """Get closed positions (optionally limited)"""
        positions = sorted(
            self.closed_positions.values(),
            key=lambda x: x['closed_at'],
            reverse=True
        )
        if limit:
            return positions[:limit]
        return positions

    def get_position_stats(self) -> Dict:
        """Get position statistics"""
        win_rate = (self.winning_positions / self.total_positions * 100) if self.total_positions > 0 else 0

        avg_win = 0
        avg_loss = 0

        if self.winning_positions > 0:
            wins = [p['pnl'] for p in self.closed_positions.values() if p['pnl'] > 0]
            avg_win = sum(wins) / len(wins) if wins else 0

        if self.losing_positions > 0:
            losses = [abs(p['pnl']) for p in self.closed_positions.values() if p['pnl'] < 0]
            avg_loss = sum(losses) / len(losses) if losses else 0

        return {
            'total_positions': self.total_positions,
            'open_positions': len(self.open_positions),
            'closed_positions': len(self.closed_positions),
            'winning_positions': self.winning_positions,
            'losing_positions': self.losing_positions,
            'win_rate': round(win_rate, 2),
            'total_pnl': round(self.total_pnl, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(avg_win / avg_loss, 2) if avg_loss > 0 else 0
        }

    def get_position_summary(self) -> str:
        """Generate human-readable position summary"""
        stats = self.get_position_stats()

        open_positions_str = ""
        if self.open_positions:
            open_positions_str = "\nOpen Positions:\n"
            for pos in self.open_positions.values():
                open_positions_str += f"  {pos['position_id']}: {pos['side']} {pos['quantity']:.5f} BTC @ ${pos['entry_price']:,.2f}\n"
                open_positions_str += f"    P&L: ${pos['pnl']:.2f} ({pos['pnl_percent']:+.2f}%), Hold: {pos['hold_duration']:.1f}m\n"

        return f"""
{'='*60}
Position Manager Summary
{'='*60}
Total Positions:    {stats['total_positions']}
Open:               {stats['open_positions']}
Closed:             {stats['closed_positions']}

Performance:
  Wins:             {stats['winning_positions']}
  Losses:           {stats['losing_positions']}
  Win Rate:         {stats['win_rate']:.1f}%

P&L:
  Total P&L:        ${stats['total_pnl']:,.2f}
  Avg Win:          ${stats['avg_win']:,.2f}
  Avg Loss:         ${stats['avg_loss']:,.2f}
  Profit Factor:    {stats['profit_factor']:.2f}
{open_positions_str}{'='*60}
"""


if __name__ == "__main__":
    # Test script
    print("Testing Position Manager...")

    # Initialize
    pm = PositionManager()

    # Test 1: Open LONG position
    print("\n1. Opening LONG position")
    pos1 = pm.open_position(
        side='LONG',
        entry_price=112000,
        quantity=0.001,
        stop_loss=111500,
        take_profit=113000,
        leverage=5,
        margin_required=22.4,
        signal_data={'adx': 32.5, 'confidence': 0.85}
    )
    print(f"   Position opened: {pos1['position_id']}")
    print(f"   Entry: ${pos1['entry_price']:,.2f}")

    # Test 2: Update with price movement
    print("\n2. Simulating price movement")
    prices = [112100, 112200, 112500, 112800, 113000]

    for price in prices:
        pm.update_position_price(pos1['position_id'], price)
        print(f"   Price: ${price:,.2f}, P&L: ${pos1['pnl']:.2f} ({pos1['pnl_percent']:+.2f}%)")

    # Test 3: Check exit conditions
    print("\n3. Checking exit conditions")
    should_exit, reason = pm.check_exit_conditions(pos1['position_id'], 113000)
    print(f"   Should exit: {should_exit}, Reason: {reason}")

    # Test 4: Close position
    print("\n4. Closing position")
    closed = pm.close_position(pos1['position_id'], 113000, 'TAKE_PROFIT')
    print(f"   Position closed: {closed['position_id']}")
    print(f"   Final P&L: ${closed['pnl']:.2f}")
    print(f"   Hold time: {closed['hold_duration']:.1f} minutes")

    # Test 5: Open SHORT position
    print("\n5. Opening SHORT position")
    pos2 = pm.open_position(
        side='SHORT',
        entry_price=113000,
        quantity=0.001,
        stop_loss=113500,
        take_profit=112000,
        leverage=5,
        margin_required=22.6
    )

    # Simulate loss
    pm.update_position_price(pos2['position_id'], 113400)
    should_exit, reason = pm.check_exit_conditions(pos2['position_id'], 113400)
    print(f"   Should exit: {should_exit}, Reason: {reason}")

    if should_exit:
        pm.close_position(pos2['position_id'], 113400, reason)

    # Test 6: Statistics
    print("\n6. Position Statistics")
    print(pm.get_position_summary())

    print("✅ Position Manager test complete!")
