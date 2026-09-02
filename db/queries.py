"""
Centralized SQL Queries Repository for PostgreSQL DBA Health Monitoring.
Contains optimized SQL statements for system metrics, locks, storage, and health snapshots.
"""

# Basic Database Info & Connection Counts
QUERY_DATABASE_INFO = """
SELECT
    current_database() AS database_name,
    version() AS version,
    numbackends AS active_connections,
    xact_commit AS commits,
    xact_rollback AS rollbacks
FROM pg_stat_database
WHERE datname = current_database();
"""

# Maximum connection setting
QUERY_MAX_CONNECTIONS = """
SHOW max_connections;
"""

# Total Database Size in Bytes
QUERY_DATABASE_SIZE = """
SELECT pg_database_size(current_database()) AS size_bytes;
"""

# Long-Running Queries (Executing > 5 minutes)
QUERY_LONG_RUNNING_QUERIES_COUNT = """
SELECT count(*) AS long_query_count
FROM pg_stat_activity
WHERE state <> 'idle'
  AND query_start IS NOT NULL
  AND now() - query_start > interval '5 minutes'
  AND pid <> pg_backend_pid();
"""

# Detailed Long-Running Queries
QUERY_LONG_RUNNING_QUERIES_DETAILS = """
SELECT
    pid,
    usename AS user,
    client_addr AS client_ip,
    state,
    ROUND(EXTRACT(EPOCH FROM (now() - query_start))::numeric, 1) AS duration_seconds,
    wait_event_type,
    wait_event,
    LEFT(query, 500) AS query_snippet
FROM pg_stat_activity
WHERE state <> 'idle'
  AND query_start IS NOT NULL
  AND now() - query_start > interval '10 seconds'
  AND pid <> pg_backend_pid()
ORDER BY query_start ASC
LIMIT 25;
"""

# Blocking Sessions Count
QUERY_BLOCKING_SESSIONS_COUNT = """
SELECT count(*) AS blocking_count
FROM pg_stat_activity
WHERE cardinality(pg_blocking_pids(pid)) > 0;
"""

# Detailed Blocking & Blocked Query Graph
QUERY_BLOCKING_DETAILS = """
SELECT
    blocked.pid AS blocked_pid,
    blocking.pid AS blocking_pid,
    blocked.usename AS blocked_user,
    blocking.usename AS blocking_user,
    ROUND(EXTRACT(EPOCH FROM (now() - blocked.query_start))::numeric, 1) AS blocked_duration_sec,
    LEFT(blocked.query, 300) AS blocked_query,
    LEFT(blocking.query, 300) AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking
  ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
LIMIT 20;
"""

# Transaction ID (XID) Age to detect Wraparound risk
QUERY_XID_AGE = """
SELECT max(age(datfrozenxid)) AS max_xid_age
FROM pg_database;
"""

# Cache Hit Ratio (Buffer Cache Efficiency)
QUERY_CACHE_HIT_RATIO = """
SELECT
    datname,
    ROUND(
        (100.0 * blks_hit / NULLIF(blks_hit + blks_read, 0))::numeric,
        2
    ) AS cache_hit_ratio
FROM pg_stat_database
WHERE datname = current_database();
"""

# Top Tables by Total Size (Table + Indexes + TOAST)
QUERY_TOP_TABLES = """
SELECT
    schemaname,
    relname AS table_name,
    pg_total_relation_size(relid) AS total_size_bytes,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size_pretty,
    pg_size_pretty(pg_relation_size(relid)) AS table_size_pretty,
    pg_size_pretty(pg_indexes_size(relid)) AS index_size_pretty
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;
"""

# Dead Tuples and Autovacuum Statistics
QUERY_DEAD_TUPLES = """
SELECT
    schemaname,
    relname AS table_name,
    n_live_tup AS live_tuples,
    n_dead_tup AS dead_tuples,
    ROUND(
        (100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0))::numeric,
        2
    ) AS dead_tuple_ratio_pct,
    last_autovacuum,
    last_vacuum,
    last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 15;
"""

# Check Installed Extensions
QUERY_EXTENSIONS = """
SELECT extname, extversion
FROM pg_extension
WHERE extname IN ('pg_stat_statements', 'vector');
"""

# Top SQL Queries by Execution Time (if pg_stat_statements is enabled)
QUERY_TOP_STATEMENTS = """
SELECT
    LEFT(query, 200) AS query_snippet,
    calls,
    ROUND(total_exec_time::numeric, 2) AS total_time_ms,
    ROUND(mean_exec_time::numeric, 2) AS mean_time_ms,
    rows
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
"""

# Replication Lag (for RDS Multi-AZ / Read Replicas)
QUERY_REPLICATION_STATUS = """
SELECT
    client_addr AS replica_ip,
    state,
    sync_state,
    ROUND(EXTRACT(EPOCH FROM (now() - replay_lag))::numeric, 2) AS replay_lag_seconds
FROM pg_stat_replication;
"""

# Insert Health Snapshot
QUERY_INSERT_HEALTH_HISTORY = """
INSERT INTO dba_ai.health_history (
    database_name,
    connections,
    max_connections,
    database_size_bytes,
    long_running_queries,
    blocking_sessions,
    xid_age,
    cache_hit_ratio,
    status
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
"""

# Retrieve Recent Health History for Trends
QUERY_SELECT_HEALTH_HISTORY = """
SELECT
    collected_at,
    database_name,
    connections,
    max_connections,
    database_size_bytes,
    long_running_queries,
    blocking_sessions,
    xid_age,
    cache_hit_ratio,
    status
FROM dba_ai.health_history
ORDER BY collected_at ASC
LIMIT %s;
"""
