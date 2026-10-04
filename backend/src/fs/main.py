"""Factory Studio API 조립점."""

from fastapi import FastAPI

from fs.bems.router import router as bems_router
from fs.common.errors import install_error_handlers
from fs.common.request_logging import RequestLogMiddleware
from fs.core.review import router as review_router
from fs.core.router import router as core_router
from fs.erp.router import router as erp_router
from fs.factory.router import router as factory_router
from fs.fems.router import router as fems_router
from fs.gw.router import router as gw_router
from fs.mes.router import router as mes_router
from fs.qms.router import router as qms_router
from fs.spc.router import router as spc_router
from fs.wms.router import router as wms_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Factory Studio", docs_url=None, redoc_url=None, openapi_url=None
    )
    app.add_middleware(RequestLogMiddleware)
    install_error_handlers(app)
    app.include_router(factory_router, prefix="/api/v1/factory")
    app.include_router(core_router, prefix="/api/v1/core")
    app.include_router(review_router, prefix="/api/v1/core")
    app.include_router(fems_router, prefix="/api/v1/fems")
    app.include_router(mes_router, prefix="/api/v1/mes")
    app.include_router(erp_router, prefix="/api/v1/erp")
    app.include_router(qms_router, prefix="/api/v1/qms")
    app.include_router(wms_router, prefix="/api/v1/wms")
    app.include_router(bems_router, prefix="/api/v1/bems")
    app.include_router(spc_router, prefix="/api/v1/spc")
    app.include_router(gw_router, prefix="/api/v1/gw")
    return app


app = create_app()
