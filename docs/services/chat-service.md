Service Name: chat (port 8004)

Responsibility:
  Answers a question from the retrieved chunks. Asks retrieval for the top 8 chunks; if none are returned or the best `score` is below `SCORE_THRESHOLD` (default `0.6`), returns the fallback "not certain / no source found" without calling the LLM. Otherwise builds a numbered prompt, calls the LLM, keeps only citations `[n]` that point to a retrieved chunk, and renumbers them. An answer with no valid citation also becomes the fallback.

Data Owned:
  - None. Chat has no database access (no `DATABASE_URL`). A semantic cache is planned for Sprint 2 (Tier 2, `docs/features/design-tier2-rate-limit-cache.md`).

API Endpoints:
  - [GET] /health - liveness check
  - [GET] / - serves the web UI (static page bundled with this service, assets under `/static/`; it calls `POST /chat` on the same origin)
  - [POST] /chat - answer a `question`; returns `answer` plus `citations` (title, url, page), or "not certain / no source found" with empty citations. Errors: `422` empty question, `503` retrieval unavailable, `502` language model unavailable

Communicates With:
  - Web UI (REST, the browser loads `GET /` and calls `POST /chat`)
  - retrieval (REST, `GET /search` with `k=8` and an `X-Correlation-ID` header; URL set by `RETRIEVAL_URL`)
  - OpenRouter LLM (REST, generates the answer from the prompt; model set by `OPENROUTER_MODEL`, default `nvidia/nemotron-3.5-super-vl:free`; up to 5 attempts with 1, 2, 4, 8 s backoff on network errors, 429 and 5xx)
  - RabbitMQ (Events, publishes `AnswerGenerated`; no consumer yet)
