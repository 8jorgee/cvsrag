import json
import logging
import re

import google.generativeai as genai

from app.config import settings

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

    # Strategy 2: Extract bracketed JSON (for objects: {}, for arrays: [])
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


_SYSTEM_PROMPT = """\
You are a CV parsing expert for a consulting firm. Extract structured information from the provided CV text.

Return ONLY a valid JSON object with these fields:
{
  "name": "Full name (use the hint if not found in text)",
  "skills": ["technical skills, tools, frameworks, platforms"],
  "certifications": ["official certifications, e.g. AZ-900, AWS Solutions Architect"],
  "experience_summary": "2-3 sentence summary of their professional experience",
  "domains": ["domain expertise, e.g. cloud computing, data engineering, machine learning"],
  "languages": ["programming languages AND spoken languages"],
  "education": "highest degree and institution",
  "years_of_experience": <integer or null>
}

Be thorough with skills — include all mentioned technologies, tools, and platforms.
Do not include markdown, only return raw JSON.\
"""


def chunk_slides_to_16k(slides_content: list[str]) -> str:
    """Chunk slides to fit within 16,000 characters, respecting slide boundaries.

    Args:
        slides_content: List of slide text strings

    Returns:
        Concatenated text of slides up to 16,000 character limit (never cuts mid-slide)
    """
    truncated_text = ""
    for slide in slides_content:
        if len(truncated_text) + len(slide) <= 16_000:
            truncated_text += slide + "\n"
        else:
            break  # Stop at 16,000 char boundary (never cut mid-slide)
    return truncated_text


def parse_profile_with_claude(
    raw_text: str, slides_content: list[str], name_hint: str
) -> dict:
    """Call Gemini to parse raw CV text into structured profile fields.

    Args:
        raw_text: Full raw text from PPTX
        slides_content: List of slide text strings for boundary-respecting chunking
        name_hint: Name hint from filename
    """
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name=settings.llm_model,
        system_instruction=_SYSTEM_PROMPT,
    )

    # Slide-boundary chunking: concatenate slides until 16,000 chars
    truncated_text = chunk_slides_to_16k(slides_content)

    if not truncated_text.strip():
        # Fallback: use raw_text if no slides
        truncated_text = raw_text[:16_000]

    try:
        response = model.generate_content(
            f"Name hint (from filename): {name_hint}\n\nCV Text:\n{truncated_text}"
        )

        content = response.text.strip()
        return parse_json_response(content, context=f"Profile parsing for {name_hint}")

    except ValueError as e:
        logger.error(f"Gemini profile parsing failed to parse JSON for '{name_hint}': {e}")
        # Graceful degradation: return skeleton profile
        return {
            "name": name_hint,
            "skills": [],
            "certifications": [],
            "experience_summary": raw_text[:400],
            "domains": [],
            "languages": [],
            "education": "",
            "years_of_experience": None,
        }
    except Exception as e:
        logger.error(f"Gemini profile parsing failed for '{name_hint}': {e}")
        return {
            "name": name_hint,
            "skills": [],
            "certifications": [],
            "experience_summary": raw_text[:400],
            "domains": [],
            "languages": [],
            "education": "",
            "years_of_experience": None,
        }
