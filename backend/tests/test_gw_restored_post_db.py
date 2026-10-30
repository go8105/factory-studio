"""Post visibility and conservative scope quarantine on an actual closed restore."""

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
from test_gw_company_work import api, call_work
from test_gw_restored_denial_db import closed, fingerprint, mfa
from test_gw_restored_object_db import denied
from test_hr_work import company_env

from fs.common.db import reset_engine
from fs.core.security.config import security_settings
from fs.gw.operating_contract import canonical
from fs.gw.restored_denial import POST_CASES, PROPERTY, RestoredPostDenialObservation
from fs.main import create_app

MARKER = "POST-PRIVATE-62"


def post_state(engine):
    with engine.connect() as c:
        return c.scalar(
            text("""SELECT encode(sha256(convert_to(jsonb_build_array(
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.person t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.organization_unit t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.board_post t),
            (SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM gw.board_event t)
            )::text,'UTF8')),'hex')""")
        )


def source_state(engine):
    return fingerprint(engine), post_state(engine)


def post(env, author, title, *, org=None, publish=True, notice=False):
    data = call_work(
        env,
        author,
        "posts",
        None,
        "create",
        {
            "board_kind": "NOTICE" if org or notice else "FREE",
            "visibility": "ORG" if org else "WORKSPACE",
            "audience_org_id": org,
            "title": title,
            "body": title + " 합성 본문",
        },
    )
    if publish:
        data = call_work(
            env,
            author,
            "posts",
            int(data["id"]),
            "publish",
            {"expected_version": data["version"]},
        )
    return data


def edit(client, co, data):
    return api(
        client,
        co,
        f"posts/{data['id']}",
        {
            "expectedVersion": data["version"],
            "visibility": "WORKSPACE",
            "title": "합성 본인 초안 수정",
            "body": "합성 본인 초안 수정 대조",
        },
        method="PATCH",
    )


@pytest.mark.parametrize("case", list(POST_CASES))
def test_closed_restore_post_visibility(
    company_env, backup_env, monkeypatch, record_property, case
):
    engine, co, admin, staff = company_env
    module, config, folders, password = backup_env
    guarded = case == "POST_VISIBILITY_GUARD"
    started = datetime.now(UTC).isoformat()
    aid = context(engine, admin).user_id
    uid = context(engine, staff).user_id
    with engine.begin() as c:
        own = (
            c.execute(
                text(
                    "SELECT person_id,p.organization_unit_id FROM gw.person_identity_binding b JOIN gw.person p ON p.id=b.person_id WHERE b.workspace_id=:w AND b.user_id=:u AND b.state='ACTIVE'"
                ),
                {"w": co["companyId"], "u": aid},
            )
            .mappings()
            .one()
        )
        org_a = own["organization_unit_id"]
        assert org_a is not None
        org_b = c.scalar(
            text(
                "INSERT INTO gw.organization_unit(workspace_id,generation_id,code,name) SELECT id,active_generation_id,'POST-OTHER-62','합성 별도 조직62' FROM core.workspace WHERE id=:w RETURNING id"
            ),
            {"w": co["companyId"]},
        )
        c.execute(
            text(
                "UPDATE gw.person SET organization_unit_id=:org WHERE id=(SELECT person_id FROM gw.person_identity_binding WHERE workspace_id=:w AND user_id=:u AND state='ACTIVE')"
            ),
            {"org": org_b, "w": co["companyId"], "u": uid},
        )
    target_post = post(
        company_env, admin, MARKER, org=None if guarded else org_a, notice=True
    )
    public = post(company_env, admin, "POST-PUBLIC-62")
    with engine.begin() as c:
        c.execute(
            text("UPDATE gw.person SET organization_unit_id=:org WHERE id=:p"),
            {"org": org_b, "p": own["person_id"]},
        )
    matching_org = post(company_env, admin, "POST-ALLOWED-ORG-62", org=org_b)
    with engine.begin() as c:
        c.execute(
            text("UPDATE gw.person SET organization_unit_id=NULL WHERE id=:p"),
            {"p": own["person_id"]},
        )
    draft = post(company_env, staff, "POST-OWN-DRAFT-62", publish=False)
    saved = edit(staff, co, draft)
    assert saved.status_code == 200
    draft = saved.json()["data"]
    assert api(admin, co, f"posts/{target_post['id']}", method="GET").status_code == 200
    assert api(staff, co, f"posts/{public['id']}", method="GET").status_code == 200
    assert (
        api(staff, co, f"posts/{matching_org['id']}", method="GET").status_code == 200
    )
    baseline = api(staff, co, f"posts/{target_post['id']}", method="GET")
    if guarded:
        assert baseline.status_code == 200
    else:
        denied(baseline, 404, "NOT_FOUND")
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
    artifact = folders["backups"] / "posts.enc"
    module.backup(
        url=source,
        company_id=co["companyId"],
        output=artifact,
        evidence=folders["backups"] / "proof.json",
        config=config,
    )
    if guarded:
        # This change cannot be safely replayed as business content: the existing
        # restore guard must quarantine the scope rather than rewrite the post.
        with engine.begin() as c:
            c.execute(
                text(
                    "UPDATE gw.board_post SET visibility='ORG',audience_org_id=:org WHERE id=:id"
                ),
                {"org": org_a, "id": int(target_post["id"])},
            )
    checkpoint = folders["checkpoints"] / "posts.enc"
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
            assert (active == 0) == guarded and hold == guarded
            assert c.scalar(
                text("SELECT visibility FROM gw.board_post WHERE id=:id"),
                {"id": int(target_post["id"])},
            ) == ("WORKSPACE" if guarded else "ORG")
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
                target_before = post_state(target) if guarded else None
                owner_read = api(
                    control, co, f"posts/{target_post['id']}", method="GET"
                )
                public_read = api(subject, co, f"posts/{public['id']}", method="GET")
                org_read = api(subject, co, f"posts/{matching_org['id']}", method="GET")
                own_write = edit(subject, co, draft)
                if guarded:
                    for response in (owner_read, public_read, org_read, own_write):
                        denied(response, 403, "GW_IDENTITY_REQUIRED")
                else:
                    assert all(
                        response.status_code == 200
                        for response in (owner_read, public_read, org_read, own_write)
                    )
                if not guarded:
                    target_before = post_state(target)
                response = api(subject, co, f"posts/{target_post['id']}", method="GET")
                write = edit(subject, co, target_post)
                status, code = POST_CASES[case]
                denied(response, status, code)
                denied(write, status, code)
                listing = api(subject, co, "posts", method="GET")
                search = subject.get(
                    "/api/v1/gw/posts",
                    params={"companyId": co["companyId"], "search": MARKER},
                )
                if guarded:
                    denied(listing, 403, "GW_IDENTITY_REQUIRED")
                    denied(search, 403, "GW_IDENTITY_REQUIRED")
                else:
                    assert listing.status_code == search.status_code == 200
                    assert str(target_post["id"]) not in {
                        str(row["id"]) for row in listing.json()["data"]["items"]
                    }
                    assert search.json()["data"]["total"] == 0
                denied_responses = (response, write, listing, search)
                if guarded:
                    denied_responses += (owner_read, public_read, org_read, own_write)
                assert all(MARKER not in item.text for item in denied_responses)
                assert post_state(target) == target_before
            reset_engine()
        assert closed(target) and source_state(engine) == before
        evidence = (folders["reports"] / "evidence.json").read_bytes()
        observation = RestoredPostDenialObservation.model_validate(
            {
                "version": 3,
                "scope": "SYNTHETIC_CLOSED_RESTORE_POST_VISIBILITY",
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
                "controlMfaAuthenticated": True,
                "subjectMfaAuthenticated": True,
                "closedBefore": True,
                "closedAfter": True,
                "sourceUnchanged": True,
                "sourceComparisonScope": "SELECTED_AUTHORIZATION_ORGANIZATION_AND_POST_TABLES",
                "baselineReadConfirmed": True,
                "baselineWriteConfirmed": True,
                "restoredOwnerReadConfirmed": not guarded,
                "restoredPublicReadConfirmed": not guarded,
                "restoredOrgReadConfirmed": not guarded,
                "restoredOwnDraftWriteConfirmed": not guarded,
                "quarantineObserved": guarded,
                "companyHold": hold,
                "contentExposed": False,
                "deniedPostStateUnchanged": True,
                "listingMode": "IDENTITY_DENIED" if guarded else "FILTERED",
                "listStatus": listing.status_code,
                "searchStatus": search.status_code,
                "listCode": "GW_IDENTITY_REQUIRED" if guarded else None,
                "searchCode": "GW_IDENTITY_REQUIRED" if guarded else None,
                "visibilityReplayed": False,
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
