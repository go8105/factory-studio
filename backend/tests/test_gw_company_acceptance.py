"""05: 1회사·1부서·10계정 합성 부하와 폐쇄 복구 리허설. 운영 인수 아님."""

# ruff: noqa: F811
import json
import os
import statistics
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.hr.work_setup import create_company
from fs.main import create_app
from seed.generate import create_template
from sqlalchemy import text
from test_gw_company_http import ok
from test_gw_company_work import api
from test_gw_wms_merge import fingerprint, isolated_database  # noqa: F401
from test_hr_users import manage


def record(kind, data):
    path = os.environ.get("GW_ACCEPTANCE_REPORT")
    if path:
        p = Path(path)
        current = json.loads(p.read_text()) if p.exists() else {}
        current[kind] = data
        p.write_text(json.dumps(current, ensure_ascii=False, indent=2))


def login(login_id, password):
    client = TestClient(create_app())
    r = client.post(
        "/api/v1/core/sessions",
        json={"loginId": login_id, "password": password},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert r.status_code == 201
    client.csrf = r.json()["data"]["csrfToken"]
    return client


@pytest.fixture
def ten_people(isolated_database):
    engine = isolated_database
    command.upgrade(Config("backend/alembic.ini"), "head")
    passwords = ["Synthetic-" + uuid4().hex for _ in range(10)]
    with engine.begin() as c:
        create_template(c, date(2026, 10, 18))
        co = create_company(
            c,
            {
                "companyName": "합성 창업 준비 회사",
                "loginId": "synthetic-owner",
                "name": "합성 관리자",
                "password": passwords[0],
                "employeeCode": "SYN-001",
                "workStart": "09:00",
                "dailyMinutes": 480,
                "breakMinutes": 60,
                "annualDays": 15,
            },
        )
    clients = [login("synthetic-owner", passwords[0])]
    try:
        admin = clients[0]
        ok(
            api(
                admin,
                co,
                "company-setup",
                {"employeeCode": "SYN-001", "reason": "10인 합성 인수 준비"},
            )
        )
        for n in range(1, 10):
            assert (
                manage(
                    admin,
                    co,
                    body={
                        "loginId": f"synthetic-staff-{n}",
                        "name": f"합성 직원 {n}",
                        "password": passwords[n],
                        "employeeCode": f"SYN-{n + 1:03}",
                        "annualDays": 15,
                        "role": "STAFF",
                    },
                ).status_code
                == 200
            )
            clients.append(login(f"synthetic-staff-{n}", passwords[n]))
        preview = ok(api(admin, co, "company-hr-preview", method="GET"))
        ok(
            api(
                admin,
                co,
                "company-hr-import",
                {
                    "previewDigest": preview["digest"],
                    "employeeCodes": [f"SYN-{n:03}" for n in range(2, 11)],
                    "reason": "9명 직원 명시적 가져오기",
                },
            )
        )
        people = ok(api(admin, co, "people", method="GET"))["rows"]
        candidates = ok(api(admin, co, "identity-candidates", method="GET"))
        # Identity IDs are obtained from the real company directory contract.
        rows = (
            candidates["items"]
            if isinstance(candidates, dict) and "items" in candidates
            else candidates["rows"]
            if isinstance(candidates, dict)
            else candidates
        )
        bindings = []
        for n, client in enumerate(clients[1:], 1):
            person = next(p for p in people if p["code"] == f"SYN-{n + 1:03}")
            candidate = next(x for x in rows if x["name"] == f"합성 직원 {n}")
            binding = ok(
                api(
                    admin,
                    co,
                    "identity-bindings",
                    {
                        "personId": person["id"],
                        "userId": str(candidate.get("userId", candidate.get("id"))),
                        "reason": "합성 본인 연결 요청",
                    },
                )
            )
            ok(
                api(
                    client,
                    co,
                    "me/binding/accept",
                    {"bindingId": binding["id"], "expectedVersion": 1},
                )
            )
            bindings.append(binding)
        with engine.connect() as c:
            assert (
                c.execute(
                    text("SELECT count(*) FROM hr.department WHERE workspace_id=:w"),
                    {"w": co["companyId"]},
                ).scalar_one()
                == 1
            )
            assert (
                c.execute(
                    text(
                        "SELECT count(*) FROM gw.person_identity_binding WHERE workspace_id=:w AND state='ACTIVE'"
                    ),
                    {"w": co["companyId"]},
                ).scalar_one()
                == 10
            )
        yield engine, co, clients, people, bindings, passwords
    finally:
        for client in clients:
            client.close()


def test_ten_simultaneous_principals_read_and_write(ten_people):
    _, co, clients, people, _, _ = ten_people
    channel = ok(
        api(
            clients[0],
            co,
            "channels",
            {
                "name": "합성 10인 대화",
                "channelKind": "GROUP",
                "memberIds": [p["id"] for p in people if p["code"] != "SYN-001"],
            },
        )
    )

    def scenario(pair):
        n, client = pair
        measurements = []
        for _ in range(10):
            started = perf_counter()
            assert api(client, co, "dashboard", method="GET").status_code == 200
            measurements.append((perf_counter() - started) * 1000)
        started = perf_counter()
        draft = ok(
            api(
                client,
                co,
                "posts",
                {
                    "boardKind": "FREE",
                    "visibility": "WORKSPACE",
                    "title": f"합성 비공개 초안 {n}",
                    "body": "10인 경합 검증",
                },
            )
        )
        key = str(uuid4())
        body = {"body": f"합성 메시지 {n}", "clientKey": str(uuid4())}
        message = ok(
            api(client, co, f"channels/{channel['id']}/messages", body, key=key)
        )
        assert (
            ok(api(client, co, f"channels/{channel['id']}/messages", body, key=key))[
                "id"
            ]
            == message["id"]
        )
        measurements.append((perf_counter() - started) * 1000)
        return measurements, draft["id"]

    started = perf_counter()
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(scenario, enumerate(clients)))
    elapsed = perf_counter() - started
    for n, (_, draft_id) in enumerate(results):
        assert (
            api(
                clients[(n + 1) % 10], co, f"posts/{draft_id}", method="GET"
            ).status_code
            == 404
        )
    messages = ok(
        api(clients[0], co, f"channels/{channel['id']}/messages", method="GET")
    )["messages"]
    assert len(messages) == 10 and len({m["seq"] for m in messages}) == 10
    timings = sorted(t for times, _ in results for t in times)
    record(
        "ten_people",
        {
            "company_count": 1,
            "department_count": 1,
            "people": 10,
            "max_workers": 10,
            "dashboard_reads": 100,
            "draft_writes": 10,
            "message_writes": 10,
            "same_key_retries": 10,
            "private_other_reads_denied": 10,
            "elapsed_seconds": round(elapsed, 3),
            "mixed_sample_p50_ms": round(statistics.median(timings), 2),
            "mixed_sample_p95_ms": round(timings[int(len(timings) * 0.95) - 1], 2),
            "max_ms": round(max(timings), 2),
            "transport": "in-process ASGI; network/phone/production capacity unverified",
        },
    )


def test_closed_restore_preserves_rows_then_reapplies_revocation(
    ten_people, monkeypatch
):
    engine, co, clients, _, bindings, passwords = ten_people
    container = os.environ.get("PG_TEST_CONTAINER")
    if not container:
        pytest.skip("PG_TEST_CONTAINER is required for isolated pg_dump/restore")
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "owned_restore_guard", Path(__file__).parents[2] / "tools/gw_route_verify.py"
    )
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    url = engine.url
    guard.validate_restore_container(
        url, container, os.environ.get("FS_GW_ROUTE_VERIFY_OWNER"), strict=True
    )
    columns, before = fingerprint(engine)
    started = perf_counter()
    dump = subprocess.run(
        [
            "docker",
            "exec",
            container,
            "pg_dump",
            "-U",
            url.username,
            "-Fc",
            url.database,
        ],
        capture_output=True,
        check=True,
    ).stdout
    backup_seconds = perf_counter() - started
    active = ok(api(clients[0], co, "identity-bindings", method="GET"))
    rows = active["items"] if "items" in active else active["rows"]
    binding = next(x for x in rows if x["id"] == bindings[0]["id"])
    ok(
        api(
            clients[0],
            co,
            f"identity-bindings/{binding['id']}/suspend",
            {
                "expectedVersion": binding["version"],
                "reason": "백업 이후 독립 보관할 권한 회수",
            },
        )
    )
    # Restore into another closed, freshly-created test database.
    name = f"gw_restore_{uuid4().hex}_test"
    from sqlalchemy import create_engine

    admin_engine = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    restored = create_engine(url.set(database=name))
    with admin_engine.connect() as c:
        c.exec_driver_sql(f'CREATE DATABASE "{name}"')
    try:
        started = perf_counter()
        subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                container,
                "pg_restore",
                "-U",
                url.username,
                "-d",
                name,
                "--exit-on-error",
            ],
            input=dump,
            capture_output=True,
            check=True,
        )
        assert fingerprint(restored, columns)[1] == before
        # All restored sessions remain closed; a separate revocation manifest is
        # reapplied through authorized API before any staff access is released.
        with restored.begin() as c:
            c.exec_driver_sql(
                "UPDATE core.auth_session SET revoked_at=clock_timestamp()"
            )
        reset_engine()
        monkeypatch.setenv(
            "DATABASE_URL", url.set(database=name).render_as_string(hide_password=False)
        )
        for client in clients:
            assert api(client, co, "me", method="GET").status_code == 401
        owner = login("synthetic-owner", passwords[0])
        staff = login("synthetic-staff-1", passwords[1])
        try:
            ok(
                api(
                    owner,
                    co,
                    f"identity-bindings/{binding['id']}/suspend",
                    {
                        "expectedVersion": binding["version"],
                        "reason": "폐쇄 복구: 백업 이후 회수 재적용",
                    },
                )
            )
            assert api(staff, co, "documents", method="GET").status_code == 403
            assert api(owner, co, "dashboard", method="GET").status_code == 200
        finally:
            owner.close()
            staff.close()
        record(
            "restore",
            {
                "table_fingerprints_equal": len(before),
                "restored_old_sessions_denied": 10,
                "revocation_reapplied": True,
                "backup_seconds": round(backup_seconds, 3),
                "restore_check_seconds": round(perf_counter() - started, 3),
                "dump_bytes": len(dump),
                "rpo_rto_company_targets": "UNSET",
                "production_acceptance": False,
            },
        )
    finally:
        reset_engine()
        restored.dispose()
        with admin_engine.connect() as c:
            c.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin_engine.dispose()
