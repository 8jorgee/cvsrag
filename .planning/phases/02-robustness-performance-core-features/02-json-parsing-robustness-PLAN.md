---
phase: 02-robustness-performance-core-features
plan: 02
type: execute
wave: 1
depends_on: [02-01]
files_modified:
  - app/search/engine.py
  - app/ingestion/profile_builder.py
autonomous: true
requirements: [ROB-01]

must_haves:
  truths:
    - "JSON parsing never crashes on clean or markdown-wrapped responses"
    - "Malformed JSON responses log an error and trigger fallback behavior"
    - "Object and array JSON parsing both supported (reranking uses [], profile parsing uses {})"
  artifacts:
    - path: app/search/engine.py
      provides: "parse_json_response() function for array JSON with fallback"
      min_lines: 20
    - path: app/ingestion/profile_builder.py
      provides: "parse_json_response() or json.loads() + bracket fallback for object JSON"
      min_lines: 15
  key_links:
    - from: app/search/engine.py
      to: tests/unit/test_json_parsing.py::test_clean_json
      via: "json.loads() first strategy"
      pattern: "json.loads\\("
    - from: app/ingestion/profile_builder.py
      to: tests/unit/test_json_parsing.py::test_markdown_json
      via: "bracket-finding regex fallback"
      pattern: "re.search.*\\["
---

<objective>
Implement robust JSON parsing in two locations: reranking logic in engine.py (arrays) and profile extraction in profile_builder.py (objects).

Purpose: Prevent crashes when Claude/Gemini API returns JSON wrapped in markdown or with extra text. Replace fragile regex extraction with `json.loads()` + fallback.

Output: Two parse_json_response() functions (or one shared, if refactored) handling both object and array JSON.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/02-robustness-performance-core-features/02-CONTEXT.md
@.planning/phases/02-robustness-performance-core-features/02-RESEARCH.md

From RESEARCH.md, Pattern 3: JSON Parsing with Fallback (ROB-01):
- Strategy 1: Try `json.loads()` directly (fast path for clean responses)
- Strategy 2: Extract bracketed content with regex (handles markdown fences)
- Strategy 3: Raise ValueError with logged context (no silent failures)

Code patterns for both cases:
```python
def parse_json_response(content: str, context: str = "") -> dict | list:
    # Strategy 1: Direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract bracketed JSON
    for pattern in [r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", r"\[.*\]"]:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue

    # Strategy 3: Give up with context
    logger.error(f"Failed to parse JSON from {context}. Raw content:\n{content[:500]}...")
    raise ValueError(f"Could not parse JSON from {context}: {content[:200]}")
```
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement JSON parsing in engine.py (array parsing for reranking)</name>
  <files>app/search/engine.py</files>
  <action>
Locate the `_claude_rerank()` function or equivalent in engine.py (currently uses regex to extract rankings from Claude response).

Implement `parse_json_response(content: str, context: str = "") -> dict | list` function:
1. Try `json.loads(content)` first (handles clean JSON)
2. If JSONDecodeError, search for bracketed content: `r"\[.*\]"` (arrays for reranking)
3. If match found, try `json.loads(match.group())`
4. If all fail, log error with context (first 500 chars) and raise ValueError

Update `_claude_rerank()` to:
- Call `parse_json_response(response.text, context="Claude reranking response")`
- Wrap in try/except: if ValueError, log error and return unranked candidates

Use structlog.get_logger() instead of logging.getLogger() (per FEAT-10, but Wave 0 test setup already imports it).

Actually import: `import json`, `import re`, `import logging` (or `import structlog`)
  </action>
  <verify>
    <automated>pytest tests/unit/test_json_parsing.py::test_clean_json tests/unit/test_json_parsing.py::test_markdown_json tests/unit/test_json_parsing.py::test_invalid_json_raises -xvs</automated>
  </verify>
  <done>
parse_json_response() in engine.py handles arrays, all 3 test cases pass (clean, markdown, invalid)
  </done>
</task>

<task type="auto">
  <name>Task 2: Implement JSON parsing in profile_builder.py (object parsing for profile extraction)</name>
  <files>app/ingestion/profile_builder.py</files>
  <action>
Locate the `parse_profile_with_claude()` function in profile_builder.py. It currently uses regex to extract JSON from Claude's response (currently handles object `{}`).

Replace regex extraction with same three-strategy approach as engine.py:
1. Try `json.loads(content)` (fast path)
2. Search for `r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"` (objects) or similar
3. Log error and raise if all fail

Implement `parse_json_response(content: str, context: str = "") -> dict` function (or reuse from engine.py if refactoring into shared module, but for now keep it local to profile_builder.py to minimize cross-module dependencies).

Update profile parsing logic:
- Call `parse_json_response(response.text, context=f"Profile parsing for {name_hint}")`
- On ValueError, return a fallback profile dict with name and empty skills (graceful degradation)

Import: `import json`, `import re`, `import logging` (or structlog)
  </action>
  <verify>
    <automated>pytest tests/unit/test_json_parsing.py::test_clean_json tests/unit/test_json_parsing.py::test_markdown_json tests/unit/test_json_parsing.py::test_invalid_json_raises -xvs</automated>
  </verify>
  <done>
parse_json_response() in profile_builder.py handles objects, fallback returns valid profile dict on parse failure
  </done>
</task>

</tasks>

<verification>
Run all three JSON parsing tests:
- `pytest tests/unit/test_json_parsing.py -xvs` should pass all 3 test cases (clean, markdown, invalid)
- No regression in existing reranking or profile parsing logic
- Manual smoke test: Call both functions with markdown-wrapped JSON and verify parsing succeeds
</verification>

<success_criteria>
- parse_json_response() exists in engine.py and profile_builder.py
- Both implementations support Strategy 1 (json.loads), Strategy 2 (bracket regex), Strategy 3 (raise with logging)
- Test cases pass: clean JSON, markdown JSON, invalid JSON (raises)
- Malformed responses log error with context (first 500 chars visible)
- Fallback behavior: reranking returns unsorted candidates, profile parsing returns skeleton profile dict
</success_criteria>

<output>
After completion, create `.planning/phases/02-robustness-performance-core-features/02-02-SUMMARY.md` documenting:
- parse_json_response() implementations in both files
- Test results (all 3 test cases passing)
- Fallback behavior verified
</output>
