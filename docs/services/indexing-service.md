Service Name: indexing (port 8002)

Responsibility:
  Consumes extracted documents, splits each page into overlapping ~200-token chunks, embeds them with all-MiniLM-L6-v2, and stores them in pgvector.

Data Owned:
  - `chunks` table (`chunk_id`, `doc_id`, `title`, `url`, `page`, `text`, 384-dim `embedding` with HNSW cosine index)

API Endpoints:
  - [GET] /health - liveness check
  - No other HTTP endpoints; the service is driven by events

Communicates With:
  - ingestion (Events, consumes `DocumentExtracted` from queue `indexing.documents`)
  - postgres (SQL, writes chunks and embeddings; idempotent on `doc_id`)
  - logging (Events, publishes `ChunksIndexed`)
  - retrieval (indirect, via the shared `chunks` table that retrieval reads)
