"""
Amazon Bedrock Integration Module.
Uses the Bedrock Converse API for structured DBA reasoning with Amazon Nova Lite / Claude.
"""

import logging
from config import (
    AWS_REGION,
    AWS_PROFILE,
    BEDROCK_MODEL_ID,
    DEMO_MODE,
)
from .prompts import SYSTEM_PROMPT_SENIOR_DBA, format_health_prompt

logger = logging.getLogger("ai.bedrock")


def get_bedrock_client():
    """Initializes and returns a boto3 bedrock-runtime client."""
    import boto3
    session = boto3.Session(region_name=AWS_REGION, profile_name=AWS_PROFILE)
    return session.client("bedrock-runtime")


def analyze_database(metrics, custom_notes=None):
    """
    Sends database health metrics to Amazon Bedrock for expert DBA analysis.
    
    Args:
        metrics (dict): Health metrics collected from PostgreSQL
        custom_notes (str, optional): Additional DBA context
    Returns:
        str: AI-generated DBA analysis in Markdown format
    """
    if DEMO_MODE:
        return _generate_mock_dba_analysis(metrics)

    prompt = format_health_prompt(metrics)
    if custom_notes:
        prompt += f"\n\n### ADDITIONAL DBA NOTES / RECENT CHANGES:\n{custom_notes}\n"

    try:
        client = get_bedrock_client()
        logger.info("Invoking Amazon Bedrock Converse API with model: %s", BEDROCK_MODEL_ID)

        response = client.converse(
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": SYSTEM_PROMPT_SENIOR_DBA}],
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            inferenceConfig={
                "temperature": 0.2,
                "maxTokens": 2048,
                "topP": 0.9,
            },
        )

        content_list = response["output"]["message"]["content"]
        analysis_text = "".join([part.get("text", "") for part in content_list])
        return analysis_text

    except Exception as exc:
        logger.error("Bedrock analysis failed: %s. Returning fallback DBA diagnosis.", exc)
        return _generate_fallback_dba_analysis(metrics, str(exc))


def invoke_bedrock_chat(messages, system_prompt=SYSTEM_PROMPT_SENIOR_DBA):
    """
    Generic chat conversation handler with Bedrock Converse API.
    
    Args:
        messages (list): List of message dictionaries [{"role": "user"|"assistant", "content": [{"text": "..."}]}]
        system_prompt (str): System instructions
    Returns:
        str: Assistant response text
    """
    if DEMO_MODE:
        return "🤖 *[Demo Mode Response]* I analyzed the metrics and historical incidents. All systems are functioning within expected bounds."

    try:
        client = get_bedrock_client()
        response = client.converse(
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": system_prompt}],
            messages=messages,
            inferenceConfig={
                "temperature": 0.3,
                "maxTokens": 2048,
            },
        )
        content_list = response["output"]["message"]["content"]
        return "".join([part.get("text", "") for part in content_list])
    except Exception as exc:
        logger.error("Bedrock chat invocation error: %s", exc)
        return f"⚠️ **Bedrock Invocation Error:** `{exc}`\n\nPlease ensure your AWS credentials are configured and model access for `{BEDROCK_MODEL_ID}` is enabled in region `{AWS_REGION}`."


def _generate_mock_dba_analysis(metrics):
    """Generates an authentic DBA diagnosis for demo / testing."""
    status = metrics.get("status", "WARNING")
    score = metrics.get("health_score", 75)
    blocking = metrics.get("blocking_sessions", 1)
    long_q = metrics.get("long_running_queries", 2)
    db_size = metrics.get("database_size_gb", 452.0)

    return f"""### 🛡️ PostgreSQL DBA Diagnostic Report (Amazon Bedrock Nova Lite)

**Status:** `{status}` | **Health Score:** `{score}/100` | **Engine:** `PostgreSQL 15.16 (AWS RDS)`

---

#### 1. Executive Summary & Health Assessment
The database cluster is currently in a **{status}** state. While the buffer cache hit ratio remains excellent at **{metrics.get('cache_hit_ratio', 99.15)}%**, there is active lock contention with **{blocking} blocking session(s)** and **{long_q} long-running query(s)** that require immediate attention to prevent connection pool exhaustion.

---

#### 2. Critical & Warning Findings

##### 🔴 Finding 1: Exclusive Lock Contention on `orders` Table
- **Evidence:** PID `13990` (`batch_loader`) has acquired an `EXCLUSIVE` lock and is currently `idle in transaction` for >450 seconds.
- **Impact:** Blocked backend PID `14205` (`app_worker`) waiting on `relation` lock, cascading to application worker timeouts.
- **Probable Root Cause:** An uncommitted batch migration or ETL script left a transaction open without issuing a `COMMIT` or `ROLLBACK`.

##### 🟠 Finding 2: Storage Growth on Primary Partition
- **Evidence:** Database storage has grown to **{db_size} GB**, primarily dominated by `public.orders` (182 GB) and `public.order_items` (115 GB).
- **Impact:** RDS storage threshold approaching allocated limits without active autovacuum compaction.

---

#### 3. Recommended Investigation SQL (Safe / Read-Only)

```sql
-- 1. Inspect the blocking transaction details and uncommitted query
SELECT
    pid, usename, client_addr, state,
    now() - xact_start AS xact_age,
    now() - query_start AS query_age,
    query
FROM pg_stat_activity
WHERE pid IN (13990, 14205);

-- 2. Inspect all active lock conflicts
SELECT
    blocked.pid AS blocked_pid,
    blocking.pid AS blocking_pid,
    blocked.query AS blocked_query,
    blocking.query AS blocking_statement
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking ON blocking.pid = ANY(pg_blocking_pids(blocked.pid));
```

---

#### 4. Immediate Remediation Steps (DBA Action Required)
1. **Coordinate Session Termination:** Contact the team running `batch_loader` (PID `13990`). If unresponsive and impacting production:
   ```sql
   -- Cancel the blocking query gracefully:
   SELECT pg_cancel_backend(13990);
   -- Or terminate if cancel does not release within 30s:
   SELECT pg_terminate_backend(13990);
   ```
2. **Verify Lock Release:** Re-check `pg_stat_activity` to ensure `app_worker` queries resume execution without queue buildup.

---

#### 5. Long-Term Preventative Measures
- **Configure `idle_in_transaction_session_timeout`:** Set to `60000` (60 seconds) in the RDS Parameter Group to automatically terminate abandoned sessions.
- **Enable `statement_timeout`:** Prevent individual application queries from exceeding 30 seconds without DBA approval.
- **CloudWatch Alarm:** Configure alarms on `ReadIOPS` > 500 and `CPUUtilization` > 80%.
"""


def _generate_fallback_dba_analysis(metrics, error_msg):
    """Fallback generator when Bedrock client is not connected to AWS."""
    return f"""### ⚠️ Offline DBA Analysis (Local Diagnostic Engine)

*Notice: Amazon Bedrock Converse API could not be reached ({error_msg}). Displaying rule-based diagnostic breakdown:*

- **Database:** `{metrics.get('database')}` ({metrics.get('postgresql_version')})
- **Health Score:** `{metrics.get('health_score')}/100` ({metrics.get('status')})
- **Connections:** `{metrics.get('connections')}` / `{metrics.get('max_connections')}`
- **Long Queries (>5m):** `{metrics.get('long_running_queries')}`
- **Blocking Sessions:** `{metrics.get('blocking_sessions')}`
- **XID Age:** `{metrics.get('xid_age')}`

#### Recommended Actions:
1. Verify RDS connectivity and ensure `pg_stat_activity` is accessible.
2. Check `idle_in_transaction_session_timeout` parameter in your RDS parameter group.
3. Configure AWS credentials via `aws configure` to enable Bedrock Nova AI analysis.
"""
