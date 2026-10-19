"""Current registered evidence diagnostics; never authorizes deployment or access."""

from datetime import timedelta

from pydantic import ValidationError

from fs.common.errors import ApiError
from fs.gw.operating_contract import (
    EvidenceEnvelope,
    _validate_pass,
    backup_is_current,
    timestamp,
)

LABELS = {
    "BACKUP": "백업 실행",
    "RESTORE": "복원 실행",
    "ACCEPTANCE": "실환경 업무 인수",
}


def assess(rows, *, policy, policy_id, code_revision, db_revision, signer_ids, now):
    """Rows are newest registration per kind, scoped by the DB adapter."""
    checks = []
    for kind, label in LABELS.items():
        row = next((r for r in rows if r["kind"] == kind), None)
        state, detail = "MISSING", "등록된 실행 기록이 없습니다."
        if policy is None:
            state, detail = "POLICY_REQUIRED", "현재 운영 기준을 먼저 적용하세요."
        elif row is not None:
            state, detail = evaluate(
                row, policy, policy_id, code_revision, db_revision, signer_ids, now
            )
        checks.append({"kind": kind, "label": label, "state": state, "detail": detail})
    return checks


def evaluate(row, policy, policy_id, code_revision, db_revision, signer_ids, now):
    if (
        row["policy_revision_id"] != policy_id
        or row["code_revision"] != code_revision
        or row["db_revision"] != db_revision
    ):
        return (
            "STALE",
            "현재 운영 기준·제품·DB 버전과 다릅니다. 새 기준으로 다시 검증하세요.",
        )
    if row["signer_key_id"] not in signer_ids:
        return (
            "INVALID",
            "현재 신뢰하는 실행자 키가 아닙니다. 운영 담당자가 확인하세요.",
        )
    try:
        data = EvidenceEnvelope.model_validate(
            {
                "version": 1,
                "runId": str(row["run_id"]),
                "workspaceId": str(row["workspace_id"]),
                "generationId": str(row["generation_id"]),
                "policyDigest": policy.digest(),
                "kind": row["kind"],
                "startedAt": row["started_at"].isoformat(),
                "finishedAt": row["finished_at"].isoformat(),
                "codeRevision": row["code_revision"],
                "dbRevision": row["db_revision"],
                "manifestDigest": row["manifest_digest"],
                "result": row["result"],
                "signerKeyId": row["signer_key_id"],
                "metrics": row["metrics"],
            }
        )
        if timestamp(data.finished_at) > now or now - timestamp(
            data.finished_at
        ) > timedelta(days=30):
            return "STALE", "실행 시각이 미래이거나 확인 기한30일이 지났습니다."
        if data.result == "FAIL":
            return (
                "FAILED",
                "가장 최근 등록한 실행이 미통과입니다. 이전 통과로 대신하지 않습니다.",
            )
        if data.result == "PARTIAL":
            return "PARTIAL", "일부 확인 상태입니다. 남은 검증을 마치세요."
        _validate_pass(data, policy)
        if data.kind == "BACKUP" and not backup_is_current(data, policy, now):
            return (
                "STALE",
                "백업 시점이 허용 손실 시간을 벗어났습니다. 새 백업을 확인하세요.",
            )
    except ValidationError, ValueError, TypeError, KeyError, ApiError, OverflowError:
        return "INVALID", "등록된 실행 결과와 검사 항목을 확인할 수 없습니다."
    return (
        "RECORDED_PASS",
        "현재 기준의 등록된 통과입니다. 외부 보관·전체 회수·실환경 인수는 별도입니다.",
    )
