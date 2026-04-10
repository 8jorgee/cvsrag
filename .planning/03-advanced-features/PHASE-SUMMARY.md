# Phase 3: Advanced Features — Planning Complete

**Date:** 2026-04-10
**Status:** 4 executable plans created, ready for implementation
**Wave structure:** 3 waves, max 2 plans per wave

## Overview

Phase 3 ships six differentiator features to cvsrag:

| Feature | Requirement | Plan | Wave |
|---------|-------------|------|------|
| Export search results (CSV/Excel) | FEAT-03 | 01 | 1 |
| Session-based search history | FEAT-04 | 01 | 1 |
| Skill gap analysis page | FEAT-05 | 02 | 2 |
| Team composition assistant (Claude) | FEAT-06 | 03 | 2 |
| Profile diff view in admin | FEAT-08 | 04 | 3 |
| Async reindex with SSE | FEAT-11 | (Already implemented in Phase 2) | — |

## Plans at a Glance

### Plan 01: Export + Search History (Wave 1)
**Files touched:** 5 (db.py, main.py, search/engine.py, 2 templates)
**Tasks:** 7 atomic tasks
**Dependencies:** None (can start immediately)
**Key work:**
- New SQLite tables: search_sessions, search_queries
- Session management with secure cookies
- Export endpoint supporting CSV and Excel (openpyxl)
- Search history dropdown below search bar
- History replay by clicking previous search

**Deliverables:**
- Users can export results as CSV or Excel
- Last 20 searches persist in session (30-day expiry)
- One-click re-run of previous searches

---

### Plan 02: Skill Gap Analysis (Wave 2)
**Files touched:** 4 (main.py, search/engine.py, new template, base.html)
**Tasks:** 5 atomic tasks
**Dependencies:** Depends on 01 (session cookie pattern), but can start in parallel with 01
**Key work:**
- Coverage matrix calculation: skill × profile
- Form to accept comma-separated required skills
- Results table with coverage %, profile count, gaps
- Navigation link added

**Deliverables:**
- Skill gap analysis page shows which team members cover each skill
- Overall coverage percentage calculated
- Fully responsive table format

---

### Plan 03: Team Composition Assistant (Wave 2)
**Files touched:** 4 (main.py, search/engine.py, new template, base.html)
**Tasks:** 5 atomic tasks
**Dependencies:** Depends on 01 (for pattern reference), can parallel with 02
**Key work:**
- Claude-powered team suggestion using _call_llm()
- Form: project description + required skills + team size
- Results: suggested team with roles, reasoning, fit scores (0-100), gaps
- Color-coded fit scoring (green >85, yellow 65-85, orange <65)
- Navigation link added

**Deliverables:**
- Users describe project, AI suggests optimal team from available profiles
- Each suggestion includes role, reasoning, gaps, fit score
- Links to full profiles from team view

---

### Plan 04: Profile Diff View (Wave 3)
**Files touched:** 4 (db.py, ingest_cvs.py, main.py, new template)
**Tasks:** 7 atomic tasks
**Dependencies:** Depends on 01 (establishes session/admin patterns), can start after 01 is done
**Key work:**
- New SQLite table: profile_history (versioned snapshots)
- Snapshot before each re-index to capture changes
- Diff calculation: added/removed/unchanged skills, changed fields
- Admin route /admin/profile/{id}/diff showing side-by-side comparison
- Integration into re-indexing process (ingest_cvs.py)
- Admin links to diff view

**Deliverables:**
- Admins can view what changed in a profile after re-indexing
- Field-level diff: skills added (green), removed (red), text fields show changes
- Version history tracked (v1, v2, v3...)
- First-time profiles show "No previous version"

---

## Wave Structure & Execution Order

```
Wave 1 (Start immediately, sequential):
├─ Plan 01: Export + Search History
│  (must complete before Wave 2, as establishes session pattern)
│
Wave 2 (Can start after Wave 1 baseline, parallel execution):
├─ Plan 02: Skill Gap Analysis ──┐
│                                 ├─ (independent, can run in parallel)
├─ Plan 03: Team Composition ────┘
│
Wave 3 (Can start after Wave 1, uses its patterns):
└─ Plan 04: Profile Diff View
```

**Parallelism notes:**
- Plans 02 and 03 are entirely independent (no shared files)
- Plan 04 depends on Plan 01 for session/admin patterns but doesn't block on them
- Suggested execution: Start Plan 01, when done proceed with (02 + 03) in parallel, then Plan 04

---

## Technical Decisions

### Database Schema
- **search_sessions:** session_id (UUID), created_at, last_accessed
- **search_queries:** session_id FK, query_text, filters_json, created_at, results_count
- **profile_history:** profile_id FK, version, metadata_json, created_at, source_file

All tables include indexes for fast retrieval (session_id, profile_id, created_at).

### Session Management
- Session ID stored in httpOnly, Secure, SameSite=Lax cookie
- 30-day expiry (2,592,000 seconds)
- Server-side in SQLite (not cookie-based) to avoid size limits

### Export Format
- CSV: UTF-8 encoded, standard columns (Name, Grade, Location, Skills, Certs, Availability %, Date, Score, Reasoning)
- Excel: Single "Search Results" sheet with same structure, using openpyxl

### LLM Integration (Plans 03)
- Uses existing `_call_llm()` function in engine.py
- Claude prompt: talent matching expert role, request JSON with team suggestions
- JSON parsing: robust with fallback to markdown-wrapped JSON extraction
- Error handling: graceful fallback, logs context

### Profile Versioning (Plan 04)
- Snapshot captured BEFORE upsert during re-indexing
- Diff calculated field-by-field (lists, text, numeric)
- Skills: added (green), removed (red), unchanged (gray)
- Text fields: show "Updated" if changed, preview in side-by-side view
- Version numbers: 1, 2, 3... increment on each change

---

## Implementation Checklist

- [ ] **Plan 01 tasks 1-7:** Database, session management, export endpoint, UI
- [ ] **Plan 02 tasks 1-5:** Skill coverage calculation, form, results template, navigation
- [ ] **Plan 03 tasks 1-5:** Claude integration, form, team suggestion template, navigation
- [ ] **Plan 04 tasks 1-7:** Profile history schema, snapshot integration, diff route, admin UI

---

## Success Criteria (Phase 3 Complete)

When all 4 plans are executed:

1. ✓ Users can export search results as CSV or Excel
2. ✓ Last 20 searches visible below search bar; clicking re-runs search
3. ✓ Skill gap analysis shows which team covers each required skill and what's missing
4. ✓ Team composition page suggests optimal team for a project using Claude
5. ✓ Admin can view field-level changes in profiles after re-indexing
6. ✓ All features use existing patterns (HTMX, FastAPI, structlog, Claude via _call_llm)
7. ✓ No new external dependencies (openpyxl/pandas already in requirements)
8. ✓ Fully integrated navigation linking new features from main page

---

## Known Unknowns & Future Refinements

### Plan 01 (Export + Search History)
- **History pagination:** If user makes >20 searches, older searches are deleted (not paginated). This is intentional to keep cookie simple.
- **Export performance:** With >500 profiles, exporting all results as Excel could take a few seconds. Consider async zip job in future.

### Plan 02 (Skill Gap Analysis)
- **Fuzzy matching:** Current implementation uses exact string match (case-insensitive). Could add fuzzy matching in future (e.g., "Python 3" matching "Python").
- **Proficiency levels:** Gap analysis currently just says "has skill" vs "doesn't have". Could extend to proficiency levels (beginner, intermediate, expert) in future.

### Plan 03 (Team Composition)
- **Claude latency:** Claude API calls are synchronous (2-5 second wait). Consider async in future or add loading spinner.
- **Profile context size:** For >100 profiles, the prompt becomes very large (~200KB). May need profile summarization or filtering before sending to Claude.

### Plan 04 (Profile Diff)
- **Large skill lists:** Diff on profiles with 50+ skills is readable but could be condensed (show counts instead of full list). Current implementation is fine for typical 10-30 skill profiles.
- **Retention policy:** Profile history grows indefinitely. Consider adding cleanup job (delete versions older than 1 year) in future.

---

## Files & Line Counts (Estimated)

| File | Estimated Lines | Purpose |
|------|-----------------|---------|
| db.py | +30 | search_sessions, search_queries, profile_history tables |
| main.py | +80 | /export, /gap-analysis, /team-builder, /admin/profile/*/diff routes |
| search/engine.py | +150 | Session helpers, skill coverage calc, team composition, profile diff funcs |
| templates/search.html | +20 | Search history dropdown |
| templates/partials/results.html | +15 | Export button |
| templates/gap_analysis.html | +100 | New template |
| templates/team_builder.html | +120 | New template |
| templates/admin_profile_diff.html | +100 | New template |
| templates/base.html | +5 | Navigation links (2 new) |
| scripts/ingest_cvs.py | +30 | Snapshot integration |

**Total new code:** ~650 lines across 10 files

---

## Commit Strategy

Each plan will be executed as a separate commit:
```
feat(03): export + search history — POST /export, session tracking
feat(03): skill gap analysis — /gap-analysis page with coverage matrix
feat(03): team composition assistant — /team-builder with Claude integration
feat(03): profile diff view — admin/profile/*/diff with version history
```

---

## Next Steps

1. **Execute Plan 01** (Export + Search History) — establish session pattern
2. **Execute Plans 02 & 03 in parallel** (Skill Gap, Team Composition) — independent features
3. **Execute Plan 04** (Profile Diff) — leverages patterns from 01
4. **Verify all success criteria** across all 4 plans
5. **Manual UAT** — test end-to-end workflows as a user
6. **Move to Phase 4** (Test Suite) once complete

---

**End of Phase 3 Planning**
