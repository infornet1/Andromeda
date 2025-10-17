#!/usr/bin/env python3
"""
Migrate existing trades to database
"""

import sys
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from src.persistence.trade_database import TradeDatabase

# Initialize database
db = TradeDatabase()

# Manually add the 4 trades from today
trades = [
    {
        'id': 'POS_5000_1760715737',
        'side': 'SHORT',
        'entry_price': 107904.16847836447,
        'exit_price': 106134.23155943846,
        'quantity': 0.00093,
        'pnl': 8.230206673005982,
        'pnl_percent': 8.201429768122917,
        'exit_reason': 'TAKE_PROFIT',
        'hold_duration': 0.1348509,
        'closed_at': '2025-10-17T11:42:25.199307',
        'timestamp': '2025-10-17T11:42:17.000000'
    },
    {
        'id': 'POS_5000_1760717858',
        'side': 'SHORT',
        'entry_price': 107956.20127876179,
        'exit_price': 107100.90786723261,
        'quantity': 0.00093,
        'pnl': 3.9771143636106494,
        'pnl_percent': 3.9612981996312318,
        'exit_reason': 'TAKE_PROFIT',
        'hold_duration': 0.15119841666666664,
        'closed_at': '2025-10-17T12:17:47.656872',
        'timestamp': '2025-10-17T12:17:38.000000'
    },
    {
        'id': 'POS_5000_1760718468',
        'side': 'SHORT',
        'entry_price': 107985.18874708244,
        'exit_price': 106745.77577866077,
        'quantity': 0.00093,
        'pnl': 5.763270303160789,
        'pnl_percent': 5.738810029422492,
        'exit_reason': 'TAKE_PROFIT',
        'hold_duration': 0.15196501666666667,
        'closed_at': '2025-10-17T12:27:57.568156',
        'timestamp': '2025-10-17T12:27:48.000000'
    },
    {
        'id': 'POS_5000_1760718531',
        'side': 'SHORT',
        'entry_price': 107988.29637424122,
        'exit_price': 106926.02,  # Approximate
        'quantity': 0.00093,
        'pnl': 6.017430939465292,
        'pnl_percent': 6.02,
        'exit_reason': 'TAKE_PROFIT',
        'hold_duration': 0.15,
        'closed_at': '2025-10-17T12:29:04.000000',
        'timestamp': '2025-10-17T12:28:51.000000'
    }
]

print("Migrating trades to database...")
print(f"Total trades to migrate: {len(trades)}")

for i, trade in enumerate(trades, 1):
    success = db.save_trade(trade)
    if success:
        print(f"✅ Trade {i}/{len(trades)} saved: {trade['id']} - P&L: ${trade['pnl']:.2f}")
    else:
        print(f"❌ Failed to save trade {i}/{len(trades)}: {trade['id']}")

print("\nMigration complete!")
print(f"Total trades in database: {db.get_trade_count()}")

# Display stats
stats = db.get_performance_stats()
print("\nPerformance Stats:")
print(f"  Total Trades: {stats['total_trades']}")
print(f"  Wins: {stats['wins']}")
print(f"  Losses: {stats['losses']}")
print(f"  Win Rate: {stats['win_rate']:.1f}%")
print(f"  Total P&L: ${stats['total_pnl']:.2f}")
print(f"  Avg P&L: ${stats['avg_pnl']:.2f}")
print(f"  Best Trade: ${stats['best_trade']:.2f}")

db.close()
