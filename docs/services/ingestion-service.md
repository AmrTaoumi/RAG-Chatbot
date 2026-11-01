Service Name: ingestion (port 8001)

Responsibility:
  Scrapes the MARP index page, publishes a `DocumentDiscovered` event for each new PDF link, then downloads each PDF and hands it to extraction.

Data Owned:
  - `discovered_documents` table (`url`, one row per PDF URL, deduplicated)
  - Downloaded PDFs on the shared `pdfs` volume (written here, read by extraction)

API Endpoints:
  - [GET] /health - liveness check
  - [POST] /discover - scrape MARP page and publish `DocumentDiscovered` per new PDF; returns `{"published": N}` (implemented; 403 if robots.txt disallows, 409 if a run is in progress)

Communicates With:
  - MARP website (REST, scrape index page and download PDFs, 5s crawl delay)
  - postgres (SQL, reads and writes `discovered_documents`)
  - RabbitMQ (Events, publishes `DocumentDiscovered`, consumes it from `ingestion.fetch`)
  - extraction (Events, publishes `DocumentFetched` with the PDF path on the shared volume)
