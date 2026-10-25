-- {dim} is replaced with the embedding dimension (an int) before this runs.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    lang text NOT NULL CHECK (lang IN ('ar', 'en')),
    sha256 text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id bigserial PRIMARY KEY,
    document_id uuid NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    idx int NOT NULL,
    location text NOT NULL,
    content text NOT NULL,
    fts_config regconfig NOT NULL,
    embedding vector({dim}) NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector(fts_config, content)) STORED,
    UNIQUE (document_id, idx)
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
