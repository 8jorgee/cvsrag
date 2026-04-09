"""Unit tests for OR/AND filter logic (SEARCH-02).

Tests verify that filters correctly implement AND logic (all required)
and OR logic (any matching).
"""

import pytest


def test_skills_any_matches():
    """Test filter: profile matches when it has required skill.

    Arrange: Candidate with profile containing skills=["Python", "JavaScript"],
             query with skills=["Python"]
    Act: Call filters.apply_filters(candidates, SearchQuery(..., skills=["Python"]))
    Assert: Profile is included in results (has required skill)
    """
    try:
        from app.search.filters import apply_filters
        from app.models import SearchQuery, Profile
    except (ImportError, AttributeError):
        pytest.skip("apply_filters not yet implemented")

    # Create mock profile with skills
    profile = Profile(
        id="profile_1",
        name="Test Developer",
        source_file="test.pdf",
        raw_text="test content",
        skills=["Python", "JavaScript"]
    )

    # Create candidate dict with profile
    candidates = [{"profile": profile, "score": 0.9}]

    # Create query with skill filter (looking for Python)
    query = SearchQuery(
        query="test",
        skills=["Python"]  # Filter: profile must have this skill
    )

    # Filter candidates
    result = apply_filters(candidates, query)

    # Profile should be in results because it has Python
    assert len(result) == 1, "Profile should match when it has the required skill"
    assert result[0]["profile"].id == "profile_1"


def test_skills_all_required():
    """Test AND logic: profile must have ALL required skills.

    Arrange: Candidate with profile containing skills=["Python", "JavaScript"],
             query with skills=["Python", "Go"]
    Act: Call filters.apply_filters(candidates, SearchQuery(..., skills=["Python", "Go"]))
    Assert: Profile is NOT included (missing Go)
    """
    try:
        from app.search.filters import apply_filters
        from app.models import SearchQuery, Profile
    except (ImportError, AttributeError):
        pytest.skip("apply_filters not yet implemented")

    # Create mock profile with limited skills
    profile = Profile(
        id="profile_1",
        name="Test Developer",
        source_file="test.pdf",
        raw_text="test content",
        skills=["Python", "JavaScript"]  # Missing Go
    )

    # Create candidate dict with profile
    candidates = [{"profile": profile, "score": 0.9}]

    # Create query with AND filter (all of these skills required)
    query = SearchQuery(
        query="test",
        skills=["Python", "Go"]  # AND logic: must have ALL skills
    )

    # Filter candidates
    result = apply_filters(candidates, query)

    # Profile should NOT be in results because it's missing Go
    assert len(result) == 0, "Profile should NOT match when missing required skill"
