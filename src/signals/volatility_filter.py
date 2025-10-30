#!/usr/bin/env python3
"""
Volatility Filter for ADX Strategy v2.0
Prevents trading during high volatility periods to avoid gap/slippage events
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from typing import Dict, Optional, List
from datetime import datetime, time
import pandas as pd
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VolatilityFilter:
    """
    Volatility-Based Trade Filter

    Features:
    - ATR-based volatility detection
    - Time-of-day filters (avoid market open/close)
    - Gap detection
    - Volume spike detection
    - Market hours restrictions
    """

    def __init__(self,
                 max_atr_multiplier: float = 2.0,
                 max_volume_multiplier: float = 3.0,
                 max_gap_percent: float = 0.5,
                 avoid_market_open_minutes: int = 60,
                 avoid_market_close_minutes: int = 60,
                 enable_time_filter: bool = True,
                 enable_atr_filter: bool = True,
                 enable_gap_filter: bool = True,
                 enable_volume_filter: bool = True):
        """
        Initialize volatility filter

        Args:
            max_atr_multiplier: Max ATR multiplier (2.0 = 2x normal ATR)
            max_volume_multiplier: Max volume multiplier (3.0 = 3x normal volume)
            max_gap_percent: Max gap size as % of price (0.5% default)
            avoid_market_open_minutes: Minutes after market open to avoid
            avoid_market_close_minutes: Minutes before market close to avoid
            enable_time_filter: Enable time-based filtering
            enable_atr_filter: Enable ATR-based filtering
            enable_gap_filter: Enable gap detection filtering
            enable_volume_filter: Enable volume spike filtering
        """
        self.max_atr_multiplier = max_atr_multiplier
        self.max_volume_multiplier = max_volume_multiplier
        self.max_gap_percent = max_gap_percent
        self.avoid_market_open_minutes = avoid_market_open_minutes
        self.avoid_market_close_minutes = avoid_market_close_minutes

        self.enable_time_filter = enable_time_filter
        self.enable_atr_filter = enable_atr_filter
        self.enable_gap_filter = enable_gap_filter
        self.enable_volume_filter = enable_volume_filter

        logger.info("Volatility Filter initialized")
        logger.info(f"  ATR Filter: {'✅' if enable_atr_filter else '❌'} (max {max_atr_multiplier}x)")
        logger.info(f"  Time Filter: {'✅' if enable_time_filter else '❌'}")
        logger.info(f"  Gap Filter: {'✅' if enable_gap_filter else '❌'} (max {max_gap_percent}%)")
        logger.info(f"  Volume Filter: {'✅' if enable_volume_filter else '❌'} (max {max_volume_multiplier}x)")

    def should_allow_trade(self, current_row: pd.Series, df_history: pd.DataFrame) -> tuple:
        """
        Check if trading should be allowed based on volatility conditions

        Args:
            current_row: Current candle data
            df_history: Historical data for reference

        Returns:
            Tuple of (allow_trade: bool, rejection_reason: str or None)
        """
        reasons = []

        # 1. Check ATR-based volatility
        if self.enable_atr_filter:
            allow, reason = self._check_atr_volatility(current_row, df_history)
            if not allow:
                reasons.append(reason)

        # 2. Check time of day
        if self.enable_time_filter:
            allow, reason = self._check_time_of_day(current_row)
            if not allow:
                reasons.append(reason)

        # 3. Check for price gaps
        if self.enable_gap_filter:
            allow, reason = self._check_price_gaps(current_row, df_history)
            if not allow:
                reasons.append(reason)

        # 4. Check volume spikes
        if self.enable_volume_filter:
            allow, reason = self._check_volume_spike(current_row, df_history)
            if not allow:
                reasons.append(reason)

        if reasons:
            combined_reason = "; ".join(reasons)
            logger.debug(f"❌ Trade rejected: {combined_reason}")
            return False, combined_reason

        return True, None

    def _check_atr_volatility(self, current_row: pd.Series, df_history: pd.DataFrame) -> tuple:
        """
        Check if current ATR is within acceptable range

        High ATR = high volatility = higher chance of slippage
        """
        if 'atr' not in current_row or pd.isna(current_row['atr']):
            return True, None

        current_atr = current_row['atr']

        # Calculate average ATR from history
        if 'atr' in df_history.columns:
            avg_atr = df_history['atr'].rolling(window=20).mean().iloc[-1]

            if pd.notna(avg_atr) and avg_atr > 0:
                atr_ratio = current_atr / avg_atr

                if atr_ratio > self.max_atr_multiplier:
                    return False, f"ATR too high ({atr_ratio:.2f}x avg, max {self.max_atr_multiplier}x)"

        return True, None

    def _check_time_of_day(self, current_row: pd.Series) -> tuple:
        """
        Check if current time is safe for trading

        Avoids:
        - First hour after market open (high volatility)
        - Last hour before market close (thin liquidity)
        """
        if 'timestamp' not in current_row:
            return True, None

        timestamp = current_row['timestamp']
        if isinstance(timestamp, str):
            timestamp = pd.to_datetime(timestamp)

        current_time = timestamp.time()

        # Crypto markets are 24/7, but we can still identify volatile hours
        # Typically, volatility is higher during:
        # - 00:00-01:00 UTC (day rollover)
        # - 09:30-10:30 UTC (traditional market open)
        # - 15:30-16:30 UTC (traditional market close)

        volatile_periods = [
            (time(0, 0), time(1, 0)),     # Midnight UTC
            (time(9, 0), time(10, 30)),   # Traditional market open
            (time(15, 0), time(16, 30)),  # Traditional market close
        ]

        for start, end in volatile_periods:
            if start <= current_time <= end:
                return False, f"Volatile time period ({current_time.strftime('%H:%M')})"

        return True, None

    def _check_price_gaps(self, current_row: pd.Series, df_history: pd.DataFrame) -> tuple:
        """
        Check for large price gaps between candles

        Large gaps can cause stop loss slippage
        """
        if len(df_history) < 2:
            return True, None

        prev_close = df_history['close'].iloc[-2]
        current_open = current_row['open']

        gap_percent = abs((current_open - prev_close) / prev_close) * 100

        if gap_percent > self.max_gap_percent:
            return False, f"Price gap detected ({gap_percent:.2f}%, max {self.max_gap_percent}%)"

        return True, None

    def _check_volume_spike(self, current_row: pd.Series, df_history: pd.DataFrame) -> tuple:
        """
        Check for unusual volume spikes

        Volume spikes often accompany high volatility events
        """
        if 'volume' not in current_row or 'volume' not in df_history.columns:
            return True, None

        current_volume = current_row['volume']

        # Calculate average volume
        avg_volume = df_history['volume'].rolling(window=20).mean().iloc[-1]

        if pd.notna(avg_volume) and avg_volume > 0:
            volume_ratio = current_volume / avg_volume

            if volume_ratio > self.max_volume_multiplier:
                return False, f"Volume spike detected ({volume_ratio:.2f}x avg, max {self.max_volume_multiplier}x)"

        return True, None

    def get_volatility_metrics(self, current_row: pd.Series, df_history: pd.DataFrame) -> Dict:
        """
        Get current volatility metrics for monitoring

        Returns:
            Dictionary with volatility indicators
        """
        metrics = {}

        # ATR ratio
        if 'atr' in current_row and 'atr' in df_history.columns:
            current_atr = current_row['atr']
            avg_atr = df_history['atr'].rolling(window=20).mean().iloc[-1]
            if pd.notna(avg_atr) and avg_atr > 0:
                metrics['atr_ratio'] = current_atr / avg_atr

        # Volume ratio
        if 'volume' in current_row and 'volume' in df_history.columns:
            current_volume = current_row['volume']
            avg_volume = df_history['volume'].rolling(window=20).mean().iloc[-1]
            if pd.notna(avg_volume) and avg_volume > 0:
                metrics['volume_ratio'] = current_volume / avg_volume

        # Price gap
        if len(df_history) >= 2:
            prev_close = df_history['close'].iloc[-2]
            current_open = current_row['open']
            metrics['gap_percent'] = abs((current_open - prev_close) / prev_close) * 100

        # Time of day
        if 'timestamp' in current_row:
            timestamp = current_row['timestamp']
            if isinstance(timestamp, str):
                timestamp = pd.to_datetime(timestamp)
            metrics['time_of_day'] = timestamp.strftime('%H:%M:%S')

        return metrics

    def get_filter_status(self) -> Dict:
        """Get current filter configuration"""
        return {
            'atr_filter': {
                'enabled': self.enable_atr_filter,
                'max_multiplier': self.max_atr_multiplier
            },
            'time_filter': {
                'enabled': self.enable_time_filter,
                'avoid_open_minutes': self.avoid_market_open_minutes,
                'avoid_close_minutes': self.avoid_market_close_minutes
            },
            'gap_filter': {
                'enabled': self.enable_gap_filter,
                'max_gap_percent': self.max_gap_percent
            },
            'volume_filter': {
                'enabled': self.enable_volume_filter,
                'max_multiplier': self.max_volume_multiplier
            }
        }


if __name__ == "__main__":
    # Test script
    print("Testing Volatility Filter...")

    # Initialize filter
    volatility_filter = VolatilityFilter(
        max_atr_multiplier=2.0,
        max_volume_multiplier=3.0,
        max_gap_percent=0.5,
        enable_time_filter=True,
        enable_atr_filter=True,
        enable_gap_filter=True,
        enable_volume_filter=True
    )

    print("\nFilter Configuration:")
    status = volatility_filter.get_filter_status()
    for filter_name, config in status.items():
        print(f"  {filter_name}: {config}")

    # Create test data
    test_history = pd.DataFrame({
        'timestamp': pd.date_range(start='2025-10-30 10:00', periods=30, freq='5min'),
        'close': [112000 + i*10 for i in range(30)],
        'open': [112000 + i*10 for i in range(30)],
        'atr': [500 + i*5 for i in range(30)],
        'volume': [1000000 + i*10000 for i in range(30)]
    })

    # Test case 1: Normal conditions (should pass)
    print("\n1. Test Normal Conditions:")
    test_row = pd.Series({
        'timestamp': pd.Timestamp('2025-10-30 11:00'),
        'close': 112300,
        'open': 112300,
        'atr': 550,
        'volume': 1100000
    })

    allow, reason = volatility_filter.should_allow_trade(test_row, test_history)
    print(f"   Result: {'✅ ALLOWED' if allow else '❌ REJECTED'}")
    if reason:
        print(f"   Reason: {reason}")

    metrics = volatility_filter.get_volatility_metrics(test_row, test_history)
    print(f"   Metrics: {metrics}")

    # Test case 2: High ATR (should reject)
    print("\n2. Test High ATR:")
    test_row_high_atr = test_row.copy()
    test_row_high_atr['atr'] = 1500  # 3x normal

    allow, reason = volatility_filter.should_allow_trade(test_row_high_atr, test_history)
    print(f"   Result: {'✅ ALLOWED' if allow else '❌ REJECTED'}")
    if reason:
        print(f"   Reason: {reason}")

    # Test case 3: Large gap (should reject)
    print("\n3. Test Large Price Gap:")
    test_row_gap = test_row.copy()
    test_row_gap['open'] = 113000  # Large gap from previous close

    allow, reason = volatility_filter.should_allow_trade(test_row_gap, test_history)
    print(f"   Result: {'✅ ALLOWED' if allow else '❌ REJECTED'}")
    if reason:
        print(f"   Reason: {reason}")

    # Test case 4: Volume spike (should reject)
    print("\n4. Test Volume Spike:")
    test_row_volume = test_row.copy()
    test_row_volume['volume'] = 5000000  # 5x normal

    allow, reason = volatility_filter.should_allow_trade(test_row_volume, test_history)
    print(f"   Result: {'✅ ALLOWED' if allow else '❌ REJECTED'}")
    if reason:
        print(f"   Reason: {reason}")

    # Test case 5: Volatile time period (should reject)
    print("\n5. Test Volatile Time Period:")
    test_row_time = test_row.copy()
    test_row_time['timestamp'] = pd.Timestamp('2025-10-30 09:30')  # Market open

    allow, reason = volatility_filter.should_allow_trade(test_row_time, test_history)
    print(f"   Result: {'✅ ALLOWED' if allow else '❌ REJECTED'}")
    if reason:
        print(f"   Reason: {reason}")

    print("\n✅ Volatility Filter test complete!")
