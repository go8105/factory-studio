"""Transactional MFA. Return expected failures so callers commit attempts before raising.

Lock order: global account-management shared lock -> per-user advisory lock ->
user/session/factor/challenge rows. Never catch database errors and turn them into
successful authentication. All secret values are returned once, outside receipts.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from fs.common.config import get_settings
from fs.common.errors import ApiError
from fs.common.security import (
    hash_password,
    member_csrf_token,
    new_session_token,
    token_hash,
    verify_password,
)
from fs.core.company import lock_accounts
from fs.core.security.config import security_settings
from fs.core.security.crypto import (
    enrollment,
    new_recovery_codes,
    opaque_token,
    totp_step,
    unavailable,
)


def audit(c, user_id, action):
    c.execute(
        text("""INSERT INTO core.audit_event(actor_user_id,action,entity_kind,entity_key,summary,actor_kind,actor_key,scope_kind)
       VALUES(:u,:a,'app_user',:key,'{}'::jsonb,'MEMBER',:key,'GLOBAL')"""),
        {"u": user_id, "a": action, "key": str(user_id)},
    )


def failed():
    return ApiError(
        401, "AUTHENTICATION_FAILED", "인증 정보를 확인하고 다시 시도하세요."
    )


def user_lock(c, user_id):
    lock_accounts(c)
    c.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"fs.security.user:{user_id}"},
    )
    return (
        c.execute(
            text("SELECT * FROM core.app_user WHERE id=:u FOR UPDATE"), {"u": user_id}
        )
        .mappings()
        .one_or_none()
    )


def active_user(row):
    return row is not None and row["status"] == "active" and row["disabled_at"] is None


def factor(c, user_id, state="ACTIVE"):
    return (
        c.execute(
            text(
                "SELECT * FROM core.mfa_factor WHERE user_id=:u AND kind='TOTP' AND state=:s FOR UPDATE"
            ),
            {"u": user_id, "s": state},
        )
        .mappings()
        .one_or_none()
    )


def session(c, context, *, recent=False, allow_recovery=False):
    if context.user_id is None:
        return None, failed()
    user = user_lock(c, context.user_id)
    row = (
        c.execute(
            text("""SELECT * FROM core.auth_session WHERE user_id=:u AND token_hash=:t
        AND revoked_at IS NULL AND expires_at>clock_timestamp()
        AND (absolute_expires_at IS NULL OR absolute_expires_at>clock_timestamp()) FOR UPDATE"""),
            {"u": context.user_id, "t": token_hash(context.token)},
        )
        .mappings()
        .one_or_none()
    )
    if (
        not active_user(user)
        or row is None
        or row["security_version"] != user["security_version"]
    ):
        return None, failed()
    if row["assurance"] == "RECOVERY_LIMITED" and not allow_recovery:
        return None, ApiError(403, "RECOVERY_ONLY", "인증 앱을 다시 등록해 주세요.")
    if recent and (
        row["assurance"] != "MFA"
        or row["verified_at"] is None
        or datetime.now(UTC) - row["verified_at"] > timedelta(minutes=5)
    ):
        return None, ApiError(
            403, "STEP_UP_REQUIRED", "인증 앱 번호로 다시 확인해 주세요."
        )
    return row, None


def throttle(c, bucket, *, now, limit, window_seconds):
    start = datetime.fromtimestamp(
        int(now.timestamp()) // window_seconds * window_seconds, UTC
    )
    row = (
        c.execute(
            text("""INSERT INTO core.authentication_throttle(bucket_hash,window_started_at,fail_count,updated_at)
        VALUES(:b,:s,0,:n) ON CONFLICT(bucket_hash,window_started_at)
        DO UPDATE SET updated_at=EXCLUDED.updated_at RETURNING id,fail_count"""),
            {"b": bucket, "s": start, "n": now},
        )
        .mappings()
        .one()
    )
    if row["fail_count"] >= limit:
        return None, ApiError(
            429,
            "AUTHENTICATION_THROTTLED",
            "잠시 기다린 뒤 다시 시도하세요.",
            {"retryAt": (start + timedelta(seconds=window_seconds)).isoformat()},
        )
    return row["id"], None


def record_failure(c, ids):
    for id in ids:
        c.execute(
            text(
                "UPDATE core.authentication_throttle SET fail_count=fail_count+1,updated_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": id},
        )


def login_gate(c, login_id, password, network):
    from fs.core.security.crypto import throttle_bucket

    settings = security_settings()
    secret = get_settings().session_secret.encode()
    ids = []
    for namespace, value, limit in (
        ("account", login_id.strip().lower(), 10),
        ("network", network, 100),
    ):
        id, error = throttle(
            c,
            throttle_bucket(secret, namespace=namespace, value=value),
            now=datetime.now(UTC),
            limit=limit,
            window_seconds=600,
        )
        if error:
            return None, error
        ids.append(id)
    lookup = c.execute(
        text("SELECT id FROM core.app_user WHERE login_id=:l"),
        {"l": login_id.strip().lower()},
    ).scalar_one_or_none()
    user = user_lock(c, lookup) if lookup is not None else None
    # Perform a scrypt even for missing accounts; no cached enumeration timing path.
    dummy = (
        "scrypt$16384$8$1$MDAwMDAwMDAwMDAwMDAwMA==$"
        + "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMA=="
    )
    valid = verify_password(password, user["password_hash"] if user else dummy)
    if not active_user(user) or not valid:
        record_failure(c, ids)
        return None, failed()
    enrolled = factor(c, user["id"])
    if enrolled is None:
        previous = c.execute(
            text(
                "SELECT 1 FROM core.mfa_factor WHERE user_id=:u AND state='REVOKED' AND confirmed_at IS NOT NULL LIMIT 1"
            ),
            {"u": user["id"]},
        ).first()
        if previous:
            return None, ApiError(
                403,
                "RECOVERY_REQUIRED",
                "진행 중인 복구 화면에서 인증 앱을 다시 등록해 주세요.",
            )
        return {"mfaRequired": False}, None
    if settings.box is None:
        return None, unavailable()
    raw, hashed = opaque_token()
    c.execute(
        text("""INSERT INTO core.authentication_challenge
        (user_id,purpose,token_hash,state,security_version,attempt_count,expires_at,created_at)
        VALUES(:u,'LOGIN_MFA',:t,'PENDING',:v,0,clock_timestamp()+interval '5 minutes',clock_timestamp())"""),
        {"u": user["id"], "t": hashed, "v": user["security_version"]},
    )
    return {"mfaRequired": True, "challengeToken": raw}, None


def start_enrollment(c, context, password, *, recovery=False):
    _row, error = session(c, context, allow_recovery=recovery)
    if error:
        return None, error
    user = (
        c.execute(
            text("SELECT * FROM core.app_user WHERE id=:u"), {"u": context.user_id}
        )
        .mappings()
        .one()
    )
    from fs.core.security.crypto import throttle_bucket

    bucket = throttle_bucket(
        get_settings().session_secret.encode(),
        namespace="account",
        value=f"enroll:{context.user_id}",
    )
    id, error = throttle(c, bucket, now=datetime.now(UTC), limit=5, window_seconds=300)
    if error:
        return None, error
    if recovery and _row["assurance"] != "RECOVERY_LIMITED":
        return None, failed()
    if not recovery and not verify_password(password, user["password_hash"]):
        record_failure(c, [id])
        return None, failed()
    if factor(c, context.user_id):
        return None, ApiError(
            409, "STATE_CHANGED", "이미 등록되어 있습니다. 계정 보안 상태를 확인하세요."
        )
    box = security_settings().box
    if box is None:
        return None, unavailable()
    c.execute(
        text(
            "UPDATE core.mfa_factor SET state='REVOKED',revoked_at=clock_timestamp() WHERE user_id=:u AND state='PENDING'"
        ),
        {"u": context.user_id},
    )
    secret, uri = enrollment(user["login_id"])
    key_id, ciphertext = box.seal(secret, purpose="totp", owner=str(context.user_id))
    factor_id = c.execute(
        text("""INSERT INTO core.mfa_factor(user_id,kind,state,secret_ciphertext,encryption_key_id,version,pending_expires_at,created_at)
        VALUES(:u,'TOTP','PENDING',:s,:k,1,clock_timestamp()+interval '10 minutes',clock_timestamp()) RETURNING id"""),
        {"u": context.user_id, "s": ciphertext, "k": key_id},
    ).scalar_one()
    return {
        "factorId": str(factor_id),
        "setupKey": secret,
        "provisioningUri": uri,
        "expiresInSeconds": 600,
    }, None


def verify_factor(c, row, code):
    box = security_settings().box
    if box is None:
        return False
    secret = box.open(
        row["secret_ciphertext"],
        key_id=row["encryption_key_id"],
        purpose="totp",
        owner=str(row["user_id"]),
    )
    step = totp_step(
        secret, code, now=datetime.now(UTC), last_used_step=row["last_used_step"]
    )
    if step is None:
        return False
    c.execute(
        text("UPDATE core.mfa_factor SET last_used_step=:s WHERE id=:id"),
        {"s": step, "id": row["id"]},
    )
    return True


def issue_codes(c, user_id, factor_row):
    c.execute(
        text(
            "UPDATE core.recovery_code SET revoked_at=clock_timestamp() WHERE user_id=:u AND used_at IS NULL AND revoked_at IS NULL"
        ),
        {"u": user_id},
    )
    codes = new_recovery_codes()
    for code in codes:
        c.execute(
            text("""INSERT INTO core.recovery_code(user_id,factor_id,factor_version,code_hash,created_at)
          VALUES(:u,:f,:v,:h,clock_timestamp())"""),
            {
                "u": user_id,
                "f": factor_row["id"],
                "v": factor_row["version"],
                "h": hash_password(code),
            },
        )
    return codes


def confirm_enrollment(c, context, factor_id, code, *, recovery=False):
    _row, error = session(c, context, allow_recovery=recovery)
    if error:
        return None, error
    if recovery and _row["assurance"] != "RECOVERY_LIMITED":
        return None, failed()
    pending = factor(c, context.user_id, "PENDING")
    if (
        pending is None
        or str(pending["id"]) != factor_id
        or pending["pending_expires_at"] <= datetime.now(UTC)
    ):
        return None, failed()
    from fs.core.security.crypto import throttle_bucket

    bucket = throttle_bucket(
        get_settings().session_secret.encode(),
        namespace="account",
        value=f"confirm:{context.user_id}",
    )
    id, error = throttle(c, bucket, now=datetime.now(UTC), limit=5, window_seconds=300)
    if error:
        return None, error
    if not verify_factor(c, pending, code):
        record_failure(c, [id])
        return None, failed()
    c.execute(
        text(
            "UPDATE core.mfa_factor SET state='ACTIVE',confirmed_at=clock_timestamp() WHERE id=:id"
        ),
        {"id": pending["id"]},
    )
    codes = issue_codes(c, context.user_id, pending)
    # Enrollment does not silently promote the current PASSWORD session.
    c.execute(
        text(
            "UPDATE core.app_user SET security_version=security_version+1 WHERE id=:u"
        ),
        {"u": context.user_id},
    )
    c.execute(
        text(
            "UPDATE core.auth_session SET revoked_at=clock_timestamp() WHERE user_id=:u AND revoked_at IS NULL"
        ),
        {"u": context.user_id},
    )
    audit(c, context.user_id, "security.mfa.enrolled")
    return {"recoveryCodes": codes, "reauthenticationRequired": True}, None


def verify_login(c, challenge_token, code):
    lookup = c.execute(
        text("SELECT user_id FROM core.authentication_challenge WHERE token_hash=:t"),
        {"t": token_hash(challenge_token)},
    ).scalar_one_or_none()
    if lookup is None:
        return None, failed()
    user = user_lock(c, lookup)
    challenge = (
        c.execute(
            text(
                "SELECT * FROM core.authentication_challenge WHERE token_hash=:t FOR UPDATE"
            ),
            {"t": token_hash(challenge_token)},
        )
        .mappings()
        .one()
    )
    if (
        not active_user(user)
        or challenge["state"] != "PENDING"
        or challenge["purpose"] != "LOGIN_MFA"
        or challenge["security_version"] != user["security_version"]
    ):
        return None, failed()
    if challenge["expires_at"] <= datetime.now(UTC):
        c.execute(
            text(
                "UPDATE core.authentication_challenge SET state='EXPIRED' WHERE id=:id"
            ),
            {"id": challenge["id"]},
        )
        return None, failed()
    if challenge["attempt_count"] >= 5:
        return None, ApiError(
            429, "AUTHENTICATION_THROTTLED", "로그인부터 다시 시작해 주세요."
        )
    from fs.core.security.crypto import throttle_bucket

    bucket = throttle_bucket(
        get_settings().session_secret.encode(),
        namespace="account",
        value=f"otp:{lookup}",
    )
    throttle_id, error = throttle(
        c, bucket, now=datetime.now(UTC), limit=5, window_seconds=300
    )
    if error:
        return None, error
    active = factor(c, lookup)
    recovery = False
    valid = False
    if active is not None:
        if len(code) == 32 and all(ch in "0123456789abcdef" for ch in code):
            codes = (
                c.execute(
                    text(
                        "SELECT * FROM core.recovery_code WHERE user_id=:u AND factor_id=:f AND factor_version=:v AND used_at IS NULL AND revoked_at IS NULL FOR UPDATE"
                    ),
                    {"u": lookup, "f": active["id"], "v": active["version"]},
                )
                .mappings()
                .all()
            )
            matched = next(
                (
                    candidate
                    for candidate in codes
                    if verify_password(code, candidate["code_hash"])
                ),
                None,
            )
            if matched:
                c.execute(
                    text(
                        "UPDATE core.recovery_code SET used_at=clock_timestamp() WHERE id=:id"
                    ),
                    {"id": matched["id"]},
                )
                recovery = valid = True
        else:
            valid = verify_factor(c, active, code)
    if not valid:
        record_failure(c, [throttle_id])
        c.execute(
            text(
                "UPDATE core.authentication_challenge SET attempt_count=attempt_count+1,state=CASE WHEN attempt_count>=4 THEN 'LOCKED' ELSE state END WHERE id=:id"
            ),
            {"id": challenge["id"]},
        )
        return None, failed()
    c.execute(
        text(
            "UPDATE core.authentication_challenge SET state='CONSUMED',consumed_at=clock_timestamp() WHERE id=:id"
        ),
        {"id": challenge["id"]},
    )
    version = user["security_version"]
    if recovery:
        c.execute(
            text(
                "UPDATE core.mfa_factor SET state='REVOKED',revoked_at=clock_timestamp() WHERE user_id=:u AND state IN ('ACTIVE','PENDING')"
            ),
            {"u": lookup},
        )
        c.execute(
            text(
                "UPDATE core.recovery_code SET revoked_at=clock_timestamp() WHERE user_id=:u AND used_at IS NULL AND revoked_at IS NULL"
            ),
            {"u": lookup},
        )
        version = c.execute(
            text(
                "UPDATE core.app_user SET security_version=security_version+1 WHERE id=:u RETURNING security_version"
            ),
            {"u": lookup},
        ).scalar_one()
        c.execute(
            text(
                "UPDATE core.auth_session SET revoked_at=clock_timestamp() WHERE user_id=:u AND revoked_at IS NULL"
            ),
            {"u": lookup},
        )
    token = new_session_token("m")
    csrf = member_csrf_token(get_settings().session_secret, token)
    c.execute(
        text("""INSERT INTO core.auth_session(user_id,token_hash,csrf_token_hash,expires_at,assurance,verified_at,security_version,auth_method,absolute_expires_at)
       VALUES(:u,:t,:csrf,clock_timestamp()+:ttl*interval '1 second',:assurance,clock_timestamp(),:v,:method,clock_timestamp()+:absolute*interval '1 second')"""),
        {
            "u": lookup,
            "t": token_hash(token),
            "csrf": token_hash(csrf),
            "v": version,
            "ttl": 900 if recovery else 1800,
            "absolute": 900 if recovery else 28800,
            "assurance": "RECOVERY_LIMITED" if recovery else "MFA",
            "method": "RECOVERY" if recovery else "TOTP",
        },
    )
    audit(c, lookup, "security.recovery.started" if recovery else "security.mfa.login")
    return {"token": token, "csrfToken": csrf, "recoveryOnly": recovery}, None


def security_summary(c, context):
    row, error = session(c, context)
    if error:
        return None, error
    active = factor(c, context.user_id)
    remaining = c.execute(
        text(
            "SELECT count(*) FROM core.recovery_code WHERE user_id=:u AND used_at IS NULL AND revoked_at IS NULL"
        ),
        {"u": context.user_id},
    ).scalar_one()
    return {
        "mfaRegistered": active is not None,
        "recoveryCodesRemaining": remaining,
        "assurance": row["assurance"],
        "verifiedAt": row["verified_at"].isoformat() if row["verified_at"] else None,
    }, None


def step_up(c, context, code):
    row, error = session(c, context)
    if error:
        return None, error
    from fs.core.security.crypto import throttle_bucket

    id, error = throttle(
        c,
        throttle_bucket(
            get_settings().session_secret.encode(),
            namespace="account",
            value=f"otp:{context.user_id}",
        ),
        now=datetime.now(UTC),
        limit=5,
        window_seconds=300,
    )
    if error:
        return None, error
    active = factor(c, context.user_id)
    if active is None or not verify_factor(c, active, code):
        record_failure(c, [id])
        return None, failed()
    c.execute(
        text(
            "UPDATE core.auth_session SET assurance='MFA',auth_method='TOTP',verified_at=clock_timestamp(),absolute_expires_at=coalesce(absolute_expires_at,clock_timestamp()+interval '8 hours') WHERE id=:id"
        ),
        {"id": row["id"]},
    )
    audit(c, context.user_id, "security.step_up.verified")
    return {"verified": True}, None


def rotate_codes(c, context):
    _row, error = session(c, context, recent=True)
    if error:
        return None, error
    active = factor(c, context.user_id)
    if active is None:
        return None, failed()
    active = (
        c.execute(
            text(
                "UPDATE core.mfa_factor SET version=version+1 WHERE id=:id RETURNING *"
            ),
            {"id": active["id"]},
        )
        .mappings()
        .one()
    )
    codes = issue_codes(c, context.user_id, active)
    c.execute(
        text(
            "UPDATE core.app_user SET security_version=security_version+1 WHERE id=:u"
        ),
        {"u": context.user_id},
    )
    c.execute(
        text(
            "UPDATE core.auth_session SET revoked_at=clock_timestamp() WHERE user_id=:u AND revoked_at IS NULL"
        ),
        {"u": context.user_id},
    )
    audit(c, context.user_id, "security.recovery_codes.rotated")
    return {"recoveryCodes": codes, "reauthenticationRequired": True}, None


def list_sessions(c, context):
    current, error = session(c, context)
    if error:
        return None, error
    values = (
        c.execute(
            text("""SELECT id,created_at,expires_at,absolute_expires_at,auth_method FROM core.auth_session
        WHERE user_id=:u AND revoked_at IS NULL AND expires_at>clock_timestamp()
        AND (absolute_expires_at IS NULL OR absolute_expires_at>clock_timestamp())
        AND security_version=:v ORDER BY created_at DESC,id DESC LIMIT 100"""),
            {"u": context.user_id, "v": current["security_version"]},
        )
        .mappings()
        .all()
    )
    return {
        "sessions": [
            {
                "id": str(row["id"]),
                "current": row["id"] == current["id"],
                "createdAt": row["created_at"].isoformat(),
                "expiresAt": min(
                    row["expires_at"], row["absolute_expires_at"] or row["expires_at"]
                ).isoformat(),
                "method": row["auth_method"],
            }
            for row in values
        ]
    }, None


def revoke_other_sessions(c, context):
    current, error = session(c, context, recent=True)
    if error:
        return None, error
    count = c.execute(
        text(
            "UPDATE core.auth_session SET revoked_at=clock_timestamp() WHERE user_id=:u AND id<>:id AND revoked_at IS NULL"
        ),
        {"u": context.user_id, "id": current["id"]},
    ).rowcount
    version = c.execute(
        text(
            "UPDATE core.app_user SET security_version=security_version+1 WHERE id=:u RETURNING security_version"
        ),
        {"u": context.user_id},
    ).scalar_one()
    c.execute(
        text("UPDATE core.auth_session SET security_version=:v WHERE id=:id"),
        {"v": version, "id": current["id"]},
    )
    audit(c, context.user_id, "security.other_sessions.revoked")
    return {"revokedCount": count}, None
