#!/usr/bin/env python3
"""GW-COMPANY-02: 승인된 회사 보안 5표만 추가한다. 기존 제약 순번은 보존한다."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def apply(d):
    expected = {
        "gw." + n
        for n in (
            "collaboration_settings",
            "person_identity_binding",
            "role_grant",
            "document_reader",
            "step_assignment",
        )
    }
    present = expected & {t["name"] for t in d["tables"]}
    if present and present != expected:
        raise ValueError(
            "회사 GW 보안 명세가 일부만 존재합니다. 자동 보정하지 않습니다."
        )
    if present:
        return False

    def col(name, type="bigint", nullable=False, default=None):
        return {
            "name": name,
            "label": name,
            "type": type,
            "nullable": nullable,
            "default": default,
            "rule": "",
        }

    def constraint(table, kind, columns, expression=""):
        d["constraints"].append(
            {
                "table": table,
                "kind": kind,
                "columns": columns,
                "expression": expression,
                "reason": "GW-COMPANY-02 회사 범위·보안 무결성",
            }
        )

    def fk(table, columns, target, targets):
        d["relations"].append(
            {
                "source": table,
                "columns": columns,
                "target": target,
                "target_columns": targets,
                "on_delete": "RESTRICT",
                "on_update": "RESTRICT",
                "note": "회사 공간·세대 복합 참조",
            }
        )

    scope = ["workspace_id", "generation_id"]
    version = lambda: col("version", "integer", default="1")
    reason = lambda: col("reason", "varchar(500)")
    actor = lambda name: col(name)
    definitions = {
        "collaboration_settings": [
            col("authz_version", default="1"),
            actor("initialized_by_user_id"),
            col("initialized_at", "timestamptz", default="clock_timestamp()"),
        ],
        "person_identity_binding": [
            col("person_id"),
            col("user_id"),
            col("state", "varchar(12)"),
            version(),
            actor("requested_by_user_id"),
            col("activated_at", "timestamptz", True),
            col("closed_at", "timestamptz", True),
            col("reason", "varchar(500)", True),
        ],
        "role_grant": [
            col("person_id"),
            col("role_key", "varchar(30)"),
            col("is_active", "boolean", default="true"),
            version(),
            actor("changed_by_user_id"),
            reason(),
        ],
        "document_reader": [
            col("document_id"),
            col("person_id"),
            col("is_active", "boolean", default="true"),
            version(),
            actor("granted_by_user_id"),
            reason(),
        ],
        "step_assignment": [
            col("document_id"),
            col("step_id"),
            col("person_id"),
            col("assignment_seq", "integer"),
            reason(),
            actor("assigned_by_user_id"),
        ],
    }
    for name, columns in definitions.items():
        table = "gw." + name
        d["tables"].append(
            {
                "name": table,
                "label": name,
                "scope": "workspace_generation",
                "phase": "GW-COMPANY-02",
                "columns": [
                    col("id", default="GENERATED ALWAYS AS IDENTITY"),
                    col("workspace_id"),
                    col("generation_id"),
                    *columns,
                    col("created_at", "timestamptz", default="clock_timestamp()"),
                ],
                "note": "회사 GW 보안 원장. 인증 user_id는 검증된 식별자이며 core 업무 FK 없음",
                "retention": "회사 운영 보존 정책에 따라 관리·물리 삭제 UI 없음",
                "guest_cleanup": "공개 템플릿 0행·게스트 복사 금지",
            }
        )
        constraint(table, "PK", ["id"])
        constraint(table, "UK", scope + ["id"])
        constraint(table, "INDEX", scope)
        fk(table, ["workspace_id"], "core.workspace", ["id"])
        fk(table, scope, "core.data_generation", ["workspace_id", "id"])
        if name != "collaboration_settings":
            fk(table, scope + ["person_id"], "gw.person", scope + ["id"])
        if name in {"document_reader", "step_assignment"}:
            fk(table, scope + ["document_id"], "gw.approval_document", scope + ["id"])
        if any(c["name"] == "version" for c in columns):
            constraint(table, "CHECK", ["version"], "version>0")
        if name in {"role_grant", "document_reader", "step_assignment"}:
            constraint(
                table,
                "CHECK",
                ["reason"],
                "char_length(btrim(reason)) BETWEEN 2 AND 500",
            )
    constraint("gw.collaboration_settings", "UK", scope)
    constraint(
        "gw.collaboration_settings", "CHECK", ["authz_version"], "authz_version>0"
    )
    table = "gw.person_identity_binding"
    for key in ["person_id", "user_id"]:
        constraint(
            table, "UK_PARTIAL", scope + [key], "UNIQUE WHERE state<>'CANCELLED'"
        )
    constraint(
        table,
        "CHECK",
        ["state", "activated_at", "closed_at"],
        "(state='PENDING' AND activated_at IS NULL AND closed_at IS NULL) OR (state='ACTIVE' AND activated_at IS NOT NULL AND closed_at IS NULL) OR (state='SUSPENDED' AND activated_at IS NOT NULL AND closed_at IS NOT NULL AND closed_at>=activated_at) OR (state='CANCELLED' AND activated_at IS NULL AND closed_at IS NOT NULL)",
    )
    constraint(
        table,
        "CHECK",
        ["reason"],
        "reason IS NULL OR char_length(btrim(reason)) BETWEEN 2 AND 500",
    )
    constraint("gw.role_grant", "UK", scope + ["person_id", "role_key"])
    constraint(
        "gw.role_grant",
        "CHECK",
        ["role_key"],
        "role_key IN ('ORG_ADMIN','ROUTE_ADMIN','POLICY_ADMIN','BOARD_PUBLISHER','SECURITY_ADMIN','AUDITOR')",
    )
    constraint("gw.document_reader", "UK", scope + ["document_id", "person_id"])
    constraint("gw.document_reader", "INDEX", scope + ["person_id", "is_active"])
    constraint("gw.approval_step", "UK", scope + ["document_id", "id"])
    constraint("gw.step_assignment", "UK", scope + ["step_id", "assignment_seq"])
    constraint("gw.step_assignment", "CHECK", ["assignment_seq"], "assignment_seq>0")
    fk(
        "gw.step_assignment",
        scope + ["document_id", "step_id"],
        "gw.approval_step",
        scope + ["document_id", "id"],
    )
    d.update(
        version="0.26.0",
        task="GW-COMPANY-02",
        date="2026-10-17",
        migration_revision="gw_company_identity",
    )
    d["change_log"].append(
        {
            "version": "0.26.0",
            "task": "GW-COMPANY-02",
            "date": "2026-10-17",
            "change": "회사 GW 보안 5표·단계 복합 참조. 기존 회사/조직/사건 enum 재사용",
            "status": "제품 업무 비공개·환경별 적용 상태는 인계 참조",
        }
    )
    return True


if __name__ == "__main__":
    path = ROOT / "docs/db/schema-metadata/schema.json"
    d = json.loads(path.read_text())
    changed = apply(d)
    if changed:
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"changed": changed, "tables": len(d["tables"])}))
