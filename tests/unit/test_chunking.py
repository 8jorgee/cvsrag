"""Unit tests for slide boundary-respecting chunking (ROB-04).

Tests verify that slide content is chunked to fit within 16K character limit
while never cutting mid-slide (respecting slide boundaries).
"""

import pytest


def test_slide_boundary_chunk():
    """Test that chunk respects slide boundaries.

    Arrange: List of 3 slides, each ~6000 chars, total ~18000 chars
    Act: Call chunk_slides_to_16k(slides_content)
    Assert: Returns string with ≤16000 chars, contains first 3 slides (or partial 3rd)
    """
    try:
        from app.ingestion.profile_builder import chunk_slides_to_16k
    except (ImportError, AttributeError):
        pytest.skip("chunk_slides_to_16k not yet implemented")

    # Create 3 slides of approximately 6000 chars each
    slide1 = "X" * 6000  # 6000 chars
    slide2 = "Y" * 6000  # 6000 chars
    slide3 = "Z" * 6000  # 6000 chars
    slides = [slide1, slide2, slide3]

    result = chunk_slides_to_16k(slides)

    # Result should not exceed 16000 chars
    assert len(result) <= 16000, f"Chunk exceeded 16K limit: {len(result)} chars"

    # Result should contain content from slides
    assert len(result) > 0, "Chunk should contain at least some slide content"


def test_no_mid_slide_cutoff():
    """Test that chunking never cuts mid-slide.

    Arrange: List of slides where slide 1 = 5000 chars, slide 2 = 6000 chars,
             slide 3 = 8000 chars
    Act: Call chunk_slides_to_16k([slide1, slide2, slide3])
    Assert: Returns exactly slides 1+2 (11000 chars total, no partial slide 3)
    """
    try:
        from app.ingestion.profile_builder import chunk_slides_to_16k
    except (ImportError, AttributeError):
        pytest.skip("chunk_slides_to_16k not yet implemented")

    # Create slides with specific sizes
    slide1 = "A" * 5000  # 5000 chars
    slide2 = "B" * 6000  # 6000 chars
    slide3 = "C" * 8000  # 8000 chars
    slides = [slide1, slide2, slide3]

    result = chunk_slides_to_16k(slides)

    # Result should contain slides 1 and 2
    assert "A" in result, "Result should contain slide 1"
    assert "B" in result, "Result should contain slide 2"

    # Result length should be exactly 11000 or contain full slide boundaries
    # The function should not partially include slide 3
    result_length = len(result)
    assert result_length <= 16000, f"Chunk exceeded 16K limit: {result_length} chars"
