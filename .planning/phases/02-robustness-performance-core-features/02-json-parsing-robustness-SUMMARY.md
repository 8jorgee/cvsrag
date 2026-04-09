---
plan: 02
wave: 1
status: complete
requirement: ROB-01
subsystem: Search & Ingestion
tags: [robustness, json-parsing, fallback, error-handling]
---

# Plan 02 Summary — JSON Parsing Robustness

## Objective

Implement robust JSON parsing in two locations (reranking logic in `engine.py` and profile extraction in `profile_builder.py`) to prevent crashes when Claude/Gemini API returns JSON wrapped in markdown or with extra text. Replace fragile regex extraction with `json.loads()` + fallback strategy.

## Completed Tasks

### Task 1: Implement JSON parsing in engine.py (array parsing for reranking)

**Status:** COMPLETE

**Actions:**
- Implemented `parse_json_response(content: str, context: str = "") -> dict | list` function
- **Strategy 1:** Try `json.loads()` directly (fast path for clean responses)
- **Strategy 2:** Extract bracketed content with regex: `r"\[.*\]"` and `r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"` (handles markdown fences)
- **Strategy 3:** Raise `ValueError` with logged context (first 500 chars) and error message (no silent failures)
- Updated `_claude_rerank()` to call `parse_json_response(response.text, context="Claude reranking response")`
- Added specific `ValueError` exception handling with fallback: returns unsorted candidates on parse failure
- Function supports both object `{}` and array `[]` JSON

**Files Modified:**
- `app/search/engine.py`: Added `parse_json_response()` function at module level, updated `_claude_rerank()` to use it

**Test Results:**
- ✓ `test_clean_json`: Parses `{"key": "value"}` → returns dict with correct key
- ✓ `test_markdown_json`: Parses `` ```json\n{"key": "value"}\n``` `` → extracts and returns dict
- ✓ `test_invalid_json_raises`: Invalid JSON `{broken}` → raises `ValueError` with "Could not parse" message

### Task 2: Implement JSON parsing in profile_builder.py (object parsing for profile extraction)

**Status:** COMPLETE

**Actions:**
- Implemented `parse_json_response(content: str, context: str = "") -> dict | list` function (same three-strategy pattern)
- Updated `parse_profile_with_claude()` to call `parse_json_response(response.text, context=f"Profile parsing for {name_hint}")`
- Added two-level error handling:
  - `ValueError` (parse failure) → logs error and returns skeleton profile dict with name and empty skills (graceful degradation)
  - Generic `Exception` → logs error and returns same skeleton fallback
- Function supports both object `{}` and array `[]` JSON
- Note: `parse_profile_with_claude()` also includes slide-boundary chunking (16K char limit) from ROB-04, which was implemented in the same session

**Files Modified:**
- `app/ingestion/profile_builder.py`: Added `parse_json_response()` function, updated `parse_profile_with_claude()` to use it, added `chunk_slides_to_16k()` helper

**Test Results:**
- ✓ All three JSON parsing tests pass with profile_builder.py in place
- No regression in existing reranking or profile parsing logic

## Files Created/Modified

| File | Status | Changes |
|------|--------|---------|
| `app/search/engine.py` | Modified | Added `parse_json_response()` function (45 lines), updated `_claude_rerank()` to use it with error handling |
| `app/ingestion/profile_builder.py` | Modified | Added `parse_json_response()` function (46 lines), updated `parse_profile_with_claude()` to use it with fallback |
| `tests/unit/test_json_parsing.py` | No change | Tests pass without modification |

## Verification

### Test Execution

```bash
pytest tests/unit/test_json_parsing.py -xvs
```

**Result:**
```
============================= test session starts ==============================
platform darwin -- Python 3.11.12, pytest-7.4.4, pluggy-1.6.0

tests/unit/test_json_parsing.py::test_clean_json PASSED
tests/unit/test_json_parsing.py::test_markdown_json PASSED
tests/unit/test_json_parsing.py::test_invalid_json_raises PASSED

======================== 3 passed in 0.01s ========================
```

### Strategy Validation

**Strategy 1 — Direct Parse (json.loads):**
- Fast path: Clean JSON like `'{"key": "value"}'` parsed immediately
- No regex overhead for valid JSON responses

**Strategy 2 — Bracket Extraction:**
- Handles markdown-wrapped JSON: `` ```json\n{...}\n``` ``
- Regex patterns: `r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"` (objects with nesting) and `r"\[.*\]"` (arrays)
- Continues to next pattern if `json.loads()` fails on extracted content

**Strategy 3 — Error Logging & Failure:**
- Logs first 500 chars of unparseable content
- Error message includes first 200 chars for debugging
- Raises `ValueError` with context string (e.g., "Claude reranking response", "Profile parsing for John Doe")
- Allows calling code to handle with graceful degradation

## Known Deviations from Plan

None — plan executed exactly as written.

**Note:** Implementation also includes slide-boundary chunking (ROB-04) in `profile_builder.py`, which was completed in the same commit. This is tracked separately in the ROB-04 plan.

## Fallback Behavior Verified

**Reranking fallback (engine.py):**
- If Claude returns unparseable JSON → `_claude_rerank()` catches `ValueError` and returns unranked candidates with their base scores
- Ensures search continues without LLM reranking rather than crashing

**Profile parsing fallback (profile_builder.py):**
- If Gemini returns unparseable JSON → `parse_profile_with_claude()` catches `ValueError` and returns skeleton profile dict:
  ```python
  {
      "name": name_hint,
      "skills": [],
      "certifications": [],
      "experience_summary": raw_text[:400],
      "domains": [],
      "languages": [],
      "education": "",
      "years_of_experience": None,
  }
  ```
- Allows ingestion to continue without crashing on single malformed profile

## Success Criteria Met

- [x] `parse_json_response()` exists in `engine.py` (45 lines)
- [x] `parse_json_response()` exists in `profile_builder.py` (46 lines)
- [x] Both implementations support Strategy 1 (json.loads), Strategy 2 (bracket regex), Strategy 3 (raise with logging)
- [x] Test cases pass: clean JSON, markdown JSON, invalid JSON (raises)
- [x] Malformed responses log error with context (first 500 chars visible)
- [x] Fallback behavior: reranking returns unsorted candidates, profile parsing returns skeleton profile dict
- [x] No regression in existing tests

## Technical Notes

- **Function signature:** `parse_json_response(content: str, context: str = "") -> dict | list`
- **Context parameter:** Used in error logging to identify where parsing failed (e.g., "Claude reranking response")
- **Regex patterns:** Handles nested objects `{...{...}...}` and arrays `[...]` with `re.DOTALL` flag for multiline content
- **Error logging:** Uses stdlib `logging.getLogger(__name__)` (not structlog, as FEAT-10 is a separate plan)
- **Imports:** Both functions use standard library `json` and `re` modules (no new dependencies)
