"""One snapshot execution and current originals, without importing unsigned PASS claims."""

import ast
import base64
import hashlib
import json
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

import pytest
from test_gw_acceptance_collection import registered_fixture
from test_gw_acceptance_preflight import facts, runner

from fs.common.errors import ApiError
from fs.gw import acceptance_report
from fs.gw.acceptance_preflight import assess
from fs.gw.operating_contract import canonical, verify_evidence
from fs.gw.readiness import SOURCE_FIELD


def setup(monkeypatch):
    key, rows, ctx = registered_fixture()
    current = {
        "workspaceId": ctx["workspace_id"],
        "generationId": ctx["generation_id"],
        "policy": ctx["policy"].model_dump(by_alias=True),
        "codeRevision": ctx["code_revision"],
        "dbRevision": ctx["db_revision"],
    }
    p, counts, admin = facts()
    report = assess(p, counts, admin, company_is_example=False)
    report.update(
        observedAt=ctx["now"].isoformat(),
        workspaceId=str(ctx["workspace_id"]),
        generationId=str(ctx["generation_id"]),
        policyDigest=ctx["policy"].digest(),
        codeRevision=ctx["code_revision"],
        dbRevision=ctx["db_revision"],
        contextDigest=hashlib.sha256(canonical(current)).hexdigest(),
        codeRevisionSource="OPERATOR_ENVIRONMENT",
        executionRevisionVerified=False,
    )
    seen = []

    class Connection:
        def execute(self, query, params):
            seen.append(str(query))
            assert params == {"w": 10, "g": 20}
            return self

        def scalar_one(self):
            return 1

        def mappings(self):
            return self

        def all(self):
            return rows

    connection = Connection()

    @contextmanager
    def transaction(engine):
        seen.append("read-only snapshot")
        yield connection

    def snapshot(c, **kwargs):
        assert c is connection and kwargs["admin_login"] == "admin"
        seen.append("preflight")
        return current, report

    monkeypatch.setattr(acceptance_report, "read_transaction", transaction)
    monkeypatch.setattr(acceptance_report, "snapshot", snapshot)
    return key, rows, ctx, current, report, seen


def collect(ctx):
    return acceptance_report.collect(
        object(),
        company_id=10,
        code_revision=ctx["code_revision"],
        public_keys=ctx["public_keys"],
        admin_login=" ADMIN ",
    )


def test_same_snapshot_combines_existing_preflight_and_original_verification(
    monkeypatch,
):
    _, _, ctx, current, preflight, seen = setup(monkeypatch)
    exported, report = collect(ctx)
    assert exported == current and report["preflight"] == preflight
    assert report["kind"] == "GW_ACCEPTANCE_EXECUTION_REPORT"
    assert report["contextDigest"] == hashlib.sha256(canonical(exported)).hexdigest()
    assert (
        report["result"] == "BLOCKED"
    )  # Missing latest ACCEPTANCE; never pair => PASS.
    assert report["backupRestoreCollection"]["result"] == "PARTIAL"
    assert seen[:2] == ["read-only snapshot", "preflight"] and len(seen) == 4
    assert "recorded_at DESC,id DESC" in seen[3]
    assert report["launchGate"]["unverifiedCount"] == 4
    assert not any(
        report[k]
        for k in (
            "ready",
            "signedEvidence",
            "liveCompanyAcceptance",
            "releaseAuthorized",
            "executionRevisionVerified",
        )
    )
    text = json.dumps(report)
    assert "_signedEnvelope" not in text and '"signature"' not in text
    assert report["revocationCoverage"]["executionState"] == "NOT_EXECUTED"
    with pytest.raises(ApiError):
        verify_evidence(report, "arbitrary", **ctx)


@pytest.mark.parametrize(
    "change,expected",
    [
        ("failure", "FAILED"),
        ("partial", "PARTIAL"),
        ("missing-original", "LEGACY_UNVERIFIED"),
        ("tamper", "INVALID"),
        ("policy", "STALE"),
        ("version", "STALE"),
        ("revoked", "INVALID"),
    ],
)
def test_report_keeps_latest_failure_and_rechecks_current_originals(
    monkeypatch, change, expected
):
    key, rows, ctx, _, _, _ = setup(monkeypatch)
    newer = deepcopy(rows[1])
    newer["id"] += 100
    if change in {"failure", "partial"}:
        original = newer["metrics"][SOURCE_FIELD]
        original["result"] = newer["result"] = (
            "FAIL" if change == "failure" else "PARTIAL"
        )
        newer["signature"] = base64.b64encode(key.sign(canonical(original))).decode()
    elif change == "missing-original":
        newer["metrics"] = {}
    elif change == "tamper":
        newer["manifest_digest"] = "f" * 64
    elif change == "policy":
        newer["policy_revision_id"] += 1
    elif change == "version":
        newer["db_revision"] = "old_head"
    else:
        ctx["public_keys"] = {}
    rows.append(newer)
    _, report = collect(ctx)
    assert report["result"] == "BLOCKED"
    assert (
        next(c for c in report["evidenceChecks"] if c["kind"] == "RESTORE")["state"]
        == expected
    )
    assert not report["backupRestoreCollection"]["backupRestorePairVerified"]


def test_strict_ten_person_preflight_cannot_be_replaced_by_looser_gate(monkeypatch):
    _, _, ctx, _, preflight, _ = setup(monkeypatch)
    from test_gw_launch_gate import inputs

    # Deliberately satisfy the looser gate in isolation so the exact preflight
    # remains an independent blocker, rather than relying on missing evidence.
    local_gate = acceptance_report.build(**inputs())
    monkeypatch.setattr(acceptance_report, "build", lambda **kwargs: local_gate)
    preflight["result"] = "BLOCKED"
    preflight["checks"][2]["state"] = "BLOCKED"
    preflight["counts"]["connectedPeople"] = 11
    _, report = collect(ctx)
    people = next(c for c in report["checks"] if c["code"] == "PEOPLE")
    assert people["state"] == "CONFIRMED" and report["result"] == "BLOCKED"
    assert report["preflight"]["result"] == "BLOCKED"
    assert report["launchGate"]["blockedCount"] == 0
    preflight["result"] = "PARTIAL"
    preflight["checks"][2]["state"] = "CONFIRMED"
    _, partial = collect(ctx)
    assert partial["result"] == "PARTIAL" and not partial["ready"]
    assert partial["launchGate"]["unverifiedCount"] == 4


def test_denial_map_points_only_to_real_existing_tests_and_claims_no_execution():
    review = acceptance_report.denial_review()
    assert len(review["checks"]) == len({c["code"] for c in review["checks"]}) == 8
    assert review["result"] == "UNVERIFIED" and not review["revocationsComplete"]
    for check in review["checks"]:
        assert check["executionState"] == "NOT_EXECUTED"
        if check["testReference"]:
            filename, function = check["testReference"].split("::")
            tree = ast.parse((Path(__file__).parent / filename).read_text())
            assert function in {
                n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
            }
        else:
            assert check["existingScope"] == "UNCONNECTED"


def test_execution_cli_uses_opt_in_collector_and_never_leaks_errors(
    tmp_path, monkeypatch, capsys
):
    _, _, ctx, current, _, _ = setup(monkeypatch)
    _, report = collect(ctx)
    tmp_path.chmod(0o700)
    cli = runner()

    class Engine:
        disposed = False

        def dispose(self):
            self.disposed = True

    engine = Engine()
    monkeypatch.setattr(cli, "create_engine", lambda *a, **k: engine)
    monkeypatch.setattr(cli, "from_environment", lambda: ctx["public_keys"])
    monkeypatch.setattr(cli, "collect_execution", lambda *a, **k: (current, report))
    monkeypatch.setattr(cli, "collect", lambda *a, **k: pytest.fail("legacy collector"))
    monkeypatch.setenv(
        "FS_GW_PREFLIGHT_DATABASE_URL",
        "postgresql+psycopg://synthetic:private-secret@localhost/owned_test",
    )
    monkeypatch.setenv("FS_CODE_REVISION", ctx["code_revision"])
    monkeypatch.setattr(
        "sys.argv",
        [
            "preflight",
            "--company-id",
            "10",
            "--execution-report",
            "--context-output",
            str(tmp_path / "context"),
            "--report",
            str(tmp_path / "report"),
        ],
    )
    assert cli.main() == 2 and engine.disposed
    assert (
        json.loads((tmp_path / "report").read_bytes())["kind"]
        == "GW_ACCEPTANCE_EXECUTION_REPORT"
    )
    assert (tmp_path / "report").stat().st_mode & 0o777 == 0o600
    assert "preflightBlockedCount" in capsys.readouterr().out
    original = (tmp_path / "report").read_bytes()
    assert cli.main() == 1 and (tmp_path / "report").read_bytes() == original

    def fail():
        raise ValueError("private-secret")

    monkeypatch.setattr(cli, "from_environment", fail)
    assert cli.main() == 1
    output = capsys.readouterr().out
    assert "private-secret" not in output and "postgresql" not in output
