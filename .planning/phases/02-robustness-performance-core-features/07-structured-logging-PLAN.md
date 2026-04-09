---
phase: 02-robustness-performance-core-features
plan: 07
type: execute
wave: 2
depends_on: [02-01]
files_modified:
  - app/main.py
  - app/config.py
  - app/db.py
  - app/search/engine.py
  - app/search/embeddings.py
  - app/search/filters.py
  - app/ingestion/profile_builder.py
  - app/ingestion/availability.py
  - scripts/ingest_cvs.py
  - requirements.txt
autonomous: true
requirements: [FEAT-10]

must_haves:
  truths:
    - "All Python logging calls use structlog.get_logger() instead of logging.getLogger()"
    - "JSON output in production mode (LOG_FORMAT=json), colored console in dev"
    - "structlog is installed and configured at application startup"
  artifacts:
    - path: app/main.py
      provides: "structlog configuration (JSON/console renderer based on LOG_FORMAT env var)"
      min_lines: 10
    - path: app/config.py
      provides: "LOG_FORMAT setting (default 'console', override with 'json')"
      min_lines: 2
    - path: requirements.txt
      provides: "structlog==24.1.0 dependency"
      min_lines: 1
  key_links:
    - from: app/main.py
      to: tests/unit/test_logging.py
      via: "structlog configuration"
      pattern: "structlog.configure"
---

<objective>
Replace all logging.getLogger() calls with structlog.get_logger() throughout the application.

Purpose: Structured JSON logging in production, colored console in development. Improves log aggregation, filtering, and debugging.

Output:
- structlog configured at app startup in main.py
- All Python modules use structlog.get_logger()
- JSON output in production (LOG_FORMAT=json), colored console otherwise
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/phases/02-robustness-performance-core-features/02-CONTEXT.md
@.planning/phases/02-robustness-performance-core-features/02-RESEARCH.md

From CONTEXT.md, FEAT-10:
- Replace all logging.getLogger() with structlog.get_logger()
- Config: JSON renderer in production (LOG_FORMAT=json), colored console in dev
- Files: All app/**/*.py + scripts/ingest_cvs.py; add structlog to requirements.txt

Note: structlog already added to requirements.txt in Plan 01 (test infrastructure).
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add LOG_FORMAT configuration to app/config.py</name>
  <files>app/config.py</files>
  <action>
In app/config.py Settings class, add:

```python
log_format: str = Field(
    default="console",
    description="Log format: 'json' for production, 'console' for development"
)
```

Or simpler, without Field:
```python
log_format: str = "console"  # Override with LOG_FORMAT env var
```

This allows LOG_FORMAT=json to be set in .env or at runtime.
  </action>
  <verify>
    <automated>python -c "from app.config import settings; print(settings.log_format)"</automated>
  </verify>
  <done>
LOG_FORMAT setting added to Settings, defaults to 'console', environment override works
  </done>
</task>

<task type="auto">
  <name>Task 2: Configure structlog in app/main.py at startup</name>
  <files>app/main.py</files>
  <action>
In app/main.py, add structlog configuration code before app initialization (at module level or in a startup function):

```python
import structlog
from app.config import settings

def configure_logging():
    """Configure structlog based on LOG_FORMAT setting."""
    if settings.log_format == "json":
        # Production: JSON renderer
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Development: Colored console renderer
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.dev.ConsoleRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

# Call at app startup
configure_logging()

# Create app
app = FastAPI(...)
```

Imports: `import structlog`, `from app.config import settings`
  </action>
  <verify>
    <automated>pytest tests/unit/test_logging.py::test_json_output tests/unit/test_logging.py::test_console_colored -xvs</automated>
  </verify>
  <done>
structlog configured in main.py, JSON and console renderers working, both test cases pass
  </done>
</task>

<task type="auto">
  <name>Task 3: Replace logging.getLogger() with structlog.get_logger() in all app/ modules</name>
  <files>app/db.py, app/search/engine.py, app/search/embeddings.py, app/search/filters.py, app/ingestion/profile_builder.py, app/ingestion/availability.py</files>
  <action>
For each Python file in app/ (and scripts/ingest_cvs.py):

1. Find all occurrences of `logging.getLogger()` using grep:
   ```bash
   grep -n "logging.getLogger()" {file}
   ```

2. Replace with `structlog.get_logger()`:
   - Remove or update any `import logging` lines
   - Add `import structlog`
   - Replace all `logger = logging.getLogger(__name__)` with `logger = structlog.get_logger()`

3. Update any logging calls that use old-style formatting:
   - OLD: `logger.info("Message with %s", variable)`
   - NEW: `logger.info("Message with", variable=variable)` (structlog uses keyword arguments)

4. Check for any print() calls that should be logger calls (convert if in critical paths)

Affected files (in order of importance):
- app/main.py (already handled in Task 2)
- app/db.py (import, replace getLogger, update any logging)
- app/search/engine.py (import, replace getLogger, update any logging)
- app/search/embeddings.py (import, replace getLogger, update any logging)
- app/search/filters.py (if it has logging)
- app/ingestion/profile_builder.py (import, replace getLogger, update any logging)
- app/ingestion/availability.py (if it has logging)
- scripts/ingest_cvs.py (import, replace getLogger, update any logging)

For brevity in this plan: focus on the core files that already have logging statements. Skip files with no logging.

Update all logger.info/warning/error/debug calls to use keyword arguments (structlog style).
  </action>
  <verify>
    <automated>grep -r "logging.getLogger" app/ scripts/ | grep -v "__pycache__" | wc -l</automated>
  </verify>
  <done>
All logging.getLogger() calls replaced with structlog.get_logger(), no "logging.getLogger" found in production code
  </done>
</task>

</tasks>

<verification>
Run logging tests:
- `pytest tests/unit/test_logging.py -xvs` should pass both JSON and console output tests
- Verify JSON output is valid (parseable with json.loads)
- Verify console output contains color codes (ANSI escapes)
- Run app with LOG_FORMAT=json and check that logs are valid JSON
- Run app with LOG_FORMAT=console and check that logs are colored/readable
</verification>

<success_criteria>
- LOG_FORMAT setting in Settings (default "console")
- structlog.configure() called in main.py at startup
- JSON renderer configured for production (LOG_FORMAT=json)
- Console renderer configured for development (default)
- All logging.getLogger() calls replaced with structlog.get_logger() across all modules
- All logger.info/warning/error calls use keyword arguments (structlog style)
- Both test cases pass (JSON output valid, console output colored)
</success_criteria>

<output>
After completion, create `.planning/phases/02-robustness-performance-core-features/02-07-SUMMARY.md` documenting:
- structlog configuration in main.py
- LOG_FORMAT setting in config.py
- List of all modules updated with structlog
- Test results confirming JSON and console output formats
</output>
