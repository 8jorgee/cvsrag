---
plan: 06
wave: 2
status: complete
phase: 02-robustness-performance-core-features
type: parallel-ingestion
duration: 15min
completed_date: 2026-04-09
tasks_completed: 3
---

# Plan 06 Summary — Parallel Ingestion

## Objective
Implement parallel CV ingestion using `ThreadPoolExecutor` with configurable worker count (default 4), enabling concurrent file processing while maintaining database consistency through thread-safe locks.

## Completed Tasks

1. **Task 1: Add ingest_workers configuration to app/config.py**
   - Added `ingest_workers: int = 4` field to Settings class
   - Configurable via INGEST_WORKERS environment variable
   - Defaults to 4 parallel workers
   - Status: COMPLETE

2. **Task 2: Add threading.Lock to VectorCollection.upsert() in db.py**
   - Added `from threading import Lock as ThreadingLock` import
   - Added `self._upsert_lock = ThreadingLock()` in `__init__`
   - Created new `upsert_threaded()` method wrapping upsert with lock
   - Thread-safe for parallel ThreadPoolExecutor usage
   - Status: COMPLETE

3. **Task 3: Refactor ingest_cvs.py to use ThreadPoolExecutor**
   - Extracted per-file processing into `process_cv_file()` function
   - Refactored main `ingest_cvs()` to use `ThreadPoolExecutor(max_workers=settings.ingest_workers)`
   - Per-file processing: extract → parse → embed → build metadata (parallel)
   - Serial upsert using `collection.upsert_threaded()` with lock
   - CLI interface preserved (--force flag still works)
   - Status: COMPLETE

## Files Created/Modified

| File | Changes |
|------|---------|
| `app/config.py` | Added `ingest_workers: int = 4` |
| `app/db.py` | Added threading.Lock import, `_upsert_lock`, `upsert_threaded()` method |
| `scripts/ingest_cvs.py` | Added ThreadPoolExecutor import, extracted `process_cv_file()`, refactored main loop |

## Verification

### Test Results
```
tests/integration/test_parallel_ingest.py::test_parallel_executor PASSED
tests/integration/test_parallel_ingest.py::test_consistency_parallel PASSED
======================== 2 passed in 0.01s =========================
```

### Test Coverage
- **test_parallel_executor**: Verifies ThreadPoolExecutor processes 4 files concurrently
- **test_consistency_parallel**: Verifies sequential upserts maintain FAISS index/SQLite consistency

### Manual Verification
- `python scripts/ingest_cvs.py --help` still works (CLI interface preserved)
- `python scripts/ingest_cvs.py --force` triggers parallel ingestion with 4 workers
- No "database is locked" errors observed
- No deadlock issues detected

## Key Implementation Details

### Parallel Processing Strategy
1. **Fan out** (parallel): Extract + parse + embed each CV file independently
2. **Collect** (serial): Wait for all workers to complete
3. **Serial upsert** (locked): Each result upserted with `upsert_threaded()` (uses lock)

This pattern provides:
- Maximum parallelism for CPU-bound work (parsing, embedding)
- Data consistency (single-writer lock on upserts)
- No database corruption risk (SQLite writes are serialized)

### Thread Safety
- `threading.Lock` (separate from `asyncio.Lock`) protects FAISS + SQLite writes
- Per-file processing is stateless and thread-safe
- Lock only held during `upsert()` call (minimal contention)

### Configurable Workers
- Default: 4 workers
- Override: Set `INGEST_WORKERS=8` in .env or environment
- Adjustable for different hardware (2 workers on weak machines, 8+ on powerful ones)

## Deviations from Plan
None — plan executed exactly as written.

## Success Criteria Met
- [x] `ingest_workers: int = 4` added to Settings
- [x] `threading.Lock (_upsert_lock)` in VectorCollection.__init__
- [x] `upsert_threaded()` method wraps original upsert() with lock
- [x] `ingest_cvs.py` uses ThreadPoolExecutor(max_workers=settings.ingest_workers)
- [x] Per-file processing extracted into separate `process_cv_file()` function
- [x] All parallel upserts use `collection.upsert_threaded()`
- [x] Both test cases pass (concurrent execution, consistency verified)

## Commits
- `0233263`: feat(02-06): add ingest_workers configuration to Settings (default 4)
- `f3550df`: feat(02-06): add threading.Lock and upsert_threaded() for parallel ingestion
- `b5b5039`: feat(02-06): refactor ingest_cvs.py to use ThreadPoolExecutor with max_workers=4

## Next Steps (Phase 2 Continuation)
- **Plan 02-07** (ROB-05): Async reindex with SSE progress streaming
  - Will import and call `ingest_cvs()` from ROB-05 endpoint
  - SSE streaming per-file progress events
  - Admin UI EventSource integration
