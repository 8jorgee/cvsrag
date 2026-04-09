# Project State

## Current Phase

**Phase 1: Security & Data Integrity** — Pending

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-09 | Keep FAISS + SQLite vector store | Already migrated from ChromaDB; adequate for 70–80 profiles |
| 2026-04-09 | Use slowapi for rate limiting | Lightweight, FastAPI-native, minimal overhead |
| 2026-04-09 | Use rapidfuzz for name matching | Best Python fuzzy match library, handles Unicode/accents |
| 2026-04-09 | Use structlog for logging | Structured JSON output, colored dev mode, standard in FastAPI ecosystem |
| 2026-04-09 | Use pytest for test suite | Standard Python testing, integrates well with FastAPI TestClient |
| 2026-04-09 | Use threading.Lock for embedding model | Simpler than aiosqlite migration, sufficient for current concurrency |
| 2026-04-09 | Profile IDs based on parsed name UUID | Stable across file renames, avoids duplicate profiles |

## Phase History

*(empty — no phases completed yet)*

## Open Questions

- Fuzzy match threshold for name matching: default 85 WRatio? (configurable in .env)
- Pagination default page_size: 10 or 20?
- Rate limit: 30 req/min per IP — confirm acceptable for internal use?

## Notes

- README references ChromaDB but actual implementation uses FAISS + SQLite (db.py)
- README should be updated after Phase 2 (out of scope for Phase 1)
