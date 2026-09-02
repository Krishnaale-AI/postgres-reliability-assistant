-- ==============================================================================
-- AI PostgreSQL DBA Health Assistant - Diagnostic Query Reference Catalog
-- Use these queries directly in psql, pgAdmin, or DBeaver for deep manual audits.
-- ==============================================================================

-- 1. General Database Health & Buffer Hit Ratio
SELECT
    datname AS database_name,
    numbackends AS active_connections,
    xact_commit AS total_commits,
    xact_rollback AS total_rollbacks,
    ROUND((100.0 * blks_hit / NULLIF(blks_hit + blks_read, 0))::numeric, 2) AS cache_hit_ratio_pct,
    pg_size_pretty(pg_database_size(datname)) AS total_database_size
FROM pg_stat_database
WHERE datname = current_database();

-- 2. Inspect Active and Long-Running Queries (> 1 minute)
SELECT
    pid,
    usename,
    client_addr,
    application_name,
    state,
    ROUND(EXTRACT(EPOCH FROM (now() - query_start))::numeric, 1) AS running_seconds,
    wait_event_type,
    wait_event,
    query
FROM pg_stat_activity
WHERE state <> 'idle'
  AND query_start IS NOT NULL
  AND now() - query_start > interval '1 minute'
  AND pid <> pg_backend_pid()
ORDER BY query_start ASC;

-- 3. Lock Contention & Blocking Session Hierarchy
SELECT
    blocked.pid AS blocked_pid,
    blocking.pid AS blocking_pid,
    blocked.usename AS blocked_user,
    blocking.usename AS blocking_user,
    blocked.state AS blocked_state,
    blocking.state AS blocking_state,
    ROUND(EXTRACT(EPOCH FROM (now() - blocked.query_start))::numeric, 1) AS blocked_duration_sec,
    blocked.query AS blocked_query,
    blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking
  ON blocking.pid = ANY(pg_blocking_pids(blocked.pid));

-- 4. Top 15 Largest Tables with Index Sizes
SELECT
    schemaname,
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    pg_size_pretty(pg_relation_size(relid)) AS table_size,
    pg_size_pretty(pg_indexes_size(relid)) AS index_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 15;

-- 5. Dead Tuples and Autovacuum Activity
SELECT
    schemaname,
    relname AS table_name,
    n_live_tup AS live_tuples,
    n_dead_tup AS dead_tuples,
    ROUND((100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0))::numeric, 2) AS dead_tuple_ratio_pct,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 15;

-- 6. Top 10 Most Expensive Queries (pg_stat_statements)
SELECT
    query,
    calls,
    ROUND(total_exec_time::numeric, 2) AS total_time_ms,
    ROUND(mean_exec_time::numeric, 2) AS mean_time_ms,
    ROUND((100.0 * shared_blks_hit / NULLIF(shared_blks_hit + shared_blks_read, 0))::numeric, 2) AS hit_percent
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;

-- 7. Transaction ID Wraparound Risk
SELECT
    datname,
    age(datfrozenxid) AS current_xid_age,
    2147483648 - age(datfrozenxid) AS tx_until_wraparound_shutdown,
    ROUND((age(datfrozenxid)::numeric / 2147483648.0) * 100, 2) AS pct_of_limit_used
FROM pg_database
ORDER BY age(datfrozenxid) DESC;

-- 8. Replication Lag Check (Replicas and Slots)
SELECT
    client_addr AS replica_ip,
    application_name,
    state,
    sync_state,
    ROUND(EXTRACT(EPOCH FROM replay_lag)::numeric, 2) AS replay_lag_seconds
FROM pg_stat_replication;
