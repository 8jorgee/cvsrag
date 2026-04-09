---
phase: 01-security-data-integrity
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - app/main.py
  - app/config.py
  - app/models.py
  - requirements.txt
  - templates/admin.html
autonomous: false
requirements: [SEC-01, SEC-02, SEC-03, SEC-04, SEC-05]
user_setup:
  - service: starlette-csrf
    why: "CSRF token middleware for admin forms"
    note: "Automatically installed via pip install -r requirements.txt"
  - service: slowapi
    why: "Rate limiting on /search endpoint"
    note: "Automatically installed via pip install -r requirements.txt"

must_haves:
  truths:
    - "Admin POST requests without valid CSRF token are rejected with 403"
    - "API key validation occurs at startup; server refuses to start if ANTHROPIC_API_KEY missing"
    - "Search queries longer than 500 characters return HTTP 400"
    - "/search endpoint rate-limited to 30 requests/minute per IP; excess requests return 429"
    - "File uploads validate MIME type (magic bytes) in addition to extension"
  artifacts:
    - path: "app/main.py"
      provides: "CSRF middleware setup, rate limiting, file MIME validation, query length validation"
      min_lines: 250
    - path: "app/config.py"
      provides: "Startup validation for ANTHROPIC_API_KEY"
      min_lines: 30
    - path: "requirements.txt"
      provides: "starlette-csrf, slowapi, python-magic dependencies"
  key_links:
    - from: "app/main.py"
      to: "CSRF middleware"
      via: "CSRFMiddleware at app startup"
      pattern: "CSRFMiddleware"
    - from: "app/main.py"
      to: "rate limiting"
      via: "@limiter.limit decorator on /search"
      pattern: "@limiter\\.limit"
    - from: "app/config.py"
      to: "startup validation"
      via: "@app.on_event('startup')"
      pattern: "validate_startup"
---

<objective>
Implement all security hardening measures (CSRF tokens, API key validation, rate limiting, input validation, file MIME validation) to make the system production-safe.

Purpose: Eliminate critical security vulnerabilities that allow CSRF attacks, API key leakage, search bombing, and file upload spoofing attacks.

Output: Secure FastAPI application with validated startup requirements and protected endpoints.
</objective>

<execution_context>
@/Users/8jorgee/.claude/get-shit-done/workflows/execute-plan.md
@/Users/8jorgee/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/8jorgee/Desktop/cvsrag/.planning/ROADMAP.md
@/Users/8jorgee/Desktop/cvsrag/.planning/STATE.md
@/Users/8jorgee/Desktop/cvsrag/.planning/REQUIREMENTS.md
@/Users/8jorgee/Desktop/cvsrag/.planning/phases/01-security-data-integrity/01-RESEARCH.md

Key codebase files:
@/Users/8jorgee/Desktop/cvsrag/app/main.py — FastAPI app, admin routes, file uploads
@/Users/8jorgee/Desktop/cvsrag/app/config.py — Pydantic settings, no startup validation
@/Users/8jorgee/Desktop/cvsrag/app/models.py — SearchQuery model, no max_length on query field
@/Users/8jorgee/Desktop/cvsrag/requirements.txt — missing starlette-csrf, slowapi, python-magic
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Wave 0: Create test infrastructure for security tests</name>
  <files>tests/__init__.py, tests/conftest.py, tests/test_security.py, tests/test_startup.py, tests/test_search.py, tests/test_upload.py</files>
  <behavior>
    - conftest.py provides shared fixtures: FastAPI TestClient, mock database, mock Anthropic client
    - test_security.py has stub for CSRF token validation (test passes if file exists)
    - test_startup.py has stub for API key validation (test passes if file exists)
    - test_search.py has stub for query length validation (test passes if file exists)
    - test_upload.py has stub for MIME type validation (test passes if file exists)
    - All tests are importable and runnable (pytest discovers them)
  </behavior>
  <action>
    1. Create `tests/__init__.py` (empty file for package structure)

    2. Create `tests/conftest.py` with fixtures:
    ```python
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
    ```

    3. Create `tests/test_security.py` with stub:
    ```python
    import pytest

    def test_csrf_missing_token_rejected(client):
        """SEC-01: POST without CSRF token returns 403."""
        # STUB — implementation in Wave 1
        pytest.skip("Implementation pending")

    def test_rate_limit_exceeded(client):
        """SEC-04: 31 requests in 60 seconds returns 429."""
        # STUB — implementation in Wave 1
        pytest.skip("Implementation pending")
    ```

    4. Create `tests/test_startup.py` with stub:
    ```python
    import pytest

    def test_missing_api_key_raises(monkeypatch):
        """SEC-03: App startup fails if ANTHROPIC_API_KEY missing."""
        # STUB — implementation in Wave 1
        pytest.skip("Implementation pending")
    ```

    5. Create `tests/test_search.py` with stub:
    ```python
    import pytest

    def test_query_length_validation(client):
        """SEC-02: Query >500 chars returns HTTP 400."""
        # STUB — implementation in Wave 1
        pytest.skip("Implementation pending")
    ```

    6. Create `tests/test_upload.py` with stub:
    ```python
    import pytest

    def test_mime_type_validation(client):
        """SEC-05: File upload validates MIME type (magic bytes)."""
        # STUB — implementation in Wave 1
        pytest.skip("Implementation pending")
    ```

    7. Add `pytest pytest-asyncio httpx` to requirements.txt if not present (check first with grep)
  </action>
  <verify>
    <automated>pytest tests/ --collect-only | grep "test session starts" && pytest tests/ -x --tb=short 2>&1 | head -20</automated>
  </verify>
  <done>Test files exist, all stubs are discoverable by pytest, conftest.py provides shared fixtures</done>
</task>

<task type="auto">
  <name>Task 1: Add CSRF middleware and token injection to app</name>
  <files>app/main.py, requirements.txt</files>
  <action>
    Per SEC-01: "CSRF tokens added to all HTMX admin forms and validated server-side"

    1. Add to requirements.txt: `starlette-csrf==0.12.0` (or latest)

    2. In app/main.py, after FastAPI import, add:
    ```python
    from starlette_csrf import CSRFMiddleware
    from starlette.middleware import Middleware
    ```

    3. Before templates = Jinja2Templates(...), add CSRF middleware to app:
    ```python
    # CSRF protection — Double Submit Cookie pattern
    csrf_secret = settings.csrf_secret or "dev-secret-change-in-production"  # Will add to config.py

    app.add_middleware(
        CSRFMiddleware,
        secret=csrf_secret,
    )
    ```

    4. For Jinja2 templates to inject csrf_token, add context processor:
    ```python
    # In main.py, before @app routes:
    @app.middleware("http")
    async def add_csrf_to_context(request: Request, call_next):
        request.state.csrf_token = request.cookies.get("csrf_token", "")
        response = await call_next(request)
        return response
    ```

    5. In any Jinja2 template that has a form (templates/admin.html), ensure the form has:
    ```html
    <form method="post" action="/admin/reindex">
        <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token }}">
        <button type="submit">Re-index CVs</button>
    </form>
    ```

    Verify starlette-csrf is installed:
    ```bash
    pip install starlette-csrf
    ```

    Reference from RESEARCH.md: starlette-csrf Double Submit Cookie pattern, automatic token validation on state-changing operations.
  </action>
  <verify>
    <automated>grep -n "CSRFMiddleware" /Users/8jorgee/Desktop/cvsrag/app/main.py && grep -n "starlette-csrf" /Users/8jorgee/Desktop/cvsrag/requirements.txt</automated>
  </verify>
  <done>CSRF middleware added to FastAPI app, starlette-csrf in requirements.txt, token injection in place for admin forms</done>
</task>

<task type="auto">
  <name>Task 2: Add API key validation at startup</name>
  <files>app/main.py, app/config.py</files>
  <action>
    Per SEC-03: "ANTHROPIC_API_KEY validated at application startup; server refuses to start if missing"

    1. In app/config.py, ensure anthropic_api_key field exists and add validation:
    ```python
    from pydantic import Field, field_validator

    class Settings(BaseSettings):
        anthropic_api_key: str = Field(..., description="Anthropic API key")  # Make it required
        # ... rest of settings

        @field_validator('anthropic_api_key')
        @classmethod
        def validate_api_key(cls, v):
            if not v or v.strip() == "":
                raise ValueError("ANTHROPIC_API_KEY must be set and non-empty")
            return v
    ```

    2. In app/main.py, add startup event:
    ```python
    @app.on_event("startup")
    async def validate_startup():
        """Validate required environment variables at startup."""
        try:
            # settings is already imported at top of main.py
            if not settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY is not set")
            logger.info("✓ ANTHROPIC_API_KEY validated at startup")
        except Exception as e:
            logger.error(f"✗ Startup validation failed: {e}")
            raise
    ```

    3. Test manually (Wave 1 automated test will verify):
    ```bash
    unset ANTHROPIC_API_KEY
    uvicorn app.main:app  # Should fail immediately with clear error
    ```

    Reference from RESEARCH.md: Pydantic BaseSettings validation at app startup (code example provided).
  </action>
  <verify>
    <automated>grep -n "validate_startup\|ANTHROPIC_API_KEY" /Users/8jorgee/Desktop/cvsrag/app/main.py && grep -n "validate_api_key" /Users/8jorgee/Desktop/cvsrag/app/config.py</automated>
  </verify>
  <done>Startup event added, API key validation triggered on app initialization</done>
</task>

<task type="auto">
  <name>Task 3: Add query length validation to SearchQuery model</name>
  <files>app/models.py</files>
  <action>
    Per SEC-02: "Search query length capped at 500 characters (HTTP 400 returned for longer queries)"

    In app/models.py, update SearchQuery class:
    ```python
    from pydantic import BaseModel, Field

    class SearchQuery(BaseModel):
        query: str = Field(
            ...,
            max_length=500,
            description="Search query (max 500 characters)"
        )
        mode: str = "smart"  # "smart" or "quick"
        skills: list[str] = Field(default_factory=list)
        certifications: list[str] = Field(default_factory=list)
        availability_status: Optional[str] = None  # "now", "30days", "90days"
        availability_percentage_min: Optional[int] = None
        grade: Optional[str] = None
        location: Optional[str] = None
    ```

    FastAPI will automatically reject queries longer than 500 characters with HTTP 400 and validation error message.

    Reference from RESEARCH.md: FastAPI Pydantic Field with max_length constraint.
  </action>
  <verify>
    <automated>grep -n "max_length=500" /Users/8jorgee/Desktop/cvsrag/app/models.py</automated>
  </verify>
  <done>SearchQuery.query field has max_length=500 constraint</done>
</task>

<task type="auto">
  <name>Task 4: Add rate limiting to /search endpoint</name>
  <files>app/main.py, requirements.txt</files>
  <action>
    Per SEC-04: "Rate limiting applied to /search endpoint (30 requests/minute per IP)"

    1. Add to requirements.txt: `slowapi==0.1.9` (or latest)

    2. In app/main.py, add imports:
    ```python
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    ```

    3. Set up limiter after FastAPI initialization:
    ```python
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    ```

    4. Add exception handler for rate limit:
    ```python
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_error_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded: 30 requests per minute per IP"},
        )
    ```

    5. Add middleware after CSRF middleware:
    ```python
    app.add_middleware(SlowAPIMiddleware)
    ```

    6. Decorate the /search POST endpoint:
    ```python
    @app.post("/search", response_class=HTMLResponse)
    @limiter.limit("30/minute")
    async def do_search(
        request: Request,
        # ... rest of parameters ...
    ):
        # ... rest of implementation ...
    ```

    Note: The Request parameter must be first in the signature when using @limiter.limit decorator.

    Reference from RESEARCH.md: SlowAPI documentation with get_remote_address strategy for IP-based limiting.
  </action>
  <verify>
    <automated>grep -n "@limiter.limit\|RateLimitExceeded" /Users/8jorgee/Desktop/cvsrag/app/main.py && grep -n "slowapi" /Users/8jorgee/Desktop/cvsrag/requirements.txt</automated>
  </verify>
  <done>Rate limiting decorator applied to /search endpoint, slowapi middleware added, 429 handler configured</done>
</task>

<task type="auto">
  <name>Task 5: Add file MIME type validation to upload endpoints</name>
  <files>app/main.py, requirements.txt</files>
  <action>
    Per SEC-05: "File upload validates content type in addition to extension"

    1. Add to requirements.txt: `python-magic==0.4.27` (or latest)

    2. In app/main.py, add imports:
    ```python
    import magic
    ```

    3. Create validation helper function in app/main.py (after _check_upload_size):
    ```python
    def _validate_upload_mime(file: UploadFile, allowed_mimes: set[str]) -> bytes:
        """Validate file MIME type using magic bytes (not client header)."""
        # Read file content
        content = file.file.read()
        file.file.seek(0)  # Reset for later reads

        # Detect MIME from content (magic bytes)
        detected_mime = magic.from_buffer(content[:2048], mime=True)

        if detected_mime not in allowed_mimes:
            raise HTTPException(
                status_code=415,
                detail=f"File content is {detected_mime}, not an allowed type. Expected: {allowed_mimes}"
            )

        return content
    ```

    4. Update /admin/upload-cv endpoint to use MIME validation:
    ```python
    @app.post("/admin/upload-cv")
    async def upload_cv(
        file: UploadFile = File(...),
        _: None = Depends(_require_admin_auth),
    ):
        # Validate extension
        safe_name = _safe_upload_name(file.filename, {".pptx"})

        # Validate MIME type (magic bytes check)
        content = _validate_upload_mime(
            file,
            allowed_mimes={
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            }
        )

        # Check size
        _check_upload_size(content)

        # ... rest of upload logic ...
    ```

    5. Similarly update /admin/upload-availability for CSV files:
    ```python
    # For CSV upload, allowed_mimes should include text/plain and text/csv
    content = _validate_upload_mime(
        file,
        allowed_mimes={"text/plain", "text/csv"}
    )
    ```

    Reference from RESEARCH.md: python-magic library for content-based MIME detection (fool-proof against spoofing).
  </action>
  <verify>
    <automated>grep -n "_validate_upload_mime\|magic.from_buffer" /Users/8jorgee/Desktop/cvsrag/app/main.py && grep -n "python-magic" /Users/8jorgee/Desktop/cvsrag/requirements.txt</automated>
  </verify>
  <done>MIME type validation function added, upload endpoints validate file content, python-magic in requirements.txt</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
  - CSRF middleware protecting admin forms (double submit cookie pattern)
  - API key validation at startup (server refuses to start without ANTHROPIC_API_KEY)
  - Query length validation (SearchQuery.query max_length=500)
  - Rate limiting on /search (30 requests/minute per IP, returns 429)
  - File MIME type validation (magic bytes check on upload)
  </what-built>
  <how-to-verify>
    1. Start the app with a valid .env file:
       ```bash
       cd /Users/8jorgee/Desktop/cvsrag
       ANTHROPIC_API_KEY="test-key" uvicorn app.main:app --reload
       ```
       Verify: Server starts successfully and logs "✓ ANTHROPIC_API_KEY validated at startup"

    2. Test CSRF protection on admin form:
       ```bash
       curl -X POST http://localhost:8000/admin/reindex
       ```
       Expected: 403 Forbidden (CSRF token missing)

    3. Test query length validation:
       ```bash
       curl -X POST http://localhost:8000/search \
         -F "query=$(python -c 'print("x" * 501)')" \
         -F "mode=smart"
       ```
       Expected: 400 Bad Request (query exceeds max length)

    4. Test rate limiting:
       ```bash
       for i in {1..31}; do
         curl -X POST http://localhost:8000/search \
           -F "query=test" \
           -F "mode=smart" &
       done; wait
       ```
       Expected: Last request(s) return 429 Too Many Requests

    5. Test file MIME validation:
       - Try uploading a .txt file with .pptx extension
       - Expected: 415 Unsupported Media Type

    6. Test startup without API key:
       ```bash
       unset ANTHROPIC_API_KEY
       uvicorn app.main:app
       ```
       Expected: Server fails immediately with error about missing API key
  </how-to-verify>
  <resume-signal>Type "approved" after verifying all security measures work as expected, or describe any issues</resume-signal>
</task>

<task type="auto">
  <name>Task 6: Update admin template with CSRF token (if needed)</name>
  <files>templates/admin.html</files>
  <action>
    Check if templates/admin.html exists and if it has forms without CSRF tokens.

    If admin.html has a form like:
    ```html
    <form method="post" action="/admin/reindex">
    ```

    Update it to include CSRF token:
    ```html
    <form method="post" action="/admin/reindex">
        <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token }}">
        <button type="submit">Re-index CVs</button>
    </form>
    ```

    Check for any other POST/PUT/DELETE forms and add csrf_token to each.

    If no admin.html exists, skip this task (forms will be implemented in Phase 2).
  </action>
  <verify>
    <automated>grep -n "csrf_token" /Users/8jorgee/Desktop/cvsrag/templates/admin.html 2>/dev/null || echo "No admin.html or no CSRF tokens yet"</automated>
  </verify>
  <done>CSRF token fields added to all admin forms, or admin.html doesn't exist yet</done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Test suite passes for security stubs (Wave 0):
   ```bash
   pytest tests/test_security.py tests/test_startup.py tests/test_search.py tests/test_upload.py -v
   ```

2. Verify no syntax errors:
   ```bash
   python -m py_compile app/main.py app/config.py app/models.py
   ```

3. Dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

4. Server starts with valid API key:
   ```bash
   ANTHROPIC_API_KEY="dummy" uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

5. Admin endpoints are protected:
   - CSRF token required on state-changing operations
   - Rate limiting active on /search
   - File uploads validate MIME type
   - Query length capped at 500 chars
</verification>

<success_criteria>
- [ ] All 5 security requirements (SEC-01 through SEC-05) implemented
- [ ] CSRF middleware active and validates tokens on POST/PUT/DELETE
- [ ] API key validated at startup; server refuses to start if missing
- [ ] SearchQuery.query has max_length=500 constraint
- [ ] /search endpoint rate-limited to 30 requests/minute per IP
- [ ] File uploads validate MIME type via magic bytes
- [ ] starlette-csrf, slowapi, python-magic added to requirements.txt
- [ ] Checkpoint verification complete
- [ ] All code committed with atomic commits per task
</success_criteria>

<output>
After completion, create `.planning/phases/01-security-data-integrity/01-SUMMARY.md` with:
- Timestamp and status (COMPLETE)
- All 5 security measures implemented and verified
- Files modified (app/main.py, app/config.py, app/models.py, requirements.txt, templates/admin.html if exists)
- Test coverage: Wave 0 test infrastructure established, stubs created for all security tests
- Key commits: CSRF middleware, API key validation, query length validation, rate limiting, MIME validation
- Dependencies installed: starlette-csrf, slowapi, python-magic
- Next steps: Proceed to Plan 02 (Data Integrity fixes)
</output>
