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
from fs.common.db import reset_engine
from fs.core.security.config import security_settings
from fs.gw import company, policy
from fs.gw import service as gw
from fs.gw.operating_contract import canonical
from fs.gw.restored_denial import (
    DELEGATION_BOUND_CASES,
    PROPERTY,
    RestoredDelegationBoundaryObservation,
)
from fs.main import create_app
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_gw_backup import backup_env
from test_gw_company import context
from test_gw_company_work import api, call_work, connect_third, document, third
from test_gw_restored_delegation_db import (
    actor_history,
    data,
    delegation_state,
    source_state,
)
from test_gw_restored_denial_db import closed, mfa
from test_gw_restored_object_db import denied
from test_hr_users import manage
from test_hr_work import company_env

MARKER = "DELEGATION-BOUND-66"


@pytest.fixture
def fourth(company_env, backup_env):
    engine, co, admin, _ = company_env
    password = backup_env[3]
    response = manage(
        admin,
        co,
        body={
            "loginId": "company-fourth",
            "password": password,
            "name": "네번째 합성 직원",
            "employeeCode": "HUGH-004",
            "annualDays": 15,
            "role": "STAFF",
        },
    )
    assert response.status_code == 200
    with TestClient(create_app()) as client:
        login = client.post(
            "/api/v1/core/sessions",
            json={"loginId": "company-fourth", "password": password},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert login.status_code == 201
        client.csrf = login.json()["data"]["csrfToken"]
        preview = data(api(admin, co, "company-hr-preview", method="GET"))
        data(
            api(
                admin,
                co,
                "company-hr-import",
                {
                    "previewDigest": preview["digest"],
                    "employeeCodes": ["HUGH-004"],
                    "reason": "합성 단계 대조 가져오기",
                },
            )
        )
        with engine.connect() as c:
            person = c.scalar(
                text(
                    "SELECT id FROM gw.person WHERE workspace_id=:w AND hr_employee_code='HUGH-004'"
                ),
                {"w": co["companyId"]},
            )
        binding = data(
            api(
                admin,
                co,
                "identity-bindings",
                {
                    "personId": str(person),
                    "userId": str(context(engine, client).user_id),
                    "reason": "합성 단계 대조 연결",
                },
            )
        )
        data(
            api(
                client,
                co,
                "me/binding/accept",
                {"bindingId": binding["id"], "expectedVersion": binding["version"]},
            )
        )
        yield client, person


def submitted(env, drafter, route, title, amount="100"):
    doc = call_work(
        env,
        drafter,
        "documents",
        None,
        "create",
        {
            "route_id": int(route),
            "kind": "GENERAL",
            "title": title,
            "body": title,
            "amount": amount,
            "currency": "KRW",
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


def eligible(engine, co, actor, doc, t=None):
    with company.transaction(context(engine, actor), co["companyId"]) as (c, ctx, _):
        p, _ = company.principal(c, ctx)
        return policy.eligible(
            c,
            ctx,
            gw.one(c, ctx, "approval_document", int(doc["id"])),
            p,
            t=t,
            company_mode=True,
        )


def deny_current(client, co, doc):
    path = f"documents/{doc['id']}"
    responses = [
        api(client, co, path, method="GET"),
        api(client, co, path + "/approve", {"expectedVersion": doc["version"]}),
        api(
            client,
            co,
            path + "/reject",
            {"expectedVersion": doc["version"], "reason": "합성 거부 경계 대조"},
        ),
    ]
    for r in responses:
        denied(r, 404, "NOT_FOUND")
        assert "data" not in r.json() and MARKER not in r.text
    listing = data(api(client, co, "documents", method="GET"))["rows"]
    search = data(
        client.get(
            "/api/v1/gw/documents",
            params={"companyId": co["companyId"], "search": MARKER},
        )
    )["rows"]
    assert str(doc["id"]) not in {str(row["id"]) for row in listing}
    assert MARKER not in json.dumps(listing, ensure_ascii=False) and search == []
    return responses


@pytest.mark.parametrize("case", list(DELEGATION_BOUND_CASES))
def test_source_bounds_and_restored_delegation_floor(
    company_env, backup_env, third, fourth, monkeypatch, record_property, case
):
    engine, co, admin, staff = company_env
    module, config, folders, password = backup_env
    started = datetime.now(UTC).isoformat()
    aid, uid = context(engine, admin).user_id, context(engine, staff).user_id
    connect_third(company_env, third)
    stage_client, stage_person = fourth
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
    original, delegate = people[uid], people[aid]
    template = document(company_env, original)
    history_doc = submitted(company_env, third, template["routeId"], "BOUND-HISTORY-66")
    control_doc = submitted(company_env, third, template["routeId"], "BOUND-CONTROL-66")
    route_id = template["routeId"]
    if case == "DELEGATION_CURRENT_STAGE":
        route_id = call_work(
            company_env,
            admin,
            "routes",
            None,
            "create",
            {
                "code": "BOUND-STAGE",
                "name": "합성 다음 단계",
                "steps": [
                    {
                        "person_id": stage_person,
                        "seq": 1,
                        "participant_role": "APPROVER",
                    },
                    {"person_id": original, "seq": 2, "participant_role": "APPROVER"},
                ],
            },
        )["id"]
    target_doc = submitted(
        company_env,
        third,
        route_id,
        MARKER,
        "101" if case == "DELEGATION_AMOUNT" else "100",
    )
    grant_body = {
        "delegatePersonId": str(delegate),
        "startsAt": (now - timedelta(hours=1)).isoformat(),
        "endsAt": (now + timedelta(hours=2)).isoformat(),
        "documentKind": "GENERAL",
        "reason": "합성 위임 범위 대조",
    }
    if case == "DELEGATION_AMOUNT":
        grant_body["maxAmount"] = "100"
    baseline_grant = data(api(staff, co, "delegations", grant_body), 201)
    assert (
        len(
            data(api(admin, co, f"documents/{control_doc['id']}", method="GET"))[
                "actionSteps"
            ]
        )
        == 1
    )
    saved = data(
        api(
            admin,
            co,
            f"documents/{history_doc['id']}/approve",
            {"expectedVersion": history_doc["version"]},
        )
    )
    actor_history(saved, delegate, original)
    data(
        api(
            staff,
            co,
            f"delegations/{baseline_grant['id']}/revoke",
            {"expectedVersion": baseline_grant["version"]},
        )
    )
    window = "ACTIVE"
    if case == "DELEGATION_NOT_STARTED":
        grant_body.update(
            startsAt=(now + timedelta(hours=1)).isoformat(),
            endsAt=(now + timedelta(hours=2)).isoformat(),
        )
        window = "FUTURE"
    elif case == "DELEGATION_EXPIRED":
        grant_body.update(
            startsAt=(now - timedelta(hours=2)).isoformat(),
            endsAt=(now - timedelta(hours=1)).isoformat(),
        )
        window = "EXPIRED"
    kind_status = kind_code = None
    if case == "DELEGATION_KIND_INPUT":
        response = api(
            staff, co, "delegations", {**grant_body, "documentKind": "ERP_PURCHASE"}
        )
        denied(response, 400, "VALIDATION_FAILED")
        kind_status, kind_code, window = 400, "VALIDATION_FAILED", "NO_GRANT"
    else:
        grant = data(api(staff, co, "delegations", grant_body), 201)
    if case in {"DELEGATION_NOT_STARTED", "DELEGATION_EXPIRED"}:
        assert (
            len(
                eligible(
                    engine,
                    co,
                    admin,
                    target_doc,
                    datetime.fromisoformat(grant["startsAt"]),
                )
            )
            == 1
        )
        assert (
            eligible(
                engine, co, admin, target_doc, datetime.fromisoformat(grant["endsAt"])
            )
            == []
        )
    assert eligible(engine, co, admin, target_doc) == []
    denied_before = delegation_state(engine)
    source_responses = deny_current(admin, co, target_doc)
    assert delegation_state(engine) == denied_before
    if case == "DELEGATION_AMOUNT":
        assert (
            len(
                data(api(admin, co, f"documents/{control_doc['id']}", method="GET"))[
                    "actionSteps"
                ]
            )
            == 1
        )
    if case == "DELEGATION_CURRENT_STAGE":
        target_doc = data(
            api(
                stage_client,
                co,
                f"documents/{target_doc['id']}/approve",
                {"expectedVersion": target_doc["version"]},
            )
        )
        assert target_doc["status"] == "IN_REVIEW" and target_doc["currentStep"] == 2
        assert (
            len(
                data(api(admin, co, f"documents/{target_doc['id']}", method="GET"))[
                    "actionSteps"
                ]
            )
            == 1
        )
        assert len(eligible(engine, co, admin, target_doc)) == 1
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
                TestClient(create_app()) as delegate_client,
                TestClient(create_app()) as original_client,
            ):
                mfa(delegate_client, target, "hugh-admin", password, secrets[aid])
                mfa(original_client, target, "hugh-staff", password, secrets[uid])
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
                before_denial = delegation_state(target)
                responses = deny_current(delegate_client, co, target_doc)
                assert delegation_state(target) == before_denial
            reset_engine()
        assert closed(target) and source_state(engine) == before
        evidence = (folders["reports"] / "evidence.json").read_bytes()
        observation = RestoredDelegationBoundaryObservation.model_validate(
            {
                "version": 7,
                "scope": "SYNTHETIC_SOURCE_BOUNDS_AND_CLOSED_RESTORE_DELEGATION_FLOOR",
                "case": case,
                "runId": os.environ.get("FS_GW_SYNTHETIC_RUN_ID", str(uuid4())),
                "codeRevision": os.environ.get(
                    "FS_GW_SYNTHETIC_CODE_REVISION", "abcdef012345"
                ),
                "dbRevision": json.loads(evidence)["envelope"]["dbRevision"],
                "startedAt": started,
                "finishedAt": datetime.now(UTC).isoformat(),
                "restoreDigest": hashlib.sha256(evidence).hexdigest(),
                "status": responses[0].status_code,
                "errorCode": "NOT_FOUND",
                "sourceReadStatus": source_responses[0].status_code,
                "sourceApproveStatus": source_responses[1].status_code,
                "sourceRejectStatus": source_responses[2].status_code,
                "sourceErrorCode": "NOT_FOUND",
                "sourceListHidden": True,
                "sourceSearchHidden": True,
                "sourcePolicyEmpty": True,
                "sourceDenialStateUnchanged": True,
                "baselineDelegatedRead": True,
                "baselineDelegatedApproval": True,
                "sourceWindow": window,
                "timeEndpointPolicyConfirmed": case
                in {"DELEGATION_NOT_STARTED", "DELEGATION_EXPIRED"},
                "amountEqualityConfirmed": case == "DELEGATION_AMOUNT",
                "kindInputStatus": kind_status,
                "kindInputCode": kind_code,
                "stageAdvancedConfirmed": case == "DELEGATION_CURRENT_STAGE",
                "restoredOriginalRead": True,
                "restoredOriginalApproval": True,
                "restoredApproveStatus": responses[1].status_code,
                "restoredRejectStatus": responses[2].status_code,
                "restoredErrorCode": "NOT_FOUND",
                "restoredListHidden": True,
                "restoredSearchHidden": True,
                "restoredDelegationsRevoked": True,
                "restoredDenialStateUnchanged": True,
                "restoredBoundaryCause": "ALL_DELEGATIONS_REVOKED",
                "companyHold": hold,
                "contentExposed": False,
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
