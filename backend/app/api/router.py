"""VivaIQ API v1 Router aggregator."""

from fastapi import APIRouter

from app.api.audio import router as audio_router
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.reports import router as reports_router
from app.api.sessions import router as sessions_router
from app.api.subjects import router as subjects_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(subjects_router)
api_router.include_router(documents_router)
api_router.include_router(sessions_router)
api_router.include_router(reports_router)
api_router.include_router(audio_router)
