"""Challenge lifecycle recording includes denied/expired outcomes and rollback."""

# ruff: noqa:F811
from datetime import UTC, datetime

import pyotp
import pytest
from sqlalchemy import text
from test_account_security_journal import checked
from test_gw_emergency import emergency_env, issue  # noqa:F401
from test_gw_security_transactions import enroll, identity  # noqa:F401
from test_gw_security_transactions import (
    test_expired_challenge_consumes_no_factor_and_version_change_denies as expired_flow,
)
from test_gw_security_transactions import (
    test_failed_otp_persists_and_new_challenge_does_not_reset_limit as denied_flow,
)
from test_security_journal import journal  # noqa:F401

from fs.common.errors import ApiError
from fs.common.security import token_hash
from fs.core.security import emergency, recording, service


def test_failed_attempts_and_lock_are_recorded(identity, journal):
    denied_flow(identity)
    records = checked(identity[0], journal)
    denied = [
        r
        for r in records
        if r["payload"]["operation"] == "security.login_challenge.denied"
    ]
    assert len(denied) == 5
    challenge = denied[-1]["payload"]["snapshot"]["challenges"][0]
    assert challenge["state"] == "LOCKED" and challenge["attempt_count"] == 5
    assert "security.login_challenge.issued" in {
        r["payload"]["operation"] for r in records
    }


def test_expired_request_is_recorded(identity, journal):
    expired_flow(identity)
    records = checked(identity[0], journal)
    expired = [
        r
        for r in records
        if r["payload"]["operation"] == "security.login_challenge.expired"
    ]
    assert len(expired) == 1
    assert any(
        c["state"] == "EXPIRED" for c in expired[0]["payload"]["snapshot"]["challenges"]
    )


@pytest.mark.parametrize("path", ["issued", "denied", "expired", "emergency"])
def test_record_failure_rolls_back_challenge_change(
    identity, journal, monkeypatch, path
):
    started, _ = enroll(identity)
    engine, ctx, password, login = identity
    gate = None
    if path != "issued":
        with engine.begin() as c:
            gate, error = service.login_gate(
                c, login, password, "synthetic-rollback-network"
            )
            assert error is None
            if path == "expired":
                c.execute(
                    text(
                        "UPDATE core.authentication_challenge SET created_at=clock_timestamp()-interval '10 minutes',expires_at=clock_timestamp()-interval '1 minute' WHERE token_hash=:t"
                    ),
                    {"t": token_hash(gate["challengeToken"])},
                )

    def state():
        with engine.connect() as c:
            return c.execute(
                text(
                    "SELECT id,state,attempt_count FROM core.authentication_challenge WHERE user_id=:u ORDER BY id"
                ),
                {"u": ctx.user_id},
            ).all()

    before = state()
    operation = (
        "security.emergency_login.denied"
        if path == "emergency"
        else "security.login_challenge." + path
    )
    real_append = recording.append

    def broken(directory, key, payload):
        if payload["operation"] == operation:
            raise OSError("synthetic journal failure")
        return real_append(directory, key, payload)

    monkeypatch.setattr(recording, "append", broken)
    with pytest.raises(ApiError) as error, engine.begin() as c:
        if path == "issued":
            service.login_gate(c, login, password, "synthetic-rollback-network")
        elif path == "emergency":
            emergency.fail_login(c, before[0][0])
        else:
            totp = pyotp.TOTP(started["setupKey"])
            valid = {
                totp.at(datetime.now(UTC).timestamp() + offset * 30)
                for offset in (-1, 0, 1)
            }
            wrong = next(f"{n:06}" for n in range(10) if f"{n:06}" not in valid)
            service.verify_login(c, gate["challengeToken"], wrong)
    assert error.value.code == "SECURITY_JOURNAL_UNAVAILABLE"
    assert state() == before


def test_expired_emergency_kit_is_recorded(emergency_env, journal):
    engine, _, _, _ = emergency_env
    kit = emergency.EmergencyKit.model_validate(
        issue(emergency_env).json()["data"]["kit"]
    )
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.authentication_challenge SET created_at=clock_timestamp()-interval '1 day',expires_at=clock_timestamp()-interval '1 minute' WHERE id=:id"
            ),
            {"id": int(kit.kit_id)},
        )
    with engine.begin() as c:
        _, error = emergency.approve(c, kit, 501, "합성 만료 확인")
    assert error.status_code == 401
    records = checked(engine, journal)
    assert "security.emergency_kit.expired" in {
        r["payload"]["operation"] for r in records
    }


def test_password_session_issuance_is_recorded_without_credentials(identity, journal):
    import json
    from uuid import uuid4

    from fs.core import service as core

    engine, ctx, password, login = identity
    with engine.begin() as c:
        _, token = core.login_member(c, login, password, str(uuid4()))
    records = checked(engine, journal)
    assert records[-1]["payload"]["operation"] == "security.password_session.issued"
    serialized = json.dumps(records)
    assert password not in serialized and token not in serialized
    assert ctx.token not in serialized


def test_password_session_record_failure_rolls_back_issuance(
    identity, journal, monkeypatch
):
    from uuid import uuid4

    from fs.core import service as core

    engine, ctx, password, login = identity
    with engine.connect() as c:
        before = c.scalar(
            text("SELECT count(*) FROM core.auth_session WHERE user_id=:u"),
            {"u": ctx.user_id},
        )

    def broken(*args, **kwargs):
        raise OSError("synthetic journal failure")

    monkeypatch.setattr(recording, "append", broken)
    with pytest.raises(ApiError), engine.begin() as c:
        core.login_member(c, login, password, str(uuid4()))
    with engine.connect() as c:
        assert (
            c.scalar(
                text("SELECT count(*) FROM core.auth_session WHERE user_id=:u"),
                {"u": ctx.user_id},
            )
            == before
        )


def test_emergency_denial_records_only_actual_changes(identity, journal):
    enroll(identity)
    engine, _, password, login = identity
    with engine.begin() as c:
        gate, error = service.login_gate(
            c, login, password, "synthetic-emergency-denial"
        )
        assert error is None
        challenge_id = c.scalar(
            text("SELECT id FROM core.authentication_challenge WHERE token_hash=:t"),
            {"t": token_hash(gate["challengeToken"])},
        )
    for _ in range(6):
        with engine.begin() as c:
            emergency.fail_login(c, challenge_id)
    records = checked(engine, journal)
    denied = [
        r
        for r in records
        if r["payload"]["operation"] == "security.emergency_login.denied"
    ]
    assert len(denied) == 5
    last = denied[-1]["payload"]["snapshot"]["challenges"][0]
    assert last["state"] == "LOCKED" and last["attempt_count"] == 5
