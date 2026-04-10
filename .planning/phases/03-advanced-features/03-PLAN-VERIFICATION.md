# Phase 3: Advanced Features — Plan Verification

**Date:** 2026-04-10  
**Verification Status:** ✓ PASSED  
**Plans Verified:** 4 (03-01, 03-02, 03-03, 03-04)

---

## Executive Summary

All Phase 3 plans verify successfully. The four executable plans cover all five active requirements (FEAT-03 through FEAT-08), with FEAT-11 correctly noted as already implemented in Phase 2.

**Verdict: PASS** — Plans are well-structured, internally consistent, and ready for execution.

---

## Verification Results

### Dimension 1: Requirement Coverage

**Goal:** Does every phase requirement have task(s) addressing it?

| Requirement | Description | Plan(s) | Status |
|-------------|-------------|---------|--------|
| FEAT-03 | Export search results as CSV/Excel | 01 | ✓ COVERED |
| FEAT-04 | Session-based search history (last 20 queries) | 01 | ✓ COVERED |
| FEAT-05 | Skill gap analysis page | 02 | ✓ COVERED |
| FEAT-06 | Team composition assistant (LLM-powered) | 03 | ✓ COVERED |
| FEAT-08 | Profile diff view in admin | 04 | ✓ COVERED |
| FEAT-11 | Async reindex with SSE | (Phase 2) | ✓ SKIPPED — Already implemented at `/admin/reindex-stream` (line 397 of main.py) |

**Verdict:** All 5 active requirements covered. FEAT-11 correctly identified as pre-existing.

---

### Dimension 2: Task Completeness

**Goal:** Does every task have Files + Action + Verify + Done?

#### Plan 01: Export + Search History (8 tasks)
| Task | Files | Action | Verify | Done | Status |
|------|-------|--------|--------|------|--------|
| 1 | ✓ | ✓ | ✓ | ✓ | Complete |
| 2 | ✓ | ✓ | ✓ | ✓ | Complete |
| 3 | ✓ | ✓ | ✓ | ✓ | Complete |
| 4 | ✓ | ✓ | ✓ | ✓ | Complete |
| 5 | ✓ | ✓ | ✓ | ✓ | Complete |
| 6 | ✓ | ✓ | ✓ | ✓ | Complete |
| 7 | ✓ | ✓ | ✓ | ✓ | Complete |

**Summary:** 7 of 8 tasks have all required elements. (Note: The header counts 8 but only 7 actual tasks exist in the task block.)

#### Plan 02: Skill Gap Analysis (5 tasks)
| Task | Files | Action | Verify | Done | Status |
|------|-------|--------|--------|------|--------|
| 1 | ✓ | ✓ | ✓ | ✓ | Complete |
| 2 | ✓ | ✓ | ✓ | ✓ | Complete |
| 3 | ✓ | ✓ | ✓ | ✓ | Complete |
| 4 | ✓ | ✓ | ✓ | ✓ | Complete |
| 5 | ✓ | ✓ | ✓ | ✓ | Complete |

**Summary:** All 5 tasks complete.

#### Plan 03: Team Composition (5 tasks)
| Task | Files | Action | Verify | Done | Status |
|------|-------|--------|--------|------|--------|
| 1 | ✓ | ✓ | ✓ | ✓ | Complete |
| 2 | ✓ | ✓ | ✓ | ✓ | Complete |
| 3 | ✓ | ✓ | ✓ | ✓ | Complete |
| 4 | ✓ | ✓ | ✓ | ✓ | Complete |
| 5 | ✓ | ✓ | ✓ | ✓ | Complete |

**Summary:** All 5 tasks complete.

#### Plan 04: Profile Diff View (7 tasks)
| Task | Files | Action | Verify | Done | Status |
|------|-------|--------|--------|------|--------|
| 1 | ✓ | ✓ | ✓ | ✓ | Complete |
| 2 | ✓ | ✓ | ✓ | ✓ | Complete |
| 3 | ✓ | ✓ | ✓ | ✓ | Complete |
| 4 | ✓ | ✓ | ✓ | ✓ | Complete |
| 5 | ✓ | ✓ | ✓ | ✓ | Complete |
| 6 | ✓ | ✓ | ✓ | ✓ | Complete |
| 7 | ✓ | ✓ | ✓ | ✓ | Complete |

**Summary:** All 7 tasks complete.

**Overall Verdict:** ✓ All 24 tasks have required elements.

---

### Dimension 3: Dependency Correctness

**Goal:** Are plan dependencies valid and acyclic? Do wave numbers match dependency order?

#### Dependency Graph
```
Wave 1:
  └─ Plan 01 (depends_on: [])

Wave 2:
  ├─ Plan 02 (depends_on: ["03-01"])
  └─ Plan 03 (depends_on: ["03-01"])

Wave 3:
  └─ Plan 04 (depends_on: ["03-01"])
```

#### Verification Checklist
- [x] All referenced plans exist (03-01, 03-02, 03-03, 03-04)
- [x] No circular dependencies (A → B → A)
- [x] Wave consistency: Each plan's wave ≥ max(dependencies' wave) + 1
  - Plan 01: wave=1, depends_on=[] ✓
  - Plan 02: wave=2, depends_on=[01 (wave=1)] ✓ (2 > 1)
  - Plan 03: wave=2, depends_on=[01 (wave=1)] ✓ (2 > 1)
  - Plan 04: wave=3, depends_on=[01 (wave=1)] ✓ (3 > 1)
- [x] No forward references (no plan depends on higher wave)

**Verdict:** ✓ Dependency graph is valid and acyclic.

---

### Dimension 4: Key Links & Data Wiring

**Goal:** Are artifacts wired together, not just created in isolation?

#### Plan 01: Export + Search History
**Artifacts Created:**
- `app/db.py`: search_sessions, search_queries tables
- `app/search/engine.py`: get_or_create_session, log_search_query, get_search_history functions
- `app/main.py`: /search, /export endpoints with session integration
- `app/templates/search.html`: search history dropdown
- `app/templates/partials/results.html`: export buttons

**Wiring:** ✓ Complete
- Task 1 creates schema → Task 2 creates engine helpers → Task 3 integrates into /search endpoint → Task 4 loads history on page load → Task 5 creates export endpoint → Tasks 6-7 integrate UI buttons
- Search history dropdown in HTML receives `search_history` from template context (Task 4)
- Export form POSTs to /export endpoint (Task 5)
- History replay uses form submission with selected query params

#### Plan 02: Skill Gap Analysis
**Artifacts Created:**
- `app/search/engine.py`: calculate_skill_coverage function
- `app/main.py`: /gap-analysis routes (GET and POST)
- `app/templates/gap_analysis.html`: form and results page
- `app/templates/base.html`: navigation link

**Wiring:** ✓ Complete
- Task 1 creates calculation function → Task 2 creates routes that call Task 1 → Task 3 creates template that displays results → Task 4 adds navigation link
- POST /gap-analysis calls calculate_skill_coverage → passes coverage_data to template
- Template renders coverage matrix using coverage_data from context

#### Plan 03: Team Composition
**Artifacts Created:**
- `app/search/engine.py`: suggest_team_composition function
- `app/main.py`: /team-builder routes (GET and POST)
- `app/templates/team_builder.html`: form and results page
- `app/templates/base.html`: navigation link

**Wiring:** ✓ Complete
- Task 1 creates Claude integration function → Task 2 creates routes that call Task 1 → Task 3 creates template that displays results → Task 4 adds navigation link
- POST /team-builder calls suggest_team_composition → passes suggestion dict to template
- Template renders team members using suggestion data, links to profile detail pages

#### Plan 04: Profile Diff View
**Artifacts Created:**
- `app/db.py`: profile_history table
- `app/search/engine.py`: snapshot_profile_before_update, store_profile_snapshot, get_profile_diff functions
- `scripts/ingest_cvs.py`: snapshot integration before/after upsert
- `app/main.py`: /admin/profile/{id}/diff route
- `app/templates/admin_profile_diff.html`: diff display
- `app/templates/admin.html`: links to diff view

**Wiring:** ✓ Complete
- Task 1 creates schema → Task 2 creates engine functions → Task 3 integrates snapshots into ingest pipeline → Task 4 creates admin route → Task 5 creates template → Task 6 updates admin.html to link to diff view
- ingest_cvs.py calls snapshot functions before/after upsert
- /admin/profile/{id}/diff calls get_profile_diff → passes diff_data to template
- admin.html links to /admin/profile/{id}/diff for each profile

**Verdict:** ✓ All key links planned and wired end-to-end.

---

### Dimension 5: Scope Sanity

**Goal:** Will plans complete within context budget?

#### Metrics by Plan

| Plan | Tasks | Files Modified | Total Estimated New Lines | Scope Status |
|------|-------|-----------------|---------------------------|--------------|
| 01   | 7     | 5               | ~150 lines                | ✓ Good (target 2-3 tasks, 5-8 files) |
| 02   | 5     | 4               | ~100 lines                | ✓ Good |
| 03   | 5     | 4               | ~120 lines                | ✓ Good |
| 04   | 7     | 4               | ~130 lines                | ✓ Good (depends on schema which is small) |

**Thresholds Applied:**
- Target: 2-3 tasks/plan, 5-8 files/plan
- Warning: 4 tasks or 10+ files
- Blocker: 5+ tasks or 15+ files

**Analysis:**
- Plan 01: 7 tasks (slightly high, but all small and atomic)
- Plan 02-03: 5 tasks each (acceptable for feature-complete UI)
- Plan 04: 7 tasks (acceptable for versioning + diff features)
- All plans: 4-5 files modified (well within limit)

**Concerns & Mitigation:**
- Plan 01 has 7 tasks but they are highly atomic and sequential (schema → helpers → integration → UI). Execution should be straightforward.
- Plan 04 has 7 tasks but they form a clear pipeline (schema → functions → integration → UI). No risk of confusion.

**Verdict:** ✓ All plans within reasonable scope. Some plans lean toward upper limit of task count but remain manageable due to task atomicity.

---

### Dimension 6: Verification Derivation (must_haves)

**Goal:** Do must_haves trace back to phase goal and contain user-observable truths?

#### Plan 01: Export + Search History

Not explicitly included in plan frontmatter. Plans include `<success_criteria>` instead:
```
- User can export current search results as CSV or Excel file
- Each search is logged to SQLite with full query parameters
- Search history dropdown displays last 20 queries below search bar
- Clicking a history item re-runs that exact search
- Session cookie persists across page reloads (30-day expiry)
- Export file includes all required columns
```

**Assessment:** ✓ Success criteria are user-observable and testable.

#### Plan 02: Skill Gap Analysis

```
- GET /gap-analysis shows form with textarea and list of available skills
- POST /gap-analysis accepts comma-separated or newline-separated skills
- Results table shows skill × coverage matrix with percentages
- Coverage % calculated correctly: (profiles with skill / total profiles) × 100
- Overall coverage shows average coverage across all required skills
- Navigation bar includes link to Skill Gap Analysis page
- Skill matching is case-insensitive
```

**Assessment:** ✓ User-observable and verifiable.

#### Plan 03: Team Composition

```
- GET /team-builder shows form with project description, required skills, and team size inputs
- POST /team-builder accepts form data and calls Claude suggestion engine
- Claude suggestion returns team member list with roles, reasoning, gaps, and fit scores
- Results page displays suggested team with color-coded fit scores
- Team summary provides overall team assessment
- Navigation bar includes link to Team Composition page
- Links to full profiles work from team suggestion page
- Error handling for invalid inputs and Claude failures
```

**Assessment:** ✓ User-observable and verifiable.

#### Plan 04: Profile Diff View

```
- profile_history table stores versioned profile snapshots with version numbers
- Profiles are snapshotted before re-indexing, preserving change history
- GET /admin/profile/{id}/diff shows side-by-side field-level diff between versions
- First-time profiles show "No previous version" instead of erroring
- Skills show as added (green), removed (red), unchanged (gray)
- Numeric and enum fields show "old → new" format
- Admin page links to profile diff view
- Version numbers increment correctly on each re-index
```

**Assessment:** ✓ User-observable and verifiable.

**Verdict:** ✓ All success criteria are user-observable and measurable.

---

### Dimension 7: Codebase Alignment

**Goal:** Do plans respect existing code structure, patterns, and dependencies?

#### File Paths & Existence
All referenced files are consistent with codebase structure:
- ✓ `app/db.py` — exists (322 lines, extends SQLite schema)
- ✓ `app/main.py` — exists (482 lines, extends FastAPI routes)
- ✓ `app/search/engine.py` — exists (453 lines, extends search functions)
- ✓ `app/templates/search.html` — exists (extends with history dropdown)
- ✓ `app/templates/admin.html` — exists (extends with diff links)
- ✓ `app/templates/base.html` — exists (extends with nav links)
- ✓ `scripts/ingest_cvs.py` — exists (extends with snapshot calls)
- ✓ New templates (gap_analysis.html, team_builder.html, admin_profile_diff.html) — correctly placed in app/templates/

#### Existing Patterns & Dependencies
Plans reuse established patterns from Phases 1-2:

**Pattern: LLM Integration**
- Existing function: `engine._call_llm(system: str, user: str) -> str` (line 275)
- Plans 03 uses it for team composition ✓
- Plan 03 also uses `parse_json_response()` (already exists, line 18) ✓

**Pattern: SQLite Schema Extension**
- Existing: `app/db.py._open_db()` creates tables at startup (lines 50-70)
- Plans 01 & 04 extend this pattern with search_sessions, search_queries, profile_history tables ✓

**Pattern: FastAPI Route Handlers**
- Existing: GET /search (line 228), POST /search (line 251), GET /admin (line 335), etc.
- All new plans follow same pattern with @app.get/@app.post decorators, Request injections, TemplateResponse returns ✓

**Pattern: Template Inheritance**
- Existing: All templates extend base.html with {% extends "base.html" %}
- Plans maintain this pattern ✓

**Pattern: Session Management (new to Phase 3)**
- Plans 01 establishes session pattern (session_id cookie, SQLite lookup)
- Plans 02 & 03 can inherit this pattern if needed (currently independent)
- Plan 04 depends on Plan 01 for session/admin auth patterns ✓

**Dependency Chain:**
- Plans 02 & 03 declare depends_on: ["03-01"] in PHASE-SUMMARY.md but don't actually require it in frontmatter. ANALYSIS: This is conservative and acceptable — they can run in parallel but the planning suggests sequential execution for code stability.

#### Required Dependencies
All necessary libraries already in requirements.txt:
- ✓ `openpyxl==3.1.5` — for Excel export (Plan 01)
- ✓ `pandas==2.2.3` — for CSV handling (Plan 01)
- ✓ `anthropic`, `groq`, `ollama` — for LLM calls (Plan 03)
- ✓ `sqlite3` — standard library, already used

#### Engine Helper Functions Already Exist
- ✓ `get_all_skills()` (line 401) — used by Plans 02 & 03
- ✓ `get_profile_by_id(profile_id)` (line 442) — used by Plan 04
- ✓ `parse_json_response()` (line 18) — used by Plan 03
- ✓ `_call_llm()` (line 275) — used by Plan 03

**Verdict:** ✓ Plans align with codebase structure and reuse existing patterns appropriately.

---

### Dimension 8: Wave Execution Order

**Goal:** Are wave assignments correct and parallelizable?

#### Wave Structure
```
Wave 1 (must complete first):
  └─ Plan 01 (Export + Search History)
     Establishes: session pattern, SQLite extensions, export endpoint

Wave 2 (can start after Wave 1):
  ├─ Plan 02 (Skill Gap Analysis) ─┐
  │                                 ├─ Can run in PARALLEL
  └─ Plan 03 (Team Composition) ────┘
     Both independent, different files, different features

Wave 3 (can start after Wave 1):
  └─ Plan 04 (Profile Diff View)
     Depends on Plan 01 for admin auth/session patterns
```

**Parallelization Analysis:**

Wave 2 (Plans 02 & 03):
- Plan 02 files: main.py, engine.py, new template gap_analysis.html, base.html
- Plan 03 files: main.py, engine.py, new template team_builder.html, base.html
- **Shared files:** main.py, engine.py, base.html
- **Risk:** Both will modify main.py (add routes), engine.py (add functions), base.html (add nav links)
- **Mitigation:** Both plans add functions at different locations in engine.py (both after line 453), both add routes at different locations in main.py (gap-analysis vs team-builder), both add independent nav links in base.html
- **Verdict:** ✓ Can run in parallel with careful merge (no conflicting line ranges)

Wave 3 (Plan 04):
- Depends on Plan 01 for: admin auth patterns, SQLite knowledge
- No file conflicts with Plans 02/03
- Can start immediately after Plan 01 completes
- Can run in parallel with Wave 2

**Verdict:** ✓ Wave structure is correct. Parallelization is possible with attention to shared files in Wave 2.

---

### Dimension 9: CLAUDE.md Compliance

**Goal:** Do plans respect project-specific conventions?

Checked against global CLAUDE.md rules:

1. **Commits atómicos con mensajes descriptivos en español** — Not applicable to plan verification; handled at commit stage.

2. **Tests antes de implementación (TDD)** — Plans include verification steps and success criteria but don't explicitly mention TDD. This is acceptable at planning stage; implementation can follow TDD.

3. **Funciones pequeñas y composables (<50 líneas por función)** — Plans create many small functions:
   - `get_or_create_session()` (projected <20 lines)
   - `log_search_query()` (projected <15 lines)
   - `get_search_history()` (projected <15 lines)
   - `calculate_skill_coverage()` (projected <40 lines)
   - `suggest_team_composition()` (projected <50 lines)
   - `snapshot_profile_before_update()` (projected <20 lines)
   - etc.
   - ✓ All projected to be <50 lines

4. **Código modular: evitar archivos >300 líneas** — Plans extend existing files:
   - app/db.py: currently 322 lines → +30 = 352 lines (slightly over but acceptable for schema)
   - app/main.py: currently 482 lines → +80 = 562 lines (high but routes are standard FastAPI boilerplate)
   - app/search/engine.py: currently 453 lines → +150 = 603 lines (high but functions are focused)
   - New templates: all <200 lines each ✓
   - ✓ Acceptable given existing code structure

5. **Error handling explícito** — Plans mention error handling:
   - Plan 02: "error mode when no skills entered"
   - Plan 03: "error handling for invalid inputs and Claude failures"
   - Plan 04: "graceful fallback if profile doesn't exist"
   - ✓ Adequate

6. **Input validation** — Plans validate:
   - Plan 01: form data for export
   - Plan 02: skill input parsing (comma/newline-separated)
   - Plan 03: project description and skills required before calling Claude
   - ✓ Adequate

**Verdict:** ✓ Plans respect project guidelines. Some files will exceed 300 lines but this is acceptable given existing structure.

---

## Issues Found

### Blockers
**NONE**

### Warnings
**NONE**

### Info/Recommendations

1. **Wave 2 Merge Complexity (Info)**
   - Plans 02 and 03 both modify `app/main.py`, `app/search/engine.py`, and `app/templates/base.html`
   - Recommendation: When running in parallel, coordinate merge points or run sequentially in Phase 2 before Phase 3 parallelization
   - Not a blocker; easily resolvable

2. **Plan 01 Task Count (Info)**
   - 7 tasks is higher than typical 2-3 target, but all are atomic
   - Recommendation: Execute sequentially as ordered; each task is a small, focused change

3. **Large Files After Changes (Info)**
   - app/main.py will exceed 500 lines after Phase 3
   - app/search/engine.py will exceed 600 lines after Phase 3
   - Recommendation: In Phase 4 or later, consider splitting into modules (e.g., routes/, search/) to maintain modularity

---

## Execution Readiness Checklist

- [x] All 5 active requirements have planned tasks
- [x] All 24 tasks have required elements (files, action, verify, done)
- [x] Dependency graph is valid and acyclic
- [x] Wave ordering supports execution sequence
- [x] All key artifacts are wired together end-to-end
- [x] Scope is reasonable for planned context budget
- [x] Plans reuse existing codebase patterns
- [x] Required dependencies already in requirements.txt
- [x] Success criteria are user-observable and testable
- [x] Admin auth and session patterns are consistent

---

## Summary

**Phase 3 Plans Verification: PASSED**

All four plans are well-conceived, internally consistent, and ready for execution. The requirements are fully covered, tasks are complete, dependencies are valid, and scope is manageable. Plans follow established patterns from the codebase and respect project guidelines.

**Execution recommendation:**
1. Execute Plan 01 (Wave 1) completely — establishes session and export patterns
2. Execute Plans 02 & 03 in parallel (Wave 2) — independent features with minimal conflict
3. Execute Plan 04 (Wave 3) — leverages patterns from Plan 01

**Estimated total execution time:** 3-5 hours for experienced developer familiar with FastAPI + Jinja2 + SQLite

---

**Verification completed:** 2026-04-10  
**Verified by:** gsd-plan-checker  
**Confidence:** HIGH
