from datetime import datetime, timedelta
import logging
from app.models import SearchQuery

logger = logging.getLogger(__name__)


def apply_filters(candidates: list[dict], query: SearchQuery) -> list[dict]:
    """Apply faceted filters to candidate list."""
    now = datetime.now()
    filtered = []

    for c in candidates:
        profile = c["profile"]

        if query.skills:
            profile_skills_lower = [s.lower() for s in profile.skills]
            if not all(s.lower() in profile_skills_lower for s in query.skills):
                continue

        if query.certifications:
            profile_certs_lower = [cert.lower() for cert in profile.certifications]
            if not all(cert.lower() in profile_certs_lower for cert in query.certifications):
                continue

        if query.availability_status:
            avail_pct = profile.availability_percentage or 0
            avail_date_str = profile.availability_date

            if query.availability_status == "now":
                if avail_pct <= 0:
                    continue
                if avail_date_str:
                    try:
                        avail_date = datetime.fromisoformat(avail_date_str)
                        if avail_date > now:
                            continue
                    except ValueError as e:
                        # Malformed date — exclude and log warning
                        logger.warning(
                            f"Malformed availability_date '{avail_date_str}' for profile {profile.name} "
                            f"(expected ISO format YYYY-MM-DD): {e} — excluding from filter"
                        )
                        continue

            elif query.availability_status == "30days":
                if not avail_date_str:
                    logger.debug(f"No availability_date for {profile.name} — excluding from filter")
                    continue
                try:
                    if datetime.fromisoformat(avail_date_str) > now + timedelta(days=30):
                        continue
                except ValueError as e:
                    # Malformed date — exclude and log warning
                    logger.warning(
                        f"Malformed availability_date '{avail_date_str}' for profile {profile.name} "
                        f"(expected ISO format YYYY-MM-DD): {e} — excluding from filter"
                    )
                    continue

            elif query.availability_status == "90days":
                if not avail_date_str:
                    logger.debug(f"No availability_date for {profile.name} — excluding from filter")
                    continue
                try:
                    if datetime.fromisoformat(avail_date_str) > now + timedelta(days=90):
                        continue
                except ValueError as e:
                    # Malformed date — exclude and log warning
                    logger.warning(
                        f"Malformed availability_date '{avail_date_str}' for profile {profile.name} "
                        f"(expected ISO format YYYY-MM-DD): {e} — excluding from filter"
                    )
                    continue

        if query.availability_percentage_min is not None:
            if (profile.availability_percentage or 0) < query.availability_percentage_min:
                continue

        if query.grade and profile.grade:
            if query.grade.lower() not in profile.grade.lower():
                continue

        if query.location and profile.location:
            if query.location.lower() not in profile.location.lower():
                continue

        filtered.append(c)

    logger.info(f"Filters applied: {len(filtered)} of {len(candidates)} passed")
    return filtered
