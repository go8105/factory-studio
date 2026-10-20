"""Real PostgreSQL/HTTP connection revocation and journal storage failure."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fs.core.security.journal import verified_records, verify
from fs.gw import company
from fs.gw.security_journal import confirm_records, record
from sqlalchemy import text
from test_gw_company import context
from test_gw_company_http import create_doc
from test_gw_company_work import api, connect_staff, initialize
from test_hr_work import company_env  # noqa: F401
from test_security_journal import journal  # noqa: F401


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


def test_company_route_cli_binds_current_policy_and_actual_suspend(
    company_env,  # noqa: F811
    journal,  # noqa: F811
    monkeypatch,
    tmp_path,
):
    from test_gw_company_work import ok
    from test_gw_evidence import prepare

    prepare(company_env, monkeypatch)
    _engine, co, admin, staff = company_env
    binding = ok(api(staff, co, "me/binding", method="GET"))
    directory, key = journal
    directory.chmod(0o755)
    values = {"expectedVersion": binding["version"], "reason": "합성 저장 실패 롤백"}
    assert (
        api(admin, co, f"identity-bindings/{binding['id']}/suspend", values).status_code
        == 503
    )
    directory.chmod(0o700)
    unchanged = ok(api(staff, co, "me/binding", method="GET"))
    assert unchanged["state"] == "ACTIVE" and unchanged["version"] == binding["version"]
    assert (
        api(admin, co, f"identity-bindings/{binding['id']}/suspend", values).status_code
        == 200
    )
    assert api(staff, co, "posts", method="GET").status_code == 403
    state = verify(directory, key)
    tmp_path.chmod(0o700)
    output_file = tmp_path / "routes.json"
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools/gw_identity_journal.py"),
            "--expected-head",
            state["head"],
            "--company-id",
            str(co["companyId"]),
            "--review-report",
            str(output_file),
        ],
        env={**os.environ, "PYTHONPATH": str(root / "backend/src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    routes = output["identityRoutes"]
    assert routes == json.loads(output_file.read_text())["identityRoutes"]
    current = ok(api(admin, co, "operations", method="GET"))
    from fs.gw.operating_contract import OperatingPolicy

    assert (
        routes["assessmentPolicyDigest"]
        == OperatingPolicy.model_validate(current["policy"]).digest()
    )
    assert routes["workspaceId"] == str(co["companyId"])
    assert routes["assessmentCodeRevision"] == "abcdef012345"
    assert routes["head"] == state["head"]
    states = {r["route"]: r for r in routes["routes"]}
    assert states["BINDING_SUSPEND"]["state"] == "COMMIT_OBSERVED"
    assert states["BINDING_SUSPEND"]["records"] == 1
    assert states["BINDING_CANCEL"]["state"] == "MISSING"
    assert states["BINDING_RESUME"]["state"] == "MISSING"
    assert routes["result"] == "BLOCKED" and not routes["executionRevisionVerified"]
    assert not routes["revocationsReapplied"] and current["ready"] is False
