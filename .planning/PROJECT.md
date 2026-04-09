# Team Profile RAG — Improvement Milestone

## What This Is

An internal RAG system for searching ~70–80 consulting team member profiles by skills, experience, certifications, and availability. The system is already functional; this milestone hardens it for production use by fixing identified bugs and adding high-value features.

## Core Value

Reliable, accurate talent search — consultants find the right person for a project in seconds, with availability data they can trust.

## Context

- **Stack**: FastAPI + Python 3.11, Jinja2 + HTMX, FAISS + SQLite (replaced ChromaDB), sentence-transformers (all-MiniLM-L6-v2), Anthropic Claude claude-sonnet-4-20250514, python-pptx
- **Scale**: ~70–80 consultant profiles, internal use
- **State**: Working MVP; needs security hardening, reliability improvements, and new features
- **Note**: README says ChromaDB but actual implementation uses custom FAISS + SQLite

## Requirements

### Validated

- ✓ Full-text + semantic search over consultant profiles — existing
- ✓ Faceted filters (skills, availability, grade, location) — existing
- ✓ Claude-powered reranking and match reasoning — existing
- ✓ Admin panel with auth (upload CVs, availability CSV, re-index) — existing
- ✓ PPTX CV parsing with Claude-powered structured extraction — existing
- ✓ Docker deployment with volume persistence — existing

### Active

**Security & Reliability Fixes**
- [ ] CSRF protection on HTMX admin forms
- [ ] Availability name matching normalized (case/accent insensitive)
- [ ] FAISS + SQLite transaction safety
- [ ] ANTHROPIC_API_KEY validated at startup
- [ ] Robust JSON parsing (replace fragile regex extraction)
- [ ] Stable profile IDs (not MD5 of filename)
- [ ] Availability delta tracking in incremental ingestion
- [ ] Search query length validation (cap at 500 chars)
- [ ] Thread-safe embedding model loading
- [ ] Async reindex (non-blocking, SSE progress)
- [ ] CV text truncation increased (8000 → 16000 chars + slide-boundary chunking)
- [ ] Date parsing errors in filters handled explicitly
- [ ] Pagination for search results
- [ ] Rate limiting on /search endpoint (30 req/min per IP)
- [ ] SQLite concurrency safety (serialize via lock or aiosqlite)

**New Features**
- [ ] Fuzzy name matching for availability lookups (rapidfuzz)
- [ ] Availability delta tracking (only re-ingest changed rows)
- [ ] Parallel ingestion (ThreadPoolExecutor, default 4 workers)
- [ ] Result export (CSV/Excel download of search results)
- [ ] Search history (last 20 searches per session, shown in UI)
- [ ] Skill gap analysis page (required skills → who covers what)
- [ ] Team composition assistant (project type → AI-suggested team)
- [ ] Embedding cache (SQLite-backed, skip re-generation for repeated queries)
- [ ] Profile diff view (what changed when CV is re-indexed)
- [ ] Test suite (pytest, unit + integration)
- [ ] Async reindex with SSE progress stream
- [ ] Structured logging (structlog, JSON in prod / colored in dev)
- [ ] OR logic in filters (skills_any / certifications_any fields)

### Out of Scope

- SharePoint connector — future milestone
- Multi-language name extraction — future
- FAISS → scalable vector DB migration — future (current scale doesn't require it)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep FAISS + SQLite | Already migrated from ChromaDB; adequate for 70–80 profiles | Confirmed |
| slowapi for rate limiting | Lightweight, FastAPI-native | — Pending |
| rapidfuzz for name matching | Best Python fuzzy match library, handles accents | — Pending |
| structlog for logging | Structured JSON output, colored dev mode, FastAPI-idiomatic | — Pending |
| pytest for test suite | Standard Python testing, easy FastAPI integration | — Pending |
| aiosqlite or threading.Lock for concurrency | Serialize SQLite access safely | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions

---
*Last updated: 2026-04-09 after initialization*
