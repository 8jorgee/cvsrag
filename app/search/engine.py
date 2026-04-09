import json
import logging
import re

import google.generativeai as genai

from app.config import settings
from app.db import get_collection
from app.models import Profile, SearchQuery, SearchResult
from app.search.embeddings import generate_embedding
from app.search.filters import apply_filters

logger = logging.getLogger(__name__)


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
    logger.error(f"Failed to parse JSON from {context}. Raw content:\n{content[:500]}...")
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


def search(query: SearchQuery) -> list[SearchResult]:
    collection = get_collection()
    count = collection.count()

    if count == 0:
        return []

    query_embedding = generate_embedding(query.query)
    n_results = min(settings.top_k_results, count)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    if not results["ids"][0]:
        return []

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
        return []

    if query.mode == "smart":
        top = candidates[: settings.rerank_top_n]
        return _claude_rerank(query.query, top)
    else:
        return [SearchResult(profile=c["profile"], score=c["score"]) for c in candidates]


def _claude_rerank(query: str, candidates: list[dict]) -> list[SearchResult]:
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name=settings.llm_model,
        system_instruction=(
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
        ),
    )

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
        response = model.generate_content(
            f'Search query: "{query}"\n\n'
            f"Candidates:\n{''.join(profiles_text)}\n"
            "Rank all candidates and explain matches."
        )

        content = response.text
        rankings = parse_json_response(content, context="Claude reranking response")

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
        logger.error(f"Claude reranking failed to parse JSON: {e}")
        return [SearchResult(profile=c["profile"], score=c["score"]) for c in candidates]
    except Exception as e:
        logger.error(f"Claude reranking failed: {e}")
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
        logger.error(f"Error fetching profile {profile_id}: {e}")
        return None
