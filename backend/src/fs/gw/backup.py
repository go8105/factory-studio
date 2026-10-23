"""Offline GW policy/checkpoint interface. Server operator only; no HTTP endpoint."""

from sqlalchemy import text

from fs.core.backup import BackupError
from fs.gw.operations import policy_from_row


def policy_snapshot(c, company_id):
    row = (
        c.execute(
            text("""SELECT p.* FROM core.company co JOIN core.workspace w ON w.id=co.workspace_id
        JOIN gw.operating_settings s ON (s.workspace_id,s.generation_id)=(w.id,w.active_generation_id)
        JOIN gw.operating_policy_revision p ON (p.workspace_id,p.generation_id,p.id)=(s.workspace_id,s.generation_id,s.current_policy_revision_id)
        WHERE co.workspace_id=:w AND co.status='ACTIVE' AND w.workspace_kind='COMPANY' """),
            {"w": company_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise BackupError("활성 회사의 적용된 운영 기준이 필요합니다.")
    policy = policy_from_row(row)
    return {
        "workspaceId": str(row["workspace_id"]),
        "generationId": str(row["generation_id"]),
        "policyDigest": policy.digest(),
        "policy": policy.model_dump(by_alias=True),
    }


def capture(c, *, scope=None):
    where = " WHERE workspace_id=:w AND generation_id=:g" if scope else ""
    params = {"w": scope[0], "g": scope[1]} if scope else {}
    queries = {
        "people": "SELECT id,workspace_id,generation_id,is_active,organization_unit_id FROM gw.person",
        "bindings": "SELECT id,workspace_id,generation_id,person_id,user_id,state FROM gw.person_identity_binding",
        "roles": "SELECT id,workspace_id,generation_id,person_id,role_key,is_active FROM gw.role_grant",
        "readers": "SELECT id,workspace_id,generation_id,document_id,person_id,is_active FROM gw.document_reader",
    }
    result = {
        kind: [dict(r) for r in c.execute(text(query + where), params).mappings()]
        for kind, query in queries.items()
    }
    # Changes that cannot be replayed without guessing conservatively quarantine the scope.
    guard_tables = [
        "organization_unit",
        "step_assignment",
        "authority_rule",
        "approval_route",
        "route_step",
        "delegation",
        "chat_member",
        "calendar_event",
        "event_attendee",
        "operating_settings",
        "retention_review",
    ]
    result["guards"] = {}
    for table in guard_tables:
        rows = c.execute(
            text(
                f"SELECT workspace_id,generation_id,encode(sha256(convert_to(coalesce(string_agg(encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex'),'' ORDER BY id),''),'UTF8')),'hex') AS hash FROM gw.{table} t{where} GROUP BY workspace_id,generation_id"
            ),
            params,
        ).mappings()
        result["guards"][table] = {
            f"{r['workspace_id']}/{r['generation_id']}": r["hash"] for r in rows
        }
    rows = c.execute(
        text(
            f"SELECT workspace_id,generation_id,encode(sha256(convert_to(coalesce(string_agg(id::text||':'||visibility||':'||coalesce(audience_org_id::text,'')||':'||status||':'||author_id::text,';' ORDER BY id),''),'UTF8')),'hex') AS hash FROM gw.board_post{where} GROUP BY workspace_id,generation_id"
        ),
        params,
    ).mappings()
    result["guards"]["post_visibility"] = {
        f"{r['workspace_id']}/{r['generation_id']}": r["hash"] for r in rows
    }
    return result


def replay(c, checkpoint):
    current = capture(c)
    quarantine = set()
    restricted = 0
    for table, before in current["guards"].items():
        after = checkpoint["guards"].get(table, {})
        for scope in set(before) | set(after):
            if before.get(scope) != after.get(scope):
                quarantine.add(tuple(map(int, scope.split("/"))))
    inactive = set()
    source_people = {r["id"]: r for r in checkpoint["people"]}
    for row in current["people"]:
        source = source_people.get(row["id"])
        if (
            source is None
            or not source["is_active"]
            or source["organization_unit_id"] != row["organization_unit_id"]
            or any(source[k] != row[k] for k in ["workspace_id", "generation_id"])
        ):
            c.execute(
                text(
                    "UPDATE gw.person SET is_active=false,version=version+1 WHERE id=:id"
                ),
                row,
            )
            inactive.add(row["id"])
            restricted += 1
    for kind, table, identity in [
        (
            "roles",
            "role_grant",
            ["workspace_id", "generation_id", "person_id", "role_key"],
        ),
        (
            "readers",
            "document_reader",
            ["workspace_id", "generation_id", "document_id", "person_id"],
        ),
    ]:
        sources = {r["id"]: r for r in checkpoint[kind]}
        for row in current[kind]:
            source = sources.get(row["id"])
            if (
                source is None
                or not source["is_active"]
                or any(source[k] != row[k] for k in identity)
                or row["person_id"] in inactive
            ):
                c.execute(
                    text(
                        f"UPDATE gw.{table} SET is_active=false,version=version+1 WHERE id=:id"
                    ),
                    row,
                )
                restricted += 1
    sources = {r["id"]: r for r in checkpoint["bindings"]}
    for row in current["bindings"]:
        source = sources.get(row["id"])
        if (
            source is None
            or source["state"] != "ACTIVE"
            or any(
                source[k] != row[k]
                for k in ["workspace_id", "generation_id", "person_id", "user_id"]
            )
            or row["person_id"] in inactive
            or (row["workspace_id"], row["generation_id"]) in quarantine
        ):
            c.execute(
                text(
                    "UPDATE gw.person_identity_binding SET state=CASE WHEN activated_at IS NULL THEN 'CANCELLED' ELSE 'SUSPENDED' END,closed_at=coalesce(closed_at,clock_timestamp()),version=version+1,reason='격리 복원 후 권한 회수 대조' WHERE id=:id"
                ),
                row,
            )
            restricted += 1
    # Delegations never silently resume after a database rollback.
    c.execute(
        text(
            "UPDATE gw.delegation SET revoked_at=coalesce(revoked_at,clock_timestamp()),version=version+1 WHERE revoked_at IS NULL"
        )
    )
    for workspace_id, generation_id in quarantine:
        c.execute(
            text(
                "UPDATE gw.operating_settings SET company_hold=true,hold_reason='격리 복원 후 보존·권한 변경 대조 필요',version=version+1,updated_at=clock_timestamp() WHERE workspace_id=:w AND generation_id=:g"
            ),
            {"w": workspace_id, "g": generation_id},
        )
    c.execute(
        text("UPDATE gw.collaboration_settings SET authz_version=authz_version+1")
    )
    return {
        "gwRestrictions": restricted,
        "quarantinedScopes": len(quarantine),
        "revocationsReapplied": True,
    }


def restrict_journal_scopes(c, scopes):
    applied = 0
    for w, g in scopes:
        p = {"w": w, "g": g}
        c.execute(
            text(
                "UPDATE gw.person_identity_binding SET state=CASE WHEN activated_at IS NULL THEN 'CANCELLED' ELSE 'SUSPENDED' END,closed_at=coalesce(closed_at,clock_timestamp()),version=version+1,reason='변경 기록에 따른 격리 복원 후 재확인' WHERE workspace_id=:w AND generation_id=:g AND state<>'CANCELLED'"
            ),
            p,
        )
        c.execute(
            text(
                "UPDATE gw.operating_settings SET company_hold=true,hold_reason='변경 기록의 권한·보존 재확인 필요',version=version+1,updated_at=clock_timestamp() WHERE workspace_id=:w AND generation_id=:g"
            ),
            p,
        )
        applied += c.execute(
            text(
                "UPDATE gw.collaboration_settings SET authz_version=authz_version+1 WHERE workspace_id=:w AND generation_id=:g"
            ),
            p,
        ).rowcount
    return applied


def restriction_violations(c, current, original, checkpoint, journal_scopes):
    """Observe effective GW restrictions; no replay, grants, or business writes."""

    def permitted(kind, row, fields, active):
        return all(
            (saved := next((r for r in source[kind] if r["id"] == row["id"]), None))
            is not None
            and active(saved)
            and all(saved[k] == row[k] for k in fields)
            for source in (original, checkpoint)
        )

    active_people = {r["id"] for r in current["people"] if r["is_active"]}
    violations = sum(
        not permitted(
            "people",
            r,
            ["workspace_id", "generation_id", "organization_unit_id"],
            lambda v: v["is_active"],
        )
        for r in current["people"]
        if r["is_active"]
    )
    for kind, fields in [
        ("roles", ["workspace_id", "generation_id", "person_id", "role_key"]),
        ("readers", ["workspace_id", "generation_id", "person_id", "document_id"]),
        ("bindings", ["workspace_id", "generation_id", "person_id", "user_id"]),
    ]:
        for row in current[kind]:
            if not (
                row["state"] == "ACTIVE" if kind == "bindings" else row["is_active"]
            ):
                continue
            violations += row["person_id"] not in active_people or not permitted(
                kind,
                row,
                fields,
                lambda r, kind=kind: (
                    r["state"] == "ACTIVE" if kind == "bindings" else r["is_active"]
                ),
            )
    quarantine = set()
    for table, before in original["guards"].items():
        after = checkpoint["guards"].get(table, {})
        quarantine.update(
            tuple(map(int, s.split("/")))
            for s in set(before) | set(after)
            if before.get(s) != after.get(s)
        )
    journal = set(map(tuple, journal_scopes))
    for w, g in quarantine | journal:
        active = sum(
            r["state"] == "ACTIVE" and (r["workspace_id"], r["generation_id"]) == (w, g)
            for r in current["bindings"]
        )
        hold = c.scalar(
            text(
                "SELECT company_hold FROM gw.operating_settings WHERE workspace_id=:w AND generation_id=:g"
            ),
            {"w": w, "g": g},
        )
        violations += bool(active) or hold is not True
    violations += c.scalar(
        text("SELECT count(*) FROM gw.delegation WHERE revoked_at IS NULL")
    )
    return int(violations)
