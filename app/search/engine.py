import json
import re
import sqlite3
import uuid
from datetime import datetime

import anthropic
import groq
import ollama
import structlog

from app.config import settings
from app.db import get_collection
from app.models import Profile, SearchQuery, SearchResult
from app.search.embeddings import generate_embedding
from app.search.filters import apply_filters

logger = structlog.get_logger()


def parse_json_response(content: str, context: str = "") -> dict | list:
    """Parse JSON response from LLM, handling markdown-wrapped or clean JSON.

    Strategy 1: Try json.loads() directly (fast path for clean responses)
    Strategy 2: Extract bracketed content with regex (handles markdown fences)
    Strategy 3: Raise ValueError with logged context (no silent failures)

    Args:
        content: Raw response text from LLM
        context: Description of where this content came from (for logging)

    Returns:
        dict or list parsed from JSON

    Raises:
        ValueError: If JSON cannot be parsed from content
    """
    # Strategy 1: Direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract bracketed JSON
    for pattern in [r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", r"\[.*\]"]:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue

    # Strategy 3: Give up with context
    logger.error("Failed to parse JSON", context=context, content_preview=content[:500])
    raise ValueError(f"Could not parse JSON from {context}: {content[:200]}")


_TOKEN_RE = re.compile(r"[a-z0-9+#.\-]{3,}")
_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "are",
    "was",
    "were",
    "into",
    "your",
    "you",
    "has",
    "have",
    "who",
    "looking",
    "need",
    "profile",
    "consultant",
}


def _metadata_to_profile(doc_id: str, metadata: dict, document: str) -> Profile:
    return Profile(
        id=doc_id,
        name=metadata.get("name", "Unknown"),
        source_file=metadata.get("source_file", ""),
        raw_text=document,
        skills=json.loads(metadata.get("skills", "[]")),
        certifications=json.loads(metadata.get("certifications", "[]")),
        experience_summary=metadata.get("experience_summary", ""),
        domains=json.loads(metadata.get("domains", "[]")),
        languages=json.loads(metadata.get("languages", "[]")),
        education=metadata.get("education", ""),
        years_of_experience=metadata.get("years_of_experience") or None,
        current_project=metadata.get("current_project") or None,
        availability_date=metadata.get("availability_date") or None,
        availability_percentage=metadata.get("availability_percentage") or None,
        location=metadata.get("location") or None,
        grade=metadata.get("grade") or None,
        last_updated=metadata.get("last_updated", ""),
    )


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _extract_query_terms(text: str) -> list[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in _STOPWORDS]


def _keyword_match_score(query_text: str, profile: Profile) -> float:
    terms = _extract_query_terms(query_text)
    if not terms:
        return 0.0

    combined_text = " ".join(
        [
            profile.name,
            profile.raw_text,
            profile.experience_summary,
            profile.education,
            profile.grade or "",
            profile.location or "",
        ]
    ).lower()
    structured_text = " ".join(
        profile.skills + profile.certifications + profile.domains + profile.languages
    ).lower()

    matched_in_text = sum(1 for t in terms if t in combined_text)
    matched_in_structured = sum(1 for t in terms if t in structured_text)
    coverage = matched_in_text / len(terms)
    structured_coverage = matched_in_structured / len(terms)

    exact_phrase_bonus = 0.2 if query_text.strip().lower() in combined_text else 0.0

    bigrams = [f"{terms[i]} {terms[i + 1]}" for i in range(len(terms) - 1)]
    if bigrams:
        bigram_hits = sum(1 for bg in bigrams if bg in combined_text)
        bigram_bonus = 0.15 * (bigram_hits / len(bigrams))
    else:
        bigram_bonus = 0.0

    role_bonus = 0.0
    if "architect" in terms and ("solution" in terms or "solutions" in terms):
        if "solution architect" in combined_text or "solutions architect" in combined_text:
            role_bonus = 0.15

    score = (0.5 * coverage) + (0.25 * structured_coverage) + exact_phrase_bonus + bigram_bonus + role_bonus
    return _clamp01(score)


def _blend_scores(semantic_score: float, keyword_score: float, has_query_terms: bool) -> float:
    if not has_query_terms:
        return _clamp01(semantic_score)
    return _clamp01((0.7 * semantic_score) + (0.3 * keyword_score))


def _calibrate_display_score(raw_score: float) -> float:
    """Map raw 0-1 relevance to a more human-friendly confidence curve."""
    score = _clamp01(raw_score)
    return _clamp01(1.0 - ((1.0 - score) ** 2))


def _normalize_llm_score(score: object) -> float | None:
    if not isinstance(score, (int, float)):
        return None
    numeric = float(score)
    if numeric > 1.0:
        numeric = numeric / 100.0
    return _clamp01(numeric)


def search(query: SearchQuery, page: int = 1, page_size: int = 10) -> dict:
    """Search for profiles with pagination support.

    Args:
        query: SearchQuery object with search parameters
        page: Page number (1-indexed), defaults to 1
        page_size: Number of results per page, defaults to 10

    Returns:
        dict with keys:
            - results: list[SearchResult] for the current page
            - total_count: int total number of matching profiles
            - page: int current page number
            - page_size: int results per page
            - has_more: bool whether more pages exist
    """
    # Validate pagination parameters
    page = max(1, page)
    page_size = max(1, page_size)

    collection = get_collection()
    count = collection.count()

    if count == 0:
        return {
            "results": [],
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "has_more": False,
        }

    query_embedding = generate_embedding(query.query)
    n_results = min(settings.top_k_results, count)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    if not results["ids"][0]:
        return {
            "results": [],
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "has_more": False,
        }

    query_terms = _extract_query_terms(query.query)
    has_query_terms = len(query_terms) > 0
    candidates = []
    for i, doc_id in enumerate(results["ids"][0]):
        metadata = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        profile = _metadata_to_profile(doc_id, metadata, results["documents"][0][i])
        semantic_score = _clamp01(1 - distance)
        keyword_score = _keyword_match_score(query.query, profile)
        blended_score = _blend_scores(semantic_score, keyword_score, has_query_terms)
        candidates.append(
            {
                "profile": profile,
                "base_score": blended_score,
                "score": _calibrate_display_score(blended_score),
            }
        )

    candidates = apply_filters(candidates, query)

    if not candidates:
        return {
            "results": [],
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "has_more": False,
        }

    if query.mode == "smart":
        top = candidates[: settings.rerank_top_n]
        all_results = _claude_rerank(query.query, top)
    else:
        all_results = [SearchResult(profile=c["profile"], score=c["score"]) for c in candidates]

    # Apply pagination to final results
    total_count = len(all_results)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_results = all_results[start_idx:end_idx]
    has_more = len(all_results) > end_idx

    return {
        "results": paginated_results,
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
    }


def _call_llm(system: str, user: str) -> str:
    """Call the configured LLM backend and return the response text."""
    if settings.llm_backend == "groq":
        client = groq.Groq(api_key=settings.groq_api_key)
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=2048,
        )
        return response.choices[0].message.content
    elif settings.llm_backend == "ollama":
        response = ollama.Client(host=settings.ollama_base_url).chat(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.message.content
    else:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text


_RERANK_SYSTEM = (
    "You are a talent matching expert for a consulting firm. "
    "Rank candidate profiles by relevance to the search query.\n\n"
    "Important semantic rules:\n"
    "- 'cloud experience' matches Azure, AWS, GCP\n"
    "- 'AI/ML' matches machine learning, deep learning, neural networks, LLMs\n"
    "- 'data engineering' matches Databricks, Spark, ETL, pipelines\n"
    "- Consider experience depth, not just keyword presence\n\n"
    "Return a JSON array only, no other text:\n"
    "[\n"
    "  {\n"
    '    "profile_index": 1,\n'
    '    "score": 0.95,\n'
    '    "reasoning": "Strong match because...",\n'
    '    "gaps": "Missing X...",\n'
    '    "highlighted_skills": ["skill1", "skill2"]\n'
    "  }\n"
    "]"
)


def _claude_rerank(query: str, candidates: list[dict]) -> list[SearchResult]:
    profiles_text = []
    for i, c in enumerate(candidates):
        p = c["profile"]
        profiles_text.append(
            f"Profile {i + 1}: {p.name}\n"
            f"- Base relevance score: {int(c.get('score', 0) * 100)}%\n"
            f"- Grade: {p.grade or 'Unknown'}\n"
            f"- Skills: {', '.join(p.skills[:15])}\n"
            f"- Certifications: {', '.join(p.certifications[:5])}\n"
            f"- Domains: {', '.join(p.domains[:5])}\n"
            f"- Experience: {p.experience_summary[:300]}\n"
            f"- Availability: {p.availability_percentage or 0}% from {p.availability_date or 'TBD'}\n"
            f"- Location: {p.location or 'Unknown'}\n"
            f"- Current project: {p.current_project or 'None (bench)'}\n"
        )

    try:
        content = _call_llm(
            system=_RERANK_SYSTEM,
            user=(
                f'Search query: "{query}"\n\n'
                f"Candidates:\n{''.join(profiles_text)}\n"
                "Rank all candidates and explain matches."
            ),
        )
        rankings = parse_json_response(content, context="LLM reranking response")

        results = []
        used_indices: set[int] = set()
        for ranking in sorted(rankings, key=lambda x: x.get("score", 0), reverse=True):
            idx = ranking.get("profile_index", 0) - 1
            if 0 <= idx < len(candidates):
                c = candidates[idx]
                used_indices.add(idx)
                llm_score = _normalize_llm_score(ranking.get("score"))
                blended_raw = (
                    (0.7 * llm_score) + (0.3 * c.get("base_score", c["score"]))
                    if llm_score is not None
                    else c.get("base_score", c["score"])
                )
                results.append(
                    SearchResult(
                        profile=c["profile"],
                        score=_calibrate_display_score(blended_raw),
                        match_reasoning=ranking.get("reasoning"),
                        gaps=ranking.get("gaps"),
                        highlighted_skills=ranking.get("highlighted_skills", []),
                    )
                )

        # Keep candidates missing from LLM output instead of dropping them.
        for i, c in enumerate(candidates):
            if i in used_indices:
                continue
            results.append(
                SearchResult(
                    profile=c["profile"],
                    score=c["score"],
                )
            )

        return sorted(results, key=lambda r: r.score, reverse=True)

    except ValueError as e:
        logger.error("Claude reranking failed to parse JSON", error=str(e))
        return [SearchResult(profile=c["profile"], score=c["score"]) for c in candidates]
    except Exception as e:
        logger.error("Claude reranking failed", error=str(e))
        return [SearchResult(profile=c["profile"], score=c["score"]) for c in candidates]


def get_all_skills() -> list[str]:
    """Return deduplicated list of all skills across indexed profiles."""
    collection = get_collection()
    if collection.count() == 0:
        return []
    all_docs = collection.get(include=["metadatas"])
    skills_set: set[str] = set()
    for meta in all_docs["metadatas"]:
        skills_set.update(json.loads(meta.get("skills", "[]")))
    return sorted(skills_set)


def get_all_certifications() -> list[str]:
    collection = get_collection()
    if collection.count() == 0:
        return []
    all_docs = collection.get(include=["metadatas"])
    certs_set: set[str] = set()
    for meta in all_docs["metadatas"]:
        certs_set.update(json.loads(meta.get("certifications", "[]")))
    return sorted(certs_set)


def get_all_grades() -> list[str]:
    collection = get_collection()
    if collection.count() == 0:
        return []
    all_docs = collection.get(include=["metadatas"])
    grades = {meta.get("grade", "") for meta in all_docs["metadatas"] if meta.get("grade")}
    return sorted(grades)


def get_all_locations() -> list[str]:
    collection = get_collection()
    if collection.count() == 0:
        return []
    all_docs = collection.get(include=["metadatas"])
    locations = {meta.get("location", "") for meta in all_docs["metadatas"] if meta.get("location")}
    return sorted(locations)


def get_profile_by_id(profile_id: str) -> Profile | None:
    collection = get_collection()
    try:
        result = collection.get(ids=[profile_id], include=["documents", "metadatas"])
        if not result["ids"]:
            return None
        return _metadata_to_profile(
            result["ids"][0], result["metadatas"][0], result["documents"][0]
        )
    except Exception as e:
        logger.error("Error fetching profile", profile_id=profile_id, error=str(e))
        return None


# ─── Session Management ─────────────────────────────────────────────────────

def get_or_create_session(db_conn: sqlite3.Connection, session_id: str | None) -> str:
    """Get or create a session.

    Args:
        db_conn: SQLite connection
        session_id: Existing session ID or None

    Returns:
        Valid session ID (existing or newly created)
    """
    now = datetime.now().isoformat()

    # Check if session exists
    if session_id:
        row = db_conn.execute(
            "SELECT id FROM search_sessions WHERE id = ?",
            (session_id,)
        ).fetchone()
        if row:
            # Update last_accessed timestamp
            db_conn.execute(
                "UPDATE search_sessions SET last_accessed = ? WHERE id = ?",
                (now, session_id)
            )
            db_conn.commit()
            return session_id

    # Create new session
    new_session_id = str(uuid.uuid4())
    db_conn.execute(
        "INSERT INTO search_sessions (id, created_at, last_accessed) VALUES (?, ?, ?)",
        (new_session_id, now, now)
    )
    db_conn.commit()
    return new_session_id


def log_search_query(
    db_conn: sqlite3.Connection,
    session_id: str,
    query: SearchQuery,
    results_count: int
) -> None:
    """Log a search query to the database.

    Automatically truncates session history to last 20 queries.

    Args:
        db_conn: SQLite connection
        session_id: Session ID
        query: SearchQuery object
        results_count: Number of results returned
    """
    now = datetime.now().isoformat()
    filters = {
        "skills": query.skills,
        "certifications": query.certifications,
        "skills_any": query.skills_any,
        "certifications_any": query.certifications_any,
        "availability_status": query.availability_status,
        "availability_percentage_min": query.availability_percentage_min,
        "grade": query.grade,
        "location": query.location,
    }

    db_conn.execute(
        """INSERT INTO search_queries
           (session_id, query_text, mode, filters_json, created_at, results_count)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, query.query, query.mode, json.dumps(filters), now, results_count)
    )
    db_conn.commit()

    # Truncate to last 20 queries for this session
    db_conn.execute(
        """DELETE FROM search_queries
           WHERE session_id = ? AND id NOT IN (
               SELECT id FROM search_queries
               WHERE session_id = ?
               ORDER BY created_at DESC
               LIMIT 20
           )""",
        (session_id, session_id)
    )
    db_conn.commit()


def get_search_history(db_conn: sqlite3.Connection, session_id: str) -> list[dict]:
    """Get search history for a session.

    Args:
        db_conn: SQLite connection
        session_id: Session ID

    Returns:
        List of dicts with keys: id, query_text, mode, created_at, results_count
    """
    rows = db_conn.execute(
        """SELECT id, query_text, mode, created_at, results_count
           FROM search_queries
           WHERE session_id = ?
           ORDER BY created_at DESC
           LIMIT 20""",
        (session_id,)
    ).fetchall()

    return [
        {
            "id": row[0],
            "query_text": row[1],
            "mode": row[2],
            "created_at": row[3],
            "results_count": row[4],
        }
        for row in rows
    ]


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
    collection = get_collection()

    # Check if we have profiles
    total_profiles = collection.count()
    if total_profiles == 0:
        return {"error": "No profiles available"}

    # Clamp team size to valid range
    team_size = max(1, min(team_size, total_profiles))

    # Fetch all profiles
    all_docs = collection.get(include=["metadatas", "documents"])
    if not all_docs["ids"]:
        return {"error": "Failed to fetch profiles"}

    # Build profiles text for Claude
    profiles_text = []
    id_to_profile = {}  # Map profile IDs to metadata for later lookup

    for i, doc_id in enumerate(all_docs["ids"]):
        metadata = all_docs["metadatas"][i]
        name = metadata.get("name", "Unknown")
        skills = json.loads(metadata.get("skills", "[]"))
        certifications = json.loads(metadata.get("certifications", "[]"))
        experience_summary = metadata.get("experience_summary", "")
        grade = metadata.get("grade", "Unknown")
        availability = metadata.get("availability_percentage", 0) or 0

        id_to_profile[doc_id] = {
            "name": name,
            "skills": skills,
            "certifications": certifications,
            "experience_summary": experience_summary,
            "grade": grade,
            "availability": availability,
        }

        profiles_text.append(
            f"ID: {doc_id}\n"
            f"Name: {name}\n"
            f"Grade: {grade}\n"
            f"Skills: {', '.join(skills[:20])}\n"
            f"Certifications: {', '.join(certifications[:10])}\n"
            f"Experience: {experience_summary[:300]}\n"
            f"Availability: {availability}%\n"
        )

    profiles_full = "\n---\n".join(profiles_text)

    # Build Claude prompt
    system_prompt = (
        "You are an expert talent matcher for consulting projects. "
        "Suggest the best team from available profiles based on project needs and skill requirements. "
        "Return ONLY valid JSON with team member suggestions and reasoning. "
        "Focus on experience depth, complementary skills, and project fit."
    )

    user_prompt = (
        f"Project Description:\n{project_description}\n\n"
        f"Required Skills: {', '.join(required_skills)}\n\n"
        f"Desired Team Size: {team_size}\n\n"
        f"Available Profiles:\n{profiles_full}\n\n"
        f"Return JSON (no markdown, no other text) with this exact structure:\n"
        f'{{\n'
        f'  "team": [\n'
        f'    {{\n'
        f'      "profile_id": "uuid-string",\n'
        f'      "profile_name": "Full Name",\n'
        f'      "role": "Suggested Role",\n'
        f'      "reasoning": "Why this person fits",\n'
        f'      "gaps": "Skill gaps or limitations",\n'
        f'      "fit_score": 0.85\n'
        f'    }}\n'
        f'  ],\n'
        f'  "team_summary": "Overall assessment of the team composition"\n'
        f'}}'
    )

    try:
        response = _call_llm(system=system_prompt, user=user_prompt)
        suggestion = parse_json_response(response, context="Team composition suggestion")

        # Validate response structure
        if not isinstance(suggestion, dict):
            return {"error": "Invalid response format from Claude"}

        team = suggestion.get("team", [])
        team_summary = suggestion.get("team_summary", "")

        # Validate and normalize team member scores
        for member in team:
            if "fit_score" in member and isinstance(member["fit_score"], (int, float)):
                member["fit_score"] = _clamp01(float(member["fit_score"]))
            else:
                member["fit_score"] = 0.5

        return {
            "team": team,
            "team_summary": team_summary,
            "error": None,
        }

    except (ValueError, json.JSONDecodeError) as e:
        logger.error("Team composition JSON parsing failed", error=str(e))
        return {"error": f"Claude response parsing failed: {str(e)}"}
    except Exception as e:
        logger.error("Team composition suggestion failed", error=str(e))
        return {"error": f"Team composition failed: {str(e)}"}
