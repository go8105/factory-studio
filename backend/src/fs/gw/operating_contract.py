"""GW-READY-02 operating policy and signed evidence validation.

No database writes or UI-provided PASS override. Transactional adapters must bind
company, current policy, current actor and scope before using this contract.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from fs.common.errors import ApiError
from fs.core.backup import BackupError
from fs.gw.evidence_trust import authorize


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)


class OperatingPolicy(StrictModel):
    expected_people: int = Field(10, alias="expectedPeople", ge=1, le=10000)
    expected_departments: int = Field(1, alias="expectedDepartments", ge=1, le=1000)
    responsible_person_id: str = Field(
        alias="responsiblePersonId", pattern=r"^[1-9][0-9]{0,18}$"
    )
    backup_interval_minutes: int = Field(
        30, alias="backupIntervalMinutes", ge=5, le=1440
    )
    rpo_minutes: int = Field(60, alias="rpoMinutes", ge=1, le=1440)
    rto_minutes: int = Field(240, alias="rtoMinutes", ge=15, le=10080)
    document_review_months: int = Field(36, alias="documentReviewMonths", ge=1, le=120)
    audit_review_months: int = Field(12, alias="auditReviewMonths", ge=1, le=120)
    backup_keep_days: int = Field(30, alias="backupKeepDays", ge=7, le=365)
    reason: str = Field(min_length=2, max_length=500)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("변경 사유를 2자 이상 입력하세요.")
        return value.strip()

    @model_validator(mode="after")
    def backup_before_loss_target(self):
        if self.backup_interval_minutes >= self.rpo_minutes:
            raise ValueError("백업 간격은 허용 손실 시간보다 짧아야 합니다.")
        return self

    def digest(self) -> str:
        return hashlib.sha256(canonical(self.model_dump(by_alias=True))).hexdigest()


def canonical(value: dict) -> bytes:
    """Only JSON values are accepted. Never sign Python repr or ambiguous floats."""
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


class RestoreExecutionObservation(StrictModel):
    version: Literal[1]
    scope: Literal["RESTORED_CHECKPOINT_RESTRICTIONS"]
    observed_at: str = Field(alias="observedAt")
    clock_tolerance_seconds: Literal[30] = Field(alias="clockToleranceSeconds")
    backup_run_id: str = Field(alias="backupRunId")
    checkpoint_run_id: str = Field(alias="checkpointRunId")
    backup_manifest_digest: str = Field(
        alias="backupManifestDigest", pattern=r"^[0-9a-f]{64}$"
    )
    checkpoint_digest: str = Field(alias="checkpointDigest", pattern=r"^[0-9a-f]{64}$")
    checkpoint_manifest_digest: str = Field(
        alias="checkpointManifestDigest", pattern=r"^[0-9a-f]{64}$"
    )
    source_identity: str = Field(alias="sourceIdentity", pattern=r"^[0-9a-f]{64}$")
    target_identity: str = Field(alias="targetIdentity", pattern=r"^[0-9a-f]{64}$")
    state_digest: str = Field(alias="stateDigest", pattern=r"^[0-9a-f]{64}$")
    connection_limit_zero: bool = Field(alias="connectionLimitZero")
    public_connect_revoked: bool = Field(alias="publicConnectRevoked")
    db_revision_matches: bool = Field(alias="dbRevisionMatches")
    unrevoked_sessions: int = Field(alias="unrevokedSessions", ge=0, le=10000000)
    pending_challenges: int = Field(alias="pendingChallenges", ge=0, le=10000000)
    core_violations: int = Field(alias="coreViolations", ge=0, le=10000000)
    gw_violations: int = Field(alias="gwViolations", ge=0, le=10000000)
    hr_violations: int = Field(alias="hrViolations", ge=0, le=10000000)
    journal_user_violations: int = Field(
        alias="journalUserViolations", ge=0, le=10000000
    )
    result: Literal["PARTIAL", "BLOCKED"]
    revocations_complete: Literal[False] = Field(alias="revocationsComplete")
    live_company_acceptance: Literal[False] = Field(alias="liveCompanyAcceptance")
    release_authorized: Literal[False] = Field(alias="releaseAuthorized")
    current_target_state_verified: Literal[False] = Field(
        alias="currentTargetStateVerified"
    )

    @model_validator(mode="before")
    @classmethod
    def exact_literals(cls, value):
        if isinstance(value, dict):
            if (
                type(value.get("version")) is not int
                or type(
                    value.get(
                        "clockToleranceSeconds", value.get("clock_tolerance_seconds")
                    )
                )
                is not int
            ):
                raise ValueError("invalid observation version")
            for name, field in cls.model_fields.items():
                key = field.alias if field.alias in value else name
                if (
                    field.annotation == Literal[False]
                    and type(value.get(key)) is not bool
                ):
                    raise ValueError("invalid observation completion flag")
        return value

    @model_validator(mode="after")
    def bounded_result(self):
        for run in [self.backup_run_id, self.checkpoint_run_id]:
            if UUID(run).version != 4 or str(UUID(run)) != run:
                raise ValueError("invalid observation run")
        timestamp(self.observed_at)
        if (
            self.source_identity == self.target_identity
            or self.backup_run_id == self.checkpoint_run_id
        ):
            raise ValueError("restore must be distinct from source")
        clear = (
            self.connection_limit_zero
            and self.public_connect_revoked
            and self.db_revision_matches
            and not any(
                [
                    self.unrevoked_sessions,
                    self.pending_challenges,
                    self.core_violations,
                    self.gw_violations,
                    self.hr_violations,
                    self.journal_user_violations,
                ]
            )
        )
        if self.result != ("PARTIAL" if clear else "BLOCKED"):
            raise ValueError("observation result mismatch")
        return self


class RestoreDiagnostics(StrictModel):
    version: Literal[1]
    database_closed: bool = Field(alias="databaseClosed")
    db_revision_matches: bool = Field(alias="dbRevisionMatches")
    checkpoint_restrictions_applied: bool = Field(alias="checkpointRestrictionsApplied")
    checkpoint_completeness_confirmed: bool = Field(
        alias="checkpointCompletenessConfirmed"
    )
    journal_candidate_intents: int = Field(
        alias="journalCandidateIntents", ge=0, le=10000000
    )
    journal_unconfirmed_intents: int = Field(
        alias="journalUnconfirmedIntents", ge=0, le=10000000
    )
    journal_quarantined_scopes: int = Field(
        alias="journalQuarantinedScopes", ge=0, le=10000000
    )

    @model_validator(mode="after")
    def consistent_counts(self):
        if self.journal_unconfirmed_intents > self.journal_candidate_intents:
            raise ValueError("미확인 기록 수가 대조 대상 수보다 많습니다.")
        return self


class ObservedRestoreDiagnostics(RestoreDiagnostics):
    version: Literal[2]
    execution_observation: RestoreExecutionObservation = Field(
        alias="executionObservation"
    )

    @model_validator(mode="before")
    @classmethod
    def integer_version(cls, value):
        if isinstance(value, dict) and type(value.get("version")) is not int:
            raise ValueError("invalid restore diagnostic version")
        return value

    @model_validator(mode="after")
    def consistent_observation(self):
        observation = self.execution_observation
        if (
            self.database_closed
            != (
                observation.connection_limit_zero and observation.public_connect_revoked
            )
            or self.db_revision_matches != observation.db_revision_matches
            or self.checkpoint_completeness_confirmed
        ):
            raise ValueError("restore observation does not establish completeness")
        return self


class EvidenceReference(StrictModel):
    run_id: str = Field(alias="runId")
    source_digest: str = Field(alias="sourceDigest", pattern=r"^[0-9a-f]{64}$")

    @field_validator("run_id")
    @classmethod
    def uuid_run(cls, value):
        parsed = UUID(value)
        if parsed.version != 4 or str(parsed) != value:
            raise ValueError("runId must be canonical UUID4")
        return value


class AcceptanceDiagnostics(StrictModel):
    version: Literal[1]
    scope: Literal["BACKUP_RESTORE_RECONCILIATION"]
    backup: EvidenceReference
    restore: EvidenceReference
    external_storage: Literal["UNVERIFIED"] = Field(alias="externalStorage")
    journal_coverage: Literal["UNVERIFIED"] = Field(alias="journalCoverage")
    live_company: Literal["UNVERIFIED"] = Field(alias="liveCompany")
    final_release: Literal["UNVERIFIED"] = Field(alias="finalRelease")


class RegisteredAcceptanceDiagnostics(AcceptanceDiagnostics):
    version: Literal[2]
    scope: Literal["CURRENT_REGISTERED_SOURCES"]
    observed_at: str = Field(alias="observedAt")
    context_digest: str = Field(alias="contextDigest", pattern=r"^[0-9a-f]{64}$")


class JournalObservationDocument(StrictModel):
    envelope: dict
    signature: str = Field(max_length=100)

    @model_validator(mode="after")
    def observation_contract(self):
        from fs.gw.journal_observation import JournalObservation

        JournalObservation.model_validate(self.envelope)
        return self


class JournalAcceptanceDiagnostics(RegisteredAcceptanceDiagnostics):
    version: Literal[3]
    scope: Literal["CURRENT_REGISTERED_SOURCES_AND_JOURNAL"]
    journal_observation: JournalObservationDocument = Field(alias="journalObservation")

    @model_validator(mode="before")
    @classmethod
    def integer_version(cls, value):
        if isinstance(value, dict) and type(value.get("version")) is not int:
            raise ValueError("진단 버전은 정수여야 합니다.")
        return value


class RestoreRecheckDocument(StrictModel):
    envelope: dict
    signature: str = Field(max_length=100)

    @model_validator(mode="after")
    def recheck_contract(self):
        from fs.gw.restore_recheck import parse_envelope

        parse_envelope(self.envelope)
        return self


class RecheckedAcceptanceDiagnostics(RegisteredAcceptanceDiagnostics):
    version: Literal[4]
    scope: Literal["CURRENT_REGISTERED_SOURCES_AND_RESTORE_RECHECK"]
    restore_recheck: RestoreRecheckDocument = Field(alias="restoreRecheck")
    journal_observation: JournalObservationDocument | None = Field(
        None, alias="journalObservation"
    )

    @model_validator(mode="before")
    @classmethod
    def integer_version(cls, value):
        if isinstance(value, dict) and type(value.get("version")) is not int:
            raise ValueError("invalid rechecked acceptance version")
        return value


class EvidenceMetrics(StrictModel):
    acceptance_diagnostics: (
        AcceptanceDiagnostics
        | RegisteredAcceptanceDiagnostics
        | JournalAcceptanceDiagnostics
        | RecheckedAcceptanceDiagnostics
        | None
    ) = Field(None, alias="acceptanceDiagnostics")
    restore_diagnostics: RestoreDiagnostics | ObservedRestoreDiagnostics | None = Field(
        None, alias="restoreDiagnostics"
    )
    # Closed allowlist deliberately excludes URLs, document contents and identities.
    snapshot_started_at: str | None = Field(None, alias="snapshotStartedAt")
    storage_confirmed_at: str | None = Field(None, alias="storageConfirmedAt")
    artifact_digest: str | None = Field(
        None, alias="artifactDigest", pattern=r"^[0-9a-f]{64}$"
    )
    row_hashes_match: bool | None = Field(None, alias="rowHashesMatch")
    foreign_keys_valid: bool | None = Field(None, alias="foreignKeysValid")
    sessions_invalidated: bool | None = Field(None, alias="sessionsInvalidated")
    revocations_reapplied: bool | None = Field(None, alias="revocationsReapplied")
    two_account_checks: bool | None = Field(None, alias="twoAccountChecks")
    loss_window_seconds: int | None = Field(
        None, alias="lossWindowSeconds", ge=0, le=31536000
    )
    elapsed_seconds: int | None = Field(None, alias="elapsedSeconds", ge=0, le=31536000)
    failed_check_count: int = Field(0, alias="failedCheckCount", ge=0, le=100000)


class EvidenceEnvelope(StrictModel):
    version: Literal[1]
    run_id: str = Field(alias="runId")
    workspace_id: str = Field(alias="workspaceId", pattern=r"^[1-9][0-9]{0,18}$")
    generation_id: str = Field(alias="generationId", pattern=r"^[1-9][0-9]{0,18}$")
    policy_digest: str = Field(alias="policyDigest", pattern=r"^[0-9a-f]{64}$")
    kind: Literal["BACKUP", "RESTORE", "ACCEPTANCE", "INCIDENT"]
    started_at: str = Field(alias="startedAt")
    finished_at: str = Field(alias="finishedAt")
    code_revision: str = Field(alias="codeRevision", pattern=r"^[0-9a-f]{7,64}$")
    db_revision: str = Field(alias="dbRevision", pattern=r"^[A-Za-z0-9_]{1,100}$")
    manifest_digest: str = Field(alias="manifestDigest", pattern=r"^[0-9a-f]{64}$")
    result: Literal["PASS", "FAIL", "PARTIAL"]
    signer_key_id: str = Field(alias="signerKeyId", pattern=r"^[A-Za-z0-9_-]{1,60}$")
    metrics: EvidenceMetrics

    @field_validator("run_id")
    @classmethod
    def uuid_run(cls, value):
        parsed = UUID(value)
        if parsed.version != 4 or str(parsed) != value:
            raise ValueError("runId must be canonical UUID4")
        return value

    @model_validator(mode="after")
    def chronological(self):
        acceptance = self.metrics.acceptance_diagnostics
        if acceptance is not None:
            if isinstance(acceptance, RegisteredAcceptanceDiagnostics) and timestamp(
                acceptance.observed_at
            ) != timestamp(self.started_at):
                raise ValueError("DB 관측 시각과 인수 실행 시작이 다릅니다.")
            expected_result = "PARTIAL"
            if (
                isinstance(
                    acceptance,
                    (JournalAcceptanceDiagnostics, RecheckedAcceptanceDiagnostics),
                )
                and acceptance.journal_observation is not None
            ):
                observation = acceptance.journal_observation.envelope
                expected_result = (
                    "FAIL" if observation["result"] == "BLOCKED" else "PARTIAL"
                )
                if observation["runId"] in {
                    self.run_id,
                    acceptance.backup.run_id,
                    acceptance.restore.run_id,
                }:
                    raise ValueError("관측 실행 번호를 재사용할 수 없습니다.")
                if timestamp(observation["observedAt"]) > timestamp(self.started_at):
                    raise ValueError("인수 시작 이후의 관측을 참조할 수 없습니다.")
            if isinstance(acceptance, RecheckedAcceptanceDiagnostics):
                recheck = acceptance.restore_recheck.envelope
                if recheck["runId"] in {
                    self.run_id,
                    acceptance.backup.run_id,
                    acceptance.restore.run_id,
                } or (
                    acceptance.journal_observation is not None
                    and recheck["runId"]
                    == acceptance.journal_observation.envelope["runId"]
                ):
                    raise ValueError("인수 재관측 실행 번호를 재사용할 수 없습니다.")
                if recheck["result"] == "BLOCKED":
                    expected_result = "FAIL"
            if self.kind != "ACCEPTANCE" or self.result != expected_result:
                raise ValueError(
                    "원본 대조 진단은 인수 일부 확인·미통과에만 허용합니다."
                )
            if self.metrics.failed_check_count or set(
                self.metrics.model_dump(exclude_none=True)
            ) != {"acceptance_diagnostics", "failed_check_count"}:
                raise ValueError("인수 원본 대조에 다른 검사 결과를 섞을 수 없습니다.")
            if (
                len({self.run_id, acceptance.backup.run_id, acceptance.restore.run_id})
                != 3
            ):
                raise ValueError("실행 번호를 재사용할 수 없습니다.")
            if (
                self.manifest_digest
                != hashlib.sha256(
                    canonical(acceptance.model_dump(by_alias=True))
                ).hexdigest()
            ):
                raise ValueError("인수 대조 명세 지문이 다릅니다.")
        if self.metrics.restore_diagnostics is not None and self.kind != "RESTORE":
            raise ValueError("복원 진단은 복원 증거에만 포함할 수 있습니다.")
        if isinstance(self.metrics.restore_diagnostics, ObservedRestoreDiagnostics):
            observation = self.metrics.restore_diagnostics.execution_observation
            if (
                not timestamp(self.started_at) - timedelta(seconds=30)
                <= timestamp(observation.observed_at)
                <= timestamp(self.finished_at) + timedelta(seconds=30)
            ):
                raise ValueError("복원 관측 시각이 실행 범위 밖입니다.")
            if observation.backup_manifest_digest != self.manifest_digest:
                raise ValueError("복원 관측의 백업 명세 지문이 다릅니다.")
            if (
                self.run_id
                in {observation.backup_run_id, observation.checkpoint_run_id}
                or self.metrics.sessions_invalidated
                != (observation.unrevoked_sessions == 0)
                or self.metrics.revocations_reapplied is not False
                or self.metrics.two_account_checks is not False
                or self.result
                != ("PARTIAL" if observation.result == "PARTIAL" else "FAIL")
            ):
                raise ValueError(
                    "복원 관측을 전체 회수/업무 인수로 승격할 수 없습니다."
                )
        if timestamp(self.started_at) > timestamp(self.finished_at):
            raise ValueError("실행 시작과 종료 시각을 확인하세요.")
        return self


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(UTC)


def acceptance_context_digest(
    *, workspace_id, generation_id, policy, code_revision, db_revision
):
    return hashlib.sha256(
        canonical(
            {
                "workspaceId": workspace_id,
                "generationId": generation_id,
                "policy": policy.model_dump(by_alias=True),
                "codeRevision": code_revision,
                "dbRevision": db_revision,
            }
        )
    ).hexdigest()


def evidence_error() -> ApiError:
    return ApiError(
        400,
        "OPERATING_EVIDENCE_INVALID",
        "실행 증거의 서명·범위·검사 결과를 확인해 주세요.",
    )


def verify_evidence(
    payload: dict,
    signature: str,
    *,
    public_keys: Mapping[str, bytes],
    workspace_id: int,
    generation_id: int,
    policy: OperatingPolicy,
    db_revision: str,
    code_revision: str,
    now: datetime,
) -> EvidenceEnvelope:
    """Signature authenticates the runner, not correctness of a compromised runner."""
    try:
        if now.tzinfo is None:
            raise ValueError("timezone required")
        if len(canonical(payload)) > 16384 or len(signature) > 100:
            raise ValueError("oversized envelope")
        data = EvidenceEnvelope.model_validate(payload)
        authorize(public_keys, data.signer_key_id, data.kind, data.workspace_id)
        key = public_keys[data.signer_key_id]
        raw_signature = base64.b64decode(signature, validate=True)
        Ed25519PublicKey.from_public_bytes(key).verify(
            raw_signature, canonical(payload)
        )
        if (
            data.workspace_id != str(workspace_id)
            or data.generation_id != str(generation_id)
            or data.policy_digest != policy.digest()
            or data.db_revision != db_revision
            or data.code_revision != code_revision
            or timestamp(data.finished_at) > now + timedelta(seconds=30)
            or timestamp(data.started_at) > now + timedelta(seconds=30)
            or now - timestamp(data.finished_at) > timedelta(days=30)
        ):
            raise ValueError("scope, version or time mismatch")
        diagnostic = data.metrics.acceptance_diagnostics
        if isinstance(
            diagnostic, RegisteredAcceptanceDiagnostics
        ) and diagnostic.context_digest != acceptance_context_digest(
            workspace_id=workspace_id,
            generation_id=generation_id,
            policy=policy,
            code_revision=code_revision,
            db_revision=db_revision,
        ):
            raise ValueError("current database snapshot context mismatch")
        if (
            isinstance(
                diagnostic,
                (JournalAcceptanceDiagnostics, RecheckedAcceptanceDiagnostics),
            )
            and diagnostic.journal_observation is not None
        ):
            from fs.gw.journal_observation import verify

            observed = verify(
                diagnostic.journal_observation.model_dump(),
                public_keys=public_keys,
                company_id=workspace_id,
                code_revision=code_revision,
                now=now,
            )
            if (
                observed.generation_id != str(generation_id)
                or observed.policy_digest != policy.digest()
                or observed.db_revision != db_revision
                or observed.context_digest != diagnostic.context_digest
            ):
                raise ValueError("journal observation context mismatch")
        if isinstance(diagnostic, RecheckedAcceptanceDiagnostics):
            from fs.gw.restore_recheck import verify_signature

            rechecked = verify_signature(
                diagnostic.restore_recheck.model_dump(),
                public_keys=public_keys,
                workspace_id=workspace_id,
                generation_id=generation_id,
                policy=policy,
                code_revision=code_revision,
                db_revision=db_revision,
                now=now,
            )
            if rechecked.restore != diagnostic.restore or timestamp(
                rechecked.checked_at
            ) > timestamp(data.started_at) + timedelta(seconds=30):
                raise ValueError("recheck reference or observation time mismatch")
        if data.result == "PASS":
            _validate_pass(data, policy)
        return data
    except (
        ValidationError,
        ValueError,
        KeyError,
        TypeError,
        InvalidSignature,
        BackupError,
        OverflowError,
    ):
        raise evidence_error() from None


def _validate_pass(data: EvidenceEnvelope, policy: OperatingPolicy):
    m = data.metrics
    if m.failed_check_count:
        raise ValueError("failed checks")
    if data.kind == "BACKUP":
        if (
            not m.snapshot_started_at
            or not m.storage_confirmed_at
            or not m.artifact_digest
        ):
            raise ValueError("missing backup checks")
        snapshot = timestamp(m.snapshot_started_at)
        stored = timestamp(m.storage_confirmed_at)
        if (
            not timestamp(data.started_at)
            <= snapshot
            <= stored
            <= timestamp(data.finished_at)
        ):
            raise ValueError("backup chronology")
    elif data.kind == "RESTORE":
        diagnostic = m.restore_diagnostics
        if diagnostic is not None and (
            not diagnostic.database_closed
            or not diagnostic.db_revision_matches
            or not diagnostic.checkpoint_restrictions_applied
            or not diagnostic.checkpoint_completeness_confirmed
            or diagnostic.journal_unconfirmed_intents
            or diagnostic.journal_quarantined_scopes
        ):
            raise ValueError("미확인 복원 진단을 통과로 처리할 수 없습니다.")
        checks = (
            m.row_hashes_match,
            m.foreign_keys_valid,
            m.sessions_invalidated,
            m.revocations_reapplied,
            m.two_account_checks,
        )
        if not all(check is True for check in checks):
            raise ValueError("missing restore checks")
        if m.loss_window_seconds is None or m.elapsed_seconds is None:
            raise ValueError("missing measurement")
        if (
            m.loss_window_seconds > policy.rpo_minutes * 60
            or m.elapsed_seconds > policy.rto_minutes * 60
        ):
            raise ValueError("target exceeded")
        actual = (
            timestamp(data.finished_at) - timestamp(data.started_at)
        ).total_seconds()
        if m.elapsed_seconds < actual:
            raise ValueError("duration understated")
    else:
        # Acceptance and incident proof contracts require actual adapter checks.
        raise ValueError("PASS contract not yet defined for this kind")


def backup_is_current(
    data: EvidenceEnvelope, policy: OperatingPolicy, now: datetime
) -> bool:
    if (
        data.kind != "BACKUP"
        or data.result != "PASS"
        or data.policy_digest != policy.digest()
    ):
        return False
    snapshot = data.metrics.snapshot_started_at
    return snapshot is not None and timedelta(0) <= now - timestamp(
        snapshot
    ) <= timedelta(minutes=policy.rpo_minutes)
