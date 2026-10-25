"""Bounded, explicitly pinned continuation of exact catalog retirement approvals."""

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from pydantic import Field, model_validator

from fs.gw import catalog_key_handover as handover
from fs.gw import catalog_store as store
from fs.gw.checkpoint_catalog import Versioned, _object
from fs.gw.evidence_trust import authorize
from fs.gw.operating_contract import StrictModel, canonical, timestamp

DOMAIN = b"FS-GW-CATALOG-KEY-CONTINUATION-v1\0"
MAX_EDGES = 8
MAX_EXPANDED = 8 * 1024 * 1024


class Continuation(Versioned):
    kind: Literal["CHECKPOINT_CATALOG_KEY_CONTINUATION"]
    continuation_id: str = Field(alias="continuationId")
    root_handover_id: str = Field(alias="rootHandoverId")
    catalog_id: str = Field(alias="catalogId")
    workspace_id: str = Field(alias="workspaceId", pattern=r"^[1-9][0-9]{0,18}$")
    generation_id: str = Field(alias="generationId", pattern=r"^[1-9][0-9]{0,18}$")
    disposition: Literal["NORMAL_RETIREMENT_CONTINUATION"]
    parent_digest: str = Field(alias="parentDigest", pattern=r"^[0-9a-f]{64}$")
    parent: str = Field(min_length=1, max_length=3 * 1024 * 1024)
    retiring_handover_digest: str = Field(
        alias="retiringHandoverDigest", pattern=r"^[0-9a-f]{64}$"
    )
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
    issued_at: str = Field(alias="issuedAt")
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

    @model_validator(mode="after")
    def coherent(self):
        for identity in (self.continuation_id, self.root_handover_id, self.catalog_id):
            handover.check_id(identity)
        timestamp(self.issued_at)
        if (
            self.retiring_key_id == self.successor_key_id
            or self.retiring_public_digest == self.successor_public_digest
        ):
            raise ValueError("continuation authority cycle")
        return self


class Document(StrictModel):
    envelope: Continuation
    retiring_signature: str = Field(alias="retiringSignature", max_length=100)
    successor_signature: str = Field(alias="successorSignature", max_length=100)


@dataclass(frozen=True)
class Verified:
    root: handover.Handover
    root_digest: str
    steps: tuple
    endpoint: str


def scope(data):
    return data.workspace_id, data.generation_id, data.catalog_id


def capture(data):
    return (
        data.captured_revision,
        data.captured_digest,
        data.captured_sequence,
        data.captured_record_digest,
    )


def verify(
    raw, *, public_keys, retiring_key_id, retiring_public, workspace_id, registry
):
    """Only deployment-configured retired public keys and one active endpoint are trusted."""
    steps, total, seen_bytes = [], 0, set()
    while True:
        if not 0 < len(raw) <= handover.MAX_BYTES or len(steps) >= MAX_EDGES:
            raise ValueError("continuation bytes/depth limit")
        sha = store.digest(raw)
        total += len(raw)
        if sha in seen_bytes or total > MAX_EXPANDED:
            raise ValueError("continuation replay/expanded size limit")
        seen_bytes.add(sha)
        value = json.loads(raw, object_pairs_hook=_object)
        if (
            isinstance(value, dict)
            and isinstance(value.get("envelope"), dict)
            and value["envelope"].get("kind") == "CHECKPOINT_CATALOG_KEY_CONTINUATION"
        ):
            document = Document.model_validate(value)
            steps.append(document)
            raw = base64.b64decode(document.envelope.parent, validate=True)
            if store.digest(raw) != document.envelope.parent_digest:
                raise ValueError("continuation parent differs")
        else:
            original = handover.Document.model_validate(value)
            root_digest = sha
            break
    root = original.envelope
    if (
        root.workspace_id != str(workspace_id)
        or root.retiring_key_id != retiring_key_id
        or root.retiring_public_digest != store.digest(retiring_public)
    ):
        raise ValueError("continuation root scope mismatch")
    steps.reverse()
    identifiers = [root.handover_id] + [d.envelope.continuation_id for d in steps]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("repeated continuation identity")
    envelopes = [root] + [d.envelope for d in steps]
    authorities = [(root.retiring_key_id, root.retiring_public_digest)]
    previous = None
    for data in envelopes:
        if previous is not None and (
            scope(data) != scope(root)
            or data.root_handover_id != root.handover_id
            or data.retiring_key_id != previous.successor_key_id
            or data.retiring_public_digest != previous.successor_public_digest
            or data.captured_revision <= previous.captured_revision
            or data.captured_digest == previous.captured_digest
            or data.captured_sequence < previous.captured_sequence
            or (
                data.captured_sequence == previous.captured_sequence
                and data.captured_record_digest != previous.captured_record_digest
            )
            or timestamp(data.issued_at) < timestamp(previous.issued_at)
        ):
            raise ValueError("continuation edge/capture regression")
        if timestamp(data.issued_at) > datetime.now(UTC) + timedelta(seconds=30):
            raise ValueError("future continuation")
        authorities.append((data.successor_key_id, data.successor_public_digest))
        previous = data
    if len({i for i, _ in authorities}) != len(authorities) or len(
        {s for _, s in authorities}
    ) != len(authorities):
        raise ValueError("cyclic/aliased continuation")
    publics = []
    for index, (identity, sha) in enumerate(authorities):
        entry = registry.get((root.workspace_id, identity))
        if index < len(authorities) - 1:
            if entry is None or entry.state != "RETIRED":
                raise ValueError("missing/ revoked intermediate authority")
            public = entry.public_key
        else:
            if entry is not None:
                raise ValueError("continuation endpoint is not active")
            authorize(public_keys, identity, "CHECKPOINT_CATALOG", root.workspace_id)
            public = public_keys[identity]
        if store.digest(public) != sha:
            raise ValueError("continuation public key differs")
        publics.append(public)
    for index, document in enumerate([original] + steps):
        handover.verify_pair(
            document,
            publics[index],
            publics[index + 1],
            handover.DOMAIN if index == 0 else DOMAIN,
        )
    return Verified(
        root, root_digest, tuple(d.envelope for d in steps), authorities[-1][0]
    )


def cross_check(chains):
    """Every retired intermediary must have its own exact, independently verified handover."""
    roots, root_ids = {}, set()
    for chain in chains:
        root = chain.root
        identity = (*scope(root), root.retiring_key_id)
        if identity in roots or root.handover_id in root_ids:
            raise ValueError("multiple handover roots for one authority/scope")
        roots[identity] = chain
        root_ids.add(root.handover_id)
    for chain in chains:
        for step in chain.steps:
            source = roots.get((*scope(step), step.retiring_key_id))
            if (
                source is None
                or source.root_digest != step.retiring_handover_digest
                or capture(source.root) != capture(step)
                or source.root.successor_key_id != step.successor_key_id
                or source.root.successor_public_digest != step.successor_public_digest
                or timestamp(source.root.issued_at) > timestamp(step.issued_at)
            ):
                raise ValueError("continuation intermediary handover/capture differs")


def extend(
    path,
    parent_raw,
    retiring_handover_raw,
    *,
    context,
    public_keys,
    retiring_signer,
    retiring_id,
    successor_signer,
    successor_id,
    predecessor_id,
    expected_parent_digest,
    expected_retiring_handover_digest,
    expected_pin_digest,
    now,
):
    """Requires only the current retiring/successor private keys, never the root private key."""
    from fs.gw.catalog_segments import walk

    lifecycle = public_keys.catalog_lifecycle
    if lifecycle is None:
        raise ValueError("current pinned predecessor approval required")
    predecessor = lifecycle.records[str(context.workspace_id), predecessor_id]
    if (
        predecessor.state != "RETIRED"
        or expected_parent_digest not in predecessor.approval_digests
        or store.digest(parent_raw) != expected_parent_digest
        or store.digest(retiring_handover_raw) != expected_retiring_handover_digest
    ):
        raise ValueError("parent is not the currently pinned approval")
    parent = verify(
        parent_raw,
        public_keys=public_keys,
        retiring_key_id=predecessor_id,
        retiring_public=predecessor.public_key,
        workspace_id=context.workspace_id,
        registry=lifecycle.records,
    )
    if len(parent.steps) + 2 > MAX_EDGES or parent.endpoint != retiring_id:
        raise ValueError("wrong current endpoint/depth")
    for signer, identity in (
        (retiring_signer, retiring_id),
        (successor_signer, successor_id),
    ):
        authorize(
            public_keys, identity, "CHECKPOINT_CATALOG", str(context.workspace_id)
        )
        handover.Ed25519PublicKey.from_public_bytes(public_keys[identity]).verify(
            signer.sign(b"catalog-continuation-key-check"),
            b"catalog-continuation-key-check",
        )
    own = handover.verify(
        retiring_handover_raw,
        public_keys=public_keys,
        retiring_key_id=retiring_id,
        retiring_public=public_keys[retiring_id],
        workspace_id=context.workspace_id,
    )
    with store.directory(path) as root, store.locked(root):
        current, pin, _ = store.current(
            root, path, public_keys=public_keys, workspace_id=context.workspace_id
        )
        store.cas(root, expected_pin_digest)
        store.check_scope(current, context)
        if current is None:
            raise ValueError("current source required")
        config = store.CatalogConfig.model_validate(
            json.loads(store.read_fd(root, store.PIN), object_pairs_hook=_object)
        )
        actual = (
            current.revision,
            config.digest,
            current.records[0].sequence,
            store.digest(canonical(current.records[0].model_dump(by_alias=True))),
        )
        if (
            current.signer_key_id != retiring_id
            or capture(own) != actual
            or own.successor_key_id != successor_id
            or scope(own) != scope(parent.root)
            or own.catalog_id != current.catalog_id
            or own.workspace_id != str(context.workspace_id)
            or own.generation_id != str(context.generation_id)
            or not timedelta(0)
            <= now - timestamp(current.published_at)
            <= timedelta(minutes=15)
            or not timestamp(current.published_at) <= timestamp(own.issued_at) <= now
        ):
            raise ValueError("continuation not at current captured source")
        snapshots, proofs = [], set()
        for item, original_raw in walk(
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
            original = json.loads(original_raw, object_pairs_hook=_object)["envelope"]
            if original["signerKeyId"] == retiring_id:
                snapshots.append((item.revision, item.digest))
            if (
                original["version"] == 2
                and original["recoveryProof"]["envelope"]["signerKeyId"] == retiring_id
            ):
                proofs.add(store.digest(canonical(original["recoveryProof"])))
        if sorted(snapshots) != [
            (s.revision, s.digest) for s in own.snapshots
        ] or proofs != set(own.recovery_proofs):
            raise ValueError(
                "retiring handover must cover exactly the retained signer originals"
            )
        envelope = Continuation(
            version=1,
            kind="CHECKPOINT_CATALOG_KEY_CONTINUATION",
            continuationId=str(uuid4()),
            rootHandoverId=parent.root.handover_id,
            catalogId=current.catalog_id,
            workspaceId=str(context.workspace_id),
            generationId=str(context.generation_id),
            disposition="NORMAL_RETIREMENT_CONTINUATION",
            parentDigest=expected_parent_digest,
            parent=base64.b64encode(parent_raw).decode(),
            retiringHandoverDigest=expected_retiring_handover_digest,
            retiringKeyId=retiring_id,
            retiringPublicDigest=store.digest(public_keys[retiring_id]),
            successorKeyId=successor_id,
            successorPublicDigest=store.digest(public_keys[successor_id]),
            issuedAt=now.isoformat(),
            capturedRevision=actual[0],
            capturedDigest=actual[1],
            capturedSequence=actual[2],
            capturedRecordDigest=actual[3],
        )
        message = DOMAIN + canonical(envelope.model_dump(by_alias=True))
        doc = Document(
            envelope=envelope,
            retiringSignature=base64.b64encode(
                retiring_signer.sign(b"RETIRING\0" + message)
            ).decode(),
            successorSignature=base64.b64encode(
                successor_signer.sign(b"SUCCESSOR\0" + message)
            ).decode(),
        )
        raw = canonical(doc.model_dump(by_alias=True)) + b"\n"
        # Check the prospective graph against current metadata plus this planned normal retirement.
        registry = dict(lifecycle.records) | {
            (str(context.workspace_id), retiring_id): handover.Grant(
                "RETIRED", public_keys[retiring_id], {}, frozenset()
            )
        }
        verified = verify(
            raw,
            public_keys=public_keys,
            retiring_key_id=predecessor_id,
            retiring_public=predecessor.public_key,
            workspace_id=context.workspace_id,
            registry=registry,
        )
        if capture(verified.steps[-1]) != capture(own):
            raise ValueError("new continuation capture mismatch")
        store.cas(root, pin)
        return raw, {
            "continuationId": envelope.continuation_id,
            "handoverDigest": store.digest(raw),
            "rootHandoverId": parent.root.handover_id,
            "catalogId": current.catalog_id,
            "capturedRevision": current.revision,
            "edges": len(verified.steps) + 1,
            "ready": False,
        }
