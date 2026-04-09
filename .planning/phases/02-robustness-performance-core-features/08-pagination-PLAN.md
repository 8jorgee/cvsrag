---
phase: 02-robustness-performance-core-features
plan: 08
type: execute
wave: 3
depends_on: [02-01, 02-02]
files_modified:
  - app/models.py
  - app/search/engine.py
  - app/main.py
  - app/templates/partials/results.html
  - app/templates/search.html
autonomous: true
requirements: [SEARCH-01]

must_haves:
  truths:
    - "Search results are paginated with page_size=10 (Load More pattern)"
    - "Page 2 returns different profiles than page 1 when result set > 10"
    - "UI shows 'Showing N of M' and Load More button when has_more=True"
  artifacts:
    - path: app/models.py
      provides: "SearchQuery and SearchResult models with pagination fields"
      min_lines: 10
    - path: app/search/engine.py
      provides: "search() accepts page and page_size parameters, returns sliced results"
      min_lines: 10
    - path: app/main.py
      provides: "POST /search endpoint accepts page Form field"
      min_lines: 5
    - path: app/templates/partials/results.html
      provides: "Load More button with HTMX hx-swap='beforeend' when has_more=True"
      min_lines: 5
  key_links:
    - from: app/models.py
      to: app/search/engine.py
      via: "page, page_size, total_count, has_more fields"
      pattern: "page: int"
    - from: app/templates/partials/results.html
      to: app/templates/search.html
      via: "HTMX Load More button"
      pattern: "hx-swap=\"beforeend\""
---

<objective>
Implement pagination for search results using "Load More" pattern with HTMX.

Purpose: Return results in chunks of 10, allowing users to load more on demand without page refresh.

Output:
- SearchQuery and SearchResult models include pagination fields
- engine.search() supports page/page_size parameters
- /search endpoint accepts page Form field
- results.html displays Load More button when more results available
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/phases/02-robustness-performance-core-features/02-CONTEXT.md
@.planning/phases/02-robustness-performance-core-features/02-RESEARCH.md

From CONTEXT.md, SEARCH-01:
- engine.search() accepts page: int = 1 and page_size: int = 10
- Returns slice [(page-1)*page_size : page*page_size] from full candidate list
- /search endpoint accepts page Form field (default 1)
- Results partial includes "Load More" button when len(results) == page_size
- Total count returned so UI can show "Showing N of M"
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add pagination fields to models.py (SearchQuery, SearchResult)</name>
  <files>app/models.py</files>
  <action>
In app/models.py, update the models:

1. SearchQuery: Add pagination field:
```python
class SearchQuery(BaseModel):
    query: str
    skills: list[str] = []
    certifications: list[str] = []
    # ... existing fields ...
    page: int = 1  # Add this
```

2. SearchResult: Add pagination metadata:
```python
class SearchResult(BaseModel):
    profile: ConsultantProfile
    score: float
    # ... existing fields ...
    total_count: int  # Total number of results
    has_more: bool    # True if more results available
    page: int         # Current page
    page_size: int    # Results per page
```

Or if SearchResult is not a model, create one that wraps the paginated response.

Alternative: If you have a response wrapper, update it to include:
- results: list[SearchResult]
- total_count: int
- page: int
- has_more: bool

Use Field(default=1) for defaults.
  </action>
  <verify>
    <automated>pytest tests/unit/test_pagination.py::test_page_size_10 tests/unit/test_pagination.py::test_total_count_accurate tests/unit/test_pagination.py::test_has_more_flag -xvs</automated>
  </verify>
  <done>
SearchQuery and SearchResult models include pagination fields (page, page_size, total_count, has_more), test cases pass
  </done>
</task>

<task type="auto">
  <name>Task 2: Implement pagination in engine.search()</name>
  <files>app/search/engine.py</files>
  <action>
In app/search/engine.py, update the `search()` function signature:

Change from:
```python
def search(query: str, filters: SearchQuery, ...) -> list[SearchResult]:
```

To:
```python
def search(query: str, filters: SearchQuery, page: int = 1, page_size: int = 10, ...) -> dict:
```

Inside the function:
1. Perform normal search to get all candidate results (as currently implemented)
2. Calculate pagination metadata:
   ```python
   total_count = len(candidates)
   start_idx = (page - 1) * page_size
   end_idx = start_idx + page_size
   paginated_results = candidates[start_idx:end_idx]
   has_more = len(candidates) > end_idx
   ```
3. Return a dict (or structured response):
   ```python
   return {
       "results": paginated_results,
       "total_count": total_count,
       "page": page,
       "page_size": page_size,
       "has_more": has_more
   }
   ```

Validation: Ensure page >= 1, page_size > 0 (add assertions or validation).
  </action>
  <verify>
    <automated>pytest tests/unit/test_pagination.py -xvs</automated>
  </verify>
  <done>
engine.search() accepts page/page_size parameters, returns paginated slice with total_count and has_more, all test cases pass
  </done>
</task>

<task type="auto">
  <name>Task 3: Update /search endpoint in main.py to handle page parameter</name>
  <files>app/main.py</files>
  <action>
In app/main.py, locate the `/search` POST endpoint.

Update it to:
1. Accept `page: int = Form(default=1)` from form data
2. Pass page and page_size to engine.search():
   ```python
   result = engine.search(
       query=search_query.query,
       filters=search_query,
       page=page,
       page_size=10
   )
   ```
3. Pass pagination metadata to template:
   ```python
   return templates.TemplateResponse("search.html", {
       "request": request,
       "results": result["results"],
       "total_count": result["total_count"],
       "page": result["page"],
       "has_more": result["has_more"],
       ...
   })
   ```

Or if using a partial response pattern, render the results partial with pagination context.
  </action>
  <verify>
    <automated>grep -n "page.*Form" app/main.py</automated>
  </verify>
  <done>
/search endpoint accepts page Form parameter, passes to engine.search(), renders pagination context
  </done>
</task>

<task type="auto">
  <name>Task 4: Add Load More button to results.html partial</name>
  <files>app/templates/partials/results.html</files>
  <action>
In app/templates/partials/results.html, after the results list, add Load More button:

```html
{% if has_more %}
  <button
    id="load-more"
    hx-post="/search"
    hx-target="#results"
    hx-swap="beforeend"
    hx-vals='{"page": {{ page + 1 }} }'
    class="btn btn-primary"
  >
    Load More (Showing {{ results|length }} of {{ total_count }})
  </button>
{% else %}
  {% if total_count > 0 %}
    <p class="text-muted">Showing all {{ total_count }} results</p>
  {% endif %}
{% endif %}
```

Key points:
- `hx-post="/search"` — submit search form again
- `hx-target="#results"` — target results container (must have id="results")
- `hx-swap="beforeend"` — append new results below existing (Load More pattern)
- `hx-vals` — pass incremented page number
- Show count: "Showing N of M"

Ensure the results container in search.html has id="results".
  </action>
  <verify>
    <automated>grep -n "hx-swap=\"beforeend\"" app/templates/partials/results.html</automated>
  </verify>
  <done>
Load More button added with HTMX hx-swap='beforeend', passes incremented page, shows result count
  </done>
</task>

<task type="auto">
  <name>Task 5: Update search.html to include results container and pagination count</name>
  <files>app/templates/search.html</files>
  <action>
In app/templates/search.html, verify/add:

1. Results container with id="results":
```html
<div id="results">
  {% include "partials/results.html" %}
</div>
```

2. Make sure the form submits to POST /search without page_size override:
```html
<form id="search-form" hx-post="/search" hx-target="#results" hx-swap="innerHTML">
  <!-- form fields -->
</form>
```

Note: Initial search should not use hx-swap="beforeend" (that's only for Load More). Set hx-swap="innerHTML" to replace results on first search.

If using HTMX, ensure that clicking Load More button keeps the search filters (the hx-post="/search" should re-submit the entire form, or pass hidden fields for active filters).

For simplicity: The Load More button in results.html includes hidden fields or posts back with the same form data + incremented page.
  </action>
  <verify>
    <automated>grep -n "id=\"results\"" app/templates/search.html</automated>
  </verify>
  <done>
search.html has results container (id="results"), form configured for HTMX with correct targets/swaps
  </done>
</task>

</tasks>

<verification>
Run pagination tests:
- `pytest tests/unit/test_pagination.py -xvs` should pass all 3 tests (page_size, total_count, has_more)
- Manual UI test: Search for a query that returns >10 results, verify page 1 shows 10, Load More button appears, clicking Load More appends next 10 below (not replacing)
</verification>

<success_criteria>
- SearchQuery and SearchResult models include page, page_size, total_count, has_more fields
- engine.search() accepts and uses page/page_size parameters, returns paginated slice
- /search endpoint accepts page Form field (default 1), passes to engine.search()
- results.html displays Load More button when has_more=True with hx-swap="beforeend"
- search.html has results container (id="results") for HTMX targeting
- All 3 pagination test cases pass
</success_criteria>

<output>
After completion, create `.planning/phases/02-robustness-performance-core-features/02-08-SUMMARY.md` documenting:
- Pagination fields added to models
- engine.search() slicing logic
- /search endpoint Form parameter handling
- Load More button implementation
- Test results confirming all 3 pagination tests pass
</output>
