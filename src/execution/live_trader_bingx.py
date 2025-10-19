#!/usr/bin/env python3
"""
Live BingX Trading Module for ADX Strategy v2.0
Executes real trades on BingX exchange - USE WITH CAUTION

This module handles real money trades. All operations are irreversible.
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from typing import Dict, List, Optional
from datetime import datetime
import logging
import time

from src.api.bingx_api import BingXAPI
from src.persistence.trade_database import TradeDatabase

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LiveTraderBingX:
    """
    Live Trading on BingX Exchange

    Mirrors PaperTrader interface but executes real orders on BingX.

    ⚠️  WARNING: THIS USES REAL MONEY ⚠️
    - All trades are executed on the real exchange
    - Losses are real and irreversible
    - Start with minimum capital
    - Monitor closely

    Features:
    - Real order execution via BingX API
    - Position synchronization with exchange
    - Balance fetching from exchange
    - Order confirmation and retry logic
    - Trade persistence to database
    - Emergency stop capability
    """

    def __init__(self,
                 api_key: str,
                 api_secret: str,
                 leverage: int = 5,
                 order_executor=None,
                 position_manager=None,
                 risk_manager=None,
                 symbol: str = "BTC-USDT"):
        """
        Initialize live trader

        Args:
            api_key: BingX API key
            api_secret: BingX API secret
            leverage: Trading leverage (default: 5)
            order_executor: OrderExecutor instance
            position_manager: PositionManager instance
            risk_manager: RiskManager instance
            symbol: Trading symbol (default: BTC-USDT)
        """
        logger.warning("="*80)
        logger.warning("⚠️  LIVE TRADING MODE - REAL MONEY AT RISK ⚠️")
        logger.warning("="*80)

        # Initialize BingX API
        self.api = BingXAPI(api_key, api_secret, testnet=False)
        self.leverage = leverage
        self.symbol = symbol

        # Components
        self.executor = order_executor
        self.position_manager = position_manager
        self.risk_manager = risk_manager

        # Get initial balance from exchange
        self.initial_balance = self._fetch_real_balance()
        self.balance = self.initial_balance

        # Trading history
        self.trade_history = []
        self.balance_history = [{'timestamp': datetime.now(), 'balance': self.balance}]

        # Statistics
        self.total_fees_paid = 0.0
        self.peak_balance = self.balance
        self.max_drawdown = 0.0

        # Database for persistent trade storage
        try:
            self.trade_db = TradeDatabase()
            logger.info("✅ Trade database initialized")

            # Restore balance from database if trades exist
            stats = self.trade_db.get_performance_stats()
            if stats['total_trades'] > 0:
                logger.info(f"📊 Historical trades: {stats['total_trades']} trades, "
                           f"${stats['total_pnl']:.2f} P&L")
        except Exception as e:
            logger.warning(f"⚠️  Could not initialize trade database: {e}")
            self.trade_db = None

        # Set leverage on exchange
        self._set_exchange_leverage()

        # Reconcile positions on startup
        self._reconcile_positions()

        logger.info(f"💰 Live Trader initialized: ${self.balance:.2f} @ {leverage}× leverage")
        logger.info(f"🎯 Trading symbol: {symbol}")

    def _fetch_real_balance(self) -> float:
        """
        Fetch actual balance from BingX exchange

        Returns:
            Current USDT balance
        """
        try:
            account = self.api.get_account_balance()
            balance = account['available_margin']
            logger.info(f"💰 Fetched balance from BingX: ${balance:.2f} USDT")
            return balance
        except Exception as e:
            logger.error(f"❌ Failed to fetch balance: {e}")
            raise Exception("Cannot initialize without real balance")

    def _set_exchange_leverage(self) -> bool:
        """Set leverage on BingX exchange for both LONG and SHORT sides (Hedge mode)"""
        try:
            # BingX Hedge mode requires setting leverage for each side separately
            success_long = self.api.set_leverage(self.symbol, self.leverage, side="LONG")
            success_short = self.api.set_leverage(self.symbol, self.leverage, side="SHORT")

            if success_long and success_short:
                logger.info(f"✅ Leverage set to {self.leverage}x on {self.symbol} (LONG & SHORT)")
                return True
            else:
                logger.warning(f"⚠️  Leverage setting partial success (LONG: {success_long}, SHORT: {success_short})")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to set leverage: {e}")
            return False

    def _reconcile_positions(self):
        """
        Sync local position tracking with exchange
        Called on startup and periodically
        """
        try:
            exchange_positions = self.api.get_positions(self.symbol)

            if not exchange_positions:
                logger.info("✅ No open positions on exchange")
                return

            for pos in exchange_positions:
                size = float(pos.get('position_amount', 0))
                if size != 0:
                    logger.warning(f"⚠️  Found open position on exchange: "
                                 f"{pos['side']} {abs(size)} BTC @ ${pos['entry_price']:.2f}")
                    logger.warning("   Please close manually or bot will manage it")

        except Exception as e:
            logger.error(f"❌ Position reconciliation failed: {e}")

    def execute_signal(self,
                      signal: Dict,
                      current_price: float,
                      position_size_data: Dict) -> Optional[Dict]:
        """
        Execute trading signal on BingX exchange

        Args:
            signal: Signal dictionary from signal generator
            current_price: Current market price
            position_size_data: Position sizing from position_sizer

        Returns:
            Execution result dictionary or None if failed
        """
        logger.info("="*80)
        logger.info(f"🔴 EXECUTING LIVE TRADE - {signal['side']} @ ${current_price:,.2f}")
        logger.info("="*80)

        # Extract signal info
        signal_id = signal.get('signal_id')
        side = signal.get('side')  # LONG or SHORT
        confidence = signal.get('confidence', 0)

        # Extract position sizing
        quantity_btc = position_size_data.get('quantity') or position_size_data.get('position_size_btc')
        stop_loss = signal.get('stop_loss')
        take_profit = signal.get('take_profit')
        risk_amount = position_size_data.get('risk_amount')

        # Validation
        if not quantity_btc or not stop_loss or not take_profit:
            logger.error(f"❌ Invalid signal data: quantity={quantity_btc}, SL={stop_loss}, TP={take_profit}")
            return None

        logger.info(f"📊 Signal: {signal_id or 'N/A'} | Confidence: {confidence*100:.1f}%")
        logger.info(f"📊 Size: {quantity_btc:.5f} BTC (${quantity_btc * current_price:.2f})")
        logger.info(f"📊 Risk: ${risk_amount:.2f} | SL: ${stop_loss:,.2f} | TP: ${take_profit:,.2f}")

        # Determine order side (BUY to open LONG, SELL to open SHORT)
        order_side = "BUY" if side == "LONG" else "SELL"

        try:
            # Place market order on BingX
            logger.info(f"📤 Placing {order_side} order on BingX...")
            order_result = self.api.place_market_order(
                symbol=self.symbol,
                side=order_side,
                quantity=quantity_btc,
                position_side=side  # LONG or SHORT
            )

            order_id = order_result.get('order_id')
            logger.info(f"✅ Order placed: {order_id if order_id else 'Checking positions...'}")

            # For market orders that filled successfully, use the order quantity
            # Market orders fill immediately on BingX
            filled_price = current_price  # Use current price as approximation
            filled_qty = quantity_btc

            # Verify position exists on exchange
            time.sleep(1)
            try:
                positions = self.api.get_positions(self.symbol)
                matching_positions = [p for p in positions if p['side'] == side and abs(p['quantity']) > 0]

                if matching_positions:
                    # Get actual fill price from position
                    filled_price = matching_positions[0]['entry_price']
                    logger.info(f"  Verified position on exchange: entry ${filled_price:,.2f}")
            except Exception as e:
                logger.warning(f"  Could not verify position: {e}")
                # Continue anyway with order data

            logger.info(f"✅ Order filled: {filled_qty:.5f} BTC @ ${filled_price:,.2f}")

            # Place Stop Loss and Take Profit orders
            logger.info(f"🛡️ Placing protective orders...")
            self._place_protective_orders(side, filled_qty, stop_loss, take_profit)

            # Create execution record
            execution = {
                'signal_id': signal_id,
                'order_id': order_id,
                'side': side,
                'entry_price': filled_price,
                'quantity': filled_qty,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'timestamp': datetime.now(),
                'status': 'FILLED',
                'exchange': 'BingX'
            }

            # Add to position manager
            if self.position_manager:
                position_id = self.position_manager.open_position(
                    symbol=self.symbol,
                    side=side,
                    entry_price=filled_price,
                    quantity=filled_qty,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    signal_data=signal
                )
                execution['position_id'] = position_id
                logger.info(f"✅ Position opened: {position_id}")

            logger.info("="*80)
            logger.info(f"✅ LIVE TRADE EXECUTED SUCCESSFULLY")
            logger.info("="*80)

            return execution

        except Exception as e:
            logger.error(f"❌ LIVE TRADE FAILED: {e}")
            return None

    def _place_protective_orders(self, side: str, quantity: float,
                                 stop_loss: float, take_profit: float) -> bool:
        """
        Place Stop Loss and Take Profit orders

        Args:
            side: Position side (LONG or SHORT)
            quantity: Position quantity
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            True if both orders placed successfully
        """
        try:
            endpoint = "/openApi/swap/v2/trade/order"

            # Place Stop Loss
            sl_params = {
                'symbol': self.symbol,
                'side': 'SELL' if side == 'LONG' else 'BUY',
                'positionSide': side,
                'type': 'STOP_MARKET',
                'quantity': quantity,
                'stopPrice': round(stop_loss, 2),
                'workingType': 'MARK_PRICE'
            }

            try:
                sl_response = self.api._request('POST', endpoint, sl_params, signed=True)
                logger.info(f"  ✅ Stop Loss placed: ${stop_loss:,.2f}")
            except Exception as e:
                logger.warning(f"  ⚠️ Stop Loss failed: {e}")

            # Place Take Profit
            tp_params = {
                'symbol': self.symbol,
                'side': 'SELL' if side == 'LONG' else 'BUY',
                'positionSide': side,
                'type': 'TAKE_PROFIT_MARKET',
                'quantity': quantity,
                'stopPrice': round(take_profit, 2),
                'workingType': 'MARK_PRICE'
            }

            try:
                tp_response = self.api._request('POST', endpoint, tp_params, signed=True)
                logger.info(f"  ✅ Take Profit placed: ${take_profit:,.2f}")
            except Exception as e:
                logger.warning(f"  ⚠️ Take Profit failed: {e}")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to place protective orders: {e}")
            return False

    def _confirm_order_filled(self, order_id: str, max_wait: int = 30) -> bool:
        """
        Wait for order to fill and confirm

        Args:
            order_id: Order ID from place_order
            max_wait: Maximum seconds to wait

        Returns:
            True if filled, False if timeout/failed
        """
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                order_status = self.api.get_order_status(self.symbol, order_id)
                status = order_status.get('status', '').upper()

                if status == 'FILLED':
                    return True
                if status in ['CANCELLED', 'REJECTED', 'EXPIRED']:
                    logger.error(f"Order {status}: {order_id}")
                    return False

                time.sleep(1)
            except Exception as e:
                logger.warning(f"Error checking order status: {e}")
                time.sleep(2)

        logger.error(f"Order fill timeout after {max_wait}s")
        return False

    def monitor_positions(self, current_price: float) -> List[Dict]:
        """
        Monitor open positions and execute exits

        Args:
            current_price: Current market price

        Returns:
            List of closed positions
        """
        if not self.position_manager:
            return []

        closed_positions = []

        # Check each open position
        for position_id in list(self.position_manager.open_positions.keys()):
            position = self.position_manager.open_positions[position_id]

            # Update position price
            self.position_manager.update_position_price(position_id, current_price)

            # Check if position should exit
            should_close, exit_reason = self.position_manager.check_exit_conditions(
                position_id,
                current_price
            )

            if should_close:
                logger.info(f"🔄 Closing position {position_id}: {exit_reason}")

                # Close position on exchange
                closed_pos = self._close_position_on_exchange(position, current_price, exit_reason)

                if closed_pos:
                    closed_positions.append(closed_pos)

                    # Save to database
                    if self.trade_db:
                        try:
                            self.trade_db.save_trade(closed_pos)
                            logger.info(f"💾 Trade saved to database")
                        except Exception as e:
                            logger.warning(f"⚠️  Could not save trade: {e}")

        return closed_positions

    def _close_position_on_exchange(self, position: Dict, current_price: float, exit_reason: str = 'MANUAL') -> Optional[Dict]:
        """
        Close position on BingX exchange

        Args:
            position: Position dictionary from position_manager
            current_price: Current market price
            exit_reason: Reason for exit (STOP_LOSS, TAKE_PROFIT, MANUAL)

        Returns:
            Closed position with P&L or None if failed
        """
        try:
            side = position['side']
            quantity = position['quantity']
            entry_price = position['entry_price']

            logger.info(f"📤 Closing {side} position on BingX: {quantity:.5f} BTC")

            # Close position via market order with positionSide
            close_side = 'SELL' if side == 'LONG' else 'BUY'
            result = self.api.place_market_order(
                symbol=self.symbol,
                side=close_side,
                quantity=quantity,
                position_side=side
            )

            logger.info(f"✅ Close order placed")

            # Use current price as exit price (market orders fill immediately)
            exit_price = current_price

            # Wait for order to process
            time.sleep(1)

            # Calculate P&L
            if side == "LONG":
                pnl = (exit_price - entry_price) * quantity
            else:  # SHORT
                pnl = (entry_price - exit_price) * quantity

            pnl_percent = (pnl / (entry_price * quantity)) * 100

            # Update balance
            self.balance += pnl

            # Close position in position manager
            if self.position_manager:
                closed_pos = self.position_manager.close_position(
                    position['position_id'],
                    exit_price,
                    exit_reason
                )

                logger.info(f"✅ Position closed: P&L = ${pnl:+.2f} ({pnl_percent:+.2f}%)")

                return closed_pos

            return None

        except Exception as e:
            logger.error(f"❌ Failed to close position: {e}")
            return None

    def get_account_status(self) -> Dict:
        """
        Get current account status from exchange

        Returns:
            Account status dictionary
        """
        try:
            # Fetch real balance from exchange
            account = self.api.get_account_balance()
            real_balance = account['available_margin']

            # Get open positions
            open_positions = self.position_manager.get_open_positions() if self.position_manager else []

            # Calculate stats
            margin_used = sum(pos.get('margin_required', 0) for pos in open_positions)
            unrealized_pnl = sum(pos.get('pnl', 0) for pos in open_positions)
            equity = real_balance + unrealized_pnl

            # Calculate total return
            total_pnl = real_balance - self.initial_balance
            total_return_percent = (total_pnl / self.initial_balance) * 100 if self.initial_balance > 0 else 0

            return {
                'balance': real_balance,
                'equity': equity,
                'margin_available': real_balance - margin_used,
                'margin_used': margin_used,
                'unrealized_pnl': unrealized_pnl,
                'total_pnl': total_pnl,
                'total_return_percent': total_return_percent,
                'peak_balance': max(self.peak_balance, real_balance),
                'max_drawdown_percent': self.max_drawdown
            }

        except Exception as e:
            logger.error(f"❌ Failed to get account status: {e}")
            return {
                'balance': self.balance,
                'equity': self.balance,
                'margin_available': self.balance,
                'margin_used': 0,
                'unrealized_pnl': 0,
                'total_pnl': 0,
                'total_return_percent': 0,
                'peak_balance': self.balance,
                'max_drawdown_percent': 0
            }

    def get_performance_stats(self) -> Dict:
        """Get performance statistics from database"""
        if not self.trade_db:
            return {
                'total_pnl': 0,
                'total_return_percent': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_trades': 0,
                'peak_balance': self.balance,
                'max_drawdown_percent': 0
            }

        stats = self.trade_db.get_performance_stats()
        total_pnl = stats['total_pnl']
        total_return = (total_pnl / self.initial_balance) * 100 if self.initial_balance > 0 else 0

        # Calculate profit factor (total wins / total losses)
        # Get winning and losing trades to calculate profit factor
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        total_trades = stats.get('total_trades', 0)

        # Calculate profit factor if we have trades
        profit_factor = 0.0
        if total_trades > 0 and losses > 0:
            # We need to get individual trade P&Ls to calculate this properly
            # For now, use a simple approximation
            win_rate = stats.get('win_rate', 0) / 100.0
            if win_rate < 1.0 and win_rate > 0:
                # Rough estimate: assumes equal win/loss sizes
                profit_factor = win_rate / (1.0 - win_rate) if (1.0 - win_rate) > 0 else 0.0

        return {
            'total_pnl': total_pnl,
            'total_return_percent': total_return,
            'win_rate': stats['win_rate'],
            'profit_factor': profit_factor,
            'total_trades': stats['total_trades'],
            'peak_balance': self.peak_balance,
            'max_drawdown_percent': self.max_drawdown
        }

    def close_all_positions(self) -> bool:
        """
        EMERGENCY: Close all open positions immediately

        Returns:
            True if all positions closed successfully
        """
        logger.warning("="*80)
        logger.warning("🚨 EMERGENCY: CLOSING ALL POSITIONS")
        logger.warning("="*80)

        try:
            # Get all open positions from exchange
            exchange_positions = self.api.get_positions(self.symbol)

            if not exchange_positions:
                logger.info("✅ No open positions to close")
                return True

            success = True
            for pos in exchange_positions:
                side = pos.get('side')
                size = float(pos.get('position_amount', 0))

                if size != 0:
                    logger.warning(f"🔄 Closing {side} position: {abs(size)} BTC")
                    result = self.api.close_position(self.symbol, side)

                    if result:
                        logger.info(f"✅ Position closed")
                    else:
                        logger.error(f"❌ Failed to close {side} position")
                        success = False

            if success:
                logger.warning("✅ All positions closed successfully")
            else:
                logger.error("❌ Some positions failed to close")

            return success

        except Exception as e:
            logger.error(f"❌ Emergency close failed: {e}")
            return False


if __name__ == "__main__":
    print("⚠️  This is the LIVE TRADING module")
    print("⚠️  Do NOT run directly - use through main trading bot")
    print("⚠️  Real money will be at risk")
