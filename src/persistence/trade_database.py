"""
Trade Database - SQLite persistence for trading history
Ensures trades are never lost on bot restart
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class TradeDatabase:
    """SQLite database for persisting trade history"""

    def __init__(self, db_path: str = 'data/trades.db'):
        """Initialize database connection and create tables if needed"""
        self.db_path = db_path

        # Create data directory if it doesn't exist
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries

        # Create tables
        self._create_tables()

    def _create_tables(self):
        """Create database tables if they don't exist"""
        cursor = self.conn.cursor()

        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                quantity REAL NOT NULL,
                pnl REAL,
                pnl_percent REAL,
                fees REAL,
                exit_reason TEXT,
                hold_duration REAL,
                closed_at TEXT,
                stop_loss REAL,
                take_profit REAL,
                trading_mode TEXT DEFAULT 'paper',
                signal_data TEXT,
                position_data TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Add trading_mode column to existing tables (migration)
        try:
            cursor.execute("ALTER TABLE trades ADD COLUMN trading_mode TEXT DEFAULT 'paper'")
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Performance snapshots table (for historical tracking)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                balance REAL NOT NULL,
                equity REAL NOT NULL,
                total_pnl REAL NOT NULL,
                total_return_percent REAL NOT NULL,
                peak_balance REAL NOT NULL,
                max_drawdown REAL NOT NULL,
                total_trades INTEGER NOT NULL,
                win_rate REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.conn.commit()

    def save_trade(self, trade: Dict) -> bool:
        """Save a trade to the database"""
        try:
            cursor = self.conn.cursor()

            # Extract data from trade record
            trade_id = trade.get('id') or trade.get('position', {}).get('position_id')
            side = trade.get('side') or trade.get('position', {}).get('side')
            entry_price = trade.get('entry_price') or trade.get('position', {}).get('entry_price')
            exit_price = trade.get('exit_price')
            quantity = trade.get('quantity') or trade.get('position', {}).get('quantity')
            pnl = trade.get('pnl')
            pnl_percent = trade.get('pnl_percent')
            exit_reason = trade.get('exit_reason')
            hold_duration = trade.get('hold_duration')
            closed_at = trade.get('closed_at')
            stop_loss = trade.get('stop_loss') or trade.get('position', {}).get('stop_loss')
            take_profit = trade.get('take_profit') or trade.get('position', {}).get('take_profit')
            trading_mode = trade.get('trading_mode', 'paper')  # Default to paper for safety

            # Serialize complex objects
            signal_data = json.dumps(trade.get('signal', {})) if 'signal' in trade else None
            position_data = json.dumps(trade.get('position', {})) if 'position' in trade else None

            # Use timestamp from trade or current time
            timestamp = trade.get('timestamp')
            if timestamp:
                if isinstance(timestamp, datetime):
                    timestamp = timestamp.isoformat()
            else:
                timestamp = datetime.now().isoformat()

            # Format closed_at
            if closed_at and isinstance(closed_at, datetime):
                closed_at = closed_at.isoformat()

            cursor.execute('''
                INSERT OR REPLACE INTO trades (
                    id, timestamp, side, entry_price, exit_price, quantity,
                    pnl, pnl_percent, exit_reason, hold_duration, closed_at,
                    stop_loss, take_profit, trading_mode, signal_data, position_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_id, timestamp, side, entry_price, exit_price, quantity,
                pnl, pnl_percent, exit_reason, hold_duration, closed_at,
                stop_loss, take_profit, trading_mode, signal_data, position_data
            ))

            self.conn.commit()
            return True

        except Exception as e:
            print(f"Error saving trade to database: {e}")
            return False

    def get_all_trades(self, limit: Optional[int] = None, trading_mode: Optional[str] = None) -> List[Dict]:
        """Get all trades from database, ordered by timestamp (newest first)

        Args:
            limit: Maximum number of trades to return
            trading_mode: Filter by 'paper' or 'live' mode (None = all trades)
        """
        cursor = self.conn.cursor()

        # Build query based on filters
        query = 'SELECT * FROM trades WHERE closed_at IS NOT NULL'
        params = []

        if trading_mode:
            query += ' AND trading_mode = ?'
            params.append(trading_mode)

        query += ' ORDER BY closed_at DESC'

        if limit:
            query += ' LIMIT ?'
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Convert to list of dictionaries
        trades = []
        for row in rows:
            trade = dict(row)

            # Parse JSON fields
            if trade.get('signal_data'):
                try:
                    trade['signal'] = json.loads(trade['signal_data'])
                except:
                    pass

            if trade.get('position_data'):
                try:
                    trade['position'] = json.loads(trade['position_data'])
                except:
                    pass

            # Remove serialized fields
            trade.pop('signal_data', None)
            trade.pop('position_data', None)
            trade.pop('created_at', None)

            trades.append(trade)

        return trades

    def get_trades_by_date(self, start_date: str, end_date: Optional[str] = None) -> List[Dict]:
        """Get trades within a date range"""
        cursor = self.conn.cursor()

        if end_date:
            cursor.execute('''
                SELECT * FROM trades
                WHERE closed_at >= ? AND closed_at <= ?
                ORDER BY closed_at DESC
            ''', (start_date, end_date))
        else:
            cursor.execute('''
                SELECT * FROM trades
                WHERE closed_at >= ?
                ORDER BY closed_at DESC
            ''', (start_date,))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_trade_count(self) -> int:
        """Get total number of closed trades"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM trades WHERE closed_at IS NOT NULL')
        return cursor.fetchone()[0]

    def get_performance_stats(self) -> Dict:
        """Calculate performance statistics from database"""
        cursor = self.conn.cursor()

        cursor.execute('''
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl,
                MAX(pnl) as best_trade,
                MIN(pnl) as worst_trade
            FROM trades
            WHERE closed_at IS NOT NULL
        ''')

        row = cursor.fetchone()

        total_trades = row['total_trades'] or 0
        wins = row['wins'] or 0
        losses = row['losses'] or 0

        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': (wins / total_trades * 100) if total_trades > 0 else 0.0,
            'total_pnl': row['total_pnl'] or 0.0,
            'avg_pnl': row['avg_pnl'] or 0.0,
            'best_trade': row['best_trade'] or 0.0,
            'worst_trade': row['worst_trade'] or 0.0
        }

    def save_performance_snapshot(self, snapshot: Dict) -> bool:
        """Save a performance snapshot"""
        try:
            cursor = self.conn.cursor()

            cursor.execute('''
                INSERT INTO performance_snapshots (
                    timestamp, balance, equity, total_pnl, total_return_percent,
                    peak_balance, max_drawdown, total_trades, win_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                snapshot.get('timestamp', datetime.now().isoformat()),
                snapshot.get('balance', 0.0),
                snapshot.get('equity', 0.0),
                snapshot.get('total_pnl', 0.0),
                snapshot.get('total_return_percent', 0.0),
                snapshot.get('peak_balance', 0.0),
                snapshot.get('max_drawdown', 0.0),
                snapshot.get('total_trades', 0),
                snapshot.get('win_rate', 0.0)
            ))

            self.conn.commit()
            return True

        except Exception as e:
            print(f"Error saving performance snapshot: {e}")
            return False

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def __del__(self):
        """Cleanup on deletion"""
        self.close()
