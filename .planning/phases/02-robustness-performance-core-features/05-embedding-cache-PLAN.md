---
phase: 02-robustness-performance-core-features
plan: 05
type: execute
wave: 2
depends_on: [02-01, 02-03]
files_modified:
  - app/db.py
  - app/search/embeddings.py
autonomous: true
requirements: [FEAT-07]

must_haves:
  truths:
    - "Embedding generation checks cache before calling model.encode()"
    - "Cache hits are logged and skip model computation"
    - "Cache key is deterministic (SHA-256 of query text)"
  artifacts:
    - path: app/db.py
      provides: "query_cache table schema and cache get/set methods in VectorCollection"
      min_lines: 20
    - path: app/search/embeddings.py
      provides: "generate_embedding() checks cache before encode()"
      min_lines: 10
  key_links:
    - from: app/db.py
      to: tests/unit/test_cache.py::test_cache_hit
      via: "cache table and get/set methods"
      pattern: "query_cache"
    - from: app/search/embeddings.py
      to: tests/unit/test_cache.py::test_cache_key_deterministic
      via: "SHA-256 hashing"
      pattern: "hashlib.sha256"
---

<objective>
Add embedding cache to existing metadata.db to skip re-generating embeddings for repeated queries.

Purpose: Reduce API calls and latency for repeated search queries. Deterministic embeddings allow indefinite cache.

Output:
- query_cache table in metadata.db with SHA-256 key
- Cache lookup in generate_embedding() before model.encode()
- Log all cache hits
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/phases/02-robustness-performance-core-features/02-CONTEXT.md
@.planning/phases/02-robustness-performance-core-features/02-RESEARCH.md

From CONTEXT.md, FEAT-07:
- New `query_cache` table in existing `metadata.db`
- Schema: `(query_hash TEXT PK, embedding TEXT NOT NULL, created_at TEXT)`
- Cache key: SHA-256 hex of query text
- Eviction: None (indefinite; query embeddings are deterministic)
- Files: app/db.py (add cache table + methods), app/search/embeddings.py (cache lookup)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add query_cache table to metadata.db in db.py</name>
  <files>app/db.py</files>
  <action>
In app/db.py VectorCollection class, locate the database initialization code (where tables are created).

Add table creation SQL (if not exists):
```sql
CREATE TABLE IF NOT EXISTS query_cache (
    query_hash TEXT PRIMARY KEY,
    embedding TEXT NOT NULL,
    created_at TEXT NOT NULL
)
```

Also add two methods to VectorCollection class:

1. `get_cached_embedding(query_text: str) -> list[float] | None`:
   - Compute query_hash = hashlib.sha256(query_text.encode()).hexdigest()
   - Query SELECT embedding FROM query_cache WHERE query_hash = ?
   - If found, parse embedding from JSON string (it was stored as JSON) and return as list[float]
   - If not found, return None

2. `set_cached_embedding(query_text: str, embedding: list[float]) -> None`:
   - Compute query_hash as above
   - Insert into query_cache: INSERT OR REPLACE INTO query_cache (query_hash, embedding, created_at) VALUES (?, ?, datetime('now'))
   - Embedding is stored as JSON string: json.dumps(embedding)

Import: `import hashlib`, `import json`
  </action>
  <verify>
    <automated>pytest tests/unit/test_cache.py::test_cache_hit tests/unit/test_cache.py::test_cache_key_deterministic -xvs</automated>
  </verify>
  <done>
query_cache table created, get_cached_embedding() and set_cached_embedding() methods added, both methods work correctly
  </done>
</task>

<task type="auto">
  <name>Task 2: Add cache lookup to generate_embedding() in embeddings.py</name>
  <files>app/search/embeddings.py</files>
  <action>
In app/search/embeddings.py, locate the `generate_embedding()` function (or similar, that calls model.encode()).

Update it to check cache first:

```python
def generate_embedding(text: str, collection: VectorCollection = None) -> list[float]:
    """Generate embedding with cache lookup."""
    # Try cache first
    if collection:
        cached = collection.get_cached_embedding(text)
        if cached:
            logger.info(f"Embedding cache hit for query: {text[:50]}...")
            return cached

    # Cache miss: generate and store
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True).tolist()

    if collection:
        collection.set_cached_embedding(text, embedding)
        logger.info(f"Cached embedding for query: {text[:50]}...")

    return embedding
```

The collection parameter needs to be passed to generate_embedding() from callers in engine.py (during search). For now, pass collection=None as default and update callers in a later task.

Actually, implement this more simply: pass collection when available, None otherwise. Log cache hits/misses.

Log messages should include "(cache hit)" and "(cached)" labels for observability.

Import: `import structlog` (or use existing logging), use `logger.info()` for cache operations
  </action>
  <verify>
    <automated>pytest tests/unit/test_cache.py -xvs</automated>
  </verify>
  <done>
generate_embedding() checks cache before model.encode(), cache hits are logged, deterministic keys verified
  </done>
</task>

</tasks>

<verification>
Run cache tests:
- `pytest tests/unit/test_cache.py::test_cache_hit -xvs` should pass (retrieve cached result)
- `pytest tests/unit/test_cache.py::test_cache_key_deterministic -xvs` should pass (SHA-256 hashing is deterministic)
- Verify logs contain "(cache hit)" messages for repeated queries
</verification>

<success_criteria>
- query_cache table exists in metadata.db
- get_cached_embedding(query_text) and set_cached_embedding(query_text, embedding) methods added
- generate_embedding() checks cache before model.encode()
- Cache key is SHA-256 hash of query text (deterministic)
- Cache hits are logged with query preview
- Both test cases pass (hit and determinism)
</success_criteria>

<output>
After completion, create `.planning/phases/02-robustness-performance-core-features/02-05-SUMMARY.md` documenting:
- query_cache table schema
- Cache methods in VectorCollection
- Integration in generate_embedding()
- Test results confirming cache hit and deterministic keys
</output>
