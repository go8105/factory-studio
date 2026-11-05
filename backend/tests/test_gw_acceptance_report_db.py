"""Owned PostgreSQL only: real read-only report, CLI, latest evidence and no writes."""

# ruff: noqa: F401,F811
import hashlib
import json
from uuid import uuid4

import pytest
from fs.gw.acceptance_preflight import read_transaction
from fs.gw.acceptance_report import collect
from fs.gw.evidence_trust import from_environment
from fs.gw.operating_contract import canonical
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_gw_acceptance_preflight import runner
from test_gw_company_work import api
from test_gw_evidence import prepare
from test_hr_work import company_env


def state(engine):
    # Deliberately include account/session/MFA and evidence state; report cannot write.
    with engine.connect() as c:
        return c.scalar(
            text("""SELECT encode(sha256(convert_to(jsonb_build_array(
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM core.app_user t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM core.auth_session t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM core.mfa_factor t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.operating_settings t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.operating_evidence t)
            )::text,'UTF8')),'hex')""")
        )


def test_report_actual_read_only_snapshot_and_unchanged_company(
    company_env, monkeypatch
):
    engine, co, admin, _ = company_env
    body, signed = prepare(company_env, monkeypatch)
    assert api(admin, co, "operating-evidence", signed(body)).status_code == 200
    before = state(engine)
    current, report = collect(
        engine,
        company_id=co["companyId"],
        code_revision=body["codeRevision"],
        public_keys=from_environment(),
    )
    assert report["contextDigest"] == hashlib.sha256(canonical(current)).hexdigest()
    assert (
        report["preflight"]["administrator"]["accountExists"] is False
    )  # No admin rename/creation.
    assert report["preflight"]["companyIsExample"] is True
    assert report["preflight"]["counts"]["connectedPeople"] == 2
    assert report["evidenceChecks"][0]["state"] == "RECORDED_PASS"
    assert report["result"] == "BLOCKED" and not report["ready"]
    assert report["launchGate"]["unverifiedCount"] == 4
    assert report["observedAt"] == report["preflight"]["observedAt"]
    assert not report["revocationCoverage"]["revocationsComplete"]
    review = report["revocationCoverage"]
    assert review["version"] == 2 and len(review["checks"]) == 12
    assert review["referenceCatalog"]["fixedSyntheticCaseCount"] == 28
    assert (
        not review["currentCompanyVerified"]
        and not review["syntheticExecutionImported"]
    )
    cases = [case for row in review["checks"] for case in row["syntheticCases"]]
    assert len(cases) == 28 and all(
        case["executionState"] == "NOT_EXECUTED" and not case["currentCompanyVerified"]
        for case in cases
    )

    assert state(engine) == before
    with pytest.raises(DBAPIError) as error, read_transaction(engine) as c:
        assert c.scalar(text("SHOW transaction_read_only")) == "on"
        c.execute(text("UPDATE gw.operating_settings SET version=version+1"))
    assert error.value.orig.sqlstate == "25006"
    assert state(engine) == before


def test_cli_actual_latest_failure_and_missing_original_remain_blocked(
    company_env, monkeypatch, tmp_path, capsys
):
    engine, co, admin, _ = company_env
    body, signed = prepare(company_env, monkeypatch)
    assert api(admin, co, "operating-evidence", signed(body)).status_code == 200
    failure = body | {"runId": str(uuid4()), "result": "FAIL"}
    assert api(admin, co, "operating-evidence", signed(failure)).status_code == 200
    cli = runner()
    tmp_path.chmod(0o700)
    monkeypatch.setenv(
        "FS_GW_PREFLIGHT_DATABASE_URL", engine.url.render_as_string(hide_password=False)
    )
    for phase, expected in [
        ("failure", "FAILED"),
        ("lost-original", "LEGACY_UNVERIFIED"),
    ]:
        if phase == "lost-original":
            # Synthetic corruption injection; never a product mutation or a real company.
            with engine.begin() as c:
                c.execute(
                    text(
                        "UPDATE gw.operating_evidence SET metrics=metrics-'_signedEnvelope' WHERE run_id=:run"
                    ),
                    {"run": failure["runId"]},
                )
        before = state(engine)
        monkeypatch.setattr(
            "sys.argv",
            [
                "preflight",
                "--company-id",
                str(co["companyId"]),
                "--execution-report",
                "--context-output",
                str(tmp_path / f"{phase}-context"),
                "--report",
                str(tmp_path / f"{phase}-report"),
            ],
        )
        assert cli.main() == 2
        report = json.loads((tmp_path / f"{phase}-report").read_bytes())
        assert report["evidenceChecks"][0]["state"] == expected
        assert report["result"] == "BLOCKED" and not report["ready"]
        assert all(c["state"] == "UNVERIFIED" for c in report["checks"][-4:])
        assert state(engine) == before
        assert "signature" not in capsys.readouterr().out
        assert (tmp_path / f"{phase}-report").stat().st_mode & 0o777 == 0o600


def test_report_rechecks_connected_partial_acceptance_in_same_snapshot(
    company_env, monkeypatch
):
    from datetime import timedelta

    from fs.gw.acceptance_reconciliation import reconcile
    from fs.gw.operating_contract import OperatingPolicy, timestamp

    engine, co, admin, _ = company_env
    backup, signed = prepare(company_env, monkeypatch)
    assert api(admin, co, "operating-evidence", signed(backup)).status_code == 200
    restore = backup | {
        "runId": str(uuid4()),
        "kind": "RESTORE",
        "result": "PARTIAL",
        "startedAt": backup["finishedAt"],
        "finishedAt": (
            timestamp(backup["finishedAt"]) + timedelta(seconds=1)
        ).isoformat(),
        "metrics": {
            "failedCheckCount": 1,
            "revocationsReapplied": False,
            "twoAccountChecks": False,
        },
    }
    assert api(admin, co, "operating-evidence", signed(restore)).status_code == 200
    current, report = collect(
        engine,
        company_id=co["companyId"],
        code_revision=backup["codeRevision"],
        public_keys=from_environment(),
    )
    context = {
        "workspace_id": current["workspaceId"],
        "generation_id": current["generationId"],
        "policy": OperatingPolicy.model_validate(current["policy"]),
        "code_revision": current["codeRevision"],
        "db_revision": current["dbRevision"],
        "public_keys": from_environment(),
        "now": timestamp(report["observedAt"]),
    }
    diagnostics = reconcile(
        {"BACKUP": signed(backup), "RESTORE": signed(restore)}, **context
    ).model_dump(by_alias=True)
    acceptance = backup | {
        "runId": str(uuid4()),
        "kind": "ACCEPTANCE",
        "result": "PARTIAL",
        "startedAt": report["observedAt"],
        "finishedAt": report["observedAt"],
        "manifestDigest": hashlib.sha256(canonical(diagnostics)).hexdigest(),
        "metrics": {"acceptanceDiagnostics": diagnostics},
    }
    assert api(admin, co, "operating-evidence", signed(acceptance)).status_code == 200
    before = state(engine)
    _, connected = collect(
        engine,
        company_id=co["companyId"],
        code_revision=backup["codeRevision"],
        public_keys=from_environment(),
    )
    check = next(c for c in connected["evidenceChecks"] if c["kind"] == "ACCEPTANCE")
    assert check["state"] == "PARTIAL" and check["signatureVerified"]
    assert connected["result"] == "BLOCKED" and not connected["ready"]
    assert state(engine) == before
    assert not connected["backupRestoreCollection"]["backupRestorePairVerified"]
