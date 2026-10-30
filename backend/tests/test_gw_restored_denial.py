"""No arbitrary status/flags, stale execution or untrusted report can count as a probe."""

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from xml.etree import ElementTree as ET

import pytest
from pydantic import ValidationError
from test_gw_route_verify import runner

from fs.gw.restored_denial import (
    ALL_CASES,
    CASES,
    OBJECT_CASES,
    PROPERTY,
    RestoredDenialObservation,
)

NOW = datetime(2026, 10, 30, 0, 0, tzinfo=UTC)


def observation(case="GW_ROLE"):
    status, code = ALL_CASES[case]
    data = {
        "version": 1,
        "scope": "SYNTHETIC_CLOSED_RESTORE_AUTHENTICATION",
        "case": case,
        "runId": str(uuid4()),
        "codeRevision": "abcdef0",
        "dbRevision": "test_head",
        "startedAt": (NOW - timedelta(seconds=1)).isoformat(),
        "finishedAt": NOW.isoformat(),
        "restoreDigest": "a" * 64,
        "status": status,
        "errorCode": code,
        "controlMfaAuthenticated": True,
        "subjectMfaAuthenticated": case != "CORE_ACCOUNT",
        "closedBefore": True,
        "closedAfter": True,
        "sourceUnchanged": True,
        "sourceComparisonScope": "SELECTED_AUTHORIZATION_TABLES",
        "ready": False,
        "revocationsComplete": False,
        "liveCompanyAcceptance": False,
    }

    if case in OBJECT_CASES:
        data.update(
            version=2,
            scope="SYNTHETIC_CLOSED_RESTORE_OBJECT_AUTHORIZATION",
            sourceComparisonScope="SELECTED_AUTHORIZATION_AND_DOCUMENT_TABLES",
            writeStatus=status,
            writeErrorCode=code,
            positiveObjectRead=True,
            positiveObjectWrite=True,
            listHidden=True,
            deniedObjectStateUnchanged=True,
        )
        if case == "FOREIGN_SCOPE":
            data.update(
                hiddenScopeReadStatus=404,
                hiddenScopeWriteStatus=404,
                hiddenScopeReadCode="NOT_FOUND",
                hiddenScopeWriteCode="NOT_FOUND",
            )
    return data


@pytest.mark.parametrize("case", list(CASES))
def test_fixed_contract_remains_synthetic_partial_scope(case):
    data = RestoredDenialObservation.model_validate(observation(case))
    assert (
        not data.ready
        and not data.revocations_complete
        and not data.live_company_acceptance
    )


@pytest.mark.parametrize(
    "change",
    [
        "status",
        "wrong-code",
        "control",
        "subject",
        "open-before",
        "open-after",
        "source",
        "ready",
        "complete",
        "live",
        "extra",
        "boolean-int",
        "bad-run",
        "future",
    ],
)
def test_rejects_wrong_boundary_or_promoted_completion(change):
    data = observation()
    edits = {
        "status": ("status", 401),
        "wrong-code": ("errorCode", "SESSION_EXPIRED"),
        "control": ("controlMfaAuthenticated", False),
        "subject": ("subjectMfaAuthenticated", False),
        "open-before": ("closedBefore", False),
        "open-after": ("closedAfter", False),
        "source": ("sourceUnchanged", False),
        "ready": ("ready", True),
        "complete": ("revocationsComplete", True),
        "live": ("liveCompanyAcceptance", True),
        "extra": ("url", "https://untrusted.invalid"),
        "boolean-int": ("closedAfter", 1),
        "bad-run": ("runId", "a" * 36),
        "future": ("startedAt", (NOW + timedelta(seconds=1)).isoformat()),
    }
    k, v = edits[change]
    data[k] = v
    with pytest.raises((ValueError, ValidationError)):
        RestoredDenialObservation.model_validate(data)


@pytest.mark.parametrize(
    "change",
    [
        "none",
        "failure",
        "skip",
        "duplicate",
        "missing",
        "wrong-run",
        "wrong-case",
        "old",
        "future",
        "db",
        "version",
        "flag",
        "extra-case",
        "extra-property",
    ],
)
def test_collector_requires_exact_current_execution_and_every_fixed_case(
    tmp_path, change
):
    module = runner()
    run = str(uuid4())
    root = ET.Element("testsuite")
    for key, (path, name) in module.DENIAL_PROBES.items():
        case = key.removeprefix("RESTORED_FRESH_AUTH_")
        data = observation(case)
        data["runId"] = run
        node = ET.SubElement(
            root,
            "testcase",
            name=name,
            classname="tests." + path.split("/")[-1].removesuffix(".py"),
        )
        props = ET.SubElement(node, "properties")
        ET.SubElement(props, "property", name=PROPERTY, value=json.dumps(data))
    first = root[0]
    prop = first.find("./properties/property")
    data = json.loads(prop.get("value"))
    if change == "failure":
        ET.SubElement(first, "failure")
    elif change == "skip":
        ET.SubElement(first, "skipped")
    elif change == "duplicate":
        first.find("properties").append(deepcopy(prop))
    elif change == "missing":
        first.remove(first.find("properties"))
    elif change == "wrong-run":
        data["runId"] = str(uuid4())
    elif change == "wrong-case":
        data["case"] = "GW_ROLE"
        data["status"], data["errorCode"] = CASES["GW_ROLE"]
        data["subjectMfaAuthenticated"] = True
    elif change == "old":
        data["startedAt"] = (NOW - timedelta(minutes=10)).isoformat()
    elif change == "future":
        data["finishedAt"] = (NOW + timedelta(seconds=1)).isoformat()
    elif change == "db":
        data["dbRevision"] = "old_head"
    elif change == "version":
        data["codeRevision"] = "fffffff"
    elif change == "flag":
        data["ready"] = True
    elif change == "extra-case":
        root.append(deepcopy(first))
    elif change == "extra-property":
        ET.SubElement(
            first.find("properties"), "property", name="unsignedClaim", value="PASS"
        )
    prop.set("value", json.dumps(data))
    path = tmp_path / "results.xml"
    ET.ElementTree(root).write(path)
    results = module.denial_observations(
        path,
        run_id=run,
        code_revision="abcdef0",
        db_revision="test_head",
        started_at=(NOW - timedelta(seconds=2)).isoformat(),
        now=NOW,
    )
    assert (len(results) == len(ALL_CASES)) == (change == "none")


def test_denial_profile_refuses_missing_container_before_database(
    tmp_path, monkeypatch
):
    module = runner()
    tmp_path.chmod(0o700)
    monkeypatch.delenv("GW_BACKUP_TEST_CONTAINER", raising=False)
    monkeypatch.setattr(
        module, "create_engine", lambda *a, **k: pytest.fail("must not connect")
    )
    with pytest.raises(module.BackupError):
        module.run(
            admin_url="postgresql+psycopg://127.0.0.1:55439/postgres",
            output=tmp_path / "report",
            restored_denial_only=True,
        )


@pytest.mark.parametrize("change", ["none", "id", "name", "extra-bind", "public-bind"])
def test_denial_profile_pins_full_container_id_and_only_loopback(monkeypatch, change):
    from types import SimpleNamespace

    from sqlalchemy.engine import make_url

    module = runner()
    cid = "a" * 64
    ports = [{"HostIp": "127.0.0.1", "HostPort": "55439"}]
    info = {
        "id": cid,
        "owner": "owned-test",
        "running": True,
        "ports": {"5432/tcp": ports},
    }
    if change == "id":
        info["id"] = "b" * 64
    elif change == "name":
        cid = "some-container-name"
    elif change == "extra-bind":
        ports.append({"HostIp": "0.0.0.0", "HostPort": "55439"})
    elif change == "public-bind":
        ports[0]["HostIp"] = "0.0.0.0"
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(info)),
    )
    args = (
        make_url("postgresql+psycopg://127.0.0.1:55439/postgres"),
        cid,
        "owned-test",
    )
    if change == "none":
        module.validate_restore_container(*args, strict=True)
    else:
        with pytest.raises(module.BackupError):
            module.validate_restore_container(*args, strict=True)


@pytest.mark.parametrize("case", list(OBJECT_CASES))
def test_object_v2_keeps_original_v1_separate(case):
    from fs.gw.restored_denial import parse_observation

    data = observation(case)
    parsed = parse_observation(json.dumps(data))
    assert parsed.version == 2 and parsed.case == case
    data["version"] = 1
    with pytest.raises(ValueError):
        parse_observation(json.dumps(data))
    legacy = observation("GW_ROLE")
    assert parse_observation(json.dumps(legacy)).version == 1
    legacy["version"] = 2
    with pytest.raises(ValueError):
        parse_observation(json.dumps(legacy))


@pytest.mark.parametrize(
    "change",
    [
        "write-success",
        "wrong-write-code",
        "no-positive-read",
        "no-positive-write",
        "list-visible",
        "state-changed",
        "wrong-source-scope",
        "other-scope-visible",
        "other-write-allowed",
        "other-code",
        "numeric-boolean",
        "status-float",
        "unknown-version",
    ],
)
def test_object_contract_rejects_unproven_read_write_or_scope(change):
    from fs.gw.restored_denial import parse_observation

    data = observation("FOREIGN_SCOPE")
    edits = {
        "write-success": ("writeStatus", 200),
        "wrong-write-code": ("writeErrorCode", "SESSION_EXPIRED"),
        "no-positive-read": ("positiveObjectRead", False),
        "no-positive-write": ("positiveObjectWrite", False),
        "list-visible": ("listHidden", False),
        "state-changed": ("deniedObjectStateUnchanged", False),
        "wrong-source-scope": (
            "sourceComparisonScope",
            "SELECTED_AUTHORIZATION_TABLES",
        ),
        "other-scope-visible": ("hiddenScopeReadStatus", 200),
        "other-write-allowed": ("hiddenScopeWriteStatus", 200),
        "other-code": ("hiddenScopeReadCode", "COMPANY_ACCESS_DENIED"),
        "numeric-boolean": ("positiveObjectWrite", 1),
        "status-float": ("hiddenScopeReadStatus", 404.0),
        "unknown-version": ("version", 3),
    }
    key, value = edits[change]
    data[key] = value
    with pytest.raises(ValueError):
        parse_observation(json.dumps(data))


@pytest.mark.parametrize(
    "raw", ["[]", "null", "1", '"claim"', '{"version":1,"version":2}', " " * 8193]
)
def test_observation_parser_refuses_ambiguous_non_objects_or_oversized_claims(raw):
    from fs.gw.restored_denial import parse_observation

    with pytest.raises(ValueError):
        parse_observation(raw)
