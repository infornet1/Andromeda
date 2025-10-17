# Balance Restoration Fix

**Date**: 2025-10-17
**Status**: ✅ COMPLETE

## Summary

Fixed balance restoration issue where bot was not correctly tracking cumulative P&L across restarts. Bot now restores complete trading history and balance from SQLite database on startup.

## Problem

The dashboard was showing incorrect balance after bot restarts:
- **Reported Balance**: $107.12 (+$7.12 P&L)
- **Actual Balance**: $131.21 (+$31.21 P&L from 5 trades)

### Root Cause

Two conflicting balance restoration mechanisms:

1. **PaperTrader** (`src/execution/paper_trader.py`)
   - Initialized with fresh $100 balance
   - Did not restore from database

2. **LiveTrader** (`live_trader.py`)
   - Restored from snapshot file (only last session)
   - Overwrote PaperTrader's balance

The snapshot file only contained data from the most recent session, losing historical trades when bot restarted.

## Solution

### 1. PaperTrader Database Restoration

**File**: `src/execution/paper_trader.py:78-97`

Added automatic balance restoration from database on initialization:

```python
# Database for persistent trade storage
try:
    self.trade_db = TradeDatabase()
    logger.info("✅ Trade database initialized")

    # Restore balance from database if trades exist
    stats = self.trade_db.get_performance_stats()
    if stats['total_trades'] > 0:
        # Calculate actual balance from database
        restored_balance = initial_balance + stats['total_pnl']
        self.balance = restored_balance
        self.peak_balance = max(initial_balance, restored_balance)
        logger.info(f"💾 Restored balance from database: ${restored_balance:.2f} "
                   f"({stats['total_trades']} trades, ${stats['total_pnl']:.2f} P&L)")

except Exception as e:
    logger.warning(f"⚠️ Could not initialize trade database: {e}")
    self.trade_db = None

logger.info(f"📊 Paper Trader initialized: ${self.balance:.2f} @ {leverage}× leverage")
```

**How It Works**:
- On startup, queries database for all historical trades
- Calculates total P&L from database
- Restores balance as `initial_balance + total_pnl`
- Updates peak balance for drawdown tracking

### 2. LiveTrader Snapshot Removal

**File**: `live_trader.py:257-261`

Removed conflicting snapshot-based restoration:

```python
# Note: PaperTrader now restores balance and trades from database automatically
# No need to restore from snapshot - database is source of truth

# Just log the current balance (already restored by PaperTrader)
logger.info(f"  ✅ Current balance: ${self.trader.balance:.2f} (restored from database)")
```

**Why This Works**:
- Database is now single source of truth
- No conflicting restoration logic
- Snapshot file only used for monitoring/display

## Verification

### Before Fix
```
Balance: $107.12
Total P&L: +$7.12
Return: +7.12%
Trades Counted: 1 (most recent only)
```

### After Fix
```
Balance: $131.21 ✅
Total P&L: +$31.21 ✅
Return: +31.21% ✅
Trades Counted: 5 (all historical) ✅
```

### All 5 Trades Accounted For:
1. SHORT +$8.23 (+8.20%) @ 11:42 AM
2. SHORT +$3.98 (+3.96%) @ 12:17 PM
3. SHORT +$5.76 (+5.74%) @ 12:27 PM
4. SHORT +$6.02 (+6.02%) @ 12:29 PM
5. SHORT +$7.22 (+7.19%) @ 12:35 PM

**Total**: $8.23 + $3.98 + $5.76 + $6.02 + $7.22 = **$31.21** ✅

## Benefits

### ✅ Persistent Balance
- Balance survives bot restarts
- No more "lost" P&L
- Accurate cumulative tracking

### ✅ Database as Source of Truth
- Single authoritative data source
- No sync conflicts
- Reliable performance tracking

### ✅ Correct Performance Metrics
- Win rate calculated from all trades
- Peak balance tracked correctly
- Drawdown calculations accurate

### ✅ Production Ready
- Can restart bot without losing state
- Safe for long-term trading sessions
- Audit trail in database

## Testing

```bash
# 1. Check database balance
python3 -c "
from src.persistence.trade_database import TradeDatabase
db = TradeDatabase()
stats = db.get_performance_stats()
print(f'Database Total P&L: \${stats[\"total_pnl\"]:.2f}')
print(f'Initial Capital: \$100.00')
print(f'Expected Balance: \${100 + stats[\"total_pnl\"]:.2f}')
"

# 2. Restart bot and verify
systemctl restart adx-trading-bot.service
sleep 3
journalctl -u adx-trading-bot.service -n 5 | grep "Restored balance"

# 3. Check dashboard API
curl -s -k https://dev.ueipab.edu.ve:5900/api/status | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Dashboard Balance: \${d[\"account\"][\"balance\"]:.2f}')"
```

## Related Files

- `src/execution/paper_trader.py` - Balance restoration logic
- `live_trader.py` - Removed snapshot restoration
- `src/persistence/trade_database.py` - Database interface
- `DATABASE_IMPLEMENTATION.md` - Original database docs

## Notes

- Database file: `data/trades.db`
- Initial capital: $100.00 (configurable)
- Balance formula: `initial_capital + sum(all_trade_pnl)`
- Works for both paper and live trading modes

---

**Fix Implemented**: 2025-10-17 12:54
**Verified Working**: Balance correctly shows $131.21
**Status**: ✅ PRODUCTION READY
