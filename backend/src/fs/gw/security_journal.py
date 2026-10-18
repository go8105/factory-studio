"""GW-owned connection/role change intents, persisted before transaction commit."""

import os

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from fs.common.errors import ApiError
from fs.core.backup import BackupError, private_file
from fs.core.security.journal import append


def confirmation(c, ctx, digest, operation):
    from fs.gw.service import audit

    audit(
        c,
        ctx,
        "security",
        digest,
        "journal-confirmation",
        {},
        entity_kind="gw.security_journal",
        summary={"generationId": str(ctx.generation_id), "operation": operation},
    )


def acl_snapshot(c, ctx):
    from fs.gw.backup import capture

    return capture(c, scope=(ctx.workspace_id, ctx.generation_id))


def record(c, ctx, operation, *, include_acl=False):
    directory = os.environ.get("FS_GW_IDENTITY_JOURNAL_DIR")
    key_path = os.environ.get("FS_GW_IDENTITY_JOURNAL_KEY_FILE")
    if not directory and not key_path:
        return  # Unconfigured environments remain explicitly unverified.
    try:
        if not directory or not key_path:
            raise BackupError("보안 변경 기록 설정이 불완전합니다.")
        key = private_file(key_path, size=32).read_bytes()
        fields = {
            "person": "id,is_active,organization_unit_id",
            "person_identity_binding": "id,person_id,user_id,state",
            "role_grant": "id,person_id,role_key,is_active",
        }
        snapshot = {
            table: [
                dict(row)
                for row in c.execute(
                    text(
                        f"SELECT {columns} FROM gw.{table} WHERE workspace_id=:w "
                        "AND generation_id=:g ORDER BY id"
                    ),
                    {"w": ctx.workspace_id, "g": ctx.generation_id},
                ).mappings()
            ]
            for table, columns in fields.items()
        }
        if include_acl:
            snapshot["acl"] = acl_snapshot(c, ctx)
        digest = append(
            directory,
            key,
            {
                "coverage": "gw.company.intent.v2",
                "workspaceId": ctx.workspace_id,
                "generationId": ctx.generation_id,
                "operation": operation,
                "snapshot": snapshot,
            },
        )
        confirmation(c, ctx, digest, operation)
    except BackupError, OSError, ValueError, TypeError, SQLAlchemyError:
        raise ApiError(
            503,
            "SECURITY_JOURNAL_UNAVAILABLE",
            "보안 변경 기록을 저장하지 못해 변경을 적용하지 않았습니다. 운영 담당자에게 문의하세요.",
        ) from None


def confirm_records(c, records):
    """Read-only exact digest matching. No grants or restore readiness decision."""
    digests = [r["digest"] for r in records]
    matches = set()
    if digests:
        for row in c.execute(
            text(
                "SELECT workspace_id,entity_key,summary FROM core.audit_event "
                "WHERE entity_kind='gw.security_journal' AND action='gw.security.journal-confirmation' "
                "AND entity_key=ANY(:digests)"
            ),
            {"digests": digests},
        ).mappings():
            if not isinstance(row["summary"], dict):
                continue
            matches.add(
                (
                    str(row["workspace_id"]),
                    row["entity_key"],
                    row["summary"].get("generationId"),
                    row["summary"].get("operation"),
                )
            )
    legacy = matched = 0
    for record in records:
        payload = record["payload"]
        if payload["coverage"] != "gw.company.intent.v2":
            legacy += 1
            continue
        if (
            str(payload["workspaceId"]),
            record["digest"],
            str(payload["generationId"]),
            payload["operation"],
        ) in matches:
            matched += 1
    return {
        "matchedRecords": matched,
        "legacyRecords": legacy,
        "unconfirmedRecords": len(records) - matched,
        "commitsConfirmed": bool(records) and matched == len(records),
        "completenessConfirmed": False,
    }
