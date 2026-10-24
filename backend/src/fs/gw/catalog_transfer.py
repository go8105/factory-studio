"""Bounded offline catalog transfer, preserving every supplied signed revision."""

import base64
import json
import os
import stat
from datetime import timedelta
from itertools import pairwise
from typing import Literal
from uuid import uuid4

from pydantic import Field

from fs.gw import catalog_recovery as recovery
from fs.gw import catalog_store as store
from fs.gw.checkpoint_catalog import (
    CatalogConfig,
    RecoveryCatalog,
    Versioned,
    _object,
    verify_document,
)
from fs.gw.checkpoint_catalog import uuid4 as catalog_id
from fs.gw.operating_contract import canonical, timestamp
from fs.gw.restore_recheck import verify_checkpoint_head

MAX_TRANSFER = 8 * 1024 * 1024
MAX_SNAPSHOTS = 256


class Identity(Versioned):
    kind: Literal["CATALOG_RECEIVER"]
    catalog_id: str = Field(alias="catalogId")
    workspace_id: str = Field(alias="workspaceId", pattern=r"^[1-9][0-9]{0,18}$")
    generation_id: str = Field(alias="generationId", pattern=r"^[1-9][0-9]{0,18}$")
    bootstrap_digest: str = Field(alias="bootstrapDigest", pattern=r"^[0-9a-f]{64}$")


class Snapshot(Versioned):
    revision: int = Field(ge=1, le=9223372036854775807)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    content: str = Field(min_length=1, max_length=3 * 1024 * 1024)


class Transfer(Versioned):
    kind: Literal["CHECKPOINT_CATALOG_TRANSFER"]
    catalog_id: str = Field(alias="catalogId")
    workspace_id: str = Field(alias="workspaceId", pattern=r"^[1-9][0-9]{0,18}$")
    generation_id: str = Field(alias="generationId", pattern=r"^[1-9][0-9]{0,18}$")
    base_revision: int = Field(alias="baseRevision", ge=0, le=9223372036854775807)
    base_digest: str = Field(alias="baseDigest", pattern=r"^(ABSENT|[0-9a-f]{64})$")
    snapshots: list[Snapshot] = Field(min_length=1, max_length=MAX_SNAPSHOTS)


class Artifact(Snapshot):
    actual_digest: str = Field(alias="actualDigest", pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0, le=store.MAX_BYTES)
    content: str = Field(max_length=3 * 1024 * 1024)


class RecoveryTransfer(Transfer):
    version: Literal[2]
    artifacts: list[Artifact] = Field(max_length=MAX_SNAPSHOTS)


class ReceiveIntent(Versioned):
    kind: Literal["CATALOG_RECEIVE_PENDING"]
    transfer_digest: str = Field(alias="transferDigest", pattern=r"^[0-9a-f]{64}$")
    catalog_id: str = Field(alias="catalogId")
    workspace_id: str = Field(alias="workspaceId", pattern=r"^[1-9][0-9]{0,18}$")
    generation_id: str = Field(alias="generationId", pattern=r"^[1-9][0-9]{0,18}$")
    base_pin_digest: str = Field(
        alias="basePinDigest", pattern=r"^(ABSENT|[0-9a-f]{64})$"
    )
    base_revision: int = Field(alias="baseRevision", ge=0)
    base_digest: str = Field(alias="baseDigest", pattern=r"^(ABSENT|[0-9a-f]{64})$")


def check_identity(root, catalog):
    identity = Identity.model_validate(
        json.loads(store.read_fd(root, store.RECEIVER, 8192), object_pairs_hook=_object)
    )
    catalog_id(identity.catalog_id)
    record = catalog.records[0]
    if (
        identity.catalog_id != catalog.catalog_id
        or identity.workspace_id != record.workspace_id
        or identity.generation_id != record.generation_id
    ):
        raise ValueError("receiver identity mismatch")
    return identity


def decode_snapshot(snapshot, identity, *, context, public_keys):
    raw = base64.b64decode(snapshot.content, validate=True)
    config = CatalogConfig(
        version=1,
        provider="SIGNED_SNAPSHOT_FILE",
        catalogId=identity,
        file="/operator-owned-unused-path",
        digest=snapshot.digest,
    )
    catalog = verify_document(
        raw, config, public_keys=public_keys, workspace_id=context.workspace_id
    )
    store.check_scope(catalog, context)
    if catalog.revision != snapshot.revision or len(catalog.records) != 1:
        raise ValueError("transfer revision/shape mismatch")
    record = catalog.records[0]
    if record.result == "PASS":
        if record.head is None:
            raise ValueError("managed PASS requires original HEAD")
        verify_checkpoint_head(record.head, public_keys, str(context.workspace_id))
    elif record.head is not None:
        raise ValueError("managed failure/partial must not infer a HEAD")
    return catalog, raw


def transition(before, after, before_digest):
    if (
        isinstance(after, RecoveryCatalog)
        and after.revision == after.recovery_proof["envelope"]["targetRevision"]
    ):
        return recovery.bridge(before, after, before_digest)
    if (
        after.catalog_id != before.catalog_id
        or after.revision != before.revision + 1
        or timestamp(after.published_at) < timestamp(before.published_at)
    ):
        raise ValueError("catalog revision gap or regression")
    previous, record = before.records[0], after.records[0]
    if record.sequence == previous.sequence:
        if canonical(record.model_dump(by_alias=True)) != canonical(
            previous.model_dump(by_alias=True)
        ):
            raise ValueError("refresh changed a recorded result")
        return
    if record.sequence != previous.sequence + 1 or timestamp(
        record.recorded_at
    ) < timestamp(previous.recorded_at):
        raise ValueError("catalog event gap or regression")
    if record.result == "PASS":
        captured = timestamp(record.head["payload"]["capturedAt"])
        if previous.result != "PASS" and captured <= timestamp(previous.recorded_at):
            raise ValueError("old success cannot replace failure")
        if previous.head is not None:
            old_capture = timestamp(previous.head["payload"]["capturedAt"])
            if captured < old_capture or (
                captured == old_capture
                and canonical(record.head) != canonical(previous.head)
            ):
                raise ValueError("HEAD capture regressed")


def validate(
    raw,
    *,
    expected_transfer_digest,
    expected_catalog_id,
    context,
    public_keys,
    now,
    allow_expired=False,
):
    catalog_id(expected_catalog_id)
    if (
        not 0 < len(raw) <= MAX_TRANSFER
        or store.digest(raw) != expected_transfer_digest
    ):
        raise ValueError("transfer bytes differ from operator anchor")
    value = json.loads(raw, object_pairs_hook=_object)
    model = (
        RecoveryTransfer
        if isinstance(value, dict)
        and type(value.get("version")) is int
        and value["version"] == 2
        else Transfer
    )
    bundle = model.model_validate(value)
    if (
        bundle.catalog_id != expected_catalog_id
        or bundle.workspace_id != str(context.workspace_id)
        or bundle.generation_id != str(context.generation_id)
        or (bundle.base_revision == 0) != (bundle.base_digest == "ABSENT")
    ):
        raise ValueError("transfer scope/base mismatch")
    decoded = [
        decode_snapshot(
            snapshot, expected_catalog_id, context=context, public_keys=public_keys
        )
        for snapshot in bundle.snapshots
    ]
    first = decoded[0][0]
    proofs = []
    if bundle.base_revision:
        if (
            first.revision != bundle.base_revision
            or store.digest(decoded[0][1]) != bundle.base_digest
            or len(decoded) < 2
        ):
            raise ValueError("transfer base differs or no progress")
    elif first.revision != 1 or first.records[0].sequence != 1:
        if not isinstance(first, RecoveryCatalog):
            raise ValueError("initial history needs signed recovery")
        proofs.append(recovery.bridge(None, first, "ABSENT"))
    for before, after in pairwise(decoded):
        proof = transition(before[0], after[0], store.digest(before[1]))
        if proof is not None:
            proofs.append(proof)
    if any(isinstance(c, RecoveryCatalog) for c, _ in decoded) and not isinstance(
        bundle, RecoveryTransfer
    ):
        raise ValueError("recovery transfer format required")
    needed = {}
    for proof in proofs:
        for slot in proof.slots:
            if slot.revision in needed:
                raise ValueError("overlapping recovery slots")
            needed[slot.revision] = slot
    artifacts = getattr(bundle, "artifacts", [])
    actual = {a.revision: a for a in artifacts}
    if len(actual) != len(artifacts) or set(actual) != {
        r for r, slot in needed.items() if slot.actual_digest is not None
    }:
        raise ValueError("missing/extra interruption artifacts")
    if set(needed) & {c.revision for c, _ in decoded}:
        raise ValueError("unknown artifact cannot become a committed snapshot")
    for revision, artifact in actual.items():
        slot = needed[revision]
        data = base64.b64decode(artifact.content, validate=True)
        if (
            artifact.digest != slot.expected_digest
            or artifact.actual_digest != slot.actual_digest
            or artifact.size != slot.size
            or len(data) != slot.size
            or store.digest(data) != slot.actual_digest
        ):
            raise ValueError("interrupted original differs from signed recovery")
    latest = decoded[-1][0]
    age = now - timestamp(latest.published_at)
    if age < -timedelta(seconds=30) or (
        age > timedelta(minutes=15) and not allow_expired
    ):
        raise ValueError("fresh transfer target required")
    return bundle, decoded


def export(path, *, context, public_keys, now, base_revision, base_digest):
    """Export through current source pin. Missing/corrupt history never gets skipped."""
    with store.directory(path) as root, store.locked(root):
        catalog, pin, _ = store.current(
            root, path, public_keys=public_keys, workspace_id=context.workspace_id
        )
        if catalog is None or not 0 <= base_revision < catalog.revision:
            raise ValueError("current source and an older receiver base required")
        store.check_scope(catalog, context)
        names, _ = store.inventory(root)
        indexed = {
            int(m[1]): (name, m[2])
            for name in names
            if (m := store.NAME.fullmatch(name))
        }
        snapshots, artifacts = [], []
        revision = catalog.revision
        total = 0
        while revision:
            if len(snapshots) >= MAX_SNAPSHOTS:
                raise ValueError("transfer batch limit; do not discard history")
            name, sha = indexed[revision]
            data = store.read_fd(root, name)
            snapshot = Snapshot(
                version=1,
                revision=revision,
                digest=sha,
                content=base64.b64encode(data).decode(),
            )
            current_catalog, _ = decode_snapshot(
                snapshot, catalog.catalog_id, context=context, public_keys=public_keys
            )
            total += len(data) * 4 // 3 + 512
            snapshots.append(snapshot)
            if revision == base_revision:
                break
            if (
                isinstance(current_catalog, RecoveryCatalog)
                and revision
                == current_catalog.recovery_proof["envelope"]["targetRevision"]
            ):
                proof = recovery.Proof.model_validate(
                    current_catalog.recovery_proof
                ).envelope
                previous = proof.base_revision
                if previous < base_revision:
                    raise ValueError("receiver base is inside an unresolved interval")
                for slot in proof.slots:
                    if slot.actual_digest is None:
                        if slot.revision in indexed:
                            raise ValueError(
                                "previously absent interruption file appeared"
                            )
                    else:
                        gap_name, expected = indexed[slot.revision]
                        gap_raw = store.read_fd(root, gap_name, allow_empty=True)
                        if (
                            expected != slot.expected_digest
                            or len(gap_raw) != slot.size
                            or store.digest(gap_raw) != slot.actual_digest
                        ):
                            raise ValueError(
                                "interruption evidence changed after signing"
                            )
                        total += len(gap_raw) * 4 // 3 + 512
                        if total > MAX_TRANSFER or len(artifacts) >= MAX_SNAPSHOTS:
                            raise ValueError("transfer size/artifact limit")
                        artifacts.append(
                            Artifact(
                                version=1,
                                revision=slot.revision,
                                digest=expected,
                                actualDigest=slot.actual_digest,
                                size=len(gap_raw),
                                content=base64.b64encode(gap_raw).decode(),
                            )
                        )
                revision = previous
            else:
                revision -= 1
            if total > MAX_TRANSFER or len(artifacts) > MAX_SNAPSHOTS:
                raise ValueError("transfer size/artifact limit")
        snapshots.reverse()
        fields = {
            "kind": "CHECKPOINT_CATALOG_TRANSFER",
            "catalogId": catalog.catalog_id,
            "workspaceId": str(context.workspace_id),
            "generationId": str(context.generation_id),
            "baseRevision": base_revision,
            "baseDigest": base_digest,
            "snapshots": snapshots,
        }
        if any(
            json.loads(base64.b64decode(s.content))["envelope"]["version"] == 2
            for s in snapshots
        ):
            bundle = RecoveryTransfer(
                version=2,
                artifacts=sorted(artifacts, key=lambda a: a.revision),
                **fields,
            )
        else:
            bundle = Transfer(version=1, **fields)
        raw = canonical(bundle.model_dump(by_alias=True)) + b"\n"
        validate(
            raw,
            expected_transfer_digest=store.digest(raw),
            expected_catalog_id=catalog.catalog_id,
            context=context,
            public_keys=public_keys,
            now=now,
        )
        store.cas(root, pin)
        return raw, {
            "catalogId": catalog.catalog_id,
            "transferDigest": store.digest(raw),
            "baseRevision": base_revision,
            "targetRevision": catalog.revision,
            "targetCatalogDigest": snapshots[-1].digest,
            "sourceResult": catalog.records[0].result,
            "ready": False,
        }


def put_snapshot(root, name, raw):
    """Publish complete bytes via an exclusive hard link; interrupted temps remain bounded."""
    try:
        existing = os.stat(name, dir_fd=root, follow_symlinks=False)
    except FileNotFoundError:
        temp = ".pin-" + uuid4().hex
        store.write_new(root, temp, raw)
        os.link(temp, name, src_dir_fd=root, dst_dir_fd=root, follow_symlinks=False)
        os.fsync(root)
        os.unlink(temp, dir_fd=root)
        os.fsync(root)
        return
    if (
        not stat.S_ISREG(existing.st_mode)
        or existing.st_uid != os.geteuid()
        or existing.st_mode & 0o077
        or existing.st_nlink not in {1, 2}
    ):
        raise ValueError("existing received snapshot invalid")
    if store.read_fd(root, name, max_links=2, allow_empty=not raw) != raw:
        raise ValueError("received immutable snapshot differs")
    if existing.st_nlink == 2:
        # A kill after link but before unlink may leave exactly one owned temp alias.
        names, _ = store.inventory(root)
        aliases = [
            n
            for n in names
            if n.startswith(".pin-")
            and (i := os.stat(n, dir_fd=root, follow_symlinks=False)).st_dev
            == existing.st_dev
            and i.st_ino == existing.st_ino
        ]
        if len(aliases) != 1:
            raise ValueError("snapshot hard link is not a transfer temp")
        os.unlink(aliases[0], dir_fd=root)
        os.fsync(root)
    if store.read_fd(root, name, allow_empty=not raw) != raw:
        raise ValueError("received immutable snapshot differs")
    # Re-sync even an existing complete file before clearing a pending operation.
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=root)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def install(
    path,
    raw,
    *,
    context,
    public_keys,
    now,
    expected_transfer_digest,
    expected_catalog_id,
    expected_pin_digest,
    initialize=False,
    resume=False,
):
    # The separately confirmed anchor and receiver CAS establish a fence BEFORE parsing input.
    catalog_id(expected_catalog_id)
    if len(expected_transfer_digest) != 64 or any(
        c not in "0123456789abcdef" for c in expected_transfer_digest
    ):
        raise ValueError("invalid operator transfer anchor")
    with store.directory(path) as root, store.locked(root):
        names, highest = store.inventory(root)
        pending = store.PENDING in names
        old, pin, _ = store.current(
            root,
            path,
            public_keys=public_keys,
            workspace_id=context.workspace_id,
            healthy=not pending,
        )
        store.cas(root, expected_pin_digest)
        store.check_scope(old, context)
        if old and (
            store.RECEIVER not in names or old.catalog_id != expected_catalog_id
        ):
            raise ValueError("receiver identity differs or publisher store selected")
        intent = None
        if pending:
            if not resume or initialize:
                raise ValueError("explicit same-transfer resume required")
            intent = ReceiveIntent.model_validate(
                json.loads(
                    store.read_fd(root, store.PENDING, 8192), object_pairs_hook=_object
                )
            )
            if (
                intent.transfer_digest != expected_transfer_digest
                or intent.catalog_id != expected_catalog_id
                or intent.workspace_id != str(context.workspace_id)
                or intent.generation_id != str(context.generation_id)
            ):
                raise ValueError("pending transfer differs")
        elif resume:
            if old is None or initialize:
                raise ValueError("no matching completed transfer")
        elif old is None:
            if (
                not initialize
                or expected_pin_digest != "ABSENT"
                or set(names) != {store.LOCK}
            ):
                raise ValueError("explicit empty receiver bootstrap required")
        elif initialize:
            raise ValueError("receiver already initialized")
        if not pending and not resume:
            base_digest = "ABSENT"
            if old:
                config = CatalogConfig.model_validate(
                    json.loads(
                        store.read_fd(root, store.PIN, 8192), object_pairs_hook=_object
                    )
                )
                base_digest = config.digest
            intent = ReceiveIntent(
                version=1,
                kind="CATALOG_RECEIVE_PENDING",
                transferDigest=expected_transfer_digest,
                catalogId=expected_catalog_id,
                workspaceId=str(context.workspace_id),
                generationId=str(context.generation_id),
                basePinDigest=pin,
                baseRevision=old.revision if old else 0,
                baseDigest=base_digest,
            )
            store.write_new(
                root, store.PENDING, canonical(intent.model_dump(by_alias=True)) + b"\n"
            )
        bundle, decoded = validate(
            raw,
            expected_transfer_digest=expected_transfer_digest,
            expected_catalog_id=expected_catalog_id,
            context=context,
            public_keys=public_keys,
            now=now,
            allow_expired=bool(pending and resume),
        )
        target, target_raw = decoded[-1]
        if intent:
            if (
                intent.base_revision != bundle.base_revision
                or intent.base_digest != bundle.base_digest
            ):
                raise ValueError("transfer does not start at fenced receiver base")
            if old and old.revision == target.revision:
                config = CatalogConfig.model_validate(
                    json.loads(
                        store.read_fd(root, store.PIN, 8192), object_pairs_hook=_object
                    )
                )
                if config.digest != store.digest(target_raw):
                    raise ValueError("completed target differs")
            elif (
                pin != intent.base_pin_digest
                or (old.revision if old else 0) != intent.base_revision
            ):
                raise ValueError("receiver base pin changed")
        elif old.revision != target.revision:
            raise ValueError("no matching completed transfer")
        if (
            old is not None
            and old.revision != target.revision
            and (
                old.revision != bundle.base_revision
                or store.digest(
                    store.read_fd(
                        root, store.filename(old.revision, bundle.base_digest)
                    )
                )
                != bundle.base_digest
            )
        ):
            raise ValueError("receiver base catalog differs")
        if old is not None and old.revision == target.revision:
            config = CatalogConfig.model_validate(
                json.loads(
                    store.read_fd(root, store.PIN, 8192), object_pairs_hook=_object
                )
            )
            if config.digest != store.digest(target_raw):
                raise ValueError("same receiver revision has different target bytes")
        indexed = {
            int(m[1]): name for name in names if (m := store.NAME.fullmatch(name))
        }
        wanted = [(catalog.revision, store.digest(data)) for catalog, data in decoded]
        wanted += [(a.revision, a.digest) for a in getattr(bundle, "artifacts", [])]
        if any(
            revision in indexed and indexed[revision] != store.filename(revision, sha)
            for revision, sha in wanted
        ):
            raise ValueError("received revision conflicts with retained history")
        if highest > target.revision:
            raise ValueError("newer receiver data exists")
        if store.RECEIVER not in names or (pending and bundle.base_revision == 0):
            identity = Identity(
                version=1,
                kind="CATALOG_RECEIVER",
                catalogId=expected_catalog_id,
                workspaceId=str(context.workspace_id),
                generationId=str(context.generation_id),
                bootstrapDigest=expected_transfer_digest,
            )
            put_snapshot(
                root,
                store.RECEIVER,
                canonical(identity.model_dump(by_alias=True)) + b"\n",
            )
        else:
            check_identity(root, target)
        for artifact in getattr(bundle, "artifacts", []):
            put_snapshot(
                root,
                store.filename(artifact.revision, artifact.digest),
                base64.b64decode(artifact.content, validate=True),
            )
        for catalog, data in decoded:
            put_snapshot(
                root, store.filename(catalog.revision, store.digest(data)), data
            )
        if not pending and resume:
            report = {
                "catalogId": target.catalog_id,
                "revision": target.revision,
                "sequence": target.records[0].sequence,
                "result": target.records[0].result,
                "catalogDigest": store.digest(target_raw),
                "pinDigest": pin,
                "ready": False,
            }
        else:
            report = store.activate(root, path, target, target_raw, pin)
        report["targetFresh"] = (
            -timedelta(seconds=30)
            <= now - timestamp(target.published_at)
            <= timedelta(minutes=15)
        )
        record = target.records[0]
        report["contextMatches"] = (
            record.policy_digest == context.policy.digest()
            and record.code_revision == context.code_revision
            and record.db_revision == context.db_revision
        )
        return report
