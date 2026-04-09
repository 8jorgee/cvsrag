"""Unit tests for embedding cache (FEAT-07).

Tests verify that embeddings are cached with deterministic keys,
enabling fast lookups for repeated queries.
"""

import pytest
import hashlib


def test_cache_hit():
    """Test that cached embeddings can be retrieved.

    Arrange: Cache a query "python skills" with embedding [0.1, 0.2, ...]
    Act: Call cache.get("python skills")
    Assert: Returns cached embedding [0.1, 0.2, ...]

    Note: This is a stub test. The EmbeddingCache will be implemented in Phase 2.
    """
    try:
        from app.search.cache import EmbeddingCache
    except ImportError:
        # Cache module not yet implemented - skip this test
        pytest.skip("EmbeddingCache not yet implemented")

    cache = EmbeddingCache()

    # Create test embedding
    test_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    query_text = "python skills"

    # Store in cache
    cache.set(query_text, test_embedding)

    # Retrieve from cache
    retrieved = cache.get(query_text)

    # Should match original
    assert retrieved is not None, "Cache should return stored embedding"
    assert retrieved == test_embedding, "Retrieved embedding should match original"


def test_cache_key_deterministic():
    """Test that cache keys are computed deterministically.

    Arrange: Query text "python skills"
    Act: Compute cache key twice using SHA-256
    Assert: Both keys are identical (deterministic hashing)

    Note: This is a stub test. The EmbeddingCache will be implemented in Phase 2.
    """
    try:
        from app.search.cache import EmbeddingCache
    except ImportError:
        # Cache module not yet implemented - skip this test
        pytest.skip("EmbeddingCache not yet implemented")

    cache = EmbeddingCache()
    query_text = "python skills"

    # Compute key twice
    key1 = cache.compute_key(query_text)
    key2 = cache.compute_key(query_text)

    # Keys should be identical
    assert key1 == key2, "Cache keys should be deterministic"

    # Verify it's using SHA-256
    expected_key = hashlib.sha256(query_text.encode()).hexdigest()
    assert key1 == expected_key, "Cache key should use SHA-256 hashing"
