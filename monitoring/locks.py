"""
Lock & Blocking Session Monitoring Module.
Detects lock contention, dependency trees, and waiting queries.
"""

import logging
from db.connection import get_db_cursor
from config import DEMO_MODE

logger = logging.getLogger("monitoring.locks")

QUERY_LOCK_TREE = """
WITH RECURSIVE lock_tree AS (
    SELECT
        pid AS root_pid,
        pid AS blocking_pid,
        pg_blocking_pids(pid) AS blocked_by,
        1 AS level
    FROM pg_stat_activity
    WHERE cardinality(pg_blocking_pids(pid)) = 0
      AND pid IN (SELECT unnest(pg_blocking_pids(pid)) FROM pg_stat_activity)
    UNION ALL
    SELECT
        lt.root_pid,
        a.pid AS blocking_pid,
        pg_blocking_pids(a.pid) AS blocked_by,
        lt.level + 1
    FROM pg_stat_activity a
    JOIN lock_tree lt ON lt.blocking_pid = ANY(pg_blocking_pids(a.pid))
)
SELECT DISTINCT
    a.pid,
    a.usename,
    a.client_addr,
    a.state,
    ROUND(EXTRACT(EPOCH FROM (now() - a.query_start))::numeric, 1) AS duration_seconds,
    a.wait_event_type,
    a.wait_event,
    pg_blocking_pids(a.pid) AS blocked_by_pids,
    LEFT(a.query, 250) AS query
FROM pg_stat_activity a
WHERE cardinality(pg_blocking_pids(a.pid)) > 0
   OR a.pid IN (SELECT unnest(pg_blocking_pids(pid)) FROM pg_stat_activity)
ORDER BY duration_seconds DESC;
"""

QUERY_ACTIVE_LOCKS = """
SELECT
    l.pid,
    d.datname,
    l.locktype,
    l.mode,
    l.granted,
    c.relname AS relation_name
FROM pg_locks l
LEFT JOIN pg_database d ON d.oid = l.database
LEFT JOIN pg_class c ON c.oid = l.relation
WHERE l.pid <> pg_backend_pid()
ORDER BY l.granted ASC, l.pid
LIMIT 25;
"""


def analyze_blocking_tree():
    """
    Returns active lock blocking relationships and queries involved.
    """
    if DEMO_MODE:
        return [
            {
                "pid": 13990,
                "usename": "batch_loader",
                "client_addr": "10.0.1.20",
                "state": "idle in transaction",
                "duration_seconds": 450.2,
                "wait_event_type": "Client",
                "wait_event": "ClientRead",
                "blocked_by_pids": [],
                "query": "LOCK TABLE orders IN EXCLUSIVE MODE;",
            },
            {
                "pid": 14205,
                "usename": "app_worker",
                "client_addr": "10.0.1.45",
                "state": "active",
                "duration_seconds": 380.5,
                "wait_event_type": "Lock",
                "wait_event": "relation",
                "blocked_by_pids": [13990],
                "query": "UPDATE orders SET status = 'PROCESSING' WHERE created_at < NOW() - INTERVAL '1 day';",
            },
        ]

    try:
        with get_db_cursor(dict_cursor=True) as cur:
            cur.execute(QUERY_LOCK_TREE)
            return cur.fetchall()
    except Exception as exc:
        logger.warning("Error fetching blocking tree: %s", exc)
        return []


def get_active_locks():
    """
    Fetches raw lock table entries for low-level diagnosis.
    """
    try:
        with get_db_cursor(dict_cursor=True) as cur:
            cur.execute(QUERY_ACTIVE_LOCKS)
            return cur.fetchall()
    except Exception as exc:
        logger.warning("Error fetching active locks: %s", exc)
        return []
