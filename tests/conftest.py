import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """FastAPI TestClient for all tests."""
    return TestClient(app)


@pytest.fixture
def mock_api_key(monkeypatch):
    """Mock ANTHROPIC_API_KEY in environment."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-12345")
