"""Keep source-drift failures as recovery boundaries, never release approvals."""

import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import text

from fs.common.errors import ApiError
from fs.gw.evidence_trust import authorize
from fs.gw.operating_contract import (
    EvidenceEnvelope,
    ObservedRestoreDiagnostics,
    RecheckedAcceptanceDiagnostics,
    canonical,
    evidence_error,
    timestamp,
)


def latest_boundary(connection, *, workspace_id, generation_id, public_keys):
    # Registration order across every policy/version. No successful-run fallback.
    row = (
        connection.execute(
            text("""SELECT * FROM gw.operating_evidence
        WHERE workspace_id=:w AND generation_id=:g AND kind='ACCEPTANCE' AND result='FAIL'
        AND metrics->'acceptanceDiagnostics'->'restoreRecheck'->'envelope'->'sourceObservation'->>'reason'='CHANGED'
        ORDER BY recorded_at DESC,id DESC LIMIT 1"""),
            {"w": workspace_id, "g": generation_id},
        )
        .mappings()
        .one_or_none()
    )
    return boundary(row, public_keys) if row else None


def boundary(row, public_keys):
    """A historical signature is checked without treating its old scope as current.

    Missing/corrupted/revoked originals demand a new backup, rather than trusting
    old checkpoint IDs. No old policy or freshness result authorizes a new run.
    """
    result = {
        "runId": str(row["run_id"]),
        "recordedAt": row["recorded_at"],
        "trustedOriginal": False,
        "previous": None,
    }
    try:
        raw = row["metrics"]["_signedEnvelope"]
        data = EvidenceEnvelope.model_validate(raw)
        for envelope, signature in [
            (raw, row["signature"]),
            (
                data.metrics.acceptance_diagnostics.restore_recheck.envelope,
                data.metrics.acceptance_diagnostics.restore_recheck.signature,
            ),
        ]:
            authorize(
                public_keys,
                envelope["signerKeyId"],
                envelope["kind"],
                str(row["workspace_id"]),
            )
            Ed25519PublicKey.from_public_bytes(
                public_keys[envelope["signerKeyId"]]
            ).verify(base64.b64decode(signature, validate=True), canonical(envelope))
        for key in (
            "workspace_id",
            "generation_id",
            "run_id",
            "kind",
            "result",
            "code_revision",
            "db_revision",
            "manifest_digest",
            "signer_key_id",
        ):
            if str(getattr(data, key)) != str(row[key]):
                raise ValueError("historical row mismatch")
        if (
            timestamp(data.started_at) != row["started_at"]
            or timestamp(data.finished_at) != row["finished_at"]
        ):
            raise ValueError("historical clock mismatch")
        if data.metrics.model_dump(by_alias=True) != {
            key: value
            for key, value in row["metrics"].items()
            if key != "_signedEnvelope"
        }:
            raise ValueError("historical metrics mismatch")
        diagnostic = data.metrics.acceptance_diagnostics
        if (
            not isinstance(diagnostic, RecheckedAcceptanceDiagnostics)
            or data.kind != "ACCEPTANCE"
            or data.result != "FAIL"
        ):
            raise ValueError("source failure required")
        recheck = diagnostic.restore_recheck.envelope
        if (
            recheck["version"] not in {2, 3, 4}
            or recheck["sourceObservation"]["reason"] != "CHANGED"
        ):
            raise ValueError("source change required")
        result.update(
            trustedOriginal=True,
            previous={
                "restoreRunId": diagnostic.restore.run_id,
                "targetIdentity": recheck["targetIdentity"],
                "measurement": recheck["measurement"],
            },
        )
    except ValueError, TypeError, KeyError, AttributeError, InvalidSignature:
        pass
    return result


def next_step(anchor, backup, restore):
    previous = anchor["previous"]
    if backup is None or (
        (previous is None or previous["measurement"] is None)
        and timestamp(backup.started_at) <= anchor["recordedAt"]
    ):
        return "NEW_BACKUP_REQUIRED"
    if (
        restore is None
        or timestamp(restore.started_at) <= anchor["recordedAt"]
        or not isinstance(
            restore.metrics.restore_diagnostics, ObservedRestoreDiagnostics
        )
    ):
        return "NEW_RESTORE_REQUIRED"
    observed = restore.metrics.restore_diagnostics.execution_observation
    if (
        observed.backup_run_id != backup.run_id
        or backup.manifest_digest != restore.manifest_digest
    ):
        return "NEW_RESTORE_REQUIRED"
    if previous is not None:
        old = previous["measurement"]
        if (
            restore.run_id == previous["restoreRunId"]
            or observed.target_identity == previous["targetIdentity"]
            or (
                old is not None
                and (
                    observed.checkpoint_run_id == old["checkpointRunId"]
                    or observed.checkpoint_digest == old["checkpointDigest"]
                )
            )
        ):
            return "NEW_RESTORE_REQUIRED"
    return "RECHECK_REQUIRED"


def require_recovery(connection, data, documents, **context):
    if connection is None or data.kind != "ACCEPTANCE" or data.result != "PARTIAL":
        return
    anchor = latest_boundary(
        connection,
        **{
            key: context[key]
            for key in ("workspace_id", "generation_id", "public_keys")
        },
    )
    if anchor is None:
        return
    diagnostic = data.metrics.acceptance_diagnostics
    if not isinstance(diagnostic, RecheckedAcceptanceDiagnostics):
        raise evidence_error()
    checked = diagnostic.restore_recheck.envelope
    if (
        checked["version"] not in {2, 3, 4}
        or checked["sourceObservation"]["reason"] != "MATCH"
        or not checked["sourceObservation"]["sourceMeasured"]
        or not checked["targetMeasured"]
    ):
        raise evidence_error()
    sources = {
        kind: EvidenceEnvelope.model_validate(document["envelope"])
        for kind, document in documents.items()
    }
    step = next_step(anchor, sources["BACKUP"], sources["RESTORE"])
    # A different UUID/file is insufficient: the checkpoint itself must have
    # been captured after the registered failure. Current-source MATCH can miss
    # an intervening change followed by a revert.
    if step == "RECHECK_REQUIRED" and (
        checked["version"] not in {3, 4}
        or timestamp(checked["checkpointHead"]["payload"]["capturedAt"])
        <= anchor["recordedAt"]
    ):
        step = "NEW_RESTORE_REQUIRED"
    if step != "RECHECK_REQUIRED":
        raise ApiError(
            400,
            "OPERATING_RECOVERY_REQUIRED",
            "원본 변경 실패 이후 새 백업부터 다시 점검하세요."
            if step == "NEW_BACKUP_REQUIRED"
            else "원본 변경 실패 등록 이후 생성한 권한 대조를 사용해 새 격리 복원을 실행·등록하세요. 서명 HEAD를 포함해 현재 원본과 다시 관측하세요.",
            {"nextStep": step},
        )


def summary(connection, rows, checks, **context):
    anchor = latest_boundary(
        connection,
        **{
            key: context[key]
            for key in ("workspace_id", "generation_id", "public_keys")
        },
    )
    if anchor is None:
        return None
    by_kind = {check["kind"]: check for check in checks}
    sources = {}
    for row in rows:
        check = by_kind.get(row["kind"], {})
        if (
            row["kind"] in {"BACKUP", "RESTORE"}
            and check.get("signatureVerified")
            and check.get("state")
            in ({"RECORDED_PASS"} if row["kind"] == "BACKUP" else {"PARTIAL"})
        ):
            sources[row["kind"]] = EvidenceEnvelope.model_validate(
                row["metrics"]["_signedEnvelope"]
            )
    step = next_step(anchor, sources.get("BACKUP"), sources.get("RESTORE"))
    accepted = by_kind.get("ACCEPTANCE", {}).get("state") == "PARTIAL" and by_kind.get(
        "ACCEPTANCE", {}
    ).get("signatureVerified")
    if step == "RECHECK_REQUIRED" and accepted:
        step = "RECOVERY_PARTIAL"
    actions = {
        "NEW_BACKUP_REQUIRED": "현재 백업을 확인할 수 없거나 이전 실패 원본·복원 관측을 재검증할 수 없습니다. 실패 등록 이후 새 백업부터 만들고 새 권한 대조와 격리 복원을 진행하세요.",
        "NEW_RESTORE_REQUIRED": "변경 원인을 확인하고 실패 등록 이후 생성한 권한 대조를 사용해 새 격리 복원을 실행·등록하세요. 이전 복원본을 다시 관측한 결과로 대신할 수 없습니다.",
        "RECHECK_REQUIRED": "서명 HEAD를 포함해 새 복원본과 현재 원본을 다시 관측하고 새 인수 점검을 등록하세요. 대조 생성 시각도 실패 등록 이후여야 합니다. 변경 기록 관측이 필요했던 회사는 함께 포함하세요.",
        "RECOVERY_PARTIAL": "새 복원본을 사용한 후속 점검까지 일부 확인했습니다. 외부 보관·전체 회수·실회사 인수·최종 운영 전환은 별도로 확인하세요.",
    }
    return {
        "state": step,
        "failedRunId": anchor["runId"],
        "failedRecordedAt": anchor["recordedAt"].isoformat(),
        "failureOriginalVerified": anchor["trustedOriginal"],
        "nextAction": actions[step],
        "ready": False,
    }
