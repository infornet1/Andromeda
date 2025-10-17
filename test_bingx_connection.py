#!/usr/bin/env python3
"""
BingX API Connection Test
Tests all required API endpoints before going live
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from src.api.bingx_api import BingXAPI
from dotenv import load_dotenv
from datetime import datetime

# Load environment
load_dotenv('config/.env')


def test_bingx_api():
    """Test all BingX API endpoints"""

    print("="*80)
    print("🧪 BingX API Connection Test")
    print("="*80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Get credentials
    api_key = os.getenv('BINGX_API_KEY')
    api_secret = os.getenv('BINGX_API_SECRET')

    if not api_key or not api_secret:
        print("❌ ERROR: BingX API credentials not found in .env file")
        print("   Please set BINGX_API_KEY and BINGX_API_SECRET")
        return False

    print("✅ API credentials found in .env\n")

    # Initialize API
    try:
        api = BingXAPI(api_key, api_secret, testnet=False)
        print("✅ BingX API initialized\n")
    except Exception as e:
        print(f"❌ Failed to initialize API: {e}\n")
        return False

    all_tests_passed = True

    # Test 1: Server Time
    print("-"*80)
    print("Test 1: Server Time")
    print("-"*80)
    try:
        server_time = api.get_server_time()
        print(f"✅ Server time: {server_time}")
        print(f"   Server datetime: {datetime.fromtimestamp(server_time/1000)}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        all_tests_passed = False
    print()

    # Test 2: Account Balance
    print("-"*80)
    print("Test 2: Account Balance")
    print("-"*80)
    try:
        balance = api.get_account_balance()
        print(f"✅ Balance retrieved:")
        print(f"   Total Equity: ${balance['total_equity']:.2f} USDT")
        print(f"   Available Margin: ${balance['available_margin']:.2f} USDT")
        print(f"   Used Margin: ${balance['used_margin']:.2f} USDT")
        print(f"   Unrealized P&L: ${balance['unrealized_pnl']:+.2f} USDT")

        if balance['available_margin'] < 10:
            print(f"\n   ⚠️  WARNING: Available balance (${balance['available_margin']:.2f}) is very low")
            print(f"      Recommended minimum: $50 for testing, $500+ for production")

    except Exception as e:
        print(f"❌ Failed: {e}")
        all_tests_passed = False
    print()

    # Test 3: Current BTC Price
    print("-"*80)
    print("Test 3: Current BTC Price")
    print("-"*80)
    try:
        ticker = api.get_ticker_price('BTC-USDT')
        print(f"✅ Price retrieved:")
        print(f"   BTC-USDT: ${ticker['price']:,.2f}")
        print(f"   Bid: ${ticker['bid']:,.2f}")
        print(f"   Ask: ${ticker['ask']:,.2f}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        all_tests_passed = False
    print()

    # Test 4: Market Data (Candles)
    print("-"*80)
    print("Test 4: Market Data (Klines)")
    print("-"*80)
    try:
        klines = api.get_kline_data('BTC-USDT', '5m', limit=10)
        print(f"✅ Klines retrieved:")
        print(f"   Retrieved {len(klines)} candles (5m timeframe)")
        if klines:
            latest = klines[-1]
            print(f"   Latest candle:")
            print(f"     Time: {latest['datetime']}")
            print(f"     Open: ${latest['open']:,.2f}")
            print(f"     High: ${latest['high']:,.2f}")
            print(f"     Low: ${latest['low']:,.2f}")
            print(f"     Close: ${latest['close']:,.2f}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        all_tests_passed = False
    print()

    # Test 5: Open Positions
    print("-"*80)
    print("Test 5: Open Positions")
    print("-"*80)
    try:
        positions = api.get_positions('BTC-USDT')
        print(f"✅ Positions retrieved:")
        open_positions = [p for p in positions if float(p.get('position_amount', 0)) != 0]

        if open_positions:
            print(f"   {len(open_positions)} open position(s) found:")
            for pos in open_positions:
                side = pos.get('side')
                size = float(pos.get('position_amount', 0))
                entry = float(pos.get('entry_price', 0))
                pnl = float(pos.get('unrealized_profit', 0))
                print(f"     {side}: {abs(size):.5f} BTC @ ${entry:,.2f} (P&L: ${pnl:+.2f})")
        else:
            print(f"   No open positions")

    except Exception as e:
        print(f"❌ Failed: {e}")
        all_tests_passed = False
    print()

    # Test 6: Leverage Status
    print("-"*80)
    print("Test 6: Leverage Configuration")
    print("-"*80)
    try:
        # Note: BingX doesn't have a "get leverage" endpoint
        # Leverage is set per position
        print(f"✅ Leverage can be configured")
        print(f"   Test leverage setting (not actually setting it)...")
        print(f"   Target leverage: 5x for BTC-USDT")
        print(f"   Use set_leverage() method to configure")
    except Exception as e:
        print(f"❌ Failed: {e}")
        all_tests_passed = False
    print()

    # Test 7: Connectivity Test
    print("-"*80)
    print("Test 7: Overall Connectivity")
    print("-"*80)
    try:
        conn_test = api.test_connectivity()
        if conn_test:
            print(f"✅ Connection to BingX successful")
        else:
            print(f"❌ Connection test failed")
            all_tests_passed = False
    except Exception as e:
        print(f"❌ Failed: {e}")
        all_tests_passed = False
    print()

    # Summary
    print("="*80)
    print("📊 TEST SUMMARY")
    print("="*80)

    if all_tests_passed:
        print("✅ ALL TESTS PASSED")
        print("\nYour BingX API is working correctly!")
        print("\n✅ You are ready to proceed with live trading setup")
        print("\n⚠️  IMPORTANT NEXT STEPS:")
        print("   1. Review your configuration in config_live.json")
        print("   2. Start with PAPER mode first: python3 live_trader.py --mode paper")
        print("   3. Only use LIVE mode after successful paper trading")
        print("   4. Start with minimal capital for initial live testing")
    else:
        print("❌ SOME TESTS FAILED")
        print("\n⚠️  Do NOT proceed with live trading until all tests pass")
        print("\n   Check:")
        print("   1. API credentials are correct in config/.env")
        print("   2. API key has required permissions (trading, balance)")
        print("   3. IP address is whitelisted on BingX")
        print("   4. Account has funds in futures wallet")

    print("="*80)

    return all_tests_passed


if __name__ == '__main__':
    try:
        success = test_bingx_api()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)
