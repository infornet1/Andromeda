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
                 tp_atr_multiplier: float = 4.0,
                 multi_timeframe_enabled: bool = True,
                 rsi_enabled: bool = True,
                 rsi_period: int = 14,
                 rsi_long_range: tuple = (50, 70),
                 rsi_short_range: tuple = (30, 50),
                 api_client = None):
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
            multi_timeframe_enabled: Enable multi-timeframe confirmation (1H + 15M + 5M)
            rsi_enabled: Enable RSI confluence filter
            rsi_period: RSI calculation period
            rsi_long_range: RSI range for LONG entries (min, max)
            rsi_short_range: RSI range for SHORT entries (min, max)
            api_client: API client for fetching multi-timeframe data
        """
        self.adx_threshold = adx_threshold
        self.adx_weak_threshold = adx_weak_threshold
        self.adx_slope_min = adx_slope_min
        self.di_spread_min = di_spread_min
        self.min_confidence = min_confidence
        self.atr_period = atr_period
        self.sl_atr_multiplier = sl_atr_multiplier
        self.tp_atr_multiplier = tp_atr_multiplier

        # NEW: Multi-timeframe and RSI improvements
        self.multi_timeframe_enabled = multi_timeframe_enabled
        self.rsi_enabled = rsi_enabled
        self.rsi_period = rsi_period
        self.rsi_long_range = rsi_long_range
        self.rsi_short_range = rsi_short_range
        self.api_client = api_client

        logger.info(f"Signal Generator initialized (ADX threshold: {adx_threshold}, MTF: {multi_timeframe_enabled}, RSI: {rsi_enabled})")

    def calculate_atr(self, high: pd.Series, low: pd.Series,
                     close: pd.Series) -> pd.Series:
        """Calculate Average True Range"""
        return talib.ATR(high, low, close, timeperiod=self.atr_period)

    def calculate_rsi(self, close: pd.Series) -> pd.Series:
        """Calculate Relative Strength Index"""
        return talib.RSI(close, timeperiod=self.rsi_period)

    def check_multi_timeframe_confirmation(self, symbol: str, current_side: str) -> bool:
        """
        Check if higher timeframes confirm the signal direction

        Args:
            symbol: Trading symbol (e.g., "BTC-USDT")
            current_side: Proposed trade side ("LONG" or "SHORT")

        Returns:
            True if all timeframes align, False otherwise
        """
        if not self.multi_timeframe_enabled or not self.api_client:
            return True  # Skip check if disabled or no API client

        try:
            from src.indicators.adx_engine import ADXEngine
            adx_engine = ADXEngine(period=14)

            # Fetch 1H data
            klines_1h = self.api_client.get_kline_data(symbol, "1h", limit=50)
            if not klines_1h or len(klines_1h) < 30:
                logger.warning("Insufficient 1H data for MTF confirmation")
                return False

            df_1h = pd.DataFrame(klines_1h)
            df_1h = adx_engine.analyze_dataframe(df_1h)

            # Fetch 15M data
            klines_15m = self.api_client.get_kline_data(symbol, "15m", limit=50)
            if not klines_15m or len(klines_15m) < 30:
                logger.warning("Insufficient 15M data for MTF confirmation")
                return False

            df_15m = pd.DataFrame(klines_15m)
            df_15m = adx_engine.analyze_dataframe(df_15m)

            # Check 1H trend
            plus_di_1h = df_1h['plus_di'].iloc[-1]
            minus_di_1h = df_1h['minus_di'].iloc[-1]
            adx_1h = df_1h['adx'].iloc[-1]

            if current_side == 'LONG':
                trend_1h_ok = (plus_di_1h > minus_di_1h and adx_1h > 20)
            else:  # SHORT
                trend_1h_ok = (minus_di_1h > plus_di_1h and adx_1h > 20)

            # Check 15M trend
            plus_di_15m = df_15m['plus_di'].iloc[-1]
            minus_di_15m = df_15m['minus_di'].iloc[-1]
            adx_15m = df_15m['adx'].iloc[-1]

            if current_side == 'LONG':
                trend_15m_ok = (plus_di_15m > minus_di_15m and adx_15m > 20)
            else:  # SHORT
                trend_15m_ok = (minus_di_15m > plus_di_15m and adx_15m > 20)

            mtf_confirmed = trend_1h_ok and trend_15m_ok

            if mtf_confirmed:
                logger.info(f"✅ Multi-timeframe confirmed for {current_side} (1H: {adx_1h:.1f}, 15M: {adx_15m:.1f})")
            else:
                logger.info(f"❌ Multi-timeframe rejected {current_side} (1H OK: {trend_1h_ok}, 15M OK: {trend_15m_ok})")

            return mtf_confirmed

        except Exception as e:
            logger.error(f"Error in multi-timeframe check: {e}")
            return False  # Reject signal on error for safety

    def check_rsi_filter(self, rsi: float, side: str) -> bool:
        """
        Check if RSI is in acceptable range for entry

        Args:
            rsi: Current RSI value
            side: Trade side ("LONG" or "SHORT")

        Returns:
            True if RSI is in acceptable range, False otherwise
        """
        if not self.rsi_enabled:
            return True  # Skip check if disabled

        if pd.isna(rsi):
            logger.warning("RSI is NaN, rejecting signal")
            return False

        if side == 'LONG':
            # For LONG: RSI should be between 50-70 (bullish but not overbought)
            rsi_ok = self.rsi_long_range[0] <= rsi <= self.rsi_long_range[1]
            if rsi_ok:
                logger.info(f"✅ RSI filter passed for LONG: {rsi:.1f} (range: {self.rsi_long_range})")
            else:
                logger.info(f"❌ RSI filter rejected LONG: {rsi:.1f} (range: {self.rsi_long_range})")
        else:  # SHORT
            # For SHORT: RSI should be between 30-50 (bearish but not oversold)
            rsi_ok = self.rsi_short_range[0] <= rsi <= self.rsi_short_range[1]
            if rsi_ok:
                logger.info(f"✅ RSI filter passed for SHORT: {rsi:.1f} (range: {self.rsi_short_range})")
            else:
                logger.info(f"❌ RSI filter rejected SHORT: {rsi:.1f} (range: {self.rsi_short_range})")

        return rsi_ok

    def generate_entry_signal(self, row: pd.Series, atr: float, symbol: str = "BTC-USDT") -> Optional[Dict]:
        """
        Generate entry signal based on ADX criteria + RSI + Multi-timeframe

        Args:
            row: Current candle data with ADX indicators and RSI
            atr: Current ATR value
            symbol: Trading symbol for multi-timeframe check

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
        rsi = row.get('rsi', None)  # NEW: Get RSI value

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

        # NEW: Additional filters (RSI + Multi-timeframe)
        # Check which side we're considering
        if long_conditions:
            proposed_side = 'LONG'
        elif short_conditions:
            proposed_side = 'SHORT'
        else:
            return None  # No signal

        # NEW: RSI Filter
        if rsi is not None and not self.check_rsi_filter(rsi, proposed_side):
            logger.info(f"Signal rejected by RSI filter ({proposed_side}, RSI: {rsi:.1f})")
            return None

        # NEW: Multi-timeframe confirmation
        if not self.check_multi_timeframe_confirmation(symbol, proposed_side):
            logger.info(f"Signal rejected by multi-timeframe filter ({proposed_side})")
            return None

        signal = None

        # Format RSI for display (avoid f-string formatting issues with None)
        rsi_str = f"{rsi:.1f}" if (rsi is not None and not pd.isna(rsi)) else 'N/A'

        if proposed_side == 'LONG':
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
                'rsi': rsi if rsi is not None else np.nan,  # NEW: Include RSI
                'entry_condition': f"ADX={adx:.2f} +DI={plus_di:.2f} -DI={minus_di:.2f} RSI={rsi_str}",
                'trend_strength': row.get('trend_strength', 'STRONG'),
                'multi_timeframe_confirmed': self.multi_timeframe_enabled,  # NEW
                'rsi_confirmed': self.rsi_enabled  # NEW
            }

        elif proposed_side == 'SHORT':
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
                'rsi': rsi if rsi is not None else np.nan,  # NEW: Include RSI
                'entry_condition': f"ADX={adx:.2f} +DI={plus_di:.2f} -DI={minus_di:.2f} RSI={rsi_str}",
                'trend_strength': row.get('trend_strength', 'STRONG'),
                'multi_timeframe_confirmed': self.multi_timeframe_enabled,  # NEW
                'rsi_confirmed': self.rsi_enabled  # NEW
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

    def scan_dataframe_for_signals(self, df: pd.DataFrame, symbol: str = "BTC-USDT") -> List[Dict]:
        """
        Scan dataframe for all entry signals

        Args:
            df: DataFrame with OHLCV and ADX indicators
            symbol: Trading symbol for multi-timeframe check

        Returns:
            List of signal dictionaries
        """
        signals = []

        # Calculate ATR
        atr = self.calculate_atr(df['high'], df['low'], df['close'])

        # NEW: Calculate RSI if enabled
        if self.rsi_enabled:
            df['rsi'] = self.calculate_rsi(df['close'])

        for idx, row in df.iterrows():
            if pd.isna(atr.iloc[idx]):
                continue

            signal = self.generate_entry_signal(row, atr.iloc[idx], symbol)

            if signal:
                # Add timestamp and index
                signal['timestamp'] = row.get('datetime') or row.get('timestamp')
                signal['candle_index'] = idx
                signals.append(signal)

        logger.info(f"Found {len(signals)} signals in {len(df)} candles (MTF: {self.multi_timeframe_enabled}, RSI: {self.rsi_enabled})")
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
