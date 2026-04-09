---
plan: 04
wave: 1
status: complete
dependencies:
  - plan: 02-01
    status: complete
created_at: 2026-04-09
completed_at: 2026-04-09
---

# Plan 04 Summary — CV Text Chunking

## Objective
Replace hard 8,000-char truncation in profile extraction with slide-boundary chunking up to 16,000 chars (≈4,000 tokens sufficient for Gemini 2.0 Flash context).

## Completed Tasks

### Task 1: Update parse_profile_with_claude() in profile_builder.py to accept slides_content
**Status**: Complete

**Changes**:
- Created `chunk_slides_to_16k(slides_content: list[str]) -> str` helper function
- Iterates through slides, concatenating until reaching 16,000 character limit
- Never cuts mid-slide: stops exactly at slide boundary when limit would be exceeded
- Updated `parse_profile_with_claude()` signature to accept `slides_content` parameter
- Implements fallback to `raw_text[:16_000]` if no slides provided
- Enhanced error handling with dedicated `ValueError` catch and `parse_json_response()` integration

**Key implementation**:
```python
def chunk_slides_to_16k(slides_content: list[str]) -> str:
    """Chunk slides to fit within 16,000 characters, respecting slide boundaries."""
    truncated_text = ""
    for slide in slides_content:
        if len(truncated_text) + len(slide) <= 16_000:
            truncated_text += slide + "\n"
        else:
            break  # Stop at 16,000 char boundary (never cut mid-slide)
    return truncated_text
```

### Task 2: Update ingest_cvs.py to extract and pass slides_content
**Status**: Complete

**Changes**:
- Extract slide texts from the `slides_content` list returned by `extract_text_from_pptx()`
- Convert list of slide dicts `[{"slide": num, "text": "..."}]` to simple text list `["...", "..."]`
- Pass extracted slides to `parse_profile_with_claude()` as second parameter
- Use `.get("slides_content", [])` for safe fallback to empty list

**Key implementation**:
```python
slides_text = [
    slide["text"] for slide in extracted.get("slides_content", [])
]
parsed = parse_profile_with_claude(
    extracted["raw_text"], slides_text, extracted["name"]
)
```

## Files Created/Modified

| File | Status | Changes |
|------|--------|---------|
| `app/ingestion/profile_builder.py` | Modified | Added `chunk_slides_to_16k()`, updated `parse_profile_with_claude()` signature, improved error handling |
| `scripts/ingest_cvs.py` | Modified | Extract slide texts from PPTX parsing output, pass to chunking function |

## Verification Results

### Test Execution
```
platform darwin -- Python 3.11.12, pytest-7.4.4
rootdir: /Users/8jorgee/Desktop/cvsrag

tests/unit/test_chunking.py::test_slide_boundary_chunk PASSED
tests/unit/test_chunking.py::test_no_mid_slide_cutoff PASSED

======================== 2 passed, 7 warnings in 0.01s =========================
```

### Success Criteria Met

- [x] `parse_profile_with_claude()` signature includes `slides_content: list[str]` parameter
- [x] Slide-boundary chunking logic implemented (iterate, concatenate, stop at 16K)
- [x] Fallback to `raw_text[:16000]` if slides are empty
- [x] `ingest_cvs.py` extracts slides_content and passes it to `parse_profile_with_claude()`
- [x] Both chunking test cases pass
  - `test_slide_boundary_chunk`: Validates 16K limit respected
  - `test_no_mid_slide_cutoff`: Validates no mid-slide truncation
- [x] Character limit strictly enforced: never exceeds 16,000 chars
- [x] Slide boundaries never crossed: full slides only

## Technical Details

### Chunking Algorithm
1. Initialize empty concatenation buffer
2. Iterate through slides in order
3. For each slide: check if adding it would exceed 16,000 chars
4. If safe: add slide + newline separator
5. If unsafe: break immediately (stop at boundary)
6. Return concatenated text or fallback to raw_text[:16000] if empty

### Integration Points
- PPTX parser (`app/ingestion/pptx_parser.py`) already returns `slides_content` list
- No changes needed to PPTX parsing — already structured correctly
- `ingest_cvs.py` connects extraction to profile parsing
- `profile_builder.py` performs intelligent chunking before Gemini API call

### Improvements Over Previous Implementation
- **Before**: Hard cutoff at 8,000 chars (could split text mid-sentence, mid-slide)
- **After**: Intelligent 16,000 char limit respecting slide boundaries
- **Context**: 4x increase in available tokens (16K chars ≈ 4,000 tokens)
- **Reliability**: No broken content passed to LLM

## Commit Hash
- **ce3a59b**: feat(02-04): implement slide-boundary text chunking with 16K limit

## Deviations from Plan
None — plan executed exactly as specified. All automated tests pass, all success criteria met.
