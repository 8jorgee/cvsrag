import pytest


def test_csrf_missing_token_rejected(client):
    """SEC-01: POST without CSRF token returns 403."""
    # STUB — implementation in Wave 1
    pytest.skip("Implementation pending")


def test_rate_limit_exceeded(client):
    """SEC-04: 31 requests in 60 seconds returns 429."""
    # STUB — implementation in Wave 1
    pytest.skip("Implementation pending")
