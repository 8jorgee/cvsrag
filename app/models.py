from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Profile(BaseModel):
    id: str
    name: str
    source_file: str
    raw_text: str
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    experience_summary: str = ""
    domains: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    education: str = ""
    years_of_experience: Optional[int] = None
    current_project: Optional[str] = None
    availability_date: Optional[str] = None
    availability_percentage: Optional[int] = None
    location: Optional[str] = None
    grade: Optional[str] = None
    last_updated: str = ""


class SearchQuery(BaseModel):
    query: str = Field(
        ...,
        max_length=500,
        description="Search query (max 500 characters)"
    )
    mode: str = "smart"  # "smart" or "quick"
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    availability_status: Optional[str] = None  # "now", "30days", "90days"
    availability_percentage_min: Optional[int] = None
    grade: Optional[str] = None
    location: Optional[str] = None


class SearchResult(BaseModel):
    profile: Profile
    score: float
    match_reasoning: Optional[str] = None
    gaps: Optional[str] = None
    highlighted_skills: list[str] = Field(default_factory=list)


class IngestionStatus(BaseModel):
    total_profiles: int
    last_ingestion: Optional[str]
    missing_availability: list[str]
    stale_profiles: list[str]
    logs: list[str] = Field(default_factory=list)
