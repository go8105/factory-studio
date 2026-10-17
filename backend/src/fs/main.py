"""Factory Studio API 조립점."""

from fastapi import Depends, FastAPI

from fs.bems.router import router as bems_router
from fs.cad_cam.router import router as cad_cam_router
from fs.common.errors import install_error_handlers
from fs.common.request_logging import RequestLogMiddleware
from fs.common.scope import seed_ready
from fs.core.review import router as review_router
from fs.core.router import router as core_router
from fs.erp.router import router as erp_router
from fs.factory.router import router as factory_router
from fs.fems.router import router as fems_router
from fs.flow.router import router as flow_router
from fs.gw.company import entry as gw_entry
from fs.gw.company_router import router as gw_company_router
from fs.gw.router import router as gw_router
from fs.hr.router import router as hr_router
from fs.hr.work_router import router as hr_work_router
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
    app.include_router(cad_cam_router, prefix="/api/v1/cad")
    app.include_router(core_router, prefix="/api/v1/core")
    app.include_router(flow_router, prefix="/api/v1/flow")
    app.include_router(flow_router, prefix="/api/v1/gw/projects")
    app.include_router(hr_work_router, prefix="/api/v1/hr/work")
    app.include_router(gw_company_router, prefix="/api/v1/gw")
    app.include_router(review_router, prefix="/api/v1/core")
    app.include_router(
        fems_router, prefix="/api/v1/fems", dependencies=[Depends(seed_ready("fems"))]
    )
    app.include_router(
        mes_router, prefix="/api/v1/mes", dependencies=[Depends(seed_ready("mes"))]
    )
    app.include_router(
        erp_router, prefix="/api/v1/erp", dependencies=[Depends(seed_ready("erp"))]
    )
    app.include_router(
        qms_router, prefix="/api/v1/qms", dependencies=[Depends(seed_ready("qms"))]
    )
    app.include_router(
        wms_router, prefix="/api/v1/wms", dependencies=[Depends(seed_ready("wms"))]
    )
    app.include_router(
        bems_router, prefix="/api/v1/bems", dependencies=[Depends(seed_ready("bems"))]
    )
    app.include_router(
        spc_router, prefix="/api/v1/spc", dependencies=[Depends(seed_ready("spc"))]
    )
    app.include_router(gw_router, prefix="/api/v1/gw", dependencies=[Depends(gw_entry)])
    app.include_router(
        hr_router, prefix="/api/v1/hr", dependencies=[Depends(seed_ready("hr"))]
    )
    return app


app = create_app()
