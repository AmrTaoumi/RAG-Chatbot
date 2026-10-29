# Service Contracts

**Status:** Draft — pending approval from all three members.

See `docs/architecture-event-flow.md` for the diagram, `docs/events/event-catalogue.md` for the events and `docs/services/` for one description per service.

---

## Services and Ports

| Service    | Port  | Role                                                  |
|------------|-------|-------------------------------------------------------|
| ingestion  | 8001  | Scrape MARP index page, discover and fetch PDFs       |
| indexing   | 8002  | Consume events, chunk, embed, store                   |
| retrieval  | 8003  | Vector search over pgvector                           |
| chat       | 8004  | Prompt + LLM, semantic cache, return answer + citations, serves the web UI |
| extraction | 8005  | Extract per-page text from fetched PDFs               |
| postgres   | 5432  | pgvector store                                        |
| rabbitmq   | 5672  | AMQP broker                                           |
| rabbitmq   | 15672 | Management UI                                         |

All backend services expose `GET /health → {"status": "ok"}`.

---

## Source

MARP index page (scraped by ingestion, configured as `MARP_URL`):
`https://www.lancaster.ac.uk/academic-standards-and-quality/regulations-and-policies/manual-of-academic-regulations-and-procedures/`

- PDF links on the page are relative (`/media/lancaster-university/...pdf`) and must be resolved against the page URL.
- `robots.txt` (`https://www.lancaster.ac.uk/robots.txt`) sets `Crawl-delay: 5`. Ingestion waits at least 5 seconds between requests to the site.

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

---

### Indexing (`localhost:8002`)

**GET /stats**  
Counts what is stored in `chunks`.

Response `200 OK`:
```json
{"documents": 16, "chunks": 534}
```

`documents` is the number of distinct `doc_id` values and `chunks` is the row count.

---

### Retrieval (`localhost:8003`)

**GET /search**

Query params: `q` (string, required), `k` (int, default 5)

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

Results ordered by score descending, tie-break on `chunk_id` ascending.

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

Fallback (no source found):
```json
{
  "answer": "I'm not certain based on the available documents.",
  "citations": []
}
```

---

## Shared Conventions

- Embedding model: `all-MiniLM-L6-v2` (384 dimensions), loaded locally by indexing (chunks), retrieval (the `q` param) and chat (cache lookups). All three must use the same model.
- All timestamps: ISO 8601 UTC
- `doc_id`: MD5 of URL (32 hex characters)
- `chunk_id`: `{doc_id}-p{page}-c{index}`
- Content-Type: `application/json` on all endpoints, except `GET /` on chat (`text/html`)
- Fetched PDFs: shared Docker volume `pdfs`, mounted at `/data/pdfs` (read-write in ingestion, read-only in extraction), file name `{doc_id}.pdf`

---

## Configuration

| Variable             | Used by    | Notes                                              |
|----------------------|------------|----------------------------------------------------|
| `OPENROUTER_API_KEY` | chat       | Secret, `.env` only                                |
| `OPENROUTER_MODEL`   | chat       | Model slug. Not chosen yet.                        |
| `CACHE_TTL_SECONDS`  | chat       | Semantic cache lifetime, default `86400` (24 hours) |

---

## Database Schema

Each table has one owning service. Other services must not write to it. `chunks` is created by `db/init/001_chunks.sql`, which also enables the pgvector extension. The other tables are created by their owner on startup (`CREATE TABLE IF NOT EXISTS`), as ingestion already does for `discovered_documents`.

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

### `semantic_cache` (owner: chat)

| Column       | Type           | Notes                                              |
|--------------|----------------|----------------------------------------------------|
| `id`         | `BIGSERIAL` PK |                                                    |
| `question`   | `TEXT`         |                                                    |
| `embedding`  | `vector(384)`  | Embedding of the question, same model as `chunks`  |
| `answer`     | `TEXT`         |                                                    |
| `citations`  | `JSONB`        | Same shape as the `/chat` response                 |
| `created_at` | `TIMESTAMPTZ`  |                                                    |
| `expires_at` | `TIMESTAMPTZ`  | `created_at + CACHE_TTL_SECONDS`. Expired rows are ignored. |
