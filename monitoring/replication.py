"""
Replication & WAL Generation Monitor.
Monitors standby replicas, replay lag, replication slots, and WAL generation rate.
"""

import logging
from db.connection import get_db_cursor
from config import DEMO_MODE

logger = logging.getLogger("monitoring.replication")

QUERY_REPLICATION_SLOTS = """
SELECT
    slot_name,
    plugin,
    slot_type,
    active,
    wal_status,
    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained_wal_bytes
FROM pg_replication_slots;
"""

QUERY_WAL_STATS = """
SELECT
    wal_records,
    wal_fpi,
    wal_bytes,
    wal_buffers_full,
    wal_write,
    wal_sync,
    wal_write_time,
    wal_sync_time
FROM pg_stat_wal;
"""


def get_replication_lag_metrics():
    """
    Returns replication status, replay lag, and active slots.
    """
    if DEMO_MODE:
        return {
            "replicas": [
                {
                    "client_addr": "10.0.3.12",
                    "application_name": "rds_read_replica_1",
                    "state": "streaming",
                    "sync_state": "async",
                    "replay_lag_seconds": 1.8,
                }
            ],
            "slots": [
                {
                    "slot_name": "rds_backup_slot",
                    "plugin": None,
                    "slot_type": "physical",
                    "active": True,
                    "wal_status": "normal",
                    "retained_wal_bytes": "16 MB",
                }
            ],
            "wal_stats": {
                "wal_write_mb": 420.5,
                "wal_sync_count": 8420,
            }
        }

    try:
        with get_db_cursor(dict_cursor=True) as cur:
            cur.execute("""
                SELECT
                    client_addr,
                    application_name,
                    state,
                    sync_state,
                    ROUND(EXTRACT(EPOCH FROM replay_lag)::numeric, 2) AS replay_lag_seconds
                FROM pg_stat_replication;
            """)
            replicas = cur.fetchall()

            cur.execute(QUERY_REPLICATION_SLOTS)
            slots = cur.fetchall()

            return {
                "replicas": replicas,
                "slots": slots,
            }
    except Exception as exc:
        logger.debug("Could not fetch replication metrics (standalone or insufficient perms): %s", exc)
        return {"replicas": [], "slots": []}
