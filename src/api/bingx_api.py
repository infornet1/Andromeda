#!/usr/bin/env python3
"""
BingX API Connector for ADX Strategy v2.0
Handles all BingX Perpetual Futures API interactions

Documentation: https://bingx-api.github.io/docs/
"""

import time
import hmac
import hashlib
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import logging
from urllib.parse import urlencode

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BingXAPI:
    """
    BingX Perpetual Futures API Client

    Features:
    - Market data (klines, ticker, orderbook)
    - Account info (balance, positions)
    - Order management (place, cancel, query)
    - Leverage management
    - Rate limiting (1200 req/min)
    """

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        """
        Initialize BingX API client

        Args:
            api_key: BingX API key
            api_secret: BingX API secret
            testnet: Use testnet (if available)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        # Base URLs
        if testnet:
            self.base_url = "https://open-api-vst.bingx.com"  # Testnet (if available)
            logger.warning("Testnet URL may not be available for BingX")
        else:
            self.base_url = "https://open-api.bingx.com"

        # Rate limiting
        self.request_count = 0
        self.rate_limit_reset = time.time() + 60
        self.max_requests_per_minute = 1200

        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-BX-APIKEY': self.api_key
        })

        logger.info(f"BingX API initialized: {self.base_url}")

    def _generate_signature(self, params: Dict) -> str:
        """
        Generate HMAC SHA256 signature for authenticated requests

        Args:
            params: Request parameters

        Returns:
            Signature string
        """
        # Sort parameters alphabetically
        sorted_params = sorted(params.items())
        query_string = urlencode(sorted_params)

        # Generate signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return signature

    def _check_rate_limit(self):
        """Check and enforce rate limiting"""
        current_time = time.time()

        # Reset counter every minute
        if current_time >= self.rate_limit_reset:
            self.request_count = 0
            self.rate_limit_reset = current_time + 60

        # Check if limit exceeded
        if self.request_count >= self.max_requests_per_minute:
            wait_time = self.rate_limit_reset - current_time
            if wait_time > 0:
                logger.warning(f"Rate limit reached. Waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                self.request_count = 0
                self.rate_limit_reset = time.time() + 60

        self.request_count += 1

    def _request(self, method: str, endpoint: str, params: Dict = None,
                 signed: bool = False) -> Dict:
        """
        Make HTTP request to BingX API

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint
            params: Request parameters
            signed: Whether request requires signature

        Returns:
            Response data as dictionary
        """
        self._check_rate_limit()

        url = f"{self.base_url}{endpoint}"
        params = params or {}

        # Add timestamp for signed requests
        if signed:
            # Use BingX server time for better synchronization
            try:
                server_time_response = self.session.get(
                    f"{self.base_url}/openApi/swap/v2/server/time",
                    timeout=5
                )
                if server_time_response.status_code == 200:
                    server_data = server_time_response.json()
                    params['timestamp'] = server_data.get('data', {}).get('serverTime', int(time.time() * 1000))
                else:
                    params['timestamp'] = int(time.time() * 1000)
            except:
                params['timestamp'] = int(time.time() * 1000)

            params['signature'] = self._generate_signature(params)

        try:
            if method == 'GET':
                response = self.session.get(url, params=params, timeout=10)
            elif method == 'POST':
                response = self.session.post(url, json=params, timeout=10)
            elif method == 'DELETE':
                response = self.session.delete(url, params=params, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            data = response.json()

            # BingX response format: {"code": 0, "msg": "", "data": {...}}
            if data.get('code') != 0:
                logger.error(f"API error: {data.get('msg', 'Unknown error')}")
                raise Exception(f"BingX API error: {data.get('msg')}")

            return data.get('data', {})

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    # ==================== Market Data Methods ====================

    def get_server_time(self) -> int:
        """
        Get BingX server time

        Returns:
            Server timestamp in milliseconds
        """
        endpoint = "/openApi/swap/v2/server/time"
        data = self._request('GET', endpoint)
        return data.get('serverTime')

    def get_kline_data(self, symbol: str = "BTC-USDT", interval: str = "5m",
                       limit: int = 100, start_time: Optional[int] = None,
                       end_time: Optional[int] = None) -> List[Dict]:
        """
        Get candlestick/kline data

        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            interval: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d)
            limit: Number of candles (max 1440)
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds

        Returns:
            List of kline dictionaries with OHLCV data
        """
        endpoint = "/openApi/swap/v3/quote/klines"

        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': min(limit, 1440)
        }

        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time

        raw_data = self._request('GET', endpoint, params)

        # Parse kline data
        # Format: {'open': '...', 'close': '...', 'high': '...', 'low': '...', 'volume': '...', 'time': ...}
        klines = []
        for k in raw_data:
            timestamp = int(k.get('time', 0))
            klines.append({
                'timestamp': timestamp,
                'open': float(k.get('open', 0)),
                'high': float(k.get('high', 0)),
                'low': float(k.get('low', 0)),
                'close': float(k.get('close', 0)),
                'volume': float(k.get('volume', 0)),
                'close_time': timestamp + (5 * 60 * 1000),  # Add 5 minutes for 5m interval
                'datetime': datetime.fromtimestamp(timestamp / 1000)
            })

        logger.info(f"Fetched {len(klines)} {interval} candles for {symbol}")
        return klines

    def get_ticker_price(self, symbol: str = "BTC-USDT") -> Dict:
        """
        Get latest ticker price

        Args:
            symbol: Trading pair

        Returns:
            Ticker data with price, volume, etc.
        """
        endpoint = "/openApi/swap/v2/quote/ticker"
        params = {'symbol': symbol}

        data = self._request('GET', endpoint, params)

        return {
            'symbol': symbol,
            'price': float(data.get('lastPrice', 0)),
            'bid': float(data.get('bidPrice', 0)),
            'ask': float(data.get('askPrice', 0)),
            'volume': float(data.get('volume', 0)),
            'timestamp': int(data.get('time', 0))
        }

    def get_orderbook(self, symbol: str = "BTC-USDT", limit: int = 20) -> Dict:
        """
        Get order book depth

        Args:
            symbol: Trading pair
            limit: Depth limit (5, 10, 20, 50, 100)

        Returns:
            Order book with bids and asks
        """
        endpoint = "/openApi/swap/v2/quote/depth"
        params = {'symbol': symbol, 'limit': limit}

        data = self._request('GET', endpoint, params)

        return {
            'bids': [[float(p), float(q)] for p, q in data.get('bids', [])],
            'asks': [[float(p), float(q)] for p, q in data.get('asks', [])],
            'timestamp': int(data.get('time', 0))
        }

    # ==================== Account Methods ====================

    def get_account_balance(self) -> Dict:
        """
        Get account balance and equity

        Returns:
            Account balance information
        """
        endpoint = "/openApi/swap/v2/user/balance"
        data = self._request('GET', endpoint, signed=True)

        balance_info = data.get('balance', {})

        return {
            'total_equity': float(balance_info.get('balance', 0)),
            'available_margin': float(balance_info.get('availableMargin', 0)),
            'used_margin': float(balance_info.get('usedMargin', 0)),
            'unrealized_pnl': float(balance_info.get('unrealizedProfit', 0)),
            'asset': balance_info.get('asset', 'USDT')
        }

    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get open positions

        Args:
            symbol: Filter by symbol (optional)

        Returns:
            List of position dictionaries
        """
        endpoint = "/openApi/swap/v2/user/positions"
        params = {}
        if symbol:
            params['symbol'] = symbol

        data = self._request('GET', endpoint, params, signed=True)

        positions = []
        for pos in data:
            if float(pos.get('positionAmt', 0)) != 0:
                positions.append({
                    'symbol': pos.get('symbol'),
                    'side': pos.get('positionSide'),
                    'quantity': float(pos.get('positionAmt', 0)),
                    'entry_price': float(pos.get('avgPrice', 0)),
                    'mark_price': float(pos.get('markPrice', 0)),
                    'unrealized_pnl': float(pos.get('unrealizedProfit', 0)),
                    'leverage': int(pos.get('leverage', 1))
                })

        return positions

    # ==================== Trading Methods ====================

    def set_leverage(self, symbol: str, leverage: int, side: str = "BOTH") -> bool:
        """
        Set leverage for symbol

        Args:
            symbol: Trading pair
            leverage: Leverage multiplier (1-150)
            side: Position side (LONG, SHORT, BOTH)

        Returns:
            True if successful
        """
        endpoint = "/openApi/swap/v2/trade/leverage"

        params = {
            'symbol': symbol,
            'leverage': leverage,
            'side': side
        }

        self._request('POST', endpoint, params, signed=True)
        logger.info(f"Set {symbol} leverage to {leverage}x ({side})")
        return True

    def place_market_order(self, symbol: str, side: str, quantity: float,
                          stop_loss: Optional[float] = None,
                          take_profit: Optional[float] = None) -> Dict:
        """
        Place market order

        Args:
            symbol: Trading pair
            side: Order side (BUY or SELL)
            quantity: Order quantity
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)

        Returns:
            Order information
        """
        endpoint = "/openApi/swap/v2/trade/order"

        params = {
            'symbol': symbol,
            'side': side.upper(),
            'type': 'MARKET',
            'quantity': quantity
        }

        if stop_loss:
            params['stopLoss'] = stop_loss
        if take_profit:
            params['takeProfit'] = take_profit

        data = self._request('POST', endpoint, params, signed=True)

        logger.info(f"Market order placed: {side} {quantity} {symbol}")

        return {
            'order_id': data.get('orderId'),
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'type': 'MARKET',
            'status': data.get('status'),
            'timestamp': int(time.time() * 1000)
        }

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        Cancel open order

        Args:
            symbol: Trading pair
            order_id: Order ID to cancel

        Returns:
            True if successful
        """
        endpoint = "/openApi/swap/v2/trade/order"

        params = {
            'symbol': symbol,
            'orderId': order_id
        }

        self._request('DELETE', endpoint, params, signed=True)
        logger.info(f"Order cancelled: {order_id}")
        return True

    def get_order_status(self, symbol: str, order_id: str) -> Dict:
        """
        Get order status

        Args:
            symbol: Trading pair
            order_id: Order ID

        Returns:
            Order status information
        """
        endpoint = "/openApi/swap/v2/trade/order"

        params = {
            'symbol': symbol,
            'orderId': order_id
        }

        data = self._request('GET', endpoint, params, signed=True)

        return {
            'order_id': data.get('orderId'),
            'status': data.get('status'),
            'filled_quantity': float(data.get('executedQty', 0)),
            'avg_price': float(data.get('avgPrice', 0)),
            'side': data.get('side'),
            'type': data.get('type')
        }

    def close_position(self, symbol: str, side: str) -> Dict:
        """
        Close position with market order

        Args:
            symbol: Trading pair
            side: Position side to close (LONG or SHORT)

        Returns:
            Close order information
        """
        # Get current position
        positions = self.get_positions(symbol)

        for pos in positions:
            if pos['side'] == side:
                quantity = abs(pos['quantity'])

                # Close LONG by SELL, close SHORT by BUY
                close_side = 'SELL' if side == 'LONG' else 'BUY'

                return self.place_market_order(symbol, close_side, quantity)

        logger.warning(f"No {side} position found for {symbol}")
        return {}

    # ==================== Utility Methods ====================

    def test_connectivity(self) -> bool:
        """
        Test API connectivity

        Returns:
            True if connected successfully
        """
        try:
            server_time = self.get_server_time()
            logger.info(f"✅ BingX API connected (server time: {server_time})")
            return True
        except Exception as e:
            logger.error(f"❌ BingX API connection failed: {e}")
            return False

    def get_exchange_info(self, symbol: str = "BTC-USDT") -> Dict:
        """
        Get trading rules and symbol information

        Args:
            symbol: Trading pair

        Returns:
            Exchange info including tick size, lot size, etc.
        """
        endpoint = "/openApi/swap/v2/quote/contracts"

        data = self._request('GET', endpoint)

        for contract in data:
            if contract.get('symbol') == symbol:
                return {
                    'symbol': symbol,
                    'tick_size': float(contract.get('tickSize', 0.1)),
                    'lot_size': float(contract.get('size', 0.001)),
                    'min_qty': float(contract.get('minQty', 0.001)),
                    'max_qty': float(contract.get('maxQty', 1000)),
                    'max_leverage': int(contract.get('maxLeverage', 125))
                }

        return {}


# ==================== Helper Functions ====================

def calculate_position_size(capital: float, risk_percent: float,
                           entry_price: float, stop_loss: float,
                           leverage: int = 1) -> float:
    """
    Calculate position size based on risk management

    Args:
        capital: Available capital
        risk_percent: Percent of capital to risk (e.g., 2.0 for 2%)
        entry_price: Entry price
        stop_loss: Stop loss price
        leverage: Leverage multiplier

    Returns:
        Position size in BTC
    """
    risk_amount = capital * (risk_percent / 100)
    stop_distance = abs(entry_price - stop_loss)
    position_value = (risk_amount / stop_distance) * entry_price
    position_size = position_value / entry_price

    # Account for leverage
    position_size = position_size * leverage

    return round(position_size, 3)


if __name__ == "__main__":
    # Test script
    from dotenv import load_dotenv
    import os

    load_dotenv('config/.env')

    api = BingXAPI(
        api_key=os.getenv('BINGX_API_KEY'),
        api_secret=os.getenv('BINGX_API_SECRET'),
        testnet=False
    )

    print("Testing BingX API connectivity...")

    # Test 1: Connectivity
    if api.test_connectivity():
        print("✅ Connection successful")

    # Test 2: Get ticker
    ticker = api.get_ticker_price("BTC-USDT")
    print(f"✅ BTC Price: ${ticker['price']:,.2f}")

    # Test 3: Get klines
    klines = api.get_kline_data("BTC-USDT", "5m", limit=10)
    print(f"✅ Fetched {len(klines)} klines")
    print(f"   Latest: O:{klines[-1]['open']} H:{klines[-1]['high']} L:{klines[-1]['low']} C:{klines[-1]['close']}")
