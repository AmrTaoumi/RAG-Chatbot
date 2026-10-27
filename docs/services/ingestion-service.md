Service Name: ingestion (port 8001)

Responsibility:
  Scrapes the MARP index page, fetches the PDFs it links to, and extracts their text page by page.

Data Owned:
  - Discovered PDF URLs (deduplicated, one record per URL)
  - Extracted documents (`doc_id`, title, url, page count, per-page text)

API Endpoints:
  - [GET] /health - liveness check
  - [POST] /discover - scrape MARP page and publish `DocumentDiscovered` per PDF (implemented; 403 if robots.txt disallows, 409 if a run is in progress)
  - [POST] /ingest/run - trigger full discovery and extraction pipeline, 202 Accepted (in contracts.md, not yet implemented)
  - [GET] /documents - list extracted documents (in contracts.md, not yet implemented)

Communicates With:
  - MARP website (REST, scrape index page and download PDFs, 5s crawl delay)
  - ingestion itself (Events, publishes `DocumentDiscovered`, consumes it from `ingestion.fetch`)
  - indexing (Events, publishes `DocumentExtracted`)
