---
phase: 1
slug: security-data-integrity
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini / pyproject.toml — Wave 0 installs |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | SEC-01 | integration | `pytest tests/test_security.py::test_csrf_missing_token_rejected -x` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | SEC-02 | unit | `pytest tests/test_search.py::test_query_length_validation -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | SEC-03 | unit | `pytest tests/test_startup.py::test_missing_api_key_raises -x` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | SEC-04 | integration | `pytest tests/test_security.py::test_rate_limit_exceeded -x` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 1 | SEC-05 | unit | `pytest tests/test_upload.py::test_mime_type_validation -x` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | DATA-01 | unit | `pytest tests/test_availability.py::test_accent_name_match -x` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | DATA-02 | unit | `pytest tests/test_db.py::test_upsert_atomicity -x` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 1 | DATA-03 | unit | `pytest tests/test_ingestion.py::test_stable_profile_id -x` | ❌ W0 | ⬜ pending |
| 1-02-04 | 02 | 1 | DATA-04 | unit | `pytest tests/test_ingestion.py::test_availability_delta_detection -x` | ❌ W0 | ⬜ pending |
| 1-02-05 | 02 | 1 | DATA-05 | unit | `pytest tests/test_filters.py::test_malformed_date_excluded -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — empty init
- [ ] `tests/conftest.py` — shared fixtures (FastAPI TestClient, mock DB, mock Anthropic client)
- [ ] `tests/test_security.py` — stubs for SEC-01 (CSRF), SEC-04 (rate limit)
- [ ] `tests/test_search.py` — stubs for SEC-02 (query length validation)
- [ ] `tests/test_startup.py` — stubs for SEC-03 (missing API key)
- [ ] `tests/test_upload.py` — stubs for SEC-05 (MIME type validation)
- [ ] `tests/test_availability.py` — stubs for DATA-01 (accent name matching)
- [ ] `tests/test_db.py` — stubs for DATA-02 (upsert atomicity)
- [ ] `tests/test_ingestion.py` — stubs for DATA-03 (stable IDs), DATA-04 (delta detection)
- [ ] `tests/test_filters.py` — stubs for DATA-05 (malformed dates)
- [ ] `pytest` added to requirements.txt if not present

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| HTMX form visually submits with CSRF token included | SEC-01 | Browser DevTools needed | Open admin, submit reindex form, check Network tab for X-CSRF-Token header |
| Rate limit returns 429 in browser | SEC-04 | Browser UX verification | Submit search 31 times rapidly, verify 429 page shown |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
