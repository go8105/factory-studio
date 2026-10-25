"""Pinned trust-history export/recovery; caller's latest anchor is never imported trust.

This local adapter preserves damaged originals in the old directory and activates
only a separate recovered directory. It does not establish external independence.
"""

import json
import os
from contextlib import ExitStack
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from fs.gw import catalog_store as store
from fs.gw import catalog_trust_store as floor
from fs.gw.checkpoint_catalog import Versioned, _object
from fs.gw.checkpoint_catalog import uuid4 as check_id
from fs.gw.operating_contract import canonical

MANIFEST = "trust-manifest.json"
RECEIVING = ".trust-receiving"
RECEIPT = ".trust-received.json"
MAX_MANIFEST = 2 * 1024 * 1024


class Anchor(Versioned):
    ledger_id: str = Field(alias="ledgerId")
    revision: int = Field(ge=1, le=floor.MAX_RECORDS)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def coherent(self):
        check_id(self.ledger_id)
        return self


class Part(Versioned):
    revision: int = Field(ge=1, le=floor.MAX_RECORDS)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=1, le=floor.MAX_BYTES)

    @property
    def name(self):
        return filename(self.revision, self.digest)


class Manifest(Versioned):
    kind: Literal["CATALOG_TRUST_EXPORT"]
    anchor: Anchor
    files: list[Part] = Field(min_length=1, max_length=floor.MAX_RECORDS)

    @model_validator(mode="after")
    def coherent(self):
        if (
            len(self.files) != self.anchor.revision
            or [f.revision for f in self.files] != list(range(1, len(self.files) + 1))
            or self.files[-1].digest != self.anchor.digest
        ):
            raise ValueError("trust manifest incomplete")
        return self


class Plan(Versioned):
    kind: Literal["CATALOG_TRUST_RECOVERY"]
    anchor: Anchor
    manifest_digest: str = Field(alias="manifestDigest", pattern=r"^[0-9a-f]{64}$")
    origin_directory: str | None = Field(alias="originDirectory", max_length=4096)
    origin_digest: str | None = Field(alias="originDigest", pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def coherent(self):
        if (self.origin_directory is None) != (self.origin_digest is None) or (
            self.origin_directory is not None
            and not Path(self.origin_directory).is_absolute()
        ):
            raise ValueError("invalid recovery origin")
        return self


def filename(revision, digest):
    return f"trust-{revision:08d}-{digest}.json"


def _names(root, allowed):
    names = []
    with os.scandir(root) as entries:
        for entry in entries:
            if len(names) >= floor.MAX_RECORDS + 5 or not allowed(entry.name):
                raise ValueError("unexpected recovery entry or size limit")
            names.append(entry.name)
    return sorted(names)


def _separate(*paths):
    paths = [Path(p).resolve() for p in paths if p is not None]
    for index, path in enumerate(paths):
        if any(
            path.is_relative_to(other) or other.is_relative_to(path)
            for other in paths[:index]
        ):
            raise ValueError("recovery directories must be separate")


def _anchor(record, sha):
    if record is None:
        raise ValueError("trust anchor missing")
    return Anchor(
        version=1, ledgerId=record.ledger_id, revision=record.revision, digest=sha
    )


def report(anchor, manifest_digest):
    return {
        "ledgerId": anchor.ledger_id,
        "revision": anchor.revision,
        "digest": anchor.digest,
        "manifestDigest": manifest_digest,
        "state": "COMPLETE",
        "ready": False,
    }


def export(path, output, *, anchor):
    _separate(path, output)
    with (
        store.directory(path) as root,
        store.locked(root),
        store.directory(output) as target,
        store.locked(target),
    ):
        if set(os.listdir(target)) != {store.LOCK}:
            raise ValueError("new empty export directory required")
        head, sha = floor._history(root)
        if head is None or _anchor(head, sha) != anchor:
            raise ValueError("source does not match confirmed latest trust anchor")
        files = []
        originals = sorted(n for n in os.listdir(root) if floor.NAME.fullmatch(n))
        for revision, name in enumerate(originals, 1):
            raw = store.read_fd(root, name, floor.MAX_BYTES)
            sha = store.digest(raw)
            if name != filename(revision, sha):
                raise ValueError("source original changed")
            store.write_new(target, name, raw)
            files.append(Part(version=1, revision=revision, digest=sha, size=len(raw)))
        current, sha = floor._history(root)
        if _anchor(current, sha) != anchor:
            raise ValueError("source changed during export")
        manifest = Manifest(
            version=1, kind="CATALOG_TRUST_EXPORT", anchor=anchor, files=files
        )
        raw = canonical(manifest.model_dump(by_alias=True))
        if len(raw) > MAX_MANIFEST:
            raise ValueError("trust manifest size limit")
        store.write_new(target, MANIFEST, raw)  # Only complete exports get a manifest.
        return report(anchor, store.digest(raw))


def _manifest(root, anchor, expected_digest):
    raw = store.read_fd(root, MANIFEST, MAX_MANIFEST)
    if store.digest(raw) != expected_digest:
        raise ValueError("trust manifest differs from confirmed pin")
    value = Manifest.model_validate(json.loads(raw, object_pairs_hook=_object))
    if value.anchor != anchor:
        raise ValueError("trust export is not confirmed latest anchor")
    names = _names(
        root, lambda n: n in {store.LOCK, MANIFEST} or floor.NAME.fullmatch(n)
    )
    if set(names) - {store.LOCK, MANIFEST} != {p.name for p in value.files}:
        raise ValueError("trust package extra or missing original")
    previous, sha = None, "ABSENT"
    for part in value.files:
        raw = _part(root, part)
        record = floor.Record.model_validate(json.loads(raw, object_pairs_hook=_object))
        if (
            record.ledger_id != anchor.ledger_id
            or record.revision != part.revision
            or record.previous_digest != sha
            or canonical(record.model_dump(by_alias=True)) != raw
        ):
            raise ValueError("trust history scope/chain differs")
        if previous is not None:
            floor.transition(previous.authorities, record.authorities)
        previous, sha = record, part.digest
    return value


def _part(root, part):
    raw = store.read_fd(root, part.name, floor.MAX_BYTES)
    if len(raw) != part.size or store.digest(raw) != part.digest:
        raise ValueError("trust original bytes differ")
    return raw


def _origin(root, anchor, manifest=None):
    """Fingerprint every retained original, including damaged bytes. Never rewrite it."""
    names = _names(
        root,
        lambda n: (
            n in {store.LOCK, floor.HEAD, floor.PENDING, RECEIPT}
            or floor.NAME.fullmatch(n)
        ),
    )
    inventory = []
    parts = None if manifest is None else {p.revision: p for p in manifest.files}
    revisions = set()
    for name in names:
        if name == store.LOCK:
            continue
        raw = store.read_fd(root, name, floor.MAX_BYTES, allow_empty=True)
        match = floor.NAME.fullmatch(name)
        if match:
            revision = int(match[1])
            if revision < 1 or revision in revisions or revision > anchor.revision:
                raise ValueError("newer or forked retained trust original")
            revisions.add(revision)
            if parts is not None and name != parts[revision].name:
                raise ValueError("retained trust branch differs")
        elif name in {floor.HEAD, floor.PENDING}:
            try:
                value = json.loads(raw, object_pairs_hook=_object)
            except json.JSONDecodeError, UnicodeDecodeError:
                value = None  # Damaged bytes are preserved; only the external pin can restore them.
            if value is not None:
                old = Anchor.model_validate(value)
                if old.ledger_id != anchor.ledger_id or old.revision > anchor.revision:
                    raise ValueError("newer or other retained trust head")
                if parts is not None and old.digest != parts[old.revision].digest:
                    raise ValueError("retained trust head branch differs")
        elif name == RECEIPT:
            old = Plan.model_validate(json.loads(raw, object_pairs_hook=_object))
            if (
                old.anchor.ledger_id != anchor.ledger_id
                or old.anchor.revision > anchor.revision
            ):
                raise ValueError("newer or other recovery receipt")
            if (
                parts is not None
                and old.anchor.digest != parts[old.anchor.revision].digest
            ):
                raise ValueError("retained recovery branch differs")
        inventory.append({"name": name, "digest": store.digest(raw), "size": len(raw)})
    return store.digest(canonical(inventory))


def validate_receipt(root, head):
    receipt = Plan.model_validate(
        json.loads(store.read_fd(root, RECEIPT, 8192), object_pairs_hook=_object)
    )
    anchor = receipt.anchor
    if (
        head is None
        or head.ledger_id != anchor.ledger_id
        or head.revision < anchor.revision
    ):
        raise ValueError("recovered trust floor rolled back")
    raw = store.read_fd(root, filename(anchor.revision, anchor.digest), floor.MAX_BYTES)
    if store.digest(raw) != anchor.digest:
        raise ValueError("recovered trust anchor differs")


def receive(
    package,
    output,
    *,
    anchor,
    expected_manifest_digest,
    origin=None,
    new_host=False,
    resume=False,
):
    if (origin is None) != new_host:
        raise ValueError("existing origin or explicit new host required")
    _separate(package, output, origin)
    with ExitStack() as stack:
        target = stack.enter_context(store.directory(output))
        stack.enter_context(store.locked(target))
        old = None
        if origin is not None:
            old = stack.enter_context(store.directory(origin))
            stack.enter_context(store.locked(old))
        origin_digest = None if old is None else _origin(old, anchor)
        plan = Plan(
            version=1,
            kind="CATALOG_TRUST_RECOVERY",
            anchor=anchor,
            manifestDigest=expected_manifest_digest,
            originDirectory=None if origin is None else str(Path(origin)),
            originDigest=origin_digest,
        )
        raw_plan = canonical(plan.model_dump(by_alias=True))
        names = _names(
            target,
            lambda n: (
                n in {store.LOCK, RECEIVING, RECEIPT, floor.HEAD, floor.PENDING}
                or floor.NAME.fullmatch(n)
            ),
        )
        if RECEIVING in names:
            if not resume or store.read_fd(target, RECEIVING, 8192) != raw_plan:
                raise ValueError("explicit same trust recovery resume required")
        elif RECEIPT in names:
            if not resume or store.read_fd(target, RECEIPT, 8192) != raw_plan:
                raise ValueError("different completed trust recovery")
            head, sha = floor._history(target)
            if _anchor(head, sha) != anchor:
                raise ValueError("completed recovery has advanced; old target refused")
            return report(anchor, expected_manifest_digest)
        else:
            if resume or set(names) != {store.LOCK}:
                raise ValueError("new empty recovered directory required")
            store.write_new(
                target, RECEIVING, raw_plan
            )  # Fence before reading untrusted package.
        source = stack.enter_context(store.directory(package))
        manifest = _manifest(source, anchor, expected_manifest_digest)
        if floor.HEAD in os.listdir(target) and store.read_fd(
            target, floor.HEAD, 1024
        ) != canonical(anchor.model_dump(by_alias=True)):
            raise ValueError(
                "recovery target head differs; never replace a newer claim"
            )
        if old is not None and _origin(old, anchor, manifest) != origin_digest:
            raise ValueError("retained origin changed")
        expected_names = {p.name for p in manifest.files}
        if any(floor.NAME.fullmatch(n) and n not in expected_names for n in names):
            raise ValueError("recovered directory trust conflict")
        for part in manifest.files:
            raw = _part(source, part)
            if part.name in os.listdir(target):
                if store.read_fd(target, part.name, floor.MAX_BYTES) != raw:
                    raise ValueError(
                        "incomplete recovery original; preserve and use a new directory"
                    )
            else:
                store.write_new(target, part.name, raw)
        # Re-read every stored original/transition before one final head activation.
        head, sha = floor._history(target, anchored=False, receiving=True)
        if head is None or _anchor(head, sha) != anchor:
            raise ValueError("recovered trust history differs")
        if old is not None and _origin(old, anchor, manifest) != origin_digest:
            raise ValueError("retained origin changed during recovery")
        if RECEIPT in os.listdir(target):
            if store.read_fd(target, RECEIPT, 8192) != raw_plan:
                raise ValueError("recovery receipt differs")
        else:
            store.write_new(target, RECEIPT, raw_plan)
        floor._activate(target, head, sha)
        os.unlink(RECEIVING, dir_fd=target)
        os.fsync(target)
        floor._history(target)
        return report(anchor, expected_manifest_digest)
