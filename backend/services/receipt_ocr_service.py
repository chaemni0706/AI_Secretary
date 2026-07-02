"""ReceiptOcrService — OPTIONAL OCR for uploaded receipt images.

Design contract (prototype):
- No OCR engine (pytesseract / easyocr) is a required dependency.
- If no OCR backend is available, ``extract_text`` returns None and the caller
  produces a safe ``needs_review`` / ``ocr_unavailable`` response instead of a
  500. The server must never die because OCR is missing.
- The MVP feature is receipt_text parsing; image upload is structurally
  supported but not depended upon for tests.

To wire a real OCR engine later, implement ``_try_ocr`` — callers need no
changes.
"""

from __future__ import annotations

from typing import Optional


def is_available() -> bool:
    """True only if an OCR backend is importable. Kept lazy + optional."""
    try:  # pragma: no cover - depends on optional runtime deps
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401

        return True
    except Exception:
        return False


def _try_ocr(image_bytes: bytes) -> Optional[str]:  # pragma: no cover
    """Attempt OCR on raw image bytes. Returns extracted text or None.

    Wrapped so ANY failure (missing lib, bad image, runtime error) degrades to
    None rather than raising — the caller treats None as 'OCR unavailable'.
    """
    try:
        import io

        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(img, lang="kor+eng")
        return text.strip() or None
    except Exception:
        return None


def extract_text(image_bytes: bytes) -> Optional[str]:
    """Best-effort OCR. Returns text, or None if OCR is unavailable/failed."""
    if not image_bytes:
        return None
    if not is_available():
        return None
    return _try_ocr(image_bytes)
