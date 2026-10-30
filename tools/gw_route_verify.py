"""Run fixed synthetic GW route probes in a newly owned DB; never production acceptance."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

from fs.core.backup import BackupError, create_private, private_directory
from fs.gw.acceptance_business import PROBE, PROPERTY, SyntheticBusinessObservation
from fs.gw.operating_contract import canonical, timestamp
from fs.gw.restored_denial import (
    ALL_CASES,
    CHAT_CASES,
    OBJECT_CASES,
    POST_CASES,
    parse_observation,
)
from fs.gw.restored_denial import (
    PROPERTY as DENIAL_PROPERTY,
)
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[1]
PROBES = {
    PROBE: (
        "backend/tests/test_gw_business_probe.py",
        "test_ten_person_mfa_preflight_and_representative_business",
    ),
    "BINDING_SUSPEND_ROLLBACK_AND_DENIAL": (
        "backend/tests/test_gw_identity_journal.py",
        "test_company_route_cli_binds_current_policy_and_actual_suspend",
    ),
    "TRANSACTION_DISPOSITION_BOUNDARIES": (
        "backend/tests/test_journal_transaction_proof.py",
        "test_actual_abort_pending_savepoint_and_source_mismatch",
    ),
    "MFA_ENROLLMENT_STORAGE_ROLLBACK": (
        "backend/tests/test_account_security_journal.py",
        "test_storage_failure_rolls_back_pending_factor",
    ),
    "LOGIN_CHALLENGE_STORAGE_ROLLBACK": (
        "backend/tests/test_challenge_security_journal.py",
        "test_record_failure_rolls_back_challenge_change[issued]",
    ),
    "PASSWORD_SESSION_STORAGE_ROLLBACK": (
        "backend/tests/test_challenge_security_journal.py",
        "test_password_session_record_failure_rolls_back_issuance",
    ),
    "HR_PASSWORD_ROLE_DISABLE_AND_RETRY": (
        "backend/tests/test_account_security_journal.py",
        "test_hr_password_role_disable_and_retry",
    ),
    "DOCUMENT_ACL_STORAGE_ROLLBACK_AND_RECORDS": (
        "backend/tests/test_gw_identity_journal.py",
        "test_company_document_actions_and_uncommitted_intent",
    ),
    "RESTORED_SESSION_CHALLENGE_AND_AUTHORITY_DENIAL": (
        "backend/tests/test_backup_journal_restore.py",
        "test_actual_history_bound_restore_restricts_without_changing_source[False]",
    ),
    "BINDING_CANCEL_STORAGE_ROLLBACK_AND_DENIAL": (
        "backend/tests/test_gw_identity_route_probes.py",
        "test_binding_transition_storage_rollback_and_access[cancel]",
    ),
    "BINDING_RESUME_STORAGE_ROLLBACK_AND_ACCESS": (
        "backend/tests/test_gw_identity_route_probes.py",
        "test_binding_transition_storage_rollback_and_access[resume]",
    ),
    "ROLE_GRANT_STORAGE_ROLLBACK_AND_ACCESS": (
        "backend/tests/test_gw_identity_route_probes.py",
        "test_role_transition_storage_rollback_and_access[grant]",
    ),
    "ROLE_REVOKE_STORAGE_ROLLBACK_AND_DENIAL": (
        "backend/tests/test_gw_identity_route_probes.py",
        "test_role_transition_storage_rollback_and_access[revoke]",
    ),
    "OTP_FAILURE_LIMIT_AND_JOURNAL": (
        "backend/tests/test_challenge_security_journal.py",
        "test_failed_attempts_and_lock_are_recorded",
    ),
    "EXPIRED_CHALLENGE_AND_JOURNAL": (
        "backend/tests/test_challenge_security_journal.py",
        "test_expired_request_is_recorded",
    ),
    "OTP_DENIAL_STORAGE_ROLLBACK": (
        "backend/tests/test_challenge_security_journal.py",
        "test_record_failure_rolls_back_challenge_change[denied]",
    ),
    "CHALLENGE_EXPIRY_STORAGE_ROLLBACK": (
        "backend/tests/test_challenge_security_journal.py",
        "test_record_failure_rolls_back_challenge_change[expired]",
    ),
    "EMERGENCY_DENIAL_STORAGE_ROLLBACK": (
        "backend/tests/test_challenge_security_journal.py",
        "test_record_failure_rolls_back_challenge_change[emergency]",
    ),
    "RECOVERY_CODE_RACE_REENROLL_AND_JOURNAL": (
        "backend/tests/test_account_security_journal.py",
        "test_security_workflows_keep_confirmation[recovery-race-reenroll]",
    ),
    "SESSION_REVOCATION_CODE_ROTATION_AND_JOURNAL": (
        "backend/tests/test_account_security_journal.py",
        "test_security_workflows_keep_confirmation[rotate-and-revoke]",
    ),
    "EMERGENCY_KIT_EXPIRY_AND_JOURNAL": (
        "backend/tests/test_challenge_security_journal.py",
        "test_expired_emergency_kit_is_recorded",
    ),
    "EMERGENCY_HTTP_RECOVERY_AND_JOURNAL": (
        "backend/tests/test_account_security_journal.py",
        "test_emergency_http_recovery_with_journal_confirmation",
    ),
    "EMERGENCY_ROLE_EXPIRY_DENIAL_AND_JOURNAL": (
        "backend/tests/test_account_security_journal.py",
        "test_emergency_role_expiry_recheck_with_journal_confirmation",
    ),
    "LOGOUT_DENIAL_AND_JOURNAL": (
        "backend/tests/test_account_security_journal.py",
        "test_normal_logout_with_journal",
    ),
}


DENIAL_PROBES = {
    "RESTORED_FRESH_AUTH_" + case: (
        "backend/tests/test_gw_restored_denial_db.py",
        "test_closed_restore_fresh_authentication_denial[" + case + "]",
    )
    for case in ALL_CASES
}
DENIAL_PROBES.update(
    {
        "RESTORED_FRESH_AUTH_" + case: (
            "backend/tests/test_gw_restored_object_db.py",
            "test_closed_restore_object_authorization[" + case + "]",
        )
        for case in OBJECT_CASES
    }
)

DENIAL_PROBES.update(
    {
        "RESTORED_FRESH_AUTH_" + case: (
            "backend/tests/test_gw_restored_post_db.py",
            "test_closed_restore_post_visibility[" + case + "]",
        )
        for case in POST_CASES
    }
)

DENIAL_PROBES.update(
    {
        "RESTORED_FRESH_AUTH_" + case: (
            "backend/tests/test_gw_restored_chat_db.py",
            "test_closed_restore_chat_membership[" + case + "]",
        )
        for case in CHAT_CASES
    }
)


def source_identity():
    commit = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    )
    files = subprocess.check_output(
        ["git", "ls-files", "-z", "backend", "tools"], cwd=ROOT
    ).split(b"\0")
    # Include this new runner and probes even before their first commit.
    paths = {Path(os.fsdecode(p)) for p in files if p}
    paths.add(Path(__file__).relative_to(ROOT))
    paths.add(Path("backend/src/fs/gw/acceptance_business.py"))
    paths.update(
        Path(path) for path, _name in [*PROBES.values(), *DENIAL_PROBES.values()]
    )
    paths.add(Path("backend/src/fs/gw/restored_denial.py"))
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(os.fsencode(path) + b"\0")
        if (ROOT / path).is_file():
            with (ROOT / path).open("rb") as source:
                while block := source.read(1024 * 1024):
                    digest.update(block)
        digest.update(b"\0")
    return {"commit": commit, "sourceDigest": digest.hexdigest()}


def probe_results(xml_path, probes=None):
    probes = PROBES if probes is None else probes
    root = ElementTree.parse(xml_path).getroot()
    cases = list(root.iter("testcase"))
    results = []
    for code, (path, name) in probes.items():
        matches = [
            case
            for case in cases
            if case.get("name") == name
            and case.get("classname") in {Path(path).stem, "tests." + Path(path).stem}
        ]
        state = "MISSING"
        if len(matches) == 1:
            case = matches[0]
            state = (
                "FAILED"
                if case.find("failure") is not None or case.find("error") is not None
                else "SKIPPED"
                if case.find("skipped") is not None
                else "PASSED"
            )
        elif matches:
            state = "INVALID"
        results.append({"probe": code, "state": state})
    unexpected = len(cases) != len(probes) or any(
        case.get("name") not in {name for _, name in probes.values()} for case in cases
    )
    return results, unexpected


def business_observation(
    xml_path, *, run_id, code_revision, db_revision, started_at, now
):
    """Accept one bounded current-run observation from the exact passed probe only.

    Pytest/runner source is the trust boundary, not a detached JSON document. This
    does not attest deployed code, real devices, or a production company.
    """
    path, name = PROBES[PROBE]
    matches = [
        case
        for case in ElementTree.parse(xml_path).getroot().iter("testcase")
        if case.get("name") == name
        and case.get("classname") in {Path(path).stem, "tests." + Path(path).stem}
    ]
    if len(matches) != 1:
        return "MISSING" if not matches else "INVALID", None
    case = matches[0]
    if any(case.find(tag) is not None for tag in ("failure", "error", "skipped")):
        return "FAILED", None
    properties = list(case.findall("./properties/property"))
    if len(properties) != 1 or properties[0].get("name") != PROPERTY:
        return "INVALID", None
    raw = properties[0].get("value", "")
    if len(raw.encode()) > 4096:
        return "INVALID", None
    try:
        data = SyntheticBusinessObservation.model_validate(json.loads(raw))
        if (
            data.run_id != run_id
            or data.code_revision != code_revision
            or data.db_revision != db_revision
            or timestamp(data.started_at) < timestamp(started_at)
            or timestamp(data.finished_at) > now
        ):
            raise ValueError()
    except (ValidationError, ValueError, TypeError, KeyError):
        return "INVALID", None
    return "SYNTHETIC_SCENARIO_PASSED", data.model_dump(by_alias=True)


def denial_observations(
    xml_path, *, run_id, code_revision, db_revision, started_at, now
):
    """Only exact passed cases from this execution; no detached report ingestion."""
    root = ElementTree.parse(xml_path).getroot()
    results, unexpected = probe_results(xml_path, DENIAL_PROBES)
    if unexpected or any(r["state"] != "PASSED" for r in results):
        return []
    observations = []
    try:
        for case in root.iter("testcase"):
            properties = case.findall("./properties/property")
            if len(properties) != 1 or properties[0].get("name") != DENIAL_PROPERTY:
                return []
            values = [properties[0].get("value")]
            if len(values) != 1:
                return []
            data = parse_observation(values[0])
            path, name = DENIAL_PROBES["RESTORED_FRESH_AUTH_" + data.case]
            if case.get("name") != name or case.get("classname") not in {
                Path(path).stem,
                "tests." + Path(path).stem,
            }:
                return []
            if (
                data.run_id != run_id
                or data.code_revision != code_revision
                or data.db_revision != db_revision
                or timestamp(data.started_at) < timestamp(started_at)
                or timestamp(data.finished_at) > now
            ):
                return []
            observations.append(data.model_dump(by_alias=True))
    except (ValueError, TypeError, KeyError):
        return []
    if len({o["case"] for o in observations}) != len(ALL_CASES):
        return []
    return observations


def validate_restore_container(url, container, owner, *, strict=False):
    if not owner:
        raise BackupError("복원 검사 컨테이너 소유 라벨이 필요합니다.")
    template = '{"id":{{json .Id}},"owner":{{json (index .Config.Labels "factory-studio.owner")}},"ports":{{json .NetworkSettings.Ports}},"running":{{json .State.Running}}}'
    result = subprocess.run(
        ["docker", "inspect", "--format", template, container],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if result.returncode:
        raise BackupError("소유 복원 검사 컨테이너를 확인하세요.")
    info = json.loads(result.stdout)
    bindings = info.get("ports", {}).get("5432/tcp") or []
    if strict and (
        not re.fullmatch(r"[0-9a-f]{64}", container)
        or info.get("id") != container
        or len(bindings) != 1
        or bindings[0].get("HostIp") != url.host
        or bindings[0].get("HostPort") != str(url.port)
    ):
        raise BackupError("고정한 시험 컨테이너ID와 단일loopback 연결이 필요합니다.")
    if (
        info.get("owner") != owner
        or info.get("running") is not True
        or not any(
            binding.get("HostIp") == url.host
            and binding.get("HostPort") == str(url.port)
            for binding in bindings
        )
    ):
        raise BackupError("복원 검사 컨테이너의 소유권·연결 범위가 다릅니다.")


def run(*, admin_url, output, restored_denial_only=False):
    probes = DENIAL_PROBES if restored_denial_only else PROBES
    output = Path(output)
    private_directory(output.parent)
    if output.exists() or output.is_symlink():
        raise BackupError("기존 보고서를 덮어쓰지 않습니다.")
    url = make_url(admin_url)
    if (
        url.drivername != "postgresql+psycopg"
        or url.database != "postgres"
        or url.host not in {"127.0.0.1", "localhost", "::1"}
    ):
        raise BackupError("소유 테스트 PostgreSQL의 postgres 관리 연결을 사용하세요.")
    container = os.environ.get("GW_BACKUP_TEST_CONTAINER")
    if restored_denial_only and not container:
        raise BackupError("복원 권한 거부 검사는 소유 컨테이너가 필요합니다.")
    if container:
        validate_restore_container(
            url,
            container,
            os.environ.get("FS_GW_ROUTE_VERIFY_OWNER"),
            strict=restored_denial_only,
        )
    identity = source_identity()
    run_id = str(uuid4())
    database = "gw_route_verify_" + uuid4().hex + "_test"
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    created = False
    report = {
        "version": 1,
        "kind": "SYNTHETIC_GW_ROUTE_EXECUTION",
        "catalogVersion": "GW_RESTORED_DENIAL_PROBES_V4"
        if restored_denial_only
        else "GW_SYNTHETIC_ROUTE_PROBES_V5",
        "restoredDenialObservations": [],
        "runId": run_id,
        "startedAt": datetime.now(UTC).isoformat(),
        "executionScope": "NEW_OWNED_SYNTHETIC_DATABASE",
        "source": identity,
        "result": "BLOCKED",
        "ready": False,
        "liveCompanyAcceptance": False,
        "revocationsReapplied": False,
        "completenessConfirmed": False,
        "restoredAccessDenial": "UNVERIFIED",
        "databaseCleaned": False,
        "probes": [],
        "businessObservationState": "UNVERIFIED",
        "syntheticBusinessObservation": None,
    }
    try:
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{database}"'))
        created = True
        env = os.environ.copy()
        test_url = url.set(database=database).render_as_string(hide_password=False)
        env.update(
            DATABASE_URL=test_url,
            TEST_DATABASE_URL=test_url,
            FS_GW_SYNTHETIC_RUN_ID=run_id,
            FS_GW_SYNTHETIC_CODE_REVISION=identity["commit"],
        )
        for key in (
            "FS_GW_IDENTITY_JOURNAL_DIR",
            "FS_GW_IDENTITY_JOURNAL_KEY_FILE",
            "FS_GW_IDENTITY_JOURNAL_EXPECTED_HEAD",
            "FS_GW_JOURNAL_TX_PROOF",
        ):
            env.pop(key, None)
        with tempfile.TemporaryDirectory(
            prefix=".gw-route-probes-", dir=output.parent
        ) as folder:
            folder = Path(folder)
            # Logs can contain synthetic credentials; never copy them to the report/stdout.
            with create_private(folder / "execution.log") as log:
                migrated = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "alembic",
                        "-c",
                        "backend/alembic.ini",
                        "upgrade",
                        "head",
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                    timeout=120,
                )
                if migrated.returncode:
                    report["failureStage"] = "MIGRATION"
                else:
                    test_engine = create_engine(test_url)
                    try:
                        with test_engine.connect() as c:
                            report["dbRevision"] = c.execute(
                                text("SELECT version_num FROM alembic_version")
                            ).scalar_one()
                    finally:
                        test_engine.dispose()
                    junit = folder / "results.xml"
                    executed = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "pytest",
                            *[f"{path}::{name}" for path, name in probes.values()],
                            "-q",
                            "--tb=no",
                            f"--junitxml={junit}",
                        ],
                        cwd=ROOT,
                        env=env,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        check=False,
                        timeout=300,
                    )
                    report["pytestExitCode"] = executed.returncode
                    if junit.exists():
                        report["probes"], unexpected = probe_results(junit, probes)
                        if (
                            executed.returncode == 0
                            and not unexpected
                            and all(p["state"] == "PASSED" for p in report["probes"])
                        ):
                            if restored_denial_only:
                                observations = denial_observations(
                                    junit,
                                    run_id=run_id,
                                    code_revision=identity["commit"],
                                    db_revision=report["dbRevision"],
                                    started_at=report["startedAt"],
                                    now=datetime.now(UTC),
                                )
                                report["restoredDenialObservations"] = observations
                                if len(observations) == len(ALL_CASES):
                                    report["result"] = "PARTIAL"
                                    report["restoredAccessDenial"] = (
                                        "SYNTHETIC_FRESH_AUTH_CASES_PASSED"
                                    )
                            else:
                                report["businessObservationState"], observation = (
                                    business_observation(
                                        junit,
                                        run_id=run_id,
                                        code_revision=identity["commit"],
                                        db_revision=report["dbRevision"],
                                        started_at=report["startedAt"],
                                        now=datetime.now(UTC),
                                    )
                                )
                                if observation is not None:
                                    report["syntheticBusinessObservation"] = observation
                                    report["result"] = "PARTIAL"
                    else:
                        report["failureStage"] = "EXECUTION"
        report["sourceUnchanged"] = source_identity() == identity
        if not report["sourceUnchanged"]:
            report["result"] = "BLOCKED"
            report["businessObservationState"] = "INVALID_SOURCE_CHANGED"
            report["syntheticBusinessObservation"] = None
            report["restoredDenialObservations"] = []
            report["restoredAccessDenial"] = "UNVERIFIED"
        if report["result"] == "PARTIAL" and any(
            p["probe"] == "RESTORED_SESSION_CHALLENGE_AND_AUTHORITY_DENIAL"
            and p["state"] == "PASSED"
            for p in report["probes"]
        ):
            report["restoredAccessDenial"] = "SYNTHETIC_SCENARIO_PASSED"
    finally:
        try:
            if created:
                with admin.connect() as c:
                    c.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
                report["databaseCleaned"] = True
        finally:
            admin.dispose()
    report["finishedAt"] = datetime.now(UTC).isoformat()
    with create_private(output) as destination:
        destination.write(canonical(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--restored-denial-only",
        action="store_true",
        help="새 소유DB의 합성 복원·새MFA 권한 거부11조건만 실행",
    )
    args = parser.parse_args()
    try:
        report = run(
            admin_url=os.environ["FS_GW_ROUTE_VERIFY_ADMIN_URL"],
            output=args.report,
            restored_denial_only=args.restored_denial_only,
        )
    except (
        BackupError,
        OSError,
        KeyError,
        ValueError,
        TypeError,
        SQLAlchemyError,
        subprocess.SubprocessError,
        ElementTree.ParseError,
    ):
        parser.exit(
            1, "검증하지 못했습니다. 소유 테스트DB 연결·파일·실행 환경을 확인하세요.\n"
        )
    print(
        json.dumps(
            {"runId": report["runId"], "result": report["result"], "ready": False}
        )
    )
    return 0 if report["result"] == "PARTIAL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
