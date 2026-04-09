# Roadmap

## Milestone 1: Production Hardening + Feature Expansion

### Phase 1: Security & Data Integrity

**Goal:** Eliminate all security vulnerabilities and data integrity bugs so the system is safe to run in production.

**Requirements:** SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, DATA-01, DATA-02, DATA-03, DATA-04, DATA-05

**Plans:** 2 plans in 2 waves

Plans:
- [x] 01-PLAN.md — Security hardening (CSRF, API key validation, rate limiting, input validation, MIME type checking) — **COMPLETE** (2026-04-09)
- [x] 02-PLAN.md — Data integrity fixes (name normalization, atomic upsert, stable IDs, CSV detection, date validation) — **COMPLETE** (2026-04-09)

**Success Criteria:**
1. Admin forms include CSRF tokens and server rejects requests without valid tokens
2. Application refuses to start without `ANTHROPIC_API_KEY` set
3. Profile availability data correctly matches profiles with accented/mixed-case names
4. Re-indexing a renamed CV updates the existing profile instead of creating a duplicate
5. Changing only the availability CSV triggers re-ingestion of affected profiles without `--force`

**UI hint**: no

---

### Phase 2: Robustness, Performance & Core Features

**Goal:** Harden the system against failures, improve performance, and ship the first set of new features (fuzzy matching, parallel ingestion, pagination, OR filters, embedding cache, structured logging).

**Requirements:** ROB-01, ROB-02, ROB-03, ROB-04, ROB-05, SEARCH-01, SEARCH-02, FEAT-01, FEAT-02, FEAT-07, FEAT-10

**Success Criteria:**
1. Claude JSON parsing never crashes on malformed responses (graceful fallback logged)
2. Re-index runs as background task; admin sees live per-CV progress without page refresh
3. Search results paginate correctly (page 2 returns different profiles than page 1 for large result sets)
4. Query `skills_any=["Python","R"]` returns profiles with Python OR R (not requiring both)
5. Repeated identical search queries skip embedding generation (cache hit logged)
6. All log output is structured JSON in production mode

**UI hint**: yes

---

### Phase 3: Advanced Features

**Goal:** Ship the high-value features that differentiate this tool: result export, search history, skill gap analysis, team composition, profile diff, and async reindex UI.

**Requirements:** FEAT-03, FEAT-04, FEAT-05, FEAT-06, FEAT-08, FEAT-11

**Success Criteria:**
1. User can download current search results as CSV or Excel from the search page
2. Last 20 searches appear below the search bar; clicking one re-runs the search
3. Skill gap analysis page shows which team members cover each required skill and what's missing
4. Team composition page returns an AI-suggested team with reasoning for a given project description
5. Admin can view what changed in a profile after re-indexing (diff between old and new structured fields)
6. Admin reindex shows a live streaming log with per-CV status (processing / done / error)

**UI hint**: yes

---

### Phase 4: Test Suite

**Goal:** Achieve 80%+ test coverage with unit and integration tests so future changes can be made with confidence.

**Requirements:** FEAT-09

**Success Criteria:**
1. `pytest` exits 0 with all tests passing
2. Coverage report shows ≥80% across `app/` modules
3. Unit tests cover: filter logic (all filter types), scoring (blended score calculation), embedding normalization
4. Integration test covers: full search pipeline from query string to ranked results
5. Tests run without network access (all external dependencies mocked)

**UI hint**: no

---

## Phase Index

| # | Phase | Goal | Requirements | Status |
|---|-------|------|--------------|--------|
| 1 | Security & Data Integrity | Eliminate security vulnerabilities and data integrity bugs | SEC-01–05, DATA-01–05 | COMPLETE ✓ (Plan 01 & 02) |
| 2 | Robustness, Performance & Core Features | Harden system, improve performance, ship first features | ROB-01–05, SEARCH-01–02, FEAT-01,02,07,10 | Pending |
| 3 | Advanced Features | Export, search history, gap analysis, team builder, diff, SSE | FEAT-03–06, FEAT-08, FEAT-11 | Pending |
| 4 | Test Suite | 80%+ coverage with pytest | FEAT-09 | Pending |
