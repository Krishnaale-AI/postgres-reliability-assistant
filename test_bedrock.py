"""
Diagnostic CLI Script to Verify Amazon Bedrock & pgvector Integration.
Tests Amazon Nova Lite (Bedrock Converse API) and Titan Text Embeddings V2.
"""

import sys
import logging

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import AWS_REGION, BEDROCK_MODEL_ID, BEDROCK_EMBEDDING_MODEL_ID, EMBEDDING_DIMENSION
from ai.bedrock import analyze_database
from ai.embeddings import get_text_embedding
from ai.rag import search_similar_incidents

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main():
    print("=" * 70)
    print(" [AI-DBA] AI PostgreSQL DBA Assistant - Amazon Bedrock & AI Diagnostic")
    print("=" * 70)
    print(f"AWS Region:             {AWS_REGION}")
    print(f"Bedrock Reasoning Model: {BEDROCK_MODEL_ID}")
    print(f"Bedrock Embedding Model: {BEDROCK_EMBEDDING_MODEL_ID}")
    print(f"Embedding Dimension:     {EMBEDDING_DIMENSION}")
    print("-" * 70)

    print("\n1. Testing Amazon Titan Text Embeddings...")
    sample_text = "Database storage expanded rapidly due to large batch ETL insert."
    try:
        vector = get_text_embedding(sample_text)
        print(f"✅ Embedding generated successfully!")
        print(f"   - Vector Length: {len(vector)} dimensions")
        print(f"   - Sample values: [{vector[0]:.4f}, {vector[1]:.4f}, {vector[2]:.4f}, ...]")
    except Exception as exc:
        print(f"⚠️ Embedding test error: {exc}")

    print("\n2. Testing Historical Incident Similarity Retrieval...")
    try:
        matches = search_similar_incidents("Why is my database storage increasing?", limit=2)
        print(f"✅ Found {len(matches)} matching incident(s):")
        for m in matches:
            dist = m.get("distance", 0.0)
            print(f"   - [Distance {dist:.4f}] #{m.get('id')} {m.get('title')}")
    except Exception as exc:
        print(f"⚠️ Retrieval error: {exc}")

    print("\n3. Testing Amazon Bedrock Converse API (Nova Lite Reasoning)...")
    mock_metrics = {
        "database": "dba_ai",
        "postgresql_version": "PostgreSQL 15.16 on AWS RDS",
        "connections": 35,
        "max_connections": 200,
        "database_size_bytes": 485321000000,
        "database_size_gb": 452.0,
        "long_running_queries": 2,
        "blocking_sessions": 1,
        "xid_age": 14250000,
        "cache_hit_ratio": 99.15,
        "status": "WARNING",
        "health_score": 75,
        "top_tables": [
            {"schemaname": "public", "table_name": "orders", "total_size_pretty": "182 GB", "table_size_pretty": "120 GB", "index_size_pretty": "62 GB"}
        ],
        "blocking_details": [
            {"blocked_pid": 14205, "blocking_pid": 13990, "blocked_user": "app_worker", "blocking_user": "batch_loader", "blocked_duration_sec": 380.5, "blocked_query": "UPDATE orders SET ...", "blocking_query": "LOCK TABLE orders IN EXCLUSIVE MODE;"}
        ],
        "long_query_details": [
            {"pid": 14205, "user": "app_worker", "state": "active", "duration_seconds": 380.5, "wait_event_type": "Lock", "wait_event": "relation", "query_snippet": "UPDATE orders ..."}
        ]
    }

    try:
        print("   Sending DBA health prompt to Bedrock...")
        analysis = analyze_database(mock_metrics)
        print("✅ Bedrock response received successfully!\n")
        print("=" * 70)
        print(analysis[:600] + "\n... [Analysis continues in Streamlit UI]")
        print("=" * 70)
    except Exception as exc:
        print(f"❌ Bedrock test error: {exc}")

    print("\nDiagnostic complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
