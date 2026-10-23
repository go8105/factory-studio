"""Scoped signed journal observations. No whole-route acceptance or release authority."""

import base64
import hashlib
from datetime import timedelta
from typing import Literal
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import Field, model_validator

from fs.core.backup import BackupError, database_identity
from fs.core.security.transaction_proof import classify, summary, timeline
from fs.gw.acceptance_preflight import read_transaction, snapshot, validate_request
from fs.gw.backup_journal import source_records
from fs.gw.evidence_trust import EvidenceTrust, authorize
from fs.gw.operating_contract import (
    EvidenceReference,
    StrictModel,
    canonical,
    timestamp,
)
from fs.gw.security_journal import confirmed_digests

DISPOSITIONS = frozenset(
    {
        "AUDIT_CONFIRMED",
        "ABORT_CONFIRMED",
        "PENDING",
        "SOURCE_MISMATCH",
        "COMMITTED_WITHOUT_AUDIT",
        "UNKNOWN",
    }
)


class JournalObservation(StrictModel):
    version: Literal[1]
    kind: Literal["JOURNAL_OBSERVATION"]
    scope: Literal["GW_COMPANY_JOURNAL_SCOPE_V1"]
    run_id: str = Field(alias="runId")
    workspace_id: str = Field(alias="workspaceId", pattern=r"^[1-9][0-9]{0,18}$")
    generation_id: str = Field(alias="generationId", pattern=r"^[1-9][0-9]{0,18}$")
    policy_digest: str = Field(alias="policyDigest", pattern=r"^[0-9a-f]{64}$")
    context_digest: str = Field(alias="contextDigest", pattern=r"^[0-9a-f]{64}$")
    code_revision: str = Field(alias="codeRevision", pattern=r"^[0-9a-f]{7,64}$")
    db_revision: str = Field(alias="dbRevision", pattern=r"^[A-Za-z0-9_]{1,100}$")
    source_identity: str = Field(alias="sourceIdentity", pattern=r"^[0-9a-f]{64}$")
    observed_at: str = Field(alias="observedAt")
    source_head: str = Field(alias="sourceHead", pattern=r"^[0-9a-f]{64}$")
    scope_records_digest: str = Field(
        alias="scopeRecordsDigest", pattern=r"^[0-9a-f]{64}$"
    )
    scope_records: int = Field(alias="scopeRecords", ge=0, le=100000)
    missing_transaction_proofs: int = Field(
        alias="missingTransactionProofs", ge=0, le=100000
    )
    dispositions: dict[str, int]
    result: Literal["PARTIAL", "BLOCKED"]
    signer_key_id: str = Field(alias="signerKeyId", pattern=r"^[A-Za-z0-9_-]{1,60}$")
    ready: Literal[False]
    completeness_confirmed: Literal[False] = Field(alias="completenessConfirmed")
    revocations_reapplied: Literal[False] = Field(alias="revocationsReapplied")
    live_company_acceptance: Literal[False] = Field(alias="liveCompanyAcceptance")
    release_authorized: Literal[False] = Field(alias="releaseAuthorized")
    execution_revision_verified: Literal[False] = Field(
        alias="executionRevisionVerified"
    )
    independent_storage_confirmed: Literal[False] = Field(
        alias="independentStorageConfirmed"
    )

    @model_validator(mode="before")
    @classmethod
    def literal_types(cls, value):
        if isinstance(value, dict):
            for name, field in cls.model_fields.items():
                key = field.alias if field.alias in value else name
                if (
                    key in value
                    and field.annotation == Literal[False]
                    and type(value[key]) is not bool
                ):
                    raise ValueError("invalid completion flag")
            if "version" in value and type(value["version"]) is not int:
                raise ValueError("invalid version")
        return value

    @model_validator(mode="after")
    def bounded_counts(self):
        EvidenceReference(runId=self.run_id, sourceDigest=self.source_head)
        timestamp(self.observed_at)
        counts = self.dispositions
        if (
            set(counts) != DISPOSITIONS
            or any(v < 0 or v > 100000 for v in counts.values())
            or sum(counts.values()) != self.scope_records
            or self.missing_transaction_proofs > self.scope_records
        ):
            raise ValueError("invalid observation counts")
        settled = counts["AUDIT_CONFIRMED"] + counts["ABORT_CONFIRMED"]
        expected = (
            "PARTIAL"
            if self.scope_records > 0
            and settled == self.scope_records
            and self.missing_transaction_proofs == 0
            else "BLOCKED"
        )
        if self.result != expected:
            raise ValueError("unsettled observations cannot be promoted")
        return self


def require_trust(keys, key_id, workspace_id):
    if not isinstance(keys, EvidenceTrust) or not keys.scoped:
        raise BackupError("회사·용도를 지정한 관측 서명 키 설정이 필요합니다.")
    authorize(keys, key_id, "JOURNAL_OBSERVATION", workspace_id)


def measure(engine, *, company_id, code_revision):
    validate_request(
        company_id=company_id, code_revision=code_revision, admin_login="admin"
    )
    before = source_records()
    if before is None:
        raise BackupError("기록과 별도 최신 지문 설정이 필요합니다.")
    state, records = before
    with read_transaction(engine) as c:
        current, preflight = snapshot(
            c, company_id=company_id, code_revision=code_revision, admin_login="admin"
        )
        identity, current_timeline = database_identity(c), timeline(c)
        selected = [
            r
            for r in records
            if r["payload"].get("coverage") == "gw.company.intent.v2"
            and r["payload"].get("workspaceId") == company_id
            and str(r["payload"].get("generationId")) == str(current["generationId"])
        ]
        dispositions = classify(c, selected, confirmed_digests(c, selected))
        missing = 0
        for record in selected:
            proof = record["payload"].get("transactionProof")
            if proof is None:
                missing += 1
            elif (
                proof["sourceIdentity"] != identity
                or proof["timeline"] != current_timeline
            ):
                dispositions[record["digest"]] = "SOURCE_MISMATCH"
        counts = summary(dispositions)["transactionDispositionCounts"]
        settled = counts["AUDIT_CONFIRMED"] + counts["ABORT_CONFIRMED"]
        measured = {
            "workspaceId": str(company_id),
            "generationId": str(current["generationId"]),
            "policyDigest": preflight["policyDigest"],
            "contextDigest": hashlib.sha256(canonical(current)).hexdigest(),
            "codeRevision": current["codeRevision"],
            "dbRevision": current["dbRevision"],
            "sourceIdentity": identity,
            "observedAt": preflight["observedAt"],
            "sourceHead": state["head"],
            "scopeRecordsDigest": hashlib.sha256(
                canonical([r["digest"] for r in selected])
            ).hexdigest(),
            "scopeRecords": len(selected),
            "missingTransactionProofs": missing,
            "dispositions": counts,
            "result": "PARTIAL"
            if selected and settled == len(selected) and not missing
            else "BLOCKED",
        }
        after = source_records()
        if after is None or after[0] != state:
            raise BackupError("관측 도중 최신 변경 기록 지문이 달라졌습니다.")
        return measured


def observe(engine, *, company_id, code_revision, public_keys, signer, signer_id):
    require_trust(public_keys, signer_id, str(company_id))
    measured = measure(engine, company_id=company_id, code_revision=code_revision)
    payload = JournalObservation.model_validate(
        {
            "version": 1,
            "kind": "JOURNAL_OBSERVATION",
            "scope": "GW_COMPANY_JOURNAL_SCOPE_V1",
            "runId": str(uuid4()),
            **measured,
            "signerKeyId": signer_id,
            **{
                name: False
                for name in (
                    "ready",
                    "completenessConfirmed",
                    "revocationsReapplied",
                    "liveCompanyAcceptance",
                    "releaseAuthorized",
                    "executionRevisionVerified",
                    "independentStorageConfirmed",
                )
            },
        }
    ).model_dump(by_alias=True)
    document = {
        "envelope": payload,
        "signature": base64.b64encode(signer.sign(canonical(payload))).decode(),
    }
    verify(
        document,
        public_keys=public_keys,
        company_id=company_id,
        code_revision=code_revision,
        now=timestamp(measured["observedAt"]),
    )
    return document


def verify(document, *, public_keys, company_id, code_revision, now):
    """Signature/scope/age only; consumers must use verify_current for live state."""
    if (
        not isinstance(document, dict)
        or set(document) != {"envelope", "signature"}
        or len(canonical(document)) > 16384
    ):
        raise ValueError("invalid observation document")
    data = JournalObservation.model_validate(document["envelope"])
    require_trust(public_keys, data.signer_key_id, str(company_id))
    Ed25519PublicKey.from_public_bytes(public_keys[data.signer_key_id]).verify(
        base64.b64decode(document["signature"], validate=True),
        canonical(document["envelope"]),
    )
    age = now - timestamp(data.observed_at)
    if (
        data.workspace_id != str(company_id)
        or data.code_revision != code_revision
        or not timedelta(0) <= age <= timedelta(minutes=15)
    ):
        raise ValueError("stale observation or scope mismatch")
    return data


def verify_current(engine, document, *, company_id, code_revision, public_keys):
    """Reobserve current sources; this never authorizes a release or permission grant."""
    current = measure(engine, company_id=company_id, code_revision=code_revision)
    data = verify(
        document,
        public_keys=public_keys,
        company_id=company_id,
        code_revision=code_revision,
        now=timestamp(current["observedAt"]),
    )
    saved = data.model_dump(by_alias=True)
    if any(
        saved[key] != value for key, value in current.items() if key != "observedAt"
    ):
        raise ValueError("observation no longer matches current journal and database")
    return data
