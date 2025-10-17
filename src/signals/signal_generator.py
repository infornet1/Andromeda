#!/usr/bin/env python3
"""
Signal Generator for ADX Strategy v2.0
Implements Trading Latino entry/exit logic with enhancements
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import talib

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SignalGenerator:
    """
    ADX Signal Generator (Trading Latino Method + Enhancements)

    Entry Logic:
    - ADX > threshold (default 25) - Strong trend
    - ADX slope > 0 (trend strengthening)
    - DI crossover confirmed
    - Minimum DI spread
    - Price breakout confirmation

    Exit Logic:
    - ADX < 20 (trend weakening)
    - DI reversal (crossover opposite direction)
    - Stop loss hit (ATR-based)
    - Take profit hit (ATR-based)
    - Timeout (1 hour default)
    """

    def __init__(self,
                 adx_threshold: float = 25.0,
                 adx_weak_threshold: float = 20.0,
                 adx_slope_min: float = 0.5,
                 di_spread_min: float = 5.0,
                 min_confidence: float = 0.6,
                 atr_period: int = 14,
                 sl_atr_multiplier: float = 2.0,
                 tp_atr_multiplier: float = 4.0):
        """
        Initialize signal generator

        Args:
            adx_threshold: Minimum ADX for entry (default 25)
            adx_weak_threshold: ADX exit threshold (default 20)
            adx_slope_min: Minimum ADX slope for entry
            di_spread_min: Minimum DI spread
            min_confidence: Minimum confidence score (0-1)
            atr_period: ATR calculation period
            sl_atr_multiplier: Stop loss ATR multiplier
            tp_atr_multiplier: Take profit ATR multiplier
        """
        self.adx_threshold = adx_threshold
        self.adx_weak_threshold = adx_weak_threshold
        self.adx_slope_min = adx_slope_min
        self.di_spread_min = di_spread_min
        self.min_confidence = min_confidence
        self.atr_period = atr_period
        self.sl_atr_multiplier = sl_atr_multiplier
        self.tp_atr_multiplier = tp_atr_multiplier

        logger.info(f"Signal Generator initialized (ADX threshold: {adx_threshold})")

    def calculate_atr(self, high: pd.Series, low: pd.Series,
                     close: pd.Series) -> pd.Series:
        """Calculate Average True Range"""
        return talib.ATR(high, low, close, timeperiod=self.atr_period)

    def generate_entry_signal(self, row: pd.Series, atr: float) -> Optional[Dict]:
        """
        Generate entry signal based on ADX criteria

        Args:
            row: Current candle data with ADX indicators
            atr: Current ATR value

        Returns:
            Signal dictionary or None
        """
        # Extract ADX indicators
        adx = row.get('adx')
        plus_di = row.get('plus_di')
        minus_di = row.get('minus_di')
        adx_slope = row.get('adx_slope')
        di_spread = abs(plus_di - minus_di) if plus_di and minus_di else 0
        confidence = row.get('confidence', 0)
        close_price = row.get('close')

        # Validate data
        if pd.isna(adx) or pd.isna(plus_di) or pd.isna(minus_di):
            return None

        # Check minimum confidence
        if confidence < self.min_confidence:
            return None

        # LONG Entry Conditions
        long_conditions = (
            adx > self.adx_threshold and              # Strong trend
            adx_slope > self.adx_slope_min and        # Trend strengthening
            plus_di > minus_di and                     # Bullish direction
            di_spread >= self.di_spread_min and       # Clear direction
            confidence >= self.min_confidence          # High confidence
        )

        # SHORT Entry Conditions
        short_conditions = (
            adx > self.adx_threshold and              # Strong trend
            adx_slope > self.adx_slope_min and        # Trend strengthening
            minus_di > plus_di and                     # Bearish direction
            di_spread >= self.di_spread_min and       # Clear direction
            confidence >= self.min_confidence          # High confidence
        )

        signal = None

        if long_conditions:
            # Calculate LONG stop loss and take profit
            stop_loss = close_price - (atr * self.sl_atr_multiplier)
            take_profit = close_price + (atr * self.tp_atr_multiplier)

            signal = {
                'signal_type': 'BUY',
                'side': 'LONG',
                'entry_price': close_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'risk_reward_ratio': self.tp_atr_multiplier / self.sl_atr_multiplier,
                'adx': adx,
                'plus_di': plus_di,
                'minus_di': minus_di,
                'adx_slope': adx_slope,
                'di_spread': di_spread,
                'confidence': confidence,
                'atr': atr,
                'entry_condition': f"ADX={adx:.2f} +DI={plus_di:.2f} -DI={minus_di:.2f} Slope={adx_slope:.2f}",
                'trend_strength': row.get('trend_strength', 'STRONG')
            }

        elif short_conditions:
            # Calculate SHORT stop loss and take profit
            stop_loss = close_price + (atr * self.sl_atr_multiplier)
            take_profit = close_price - (atr * self.tp_atr_multiplier)

            signal = {
                'signal_type': 'SELL',
                'side': 'SHORT',
                'entry_price': close_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'risk_reward_ratio': self.tp_atr_multiplier / self.sl_atr_multiplier,
                'adx': adx,
                'plus_di': plus_di,
                'minus_di': minus_di,
                'adx_slope': adx_slope,
                'di_spread': di_spread,
                'confidence': confidence,
                'atr': atr,
                'entry_condition': f"ADX={adx:.2f} +DI={plus_di:.2f} -DI={minus_di:.2f} Slope={adx_slope:.2f}",
                'trend_strength': row.get('trend_strength', 'STRONG')
            }

        return signal

    def check_exit_conditions(self, signal: Dict, current_row: pd.Series) -> Optional[str]:
        """
        Check if position should be exited

        Args:
            signal: Original entry signal
            current_row: Current candle data

        Returns:
            Exit reason or None
        """
        current_price = current_row.get('close')
        adx = current_row.get('adx')
        plus_di = current_row.get('plus_di')
        minus_di = current_row.get('minus_di')

        if pd.isna(current_price) or pd.isna(adx):
            return None

        side = signal.get('side')
        entry_price = signal.get('entry_price')
        stop_loss = signal.get('stop_loss')
        take_profit = signal.get('take_profit')

        # Check stop loss
        if side == 'LONG' and current_price <= stop_loss:
            return 'STOP_LOSS'
        elif side == 'SHORT' and current_price >= stop_loss:
            return 'STOP_LOSS'

        # Check take profit
        if side == 'LONG' and current_price >= take_profit:
            return 'TAKE_PROFIT'
        elif side == 'SHORT' and current_price <= take_profit:
            return 'TAKE_PROFIT'

        # Check trend weakening
        if adx < self.adx_weak_threshold:
            return 'TREND_WEAK'

        # Check DI reversal
        if side == 'LONG' and minus_di > plus_di:
            return 'DI_REVERSAL'
        elif side == 'SHORT' and plus_di > minus_di:
            return 'DI_REVERSAL'

        return None

    def scan_dataframe_for_signals(self, df: pd.DataFrame) -> List[Dict]:
        """
        Scan dataframe for all entry signals

        Args:
            df: DataFrame with OHLCV and ADX indicators

        Returns:
            List of signal dictionaries
        """
        signals = []

        # Calculate ATR
        atr = self.calculate_atr(df['high'], df['low'], df['close'])

        for idx, row in df.iterrows():
            if pd.isna(atr.iloc[idx]):
                continue

            signal = self.generate_entry_signal(row, atr.iloc[idx])

            if signal:
                # Add timestamp and index
                signal['timestamp'] = row.get('datetime') or row.get('timestamp')
                signal['candle_index'] = idx
                signals.append(signal)

        logger.info(f"Found {len(signals)} signals in {len(df)} candles")
        return signals

    def backtest_signal(self, entry_signal: Dict, df: pd.DataFrame,
                       entry_idx: int, timeout_candles: int = 12) -> Dict:
        """
        Backtest a single signal to determine outcome

        Args:
            entry_signal: Entry signal dictionary
            df: Full dataframe with price data
            entry_idx: Index where signal was generated
            timeout_candles: Maximum candles to hold (default 12 = 1 hour for 5m)

        Returns:
            Signal with outcome (WIN/LOSS/TIMEOUT)
        """
        result = entry_signal.copy()
        result['outcome'] = 'TIMEOUT'
        result['exit_price'] = None
        result['exit_reason'] = 'TIMEOUT'
        result['pnl_percent'] = 0
        result['pnl_amount'] = 0
        result['bars_held'] = 0

        side = entry_signal.get('side')
        entry_price = entry_signal.get('entry_price')
        stop_loss = entry_signal.get('stop_loss')
        take_profit = entry_signal.get('take_profit')

        # Scan forward from entry
        max_idx = min(entry_idx + timeout_candles, len(df) - 1)

        for i in range(entry_idx + 1, max_idx + 1):
            current_row = df.iloc[i]
            current_high = current_row.get('high')
            current_low = current_row.get('low')
            current_close = current_row.get('close')

            # Check exit conditions
            exit_reason = self.check_exit_conditions(entry_signal, current_row)

            if exit_reason:
                result['exit_reason'] = exit_reason
                result['bars_held'] = i - entry_idx

                # Determine exit price based on reason
                if exit_reason == 'STOP_LOSS':
                    result['exit_price'] = stop_loss
                    result['outcome'] = 'LOSS'
                elif exit_reason == 'TAKE_PROFIT':
                    result['exit_price'] = take_profit
                    result['outcome'] = 'WIN'
                else:
                    result['exit_price'] = current_close
                    # Determine WIN/LOSS based on price movement
                    if side == 'LONG':
                        result['outcome'] = 'WIN' if current_close > entry_price else 'LOSS'
                    else:
                        result['outcome'] = 'WIN' if current_close < entry_price else 'LOSS'

                break

            # Check if price hit SL/TP intrabar
            if side == 'LONG':
                if current_low <= stop_loss:
                    result['exit_price'] = stop_loss
                    result['exit_reason'] = 'STOP_LOSS'
                    result['outcome'] = 'LOSS'
                    result['bars_held'] = i - entry_idx
                    break
                elif current_high >= take_profit:
                    result['exit_price'] = take_profit
                    result['exit_reason'] = 'TAKE_PROFIT'
                    result['outcome'] = 'WIN'
                    result['bars_held'] = i - entry_idx
                    break
            else:  # SHORT
                if current_high >= stop_loss:
                    result['exit_price'] = stop_loss
                    result['exit_reason'] = 'STOP_LOSS'
                    result['outcome'] = 'LOSS'
                    result['bars_held'] = i - entry_idx
                    break
                elif current_low <= take_profit:
                    result['exit_price'] = take_profit
                    result['exit_reason'] = 'TAKE_PROFIT'
                    result['outcome'] = 'WIN'
                    result['bars_held'] = i - entry_idx
                    break

        # Calculate P&L if exited
        if result['exit_price']:
            if side == 'LONG':
                pnl_percent = ((result['exit_price'] - entry_price) / entry_price) * 100
            else:  # SHORT
                pnl_percent = ((entry_price - result['exit_price']) / entry_price) * 100

            result['pnl_percent'] = round(pnl_percent, 4)

            # Calculate dollar P&L (assuming $100 capital with 5x leverage)
            capital = 100
            leverage = 5
            position_value = capital * leverage
            result['pnl_amount'] = round((pnl_percent / 100) * position_value, 2)
        else:
            # Timeout - use last candle price
            result['exit_price'] = df.iloc[max_idx].get('close')
            result['bars_held'] = timeout_candles

        return result

    def generate_signal_summary(self, signal: Dict) -> str:
        """Generate human-readable signal summary"""
        signal_type = signal.get('signal_type')
        side = signal.get('side')
        entry = signal.get('entry_price')
        sl = signal.get('stop_loss')
        tp = signal.get('take_profit')
        confidence = signal.get('confidence', 0)
        adx = signal.get('adx')

        summary = f"""
{'='*60}
{signal_type} Signal - {side} Position
{'='*60}
Entry:      ${entry:,.2f}
Stop Loss:  ${sl:,.2f} (-{abs(entry-sl):.2f}, -{abs(entry-sl)/entry*100:.2f}%)
Take Profit: ${tp:,.2f} (+{abs(tp-entry):.2f}, +{abs(tp-entry)/entry*100:.2f}%)
Risk/Reward: {signal.get('risk_reward_ratio', 0):.1f}:1

ADX Analysis:
  ADX:        {adx:.2f}
  +DI:        {signal.get('plus_di'):.2f}
  -DI:        {signal.get('minus_di'):.2f}
  Spread:     {signal.get('di_spread'):.2f}
  Slope:      {signal.get('adx_slope'):.4f}
  Trend:      {signal.get('trend_strength')}

Confidence:   {confidence:.1%}
{'='*60}
"""
        return summary


if __name__ == "__main__":
    # Test script
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from dotenv import load_dotenv
    from src.api.bingx_api import BingXAPI
    from src.indicators.adx_engine import ADXEngine

    load_dotenv('config/.env')

    print("Testing Signal Generator...")

    # 1. Fetch data
    api = BingXAPI(
        api_key=os.getenv('BINGX_API_KEY'),
        api_secret=os.getenv('BINGX_API_SECRET')
    )

    klines = api.get_kline_data("BTC-USDT", "5m", limit=200)
    df = pd.DataFrame(klines)

    # 2. Calculate ADX
    adx_engine = ADXEngine(period=14)
    df = adx_engine.analyze_dataframe(df)

    # 3. Generate signals
    generator = SignalGenerator(
        adx_threshold=25.0,
        min_confidence=0.6
    )

    signals = generator.scan_dataframe_for_signals(df)

    print(f"\n✅ Scanned {len(df)} candles")
    print(f"✅ Found {len(signals)} signals")

    # 4. Backtest signals
    if signals:
        print(f"\nBacktesting {len(signals)} signals...")

        results = []
        for sig in signals:
            entry_idx = sig.get('candle_index')
            result = generator.backtest_signal(sig, df, entry_idx)
            results.append(result)

        # Calculate stats
        wins = sum(1 for r in results if r['outcome'] == 'WIN')
        losses = sum(1 for r in results if r['outcome'] == 'LOSS')
        timeouts = sum(1 for r in results if r['outcome'] == 'TIMEOUT')

        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        total_pnl = sum(r.get('pnl_amount', 0) for r in results)

        print(f"\nBacktest Results:")
        print(f"  Wins:     {wins}")
        print(f"  Losses:   {losses}")
        print(f"  Timeouts: {timeouts}")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Total P&L: ${total_pnl:.2f}")

        # Show last signal
        if results:
            print("\nLatest Signal:")
            print(generator.generate_signal_summary(results[-1]))
    else:
        print("\n⚠️  No signals found in current market conditions")
        print("   (ADX likely below threshold or low confidence)")

    print("\n✅ Signal Generator test complete!")
