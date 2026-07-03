from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

<<<<<<< HEAD
from backend.api import (
    alert,
    briefing,
    coaching,
    dashboard,
    emotion,
    health,
    local_schedule,
    memory,
    message,
    notification,
    place,
    reservation,
    schedule,
    todo,
    travel,
    chat,
    ledger,
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
=======
from backend.routers import medicine, routines

app = FastAPI(title="AI Secretary - Medicine OCR Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
>>>>>>> origin/Feature_SJ
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
<<<<<<< HEAD
register_exception_handlers(app)
app.include_router(health.router)

for r in (
    schedule,
    reservation,
    message,
    alert,
    briefing,
    emotion,
    local_schedule,
    todo,
    dashboard,
    memory,
    notification,
    coaching,
    chat,
    ledger,
    place,
    travel,
):
    app.include_router(r.router, prefix=settings.API_V1_PREFIX)
=======

app.include_router(medicine.router)
app.include_router(routines.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "medicine-ocr-backend"}
>>>>>>> origin/Feature_SJ
