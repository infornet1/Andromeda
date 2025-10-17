#!/usr/bin/env python3
"""
Quick script to check current ADX values and signal proximity
"""
import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

import pandas as pd
from dotenv import load_dotenv
from src.api.bingx_api import BingXAPI
from src.indicators.adx_engine import ADXEngine
from src.signals.signal_generator import SignalGenerator

# Load environment
load_dotenv('config/.env')

def main():
    print("="*80)
    print("ADX STRATEGY v2.0 - Current Market Analysis")
    print("="*80)

    # Initialize components
    api_key = os.getenv('BINGX_API_KEY')
    api_secret = os.getenv('BINGX_API_SECRET')

    api = BingXAPI(api_key=api_key, api_secret=api_secret)
    adx_engine = ADXEngine(period=14)
    signal_gen = SignalGenerator(adx_threshold=25, min_confidence=0.6)

    # Fetch latest data
    print("\n📊 Fetching latest BTC-USDT data...")
    klines = api.get_kline_data(symbol='BTC-USDT', interval='5m', limit=200)

    if not klines:
        print("❌ Failed to fetch data")
        return

    df = pd.DataFrame(klines)
    print(f"✅ Fetched {len(df)} candles")

    # Calculate ADX indicators
    print("\n🔍 Calculating ADX indicators...")
    df = adx_engine.analyze_dataframe(df)

    # Get latest values
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    current_price = latest['close']
    adx = latest['adx']
    plus_di = latest['plus_di']
    minus_di = latest['minus_di']
    adx_slope = latest['adx_slope']
    di_spread = plus_di - minus_di

    print("\n" + "="*80)
    print("📈 CURRENT MARKET CONDITIONS")
    print("="*80)
    print(f"BTC Price:        ${current_price:,.2f}")
    print(f"Timestamp:        {latest['timestamp']}")
    print()
    print("-"*80)
    print("ADX INDICATOR VALUES:")
    print("-"*80)
    print(f"ADX Value:        {adx:.2f}  {'✅ STRONG' if adx >= 25 else '⚠️  WEAK'} (threshold: 25)")
    print(f"+DI (Plus DI):    {plus_di:.2f}")
    print(f"-DI (Minus DI):   {minus_di:.2f}")
    print(f"DI Spread:        {di_spread:+.2f}  ({'BULLISH' if di_spread > 0 else 'BEARISH'})")
    print(f"ADX Slope:        {adx_slope:+.4f}  ({'RISING' if adx_slope > 0 else 'FALLING'})")
    print()

    # Signal analysis
    print("-"*80)
    print("🎯 SIGNAL REQUIREMENTS CHECK:")
    print("-"*80)

    # Check for LONG signal
    long_checks = {
        'ADX > 25': adx > 25,
        '+DI > -DI': plus_di > minus_di,
        'ADX Rising': adx_slope > 0,
        'Strong DI spread': abs(di_spread) > 5
    }

    # Check for SHORT signal
    short_checks = {
        'ADX > 25': adx > 25,
        '-DI > +DI': minus_di > plus_di,
        'ADX Rising': adx_slope > 0,
        'Strong DI spread': abs(di_spread) > 5
    }

    print("\n🟢 LONG Signal Requirements:")
    for check, passed in long_checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check}")

    long_score = sum(long_checks.values())
    print(f"\n  Score: {long_score}/4 checks passed")

    print("\n🔴 SHORT Signal Requirements:")
    for check, passed in short_checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check}")

    short_score = sum(short_checks.values())
    print(f"\n  Score: {short_score}/4 checks passed")

    # Calculate ATR for signal generation test
    atr_values = signal_gen.calculate_atr(df['high'], df['low'], df['close'])
    current_atr = atr_values.iloc[-1]

    print("\n" + "-"*80)
    print("🔬 ATTEMPTING SIGNAL GENERATION...")
    print("-"*80)

    signal = signal_gen.generate_entry_signal(latest, current_atr)

    if signal:
        print(f"\n✅ SIGNAL DETECTED!")
        print(f"   Direction: {signal['side']}")
        print(f"   Confidence: {signal['confidence']*100:.1f}%")
        print(f"   Entry: ${current_price:,.2f}")
        print(f"   Stop Loss: ${signal['stop_loss']:,.2f}")
        print(f"   Take Profit: ${signal['take_profit']:,.2f}")
        print(f"   Risk/Reward: {abs((signal['take_profit'] - current_price) / (signal['stop_loss'] - current_price)):.2f}")
    else:
        print("\n⚠️  NO SIGNAL GENERATED")
        print("\n   Why not?")

        if adx < 25:
            print(f"   • ADX too low ({adx:.2f} < 25) - Trend not strong enough")
            print(f"     → Need {25 - adx:.2f} more points")

        if abs(di_spread) < 5:
            print(f"   • DI spread too narrow ({abs(di_spread):.2f} < 5) - No clear direction")
            print(f"     → Need {5 - abs(di_spread):.2f} more points of separation")

        if adx_slope <= 0:
            print(f"   • ADX falling ({adx_slope:.4f}) - Trend weakening")

    # Historical context
    print("\n" + "="*80)
    print("📊 RECENT ADX HISTORY (Last 10 candles)")
    print("="*80)
    print(f"{'Time':<20} {'Price':>12} {'ADX':>8} {'+DI':>8} {'-DI':>8} {'Spread':>8}")
    print("-"*80)

    for i in range(max(0, len(df)-10), len(df)):
        row = df.iloc[i]
        spread = row['plus_di'] - row['minus_di']
        marker = " ← NOW" if i == len(df)-1 else ""
        print(f"{row['timestamp']:<20} ${row['close']:>10,.2f} {row['adx']:>8.2f} {row['plus_di']:>8.2f} {row['minus_di']:>8.2f} {spread:>+8.2f}{marker}")

    print("\n" + "="*80)
    print("📈 MARKET TREND ANALYSIS")
    print("="*80)

    # Determine market state
    if adx < 20:
        market_state = "📊 RANGING / CHOPPY - Low trend strength"
        advice = "Wait for ADX to rise above 25 before entering trades"
    elif adx < 25:
        market_state = "🔄 BUILDING - Trend beginning to form"
        advice = "Monitor closely - close to signal threshold"
    elif adx < 40:
        market_state = "💪 TRENDING - Strong directional movement"
        advice = "Good conditions for trading signals"
    else:
        market_state = "🔥 VERY STRONG TREND - Extreme momentum"
        advice = "Caution: May be overextended, watch for reversal"

    print(f"\nMarket State: {market_state}")
    print(f"Recommendation: {advice}")

    # Proximity to signal
    print("\n" + "="*80)
    print("🎯 DISTANCE TO NEXT SIGNAL")
    print("="*80)

    if adx < 25:
        adx_gap = 25 - adx
        print(f"ADX needs to rise by: {adx_gap:.2f} points ({adx_gap/25*100:.1f}% more)")
    else:
        print(f"✅ ADX requirement met ({adx:.2f} >= 25)")

    if abs(di_spread) < 5:
        spread_gap = 5 - abs(di_spread)
        print(f"DI spread needs: {spread_gap:.2f} more points of separation")
    else:
        print(f"✅ DI spread requirement met ({abs(di_spread):.2f} >= 5)")

    # Estimate time to signal
    print("\n" + "-"*80)

    # Calculate ADX change rate
    adx_prev_5 = df.iloc[-6:-1]['adx'].mean()
    adx_change_rate = (adx - adx_prev_5) / 5  # Average change per candle

    print(f"\nADX Trend (last 5 candles): {adx_change_rate:+.2f} per candle")

    if adx < 25 and adx_change_rate > 0:
        candles_needed = (25 - adx) / adx_change_rate
        minutes_needed = candles_needed * 5
        print(f"Estimated time to ADX > 25: ~{int(candles_needed)} candles ({int(minutes_needed)} minutes)")
        print(f"⏰ Potential signal around: {pd.Timestamp.now() + pd.Timedelta(minutes=minutes_needed)}")
    elif adx >= 25:
        print("✅ Already at signal threshold - waiting for DI crossover")
    else:
        print("⚠️  ADX falling - may take longer for signal conditions")

    print("\n" + "="*80)
    print("✅ Analysis Complete")
    print("="*80)

if __name__ == "__main__":
    main()
