"""Offline encrypted backup/checkpoint/closed restore. Never opens employee access.

Secrets come from protected files/environment; no database URLs or keys on argv.
Run with `uv run --project backend python tools/gw_backup.py --help`.
"""

import argparse
import base64
import hashlib
import io
import json
import math
import os
import re
import tarfile
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from fs.common.errors import ApiError
from fs.core.backup import (
    BackupError,
    create_private,
    database_identity,
    decrypt,
    encrypt,
    fk_valid,
    inventory,
    private_directory,
    private_file,
    require_tool_version,
    run_pg,
    sha256_file,
    tool_database_identity,
)
from fs.core.security import backup as core_checkpoint
from fs.core.security.config import security_settings
from fs.gw import backup as gw_checkpoint
from fs.gw import backup_journal
from fs.gw.operating_contract import canonical, timestamp
from fs.hr import backup as hr_checkpoint
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

CONTEXT = b"FS-OPERATOR-BUNDLE-v1\0"


def preflight(*paths):
    if len({p.resolve() for p in paths}) != len(paths):
        raise BackupError("출력 파일은 서로 다른 새 경로여야 합니다.")
    for path in paths:
        private_directory(path.parent)
        if path.exists() or path.is_symlink():
            raise BackupError("기존 출력 파일을 덮어쓰지 않습니다.")


def now():
    return datetime.now(UTC).isoformat()


def settings():
    security = security_settings()
    if security.mode == "PUBLIC_DEMO" or security.box is None:
        raise BackupError("회사 보안 모드와 인증 키가 필요합니다.")
    key = private_file(os.environ["FS_GW_BACKUP_KEY_FILE"], size=32).read_bytes()
    signer = Ed25519PrivateKey.from_private_bytes(
        private_file(os.environ["FS_GW_RUNNER_KEY_FILE"], size=32).read_bytes()
    )
    signer_id = os.environ["FS_GW_RUNNER_KEY_ID"]
    key_id = os.environ["FS_GW_BACKUP_KEY_ID"]
    revision = os.environ["FS_CODE_REVISION"]
    if not all(
        re.fullmatch(r"[A-Za-z0-9_-]{1,60}", v) for v in [signer_id, key_id]
    ) or not re.fullmatch(r"[0-9a-f]{7,64}", revision):
        raise BackupError("키 식별자·제품 버전을 확인하세요.")
    configured = json.loads(os.environ["FS_GW_EVIDENCE_PUBLIC_KEYS"])
    if not isinstance(configured, dict) or not 1 <= len(configured) <= 20:
        raise BackupError("검증 공개 키 설정을 확인하세요.")
    public = {
        name: base64.b64decode(value, validate=True)
        for name, value in configured.items()
    }
    if any(len(value) != 32 for value in public.values()):
        raise BackupError("검증 공개 키 크기를 확인하세요.")
    if public.get(signer_id) != signer.public_key().public_bytes_raw():
        raise BackupError("실행자 서명 키와 서버 검증 공개 키가 다릅니다.")
    return {
        "key": key,
        "keyId": key_id,
        "signer": signer,
        "signerId": signer_id,
        "public": public,
        "codeRevision": revision,
        "authenticationKeyIds": sorted(security.box.keys),
        "secretPaths": [
            os.environ["FS_GW_BACKUP_KEY_FILE"],
            os.environ["FS_GW_RUNNER_KEY_FILE"],
        ],
    }


def signed_document(data, config):
    return {
        "payload": data,
        "signature": base64.b64encode(
            config["signer"].sign(CONTEXT + canonical(data))
        ).decode(),
        "signerKeyId": config["signerId"],
    }


def verified_document(value, config):
    try:
        if set(value) != {"payload", "signature", "signerKeyId"}:
            raise ValueError()
        key = Ed25519PublicKey.from_public_bytes(config["public"][value["signerKeyId"]])
        key.verify(
            base64.b64decode(value["signature"], validate=True),
            CONTEXT + canonical(value["payload"]),
        )
        if not isinstance(value["payload"], dict):
            raise TypeError()
        return value["payload"]
    except (ValueError, KeyError, TypeError, InvalidSignature):
        raise BackupError("운영 명세의 서명 검증에 실패했습니다.") from None


def write_json(path, value):
    with create_private(path) as out:
        out.write(canonical(value) + b"\n")
        out.flush()
        os.fsync(out.fileno())
    descriptor = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def pack(path, manifest, config, *, dump=None):
    with tarfile.open(path, "w") as archive:
        data = canonical(signed_document(manifest, config))
        entry = tarfile.TarInfo("manifest.json")
        entry.size = len(data)
        entry.mode = 0o600
        archive.addfile(entry, io.BytesIO(data))
        if dump is not None:
            archive.add(dump, arcname="database.dump", recursive=False)
    os.chmod(path, 0o600)


def unpack(artifact, temp, config, *, kind):
    plain = temp / "payload.tar"
    decrypt(private_file(artifact), plain, config["key"])
    manifest = None
    names = set()
    with tarfile.open(plain, "r:") as archive:
        for entry in archive:
            if (
                entry.name not in {"manifest.json", "database.dump"}
                or entry.name in names
                or not entry.isfile()
            ):
                raise BackupError("백업 파일 구성을 확인하세요.")
            names.add(entry.name)
            source = archive.extractfile(entry)
            if entry.name == "manifest.json":
                if entry.size > 16 * 1024 * 1024:
                    raise BackupError("백업 명세 크기를 확인하세요.")
                manifest = verified_document(json.loads(source.read()), config)
            else:
                with create_private(temp / "database.dump") as out:
                    while block := source.read(1024 * 1024):
                        out.write(block)
    if (
        manifest is None
        or manifest.get("version") != 1
        or manifest.get("kind") != kind
        or manifest.get("encryptionKeyId") != config["keyId"]
    ):
        raise BackupError("백업 종류·버전·키 식별자가 맞지 않습니다.")
    if kind == "BACKUP":
        if (
            names != {"manifest.json", "database.dump"}
            or sha256_file(temp / "database.dump") != manifest["dumpDigest"]
        ):
            raise BackupError("DB 백업 지문이 맞지 않습니다.")
    elif names != {"manifest.json"}:
        raise BackupError("권한 대조 파일 구성이 맞지 않습니다.")
    return manifest


def proof(manifest, config, *, kind, result, started, finished, metrics):
    envelope = {
        "version": 1,
        "runId": manifest["runId"] if kind == "BACKUP" else str(uuid4()),
        "workspaceId": manifest["scope"]["workspaceId"],
        "generationId": manifest["scope"]["generationId"],
        "policyDigest": manifest["scope"]["policyDigest"],
        "kind": kind,
        "startedAt": started,
        "finishedAt": finished,
        "codeRevision": manifest["codeRevision"],
        "dbRevision": manifest["dbRevision"],
        "manifestDigest": hashlib.sha256(canonical(manifest)).hexdigest(),
        "result": result,
        "signerKeyId": config["signerId"],
        "metrics": metrics,
    }
    return {
        "envelope": envelope,
        "signature": base64.b64encode(
            config["signer"].sign(canonical(envelope))
        ).decode(),
    }


def snapshot(c):
    c.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    c.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    clock = c.execute(text("SELECT transaction_timestamp()")).scalar_one()
    if abs((datetime.now(UTC) - clock).total_seconds()) > 30:
        raise BackupError("서버와 실행자 시각 차이를 먼저 확인하세요.")
    return clock.isoformat()


def backup(*, url, company_id, output, evidence, config):
    preflight(output, evidence)
    if any(
        Path(path).resolve().is_relative_to(output.parent.resolve())
        for path in config.get("secretPaths", [])
        + (
            [os.environ["FS_GW_IDENTITY_JOURNAL_KEY_FILE"]]
            if os.environ.get("FS_GW_IDENTITY_JOURNAL_KEY_FILE")
            else []
        )
    ):
        raise BackupError("백업 파일과 키 파일은 다른 보관 경로를 사용하세요.")
    engine = create_engine(url)
    try:
        with tempfile.TemporaryDirectory(
            prefix=".fs-backup-", dir=private_directory(output.parent)
        ) as folder:
            temp = Path(folder)
            observed_journal = backup_journal.source_records()
            with engine.connect() as c, c.begin():
                started = snapshot(c)
                scope = gw_checkpoint.policy_snapshot(c, company_id)
                major = (
                    int(c.execute(text("SHOW server_version_num")).scalar_one())
                    // 10000
                )
                require_tool_version("pg_dump", url, major)
                if not core_checkpoint.required_keys(c).issubset(
                    config["authenticationKeyIds"]
                ):
                    raise BackupError("활성 인증 앱의 암호화 키가 누락되었습니다.")
                exported = c.execute(text("SELECT pg_export_snapshot()")).scalar_one()
                manifest = {
                    "version": 1,
                    "kind": "BACKUP",
                    "journal": backup_journal.anchor(c, observed_journal),
                    "runId": str(uuid4()),
                    "sourceIdentity": database_identity(c),
                    "scope": scope,
                    "startedAt": started,
                    "codeRevision": config["codeRevision"],
                    "dbRevision": c.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one(),
                    "serverMajor": major,
                    "encryptionKeyId": config["keyId"],
                    "authenticationKeyIds": config["authenticationKeyIds"],
                    "inventory": inventory(c),
                    "coreSecurity": core_checkpoint.capture(c),
                    "gwSecurity": gw_checkpoint.capture(c),
                    "hrSecurity": hr_checkpoint.capture(c),
                }
                if tool_database_identity(url) != manifest["sourceIdentity"]:
                    raise BackupError("DB 도구가 다른 원본을 가리킵니다.")
                dump = temp / "database.dump"
                with create_private(dump) as out:
                    run_pg(
                        "pg_dump",
                        url,
                        [
                            "--format=custom",
                            "--no-owner",
                            "--no-privileges",
                            "--snapshot=" + exported,
                        ],
                        output_file=out,
                    )
                manifest["dumpDigest"] = sha256_file(dump)
            pack(temp / "package.tar", manifest, config, dump=dump)
            if (temp / "package.tar").stat().st_size > 1024 * 1024 * 1024:
                raise BackupError("현재 백업 묶음 허용 한도는1GiB입니다.")
            encrypt(temp / "package.tar", output, config["key"])
            (temp / "verification").mkdir(mode=0o700)
            verified = unpack(output, temp / "verification", config, kind="BACKUP")
            if verified != manifest:
                raise BackupError("저장 후 백업 자체 검증에 실패했습니다.")
            artifact = sha256_file(output)
            with engine.connect() as c:
                finished = (
                    c.execute(text("SELECT clock_timestamp()")).scalar_one().isoformat()
                )
            result = proof(
                manifest,
                config,
                kind="BACKUP",
                result="PASS",
                started=started,
                finished=finished,
                metrics={
                    "snapshotStartedAt": started,
                    "storageConfirmedAt": finished,
                    "artifactDigest": artifact,
                    "failedCheckCount": 0,
                },
            )
            write_json(evidence, result)
            return {
                "runId": manifest["runId"],
                "result": "PASS",
                "tableCount": len(manifest["inventory"]),
            }
    finally:
        engine.dispose()


def checkpoint(*, url, artifact, output, head, config):
    if (
        output.parent.resolve() == artifact.parent.resolve()
        or head.parent.resolve() == artifact.parent.resolve()
    ):
        raise BackupError(
            "권한 대조 기록과 최신 지문은 백업과 다른 비공개 폴더에 보관하세요."
        )
    preflight(output, head)
    engine = create_engine(url)
    try:
        with tempfile.TemporaryDirectory(
            prefix=".fs-checkpoint-", dir=private_directory(output.parent)
        ) as folder:
            temp = Path(folder)
            original = unpack(artifact, temp, config, kind="BACKUP")
            observed_journal = backup_journal.source_records()
            with engine.connect() as c, c.begin():
                started = snapshot(c)
                if database_identity(c) != original["sourceIdentity"]:
                    raise BackupError("백업과 다른 원본 DB입니다.")
                if timestamp(started) < timestamp(original["startedAt"]):
                    raise BackupError("백업보다 오래된 권한 대조 기록입니다.")
                manifest = {
                    "version": 1,
                    "kind": "CHECKPOINT",
                    "journal": backup_journal.plan(
                        c, original.get("journal"), observed_journal
                    ),
                    "runId": str(uuid4()),
                    "backupRunId": original["runId"],
                    "backupManifestDigest": __import__("hashlib")
                    .sha256(canonical(original))
                    .hexdigest(),
                    "sourceIdentity": original["sourceIdentity"],
                    "capturedAt": started,
                    "encryptionKeyId": config["keyId"],
                    "coreSecurity": core_checkpoint.capture(c),
                    "gwSecurity": gw_checkpoint.capture(c),
                    "hrSecurity": hr_checkpoint.capture(c),
                }
            # Remove decrypted backup members before creating the checkpoint package.
            (temp / "payload.tar").unlink()
            (temp / "database.dump").unlink()
            pack(temp / "package.tar", manifest, config)
            encrypt(temp / "package.tar", output, config["key"])
            latest = {
                "version": 1,
                "kind": "CHECKPOINT_HEAD",
                "backupRunId": original["runId"],
                "runId": manifest["runId"],
                "checkpointDigest": sha256_file(output),
                "capturedAt": started,
            }
            write_json(head, signed_document(latest, config))
            return {
                "runId": manifest["runId"],
                "capturedAt": started,
                "checkpointDigest": latest["checkpointDigest"],
            }
    finally:
        engine.dispose()


def restore(
    *,
    admin_url,
    artifact,
    checkpoint_file,
    head,
    expected_checkpoint_digest,
    report,
    evidence,
    config,
):
    if not re.fullmatch(r"[0-9a-f]{64}", expected_checkpoint_digest):
        raise BackupError("독립 보관한 최신 권한 대조 지문을 확인하세요.")
    preflight(report, evidence)
    target_created = False
    started = now()
    timer = time.monotonic()
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    target = None
    target_name = "fs_gw_restore_" + uuid4().hex + "_test"
    try:
        with tempfile.TemporaryDirectory(
            prefix=".fs-restore-", dir=private_directory(report.parent)
        ) as folder:
            temp = Path(folder)
            manifest = unpack(artifact, temp, config, kind="BACKUP")
            if config["codeRevision"] != manifest["codeRevision"] or not set(
                manifest["authenticationKeyIds"]
            ).issubset(config["authenticationKeyIds"]):
                raise BackupError("백업과 같은 제품 버전·인증 암호화 키가 필요합니다.")
            latest = verified_document(
                json.loads(private_file(head).read_text()), config
            )
            digest = sha256_file(private_file(checkpoint_file))
            if (
                latest.get("kind") != "CHECKPOINT_HEAD"
                or latest.get("checkpointDigest") != digest
                or digest != expected_checkpoint_digest
            ):
                raise BackupError("최신 권한 대조 지문과 파일이 다릅니다.")
            (temp / "checkpoint").mkdir(mode=0o700)
            changes = unpack(
                checkpoint_file, temp / "checkpoint", config, kind="CHECKPOINT"
            )
            if (
                changes["backupRunId"] != manifest["runId"]
                or changes["sourceIdentity"] != manifest["sourceIdentity"]
                or changes["backupManifestDigest"]
                != hashlib.sha256(canonical(manifest)).hexdigest()
                or latest.get("backupRunId") != manifest["runId"]
                or latest.get("runId") != changes["runId"]
                or latest.get("capturedAt") != changes["capturedAt"]
            ):
                raise BackupError("백업과 권한 대조 기록의 연결이 맞지 않습니다.")
            backup_journal.validate_restore(
                manifest.get("journal"), changes.get("journal")
            )
            age = (datetime.now(UTC) - timestamp(changes["capturedAt"])).total_seconds()
            if (
                age < -30
                or age > manifest["scope"]["policy"]["rpoMinutes"] * 60
                or timestamp(changes["capturedAt"]) < timestamp(manifest["startedAt"])
            ):
                raise BackupError("권한 대조 기록의 시각·기한을 확인하세요.")
            with admin.connect() as c:
                major = (
                    int(c.execute(text("SHOW server_version_num")).scalar_one())
                    // 10000
                )
                if major != manifest["serverMajor"]:
                    raise BackupError("같은 주 버전의 격리 복원 서버가 필요합니다.")
                require_tool_version("pg_restore", admin_url, major, restore=True)
                # Always create a new target. There is no --clean, overwrite or user-selected DB name.
                c.execute(
                    text(
                        f'CREATE DATABASE "{target_name}" TEMPLATE template0 CONNECTION LIMIT 0'
                    )
                )
                target_created = True
                c.execute(
                    text(f'REVOKE CONNECT ON DATABASE "{target_name}" FROM PUBLIC')
                )
                c.execute(
                    text(
                        f"COMMENT ON DATABASE \"{target_name}\" IS 'Factory Studio closed recovery; no employee access'"
                    )
                )
            target_url = (
                make_url(admin_url)
                .set(database=target_name)
                .render_as_string(hide_password=False)
            )
            target = create_engine(target_url)
            with target.connect() as c:
                if tool_database_identity(
                    target_url, restore=True
                ) != database_identity(c):
                    raise BackupError("DB 도구가 다른 복원 대상을 가리킵니다.")
            with open(temp / "database.dump", "rb") as src:
                run_pg(
                    "pg_restore",
                    target_url,
                    [
                        "--exit-on-error",
                        "--no-owner",
                        "--no-privileges",
                        "--dbname=" + target_name,
                    ],
                    input_file=src,
                    restore=True,
                )
            with target.connect() as c, c.begin():
                snapshot(c)
                row_match = inventory(c) == manifest["inventory"]
                foreign_keys = fk_valid(c)
                head_match = (
                    c.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one()
                    == manifest["dbRevision"]
                )
            if not (row_match and foreign_keys and head_match):
                raise BackupError(
                    "복원 행·지문·FK·DB 버전이 일치하지 않습니다. 격리 DB를 유지합니다."
                )
            with target.begin() as c:
                c.execute(text("SET LOCAL TIME ZONE 'UTC'"))
                core_result = core_checkpoint.replay(c, changes["coreSecurity"])
                gw_result = gw_checkpoint.replay(c, changes["gwSecurity"])
                hr_result = hr_checkpoint.replay(c, changes["hrSecurity"])
                journal = changes.get("journal")
                journal_result = {
                    "journalRestrictionsApplied": journal is not None,
                    "journalCandidateIntents": 0,
                    "journalUnconfirmedIntents": 0,
                    "journalCounterIntents": 0,
                    "journalAbortedIntents": 0,
                    "journalDisabledAccounts": 0,
                    "journalQuarantinedScopes": 0,
                }
                if journal is not None:
                    journal_result.update(
                        journalCandidateIntents=journal["candidates"],
                        journalUnconfirmedIntents=journal["unconfirmed"],
                        journalCounterIntents=journal["counterIntents"],
                        journalAbortedIntents=journal.get("abortedIntents", 0),
                        journalDisabledAccounts=core_checkpoint.restrict_journal_users(
                            c, journal["users"]
                        ),
                        journalQuarantinedScopes=gw_checkpoint.restrict_journal_scopes(
                            c, journal["scopes"]
                        ),
                    )
                    hr_checkpoint.restrict_journal_users(c, journal["users"])

                # Security replay may only restrict restored permissions; originals remain untouched.
                if not core_result["sessionsInvalidated"]:
                    raise BackupError("기존 인증 세션을 무효화하지 못했습니다.")
            finished = now()
            elapsed = math.ceil(time.monotonic() - timer)
            loss = max(
                0,
                math.ceil(
                    (
                        timestamp(finished) - timestamp(manifest["startedAt"])
                    ).total_seconds()
                    + 30
                ),
            )
            # No human/business probes or off-host durability assertions are inferred from row hashes.
            result = {
                "result": "PARTIAL",
                "database": target_name,
                "closed": True,
                "rowHashesMatch": row_match,
                "foreignKeysValid": foreign_keys,
                "dbRevisionMatches": head_match,
                **core_result,
                **gw_result,
                **hr_result,
                **journal_result,
                "checkpointRestrictionsApplied": True,
                "checkpointCompletenessConfirmed": False,
                "revocationsReapplied": False,
                "twoAccountChecks": False,
                "checkpointAgeSeconds": max(0, math.ceil(age)),
                "clockToleranceSeconds": 30,
                "lossWindowSeconds": loss,
                "elapsedSeconds": elapsed,
                "remaining": [
                    "최신 권한 대조 기록의 완전성·별도 보관 책임자 확인",
                    "관리자/직원 대표 업무·회수 계정 거부 인수",
                    "다른 솔루션 권한·외부 파일/저장소·실환경 경계 확인",
                    "격리 범위가 있으면 권한 변경 대조 및 별도 복구 계획",
                ],
                "targetLimits": "PUBLIC CONNECT 회수/접속수0; 운영 앱·worker 연결 금지",
            }
            write_json(report, result)
            write_json(
                evidence,
                proof(
                    manifest,
                    config,
                    kind="RESTORE",
                    result="PARTIAL",
                    started=started,
                    finished=finished,
                    metrics={
                        k: result[k]
                        for k in [
                            "rowHashesMatch",
                            "foreignKeysValid",
                            "sessionsInvalidated",
                            "revocationsReapplied",
                            "twoAccountChecks",
                            "lossWindowSeconds",
                            "elapsedSeconds",
                        ]
                    }
                    | {"failedCheckCount": 1},
                ),
            )
            return {"result": "PARTIAL", "database": target_name, "closed": True}
    except BaseException:
        frozen = False
        if target_created:
            try:
                with admin.connect() as c:
                    c.execute(
                        text(f'ALTER DATABASE "{target_name}" ALLOW_CONNECTIONS false')
                    )
                frozen = True
            except SQLAlchemyError:
                pass
        if target_created and not report.exists():
            write_json(
                report,
                {
                    "result": "FAIL",
                    "connectionsDisabled": frozen,
                    "database": target_name,
                    "closed": True,
                    "remaining": [
                        "복원 검증 실패; 격리 DB를 유지하고 비공개 진단을 확인하세요."
                    ],
                },
            )
        raise
    finally:
        if target is not None:
            target.dispose()
        admin.dispose()


def check(*, url, artifact, config):
    engine = create_engine(url)
    try:
        with tempfile.TemporaryDirectory(
            prefix=".fs-backup-check-", dir=private_directory(artifact.parent)
        ) as folder:
            manifest = unpack(artifact, Path(folder), config, kind="BACKUP")
            with engine.connect() as c, c.begin():
                snapshot(c)
                active = gw_checkpoint.policy_snapshot(
                    c, int(manifest["scope"]["workspaceId"])
                )
                clock = c.execute(text("SELECT clock_timestamp()")).scalar_one()
                age = math.ceil(
                    (clock - timestamp(manifest["startedAt"])).total_seconds()
                )
                same_source = database_identity(c) == manifest["sourceIdentity"]
                same_policy = (
                    active["policyDigest"] == manifest["scope"]["policyDigest"]
                    and active["generationId"] == manifest["scope"]["generationId"]
                )
                same_code = config["codeRevision"] == manifest["codeRevision"]
                same_db = (
                    c.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one()
                    == manifest["dbRevision"]
                )
            current = (
                same_source
                and same_policy
                and same_code
                and same_db
                and 0 <= age <= active["policy"]["rpoMinutes"] * 60
            )
            return {
                "artifactValid": True,
                "current": current,
                "snapshotAgeSeconds": age,
                "policyMatches": same_policy,
                "sourceMatches": same_source,
                "codeMatches": same_code,
                "dbMatches": same_db,
                "storageScope": "LOCAL",
                "operatingReady": False,
            }
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("backup")
    p.add_argument("--company-id", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--evidence", type=Path, required=True)
    p = sub.add_parser("checkpoint")
    p.add_argument("--backup", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--head", type=Path, required=True)
    p = sub.add_parser("restore")
    p.add_argument("--backup", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--head", type=Path, required=True)
    p.add_argument("--expected-checkpoint-digest", required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--evidence", type=Path, required=True)
    p = sub.add_parser("check")
    p.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = settings()
        if args.command == "backup":
            result = backup(
                url=os.environ["DATABASE_URL"],
                company_id=args.company_id,
                output=args.output,
                evidence=args.evidence,
                config=config,
            )
        elif args.command == "checkpoint":
            result = checkpoint(
                url=os.environ["DATABASE_URL"],
                artifact=args.backup,
                output=args.output,
                head=args.head,
                config=config,
            )
        elif args.command == "check":
            result = check(
                url=os.environ["DATABASE_URL"], artifact=args.backup, config=config
            )
        else:
            result = restore(
                admin_url=os.environ["FS_GW_RESTORE_ADMIN_URL"],
                artifact=args.backup,
                checkpoint_file=args.checkpoint,
                head=args.head,
                expected_checkpoint_digest=args.expected_checkpoint_digest,
                report=args.report,
                evidence=args.evidence,
                config=config,
            )
    except (
        BackupError,
        ApiError,
        SQLAlchemyError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        tarfile.TarError,
    ):
        parser.exit(
            1,
            "실행하지 못했습니다. 비공개 환경·키·도구 버전·파일·서명·권한 대조 기한을 확인하세요. 생성된 격리 DB와 결과 파일은 보존하며 원본 DB는 덮어쓰지 않습니다.\n",
        )
    print(json.dumps(result, ensure_ascii=False))
    if args.command == "check" and not result["current"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
