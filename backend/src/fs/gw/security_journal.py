"""GW-owned connection/role change intents, persisted before transaction commit."""

import os

from sqlalchemy import text

from fs.common.errors import ApiError
from fs.core.backup import BackupError, private_file
from fs.core.security.journal import append


def record(c, ctx, operation):
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
        append(
            directory,
            key,
            {
                "coverage": "gw.company_identity.intent.v1",
                "workspaceId": ctx.workspace_id,
                "generationId": ctx.generation_id,
                "operation": operation,
                "snapshot": snapshot,
            },
        )
    except BackupError, OSError, ValueError, TypeError:
        raise ApiError(
            503,
            "SECURITY_JOURNAL_UNAVAILABLE",
            "보안 변경 기록을 저장하지 못해 변경을 적용하지 않았습니다. 운영 담당자에게 문의하세요.",
        ) from None
