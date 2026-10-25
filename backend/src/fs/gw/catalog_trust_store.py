"""Local durable trust floor. Deployment must protect this store and its locator.

Append-only owned files detect configuration rollback while retained; they do not
prove independent storage or detect a host administrator rolling back all copies.
"""

import base64
import json
import os
import re
from typing import Literal
from uuid import uuid4

from pydantic import Field, model_validator

from fs.gw import catalog_store as store
from fs.gw.checkpoint_catalog import Versioned, _object
from fs.gw.checkpoint_catalog import uuid4 as check_id
from fs.gw.operating_contract import canonical
from fs.gw.trust_configuration import TrustConfigurationError

ENV = "FS_GW_CATALOG_TRUST_DIRECTORY"
HEAD = "current-trust.json"
PENDING = ".trust-head.pending"
MAX_RECORDS = 4096
MAX_BYTES = 256 * 1024
NAME = re.compile(r"trust-([0-9]{8})-([0-9a-f]{64})\.json\Z")


class Authority(Versioned):
    workspace_id: str = Field(alias="workspaceId", pattern=r"^[1-9][0-9]{0,18}$")
    key_id: str = Field(alias="keyId", pattern=r"^[A-Za-z0-9_-]{1,60}$")
    public_digest: str = Field(alias="publicDigest", pattern=r"^[0-9a-f]{64}$")
    state: Literal["ACTIVE", "RETIRED", "REVOKED"]
    approvals: list[list[str]] = Field(max_length=20)

    @model_validator(mode="after")
    def coherent(self):
        if (self.state == "RETIRED") != bool(self.approvals):
            raise ValueError("invalid trust floor grants")
        roots = set()
        for path in self.approvals:
            if (
                not 1 <= len(path) <= 8
                or len(set(path)) != len(path)
                or any(not re.fullmatch(r"[0-9a-f]{64}", sha) for sha in path)
                or path[0] in roots
            ):
                raise ValueError("invalid approval lineage")
            roots.add(path[0])
        return self


class Record(Versioned):
    kind: Literal["CATALOG_TRUST_FLOOR"]
    ledger_id: str = Field(alias="ledgerId")
    revision: int = Field(ge=1, le=MAX_RECORDS)
    previous_digest: str = Field(
        alias="previousDigest", pattern=r"^(ABSENT|[0-9a-f]{64})$"
    )
    authorities: list[Authority] = Field(min_length=1, max_length=2100)

    @model_validator(mode="after")
    def coherent(self):
        check_id(self.ledger_id)
        identities = [(a.workspace_id, a.key_id) for a in self.authorities]
        if identities != sorted(set(identities)):
            raise ValueError("ambiguous trust floor")
        names, publics = {}, {}
        for a in self.authorities:
            if (
                names.get(a.key_id, a.public_digest) != a.public_digest
                or publics.get(a.public_digest, a.key_id) != a.key_id
            ):
                raise ValueError("reused trust identity")
            names[a.key_id], publics[a.public_digest] = a.public_digest, a.key_id
        return self


def _lineage(raw):
    # Caller bind() verifies all signatures, parents and cross-links before commit.
    from fs.gw import catalog_key_chain as chain
    from fs.gw import catalog_key_handover as handover

    path = []
    total = 0
    while True:
        total += len(raw)
        if (
            not 0 < len(raw) <= handover.MAX_BYTES
            or total > chain.MAX_EXPANDED
            or len(path) >= 8
        ):
            raise ValueError("approval lineage limit")
        path.append(store.digest(raw))
        value = json.loads(raw, object_pairs_hook=_object)
        if (
            value.get("envelope", {}).get("kind")
            != "CHECKPOINT_CATALOG_KEY_CONTINUATION"
        ):
            handover.Document.model_validate(value)
            return list(reversed(path))
        document = chain.Document.model_validate(value)
        raw = base64.b64decode(document.envelope.parent, validate=True)
        if store.digest(raw) != document.envelope.parent_digest:
            raise ValueError("approval lineage differs")


def snapshot(trust):
    result = {}
    if not trust.scoped:
        raise ValueError("scoped trust required")
    for name, public in trust.items():
        companies, uses = trust.scopes[name]
        if "CHECKPOINT_CATALOG" in uses:
            for company in companies:
                result[company, name] = Authority(
                    version=1,
                    workspaceId=company,
                    keyId=name,
                    publicDigest=store.digest(public),
                    state="ACTIVE",
                    approvals=[],
                )
    if trust.catalog_lifecycle is not None:
        for (company, name), grant in trust.catalog_lifecycle.records.items():
            result[company, name] = Authority(
                version=1,
                workspaceId=company,
                keyId=name,
                publicDigest=store.digest(grant.public_key),
                state=grant.state,
                approvals=[list(path) for path in grant.approval_paths],
            )
    for a in result.values():
        for name, public in trust.items():
            sha = store.digest(public)
            if (
                name == a.key_id
                and (
                    sha != a.public_digest
                    or trust.scopes[name][1] != frozenset(["CHECKPOINT_CATALOG"])
                )
            ) or (name != a.key_id and sha == a.public_digest):
                raise ValueError("catalog trust identity reused or repurposed")
    return sorted(result.values(), key=lambda a: (a.workspace_id, a.key_id))


def transition(before, after):
    next_records = {(a.workspace_id, a.key_id): a for a in after}
    old_records = {(a.workspace_id, a.key_id): a for a in before}
    # Includes old ACTIVE identities: removed authority must be explicitly retired/revoked.
    names = {a.key_id: a.public_digest for a in before}
    publics = {a.public_digest: a.key_id for a in before}
    for a in after:
        if (
            names.get(a.key_id, a.public_digest) != a.public_digest
            or publics.get(a.public_digest, a.key_id) != a.key_id
        ):
            raise ValueError("trust identity changed")
        if (a.workspace_id, a.key_id) not in old_records and a.state == "RETIRED":
            raise ValueError("retirement requires previously active authority")
    for old in before:
        new = next_records.get((old.workspace_id, old.key_id))
        if new is None or old.public_digest != new.public_digest:
            raise ValueError("trust floor removed")
        if old.state == "REVOKED" and new.state != "REVOKED":
            raise ValueError("revocation cannot be undone")
        if old.state == "RETIRED":
            if new.state not in {"RETIRED", "REVOKED"}:
                raise ValueError("retired key reactivated")
            if new.state == "RETIRED":
                paths = {p[0]: p for p in new.approvals}
                if set(paths) != {p[0] for p in old.approvals} or any(
                    paths[p[0]][: len(p)] != p for p in old.approvals
                ):
                    raise ValueError("retirement approval rollback or fork")


def _history(root, *, anchored=True, receiving=False):
    from fs.gw import catalog_trust_transfer as transfer

    if not receiving and transfer.RECEIVING in os.listdir(root):
        raise TrustConfigurationError("TRUST_RECOVERY_PENDING")
    names = []
    with os.scandir(root) as entries:
        for entry in entries:
            if len(names) > MAX_RECORDS:
                raise ValueError("trust history limit")
            if entry.name not in {
                store.LOCK,
                HEAD,
                PENDING,
                transfer.RECEIVING,
                transfer.RECEIPT,
            }:
                if not NAME.fullmatch(entry.name):
                    raise ValueError("incomplete or unexpected trust history")
                names.append(entry.name)
    previous, sha = None, "ABSENT"
    for index, name in enumerate(sorted(names), 1):
        raw = store.read_fd(root, name, MAX_BYTES)
        record = Record.model_validate(json.loads(raw, object_pairs_hook=_object))
        match = NAME.fullmatch(name)
        if (
            record.revision != index
            or int(match[1]) != index
            or store.digest(raw) != match[2]
            or record.previous_digest != sha
            or canonical(record.model_dump(by_alias=True)) != raw
            or (previous is None and record.previous_digest != "ABSENT")
            or (previous is not None and previous.ledger_id != record.ledger_id)
        ):
            raise ValueError("trust history inconsistent")
        if previous is not None:
            transition(previous.authorities, record.authorities)
        previous, sha = record, store.digest(raw)
    if transfer.RECEIPT in os.listdir(root):
        transfer.validate_receipt(root, previous)
    if anchored:
        if PENDING in os.listdir(root):
            raise TrustConfigurationError("TRUST_UPDATE_PENDING")
        if previous is not None:
            if store.read_fd(root, HEAD, 1024) != _head_bytes(previous, sha):
                raise ValueError("trust head differs from retained history")
        elif HEAD in os.listdir(root):
            raise ValueError("trust history missing")
    return previous, sha


def _head_bytes(record, sha):
    return canonical(
        {
            "version": 1,
            "ledgerId": record.ledger_id,
            "revision": record.revision,
            "digest": sha,
        }
    )


def _activate(root, record, sha):
    raw = _head_bytes(record, sha)
    if PENDING in os.listdir(root):
        if store.read_fd(root, PENDING, 1024) != raw:
            raise ValueError("incomplete trust head differs")
    else:
        store.write_new(root, PENDING, raw)
    os.replace(PENDING, HEAD, src_dir_fd=root, dst_dir_fd=root)
    os.fsync(root)


def inspect(path):
    with store.directory(path) as root, store.locked(root):
        head, sha = _history(root)
        if head is None:
            raise ValueError("trust history not initialized")
        return head, sha


def check(trust, path):
    head, _ = inspect(path)
    if snapshot(trust) != head.authorities:
        raise TrustConfigurationError("TRUST_SETTINGS_MISMATCH")
    return trust


def _append(root, old, sha, authorities):
    record = Record(
        version=1,
        kind="CATALOG_TRUST_FLOOR",
        ledgerId=old.ledger_id if old else str(uuid4()),
        revision=old.revision + 1 if old else 1,
        previousDigest=sha,
        authorities=authorities,
    )
    raw = canonical(record.model_dump(by_alias=True))
    if len(raw) > MAX_BYTES:
        raise ValueError("trust record size limit")
    # Exclusive creation + file/directory fsync. An interrupted partial file blocks reads.
    store.write_new(root, f"trust-{record.revision:08d}-{store.digest(raw)}.json", raw)
    _activate(root, record, store.digest(raw))
    return record, store.digest(raw)


def commit(path, trust, *, expected_digest, initialize=False):
    authorities = snapshot(trust)
    with store.directory(path) as root, store.locked(root):
        old, sha = _history(root)
        if sha != expected_digest or initialize != (old is None):
            raise ValueError("trust history CAS mismatch")
        if old is not None:
            transition(old.authorities, authorities)
            if old.authorities == authorities:
                return old, sha
        return _append(root, old, sha, authorities)


def revoke(path, *, workspace_id, key_id, expected_digest):
    """Persist revocation before editing live settings, even if it invalidates a chain."""
    with store.directory(path) as root, store.locked(root):
        old, sha = _history(root)
        if old is None or sha != expected_digest:
            raise ValueError("trust history CAS mismatch")
        found = False
        authorities = []
        for a in old.authorities:
            if (a.workspace_id, a.key_id) == (workspace_id, key_id):
                found = True
                a = a.model_copy(update={"state": "REVOKED", "approvals": []})
            authorities.append(a)
        if not found:
            raise ValueError("unknown revocation identity")
        if old.authorities == authorities:
            return old, sha
        return _append(root, old, sha, authorities)


def resume(path, *, expected_digest):
    """Finish only an exact complete retained append; never repair corrupt originals."""
    with store.directory(path) as root, store.locked(root):
        head, sha = _history(root, anchored=False)
        if head is None or sha != expected_digest:
            raise ValueError("trust resume target differs")
        if HEAD in os.listdir(root):
            previous = store.read_fd(root, HEAD, 1024)
            # Exact old head bytes can only name the direct predecessor or same target.
            if previous != _head_bytes(head, sha):
                files = sorted(n for n in os.listdir(root) if NAME.fullmatch(n))
                if len(files) < 2:
                    raise ValueError("trust resume predecessor missing")
                raw = store.read_fd(root, files[-2], MAX_BYTES)
                old = Record.model_validate(json.loads(raw, object_pairs_hook=_object))
                if previous != _head_bytes(old, head.previous_digest):
                    raise ValueError("trust resume predecessor differs")
        elif head.revision != 1:
            raise ValueError("trust resume head missing")
        _activate(root, head, sha)
        return head, sha


def required(trust):
    return trust.catalog_lifecycle is not None or (
        trust.scoped
        and any("CHECKPOINT_CATALOG" in uses for _, uses in trust.scopes.values())
    )
