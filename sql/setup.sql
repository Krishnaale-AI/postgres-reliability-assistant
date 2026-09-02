-- ==============================================================================
-- AI PostgreSQL DBA Health Assistant - Database Setup Script
-- Target: AWS RDS PostgreSQL 15.16
-- Database: dba_ai
-- ==============================================================================

-- 1. Enable Required Extensions
-- Note: On AWS RDS PostgreSQL 15, ensure your DB parameter group has
-- shared_preload_libraries containing 'pg_stat_statements'.
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create Application Schema
CREATE SCHEMA IF NOT EXISTS dba_ai;

-- ------------------------------------------------------------------------------
-- 3. Create Health Snapshot History Table
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dba_ai.health_history (
    id BIGSERIAL PRIMARY KEY,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    database_name TEXT NOT NULL,
    connections INTEGER NOT NULL DEFAULT 0,
    max_connections INTEGER NOT NULL DEFAULT 100,
    database_size_bytes BIGINT NOT NULL DEFAULT 0,
    long_running_queries INTEGER NOT NULL DEFAULT 0,
    blocking_sessions INTEGER NOT NULL DEFAULT 0,
    xid_age BIGINT NOT NULL DEFAULT 0,
    cache_hit_ratio NUMERIC(5, 2) DEFAULT 99.0,
    replication_lag_seconds DOUBLE PRECISION DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'HEALTHY'
);

CREATE INDEX IF NOT EXISTS idx_health_history_collected_at 
ON dba_ai.health_history (collected_at DESC);

-- ------------------------------------------------------------------------------
-- 4. Create Historical DBA Incident Knowledge Base Table (RAG + pgvector)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dba_ai.incidents (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    problem TEXT NOT NULL,
    root_cause TEXT NOT NULL,
    resolution TEXT NOT NULL,
    prevention TEXT NOT NULL,
    embedding VECTOR(1024), -- Set to 1024 for Titan V2, or 1536 for Titan V1 / OpenAI
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 5. Seed Initial DBA Incident Catalog
-- ------------------------------------------------------------------------------
INSERT INTO dba_ai.incidents (title, problem, root_cause, resolution, prevention)
VALUES
(
    'Rapid Database Storage Growth from Batch ETL',
    'Database size expanded by 35 GB in 6 hours, triggering a low storage warning in CloudWatch.',
    'Nightly batch insertion job loaded raw customer telemetry into unpartitioned table without TOAST compression and index cleanup.',
    'Identified the largest table via pg_stat_user_tables, archived historic partitions to S3, and reclaimed space.',
    'Implement table partitioning by month, enable RDS Storage Auto-Scaling, and set CloudWatch FreeStorageSpace alarm at 20%.'
),
(
    'Application Lock Queuing from Uncommitted Transaction',
    'Application API response times degraded from 50ms to 30s. Multiple microservices reported 504 gateway timeouts.',
    'A developer initiated a transaction in DBeaver with an EXCLUSIVE lock on orders table and left the session idle in transaction.',
    'Queried pg_stat_activity using pg_blocking_pids(), identified the blocking PID, and executed pg_cancel_backend() followed by pg_terminate_backend().',
    'Set idle_in_transaction_session_timeout = 60000 (60s) in the RDS parameter group to prevent abandoned transactions.'
),
(
    'Replication Lag Spike During Bulk UPDATE',
    'RDS Read Replica lag increased from 0 seconds to 18 minutes during business hours, causing stale read queries.',
    'A single monolithic UPDATE statement updated 5 million rows on the primary, overwhelming replica WAL replay queue.',
    'Batched remaining updates into transactions of 5,000 rows with 50ms sleep intervals; monitored pg_stat_replication until lag cleared.',
    'Enforce application batch-write limits and adjust max_standby_streaming_delay in replica parameter group.'
),
(
    'Transaction ID Wraparound Warning',
    'PostgreSQL log reported WARNING: database "dba_ai" must be vacuumed within 10000000 transactions to prevent wraparound shutdown.',
    'Autovacuum was falling behind due to heavy I/O throttling on a db.t3.micro burstable instance with autovacuum_max_workers = 3.',
    'Executed manual VACUUM FREEZE VERBOSE on high-age tables during maintenance window and adjusted autovacuum_vacuum_cost_limit.',
    'Monitor datfrozenxid age continuously and alert when max_xid_age exceeds 500,000,000.'
),
(
    'Degraded Query Performance from Buffer Cache Eviction',
    'Average query latency spiked 4x after a large analytics reporting query swept through the shared buffer cache.',
    'Sequential scan on a 40GB table polluted the shared_buffers cache, evicting frequently accessed index pages.',
    'Added missing composite B-Tree index on (tenant_id, created_at) to avoid table scans and used pg_prewarm to reload hot tables.',
    'Route heavy analytical reporting queries to a dedicated RDS Read Replica.'
)
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------------------------
-- 6. Create HNSW Vector Cosine Distance Index
-- Note: Run after populating embeddings. HNSW provides fast approximate nearest neighbor search.
-- ------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_incidents_embedding_hnsw
ON dba_ai.incidents
USING hnsw (embedding vector_cosine_ops);
