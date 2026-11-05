"""No arbitrary status/flags, stale execution or untrusted report can count as a probe."""

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from xml.etree import ElementTree as ET

import pytest
from fs.gw.restored_denial import (
    ALL_CASES,
    CALENDAR_CASES,
    CASES,
    CHAT_CASES,
    DELEGATION_BOUND_CASES,
    DELEGATION_CASES,
    DELEGATION_RELATION_CASES,
    OBJECT_CASES,
    POST_CASES,
    PROPERTY,
    STORED_DELEGATION_CASES,
    RestoredDenialObservation,
)
from pydantic import ValidationError
from test_gw_route_verify import runner

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
    if case in POST_CASES:
        guarded = case == "POST_VISIBILITY_GUARD"
        data.update(
            version=3,
            scope="SYNTHETIC_CLOSED_RESTORE_POST_VISIBILITY",
            sourceComparisonScope="SELECTED_AUTHORIZATION_ORGANIZATION_AND_POST_TABLES",
            writeStatus=status,
            writeErrorCode=code,
            baselineReadConfirmed=True,
            baselineWriteConfirmed=True,
            restoredOwnerReadConfirmed=not guarded,
            restoredPublicReadConfirmed=not guarded,
            restoredOrgReadConfirmed=not guarded,
            restoredOwnDraftWriteConfirmed=not guarded,
            quarantineObserved=guarded,
            companyHold=guarded,
            contentExposed=False,
            deniedPostStateUnchanged=True,
            listingMode="IDENTITY_DENIED" if guarded else "FILTERED",
            listStatus=403 if guarded else 200,
            searchStatus=403 if guarded else 200,
            listCode="GW_IDENTITY_REQUIRED" if guarded else None,
            searchCode="GW_IDENTITY_REQUIRED" if guarded else None,
            visibilityReplayed=False,
        )
    if case in CHAT_CASES:
        guarded = case == "CHAT_MEMBERSHIP_GUARD"
        data.update(
            version=4,
            scope="SYNTHETIC_CLOSED_RESTORE_CHAT_MEMBERSHIP",
            sourceComparisonScope="SELECTED_AUTHORIZATION_CHAT_AND_RECEIPT_TABLES",
            writeStatus=status,
            writeErrorCode=code,
            replayStatus=status,
            replayCode=code,
            cursorStatus=status,
            cursorCode=code,
            readStatus=status,
            readCode=code,
            listStatus=403 if guarded else 200,
            listCode=code if guarded else None,
            listingMode="IDENTITY_DENIED" if guarded else "FILTERED",
            baselineReadConfirmed=True,
            baselineSendConfirmed=True,
            baselineCursorConfirmed=True,
            restoredOwnerReadConfirmed=not guarded,
            restoredSharedReadConfirmed=not guarded,
            restoredSharedSendConfirmed=not guarded,
            restoredSharedCursorConfirmed=not guarded,
            quarantineObserved=guarded,
            companyHold=guarded,
            contentExposed=False,
            deniedChatStateUnchanged=True,
            membershipReplayed=False,
            cachedReceiptRetained=True,
        )
    if case in CALENDAR_CASES:
        guarded = case == "CALENDAR_ATTENDEE_GUARD"
        data.update(
            version=5,
            scope="SYNTHETIC_CLOSED_RESTORE_CALENDAR_AUTHORIZATION",
            sourceComparisonScope="SELECTED_AUTHORIZATION_CALENDAR_AND_RECEIPT_TABLES",
            respondStatus=status,
            respondCode=code,
            replayStatus=status,
            replayCode=code,
            editStatus=status,
            editCode=code,
            cancelStatus=status,
            cancelCode=code,
            attendeeEditStatus=status,
            attendeeEditCode=code,
            attendeeCancelStatus=status,
            attendeeCancelCode=code,
            listStatus=403 if guarded else 200,
            listCode=code if guarded else None,
            listingMode="IDENTITY_DENIED" if guarded else "FILTERED",
            baselineReadConfirmed=True,
            baselineRespondConfirmed=True,
            baselineOwnerEditConfirmed=True,
            restoredOwnerReadConfirmed=not guarded,
            restoredOwnerEditConfirmed=not guarded,
            restoredAttendeeReadConfirmed=not guarded,
            restoredAttendeeRespondConfirmed=not guarded,
            quarantineObserved=guarded,
            companyHold=guarded,
            contentExposed=False,
            deniedCalendarStateUnchanged=True,
            attendeesReplayed=False,
            cachedReceiptRetained=True,
        )
    if case in DELEGATION_CASES:
        guarded = case == "DELEGATION_GUARD"
        data.update(
            version=6,
            scope="SYNTHETIC_CLOSED_RESTORE_DELEGATION_AUTHORIZATION",
            sourceComparisonScope="SELECTED_AUTHORIZATION_DELEGATION_DOCUMENT_AND_RECEIPT_TABLES",
            approveStatus=status,
            approveCode=code,
            rejectStatus=status,
            rejectCode=code,
            listStatus=403 if guarded else 200,
            listCode=code if guarded else None,
            searchStatus=403 if guarded else 200,
            searchCode=code if guarded else None,
            historyStatus=403 if guarded else 200,
            historyCode=code if guarded else None,
            replayStatus=403 if guarded else 200,
            replayCode=code if guarded else None,
            listingMode="IDENTITY_DENIED" if guarded else "FILTERED",
            baselineDelegatedRead=True,
            baselineDelegatedApproval=True,
            baselineActorHistory=True,
            restoredOriginalRead=not guarded,
            restoredOriginalApproval=not guarded,
            restoredActorHistory=not guarded,
            quarantineObserved=guarded,
            companyHold=guarded,
            contentExposed=False,
            deniedDelegationStateUnchanged=True,
            delegationReplayed=False,
            cachedReceiptRetained=True,
            restoredDelegationsRevoked=True,
        )
    if case in DELEGATION_BOUND_CASES:
        data.update(
            version=7,
            scope="SYNTHETIC_SOURCE_BOUNDS_AND_CLOSED_RESTORE_DELEGATION_FLOOR",
            sourceComparisonScope="SELECTED_AUTHORIZATION_DELEGATION_DOCUMENT_AND_RECEIPT_TABLES",
            sourceReadStatus=404,
            sourceApproveStatus=404,
            sourceRejectStatus=404,
            sourceErrorCode="NOT_FOUND",
            sourceListHidden=True,
            sourceSearchHidden=True,
            sourcePolicyEmpty=True,
            sourceDenialStateUnchanged=True,
            baselineDelegatedRead=True,
            baselineDelegatedApproval=True,
            sourceWindow={
                "DELEGATION_NOT_STARTED": "FUTURE",
                "DELEGATION_EXPIRED": "EXPIRED",
                "DELEGATION_KIND_INPUT": "NO_GRANT",
            }.get(case, "ACTIVE"),
            timeEndpointPolicyConfirmed=case
            in {"DELEGATION_NOT_STARTED", "DELEGATION_EXPIRED"},
            amountEqualityConfirmed=case == "DELEGATION_AMOUNT",
            kindInputStatus=400 if case == "DELEGATION_KIND_INPUT" else None,
            kindInputCode="VALIDATION_FAILED"
            if case == "DELEGATION_KIND_INPUT"
            else None,
            stageAdvancedConfirmed=case == "DELEGATION_CURRENT_STAGE",
            restoredOriginalRead=True,
            restoredOriginalApproval=True,
            restoredApproveStatus=404,
            restoredRejectStatus=404,
            restoredErrorCode="NOT_FOUND",
            restoredListHidden=True,
            restoredSearchHidden=True,
            restoredDelegationsRevoked=True,
            restoredDenialStateUnchanged=True,
            restoredBoundaryCause="ALL_DELEGATIONS_REVOKED",
            companyHold=False,
            contentExposed=False,
            delegationReplayed=False,
        )
    if case in DELEGATION_RELATION_CASES:
        direct = case == "DELEGATION_DIRECT_ASSIGNMENT"
        chain = case == "DELEGATION_CHAIN_INPUT"
        data.update(
            version=8,
            scope="SYNTHETIC_SOURCE_RELATION_MONEY_AND_CLOSED_RESTORE_FLOOR",
            sourceComparisonScope="SELECTED_AUTHORIZATION_DELEGATION_DOCUMENT_AND_RECEIPT_TABLES",
            sourceReadStatus=200 if direct else 404,
            sourceReadCode=None if direct else "NOT_FOUND",
            sourceApproveStatus=status,
            sourceRejectStatus=status,
            sourceActionCode=code,
            sourceActionReason="NOT_CURRENT_STEP" if direct else None,
            sourceTargetAmount=None if case == "DELEGATION_MISSING_AMOUNT" else "100",
            sourceTargetCurrency=None
            if case == "DELEGATION_MISSING_AMOUNT"
            else "USD"
            if case == "DELEGATION_FOREIGN_CURRENCY"
            else "KRW",
            sourceLimitedGrant=case
            in {"DELEGATION_FOREIGN_CURRENCY", "DELEGATION_MISSING_AMOUNT"},
            sourceTargetListed=direct,
            sourceTargetSearchable=direct,
            sourcePolicyEmpty=True,
            sourceDenialStateUnchanged=True,
            baselineDelegatedRead=True,
            baselineDelegatedApproval=True,
            sourceRemainingValidGrant=True,
            chainInputStatus=409 if chain else None,
            chainInputCode="PRECONDITION_NOT_MET" if chain else None,
            chainInputReason="DELEGATION_OVERLAP_OR_CHAIN" if chain else None,
            chainRejectedStateUnchanged=chain,
            sourceDirectApproval=direct,
            restoredOriginalRead=True,
            restoredOriginalApproval=True,
            restoredSubjectDirectApproval=direct,
            restoredReadStatus=200 if direct else 404,
            restoredReadCode=None if direct else "NOT_FOUND",
            restoredApproveStatus=status,
            restoredRejectStatus=status,
            restoredActionCode=code,
            restoredActionReason="NOT_CURRENT_STEP" if direct else None,
            restoredTargetListed=direct,
            restoredTargetSearchable=direct,
            restoredDelegationsRevoked=True,
            restoredDenialStateUnchanged=True,
            restoredBoundaryCause="DIRECT_ASSIGNMENT_RETAINED"
            if direct
            else "ALL_DELEGATIONS_REVOKED",
            companyHold=False,
            unauthorizedContentExposed=False,
            delegationReplayed=False,
        )
    if case in STORED_DELEGATION_CASES:
        direct = case == "STORED_DIRECT_ASSIGNMENT"
        shape, count, kind = {
            "STORED_KIND_MISMATCH": ("KIND_MISMATCH", 1, "ERP_PURCHASE"),
            "STORED_OUTGOING_CHAIN": ("OUTGOING_CHAIN", 2, "GENERAL"),
            "STORED_INCOMING_CHAIN": ("INCOMING_CHAIN", 2, "GENERAL"),
            "STORED_DIRECT_ASSIGNMENT": ("DIRECT_ASSIGNMENT", 1, "GENERAL"),
        }[case]
        data.update(
            version=9,
            scope="SYNTHETIC_STORED_FIXTURE_POLICY_ACL_AND_CLOSED_RESTORE_FLOOR",
            sourceComparisonScope="SELECTED_AUTHORIZATION_DELEGATION_DOCUMENT_AND_RECEIPT_TABLES",
            fixtureInserted=True,
            fixtureAcceptedViaApi=False,
            fixtureShape=shape,
            fixtureActiveCount=count,
            fixtureKind=kind,
            targetKind="GENERAL",
            baselineExactKindConfirmed=True,
            baselineWildcardKindConfirmed=True,
            sourceReadStatus=200 if direct else 404,
            sourceReadCode=None if direct else "NOT_FOUND",
            sourceApproveStatus=status,
            sourceRejectStatus=status,
            sourceActionCode=code,
            sourceActionReason="NOT_CURRENT_STEP" if direct else None,
            sourceListVisible=direct,
            sourceSearchVisible=direct,
            sourcePolicyEmpty=True,
            sourceDirectControlConfirmed=True,
            sourcePolicyApproveStatus=409,
            sourcePolicyRejectStatus=409,
            sourcePolicyCode="PRECONDITION_NOT_MET",
            sourcePolicyReason="NOT_CURRENT_STEP",
            sourceDenialStateUnchanged=True,
            restoredOriginalRead=True,
            restoredOriginalApproval=True,
            restoredDirectControlConfirmed=True,
            restoredReadStatus=200 if direct else 404,
            restoredReadCode=None if direct else "NOT_FOUND",
            restoredApproveStatus=status,
            restoredRejectStatus=status,
            restoredActionCode=code,
            restoredActionReason="NOT_CURRENT_STEP" if direct else None,
            restoredListVisible=direct,
            restoredSearchVisible=direct,
            restoredPolicyEmpty=True,
            restoredPolicyApproveStatus=409,
            restoredPolicyRejectStatus=409,
            restoredPolicyCode="PRECONDITION_NOT_MET",
            restoredPolicyReason="NOT_CURRENT_STEP",
            restoredDelegationsRevoked=True,
            restoredDenialStateUnchanged=True,
            restoredBoundaryCause="DIRECT_ASSIGNMENT_RETAINED"
            if direct
            else "ALL_DELEGATIONS_REVOKED",
            companyHold=False,
            unauthorizedContentExposed=False,
            delegationReplayed=False,
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
        "unknown-version": ("version", 10),
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


@pytest.mark.parametrize("case", list(POST_CASES))
def test_post_v3_distinguishes_filtering_from_whole_scope_quarantine(case):
    from fs.gw.restored_denial import parse_observation

    data = observation(case)
    parsed = parse_observation(json.dumps(data))
    guarded = case == "POST_VISIBILITY_GUARD"
    assert parsed.version == 3 and parsed.quarantine_observed == guarded
    assert parsed.restored_owner_read_confirmed is (not guarded)
    for version in (1, 2):
        data["version"] = version
        with pytest.raises(ValueError):
            parse_observation(json.dumps(data))


@pytest.mark.parametrize(
    "change",
    [
        "baseline-read",
        "baseline-write",
        "owner-positive",
        "public-positive",
        "org-positive",
        "draft-positive",
        "quarantine",
        "hold",
        "content",
        "state",
        "list-code",
        "search-code",
        "list-status",
        "search-status",
        "listing-mode",
        "replayed",
        "status-code",
        "source-scope",
        "boolean-int",
        "float-status",
    ],
)
def test_post_guard_contract_cannot_be_reported_as_successful_object_filtering(change):
    from fs.gw.restored_denial import parse_observation

    data = observation("POST_VISIBILITY_GUARD")
    changes = {
        "baseline-read": ("baselineReadConfirmed", False),
        "baseline-write": ("baselineWriteConfirmed", False),
        "owner-positive": ("restoredOwnerReadConfirmed", True),
        "public-positive": ("restoredPublicReadConfirmed", True),
        "org-positive": ("restoredOrgReadConfirmed", True),
        "draft-positive": ("restoredOwnDraftWriteConfirmed", True),
        "quarantine": ("quarantineObserved", False),
        "hold": ("companyHold", False),
        "content": ("contentExposed", True),
        "state": ("deniedPostStateUnchanged", False),
        "list-code": ("listCode", "NOT_FOUND"),
        "search-code": ("searchCode", "SESSION_EXPIRED"),
        "list-status": ("listStatus", 200),
        "search-status": ("searchStatus", 404),
        "listing-mode": ("listingMode", "FILTERED"),
        "replayed": ("visibilityReplayed", True),
        "status-code": ("errorCode", "NOT_FOUND"),
        "source-scope": ("sourceComparisonScope", "SELECTED_AUTHORIZATION_TABLES"),
        "boolean-int": ("quarantineObserved", 1),
        "float-status": ("listStatus", 403.0),
    }
    key, value = changes[change]
    data[key] = value
    with pytest.raises(ValueError):
        parse_observation(json.dumps(data))


@pytest.mark.parametrize("case", list(CHAT_CASES))
def test_chat_v4_preserves_previous_versions_and_exact_membership_boundary(case):
    from fs.gw.restored_denial import parse_observation

    data = observation(case)
    parsed = parse_observation(json.dumps(data))
    assert parsed.version == 4 and not parsed.membership_replayed
    assert parsed.restored_shared_send_confirmed is (case == "CHAT_LEFT_MEMBER")
    for version in (1, 2, 3):
        data["version"] = version
        with pytest.raises(ValueError):
            parse_observation(json.dumps(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("baselineReadConfirmed", False),
        ("baselineSendConfirmed", False),
        ("baselineCursorConfirmed", False),
        ("restoredOwnerReadConfirmed", True),
        ("restoredSharedReadConfirmed", True),
        ("restoredSharedSendConfirmed", True),
        ("restoredSharedCursorConfirmed", True),
        ("quarantineObserved", False),
        ("companyHold", False),
        ("contentExposed", True),
        ("deniedChatStateUnchanged", False),
        ("membershipReplayed", True),
        ("cachedReceiptRetained", False),
        ("writeStatus", 200),
        ("writeErrorCode", "NOT_FOUND"),
        ("replayStatus", 200),
        ("replayCode", "SESSION_EXPIRED"),
        ("cursorStatus", 200),
        ("cursorCode", "NOT_FOUND"),
        ("readStatus", 200),
        ("readCode", "NOT_FOUND"),
        ("listStatus", 200),
        ("listCode", None),
        ("listingMode", "FILTERED"),
        ("sourceComparisonScope", "SELECTED_AUTHORIZATION_TABLES"),
        ("companyHold", 1),
        ("readStatus", 403.0),
    ],
)
def test_chat_guard_rejects_cached_replay_cursor_or_false_positive_claims(field, value):
    from fs.gw.restored_denial import parse_observation

    data = observation("CHAT_MEMBERSHIP_GUARD")
    data[field] = value
    with pytest.raises(ValueError):
        parse_observation(json.dumps(data))


@pytest.mark.parametrize("case", list(CALENDAR_CASES))
def test_calendar_v5_keeps_owner_and_attendee_boundaries_separate(case):
    from fs.gw.restored_denial import parse_observation

    data = observation(case)
    parsed = parse_observation(json.dumps(data))
    assert parsed.version == 5 and not parsed.attendees_replayed
    assert parsed.restored_attendee_respond_confirmed is (
        case == "CALENDAR_REMOVED_ATTENDEE"
    )
    for version in (1, 2, 3, 4):
        data["version"] = version
        with pytest.raises(ValueError):
            parse_observation(json.dumps(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("baselineReadConfirmed", False),
        ("baselineRespondConfirmed", False),
        ("baselineOwnerEditConfirmed", False),
        ("restoredOwnerReadConfirmed", True),
        ("restoredOwnerEditConfirmed", True),
        ("restoredAttendeeReadConfirmed", True),
        ("restoredAttendeeRespondConfirmed", True),
        ("quarantineObserved", False),
        ("companyHold", False),
        ("contentExposed", True),
        ("deniedCalendarStateUnchanged", False),
        ("attendeesReplayed", True),
        ("cachedReceiptRetained", False),
        ("respondStatus", 200),
        ("respondCode", "NOT_FOUND"),
        ("replayStatus", 200),
        ("replayCode", "SESSION_EXPIRED"),
        ("editStatus", 200),
        ("editCode", "NOT_FOUND"),
        ("cancelStatus", 200),
        ("cancelCode", "NOT_FOUND"),
        ("attendeeEditStatus", 200),
        ("attendeeEditCode", "NOT_FOUND"),
        ("attendeeCancelStatus", 200),
        ("attendeeCancelCode", "NOT_FOUND"),
        ("listStatus", 200),
        ("listCode", None),
        ("listingMode", "FILTERED"),
        ("sourceComparisonScope", "SELECTED_AUTHORIZATION_TABLES"),
        ("companyHold", 1),
        ("respondStatus", 403.0),
    ],
)
def test_calendar_rejects_false_owner_or_attendee_or_cached_receipt_claims(
    field, value
):
    from fs.gw.restored_denial import parse_observation

    data = observation("CALENDAR_ATTENDEE_GUARD")
    data[field] = value
    with pytest.raises(ValueError):
        parse_observation(json.dumps(data))


@pytest.mark.parametrize("case", list(DELEGATION_CASES))
def test_delegation_v6_separates_current_power_from_historical_actor_access(case):
    from fs.gw.restored_denial import parse_observation

    data = observation(case)
    parsed = parse_observation(json.dumps(data))
    assert parsed.version == 6 and not parsed.delegation_replayed
    assert parsed.restored_actor_history is (case == "DELEGATION_REVOKED")
    for version in (1, 2, 3, 4, 5):
        data["version"] = version
        with pytest.raises(ValueError):
            parse_observation(json.dumps(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("baselineDelegatedRead", False),
        ("baselineDelegatedApproval", False),
        ("baselineActorHistory", False),
        ("restoredOriginalRead", True),
        ("restoredOriginalApproval", True),
        ("restoredActorHistory", True),
        ("quarantineObserved", False),
        ("companyHold", False),
        ("contentExposed", True),
        ("deniedDelegationStateUnchanged", False),
        ("delegationReplayed", True),
        ("restoredDelegationsRevoked", False),
        ("cachedReceiptRetained", False),
        ("approveStatus", 200),
        ("approveCode", "NOT_FOUND"),
        ("rejectStatus", 200),
        ("rejectCode", "NOT_FOUND"),
        ("listStatus", 200),
        ("listCode", None),
        ("searchStatus", 200),
        ("searchCode", None),
        ("historyStatus", 200),
        ("historyCode", None),
        ("replayStatus", 200),
        ("replayCode", None),
        ("listingMode", "FILTERED"),
        ("sourceComparisonScope", "SELECTED_AUTHORIZATION_TABLES"),
        ("companyHold", 1),
        ("approveStatus", 403.0),
    ],
)
def test_delegation_rejects_false_authority_or_history_or_replay_claims(field, value):
    from fs.gw.restored_denial import parse_observation

    data = observation("DELEGATION_GUARD")
    data[field] = value
    with pytest.raises(ValueError):
        parse_observation(json.dumps(data))


@pytest.mark.parametrize("case", list(DELEGATION_BOUND_CASES))
def test_v7_measures_source_boundary_separately_from_restore_floor(case):
    from fs.gw.restored_denial import parse_observation

    data = observation(case)
    parsed = parse_observation(json.dumps(data))
    assert (
        parsed.version == 7
        and parsed.restored_boundary_cause == "ALL_DELEGATIONS_REVOKED"
    )
    for version in range(1, 7):
        data["version"] = version
        with pytest.raises(ValueError):
            parse_observation(json.dumps(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("sourceReadStatus", 200),
        ("sourceApproveStatus", 409),
        ("sourceRejectStatus", 403),
        ("sourceErrorCode", "NOT_CURRENT_STEP"),
        ("sourceListHidden", False),
        ("sourceSearchHidden", False),
        ("sourcePolicyEmpty", False),
        ("sourceDenialStateUnchanged", False),
        ("baselineDelegatedRead", False),
        ("baselineDelegatedApproval", False),
        ("sourceWindow", "ACTIVE"),
        ("timeEndpointPolicyConfirmed", False),
        ("amountEqualityConfirmed", True),
        ("kindInputStatus", 400),
        ("kindInputCode", "VALIDATION_FAILED"),
        ("stageAdvancedConfirmed", True),
        ("restoredOriginalRead", False),
        ("restoredOriginalApproval", False),
        ("restoredApproveStatus", 409),
        ("restoredRejectStatus", 200),
        ("restoredErrorCode", "NOT_CURRENT_STEP"),
        ("restoredListHidden", False),
        ("restoredSearchHidden", False),
        ("restoredDelegationsRevoked", False),
        ("restoredDenialStateUnchanged", False),
        ("restoredBoundaryCause", "EXPIRED_ONLY"),
        ("companyHold", True),
        ("contentExposed", True),
        ("delegationReplayed", True),
        ("sourcePolicyEmpty", 1),
        ("sourceApproveStatus", 404.0),
    ],
)
def test_v7_rejects_unmeasured_source_or_inflated_restore_claim(field, value):
    from fs.gw.restored_denial import parse_observation

    data = observation("DELEGATION_EXPIRED")
    data[field] = value
    with pytest.raises(ValueError):
        parse_observation(json.dumps(data))


@pytest.mark.parametrize(
    "case,field,value",
    [
        ("DELEGATION_AMOUNT", "amountEqualityConfirmed", False),
        ("DELEGATION_KIND_INPUT", "kindInputStatus", 422),
        ("DELEGATION_KIND_INPUT", "kindInputStatus", 400.0),
        ("DELEGATION_KIND_INPUT", "kindInputCode", "DELEGATION_OVERLAP_OR_CHAIN"),
        ("DELEGATION_CURRENT_STAGE", "stageAdvancedConfirmed", False),
    ],
)
def test_v7_does_not_substitute_wrong_input_or_missing_allowed_control(
    case, field, value
):
    from fs.gw.restored_denial import parse_observation

    data = observation(case)
    data[field] = value
    with pytest.raises(ValueError):
        parse_observation(json.dumps(data))


@pytest.mark.parametrize("case", list(DELEGATION_RELATION_CASES))
def test_v8_keeps_direct_read_access_separate_from_delegated_decisions(case):
    from fs.gw.restored_denial import parse_observation

    data = observation(case)
    parsed = parse_observation(json.dumps(data))
    assert parsed.version == 8 and parsed.source_policy_empty
    assert parsed.restored_subject_direct_approval is (
        case == "DELEGATION_DIRECT_ASSIGNMENT"
    )
    for version in range(1, 8):
        data["version"] = version
        with pytest.raises(ValueError):
            parse_observation(json.dumps(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("sourceReadStatus", 404),
        ("sourceReadCode", "NOT_FOUND"),
        ("sourceApproveStatus", 200),
        ("sourceRejectStatus", 404),
        ("sourceActionCode", "NOT_FOUND"),
        ("sourceTargetListed", False),
        ("sourceTargetSearchable", False),
        ("sourcePolicyEmpty", False),
        ("sourceDenialStateUnchanged", False),
        ("baselineDelegatedRead", False),
        ("baselineDelegatedApproval", False),
        ("sourceRemainingValidGrant", False),
        ("chainInputStatus", 409),
        ("chainInputCode", "DELEGATION_OVERLAP_OR_CHAIN"),
        ("chainRejectedStateUnchanged", True),
        ("sourceDirectApproval", False),
        ("restoredOriginalRead", False),
        ("restoredOriginalApproval", False),
        ("restoredSubjectDirectApproval", False),
        ("restoredReadStatus", 404),
        ("restoredReadCode", "NOT_FOUND"),
        ("restoredApproveStatus", 200),
        ("restoredRejectStatus", 404),
        ("restoredActionCode", "NOT_FOUND"),
        ("restoredTargetListed", False),
        ("restoredTargetSearchable", False),
        ("restoredDelegationsRevoked", False),
        ("restoredDenialStateUnchanged", False),
        ("restoredBoundaryCause", "ALL_DELEGATIONS_REVOKED"),
        ("companyHold", True),
        ("unauthorizedContentExposed", True),
        ("delegationReplayed", True),
        ("sourceTargetListed", 1),
        ("sourceApproveStatus", 409.0),
    ],
)
def test_v8_rejects_hidden_direct_rights_or_unmeasured_decision_claim(field, value):
    from fs.gw.restored_denial import parse_observation

    data = observation("DELEGATION_DIRECT_ASSIGNMENT")
    data[field] = value
    with pytest.raises(ValueError):
        parse_observation(json.dumps(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("chainInputStatus", 400),
        ("chainInputStatus", 409.0),
        ("chainInputCode", "VALIDATION_FAILED"),
        ("chainRejectedStateUnchanged", False),
        ("sourceTargetListed", True),
        ("restoredSubjectDirectApproval", True),
        ("restoredBoundaryCause", "DIRECT_ASSIGNMENT_RETAINED"),
    ],
)
def test_v8_chain_requires_exact_rejected_registration_and_retained_valid_grant(
    field, value
):
    from fs.gw.restored_denial import parse_observation

    data = observation("DELEGATION_CHAIN_INPUT")
    data[field] = value
    with pytest.raises(ValueError):
        parse_observation(json.dumps(data))


@pytest.mark.parametrize(
    "case,field,value",
    [
        ("DELEGATION_CHAIN_INPUT", "chainInputReason", "NOT_CURRENT_STEP"),
        ("DELEGATION_DIRECT_ASSIGNMENT", "sourceActionReason", None),
        ("DELEGATION_DIRECT_ASSIGNMENT", "restoredActionReason", None),
        ("DELEGATION_FOREIGN_CURRENCY", "sourceTargetCurrency", "KRW"),
        ("DELEGATION_FOREIGN_CURRENCY", "sourceTargetAmount", None),
        ("DELEGATION_FOREIGN_CURRENCY", "sourceLimitedGrant", False),
        ("DELEGATION_MISSING_AMOUNT", "sourceTargetAmount", "100"),
        ("DELEGATION_MISSING_AMOUNT", "sourceTargetCurrency", "USD"),
        ("DELEGATION_MISSING_AMOUNT", "sourceLimitedGrant", 1),
    ],
)
def test_v8_requires_measured_currency_amount_limit_and_precise_reason(
    case, field, value
):
    from fs.gw.restored_denial import parse_observation

    data = observation(case)
    data[field] = value
    with pytest.raises(ValueError):
        parse_observation(json.dumps(data))


@pytest.mark.parametrize("case", list(STORED_DELEGATION_CASES))
def test_v9_stored_faults_require_both_policy_and_http_observations(case):
    from fs.gw.restored_denial import parse_observation

    data = observation(case)
    parsed = parse_observation(json.dumps(data))
    assert (
        parsed.version == 9
        and parsed.fixture_inserted
        and not parsed.fixture_accepted_via_api
    )
    for version in range(1, 9):
        data["version"] = version
        with pytest.raises(ValueError):
            parse_observation(json.dumps(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("fixtureInserted", False),
        ("fixtureAcceptedViaApi", True),
        ("fixtureShape", "INCOMING_CHAIN"),
        ("fixtureActiveCount", 1),
        ("fixtureKind", "ERP_PURCHASE"),
        ("targetKind", "ERP_PURCHASE"),
        ("baselineExactKindConfirmed", False),
        ("baselineWildcardKindConfirmed", False),
        ("sourceReadStatus", 200),
        ("sourceReadCode", None),
        ("sourceApproveStatus", 409),
        ("sourceRejectStatus", 409),
        ("sourceActionCode", "PRECONDITION_NOT_MET"),
        ("sourceActionReason", "NOT_CURRENT_STEP"),
        ("sourceListVisible", True),
        ("sourceSearchVisible", True),
        ("sourcePolicyEmpty", False),
        ("sourceDirectControlConfirmed", False),
        ("sourcePolicyApproveStatus", 200),
        ("sourcePolicyRejectStatus", 404),
        ("sourcePolicyCode", "NOT_FOUND"),
        ("sourcePolicyReason", "WRONG_ACTOR"),
        ("sourceDenialStateUnchanged", False),
        ("restoredOriginalRead", False),
        ("restoredOriginalApproval", False),
        ("restoredDirectControlConfirmed", False),
        ("restoredReadStatus", 200),
        ("restoredReadCode", None),
        ("restoredApproveStatus", 409),
        ("restoredRejectStatus", 409),
        ("restoredActionCode", "PRECONDITION_NOT_MET"),
        ("restoredActionReason", "NOT_CURRENT_STEP"),
        ("restoredListVisible", True),
        ("restoredSearchVisible", True),
        ("restoredPolicyEmpty", False),
        ("restoredPolicyApproveStatus", 404),
        ("restoredPolicyRejectStatus", 200),
        ("restoredPolicyCode", "NOT_FOUND"),
        ("restoredPolicyReason", "WRONG_ACTOR"),
        ("restoredDelegationsRevoked", False),
        ("restoredDenialStateUnchanged", False),
        ("restoredBoundaryCause", "DIRECT_ASSIGNMENT_RETAINED"),
        ("companyHold", True),
        ("unauthorizedContentExposed", True),
        ("delegationReplayed", True),
        ("fixtureActiveCount", 2.0),
        ("sourcePolicyEmpty", 1),
    ],
)
def test_v9_cannot_promote_inserted_fixture_to_api_acceptance_or_missing_denial(
    field, value
):
    from fs.gw.restored_denial import parse_observation

    data = observation("STORED_OUTGOING_CHAIN")
    data[field] = value
    with pytest.raises(ValueError):
        parse_observation(json.dumps(data))


@pytest.mark.parametrize(
    "case,field,value",
    [
        ("STORED_KIND_MISMATCH", "fixtureKind", "GENERAL"),
        ("STORED_INCOMING_CHAIN", "fixtureShape", "OUTGOING_CHAIN"),
        ("STORED_DIRECT_ASSIGNMENT", "sourceReadStatus", 404),
        ("STORED_DIRECT_ASSIGNMENT", "sourceListVisible", False),
        ("STORED_DIRECT_ASSIGNMENT", "restoredReadStatus", 404),
        ("STORED_DIRECT_ASSIGNMENT", "restoredSearchVisible", False),
        ("STORED_DIRECT_ASSIGNMENT", "sourceActionReason", None),
        ("STORED_DIRECT_ASSIGNMENT", "restoredActionReason", None),
    ],
)
def test_v9_distinguishes_stored_kind_direction_and_authorized_direct_read(
    case, field, value
):
    from fs.gw.restored_denial import parse_observation

    data = observation(case)
    data[field] = value
    with pytest.raises(ValueError):
        parse_observation(json.dumps(data))
