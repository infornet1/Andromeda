#!/usr/bin/env python3
"""
Order Executor for ADX Strategy v2.0
Handles order placement, execution, and status tracking
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from typing import Dict, Optional, List
from datetime import datetime
import time
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderExecutor:
    """
    Order Execution Engine

    Features:
    - Market order execution
    - Limit order placement (optional)
    - Stop loss / Take profit orders
    - Order status tracking
    - Error handling & retries
    - Slippage simulation
    """

    def __init__(self,
                 api_client=None,
                 default_symbol: str = "BTC-USDT",
                 max_retries: int = 3,
                 retry_delay: float = 1.0,
                 enable_live_trading: bool = False):
        """
        Initialize order executor

        Args:
            api_client: BingX API client (optional, for live trading)
            default_symbol: Default trading symbol
            max_retries: Max retry attempts for failed orders
            retry_delay: Delay between retries (seconds)
            enable_live_trading: Enable real order execution (DANGEROUS!)
        """
        self.api = api_client
        self.default_symbol = default_symbol
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.enable_live_trading = enable_live_trading

        # Order tracking
        self.pending_orders = {}
        self.executed_orders = {}
        self.failed_orders = {}
        self.order_id_counter = 1000

        # Statistics
        self.total_orders = 0
        self.successful_orders = 0
        self.failed_order_count = 0

        if enable_live_trading and not api_client:
            logger.warning("⚠️  Live trading enabled but no API client provided!")

        if enable_live_trading:
            logger.critical("🚨 LIVE TRADING ENABLED - REAL MONEY AT RISK!")
        else:
            logger.info("✅ Paper trading mode - No real orders will be placed")

    def generate_order_id(self) -> str:
        """Generate unique order ID"""
        order_id = f"ADX_{self.order_id_counter}_{int(time.time())}"
        self.order_id_counter += 1
        return order_id

    def place_market_order(self,
                          side: str,
                          quantity: float,
                          symbol: Optional[str] = None,
                          stop_loss: Optional[float] = None,
                          take_profit: Optional[float] = None,
                          metadata: Optional[Dict] = None) -> Dict:
        """
        Place market order (instant execution at current price)

        Args:
            side: BUY or SELL
            quantity: Position size in BTC
            symbol: Trading symbol (default: BTC-USDT)
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            metadata: Additional order metadata

        Returns:
            Order result dictionary
        """
        symbol = symbol or self.default_symbol
        order_id = self.generate_order_id()

        logger.info(f"📝 Placing {side} market order: {quantity} BTC @ {symbol}")

        order = {
            'order_id': order_id,
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'quantity': quantity,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'status': 'PENDING',
            'created_at': datetime.now(),
            'metadata': metadata or {}
        }

        self.pending_orders[order_id] = order
        self.total_orders += 1

        # Execute order
        result = self._execute_order(order)

        return result

    def place_limit_order(self,
                         side: str,
                         quantity: float,
                         price: float,
                         symbol: Optional[str] = None,
                         stop_loss: Optional[float] = None,
                         take_profit: Optional[float] = None,
                         time_in_force: str = "GTC",
                         metadata: Optional[Dict] = None) -> Dict:
        """
        Place limit order (execution at specified price)

        Args:
            side: BUY or SELL
            quantity: Position size in BTC
            price: Limit price
            symbol: Trading symbol
            stop_loss: Stop loss price
            take_profit: Take profit price
            time_in_force: GTC (Good Till Cancel) or IOC (Immediate Or Cancel)
            metadata: Additional order metadata

        Returns:
            Order result dictionary
        """
        symbol = symbol or self.default_symbol
        order_id = self.generate_order_id()

        logger.info(f"📝 Placing {side} limit order: {quantity} BTC @ ${price:,.2f}")

        order = {
            'order_id': order_id,
            'symbol': symbol,
            'side': side,
            'type': 'LIMIT',
            'quantity': quantity,
            'price': price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'time_in_force': time_in_force,
            'status': 'PENDING',
            'created_at': datetime.now(),
            'metadata': metadata or {}
        }

        self.pending_orders[order_id] = order
        self.total_orders += 1

        # In paper trading, limit orders execute immediately
        # In live trading, they would wait for price to be hit
        if not self.enable_live_trading:
            logger.info("📊 Paper trading: Limit order will execute at limit price")
            result = self._execute_order(order)
        else:
            # Live trading would submit order to exchange
            result = self._submit_live_order(order)

        return result

    def place_stop_loss_order(self,
                             position_id: str,
                             stop_price: float,
                             quantity: float,
                             symbol: Optional[str] = None) -> Dict:
        """
        Place stop loss order

        Args:
            position_id: Associated position ID
            stop_price: Stop loss trigger price
            quantity: Quantity to close
            symbol: Trading symbol

        Returns:
            Order result dictionary
        """
        symbol = symbol or self.default_symbol
        order_id = self.generate_order_id()

        logger.info(f"🛑 Placing stop loss: ${stop_price:,.2f} for position {position_id}")

        order = {
            'order_id': order_id,
            'symbol': symbol,
            'side': 'SELL',  # SL always closes position
            'type': 'STOP_LOSS',
            'quantity': quantity,
            'stop_price': stop_price,
            'status': 'PENDING',
            'position_id': position_id,
            'created_at': datetime.now()
        }

        self.pending_orders[order_id] = order

        if not self.enable_live_trading:
            logger.info("📊 Paper trading: Stop loss order registered")
            order['status'] = 'PLACED'
            self.executed_orders[order_id] = order
            del self.pending_orders[order_id]

        return order

    def place_take_profit_order(self,
                               position_id: str,
                               take_profit_price: float,
                               quantity: float,
                               symbol: Optional[str] = None) -> Dict:
        """
        Place take profit order

        Args:
            position_id: Associated position ID
            take_profit_price: Take profit trigger price
            quantity: Quantity to close
            symbol: Trading symbol

        Returns:
            Order result dictionary
        """
        symbol = symbol or self.default_symbol
        order_id = self.generate_order_id()

        logger.info(f"🎯 Placing take profit: ${take_profit_price:,.2f} for position {position_id}")

        order = {
            'order_id': order_id,
            'symbol': symbol,
            'side': 'SELL',  # TP always closes position
            'type': 'TAKE_PROFIT',
            'quantity': quantity,
            'take_profit_price': take_profit_price,
            'status': 'PENDING',
            'position_id': position_id,
            'created_at': datetime.now()
        }

        self.pending_orders[order_id] = order

        if not self.enable_live_trading:
            logger.info("📊 Paper trading: Take profit order registered")
            order['status'] = 'PLACED'
            self.executed_orders[order_id] = order
            del self.pending_orders[order_id]

        return order

    def _execute_order(self, order: Dict) -> Dict:
        """
        Execute order (internal method)

        Args:
            order: Order dictionary

        Returns:
            Execution result
        """
        order_id = order['order_id']

        try:
            if self.enable_live_trading and self.api:
                # Live trading execution
                result = self._execute_live_order(order)
            else:
                # Paper trading execution
                result = self._execute_paper_order(order)

            # Update order status
            order['status'] = result['status']
            order['executed_at'] = result.get('executed_at')
            order['executed_price'] = result.get('executed_price')
            order['executed_quantity'] = result.get('executed_quantity')
            order['fee'] = result.get('fee', 0)
            order['exchange_order_id'] = result.get('exchange_order_id')

            # Move to executed orders
            if result['status'] == 'FILLED':
                self.executed_orders[order_id] = order
                self.successful_orders += 1
                logger.info(f"✅ Order {order_id} executed successfully")
            else:
                self.failed_orders[order_id] = order
                self.failed_order_count += 1
                logger.error(f"❌ Order {order_id} failed: {result.get('error')}")

            # Remove from pending
            if order_id in self.pending_orders:
                del self.pending_orders[order_id]

            return result

        except Exception as e:
            logger.error(f"❌ Order execution error: {e}")
            order['status'] = 'FAILED'
            order['error'] = str(e)
            self.failed_orders[order_id] = order
            self.failed_order_count += 1

            if order_id in self.pending_orders:
                del self.pending_orders[order_id]

            return {
                'status': 'FAILED',
                'order_id': order_id,
                'error': str(e)
            }

    def _execute_paper_order(self, order: Dict) -> Dict:
        """
        Execute order in paper trading mode

        Args:
            order: Order dictionary

        Returns:
            Simulated execution result
        """
        # Simulate execution with realistic slippage
        base_price = order.get('price')  # Limit order price

        # For market orders, we'd get current market price
        # For now, simulate with a reasonable price
        if not base_price:
            base_price = 112000  # Default BTC price (would fetch from API in real system)

        # Simulate slippage (0.01% - 0.05%)
        import random
        slippage_percent = random.uniform(0.0001, 0.0005)

        if order['side'] == 'BUY':
            executed_price = base_price * (1 + slippage_percent)
        else:
            executed_price = base_price * (1 - slippage_percent)

        # Simulate fee (0.05% taker fee on BingX)
        fee_percent = 0.0005
        notional_value = order['quantity'] * executed_price
        fee = notional_value * fee_percent

        logger.info(f"📊 Paper order executed: {order['quantity']:.5f} BTC @ ${executed_price:,.2f}")
        logger.info(f"   Slippage: {slippage_percent*100:.3f}%, Fee: ${fee:.2f}")

        return {
            'status': 'FILLED',
            'order_id': order['order_id'],
            'executed_price': executed_price,
            'executed_quantity': order['quantity'],
            'executed_at': datetime.now(),
            'fee': fee,
            'exchange_order_id': f"PAPER_{order['order_id']}"
        }

    def _execute_live_order(self, order: Dict) -> Dict:
        """
        Execute order on live exchange (REAL MONEY!)

        Args:
            order: Order dictionary

        Returns:
            Exchange execution result
        """
        logger.critical(f"🚨 EXECUTING LIVE ORDER - REAL MONEY AT RISK!")

        retries = 0
        last_error = None

        while retries < self.max_retries:
            try:
                # Place order via BingX API
                if order['type'] == 'MARKET':
                    response = self.api.place_market_order(
                        symbol=order['symbol'],
                        side=order['side'],
                        quantity=order['quantity']
                    )
                elif order['type'] == 'LIMIT':
                    response = self.api.place_limit_order(
                        symbol=order['symbol'],
                        side=order['side'],
                        quantity=order['quantity'],
                        price=order['price']
                    )
                else:
                    raise ValueError(f"Unsupported order type: {order['type']}")

                # Parse response
                if response.get('code') == 0:
                    logger.info(f"✅ Live order placed: {response.get('data', {}).get('orderId')}")
                    return {
                        'status': 'FILLED',
                        'order_id': order['order_id'],
                        'executed_price': response.get('data', {}).get('price'),
                        'executed_quantity': response.get('data', {}).get('executedQty'),
                        'executed_at': datetime.now(),
                        'fee': response.get('data', {}).get('fee', 0),
                        'exchange_order_id': response.get('data', {}).get('orderId')
                    }
                else:
                    last_error = response.get('msg', 'Unknown error')
                    logger.error(f"❌ Exchange error: {last_error}")

            except Exception as e:
                last_error = str(e)
                logger.error(f"❌ Retry {retries+1}/{self.max_retries}: {e}")

            retries += 1
            if retries < self.max_retries:
                time.sleep(self.retry_delay)

        # All retries failed
        return {
            'status': 'FAILED',
            'order_id': order['order_id'],
            'error': last_error
        }

    def _submit_live_order(self, order: Dict) -> Dict:
        """Submit limit order to exchange (waits for fill)"""
        # Similar to _execute_live_order but for limit orders
        # that need to wait for price to be hit
        return self._execute_live_order(order)

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel pending order

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancelled successfully
        """
        if order_id in self.pending_orders:
            order = self.pending_orders[order_id]

            if self.enable_live_trading and self.api:
                # Cancel on exchange
                try:
                    response = self.api.cancel_order(
                        symbol=order['symbol'],
                        order_id=order.get('exchange_order_id')
                    )
                    if response.get('code') == 0:
                        logger.info(f"✅ Order {order_id} cancelled on exchange")
                    else:
                        logger.error(f"❌ Failed to cancel order on exchange: {response.get('msg')}")
                        return False
                except Exception as e:
                    logger.error(f"❌ Cancel order error: {e}")
                    return False

            # Remove from pending
            order['status'] = 'CANCELLED'
            order['cancelled_at'] = datetime.now()
            self.failed_orders[order_id] = order
            del self.pending_orders[order_id]

            logger.info(f"✅ Order {order_id} cancelled")
            return True

        logger.warning(f"⚠️  Order {order_id} not found in pending orders")
        return False

    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Get order status

        Args:
            order_id: Order ID

        Returns:
            Order dictionary or None
        """
        if order_id in self.pending_orders:
            return self.pending_orders[order_id]
        elif order_id in self.executed_orders:
            return self.executed_orders[order_id]
        elif order_id in self.failed_orders:
            return self.failed_orders[order_id]

        return None

    def get_all_orders(self, status: Optional[str] = None) -> List[Dict]:
        """
        Get all orders, optionally filtered by status

        Args:
            status: PENDING, FILLED, FAILED, or None for all

        Returns:
            List of order dictionaries
        """
        all_orders = []

        if status is None or status == 'PENDING':
            all_orders.extend(self.pending_orders.values())

        if status is None or status == 'FILLED':
            all_orders.extend(self.executed_orders.values())

        if status is None or status == 'FAILED':
            all_orders.extend(self.failed_orders.values())

        return sorted(all_orders, key=lambda x: x['created_at'], reverse=True)

    def get_execution_stats(self) -> Dict:
        """Get execution statistics"""
        success_rate = (self.successful_orders / self.total_orders * 100) if self.total_orders > 0 else 0

        return {
            'total_orders': self.total_orders,
            'successful_orders': self.successful_orders,
            'failed_orders': self.failed_order_count,
            'pending_orders': len(self.pending_orders),
            'success_rate': round(success_rate, 2),
            'mode': 'LIVE' if self.enable_live_trading else 'PAPER'
        }

    def get_execution_summary(self) -> str:
        """Generate human-readable execution summary"""
        stats = self.get_execution_stats()

        return f"""
{'='*60}
Order Execution Summary
{'='*60}
Mode:               {stats['mode']} TRADING
Total Orders:       {stats['total_orders']}
Successful:         {stats['successful_orders']}
Failed:             {stats['failed_orders']}
Pending:            {stats['pending_orders']}
Success Rate:       {stats['success_rate']:.1f}%
{'='*60}
"""


if __name__ == "__main__":
    # Test script
    print("Testing Order Executor...")

    # Initialize in paper trading mode
    executor = OrderExecutor(enable_live_trading=False)

    # Test 1: Place market order
    print("\n1. Testing market order placement")
    order1 = executor.place_market_order(
        side='BUY',
        quantity=0.001,
        stop_loss=111000,
        take_profit=113000,
        metadata={'signal_id': 'TEST_001', 'strategy': 'ADX_v2'}
    )
    print(f"   Order placed: {order1['order_id']}")
    print(f"   Status: {order1['status']}")
    if order1['status'] == 'FILLED':
        print(f"   Executed: {order1['executed_quantity']:.5f} BTC @ ${order1['executed_price']:,.2f}")
        print(f"   Fee: ${order1['fee']:.2f}")

    # Test 2: Place limit order
    print("\n2. Testing limit order placement")
    order2 = executor.place_limit_order(
        side='SELL',
        quantity=0.001,
        price=113000,
        stop_loss=114000,
        take_profit=111000
    )
    print(f"   Order placed: {order2['order_id']}")
    print(f"   Status: {order2['status']}")

    # Test 3: Get order status
    print("\n3. Testing order status retrieval")
    status = executor.get_order_status(order1['order_id'])
    print(f"   Order {order1['order_id']}: {status['status']}")

    # Test 4: Get all orders
    print("\n4. Testing get all orders")
    all_orders = executor.get_all_orders()
    print(f"   Total orders: {len(all_orders)}")
    for order in all_orders:
        print(f"     - {order['order_id']}: {order['side']} {order['quantity']:.5f} BTC [{order['status']}]")

    # Test 5: Execution statistics
    print("\n5. Execution Statistics")
    print(executor.get_execution_summary())

    print("✅ Order Executor test complete!")
