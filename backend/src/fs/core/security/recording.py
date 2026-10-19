"""Authentication-owned state recording. Never copy credentials or business data."""

import json
import os

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from fs.common.errors import ApiError
from fs.core.backup import BackupError, private_file
from fs.core.security.journal import append

KINDS = {"core.security.intent.v1", "hr.users.intent.v1"}


def configured():
    directory = os.environ.get("FS_GW_IDENTITY_JOURNAL_DIR")
    key_path = os.environ.get("FS_GW_IDENTITY_JOURNAL_KEY_FILE")
    if not directory and not key_path:
        return None
    try:
        if not directory or not key_path:
            raise BackupError("기록 설정이 불완전합니다.")
        return directory, private_file(key_path, size=32).read_bytes()
    except BackupError, OSError, ValueError:
        raise unavailable() from None


def unavailable():
    return ApiError(
        503,
        "SECURITY_JOURNAL_UNAVAILABLE",
        "보안 변경 기록을 저장하지 못해 변경을 적용하지 않았습니다. 운영 담당자에게 문의하세요.",
    )


def subject(payload):
    return {
        k: payload[k]
        for k in ("coverage", "operation", "userId", "workspaceId", "generationId")
        if k in payload
    }


def persist(c, payload, *, actor_id=None, config=None):
    config = config or configured()
    if config is None:
        return
    try:
        from fs.core.security.transaction_proof import capture

        payload = {**payload, **capture(c)}
        digest = append(config[0], config[1], payload)
        c.execute(
            text(
                "INSERT INTO core.audit_event(actor_user_id,action,entity_kind,entity_key,summary,actor_kind,actor_key,scope_kind) "
                "VALUES(:actor,'security.journal.confirmation','security_journal',:digest,CAST(:summary AS jsonb),:kind,:key,'GLOBAL')"
            ),
            {
                "actor": actor_id,
                "digest": digest,
                "summary": json.dumps({"subject": subject(payload)}),
                "kind": "MEMBER" if actor_id is not None else "SYSTEM",
                "key": str(actor_id) if actor_id is not None else "security-service",
            },
        )
    except BackupError, OSError, ValueError, TypeError, SQLAlchemyError:
        raise unavailable() from None


def capture_user(c, user_id):
    queries = {
        "user": "SELECT id,status,disabled_at IS NOT NULL AS disabled,security_version FROM core.app_user WHERE id=:u",
        "roles": "SELECT role_id FROM core.user_role WHERE user_id=:u ORDER BY role_id",
        "members": "SELECT id,workspace_id,role,is_active FROM core.company_member WHERE user_id=:u ORDER BY id",
        "factors": "SELECT id,state,version,last_used_step FROM core.mfa_factor WHERE user_id=:u ORDER BY id",
        "codes": "SELECT id,factor_id,used_at IS NOT NULL AS used,revoked_at IS NOT NULL AS revoked FROM core.recovery_code WHERE user_id=:u ORDER BY id",
        "sessions": "SELECT id,assurance,security_version,revoked_at IS NOT NULL AS revoked FROM core.auth_session WHERE user_id=:u ORDER BY id",
        "challenges": "SELECT id,purpose,state,security_version,attempt_count,expires_at::text AS expires FROM core.authentication_challenge WHERE user_id=:u ORDER BY id",
        "sso": "SELECT id,state,version FROM core.sso_identity WHERE user_id=:u ORDER BY id",
    }
    return {
        kind: [dict(r) for r in c.execute(text(query), {"u": user_id}).mappings()]
        for kind, query in queries.items()
    }


def record_user(c, user_id, operation, *, system=False):
    config = configured()
    if config is None:
        return
    persist(
        c,
        {
            "coverage": "core.security.intent.v1",
            "userId": user_id,
            "operation": operation,
            "snapshot": capture_user(c, user_id),
        },
        actor_id=None if system else user_id,
        config=config,
    )


def record_throttles(c, ids):
    config = configured()
    if config is None:
        return
    rows = c.execute(
        text(
            "SELECT id,window_started_at::text AS window,fail_count,locked_until::text AS locked FROM core.authentication_throttle WHERE id=ANY(:ids) ORDER BY id"
        ),
        {"ids": ids},
    ).mappings()
    persist(
        c,
        {
            "coverage": "core.security.intent.v1",
            "userId": None,
            "operation": "security.throttle.changed",
            "snapshot": {"throttles": [dict(r) for r in rows]},
        },
        config=config,
    )


def confirmed_digests(c, records):
    if not records:
        return set()
    rows = c.execute(
        text(
            "SELECT entity_key,summary FROM core.audit_event WHERE action='security.journal.confirmation' AND entity_kind='security_journal' AND entity_key=ANY(:digests)"
        ),
        {"digests": [r["digest"] for r in records]},
    ).mappings()
    matches = {}
    for row in rows:
        if isinstance(row["summary"], dict):
            matches.setdefault(row["entity_key"], []).append(
                row["summary"].get("subject")
            )
    return {
        r["digest"]
        for r in records
        if subject(r["payload"]) in matches.get(r["digest"], [])
    }


def confirmed_count(c, records):
    return len(confirmed_digests(c, records))
