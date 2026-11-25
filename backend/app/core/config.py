"""VivaIQ Core Configuration Settings."""

import logging
import secrets
from functools import lru_cache
from pathlib import Path
from typing import List, Literal, Optional, Union

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

KNOWN_SECRET_PLACEHOLDERS = {
    "dev-secret-key-vivaiq-change-in-production-only",
    "replace-this-with-a-secure-random-secret-key-in-production",
    "change-me",
    "",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    PROJECT_NAME: str = "VivaIQ"
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = False
    DEMO_MODE: bool = False
    API_V1_STR: str = "/api/v1"
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Security
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # Browser sessions use httpOnly cookies. Secure defaults to on in production (HTTPS only).
    AUTH_COOKIE_SECURE: Optional[bool] = None
    AUTH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    AUTH_COOKIE_DOMAIN: Optional[str] = None
    AUDIO_RETENTION_DAYS: int = 30

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./vivaiq.db"

    # Storage Paths
    DATA_DIR: Path = Path("./data")
    AUDIO_STORAGE_PATH: Path = Path("./data/audio")
    DOCUMENT_STORAGE_PATH: Path = Path("./data/documents")
    CHROMA_PERSIST_PATH: Path = Path("./data/chromadb")

    # LLM Gateway
    LLM_PROVIDER: Literal["ollama", "gemini", "grok", "mock"] = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma2:2b"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GROK_API_KEY: str = ""
    GROK_MODEL: str = "grok-beta"

    # STT Configuration
    STT_PROVIDER: Literal["whisper", "mock"] = "whisper"
    WHISPER_MODEL: str = "base.en"
    WHISPER_DEVICE: Literal["cuda", "cpu"] = "cuda"
    WHISPER_COMPUTE_TYPE: str = "float16"
    WHISPER_LANGUAGE: str = "en"
    WHISPER_BEAM_SIZE: int = 1

    # TTS Configuration
    TTS_PROVIDER: Literal["browser", "piper", "kokoro", "edge", "mock"] = "browser"
    PIPER_MODEL_PATH: str = ""
    PDF_FONT_PATH: str = ""  # Unicode .ttf for PDF reports; auto-detected (DejaVu/Arial) when empty
    EDGE_TTS_VOICE: str = "en-US-JennyNeural"  # e.g. en-IN-NeerjaNeural for Indian English

    # RAG & Embeddings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    TOP_K_RETRIEVAL: int = 4

    # Viva Session Defaults
    MIN_QUESTIONS: int = 6
    MAX_QUESTIONS: int = 10

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        import json

        return json.loads(v)

    @model_validator(mode="after")
    def validate_secrets_and_providers(self) -> "Settings":
        # Check SECRET_KEY in production
        if self.ENVIRONMENT == "production":
            if not self.SECRET_KEY or self.SECRET_KEY in KNOWN_SECRET_PLACEHOLDERS:
                raise ValueError(
                    "CRITICAL: Production environment cannot use default or placeholder SECRET_KEY. "
                    "Set a secure random SECRET_KEY in your production environment variables."
                )
        else:
            # Generate random dev key if placeholder or empty
            if not self.SECRET_KEY or self.SECRET_KEY in KNOWN_SECRET_PLACEHOLDERS:
                self.SECRET_KEY = secrets.token_hex(32)
                logging.getLogger("uvicorn").warning(
                    "WARNING: Using ephemeral random SECRET_KEY for non-production environment. Set SECRET_KEY in .env for persistent sessions."
                )

        if "*" in self.CORS_ORIGINS:
            raise ValueError("CORS_ORIGINS must list explicit origins; '*' is not allowed.")

        if self.AUTH_COOKIE_SECURE is None:
            self.AUTH_COOKIE_SECURE = self.ENVIRONMENT == "production"
        if self.AUTH_COOKIE_SAMESITE == "none" and not self.AUTH_COOKIE_SECURE:
            raise ValueError(
                "AUTH_COOKIE_SAMESITE='none' requires AUTH_COOKIE_SECURE=true (browsers refuse it otherwise)."
            )

        if self.ENVIRONMENT == "production" and self.DEMO_MODE:
            raise ValueError("DEMO_MODE cannot be enabled in production (it permits mock STT/LLM).")

        # Enforce that mock STT / LLM is only permitted in testing or when DEMO_MODE=True
        if not self.DEMO_MODE and self.ENVIRONMENT != "testing":
            if self.STT_PROVIDER == "mock":
                raise ValueError(
                    "STT_PROVIDER='mock' is only permitted when ENVIRONMENT='testing' or DEMO_MODE=True. "
                    "Set STT_PROVIDER='whisper' or configure DEMO_MODE=True."
                )
            if self.LLM_PROVIDER == "mock":
                raise ValueError(
                    "LLM_PROVIDER='mock' is only permitted when ENVIRONMENT='testing' or DEMO_MODE=True. "
                    "Set LLM_PROVIDER to 'ollama', 'gemini', or 'grok', or configure DEMO_MODE=True."
                )

        return self


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # Ensure local data directories exist
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.AUDIO_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    settings.DOCUMENT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    settings.CHROMA_PERSIST_PATH.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
