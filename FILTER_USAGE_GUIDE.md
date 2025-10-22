# Quick Guide: Trade History Filter

## How to Filter Trades by Mode

### Option 1: Using the Dashboard API

**Get all trades:**
```
https://dev.ueipab.edu.ve:5900/api/trades?limit=20
```

**Get only paper trades:**
```
https://dev.ueipab.edu.ve:5900/api/trades?limit=20&mode=paper
```

**Get only live trades:**
```
https://dev.ueipab.edu.ve:5900/api/trades?limit=20&mode=live
```

### Option 2: Using Python

```python
from src.persistence.trade_database import TradeDatabase

db = TradeDatabase('data/trades.db')

# All trades
all_trades = db.get_all_trades(limit=50)

# Paper only
paper_trades = db.get_all_trades(limit=50, trading_mode='paper')

# Live only
live_trades = db.get_all_trades(limit=50, trading_mode='live')
```

### Option 3: Using the Test Script

```bash
cd /var/www/dev/trading/adx_strategy_v2
python3 test_trade_filter.py
```

## Current Status

- **Total Trades:** 30
- **Paper Trades:** 30
- **Live Trades:** 0

All your trades are currently from paper trading (as expected).

## When You Go Live

When you switch to live trading mode, new trades will automatically be tagged as `mode='live'`, and you'll be able to filter and compare:

- Paper trading performance vs live trading performance
- Win rates in simulation vs real markets
- Risk/reward profiles in each mode

## Benefits

- ✅ Clean separation of test vs real trading
- ✅ Easy performance comparison
- ✅ Track improvement over time
- ✅ Verify strategy before scaling capital

---

**Documentation:** See `TRADE_MODE_FILTER_FEATURE.md` for full details
