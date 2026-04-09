from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd
import structlog
from unidecode import unidecode
from rapidfuzz import fuzz

logger = structlog.get_logger()


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
        logger.debug("Availability matched (exact)", name=parsed_name)
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
        logger.debug("Availability matched (fuzzy)", name=parsed_name, score=best_score)
        return availability_dict[best_match]

    logger.debug("No availability match found", name=parsed_name, threshold=threshold)
    return {}


class AvailabilityAdapter(ABC):
    @abstractmethod
    def get_availability(self) -> dict[str, dict]:
        """Return dict mapping lowercase person name to their availability data."""
        pass


class CSVAvailabilityAdapter(AvailabilityAdapter):
    """Reads availability from a CSV or Excel file."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def get_availability(self) -> dict[str, dict]:
        path = Path(self.file_path)
        if not path.exists():
            logger.warning("Availability file not found", file_path=self.file_path)
            return {}

        try:
            if path.suffix.lower() in (".xlsx", ".xls"):
                df = pd.read_excel(path)
            else:
                df = pd.read_csv(path)

            result: dict[str, dict] = {}
            for _, row in df.iterrows():
                name = str(row.get("name", "")).strip()
                if not name:
                    continue

                normalized = normalize_name(name)  # Apply normalization
                avail_pct = row.get("availability_percentage")
                avail_date = row.get("availability_date")
                location = row.get("location")
                grade = row.get("grade")
                current_project = row.get("current_project")
                result[normalized] = {
                    "current_project": (
                        str(current_project).strip()
                        if pd.notna(current_project) and str(current_project).strip()
                        else None
                    ),
                    "availability_date": (
                        str(avail_date).strip()
                        if pd.notna(avail_date) and str(avail_date).strip()
                        else None
                    ),
                    "availability_percentage": int(avail_pct) if pd.notna(avail_pct) else None,
                    "location": (
                        str(location).strip()
                        if pd.notna(location) and str(location).strip()
                        else None
                    ),
                    "grade": (
                        str(grade).strip()
                        if pd.notna(grade) and str(grade).strip()
                        else None
                    ),
                }

            return result

        except Exception as e:
            logger.error("Error reading availability file", file_path=self.file_path, error=str(e))
            return {}


class SharePointAvailabilityAdapter(AvailabilityAdapter):
    """Future: reads availability from SharePoint/internal tool API."""

    def get_availability(self) -> dict[str, dict]:
        raise NotImplementedError("SharePoint availability adapter not yet implemented")


def get_availability_adapter(file_path: str) -> AvailabilityAdapter:
    return CSVAvailabilityAdapter(file_path)
