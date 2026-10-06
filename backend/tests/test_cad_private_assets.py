from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from fs.cad_cam import router as assets
from fs.common.auth import AuthContext, resolve_auth
from fs.main import create_app

ADMIN = AuthContext("MEMBER", "1", 1, 1, 1, frozenset({"ADMIN"}), "synthetic")


@pytest.fixture
def client(tmp_path, monkeypatch):
    (tmp_path / "soap-poc.html").write_text("private-design")
    (tmp_path / "part.stl").write_bytes(b"private-stl")
    (tmp_path / "outside-link.stl").symlink_to(tmp_path.parent / "outside.stl")
    (tmp_path.parent / "outside.stl").write_bytes(b"outside")
    monkeypatch.setattr(assets, "ASSET_ROOT", tmp_path)
    app = create_app()
    with TestClient(app) as client:
        yield client


def test_anonymous_denied_without_database(client):
    assert client.get("/api/v1/cad/admin/soap-poc/soap-poc.html").status_code == 401


@pytest.mark.parametrize(
    "context",
    [
        replace(ADMIN, roles=frozenset({"MEMBER"})),
        replace(ADMIN, actor_kind="GUEST", roles=frozenset({"GUEST"})),
        replace(ADMIN, actor_kind="GUEST"),
    ],
)
@pytest.mark.parametrize("name", ["soap-poc.html", "part.stl"])
def test_non_admin_cannot_read_any_file(client, context, name):
    client.app.dependency_overrides[resolve_auth] = lambda: context
    response = client.get("/api/v1/cad/admin/soap-poc/" + name)
    assert response.status_code == 403
    assert "private-design" not in response.text


def test_admin_files_no_cache_and_revocation(client):
    client.app.dependency_overrides[resolve_auth] = lambda: ADMIN
    response = client.get("/api/v1/cad/admin/soap-poc/part.stl")
    assert response.status_code == 200 and response.content == b"private-stl"
    assert response.headers["cache-control"] == "private, no-store"
    client.app.dependency_overrides[resolve_auth] = lambda: replace(
        ADMIN, roles=frozenset()
    )
    assert client.get("/api/v1/cad/admin/soap-poc/part.stl").status_code == 403


@pytest.mark.parametrize(
    "name",
    [
        "missing.stl",
        "outside-link.stl",
        "%2e%2e%2foutside.stl",
        "%2fetc%2fpasswd",
        ".hidden.stl",
    ],
)
def test_admin_path_cannot_escape_asset_root(client, name):
    client.app.dependency_overrides[resolve_auth] = lambda: ADMIN
    assert client.get("/api/v1/cad/admin/soap-poc/" + name).status_code == 404
