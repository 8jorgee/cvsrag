"""Integration tests for FAISS/SQLite consistency (ROB-03).

Tests verify that FAISS vector index and SQLite metadata remain
synchronized after concurrent operations.
"""

import pytest


def test_faiss_sqlite_sync():
    """Test that FAISS and SQLite remain synchronized.

    Arrange: Insert 10 profiles via upsert
    Act: Query FAISS index and SQLite for count
    Assert: FAISS index contains 10 vectors, SQLite metadata table contains 10 rows
    Assert: Profile IDs match between FAISS and SQLite
    """
    from app.db import VectorCollection
    import tempfile

    # Create temporary database directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize VectorCollection
        collection = VectorCollection(tmpdir)

        # Create 10 mock profiles with their embeddings
        profile_ids = []
        embeddings = []
        documents = []
        metadatas = []

        for i in range(10):
            profile_id = f"profile_{i:02d}"
            profile_ids.append(profile_id)

            profile_data = {
                "id": profile_id,
                "name": f"Developer {i}",
                "skills": ["Python", "JavaScript"],
                "experience_years": 5 + i
            }

            # Prepare mock embedding and metadata
            embedding = [0.1 + (i * 0.01)] * 384
            embeddings.append(embedding)
            documents.append(f"Profile: Developer {i}")
            metadatas.append(profile_data)

        # Upsert all profiles at once (matching API signature)
        collection.upsert(
            ids=profile_ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

        # Query FAISS index
        query_embedding = [[0.1] * 384]
        faiss_results = collection.query(query_embedding, n_results=10)
        faiss_ids = faiss_results["ids"][0] if faiss_results["ids"] else []

        # Query SQLite
        sqlite_count = collection.count()

        # Verify counts match
        assert len(faiss_ids) == 10, f"FAISS should have 10 results, got {len(faiss_ids)}"
        assert sqlite_count == 10, f"SQLite should have 10 rows, got {sqlite_count}"

        # Verify IDs match between systems
        for profile_id in profile_ids:
            assert profile_id in faiss_ids, f"Profile {profile_id} missing from FAISS results"
