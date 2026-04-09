---
phase: 02-robustness-performance-core-features
plan: 03
type: execute
wave: 1
depends_on: [02-01]
files_modified:
  - app/search/embeddings.py
  - app/db.py
autonomous: true
requirements: [ROB-02, ROB-03]

must_haves:
  truths:
    - "Embedding model initializes once and is thread-safe across concurrent callers"
    - "SQLite upserts under async concurrent load do not raise 'database is locked' errors"
    - "Multiple threads/async tasks can safely call get_model() and upsert() without deadlock"
  artifacts:
    - path: app/search/embeddings.py
      provides: "threading.Lock guard on _model initialization in get_model()"
      min_lines: 10
    - path: app/db.py
      provides: "asyncio.Lock in VectorCollection for SQLite write serialization"
      min_lines: 10
  key_links:
    - from: app/search/embeddings.py
      to: tests/unit/test_embeddings.py::test_concurrent_model_loading
      via: "threading.Lock"
      pattern: "_model_lock"
    - from: app/db.py
      to: tests/integration/test_db_async.py::test_concurrent_upsert
      via: "asyncio.Lock"
      pattern: "_sqlite_write_lock"
---

<objective>
Add thread-safety to embedding model loading (ROB-02) and SQLite write serialization (ROB-03).

Purpose: Prevent race conditions when multiple threads/tasks initialize the model or write to the database.

Output:
- threading.Lock in embeddings.py guarding _model
- asyncio.Lock in db.py VectorCollection guarding async writes
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/phases/02-robustness-performance-core-features/02-CONTEXT.md
@.planning/phases/02-robustness-performance-core-features/02-RESEARCH.md

From RESEARCH.md, Pattern 1: Thread-Safe Embedding Model (ROB-02):
- Lock is acquired BEFORE checking `if _model is None`
- Only first thread enters init; others block and skip
- Model is cached after first load — subsequent calls are lock-free fast path

From RESEARCH.md, Pattern 2: Async Lock for SQLite (ROB-03):
- `asyncio.Lock` serializes async SQLite access
- Subsequent async writes block until lock is released
- WAL mode still handles concurrent reads
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add threading.Lock to embeddings.py for model initialization</name>
  <files>app/search/embeddings.py</files>
  <action>
In app/search/embeddings.py, locate the global `_model` variable and the `get_model()` function.

Add:
1. Import statement: `import threading`
2. Global variable after `_model`: `_model_lock = threading.Lock()`
3. Update `get_model()` function to wrap model initialization:

```python
def get_model() -> SentenceTransformer:
    global _model
    with _model_lock:  # Acquire lock
        if _model is None:
            logger.info(f"Loading embedding model: {settings.embedding_model}")
            _model = SentenceTransformer(settings.embedding_model)
    return _model
```

Ensure lock is acquired BEFORE the `if _model is None` check (critical for thread safety).

If get_model() does not exist, create it as a wrapper that returns the global _model with lock protection.

Do NOT modify the model itself or the generate_embedding() function in this task (that's handled in Task 2 of later plans).
  </action>
  <verify>
    <automated>pytest tests/unit/test_embeddings.py::test_concurrent_model_loading -xvs</automated>
  </verify>
  <done>
threading.Lock in place, get_model() synchronizes initialization, test passes (no deadlock, same model object returned)
  </done>
</task>

<task type="auto">
  <name>Task 2: Add asyncio.Lock to db.py for SQLite write serialization</name>
  <files>app/db.py</files>
  <action>
In app/db.py, locate the `VectorCollection` class definition and `__init__` method.

Add:
1. Import statement: `import asyncio`
2. In `__init__`, after any existing initialization, add: `self._sqlite_write_lock = asyncio.Lock()`
3. Create (or update if exists) an async method `upsert_async()` that:
   - Acquires `self._sqlite_write_lock`
   - Calls the synchronous `self.upsert()` within `asyncio.to_thread()` to avoid blocking the event loop
   - Returns normally

Example:
```python
async def upsert_async(self, ids, embeddings, documents, metadatas):
    """Async wrapper around synchronous upsert."""
    async with self._sqlite_write_lock:  # Only one async writer at a time
        await asyncio.to_thread(
            self.upsert, ids, embeddings, documents, metadatas
        )
```

Do NOT modify the synchronous `upsert()` method. The lock is only for async callers.

For FEAT-02 (parallel ingestion with ThreadPoolExecutor), a separate threading.Lock will be added in a later plan.
  </action>
  <verify>
    <automated>pytest tests/integration/test_db_async.py::test_concurrent_upsert -xvs</automated>
  </verify>
  <done>
asyncio.Lock in VectorCollection, upsert_async() method created, concurrent async upserts pass without "database is locked" errors
  </done>
</task>

</tasks>

<verification>
Run both concurrency tests:
- `pytest tests/unit/test_embeddings.py::test_concurrent_model_loading -xvs` should pass (no deadlock, same model)
- `pytest tests/integration/test_db_async.py::test_concurrent_upsert -xvs` should pass (no database locked errors)
</verification>

<success_criteria>
- threading.Lock (_model_lock) added to embeddings.py
- get_model() acquires lock before checking/initializing _model
- asyncio.Lock (_sqlite_write_lock) added to VectorCollection.__init__
- upsert_async() method created with lock + asyncio.to_thread()
- Both test cases pass: concurrent model loading and concurrent async upserts
</success_criteria>

<output>
After completion, create `.planning/phases/02-robustness-performance-core-features/02-03-SUMMARY.md` documenting:
- Thread safety mechanism in embeddings.py
- Async lock mechanism in db.py
- Test results confirming no deadlock or database errors
</output>
