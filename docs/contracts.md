# Service Contracts

**Status:** Draft — pending approval from all three members.

---

## Services and Ports

| Service    | Port | Role                                      |
|------------|------|-------------------------------------------|
| ingestion  | 8001 | Scrape MARP, fetch PDFs, extract text     |
| indexing   | 8002 | Consume events, chunk, embed, store       |
| retrieval  | 8003 | Vector search over pgvector               |
| chat       | 8004 | Prompt + LLM, return answer + citations   |
| postgres   | 5432 | pgvector store                            |
| rabbitmq   | 5672 | AMQP broker                               |
| rabbitmq   | 15672| Management UI                             |

All services expose `GET /health → {"status": "ok"}`.

---

## Events

Exchange: `rag.topic` (topic exchange). All events are JSON.

### DocumentDiscovered
Published by: ingestion  
Consumed by: ingestion (fetcher)

```json
{
  "event": "DocumentDiscovered",
  "url": "https://example.ac.uk/marp/Academic-Integrity-Regs.pdf",
  "title": "Academic Integrity Regulations",
  "discovered_at": "2026-10-20T12:00:00Z"
}
```

### DocumentExtracted
Published by: ingestion  
Consumed by: indexing

```json
{
  "event": "DocumentExtracted",
  "doc_id": "a1b2c3d4",
  "url": "https://example.ac.uk/marp/Academic-Integrity-Regs.pdf",
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
Consumed by: (logging / future consumers)

```json
{
  "event": "ChunksIndexed",
  "doc_id": "a1b2c3d4",
  "chunk_count": 34,
  "indexed_at": "2026-10-20T12:02:00Z"
}
```

### RetrievalCompleted
Published by: retrieval  
Consumed by: (logging / future consumers)

```json
{
  "event": "RetrievalCompleted",
  "query": "what is the late submission penalty?",
  "k": 5,
  "results": [
    {
      "chunk_id": "c001",
      "doc_id": "a1b2c3d4",
      "title": "Academic Integrity Regulations",
      "url": "https://example.ac.uk/marp/Academic-Integrity-Regs.pdf",
      "page": 3,
      "score": 0.91
    }
  ],
  "retrieved_at": "2026-10-20T12:03:00Z"
}
```

### AnswerGenerated
Published by: chat  
Consumed by: (logging / future consumers)

```json
{
  "event": "AnswerGenerated",
  "question": "what is the late submission penalty?",
  "answer": "A 5-mark deduction per day up to a maximum of 5 days...",
  "citations": [
    {
      "title": "Academic Integrity Regulations",
      "url": "https://example.ac.uk/marp/Academic-Integrity-Regs.pdf",
      "page": 3
    }
  ],
  "generated_at": "2026-10-20T12:03:05Z"
}
```

---

## HTTP Endpoints

### Ingestion (`localhost:8001`)

**POST /ingest/run**  
Triggers discovery and extraction pipeline.

Request: _(no body)_

Response `202 Accepted`:
```json
{"status": "started"}
```

**GET /documents**  
Lists extracted documents.

Response `200 OK`:
```json
[
  {
    "doc_id": "a1b2c3d4",
    "title": "Academic Integrity Regulations",
    "url": "https://example.ac.uk/marp/Academic-Integrity-Regs.pdf",
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
      "chunk_id": "c001",
      "doc_id": "a1b2c3d4",
      "title": "Academic Integrity Regulations",
      "url": "https://example.ac.uk/marp/Academic-Integrity-Regs.pdf",
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
      "url": "https://example.ac.uk/marp/Academic-Integrity-Regs.pdf",
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

- Embedding model: `all-MiniLM-L6-v2` (384 dimensions)
- All timestamps: ISO 8601 UTC
- `doc_id`: MD5 of URL
- `chunk_id`: `{doc_id}-p{page}-c{index}`
- Content-Type: `application/json` on all endpoints
