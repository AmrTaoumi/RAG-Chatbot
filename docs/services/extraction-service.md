Service Name: extraction (port 8005)

Responsibility:
  Converts fetched MARP PDFs into per-page text and document metadata.

Data Owned:
  - `documents` table (`doc_id`, `title`, `url`, `page_count`, `pages`, `extracted_at`)

API Endpoints:
  - [GET] /health - liveness check
  - [GET] /documents - list extracted documents (`[]` when there are none; 503 if the database is unreachable)

Communicates With:
  - ingestion (Events, consumes `DocumentFetched` from queue `extraction.documents`; reads the PDF from the shared `pdfs` volume, read-only)
  - postgres (SQL, writes `documents`; idempotent on `doc_id`)
  - indexing (Events, publishes `DocumentExtracted`)

Note:
  Extraction was split out of ingestion (Week 2 slide 22 example). Ingestion now only discovers and fetches PDFs.
