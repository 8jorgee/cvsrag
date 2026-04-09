# Requirements

## v1 Requirements

### Security & Reliability (SEC)

- [ ] **SEC-01**: CSRF tokens added to all HTMX admin forms and validated server-side
- [ ] **SEC-02**: Search query length capped at 500 characters (HTTP 400 returned for longer queries)
- [ ] **SEC-03**: `ANTHROPIC_API_KEY` validated at application startup; server refuses to start if missing
- [ ] **SEC-04**: Rate limiting applied to `/search` endpoint (30 requests/minute per IP)
- [ ] **SEC-05**: File upload validates content type in addition to extension

### Data Integrity (DATA)

- [ ] **DATA-01**: Availability name matching is case-insensitive and accent-insensitive (unidecode normalization)
- [ ] **DATA-02**: FAISS index and SQLite metadata stay in sync — upsert is atomic (rollback SQLite if FAISS fails)
- [ ] **DATA-03**: Profile IDs are stable UUIDs derived from parsed profile name, not MD5 of filename
- [ ] **DATA-04**: Incremental ingestion detects availability CSV row changes, not only CV file hash changes
- [ ] **DATA-05**: Malformed availability dates cause profile to be excluded from availability filter (not silently pass through)

### Robustness (ROB)

- [ ] **ROB-01**: Claude JSON responses parsed with `json.loads()` + bracket-finding fallback (not raw regex)
- [ ] **ROB-02**: Embedding model loading is thread-safe (threading.Lock guards initialization)
- [ ] **ROB-03**: SQLite access serialized safely in async context (asyncio.Lock or aiosqlite)
- [ ] **ROB-04**: CV text extraction uses up to 16,000 characters with slide-boundary chunking (not hard 8000-char cutoff)
- [ ] **ROB-05**: Re-index triggered from admin runs as background task (non-blocking); admin UI shows live progress via SSE

### Search Quality (SEARCH)

- [ ] **SEARCH-01**: Search results support pagination (page + page_size parameters)
- [ ] **SEARCH-02**: Filters support OR logic for skills and certifications (`skills_any`, `certifications_any` fields alongside existing AND fields)

### New Features (FEAT)

- [ ] **FEAT-01**: Fuzzy name matching for availability lookups using rapidfuzz (WRatio threshold configurable in settings)
- [ ] **FEAT-02**: Parallel ingestion processes multiple CVs concurrently (ThreadPoolExecutor, default 4 workers, configurable)
- [ ] **FEAT-03**: Search results page has "Export" button — downloads current results as CSV or Excel
- [ ] **FEAT-04**: Search history stored per session (last 20 queries) and shown below search bar for one-click re-run
- [ ] **FEAT-05**: Skill gap analysis page — user enters required skills, system shows which profiles cover each skill and what's missing across the team
- [ ] **FEAT-06**: Team composition assistant page — user describes project (type + required skills), Claude suggests optimal team from available profiles
- [ ] **FEAT-07**: Embedding cache — query embeddings stored in SQLite keyed by SHA-256 of query text; skip re-generation on repeated queries
- [ ] **FEAT-08**: Profile diff view in admin — when a CV is re-indexed, admin can see what structured fields changed vs previous version
- [ ] **FEAT-09**: Full test suite with pytest — unit tests for filters, scoring, embeddings; integration test for full search pipeline; target 80% coverage
- [ ] **FEAT-10**: Structured logging via structlog — JSON format in production, colored console in development; replaces all print() calls
- [ ] **FEAT-11**: Async reindex with SSE — `/admin/reindex-stream` endpoint streams progress per CV in real time to admin UI

## v2 Requirements (Deferred)

- SharePoint connector for automatic CV sync
- Multi-language name extraction (non-English naming conventions)
- FAISS → scalable vector DB (Qdrant/Weaviate) for >500 profiles
- OAuth / SSO for admin authentication
- Export results as formatted PDF

## Out of Scope

- Public-facing search (internal only) — security model assumes trusted network
- Real-time CV editing in the UI — upload workflow is sufficient
- User accounts / per-user saved searches — session-based history is enough for v1

## Traceability

| REQ-ID | Phase |
|--------|-------|
| SEC-01, SEC-02, SEC-03, SEC-04, SEC-05 | Phase 1 |
| DATA-01, DATA-02, DATA-03, DATA-04, DATA-05 | Phase 1 |
| ROB-01, ROB-02, ROB-03, ROB-04, ROB-05 | Phase 2 |
| SEARCH-01, SEARCH-02 | Phase 2 |
| FEAT-01, FEAT-02, FEAT-07, FEAT-10 | Phase 2 |
| FEAT-03, FEAT-04 | Phase 3 |
| FEAT-05, FEAT-06 | Phase 3 |
| FEAT-08, FEAT-11 | Phase 3 |
| FEAT-09 | Phase 4 |
