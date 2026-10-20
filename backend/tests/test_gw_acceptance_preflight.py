"""A current snapshot is a precondition, never final business acceptance."""

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fs.core.backup import BackupError
from fs.gw.acceptance_preflight import assess, collect


def facts():
    return (
        {"expectedPeople": 10, "expectedDepartments": 1},
        {
            "activeMembers": 10,
            "activePeople": 10,
            "connectedPeople": 10,
            "mfaPeople": 10,
            "activeDepartments": 1,
            "unassignedDepartmentPeople": 0,
            "securityAdministrators": 1,
            "nonSecurityAdminPeople": 9,
            "responsibleConnected": True,
        },
        {"securityAdministrator": True, "mfaEnrolled": True},
    )


def test_all_measured_preconditions_still_do_not_establish_live_acceptance():
    p, c, a = facts()
    report = assess(p, c, a, company_is_example=False)
    assert report["result"] == "PARTIAL"
    assert all(row["state"] == "CONFIRMED" for row in report["checks"])
    assert (
        report["ready"]
        is report["liveCompanyAcceptance"]
        is report["releaseAuthorized"]
        is False
    )
    assert len(report["remainingConditions"]) == 4
    assert (
        report["representativeBusinessChecks"] == report["deviceChecks"] == "UNVERIFIED"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("activeMembers", 9),
        ("activePeople", 11),
        ("connectedPeople", 9),
        ("mfaPeople", 9),
        ("activeDepartments", 2),
        ("unassignedDepartmentPeople", 1),
        ("securityAdministrators", 2),
        ("nonSecurityAdminPeople", 8),
        ("responsibleConnected", False),
    ],
)
def test_missing_or_excess_people_and_roles_remain_blocked(field, value):
    p, c, a = facts()
    c[field] = value
    assert assess(p, c, a, company_is_example=False)["result"] == "BLOCKED"


@pytest.mark.parametrize(
    "change", ["example", "plan", "department-plan", "admin-role", "admin-mfa"]
)
def test_example_plan_and_administrator_assignment_are_independent(change):
    p, c, a = facts()
    if change == "plan":
        p["expectedPeople"] = 2
    elif change == "department-plan":
        p["expectedDepartments"] = 2
    elif change == "admin-role":
        a["securityAdministrator"] = False
    elif change == "admin-mfa":
        a["mfaEnrolled"] = False
    assert (
        assess(p, c, a, company_is_example=change == "example")["result"] == "BLOCKED"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"company_id": True},
        {"company_id": 0},
        {"company_id": 9223372036854775808},
        {"code_revision": "untrusted"},
        {"admin_login": ""},
        {"admin_login": "x\nadmin"},
    ],
)
def test_invalid_arguments_rejected_before_connection(change):
    class NeverConnect:
        def connect(self):
            raise AssertionError("must not connect")

    args = {"company_id": 1, "code_revision": "a" * 7, "admin_login": "admin"} | change
    with pytest.raises(BackupError):
        collect(NeverConnect(), **args)


def runner():
    spec = importlib.util.spec_from_file_location(
        "preflight_runner",
        Path(__file__).parents[2] / "tools/gw_acceptance_preflight.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_private_output_pair_preserves_existing_files_and_removes_only_created_half(
    tmp_path, monkeypatch
):
    cli = runner()
    tmp_path.chmod(0o700)
    context = tmp_path / "context"
    report = tmp_path / "report"
    cli.write_outputs(
        {"policy": "synthetic"},
        {"ready": False},
        context_output=context,
        report_output=report,
    )
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in (context, report))
    original = context.read_bytes()
    with pytest.raises(BackupError):
        cli.write_outputs({}, {}, context_output=context, report_output=report)
    assert context.read_bytes() == original
    with pytest.raises(BackupError):
        cli.write_outputs({}, {}, context_output=tmp_path / "new", report_output=report)
    assert not (tmp_path / "new").exists()
    context.unlink()
    report.unlink()
    create = cli.create_private

    def race(path):
        if path == report:
            report.write_bytes(b"concurrent output")
            raise FileExistsError()
        return create(path)

    monkeypatch.setattr(cli, "create_private", race)
    with pytest.raises(FileExistsError):
        cli.write_outputs({}, {}, context_output=context, report_output=report)
    assert not context.exists() and report.read_bytes() == b"concurrent output"


def test_cli_defaults_to_admin_without_changing_authority_and_masks_connection(
    tmp_path, monkeypatch, capsys
):
    cli = runner()
    tmp_path.chmod(0o700)
    from test_gw_operating_contract import policy

    context = {
        "workspaceId": 10,
        "generationId": 20,
        "policy": policy().model_dump(by_alias=True),
        "codeRevision": "abcdef0",
        "dbRevision": "test_head",
    }
    p, c, a = facts()
    a["securityAdministrator"] = False
    report = assess(p, c, a, company_is_example=True)
    seen = {}

    class Engine:
        def dispose(self):
            seen["disposed"] = True

    monkeypatch.setenv(
        "FS_GW_PREFLIGHT_DATABASE_URL",
        "postgresql+psycopg://synthetic:never-output@127.0.0.1/synthetic_test",
    )
    monkeypatch.setenv("FS_CODE_REVISION", "abcdef0")
    monkeypatch.setattr(cli, "create_engine", lambda *args, **kwargs: Engine())

    def snapshot(engine, **args):
        seen.update(args)
        return deepcopy(context), deepcopy(report)

    monkeypatch.setattr(cli, "collect", snapshot)
    monkeypatch.setattr(
        "sys.argv",
        [
            "preflight",
            "--company-id",
            "10",
            "--context-output",
            str(tmp_path / "context"),
            "--report",
            str(tmp_path / "report"),
        ],
    )
    assert cli.main() == 2
    assert seen["admin_login"] == "admin" and seen["disposed"]
    assert json.loads((tmp_path / "context").read_bytes()) == context
    assert (
        json.loads((tmp_path / "report").read_bytes())["administrator"][
            "securityAdministrator"
        ]
        is False
    )
    output = capsys.readouterr().out
    assert "never-output" not in output and "postgresql" not in output
    # Arbitrary database errors must not echo URLs, usernames or driver messages.
    from sqlalchemy.exc import OperationalError

    def fail(*args, **kwargs):
        raise OperationalError("private SQL", {}, Exception("never-output"))

    monkeypatch.setattr(cli, "collect", fail)
    assert cli.main() == 1
    assert "never-output" not in capsys.readouterr().out
