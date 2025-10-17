#!/bin/bash
# Start ADX Strategy v2.0 Live Paper Trading Bot

echo "=========================================="
echo "ADX STRATEGY v2.0 - PAPER TRADING"
echo "=========================================="
echo ""

# Create logs directory
mkdir -p logs

# Activate virtual environment
if [ -d "venv" ]; then
    echo "✅ Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  Virtual environment not found"
fi

# Check if config exists
if [ ! -f "config_live.json" ]; then
    echo "❌ Configuration file not found: config_live.json"
    exit 1
fi

echo "✅ Configuration loaded: config_live.json"
echo ""

# Display configuration
echo "Trading Parameters:"
echo "  Symbol: BTC-USDT"
echo "  Initial Capital: \$100"
echo "  Leverage: 5×"
echo "  Risk per Trade: 2%"
echo "  Max Positions: 2"
echo ""

# Confirm start
read -p "Start 48-hour paper trading session? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled"
    exit 1
fi

echo ""
echo "=========================================="
echo "🚀 STARTING LIVE PAPER TRADING BOT"
echo "=========================================="
echo ""
echo "Session Duration: 48 hours"
echo "Press Ctrl+C to stop gracefully"
echo ""

# Run the bot
python3 live_trader.py

# Check exit status
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ Trading session completed successfully"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "❌ Trading session ended with errors"
    echo "=========================================="
fi

echo ""
echo "Check logs/live_trading.log for details"
echo "Check logs/alerts.log for trading alerts"
echo "Check logs/final_snapshot.json for final state"
echo ""
