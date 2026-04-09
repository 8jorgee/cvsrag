"""
Vector store backed by FAISS (inner-product on L2-normalised vectors = cosine similarity)
and SQLite for metadata + embedding persistence.

Replaces ChromaDB to avoid the pydantic-v1 / Python-3.14 incompatibility.

Public interface (mirrors the subset of ChromaDB's collection API we use):
    get_collection() -> VectorCollection
    collection.upsert(ids, embeddings, documents, metadatas)
    collection.query(query_embeddings, n_results, include) -> dict
    collection.get(ids=None, include=None)               -> dict
    collection.count()                                   -> int
"""

import json
import logging
import sqlite3
from pathlib import Path

import faiss
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

_EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension


class VectorCollection:
    """FAISS + SQLite vector collection."""

    def __init__(self, db_dir: str):
        self._dir = Path(db_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

        self._db_path = self._dir / "metadata.db"
        self._index_path = self._dir / "index.faiss"

        self._conn = self._open_db()
        self._index = self._load_or_rebuild_index()

    # ─── setup ──────────────────────────────────────────────────────────────

    def _open_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id         TEXT PRIMARY KEY,
                document   TEXT NOT NULL,
                metadata   TEXT NOT NULL,
                embedding  TEXT NOT NULL   -- JSON array of floats
            )
        """)
        conn.commit()
        return conn

    def _load_or_rebuild_index(self) -> faiss.IndexFlatIP:
        """Load the FAISS index from file, or rebuild it from SQLite embeddings."""
        if self._index_path.exists():
            try:
                index = faiss.read_index(str(self._index_path))
                # Sanity check: index size must match DB row count
                db_count = self._conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
                if index.ntotal == db_count:
                    logger.debug(f"Loaded FAISS index ({index.ntotal} vectors)")
                    return index
                logger.warning("FAISS index size mismatch — rebuilding")
            except Exception as e:
                logger.warning(f"Could not load FAISS index: {e} — rebuilding")

        return self._rebuild_index()

    def _rebuild_index(self) -> faiss.IndexFlatIP:
        """Reconstruct the FAISS index from all embeddings stored in SQLite."""
        index = faiss.IndexFlatIP(_EMBEDDING_DIM)
        rows = self._conn.execute(
            "SELECT embedding FROM profiles ORDER BY rowid"
        ).fetchall()

        if rows:
            vecs = np.array(
                [json.loads(r["embedding"]) for r in rows], dtype=np.float32
            )
            index.add(vecs)
            logger.debug(f"Rebuilt FAISS index with {index.ntotal} vectors")

        faiss.write_index(index, str(self._index_path))
        return index

    # ─── public API ─────────────────────────────────────────────────────────

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """
        Insert or replace profiles atomically.

        Strategy:
        1. Update SQLite first (transactional)
        2. If SQLite succeeds, rebuild/append to FAISS
        3. If FAISS fails, rollback SQLite changes
        4. Never leave FAISS and SQLite in inconsistent state
        """
        try:
            needs_rebuild = False

            # Step 1: Validate and insert into SQLite
            for doc_id, embedding, document, metadata in zip(
                ids, embeddings, documents, metadatas
            ):
                existing = self._conn.execute(
                    "SELECT id FROM profiles WHERE id = ?", (doc_id,)
                ).fetchone()

                self._conn.execute(
                    """INSERT INTO profiles (id, document, metadata, embedding)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET
                         document  = excluded.document,
                         metadata  = excluded.metadata,
                         embedding = excluded.embedding
                    """,
                    (doc_id, document, json.dumps(metadata), json.dumps(embedding)),
                )

                if existing:
                    needs_rebuild = True  # Mark index for rebuild

            # Step 2: Commit SQLite transaction
            self._conn.commit()
            logger.info(f"Upserted {len(ids)} profiles to SQLite")

            # Step 3: Update FAISS (if SQLite succeeded)
            try:
                if needs_rebuild:
                    self._index = self._rebuild_index()
                    logger.info(f"Rebuilt FAISS index ({self._index.ntotal} vectors)")
                else:
                    # Append new vectors to the end of the index
                    new_vecs = np.array(embeddings, dtype=np.float32)
                    self._index.add(new_vecs)
                    faiss.write_index(self._index, str(self._index_path))
                    logger.info(f"Added {len(embeddings)} vectors to FAISS")

            except Exception as faiss_error:
                # FAISS failed — rollback SQLite changes
                logger.error(f"FAISS operation failed: {faiss_error} — rolling back SQLite")
                self._conn.rollback()
                self._index = self._load_or_rebuild_index()  # Restore FAISS from SQLite
                raise RuntimeError(f"Upsert failed and was rolled back: {faiss_error}")

        except Exception as e:
            # Catch any other errors and ensure rollback
            if not isinstance(e, RuntimeError):
                logger.error(f"Upsert failed: {e}")
                self._conn.rollback()
            raise

    def query(
        self,
        query_embeddings: list[list[float]],
        n_results: int,
        include: list[str] | None = None,
    ) -> dict:
        if self._index.ntotal == 0:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        vec = np.array(query_embeddings, dtype=np.float32)
        k = min(n_results, self._index.ntotal)
        scores, row_indices = self._index.search(vec, k)

        # Map FAISS row-index (0-based insertion order) back to SQLite rows
        all_rows = self._conn.execute(
            "SELECT id, document, metadata FROM profiles ORDER BY rowid"
        ).fetchall()

        result_ids, result_docs, result_metas, result_dists = [], [], [], []
        for score, row_idx in zip(scores[0], row_indices[0]):
            if row_idx == -1 or row_idx >= len(all_rows):
                continue
            row = all_rows[row_idx]
            result_ids.append(row["id"])
            result_docs.append(row["document"])
            result_metas.append(json.loads(row["metadata"]))
            result_dists.append(float(1.0 - score))  # cosine distance

        return {
            "ids": [result_ids],
            "documents": [result_docs],
            "metadatas": [result_metas],
            "distances": [result_dists],
        }

    def get(
        self,
        ids: list[str] | None = None,
        include: list[str] | None = None,
    ) -> dict:
        if ids:
            placeholders = ",".join("?" * len(ids))
            rows = self._conn.execute(
                f"SELECT id, document, metadata FROM profiles WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, document, metadata FROM profiles"
            ).fetchall()

        return {
            "ids": [r["id"] for r in rows],
            "documents": [r["document"] for r in rows],
            "metadatas": [json.loads(r["metadata"]) for r in rows],
        }

    def delete(self, ids: list[str]) -> None:
        placeholders = ",".join("?" * len(ids))
        self._conn.execute(
            f"DELETE FROM profiles WHERE id IN ({placeholders})", ids
        )
        self._conn.commit()
        self._index = self._rebuild_index()


_collection: VectorCollection | None = None


def get_collection() -> VectorCollection:
    global _collection
    if _collection is None:
        _collection = VectorCollection(settings.chroma_db_path)
    return _collection
