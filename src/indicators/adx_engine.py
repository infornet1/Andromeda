#!/usr/bin/env python3
"""
ADX Calculation Engine for ADX Strategy v2.0
Implements all 6 ADX indicators (Trading Latino methodology)

References:
- Wilder, J. Welles. "New Concepts in Technical Trading Systems" (1978)
- Trading Latino ADX Strategy
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
import talib

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ADXEngine:
    """
    ADX (Average Directional Index) Calculation Engine

    Implements 6 key indicators:
    1. ADX (14-period) - Trend strength
    2. +DI (Plus Directional Indicator) - Bullish pressure
    3. -DI (Minus Directional Indicator) - Bearish pressure
    4. Trend Strength Classification - Categorize trend strength
    5. DI Crossover Detection - Entry/exit signals
    6. ADX+DI Combo Signal - Combined confirmation

    All calculations use standard Wilder's smoothing (14-period default)
    """

    def __init__(self, period: int = 14):
        """
        Initialize ADX engine

        Args:
            period: ADX calculation period (default 14)
        """
        self.period = period
        logger.info(f"ADX Engine initialized (period: {period})")

    def calculate_adx(self, high: pd.Series, low: pd.Series,
                     close: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate ADX, +DI, and -DI using TA-Lib

        Args:
            high: High prices
            low: Low prices
            close: Close prices

        Returns:
            Tuple of (ADX, +DI, -DI) as pandas Series
        """
        # Calculate using TA-Lib (Wilder's method)
        adx = talib.ADX(high, low, close, timeperiod=self.period)
        plus_di = talib.PLUS_DI(high, low, close, timeperiod=self.period)
        minus_di = talib.MINUS_DI(high, low, close, timeperiod=self.period)

        return adx, plus_di, minus_di

    def calculate_adx_slope(self, adx: pd.Series, periods: int = 3) -> pd.Series:
        """
        Calculate ADX slope (rate of change)

        Args:
            adx: ADX values
            periods: Number of periods for slope calculation

        Returns:
            ADX slope as pandas Series
        """
        # Calculate slope using linear regression over N periods
        slope = adx.diff(periods) / periods

        return slope

    def classify_trend_strength(self, adx: pd.Series) -> pd.Series:
        """
        Classify trend strength based on ADX value

        Args:
            adx: ADX values

        Returns:
            Trend strength classification as strings

        Classification:
        - 0-20: NONE (No trend / ranging)
        - 20-25: WEAK (Emerging trend)
        - 25-35: STRONG (Strong trend - tradeable)
        - 35-50: VERY_STRONG (Very strong trend)
        - 50+: EXTREME (Extremely strong trend)
        """
        def classify(value):
            if pd.isna(value):
                return 'NONE'
            elif value < 20:
                return 'NONE'
            elif value < 25:
                return 'WEAK'
            elif value < 35:
                return 'STRONG'
            elif value < 50:
                return 'VERY_STRONG'
            else:
                return 'EXTREME'

        return adx.apply(classify)

    def detect_di_crossover(self, plus_di: pd.Series,
                           minus_di: pd.Series) -> pd.Series:
        """
        Detect DI crossovers (entry signals)

        Args:
            plus_di: +DI values
            minus_di: -DI values

        Returns:
            Crossover signals: 'BULLISH', 'BEARISH', or None

        Signals:
        - BULLISH: +DI crosses above -DI (LONG entry)
        - BEARISH: -DI crosses above +DI (SHORT entry)
        """
        signals = pd.Series(index=plus_di.index, dtype=object)

        # Bullish crossover: +DI crosses above -DI
        bullish_cross = (plus_di > minus_di) & (plus_di.shift(1) <= minus_di.shift(1))

        # Bearish crossover: -DI crosses above +DI
        bearish_cross = (minus_di > plus_di) & (minus_di.shift(1) <= plus_di.shift(1))

        signals[bullish_cross] = 'BULLISH'
        signals[bearish_cross] = 'BEARISH'

        return signals

    def calculate_di_spread(self, plus_di: pd.Series, minus_di: pd.Series) -> pd.Series:
        """
        Calculate spread between +DI and -DI

        Args:
            plus_di: +DI values
            minus_di: -DI values

        Returns:
            DI spread (positive for bullish, negative for bearish)
        """
        return plus_di - minus_di

    def generate_adx_combo_signal(self, adx: pd.Series, plus_di: pd.Series,
                                  minus_di: pd.Series,
                                  adx_threshold: float = 25.0,
                                  slope_threshold: float = 0.5) -> pd.Series:
        """
        Generate ADX+DI combo signals (Trading Latino method)

        Args:
            adx: ADX values
            plus_di: +DI values
            minus_di: -DI values
            adx_threshold: Minimum ADX for strong trend (default 25)
            slope_threshold: Minimum ADX slope (positive = rising)

        Returns:
            Signal: 'BUY', 'SELL', 'HOLD', or 'EXIT'

        Logic:
        - BUY: ADX > threshold AND ADX rising AND +DI > -DI
        - SELL: ADX > threshold AND ADX rising AND -DI > +DI
        - EXIT: ADX < 20 (trend weakening)
        - HOLD: All other conditions
        """
        signals = pd.Series('HOLD', index=adx.index)

        # Calculate ADX slope
        adx_slope = self.calculate_adx_slope(adx, periods=3)

        # Strong uptrend conditions
        buy_condition = (
            (adx > adx_threshold) &
            (adx_slope > slope_threshold) &
            (plus_di > minus_di)
        )

        # Strong downtrend conditions
        sell_condition = (
            (adx > adx_threshold) &
            (adx_slope > slope_threshold) &
            (minus_di > plus_di)
        )

        # Exit conditions (trend weakening)
        exit_condition = (adx < 20)

        signals[buy_condition] = 'BUY'
        signals[sell_condition] = 'SELL'
        signals[exit_condition] = 'EXIT'

        return signals

    def calculate_signal_confidence(self, adx: pd.Series, plus_di: pd.Series,
                                   minus_di: pd.Series) -> pd.Series:
        """
        Calculate signal confidence score (0-1)

        Args:
            adx: ADX values
            plus_di: +DI values
            minus_di: -DI values

        Returns:
            Confidence score (0.0 to 1.0)

        Factors:
        - ADX strength (higher = more confident)
        - DI spread (wider = more confident)
        - ADX slope (rising = more confident)
        """
        # Normalize ADX to 0-1 (cap at 50)
        adx_norm = (adx / 50).clip(0, 1)

        # Normalize DI spread (cap at 30)
        di_spread = abs(plus_di - minus_di)
        di_spread_norm = (di_spread / 30).clip(0, 1)

        # Normalize ADX slope (cap at 2)
        adx_slope = self.calculate_adx_slope(adx, periods=3)
        adx_slope_norm = ((adx_slope + 2) / 4).clip(0, 1)

        # Weighted average (ADX = 50%, DI spread = 30%, ADX slope = 20%)
        confidence = (
            adx_norm * 0.5 +
            di_spread_norm * 0.3 +
            adx_slope_norm * 0.2
        )

        return confidence.clip(0, 1)

    def analyze_dataframe(self, df: pd.DataFrame,
                         adx_threshold: float = 25.0) -> pd.DataFrame:
        """
        Analyze full dataframe with all 6 ADX indicators

        Args:
            df: DataFrame with columns: ['open', 'high', 'low', 'close', 'volume']
            adx_threshold: ADX threshold for signal generation

        Returns:
            DataFrame with added ADX indicator columns
        """
        logger.info(f"Analyzing {len(df)} candles with ADX indicators")

        # Ensure required columns exist
        required = ['high', 'low', 'close']
        if not all(col in df.columns for col in required):
            raise ValueError(f"DataFrame must contain: {required}")

        # 1. Calculate ADX, +DI, -DI
        adx, plus_di, minus_di = self.calculate_adx(
            df['high'],
            df['low'],
            df['close']
        )

        df['adx'] = adx
        df['plus_di'] = plus_di
        df['minus_di'] = minus_di

        # 2. Calculate ADX slope
        df['adx_slope'] = self.calculate_adx_slope(adx)

        # 3. Classify trend strength
        df['trend_strength'] = self.classify_trend_strength(adx)

        # 4. Detect DI crossovers
        df['di_crossover'] = self.detect_di_crossover(plus_di, minus_di)

        # 5. Calculate DI spread
        df['di_spread'] = self.calculate_di_spread(plus_di, minus_di)

        # 6. Generate ADX combo signals
        df['adx_signal'] = self.generate_adx_combo_signal(
            adx, plus_di, minus_di, adx_threshold
        )

        # 7. Calculate confidence score
        df['confidence'] = self.calculate_signal_confidence(adx, plus_di, minus_di)

        logger.info("ADX analysis complete")
        return df

    def get_latest_signal(self, df: pd.DataFrame) -> Dict:
        """
        Get latest ADX signal with all indicators

        Args:
            df: DataFrame with ADX indicators

        Returns:
            Dictionary with latest signal data
        """
        if df.empty:
            return {}

        latest = df.iloc[-1]

        return {
            'timestamp': latest.get('timestamp'),
            'datetime': latest.get('datetime'),
            'close_price': float(latest.get('close', 0)),
            'adx': float(latest.get('adx', 0)),
            'plus_di': float(latest.get('plus_di', 0)),
            'minus_di': float(latest.get('minus_di', 0)),
            'adx_slope': float(latest.get('adx_slope', 0)),
            'trend_strength': latest.get('trend_strength', 'NONE'),
            'di_crossover': latest.get('di_crossover'),
            'di_spread': float(latest.get('di_spread', 0)),
            'adx_signal': latest.get('adx_signal', 'HOLD'),
            'confidence': float(latest.get('confidence', 0))
        }

    def print_signal_summary(self, signal: Dict):
        """
        Print formatted signal summary

        Args:
            signal: Signal dictionary from get_latest_signal
        """
        print("\n" + "=" * 60)
        print("ADX Signal Summary")
        print("=" * 60)
        print(f"Timestamp:       {signal.get('datetime', 'N/A')}")
        print(f"Close Price:     ${signal.get('close_price', 0):,.2f}")
        print(f"\nADX Indicators:")
        print(f"  ADX:           {signal.get('adx', 0):.2f}")
        print(f"  +DI:           {signal.get('plus_di', 0):.2f}")
        print(f"  -DI:           {signal.get('minus_di', 0):.2f}")
        print(f"  ADX Slope:     {signal.get('adx_slope', 0):.4f}")
        print(f"  DI Spread:     {signal.get('di_spread', 0):.2f}")
        print(f"\nSignal Analysis:")
        print(f"  Trend Strength: {signal.get('trend_strength', 'NONE')}")
        print(f"  DI Crossover:   {signal.get('di_crossover') or 'None'}")
        print(f"  ADX Signal:     {signal.get('adx_signal', 'HOLD')}")
        print(f"  Confidence:     {signal.get('confidence', 0):.2%}")
        print("=" * 60)


# ==================== Helper Functions ====================

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series,
                 period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR) for stop loss / take profit

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR period (default 14)

    Returns:
        ATR values as pandas Series
    """
    return talib.ATR(high, low, close, timeperiod=period)


if __name__ == "__main__":
    # Test script
    import sys
    sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')
    from dotenv import load_dotenv
    import os
    from src.api.bingx_api import BingXAPI

    load_dotenv('config/.env')

    print("Testing ADX Engine...")

    # 1. Fetch data from BingX
    api = BingXAPI(
        api_key=os.getenv('BINGX_API_KEY'),
        api_secret=os.getenv('BINGX_API_SECRET')
    )

    klines = api.get_kline_data("BTC-USDT", "5m", limit=100)

    # 2. Convert to DataFrame
    df = pd.DataFrame(klines)

    print(f"\n✅ Fetched {len(df)} candles")
    print(f"   Date range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")

    # 3. Calculate ADX indicators
    engine = ADXEngine(period=14)
    df = engine.analyze_dataframe(df, adx_threshold=25.0)

    # 4. Get latest signal
    signal = engine.get_latest_signal(df)
    engine.print_signal_summary(signal)

    # 5. Show recent signals
    print("\nRecent ADX Signals (last 10):")
    print(df[['datetime', 'close', 'adx', 'plus_di', 'minus_di',
              'trend_strength', 'adx_signal', 'confidence']].tail(10).to_string())

    print("\n✅ ADX Engine test complete!")
