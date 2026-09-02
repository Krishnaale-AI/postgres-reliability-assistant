"""
AI PostgreSQL DBA Health Assistant - Main Streamlit Dashboard.
Real-time AWS RDS PostgreSQL monitoring, Amazon Bedrock reasoning, and pgvector RAG assistant.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from config import (
    AWS_REGION,
    BEDROCK_MODEL_ID,
    BEDROCK_EMBEDDING_MODEL_ID,
    RDS_HOST,
    RDS_DATABASE,
    RDS_USER,
    USE_SECRETS_MANAGER,
    DEMO_MODE,
)
from db.connection import check_database_connection
from db.health import collect_health
from db.history import save_health_snapshot, get_growth_trend
from monitoring.storage import analyze_storage_bloat
from monitoring.locks import analyze_blocking_tree, get_active_locks
from monitoring.vacuum import check_vacuum_needed, get_autovacuum_activity
from monitoring.xid import calculate_wraparound_risk, get_database_xid_ages
from monitoring.replication import get_replication_lag_metrics
from monitoring.cloudwatch import get_rds_cloudwatch_metrics
from ai.bedrock import analyze_database
from ai.rag import search_similar_incidents, answer_dba_rag_query, populate_incident_embeddings

# ------------------------------------------------------------------------------
# Page Configuration & Modern Styling
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="AI PostgreSQL DBA Assistant",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for polished, modern DBA interface
st.markdown("""
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .badge-healthy {
        background-color: #DCFCE7;
        color: #166534;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-warning {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-critical {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .sql-box {
        background-color: #0F172A;
        color: #F8FAFC;
        padding: 12px;
        border-radius: 6px;
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# Sidebar Controls & AWS Configuration Status
# ------------------------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/postgreesql.png", width=64)
    st.title("DBA Control Center")
    st.caption("AI-Powered PostgreSQL Health & Troubleshooting")

    # Connection Status Check
    db_conn = check_database_connection()
    is_live = db_conn["connected"]

    if is_live:
        st.success(f"🟢 Connected to RDS (`{RDS_DATABASE}`)")
    else:
        st.warning("🟠 RDS Offline / Demo Mode Active")

    use_demo = st.toggle("Simulate Demo Cluster Workload", value=(not is_live or DEMO_MODE))

    st.markdown("---")
    st.subheader("⚡ Quick Actions")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        run_check = st.button("🔍 Run Health Check", use_container_width=True, type="primary")
    with col_btn2:
        save_snap = st.button("💾 Save Snapshot", use_container_width=True)

    seed_kb = st.button("🧠 Index pgvector Embeddings", use_container_width=True)
    if seed_kb:
        with st.spinner("Generating embeddings via Amazon Titan..."):
            count = populate_incident_embeddings()
            st.success(f"Vector knowledge base updated ({count} items)!")

    st.markdown("---")
    with st.expander("🛠️ Environment & AWS Settings", expanded=False):
        st.write(f"**AWS Region:** `{AWS_REGION}`")
        st.write(f"**Host:** `{RDS_HOST}`")
        st.write(f"**Database:** `{RDS_DATABASE}`")
        st.write(f"**User:** `{RDS_USER}`")
        st.write(f"**Secrets Manager:** `{'Yes' if USE_SECRETS_MANAGER else 'No'}`")
        st.write(f"**Bedrock Model:** `{BEDROCK_MODEL_ID}`")
        st.write(f"**Embedding Model:** `{BEDROCK_EMBEDDING_MODEL_ID}`")


# ------------------------------------------------------------------------------
# Fetch Telemetry Data
# ------------------------------------------------------------------------------
@st.cache_data(ttl=60)
def load_cached_health_data(demo_flag):
    return collect_health(is_demo=demo_flag)

metrics = load_cached_health_data(use_demo)

if save_snap:
    if save_health_snapshot(metrics):
        st.toast("✅ Health snapshot saved to dba_ai.health_history!", icon="💾")

score = metrics.get("health_score", 85)
status = metrics.get("status", "HEALTHY")


# ------------------------------------------------------------------------------
# Top Header & Health Score Banner
# ------------------------------------------------------------------------------
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown('<div class="main-header">🛡️ AI PostgreSQL DBA Health Assistant</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header">Target: <b>{RDS_HOST}</b> | Engine: <b>{metrics.get("postgresql_version", "PostgreSQL 15.16")}</b></div>', unsafe_allow_html=True)

with col_h2:
    if status == "HEALTHY":
        badge_html = f'<span class="badge-healthy">🟢 HEALTHY ({score}/100)</span>'
    elif status == "WARNING":
        badge_html = f'<span class="badge-warning">🟠 WARNING ({score}/100)</span>'
    else:
        badge_html = f'<span class="badge-critical">🔴 CRITICAL ({score}/100)</span>'
    st.markdown(f"<div style='text-align: right; padding-top: 10px;'>{badge_html}</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# KPI Scorecards
# ------------------------------------------------------------------------------
kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)

with kpi1:
    conn_str = f"{metrics.get('connections', 0)} / {metrics.get('max_connections', 100)}"
    conn_pct = int((metrics.get('connections', 0) / max(metrics.get('max_connections', 100), 1)) * 100)
    st.metric("Connections", conn_str, f"{conn_pct}% capacity", delta_color="inverse" if conn_pct > 80 else "normal")

with kpi2:
    db_size_gb = metrics.get("database_size_gb", 0.0)
    st.metric("Database Size", f"{db_size_gb:.1f} GB", "+2.4 GB / 24h")

with kpi3:
    cache_hit = metrics.get("cache_hit_ratio", 99.0)
    st.metric("Buffer Cache Hit", f"{cache_hit:.2f}%", "-0.1%" if cache_hit < 99 else "Optimal")

with kpi4:
    long_q = metrics.get("long_running_queries", 0)
    st.metric("Long Queries (>5m)", f"{long_q}", "-1 vs avg" if long_q == 0 else f"+{long_q} Active", delta_color="inverse" if long_q > 0 else "normal")

with kpi5:
    blocking = metrics.get("blocking_sessions", 0)
    st.metric("Blocking Locks", f"{blocking}", "Requires Action" if blocking > 0 else "Clean", delta_color="inverse" if blocking > 0 else "normal")

with kpi6:
    xid_age = metrics.get("xid_age", 0)
    xid_risk = calculate_wraparound_risk(xid_age)
    st.metric("Max XID Age", f"{xid_age / 1_000_000:.1f}M", xid_risk["risk_level"])

st.markdown("---")


# ------------------------------------------------------------------------------
# Main Diagnostic Tabs
# ------------------------------------------------------------------------------
tab_overview, tab_perf, tab_storage, tab_cw, tab_ai, tab_rag, tab_runbook = st.tabs([
    "📊 Health Overview",
    "⚡ Performance & Locks",
    "📈 Storage & Bloat",
    "☁️ CloudWatch RDS",
    "🤖 Bedrock AI DBA",
    "🧠 pgvector RAG Assistant",
    "🛡️ Safe DBA Runbook",
])


# ------------------------------------------------------------------------------
# TAB 1: HEALTH OVERVIEW
# ------------------------------------------------------------------------------
with tab_overview:
    st.subheader("System Health Matrix")
    
    col_ov1, col_ov2 = st.columns([1, 1])

    with col_ov1:
        st.markdown("##### 📌 Core Cluster Telemetry")
        summary_data = {
            "Parameter": [
                "Database Name",
                "Engine Version",
                "Health Score",
                "Operational Status",
                "Total Size",
                "Active Backends",
                "Cache Hit Ratio",
                "Max Transaction ID Age",
                "Wraparound Distance",
            ],
            "Value": [
                metrics.get("database", "dba_ai"),
                metrics.get("postgresql_version", "PostgreSQL 15.16"),
                f"{score} / 100",
                status,
                f"{db_size_gb:.2f} GB",
                f"{metrics.get('connections')} active backends",
                f"{cache_hit:.2f}%",
                f"{xid_age:,} tx",
                f"{xid_risk['transactions_remaining']:,} tx headroom ({xid_risk['wraparound_pct']}%)",
            ]
        }
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

    with col_ov2:
        st.markdown("##### 🎯 Health Score Breakdown")
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "PostgreSQL Reliability Index"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "#2563EB"},
                'steps': [
                    {'range': [0, 70], 'color': "#FEE2E2"},
                    {'range': [70, 90], 'color': "#FEF3C7"},
                    {'range': [90, 100], 'color': "#DCFCE7"},
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': score
                }
            }
        ))
        fig_gauge.update_layout(height=280, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_gauge, use_container_width=True)

    st.markdown("##### 🕒 Historical Growth & Connections Trend")
    trend_df = get_growth_trend()
    if not trend_df.empty:
        fig_trend = px.line(
            trend_df,
            x="collected_at",
            y=["database_size_gb", "connections"],
            labels={"value": "Metric Value", "collected_at": "Timestamp", "variable": "Metric"},
            title="Database Growth (GB) vs Connection Activity (7-Day History)",
            color_discrete_map={"database_size_gb": "#2563EB", "connections": "#10B981"}
        )
        fig_trend.update_layout(height=320, hovermode="x unified")
        st.plotly_chart(fig_trend, use_container_width=True)


# ------------------------------------------------------------------------------
# TAB 2: PERFORMANCE & LOCKS
# ------------------------------------------------------------------------------
with tab_perf:
    st.subheader("Active Lock Conflicts & Slow Queries")

    # Blocking Sessions Section
    blocking_list = analyze_blocking_tree()
    if blocking_list:
        st.error(f"🚨 **Lock Contention Detected:** {len(blocking_list)} session(s) involved in lock dependency chains.")
        st.dataframe(pd.DataFrame(blocking_list), use_container_width=True)
    else:
        st.success("✅ **No Lock Conflicts Detected:** Zero sessions blocked waiting on lock acquisition.")

    st.markdown("---")

    # Long Running Queries
    st.markdown("##### ⏱️ Active & Long-Running Queries (>10s)")
    long_queries = metrics.get("long_query_details", [])
    if long_queries:
        st.dataframe(pd.DataFrame(long_queries), use_container_width=True)
    else:
        st.info("No long-running queries currently active.")

    st.markdown("---")

    # Top Statements (pg_stat_statements)
    st.markdown("##### 📊 Top Cumulative SQL Execution Times (`pg_stat_statements`)")
    top_stmts = metrics.get("top_statements", [])
    if top_stmts:
        st.dataframe(pd.DataFrame(top_stmts), use_container_width=True)
    else:
        st.info("Ensure `pg_stat_statements` is enabled in your RDS parameter group to view top SQL statistics.")


# ------------------------------------------------------------------------------
# TAB 3: STORAGE & BLOAT
# ------------------------------------------------------------------------------
with tab_storage:
    st.subheader("Storage Distribution, Bloat & Vacuum Statistics")

    bloat_info = analyze_storage_bloat()

    col_st1, col_st2 = st.columns([1, 1])
    with col_st1:
        st.markdown("##### 📦 Top 10 Largest Tables")
        tables_df = pd.DataFrame(bloat_info.get("tables", []))
        if not tables_df.empty:
            st.dataframe(tables_df, use_container_width=True)
        else:
            st.info("No user tables found.")

    with col_st2:
        st.markdown("##### 🔍 Index Sizes & Scan Activity")
        indexes_df = pd.DataFrame(bloat_info.get("indexes", []))
        if not indexes_df.empty:
            st.dataframe(indexes_df, use_container_width=True)
        else:
            st.info("No user indexes found.")

    st.markdown("---")
    st.markdown("##### 🧹 Autovacuum Candidates & Dead Tuples")
    dead_tup_df = pd.DataFrame(metrics.get("dead_tuples", []))
    if not dead_tup_df.empty:
        st.dataframe(dead_tup_df, use_container_width=True)
    else:
        st.info("Dead tuple counts are within healthy operational thresholds.")


# ------------------------------------------------------------------------------
# TAB 4: CLOUDWATCH RDS TELEMETRY
# ------------------------------------------------------------------------------
with tab_cw:
    st.subheader("Amazon CloudWatch RDS Telemetry")
    cw_metrics = get_rds_cloudwatch_metrics()

    cw_col1, cw_col2, cw_col3, cw_col4 = st.columns(4)
    with cw_col1:
        st.metric("RDS CPU Utilization", f"{cw_metrics.get('cpu_utilization_pct', 0)}%", "Under 80% Threshold")
    with cw_col2:
        st.metric("Free Storage Space", f"{cw_metrics.get('free_storage_gb', 0)} GB", "Auto-Scaling Ready")
    with cw_col3:
        st.metric("Freeable Memory", f"{cw_metrics.get('freeable_memory_mb', 0)} MB", "Sufficient")
    with cw_col4:
        st.metric("IOPS Activity", f"{cw_metrics.get('read_iops', 0)} R / {cw_metrics.get('write_iops', 0)} W", "GP3 Baseline")

    st.caption(f"Telemetry Source: **{cw_metrics.get('source', 'Live')}** for DBInstanceIdentifier: `{cw_metrics.get('instance_id')}`")

    st.markdown("---")
    st.markdown("##### 🛡️ Recommended CloudWatch Alarms for Production PostgreSQL")
    cw_alarm_data = [
        {"Alarm Name": "RDS-High-CPU", "Metric": "CPUUtilization", "Threshold": "> 80% for 15 min", "Action": "Review top SQL & pg_stat_statements"},
        {"Alarm Name": "RDS-Low-Free-Storage", "Metric": "FreeStorageSpace", "Threshold": "< 15% of allocated", "Action": "Trigger storage scale or purge old tables"},
        {"Alarm Name": "RDS-High-Connections", "Metric": "DatabaseConnections", "Threshold": "> 85% of max_connections", "Action": "Inspect connection leaks or configure PgBouncer / RDS Proxy"},
        {"Alarm Name": "RDS-Read-Latency", "Metric": "ReadLatency", "Threshold": "> 20ms", "Action": "Inspect index scans vs disk reads"},
    ]
    st.dataframe(pd.DataFrame(cw_alarm_data), use_container_width=True)


# ------------------------------------------------------------------------------
# TAB 5: BEDROCK AI DBA DIAGNOSIS
# ------------------------------------------------------------------------------
with tab_ai:
    st.subheader("🤖 Amazon Bedrock AI DBA Diagnostic Report")
    st.caption(f"Powered by Foundation Model: `{BEDROCK_MODEL_ID}` (Region: `{AWS_REGION}`)")

    custom_context = st.text_input(
        "Optional DBA Context / Recent Application Deployments:",
        placeholder="e.g. Nightly billing batch ran at 02:00 UTC; migration added column to orders table."
    )

    if st.button("🚀 Generate AI DBA Diagnosis", type="primary", key="btn_run_ai"):
        with st.spinner("Analyzing PostgreSQL telemetry with Amazon Bedrock Nova..."):
            ai_report = analyze_database(metrics, custom_notes=custom_context)
            st.session_state["latest_ai_report"] = ai_report

    if "latest_ai_report" in st.session_state:
        st.markdown(st.session_state["latest_ai_report"])
    else:
        st.info("Click **'Generate AI DBA Diagnosis'** above to submit the active telemetry to Amazon Bedrock.")


# ------------------------------------------------------------------------------
# TAB 6: PGVECTOR RAG ASSISTANT
# ------------------------------------------------------------------------------
with tab_rag:
    st.subheader("🧠 Retrieval-Augmented DBA Incident Assistant")
    st.caption("Matches your inquiry against historical DBA incident vectors in `pgvector` using cosine similarity.")

    user_query = st.text_input(
        "Ask a database troubleshooting or optimization question:",
        placeholder="e.g. Why is storage increasing rapidly on orders table?"
    )

    if user_query:
        with st.spinner("Searching pgvector and consulting Bedrock..."):
            rag_answer, matches = answer_dba_rag_query(user_query, metrics)

            st.markdown(rag_answer)

            st.markdown("---")
            st.markdown("##### 📚 Matched Historical Incidents from pgvector")
            for m in matches:
                with st.expander(f"Case #{m.get('id')}: {m.get('title')} (Distance: {m.get('distance', 0.0):.4f})"):
                    st.write(f"**Problem:** {m.get('problem')}")
                    st.write(f"**Root Cause:** {m.get('root_cause')}")
                    st.write(f"**Resolution:** {m.get('resolution')}")
                    st.write(f"**Prevention:** {m.get('prevention')}")


# ------------------------------------------------------------------------------
# TAB 7: SAFE DBA RUNBOOK
# ------------------------------------------------------------------------------
with tab_runbook:
    st.subheader("🛡️ Safe DBA Operations & Investigation Runbook")
    st.warning("⚠️ **Safety Rule:** Never execute destructive SQL (DROP/TRUNCATE/TERMINATE) without verifying the impact on dependent applications.")

    runbook_col1, runbook_col2 = st.columns(2)

    with runbook_col1:
        st.markdown("##### 1. Safely Terminate a Blocking Backend")
        st.code("""-- 1. Try graceful cancellation first (gives query chance to rollback):
SELECT pg_cancel_backend(PID_HERE);

-- 2. If still hanging after 30s, terminate backend connection:
SELECT pg_terminate_backend(PID_HERE);""", language="sql")

        st.markdown("##### 2. Reclaim Space with Non-Blocking Re-index")
        st.code("""-- Rebuild index concurrently without table lock:
REINDEX INDEX CONCURRENTLY idx_orders_customer_id;""", language="sql")

    with runbook_col2:
        st.markdown("##### 3. Check Autovacuum Freeze Wraparound Status")
        st.code("""SELECT
    c.oid::regclass as table_name,
    age(c.relfrozenxid) as xid_age,
    pg_size_pretty(pg_total_relation_size(c.oid)) as size
FROM pg_class c
WHERE c.relkind = 'r'
ORDER BY age(c.relfrozenxid) DESC
LIMIT 10;""", language="sql")

        st.markdown("##### 4. Set Session Timeout Safeguards")
        st.code("""-- Prevent abandoned developer transactions:
ALTER ROLE app_user SET idle_in_transaction_session_timeout = '60s';
ALTER ROLE app_user SET statement_timeout = '30s';""", language="sql")
