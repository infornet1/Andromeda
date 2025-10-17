# BingX Live Trading - Go Live Checklist

**Target**: Transition from paper trading to live trading on BingX
**Date Created**: 2025-10-17
**Status**: 📋 PLANNING

---

## Current Status

### ✅ Completed (Paper Trading Phase)
- [x] ADX Strategy v2.0 implemented
- [x] Paper trading simulator working
- [x] SQLite database for persistent storage
- [x] Balance restoration across restarts
- [x] Web dashboard (HTTPS)
- [x] Risk management system
- [x] Position sizing (2% risk per trade)
- [x] Email notifications
- [x] 5 successful paper trades (100% win rate, +31.21%)

### Current Configuration
- **Mode**: Paper Trading
- **Initial Capital**: $100 (simulated)
- **Leverage**: 5x
- **Risk Per Trade**: 2%
- **Max Positions**: 2
- **Symbol**: BTC-USDT
- **Timeframe**: 5m
- **Session Duration**: 48 hours

---

## Pre-Live Requirements

### 1. ⚠️ BingX Account Setup

#### Account Requirements
- [ ] Verified BingX account
- [ ] KYC completed
- [ ] Futures trading enabled
- [ ] API access enabled

#### API Key Configuration
- [ ] Create API key with trading permissions
- [ ] Enable futures trading permission
- [ ] Enable reading account balance
- [ ] Enable placing orders
- [ ] Enable canceling orders
- [ ] Whitelist server IP: `64.23.157.121`
- [ ] Save API key securely
- [ ] Save API secret securely

#### Security Settings
- [ ] Enable 2FA on account
- [ ] Set withdrawal whitelist
- [ ] Enable login notification
- [ ] Set API key restrictions (IP whitelist)
- [ ] Disable unnecessary permissions

### 2. 💰 Capital & Risk Management

#### Initial Capital Decision
- [ ] Decide initial trading capital
- [ ] **Recommended minimum**: $500 - $1,000
- [ ] **Conservative**: $1,000 - $2,000
- [ ] **Aggressive**: $2,000+
- [ ] Fund BingX futures wallet

#### Risk Parameters Review
Current settings (from `config_live.json`):
```json
{
  "initial_capital": 100.0,        // ⚠️ UPDATE THIS
  "leverage": 5,                   // Review if appropriate
  "risk_per_trade_percent": 2.0,   // 2% of capital per trade
  "max_positions": 2,              // Maximum open positions
  "daily_loss_limit_percent": 5.0, // Stop trading if lose 5% in day
  "max_drawdown_percent": 15.0,    // Circuit breaker at 15% drawdown
  "consecutive_loss_limit": 3      // Stop after 3 losses in a row
}
```

#### Capital & Risk Review Tasks
- [ ] Set appropriate `initial_capital` in config
- [ ] Confirm leverage is suitable (5x = moderate)
- [ ] Review daily loss limit (5% = $50 on $1000)
- [ ] Review max drawdown (15% = $150 on $1000)
- [ ] Understand position sizing:
  - With $1000 capital, 2% risk = $20 per trade
  - With 5x leverage: can control $100 position with $20 margin
  - Stop loss determines actual BTC quantity

### 3. 🧪 Live API Testing (Required!)

#### Test BingX API Connection
- [ ] Test API authentication
- [ ] Test fetching account balance
- [ ] Test fetching current positions
- [ ] Test placing **testnet** orders (if BingX has testnet)
- [ ] Test canceling orders
- [ ] Test websocket connection (if using)
- [ ] Verify API rate limits

#### Create Test Script
```bash
# Test BingX API connectivity
python3 test_bingx_live_api.py
```

Tasks:
- [ ] Create `test_bingx_live_api.py` script
- [ ] Test all required API endpoints
- [ ] Verify order placement works
- [ ] Verify position closing works
- [ ] Test error handling

### 4. 🔧 Code Modifications for Live Trading

#### Current Issues to Address

##### A. Live Order Execution
**Status**: Currently using paper trading simulator

**Required Changes**:
- [ ] Review `src/execution/order_executor.py`
- [ ] Implement real BingX order placement
- [ ] Add order confirmation checks
- [ ] Add retry logic for failed orders
- [ ] Add order status polling
- [ ] Handle partial fills
- [ ] Handle order rejections

##### B. Position Management
**Status**: Currently tracking virtual positions

**Required Changes**:
- [ ] Modify `src/execution/position_manager.py`
- [ ] Fetch real positions from BingX
- [ ] Sync local state with exchange
- [ ] Handle external position changes
- [ ] Add position reconciliation

##### C. Live Trader Mode Switch
**Status**: `live_trader.py` currently uses PaperTrader

**Required Changes**:
- [ ] Add `--mode` parameter: `paper` or `live`
- [ ] Create `LiveTrader` class (separate from PaperTrader)
- [ ] Implement real balance fetching
- [ ] Implement real order execution
- [ ] Add emergency stop mechanism

##### D. Price Feed
**Status**: Currently using REST API polling

**Options to Consider**:
- [ ] Keep REST polling (simpler, current method)
- [ ] Add WebSocket for real-time prices (better, more efficient)
- [ ] Decide on price feed method

##### E. Slippage & Fees
**Status**: Simulated in paper trading

**Required Changes**:
- [ ] Verify BingX trading fees (taker: ~0.05%, maker: ~0.02%)
- [ ] Update fee configuration to match actual fees
- [ ] Remove simulated slippage (real slippage will occur naturally)
- [ ] Add P&L calculations with real fees

### 5. 🛡️ Safety Mechanisms

#### Emergency Controls
- [ ] Implement emergency stop button/command
- [ ] Add manual override for circuit breaker
- [ ] Create position close-all function
- [ ] Add pause trading command
- [ ] Test emergency stop procedures

#### Monitoring & Alerts
- [ ] Email alerts for trade execution
- [ ] Email alerts for position opens/closes
- [ ] Email alerts for circuit breaker activation
- [ ] Email alerts for errors
- [ ] SMS alerts (optional, recommended)
- [ ] Test all alert mechanisms

#### Logging & Audit Trail
- [ ] Ensure all orders logged to database
- [ ] Log all API responses
- [ ] Log all errors with full context
- [ ] Create audit log for manual interventions
- [ ] Set up log rotation

### 6. 📊 Testing & Validation

#### Dry Run with Minimal Capital
- [ ] Fund account with minimal amount ($50-$100)
- [ ] Run bot in live mode for 24 hours
- [ ] Execute 2-3 real trades
- [ ] Verify orders execute correctly
- [ ] Verify positions close correctly
- [ ] Verify P&L calculations accurate
- [ ] Verify database records correct
- [ ] Verify dashboard shows correct data

#### Failure Scenario Testing
- [ ] Test network disconnection recovery
- [ ] Test bot restart during open position
- [ ] Test API timeout handling
- [ ] Test order rejection handling
- [ ] Test insufficient balance handling
- [ ] Test position close failure
- [ ] Verify circuit breaker activates correctly

### 7. 📝 Documentation & Procedures

#### Operating Procedures
- [ ] Document startup procedure
- [ ] Document shutdown procedure
- [ ] Document emergency stop procedure
- [ ] Document position close procedure
- [ ] Document configuration changes
- [ ] Create troubleshooting guide

#### Monitoring Procedures
- [ ] Define monitoring frequency (every hour? every 4 hours?)
- [ ] Create monitoring checklist
- [ ] Define normal vs abnormal behavior
- [ ] Create escalation procedures
- [ ] Document when to intervene manually

---

## Implementation Phases

### Phase 1: Preparation (1-2 days)
1. Set up BingX account with API keys
2. Create test script for API validation
3. Review and update configuration files
4. Test all API endpoints

### Phase 2: Code Development (2-3 days)
1. Implement live order execution
2. Implement real position management
3. Add live/paper mode switch
4. Implement emergency controls
5. Add comprehensive error handling

### Phase 3: Testing (2-3 days)
1. Test with minimal capital ($50-$100)
2. Execute 5-10 real trades
3. Test all failure scenarios
4. Verify monitoring and alerts
5. Test emergency procedures

### Phase 4: Production Deployment (1 day)
1. Fund account with production capital
2. Final configuration review
3. Start bot with full monitoring
4. Monitor closely for first 24 hours
5. Gradual increase in position sizes if successful

---

## Risk Warnings

### ⚠️ CRITICAL WARNINGS

1. **Real Money at Risk**: Live trading involves real capital that can be lost.

2. **Strategy Not Guaranteed**: Paper trading success doesn't guarantee live profits.

3. **Market Conditions Change**: Volatility, liquidity, slippage differ from paper trading.

4. **Technical Failures**: Bugs, network issues, API outages can cause losses.

5. **Exchange Risk**: BingX could have downtime, API issues, or (rarely) security issues.

6. **Start Small**: Always start with capital you can afford to lose completely.

### Recommended Approach

1. **Start with minimum capital** ($500-$1000)
2. **Run for 1 week** to verify everything works
3. **Monitor very closely** during first week
4. **Gradually increase** capital only after proven stability
5. **Never exceed** risk tolerance
6. **Be ready to stop** immediately if issues arise

---

## Key Code Files to Modify

### Critical Files
1. `src/execution/order_executor.py` - Real order execution
2. `src/execution/position_manager.py` - Real position tracking
3. `src/execution/paper_trader.py` - May need LiveTrader alternative
4. `live_trader.py` - Add mode switch

### Configuration Files
1. `config_live.json` - Update with real capital
2. `config/.env` - API keys (keep secure!)

### Testing Files (to create)
1. `test_bingx_live_api.py` - API connectivity test
2. `test_live_orders.py` - Order execution test
3. `emergency_stop.py` - Emergency shutdown script

---

## Next Steps

### Immediate Actions Required

1. **Review & Approve This Checklist**
   - Review all items with team/user
   - Adjust based on risk tolerance
   - Approve phase plan

2. **BingX Account Setup**
   - Create account if not exists
   - Complete KYC
   - Enable API access
   - Create API keys with appropriate permissions

3. **Decide on Capital**
   - Determine initial trading capital
   - Understand maximum loss tolerance
   - Fund BingX account

4. **Create API Test Script**
   - Test connectivity
   - Test all required endpoints
   - Validate order placement (testnet if available)

### Questions to Answer Before Proceeding

1. **What is the initial capital amount?** $_______
2. **What is maximum acceptable loss?** $_______
3. **Who will monitor the bot?** _______
4. **How often will it be monitored?** _______
5. **What are emergency contact procedures?** _______
6. **Is there a testnet available for testing?** Yes/No
7. **Start with paper mode first for how long?** _______ days
8. **Acceptable daily loss before manual intervention?** $_______

---

## Status Tracking

- [ ] Phase 1: Preparation - NOT STARTED
- [ ] Phase 2: Code Development - NOT STARTED
- [ ] Phase 3: Testing - NOT STARTED
- [ ] Phase 4: Production Deployment - NOT STARTED

**Current Status**: Paper trading with 5 successful trades (+31.21%)

**Ready to Proceed**: NO - Must complete checklist first

---

**Document Version**: 1.0
**Last Updated**: 2025-10-17
**Next Review**: Before Phase 1 starts
