import logging
import re
import secrets
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

import aiofiles
import magic
import structlog
import asyncio
import json

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette_csrf import CSRFMiddleware

from app.config import settings
from app.db import get_collection
from app.models import SearchQuery
from app.search import engine
from scripts.ingest_cvs import ingest_cvs


def configure_logging():
    """Configure structlog based on LOG_FORMAT setting."""
    if settings.log_format == "json":
        # Production: JSON renderer
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Development: Colored console renderer
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
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


# Configure logging at startup
configure_logging()
logger = structlog.get_logger()

app = FastAPI(title="Team Profile RAG", version="1.0.0")

# ─── Security Middleware ────────────────────────────────────────────────────────

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# CSRF protection — Double Submit Cookie pattern
csrf_secret = settings.csrf_secret or "dev-secret-change-in-production"
app.add_middleware(
    CSRFMiddleware,
    secret=csrf_secret,
    exempt_urls=[re.compile(r"^/search")],
)

# ─── Static Files & Templates ──────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
admin_security = HTTPBasic(auto_error=False)


# ─── Startup & Shutdown ────────────────────────────────────────────────────────

@app.on_event("startup")
async def validate_startup():
    """Validate required environment variables at startup."""
    try:
        if settings.llm_backend == "anthropic" and not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        if settings.llm_backend == "groq" and not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is not set")
        logger.info("API key validated", status="valid")
    except Exception as e:
        logger.error("Startup validation failed", error=str(e))
        raise


# ─── Exception Handlers ─────────────────────────────────────────────────────────

@app.exception_handler(RateLimitExceeded)
async def rate_limit_error_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded: 30 requests per minute per IP"},
    )


# ─── Middleware ─────────────────────────────────────────────────────────────────

@app.middleware("http")
async def add_csrf_to_context(request: Request, call_next):
    """Add CSRF token to request context for template injection."""
    request.state.csrf_token = request.cookies.get("csrf_token", "")
    response = await call_next(request)
    return response


# ─── Helpers ────────────────────────────────────────────────────────────────

def _availability_color(profile) -> str:
    """Return CSS color class for availability badge."""
    pct = profile.availability_percentage or 0
    date_str = profile.availability_date
    now = datetime.now()

    if pct == 0:
        return "busy"

    if date_str:
        try:
            avail_date = datetime.fromisoformat(date_str)
            if avail_date <= now:
                return "available"
            elif avail_date <= now + timedelta(days=30):
                return "soon"
            else:
                return "busy"
        except ValueError:
            pass

    return "available" if pct > 0 else "busy"


def _safe_upload_name(filename: str, allowed_exts: set[str]) -> str:
    """Validate upload filename and return safe basename only."""
    name = Path(filename).name
    if name != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if Path(name).suffix.lower() not in allowed_exts:
        raise HTTPException(status_code=400, detail="Invalid file type")
    return name


def _check_upload_size(content: bytes) -> None:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max allowed size is {settings.max_upload_mb} MB",
        )


def _validate_upload_mime(file: UploadFile, allowed_mimes: set[str]) -> bytes:
    """Validate file MIME type using magic bytes (not client header)."""
    # Read file content
    content = file.file.read()
    file.file.seek(0)  # Reset for later reads

    # Detect MIME from content (magic bytes)
    detected_mime = magic.from_buffer(content[:2048], mime=True)

    if detected_mime not in allowed_mimes:
        raise HTTPException(
            status_code=415,
            detail=f"File content is {detected_mime}, not an allowed type. Expected: {', '.join(allowed_mimes)}"
        )

    return content


def _require_admin_auth(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(admin_security)],
) -> None:
    """Protect admin routes when ADMIN_USERNAME + ADMIN_PASSWORD are configured."""
    if not settings.admin_username or not settings.admin_password:
        return

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    username_ok = secrets.compare_digest(credentials.username, settings.admin_username)
    password_ok = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


# ─── Routes ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def search_page(request: Request):
    collection = get_collection()
    total = collection.count()

    skills = engine.get_all_skills() if total > 0 else []
    certifications = engine.get_all_certifications() if total > 0 else []
    grades = engine.get_all_grades() if total > 0 else []
    locations = engine.get_all_locations() if total > 0 else []

    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "total_profiles": total,
            "all_skills": skills,
            "all_certifications": certifications,
            "all_grades": grades,
            "all_locations": locations,
        },
    )


@app.post("/search", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def do_search(
    request: Request,
    query: str = Form(""),
    mode: str = Form("smart"),
    skills: list[str] = Form(default=[]),
    certifications: list[str] = Form(default=[]),
    skills_any: list[str] = Form(default=[]),
    certifications_any: list[str] = Form(default=[]),
    availability_status: str = Form(""),
    availability_percentage_min: str = Form(""),
    grade: str = Form(""),
    location: str = Form(""),
    page: str = Form("1"),
):
    search_query = SearchQuery(
        query=query,
        mode=mode,
        skills=skills,
        certifications=certifications,
        skills_any=skills_any,
        certifications_any=certifications_any,
        availability_status=availability_status or None,
        availability_percentage_min=int(availability_percentage_min) if availability_percentage_min else None,
        grade=grade or None,
        location=location or None,
        page=int(page) if page else 1,
    )

    # Call search with pagination parameters
    page_num = max(1, int(page) if page else 1)
    result = engine.search(search_query, page=page_num, page_size=10)

    return templates.TemplateResponse(
        "partials/results.html",
        {
            "request": request,
            "results": result["results"],
            "query": query,
            "total_count": result["total_count"],
            "page": result["page"],
            "page_size": result["page_size"],
            "has_more": result["has_more"],
            "availability_color": _availability_color,
        },
    )


@app.get("/profile/{profile_id}", response_class=HTMLResponse)
async def profile_detail(request: Request, profile_id: str):
    profile = engine.get_profile_by_id(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return templates.TemplateResponse(
        "profile_detail.html",
        {
            "request": request,
            "profile": profile,
            "availability_color": _availability_color(profile),
        },
    )


@app.get("/download/{profile_id}")
async def download_cv(profile_id: str):
    profile = engine.get_profile_by_id(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    cv_path = Path(settings.cv_directory) / profile.source_file
    if not cv_path.exists():
        raise HTTPException(status_code=404, detail="Original CV file not found")

    return FileResponse(
        path=str(cv_path),
        filename=profile.source_file,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


# ─── Admin ───────────────────────────────────────────────────────────────────

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, _: None = Depends(_require_admin_auth)):
    collection = get_collection()
    total = collection.count()

    missing_avail = []
    stale = []
    last_ingestion = None
    six_months_ago = datetime.now() - timedelta(days=180)

    if total > 0:
        all_docs = collection.get(include=["metadatas"])
        for meta in all_docs["metadatas"]:
            if not meta.get("availability_date") and not meta.get("availability_percentage"):
                missing_avail.append(meta.get("name", "Unknown"))

            updated_str = meta.get("last_updated", "")
            if updated_str:
                try:
                    updated = datetime.fromisoformat(updated_str)
                    if updated < six_months_ago:
                        stale.append(meta.get("name", "Unknown"))
                    if last_ingestion is None or updated > last_ingestion:
                        last_ingestion = updated
                except ValueError:
                    pass

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "total_profiles": total,
            "last_ingestion": last_ingestion.strftime("%Y-%m-%d %H:%M") if last_ingestion else "Never",
            "missing_availability": missing_avail,
            "stale_profiles": stale,
        },
    )


@app.post("/admin/reindex")
async def reindex(force: bool = False, _: None = Depends(_require_admin_auth)):
    """Trigger CV re-ingestion in a subprocess."""
    script = Path(__file__).parent.parent / "scripts" / "ingest_cvs.py"
    cmd = [sys.executable, str(script)]
    if force:
        cmd.append("--force")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return JSONResponse(
            {
                "status": "ok" if result.returncode == 0 else "error",
                "stdout": result.stdout[-3000:],
                "stderr": result.stderr[-1000:],
            }
        )
    except subprocess.TimeoutExpired:
        return JSONResponse({"status": "timeout", "message": "Ingestion is still running"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/admin/reindex-stream")
async def reindex_stream(request: Request, force: bool = False, _: None = Depends(_require_admin_auth)):
    """
    SSE endpoint for streaming re-index progress.
    Runs ingest_cvs in a background thread and yields SSE events.
    """
    async def event_generator():
        # Collect events as ingest_cvs invokes the callback
        events = []

        def collect_event(event: dict):
            events.append(event)

        def stream_events():
            # Call ingest_cvs with callback
            ingest_cvs(
                force_reindex=force,
                progress_callback=collect_event,
                cv_dir=settings.cv_directory,
                availability_file=settings.availability_file,
            )
            return events

        # Execute in thread to avoid blocking event loop
        all_events = await asyncio.to_thread(stream_events)

        # Yield each event as SSE data
        for event in all_events:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@app.post("/admin/upload-cv")
async def upload_cv(file: UploadFile = File(...), _: None = Depends(_require_admin_auth)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    safe_name = _safe_upload_name(file.filename, {".pptx"})

    # Validate MIME type (magic bytes check)
    content = _validate_upload_mime(
        file,
        allowed_mimes={
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        }
    )

    # Check size
    _check_upload_size(content)

    dest = Path(settings.cv_directory) / safe_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(dest, "wb") as f:
        await f.write(content)

    logger.info("CV uploaded", filename=safe_name)
    return JSONResponse({"status": "ok", "filename": safe_name})


@app.post("/admin/upload-availability")
async def upload_availability(file: UploadFile = File(...), _: None = Depends(_require_admin_auth)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    safe_name = _safe_upload_name(file.filename, {".csv", ".xlsx"})

    # Validate MIME type (magic bytes check) for CSV
    content = _validate_upload_mime(
        file,
        allowed_mimes={"text/plain", "text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    )

    # Check size
    _check_upload_size(content)

    dest = Path(settings.availability_file)
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(dest, "wb") as f:
        await f.write(content)

    logger.info("Availability data uploaded", filename=safe_name)
    return JSONResponse({"status": "ok", "filename": safe_name})
