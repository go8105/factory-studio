"""Actual synthetic ten-person MFA and company workflows in a newly owned DB."""

# ruff: noqa: F401,F811
import hashlib
import json
import os
from datetime import UTC, datetime
from uuid import uuid4

import pyotp
from cryptography.fernet import Fernet
from sqlalchemy import text
from test_gw_company_acceptance import ten_people
from test_gw_company_work import api
from test_gw_wms_merge import isolated_database

from fs.gw.acceptance_business import PROPERTY, SyntheticBusinessObservation
from fs.gw.acceptance_preflight import collect
from fs.gw.operating_contract import OperatingPolicy, canonical


def data(response, status=None):
    # Never attach enrollment/login response bodies (which contain secrets) to errors.
    assert response.status_code in ({200, 201} if status is None else {status})
    return response.json()["data"]


def test_ten_person_mfa_preflight_and_representative_business(
    ten_people, monkeypatch, record_property
):
    engine, co, clients, people, _, passwords = ten_people
    monkeypatch.setenv("FS_SECURITY_MODE", "TEAM_TEST")
    monkeypatch.setenv(
        "FS_SECURITY_KEYS", json.dumps({"synthetic": Fernet.generate_key().decode()})
    )
    monkeypatch.setenv("FS_SECURITY_KEY_ID", "synthetic")
    admin = clients[0]
    # Only the newly created synthetic fixture account is renamed, never a live account.
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.app_user SET login_id='admin' WHERE login_id='synthetic-owner'"
            )
        )
    started = datetime.now(UTC).isoformat()
    for i, client in enumerate(clients):
        enrollment = data(
            client.post(
                "/api/v1/core/security/enrollment/start",
                json={"password": passwords[i]},
                headers={"X-CSRF-Token": client.csrf},
            )
        )
        data(
            client.post(
                "/api/v1/core/security/enrollment/confirm",
                json={
                    "factorId": enrollment["factorId"],
                    "code": pyotp.TOTP(enrollment["setupKey"]).now(),
                },
                headers={"X-CSRF-Token": client.csrf},
            )
        )
        assert client.get("/api/v1/core/sessions/current").status_code == 401
        challenge = data(
            client.post(
                "/api/v1/core/sessions",
                json={
                    "loginId": "admin" if i == 0 else f"synthetic-staff-{i}",
                    "password": passwords[i],
                },
                headers={"Idempotency-Key": str(uuid4())},
            ),
            202,
        )
        # The next unused step is inside the product's normal +/-1 TOTP window.
        # No factor/session rows, verifier clocks or production settings are patched.
        with engine.connect() as c:
            now = c.scalar(text("SELECT clock_timestamp()"))
        verified = data(
            client.post(
                "/api/v1/core/security/login/verify",
                json={
                    "code": pyotp.TOTP(enrollment["setupKey"]).at(
                        (int(now.timestamp()) // 30 + 1) * 30
                    )
                },
                headers={"X-CSRF-Token": challenge["challengeCsrfToken"]},
            ),
            201,
        )
        client.csrf = verified["csrfToken"]
        assert verified.get("recoveryOnly", False) is False
        assert data(client.get("/api/v1/core/security/me"))["mfaRegistered"] is True
        me = data(api(client, co, "me", method="GET"))
        assert me["businessReady"] and me["bindingStatus"] == "ACTIVE"
        assert ("SECURITY_ADMIN" in me["roles"]) == (i == 0)
    responsible = data(api(admin, co, "me", method="GET"))["person"]["id"]
    policy = OperatingPolicy(
        responsiblePersonId=responsible, reason="합성 10인 업무 실행 기준"
    )
    data(
        api(
            admin,
            co,
            "operating-policies",
            {"expectedVersion": 0, "policy": policy.model_dump(by_alias=True)},
        )
    )
    code = os.environ.get("FS_GW_SYNTHETIC_CODE_REVISION", "abcdef012345")
    context, preflight = collect(engine, company_id=co["companyId"], code_revision=code)
    assert preflight["result"] == "PARTIAL"
    assert (
        preflight["counts"]["connectedPeople"] == preflight["counts"]["mfaPeople"] == 10
    )
    route = data(
        api(
            admin,
            co,
            "routes",
            {
                "code": "SYN-TEN",
                "name": "합성 관리자 결재",
                "steps": [
                    {"personId": responsible, "seq": 1, "participantRole": "APPROVER"}
                ],
            },
        )
    )
    channel = data(
        api(
            admin,
            co,
            "channels",
            {
                "name": "합성 10인 실행",
                "channelKind": "GROUP",
                "memberIds": [p["id"] for p in people if p["id"] != responsible],
            },
        )
    )
    event = data(
        api(
            admin,
            co,
            "calendar",
            {
                "title": "합성 10인 일정",
                "scope": "PERSONAL",
                "startsAt": "2026-10-21T09:00:00+09:00",
                "endsAt": "2026-10-21T10:00:00+09:00",
                "attendeeIds": [p["id"] for p in people if p["id"] != responsible],
            },
        )
    )
    for i, staff in enumerate(clients[1:], 1):
        assert api(staff, co, "operating-evidence", method="GET").status_code == 403
        doc = data(
            api(
                staff,
                co,
                "documents",
                {
                    "routeId": route["id"],
                    "kind": "GENERAL",
                    "title": f"합성 기안 {i}",
                    "body": "합성 업무 원문",
                },
            )
        )
        other = clients[1 + i % 9]
        assert api(other, co, f"documents/{doc['id']}", method="GET").status_code == 404
        submitted = data(
            api(
                staff,
                co,
                f"documents/{doc['id']}/submit",
                {"expectedVersion": doc["version"]},
            )
        )
        approved = data(
            api(
                admin,
                co,
                f"documents/{doc['id']}/approve",
                {"expectedVersion": submitted["version"]},
            )
        )
        assert approved["status"] == "APPROVED"
        post = data(
            api(
                staff,
                co,
                "posts",
                {
                    "boardKind": "FREE",
                    "visibility": "WORKSPACE",
                    "title": f"합성 게시 {i}",
                    "body": "합성 게시 원문",
                },
            )
        )
        published = data(
            api(
                staff,
                co,
                f"posts/{post['id']}/publish",
                {"expectedVersion": post["version"]},
            )
        )
        assert published["status"] == "PUBLISHED"
        assert (
            data(api(other, co, f"posts/{post['id']}", method="GET"))["status"]
            == "PUBLISHED"
        )
        comment = data(
            api(
                staff,
                co,
                "comments",
                {
                    "targetKind": "DOCUMENT",
                    "targetId": doc["id"],
                    "body": "합성 업무 댓글",
                },
            )
        )
        assert comment["id"]
        responded = data(
            api(
                staff,
                co,
                f"calendar/{event['id']}/respond",
                {"expectedVersion": event["version"], "response": "ACCEPTED"},
            )
        )
        assert any(a["response"] == "ACCEPTED" for a in responded["attendees"])
        # Attendee response may advance the event version: always use the latest response.
        event = responded
        notices = data(api(staff, co, "notifications", method="GET"))
        assert notices
        read_notice = data(api(staff, co, f"notifications/{notices[0]['id']}/read", {}))
        assert read_notice["readAt"] is not None
    assert len(event["attendees"]) == 9
    assert all(a["response"] == "ACCEPTED" for a in event["attendees"])
    message_ids = set()
    for client in clients:
        key = str(uuid4())
        body = {"body": "합성 참여 메시지", "clientKey": str(uuid4())}
        message = data(
            api(client, co, f"channels/{channel['id']}/messages", body, key=key)
        )
        assert (
            data(api(client, co, f"channels/{channel['id']}/messages", body, key=key))[
                "id"
            ]
            == message["id"]
        )
        message_ids.add(message["id"])
    messages = data(api(admin, co, f"channels/{channel['id']}/messages", method="GET"))[
        "messages"
    ]
    assert len(message_ids) == len(messages) == len({m["seq"] for m in messages}) == 10
    final_context, final = collect(
        engine, company_id=co["companyId"], code_revision=code
    )
    assert final["result"] == "PARTIAL"
    operation = data(api(admin, co, "operations", method="GET"))
    assert operation["ready"] is False
    observation = SyntheticBusinessObservation.model_validate(
        {
            "version": 1,
            "scope": "SYNTHETIC_TEN_PERSON_ASGI",
            "runId": os.environ.get("FS_GW_SYNTHETIC_RUN_ID", str(uuid4())),
            "contextDigest": hashlib.sha256(canonical(context)).hexdigest(),
            "finalContextDigest": hashlib.sha256(canonical(final_context)).hexdigest(),
            "policyDigest": preflight["policyDigest"],
            "workspaceId": str(context["workspaceId"]),
            "generationId": str(context["generationId"]),
            "codeRevision": code,
            "dbRevision": context["dbRevision"],
            "startedAt": started,
            "finishedAt": datetime.now(UTC).isoformat(),
            "preflightResult": preflight["result"],
            "finalPreflightResult": final["result"],
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
    )
    record_property(PROPERTY, canonical(observation.model_dump(by_alias=True)).decode())
