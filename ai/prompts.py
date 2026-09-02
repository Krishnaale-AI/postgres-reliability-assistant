"""
Prompt Templates and DBA System Instructions for Amazon Bedrock.
Includes safety guardrails preventing automated destructive actions.
"""

SYSTEM_PROMPT_SENIOR_DBA = """
You are a Principal AWS RDS PostgreSQL Database Administrator and Reliability Engineer.
Your objective is to provide precise, actionable, and non-destructive diagnosis of database health and performance issues.

STRICT OPERATIONAL RULES:
1. SAFE DBA RECOMMENDATIONS ONLY: Never propose destructive commands (e.g. DROP TABLE, TRUNCATE, DELETE, ALTER TABLE without CONCURRENTLY) without clear warnings and safe investigation steps.
2. DISTINGUISH FACTS FROM HYPOTHESES: Clearly cite which specific metric proves an issue versus what is an educated hypothesis.
3. CONCRETE INVESTIGATION SQL: For every identified issue, provide clean, copy-pasteable PostgreSQL query snippets using system catalogs (pg_stat_activity, pg_stat_statements, pg_stat_user_tables).
4. PREVENTATIVE GUIDANCE: Provide architecture and configuration advice (e.g. autovacuum tuning, connection pooling, index adjustments, CloudWatch alarms).
5. AWS RDS CONTEXT: Keep AWS RDS specifics in mind (managed PostgreSQL, parameter groups, Multi-AZ, CloudWatch metrics, storage auto-scaling).
"""


def format_health_prompt(metrics):
    """Formats live or collected health metrics into a senior DBA diagnostic prompt."""
    
    # Format top tables summary
    top_tables_summary = ""
    for t in metrics.get("top_tables", [])[:5]:
        top_tables_summary += f"  - {t.get('schemaname')}.{t.get('table_name')}: {t.get('total_size_pretty', 'N/A')} (Table: {t.get('table_size_pretty', 'N/A')}, Index: {t.get('index_size_pretty', 'N/A')})\n"
    if not top_tables_summary:
        top_tables_summary = "  - No user tables or stats unavailable.\n"

    # Format blocking sessions
    blocking_summary = ""
    for b in metrics.get("blocking_details", [])[:3]:
        blocking_summary += f"  - Blocked PID {b.get('blocked_pid')} ({b.get('blocked_user')}) blocked by PID {b.get('blocking_pid')} ({b.get('blocking_user')}) for {b.get('blocked_duration_sec')}s.\n    Blocked query: {b.get('blocked_query')}\n    Blocking query: {b.get('blocking_query')}\n"
    if not blocking_summary:
        blocking_summary = "  - None detected.\n"

    # Format long running queries
    long_q_summary = ""
    for q in metrics.get("long_query_details", [])[:3]:
        long_q_summary += f"  - PID {q.get('pid')} ({q.get('user')}, {q.get('state')} for {q.get('duration_seconds')}s, wait: {q.get('wait_event_type')}/{q.get('wait_event')}): {q.get('query_snippet')}\n"
    if not long_q_summary:
        long_q_summary = "  - None exceeding threshold.\n"

    prompt = f"""
Analyze the following AWS RDS PostgreSQL database health telemetry and provide an expert DBA diagnosis report.

### DATABASE METADATA:
- Database Name: {metrics.get('database', 'dba_ai')}
- Engine Version: {metrics.get('postgresql_version', 'PostgreSQL 15.16')}
- Calculated Health Score: {metrics.get('health_score', 100)} / 100 ({metrics.get('status', 'HEALTHY')})
- Active Backends: {metrics.get('connections', 0)} / {metrics.get('max_connections', 100)} connections
- Total Database Size: {metrics.get('database_size_gb', 0.0)} GB ({metrics.get('database_size_bytes', 0)} bytes)
- Buffer Cache Hit Ratio: {metrics.get('cache_hit_ratio', 99.0)}%
- Max Transaction ID (XID) Age: {metrics.get('xid_age', 0)} (Wraparound limit: 2.14B)

### CRITICAL OBSERVATIONS:
- Long-Running Queries (>5m): {metrics.get('long_running_queries', 0)}
- Active Blocking Sessions: {metrics.get('blocking_sessions', 0)}

### ACTIVE BLOCKING GRAPHS:
{blocking_summary}

### SLOW / ACTIVE QUERIES:
{long_q_summary}

### TOP TABLES BY DISK CONSUMPTION:
{top_tables_summary}

---
Please produce an organized, executive-grade Markdown assessment covering:
1. **Executive Health Summary & Risk Classification**
2. **Critical & Warning Findings** (Root causes, impacted workloads)
3. **Targeted Diagnostic SQL Queries** (To run in psql/IDE to inspect further)
4. **Immediate Remediation Steps** (Prioritized, non-destructive DBA actions)
5. **Long-Term Architectural & Preventative Measures** (Autovacuum tuning, indexing, CloudWatch alerts)
"""
    return prompt.strip()


def format_rag_prompt(user_query, current_metrics, retrieved_incidents):
    """
    Constructs a Retrieval-Augmented Generation prompt combining current metrics,
    historical DBA incident cases retrieved via pgvector, and the user's question.
    """
    
    incidents_context = ""
    for idx, inc in enumerate(retrieved_incidents, 1):
        similarity_pct = round((1.0 - float(inc.get('distance', 0.5))) * 100, 1)
        incidents_context += f"""
[Case #{idx}] {inc.get('title')} (Historical Similarity: {similarity_pct}%)
- Problem: {inc.get('problem')}
- Root Cause: {inc.get('root_cause')}
- Resolution: {inc.get('resolution')}
- Prevention: {inc.get('prevention')}
"""

    if not incidents_context:
        incidents_context = "No closely matching historical incidents found in pgvector knowledge base.\n"

    prompt = f"""
You are assisting a PostgreSQL DBA with a troubleshooting inquiry.

### USER INQUIRY:
"{user_query}"

### CURRENT DATABASE TELEMETRY:
- Database: {current_metrics.get('database', 'dba_ai')} ({current_metrics.get('postgresql_version', 'PostgreSQL 15.16')})
- Health Score: {current_metrics.get('health_score', 100)}% ({current_metrics.get('status', 'HEALTHY')})
- Size: {current_metrics.get('database_size_gb', 0)} GB
- Connections: {current_metrics.get('connections', 0)} / {current_metrics.get('max_connections', 100)}
- Cache Hit Ratio: {current_metrics.get('cache_hit_ratio', 99.0)}%
- Blocking Sessions: {current_metrics.get('blocking_sessions', 0)}
- Long-Running Queries: {current_metrics.get('long_running_queries', 0)}
- Max XID Age: {current_metrics.get('xid_age', 0)}

### HISTORICAL SIMILAR INCIDENTS (Retrieved from pgvector):
{incidents_context}

---
Based on the current telemetry and historical knowledge:
1. Explain the most probable causes for the user's inquiry.
2. Highlight any similarities with historical incidents and whether the historical solution applies.
3. Provide safe, copy-pasteable PostgreSQL diagnostic queries.
4. Recommend step-by-step mitigation actions.
"""
    return prompt.strip()
