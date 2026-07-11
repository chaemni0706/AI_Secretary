"""약봉투 이미지 OCR 분석 API."""

import os
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from backend.core.response import success_response
from backend.services import medicine_ocr_service

router = APIRouter(prefix="/api/v1/medicine", tags=["medicine"])

TEMP_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp_uploads")


@router.post("/analyze")
async def analyze_medicine_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드할 수 있습니다.")

    os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
    extension = os.path.splitext(file.filename or "")[1] or ".jpg"
    temp_filename = f"{uuid.uuid4().hex}{extension}"
    temp_path = os.path.join(TEMP_UPLOAD_DIR, temp_filename)

    try:
        contents = await file.read()
        with open(temp_path, "wb") as f:
            f.write(contents)

        analysis = medicine_ocr_service.analyze_medicine_image(temp_path)
    except RuntimeError as exc:
        # paddleocr 미설치 등 optional dependency 부재 → 앱은 죽지 않고 명확히 안내
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "Medicine OCR 기능을 사용할 수 없습니다.",
                "error": {
                    "code": "OPTIONAL_DEPENDENCY_MISSING",
                    "detail": str(exc),
                },
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 분석 중 오류가 발생했습니다: {e}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return success_response(
        message="약봉투 이미지 분석이 완료되었습니다.",
        data={
            "source_type": "medicine_ocr",
            "record_type": "medicine",
            "image_file": file.filename,
            "dispensed_date": analysis["dispensed_date"],
            "dispensed_date_note": analysis["dispensed_date_note"],
            "medicines": analysis["medicines"],
            "status": "pending_user_confirmation",
            "needs_user_confirmation": True,
            "warning": "약 정보는 OCR 기반 추출 결과이므로 사용자 확인 후 일정 또는 루틴에 저장해야 합니다.",
        },
    )
