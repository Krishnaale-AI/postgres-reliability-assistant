"""
PostgreSQL Vacuum & Dead Tuples Monitoring.
Monitors autovacuum daemon activity, dead tuple buildup, and vacuum candidate tables.
"""

import logging
from db.connection import get_db_cursor
from config import DEMO_MODE

logger = logging.getLogger("monitoring.vacuum")

QUERY_AUTOVACUUM_PROGRESS = """
SELECT
    p.pid,
    c.relname AS table_name,
    p.phase,
    p.heap_blks_total,
    p.heap_blks_scanned,
    p.heap_blks_vacuumed,
    p.num_dead_tuples
FROM pg_stat_progress_vacuum p
JOIN pg_class c ON c.oid = p.relid;
"""

QUERY_VACUUM_CANDIDATES = """
SELECT
    schemaname,
    relname AS table_name,
    n_live_tup AS live_tuples,
    n_dead_tup AS dead_tuples,
    ROUND((100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0))::numeric, 2) AS dead_pct,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY dead_pct DESC
LIMIT 15;
"""


def get_autovacuum_activity():
    """Fetches real-time progress of currently running vacuum workers."""
    if DEMO_MODE:
        return []

    try:
        with get_db_cursor(dict_cursor=True) as cur:
            cur.execute(QUERY_AUTOVACUUM_PROGRESS)
            return cur.fetchall()
    except Exception as exc:
        logger.debug("Could not fetch autovacuum progress: %s", exc)
        return []


def check_vacuum_needed():
    """Returns tables where dead tuple accumulation exceeds recommended thresholds."""
    if DEMO_MODE:
        return [
            {"schemaname": "public", "table_name": "orders", "live_tuples": 45000000, "dead_tuples": 1850000, "dead_pct": 3.95, "last_autovacuum": "2026-09-01 18:20:00"},
            {"schemaname": "public", "table_name": "audit_logs", "live_tuples": 28000000, "dead_tuples": 950000, "dead_pct": 3.28, "last_autovacuum": "2026-09-01 17:45:00"},
        ]

    try:
        with get_db_cursor(dict_cursor=True) as cur:
            cur.execute(QUERY_VACUUM_CANDIDATES)
            return cur.fetchall()
    except Exception as exc:
        logger.warning("Error fetching vacuum candidates: %s", exc)
        return []
