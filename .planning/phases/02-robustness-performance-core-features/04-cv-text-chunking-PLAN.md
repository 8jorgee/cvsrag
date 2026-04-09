---
phase: 02-robustness-performance-core-features
plan: 04
type: execute
wave: 1
depends_on: [02-01]
files_modified:
  - app/ingestion/profile_builder.py
  - scripts/ingest_cvs.py
autonomous: true
requirements: [ROB-04]

must_haves:
  truths:
    - "CV text chunking respects slide boundaries and never cuts mid-slide"
    - "Chunked text is ≤16,000 characters (4x the previous 8,000-char limit)"
    - "If slides are missing, fallback to raw_text[:16000]"
  artifacts:
    - path: app/ingestion/profile_builder.py
      provides: "parse_profile_with_claude() accepts slides_content parameter, uses slide-boundary chunking"
      min_lines: 15
    - path: scripts/ingest_cvs.py
      provides: "Updated to extract and pass slides_content from PPTX parsing"
      min_lines: 5
  key_links:
    - from: app/ingestion/profile_builder.py
      to: tests/unit/test_chunking.py::test_slide_boundary_chunk
      via: "slide-boundary logic"
      pattern: "for slide in slides_content"
    - from: scripts/ingest_cvs.py
      to: app/ingestion/profile_builder.py
      via: "slides_content extraction"
      pattern: "extracted\\[\"slides_content\"\\]"
---

<objective>
Replace hard 8,000-char truncation in profile extraction with slide-boundary chunking up to 16,000 chars.

Purpose: Preserve context without arbitrary mid-slide cutoffs. 16,000 chars ≈ 4,000 tokens, sufficient for Gemini 2.0 Flash context.

Output:
- parse_profile_with_claude() accepts slides_content list and performs intelligent chunking
- ingest_cvs.py extracts and passes slides_content from PPTX parsing
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/phases/02-robustness-performance-core-features/02-CONTEXT.md
@.planning/phases/02-robustness-performance-core-features/02-RESEARCH.md

From RESEARCH.md, Pattern 4: Slide-Boundary Text Chunking (ROB-04):
- Iterate through `slides_content` list
- Concatenate slides until cumulative length ≥ 16,000 chars
- Pass that as `truncated_text`
- Fallback: use raw_text[:16000] if slides are missing

Current implementation in profile_builder.py uses `raw_text[:8000]` which the code should replace.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Update parse_profile_with_claude() in profile_builder.py to accept slides_content</name>
  <files>app/ingestion/profile_builder.py</files>
  <action>
Locate `parse_profile_with_claude()` function signature and update it:

Change from:
```python
def parse_profile_with_claude(raw_text: str, name_hint: str) -> dict:
```

To:
```python
def parse_profile_with_claude(raw_text: str, slides_content: list[str], name_hint: str) -> dict:
```

Inside the function, replace the line that does `raw_text[:8000]` with slide-boundary chunking logic:

```python
# Slide-boundary chunking: concatenate slides until 16,000 chars
truncated_text = ""
for slide in slides_content:
    if len(truncated_text) + len(slide) <= 16_000:
        truncated_text += slide + "\n"
    else:
        break  # Stop at 16,000 char boundary (never cut mid-slide)

if not truncated_text.strip():
    # Fallback: use raw_text if no slides
    truncated_text = raw_text[:16_000]
```

Then use `truncated_text` in the Claude API call instead of `raw_text[:8000]`.

Ensure the function signature and all calls within the function are updated.
  </action>
  <verify>
    <automated>pytest tests/unit/test_chunking.py::test_slide_boundary_chunk tests/unit/test_chunking.py::test_no_mid_slide_cutoff -xvs</automated>
  </verify>
  <done>
parse_profile_with_claude() accepts slides_content, performs slide-boundary chunking, respects 16K char limit, test cases pass
  </done>
</task>

<task type="auto">
  <name>Task 2: Update ingest_cvs.py to extract and pass slides_content</name>
  <files>scripts/ingest_cvs.py</files>
  <action>
In scripts/ingest_cvs.py, locate the section that calls `parse_profile_with_claude()`.

Before that call, the script should have extracted profile data from the PPTX file. This extraction should return a dict with keys like:
- "raw_text" — full text from PPTX
- "slides_content" — list of slide texts

If "slides_content" is not already extracted by the PPTX parser (pptx_parser.py), update the extraction to include it:
```python
extracted = {
    "raw_text": ...,
    "slides_content": [...list of slide texts...],  # Add this
    ...other fields...
}
```

Then update the call to parse_profile_with_claude():

Change from:
```python
parsed = parse_profile_with_claude(extracted["raw_text"], name_hint)
```

To:
```python
parsed = parse_profile_with_claude(
    extracted["raw_text"],
    extracted.get("slides_content", []),
    name_hint
)
```

Use .get("slides_content", []) to handle old code paths that don't extract slides.
  </action>
  <verify>
    <automated>grep -n "parse_profile_with_claude" scripts/ingest_cvs.py | head -5</automated>
  </verify>
  <done>
ingest_cvs.py updated to pass slides_content from extracted dict to parse_profile_with_claude()
  </done>
</task>

</tasks>

<verification>
Run chunking tests:
- `pytest tests/unit/test_chunking.py -xvs` should pass both slide boundary tests
- Verify that 16,000 char limit is respected
- Verify that slide boundaries are never crossed (no mid-slide truncation)
</verification>

<success_criteria>
- parse_profile_with_claude() signature includes slides_content: list[str] parameter
- Slide-boundary chunking logic implemented (iterate, concatenate, stop at 16K)
- Fallback to raw_text[:16000] if slides are empty
- ingest_cvs.py extracts slides_content and passes it to parse_profile_with_claude()
- Both chunking test cases pass (boundary respect, no mid-slide cutoff)
</success_criteria>

<output>
After completion, create `.planning/phases/02-robustness-performance-core-features/02-04-SUMMARY.md` documenting:
- Chunking logic in profile_builder.py
- Integration with ingest_cvs.py
- Test results confirming 16K limit and slide boundary respect
</output>
