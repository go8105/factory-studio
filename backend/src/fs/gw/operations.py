"""GW-READY-02 company operating policies. Current role and scope before receipt."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from fs.common.errors import ApiError
from fs.common.security import token_hash
from fs.gw import company
from fs.gw.company_identity import audit, require_active
from fs.gw.operating_contract import OperatingPolicy

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
        blockers = []
        if policy is None:
            blockers.append("운영 기준과 책임자를 확인해 적용하세요.")
        elif counts["connected"] < policy.expected_people:
            blockers.append("예정 인원만큼 직원 본인 연결을 마치세요.")
        if counts["enrolled"] < counts["connected"]:
            blockers.append("연결된 모든 직원의 인증 앱 등록을 마치세요.")
        # These adapters must be completed and measured before release. Never green by checkbox.
        blockers.extend(
            [
                "암호화 백업·폐쇄 복원과 권한 회수 재적용 검증이 아직 연결되지 않았습니다.",
                "실제 환경·대표 업무 인수 검증이 필요합니다.",
            ]
        )
        return {
            "administrator": True,
            "canEdit": "SECURITY_ADMIN" in roles,
            "version": current["version"] if current else 0,
            "rolloutState": current["rollout_state"] if current else "DRAFT",
            "connectedPeople": counts["connected"],
            "mfaPeople": counts["enrolled"],
            "policy": policy.model_dump(by_alias=True) if policy else None,
            "revisionNo": row["revision_no"] if row else None,
            "ready": False,
            "blockers": blockers,
        }


def apply_policy(context, company_id, payload, key):
    policy = OperatingPolicy.model_validate(payload["policy"])

    def authorize(c, ctx, _person):
        company.principal(c, ctx, "SECURITY_ADMIN")
        current_session = c.execute(
            text("""SELECT s.verified_at FROM core.auth_session s JOIN core.app_user u ON u.id=s.user_id
            WHERE s.user_id=:u AND s.token_hash=:t AND s.revoked_at IS NULL AND s.assurance='MFA'
            AND s.security_version=u.security_version AND s.expires_at>clock_timestamp()
            AND (s.absolute_expires_at IS NULL OR s.absolute_expires_at>clock_timestamp())
            FOR SHARE OF s"""),
            {"u": ctx.user_id, "t": token_hash(context.token)},
        ).first()
        if (
            current_session is None
            or current_session[0] is None
            or datetime.now(UTC) - current_session[0] > timedelta(minutes=5)
        ):
            raise ApiError(
                403, "STEP_UP_REQUIRED", "내 계정 보안에서 본인을 다시 확인해 주세요."
            )
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
