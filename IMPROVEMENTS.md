# Improvements Log — CVs RAG System

This document summarises all bugs fixed, issues resolved, and new features shipped across completed development phases, followed by a preview of what is coming in Phases 3 and 4.

---

## Phase 1 — Security & Data Integrity

**Goal:** Eliminate all security vulnerabilities and data integrity bugs so the system is safe to run in production.

### Bugs & Security Issues Fixed

#### SEC-01 — CSRF tokens missing from admin forms
**Problem:** Admin forms (re-index, file upload) had no CSRF protection. An attacker could trick an authenticated admin into triggering reindex or uploading malicious files via a forged request.
**Fix:** Added `starlette-csrf` middleware. All HTMX admin forms now include a CSRF token cookie and the server rejects any POST request that does not present a valid token.

#### SEC-02 — No input length validation on search queries
**Problem:** Search queries were passed directly to the embedding model with no size cap. A sufficiently long query could degrade performance or trigger unexpected model behaviour.
**Fix:** Search query length is now capped at 500 characters. Queries that exceed this limit receive an HTTP 400 response immediately.

#### SEC-03 — Application started silently without a valid API key
**Problem:** If `GEMINI_API_KEY` was missing or empty, the app started normally but failed at the moment of the first LLM call, producing a confusing runtime error.
**Fix:** The API key is now validated at startup. The server refuses to start and logs a clear error message if the key is absent or blank.

#### SEC-04 — No rate limiting on the search endpoint
**Problem:** The `/search` endpoint had no throttle. A single client could flood the server with requests, consuming embedding and LLM quota.
**Fix:** Applied `slowapi` rate limiting to `/search`: 30 requests per minute per IP. Requests beyond the limit receive HTTP 429.

#### SEC-05 — File upload validated extension only, not content type
**Problem:** A user could rename any file to `.pptx` and upload it. The server accepted it based on file extension alone.
**Fix:** Upload endpoints now validate both the file extension and the MIME content type. Files that don't match the expected type are rejected with HTTP 400.

#### DATA-01 — Availability matching broken for accented and mixed-case names
**Problem:** A name like "María García" in the availability spreadsheet would not match "maria garcia" in the CV, causing availability data to be silently missing from search results.
**Fix:** Implemented case-insensitive and accent-insensitive name matching using `unidecode` normalization via `rapidfuzz` WRatio (threshold configurable, default 85).

#### DATA-02 — FAISS index and SQLite could get out of sync
**Problem:** If the SQLite write succeeded but the FAISS index update failed (or vice versa), the two stores would diverge. Subsequent searches would return stale or missing results.
**Fix:** Upsert is now atomic. If the FAISS write fails, the SQLite write is rolled back. Both stores are always consistent.

#### DATA-03 — Profile IDs were based on MD5 of filename
**Problem:** Renaming a CV file (e.g., `john_smith_v2.pptx` → `john_smith.pptx`) generated a new profile ID, creating a duplicate entry instead of updating the existing profile.
**Fix:** Profile IDs are now stable UUIDs derived from the parsed profile name extracted from the CV content. Renaming the file no longer creates a duplicate.

#### DATA-04 — Availability CSV changes did not trigger re-ingestion
**Problem:** When only the availability spreadsheet changed (no CV files changed), incremental ingestion skipped all profiles and left availability data stale.
**Fix:** Incremental ingestion now tracks a hash of each profile's availability row separately. A change in the CSV row triggers re-ingestion of the affected profile even when the CV file itself is unchanged.

#### DATA-05 — Malformed availability dates silently passed through filters
**Problem:** Invalid date strings in the availability spreadsheet (e.g., `"TBD"`, `"N/A"`, free text) were stored as-is and caused the availability date filter to behave unpredictably.
**Fix:** Malformed dates are detected during ingestion and the profile is excluded from date-based availability filtering rather than letting corrupted data reach the filter.

---

## Phase 2 — Robustness, Performance & Core Features

**Goal:** Harden the system against runtime failures, improve performance, and ship the first set of new features.

### Bugs & Robustness Issues Fixed

#### ROB-01 — LLM JSON responses parsed with fragile regex
**Problem:** JSON extracted from Claude/Gemini responses used a raw regex (`re.search(r"\[.*\]", content, re.DOTALL)`). Responses wrapped in markdown fences, responses with extra whitespace, or responses with nested brackets caused silent parse failures and crashed the ingestion pipeline.
**Fix:** Replaced the regex with a three-strategy parser in both `engine.py` and `profile_builder.py`:
1. Try `json.loads(content)` directly (fast path for clean responses).
2. Extract bracketed content and retry (handles markdown fences like ` ```json ... ``` `).
3. If both fail, raise `ValueError` with a structured log entry — no more silent failures.

#### ROB-02 — Embedding model initialization was not thread-safe
**Problem:** Under concurrent requests, multiple threads could attempt to initialise the `SentenceTransformer` model simultaneously, leading to race conditions and potentially loading the model multiple times (wasting ~90 MB of RAM per duplicate load).
**Fix:** Added a `threading.Lock` around the model initialisation block in `embeddings.py`. The model is now guaranteed to be loaded exactly once regardless of how many threads call it concurrently.

#### ROB-03 — SQLite writes unsafe under async concurrency
**Problem:** FastAPI's async request handlers could run concurrently and issue simultaneous SQLite writes. SQLite does not support concurrent writes; without serialisation this could cause database corruption or `OperationalError: database is locked`.
**Fix:** Added an `asyncio.Lock` to `VectorCollection` in `db.py`. All async write operations (upsert, delete) now acquire this lock, serialising writes while reads remain concurrent (SQLite WAL mode).

#### ROB-04 — CV text cut off at a hard 8 000-character limit
**Problem:** Only the first 8 000 characters of a CV were sent to the LLM for profile extraction. For long CVs this truncated mid-sentence or mid-slide, causing the LLM to miss skills, certifications, and experience from later slides.
**Fix:** Replaced the hard cutoff with slide-boundary chunking (`chunk_slides_to_16k()`). The function concatenates complete slides until the cumulative length reaches 16 000 characters, never cutting mid-slide. This doubles the usable text budget while ensuring coherent context for the LLM.

### New Features Shipped

#### SEARCH-01 — Search result pagination with Load More
Search results now paginate with a page size of 10. A **Load More** button appears below results when additional pages exist. Clicking it appends the next page of results below the existing cards using HTMX (`hx-swap="beforeend"`) — no page reload. The UI shows a "Showing N of M" counter so users know how many profiles match.

#### SEARCH-02 — OR filter logic for skills and certifications
Filter groups previously applied AND logic only (a profile had to match every selected skill). Now each filter group has an **AND / OR toggle**. Switching to OR changes the form field names from `skills` to `skills_any` (and `certifications` to `certifications_any`), and the backend applies `any()` matching instead of `all()`. Default remains AND.

#### FEAT-01 — Fuzzy name matching for availability lookups
Availability data is now matched to CV profiles using `rapidfuzz` WRatio scoring (threshold 85, configurable via `settings.fuzzy_match_threshold`). This was already partially in place from Phase 1 work and confirmed complete.

#### FEAT-02 — Parallel CV ingestion
`ingest_cvs.py` now processes multiple CV files concurrently using a `ThreadPoolExecutor` with `max_workers=4` (configurable via `INGEST_WORKERS` environment variable or `settings.ingest_workers`). Per-file work (extraction, LLM parsing, embedding generation) runs in parallel; the final database write is serialised with a `threading.Lock` to prevent corruption. Typical ingestion time scales near-linearly with worker count.

#### FEAT-07 — Embedding cache
Query embeddings are now cached in a `query_cache` table in the existing `metadata.db` SQLite database. The cache key is the SHA-256 hex digest of the query text. On a cache hit the embedding is read from SQLite and the `SentenceTransformer` model is skipped entirely, reducing p50 search latency for repeated queries. The cache has no eviction (query embeddings are deterministic and cheap to store).

#### FEAT-10 — Structured logging via structlog
All `logging.getLogger()` calls across `app/` and `scripts/` have been replaced with `structlog.get_logger()`. In production mode (`LOG_FORMAT=json`) every log line is a JSON object with structured fields (timestamp, level, event, key-value context). In development mode the output is human-readable with coloured level labels. This makes log aggregation and alerting in production tooling (Datadog, CloudWatch, Loki) trivial.

#### ROB-05 — Live re-index progress via Server-Sent Events
The admin **Re-index** button no longer fires a plain POST and waits for a response. Instead it opens an `EventSource` connection to the new `GET /admin/reindex-stream?force=true|false` endpoint. The server streams per-file progress events in real time:
- `{"file": "john.pptx", "status": "processing|ok|error"}` — one event per CV file.
- `{"done": true, "processed": N, "skipped": N, "errors": N}` — final summary event.

The admin log box updates line by line as each file is processed, with colour-coded status indicators (✓ green / ⊘ grey / ✗ red). The old `/admin/reindex` POST endpoint is retained for backward compatibility.

---

## Phase 3 — Advanced Features (Upcoming)

**Goal:** Ship the high-value differentiating features that make this tool a genuine talent intelligence platform, not just a search interface.

### What will be built

#### FEAT-03 — Export search results
A download button on the search results page will allow users to export the currently displayed results as a **CSV or Excel file**. The export will include name, grade, location, key skills, availability date, and match score. This removes the need to manually copy-paste data into spreadsheets for staffing decisions.

#### FEAT-04 — Search history
The last 20 search queries will be stored per browser session and displayed below the search bar. Clicking a previous query re-runs it instantly. This allows recruiters and staffing managers to iterate quickly between similar searches without retyping.

#### FEAT-05 — Skill gap analysis
A dedicated page where a user enters a list of required skills for a project. The system responds with:
- Which profiles in the database cover each required skill.
- A gap matrix showing skills for which no profile qualifies.
- A summary of overall team coverage percentage.

This turns the tool from a "find one person" tool into a "staff a whole project" tool.

#### FEAT-06 — Team composition assistant
A page where the user describes a project (type, required skills, timeline, seniority mix). Claude analyses all available profiles and suggests an **optimal team composition** with named individuals, their roles, and reasoning for each choice. Availability data is factored in so bench-status and upcoming free dates are reflected in the recommendation.

#### FEAT-08 — Profile diff view in admin
When a CV is re-indexed, the admin will be able to see exactly **what structured fields changed** compared to the previous version (e.g., a new certification was detected, years of experience increased, a skill was added or removed). This makes it easy to verify that a CV update was parsed correctly and catches LLM extraction regressions.

#### FEAT-11 — Async reindex UI polish
Completing the SSE work from Phase 2 with additional UI improvements: progress bar, elapsed time display, error retry button, and clearer per-file status in the admin dashboard.

---

## Phase 4 — Full Test Suite (Upcoming)

**Goal:** Achieve ≥ 80% test coverage across the `app/` codebase so future changes can be made with confidence and regressions are caught automatically.

### What will be built

#### FEAT-09 — Comprehensive pytest suite

The existing test stubs (created in Phase 2, Plan 01) will be filled with real implementations:

| Test area | Coverage target | Notes |
|-----------|----------------|-------|
| Filter logic | All filter types (AND, OR, date range, grade, location) | Parametrised test matrix |
| Scoring | Blended score calculation, calibration curve, keyword bonus | Pure function — easy to unit test |
| Embedding normalisation | Vector shape, magnitude clamping | Mocked model to avoid torch load |
| JSON parsing | Clean, markdown-wrapped, deeply nested, unparseable | ROB-01 behaviour |
| Chunking | Slide boundary, 16K limit, empty slides, single-slide | ROB-04 behaviour |
| Availability matching | Exact, fuzzy, accented, mismatched case | DATA-01 behaviour |
| Ingestion pipeline | Atomic upsert, stable ID, CSV change detection | DATA-02, DATA-03, DATA-04 |
| Security | CSRF rejection, rate limit (429), query length (400), MIME type | SEC-01–05 |
| Full search pipeline | Query → embed → retrieve → filter → rerank → paginate | End-to-end integration test |

**Constraints:**
- All external dependencies (LLM API, SentenceTransformer model, FAISS) will be mocked so tests run offline in CI with no network access.
- Target: `pytest` exits 0, coverage report shows ≥ 80% across all `app/` modules.
- Estimated runtime: < 60 seconds for the full suite.

---

## Summary

| Phase | Status | Items delivered |
|-------|--------|----------------|
| 1 — Security & Data Integrity | ✅ Complete | 5 security fixes, 5 data integrity fixes |
| 2 — Robustness, Performance & Core Features | ✅ Complete | 4 robustness fixes, 6 new features, 21 tests |
| 3 — Advanced Features | 🔜 Upcoming | Export, search history, skill gap, team builder, profile diff |
| 4 — Test Suite | 🔜 Upcoming | ≥ 80% pytest coverage, full offline CI suite |
