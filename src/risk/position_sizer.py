#!/usr/bin/env python3
"""
Position Sizing Calculator for ADX Strategy v2.0
Calculates optimal position sizes based on risk parameters and leverage
"""

from typing import Dict, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PositionSizer:
    """
    Position Size Calculator

    Features:
    - Risk-based position sizing (1-2% per trade)
    - Leverage integration (5x default)
    - Kelly Criterion (optional)
    - Position size limits
    - Margin requirement calculation
    """

    def __init__(self,
                 initial_capital: float = 100.0,
                 risk_per_trade_percent: float = 2.0,
                 leverage: int = 5,
                 max_position_size_percent: float = 20.0,
                 min_position_size_usd: float = 10.0):
        """
        Initialize position sizer

        Args:
            initial_capital: Starting capital in USDT
            risk_per_trade_percent: Risk per trade as % of capital (1-2%)
            leverage: Leverage multiplier (1-20x)
            max_position_size_percent: Max position as % of capital
            min_position_size_usd: Minimum position size in USDT
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.risk_per_trade_percent = risk_per_trade_percent
        self.leverage = leverage
        self.max_position_size_percent = max_position_size_percent
        self.min_position_size_usd = min_position_size_usd

        logger.info(f"Position Sizer initialized: ${initial_capital} @ {leverage}x leverage")

    def update_capital(self, new_capital: float):
        """Update current capital after trades"""
        self.current_capital = new_capital
        logger.info(f"Capital updated: ${self.current_capital:.2f}")

    def calculate_position_size(self,
                                entry_price: float,
                                stop_loss: float,
                                account_balance: Optional[float] = None) -> Dict:
        """
        Calculate position size based on risk parameters

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            account_balance: Current account balance (uses current_capital if None)

        Returns:
            Dictionary with position sizing details
        """
        balance = account_balance or self.current_capital

        # Calculate risk amount in USDT
        risk_amount = balance * (self.risk_per_trade_percent / 100)

        # Calculate stop distance
        stop_distance = abs(entry_price - stop_loss)
        stop_distance_percent = (stop_distance / entry_price) * 100

        # Calculate position size based on risk
        # Position Size = Risk Amount / (Stop Distance % * Entry Price)
        # This ensures we only lose the risk amount if SL hits
        position_size_notional = risk_amount / (stop_distance_percent / 100)

        # Account for leverage (we can control larger position with less capital)
        # With 5x leverage: $100 capital = $500 position size max
        max_position_notional = balance * self.leverage

        # Position size in USDT (notional value)
        position_size_notional = min(
            position_size_notional,
            max_position_notional * (self.max_position_size_percent / 100)
        )

        # Convert to BTC quantity
        position_size_btc = position_size_notional / entry_price

        # Calculate margin required
        margin_required = position_size_notional / self.leverage

        # Calculate actual risk if position size was limited
        actual_risk_amount = (stop_distance_percent / 100) * position_size_notional
        actual_risk_percent = (actual_risk_amount / balance) * 100

        # Validate minimum position size
        if position_size_notional < self.min_position_size_usd:
            logger.warning(f"Position size ${position_size_notional:.2f} below minimum ${self.min_position_size_usd}")

        result = {
            'position_size_btc': round(position_size_btc, 5),
            'position_size_usd': round(position_size_notional, 2),
            'margin_required': round(margin_required, 2),
            'risk_amount': round(risk_amount, 2),
            'actual_risk_amount': round(actual_risk_amount, 2),
            'risk_percent': round(self.risk_per_trade_percent, 2),
            'actual_risk_percent': round(actual_risk_percent, 2),
            'stop_distance': round(stop_distance, 2),
            'stop_distance_percent': round(stop_distance_percent, 4),
            'leverage': self.leverage,
            'account_balance': round(balance, 2),
            'is_valid': position_size_notional >= self.min_position_size_usd
        }

        logger.debug(f"Position calculated: {result['position_size_btc']} BTC (${result['position_size_usd']})")

        return result

    def calculate_kelly_criterion(self,
                                  win_rate: float,
                                  avg_win: float,
                                  avg_loss: float) -> float:
        """
        Calculate Kelly Criterion for optimal position sizing

        Args:
            win_rate: Historical win rate (0-1)
            avg_win: Average win amount
            avg_loss: Average loss amount (positive number)

        Returns:
            Kelly percentage (0-1)
        """
        if avg_loss == 0 or win_rate == 0:
            return 0

        # Kelly = (Win Rate * Avg Win - Loss Rate * Avg Loss) / Avg Win
        loss_rate = 1 - win_rate
        win_loss_ratio = avg_win / avg_loss

        kelly = (win_rate * win_loss_ratio - loss_rate) / win_loss_ratio

        # Use fractional Kelly (25-50%) for safety
        fractional_kelly = max(0, min(kelly * 0.25, 0.5))

        logger.info(f"Kelly Criterion: {kelly:.2%} (Fractional: {fractional_kelly:.2%})")

        return fractional_kelly

    def calculate_with_kelly(self,
                            entry_price: float,
                            stop_loss: float,
                            win_rate: float,
                            avg_win: float,
                            avg_loss: float) -> Dict:
        """
        Calculate position size using Kelly Criterion

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            win_rate: Historical win rate (0-1)
            avg_win: Average win
            avg_loss: Average loss

        Returns:
            Position sizing with Kelly adjustment
        """
        # Get base position size
        base_position = self.calculate_position_size(entry_price, stop_loss)

        # Calculate Kelly percentage
        kelly_percent = self.calculate_kelly_criterion(win_rate, avg_win, avg_loss)

        # Adjust position size by Kelly
        adjusted_size_btc = base_position['position_size_btc'] * kelly_percent
        adjusted_size_usd = base_position['position_size_usd'] * kelly_percent

        base_position.update({
            'position_size_btc': round(adjusted_size_btc, 5),
            'position_size_usd': round(adjusted_size_usd, 2),
            'kelly_adjustment': kelly_percent,
            'original_size': base_position['position_size_btc']
        })

        return base_position

    def validate_position(self, position: Dict, max_margin_usage: float = 0.8) -> Dict:
        """
        Validate position against risk limits

        Args:
            position: Position dictionary from calculate_position_size
            max_margin_usage: Maximum margin usage (0-1)

        Returns:
            Validation result with warnings
        """
        warnings = []
        is_valid = True

        # Check minimum position size
        if position['position_size_usd'] < self.min_position_size_usd:
            warnings.append(f"Position size ${position['position_size_usd']:.2f} below minimum ${self.min_position_size_usd}")
            is_valid = False

        # Check margin usage
        margin_usage_percent = (position['margin_required'] / position['account_balance']) * 100
        if margin_usage_percent > max_margin_usage * 100:
            warnings.append(f"Margin usage {margin_usage_percent:.1f}% exceeds limit {max_margin_usage*100:.1f}%")
            is_valid = False

        # Check risk percentage
        if position['actual_risk_percent'] > self.risk_per_trade_percent * 1.5:
            warnings.append(f"Risk {position['actual_risk_percent']:.2f}% exceeds target {self.risk_per_trade_percent:.2f}%")
            is_valid = False

        return {
            'is_valid': is_valid,
            'warnings': warnings,
            'margin_usage_percent': round(margin_usage_percent, 2)
        }

    def calculate_profit_target(self,
                               entry_price: float,
                               stop_loss: float,
                               risk_reward_ratio: float = 2.0,
                               side: str = 'LONG') -> float:
        """
        Calculate take profit price based on risk/reward ratio

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_reward_ratio: Risk/Reward ratio (default 2:1)
            side: Position side (LONG or SHORT)

        Returns:
            Take profit price
        """
        stop_distance = abs(entry_price - stop_loss)
        target_distance = stop_distance * risk_reward_ratio

        if side == 'LONG':
            take_profit = entry_price + target_distance
        else:  # SHORT
            take_profit = entry_price - target_distance

        return round(take_profit, 2)

    def get_sizing_summary(self, position: Dict) -> str:
        """Generate human-readable position sizing summary"""
        return f"""
{'='*60}
Position Sizing Summary
{'='*60}
Account Balance:    ${position['account_balance']:,.2f}
Leverage:           {position['leverage']}x

Position:
  Size (BTC):       {position['position_size_btc']:.5f} BTC
  Size (USD):       ${position['position_size_usd']:,.2f}
  Margin Required:  ${position['margin_required']:,.2f}

Risk:
  Risk Amount:      ${position['risk_amount']:,.2f}
  Risk Percent:     {position['risk_percent']:.2f}%
  Actual Risk:      {position['actual_risk_percent']:.2f}%
  Stop Distance:    ${position['stop_distance']:,.2f} ({position['stop_distance_percent']:.2f}%)

Valid:              {'✅ Yes' if position['is_valid'] else '❌ No'}
{'='*60}
"""


if __name__ == "__main__":
    # Test script
    print("Testing Position Sizer...")

    # Initialize with $100 capital, 5x leverage
    sizer = PositionSizer(
        initial_capital=100.0,
        risk_per_trade_percent=2.0,
        leverage=5
    )

    # Test 1: Calculate position for LONG
    print("\n1. LONG Position (BTC @ $112,000)")
    entry = 112000
    stop_loss = 111500  # -$500 stop (-0.45%)
    take_profit = 113000  # +$1000 target (+0.89%)

    position = sizer.calculate_position_size(entry, stop_loss)
    print(sizer.get_sizing_summary(position))

    validation = sizer.validate_position(position)
    print(f"Validation: {'✅ PASSED' if validation['is_valid'] else '❌ FAILED'}")
    if validation['warnings']:
        for warning in validation['warnings']:
            print(f"  ⚠️  {warning}")

    # Test 2: Calculate position for SHORT
    print("\n2. SHORT Position (BTC @ $112,000)")
    entry = 112000
    stop_loss = 112500  # +$500 stop (+0.45%)
    take_profit = 111000  # -$1000 target (-0.89%)

    position = sizer.calculate_position_size(entry, stop_loss)
    print(f"Position Size: {position['position_size_btc']:.5f} BTC (${position['position_size_usd']:,.2f})")
    print(f"Margin Required: ${position['margin_required']:,.2f}")
    print(f"Risk: ${position['risk_amount']:,.2f} ({position['risk_percent']:.2f}%)")

    # Test 3: Kelly Criterion
    print("\n3. Kelly Criterion Adjustment")
    print("   Historical: 60% win rate, avg win $5, avg loss $3")

    kelly_position = sizer.calculate_with_kelly(
        entry, stop_loss,
        win_rate=0.60,
        avg_win=5.0,
        avg_loss=3.0
    )

    print(f"   Original Size: {position['position_size_btc']:.5f} BTC")
    print(f"   Kelly Adjusted: {kelly_position['position_size_btc']:.5f} BTC")
    print(f"   Kelly Factor: {kelly_position.get('kelly_adjustment', 0):.2%}")

    # Test 4: Calculate take profit
    print("\n4. Take Profit Calculator")
    tp_long = sizer.calculate_profit_target(entry, stop_loss, 2.0, 'LONG')
    tp_short = sizer.calculate_profit_target(entry, 112500, 2.0, 'SHORT')

    print(f"   LONG @ ${entry:,.0f}, SL ${stop_loss:,.0f} → TP ${tp_long:,.0f}")
    print(f"   SHORT @ ${entry:,.0f}, SL $112,500 → TP ${tp_short:,.0f}")

    print("\n✅ Position Sizer test complete!")
