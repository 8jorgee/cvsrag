---
phase: 02-robustness-performance-core-features
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - pytest.ini
  - tests/conftest.py
  - tests/unit/test_json_parsing.py
  - tests/unit/test_embeddings.py
  - tests/unit/test_chunking.py
  - tests/unit/test_pagination.py
  - tests/unit/test_filters.py
  - tests/unit/test_cache.py
  - tests/unit/test_logging.py
  - tests/integration/test_db_async.py
  - tests/integration/test_db_consistency.py
  - tests/integration/test_sse.py
  - tests/integration/test_parallel_ingest.py
  - requirements.txt
autonomous: true
requirements: [ROB-01, ROB-02, ROB-03, ROB-04, ROB-05, SEARCH-01, SEARCH-02, FEAT-02, FEAT-07, FEAT-10]

must_haves:
  truths:
    - "pytest fixtures can instantiate test databases and async clients"
    - "Test files exist for every Phase 2 requirement and are discoverable by pytest"
    - "Test configuration activates asyncio event loop mode"
    - "structlog is installed and importable"
  artifacts:
    - path: pytest.ini
      provides: "pytest configuration with asyncio mode and test path discovery"
    - path: tests/conftest.py
      provides: "Shared fixtures for database, async client, temporary directories"
    - path: tests/unit/test_json_parsing.py
      provides: "3 test stubs for ROB-01 (clean, markdown, invalid JSON)"
    - path: tests/integration/test_db_async.py
      provides: "Async concurrency test stubs for ROB-03"
  key_links:
    - from: pytest.ini
      to: tests/
      via: test discovery
      pattern: testpaths=tests
    - from: tests/conftest.py
      to: all test files
      via: fixture imports
      pattern: pytest fixtures
---

<objective>
Create pytest infrastructure (fixtures, configuration, test stubs) for Phase 2 feature development.

Purpose: Establish test-driven development foundation before implementing features. All Wave 1+ tasks reference test stubs created here.

Output:
- pytest.ini with asyncio mode enabled
- tests/conftest.py with reusable fixtures (db, async client, temp dirs)
- 13 test stub files (unit + integration) corresponding to VALIDATION.md
- structlog added to requirements.txt
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/02-robustness-performance-core-features/02-VALIDATION.md
@.planning/phases/02-robustness-performance-core-features/02-CONTEXT.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create pytest.ini with asyncio mode</name>
  <files>pytest.ini</files>
  <action>
Create pytest.ini at project root with:
- [pytest] section
- testpaths = tests
- asyncio_mode = auto (enables pytest-asyncio for async test functions)
- markers for "slow" tests (optional, referenced in VALIDATION.md)
- python_files = test_*.py
- python_classes = Test*
- python_functions = test_*

Verify pytest can discover tests with `pytest --collect-only` command.
  </action>
  <verify>
    <automated>pytest --collect-only | grep "test session starts"</automated>
  </verify>
  <done>
pytest.ini exists, asyncio_mode=auto set, test discovery works
  </done>
</task>

<task type="auto">
  <name>Task 2: Create conftest.py with core fixtures</name>
  <files>tests/conftest.py</files>
  <action>
Create tests/conftest.py with:

1. fixture: `temp_db_dir` - returns a temporary directory for test databases (uses tmpdir)
2. fixture: `test_metadata_db` - creates an in-memory SQLite metadata.db for tests (Path to temp file)
3. fixture: `mock_settings` - returns a Settings object with test values (api_key="test", embedding_model="all-MiniLM-L6-v2")
4. fixture: `async_client` - returns TestClient from fastapi.testclient for testing endpoints (instantiates app with mock settings)
5. fixture: `mock_embeddings` - returns mock embedding vectors (fixture that returns lambda text: [0.1] * 384)

All fixtures should use type hints. Use pytest-asyncio for async fixtures if needed.

Reference existing app/config.py for Settings model structure. Do not actually connect to external APIs (all fixtures use mocks/test doubles).
  </action>
  <verify>
    <automated>pytest tests/conftest.py --collect-only | grep "test_metadata_db\|async_client"</automated>
  </verify>
  <done>
tests/conftest.py exists with 5+ fixtures, all correctly typed and documented
  </done>
</task>

<task type="auto">
  <name>Task 3: Create unit test stubs for ROB-01 (JSON parsing)</name>
  <files>tests/unit/test_json_parsing.py</files>
  <action>
Create tests/unit/test_json_parsing.py with three test stubs:

1. test_clean_json:
   - Arrange: JSON object string `{"key": "value"}`
   - Act: Call parse_json_response(clean_json)
   - Assert: Returns dict with key="value"

2. test_markdown_json:
   - Arrange: JSON wrapped in markdown: `` ```json\n{"key": "value"}\n``` ``
   - Act: Call parse_json_response(markdown_json)
   - Assert: Returns dict with key="value"

3. test_invalid_json_raises:
   - Arrange: Invalid JSON string (e.g., `{broken}`)
   - Act: Call parse_json_response(invalid) expecting ValueError
   - Assert: ValueError is raised with "Could not parse" in message

Import statements may be placeholders (e.g., `from app.search.engine import parse_json_response` — function doesn't exist yet).

Use pytest.raises() context manager for exception testing.
  </action>
  <verify>
    <automated>pytest tests/unit/test_json_parsing.py --collect-only -q</automated>
  </verify>
  <done>
test_json_parsing.py exists with 3 test functions, all correctly named per spec
  </done>
</task>

<task type="auto">
  <name>Task 4: Create unit test stubs for ROB-02 (thread safety)</name>
  <files>tests/unit/test_embeddings.py</files>
  <action>
Create tests/unit/test_embeddings.py with one test stub:

1. test_concurrent_model_loading:
   - Arrange: Import get_model, create ThreadPoolExecutor(max_workers=5)
   - Act: Submit 5 tasks calling get_model() concurrently
   - Assert: All 5 calls complete without deadlock, all return same model object (identity check with `is`)

This test verifies that threading.Lock in embeddings.py prevents race conditions during concurrent initialization.

Use concurrent.futures.ThreadPoolExecutor for the concurrent calls.
  </action>
  <verify>
    <automated>pytest tests/unit/test_embeddings.py::test_concurrent_model_loading --collect-only</automated>
  </verify>
  <done>
test_embeddings.py exists with test_concurrent_model_loading stub
  </done>
</task>

<task type="auto">
  <name>Task 5: Create unit test stubs for ROB-04 (chunking)</name>
  <files>tests/unit/test_chunking.py</files>
  <action>
Create tests/unit/test_chunking.py with two test stubs:

1. test_slide_boundary_chunk:
   - Arrange: List of 3 slides, each ~6000 chars, total ~18000 chars
   - Act: Call chunk_slides_to_16k(slides_content)
   - Assert: Returns string with ≤16000 chars, contains first 3 slides (or partial 3rd)

2. test_no_mid_slide_cutoff:
   - Arrange: List of slides where slide 1 = 5000 chars, slide 2 = 6000 chars, slide 3 = 8000 chars
   - Act: Call chunk_slides_to_16k([slide1, slide2, slide3])
   - Assert: Returns exactly slides 1+2 (11000 chars total, no partial slide 3)

This tests slide-boundary chunking logic (never cut mid-slide). Function name is placeholder; actual implementation is in profile_builder.py.

Use len() to measure character counts.
  </action>
  <verify>
    <automated>pytest tests/unit/test_chunking.py --collect-only -q</automated>
  </verify>
  <done>
test_chunking.py exists with 2 test stubs for slide boundary validation
  </done>
</task>

<task type="auto">
  <name>Task 6: Create unit test stubs for SEARCH-01 (pagination)</name>
  <files>tests/unit/test_pagination.py</files>
  <action>
Create tests/unit/test_pagination.py with three test stubs:

1. test_page_size_10:
   - Arrange: search() returns 30 total results, page=1, page_size=10
   - Act: Call engine.search(..., page=1, page_size=10)
   - Assert: Returns exactly 10 results

2. test_total_count_accurate:
   - Arrange: search() returns 25 results total
   - Act: Call engine.search(...) and inspect total_count field
   - Assert: SearchResult.total_count == 25

3. test_has_more_flag:
   - Arrange: search() returns 30 results, page=1, page_size=10
   - Act: Call engine.search(..., page=1, page_size=10)
   - Assert: SearchResult.has_more == True (more results available)
   - Arrange: search() page=3, page_size=10 (30 results total)
   - Act: Call engine.search(..., page=3)
   - Assert: SearchResult.has_more == False (no results after page 3)

Tests verify pagination math (page slicing, total count, has_more flag).

Use mock candidates list in arrangement phase.
  </action>
  <verify>
    <automated>pytest tests/unit/test_pagination.py --collect-only -q</automated>
  </verify>
  <done>
test_pagination.py exists with 3 pagination test stubs
  </done>
</task>

<task type="auto">
  <name>Task 7: Create unit test stubs for SEARCH-02 (OR filters)</name>
  <files>tests/unit/test_filters.py</files>
  <action>
Create tests/unit/test_filters.py with two test stubs:

1. test_skills_any_matches:
   - Arrange: Profile with skills=["Python", "JavaScript"], query with skills_any=["Python", "R"]
   - Act: Call filters.apply_filters(profile, SearchQuery(..., skills_any=["Python", "R"]))
   - Assert: Profile matches (Python is in both lists — OR logic)

2. test_skills_all_required:
   - Arrange: Profile with skills=["Python", "JavaScript"], query with skills=["Python", "Go"]
   - Act: Call filters.apply_filters(profile, SearchQuery(..., skills=["Python", "Go"]))
   - Assert: Profile does NOT match (missing Go — AND logic requires all)

Tests verify OR vs AND filter behavior. Use mock profiles with known skills.
  </action>
  <verify>
    <automated>pytest tests/unit/test_filters.py --collect-only -q</automated>
  </verify>
  <done>
test_filters.py exists with 2 OR/AND filter logic stubs
  </done>
</task>

<task type="auto">
  <name>Task 8: Create unit test stubs for FEAT-07 (embedding cache)</name>
  <files>tests/unit/test_cache.py</files>
  <action>
Create tests/unit/test_cache.py with two test stubs:

1. test_cache_hit:
   - Arrange: Cache a query "python skills" with embedding [0.1, 0.2, ...]
   - Act: Call cache.get("python skills")
   - Assert: Returns cached embedding [0.1, 0.2, ...]

2. test_cache_key_deterministic:
   - Arrange: Query text "python skills"
   - Act: Compute cache key twice using SHA-256
   - Assert: Both keys are identical (deterministic hashing)

Tests verify cache lookup and key generation. Use hashlib.sha256 to compute expected key.
  </action>
  <verify>
    <automated>pytest tests/unit/test_cache.py --collect-only -q</automated>
  </verify>
  <done>
test_cache.py exists with 2 cache test stubs
  </done>
</task>

<task type="auto">
  <name>Task 9: Create unit test stubs for FEAT-10 (structured logging)</name>
  <files>tests/unit/test_logging.py</files>
  <action>
Create tests/unit/test_logging.py with two test stubs:

1. test_json_output:
   - Arrange: Configure structlog with JSON renderer, set LOG_FORMAT="json"
   - Act: Log a message with context (e.g., logger.info("user logged in", user_id=123))
   - Assert: Log output contains valid JSON with user_id=123 field

2. test_console_colored:
   - Arrange: Configure structlog with console colored renderer, set LOG_FORMAT="dev"
   - Act: Log a message
   - Assert: Output contains color codes or ANSI escape sequences (verify with regex)

Tests verify structlog configuration in both production and development modes. Use capsys fixture to capture log output.
  </action>
  <verify>
    <automated>pytest tests/unit/test_logging.py --collect-only -q</automated>
  </verify>
  <done>
test_logging.py exists with 2 logging format stubs
  </done>
</task>

<task type="auto">
  <name>Task 10: Create integration test stubs for ROB-03 (async SQLite)</name>
  <files>tests/integration/test_db_async.py</files>
  <action>
Create tests/integration/test_db_async.py with one test stub:

1. test_concurrent_upsert:
   - Arrange: Initialize VectorCollection with test metadata.db, create 5 asyncio tasks
   - Act: Run 5 concurrent upsert_async() calls with different profile IDs
   - Assert: All upserts complete without "database is locked" exception
   - Assert: Final profile count in SQLite matches expected (5 profiles)

This test verifies that asyncio.Lock in db.py prevents write contention.

Use asyncio.gather() to run concurrent tasks. Mark with @pytest.mark.asyncio.
  </action>
  <verify>
    <automated>pytest tests/integration/test_db_async.py::test_concurrent_upsert --collect-only</automated>
  </verify>
  <done>
test_db_async.py exists with concurrent upsert test stub
  </done>
</task>

<task type="auto">
  <name>Task 11: Create integration test stubs for FAISS/SQLite consistency</name>
  <files>tests/integration/test_db_consistency.py</files>
  <action>
Create tests/integration/test_db_consistency.py with one test stub:

1. test_faiss_sqlite_sync:
   - Arrange: Insert 10 profiles via upsert
   - Act: Query FAISS index (search) and SQLite (SELECT count)
   - Assert: FAISS index contains 10 vectors, SQLite metadata table contains 10 rows
   - Assert: Profile IDs match between FAISS and SQLite

This tests that FAISS and SQLite remain synchronized after concurrent operations.

Use mock profile data for test inserts.
  </action>
  <verify>
    <automated>pytest tests/integration/test_db_consistency.py --collect-only -q</automated>
  </verify>
  <done>
test_db_consistency.py exists with FAISS/SQLite sync stub
  </done>
</task>

<task type="auto">
  <name>Task 12: Create integration test stubs for SSE streaming</name>
  <files>tests/integration/test_sse.py</files>
  <action>
Create tests/integration/test_sse.py with two test stubs:

1. test_reindex_stream_content_type:
   - Arrange: Prepare test admin client (async_client fixture)
   - Act: GET /admin/reindex-stream?force=false
   - Assert: response.status_code == 200, response.headers["content-type"] == "text/event-stream"

2. test_sse_json_format:
   - Arrange: Prepare test admin client
   - Act: GET /admin/reindex-stream?force=false, collect first event
   - Assert: Event data is valid JSON (parseable with json.loads)
   - Assert: Event contains "file" and "status" fields (or final event contains "done": true)

Tests verify SSE endpoint exists and returns correct format. Use mock ingestion function (no real file processing).

Use TestClient to make synchronous requests to async endpoint.
  </action>
  <verify>
    <automated>pytest tests/integration/test_sse.py --collect-only -q</automated>
  </verify>
  <done>
test_sse.py exists with 2 SSE format test stubs
  </done>
</task>

<task type="auto">
  <name>Task 13: Create integration test stubs for parallel ingestion</name>
  <files>tests/integration/test_parallel_ingest.py</files>
  <action>
Create tests/integration/test_parallel_ingest.py with two test stubs:

1. test_parallel_executor:
   - Arrange: Create list of 4 mock CV files, initialize ThreadPoolExecutor(max_workers=4)
   - Act: Submit all 4 files to parallel ingestion
   - Assert: All tasks complete, worker pool has processed 4 items concurrently

2. test_consistency_parallel:
   - Arrange: Create list of 4 distinct profiles for parallel upsert
   - Act: Call ingest_parallel(profiles) with ThreadPoolExecutor
   - Assert: Final FAISS index and SQLite both contain 4 profiles
   - Assert: No profiles are duplicated or lost

Tests verify ThreadPoolExecutor integration and data consistency with parallel threading.

Use threading events or locks to verify concurrent execution.
  </action>
  <verify>
    <automated>pytest tests/integration/test_parallel_ingest.py --collect-only -q</automated>
  </verify>
  <done>
test_parallel_ingest.py exists with 2 parallel ingestion stubs
  </done>
</task>

<task type="auto">
  <name>Task 14: Add structlog to requirements.txt</name>
  <files>requirements.txt</files>
  <action>
Read requirements.txt, check if structlog is present.

If not present, add:
  structlog==24.1.0

to the dependencies list. Do NOT remove or modify any existing lines.

After edit, verify installation:
  pip install -q structlog==24.1.0
  python -c "import structlog; print(f'structlog {structlog.__version__} installed')"
  </action>
  <verify>
    <automated>grep -q "structlog" requirements.txt && python -c "import structlog; print('OK')"</automated>
  </verify>
  <done>
structlog==24.1.0 added to requirements.txt and installed
  </done>
</task>

</tasks>

<verification>
After all tasks complete:
1. `pytest --collect-only` discovers 13 test files (unit + integration)
2. `pytest tests/ -x` runs stubs without errors (all tests should be skipped or pass trivially until implementations added)
3. `pytest tests/conftest.py` imports all fixtures without errors
</verification>

<success_criteria>
- pytest.ini exists with asyncio_mode=auto
- tests/conftest.py defines 5+ fixtures (temp_db_dir, test_metadata_db, mock_settings, async_client, mock_embeddings)
- All 13 test stub files exist in correct subdirectories (tests/unit/ and tests/integration/)
- structlog installed and importable
- `pytest --collect-only` discovers all 13+ test functions
- No import errors when running `pytest tests/ -x`
</success_criteria>

<output>
After completion, create `.planning/phases/02-robustness-performance-core-features/02-01-SUMMARY.md` documenting:
- All test files created
- pytest configuration applied
- structlog version installed
- Fixture availability confirmed
</output>
