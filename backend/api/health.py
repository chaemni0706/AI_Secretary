"""Health check endpoint."""

from fastapi import APIRouter

from backend.core.config import settings
from backend.core.response import success_response

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check")
async def health_check():
    """Return server health status in the common response envelope."""
    return success_response(
        message="Backend server is running",
        data={
            "status": "ok",
            "service": settings.APP_NAME,
        },
    )
