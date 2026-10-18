"""Emergency credentials owned by core. GW validates administrator eligibility.

Existing RECOVERY challenges distinguish kit/grant with a provider marker and
purpose-bound encrypted payload. No business FKs, plaintext credentials or receipt.
"""

import hmac
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text

from fs.common.errors import ApiError
from fs.common.security import token_hash
from fs.core.security import service
from fs.core.security.config import security_settings
from fs.core.security.crypto import opaque_token, unavailable

ID = r"^[1-9][0-9]{0,18}$"


class EmergencyKit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    version: Literal[1]
    user_id: str = Field(alias="userId", pattern=ID)
    company_id: str = Field(alias="companyId", pattern=ID)
    generation_id: str = Field(alias="generationId", pattern=ID)
    person_id: str = Field(alias="personId", pattern=ID)
    kit_id: str = Field(alias="kitId", pattern=ID)
    kit_secret: str = Field(
        alias="kitSecret", pattern=r"^[A-Za-z0-9_-]{43}$", repr=False
    )

    @field_validator("user_id", "company_id", "generation_id", "person_id", "kit_id")
    @classmethod
    def bounded_id(cls, value, info):
        if int(value) > (
            2147483647 if info.field_name == "company_id" else 9223372036854775807
        ):
            raise ValueError("식별자 범위를 확인하세요.")
        return value


def system_audit(c, user_id, action, summary, *, operator_uid=None):
    actor = (
        f"local-uid:{operator_uid}" if operator_uid is not None else "security-service"
    )
    c.execute(
        text("""INSERT INTO core.audit_event(action,entity_kind,entity_key,summary,actor_kind,actor_key,scope_kind)
        VALUES(:a,'app_user',:u,CAST(:summary AS jsonb),'SYSTEM',:actor,'GLOBAL')"""),
        {
            "a": action,
            "u": str(user_id),
            "summary": json.dumps(summary),
            "actor": actor,
        },
    )


def kit_marker(company_id, operation_key=None):
    prefix = f"gw-kit:{company_id}:"
    return prefix + token_hash(operation_key)[:32] if operation_key else prefix


def grant_marker(company_id):
    return f"gw-grant:{company_id}"


def issue_kit(c, ctx, person_id, reason, operation_key):
    user = c.execute(
        text("SELECT security_version FROM core.app_user WHERE id=:u"),
        {"u": ctx.user_id},
    ).scalar_one()
    box = security_settings().box
    if box is None:
        return None, unavailable()
    marker = kit_marker(ctx.workspace_id, operation_key)
    prior = (
        c.execute(
            text(
                "SELECT * FROM core.authentication_challenge WHERE user_id=:u AND purpose='RECOVERY' AND provider_key=:p ORDER BY id DESC LIMIT 1 FOR UPDATE"
            ),
            {"u": ctx.user_id, "p": marker},
        )
        .mappings()
        .one_or_none()
    )
    if prior:
        old = json.loads(
            box.open(
                prior["protected_payload"],
                key_id=prior["encryption_key_id"],
                purpose="emergency-kit",
                owner=str(ctx.user_id),
            )
        )
        if old.get("operationHash") == token_hash(operation_key):
            return None, ApiError(
                409,
                "ONE_TIME_RESPONSE_UNAVAILABLE",
                "발급 결과는 다시 표시하지 않습니다. 준비 상태를 확인하고 필요하면 새 문서를 발급하세요.",
            )
    error = service.issuance_quota(c, ctx.user_id, "emergency-kit", limit=3)
    if error:
        return None, error
    raw, hashed = opaque_token()
    payload = {
        "kind": "EMERGENCY_KIT",
        "companyId": str(ctx.workspace_id),
        "generationId": str(ctx.generation_id),
        "personId": str(person_id),
        "operationHash": token_hash(operation_key),
    }
    key_id, encrypted = box.seal(
        json.dumps(payload), purpose="emergency-kit", owner=str(ctx.user_id)
    )
    c.execute(
        text(
            "UPDATE core.authentication_challenge SET state='EXPIRED' WHERE user_id=:u AND purpose='RECOVERY' AND provider_key LIKE :p AND state='PENDING'"
        ),
        {"u": ctx.user_id, "p": kit_marker(ctx.workspace_id) + "%"},
    )
    c.execute(
        text(
            "UPDATE core.authentication_challenge SET state='EXPIRED' WHERE user_id=:u AND purpose='RECOVERY' AND provider_key=:p AND state='PENDING'"
        ),
        {"u": ctx.user_id, "p": grant_marker(ctx.workspace_id)},
    )
    row = (
        c.execute(
            text("""INSERT INTO core.authentication_challenge(user_id,session_id,purpose,token_hash,state,security_version,provider_key,protected_payload,encryption_key_id,attempt_count,expires_at,created_at)
        VALUES(:u,NULL,'RECOVERY',:hash,'PENDING',:v,:marker,:payload,:key,0,clock_timestamp()+interval '365 days',clock_timestamp()) RETURNING id,expires_at"""),
            {
                "u": ctx.user_id,
                "hash": hashed,
                "v": user,
                "marker": marker,
                "payload": encrypted,
                "key": key_id,
            },
        )
        .mappings()
        .one()
    )
    service.audit(c, ctx.user_id, "security.emergency_kit.issued")
    system_audit(
        c,
        ctx.user_id,
        "security.emergency_kit.scope",
        {"companyId": str(ctx.workspace_id), "kitId": str(row["id"]), "reason": reason},
    )
    return {
        "kit": {
            "version": 1,
            "userId": str(ctx.user_id),
            **{k: payload[k] for k in ("companyId", "generationId", "personId")},
            "kitId": str(row["id"]),
            "kitSecret": raw,
        },
        "expiresAt": row["expires_at"].isoformat(),
    }, None


def summary(c, user_id, company_id):
    row = (
        c.execute(
            text("""SELECT a.id,a.created_at,a.expires_at,a.state,a.security_version=u.security_version AS current
        FROM core.authentication_challenge a JOIN core.app_user u ON u.id=a.user_id
        WHERE a.user_id=:u AND a.purpose='RECOVERY' AND a.provider_key LIKE :p ORDER BY a.id DESC LIMIT 1"""),
            {"u": user_id, "p": kit_marker(company_id) + "%"},
        )
        .mappings()
        .one_or_none()
    )
    return {
        "prepared": bool(
            row
            and row["current"]
            and row["state"] == "PENDING"
            and row["expires_at"] > service.database_now(c)
        ),
        "expiresAt": row["expires_at"].isoformat() if row else None,
    }


def approve(c, kit: EmergencyKit, operator_uid: int, reason: str):
    """Caller holds company/account/per-user locks and current GW role."""
    user = (
        c.execute(
            text("SELECT * FROM core.app_user WHERE id=:u FOR UPDATE"),
            {"u": int(kit.user_id)},
        )
        .mappings()
        .one_or_none()
    )
    row = (
        c.execute(
            text(
                "SELECT * FROM core.authentication_challenge WHERE id=:id AND user_id=:u AND purpose='RECOVERY' AND provider_key LIKE :p FOR UPDATE"
            ),
            {
                "id": int(kit.kit_id),
                "u": int(kit.user_id),
                "p": kit_marker(kit.company_id) + "%",
            },
        )
        .mappings()
        .one_or_none()
    )
    if (
        not service.active_user(user)
        or row is None
        or row["state"] != "PENDING"
        or row["security_version"] != user["security_version"]
    ):
        return None, service.failed()
    if row["expires_at"] <= service.database_now(c):
        c.execute(
            text(
                "UPDATE core.authentication_challenge SET state='EXPIRED' WHERE id=:id"
            ),
            {"id": row["id"]},
        )
        return None, service.failed()
    if not hmac.compare_digest(row["token_hash"], token_hash(kit.kit_secret)):
        c.execute(
            text(
                "UPDATE core.authentication_challenge SET attempt_count=attempt_count+1,state=CASE WHEN attempt_count>=4 THEN 'LOCKED' ELSE state END WHERE id=:id"
            ),
            {"id": row["id"]},
        )
        system_audit(
            c,
            int(kit.user_id),
            "security.emergency_kit.denied",
            {"kitId": kit.kit_id},
            operator_uid=operator_uid,
        )
        return None, service.failed()
    box = security_settings().box
    if box is None:
        return None, unavailable()
    payload = json.loads(
        box.open(
            row["protected_payload"],
            key_id=row["encryption_key_id"],
            purpose="emergency-kit",
            owner=kit.user_id,
        )
    )
    expected = {
        "kind": "EMERGENCY_KIT",
        "companyId": kit.company_id,
        "generationId": kit.generation_id,
        "personId": kit.person_id,
    }
    if any(payload.get(k) != v for k, v in expected.items()):
        return None, service.failed()
    raw, hashed = opaque_token()
    payload = expected | {
        "kind": "EMERGENCY_GRANT",
        "kitId": kit.kit_id,
        "operatorUid": operator_uid,
        "reason": reason,
    }
    key_id, encrypted = box.seal(
        json.dumps(payload), purpose="emergency-grant", owner=kit.user_id
    )
    c.execute(
        text(
            "UPDATE core.authentication_challenge SET state='CONSUMED',consumed_at=clock_timestamp() WHERE id=:id"
        ),
        {"id": row["id"]},
    )
    grant = (
        c.execute(
            text("""INSERT INTO core.authentication_challenge(user_id,purpose,token_hash,state,security_version,provider_key,protected_payload,encryption_key_id,attempt_count,expires_at,created_at)
        VALUES(:u,'RECOVERY',:hash,'PENDING',:v,:provider,:payload,:key,0,clock_timestamp()+interval '15 minutes',clock_timestamp()) RETURNING id,expires_at"""),
            {
                "u": int(kit.user_id),
                "hash": hashed,
                "provider": grant_marker(kit.company_id),
                "v": user["security_version"],
                "payload": encrypted,
                "key": key_id,
            },
        )
        .mappings()
        .one()
    )
    system_audit(
        c,
        int(kit.user_id),
        "security.emergency.approved",
        {
            "companyId": kit.company_id,
            "kitId": kit.kit_id,
            "grantId": str(grant["id"]),
            "reason": reason,
        },
        operator_uid=operator_uid,
    )
    return {"grantToken": raw, "expiresAt": grant["expires_at"].isoformat()}, None


def peek_grant(c, raw):
    row = (
        c.execute(
            text(
                "SELECT * FROM core.authentication_challenge WHERE token_hash=:t AND purpose='RECOVERY' AND provider_key LIKE 'gw-grant:%'"
            ),
            {"t": token_hash(raw)},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    box = security_settings().box
    if box is None:
        raise unavailable()
    payload = json.loads(
        box.open(
            row["protected_payload"],
            key_id=row["encryption_key_id"],
            purpose="emergency-grant",
            owner=str(row["user_id"]),
        )
    )
    return {"userId": row["user_id"], **payload}


def fail_login(c, challenge_id):
    c.execute(
        text(
            "UPDATE core.authentication_challenge SET attempt_count=attempt_count+1,state=CASE WHEN attempt_count>=4 THEN 'LOCKED' ELSE state END WHERE id=:id AND state='PENDING'"
        ),
        {"id": challenge_id},
    )
    return None, service.failed()


def login_owner(c, login_token):
    return c.execute(
        text(
            "SELECT user_id FROM core.authentication_challenge WHERE token_hash=:t AND purpose='LOGIN_MFA'"
        ),
        {"t": token_hash(login_token)},
    ).scalar_one_or_none()


def reject_login(c, login_token):
    user_id = c.execute(
        text(
            "SELECT user_id FROM core.authentication_challenge WHERE token_hash=:t AND purpose='LOGIN_MFA'"
        ),
        {"t": token_hash(login_token)},
    ).scalar_one_or_none()
    if user_id is None:
        return None, service.failed()
    user = service.user_lock(c, user_id)
    row = (
        c.execute(
            text(
                "SELECT * FROM core.authentication_challenge WHERE token_hash=:t FOR UPDATE"
            ),
            {"t": token_hash(login_token)},
        )
        .mappings()
        .one()
    )
    if row["state"] == "LOCKED":
        return None, ApiError(
            429,
            "AUTHENTICATION_THROTTLED",
            "잠시 기다린 뒤 로그인부터 다시 시작하세요.",
        )
    if (
        not service.active_user(user)
        or row["state"] != "PENDING"
        or row["expires_at"] <= service.database_now(c)
        or row["security_version"] != user["security_version"]
    ):
        return None, service.failed()
    error = service.issuance_quota(c, user_id, "emergency-redeem", limit=5, seconds=300)
    return (None, error) if error else fail_login(c, row["id"])


def redeem(c, login_token, grant_token, *, user_id):
    """Caller rechecks current GW eligibility under company/account/per-user locks."""
    login = (
        c.execute(
            text(
                "SELECT * FROM core.authentication_challenge WHERE token_hash=:t FOR UPDATE"
            ),
            {"t": token_hash(login_token)},
        )
        .mappings()
        .one_or_none()
    )
    if (
        login is None
        or login["user_id"] != user_id
        or login["purpose"] != "LOGIN_MFA"
        or login["state"] != "PENDING"
        or login["expires_at"] <= service.database_now(c)
    ):
        return None, service.failed()
    user = (
        c.execute(
            text("SELECT * FROM core.app_user WHERE id=:u FOR UPDATE"),
            {"u": login["user_id"]},
        )
        .mappings()
        .one_or_none()
    )
    if (
        not service.active_user(user)
        or login["security_version"] != user["security_version"]
    ):
        return fail_login(c, login["id"])
    error = service.issuance_quota(
        c, user["id"], "emergency-redeem", limit=5, seconds=300
    )
    if error:
        return None, error
    grant = (
        c.execute(
            text(
                "SELECT * FROM core.authentication_challenge WHERE token_hash=:t AND user_id=:u AND purpose='RECOVERY' AND provider_key LIKE 'gw-grant:%' FOR UPDATE"
            ),
            {"t": token_hash(grant_token), "u": user["id"]},
        )
        .mappings()
        .one_or_none()
    )
    if (
        grant is None
        or grant["state"] != "PENDING"
        or grant["security_version"] != user["security_version"]
        or grant["expires_at"] <= service.database_now(c)
    ):
        return fail_login(c, login["id"])
    c.execute(
        text(
            "UPDATE core.authentication_challenge SET state='CONSUMED',consumed_at=clock_timestamp() WHERE id IN (:login,:grant)"
        ),
        {"login": login["id"], "grant": grant["id"]},
    )
    version = service.begin_recovery(c, user["id"])
    result = service.issue_session(c, user["id"], version, recovery=True)
    service.audit(c, user["id"], "security.emergency.redeemed")
    return result, None
