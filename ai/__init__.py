"""
AI & RAG Package for AI PostgreSQL DBA Health Assistant.
Integrates Amazon Bedrock (Nova Lite/Pro/Claude), Titan Embeddings, and pgvector.
"""

from .bedrock import analyze_database, invoke_bedrock_chat
from .embeddings import get_text_embedding
from .rag import search_similar_incidents, answer_dba_rag_query, populate_incident_embeddings
from .prompts import SYSTEM_PROMPT_SENIOR_DBA, format_health_prompt, format_rag_prompt

__all__ = [
    "analyze_database",
    "invoke_bedrock_chat",
    "get_text_embedding",
    "search_similar_incidents",
    "answer_dba_rag_query",
    "populate_incident_embeddings",
    "SYSTEM_PROMPT_SENIOR_DBA",
    "format_health_prompt",
    "format_rag_prompt",
]
