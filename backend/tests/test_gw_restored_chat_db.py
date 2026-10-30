"""Closed restore: left-channel privacy, cached replay and membership guard."""

# ruff: noqa:F401,F811
import hashlib
import json
import os
from datetime import UTC, datetime
from uuid import uuid4

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_gw_backup import backup_env
from test_gw_company import context
from test_gw_company_work import api
from test_gw_restored_denial_db import closed, fingerprint, mfa
from test_gw_restored_object_db import denied
from test_hr_work import company_env

from fs.common.db import reset_engine
from fs.core.security.config import security_settings
from fs.gw.operating_contract import canonical
from fs.gw.restored_denial import CHAT_CASES, PROPERTY, RestoredChatDenialObservation
from fs.main import create_app

MARKER = "CHAT-PRIVATE-63"


def chat_state(engine):
    with engine.connect() as c:
        return c.scalar(
            text("""SELECT encode(sha256(convert_to(jsonb_build_array(
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.chat_channel t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.chat_member t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.chat_message t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM core.request_receipt t)
            )::text,'UTF8')),'hex')""")
        )


def source_state(engine):
    return fingerprint(engine), chat_state(engine)


def data(response, expected=200):
    assert response.status_code == expected
    return response.json()["data"]


@pytest.mark.parametrize("case", list(CHAT_CASES))
def test_closed_restore_chat_membership(
    company_env, backup_env, monkeypatch, record_property, case
):
    engine, co, admin, staff = company_env
    module, config, folders, password = backup_env
    started = datetime.now(UTC).isoformat()
    guarded = case == "CHAT_MEMBERSHIP_GUARD"
    aid = context(engine, admin).user_id
    uid = context(engine, staff).user_id
    with engine.connect() as c:
        person = c.scalar(
            text(
                "SELECT person_id FROM gw.person_identity_binding WHERE workspace_id=:w AND user_id=:u AND state='ACTIVE'"
            ),
            {"w": co["companyId"], "u": uid},
        )
    private = data(
        api(
            admin,
            co,
            "channels",
            {"name": MARKER, "channelKind": "DIRECT", "memberIds": [str(person)]},
        ),
        201,
    )
    shared = data(
        api(
            admin,
            co,
            "channels",
            {
                "name": "CHAT-CONTROL-63",
                "channelKind": "DIRECT",
                "memberIds": [str(person)],
            },
        ),
        201,
    )
    private_path = f"channels/{private['id']}"
    shared_path = f"channels/{shared['id']}"
    cache_key = str(uuid4())
    cache_body = {"body": MARKER, "clientKey": str(uuid4())}
    cached = data(api(staff, co, private_path + "/messages", cache_body, key=cache_key))
    assert (
        data(api(admin, co, private_path + "/messages", method="GET"))["messages"][0][
            "body"
        ]
        == MARKER
    )
    assert (
        data(api(staff, co, private_path + "/messages", method="GET"))["messages"][0][
            "body"
        ]
        == MARKER
    )
    initial = data(
        api(
            staff,
            co,
            shared_path + "/messages",
            {"body": "합성 공유 메시지", "clientKey": str(uuid4())},
        )
    )
    data(api(staff, co, shared_path + "/messages", method="GET"))
    data(api(staff, co, shared_path + "/read", {"seq": initial["seq"]}))
    if not guarded:
        data(api(staff, co, private_path + "/leave", {}))
        denied(
            api(staff, co, private_path + "/messages", method="GET"), 404, "NOT_FOUND"
        )
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
    artifact = folders["backups"] / "chat.enc"
    module.backup(
        url=source,
        company_id=co["companyId"],
        output=artifact,
        evidence=folders["backups"] / "proof.json",
        config=config,
    )
    if guarded:
        data(api(staff, co, private_path + "/leave", {}))
    checkpoint = folders["checkpoints"] / "chat.enc"
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
            left = c.scalar(
                text(
                    "SELECT left_at IS NOT NULL FROM gw.chat_member WHERE channel_id=:id AND person_id=:p"
                ),
                {"id": int(private["id"]), "p": person},
            )
            assert left == (not guarded)
            assert c.scalar(
                text(
                    "SELECT response_summary->>'id' FROM core.request_receipt WHERE workspace_id=:w AND actor_user_id=:u AND request_key=:key"
                ),
                {"w": co["companyId"], "u": uid, "key": cache_key},
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
                target_before = chat_state(target) if guarded else None
                owner_read = api(control, co, private_path + "/messages", method="GET")
                shared_read = api(subject, co, shared_path + "/messages", method="GET")
                shared_send = api(
                    subject,
                    co,
                    shared_path + "/messages",
                    {"body": "합성 복원 후 정상 메시지", "clientKey": str(uuid4())},
                )
                seq = initial["seq"] if guarded else data(shared_send)["seq"]
                shared_cursor = api(subject, co, shared_path + "/read", {"seq": seq})
                if guarded:
                    for response in (
                        owner_read,
                        shared_read,
                        shared_send,
                        shared_cursor,
                    ):
                        denied(response, 403, "GW_IDENTITY_REQUIRED")
                else:
                    assert data(owner_read)["messages"][0]["body"] == MARKER
                    data(shared_read)
                    data(shared_cursor)
                    target_before = chat_state(target)
                with target.connect() as c:
                    assert c.scalar(
                        text(
                            "SELECT response_summary->>'id' FROM core.request_receipt WHERE workspace_id=:w AND actor_user_id=:u AND request_key=:key"
                        ),
                        {"w": co["companyId"], "u": uid, "key": cache_key},
                    ) == str(cached["id"])
                read = api(subject, co, private_path + "/messages", method="GET")
                cursor = subject.get(
                    "/api/v1/gw/" + private_path + "/messages",
                    params={"companyId": co["companyId"], "after": cached["seq"]},
                )
                write = api(
                    subject,
                    co,
                    private_path + "/messages",
                    {"body": "거부할 합성 메시지", "clientKey": str(uuid4())},
                )
                replay = api(
                    subject, co, private_path + "/messages", cache_body, key=cache_key
                )
                mark_read = api(
                    subject, co, private_path + "/read", {"seq": cached["seq"]}
                )
                status, code = CHAT_CASES[case]
                for response in (read, cursor, write, replay, mark_read):
                    denied(response, status, code)
                listing = api(subject, co, "channels", method="GET")
                if guarded:
                    denied(listing, 403, "GW_IDENTITY_REQUIRED")
                else:
                    rows = data(listing)
                    assert str(private["id"]) not in {str(row["id"]) for row in rows}
                    assert str(shared["id"]) in {str(row["id"]) for row in rows}
                denied_responses = (read, cursor, write, replay, mark_read, listing)
                if guarded:
                    denied_responses += (
                        owner_read,
                        shared_read,
                        shared_send,
                        shared_cursor,
                    )
                assert all(MARKER not in response.text for response in denied_responses)
                assert all(
                    "data" not in response.json()
                    for response in denied_responses
                    if response.status_code >= 400
                )
                assert chat_state(target) == target_before
            reset_engine()
        assert closed(target) and source_state(engine) == before
        evidence = (folders["reports"] / "evidence.json").read_bytes()
        observation = RestoredChatDenialObservation.model_validate(
            {
                "version": 4,
                "scope": "SYNTHETIC_CLOSED_RESTORE_CHAT_MEMBERSHIP",
                "case": case,
                "runId": os.environ.get("FS_GW_SYNTHETIC_RUN_ID", str(uuid4())),
                "codeRevision": os.environ.get(
                    "FS_GW_SYNTHETIC_CODE_REVISION", "abcdef012345"
                ),
                "dbRevision": json.loads(evidence)["envelope"]["dbRevision"],
                "startedAt": started,
                "finishedAt": datetime.now(UTC).isoformat(),
                "restoreDigest": hashlib.sha256(evidence).hexdigest(),
                "status": status,
                "errorCode": code,
                "writeStatus": write.status_code,
                "writeErrorCode": code,
                "replayStatus": replay.status_code,
                "replayCode": code,
                "cursorStatus": cursor.status_code,
                "cursorCode": code,
                "readStatus": mark_read.status_code,
                "readCode": code,
                "listStatus": listing.status_code,
                "listCode": code if guarded else None,
                "listingMode": "IDENTITY_DENIED" if guarded else "FILTERED",
                "baselineReadConfirmed": True,
                "baselineSendConfirmed": True,
                "baselineCursorConfirmed": True,
                "restoredOwnerReadConfirmed": not guarded,
                "restoredSharedReadConfirmed": not guarded,
                "restoredSharedSendConfirmed": not guarded,
                "restoredSharedCursorConfirmed": not guarded,
                "quarantineObserved": guarded,
                "companyHold": hold,
                "contentExposed": False,
                "deniedChatStateUnchanged": True,
                "membershipReplayed": False,
                "cachedReceiptRetained": True,
                "controlMfaAuthenticated": True,
                "subjectMfaAuthenticated": True,
                "closedBefore": True,
                "closedAfter": True,
                "sourceUnchanged": True,
                "sourceComparisonScope": "SELECTED_AUTHORIZATION_CHAT_AND_RECEIPT_TABLES",
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
