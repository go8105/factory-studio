"""No arbitrary status/flags, stale execution or untrusted report can count as a probe."""

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from xml.etree import ElementTree as ET

import pytest
from pydantic import ValidationError
from test_gw_route_verify import runner

from fs.gw.restored_denial import CASES, PROPERTY, RestoredDenialObservation

NOW = datetime(2026, 10, 30, 0, 0, tzinfo=UTC)


def observation(case="GW_ROLE"):
    status, code = CASES[case]
    return {
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
    assert (len(results) == 5) == (change == "none")


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
