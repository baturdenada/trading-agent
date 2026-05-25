"""
State Manager - Persistent data storage using SQLite
Replaces fragile JSON + in-memory approach with reliable database
"""

import sqlite3
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

class StateManager:
    """Manages persistent application state using SQLite"""

    def __init__(self, db_path: Path):
        """Initialize state manager with SQLite database"""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
            self._init_schema()
            logger.info(f"State Manager initialized with database: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize state manager: {e}")
            raise

    def _init_schema(self):
        """Initialize database schema"""
        cursor = self.conn.cursor()

        # Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket INTEGER UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                entry_time DATETIME NOT NULL,
                exit_time DATETIME,
                entry_price REAL NOT NULL,
                exit_price REAL,
                volume REAL NOT NULL,
                profit REAL,
                is_win BOOLEAN,
                strategy TEXT,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_symbol (symbol),
                INDEX idx_entry_time (entry_time),
                INDEX idx_is_win (is_win)
            )
        """)

        # Lessons learned table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                trades_involved TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_category (category),
                INDEX idx_created (created_at)
            )
        """)

        # Performance metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                total_trades INTEGER,
                wins INTEGER,
                losses INTEGER,
                win_rate REAL,
                net_profit REAL,
                avg_win REAL,
                avg_loss REAL,
                max_drawdown REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_date (date)
            )
        """)

        # Application state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                type TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()
        logger.info("Database schema initialized")

    # Trade Management
    def add_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Add or update a trade record"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO trades
                (ticket, symbol, entry_time, exit_time, entry_price, exit_price,
                 volume, profit, is_win, strategy, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_data.get('ticket'),
                trade_data.get('symbol'),
                trade_data.get('entry_time'),
                trade_data.get('exit_time'),
                trade_data.get('entry_price'),
                trade_data.get('exit_price'),
                trade_data.get('volume'),
                trade_data.get('profit'),
                trade_data.get('is_win'),
                trade_data.get('strategy'),
                trade_data.get('notes')
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to add trade: {e}")
            return False

    def get_all_trades(self, limit: Optional[int] = None) -> List[Dict]:
        """Get all trades (O(1) - database query)"""
        try:
            cursor = self.conn.cursor()
            query = "SELECT * FROM trades ORDER BY entry_time DESC"
            if limit:
                query += f" LIMIT {limit}"
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get trades: {e}")
            return []

    def get_trades_by_date(self, start_date: str, end_date: str) -> List[Dict]:
        """Get trades within date range"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM trades
                WHERE DATE(entry_time) BETWEEN ? AND ?
                ORDER BY entry_time DESC
            """, (start_date, end_date))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get trades by date: {e}")
            return []

    def get_recent_trades(self, limit: int = 100) -> List[Dict]:
        """Get N most recent trades (O(log n) with index)"""
        return self.get_all_trades(limit)

    def get_trade_statistics(self, limit: Optional[int] = None) -> Dict:
        """Calculate trading statistics efficiently"""
        try:
            cursor = self.conn.cursor()

            if limit:
                cursor.execute(f"""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN is_win=1 THEN 1 ELSE 0 END) as wins,
                           SUM(CASE WHEN is_win=0 THEN 1 ELSE 0 END) as losses,
                           SUM(profit) as net_profit,
                           AVG(CASE WHEN is_win=1 THEN profit ELSE NULL END) as avg_win,
                           AVG(CASE WHEN is_win=0 THEN profit ELSE NULL END) as avg_loss
                    FROM (SELECT * FROM trades ORDER BY entry_time DESC LIMIT {limit})
                """)
            else:
                cursor.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN is_win=1 THEN 1 ELSE 0 END) as wins,
                           SUM(CASE WHEN is_win=0 THEN 1 ELSE 0 END) as losses,
                           SUM(profit) as net_profit,
                           AVG(CASE WHEN is_win=1 THEN profit ELSE NULL END) as avg_win,
                           AVG(CASE WHEN is_win=0 THEN profit ELSE NULL END) as avg_loss
                    FROM trades
                """)

            row = cursor.fetchone()
            return {
                'total_trades': row['total'] or 0,
                'wins': row['wins'] or 0,
                'losses': row['losses'] or 0,
                'win_rate': (row['wins'] / row['total'] * 100) if row['total'] else 0,
                'net_profit': row['net_profit'] or 0,
                'avg_win': row['avg_win'] or 0,
                'avg_loss': row['avg_loss'] or 0
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    # Lesson Management
    def add_lesson(self, title: str, description: str, category: str = None,
                   trades_involved: List[int] = None) -> bool:
        """Add a lesson learned"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO lessons (title, description, category, trades_involved)
                VALUES (?, ?, ?, ?)
            """, (title, description, category, json.dumps(trades_involved or [])))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to add lesson: {e}")
            return False

    def get_lessons(self, category: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get lessons learned"""
        try:
            cursor = self.conn.cursor()
            if category:
                cursor.execute("""
                    SELECT * FROM lessons
                    WHERE category = ?
                    ORDER BY created_at DESC LIMIT ?
                """, (category, limit))
            else:
                cursor.execute("""
                    SELECT * FROM lessons
                    ORDER BY created_at DESC LIMIT ?
                """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get lessons: {e}")
            return []

    # Metrics Management
    def save_metrics(self, date: str, metrics: Dict) -> bool:
        """Save daily metrics"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO metrics
                (date, total_trades, wins, losses, win_rate, net_profit,
                 avg_win, avg_loss, max_drawdown)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date,
                metrics.get('total_trades'),
                metrics.get('wins'),
                metrics.get('losses'),
                metrics.get('win_rate'),
                metrics.get('net_profit'),
                metrics.get('avg_win'),
                metrics.get('avg_loss'),
                metrics.get('max_drawdown')
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
            return False

    def get_metrics(self, date: str) -> Optional[Dict]:
        """Get metrics for a specific date"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM metrics WHERE date = ?", (date,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return None

    # Application State
    def set_state(self, key: str, value: Any, value_type: str = "json") -> bool:
        """Set application state value"""
        try:
            cursor = self.conn.cursor()
            json_value = json.dumps(value) if value_type == "json" else str(value)
            cursor.execute("""
                INSERT OR REPLACE INTO app_state (key, value, type)
                VALUES (?, ?, ?)
            """, (key, json_value, value_type))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to set state: {e}")
            return False

    def get_state(self, key: str) -> Optional[Any]:
        """Get application state value"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value, type FROM app_state WHERE key = ?", (key,))
            row = cursor.fetchone()
            if not row:
                return None
            value = row['value']
            value_type = row['type']
            return json.loads(value) if value_type == "json" else value
        except Exception as e:
            logger.error(f"Failed to get state: {e}")
            return None

    def close(self):
        """Close database connection"""
        try:
            self.conn.close()
            logger.info("State manager database closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
