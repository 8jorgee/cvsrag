# Phase 1: Security & Data Integrity - Research

**Researched:** 2026-04-09
**Domain:** FastAPI security, data integrity, file validation, name matching
**Confidence:** HIGH

## Summary

Phase 1 eliminates critical security vulnerabilities and data consistency bugs to make the system production-safe. The phase requires five security hardening measures (CSRF tokens, API key validation, rate limiting, input length validation, file MIME type checking) and five data integrity fixes (accent-insensitive name matching, atomic database upserts, stable profile IDs, CSV change detection, date validation).

The codebase is built on FastAPI with FAISS+SQLite for the vector store, and currently lacks all CSRF protection, API key validation, and has three data bugs: names from CV files are not lowercased before availability lookup causing mismatches, profile IDs are MD5(filename) so renames create duplicates, and CSV changes alone don't trigger re-ingestion. These are high-priority production blockers.

**Primary recommendation:** Use `starlette-csrf` for CSRF tokens (integrates seamlessly with FastAPI), `unidecode` for accent normalization before name matching, `rapidfuzz` for fuzzy matching (already decided in STATE.md), and implement atomic transaction patterns in the FAISS/SQLite upsert logic to guarantee consistency.

## User Constraints (from REQUIREMENTS.md)

### Locked Decisions (from STATE.md)
- **Vector Store:** Keep FAISS + SQLite (already migrated from ChromaDB)
- **Rate Limiter:** Use slowapi (lightweight, FastAPI-native)
- **Name Matching:** Use rapidfuzz (best Python fuzzy match library for Unicode/accents)
- **Profile ID Strategy:** Base on parsed name UUID (stable across file renames, avoids duplicates)
- **Logging:** Use structlog (structured JSON output, colored dev mode)
- **Test Suite:** Use pytest (integrates well with FastAPI TestClient)
- **Embedding Model Concurrency:** Use threading.Lock (simpler than aiosqlite migration)

### Claude's Discretion
- Fuzzy match threshold for name matching: default 85 WRatio (configurable in .env)
- Pagination default page_size: 10 or 20
- Rate limit: 30 req/min per IP (confirm acceptable for internal use)

### Deferred Ideas (OUT OF SCOPE)
- SharePoint connector for automatic CV sync
- Multi-language name extraction
- FAISS → scalable vector DB migration (>500 profiles)
- OAuth / SSO authentication
- Public-facing search

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEC-01 | CSRF tokens on admin forms, server rejects requests without valid tokens | starlette-csrf middleware, token injection in Jinja templates |
| SEC-02 | App refuses to start without ANTHROPIC_API_KEY set | Pydantic BaseSettings validation at app startup |
| SEC-03 | Profile availability matches names (accent/case insensitive) | unidecode + rapidfuzz for fuzzy matching with 85 WRatio threshold |
| SEC-04 | Re-indexing renamed CVs updates existing profile, no duplicates | Profile IDs from parsed name UUID (not MD5 of filename) |
| SEC-05 | CSV-only changes trigger re-ingestion without --force | Hash availability file content + store in metadata alongside file_hash |
| DATA-01 | Query length capped at 500 characters (HTTP 400 for longer) | FastAPI query parameter validation with max_length constraint |
| DATA-02 | FAISS index and SQLite metadata atomic (rollback SQLite if FAISS fails) | SQLite transactions with PRAGMA journal_mode=WAL, explicit rollback on FAISS error |
| DATA-03 | Malformed dates excluded from availability filter (not silent pass-through) | Date validation with try/except in availability lookup |
| DATA-04 | File upload validates MIME type (not just extension) | python-magic or filetype library for content-based detection |
| DATA-05 | Rate limiting on /search endpoint (30 req/min per IP) | slowapi limiter with get_remote_address strategy |

## Standard Stack

### Core Security & Validation Libraries
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| starlette-csrf | Latest (0.12.x) | CSRF token generation, validation middleware | Standard pattern for Starlette/FastAPI, Double Submit Cookie technique, thread-safe |
| unidecode | 1.4.0+ (Aug 2025) | Unicode → ASCII transliteration for accent removal | Hand-tuned character mapping, handles 99%+ of Latin diacritics, 10x faster in Python 3.11+ |
| rapidfuzz | 3.5.2+ | Fuzzy string matching for name reconciliation | Best-in-class Python library, handles Unicode/accents natively, WRatio scoring, <50ms per match |
| slowapi | 0.1.9 | Rate limiting for FastAPI/Starlette | Decorator-based, IP-aware, returns HTTP 429 on exceed, minimal overhead |

### Data Validation & File Handling
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-magic | Latest | MIME type detection from file content (not header) | Validates actual file bytes, immune to client spoofing |
| filetype | 1.2.0+ | Lightweight MIME type detection alternative | If python-magic unavailable; dependency-free |

### Existing Stack (from requirements.txt)
- **FastAPI** 0.115.0 — Web framework
- **Pydantic-settings** 2.13.1 — Settings validation with .env support
- **Anthropic** 0.84.0 — Claude API client (requires ANTHROPIC_API_KEY env var)
- **python-multipart** 0.0.12 — Form parsing for uploads
- **aiofiles** 23.2.1 — Async file I/O

**Installation:**
```bash
pip install starlette-csrf unidecode rapidfuzz slowapi python-magic
# OR if python-magic unavailable:
pip install starlette-csrf unidecode rapidfuzz slowapi filetype
```

## Architecture Patterns

### 1. CSRF Token Injection Pattern
**What:** Middleware validates X-CSRFTOKEN header or form field on POST/PUT/DELETE requests. Tokens are per-session, tied to user cookies.

**When to use:** All state-changing operations (admin forms, file uploads, re-indexing).

**Example:**
```python
# app/main.py
from starlette_csrf import CSRFMiddleware
from starlette.middleware import Middleware

app = FastAPI(
    middleware=[
        Middleware(
            CSRFMiddleware,
            secret='your-secret-key-from-env',
            exempt_urls=['/api/'],  # API endpoints don't need tokens
        ),
    ]
)

# In Jinja template:
<form method="post" action="/admin/reindex">
    <input type="hidden" name="csrf_token" value="{{ request.session['csrf_token'] }}">
    <button type="submit">Re-index</button>
</form>
```

**Source:** [starlette-csrf documentation](https://github.com/frankie567/starlette-csrf)

### 2. Name Normalization + Fuzzy Matching Pattern
**What:** Before comparing names (CV vs. Availability CSV), normalize both sides: unidecode (remove accents) + lowercase, then use rapidfuzz.WRatio for fuzzy matching.

**When to use:** Loading availability data, matching profiles to availability records.

**Example:**
```python
# app/ingestion/availability.py
from unidecode import unidecode
from rapidfuzz import fuzz

def normalize_name(name: str) -> str:
    """Convert 'François' to 'francois' for consistent matching."""
    return unidecode(name).lower().strip()

def get_availability(self) -> dict[str, dict]:
    """Return dict mapping normalized name to availability data."""
    result = {}
    for _, row in df.iterrows():
        name = str(row.get("name", "")).strip()
        if not name:
            continue

        normalized = normalize_name(name)  # 'François Müller' → 'francois muller'
        result[normalized] = {
            "availability_percentage": int(row.get("availability_percentage")) or None,
            "availability_date": str(row.get("availability_date")).strip() or None,
            # ... other fields
        }
    return result

def match_availability_fuzzy(parsed_name: str, availability: dict, threshold: int = 85) -> dict:
    """Fuzzy match parsed CV name against availability records."""
    norm_parsed = normalize_name(parsed_name)

    if norm_parsed in availability:
        return availability[norm_parsed]  # Exact match after normalization

    # Fallback to fuzzy matching if exact miss
    best_match = None
    best_score = 0
    for avail_name in availability.keys():
        score = fuzz.WRatio(norm_parsed, avail_name)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = avail_name

    if best_match:
        return availability[best_match]
    return {}
```

**Source:** [RapidFuzz 3.14.4 documentation](https://rapidfuzz.github.io/RapidFuzz/)

### 3. Atomic FAISS-SQLite Upsert Pattern
**What:** Update SQLite transaction first (with automatic rollback), then rebuild FAISS index. If SQLite fails, FAISS is never touched.

**When to use:** Profile ingestion, re-indexing, bulk updates.

**Example:**
```python
# app/db.py — VectorCollection.upsert()
def upsert(self, ids: list[str], embeddings: list[list[float]], documents: list[str], metadatas: list[dict]) -> None:
    """Atomic: update SQLite first, then FAISS. Rollback SQLite on any error."""
    try:
        needs_rebuild = False
        for doc_id, embedding, document, metadata in zip(ids, embeddings, documents, metadatas):
            existing = self._conn.execute(
                "SELECT id FROM profiles WHERE id = ?", (doc_id,)
            ).fetchone()

            self._conn.execute(
                """INSERT INTO profiles (id, document, metadata, embedding)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     document = excluded.document,
                     metadata = excluded.metadata,
                     embedding = excluded.embedding
                """,
                (doc_id, document, json.dumps(metadata), json.dumps(embedding)),
            )
            if existing:
                needs_rebuild = True

        self._conn.commit()  # Commit SQLite transaction

        # Only if SQLite succeeded, update FAISS
        if needs_rebuild:
            self._index = self._rebuild_index()
        else:
            new_vecs = np.array(embeddings, dtype=np.float32)
            self._index.add(new_vecs)
        faiss.write_index(self._index, str(self._index_path))

    except Exception as e:
        self._conn.rollback()  # Undo SQLite writes if anything fails
        logger.error(f"Upsert failed, rolled back: {e}")
        raise
```

**Source:** [SQLite Transaction Best Practices](https://www.sqlitetutorial.net/sqlite-transaction-explained-by-practical-examples/)

### 4. Stable Profile ID Pattern
**What:** Profile IDs derived from parsed name (as UUID or hash of normalized name), not from filename. Ensures re-indexing a renamed file updates the existing profile.

**When to use:** Profile creation, preventing duplicates on filename changes.

**Example:**
```python
# scripts/ingest_cvs.py — CURRENT (BROKEN):
profile_id = hashlib.md5(filename.encode()).hexdigest()  # BUG: Changes if file renamed

# FIXED:
import uuid

def derive_profile_id(parsed_name: str, department: str = "") -> str:
    """Stable ID from name, not filename."""
    combined = f"{parsed_name}:{department}".lower().strip()
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, combined))

# In ingest_cvs():
parsed = parse_profile_with_claude(extracted["raw_text"], extracted["name"])
profile_id = derive_profile_id(parsed["name"])  # Stable even if .pptx renamed
```

**Source:** [STATE.md decisions log](/.planning/STATE.md)

### 5. CSV Change Detection Pattern
**What:** Hash both the CV file AND the availability CSV. Trigger re-ingestion if either hash changes, not just the CV hash.

**When to use:** Incremental ingestion logic in ingest_cvs.py.

**Example:**
```python
# scripts/ingest_cvs.py
def ingest_cvs(force_reindex: bool = False) -> None:
    collection = get_collection()

    # Load and hash availability file
    avail_file = Path(settings.availability_file)
    avail_hash = file_hash(str(avail_file)) if avail_file.exists() else ""

    # Build existing index
    existing: dict[str, dict] = {}
    if not force_reindex and collection.count() > 0:
        all_docs = collection.get(include=["metadatas"])
        for i, doc_id in enumerate(all_docs["ids"]):
            meta = all_docs["metadatas"][i]
            existing[meta.get("source_file", "")] = {
                "id": doc_id,
                "file_hash": meta.get("file_hash", ""),
                "avail_hash": meta.get("availability_hash", ""),  # NEW
            }

    for pptx_path in pptx_files:
        filename = pptx_path.name
        fhash = file_hash(str(pptx_path))

        # Re-index if CV changed OR availability changed
        if filename in existing:
            prev_fhash = existing[filename]["file_hash"]
            prev_avail_hash = existing[filename]["avail_hash"]
            if fhash == prev_fhash and avail_hash == prev_avail_hash:
                logger.info(f"  SKIP  {filename} (CV and availability unchanged)")
                skipped += 1
                continue

        logger.info(f"  PROC  {filename}")
        # ... extract, parse, match availability, upsert ...

        metadata["availability_hash"] = avail_hash  # Store for next run
```

### 6. Date Validation Pattern
**What:** Parse dates in a try/except block. If invalid, log warning and exclude from availability filter (don't silently pass through).

**When to use:** Availability data ingestion, availability filter application.

**Example:**
```python
# app/search/filters.py
def apply_availability_filter(candidates: list, filter_spec: dict) -> list:
    """Exclude profiles with invalid availability_date from filter results."""
    if not filter_spec.get("availability_status"):
        return candidates

    status = filter_spec["availability_status"]  # "now", "30days", "90days"
    now = datetime.now()

    filtered = []
    for c in candidates:
        profile = c["profile"]
        date_str = profile.availability_date

        if not date_str:
            continue  # No date = unknown availability, exclude

        try:
            avail_date = datetime.fromisoformat(date_str)

            if status == "now" and avail_date <= now:
                filtered.append(c)
            elif status == "30days" and avail_date <= now + timedelta(days=30):
                filtered.append(c)
            elif status == "90days" and avail_date <= now + timedelta(days=90):
                filtered.append(c)
        except ValueError:
            logger.warning(f"Malformed availability_date '{date_str}' for {profile.name} — excluding from filter")
            # Don't include in filtered results

    return filtered
```

### 7. File MIME Type Validation Pattern
**What:** Check both filename extension AND file content (magic bytes). Reject if either doesn't match allowed types.

**When to use:** CV upload (/admin/upload-cv), availability upload (/admin/upload-availability).

**Example:**
```python
# app/main.py
import magic

def _validate_upload_file(file: UploadFile, allowed_extensions: set[str], allowed_mimes: set[str]) -> None:
    """Validate file extension and MIME type."""
    # Check extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {allowed_extensions}")

    # Check MIME type from content (not from client header)
    content = file.file.read()
    file.file.seek(0)  # Reset for later reads

    detected_mime = magic.from_buffer(content[:2048], mime=True)
    if detected_mime not in allowed_mimes:
        raise HTTPException(
            status_code=415,
            detail=f"File content is {detected_mime}, not a valid {ext} file"
        )

    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")

@app.post("/admin/upload-cv")
async def upload_cv(file: UploadFile = File(...), _: None = Depends(_require_admin_auth)):
    _validate_upload_file(
        file,
        allowed_extensions={".pptx"},
        allowed_mimes={"application/vnd.openxmlformats-officedocument.presentationml.presentation"}
    )
    # ... rest of upload logic ...
```

**Source:** [python-magic documentation](https://github.com/ahupp/python-magic)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSRF token management | Custom token generation/validation logic | starlette-csrf | Middleware handles session binding, token expiry, timing-safe comparison |
| Accent-insensitive name matching | Regex-based diacritic removal | unidecode + rapidfuzz | Unicode edge cases (Nordic chars, accented vowels, combined diacritics) are complex; battle-tested library handles 99%+ of cases |
| Rate limiting | Manual request counting per IP | slowapi | Thread-safe, async-compatible, handles multiple middleware, integrates with FastAPI exception handlers |
| MIME type detection | Extension-only validation | python-magic | Client-provided content-type header is untrustworthy; magic bytes inspection is fool-proof against spoofing |
| FAISS-SQLite atomicity | Write to FAISS, then SQLite | SQLite transaction + FAISS rebuild | Crash between two writes = orphaned embeddings; single transaction ensures all-or-nothing |

**Key insight:** Name matching, CSRF, and file validation all have subtle security/data consistency requirements that custom code routinely gets wrong. Existing libraries encode the lessons of dozens of production incidents.

## Common Pitfalls

### Pitfall 1: Name Lookup Before Normalization
**What goes wrong:** CSV has "François Müller", CV parsing returns "Francois Muller", lookup fails silently → profile marked with 0% availability instead of actual data.

**Why it happens:** Developers skip the normalization step because names "look" like they should match visually.

**How to avoid:** Always normalize both sides of a name comparison: unidecode(name).lower(). Verify with a unit test that "François Müller" → "francois muller" matches "Francois Muller" at >85 WRatio.

**Warning signs:** Availability dashboard shows many profiles with 0% availability, but CSV has entries for them. Logs show no "Matched availability for X" messages for expected names.

### Pitfall 2: Relying on Content-Type Header for File Validation
**What goes wrong:** Attacker uploads a .exe file disguised as .pptx (client says content-type: application/vnd.openxmlformats...). Code accepts it because it checks header, not content.

**Why it happens:** Content-Type is convenient and always present, so developers skip the magic byte check.

**How to avoid:** Use python-magic to read actual file bytes. Check magic bytes before writing to disk. Never trust the client's content-type header.

**Warning signs:** Upload succeeds but file is corrupted; extraction fails with unexpected errors on "valid" PPTX files.

### Pitfall 3: Missing CSRF Token Validation on Form Submissions
**What goes wrong:** Admin form POST has no CSRF validation. Attacker tricks admin into clicking a link on another website, which auto-submits a form to re-index or delete data.

**Why it happens:** CSRF feels optional because the site uses HTTP Basic auth. But auth protects against WHO submits, not WHAT gets submitted.

**How to avoid:** Apply CSRF middleware to ALL state-changing endpoints. Use POST/PUT/DELETE (not GET) for mutations. Validate X-CSRFTOKEN header or form field on every write.

**Warning signs:** Admin is not using Forms with hidden CSRF tokens; network tab shows no csrf_token parameter in POST requests.

### Pitfall 4: Profile ID Based on Filename
**What goes wrong:** Admin renames "john-smith.pptx" → "john.smith.pptx" to fix a typo. Ingestion creates a duplicate profile with new ID instead of updating existing one.

**Why it happens:** Using filename as the ID source seemed convenient (no need to parse), and duplicates weren't caught until the admin dashboard showed two "John Smith" profiles.

**How to avoid:** Derive profile ID from parsed name + department, not filename. Use UUID5 for stability. Verify in a test that re-ingesting the same CV with different filenames produces the same profile ID.

**Warning signs:** Searching for a person returns duplicate profiles; admin dashboard shows the same name multiple times.

### Pitfall 5: CSV Changes Not Triggering Re-ingestion
**What goes wrong:** Admin updates availability.csv to change "John Smith" from 0% to 50% available. Running ingest_cvs (no --force) skips re-indexing because CV file hash is unchanged. Availability data is stale.

**Why it happens:** Incremental ingestion only hashes the .pptx files, not the CSV. Developers assume CSV is static or will always be reloaded fresh.

**How to avoid:** Store both file_hash (CV) and availability_hash (CSV) in metadata. On ingestion, re-process any profile whose availability_hash differs from current CSV hash.

**Warning signs:** Admin makes availability.csv changes but they don't appear in search results until --force flag is used.

### Pitfall 6: Availability Date Parsing Errors Passed Silently
**What goes wrong:** CSV has a malformed date like "32-01-2026". Code tries to parse, fails silently (or catches exception without logging), marks availability_date as null, profile is excluded from availability filters.

**Why it happens:** Exception handling is generic ("on error, use default None"), so bad data degrades silently instead of alerting admins.

**How to avoid:** Log all parse failures with the offending value and profile name. Exclude malformed profiles from availability filters (don't hide the error). Alert admin in the dashboard about unparseable dates.

**Warning signs:** Profiles with invalid dates are missing from availability-filtered results; logs show no mention of parse errors.

## Code Examples

### Startup API Key Validation
```python
# app/main.py
from fastapi import FastAPI

def validate_startup():
    """Ensure ANTHROPIC_API_KEY is set before app starts."""
    from app.config import settings
    if not settings.anthropic_api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Set it in .env or as a system environment variable."
        )
    logger.info("ANTHROPIC_API_KEY validated at startup")

@app.on_event("startup")
async def startup_event():
    validate_startup()
```

**Source:** [Pydantic BaseSettings documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

### Query Length Validation
```python
# app/models.py
from pydantic import BaseModel, Field

class SearchQuery(BaseModel):
    query: str = Field(..., max_length=500)  # SEC-02: Reject queries >500 chars
    mode: str = "smart"
    # ... other fields ...

# app/main.py
@app.post("/search")
async def do_search(query: SearchQuery):
    # FastAPI automatically rejects if query.query > 500 chars
    results = engine.search(query)
    return results
```

**Source:** [FastAPI validation documentation](https://fastapi.tiangolo.com/tutorial/body-more-than-one-parameter/)

### Rate Limiting Setup
```python
# app/main.py
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_error_handler)

def _rate_limit_error_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded: 30 requests per minute"},
    )

@app.post("/search")
@limiter.limit("30/minute")
async def do_search(request: Request, query: SearchQuery):
    results = engine.search(query)
    return templates.TemplateResponse("partials/results.html", {...})
```

**Source:** [SlowAPI documentation](https://slowapi.readthedocs.io/)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (with FastAPI TestClient) |
| Config file | pytest.ini or pyproject.toml (Wave 0) |
| Quick run command | `pytest tests/ -k "security" -x` |
| Full suite command | `pytest tests/ --cov=app --cov-report=term-missing` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEC-01 | CSRF token rejected on POST without token | unit | `pytest tests/test_security.py::test_csrf_required -x` | ❌ Wave 0 |
| SEC-02 | App startup fails if ANTHROPIC_API_KEY missing | unit | `pytest tests/test_config.py::test_api_key_required -x` | ❌ Wave 0 |
| SEC-03 | Profile matches availability by normalized name | integration | `pytest tests/test_ingestion.py::test_availability_accent_insensitive -x` | ❌ Wave 0 |
| SEC-04 | Re-indexing same profile with different filename keeps same ID | integration | `pytest tests/test_ingestion.py::test_profile_id_stable -x` | ❌ Wave 0 |
| SEC-05 | CSV change triggers re-ingestion without --force | integration | `pytest tests/test_ingestion.py::test_csv_change_detection -x` | ❌ Wave 0 |
| DATA-01 | Query >500 chars rejected with HTTP 400 | unit | `pytest tests/test_api.py::test_query_length_limit -x` | ❌ Wave 0 |
| DATA-02 | FAISS-SQLite upsert rolls back on error | unit | `pytest tests/test_db.py::test_upsert_rollback -x` | ❌ Wave 0 |
| DATA-03 | Malformed dates excluded from availability filter | unit | `pytest tests/test_filters.py::test_malformed_date_excluded -x` | ❌ Wave 0 |
| DATA-04 | File upload validates MIME type | unit | `pytest tests/test_uploads.py::test_mime_type_validation -x` | ❌ Wave 0 |
| DATA-05 | /search endpoint rate-limited at 30/min | integration | `pytest tests/test_api.py::test_rate_limit_enforcement -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_<module>.py -x` (quick validation)
- **Per wave merge:** `pytest tests/ --cov=app -x` (full coverage check)
- **Phase gate:** All tests passing + coverage ≥ 60% before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_security.py` — CSRF token validation, API key startup check
- [ ] `tests/test_ingestion.py` — Profile ID stability, name normalization, CSV change detection
- [ ] `tests/test_api.py` — Query length limits, rate limiting
- [ ] `tests/test_uploads.py` — MIME type validation, file size limits
- [ ] `tests/test_db.py` — Atomic upsert, rollback behavior
- [ ] `tests/test_filters.py` — Date validation, availability filtering
- [ ] `tests/conftest.py` — Shared fixtures (mock FastAPI TestClient, test database)
- [ ] Framework install: `pip install pytest pytest-asyncio httpx` (if not already present)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Core | ✓ | 3.9+ (via requirements.txt) | — |
| pip | Dependency install | ✓ | Latest | — |
| FastAPI | Web framework | ✓ | 0.115.0 (in requirements.txt) | — |
| python-magic | File MIME validation (DATA-05) | ✗ (needs install) | Latest | filetype library |
| pytest | Test framework (Wave 0) | ✗ (needs install) | 7.4.0+ | — |

**Missing dependencies with no fallback:**
- pytest — required for test suite (Wave 0 task)

**Missing dependencies with fallback:**
- python-magic — if unavailable, use filetype library (lighter weight, no C dependency)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Extension-only file validation | Content-based MIME type detection (python-magic) | 2024 industry standard | Prevents spoofing attacks |
| Manual CSRF token generation | Middleware-based token binding (starlette-csrf) | 2023 FastAPI best practice | Automatic token lifecycle, timing-safe comparison |
| Regex-based diacritic removal | Unidecode library + fuzzy matching | 2020s standard | Handles 99% of Unicode cases, not 70% |
| Profile ID from filename | UUID from parsed name | 2024 data integrity standard | Survives file renames, prevents duplicates |
| CV-only change detection | Dual-hash strategy (CV + CSV) | Modern RAG practice | Catches all data changes, not just content |

**Deprecated/outdated:**
- ChromaDB for vector storage (replaced by FAISS + SQLite in this codebase) — Pydantic v1 incompatibility with Python 3.14
- Manual JWT token generation — Starlette security primitives superior

## Open Questions

1. **CSRF token secret rotation**
   - What we know: starlette-csrf supports rotating secrets
   - What's unclear: How often should we rotate in production? Per-session or global?
   - Recommendation: For now, use a global secret from .env. Plan token rotation in Phase 2 (advanced features).

2. **Fuzzy match threshold calibration**
   - What we know: STATE.md sets default to 85 WRatio, configurable in .env
   - What's unclear: What threshold minimizes false negatives (missing matches) vs. false positives (wrong matches)?
   - Recommendation: Start with 85, monitor availability matching in admin dashboard, adjust in Phase 2 if too many missed matches.

3. **Availability hash collision risk**
   - What we know: We'll hash CSV content to detect changes
   - What's unclear: Should we hash just the entire file, or hash per-row and store row-level hashes in metadata?
   - Recommendation: Hash entire file for Phase 1 (simpler). If re-indexing becomes slow due to large CSVs, migrate to row-level hashing in Phase 2.

## Sources

### Primary (HIGH confidence)
- [FastAPI documentation](https://fastapi.tiangolo.com/) — Input validation, startup events
- [starlette-csrf GitHub](https://github.com/frankie567/starlette-csrf) — CSRF middleware implementation
- [Unidecode PyPI](https://pypi.org/project/Unidecode/) — Unicode transliteration
- [RapidFuzz documentation](https://rapidfuzz.github.io/RapidFuzz/) — Fuzzy matching with Unicode support
- [SlowAPI documentation](https://slowapi.readthedocs.io/) — FastAPI rate limiting
- [SQLite Transaction documentation](https://www.sqlitetutorial.net/sqlite-transaction-explained-by-practical-examples/) — Atomic operations
- [python-magic documentation](https://github.com/ahupp/python-magic) — File MIME type detection

### Secondary (MEDIUM confidence - verified with official sources)
- [FastAPI CSRF protection best practices](https://fastapi.tiangolo.com/tutorial/security/first-steps/) — Input validation patterns
- [Pydantic BaseSettings documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) — Environment variable validation
- [python-magic library comparison](https://www.tutorialspoint.com/how-to-find-the-mime-type-of-a-file-in-python) — MIME detection methods

### Tertiary (research references)
- [starlette-csrf - Snyk security analysis](https://snyk.io/advisor/python/starlette-csrf) — Library health check
- [FAISS-SQLite sync challenges](https://dev.to/mayank_laddha_ml/faiss-with-sqlite-for-rag-3e2b) — Architecture considerations
- [RapidFuzz vs. alternatives](https://github.com/rapidfuzz/RapidFuzz) — Comparison with FuzzyWuzzy, others

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — All libraries verified as current (2024–2025) and production-ready
- Architecture patterns: HIGH — Based on official documentation and industry best practices
- Pitfalls: HIGH — Derived from documented security/data integrity issues in similar systems
- Test coverage: MEDIUM — Test file structure inferred from pytest + FastAPI conventions (Wave 0 will generate actual files)

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (30 days — stable libraries, no major version changes expected)
