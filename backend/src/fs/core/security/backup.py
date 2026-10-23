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


def restrict_journal_users(c, user_ids):
    """Historical or unconfirmed changes require manual review; never re-enable."""
    if not user_ids:
        return 0
    return c.execute(
        text(
            "UPDATE core.app_user SET status='disabled',disabled_at=coalesce(disabled_at,clock_timestamp()),security_version=security_version+1 WHERE id=ANY(:ids)"
        ),
        {"ids": user_ids},
    ).rowcount


def restriction_violations(current, original, checkpoint, journal_users):
    """Read-only comparison against both captured states; stricter denial is valid.

    Snapshots stay private. This verifies only the explicit checkpoint fields,
    never completeness of the collection paths or live company acceptance.
    """
    from datetime import datetime

    def matched(kind, row, fields, allowed=lambda r: True):
        for source in (original, checkpoint):
            saved = next(
                (r for r in source[kind] if r.get("id") == row.get("id")), None
            )
            if (
                saved is None
                or not allowed(saved)
                or any(saved[k] != row[k] for k in fields)
            ):
                return False
        return True

    users = {r["id"]: r for r in current["users"]}
    active_users = {
        k for k, r in users.items() if r["status"] == "active" and not r["disabled"]
    }
    violations = sum(
        not matched(
            "users",
            row,
            ["identity", "credential", "security_version"],
            lambda r: r["status"] == "active" and not r["disabled"],
        )
        for row in current["users"]
        if row["id"] in active_users
    )
    allowed_roles = set.intersection(
        *(
            {(r["user_id"], r["role_id"]) for r in source["roles"]}
            for source in (original, checkpoint)
        )
    )
    violations += sum(
        (r["user_id"], r["role_id"]) not in allowed_roles for r in current["roles"]
    )
    workspace_sources = [
        {r["id"]: r for r in source["workspaces"]} for source in (original, checkpoint)
    ]
    blocked = {
        r["id"]
        for r in current["workspaces"]
        if any(source.get(r["id"]) != r for source in workspace_sources)
    }
    companies = [
        {r["workspace_id"]: r for r in source["companies"]}
        for source in (original, checkpoint)
    ]
    blocked.update(
        r["workspace_id"]
        for r in current["companies"]
        if any(
            source.get(r["workspace_id"], {}).get("status") != "ACTIVE"
            for source in companies
        )
    )
    violations += sum(
        r["workspace_id"] in blocked
        or not matched(
            "members", r, ["workspace_id", "user_id", "role"], lambda v: v["is_active"]
        )
        for r in current["members"]
        if r["is_active"]
    )
    factors = {r["id"]: r for r in current["factors"]}
    for row in factors.values():
        if row["state"] not in {"ACTIVE", "PENDING"}:
            continue
        valid = (
            row["state"] == "ACTIVE"
            and row["user_id"] in active_users
            and matched(
                "factors",
                row,
                ["user_id", "version", "secret"],
                lambda r: r["state"] == "ACTIVE",
            )
        )
        if valid:
            for source in (original, checkpoint):
                saved = next(r for r in source["factors"] if r["id"] == row["id"])
                if saved["last_used_step"] is not None and (
                    row["last_used_step"] is None
                    or row["last_used_step"] < saved["last_used_step"]
                ):
                    valid = False
        violations += not valid
    for row in current["codes"]:
        if not row["used"] and not row["revoked"]:
            violations += not (
                row["user_id"] in active_users
                and factors.get(row["factor_id"], {}).get("state") == "ACTIVE"
                and matched(
                    "codes",
                    row,
                    ["user_id", "factor_id"],
                    lambda r: not r["used"] and not r["revoked"],
                )
            )
    violations += sum(
        r["user_id"] not in active_users
        or not matched(
            "sso", r, ["user_id", "version"], lambda v: v["state"] == "ACTIVE"
        )
        for r in current["sso"]
        if r["state"] == "ACTIVE"
    )
    throttles = {(r["bucket_hash"], r["window"]): r for r in current["throttles"]}
    for saved in checkpoint["throttles"]:
        row = throttles.get((saved["bucket_hash"], saved["window"]))
        violations += (
            row is None
            or row["fail_count"] < saved["fail_count"]
            or bool(
                saved["locked"] is not None
                and (
                    row["locked"] is None
                    or datetime.fromisoformat(row["locked"])
                    < datetime.fromisoformat(saved["locked"])
                )
            )
        )
    journal_violations = sum(
        uid in users
        and (users[uid]["status"] != "disabled" or not users[uid]["disabled"])
        for uid in set(journal_users)
    )
    return int(violations), journal_violations
