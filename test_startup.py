#!/usr/bin/env python3
"""
Quick test to verify the live trader initializes correctly
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from live_trader import LiveTradingBot

print("="*80)
print("Testing Live Trader Initialization")
print("="*80)

try:
    # Initialize bot
    print("\n1. Creating LiveTradingBot instance...")
    bot = LiveTradingBot(config_file='config_live.json')
    print("✅ Bot created successfully!")

    # Check components
    print("\n2. Checking components:")
    print(f"  API Client: {'✅ Initialized' if bot.api else '⚠️  Demo Mode (no API)'}")
    print(f"  ADX Engine: {'✅' if bot.adx_engine else '❌'}")
    print(f"  Signal Generator: {'✅' if bot.signal_gen else '❌'}")
    print(f"  Risk Manager: {'✅' if bot.risk_mgr else '❌'}")
    print(f"  Position Sizer: {'✅' if bot.sizer else '❌'}")
    print(f"  Order Executor: {'✅' if bot.executor else '❌'}")
    print(f"  Position Manager: {'✅' if bot.position_mgr else '❌'}")
    print(f"  Paper Trader: {'✅' if bot.trader else '❌'}")
    print(f"  Dashboard: {'✅' if bot.dashboard else '❌'}")
    print(f"  Performance Tracker: {'✅' if bot.perf_tracker else '❌'}")
    print(f"  Alert System: {'✅' if bot.alerts else '❌'}")
    print(f"  System Monitor: {'✅' if bot.monitor else '❌'}")

    # Test fetching price
    print("\n3. Testing price fetch...")
    price = bot._fetch_current_price()
    print(f"✅ Current price: ${price:,.2f}")

    # Test dashboard
    print("\n4. Testing dashboard...")
    status_bar = bot.dashboard.get_status_bar()
    print(f"✅ Status: {status_bar}")

    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED - BOT IS READY TO RUN!")
    print("="*80)
    print("\nTo start 48-hour paper trading:")
    print("  ./run_paper_trading.sh")
    print("\nOr for a short test:")
    print("  python3 -c \"from live_trader import LiveTradingBot; LiveTradingBot().start(duration_hours=0.1)\"")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
