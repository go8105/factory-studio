"""Detached flags or stale/failed JUnit observations never establish acceptance."""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree as ET

import pytest
from fs.gw.acceptance_business import PROBE, PROPERTY
from fs.gw.operating_contract import canonical


def runner():
    path = Path(__file__).resolve().parents[2] / "tools/gw_route_verify.py"
    spec = importlib.util.spec_from_file_location("business_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def observation():
    return {
        "version": 1,
        "scope": "SYNTHETIC_TEN_PERSON_ASGI",
        "runId": str(uuid4()),
        "contextDigest": "a" * 64,
        "finalContextDigest": "a" * 64,
        "policyDigest": "b" * 64,
        "workspaceId": "7",
        "generationId": "9",
        "codeRevision": "abc1234",
        "dbRevision": "test_head",
        "startedAt": "2026-10-20T01:00:01+00:00",
        "finishedAt": "2026-10-20T01:00:02+00:00",
        "preflightResult": "PARTIAL",
        "finalPreflightResult": "PARTIAL",
        "mfaAuthenticated": 10,
        "securityAdministrators": 1,
        "staff": 9,
        "approvedDocuments": 9,
        "publishedPosts": 9,
        "acceptedAttendees": 9,
        "comments": 9,
        "notificationsRead": 9,
        "messages": 10,
        "deniedStaffAdminReads": 9,
        "deniedOtherDraftReads": 9,
        "ready": False,
        "liveCompanyAcceptance": False,
        "deviceChecks": "UNVERIFIED",
        "networkChecks": "UNVERIFIED",
        "representativeLiveBusiness": "UNVERIFIED",
    }


@pytest.mark.parametrize(
    "change",
    [
        "none",
        "run",
        "code",
        "db",
        "policy-context",
        "start-before-run",
        "future",
        "time-order",
        "naive-time",
        "missing",
        "duplicate",
        "failed",
        "error",
        "skipped",
        "wrong-class",
        "wrong-property",
        "extra-property",
        "duplicate-property",
        "broken-json",
        "huge",
        "unknown-field",
        "ready",
        "live",
        "device",
        "scope",
        "blocked",
        "final-blocked",
        "missing-mfa",
        "missing-staff",
        "missing-work",
        "bool-count",
    ],
)
def test_current_passed_fixed_scenario_is_required(tmp_path, change):
    module = runner()
    value = observation()
    args = {
        "run_id": value["runId"],
        "code_revision": value["codeRevision"],
        "db_revision": value["dbRevision"],
        "started_at": "2026-10-20T01:00:00+00:00",
        "now": datetime(2026, 10, 20, 1, 1, tzinfo=UTC),
    }
    mutations = {
        "run": {"runId": str(uuid4())},
        "code": {"codeRevision": "fffffff"},
        "db": {"dbRevision": "old"},
        "policy-context": {"finalContextDigest": "c" * 64},
        "start-before-run": {"startedAt": "2026-10-20T00:59:59+00:00"},
        "future": {"finishedAt": (args["now"] + timedelta(seconds=1)).isoformat()},
        "time-order": {"finishedAt": "2026-10-20T01:00:00+00:00"},
        "naive-time": {"startedAt": "2026-10-20T01:00:01"},
        "unknown-field": {"password": "must not copy unknown fields"},
        "ready": {"ready": True},
        "live": {"liveCompanyAcceptance": True},
        "device": {"deviceChecks": "PASS"},
        "scope": {"scope": "LIVE_COMPANY"},
        "blocked": {"preflightResult": "BLOCKED"},
        "final-blocked": {"finalPreflightResult": "BLOCKED"},
        "missing-mfa": {"mfaAuthenticated": 9},
        "missing-staff": {"staff": 8},
        "missing-work": {"approvedDocuments": 8},
        "bool-count": {"securityAdministrators": True},
    }
    value.update(mutations.get(change, {}))
    suite = ET.Element("testsuite")
    path, name = module.PROBES[PROBE]
    case = ET.SubElement(
        suite, "testcase", name=name, classname="tests." + Path(path).stem
    )
    properties = ET.SubElement(case, "properties")
    prop = ET.SubElement(
        properties, "property", name=PROPERTY, value=canonical(value).decode()
    )
    if change == "missing":
        suite.remove(case)
    elif change == "duplicate":
        suite.append(ET.fromstring(ET.tostring(case)))
    elif change in {"failed", "error", "skipped"}:
        ET.SubElement(case, "failure" if change == "failed" else change)
    elif change == "wrong-class":
        case.set("classname", "other")
    elif change == "wrong-property":
        prop.set("name", "other")
    elif change in {"extra-property", "duplicate-property"}:
        ET.SubElement(
            properties,
            "property",
            name=PROPERTY if change == "duplicate-property" else "secret",
            value="unknown",
        )
    elif change == "broken-json":
        prop.set("value", "{invalid")
    elif change == "huge":
        prop.set("value", "x" * 4097)
    xml = tmp_path / "results.xml"
    ET.ElementTree(suite).write(xml)
    state, result = module.business_observation(xml, **args)
    if change == "none":
        assert state == "SYNTHETIC_SCENARIO_PASSED" and result == value
        assert result["ready"] is result["liveCompanyAcceptance"] is False
    else:
        assert state != "SYNTHETIC_SCENARIO_PASSED" and result is None
