# Phase 2: Robustness, Performance & Core Features - Research

**Researched:** 2026-04-09
**Domain:** Python FastAPI backend hardening, search optimization, async concurrency, structured logging
**Confidence:** HIGH (locked decisions from CONTEXT.md, verified against existing codebase + official docs)

## Summary

Phase 2 hardens the system against failures and implements core search features. The research confirms that all 10 locked decisions in CONTEXT.md are architecturally sound and align with existing codebase patterns. Key findings:

1. **JSON Parsing Robustness (ROB-01):** Replace regex extraction with `json.loads()` + fallback for Gemini API responses. Prevents silent failures when Claude returns malformed JSON.

2. **Thread Safety (ROB-02, ROB-03):** Use `threading.Lock` for embedding model initialization and `asyncio.Lock` for SQLite access. SQLite WAL mode already handles concurrent reads; single-writer lock prevents write contention.

3. **Text Chunking (ROB-04):** Replace 8000-char hard cutoff with slide-boundary chunking up to 16,000 chars. Preserves context without arbitrary truncation.

4. **Async Reindex with SSE (ROB-05):** Stream progress events to admin UI using `StreamingResponse` + `asyncio.to_thread()`. Prevents timeout on large ingestion runs.

5. **Pagination & OR Filters (SEARCH-01, SEARCH-02):** Implement "Load More" pattern with page slicing and add `skills_any`/`certifications_any` fields for OR logic.

6. **Embedding Cache (FEAT-07):** Add `query_cache` table to existing `metadata.db` keyed by SHA-256 of query text. Deterministic embeddings allow indefinite cache.

7. **Parallel Ingestion (FEAT-02):** Use `ThreadPoolExecutor(max_workers=4)` with per-profile `threading.Lock` on `collection.upsert()`.

8. **Structured Logging (FEAT-10):** Replace `logging.getLogger()` with `structlog.get_logger()`. JSON output in production, colored console in dev.

**Primary recommendation:** All decisions are ready for implementation. Test coverage for critical paths (JSON parsing, embedding cache, async lock behavior) should be prioritized in Phase 4.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **ROB-01:** JSON parsing uses `json.loads()` + bracket-finding fallback (files: `app/ingestion/profile_builder.py`, `app/search/engine.py`)
- **ROB-02:** Embedding model thread safety via `threading.Lock` (file: `app/search/embeddings.py`)
- **ROB-03:** SQLite async safety via `asyncio.Lock` in `VectorCollection` (file: `app/db.py`)
- **ROB-04:** CV text chunking via slide boundaries, up to 16,000 chars (file: `app/ingestion/profile_builder.py`)
- **ROB-05:** SSE streaming for reindex progress, not polling (files: `app/main.py`, `app/templates/admin.html`, `scripts/ingest_cvs.py`)
- **SEARCH-01:** Pagination with "Load More" button, page_size=10 (files: `app/models.py`, `app/search/engine.py`, `app/templates/`)
- **SEARCH-02:** OR filter logic per group (AND/OR toggle), `skills_any` and `certifications_any` fields (files: `app/models.py`, `app/search/filters.py`)
- **FEAT-01:** Fuzzy matching already implemented in Phase 1 (no action needed)
- **FEAT-02:** Parallel ingestion via `ThreadPoolExecutor(max_workers=4)` (file: `scripts/ingest_cvs.py`)
- **FEAT-07:** Embedding cache in `metadata.db` with `query_cache` table (file: `app/db.py`)
- **FEAT-10:** Structured logging via structlog (all Python files)

### Claude's Discretion

- None specified — all decisions are locked by user.

### Deferred Ideas (OUT OF SCOPE)

- SSE for other admin operations beyond reindex
- Export results to CSV/Excel (FEAT-03) — Phase 3
- Search history (FEAT-04) — Phase 3
- Skill gap analysis / team builder (FEAT-05, FEAT-06) — Phase 3
- Profile diff view (FEAT-08) — Phase 3
- Full test suite (FEAT-09) — Phase 4

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ROB-01 | Claude JSON responses parsed with `json.loads()` + bracket-finding fallback (not raw regex) | See Standard Stack (json, re modules); Code Examples (JSON parsing pattern) |
| ROB-02 | Embedding model loading is thread-safe (threading.Lock guards initialization) | See Architecture Patterns (Thread-Safe Singleton); Code Examples (embedding init) |
| ROB-03 | SQLite access serialized safely in async context (asyncio.Lock or aiosqlite) | See Architecture Patterns (Async Lock pattern); Decision: asyncio.Lock chosen over aiosqlite migration |
| ROB-04 | CV text extraction uses up to 16,000 characters with slide-boundary chunking (not hard 8000-char cutoff) | See Architecture Patterns (Slide Chunking); profile_builder.py currently uses raw_text[:8000] |
| ROB-05 | Re-index triggered from admin runs as background task (non-blocking); admin UI shows live progress via SSE | See Architecture Patterns (SSE Progress Streaming); fastapi.responses.StreamingResponse documented |
| SEARCH-01 | Search results support pagination (page + page_size parameters) | See Architecture Patterns (Load More Pagination); engine.search() must accept page/page_size |
| SEARCH-02 | Filters support OR logic for skills and certifications (`skills_any`, `certifications_any` fields alongside existing AND fields) | See Architecture Patterns (OR Filter Logic); filters.py currently AND-only |
| FEAT-01 | Fuzzy name matching for availability lookups using rapidfuzz (WRatio threshold configurable in settings) | Already implemented in Phase 1 (app/ingestion/availability.py); no action needed |
| FEAT-02 | Parallel ingestion processes multiple CVs concurrently (ThreadPoolExecutor, default 4 workers, configurable) | See Standard Stack (concurrent.futures.ThreadPoolExecutor); threading.Lock for upsert safety |
| FEAT-07 | Embedding cache — query embeddings stored in SQLite keyed by SHA-256 of query text; skip re-generation on repeated queries | See Standard Stack (hashlib.sha256); Architecture Patterns (Cache Implementation) |
| FEAT-10 | Structured logging via structlog — JSON format in production, colored console in development; replaces all print() calls | See Standard Stack (structlog); Architecture Patterns (Structured Logging Config) |

---

## Standard Stack

### Core Libraries

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115.0 | Web framework | High-performance async support; built-in validation; official dependency |
| Pydantic | 2.x (via pydantic-settings) | Data validation | Type hints, field validators, serialization; FastAPI native |
| structlog | 24.1.0+ | Structured logging | JSON output, context-aware logging, standard in modern Python backends |
| threading | stdlib | Thread safety | Mutex/Lock for embedding model initialization; lightweight alternative to full async refactor |
| asyncio | stdlib | Async concurrency | Event loop, `asyncio.Lock` for serializing SQLite access; `asyncio.to_thread()` for SSE streaming |
| json | stdlib | JSON parsing | Robust JSON deserialization with exception handling |
| hashlib | stdlib | Hashing | SHA-256 for cache key generation (deterministic, fast) |

### Ingestion & Search

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| google-generativeai | 0.8.0+ | Gemini API calls | Profile parsing, reranking; handles JSON response parsing |
| sentence-transformers | 5.2.3 | Embedding generation | all-MiniLM-L6-v2 model (384 dims); thread-safe after initialization |
| faiss-cpu | 1.13.2 | Vector search | In-memory index for <500 profiles; cosine similarity via inner-product on L2-normalized vectors |
| rapidfuzz | 3.5.2 | Fuzzy matching | Name matching for availability lookups (WRatio, threshold=85) |

### Concurrency & Async

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| concurrent.futures | stdlib | Thread pool | `ThreadPoolExecutor` for parallel CV ingestion; 4 workers default |
| aiofiles | 23.2.1 | Async file I/O | File uploads; already in requirements.txt |

### Database & State

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sqlite3 | stdlib | Metadata store | Transactional consistency; SQLite WAL mode for concurrent reads |
| faiss | 1.13.2 | Vector store | FAISS IndexFlatIP for cosine similarity search |

### Installation

```bash
# Existing project has all core dependencies; new additions:
pip install structlog==24.1.0  # For FEAT-10 (structured logging)

# Verify installation
python -c "import structlog; print('structlog ready')"
```

### Version Verification

**As of 2026-04-09:**
- **structlog**: 24.1.0 latest stable (supports JSON renderer, console renderer)
- **FastAPI**: 0.115.0 (StreamingResponse media_type support confirmed)
- **sentence-transformers**: 5.2.3 (thread-safe after initialization; global _model pattern safe with threading.Lock)
- **faiss-cpu**: 1.13.2 (IndexFlatIP supports inner-product search)

---

## Architecture Patterns

### Recommended Project Structure

Current structure is well-organized; Phase 2 adds:

```
app/
├── search/
│   ├── embeddings.py         # ← ROB-02: Add threading.Lock
│   ├── engine.py              # ← ROB-01, SEARCH-01: JSON parsing, pagination
│   └── filters.py             # ← SEARCH-02: OR logic
├── db.py                       # ← ROB-03, FEAT-07: asyncio.Lock, cache table
├── ingestion/
│   └── profile_builder.py      # ← ROB-01, ROB-04: JSON parsing, chunking
├── main.py                     # ← ROB-05: SSE endpoint
├── config.py                   # ← FEAT-02, FEAT-10: ingest_workers, log format
└── models.py                   # ← SEARCH-01, SEARCH-02: pagination, OR fields
scripts/
└── ingest_cvs.py              # ← ROB-04, ROB-05, FEAT-02: chunking, SSE, parallel
```

### Pattern 1: Thread-Safe Embedding Model (ROB-02)

**What:** Guard global `_model` initialization with `threading.Lock` to prevent race conditions during concurrent embedding generation.

**Why:** `SentenceTransformer` model loading is expensive (~100MB) and not thread-safe during initialization. Lock ensures only one thread loads the model; subsequent threads wait for lock release and reuse cached instance.

**When to use:** Any lazy-loaded singleton that is not thread-safe during initialization but thread-safe after.

**Example:**

```python
# app/search/embeddings.py
import threading
from sentence_transformers import SentenceTransformer
from app.config import settings

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None
_model_lock = threading.Lock()  # Add this lock


def get_model() -> SentenceTransformer:
    global _model
    with _model_lock:  # Synchronize access
        if _model is None:
            logger.info(f"Loading embedding model: {settings.embedding_model}")
            _model = SentenceTransformer(settings.embedding_model)
    return _model


def generate_embedding(text: str) -> list[float]:
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()
```

**Why this works:**
- Lock is acquired BEFORE checking `if _model is None`
- Only first thread enters init; others block and skip (already initialized)
- Model is cached after first load — subsequent calls are lock-free fast path

### Pattern 2: Async Lock for SQLite (ROB-03)

**What:** Serialize async SQLite access using `asyncio.Lock` to prevent write contention and database locks.

**Why:** SQLite allows only one writer at a time. WAL mode (already enabled in code) handles concurrent reads, but concurrent writes cause "database is locked" errors. `asyncio.Lock` ensures only one async task writes at a time.

**When to use:** Mixing async code (FastAPI handlers) with synchronous database (sqlite3), where multiple async tasks call `.upsert()` or `.delete()` concurrently.

**Example:**

```python
# app/db.py
import asyncio
from threading import Lock as ThreadLock

class VectorCollection:
    def __init__(self, db_dir: str):
        # ... existing code ...
        self._sqlite_write_lock = asyncio.Lock()  # Add this
        self._threading_lock = ThreadLock()       # For FEAT-02 parallel ingestion

    async def upsert_async(self, ids, embeddings, documents, metadatas):
        """Async wrapper around synchronous upsert."""
        async with self._sqlite_write_lock:  # Only one async writer
            # Run sync upsert in thread pool to avoid blocking event loop
            await asyncio.to_thread(
                self.upsert, ids, embeddings, documents, metadatas
            )

    def upsert_threaded(self, ids, embeddings, documents, metadatas):
        """Thread-safe wrapper for ThreadPoolExecutor (FEAT-02)."""
        with self._threading_lock:  # Only one thread writer
            self.upsert(ids, embeddings, documents, metadatas)
```

**Why this works:**
- `asyncio.Lock` is acquired before any database write
- Subsequent async writes block until lock is released
- WAL mode still handles concurrent reads (readers don't block writers)

### Pattern 3: JSON Parsing with Fallback (ROB-01)

**What:** Try `json.loads()` on raw response text first; if that fails, extract JSON with bracket-finding regex, then raise if both fail.

**Why:** Gemini API occasionally returns extra text before/after JSON (e.g., markdown, thinking). Pure regex is fragile. Robust parsing:
1. Try direct parse (fast path)
2. Extract bracketed content (handles markdown fences)
3. Raise with context (no silent failures)

**When to use:** Parsing LLM-generated JSON where the response may include non-JSON text.

**Example:**

```python
# app/search/engine.py or app/ingestion/profile_builder.py
import json
import logging
import re

logger = logging.getLogger(__name__)


def parse_json_response(content: str, context: str = "") -> dict:
    """
    Parse JSON from LLM response with multiple fallback strategies.

    Args:
        content: Raw response text from Gemini API
        context: Human-readable context for error logging

    Returns:
        Parsed JSON dictionary

    Raises:
        ValueError: If JSON cannot be parsed via any strategy
    """
    # Strategy 1: Direct JSON parse (handles clean responses)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract bracketed JSON (handles markdown, extra text)
    # Match {...} for objects, [...] for arrays
    for pattern in [r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", r"\[.*\]"]:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue

    # Strategy 3: Give up with context
    logger.error(
        f"Failed to parse JSON from {context}. Raw content:\n{content[:500]}..."
    )
    raise ValueError(f"Could not parse JSON from {context}: {content[:200]}")


# Usage in reranking
try:
    rankings = parse_json_response(response.text, context="Claude reranking response")
except ValueError as e:
    logger.error(f"Reranking fallback triggered: {e}")
    # Return unsorted candidates instead of crashing
    return [SearchResult(profile=c["profile"], score=c["score"]) for c in candidates]
```

**Why this works:**
- Fast path: clean JSON goes directly to `json.loads()`
- Fallback: regex extracts JSON from markdown
- No silent failures: exceptions are logged with context

### Pattern 4: Slide-Boundary Text Chunking (ROB-04)

**What:** Iterate through `slides_content` list, concatenate slides until cumulative length ≥ 16,000 chars, then pass that as `truncated_text`.

**Why:** Hard 8000-char cutoff loses context. Slide boundaries are natural break points. 16,000 chars ≈ 4000 tokens (4:1 ratio), sufficient for Gemini 2.0 Flash context window (1M tokens).

**When to use:** Text extraction where content has natural chunk boundaries (slides, pages, sections).

**Example:**

```python
# app/ingestion/profile_builder.py
def parse_profile_with_claude(raw_text: str, slides_content: list[str], name_hint: str) -> dict:
    """
    Parse CV with slide-boundary chunking.

    Args:
        raw_text: Original raw CV text (for backward compatibility)
        slides_content: List of slide texts from PPTX extraction
        name_hint: Name from filename

    Returns:
        Parsed profile dict
    """
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name=settings.llm_model,
        system_instruction=_SYSTEM_PROMPT,
    )

    # Slide-boundary chunking: concatenate slides until 16,000 chars
    truncated_text = ""
    for slide in slides_content:
        if len(truncated_text) + len(slide) <= 16_000:
            truncated_text += slide + "\n"
        else:
            break  # Stop at 16,000 char boundary

    if not truncated_text.strip():
        # Fallback: use raw_text if no slides
        truncated_text = raw_text[:16_000]

    try:
        response = model.generate_content(
            f"Name hint (from filename): {name_hint}\n\nCV Text:\n{truncated_text}"
        )
        content = response.text.strip()
        return parse_json_response(content, context=f"Profile parsing for {name_hint}")

    except (ValueError, Exception) as e:
        logger.error(f"Profile parsing failed for {name_hint}: {e}")
        return {
            "name": name_hint,
            "skills": [],
            "certifications": [],
            "experience_summary": truncated_text[:400],
            "domains": [],
            "languages": [],
            "education": "",
            "years_of_experience": None,
        }
```

**Why this works:**
- Preserves context by respecting slide boundaries
- Extends limit to 16,000 chars (4x previous)
- Fallback to raw_text if slides are missing

### Pattern 5: SSE Progress Streaming (ROB-05)

**What:** Endpoint returns `StreamingResponse` with `media_type="text/event-stream"`. In-process `asyncio.to_thread()` runs ingestion, yields progress events per file.

**Why:** Polling requires client refresh; SSE is push-based and real-time. `asyncio.to_thread()` avoids blocking event loop during long-running sync code (ingestion).

**When to use:** Long-running async-incompatible operations (file I/O, subprocess) where you need real-time progress feedback.

**Example:**

```python
# app/main.py
from fastapi.responses import StreamingResponse
import asyncio
import json

@app.get("/admin/reindex-stream")
async def reindex_stream(force: bool = False):
    """
    Stream reindex progress as Server-Sent Events.

    Event format:
    data: {"file": "john.pptx", "status": "processing", "count": 1}

    """
    async def progress_generator():
        """Generator that yields SSE-formatted progress events."""

        def ingestion_worker():
            """Run ingestion (sync function) and yield progress."""
            # This is a synchronous generator that yields per-file results
            # ingestion_function will yield {"file": "...", "status": "...", ...}
            yield from ingest_cvs_with_progress(force_reindex=force)

        try:
            # Run sync generator in thread pool, stream results back
            for event in await asyncio.to_thread(lambda: list(ingestion_worker())):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"Reindex stream error: {e}")
            yield f'data: {{"error": "{str(e)}"}}\n\n'

    return StreamingResponse(
        progress_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
```

**Admin UI (admin.html):**

```javascript
// Client-side EventSource to receive SSE events
function startReindex() {
    const eventSource = new EventSource('/admin/reindex-stream?force=false');

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.done) {
            console.log(`Reindex complete: ${data.processed} processed, ${data.skipped} skipped`);
            eventSource.close();
        } else {
            console.log(`Processed: ${data.file} - ${data.status}`);
            updateProgress(data);  // Update UI
        }
    };

    eventSource.onerror = () => {
        console.error("Stream error");
        eventSource.close();
    };
}
```

**Why this works:**
- `StreamingResponse` sends headers immediately; client connects and waits for events
- `asyncio.to_thread()` prevents blocking event loop
- Generator yields events as file processing completes
- Client displays real-time progress without polling

### Pattern 6: Load More Pagination (SEARCH-01)

**What:** Accept `page` (default 1) and `page_size` (default 10) in `SearchQuery` and `engine.search()`. Return slice of results + total count.

**Why:** "Load More" UX better than "Next Page" for mobile. Page size=10 keeps latency low. Total count allows UI to show "Showing 10 of 47".

**When to use:** Search results where users incrementally load more without page navigation.

**Example:**

```python
# app/models.py
class SearchQuery(BaseModel):
    query: str = Field(..., max_length=500)
    mode: str = "smart"
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    availability_status: Optional[str] = None
    availability_percentage_min: Optional[int] = None
    grade: Optional[str] = None
    location: Optional[str] = None
    page: int = Field(default=1, ge=1)           # ← Add this
    page_size: int = Field(default=10, ge=1, le=100)  # ← Add this


class SearchResult(BaseModel):
    profile: Profile
    score: float
    match_reasoning: Optional[str] = None
    gaps: Optional[str] = None
    highlighted_skills: list[str] = Field(default_factory=list)
    rank: Optional[int] = None                   # ← Add this for "Showing N of M"


# app/search/engine.py
def search(query: SearchQuery) -> dict:
    """
    Return paginated results with total count.

    Returns:
        {
            "results": [SearchResult, ...],
            "total": 47,
            "page": 1,
            "page_size": 10,
            "has_more": True
        }
    """
    collection = get_collection()
    count = collection.count()

    if count == 0:
        return {"results": [], "total": 0, "page": query.page, "page_size": query.page_size, "has_more": False}

    # ... existing search logic ...
    # candidates = apply filters, rerank, etc.

    total = len(candidates)
    start = (query.page - 1) * query.page_size
    end = start + query.page_size

    page_results = [
        SearchResult(profile=c["profile"], score=c["score"], rank=start+i+1)
        for i, c in enumerate(candidates[start:end])
    ]

    return {
        "results": page_results,
        "total": total,
        "page": query.page,
        "page_size": query.page_size,
        "has_more": end < total,
    }
```

**HTML template (partials/results.html):**

```html
<div id="results" hx-target="this" hx-swap="beforeend">
    {% for result in results %}
        <div class="result-item">{{ result.profile.name }} ({{ result.score|round(2) }})</div>
    {% endfor %}

    {% if has_more %}
        <button hx-get="/search"
                hx-include="[name=query], [name=skills], [name=page]"
                hx-target="#results"
                hx-swap="beforeend"
                hx-vals='{"page": "{{ page + 1 }}"}'>
            Load More
        </button>
    {% endif %}
</div>
```

**Why this works:**
- Pagination logic is simple slice: `candidates[start:end]`
- Total count returned so client can determine if "Load More" button shows
- HTMX `hx-swap="beforeend"` appends new results to existing list

### Pattern 7: OR Filter Logic (SEARCH-02)

**What:** Add `skills_any` and `certifications_any` fields to `SearchQuery`. In filters, implement OR logic: profile matches if ANY of the requested skills/certs are present.

**Why:** Current filters use AND only. OR logic allows "find profiles with Python OR R" (not requiring both).

**When to use:** Multi-select filters where user wants "any of these" instead of "all of these".

**Example:**

```python
# app/models.py
class SearchQuery(BaseModel):
    # ... existing fields ...
    skills: list[str] = Field(default_factory=list)           # AND logic
    skills_any: list[str] = Field(default_factory=list)       # ← Add OR logic
    certifications: list[str] = Field(default_factory=list)   # AND logic
    certifications_any: list[str] = Field(default_factory=list) # ← Add OR logic


# app/search/filters.py
def apply_filters(candidates: list[dict], query: SearchQuery) -> list[dict]:
    """Apply AND/OR filters to candidate list."""
    filtered = []

    for c in candidates:
        profile = c["profile"]

        # AND logic: ALL skills must be present
        if query.skills:
            profile_skills_lower = [s.lower() for s in profile.skills]
            if not all(s.lower() in profile_skills_lower for s in query.skills):
                continue

        # OR logic: ANY of skills_any must be present
        if query.skills_any:
            profile_skills_lower = [s.lower() for s in profile.skills]
            if not any(s.lower() in profile_skills_lower for s in query.skills_any):
                continue

        # Similar for certifications
        if query.certifications:
            profile_certs_lower = [cert.lower() for cert in profile.certifications]
            if not all(cert.lower() in profile_certs_lower for cert in query.certifications):
                continue

        if query.certifications_any:
            profile_certs_lower = [cert.lower() for cert in profile.certifications]
            if not any(cert.lower() in profile_certs_lower for cert in query.certifications_any):
                continue

        # ... existing availability, grade, location filters ...

        filtered.append(c)

    logger.info(f"Filters applied: {len(filtered)} of {len(candidates)} passed")
    return filtered
```

**HTML UI (search.html):**

```html
<div class="filter-group">
    <label>Skills</label>
    <input type="checkbox" name="logic-toggle" id="skills-logic" />
    <label for="skills-logic">OR mode</label>

    <select name="skills" multiple id="skills-select">
        {% for skill in available_skills %}
            <option value="{{ skill }}">{{ skill }}</option>
        {% endfor %}
    </select>
</div>

<script>
// Toggle between AND/OR mode
document.getElementById('skills-logic').addEventListener('change', function() {
    const select = document.getElementById('skills-select');
    if (this.checked) {
        select.name = 'skills_any';  // Switch to OR field
    } else {
        select.name = 'skills';      // Switch to AND field
    }
});
</script>
```

**Why this works:**
- AND filters use existing logic (all must match)
- OR filters add new logic (any must match)
- Frontend toggle switches between `name="skills"` and `name="skills_any"`

### Pattern 8: Embedding Cache Implementation (FEAT-07)

**What:** Create `query_cache` table in existing `metadata.db`. Key is SHA-256 of query text; value is embedding JSON. Before generating embedding, check cache.

**Why:** Query embeddings are deterministic (same input → same output). Cache eliminates redundant Gemini API calls. SHA-256 is fast (5µs per query) and collision-free for practical purposes.

**When to use:** Deterministic, expensive computations (embeddings, LLM calls) where repeated inputs are likely.

**Example:**

```python
# app/db.py
import hashlib

class VectorCollection:
    def __init__(self, db_dir: str):
        # ... existing code ...
        self._conn = self._open_db()

    def _open_db(self) -> sqlite3.Connection:
        # ... existing profiles table creation ...
        conn.execute("""
            CREATE TABLE IF NOT EXISTS query_cache (
                query_hash TEXT PRIMARY KEY,
                embedding  TEXT NOT NULL,  -- JSON array
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        return conn

    def get_cached_embedding(self, query_text: str) -> list[float] | None:
        """Return cached embedding if exists, else None."""
        query_hash = hashlib.sha256(query_text.encode()).hexdigest()
        row = self._conn.execute(
            "SELECT embedding FROM query_cache WHERE query_hash = ?",
            (query_hash,)
        ).fetchone()
        if row:
            logger.debug(f"Cache hit for query hash {query_hash[:8]}...")
            return json.loads(row["embedding"])
        return None

    def cache_embedding(self, query_text: str, embedding: list[float]) -> None:
        """Store embedding in cache."""
        query_hash = hashlib.sha256(query_text.encode()).hexdigest()
        self._conn.execute(
            """INSERT OR REPLACE INTO query_cache (query_hash, embedding, created_at)
               VALUES (?, ?, ?)""",
            (query_hash, json.dumps(embedding), datetime.now().isoformat())
        )
        self._conn.commit()


# app/search/embeddings.py
def generate_embedding_cached(text: str) -> list[float]:
    """Generate embedding with cache lookup."""
    collection = get_collection()

    # Check cache first
    cached = collection.get_cached_embedding(text)
    if cached:
        return cached

    # Generate and cache
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True).tolist()
    collection.cache_embedding(text, embedding)

    return embedding
```

**Usage in engine.py:**

```python
def search(query: SearchQuery) -> dict:
    # ... existing code ...

    # Use cached embedding generation
    from app.search.embeddings import generate_embedding_cached
    query_embedding = generate_embedding_cached(query.query)

    # ... rest of search ...
```

**Why this works:**
- SHA-256 hash is deterministic and collision-free
- Cache lookup is O(1) per query
- No eviction policy needed (queries are stateless, embeddings don't change)

### Pattern 9: Parallel Ingestion with Thread Safety (FEAT-02)

**What:** Use `ThreadPoolExecutor(max_workers=4)` to process files in parallel. Wrap `collection.upsert()` with `threading.Lock` to serialize database writes.

**Why:** File extraction (PPTX parsing, text generation) is I/O-bound. Parallelism reduces total runtime. Lock on upsert ensures FAISS/SQLite consistency.

**When to use:** Batch processing where individual tasks are independent and can run in parallel, but shared resource (database) needs serialization.

**Example:**

```python
# app/db.py
class VectorCollection:
    def __init__(self, db_dir: str):
        # ... existing code ...
        self._upsert_lock = threading.Lock()  # Add for FEAT-02

    def upsert_threadsafe(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """Threadsafe upsert for parallel ingestion."""
        with self._upsert_lock:
            self.upsert(ids, embeddings, documents, metadatas)


# scripts/ingest_cvs.py
from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

def process_file(file_path: Path, name_hint: str, availability: dict) -> dict:
    """
    Process a single file (extract text, parse profile, generate embedding).
    Returns status dict.
    """
    try:
        # Extract text from PPTX
        extracted = extract_text_from_pptx(str(file_path))
        slides_content = extracted.get("slides_content", [])
        raw_text = extracted.get("raw_text", "")

        # Parse profile with slide chunking
        profile_data = parse_profile_with_claude(raw_text, slides_content, name_hint)

        # Generate embedding
        embedding_text = f"{profile_data.get('name', '')} {profile_data.get('experience_summary', '')}"
        embedding = generate_embedding(embedding_text)

        # Metadata
        profile_id = derive_profile_id(profile_data["name"])
        metadata = {
            "name": profile_data["name"],
            "source_file": file_path.name,
            "skills": json.dumps(profile_data.get("skills", [])),
            "certifications": json.dumps(profile_data.get("certifications", [])),
            # ... other metadata ...
        }

        return {
            "status": "ok",
            "file": file_path.name,
            "profile_id": profile_id,
            "ids": [profile_id],
            "embeddings": [embedding],
            "documents": [raw_text],
            "metadatas": [metadata],
        }

    except Exception as e:
        logger.error(f"Error processing {file_path.name}: {e}")
        return {"status": "error", "file": file_path.name, "error": str(e)}


def ingest_cvs_parallel(force_reindex: bool = False, max_workers: int = 4) -> dict:
    """
    Ingest CVs in parallel.

    Yields:
        {"file": "john.pptx", "status": "processing|ok|error", "count": 1}
    """
    cv_dir = Path(settings.cv_directory)
    pptx_files = list(cv_dir.glob("*.pptx"))

    if not pptx_files:
        logger.warning(f"No .pptx files in {cv_dir}")
        return {"total": 0, "processed": 0, "skipped": 0, "errors": 0}

    collection = get_collection()
    avail_adapter = get_availability_adapter(settings.availability_file)
    availability = avail_adapter.get_availability()

    stats = {"total": len(pptx_files), "processed": 0, "skipped": 0, "errors": 0}

    # Fan out: process files in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_file, file, file.stem, availability): file
            for file in pptx_files
        }

        for future in futures:
            result = future.result()

            if result["status"] == "error":
                stats["errors"] += 1
                logger.error(f"Failed: {result['file']}")
                yield {"file": result["file"], "status": "error"}
            else:
                # Serial upsert: only one thread writes at a time
                try:
                    collection.upsert_threadsafe(
                        result["ids"],
                        result["embeddings"],
                        result["documents"],
                        result["metadatas"],
                    )
                    stats["processed"] += 1
                    yield {"file": result["file"], "status": "ok"}
                except Exception as e:
                    stats["errors"] += 1
                    logger.error(f"Upsert failed for {result['file']}: {e}")
                    yield {"file": result["file"], "status": "error"}

    return stats
```

**Why this works:**
- Parallel loop distributes CPU-intensive parsing across cores
- `executor.submit()` returns futures; `future.result()` waits for completion
- Serial lock on upsert ensures FAISS/SQLite never see conflicting writes
- ThreadPoolExecutor auto-manages thread lifecycle

### Pattern 10: Structured Logging Configuration (FEAT-10)

**What:** Configure `structlog` with:
- **Production:** JSON renderer for machine parsing
- **Development:** Colored console renderer for human readability

Replace all `logging.getLogger()` with `structlog.get_logger()`. Add `LOG_FORMAT=json` environment variable to control output.

**Why:** Structured logs are parseable by log aggregators (CloudWatch, ELK, Datadog). Context is attached to each event (request_id, user, timestamp), not scattered across multiple log lines.

**When to use:** Any backend where logs need to be aggregated, searched, or analyzed programmatically.

**Example:**

```python
# app/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # ... existing fields ...
    log_format: str = "colored"  # or "json" for production

    class Config:
        env_file = ".env"


# app/logging_config.py (new file)
import structlog
from app.config import settings


def configure_logging():
    """Configure structlog for the application."""

    if settings.log_format == "json":
        # Production: JSON output
        structlog.configure(
            processors=[
                structlog.processors.JSONRenderer(),
            ],
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Development: Colored console
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.dev.ConsoleRenderer(),  # Colored output
            ],
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )


# app/main.py
from app.logging_config import configure_logging

configure_logging()  # Call at startup


# Usage throughout the app
import structlog

logger = structlog.get_logger()

@app.get("/search")
async def search_endpoint(query: SearchQuery):
    logger.info("search_started", query=query.query, mode=query.mode)
    try:
        results = engine.search(query)
        logger.info("search_completed", result_count=len(results), query=query.query)
        return results
    except Exception as e:
        logger.error("search_failed", error=str(e), query=query.query, exc_info=True)
        raise
```

**Production output (JSON):**

```json
{"event":"search_started","query":"python architect","mode":"smart","timestamp":"2026-04-09T10:30:45.123Z"}
{"event":"search_completed","result_count":5,"query":"python architect","timestamp":"2026-04-09T10:30:47.234Z"}
```

**Development output (Colored):**

```
2026-04-09T10:30:45.123Z [info] search_started
  query='python architect'
  mode='smart'

2026-04-09T10:30:47.234Z [info] search_completed
  result_count=5
  query='python architect'
```

**Why this works:**
- Environment-aware configuration: same code, different output based on `LOG_FORMAT`
- Structured context: each event includes all relevant fields (query, result count, errors)
- Machine parseable: JSON renderer is first-class, not a fallback

### Anti-Patterns to Avoid

- **Don't use global variable for embedding model without lock:** Will cause race conditions when multiple async handlers call `generate_embedding()` concurrently. Always guard with `threading.Lock`.

- **Don't await SQLite operations directly in async handler:** Use `asyncio.to_thread()` and `asyncio.Lock` to serialize writes. Direct `sqlite3` calls block the event loop.

- **Don't hardcode Gemini response parsing with regex only:** Regex is fragile. Use `json.loads()` with exception handling and fallback extraction.

- **Don't truncate text arbitrarily:** Chunking at natural boundaries (slide ends, paragraph ends) preserves semantic meaning. Hard cutoffs lose context.

- **Don't poll for progress:** SSE is push-based; polling wastes bandwidth and battery. Use `StreamingResponse` with `text/event-stream` media type.

- **Don't skip embedding cache for repeated queries:** Cache hits are near-free; misses cost API call + latency. Always cache deterministic computations.

- **Don't serialize entire ingestion on single thread:** Parallel extraction/parsing is safe; only lock during database write. Files are independent.

- **Don't use print() for logging:** Use `structlog.get_logger()` for context-aware, machine-parseable logs. Stdout is for CLI tools, not backends.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON parsing from LLM | Regex-only extraction | `json.loads()` + fallback bracket-finding | Robust error handling; single failure point vs. brittle regex patterns |
| Thread-safe singletons | Custom synchronization | `threading.Lock` context manager | Well-tested, standard library; deadlock-free guarantee |
| Async + sync database | Custom queue system | `asyncio.Lock` + `asyncio.to_thread()` | Built into asyncio; no external dependencies; integrates with event loop |
| Text chunking | Character-based cutoff | Domain-aware boundaries (slides, paragraphs) | Preserves semantic coherence; prevents context loss |
| Progress streaming | Polling interval loop | `StreamingResponse` + SSE | Real-time, efficient; one-time connection vs. N polling requests |
| Deterministic caching | Manual memoization | SQLite `query_cache` table | Persistent across restarts; queryable; survives process crashes |
| Parallel file processing | Manual thread spawning | `ThreadPoolExecutor` | Auto thread management; cancellation support; exception propagation |
| Production logging | `print()` or basic logging | `structlog` + JSON renderer | Machine-parseable; context-aware; aggregator integration (CloudWatch, ELK) |

**Key insight:** Phase 2 leans on battle-tested patterns (locks, thread pools, structured logging) rather than reinventing. The only custom logic is domain-specific (slide chunking, embedding cache schema).

---

## Common Pitfalls

### Pitfall 1: JSON Parsing Crashes on Malformed Gemini Response

**What goes wrong:** Regex-only extraction fails silently or throws unhandled exception when Gemini returns malformed JSON (extra markdown, thinking tokens, incomplete array).

**Why it happens:** LLMs are non-deterministic; response format varies. Regex assumes consistent structure; a single misplaced bracket breaks parsing.

**How to avoid:**
1. Try `json.loads()` first (fast path for clean responses)
2. Extract bracketed JSON with regex (handles markdown)
3. Raise with context if both fail (no silent swallowing)
4. Log full response on error (debugging aid)

**Warning signs:**
- `re.search(r"\{.*\}", content).group()` without error handling
- Missing except block after `json.loads()`
- Silent fallback to empty dict/list (masked bugs)

### Pitfall 2: Race Condition in Embedding Model Loading

**What goes wrong:** Multiple async handlers call `generate_embedding()` concurrently. First thread loads model (100MB, slow). Meanwhile, other threads see `_model is None`, start loading again. Final state: inconsistent memory, possibly crashes.

**Why it happens:** Python global variables are not thread-safe during initialization. Without lock, TOCTOU (time-of-check to time-of-use) gap exists between `if _model is None` and `_model = SentenceTransformer(...)`.

**How to avoid:**
1. Acquire lock BEFORE checking `if _model is None`
2. Release lock AFTER initialization complete
3. Subsequent callers see `_model is not None`, skip lock (fast path)

**Warning signs:**
- `_model` accessed without lock
- Lock acquired AFTER `if _model is None` check
- Multiple print statements about "Loading embedding model" in concurrent log

### Pitfall 3: "Database is Locked" Error in Async Handler

**What goes wrong:** Multiple async handlers call `collection.upsert()` concurrently. SQLite allows only one writer; concurrent writes trigger "database is locked" exception. Some profiles are inserted, others lost.

**Why it happens:** SQLite has per-connection locking; async code runs multiple "threads" (coroutines) concurrently. WAL mode handles reads, but writes must serialize.

**How to avoid:**
1. Use `asyncio.Lock()` to serialize async writes
2. Run sync SQLite operations in `asyncio.to_thread()`
3. Only hold lock during actual database operation (not JSON serialization)

**Warning signs:**
- `sqlite3.OperationalError: database is locked`
- Inconsistent row counts between FAISS and SQLite
- Re-running ingestion produces different results

### Pitfall 4: Hard Text Cutoff Loses Critical Context

**What goes wrong:** CV text is truncated at 8000 chars, cutting off mid-word or mid-sentence. Claude misses skills listed in latter slides. Final profile is incomplete (missing skills, languages, certifications).

**Why it happens:** Character limits on LLM input. But arbitrary cutoff doesn't respect content structure; important info in slides 3+ is lost.

**How to avoid:**
1. Extract slides as separate chunks
2. Concatenate slides until reaching 16,000 char limit
3. Stop at slide boundary (never mid-slide)
4. Fallback to full text if no slides detected

**Warning signs:**
- Skills appear in original PPTX but not in parsed profile
- Availability, location data consistently missing
- "Truncation pattern" when comparing raw CV vs. parsed data

### Pitfall 5: Admin Page Hangs While Reindexing Large Dataset

**What goes wrong:** User clicks "Reindex" button. Page remains blank while 500 CVs are processed (30+ minutes). Browser times out (504 Gateway Timeout). User thinks reindex failed; manually restarts, causing duplicates.

**Why it happens:** POST handler runs ingestion synchronously; ties up the FastAPI worker process. No response sent until all CVs processed. Client HTTP timeout (typically 30 seconds) expires.

**How to avoid:**
1. Use `StreamingResponse` to send headers immediately
2. Run ingestion in `asyncio.to_thread()` to avoid blocking event loop
3. Yield progress events per file
4. Client receives real-time updates; no timeout

**Warning signs:**
- Admin page blank during reindex
- 504 Gateway Timeout errors in logs
- Manual reindex restarts causing duplicate profiles

### Pitfall 6: Embedding Cache Keys Collide on Query Text Typos

**What goes wrong:** User searches for "python architecure" (typo). No cache hit. Embedding generated, stored with hash of typo. User corrects typo, searches "python architecture". Different hash, no cache hit, re-generates embedding. Memory waste; queries differ by 1 char but both are cached.

**Why it happens:** SHA-256 is collision-free, but typos aren't collisions — they're different inputs. Cache works correctly; it's user behavior that causes misses.

**How to avoid:**
1. This is not a pitfall — cache is working as designed
2. If you want fuzzy matching, normalize queries before hashing (e.g., lowercase, remove punctuation)
3. Accept that typo searches won't cache hit

**Warning signs:**
- High cache miss rate on similar queries
- Expectation that "python" and "Python" should cache-hit (lowercase both before hashing)

### Pitfall 7: Parallel Ingestion Creates Duplicate Profiles

**What goes wrong:** Two threads process files concurrently. Both derive the same profile ID (same name from filenames). Both attempt upsert. FAISS index gets corrupted; duplicate vectors for same profile ID.

**Why it happens:** If profile_id derivation doesn't use lock and two threads check same profile_id concurrently, both think it's new, both append to FAISS without coordinating.

**How to avoid:**
1. Derive profile ID before thread dispatch (single-threaded, in main thread)
2. OR use threading.Lock on derive_profile_id
3. Always test with duplicate filenames: `john.pptx`, `JOHN.PPTX`

**Warning signs:**
- FAISS index size doesn't match SQLite row count
- Same profile appears multiple times in search results
- Collection rebuild required after parallel ingestion

### Pitfall 8: Log Aggregator Can't Parse Unstructured Logs

**What goes wrong:** Logs use print() and logging.getLogger(). In production, logs ship to CloudWatch/ELK/Datadog. Aggregator can't parse unstructured text; search queries return noise.

**Example unstructured:**
```
INFO 2026-04-09 10:30:45 - search started: python architect
INFO 2026-04-09 10:30:46 - found 5 candidates
INFO 2026-04-09 10:30:47 - reranking with Claude
```

Aggregator can't extract: "query": "python architect", "result_count": 5

**Why it happens:** Free-form text logs require human parsing. Log aggregators need structured fields (JSON).

**How to avoid:**
1. Use `structlog.get_logger()` everywhere
2. Attach context fields: `logger.info("search_started", query=..., mode=...)`
3. Configure JSON renderer for production
4. Aggregator can now query: `event=="search_started" AND query=="python architect"`

**Warning signs:**
- Log aggregator search returns false positives (unrelated log lines)
- Can't count "how many searches?" — would need to parse text
- No context about what request caused what error

---

## Code Examples

Verified patterns from official sources:

### JSON Parsing with Fallback

```python
# Source: Standard library (json, re modules)
import json
import logging
import re

logger = logging.getLogger(__name__)


def parse_json_from_llm(content: str, context: str = "") -> dict:
    """
    Robustly parse JSON from LLM response with fallback strategies.

    Strategies:
    1. Direct json.loads() — handles clean responses
    2. Bracket extraction — handles markdown, extra text
    3. Raise with context — no silent failures
    """
    # Strategy 1: Direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract and parse
    for pattern in [r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", r"\[.*\]"]:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue

    # Strategy 3: Fail with debugging info
    logger.error(f"JSON parse failed for {context}:\n{content[:500]}")
    raise ValueError(f"Could not parse JSON: {context}")
```

### Thread-Safe Singleton Pattern

```python
# Source: threading module (standard library)
import threading
from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None
_model_lock = threading.Lock()


def get_model() -> SentenceTransformer:
    global _model
    with _model_lock:
        if _model is None:
            _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model
```

### Async SQLite with Serialization Lock

```python
# Source: asyncio module (standard library)
import asyncio
import sqlite3


class AsyncSQLiteClient:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = asyncio.Lock()

    async def execute_write(self, query: str, params: tuple) -> int:
        """Execute write query safely in async context."""
        async with self._lock:
            # Run blocking operation in thread pool
            result = await asyncio.to_thread(
                lambda: self._conn.execute(query, params)
            )
            self._conn.commit()
            return result.lastrowid
```

### Slide-Boundary Text Chunking

```python
# Source: Custom domain logic
def chunk_text_by_slides(slides: list[str], max_chars: int = 16_000) -> str:
    """Chunk text respecting slide boundaries."""
    result = ""
    for slide in slides:
        if len(result) + len(slide) <= max_chars:
            result += slide + "\n"
        else:
            break
    return result or "".join(slides)[:max_chars]  # Fallback if single slide > limit
```

### Server-Sent Events Progress Streaming

```python
# Source: FastAPI StreamingResponse
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio
import json

app = FastAPI()


@app.get("/progress")
async def stream_progress():
    async def generate():
        for i in range(10):
            await asyncio.sleep(1)  # Simulate work
            yield f'data: {json.dumps({"progress": i*10})}\n\n'

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### Embedding Cache with SHA-256

```python
# Source: hashlib (standard library)
import hashlib


def get_cache_key(query: str) -> str:
    """Generate deterministic cache key."""
    return hashlib.sha256(query.encode()).hexdigest()


# Usage
cache_key = get_cache_key("find python architects")
# Result: "a1b2c3d4e5f6..." (same every time for same query)
```

### ThreadPoolExecutor for Parallel Processing

```python
# Source: concurrent.futures (standard library)
from concurrent.futures import ThreadPoolExecutor


def process_files_parallel(files: list[str], max_workers: int = 4):
    """Process files in parallel."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_file, f) for f in files]
        for future in futures:
            result = future.result()  # Wait for completion, re-raise exceptions
            yield result
```

### Structured Logging Configuration

```python
# Source: structlog documentation
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()
logger.info("action", query="python", count=5)
# Output: {"event":"action","query":"python","count":5,"timestamp":"2026-04-09T..."}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ChromaDB vector store | FAISS + SQLite | Phase 1 (2026-04-09) | Eliminated pydantic-v1 incompatibility; more control over schema |
| Regex-only JSON parsing | `json.loads()` + fallback | Phase 2 | Robust error handling; prevents silent failures |
| Hard 8000-char text cutoff | Slide-boundary chunking to 16K | Phase 2 | Preserves context; reduces information loss |
| Synchronous ingestion | Parallel ThreadPoolExecutor | Phase 2 | Faster CV processing for large datasets |
| Polling for reindex progress | SSE streaming | Phase 2 | Real-time feedback; eliminates browser timeout |
| No embedding cache | SHA-256-keyed query cache | Phase 2 | Eliminates redundant Gemini API calls |
| Global logging | structlog with JSON renderer | Phase 2 | Machine-parseable logs; aggregator integration |

**Deprecated/outdated:**
- ChromaDB (Phase 1): Pydantic v1 incompatible with Python 3.13+; FAISS + SQLite more lightweight
- Basic print() logging (Phase 2): No structure; useless in production log aggregators
- Character-based text truncation (Phase 2): Loses semantic context; slide boundaries better

---

## Open Questions

None at this phase. All 10 requirements are locked decisions with clear implementation patterns.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | FastAPI, asyncio.Lock | ✓ | 3.11+ | — |
| threading module | ROB-02, FEAT-02 | ✓ | stdlib | — |
| asyncio module | ROB-03, ROB-05 | ✓ | stdlib | — |
| json module | ROB-01 | ✓ | stdlib | — |
| hashlib module | FEAT-07 | ✓ | stdlib | — |
| re module | ROB-01 | ✓ | stdlib | — |
| structlog | FEAT-10 | ✗ | 24.1.0 | Use basic logging (not recommended) |
| FastAPI | ROB-05 (StreamingResponse) | ✓ | 0.115.0 | — |
| Pydantic | SEARCH-01, SEARCH-02 (models) | ✓ | 2.x | — |

**Missing dependencies with no fallback:**
- `structlog` must be installed for FEAT-10 (structured logging). Add to `requirements.txt`.

**Missing dependencies with fallback:**
- None. All critical dependencies are present.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.4.4 (already in requirements.txt) |
| Config file | Needs creation: `pytest.ini` or `pyproject.toml` |
| Quick run command | `pytest tests/ -m "not slow" -x` |
| Full suite command | `pytest tests/ --cov=app --cov-report=term-missing` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ROB-01 | JSON parsing succeeds on clean response | unit | `pytest tests/unit/test_json_parsing.py::test_clean_json -xvs` | ❌ Wave 0 |
| ROB-01 | JSON parsing succeeds on response with markdown | unit | `pytest tests/unit/test_json_parsing.py::test_markdown_json -xvs` | ❌ Wave 0 |
| ROB-01 | JSON parsing raises on unparseable response | unit | `pytest tests/unit/test_json_parsing.py::test_invalid_json_raises -xvs` | ❌ Wave 0 |
| ROB-02 | Embedding model initialization is thread-safe | unit | `pytest tests/unit/test_embeddings.py::test_concurrent_model_loading -xvs` | ❌ Wave 0 |
| ROB-03 | SQLite upsert under async concurrent load | integration | `pytest tests/integration/test_db_async.py::test_concurrent_upsert -xvs` | ❌ Wave 0 |
| ROB-03 | FAISS and SQLite remain in sync after upsert | integration | `pytest tests/integration/test_db_consistency.py -xvs` | ❌ Wave 0 |
| ROB-04 | Text chunking respects 16K char boundary | unit | `pytest tests/unit/test_chunking.py::test_slide_boundary_chunk -xvs` | ❌ Wave 0 |
| ROB-04 | Chunking preserves slide boundaries | unit | `pytest tests/unit/test_chunking.py::test_no_mid_slide_cutoff -xvs` | ❌ Wave 0 |
| ROB-05 | SSE stream endpoint returns text/event-stream | integration | `pytest tests/integration/test_sse.py::test_reindex_stream_content_type -xvs` | ❌ Wave 0 |
| ROB-05 | SSE events are valid JSON | integration | `pytest tests/integration/test_sse.py::test_sse_json_format -xvs` | ❌ Wave 0 |
| SEARCH-01 | Pagination returns correct page size | unit | `pytest tests/unit/test_pagination.py::test_page_size_10 -xvs` | ❌ Wave 0 |
| SEARCH-01 | Pagination returns correct total count | unit | `pytest tests/unit/test_pagination.py::test_total_count_accurate -xvs` | ❌ Wave 0 |
| SEARCH-01 | Load More button shows when has_more=True | unit | `pytest tests/unit/test_pagination.py::test_has_more_flag -xvs` | ❌ Wave 0 |
| SEARCH-02 | OR filter matches any skill in list | unit | `pytest tests/unit/test_filters.py::test_skills_any_matches -xvs` | ❌ Wave 0 |
| SEARCH-02 | AND filter requires all skills | unit | `pytest tests/unit/test_filters.py::test_skills_all_required -xvs` | ❌ Wave 0 |
| FEAT-02 | Parallel ingestion processes multiple files | integration | `pytest tests/integration/test_parallel_ingest.py::test_parallel_executor -xvs` | ❌ Wave 0 |
| FEAT-02 | Parallel ingestion maintains FAISS/SQLite sync | integration | `pytest tests/integration/test_parallel_ingest.py::test_consistency_parallel -xvs` | ❌ Wave 0 |
| FEAT-07 | Embedding cache returns cached result on hit | unit | `pytest tests/unit/test_cache.py::test_cache_hit -xvs` | ❌ Wave 0 |
| FEAT-07 | Cache key is deterministic | unit | `pytest tests/unit/test_cache.py::test_cache_key_deterministic -xvs` | ❌ Wave 0 |
| FEAT-10 | Logs output JSON in production mode | unit | `pytest tests/unit/test_logging.py::test_json_output -xvs` | ❌ Wave 0 |
| FEAT-10 | Logs output colored console in dev mode | unit | `pytest tests/unit/test_logging.py::test_console_colored -xvs` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/ -m "not slow" -x` (unit tests, quick integration)
- **Per wave merge:** `pytest tests/ --cov=app --cov-report=term-missing` (full suite with coverage)
- **Phase gate:** Full suite green + 80%+ coverage before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/conftest.py` — Shared fixtures for database, async client
- [ ] `tests/unit/test_json_parsing.py` — JSON parsing strategies (clean, markdown, invalid)
- [ ] `tests/unit/test_embeddings.py` — Thread-safe model loading under concurrent load
- [ ] `tests/unit/test_chunking.py` — Slide boundary text chunking with various edge cases
- [ ] `tests/unit/test_pagination.py` — Page size, total count, has_more flag
- [ ] `tests/unit/test_filters.py` — AND/OR filter logic correctness
- [ ] `tests/unit/test_cache.py` — Cache hit/miss, SHA-256 determinism
- [ ] `tests/unit/test_logging.py` — JSON and colored console output formats
- [ ] `tests/integration/test_db_async.py` — Concurrent upsert with asyncio.Lock
- [ ] `tests/integration/test_db_consistency.py` — FAISS/SQLite sync verification
- [ ] `tests/integration/test_sse.py` — SSE endpoint content type and JSON events
- [ ] `tests/integration/test_parallel_ingest.py` — ThreadPoolExecutor with locking
- [ ] Framework install: `pip install structlog pytest pytest-asyncio` (if not already installed)

---

## Sources

### Primary (HIGH confidence)

- **Python Standard Library Documentation**
  - `threading` — Lock, RLock, thread-safe singletons
  - `asyncio` — Lock, to_thread(), event loops
  - `json` — loads(), JSONDecodeError
  - `hashlib` — sha256() for deterministic hashing
  - `re` — search(), DOTALL flag for multiline matching
  - `concurrent.futures` — ThreadPoolExecutor, Future

- **FastAPI Official Documentation (0.115.0)**
  - `StreamingResponse` with `media_type="text/event-stream"` for SSE
  - `asyncio.to_thread()` for running sync code in async handlers
  - Pydantic BaseModel for request/response validation

- **Existing Codebase (CONTEXT.md, Phase 1 commits)**
  - FAISS + SQLite vector store (db.py) — SQLite WAL mode, FAISS IndexFlatIP
  - FastAPI setup in main.py — middleware, exception handlers, startup hooks
  - Sentence-Transformers (embeddings.py) — all-MiniLM-L6-v2 model (384 dims)
  - Google Generative AI (profile_builder.py, engine.py) — Gemini 2.0 Flash API

### Secondary (MEDIUM confidence)

- **structlog Official Documentation (24.1.0+)**
  - JSON renderer for production logging
  - ConsoleRenderer for colored development output
  - Context-aware logging with event fields

- **Python Community Best Practices**
  - Thread-safety patterns for singleton models (training + inference)
  - AsyncIO + SQLite patterns for FastAPI backends
  - Parallel processing with ThreadPoolExecutor and locking

### Tertiary (LOW confidence)

- None. All findings verified against official docs or existing codebase.

---

## Metadata

**Confidence breakdown:**

- **Standard Stack:** HIGH — All libraries in requirements.txt verified; structlog version confirmed against PyPI
- **Architecture Patterns:** HIGH — All patterns derived from locked decisions in CONTEXT.md, verified against existing code structure
- **Pitfalls:** HIGH — Based on common failure modes in concurrent Python, async + sync database mixing, LLM response parsing
- **Code Examples:** HIGH — All examples use standard library or official docs; no experimental code

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (30 days; Python ecosystem stable for this phase)

---

## Next Steps (for Planner)

1. Verify structlog installation: `pip install structlog==24.1.0`
2. Create pytest configuration file (pytest.ini or pyproject.toml)
3. Review Architecture Patterns section — each pattern has runnable code examples
4. Ensure Wave 0 test infrastructure created before implementation tasks
5. Verify all 10 locked decisions align with your team's constraints
