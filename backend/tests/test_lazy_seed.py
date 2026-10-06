"""W0-1 지연 복사: 솔루션 시드는 처음 열 때 한 번만, 실패하면 흔적 없이, 세대가 바뀌면 다시."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
import seed.copy
from fs.common.auth import AuthContext
from fs.common.scope import module_available, seed_ready
from sqlalchemy import text

SEEDS = ()  # 지연 복사 자체를 검사한다 — 미리 복사하지 않는다


def _context(workspace_id: int) -> AuthContext:
    return AuthContext(
        actor_kind="GUEST",
        actor_key="lazy-seed-test",
        workspace_id=workspace_id,
        generation_id=None,
        user_id=None,
        roles=frozenset(),
        token="g_lazy",
    )


def _rows(engine, schema: str, workspace_id: int) -> int:
    with engine.connect() as connection:
        tables = connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname=:s"), {"s": schema}
        ).scalars()
        return sum(
            connection.execute(
                text(f'SELECT count(*) FROM "{schema}"."{t}" WHERE workspace_id=:w'),
                {"w": workspace_id},
            ).scalar_one()
            for t in list(tables)
        )


def _available(engine, workspace_id: int, module: str) -> bool:
    with engine.connect() as connection:
        return module_available(connection, workspace_id, module)


def test_first_open_copies_only_that_solution_once(guest_space):
    client, created, engine = guest_space
    w = created["workspaceId"]
    assert _rows(engine, "qms", w) == 0
    assert not _available(engine, w, "qms")  # 교차 조회: 아직 열지 않음 = 꺼짐과 같음
    dependency = seed_ready("qms")
    with ThreadPoolExecutor(4) as pool:  # 처음 열기가 겹쳐도 한 번만 복사
        list(pool.map(lambda _: dependency(_context(w)), range(4)))
    copied = _rows(engine, "qms", w)
    assert copied > 0 and _available(engine, w, "qms")
    assert _rows(engine, "mes", w) == 0
    assert client.get("/api/v1/qms/dashboard").status_code == 200
    assert _rows(engine, "qms", w) == copied


def test_failed_copy_leaves_no_rows_and_retries(guest_space, monkeypatch):
    _, created, engine = guest_space
    w = created["workspaceId"]
    original = seed.copy._copy_business_rows

    def copy_then_fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected lazy copy failure")

    monkeypatch.setattr(seed.copy, "_copy_business_rows", copy_then_fail)
    with pytest.raises(RuntimeError, match="injected"):
        seed_ready("wms")(_context(w))
    assert _rows(engine, "wms", w) == 0 and not _available(engine, w, "wms")
    monkeypatch.setattr(seed.copy, "_copy_business_rows", original)
    seed_ready("wms")(_context(w))
    assert _rows(engine, "wms", w) > 0 and _available(engine, w, "wms")


def test_reset_makes_solutions_lazy_again(guest_space):
    client, created, engine = guest_space
    w = created["workspaceId"]
    csrf = created["csrfToken"]
    assert client.get("/api/v1/spc/dashboard").status_code == 200
    assert _available(engine, w, "spc")
    reset = client.post(
        "/api/v1/core/workspace/generations",
        headers={"Idempotency-Key": str(uuid4()), "X-CSRF-Token": csrf},
    )
    assert reset.status_code == 201, reset.text
    assert not _available(engine, w, "spc")  # 새 세대 — 다시 처음 열 때 복사
    assert client.get("/api/v1/spc/dashboard").status_code == 200
    assert _available(engine, w, "spc")


def test_disabled_solution_is_not_available_even_when_seeded(guest_space):
    _, created, engine = guest_space
    w = created["workspaceId"]
    seed_ready("fems")(_context(w))
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE core.workspace_module SET enabled=false WHERE workspace_id=:w AND module_key='fems'"
            ),
            {"w": w},
        )
    assert not _available(engine, w, "fems")
