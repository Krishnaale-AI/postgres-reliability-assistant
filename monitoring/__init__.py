"""
PostgreSQL Specialized Monitoring Package.
Provides dedicated modules for storage analysis, lock detection, vacuum optimization,
transaction ID tracking, replication lag, and CloudWatch metrics.
"""

from .storage import analyze_storage_bloat, get_tablespace_stats
from .locks import analyze_blocking_tree, get_active_locks
from .vacuum import check_vacuum_needed, get_autovacuum_activity
from .xid import calculate_wraparound_risk, get_database_xid_ages
from .replication import get_replication_lag_metrics
# pyrefly: ignore [missing-import]
from .cloudwatch import get_rds_cloudwatch_metrics

__all__ = [
    "analyze_storage_bloat",
    "get_tablespace_stats",
    "analyze_blocking_tree",
    "get_active_locks",
    "check_vacuum_needed",
    "get_autovacuum_activity",
    "calculate_wraparound_risk",
    "get_database_xid_ages",
    "get_replication_lag_metrics",
    "get_rds_cloudwatch_metrics",
]
