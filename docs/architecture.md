# AI PostgreSQL DBA Health Assistant - Architecture Guide

## 1. System Overview

The **AI PostgreSQL DBA Health Assistant** is an intelligent monitoring, diagnostic, and remediation assistant designed for **AWS RDS PostgreSQL 15.16**. It bridges deep database telemetry with generative AI reasoning using **Amazon Bedrock** and vector similarity retrieval via **pgvector**.

```mermaid
flowchart TD
    subgraph AWS_RDS ["AWS RDS PostgreSQL 15.16"]
        PGA["pg_stat_activity"]
        PGD["pg_stat_database"]
        PGS["pg_stat_statements"]
        PGU["pg_stat_user_tables"]
        PGV["pgvector (dba_ai.incidents)"]
        HIS["dba_ai.health_history"]
    end

    subgraph AWS_Cloud ["AWS Management Services"]
        CW["Amazon CloudWatch\n(CPU, IOPS, Memory, Storage)"]
        SM["AWS Secrets Manager\n(Database Credentials)"]
        Bedrock["Amazon Bedrock\n(Nova Lite / Titan Embeddings)"]
    end

    subgraph Python_Backend ["Python Diagnostic & RAG Engine"]
        Conn["db/connection.py\n(SSL & Secrets Manager)"]
        Collector["db/health.py\n(Metric Aggregation & Scoring)"]
        Monitoring["monitoring/*\n(Storage, Locks, Vacuum, XID, Replication)"]
        BedrockClient["ai/bedrock.py\n(Bedrock Converse API)"]
        RAGClient["ai/rag.py\n(Cosine Distance Search)"]
    end

    subgraph User_Interface ["Streamlit Dashboard (app.py)"]
        ScoreGauge["Reliability Index Gauge (0-100)"]
        PerfTab["Locks & Slow Queries"]
        StorageTab["Storage Bloat & Growth Trends"]
        CWTab["RDS Infrastructure Telemetry"]
        AITab["Bedrock Executive Diagnosis"]
        RAGTab["pgvector Historical Incident RAG"]
    end

    %% Connections
    SM -.->|Fetch Credentials| Conn
    Conn -->|Query Catalogs| PGA & PGD & PGS & PGU
    PGA & PGD & PGS & PGU --> Collector & Monitoring
    CW --> Monitoring
    Collector -->|Record Snapshots| HIS
    Collector --> ScoreGauge
    Collector --> BedrockClient
    PGV <-->|Semantic Search| RAGClient
    Bedrock <-->|Inference & Embeddings| BedrockClient & RAGClient
    BedrockClient --> AITab
    RAGClient --> RAGTab
    Monitoring --> PerfTab & StorageTab & CWTab
```

---

## 2. Key Subsystems

### A. Database Health Engine (`db/`)
- **Connection Factory (`connection.py`)**: Enforces TLS (`sslmode=require`) connections and supports dynamic credential resolution from AWS Secrets Manager.
- **Health Collector (`health.py`)**: Gathers metrics from PostgreSQL system catalogs (`pg_stat_activity`, `pg_stat_database`, `pg_statio_user_tables`, `pg_database`).
- **Deterministic Reliability Score (`calculate_health_score`)**: Computes a score (0–100) and severity rating (`HEALTHY`, `WARNING`, `CRITICAL`) using mathematical penalty weights for lock contention, long-running queries, buffer cache misses, and XID age.
- **Snapshot Persistence (`history.py`)**: Stores time-series health metrics in `dba_ai.health_history` for trend visualization.

### B. Specialized DBA Monitoring Modules (`monitoring/`)
- **Storage Bloat (`storage.py`)**: Analyzes table sizes, index overhead, and TOAST distribution.
- **Lock Contention (`locks.py`)**: Reconstructs recursive blocking trees to trace root blocking backends.
- **Autovacuum & Dead Tuples (`vacuum.py`)**: Tracks dead tuple ratios and autovacuum worker execution.
- **Transaction ID Wraparound (`xid.py`)**: Monitors `datfrozenxid` and `relfrozenxid` against PostgreSQL's 2.14B limit.
- **Replication Lag (`replication.py`)**: Tracks streaming replica replay delay and WAL backlog.
- **CloudWatch Telemetry (`cloudwatch.py`)**: Pulls CPU utilization, IOPS, and storage headroom from AWS CloudWatch.

### C. Generative AI & pgvector RAG (`ai/`)
- **Bedrock Converse API (`bedrock.py`)**: Generates structured, non-destructive DBA reports using foundation models like Amazon Nova Lite (`amazon.nova-lite-v1:0`).
- **Titan Embeddings (`embeddings.py`)**: Computes 1024-dimensional normalized dense vectors with Amazon Titan Text Embeddings V2.
- **RAG Engine (`rag.py`)**: Executes cosine similarity searches (`<=>`) on `dba_ai.incidents` using `pgvector` HNSW indexes and synthesizes augmented solutions.
- **Safety Guardrails (`prompts.py`)**: Strict system prompts enforcing read-only investigation first, with copy-pasteable SQL commands for safe DBA execution.
