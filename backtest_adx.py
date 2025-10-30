#!/usr/bin/env python3
"""
Comprehensive Backtesting Framework for ADX Strategy v2.0
Tests strategy on historical data (3-6 months) before live trading
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import json

# Import strategy components
from src.api.bingx_api import BingXAPI
from src.indicators.adx_engine import ADXEngine
from src.signals.signal_generator import SignalGenerator
from src.signals.signal_filters import SignalFilters
from src.risk.position_sizer import PositionSizer
from src.risk.risk_manager import RiskManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ADXBacktester:
    """
    Comprehensive Backtesting Engine for ADX Strategy

    Features:
    - Historical data testing (3-6 months)
    - Full strategy simulation with all components
    - Performance metrics calculation
    - Market condition analysis
    - Parameter optimization support
    """

    def __init__(self, config: Dict):
        """
        Initialize backtester

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.initial_capital = config.get('initial_capital', 160.0)
        self.leverage = config.get('leverage', 5)
        self.risk_per_trade = config.get('risk_per_trade', 2.0)

        # Initialize components
        self.adx_engine = ADXEngine(period=config.get('adx_period', 14))
        self.signal_gen = SignalGenerator(
            adx_threshold=config.get('adx_threshold', 25),
            min_confidence=config.get('min_confidence', 0.6)
        )
        self.signal_filters = SignalFilters(
            enable_short_bias=config.get('enable_short_bias', True),
            short_bias_multiplier=config.get('short_bias_multiplier', 1.5)
        )
        self.sizer = PositionSizer(
            initial_capital=self.initial_capital,
            risk_per_trade_percent=self.risk_per_trade,
            leverage=self.leverage
        )

        # Backtest state
        self.trades = []
        self.balance = self.initial_capital
        self.peak_balance = self.initial_capital
        self.equity_curve = []

        logger.info(f"Backtester initialized: ${self.initial_capital} @ {self.leverage}x leverage")

    def fetch_historical_data(self, symbol: str, interval: str, days: int) -> pd.DataFrame:
        """
        Fetch historical kline data from BingX

        Args:
            symbol: Trading pair (e.g., 'BTC-USDT')
            interval: Timeframe (e.g., '5m', '15m', '1h')
            days: Number of days to fetch

        Returns:
            DataFrame with OHLCV data
        """
        logger.info(f"Fetching {days} days of {interval} data for {symbol}...")

        # Initialize API
        api_key = os.getenv('BINGX_API_KEY')
        api_secret = os.getenv('BINGX_API_SECRET')

        if not api_key or not api_secret:
            raise ValueError("BingX API credentials not found in .env file")

        api = BingXAPI(api_key=api_key, api_secret=api_secret)

        # Calculate limit based on interval and days
        interval_minutes = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '2h': 120, '4h': 240, '6h': 360, '12h': 720, '1d': 1440
        }

        minutes_per_candle = interval_minutes.get(interval, 5)
        total_candles = (days * 24 * 60) // minutes_per_candle

        # BingX limit is 1000 per request, so we need multiple requests
        all_klines = []
        max_limit = 1000

        end_time = int(datetime.now().timestamp() * 1000)

        while len(all_klines) < total_candles:
            limit = min(max_limit, total_candles - len(all_klines))

            klines = api.get_kline_data(symbol=symbol, interval=interval, limit=limit, end_time=end_time)

            if not klines:
                break

            all_klines = klines + all_klines
            end_time = int(klines[0]['timestamp']) - 1

            logger.info(f"Fetched {len(all_klines)} / {total_candles} candles...")

            if len(klines) < limit:
                break

        df = pd.DataFrame(all_klines)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        logger.info(f"✅ Fetched {len(df)} candles from {df['timestamp'].min()} to {df['timestamp'].max()}")

        return df

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare data with indicators

        Args:
            df: Raw OHLCV dataframe

        Returns:
            DataFrame with indicators calculated
        """
        logger.info("Calculating indicators...")

        # Calculate ADX indicators
        df = self.adx_engine.analyze_dataframe(df)

        # Calculate ATR for signal generation
        df['atr'] = self.signal_gen.calculate_atr(df['high'], df['low'], df['close'])

        # Calculate volatility metrics
        df['volatility'] = df['close'].rolling(window=20).std()
        df['avg_volume'] = df['volume'].rolling(window=20).mean()

        logger.info(f"✅ Indicators calculated for {len(df)} candles")

        return df

    def run_backtest(self, df: pd.DataFrame) -> Dict:
        """
        Run backtest on historical data

        Args:
            df: Prepared dataframe with indicators

        Returns:
            Backtest results dictionary
        """
        logger.info("="*80)
        logger.info("STARTING BACKTEST")
        logger.info("="*80)

        self.trades = []
        self.balance = self.initial_capital
        self.peak_balance = self.initial_capital
        self.equity_curve = []
        open_position = None

        for i in range(50, len(df)):  # Start after warmup period
            row = df.iloc[i]
            current_time = row['timestamp']
            current_price = row['close']

            # Update equity curve
            unrealized_pnl = 0
            if open_position:
                if open_position['side'] == 'LONG':
                    unrealized_pnl = (current_price - open_position['entry_price']) * open_position['quantity']
                else:
                    unrealized_pnl = (open_position['entry_price'] - current_price) * open_position['quantity']

            equity = self.balance + unrealized_pnl
            self.equity_curve.append({
                'timestamp': current_time,
                'balance': self.balance,
                'equity': equity,
                'price': current_price
            })

            # Update peak balance
            if equity > self.peak_balance:
                self.peak_balance = equity

            # Check exit conditions for open position
            if open_position:
                should_exit, exit_reason = self._check_exit_conditions(open_position, row)

                if should_exit:
                    trade_result = self._close_position(open_position, current_price, exit_reason, current_time)
                    self.trades.append(trade_result)
                    self.balance = trade_result['exit_balance']
                    open_position = None

            # Look for entry signals if no open position
            if not open_position:
                signal = self.signal_gen.generate_entry_signal(row, row['atr'])

                if signal:
                    # Apply filters
                    df_subset = df.iloc[max(0, i-50):i+1]
                    passed_signals, _ = self.signal_filters.filter_signals([signal], df_subset)

                    if passed_signals:
                        # Open position
                        open_position = self._open_position(passed_signals[0], current_price, current_time, row)

        # Close any remaining open position
        if open_position:
            trade_result = self._close_position(open_position, df.iloc[-1]['close'], 'END_OF_DATA', df.iloc[-1]['timestamp'])
            self.trades.append(trade_result)
            self.balance = trade_result['exit_balance']

        # Calculate results
        results = self._calculate_results()

        logger.info("="*80)
        logger.info("BACKTEST COMPLETE")
        logger.info("="*80)

        return results

    def _open_position(self, signal: Dict, current_price: float, timestamp, row) -> Dict:
        """Open a new position"""
        # Calculate position size
        position_size = self.sizer.calculate_position_size(
            current_price,
            signal['stop_loss'],
            account_balance=self.balance
        )

        # Apply max loss protection (2% hard cap)
        max_loss_amount = self.balance * 0.02
        if position_size['actual_risk_amount'] > max_loss_amount:
            # Reduce position size
            scale_factor = max_loss_amount / position_size['actual_risk_amount']
            position_size['position_size_btc'] *= scale_factor
            position_size['position_size_usd'] *= scale_factor
            logger.warning(f"Position size reduced by {(1-scale_factor)*100:.1f}% to enforce 2% max loss")

        position = {
            'entry_time': timestamp,
            'entry_price': current_price,
            'side': signal['side'],
            'quantity': position_size['position_size_btc'],
            'stop_loss': signal['stop_loss'],
            'take_profit': signal['take_profit'],
            'entry_balance': self.balance,
            'signal_confidence': signal['confidence'],
            'adx': row['adx'],
            'volatility': row.get('volatility', 0)
        }

        logger.debug(f"📈 Opened {signal['side']} @ ${current_price:.2f}, Size: {position['quantity']:.5f} BTC")

        return position

    def _check_exit_conditions(self, position: Dict, row) -> tuple:
        """Check if position should be closed"""
        current_price = row['close']
        high = row['high']
        low = row['low']

        if position['side'] == 'LONG':
            # Check stop loss
            if low <= position['stop_loss']:
                return True, 'STOP_LOSS'
            # Check take profit
            if high >= position['take_profit']:
                return True, 'TAKE_PROFIT'

        else:  # SHORT
            # Check stop loss
            if high >= position['stop_loss']:
                return True, 'STOP_LOSS'
            # Check take profit
            if low <= position['take_profit']:
                return True, 'TAKE_PROFIT'

        return False, None

    def _close_position(self, position: Dict, exit_price: float, exit_reason: str, timestamp) -> Dict:
        """Close position and calculate P&L"""
        if position['side'] == 'LONG':
            pnl = (exit_price - position['entry_price']) * position['quantity']
        else:
            pnl = (position['entry_price'] - exit_price) * position['quantity']

        pnl_percent = (pnl / position['entry_balance']) * 100

        hold_duration_minutes = (timestamp - position['entry_time']).total_seconds() / 60

        exit_balance = position['entry_balance'] + pnl

        trade_result = {
            'entry_time': position['entry_time'],
            'exit_time': timestamp,
            'side': position['side'],
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'quantity': position['quantity'],
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'exit_reason': exit_reason,
            'entry_balance': position['entry_balance'],
            'exit_balance': exit_balance,
            'hold_duration': hold_duration_minutes,
            'signal_confidence': position['signal_confidence'],
            'adx': position['adx'],
            'volatility': position['volatility']
        }

        emoji = '✅' if pnl > 0 else '❌'
        logger.debug(f"{emoji} Closed {position['side']} @ ${exit_price:.2f}, P&L: ${pnl:+.2f} ({exit_reason})")

        return trade_result

    def _calculate_results(self) -> Dict:
        """Calculate backtest performance metrics"""
        df_trades = pd.DataFrame(self.trades)

        if len(df_trades) == 0:
            return {'error': 'No trades generated'}

        # Basic metrics
        total_trades = len(df_trades)
        wins = df_trades[df_trades['pnl'] > 0]
        losses = df_trades[df_trades['pnl'] <= 0]

        win_rate = len(wins) / total_trades if total_trades > 0 else 0

        total_pnl = df_trades['pnl'].sum()
        total_return_pct = ((self.balance - self.initial_capital) / self.initial_capital) * 100

        # Win/Loss metrics
        avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
        avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
        largest_win = wins['pnl'].max() if len(wins) > 0 else 0
        largest_loss = losses['pnl'].min() if len(losses) > 0 else 0

        # Profit factor
        gross_profit = wins['pnl'].sum() if len(wins) > 0 else 0
        gross_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Expectancy
        expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

        # Drawdown
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['cummax'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['cummax']) / equity_df['cummax'] * 100
        max_drawdown = abs(equity_df['drawdown'].min())

        # Consecutive wins/losses
        df_trades['is_win'] = df_trades['pnl'] > 0
        consecutive_losses = 0
        max_consecutive_losses = 0
        for win in df_trades['is_win']:
            if not win:
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            else:
                consecutive_losses = 0

        # Side performance
        long_trades = df_trades[df_trades['side'] == 'LONG']
        short_trades = df_trades[df_trades['side'] == 'SHORT']

        results = {
            'overview': {
                'initial_capital': self.initial_capital,
                'final_balance': self.balance,
                'total_pnl': total_pnl,
                'total_return_pct': total_return_pct,
                'peak_balance': self.peak_balance,
                'total_trades': total_trades,
                'backtest_duration_days': (df_trades['exit_time'].max() - df_trades['entry_time'].min()).days
            },
            'win_loss': {
                'wins': len(wins),
                'losses': len(losses),
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'largest_win': largest_win,
                'largest_loss': largest_loss,
                'profit_factor': profit_factor,
                'expectancy': expectancy
            },
            'risk': {
                'max_drawdown': max_drawdown,
                'max_consecutive_losses': max_consecutive_losses,
                'sharpe_ratio': self._calculate_sharpe_ratio(df_trades),
                'sortino_ratio': self._calculate_sortino_ratio(df_trades)
            },
            'side_performance': {
                'long': {
                    'trades': len(long_trades),
                    'win_rate': len(long_trades[long_trades['pnl'] > 0]) / len(long_trades) if len(long_trades) > 0 else 0,
                    'total_pnl': long_trades['pnl'].sum() if len(long_trades) > 0 else 0
                },
                'short': {
                    'trades': len(short_trades),
                    'win_rate': len(short_trades[short_trades['pnl'] > 0]) / len(short_trades) if len(short_trades) > 0 else 0,
                    'total_pnl': short_trades['pnl'].sum() if len(short_trades) > 0 else 0
                }
            },
            'trades': df_trades.to_dict('records'),
            'equity_curve': self.equity_curve
        }

        return results

    def _calculate_sharpe_ratio(self, df_trades: pd.DataFrame, risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe Ratio"""
        if len(df_trades) < 2:
            return 0

        returns = df_trades['pnl_percent']
        excess_returns = returns - risk_free_rate

        if returns.std() == 0:
            return 0

        sharpe = (excess_returns.mean() / returns.std()) * np.sqrt(252)  # Annualized
        return sharpe

    def _calculate_sortino_ratio(self, df_trades: pd.DataFrame, risk_free_rate: float = 0.0) -> float:
        """Calculate Sortino Ratio (only penalizes downside volatility)"""
        if len(df_trades) < 2:
            return 0

        returns = df_trades['pnl_percent']
        excess_returns = returns - risk_free_rate
        downside_returns = returns[returns < 0]

        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0

        sortino = (excess_returns.mean() / downside_returns.std()) * np.sqrt(252)
        return sortino

    def print_results(self, results: Dict):
        """Print formatted backtest results"""
        print("\n" + "="*80)
        print("BACKTEST RESULTS")
        print("="*80)

        overview = results['overview']
        print(f"\nOverview:")
        print(f"  Initial Capital:    ${overview['initial_capital']:,.2f}")
        print(f"  Final Balance:      ${overview['final_balance']:,.2f}")
        print(f"  Total P&L:          ${overview['total_pnl']:+,.2f}")
        print(f"  Total Return:       {overview['total_return_pct']:+.2f}%")
        print(f"  Peak Balance:       ${overview['peak_balance']:,.2f}")
        print(f"  Total Trades:       {overview['total_trades']}")
        print(f"  Duration:           {overview['backtest_duration_days']} days")

        wl = results['win_loss']
        print(f"\nWin/Loss Statistics:")
        print(f"  Wins:               {wl['wins']} ({wl['win_rate']*100:.1f}%)")
        print(f"  Losses:             {wl['losses']}")
        print(f"  Avg Win:            ${wl['avg_win']:.2f}")
        print(f"  Avg Loss:           ${wl['avg_loss']:.2f}")
        print(f"  Largest Win:        ${wl['largest_win']:.2f}")
        print(f"  Largest Loss:       ${wl['largest_loss']:.2f}")
        print(f"  Profit Factor:      {wl['profit_factor']:.2f}")
        print(f"  Expectancy:         ${wl['expectancy']:.2f} per trade")

        risk = results['risk']
        print(f"\nRisk Metrics:")
        print(f"  Max Drawdown:       {risk['max_drawdown']:.2f}%")
        print(f"  Max Consecutive L:  {risk['max_consecutive_losses']}")
        print(f"  Sharpe Ratio:       {risk['sharpe_ratio']:.2f}")
        print(f"  Sortino Ratio:      {risk['sortino_ratio']:.2f}")

        side = results['side_performance']
        print(f"\nSide Performance:")
        print(f"  LONG:  {side['long']['trades']} trades, {side['long']['win_rate']*100:.1f}% WR, ${side['long']['total_pnl']:+.2f} P&L")
        print(f"  SHORT: {side['short']['trades']} trades, {side['short']['win_rate']*100:.1f}% WR, ${side['short']['total_pnl']:+.2f} P&L")

        print("\n" + "="*80)

    def save_results(self, results: Dict, filename: str):
        """Save backtest results to JSON file"""
        # Convert timestamps to strings
        for trade in results['trades']:
            trade['entry_time'] = str(trade['entry_time'])
            trade['exit_time'] = str(trade['exit_time'])

        for equity_point in results['equity_curve']:
            equity_point['timestamp'] = str(equity_point['timestamp'])

        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"✅ Results saved to {filename}")


if __name__ == "__main__":
    print("="*80)
    print("ADX STRATEGY v2.0 - BACKTESTING FRAMEWORK")
    print("="*80)

    # Configuration
    config = {
        'initial_capital': 160.0,
        'leverage': 5,
        'risk_per_trade': 2.0,
        'adx_period': 14,
        'adx_threshold': 25,
        'min_confidence': 0.6,
        'enable_short_bias': True,
        'short_bias_multiplier': 1.5
    }

    # Initialize backtester
    backtester = ADXBacktester(config)

    # Fetch historical data (90 days)
    try:
        print("\nStep 1: Fetching historical data...")
        df = backtester.fetch_historical_data(
            symbol='BTC-USDT',
            interval='5m',
            days=90
        )

        print("\nStep 2: Preparing data with indicators...")
        df = backtester.prepare_data(df)

        print("\nStep 3: Running backtest...")
        results = backtester.run_backtest(df)

        print("\nStep 4: Analyzing results...")
        backtester.print_results(results)

        print("\nStep 5: Saving results...")
        backtester.save_results(results, 'backtest_results.json')

        print("\n✅ Backtest complete!")

    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        print(f"\n❌ Backtest failed: {e}")
