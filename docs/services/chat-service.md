Service Name: chat (port 8004)

Responsibility:
  Builds a prompt from retrieved chunks, calls the LLM, and returns an answer with citations (or a fallback when no source supports an answer).

Data Owned:
  - None (stateless; no database of its own)

API Endpoints:
  - [GET] /health - liveness check
  - [POST] /chat - answer a `question`; returns `answer` plus `citations` (title, url, page), or "I'm not certain based on the available documents." with empty citations

Communicates With:
  - retrieval (REST, `GET /search` to fetch relevant chunks)
  - LLM provider (REST, generates the answer from the prompt)
  - logging (Events, publishes `AnswerGenerated`)
