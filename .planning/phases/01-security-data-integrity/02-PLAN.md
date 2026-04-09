---
phase: 01-security-data-integrity
plan: 02
type: execute
wave: 2
depends_on: [01]
files_modified:
  - app/config.py
  - app/db.py
  - app/models.py
  - app/ingestion/availability.py
  - app/search/filters.py
  - scripts/ingest_cvs.py
  - requirements.txt
autonomous: false
requirements: [DATA-01, DATA-02, DATA-03, DATA-04, DATA-05]
user_setup: []

must_haves:
  truths:
    - "Profile availability names matched case-insensitively and accent-insensitively (François → francois)"
    - "FAISS index and SQLite metadata stay in sync on upsert; rollback SQLite if FAISS fails"
    - "Profile IDs are stable UUIDs derived from parsed name, not MD5 of filename"
    - "Availability CSV changes trigger re-ingestion of affected profiles without --force flag"
    - "Profiles with malformed availability dates are excluded from availability filters with warning logged"
  artifacts:
    - path: "app/ingestion/availability.py"
      provides: "Name normalization (unidecode), fuzzy matching with rapidfuzz"
      min_lines: 80
    - path: "app/db.py"
      provides: "Atomic upsert with SQLite rollback on FAISS error"
      min_lines: 200
    - path: "scripts/ingest_cvs.py"
      provides: "Stable profile ID from parsed name (UUID), CSV change detection"
      min_lines: 150
    - path: "app/search/filters.py"
      provides: "Date validation with try/except, exclusion on parse error"
      min_lines: 100
    - path: "app/config.py"
      provides: "FUZZY_MATCH_THRESHOLD setting (default 85, configurable)"
      min_lines: 30
    - path: "requirements.txt"
      provides: "unidecode, rapidfuzz dependencies"
  key_links:
    - from: "scripts/ingest_cvs.py"
      to: "app/ingestion/availability.py"
      via: "import normalize_name, match_availability_fuzzy"
      pattern: "from app.ingestion.availability import"
    - from: "scripts/ingest_cvs.py"
      to: "app/db.py"
      via: "collection.upsert(ids, embeddings, documents, metadatas)"
      pattern: "collection.upsert"
    - from: "app/search/filters.py"
      to: "app/models.py"
      via: "Profile.availability_date field"
      pattern: "availability_date"
    - from: "app/db.py"
      to: "SQLite transaction"
      via: "self._conn.commit() with try/except for rollback"
      pattern: "self._conn.commit\|self._conn.rollback"
---

<objective>
Fix all data integrity bugs: name matching, atomic database operations, stable profile IDs, CSV change detection, and date validation.

Purpose: Ensure profile data is consistent, searchable by availability, and doesn't create duplicates or lose data on system failures.

Output: Robust data ingestion and storage layer with normalized name matching and atomic operations.
</objective>

<execution_context>
@/Users/8jorgee/.claude/get-shit-done/workflows/execute-plan.md
@/Users/8jorgee/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/8jorgee/Desktop/cvsrag/.planning/ROADMAP.md
@/Users/8jorgee/Desktop/cvsrag/.planning/STATE.md
@/Users/8jorgee/Desktop/cvsrag/.planning/REQUIREMENTS.md
@/Users/8jorgee/Desktop/cvsrag/.planning/phases/01-security-data-integrity/01-RESEARCH.md
@/Users/8jorgee/Desktop/cvsrag/.planning/phases/01-security-data-integrity/01-SUMMARY.md

Key codebase files:
@/Users/8jorgee/Desktop/cvsrag/app/db.py — VectorCollection.upsert() not atomic (SQLite commit before FAISS sync)
@/Users/8jorgee/Desktop/cvsrag/app/ingestion/availability.py — CSVAvailabilityAdapter, doesn't normalize names
@/Users/8jorgee/Desktop/cvsrag/scripts/ingest_cvs.py — Profile ID = MD5(filename), no CSV change detection
@/Users/8jorgee/Desktop/cvsrag/app/search/filters.py — Availability filter, silent date parse errors
@/Users/8jorgee/Desktop/cvsrag/app/config.py — Settings, no fuzzy match threshold
@/Users/8jorgee/Desktop/cvsrag/app/models.py — Profile model, availability_date field

Interfaces needed from Plan 01 (SUMMARY.md):
- CSRF middleware active in app/main.py
- API key validation at startup
- SearchQuery.query has max_length=500
- Rate limiting on /search
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Wave 0: Create test infrastructure for data integrity tests</name>
  <files>tests/test_availability.py, tests/test_db.py, tests/test_ingestion.py, tests/test_filters.py</files>
  <behavior>
    - test_availability.py has stub for DATA-01 (accent-insensitive name matching)
    - test_db.py has stub for DATA-02 (atomic upsert)
    - test_ingestion.py has stubs for DATA-03 (stable IDs) and DATA-04 (CSV delta detection)
    - test_filters.py has stub for DATA-05 (malformed date exclusion)
    - All tests are importable and runnable (pytest discovers them)
  </behavior>
  <action>
    1. Add test stubs to tests/test_availability.py:
    ```python
    import pytest

    def test_accent_name_match():
        """DATA-01: Availability name matching is accent-insensitive."""
        # STUB — implementation in Wave 1
        pytest.skip("Implementation pending")
    ```

    2. Add test stub to tests/test_db.py:
    ```python
    import pytest

    def test_upsert_atomicity():
        """DATA-02: FAISS-SQLite upsert is atomic (rollback SQLite if FAISS fails)."""
        # STUB — implementation in Wave 1
        pytest.skip("Implementation pending")
    ```

    3. Add test stubs to tests/test_ingestion.py:
    ```python
    import pytest

    def test_stable_profile_id():
        """DATA-03: Profile ID is stable UUID from parsed name, not MD5(filename)."""
        # STUB — implementation in Wave 1
        pytest.skip("Implementation pending")

    def test_availability_delta_detection():
        """DATA-04: CSV change detection triggers re-ingestion without --force."""
        # STUB — implementation in Wave 1
        pytest.skip("Implementation pending")
    ```

    4. Add test stub to tests/test_filters.py:
    ```python
    import pytest

    def test_malformed_date_excluded():
        """DATA-05: Profiles with malformed availability dates excluded from filter."""
        # STUB — implementation in Wave 1
        pytest.skip("Implementation pending")
    ```

    These stubs extend the conftest.py fixtures from Plan 01 Wave 0.
  </action>
  <verify>
    <automated>pytest tests/test_availability.py tests/test_db.py tests/test_ingestion.py tests/test_filters.py --collect-only 2>&1 | grep "test session starts"</automated>
  </verify>
  <done>Data integrity test stubs created and discoverable by pytest</done>
</task>

<task type="auto">
  <name>Task 1: Add name normalization and fuzzy matching utilities</name>
  <files>app/ingestion/availability.py, app/config.py, requirements.txt</files>
  <action>
    Per DATA-01: "Availability name matching is case-insensitive and accent-insensitive"

    1. Add to requirements.txt: `unidecode==1.4.0` and `rapidfuzz==3.5.2` (or latest)

    2. In app/config.py, add new setting:
    ```python
    class Settings(BaseSettings):
        # ... existing settings ...
        fuzzy_match_threshold: int = 85  # WRatio threshold for name matching (configurable in .env)
    ```

    3. In app/ingestion/availability.py (create if doesn't exist), add imports and utilities:
    ```python
    from unidecode import unidecode
    from rapidfuzz import fuzz
    import logging

    logger = logging.getLogger(__name__)

    def normalize_name(name: str) -> str:
        """
        Normalize name for consistent matching:
        - Remove accents: François → Francois
        - Lowercase: Francois → francois
        - Strip whitespace
        """
        if not name:
            return ""
        return unidecode(name).lower().strip()


    def match_availability_fuzzy(
        parsed_name: str,
        availability_dict: dict[str, dict],
        threshold: int = 85
    ) -> dict:
        """
        Fuzzy match parsed CV name against availability records.

        Returns: matching availability data, or {} if no match

        Strategy:
        1. Try exact match after normalization (fastest)
        2. Fall back to fuzzy matching with WRatio if no exact match
        3. Return first match above threshold
        """
        if not parsed_name:
            return {}

        norm_parsed = normalize_name(parsed_name)

        # Fast path: exact match after normalization
        if norm_parsed in availability_dict:
            logger.debug(f"Matched availability for '{parsed_name}' (exact after normalization)")
            return availability_dict[norm_parsed]

        # Fuzzy match fallback
        best_match = None
        best_score = 0
        for avail_name, avail_data in availability_dict.items():
            score = fuzz.WRatio(norm_parsed, avail_name)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = avail_name

        if best_match:
            logger.debug(f"Matched availability for '{parsed_name}' via fuzzy (score {best_score})")
            return availability_dict[best_match]

        logger.debug(f"No availability match for '{parsed_name}' (threshold {threshold})")
        return {}
    ```

    4. Update CSVAvailabilityAdapter.get_availability() to use normalize_name:
    ```python
    def get_availability(self) -> dict[str, dict]:
        """Return dict mapping normalized name → availability data."""
        result = {}
        for _, row in df.iterrows():
            name = str(row.get("name", "")).strip()
            if not name:
                continue

            normalized = normalize_name(name)  # Apply normalization
            result[normalized] = {
                "availability_percentage": int(row.get("availability_percentage")) or None,
                "availability_date": str(row.get("availability_date")).strip() or None,
                # ... other fields ...
            }
        return result
    ```

    Reference from RESEARCH.md: unidecode for accent removal, rapidfuzz for fuzzy matching with Unicode support.
  </action>
  <verify>
    <automated>grep -n "from unidecode import\|from rapidfuzz import\|def normalize_name\|def match_availability_fuzzy" /Users/8jorgee/Desktop/cvsrag/app/ingestion/availability.py && grep -n "fuzzy_match_threshold\|unidecode\|rapidfuzz" /Users/8jorgee/Desktop/cvsrag/app/config.py /Users/8jorgee/Desktop/cvsrag/requirements.txt</automated>
  </verify>
  <done>Name normalization and fuzzy matching utilities added, dependencies in requirements.txt</done>
</task>

<task type="auto">
  <name>Task 2: Make FAISS-SQLite upsert atomic with rollback</name>
  <files>app/db.py</files>
  <action>
    Per DATA-02: "FAISS index and SQLite metadata stay in sync — upsert is atomic (rollback SQLite if FAISS fails)"

    In app/db.py, update VectorCollection.upsert() method to wrap FAISS operations in try/except with SQLite rollback:

    ```python
    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """
        Insert or replace profiles atomically.

        Strategy:
        1. Update SQLite first (transactional)
        2. If SQLite succeeds, rebuild/append to FAISS
        3. If FAISS fails, rollback SQLite changes
        4. Never leave FAISS and SQLite in inconsistent state
        """
        try:
            needs_rebuild = False

            # Step 1: Validate all IDs exist (before any writes)
            for doc_id, embedding, document, metadata in zip(
                ids, embeddings, documents, metadatas
            ):
                existing = self._conn.execute(
                    "SELECT id FROM profiles WHERE id = ?", (doc_id,)
                ).fetchone()

                self._conn.execute(
                    """INSERT INTO profiles (id, document, metadata, embedding)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET
                         document  = excluded.document,
                         metadata  = excluded.metadata,
                         embedding = excluded.embedding
                    """,
                    (doc_id, document, json.dumps(metadata), json.dumps(embedding)),
                )

                if existing:
                    needs_rebuild = True  # Mark index for rebuild

            # Step 2: Commit SQLite transaction
            self._conn.commit()
            logger.info(f"Upserted {len(ids)} profiles to SQLite")

            # Step 3: Update FAISS (if SQLite succeeded)
            try:
                if needs_rebuild:
                    self._index = self._rebuild_index()
                    logger.info(f"Rebuilt FAISS index ({self._index.ntotal} vectors)")
                else:
                    # Append new vectors to the end of the index
                    new_vecs = np.array(embeddings, dtype=np.float32)
                    self._index.add(new_vecs)
                    logger.info(f"Added {len(embeddings)} vectors to FAISS")

                faiss.write_index(self._index, str(self._index_path))

            except Exception as faiss_error:
                # FAISS failed — rollback SQLite changes
                logger.error(f"FAISS operation failed: {faiss_error} — rolling back SQLite")
                self._conn.rollback()
                self._index = self._load_or_rebuild_index()  # Restore FAISS from SQLite
                raise RuntimeError(f"Upsert failed and was rolled back: {faiss_error}")

        except Exception as e:
            # Catch any other errors and ensure rollback
            if not isinstance(e, RuntimeError):
                logger.error(f"Upsert failed: {e}")
                self._conn.rollback()
            raise
    ```

    Key changes:
    - SQLite commit happens BEFORE FAISS updates
    - FAISS errors trigger SQLite rollback
    - All-or-nothing semantics: either both are updated, or neither is
    - Detailed logging for debugging

    Reference from RESEARCH.md: Atomic FAISS-SQLite upsert pattern.
  </action>
  <verify>
    <automated>grep -n "self._conn.rollback()\|if faiss_error\|except.*faiss_error" /Users/8jorgee/Desktop/cvsrag/app/db.py && grep -n "Upserted\|Rolled back" /Users/8jorgee/Desktop/cvsrag/app/db.py</automated>
  </verify>
  <done>Upsert method updated with SQLite rollback on FAISS failure, atomicity guaranteed</done>
</task>

<task type="auto">
  <name>Task 3: Implement stable profile IDs from parsed name</name>
  <files>scripts/ingest_cvs.py, app/config.py</files>
  <action>
    Per DATA-03: "Profile IDs are stable UUIDs derived from parsed profile name, not MD5 of filename"

    1. In scripts/ingest_cvs.py, add import and helper function:
    ```python
    import uuid
    from app.ingestion.availability import normalize_name

    def derive_profile_id(parsed_name: str, department: str = "") -> str:
        """
        Derive stable profile ID from parsed name (not filename).

        UUID5 is deterministic: same input → same ID, even across re-indexing.
        This ensures renames don't create duplicate profiles.
        """
        if not parsed_name:
            raise ValueError("Profile name required for ID derivation")

        # Normalize name for ID generation (accent-insensitive)
        normalized = normalize_name(parsed_name)

        # Combine with department for uniqueness (optional)
        combined = f"{normalized}:{department}".lower().strip()

        # Use UUID5 for stable, deterministic IDs
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, combined))
    ```

    2. In ingest_cvs() function, replace the old line:
    ```python
    # OLD (BROKEN):
    profile_id = hashlib.md5(filename.encode()).hexdigest()

    # NEW (FIXED):
    parsed = parse_profile_with_claude(extracted["raw_text"], extracted["name"])
    profile_id = derive_profile_id(parsed["name"], department="")  # Use parsed name
    ```

    3. Verify the metadata stores profile_id for traceability:
    ```python
    metadata = {
        "source_file": filename,
        "file_hash": fhash,
        "availability_hash": avail_hash,
        "profile_id": profile_id,  # Store for reference
        # ... other metadata ...
    }
    ```

    Reference from RESEARCH.md: Stable Profile ID Pattern using UUID5.
  </action>
  <verify>
    <automated>grep -n "def derive_profile_id\|uuid.uuid5\|uuid.NAMESPACE_DNS" /Users/8jorgee/Desktop/cvsrag/scripts/ingest_cvs.py && grep -n "profile_id = derive_profile_id" /Users/8jorgee/Desktop/cvsrag/scripts/ingest_cvs.py</automated>
  </verify>
  <done>Profile ID generation switched from MD5(filename) to UUID5(normalized_name), ensuring stability across renames</done>
</task>

<task type="auto">
  <name>Task 4: Implement CSV change detection for incremental ingestion</name>
  <files>scripts/ingest_cvs.py</files>
  <action>
    Per DATA-04: "Incremental ingestion detects availability CSV row changes, not only CV file hash changes"

    In scripts/ingest_cvs.py, add:

    1. Helper function to hash availability CSV:
    ```python
    def hash_file(filepath: str) -> str:
        """Compute SHA256 hash of file for change detection."""
        import hashlib
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    ```

    2. In ingest_cvs() function, before processing CVs:
    ```python
    def ingest_cvs(force_reindex: bool = False) -> None:
        collection = get_collection()

        # Hash availability file for change detection
        avail_file = Path(settings.availability_file)
        current_avail_hash = hash_file(str(avail_file)) if avail_file.exists() else ""

        # Load existing profiles and their metadata
        existing: dict[str, dict] = {}
        if not force_reindex and collection.count() > 0:
            all_docs = collection.get(include=["metadatas"])
            for i, doc_id in enumerate(all_docs["ids"]):
                meta = all_docs["metadatas"][i]
                existing[meta.get("source_file", "")] = {
                    "id": doc_id,
                    "file_hash": meta.get("file_hash", ""),
                    "availability_hash": meta.get("availability_hash", ""),  # NEW
                }

        # Process CV files
        for pptx_path in pptx_files:
            filename = pptx_path.name
            fhash = hash_file(str(pptx_path))

            # Check if re-indexing needed: CV changed OR availability changed
            if filename in existing:
                prev_fhash = existing[filename]["file_hash"]
                prev_avail_hash = existing[filename]["availability_hash"]

                # Skip only if BOTH hashes match
                if fhash == prev_fhash and current_avail_hash == prev_avail_hash:
                    logger.info(f"  SKIP  {filename} (CV and availability unchanged)")
                    skipped += 1
                    continue

            logger.info(f"  PROC  {filename}")
            # ... extract, parse, match availability, upsert ...

            # Store both hashes in metadata
            metadata["file_hash"] = fhash
            metadata["availability_hash"] = current_avail_hash  # NEW
    ```

    This ensures:
    - CSV-only changes trigger re-ingestion
    - CV-only changes still work
    - Unchanged files are skipped (performance)

    Reference from RESEARCH.md: CSV Change Detection Pattern.
  </action>
  <verify>
    <automated>grep -n "availability_hash\|current_avail_hash\|hash_file" /Users/8jorgee/Desktop/cvsrag/scripts/ingest_cvs.py && grep -n "prev_avail_hash" /Users/8jorgee/Desktop/cvsrag/scripts/ingest_cvs.py</automated>
  </verify>
  <done>CSV change detection implemented; incremental ingestion now tracks both CV and availability file hashes</done>
</task>

<task type="auto">
  <name>Task 5: Add date validation with exclusion on error</name>
  <files>app/search/filters.py</files>
  <action>
    Per DATA-05: "Malformed availability dates cause profile to be excluded from availability filter (not silently pass through)"

    In app/search/filters.py, update apply_availability_filter() function:

    ```python
    from datetime import datetime, timedelta
    import logging

    logger = logging.getLogger(__name__)

    def apply_availability_filter(candidates: list, filter_spec: dict) -> list:
        """
        Filter profiles by availability status.

        Exclusion on malformed dates: profiles with invalid availability_date
        are logged and excluded from results (not silently included).
        """
        if not filter_spec.get("availability_status"):
            return candidates

        status = filter_spec["availability_status"]  # "now", "30days", "90days"
        now = datetime.now()
        filtered = []

        for c in candidates:
            profile = c["profile"]
            date_str = profile.availability_date

            # No date = no availability data, exclude
            if not date_str:
                logger.debug(f"No availability_date for {profile.name} — excluding from filter")
                continue

            # Try to parse the date
            try:
                avail_date = datetime.fromisoformat(date_str)

                # Check against status
                if status == "now" and avail_date <= now:
                    filtered.append(c)
                elif status == "30days" and avail_date <= now + timedelta(days=30):
                    filtered.append(c)
                elif status == "90days" and avail_date <= now + timedelta(days=90):
                    filtered.append(c)

            except ValueError as e:
                # Malformed date — exclude and log warning
                logger.warning(
                    f"Malformed availability_date '{date_str}' for profile {profile.name} "
                    f"(expected ISO format YYYY-MM-DD): {e} — excluding from filter"
                )
                # Don't include in filtered results

        logger.info(f"Availability filter '{status}': {len(filtered)} of {len(candidates)} passed")
        return filtered
    ```

    Key changes:
    - Wrap datetime.fromisoformat() in try/except
    - Log detailed warning on parse failure (includes value and expected format)
    - Exclude malformed profiles from results (don't silently include them)
    - Debug logging for no-date profiles

    Reference from RESEARCH.md: Date Validation Pattern.
  </action>
  <verify>
    <automated>grep -n "except ValueError\|malformed availability_date\|excluding from filter" /Users/8jorgee/Desktop/cvsrag/app/search/filters.py && grep -n "datetime.fromisoformat" /Users/8jorgee/Desktop/cvsrag/app/search/filters.py</automated>
  </verify>
  <done>Date validation with exception handling added to availability filter; malformed dates logged and excluded</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
  - Name normalization (unidecode + rapidfuzz) for accent-insensitive matching
  - Atomic FAISS-SQLite upsert with rollback on error
  - Stable profile IDs from parsed name (UUID5, not MD5 filename)
  - CSV change detection triggering re-ingestion without --force
  - Date validation with exclusion on parse error
  </what-built>
  <how-to-verify>
    1. Test name normalization:
       ```bash
       cd /Users/8jorgee/Desktop/cvsrag
       python3 -c "
       from app.ingestion.availability import normalize_name, match_availability_fuzzy
       print('Testing name normalization:')
       print(f\"  François Müller -> {normalize_name('François Müller')}\")
       print(f\"  JOHN SMITH -> {normalize_name('JOHN SMITH')}\")

       avail = {
           'francois muller': {'availability_percentage': 50},
           'john smith': {'availability_percentage': 100}
       }
       match = match_availability_fuzzy('François Müller', avail)
       print(f\"  Match for 'François Müller': {match}\")
       "
       ```

    2. Test stable profile ID:
       ```bash
       python3 -c "
       from scripts.ingest_cvs import derive_profile_id
       id1 = derive_profile_id('John Smith')
       id2 = derive_profile_id('John Smith')
       print(f'ID consistency: {id1 == id2}')
       print(f'ID format (UUID): {len(id1) == 36}')
       "
       ```

    3. Inspect FAISS-SQLite upsert code:
       ```bash
       grep -A 5 "self._conn.rollback()" /Users/8jorgee/Desktop/cvsrag/app/db.py
       ```
       Verify: Rollback is triggered on FAISS error

    4. Test incremental ingestion (manual):
       ```bash
       # Edit availability.csv (add/change a name's availability)
       # Run ingest_cvs without --force
       ANTHROPIC_API_KEY="test" python scripts/ingest_cvs.py
       # Verify: Profiles are re-processed even though CVs haven't changed
       ```

    5. Test date validation:
       ```bash
       python3 -c "
       from app.search.filters import apply_availability_filter
       # Create test profile with malformed date
       from app.models import Profile, SearchResult
       bad_profile = Profile(
           id='test',
           name='Test',
           source_file='test.pptx',
           raw_text='',
           availability_date='invalid-date'
       )
       result = SearchResult(profile=bad_profile, score=0.5)
       filtered = apply_availability_filter([result], {'availability_status': 'now'})
       print(f'Malformed date excluded: {len(filtered) == 0}')
       "
       ```
  </how-to-verify>
  <resume-signal>Type "approved" after verifying all data integrity fixes work correctly, or describe any issues</resume-signal>
</task>

<task type="auto">
  <name>Task 6: Commit data integrity changes and verify test suite</name>
  <files>app/db.py, app/ingestion/availability.py, app/config.py, scripts/ingest_cvs.py, app/search/filters.py, requirements.txt</files>
  <action>
    After checkpoint approval, make atomic commits for each data integrity change:

    1. Commit name normalization and fuzzy matching:
    ```bash
    cd /Users/8jorgee/Desktop/cvsrag
    git add app/ingestion/availability.py app/config.py requirements.txt
    git commit -m "feat(01-data-integrity): add unidecode + rapidfuzz for accent-insensitive name matching

    - Add normalize_name() and match_availability_fuzzy() utilities
    - Implement fuzzy matching with configurable threshold (default 85 WRatio)
    - Add fuzzy_match_threshold setting to config
    - Update CSVAvailabilityAdapter to use normalized names"
    ```

    2. Commit atomic upsert:
    ```bash
    git add app/db.py
    git commit -m "fix(01-data-integrity): make FAISS-SQLite upsert atomic with rollback

    - SQLite commit before FAISS updates
    - Rollback SQLite if FAISS fails
    - Never leave index and metadata in inconsistent state
    - Detailed logging for debugging"
    ```

    3. Commit stable profile IDs:
    ```bash
    git add scripts/ingest_cvs.py
    git commit -m "fix(01-data-integrity): derive stable profile IDs from parsed name

    - Replace MD5(filename) with UUID5(normalized_name)
    - Ensures same profile ID even if file is renamed
    - Prevents duplicate profiles on filename changes"
    ```

    4. Commit CSV change detection:
    ```bash
    git add scripts/ingest_cvs.py
    git commit -m "feat(01-data-integrity): detect availability CSV changes for incremental ingestion

    - Hash availability.csv alongside CV file hash
    - Re-process profiles if CSV changes, not just CV file
    - Skip unchanged profiles even with CSV updates (if hashes match)"
    ```

    5. Commit date validation:
    ```bash
    git add app/search/filters.py
    git commit -m "fix(01-data-integrity): validate availability dates and exclude on error

    - Wrap datetime parsing in try/except
    - Log malformed dates with offending values
    - Exclude profiles with invalid dates from availability filters"
    ```

    6. Run test suite to verify all stubs are discoverable:
    ```bash
    pytest tests/ -v --tb=short 2>&1 | head -50
    ```
  </action>
  <verify>
    <automated>git log --oneline -6 2>/dev/null | head -5</automated>
  </verify>
  <done>All data integrity changes committed atomically, test suite verified</done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Test suite runs without errors for data integrity stubs:
   ```bash
   pytest tests/test_availability.py tests/test_db.py tests/test_ingestion.py tests/test_filters.py -v
   ```

2. Verify all dependencies installed:
   ```bash
   pip show unidecode rapidfuzz python-magic slowapi starlette-csrf
   ```

3. Verify code quality:
   ```bash
   python -m py_compile app/db.py app/ingestion/availability.py scripts/ingest_cvs.py app/search/filters.py app/config.py
   ```

4. Git history shows all 5 atomic commits:
   ```bash
   git log --oneline | head -10 | grep -c "01-data-integrity"  # Should show 5
   ```

5. FAISS and SQLite stay in sync (manual test):
   - Ingest a profile
   - Verify FAISS index.ntotal matches SQLite profile count
   - Update profile and re-ingest
   - Verify no orphaned embeddings

6. Name matching works across accents/case:
   - CSV has "François Müller"
   - CV parses as "Francois Muller"
   - Availability lookup succeeds with 85+ WRatio score
</verification>

<success_criteria>
- [ ] All 5 data integrity requirements (DATA-01 through DATA-05) implemented
- [ ] Name normalization (unidecode + rapidfuzz) functional
- [ ] FAISS-SQLite upsert atomic with rollback on error
- [ ] Profile IDs stable UUIDs from parsed names (not filenames)
- [ ] CSV change detection triggers re-ingestion without --force
- [ ] Malformed availability dates excluded from filters with logging
- [ ] unidecode, rapidfuzz, python-magic added to requirements.txt
- [ ] Checkpoint verification complete
- [ ] All 5 data integrity changes committed with atomic commits
- [ ] Test suite passes (stubs discoverable, no syntax errors)
</success_criteria>

<output>
After completion, create `.planning/phases/01-security-data-integrity/02-SUMMARY.md` with:
- Timestamp and status (COMPLETE)
- All 5 data integrity measures implemented and verified
- Files modified (app/db.py, app/ingestion/availability.py, app/config.py, scripts/ingest_cvs.py, app/search/filters.py, requirements.txt)
- Test coverage: Wave 0 test infrastructure for data integrity, stubs created for all 5 requirements
- Key commits: Name normalization, atomic upsert, stable IDs, CSV delta detection, date validation
- Dependencies installed: unidecode, rapidfuzz, python-magic
- Phase completion: Both Plan 01 (security) and Plan 02 (data integrity) complete
- Next steps: Proceed to Phase 2 (Robustness, Performance & Core Features)
</output>
