"""HR-owned account state, with authentication state supplied by its owner."""

from sqlalchemy import text

from fs.core.security.recording import capture_user, configured, persist


def record(c, ctx, user_id, operation):
    config = configured()
    if config is None:
        return
    rows = c.execute(
        text(
            "SELECT id,user_id,employee_id,work_role,is_active FROM hr.work_account WHERE workspace_id=:w AND generation_id=:g AND user_id=:u ORDER BY id"
        ),
        {"w": ctx.workspace_id, "g": ctx.generation_id, "u": user_id},
    ).mappings()
    persist(
        c,
        {
            "coverage": "hr.users.intent.v1",
            "userId": user_id,
            "workspaceId": ctx.workspace_id,
            "generationId": ctx.generation_id,
            "operation": operation,
            "snapshot": {
                "accounts": [dict(r) for r in rows],
                "core": capture_user(c, user_id),
            },
        },
        actor_id=ctx.user_id,
        config=config,
    )
