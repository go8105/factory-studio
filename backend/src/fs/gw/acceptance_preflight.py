"""Operator-only read snapshot for the approved 10-person acceptance environment.

No account/session mutation, grants, evidence registration, or acceptance approval.
"""

import hashlib
import re
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text

from fs.core.backup import BackupError
from fs.gw.backup import policy_snapshot
from fs.gw.operating_contract import canonical

REMAINING = ["EXTERNAL_STORAGE", "JOURNAL_COVERAGE", "LIVE_COMPANY", "FINAL_RELEASE"]


def collect(engine, *, company_id, code_revision, admin_login="admin"):
    if (
        type(company_id) is not int
        or not 0 < company_id <= 9223372036854775807
        or not isinstance(code_revision, str)
        or not re.fullmatch(r"[0-9a-f]{7,64}", code_revision)
        or not isinstance(admin_login, str)
        or not admin_login.strip()
        or len(admin_login) > 100
        or any(ord(c) < 32 for c in admin_login)
    ):
        raise BackupError("회사·제품 버전·점검할 관리자 식별자를 확인하세요.")
    with (
        engine.connect().execution_options(isolation_level="REPEATABLE READ") as c,
        c.begin(),
    ):
        c.execute(text("SET TRANSACTION READ ONLY"))
        c.execute(text("SET LOCAL statement_timeout='15s'"))
        c.execute(text("SET LOCAL lock_timeout='3s'"))
        return snapshot(
            c,
            company_id=company_id,
            code_revision=code_revision,
            admin_login=admin_login.strip().lower(),
        )


def snapshot(c, *, company_id, code_revision, admin_login):
    if c.scalar(text("SHOW transaction_read_only")) != "on":
        raise BackupError("읽기 전용 거래에서만 인수 사전점검을 실행하세요.")
    clock = c.scalar(text("SELECT transaction_timestamp()"))
    if abs((datetime.now(UTC) - clock).total_seconds()) > 30:
        raise BackupError("서버와 실행자 시각 차이를 먼저 확인하세요.")
    scope = policy_snapshot(c, company_id)
    p = {"w": company_id, "g": int(scope["generationId"]), "login": admin_login}
    metadata = (
        c.execute(
            text("""SELECT co.is_example,d.status,
        EXISTS(SELECT 1 FROM core.workspace_module m WHERE m.workspace_id=w.id AND m.module_key='gw' AND m.enabled AND m.seeded_generation_id=d.id) AS enabled,
        EXISTS(SELECT 1 FROM gw.collaboration_settings cs WHERE (cs.workspace_id,cs.generation_id)=(w.id,d.id)) AS initialized,
        r.policy_digest
        FROM core.company co JOIN core.workspace w ON w.id=co.workspace_id
        JOIN core.data_generation d ON (d.workspace_id,d.id)=(w.id,w.active_generation_id)
        JOIN gw.operating_settings s ON (s.workspace_id,s.generation_id)=(w.id,d.id)
        JOIN gw.operating_policy_revision r ON (r.workspace_id,r.generation_id,r.id)=(s.workspace_id,s.generation_id,s.current_policy_revision_id)
        WHERE w.id=:w AND d.id=:g"""),
            p,
        )
        .mappings()
        .one()
    )
    if (
        metadata["status"] != "active"
        or not metadata["enabled"]
        or not metadata["initialized"]
        or metadata["policy_digest"] != scope["policyDigest"]
    ):
        raise BackupError("활성 GW 세대와 현재 운영 기준 원본을 확인하세요.")
    db_revision = c.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar_one()
    if not isinstance(db_revision, str) or not re.fullmatch(
        r"[A-Za-z0-9_]{1,100}", db_revision
    ):
        raise BackupError("현재 DB 버전을 확인하세요.")
    counts = (
        c.execute(
            text("""WITH connected AS (
        SELECT b.user_id,b.person_id,
        EXISTS(SELECT 1 FROM gw.organization_unit o WHERE (o.workspace_id,o.generation_id,o.id)=(p.workspace_id,p.generation_id,p.organization_unit_id) AND o.is_active) AS active_department,
        EXISTS(SELECT 1 FROM core.mfa_factor f WHERE f.user_id=b.user_id AND f.state='ACTIVE') AS mfa,
        EXISTS(SELECT 1 FROM gw.role_grant r WHERE (r.workspace_id,r.generation_id,r.person_id)=(b.workspace_id,b.generation_id,b.person_id) AND r.role_key='SECURITY_ADMIN' AND r.is_active) AS security_admin
        FROM gw.person_identity_binding b
        JOIN gw.person p ON (p.workspace_id,p.generation_id,p.id)=(b.workspace_id,b.generation_id,b.person_id)
        JOIN core.company_member m ON (m.workspace_id,m.user_id)=(b.workspace_id,b.user_id)
        JOIN core.app_user u ON u.id=b.user_id
        WHERE b.workspace_id=:w AND b.generation_id=:g AND b.state='ACTIVE' AND p.is_active AND m.is_active AND u.status='active' AND u.disabled_at IS NULL
        ) SELECT
        (SELECT count(*) FROM core.company_member m JOIN core.app_user u ON u.id=m.user_id WHERE m.workspace_id=:w AND m.is_active AND u.status='active' AND u.disabled_at IS NULL) AS "activeMembers",
        (SELECT count(*) FROM gw.person WHERE workspace_id=:w AND generation_id=:g AND is_active) AS "activePeople",
        count(*) AS "connectedPeople",count(*) FILTER(WHERE mfa) AS "mfaPeople",
        count(*) FILTER(WHERE security_admin) AS "securityAdministrators",
        count(*) FILTER(WHERE NOT security_admin) AS "nonSecurityAdminPeople",
        count(*) FILTER(WHERE NOT active_department) AS "unassignedDepartmentPeople",
        (SELECT count(*) FROM gw.organization_unit WHERE workspace_id=:w AND generation_id=:g AND is_active) AS "activeDepartments",
        EXISTS(SELECT 1 FROM connected WHERE person_id=cast(:responsible AS bigint)) AS "responsibleConnected"
        FROM connected"""),
            p | {"responsible": scope["policy"]["responsiblePersonId"]},
        )
        .mappings()
        .one()
    )
    account = (
        c.execute(
            text("""SELECT u.id,u.status='active' AND u.disabled_at IS NULL AS active,
        EXISTS(SELECT 1 FROM core.user_role ur JOIN core.role r ON r.id=ur.role_id WHERE ur.user_id=u.id AND r.role_key='ADMIN') AS platform_admin,
        EXISTS(SELECT 1 FROM core.company_member m WHERE m.workspace_id=:w AND m.user_id=u.id AND m.is_active) AS member,
        EXISTS(SELECT 1 FROM core.mfa_factor f WHERE f.user_id=u.id AND f.state='ACTIVE') AS mfa
        FROM core.app_user u WHERE u.login_id=:login"""),
            p,
        )
        .mappings()
        .one_or_none()
    )
    binding = c.execute(
        text("""SELECT p.id FROM gw.person_identity_binding b JOIN gw.person p ON (p.workspace_id,p.generation_id,p.id)=(b.workspace_id,b.generation_id,b.person_id)
        WHERE b.workspace_id=:w AND b.generation_id=:g AND b.user_id=:u AND b.state='ACTIVE' AND p.is_active"""),
        p | {"u": account["id"] if account else None},
    ).scalar_one_or_none()
    roles = set(
        c.execute(
            text(
                """SELECT role_key FROM gw.role_grant WHERE workspace_id=:w AND generation_id=:g AND person_id=:person AND is_active"""
            ),
            p | {"person": binding},
        ).scalars()
    )
    active = bool(account and account["active"])
    connected = bool(active and account["member"] and binding is not None)
    administrator = {
        "accountExists": account is not None,
        "accountActive": active,
        "platformAdministrator": bool(account and account["platform_admin"]),
        "companyMember": bool(active and account["member"]),
        "identityConnected": connected,
        "securityAdministrator": connected and "SECURITY_ADMIN" in roles,
        "auditor": connected and "AUDITOR" in roles,
        "mfaEnrolled": bool(active and account["mfa"]),
        "menuRoleEligible": connected and bool(roles & {"SECURITY_ADMIN", "AUDITOR"}),
        "businessSession": "NOT_CHECKED",
        "recentAuthentication": "NOT_CHECKED",
    }
    context = {
        "workspaceId": company_id,
        "generationId": int(scope["generationId"]),
        "policy": scope["policy"],
        "codeRevision": code_revision,
        "dbRevision": db_revision,
    }
    report = assess(
        scope["policy"],
        dict(counts),
        administrator,
        company_is_example=metadata["is_example"],
    )
    report.update(
        version=1,
        kind="GW_ACCEPTANCE_PREFLIGHT",
        runId=str(uuid4()),
        observedAt=clock.isoformat(),
        workspaceId=str(company_id),
        generationId=scope["generationId"],
        policyDigest=scope["policyDigest"],
        codeRevision=code_revision,
        dbRevision=db_revision,
        contextDigest=hashlib.sha256(canonical(context)).hexdigest(),
        codeRevisionSource="OPERATOR_ENVIRONMENT",
        executionRevisionVerified=False,
    )
    return context, report


def assess(policy, counts, administrator, *, company_is_example):
    checks = []

    def check(code, passed):
        checks.append({"code": code, "state": "CONFIRMED" if passed else "BLOCKED"})

    check(
        "TEN_PERSON_PLAN",
        policy["expectedPeople"] == 10 and policy["expectedDepartments"] == 1,
    )
    check("NON_EXAMPLE_MARKER", company_is_example is False)
    check(
        "TEN_CONNECTED_PEOPLE",
        counts["activeMembers"]
        == counts["activePeople"]
        == counts["connectedPeople"]
        == 10,
    )
    check("ONE_DEPARTMENT", counts["activeDepartments"] == 1)
    check(
        "ALL_CONNECTED_DEPARTMENT",
        counts["connectedPeople"] > 0 and counts["unassignedDepartmentPeople"] == 0,
    )
    check(
        "ALL_CONNECTED_MFA",
        counts["connectedPeople"] > 0
        and counts["mfaPeople"] == counts["connectedPeople"],
    )
    check(
        "ONE_SECURITY_ADMIN_NINE_OTHERS",
        counts["securityAdministrators"] == 1 and counts["nonSecurityAdminPeople"] == 9,
    )
    check("RESPONSIBLE_CONNECTED", counts["responsibleConnected"] is True)
    check("ADMIN_COMPANY_SECURITY_ROLE", administrator["securityAdministrator"] is True)
    check("ADMIN_MFA_ENROLLED", administrator["mfaEnrolled"] is True)
    return {
        "result": "PARTIAL"
        if all(r["state"] == "CONFIRMED" for r in checks)
        else "BLOCKED",
        "ready": False,
        "liveCompanyAcceptance": False,
        "releaseAuthorized": False,
        "companyIsExample": company_is_example,
        "counts": counts,
        "administrator": administrator,
        "checks": checks,
        "remainingConditions": list(REMAINING),
        "representativeBusinessChecks": "UNVERIFIED",
        "deviceChecks": "UNVERIFIED",
    }
