"""Closed restore: calendar owner/attendee ACL, cached replay and conservative guard."""

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
from fs.gw.restored_denial import (
    CALENDAR_CASES,
    PROPERTY,
    RestoredCalendarDenialObservation,
)
from fs.main import create_app

MARKER = "CALENDAR-PRIVATE-64"


def calendar_state(engine):
    with engine.connect() as c:
        return c.scalar(
            text("""SELECT encode(sha256(convert_to(jsonb_build_array(
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.calendar_event t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.event_attendee t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM core.request_receipt t)
            )::text,'UTF8')),'hex')""")
        )


def source_state(engine):
    return fingerprint(engine), calendar_state(engine)


def data(response, expected=200):
    assert response.status_code == expected
    return response.json()["data"]


def event_body(title, attendees):
    return {
        "title": title,
        "scope": "PERSONAL",
        "startsAt": "2026-11-02T01:00:00Z",
        "endsAt": "2026-11-02T02:00:00Z",
        "attendeeIds": [str(p) for p in attendees],
    }


def edit(client, co, event, attendees):
    return api(
        client,
        co,
        f"calendar/{event['id']}",
        {**event_body(event["title"], attendees), "expectedVersion": event["version"]},
        method="PATCH",
    )


@pytest.mark.parametrize("case", list(CALENDAR_CASES))
def test_closed_restore_calendar_authorization(
    company_env, backup_env, monkeypatch, record_property, case
):
    engine, co, admin, staff = company_env
    module, config, folders, password = backup_env
    started = datetime.now(UTC).isoformat()
    guarded = case == "CALENDAR_ATTENDEE_GUARD"
    aid = context(engine, admin).user_id
    uid = context(engine, staff).user_id
    with engine.connect() as c:
        person = c.scalar(
            text(
                "SELECT person_id FROM gw.person_identity_binding WHERE workspace_id=:w AND user_id=:u AND state='ACTIVE'"
            ),
            {"w": co["companyId"], "u": uid},
        )
    private = data(api(admin, co, "calendar", event_body(MARKER, [person])), 201)
    shared = data(
        api(admin, co, "calendar", event_body("CALENDAR-CONTROL-64", [person])), 201
    )
    private_path = f"calendar/{private['id']}"
    shared_path = f"calendar/{shared['id']}"
    assert data(api(staff, co, private_path, method="GET"))["title"] == MARKER
    cache_key = str(uuid4())
    cache_body = {"expectedVersion": private["version"], "response": "ACCEPTED"}
    cached = data(api(staff, co, private_path + "/respond", cache_body, key=cache_key))
    assert cached["id"] == private["id"]
    assert any(
        str(a["personId"]) == str(person) and a["response"] == "ACCEPTED"
        for a in cached["attendees"]
    )
    shared = data(edit(admin, co, shared, [person]))
    assert shared["allDay"] is False and shared["location"] is None
    data(api(staff, co, shared_path, method="GET"))
    data(
        api(
            staff,
            co,
            shared_path + "/respond",
            {"expectedVersion": shared["version"], "response": "ACCEPTED"},
        )
    )
    if not guarded:
        private = data(edit(admin, co, private, []))
        denied(api(staff, co, private_path, method="GET"), 404, "NOT_FOUND")
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
    artifact = folders["backups"] / "calendar.enc"
    module.backup(
        url=source,
        company_id=co["companyId"],
        output=artifact,
        evidence=folders["backups"] / "proof.json",
        config=config,
    )
    if guarded:
        private = data(edit(admin, co, private, []))
    checkpoint = folders["checkpoints"] / "calendar.enc"
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
            present = c.scalar(
                text(
                    "SELECT count(*) FROM gw.event_attendee WHERE event_id=:id AND person_id=:p"
                ),
                {"id": int(private["id"]), "p": person},
            )
            assert bool(present) == guarded
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
                target_before = calendar_state(target) if guarded else None
                owner_read = api(control, co, private_path, method="GET")
                owner_edit = edit(control, co, shared, [person])
                attendee_read = api(subject, co, shared_path, method="GET")
                current = shared if guarded else data(owner_edit)
                attendee_respond = api(
                    subject,
                    co,
                    shared_path + "/respond",
                    {"expectedVersion": current["version"], "response": "DECLINED"},
                )
                if guarded:
                    for response in (
                        owner_read,
                        owner_edit,
                        attendee_read,
                        attendee_respond,
                    ):
                        denied(response, 403, "GW_IDENTITY_REQUIRED")
                else:
                    assert data(owner_read)["title"] == MARKER
                    data(attendee_read)
                    responded = data(attendee_respond)
                    assert any(
                        str(a["personId"]) == str(person)
                        and a["response"] == "DECLINED"
                        for a in responded["attendees"]
                    )
                    target_before = calendar_state(target)
                with target.connect() as c:
                    assert c.scalar(
                        text(
                            "SELECT response_summary->>'id' FROM core.request_receipt WHERE workspace_id=:w AND actor_user_id=:u AND request_key=:key"
                        ),
                        {"w": co["companyId"], "u": uid, "key": cache_key},
                    ) == str(cached["id"])
                read = api(subject, co, private_path, method="GET")
                respond = api(
                    subject,
                    co,
                    private_path + "/respond",
                    {"expectedVersion": private["version"], "response": "DECLINED"},
                )
                replay = api(
                    subject, co, private_path + "/respond", cache_body, key=cache_key
                )
                write = edit(subject, co, private, [])
                cancel = api(
                    subject,
                    co,
                    private_path + "/cancel",
                    {"expectedVersion": private["version"]},
                )
                attendee_edit = edit(subject, co, current, [person])
                attendee_cancel = api(
                    subject,
                    co,
                    shared_path + "/cancel",
                    {"expectedVersion": current["version"]},
                )
                status, code = CALENDAR_CASES[case]
                for response in (
                    read,
                    respond,
                    replay,
                    write,
                    cancel,
                    attendee_edit,
                    attendee_cancel,
                ):
                    denied(response, status, code)
                listing = subject.get(
                    "/api/v1/gw/calendar",
                    params={
                        "companyId": co["companyId"],
                        "startsAt": "2026-11-01T00:00:00Z",
                        "endsAt": "2026-11-03T00:00:00Z",
                    },
                )
                if guarded:
                    denied(listing, 403, "GW_IDENTITY_REQUIRED")
                else:
                    rows = data(listing)
                    assert str(private["id"]) not in {str(row["id"]) for row in rows}
                    assert str(shared["id"]) in {str(row["id"]) for row in rows}
                responses = (
                    read,
                    respond,
                    replay,
                    write,
                    cancel,
                    attendee_edit,
                    attendee_cancel,
                    listing,
                )
                if guarded:
                    responses += (
                        owner_read,
                        owner_edit,
                        attendee_read,
                        attendee_respond,
                    )
                assert all(MARKER not in response.text for response in responses)
                assert all(
                    "data" not in response.json()
                    for response in responses
                    if response.status_code >= 400
                )
                assert calendar_state(target) == target_before
            reset_engine()
        assert closed(target) and source_state(engine) == before
        evidence = (folders["reports"] / "evidence.json").read_bytes()
        observation = RestoredCalendarDenialObservation.model_validate(
            {
                "version": 5,
                "scope": "SYNTHETIC_CLOSED_RESTORE_CALENDAR_AUTHORIZATION",
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
                "respondStatus": respond.status_code,
                "respondCode": code,
                "replayStatus": replay.status_code,
                "replayCode": code,
                "editStatus": write.status_code,
                "editCode": code,
                "cancelStatus": cancel.status_code,
                "cancelCode": code,
                "attendeeEditStatus": attendee_edit.status_code,
                "attendeeEditCode": code,
                "attendeeCancelStatus": attendee_cancel.status_code,
                "attendeeCancelCode": code,
                "listStatus": listing.status_code,
                "listCode": code if guarded else None,
                "listingMode": "IDENTITY_DENIED" if guarded else "FILTERED",
                "baselineReadConfirmed": True,
                "baselineRespondConfirmed": True,
                "baselineOwnerEditConfirmed": True,
                "restoredOwnerReadConfirmed": not guarded,
                "restoredOwnerEditConfirmed": not guarded,
                "restoredAttendeeReadConfirmed": not guarded,
                "restoredAttendeeRespondConfirmed": not guarded,
                "quarantineObserved": guarded,
                "companyHold": hold,
                "contentExposed": False,
                "deniedCalendarStateUnchanged": True,
                "attendeesReplayed": False,
                "cachedReceiptRetained": True,
                "controlMfaAuthenticated": True,
                "subjectMfaAuthenticated": True,
                "closedBefore": True,
                "closedAfter": True,
                "sourceUnchanged": True,
                "sourceComparisonScope": "SELECTED_AUTHORIZATION_CALENDAR_AND_RECEIPT_TABLES",
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
