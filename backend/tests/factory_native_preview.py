"""LOCAL E2E ONLY: fake authentication; real native subprocess. Never deploy."""

import os
from pathlib import Path

from fs.common.auth import AuthContext, resolve_auth
from fs.common.security import guest_csrf_token
from fs.main import create_app

os.environ["DATABASE_URL"] = "postgresql+psycopg://unused/unused_test"
os.environ["SESSION_SECRET"] = "native-preview-secret-32-characters-long"
os.environ["VISION_CORE_EXECUTABLE"] = str(
    Path(__file__).resolve().parents[2] / "work/inspection-core/bin/inspection_core"
)
app = create_app()
app.dependency_overrides[resolve_auth] = lambda: AuthContext(
    "GUEST", "demo", 10, 20, None, frozenset({"GUEST"}), "g_preview"
)


@app.get("/_test/session")
def preview_session():
    return {
        "data": {
            "actorKind": "GUEST",
            "workspaceId": 10,
            "generationId": 20,
            "roles": [],
            "csrfToken": guest_csrf_token(os.environ["SESSION_SECRET"], "g_preview"),
            "expiresAt": None,
        }
    }
