"""GW-e: populated generation copy, lazy reset, business actions and cleanup on PostgreSQL."""

from datetime import date, datetime
from uuid import uuid4

from fs.core.service import _delete_guest
from fs.erp.interface import approval_source_digest
from seed.copy import copy_template, copy_template_generation
from seed.gw import COUNTS
from sqlalchemy import text
from tests.test_gw import call, ok

SEEDS = ("gw", "erp", "hr")


def scoped(c, w, g, table):
    return (
        c.execute(
            text(
                f"SELECT * FROM gw.{table} WHERE workspace_id=:w AND generation_id=:g ORDER BY id"
            ),
            {"w": w, "g": g},
        )
        .mappings()
        .all()
    )


def test_populated_copy_shifts_dates_and_remaps_every_reference(guest_space):
    _, session, engine = guest_space
    with engine.begin() as c:
        w, g = session["workspaceId"], session["generationId"]
        source_date = c.execute(
            text("SELECT seed_date FROM core.data_generation WHERE id=:g"), {"g": g}
        ).scalar_one()
        original = {
            table: scoped(c, w, g, table.removeprefix("gw.")) for table in COUNTS
        }
        for target_date in [date(2027, 1, 5), date(2028, 2, 29)]:
            nw, ng, counts, _ = copy_template(
                c, w, g, target_date, str(uuid4()), schemas=("gw",)
            )
            assert {k: v for k, v in counts.items() if k.startswith("gw.")} == COUNTS
            copied = {
                table: scoped(c, nw, ng, table.removeprefix("gw.")) for table in COUNTS
            }
            ids = {
                table: {
                    old["id"]: new["id"]
                    for old, new in zip(original[table], copied[table], strict=True)
                }
                for table in COUNTS
            }
            delta = target_date - source_date
            for table in COUNTS:
                for old, new in zip(original[table], copied[table], strict=True):
                    assert (
                        new["workspace_id"] == nw
                        and new["generation_id"] == ng
                        and new["id"] != old["id"]
                    )
                    for field, value in old.items():
                        if isinstance(value, datetime):
                            assert new[field] == value + delta, (table, field)
            docs = {d["id"]: d for d in copied["gw.approval_document"]}
            for event in copied["gw.approval_event"]:
                details = event["details"] or {}
                if details.get("stepId"):
                    step = next(
                        s
                        for s in copied["gw.approval_step"]
                        if str(s["id"]) == details["stepId"]
                    )
                    assert step["document_id"] == event["document_id"]
                if details.get("delegationId"):
                    assert details["delegationId"] in {
                        str(d["id"]) for d in copied["gw.delegation"]
                    }
                if details.get("authorityRule"):
                    frozen = details["authorityRule"]
                    rule = copied["gw.authority_rule"][0]
                    assert (
                        frozen["id"] == str(rule["id"])
                        and frozen["effectiveFrom"] == rule["effective_from"]
                    )
                    assert (
                        datetime.fromisoformat(frozen["createdAt"])
                        == rule["created_at"]
                    )
                if details.get("appliedMonth"):
                    from seed.common import SEOUL

                    assert details["appliedMonth"] == docs[event["document_id"]][
                        "submitted_at"
                    ].astimezone(SEOUL).strftime("%Y-%m")
            targets = {
                "DOCUMENT": "gw.approval_document",
                "POST": "gw.board_post",
                "EVENT": "gw.calendar_event",
            }
            key_tables = {
                "D": "gw.approval_document",
                "P": "gw.board_post",
                "E": "gw.calendar_event",
                "C": "gw.comment",
            }
            for old, new in zip(
                original["gw.notification"], copied["gw.notification"], strict=True
            ):
                assert new["ref_id"] == ids[targets[old["ref_kind"]]][old["ref_id"]]
                prefix, entity, *rest = old["event_key"].split(":")
                assert new["event_key"] == ":".join(
                    [prefix, str(ids[key_tables[prefix]][int(entity)]), *rest]
                )
            for old, new in zip(
                original["gw.approval_document"],
                copied["gw.approval_document"],
                strict=True,
            ):
                assert (old["drafter_org_code"], old["drafter_org_name"]) == (
                    new["drafter_org_code"],
                    new["drafter_org_name"],
                )
                if new["source_snapshot"]:
                    assert (
                        new["source_digest"]
                        == old["source_digest"]
                        == approval_source_digest(new["source_snapshot"])
                    )
            assert [
                (m["seq"], m["client_key"], m["body"])
                for m in copied["gw.chat_message"]
            ] == [
                (m["seq"], m["client_key"], m["body"])
                for m in original["gw.chat_message"]
            ]
            assert [m["last_read_seq"] for m in copied["gw.chat_member"]] == [
                m["last_read_seq"] for m in original["gw.chat_member"]
            ]
            # 같은 원본을 다시 복사해도 기존 이력은 변하지 않는다.
            assert {
                table: scoped(c, w, g, table.removeprefix("gw.")) for table in COUNTS
            } == original
            _delete_guest(c, nw)
            for table in COUNTS:
                assert not scoped(c, nw, ng, table.removeprefix("gw."))


def test_seed_pending_delegation_consent_and_final_approval(guest_space, monkeypatch):
    from fs.gw import service
    from seed.common import at

    # 공통 fixture는 FS_TODAY=2026-09-24로 고정한다. 기간 판정도 그 체험 시각으로 맞춘다.
    monkeypatch.setattr(service, "now", lambda c: at(date(2026, 9, 24), 0, 12))
    client, session, engine = guest_space
    people = {p["code"]: p for p in ok(client.get("/api/v1/gw/people-options"))}
    with engine.connect() as c:
        doc = next(
            d
            for d in scoped(
                c, session["workspaceId"], session["generationId"], "approval_document"
            )
            if d["serial"] == 2
        )
    path = f"/documents/{doc['id']}"
    pending = ok(
        client.get(
            "/api/v1/gw/documents",
            params={"box": "pending", "personId": people["E009"]["id"]},
        )
    )
    assert any(d["id"] == str(doc["id"]) for d in pending["rows"])
    result = ok(
        call(
            client,
            session,
            "POST",
            path + "/approve",
            {"actingPersonId": people["E009"]["id"], "expectedVersion": doc["version"]},
        )
    )
    assert result["status"] == "IN_REVIEW" and result["currentStep"] == 1
    result = ok(
        call(
            client,
            session,
            "POST",
            path + "/consent",
            {
                "actingPersonId": people["E007"]["id"],
                "expectedVersion": result["version"],
            },
        )
    )
    assert result["currentStep"] == 2
    result = ok(
        call(
            client,
            session,
            "POST",
            path + "/approve",
            {
                "actingPersonId": people["E004"]["id"],
                "expectedVersion": result["version"],
            },
        )
    )
    assert result["status"] == "APPROVED"
    assert any(
        e.get("onBehalfOfPersonId") == people["E003"]["id"] for e in result["events"]
    )
    assert any(
        s["participantRole"] == "REFERENCE" and s["status"] == "SKIPPED"
        for s in result["steps"]
    )


def test_seed_generation_reset_and_actual_populated_cleanup(guest_space):
    _, session, engine = guest_space
    with engine.begin() as c:
        w, g = session["workspaceId"], session["generationId"]
        template = c.execute(
            text("SELECT template_generation_id FROM core.data_generation WHERE id=:g"),
            {"g": g},
        ).scalar_one()
        tw = c.execute(
            text("SELECT workspace_id FROM core.data_generation WHERE id=:g"),
            {"g": template},
        ).scalar_one()
        ng, counts, _ = copy_template_generation(
            c, tw, template, w, date(2027, 1, 5), schemas=("gw",)
        )
        assert {k: v for k, v in counts.items() if k.startswith("gw.")} == COUNTS
        assert scoped(c, w, g, "approval_event") and scoped(c, w, ng, "approval_event")
        _delete_guest(c, w)
        for table in COUNTS:
            assert not scoped(c, w, g, table.removeprefix("gw.")) and not scoped(
                c, w, ng, table.removeprefix("gw.")
            )


def test_lazy_reset_copies_gw_once_without_opening_other_modules(guest_space):
    client, session, engine = guest_space
    old = ok(client.get("/api/v1/gw/people-options"))
    reset = ok(call(client, session, "POST", "/api/v1/core/workspace/generations"), 201)
    first = ok(client.get("/api/v1/gw/people-options"))
    second = ok(client.get("/api/v1/gw/people-options"))
    assert first == second and len(first) == 10
    assert {p["id"] for p in old}.isdisjoint(p["id"] for p in first)
    with engine.connect() as c:
        g = c.execute(
            text("SELECT active_generation_id FROM core.workspace WHERE id=:w"),
            {"w": session["workspaceId"]},
        ).scalar_one()
        assert g != session["generationId"]
        for table, count in COUNTS.items():
            assert (
                len(scoped(c, session["workspaceId"], g, table.removeprefix("gw.")))
                == count
            )
        enabled = (
            c.execute(
                text(
                    "SELECT module_key FROM core.workspace_module WHERE workspace_id=:w AND seeded_generation_id=:g"
                ),
                {"w": session["workspaceId"], "g": g},
            )
            .scalars()
            .all()
        )
        assert enabled == ["gw"]
    person = next(p for p in first if p["code"] == "E005")
    inbox = ok(
        client.get("/api/v1/gw/notifications", params={"personId": person["id"]})
    )
    assert inbox and {n["refKind"] for n in inbox} == {"DOCUMENT", "POST", "EVENT"}
    assert reset  # 실제 초기화 응답이 성공한 후 확인한다.


def test_copied_seed_messages_keep_retry_keys_and_append_sequence(guest_space):
    client, session, _ = guest_space
    people = {p["code"]: p for p in ok(client.get("/api/v1/gw/people-options"))}
    person = people["E005"]["id"]
    channels = ok(client.get("/api/v1/gw/channels", params={"personId": person}))
    channel = next(ch for ch in channels if ch["code"] == "DEMO-CHAT-1")
    path = f"/channels/{channel['id']}/messages"
    replay = {
        "actingPersonId": person,
        "body": "품질 협의 일정에 참석해 주세요.",
        "clientKey": "demo-1-1",
    }
    old = ok(call(client, session, "POST", path, replay))
    assert old["seq"] == 1
    new = ok(
        call(
            client,
            session,
            "POST",
            path,
            {**replay, "clientKey": "after-copy", "body": "복사 후 새 메시지"},
        )
    )
    assert new["seq"] == 3
    assert (
        ok(
            call(
                client,
                session,
                "POST",
                path,
                {**replay, "clientKey": "after-copy", "body": "복사 후 새 메시지"},
            )
        )["id"]
        == new["id"]
    )
    cursor = ok(
        client.get("/api/v1/gw" + path, params={"personId": person, "after": 2})
    )
    assert [m["seq"] for m in cursor["messages"]] == [3]


def test_first_day_template_uses_actual_submission_month(guest_space):
    _, _, engine = guest_space
    from seed.generate import create_template
    from seed.validate import validate_all

    with engine.connect() as c:
        tx = c.begin()
        try:
            w, g, _ = create_template(c, date(2027, 1, 1))
            result = validate_all(c, w, g, date(2027, 1, 1))
            assert "V-GW" in result
            submissions = [
                e
                for e in scoped(c, w, g, "approval_event")
                if e["event_type"] == "SUBMITTED"
            ]
            assert all(e["details"]["appliedMonth"] == "2026-12" for e in submissions)
        finally:
            tx.rollback()
