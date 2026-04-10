---
phase: "03-advanced-features"
plan: "02"
wave: 2
type: "execute"
autonomous: true
requirements: ["FEAT-05"]
depends_on: ["03-01"]
files_modified:
  - app/main.py
  - app/search/engine.py
  - app/templates/gap_analysis.html
  - app/templates/base.html
---

<objective>
Create a skill gap analysis page that accepts a comma-separated list of required skills and returns a table showing which team members cover each skill and which skills have gaps.

**Purpose:** Help team leads quickly assess whether their available team can cover required skills for a project, or identify which consultants need upskilling.

**Output:**
- GET `/gap-analysis` form page
- POST `/gap-analysis` results page showing:
  - Table with rows = required skills, columns = profiles (showing checkmark if has skill)
  - Summary row: gap count and coverage percentage per skill
  - Overall coverage percentage
- New template `gap_analysis.html` with form and results
- Helper function in engine.py to calculate skill coverage
</objective>

<execution_context>
@/Users/8jorgee/.claude/rules/common/development-workflow.md
@/Users/8jorgee/.claude/rules/common/coding-style.md
</execution_context>

<context>
@/Users/8jorgee/Desktop/cvsrag/.planning/ROADMAP.md
@/Users/8jorgee/Desktop/cvsrag/app/main.py (lines 228–248, GET / route for reference)
@/Users/8jorgee/Desktop/cvsrag/app/search/engine.py (lines 401–422, get_all_skills pattern)
@/Users/8jorgee/Desktop/cvsrag/app/models.py (Profile model for skill structure)

## Design Notes

**Form input:** Comma-separated skills (e.g., "Python, Azure, AWS, DevOps")

**Analysis logic:**
- Query all profiles from database
- For each required skill, find profiles that have it (case-insensitive match)
- Build coverage matrix: skill × profile → boolean (has skill)
- Calculate: profiles with skill / total profiles × 100% = coverage %
- Calculate: gaps = (total profiles - profiles with skill) for each skill

**UI/UX:**
- Form is simple: textarea with placeholder "Enter required skills, one per line or comma-separated"
- Results in a responsive table (HTML table with horizontal scroll on mobile if needed)
- Summary card at top: "X skills requested, Y fully covered (100%), Z partially covered, A gaps"
- Color-coded: ✓ (green) for covered, ✗ (red) for gap
- Sort table by coverage % (most critical gaps first)

**Database:** Uses existing profiles collection via get_collection().get(), no new tables needed.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create calculate_skill_coverage function in engine.py</name>
  <files>app/search/engine.py</files>
  <action>
Add a new function to engine.py (after line 453) named calculate_skill_coverage():

```python
def calculate_skill_coverage(required_skills: list[str]) -> dict:
    """
    Calculate skill coverage across all profiles.

    Args:
        required_skills: List of skill names (case-insensitive)

    Returns:
        dict with keys:
        - total_profiles: int
        - skill_coverage: dict[skill_name] = {
            "count": int (profiles with this skill),
            "percentage": float (0-100),
            "gaps": int (profiles without this skill),
            "profile_ids": list[str] (IDs of profiles with this skill)
          }
        - profiles: list[dict] with id, name, skills (for rendering table)
        - overall_coverage: float (0-100, average coverage across all skills)
    """
```

Logic:
1. Fetch all profiles via collection.get(include=["metadatas"])
2. For each profile, parse skills_json from metadata
3. Normalize all skills to lowercase for matching
4. For each required skill:
   - Count how many profiles have it (case-insensitive)
   - Calculate coverage percentage
   - Collect profile IDs that have it
5. Calculate overall_coverage as average coverage % across all required skills
6. Return comprehensive dict suitable for template rendering

Normalize input skills to lowercase. Handle empty input (return empty dict or all-zeros).
  </action>
  <verify>
    ```bash
    grep -n "def calculate_skill_coverage" /Users/8jorgee/Desktop/cvsrag/app/search/engine.py
    ```
    Expected: Function exists with docstring and return structure visible.
  </verify>
  <done>calculate_skill_coverage function added to engine.py, returns skill coverage matrix.</done>
</task>

<task type="auto">
  <name>Task 2: Add GET /gap-analysis and POST /gap-analysis routes to main.py</name>
  <files>app/main.py</files>
  <action>
Add two routes to main.py after the /search route (after line 297):

**GET /gap-analysis:**
```python
@app.get("/gap-analysis", response_class=HTMLResponse)
async def gap_analysis_form(request: Request):
    collection = get_collection()
    total = collection.count()
    all_skills = engine.get_all_skills() if total > 0 else []

    return templates.TemplateResponse(
        "gap_analysis.html",
        {
            "request": request,
            "mode": "form",
            "total_profiles": total,
            "all_skills": all_skills,
        },
    )
```

**POST /gap-analysis:**
```python
@app.post("/gap-analysis", response_class=HTMLResponse)
async def gap_analysis_submit(
    request: Request,
    skills_input: str = Form(""),
):
    # Parse comma-separated or newline-separated skills
    raw_skills = [s.strip() for s in skills_input.replace(',', '\n').split('\n') if s.strip()]

    if not raw_skills:
        return templates.TemplateResponse(
            "gap_analysis.html",
            {
                "request": request,
                "mode": "error",
                "error_message": "Please enter at least one skill",
                "total_profiles": get_collection().count(),
                "all_skills": engine.get_all_skills(),
            },
        )

    coverage = engine.calculate_skill_coverage(raw_skills)

    return templates.TemplateResponse(
        "gap_analysis.html",
        {
            "request": request,
            "mode": "results",
            "skills_input": raw_skills,
            "coverage_data": coverage,
            "total_profiles": coverage.get("total_profiles", 0),
        },
    )
```

Both routes are public (no admin auth required). Add CSRF protection (should be automatic via middleware, but verify).
  </action>
  <verify>
    ```bash
    grep -n "@app.get(\"/gap-analysis\")\|@app.post(\"/gap-analysis\")" /Users/8jorgee/Desktop/cvsrag/app/main.py
    ```
    Expected: Both routes defined with correct signatures.
  </verify>
  <done>GET and POST /gap-analysis routes added to main.py, route to template with coverage data.</done>
</task>

<task type="auto">
  <name>Task 3: Create gap_analysis.html template</name>
  <files>app/templates/gap_analysis.html</files>
  <action>
Create a new template file `app/templates/gap_analysis.html` extending base.html with three sections:

**Section 1: Form (when mode == "form")**
```html
<h1>Skill Gap Analysis</h1>
<p>Enter the skills your project requires, and we'll show you which team members cover each skill.</p>

<form method="post" action="/gap-analysis">
  <textarea name="skills_input" placeholder="Enter skills (comma-separated or one per line):&#10;e.g., Python, Azure, DevOps, Kubernetes" rows="6" cols="50"></textarea>
  <button type="submit">Analyze Coverage</button>
</form>

<div class="skills-suggestions">
  <p><strong>Available skills in your team:</strong></p>
  <ul>
    {% for skill in all_skills[:20] %}
      <li>{{ skill }}</li>
    {% endfor %}
    {% if all_skills|length > 20 %}
      <li>... and {{ all_skills|length - 20 }} more</li>
    {% endif %}
  </ul>
</div>
```

**Section 2: Results (when mode == "results")**
```html
<h1>Skill Gap Analysis Results</h1>

<div class="analysis-summary">
  <h2>Coverage Summary</h2>
  <p><strong>Overall Coverage: {{ "%.0f" | format(coverage_data.overall_coverage) }}%</strong></p>
  <ul>
    {% for skill, data in coverage_data.skill_coverage.items() %}
      <li>{{ skill }}: {{ data.percentage | round(1) }}% ({{ data.count }}/{{ total_profiles }} profiles)</li>
    {% endfor %}
  </ul>
</div>

<table class="coverage-matrix">
  <thead>
    <tr>
      <th>Skill</th>
      <th>Coverage %</th>
      <th>Covered By</th>
      <th>Gaps</th>
    </tr>
  </thead>
  <tbody>
    {% for skill in skills_input %}
      {% set skill_data = coverage_data.skill_coverage.get(skill.lower(), {}) %}
      <tr class="{% if skill_data.percentage == 100 %}covered{% elif skill_data.percentage >= 50 %}partial{% else %}gap{% endif %}">
        <td class="skill-name">{{ skill }}</td>
        <td class="coverage-percent">{{ skill_data.percentage | round(1) }}%</td>
        <td class="profiles-covered">
          {% if skill_data.count > 0 %}
            ✓ {{ skill_data.count }} profile{{ "s" if skill_data.count > 1 else "" }}
          {% else %}
            <span style="color: red;">No one</span>
          {% endif %}
        </td>
        <td class="gaps-count">
          {% if skill_data.gaps > 0 %}
            <span style="color: red;">{{ skill_data.gaps }}</span>
          {% else %}
            ✓ None
          {% endif %}
        </td>
      </tr>
    {% endfor %}
  </tbody>
</table>

<a href="/gap-analysis">← New Analysis</a>
```

**Section 3: Error (when mode == "error")**
```html
<h1>Skill Gap Analysis</h1>
<div class="error-message" style="color: red; border: 1px solid red; padding: 10px;">
  <p>{{ error_message }}</p>
</div>
<a href="/gap-analysis">← Try Again</a>
```

All sections inherit from base.html (use {% extends "base.html" %}).
  </action>
  <verify>
    ```bash
    test -f /Users/8jorgee/Desktop/cvsrag/app/templates/gap_analysis.html && echo "exists" && wc -l /Users/8jorgee/Desktop/cvsrag/app/templates/gap_analysis.html
    ```
    Expected: File exists with ~100+ lines of Jinja2 template.
  </verify>
  <done>gap_analysis.html template created with form, results, and error modes.</done>
</task>

<task type="auto">
  <name>Task 4: Add navigation link to Gap Analysis page in base.html</name>
  <files>app/templates/base.html</files>
  <action>
In base.html (the main navigation/menu section), add a link to /gap-analysis:

Find the navigation section (typically in a <nav> or <header> element) and add:
```html
<a href="/gap-analysis">Skill Gap Analysis</a>
```

Or, if there's a list of links:
```html
<li><a href="/gap-analysis">Skill Gap Analysis</a></li>
```

Place it near other main feature links (after search, before admin if applicable). Keep styling consistent with existing nav items.
  </action>
  <verify>
    ```bash
    grep -n "gap-analysis\|Gap Analysis" /Users/8jorgee/Desktop/cvsrag/app/templates/base.html
    ```
    Expected: Link to /gap-analysis visible in navigation.
  </verify>
  <done>Navigation bar includes link to Skill Gap Analysis page.</done>
</task>

<task type="auto">
  <name>Task 5: Test skill coverage calculation with sample data</name>
  <files>app/search/engine.py (test-only)</files>
  <action>
No new files created. This is a verification task.

Manually test the calculate_skill_coverage function by:

1. Run the app: `cd /Users/8jorgee/Desktop/cvsrag && python -m uvicorn app.main:app --reload`
2. Navigate to http://localhost:8000/gap-analysis
3. Enter sample skills: "Python, JavaScript, Azure"
4. Submit form and verify results table:
   - Each skill appears as a row
   - Coverage % calculated correctly (0-100)
   - Profiles covered shows correct count
   - Gaps shows correct count (total_profiles - covered)
   - Overall coverage shows average across all skills

5. Test edge cases:
   - Enter non-existent skill (should show 0% coverage)
   - Enter skill that all profiles have (should show 100%)
   - Enter skills with mixed case (should normalize and match)

No automated test required for this task (manual verification only).
  </action>
  <verify>
    Manual test via browser:
    1. Open http://localhost:8000/gap-analysis
    2. Enter "python, azure, devops"
    3. Click "Analyze Coverage"
    4. Verify results table populates correctly
    5. Check that percentages sum correctly for overall coverage
  </verify>
  <done>Skill coverage calculation works correctly and results display in table format.</done>
</task>

</tasks>

<verification>
1. **Form loads:** Navigate to http://localhost:8000/gap-analysis, verify form appears with textarea and submit button.
2. **Form submission:** Enter "Python, Azure, DevOps", click submit, verify results table appears.
3. **Results accuracy:** Verify coverage % for each skill matches expected (e.g., if 3 of 5 profiles have Python, should show 60%).
4. **Overall coverage:** Verify overall coverage % is the average of all skill coverages.
5. **Navigation:** Verify link to Gap Analysis appears in main navigation bar.
6. **Error handling:** Submit empty form, verify error message appears.
7. **Case insensitivity:** Enter "python" and "PYTHON" separately, verify they match the same profiles.
</verification>

<success_criteria>
- [ ] GET /gap-analysis shows form with textarea and list of available skills
- [ ] POST /gap-analysis accepts comma-separated or newline-separated skills
- [ ] Results table shows skill × coverage matrix with percentages
- [ ] Coverage % calculated correctly: (profiles with skill / total profiles) × 100
- [ ] Overall coverage shows average coverage across all required skills
- [ ] Navigation bar includes link to Skill Gap Analysis page
- [ ] Skill matching is case-insensitive
</success_criteria>

<output>
After completion, create `.planning/03-advanced-features/03-02-SUMMARY.md` with:
- Skill coverage calculation logic and test results
- Template rendering and table structure
- Performance notes (if analyzing >100 profiles)
- Known limitations (e.g., exact skill match only, no fuzzy matching)
</output>
