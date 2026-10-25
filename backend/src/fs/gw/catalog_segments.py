"""Bounded file segments with one trusted final anchor and no intermediate activation."""

import base64
import json
import os
import re
import stat
from datetime import timedelta
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from fs.gw import catalog_recovery as recovery
from fs.gw import catalog_store as store
from fs.gw import catalog_transfer as transfer
from fs.gw.checkpoint_catalog import RecoveryCatalog, Versioned, _object
from fs.gw.checkpoint_catalog import uuid4 as catalog_id
from fs.gw.operating_contract import canonical, timestamp

MAX_PARTS = 8192
MAX_PLAN = 2 * 1024 * 1024


class Entry(Versioned):
    kind: Literal["SNAPSHOT", "ARTIFACT"]
    revision: int = Field(ge=1, le=9223372036854775807)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_digest: str = Field(alias="actualDigest", pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0, le=store.MAX_BYTES)


class Plan(Versioned):
    kind: Literal["CHECKPOINT_CATALOG_SEGMENTS"]
    catalog_id: str = Field(alias="catalogId")
    workspace_id: str = Field(alias="workspaceId", pattern=r"^[1-9][0-9]{0,18}$")
    generation_id: str = Field(alias="generationId", pattern=r"^[1-9][0-9]{0,18}$")
    base_revision: int = Field(alias="baseRevision", ge=0, le=9223372036854775807)
    base_digest: str = Field(alias="baseDigest", pattern=r"^(ABSENT|[0-9a-f]{64})$")
    target_revision: int = Field(alias="targetRevision", ge=1, le=9223372036854775807)
    target_digest: str = Field(alias="targetDigest", pattern=r"^[0-9a-f]{64}$")
    parts: list[Entry] = Field(min_length=1, max_length=MAX_PARTS)

    @model_validator(mode="after")
    def coherent(self):
        catalog_id(self.catalog_id)
        if (
            (self.base_revision == 0) != (self.base_digest == "ABSENT")
            or self.base_revision >= self.target_revision
            or len({p.revision for p in self.parts}) != len(self.parts)
            or self.parts[0].kind != "SNAPSHOT"
            or self.parts[0].revision != self.target_revision
            or self.parts[0].digest != self.target_digest
            or any(p.revision > self.target_revision for p in self.parts)
            or any(p.revision < max(1, self.base_revision) for p in self.parts)
            or any(
                p.kind == "SNAPSHOT" and (p.digest != p.actual_digest or not p.size)
                for p in self.parts
            )
        ):
            raise ValueError("segment plan inconsistent")
        return self


class Intent(Versioned):
    kind: Literal["CATALOG_SEGMENTS_PENDING"]
    plan_digest: str = Field(alias="planDigest", pattern=r"^[0-9a-f]{64}$")
    catalog_id: str = Field(alias="catalogId")
    workspace_id: str = Field(alias="workspaceId")
    generation_id: str = Field(alias="generationId")
    base_pin_digest: str = Field(
        alias="basePinDigest", pattern=r"^(ABSENT|[0-9a-f]{64})$"
    )
    base_revision: int = Field(alias="baseRevision", ge=0, le=9223372036854775807)
    base_digest: str = Field(alias="baseDigest", pattern=r"^(ABSENT|[0-9a-f]{64})$")


def entry(kind, revision, sha, raw):
    return Entry(
        version=1,
        kind=kind,
        revision=revision,
        digest=sha,
        actualDigest=store.digest(raw),
        size=len(raw),
    )


def walk(
    root,
    *,
    identity,
    context,
    public_keys,
    target_revision,
    target_digest,
    base_revision,
    base_digest,
):
    """Validate backwards with constant raw-file memory, including every recovery original."""
    names, _ = store.inventory(root)
    indexed = {
        int(m[1]): (name, m[2]) for name in names if (m := store.NAME.fullmatch(name))
    }
    revision, after, count = target_revision, None, 0
    while revision:
        name, sha = indexed[revision]
        raw = store.read_fd(root, name)
        if revision == target_revision and sha != target_digest:
            raise ValueError("final anchor differs")
        snapshot = transfer.Snapshot(
            version=1,
            revision=revision,
            digest=sha,
            content=base64.b64encode(raw).decode(),
        )
        catalog, _ = transfer.decode_snapshot(
            snapshot,
            identity,
            context=context,
            public_keys=public_keys,
            historical=revision != target_revision,
        )
        if after is not None:
            transfer.transition(catalog, after, sha)
        count += 1
        if count > MAX_PARTS:
            raise ValueError("segmented history limit")
        yield entry("SNAPSHOT", revision, sha, raw), raw
        if revision == base_revision:
            if sha != base_digest:
                raise ValueError("receiver base differs")
            return
        if (
            isinstance(catalog, RecoveryCatalog)
            and revision == catalog.recovery_proof["envelope"]["targetRevision"]
        ):
            proof = recovery.Proof.model_validate(catalog.recovery_proof).envelope
            previous = proof.base_revision
            if previous < base_revision:
                raise ValueError("receiver base inside unresolved interval")
            for slot in proof.slots:
                if slot.actual_digest is None:
                    if slot.revision in indexed:
                        raise ValueError("absent original appeared")
                    continue
                gap_name, expected = indexed[slot.revision]
                data = store.read_fd(root, gap_name, allow_empty=True)
                if (
                    expected != slot.expected_digest
                    or len(data) != slot.size
                    or store.digest(data) != slot.actual_digest
                ):
                    raise ValueError("interrupted original differs")
                count += 1
                if count > MAX_PARTS:
                    raise ValueError("segmented history limit")
                yield entry("ARTIFACT", slot.revision, expected, data), data
            if not previous:
                recovery.bridge(None, catalog, "ABSENT")
                return
        else:
            previous = revision - 1
            if not previous:
                if revision != 1 or catalog.records[0].sequence != 1 or base_revision:
                    raise ValueError("initial history missing")
                return
        revision, after = previous, catalog
    raise ValueError("history base missing")


def arguments(plan, context, public_keys):
    return {
        "identity": plan.catalog_id,
        "context": context,
        "public_keys": public_keys,
        "target_revision": plan.target_revision,
        "target_digest": plan.target_digest,
        "base_revision": plan.base_revision,
        "base_digest": plan.base_digest,
    }


def export(path, output, *, context, public_keys, now, base_revision, base_digest):
    """Write an empty private package folder; manifest is published only after validation."""
    if Path(path).resolve() == Path(output).resolve():
        raise ValueError("separate package directory required")
    with (
        store.directory(path) as root,
        store.locked(root),
        store.directory(output) as dest,
    ):
        # Retry a failed export into a NEW folder; partial output has no final manifest anchor.
        if any(Path(output).iterdir()):
            raise ValueError("empty package directory required")
        catalog, pin, _ = store.current(
            root, path, public_keys=public_keys, workspace_id=context.workspace_id
        )
        if catalog is None or not 0 <= base_revision < catalog.revision:
            raise ValueError("current source and older base required")
        age = now - timestamp(catalog.published_at)
        if not -timedelta(seconds=30) <= age <= timedelta(minutes=15):
            raise ValueError("fresh source required")
        config = store.CatalogConfig.model_validate(
            json.loads(store.read_fd(root, store.PIN), object_pairs_hook=_object)
        )
        parts = []
        for index, (item, raw) in enumerate(
            walk(
                root,
                identity=catalog.catalog_id,
                context=context,
                public_keys=public_keys,
                target_revision=catalog.revision,
                target_digest=config.digest,
                base_revision=base_revision,
                base_digest=base_digest,
            ),
            1,
        ):
            store.write_new(dest, f"part-{index:05d}.bin", raw)
            parts.append(item)
        plan = Plan(
            version=1,
            kind="CHECKPOINT_CATALOG_SEGMENTS",
            catalogId=catalog.catalog_id,
            workspaceId=str(context.workspace_id),
            generationId=str(context.generation_id),
            baseRevision=base_revision,
            baseDigest=base_digest,
            targetRevision=catalog.revision,
            targetDigest=config.digest,
            parts=parts,
        )
        raw = canonical(plan.model_dump(by_alias=True)) + b"\n"
        if len(raw) > MAX_PLAN:
            raise ValueError("manifest limit")
        store.cas(root, pin)
        store.write_new(dest, "manifest.json", raw)
        return {
            "catalogId": catalog.catalog_id,
            "manifestDigest": store.digest(raw),
            "targetRevision": catalog.revision,
            "targetCatalogDigest": config.digest,
            "parts": len(parts),
            "ready": False,
        }


def parse(raw, expected_digest, identity, context):
    if not 0 < len(raw) <= MAX_PLAN or store.digest(raw) != expected_digest:
        raise ValueError("manifest differs from operator anchor")
    plan = Plan.model_validate(json.loads(raw, object_pairs_hook=_object))
    if (
        plan.catalog_id != identity
        or plan.workspace_id != str(context.workspace_id)
        or plan.generation_id != str(context.generation_id)
    ):
        raise ValueError("manifest scope differs")
    return plan


def progress(root, plan, *, repair=True):
    names, highest = store.inventory(root)
    indexed = {int(m[1]): name for name in names if (m := store.NAME.fullmatch(name))}
    if highest > plan.target_revision:
        raise ValueError("newer receiver history exists")
    done = 0
    gap = False
    wanted = {p.revision for p in plan.parts}
    if any(r > plan.base_revision and r not in wanted for r in indexed):
        raise ValueError("unexpected receiver history")
    for item in plan.parts:
        name = store.filename(item.revision, item.digest)
        if item.revision in indexed:
            if indexed[item.revision] != name:
                raise ValueError("retained revision fork")
            info = os.stat(name, dir_fd=root, follow_symlinks=False)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o077
                or info.st_size != item.size
                or info.st_nlink not in ({1, 2} if repair else {1})
            ):
                raise ValueError("invalid retained part")
            if info.st_nlink == 2:
                data = store.read_fd(
                    root, name, max_links=2, allow_empty=item.size == 0
                )
                if store.digest(data) != item.actual_digest:
                    raise ValueError("interrupted part changed")
                transfer.put_snapshot(root, name, data)
            if not gap:
                done += 1
        else:
            gap = True
    return done


def receive(
    path,
    raw,
    *,
    context,
    public_keys,
    now,
    expected_manifest_digest,
    expected_catalog_id,
    expected_pin_digest,
    initialize=False,
    resume=False,
    part_number=None,
    part_raw=None,
    status=False,
):
    """Fence before parsing, recover progress from immutable originals, activate ONLY at final."""
    catalog_id(expected_catalog_id)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_manifest_digest):
        raise ValueError("invalid operator manifest anchor")
    with store.directory(path) as root, store.locked(root):
        names, _ = store.inventory(root)
        pending = store.PENDING in names
        old, pin, _ = store.current(
            root,
            path,
            public_keys=public_keys,
            workspace_id=context.workspace_id,
            healthy=not pending,
            historical=True,
        )
        store.cas(root, expected_pin_digest)
        store.check_scope(old, context)
        if old and (
            store.RECEIVER not in names or old.catalog_id != expected_catalog_id
        ):
            raise ValueError("receiver role differs")
        if status and (initialize or part_number is not None):
            raise ValueError("status cannot mutate a session")
        intent = None
        if pending:
            if not (resume or status) or initialize:
                raise ValueError("explicit same-plan resume required")
            intent = Intent.model_validate(
                json.loads(
                    store.read_fd(root, store.PENDING, 8192), object_pairs_hook=_object
                )
            )
            if (
                intent.plan_digest,
                intent.catalog_id,
                intent.workspace_id,
                intent.generation_id,
            ) != (
                expected_manifest_digest,
                expected_catalog_id,
                str(context.workspace_id),
                str(context.generation_id),
            ):
                raise ValueError("pending plan differs")
        elif resume or status:
            if old is None or initialize:
                raise ValueError("no matching completed session")
        elif old is None:
            if not initialize or pin != "ABSENT" or set(names) != {store.LOCK}:
                raise ValueError("explicit empty receiver required")
        elif initialize:
            raise ValueError("already initialized")
        if not pending and not resume and not status:
            base_digest = "ABSENT"
            if old:
                base_digest = store.CatalogConfig.model_validate(
                    json.loads(
                        store.read_fd(root, store.PIN), object_pairs_hook=_object
                    )
                ).digest
            intent = Intent(
                version=1,
                kind="CATALOG_SEGMENTS_PENDING",
                planDigest=expected_manifest_digest,
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
        plan = parse(raw, expected_manifest_digest, expected_catalog_id, context)
        if intent and (
            intent.base_revision != plan.base_revision
            or intent.base_digest != plan.base_digest
        ):
            raise ValueError("manifest does not start at fenced base")
        completed = old is not None and old.revision == plan.target_revision
        if completed:
            config = store.CatalogConfig.model_validate(
                json.loads(store.read_fd(root, store.PIN), object_pairs_hook=_object)
            )
            if config.digest != plan.target_digest:
                raise ValueError("completed target fork")
        elif (
            intent is None
            or pin != intent.base_pin_digest
            or (old.revision if old else 0) != plan.base_revision
        ):
            raise ValueError("receiver base changed")
        plan_name = f".catalog-plan-{expected_manifest_digest}.json"
        if not pending and (resume or status) and plan_name not in names:
            raise ValueError("no matching retained manifest")
        if status:
            if store.read_fd(root, plan_name, MAX_PLAN) != raw:
                raise ValueError("retained manifest differs")
        else:
            transfer.put_snapshot(root, plan_name, raw)
            if store.RECEIVER not in names or (intent and intent.base_revision == 0):
                identity = transfer.Identity(
                    version=1,
                    kind="CATALOG_RECEIVER",
                    catalogId=plan.catalog_id,
                    workspaceId=plan.workspace_id,
                    generationId=plan.generation_id,
                    bootstrapDigest=expected_manifest_digest,
                )
                transfer.put_snapshot(
                    root,
                    store.RECEIVER,
                    canonical(identity.model_dump(by_alias=True)) + b"\n",
                )
        done = progress(root, plan, repair=not status)
        if part_number is not None:
            if type(part_number) is not int or not 1 <= part_number <= min(
                done + 1, len(plan.parts)
            ):
                raise ValueError("next part or exact replay required")
            item = plan.parts[part_number - 1]
            if (
                part_raw is None
                or len(part_raw) != item.size
                or store.digest(part_raw) != item.actual_digest
            ):
                raise ValueError("part bytes differ")
            if item.kind == "SNAPSHOT":
                transfer.decode_snapshot(
                    transfer.Snapshot(
                        version=1,
                        revision=item.revision,
                        digest=item.digest,
                        content=base64.b64encode(part_raw).decode(),
                    ),
                    plan.catalog_id,
                    context=context,
                    public_keys=public_keys,
                    historical=item.revision != plan.target_revision,
                )
            transfer.put_snapshot(
                root, store.filename(item.revision, item.digest), part_raw
            )
            done = progress(root, plan, repair=not status)
        report = {
            "catalogId": plan.catalog_id,
            "manifestDigest": expected_manifest_digest,
            "targetRevision": plan.target_revision,
            "receivedParts": done,
            "totalParts": len(plan.parts),
            "nextPart": done + 1 if done < len(plan.parts) else None,
            "state": "RECEIVING",
            "pinDigest": pin,
            "ready": False,
        }
        if done < len(plan.parts):
            return report
        # Re-read ALL originals and CURRENT key authority; never trust a saved progress number.
        checked = 0
        for checked, (item, _) in enumerate(
            walk(root, **arguments(plan, context, public_keys)), 1
        ):
            if checked > len(plan.parts) or item != plan.parts[checked - 1]:
                raise ValueError("manifest is not exact signed history")
        if checked != len(plan.parts):
            raise ValueError("extra manifest originals")
        data = store.read_fd(
            root, store.filename(plan.target_revision, plan.target_digest)
        )
        target, _ = transfer.decode_snapshot(
            transfer.Snapshot(
                version=1,
                revision=plan.target_revision,
                digest=plan.target_digest,
                content=base64.b64encode(data).decode(),
            ),
            plan.catalog_id,
            context=context,
            public_keys=public_keys,
        )
        age = now - timestamp(target.published_at)
        if age < -timedelta(seconds=30) or (
            age > timedelta(minutes=15) and not (resume or status)
        ):
            raise ValueError("fresh final target required")
        if status:
            report["state"] = "COMPLETE" if not pending else "AWAITING_FINALIZE"
        else:
            if store.PENDING in store.inventory(root)[0]:
                report.update(store.activate(root, path, target, data, pin))
            report["state"] = "COMPLETE"
        record = target.records[0]
        report.update(
            revision=target.revision,
            sequence=record.sequence,
            result=record.result,
            catalogDigest=plan.target_digest,
            targetFresh=age <= timedelta(minutes=15),
            contextMatches=(
                record.policy_digest == context.policy.digest()
                and record.code_revision == context.code_revision
                and record.db_revision == context.db_revision
            ),
        )
        if report["state"] != "COMPLETE":
            report["sourceResult"] = report.pop("result")
        return report
