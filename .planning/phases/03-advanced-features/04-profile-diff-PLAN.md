---
phase: "03-advanced-features"
plan: "04"
wave: 3
type: "execute"
autonomous: true
requirements: ["FEAT-08"]
depends_on: ["03-01"]
files_modified:
  - app/db.py
  - scripts/ingest_cvs.py
  - app/main.py
  - app/templates/admin.html
---

<objective>
Enable admins to view field-level changes to profile metadata after re-indexing a CV. Store versioned profile snapshots and provide a diff view showing what changed (name, skills added/removed, grade updated, etc.).

**Purpose:** Reduce manual verification work after re-indexing by making it obvious what structural fields changed vs stayed the same.

**Output:**
- New SQLite table `profile_history` storing versioned profile snapshots
- Profile snapshot captured BEFORE each upsert during re-indexing
- New admin route `/admin/profile/{profile_id}/diff` showing side-by-side field diff
- Admin profile list links to diff view
- Handle first-time index gracefully (no "previous version" to diff against)
</objective>

<execution_context>
@/Users/8jorgee/.claude/rules/common/development-workflow.md
@/Users/8jorgee/.claude/rules/common/coding-style.md
</execution_context>

<context>
@/Users/8jorgee/Desktop/cvsrag/.planning/ROADMAP.md
@/Users/8jorgee/Desktop/cvsrag/app/db.py (lines 54–70, table creation pattern)
@/Users/8jorgee/Desktop/cvsrag/scripts/ingest_cvs.py (re-indexing logic where upsert happens)
@/Users/8jorgee/Desktop/cvsrag/app/main.py (lines 335–371, admin page)
@/Users/8jorgee/Desktop/cvsrag/app/models.py (Profile model fields)

## Design Notes

**Profile history table:**
- id: INTEGER PRIMARY KEY AUTOINCREMENT
- profile_id: TEXT (foreign key to profiles.id in FAISS/SQLite)
- version: INTEGER (1, 2, 3... for each change)
- metadata_json: TEXT (complete JSON snapshot of all structured fields: skills, certs, experience, grade, etc.)
- created_at: TEXT (ISO timestamp)
- source_file: TEXT (the CV filename that produced this version)

**Diff logic:**
1. On first index of a profile: store snapshot with version=1
2. On re-index (upsert): before updating, fetch previous metadata, store old version
3. Diff view: compare latest version vs previous version field-by-field
4. Show:
   - Skills: added (green), removed (red), unchanged (gray)
   - Certifications: added (green), removed (red)
   - Text fields (experience_summary, education): character-level or paragraph-level diff (show "updated" if changed)
   - Numeric fields (years_of_experience): show before → after
   - Enum fields (grade, location): show before → after
5. First-time index: show "No previous version" instead of diff

**Admin UI:**
- Admin profile list (already exists on /admin) should link profile names to /admin/profile/{id}/diff
- Diff page shows current version at top, "Previous version(s)" section below with version selector
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add profile_history table to SQLite schema in db.py</name>
  <files>app/db.py</files>
  <action>
In db.py's _open_db() method (around line 50), add a new profile_history table after the existing tables:

```sql
CREATE TABLE IF NOT EXISTS profile_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id      TEXT NOT NULL,
    version         INTEGER NOT NULL,
    metadata_json   TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    source_file     TEXT,
    FOREIGN KEY (profile_id) REFERENCES profiles(id),
    UNIQUE (profile_id, version)
)
```

Create indexes:
- ON (profile_id, version DESC) for fast "get all versions of profile X" queries
- ON created_at for cleanup queries (if implementing retention policy later)

Add initialization code: When DB opens, if profile_history is empty but profiles table has data, populate initial history with version=1 snapshots for all existing profiles (one-time migration).

Note: This migration code should log that it's capturing initial snapshots, then never run again.
  </action>
  <verify>
    ```bash
    sqlite3 /Users/8jorgee/Desktop/cvsrag/chroma_db/metadata.db ".schema profile_history" | head -20
    ```
    Expected: Table schema with all columns and indexes listed.
  </verify>
  <done>SQLite schema includes profile_history table with version tracking and indexes.</done>
</task>

<task type="auto">
  <name>Task 2: Add snapshot and diff functions to engine.py</name>
  <files>app/search/engine.py</files>
  <action>
Add three new functions to engine.py (after line 453):

**1. snapshot_profile_before_update(db_conn, profile_id: str) -> None**
- Query current profile metadata from SQLite (SELECT metadata FROM profiles WHERE id = ?)
- If profile exists (has previous version), get max version from profile_history
- Parse metadata_json
- Insert into profile_history with version = max_version + 1
- Use current timestamp (datetime.now().isoformat())
- Log snapshot created

If profile doesn't exist yet (first index), skip snapshot (version 1 will be created on first display).

**2. store_profile_snapshot(db_conn, profile_id: str, metadata: dict, source_file: str, version: int) -> None**
- Insert into profile_history: (profile_id, version, metadata_json, created_at, source_file)
- Use provided version number (typically 1 for initial snapshot)

Helper to insert new snapshots during re-indexing.

**3. get_profile_diff(db_conn, profile_id: str) -> dict**
- Query profile_history for this profile_id, order by version DESC, limit 2
- If only 1 version exists, return {"current": metadata, "previous": None, "version": 1}
- If 2+ versions exist, parse both JSONs and compute field-level diff
- Return dict:
  ```python
  {
      "current_version": 2,
      "previous_version": 1,
      "current": {metadata dict},
      "previous": {metadata dict},
      "diff": {
          "skills": {"added": [...], "removed": [...], "unchanged": [...]},
          "certifications": {"added": [...], "removed": [...], "unchanged": [...]},
          "experience_summary": {"changed": bool, "old": str, "new": str},
          "education": {"changed": bool, "old": str, "new": str},
          "years_of_experience": {"changed": bool, "old": int, "new": int},
          "grade": {"changed": bool, "old": str, "new": str},
          "location": {"changed": bool, "old": str, "new": str},
          ...
      }
  }
  ```

All text comparisons should be case-insensitive for lists (skills, certs).
  </action>
  <verify>
    ```bash
    grep -n "def snapshot_profile_before_update\|def store_profile_snapshot\|def get_profile_diff" /Users/8jorgee/Desktop/cvsrag/app/search/engine.py
    ```
    Expected: All three functions defined.
  </verify>
  <done>Three profile history functions added to engine.py.</done>
</task>

<task type="auto">
  <name>Task 3: Integrate snapshot capture into ingest_cvs.py re-indexing</name>
  <files>scripts/ingest_cvs.py</files>
  <action>
Modify scripts/ingest_cvs.py to capture profile snapshots BEFORE updating profiles:

Find the location where profiles are upserted (likely collection.upsert() or collection.upsert_threaded() calls).

BEFORE the upsert call, add:

```python
for profile_id in ids_to_upsert:
    engine.snapshot_profile_before_update(get_collection()._conn, profile_id)
```

This captures the previous version of metadata before the upsert overwrites it.

For first-time indexing of a new profile (no previous version):
- snapshot_profile_before_update will skip (no existing metadata to snapshot)
- After upsert succeeds, capture an initial snapshot with version=1:

```python
for i, profile_id in enumerate(ids_to_upsert):
    # After successful upsert
    new_metadata = metadatas[i]  # From upsert call
    engine.store_profile_snapshot(
        get_collection()._conn,
        profile_id,
        new_metadata,
        source_file,
        version=1
    )
```

Or, simpler: Always store the new version after upsert (overwrite the before snapshot with the after snapshot, increment version).

Keep the logic simple: capture old version before upsert, then capture new version after upsert (version increments by 1 each time).

Log progress_callback events (e.g., "Snapshotting profile {name}...") if using the callback pattern.
  </action>
  <verify>
    ```bash
    grep -n "snapshot_profile_before_update\|store_profile_snapshot" /Users/8jorgee/Desktop/cvsrag/scripts/ingest_cvs.py
    ```
    Expected: Calls visible around upsert logic.
  </verify>
  <done>ingest_cvs.py captures profile snapshots during re-indexing.</done>
</task>

<task type="auto">
  <name>Task 4: Add GET /admin/profile/{profile_id}/diff route in main.py</name>
  <files>app/main.py</files>
  <action>
Add a new admin route to main.py after the existing admin routes (after line 482):

```python
@app.get("/admin/profile/{profile_id}/diff", response_class=HTMLResponse)
async def admin_profile_diff(
    request: Request,
    profile_id: str,
    _: None = Depends(_require_admin_auth),
):
    """Show version diff for a profile."""
    profile = engine.get_profile_by_id(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    diff_data = engine.get_profile_diff(get_collection()._conn, profile_id)

    return templates.TemplateResponse(
        "admin_profile_diff.html",
        {
            "request": request,
            "profile": profile,
            "diff_data": diff_data,
        },
    )
```

Route is protected by _require_admin_auth. Should return 404 if profile doesn't exist.
  </action>
  <verify>
    ```bash
    grep -n "@app.get(\"/admin/profile/{profile_id}/diff\")" /Users/8jorgee/Desktop/cvsrag/app/main.py
    ```
    Expected: Route defined.
  </verify>
  <done>GET /admin/profile/{profile_id}/diff route added to main.py.</done>
</task>

<task type="auto">
  <name>Task 5: Create admin_profile_diff.html template</name>
  <files>app/templates/admin_profile_diff.html</files>
  <action>
Create a new template file `app/templates/admin_profile_diff.html` extending base.html:

```html
{% extends "base.html" %}

{% block content %}
<div class="admin-section">
  <h1>Profile Version History: {{ profile.name }}</h1>

  {% if diff_data.previous_version %}
    <div class="diff-container">
      <h2>Changes from v{{ diff_data.previous_version }} to v{{ diff_data.current_version }}</h2>

      <!-- Skills Diff -->
      {% if diff_data.diff.skills %}
        <section class="diff-section">
          <h3>Skills</h3>
          {% if diff_data.diff.skills.added %}
            <div class="diff-added">
              <strong>Added:</strong>
              <ul>
                {% for skill in diff_data.diff.skills.added %}
                  <li style="color: green;">+ {{ skill }}</li>
                {% endfor %}
              </ul>
            </div>
          {% endif %}

          {% if diff_data.diff.skills.removed %}
            <div class="diff-removed">
              <strong>Removed:</strong>
              <ul>
                {% for skill in diff_data.diff.skills.removed %}
                  <li style="color: red;">- {{ skill }}</li>
                {% endfor %}
              </ul>
            </div>
          {% endif %}

          {% if diff_data.diff.skills.unchanged %}
            <div class="diff-unchanged">
              <strong>Unchanged ({{ diff_data.diff.skills.unchanged|length }}):</strong>
              <p>{{ diff_data.diff.skills.unchanged[:5] | join(', ') }}{% if diff_data.diff.skills.unchanged|length > 5 %}, ...{% endif %}</p>
            </div>
          {% endif %}
        </section>
      {% endif %}

      <!-- Certifications Diff -->
      {% if diff_data.diff.certifications %}
        <section class="diff-section">
          <h3>Certifications</h3>
          {% if diff_data.diff.certifications.added %}
            <div class="diff-added">
              <strong>Added:</strong>
              <ul>
                {% for cert in diff_data.diff.certifications.added %}
                  <li style="color: green;">+ {{ cert }}</li>
                {% endfor %}
              </ul>
            </div>
          {% endif %}

          {% if diff_data.diff.certifications.removed %}
            <div class="diff-removed">
              <strong>Removed:</strong>
              <ul>
                {% for cert in diff_data.diff.certifications.removed %}
                  <li style="color: red;">- {{ cert }}</li>
                {% endfor %}
              </ul>
            </div>
          {% endif %}
        </section>
      {% endif %}

      <!-- Text Fields Diff (experience, education) -->
      {% if diff_data.diff.experience_summary and diff_data.diff.experience_summary.changed %}
        <section class="diff-section">
          <h3>Experience Summary</h3>
          <p><strong>Updated:</strong> Yes</p>
          <div style="display: flex; gap: 20px;">
            <div style="flex: 1;">
              <h4>Previous</h4>
              <p style="color: #888;">{{ diff_data.diff.experience_summary.old[:200] }}...</p>
            </div>
            <div style="flex: 1;">
              <h4>Current</h4>
              <p>{{ diff_data.diff.experience_summary.new[:200] }}...</p>
            </div>
          </div>
        </section>
      {% endif %}

      <!-- Numeric/Enum Fields -->
      {% for field_name, field_diff in diff_data.diff.items() %}
        {% if field_name not in ['skills', 'certifications', 'experience_summary', 'education'] and field_diff.changed %}
          <section class="diff-section">
            <h3>{{ field_name | title }}</h3>
            <p>
              <strong>Previous:</strong> <code>{{ field_diff.old }}</code>
              <strong>→ Current:</strong> <code>{{ field_diff.new }}</code>
            </p>
          </section>
        {% endif %}
      {% endfor %}
    </div>
  {% else %}
    <div class="info-box">
      <p><strong>This is the first version of this profile.</strong> No previous version available to diff against.</p>
    </div>
  {% endif %}

  <div class="actions">
    <a href="/admin" class="btn">← Back to Admin</a>
    <a href="/profile/{{ profile.id }}" class="btn">View Current Profile</a>
  </div>
</div>
{% endblock %}
```

Keep styling minimal — use semantic HTML and let base.html's stylesheet handle formatting.
  </action>
  <verify>
    ```bash
    test -f /Users/8jorgee/Desktop/cvsrag/app/templates/admin_profile_diff.html && echo "exists"
    ```
    Expected: File exists.
  </verify>
  <done>admin_profile_diff.html template created with diff view for profile versions.</done>
</task>

<task type="auto">
  <name>Task 6: Update admin.html to link profiles to diff view</name>
  <files>app/templates/admin.html</files>
  <action>
In the admin profile list (assuming there's a section showing profile names or a table of profiles on the admin page), update the profile name/link to point to the diff view:

Find the section where profile names are displayed (likely in admin_page route which renders missing_availability and stale_profiles lists).

For each profile name, change from:
```html
<a href="/profile/{{ profile_id }}">{{ profile_name }}</a>
```

To:
```html
<a href="/admin/profile/{{ profile_id }}/diff">{{ profile_name }}</a>
```

Or, if there's no existing profile list on the admin page, add one. Query all profiles and display them with links to the diff view:

```html
<h2>All Profiles</h2>
<ul>
  {% for profile in all_profiles %}
    <li><a href="/admin/profile/{{ profile.id }}/diff">{{ profile.name }}</a> ({{ profile.grade or 'N/A' }})</li>
  {% endfor %}
</ul>
```

For the second case, update the admin_page route to also fetch all profiles:
```python
collection = get_collection()
all_profiles = collection.get(include=["metadatas"])
# Parse into list of Profile objects
# Pass to template
```

Keep it simple for now — just add diff links to existing profile lists, or create a minimal "Profile Versions" section.
  </action>
  <verify>
    ```bash
    grep -n "/admin/profile.*diff\|admin_profile_diff" /Users/8jorgee/Desktop/cvsrag/app/templates/admin.html
    ```
    Expected: Links to diff view visible.
  </verify>
  <done>Admin page includes links to profile diff view.</done>
</task>

<task type="auto">
  <name>Task 7: Manual test of profile versioning and diff view</name>
  <files>scripts/ingest_cvs.py (test-only)</files>
  <action>
No new files created. This is a verification task.

Manually test the profile versioning feature:

1. Start with fresh database: `rm -rf /Users/8jorgee/Desktop/cvsrag/chroma_db`
2. Run the app: `cd /Users/8jorgee/Desktop/cvsrag && python -m uvicorn app.main:app --reload`
3. Upload a CV and run initial indexing
4. Check admin page: navigate to /admin (provide credentials if prompted)
5. Click a profile name → verify diff page shows "No previous version"
6. Modify the CV file (e.g., add a new skill in the PPTX or change the name)
7. Run re-indexing from admin page (click "Reindex" button)
8. Return to the same profile diff page, refresh
9. Verify diff shows:
   - Previous version (v1) displayed
   - New version (v2) displayed
   - Changes highlighted: skills added (green), removed (red)
   - Text fields show "Updated" if changed
10. Test multiple versions: re-index same profile again, verify version increments to 3

Edge cases:
- Delete a skill from CV → verify it shows in "Removed" section
- Add multiple new skills → verify all appear in "Added" section
- Change grade or location → verify field shows old → new

No automated test required (manual verification only).
  </action>
  <verify>
    Manual test via browser:
    1. Upload a CV and index it
    2. Navigate to /admin, find profile, click diff link
    3. Verify "No previous version" message
    4. Modify CV and re-index
    5. Return to diff page, refresh
    6. Verify changes are displayed (skills added/removed/unchanged)
    7. Verify version numbers increment correctly
  </verify>
  <done>Profile versioning and diff view work end-to-end.</done>
</task>

</tasks>

<verification>
1. **Database schema:** Verify profile_history table exists with correct columns and indexes.
2. **First-time snapshot:** Upload a new CV, verify profile_history has one entry (version 1) for that profile.
3. **Re-index snapshot:** Modify the CV, run re-index, verify profile_history now has two entries (v1 and v2).
4. **Diff view:** Navigate to /admin/profile/{id}/diff, verify changes are displayed (added/removed skills, changed text fields).
5. **First version:** Verify profile with only one version shows "No previous version" message.
6. **Admin links:** Verify admin.html has links to diff view.
7. **Version increment:** Index three times, verify version numbers go 1 → 2 → 3.
8. **Field-level diff:** Verify skills show as added/removed, numeric fields show before → after, text fields show "Updated".
</verification>

<success_criteria>
- [ ] profile_history table stores versioned profile snapshots with version numbers
- [ ] Profiles are snapshotted before re-indexing, preserving change history
- [ ] GET /admin/profile/{id}/diff shows side-by-side field-level diff between versions
- [ ] First-time profiles show "No previous version" instead of erroring
- [ ] Skills show as added (green), removed (red), unchanged (gray)
- [ ] Numeric and enum fields show "old → new" format
- [ ] Admin page links to profile diff view
- [ ] Version numbers increment correctly on each re-index
</success_criteria>

<output>
After completion, create `.planning/03-advanced-features/03-04-SUMMARY.md` with:
- Profile history schema and indexing strategy
- Diff calculation logic and performance (large skill lists)
- Template rendering and color-coding scheme
- Example diffs (skills added/removed, fields changed)
- Known limitations (if any)
</output>
