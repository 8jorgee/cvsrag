#!/usr/bin/env python3
"""
Ingest .pptx CV files into the vector store (FAISS + SQLite).

Usage:
    python scripts/ingest_cvs.py          # incremental (skip unchanged files)
    python scripts/ingest_cvs.py --force  # re-index everything
"""

import argparse
import hashlib
import json
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Make app importable from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.config import settings
from app.db import get_collection
from app.ingestion.availability import get_availability_adapter, normalize_name
from app.ingestion.profile_builder import parse_profile_with_claude
from app.ingestion.pptx_parser import extract_text_from_pptx
from app.search.embeddings import generate_embedding

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def file_hash(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


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


def ingest_cvs(force_reindex: bool = False) -> None:
    cv_dir = Path(settings.cv_directory)
    if not cv_dir.exists():
        logger.error(f"CV directory not found: {cv_dir}")
        sys.exit(1)

    pptx_files = list(cv_dir.glob("*.pptx"))
    if not pptx_files:
        logger.warning(f"No .pptx files found in {cv_dir}")
        return

    logger.info(f"Found {len(pptx_files)} .pptx file(s) in {cv_dir}")

    collection = get_collection()

    # Load availability data
    avail_adapter = get_availability_adapter(settings.availability_file)
    availability = avail_adapter.get_availability()
    logger.info(f"Loaded availability for {len(availability)} people")

    # Build existing-file index for incremental updates
    existing: dict[str, dict] = {}
    if not force_reindex and collection.count() > 0:
        all_docs = collection.get(include=["metadatas"])
        for i, doc_id in enumerate(all_docs["ids"]):
            meta = all_docs["metadatas"][i]
            existing[meta.get("source_file", "")] = {
                "id": doc_id,
                "hash": meta.get("file_hash", ""),
            }

    processed = skipped = errors = 0

    for pptx_path in pptx_files:
        filename = pptx_path.name
        fhash = file_hash(str(pptx_path))

        if filename in existing and existing[filename]["hash"] == fhash:
            logger.info(f"  SKIP  {filename} (unchanged)")
            skipped += 1
            continue

        logger.info(f"  PROC  {filename}")

        try:
            # 1. Extract text
            extracted = extract_text_from_pptx(str(pptx_path))
            if not extracted["raw_text"].strip():
                logger.warning(f"    No text extracted from {filename}, skipping")
                errors += 1
                continue

            # 2. Claude-powered structured parsing
            parsed = parse_profile_with_claude(extracted["raw_text"], extracted["name"])

            # 3. Merge availability (match by normalized name)
            name = parsed.get("name", extracted["name"])
            avail = availability.get(normalize_name(name), {})

            # 4. Build embedding text
            embedding_text = "\n".join([
                f"Name: {name}",
                f"Skills: {', '.join(parsed.get('skills', []))}",
                f"Certifications: {', '.join(parsed.get('certifications', []))}",
                f"Experience: {parsed.get('experience_summary', '')}",
                f"Domains: {', '.join(parsed.get('domains', []))}",
                extracted["raw_text"][:2000],
            ])
            embedding = generate_embedding(embedding_text)

            # 5. Build metadata
            profile_id = derive_profile_id(name, department="")  # Use parsed name
            metadata: dict = {
                "name": name,
                "source_file": filename,
                "profile_id": profile_id,  # Store for reference
                "skills": json.dumps(parsed.get("skills", [])),
                "certifications": json.dumps(parsed.get("certifications", [])),
                "experience_summary": parsed.get("experience_summary", "")[:500],
                "domains": json.dumps(parsed.get("domains", [])),
                "languages": json.dumps(parsed.get("languages", [])),
                "education": parsed.get("education", ""),
                "years_of_experience": parsed.get("years_of_experience") or 0,
                "file_hash": fhash,
                "last_updated": datetime.now().isoformat(),
                "current_project": avail.get("current_project") or "",
                "availability_date": avail.get("availability_date") or "",
                "availability_percentage": avail.get("availability_percentage") or 0,
                "location": avail.get("location") or "",
                "grade": avail.get("grade") or "",
            }

            # 6. Upsert
            collection.upsert(
                ids=[profile_id],
                embeddings=[embedding],
                documents=[extracted["raw_text"]],
                metadatas=[metadata],
            )
            logger.info(f"    OK    {name}")
            processed += 1

        except Exception as e:
            logger.error(f"    ERR   {filename}: {e}", exc_info=True)
            errors += 1

    logger.info(
        f"\nDone — processed: {processed}, skipped: {skipped}, errors: {errors}"
    )
    logger.info(f"Total profiles in collection: {collection.count()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest CV .pptx files into ChromaDB")
    parser.add_argument("--force", action="store_true", help="Force re-index all files")
    args = parser.parse_args()
    ingest_cvs(force_reindex=args.force)
