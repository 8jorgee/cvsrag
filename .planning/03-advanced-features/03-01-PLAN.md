---
phase: "03-advanced-features"
plan: "01"
wave: 1
type: "execute"
autonomous: true
requirements: ["FEAT-03", "FEAT-04"]
depends_on: []
files_modified:
  - app/db.py
  - app/main.py
  - app/templates/search.html
  - app/templates/partials/results.html
  - app/search/engine.py
---

<objective>
Enable users to export current search results as CSV or Excel, and display the last 20 search queries in a session-based history dropdown below the search bar.

**Purpose:** Increase user engagement by allowing offline result analysis (export) and enabling quick re-runs of previous searches (history) without re-typing.

**Output:**
- POST `/export` endpoint that returns downloadable CSV/Excel
- Session-based search history stored in SQLite (search_sessions and search_queries tables)
- Search history dropdown UI component in search.html
- Export button integrated into search results view
</objective>

<execution_context>
@/Users/8jorgee/.claude/rules/common/development-workflow.md
@/Users/8jorgee/.claude/rules/common/coding-style.md
@/Users/8jorgee/.claude/rules/common/testing.md
</execution_context>

<context>
@/Users/8jorgee/Desktop/cvsrag/.planning/ROADMAP.md
@/Users/8jorgee/Desktop/cvsrag/.planning/STATE.md
@/Users/8jorgee/Desktop/cvsrag/app/main.py (lines 251–297, /search endpoint)
@/Users/8jorgee/Desktop/cvsrag/app/db.py (lines 54–70, table creation)
@/Users/8jorgee/Desktop/cvsrag/app/models.py (SearchResult model)

## Key Dependencies

The export feature depends on openpyxl (already in requirements.txt). Search history requires:
- Session cookie (`session_id`) set on first page load
- SQLite tables for session tracking and query persistence
- Jinja2 template rendering for dropdown and button

## Design Notes

**Export format:**
- CSV: columns = [Name, Grade, Location, Skills, Certifications, Availability %, Availability Date, Score, Match Reasoning]
- Excel: same structure, one sheet named "Search Results"

**Session management:**
- Session ID stored in `session_id` cookie (secure, httponly, 30-day expiry)
- Search history queries stored per-session in database
- UI shows last 20 queries; clicking re-runs search with original parameters

**HTMX integration:**
- Export button in partials/results.html (POST to /export with form data)
- Search history dropdown in search.html (populated from template context on page load)
- History click triggers form submission via HTMX or standard form
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add search_sessions and search_queries tables to SQLite schema</name>
  <files>app/db.py</files>
  <action>
In db.py's _open_db() method (around line 50), add two new tables after the query_cache table:

1. **search_sessions** table:
   - id (TEXT PRIMARY KEY) — UUID session identifier
   - created_at (TEXT) — ISO timestamp
   - last_accessed (TEXT) — ISO timestamp (update on each search)

2. **search_queries** table:
   - id (INTEGER PRIMARY KEY AUTOINCREMENT)
   - session_id (TEXT FOREIGN KEY to search_sessions.id)
   - query_text (TEXT) — raw query string
   - mode (TEXT) — "smart" or "quick"
   - filters_json (TEXT) — JSON serialization of all filter params (skills, certs, availability, etc.)
   - created_at (TEXT) — ISO timestamp
   - results_count (INTEGER) — how many results returned

Create indexes on session_id and created_at for fast retrieval. Implement cleanup: delete sessions older than 30 days (run at startup).

No implementation of cleanup logic required in this task — just schema. Cleanup can be added in a future plan if needed.
  </action>
  <verify>
    ```bash
    sqlite3 /Users/8jorgee/Desktop/cvsrag/chroma_db/metadata.db ".schema" | grep -E "search_sessions|search_queries"
    ```
    Expected: Two tables with columns as described above.
  </verify>
  <done>SQLite schema includes search_sessions and search_queries tables with appropriate indexes and foreign keys.</done>
</task>

<task type="auto">
  <name>Task 2: Create session ID helper and history retrieval function in engine.py</name>
  <files>app/search/engine.py</files>
  <action>
Add three new functions to engine.py after the existing helper functions (after line 453):

1. **get_or_create_session(db_conn, session_id: str | None) -> str**
   - If session_id is None or doesn't exist in DB, create new session with UUID, return it
   - If session_id exists, update last_accessed timestamp, return it
   - Use ISO timestamp format (datetime.now().isoformat())

2. **log_search_query(db_conn, session_id: str, query: SearchQuery, results_count: int) -> None**
   - Insert row into search_queries with all params
   - Truncate session history to last 20 queries (delete older ones)

3. **get_search_history(db_conn, session_id: str) -> list[dict]**
   - Query last 20 search_queries rows for this session (ORDER BY created_at DESC)
   - Return list of dicts: {id, query_text, mode, created_at, results_count}
   - Used to populate the history dropdown in templates

All functions use the existing get_collection() singleton's ._conn (SQLite connection).
  </action>
  <verify>
    ```bash
    grep -n "def get_or_create_session\|def log_search_query\|def get_search_history" /Users/8jorgee/Desktop/cvsrag/app/search/engine.py
    ```
    Expected: All three functions defined with correct signatures.
  </verify>
  <done>Three helper functions added to engine.py for session management and history retrieval.</done>
</task>

<task type="auto">
  <name>Task 3: Integrate session tracking into POST /search endpoint</name>
  <files>app/main.py</files>
  <action>
Modify the POST /search endpoint (lines 251–297) to:

1. Extract session_id from request.cookies.get("session_id"), fallback to None
2. Call engine.get_or_create_session(get_collection()._conn, session_id) to get valid session ID
3. Run the existing search logic unchanged
4. Call engine.log_search_query(get_collection()._conn, session_id, search_query, len(result["results"])) to log the query
5. Set session_id cookie on response: HTTPResponse header "Set-Cookie: session_id={session_id}; Path=/; Max-Age=2592000; HttpOnly; Secure; SameSite=Lax"

Return the response with the cookie set (modify the TemplateResponse to include cookie headers or use response.set_cookie()).

No changes to search result rendering — just add logging and cookie setting.
  </action>
  <verify>
    ```bash
    grep -A 20 "async def do_search" /Users/8jorgee/Desktop/cvsrag/app/main.py | head -30
    ```
    Expected: get_or_create_session and log_search_query calls visible in the function body.
  </verify>
  <done>POST /search endpoint tracks session ID and logs each query to SQLite.</done>
</task>

<task type="auto">
  <name>Task 4: Add GET /search endpoint to load search history on initial page load</name>
  <files>app/main.py</files>
  <action>
Add a new GET route handler for "/" (modify existing GET / route at line 228–248 or add a new handler if needed):

When GET / is requested:
1. Extract session_id from request.cookies
2. Call engine.get_or_create_session(get_collection()._conn, session_id) to create if needed
3. Call engine.get_search_history(get_collection()._conn, session_id) to get last 20 queries
4. Pass session_id and search_history list to template context
5. Set session_id cookie on response

Return templates.TemplateResponse with context including session_id and search_history.

The GET / endpoint (search_page) should be updated; it already exists at lines 228–248. Add the session and history logic there.
  </action>
  <verify>
    ```bash
    grep -A 15 "async def search_page" /Users/8jorgee/Desktop/cvsrag/app/main.py | head -20
    ```
    Expected: get_or_create_session and get_search_history calls in the function.
  </verify>
  <done>GET / endpoint initializes session and populates search history context for template.</done>
</task>

<task type="auto">
  <name>Task 5: Create POST /export endpoint returning CSV/Excel from search results</name>
  <files>app/main.py</files>
  <action>
Add a new POST /export route in main.py after the /search endpoint:

```python
@app.post("/export")
@limiter.limit("10/minute")
async def export_results(
    request: Request,
    query: str = Form(""),
    mode: str = Form("smart"),
    skills: list[str] = Form(default=[]),
    certifications: list[str] = Form(default=[]),
    skills_any: list[str] = Form(default=[]),
    certifications_any: list[str] = Form(default=[]),
    availability_status: str = Form(""),
    availability_percentage_min: str = Form(""),
    grade: str = Form(""),
    location: str = Form(""),
    export_format: str = Form("csv"),  # "csv" or "xlsx"
):
```

Logic:
1. Build SearchQuery from form params (same as /search endpoint)
2. Call engine.search() to get results
3. Extract fields from results: name, grade, location, skills (comma-separated), certifications (comma-separated), availability_percentage, availability_date, score, match_reasoning
4. If export_format == "csv": return CSV as plain text file
5. If export_format == "xlsx": use openpyxl to create workbook, add one sheet named "Search Results" with headers and data rows, return Excel file

Use FastAPI's FileResponse or StreamingResponse. Filename should be: `search-results-{timestamp}.csv` or `.xlsx`

Columns: Name | Grade | Location | Skills | Certifications | Availability % | Availability Date | Score | Match Reasoning
  </action>
  <verify>
    ```bash
    curl -X POST http://localhost:8000/export \
      -F "query=python" \
      -F "export_format=csv" \
      -H "Accept: text/csv" | head -5
    ```
    Expected: CSV header row + at least one data row (or empty if no results).
  </verify>
  <done>POST /export endpoint returns downloadable CSV or Excel file with current search results.</done>
</task>

<task type="auto">
  <name>Task 6: Update search.html to show search history dropdown below search bar</name>
  <files>app/templates/search.html</files>
  <action>
In the search form section of search.html (where the text query input is), add a search history dropdown component below the search input:

Structure:
```html
<div class="search-history">
  <label for="history-dropdown">Recent Searches ({{ search_history|length }})</label>
  <select id="history-dropdown" name="history" onchange="replaySearch(this.value)">
    <option value="">-- Select a recent search --</option>
    {% for history_item in search_history %}
      <option value="{{ history_item.id }}" data-query="{{ history_item.query_text }}" data-mode="{{ history_item.mode }}" data-filters="{{ history_item.filters_json|e }}">
        {{ history_item.query_text[:40] }}... ({{ history_item.results_count }} results, {{ history_item.created_at[:10] }})
      </option>
    {% endfor %}
  </select>
</div>
```

Add a JavaScript snippet or HTMX target to replay the search when a history item is selected. Since this is HTMX frontend, consider using HTMX to reconstruct the form and submit, or use a simple JavaScript onclick handler that parses the data attributes and repopulates the form before submitting.

Simple approach: Use form.submit() after repopulating hidden inputs with the selected query params.

Alternative (HTMX): Add hx-post to dropdown that sends the selected query ID to a new endpoint /search-by-history/{history_id} that retrieves and re-executes that search.

Use simple JavaScript approach for now (no new backend endpoint needed).
  </action>
  <verify>
    ```bash
    grep -n "search-history\|history-dropdown" /Users/8jorgee/Desktop/cvsrag/app/templates/search.html
    ```
    Expected: HTML elements and JavaScript handler visible.
  </verify>
  <done>search.html displays dropdown with last 20 searches; clicking a history item re-runs that search.</done>
</task>

<task type="auto">
  <name>Task 7: Add Export button to search results template (partials/results.html)</name>
  <files>app/templates/partials/results.html</files>
  <action>
In the search results partial, add an Export button near the results header (e.g., next to "Results" title):

```html
<div class="results-header">
  <h2>Results ({{ total_count }} found)</h2>
  <form method="post" action="/export" style="display: inline;">
    <input type="hidden" name="query" value="{{ query }}">
    <input type="hidden" name="mode" value="quick">  <!-- Could be made dynamic -->
    <button type="submit" name="export_format" value="csv" class="btn-export">Export as CSV</button>
    <button type="submit" name="export_format" value="xlsx" class="btn-export">Export as Excel</button>
  </form>
</div>
```

Add a hidden form that contains all current search parameters so the export reflects the current filtered/paginated results. The form should POST to /export with all the same fields as the /search endpoint (query, mode, skills, certifications, skills_any, certifications_any, availability_status, availability_percentage_min, grade, location).

Style the export buttons with CSS class `.btn-export` (add to static/style.css if needed — keep styling minimal).
  </action>
  <verify>
    ```bash
    grep -n "Export\|export_format" /Users/8jorgee/Desktop/cvsrag/app/templates/partials/results.html
    ```
    Expected: Export button form visible with correct action="/export".
  </verify>
  <done>Search results page includes Export CSV and Export Excel buttons above the results list.</done>
</task>

</tasks>

<verification>
1. **Database schema:** Verify search_sessions and search_queries tables exist in metadata.db with correct columns and indexes.
2. **Session tracking:** Perform a search, verify session_id cookie is set in browser DevTools.
3. **Search history:** Make 3 different searches, refresh page, verify dropdown shows all 3 searches with correct query text.
4. **Export CSV:** Click "Export as CSV" from results page, verify file downloads with correct headers and data.
5. **Export Excel:** Click "Export as Excel" from results page, verify file downloads as .xlsx with "Search Results" sheet.
6. **History replay:** Click a history item from dropdown, verify search re-runs with same parameters.
7. **Cookie persistence:** Close and reopen browser, verify session ID persists and old searches are still in dropdown.
</verification>

<success_criteria>
- [ ] User can export current search results as CSV or Excel file
- [ ] Each search is logged to SQLite with full query parameters
- [ ] Search history dropdown displays last 20 queries below search bar
- [ ] Clicking a history item re-runs that exact search
- [ ] Session cookie persists across page reloads (30-day expiry)
- [ ] Export file includes all required columns: Name, Grade, Location, Skills, Certifications, Availability %, Availability Date, Score, Match Reasoning
</success_criteria>

<output>
After completion, create `.planning/03-advanced-features/03-01-SUMMARY.md` with:
- What was implemented
- File changes and line counts
- How to verify each feature
- Known issues or edge cases (if any)
</output>
