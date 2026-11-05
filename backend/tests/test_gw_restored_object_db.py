"""Object ACL and a real second synthetic company on a closed restored database."""

# ruff: noqa:F401,F811
import hashlib
import json
import os
from datetime import UTC, datetime, time
from uuid import uuid4

import pyotp
import pytest
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.core.security.config import security_settings
from fs.gw.operating_contract import canonical
from fs.gw.restored_denial import (
    OBJECT_CASES,
    PROPERTY,
    RestoredObjectDenialObservation,
)
from fs.hr.work_setup import create_company
from fs.main import create_app
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_gw_backup import backup_env
from test_gw_company import context
from test_gw_company_work import api, call_work, document
from test_gw_restored_denial_db import closed, fingerprint, mfa
from test_hr_work import company_env


def object_state(engine):
    with engine.connect() as c:
        return c.scalar(
            text("""SELECT encode(sha256(convert_to(jsonb_build_array(
          (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.approval_document t),
          (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.document_reader t),
          (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.approval_step t),
          (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.approval_event t)
        )::text,'UTF8')),'hex')""")
        )


def source_state(engine):
    return (fingerprint(engine), object_state(engine))


def edit(client, company, doc):
    return api(
        client,
        company,
        f"documents/{doc['id']}",
        {
            "expectedVersion": doc["version"],
            "title": "합성 수정 대조",
            "body": "합성 원문 수정 대조",
        },
        method="PATCH",
    )


def denied(response, status, code):
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize("case", list(OBJECT_CASES))
def test_closed_restore_object_authorization(
    company_env, backup_env, monkeypatch, record_property, case
):
    engine, co, admin, staff = company_env
    module, config, folders, password = backup_env
    started = datetime.now(UTC).isoformat()
    aid = context(engine, admin).user_id
    uid = context(engine, staff).user_id
    with engine.connect() as c:
        reader = c.scalar(
            text(
                "SELECT person_id FROM gw.person_identity_binding WHERE workspace_id=:w AND user_id=:u AND state='ACTIVE'"
            ),
            {"w": co["companyId"], "u": uid},
        )
    control_doc = document(company_env, reader)
    extra_client = None
    secrets = {u: pyotp.random_base32() for u in (aid, uid)}
    target_company = co
    if case == "DOCUMENT_READER":
        doc = call_work(
            company_env,
            admin,
            "documents",
            None,
            "create",
            {
                "route_id": int(control_doc["routeId"]),
                "kind": "GENERAL",
                "title": "ACL-private-61",
                "body": "합성 대상 원문",
            },
        )
        with engine.begin() as c:
            c.execute(
                text(
                    "UPDATE gw.approval_document SET status='WITHDRAWN',submitted_at=clock_timestamp(),closed_at=clock_timestamp(),submission_order=serial WHERE id=:id"
                ),
                {"id": int(doc["id"])},
            )
            c.execute(
                text(
                    "UPDATE gw.approval_step SET status='SKIPPED' WHERE document_id=:id"
                ),
                {"id": int(doc["id"])},
            )
            c.execute(
                text(
                    "INSERT INTO gw.document_reader(workspace_id,generation_id,document_id,person_id,is_active,granted_by_user_id,reason) SELECT workspace_id,generation_id,id,:p,true,:u,'합성 참조자 준비' FROM gw.approval_document WHERE id=:id"
                ),
                {"id": int(doc["id"]), "p": reader, "u": aid},
            )
        assert api(staff, co, f"documents/{doc['id']}", method="GET").status_code == 200
    else:
        with engine.begin() as c:
            target_company = create_company(
                c,
                {
                    "companyName": "합성 격리 회사61",
                    "loginId": "synthetic-other-61",
                    "name": "합성 별도 소유자",
                    "password": password,
                    "employeeCode": "OTHER-001",
                    "workStart": time(9),
                    "dailyMinutes": 480,
                    "breakMinutes": 60,
                    "annualDays": 12,
                },
            )
        extra_client = TestClient(create_app())
        login = extra_client.post(
            "/api/v1/core/sessions",
            json={"loginId": "synthetic-other-61", "password": password},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert login.status_code == 201
        extra_client.csrf = login.json()["data"]["csrfToken"]
        setup = api(
            extra_client,
            target_company,
            "company-setup",
            {"employeeCode": "OTHER-001", "reason": "합성 별도 회사 준비"},
        )
        assert setup.status_code == 200
        # A distinct active approver is required by the actual document workflow.
        # Give only the existing synthetic administrator a second company binding;
        # the subject staff account remains a member of company A alone.
        with engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO core.company_member(workspace_id,user_id,role) VALUES(:w,:u,'MEMBER')"
                ),
                {"w": target_company["companyId"], "u": aid},
            )
            approver = c.scalar(
                text(
                    "INSERT INTO gw.person(workspace_id,generation_id,code,name,job_role) SELECT id,active_generation_id,'OTHER-APPROVER','합성 별도 결재자','STAFF' FROM core.workspace WHERE id=:w RETURNING id"
                ),
                {"w": target_company["companyId"]},
            )
            c.execute(
                text(
                    "INSERT INTO gw.person_identity_binding(workspace_id,generation_id,person_id,user_id,state,requested_by_user_id,activated_at,reason) SELECT id,active_generation_id,:p,:u,'ACTIVE',:requester,clock_timestamp(),'합성 별도 결재자 연결' FROM core.workspace WHERE id=:w"
                ),
                {
                    "w": target_company["companyId"],
                    "p": approver,
                    "u": aid,
                    "requester": target_company["userId"],
                },
            )
        doc = document((engine, target_company, extra_client, extra_client), approver)
        secrets[target_company["userId"]] = pyotp.random_base32()
    try:
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
        artifact = folders["backups"] / "objects.enc"
        module.backup(
            url=source,
            company_id=co["companyId"],
            output=artifact,
            evidence=folders["backups"] / "proof.json",
            config=config,
        )
        if case == "DOCUMENT_READER":
            with engine.begin() as c:
                c.execute(
                    text(
                        "UPDATE gw.document_reader SET is_active=false,version=version+1 WHERE document_id=:id AND person_id=:p"
                    ),
                    {"id": int(doc["id"]), "p": reader},
                )
        checkpoint = folders["checkpoints"] / "objects.enc"
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
            with monkeypatch.context() as local:
                local.setenv(
                    "DATABASE_URL", target_url.render_as_string(hide_password=False)
                )
                reset_engine()
                with (
                    TestClient(create_app()) as control,
                    TestClient(create_app()) as subject,
                    TestClient(create_app()) as foreign_owner,
                ):
                    mfa(control, target, "hugh-admin", password, secrets[aid])
                    mfa(subject, target, "hugh-staff", password, secrets[uid])
                    assert api(subject, co, "me", method="GET").status_code == 200
                    assert (
                        api(
                            control, co, f"documents/{control_doc['id']}", method="GET"
                        ).status_code
                        == 200
                    )
                    assert edit(control, co, control_doc).status_code == 200
                    if case == "DOCUMENT_READER":
                        assert (
                            api(
                                control, co, f"documents/{doc['id']}", method="GET"
                            ).status_code
                            == 200
                        )
                        search = "ACL-private-61"
                    else:
                        mfa(
                            foreign_owner,
                            target,
                            "synthetic-other-61",
                            password,
                            secrets[target_company["userId"]],
                        )
                        assert (
                            api(
                                foreign_owner,
                                target_company,
                                f"documents/{doc['id']}",
                                method="GET",
                            ).status_code
                            == 200
                        )
                        assert (
                            edit(foreign_owner, target_company, doc).status_code == 200
                        )
                        search = "합성 수정 대조"
                    target_before = object_state(target)
                    status, code = OBJECT_CASES[case]
                    read_response = api(
                        subject, target_company, f"documents/{doc['id']}", method="GET"
                    )
                    write_response = edit(subject, target_company, doc)
                    denied(read_response, status, code)
                    denied(write_response, status, code)
                    hidden = {}
                    if case == "FOREIGN_SCOPE":
                        denied(
                            api(subject, co, f"documents/{doc['id']}", method="GET"),
                            404,
                            "NOT_FOUND",
                        )
                        denied(edit(subject, co, doc), 404, "NOT_FOUND")
                        hidden = {
                            "hiddenScopeReadStatus": 404,
                            "hiddenScopeWriteStatus": 404,
                            "hiddenScopeReadCode": "NOT_FOUND",
                            "hiddenScopeWriteCode": "NOT_FOUND",
                        }
                    listing = api(subject, co, "documents", method="GET")
                    assert listing.status_code == 200
                    assert str(doc["id"]) not in {
                        str(d["id"]) for d in listing.json()["data"]["items"]
                    }
                    searched = subject.get(
                        "/api/v1/gw/documents",
                        params={"companyId": co["companyId"], "search": search},
                    )
                    assert (
                        searched.status_code == 200
                        and searched.json()["data"]["total"] == 0
                    )
                    assert object_state(target) == target_before
                reset_engine()
            assert closed(target) and source_state(engine) == before
            evidence = (folders["reports"] / "evidence.json").read_bytes()
            observation = RestoredObjectDenialObservation.model_validate(
                {
                    "version": 2,
                    "scope": "SYNTHETIC_CLOSED_RESTORE_OBJECT_AUTHORIZATION",
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
                    "writeStatus": status,
                    "writeErrorCode": code,
                    "positiveObjectRead": True,
                    "positiveObjectWrite": True,
                    "listHidden": True,
                    "deniedObjectStateUnchanged": True,
                    "controlMfaAuthenticated": True,
                    "subjectMfaAuthenticated": True,
                    "closedBefore": True,
                    "closedAfter": True,
                    "sourceUnchanged": True,
                    "sourceComparisonScope": "SELECTED_AUTHORIZATION_AND_DOCUMENT_TABLES",
                    "ready": False,
                    "revocationsComplete": False,
                    "liveCompanyAcceptance": False,
                    **hidden,
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
                    c.execute(
                        text(f'DROP DATABASE "{restored["database"]}" WITH (FORCE)')
                    )
            finally:
                cleanup.dispose()
    finally:
        if extra_client:
            extra_client.close()
