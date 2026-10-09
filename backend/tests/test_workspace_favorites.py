"""Real PostgreSQL: menu preferences isolation, persistence and atomic writes."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fs.common.auth import resolve_token
from fs.common.errors import ApiError
from fs.core import favorites
from fs.core.service import _delete_guest, create_member_account
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

PATH = "/api/v1/core/workspace/menus"
SEEDS = ()


def put(client, session, ids, *, version=1, mode="favorites", key=None):
    return client.put(
        PATH,
        json={"menuIds": ids, "sidebarMode": mode, "expectedVersion": version},
        headers={
            "X-CSRF-Token": session["csrfToken"],
            "Idempotency-Key": key or str(uuid4()),
        },
    )


def test_default_configuration_does_not_seed_business_modules(guest_space):
    client, session, engine = guest_space
    assert client.get(PATH).json()["data"] == {
        "menuIds": favorites.catalog()["defaultMenuIds"],
        "sidebarMode": "favorites",
        "version": 1,
    }
    with engine.connect() as c:
        row = c.execute(
            text(
                "SELECT menu_preferences,menu_preferences_version FROM core.workspace WHERE id=:w"
            ),
            {"w": session["workspaceId"]},
        ).one()
        assert row == (None, 1)
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM core.workspace_module WHERE workspace_id=:w AND seeded_generation_id IS NOT NULL"
                ),
                {"w": session["workspaceId"]},
            ).scalar_one()
            == 0
        )


def test_order_empty_selection_and_reset_preserve_preferences(guest_space):
    client, session, _ = guest_space
    ids = ["erp:dashboard", "gw:pending", "mes:work-orders"]
    result = put(client, session, ids, mode="all")
    assert result.status_code == 200, result.text
    assert result.json()["data"] == {"menuIds": ids, "sidebarMode": "all", "version": 2}
    reset = client.post(
        "/api/v1/core/workspace/generations",
        headers={"X-CSRF-Token": session["csrfToken"], "Idempotency-Key": str(uuid4())},
    )
    assert reset.status_code == 201, reset.text
    assert client.get(PATH).json()["data"] == result.json()["data"]
    cleared = put(client, session, [], version=2)
    assert cleared.status_code == 200
    assert client.get(PATH).json()["data"]["menuIds"] == []


def test_separate_guest_isolation_csrf_and_authentication(guest_space):
    client, session, engine = guest_space
    assert put(client, session, ["gw:chat"]).status_code == 200
    with TestClient(client.app, base_url="https://testserver") as other:
        assert other.get(PATH).status_code == 401
        created = other.post(
            "/api/v1/core/guest-sessions",
            json={"nickname": "즐겨찾기 격리"},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert created.status_code == 201, created.text
        second = created.json()["data"]
        assert (
            other.get(PATH).json()["data"]["menuIds"]
            == favorites.catalog()["defaultMenuIds"]
        )
        denied = other.put(
            PATH,
            json={"menuIds": [], "sidebarMode": "all", "expectedVersion": 1},
            headers={
                "Idempotency-Key": str(uuid4()),
                "X-CSRF-Token": session["csrfToken"],
            },
        )
        assert denied.status_code == 403
        assert put(other, second, ["mes:lots"]).status_code == 200
        assert client.get(PATH).json()["data"]["menuIds"] == ["gw:chat"]
    with engine.begin() as c:
        _delete_guest(c, second["workspaceId"])


def test_replay_conflict_validation_and_single_audit(guest_space):
    client, session, engine = guest_space
    key = str(uuid4())
    first = put(client, session, ["gw:pending"], key=key)
    assert first.status_code == 200
    assert put(client, session, ["gw:pending"], key=key).json() == first.json()
    assert put(client, session, ["mes:lots"], key=key).status_code == 422
    assert put(client, session, ["mes:lots"]).status_code == 409
    for ids in [
        ["gw:chat", "gw:chat"],
        ["erp:not-a-menu"],
        ["unknown:dashboard"],
        ["//outside/path"],
    ]:
        invalid = put(client, session, ids, version=2)
        assert invalid.status_code == 400, invalid.text
    with engine.connect() as c:
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM core.audit_event WHERE workspace_id=:w AND action='workspace.menus.updated'"
                ),
                {"w": session["workspaceId"]},
            ).scalar_one()
            == 1
        )
    assert client.get(PATH).json()["data"]["version"] == 2


def test_concurrent_updates_cannot_overwrite_another_window(guest_space):
    client, _, engine = guest_space
    with engine.begin() as c:
        context = resolve_token(c, client.cookies.get("fs_session"))
    barrier = Barrier(2)

    def change(menu):
        payload = favorites.MenuPreferencesUpdate(
            menuIds=[menu], sidebarMode="favorites", expectedVersion=1
        )
        barrier.wait(timeout=10)
        try:
            with engine.begin() as c:
                return favorites.update(c, context, payload, str(uuid4()))
        except ApiError as e:
            return e.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(change, ["gw:chat", "mes:lots"]))
    assert sum(isinstance(r, dict) and r["version"] == 2 for r in results) == 1
    assert results.count(409) == 1
    assert client.get(PATH).json()["data"]["version"] == 2


def test_audit_failure_rolls_back_preferences_and_receipt(guest_space, monkeypatch):
    client, session, engine = guest_space
    with engine.begin() as c:
        context = resolve_token(c, client.cookies.get("fs_session"))

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(favorites, "_audit", fail)
    key = str(uuid4())
    with (
        pytest.raises(RuntimeError, match="synthetic audit failure"),
        engine.begin() as c,
    ):
        favorites.update(
            c,
            context,
            favorites.MenuPreferencesUpdate(
                menuIds=["gw:chat"], sidebarMode="all", expectedVersion=1
            ),
            key,
        )
    assert client.get(PATH).json()["data"]["version"] == 1
    with engine.connect() as c:
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM core.request_receipt WHERE workspace_id=:w AND request_key=:key"
                ),
                {"w": session["workspaceId"], "key": key},
            ).scalar_one()
            == 0
        )


def test_member_configuration_shared_by_two_login_sessions(guest_space):
    guest, _, engine = guest_space
    login = f"fav-{uuid4().hex}"
    password = "synthetic-favorite-member-01"
    with engine.begin() as c:
        account = create_member_account(
            c, login, "즐겨찾기 합성 회원", password, date(2026, 9, 24)
        )
    with (
        TestClient(guest.app, base_url="https://testserver") as first,
        TestClient(guest.app, base_url="https://testserver") as second,
    ):
        sessions = []
        for browser in (first, second):
            response = browser.post(
                "/api/v1/core/sessions",
                json={"loginId": login, "password": password},
                headers={"Idempotency-Key": str(uuid4())},
            )
            assert response.status_code == 201, response.text
            sessions.append(response.json()["data"])
        assert (
            put(first, sessions[0], ["erp:dashboard", "hr:overview"]).status_code == 200
        )
        assert second.get(PATH).json()["data"]["menuIds"] == [
            "erp:dashboard",
            "hr:overview",
        ]
        assert put(second, sessions[1], ["gw:chat"], version=2).status_code == 200
        assert first.get(PATH).json()["data"]["menuIds"] == ["gw:chat"]
    with engine.begin() as c:
        _delete_guest(c, account["workspaceId"])
        # Keep the synthetic subject for retired audit records; revoke its sessions.
        c.execute(
            text(
                "UPDATE core.auth_session SET revoked_at=clock_timestamp() WHERE user_id=(SELECT id FROM core.app_user WHERE login_id=:login)"
            ),
            {"login": login},
        )


def test_database_rejects_malformed_preferences_and_bad_version(guest_space):
    _, session, engine = guest_space
    with engine.begin() as c:
        for value in [
            [],
            {"menuIds": [], "sidebarMode": "unknown"},
            {"menuIds": [], "sidebarMode": None},
            {"menuIds": "wrong", "sidebarMode": "all"},
        ]:
            with pytest.raises(IntegrityError), c.begin_nested():
                c.execute(
                    text(
                        "UPDATE core.workspace SET menu_preferences=CAST(:value AS jsonb) WHERE id=:w"
                    ),
                    {"w": session["workspaceId"], "value": json.dumps(value)},
                )
        with pytest.raises(IntegrityError), c.begin_nested():
            c.execute(
                text(
                    "UPDATE core.workspace SET menu_preferences_version=0 WHERE id=:w"
                ),
                {"w": session["workspaceId"]},
            )
