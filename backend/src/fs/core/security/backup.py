"""Deny-only security checkpoint replay after an offline database restore."""

from sqlalchemy import text


def capture(c):
    queries = {
        "roles": "SELECT user_id,role_id FROM core.user_role",
        "workspaces": "SELECT id,owner_user_id,active_generation_id,workspace_kind FROM core.workspace",
        "companies": "SELECT workspace_id,status FROM core.company",
        "users": "SELECT id,status,disabled_at IS NOT NULL AS disabled,security_version,encode(sha256(convert_to(login_id,'UTF8')),'hex') AS identity,encode(sha256(convert_to(password_hash,'UTF8')),'hex') AS credential FROM core.app_user",
        "members": "SELECT id,workspace_id,user_id,role,is_active FROM core.company_member",
        "factors": "SELECT id,user_id,state,version,last_used_step,encode(sha256(convert_to(secret_ciphertext,'UTF8')),'hex') AS secret FROM core.mfa_factor",
        "codes": "SELECT id,user_id,factor_id,used_at IS NOT NULL AS used,revoked_at IS NOT NULL AS revoked FROM core.recovery_code",
        "sso": "SELECT id,user_id,state,version FROM core.sso_identity",
        "throttles": "SELECT bucket_hash,window_started_at::text AS window,fail_count,locked_until::text AS locked FROM core.authentication_throttle",
    }
    return {
        kind: [dict(r) for r in c.execute(text(query)).mappings()]
        for kind, query in queries.items()
    }


def replay(c, checkpoint):
    current = capture(c)
    disabled = set()
    changed = 0
    for row in current["users"]:
        source = next((v for v in checkpoint["users"] if v["id"] == row["id"]), None)
        if (
            source is None
            or source["disabled"]
            or source["status"] != "active"
            or source["security_version"] != row["security_version"]
            or source["credential"] != row["credential"]
            or source["identity"] != row["identity"]
        ):
            c.execute(
                text(
                    "UPDATE core.app_user SET status='disabled',disabled_at=coalesce(disabled_at,clock_timestamp()),security_version=security_version+1 WHERE id=:id"
                ),
                {"id": row["id"]},
            )
            disabled.add(row["id"])
            changed += 1
    active_roles = {(r["user_id"], r["role_id"]) for r in checkpoint["roles"]}
    for row in current["roles"]:
        if (row["user_id"], row["role_id"]) not in active_roles:
            c.execute(
                text(
                    "DELETE FROM core.user_role WHERE user_id=:user_id AND role_id=:role_id"
                ),
                row,
            )
            changed += 1
    source_workspaces = {r["id"]: r for r in checkpoint["workspaces"]}
    blocked_workspaces = {
        r["id"] for r in current["workspaces"] if source_workspaces.get(r["id"]) != r
    }
    source_companies = {r["workspace_id"]: r for r in checkpoint["companies"]}
    blocked_workspaces.update(
        r["workspace_id"]
        for r in current["companies"]
        if source_companies.get(r["workspace_id"], {}).get("status") != "ACTIVE"
    )
    for row in current["members"]:
        source = next((v for v in checkpoint["members"] if v["id"] == row["id"]), None)
        if (
            row["workspace_id"] in blocked_workspaces
            or source is None
            or not source["is_active"]
            or any(source[k] != row[k] for k in ["workspace_id", "user_id", "role"])
        ):
            c.execute(
                text("UPDATE core.company_member SET is_active=false WHERE id=:id"),
                {"id": row["id"]},
            )
            changed += 1
    for row in current["factors"]:
        source = next((v for v in checkpoint["factors"] if v["id"] == row["id"]), None)
        if (
            row["state"] == "PENDING"
            or source is None
            or source["state"] != "ACTIVE"
            or source["version"] != row["version"]
            or source["user_id"] != row["user_id"]
            or source["secret"] != row["secret"]
            or row["user_id"] in disabled
        ):
            c.execute(
                text(
                    "UPDATE core.mfa_factor SET state='REVOKED',revoked_at=coalesce(revoked_at,clock_timestamp()) WHERE id=:id"
                ),
                {"id": row["id"]},
            )
            changed += 1
        elif source["last_used_step"] is not None:
            c.execute(
                text(
                    "UPDATE core.mfa_factor SET last_used_step=greatest(last_used_step,:step) WHERE id=:id"
                ),
                {"id": row["id"], "step": source["last_used_step"]},
            )
    for kind, table in [("codes", "recovery_code"), ("sso", "sso_identity")]:
        sources = {r["id"]: r for r in checkpoint[kind]}
        for row in current[kind]:
            source = sources.get(row["id"])
            if (
                source is None
                or source["user_id"] != row["user_id"]
                or row["user_id"] in disabled
                or (
                    kind == "codes"
                    and (
                        source["used"]
                        or source["revoked"]
                        or source["factor_id"] != row["factor_id"]
                    )
                )
                or (
                    kind == "sso"
                    and (
                        source["state"] != "ACTIVE"
                        or source["version"] != row["version"]
                    )
                )
            ):
                change = "revoked_at=coalesce(revoked_at,clock_timestamp())" + (
                    ",state='REVOKED'" if kind == "sso" else ""
                )
                c.execute(
                    text(f"UPDATE core.{table} SET {change} WHERE id=:id"),
                    {"id": row["id"]},
                )
                changed += 1
    for row in checkpoint["throttles"]:
        c.execute(
            text("""INSERT INTO core.authentication_throttle(bucket_hash,window_started_at,fail_count,locked_until,updated_at)
            VALUES(:bucket_hash,cast(:window AS timestamptz),:fail_count,cast(:locked AS timestamptz),clock_timestamp())
            ON CONFLICT(bucket_hash,window_started_at) DO UPDATE SET fail_count=greatest(core.authentication_throttle.fail_count,excluded.fail_count),locked_until=greatest(core.authentication_throttle.locked_until,excluded.locked_until),updated_at=clock_timestamp()"""),
            row,
        )
    c.execute(
        text(
            "UPDATE core.auth_session SET revoked_at=coalesce(revoked_at,clock_timestamp())"
        )
    )
    c.execute(
        text(
            "UPDATE core.authentication_challenge SET state='EXPIRED' WHERE state='PENDING'"
        )
    )
    invalidated = c.execute(
        text(
            "SELECT NOT EXISTS(SELECT 1 FROM core.auth_session WHERE revoked_at IS NULL)"
        )
    ).scalar_one()
    return {
        "sessionsInvalidated": invalidated,
        "coreRestrictions": changed,
        "disabledAccounts": len(disabled),
    }


def required_keys(c):
    return set(
        c.execute(
            text(
                "SELECT DISTINCT encryption_key_id FROM core.mfa_factor WHERE state='ACTIVE'"
            )
        ).scalars()
    )
