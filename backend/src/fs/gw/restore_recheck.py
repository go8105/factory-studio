"""Fresh scoped snapshots of an existing closed restore, never release authority."""

import base64
import hashlib
from datetime import timedelta
from typing import Literal
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import Field, model_validator

from fs.gw.evidence_trust import EvidenceTrust, authorize
from fs.gw.operating_contract import (
    EvidenceReference,
    ObservedRestoreDiagnostics,
    RestoreExecutionObservation,
    StrictModel,
    canonical,
    timestamp,
    verify_evidence,
)
from fs.gw.source_checkpoint import SourceCheckpointObservation


class RestoreRecheck(StrictModel):
    version: Literal[1]
    kind: Literal["RESTORE_RECHECK"]
    scope: Literal["CURRENT_RESTORED_CHECKPOINT_RESTRICTIONS"]
    run_id: str = Field(alias="runId")
    workspace_id: str = Field(alias="workspaceId", pattern=r"^[1-9][0-9]{0,18}$")
    generation_id: str = Field(alias="generationId", pattern=r"^[1-9][0-9]{0,18}$")
    policy_digest: str = Field(alias="policyDigest", pattern=r"^[0-9a-f]{64}$")
    code_revision: str = Field(alias="codeRevision", pattern=r"^[0-9a-f]{7,64}$")
    db_revision: str = Field(alias="dbRevision", pattern=r"^[A-Za-z0-9_]{1,100}$")
    checked_at: str = Field(alias="checkedAt")
    restore: EvidenceReference
    target_identity: str = Field(alias="targetIdentity", pattern=r"^[0-9a-f]{64}$")
    measurement: RestoreExecutionObservation | None
    target_measured: bool = Field(alias="targetMeasured")
    state_matches_execution: bool | None = Field(alias="stateMatchesExecution")
    reason: Literal["MEASURED", "MEASUREMENT_UNAVAILABLE"]
    result: Literal["PARTIAL", "BLOCKED"]
    signer_key_id: str = Field(alias="signerKeyId", pattern=r"^[A-Za-z0-9_-]{1,60}$")
    ready: Literal[False]
    revocations_complete: Literal[False] = Field(alias="revocationsComplete")
    live_company_acceptance: Literal[False] = Field(alias="liveCompanyAcceptance")
    release_authorized: Literal[False] = Field(alias="releaseAuthorized")

    @model_validator(mode="before")
    @classmethod
    def exact_literals(cls, value):
        if isinstance(value, dict):
            if type(value.get("version")) is not int:
                raise ValueError("invalid recheck version")
            for name, field in cls.model_fields.items():
                key = field.alias if field.alias in value else name
                if (
                    field.annotation == Literal[False]
                    and type(value.get(key)) is not bool
                ):
                    raise ValueError("invalid completion flag")
        return value

    def expected_result(self):
        return self.measurement.result if self.measurement is not None else "BLOCKED"

    @model_validator(mode="after")
    def consistent_snapshot(self):
        EvidenceReference(runId=self.run_id, sourceDigest=self.target_identity)
        if self.run_id == self.restore.run_id:
            raise ValueError("reused restore run")
        checked = timestamp(self.checked_at)
        if self.measurement is None:
            if (
                self.target_measured
                or self.state_matches_execution is not None
                or self.reason != "MEASUREMENT_UNAVAILABLE"
                or self.result != "BLOCKED"
            ):
                raise ValueError("unavailable measurements cannot be inferred")
        elif (
            not self.target_measured
            or self.reason != "MEASURED"
            or self.state_matches_execution is None
            or self.target_identity != self.measurement.target_identity
            or abs((checked - timestamp(self.measurement.observed_at)).total_seconds())
            > 30
            or self.result != self.expected_result()
        ):
            raise ValueError("recheck measurement mismatch")
        return self


class CurrentSourceRestoreRecheck(RestoreRecheck):
    version: Literal[2]
    scope: Literal["CURRENT_SOURCE_AND_RESTORED_CHECKPOINT_RESTRICTIONS"]
    source_observation: SourceCheckpointObservation = Field(alias="sourceObservation")

    def expected_result(self):
        return (
            "BLOCKED"
            if self.source_observation.result == "BLOCKED"
            else super().expected_result()
        )

    @model_validator(mode="after")
    def source_clock(self):
        if (
            abs(
                (
                    timestamp(self.checked_at)
                    - timestamp(self.source_observation.observed_at)
                ).total_seconds()
            )
            > 30
        ):
            raise ValueError("source and restore observation clocks differ")
        return self


def parse_envelope(value):
    model = (
        CurrentSourceRestoreRecheck
        if isinstance(value, dict) and value.get("version") == 2
        else RestoreRecheck
    )
    return model.model_validate(value)


def require_trust(keys, signer_id, workspace_id):
    if not isinstance(keys, EvidenceTrust) or not keys.scoped:
        raise ValueError("scoped restore recheck signer required")
    authorize(keys, signer_id, "RESTORE_RECHECK", workspace_id)


def verify_signature(document, **context):
    if (
        not isinstance(document, dict)
        or set(document) != {"envelope", "signature"}
        or len(canonical(document)) > 16384
    ):
        raise ValueError("invalid restore recheck")
    data = parse_envelope(document["envelope"])
    require_trust(
        context["public_keys"], data.signer_key_id, str(context["workspace_id"])
    )
    try:
        Ed25519PublicKey.from_public_bytes(
            context["public_keys"][data.signer_key_id]
        ).verify(
            base64.b64decode(document["signature"], validate=True),
            canonical(document["envelope"]),
        )
    except InvalidSignature:
        raise ValueError("restore recheck signature mismatch") from None
    if (
        data.workspace_id != str(context["workspace_id"])
        or data.generation_id != str(context["generation_id"])
        or data.policy_digest != context["policy"].digest()
        or data.code_revision != context["code_revision"]
        or data.db_revision != context["db_revision"]
        or not -timedelta(seconds=30)
        <= context["now"] - timestamp(data.checked_at)
        <= timedelta(minutes=15)
    ):
        raise ValueError("restore recheck scope or freshness mismatch")
    if isinstance(data, CurrentSourceRestoreRecheck) and not -timedelta(
        seconds=30
    ) <= context["now"] - timestamp(data.source_observation.observed_at) <= timedelta(
        minutes=15
    ):
        raise ValueError("source observation freshness mismatch")
    return data


def verify(document, restore_document, **context):
    data = verify_signature(document, **context)
    restore = verify_evidence(
        restore_document["envelope"], restore_document["signature"], **context
    )
    diagnostic = restore.metrics.restore_diagnostics
    if (
        restore.kind != "RESTORE"
        or restore.result != "PARTIAL"
        or not isinstance(diagnostic, ObservedRestoreDiagnostics)
    ):
        raise ValueError("measured partial restore original required")
    original = diagnostic.execution_observation
    if (
        data.restore.run_id != restore.run_id
        or data.restore.source_digest
        != hashlib.sha256(canonical(restore_document)).hexdigest()
        or data.target_identity != original.target_identity
        or timestamp(data.checked_at)
        < timestamp(restore.finished_at) - timedelta(seconds=30)
        or data.run_id in {original.backup_run_id, original.checkpoint_run_id}
    ):
        raise ValueError("restore recheck original mismatch")
    if (
        isinstance(data, CurrentSourceRestoreRecheck)
        and data.source_observation.source_identity != original.source_identity
    ):
        raise ValueError("current source physical identity mismatch")
    if data.measurement is not None:
        for field in (
            "backup_run_id",
            "checkpoint_run_id",
            "backup_manifest_digest",
            "checkpoint_digest",
            "checkpoint_manifest_digest",
            "source_identity",
            "target_identity",
        ):
            if getattr(data.measurement, field) != getattr(original, field):
                raise ValueError("recheck source or target changed")
        if data.state_matches_execution != (
            data.measurement.state_digest == original.state_digest
        ):
            raise ValueError("recheck state digest mismatch")
    return data


def sign(
    restore_document,
    *,
    measurement,
    checked_at,
    signer,
    signer_id,
    source_observation=None,
    **context,
):
    restore = verify_evidence(
        restore_document["envelope"], restore_document["signature"], **context
    )
    if not isinstance(restore.metrics.restore_diagnostics, ObservedRestoreDiagnostics):
        raise TypeError("restore execution observation required")
    original = restore.metrics.restore_diagnostics.execution_observation
    require_trust(context["public_keys"], signer_id, str(context["workspace_id"]))
    payload = parse_envelope(
        {
            "version": 2 if source_observation is not None else 1,
            "kind": "RESTORE_RECHECK",
            "scope": "CURRENT_SOURCE_AND_RESTORED_CHECKPOINT_RESTRICTIONS"
            if source_observation is not None
            else "CURRENT_RESTORED_CHECKPOINT_RESTRICTIONS",
            "runId": str(uuid4()),
            "workspaceId": str(context["workspace_id"]),
            "generationId": str(context["generation_id"]),
            "policyDigest": context["policy"].digest(),
            "codeRevision": context["code_revision"],
            "dbRevision": context["db_revision"],
            "checkedAt": checked_at,
            "restore": {
                "runId": restore.run_id,
                "sourceDigest": hashlib.sha256(canonical(restore_document)).hexdigest(),
            },
            "targetIdentity": original.target_identity,
            "measurement": measurement,
            "targetMeasured": measurement is not None,
            "stateMatchesExecution": measurement["stateDigest"] == original.state_digest
            if measurement is not None
            else None,
            "reason": "MEASURED"
            if measurement is not None
            else "MEASUREMENT_UNAVAILABLE",
            "result": "BLOCKED"
            if source_observation is not None
            and source_observation["result"] == "BLOCKED"
            else measurement["result"]
            if measurement is not None
            else "BLOCKED",
            **(
                {"sourceObservation": source_observation}
                if source_observation is not None
                else {}
            ),
            "signerKeyId": signer_id,
            "ready": False,
            "revocationsComplete": False,
            "liveCompanyAcceptance": False,
            "releaseAuthorized": False,
        }
    ).model_dump(by_alias=True)
    document = {
        "envelope": payload,
        "signature": base64.b64encode(signer.sign(canonical(payload))).decode(),
    }
    verify(document, restore_document, **context)
    return document
