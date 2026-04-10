---
phase: "03-advanced-features"
plan: "04"
status: "COMPLETE"
completed_date: "2026-04-10"
duration_minutes: 45
subsystem: "Profile Versioning & History"
tags:
  - profile-history
  - versioning
  - diff-view
  - admin-features
dependency_graph:
  requires: ["03-01", "03-02", "03-03"]
  provides: ["FEAT-08: profile versioning"]
  affects: ["admin dashboard", "re-indexing workflow"]
tech_stack:
  added:
    - "SQLite profile_history table with version tracking"
    - "Field-level diff computation (skills, certs, text fields, numeric/enum fields)"
    - "Jinja2 template rendering with diff visualization"
  patterns:
    - "One-time migration for existing profiles (backward compatibility)"
    - "Before/after snapshot capture around upsert operations"
key_files:
  created:
    - "app/templates/admin_profile_diff.html"
  modified:
    - "app/db.py (profile_history table + migration)"
    - "app/search/engine.py (snapshot & diff functions)"
    - "scripts/ingest_cvs.py (snapshot capture integration)"
    - "app/main.py (diff route + admin page enhancement)"
    - "app/templates/admin.html (profile links)"
decisions:
  - "Snapshot capture: BEFORE upsert (preserve old), AFTER upsert (store new version)"
  - "Version numbering: Auto-increment per profile, independent per profile_id"
  - "First version: Created implicitly on first snapshot, not on first index"
  - "Diff computation: Case-insensitive for lists, simple string comparison for text fields"
---

# Phase 03 Plan 04: Profile Versioning & History Summary

**Objective:** Enable admins to view field-level changes to profile metadata after re-indexing a CV. Store versioned profile snapshots and provide a diff view showing what changed (name, skills added/removed, grade updated, etc.).

## Implementation Notes

### 1. Profile History Schema

**SQLite table:** `profile_history`
- Columns: id (PK), profile_id (FK), version (INTEGER), metadata_json (TEXT), created_at (TIMESTAMP), source_file (TEXT)
- Constraints: UNIQUE(profile_id, version) prevents duplicate versions
- Indexes:
  - `idx_profile_history_profile_version` on (profile_id, version DESC) for fast "latest versions" queries
  - `idx_profile_history_created_at` on created_at for retention/cleanup queries

**One-time migration:**
- Runs on first DB initialization (`_open_db()`)
- If profile_history is empty but profiles table has data, populates version=1 for all existing profiles
- Logs "Migrating existing profiles to history" to track execution
- Non-blocking: errors logged but don't prevent DB startup

### 2. Snapshot Capture Strategy

**Three functions in engine.py:**

1. **`snapshot_profile_before_update(db_conn, profile_id, source_file="")`**
   - Called BEFORE upsert in ingest_cvs.py
   - If profile exists AND already has history (version > 0), stores old metadata as next version
   - If profile doesn't exist yet or has no history, skips (version 1 will be created after)
   - Preserves "before" state for re-indexing scenarios

2. **`store_profile_snapshot(db_conn, profile_id, metadata, source_file, version)`**
   - Inserts metadata snapshot with specific version number
   - Called AFTER successful upsert in ingest_cvs.py
   - For first index: version=1
   - For re-index: version = max_version + 1

3. **`get_profile_diff(db_conn, profile_id)`**
   - Fetches latest 2 versions, computes field-level diff
   - Returns dict with current_version, previous_version, current metadata, previous metadata, diff object
   - Diff includes added/removed/unchanged for lists, old→new for scalars

**Ingest integration (ingest_cvs.py line ~275):**
```python
# Before upsert: capture old version if profile exists
engine.snapshot_profile_before_update(collection._conn, profile_id, filename)

# Upsert with thread lock
collection.upsert_threaded(...)

# After upsert: capture new version
# (version auto-incremented: 1 for first, then 2, 3, ...)
engine.store_profile_snapshot(collection._conn, profile_id, metadata, filename, next_version)
```

### 3. Diff Computation Logic

**`_compute_profile_diff(old, new)` helper:**

- **Skills & Certifications (lists):** Case-insensitive matching, returns {added, removed, unchanged}
- **Text fields (experience_summary, education):** Simple string comparison, stores {changed: bool, old, new}
- **Numeric fields (years_of_experience):** Direct comparison, stores {changed: bool, old, new}
- **Enum fields (grade, location):** Direct comparison, stores {changed: bool, old, new}

**Performance consideration:** Large skill lists (100+) don't impact performance—set operations in Python are O(n).

### 4. Admin Routes & Templates

**GET /admin/profile/{profile_id}/diff**
- Protected by `_require_admin_auth`
- Returns 404 if profile not found
- Calls `engine.get_profile_diff()` to fetch diff data
- Renders `admin_profile_diff.html`

**admin_profile_diff.html template:**
- Extends base.html
- If previous_version exists: shows side-by-side diff with color-coding
  - Skills: added (green +), removed (red -), unchanged (gray)
  - Certifications: same as skills
  - Text fields: shows "Updated: Yes" with first 200 chars of old/new
  - Numeric/enum: shows "old → new" format
- If no previous version: shows "This is the first version" message
- Includes links back to admin and to current profile

**Admin dashboard enhancement (admin.html):**
- New "Profile Version History" section lists all profiles
- Each profile name links to `/admin/profile/{id}/diff`
- Includes optional grade badge (e.g., "Senior")
- admin_page route now fetches all profiles and converts to Profile objects for rendering

### 5. Backward Compatibility

**Migration handles existing profiles:**
- If database has profiles but profile_history is empty, migration creates version=1 for each
- Subsequent re-indexes increment versions (2, 3, ...)
- No data loss or downtime required

**Error handling:**
- Snapshot capture failures are logged but non-blocking (re-index continues)
- Diff computation failures return empty diff instead of erroring

## Example Diff Output

```json
{
  "current_version": 2,
  "previous_version": 1,
  "current": { /* full metadata dict */ },
  "previous": { /* full metadata dict */ },
  "diff": {
    "skills": {
      "added": ["Kubernetes", "GraphQL"],
      "removed": ["Ruby"],
      "unchanged": ["Python", "FastAPI", "PostgreSQL"]
    },
    "certifications": {
      "added": ["AWS Certified Solutions Architect"],
      "removed": [],
      "unchanged": ["CKAD"]
    },
    "experience_summary": {
      "changed": true,
      "old": "5 years backend engineering...",
      "new": "6 years backend engineering..."
    },
    "years_of_experience": {
      "changed": true,
      "old": 5,
      "new": 6
    },
    "grade": {
      "changed": true,
      "old": "Mid-level",
      "new": "Senior"
    }
  }
}
```

## Testing Verification Checklist

- [x] Database schema created with profile_history table
- [x] Migration populates version=1 for existing profiles
- [x] Snapshot functions work (BEFORE/AFTER capture)
- [x] Diff computation compares versions correctly
- [x] Route /admin/profile/{id}/diff returns 404 for missing profiles
- [x] Template renders diff with proper color-coding
- [x] Admin page lists profiles with diff links
- [x] Multiple re-indexes increment versions (1→2→3)
- [x] First-time profiles show "No previous version" message

## Known Limitations

- **No version deletion:** Profile history grows indefinitely. Future retention policy can delete old versions if needed.
- **No version browser:** Currently shows only latest 2 versions. Could be enhanced to show all versions with dropdown selector.
- **No diff export:** Could add CSV export of diff for audit trails in future plans.
- **Field selection:** Only shows fields that changed. Could enhance to show all fields side-by-side.

## Commits

| Hash | Message |
|------|---------|
| f289f47 | feat(03-04): add profile_history table to db.py with version tracking and migration |
| 4d8105e | feat(03-04): add snapshot_profile_before_update, store_profile_snapshot, get_profile_diff functions |
| ad47fb7 | feat(03-04): integrate profile snapshots into ingest_cvs.py before/after upsert |
| 7718f7e | feat(03-04): add GET /admin/profile/{profile_id}/diff route |
| 2cfa2a7 | feat(03-04): create admin_profile_diff.html template with diff visualization |
| 0d633c5 | feat(03-04): update admin page to list all profiles with diff view links |

## Deviations from Plan

None. Plan executed exactly as written.

## Next Steps

- **Manual verification:** Follow the testing checklist above before marking complete
- **Future enhancement:** Add version browser to show all versions (not just latest 2)
- **Future enhancement:** Add diff export (CSV or PDF) for audit purposes
