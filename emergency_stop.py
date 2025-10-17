#!/usr/bin/env python3
"""
🚨 EMERGENCY STOP - ADX Strategy v2.0
Closes all open positions on BingX immediately
USE ONLY IN EMERGENCY
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from src.api.bingx_api import BingXAPI
from dotenv import load_dotenv
from datetime import datetime

# Load environment
load_dotenv('config/.env')


def emergency_stop():
    """
    Close all open positions immediately
    """
    print("="*80)
    print("🚨 EMERGENCY STOP - ADX STRATEGY V2.0")
    print("="*80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("")

    # Initialize API
    api_key = os.getenv('BINGX_API_KEY')
    api_secret = os.getenv('BINGX_API_SECRET')

    if not api_key or not api_secret:
        print("❌ Error: BingX API credentials not found in .env file")
        return False

    print("📡 Connecting to BingX...")
    api = BingXAPI(api_key, api_secret, testnet=False)

    try:
        # Get all open positions
        print("🔍 Checking for open positions...")
        positions = api.get_positions('BTC-USDT')

        if not positions:
            print("✅ No open positions found")
            print("="*80)
            return True

        # Count positions to close
        positions_to_close = [pos for pos in positions
                             if float(pos.get('position_amount', 0)) != 0]

        if not positions_to_close:
            print("✅ No open positions found")
            print("="*80)
            return True

        print(f"\n⚠️  Found {len(positions_to_close)} open position(s):")
        print("-"*80)

        for pos in positions_to_close:
            side = pos.get('side')
            size = float(pos.get('position_amount', 0))
            entry = float(pos.get('entry_price', 0))
            unrealized_pnl = float(pos.get('unrealized_profit', 0))

            print(f"  {side}: {abs(size):.5f} BTC @ ${entry:,.2f}")
            print(f"    Unrealized P&L: ${unrealized_pnl:+.2f}")

        print("-"*80)

        # Confirmation
        print("\n🚨 WARNING: This will IMMEDIATELY close ALL positions")
        print("   This action cannot be undone!")
        print("")
        confirmation = input("Type 'CLOSE ALL' to proceed: ")

        if confirmation != 'CLOSE ALL':
            print("\n❌ Emergency stop cancelled")
            print("="*80)
            return False

        print("\n🔄 Closing all positions...")
        print("-"*80)

        # Close each position
        success_count = 0
        for pos in positions_to_close:
            side = pos.get('side')
            size = abs(float(pos.get('position_amount', 0)))

            try:
                print(f"\n  Closing {side} position ({size:.5f} BTC)...")
                result = api.close_position('BTC-USDT', side)

                if result and 'order_id' in result:
                    print(f"    ✅ Close order placed: {result['order_id']}")
                    success_count += 1
                else:
                    print(f"    ❌ Failed to close {side} position")

            except Exception as e:
                print(f"    ❌ Error closing {side}: {e}")

        print("\n" + "-"*80)
        print(f"\n📊 Summary:")
        print(f"  Positions found: {len(positions_to_close)}")
        print(f"  Close orders placed: {success_count}")

        if success_count == len(positions_to_close):
            print("\n✅ All positions closed successfully")
        else:
            print(f"\n⚠️  {len(positions_to_close) - success_count} positions failed to close")
            print("   Please check BingX manually!")

        print("="*80)
        return success_count == len(positions_to_close)

    except Exception as e:
        print(f"\n❌ Emergency stop failed: {e}")
        print("="*80)
        return False


if __name__ == '__main__':
    try:
        success = emergency_stop()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Emergency stop interrupted")
        sys.exit(1)
