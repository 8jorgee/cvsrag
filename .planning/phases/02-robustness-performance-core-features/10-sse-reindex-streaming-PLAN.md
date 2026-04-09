---
phase: 02-robustness-performance-core-features
plan: 10
type: execute
wave: 3
depends_on: [02-01, 02-03, 02-04, 02-06]
files_modified:
  - app/main.py
  - scripts/ingest_cvs.py
  - app/templates/admin.html
autonomous: true
requirements: [ROB-05]

must_haves:
  truths:
    - "Re-index runs as a background task (non-blocking), admin UI does not freeze"
    - "Admin sees live per-CV progress without page refresh via SSE"
    - "Final summary includes counts: processed, skipped, errors"
  artifacts:
    - path: app/main.py
      provides: "GET /admin/reindex-stream endpoint with StreamingResponse"
      min_lines: 20
    - path: scripts/ingest_cvs.py
      provides: "ingest_cvs() refactored to yield progress events"
      min_lines: 10
    - path: app/templates/admin.html
      provides: "EventSource client replaces fetch-based POST trigger"
      min_lines: 10
  key_links:
    - from: app/main.py
      to: scripts/ingest_cvs.py
      via: "asyncio.to_thread() calls ingest_cvs()"
      pattern: "asyncio.to_thread"
    - from: app/templates/admin.html
      to: app/main.py
      via: "EventSource('/admin/reindex-stream')"
      pattern: "EventSource"
---

<objective>
Implement Server-Sent Events (SSE) streaming for re-index progress on admin panel.

Purpose: Prevent timeout on large ingestion runs and give admin live feedback without page refresh.

Output:
- GET /admin/reindex-stream endpoint that streams progress as SSE events
- ingest_cvs() refactored to yield progress callbacks
- admin.html replaces fetch POST with EventSource client
- Per-file events: {file, status, count}; final event: {done, processed, skipped, errors}
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/phases/02-robustness-performance-core-features/02-CONTEXT.md
@.planning/phases/02-robustness-performance-core-features/02-RESEARCH.md

From CONTEXT.md, ROB-05:
- New endpoint `GET /admin/reindex-stream?force=true|false` using `StreamingResponse(media_type="text/event-stream")`
- Run ingestion in-process (import and call `ingest_cvs()`) inside a thread (`asyncio.to_thread`) while yielding SSE events
- Per-file events: `data: {"file": "john.pptx", "status": "processing|ok|error", "count": N}\n\n`
- Final event: `data: {"done": true, "processed": N, "skipped": N, "errors": N}\n\n`
- Admin UI: replace `triggerReindex()` fetch call with `EventSource('/admin/reindex-stream?force=...')` in `admin.html`
- Keep old `/admin/reindex` POST for backward compatibility (still works, just no streaming)

From RESEARCH.md, Pattern 5: SSE Progress Streaming (ROB-05):
- `StreamingResponse` with `media_type="text/event-stream"`
- `asyncio.to_thread()` runs sync ingestion code
- Yields events as generators or async generators
</context>

<tasks>

<task type="auto">
  <name>Task 1: Refactor ingest_cvs() to support progress callbacks or yield</name>
  <files>scripts/ingest_cvs.py</files>
  <action>
Refactor ingest_cvs() to support progress tracking. Two approaches:

**Approach A: Callback-based (simpler for SSE)**
Add optional `progress_callback` parameter:

```python
def ingest_cvs(
    cv_dir: str = settings.cv_dir,
    availability_csv: str = settings.availability_csv,
    force: bool = False,
    progress_callback: callable = None  # Add this
) -> dict:
    """Ingest CVs with optional progress callback."""
    processed = 0
    skipped = 0
    errors = 0

    # ... existing logic ...

    for filepath in cv_files:
        try:
            # ... process file ...
            processed += 1
            if progress_callback:
                progress_callback({
                    "file": os.path.basename(filepath),
                    "status": "ok",
                    "count": processed
                })
        except Exception as e:
            errors += 1
            if progress_callback:
                progress_callback({
                    "file": os.path.basename(filepath),
                    "status": "error",
                    "error": str(e)
                })

    if progress_callback:
        progress_callback({
            "done": True,
            "processed": processed,
            "skipped": skipped,
            "errors": errors
        })

    return {"processed": processed, "skipped": skipped, "errors": errors}
```

**Approach B: Generator-based (more Pythonic)**
Refactor as generator:

```python
def ingest_cvs_generator(...):
    """Ingest CVs, yielding progress events."""
    # ... setup ...
    for filepath in cv_files:
        try:
            # ... process ...
            yield {"file": basename, "status": "ok", "count": processed}
        except Exception as e:
            yield {"file": basename, "status": "error", "error": str(e)}

    yield {"done": True, "processed": processed, ...}
```

For simplicity in this task, use Approach A (callback). Keep the original ingest_cvs() function callable as a CLI script (main block unchanged).

Import: `import os` for basename
  </action>
  <verify>
    <automated>grep -n "progress_callback" scripts/ingest_cvs.py | head -3</automated>
  </verify>
  <done>
ingest_cvs() refactored to accept progress_callback parameter, yields per-file and final summary events
  </done>
</task>

<task type="auto">
  <name>Task 2: Implement GET /admin/reindex-stream endpoint in main.py</name>
  <files>app/main.py</files>
  <action>
In app/main.py, add new endpoint:

```python
import asyncio
import json
from fastapi.responses import StreamingResponse
from scripts.ingest_cvs import ingest_cvs

@app.get("/admin/reindex-stream")
async def reindex_stream(request: Request, force: bool = False):
    """
    SSE endpoint for streaming re-index progress.
    Runs ingest_cvs in a background thread and yields SSE events.
    """
    async def event_generator():
        # Run ingest_cvs in thread pool (avoid blocking event loop)
        events = []

        def collect_event(event: dict):
            events.append(event)

        def stream_events():
            # Call ingest_cvs with callback
            ingest_cvs(
                cv_dir=settings.cv_dir,
                availability_csv=settings.availability_csv,
                force=force,
                progress_callback=collect_event
            )
            return events

        # Execute in thread
        all_events = await asyncio.to_thread(stream_events)

        # Yield each event as SSE data
        for event in all_events:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

Key points:
- `@app.get()` method (not POST; client initiates with EventSource)
- `media_type="text/event-stream"` tells browser to expect SSE
- `asyncio.to_thread()` runs sync ingest_cvs without blocking event loop
- SSE format: `data: {json}\n\n` (two newlines to delimit events)

Import: `import asyncio`, `import json`, `from fastapi.responses import StreamingResponse`

Keep old `/admin/reindex` POST endpoint for backward compatibility (still works with POST trigger).
  </action>
  <verify>
    <automated>pytest tests/integration/test_sse.py::test_reindex_stream_content_type tests/integration/test_sse.py::test_sse_json_format -xvs</automated>
  </verify>
  <done>
/admin/reindex-stream endpoint created, returns SSE events with correct media type, test cases pass
  </done>
</task>

<task type="auto">
  <name>Task 3: Update admin.html to use EventSource instead of fetch POST</name>
  <files>app/templates/admin.html</files>
  <action>
In app/templates/admin.html, locate the current re-index button and trigger function (likely `triggerReindex()`).

Replace fetch POST trigger with EventSource client:

Current (fetch POST):
```html
<button onclick="triggerReindex()">Re-index CVs</button>

<script>
async function triggerReindex() {
  const response = await fetch('/admin/reindex', {
    method: 'POST',
    headers: { 'X-CSRF-Token': getCsrfToken() }
  });
  // ... handle response ...
}
</script>
```

New (EventSource):
```html
<button onclick="triggerReindex()">Re-index CVs</button>
<div id="log-box" style="border: 1px solid #ccc; height: 300px; overflow-y: auto; padding: 10px; background: #f5f5f5;">
  <p class="text-muted">Re-index log appears here...</p>
</div>

<script>
function triggerReindex() {
  const logBox = document.getElementById('log-box');
  logBox.innerHTML = '<p style="color: blue;">Starting re-index...</p>';

  const eventSource = new EventSource('/admin/reindex-stream?force=false');

  eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);

    if (data.done) {
      // Final summary
      logBox.innerHTML += `
        <p style="color: green;">Done! Processed: ${data.processed}, Skipped: ${data.skipped}, Errors: ${data.errors}</p>
      `;
      eventSource.close();
    } else {
      // Per-file event
      const status = data.status === 'ok' ? '✓' : '✗';
      const color = data.status === 'ok' ? 'green' : 'red';
      logBox.innerHTML += `
        <p style="color: ${color};">[${status}] ${data.file}</p>
      `;
    }

    // Auto-scroll to bottom
    logBox.scrollTop = logBox.scrollHeight;
  };

  eventSource.onerror = function() {
    logBox.innerHTML += '<p style="color: red;">Error: Connection lost</p>';
    eventSource.close();
  };
}
</script>
```

Ensure:
- Log box HTML element exists (id="log-box")
- EventSource client handles onmessage and onerror
- Events are parsed as JSON
- Final event closes connection

Optional: Add spinner/loading indicator while re-index is in progress
  </action>
  <verify>
    <automated>grep -n "EventSource" app/templates/admin.html</automated>
  </verify>
  <done>
admin.html EventSource client replaces fetch POST, logs per-file progress, handles final summary and errors
  </done>
</task>

</tasks>

<verification>
Run SSE tests:
- `pytest tests/integration/test_sse.py -xvs` should pass both tests (content type, JSON format)
- Manual UI test: Open /admin panel, click Re-index, observe log box updates line-by-line as files are processed (live streaming without refresh)
- Verify final summary appears with counts (processed, skipped, errors)
</verification>

<success_criteria>
- ingest_cvs() accepts progress_callback parameter and invokes it for each file and final summary
- GET /admin/reindex-stream endpoint created, returns StreamingResponse with text/event-stream media type
- SSE events are valid JSON format: {file, status, count} for per-file; {done, processed, skipped, errors} for final
- admin.html has EventSource client listening on /admin/reindex-stream
- Log box updates line-by-line as SSE events arrive (no page refresh)
- Both SSE test cases pass
</success_criteria>

<output>
After completion, create `.planning/phases/02-robustness-performance-core-features/02-10-SUMMARY.md` documenting:
- progress_callback integration in ingest_cvs()
- /admin/reindex-stream endpoint implementation
- EventSource client in admin.html
- Test results confirming SSE content type and JSON format
- Manual UI verification of live streaming progress
</output>
