#!/usr/bin/env python3
"""
Database Manager for ADX Strategy v2.0
Handles all MariaDB operations for signals, trades, and performance tracking
"""

import mysql.connector
from mysql.connector import Error, pooling
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    MariaDB Database Manager

    Features:
    - Connection pooling for performance
    - Signal storage and retrieval
    - Trade tracking
    - Performance metrics
    - System logging
    """

    def __init__(self, host: str, port: int, database: str,
                 user: str, password: str, pool_size: int = 5):
        """
        Initialize database manager with connection pooling

        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
            pool_size: Connection pool size
        """
        self.config = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password,
            'autocommit': True
        }

        # Create connection pool
        try:
            self.pool = pooling.MySQLConnectionPool(
                pool_name="adx_pool",
                pool_size=pool_size,
                **self.config
            )
            logger.info(f"Database pool created: {database}@{host} (size: {pool_size})")
        except Error as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise

    def get_connection(self):
        """Get connection from pool"""
        return self.pool.get_connection()

    def execute_query(self, query: str, params: Tuple = None,
                     fetch_one: bool = False, fetch_all: bool = False) -> Optional[any]:
        """
        Execute SQL query

        Args:
            query: SQL query
            params: Query parameters
            fetch_one: Fetch single row
            fetch_all: Fetch all rows

        Returns:
            Query result or None
        """
        connection = None
        cursor = None
        try:
            connection = self.get_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(query, params or ())

            if fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            else:
                connection.commit()
                return cursor.lastrowid

        except Error as e:
            logger.error(f"Query error: {e}")
            logger.error(f"Query: {query}")
            if connection:
                connection.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    # ==================== Signal Operations ====================

    def insert_signal(self, signal_data: Dict) -> int:
        """
        Insert new ADX signal

        Args:
            signal_data: Signal dictionary with ADX indicators

        Returns:
            Signal ID
        """
        query = """
            INSERT INTO adx_signals (
                timestamp, symbol, timeframe,
                open_price, high_price, low_price, close_price, volume,
                adx_value, plus_di, minus_di, adx_slope, di_spread, trend_strength,
                signal_type, entry_condition, confidence,
                stop_loss_price, take_profit_price, risk_reward_ratio, position_size
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s
            )
        """

        params = (
            signal_data.get('timestamp') or datetime.now(),
            signal_data.get('symbol', 'BTC-USDT'),
            signal_data.get('timeframe', '5m'),
            signal_data.get('open'),
            signal_data.get('high'),
            signal_data.get('low'),
            signal_data.get('close'),
            signal_data.get('volume'),
            signal_data.get('adx'),
            signal_data.get('plus_di'),
            signal_data.get('minus_di'),
            signal_data.get('adx_slope'),
            signal_data.get('di_spread'),
            signal_data.get('trend_strength', 'NONE'),
            signal_data.get('signal_type', 'HOLD'),
            signal_data.get('entry_condition'),
            signal_data.get('confidence', 0.5),
            signal_data.get('stop_loss_price'),
            signal_data.get('take_profit_price'),
            signal_data.get('risk_reward_ratio'),
            signal_data.get('position_size')
        )

        signal_id = self.execute_query(query, params)
        logger.info(f"Signal inserted: ID={signal_id}, Type={signal_data.get('signal_type')}")
        return signal_id

    def get_pending_signals(self, limit: int = 10) -> List[Dict]:
        """
        Get pending signals

        Args:
            limit: Maximum number of signals

        Returns:
            List of pending signals
        """
        query = """
            SELECT * FROM adx_signals
            WHERE outcome = 'PENDING'
            ORDER BY timestamp DESC
            LIMIT %s
        """

        return self.execute_query(query, (limit,), fetch_all=True)

    def update_signal_outcome(self, signal_id: int, outcome: str,
                             exit_price: float, pnl_percent: float,
                             pnl_amount: float):
        """
        Update signal outcome

        Args:
            signal_id: Signal ID
            outcome: Outcome (WIN, LOSS, TIMEOUT, CANCELLED)
            exit_price: Exit price
            pnl_percent: P&L percentage
            pnl_amount: P&L amount in USDT
        """
        query = """
            UPDATE adx_signals
            SET outcome = %s,
                exit_price = %s,
                exit_timestamp = %s,
                pnl_percent = %s,
                pnl_amount = %s
            WHERE id = %s
        """

        params = (outcome, exit_price, datetime.now(), pnl_percent, pnl_amount, signal_id)
        self.execute_query(query, params)
        logger.info(f"Signal {signal_id} updated: {outcome}, PNL: {pnl_percent:.2f}%")

    # ==================== Trade Operations ====================

    def insert_trade(self, trade_data: Dict) -> int:
        """
        Insert new trade

        Args:
            trade_data: Trade dictionary

        Returns:
            Trade ID
        """
        query = """
            INSERT INTO adx_trades (
                signal_id, timestamp, symbol,
                side, order_type, quantity, entry_price, leverage,
                stop_loss, take_profit, risk_reward_ratio, risk_amount,
                order_id, status
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s
            )
        """

        params = (
            trade_data.get('signal_id'),
            trade_data.get('timestamp') or datetime.now(),
            trade_data.get('symbol', 'BTC-USDT'),
            trade_data.get('side'),
            trade_data.get('order_type', 'MARKET'),
            trade_data.get('quantity'),
            trade_data.get('entry_price'),
            trade_data.get('leverage', 5),
            trade_data.get('stop_loss'),
            trade_data.get('take_profit'),
            trade_data.get('risk_reward_ratio', 2.0),
            trade_data.get('risk_amount'),
            trade_data.get('order_id'),
            trade_data.get('status', 'PENDING')
        )

        trade_id = self.execute_query(query, params)
        logger.info(f"Trade inserted: ID={trade_id}, Side={trade_data.get('side')}")
        return trade_id

    def update_trade_status(self, trade_id: int, status: str,
                           filled_quantity: Optional[float] = None,
                           avg_fill_price: Optional[float] = None):
        """
        Update trade status

        Args:
            trade_id: Trade ID
            status: New status
            filled_quantity: Filled quantity
            avg_fill_price: Average fill price
        """
        query = """
            UPDATE adx_trades
            SET status = %s,
                filled_quantity = COALESCE(%s, filled_quantity),
                avg_fill_price = COALESCE(%s, avg_fill_price)
            WHERE id = %s
        """

        params = (status, filled_quantity, avg_fill_price, trade_id)
        self.execute_query(query, params)
        logger.info(f"Trade {trade_id} status updated: {status}")

    def close_trade(self, trade_id: int, exit_price: float,
                   exit_reason: str, realized_pnl: float):
        """
        Close trade and record results

        Args:
            trade_id: Trade ID
            exit_price: Exit price
            exit_reason: Reason for exit
            realized_pnl: Realized P&L
        """
        query = """
            UPDATE adx_trades
            SET status = 'CLOSED',
                exit_timestamp = %s,
                exit_price = %s,
                exit_reason = %s,
                realized_pnl = %s,
                realized_pnl_percent = ((%s - entry_price) / entry_price * 100 *
                    CASE WHEN side = 'LONG' THEN 1 ELSE -1 END),
                hold_duration_minutes = TIMESTAMPDIFF(MINUTE, timestamp, %s)
            WHERE id = %s
        """

        now = datetime.now()
        params = (now, exit_price, exit_reason, realized_pnl, exit_price, now, trade_id)
        self.execute_query(query, params)
        logger.info(f"Trade {trade_id} closed: {exit_reason}, PNL: ${realized_pnl:.2f}")

    def get_open_trades(self) -> List[Dict]:
        """Get all open trades"""
        query = """
            SELECT * FROM adx_trades
            WHERE status IN ('OPEN', 'FILLED')
            ORDER BY timestamp DESC
        """

        return self.execute_query(query, fetch_all=True)

    # ==================== Performance Operations ====================

    def calculate_performance(self, period: str = '24h') -> Dict:
        """
        Calculate performance metrics

        Args:
            period: Time period ('1h', '24h', '7d', '30d', 'all')

        Returns:
            Performance metrics dictionary
        """
        # Determine time filter
        if period == 'all':
            time_filter = ""
        else:
            intervals = {'1h': 'HOUR', '24h': 'DAY', '7d': 'WEEK', '30d': 'MONTH'}
            interval = intervals.get(period, 'DAY')
            time_filter = f"AND timestamp >= DATE_SUB(NOW(), INTERVAL 1 {interval})"

        query = f"""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome = 'TIMEOUT' THEN 1 ELSE 0 END) as timeouts,
                AVG(CASE WHEN outcome IN ('WIN', 'LOSS') THEN adx_value END) as avg_adx,
                AVG(confidence) as avg_confidence,
                SUM(pnl_amount) as total_pnl,
                AVG(CASE WHEN outcome = 'WIN' THEN pnl_amount END) as avg_win,
                AVG(CASE WHEN outcome = 'LOSS' THEN pnl_amount END) as avg_loss,
                MAX(pnl_amount) as largest_win,
                MIN(pnl_amount) as largest_loss
            FROM adx_signals
            WHERE outcome IN ('WIN', 'LOSS', 'TIMEOUT')
            {time_filter}
        """

        result = self.execute_query(query, fetch_one=True) or {}

        total = result.get('total_trades', 0) or 0
        wins = result.get('wins', 0) or 0
        losses = result.get('losses', 0) or 0

        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

        return {
            'period': period,
            'total_trades': total,
            'wins': wins,
            'losses': losses,
            'timeouts': result.get('timeouts', 0),
            'win_rate': round(win_rate, 2),
            'avg_adx': round(result.get('avg_adx', 0) or 0, 2),
            'avg_confidence': round(result.get('avg_confidence', 0) or 0, 4),
            'total_pnl': round(result.get('total_pnl', 0) or 0, 2),
            'avg_win': round(result.get('avg_win', 0) or 0, 2),
            'avg_loss': round(result.get('avg_loss', 0) or 0, 2),
            'largest_win': round(result.get('largest_win', 0) or 0, 2),
            'largest_loss': round(result.get('largest_loss', 0) or 0, 2)
        }

    def save_performance_snapshot(self, period: str, metrics: Dict):
        """
        Save performance snapshot to database

        Args:
            period: Time period
            metrics: Performance metrics
        """
        query = """
            INSERT INTO adx_performance (
                period, total_trades, winning_trades, losing_trades, timeout_trades,
                win_rate, total_pnl, avg_win, avg_loss, largest_win, largest_loss,
                avg_adx, avg_confidence
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s
            )
        """

        params = (
            period,
            metrics.get('total_trades', 0),
            metrics.get('wins', 0),
            metrics.get('losses', 0),
            metrics.get('timeouts', 0),
            metrics.get('win_rate', 0) / 100,  # Convert to decimal
            metrics.get('total_pnl', 0),
            metrics.get('avg_win', 0),
            metrics.get('avg_loss', 0),
            metrics.get('largest_win', 0),
            metrics.get('largest_loss', 0),
            metrics.get('avg_adx', 0),
            metrics.get('avg_confidence', 0)
        )

        self.execute_query(query, params)
        logger.info(f"Performance snapshot saved: {period}")

    # ==================== Parameter Operations ====================

    def get_parameter(self, param_name: str) -> Optional[str]:
        """Get strategy parameter value"""
        query = "SELECT parameter_value FROM adx_strategy_params WHERE parameter_name = %s"
        result = self.execute_query(query, (param_name,), fetch_one=True)
        return result['parameter_value'] if result else None

    def get_all_parameters(self, category: Optional[str] = None) -> Dict:
        """
        Get all strategy parameters

        Args:
            category: Filter by category (optional)

        Returns:
            Dictionary of parameters
        """
        if category:
            query = "SELECT parameter_name, parameter_value FROM adx_strategy_params WHERE category = %s"
            results = self.execute_query(query, (category,), fetch_all=True)
        else:
            query = "SELECT parameter_name, parameter_value FROM adx_strategy_params"
            results = self.execute_query(query, fetch_all=True)

        return {r['parameter_name']: r['parameter_value'] for r in results or []}

    def update_parameter(self, param_name: str, param_value: str):
        """Update strategy parameter"""
        query = """
            UPDATE adx_strategy_params
            SET parameter_value = %s
            WHERE parameter_name = %s
        """

        self.execute_query(query, (param_value, param_name))
        logger.info(f"Parameter updated: {param_name} = {param_value}")

    # ==================== System Logging ====================

    def log_system_event(self, level: str, component: str, message: str, details: Dict = None):
        """
        Log system event

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            component: Component name
            message: Log message
            details: Additional details as JSON
        """
        query = """
            INSERT INTO adx_system_logs (log_level, component, message, details)
            VALUES (%s, %s, %s, %s)
        """

        params = (level, component, message, json.dumps(details) if details else None)
        self.execute_query(query, params)


if __name__ == "__main__":
    # Test script
    from dotenv import load_dotenv
    import os

    load_dotenv('config/.env')

    print("Testing Database Manager...")

    # Initialize
    db = DatabaseManager(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 3306)),
        database=os.getenv('DB_NAME', 'bitcoin_trading'),
        user=os.getenv('DB_USER', 'trader'),
        password=os.getenv('DB_PASSWORD', 'SecureTrader2025!@#')
    )

    # Test 1: Get parameters
    print("\n1. Testing parameter retrieval...")
    params = db.get_all_parameters('ADX')
    print(f"✅ ADX Parameters: {params}")

    # Test 2: Calculate performance
    print("\n2. Testing performance calculation...")
    perf = db.calculate_performance('all')
    print(f"✅ Performance: {perf}")

    # Test 3: Log system event
    print("\n3. Testing system logging...")
    db.log_system_event('INFO', 'TEST', 'Database manager test complete')
    print("✅ System event logged")

    print("\n✅ Database Manager test complete!")
