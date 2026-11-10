Service Name: retrieval (port 8003)

Responsibility:
  Runs vector similarity search over stored chunks and returns the top-k matches with scores and source metadata.

Data Owned:
  - None (read-only access to the `chunks` table owned by indexing)

API Endpoints:
  - [GET] /health - liveness check
  - [GET] /search - search chunks by query `q` (required) and result count `k` (default 5, 1–20); optional `X-Correlation-ID` header (a new one is created if missing); results ordered by score descending, ties broken by `chunk_id` ascending, `score` rounded to 4 decimals. Errors: `422` bad `q` or `k`, `503` database unavailable

Communicates With:
  - chat (REST, answers `GET /search` calls)
  - postgres (SQL, reads chunks using the `<=>` cosine operator; `score = 1 - distance`)
  - embedding model (local, retrieval loads `BAAI/bge-small-en-v1.5` itself to embed `q`, normalised, with the query prefix "Represent this sentence for searching relevant passages: "; same model as indexing)
  - RabbitMQ (Events, publishes `RetrievalCompleted`; no consumer yet)
