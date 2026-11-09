"""공통 휴일 달력 API (DSN-16 Q1, P-08). 체험 공간은 본인 달력을 직접 고친다."""

from test_bems import _call, _ok

H = "/api/v1/core/holidays"


def _create(client, created, day="2026-09-24", **extra):
    return _call(
        client,
        created,
        "POST",
        H,
        {"date": day, "name": "임시 휴무", "kind": "COMPANY", **extra},
    )


def test_list_defaults_to_business_year_with_seeded_public_holidays(guest_space):
    client, _, _ = guest_space
    rows = _ok(client.get(H))
    assert [r["date"] for r in rows] == sorted(r["date"] for r in rows)
    assert {r["kind"] for r in rows} == {"PUBLIC"}
    assert {r["date"] for r in rows} >= {"2026-10-03", "2026-12-25"}
    assert all(r["date"].startswith("2026") for r in rows)
    assert all(
        r["date"].startswith("2025") for r in _ok(client.get(H, params={"year": 2025}))
    )
    assert client.get(H).json()["page"]["total"] == len(rows)


def test_create_update_delete_and_duplicate_date(guest_space):
    client, created, _ = guest_space
    row = _ok(_create(client, created), 201)
    assert (row["date"], row["kind"]) == ("2026-09-24", "COMPANY")
    duplicate = _create(client, created)
    assert duplicate.status_code == 400
    assert "date" in duplicate.json()["error"]["details"]["fields"]
    renamed = _ok(
        _call(
            client,
            created,
            "PATCH",
            f"{H}/{row['id']}",
            {"name": "창립기념일", "date": "2026-09-25"},
        )
    )
    assert (renamed["name"], renamed["date"]) == ("창립기념일", "2026-09-25")
    other = _ok(_create(client, created, "2026-09-26"), 201)
    clash = _call(
        client, created, "PATCH", f"{H}/{other['id']}", {"date": "2026-09-25"}
    )
    assert clash.status_code == 400
    _ok(_call(client, created, "DELETE", f"{H}/{other['id']}"))
    _ok(_call(client, created, "PATCH", f"{H}/{row['id']}", {"date": "2026-09-24"}))
    assert _call(client, created, "PATCH", f"{H}/{row['id']}", {}).status_code == 400
    assert (
        _call(
            client, created, "PATCH", f"{H}/{row['id']}", {"kind": "OTHER"}
        ).status_code
        == 400
    )
    _ok(_call(client, created, "DELETE", f"{H}/{row['id']}"))
    assert "2026-09-24" not in {r["date"] for r in _ok(client.get(H))}
    assert _call(client, created, "DELETE", f"{H}/{row['id']}").status_code == 404


def test_create_is_idempotent_and_validates(guest_space):
    client, created, _ = guest_space
    first = _call(
        client,
        created,
        "POST",
        H,
        {"date": "2026-12-24", "name": "성탄 전야", "kind": "COMPANY"},
        key="hol-1",
    )
    again = _call(
        client,
        created,
        "POST",
        H,
        {"date": "2026-12-24", "name": "성탄 전야", "kind": "COMPANY"},
        key="hol-1",
    )
    assert first.status_code == again.status_code == 201
    assert first.json() == again.json()
    assert _create(client, created, "1999-01-01").status_code == 400
    blank = _call(client, created, "POST", H, {"date": "2026-12-26", "name": "  "})
    assert blank.status_code == 400
    assert _create(client, created, "2026-12-27", kind="PRIVATE").status_code == 400


def test_bems_reads_the_same_calendar(guest_space):
    """BEMS는 core 달력을 날짜로 읽는다(휴일 추가 → 같은 날 스케줄 구분이 바뀐다)는 계약은
    test_bems_lighting에서 시뮬레이션으로 확인한다. 여기서는 interface 조회만 본다."""
    from datetime import date

    from fs.common.auth import AuthContext
    from fs.common.db import get_engine
    from fs.core import interface as core

    client, created, _ = guest_space
    _ok(_create(client, created, "2026-09-25"), 201)
    context = AuthContext(
        actor_kind="GUEST",
        actor_key="x",
        workspace_id=created["workspaceId"],
        generation_id=created["generationId"],
        user_id=None,
        roles=frozenset({"GUEST"}),
        token="t",
    )
    with get_engine().connect() as connection:
        rows = core.holidays(connection, context, date(2026, 9, 24), date(2026, 9, 26))
    assert [r["date"] for r in rows] == ["2026-09-25"]
