"""
Database access and schema management using Python built-in sqlite3.
"""

import sqlite3
from pathlib import Path
from typing import Generator
from contextlib import contextmanager

from app.config import settings


def get_db_path(custom_path: Path | str | None = None) -> Path:
    """Resolve database path, ensuring parent directories exist."""
    if custom_path:
        path = Path(custom_path)
    else:
        path = settings.DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect_db(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Create and return a configured SQLite connection."""
    resolved_path = get_db_path(db_path)
    conn = sqlite3.connect(str(resolved_path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode and foreign key constraints
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def get_db(db_path: Path | str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connection with automatic commit and rollback."""
    conn = connect_db(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | str | None = None) -> None:
    """
    Initialize SQLite database schema and indexes.
    Creates tables if they do not already exist.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()

        # Sales transactions table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sales_transactions (
                transaction_id TEXT PRIMARY KEY,
                order_date_raw TEXT NOT NULL,
                order_date_iso TEXT,
                order_year INTEGER,
                order_month INTEGER,
                year_month TEXT,
                product TEXT,
                category TEXT,
                region TEXT,
                sales_channel TEXT,
                quantity INTEGER,
                unit_price REAL,
                discount_amount REAL DEFAULT 0.0,
                status TEXT NOT NULL,
                gross_revenue REAL DEFAULT 0.0,
                net_revenue REAL DEFAULT 0.0,
                is_valid INTEGER DEFAULT 1,
                data_quality_flag TEXT DEFAULT 'VALID',
                exclusion_reason TEXT,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # Performance indexes for analytical queries
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_txn_is_valid ON sales_transactions(is_valid);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_txn_year_month ON sales_transactions(year_month);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_txn_product ON sales_transactions(product);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_txn_region ON sales_transactions(region);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_txn_date_iso ON sales_transactions(order_date_iso);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_txn_status ON sales_transactions(status);"
        )

        # Import history tracking table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS import_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                total_records INTEGER NOT NULL,
                valid_records INTEGER NOT NULL,
                flagged_records INTEGER NOT NULL,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def reset_db(db_path: Path | str | None = None) -> None:
    """Drop and recreate all tables (useful for rebuilds and testing)."""
    with get_db(db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS sales_transactions;")
        conn.execute("DROP TABLE IF EXISTS import_history;")
    init_db(db_path)
