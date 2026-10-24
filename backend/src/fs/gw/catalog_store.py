"""Operator-owned catalog publishing. Local durability is not external independence."""

import base64
import fcntl
import hashlib
import json
import os
import re
import stat
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import Field

from fs.gw.checkpoint_catalog import (
    DOMAIN,
    MAX_BYTES,
    Catalog,
    CatalogConfig,
    CatalogRecord,
    _object,
    verify_document,
)
from fs.gw.evidence_trust import EvidenceTrust, authorize
from fs.gw.operating_contract import OperatingPolicy, StrictModel, canonical, timestamp
from fs.gw.restore_recheck import verify_checkpoint_head

PIN_ENV = "FS_GW_CHECKPOINT_CATALOG_PIN_FILE"
PIN = "current-pin.json"
PENDING = ".catalog.pending"
LOCK = ".catalog.lock"
NAME = re.compile(r"catalog-([0-9]{20})-([0-9a-f]{64})\.json\Z")


class PublishContext(StrictModel):
    workspace_id: int = Field(alias="workspaceId", ge=1)
    generation_id: int = Field(alias="generationId", ge=1)
    policy: OperatingPolicy
    code_revision: str = Field(alias="codeRevision", pattern=r"^[0-9a-f]{7,64}$")
    db_revision: str = Field(alias="dbRevision", pattern=r"^[A-Za-z0-9_]{1,100}$")


class Intent(StrictModel):
    version: int = Field(ge=1, le=1)
    catalog_id: str = Field(alias="catalogId")
    workspace_id: str = Field(alias="workspaceId", pattern=r"^[1-9][0-9]{0,18}$")
    generation_id: str = Field(alias="generationId", pattern=r"^[1-9][0-9]{0,18}$")
    revision: int = Field(ge=1)
    sequence: int = Field(ge=1)
    expected_pin_digest: str = Field(
        alias="expectedPinDigest", pattern=r"^(ABSENT|[0-9a-f]{64})$"
    )


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_fd(root, name, limit=MAX_BYTES):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
            or not 0 < info.st_size <= limit
        ):
            raise ValueError("private regular file required")
        raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("file too large")
        return raw


def load_private(path, limit=65536):
    path = Path(path)
    with directory(path.parent) as root:
        return json.loads(read_fd(root, path.name, limit), object_pairs_hook=_object)


@contextmanager
def directory(path):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError("absolute directory required")
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError("owned private directory required")
        yield fd
        current = path.lstat()
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError("catalog directory changed")
    finally:
        os.close(fd)


@contextmanager
def locked(root):
    fd = os.open(
        LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=root
    )
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
        ):
            raise ValueError("invalid catalog lock")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
        current = os.stat(LOCK, dir_fd=root, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError("catalog lock changed")
    finally:
        os.close(fd)


def inventory(root):
    names = []
    with os.scandir(root) as entries:
        for entry in entries:
            if len(names) >= 100000:
                raise ValueError("catalog inventory limit")
            names.append(entry.name)
    revisions = []
    for name in names:
        match = NAME.fullmatch(name)
        if match:
            revisions.append(int(match[1]))
        elif name not in {PIN, PENDING, LOCK} and not re.fullmatch(
            r"\.pin-[0-9a-f]{32}", name
        ):
            raise ValueError("unexpected catalog entry")
    if len(revisions) != len(set(revisions)):
        raise ValueError("conflicting catalog revisions")
    return names, max(revisions, default=0)


def current(root, path, *, public_keys, workspace_id, healthy=True):
    names, highest = inventory(root)
    if healthy and PENDING in names:
        raise ValueError("interrupted catalog publication")
    if PIN not in names:
        if healthy and highest:
            raise ValueError("catalog pin missing")
        return None, "ABSENT", highest
    raw_pin = read_fd(root, PIN, 8192)
    config = CatalogConfig.model_validate(
        json.loads(raw_pin, object_pairs_hook=_object)
    )
    file = Path(config.file)
    if file.parent != Path(path):
        raise ValueError("catalog must stay in its store")
    raw = read_fd(root, file.name)
    catalog = verify_document(
        raw, config, public_keys=public_keys, workspace_id=workspace_id
    )
    if (
        file.name != filename(catalog.revision, config.digest)
        or len(catalog.records) != 1
    ):
        raise ValueError("managed catalog shape mismatch")
    if healthy and highest != catalog.revision:
        raise ValueError("uncommitted newer catalog exists")
    if read_fd(root, PIN, 8192) != raw_pin:
        raise ValueError("catalog pin changed during read")
    return catalog, digest(raw_pin), highest


def filename(revision, sha):
    return f"catalog-{revision:020d}-{sha}.json"


def check_scope(catalog, context):
    if catalog and any(
        r.workspace_id != str(context.workspace_id)
        or r.generation_id != str(context.generation_id)
        for r in catalog.records
    ):
        raise ValueError("catalog company/generation differs")


def write_new(root, name, raw):
    fd = os.open(
        name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=root
    )
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.fsync(root)


def cas(root, expected):
    try:
        actual = digest(read_fd(root, PIN, 8192))
    except FileNotFoundError:
        actual = "ABSENT"
    if expected != actual:
        raise ValueError("catalog pin changed; inspect before retry")


def commit(root, path, catalog, signer, expected):
    envelope = catalog.model_dump(by_alias=True)
    raw = (
        canonical(
            {
                "envelope": envelope,
                "signature": base64.b64encode(
                    signer.sign(DOMAIN + canonical(envelope))
                ).decode(),
            }
        )
        + b"\n"
    )
    if len(raw) > MAX_BYTES:
        raise ValueError("catalog size limit")
    record = catalog.records[0]
    # Never overwrite or delete an old snapshot, including failed partial writes.
    name = filename(catalog.revision, digest(raw))
    write_new(root, name, raw)
    config = CatalogConfig(
        version=1,
        provider="SIGNED_SNAPSHOT_FILE",
        catalogId=catalog.catalog_id,
        file=str(Path(path) / name),
        digest=digest(raw),
    )
    raw_pin = canonical(config.model_dump(by_alias=True)) + b"\n"
    temp = ".pin-" + uuid4().hex
    write_new(root, temp, raw_pin)
    cas(root, expected)
    os.replace(temp, PIN, src_dir_fd=root, dst_dir_fd=root)
    os.fsync(root)
    os.unlink(PENDING, dir_fd=root)
    os.fsync(root)
    return {
        "catalogId": catalog.catalog_id,
        "revision": catalog.revision,
        "sequence": record.sequence,
        "result": record.result,
        "catalogDigest": config.digest,
        "pinDigest": digest(raw_pin),
        "ready": False,
    }


def checkpoint_hash(path):
    path = Path(path)
    with directory(path.parent) as root:
        fd = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root
        )
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_uid != os.geteuid()
                or before.st_mode & 0o077
                or before.st_nlink != 1
                or not 36 <= before.st_size <= 1024**3
            ):
                raise ValueError("invalid encrypted checkpoint")
            prefix = stream.read(8)
            if prefix != b"FSBACK01":
                raise ValueError("encrypted checkpoint format required")
            sha = hashlib.sha256(prefix)
            size = len(prefix)
            while block := stream.read(1024 * 1024):
                size += len(block)
                if size > 1024**3:
                    raise ValueError("checkpoint too large")
                sha.update(block)
            after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ) or size != before.st_size:
                raise ValueError("checkpoint changed during read")
            return sha.hexdigest()


def publish(
    path,
    *,
    context,
    public_keys,
    signer,
    signer_id,
    now,
    expected_pin_digest,
    operation="publish",
    head_path=None,
    checkpoint_path=None,
    initialize=False,
):
    """Return PASS for verified file identity only; no operational acceptance claim."""
    if operation not in {"publish", "refresh", "recover-pending"}:
        raise ValueError("unknown catalog operation")
    if not isinstance(public_keys, EvidenceTrust) or not public_keys.scoped:
        raise ValueError("scoped catalog authority required")
    authorize(public_keys, signer_id, "CHECKPOINT_CATALOG", str(context.workspace_id))
    Ed25519PublicKey.from_public_bytes(public_keys[signer_id]).verify(
        signer.sign(b"catalog-key-check"), b"catalog-key-check"
    )
    with directory(path) as root, locked(root):
        recovering = operation == "recover-pending"
        old, pin, highest = current(
            root,
            path,
            public_keys=public_keys,
            workspace_id=context.workspace_id,
            healthy=not recovering,
        )
        cas(root, expected_pin_digest)
        check_scope(old, context)
        if old is not None and initialize:
            raise ValueError("initialization cannot replace an existing catalog")
        names, _ = inventory(root)
        intent = None
        if recovering:
            intent = Intent.model_validate(
                json.loads(read_fd(root, PENDING, 8192), object_pairs_hook=_object)
            )
            if (
                intent.workspace_id != str(context.workspace_id)
                or intent.generation_id != str(context.generation_id)
                or (old and intent.catalog_id != old.catalog_id)
            ):
                raise ValueError("pending publication scope differs")
            from fs.gw.checkpoint_catalog import uuid4 as validate_id

            validate_id(intent.catalog_id)
        elif old is None and (
            not initialize or expected_pin_digest != "ABSENT" or set(names) != {LOCK}
        ):
            raise ValueError("explicit empty-store initialization required")
        if old is None and operation == "refresh":
            raise ValueError("refresh requires current catalog")
        if old and timestamp(old.published_at) > now:
            raise ValueError("publication clock moved backwards")
        previous = old.records[0] if old else None
        revision = max(highest, intent.revision if intent else 0) + 1
        sequence = (
            max(previous.sequence if previous else 0, intent.sequence if intent else 0)
            + 1
        )
        catalog_id = (
            old.catalog_id if old else intent.catalog_id if intent else str(uuid4())
        )
        if not recovering:
            intent = Intent(
                version=1,
                catalogId=catalog_id,
                workspaceId=str(context.workspace_id),
                generationId=str(context.generation_id),
                revision=revision,
                sequence=sequence,
                expectedPinDigest=pin,
            )
            # Persist intent before reading source files: a killed validation also blocks old success.
            write_new(
                root, PENDING, canonical(intent.model_dump(by_alias=True)) + b"\n"
            )
        result, head = "PARTIAL", None
        if operation == "refresh":
            if previous.head is not None:
                verify_checkpoint_head(
                    previous.head, public_keys, str(context.workspace_id)
                )
            record = previous
        else:
            if operation == "publish":
                try:
                    head = load_private(head_path)
                    verified = verify_checkpoint_head(
                        head, public_keys, str(context.workspace_id)
                    )
                    captured = timestamp(verified.captured_at)
                    if (
                        verified.scope.generation_id != str(context.generation_id)
                        or verified.scope.policy_digest != context.policy.digest()
                        or not -timedelta(seconds=30)
                        <= now - captured
                        <= timedelta(minutes=context.policy.rpo_minutes, seconds=30)
                        or verified.checkpoint_digest
                        != checkpoint_hash(checkpoint_path)
                    ):
                        raise ValueError("checkpoint identity mismatch")
                    if previous:
                        if previous.result != "PASS" and captured <= timestamp(
                            previous.recorded_at
                        ):
                            raise ValueError("new capture required after failure")
                        if previous.head:
                            before = timestamp(previous.head["payload"]["capturedAt"])
                            if captured < before or (
                                captured == before
                                and canonical(previous.head) != canonical(head)
                            ):
                                raise ValueError("checkpoint capture moved backwards")
                    result = "PASS"
                except OSError, ValueError, TypeError, KeyError, RecursionError:
                    # Valid authority/CAS but invalid source: append FAIL, never revive old success.
                    result, head = "FAIL", None
            elif not recovering:
                raise ValueError("unknown catalog operation")
            record = CatalogRecord(
                sequence=sequence,
                workspaceId=str(context.workspace_id),
                generationId=str(context.generation_id),
                policyDigest=context.policy.digest(),
                codeRevision=context.code_revision,
                dbRevision=context.db_revision,
                recordedAt=now.isoformat(),
                result=result,
                head=head,
            )
        catalog = Catalog(
            version=1,
            kind="CHECKPOINT_CATALOG",
            catalogId=catalog_id,
            revision=revision,
            publishedAt=now.isoformat(),
            records=[record],
            signerKeyId=signer_id,
        )
        return commit(root, path, catalog, signer, pin)


def managed_read(path, *, public_keys, workspace_id, now):
    """Read a fixed operator pin; pending/newer uncommitted data closes the gate."""
    path = Path(path)
    if path.name != PIN:
        raise ValueError("fixed managed pin required")
    with directory(path.parent) as root:
        catalog, pin, _ = current(
            root, path.parent, public_keys=public_keys, workspace_id=workspace_id
        )
        if catalog is None or not -timedelta(seconds=30) <= now - timestamp(
            catalog.published_at
        ) <= timedelta(minutes=15):
            raise ValueError("current fresh catalog required")
        # Recheck inventory and pin after verification; never fall back during a write.
        names, highest = inventory(root)
        raw_pin = read_fd(root, PIN, 8192)
        if PENDING in names or highest != catalog.revision or digest(raw_pin) != pin:
            raise ValueError("catalog changed during read")
        config = CatalogConfig.model_validate(
            json.loads(raw_pin, object_pairs_hook=_object)
        )
        return catalog, config.digest
