"""Signed runner evidence ingestion. Never turn an uploaded checkbox into readiness."""

import base64
import json
import os
import re

from sqlalchemy import text

from fs.common.errors import ApiError
from fs.core.company import require_recent_auth
from fs.core.security.service import database_now
from fs.gw import company
from fs.gw.company_identity import audit
from fs.gw.operating_contract import verify_evidence
from fs.gw.operations import policy_from_row, settings
from fs.gw.readiness import SOURCE_FIELD

S = company.S


def verifier_config(c):
    try:
        configured = json.loads(os.environ["FS_GW_EVIDENCE_PUBLIC_KEYS"])
        if not isinstance(configured, dict) or not 1 <= len(configured) <= 20:
            raise ValueError()
        keys = {
            name: base64.b64decode(value, validate=True)
            for name, value in configured.items()
        }
        if any(len(value) != 32 for value in keys.values()):
            raise ValueError()
        if any(
            not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", name)
            for name in keys
        ):
            raise ValueError()
        revision = os.environ["FS_CODE_REVISION"]
        if not re.fullmatch(r"[0-9a-f]{7,64}", revision):
            raise ValueError()
        db_revision = c.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        return keys, revision, db_revision
    except KeyError, ValueError, TypeError:
        raise ApiError(
            503,
            "SECURITY_CONFIGURATION_UNAVAILABLE",
            "운영 실행 증거의 검증 키와 제품 버전을 서버에서 설정해야 합니다.",
        ) from None


def record(context, company_id, payload, key):
    def authorize(c, ctx, _person):
        company.principal(c, ctx, "SECURITY_ADMIN")
        require_recent_auth(c, ctx, always=True)

    def run(c, ctx, _person):
        current = settings(c, ctx)
        if current is None or current["current_policy_revision_id"] is None:
            raise ApiError(
                409, "OPERATING_PREREQUISITE_REQUIRED", "운영 기준을 먼저 적용하세요."
            )
        p = {"w": ctx.workspace_id, "g": ctx.generation_id}
        row = (
            c.execute(
                text(
                    f"SELECT * FROM gw.operating_policy_revision WHERE {S} AND id=:id"
                ),
                p | {"id": current["current_policy_revision_id"]},
            )
            .mappings()
            .one()
        )
        keys, revision, db_revision = verifier_config(c)
        data = verify_evidence(
            payload["envelope"],
            payload["signature"],
            public_keys=keys,
            workspace_id=ctx.workspace_id,
            generation_id=ctx.generation_id,
            policy=policy_from_row(row),
            db_revision=db_revision,
            code_revision=revision,
            now=database_now(c),
        )
        exists = c.execute(
            text(
                f"SELECT id FROM gw.operating_evidence WHERE {S} AND run_id=cast(:run AS uuid)"
            ),
            p | {"run": data.run_id},
        ).scalar_one_or_none()
        if exists is not None:
            raise ApiError(
                409, "STATE_CHANGED", "이미 등록한 실행입니다. 실행 기록을 확인하세요."
            )
        values = (
            p
            | data.model_dump()
            | {
                "policy": row["id"],
                "u": ctx.user_id,
                "signature": payload["signature"],
                "metrics": json.dumps(
                    {
                        **data.metrics.model_dump(by_alias=True),
                        SOURCE_FIELD: payload["envelope"],
                    }
                ),
            }
        )
        id = c.execute(
            text("""INSERT INTO gw.operating_evidence(workspace_id,generation_id,run_id,kind,started_at,finished_at,policy_revision_id,code_revision,db_revision,manifest_digest,result,metrics,signer_key_id,signature,recorded_by_user_id,recorded_at)
        VALUES(:w,:g,cast(:run_id AS uuid),:kind,cast(:started_at AS timestamptz),cast(:finished_at AS timestamptz),:policy,:code_revision,:db_revision,:manifest_digest,:result,cast(:metrics AS jsonb),:signer_key_id,:signature,:u,clock_timestamp()) RETURNING id"""),
            values,
        ).scalar_one()
        audit(
            c,
            ctx,
            "operating_evidence",
            id,
            "operating_evidence.recorded",
            "서명된 운영 실행 증거 등록",
            {"kind": data.kind, "result": data.result, "runId": data.run_id},
        )
        return (
            {"id": str(id), "runId": data.run_id, "result": data.result},
            "gw.operating_evidence",
            id,
        )

    return company.action(
        context,
        company_id,
        "gw.operating_evidence.record",
        key,
        payload,
        run,
        authorize=authorize,
    )


def history(context, company_id, *, offset=0, limit=20):
    with company.transaction(context, company_id) as (c, ctx, _):
        _, roles = company.principal(c, ctx)
        if not roles.intersection({"SECURITY_ADMIN", "AUDITOR"}):
            raise ApiError(403, "FORBIDDEN", "운영 실행 기록을 확인할 권한이 없습니다.")
        p = {
            "w": ctx.workspace_id,
            "g": ctx.generation_id,
            "offset": offset,
            "limit": limit,
        }
        rows = (
            c.execute(
                text(f"""SELECT e.id,e.run_id,e.kind,e.result,e.started_at,e.finished_at,e.code_revision,e.db_revision,e.recorded_at,r.revision_no,
            (e.policy_revision_id=s.current_policy_revision_id) AS current_policy
            FROM gw.operating_evidence e JOIN gw.operating_policy_revision r ON (r.workspace_id,r.generation_id,r.id)=(e.workspace_id,e.generation_id,e.policy_revision_id)
            JOIN gw.operating_settings s ON (s.workspace_id,s.generation_id)=(e.workspace_id,e.generation_id)
            WHERE e.{S.replace(" AND ", " AND e.")} ORDER BY e.recorded_at DESC,e.id DESC LIMIT :limit OFFSET :offset"""),
                p,
            )
            .mappings()
            .all()
        )
        count = c.execute(
            text(f"SELECT count(*) FROM gw.operating_evidence WHERE {S}"), p
        ).scalar_one()
        return {
            "total": count,
            "items": [
                {
                    "id": str(r["id"]),
                    "runId": str(r["run_id"]),
                    "kind": r["kind"],
                    "result": r["result"],
                    "startedAt": r["started_at"].isoformat(),
                    "finishedAt": r["finished_at"].isoformat(),
                    "recordedAt": r["recorded_at"].isoformat(),
                    "revisionNo": r["revision_no"],
                    "currentPolicy": r["current_policy"],
                    "codeRevision": r["code_revision"],
                    "dbRevision": r["db_revision"],
                }
                for r in rows
            ],
        }
