from __future__ import annotations

import logging
from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("factory_studio.request")


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        started = perf_counter()
        response = await call_next(request)
        logger.info(
            "request method=%s path=%s status=%s elapsed_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            (perf_counter() - started) * 1000,
        )
        return response
