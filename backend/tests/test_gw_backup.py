"""Real PG18 dump/encryption/closed restore with synthetic security revocations."""

# ruff: noqa:F401,F811
import base64
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_gw_company import context
from test_gw_company_work import api, ok
from test_gw_evidence import prepare
from test_hr_work import company_env

from fs.common.db import reset_engine
from fs.common.security import hash_password
from fs.core.backup import BackupError
from fs.main import create_app


def runner():
    spec = importlib.util.spec_from_file_location(
        "gw_backup_runner", Path(__file__).parents[2] / "tools/gw_backup.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def backup_env(company_env, monkeypatch, tmp_path):
    container = os.environ.get("GW_BACKUP_TEST_CONTAINER")
    if not container:
        pytest.skip("Owned PG18 container required for real backup test")
    engine, _co, admin, staff = company_env
    secret = "Synthetic-" + uuid4().hex
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.app_user SET password_hash=:p WHERE login_id IN ('hugh-admin','hugh-staff')"
            ),
            {"p": hash_password(secret)},
        )
    for client, login in [(admin, "hugh-admin"), (staff, "hugh-staff")]:
        client.cookies.clear()
        r = client.post(
            "/api/v1/core/sessions",
            json={"loginId": login, "password": secret},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert r.status_code == 201
        client.csrf = r.json()["data"]["csrfToken"]
    prepare(company_env, monkeypatch)
    monkeypatch.setenv("FS_SECURITY_MODE", "TEAM_TEST")
    monkeypatch.setenv("FS_SECURITY_KEY_ID", "synthetic")
    monkeypatch.setenv(
        "FS_SECURITY_KEYS", json.dumps({"synthetic": Fernet.generate_key().decode()})
    )
    key = tmp_path / "backup.key"
    key.write_bytes(os.urandom(32))
    key.chmod(0o600)
    signer = Ed25519PrivateKey.generate()
    signer_file = tmp_path / "runner.key"
    signer_file.write_bytes(signer.private_bytes_raw())
    signer_file.chmod(0o600)
    for name, value in {
        "FS_GW_BACKUP_KEY_FILE": str(key),
        "FS_GW_BACKUP_KEY_ID": "synthetic",
        "FS_GW_RUNNER_KEY_FILE": str(signer_file),
        "FS_GW_RUNNER_KEY_ID": "runner",
        "FS_GW_EVIDENCE_PUBLIC_KEYS": json.dumps(
            {
                "runner": base64.b64encode(
                    signer.public_key().public_bytes_raw()
                ).decode()
            }
        ),
        "FS_GW_PG_CONTAINER": container,
        "FS_GW_RESTORE_PG_CONTAINER": container,
        "FS_CODE_REVISION": "abcdef012345",
        "DATABASE_URL": os.environ["TEST_DATABASE_URL"],
    }.items():
        monkeypatch.setenv(name, value)
    folders = {}
    for name in ["backups", "checkpoints", "reports"]:
        folder = tmp_path / name
        folder.mkdir(mode=0o700)
        folders[name] = folder
    module = runner()
    config = module.settings()
    yield module, config, folders, secret


def test_actual_backup_replay_restore_and_business_denial(
    company_env, backup_env, monkeypatch
):
    module, config, folders, password = backup_env
    engine, co, admin, staff = company_env
    source_url = os.environ["TEST_DATABASE_URL"]
    artifact = folders["backups"] / "database.fsbackup"
    backup_proof = folders["backups"] / "evidence.json"
    # Execute the actual operator CLI; secrets stay in environment/protected key files.
    result = subprocess.run(
        [
            str(Path(sys.executable).absolute()),
            str(Path(__file__).parents[2] / "tools/gw_backup.py"),
            "backup",
            "--company-id",
            str(co["companyId"]),
            "--output",
            str(artifact),
            "--evidence",
            str(backup_proof),
        ],
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["result"] == "PASS" and summary["tableCount"] >= 219
    assert (
        password not in result.stdout and password.encode() not in artifact.read_bytes()
    )
    assert (
        ok(api(admin, co, "operating-evidence", json.loads(backup_proof.read_text())))[
            "result"
        ]
        == "PASS"
    )
    with engine.connect() as c:
        staff_person = c.execute(
            text(
                "SELECT person_id FROM gw.person_identity_binding WHERE workspace_id=:w AND user_id=:u AND state='ACTIVE'"
            ),
            {"w": co["companyId"], "u": context(engine, staff).user_id},
        ).scalar_one()
    binding = ok(api(staff, co, "me/binding", method="GET"))
    ok(
        api(
            admin,
            co,
            f"identity-bindings/{binding['id']}/suspend",
            {
                "expectedVersion": binding["version"],
                "reason": "합성 백업 이후 권한 회수",
            },
        )
    )
    checkpoint = folders["checkpoints"] / "checkpoint.fsbackup"
    head = folders["checkpoints"] / "head.json"
    captured = module.checkpoint(
        url=source_url, artifact=artifact, output=checkpoint, head=head, config=config
    )
    report = folders["reports"] / "restore.json"
    restore_proof = folders["reports"] / "evidence.json"
    admin_url = (
        make_url(source_url)
        .set(database="postgres")
        .render_as_string(hide_password=False)
    )
    restored = module.restore(
        admin_url=admin_url,
        artifact=artifact,
        checkpoint_file=checkpoint,
        head=head,
        expected_checkpoint_digest=captured["checkpointDigest"],
        report=report,
        evidence=restore_proof,
        config=config,
    )
    assert restored["result"] == "PARTIAL" and restored["closed"] is True
    details = json.loads(report.read_text())
    assert (
        details["rowHashesMatch"]
        and details["foreignKeysValid"]
        and details["sessionsInvalidated"]
        and details["checkpointRestrictionsApplied"]
    )
    assert details["revocationsReapplied"] is False
    assert details["checkpointCompletenessConfirmed"] is False
    assert details["twoAccountChecks"] is False and details["quarantinedScopes"] == 0
    assert (
        ok(api(admin, co, "operating-evidence", json.loads(restore_proof.read_text())))[
            "result"
        ]
        == "PARTIAL"
    )
    target_url = (
        make_url(source_url)
        .set(database=restored["database"])
        .render_as_string(hide_password=False)
    )
    target = create_engine(target_url)
    try:
        with target.connect() as c:
            assert (
                c.execute(
                    text(
                        "SELECT datconnlimit FROM pg_database WHERE datname=current_database()"
                    )
                ).scalar_one()
                == 0
            )
            assert (
                c.execute(
                    text(
                        "SELECT state FROM gw.person_identity_binding WHERE person_id=:p AND workspace_id=:w"
                    ),
                    {"p": staff_person, "w": co["companyId"]},
                ).scalar_one()
                == "SUSPENDED"
            )
        old_cookie = admin.cookies.get("fs_session")
        monkeypatch.setenv("DATABASE_URL", target_url)
        reset_engine()
        with (
            TestClient(create_app()) as restored_admin,
            TestClient(create_app()) as restored_staff,
        ):
            restored_admin.cookies.set("fs_session", old_cookie)
            assert (
                restored_admin.get("/api/v1/core/sessions/current").status_code == 401
            )
            for client, login in [
                (restored_admin, "hugh-admin"),
                (restored_staff, "hugh-staff"),
            ]:
                client.cookies.clear()
                response = client.post(
                    "/api/v1/core/sessions",
                    json={"loginId": login, "password": password},
                    headers={"Idempotency-Key": str(uuid4())},
                )
                assert response.status_code == 201
            assert (
                restored_admin.get(
                    "/api/v1/gw/posts", params={"companyId": co["companyId"]}
                ).status_code
                == 200
            )
            assert (
                restored_staff.get(
                    "/api/v1/gw/posts", params={"companyId": co["companyId"]}
                ).status_code
                == 403
            )
    finally:
        reset_engine()
        monkeypatch.setenv("DATABASE_URL", source_url)
        target.dispose()
        cleanup = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with cleanup.connect() as c:
            c.execute(text(f'DROP DATABASE "{restored["database"]}" WITH (FORCE)'))
        cleanup.dispose()


def test_missing_or_wrong_latest_checkpoint_never_creates_target(
    company_env, backup_env
):
    module, config, folders, _password = backup_env
    _engine, co, _admin, _staff = company_env
    source_url = os.environ["TEST_DATABASE_URL"]
    artifact = folders["backups"] / "database.fsbackup"
    module.backup(
        url=source_url,
        company_id=co["companyId"],
        output=artifact,
        evidence=folders["backups"] / "evidence.json",
        config=config,
    )
    assert (
        module.check(url=source_url, artifact=artifact, config=config)["current"]
        is True
    )
    policy = ok(api(company_env[2], co, "operations", method="GET"))["policy"] | {
        "reason": "합성 백업 후 정책 변경",
        "rpoMinutes": 90,
    }
    ok(
        api(
            company_env[2],
            co,
            "operating-policies",
            {"expectedVersion": 1, "policy": policy},
        )
    )
    checked = module.check(url=source_url, artifact=artifact, config=config)
    assert checked["current"] is False and checked["policyMatches"] is False
    checkpoint = folders["checkpoints"] / "checkpoint.fsbackup"
    head = folders["checkpoints"] / "head.json"
    module.checkpoint(
        url=source_url, artifact=artifact, output=checkpoint, head=head, config=config
    )
    with pytest.raises(BackupError):
        module.restore(
            admin_url=make_url(source_url)
            .set(database="postgres")
            .render_as_string(hide_password=False),
            artifact=artifact,
            checkpoint_file=checkpoint,
            head=head,
            expected_checkpoint_digest="0" * 64,
            report=folders["reports"] / "restore.json",
            evidence=folders["reports"] / "proof.json",
            config=config,
        )
    assert not (folders["reports"] / "restore.json").exists()
    artifact_raw = bytearray(artifact.read_bytes())
    artifact_raw[40] ^= 1
    artifact.write_bytes(artifact_raw)
    with pytest.raises(BackupError):
        module.checkpoint(
            url=source_url,
            artifact=artifact,
            output=folders["checkpoints"] / "second.fsbackup",
            head=folders["checkpoints"] / "second.json",
            config=config,
        )


def test_failed_restore_keeps_new_database_closed_and_preserves_report(
    company_env, backup_env, monkeypatch
):
    module, config, folders, _password = backup_env
    _engine, co, _admin, _staff = company_env
    source_url = os.environ["TEST_DATABASE_URL"]
    artifact = folders["backups"] / "database.fsbackup"
    module.backup(
        url=source_url,
        company_id=co["companyId"],
        output=artifact,
        evidence=folders["backups"] / "evidence.json",
        config=config,
    )
    checkpoint = folders["checkpoints"] / "checkpoint.fsbackup"
    head = folders["checkpoints"] / "head.json"
    captured = module.checkpoint(
        url=source_url, artifact=artifact, output=checkpoint, head=head, config=config
    )
    monkeypatch.setattr(module, "inventory", lambda _: {})
    report = folders["reports"] / "failure.json"
    admin_url = (
        make_url(source_url)
        .set(database="postgres")
        .render_as_string(hide_password=False)
    )
    with pytest.raises(BackupError):
        module.restore(
            admin_url=admin_url,
            artifact=artifact,
            checkpoint_file=checkpoint,
            head=head,
            expected_checkpoint_digest=captured["checkpointDigest"],
            report=report,
            evidence=folders["reports"] / "proof.json",
            config=config,
        )
    result = json.loads(report.read_text())
    assert result["result"] == "FAIL" and result["closed"] is True
    assert result["connectionsDisabled"] is True
    assert not (folders["reports"] / "proof.json").exists()
    cleanup = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with cleanup.connect() as c:
        assert (
            c.execute(
                text("SELECT datconnlimit FROM pg_database WHERE datname=:name"),
                {"name": result["database"]},
            ).scalar_one()
            == 0
        )
        c.execute(text(f'DROP DATABASE "{result["database"]}" WITH (FORCE)'))
    cleanup.dispose()
