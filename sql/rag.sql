-- ==============================================================================
-- AI PostgreSQL DBA Health Assistant - pgvector Similarity & RAG Queries
-- ==============================================================================

-- 1. Check pgvector extension version
SELECT extname, extversion 
FROM pg_extension 
WHERE extname = 'vector';

-- 2. Inspect Incidents Vector Table
SELECT id, title, created_at, (embedding IS NOT NULL) AS has_vector
FROM dba_ai.incidents;

-- 3. Semantic Similarity Search via Cosine Distance (<=>)
-- Example placeholder query (replace vector array with query embedding from Bedrock Titan)
/*
SELECT
    id,
    title,
    problem,
    root_cause,
    resolution,
    prevention,
    (embedding <=> '[0.012, -0.034, ...]'::vector) AS cosine_distance
FROM dba_ai.incidents
WHERE embedding IS NOT NULL
ORDER BY embedding <=> '[0.012, -0.034, ...]'::vector ASC
LIMIT 3;
*/

-- 4. Calculate Vector Index Efficiency & HNSW Parameters
SET hnsw.ef_search = 64; -- Increase for higher recall at search time
