"""GW-e: HR 합성 코드 사전의 조직 스냅샷과 결재·협업 체험 데이터."""

from fs.common.auth import AuthContext
from fs.erp.interface import approval_document

from seed.common import SEOUL, at, month_text
from seed.hr import DEPARTMENTS, EMPLOYEES

COUNTS = {
    "gw.organization_unit": 4,
    "gw.person": 10,
    "gw.approval_route": 2,
    "gw.route_step": 6,
    "gw.authority_rule": 1,
    "gw.delegation": 1,
    "gw.approval_document": 5,
    "gw.approval_step": 16,
    "gw.approval_event": 14,
    "gw.board_post": 3,
    "gw.board_event": 5,
    "gw.comment": 3,
    "gw.comment_revision": 1,
    "gw.calendar_event": 3,
    "gw.event_attendee": 4,
    "gw.notification": 8,
    "gw.chat_channel": 2,
    "gw.chat_member": 5,
    "gw.chat_message": 5,
}


def seed_gw(w):
    t = w.seed_date
    # SQL NULL은 일반 기안 원천 없음이다(JSON null과 구분).
    w.table("gw.approval_document").c.source_snapshot.type.none_as_null = True
    w.table("gw.approval_event").c.details.type.none_as_null = True
    org = w.add(
        "gw.organization_unit",
        [
            {"code": code, "name": name, "hr_synced_at": at(t, -2, 9)}
            for code, name, _, _ in DEPARTMENTS
        ],
        "code",
    )
    roles = {
        "E001": "BOARD_ADMIN",
        "E003": "MANAGER",
        "E004": "EXECUTIVE",
        "E007": "MANAGER",
    }
    source = {
        code: {
            "code": code,
            "name": name,
            "job_role": roles.get(code, "STAFF"),
            "hr_employee_code": code,
            "organization_unit_id": org[dept],
        }
        for code, name, dept, *_ in EMPLOYEES
    }
    people = w.add("gw.person", source.values(), "code")

    def identity(code, prefix):
        return {
            prefix + "_id": people[code],
            prefix + "_code": code,
            prefix + "_name": source[code]["name"],
            prefix + "_job_role": source[code]["job_role"],
        }

    routes = w.add(
        "gw.approval_route",
        [
            {"code": "DEMO-PARALLEL", "name": "생산팀 병렬 결재·품질 합의"},
            {"code": "DEMO-SIMPLE", "name": "생산팀 순차 결재"},
        ],
        "code",
    )
    parallel = [
        ("E003", 1, "APPROVER"),
        ("E007", 1, "CONSENT"),
        ("E008", 1, "REFERENCE"),
        ("E004", 2, "APPROVER"),
    ]
    simple = [("E003", 1, "APPROVER"), ("E004", 2, "APPROVER")]
    w.add(
        "gw.route_step",
        [
            {
                "route_id": routes[route],
                "person_id": people[code],
                "seq": seq,
                "participant_role": role,
            }
            for route, steps in [("DEMO-PARALLEL", parallel), ("DEMO-SIMPLE", simple)]
            for code, seq, role in steps
        ],
    )
    rule = w.add(
        "gw.authority_rule",
        [
            {
                "code": "DEMO-SMALL",
                "document_kind": "GENERAL",
                "currency": "KRW",
                "amount_from": "0",
                "amount_to": "100000",
                "final_seq": 1,
                "effective_from": month_text(t, -3),
            }
        ],
        "code",
    )["DEMO-SMALL"]
    grant = w.add(
        "gw.delegation",
        [
            {
                "delegator_person_id": people["E003"],
                "delegate_person_id": people["E009"],
                "starts_at": at(t, -1),
                "ends_at": at(t, 7),
                "document_kind": "GENERAL",
                "max_amount": "1000000",
                "reason": "합성 출장 기간 생산팀 결재 위임",
            }
        ],
        "id",
    )
    delegation_id = next(iter(grant.values()))
    specs = [
        ("초안: 생산 협업 개선", "DRAFT", "DEMO-PARALLEL", None),
        ("대기: 병렬 결재·품질 합의", "IN_REVIEW", "DEMO-PARALLEL", "300000"),
        ("완료: 소액 전결·위임", "APPROVED", "DEMO-PARALLEL", "50000"),
        ("완료: 기존 순차 결재", "APPROVED", "DEMO-SIMPLE", "200000"),
    ]
    docs = []
    for i, (title, status, route, amount) in enumerate(specs, 1):
        docs.append(
            dict(
                serial=i,
                document_no=f"GW-{i:06d}",
                kind="GENERAL",
                title=title,
                body="합성 체험 문서입니다. 담당자를 바꾸어 결재·합의·위임 이력을 확인하세요.",
                **identity("E005", "drafter"),
                route_id=routes[route],
                route_code=route,
                route_name="생산팀 병렬 결재·품질 합의"
                if route == "DEMO-PARALLEL"
                else "생산팀 순차 결재",
                status=status,
                version=1 if status == "DRAFT" else 2 if status == "IN_REVIEW" else 4,
                policy_version=1 if i == 4 else 2,
                amount=amount,
                currency="KRW" if amount else None,
                submission_order=i - 1 if i > 1 else None,
                current_step=1 if status == "IN_REVIEW" else None,
                submitted_at=at(t, -1, 9) if i > 1 else None,
                closed_at=at(t, -1, 12) if status == "APPROVED" else None,
                authority_rule_id=rule if i == 3 else None,
                drafter_org_code="PROD" if i > 1 else None,
                drafter_org_name="생산팀" if i > 1 else None,
                created_at=at(t, -2, 10),
            )
        )
    ctx = AuthContext(
        "SEED", "gw-demo", w.workspace_id, w.generation_id, None, frozenset(), ""
    )
    linked = approval_document(w.connection, ctx, "PURCHASE_INVOICE", "PI-0004")
    assert linked and linked.get("found"), "GW 합성 원천 PI-0004가 없습니다."
    snapshot = linked["snapshot"]
    docs.append(
        dict(
            docs[0],
            serial=5,
            document_no="GW-000005",
            kind="ERP_PURCHASE",
            title="초안: ERP 매입 원문 연결",
            route_id=routes["DEMO-SIMPLE"],
            route_code="DEMO-SIMPLE",
            route_name="생산팀 순차 결재",
            source_kind="PURCHASE_INVOICE",
            source_no="PI-0004",
            source_snapshot=snapshot,
            source_digest=linked["digest"],
            source_status=linked["status"],
            amount=snapshot["totalAmount"],
            currency=snapshot["currency"],
        )
    )
    # 모든 행의 선택 칸을 명시해 마지막 ERP 원천도 executemany에 포함한다.
    for doc in docs:
        for field in (
            "source_kind",
            "source_no",
            "source_snapshot",
            "source_digest",
            "source_status",
        ):
            doc.setdefault(field, None)
    did = w.add("gw.approval_document", docs, "serial")
    step_rows = []
    for i in range(1, 6):
        for code, seq, role in simple if i in (4, 5) else parallel:
            status = (
                "WAITING"
                if i < 3 or i == 5
                else "SKIPPED"
                if i == 3 and (seq == 2 or role == "REFERENCE")
                else "APPROVED"
            )
            dept = next(e[2] for e in EMPLOYEES if e[0] == code)
            step_rows.append(
                dict(
                    document_id=did[i],
                    seq=seq,
                    **identity(code, "person"),
                    participant_role=role,
                    status=status,
                    decided_at=at(t, -1, 11 if code == "E003" else 12)
                    if status == "APPROVED"
                    else None,
                    organization_code=dept if i in (2, 3, 4) else None,
                    organization_name=next(d[1] for d in DEPARTMENTS if d[0] == dept)
                    if i in (2, 3, 4)
                    else None,
                )
            )
    steps = w.add("gw.approval_step", step_rows, ("document_id", "person_code"))
    events = []

    def event(i, kind, code, version, seq=None, details=None, on_behalf=None):
        ordinal = sum(e["document_id"] == did[i] for e in events) + 1
        events.append(
            {
                "document_id": did[i],
                "event_seq": ordinal,
                "event_type": kind,
                "acting_person_id": people[code],
                "person_code": code,
                "person_name": source[code]["name"],
                "person_job_role": source[code]["job_role"],
                "actor_kind": "SEED",
                "actor_key": "gw-demo",
                "document_version": version,
                "step_seq": seq,
                "details": details,
                "on_behalf_of_person_id": on_behalf,
                "created_at": at(t, -2, 10)
                if kind == "CREATED"
                else at(t, -1, 9)
                if kind == "SUBMITTED"
                else at(t, -1, 12),
            }
        )

    for i in range(1, 6):
        event(i, "CREATED", "E005", 1)
        if i in (2, 3, 4):
            frozen = (
                {
                    "id": str(rule),
                    "workspaceId": str(w.workspace_id),
                    "generationId": str(w.generation_id),
                    "code": "DEMO-SMALL",
                    "documentKind": "GENERAL",
                    "currency": "KRW",
                    "amountFrom": "0.00",
                    "amountTo": "100000.00",
                    "finalSeq": 1,
                    "effectiveFrom": month_text(t, -3),
                    "effectiveTo": None,
                    "isActive": True,
                    "version": 1,
                    "createdAt": at(t, -91, 9).isoformat(),
                }
                if i == 3
                else None
            )
            event(
                i,
                "SUBMITTED",
                "E005",
                2,
                details={
                    "policyVersion": 1 if i == 4 else 2,
                    "authorityRule": frozen,
                    "appliedMonth": at(t, -1, 9).astimezone(SEOUL).strftime("%Y-%m"),
                },
            )
    event(
        3,
        "SKIPPED",
        "E005",
        2,
        2,
        {"stepId": str(steps[(did[3], "E004")]), "reason": "전결 규칙 적용"},
    )
    for code, kind in [("E003", "APPROVED"), ("E007", "CONSENTED")]:
        event(
            3,
            kind,
            "E009" if code == "E003" else code,
            3 if code == "E003" else 4,
            1,
            {
                "stepId": str(steps[(did[3], code)]),
                "participantRole": "APPROVER" if code == "E003" else "CONSENT",
                "delegationId": str(delegation_id) if code == "E003" else None,
                "originalPersonName": source[code]["name"],
            },
            people[code] if code == "E003" else None,
        )
    for code, seq in [("E008", 1)]:
        event(
            3,
            "SKIPPED",
            "E005",
            2 if seq == 2 else 4,
            seq,
            {
                "stepId": str(steps[(did[3], code)]),
                "reason": "전결 규칙 적용" if seq == 2 else "종결 시 참고 생략",
            },
        )
    for code, seq, _ in simple:
        event(4, "APPROVED", code, 2 + seq, seq, {"stepId": str(steps[(did[4], code)])})
    w.add("gw.approval_event", events)
    posts = w.add(
        "gw.board_post",
        [
            dict(
                serial=i,
                post_no=f"GB{i:06d}",
                board_kind=kind,
                **identity("E001", "author"),
                title=title,
                body="합성 공지입니다. 댓글 수정 이력과 부서별 표시를 확인하세요.",
                status="DRAFT" if i == 3 else "PUBLISHED",
                version=1 if i == 3 else 2,
                published_at=None if i == 3 else at(t, -1, 10),
                visibility="ORG" if i == 2 else "WORKSPACE",
                audience_org_id=org["PROD"] if i == 2 else None,
            )
            for i, kind, title in [
                (1, "NOTICE", "전사: 협업 체험 안내"),
                (2, "NOTICE", "생산팀: 부서 협업 안내"),
                (3, "FREE", "초안: 개선 아이디어"),
            ]
        ],
        "serial",
    )
    w.add(
        "gw.board_event",
        [
            {
                "post_id": posts[i],
                "event_seq": seq,
                "event_type": kind,
                "acting_person_id": people["E001"],
                "person_code": "E001",
                "person_name": source["E001"]["name"],
                "person_job_role": "BOARD_ADMIN",
                "actor_kind": "SEED",
                "actor_key": "gw-demo",
                "post_version": seq,
                "created_at": at(t, -2 if seq == 1 else -1, 10),
            }
            for i in range(1, 4)
            for seq, kind in [(1, "CREATED"), (2, "PUBLISHED")]
            if i < 3 or seq == 1
        ],
    )
    comments = w.add(
        "gw.comment",
        [
            {
                "target_kind": "POST" if i < 3 else "DOCUMENT",
                "post_id": posts[1] if i < 3 else None,
                "document_id": did[3] if i == 3 else None,
                "author_id": people["E005"],
                "author_name": source["E005"]["name"],
                "body": body,
                "status": "DELETED" if i == 2 else "ACTIVE",
                "revision_no": 2 if i == 1 else 1,
                "version": 2 if i < 3 else 1,
                "deleted_at": at(t, -1, 14) if i == 2 else None,
                "created_at": at(t, -1, 13),
            }
            for i, body in [
                (1, "확인했습니다. 일정 참석도 응답하겠습니다."),
                (2, "삭제 표시로 보존되는 합성 댓글"),
                (3, "결재 원문과 별도로 보관되는 의견입니다."),
            ]
        ],
        "id",
    )
    comment_ids = list(comments.values())
    w.add(
        "gw.comment_revision",
        [
            {
                "comment_id": comment_ids[0],
                "revision_no": 1,
                "body": "확인했습니다.",
                "created_at": at(t, -1, 14),
            }
        ],
    )
    events_ids = w.add(
        "gw.calendar_event",
        [
            {
                "event_no": f"GE{i:06d}",
                "title": title,
                "owner_id": people["E001"],
                "scope": "PERSONAL" if i == 1 else "DEPARTMENT",
                "organization_unit_id": None if i == 1 else org["PROD"],
                "starts_at": at(t, 0 if i == 1 else 1, 14 if i == 1 else 0),
                "ends_at": at(t, 0 if i == 1 else 2, 15 if i == 1 else 0),
                "all_day": i > 1,
                "status": "CANCELLED" if i == 3 else "ACTIVE",
                "location": "합성 회의실",
            }
            for i, title in [
                (1, "개인: 품질 협의"),
                (2, "생산팀: 종일 협업 점검"),
                (3, "취소: 이전 점검 일정"),
            ]
        ],
        "event_no",
    )
    for i in range(1, 4):
        w.add(
            "gw.event_attendee",
            [
                {
                    "event_id": events_ids[f"GE{i:06d}"],
                    "person_id": people[code],
                    "response": "ACCEPTED" if code == "E007" else "PENDING",
                    "responded_at": at(t, -1, 15) if code == "E007" else None,
                }
                for code in (["E005", "E007"] if i == 1 else ["E005"])
            ],
        )
    notifications = []
    for code in ["E003", "E007", "E009"]:
        notifications.append(
            {
                "recipient_id": people[code],
                "kind": "APPROVAL_ARRIVED",
                "ref_kind": "DOCUMENT",
                "ref_id": did[2],
                "event_key": f"D:{did[2]}:STAGE:1",
                "title": docs[1]["title"],
            }
        )
    notifications.append(
        {
            "recipient_id": people["E005"],
            "kind": "APPROVAL_DONE",
            "ref_kind": "DOCUMENT",
            "ref_id": did[3],
            "event_key": f"D:{did[3]}:CLOSED",
            "title": docs[2]["title"],
            "read_at": at(t, -1, 16),
        }
    )
    for code in ["E005", "E007"]:
        notifications.append(
            {
                "recipient_id": people[code],
                "kind": "NOTICE",
                "ref_kind": "POST",
                "ref_id": posts[1],
                "event_key": f"P:{posts[1]}:PUBLISHED",
                "title": "전사: 협업 체험 안내",
            }
        )
    notifications.append(
        {
            "recipient_id": people["E001"],
            "kind": "COMMENT",
            "ref_kind": "POST",
            "ref_id": posts[1],
            "event_key": f"C:{comment_ids[0]}:CREATED",
            "title": "새 댓글: 전사 협업 체험 안내",
        }
    )
    notifications.append(
        {
            "recipient_id": people["E005"],
            "kind": "EVENT",
            "ref_kind": "EVENT",
            "ref_id": events_ids["GE000002"],
            "event_key": f"E:{events_ids['GE000002']}:V:1",
            "title": "생산팀: 종일 협업 점검",
        }
    )
    # executemany는 첫 행의 칸을 기준으로 하므로 선택 칸도 명시한다.
    w.add(
        "gw.notification",
        [
            dict(read_at=None, **n, created_at=at(t, -1, 15))
            if "read_at" not in n
            else dict(n, created_at=at(t, -1, 15))
            for n in notifications
        ],
    )
    channels = w.add(
        "gw.chat_channel",
        [
            {
                "code": f"DEMO-CHAT-{i}",
                "name": name,
                "channel_kind": "DIRECT" if i == 1 else "GROUP",
                "created_by_id": people["E005"],
                "last_seq": 2 if i == 1 else 3,
            }
            for i, name in [(1, "생산·품질 협의"), (2, "생산 협업 모임")]
        ],
        "code",
    )
    w.add(
        "gw.chat_member",
        [
            {
                "channel_id": channels[f"DEMO-CHAT-{i}"],
                "person_id": people[code],
                "joined_at": at(t, -2, 9),
                "left_at": at(t, -1, 17) if i == 2 and code == "E009" else None,
                "last_read_seq": 1 if code == "E005" else 2,
            }
            for i, codes in [(1, ["E005", "E007"]), (2, ["E005", "E003", "E009"])]
            for code in codes
        ],
    )
    w.add(
        "gw.chat_message",
        [
            {
                "channel_id": channels[f"DEMO-CHAT-{i}"],
                "seq": seq,
                "author_id": people[code],
                "body": body,
                "client_key": f"demo-{i}-{seq}",
                "created_at": at(t, -1, 16, seq),
            }
            for i, seq, code, body in [
                (1, 1, "E005", "품질 협의 일정에 참석해 주세요."),
                (1, 2, "E007", "참석 응답을 완료했습니다."),
                (2, 1, "E005", "병렬 결재·합의 문서를 확인해 주세요."),
                (2, 2, "E003", "출장 중에는 설비팀 담당자에게 위임합니다."),
                (2, 3, "E009", "위임받은 문서와 전결 이력을 확인했습니다."),
            ]
        ],
    )
