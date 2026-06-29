"""Common API response structure and error handling.

Every endpoint returns the same envelope::

    {
        "success": true | false,
        "message": "...",
        "data": <any | null>
    }

Use `success_response()` / `error_response()` to build responses, and the
registered exception handlers to keep error payloads consistent.
"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard response envelope used across all endpoints."""

    success: bool = True
    message: str = "OK"
    data: Optional[T] = None


def success_response(
    data: Any = None,
    message: str = "OK",
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    """Build a standard success JSONResponse."""
    payload = ApiResponse(success=True, message=message, data=data)
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload.model_dump()),
    )


def error_response(
    message: str = "Internal Server Error",
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    data: Any = None,
) -> JSONResponse:
    """Build a standard error JSONResponse."""
    payload = ApiResponse(success=False, message=message, data=data)
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload.model_dump()),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers so all errors use the common response shape."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return error_response(
            message=str(exc.detail),
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        return error_response(
            message="Validation error",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            data=jsonable_encoder(exc.errors()),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return error_response(
            message="Internal Server Error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
