# Phase 2 — Robustness, Performance & Core Features: Planning Summary

**Created:** 2026-04-09
**Phase:** 02-robustness-performance-core-features
**Status:** Planning complete, ready for execution

---

## Overview

Phase 2 delivers 10 detailed execution plans spanning 3 waves to harden the system and ship core search features. All requirements from CONTEXT.md are mapped to specific plans with clear task breakdowns and testing strategy.

---

## Plans Created

| # | Plan | Wave | Tasks | Requirements | Status |
|---|------|------|-------|--------------|--------|
| 01 | Test Infrastructure | 0 | 14 | ROB-01–05, SEARCH-01–02, FEAT-02, FEAT-07, FEAT-10 | Ready |
| 02 | JSON Parsing Robustness | 1 | 2 | ROB-01 | Ready |
| 03 | Thread Safety & DB Concurrency | 1 | 2 | ROB-02, ROB-03 | Ready |
| 04 | CV Text Chunking | 1 | 2 | ROB-04 | Ready |
| 05 | Embedding Cache | 2 | 2 | FEAT-07 | Ready |
| 06 | Parallel Ingestion | 2 | 3 | FEAT-02 | Ready |
| 07 | Structured Logging | 2 | 3 | FEAT-10 | Ready |
| 08 | Pagination | 3 | 5 | SEARCH-01 | Ready |
| 09 | OR Filter Logic | 3 | 4 | SEARCH-02 | Ready |
| 10 | SSE Reindex Streaming | 3 | 3 | ROB-05 | Ready |

**Total:** 10 plans, 40 tasks across 3 waves

---

## Wave Execution Strategy

### Wave 0 (Prerequisite)
**Plan 01: Test Infrastructure**
- Creates pytest configuration, fixtures, and 13 test stub files
- Installs structlog dependency
- **Must complete before Wave 1 starts** (test-first approach)
- **Estimated time:** 30-45 min execution

### Wave 1 (Core Robustness Fixes)
**Plans 02–04:** Independent robustness improvements
- Plan 02: JSON parsing (engine.py, profile_builder.py)
- Plan 03: Thread safety (embeddings.py, db.py)
- Plan 04: Text chunking (profile_builder.py, ingest_cvs.py)
- **Can run in parallel** (no cross-dependencies)
- **Dependencies:** Wave 0 only
- **Estimated time:** 60-90 min total

### Wave 2 (Feature Additions)
**Plans 05–07:** Features that build on Wave 1
- Plan 05: Embedding cache (db.py, embeddings.py) — depends on ROB-03 asyncio.Lock
- Plan 06: Parallel ingestion (ingest_cvs.py, db.py, config.py) — depends on ROB-03 and ROB-04
- Plan 07: Structured logging (all modules) — independent, can start anytime
- **Can run in parallel** (no direct dependencies except Plan 06 on 04)
- **Dependencies:** Wave 1 complete
- **Estimated time:** 90-120 min total

### Wave 3 (Search UI Features)
**Plans 08–10:** User-facing features
- Plan 08: Pagination (models.py, engine.py, main.py, templates)
- Plan 09: OR Filters (models.py, filters.py, main.py, templates)
- Plan 10: SSE Streaming (main.py, ingest_cvs.py, admin.html) — depends on ROB-03 and FEAT-02
- **Can run in parallel** (Plans 08 & 09 independent; Plan 10 depends on earlier infrastructure)
- **Dependencies:** Wave 0 + 1 complete, Plan 06 or 07 for context
- **Estimated time:** 120-150 min total

---

## Requirements Coverage

All 11 Phase 2 requirements are addressed:

| ID | Description | Plan | Status |
|----|-------------|------|--------|
| ROB-01 | JSON parsing robustness (json.loads + fallback) | 02 | Covered |
| ROB-02 | Thread-safe embedding model (threading.Lock) | 03 | Covered |
| ROB-03 | SQLite async safety (asyncio.Lock) | 03 | Covered |
| ROB-04 | CV text chunking (16K chars, slide boundaries) | 04 | Covered |
| ROB-05 | Async reindex with SSE progress | 10 | Covered |
| SEARCH-01 | Pagination (Load More, page_size=10) | 08 | Covered |
| SEARCH-02 | OR filter logic (skills_any, certifications_any) | 09 | Covered |
| FEAT-01 | Fuzzy name matching | — | Already done in Phase 1 ✓ |
| FEAT-02 | Parallel ingestion (ThreadPoolExecutor, 4 workers) | 06 | Covered |
| FEAT-07 | Embedding cache (query_cache table) | 05 | Covered |
| FEAT-10 | Structured logging (structlog) | 07 | Covered |

---

## Test Coverage by Plan

All plans include automated verification (pytest commands) tied to test stubs created in Wave 0:

- **Plan 02** → `pytest tests/unit/test_json_parsing.py -xvs`
- **Plan 03** → `pytest tests/unit/test_embeddings.py tests/integration/test_db_async.py -xvs`
- **Plan 04** → `pytest tests/unit/test_chunking.py -xvs`
- **Plan 05** → `pytest tests/unit/test_cache.py -xvs`
- **Plan 06** → `pytest tests/integration/test_parallel_ingest.py -xvs`
- **Plan 07** → `pytest tests/unit/test_logging.py -xvs`
- **Plan 08** → `pytest tests/unit/test_pagination.py -xvs`
- **Plan 09** → `pytest tests/unit/test_filters.py -xvs`
- **Plan 10** → `pytest tests/integration/test_sse.py -xvs`

Quick suite: `pytest tests/ -m "not slow" -x` (validates most features in ~30 sec)
Full suite: `pytest tests/ --cov=app --cov-report=term-missing` (includes coverage reporting, ~90 sec)

---

## Key Architectural Decisions

All decisions from CONTEXT.md are incorporated into plans with code patterns from RESEARCH.md:

1. **JSON Parsing** → Two parse_json_response() functions (object and array) with 3-strategy fallback
2. **Thread Safety** → threading.Lock for embeddings, asyncio.Lock for SQLite (separate concerns)
3. **Text Chunking** → Slide-boundary algorithm, 16K char limit, fallback to raw_text
4. **Embedding Cache** → SHA-256 keyed query_cache table in metadata.db
5. **Parallel Ingestion** → ThreadPoolExecutor with locked upsert, configurable via settings
6. **Structured Logging** → structlog with JSON renderer (production) + console renderer (dev)
7. **Pagination** → Load More pattern with HTMX hx-swap="beforeend", page_size=10
8. **OR Filters** → skills_any/certifications_any fields, toggle UI swaps field names
9. **SSE Streaming** → asyncio.to_thread() runs sync code, yields JSON events, EventSource consumes

---

## File Modifications Summary

| File | Plans Touching | Changes |
|------|----------------|---------|
| `app/main.py` | 07, 08, 09, 10 | Logging config, /search Form fields, /admin/reindex-stream endpoint |
| `app/config.py` | 06, 07 | ingest_workers, log_format settings |
| `app/models.py` | 08, 09 | Pagination fields (page, total_count, has_more), OR filter fields (skills_any, certifications_any) |
| `app/db.py` | 03, 05, 06 | asyncio.Lock, query_cache table, upsert_threaded() |
| `app/search/engine.py` | 02, 08 | parse_json_response(), pagination logic |
| `app/search/embeddings.py` | 03, 05, 07 | threading.Lock, cache lookup, structlog |
| `app/search/filters.py` | 07, 09 | OR logic for skills_any/certifications_any, structlog |
| `app/ingestion/profile_builder.py` | 02, 04, 07 | parse_json_response(), slide-boundary chunking, structlog |
| `app/ingestion/availability.py` | 07 | structlog replacement |
| `app/templates/admin.html` | 10 | EventSource client for SSE |
| `app/templates/search.html` | 08, 09 | Results container, Load More button, AND/OR toggle JS |
| `app/templates/partials/results.html` | 08 | Load More button with HTMX |
| `scripts/ingest_cvs.py` | 04, 06, 07, 10 | Slide extraction, ThreadPoolExecutor, structlog, progress_callback |
| `requirements.txt` | 01, 07 | structlog dependency |
| `pytest.ini` | 01 | (new) Test configuration |
| `tests/conftest.py` | 01 | (new) Shared fixtures |
| `tests/unit/*.py` | 01 | (new) Test stubs (7 files) |
| `tests/integration/*.py` | 01 | (new) Test stubs (6 files) |

---

## Execution Notes

1. **Test Infrastructure First**: Wave 0 (Plan 01) creates all test stubs. Subsequent plans import these and add implementations.

2. **Parallel Execution**: Waves 1, 2, and 3 can overlap in execution. Plans within same wave have no cross-dependencies.

3. **Backward Compatibility**: Old `/admin/reindex` POST endpoint kept functional (Plan 10). Logging switches happen gradually (Plan 07).

4. **Database Safety**: Both asyncio.Lock (async) and threading.Lock (threaded) added to db.py for different contexts. Not mutually exclusive.

5. **Logging Rollout**: Plan 07 replaces logging.getLogger() calls but can coexist during transition. No breaking changes.

6. **UI Patterns**: Plans 08-09 use HTMX for dynamic updates. Plan 10 uses EventSource. Ensure admin.html loads before Plan 10.

---

## Success Criteria for Phase 2

At end of execution, validate:

- [ ] All pytest tests pass: `pytest tests/ --cov=app --cov-report=term-missing`
- [ ] No regression in Phase 1 functionality (existing tests still pass)
- [ ] JSON parsing never crashes on malformed responses
- [ ] Re-index streaming shows live progress in admin UI
- [ ] Pagination works: page 2 returns different results than page 1 (for large result sets)
- [ ] OR filter matches profiles with any skill (not requiring all)
- [ ] Embedding cache hits logged on repeated queries
- [ ] All logs are JSON in production mode (LOG_FORMAT=json)
- [ ] Parallel ingestion processes 4 CVs concurrently without deadlock
- [ ] No "database is locked" errors under concurrent load

---

## Next Steps

1. **Execute Plan 01** (Wave 0) — Creates test infrastructure and fixtures
2. **Execute Plans 02-04** in parallel (Wave 1) — Core robustness fixes
3. **Execute Plans 05-07** in parallel (Wave 2) — Feature additions
4. **Execute Plans 08-10** in parallel (Wave 3) — Search UI features
5. **Run full test suite** and verify success criteria
6. **Commit to git** with detailed commit messages
7. **Transition Phase** → `/gsd:transition` to mark Phase 2 complete

---

*End of Planning Summary*
