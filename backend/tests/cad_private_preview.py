"""Synthetic login fixture. Run only locally; real asset router/authz is exercised."""

from fastapi import Cookie
from fastapi.responses import JSONResponse
from fs.common.auth import AuthContext, resolve_auth
from fs.common.errors import ApiError
from fs.main import create_app

app = create_app()


def preview_auth(cad_private_preview: str | None = Cookie(None)):
    if cad_private_preview not in {"guest", "admin", "member"}:
        raise ApiError(401, "SESSION_EXPIRED", "모의 세션이 필요합니다.")
    role = {"guest": "GUEST", "admin": "ADMIN", "member": "MEMBER"}[cad_private_preview]
    return AuthContext(
        "GUEST" if role == "GUEST" else "MEMBER",
        "901",
        901,
        1,
        901,
        frozenset({role}),
        "synthetic",
    )


app.dependency_overrides[resolve_auth] = preview_auth


def session(role):
    return {
        "actorKind": "GUEST" if role == "GUEST" else "MEMBER",
        "workspaceId": 901,
        "generationId": 1,
        "roles": [role],
        "csrfToken": "synthetic",
        "expiresAt": None,
    }


@app.middleware("http")
async def fixture(request, call_next):
    path = request.url.path
    cookie = request.cookies.get("cad_private_preview")
    if path == "/api/v1/core/guest-sessions" and request.method == "POST":
        response = JSONResponse({"data": session("GUEST")}, status_code=201)
        response.set_cookie("cad_private_preview", "guest", httponly=True)
        return response
    if path == "/api/v1/core/sessions" and request.method == "POST":
        body = await request.json()
        kind = "admin" if body.get("loginId") == "admin-preview" else "member"
        response = JSONResponse(
            {"data": session("ADMIN" if kind == "admin" else "MEMBER")}
        )
        response.set_cookie("cad_private_preview", kind, httponly=True)
        return response
    if path == "/api/v1/core/sessions/current":
        if request.method == "DELETE":
            response = JSONResponse({"data": None})
            response.delete_cookie("cad_private_preview")
            return response
        if cookie not in {"guest", "admin", "member"}:
            return JSONResponse(
                {"error": {"code": "SESSION_EXPIRED", "message": "모의 세션 없음"}},
                status_code=401,
            )
        return JSONResponse(
            {
                "data": session(
                    {"guest": "GUEST", "admin": "ADMIN", "member": "MEMBER"}[cookie]
                )
            }
        )
    if path == "/api/v1/core/workspace/modules":
        return JSONResponse(
            {
                "data": [
                    {"moduleKey": key, "enabled": True, "updatedAt": None}
                    for key in ["mes", "erp", "fems", "qms", "wms", "bems", "spc", "gw"]
                ]
            }
        )
    if path == "/api/v1/core/reviews/summary":
        return JSONResponse({"data": []})
    return await call_next(request)
