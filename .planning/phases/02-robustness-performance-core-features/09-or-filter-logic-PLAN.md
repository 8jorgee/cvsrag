---
phase: 02-robustness-performance-core-features
plan: 09
type: execute
wave: 3
depends_on: [02-01, 02-02]
files_modified:
  - app/models.py
  - app/search/filters.py
  - app/main.py
  - app/templates/search.html
autonomous: true
requirements: [SEARCH-02]

must_haves:
  truths:
    - "Filter query with skills_any=['Python','R'] matches profiles with Python OR R (not requiring both)"
    - "Filter query with skills=['Python','Go'] matches profiles with Python AND Go (both required)"
    - "UI toggle switches between AND and OR modes per filter group"
  artifacts:
    - path: app/models.py
      provides: "SearchQuery includes skills_any and certifications_any fields alongside skills/certifications"
      min_lines: 5
    - path: app/search/filters.py
      provides: "OR filter logic in apply_filters() for skills_any/certifications_any"
      min_lines: 10
    - path: app/main.py
      provides: "/search endpoint accepts skills_any and certifications_any Form fields"
      min_lines: 3
    - path: app/templates/search.html
      provides: "AND/OR toggle button for Skills and Certifications groups"
      min_lines: 5
  key_links:
    - from: app/models.py
      to: app/search/filters.py
      via: "skills_any, certifications_any fields"
      pattern: "skills_any:"
    - from: app/templates/search.html
      to: app/main.py
      via: "Form field name switching (skills vs skills_any)"
      pattern: "name=\"skills\""
---

<objective>
Add OR filter logic alongside existing AND filters for Skills and Certifications.

Purpose: Users can search for profiles with ANY of a skill set (OR) or ALL of a skill set (AND).

Output:
- SearchQuery includes skills_any and certifications_any fields
- filters.py applies OR logic: profile matches if ANY of the requested skills are present
- /search endpoint accepts both AND and OR form parameters
- search.html includes AND/OR toggle per filter group
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/phases/02-robustness-performance-core-features/02-CONTEXT.md
@.planning/phases/02-robustness-performance-core-features/02-RESEARCH.md

From CONTEXT.md, SEARCH-02:
- SearchQuery adds skills_any: list[str] and certifications_any: list[str]
- filters.py applies OR logic: any of skills_any must appear in profile skills
- UI: small toggle button next to each group label (AND → OR); selecting OR swaps name="skills" → name="skills_any" via JS
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add skills_any and certifications_any to SearchQuery model</name>
  <files>app/models.py</files>
  <action>
In app/models.py, update SearchQuery to include OR filter fields:

```python
class SearchQuery(BaseModel):
    query: str = ""
    # AND filters (existing)
    skills: list[str] = []
    certifications: list[str] = []
    # ... other existing AND filters ...

    # OR filters (new)
    skills_any: list[str] = []
    certifications_any: list[str] = []
```

These fields coexist with the AND versions. A search can use skills=[X, Y] (AND) or skills_any=[X, Y] (OR), but not both simultaneously (or you can support both and combine them with AND logic at the engine level).

For simplicity: skills_any and skills are mutually exclusive per filter group (UI enforces this via toggle).
  </action>
  <verify>
    <automated>pytest tests/unit/test_filters.py::test_skills_any_matches tests/unit/test_filters.py::test_skills_all_required -xvs</automated>
  </verify>
  <done>
SearchQuery includes skills_any and certifications_any fields, both test cases pass (OR and AND logic verified)
  </done>
</task>

<task type="auto">
  <name>Task 2: Implement OR filter logic in filters.py</name>
  <files>app/search/filters.py</files>
  <action>
In app/search/filters.py, update the filter application logic to handle both AND and OR:

Current logic (AND):
```python
def apply_filters(profile: dict, query: SearchQuery) -> bool:
    if query.skills:
        # ALL skills must be present (AND)
        if not all(skill in profile.get("skills", []) for skill in query.skills):
            return False
    # ... similar for other filters ...
    return True
```

New logic (add OR support):
```python
def apply_filters(profile: dict, query: SearchQuery) -> bool:
    # AND logic: ALL skills must be present
    if query.skills:
        if not all(skill in profile.get("skills", []) for skill in query.skills):
            return False

    # OR logic: ANY skill must be present
    if query.skills_any:
        if not any(skill in profile.get("skills", []) for skill in query.skills_any):
            return False

    # Same for certifications
    if query.certifications:
        if not all(cert in profile.get("certifications", []) for cert in query.certifications):
            return False

    if query.certifications_any:
        if not any(cert in profile.get("certifications", []) for cert in query.certifications_any):
            return False

    # ... other filters ...
    return True
```

Key difference:
- AND (all): `all(item in profile_list for item in query_list)` — every query item must be in profile
- OR (any): `any(item in profile_list for item in query_list)` — at least one query item must be in profile
  </action>
  <verify>
    <automated>pytest tests/unit/test_filters.py -xvs</automated>
  </verify>
  <done>
filters.py applies both AND and OR logic, both test cases pass (skills_any matches any, skills requires all)
  </done>
</task>

<task type="auto">
  <name>Task 3: Update /search endpoint in main.py to accept skills_any and certifications_any</name>
  <files>app/main.py</files>
  <action>
In app/main.py, update the `/search` POST endpoint to accept additional form fields:

```python
@app.post("/search")
async def search(
    request: Request,
    query: str = Form(...),
    skills: list[str] = Form(default=[]),
    certifications: list[str] = Form(default=[]),
    skills_any: list[str] = Form(default=[]),
    certifications_any: list[str] = Form(default=[]),
    # ... other existing form parameters ...
):
    search_query = SearchQuery(
        query=query,
        skills=skills,
        certifications=certifications,
        skills_any=skills_any,
        certifications_any=certifications_any,
        # ... other fields ...
    )
    # ... rest of search logic ...
```

Ensure that Form fields properly parse lists from form data (FastAPI handles multiple values with the same name as list).
  </action>
  <verify>
    <automated>grep -n "skills_any.*Form" app/main.py</automated>
  </verify>
  <done>
/search endpoint accepts skills_any and certifications_any Form parameters, passes to SearchQuery
  </done>
</task>

<task type="auto">
  <name>Task 4: Add AND/OR toggle to search.html for Skills and Certifications</name>
  <files>app/templates/search.html</files>
  <action>
In app/templates/search.html, update the Skills and Certifications filter sections to include toggle buttons:

For each filter group (Skills, Certifications), wrap in a container with toggle:

```html
<div class="filter-group">
  <label>
    Skills
    <button type="button" class="btn-toggle-filter" data-filter="skills">
      <span class="badge" id="skills-mode">AND</span>
    </button>
  </label>
  <div id="skills-inputs">
    <input type="hidden" id="skills-mode-field" name="skills" value="">
    <!-- Multiple checkbox or multi-select for skills -->
    <select id="skills-select" multiple class="form-control" onchange="updateSkillsField()">
      <!-- Skill options -->
    </select>
  </div>
</div>
```

Add JavaScript to toggle between AND and OR modes:

```javascript
<script>
function toggleFilterMode(filterName) {
  const modeSpan = document.getElementById(`${filterName}-mode`);
  const modeField = document.getElementById(`${filterName}-mode-field`);

  if (modeSpan.textContent === 'AND') {
    modeSpan.textContent = 'OR';
    modeField.name = `${filterName}_any`;
  } else {
    modeSpan.textContent = 'AND';
    modeField.name = filterName;
  }
}

// Attach toggle handlers
document.querySelectorAll('.btn-toggle-filter').forEach(btn => {
  btn.addEventListener('click', (e) => {
    e.preventDefault();
    const filterName = btn.dataset.filter;
    toggleFilterMode(filterName);
  });
});

function updateSkillsField() {
  const select = document.getElementById('skills-select');
  const modeField = document.getElementById('skills-mode-field');
  const selected = Array.from(select.selectedOptions).map(opt => opt.value);

  // Update the hidden field value (or rebuild form data)
  modeField.value = selected.join(',');
  // For proper form submission, dynamically create inputs
}
</script>
```

Simpler approach: Use a checkbox for each skill, and on form submit, collect checked items into either skills[] or skills_any[] based on the toggle state.

For prototyping: Static button that switches the input name attribute between "skills" and "skills_any".
  </action>
  <verify>
    <automated>grep -n "skills_any" app/templates/search.html</automated>
  </verify>
  <done>
AND/OR toggle button added to search.html, toggles between skills (AND) and skills_any (OR) field names via JavaScript
  </done>
</task>

</tasks>

<verification>
Run filter tests:
- `pytest tests/unit/test_filters.py -xvs` should pass both tests (AND and OR logic)
- Manual UI test: Select multiple skills with AND mode (default), search, verify all skills required in results. Switch to OR mode, search, verify any skill matches.
</verification>

<success_criteria>
- SearchQuery includes skills_any and certifications_any fields
- filters.py implements both AND logic (all required) and OR logic (any match)
- /search endpoint accepts skills_any and certifications_any Form fields
- search.html includes toggle button for each filter group (Skills, Certifications)
- Toggle switches field name from "skills" to "skills_any" via JavaScript
- Both test cases pass (AND and OR filter correctness)
</success_criteria>

<output>
After completion, create `.planning/phases/02-robustness-performance-core-features/02-09-SUMMARY.md` documenting:
- skills_any and certifications_any fields in SearchQuery
- OR filter logic in filters.py
- /search endpoint Form parameter handling
- AND/OR toggle implementation in search.html
- Test results confirming both AND and OR logic work correctly
</output>
