"""Checkpoint replay preserves revocation/OTP consumption and never promotes users."""

# ruff: noqa:F401,F811
from uuid import uuid4

from fs.common.security import hash_password
from fs.core.security import backup as core_checkpoint
from fs.gw import backup as gw_checkpoint
from fs.hr import backup as hr_checkpoint
from sqlalchemy import text
from test_gw_backup import backup_env
from test_gw_company_work import call_work
from test_gw_emergency import emergency_env
from test_hr_work import company_env


def test_used_real_mfa_code_and_counter_cannot_return_after_replay(emergency_env):
    engine, _co, client, _login = emergency_env
    with engine.begin() as c:
        factor = dict(
            c.execute(
                text(
                    "SELECT id,last_used_step FROM core.mfa_factor WHERE state='ACTIVE'"
                )
            )
            .mappings()
            .one()
        )
        code = c.execute(
            text(
                "SELECT id FROM core.recovery_code WHERE used_at IS NULL AND revoked_at IS NULL LIMIT 1"
            )
        ).scalar_one()
        c.execute(
            text(
                "UPDATE core.mfa_factor SET last_used_step=last_used_step+3 WHERE id=:id"
            ),
            factor,
        )
        c.execute(
            text(
                "UPDATE core.recovery_code SET used_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": code},
        )
        latest = core_checkpoint.capture(c)
        # Model the older authentication data restored from the backup.
        c.execute(
            text(
                "UPDATE core.mfa_factor SET last_used_step=:last_used_step WHERE id=:id"
            ),
            factor,
        )
        c.execute(
            text("UPDATE core.recovery_code SET used_at=NULL WHERE id=:id"),
            {"id": code},
        )
        result = core_checkpoint.replay(c, latest)
        assert result["sessionsInvalidated"] is True
        assert (
            c.execute(
                text("SELECT last_used_step FROM core.mfa_factor WHERE id=:id"), factor
            ).scalar_one()
            == factor["last_used_step"] + 3
        )
        assert c.execute(
            text("SELECT revoked_at IS NOT NULL FROM core.recovery_code WHERE id=:id"),
            {"id": code},
        ).scalar_one()
    assert client.get("/api/v1/core/sessions/current").status_code == 401


def test_changed_password_is_not_resurrected(emergency_env):
    engine, _co, _client, _login = emergency_env
    with engine.begin() as c:
        user = dict(
            c.execute(
                text(
                    "SELECT id,password_hash FROM core.app_user WHERE login_id=:login"
                ),
                {"login": "synthetic-emergency-owner"},
            )
            .mappings()
            .one()
        )
        c.execute(
            text("UPDATE core.app_user SET password_hash=:value WHERE id=:id"),
            {"id": user["id"], "value": hash_password(uuid4().hex)},
        )
        latest = core_checkpoint.capture(c)
        c.execute(
            text("UPDATE core.app_user SET password_hash=:password_hash WHERE id=:id"),
            user,
        )
        result = core_checkpoint.replay(c, latest)
        assert result["disabledAccounts"] >= 1
        assert c.execute(
            text("SELECT status='disabled' FROM core.app_user WHERE id=:id"), user
        ).scalar_one()
        assert c.execute(
            text(
                "SELECT NOT EXISTS(SELECT 1 FROM core.mfa_factor WHERE user_id=:id AND state='ACTIVE')"
            ),
            user,
        ).scalar_one()


def test_uncertain_acl_or_hold_change_keeps_scope_quarantined(company_env, backup_env):
    engine, co, _admin, _staff = company_env
    with engine.begin() as c:
        before = c.execute(
            text(
                "SELECT company_hold FROM gw.operating_settings WHERE workspace_id=:w"
            ),
            {"w": co["companyId"]},
        ).scalar_one()
        c.execute(
            text(
                "UPDATE gw.operating_settings SET company_hold=true,hold_reason='합성 백업 이후 보존 중지',version=version+1 WHERE workspace_id=:w"
            ),
            {"w": co["companyId"]},
        )
        latest = gw_checkpoint.capture(c)
        c.execute(
            text(
                "UPDATE gw.operating_settings SET company_hold=:hold,hold_reason=NULL,version=version-1 WHERE workspace_id=:w"
            ),
            {"w": co["companyId"], "hold": before},
        )
        result = gw_checkpoint.replay(c, latest)
        assert result["quarantinedScopes"] == 1
        assert c.execute(
            text(
                "SELECT NOT EXISTS(SELECT 1 FROM gw.person_identity_binding WHERE workspace_id=:w AND state='ACTIVE')"
            ),
            {"w": co["companyId"]},
        ).scalar_one()
        assert c.execute(
            text(
                "SELECT company_hold FROM gw.operating_settings WHERE workspace_id=:w"
            ),
            {"w": co["companyId"]},
        ).scalar_one()


def test_hr_role_downgrade_never_restores_old_management_access(
    company_env, backup_env
):
    engine, _co, _admin, _staff = company_env
    with engine.begin() as c:
        account = c.execute(
            text("SELECT id FROM hr.work_account WHERE work_role='ADMIN' LIMIT 1")
        ).scalar_one()
        c.execute(
            text("UPDATE hr.work_account SET work_role='STAFF' WHERE id=:id"),
            {"id": account},
        )
        latest = hr_checkpoint.capture(c)
        c.execute(
            text("UPDATE hr.work_account SET work_role='ADMIN' WHERE id=:id"),
            {"id": account},
        )
        assert hr_checkpoint.replay(c, latest)["hrRestrictions"] == 1
        assert c.execute(
            text("SELECT NOT is_active FROM hr.work_account WHERE id=:id"),
            {"id": account},
        ).scalar_one()
