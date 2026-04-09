"""Embedding cache for query embeddings.

Provides a simple interface to cache and retrieve embeddings for repeated queries,
reducing re-computation of embeddings for the same query text.
"""

import hashlib
from app.db import get_collection


class EmbeddingCache:
    """Cache for query embeddings backed by SQLite."""

    def __init__(self):
        """Initialize cache with access to the vector collection."""
        self.collection = get_collection()

    def compute_key(self, query_text: str) -> str:
        """Compute deterministic cache key for query text.

        Args:
            query_text: The query text

        Returns:
            SHA-256 hex digest of query text
        """
        return hashlib.sha256(query_text.encode()).hexdigest()

    def get(self, query_text: str) -> list[float] | None:
        """Retrieve cached embedding for query.

        Args:
            query_text: The query text

        Returns:
            Embedding as list[float] if found, None otherwise
        """
        return self.collection.get_cached_embedding(query_text)

    def set(self, query_text: str, embedding: list[float]) -> None:
        """Cache embedding for query.

        Args:
            query_text: The query text
            embedding: The embedding vector as list[float]
        """
        self.collection.set_cached_embedding(query_text, embedding)
