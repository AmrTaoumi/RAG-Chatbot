Service Name: chat (port 8004)

Responsibility:
  Builds a prompt from retrieved chunks, calls the LLM, and returns an answer with citations (or a fallback when no source supports an answer). Caches answers for similar questions.

Data Owned:
  - `semantic_cache` table (`question`, `embedding`, `answer`, `citations`, `created_at`, `expires_at`); rows expire after `CACHE_TTL_SECONDS` (default 24 hours)

API Endpoints:
  - [GET] /health - liveness check
  - [GET] / - serves the web UI (static page bundled with this service; it calls `POST /chat` on the same origin)
  - [POST] /chat - answer a `question`; returns `answer` plus `citations` (title, url, page), or "I'm not certain based on the available documents." with empty citations

Communicates With:
  - Web UI (REST, the browser loads `GET /` and calls `POST /chat`)
  - retrieval (REST, `GET /search` to fetch relevant chunks)
  - OpenRouter LLM (REST, generates the answer from the prompt; model set by `OPENROUTER_MODEL`)
  - postgres (SQL, reads and writes `semantic_cache`)
  - embedding model (local, chat loads all-MiniLM-L6-v2 itself to embed each question for the cache lookup; same model as indexing, so the vectors are comparable)
  - RabbitMQ (Events, publishes `AnswerGenerated`; no consumer yet)
