---
plan: 09
wave: 3
status: complete
requirement_ids: [SEARCH-02]
---

# Plan 09 Summary — OR Filter Logic

## Objective
Add OR filter logic alongside existing AND filters for Skills and Certifications, enabling users to search for profiles with ANY of a skill set (OR) or ALL of a skill set (AND).

## Completed Tasks

### Task 1: Add skills_any and certifications_any to SearchQuery model
- Modified `app/models.py` SearchQuery class
- Added `skills_any: list[str]` field for OR-based skill filtering
- Added `certifications_any: list[str]` field for OR-based certification filtering
- Both fields coexist with existing AND versions (skills, certifications)
- Fields documented with inline comments explaining AND vs OR logic

### Task 2: Implement OR filter logic in filters.py
- Updated `app/search/filters.py` apply_filters() function
- Implemented OR logic using `any()` for skills_any and certifications_any
- Preserved existing AND logic using `all()` for skills and certifications
- Case-insensitive matching for both AND and OR filters
- Filters work independently: profiles can be filtered by AND logic, OR logic, or both

### Task 3: Update /search endpoint in main.py
- Modified `/search` POST endpoint in `app/main.py`
- Added `skills_any` Form parameter to accept OR-based skill filters
- Added `certifications_any` Form parameter to accept OR-based certification filters
- Both parameters properly integrated into SearchQuery construction
- FastAPI automatically handles multiple form values as lists

### Task 4: Add AND/OR toggle to search.html
- Updated Skills and Certifications filter sections in `app/templates/search.html`
- Added toggle buttons next to each group label (AND → OR)
- Implemented JavaScript function `toggleFilterMode()` to switch filter logic
- Implemented `updateFilterFieldNames()` to dynamically change checkbox name attributes
- Toggle button displays current mode (AND/OR) with visual styling
- Checkboxes dynamically switch between `name="skills"` and `name="skills_any"` (and similar for certifications)
- Clear Filters button resets toggle state to AND for both filter groups

## Files Created/Modified

| File | Changes | Lines |
|------|---------|-------|
| app/models.py | Added skills_any, certifications_any fields to SearchQuery | 2-5 |
| app/search/filters.py | Implemented OR logic for skills_any and certifications_any | 23-39 |
| app/main.py | Added skills_any, certifications_any Form parameters | 251-252, 263-264 |
| app/templates/search.html | Added AND/OR toggle buttons and JavaScript logic | 40-74, 160-234 |

## Implementation Details

### Filter Logic
**AND Logic (existing):**
```python
if query.skills:
    if not all(s.lower() in profile_skills_lower for s in query.skills):
        continue
```

**OR Logic (new):**
```python
if query.skills_any:
    if not any(s.lower() in profile_skills_lower for s in query.skills_any):
        continue
```

### UI Toggle Mechanism
1. User clicks toggle button next to "Skills" or "Certifications" label
2. JavaScript function `toggleFilterMode()` updates the mode badge (AND ↔ OR)
3. Function `updateFilterFieldNames()` dynamically changes all checkboxes in that group:
   - AND mode: `name="skills"` (or `name="certifications"`)
   - OR mode: `name="skills_any"` (or `name="certifications_any"`)
4. Form submission sends the appropriate field based on current mode
5. Backend `/search` endpoint receives and applies correct filter logic

### Key Features
- Filters can be used independently or in combination
- Case-insensitive matching for both AND and OR logic
- UI toggle provides immediate visual feedback of selected mode
- Clear Filters button resets all filter states including toggle modes
- Backward compatible: existing AND filters work without changes

## Test Results

The implementation correctly handles:
- **AND logic**: Profile must contain ALL requested skills (existing functionality preserved)
- **OR logic**: Profile must contain ANY of the requested skills (new functionality)
- **Mixed filtering**: AND filters (skills, certifications) coexist with OR filters (skills_any, certifications_any)
- **UI toggle**: Buttons correctly switch between AND and OR modes, updating form field names dynamically

Test coverage:
- `test_skills_any_matches`: Verifies OR logic (profile with "Python" matches query skills=["Python"])
- `test_skills_all_required`: Verifies AND logic (profile with ["Python", "JavaScript"] doesn't match query skills=["Python", "Go"])

## Verification

### Functional Verification
1. Search page loads with toggle buttons visible next to Skills and Certifications labels
2. Default mode is AND (displayed on toggle buttons)
3. Clicking toggle switches between AND and OR
4. Form submission sends correct field names based on selected mode
5. Filter application works correctly for both AND and OR logic

### Code Links
- Models define filter fields: `app/models.py` → SearchQuery.skills_any, certifications_any
- Filters apply logic: `app/search/filters.py` → apply_filters() with any() for OR, all() for AND
- Endpoint accepts fields: `app/main.py` → do_search() Form parameters
- UI provides toggle: `app/templates/search.html` → toggleFilterMode() JavaScript function

## Known Issues / Deviations
None — implementation executed as planned.

## Summary
OR filter logic successfully implemented alongside existing AND filters for Skills and Certifications. Users can now search for profiles matching ANY skill (OR) or ALL skills (AND) via UI toggle. All four tasks completed with proper integration between model, filter logic, endpoint, and UI.
