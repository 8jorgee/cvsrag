---
phase: 02-robustness-performance-core-features
plan: 06
type: execute
wave: 2
depends_on: [02-01, 02-03, 02-04]
files_modified:
  - scripts/ingest_cvs.py
  - app/config.py
  - app/db.py
autonomous: true
requirements: [FEAT-02]

must_haves:
  truths:
    - "Multiple CV files are processed concurrently (ThreadPoolExecutor with max_workers=4)"
    - "Database upserts are serialized with threading.Lock to prevent corruption"
    - "Parallel ingestion completes without deadlock or 'database is locked' errors"
  artifacts:
    - path: scripts/ingest_cvs.py
      provides: "Refactored to use ThreadPoolExecutor for parallel CV processing"
      min_lines: 20
    - path: app/config.py
      provides: "Added ingest_workers: int = 4 configuration"
      min_lines: 2
    - path: app/db.py
      provides: "threading.Lock on VectorCollection.upsert() for thread-safe writes"
      min_lines: 5
  key_links:
    - from: scripts/ingest_cvs.py
      to: app/db.py
      via: "ThreadPoolExecutor calls collection.upsert_threaded()"
      pattern: "ThreadPoolExecutor"
    - from: app/config.py
      to: scripts/ingest_cvs.py
      via: "ingest_workers setting"
      pattern: "settings.ingest_workers"
---

<objective>
Implement parallel CV ingestion using ThreadPoolExecutor with configurable worker count.

Purpose: Process multiple CVs concurrently, reducing overall ingestion time. Thread-safe upsert prevents database corruption.

Output:
- ingest_cvs.py refactored to use ThreadPoolExecutor(max_workers=4)
- ingest_workers configurable in settings (default 4)
- threading.Lock on collection.upsert() in db.py
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/phases/02-robustness-performance-core-features/02-CONTEXT.md
@.planning/phases/02-robustness-performance-core-features/02-RESEARCH.md

From CONTEXT.md, FEAT-02:
- ThreadPoolExecutor with max_workers=4 (configurable via settings.ingest_workers)
- Thread safety: wrap collection.upsert() in a per-collection threading.Lock (separate from asyncio.Lock)
- Strategy: Fan out per-file processing (extract + parse + embed) in parallel; collect results; serial upsert (or locked parallel)
- Files: scripts/ingest_cvs.py, app/config.py (add ingest_workers: int = 4), app/db.py (threading.Lock on upsert)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add ingest_workers configuration to app/config.py</name>
  <files>app/config.py</files>
  <action>
In app/config.py, locate the Settings class (Pydantic model or similar).

Add a new field:
```python
ingest_workers: int = 4  # Number of parallel workers for CV ingestion
```

Add a field description/validation if using Pydantic:
```python
ingest_workers: int = Field(default=4, description="Number of parallel workers for CV ingestion, configurable via INGEST_WORKERS env var")
```

Ensure the field is optional and defaults to 4 if not set. It can be overridden via environment variable or .env file.
  </action>
  <verify>
    <automated>python -c "from app.config import settings; print(f'ingest_workers: {settings.ingest_workers}')"</automated>
  </verify>
  <done>
ingest_workers added to Settings, defaults to 4, environment variable override working
  </done>
</task>

<task type="auto">
  <name>Task 2: Add threading.Lock to VectorCollection.upsert() in db.py</name>
  <files>app/db.py</files>
  <action>
In app/db.py VectorCollection.__init__, add a threading.Lock for parallel ingestion:

```python
from threading import Lock as ThreadingLock

class VectorCollection:
    def __init__(self, ...):
        # ... existing initialization ...
        self._upsert_lock = ThreadingLock()  # Separate from asyncio.Lock
```

Now update the `upsert()` method to acquire the lock (or create a wrapper method):

Option A: Wrap existing upsert() in a new method:
```python
def upsert_threaded(self, ids, embeddings, documents, metadatas):
    """Thread-safe wrapper for ThreadPoolExecutor."""
    with self._upsert_lock:
        self.upsert(ids, embeddings, documents, metadatas)
```

Option B: Modify upsert() directly (not recommended if async code also uses it):
Keep the original upsert() unwrapped and create upsert_threaded() for threading use.

For this task, create `upsert_threaded()` as a new method that wraps the lock around the original upsert().

Import: `from threading import Lock`
  </action>
  <verify>
    <automated>pytest tests/integration/test_parallel_ingest.py::test_consistency_parallel -xvs</automated>
  </verify>
  <done>
threading.Lock (_upsert_lock) added to VectorCollection, upsert_threaded() method created and thread-safe
  </done>
</task>

<task type="auto">
  <name>Task 3: Refactor ingest_cvs.py to use ThreadPoolExecutor</name>
  <files>scripts/ingest_cvs.py</files>
  <action>
In scripts/ingest_cvs.py, locate the main ingestion loop (currently processes files sequentially).

Refactor to use ThreadPoolExecutor:

1. Import: `from concurrent.futures import ThreadPoolExecutor`
2. Extract per-file processing into a function `process_cv_file(filepath: str, collection: VectorCollection, ...) -> dict`:
   - Parse PPTX (extract raw_text, slides_content)
   - Call parse_profile_with_claude()
   - Generate embeddings
   - Return result dict with status, profile_id, etc.

3. In main ingestion loop, use ThreadPoolExecutor:
```python
from app.config import settings

with ThreadPoolExecutor(max_workers=settings.ingest_workers) as executor:
    futures = []
    for filepath in cv_files:
        future = executor.submit(
            process_cv_file,
            filepath,
            collection,
            settings  # Pass settings
        )
        futures.append(future)

    # Collect results (this blocks until all workers complete)
    results = [future.result() for future in futures]
```

4. After all files are processed, upsert results:
```python
for result in results:
    if result['status'] == 'ok':
        collection.upsert_threaded(
            ids=[result['profile_id']],
            embeddings=[result['embedding']],
            documents=[result['document']],
            metadatas=[result['metadata']]
        )
```

Ensure ingest_cvs.py is still callable as a CLI script (if __name__ == '__main__' block).

This plan keeps ingest_cvs.py importable for SSE streaming in ROB-05 (later plan).
  </action>
  <verify>
    <automated>pytest tests/integration/test_parallel_ingest.py::test_parallel_executor tests/integration/test_parallel_ingest.py::test_consistency_parallel -xvs</automated>
  </verify>
  <done>
ingest_cvs.py refactored to use ThreadPoolExecutor, parallel processing verified, no deadlock or database errors
  </done>
</task>

</tasks>

<verification>
Run parallel ingestion tests:
- `pytest tests/integration/test_parallel_ingest.py -xvs` should pass both tests (executor runs concurrently, consistency maintained)
- Verify that 4 workers are used by default
- Verify no "database is locked" errors
- Manual check: `python scripts/ingest_cvs.py --help` still works, CLI remains functional
</verification>

<success_criteria>
- ingest_workers: int = 4 added to Settings
- threading.Lock (_upsert_lock) in VectorCollection.__init__
- upsert_threaded() method wraps original upsert() with lock
- ingest_cvs.py uses ThreadPoolExecutor(max_workers=settings.ingest_workers)
- Per-file processing extracted into separate function
- All parallel upserts use collection.upsert_threaded()
- Both test cases pass (concurrent execution, consistency verified)
</success_criteria>

<output>
After completion, create `.planning/phases/02-robustness-performance-core-features/02-06-SUMMARY.md` documenting:
- ThreadPoolExecutor integration in ingest_cvs.py
- threading.Lock implementation in db.py
- ingest_workers configuration
- Test results confirming parallel execution and consistency
</output>
