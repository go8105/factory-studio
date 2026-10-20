"""GW-READY-02 company operating policies. Current role and scope before receipt."""

from sqlalchemy import text

from fs.common.errors import ApiError
from fs.core.company import require_recent_auth
from fs.core.security.emergency import summary as emergency_summary
from fs.core.security.service import database_now
from fs.gw import company
from fs.gw.acceptance_collection import collect_registered
from fs.gw.company_identity import audit, require_active
from fs.gw.launch_gate import build as build_launch_gate
from fs.gw.operating_contract import OperatingPolicy
from fs.gw.readiness import assess

S = company.S


def settings(c, ctx):
    return (
        c.execute(
            text(f"SELECT * FROM gw.operating_settings WHERE {S} FOR UPDATE"),
            {"w": ctx.workspace_id, "g": ctx.generation_id},
        )
        .mappings()
        .one_or_none()
    )


def policy_from_row(row):
    if row is None:
        return None
    return OperatingPolicy.model_validate(
        {
            name: str(row[name]) if name == "responsible_person_id" else row[name]
            for name in OperatingPolicy.model_fields
        }
    )


def read(context, company_id):
    with company.transaction(context, company_id) as (c, ctx, _):
        _person, roles = company.principal(c, ctx)
        if not roles.intersection({"SECURITY_ADMIN", "AUDITOR"}):
            return {
                "administrator": False,
                "nextAction": "내 계정 보안에서 인증 앱 등록을 확인하세요.",
            }
        p = {"w": ctx.workspace_id, "g": ctx.generation_id}
        current = settings(c, ctx)
        row = (
            c.execute(
                text(
                    f"SELECT * FROM gw.operating_policy_revision WHERE {S} AND id=:id"
                ),
                p | {"id": current["current_policy_revision_id"]},
            )
            .mappings()
            .one_or_none()
            if current
            else None
        )
        policy = policy_from_row(row)
        counts = (
            c.execute(
                text(f"""SELECT count(*) AS connected,count(*) FILTER(WHERE EXISTS(SELECT 1 FROM core.mfa_factor f WHERE f.user_id=b.user_id AND f.state='ACTIVE')) AS enrolled
            FROM gw.person_identity_binding b JOIN gw.person p ON (p.workspace_id,p.generation_id,p.id)=(b.workspace_id,b.generation_id,b.person_id)
            JOIN core.app_user u ON u.id=b.user_id JOIN core.company_member m ON m.user_id=u.id AND m.workspace_id=b.workspace_id
            WHERE b.{S.replace(" AND ", " AND b.")} AND b.state='ACTIVE' AND p.is_active AND m.is_active AND u.status='active' AND u.disabled_at IS NULL"""),
                p,
            )
            .mappings()
            .one()
        )
        from fs.gw.operating_evidence import verifier_config

        pair_check = {
            "result": "BLOCKED",
            "backupRestorePairVerified": False,
            "ready": False,
            "source": "LATEST_REGISTRATIONS",
            "reason": "POLICY_REQUIRED",
        }
        try:
            keys, code_revision, db_revision = verifier_config(c)
            evidence_rows = (
                c.execute(
                    text(f"""SELECT DISTINCT ON (kind) *
                FROM gw.operating_evidence WHERE {S}
                ORDER BY kind,recorded_at DESC,id DESC"""),
                    p,
                )
                .mappings()
                .all()
            )
            clock = database_now(c)
            if policy is not None:
                pair_check = collect_registered(
                    evidence_rows,
                    policy_id=current["current_policy_revision_id"],
                    workspace_id=ctx.workspace_id,
                    generation_id=ctx.generation_id,
                    policy=policy,
                    code_revision=code_revision,
                    db_revision=db_revision,
                    public_keys=keys,
                    now=clock,
                )
            evidence_checks = assess(
                evidence_rows,
                policy=policy,
                policy_id=current["current_policy_revision_id"] if current else None,
                code_revision=code_revision,
                db_revision=db_revision,
                public_keys=keys,
                now=clock,
            )
        except ApiError as error:
            if error.code != "SECURITY_CONFIGURATION_UNAVAILABLE":
                raise
            pair_check["reason"] = "CONFIG_REQUIRED"
            evidence_checks = [
                {
                    "kind": kind,
                    "label": label,
                    "state": "CONFIG_REQUIRED",
                    "signatureVerified": False,
                    "detail": "서버의 실행 증거 검증 키와 버전을 설정해야 합니다.",
                }
                for kind, label in (
                    ("BACKUP", "백업 실행"),
                    ("RESTORE", "복원 실행"),
                    ("ACCEPTANCE", "실환경 업무 인수"),
                )
            ]
        scope_checks = (
            c.execute(
                text(f"""SELECT
            (SELECT count(*) FROM gw.organization_unit WHERE {S} AND is_active) AS departments,
            EXISTS(SELECT 1 FROM gw.person p
                JOIN gw.person_identity_binding b ON (b.workspace_id,b.generation_id,b.person_id)=(p.workspace_id,p.generation_id,p.id)
                JOIN core.app_user u ON u.id=b.user_id
                JOIN core.company_member m ON m.workspace_id=p.workspace_id AND m.user_id=u.id
                WHERE p.{S.replace(" AND ", " AND p.")} AND p.id=:person
                AND p.is_active AND b.state='ACTIVE' AND m.is_active
                AND u.status='active' AND u.disabled_at IS NULL) AS responsible_active"""),
                p | {"person": int(policy.responsible_person_id) if policy else None},
            )
            .mappings()
            .one()
        )
        launch_gate = build_launch_gate(
            policy=policy,
            connected=counts["connected"],
            enrolled=counts["enrolled"],
            departments=scope_checks["departments"],
            responsible_active=scope_checks["responsible_active"],
            evidence=evidence_checks,
        )
        blockers = [
            f"{check['label']}: {check['detail']} {check['nextAction']}"
            for check in launch_gate["checks"]
            if check["state"] != "CONFIRMED"
        ]
        return {
            "administrator": True,
            "canEdit": "SECURITY_ADMIN" in roles,
            "version": current["version"] if current else 0,
            "rolloutState": current["rollout_state"] if current else "DRAFT",
            "connectedPeople": counts["connected"],
            "mfaPeople": counts["enrolled"],
            "policy": policy.model_dump(by_alias=True) if policy else None,
            "revisionNo": row["revision_no"] if row else None,
            "emergencyKit": emergency_summary(c, ctx.user_id, ctx.workspace_id),
            "evidenceChecks": evidence_checks,
            "backupRestoreCollection": pair_check,
            "evidenceIntegrityReverified": all(
                check["signatureVerified"] for check in evidence_checks
            ),
            "launchGate": launch_gate,
            "ready": launch_gate["ready"],
            "blockers": blockers,
        }


def apply_policy(context, company_id, payload, key):
    policy = OperatingPolicy.model_validate(payload["policy"])

    def authorize(c, ctx, _person):
        company.principal(c, ctx, "SECURITY_ADMIN")
        require_recent_auth(c, ctx, always=True)
        require_active(c, ctx, int(policy.responsible_person_id))

    def run(c, ctx, _person):
        current = settings(c, ctx)
        version = current["version"] if current else 0
        if version != payload["expectedVersion"]:
            raise ApiError(
                409,
                "STATE_CHANGED",
                "기준이 변경되었습니다. 현재 값과 비교한 뒤 다시 적용하세요.",
            )
        p = {"w": ctx.workspace_id, "g": ctx.generation_id}
        revision_no = c.execute(
            text(
                f"SELECT coalesce(max(revision_no),0)+1 FROM gw.operating_policy_revision WHERE {S}"
            ),
            p,
        ).scalar_one()
        values = (
            p
            | policy.model_dump()
            | {"revision": revision_no, "u": ctx.user_id, "digest": policy.digest()}
        )
        values["responsible_person_id"] = int(policy.responsible_person_id)
        fields = list(OperatingPolicy.model_fields)
        id = c.execute(
            text(f"""INSERT INTO gw.operating_policy_revision(workspace_id,generation_id,revision_no,{",".join(fields)},confirmed_by_user_id,confirmed_at,policy_digest)
            VALUES(:w,:g,:revision,{",".join(":" + f for f in fields)},:u,clock_timestamp(),:digest) RETURNING id"""),
            values,
        ).scalar_one()
        if current:
            c.execute(
                text(
                    f"UPDATE gw.operating_settings SET current_policy_revision_id=:id,version=version+1,updated_by_user_id=:u,updated_at=clock_timestamp() WHERE {S}"
                ),
                p | {"id": id, "u": ctx.user_id},
            )
        else:
            c.execute(
                text(
                    "INSERT INTO gw.operating_settings(workspace_id,generation_id,version,current_policy_revision_id,rollout_state,updated_by_user_id,updated_at) VALUES(:w,:g,1,:id,'DRAFT',:u,clock_timestamp())"
                ),
                p | {"id": id, "u": ctx.user_id},
            )
        audit(
            c,
            ctx,
            "operating_policy_revision",
            id,
            "operating_policy.applied",
            policy.reason,
            {"version": version + 1},
        )
        return (
            {"id": str(id), "revisionNo": revision_no, "version": version + 1},
            "gw.operating_policy_revision",
            id,
        )

    return company.action(
        context,
        company_id,
        "gw.operating_policy.apply",
        key,
        payload,
        run,
        authorize=authorize,
    )
