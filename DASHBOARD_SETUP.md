# ADX Strategy v2.0 - Web Dashboard Setup

**Created**: 2025-10-17
**Status**: ✅ OPERATIONAL
**Port**: 5900
**Service**: adx-dashboard.service

---

## Overview

Real-time web dashboard for monitoring ADX Strategy v2.0 paper/live trading bot. Provides live market data, position tracking, performance metrics, and risk management monitoring.

## Access

- **Local**: http://localhost:5900
- **External**: http://64.23.157.121:5900
- **Health Check**: http://localhost:5900/health

## Architecture

### Components

1. **Backend**: Flask web server (`dashboard_web.py`)
2. **Frontend**: HTML/CSS/JavaScript with auto-refresh
3. **Data Source**: Reads from `logs/final_snapshot.json` + live BingX API
4. **Service**: Systemd service for auto-start and monitoring

### File Structure

```
/var/www/dev/trading/adx_strategy_v2/
├── dashboard_web.py              # Flask server (port 5900)
├── templates/
│   └── dashboard.html            # Main dashboard page
├── static/
│   ├── css/
│   │   └── dashboard.css         # Dark theme styling
│   └── js/
│       └── dashboard.js          # Auto-refresh logic (5s)
└── systemd/
    └── adx-dashboard.service     # Systemd service file
```

---

## API Endpoints

### GET /
Main dashboard HTML page

### GET /health
Health check endpoint
```json
{
  "status": "ok",
  "service": "adx-dashboard",
  "timestamp": "2025-10-17T12:05:01.984209"
}
```

### GET /api/status
Complete status snapshot
```json
{
  "timestamp": "2025-10-17T12:05:06.812663",
  "bot_status": {
    "running": true,
    "status": "active",
    "last_update": "2025-10-17T11:42:15.756182"
  },
  "account": {
    "balance": 100.0,
    "equity": 100.0,
    "available": 100.0,
    "margin_used": 0.0,
    "unrealized_pnl": 0.0,
    "total_pnl": 0.0,
    "total_return_percent": 0.0,
    "peak_balance": 100.0,
    "max_drawdown": 0.0
  },
  "positions": [],
  "positions_count": 0,
  "btc_price": 107096.5
}
```

### GET /api/adx
Current ADX indicators from live BingX data
```json
{
  "adx": 27.99,
  "plus_di": 15.96,
  "minus_di": 19.45,
  "di_spread": -3.49,
  "adx_slope": -0.46,
  "market_state": "TRENDING",
  "trend_strength": "STRONG",
  "confidence": 39.2
}
```

### GET /api/trades?limit=10
Recent trade history
```json
{
  "trades": [
    {
      "side": "SHORT",
      "entry_price": 107904.17,
      "exit_price": 106134.23,
      "pnl": 8.23,
      "pnl_percent": 8.20,
      "exit_reason": "TAKE_PROFIT",
      "hold_time_seconds": 8
    }
  ]
}
```

### GET /api/performance
Performance statistics
```json
{
  "total_trades": 1,
  "wins": 1,
  "losses": 0,
  "win_rate": 100.0,
  "profit_factor": null,
  "total_pnl": 8.23,
  "avg_pnl": 8.23,
  "best_trade": 8.23,
  "worst_trade": 0.0
}
```

### GET /api/risk
Risk management status
```json
{
  "daily_pnl": 8.23,
  "daily_loss_limit": 5.0,
  "max_drawdown": 0.0,
  "max_drawdown_limit": 15.0,
  "circuit_breaker": false,
  "positions_open": 0,
  "positions_max": 2,
  "consecutive_wins": 1,
  "consecutive_losses": 0,
  "can_trade": true
}
```

---

## Dashboard Features

### 1. Real-Time Updates
- Auto-refresh every 5 seconds
- Countdown timer showing next update
- Last update timestamp

### 2. Quick Stats (Top Cards)
- **Balance**: Current account balance with change from initial $100
- **Total P&L**: Cumulative profit/loss with percentage
- **Open Positions**: Active positions count (X/2) with unrealized P&L
- **BTC Price**: Current BTC-USDT price from BingX

### 3. ADX Indicators Panel
- **ADX Value**: Large display with visual progress bar (0-50 scale)
- **Market State**: Badge showing RANGING/BUILDING/TRENDING
- **+DI / -DI**: Directional indicators
- **DI Spread**: Difference between directional indicators
- **ADX Slope**: Rate of change (momentum indicator)
- **Confidence**: Signal confidence percentage

### 4. Active Positions Panel
- Live position cards with color coding (GREEN=LONG, RED=SHORT)
- Entry price, current price, unrealized P&L
- Stop loss and take profit levels
- Empty state when no positions

### 5. Performance Panel
- Total trades count
- Win rate percentage
- Wins/Losses breakdown
- Profit factor ratio
- Average P&L per trade
- Best trade profit

### 6. Risk Management Panel
- **Daily P&L**: Progress bar vs 5% limit
- **Max Drawdown**: Progress bar vs 15% limit
- **Margin Used**: Shows margin utilization
- **Consecutive Trades**: Win/loss streak tracking
- **Circuit Breaker**: Status indicator (OK/ACTIVE)

### 7. Trade History Panel
- Last 10 closed trades
- Side (LONG/SHORT), P&L, entry/exit prices
- Exit reason (TAKE_PROFIT, STOP_LOSS, etc.)
- Hold time duration
- P&L percentage

---

## Service Management

### Start Dashboard
```bash
systemctl start adx-dashboard.service
```

### Stop Dashboard
```bash
systemctl stop adx-dashboard.service
```

### Restart Dashboard
```bash
systemctl restart adx-dashboard.service
```

### Check Status
```bash
systemctl status adx-dashboard.service
```

### View Logs
```bash
journalctl -u adx-dashboard.service -f
```

### Enable Auto-Start on Boot
```bash
systemctl enable adx-dashboard.service
```

---

## Installation Steps

### 1. Install Flask Dependencies
```bash
cd /var/www/dev/trading/adx_strategy_v2
source venv/bin/activate
pip install flask
```

### 2. Copy Systemd Service File
```bash
sudo cp systemd/adx-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### 3. Enable and Start Service
```bash
sudo systemctl enable adx-dashboard.service
sudo systemctl start adx-dashboard.service
```

### 4. Verify Service is Running
```bash
systemctl status adx-dashboard.service
curl http://localhost:5900/health
```

---

## Design

### Dark Theme
- **Background**: #1e1e1e (dark charcoal)
- **Cards**: #2d2d2d (medium gray)
- **Tertiary**: #3a3a3a (light gray)
- **Accent**: #00aaff (blue)
- **Positive**: #00ff88 (green)
- **Negative**: #ff4444 (red)
- **Warning**: #ffaa00 (orange)

### Responsive Design
- Desktop: 2-column grid layout
- Tablet: Single column layout
- Mobile: Stacked cards, simplified navigation

### Animations
- Pulsing status dots
- Smooth progress bar transitions
- Hover effects on cards
- Shimmer loading effect

---

## Data Flow

```
┌─────────────────┐
│  BingX API      │──┐
│  (Live Data)    │  │
└─────────────────┘  │
                     ▼
┌─────────────────┐  ┌──────────────────────┐
│  Trading Bot    │─▶│  final_snapshot.json │
│  (live_trader)  │  │  (Bot State)         │
└─────────────────┘  └──────────────────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │  Dashboard      │
                     │  Flask Server   │
                     │  (Port 5900)    │
                     └─────────────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │  Web Browser    │
                     │  (Auto-refresh) │
                     └─────────────────┘
```

1. **Trading Bot** writes state to `logs/final_snapshot.json` every cycle
2. **Dashboard Backend** reads snapshot + queries BingX API for live data
3. **Dashboard Frontend** polls API every 5 seconds via AJAX
4. **Browser** updates UI with latest data

---

## Troubleshooting

### Dashboard Not Loading

**Check Service Status**:
```bash
systemctl status adx-dashboard.service
```

**Check Logs**:
```bash
journalctl -u adx-dashboard.service -n 50
```

**Common Issues**:
- Port 5900 already in use: Check with `lsof -i :5900`
- Flask not installed: `venv/bin/pip install flask`
- Permission denied: Check file permissions on dashboard_web.py

### API Returning Errors

**Check Bot is Running**:
```bash
systemctl status adx-trading-bot.service
```

**Check Snapshot File**:
```bash
cat logs/final_snapshot.json | python3 -m json.tool
```

**Check API Keys**:
```bash
grep BINGX_API_KEY config/.env
```

### Dashboard Shows Stale Data

**Check Last Update Timestamp**: Should update every 5 seconds

**Verify Bot is Writing Snapshot**:
```bash
stat logs/final_snapshot.json  # Check modification time
```

**Check Browser Console**: F12 → Console tab for JavaScript errors

---

## Security Notes

- Dashboard runs on port 5900 (accessible from external network)
- **NO TRADE EXECUTION**: Dashboard is read-only monitoring
- API keys stored in `config/.env` (not exposed to web)
- No authentication implemented (internal use only)
- Consider firewall rules for production deployment

---

## Future Enhancements

- [ ] Add authentication (login page)
- [ ] WebSocket support for real-time push updates
- [ ] Historical P&L chart (Chart.js)
- [ ] Trade notification system
- [ ] Mobile app version
- [ ] Export trades to CSV
- [ ] Dark/Light theme toggle
- [ ] Multi-symbol support

---

## Related Documentation

- **Bot Status**: `LIVE_TRADING_STATUS.md`
- **Project Overview**: `PROJECT_COMPLETE.md`
- **Bug Fixes**: `BUGFIX_2025-10-17.md`
- **Port Configuration**: `PORT_INFO.md`

---

## Change Log

### 2025-10-17
- ✅ Initial dashboard creation
- ✅ Flask server implementation
- ✅ All API endpoints working
- ✅ Dark theme UI completed
- ✅ Auto-refresh functionality
- ✅ Systemd service configured
- ✅ Service deployed and running on port 5900
