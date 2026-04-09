---
plan: 05
wave: 2
status: complete
date: 2026-04-09
---

# Plan 05 Summary — Embedding Cache (FEAT-07)

## Objective
Add embedding cache to existing `metadata.db` to skip re-generating embeddings for repeated queries. Reduces API calls and latency for repeated search queries.

## Completed Tasks

1. **Task 1: Add query_cache table to metadata.db in db.py** ✓
   - Created `query_cache` table with schema: `(query_hash TEXT PK, embedding TEXT NOT NULL, created_at TEXT)`
   - Implemented `get_cached_embedding(query_text: str) -> list[float] | None` method
   - Implemented `set_cached_embedding(query_text: str, embedding: list[float]) -> None` method
   - Both methods compute SHA-256 hash of query text for deterministic cache keys
   - Embedding stored/retrieved as JSON string

2. **Task 2: Add cache lookup to generate_embedding() in embeddings.py** ✓
   - Updated `generate_embedding()` to accept optional `collection` parameter
   - Checks cache before calling `model.encode()` for performance
   - Logs cache hits with query preview: `"Embedding cache hit for query: {text[:50]}..."`
   - Logs cache stores with query preview: `"Cached embedding for query: {text[:50]}..."`
   - Gracefully handles missing collection (None) with backward compatibility

3. **Task 3: Create EmbeddingCache wrapper class** ✓
   - Created `app/search/cache.py` with `EmbeddingCache` class
   - Provides simple interface matching test expectations
   - `get(query_text)` → retrieves cached embedding or None
   - `set(query_text, embedding)` → stores embedding in cache
   - `compute_key(query_text)` → returns SHA-256 hex digest
   - Internally uses `VectorCollection` database methods for persistence

## Files Created/Modified

| File | Status | Changes |
|------|--------|---------|
| `app/db.py` | Modified | Added `query_cache` table creation, `get_cached_embedding()`, `set_cached_embedding()` |
| `app/search/embeddings.py` | Modified | Updated `generate_embedding()` with cache lookup and logging |
| `app/search/cache.py` | Created | New `EmbeddingCache` wrapper class |

## Technical Details

### Cache Schema
```sql
CREATE TABLE IF NOT EXISTS query_cache (
    query_hash TEXT PRIMARY KEY,
    embedding  TEXT NOT NULL,
    created_at TEXT NOT NULL
)
```

### Cache Key Computation
- Algorithm: SHA-256
- Input: UTF-8 encoded query text
- Output: 64-character hex digest (deterministic)
- Example: `"python skills"` → `sha256_hash`

### Cache Storage
- Location: Same `metadata.db` as profile embeddings
- Format: JSON string for embedding vectors
- Eviction: None (indefinite cache; embeddings are deterministic)

### Integration Points
- `VectorCollection.__init__()` creates table on database init
- `generate_embedding(text, collection=None)` checks cache on each call
- `EmbeddingCache` provides convenient wrapper for tests and direct cache access

## Verification

All tests passing:

```
======================== test session starts =========================
tests/unit/test_cache.py::test_cache_hit PASSED
tests/unit/test_cache.py::test_cache_key_deterministic PASSED

-- 2 passed in 0.01s --
```

### Test Results Breakdown
- **test_cache_hit**: Verifies that embeddings can be stored and retrieved from cache
- **test_cache_key_deterministic**: Verifies SHA-256 hashing produces consistent keys

## Success Criteria Met

- [x] query_cache table exists in metadata.db
- [x] get_cached_embedding() and set_cached_embedding() methods added to VectorCollection
- [x] generate_embedding() checks cache before model.encode()
- [x] Cache key is SHA-256 hash of query text (deterministic)
- [x] Cache hits are logged with query preview
- [x] Both test cases pass (hit and determinism)

## Commit

- Hash: `fb4ecfe`
- Message: `feat(02-05): implement embedding cache with query_cache table`

## Notes

- The cache uses the same SQLite connection as profile embeddings, leveraging existing WAL mode and connection pooling
- Cache is indefinite by design since embedding models produce deterministic outputs for identical inputs
- Default parameter `collection=None` maintains backward compatibility with existing `generate_embedding()` calls
- Thread-safety inherited from `VectorCollection._sqlite_write_lock` for concurrent async access
