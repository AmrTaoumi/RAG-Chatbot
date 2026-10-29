# Service Contracts

**Status:** Draft — pending approval from all three members.

See `docs/architecture.md` for the diagram and `docs/services/` for one description per service.

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

Exchange: `rag.topic` (topic exchange, durable). All events are JSON.

### Routing

| Event               | Routing key           | Queue                 | Consumer            |
|---------------------|-----------------------|-----------------------|---------------------|
| DocumentDiscovered  | `document.discovered` | `ingestion.fetch`     | ingestion (fetcher) |
| DocumentFetched     | `document.fetched`    | `extraction.documents`| extraction          |
| DocumentExtracted   | `document.extracted`  | `indexing.documents`  | indexing            |
| ChunksIndexed       | `chunks.indexed`      | none yet              | none yet            |
| RetrievalCompleted  | `retrieval.completed` | none yet              | none yet            |
| AnswerGenerated     | `answer.generated`    | none yet              | none yet            |

Rules:
- Queues are durable. Both the consuming service and the publishing service declare the queue and binding on startup, using the names in the routing table (declaring is idempotent). This way an event published before its consumer has started is kept, not lost.
- Events with a consumer are published with `mandatory=True` and publisher confirms, so an unroutable message raises an error.
- `ChunksIndexed`, `RetrievalCompleted` and `AnswerGenerated` have no consumer and no queue yet. They are published with `mandatory=False`, so RabbitMQ drops them without an error until a consumer binds a queue.
- Messages are persistent (`delivery_mode=2`) with `content_type: application/json`.
- Consumers ack manually, after processing succeeds.
- Delivery is at-least-once, so every consumer must be idempotent (key: `doc_id`).

### DocumentDiscovered
Published by: ingestion  
Consumed by: ingestion (fetcher)

`doc_id` is not in the event. It is derived from `url` (MD5, see Shared Conventions).

```json
{
  "event": "DocumentDiscovered",
  "url": "https://www.lancaster.ac.uk/media/lancaster-university/content-assets/documents/student-based-services/asq/marp/Academic-Integrity-Regs.pdf",
  "title": "Academic Integrity Regulations",
  "discovered_at": "2026-10-20T12:00:00Z"
}
```

### DocumentFetched
Published by: ingestion (after downloading the PDF)  
Consumed by: extraction

The PDF is not carried in the event. It is written to the shared `pdfs` volume and the event gives its path.

```json
{
  "event": "DocumentFetched",
  "doc_id": "9e107d9d372bb6826bd81d3542a419d6",
  "url": "https://www.lancaster.ac.uk/media/lancaster-university/content-assets/documents/student-based-services/asq/marp/Academic-Integrity-Regs.pdf",
  "title": "Academic Integrity Regulations",
  "path": "/data/pdfs/9e107d9d372bb6826bd81d3542a419d6.pdf",
  "fetched_at": "2026-10-20T12:00:30Z"
}
```

### DocumentExtracted
Published by: extraction  
Consumed by: indexing

```json
{
  "event": "DocumentExtracted",
  "doc_id": "9e107d9d372bb6826bd81d3542a419d6",
  "url": "https://www.lancaster.ac.uk/media/lancaster-university/content-assets/documents/student-based-services/asq/marp/Academic-Integrity-Regs.pdf",
  "title": "Academic Integrity Regulations",
  "page_count": 12,
  "pages": [
    {"page": 1, "text": "..."},
    {"page": 2, "text": "..."}
  ],
  "extracted_at": "2026-10-20T12:01:00Z"
}
```

### ChunksIndexed
Published by: indexing  
Consumed by: none yet

```json
{
  "event": "ChunksIndexed",
  "doc_id": "9e107d9d372bb6826bd81d3542a419d6",
  "chunk_count": 34,
  "indexed_at": "2026-10-20T12:02:00Z"
}
```

### RetrievalCompleted
Published by: retrieval  
Consumed by: none yet

```json
{
  "event": "RetrievalCompleted",
  "query": "what is the late submission penalty?",
  "k": 5,
  "results": [
    {
      "chunk_id": "9e107d9d372bb6826bd81d3542a419d6-p3-c0",
      "doc_id": "9e107d9d372bb6826bd81d3542a419d6",
      "title": "Academic Integrity Regulations",
      "url": "https://www.lancaster.ac.uk/media/lancaster-university/content-assets/documents/student-based-services/asq/marp/Academic-Integrity-Regs.pdf",
      "page": 3,
      "score": 0.91
    }
  ],
  "retrieved_at": "2026-10-20T12:03:00Z"
}
```

### AnswerGenerated
Published by: chat  
Consumed by: none yet

```json
{
  "event": "AnswerGenerated",
  "question": "what is the late submission penalty?",
  "answer": "A 5-mark deduction per day up to a maximum of 5 days...",
  "citations": [
    {
      "title": "Academic Integrity Regulations",
      "url": "https://www.lancaster.ac.uk/media/lancaster-university/content-assets/documents/student-based-services/asq/marp/Academic-Integrity-Regs.pdf",
      "page": 3
    }
  ],
  "generated_at": "2026-10-20T12:03:05Z"
}
```

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

### Retrieval (`localhost:8003`)

**GET /search**

Query params: `q` (string, required), `k` (int, default 5)

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
