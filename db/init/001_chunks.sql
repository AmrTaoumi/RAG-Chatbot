CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id   TEXT PRIMARY KEY,
    doc_id     TEXT NOT NULL,
    title      TEXT NOT NULL,
    url        TEXT NOT NULL,
    page       INTEGER NOT NULL,
    text       TEXT NOT NULL,
    embedding  vector(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS chunks_doc_id_idx ON chunks (doc_id);

