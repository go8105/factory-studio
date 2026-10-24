"""Read an operator-pinned signed catalog; never claim physical storage independence."""

import base64
import hashlib
import json
import os
import stat
from datetime import timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import Field, model_validator
from sqlalchemy import text

from fs.common.errors import ApiError
from fs.gw.evidence_trust import EvidenceTrust, authorize
from fs.gw.operating_contract import StrictModel, canonical, evidence_error, timestamp

ENV = "FS_GW_CHECKPOINT_CATALOG"
DOMAIN = b"FS-GW-CHECKPOINT-CATALOG-v1\0"
MAX_BYTES = 2 * 1024 * 1024


def uuid4(value):
    parsed = UUID(value)
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("invalid catalog identity")
    return value


class Versioned(StrictModel):
    version: Literal[1]

    @model_validator(mode="before")
    @classmethod
    def integer_version(cls, value):
        if isinstance(value, dict) and type(value.get("version")) is not int:
            raise ValueError("invalid catalog version")
        return value


class CatalogConfig(Versioned):
    provider: Literal["SIGNED_SNAPSHOT_FILE"]
    catalog_id: str = Field(alias="catalogId")
    file: str = Field(min_length=1, max_length=4096)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def identity_and_path(self):
        uuid4(self.catalog_id)
        if not Path(self.file).is_absolute():
            raise ValueError("absolute catalog path required")
        return self


class CatalogRecord(StrictModel):
    sequence: int = Field(ge=1, le=9223372036854775807)
    workspace_id: str = Field(alias="workspaceId", pattern=r"^[1-9][0-9]{0,18}$")
    generation_id: str = Field(alias="generationId", pattern=r"^[1-9][0-9]{0,18}$")
    policy_digest: str = Field(alias="policyDigest", pattern=r"^[0-9a-f]{64}$")
    code_revision: str = Field(alias="codeRevision", pattern=r"^[0-9a-f]{7,64}$")
    db_revision: str = Field(alias="dbRevision", pattern=r"^[A-Za-z0-9_]{1,100}$")
    recorded_at: str = Field(alias="recordedAt")
    result: Literal["PASS", "PARTIAL", "FAIL"]
    head: dict | None

    @model_validator(mode="after")
    def scoped_head(self):
        from fs.gw.restore_recheck import CheckpointHeadDocument

        timestamp(self.recorded_at)
        if self.head is not None:
            head = CheckpointHeadDocument.model_validate(self.head).payload
            if (
                head.scope.workspace_id != self.workspace_id
                or head.scope.generation_id != self.generation_id
                or head.scope.policy_digest != self.policy_digest
                or timestamp(head.captured_at)
                > timestamp(self.recorded_at) + timedelta(seconds=30)
            ):
                raise ValueError("catalog record and head differ")
        return self


class Catalog(Versioned):
    kind: Literal["CHECKPOINT_CATALOG"]
    catalog_id: str = Field(alias="catalogId")
    revision: int = Field(ge=1, le=9223372036854775807)
    published_at: str = Field(alias="publishedAt")
    records: list[CatalogRecord] = Field(max_length=1000)
    signer_key_id: str = Field(alias="signerKeyId", pattern=r"^[A-Za-z0-9_-]{1,60}$")

    @model_validator(mode="after")
    def ordered_records(self):
        uuid4(self.catalog_id)
        published = timestamp(self.published_at)
        numbers = [record.sequence for record in self.records]
        if len(set(numbers)) != len(numbers) or any(
            timestamp(record.recorded_at) > published + timedelta(seconds=30)
            for record in self.records
        ):
            raise ValueError("duplicate sequence or future catalog record")
        return self


class RecoveryCatalog(Catalog):
    version: Literal[2]
    recovery_proof: dict = Field(alias="recoveryProof")


class CatalogDocument(StrictModel):
    envelope: Catalog | RecoveryCatalog
    signature: str = Field(max_length=100)


class CatalogObservation(Versioned):
    scope: Literal["CONFIGURED_SIGNED_CHECKPOINT_CATALOG"]
    catalog_id: str = Field(alias="catalogId")
    catalog_revision: int = Field(alias="catalogRevision", ge=1, le=9223372036854775807)
    catalog_digest: str = Field(alias="catalogDigest", pattern=r"^[0-9a-f]{64}$")
    published_at: str = Field(alias="publishedAt")
    observed_at: str = Field(alias="observedAt")
    latest_sequence: int | None = Field(
        alias="latestSequence", ge=1, le=9223372036854775807
    )
    latest_record_result: Literal["PASS", "PARTIAL", "FAIL"] | None = Field(
        alias="latestRecordResult"
    )
    latest_head_digest: str | None = Field(
        alias="latestHeadDigest", pattern=r"^[0-9a-f]{64}$"
    )
    latest_captured_at: str | None = Field(alias="latestCapturedAt")
    reason: Literal[
        "MATCH",
        "HEAD_MISMATCH",
        "LATEST_FAIL",
        "LATEST_PARTIAL",
        "ORIGINAL_MISSING",
        "SCOPE_MISSING",
        "CONTEXT_MISMATCH",
    ]
    result: Literal["PARTIAL", "BLOCKED"]
    catalog_signature_verified: Literal[True] = Field(alias="catalogSignatureVerified")
    external_independence_verified: Literal[False] = Field(
        alias="externalIndependenceVerified"
    )

    @model_validator(mode="before")
    @classmethod
    def exact_flags(cls, value):
        if isinstance(value, dict):
            for alias, name in (
                ("catalogSignatureVerified", "catalog_signature_verified"),
                ("externalIndependenceVerified", "external_independence_verified"),
            ):
                if type(value.get(alias, value.get(name))) is not bool:
                    raise ValueError("invalid catalog observation flag")
        return value

    @model_validator(mode="after")
    def bounded_result(self):
        uuid4(self.catalog_id)
        for value in (self.published_at, self.observed_at):
            timestamp(value)
        if self.latest_captured_at is not None:
            timestamp(self.latest_captured_at)
        if (self.latest_head_digest is None) != (self.latest_captured_at is None):
            raise ValueError("catalog capture metadata mismatch")
        if self.result != ("PARTIAL" if self.reason == "MATCH" else "BLOCKED"):
            raise ValueError("catalog observation result mismatch")
        if self.reason == "SCOPE_MISSING":
            if any(
                value is not None
                for value in (
                    self.latest_sequence,
                    self.latest_record_result,
                    self.latest_head_digest,
                    self.latest_captured_at,
                )
            ):
                raise ValueError("missing catalog record cannot be inferred")
        elif self.latest_sequence is None or self.latest_record_result is None:
            raise ValueError("catalog record metadata required")
        if self.reason in {"MATCH", "HEAD_MISMATCH", "CONTEXT_MISMATCH"} and (
            self.latest_record_result != "PASS" or self.latest_head_digest is None
        ):
            raise ValueError("catalog head metadata required")
        if self.reason == "ORIGINAL_MISSING" and (
            self.latest_record_result != "PASS" or self.latest_head_digest is not None
        ):
            raise ValueError("missing catalog original mismatch")
        if (self.reason == "LATEST_FAIL" and self.latest_record_result != "FAIL") or (
            self.reason == "LATEST_PARTIAL" and self.latest_record_result != "PARTIAL"
        ):
            raise ValueError("latest catalog result mismatch")
        return self


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate catalog field")
        result[key] = value
    return result


def configured():
    # An explicitly empty configuration is an error, never disabled mode.
    return ENV in os.environ or "FS_GW_CHECKPOINT_CATALOG_PIN_FILE" in os.environ


def read(*, public_keys, workspace_id, now):
    """Read one bounded descriptor snapshot, not a path supplied by an upload."""
    try:
        from fs.gw.catalog_store import PIN_ENV, managed_read

        if PIN_ENV in os.environ:
            if ENV in os.environ:
                raise ValueError("ambiguous catalog configuration")
            return managed_read(
                os.environ[PIN_ENV],
                public_keys=public_keys,
                workspace_id=workspace_id,
                now=now,
            )
        raw_config = os.environ[ENV]
        if len(raw_config.encode()) > 8192:
            raise ValueError()
        config = CatalogConfig.model_validate(
            json.loads(raw_config, object_pairs_hook=_object)
        )
        path = Path(config.file)
        parent = path.parent.lstat()
        if (
            not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.geteuid()
            or parent.st_mode & 0o077
        ):
            raise ValueError()
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o077
                or not 0 < info.st_size <= MAX_BYTES
            ):
                raise ValueError()
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != config.digest:
            raise ValueError()
        catalog = verify_document(
            raw, config, public_keys=public_keys, workspace_id=workspace_id
        )
        if (
            not -timedelta(seconds=30)
            <= now - timestamp(catalog.published_at)
            <= timedelta(minutes=15)
        ):
            raise ValueError()
        return catalog, config.digest
    except OSError, KeyError, TypeError, ValueError, InvalidSignature, RecursionError:
        raise ValueError(
            "configured checkpoint catalog unavailable or invalid"
        ) from None


def verify_document(raw, config, *, public_keys, workspace_id):
    """Verify archived bytes without requiring a fresh publication time."""
    if (
        not 0 < len(raw) <= MAX_BYTES
        or hashlib.sha256(raw).hexdigest() != config.digest
    ):
        raise ValueError("catalog bytes differ from pin")
    document = CatalogDocument.model_validate(
        json.loads(raw, object_pairs_hook=_object)
    )
    catalog = document.envelope
    if not isinstance(public_keys, EvidenceTrust) or not public_keys.scoped:
        raise ValueError("scoped catalog authority required")
    authorize(
        public_keys, catalog.signer_key_id, "CHECKPOINT_CATALOG", str(workspace_id)
    )
    Ed25519PublicKey.from_public_bytes(public_keys[catalog.signer_key_id]).verify(
        base64.b64decode(document.signature, validate=True),
        DOMAIN + canonical(catalog.model_dump(by_alias=True)),
    )
    if catalog.catalog_id != config.catalog_id:
        raise ValueError("catalog identity differs from pin")
    if isinstance(catalog, RecoveryCatalog):
        from fs.gw.catalog_recovery import verify as verify_recovery

        verify_recovery(catalog, public_keys=public_keys, workspace_id=workspace_id)
    return catalog


def observe(selected_head, *, observed_at, **context):
    catalog, digest = read(
        **{key: context[key] for key in ("public_keys", "workspace_id", "now")}
    )
    if timestamp(catalog.published_at) > timestamp(observed_at) + timedelta(seconds=30):
        raise ValueError("catalog published after observation")
    candidates = [
        r
        for r in catalog.records
        if r.workspace_id == str(context["workspace_id"])
        and r.generation_id == str(context["generation_id"])
    ]
    # All policies, versions, results and missing originals; never search for PASS.
    latest = max(candidates, key=lambda r: r.sequence) if candidates else None
    reason = "SCOPE_MISSING"
    head_digest = None
    captured_at = None
    if latest is not None:
        if latest.head is not None:
            from fs.gw.restore_recheck import verify_checkpoint_head

            verify_checkpoint_head(
                latest.head, context["public_keys"], str(context["workspace_id"])
            )
            head_digest = hashlib.sha256(canonical(latest.head)).hexdigest()
            captured_at = latest.head["payload"]["capturedAt"]
        reason = (
            "LATEST_FAIL"
            if latest.result == "FAIL"
            else "LATEST_PARTIAL"
            if latest.result == "PARTIAL"
            else "ORIGINAL_MISSING"
            if latest.head is None
            else "CONTEXT_MISMATCH"
            if (
                latest.policy_digest != context["policy"].digest()
                or latest.code_revision != context["code_revision"]
                or latest.db_revision != context["db_revision"]
            )
            else "HEAD_MISMATCH"
            if canonical(latest.head) != canonical(selected_head)
            else "MATCH"
        )
    return CatalogObservation.model_validate(
        {
            "version": 1,
            "scope": "CONFIGURED_SIGNED_CHECKPOINT_CATALOG",
            "catalogId": catalog.catalog_id,
            "catalogRevision": catalog.revision,
            "catalogDigest": digest,
            "publishedAt": catalog.published_at,
            "observedAt": observed_at,
            "latestSequence": latest.sequence if latest else None,
            "latestRecordResult": latest.result if latest else None,
            "latestHeadDigest": head_digest,
            "latestCapturedAt": captured_at,
            "reason": reason,
            "result": "PARTIAL" if reason == "MATCH" else "BLOCKED",
            "catalogSignatureVerified": True,
            "externalIndependenceVerified": False,
        }
    ).model_dump(by_alias=True)


def require_history(connection, data, *, workspace_id, generation_id):
    """Retained observations provide a floor even after a pin/config rollback."""
    diagnostic = data.metrics.acceptance_diagnostics
    recheck = getattr(diagnostic, "restore_recheck", None)
    current = recheck.envelope.get("catalogObservation") if recheck else None
    history = (
        connection.execute(
            text("""SELECT metrics->'acceptanceDiagnostics'->'restoreRecheck'->'envelope'->'catalogObservation' AS observation,result,recorded_at
        FROM gw.operating_evidence WHERE workspace_id=:w AND generation_id=:g AND kind='ACCEPTANCE'
        AND metrics->'acceptanceDiagnostics'->'restoreRecheck'->'envelope'->>'version'='4'"""),
            {"w": workspace_id, "g": generation_id},
        )
        .mappings()
        .all()
    )
    if (configured() or history) and current is None:
        raise evidence_error()
    if current is None:
        return
    candidate = CatalogObservation.model_validate(current)
    for row in history:
        try:
            old = CatalogObservation.model_validate(row["observation"])
        except ValueError, TypeError:
            raise evidence_error() from None
        if (
            candidate.catalog_id != old.catalog_id
            or candidate.catalog_revision < old.catalog_revision
            or (
                candidate.catalog_revision == old.catalog_revision
                and candidate.catalog_digest != old.catalog_digest
            )
            or (
                candidate.latest_sequence is not None
                and candidate.latest_sequence == old.latest_sequence
                and (
                    candidate.latest_head_digest != old.latest_head_digest
                    or candidate.latest_record_result != old.latest_record_result
                )
            )
            or (
                old.latest_sequence is not None
                and (
                    candidate.latest_sequence is None
                    or candidate.latest_sequence < old.latest_sequence
                )
                and data.result != "FAIL"
            )
            or (
                candidate.latest_sequence is not None
                and old.latest_sequence is not None
                and candidate.latest_sequence < old.latest_sequence
            )
            or (
                data.result == "PARTIAL"
                and old.latest_captured_at is not None
                and (
                    candidate.latest_captured_at is None
                    or timestamp(candidate.latest_captured_at)
                    < timestamp(old.latest_captured_at)
                    or (
                        timestamp(candidate.latest_captured_at)
                        == timestamp(old.latest_captured_at)
                        and candidate.latest_head_digest != old.latest_head_digest
                    )
                )
            )
        ):
            raise evidence_error()
        if (
            data.result == "PARTIAL"
            and row.get("result") == "FAIL"
            and old.reason != "MATCH"
            and (
                candidate.latest_captured_at is None
                or timestamp(candidate.latest_captured_at) <= row["recorded_at"]
            )
        ):
            raise ApiError(
                400,
                "OPERATING_RECOVERY_REQUIRED",
                "목록 대조 미통과 등록 이후 새 권한 대조와 격리 복원을 실행·등록하고 다시 관측하세요.",
                {"nextStep": "NEW_RESTORE_REQUIRED"},
            )
