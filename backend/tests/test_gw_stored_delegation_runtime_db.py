"""Stored synthetic grant faults: actual policy decisions, company ACL, closed restore."""

# ruff: noqa:F401,F811
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pyotp
import pytest
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.common.errors import ApiError
from fs.core.security.config import security_settings
from fs.gw import company, policy
from fs.gw import service as gw
from fs.gw.operating_contract import canonical
from fs.gw.restored_denial import (
    PROPERTY,
    STORED_DELEGATION_CASES,
    StoredDelegationRuntimeObservation,
)
from fs.main import create_app
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_gw_backup import backup_env
from test_gw_company import context
from test_gw_company_work import api, call_work, connect_third, document, third
from test_gw_restored_delegation_bounds_db import eligible, fourth
from test_gw_restored_delegation_db import (
    actor_history,
    data,
    delegation_state,
    source_state,
)
from test_gw_restored_delegation_relations_db import route, submitted
from test_gw_restored_denial_db import closed, mfa
from test_gw_restored_object_db import denied
from test_hr_work import company_env

MARKER = "STORED-DELEGATION-68"


def policy_denials(engine, co, client, doc):
    assert eligible(engine, co, client, doc) == []
    results = []
    for action in ("approve", "reject"):
        with (
            pytest.raises(ApiError) as error,
            company.transaction(
                context(engine, client), co["companyId"], write=True
            ) as (c, ctx, _),
        ):
            person, _ = company.principal(c, ctx)
            row = gw.one(c, ctx, "approval_document", int(doc["id"]))
            policy.decision(
                c,
                ctx,
                row,
                person,
                action,
                {
                    "expected_version": doc["version"],
                    "reason": "합성 정책 런타임 거부",
                },
                company_mode=True,
            )
        assert (
            error.value.status_code == 409
            and error.value.code == "PRECONDITION_NOT_MET"
        )
        assert error.value.details["reason"] == "NOT_CURRENT_STEP"
        results.append(error.value.status_code)
    return results


def http_scope(client, co, doc, direct):
    path = f"documents/{doc['id']}"
    read = api(client, co, path, method="GET")
    if direct:
        assert data(read)["title"] == MARKER and not data(read)["actionSteps"]
    else:
        denied(read, 404, "NOT_FOUND")
        assert "data" not in read.json() and MARKER not in read.text
    approve = api(client, co, path + "/approve", {"expectedVersion": doc["version"]})
    reject = api(
        client,
        co,
        path + "/reject",
        {"expectedVersion": doc["version"], "reason": "합성 저장 상태 거부"},
    )
    status, error = (409, "PRECONDITION_NOT_MET") if direct else (404, "NOT_FOUND")
    for r in (approve, reject):
        denied(r, status, error)
        assert r.json()["error"]["details"].get("reason") == (
            "NOT_CURRENT_STEP" if direct else None
        )
        assert "data" not in r.json() and MARKER not in r.text
    listing = data(api(client, co, "documents", method="GET"))["rows"]
    search = data(
        client.get(
            "/api/v1/gw/documents",
            params={"companyId": co["companyId"], "search": MARKER},
        )
    )["rows"]
    assert (str(doc["id"]) in {str(row["id"]) for row in listing}) == direct
    assert (str(doc["id"]) in {str(row["id"]) for row in search}) == direct
    if not direct:
        assert MARKER not in json.dumps(listing, ensure_ascii=False) and search == []
    return read, approve, reject


@pytest.mark.parametrize("case", list(STORED_DELEGATION_CASES))
def test_stored_delegation_policy_acl_and_restore(
    company_env, backup_env, third, fourth, monkeypatch, record_property, case
):
    engine, co, admin, staff = company_env
    module, config, folders, password = backup_env
    started = datetime.now(UTC).isoformat()
    connect_third(company_env, third)
    _other_client, other_person = fourth
    direct = case == "STORED_DIRECT_ASSIGNMENT"
    control_uid, subject_uid = (
        context(engine, staff).user_id,
        context(engine, admin).user_id,
    )
    with company.transaction(context(engine, staff), co["companyId"]) as (c, ctx, _):
        people = {
            r["user_id"]: r["person_id"]
            for r in c.execute(
                text(
                    "SELECT user_id,person_id FROM gw.person_identity_binding WHERE workspace_id=:w AND generation_id=:g AND state='ACTIVE'"
                ),
                {"w": ctx.workspace_id, "g": ctx.generation_id},
            ).mappings()
        }
        now = c.scalar(text("SELECT clock_timestamp()"))
    original, delegate = people[control_uid], people[subject_uid]
    original_route = route(admin, co, "STORED-ORIGINAL", [original])
    direct_route = route(admin, co, "STORED-DIRECT", [delegate])
    target_route = (
        route(admin, co, "STORED-CONFLICT", [original, delegate])
        if direct
        else original_route
    )
    target_doc = submitted(third, co, target_route, MARKER)
    control_doc = submitted(third, co, original_route, "STORED-ORIGINAL-CONTROL-68")
    source_direct = submitted(third, co, direct_route, "STORED-SOURCE-DIRECT-68")
    restored_direct = submitted(third, co, direct_route, "STORED-RESTORE-DIRECT-68")
    assert target_doc["kind"] == "GENERAL"
    grant_body = {
        "delegatePersonId": str(delegate),
        "startsAt": (now - timedelta(hours=1)).isoformat(),
        "endsAt": (now + timedelta(hours=2)).isoformat(),
        "reason": "합成 종류 일치 대조",
    }
    for kind, title in (("GENERAL", "STORED-EXACT-68"), (None, "STORED-WILDCARD-68")):
        history = submitted(third, co, original_route, title)
        grant = data(
            api(staff, co, "delegations", {**grant_body, "documentKind": kind}), 201
        )
        assert grant["documentKind"] == kind
        assert len(eligible(engine, co, admin, history)) == 1
        assert (
            len(
                data(api(admin, co, f"documents/{history['id']}", method="GET"))[
                    "actionSteps"
                ]
            )
            == 1
        )
        actor_history(
            data(
                api(
                    admin,
                    co,
                    f"documents/{history['id']}/approve",
                    {"expectedVersion": history["version"]},
                )
            ),
            delegate,
            original,
        )
        data(
            api(
                staff,
                co,
                f"delegations/{grant['id']}/revoke",
                {"expectedVersion": grant["version"]},
            )
        )
    fixture_kind = "ERP_PURCHASE" if case == "STORED_KIND_MISMATCH" else "GENERAL"
    pairs = [(original, delegate)]
    if case == "STORED_OUTGOING_CHAIN":
        pairs.append((delegate, other_person))
    elif case == "STORED_INCOMING_CHAIN":
        pairs.append((other_person, original))
    with company.transaction(context(engine, admin), co["companyId"], write=True) as (
        c,
        ctx,
        _,
    ):
        for owner, recipient in pairs:
            gw.insert(
                c,
                ctx,
                "delegation",
                {
                    "delegator_person_id": owner,
                    "delegate_person_id": recipient,
                    "starts_at": now - timedelta(hours=1),
                    "ends_at": now + timedelta(hours=2),
                    "document_kind": fixture_kind,
                    "reason": "합성 저장 상태 결함 주입 · 지원 API 아님",
                },
            )
        stored = (
            c.execute(
                text(
                    "SELECT delegator_person_id,delegate_person_id,document_kind FROM gw.delegation WHERE workspace_id=:w AND generation_id=:g AND revoked_at IS NULL"
                ),
                {"w": ctx.workspace_id, "g": ctx.generation_id},
            )
            .mappings()
            .all()
        )
        assert len(stored) == len(pairs)
        assert {
            (r["delegator_person_id"], r["delegate_person_id"]) for r in stored
        } == set(pairs)
        assert all(r["document_kind"] == fixture_kind for r in stored)
    actor_history(
        data(
            api(
                admin,
                co,
                f"documents/{source_direct['id']}/approve",
                {"expectedVersion": source_direct["version"]},
            )
        ),
        delegate,
        None,
    )
    before_denial = delegation_state(engine)
    source_responses = http_scope(admin, co, target_doc, direct)
    source_policy = policy_denials(engine, co, admin, target_doc)
    assert delegation_state(engine) == before_denial
    secrets = {u: pyotp.random_base32() for u in (control_uid, subject_uid)}
    with engine.begin() as c:
        for user, secret in secrets.items():
            key, encrypted = security_settings().box.seal(
                secret, purpose="totp", owner=str(user)
            )
            c.execute(
                text(
                    "INSERT INTO core.mfa_factor(user_id,kind,state,secret_ciphertext,encryption_key_id,version,confirmed_at,created_at) VALUES(:u,'TOTP','ACTIVE',:s,:k,1,clock_timestamp(),clock_timestamp())"
                ),
                {"u": user, "s": encrypted, "k": key},
            )
    source = os.environ["TEST_DATABASE_URL"]
    artifact = folders["backups"] / "delegation.enc"
    module.backup(
        url=source,
        company_id=co["companyId"],
        output=artifact,
        evidence=folders["backups"] / "proof.json",
        config=config,
    )
    checkpoint = folders["checkpoints"] / "delegation.enc"
    head = folders["checkpoints"] / "head.json"
    captured = module.checkpoint(
        url=source, artifact=artifact, output=checkpoint, head=head, config=config
    )
    before = source_state(engine)
    restored = module.restore(
        admin_url=make_url(source)
        .set(database="postgres")
        .render_as_string(hide_password=False),
        artifact=artifact,
        checkpoint_file=checkpoint,
        head=head,
        expected_checkpoint_digest=captured["checkpointDigest"],
        config=config,
        report=folders["reports"] / "restore.json",
        evidence=folders["reports"] / "evidence.json",
    )
    target_url = make_url(source).set(database=restored["database"])
    target = create_engine(target_url)
    try:
        assert restored["result"] == "PARTIAL" and closed(target)
        with target.connect() as c:
            hold = c.scalar(
                text(
                    "SELECT company_hold FROM gw.operating_settings WHERE workspace_id=:w"
                ),
                {"w": co["companyId"]},
            )
            assert hold is False
            assert (
                c.scalar(
                    text("SELECT count(*) FROM gw.delegation WHERE revoked_at IS NULL")
                )
                == 0
            )
        with monkeypatch.context() as local:
            local.setenv(
                "DATABASE_URL", target_url.render_as_string(hide_password=False)
            )
            reset_engine()
            with (
                TestClient(create_app()) as original_client,
                TestClient(create_app()) as subject_client,
            ):
                mfa(
                    original_client,
                    target,
                    "hugh-staff",
                    password,
                    secrets[control_uid],
                )
                mfa(
                    subject_client, target, "hugh-admin", password, secrets[subject_uid]
                )
                assert (
                    len(
                        data(
                            api(
                                original_client,
                                co,
                                f"documents/{target_doc['id']}",
                                method="GET",
                            )
                        )["actionSteps"]
                    )
                    == 1
                )
                actor_history(
                    data(
                        api(
                            original_client,
                            co,
                            f"documents/{control_doc['id']}/approve",
                            {"expectedVersion": control_doc["version"]},
                        )
                    ),
                    original,
                    None,
                )
                actor_history(
                    data(
                        api(
                            subject_client,
                            co,
                            f"documents/{restored_direct['id']}/approve",
                            {"expectedVersion": restored_direct["version"]},
                        )
                    ),
                    delegate,
                    None,
                )
                before_denial = delegation_state(target)
                responses = http_scope(subject_client, co, target_doc, direct)
                restored_policy = policy_denials(target, co, subject_client, target_doc)
                assert delegation_state(target) == before_denial
            reset_engine()
        assert closed(target) and source_state(engine) == before
        evidence = (folders["reports"] / "evidence.json").read_bytes()
        _action_status, action_code = STORED_DELEGATION_CASES[case]
        observation = StoredDelegationRuntimeObservation.model_validate(
            {
                "version": 9,
                "scope": "SYNTHETIC_STORED_FIXTURE_POLICY_ACL_AND_CLOSED_RESTORE_FLOOR",
                "case": case,
                "runId": os.environ.get("FS_GW_SYNTHETIC_RUN_ID", str(uuid4())),
                "codeRevision": os.environ.get(
                    "FS_GW_SYNTHETIC_CODE_REVISION", "abcdef012345"
                ),
                "dbRevision": json.loads(evidence)["envelope"]["dbRevision"],
                "startedAt": started,
                "finishedAt": datetime.now(UTC).isoformat(),
                "restoreDigest": hashlib.sha256(evidence).hexdigest(),
                "status": responses[1].status_code,
                "errorCode": action_code,
                "fixtureInserted": True,
                "fixtureAcceptedViaApi": False,
                "fixtureShape": case.removeprefix("STORED_"),
                "fixtureActiveCount": len(stored),
                "fixtureKind": fixture_kind,
                "targetKind": target_doc["kind"],
                "baselineExactKindConfirmed": True,
                "baselineWildcardKindConfirmed": True,
                "sourceReadStatus": source_responses[0].status_code,
                "sourceReadCode": None if direct else "NOT_FOUND",
                "sourceApproveStatus": source_responses[1].status_code,
                "sourceRejectStatus": source_responses[2].status_code,
                "sourceActionCode": action_code,
                "sourceActionReason": "NOT_CURRENT_STEP" if direct else None,
                "sourceListVisible": direct,
                "sourceSearchVisible": direct,
                "sourcePolicyEmpty": True,
                "sourceDirectControlConfirmed": True,
                "sourcePolicyApproveStatus": source_policy[0],
                "sourcePolicyRejectStatus": source_policy[1],
                "sourcePolicyCode": "PRECONDITION_NOT_MET",
                "sourcePolicyReason": "NOT_CURRENT_STEP",
                "sourceDenialStateUnchanged": True,
                "restoredOriginalRead": True,
                "restoredOriginalApproval": True,
                "restoredDirectControlConfirmed": True,
                "restoredReadStatus": responses[0].status_code,
                "restoredReadCode": None if direct else "NOT_FOUND",
                "restoredApproveStatus": responses[1].status_code,
                "restoredRejectStatus": responses[2].status_code,
                "restoredActionCode": action_code,
                "restoredActionReason": "NOT_CURRENT_STEP" if direct else None,
                "restoredListVisible": direct,
                "restoredSearchVisible": direct,
                "restoredPolicyEmpty": True,
                "restoredPolicyApproveStatus": restored_policy[0],
                "restoredPolicyRejectStatus": restored_policy[1],
                "restoredPolicyCode": "PRECONDITION_NOT_MET",
                "restoredPolicyReason": "NOT_CURRENT_STEP",
                "restoredDelegationsRevoked": True,
                "restoredDenialStateUnchanged": True,
                "restoredBoundaryCause": "DIRECT_ASSIGNMENT_RETAINED"
                if direct
                else "ALL_DELEGATIONS_REVOKED",
                "companyHold": hold,
                "unauthorizedContentExposed": False,
                "delegationReplayed": False,
                "controlMfaAuthenticated": True,
                "subjectMfaAuthenticated": True,
                "closedBefore": True,
                "closedAfter": True,
                "sourceUnchanged": True,
                "sourceComparisonScope": "SELECTED_AUTHORIZATION_DELEGATION_DOCUMENT_AND_RECEIPT_TABLES",
                "ready": False,
                "revocationsComplete": False,
                "liveCompanyAcceptance": False,
            }
        )
        record_property(
            PROPERTY, canonical(observation.model_dump(by_alias=True)).decode()
        )
    finally:
        reset_engine()
        target.dispose()
        cleanup = create_engine(
            make_url(source).set(database="postgres"), isolation_level="AUTOCOMMIT"
        )
        try:
            with cleanup.connect() as c:
                c.execute(text(f'DROP DATABASE "{restored["database"]}" WITH (FORCE)'))
        finally:
            cleanup.dispose()
