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
from concurrent.futures import ThreadPoolExecutor

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


def process_cv_file(
    pptx_path: str,
    existing_files: dict,
    current_avail_hash: str,
    availability: dict,
) -> dict:
    """Process a single CV file: extract, parse, embed, build metadata.

    Args:
        pptx_path: Path to the CV file
        existing_files: Dictionary of existing files and their hashes
        current_avail_hash: Hash of current availability file
        availability: Availability data dictionary

    Returns:
        Result dictionary with status, profile_id, embedding, document, metadata, or error info
    """
    pptx_path_obj = Path(pptx_path)
    filename = pptx_path_obj.name

    try:
        fhash = file_hash(pptx_path)

        # Check if re-indexing needed
        if filename in existing_files:
            prev_fhash = existing_files[filename]["file_hash"]
            prev_avail_hash = existing_files[filename]["availability_hash"]

            # Skip if hashes match
            if fhash == prev_fhash and current_avail_hash == prev_avail_hash:
                return {
                    "status": "skip",
                    "filename": filename,
                }

        # 1. Extract text
        extracted = extract_text_from_pptx(pptx_path)
        if not extracted["raw_text"].strip():
            logger.warning(f"No text extracted from {filename}, skipping")
            return {
                "status": "skip",
                "filename": filename,
            }

        # 2. Claude-powered structured parsing
        slides_text = [
            slide["text"] for slide in extracted.get("slides_content", [])
        ]
        parsed = parse_profile_with_claude(
            extracted["raw_text"], slides_text, extracted["name"]
        )

        # 3. Merge availability
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
        profile_id = derive_profile_id(name, department="")
        metadata: dict = {
            "name": name,
            "source_file": filename,
            "profile_id": profile_id,
            "skills": json.dumps(parsed.get("skills", [])),
            "certifications": json.dumps(parsed.get("certifications", [])),
            "experience_summary": parsed.get("experience_summary", "")[:500],
            "domains": json.dumps(parsed.get("domains", [])),
            "languages": json.dumps(parsed.get("languages", [])),
            "education": parsed.get("education", ""),
            "years_of_experience": parsed.get("years_of_experience") or 0,
            "file_hash": fhash,
            "availability_hash": current_avail_hash,
            "last_updated": datetime.now().isoformat(),
            "current_project": avail.get("current_project") or "",
            "availability_date": avail.get("availability_date") or "",
            "availability_percentage": avail.get("availability_percentage") or 0,
            "location": avail.get("location") or "",
            "grade": avail.get("grade") or "",
        }

        return {
            "status": "ok",
            "filename": filename,
            "profile_id": profile_id,
            "name": name,
            "embedding": embedding,
            "document": extracted["raw_text"],
            "metadata": metadata,
        }

    except Exception as e:
        logger.error(f"Error processing {filename}: {e}", exc_info=True)
        return {
            "status": "error",
            "filename": filename,
            "error": str(e),
        }


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

    # Load availability data and hash it
    avail_adapter = get_availability_adapter(settings.availability_file)
    availability = avail_adapter.get_availability()
    logger.info(f"Loaded availability for {len(availability)} people")

    # Hash availability file for change detection
    avail_file = Path(settings.availability_file)
    current_avail_hash = file_hash(str(avail_file)) if avail_file.exists() else ""

    # Build existing-file index for incremental updates
    existing: dict[str, dict] = {}
    if not force_reindex and collection.count() > 0:
        all_docs = collection.get(include=["metadatas"])
        for i, doc_id in enumerate(all_docs["ids"]):
            meta = all_docs["metadatas"][i]
            existing[meta.get("source_file", "")] = {
                "id": doc_id,
                "file_hash": meta.get("file_hash", ""),
                "availability_hash": meta.get("availability_hash", ""),
            }

    processed = skipped = errors = 0

    # Use ThreadPoolExecutor for parallel CV processing
    max_workers = settings.ingest_workers
    logger.info(f"Starting parallel ingestion with {max_workers} workers")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all files to the executor
        futures = []
        for pptx_path in pptx_files:
            future = executor.submit(
                process_cv_file,
                str(pptx_path),
                existing,
                current_avail_hash,
                availability,
            )
            futures.append(future)

        # Collect results (this blocks until all workers complete)
        results = []
        for future in futures:
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Worker task failed: {e}", exc_info=True)
                errors += 1

    # Process results and perform serial upserts with lock
    for result in results:
        if result["status"] == "ok":
            logger.info(f"  OK    {result['name']}")
            collection.upsert_threaded(
                ids=[result["profile_id"]],
                embeddings=[result["embedding"]],
                documents=[result["document"]],
                metadatas=[result["metadata"]],
            )
            processed += 1
        elif result["status"] == "skip":
            logger.info(f"  SKIP  {result['filename']} (unchanged)")
            skipped += 1
        elif result["status"] == "error":
            logger.error(f"    ERR   {result['filename']}: {result.get('error', 'unknown error')}")
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
