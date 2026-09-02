"""
PostgreSQL Connection Factory.
Manages secure SSL connections to AWS RDS PostgreSQL with credential resolution.
"""

import logging
from contextlib import contextmanager
try:
    # pyrefly: ignore [missing-import]
    import psycopg
    # pyrefly: ignore [missing-import]
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

from config import (
    RDS_HOST,
    RDS_PORT,
    RDS_DATABASE,
    RDS_USER,
    RDS_PASSWORD,
    RDS_SSLMODE,
    resolve_db_credentials,
)

logger = logging.getLogger("db.connection")


def get_connection_params():
    """Returns current active connection dictionary."""
    creds = resolve_db_credentials()
    return {
        "host": creds["host"],
        "port": creds["port"],
        "dbname": creds["database"],
        "user": creds["user"],
        "password": creds["password"],
        "sslmode": creds["sslmode"],
        "connect_timeout": 10,
    }


def get_connection(autocommit=True, row_factory=None):
    """
    Creates and returns a new psycopg connection to PostgreSQL.
    
    Args:
        autocommit (bool): Whether queries commit automatically.
        row_factory: Optional row factory (e.g. dict_row).
        
    Returns:
        psycopg.Connection: Active database connection.
    """
    if psycopg is None:
        raise RuntimeError("psycopg is not installed. Please install it using: pip install psycopg[binary]")

    params = get_connection_params()
    conn = psycopg.connect(
        **params,
        autocommit=autocommit,
        row_factory=row_factory
    )
    return conn


@contextmanager
def get_db_cursor(dict_cursor=False):
    """
    Context manager for safely acquiring and releasing database connections and cursors.
    """
    if psycopg is None:
        raise RuntimeError("psycopg is not installed. Please install it using: pip install psycopg[binary]")

    row_fac = dict_row if dict_cursor else None
    conn = get_connection(autocommit=True, row_factory=row_fac)
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def check_database_connection():
    """
    Tests database connectivity and returns metadata (version, current db, ping latency).
    """
    if psycopg is None:
        return {
            "connected": False,
            "version": None,
            "database": None,
            "server_time": None,
            "error": "psycopg package not installed. Install via 'pip install psycopg[binary]' or run in demo mode.",
        }

    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT version(), current_database(), now();")
            row = cur.fetchone()
            return {
                "connected": True,
                "version": row[0],
                "database": row[1],
                "server_time": str(row[2]),
                "error": None,
            }
    except Exception as exc:
        logger.error("Database connection failed: %s", exc)
        return {
            "connected": False,
            "version": None,
            "database": None,
            "server_time": None,
            "error": str(exc),
        }

