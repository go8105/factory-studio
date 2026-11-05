"""One snapshot execution and current originals, without importing unsigned PASS claims."""

import ast
import base64
import hashlib
import json
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

import pytest
from fs.common.errors import ApiError
from fs.gw import acceptance_report
from fs.gw.acceptance_preflight import assess
from fs.gw.denial_catalog import FAMILIES
from fs.gw.operating_contract import canonical, verify_evidence
from fs.gw.readiness import SOURCE_FIELD
from test_gw_acceptance_collection import registered_fixture
from test_gw_acceptance_preflight import facts, runner


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
    review = report["revocationCoverage"]
    assert len(report["checks"]) == len(review["checks"]) == 12
    assert {check["code"] for check in report["checks"]}.isdisjoint(
        {check["code"] for check in review["checks"]}
    )
    assert all(check["executionState"] == "NOT_EXECUTED" for check in review["checks"])

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
    assert len(review["checks"]) == len({c["code"] for c in review["checks"]}) == 12
    assert review["version"] == 2 and review["result"] == "UNVERIFIED"
    assert not review["revocationsComplete"] and not review["currentCompanyVerified"]
    root = Path(__file__).resolve().parents[2]
    for check in review["checks"]:
        assert (
            check["executionState"] == "NOT_EXECUTED"
            and not check["currentCompanyVerified"]
        )
        assert check["testReference"] == check["testReferences"][0]
        for reference in check["testReferences"]:
            filename, function = reference.split("::")
            tree = ast.parse((root / filename).read_text())
            assert function.split("[", 1)[0] in {
                n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
            }


def test_review_has_every_fixed_case_once_and_separates_legacy_references():
    from collections import Counter

    from fs.gw.denial_catalog import CATALOG_VERSION, DENIAL_PROBES
    from fs.gw.restored_denial import ALL_CASES
    from test_gw_route_verify import runner as route_runner

    review = acceptance_report.denial_review()
    cases = [item for row in review["checks"] for item in row["syntheticCases"]]
    assert Counter(item["case"] for item in cases) == Counter(ALL_CASES.keys())
    assert len(cases) == 28 and {item["probe"] for item in cases} == set(DENIAL_PROBES)
    assert dict(route_runner().DENIAL_PROBES) == dict(DENIAL_PROBES)
    assert review["referenceCatalog"] == {
        "version": CATALOG_VERSION,
        "fixedSyntheticCaseCount": 28,
        "observationFamilyCount": 9,
        "observationVersions": list(range(1, 10)),
        "executionProfile": "RESTORED_DENIAL_ONLY",
        "executionScope": "NEW_OWNED_SYNTHETIC_DATABASE",
    }
    rows = {row["code"]: row for row in review["checks"]}
    assert (
        rows["OLD_SESSIONS"]["syntheticCases"]
        == rows["PENDING_AUTHENTICATION"]["syntheticCases"]
        == []
    )
    assert {c["case"] for c in rows["COMPANY_MEMBERSHIP"]["syntheticCases"]} == {
        "COMPANY_MEMBERSHIP",
        "FOREIGN_SCOPE",
    }
    assert {c["case"] for c in rows["DOCUMENT_ACL"]["syntheticCases"]} == {
        "DOCUMENT_READER"
    }
    assert len(rows["DELEGATION"]["syntheticCases"]) == 15
    for case in cases:
        assert case["testReference"] == "::".join(DENIAL_PROBES[case["probe"]])
        assert (
            case["executionState"] == "NOT_EXECUTED"
            and not case["currentCompanyVerified"]
        )


def test_review_does_not_read_or_run_or_import_claims_and_returns_fresh_flags(
    monkeypatch,
):
    import subprocess

    def forbidden(*args, **kwargs):
        pytest.fail("review metadata must not execute or import results")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(acceptance_report, "read_transaction", forbidden)
    monkeypatch.setenv("FS_GW_SYNTHETIC_RESULT", "PASS")
    monkeypatch.setenv("FS_GW_SYNTHETIC_REPORT", "work/old-pass.json")
    first = acceptance_report.denial_review()
    first["result"] = "PASS"
    first["checks"][2]["syntheticCases"][0]["executionState"] = "PASSED"
    first["checks"][2]["syntheticCases"][0]["currentCompanyVerified"] = True
    fresh = acceptance_report.denial_review()
    assert fresh["result"] == "UNVERIFIED" and fresh["executionState"] == "NOT_EXECUTED"
    assert not fresh["syntheticExecutionImported"] and not fresh["coverageComplete"]
    assert not fresh["revocationsComplete"] and not fresh["currentCompanyVerified"]
    for row in fresh["checks"]:
        for case in row["syntheticCases"]:
            assert (
                case["executionState"] == "NOT_EXECUTED"
                and not case["currentCompanyVerified"]
            )


@pytest.mark.parametrize("family", FAMILIES)
def test_catalog_family_matches_its_strict_observation_case_literals(family):
    from typing import get_args

    from fs.gw.denial_catalog import review_cases

    assert set(family.cases) == set(
        get_args(family.observation.model_fields["case"].annotation)
    )
    cases = review_cases(family.cases)
    assert {case["case"] for case in cases} == set(family.cases)
    assert all(
        case["observationVersion"] == family.observation_version
        and case["observationScope"] == family.observation_scope
        for case in cases
    )


def test_unknown_catalog_reference_is_not_silently_replaced_by_legacy_test():
    from fs.gw.denial_catalog import review_cases

    with pytest.raises(ValueError):
        review_cases(["CORE_ACCOUNT", "UNKNOWN_CASE"])


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
