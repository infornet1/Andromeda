#!/usr/bin/env python3
"""
Complete Phase 3 Integration Test
Tests signal generation + filters + backtesting on real market data
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from dotenv import load_dotenv
import pandas as pd
from src.api.bingx_api import BingXAPI
from src.indicators.adx_engine import ADXEngine
from src.signals.signal_generator import SignalGenerator
from src.signals.signal_filters import SignalFilters, SignalDeduplicator

load_dotenv('config/.env')

print("="*70)
print("Phase 3 Complete Integration Test")
print("="*70)

# Initialize all components
print("\n1. Initializing components...")
api = BingXAPI(
    api_key=os.getenv('BINGX_API_KEY'),
    api_secret=os.getenv('BINGX_API_SECRET')
)

adx_engine = ADXEngine(period=14)

generator = SignalGenerator(
    adx_threshold=25.0,
    min_confidence=0.55,  # Lower for testing
    sl_atr_multiplier=2.0,
    tp_atr_multiplier=4.0
)

filters = SignalFilters(
    enable_short_bias=True,
    short_bias_multiplier=1.5,
    min_confidence=0.6,
    min_adx=25.0,
    cooldown_minutes=15
)

deduplicator = SignalDeduplicator()

print("✅ All components initialized")

# Fetch and analyze data
print("\n2. Fetching market data...")
klines = api.get_kline_data("BTC-USDT", "5m", limit=500)
df = pd.DataFrame(klines)
print(f"✅ Fetched {len(df)} candles")
print(f"   Date range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")

# Calculate ADX
print("\n3. Calculating ADX indicators...")
df = adx_engine.analyze_dataframe(df)
print(f"✅ ADX analysis complete")

# Generate signals
print("\n4. Generating entry signals...")
raw_signals = generator.scan_dataframe_for_signals(df)
print(f"✅ Found {len(raw_signals)} raw signals")

if raw_signals:
    # Apply filters
    print("\n5. Applying filters...")
    passed_signals, filtered_signals = filters.filter_signals(raw_signals, df)
    print(f"✅ Filtered: {len(passed_signals)} passed, {len(filtered_signals)} rejected")

    # Show filter statistics
    if filtered_signals:
        stats = filters.get_filter_statistics(filtered_signals)
        print(f"\n   Filter Statistics:")
        for reason, count in stats.get('by_reason', {}).items():
            print(f"     - {reason}: {count}")

    # Deduplicate
    print("\n6. Deduplicating signals...")
    final_signals = deduplicator.deduplicate(passed_signals)
    print(f"✅ Final signals: {len(final_signals)}")

    if final_signals:
        # Backtest each signal
        print("\n7. Backtesting signals...")
        results = []
        for signal in final_signals:
            entry_idx = signal.get('candle_index')
            result = generator.backtest_signal(signal, df, entry_idx, timeout_candles=12)
            results.append(result)

        # Calculate performance
        wins = sum(1 for r in results if r['outcome'] == 'WIN')
        losses = sum(1 for r in results if r['outcome'] == 'LOSS')
        timeouts = sum(1 for r in results if r['outcome'] == 'TIMEOUT')

        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        total_pnl = sum(r.get('pnl_amount', 0) for r in results)
        avg_bars_held = sum(r.get('bars_held', 0) for r in results) / len(results) if results else 0

        print(f"\n{'='*70}")
        print("BACKTEST RESULTS")
        print(f"{'='*70}")
        print(f"Period:          {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
        print(f"Candles:         {len(df)} (5m timeframe)")
        print(f"\nSignals:")
        print(f"  Raw:           {len(raw_signals)}")
        print(f"  After Filters: {len(passed_signals)}")
        print(f"  Final:         {len(final_signals)}")
        print(f"\nOutcomes:")
        print(f"  Wins:          {wins}")
        print(f"  Losses:        {losses}")
        print(f"  Timeouts:      {timeouts}")
        print(f"  Win Rate:      {win_rate:.1f}%")
        print(f"\nPerformance:")
        print(f"  Total P&L:     ${total_pnl:.2f}")
        print(f"  Avg Hold Time: {avg_bars_held:.1f} bars ({avg_bars_held * 5:.0f} minutes)")
        print(f"{'='*70}")

        # Show individual signals
        print(f"\nDetailed Signal Results:")
        print(f"-" * 70)
        for i, r in enumerate(results, 1):
            side = r.get('side')
            entry = r.get('entry_price')
            exit_p = r.get('exit_price')
            outcome = r.get('outcome')
            pnl = r.get('pnl_amount', 0)
            reason = r.get('exit_reason')
            confidence = r.get('confidence', 0)

            print(f"{i}. {side:5} @ ${entry:,.0f} → ${exit_p:,.0f} | "
                  f"{outcome:7} (${pnl:+.2f}) | {reason:12} | Conf: {confidence:.1%}")

        # Signal type breakdown
        print(f"\n{'='*70}")
        print("SIGNAL TYPE ANALYSIS")
        print(f"{'='*70}")
        long_signals = [r for r in results if r.get('side') == 'LONG']
        short_signals = [r for r in results if r.get('side') == 'SHORT']

        if long_signals:
            long_wins = sum(1 for r in long_signals if r['outcome'] == 'WIN')
            long_total = sum(1 for r in long_signals if r['outcome'] in ['WIN', 'LOSS'])
            long_wr = (long_wins / long_total * 100) if long_total > 0 else 0
            long_pnl = sum(r.get('pnl_amount', 0) for r in long_signals)
            print(f"LONG Signals:  {len(long_signals)}")
            print(f"  Win Rate:    {long_wr:.1f}%")
            print(f"  Total P&L:   ${long_pnl:.2f}")

        if short_signals:
            short_wins = sum(1 for r in short_signals if r['outcome'] == 'WIN')
            short_total = sum(1 for r in short_signals if r['outcome'] in ['WIN', 'LOSS'])
            short_wr = (short_wins / short_total * 100) if short_total > 0 else 0
            short_pnl = sum(r.get('pnl_amount', 0) for r in short_signals)
            print(f"\nSHORT Signals: {len(short_signals)}")
            print(f"  Win Rate:    {short_wr:.1f}%")
            print(f"  Total P&L:   ${short_pnl:.2f}")

        print(f"{'='*70}")

        # Comparison with SCALPING v1.2
        print(f"\nComparison with SCALPING v1.2:")
        print(f"  SCALPING v1.2: 49.5% win rate, 92% timeout rate")
        print(f"  ADX v2.0:      {win_rate:.1f}% win rate, {timeouts/len(results)*100:.1f}% timeout rate")

        if win_rate > 49.5:
            print(f"  ✅ Improvement: +{win_rate - 49.5:.1f}%!")
        else:
            print(f"  ⚠️  Lower than SCALPING v1.2")

    else:
        print("\n⚠️  No signals passed all filters")
else:
    print("\n⚠️  No raw signals generated")
    print("   This is normal if market is ranging (ADX < 25)")

print(f"\n{'='*70}")
print("✅ Phase 3 Integration Test Complete!")
print(f"{'='*70}")
