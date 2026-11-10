# Scrum Artefacts

Product goal, product backlog, sprint log and team retrospective for MARP-Guide.

Snapshot taken on **10 Nov 2026** (Sprint 1 freeze) from the GitHub issues, the *Sprint 1* milestone, pull requests and commit history. The live board is the GitHub Project for this repository.

**At freeze:** all 32 Sprint 1 issues and all 128 estimated hours are done. The end-to-end run passed for all three members on 8 Nov.

**Contents**

1. [Product Goal](#1-product-goal)
2. [Team](#2-team)
3. [Definition of Done](#3-definition-of-done)
4. [Product Backlog](#4-product-backlog)
5. [Sprint Log](#5-sprint-log)
6. [Sprint 1 Retrospective](#6-sprint-1-retrospective)

---

## 1. Product Goal

> Build a chat application that answers questions about Lancaster University's Manual of Academic Regulations and Procedures (MARP). Answers come only from the processed MARP PDFs, cite their sources (title, page number, link), and are easy to understand. When no suitable source exists, the answer says "not certain / no source found".

**Vision:** reliable, quickly accessible information with sources, and no hallucinations.

**Users:** students and staff who need quick access to university regulations.

**Increments:**

| Increment | Sprint | Scope | Review |
|---|---|---|---|
| 1: Core RAG pipeline | Sprint 1, 19 Oct – 10 Nov | Ingestion, extraction, indexing, retrieval and chat as event-driven microservices under Docker Compose; answers with at least 1 citation; Tier 1 and Tier 2 designs | 12 Nov 2026 |
| 2: Full MVP + features | Sprint 2, 16 Nov – 17 Dec | At least 2 citations, web chat UI, Tier 1 (Auth & Sessions) and Tier 2 (Rate Limiting & Caching) implemented, automated tests in CI, test catalogue | 17 Dec 2026 |

## 2. Team

| Member | GitHub | Sprint 1 track |
|---|---|---|
| Amr Khalil Taoumi | AmrTaoumi | A: Ingestion & Extraction |
| Layla Alwahabi | layla-alw | B: Indexing & Retrieval |
| Walid Alwahabi | Walid-Alwahabi | C: Chat (LLM, prompt, citations, UI) |

Shared items (`track:shared`) are split into one issue per member, e.g. S1-16 (A), (B), (C).

## 3. Definition of Done

As practised in Sprint 1:

- [ ] Every acceptance criterion in the issue is ticked.
- [ ] Work is done on a `feature/<task-id>-…`, `fix/…` or `docs/…` branch and merged into `develop` through a reviewed pull request.
- [ ] CI is green: `pytest` passes for each service in the matrix and `docker compose build` succeeds.
- [ ] The service starts under `docker compose up` and answers `GET /health`.
- [ ] Any change to an interface also updates `docs/architecture/contracts.md`, `docs/events/event-catalogue.md` or the service doc.
- [ ] The issue is closed and the board card is moved to *Done*.

---

## 4. Product Backlog

Every Sprint 1 item is a GitHub issue with owner, estimate, dependencies and acceptance criteria; Sprint 2 candidates become issues at Sprint 2 planning. Sprint 1 estimates are in hours, taken from each issue; Sprint 2 estimates come from the design docs and are in days.

### 4.1 Sprint 1 items (milestone *Sprint 1*, due 9 Nov 2026)

All 32 issues are done. S1-18 is absent: issues #23–#25 were deleted.

| ID | Issue | Item | Track | Assignee | Est. | Status |
|---|---|---|---|---|---|---|
| S1-01 | #2 | Repo, branches, project board, labels, README skeleton | Shared | Amr | 2h | Done 20 Oct |
| S1-02 | #3 #4 #5 | Contract workshop | Shared | All three | 3h ×3 | Done 20 Oct |
| S1-03 | #6 | docker-compose with RabbitMQ and Postgres (pgvector) + service template | Shared | Amr | 4h | Done 20 Oct |
| S1-04 | #7 | Discovery: scrape MARP page, publish `DocumentDiscovered` | A | Amr | 6h | Done 26 Oct |
| S1-05 | #8 | Fetch and extract PDFs, publish `DocumentExtracted` | A | Amr | 8h | Done 2 Nov |
| S1-06 | #9 | Ingestion REST API with OpenAPI docs | A | Amr | 3h | Done 4 Nov |
| S1-07 | #10 | DB schema for chunks + pgvector index | B | Layla | 3h | Done 23 Oct |
| S1-08 | #11 | Custom chunker with unit tests | B | Layla | 8h | Done 24 Oct |
| S1-09 | #12 | Embedding and indexing consumer, publish `ChunksIndexed` | B | Layla | 6h | Done 4 Nov |
| S1-10 | #13 | `/search` endpoint, publish `RetrievalCompleted` | B | Layla | 6h | Done 2 Nov |
| S1-10.1 | #46 | Retrieval Dockerfile + compose block *(added 2 Nov)* | B | Layla | | Done 3 Nov |
| S1-11 | #14 | OpenRouter client | C | Walid | 4h | Done 2 Nov |
| S1-12 | #15 | Prompt template and citation logic | C | Walid | 8h | Done 4 Nov |
| S1-13 | #16 | Fallback: not certain / no source found | C | Walid | 3h | Done 5 Nov |
| S1-14 | #17 | `/chat` endpoint, publish `AnswerGenerated` | C | Walid | 6h | Done 8 Nov |
| S1-15 | #18 | Minimal static test page for the demo | C | Walid | 3h | Done 8 Nov |
| S1-16 | #19 #20 #21 | End-to-end run | Shared | All three | 8h ×3 | Done 8 Nov |
| S1-17 | #22 | Event schemas with examples + Mermaid event-flow diagram | Shared | Amr, Layla | 3h | Done 31 Oct |
| S1-19 | #26 | Tier 1 design doc: User Auth & Sessions | C | Layla | 5h | Done 4 Nov |
| S1-20 | #27 | Tier 2 design doc: Rate Limiting & Caching (PR #57) | B | Walid | 5h | Done 10 Nov |
| S1-21 | #28 | Scrum artefacts in `docs/` | Shared | Amr | 3h | Done 10 Nov |
| S1-22 | #29 | README: architecture diagram, setup, tech stack | Shared | Amr | 3h | Done 8 Nov |
| S1-23 | #30 #31 #32 | Demo script, slides and reflective report | Shared | All three | | Done 10 Nov |
| S1-24 | #33 #34 #35 | Freeze: tag `assessment-1`, zip, test on a clean machine | Shared | All three | 2h ×3 | Done 10 Nov |

### 4.2 Sprint 2 candidates, in priority order

These are refined and turned into issues at Sprint 2 planning (week 6). Rows 1–5 close MVP gaps for Assessment 2. Tier 1 comes before Tier 2 because the per-user rate limit and the cache isolation both depend on the authenticated user (JWT `sub`).

| # | Item | Epic | Source | Est. | Owner |
|---|---|---|---|---|---|
| 1 | Answers carry **at least 2 citations** (title, page, link); fall back when fewer than 2 sources qualify | RAG & Chat | Brief 2.1.3 D | TBD | TBD |
| 2 | Test catalogue: 10–15 MARP questions with expected answer and source pages | Quality | Brief M9 | TBD | TBD |
| 3 | Integration tests across services in CI + coverage report | Quality | Brief M8 | TBD | TBD |
| 4 | Web chat: sources panel with link-out per citation | UX | Brief 2.1.8 | TBD | TBD |
| 5 | Re-tune `SCORE_THRESHOLD` against the test catalogue and record the scores | Quality | Retro action A2 | TBD | TBD |
| T1-1 | Scaffold auth service, compose, `.env.example`, CORS (`CORS_ALLOWED_ORIGINS`) | Tier 1 | [Tier 1 design §E](../features/design-tier1-auth-sessions.md) | 0.5d | Amr |
| T1-2 | Create tables on startup (auth: users, refresh_tokens; chat: conversations, messages) | Tier 1 | Tier 1 §E | 1d | Walid |
| T1-3 | Register and login with hashing and JWT issuing | Tier 1 | Tier 1 §E | 1.5d | Layla |
| T1-4 | Refresh token rotation and logout revocation | Tier 1 | Tier 1 §E | 1.5d | Amr |
| T1-5 | Chat: JWT verification, scope `/chat` per user | Tier 1 | Tier 1 §E | 1d | Walid |
| T1-6 | Chat: conversation list, get and delete endpoints | Tier 1 | Tier 1 §E | 1d | Layla |
| T1-7 | Publish `UserLoggedIn` / `UserLoggedOut` | Tier 1 | Tier 1 §E | 0.5d | Amr |
| T1-8 | Web UI: login form, token handling, history view | Tier 1 | Tier 1 §E | 2d | Walid |
| T1-9 | Tier 1 tests, update `contracts.md` and the architecture diagram | Tier 1 | Tier 1 §E | 1.5d | Layla |
| T2-1 | Chat DB connection, create tables, env vars, load bge-small in chat | Tier 2 | [Tier 2 design §E](../features/design-tier2-rate-limit-cache.md) | 0.5d | Amr |
| T2-2 | Per-user limit (429) and global LLM budget (503), counting retries | Tier 2 | Tier 2 §E | 2d | Walid |
| T2-3 | Semantic cache: lookup, save, `cached` field | Tier 2 | Tier 2 §E | 1.5d | Layla |
| T2-4 | `ChunksIndexed` consumer clears the cache; update the event catalogue | Tier 2 | Tier 2 §E | 1d | Amr |
| T2-5 | Tune `CACHE_SIMILARITY`; UI messages for 429/503 | Tier 2 | Tier 2 §E | 1d | Walid |
| T2-6 | Tier 2 tests, update `contracts.md` (model, tables) and the diagram | Tier 2 | Tier 2 §E | 1.5d | Layla |

---

## 5. Sprint Log

### Sprint 1: 19 Oct – 10 Nov 2026

**Sprint goal:** deliver the core RAG pipeline end to end under Docker Compose (discover → fetch → extract → chunk/embed/index → search → chat with at least 1 citation), with every step publishing an event, and document the Tier 1 and Tier 2 designs.

**Milestone:** *Sprint 1*, due 9 Nov; freeze and tag `assessment-1` on Tue 10 Nov; upload 11 Nov 12:00; review/presentation 12 Nov.

#### Sprint backlog

At sprint planning on 19 Oct, 31 issues (S1-01 … S1-24, 128h estimated) were selected into the *Sprint 1* milestone and the sprint board. S1-10.1 (#46) was added on 2 Nov, making 32. The full list with assignees, estimates and status is in [4.1](#41-sprint-1-items-milestone-sprint-1-due-9-nov-2026).

#### Weekly log

| Week | Events |
|---|---|
| 19–25 Oct | **Sprint planning** (19 Oct): S1-01 … S1-24 created as issues with owner, estimate, dependencies and acceptance criteria (128h); work split into tracks A/B/C. **Contract workshop** (S1-02, 20 Oct): `contracts.md` agreed before any service code. Compose with RabbitMQ + Postgres/pgvector (S1-03), chunks table with HNSW index (S1-07, PR #37), token-based chunker with tests (S1-08, PR #38). CI pytest workflow added 25 Oct. |
| 26 Oct – 1 Nov | Discovery with robots.txt and dedupe, publishes `DocumentDiscovered` (S1-04, PR #40). **Scope change (29 Oct):** PDF extraction split out of ingestion into its own extraction service; event catalogue written; contracts, service docs and diagram realigned (PRs #41, #42). Event schemas done (S1-17); numbered architecture diagram (PR #43). |
| 2–8 Nov | Extraction (S1-05, PR #44), `/search` with `RetrievalCompleted` (S1-10, PR #45), OpenRouter client (S1-11). Missing retrieval Dockerfile added as S1-10.1. Ingestion API (S1-06), indexing consumer (S1-09, PR #52), citations (S1-12), Tier 1 design (S1-19, PRs #49, #51). Fallback below `SCORE_THRESHOLD` (S1-13), threshold lowered 0.5 → 0.35 after measuring MARP scores (PR #54). 8 Nov: embeddings switched to `bge-small-en-v1.5`, web UI added, **end-to-end run passed** (S1-16). |
| 9–10 Nov | Milestone due 9 Nov with 14h left. **Freeze (10 Nov):** PRs #55–#58 merged; `SCORE_THRESHOLD` raised to 0.6 for bge; Tier 2 design merged (S1-20, PR #57); Scrum artefacts (S1-21), demo prep (S1-23) and freeze (S1-24) done. All 32 issues done. |

#### Sprint 1 outcome

| Measure | Result |
|---|---|
| Issues done | 32 of 32 (100%) |
| Estimated hours done (velocity) | 128 of 128 (100%) |
| Pull requests merged | 21 |
| Services | ingestion, extraction, indexing, retrieval, chat (each with `/health`, in CI and in compose) |
| Events | `DocumentDiscovered`, `DocumentFetched`, `DocumentExtracted`, `ChunksIndexed`, `RetrievalCompleted`, `AnswerGenerated` |
| Carried over | None |

#### Sprint 1 review

**Increment:** a MARP question typed into the web page goes through `/chat` → `/search` over pgvector, then OpenRouter; the answer comes back with numbered citations, or a fallback when no source scores above the threshold. The pipeline is filled by discover → fetch → extract → index, and every step publishes an event on RabbitMQ.

**Review:** Assessment 1 presentation, 12 Nov 2026.

**Feedback:** *to be added after the review.*

### Sprint 2: 16 Nov – 17 Dec 2026 (planned)

**Draft sprint goal:** implement Tier 1 (Auth & Sessions) and Tier 2 (Rate Limiting & Caching), and complete the MVP with at least 2 citations, a test catalogue and integration tests in CI.

**Planning:** week 6, starting from the prioritised list in [4.2](#42-sprint-2-candidates-in-priority-order) and the actions in [6.3](#63-what-will-we-improve-in-sprint-2).

---

## 6. Sprint 1 Retrospective

The pipeline shipped on time, but scope changed mid-sprint and core retrieval settings changed in the last days. Two actions carry into Sprint 2.

**Format:** what went well? / what didn't go well? / what will we improve in Sprint 2? Held at the end of Sprint 1, after the freeze.

### 6.1 What went well?

- **The contract workshop came first.** S1-02 (20 Oct) produced `contracts.md` and a shared event envelope before any service code. That let the three tracks build in parallel and plug together at the end-to-end run.
- **Issues were well formed.** The Sprint 1 issues created at planning had an owner, dependencies and checkbox acceptance criteria, and most had an hour estimate, so it was always clear what "done" meant.
- **CI came early.** The pytest workflow existed from 25 Oct, and each new service joined the CI matrix as it landed. `docker compose build` also runs in CI.
- **Every change went through a PR into `develop`.** 21 PRs were merged
- **We measured before tuning.** The first `SCORE_THRESHOLD` change was based on measured MARP retrieval scores rather than guesswork.
- **The end-to-end run (S1-16) passed for all three members** two days before the freeze.

### 6.2 What didn't go well?

- **Mid-sprint scope changes.** Splitting extraction into its own service (29 Oct) was the right call, but it forced a pass to realign contracts, service docs and the diagram. The retrieval Dockerfile was missed at planning and added as S1-10.1. The score-threshold fallback was only noticed as missing on 7 Nov.
- **Late changes to core retrieval behaviour.** The embedding model was switched to bge on 8 Nov, and `SCORE_THRESHOLD` moved 0.5 → 0.35 → 0.6 between 7 and 10 Nov. There was no fixed question set to check each change against.

### 6.3 What will we improve in Sprint 2?

| # | Action | Check |
|---|---|---|
| A1 | Run the end-to-end flow weekly, not just before the freeze | One E2E note per week in the sprint log |
| A2 | Build the test catalogue (backlog #2) **before** further threshold or embedding changes; log scores per change. After any embedding model change, re-index all chunks and re-tune `SCORE_THRESHOLD` | Catalogue committed by week 7 |
