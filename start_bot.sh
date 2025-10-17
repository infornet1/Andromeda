#!/bin/bash
# ADX Trading Bot Startup Script

cd /var/www/dev/trading/adx_strategy_v2
source venv/bin/activate
exec python3 live_trader.py
