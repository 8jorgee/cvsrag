---
phase: 2
slug: robustness-performance-core-features
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-09
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4.4 (already in requirements.txt) |
| **Config file** | `pytest.ini` — Wave 0 creates it |
| **Quick run command** | `pytest tests/ -m "not slow" -x` |
| **Full suite command** | `pytest tests/ --cov=app --cov-report=term-missing` |
| **Estimated runtime** | ~30 seconds (unit) / ~90 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -m "not slow" -x`
- **After every plan wave:** Run `pytest tests/ --cov=app --cov-report=term-missing`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| ROB-01 | JSON parsing succeeds on clean response | unit | `pytest tests/unit/test_json_parsing.py::test_clean_json -xvs` | ❌ W0 | ⬜ pending |
| ROB-01 | JSON parsing succeeds on markdown-wrapped response | unit | `pytest tests/unit/test_json_parsing.py::test_markdown_json -xvs` | ❌ W0 | ⬜ pending |
| ROB-01 | JSON parsing raises on unparseable response | unit | `pytest tests/unit/test_json_parsing.py::test_invalid_json_raises -xvs` | ❌ W0 | ⬜ pending |
| ROB-02 | Embedding model initialization is thread-safe | unit | `pytest tests/unit/test_embeddings.py::test_concurrent_model_loading -xvs` | ❌ W0 | ⬜ pending |
| ROB-03 | SQLite upsert under async concurrent load | integration | `pytest tests/integration/test_db_async.py::test_concurrent_upsert -xvs` | ❌ W0 | ⬜ pending |
| ROB-03 | FAISS and SQLite remain in sync after concurrent upsert | integration | `pytest tests/integration/test_db_consistency.py -xvs` | ❌ W0 | ⬜ pending |
| ROB-04 | Text chunking respects 16K char boundary | unit | `pytest tests/unit/test_chunking.py::test_slide_boundary_chunk -xvs` | ❌ W0 | ⬜ pending |
| ROB-04 | Chunking preserves slide boundaries (no mid-slide cut) | unit | `pytest tests/unit/test_chunking.py::test_no_mid_slide_cutoff -xvs` | ❌ W0 | ⬜ pending |
| ROB-05 | SSE stream endpoint returns text/event-stream | integration | `pytest tests/integration/test_sse.py::test_reindex_stream_content_type -xvs` | ❌ W0 | ⬜ pending |
| ROB-05 | SSE events are valid JSON | integration | `pytest tests/integration/test_sse.py::test_sse_json_format -xvs` | ❌ W0 | ⬜ pending |
| SEARCH-01 | Pagination returns correct page size | unit | `pytest tests/unit/test_pagination.py::test_page_size_10 -xvs` | ❌ W0 | ⬜ pending |
| SEARCH-01 | Pagination returns correct total count | unit | `pytest tests/unit/test_pagination.py::test_total_count_accurate -xvs` | ❌ W0 | ⬜ pending |
| SEARCH-01 | Load More flag set when has_more=True | unit | `pytest tests/unit/test_pagination.py::test_has_more_flag -xvs` | ❌ W0 | ⬜ pending |
| SEARCH-02 | OR filter matches any skill in list | unit | `pytest tests/unit/test_filters.py::test_skills_any_matches -xvs` | ❌ W0 | ⬜ pending |
| SEARCH-02 | AND filter requires all skills | unit | `pytest tests/unit/test_filters.py::test_skills_all_required -xvs` | ❌ W0 | ⬜ pending |
| FEAT-02 | Parallel ingestion processes multiple files concurrently | integration | `pytest tests/integration/test_parallel_ingest.py::test_parallel_executor -xvs` | ❌ W0 | ⬜ pending |
| FEAT-02 | Parallel ingestion maintains FAISS/SQLite sync | integration | `pytest tests/integration/test_parallel_ingest.py::test_consistency_parallel -xvs` | ❌ W0 | ⬜ pending |
| FEAT-07 | Embedding cache returns cached result on hit | unit | `pytest tests/unit/test_cache.py::test_cache_hit -xvs` | ❌ W0 | ⬜ pending |
| FEAT-07 | Cache key is deterministic (SHA-256) | unit | `pytest tests/unit/test_cache.py::test_cache_key_deterministic -xvs` | ❌ W0 | ⬜ pending |
| FEAT-10 | Logs output JSON in production mode | unit | `pytest tests/unit/test_logging.py::test_json_output -xvs` | ❌ W0 | ⬜ pending |
| FEAT-10 | Logs output colored console in dev mode | unit | `pytest tests/unit/test_logging.py::test_console_colored -xvs` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — Shared fixtures for database, async client, temp dirs
- [ ] `pytest.ini` — Configure asyncio mode and test paths
- [ ] `tests/unit/test_json_parsing.py` — Stubs for ROB-01 (clean, markdown, invalid)
- [ ] `tests/unit/test_embeddings.py` — Thread-safe model loading under concurrent load
- [ ] `tests/unit/test_chunking.py` — Slide boundary chunking with edge cases
- [ ] `tests/unit/test_pagination.py` — Page size, total count, has_more flag
- [ ] `tests/unit/test_filters.py` — AND/OR filter logic correctness
- [ ] `tests/unit/test_cache.py` — Cache hit/miss, SHA-256 determinism
- [ ] `tests/unit/test_logging.py` — JSON and colored console output formats
- [ ] `tests/integration/test_db_async.py` — Concurrent upsert with asyncio.Lock
- [ ] `tests/integration/test_db_consistency.py` — FAISS/SQLite sync verification
- [ ] `tests/integration/test_sse.py` — SSE endpoint content type and JSON events
- [ ] `tests/integration/test_parallel_ingest.py` — ThreadPoolExecutor with locking

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Admin UI switches from fetch POST to EventSource on Re-index | ROB-05 | Browser JS behavior, not testable with pytest | Open /admin, click Re-index, observe log-box updates line-by-line as SSE events arrive |
| Load More button appends results below existing results | SEARCH-01 | HTMX hx-swap="beforeend" DOM behavior | Search for any query, click Load More, verify new cards appended (not replaced) |
| AND/OR toggle switches field names in form | SEARCH-02 | JS DOM manipulation of form field names | Open search page, click OR toggle on Skills, submit, verify skills_any param in request |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
