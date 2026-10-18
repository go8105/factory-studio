"""Approved GW-READY-02 additive metadata. Preserves existing constraint numbering."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def apply(data, proposal):
    old = {t["name"]: t for t in data["tables"]}
    if "core.mfa_factor" in old:
        raise ValueError("already applied; do not regenerate partial metadata")
    for table in proposal["tables"]:
        columns = []
        for c in table["columns"]:
            default = c["default"] or None
            if default == "IDENTITY":
                default = "GENERATED ALWAYS AS IDENTITY"
            columns.append(
                {
                    "name": c["name"],
                    "label": c["name"],
                    "type": c["type"],
                    "nullable": c["nullable"],
                    "default": default,
                    "rule": c.get("note", ""),
                }
            )
        if table["name"] in old:
            known = {c["name"] for c in old[table["name"]]["columns"]}
            old[table["name"]]["columns"].extend(
                c for c in columns if c["name"] not in known
            )
        else:
            data["tables"].append(
                {
                    "name": table["name"],
                    "label": table["label"],
                    "scope": "workspace_generation"
                    if table["name"].startswith("gw.")
                    else "global",
                    "phase": "GW-READY-02",
                    "columns": columns,
                    "note": "실사용 보안·운영 기반",
                    "retention": "명시 운영 보관 정책·원본 자동 삭제 없음",
                    "guest_cleanup": "회사 전용 0행·게스트 복사 금지",
                }
            )

    def c(table, kind, columns, expression=""):
        data["constraints"].append(
            {
                "table": table,
                "kind": kind,
                "columns": columns,
                "expression": expression,
                "reason": "GW-READY-02 인증·운영 무결성",
            }
        )

    S = ["workspace_id", "generation_id"]
    for table in proposal["tables"]:
        name = table["name"]
        if name in {"core.app_user", "core.auth_session"}:
            continue
        c(name, "PK", ["id"])
        if name.startswith("gw."):
            c(name, "UK", S + ["id"])
            c(name, "INDEX", S)
    for relation in proposal["relations"]:
        data["relations"].append(
            {k: v for k, v in relation.items() if k not in {"id"}}
            | {"note": "GW-READY-02 승인 설계"}
        )
    c("core.app_user", "CHECK", ["security_version"], "security_version>0")
    c("core.auth_session", "UK", ["user_id", "id"])
    c("core.auth_session", "CHECK", ["security_version"], "security_version>0")
    c(
        "core.auth_session",
        "CHECK",
        ["assurance"],
        "assurance IN ('PASSWORD','MFA','RECOVERY_LIMITED','OIDC')",
    )
    c(
        "core.auth_session",
        "CHECK",
        ["auth_method"],
        "auth_method IN ('PASSWORD','TOTP','RECOVERY','OIDC')",
    )
    t = "core.mfa_factor"
    c(t, "UK", ["user_id", "id"])
    for state in ("ACTIVE", "PENDING"):
        c(t, "UK_PARTIAL", ["user_id", "kind"], f"UNIQUE WHERE state='{state}'")
    c(t, "CHECK", ["kind"], "kind='TOTP'")
    c(t, "CHECK", ["version"], "version>0")
    c(
        t,
        "CHECK",
        ["state", "pending_expires_at", "confirmed_at", "revoked_at"],
        "(state='PENDING' AND pending_expires_at IS NOT NULL AND revoked_at IS NULL) OR (state='ACTIVE' AND confirmed_at IS NOT NULL AND revoked_at IS NULL) OR (state='REVOKED' AND revoked_at IS NOT NULL)",
    )
    t = "core.authentication_challenge"
    c(t, "UK", ["token_hash"])
    c(t, "CHECK", ["state"], "state IN ('PENDING','CONSUMED','EXPIRED','LOCKED')")
    c(
        t,
        "CHECK",
        ["purpose"],
        "purpose IN ('LOGIN_MFA','STEP_UP','ENROLL','OIDC_LOGIN','OIDC_LINK','RECOVERY')",
    )
    c(t, "CHECK", ["attempt_count"], "attempt_count>=0")
    c(t, "CHECK", ["expires_at", "created_at"], "expires_at>created_at")
    c(
        t,
        "CHECK",
        ["state", "consumed_at"],
        "state<>'CONSUMED' OR consumed_at IS NOT NULL",
    )
    c(
        t,
        "CHECK",
        ["purpose", "user_id", "session_id"],
        "(purpose='OIDC_LOGIN' OR user_id IS NOT NULL) AND (purpose NOT IN ('STEP_UP','OIDC_LINK') OR session_id IS NOT NULL)",
    )
    c(
        t,
        "CHECK",
        ["protected_payload", "encryption_key_id"],
        "(protected_payload IS NULL)=(encryption_key_id IS NULL)",
    )
    c(t, "INDEX", ["expires_at"])
    t = "core.recovery_code"
    c(t, "UK", ["user_id", "code_hash"])
    c(t, "CHECK", ["factor_version"], "factor_version>0")
    t = "core.sso_identity"
    c(t, "UK", ["issuer", "subject"])
    c(t, "UK_PARTIAL", ["user_id", "provider_key"], "UNIQUE WHERE state='ACTIVE'")
    c(
        t,
        "CHECK",
        ["state", "revoked_at"],
        "(state='ACTIVE' AND revoked_at IS NULL) OR (state='REVOKED' AND revoked_at IS NOT NULL)",
    )
    c(t, "CHECK", ["version"], "version>0")
    t = "core.authentication_throttle"
    c(t, "UK", ["bucket_hash", "window_started_at"])
    c(t, "CHECK", ["fail_count"], "fail_count>=0")
    c(t, "INDEX", ["locked_until"])
    t = "gw.operating_settings"
    c(t, "UK", S)
    c(t, "CHECK", ["version"], "version>0")
    c(
        t,
        "CHECK",
        ["rollout_state"],
        "rollout_state IN ('DRAFT','PILOT','ACTIVE','PAUSED')",
    )
    c(
        t,
        "CHECK",
        ["company_hold", "hold_reason"],
        "NOT company_hold OR (hold_reason IS NOT NULL AND char_length(btrim(hold_reason)) BETWEEN 2 AND 500)",
    )
    t = "gw.operating_policy_revision"
    c(t, "UK", S + ["revision_no"])
    for name, low, high in [
        ("expected_people", 1, 10000),
        ("expected_departments", 1, 1000),
        ("backup_interval_minutes", 5, 1440),
        ("rpo_minutes", 1, 1440),
        ("rto_minutes", 15, 10080),
        ("document_review_months", 1, 120),
        ("audit_review_months", 1, 120),
        ("backup_keep_days", 7, 365),
    ]:
        c(t, "CHECK", [name], f"{name} BETWEEN {low} AND {high}")
    c(
        t,
        "CHECK",
        ["backup_interval_minutes", "rpo_minutes"],
        "backup_interval_minutes<rpo_minutes",
    )
    c(t, "CHECK", ["revision_no"], "revision_no>0")
    c(t, "CHECK", ["reason"], "char_length(btrim(reason)) BETWEEN 2 AND 500")
    t = "gw.operating_evidence"
    c(t, "UK", S + ["run_id"])
    c(t, "CHECK", ["kind"], "kind IN ('BACKUP','RESTORE','ACCEPTANCE','INCIDENT')")
    c(t, "CHECK", ["result"], "result IN ('PASS','FAIL','PARTIAL')")
    c(t, "CHECK", ["finished_at", "started_at"], "finished_at>=started_at")
    t = "gw.retention_review"
    for key in ("document_id", "post_id"):
        c(
            t,
            "UK_PARTIAL",
            S + [key, "policy_revision_id"],
            f"UNIQUE WHERE {key} IS NOT NULL",
        )
    c(
        t,
        "CHECK",
        ["document_id", "post_id"],
        "(document_id IS NULL)<>(post_id IS NULL)",
    )
    c(t, "CHECK", ["state"], "state IN ('DUE','HELD','ARCHIVE_PREPARED','ARCHIVED')")
    c(t, "CHECK", ["version"], "version>0")
    c(t, "CHECK", ["reason"], "char_length(btrim(reason)) BETWEEN 2 AND 500")
    c(
        t,
        "CHECK",
        [
            "state",
            "archive_digest",
            "archive_reference",
            "reviewed_by_user_id",
            "reviewed_at",
        ],
        "state<>'ARCHIVED' OR (archive_digest IS NOT NULL AND archive_reference IS NOT NULL AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL)",
    )
    data.update(
        version="0.28.0",
        task="GW-READY-02",
        date="2026-10-18",
        migration_revision="gw_readiness",
        status="구현 중 / 로컬 검증 전",
    )
    return data


if __name__ == "__main__":
    path = ROOT / "docs/db/schema-metadata/schema.json"
    data = json.loads(path.read_text())
    proposal = json.loads(
        (ROOT / "docs/modules/gw/review/schema-proposal.json").read_text()
    )
    apply(data, proposal)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
