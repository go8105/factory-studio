from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def _content(error: ApiError) -> dict[str, object]:
    return {
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details,
        }
    }


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(_request: Request, error: ApiError) -> JSONResponse:
        response = JSONResponse(status_code=error.status_code, content=_content(error))
        if error.code in {"SESSION_EXPIRED", "WORKSPACE_EXPIRED"}:
            response.delete_cookie(
                "fs_session", path="/", secure=True, httponly=True, samesite="lax"
            )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        fields = {
            ".".join(str(part) for part in item["loc"]): item["msg"]
            for item in error.errors()
        }
        api_error = ApiError(
            400,
            "VALIDATION_FAILED",
            "요청 형식이 올바르지 않습니다.",
            {"fields": fields},
        )
        return JSONResponse(status_code=400, content=_content(api_error))

    @app.exception_handler(HTTPException)
    async def http_error_handler(
        _request: Request, error: HTTPException
    ) -> JSONResponse:
        code = "NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR"
        api_error = ApiError(error.status_code, code, str(error.detail))
        return JSONResponse(status_code=error.status_code, content=_content(api_error))

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        _request: Request, _error: Exception
    ) -> JSONResponse:
        api_error = ApiError(500, "INTERNAL_ERROR", "요청을 처리하지 못했습니다.")
        return JSONResponse(status_code=500, content=_content(api_error))
