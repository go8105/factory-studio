"""Offline HR account restrictions for full-database recovery. Never grants access."""

from sqlalchemy import text


def capture(c):
    return [
        dict(r)
        for r in c.execute(
            text(
                "SELECT id,workspace_id,generation_id,user_id,employee_id,work_role,is_active FROM hr.work_account"
            )
        ).mappings()
    ]


def replay(c, checkpoint):
    sources = {r["id"]: r for r in checkpoint}
    restricted = 0
    for row in capture(c):
        source = sources.get(row["id"])
        if (
            source is None
            or not source["is_active"]
            or any(
                source[k] != row[k]
                for k in [
                    "workspace_id",
                    "generation_id",
                    "user_id",
                    "employee_id",
                    "work_role",
                ]
            )
        ):
            c.execute(
                text("UPDATE hr.work_account SET is_active=false WHERE id=:id"), row
            )
            restricted += 1
    return {"hrRestrictions": restricted}


def restrict_journal_users(c, user_ids):
    if not user_ids:
        return 0
    return c.execute(
        text("UPDATE hr.work_account SET is_active=false WHERE user_id=ANY(:ids)"),
        {"ids": user_ids},
    ).rowcount


def restriction_violations(current, original, checkpoint, journal_users):
    """Only active restored HR grants need both captured permissions."""
    sources = [{r["id"]: r for r in rows} for rows in (original, checkpoint)]
    fields = ["workspace_id", "generation_id", "user_id", "employee_id", "work_role"]
    return sum(
        row["user_id"] in journal_users
        or any(
            (saved := source.get(row["id"])) is None
            or not saved["is_active"]
            or any(saved[k] != row[k] for k in fields)
            for source in sources
        )
        for row in current
        if row["is_active"]
    )
