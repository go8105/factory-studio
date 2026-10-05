from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from fs.common.auth import AuthContext, resolve_auth

router = APIRouter()
ASSET_ROOT = Path(__file__).resolve().parents[3] / "private-assets" / "soap-poc"
PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "frame-ancestors 'self'",
}


@router.get("/admin/soap-poc/{asset_path:path}")
def soap_asset(asset_path: str, context: Annotated[AuthContext, Depends(resolve_auth)]):
    if context.actor_kind != "MEMBER" or "ADMIN" not in context.roles:
        raise HTTPException(403, "관리자 전용입니다.", headers=PRIVATE_HEADERS)
    root = ASSET_ROOT.resolve()
    path = (root / asset_path).resolve()
    if (
        not asset_path
        or any(part.startswith(".") for part in Path(asset_path).parts)
        or not path.is_relative_to(root)
        or path.suffix
        not in {".html", ".js", ".css", ".stl", ".json", ".csv", ".md", ".zip"}
        or not path.is_file()
    ):
        raise HTTPException(404, "파일이 없습니다.", headers=PRIVATE_HEADERS)
    return FileResponse(path, headers=PRIVATE_HEADERS)
