#!/usr/bin/env python3
"""
Risk Manager for ADX Strategy v2.0
Enforces all risk limits and circuit breakers
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskManager:
    """
    Comprehensive Risk Manager

    Features:
    - Daily loss limits
    - Maximum drawdown tracking
    - Concurrent position limits
    - Risk per trade validation
    - Circuit breaker logic
    - Emergency stop mechanism
    """

    def __init__(self,
                 initial_capital: float = 100.0,
                 daily_loss_limit_percent: float = 5.0,
                 max_drawdown_percent: float = 15.0,
                 max_concurrent_positions: int = 2,
                 risk_per_trade_percent: float = 2.0,
                 max_risk_per_trade_percent: float = 3.0,
                 consecutive_loss_limit: int = 3):
        """
        Initialize risk manager

        Args:
            initial_capital: Starting capital
            daily_loss_limit_percent: Max daily loss (%)
            max_drawdown_percent: Max drawdown (%)
            max_concurrent_positions: Max open positions
            risk_per_trade_percent: Target risk per trade
            max_risk_per_trade_percent: Maximum risk per trade
            consecutive_loss_limit: Stop after N consecutive losses
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.peak_capital = initial_capital

        self.daily_loss_limit_percent = daily_loss_limit_percent
        self.max_drawdown_percent = max_drawdown_percent
        self.max_concurrent_positions = max_concurrent_positions
        self.risk_per_trade_percent = risk_per_trade_percent
        self.max_risk_per_trade_percent = max_risk_per_trade_percent
        self.consecutive_loss_limit = consecutive_loss_limit

        # Tracking
        self.daily_pnl = 0.0
        self.daily_start_capital = initial_capital
        self.last_reset_date = datetime.now().date()

        self.open_positions = []
        self.consecutive_losses = 0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

        self.circuit_breaker_active = False
        self.circuit_breaker_reason = None

        logger.info(f"Risk Manager initialized: ${initial_capital}, daily limit: {daily_loss_limit_percent}%")

    def reset_daily_tracking(self):
        """Reset daily P&L tracking (call at start of new day)"""
        self.daily_pnl = 0.0
        self.daily_start_capital = self.current_capital
        self.last_reset_date = datetime.now().date()
        logger.info(f"Daily tracking reset: Starting capital ${self.current_capital:.2f}")

    def check_daily_reset(self):
        """Check if we need to reset daily tracking"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.reset_daily_tracking()

    def update_capital(self, new_capital: float):
        """Update current capital"""
        old_capital = self.current_capital
        self.current_capital = new_capital

        # Update peak capital
        if new_capital > self.peak_capital:
            self.peak_capital = new_capital

        logger.info(f"Capital updated: ${old_capital:.2f} → ${new_capital:.2f}")

    def record_trade_result(self, pnl: float, outcome: str):
        """
        Record trade result

        Args:
            pnl: Profit/Loss amount
            outcome: WIN, LOSS, or TIMEOUT
        """
        self.check_daily_reset()

        self.daily_pnl += pnl
        self.total_trades += 1

        if outcome == 'WIN':
            self.winning_trades += 1
            self.consecutive_losses = 0
        elif outcome == 'LOSS':
            self.losing_trades += 1
            self.consecutive_losses += 1

        logger.info(f"Trade recorded: {outcome}, P&L: ${pnl:.2f}, Daily P&L: ${self.daily_pnl:.2f}")

    def can_open_position(self) -> tuple[bool, Optional[str]]:
        """
        Check if new position can be opened

        Returns:
            (can_open, reason) tuple
        """
        # Check circuit breaker
        if self.circuit_breaker_active:
            return False, f"Circuit breaker active: {self.circuit_breaker_reason}"

        # Check concurrent positions
        if len(self.open_positions) >= self.max_concurrent_positions:
            return False, f"Max concurrent positions reached ({self.max_concurrent_positions})"

        # Check daily loss limit
        daily_loss_percent = (self.daily_pnl / self.daily_start_capital) * 100
        if daily_loss_percent <= -self.daily_loss_limit_percent:
            reason = f"Daily loss limit hit: {daily_loss_percent:.2f}% / -{self.daily_loss_limit_percent}%"
            self.activate_circuit_breaker(reason)
            return False, reason

        # Check max drawdown
        drawdown_percent = ((self.peak_capital - self.current_capital) / self.peak_capital) * 100
        if drawdown_percent >= self.max_drawdown_percent:
            reason = f"Max drawdown exceeded: {drawdown_percent:.2f}% / {self.max_drawdown_percent}%"
            self.activate_circuit_breaker(reason)
            return False, reason

        # Check consecutive losses
        if self.consecutive_losses >= self.consecutive_loss_limit:
            reason = f"Consecutive loss limit: {self.consecutive_losses} / {self.consecutive_loss_limit}"
            self.activate_circuit_breaker(reason)
            return False, reason

        return True, None

    def validate_trade_risk(self, position: Dict) -> tuple[bool, List[str]]:
        """
        Validate trade risk parameters

        Args:
            position: Position dictionary from position_sizer

        Returns:
            (is_valid, warnings) tuple
        """
        warnings = []
        is_valid = True

        # Check risk percentage
        risk_percent = position.get('actual_risk_percent', 0)
        if risk_percent > self.max_risk_per_trade_percent:
            warnings.append(f"Risk {risk_percent:.2f}% exceeds max {self.max_risk_per_trade_percent}%")
            is_valid = False

        # Check margin requirement
        margin_required = position.get('margin_required', 0)
        available_margin = self.current_capital * 0.8  # Use max 80% of capital

        if margin_required > available_margin:
            warnings.append(f"Margin ${margin_required:.2f} exceeds available ${available_margin:.2f}")
            is_valid = False

        # Check position size
        if not position.get('is_valid', False):
            warnings.append("Position size below minimum or invalid")
            is_valid = False

        return is_valid, warnings

    def activate_circuit_breaker(self, reason: str):
        """Activate circuit breaker (stops all trading)"""
        self.circuit_breaker_active = True
        self.circuit_breaker_reason = reason
        logger.critical(f"🚨 CIRCUIT BREAKER ACTIVATED: {reason}")

    def deactivate_circuit_breaker(self):
        """Manually deactivate circuit breaker"""
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = None
        self.consecutive_losses = 0
        logger.info("Circuit breaker deactivated")

    def add_open_position(self, position_id: str, position_data: Dict):
        """Add position to tracking"""
        self.open_positions.append({
            'id': position_id,
            'data': position_data,
            'opened_at': datetime.now()
        })
        logger.info(f"Position added: {position_id} ({len(self.open_positions)} open)")

    def remove_open_position(self, position_id: str):
        """Remove position from tracking"""
        self.open_positions = [p for p in self.open_positions if p['id'] != position_id]
        logger.info(f"Position removed: {position_id} ({len(self.open_positions)} open)")

    def get_risk_status(self) -> Dict:
        """Get current risk status"""
        self.check_daily_reset()

        daily_loss_percent = (self.daily_pnl / self.daily_start_capital) * 100 if self.daily_start_capital > 0 else 0
        drawdown = self.peak_capital - self.current_capital
        drawdown_percent = (drawdown / self.peak_capital) * 100 if self.peak_capital > 0 else 0

        daily_loss_remaining = self.daily_loss_limit_percent + daily_loss_percent
        drawdown_remaining = self.max_drawdown_percent - drawdown_percent

        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0

        return {
            'current_capital': self.current_capital,
            'peak_capital': self.peak_capital,
            'daily_pnl': self.daily_pnl,
            'daily_loss_percent': round(daily_loss_percent, 2),
            'daily_loss_limit': self.daily_loss_limit_percent,
            'daily_loss_remaining': round(daily_loss_remaining, 2),
            'drawdown': round(drawdown, 2),
            'drawdown_percent': round(drawdown_percent, 2),
            'drawdown_limit': self.max_drawdown_percent,
            'drawdown_remaining': round(drawdown_remaining, 2),
            'open_positions': len(self.open_positions),
            'max_positions': self.max_concurrent_positions,
            'positions_available': self.max_concurrent_positions - len(self.open_positions),
            'consecutive_losses': self.consecutive_losses,
            'consecutive_loss_limit': self.consecutive_loss_limit,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': round(win_rate, 2),
            'circuit_breaker_active': self.circuit_breaker_active,
            'circuit_breaker_reason': self.circuit_breaker_reason,
            'can_trade': not self.circuit_breaker_active and len(self.open_positions) < self.max_concurrent_positions
        }

    def get_risk_summary(self) -> str:
        """Generate human-readable risk summary"""
        status = self.get_risk_status()

        circuit_status = "🚨 ACTIVE" if status['circuit_breaker_active'] else "✅ Inactive"

        return f"""
{'='*60}
Risk Manager Status
{'='*60}
Capital:
  Current:          ${status['current_capital']:,.2f}
  Peak:             ${status['peak_capital']:,.2f}
  Drawdown:         ${status['drawdown']:,.2f} ({status['drawdown_percent']:.2f}%)
  DD Limit:         {status['drawdown_limit']:.2f}%
  DD Remaining:     {status['drawdown_remaining']:.2f}%

Daily Performance:
  P&L:              ${status['daily_pnl']:,.2f} ({status['daily_loss_percent']:+.2f}%)
  Loss Limit:       -{status['daily_loss_limit']:.2f}%
  Remaining:        {status['daily_loss_remaining']:.2f}%

Positions:
  Open:             {status['open_positions']} / {status['max_positions']}
  Available:        {status['positions_available']}

Trading Record:
  Total Trades:     {status['total_trades']}
  Wins:             {status['winning_trades']}
  Losses:           {status['losing_trades']}
  Win Rate:         {status['win_rate']:.1f}%
  Consecutive Loss: {status['consecutive_losses']} / {status['consecutive_loss_limit']}

Circuit Breaker:    {circuit_status}
{f"  Reason: {status['circuit_breaker_reason']}" if status['circuit_breaker_active'] else ''}

Can Trade:          {'✅ YES' if status['can_trade'] else '❌ NO'}
{'='*60}
"""


if __name__ == "__main__":
    # Test script
    print("Testing Risk Manager...")

    # Initialize
    rm = RiskManager(
        initial_capital=100.0,
        daily_loss_limit_percent=5.0,
        max_drawdown_percent=15.0,
        max_concurrent_positions=2,
        consecutive_loss_limit=3
    )

    # Test 1: Initial status
    print("\n1. Initial Status")
    print(rm.get_risk_summary())

    # Test 2: Check if can open position
    print("\n2. Can open position?")
    can_open, reason = rm.can_open_position()
    print(f"   Result: {'✅ YES' if can_open else f'❌ NO - {reason}'}")

    # Test 3: Add positions
    print("\n3. Opening positions...")
    rm.add_open_position("pos1", {'size': 0.001})
    rm.add_open_position("pos2", {'size': 0.001})

    can_open, reason = rm.can_open_position()
    print(f"   Can open 3rd: {'✅ YES' if can_open else f'❌ NO - {reason}'}")

    # Test 4: Record losses
    print("\n4. Recording consecutive losses...")
    rm.remove_open_position("pos1")
    rm.record_trade_result(-2.0, 'LOSS')
    rm.update_capital(98.0)

    rm.remove_open_position("pos2")
    rm.record_trade_result(-2.0, 'LOSS')
    rm.update_capital(96.0)

    rm.record_trade_result(-2.0, 'LOSS')
    rm.update_capital(94.0)

    print(f"   Consecutive losses: {rm.consecutive_losses}")
    can_open, reason = rm.can_open_position()
    print(f"   Can trade: {'✅ YES' if can_open else f'❌ NO - {reason}'}")

    # Test 5: Final status
    print("\n5. Final Status After Losses")
    print(rm.get_risk_summary())

    # Test 6: Deactivate circuit breaker
    print("\n6. Deactivating circuit breaker...")
    rm.deactivate_circuit_breaker()
    can_open, reason = rm.can_open_position()
    print(f"   Can trade: {'✅ YES' if can_open else f'❌ NO - {reason}'}")

    print("\n✅ Risk Manager test complete!")
