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
import sqlite3
from pathlib import Path
import asyncio
import hashlib
from threading import Lock as ThreadingLock
from datetime import datetime

import faiss
import numpy as np
import structlog

from app.config import settings

logger = structlog.get_logger()

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
        self._sqlite_write_lock = asyncio.Lock()  # Serialize async SQLite writes
        self._upsert_lock = ThreadingLock()  # Separate lock for ThreadPoolExecutor parallel ingestion

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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS query_cache (
                query_hash TEXT PRIMARY KEY,
                embedding  TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_sessions (
                id             TEXT PRIMARY KEY,
                created_at     TEXT NOT NULL,
                last_accessed  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_queries (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT NOT NULL,
                query_text      TEXT NOT NULL,
                mode            TEXT NOT NULL,
                filters_json    TEXT,
                created_at      TEXT NOT NULL,
                results_count   INTEGER,
                FOREIGN KEY(session_id) REFERENCES search_sessions(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_search_queries_session_id ON search_queries(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_search_queries_created_at ON search_queries(created_at)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profile_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id      TEXT NOT NULL,
                version         INTEGER NOT NULL,
                metadata_json   TEXT NOT NULL,
                created_at      TEXT NOT NULL,
                source_file     TEXT,
                FOREIGN KEY (profile_id) REFERENCES profiles(id),
                UNIQUE (profile_id, version)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_profile_history_profile_version ON profile_history(profile_id, version DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_profile_history_created_at ON profile_history(created_at)")

        # One-time migration: populate initial history for existing profiles
        self._migrate_existing_profiles_to_history(conn)

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
                    logger.debug("FAISS index loaded", vector_count=index.ntotal)
                    return index
                logger.warning("FAISS index size mismatch, rebuilding")
            except Exception as e:
                logger.warning("Could not load FAISS index, rebuilding", error=str(e))

        return self._rebuild_index()

    def _migrate_existing_profiles_to_history(self, conn: sqlite3.Connection) -> None:
        """One-time migration: populate profile_history with initial snapshots for existing profiles.

        This runs on first _open_db() call. If profile_history is empty but profiles exist,
        we create version=1 snapshots for all existing profiles.
        """
        try:
            # Check if profile_history is empty
            history_count = conn.execute(
                "SELECT COUNT(*) FROM profile_history"
            ).fetchone()[0]

            if history_count == 0:
                # Get all existing profiles
                profiles = conn.execute(
                    "SELECT id, metadata FROM profiles"
                ).fetchall()

                if profiles:
                    now = datetime.now().isoformat()
                    logger.info("Migrating existing profiles to history", profile_count=len(profiles))

                    for profile_row in profiles:
                        profile_id = profile_row["id"]
                        metadata_json = profile_row["metadata"]
                        source_file = ""

                        # Insert version 1 for this profile
                        conn.execute(
                            """INSERT INTO profile_history
                               (profile_id, version, metadata_json, created_at, source_file)
                               VALUES (?, ?, ?, ?, ?)""",
                            (profile_id, 1, metadata_json, now, source_file)
                        )
                    conn.commit()
                    logger.info("Profile history migration completed", profile_count=len(profiles))
        except Exception as e:
            logger.error("Profile history migration failed", error=str(e))
            # Don't raise — allow DB to continue even if migration fails

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
            logger.debug("FAISS index rebuilt", vector_count=index.ntotal)

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
            logger.info("Profiles upserted to SQLite", count=len(ids))

            # Step 3: Update FAISS (if SQLite succeeded)
            try:
                if needs_rebuild:
                    self._index = self._rebuild_index()
                    logger.info("FAISS index rebuilt", vector_count=self._index.ntotal)
                else:
                    # Append new vectors to the end of the index
                    new_vecs = np.array(embeddings, dtype=np.float32)
                    self._index.add(new_vecs)
                    faiss.write_index(self._index, str(self._index_path))
                    logger.info("Vectors added to FAISS", count=len(embeddings))

            except Exception as faiss_error:
                # FAISS failed — rollback SQLite changes
                logger.error("FAISS operation failed, rolling back SQLite", error=str(faiss_error))
                self._conn.rollback()
                self._index = self._load_or_rebuild_index()  # Restore FAISS from SQLite
                raise RuntimeError(f"Upsert failed and was rolled back: {faiss_error}")

        except Exception as e:
            # Catch any other errors and ensure rollback
            if not isinstance(e, RuntimeError):
                logger.error("Upsert failed", error=str(e))
                self._conn.rollback()
            raise

    async def upsert_async(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """Async wrapper around synchronous upsert, with SQLite write serialization.

        Acquires _sqlite_write_lock to ensure only one async task writes to SQLite
        at a time, preventing 'database is locked' errors under concurrent load.
        """
        async with self._sqlite_write_lock:  # Only one async writer at a time
            await asyncio.to_thread(
                self.upsert, ids, embeddings, documents, metadatas
            )

    def upsert_threaded(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """Thread-safe wrapper for ThreadPoolExecutor parallel ingestion.

        Acquires _upsert_lock to serialize writes when using ThreadPoolExecutor,
        preventing concurrent database writes that could cause corruption.
        """
        with self._upsert_lock:
            self.upsert(ids, embeddings, documents, metadatas)

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

    # ─── embedding cache ────────────────────────────────────────────────────────

    def get_cached_embedding(self, query_text: str) -> list[float] | None:
        """Retrieve cached embedding for a query.

        Args:
            query_text: The query text to look up

        Returns:
            Embedding as list[float] if found in cache, None otherwise
        """
        query_hash = hashlib.sha256(query_text.encode()).hexdigest()
        row = self._conn.execute(
            "SELECT embedding FROM query_cache WHERE query_hash = ?",
            (query_hash,)
        ).fetchone()

        if row:
            return json.loads(row["embedding"])
        return None

    def set_cached_embedding(self, query_text: str, embedding: list[float]) -> None:
        """Cache an embedding for a query.

        Args:
            query_text: The query text to cache
            embedding: The embedding vector as list[float]
        """
        query_hash = hashlib.sha256(query_text.encode()).hexdigest()
        self._conn.execute(
            """INSERT OR REPLACE INTO query_cache (query_hash, embedding, created_at)
               VALUES (?, ?, datetime('now'))""",
            (query_hash, json.dumps(embedding))
        )
        self._conn.commit()


_collection: VectorCollection | None = None


def get_collection() -> VectorCollection:
    global _collection
    if _collection is None:
        _collection = VectorCollection(settings.chroma_db_path)
    return _collection
