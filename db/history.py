"""
Database Health History Module.
Records periodic snapshots of PostgreSQL health metrics and computes trend statistics.
"""

import logging
from datetime import datetime, timedelta
import pandas as pd
from config import DEMO_MODE
from .connection import get_db_cursor
from .queries import QUERY_INSERT_HEALTH_HISTORY, QUERY_SELECT_HEALTH_HISTORY

logger = logging.getLogger("db.history")


def save_health_snapshot(metrics):
    """
    Saves a health check snapshot into the dba_ai.health_history table.
    
    Args:
        metrics (dict): Consolidated metrics from collect_health()
    Returns:
        bool: True if recorded successfully, False otherwise
    """
    if DEMO_MODE:
        logger.info("Demo mode: Simulated health snapshot record.")
        return True

    try:
        with get_db_cursor() as cur:
            cur.execute(
                QUERY_INSERT_HEALTH_HISTORY,
                (
                    metrics.get("database", "dba_ai"),
                    metrics.get("connections", 0),
                    metrics.get("max_connections", 100),
                    metrics.get("database_size_bytes", 0),
                    metrics.get("long_running_queries", 0),
                    metrics.get("blocking_sessions", 0),
                    metrics.get("xid_age", 0),
                    metrics.get("cache_hit_ratio", 99.0),
                    metrics.get("status", "HEALTHY"),
                ),
            )
            logger.info("Successfully recorded health snapshot to dba_ai.health_history")
            return True
    except Exception as exc:
        logger.warning("Could not save health snapshot to database: %s", exc)
        return False


def get_health_history(limit=100):
    """
    Fetches the historical health metrics from PostgreSQL.
    
    Args:
        limit (int): Max number of data points.
    Returns:
        pd.DataFrame: DataFrame containing time-series health metrics.
    """
    if DEMO_MODE:
        return _generate_mock_history_df()

    try:
        with get_db_cursor(dict_cursor=True) as cur:
            cur.execute(QUERY_SELECT_HEALTH_HISTORY, (limit,))
            rows = cur.fetchall()
            if rows and len(rows) > 0:
                df = pd.DataFrame(rows)
                df["database_size_gb"] = df["database_size_bytes"] / (1024 ** 3)
                df["collected_at"] = pd.to_datetime(df["collected_at"])
                return df
    except Exception as exc:
        logger.warning("Failed to fetch historical health records: %s. Using simulated trend.", exc)

    return _generate_mock_history_df()


def get_growth_trend():
    """
    Returns time series trend dataframe formatted specifically for visualization.
    """
    return get_health_history(limit=50)


def _generate_mock_history_df():
    """Generates synthetic 7-day historical database metrics for visualization."""
    now = datetime.now()
    timestamps = [now - timedelta(hours=i * 4) for i in range(42, -1, -1)]
    
    # Simulate gradual DB growth from 420 GB to 452 GB
    base_size_gb = 420.0
    records = []
    
    for i, ts in enumerate(timestamps):
        growth = (i / len(timestamps)) * 32.0 + (i % 3) * 0.4
        curr_size_gb = base_size_gb + growth
        curr_size_bytes = int(curr_size_gb * (1024 ** 3))
        
        # Varying connections between 20 and 55
        conns = 25 + int((i % 7) * 4) + (10 if 9 <= ts.hour <= 17 else 0)
        
        # Spikes in long queries or blocking
        long_q = 2 if i in (38, 39, 40) else (1 if i % 10 == 0 else 0)
        blocking = 1 if i in (39, 40) else 0
        
        records.append({
            "collected_at": ts,
            "database_name": "dba_ai",
            "connections": conns,
            "max_connections": 200,
            "database_size_bytes": curr_size_bytes,
            "database_size_gb": round(curr_size_gb, 2),
            "long_running_queries": long_q,
            "blocking_sessions": blocking,
            "xid_age": 14000000 + i * 5000,
            "cache_hit_ratio": 99.2 - (0.5 if long_q > 0 else 0.0),
            "status": "WARNING" if (blocking or long_q > 1) else "HEALTHY",
        })

    return pd.DataFrame(records)
