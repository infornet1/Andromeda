#!/usr/bin/env python3
"""
Live Paper Trading Bot for ADX Strategy v2.0
Runs the complete trading system in real-time with live market data
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

import time
import signal
import json
from datetime import datetime, timedelta
from typing import Dict, Optional
import pandas as pd
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv('config/.env')

# Import all components
from src.api.bingx_api import BingXAPI
from src.indicators.adx_engine import ADXEngine
from src.signals.signal_generator import SignalGenerator
from src.signals.signal_filters import SignalFilters
from src.risk.position_sizer import PositionSizer
from src.risk.risk_manager import RiskManager
from src.execution.order_executor import OrderExecutor
from src.execution.position_manager import PositionManager
from src.execution.paper_trader import PaperTrader
from src.monitoring.dashboard import Dashboard
from src.monitoring.performance_tracker import PerformanceTracker
from src.monitoring.alerts import AlertSystem, AlertType, AlertLevel
from src.monitoring.system_monitor import SystemMonitor
from adx_email_notifier import ADXEmailNotifier
from adx_hourly_reporter import ADXHourlyReporter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/live_trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LiveTradingBot:
    """
    Live Paper Trading Bot

    Features:
    - Real-time signal generation from live data
    - Automatic position management
    - Risk controls enforcement
    - Live monitoring dashboard
    - Performance tracking
    - Alert notifications
    """

    def __init__(self, config_file: str = 'config_live.json', mode: str = 'paper'):
        """
        Initialize live trading bot

        Args:
            config_file: Path to configuration file
            mode: Trading mode - 'paper' or 'live' (default: 'paper')
        """

        self.mode = mode.lower()

        logger.info("="*80)
        if self.mode == 'live':
            logger.warning("🔴 ADX STRATEGY v2.0 - LIVE TRADING MODE")
            logger.warning("⚠️  REAL MONEY AT RISK ⚠️")
        else:
            logger.info("📊 ADX STRATEGY v2.0 - PAPER TRADING MODE")
        logger.info("="*80)

        # Load configuration
        self.config = self._load_config(config_file)

        # Initialize components
        self._initialize_components()

        # Bot state
        self.running = False
        self.start_time = None
        self.last_signal_check = None
        self.last_hourly_report = None
        self.signal_check_interval = self.config.get('signal_check_interval', 300)  # 5 minutes
        self.hourly_report_interval = 3600  # 1 hour in seconds

        # Restore previous session data
        self._restore_previous_session()

        logger.info("✅ Live Trading Bot initialized successfully")

    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from file"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"✅ Configuration loaded from {config_file}")
            return config
        except FileNotFoundError:
            logger.warning(f"⚠️  Config file not found, using defaults")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Get default configuration"""
        return {
            'initial_capital': 100.0,
            'leverage': 5,
            'risk_per_trade': 2.0,
            'daily_loss_limit': 5.0,
            'max_drawdown': 15.0,
            'max_positions': 2,
            'consecutive_loss_limit': 3,
            'symbol': 'BTC-USDT',
            'timeframe': '5m',
            'signal_check_interval': 300,
            'adx_period': 14,
            'adx_threshold': 25,
            'enable_short_bias': True,
            'short_bias_multiplier': 1.5
        }

    def _initialize_components(self):
        """Initialize all trading components"""

        logger.info("Initializing components...")

        cfg = self.config

        # API Client (load credentials from environment)
        api_key = os.getenv('BINGX_API_KEY')
        api_secret = os.getenv('BINGX_API_SECRET')

        if not api_key or not api_secret:
            logger.warning("⚠️  BingX API credentials not found, using demo mode")
            self.api = None
        else:
            self.api = BingXAPI(api_key=api_key, api_secret=api_secret)
            logger.info("  ✅ BingX API initialized")

        # ADX Engine
        self.adx_engine = ADXEngine(period=cfg.get('adx_period', 14))
        logger.info("  ✅ ADX Engine initialized")

        # Signal Generator with v2.2 improvements
        # CRITICAL FIX #2: Pass all v2.2 parameters including api_client for MTF
        self.signal_gen = SignalGenerator(
            adx_threshold=cfg.get('adx_threshold', 25),
            min_confidence=cfg.get('min_confidence', 0.6),
            multi_timeframe_enabled=cfg.get('multi_timeframe', {}).get('enabled', True),
            rsi_enabled=cfg.get('rsi', {}).get('enabled', True),
            rsi_period=cfg.get('rsi', {}).get('period', 14),
            rsi_long_range=tuple(cfg.get('rsi', {}).get('long_range', [50, 70])),
            rsi_short_range=tuple(cfg.get('rsi', {}).get('short_range', [30, 50])),
            api_client=self.api  # Enable multi-timeframe confirmation
        )
        logger.info("  ✅ Signal Generator initialized (v2.2: MTF + RSI)")

        # Signal Filters
        self.signal_filters = SignalFilters(
            enable_short_bias=cfg.get('enable_short_bias', True),
            short_bias_multiplier=cfg.get('short_bias_multiplier', 1.5),
            min_confidence=cfg.get('min_confidence', 0.6)
        )
        logger.info("  ✅ Signal Filters initialized")

        # Risk Manager
        self.risk_mgr = RiskManager(
            initial_capital=cfg.get('initial_capital', 100.0),
            daily_loss_limit_percent=cfg.get('daily_loss_limit', 5.0),
            max_drawdown_percent=cfg.get('max_drawdown', 15.0),
            max_concurrent_positions=cfg.get('max_positions', 2),
            consecutive_loss_limit=cfg.get('consecutive_loss_limit', 3)
        )
        logger.info("  ✅ Risk Manager initialized")

        # Position Sizer with v2.2 slippage protection
        position_cfg = cfg.get('position_sizing', {})
        self.sizer = PositionSizer(
            initial_capital=cfg.get('initial_capital', 100.0),
            risk_per_trade_percent=cfg.get('risk_per_trade', 2.0),
            leverage=cfg.get('leverage', 5),
            slippage_buffer_percent=position_cfg.get('slippage_buffer_percent', 0.5),
            max_position_value_percent=position_cfg.get('max_position_value_percent', 10.0),
            min_position_size_usd=position_cfg.get('min_position_size_usd', 20.0)
        )
        logger.info("  ✅ Position Sizer initialized (v2.2: Slippage Protection)")

        # Order Executor
        self.executor = OrderExecutor(
            api_client=self.api,
            enable_live_trading=False  # PAPER TRADING MODE
        )
        logger.info("  ✅ Order Executor initialized (PAPER MODE)")

        # Position Manager with v2.2 trailing stops
        trailing_cfg = cfg.get('trailing_stop', {})
        self.position_mgr = PositionManager(
            order_executor=self.executor,
            enable_trailing_stop=trailing_cfg.get('enabled', True),
            trailing_stop_activation_percent=trailing_cfg.get('activation_percent', 1.0),
            trailing_stop_atr_multiplier=trailing_cfg.get('atr_multiplier', 1.5),
            breakeven_activation_percent=trailing_cfg.get('breakeven_activation_percent', 0.5)
        )
        logger.info("  ✅ Position Manager initialized (v2.2: Trailing Stops)")

        # Initialize Trader (Paper or Live based on mode)
        if self.mode == 'live':
            # LIVE TRADING MODE - Real BingX exchange
            from src.execution.live_trader_bingx import LiveTraderBingX

            logger.warning("  🔴 Initializing LIVE TRADER...")
            logger.warning("  ⚠️  REAL MONEY WILL BE USED")

            api_key = os.getenv('BINGX_API_KEY')
            api_secret = os.getenv('BINGX_API_SECRET')

            if not api_key or not api_secret:
                raise ValueError("BingX API credentials not found in .env file")

            self.trader = LiveTraderBingX(
                api_key=api_key,
                api_secret=api_secret,
                leverage=cfg.get('leverage', 5),
                order_executor=self.executor,
                position_manager=self.position_mgr,
                risk_manager=self.risk_mgr,
                symbol=cfg.get('symbol', 'BTC-USDT')
            )
            logger.warning("  ✅ Live Trader initialized - LIVE MODE ACTIVE")

        else:
            # PAPER TRADING MODE - Simulation
            self.trader = PaperTrader(
                initial_balance=cfg.get('initial_capital', 100.0),
                leverage=cfg.get('leverage', 5),
                order_executor=self.executor,
                position_manager=self.position_mgr,
                risk_manager=self.risk_mgr
            )
            logger.info("  ✅ Paper Trader initialized")

        # Monitoring
        self.dashboard = Dashboard(
            paper_trader=self.trader,
            position_manager=self.position_mgr,
            order_executor=self.executor,
            risk_manager=self.risk_mgr
        )
        logger.info("  ✅ Dashboard initialized")

        self.perf_tracker = PerformanceTracker(
            paper_trader=self.trader,
            position_manager=self.position_mgr,
            risk_manager=self.risk_mgr
        )
        logger.info("  ✅ Performance Tracker initialized")

        self.alerts = AlertSystem(
            enable_console=True,
            enable_file=True,
            log_file='logs/alerts.log'
        )
        logger.info("  ✅ Alert System initialized")

        self.monitor = SystemMonitor(
            paper_trader=self.trader,
            position_manager=self.position_mgr,
            order_executor=self.executor,
            risk_manager=self.risk_mgr,
            api_client=self.api
        )
        logger.info("  ✅ System Monitor initialized")

        # Email Notifier
        try:
            self.email_notifier = ADXEmailNotifier()
            logger.info("  ✅ Email Notifier initialized")
        except Exception as e:
            logger.warning(f"  ⚠️  Email Notifier disabled: {e}")
            self.email_notifier = None

        # Hourly Reporter
        try:
            self.hourly_reporter = ADXHourlyReporter()
            logger.info("  ✅ Hourly Reporter initialized")
        except Exception as e:
            logger.warning(f"  ⚠️  Hourly Reporter disabled: {e}")
            self.hourly_reporter = None

        # Validate v2.2 features are properly enabled
        self._validate_v2_2_features()

    def _validate_v2_2_features(self):
        """
        Validate that v2.2 improvements are properly configured and enabled
        Fails fast if critical features are missing
        """
        logger.info("\n" + "=" * 70)
        logger.info("VALIDATING v2.2 FEATURES")
        logger.info("=" * 70)

        errors = []
        warnings = []

        # Check RSI enabled
        if not self.signal_gen.rsi_enabled:
            errors.append("❌ RSI filter is DISABLED (should be enabled in v2.2)")
        else:
            logger.info("✅ RSI Filter: ENABLED")
            logger.info(f"   - Period: {self.signal_gen.rsi_period}")
            logger.info(f"   - LONG range: {self.signal_gen.rsi_long_range}")
            logger.info(f"   - SHORT range: {self.signal_gen.rsi_short_range}")

        # Check MTF enabled
        if not self.signal_gen.multi_timeframe_enabled:
            errors.append("❌ Multi-timeframe confirmation is DISABLED")
        else:
            logger.info("✅ Multi-Timeframe Confirmation: ENABLED")

        # Check API client provided for MTF
        if self.signal_gen.multi_timeframe_enabled and not self.signal_gen.api_client:
            errors.append("❌ MTF enabled but no API client provided (MTF won't work)")
        elif self.signal_gen.multi_timeframe_enabled:
            logger.info("   - API client: Connected")

        # Check trailing stops enabled
        if not self.position_mgr.enable_trailing_stop:
            errors.append("❌ Trailing stops are DISABLED")
        else:
            logger.info("✅ Trailing Stops: ENABLED")
            logger.info(f"   - Breakeven at: {self.position_mgr.breakeven_activation_percent}%")
            logger.info(f"   - Trailing at: {self.position_mgr.trailing_stop_activation_percent}%")
            logger.info(f"   - ATR multiplier: {self.position_mgr.trailing_stop_atr_multiplier}x")

        # Check slippage buffer
        if self.sizer.slippage_buffer_percent <= 0:
            warnings.append("⚠️  Slippage buffer is 0% (no slippage protection)")
        else:
            logger.info("✅ Slippage Protection: ENABLED")
            logger.info(f"   - Buffer: {self.sizer.slippage_buffer_percent * 100:.0f}%")

        # Check position value cap
        if self.sizer.max_position_value_percent >= 20:
            warnings.append(f"⚠️  Position value cap is {self.sizer.max_position_value_percent}% (risky, recommend 10%)")
        else:
            logger.info("✅ Position Value Cap: ENABLED")
            logger.info(f"   - Max position: {self.sizer.max_position_value_percent}% of capital")

        # Check leverage
        if self.sizer.leverage >= 5:
            warnings.append(f"⚠️  Leverage is {self.sizer.leverage}x (high risk, recommend 3x)")
        else:
            logger.info(f"✅ Leverage: {self.sizer.leverage}x (safe)")

        # Check circuit breaker
        circuit_breaker_limit = self.risk_mgr.consecutive_loss_limit
        if circuit_breaker_limit > 5:
            warnings.append(f"⚠️  Circuit breaker set to {circuit_breaker_limit} losses (recommend 3-5)")
        else:
            logger.info(f"✅ Circuit Breaker: {circuit_breaker_limit} consecutive losses")

        logger.info("=" * 70)

        # Print warnings
        if warnings:
            logger.warning("\nWARNINGS:")
            for warning in warnings:
                logger.warning(f"  {warning}")

        # Print errors and fail if any
        if errors:
            logger.critical("\n🚨 v2.2 FEATURE VALIDATION FAILED:")
            for error in errors:
                logger.critical(f"  {error}")
            logger.critical("\nBot startup aborted. Fix configuration and try again.")
            raise RuntimeError("v2.2 features not properly configured")
        else:
            logger.info("\n✅ All v2.2 features validated successfully!")
            logger.info("=" * 70 + "\n")

    def _restore_previous_session(self):
        """Restore trade history and account state from previous session"""
        snapshot_file = 'logs/final_snapshot.json'

        if not os.path.exists(snapshot_file):
            logger.info("  No previous session to restore")
            return

        try:
            with open(snapshot_file, 'r') as f:
                snapshot = json.load(f)

            # Note: PaperTrader now restores balance and trades from database automatically
            # No need to restore from snapshot - database is source of truth

            # Just log the current balance (already restored by PaperTrader)
            logger.info(f"  ✅ Current balance: ${self.trader.balance:.2f} (restored from database)")

            # Restore risk manager state
            risk = snapshot.get('risk', {})
            if risk:
                self.risk_mgr.consecutive_wins = risk.get('consecutive_wins', 0)
                self.risk_mgr.consecutive_losses = risk.get('consecutive_losses', 0)
                logger.info(f"  ✅ Restored risk state (streak: {self.risk_mgr.consecutive_wins}W / {self.risk_mgr.consecutive_losses}L)")

        except Exception as e:
            logger.warning(f"  ⚠️  Could not restore previous session: {e}")

    def start(self, duration_hours: int = 48):
        """Start live paper trading"""

        logger.info("="*80)
        logger.info(f"🚀 STARTING LIVE PAPER TRADING - {duration_hours} HOUR SESSION")
        logger.info("="*80)

        self.running = True
        self.start_time = datetime.now()
        end_time = self.start_time + timedelta(hours=duration_hours)

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info(f"Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"End Time:   {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration:   {duration_hours} hours")
        logger.info("="*80)

        # Send startup alert
        self.alerts.send_alert(
            AlertType.SYSTEM_ERROR,  # Using generic type
            AlertLevel.INFO,
            f"Live trading bot started - {duration_hours}h session",
            {'start_time': self.start_time.isoformat(), 'duration_hours': duration_hours}
        )

        # Main trading loop
        iteration = 0
        while self.running and datetime.now() < end_time:
            try:
                iteration += 1

                # 1. Fetch latest market data
                current_price = self._fetch_current_price()

                # 2. Update open positions with current price
                self._update_positions(current_price)

                # 3. Check for new signals (every 5 minutes)
                if self._should_check_signals():
                    self._check_and_execute_signals()

                # 4. Send hourly market report (every hour)
                if self._should_send_hourly_report():
                    self._send_hourly_report()

                # 5. Display dashboard (every minute)
                if iteration % 12 == 0:  # Every 60 seconds
                    self._display_status()

                # 6. Capture performance snapshot
                if iteration % 60 == 0:  # Every 5 minutes
                    self.perf_tracker.capture_snapshot()

                # 7. System health check
                if iteration % 120 == 0:  # Every 10 minutes
                    self._health_check()

                # 8. Export snapshot for dashboard (every cycle)
                self.dashboard.export_snapshot('logs/final_snapshot.json')

                # Wait 5 seconds before next iteration
                time.sleep(5)

            except KeyboardInterrupt:
                logger.info("\n⚠️  Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}", exc_info=True)
                self.alerts.system_error(str(e))
                time.sleep(10)  # Wait before retry

        # Cleanup and final report
        self._shutdown()

    def _fetch_current_price(self) -> float:
        """Fetch current market price"""
        if self.api is None:
            # Demo mode - simulate realistic price movement
            import random
            base_price = 112000.0
            volatility = random.gauss(0, 100)  # ±100 variance
            return base_price + volatility

        try:
            ticker = self.api.get_ticker_price(self.config.get('symbol', 'BTC-USDT'))
            if ticker and 'price' in ticker:
                return float(ticker['price'])
        except Exception as e:
            logger.error(f"Error fetching price: {e}")

        # Return default if error
        return 112000.0

    def _update_positions(self, current_price: float):
        """Update open positions with current price"""
        # First, reconcile positions with BingX exchange
        self._reconcile_positions_with_bingx()

        # Then update positions with current price
        self.trader.monitor_positions(current_price)

    def _reconcile_positions_with_bingx(self):
        """
        Reconcile bot-tracked positions with actual BingX positions
        Closes any positions in bot memory that don't exist on exchange
        """
        if not self.api or self.mode != 'live':
            return  # Only reconcile in live mode with API access

        try:
            # Get actual positions from BingX
            bingx_positions = self.api.get_positions(self.config.get('symbol', 'BTC-USDT'))
            bingx_position_ids = set()

            # Create lookup of BingX positions by side
            for pos in bingx_positions:
                side = pos['side']
                bingx_position_ids.add(f"{pos['symbol']}_{side}")

            # Get bot-tracked positions
            bot_positions = self.position_mgr.get_open_positions()

            # Check each bot position against BingX
            for bot_pos in bot_positions:
                bot_id = f"{bot_pos['symbol']}_{bot_pos['side']}"

                # If position doesn't exist on BingX, close it in bot
                if bot_id not in bingx_position_ids:
                    logger.warning(f"⚠️  Position {bot_pos['position_id']} not found on BingX - reconciling")
                    logger.info(f"   Closing stale position: {bot_pos['side']} @ ${bot_pos['entry_price']:.2f}")

                    # Close position in bot memory
                    current_price = self._fetch_current_price()
                    self.position_mgr.close_position(
                        bot_pos['position_id'],
                        current_price,
                        exit_reason='EXCHANGE_CLOSED_RECONCILIATION'
                    )

                    logger.info(f"   ✅ Position reconciled and closed in bot")

        except Exception as e:
            logger.error(f"Error during position reconciliation: {e}", exc_info=True)

    def _should_check_signals(self) -> bool:
        """Check if it's time to look for new signals"""
        if self.last_signal_check is None:
            return True

        elapsed = (datetime.now() - self.last_signal_check).total_seconds()
        return elapsed >= self.signal_check_interval

    def _should_send_hourly_report(self) -> bool:
        """Check if it's time to send hourly report"""
        if self.last_hourly_report is None:
            return True

        elapsed = (datetime.now() - self.last_hourly_report).total_seconds()
        return elapsed >= self.hourly_report_interval

    def _check_and_execute_signals(self):
        """Check for trading signals and execute if valid"""

        logger.info("🔍 Checking for trading signals...")
        self.last_signal_check = datetime.now()

        try:
            # Fetch recent klines
            if self.api is None:
                logger.info("  Demo mode - skipping signal generation (no live data)")
                return

            klines = self.api.get_kline_data(
                symbol=self.config.get('symbol', 'BTC-USDT'),
                interval=self.config.get('timeframe', '5m'),
                limit=200
            )

            if not klines:
                logger.warning("No kline data received")
                return

            # Convert to DataFrame
            df = pd.DataFrame(klines)

            # Calculate ADX indicators
            df = self.adx_engine.analyze_dataframe(df)

            # CRITICAL FIX #1: Calculate RSI before signal generation (v2.2)
            if self.signal_gen.rsi_enabled:
                df['rsi'] = self.signal_gen.calculate_rsi(df['close'])
                logger.debug(f"  RSI calculated: latest = {df['rsi'].iloc[-1]:.1f}")

            # Calculate ATR for signal generation
            atr_values = self.signal_gen.calculate_atr(df['high'], df['low'], df['close'])

            # Scan for signals in recent candles (last 10)
            signals = []
            for i in range(max(0, len(df) - 10), len(df)):
                row = df.iloc[i]
                atr = atr_values.iloc[i] if not pd.isna(atr_values.iloc[i]) else 0

                # Pass symbol for multi-timeframe confirmation
                signal = self.signal_gen.generate_entry_signal(row, atr, self.config.get('symbol', 'BTC-USDT'))
                if signal:
                    signal['timestamp'] = row['timestamp']
                    signals.append(signal)

            if not signals:
                logger.info("  No signals generated")
                return

            logger.info(f"  Generated {len(signals)} raw signals")

            # Apply filters
            passed_signals, filtered_out = self.signal_filters.filter_signals(signals, df)

            if not passed_signals:
                logger.info("  All signals filtered out")
                return

            logger.info(f"  {len(passed_signals)} signals passed filters")

            # Execute most recent valid signal
            if passed_signals:
                latest_signal = passed_signals[-1]  # Take most recent
                self._execute_signal(latest_signal, df.iloc[-1]['close'])

        except Exception as e:
            logger.error(f"Error in signal generation: {e}", exc_info=True)

    def _execute_signal(self, signal: Dict, current_price: float):
        """Execute trading signal"""

        logger.info(f"📊 Executing {signal['side']} signal (confidence: {signal['confidence']*100:.1f}%)")

        # Calculate position size
        position_size = self.sizer.calculate_position_size(
            current_price,
            signal['stop_loss']
        )

        # Execute via trader (live or paper)
        result = self.trader.execute_signal(signal, current_price, position_size)

        if result:
            # Get position ID from result (structure differs between live/paper trader)
            position_id = result.get('position_id') or result.get('position', {}).get('position_id')

            if position_id:
                # Send alert
                self.alerts.position_opened(
                    position_id,
                    signal['side'],
                    current_price,
                    position_size['position_size_btc']
                )
            logger.info(f"  ✅ Signal executed successfully")

            # Send email notification
            if self.email_notifier:
                try:
                    # Extract ADX data from signal if available
                    adx_data = {
                        'adx': signal.get('adx', 0),
                        'plus_di': signal.get('plus_di', 0),
                        'minus_di': signal.get('minus_di', 0),
                        'di_spread': signal.get('di_spread', 0),
                        'adx_slope': signal.get('adx_slope', 0)
                    }

                    self.email_notifier.send_signal_alert(signal, current_price, adx_data)
                    logger.info("  📧 Email notification sent")
                except Exception as e:
                    logger.error(f"  ❌ Failed to send email notification: {e}")
        else:
            logger.warning(f"  ❌ Signal execution failed or rejected")

    def _display_status(self):
        """Display current status"""
        print("\n" + "="*80)
        print(self.dashboard.get_status_bar())
        print("="*80 + "\n")

    def _send_hourly_report(self):
        """Send hourly market analysis report"""
        if not self.hourly_reporter:
            return

        logger.info("📧 Sending hourly market report...")
        self.last_hourly_report = datetime.now()

        try:
            # Fetch latest data for report
            if self.api is None:
                logger.info("  Demo mode - skipping hourly report (no live data)")
                return

            klines = self.api.get_kline_data(
                symbol=self.config.get('symbol', 'BTC-USDT'),
                interval=self.config.get('timeframe', '5m'),
                limit=200
            )

            if not klines:
                logger.warning("  No kline data for hourly report")
                return

            # Convert to DataFrame and add indicators
            df = pd.DataFrame(klines)
            df = self.adx_engine.analyze_dataframe(df)

            # Send report
            success = self.hourly_reporter.send_hourly_report(
                df,
                paper_trader=self.trader,
                position_manager=self.position_mgr
            )

            if success:
                logger.info("  ✅ Hourly report sent successfully")
            else:
                logger.warning("  ⚠️  Failed to send hourly report")

        except Exception as e:
            logger.error(f"  ❌ Error sending hourly report: {e}", exc_info=True)

    def _health_check(self):
        """Perform system health check"""
        health = self.monitor.check_health()

        if health['overall_status'] != 'ONLINE':
            self.alerts.send_alert(
                AlertType.SYSTEM_ERROR,
                AlertLevel.WARNING,
                f"System health degraded: {health['overall_status']}",
                health
            )

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("\n🛑 Shutdown signal received")
        self.running = False

    def _shutdown(self):
        """Clean shutdown and final report"""

        logger.info("="*80)
        logger.info("🛑 SHUTTING DOWN LIVE TRADING BOT")
        logger.info("="*80)

        # Close any open positions
        if hasattr(self, 'position_mgr') and self.position_mgr:
            open_positions = self.position_mgr.get_open_positions()
            if open_positions:
                logger.info(f"Closing {len(open_positions)} open positions...")
                current_price = self._fetch_current_price()
                for pos in open_positions:
                    try:
                        if hasattr(self.trader, '_close_position_on_exchange'):
                            self.trader._close_position_on_exchange(pos, current_price, 'SHUTDOWN')
                    except Exception as e:
                        logger.warning(f"Failed to close position: {e}")

        # Generate final reports
        logger.info("\n" + "="*80)
        logger.info("FINAL PERFORMANCE REPORT")
        logger.info("="*80)

        print(self.perf_tracker.generate_performance_report())

        # Paper trading summary (only if paper mode)
        if hasattr(self.trader, 'get_paper_trading_summary'):
            print(self.trader.get_paper_trading_summary())

        # Session summary
        if self.start_time:
            session_duration = datetime.now() - self.start_time
            hours = session_duration.total_seconds() / 3600

            logger.info("\n" + "="*80)
            logger.info("SESSION SUMMARY")
            logger.info("="*80)
            logger.info(f"Session Duration: {hours:.2f} hours")
            logger.info(f"Signals Checked: {iteration if 'iteration' in locals() else 'N/A'}")
            # Get trade count
            if hasattr(self.trader, 'get_performance_stats'):
                stats = self.trader.get_performance_stats()
                logger.info(f"Trades Executed: {stats.get('total_trades', 0)}")
                logger.info(f"Final Balance: ${self.trader.balance:.2f}")
            logger.info("="*80)

        # Save final snapshot
        self.dashboard.export_snapshot('logs/final_snapshot.json')
        logger.info("📄 Final snapshot saved to logs/final_snapshot.json")

        logger.info("\n✅ Shutdown complete")


if __name__ == "__main__":
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='ADX Strategy v2.0 - Trading Bot')
    parser.add_argument('--mode', type=str, default='paper',
                       choices=['paper', 'live'],
                       help='Trading mode: paper (simulation) or live (real money)')
    parser.add_argument('--config', type=str, default='config_live.json',
                       help='Configuration file path')
    parser.add_argument('--duration', type=int, default=48,
                       help='Trading duration in hours')
    parser.add_argument('--skip-confirmation', action='store_true',
                       help='Skip live trading confirmation (for systemd service)')

    args = parser.parse_args()

    # Create logs directory
    os.makedirs('logs', exist_ok=True)

    # Safety confirmation for live mode
    if args.mode == 'live':
        print("="*80)
        print("⚠️  WARNING: LIVE TRADING MODE ⚠️")
        print("="*80)
        print("You are about to start LIVE trading with REAL MONEY.")
        print("All trades will be executed on BingX exchange.")
        print("Losses are real and irreversible.")
        print("")
        print("Make sure you:")
        print("  1. Have funded your BingX account")
        print("  2. Have set appropriate risk limits in config")
        print("  3. Will monitor the bot closely")
        print("  4. Have tested with paper trading first")
        print("="*80)

        if not args.skip_confirmation:
            confirmation = input("Type 'START LIVE TRADING' to proceed: ")

            if confirmation != 'START LIVE TRADING':
                print("❌ Live trading cancelled")
                sys.exit(0)
        else:
            print("⚠️  Confirmation skipped (running as service)")

        print("\n✅ Starting live trading...")
        time.sleep(2)

    # Create bot
    bot = LiveTradingBot(config_file=args.config, mode=args.mode)

    # Start trading
    bot.start(duration_hours=args.duration)
