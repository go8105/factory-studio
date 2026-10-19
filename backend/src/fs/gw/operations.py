"""GW-READY-02 company operating policies. Current role and scope before receipt."""

from sqlalchemy import text

from fs.common.errors import ApiError
from fs.core.company import require_recent_auth
from fs.core.security.emergency import summary as emergency_summary
from fs.core.security.service import database_now
from fs.gw import company
from fs.gw.company_identity import audit, require_active
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
        blockers = []
        if policy is None:
            blockers.append("운영 기준과 책임자를 확인해 적용하세요.")
        elif counts["connected"] < policy.expected_people:
            blockers.append("예정 인원만큼 직원 본인 연결을 마치세요.")
        if counts["enrolled"] < counts["connected"]:
            blockers.append("연결된 모든 직원의 인증 앱 등록을 마치세요.")
        # Evidence registration validates signatures. Stored normalized metrics cannot
        # reconstruct the original signed envelope, so this is not signature re-verification.
        from fs.gw.operating_evidence import verifier_config

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
            evidence_checks = assess(
                evidence_rows,
                policy=policy,
                policy_id=current["current_policy_revision_id"] if current else None,
                code_revision=code_revision,
                db_revision=db_revision,
                signer_ids=set(keys),
                now=database_now(c),
            )
        except ApiError as error:
            if error.code != "SECURITY_CONFIGURATION_UNAVAILABLE":
                raise
            evidence_checks = [
                {
                    "kind": kind,
                    "label": label,
                    "state": "CONFIG_REQUIRED",
                    "detail": "서버의 실행 증거 검증 키와 버전을 설정해야 합니다.",
                }
                for kind, label in (
                    ("BACKUP", "백업 실행"),
                    ("RESTORE", "복원 실행"),
                    ("ACCEPTANCE", "실환경 업무 인수"),
                )
            ]
        blockers.extend(
            f"{check['label']}: {check['detail']}"
            for check in evidence_checks
            if check["state"] != "RECORDED_PASS"
        )
        # These adapters must be completed and measured before release. Never green by checkbox.
        blockers.extend(
            [
                "실제 외부 저장소의 장애·복구 인수가 필요합니다.",
                "모든 보안 변경 경로의 수집 완전성과 복원 후 전체 회수 검증이 필요합니다.",
                "등록 기록의 원본 서명 재검증과 운영 전환 최종 승인은 아직 연결되지 않았습니다.",
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
            "emergencyKit": emergency_summary(c, ctx.user_id, ctx.workspace_id),
            "evidenceChecks": evidence_checks,
            "evidenceIntegrityReverified": False,
            "ready": False,
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
