# Service Contracts

**Status:** Agreed at the contract workshop (S1-02, 20 Oct 2026); approved by all three members at the Sprint 1 freeze (10 Nov 2026).

Update 1: Changes added in Sprint 2 with the auth service, the JWT keys and the Tier 1 tables. 23rd of November, 2026.

See `docs/architecture/architecture-event-flow.md` for the diagram, `docs/events/event-catalogue.md` for the events and `docs/services/` for one description per service.

---

## Services and Ports

| Service    | Port  | Role                                                  |
|------------|-------|-------------------------------------------------------|
| ingestion  | 8001  | Scrape MARP index page, discover and fetch PDFs       |
| indexing   | 8002  | Consume events, chunk, embed, store                   |
| retrieval  | 8003  | Vector search over pgvector                           |
| chat       | 8004  | Score threshold, prompt + LLM, return answer + citations, serves the web UI |
| extraction | 8005  | Extract per-page text from fetched PDFs               |
| auth       | 8006  | Accounts and JWT issuing (Tier 1, only `GET /health` so far) |
| postgres   | 5432  | pgvector store                                        |
| rabbitmq   | 5672  | AMQP broker                                           |
| rabbitmq   | 15672 | Management UI                                         |

All backend services expose `GET /health → {"status": "ok"}`.

---

## Source

MARP index page (scraped by ingestion, configured as `MARP_URL`):
`https://www.lancaster.ac.uk/academic-standards-and-quality/regulations-and-policies/manual-of-academic-regulations-and-procedures/`

- PDF links on the page are relative (`/media/lancaster-university/...pdf`) and must be resolved against the page URL.
- `robots.txt` (`https://www.lancaster.ac.uk/robots.txt`) sets `Crawl-delay: 5`. Ingestion reads this value and waits 5 seconds between requests to the site.

---

## Events

Event definitions (routing, envelope, `correlationId` rules and one schema per event) are in `docs/events/event-catalogue.md`.

---

## HTTP Endpoints

### Ingestion (`localhost:8001`)

**POST /discover**  
Scrapes the MARP index page and publishes one `DocumentDiscovered` per new PDF. Runs synchronously.

Request: _(no body)_

Response `200 OK`:
```json
{"published": 3}
```

Errors:
- `403` — `robots.txt` disallows the index page.
- `409` — another discovery run is in progress.

---

### Extraction (`localhost:8005`)

**GET /documents**  
Lists extracted documents.

Response `200 OK`:
```json
[
  {
    "doc_id": "9e107d9d372bb6826bd81d3542a419d6",
    "title": "Academic Integrity Regulations",
    "url": "https://www.lancaster.ac.uk/media/lancaster-university/content-assets/documents/student-based-services/asq/marp/Academic-Integrity-Regs.pdf",
    "page_count": 12,
    "extracted_at": "2026-10-20T12:01:00Z"
  }
]
```

An empty database returns `[]`.

Errors:
- `503` with `{"detail": "database unavailable"}` — Postgres cannot be reached. `/health` still answers `200`.

---

### Retrieval (`localhost:8003`)

**GET /search**

Query params: `q` (string, required, non-empty), `k` (int, default 5, min 1, max 20)

Optional header: `X-Correlation-ID` (UUID). Retrieval puts it in `RetrievalCompleted.correlationId`, or creates one if missing.

Response `200 OK`:
```json
{
  "query": "what is the late submission penalty?",
  "results": [
    {
      "chunk_id": "9e107d9d372bb6826bd81d3542a419d6-p3-c0",
      "doc_id": "9e107d9d372bb6826bd81d3542a419d6",
      "title": "Academic Integrity Regulations",
      "url": "https://www.lancaster.ac.uk/media/lancaster-university/content-assets/documents/student-based-services/asq/marp/Academic-Integrity-Regs.pdf",
      "page": 3,
      "text": "A 5-mark deduction per day...",
      "score": 0.91
    }
  ]
}
```

Results ordered by score descending, tie-break on `chunk_id` ascending. Ordering uses the exact distance; `score` in the response is rounded to 4 decimals, so two results can show the same score and not be in `chunk_id` order.

Errors:
- `422` — `q` missing or empty, or `k` outside 1–20.
- `503` with `{"detail": "database unavailable"}` — Postgres cannot be reached. `/health` still answers `200`.

---

### Chat (`localhost:8004`)

**GET /**  
Serves the web UI (static HTML and JS bundled with the chat service). The page calls `POST /chat` on the same origin, so no CORS is needed.

Response `200 OK`: `text/html`

**POST /chat**

Request:
```json
{"question": "what is the late submission penalty?"}
```

Response `200 OK`:
```json
{
  "answer": "A 5-mark deduction per day up to a maximum of 5 days...",
  "citations": [
    {
      "title": "Academic Integrity Regulations",
      "url": "https://www.lancaster.ac.uk/media/lancaster-university/content-assets/documents/student-based-services/asq/marp/Academic-Integrity-Regs.pdf",
      "page": 3
    }
  ]
}
```

Chat calls `GET /search` with `k=8` and the request's correlation ID in `X-Correlation-ID`. Citation markers `[n]` in `answer` are renumbered to match the order of `citations`.

Fallback (no source found):
```json
{
  "answer": "not certain / no source found",
  "citations": []
}
```

Chat returns the fallback without calling the LLM when retrieval returns no results or the top result's `score` is below `SCORE_THRESHOLD` (default `0.6`). It also returns the fallback when the LLM answer cites no valid source.

Errors:
- `422` — `question` missing or empty.
- `503` with `{"detail": "retrieval unavailable"}` — the call to retrieval failed or returned an error.
- `502` with `{"detail": "language model unavailable"}` — OpenRouter failed after retries, returned an empty answer, or `OPENROUTER_API_KEY` is not set.

---

### Auth (`localhost:8006`)

Only `GET /health` so far. Register, login, refresh and logout come with T1-3 and T1-4.

CORS: auth accepts browser calls only from the origins in `CORS_ALLOWED_ORIGINS` (the chat UI, `http://localhost:8004`), with credentials, methods `GET` and `POST`, and the `Authorization` and `Content-Type` headers. Other origins get no `Access-Control-Allow-Origin`, so the browser blocks them.

---

## Shared Conventions

- Embedding model: `BAAI/bge-small-en-v1.5` (384 dimensions, normalised), loaded locally by indexing (chunks) and retrieval (the `q` param). Both must use the same model. Retrieval adds the query prefix `Represent this sentence for searching relevant passages: ` before embedding `q`; chunks are embedded without it.
- All timestamps: ISO 8601 UTC
- `doc_id`: MD5 of URL (32 hex characters)
- `chunk_id`: `{doc_id}-p{page}-c{index}`
- Content-Type: `application/json` on all endpoints, except `GET /` (`text/html`) and the UI files under `/static/` on chat
- Fetched PDFs: shared Docker volume `pdfs`, mounted at `/data/pdfs` (read-write in ingestion, read-only in extraction), file name `{doc_id}.pdf`
- JWT keys: one RS256 key pair. Auth gets the private key and chat only the public key, both as Docker secrets under `/run/secrets/`. Created with `./scripts/gen-keys.sh`, never committed.

---

## Configuration

| Variable             | Used by    | Notes                                              |
|----------------------|------------|----------------------------------------------------|
| `OPENROUTER_API_KEY` | chat       | Secret, `.env` only                                |
| `OPENROUTER_MODEL`   | chat       | Model slug, default `nvidia/nemotron-3.5-super-vl:free` |
| `SCORE_THRESHOLD`    | chat       | Minimum top retrieval score before the LLM is called, default `0.6` |
| `RETRIEVAL_URL`      | chat       | Set by compose to `http://retrieval:8000`          |
| `MARP_URL`           | ingestion  | MARP index page to scrape                          |
| `USER_AGENT`         | ingestion  | Sent on every request to the MARP site and checked against `robots.txt` |
| `PDF_DIR`            | ingestion, extraction | Default `/data/pdfs` (the `pdfs` volume) |
| `CORS_ALLOWED_ORIGINS` | auth     | Comma-separated origins allowed to call auth from the browser, `*` is not allowed. Auth won't start without it |
| `JWT_PRIVATE_KEY_PATH` | auth     | Set by compose to `/run/secrets/jwt_private_key`. Auth won't start without a valid RSA key (2048 bits or more) |
| `JWT_PUBLIC_KEY_PATH`  | chat     | Set by compose to `/run/secrets/jwt_public_key`. Chat won't start without a valid RSA key (2048 bits or more) |
| `JWT_PRIVATE_KEY_FILE`, `JWT_PUBLIC_KEY_FILE` | compose, `scripts/gen-keys.sh` | Key files on the host, default `./keys/jwt_private.pem` and `./keys/jwt_public.pem`. Never committed. The script reads them from the shell, not `.env` |
| `DATABASE_URL`       | ingestion, extraction, indexing, retrieval, chat, auth | Built by compose from `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` |
| `RABBITMQ_URL`       | all six services | Built by compose from `RABBITMQ_DEFAULT_USER`, `RABBITMQ_DEFAULT_PASS`. Auth doesn't publish anything yet |

---

## Database Schema

Each table has one owning service. Other services must not write to it. `chunks` is created by `db/init/001_chunks.sql`, which also enables the pgvector extension. The other tables are created by their owner with `CREATE TABLE IF NOT EXISTS`: `documents` by extraction when its consumer starts (or on the first `GET /documents`), `discovered_documents` by ingestion on the first `POST /discover`, `users` and `refresh_tokens` by auth on startup, `conversations` and `messages` by chat on startup.

### `chunks` (owner: indexing; created by `db/init/001_chunks.sql`)

| Column      | Type          | Notes                                  |
|-------------|---------------|----------------------------------------|
| `chunk_id`  | `TEXT` PK     | `{doc_id}-p{page}-c{index}`            |
| `doc_id`    | `TEXT`        | MD5 of URL, indexed                    |
| `title`     | `TEXT`        |                                        |
| `url`       | `TEXT`        |                                        |
| `page`      | `INTEGER`     |                                        |
| `text`      | `TEXT`        | chunk content                          |
| `embedding` | `vector(384)` | HNSW index, cosine (`vector_cosine_ops`) |

Search must use the `<=>` operator for the index to be used.
`score = 1 - (embedding <=> query_vector)`.

Retrieval reads this table, read-only.

### `discovered_documents` (owner: ingestion)

| Column | Type      | Notes                                   |
|--------|-----------|-----------------------------------------|
| `url`  | `TEXT` PK | One row per PDF URL, written once the `DocumentDiscovered` event is confirmed |

### `documents` (owner: extraction)

| Column         | Type          | Notes                          |
|----------------|---------------|--------------------------------|
| `doc_id`       | `TEXT` PK     | MD5 of URL                     |
| `title`        | `TEXT`        |                                |
| `url`          | `TEXT`        |                                |
| `page_count`   | `INTEGER`     |                                |
| `pages`        | `JSONB`       | `[{"page": 1, "text": "..."}]` |
| `extracted_at` | `TIMESTAMPTZ` |                                |

### `users` (owner: auth)

| Column          | Type          | Notes                          |
|-----------------|---------------|--------------------------------|
| `id`            | `TEXT` PK     | UUID                           |
| `email`         | `TEXT`        | unique                         |
| `password_hash` | `TEXT`        | only the hash, never the password |
| `created_at`    | `TIMESTAMPTZ` | default `now()`                |

### `refresh_tokens` (owner: auth)

| Column       | Type          | Notes                                |
|--------------|---------------|--------------------------------------|
| `id`         | `TEXT` PK     | UUID                                 |
| `user_id`    | `TEXT`        | FK to `users(id)`, indexed           |
| `token_hash` | `TEXT`        | unique, only the hash is stored      |
| `expires_at` | `TIMESTAMPTZ` |                                      |
| `revoked_at` | `TIMESTAMPTZ` | null until the token is revoked      |
| `created_at` | `TIMESTAMPTZ` | default `now()`                      |

### `conversations` (owner: chat)

| Column       | Type          | Notes                                                       |
|--------------|---------------|-------------------------------------------------------------|
| `id`         | `TEXT` PK     | UUID                                                        |
| `user_id`    | `TEXT`        | JWT `sub`, no FK because `users` belongs to auth. Indexed with `created_at` |
| `title`      | `TEXT`        |                                                             |
| `created_at` | `TIMESTAMPTZ` | default `now()`                                             |

### `messages` (owner: chat)

| Column            | Type          | Notes                                                    |
|-------------------|---------------|----------------------------------------------------------|
| `id`              | `TEXT` PK     | UUID                                                     |
| `conversation_id` | `TEXT`        | FK to `conversations(id)`, `ON DELETE CASCADE`. Indexed with `created_at` |
| `role`            | `TEXT`        | `user` or `assistant`                                    |
| `content`         | `TEXT`        |                                                          |
| `citations`       | `JSONB`       | default `[]`                                             |
| `created_at`      | `TIMESTAMPTZ` | default `now()`                                          |

### Planned for Sprint 2

Tier 2 adds a semantic cache owned by chat. It doesn't exist yet, see [`design-tier2-rate-limit-cache.md`](../features/design-tier2-rate-limit-cache.md). This file is updated when it is built.
