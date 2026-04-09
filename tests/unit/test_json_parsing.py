"""Unit tests for JSON response parsing (ROB-01).

Tests verify that the search engine can parse JSON from various formats:
- Clean JSON objects
- JSON wrapped in markdown code blocks
- Invalid JSON with proper error handling
"""

import pytest


def test_clean_json():
    """Test parsing clean JSON object.

    Arrange: JSON object string {"key": "value"}
    Act: Call parse_json_response(clean_json)
    Assert: Returns dict with key="value"
    """
    try:
        from app.search.engine import parse_json_response
    except (ImportError, AttributeError):
        pytest.skip("parse_json_response not yet implemented")

    clean_json = '{"key": "value"}'
    result = parse_json_response(clean_json)
    assert isinstance(result, dict)
    assert result.get("key") == "value"


def test_markdown_json():
    """Test parsing JSON wrapped in markdown code block.

    Arrange: JSON wrapped in markdown: ```json\n{"key": "value"}\n```
    Act: Call parse_json_response(markdown_json)
    Assert: Returns dict with key="value"
    """
    try:
        from app.search.engine import parse_json_response
    except (ImportError, AttributeError):
        pytest.skip("parse_json_response not yet implemented")

    markdown_json = '```json\n{"key": "value"}\n```'
    result = parse_json_response(markdown_json)
    assert isinstance(result, dict)
    assert result.get("key") == "value"


def test_invalid_json_raises():
    """Test that invalid JSON raises ValueError.

    Arrange: Invalid JSON string {broken}
    Act: Call parse_json_response(invalid) expecting ValueError
    Assert: ValueError is raised with "Could not parse" in message
    """
    try:
        from app.search.engine import parse_json_response
    except (ImportError, AttributeError):
        pytest.skip("parse_json_response not yet implemented")

    invalid_json = '{broken}'
    with pytest.raises(ValueError, match="Could not parse"):
        parse_json_response(invalid_json)
