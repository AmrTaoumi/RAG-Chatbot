Service Name: indexing (port 8002)

Responsibility:
  Consumes extracted documents, splits each page into ~200-token chunks with 40-token overlap (tiktoken `cl100k_base`), embeds them with `BAAI/bge-small-en-v1.5` (normalised, no query prefix), and stores them in pgvector. Re-indexing a document replaces its chunks.

Data Owned:
  - `chunks` table (`chunk_id`, `doc_id`, `title`, `url`, `page`, `text`, 384-dim `embedding` with HNSW cosine index)

API Endpoints:
  - [GET] /health - liveness check

Communicates With:
  - extraction (Events, consumes `DocumentExtracted` from queue `indexing.documents`)
  - postgres (SQL, writes chunks and embeddings; idempotent on `doc_id`)
  - embedding model (local, indexing loads `BAAI/bge-small-en-v1.5` itself; same model as retrieval, so scores are comparable)
  - RabbitMQ (Events, publishes `ChunksIndexed`; no consumer yet)
  - retrieval (indirect, via the shared `chunks` table that retrieval reads)
