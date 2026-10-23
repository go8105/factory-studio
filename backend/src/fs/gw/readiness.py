"""Reverify retained signed evidence; never authorizes deployment or access."""

from datetime import timedelta

from fs.common.errors import ApiError
from fs.gw.operating_contract import (
    EvidenceEnvelope,
    JournalAcceptanceDiagnostics,
    RecheckedAcceptanceDiagnostics,
    RegisteredAcceptanceDiagnostics,
    backup_is_current,
    timestamp,
    verify_evidence,
)

LABELS = {
    "BACKUP": "백업 실행",
    "RESTORE": "복원 실행",
    "ACCEPTANCE": "실환경 업무 인수",
}
SOURCE_FIELD = "_signedEnvelope"


def assess(
    rows,
    *,
    policy,
    policy_id,
    code_revision,
    db_revision,
    public_keys,
    now,
    connection=None,
):
    checks = []
    for kind, label in LABELS.items():
        observation = None
        recheck_summary = None
        row = next((r for r in rows if r["kind"] == kind), None)
        state, detail, verified = "MISSING", "등록된 실행 기록이 없습니다.", False
        if policy is None:
            state, detail = "POLICY_REQUIRED", "현재 운영 기준을 먼저 적용하세요."
        elif row is not None:
            state, detail, verified = evaluate(
                row, policy, policy_id, code_revision, db_revision, public_keys, now
            )
            if (
                kind == "ACCEPTANCE"
                and state in {"PARTIAL", "FAILED"}
                and verified
                and row["metrics"].get("acceptanceDiagnostics") is not None
            ):
                from fs.gw.acceptance_reconciliation import verify_registered_sources

                try:
                    data = EvidenceEnvelope.model_validate(row["metrics"][SOURCE_FIELD])
                    verify_registered_sources(
                        data,
                        rows,
                        policy_id=policy_id,
                        connection=connection,
                        policy=policy,
                        code_revision=code_revision,
                        db_revision=db_revision,
                        public_keys=public_keys,
                        now=now,
                        workspace_id=row["workspace_id"],
                        generation_id=row["generation_id"],
                    )
                    detail = "최신 백업·복원 원본과 서명 인수 점검 기록이 일치합니다. 외부 보관·전체 회수·실회사·최종 전환은 미확인입니다."
                    if isinstance(
                        data.metrics.acceptance_diagnostics,
                        RegisteredAcceptanceDiagnostics,
                    ):
                        detail = "DB 관측의 현재 기준과 최신 백업·복원 등록 원본을 재검증했습니다. 외부 보관·전체 회수·실회사·최종 전환은 미확인입니다."
                    if (
                        isinstance(
                            data.metrics.acceptance_diagnostics,
                            (
                                JournalAcceptanceDiagnostics,
                                RecheckedAcceptanceDiagnostics,
                            ),
                        )
                        and data.metrics.acceptance_diagnostics.journal_observation
                        is not None
                    ):
                        saved = data.metrics.acceptance_diagnostics.journal_observation.envelope
                        counts = saved["dispositions"]
                        observation = {
                            "observedAt": saved["observedAt"],
                            "scopeRecords": saved["scopeRecords"],
                            "auditConfirmed": counts["AUDIT_CONFIRMED"],
                            "abortConfirmed": counts["ABORT_CONFIRMED"],
                            "unresolvedRecords": saved["scopeRecords"]
                            - counts["AUDIT_CONFIRMED"]
                            - counts["ABORT_CONFIRMED"],
                            "missingTransactionProofs": saved[
                                "missingTransactionProofs"
                            ],
                        }
                        detail = (
                            "현재 회사 변경 기록의 서명 관측과 최신 백업·복원 원본을 재대조했습니다. 일부 확인이며 전체 수집·권한 회수·실회사 인수는 미확인입니다."
                            if state == "PARTIAL"
                            else "최근 관측에 미확인 거래 또는 기록이 남아 인수 점검이 미통과입니다. 원인을 조사한 뒤 새 관측으로 점검하세요."
                        )
                    if isinstance(
                        data.metrics.acceptance_diagnostics,
                        RecheckedAcceptanceDiagnostics,
                    ):
                        saved = (
                            data.metrics.acceptance_diagnostics.restore_recheck.envelope
                        )
                        recheck_summary = {
                            k: saved[k]
                            for k in (
                                "checkedAt",
                                "result",
                                "targetMeasured",
                                "stateMatchesExecution",
                                "reason",
                            )
                        }
                        if saved["version"] == 2:
                            recheck_summary["sourceObservation"] = {
                                key: saved["sourceObservation"][key]
                                for key in (
                                    "observedAt",
                                    "sourceMeasured",
                                    "contextMatches",
                                    "changedGroups",
                                    "reason",
                                    "result",
                                )
                            }
                        if saved["measurement"] is not None:
                            recheck_summary["measurement"] = {
                                k: saved["measurement"][k]
                                for k in (
                                    "unrevokedSessions",
                                    "pendingChallenges",
                                    "coreViolations",
                                    "gwViolations",
                                    "hrViolations",
                                    "journalUserViolations",
                                    "connectionLimitZero",
                                    "publicConnectRevoked",
                                )
                            }
                        detail = (
                            "최근 서명 관측 시점의 복원본 제한과 최신 등록 원본을 대조했습니다. 관측 유효 기한은15분이며 현재까지 연속 감시한 결과는 아닙니다."
                            if state == "PARTIAL"
                            else "최근 복원본 재관측이 미통과이거나 측정 불가입니다. 원인을 조사하고 새 관측을 등록하세요."
                        )

                except ApiError, ValueError, TypeError, KeyError:
                    state, verified = "INVALID", False
                    detail = "참조한 원본이 현재 최신 등록·변경 기록과 다르거나 재검증에 실패했습니다. 최신 원본으로 다시 점검하세요."
        checks.append(
            {
                "kind": kind,
                "label": label,
                "state": state,
                "detail": detail,
                "signatureVerified": verified,
                **(
                    {"journalObservation": observation}
                    if observation is not None
                    else {}
                ),
                **(
                    {"restoreRecheck": recheck_summary}
                    if recheck_summary is not None
                    else {}
                ),
            }
        )
    return checks


def evaluate(row, policy, policy_id, code_revision, db_revision, public_keys, now):
    if (
        row["policy_revision_id"] != policy_id
        or row["code_revision"] != code_revision
        or row["db_revision"] != db_revision
    ):
        return (
            "STALE",
            "현재 운영 기준·제품·DB 버전과 다릅니다. 새 기준으로 다시 검증하세요.",
            False,
        )
    if row["finished_at"] > now + timedelta(seconds=30) or now - row[
        "finished_at"
    ] > timedelta(days=30):
        return "STALE", "실행 시각이 미래이거나 확인 기한30일이 지났습니다.", False
    if row["signer_key_id"] not in public_keys:
        return (
            "INVALID",
            "현재 신뢰하는 실행자 키가 아닙니다. 운영 담당자가 확인하세요.",
            False,
        )
    if not isinstance(row["metrics"], dict) or SOURCE_FIELD not in row["metrics"]:
        return (
            "LEGACY_UNVERIFIED",
            "원본 서명 대상 내용이 없어 재검증할 수 없습니다. 새 실행 증거를 등록하세요.",
            False,
        )
    try:
        data = verify_evidence(
            row["metrics"][SOURCE_FIELD],
            row["signature"],
            public_keys=public_keys,
            workspace_id=row["workspace_id"],
            generation_id=row["generation_id"],
            policy=policy,
            code_revision=code_revision,
            db_revision=db_revision,
            now=now,
        )
        stored = EvidenceEnvelope.model_validate(
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
                "metrics": {
                    k: v for k, v in row["metrics"].items() if k != SOURCE_FIELD
                },
            }
        )
        # PostgreSQL timestamps normalize offsets; compare instants, then all other values.
        source = data.model_dump()
        target = stored.model_dump()
        for field in ("started_at", "finished_at"):
            if timestamp(source.pop(field)) != timestamp(target.pop(field)):
                raise ValueError()
        if source != target:
            raise ValueError()
    except ValueError, TypeError, KeyError, ApiError, OverflowError:
        return (
            "INVALID",
            "원본 서명·현재성 또는 등록 결과 대조에 실패했습니다. 운영 담당자가 확인하세요.",
            False,
        )
    if timestamp(data.finished_at) > now:
        return "STALE", "실행 시각이 미래입니다. 현재 시각을 확인하세요.", True
    if data.result == "FAIL":
        return (
            "FAILED",
            "가장 최근 등록한 실행이 미통과입니다. 이전 통과로 대신하지 않습니다.",
            True,
        )
    if data.result == "PARTIAL":
        return "PARTIAL", "일부 확인 상태입니다. 남은 검증을 마치세요.", True
    if data.kind == "BACKUP" and not backup_is_current(data, policy, now):
        return (
            "STALE",
            "백업 시점이 허용 손실 시간을 벗어났습니다. 새 백업을 확인하세요.",
            True,
        )
    return (
        "RECORDED_PASS",
        "현재 신뢰 키로 원본 서명과 등록 결과를 재검증했습니다. 외부 보관·전체 회수·실환경 인수는 별도입니다.",
        True,
    )
