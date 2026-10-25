"""Exact catalog history approvals for planned retirement; revocation always denies."""

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Literal
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import Field, model_validator

from fs.gw import catalog_store as store
from fs.gw.checkpoint_catalog import Versioned, _object
from fs.gw.checkpoint_catalog import uuid4 as check_id
from fs.gw.evidence_trust import EvidenceTrust, authorize
from fs.gw.operating_contract import StrictModel, canonical, timestamp

ENV = "FS_GW_CATALOG_KEY_LIFECYCLE"
DOMAIN = b"FS-GW-CATALOG-KEY-HANDOVER-v1\0"
MAX_BYTES = 2 * 1024 * 1024


class Snapshot(Versioned):
    revision: int = Field(ge=1, le=9223372036854775807)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class Handover(Versioned):
    kind: Literal["CHECKPOINT_CATALOG_KEY_HANDOVER"]
    handover_id: str = Field(alias="handoverId")
    catalog_id: str = Field(alias="catalogId")
    workspace_id: str = Field(alias="workspaceId", pattern=r"^[1-9][0-9]{0,18}$")
    generation_id: str = Field(alias="generationId", pattern=r"^[1-9][0-9]{0,18}$")
    disposition: Literal["NORMAL_RETIREMENT"]
    issued_at: str = Field(alias="issuedAt")
    retiring_key_id: str = Field(
        alias="retiringKeyId", pattern=r"^[A-Za-z0-9_-]{1,60}$"
    )
    retiring_public_digest: str = Field(
        alias="retiringPublicDigest", pattern=r"^[0-9a-f]{64}$"
    )
    successor_key_id: str = Field(
        alias="successorKeyId", pattern=r"^[A-Za-z0-9_-]{1,60}$"
    )
    successor_public_digest: str = Field(
        alias="successorPublicDigest", pattern=r"^[0-9a-f]{64}$"
    )
    captured_revision: int = Field(
        alias="capturedRevision", ge=1, le=9223372036854775807
    )
    captured_digest: str = Field(alias="capturedDigest", pattern=r"^[0-9a-f]{64}$")
    captured_sequence: int = Field(
        alias="capturedSequence", ge=1, le=9223372036854775807
    )
    captured_record_digest: str = Field(
        alias="capturedRecordDigest", pattern=r"^[0-9a-f]{64}$"
    )
    snapshots: list[Snapshot] = Field(min_length=1, max_length=8192)
    recovery_proofs: list[str] = Field(alias="recoveryProofs", max_length=8192)

    @model_validator(mode="after")
    def coherent(self):
        check_id(self.handover_id)
        check_id(self.catalog_id)
        timestamp(self.issued_at)
        numbers = [s.revision for s in self.snapshots]
        if (
            numbers != sorted(set(numbers))
            or self.snapshots[-1].revision != self.captured_revision
            or self.snapshots[-1].digest != self.captured_digest
            or self.retiring_key_id == self.successor_key_id
            or self.retiring_public_digest == self.successor_public_digest
            or len(set(self.recovery_proofs)) != len(self.recovery_proofs)
            or any(
                len(s) != 64 or any(c not in "0123456789abcdef" for c in s)
                for s in self.recovery_proofs
            )
        ):
            raise ValueError("handover scope/history inconsistent")
        return self


class Document(StrictModel):
    envelope: Handover
    retiring_signature: str = Field(alias="retiringSignature", max_length=100)
    successor_signature: str = Field(alias="successorSignature", max_length=100)


class Approval(Versioned):
    file: str = Field(min_length=1, max_length=4096)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def absolute(self):
        if not Path(self.file).is_absolute():
            raise ValueError("absolute handover path required")
        return self


class KeyState(Versioned):
    workspace_id: str = Field(alias="workspaceId", pattern=r"^[1-9][0-9]{0,18}$")
    key_id: str = Field(alias="keyId", pattern=r"^[A-Za-z0-9_-]{1,60}$")
    public_key: str = Field(alias="publicKey", max_length=100)
    state: Literal["RETIRED", "REVOKED"]
    approvals: list[Approval] = Field(max_length=20)

    @model_validator(mode="after")
    def bounded(self):
        if len(base64.b64decode(self.public_key, validate=True)) != 32 or (
            self.state == "RETIRED"
        ) != bool(self.approvals):
            raise ValueError(
                "normal retirement requires approvals; revocation cannot carry grants"
            )
        return self


class Configuration(Versioned):
    keys: list[KeyState] = Field(min_length=1, max_length=100)


@dataclass(frozen=True)
class Grant:
    state: str
    public_key: bytes
    # Exact (kind, catalog ID, generation, digest) -> cutoff and capture metadata.
    documents: object
    approval_digests: frozenset = frozenset()
    approval_paths: tuple = ()


class Lifecycle:
    def __init__(self, records):
        self.records = MappingProxyType(records)

    def deny_current(self, key_id, workspace_id):
        if (workspace_id, key_id) in self.records:
            raise ValueError(
                "retired/revoked catalog key cannot sign current documents"
            )


def key(
    public_keys,
    key_id,
    workspace_id,
    *,
    kind="SNAPSHOT",
    digest=None,
    catalog_id=None,
    generation_id=None,
    claimed_at=None,
    catalog=None,
):
    """Only these two catalog verifiers can request an exact historical grant."""
    if not isinstance(public_keys, EvidenceTrust) or not public_keys.scoped:
        raise ValueError("scoped catalog authority required")
    lifecycle = public_keys.catalog_lifecycle
    record = lifecycle.records.get((str(workspace_id), key_id)) if lifecycle else None
    if record is not None:
        captured = record.documents.get((kind, catalog_id, generation_id, digest))
        if (
            record.state != "RETIRED"
            or digest is None
            or captured is None
            or claimed_at is None
            or timestamp(claimed_at) > captured[0]
        ):
            raise ValueError("catalog history key denied")
        if kind == "SNAPSHOT" and (
            catalog is None
            or catalog.revision != captured[1]
            or (
                captured[2] is not None
                and (
                    len(catalog.records) != 1
                    or catalog.records[0].sequence != captured[2]
                    or store.digest(
                        canonical(catalog.records[0].model_dump(by_alias=True))
                    )
                    != captured[3]
                )
            )
        ):
            raise ValueError("handover capture metadata differs from original")
        return record.public_key
    authorize(public_keys, key_id, "CHECKPOINT_CATALOG", str(workspace_id))
    return public_keys[key_id]


def verify(
    raw,
    *,
    public_keys,
    retiring_key_id,
    retiring_public,
    workspace_id,
    blocked=frozenset(),
):
    if not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("handover size limit")
    document = Document.model_validate(json.loads(raw, object_pairs_hook=_object))
    data = document.envelope
    if (
        data.workspace_id != str(workspace_id)
        or data.retiring_key_id != retiring_key_id
        or data.retiring_public_digest != store.digest(retiring_public)
        or (data.workspace_id, data.successor_key_id) in blocked
        or timestamp(data.issued_at) > datetime.now(UTC) + timedelta(seconds=30)
    ):
        raise ValueError("handover trust/context mismatch")
    authorize(
        public_keys, data.successor_key_id, "CHECKPOINT_CATALOG", data.workspace_id
    )
    successor = public_keys[data.successor_key_id]
    if (
        store.digest(successor) != data.successor_public_digest
        or successor == retiring_public
    ):
        raise ValueError("successor identity mismatch")
    verify_pair(document, retiring_public, successor, DOMAIN)
    return data


def verify_pair(document, retiring_public, successor_public, domain):
    message = domain + canonical(document.envelope.model_dump(by_alias=True))
    for public, signature, role in (
        (retiring_public, document.retiring_signature, b"RETIRING\0"),
        (successor_public, document.successor_signature, b"SUCCESSOR\0"),
    ):
        Ed25519PublicKey.from_public_bytes(public).verify(
            base64.b64decode(signature, validate=True), role + message
        )


def bind(public_keys, value):
    """Deployment-owned lifecycle; no keys/grants are imported from uploaded proof files."""
    if (
        not public_keys.scoped
        or not isinstance(value, str)
        or len(value.encode()) > 65536
    ):
        raise ValueError("invalid catalog lifecycle configuration")
    config = Configuration.model_validate(json.loads(value, object_pairs_hook=_object))
    records, identities, fingerprints = {}, set(), set()
    named_public, public_names = {}, {}
    if sum(len(k.approvals) for k in config.keys) > 20:
        raise ValueError("handover approval count limit")
    for item in config.keys:
        identity = item.workspace_id, item.key_id
        raw = base64.b64decode(item.public_key, validate=True)
        fingerprint = item.workspace_id, raw
        if (item.key_id in named_public and named_public[item.key_id] != raw) or (
            raw in public_names and public_names[raw] != item.key_id
        ):
            raise ValueError("lifecycle key reused or aliased across companies")
        named_public[item.key_id], public_names[raw] = raw, item.key_id
        if identity in identities or fingerprint in fingerprints:
            raise ValueError("duplicate or aliased lifecycle key")
        identities.add(identity)
        fingerprints.add(fingerprint)
        for name, public in public_keys.items():
            if (name == item.key_id and public != raw) or (
                name != item.key_id and public == raw
            ):
                raise ValueError("lifecycle key identity reused/aliased")
    from fs.gw.catalog_key_chain import cross_check
    from fs.gw.catalog_key_chain import verify as verify_chain

    registry = {
        (item.workspace_id, item.key_id): Grant(
            item.state, base64.b64decode(item.public_key, validate=True), {}
        )
        for item in config.keys
    }
    chains = []
    for item in config.keys:
        raw_public = base64.b64decode(item.public_key, validate=True)
        documents = {}
        approval_paths = []
        for approval in item.approvals:
            path = Path(approval.file)
            with store.directory(path.parent) as root:
                raw = store.read_fd(root, path.name, MAX_BYTES)
            if store.digest(raw) != approval.digest:
                raise ValueError("handover differs from configured pin")
            chain = verify_chain(
                raw,
                public_keys=public_keys,
                retiring_key_id=item.key_id,
                retiring_public=raw_public,
                workspace_id=item.workspace_id,
                registry=registry,
            )
            from fs.gw.catalog_trust_store import _lineage

            approval_paths.append(tuple(_lineage(raw)))
            chains.append(chain)
            data = chain.root
            captured = timestamp(data.issued_at)
            for snapshot in data.snapshots:
                identity = (
                    "SNAPSHOT",
                    data.catalog_id,
                    data.generation_id,
                    snapshot.digest,
                )
                if identity in documents:
                    raise ValueError("overlapping historical approvals")
                documents[identity] = (
                    captured,
                    snapshot.revision,
                    data.captured_sequence
                    if snapshot.revision == data.captured_revision
                    else None,
                    data.captured_record_digest
                    if snapshot.revision == data.captured_revision
                    else None,
                )
            for sha in data.recovery_proofs:
                identity = "RECOVERY", data.catalog_id, data.generation_id, sha
                if identity in documents:
                    raise ValueError("overlapping recovery approvals")
                documents[identity] = (captured, None, None, None)
        records[item.workspace_id, item.key_id] = Grant(
            item.state,
            raw_public,
            MappingProxyType(documents),
            frozenset(a.digest for a in item.approvals),
            tuple(sorted(approval_paths)),
        )
    cross_check(chains)
    return EvidenceTrust(
        public_keys, public_keys.scopes, catalog_lifecycle=Lifecycle(records)
    )


def issue(
    path,
    *,
    context,
    public_keys,
    retiring_signer,
    retiring_id,
    successor_signer,
    successor_id,
    now,
    expected_pin_digest,
):
    """Before retirement, both active authorities attest the exact retained source history."""
    from fs.gw.catalog_segments import walk

    for signer, identity in (
        (retiring_signer, retiring_id),
        (successor_signer, successor_id),
    ):
        authorize(
            public_keys, identity, "CHECKPOINT_CATALOG", str(context.workspace_id)
        )
        Ed25519PublicKey.from_public_bytes(public_keys[identity]).verify(
            signer.sign(b"catalog-handover-key-check"), b"catalog-handover-key-check"
        )
    with store.directory(path) as root, store.locked(root):
        current, pin, _ = store.current(
            root, path, public_keys=public_keys, workspace_id=context.workspace_id
        )
        store.cas(root, expected_pin_digest)
        store.check_scope(current, context)
        if (
            current is None
            or current.signer_key_id != retiring_id
            or not timedelta(0)
            <= now - timestamp(current.published_at)
            <= timedelta(minutes=15)
        ):
            raise ValueError("current retiring authority and fresh source required")
        config = store.CatalogConfig.model_validate(
            json.loads(store.read_fd(root, store.PIN), object_pairs_hook=_object)
        )
        snapshots, proofs = [], set()
        for item, raw in walk(
            root,
            identity=current.catalog_id,
            context=context,
            public_keys=public_keys,
            target_revision=current.revision,
            target_digest=config.digest,
            base_revision=0,
            base_digest="ABSENT",
        ):
            if item.kind != "SNAPSHOT":
                continue
            original = json.loads(raw, object_pairs_hook=_object)["envelope"]
            if original["signerKeyId"] == retiring_id:
                snapshots.append(
                    Snapshot(version=1, revision=item.revision, digest=item.digest)
                )
            if (
                original["version"] == 2
                and original["recoveryProof"]["envelope"]["signerKeyId"] == retiring_id
            ):
                proofs.add(store.digest(canonical(original["recoveryProof"])))
        envelope = Handover(
            version=1,
            kind="CHECKPOINT_CATALOG_KEY_HANDOVER",
            handoverId=str(uuid4()),
            catalogId=current.catalog_id,
            workspaceId=str(context.workspace_id),
            generationId=str(context.generation_id),
            disposition="NORMAL_RETIREMENT",
            issuedAt=now.isoformat(),
            retiringKeyId=retiring_id,
            retiringPublicDigest=store.digest(public_keys[retiring_id]),
            successorKeyId=successor_id,
            successorPublicDigest=store.digest(public_keys[successor_id]),
            capturedRevision=current.revision,
            capturedDigest=config.digest,
            capturedSequence=current.records[0].sequence,
            capturedRecordDigest=store.digest(
                canonical(current.records[0].model_dump(by_alias=True))
            ),
            snapshots=sorted(snapshots, key=lambda s: s.revision),
            recoveryProofs=sorted(proofs),
        )
        message = DOMAIN + canonical(envelope.model_dump(by_alias=True))
        document = Document(
            envelope=envelope,
            retiringSignature=base64.b64encode(
                retiring_signer.sign(b"RETIRING\0" + message)
            ).decode(),
            successorSignature=base64.b64encode(
                successor_signer.sign(b"SUCCESSOR\0" + message)
            ).decode(),
        )
        raw = canonical(document.model_dump(by_alias=True)) + b"\n"
        verify(
            raw,
            public_keys=public_keys,
            retiring_key_id=retiring_id,
            retiring_public=public_keys[retiring_id],
            workspace_id=context.workspace_id,
        )
        store.cas(root, pin)
        return raw, {
            "handoverId": envelope.handover_id,
            "handoverDigest": store.digest(raw),
            "catalogId": current.catalog_id,
            "capturedRevision": current.revision,
            "snapshots": len(snapshots),
            "recoveryProofs": len(proofs),
            "ready": False,
        }
