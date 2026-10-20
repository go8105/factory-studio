"""Owned PostgreSQL snapshots and synthetic admin-name permission boundaries."""

# ruff: noqa: F401,F811
import hashlib
import json

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from test_gw_company import context
from test_gw_company_work import api
from test_gw_evidence import prepare
from test_hr_work import company_env

from fs.core.backup import BackupError
from fs.gw.acceptance_preflight import collect, snapshot
from fs.gw.operating_contract import canonical


def configured(company_env, monkeypatch):
    prepare(company_env, monkeypatch)
    engine, co, admin, staff = company_env
    user = context(engine, admin).user_id
    with engine.begin() as c:
        # Only this fresh synthetic test DB gets an account named admin.
        c.execute(
            text("UPDATE core.app_user SET login_id='admin' WHERE id=:u"), {"u": user}
        )
        role = c.scalar(text("SELECT id FROM core.role WHERE role_key='ADMIN'"))
        if role is None:
            role = c.scalar(
                text(
                    "INSERT INTO core.role(role_key,description) VALUES ('ADMIN','합성 관리자') RETURNING id"
                )
            )
        c.execute(
            text(
                "INSERT INTO core.user_role(user_id,role_id) VALUES (:u,:r) ON CONFLICT DO NOTHING"
            ),
            {"u": user, "r": role},
        )
    return engine, co, admin, staff, user


def test_admin_named_platform_admin_needs_company_binding_and_gw_role(
    company_env, monkeypatch
):
    engine, co, admin, _, user = configured(company_env, monkeypatch)
    args = {"company_id": co["companyId"], "code_revision": "abcdef012345"}
    ctx, report = collect(engine, **args)
    assert report["administrator"]["platformAdministrator"]
    assert report["administrator"]["securityAdministrator"]
    assert report["administrator"]["menuRoleEligible"]
    assert report["administrator"]["businessSession"] == "NOT_CHECKED"
    assert report["counts"]["connectedPeople"] == 2 and report["result"] == "BLOCKED"
    assert report["companyIsExample"] and not report["ready"]
    assert report["contextDigest"] == hashlib.sha256(canonical(ctx)).hexdigest()
    assert api(admin, co, "operations", method="GET").json()["data"]["administrator"]
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE gw.role_grant SET is_active=false WHERE workspace_id=:w AND role_key='SECURITY_ADMIN'"
            ),
            {"w": co["companyId"]},
        )
    _, report = collect(engine, **args)
    assert report["administrator"]["platformAdministrator"]
    assert not report["administrator"]["securityAdministrator"]
    assert not report["administrator"]["menuRoleEligible"]
    assert (
        api(admin, co, "operations", method="GET").json()["data"]["administrator"]
        is False
    )
    assert api(admin, co, "operating-evidence", method="GET").status_code == 403
    with engine.begin() as c:
        b = c.execute(
            text(
                "SELECT generation_id,person_id FROM gw.person_identity_binding WHERE workspace_id=:w AND user_id=:u"
            ),
            {"w": co["companyId"], "u": user},
        ).one()
        c.execute(
            text(
                "INSERT INTO gw.role_grant(workspace_id,generation_id,person_id,role_key,changed_by_user_id,reason) VALUES (:w,:g,:p,'AUDITOR',:u,'합성 감사 역할')"
            ),
            {"w": co["companyId"], "g": b[0], "p": b[1], "u": user},
        )
    _, report = collect(engine, **args)
    assert (
        report["administrator"]["auditor"]
        and report["administrator"]["menuRoleEligible"]
    )
    current = api(admin, co, "operations", method="GET").json()["data"]
    assert current["administrator"] and not current["canEdit"]
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.company_member SET is_active=false WHERE workspace_id=:w AND user_id=:u"
            ),
            {"w": co["companyId"], "u": user},
        )
    _, report = collect(engine, **args)
    assert report["administrator"]["platformAdministrator"]
    assert not report["administrator"]["identityConnected"]
    assert not report["administrator"]["menuRoleEligible"]
    assert api(admin, co, "operations", method="GET").status_code == 403
    assert "admin" not in json.dumps(report["counts"])
    assert not report["ready"]


@pytest.mark.parametrize(
    "change",
    [
        "missing-admin",
        "unbound",
        "suspended",
        "disabled",
        "old-policy",
        "module-disabled",
        "other-company",
    ],
)
def test_current_scope_and_account_state_are_not_inferred_from_admin_name(
    company_env, monkeypatch, change
):
    engine, co, _, _, user = configured(company_env, monkeypatch)
    args = {"company_id": co["companyId"], "code_revision": "abcdef012345"}
    with engine.begin() as c:
        if change == "missing-admin":
            args["admin_login"] = "missing-admin"
        elif change == "unbound":
            c.execute(
                text(
                    "UPDATE gw.person_identity_binding SET state='CANCELLED',activated_at=NULL,closed_at=clock_timestamp() WHERE workspace_id=:w AND user_id=:u"
                ),
                {"w": co["companyId"], "u": user},
            )
        elif change == "suspended":
            c.execute(
                text(
                    "UPDATE gw.person_identity_binding SET state='SUSPENDED',closed_at=clock_timestamp() WHERE workspace_id=:w AND user_id=:u"
                ),
                {"w": co["companyId"], "u": user},
            )
        elif change == "disabled":
            c.execute(
                text(
                    "UPDATE core.app_user SET status='disabled',disabled_at=clock_timestamp() WHERE id=:u"
                ),
                {"u": user},
            )
        elif change == "old-policy":
            c.execute(
                text(
                    "UPDATE gw.operating_policy_revision SET policy_digest=:d WHERE workspace_id=:w"
                ),
                {"w": co["companyId"], "d": "f" * 64},
            )
        elif change == "module-disabled":
            c.execute(
                text(
                    "UPDATE core.workspace_module SET enabled=false WHERE workspace_id=:w AND module_key='gw'"
                ),
                {"w": co["companyId"]},
            )
        else:
            args["company_id"] += 10000
    if change in {"old-policy", "module-disabled", "other-company"}:
        with pytest.raises(BackupError):
            collect(engine, **args)
    else:
        _, report = collect(engine, **args)
        assert not report["administrator"]["menuRoleEligible"]
        assert not report["administrator"]["securityAdministrator"]
        assert report["result"] == "BLOCKED" and report["ready"] is False


def test_postgresql_enforces_read_only_and_a_new_snapshot_tracks_policy(
    company_env, monkeypatch
):
    engine, co, admin, _, _ = configured(company_env, monkeypatch)
    args = {"company_id": co["companyId"], "code_revision": "abcdef012345"}
    first, _ = collect(engine, **args)
    with engine.connect() as c, c.begin(), pytest.raises(BackupError):
        snapshot(c, admin_login="admin", **args)

    def injected_write(conn, cursor, statement, parameters, ctx, executemany):
        if statement == "SELECT transaction_timestamp()":
            conn.execute(text("UPDATE gw.operating_settings SET version=version+1"))

    event.listen(engine, "before_cursor_execute", injected_write)
    try:
        with pytest.raises(DBAPIError):
            collect(engine, **args)
    finally:
        event.remove(engine, "before_cursor_execute", injected_write)
    with engine.connect() as c:
        assert (
            c.scalar(
                text("SELECT version FROM gw.operating_settings WHERE workspace_id=:w"),
                {"w": co["companyId"]},
            )
            == 1
        )
    body = {
        "expectedVersion": 1,
        "policy": first["policy"] | {"reason": "합성 새 인수 기준", "rpoMinutes": 90},
    }
    assert api(admin, co, "operating-policies", body).status_code == 200
    second, report = collect(engine, **args)
    assert second["policy"]["rpoMinutes"] == 90
    assert report["contextDigest"] != hashlib.sha256(canonical(first)).hexdigest()
    assert not report["ready"]


def test_actual_cli_exports_private_current_context_and_never_prints_account_data(
    company_env, monkeypatch, tmp_path
):
    import os
    import subprocess
    import sys
    from pathlib import Path

    from fs.gw.operating_contract import OperatingPolicy

    _engine, co, _, _, _ = configured(company_env, monkeypatch)
    tmp_path.chmod(0o700)
    env = os.environ.copy()
    env["FS_GW_PREFLIGHT_DATABASE_URL"] = env["TEST_DATABASE_URL"]
    env["FS_CODE_REVISION"] = "abcdef012345"
    command = [
        sys.executable,
        str(Path(__file__).parents[2] / "tools/gw_acceptance_preflight.py"),
        "--company-id",
        str(co["companyId"]),
        "--context-output",
        str(tmp_path / "context.json"),
        "--report",
        str(tmp_path / "report.json"),
    ]
    result = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 2, result.stdout
    summary = json.loads(result.stdout)
    assert set(summary) == {"result", "ready", "blockedCount"} and not summary["ready"]
    current = json.loads((tmp_path / "context.json").read_bytes())
    report = json.loads((tmp_path / "report.json").read_bytes())
    assert set(current) == {
        "workspaceId",
        "generationId",
        "policy",
        "codeRevision",
        "dbRevision",
    }
    assert (
        OperatingPolicy.model_validate(current["policy"]).digest()
        == report["policyDigest"]
    )
    assert (
        report["administrator"]["securityAdministrator"]
        and report["administrator"]["platformAdministrator"]
    )
    assert report["counts"]["connectedPeople"] == 2 and report["companyIsExample"]
    assert not report["ready"] and not report["liveCompanyAcceptance"]
    assert (tmp_path / "context.json").stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "report.json").stat().st_mode & 0o777 == 0o600
    data = (tmp_path / "report.json").read_text()
    assert (
        '"admin"' not in data
        and "hugh-" not in data
        and "password" not in data
        and "login_id" not in data
    )
    original = (tmp_path / "context.json").read_bytes()
    assert (
        subprocess.run(
            command, env=env, capture_output=True, timeout=30, check=False
        ).returncode
        == 1
    )
    assert (tmp_path / "context.json").read_bytes() == original


def test_ten_synthetic_database_assignments_are_only_partial_not_workflow_acceptance(
    company_env, monkeypatch
):
    engine, co, _, _, admin_user = configured(company_env, monkeypatch)
    with engine.begin() as c:
        g = c.scalar(
            text("SELECT active_generation_id FROM core.workspace WHERE id=:w"),
            {"w": co["companyId"]},
        )
        department = c.scalar(
            text(
                "SELECT id FROM gw.organization_unit WHERE workspace_id=:w AND generation_id=:g AND is_active"
            ),
            {"w": co["companyId"], "g": g},
        )
        c.execute(
            text("UPDATE core.company SET is_example=false WHERE workspace_id=:w"),
            {"w": co["companyId"]},
        )
        for i in range(8):
            u = c.scalar(
                text(
                    "INSERT INTO core.app_user(login_id,password_hash,display_name,status) VALUES (:login,'synthetic-unusable-hash','합성 배정 검사','active') RETURNING id"
                ),
                {"login": f"synthetic-preflight-{i}"},
            )
            c.execute(
                text(
                    "INSERT INTO core.company_member(workspace_id,user_id,role) VALUES (:w,:u,'MEMBER')"
                ),
                {"w": co["companyId"], "u": u},
            )
            p = c.scalar(
                text(
                    "INSERT INTO gw.person(workspace_id,generation_id,code,name,job_role,organization_unit_id) VALUES (:w,:g,:code,'합성 배정 검사','STAFF',:o) RETURNING id"
                ),
                {"w": co["companyId"], "g": g, "code": f"SYN-PF-{i}", "o": department},
            )
            c.execute(
                text(
                    "INSERT INTO gw.person_identity_binding(workspace_id,generation_id,person_id,user_id,state,requested_by_user_id,activated_at,reason) VALUES (:w,:g,:p,:u,'ACTIVE',:a,clock_timestamp(),'합성 사전조건 주입')"
                ),
                {"w": co["companyId"], "g": g, "p": p, "u": u, "a": admin_user},
            )
        # Deliberately unusable synthetic factor rows prove only DB registration,
        # never OTP possession, valid decryption, sessions, devices or real business.
        c.execute(
            text(
                "INSERT INTO core.mfa_factor(user_id,kind,state,secret_ciphertext,encryption_key_id,confirmed_at,created_at) SELECT user_id,'TOTP','ACTIVE','synthetic-unusable-ciphertext','synthetic',clock_timestamp(),clock_timestamp() FROM core.company_member WHERE workspace_id=:w"
            ),
            {"w": co["companyId"]},
        )
    _ctx, report = collect(
        engine, company_id=co["companyId"], code_revision="abcdef012345"
    )
    assert report["counts"]["connectedPeople"] == report["counts"]["mfaPeople"] == 10
    assert (
        report["counts"]["securityAdministrators"] == 1
        and report["counts"]["nonSecurityAdminPeople"] == 9
    )
    assert report["counts"]["unassignedDepartmentPeople"] == 0
    assert report["result"] == "PARTIAL" and all(
        r["state"] == "CONFIRMED" for r in report["checks"]
    )
    assert (
        report["ready"]
        is report["liveCompanyAcceptance"]
        is report["releaseAuthorized"]
        is False
    )
    assert report["administrator"]["businessSession"] == "NOT_CHECKED"
    assert (
        report["representativeBusinessChecks"] == report["deviceChecks"] == "UNVERIFIED"
    )
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE gw.person SET organization_unit_id=NULL WHERE workspace_id=:w AND code=:code"
            ),
            {"w": co["companyId"], "code": "SYN-PF-0"},
        )
    _, unassigned = collect(
        engine, company_id=co["companyId"], code_revision="abcdef012345"
    )
    assert (
        unassigned["result"] == "BLOCKED"
        and unassigned["counts"]["unassignedDepartmentPeople"] == 1
    )
