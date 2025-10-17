#!/usr/bin/env python3
"""
Alert System for ADX Strategy v2.0
Manages notifications for important trading events
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from typing import Dict, List, Optional, Callable
from datetime import datetime
from enum import Enum
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertType(Enum):
    """Alert event types"""
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"
    TAKE_PROFIT_HIT = "TAKE_PROFIT_HIT"
    STOP_LOSS_HIT = "STOP_LOSS_HIT"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    DAILY_LOSS_WARNING = "DAILY_LOSS_WARNING"
    DRAWDOWN_WARNING = "DRAWDOWN_WARNING"
    CONSECUTIVE_LOSSES = "CONSECUTIVE_LOSSES"
    POSITION_LIMIT = "POSITION_LIMIT"
    BALANCE_MILESTONE = "BALANCE_MILESTONE"
    SYSTEM_ERROR = "SYSTEM_ERROR"


class AlertSystem:
    """
    Alert and Notification System

    Features:
    - Multi-level alerts (INFO, WARNING, CRITICAL)
    - Event-based notifications
    - Alert history tracking
    - Custom alert handlers
    - Alert filtering and routing
    """

    def __init__(self,
                 enable_console: bool = True,
                 enable_file: bool = True,
                 log_file: str = "/var/www/dev/trading/adx_strategy_v2/logs/alerts.log"):
        """
        Initialize alert system

        Args:
            enable_console: Print alerts to console
            enable_file: Write alerts to file
            log_file: Path to alert log file
        """
        self.enable_console = enable_console
        self.enable_file = enable_file
        self.log_file = log_file

        # Alert history
        self.alerts = []
        self.alert_count = {level: 0 for level in AlertLevel}

        # Custom handlers
        self.handlers = {}

        # Alert configuration
        self.min_level = AlertLevel.INFO
        self.muted_types = set()

        # Ensure log directory exists
        if enable_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)

        logger.info("Alert System initialized")

    def send_alert(self,
                   alert_type: AlertType,
                   level: AlertLevel,
                   message: str,
                   data: Optional[Dict] = None):
        """
        Send alert notification

        Args:
            alert_type: Type of alert
            level: Severity level
            message: Alert message
            data: Additional alert data
        """
        # Check if alert type is muted
        if alert_type in self.muted_types:
            return

        # Check if level is high enough
        level_priority = {AlertLevel.INFO: 0, AlertLevel.WARNING: 1, AlertLevel.CRITICAL: 2}
        if level_priority[level] < level_priority[self.min_level]:
            return

        # Create alert
        alert = {
            'id': len(self.alerts) + 1,
            'timestamp': datetime.now(),
            'type': alert_type.value,
            'level': level.value,
            'message': message,
            'data': data or {}
        }

        # Store alert
        self.alerts.append(alert)
        self.alert_count[level] += 1

        # Output alert
        self._output_alert(alert)

        # Call custom handlers
        if alert_type in self.handlers:
            try:
                self.handlers[alert_type](alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

        logger.debug(f"Alert sent: {alert_type.value} - {message}")

    def _output_alert(self, alert: Dict):
        """Output alert to configured destinations"""
        # Format alert
        formatted = self._format_alert(alert)

        # Console output
        if self.enable_console:
            print(formatted)

        # File output
        if self.enable_file:
            try:
                with open(self.log_file, 'a') as f:
                    f.write(formatted + '\n')
            except Exception as e:
                logger.error(f"Failed to write alert to file: {e}")

    def _format_alert(self, alert: Dict) -> str:
        """Format alert for display"""
        emoji = {
            'INFO': '📢',
            'WARNING': '⚠️ ',
            'CRITICAL': '🚨'
        }

        level_emoji = emoji.get(alert['level'], '📢')
        timestamp = alert['timestamp'].strftime('%Y-%m-%d %H:%M:%S')

        return f"{level_emoji} [{timestamp}] {alert['level']:<8} | {alert['type']:<25} | {alert['message']}"

    def register_handler(self, alert_type: AlertType, handler: Callable):
        """
        Register custom alert handler

        Args:
            alert_type: Alert type to handle
            handler: Callback function(alert_dict)
        """
        self.handlers[alert_type] = handler
        logger.info(f"Registered handler for {alert_type.value}")

    def mute_alert_type(self, alert_type: AlertType):
        """Mute specific alert type"""
        self.muted_types.add(alert_type)
        logger.info(f"Muted alerts: {alert_type.value}")

    def unmute_alert_type(self, alert_type: AlertType):
        """Unmute specific alert type"""
        if alert_type in self.muted_types:
            self.muted_types.remove(alert_type)
            logger.info(f"Unmuted alerts: {alert_type.value}")

    def set_min_level(self, level: AlertLevel):
        """Set minimum alert level"""
        self.min_level = level
        logger.info(f"Min alert level set to: {level.value}")

    def get_alerts(self,
                   level: Optional[AlertLevel] = None,
                   alert_type: Optional[AlertType] = None,
                   limit: Optional[int] = None) -> List[Dict]:
        """
        Get alerts with optional filtering

        Args:
            level: Filter by level
            alert_type: Filter by type
            limit: Maximum number of alerts

        Returns:
            List of alerts
        """
        filtered = self.alerts

        if level:
            filtered = [a for a in filtered if a['level'] == level.value]

        if alert_type:
            filtered = [a for a in filtered if a['type'] == alert_type.value]

        # Sort by timestamp (newest first)
        filtered = sorted(filtered, key=lambda x: x['timestamp'], reverse=True)

        if limit:
            filtered = filtered[:limit]

        return filtered

    def get_alert_summary(self) -> Dict:
        """Get alert statistics"""
        return {
            'total_alerts': len(self.alerts),
            'info_count': self.alert_count[AlertLevel.INFO],
            'warning_count': self.alert_count[AlertLevel.WARNING],
            'critical_count': self.alert_count[AlertLevel.CRITICAL],
            'last_alert': self.alerts[-1] if self.alerts else None,
            'muted_types': [t.value for t in self.muted_types]
        }

    def clear_alerts(self):
        """Clear alert history"""
        count = len(self.alerts)
        self.alerts = []
        self.alert_count = {level: 0 for level in AlertLevel}
        logger.info(f"Cleared {count} alerts")

    # Convenience methods for common alerts

    def position_opened(self, position_id: str, side: str, entry_price: float, quantity: float):
        """Alert for position opened"""
        self.send_alert(
            AlertType.POSITION_OPENED,
            AlertLevel.INFO,
            f"{side} position opened: {quantity:.5f} BTC @ ${entry_price:,.2f}",
            {'position_id': position_id, 'side': side, 'entry_price': entry_price, 'quantity': quantity}
        )

    def position_closed(self, position_id: str, side: str, pnl: float, reason: str):
        """Alert for position closed"""
        level = AlertLevel.INFO if pnl >= 0 else AlertLevel.WARNING
        emoji = '✅ WIN' if pnl >= 0 else '❌ LOSS'

        self.send_alert(
            AlertType.POSITION_CLOSED,
            level,
            f"{emoji}: {side} position closed, P&L: ${pnl:+.2f} ({reason})",
            {'position_id': position_id, 'side': side, 'pnl': pnl, 'reason': reason}
        )

    def take_profit_hit(self, position_id: str, tp_price: float, pnl: float):
        """Alert for take profit hit"""
        self.send_alert(
            AlertType.TAKE_PROFIT_HIT,
            AlertLevel.INFO,
            f"Take profit hit @ ${tp_price:,.2f}, P&L: ${pnl:+.2f}",
            {'position_id': position_id, 'tp_price': tp_price, 'pnl': pnl}
        )

    def stop_loss_hit(self, position_id: str, sl_price: float, pnl: float):
        """Alert for stop loss hit"""
        self.send_alert(
            AlertType.STOP_LOSS_HIT,
            AlertLevel.WARNING,
            f"Stop loss hit @ ${sl_price:,.2f}, P&L: ${pnl:+.2f}",
            {'position_id': position_id, 'sl_price': sl_price, 'pnl': pnl}
        )

    def circuit_breaker_triggered(self, reason: str):
        """Alert for circuit breaker activation"""
        self.send_alert(
            AlertType.CIRCUIT_BREAKER,
            AlertLevel.CRITICAL,
            f"CIRCUIT BREAKER ACTIVATED: {reason}",
            {'reason': reason}
        )

    def daily_loss_warning(self, current_loss: float, limit: float):
        """Alert for approaching daily loss limit"""
        percent_used = (abs(current_loss) / limit) * 100

        self.send_alert(
            AlertType.DAILY_LOSS_WARNING,
            AlertLevel.WARNING,
            f"Daily loss at {percent_used:.1f}%: ${current_loss:.2f} / ${limit:.2f} limit",
            {'current_loss': current_loss, 'limit': limit, 'percent_used': percent_used}
        )

    def drawdown_warning(self, current_dd: float, limit: float):
        """Alert for approaching drawdown limit"""
        percent_used = (current_dd / limit) * 100

        self.send_alert(
            AlertType.DRAWDOWN_WARNING,
            AlertLevel.WARNING,
            f"Drawdown at {percent_used:.1f}%: {current_dd:.2f}% / {limit:.2f}% limit",
            {'current_dd': current_dd, 'limit': limit, 'percent_used': percent_used}
        )

    def consecutive_losses(self, count: int, limit: int):
        """Alert for consecutive losses"""
        self.send_alert(
            AlertType.CONSECUTIVE_LOSSES,
            AlertLevel.WARNING,
            f"Consecutive losses: {count} / {limit}",
            {'count': count, 'limit': limit}
        )

    def position_limit_reached(self, current: int, max_positions: int):
        """Alert for position limit reached"""
        self.send_alert(
            AlertType.POSITION_LIMIT,
            AlertLevel.INFO,
            f"Position limit reached: {current} / {max_positions}",
            {'current': current, 'max': max_positions}
        )

    def balance_milestone(self, balance: float, milestone: str):
        """Alert for balance milestone"""
        self.send_alert(
            AlertType.BALANCE_MILESTONE,
            AlertLevel.INFO,
            f"Balance milestone reached: ${balance:.2f} ({milestone})",
            {'balance': balance, 'milestone': milestone}
        )

    def system_error(self, error_msg: str):
        """Alert for system error"""
        self.send_alert(
            AlertType.SYSTEM_ERROR,
            AlertLevel.CRITICAL,
            f"System error: {error_msg}",
            {'error': error_msg}
        )


if __name__ == "__main__":
    # Test script
    import time

    print("Testing Alert System...")

    # Initialize
    alerts = AlertSystem(enable_console=True, enable_file=False)

    print("\n1. Sending test alerts...")

    # Test different alert types
    alerts.position_opened("POS_001", "LONG", 112000, 0.001)
    time.sleep(0.1)

    alerts.position_closed("POS_001", "LONG", 4.50, "TAKE_PROFIT")
    time.sleep(0.1)

    alerts.take_profit_hit("POS_001", 113000, 4.50)
    time.sleep(0.1)

    alerts.stop_loss_hit("POS_002", 111500, -2.00)
    time.sleep(0.1)

    alerts.daily_loss_warning(-4.00, 5.00)
    time.sleep(0.1)

    alerts.consecutive_losses(2, 3)
    time.sleep(0.1)

    alerts.circuit_breaker_triggered("Daily loss limit exceeded")
    time.sleep(0.1)

    print("\n2. Alert Summary")
    summary = alerts.get_alert_summary()
    for key, value in summary.items():
        if key != 'last_alert':
            print(f"  {key}: {value}")

    print("\n3. Get Critical Alerts")
    critical = alerts.get_alerts(level=AlertLevel.CRITICAL)
    print(f"  Found {len(critical)} critical alerts")
    for alert in critical:
        print(f"    - {alert['message']}")

    print("\n4. Get Warning Alerts")
    warnings = alerts.get_alerts(level=AlertLevel.WARNING)
    print(f"  Found {len(warnings)} warning alerts")

    print("\n5. Testing Custom Handler")
    def custom_handler(alert):
        print(f"  CUSTOM HANDLER: Received alert - {alert['message']}")

    alerts.register_handler(AlertType.POSITION_OPENED, custom_handler)
    alerts.position_opened("POS_003", "SHORT", 113000, 0.001)

    print("\n6. Testing Mute/Unmute")
    alerts.mute_alert_type(AlertType.POSITION_OPENED)
    alerts.position_opened("POS_004", "LONG", 112500, 0.001)  # Should not appear
    print("  (Position opened alert should be muted)")

    alerts.unmute_alert_type(AlertType.POSITION_OPENED)
    alerts.position_opened("POS_005", "LONG", 112600, 0.001)  # Should appear

    print("\n7. Recent Alerts (Last 5)")
    recent = alerts.get_alerts(limit=5)
    for alert in recent:
        print(f"  {alert['timestamp'].strftime('%H:%M:%S')} - {alert['message']}")

    print("\n✅ Alert System test complete!")
    print(f"\nTotal alerts sent: {len(alerts.alerts)}")
