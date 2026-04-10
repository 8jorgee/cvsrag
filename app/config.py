from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional


class Settings(BaseSettings):
    anthropic_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    chroma_db_path: str = "./data/chroma_db"
    cv_directory: str = "./data/cvs"
    availability_file: str = "./data/availability.csv"
    embedding_model: str = "all-MiniLM-L6-v2"
    # LLM backend: "anthropic", "ollama" or "groq"
    llm_backend: str = "groq"
    llm_model: str = "llama-3.1-8b-instant"
    ollama_base_url: str = "http://localhost:11434"
    top_k_results: int = 20
    rerank_top_n: int = 10
    admin_username: Optional[str] = None
    admin_password: Optional[str] = None
    max_upload_mb: int = 25
    csrf_secret: Optional[str] = None
    fuzzy_match_threshold: int = 85
    ingest_workers: int = 4
    log_format: str = "console"

    class Config:
        env_file = ".env"

    @field_validator('anthropic_api_key')
    @classmethod
    def validate_api_key(cls, v):
        if v is not None and (not v or v.strip() == ""):
            raise ValueError("ANTHROPIC_API_KEY must be set and non-empty")
        return v


settings = Settings()
