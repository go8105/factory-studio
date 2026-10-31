"""Closed restore: current delegation revocation versus retained historical actor access."""

# ruff: noqa:F401,F811
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_gw_backup import backup_env
from test_gw_company import context
from test_gw_company_work import api, call_work, connect_third, document, third
from test_gw_restored_denial_db import closed, fingerprint, mfa
from test_gw_restored_object_db import denied
from test_hr_work import company_env

from fs.common.db import reset_engine
from fs.core.security.config import security_settings
from fs.gw.operating_contract import canonical
from fs.gw.restored_denial import (
    DELEGATION_CASES,
    PROPERTY,
    RestoredDelegationDenialObservation,
)
from fs.main import create_app

MARKER = "DELEGATION-PRIVATE-65"


def delegation_state(engine):
    with engine.connect() as c:
        return c.scalar(
            text("""SELECT encode(sha256(convert_to(jsonb_build_array(
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.approval_document t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.approval_step t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.approval_event t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.delegation t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM core.request_receipt t)
            )::text,'UTF8')),'hex')""")
        )


def source_state(engine):
    return fingerprint(engine), delegation_state(engine)


def data(response, expected=200):
    assert response.status_code == expected
    return response.json()["data"]


def submitted(env, drafter, route_id, title):
    doc = call_work(
        env,
        drafter,
        "documents",
        None,
        "create",
        {
            "route_id": int(route_id),
            "kind": "GENERAL",
            "title": title,
            "body": title,
        },
    )
    return data(
        api(
            drafter,
            env[1],
            f"documents/{doc['id']}/submit",
            {"expectedVersion": doc["version"]},
        )
    )


def actor_history(doc, actual, original):
    events = [e for e in doc["events"] if e["eventType"] == "APPROVED"]
    assert len(events) == 1
    assert str(events[0]["actingPersonId"]) == str(actual)
    assert events[0]["onBehalfOfPersonId"] == (str(original) if original else None)
    assert doc["status"] == "APPROVED" and not doc["actionSteps"]


@pytest.mark.parametrize("case", list(DELEGATION_CASES))
def test_closed_restore_delegation_authorization(
    company_env, backup_env, third, monkeypatch, record_property, case
):
    engine, co, admin, staff = company_env
    module, config, folders, password = backup_env
    started = datetime.now(UTC).isoformat()
    guarded = case == "DELEGATION_GUARD"
    aid = context(engine, admin).user_id
    uid = context(engine, staff).user_id
    connect_third(company_env, third)
    with engine.connect() as c:
        people = {
            r["user_id"]: r["person_id"]
            for r in c.execute(
                text(
                    "SELECT user_id,person_id FROM gw.person_identity_binding WHERE workspace_id=:w AND state='ACTIVE'"
                ),
                {"w": co["companyId"]},
            ).mappings()
        }
    original, delegate = people[uid], people[aid]
    template = document(company_env, original)
    target_doc = submitted(company_env, third, template["routeId"], MARKER)
    history_doc = submitted(
        company_env, third, template["routeId"], "DELEGATION-HISTORY-65"
    )
    control_doc = submitted(
        company_env, third, template["routeId"], "DELEGATION-CONTROL-65"
    )
    now = datetime.now(UTC)
    grant = data(
        api(
            staff,
            co,
            "delegations",
            {
                "delegatePersonId": str(delegate),
                "startsAt": (now - timedelta(hours=1)).isoformat(),
                "endsAt": (now + timedelta(hours=2)).isoformat(),
                "documentKind": "GENERAL",
                "reason": "합성 복원 위임 대조",
            },
        ),
        201,
    )
    target_path = f"documents/{target_doc['id']}"
    history_path = f"documents/{history_doc['id']}"
    control_path = f"documents/{control_doc['id']}"
    baseline = data(api(admin, co, target_path, method="GET"))
    assert len(baseline["actionSteps"]) == 1
    assert baseline["actionSteps"][0]["delegationId"] == grant["id"]
    cache_key = str(uuid4())
    cache_body = {"expectedVersion": history_doc["version"]}
    cached = data(api(admin, co, history_path + "/approve", cache_body, key=cache_key))
    actor_history(cached, delegate, original)
    if not guarded:
        data(
            api(
                staff,
                co,
                f"delegations/{grant['id']}/revoke",
                {"expectedVersion": grant["version"]},
            )
        )
        denied(api(admin, co, target_path, method="GET"), 404, "NOT_FOUND")
    secrets = {u: pyotp.random_base32() for u in (aid, uid)}
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
    if guarded:
        data(
            api(
                staff,
                co,
                f"delegations/{grant['id']}/revoke",
                {"expectedVersion": grant["version"]},
            )
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
            active = c.scalar(
                text(
                    "SELECT count(*) FROM gw.person_identity_binding WHERE workspace_id=:w AND state='ACTIVE'"
                ),
                {"w": co["companyId"]},
            )
            assert hold == guarded and (active == 0) == guarded
            revoked = c.scalar(
                text("SELECT revoked_at IS NOT NULL FROM gw.delegation WHERE id=:id"),
                {"id": int(grant["id"])},
            )
            assert revoked is True
            assert (
                c.scalar(
                    text("SELECT count(*) FROM gw.delegation WHERE revoked_at IS NULL")
                )
                == 0
            )
            assert c.scalar(
                text(
                    "SELECT response_summary->>'id' FROM core.request_receipt WHERE workspace_id=:w AND actor_user_id=:u AND request_key=:key"
                ),
                {"w": co["companyId"], "u": aid, "key": cache_key},
            ) == str(cached["id"])
        with monkeypatch.context() as local:
            local.setenv(
                "DATABASE_URL", target_url.render_as_string(hide_password=False)
            )
            reset_engine()
            with (
                TestClient(create_app()) as control,
                TestClient(create_app()) as subject,
            ):
                mfa(control, target, "hugh-admin", password, secrets[aid])
                mfa(subject, target, "hugh-staff", password, secrets[uid])
                target_before = delegation_state(target) if guarded else None
                original_read = api(subject, co, target_path, method="GET")
                original_approve = api(
                    subject,
                    co,
                    control_path + "/approve",
                    {"expectedVersion": control_doc["version"]},
                )
                history = api(control, co, history_path, method="GET")
                if guarded:
                    for response in (original_read, original_approve, history):
                        denied(response, 403, "GW_IDENTITY_REQUIRED")
                else:
                    assert len(data(original_read)["actionSteps"]) == 1
                    actor_history(data(original_approve), original, None)
                    actor_history(data(history), delegate, original)
                    target_before = delegation_state(target)
                with target.connect() as c:
                    assert c.scalar(
                        text(
                            "SELECT response_summary->>'id' FROM core.request_receipt WHERE workspace_id=:w AND actor_user_id=:u AND request_key=:key"
                        ),
                        {"w": co["companyId"], "u": aid, "key": cache_key},
                    ) == str(cached["id"])
                read = api(control, co, target_path, method="GET")
                approve = api(
                    control,
                    co,
                    target_path + "/approve",
                    {"expectedVersion": target_doc["version"]},
                )
                reject = api(
                    control,
                    co,
                    target_path + "/reject",
                    {
                        "expectedVersion": target_doc["version"],
                        "reason": "거부할 합성 대리 결재",
                    },
                )
                status, code = DELEGATION_CASES[case]
                for response in (read, approve, reject):
                    denied(response, status, code)
                replay = api(
                    control, co, history_path + "/approve", cache_body, key=cache_key
                )
                if guarded:
                    denied(replay, 403, "GW_IDENTITY_REQUIRED")
                else:
                    assert data(replay) == cached
                    actor_history(data(replay), delegate, original)
                listing = api(control, co, "documents", method="GET")
                search = control.get(
                    "/api/v1/gw/documents",
                    params={"companyId": co["companyId"], "search": MARKER},
                )
                if guarded:
                    for response in (listing, search):
                        denied(response, 403, "GW_IDENTITY_REQUIRED")
                else:
                    ids = {str(row["id"]) for row in data(listing)["rows"]}
                    assert (
                        str(target_doc["id"]) not in ids
                        and str(history_doc["id"]) in ids
                    )
                    assert data(search)["rows"] == []
                responses = (read, approve, reject, listing, search)
                if guarded:
                    responses += (original_read, original_approve, history, replay)
                assert all(MARKER not in response.text for response in responses)
                assert all(
                    "data" not in response.json()
                    for response in responses
                    if response.status_code >= 400
                )
                assert delegation_state(target) == target_before
            reset_engine()
        assert closed(target) and source_state(engine) == before
        evidence = (folders["reports"] / "evidence.json").read_bytes()
        observation = RestoredDelegationDenialObservation.model_validate(
            {
                "version": 6,
                "scope": "SYNTHETIC_CLOSED_RESTORE_DELEGATION_AUTHORIZATION",
                "case": case,
                "runId": os.environ.get("FS_GW_SYNTHETIC_RUN_ID", str(uuid4())),
                "codeRevision": os.environ.get(
                    "FS_GW_SYNTHETIC_CODE_REVISION", "abcdef012345"
                ),
                "dbRevision": json.loads(evidence)["envelope"]["dbRevision"],
                "startedAt": started,
                "finishedAt": datetime.now(UTC).isoformat(),
                "restoreDigest": hashlib.sha256(evidence).hexdigest(),
                "status": read.status_code,
                "errorCode": code,
                "approveStatus": approve.status_code,
                "approveCode": code,
                "rejectStatus": reject.status_code,
                "rejectCode": code,
                "listStatus": listing.status_code,
                "listCode": code if guarded else None,
                "searchStatus": search.status_code,
                "searchCode": code if guarded else None,
                "historyStatus": history.status_code,
                "historyCode": code if guarded else None,
                "replayStatus": replay.status_code,
                "replayCode": code if guarded else None,
                "listingMode": "IDENTITY_DENIED" if guarded else "FILTERED",
                "baselineDelegatedRead": True,
                "baselineDelegatedApproval": True,
                "baselineActorHistory": True,
                "restoredOriginalRead": not guarded,
                "restoredOriginalApproval": not guarded,
                "restoredActorHistory": not guarded,
                "quarantineObserved": guarded,
                "companyHold": hold,
                "contentExposed": False,
                "deniedDelegationStateUnchanged": True,
                "cachedReceiptRetained": True,
                "restoredDelegationsRevoked": True,
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
