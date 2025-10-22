// ADX Strategy v2.0 - Dashboard JavaScript
// Auto-refresh and dynamic updates

const REFRESH_INTERVAL = 5000; // 5 seconds
let refreshTimer = null;
let countdownTimer = null;
let countdown = 5;

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Dashboard initialized');
    fetchAllData();
    startAutoRefresh();
});

// Start auto-refresh cycle
function startAutoRefresh() {
    refreshTimer = setInterval(fetchAllData, REFRESH_INTERVAL);
    startCountdown();
}

// Countdown timer
function startCountdown() {
    countdown = 5;
    countdownTimer = setInterval(() => {
        countdown--;
        document.getElementById('countdown').textContent = countdown;
        if (countdown <= 0) {
            countdown = 5;
        }
    }, 1000);
}

// Fetch all data from API
async function fetchAllData() {
    try {
        await Promise.all([
            fetchStatus(),
            fetchADX(),
            fetchPerformance(),
            fetchRisk(),
            fetchTrades()
        ]);
        updateLastUpdateTime();
    } catch (error) {
        console.error('Error fetching data:', error);
    }
}

// Fetch status (account, positions, BTC price)
async function fetchStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        // Update bot status
        const statusIndicator = document.getElementById('botStatus');
        const statusDot = statusIndicator.querySelector('.status-dot');
        const statusText = statusIndicator.querySelector('.status-text');

        if (data.bot_status.running) {
            statusDot.classList.remove('inactive');
            statusDot.classList.add('active');
            statusText.textContent = 'LIVE';
        } else {
            statusDot.classList.remove('active');
            statusDot.classList.add('inactive');
            statusText.textContent = 'OFFLINE';
        }

        // Update account stats
        const account = data.account;
        // Use initial capital from config or default to 160
        const INITIAL_CAPITAL = 160.0;
        document.getElementById('balance').textContent = formatCurrency(account.balance);
        const balanceChange = account.balance - INITIAL_CAPITAL;
        document.getElementById('balanceChange').textContent = formatCurrency(balanceChange);
        setColorClass('balanceChange', balanceChange);

        document.getElementById('totalPnl').textContent = formatCurrency(account.total_pnl);
        document.getElementById('pnlPercent').textContent = formatPercent(account.total_return_percent);
        setColorClass('totalPnl', account.total_pnl);
        setColorClass('pnlPercent', account.total_pnl);

        document.getElementById('positions').textContent = `${data.positions_count}/2`;
        document.getElementById('unrealizedPnl').textContent = formatCurrency(account.unrealized_pnl);
        setColorClass('unrealizedPnl', account.unrealized_pnl);

        document.getElementById('btcPrice').textContent = formatCurrency(data.btc_price);

        // Update positions
        updatePositions(data.positions);

    } catch (error) {
        console.error('Error fetching status:', error);
    }
}

// Fetch ADX data
async function fetchADX() {
    try {
        const response = await fetch('/api/adx');
        const data = await response.json();

        document.getElementById('adxValue').textContent = data.adx.toFixed(2);
        document.getElementById('plusDi').textContent = data.plus_di.toFixed(2);
        document.getElementById('minusDi').textContent = data.minus_di.toFixed(2);
        document.getElementById('diSpread').textContent = data.di_spread.toFixed(2);
        document.getElementById('adxSlope').textContent = data.adx_slope.toFixed(2);
        document.getElementById('confidence').textContent = data.confidence.toFixed(1) + '%';

        // Update ADX bar (max 50)
        const adxPercent = Math.min((data.adx / 50) * 100, 100);
        document.getElementById('adxBar').style.width = adxPercent + '%';

        // Update market state
        const marketState = document.getElementById('marketState');
        marketState.textContent = data.market_state;
        marketState.classList.remove('trending', 'ranging', 'building');
        marketState.classList.add(data.market_state.toLowerCase());

        // Color code metrics
        setColorClass('adxValue', data.adx >= 25 ? 1 : -1);
        setColorClass('adxSlope', data.adx_slope);
        setColorClass('diSpread', data.di_spread);

    } catch (error) {
        console.error('Error fetching ADX:', error);
    }
}

// Fetch performance stats
async function fetchPerformance() {
    try {
        const response = await fetch('/api/performance');
        const data = await response.json();

        document.getElementById('totalTrades').textContent = data.total_trades;
        document.getElementById('winRate').textContent = data.win_rate.toFixed(1) + '%';
        document.getElementById('winsLosses').textContent = `${data.wins} / ${data.losses}`;
        document.getElementById('profitFactor').textContent = data.profit_factor ? data.profit_factor.toFixed(2) : '--';
        document.getElementById('avgPnl').textContent = formatCurrency(data.avg_pnl);
        document.getElementById('bestTrade').textContent = formatCurrency(data.best_trade);

        setColorClass('winRate', data.win_rate >= 50 ? 1 : -1);
        setColorClass('avgPnl', data.avg_pnl);
        setColorClass('bestTrade', data.best_trade);

    } catch (error) {
        console.error('Error fetching performance:', error);
    }
}

// Fetch risk status
async function fetchRisk() {
    try {
        const response = await fetch('/api/risk');
        const data = await response.json();

        document.getElementById('dailyPnl').textContent = formatCurrency(data.daily_pnl);
        document.getElementById('maxDrawdown').textContent = data.max_drawdown.toFixed(2) + '%';
        document.getElementById('consecutive').textContent = `${data.consecutive_wins}W / ${data.consecutive_losses}L`;

        // Update progress bars
        const dailyPnlPercent = Math.abs(data.daily_pnl / data.daily_loss_limit) * 100;
        updateProgressBar('dailyPnlBar', dailyPnlPercent, data.daily_pnl < 0);

        const drawdownPercent = (data.max_drawdown / data.max_drawdown_limit) * 100;
        updateProgressBar('drawdownBar', drawdownPercent, true);

        // Circuit breaker status
        const circuitStatus = document.getElementById('circuitStatus');
        if (data.circuit_breaker) {
            circuitStatus.textContent = 'ACTIVE';
            circuitStatus.classList.add('active');
        } else {
            circuitStatus.textContent = 'OK';
            circuitStatus.classList.remove('active');
        }

        setColorClass('dailyPnl', data.daily_pnl);

    } catch (error) {
        console.error('Error fetching risk:', error);
    }
}

// Fetch trade history with optional filter
async function fetchTrades() {
    try {
        // Get selected filter mode
        const filterSelect = document.getElementById('tradeFilter');
        const mode = filterSelect ? filterSelect.value : '';

        // Build URL with filter
        let url = '/api/trades?limit=10';
        if (mode) {
            url += `&mode=${mode}`;
        }

        const response = await fetch(url);
        const data = await response.json();

        const container = document.getElementById('tradesContainer');

        if (data.trades.length === 0) {
            const filterText = mode ? ` (${mode} mode)` : '';
            container.innerHTML = `<div class="empty-state">No trades yet${filterText}</div>`;
            return;
        }

        container.innerHTML = data.trades.map(trade => `
            <div class="trade-item ${trade.pnl > 0 ? 'win' : 'loss'}">
                <div class="trade-header">
                    <span class="trade-side">${trade.side}</span>
                    <span class="trade-mode-badge ${trade.trading_mode || 'paper'}">${(trade.trading_mode || 'paper').toUpperCase()}</span>
                    <span class="trade-pnl ${trade.pnl > 0 ? 'positive' : 'negative'}">
                        ${formatCurrency(trade.pnl)}
                    </span>
                </div>
                <div class="trade-details">
                    <span>${formatCurrency(trade.entry_price)} → ${formatCurrency(trade.exit_price)}</span>
                    <span>${trade.exit_reason}</span>
                </div>
                <div class="trade-details">
                    <span>${formatHoldTime(trade.hold_duration * 3600)}</span>
                    <span>${formatPercent(trade.pnl_percent)}</span>
                </div>
                <div class="trade-timestamp">
                    ${formatTimestamp(trade.closed_at)}
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error fetching trades:', error);
    }
}

// Update positions display
function updatePositions(positions) {
    const container = document.getElementById('positionsContainer');

    if (positions.length === 0) {
        container.innerHTML = '<div class="empty-state">No open positions</div>';
        return;
    }

    container.innerHTML = positions.map(pos => `
        <div class="position-card ${pos.side.toLowerCase()}">
            <div class="position-header">
                <span class="position-side">${pos.side}</span>
                <span class="position-pnl ${pos.unrealized_pnl > 0 ? 'positive' : 'negative'}">
                    ${formatCurrency(pos.unrealized_pnl)}
                </span>
            </div>
            <div class="position-details">
                <div class="position-detail">
                    <span>Entry:</span>
                    <span>${formatCurrency(pos.entry_price)}</span>
                </div>
                <div class="position-detail">
                    <span>Current:</span>
                    <span>${formatCurrency(pos.current_price)}</span>
                </div>
                <div class="position-detail">
                    <span>Stop Loss:</span>
                    <span>${formatCurrency(pos.stop_loss)}</span>
                </div>
                <div class="position-detail">
                    <span>Take Profit:</span>
                    <span>${formatCurrency(pos.take_profit)}</span>
                </div>
            </div>
        </div>
    `).join('');
}

// Update progress bar
function updateProgressBar(id, percent, isDanger) {
    const bar = document.getElementById(id);
    bar.style.width = Math.min(percent, 100) + '%';

    bar.classList.remove('warning', 'danger');
    if (isDanger && percent > 80) {
        bar.classList.add('danger');
    } else if (isDanger && percent > 50) {
        bar.classList.add('warning');
    }
}

// Update last update time
function updateLastUpdateTime() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString();
    document.getElementById('lastUpdate').textContent = `Last update: ${timeStr}`;
}

// Utility: Format currency
function formatCurrency(value) {
    if (typeof value !== 'number') return '$0.00';
    const sign = value >= 0 ? '+' : '';
    return sign + '$' + Math.abs(value).toFixed(2);
}

// Utility: Format percent
function formatPercent(value) {
    if (typeof value !== 'number') return '0.00%';
    const sign = value >= 0 ? '+' : '';
    return sign + value.toFixed(2) + '%';
}

// Utility: Format hold time
function formatHoldTime(seconds) {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
}

// Utility: Format timestamp
function formatTimestamp(timestamp) {
    if (!timestamp) return '--';
    const date = new Date(timestamp);
    const now = new Date();

    // If today, show time only
    if (date.toDateString() === now.toDateString()) {
        return '🕐 Today ' + date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
    }

    // If yesterday
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (date.toDateString() === yesterday.toDateString()) {
        return '🕐 Yesterday ' + date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
    }

    // Otherwise show full date and time
    return '🕐 ' + date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric'
    }) + ' ' + date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
    });
}

// Utility: Set color class based on value
function setColorClass(id, value) {
    const element = document.getElementById(id);
    if (!element) return;

    element.classList.remove('positive', 'negative');
    if (value > 0) {
        element.classList.add('positive');
    } else if (value < 0) {
        element.classList.add('negative');
    }
}

// Filter trades by mode (called by dropdown onchange)
function filterTrades() {
    console.log('🔄 Filtering trades...');
    fetchTrades();
}

// Error handling for fetch
window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', event.reason);
});
