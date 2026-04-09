import pytest
import tempfile
import sqlite3
from pathlib import Path
from typing import Callable
from fastapi.testclient import TestClient
from app.main import app
from app.config import Settings


@pytest.fixture
def client():
    """FastAPI TestClient for all tests."""
    return TestClient(app)


@pytest.fixture
def mock_api_key(monkeypatch):
    """Mock ANTHROPIC_API_KEY in environment."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-12345")


@pytest.fixture
def temp_db_dir() -> Path:
    """Temporary directory for test databases.

    Returns:
        Path to a temporary directory that pytest cleans up after test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_metadata_db(temp_db_dir: Path) -> Path:
    """Create an in-memory SQLite metadata database for testing.

    Args:
        temp_db_dir: Temporary directory fixture.

    Returns:
        Path to SQLite database file.
    """
    db_path = temp_db_dir / "metadata.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create schema matching production database
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            embedding BLOB,
            metadata TEXT
        )
    """)
    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def mock_settings(temp_db_dir: Path) -> Settings:
    """Settings object with test-safe values.

    Args:
        temp_db_dir: Temporary directory for databases.

    Returns:
        Settings instance configured for testing.
    """
    return Settings(
        gemini_api_key="test-key-12345",
        embedding_model="all-MiniLM-L6-v2",
        chroma_db_path=str(temp_db_dir / "chroma_db"),
        cv_directory=str(temp_db_dir / "cvs"),
        availability_file=str(temp_db_dir / "availability.csv"),
        top_k_results=10,
        rerank_top_n=5,
        admin_username="admin",
        admin_password="password",
        csrf_secret="test-csrf-secret"
    )


@pytest.fixture
def async_client(mock_settings: Settings) -> TestClient:
    """TestClient for testing FastAPI endpoints with test settings.

    Args:
        mock_settings: Test settings fixture.

    Returns:
        FastAPI TestClient instance.
    """
    return TestClient(app)


@pytest.fixture
def mock_embeddings() -> Callable[[str], list]:
    """Mock embedding function returning fixed-size vectors.

    Returns:
        Function that takes text and returns embedding vector of size 384.
        All embeddings are set to [0.1, 0.1, ...] for deterministic testing.
    """
    def embed(text: str) -> list:
        """Return mock embedding vector of size 384."""
        return [0.1] * 384

    return embed
