-- Runs on first pgvector container init. Enables the vector extension and creates the
-- chunks table for semantic search. Also creates a matching test database.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS transcript_chunks (
    id           TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    meeting_id   TEXT NOT NULL,
    client_id    TEXT NOT NULL,
    chunk_index  INTEGER NOT NULL,
    content      TEXT NOT NULL,
    embedding    vector(384) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Filter-by-tenant (every query is tenant-scoped) and by meeting (idempotent re-index).
CREATE INDEX IF NOT EXISTS ix_chunks_tenant ON transcript_chunks (tenant_id);
CREATE INDEX IF NOT EXISTS ix_chunks_meeting ON transcript_chunks (meeting_id);
-- Approximate nearest-neighbour index (cosine). ivfflat needs ANALYZE/data to be effective;
-- fine for the learning scale.
CREATE INDEX IF NOT EXISTS ix_chunks_embedding
    ON transcript_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
