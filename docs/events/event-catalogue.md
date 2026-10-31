# Event Catalogue

**Status:** Draft, pending approval from all three members.

All events published on RabbitMQ. REST endpoints, database tables and shared conventions are in `docs/contracts.md`. The event flow diagram is in `docs/architecture-event-flow.md`.

Exchange: `rag.topic` (topic exchange, durable). All events are JSON with the envelope below.

## Routing

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
- Delivery is at-least-once, so every consumer must be idempotent (key: `payload.doc_id`, or `payload.url` for `DocumentDiscovered`).

## Envelope

Every event has the same envelope. Event-specific fields go in `payload`.

```json
{
  "eventType": "DocumentDiscovered",
  "eventId": "3f2b8c1e-5d0a-4c1e-9a7b-1e2d3c4b5a61",
  "timestamp": "2026-10-20T12:00:00Z",
  "correlationId": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "payload": { }
}
```

| Field           | Meaning |
|-----------------|---------|
| `eventType`     | Event name, same as in the routing table |
| `eventId`       | UUID v4, new for every message |
| `timestamp`     | When the event was created, ISO 8601 UTC |
| `correlationId` | UUID v4 shared by every event in one journey, so they can be traced together |
| `payload`       | Event-specific fields, defined per event below |

`correlationId` rules:
- **Document flow:** ingestion creates one per document in `DocumentDiscovered`. `DocumentFetched`, `DocumentExtracted` and `ChunksIndexed` copy it.
- **Chat flow:** chat creates one per `POST /chat`. It sends it to retrieval in the `X-Correlation-ID` request header, and retrieval uses it in `RetrievalCompleted`. If the header is missing, retrieval creates one. `AnswerGenerated` uses the same ID.
- Services include the `correlationId` in their log lines.

## DocumentDiscovered
Triggered by: ingestion  
Consumed by: ingestion (fetcher)  
Purpose: Tell the fetcher that a new MARP PDF link exists, so it is downloaded exactly once.

`doc_id` is not in the payload. It is derived from `url` (MD5, see Shared Conventions in `docs/contracts.md`). A new `correlationId` is created here for each document.

```json
{
  "eventType": "DocumentDiscovered",
  "eventId": "3f2b8c1e-5d0a-4c1e-9a7b-1e2d3c4b5a61",
  "timestamp": "2026-10-20T12:00:00Z",
  "correlationId": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "payload": {
    "url": "https://www.lancaster.ac.uk/media/lancaster-university/content-assets/documents/student-based-services/asq/marp/Academic-Integrity-Regs.pdf",
    "title": "Academic Integrity Regulations"
  }
}
```

## DocumentFetched
Triggered by: ingestion (after downloading the PDF)  
Consumed by: extraction  
Purpose: Tell extraction that a PDF is on the shared volume and ready to read.

The PDF is not carried in the event. It is written to the shared `pdfs` volume and the payload gives its path.

```json
{
  "eventType": "DocumentFetched",
  "eventId": "3f2b8c1e-5d0a-4c1e-9a7b-1e2d3c4b5a62",
  "timestamp": "2026-10-20T12:00:30Z",
  "correlationId": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "payload": {
    "doc_id": "9e107d9d372bb6826bd81d3542a419d6",
    "url": "https://www.lancaster.ac.uk/media/lancaster-university/content-assets/documents/student-based-services/asq/marp/Academic-Integrity-Regs.pdf",
    "title": "Academic Integrity Regulations",
    "path": "/data/pdfs/9e107d9d372bb6826bd81d3542a419d6.pdf"
  }
}
```

## DocumentExtracted
Triggered by: extraction  
Consumed by: indexing  
Purpose: Hand the per-page text of a document to indexing for chunking and embedding.

```json
{
  "eventType": "DocumentExtracted",
  "eventId": "3f2b8c1e-5d0a-4c1e-9a7b-1e2d3c4b5a63",
  "timestamp": "2026-10-20T12:01:00Z",
  "correlationId": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "payload": {
    "doc_id": "9e107d9d372bb6826bd81d3542a419d6",
    "url": "https://www.lancaster.ac.uk/media/lancaster-university/content-assets/documents/student-based-services/asq/marp/Academic-Integrity-Regs.pdf",
    "title": "Academic Integrity Regulations",
    "page_count": 12,
    "pages": [
      {
        "page": 1,
        "text": "..."
      },
      {
        "page": 2,
        "text": "..."
      }
    ]
  }
}
```

## ChunksIndexed
Triggered by: indexing  
Consumed by: none yet  
Purpose: Record that a document's chunks are stored and searchable.

```json
{
  "eventType": "ChunksIndexed",
  "eventId": "3f2b8c1e-5d0a-4c1e-9a7b-1e2d3c4b5a64",
  "timestamp": "2026-10-20T12:02:00Z",
  "correlationId": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "payload": {
    "doc_id": "9e107d9d372bb6826bd81d3542a419d6",
    "chunk_count": 34
  }
}
```

## RetrievalCompleted
Triggered by: retrieval  
Consumed by: none yet  
Purpose: Record which chunks were returned for a query, for later analysis.

```json
{
  "eventType": "RetrievalCompleted",
  "eventId": "3f2b8c1e-5d0a-4c1e-9a7b-1e2d3c4b5a65",
  "timestamp": "2026-10-20T12:03:00Z",
  "correlationId": "b2a1c3d4-8e5f-4a6b-9c7d-0e1f2a3b4c5d",
  "payload": {
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
    ]
  }
}
```

## AnswerGenerated
Triggered by: chat  
Consumed by: none yet  
Purpose: Record the question, answer and citations that were returned to the user.

```json
{
  "eventType": "AnswerGenerated",
  "eventId": "3f2b8c1e-5d0a-4c1e-9a7b-1e2d3c4b5a66",
  "timestamp": "2026-10-20T12:03:05Z",
  "correlationId": "b2a1c3d4-8e5f-4a6b-9c7d-0e1f2a3b4c5d",
  "payload": {
    "question": "what is the late submission penalty?",
    "answer": "A 5-mark deduction per day up to a maximum of 5 days...",
    "citations": [
      {
        "title": "Academic Integrity Regulations",
        "url": "https://www.lancaster.ac.uk/media/lancaster-university/content-assets/documents/student-based-services/asq/marp/Academic-Integrity-Regs.pdf",
        "page": 3
      }
    ]
  }
}
```