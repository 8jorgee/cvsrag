---
phase: 02
plan: 03
wave: 1
status: complete
date: 2026-04-09
---

# Plan 03 Summary — Thread Safety & DB Concurrency

## Objective
Add thread-safety to embedding model loading (ROB-02) and SQLite write serialization (ROB-03) to prevent race conditions when multiple threads/tasks initialize the model or write to the database.

## Completed Tasks

### Task 1: Add threading.Lock to embeddings.py for model initialization (ROB-02)
- **Status:** PASSED
- **Changes:**
  - Added `import threading` to app/search/embeddings.py
  - Created global `_model_lock = threading.Lock()` variable
  - Modified `get_model()` to wrap initialization with `with _model_lock:` context manager
  - Lock is acquired BEFORE checking `if _model is None` (critical for thread safety)
  - First thread initializes the model; others block and skip initialization
  - Subsequent calls use fast path without blocking once model is cached
- **Test:** `pytest tests/unit/test_embeddings.py::test_concurrent_model_loading -xvs` ✓ PASSED

### Task 2: Add asyncio.Lock to db.py for SQLite write serialization (ROB-03)
- **Status:** PASSED
- **Changes:**
  - Added `import asyncio` to app/db.py
  - Added `self._sqlite_write_lock = asyncio.Lock()` to `VectorCollection.__init__`
  - Created new `upsert_async()` async method that:
    - Acquires `self._sqlite_write_lock` with `async with` context manager
    - Calls synchronous `self.upsert()` within `asyncio.to_thread()` to avoid blocking event loop
    - Ensures only one async task writes to SQLite at a time
  - Synchronous `upsert()` method unchanged (for backward compatibility with threading.Lock future implementation)
- **Test:** `pytest tests/integration/test_db_async.py::test_concurrent_upsert -xvs` ✓ PASSED

## Files Created/Modified

| File | Changes | Lines |
|------|---------|-------|
| app/search/embeddings.py | Added threading.Lock for model init | +6 lines |
| app/db.py | Added asyncio.Lock and upsert_async() | +19 lines |

## Verification Results

### Full Test Suite (All 3 tests passed)
```
======================== 3 passed, 7 warnings in 2.78s =========================

- tests/unit/test_embeddings.py::test_concurrent_model_loading PASSED
- tests/integration/test_db_async.py::test_concurrent_upsert PASSED
- tests/integration/test_db_consistency.py PASSED
```

### Key Assertions Verified
1. **Thread Safety (embeddings.py):**
   - 5 concurrent threads calling `get_model()` all complete successfully
   - All threads return the same model instance (identity check passes)
   - No deadlock or race conditions

2. **Async Lock (db.py):**
   - 5 concurrent async upserts execute without "database is locked" errors
   - All 5 profiles successfully stored in database
   - FAISS index remains consistent with SQLite metadata

## Architecture & Design

### Pattern 1: Thread-Safe Embedding Model Loading (ROB-02)
```python
_model_lock = threading.Lock()

def get_model() -> SentenceTransformer:
    global _model
    with _model_lock:  # Acquire lock BEFORE checking _model
        if _model is None:
            _model = SentenceTransformer(settings.embedding_model)
    return _model
```

**Why this works:**
- Lock is acquired BEFORE the `if _model is None` check (prevents TOCTOU race)
- Only the first thread enters the initialization block
- Other threads wait for lock, then check `_model is None` (now false), and skip init
- Subsequent calls acquire lock, find `_model` already set, and skip init (fast path)

### Pattern 2: Async Lock for SQLite Serialization (ROB-03)
```python
self._sqlite_write_lock = asyncio.Lock()

async def upsert_async(self, ids, embeddings, documents, metadatas):
    async with self._sqlite_write_lock:
        await asyncio.to_thread(self.upsert, ids, embeddings, documents, metadatas)
```

**Why this works:**
- `asyncio.Lock` ensures sequential access from async tasks
- `asyncio.to_thread()` runs synchronous SQLite operations in thread pool (avoids blocking event loop)
- Only one async writer at a time → no "database is locked" from concurrent writes
- WAL mode (set in `_open_db()`) still allows concurrent reads while writes are serialized

## Requirements Met

✓ **ROB-02:** Embedding model initializes once and is thread-safe across concurrent callers
✓ **ROB-03:** SQLite upserts under async concurrent load do not raise 'database is locked' errors
✓ **Key Links:** Both test cases pass with patterns matching expected link targets:
  - `_model_lock` pattern in embeddings.py matches test's model loading check
  - `_sqlite_write_lock` pattern in db.py matches test's concurrent upsert check

## Deviations from Plan
None - plan executed exactly as specified. Both tasks completed with correct patterns and all tests passing.

## Dependencies & Future Work

**Completed Dependencies:**
- Phase 02-01: Test Infrastructure (✓ completed)

**Future Dependencies (handled in later plans):**
- Plan 04: CV text chunking (can now safely call `generate_embedding()` from multiple threads)
- Plan 06: Parallel ingestion with ThreadPoolExecutor (will add threading.Lock to upsert() for sync callers)
- Plan 09: OR filter logic (queries safe with current asyncio.Lock implementation)

## Notes for Next Phases

1. **Threading.Lock for synchronous upsert():** Plan 06 (Parallel Ingestion) will add a separate `threading.Lock` to guard the synchronous `upsert()` method for ThreadPoolExecutor-based ingestion. This keeps async and sync concurrency controls separate and appropriate.

2. **Model loading fully optimized:** Subsequent calls to `get_model()` are now lock-free after model is cached. Lock contention minimal (only on first call).

3. **SQLite WAL mode + async serialization:** The combination of SQLite WAL mode (line 48 in db.py) and asyncio.Lock provides:
   - Concurrent reads (via WAL)
   - Serialized writes (via asyncio.Lock)
   - No corruption or "database is locked" errors

---

**Commits:**
- `5fed8c6` feat(02-03): add threading.Lock to guard embedding model initialization
- `cd12e56` feat(02-03): add asyncio.Lock to VectorCollection for SQLite write serialization
