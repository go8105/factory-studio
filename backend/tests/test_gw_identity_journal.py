"""Real PostgreSQL/HTTP connection revocation and journal storage failure."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_gw_company import context
from test_gw_company_http import create_doc
from test_gw_company_work import api, connect_staff, initialize
from test_hr_work import company_env  # noqa: F401
from test_security_journal import journal  # noqa: F401

from fs.core.security.journal import verified_records, verify
from fs.gw import company
from fs.gw.security_journal import confirm_records, record


def inspect_cli(head):
    root = Path(__file__).resolve().parents[2]
    return subprocess.run(
        [
            sys.executable,
            str(root / "tools/gw_identity_journal.py"),
            "--expected-head",
            head,
            "--check-database",
        ],
        env={**os.environ, "PYTHONPATH": str(root / "backend/src")},
        capture_output=True,
        text=True,
        check=False,
    )


def test_http_revocation_record_and_storage_failure(company_env, journal):  # noqa: F811
    engine, co, admin, _ = company_env
    directory, key = journal
    initialize(company_env)
    assert verify(directory, key)["records"] == 1
    _, binding = connect_staff(company_env)
    assert verify(directory, key)["records"] == 4

    def current():
        with engine.connect() as c:
            return c.execute(
                text(
                    "SELECT state,version FROM gw.person_identity_binding WHERE id=:id"
                ),
                {"id": int(binding)},
            ).one()

    before = current()
    values = {"expectedVersion": before.version, "reason": "합성 연결 회수 검증"}
    idempotency_key = str(uuid4())
    directory.chmod(0o755)
    failed = api(
        admin, co, f"identity-bindings/{binding}/suspend", values, key=idempotency_key
    )
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "SECURITY_JOURNAL_UNAVAILABLE"
    assert current() == before
    directory.chmod(0o700)
    saved = api(
        admin, co, f"identity-bindings/{binding}/suspend", values, key=idempotency_key
    )
    assert saved.status_code == 200
    assert current().state == "SUSPENDED"
    state = verify(directory, key)
    assert state["records"] == 5 and not state["completenessConfirmed"]
    assert (
        api(
            admin,
            co,
            f"identity-bindings/{binding}/suspend",
            values,
            key=idempotency_key,
        ).status_code
        == 200
    )
    assert verify(directory, key)["records"] == 5

    state, records = verified_records(directory, key, state["head"])
    with engine.connect() as c:
        matched = confirm_records(c, records)
    assert matched["commitsConfirmed"] and matched["matchedRecords"] == 5
    assert not matched["completenessConfirmed"]
    assert any("acl" in r["payload"]["snapshot"] for r in records)
    cli = inspect_cli(state["head"])
    assert cli.returncode == 0 and json.loads(cli.stdout)["commitsConfirmed"]
    # Exact scope and metadata must match, not just a digest somewhere in the DB.
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.audit_event SET summary=jsonb_set(summary,'{generationId}','\"different\"') WHERE entity_key=:digest"
            ),
            {"digest": records[-1]["digest"]},
        )
    with engine.connect() as c:
        assert confirm_records(c, records)["unconfirmedRecords"] == 1
    cli = inspect_cli(state["head"])
    assert cli.returncode == 3 and not json.loads(cli.stdout)["commitsConfirmed"]


def test_company_document_actions_and_uncommitted_intent(company_env, journal):  # noqa: F811
    engine, co, admin, staff = company_env
    directory, key = journal
    _, _, doc = create_doc(company_env)
    submitted = api(
        admin, co, f"documents/{doc['id']}/submit", {"expectedVersion": doc["version"]}
    )
    assert submitted.status_code == 200
    approved = api(
        staff,
        co,
        f"documents/{doc['id']}/approve",
        {"expectedVersion": submitted.json()["data"]["version"]},
    )
    assert approved.status_code == 200
    state = verify(directory, key)
    _, records = verified_records(directory, key, state["head"])
    with engine.connect() as c:
        assert confirm_records(c, records)["commitsConfirmed"]
    acl_records = [r["payload"] for r in records if "acl" in r["payload"]["snapshot"]]
    assert len(acl_records) >= 5  # HR import, route, draft, submit, approve.
    for payload in acl_records:
        assert str(payload["workspaceId"]) == str(co["companyId"])
        acl = payload["snapshot"]["acl"]
        for kind in ("people", "bindings", "roles", "readers"):
            assert all(
                str(r["workspace_id"]) == str(co["companyId"]) for r in acl[kind]
            )
        assert all(
            set(scopes) <= {f"{payload['workspaceId']}/{payload['generationId']}"}
            for scopes in acl["guards"].values()
        )

    ctx = context(engine, admin)
    with pytest.raises(RuntimeError, match="synthetic rollback"), engine.begin() as c:
        scoped, _ = company.resolve_company(c, ctx, co["companyId"])
        record(c, scoped, "synthetic.rollback", include_acl=True)
        raise RuntimeError("synthetic rollback")
    state = verify(directory, key)
    _, after = verified_records(directory, key, state["head"])
    assert len(after) == len(records) + 1
    with engine.connect() as c:
        result = confirm_records(c, after)
    assert result["unconfirmedRecords"] == 1 and not result["commitsConfirmed"]
    cli = inspect_cli(state["head"])
    assert cli.returncode == 3
    assert "synthetic.rollback" not in cli.stdout
