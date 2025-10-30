#!/usr/bin/env python3
"""
Market Condition Analyzer for ADX Strategy v2.0
Identifies optimal market conditions for ADX trading strategy
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketConditionAnalyzer:
    """
    Market Condition Analysis

    Identifies market regimes and optimal trading conditions:
    - Trending vs Ranging markets
    - Bullish vs Bearish trends
    - Market strength
    - Volatility regime
    """

    def __init__(self,
                 trend_sma_period: int = 50,
                 range_atr_multiplier: float = 1.5,
                 min_trend_adx: float = 25.0):
        """
        Initialize market condition analyzer

        Args:
            trend_sma_period: Period for trend detection SMA
            range_atr_multiplier: ATR multiplier for range detection
            min_trend_adx: Minimum ADX for trending market
        """
        self.trend_sma_period = trend_sma_period
        self.range_atr_multiplier = range_atr_multiplier
        self.min_trend_adx = min_trend_adx

        logger.info("Market Condition Analyzer initialized")

    def analyze_market_condition(self, df: pd.DataFrame) -> Dict:
        """
        Analyze current market condition

        Args:
            df: DataFrame with OHLCV and indicator data

        Returns:
            Dictionary with market condition analysis
        """
        if len(df) < self.trend_sma_period:
            return {'error': 'Insufficient data'}

        current = df.iloc[-1]

        # 1. Trend Direction
        trend_direction = self._detect_trend_direction(df)

        # 2. Trend Strength
        trend_strength = self._calculate_trend_strength(df)

        # 3. Market Regime (Trending vs Ranging)
        market_regime = self._identify_market_regime(df)

        # 4. Volatility Regime
        volatility_regime = self._identify_volatility_regime(df)

        # 5. ADX Condition
        adx_condition = self._analyze_adx_condition(df)

        # 6. Overall Trading Suitability
        is_suitable, reasons = self._evaluate_trading_suitability(
            trend_direction, trend_strength, market_regime, adx_condition
        )

        analysis = {
            'timestamp': current['timestamp'],
            'price': current['close'],
            'trend_direction': trend_direction,
            'trend_strength': trend_strength,
            'market_regime': market_regime,
            'volatility_regime': volatility_regime,
            'adx_condition': adx_condition,
            'is_suitable_for_trading': is_suitable,
            'reasons': reasons
        }

        return analysis

    def _detect_trend_direction(self, df: pd.DataFrame) -> str:
        """
        Detect overall trend direction

        Returns:
            'BULLISH', 'BEARISH', or 'NEUTRAL'
        """
        # Use multiple SMAs for confirmation
        current_price = df['close'].iloc[-1]

        # Calculate SMAs
        sma_20 = df['close'].rolling(window=20).mean().iloc[-1]
        sma_50 = df['close'].rolling(window=50).mean().iloc[-1]

        # Price position relative to SMAs
        if current_price > sma_20 and sma_20 > sma_50:
            return 'BULLISH'
        elif current_price < sma_20 and sma_20 < sma_50:
            return 'BEARISH'
        else:
            return 'NEUTRAL'

    def _calculate_trend_strength(self, df: pd.DataFrame) -> Dict:
        """
        Calculate trend strength using ADX and other indicators

        Returns:
            Dictionary with strength metrics
        """
        current_adx = df['adx'].iloc[-1] if 'adx' in df.columns else 0

        # ADX interpretation
        if current_adx < 20:
            strength_label = 'WEAK'
        elif 20 <= current_adx < 25:
            strength_label = 'MODERATE'
        elif 25 <= current_adx < 40:
            strength_label = 'STRONG'
        else:
            strength_label = 'VERY_STRONG'

        # Calculate price momentum
        returns = df['close'].pct_change()
        momentum_5 = returns.rolling(window=5).sum().iloc[-1] * 100
        momentum_20 = returns.rolling(window=20).sum().iloc[-1] * 100

        return {
            'adx_value': round(current_adx, 2),
            'strength_label': strength_label,
            'momentum_5_period': round(momentum_5, 2),
            'momentum_20_period': round(momentum_20, 2)
        }

    def _identify_market_regime(self, df: pd.DataFrame) -> str:
        """
        Identify if market is TRENDING or RANGING

        ADX Strategy works best in TRENDING markets
        """
        current_adx = df['adx'].iloc[-1] if 'adx' in df.columns else 0

        # Calculate price range
        recent_high = df['high'].rolling(window=20).max().iloc[-1]
        recent_low = df['low'].rolling(window=20).min().iloc[-1]
        current_price = df['close'].iloc[-1]

        price_range_percent = ((recent_high - recent_low) / recent_low) * 100

        # Trending market criteria:
        # 1. ADX above threshold
        # 2. Price making consistent moves
        if current_adx >= self.min_trend_adx and price_range_percent > 2.0:
            return 'TRENDING'
        else:
            return 'RANGING'

    def _identify_volatility_regime(self, df: pd.DataFrame) -> str:
        """
        Identify current volatility regime

        Returns:
            'LOW', 'NORMAL', 'HIGH', or 'EXTREME'
        """
        if 'atr' not in df.columns:
            return 'UNKNOWN'

        current_atr = df['atr'].iloc[-1]
        avg_atr = df['atr'].rolling(window=50).mean().iloc[-1]

        if pd.isna(avg_atr) or avg_atr == 0:
            return 'UNKNOWN'

        atr_ratio = current_atr / avg_atr

        if atr_ratio < 0.7:
            return 'LOW'
        elif 0.7 <= atr_ratio < 1.3:
            return 'NORMAL'
        elif 1.3 <= atr_ratio < 2.0:
            return 'HIGH'
        else:
            return 'EXTREME'

    def _analyze_adx_condition(self, df: pd.DataFrame) -> Dict:
        """
        Analyze ADX indicator conditions
        """
        if 'adx' not in df.columns:
            return {'error': 'ADX data not available'}

        current = df.iloc[-1]

        # ADX value
        adx = current['adx']

        # DI+ and DI-
        plus_di = current.get('plus_di', 0)
        minus_di = current.get('minus_di', 0)

        # DI spread
        di_spread = abs(plus_di - minus_di)

        # ADX trend (rising or falling)
        adx_prev = df['adx'].iloc[-5]
        adx_trend = 'RISING' if adx > adx_prev else 'FALLING'

        return {
            'adx': round(adx, 2),
            'plus_di': round(plus_di, 2),
            'minus_di': round(minus_di, 2),
            'di_spread': round(di_spread, 2),
            'adx_trend': adx_trend,
            'above_threshold': adx >= self.min_trend_adx
        }

    def _evaluate_trading_suitability(self,
                                     trend_direction: str,
                                     trend_strength: Dict,
                                     market_regime: str,
                                     adx_condition: Dict) -> tuple:
        """
        Evaluate if current conditions are suitable for ADX strategy

        Returns:
            Tuple of (is_suitable: bool, reasons: List[str])
        """
        reasons = []
        is_suitable = True

        # 1. Check market regime
        if market_regime != 'TRENDING':
            is_suitable = False
            reasons.append(f"Market is {market_regime}, ADX needs TRENDING markets")

        # 2. Check ADX threshold
        if not adx_condition.get('above_threshold', False):
            is_suitable = False
            reasons.append(f"ADX {adx_condition['adx']} below threshold {self.min_trend_adx}")

        # 3. Check trend direction
        if trend_direction == 'NEUTRAL':
            is_suitable = False
            reasons.append("No clear trend direction")

        # 4. Check trend strength
        if trend_strength['strength_label'] == 'WEAK':
            is_suitable = False
            reasons.append("Trend strength too weak")

        # If all good, add positive reasons
        if is_suitable:
            reasons.append(f"✅ Market is {trend_direction} and {market_regime}")
            reasons.append(f"✅ Trend strength is {trend_strength['strength_label']}")
            reasons.append(f"✅ ADX at {adx_condition['adx']:.1f} (above {self.min_trend_adx})")

        return is_suitable, reasons

    def analyze_strategy_performance_by_condition(self, trades: List[Dict], df: pd.DataFrame) -> Dict:
        """
        Analyze strategy performance across different market conditions

        Args:
            trades: List of trade dictionaries
            df: Market data DataFrame

        Returns:
            Performance breakdown by market condition
        """
        if not trades:
            return {'error': 'No trades provided'}

        # Categorize each trade by market condition at entry
        categorized_trades = {
            'TRENDING_BULLISH': [],
            'TRENDING_BEARISH': [],
            'RANGING': [],
            'HIGH_VOLATILITY': []
        }

        for trade in trades:
            # Find market condition at trade entry time
            trade_time = pd.to_datetime(trade.get('entry_time') or trade.get('timestamp'))

            # Find closest market data
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            idx = df['timestamp'].searchsorted(trade_time)

            if idx >= len(df):
                continue

            # Analyze conditions at that time
            df_subset = df.iloc[:idx+1]
            condition = self.analyze_market_condition(df_subset)

            # Categorize trade
            if condition['market_regime'] == 'TRENDING':
                if condition['trend_direction'] == 'BULLISH':
                    categorized_trades['TRENDING_BULLISH'].append(trade)
                else:
                    categorized_trades['TRENDING_BEARISH'].append(trade)
            else:
                categorized_trades['RANGING'].append(trade)

            if condition['volatility_regime'] in ['HIGH', 'EXTREME']:
                categorized_trades['HIGH_VOLATILITY'].append(trade)

        # Calculate performance for each category
        performance_by_condition = {}

        for condition_name, condition_trades in categorized_trades.items():
            if not condition_trades:
                continue

            trades_df = pd.DataFrame(condition_trades)
            wins = trades_df[trades_df['pnl'] > 0]

            performance_by_condition[condition_name] = {
                'total_trades': len(condition_trades),
                'wins': len(wins),
                'losses': len(trades_df) - len(wins),
                'win_rate': len(wins) / len(trades_df) if len(trades_df) > 0 else 0,
                'total_pnl': trades_df['pnl'].sum(),
                'avg_pnl': trades_df['pnl'].mean(),
                'largest_win': wins['pnl'].max() if len(wins) > 0 else 0,
                'largest_loss': trades_df[trades_df['pnl'] < 0]['pnl'].min() if len(trades_df[trades_df['pnl'] < 0]) > 0 else 0
            }

        return performance_by_condition

    def get_optimal_conditions_summary(self, performance_by_condition: Dict) -> str:
        """
        Generate summary of optimal trading conditions
        """
        summary = "\n" + "="*80 + "\n"
        summary += "OPTIMAL MARKET CONDITIONS FOR ADX STRATEGY\n"
        summary += "="*80 + "\n\n"

        best_condition = None
        best_win_rate = 0
        best_pnl = float('-inf')

        for condition_name, metrics in performance_by_condition.items():
            win_rate = metrics['win_rate'] * 100
            total_pnl = metrics['total_pnl']

            summary += f"{condition_name}:\n"
            summary += f"  Trades: {metrics['total_trades']}\n"
            summary += f"  Win Rate: {win_rate:.1f}%\n"
            summary += f"  Total P&L: ${total_pnl:+.2f}\n"
            summary += f"  Avg P&L: ${metrics['avg_pnl']:+.2f}\n"
            summary += f"  Largest Win: ${metrics['largest_win']:.2f}\n"
            summary += f"  Largest Loss: ${metrics['largest_loss']:.2f}\n\n"

            # Track best condition
            if total_pnl > best_pnl:
                best_pnl = total_pnl
                best_condition = condition_name
                best_win_rate = win_rate

        if best_condition:
            summary += "="*80 + "\n"
            summary += f"✅ BEST CONDITION: {best_condition}\n"
            summary += f"   Win Rate: {best_win_rate:.1f}%, Total P&L: ${best_pnl:+.2f}\n"
            summary += "="*80 + "\n"

        return summary


if __name__ == "__main__":
    print("Testing Market Condition Analyzer...")

    # Create test data
    test_data = pd.DataFrame({
        'timestamp': pd.date_range(start='2025-10-01', periods=100, freq='5min'),
        'close': [112000 + i*10 + np.random.randn()*50 for i in range(100)],
        'high': [112000 + i*10 + 100 for i in range(100)],
        'low': [112000 + i*10 - 100 for i in range(100)],
        'adx': [20 + i*0.2 for i in range(100)],
        'plus_di': [25 + i*0.1 for i in range(100)],
        'minus_di': [15 + i*0.05 for i in range(100)],
        'atr': [500 + i*2 for i in range(100)]
    })

    # Initialize analyzer
    analyzer = MarketConditionAnalyzer(
        trend_sma_period=50,
        range_atr_multiplier=1.5,
        min_trend_adx=25.0
    )

    # Test market condition analysis
    print("\n1. Analyzing Market Condition:")
    condition = analyzer.analyze_market_condition(test_data)

    for key, value in condition.items():
        if key != 'reasons':
            print(f"   {key}: {value}")

    print(f"\n   Trading Suitability: {'✅ SUITABLE' if condition['is_suitable_for_trading'] else '❌ NOT SUITABLE'}")
    print(f"   Reasons:")
    for reason in condition['reasons']:
        print(f"      - {reason}")

    print("\n✅ Market Condition Analyzer test complete!")
