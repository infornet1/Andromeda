#!/usr/bin/env python3
"""
ADX Strategy v2.0 - Real-Time Web Dashboard
Standalone service for monitoring paper/live trading

Port: 5900
Access: http://localhost:5900
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from flask import Flask, render_template, jsonify, request
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, List, Optional
from dotenv import load_dotenv

from src.persistence.trade_database import TradeDatabase
from src.api.bingx_api import BingXAPI

# Load environment
load_dotenv('config/.env')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


class DashboardDataProvider:
    """
    Data provider for dashboard - reads from bot state files and logs
    """

    def __init__(self):
        self.base_path = '/var/www/dev/trading/adx_strategy_v2'
        self.snapshot_file = os.path.join(self.base_path, 'logs/final_snapshot.json')
        self.config_file = os.path.join(self.base_path, 'config_live.json')

        # Initialize trade database
        try:
            self.trade_db = TradeDatabase()
            logger.info("✅ Trade database initialized for dashboard")
        except Exception as e:
            logger.warning(f"⚠️ Trade database not available: {e}")
            self.trade_db = None

        # Detect if bot is in paper or live mode
        self.is_paper_mode = self._detect_paper_mode()

        # Initialize BingX API only for LIVE mode
        if not self.is_paper_mode:
            try:
                self.bingx_api = BingXAPI(
                    api_key=os.getenv('BINGX_API_KEY'),
                    api_secret=os.getenv('BINGX_API_SECRET')
                )
                logger.info("✅ BingX API initialized for dashboard (LIVE MODE)")
            except Exception as e:
                logger.warning(f"⚠️ BingX API not available: {e}")
                self.bingx_api = None
        else:
            self.bingx_api = None
            logger.info("📄 Dashboard in PAPER MODE - BingX API disabled")

    def _detect_paper_mode(self) -> bool:
        """Detect if bot is running in paper or live mode"""
        try:
            import subprocess
            result = subprocess.run(
                ['ps', 'aux'],
                capture_output=True,
                text=True
            )
            # Check if live_trader.py is running with --mode paper
            for line in result.stdout.split('\n'):
                if 'live_trader.py' in line and '--mode paper' in line:
                    logger.info("🔍 Detected bot running in PAPER MODE")
                    return True
                elif 'live_trader.py' in line and '--mode live' in line:
                    logger.info("🔍 Detected bot running in LIVE MODE")
                    return False

            # Default to paper mode if uncertain
            logger.warning("⚠️ Could not detect mode, defaulting to PAPER MODE")
            return True
        except Exception as e:
            logger.error(f"Error detecting mode: {e}, defaulting to PAPER MODE")
            return True

    def get_bot_status(self) -> Dict:
        """Get current bot status"""
        try:
            # Check if bot is running by looking for the process
            import subprocess
            result = subprocess.run(
                ['pgrep', '-f', 'live_trader.py'],
                capture_output=True,
                text=True
            )
            is_running = bool(result.stdout.strip())

            # Also check if snapshot is recent (updated within last 30 seconds)
            if os.path.exists(self.snapshot_file):
                with open(self.snapshot_file, 'r') as f:
                    snapshot = json.load(f)
                    last_update = snapshot.get('timestamp', 'N/A')

                    # Check if snapshot is fresh
                    if last_update != 'N/A':
                        from datetime import datetime, timedelta
                        try:
                            snapshot_time = datetime.fromisoformat(last_update)
                            time_diff = (datetime.now() - snapshot_time).total_seconds()
                            # Consider running if snapshot updated within 30 seconds
                            if time_diff < 30:
                                is_running = True
                        except:
                            pass
            else:
                last_update = 'N/A'

            return {
                'running': is_running,
                'status': 'active' if is_running else 'inactive',
                'last_update': last_update
            }
        except Exception as e:
            logger.error(f"Error getting bot status: {e}")
            return {'running': False, 'status': 'unknown', 'last_update': 'N/A'}

    def get_account_status(self) -> Dict:
        """Get account balance and P&L (from live BingX or paper trading bot)"""
        try:
            # Get bot-tracked account from snapshot
            bot_account = {}
            if os.path.exists(self.snapshot_file):
                with open(self.snapshot_file, 'r') as f:
                    snapshot = json.load(f)
                    bot_account = snapshot.get('account', {})

            # In PAPER MODE: Use only bot snapshot data
            if self.is_paper_mode:
                return {
                    'balance': bot_account.get('balance', 100.0),
                    'equity': bot_account.get('equity', 100.0),
                    'available': bot_account.get('available', 100.0),
                    'margin_used': bot_account.get('margin_used', 0.0),
                    'unrealized_pnl': bot_account.get('unrealized_pnl', 0.0),
                    'total_pnl': bot_account.get('total_pnl', 0.0),
                    'total_return_percent': bot_account.get('total_return_percent', 0.0),
                    'peak_balance': bot_account.get('peak_balance', 100.0),
                    'max_drawdown': bot_account.get('max_drawdown', 0.0),
                    'data_source': 'PAPER_TRADING',
                    'trading_mode': 'PAPER'
                }

            # In LIVE MODE: Get live BingX balance if available
            live_balance = None
            live_equity = None
            live_unrealized = None
            live_margin_used = None
            live_available = None

            try:
                if self.bingx_api:
                    bingx_balance = self.bingx_api.get_account_balance()
                    live_equity = bingx_balance.get('total_equity', None)
                    live_available = bingx_balance.get('available_margin', None)
                    live_margin_used = bingx_balance.get('used_margin', None)
                    live_unrealized = bingx_balance.get('unrealized_pnl', None)
                    live_balance = live_equity
            except Exception as e:
                logger.debug(f"Could not fetch live balance: {e}")

            # Prefer live data, fall back to bot data
            return {
                'balance': live_balance if live_balance is not None else bot_account.get('balance', 100.0),
                'equity': live_equity if live_equity is not None else bot_account.get('equity', 100.0),
                'available': live_available if live_available is not None else bot_account.get('available', 100.0),
                'margin_used': live_margin_used if live_margin_used is not None else bot_account.get('margin_used', 0.0),
                'unrealized_pnl': live_unrealized if live_unrealized is not None else bot_account.get('unrealized_pnl', 0.0),
                'total_pnl': bot_account.get('total_pnl', 0.0),
                'total_return_percent': bot_account.get('total_return_percent', 0.0),
                'peak_balance': bot_account.get('peak_balance', 100.0),
                'max_drawdown': bot_account.get('max_drawdown', 0.0),
                'data_source': 'LIVE_BINGX' if live_balance is not None else 'BOT_SNAPSHOT',
                'trading_mode': 'LIVE'
            }
        except Exception as e:
            logger.error(f"Error getting account status: {e}")
            return self._get_default_account()

    def get_live_bingx_positions(self) -> List[Dict]:
        """Get actual positions from BingX exchange"""
        try:
            if not self.bingx_api:
                return []

            positions = self.bingx_api.get_positions("BTC-USDT")

            # Format for dashboard
            formatted = []
            for pos in positions:
                formatted.append({
                    'id': f"BINGX_{pos['side']}",
                    'side': pos['side'],
                    'symbol': pos['symbol'],
                    'entry_price': pos['entry_price'],
                    'current_price': pos['mark_price'],
                    'quantity': abs(pos['quantity']),
                    'pnl': pos['unrealized_pnl'],
                    'pnl_percent': (pos['unrealized_pnl'] / (pos['entry_price'] * abs(pos['quantity']))) * 100 if pos['quantity'] != 0 else 0,
                    'leverage': pos['leverage'],
                    'source': 'LIVE_EXCHANGE',
                    'margin_required': (pos['entry_price'] * abs(pos['quantity'])) / pos['leverage']
                })

            return formatted
        except Exception as e:
            logger.error(f"Error getting live BingX positions: {e}")
            return []

    def get_positions(self) -> List[Dict]:
        """Get open positions (from paper trading or live exchange)"""
        try:
            bot_positions = []

            # Get bot-tracked positions from snapshot
            if os.path.exists(self.snapshot_file):
                with open(self.snapshot_file, 'r') as f:
                    snapshot = json.load(f)
                    bot_positions = snapshot.get('positions', [])
                    for pos in bot_positions:
                        pos['source'] = 'PAPER_TRADING' if self.is_paper_mode else 'BOT_TRACKED'

            # In PAPER MODE: Return only bot positions
            if self.is_paper_mode:
                return bot_positions

            # In LIVE MODE: Get live BingX positions
            live_positions = self.get_live_bingx_positions()

            # Combine both (live positions first for visibility)
            all_positions = live_positions + bot_positions

            return all_positions
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def get_adx_data(self) -> Dict:
        """Get current ADX indicators"""
        try:
            # Import here to avoid circular dependencies
            from src.api.bingx_api import BingXAPI
            from src.indicators.adx_engine import ADXEngine
            import pandas as pd

            api_key = os.getenv('BINGX_API_KEY')
            api_secret = os.getenv('BINGX_API_SECRET')

            if not api_key or not api_secret:
                return self._get_default_adx()

            api = BingXAPI(api_key, api_secret)
            candles = api.get_kline_data('BTC-USDT', '5m', limit=200)

            if not candles:
                return self._get_default_adx()

            df = pd.DataFrame(candles)
            adx_engine = ADXEngine(period=14)
            df = adx_engine.analyze_dataframe(df, adx_threshold=25.0)

            latest = df.iloc[-1]

            # Determine market state
            adx_val = latest['adx']
            if adx_val < 20:
                state = 'RANGING'
            elif adx_val < 25:
                state = 'BUILDING'
            else:
                state = 'TRENDING'

            return {
                'adx': round(float(latest['adx']), 2),
                'plus_di': round(float(latest['plus_di']), 2),
                'minus_di': round(float(latest['minus_di']), 2),
                'di_spread': round(float(latest['di_spread']), 2),
                'adx_slope': round(float(latest['adx_slope']), 2),
                'market_state': state,
                'trend_strength': latest['trend_strength'],
                'confidence': round(float(latest['confidence']) * 100, 1)
            }
        except Exception as e:
            logger.error(f"Error getting ADX data: {e}")
            return self._get_default_adx()

    def get_btc_price(self) -> float:
        """Get current BTC price"""
        try:
            from src.api.bingx_api import BingXAPI

            api_key = os.getenv('BINGX_API_KEY')
            api_secret = os.getenv('BINGX_API_SECRET')

            if not api_key or not api_secret:
                return 107907.80

            api = BingXAPI(api_key, api_secret)
            ticker = api.get_ticker_price('BTC-USDT')

            if ticker and 'price' in ticker:
                return float(ticker['price'])

            return 107907.80
        except Exception as e:
            logger.error(f"Error getting BTC price: {e}")
            return 107907.80

    def get_trades(self, limit: int = 10, trading_mode: Optional[str] = None) -> List[Dict]:
        """Get recent trades from database

        Args:
            limit: Maximum number of trades to return
            trading_mode: Filter by 'paper' or 'live' mode (None = all trades)
        """
        try:
            if self.trade_db:
                # Get trades from database with filter
                trades = self.trade_db.get_all_trades(limit=limit, trading_mode=trading_mode)
                return trades
            else:
                # Fallback to snapshot file
                if not os.path.exists(self.snapshot_file):
                    return []

                with open(self.snapshot_file, 'r') as f:
                    snapshot = json.load(f)
                    trades = snapshot.get('recent_trades', [])

                # Return last N trades
                return trades[-limit:] if trades else []
        except Exception as e:
            logger.error(f"Error getting trades: {e}")
            return []

    def get_performance(self) -> Dict:
        """Get performance statistics from database"""
        try:
            if self.trade_db:
                # Get stats from database
                stats = self.trade_db.get_performance_stats()

                # Calculate profit factor
                trades = self.trade_db.get_all_trades()
                gross_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
                gross_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))
                profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

                return {
                    'total_trades': stats['total_trades'],
                    'wins': stats['wins'],
                    'losses': stats['losses'],
                    'win_rate': round(stats['win_rate'], 2),
                    'profit_factor': round(profit_factor, 2) if profit_factor else None,
                    'total_pnl': round(stats['total_pnl'], 2),
                    'avg_pnl': round(stats['avg_pnl'], 2),
                    'best_trade': round(stats['best_trade'], 2),
                    'worst_trade': round(stats['worst_trade'], 2)
                }
            else:
                # Fallback to snapshot calculation
                return self._get_default_performance()
        except Exception as e:
            logger.error(f"Error getting performance: {e}")
            return self._get_default_performance()

    def get_risk_status(self) -> Dict:
        """Get risk management status"""
        try:
            if not os.path.exists(self.snapshot_file):
                return self._get_default_risk()

            with open(self.snapshot_file, 'r') as f:
                snapshot = json.load(f)
                risk = snapshot.get('risk', {})

            return {
                'daily_pnl': risk.get('daily_pnl', 0.0),
                'daily_loss_limit': risk.get('daily_loss_limit_percent', 5.0),
                'max_drawdown': risk.get('current_drawdown_percent', 0.0),
                'max_drawdown_limit': risk.get('max_drawdown_percent', 15.0),
                'circuit_breaker': risk.get('circuit_breaker_active', False),
                'positions_open': risk.get('open_positions', 0),
                'positions_max': risk.get('max_positions', 2),
                'consecutive_wins': risk.get('consecutive_wins', 0),
                'consecutive_losses': risk.get('consecutive_losses', 0),
                'can_trade': risk.get('can_trade', True)
            }
        except Exception as e:
            logger.error(f"Error getting risk status: {e}")
            return self._get_default_risk()

    def _get_default_account(self) -> Dict:
        return {
            'balance': 100.0,
            'equity': 100.0,
            'available': 100.0,
            'margin_used': 0.0,
            'unrealized_pnl': 0.0,
            'total_pnl': 0.0,
            'total_return_percent': 0.0,
            'peak_balance': 100.0,
            'max_drawdown': 0.0
        }

    def _get_default_adx(self) -> Dict:
        return {
            'adx': 0.0,
            'plus_di': 0.0,
            'minus_di': 0.0,
            'di_spread': 0.0,
            'adx_slope': 0.0,
            'market_state': 'UNKNOWN',
            'trend_strength': 'NONE',
            'confidence': 0.0
        }

    def _get_default_performance(self) -> Dict:
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'profit_factor': None,
            'total_pnl': 0.0,
            'avg_pnl': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0
        }

    def _get_default_risk(self) -> Dict:
        return {
            'daily_pnl': 0.0,
            'daily_loss_limit': 5.0,
            'max_drawdown': 0.0,
            'max_drawdown_limit': 15.0,
            'circuit_breaker': False,
            'positions_open': 0,
            'positions_max': 2,
            'consecutive_wins': 0,
            'consecutive_losses': 0,
            'can_trade': True
        }


# Initialize data provider
data_provider = DashboardDataProvider()


# Routes
@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/status')
def api_status():
    """Get complete status snapshot"""
    try:
        bot_status = data_provider.get_bot_status()
        account = data_provider.get_account_status()
        positions = data_provider.get_positions()
        btc_price = data_provider.get_btc_price()

        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'bot_status': bot_status,
            'account': account,
            'positions': positions,
            'btc_price': btc_price,
            'positions_count': len(positions)
        })
    except Exception as e:
        logger.error(f"Error in /api/status: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/adx')
def api_adx():
    """Get ADX indicators"""
    try:
        adx_data = data_provider.get_adx_data()
        return jsonify(adx_data)
    except Exception as e:
        logger.error(f"Error in /api/adx: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/trades')
def api_trades():
    """Get recent trades with optional filtering

    Query params:
        - limit: Maximum number of trades to return (default: 10)
        - mode: Filter by 'paper', 'live', or omit for all trades
    """
    try:
        limit = int(request.args.get('limit', 10))
        trading_mode = request.args.get('mode', None)  # 'paper', 'live', or None

        # Validate trading_mode
        if trading_mode and trading_mode not in ['paper', 'live']:
            return jsonify({'error': 'Invalid mode. Use "paper" or "live"'}), 400

        trades = data_provider.get_trades(limit=limit, trading_mode=trading_mode)

        # Return with metadata
        return jsonify({
            'trades': trades,
            'count': len(trades),
            'filter': {
                'limit': limit,
                'mode': trading_mode or 'all'
            }
        })
    except Exception as e:
        logger.error(f"Error in /api/trades: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/performance')
def api_performance():
    """Get performance statistics"""
    try:
        performance = data_provider.get_performance()
        return jsonify(performance)
    except Exception as e:
        logger.error(f"Error in /api/performance: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/risk')
def api_risk():
    """Get risk management status"""
    try:
        risk = data_provider.get_risk_status()
        return jsonify(risk)
    except Exception as e:
        logger.error(f"Error in /api/risk: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'adx-dashboard', 'timestamp': datetime.now().isoformat()})


if __name__ == '__main__':
    logger.info("="*80)
    logger.info("🚀 ADX STRATEGY v2.0 - DASHBOARD SERVER")
    logger.info("="*80)
    logger.info("📊 Dashboard URL: https://dev.ueipab.edu.ve:5900")
    logger.info("📊 Local Access: http://localhost:5900")
    logger.info("⌨️  Press Ctrl+C to stop")
    logger.info("="*80)

    # SSL certificate paths (using existing Let's Encrypt certificates)
    ssl_cert = '/etc/letsencrypt/live/dev.ueipab.edu.ve/fullchain.pem'
    ssl_key = '/etc/letsencrypt/live/dev.ueipab.edu.ve/privkey.pem'

    # Run Flask app with SSL
    app.run(host='0.0.0.0', port=5900, debug=False,
            ssl_context=(ssl_cert, ssl_key))
