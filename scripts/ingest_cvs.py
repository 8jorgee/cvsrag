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
import sys
import uuid
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import structlog

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

# Configure structlog for CLI output
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()


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
            logger.warning("No text extracted, skipping", filename=filename)
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
        logger.error("Error processing CV file", filename=filename, error=str(e), exc_info=True)
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


def ingest_cvs(
    force_reindex: bool = False,
    progress_callback: callable = None,
    cv_dir: str = None,
    availability_file: str = None,
) -> dict:
    """
    Ingest CVs with optional progress callback.

    Args:
        force_reindex: Force re-index all files
        progress_callback: Optional callback function invoked with progress events
        cv_dir: CV directory (defaults to settings.cv_directory)
        availability_file: Availability file path (defaults to settings.availability_file)

    Returns:
        Dictionary with processed, skipped, errors counts
    """
    if cv_dir is None:
        cv_dir = settings.cv_directory
    if availability_file is None:
        availability_file = settings.availability_file

    cv_path = Path(cv_dir)
    if not cv_path.exists():
        logger.error("CV directory not found", directory=str(cv_path))
        sys.exit(1)

    pptx_files = list(cv_path.glob("*.pptx"))
    if not pptx_files:
        logger.warning("No .pptx files found", directory=str(cv_path))
        return {"processed": 0, "skipped": 0, "errors": 0}

    logger.info("CV files found", count=len(pptx_files), directory=str(cv_path))

    collection = get_collection()

    # Load availability data and hash it
    avail_adapter = get_availability_adapter(availability_file)
    availability = avail_adapter.get_availability()
    logger.info("Availability data loaded", people_count=len(availability))

    # Hash availability file for change detection
    avail_file = Path(availability_file)
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
    logger.info("Starting parallel ingestion", worker_count=max_workers)

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
                logger.error("Worker task failed", error=str(e), exc_info=True)
                errors += 1

    # Process results and perform serial upserts with lock
    for result in results:
        if result["status"] == "ok":
            logger.info("CV processed successfully", name=result['name'])
            collection.upsert_threaded(
                ids=[result["profile_id"]],
                embeddings=[result["embedding"]],
                documents=[result["document"]],
                metadatas=[result["metadata"]],
            )
            processed += 1
            if progress_callback:
                progress_callback({
                    "file": result["filename"],
                    "status": "ok",
                    "count": processed
                })
        elif result["status"] == "skip":
            logger.info("CV skipped (unchanged)", filename=result['filename'])
            skipped += 1
            if progress_callback:
                progress_callback({
                    "file": result["filename"],
                    "status": "skip",
                    "count": processed
                })
        elif result["status"] == "error":
            logger.error("CV processing error", filename=result['filename'], error=result.get('error', 'unknown error'))
            errors += 1
            if progress_callback:
                progress_callback({
                    "file": result["filename"],
                    "status": "error",
                    "error": result.get('error', 'unknown error')
                })

    logger.info(
        "Ingestion completed",
        processed=processed,
        skipped=skipped,
        errors=errors
    )
    logger.info("Total profiles in collection", count=collection.count())

    # Send final summary event
    if progress_callback:
        progress_callback({
            "done": True,
            "processed": processed,
            "skipped": skipped,
            "errors": errors
        })

    return {"processed": processed, "skipped": skipped, "errors": errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest CV .pptx files into ChromaDB")
    parser.add_argument("--force", action="store_true", help="Force re-index all files")
    args = parser.parse_args()
    result = ingest_cvs(force_reindex=args.force)
    logger.info("CLI ingestion result", **result)
