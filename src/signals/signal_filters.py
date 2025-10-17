#!/usr/bin/env python3
"""
Signal Filters for ADX Strategy v2.0
Implements quality filters including SHORT bias from SCALPING v1.2 learnings
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SignalFilters:
    """
    Signal Quality Filters

    Filters Applied:
    1. SHORT Bias - Prioritize SHORT signals (90% win rate in SCALPING v1.2)
    2. Confidence Threshold - Minimum confidence score
    3. ADX Strength - Additional ADX validation
    4. DI Spread - Minimum directional clarity
    5. Time-of-Day - Optional trading hours
    6. Cooldown - Prevent signal spam
    7. Volume - Minimum volume threshold
    8. Volatility - ATR-based filters
    """

    def __init__(self,
                 enable_short_bias: bool = True,
                 short_bias_multiplier: float = 1.5,
                 min_confidence: float = 0.6,
                 min_adx: float = 25.0,
                 min_di_spread: float = 5.0,
                 cooldown_minutes: int = 15,
                 min_volume_percentile: float = 25.0,
                 enable_time_filter: bool = False,
                 trading_hours_start: int = 0,
                 trading_hours_end: int = 24):
        """
        Initialize signal filters

        Args:
            enable_short_bias: Apply SHORT bias from SCALPING v1.2
            short_bias_multiplier: Boost SHORT signal confidence
            min_confidence: Minimum confidence (0-1)
            min_adx: Minimum ADX value
            min_di_spread: Minimum DI spread
            cooldown_minutes: Minutes between signals
            min_volume_percentile: Minimum volume percentile
            enable_time_filter: Enable time-based filtering
            trading_hours_start: Start hour (0-23)
            trading_hours_end: End hour (0-23)
        """
        self.enable_short_bias = enable_short_bias
        self.short_bias_multiplier = short_bias_multiplier
        self.min_confidence = min_confidence
        self.min_adx = min_adx
        self.min_di_spread = min_di_spread
        self.cooldown_minutes = cooldown_minutes
        self.min_volume_percentile = min_volume_percentile
        self.enable_time_filter = enable_time_filter
        self.trading_hours_start = trading_hours_start
        self.trading_hours_end = trading_hours_end

        self.last_signal_time = {}  # Track last signal time by type

        logger.info(f"Signal Filters initialized (SHORT bias: {enable_short_bias})")

    def apply_short_bias(self, signal: Dict) -> Dict:
        """
        Apply SHORT bias - boost SHORT signal confidence

        Based on SCALPING v1.2 learning:
        - SHORT signals: 90% win rate
        - LONG signals: 0% win rate

        Args:
            signal: Signal dictionary

        Returns:
            Modified signal with adjusted confidence
        """
        if not self.enable_short_bias:
            return signal

        if signal.get('side') == 'SHORT':
            # Boost SHORT signal confidence
            original_confidence = signal.get('confidence', 0.5)
            boosted_confidence = min(original_confidence * self.short_bias_multiplier, 1.0)

            signal['confidence'] = boosted_confidence
            signal['confidence_adjusted'] = True
            signal['confidence_boost'] = boosted_confidence - original_confidence

            logger.debug(f"SHORT bias applied: {original_confidence:.2%} → {boosted_confidence:.2%}")

        return signal

    def filter_by_confidence(self, signal: Dict) -> bool:
        """Filter by minimum confidence threshold"""
        confidence = signal.get('confidence', 0)
        passed = confidence >= self.min_confidence

        if not passed:
            logger.debug(f"Signal filtered: Low confidence ({confidence:.2%} < {self.min_confidence:.2%})")

        return passed

    def filter_by_adx_strength(self, signal: Dict) -> bool:
        """Filter by ADX strength"""
        adx = signal.get('adx', 0)
        passed = adx >= self.min_adx

        if not passed:
            logger.debug(f"Signal filtered: Weak ADX ({adx:.2f} < {self.min_adx})")

        return passed

    def filter_by_di_spread(self, signal: Dict) -> bool:
        """Filter by DI spread (directional clarity)"""
        di_spread = signal.get('di_spread', 0)
        passed = di_spread >= self.min_di_spread

        if not passed:
            logger.debug(f"Signal filtered: Low DI spread ({di_spread:.2f} < {self.min_di_spread})")

        return passed

    def filter_by_cooldown(self, signal: Dict) -> bool:
        """
        Filter by cooldown period to prevent signal spam

        Args:
            signal: Signal dictionary with timestamp

        Returns:
            True if cooldown period has passed
        """
        signal_type = signal.get('signal_type')
        timestamp = signal.get('timestamp')

        if not timestamp:
            return True

        # Convert to datetime if needed
        if isinstance(timestamp, str):
            timestamp = pd.to_datetime(timestamp)
        elif isinstance(timestamp, (int, np.integer)):
            # Handle Unix timestamp (milliseconds or seconds)
            if timestamp > 1e12:  # Milliseconds
                timestamp = pd.to_datetime(timestamp, unit='ms')
            else:  # Seconds
                timestamp = pd.to_datetime(timestamp, unit='s')

        last_time = self.last_signal_time.get(signal_type)

        if last_time:
            # Ensure last_time is also datetime
            if isinstance(last_time, (int, np.integer)):
                if last_time > 1e12:
                    last_time = pd.to_datetime(last_time, unit='ms')
                else:
                    last_time = pd.to_datetime(last_time, unit='s')

            time_diff = (timestamp - last_time).total_seconds() / 60  # Minutes
            if time_diff < self.cooldown_minutes:
                logger.debug(f"Signal filtered: Cooldown ({time_diff:.1f}m < {self.cooldown_minutes}m)")
                return False

        # Update last signal time
        self.last_signal_time[signal_type] = timestamp
        return True

    def filter_by_time_of_day(self, signal: Dict) -> bool:
        """Filter by trading hours"""
        if not self.enable_time_filter:
            return True

        timestamp = signal.get('timestamp')
        if not timestamp:
            return True

        if isinstance(timestamp, str):
            timestamp = pd.to_datetime(timestamp)
        elif isinstance(timestamp, (int, np.integer)):
            # Handle Unix timestamp (milliseconds or seconds)
            if timestamp > 1e12:  # Milliseconds
                timestamp = pd.to_datetime(timestamp, unit='ms')
            else:  # Seconds
                timestamp = pd.to_datetime(timestamp, unit='s')

        hour = timestamp.hour

        if self.trading_hours_start <= self.trading_hours_end:
            # Normal range (e.g., 9-17)
            passed = self.trading_hours_start <= hour < self.trading_hours_end
        else:
            # Wrap-around range (e.g., 22-6)
            passed = hour >= self.trading_hours_start or hour < self.trading_hours_end

        if not passed:
            logger.debug(f"Signal filtered: Outside trading hours ({hour}:00)")

        return passed

    def filter_by_volume(self, signal: Dict, df: pd.DataFrame) -> bool:
        """
        Filter by volume - require above minimum percentile

        Args:
            signal: Signal dictionary
            df: DataFrame with volume data

        Returns:
            True if volume is sufficient
        """
        if df.empty or 'volume' not in df.columns:
            return True

        candle_idx = signal.get('candle_index')
        if candle_idx is None or candle_idx >= len(df):
            return True

        current_volume = df.iloc[candle_idx].get('volume', 0)
        volume_threshold = df['volume'].quantile(self.min_volume_percentile / 100)

        passed = current_volume >= volume_threshold

        if not passed:
            logger.debug(f"Signal filtered: Low volume ({current_volume:.2f} < {volume_threshold:.2f})")

        return passed

    def filter_by_volatility(self, signal: Dict, df: pd.DataFrame) -> bool:
        """
        Filter by volatility - ensure sufficient ATR

        Args:
            signal: Signal dictionary with ATR
            df: DataFrame with price data

        Returns:
            True if volatility is sufficient
        """
        atr = signal.get('atr')
        if not atr:
            return True

        # ATR should be at least 0.1% of price
        entry_price = signal.get('entry_price', 0)
        min_atr = entry_price * 0.001  # 0.1%

        passed = atr >= min_atr

        if not passed:
            logger.debug(f"Signal filtered: Low volatility (ATR={atr:.2f} < {min_atr:.2f})")

        return passed

    def filter_signal(self, signal: Dict, df: Optional[pd.DataFrame] = None) -> Tuple[bool, Dict]:
        """
        Apply all filters to a signal

        Args:
            signal: Signal dictionary
            df: Optional dataframe for volume/volatility checks

        Returns:
            (passed, filtered_signal) tuple
        """
        # Apply SHORT bias first (modifies confidence)
        signal = self.apply_short_bias(signal)

        # Apply filters in order
        filters = [
            ('confidence', self.filter_by_confidence),
            ('adx_strength', self.filter_by_adx_strength),
            ('di_spread', self.filter_by_di_spread),
            ('cooldown', self.filter_by_cooldown),
            ('time_of_day', self.filter_by_time_of_day),
        ]

        for filter_name, filter_func in filters:
            if not filter_func(signal):
                signal['filtered'] = True
                signal['filter_reason'] = filter_name
                return False, signal

        # Optional filters requiring dataframe
        if df is not None:
            if not self.filter_by_volume(signal, df):
                signal['filtered'] = True
                signal['filter_reason'] = 'volume'
                return False, signal

            if not self.filter_by_volatility(signal, df):
                signal['filtered'] = True
                signal['filter_reason'] = 'volatility'
                return False, signal

        signal['filtered'] = False
        signal['filter_reason'] = None
        return True, signal

    def filter_signals(self, signals: List[Dict],
                      df: Optional[pd.DataFrame] = None) -> Tuple[List[Dict], List[Dict]]:
        """
        Filter multiple signals

        Args:
            signals: List of signal dictionaries
            df: Optional dataframe for context

        Returns:
            (passed_signals, filtered_signals) tuple
        """
        passed = []
        filtered = []

        for signal in signals:
            is_valid, processed_signal = self.filter_signal(signal, df)

            if is_valid:
                passed.append(processed_signal)
            else:
                filtered.append(processed_signal)

        logger.info(f"Filtered {len(signals)} signals: {len(passed)} passed, {len(filtered)} filtered")

        return passed, filtered

    def get_filter_statistics(self, filtered_signals: List[Dict]) -> Dict:
        """
        Get statistics on why signals were filtered

        Args:
            filtered_signals: List of filtered signals

        Returns:
            Statistics dictionary
        """
        if not filtered_signals:
            return {}

        reasons = {}
        for sig in filtered_signals:
            reason = sig.get('filter_reason', 'unknown')
            reasons[reason] = reasons.get(reason, 0) + 1

        return {
            'total_filtered': len(filtered_signals),
            'by_reason': reasons,
            'filter_rate': len(filtered_signals) / (len(filtered_signals) + 1) * 100
        }


class SignalDeduplicator:
    """Remove duplicate signals"""

    def __init__(self, time_window_minutes: int = 5, price_tolerance_percent: float = 0.1):
        """
        Initialize deduplicator

        Args:
            time_window_minutes: Time window for duplicate detection
            price_tolerance_percent: Price tolerance for duplicates
        """
        self.time_window = timedelta(minutes=time_window_minutes)
        self.price_tolerance = price_tolerance_percent / 100

    def are_signals_similar(self, sig1: Dict, sig2: Dict) -> bool:
        """Check if two signals are similar enough to be duplicates"""
        # Must be same side
        if sig1.get('side') != sig2.get('side'):
            return False

        # Check time proximity
        time1 = sig1.get('timestamp')
        time2 = sig2.get('timestamp')

        if time1 and time2:
            if isinstance(time1, str):
                time1 = pd.to_datetime(time1)
            if isinstance(time2, str):
                time2 = pd.to_datetime(time2)

            if abs(time2 - time1) > self.time_window:
                return False

        # Check price proximity
        price1 = sig1.get('entry_price', 0)
        price2 = sig2.get('entry_price', 0)

        if price1 and price2:
            price_diff = abs(price2 - price1) / price1
            if price_diff > self.price_tolerance:
                return False

        return True

    def deduplicate(self, signals: List[Dict]) -> List[Dict]:
        """
        Remove duplicate signals, keeping highest confidence

        Args:
            signals: List of signals

        Returns:
            Deduplicated list
        """
        if len(signals) <= 1:
            return signals

        # Sort by timestamp
        signals = sorted(signals, key=lambda s: s.get('timestamp', datetime.min))

        unique = []
        for signal in signals:
            is_duplicate = False

            for existing in unique:
                if self.are_signals_similar(signal, existing):
                    # Keep higher confidence
                    if signal.get('confidence', 0) > existing.get('confidence', 0):
                        unique.remove(existing)
                        unique.append(signal)
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique.append(signal)

        logger.info(f"Deduplicated: {len(signals)} → {len(unique)} signals")
        return unique


if __name__ == "__main__":
    # Test script
    print("Testing Signal Filters...")

    # Create test signals
    test_signals = [
        {
            'signal_type': 'SELL',
            'side': 'SHORT',
            'entry_price': 112000,
            'confidence': 0.65,
            'adx': 27.5,
            'di_spread': 8.2,
            'timestamp': datetime.now(),
            'atr': 150
        },
        {
            'signal_type': 'BUY',
            'side': 'LONG',
            'entry_price': 112500,
            'confidence': 0.55,
            'adx': 23.0,
            'di_spread': 4.5,
            'timestamp': datetime.now() + timedelta(minutes=5),
            'atr': 140
        },
        {
            'signal_type': 'SELL',
            'side': 'SHORT',
            'entry_price': 112200,
            'confidence': 0.70,
            'adx': 30.0,
            'di_spread': 10.5,
            'timestamp': datetime.now() + timedelta(minutes=20),
            'atr': 160
        }
    ]

    # 1. Test signal filters
    filters = SignalFilters(
        enable_short_bias=True,
        short_bias_multiplier=1.5,
        min_confidence=0.6,
        min_adx=25.0,
        cooldown_minutes=15
    )

    passed, filtered = filters.filter_signals(test_signals)

    print(f"\n✅ Tested {len(test_signals)} signals")
    print(f"   Passed: {len(passed)}")
    print(f"   Filtered: {len(filtered)}")

    if passed:
        print(f"\nPassed Signals:")
        for sig in passed:
            print(f"  - {sig['side']} @ ${sig['entry_price']:,.0f}, "
                  f"confidence={sig['confidence']:.2%} "
                  f"(adjusted: {sig.get('confidence_adjusted', False)})")

    if filtered:
        print(f"\nFiltered Signals:")
        for sig in filtered:
            print(f"  - {sig['side']} @ ${sig['entry_price']:,.0f}, "
                  f"reason={sig['filter_reason']}")

    # 2. Test deduplicator
    print(f"\n2. Testing Deduplicator...")

    duplicate_signals = [
        {'side': 'SHORT', 'entry_price': 112000, 'confidence': 0.65,
         'timestamp': datetime.now()},
        {'side': 'SHORT', 'entry_price': 112050, 'confidence': 0.70,
         'timestamp': datetime.now() + timedelta(minutes=2)},
        {'side': 'LONG', 'entry_price': 113000, 'confidence': 0.60,
         'timestamp': datetime.now() + timedelta(minutes=10)}
    ]

    dedup = SignalDeduplicator()
    unique = dedup.deduplicate(duplicate_signals)

    print(f"   Original: {len(duplicate_signals)} signals")
    print(f"   Unique: {len(unique)} signals")

    print("\n✅ Signal Filters test complete!")
