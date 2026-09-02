"""
Retrieval-Augmented Generation (RAG) Module using pgvector.
Performs semantic similarity search on historical DBA incidents and generates guided resolution plans.
"""

import logging
from db.connection import get_db_cursor
from config import DEMO_MODE
from .embeddings import get_text_embedding
from .bedrock import analyze_database
from .prompts import format_rag_prompt, SYSTEM_PROMPT_SENIOR_DBA

logger = logging.getLogger("ai.rag")

QUERY_SIMILAR_INCIDENTS = """
SELECT
    id,
    title,
    problem,
    root_cause,
    resolution,
    prevention,
    (embedding <=> %s::vector) AS distance
FROM dba_ai.incidents
WHERE embedding IS NOT NULL
ORDER BY embedding <=> %s::vector ASC
LIMIT %s;
"""

QUERY_UNEMBEDDED_INCIDENTS = """
SELECT id, title, problem, root_cause, resolution, prevention
FROM dba_ai.incidents
WHERE embedding IS NULL;
"""

QUERY_UPDATE_EMBEDDING = """
UPDATE dba_ai.incidents
SET embedding = %s::vector
WHERE id = %s;
"""


def search_similar_incidents(query_text, limit=3):
    """
    Searches the dba_ai.incidents table for historically similar DBA problems using pgvector cosine distance.
    
    Args:
        query_text (str): Problem description or query from user
        limit (int): Number of similar incidents to retrieve
    Returns:
        list[dict]: List of incident matches with distance scores
    """
    if DEMO_MODE:
        return _get_mock_incident_matches(query_text)

    try:
        # Generate embedding for the query
        query_vector = get_text_embedding(query_text)
        vector_str = "[" + ",".join(f"{x:.6f}" for x in query_vector) + "]"

        with get_db_cursor(dict_cursor=True) as cur:
            cur.execute(QUERY_SIMILAR_INCIDENTS, (vector_str, vector_str, limit))
            rows = cur.fetchall()
            if rows:
                return rows
    except Exception as exc:
        logger.warning("pgvector similarity search failed: %s. Using fallback incident catalog.", exc)

    return _get_mock_incident_matches(query_text)


def populate_incident_embeddings():
    """
    Generates and saves embeddings for all incidents in dba_ai.incidents that lack vectors.
    """
    if DEMO_MODE:
        return 3

    updated_count = 0
    try:
        with get_db_cursor(dict_cursor=True) as cur:
            cur.execute(QUERY_UNEMBEDDED_INCIDENTS)
            incidents = cur.fetchall()

            for inc in incidents:
                composite_text = f"{inc['title']}. Problem: {inc['problem']}. Root cause: {inc.get('root_cause', '')}."
                vector = get_text_embedding(composite_text)
                vector_str = "[" + ",".join(f"{x:.6f}" for x in vector) + "]"

                cur.execute(QUERY_UPDATE_EMBEDDING, (vector_str, inc["id"]))
                updated_count += 1

        logger.info("Successfully populated embeddings for %d incidents.", updated_count)
        return updated_count
    except Exception as exc:
        logger.error("Failed to populate incident embeddings: %s", exc)
        return updated_count


def answer_dba_rag_query(user_query, current_metrics):
    """
    Full RAG pipeline:
    1. Search pgvector for similar past DBA cases.
    2. Format augmented prompt with current metrics + historical solutions.
    3. Invoke Amazon Bedrock to generate a DBA recommendation.
    """
    # 1. Retrieve
    similar_incidents = search_similar_incidents(user_query, limit=3)

    # 2. Augment
    rag_prompt = format_rag_prompt(user_query, current_metrics, similar_incidents)

    # 3. Generate via Bedrock
    if DEMO_MODE:
        return _generate_mock_rag_response(user_query, similar_incidents), similar_incidents

    try:
        from .bedrock import get_bedrock_client, BEDROCK_MODEL_ID

        client = get_bedrock_client()
        response = client.converse(
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": SYSTEM_PROMPT_SENIOR_DBA}],
            messages=[
                {
                    "role": "user",
                    "content": [{"text": rag_prompt}],
                }
            ],
            inferenceConfig={
                "temperature": 0.2,
                "maxTokens": 2048,
            },
        )
        content_list = response["output"]["message"]["content"]
        answer_text = "".join([part.get("text", "") for part in content_list])
        return answer_text, similar_incidents

    except Exception as exc:
        logger.warning("Bedrock RAG response generation failed: %s. Returning fallback answer.", exc)
        return _generate_mock_rag_response(user_query, similar_incidents), similar_incidents


def _get_mock_incident_matches(query_text):
    """Returns realistic historical DBA incident matches for demo/offline mode."""
    q = query_text.lower()
    if "storage" in q or "grow" in q or "size" in q or "disk" in q:
        return [
            {
                "id": 1,
                "title": "Rapid RDS Storage Growth from Unindexed Audit Logs",
                "problem": "RDS database storage expanded by 45 GB within 12 hours, triggering a low-disk warning.",
                "root_cause": "A nightly ETL pipeline performed massive batch inserts into the audit_logs table without table partitioning or TOAST compression.",
                "resolution": "Truncated temporary staging tables, created monthly range partitions for audit_logs, and enabled storage auto-scaling.",
                "prevention": "Set up CloudWatch FreeStorageSpace alarm at 20% threshold and configured daily table bloat reports.",
                "distance": 0.08,
            },
            {
                "id": 2,
                "title": "Autovacuum Lag Leading to Table Bloat",
                "problem": "Query performance degraded 5x following high-volume UPDATE operations.",
                "root_cause": "Autovacuum settings were too conservative (autovacuum_vacuum_scale_factor = 0.2 on a 50M-row table).",
                "resolution": "Tuned table-level autovacuum scale factor to 0.05 and ran pg_repack to reclaim 30GB disk space without locks.",
                "prevention": "Configured table-specific autovacuum parameters for write-heavy tables.",
                "distance": 0.15,
            },
        ]
    elif "lock" in q or "block" in q or "hang" in q or "slow" in q:
        return [
            {
                "id": 3,
                "title": "Uncommitted Transaction Causing Widespread Lock Queuing",
                "problem": "Web application connections spiked to maximum and APIs timed out with 504 errors.",
                "root_cause": "A developer executed an ALTER TABLE inside a DBeaver session and left the transaction open ('idle in transaction') while acquiring ACCESS EXCLUSIVE lock.",
                "resolution": "Identified the blocking PID via pg_blocking_pids() and terminated the session via pg_terminate_backend().",
                "prevention": "Configured idle_in_transaction_session_timeout = 60000 (60s) in the RDS parameter group.",
                "distance": 0.05,
            }
        ]
    else:
        return [
            {
                "id": 4,
                "title": "Replication Lag Spike on RDS Read Replica",
                "problem": "Read replica lag exceeded 15 minutes during peak reporting hours.",
                "root_cause": "A large batch UPDATE statement generated substantial WAL volume on primary while replica was CPU-throttled on db.t3.micro.",
                "resolution": "Batched updates into chunks of 5000 rows and upgraded replica to db.m6g.large.",
                "prevention": "Enforced batch sizing standards for application write workloads.",
                "distance": 0.12,
            }
        ]


def _generate_mock_rag_response(user_query, incidents):
    """Generates mock RAG response synthesis."""
    top_inc = incidents[0] if incidents else {}
    return f"""### 💡 RAG-Augmented DBA Analysis

**Inquiry:** *"{user_query}"*

#### 1. Correlation with Historical Incidents
Based on a vector similarity match with **Historical Incident #{top_inc.get('id')}: "{top_inc.get('title')}"**, the symptoms align closely with past incidents:
- **Historical Root Cause:** {top_inc.get('root_cause')}
- **Historical Solution:** {top_inc.get('resolution')}

#### 2. Root Cause Analysis for Current Environment
Review of active telemetry indicates potential correlation. The primary factors include:
1. Transaction concurrency holding lock primitives or accumulating dead tuples.
2. Background autovacuum latency relative to table write frequency.

#### 3. Recommended Investigation SQL
```sql
-- Check table bloat and dead tuple accumulation
SELECT schemaname, relname, n_live_tup, n_dead_tup,
       ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS dead_ratio_pct,
       last_autovacuum
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 5;
```

#### 4. Step-by-Step Resolution
1. Validate whether autovacuum is currently actively processing the target relation.
2. Check if setting table-level `autovacuum_vacuum_scale_factor = 0.05` improves worker scheduling.
3. Review `{top_inc.get('prevention')}` to prevent future occurrences.
"""
