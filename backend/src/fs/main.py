"""Factory Studio API 조립점."""

from fastapi import FastAPI

from fs.common.errors import install_error_handlers
from fs.common.request_logging import RequestLogMiddleware
from fs.core.router import router as core_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Factory Studio", docs_url=None, redoc_url=None, openapi_url=None
    )
    app.add_middleware(RequestLogMiddleware)
    install_error_handlers(app)
    app.include_router(core_router, prefix="/api/v1/core")
    return app


app = create_app()
