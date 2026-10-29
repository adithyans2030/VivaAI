"""VivaIQ FastAPI Application Entrypoint."""

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import async_session_factory, init_db
from app.core.errors import VivaIQError, vivaiq_exception_handler
from app.core.logging import logger, setup_logging
from app.services.retention import run_retention_forever
from app.ws.session_handler import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle."""
    setup_logging(debug=settings.DEBUG)
    logger.info("Initializing VivaIQ database schema...")
    await init_db()
    retention_task = None
    if settings.ENVIRONMENT != "testing":
        retention_task = asyncio.create_task(run_retention_forever(async_session_factory))
    logger.info("Database schema initialized. VivaIQ ready.")
    yield
    logger.info("Shutting down VivaIQ services...")
    if retention_task:
        retention_task.cancel()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="Production-grade AI Voice Viva Examiner backend.",
    lifespan=lifespan,
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next) -> Response:
    """Attach unique request-id and calculate execution duration."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
    return response


# Register custom exception handler
# Starlette types handlers as taking a bare Exception; ours narrows to VivaIQError.
app.add_exception_handler(VivaIQError, vivaiq_exception_handler)  # type: ignore[arg-type]

# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Include WebSocket router
app.include_router(ws_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    """Basic health check endpoint."""
    return {"status": "healthy", "service": settings.PROJECT_NAME, "version": "0.1.0"}


@app.get("/ready", tags=["system"])
async def readiness_check() -> dict:
    """Readiness probe checking real provider and model statuses."""
    from app.services.rag import get_rag_store
    from app.services.stt import WhisperSTTProvider, get_stt_provider

    stt_provider = get_stt_provider()
    stt_model_loaded = stt_provider.is_model_loaded()
    stt_device = stt_provider.get_active_device() if isinstance(stt_provider, WhisperSTTProvider) else "mock"

    rag_store = get_rag_store()
    chroma_active = rag_store.is_chroma_active()

    return {
        "status": "ready",
        "environment": settings.ENVIRONMENT,
        "demo_mode": settings.DEMO_MODE,
        "llm_provider": settings.LLM_PROVIDER,
        "stt_provider": settings.STT_PROVIDER,
        "stt_model_loaded": stt_model_loaded,
        "stt_active_device": stt_device,
        "tts_provider": settings.TTS_PROVIDER,
        "chroma_active": chroma_active,
        "rag_store_mode": "chromadb" if chroma_active else "in_memory_tfidf",
    }
