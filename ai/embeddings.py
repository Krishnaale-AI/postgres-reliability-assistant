"""
Vector Embeddings Module for pgvector Knowledge Base.
Generates semantic embeddings using Amazon Titan Text Embeddings V2 via Amazon Bedrock.
"""

import json
import logging
import hashlib
from config import (
    AWS_REGION,
    AWS_PROFILE,
    BEDROCK_EMBEDDING_MODEL_ID,
    EMBEDDING_DIMENSION,
    DEMO_MODE,
)

logger = logging.getLogger("ai.embeddings")


def get_text_embedding(text, dimensions=None):
    """
    Generates a dense vector embedding for the input text using Amazon Bedrock.
    
    Args:
        text (str): Content string to embed
        dimensions (int, optional): Target vector dimension (e.g. 1024 or 1536)
    Returns:
        list[float]: Embedding vector
    """
    dim = dimensions or EMBEDDING_DIMENSION

    if DEMO_MODE:
        return _generate_deterministic_mock_embedding(text, dim)

    try:
        import boto3
        session = boto3.Session(region_name=AWS_REGION, profile_name=AWS_PROFILE)
        client = session.client("bedrock-runtime")

        # Request payload for Titan Embeddings V2
        body = json.dumps({
            "inputText": text,
            "dimensions": dim,
            "normalize": True,
        })

        response = client.invoke_model(
            modelId=BEDROCK_EMBEDDING_MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read().decode("utf-8"))
        embedding = response_body.get("embedding", [])
        return embedding

    except Exception as exc:
        logger.warning("Bedrock embedding generation failed: %s. Using deterministic fallback vector.", exc)
        return _generate_deterministic_mock_embedding(text, dim)


def _generate_deterministic_mock_embedding(text, dimensions):
    """
    Generates a deterministic normalized unit vector based on SHA-256 hash of text.
    Ensures repeatable similarity searches in demo/offline mode.
    """
    import math

    hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()
    
    vector = []
    for i in range(dimensions):
        byte_val = hash_bytes[i % len(hash_bytes)]
        offset = (i * 7) % 256
        val = ((byte_val + offset) % 256) / 255.0 - 0.5
        vector.append(val)

    # Normalize vector to unit length
    magnitude = math.sqrt(sum(x * x for x in vector))
    if magnitude > 0:
        vector = [x / magnitude for x in vector]

    return vector

