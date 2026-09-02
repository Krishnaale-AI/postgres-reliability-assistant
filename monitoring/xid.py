"""
Transaction ID (XID) Wraparound Risk Monitor.
Calculates distance to PostgreSQL transaction wraparound limit (2.14B transactions).
"""

import logging
from db.connection import get_db_cursor
from config import DEMO_MODE

logger = logging.getLogger("monitoring.xid")

QUERY_DATABASE_XIDS = """
SELECT
    datname AS database_name,
    age(datfrozenxid) AS current_xid_age,
    2147483648 - age(datfrozenxid) AS tx_remaining_until_wraparound,
    ROUND((age(datfrozenxid)::numeric / 2147483648.0) * 100, 2) AS wraparound_pct_used
FROM pg_database
ORDER BY age(datfrozenxid) DESC;
"""

QUERY_TABLE_XIDS = """
SELECT
    schemaname,
    relname AS table_name,
    age(relfrozenxid) AS table_xid_age,
    ROUND((age(relfrozenxid)::numeric / 2147483648.0) * 100, 2) AS wraparound_pct_used
FROM pg_stat_user_tables
ORDER BY age(relfrozenxid) DESC
LIMIT 10;
"""


def get_database_xid_ages():
    """Fetches XID ages across all databases on the PostgreSQL instance."""
    if DEMO_MODE:
        return [
            {"database_name": "dba_ai", "current_xid_age": 14250000, "tx_remaining_until_wraparound": 2133233648, "wraparound_pct_used": 0.66},
            {"database_name": "postgres", "current_xid_age": 1200000, "tx_remaining_until_wraparound": 2146283648, "wraparound_pct_used": 0.06},
        ]

    try:
        with get_db_cursor(dict_cursor=True) as cur:
            cur.execute(QUERY_DATABASE_XIDS)
            return cur.fetchall()
    except Exception as exc:
        logger.warning("Error fetching database XID ages: %s", exc)
        return []


def calculate_wraparound_risk(max_xid_age):
    """
    Evaluates risk level and remaining headroom before emergency shutdown.
    
    Risk Thresholds:
    - Normal: < 200M (autovacuum_freeze_max_age standard)
    - Warning: 200M - 1 Billion
    - Critical: > 1 Billion (autovacuum emergency freeze triggers)
    - Emergency: > 1.5 Billion (approaching read-only mode)
    """
    pct = (max_xid_age / 2_147_483_648) * 100.0
    remaining = 2_147_483_648 - max_xid_age

    if max_xid_age >= 1_500_000_000:
        level = "EMERGENCY"
        action = "CRITICAL: Imminent wraparound risk! Run manual aggressive VACUUM FREEZE immediately."
    elif max_xid_age >= 1_000_000_000:
        level = "CRITICAL"
        action = "Aggressive autovacuum freeze should be running. Monitor autovacuum workers and table bloat."
    elif max_xid_age >= 200_000_000:
        level = "WARNING"
        action = "Database has passed typical freeze threshold. Normal autovacuum freeze is handling it."
    else:
        level = "HEALTHY"
        action = "XID age is well within normal operational boundaries."

    return {
        "xid_age": max_xid_age,
        "wraparound_pct": round(pct, 2),
        "transactions_remaining": remaining,
        "risk_level": level,
        "recommendation": action,
    }
