"""
Centralized configuration for the FastAPI RAG backend.

Import the singleton settings object anywhere in the backend with:

    from app.core.config import settings
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Production-ready application settings.

    Values can be overridden with environment variables or a `.env` file. Field
    names intentionally match the required environment variable names, e.g.
    `OLLAMA_MODEL=qwen3:8b`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "RAG Backend"
    API_VERSION: str = "v1"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = Field(default=8000, ge=1, le=65535)

    # LLM / Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    REQUEST_TIMEOUT: int = Field(default=120, gt=0)

    # Embeddings
    EMBEDDING_MODEL: str = "mxbai-embed-large:latest"

    # Vector Store Configuration
    VECTOR_DB_TYPE: str = Field(default="chromadb", description="Vector DB backend: 'chromadb' or 'faiss'")
    
    # ChromaDB
    CHROMA_DB_PATH: Optional[str] = Field(default=None, description="Override path for ChromaDB persistent storage (env: CHROMA_DB_PATH)")
    CHROMA_PERSIST_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "chroma_db",
        description="Resolved absolute path for ChromaDB persistent storage",
    )
    CHROMA_COLLECTION_NAME: str = "default_ollama"
    
    # FAISS
    FAISS_INDEX_PATH: Optional[str] = Field(default=None, description="Path to FAISS index storage")
    FAISS_INDEX_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "faiss_index",
        description="Resolved absolute path for FAISS index storage",
    )

    # Chunking
    CHUNK_SIZE: int = Field(default=1000, gt=0)
    CHUNK_OVERLAP: int = Field(default=200, ge=0)

    # Similarity Threshold for Retrieval
    SIMILARITY_THRESHOLD: float = Field(default=0.10, ge=0.0, le=1.0)

    # Uploads
    UPLOAD_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "uploads",
        description="Resolved absolute path for uploaded file storage",
    )
    MAX_UPLOAD_SIZE: int = Field(default=25 * 1024 * 1024, gt=0)

    # Retrieval
    DEFAULT_TOP_K: int = Field(default=3, gt=0)

    # Redis + Celery (Phase 7 — Async Processing)
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL used as Celery broker and cache store.",
    )
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Celery task broker URL (Redis).",
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="rpc://",
        description="Celery result backend. Uses rpc:// to avoid Redis memory bloat from stale task metadata.",
    )
    REDIS_CACHE_TTL: int = Field(
        default=300,
        gt=0,
        description="Chat response cache TTL in seconds (default 5 minutes).",
    )
    CELERY_TASK_MAX_RETRIES: int = Field(
        default=3,
        ge=0,
        description="Maximum Celery task retry attempts before marking as failed.",
    )

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_flag(cls, value: Any) -> Any:
        """Parse common boolean and environment names for DEBUG."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "dev", "development"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return value

    @field_validator("OLLAMA_BASE_URL")
    @classmethod
    def validate_ollama_base_url(cls, value: str) -> str:
        """Normalize and validate the Ollama base URL."""
        normalized = value.strip().rstrip("/")
        if not normalized:
            raise ValueError("OLLAMA_BASE_URL cannot be empty")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("OLLAMA_BASE_URL must start with http:// or https://")
        return normalized

    @field_validator("APP_NAME", "API_VERSION", "OLLAMA_MODEL", "EMBEDDING_MODEL", "CHROMA_COLLECTION_NAME")
    @classmethod
    def validate_non_empty_strings(cls, value: str) -> str:
        """Ensure required string settings are not blank."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Configuration value cannot be empty")
        return normalized

    @model_validator(mode="after")
    def resolve_chroma_persist_dir(self) -> "Settings":
        """Resolve CHROMA_PERSIST_DIR, preferring CHROMA_DB_PATH env var if set."""
        raw = self.CHROMA_DB_PATH
        if raw and str(raw).strip():
            p = Path(str(raw).strip())
            if not p.is_absolute():
                p = Path(__file__).resolve().parent.parent / p
            self.CHROMA_PERSIST_DIR = p
        return self

    @model_validator(mode="after")
    def resolve_faiss_index_dir(self) -> "Settings":
        """Resolve FAISS_INDEX_DIR, preferring FAISS_INDEX_PATH env var if set."""
        raw = self.FAISS_INDEX_PATH
        if raw and str(raw).strip():
            p = Path(str(raw).strip())
            if not p.is_absolute():
                p = Path(__file__).resolve().parent.parent / p
            self.FAISS_INDEX_DIR = p
        return self

    @model_validator(mode="after")
    def validate_chunking(self) -> "Settings":
        """Ensure chunk overlap is smaller than chunk size."""
        if self.CHUNK_OVERLAP >= self.CHUNK_SIZE:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return self

    @model_validator(mode="after")
    def create_required_directories(self) -> "Settings":
        """Create runtime directories if they do not already exist."""
        for directory in (self.CHROMA_PERSIST_DIR, self.FAISS_INDEX_DIR, self.UPLOAD_DIR):
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug("Ensured directory exists: %s", directory)
        return self

    @property
    def chroma_persist_path(self) -> Path:
        """Return the ChromaDB persistence directory as a Path."""
        return self.CHROMA_PERSIST_DIR

    @property
    def upload_path(self) -> Path:
        """Return the upload directory as a Path."""
        return self.UPLOAD_DIR

    @property
    def faiss_index_path(self) -> Path:
        """Return the FAISS index directory as a Path."""
        return self.FAISS_INDEX_DIR

    def as_log_dict(self) -> dict[str, Any]:
        """
        Return a safe settings summary for logs.

        This project currently has no secrets in settings, but this method keeps
        logging centralized so future secret fields can be redacted in one place.
        """
        return {
            "app_name": self.APP_NAME,
            "api_version": self.API_VERSION,
            "debug": self.DEBUG,
            "host": self.HOST,
            "port": self.PORT,
            "ollama_base_url": self.OLLAMA_BASE_URL,
            "ollama_model": self.OLLAMA_MODEL,
            "request_timeout": self.REQUEST_TIMEOUT,
            "embedding_model": self.EMBEDDING_MODEL,
            "chroma_persist_dir": str(self.CHROMA_PERSIST_DIR),
            "chroma_db_path_env": self.CHROMA_DB_PATH,
            "chroma_collection_name": self.CHROMA_COLLECTION_NAME,
            "chunk_size": self.CHUNK_SIZE,
            "chunk_overlap": self.CHUNK_OVERLAP,
            "upload_dir": str(self.UPLOAD_DIR),
            "max_upload_size": self.MAX_UPLOAD_SIZE,
            "default_top_k": self.DEFAULT_TOP_K,
            "redis_url": self.REDIS_URL,
            "celery_broker_url": self.CELERY_BROKER_URL,
            "celery_result_backend": self.CELERY_RESULT_BACKEND,
            "redis_cache_ttl": self.REDIS_CACHE_TTL,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    loaded_settings = Settings()
    logger.info("Application settings loaded: %s", loaded_settings.as_log_dict())
    return loaded_settings


settings = get_settings()
