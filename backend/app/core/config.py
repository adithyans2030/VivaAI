"""VivaIQ Core Configuration Settings."""

from functools import lru_cache
from pathlib import Path
from typing import List, Literal, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Security
    SECRET_KEY: str = "dev-secret-key-vivaiq-change-in-production-only"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./vivaiq.db"

    # Storage Paths
    DATA_DIR: Path = Path("./data")
    AUDIO_STORAGE_PATH: Path = Path("./data/audio")
    DOCUMENT_STORAGE_PATH: Path = Path("./data/documents")
    CHROMA_PERSIST_PATH: Path = Path("./data/chromadb")

    # LLM Gateway
    LLM_PROVIDER: Literal["ollama", "gemini", "grok", "mock"] = "mock"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GROK_API_KEY: str = ""
    GROK_MODEL: str = "grok-beta"

    # STT Configuration
    STT_PROVIDER: Literal["whisper", "mock"] = "mock"
    WHISPER_MODEL: str = "base.en"
    WHISPER_DEVICE: Literal["cuda", "cpu"] = "cuda"
    WHISPER_COMPUTE_TYPE: str = "float16"

    # TTS Configuration
    TTS_PROVIDER: Literal["browser", "piper", "kokoro", "mock"] = "browser"
    PIPER_MODEL_PATH: str = ""

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
