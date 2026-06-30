from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import (
    alert, briefing, emotion, health, local_schedule, message, reservation,
    schedule, todo,
)
from backend.core.config import settings
from backend.core.response import register_exception_handlers

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI Secretary backend API (rule-based / mock / template MVP).",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(health.router)
for r in (schedule, reservation, message, alert, briefing, emotion,
          local_schedule, todo):
    app.include_router(r.router, prefix=settings.API_V1_PREFIX)
