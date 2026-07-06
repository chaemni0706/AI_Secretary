from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import (
    alert,
    briefing,
    coaching,
    dashboard,
    emotion,
    health,
    image_verification,
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
    voice,
    user_preferences,
    verification,
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

for r in (
    schedule,
    reservation,
    message,
    alert,
    briefing,
    emotion,
    image_verification,
    verification,
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
    voice,
    user_preferences,
):
    app.include_router(r.router, prefix=settings.API_V1_PREFIX)

# --------------------------------------------------------------------------- #
# Optional: Medicine OCR / Routines routers (Feature_SJ)
#
# 이 라우터들은 스스로 "/api/v1/..." prefix 를 갖고 있으므로 추가 prefix 없이 등록한다.
# paddleocr 는 서비스 계층에서 lazy import 되므로 미설치여도 여기서 import/등록은 안전하다.
# 그럼에도 만약의 import 실패로 핵심 앱 기동이 막히지 않도록 방어적으로 감싼다.
# --------------------------------------------------------------------------- #
try:
    from backend.routers import medicine as _medicine_router
    from backend.routers import routines as _routines_router

    app.include_router(_medicine_router.router)
    app.include_router(_routines_router.router)
except Exception as exc:  # noqa: BLE001 - optional feature must never block startup
    import logging

    logging.getLogger("uvicorn.error").warning(
        "Medicine OCR/Routines 라우터를 로드하지 못해 비활성화합니다: %s", exc
    )
