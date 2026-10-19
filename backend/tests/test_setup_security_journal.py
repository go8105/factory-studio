"""Operator setup records and the explicit no-session-replay boundary."""

# ruff: noqa:F811
from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_account_security_journal import checked
from test_gw_security_transactions import identity  # noqa:F401
from test_security_journal import journal  # noqa:F401

from fs.common.auth import _resolve_member
from fs.common.errors import ApiError
from fs.core.security import backup, recording
from fs.core.service import create_member_account
from fs.hr.work_setup import activate_example_company, prepare_example_company
from seed.generate import create_template


def template(engine):
    with engine.begin() as c:
        create_template(c, date(2026, 10, 19))


def test_operator_account_creation_records_roles_without_secrets(
    clean_database, journal
):
    import json

    template(clean_database)
    password = uuid4().hex
    with clean_database.begin() as c:
        result = create_member_account(
            c,
            "synthetic-setup-admin",
            "합성 운영자",
            password,
            date(2026, 10, 19),
            admin=True,
        )
    records = checked(clean_database, journal)
    row = records[-1]["payload"]
    assert (
        row["operation"] == "security.member_account.created"
        and row["userId"] == result["userId"]
    )
    assert row["snapshot"]["roles"]
    assert password not in json.dumps(records)


def test_operator_account_record_failure_rolls_back_creation(
    clean_database, journal, monkeypatch
):
    template(clean_database)

    def fail(*args, **kwargs):
        raise OSError("synthetic recording failure")

    monkeypatch.setattr(recording, "append", fail)
    with pytest.raises(ApiError), clean_database.begin() as c:
        create_member_account(
            c,
            "synthetic-setup-admin",
            "합성 운영자",
            uuid4().hex,
            date(2026, 10, 19),
            admin=True,
        )
    with clean_database.connect() as c:
        assert (
            c.scalar(
                text(
                    "SELECT count(*) FROM core.app_user WHERE login_id='synthetic-setup-admin'"
                )
            )
            == 0
        )


def test_example_prepare_and_activation_record_actual_account_states(
    clean_database, journal
):
    import json

    template(clean_database)
    password = uuid4().hex
    with clean_database.begin() as c:
        prepare_example_company(c)
    with clean_database.begin() as c:
        activate_example_company(c, password, password)
    records = checked(clean_database, journal)
    for operation, status in [
        ("hr.setup.example.disabled", "disabled"),
        ("hr.setup.example.activated", "active"),
    ]:
        selected = [r for r in records if r["payload"]["operation"] == operation]
        assert len(selected) == 2
        assert all(
            r["payload"]["snapshot"]["user"][0]["status"] == status for r in selected
        )
    assert (
        len(
            [
                r
                for r in records
                if r["payload"]["operation"] == "hr.setup.example.created"
            ]
        )
        == 2
    )
    assert password not in json.dumps(records)


@pytest.mark.parametrize("activate", [False, True])
def test_example_setup_record_failure_rolls_back(
    clean_database, journal, monkeypatch, activate
):
    template(clean_database)
    if activate:
        with clean_database.begin() as c:
            prepare_example_company(c)
    operation = (
        "hr.setup.example.activated" if activate else "hr.setup.example.disabled"
    )
    original = recording.append

    def fail(directory, key, payload):
        if payload["operation"] == operation:
            raise OSError("synthetic recording failure")
        return original(directory, key, payload)

    monkeypatch.setattr(recording, "append", fail)
    with pytest.raises(ApiError), clean_database.begin() as c:
        if activate:
            activate_example_company(c, uuid4().hex, uuid4().hex)
        else:
            prepare_example_company(c)
    with clean_database.connect() as c:
        states = (
            c.execute(
                text(
                    "SELECT status FROM core.app_user WHERE login_id IN ('hugh-admin','hugh-staff')"
                )
            )
            .scalars()
            .all()
        )
    assert states == ["disabled", "disabled"] if activate else not states


def test_session_idle_extension_cannot_survive_closed_replay(identity, journal):
    engine, ctx, _, _ = identity
    with engine.begin() as c:
        now = c.scalar(text("SELECT clock_timestamp()"))
        limit = now + timedelta(minutes=2)
        c.execute(
            text(
                "UPDATE core.auth_session SET expires_at=:e,absolute_expires_at=:a WHERE user_id=:u"
            ),
            {"e": now + timedelta(seconds=10), "a": limit, "u": ctx.user_id},
        )
        checkpoint = backup.capture(c)
        _resolve_member(c, ctx.token)
        extended = c.scalar(
            text("SELECT expires_at FROM core.auth_session WHERE user_id=:u"),
            {"u": ctx.user_id},
        )
        assert now + timedelta(seconds=10) < extended <= limit
        result = backup.replay(c, checkpoint)
        assert result["sessionsInvalidated"]
    with pytest.raises(ApiError) as error, engine.begin() as c:
        _resolve_member(c, ctx.token)
    assert error.value.code == "SESSION_EXPIRED"
