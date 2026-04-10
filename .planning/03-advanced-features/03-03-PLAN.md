---
phase: "03-advanced-features"
plan: "03"
wave: 2
type: "execute"
autonomous: true
requirements: ["FEAT-06"]
depends_on: ["03-01"]
files_modified:
  - app/main.py
  - app/search/engine.py
  - app/templates/team_builder.html
  - app/templates/base.html
---

<objective>
Create a team composition assistant page that uses Claude to suggest an optimal team from available profiles based on a project description and required skills.

**Purpose:** Reduce time spent manually selecting team members by leveraging Claude's ability to reason about profile fit, experience depth, and complementary skills.

**Output:**
- GET `/team-builder` form page (project description + required skills + team size)
- POST `/team-builder` results page showing Claude-suggested team with reasoning
- New template `team_builder.html` with form and results
- Helper function in engine.py to call Claude with profile context
</objective>

<execution_context>
@/Users/8jorgee/.claude/rules/common/development-workflow.md
@/Users/8jorgee/.claude/rules/common/coding-style.md
</execution_context>

<context>
@/Users/8jorgee/Desktop/cvsrag/.planning/ROADMAP.md
@/Users/8jorgee/Desktop/cvsrag/app/main.py (lines 275–306, _call_llm usage example in _claude_rerank)
@/Users/8jorgee/Desktop/cvsrag/app/search/engine.py (lines 275–306, _call_llm function)
@/Users/8jorgee/Desktop/cvsrag/app/models.py (Profile model)

## Design Notes

**Form inputs:**
- Project description (textarea): "Building a cloud migration platform for an enterprise customer. Need strong AWS expertise, DevOps practices, Python backend, React frontend."
- Required skills (comma-separated): "Python, AWS, DevOps, React"
- Team size (number): 3-5 people

**Claude prompt:**
System message establishes Claude as a talent matching expert. User message includes:
1. Project description
2. Required skills
3. Desired team size
4. All available profiles (name, skills, certifications, experience_summary, grade, availability)

Claude returns JSON with:
```json
{
  "team": [
    {
      "profile_id": "uuid",
      "profile_name": "John Doe",
      "role": "Tech Lead / AWS Architect",
      "reasoning": "Strong AWS experience, 12+ years in cloud migrations, familiar with enterprise constraints",
      "gaps": "Limited React experience",
      "fit_score": 0.95
    },
    ...
  ],
  "team_summary": "This team covers all required skills with strong depth in cloud/DevOps and full-stack capability. Strong team for enterprise delivery."
}
```

**UI/UX:**
- Form collects project description, skills, team size
- Results show suggested team members with roles, reasoning, gaps, and fit scores
- Color-coded: green for high fit (>0.85), yellow for medium (0.65-0.85), orange for low (<0.65)
- Summary card at top with team overview
- Ability to "refine" (go back to form) or "export" (CSV of suggested team)

**Database:** Uses existing profiles collection via get_collection().get(), no new tables needed.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create suggest_team_composition function in engine.py</name>
  <files>app/search/engine.py</files>
  <action>
Add a new function to engine.py (after line 453) named suggest_team_composition():

```python
def suggest_team_composition(
    project_description: str,
    required_skills: list[str],
    team_size: int,
) -> dict:
    """
    Use Claude to suggest an optimal team from available profiles.

    Args:
        project_description: Description of the project and requirements
        required_skills: List of required skill names
        team_size: Desired number of team members (e.g., 3-5)

    Returns:
        dict with keys:
        - team: list[dict] with profile_id, profile_name, role, reasoning, gaps, fit_score
        - team_summary: str (Claude's overall team assessment)
        - error: str (if Claude call failed)
    """
```

Logic:
1. Fetch all profiles via collection.get(include=["metadatas"])
2. Build profiles_text for Claude (similar to _claude_rerank, include name, skills, certs, experience, grade, availability)
3. Call _call_llm() with:
   - System prompt: "You are an expert talent matcher for consulting projects. Suggest the best team from available profiles based on project needs and skill requirements. Return JSON with team member suggestions and reasoning."
   - User prompt: "Project: {project_description}\n\nRequired skills: {', '.join(required_skills)}\n\nDesired team size: {team_size}\n\nAvailable profiles:\n{profiles_text}\n\nReturn JSON with 'team' array and 'team_summary' field."
4. Parse JSON response using parse_json_response() (handles markdown-wrapped JSON)
5. Return dict with team array and summary
6. Catch errors and return {"error": "Claude response parsing failed"} — don't crash

Structure the return dict for template rendering:
```python
return {
    "team": [
        {
            "profile_id": str,
            "profile_name": str,
            "role": str,
            "reasoning": str,
            "gaps": str,
            "fit_score": float (0-1),
        }
    ],
    "team_summary": str,
    "error": None,  # or error message if failed
}
```

Handle edge cases:
- Empty profiles list → return error
- Claude returns invalid JSON → log and return error
- team_size invalid (< 1 or > total profiles) → clamp to valid range
  </action>
  <verify>
    ```bash
    grep -n "def suggest_team_composition" /Users/8jorgee/Desktop/cvsrag/app/search/engine.py
    ```
    Expected: Function exists with docstring and parse_json_response call visible.
  </verify>
  <done>suggest_team_composition function added to engine.py, calls Claude with profile context.</done>
</task>

<task type="auto">
  <name>Task 2: Add GET /team-builder and POST /team-builder routes to main.py</name>
  <files>app/main.py</files>
  <action>
Add two routes to main.py after the /gap-analysis route:

**GET /team-builder:**
```python
@app.get("/team-builder", response_class=HTMLResponse)
async def team_builder_form(request: Request):
    collection = get_collection()
    total = collection.count()
    all_skills = engine.get_all_skills() if total > 0 else []

    return templates.TemplateResponse(
        "team_builder.html",
        {
            "request": request,
            "mode": "form",
            "total_profiles": total,
            "all_skills": all_skills,
        },
    )
```

**POST /team-builder:**
```python
@app.post("/team-builder", response_class=HTMLResponse)
async def team_builder_submit(
    request: Request,
    project_description: str = Form(""),
    required_skills: str = Form(""),
    team_size: str = Form("3"),
):
    # Validate inputs
    if not project_description or not project_description.strip():
        return templates.TemplateResponse(
            "team_builder.html",
            {
                "request": request,
                "mode": "error",
                "error_message": "Please describe your project",
                "total_profiles": get_collection().count(),
                "all_skills": engine.get_all_skills(),
            },
        )

    if not required_skills or not required_skills.strip():
        return templates.TemplateResponse(
            "team_builder.html",
            {
                "request": request,
                "mode": "error",
                "error_message": "Please specify required skills",
                "total_profiles": get_collection().count(),
                "all_skills": engine.get_all_skills(),
            },
        )

    try:
        team_size = max(1, min(int(team_size), get_collection().count()))
    except (ValueError, TypeError):
        team_size = 3

    # Parse skills
    skills_list = [s.strip() for s in required_skills.replace(',', '\n').split('\n') if s.strip()]

    # Call Claude
    suggestion = engine.suggest_team_composition(project_description, skills_list, team_size)

    if suggestion.get("error"):
        return templates.TemplateResponse(
            "team_builder.html",
            {
                "request": request,
                "mode": "error",
                "error_message": f"Team composition failed: {suggestion['error']}",
                "total_profiles": get_collection().count(),
                "all_skills": engine.get_all_skills(),
            },
        )

    return templates.TemplateResponse(
        "team_builder.html",
        {
            "request": request,
            "mode": "results",
            "project_description": project_description,
            "required_skills": skills_list,
            "team_size": team_size,
            "suggestion": suggestion,
            "total_profiles": get_collection().count(),
        },
    )
```

Both routes are public (no admin auth required).
  </action>
  <verify>
    ```bash
    grep -n "@app.get(\"/team-builder\")\|@app.post(\"/team-builder\")" /Users/8jorgee/Desktop/cvsrag/app/main.py
    ```
    Expected: Both routes defined with correct signatures.
  </verify>
  <done>GET and POST /team-builder routes added to main.py.</done>
</task>

<task type="auto">
  <name>Task 3: Create team_builder.html template</name>
  <files>app/templates/team_builder.html</files>
  <action>
Create a new template file `app/templates/team_builder.html` extending base.html with three sections:

**Section 1: Form (when mode == "form")**
```html
<h1>Team Composition Assistant</h1>
<p>Describe your project and required skills, and we'll suggest an optimal team from your available consultants.</p>

<form method="post" action="/team-builder">
  <fieldset>
    <label for="project-desc"><strong>Project Description</strong></label>
    <textarea id="project-desc" name="project_description" placeholder="E.g., Building a cloud migration platform for an enterprise customer. Need strong AWS expertise, DevOps practices, Python backend, React frontend, and experience managing large distributed teams." rows="6" required></textarea>

    <label for="required-skills"><strong>Required Skills (comma-separated)</strong></label>
    <input type="text" id="required-skills" name="required_skills" placeholder="E.g., Python, AWS, DevOps, React" required />

    <label for="team-size"><strong>Desired Team Size</strong></label>
    <input type="number" id="team-size" name="team_size" value="3" min="1" max="20" required />

    <button type="submit">Get Team Suggestion</button>
  </fieldset>
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
<h1>Team Composition Suggestion</h1>

<div class="suggestion-context">
  <h3>Project Summary</h3>
  <p><strong>Description:</strong> {{ project_description }}</p>
  <p><strong>Required Skills:</strong> {{ required_skills | join(', ') }}</p>
  <p><strong>Suggested Team Size:</strong> {{ suggestion.team | length }} members</p>
</div>

<div class="team-summary">
  <h3>Team Overview</h3>
  <p>{{ suggestion.team_summary }}</p>
</div>

<div class="suggested-team">
  <h3>Suggested Team Members</h3>
  {% for member in suggestion.team %}
    {% set fit_class = 'high-fit' if member.fit_score > 0.85 else 'medium-fit' if member.fit_score > 0.65 else 'low-fit' %}
    <div class="team-member {{ fit_class }}">
      <h4>{{ member.profile_name }} — {{ member.role }}</h4>
      <p><strong>Fit Score:</strong> {{ "%.0f" | format(member.fit_score * 100) }}%</p>
      <p><strong>Reasoning:</strong> {{ member.reasoning }}</p>
      {% if member.gaps %}
        <p><strong>Gaps:</strong> {{ member.gaps }}</p>
      {% endif %}
      <a href="/profile/{{ member.profile_id }}">View Full Profile</a>
    </div>
  {% endfor %}
</div>

<div class="actions">
  <a href="/team-builder" class="btn">← Refine Search</a>
  <!-- Optional: Add export to CSV button similar to search results export -->
</div>
```

**Section 3: Error (when mode == "error")**
```html
<h1>Team Composition Assistant</h1>
<div class="error-message" style="color: red; border: 1px solid red; padding: 10px;">
  <p>{{ error_message }}</p>
</div>
<a href="/team-builder">← Try Again</a>
```

All sections inherit from base.html.
  </action>
  <verify>
    ```bash
    test -f /Users/8jorgee/Desktop/cvsrag/app/templates/team_builder.html && echo "exists" && wc -l /Users/8jorgee/Desktop/cvsrag/app/templates/team_builder.html
    ```
    Expected: File exists with ~120+ lines of Jinja2 template.
  </verify>
  <done>team_builder.html template created with form, results, and error modes.</done>
</task>

<task type="auto">
  <name>Task 4: Add navigation link to Team Builder page in base.html</name>
  <files>app/templates/base.html</files>
  <action>
In base.html (the main navigation/menu section), add a link to /team-builder:

Find the navigation section and add:
```html
<a href="/team-builder">Team Composition</a>
```

Or, if there's a list of links:
```html
<li><a href="/team-builder">Team Composition</a></li>
```

Place it near other feature links (after skill gap analysis would make sense). Keep styling consistent with existing nav items.
  </action>
  <verify>
    ```bash
    grep -n "team-builder\|Team Composition" /Users/8jorgee/Desktop/cvsrag/app/templates/base.html
    ```
    Expected: Link to /team-builder visible in navigation.
  </verify>
  <done>Navigation bar includes link to Team Composition page.</done>
</task>

<task type="auto">
  <name>Task 5: Manual test of team composition with Claude</name>
  <files>app/search/engine.py (test-only)</files>
  <action>
No new files created. This is a verification task.

Manually test the team composition feature:

1. Run the app: `cd /Users/8jorgee/Desktop/cvsrag && python -m uvicorn app.main:app --reload`
2. Navigate to http://localhost:8000/team-builder
3. Fill form with sample data:
   - Project: "Building a financial risk analysis platform. Need strong Python, NumPy/Pandas for data processing, AWS for deployment, and strong communication skills."
   - Skills: "Python, AWS, Finance, DevOps"
   - Team size: 3
4. Submit form
5. Verify Claude suggestions:
   - Team members listed with names and roles
   - Fit scores range from 0-100
   - Reasoning explains why each person is suggested
   - Gaps section identifies skill shortfalls (if any)
   - Team summary provides overall assessment
6. Click "View Full Profile" on a suggested member, verify profile loads
7. Go back and try another search with different parameters

Test error handling:
- Submit with empty project description → error
- Submit with empty skills → error
- Check that Claude JSON parsing handles various formats (with/without markdown fences)

No automated test required (manual verification only).
  </action>
  <verify>
    Manual test via browser:
    1. Open http://localhost:8000/team-builder
    2. Fill in form with sample project data
    3. Click submit
    4. Verify suggested team loads with all fields (name, role, reasoning, fit score, gaps)
    5. Verify team summary text appears
    6. Click profile link and verify full profile page loads
  </verify>
  <done>Team composition suggestion works end-to-end with Claude integration.</done>
</task>

</tasks>

<verification>
1. **Form loads:** Navigate to http://localhost:8000/team-builder, verify form appears with all fields (description textarea, skills input, team size number input).
2. **Form submission:** Fill form and submit, verify Claude response is fetched and parsed successfully.
3. **Results display:** Verify all team member cards appear with names, roles, reasoning, fit scores, and gaps.
4. **Fit scoring:** Verify fit scores range from 0-1 and color-code correctly (green >0.85, yellow 0.65-0.85, orange <0.65).
5. **Navigation:** Verify link to Team Composition appears in main navigation bar.
6. **Error handling:** Submit empty form, verify error messages appear.
7. **Profile links:** Click "View Full Profile" on a suggested member, verify profile detail page loads.
8. **JSON parsing:** Verify Claude responses with various JSON formats (markdown, raw, nested objects) are parsed correctly.
</verification>

<success_criteria>
- [ ] GET /team-builder shows form with project description, required skills, and team size inputs
- [ ] POST /team-builder accepts form data and calls Claude suggestion engine
- [ ] Claude suggestion returns team member list with roles, reasoning, gaps, and fit scores
- [ ] Results page displays suggested team with color-coded fit scores
- [ ] Team summary provides overall team assessment
- [ ] Navigation bar includes link to Team Composition page
- [ ] Links to full profiles work from team suggestion page
- [ ] Error handling for invalid inputs and Claude failures
</success_criteria>

<output>
After completion, create `.planning/03-advanced-features/03-03-SUMMARY.md` with:
- Claude prompt and response format
- JSON parsing strategy for team suggestions
- Example team compositions (anonymized)
- Performance notes (Claude API call time)
- Edge cases and error handling
</output>
