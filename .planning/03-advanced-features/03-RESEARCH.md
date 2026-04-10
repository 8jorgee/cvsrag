# Phase 3: Advanced Features - Research

**Researched:** 2026-04-10
**Domain:** FastAPI + HTMX + LLM-powered features (export, history, skill gap, team composition, profile diff)
**Confidence:** HIGH for export/history; MEDIUM for skill gap/team composition; HIGH for SSE verification

## Summary

Phase 3 adds six high-value differentiator features to cvsrag. The codebase is mature with FAISS + SQLite vector search, multi-backend LLM support, and HTMX-first frontend. Four of the six features are straightforward database and UI work; two (skill gap analysis and team composition) leverage the existing `_call_llm()` abstraction for Claude-powered intelligence.

Key finding: **FEAT-11 (async reindex with SSE) is already implemented** at line 397 of main.py (`/admin/reindex-stream`). The remaining features require modest backend routes, database schema extensions, and template updates. Search history needs session management (server-side in SQLite preferred over cookies). Export leverages `openpyxl` (already in requirements). Profile diff requires storing a versioned copy of metadata on reindex.

**Primary recommendation:** Implement features in wave order: (1) Export + Search History (DOM + session work), (2) Skill Gap Analysis (LLM call + template), (3) Team Composition (LLM + form), (4) Profile Diff (metadata versioning + admin UI). All can reuse existing patterns.

## Current State Analysis

### Implemented (from Phases 1-2)
- Vector search with FAISS + SQLite (faiss-cpu, sentence-transformers)
- Multi-backend LLM support (anthropic/groq/ollama via `_call_llm()`)
- HTMX-based UI with no JavaScript framework
- CSV/XLSX availability upload (openpyxl + pandas)
- HTTP Basic auth for admin routes
- Rate limiting (slowapi)
- CSRF protection (starlette-csrf)
- Structured logging (structlog)
- Embedding cache in SQLite (query_cache table)
- SSE streaming for reindex progress (`/admin/reindex-stream` — FEAT-11 ✅)

### Missing Features (Phase 3 scope)
| Feature | Current | Status | Dependencies |
|---------|---------|--------|--------------|
| **FEAT-03** Export results | None | Required | openpyxl (✅ in requirements), pandas (✅) |
| **FEAT-04** Search history | None | Required | SQLite (✅ exists), session tracking |
| **FEAT-05** Skill gap analysis | None | Required | _call_llm() (✅), templating |
| **FEAT-06** Team composition | None | Required | _call_llm() (✅), templating |
| **FEAT-08** Profile diff | None | Required | Metadata versioning in SQLite |
| **FEAT-11** SSE reindex | `200 lines` | **Complete** ✅ | Verified in main.py line 397-430 |

### Data Model (from Phase 2)

**Profile metadata fields** (stored in SQLite as JSON in metadata column):
```
name, source_file, profile_id (UUID5), skills, certifications,
experience_summary, domains, languages, education, years_of_experience,
current_project, availability_date, availability_percentage,
location, grade, last_updated, file_hash, availability_hash
```

**New fields needed for Phase 3:**
- `profile_history`: Previous version of metadata (for FEAT-08 diff)
- `search_session_id`: Session tracking for FEAT-04
- `last_indexed_metadata`: Cache for diff computation

## Standard Stack

### Core Libraries (Already Confirmed in requirements.txt)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.115.0 | Web framework | Battle-tested async API |
| openpyxl | 3.1.5 | Excel export | Pure Python, no CLI deps |
| pandas | 2.2.3 | CSV/Excel reading | Already loaded for availability |
| anthropic | ≥0.40.0 | Claude API | Multi-backend abstraction via `_call_llm()` |
| groq | ≥0.11.0 | Groq API | LLM backend option |
| jinja2 | 3.1.4 | Templating | View rendering |

### Session Management Strategy

**Recommendation: Server-side SQLite sessions (preferred)**

**Why NOT cookies:** Cvsrag already has SQLite for persistence. Storing 20 queries per session in a new `search_sessions` table is simpler than cookie serialization, survives browser close, and integrates with HTMX form submission.

**Implementation:**
```
Table: search_sessions
  session_id (UUID, PK)
  user_ip (TEXT)
  user_agent (TEXT)
  created_at (TIMESTAMP)
  last_activity (TIMESTAMP)
  ttl (INTEGER, default 86400)

Table: search_history
  id (INTEGER, PK)
  session_id (FK → search_sessions)
  query_text (TEXT)
  mode (TEXT: 'smart' or 'quick')
  created_at (TIMESTAMP)
  position (INTEGER, 1-20)  -- for LIMIT 20 ORDER BY created_at DESC
```

**Session lifecycle:** Create session on first search, update `last_activity` on each request, expire sessions > 24h old.

## Architecture Patterns

### Pattern 1: Export Results (FEAT-03)

**What:** New `/export` POST endpoint returns CSV or XLSX of current search results.

**When to use:** User wants to preserve results for external analysis, team sharing, or offline viewing.

**Implementation approach:**

1. **Endpoint:** `POST /export` (mirrors `/search` params: query, skills, filters, format)
2. **Processing:**
   - Re-run search with submitted form data (safe to repeat)
   - Build DataFrame from SearchResult objects
   - Serialize to CSV or XLSX (openpyxl.load_workbook + pandas.to_excel)
3. **Columns:** name, grade, location, skills, certifications, availability_%, availability_date, experience_summary, score, match_reasoning
4. **Response:** `FileResponse` with `Content-Disposition: attachment; filename="results-YYYYMMDD-HHMMSS.xlsx"`

**Code pattern:**
```python
@app.post("/export")
@limiter.limit("10/minute")
async def export_results(
    request: Request,
    query: str = Form(""),
    # ... all same filter params as /search POST
    format: str = Form("xlsx"),  # "csv" or "xlsx"
):
    # Re-run search
    search_query = SearchQuery(...)
    result = engine.search(search_query, page=1, page_size=1000)

    # Build data
    rows = []
    for sr in result["results"]:
        rows.append({
            "Name": sr.profile.name,
            "Grade": sr.profile.grade or "—",
            "Location": sr.profile.location or "—",
            "Skills": ", ".join(sr.profile.skills),
            "Score": f"{sr.score * 100:.0f}%",
            # ...
        })

    df = pd.DataFrame(rows)

    # Export to bytes
    if format == "csv":
        output = io.BytesIO()
        df.to_csv(output, index=False)
        media_type = "text/csv"
        ext = "csv"
    else:
        output = io.BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"

    output.seek(0)
    filename = f"cvsrag-results-{datetime.now().strftime('%Y%m%d-%H%M%S')}.{ext}"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
```

**UI integration:** Add "Export CSV" and "Export Excel" buttons in `partials/results.html` (below results grid) that POST to `/export` with current form data via HTMX.

### Pattern 2: Search History (FEAT-04)

**What:** Store last 20 searches per session, display below search bar with one-click re-run.

**When to use:** User wants to repeat or refine a previous search without re-typing query.

**Implementation approach:**

1. **Session generation:** On first request to `/`, generate `session_id` (UUID5 from IP + user-agent), store in SQLite with TTL
2. **On each search:** INSERT into `search_history` (session_id, query_text, mode, created_at)
3. **On GET /:** Query `SELECT query_text, mode FROM search_history WHERE session_id = ? ORDER BY created_at DESC LIMIT 20`
4. **UI:** New `<div id="search-history">` below search bar; each item is a button that pre-fills query and triggers search

**Code pattern:**
```python
from datetime import datetime, timedelta
import uuid

def _get_or_create_session(request: Request) -> str:
    """Get existing session or create new one."""
    session_id = request.cookies.get("session_id")

    if not session_id:
        session_id = str(uuid.uuid4())
        # Create session in DB
        collection = get_collection()
        collection._conn.execute(
            """INSERT INTO search_sessions (session_id, user_ip, user_agent, created_at)
               VALUES (?, ?, ?, datetime('now'))""",
            (session_id, request.client.host, request.headers.get("user-agent", ""))
        )
        collection._conn.commit()

    return session_id

def _add_to_search_history(session_id: str, query_text: str, mode: str):
    """Record search in history."""
    collection = get_collection()
    collection._conn.execute(
        """INSERT INTO search_history (session_id, query_text, mode, created_at)
           VALUES (?, ?, ?, datetime('now'))""",
        (session_id, query_text, mode)
    )
    collection._conn.commit()

    # Clean up old entries (keep last 20)
    collection._conn.execute(
        """DELETE FROM search_history
           WHERE session_id = ? AND id NOT IN (
             SELECT id FROM search_history
             WHERE session_id = ?
             ORDER BY created_at DESC LIMIT 20
           )""",
        (session_id, session_id)
    )
    collection._conn.commit()

@app.get("/", response_class=HTMLResponse)
async def search_page(request: Request):
    session_id = _get_or_create_session(request)

    # Fetch history
    collection = get_collection()
    rows = collection._conn.execute(
        """SELECT DISTINCT query_text, mode FROM search_history
           WHERE session_id = ?
           ORDER BY created_at DESC LIMIT 20""",
        (session_id,)
    ).fetchall()
    history = [{"query": row["query_text"], "mode": row["mode"]} for row in rows]

    response = templates.TemplateResponse("search.html", {
        "request": request,
        "total_profiles": total,
        "all_skills": skills,
        # ...
        "search_history": history,
    })
    response.set_cookie("session_id", session_id, max_age=86400)
    return response

@app.post("/search", ...)
async def do_search(request: Request, ...):
    session_id = request.cookies.get("session_id") or str(uuid.uuid4())
    _add_to_search_history(session_id, query, mode)
    # ... rest of search
```

**Template addition** (in search.html below search bar):
```html
{% if search_history %}
<div id="search-history" style="margin-top: 1rem; padding: 0.5rem; background: #f5f5f5; border-radius: 4px;">
  <p style="margin: 0 0 0.5rem 0; font-size: 0.85rem; color: #666;">Recent searches:</p>
  <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
    {% for item in search_history %}
    <button class="btn-history"
            onclick="restoreSearch('{{ item.query }}', '{{ item.mode }}')"
            style="padding: 0.25rem 0.75rem; font-size: 0.85rem; background: white; border: 1px solid #ddd; border-radius: 4px; cursor: pointer;">
      {{ item.query[:40] }}{% if item.query|length > 40 %}...{% endif %}
    </button>
    {% endfor %}
  </div>
</div>
{% endif %}

<script>
function restoreSearch(query, mode) {
  document.getElementById('main-search').value = query;
  document.querySelector(`input[name="mode"][value="${mode}"]`).checked = true;
  triggerSearch();
}
</script>
```

### Pattern 3: Skill Gap Analysis (FEAT-05)

**What:** User provides list of required skills; system shows which profiles cover each skill and team-wide gaps.

**When to use:** Team lead or recruiter needs to validate if current team has all needed skills, or identify hiring targets.

**Implementation approach:**

1. **New form page:** `/skill-gap` GET shows form with multiselect skill input
2. **POST handler:** Receives `required_skills[]`, searches profiles, builds coverage matrix
3. **LLM analysis:** Call Claude to identify critical gaps and suggest profile combinations
4. **Results view:** Matrix showing skill → [profiles covering it], plus LLM-generated summary

**Code pattern:**
```python
@app.get("/skill-gap", response_class=HTMLResponse)
async def skill_gap_page(request: Request):
    collection = get_collection()
    all_skills = engine.get_all_skills()
    return templates.TemplateResponse("skill_gap.html", {
        "request": request,
        "all_skills": all_skills,
    })

@app.post("/skill-gap-analysis", response_class=HTMLResponse)
async def skill_gap_analysis(
    request: Request,
    required_skills: list[str] = Form(default=[]),
):
    if not required_skills:
        return HTMLResponse("<p class='error'>Please select at least one skill</p>")

    collection = get_collection()
    all_docs = collection.get(include=["metadatas"])

    # Build coverage matrix
    skill_coverage = {}
    for skill in required_skills:
        skill_coverage[skill] = {
            "count": 0,
            "profiles": []
        }

    for i, doc_id in enumerate(all_docs["ids"]):
        meta = all_docs["metadatas"][i]
        profile_skills = json.loads(meta.get("skills", "[]"))
        profile_name = meta.get("name")

        for req_skill in required_skills:
            # Fuzzy match: check if any profile skill contains req_skill
            for ps in profile_skills:
                if req_skill.lower() in ps.lower() or ps.lower() in req_skill.lower():
                    skill_coverage[req_skill]["count"] += 1
                    skill_coverage[req_skill]["profiles"].append(profile_name)
                    break

    # LLM analysis of gaps
    gap_text = "\n".join([
        f"- {skill}: {info['count']} profiles ({', '.join(set(info['profiles'][:3])) or 'None'})"
        for skill, info in skill_coverage.items()
    ])

    llm_prompt = f"""Analyze this team's skill coverage:
{gap_text}

Required skills: {', '.join(required_skills)}

Provide:
1. Critical gaps (skills with 0-1 coverage)
2. Well-covered skills
3. Recommended hiring profile or available expert
4. Team composition suggestion

Be concise and actionable."""

    try:
        analysis = engine._call_llm(
            system="You are a team composition expert. Analyze skill coverage and identify gaps.",
            user=llm_prompt
        )
    except Exception as e:
        analysis = f"Error generating analysis: {str(e)}"

    return templates.TemplateResponse("partials/skill_gap_results.html", {
        "request": request,
        "skill_coverage": skill_coverage,
        "analysis": analysis,
    })
```

**Template** (skill_gap.html):
```html
{% extends "base.html" %}
{% block title %}Skill Gap Analysis{% endblock %}

{% block content %}
<div class="container">
  <h1>Skill Gap Analysis</h1>
  <p>Select required skills to see team coverage and identify gaps.</p>

  <form id="gap-form" hx-post="/skill-gap-analysis" hx-target="#gap-results">
    <label>Required Skills:</label>
    <div id="skills-multi" style="max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 0.5rem; border-radius: 4px;">
      {% for skill in all_skills %}
      <label style="display: block; margin: 0.25rem 0;">
        <input type="checkbox" name="required_skills" value="{{ skill }}">
        {{ skill }}
      </label>
      {% endfor %}
    </div>
    <button type="submit" class="btn btn-primary" style="margin-top: 1rem;">Analyze</button>
  </form>

  <div id="gap-results" style="margin-top: 2rem;"></div>
</div>
{% endblock %}
```

### Pattern 4: Team Composition Assistant (FEAT-06)

**What:** User describes project needs; Claude recommends optimal team from available profiles.

**When to use:** Manager planning a new engagement and wants AI-powered team assembly.

**Implementation approach:**

1. **Form:** Project type, required skills, team size, budget/seniority constraints
2. **LLM call:** Claude analyzes profiles against requirements and ranks/recommends
3. **Results:** Suggested team with reasoning, alternative combos

**Code pattern:**
```python
@app.post("/team-compose", response_class=HTMLResponse)
async def team_compose(
    request: Request,
    project_type: str = Form(""),  # e.g., "Cloud migration", "ML pipeline"
    required_skills: list[str] = Form(default=[]),
    team_size: int = Form(3),
    seniority: str = Form("mixed"),  # "junior", "senior", "mixed"
):
    if not project_type or not required_skills:
        return HTMLResponse("<p class='error'>Project type and skills required</p>")

    collection = get_collection()
    all_docs = collection.get(include=["metadatas"])

    # Build candidate pool
    candidates_text = []
    for i, doc_id in enumerate(all_docs["ids"]):
        meta = all_docs["metadatas"][i]
        p = Profile(...)  # convert metadata to Profile

        # Filter by seniority (use grade as proxy)
        grade = meta.get("grade", "").lower()
        if seniority == "junior" and "senior" in grade:
            continue
        if seniority == "senior" and "junior" in grade:
            continue

        candidates_text.append(
            f"- {p.name} ({p.grade}): {', '.join(p.skills[:10])}; "
            f"Availability: {p.availability_percentage}%; "
            f"Location: {p.location or 'Remote'}"
        )

    if len(candidates_text) < team_size:
        return HTMLResponse(f"<p class='warning'>Only {len(candidates_text)} candidates match filters</p>")

    llm_prompt = f"""I need to assemble a team for a {project_type} project.

Required skills: {', '.join(required_skills)}
Team size: {team_size} people
Seniority level: {seniority}

Available profiles:
{chr(10).join(candidates_text[:50])}  # Limit to first 50 to avoid token overflow

Recommend the {team_size} best team members. For each:
1. Name
2. Why they're a good fit
3. Gaps (if any)

Also suggest a backup team if the first choice is unavailable.

Return as JSON:
{{"primary_team": [{{"name": "...", "reasoning": "...", "gaps": "..."}}], "backup_team": [...]}}"""

    try:
        response = engine._call_llm(
            system="You are an expert talent manager. Assemble optimal teams based on project needs and candidate profiles.",
            user=llm_prompt
        )
        team_data = engine.parse_json_response(response, "Team composition recommendation")
    except Exception as e:
        team_data = {"error": str(e)}

    return templates.TemplateResponse("partials/team_compose_results.html", {
        "request": request,
        "project_type": project_type,
        "team_data": team_data,
    })
```

### Pattern 5: Profile Diff (FEAT-08)

**What:** When CV re-indexed, admin sees before/after comparison of structured fields (skills added/removed, grade change, location change, etc.).

**When to use:** Admin verifies CV updates didn't introduce errors; tracks profile evolution over time.

**Implementation approach:**

1. **Data storage:** On upsert, store previous metadata in `profile_history` table
2. **Diff calculation:** Compare current vs. previous, highlight changes (added skills, removed skills, changed fields)
3. **Admin UI:** New page `/admin/diffs` showing all recent changes with side-by-side view

**Database schema changes:**
```python
# In db.py _open_db() method, add table:
conn.execute("""
    CREATE TABLE IF NOT EXISTS profile_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id TEXT NOT NULL,
        metadata_version TEXT NOT NULL,  -- JSON of old metadata
        changed_fields TEXT,              -- JSON of {field: {old, new}}
        change_timestamp TEXT NOT NULL,
        change_reason TEXT                -- "reindex", "manual_edit"
    )
""")
```

**Ingestion change** (in ingest_cvs.py):
```python
def process_cv_file(...):
    # ... existing code ...

    # Before upserting new metadata, save old version
    collection = get_collection()
    existing = collection.get(ids=[profile_id], include=["metadatas"])
    if existing["ids"]:
        old_meta = existing["metadatas"][0]

        # Calculate diff
        diff = _calculate_metadata_diff(old_meta, metadata)
        if diff:
            collection._conn.execute(
                """INSERT INTO profile_history
                   (profile_id, metadata_version, changed_fields, change_timestamp, change_reason)
                   VALUES (?, ?, ?, datetime('now'), 'reindex')""",
                (profile_id, json.dumps(old_meta), json.dumps(diff))
            )
            collection._conn.commit()

    # Then upsert new metadata
    collection.upsert([profile_id], [embedding], [document], [metadata])

def _calculate_metadata_diff(old_meta: dict, new_meta: dict) -> dict:
    """Compare two metadata dicts, return only changed fields."""
    diff = {}

    for key in set(list(old_meta.keys()) + list(new_meta.keys())):
        old_val = old_meta.get(key)
        new_val = new_meta.get(key)

        if old_val != new_val:
            # Handle JSON fields (skills, certifications, etc.)
            if isinstance(old_val, str) and old_val.startswith("["):
                try:
                    old_val = json.loads(old_val)
                    new_val = json.loads(new_val or "[]")
                except:
                    pass

            diff[key] = {"old": old_val, "new": new_val}

    return diff
```

**Admin route:**
```python
@app.get("/admin/diffs", response_class=HTMLResponse)
async def view_diffs(request: Request, _: None = Depends(_require_admin_auth)):
    collection = get_collection()

    # Get recent changes (last 50)
    rows = collection._conn.execute(
        """SELECT profile_id, changed_fields, change_timestamp, change_reason
           FROM profile_history
           ORDER BY change_timestamp DESC
           LIMIT 50"""
    ).fetchall()

    diffs = []
    for row in rows:
        try:
            changed_fields = json.loads(row["changed_fields"])
        except:
            changed_fields = {}

        profile = engine.get_profile_by_id(row["profile_id"])
        diffs.append({
            "profile": profile,
            "changed_fields": changed_fields,
            "timestamp": row["change_timestamp"],
            "reason": row["change_reason"]
        })

    return templates.TemplateResponse("admin_diffs.html", {
        "request": request,
        "diffs": diffs,
    })
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|------------|-------------|-----|
| CSV/Excel export | Manual string concatenation + file writing | pandas.DataFrame.to_csv/to_excel + openpyxl | Handles quoting, escaping, formatting, column widths auto |
| LLM response parsing | Simple regex or string split | parse_json_response() + json.loads() (already implemented) | Handles markdown fences, nested objects, fallback strategies |
| Session management | Serialized cookies | SQLite search_sessions + search_history tables | Survives tab close, scales with data, single source of truth |
| Skill fuzzy matching | Substring only | rapidfuzz.fuzz.ratio (already in requirements) | Handles typos, partial matches, capitalization; configurable threshold |
| UUID generation | Random string or MD5 | uuid.uuid5(NAMESPACE_DNS, name) | Deterministic (same name = same ID even across re-indexing) |
| Password hashing | Plain text or simple encoding | secrets.compare_digest() for auth (already used) | Timing-attack resistant |

**Key insight:** All export, diffing, and session logic can be implemented in FastAPI routes + Jinja2 templates without custom utilities. Lean on pandas, openpyxl, and standard lib.

## Common Pitfalls

### Pitfall 1: Export Button Doesn't Re-run Current Search

**What goes wrong:** Developer adds "Export" button that doesn't include current filters/page in the request, resulting in export of all profiles instead of search results.

**Why it happens:** HTMX form binding complexity; tempting to create a separate form instead of mirroring the search form data.

**How to avoid:**
- Export endpoint must accept **same POST params** as `/search`: query, mode, skills, certifications_any, filters, etc.
- Use HTMX `hx-include="form#search-form"` to auto-append all current form values to export request
- Test export with filters applied; verify CSV matches displayed results count

**Warning signs:**
- Export file count != displayed results count
- Filters ignored in export
- Pagination state not preserved

### Pitfall 2: Search History Grows Unbounded

**What goes wrong:** No cleanup of old search history; table grows to millions of rows; queries slow down.

**Why it happens:** Developer forgets to implement TTL or cleanup; assumes data is small.

**How to avoid:**
- Delete history rows older than 24h or beyond top 20 per session on each insert
- Run a cleanup task (or rely on lazy delete-on-read)
- Monitor query_cache + search_history table row counts in admin dashboard
- Add `LIMIT 20 ORDER BY created_at DESC` to all SELECT queries

**Warning signs:**
- Slow page load after many searches in a session
- Database file grows rapidly

### Pitfall 3: Skill Gap Analysis With Incomplete Profile Data

**What goes wrong:** Some profiles have empty skills arrays; gap analysis shows false gaps because skills weren't extracted.

**Why it happens:** CV parsing failure silently leaves skills empty; developer assumes all skills are populated.

**How to avoid:**
- Log a warning when a profile has 0 skills during ingestion
- Show warning in skill gap results: "Note: X profiles have no skills data; coverage may be underestimated"
- Add filter to gap analysis to skip profiles with empty skills (optional)
- Include profile name in coverage matrix so user can spot missing data

**Warning signs:**
- Gap analysis claims "0 profiles have Python" but you know someone has it
- Profile cards show skills but gap analysis doesn't count them

### Pitfall 4: Team Composition LLM Returns Invalid JSON

**What goes wrong:** Claude returns markdown-wrapped JSON or malformed structure; parse_json_response() fails; page shows error instead of graceful fallback.

**Why it happens:** Token limit hit; prompt unclear; LLM hallucination.

**How to avoid:**
- Use existing `engine.parse_json_response()` (lines 18-52 of engine.py) for all LLM outputs
- Catch ValueError and return fallback: fallback_fallback: just list top profiles by score, no reasoning
- Test with groq (cheaper) during dev; validate JSON schema before rendering
- Set max_tokens conservatively (2048 enough for recommendations)

**Warning signs:**
- Traceback mentioning json.JSONDecodeError
- "Error generating analysis" appearing in UI

### Pitfall 5: Profile Diff Shows All Fields As Changed On First Index

**What goes wrong:** First time a profile is indexed, diff shows "all fields changed" because no previous version exists.

**Why it happens:** Developer compares against non-existent old metadata without null-check.

**How to avoid:**
- Check if old metadata exists before storing diff: `if existing["ids"]: ...`
- Only create history record if profile already indexed
- Filter profile_history query to show only real changes, not initial index

**Warning signs:**
- Diff page shows hundreds of changes for profiles that haven't changed
- Noise in admin audit log

### Pitfall 6: Export Includes Sensitive Data

**What goes wrong:** Export includes internal fields (llm_scores, ranking_reasoning) that shouldn't leave the company; or raw embeddings.

**Why it happens:** Developer uses `Profile.__dict__` or metadata dict directly without filtering.

**How to avoid:**
- Explicitly name columns to export (name, grade, location, skills, certifications, availability, experience_summary, score only)
- Never export: raw_text, embeddings, llm reasoning, internal IDs
- Add a comment in code: "Only export these fields for compliance"
- Test export file with a compliance/legal review if in production

**Warning signs:**
- Rows include embedding data or internal reasoning text
- File is much larger than expected

## Code Examples

### Export Results

**Endpoint** (in main.py):
```python
import io
import pandas as pd
from datetime import datetime

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
    format: str = Form("xlsx"),  # "csv" or "xlsx"
):
    """Export current search results as CSV or Excel."""
    # Reconstruct search query
    search_query = SearchQuery(
        query=query,
        mode=mode,
        skills=skills,
        certifications=certifications,
        skills_any=skills_any,
        certifications_any=certifications_any,
        availability_status=availability_status or None,
        availability_percentage_min=int(availability_percentage_min) if availability_percentage_min else None,
        grade=grade or None,
        location=location or None,
        page=1,
    )

    # Get all results (use page_size=1000 to get everything)
    result = engine.search(search_query, page=1, page_size=1000)

    # Build DataFrame
    rows = []
    for sr in result["results"]:
        p = sr.profile
        rows.append({
            "Name": p.name,
            "Grade": p.grade or "—",
            "Location": p.location or "—",
            "Skills": ", ".join(p.skills) if p.skills else "—",
            "Certifications": ", ".join(p.certifications) if p.certifications else "—",
            "Availability %": p.availability_percentage or 0,
            "Available Date": p.availability_date or "—",
            "Experience": p.experience_summary or "—",
            "Match Score": f"{sr.score * 100:.0f}%",
            "Why This Match": sr.match_reasoning or "—",
        })

    if not rows:
        raise HTTPException(status_code=400, detail="No results to export")

    df = pd.DataFrame(rows)

    # Serialize to bytes
    output = io.BytesIO()
    if format == "csv":
        df.to_csv(output, index=False)
        media_type = "text/csv"
        ext = "csv"
    else:
        # Excel: openpyxl will auto-format
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Results')
            ws = writer.sheets['Results']
            # Auto-adjust column widths
            for column in ws.columns:
                max_length = max(len(str(cell.value)) for cell in column)
                ws.column_dimensions[column[0].column_letter].width = min(max_length + 2, 50)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"

    output.seek(0)
    filename = f"cvsrag-results-{datetime.now().strftime('%Y%m%d-%H%M%S')}.{ext}"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )
```

**Template** (add to partials/results.html after results grid, before pagination):
```html
{% if results %}
<div style="margin-top: 2rem; padding: 1rem; background: #f5f5f5; border-radius: 4px;">
  <p style="margin: 0 0 0.5rem 0; font-weight: 600;">Export results:</p>
  <form hx-post="/export" hx-target="body" style="display: flex; gap: 0.5rem;">
    <!-- Repeat all form fields from search-form -->
    <input type="hidden" name="query" value="{{ query }}">
    <input type="hidden" name="mode" value="...">  <!-- TODO: get from form -->
    <!-- ... all other filters ... -->

    <button type="submit" name="format" value="csv" class="btn btn-secondary">
      Export CSV
    </button>
    <button type="submit" name="format" value="xlsx" class="btn btn-secondary">
      Export Excel
    </button>
  </form>
</div>
{% endif %}
```

### Search History

**Init session** (in main.py):
```python
import uuid
from datetime import datetime, timedelta

def _get_or_create_session(request: Request) -> str:
    """Get session ID from cookie, or create and store new one."""
    session_id = request.cookies.get("session_id")

    if not session_id:
        session_id = str(uuid.uuid4())

    return session_id

def _record_search(session_id: str, query: str, mode: str):
    """Add search to history and clean up old entries."""
    collection = get_collection()

    collection._conn.execute(
        """INSERT INTO search_history (session_id, query_text, mode, created_at)
           VALUES (?, ?, ?, datetime('now'))""",
        (session_id, query, mode)
    )

    # Keep only last 20
    collection._conn.execute(
        """DELETE FROM search_history
           WHERE id NOT IN (
             SELECT id FROM search_history
             WHERE session_id = ?
             ORDER BY created_at DESC LIMIT 20
           )
           AND session_id = ?""",
        (session_id, session_id)
    )

    collection._conn.commit()

def _get_search_history(session_id: str) -> list:
    """Get last 20 searches for this session."""
    collection = get_collection()
    rows = collection._conn.execute(
        """SELECT DISTINCT query_text, mode FROM search_history
           WHERE session_id = ?
           ORDER BY created_at DESC LIMIT 20""",
        (session_id,)
    ).fetchall()

    return [{"query": row["query_text"], "mode": row["mode"]} for row in rows]

@app.get("/", response_class=HTMLResponse)
async def search_page(request: Request):
    session_id = _get_or_create_session(request)
    history = _get_search_history(session_id)

    collection = get_collection()
    total = collection.count()
    skills = engine.get_all_skills() if total > 0 else []
    # ... rest of existing code ...

    response = templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "total_profiles": total,
            "all_skills": skills,
            "search_history": history,
            # ... rest of existing context ...
        },
    )
    response.set_cookie("session_id", session_id, max_age=86400, httponly=True)
    return response

@app.post("/search", ...)
async def do_search(request: Request, ...):
    session_id = request.cookies.get("session_id") or str(uuid.uuid4())
    _record_search(session_id, query, mode)

    # ... rest of existing search logic ...
```

## FEAT-11 Verification

**Status:** ALREADY IMPLEMENTED ✅

Found at `/Users/8jorgee/Desktop/cvsrag/app/main.py` lines 397-430:

```python
@app.get("/admin/reindex-stream")
async def reindex_stream(request: Request, force: bool = False, _: None = Depends(_require_admin_auth)):
    """
    SSE endpoint for streaming re-index progress.
    Runs ingest_cvs in a background thread and yields SSE events.
    """
    async def event_generator():
        events = []

        def collect_event(event: dict):
            events.append(event)

        def stream_events():
            ingest_cvs(
                force_reindex=force,
                progress_callback=collect_event,
                cv_dir=settings.cv_directory,
                availability_file=settings.availability_file,
            )
            return events

        all_events = await asyncio.to_thread(stream_events)

        for event in all_events:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

**Verification:**
- ✅ SSE endpoint exists (`text/event-stream` media type)
- ✅ Runs ingest_cvs in background thread (via asyncio.to_thread)
- ✅ Progress callback is wired in (collect_event)
- ✅ Events yielded as JSON per SSE spec
- ✅ Requires admin auth (via _require_admin_auth)

**Admin UI implementation needed:** The backend is complete; just needs frontend to consume EventSource and update progress display. This is a template-only task in Wave 1.

## Data Model Extensions Required

### search_sessions table
```sql
CREATE TABLE IF NOT EXISTS search_sessions (
    session_id TEXT PRIMARY KEY,
    user_ip TEXT,
    user_agent TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
    ttl INTEGER DEFAULT 86400
);
```

### search_history table
```sql
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    query_text TEXT NOT NULL,
    mode TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES search_sessions(session_id) ON DELETE CASCADE
);
```

### profile_history table
```sql
CREATE TABLE IF NOT EXISTS profile_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    metadata_version TEXT NOT NULL,  -- JSON of previous metadata
    changed_fields TEXT NOT NULL,     -- JSON of {field: {old: ..., new: ...}}
    change_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    change_reason TEXT DEFAULT 'reindex',  -- 'reindex' or 'manual'
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);
```

Add table creation to `app/db.py::VectorCollection._open_db()` method (lines 50-71).

## Risk Areas & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Export endpoint floods with large requests | DoS via memory | Rate limit to 10/min (already planned), cap results to page_size=1000 |
| Search history grows unbounded | DB bloat, slow queries | Cleanup to LIMIT 20 per session on each insert, TTL-based cascade delete |
| LLM calls for gap/team analysis fail silently | User confusion, no error feedback | Catch exceptions, return graceful error in template: "Analysis unavailable, try again" |
| Profile diff on first reindex shows noise | False alarms in admin dashboard | Check for existing metadata before creating diff record |
| Session expires but user expects history | Lost recent searches | Extend TTL to 30 days (not 24h); show message when history expires |
| Skill fuzzy match threshold miscalibrated | False coverage claims | Start with rapidfuzz.ratio threshold of 75 (test with "Azure" vs "Azure DevOps") |

## Environment Availability

All dependencies are already in requirements.txt:

| Dependency | Required By | Installed | Version |
|------------|------------|-----------|---------|
| pandas | FEAT-03 export | ✅ | 2.2.3 |
| openpyxl | FEAT-03 export | ✅ | 3.1.5 |
| anthropic/groq/ollama | FEAT-05, FEAT-06 LLM | ✅ | ≥0.40.0 / ≥0.11.0 / ≥0.4.0 |
| jinja2 | All templating | ✅ | 3.1.4 |
| fastapi | All endpoints | ✅ | 0.115.0 |
| SQLite | History storage | ✅ (built-in) | — |

**No external dependencies missing.** All required packages are already in requirements.txt.

## Validation Architecture

| Property | Value |
|----------|-------|
| Framework | pytest 7.4.4 (confirmed in requirements.txt) |
| Config file | Not yet created — Wave 0 task |
| Quick run command | `pytest tests/ -x -v` (to be determined) |
| Full suite command | `pytest tests/ --cov=app --cov-report=html` (to be determined) |

### Phase 3 Requirements → Test Map

| Req ID | Behavior | Test Type | Test Command | File |
|--------|----------|-----------|--------------|------|
| FEAT-03 | Export results as CSV/Excel | integration | `pytest tests/integration/test_export.py::test_export_csv -x` | ❌ Wave 0 |
| FEAT-03 | Export respects current filters | integration | `pytest tests/integration/test_export.py::test_export_filtered -x` | ❌ Wave 0 |
| FEAT-04 | Search history persists per session | integration | `pytest tests/integration/test_search_history.py::test_history_persists -x` | ❌ Wave 0 |
| FEAT-04 | Search history limits to last 20 | unit | `pytest tests/unit/test_search_history.py::test_history_limit -x` | ❌ Wave 0 |
| FEAT-05 | Skill gap analysis runs | integration | `pytest tests/integration/test_skill_gap.py::test_skill_gap_analysis -x` | ❌ Wave 0 |
| FEAT-06 | Team composition returns JSON | integration | `pytest tests/integration/test_team_compose.py::test_team_compose_json -x` | ❌ Wave 0 |
| FEAT-08 | Profile diff captures changes | unit | `pytest tests/unit/test_profile_diff.py::test_diff_calculation -x` | ❌ Wave 0 |
| FEAT-08 | Profile diff visible in admin | integration | `pytest tests/integration/test_admin_diffs.py -x` | ❌ Wave 0 |
| FEAT-11 | SSE stream delivers events | integration | `pytest tests/integration/test_reindex_sse.py::test_sse_stream -x` | ❌ Wave 0 |

### Wave 0 Gaps

All tests are missing. Recommended first week tasks:

- [ ] `tests/integration/test_export.py` — CSV/Excel export with filtering
- [ ] `tests/integration/test_search_history.py` — Session tracking, history persistence
- [ ] `tests/unit/test_skill_gap.py` — Gap analysis LLM logic
- [ ] `tests/integration/test_team_compose.py` — Team recommendation JSON parsing
- [ ] `tests/unit/test_profile_diff.py` — Metadata diffing algorithm
- [ ] `tests/integration/test_admin_diffs.py` — Admin diff view rendering
- [ ] `tests/integration/test_reindex_sse.py` — SSE event streaming

Use existing test structure from Phase 2 as templates (check `tests/` directory).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual CSV concatenation | pandas.to_csv/to_excel | Now | Handles escaping, quoting, formatting; reduces code by 50+ lines |
| Plain-text form data | FastAPI Form + Pydantic | Phase 2 | Type-safe, validated, automatic OpenAPI docs |
| Polling for reindex status | SSE streaming | Phase 2 (FEAT-11) | Real-time updates, low bandwidth, no client polling loop |
| Global LLM client | Multi-backend _call_llm() | Phase 2 | Supports anthropic/groq/ollama; easy to switch backends |
| Session cookies only | Server-side SQLite sessions | Now | Persists across browser close, scales with data |

## Open Questions

1. **Session TTL duration?**
   - What we know: Default is 24h for browser cookies
   - What's unclear: Should we extend to 30 days for persistent history, or keep 24h?
   - Recommendation: Use 30 days (many team members may search once/week). Add admin setting to control.

2. **Fuzzy match threshold for skill gap?**
   - What we know: rapidfuzz already in requirements
   - What's unclear: What WRatio threshold captures "Azure" vs "Azure DevOps" vs false positives?
   - Recommendation: Start with 75 threshold, add A/B test in skill gap results ("What percentage matched?").

3. **Team composition team size default?**
   - What we know: User can specify, typical team is 3-5 people
   - What's unclear: Should default be 3, 4, or 5? Should there be preset buttons (Squad, Team, Department)?
   - Recommendation: Default to 3 (smallest useful team), allow 1-10 range.

4. **Profile diff: Show all historical versions or just last 2?**
   - What we know: profile_history table stores all versions
   - What's unclear: Should admin see full history or just "what changed since last index"?
   - Recommendation: Default to "last change only", add filter to show full history by date range.

5. **Export: Include internal match reasoning or hide from users?**
   - What we know: match_reasoning field is AI-generated explanation
   - What's unclear: Is this proprietary logic or useful context for exported report?
   - Recommendation: Include in export (it's useful context), but warn admin in code comment about sharing.

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `/Users/8jorgee/Desktop/cvsrag/app/main.py` (FEAT-11 verified), `/app/search/engine.py` (LLM integration pattern), `/app/db.py` (SQLite + FAISS architecture)
- Requirements: `/requirements.txt` (all dependencies confirmed)
- Existing patterns: Profile model, SearchQuery, _call_llm(), parse_json_response()

### Secondary (MEDIUM confidence)
- FastAPI docs (streaming responses, FileResponse, Form handling)
- pandas/openpyxl documentation (export patterns)
- SQLite transaction semantics (session + history tables)

## Metadata

**Confidence breakdown:**
- Export (FEAT-03): HIGH — pandas/openpyxl documented, pattern is standard
- Search history (FEAT-04): HIGH — SQLite session table is straightforward
- Skill gap (FEAT-05): MEDIUM — LLM integration pattern proven, but prompt design needs testing
- Team composition (FEAT-06): MEDIUM — Similar to skill gap, JSON parsing critical
- Profile diff (FEAT-08): HIGH — Metadata diffing is deterministic
- FEAT-11 verification: HIGH — Code exists and is complete

**Research date:** 2026-04-10
**Valid until:** 2026-05-10 (30 days; FastAPI/pandas are stable)
