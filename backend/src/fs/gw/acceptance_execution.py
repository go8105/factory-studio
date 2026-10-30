"""Current transaction adapter for existing validators, without release authority.

The caller owns the company transaction and obtains policy, clock, revisions and
keys from server configuration. Never execute unsigned reports or proof claims.
"""

from fs.gw.acceptance_collection import collect_registered
from fs.gw.operating_contract import evidence_error
from fs.gw.readiness import assess


def execute(rows, *, connection, policy_id, **context):
    # Select before verification across every result/policy/version. Even a later
    # missing original or revoked signer must supersede an older success.
    latest = {}
    for row in rows:
        if row["kind"] not in {"BACKUP", "RESTORE", "ACCEPTANCE"}:
            continue
        if (
            row["workspace_id"] != context["workspace_id"]
            or row["generation_id"] != context["generation_id"]
        ):
            raise evidence_error()
        previous = latest.get(row["kind"])
        if previous is None or (row["recorded_at"], row["id"]) > (
            previous["recorded_at"],
            previous["id"],
        ):
            latest[row["kind"]] = row
    selected = list(latest.values())
    pair = {
        "result": "BLOCKED",
        "backupRestorePairVerified": False,
        "ready": False,
        "source": "LATEST_REGISTRATIONS",
        "reason": "POLICY_REQUIRED",
    }
    if context["policy"] is not None:
        pair = collect_registered(selected, policy_id=policy_id, **context)
    checks = assess(
        selected,
        connection=connection,
        policy_id=policy_id,
        **{
            key: value
            for key, value in context.items()
            if key not in {"workspace_id", "generation_id"}
        },
    )
    return pair, checks
