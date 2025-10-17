#!/usr/bin/env python3
"""
System Health Monitor for ADX Strategy v2.0
Monitors system components and overall health
"""

import sys
import os
sys.path.insert(0, '/var/www/dev/trading/adx_strategy_v2')

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ComponentStatus:
    """Status of a system component"""
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


class SystemMonitor:
    """
    System Health Monitoring

    Features:
    - Component health checks
    - Performance monitoring
    - Error tracking
    - Uptime tracking
    - Resource monitoring
    """

    def __init__(self,
                 paper_trader=None,
                 position_manager=None,
                 order_executor=None,
                 risk_manager=None,
                 api_client=None,
                 db_manager=None):
        """
        Initialize system monitor

        Args:
            paper_trader: PaperTrader instance
            position_manager: PositionManager instance
            order_executor: OrderExecutor instance
            risk_manager: RiskManager instance
            api_client: BingX API client instance
            db_manager: Database manager instance
        """
        self.trader = paper_trader
        self.position_mgr = position_manager
        self.executor = order_executor
        self.risk_mgr = risk_manager
        self.api = api_client
        self.db = db_manager

        # Monitoring data
        self.start_time = datetime.now()
        self.last_check = None
        self.check_count = 0

        # Component statuses
        self.component_status = {}
        self.component_errors = {}
        self.component_last_check = {}

        # Performance metrics
        self.operation_counts = {}
        self.operation_errors = {}
        self.response_times = {}

        logger.info("System Monitor initialized")

    def check_health(self) -> Dict:
        """
        Perform comprehensive system health check

        Returns:
            Health status dictionary
        """
        self.last_check = datetime.now()
        self.check_count += 1

        health = {
            'timestamp': self.last_check,
            'overall_status': ComponentStatus.ONLINE,
            'components': {},
            'uptime_seconds': self._get_uptime(),
            'checks_performed': self.check_count
        }

        # Check each component
        components = [
            ('paper_trader', self.trader),
            ('position_manager', self.position_mgr),
            ('order_executor', self.executor),
            ('risk_manager', self.risk_mgr),
            ('api_client', self.api),
            ('database', self.db)
        ]

        for name, component in components:
            status = self._check_component(name, component)
            health['components'][name] = status

            # Update overall status
            if status['status'] == ComponentStatus.ERROR:
                health['overall_status'] = ComponentStatus.ERROR
            elif status['status'] == ComponentStatus.DEGRADED and health['overall_status'] != ComponentStatus.ERROR:
                health['overall_status'] = ComponentStatus.DEGRADED

        return health

    def _check_component(self, name: str, component) -> Dict:
        """Check individual component health"""
        if component is None:
            return {
                'status': ComponentStatus.OFFLINE,
                'message': 'Component not initialized',
                'last_check': datetime.now()
            }

        try:
            # Component-specific health checks
            if name == 'paper_trader':
                return self._check_paper_trader()
            elif name == 'position_manager':
                return self._check_position_manager()
            elif name == 'order_executor':
                return self._check_order_executor()
            elif name == 'risk_manager':
                return self._check_risk_manager()
            elif name == 'api_client':
                return self._check_api_client()
            elif name == 'database':
                return self._check_database()
            else:
                return {
                    'status': ComponentStatus.ONLINE,
                    'message': 'OK',
                    'last_check': datetime.now()
                }

        except Exception as e:
            logger.error(f"Health check failed for {name}: {e}")
            self.component_errors[name] = str(e)
            return {
                'status': ComponentStatus.ERROR,
                'message': str(e),
                'last_check': datetime.now()
            }

    def _check_paper_trader(self) -> Dict:
        """Check paper trader health"""
        if not self.trader:
            return {'status': ComponentStatus.OFFLINE, 'message': 'Not initialized'}

        try:
            balance = self.trader.balance
            equity = self.trader.get_account_status()['equity']

            # Check for negative balance (should never happen)
            if balance < 0:
                return {
                    'status': ComponentStatus.ERROR,
                    'message': f'Negative balance: ${balance:.2f}',
                    'last_check': datetime.now()
                }

            # Check for zero balance (problematic)
            if balance == 0:
                return {
                    'status': ComponentStatus.DEGRADED,
                    'message': 'Zero balance',
                    'last_check': datetime.now()
                }

            return {
                'status': ComponentStatus.ONLINE,
                'message': f'Balance: ${balance:.2f}, Equity: ${equity:.2f}',
                'last_check': datetime.now()
            }

        except Exception as e:
            return {
                'status': ComponentStatus.ERROR,
                'message': str(e),
                'last_check': datetime.now()
            }

    def _check_position_manager(self) -> Dict:
        """Check position manager health"""
        if not self.position_mgr:
            return {'status': ComponentStatus.OFFLINE, 'message': 'Not initialized'}

        try:
            open_pos = len(self.position_mgr.get_open_positions())
            total_pos = self.position_mgr.total_positions

            return {
                'status': ComponentStatus.ONLINE,
                'message': f'{open_pos} open positions, {total_pos} total',
                'last_check': datetime.now()
            }

        except Exception as e:
            return {
                'status': ComponentStatus.ERROR,
                'message': str(e),
                'last_check': datetime.now()
            }

    def _check_order_executor(self) -> Dict:
        """Check order executor health"""
        if not self.executor:
            return {'status': ComponentStatus.OFFLINE, 'message': 'Not initialized'}

        try:
            stats = self.executor.get_execution_stats()
            success_rate = stats['success_rate']

            # Check for low success rate
            if success_rate < 90 and stats['total_orders'] > 5:
                return {
                    'status': ComponentStatus.DEGRADED,
                    'message': f'Low success rate: {success_rate:.1f}%',
                    'last_check': datetime.now()
                }

            return {
                'status': ComponentStatus.ONLINE,
                'message': f"{stats['total_orders']} orders, {success_rate:.1f}% success",
                'last_check': datetime.now()
            }

        except Exception as e:
            return {
                'status': ComponentStatus.ERROR,
                'message': str(e),
                'last_check': datetime.now()
            }

    def _check_risk_manager(self) -> Dict:
        """Check risk manager health"""
        if not self.risk_mgr:
            return {'status': ComponentStatus.OFFLINE, 'message': 'Not initialized'}

        try:
            status = self.risk_mgr.get_risk_status()

            # Check circuit breaker
            if status['circuit_breaker_active']:
                return {
                    'status': ComponentStatus.DEGRADED,
                    'message': f"Circuit breaker: {status['circuit_breaker_reason']}",
                    'last_check': datetime.now()
                }

            return {
                'status': ComponentStatus.ONLINE,
                'message': f"Daily loss: {status['daily_loss_percent']:.2f}%, Positions: {status['open_positions']}/{status['max_positions']}",
                'last_check': datetime.now()
            }

        except Exception as e:
            return {
                'status': ComponentStatus.ERROR,
                'message': str(e),
                'last_check': datetime.now()
            }

    def _check_api_client(self) -> Dict:
        """Check API client health"""
        if not self.api:
            return {'status': ComponentStatus.OFFLINE, 'message': 'Not initialized'}

        try:
            # In real implementation, would ping API
            # For now, just check if object exists
            return {
                'status': ComponentStatus.ONLINE,
                'message': 'API client ready',
                'last_check': datetime.now()
            }

        except Exception as e:
            return {
                'status': ComponentStatus.ERROR,
                'message': str(e),
                'last_check': datetime.now()
            }

    def _check_database(self) -> Dict:
        """Check database health"""
        if not self.db:
            return {'status': ComponentStatus.OFFLINE, 'message': 'Not initialized'}

        try:
            # In real implementation, would test DB connection
            return {
                'status': ComponentStatus.ONLINE,
                'message': 'Database connected',
                'last_check': datetime.now()
            }

        except Exception as e:
            return {
                'status': ComponentStatus.ERROR,
                'message': str(e),
                'last_check': datetime.now()
            }

    def _get_uptime(self) -> float:
        """Get system uptime in seconds"""
        return (datetime.now() - self.start_time).total_seconds()

    def get_uptime_formatted(self) -> str:
        """Get formatted uptime string"""
        uptime = self._get_uptime()
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    def record_operation(self, operation: str, success: bool = True, response_time: float = None):
        """
        Record operation for monitoring

        Args:
            operation: Operation name
            success: Whether operation succeeded
            response_time: Operation duration in seconds
        """
        # Count operations
        if operation not in self.operation_counts:
            self.operation_counts[operation] = 0
            self.operation_errors[operation] = 0
            self.response_times[operation] = []

        self.operation_counts[operation] += 1

        if not success:
            self.operation_errors[operation] += 1

        if response_time is not None:
            self.response_times[operation].append(response_time)

    def get_operation_stats(self, operation: Optional[str] = None) -> Dict:
        """Get statistics for operations"""
        if operation:
            # Stats for specific operation
            if operation not in self.operation_counts:
                return {}

            count = self.operation_counts[operation]
            errors = self.operation_errors[operation]
            times = self.response_times[operation]

            avg_time = sum(times) / len(times) if times else 0

            return {
                'operation': operation,
                'count': count,
                'errors': errors,
                'success_rate': ((count - errors) / count * 100) if count > 0 else 0,
                'avg_response_time': round(avg_time, 3)
            }
        else:
            # Stats for all operations
            stats = {}
            for op in self.operation_counts.keys():
                stats[op] = self.get_operation_stats(op)
            return stats

    def get_system_status_summary(self) -> str:
        """Generate human-readable system status summary"""
        health = self.check_health()

        status_emoji = {
            ComponentStatus.ONLINE: '✅',
            ComponentStatus.OFFLINE: '⚫',
            ComponentStatus.DEGRADED: '⚠️ ',
            ComponentStatus.ERROR: '🚨'
        }

        summary = f"""
{'='*80}
{'SYSTEM STATUS':^80}
{'='*80}
Uptime:           {self.get_uptime_formatted()}
Last Check:       {health['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}
Checks Performed: {health['checks_performed']}
Overall Status:   {status_emoji.get(health['overall_status'], '?')} {health['overall_status']}

{'='*80}
COMPONENT HEALTH
{'='*80}
"""

        for name, status in health['components'].items():
            emoji = status_emoji.get(status['status'], '?')
            summary += f"{emoji} {name.replace('_', ' ').title():<20} {status['status']:<10} {status['message']}\n"

        summary += f"\n{'='*80}\n"

        return summary

    def get_performance_summary(self) -> str:
        """Generate performance statistics summary"""
        stats = self.get_operation_stats()

        if not stats:
            return "No operation data available"

        summary = f"""
{'='*80}
{'PERFORMANCE METRICS':^80}
{'='*80}
"""

        for op, data in stats.items():
            summary += f"\n{op.replace('_', ' ').title()}:\n"
            summary += f"  Count:        {data['count']}\n"
            summary += f"  Errors:       {data['errors']}\n"
            summary += f"  Success Rate: {data['success_rate']:.1f}%\n"
            summary += f"  Avg Time:     {data['avg_response_time']:.3f}s\n"

        summary += f"\n{'='*80}\n"

        return summary


if __name__ == "__main__":
    # Test script
    from src.execution.paper_trader import PaperTrader
    from src.execution.position_manager import PositionManager
    from src.execution.order_executor import OrderExecutor
    from src.risk.risk_manager import RiskManager

    print("Testing System Monitor...")

    # Initialize components
    executor = OrderExecutor(enable_live_trading=False)
    position_mgr = PositionManager(order_executor=executor)
    risk_mgr = RiskManager(initial_capital=100.0)
    trader = PaperTrader(
        initial_balance=100.0,
        leverage=5,
        order_executor=executor,
        position_manager=position_mgr,
        risk_manager=risk_mgr
    )

    # Initialize monitor
    monitor = SystemMonitor(
        paper_trader=trader,
        position_manager=position_mgr,
        order_executor=executor,
        risk_manager=risk_mgr
    )

    print("\n1. Initial Health Check")
    print(monitor.get_system_status_summary())

    print("\n2. Recording Operations")
    monitor.record_operation('signal_generation', success=True, response_time=0.015)
    monitor.record_operation('signal_generation', success=True, response_time=0.012)
    monitor.record_operation('order_execution', success=True, response_time=0.050)
    monitor.record_operation('order_execution', success=False, response_time=0.100)
    monitor.record_operation('risk_check', success=True, response_time=0.001)

    print("\n3. Operation Stats")
    stats = monitor.get_operation_stats()
    for op, data in stats.items():
        print(f"  {op}: {data['count']} ops, {data['success_rate']:.1f}% success, {data['avg_response_time']:.3f}s avg")

    print("\n4. Performance Summary")
    print(monitor.get_performance_summary())

    print("\n5. Uptime")
    print(f"  System uptime: {monitor.get_uptime_formatted()}")

    print("\n6. Final Health Check")
    health = monitor.check_health()
    print(f"  Overall Status: {health['overall_status']}")
    print(f"  Components Online: {sum(1 for c in health['components'].values() if c['status'] == ComponentStatus.ONLINE)}/{len(health['components'])}")

    print("\n✅ System Monitor test complete!")
