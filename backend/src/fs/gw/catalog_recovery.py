"""Signed interruption attestations preserve unknown bytes; they never certify success."""

import base64
import hashlib
from typing import Literal

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import Field, model_validator

from fs.gw import catalog_store as store
from fs.gw.checkpoint_catalog import RecoveryCatalog, Versioned, uuid4
from fs.gw.operating_contract import StrictModel, canonical, timestamp

DOMAIN = b"FS-GW-CHECKPOINT-CATALOG-RECOVERY-v1\0"
MAX_SLOTS = 256


class Slot(StrictModel):
    revision: int = Field(ge=1, le=9223372036854775807)
    expected_digest: str | None = Field(
        alias="expectedDigest", pattern=r"^[0-9a-f]{64}$"
    )
    actual_digest: str | None = Field(alias="actualDigest", pattern=r"^[0-9a-f]{64}$")
    size: int | None = Field(ge=0, le=store.MAX_BYTES)

    @model_validator(mode="after")
    def complete_metadata(self):
        if (
            len(
                {
                    self.expected_digest is None,
                    self.actual_digest is None,
                    self.size is None,
                }
            )
            != 1
        ):
            raise ValueError("interruption slot metadata incomplete")
        return self


class Recovery(Versioned):
    kind: Literal["CHECKPOINT_CATALOG_RECOVERY"]
    catalog_id: str = Field(alias="catalogId")
    workspace_id: str = Field(alias="workspaceId", pattern=r"^[1-9][0-9]{0,18}$")
    generation_id: str = Field(alias="generationId", pattern=r"^[1-9][0-9]{0,18}$")
    base_revision: int = Field(alias="baseRevision", ge=0, le=9223372036854775807)
    base_digest: str = Field(alias="baseDigest", pattern=r"^(ABSENT|[0-9a-f]{64})$")
    base_sequence: int = Field(alias="baseSequence", ge=0, le=9223372036854775807)
    target_revision: int = Field(alias="targetRevision", ge=1, le=9223372036854775807)
    target_sequence: int = Field(alias="targetSequence", ge=1, le=9223372036854775807)
    record_digest: str = Field(alias="recordDigest", pattern=r"^[0-9a-f]{64}$")
    recovered_at: str = Field(alias="recoveredAt")
    disposition: Literal["PARTIAL_HEAD_UNKNOWN"]
    intent: store.Intent
    slots: list[Slot] = Field(max_length=MAX_SLOTS)
    signer_key_id: str = Field(alias="signerKeyId", pattern=r"^[A-Za-z0-9_-]{1,60}$")

    @model_validator(mode="after")
    def bounded_gap(self):
        uuid4(self.catalog_id)
        timestamp(self.recovered_at)
        if (
            (self.base_revision == 0) != (self.base_digest == "ABSENT")
            or (self.base_revision == 0) != (self.base_sequence == 0)
            or self.target_revision
            != max(
                self.base_revision,
                self.intent.revision,
                max((s.revision for s in self.slots), default=0),
            )
            + 1
            or self.target_sequence != max(self.base_sequence, self.intent.sequence) + 1
            or self.target_revision - self.base_revision - 1 != len(self.slots)
            or [s.revision for s in self.slots]
            != list(range(self.base_revision + 1, self.target_revision))
            or self.intent.catalog_id != self.catalog_id
            or self.intent.workspace_id != self.workspace_id
            or self.intent.generation_id != self.generation_id
            or self.intent.revision > self.base_revision + 1
            or self.intent.sequence > self.base_sequence + 1
            or (
                self.intent.revision == self.base_revision + 1
                and self.intent.sequence != self.base_sequence + 1
            )
            or (
                (self.intent.revision == 1)
                != (self.intent.expected_pin_digest == "ABSENT")
            )
        ):
            raise ValueError("recovery reservation/interval mismatch")
        return self


class Proof(StrictModel):
    envelope: Recovery
    signature: str = Field(max_length=100)


def record_digest(record):
    return hashlib.sha256(canonical(record.model_dump(by_alias=True))).hexdigest()


def verify(catalog, *, public_keys, workspace_id):
    proof = Proof.model_validate(catalog.recovery_proof)
    data = proof.envelope
    from fs.gw.catalog_key_handover import key

    public = key(
        public_keys,
        data.signer_key_id,
        str(workspace_id),
        kind="RECOVERY",
        digest=store.digest(canonical(proof.model_dump(by_alias=True))),
        catalog_id=data.catalog_id,
        generation_id=data.generation_id,
        claimed_at=data.recovered_at,
    )
    Ed25519PublicKey.from_public_bytes(public).verify(
        base64.b64decode(proof.signature, validate=True),
        DOMAIN + canonical(data.model_dump(by_alias=True)),
    )
    if len(catalog.records) != 1:
        raise ValueError("recovery requires one unknown record")
    record = catalog.records[0]
    if (
        data.workspace_id != str(workspace_id)
        or data.catalog_id != catalog.catalog_id
        or data.workspace_id != record.workspace_id
        or data.generation_id != record.generation_id
        or record.result != "PARTIAL"
        or record.head is not None
        or data.record_digest != record_digest(record)
        or data.target_sequence != record.sequence
        or catalog.revision < data.target_revision
        or record.recorded_at != data.recovered_at
        or timestamp(catalog.published_at) < timestamp(data.recovered_at)
        or (
            catalog.revision == data.target_revision
            and catalog.published_at != data.recovered_at
        )
    ):
        raise ValueError("recovery catalog/proof mismatch")
    return data


def make(catalog, old, old_digest, intent, root, *, signer, signer_id):
    if catalog.revision - (old.revision if old else 0) - 1 > MAX_SLOTS:
        raise ValueError("recovery interval exceeds bounded proof")
    names, _ = store.inventory(root)
    indexed = {
        int(m[1]): (name, m[2]) for name in names if (m := store.NAME.fullmatch(name))
    }
    slots = []
    for revision in range((old.revision if old else 0) + 1, catalog.revision):
        if revision in indexed:
            name, expected = indexed[revision]
            raw = store.read_fd(root, name, allow_empty=True)
            slots.append(
                Slot(
                    revision=revision,
                    expectedDigest=expected,
                    actualDigest=store.digest(raw),
                    size=len(raw),
                )
            )
        else:
            slots.append(
                Slot(
                    revision=revision, expectedDigest=None, actualDigest=None, size=None
                )
            )
    record = catalog.records[0]
    envelope = Recovery(
        version=1,
        kind="CHECKPOINT_CATALOG_RECOVERY",
        catalogId=catalog.catalog_id,
        workspaceId=record.workspace_id,
        generationId=record.generation_id,
        baseRevision=old.revision if old else 0,
        baseDigest=old_digest,
        baseSequence=old.records[0].sequence if old else 0,
        targetRevision=catalog.revision,
        targetSequence=record.sequence,
        recordDigest=record_digest(record),
        recoveredAt=record.recorded_at,
        disposition="PARTIAL_HEAD_UNKNOWN",
        intent=intent,
        slots=slots,
        signerKeyId=signer_id,
    )
    proof = Proof(
        envelope=envelope,
        signature=base64.b64encode(
            signer.sign(DOMAIN + canonical(envelope.model_dump(by_alias=True)))
        ).decode(),
    )
    return RecoveryCatalog.model_validate(
        catalog.model_dump(by_alias=True)
        | {"version": 2, "recoveryProof": proof.model_dump(by_alias=True)}
    )


def bridge(before, after, before_digest):
    """Compare to the actual receiver predecessor, not a caller-invented base."""
    data = Proof.model_validate(after.recovery_proof).envelope
    if (
        after.revision != data.target_revision
        or data.base_revision != (before.revision if before else 0)
        or data.base_sequence != (before.records[0].sequence if before else 0)
        or data.base_digest != before_digest
        or (before and timestamp(after.published_at) < timestamp(before.published_at))
    ):
        raise ValueError("recovery does not extend the receiver predecessor")
    return data
