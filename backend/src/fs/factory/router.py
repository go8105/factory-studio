from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, ConfigDict

from fs.common.auth import AuthContext, require_csrf, resolve_auth
from fs.factory.explanation import explain
from fs.factory.native import NativeRequest, inspect_native

router = APIRouter()


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: Literal["normal", "reject-rise", "stopped"]


@router.post("/vision/explanation")
def vision_explanation(
    body: ExplainRequest,
    response: Response,
    context: Annotated[AuthContext, Depends(resolve_auth)],
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> dict:
    require_csrf(context, csrf)
    response.headers["Cache-Control"] = "no-store"
    return {"data": explain(body.scenario)}


@router.post("/vision/inspect")
async def vision_inspect(
    body: NativeRequest,
    response: Response,
    context: Annotated[AuthContext, Depends(resolve_auth)],
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> dict:
    require_csrf(context, csrf)
    response.headers["Cache-Control"] = "no-store"
    return {"data": await inspect_native(body)}
