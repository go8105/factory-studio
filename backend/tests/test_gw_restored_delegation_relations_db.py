"""Real source relation/money checks and closed restore with direct rights retained."""

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
from test_gw_restored_denial_db import closed, mfa
from test_gw_restored_object_db import denied
from test_hr_work import company_env

from fs.common.db import reset_engine
from fs.core.security.config import security_settings
from fs.gw import company, policy
from fs.gw import service as gw
from fs.gw.operating_contract import canonical
from fs.gw.restored_denial import (
    DELEGATION_RELATION_CASES,
    PROPERTY,
    RestoredDelegationRelationObservation,
)
from fs.main import create_app

MARKER = "DELEGATION-RELATION-67"


def route(client, co, code, people):
    return data(
        api(
            client,
            co,
            "routes",
            {
                "code": code,
                "name": "합성 관계 경계",
                "steps": [
                    {
                        "personId": str(person),
                        "seq": i + 1,
                        "participantRole": "APPROVER",
                    }
                    for i, person in enumerate(people)
                ],
            },
        ),
        201,
    )["id"]


def submitted(drafter, co, route_id, title, amount="100", currency="KRW"):
    doc = data(
        api(
            drafter,
            co,
            "documents",
            {
                "routeId": str(route_id),
                "kind": "GENERAL",
                "title": title,
                "body": title,
                "amount": amount,
                "currency": currency,
            },
        ),
        201,
    )
    return data(
        api(
            drafter,
            co,
            f"documents/{doc['id']}/submit",
            {"expectedVersion": doc["version"]},
        )
    )


def scope(client, co, doc, direct):
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
        {"expectedVersion": doc["version"], "reason": "합성 관계 경계 거부"},
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


@pytest.mark.parametrize("case", list(DELEGATION_RELATION_CASES))
def test_source_relation_money_and_restored_floor(
    company_env, backup_env, third, fourth, monkeypatch, record_property, case
):
    engine, co, admin, staff = company_env
    module, config, folders, password = backup_env
    started = datetime.now(UTC).isoformat()
    connect_third(company_env, third)
    other_client, other_person = fourth
    direct = case == "DELEGATION_DIRECT_ASSIGNMENT"
    chain = case == "DELEGATION_CHAIN_INPUT"
    original_uid, delegate_uid = (
        context(engine, staff).user_id,
        context(engine, admin).user_id,
    )
    subject_uid = context(engine, other_client).user_id if chain else delegate_uid
    control_uid = original_uid
    source_subject = other_client if chain else admin
    subject_login = "company-fourth" if chain else "hugh-admin"
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
        now = c.scalar(text("SELECT clock_timestamp()"))
    original, delegate = people[original_uid], people[delegate_uid]
    main_route = route(admin, co, "REL-ORIGINAL", [original])
    direct_route = route(admin, co, "REL-DIRECT", [delegate])
    target_route = (
        route(admin, co, "REL-CONFLICT", [original, delegate]) if direct else main_route
    )
    history_doc = submitted(third, co, main_route, "REL-HISTORY-67")
    control_doc = submitted(third, co, main_route, "REL-CONTROL-67")
    direct_pending = submitted(third, co, direct_route, "REL-DIRECT-CONTROL-67")
    amount, currency = (
        ("100", "USD")
        if case == "DELEGATION_FOREIGN_CURRENCY"
        else (None, None)
        if case == "DELEGATION_MISSING_AMOUNT"
        else ("100", "KRW")
    )
    target_doc = submitted(third, co, target_route, MARKER, amount, currency)
    grant_body = {
        "delegatePersonId": str(delegate),
        "startsAt": (now - timedelta(hours=1)).isoformat(),
        "endsAt": (now + timedelta(hours=2)).isoformat(),
        "documentKind": "GENERAL",
        "reason": "합성 관계/통화 경계",
    }
    if case in {"DELEGATION_FOREIGN_CURRENCY", "DELEGATION_MISSING_AMOUNT"}:
        grant_body["maxAmount"] = "100"
    grant = data(api(staff, co, "delegations", grant_body), 201)
    if amount is None:
        assert target_doc["amount"] is None and target_doc["currency"] is None
    else:
        assert (
            Decimal(str(target_doc["amount"])) == Decimal(100)
            and target_doc["currency"] == currency
        )
    limited = case in {"DELEGATION_FOREIGN_CURRENCY", "DELEGATION_MISSING_AMOUNT"}
    assert (
        (Decimal(str(grant["maxAmount"])) == Decimal(100))
        if limited
        else grant["maxAmount"] is None
    )
    assert (
        len(
            data(api(admin, co, f"documents/{control_doc['id']}", method="GET"))[
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
                f"documents/{history_doc['id']}/approve",
                {"expectedVersion": history_doc["version"]},
            )
        ),
        delegate,
        original,
    )
    if direct:
        direct_done = submitted(third, co, direct_route, "REL-DIRECT-DONE-67")
        actor_history(
            data(
                api(
                    admin,
                    co,
                    f"documents/{direct_done['id']}/approve",
                    {"expectedVersion": direct_done["version"]},
                )
            ),
            delegate,
            None,
        )
    chain_status = chain_code = None
    if chain:
        before_chain = delegation_state(engine)
        response = api(
            admin,
            co,
            "delegations",
            {**grant_body, "delegatePersonId": str(other_person)},
        )
        denied(response, 409, "PRECONDITION_NOT_MET")
        assert (
            response.json()["error"]["details"]["reason"]
            == "DELEGATION_OVERLAP_OR_CHAIN"
        )
        assert delegation_state(engine) == before_chain
        chain_status, chain_code = (
            response.status_code,
            response.json()["error"]["code"],
        )
    assert len(eligible(engine, co, admin, control_doc)) == 1
    with company.transaction(context(engine, staff), co["companyId"]) as (c, ctx, _):
        assert (
            c.scalar(
                text(
                    "SELECT count(*) FROM gw.delegation WHERE workspace_id=:w AND generation_id=:g AND revoked_at IS NULL"
                ),
                {"w": ctx.workspace_id, "g": ctx.generation_id},
            )
            == 1
        )
        assert c.scalar(
            text(
                "SELECT revoked_at IS NULL FROM gw.delegation WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {"w": ctx.workspace_id, "g": ctx.generation_id, "id": int(grant["id"])},
        )
    assert eligible(engine, co, source_subject, target_doc) == []
    before_denial = delegation_state(engine)
    source_responses = scope(source_subject, co, target_doc, direct)
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
                    subject_client,
                    target,
                    subject_login,
                    password,
                    secrets[subject_uid],
                )
                original_read = data(
                    api(
                        original_client,
                        co,
                        f"documents/{target_doc['id']}",
                        method="GET",
                    )
                )
                assert len(original_read["actionSteps"]) == 1
                approved = data(
                    api(
                        original_client,
                        co,
                        f"documents/{control_doc['id']}/approve",
                        {"expectedVersion": control_doc["version"]},
                    )
                )
                actor_history(approved, original, None)
                if direct:
                    actor_history(
                        data(
                            api(
                                subject_client,
                                co,
                                f"documents/{direct_pending['id']}/approve",
                                {"expectedVersion": direct_pending["version"]},
                            )
                        ),
                        delegate,
                        None,
                    )
                before_denial = delegation_state(target)
                responses = scope(subject_client, co, target_doc, direct)
                assert delegation_state(target) == before_denial
            reset_engine()
        assert closed(target) and source_state(engine) == before
        evidence = (folders["reports"] / "evidence.json").read_bytes()
        _action_status, action_code = DELEGATION_RELATION_CASES[case]
        observation = RestoredDelegationRelationObservation.model_validate(
            {
                "version": 8,
                "scope": "SYNTHETIC_SOURCE_RELATION_MONEY_AND_CLOSED_RESTORE_FLOOR",
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
                "sourceReadStatus": source_responses[0].status_code,
                "sourceReadCode": None if direct else "NOT_FOUND",
                "sourceApproveStatus": source_responses[1].status_code,
                "sourceRejectStatus": source_responses[2].status_code,
                "sourceActionCode": action_code,
                "sourceActionReason": "NOT_CURRENT_STEP" if direct else None,
                "sourceTargetAmount": "100" if amount is not None else None,
                "sourceTargetCurrency": currency,
                "sourceLimitedGrant": limited,
                "sourceTargetListed": direct,
                "sourceTargetSearchable": direct,
                "sourcePolicyEmpty": True,
                "sourceDenialStateUnchanged": True,
                "baselineDelegatedRead": True,
                "baselineDelegatedApproval": True,
                "sourceRemainingValidGrant": True,
                "chainInputStatus": chain_status,
                "chainInputCode": chain_code,
                "chainInputReason": "DELEGATION_OVERLAP_OR_CHAIN" if chain else None,
                "chainRejectedStateUnchanged": chain,
                "sourceDirectApproval": direct,
                "restoredOriginalRead": True,
                "restoredOriginalApproval": True,
                "restoredSubjectDirectApproval": direct,
                "restoredReadStatus": responses[0].status_code,
                "restoredReadCode": None if direct else "NOT_FOUND",
                "restoredApproveStatus": responses[1].status_code,
                "restoredRejectStatus": responses[2].status_code,
                "restoredActionCode": action_code,
                "restoredActionReason": "NOT_CURRENT_STEP" if direct else None,
                "restoredTargetListed": direct,
                "restoredTargetSearchable": direct,
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
