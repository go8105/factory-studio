"""MFA transaction integration against an isolated *_test PostgreSQL database."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pyotp
import pytest
from cryptography.fernet import Fernet
from fs.common.auth import AuthContext
from fs.common.security import hash_password, token_hash
from fs.core.security import service
from sqlalchemy import text


@pytest.fixture
def identity(db_engine, monkeypatch):
    import json

    monkeypatch.setenv("FS_SECURITY_MODE", "TEAM_TEST")
    monkeypatch.setenv(
        "FS_SECURITY_KEYS", json.dumps({"v1": Fernet.generate_key().decode()})
    )
    monkeypatch.setenv("FS_SECURITY_KEY_ID", "v1")
    monkeypatch.setenv("SESSION_SECRET", "synthetic-secret-only-for-transaction-tests")
    token, password, login = "m_" + uuid4().hex, uuid4().hex, "synthetic-" + uuid4().hex
    with db_engine.begin() as c:
        user = c.execute(
            text(
                "INSERT INTO core.app_user(login_id,password_hash,display_name) VALUES(:l,:p,'합성 직원') RETURNING id"
            ),
            {"l": login, "p": hash_password(password)},
        ).scalar_one()
        c.execute(
            text(
                "INSERT INTO core.auth_session(user_id,token_hash,csrf_token_hash,expires_at) VALUES(:u,:t,'synthetic-csrf',clock_timestamp()+interval '30 minutes')"
            ),
            {"u": user, "t": token_hash(token)},
        )
    with db_engine.begin() as c:
        workspace = c.execute(
            text(
                "INSERT INTO core.workspace(owner_user_id,workspace_kind) VALUES(:u,'MEMBER') RETURNING id"
            ),
            {"u": user},
        ).scalar_one()
        generation = c.execute(
            text(
                "INSERT INTO core.data_generation(workspace_id,seed_version,seed_date,status,activated_at) VALUES(:w,'synthetic-ready02',current_date,'active',clock_timestamp()) RETURNING id"
            ),
            {"w": workspace},
        ).scalar_one()
        c.execute(
            text("UPDATE core.workspace SET active_generation_id=:g WHERE id=:w"),
            {"g": generation, "w": workspace},
        )
    context = AuthContext(
        "MEMBER", str(user), workspace, generation, user, frozenset(), token
    )
    yield db_engine, context, password, login
    with db_engine.begin() as c:
        for table in (
            "recovery_code",
            "authentication_challenge",
            "mfa_factor",
            "auth_session",
            "sso_identity",
        ):
            c.execute(text(f"DELETE FROM core.{table} WHERE user_id=:u"), {"u": user})
        c.execute(
            text("DELETE FROM core.audit_event WHERE actor_user_id=:u"), {"u": user}
        )
        c.execute(
            text("DELETE FROM core.request_receipt WHERE workspace_id=:w"),
            {"w": workspace},
        )
        c.execute(
            text("UPDATE core.workspace SET active_generation_id=NULL WHERE id=:w"),
            {"w": workspace},
        )
        c.execute(
            text("DELETE FROM core.data_generation WHERE workspace_id=:w"),
            {"w": workspace},
        )
        c.execute(text("DELETE FROM core.workspace WHERE id=:w"), {"w": workspace})
        c.execute(text("DELETE FROM core.app_user WHERE id=:u"), {"u": user})


def enroll(identity):
    engine, context, password, _ = identity
    with engine.begin() as c:
        started, error = service.start_enrollment(c, context, password)
    assert error is None
    code = pyotp.TOTP(started["setupKey"]).now()
    with engine.begin() as c:
        confirmed, error = service.confirm_enrollment(
            c, context, started["factorId"], code
        )
    assert error is None and len(confirmed["recoveryCodes"]) == 8
    return started, confirmed


def test_enrollment_invalidates_sessions_and_only_hashes_codes(identity):
    started, confirmed = enroll(identity)
    engine, context, _, _ = identity
    with engine.begin() as c:
        summary, error = service.security_summary(c, context)
        assert summary is None and error.status_code == 401
        stored = c.execute(
            text(
                "SELECT secret_ciphertext,last_used_step FROM core.mfa_factor WHERE user_id=:u AND state='ACTIVE'"
            ),
            {"u": context.user_id},
        ).one()
        assert started["setupKey"] not in stored[0] and stored[1] is not None
        hashes = (
            c.execute(
                text("SELECT code_hash FROM core.recovery_code WHERE user_id=:u"),
                {"u": context.user_id},
            )
            .scalars()
            .all()
        )
        assert len(hashes) == 8 and all(x.startswith("scrypt$") for x in hashes)
        assert not any(
            code in hashed for code in confirmed["recoveryCodes"] for hashed in hashes
        )


def next_code(engine, user, seed):
    # Independent requests use the same next allowed real-time window without sleeping.
    with engine.begin() as c:
        c.execute(
            text("UPDATE core.mfa_factor SET last_used_step=:s WHERE user_id=:u"),
            {"s": int(datetime.now(UTC).timestamp()) // 30 - 1, "u": user},
        )
    return pyotp.TOTP(seed).now()


def test_password_alone_creates_challenge_and_racing_otp_only_one_session(identity):
    started, _ = enroll(identity)
    engine, context, password, login = identity
    with engine.begin() as c:
        gate, error = service.login_gate(
            c, login, password, "synthetic-network-" + login
        )
    assert error is None and gate["mfaRequired"]
    code = next_code(engine, context.user_id, started["setupKey"])

    def attempt(_):
        with engine.begin() as c:
            return service.verify_login(c, gate["challengeToken"], code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sum(error is None for _, error in results) == 1
    with engine.connect() as c:
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM core.auth_session WHERE user_id=:u AND revoked_at IS NULL AND assurance='MFA'"
                ),
                {"u": context.user_id},
            ).scalar_one()
            == 1
        )


def test_failed_otp_persists_and_new_challenge_does_not_reset_limit(identity):
    started, _ = enroll(identity)
    engine, _, password, login = identity

    def gate():
        with engine.begin() as c:
            result, error = service.login_gate(
                c, login, password, "synthetic-network-" + login
            )
        assert error is None
        return result["challengeToken"]

    first = gate()
    valid = {
        pyotp.TOTP(started["setupKey"]).at(datetime.now(UTC).timestamp() + offset * 30)
        for offset in (-1, 0, 1)
    }
    wrong = next(f"{n:06}" for n in range(10) if f"{n:06}" not in valid)
    for _ in range(5):
        with engine.begin() as c:
            _, error = service.verify_login(c, first, wrong)
        assert error.status_code == 401
    with engine.begin() as c:
        _, error = service.verify_login(c, first, wrong)
    assert error.status_code == 429
    second = gate()
    with engine.begin() as c:
        _, error = service.verify_login(c, second, wrong)
    assert error.status_code == 429
    with engine.connect() as c:
        row = c.execute(
            text(
                "SELECT state,attempt_count FROM core.authentication_challenge WHERE token_hash=:t"
            ),
            {"t": token_hash(first)},
        ).one()
        assert tuple(row) == ("LOCKED", 5)


def test_expired_challenge_consumes_no_factor_and_version_change_denies(identity):
    started, _ = enroll(identity)
    engine, context, password, login = identity
    with engine.begin() as c:
        gate, _ = service.login_gate(c, login, password, "synthetic-network-" + login)
        c.execute(
            text(
                "UPDATE core.authentication_challenge SET created_at=clock_timestamp()-interval '10 minutes',expires_at=clock_timestamp()-interval '1 minute' WHERE token_hash=:t"
            ),
            {"t": token_hash(gate["challengeToken"])},
        )
    with engine.begin() as c:
        _, error = service.verify_login(
            c, gate["challengeToken"], pyotp.TOTP(started["setupKey"]).now()
        )
    assert error.status_code == 401
    with engine.begin() as c:
        gate, _ = service.login_gate(c, login, password, "synthetic-network-" + login)
        c.execute(
            text(
                "UPDATE core.app_user SET security_version=security_version+1 WHERE id=:u"
            ),
            {"u": context.user_id},
        )
    with engine.begin() as c:
        _, error = service.verify_login(
            c, gate["challengeToken"], pyotp.TOTP(started["setupKey"]).now()
        )
    assert error.status_code == 401


def test_recovery_code_race_restricts_session_and_reenrollment(identity):
    _started, confirmed = enroll(identity)
    engine, context, password, login = identity
    with engine.begin() as c:
        gate, error = service.login_gate(
            c, login, password, "synthetic-network-" + login
        )
    assert error is None

    def consume(_):
        with engine.begin() as c:
            return service.verify_login(
                c, gate["challengeToken"], confirmed["recoveryCodes"][0]
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(consume, range(2)))
    assert sum(error is None for _, error in results) == 1
    value = next(value for value, error in results if error is None)
    assert value["recoveryOnly"] is True
    recovery = AuthContext(
        "MEMBER",
        str(context.user_id),
        1,
        1,
        context.user_id,
        frozenset(),
        value["token"],
    )
    with engine.begin() as c:
        _, error = service.session(c, recovery)
        assert error.code == "RECOVERY_ONLY"
        again, error = service.login_gate(
            c, login, password, "synthetic-network-" + login
        )
        assert error is None and again["mfaRequired"] is True
        denied, error = service.verify_login(
            c, again["challengeToken"], confirmed["recoveryCodes"][1]
        )
        assert denied is None and error.status_code == 401
        pending, error = service.start_enrollment(c, recovery, "", recovery=True)
        assert error is None
    with engine.begin() as c:
        new_codes, error = service.confirm_enrollment(
            c,
            recovery,
            pending["factorId"],
            pyotp.TOTP(pending["setupKey"]).now(),
            recovery=True,
        )
        assert error is None and set(new_codes["recoveryCodes"]).isdisjoint(
            confirmed["recoveryCodes"]
        )
    with engine.begin() as c:
        _, error = service.session(c, recovery, allow_recovery=True)
        assert error.status_code == 401
        gate, error = service.login_gate(
            c, login, password, "synthetic-network-" + login
        )
        assert error is None
        _, error = service.verify_login(
            c, gate["challengeToken"], confirmed["recoveryCodes"][1]
        )
        assert error.status_code == 401


def test_recent_auth_rotation_and_other_session_revocation(identity):
    started, old_codes = enroll(identity)
    engine, context, password, login = identity
    with engine.begin() as c:
        gate, _ = service.login_gate(c, login, password, "synthetic-network-" + login)
    code = next_code(engine, context.user_id, started["setupKey"])
    with engine.begin() as c:
        value, error = service.verify_login(c, gate["challengeToken"], code)
        assert error is None
    current = AuthContext(
        "MEMBER",
        str(context.user_id),
        context.workspace_id,
        context.generation_id,
        context.user_id,
        frozenset(),
        value["token"],
    )
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.auth_session SET verified_at=clock_timestamp()-interval '6 minutes' WHERE token_hash=:t"
            ),
            {"t": token_hash(current.token)},
        )
    with engine.begin() as c:
        _, error = service.rotate_codes(c, current)
        assert error.code == "STEP_UP_REQUIRED"
        c.execute(
            text(
                "UPDATE core.auth_session SET verified_at=clock_timestamp() WHERE token_hash=:t"
            ),
            {"t": token_hash(current.token)},
        )
        c.execute(
            text(
                "INSERT INTO core.auth_session(user_id,token_hash,csrf_token_hash,expires_at,security_version) SELECT id,:t,'synthetic',clock_timestamp()+interval '30 minutes',security_version FROM core.app_user WHERE id=:u"
            ),
            {"u": context.user_id, "t": token_hash("m_synthetic-other-" + uuid4().hex)},
        )
    with engine.begin() as c:
        rows, error = service.list_sessions(c, current)
        assert error is None and len(rows["sessions"]) == 2
        assert sum(r["current"] for r in rows["sessions"]) == 1
        result, error = service.revoke_other_sessions(c, current)
        assert error is None and result["revokedCount"] == 1
    with engine.begin() as c:
        rows, error = service.list_sessions(c, current)
        assert error is None and len(rows["sessions"]) == 1
        result, error = service.rotate_codes(c, current)
        assert error is None and len(result["recoveryCodes"]) == 8
        assert set(result["recoveryCodes"]).isdisjoint(old_codes["recoveryCodes"])
    with engine.begin() as c:
        _, error = service.list_sessions(c, current)
        assert error.status_code == 401


def test_valid_password_issuance_budget_persists_and_serializes_last_slot(identity):
    engine, _context, password, login = identity
    # Use a fixed DB clock only for the bucket to avoid a ten-minute boundary race.
    from unittest.mock import patch

    fixed = datetime(2026, 10, 18, 0, 1, tzinfo=UTC)
    with patch.object(service, "database_now", return_value=fixed):
        for _ in range(19):
            with engine.begin() as c:
                value, error = service.login_gate(
                    c, login, password, "synthetic-network-" + login
                )
            assert error is None and value["mfaRequired"] is False

        def issue(_):
            with engine.begin() as c:
                return service.login_gate(
                    c, login, password, "synthetic-network-" + login
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(issue, range(2)))
    assert sum(error is None for _, error in results) == 1
    assert next(error for _, error in results if error is not None).status_code == 429


def test_new_enrollment_keys_are_bounded_without_requiring_failed_password(identity):
    engine, context, password, _login = identity
    for _ in range(3):
        with engine.begin() as c:
            value, error = service.start_enrollment(c, context, password)
        assert error is None and value["setupKey"]
    with engine.begin() as c:
        value, error = service.start_enrollment(c, context, password)
    assert value is None and error.status_code == 429
