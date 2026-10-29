Service Name: retrieval (port 8003)

Responsibility:
  Runs vector similarity search over stored chunks and returns the top-k matches with scores and source metadata.

Data Owned:
  - None (read-only access to the `chunks` table owned by indexing)

API Endpoints:
  - [GET] /health - liveness check
  - [GET] /search - search chunks by query `q` (required) and result count `k` (default 5); results ordered by score descending, ties broken by `chunk_id` ascending

Communicates With:
  - chat (REST, answers `GET /search` calls)
  - postgres (SQL, reads chunks using the `<=>` cosine operator; `score = 1 - distance`)
  - logging (Events, publishes `RetrievalCompleted`)
