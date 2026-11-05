"""Fixed synthetic credentials only, actual closed PG restore and fresh MFA HTTP."""

# ruff: noqa:F401,F811
import hashlib
import json
import os
from datetime import UTC, datetime
from uuid import uuid4

import pyotp
import pytest
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.core.security.config import security_settings
from fs.gw.operating_contract import canonical
from fs.gw.restored_denial import CASES, PROPERTY, RestoredDenialObservation
from fs.main import create_app
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_gw_backup import backup_env
from test_gw_company import context
from test_gw_company_work import api
from test_hr_work import company_env


def fingerprint(engine):
    with engine.connect() as c:
        return c.scalar(
            text("""SELECT encode(sha256(convert_to(jsonb_build_array(
          (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM core.app_user t),
          (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM core.auth_session t),
          (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM core.mfa_factor t),
          (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM core.company_member t),
          (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.person_identity_binding t),
          (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.role_grant t),
          (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM hr.work_account t)
        )::text,'UTF8')),'hex')""")
        )


def closed(engine):
    with engine.connect() as c:
        return (
            c.scalar(
                text("""SELECT datconnlimit=0 AND NOT EXISTS(
          SELECT 1 FROM aclexplode(coalesce(datacl,acldefault('d',datdba))) a
          WHERE a.grantee=0 AND a.privilege_type='CONNECT')
          FROM pg_database WHERE datname=current_database()""")
            )
            is True
        )


def mfa(client, engine, login, password, secret):
    response = client.post(
        "/api/v1/core/sessions",
        json={"loginId": login, "password": password},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 202
    challenge = response.json()["data"]
    with engine.connect() as c:
        now = c.scalar(text("SELECT clock_timestamp()"))
    verified = client.post(
        "/api/v1/core/security/login/verify",
        json={"code": pyotp.TOTP(secret).at(int(now.timestamp()))},
        headers={"X-CSRF-Token": challenge["challengeCsrfToken"]},
    )
    assert verified.status_code == 201
    client.csrf = verified.json()["data"]["csrfToken"]
    assert client.get("/api/v1/core/sessions/current").status_code == 200
    with engine.connect() as c:
        assert c.scalar(
            text(
                "SELECT assurance='MFA' FROM core.auth_session WHERE user_id=(SELECT id FROM core.app_user WHERE login_id=:l) AND revoked_at IS NULL ORDER BY id DESC LIMIT 1"
            ),
            {"l": login},
        )


@pytest.mark.parametrize("case", list(CASES))
def test_closed_restore_fresh_authentication_denial(
    company_env, backup_env, monkeypatch, record_property, case
):
    engine, co, admin, staff = company_env
    module, config, folders, password = backup_env
    started = datetime.now(UTC).isoformat()
    uid = context(engine, staff).user_id
    aid = context(engine, admin).user_id
    secrets = {u: pyotp.random_base32() for u in (aid, uid)}
    # Synthetic baseline preparation only; this does not test MFA enrollment.
    with engine.begin() as c:
        for user, secret in secrets.items():
            key, encrypted = security_settings().box.seal(
                secret, purpose="totp", owner=str(user)
            )
            c.execute(
                text("""INSERT INTO core.mfa_factor(user_id,kind,state,secret_ciphertext,encryption_key_id,version,confirmed_at,created_at)
                VALUES(:u,'TOTP','ACTIVE',:s,:k,1,clock_timestamp(),clock_timestamp())"""),
                {"u": user, "s": encrypted, "k": key},
            )
        c.execute(
            text("UPDATE hr.work_account SET work_role='ADMIN' WHERE user_id=:u"),
            {"u": uid},
        )
        person = c.scalar(
            text(
                "SELECT person_id FROM gw.person_identity_binding WHERE user_id=:u AND workspace_id=:w AND state='ACTIVE'"
            ),
            {"u": uid, "w": co["companyId"]},
        )
        c.execute(
            text(
                "INSERT INTO gw.role_grant(workspace_id,generation_id,person_id,role_key,is_active,version,changed_by_user_id,reason) SELECT workspace_id,generation_id,:p,'SECURITY_ADMIN',true,1,:a,'합성 준비' FROM gw.collaboration_settings WHERE workspace_id=:w"
            ),
            {"p": person, "w": co["companyId"], "a": aid},
        )
    source = os.environ["TEST_DATABASE_URL"]
    artifact = folders["backups"] / "denial.enc"
    module.backup(
        url=source,
        company_id=co["companyId"],
        output=artifact,
        evidence=folders["backups"] / "proof.json",
        config=config,
    )
    with engine.begin() as c:
        queries = {
            "CORE_ACCOUNT": "UPDATE core.app_user SET status='disabled',disabled_at=clock_timestamp() WHERE id=:u",
            "COMPANY_MEMBERSHIP": "UPDATE core.company_member SET is_active=false WHERE user_id=:u AND workspace_id=:w",
            "GW_BINDING": "UPDATE gw.person_identity_binding SET state='SUSPENDED',closed_at=clock_timestamp(),reason='합성 회수' WHERE user_id=:u AND workspace_id=:w",
            "GW_ROLE": "UPDATE gw.role_grant SET is_active=false WHERE person_id=:p AND workspace_id=:w",
            "HR_AUTHORITY": "UPDATE hr.work_account SET work_role='STAFF' WHERE user_id=:u",
        }
        c.execute(text(queries[case]), {"u": uid, "w": co["companyId"], "p": person})
    checkpoint = folders["checkpoints"] / "denial.enc"
    head = folders["checkpoints"] / "head.json"
    captured = module.checkpoint(
        url=source, artifact=artifact, output=checkpoint, head=head, config=config
    )
    before = fingerprint(engine)
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
            ):
                mfa(control, target, "hugh-admin", password, secrets[aid])
                assert (
                    api(control, co, "security-events", method="GET").status_code == 200
                )
                if case == "CORE_ACCOUNT":
                    response = subject.post(
                        "/api/v1/core/sessions",
                        json={"loginId": "hugh-staff", "password": password},
                        headers={"Idempotency-Key": str(uuid4())},
                    )
                else:
                    mfa(subject, target, "hugh-staff", password, secrets[uid])
                    if case == "HR_AUTHORITY":
                        assert api(subject, co, "me", method="GET").status_code == 200
                        response = subject.get(
                            "/api/v1/hr/work/users",
                            params={"companyId": co["companyId"]},
                        )
                    else:
                        if case == "GW_ROLE":
                            assert (
                                api(subject, co, "me", method="GET").status_code == 200
                            )
                        response = api(subject, co, "security-events", method="GET")
                expected_status, expected_code = CASES[case]
                assert response.status_code == expected_status
                assert response.json()["error"]["code"] == expected_code
            reset_engine()
        assert closed(target) and fingerprint(engine) == before
        proof = RestoredDenialObservation.model_validate(
            {
                "version": 1,
                "scope": "SYNTHETIC_CLOSED_RESTORE_AUTHENTICATION",
                "case": case,
                "runId": os.environ.get("FS_GW_SYNTHETIC_RUN_ID", str(uuid4())),
                "codeRevision": os.environ.get(
                    "FS_GW_SYNTHETIC_CODE_REVISION", "abcdef012345"
                ),
                "dbRevision": config["db_revision"]
                if "db_revision" in config
                else json.loads((folders["reports"] / "evidence.json").read_bytes())[
                    "envelope"
                ]["dbRevision"],
                "startedAt": started,
                "finishedAt": datetime.now(UTC).isoformat(),
                "restoreDigest": hashlib.sha256(
                    (folders["reports"] / "evidence.json").read_bytes()
                ).hexdigest(),
                "status": response.status_code,
                "errorCode": expected_code,
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
        )
        record_property(PROPERTY, canonical(proof.model_dump(by_alias=True)).decode())
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
