"""DSN-31: GW 보강(체험 + 실제 도입 A 설계)을 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn30 다음·apply_dsn90 앞).

근거: docs/modules/gw/GW_보강설계_DSN-31.md 4장, 결정 Q1~Q7. ROADMAP-02 D81(사람·조직 원천 = HR)·D82.
체험 GW(W5): 결재 대상 확장(ERP 발주·지출결의·PLM ECO), 병렬·합의·전결·위임, 댓글, 일정, 알림함, 채팅, ERP 확정 통제(ERP 소유).
실제 도입 A(설계만 목표 DB, 개발은 별도 트랙 — Q1): core TEAM 공간·멤버십·초대·생성 영수증, 세션 활성 공간·추가 인증,
GW 협업 설정·직원 계정 연결·업무 권한·문서 열람·결재 재배정. GW-EXT A의 person_assignment는 D81로 두지 않는다
(조직은 HR 부서를 가져온 gw.organization_unit, 사람의 현재 조직은 gw.person.organization_unit_id).
"""

import copy
import json
from pathlib import Path

import apply_fs030a
from apply_fs023a import S, c, col, r
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
CODE = "~ '^[A-Z0-9][A-Z0-9_-]{0,29}$'"
P = "gw."
KINDS = ("GENERAL", "ERP_PURCHASE", "ERP_PO", "ERP_EXPENSE", "PLM_ECO")
SOURCE = {
    "ERP_PURCHASE": "PURCHASE_INVOICE",
    "ERP_PO": "PURCHASE_ORDER",
    "ERP_EXPENSE": "EXPENSE_CLAIM",
    "PLM_ECO": "ECO",
}
ROLES = ("APPROVER", "CONSENT", "REFERENCE")
STEP_EVENTS = (
    "('APPROVED','REJECTED','CONSENTED','OPPOSED','SKIPPED','STEP_REASSIGNED')"
)
REASON_EVENTS = "('REJECTED','WITHDRAWN','OPPOSED','STEP_REASSIGNED','READER_REVOKED')"


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    t = {**_table(name, label, sub, note, columns), "phase": "DSN-31"}
    t["columns"][-1] = {
        **t["columns"][-1],
        "default": "clock_timestamp()",
    }  # GW 관례(FS-030 D68)
    return t


def core_table(name, label, note, columns, scope="global"):
    return dict(
        name=name,
        label=label,
        scope=scope,
        phase="DSN-31",
        retention="초기화 보존",
        guest_cleanup="TEAM 공간 전용(게스트 복사 대상 아님)",
        sub_module="team",
        note=note,
        columns=[
            col("id", "내부 식별자", "bigint", default="GENERATED ALWAYS AS IDENTITY"),
            *columns,
        ],
    )


def person(name="person_id", label="담당자", nullable=False):
    return col(name, label, "bigint", nullable=nullable, rule="gw.person")


def subject(name, label, nullable=False):
    return col(
        name,
        label,
        "uuid",
        nullable=nullable,
        rule="core.app_user.subject_key 스냅샷(FK 없음, 서버 인증 값)",
    )


AR, DG, CM, CR, CE, EA, NT, CH, CHM, CHG = (
    P + n
    for n in (
        "authority_rule",
        "delegation",
        "comment",
        "comment_revision",
        "calendar_event",
        "event_attendee",
        "notification",
        "chat_channel",
        "chat_member",
        "chat_message",
    )
)
OU, CS, IB, RG, DR, SA = (
    P + n
    for n in (
        "organization_unit",
        "collaboration_settings",
        "person_identity_binding",
        "role_grant",
        "document_reader",
        "step_assignment",
    )
)
WM, WI, TR = (
    "core.workspace_membership",
    "core.workspace_invitation",
    "core.team_creation_receipt",
)
EP, EV = "erp.approval_policy", "erp.approval_evidence"

TABLES = [
    # ── 체험 GW ──
    table(
        AR,
        "전결 규칙",
        "approval",
        "DSN-31 F07(Q3). 문서 유형·금액·통화별로 생략할 단계. 상신 때 문서에 규칙 id를 고정(이후 규칙이 바뀌어도 그대로)",
        [
            col("code", "규칙 코드", "varchar(30)"),
            col("document_kind", "문서 유형", "varchar(20)", rule=" / ".join(KINDS)),
            col("currency", "통화", "varchar(3)", default="'KRW'"),
            col("amount_from", "금액 이상", "numeric(18,2)", default="0"),
            col(
                "amount_to",
                "금액 미만",
                "numeric(18,2)",
                nullable=True,
                rule="NULL이면 상한 없음",
            ),
            col(
                "final_seq",
                "최종 결재 단계",
                "smallint",
                rule="이 단계까지 결재하고 뒤 단계는 SKIPPED",
            ),
            col("effective_from", "적용 시작 월", "varchar(7)", rule="'YYYY-MM'"),
            col(
                "effective_to",
                "적용 끝 월",
                "varchar(7)",
                nullable=True,
                rule="'YYYY-MM'",
            ),
            col("is_active", "사용 여부", "boolean", default="true"),
            col("version", "버전", "integer", default="1"),
        ],
    ),
    table(
        DG,
        "위임",
        "approval",
        "DSN-31 F08(Q3). 부재 기간 대리 결재. 연쇄 위임·자기 결재·기안자 우회 금지(SERVICE). 원 담당자와 실제 수행자를 사건에 함께 남긴다",
        [
            person("delegator_person_id", "위임자"),
            person("delegate_person_id", "수임자"),
            col("starts_at", "시작", "timestamptz"),
            col("ends_at", "끝", "timestamptz"),
            col(
                "document_kind",
                "대상 문서 유형",
                "varchar(20)",
                nullable=True,
                rule="NULL이면 전체",
            ),
            col("max_amount", "금액 한도", "numeric(18,2)", nullable=True),
            col("reason", "사유", "varchar(500)"),
            col("revoked_at", "회수 시각", "timestamptz", nullable=True),
            col("version", "버전", "integer", default="1"),
        ],
    ),
    table(
        CM,
        "댓글",
        "board",
        "DSN-31 F13(Q4). 게시글·결재 문서의 댓글. 원문 승인 범위를 바꾸지 않는다. 수정은 revision, 삭제는 표시",
        [
            col("target_kind", "대상", "varchar(10)", rule="POST / DOCUMENT"),
            col("post_id", "게시글", "bigint", nullable=True),
            col("document_id", "결재 문서", "bigint", nullable=True),
            person("author_id", "작성자"),
            col("author_name", "작성자명", "varchar(80)", rule="스냅샷"),
            col("body", "내용", "varchar(2000)"),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'ACTIVE'",
                rule="ACTIVE / DELETED",
            ),
            col("revision_no", "현재 revision", "integer", default="1"),
            col("deleted_at", "삭제 표시 시각", "timestamptz", nullable=True),
            col("version", "버전", "integer", default="1"),
        ],
    ),
    table(
        CR,
        "댓글 수정 이력",
        "board",
        "DSN-31 F13. 수정 전 내용(추가만)",
        [
            col("comment_id", "댓글", "bigint"),
            col("revision_no", "revision", "integer"),
            col("body", "내용", "varchar(2000)"),
        ],
    ),
    table(
        CE,
        "일정",
        "collab",
        "DSN-31 F31(Q5). 개인·부서 일정. 부서 일정의 부서는 조직 단위(HR 부서 스냅샷)",
        [
            col("event_no", "일정 번호", "varchar(40)"),
            col("title", "제목", "varchar(200)"),
            person("owner_id", "등록자"),
            col("scope", "공개 범위", "varchar(12)", rule="PERSONAL / DEPARTMENT"),
            col("organization_unit_id", "부서", "bigint", nullable=True),
            col("starts_at", "시작", "timestamptz"),
            col("ends_at", "끝", "timestamptz"),
            col("all_day", "종일", "boolean", default="false"),
            col("location", "장소", "varchar(200)", nullable=True),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'ACTIVE'",
                rule="ACTIVE / CANCELLED",
            ),
            col("version", "버전", "integer", default="1"),
        ],
    ),
    table(
        EA,
        "일정 참석자",
        "collab",
        "DSN-31 F31. 참석 응답",
        [
            col("event_id", "일정", "bigint"),
            person(),
            col(
                "response",
                "응답",
                "varchar(10)",
                default="'PENDING'",
                rule="PENDING / ACCEPTED / DECLINED",
            ),
            col("responded_at", "응답 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        NT,
        "알림",
        "collab",
        "DSN-31 F32(Q5). 내부 알림함. 업무 변경 트랜잭션 안에서 생성(사건 키로 중복 0). 외부 메일·푸시는 실제 도입 트랙 F",
        [
            person("recipient_id", "받는 사람"),
            col(
                "kind",
                "종류",
                "varchar(20)",
                rule="APPROVAL_ARRIVED / APPROVAL_DONE / REJECTED / WITHDRAWN / NOTICE / COMMENT / EVENT / MENTION",
            ),
            col(
                "ref_kind",
                "대상 종류",
                "varchar(12)",
                rule="DOCUMENT / POST / EVENT / CHANNEL",
            ),
            col("ref_id", "대상 id", "bigint"),
            col(
                "event_key",
                "사건 키",
                "varchar(80)",
                rule="(대상 종류, 대상, 사건 순번) — 재시도 중복 방지",
            ),
            col("title", "제목", "varchar(200)"),
            col("read_at", "읽은 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        CH,
        "대화방",
        "collab",
        "DSN-31 F33(Q5). 1:1·그룹 대화. 저장은 HTTP(추가만), 실시간 전송 수단은 개발 때 부하 확인 후 선택",
        [
            col("code", "대화방 코드", "varchar(30)"),
            col("name", "이름", "varchar(100)"),
            col("channel_kind", "구분", "varchar(8)", rule="DIRECT / GROUP"),
            person("created_by_id", "만든 사람"),
            col("last_seq", "마지막 메시지 순번", "bigint", default="0"),
            col("archived_at", "보관 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        CHM,
        "대화방 참여자",
        "collab",
        "DSN-31 F33. 참여·나감·읽음 커서. 나간 뒤 새 메시지 수신 차단",
        [
            col("channel_id", "대화방", "bigint"),
            person(),
            col("joined_at", "참여 시각", "timestamptz", default="now()"),
            col("left_at", "나간 시각", "timestamptz", nullable=True),
            col("last_read_seq", "읽은 순번", "bigint", default="0"),
        ],
    ),
    table(
        CHG,
        "메시지",
        "collab",
        "DSN-31 F33. 대화방별 순번(재연결·중복 제거 기준). 추가만, 정정은 새 메시지",
        [
            col("channel_id", "대화방", "bigint"),
            col("seq", "순번", "bigint"),
            person("author_id", "보낸 사람"),
            col("body", "내용", "varchar(2000)"),
            col("client_key", "클라이언트 키", "varchar(80)", rule="재전송 중복 제거"),
        ],
    ),
    # ── 사람·조직(D81) + 실제 도입 A(GW) ──
    table(
        OU,
        "조직 단위",
        "org",
        "DSN-31 F22·F23(D81). HR 부서를 'HR에서 가져오기'한 스냅샷(코드 = HR 부서 코드). 문서 권한·부서 일정·게시 대상 판정용. 순환 금지(SERVICE)",
        [
            col("code", "부서 코드", "varchar(30)", rule="HR 부서 코드"),
            col("name", "부서명", "varchar(100)"),
            col("parent_id", "상위", "bigint", nullable=True),
            col("is_active", "사용 여부", "boolean", default="true"),
            col("hr_synced_at", "HR 가져온 시각", "timestamptz", nullable=True),
            col("version", "버전", "integer", default="1"),
        ],
    ),
    table(
        CS,
        "협업 설정",
        "team",
        "DSN-31 F51(Q1, 실제 도입). TEAM 공간 GW 초기화 1회·권한 버전(권한이 바뀌면 +1, 캐시 무효화)",
        [
            col("authz_version", "권한 버전", "bigint", default="1"),
            subject("initialized_by_subject", "초기화한 계정"),
            col("initialized_at", "초기화 시각", "timestamptz"),
        ],
    ),
    table(
        IB,
        "직원 계정 연결",
        "team",
        "DSN-31 F52(Q1). 실제 계정(subject) ↔ GW 담당자. 활성 후 subject·person 변경 금지, 같은 직원을 다른 계정에 다시 연결 금지",
        [
            person(),
            subject("subject_key", "계정"),
            col(
                "state",
                "상태",
                "varchar(12)",
                default="'PENDING'",
                rule="PENDING / ACTIVE / SUSPENDED / CANCELLED",
            ),
            subject("requested_by_subject", "요청 계정"),
            col("activated_at", "활성 시각", "timestamptz", nullable=True),
            col("closed_at", "종료 시각", "timestamptz", nullable=True),
            col("reason", "사유", "varchar(500)", nullable=True),
            col("version", "버전", "integer", default="1"),
        ],
    ),
    table(
        RG,
        "업무 권한",
        "team",
        "DSN-31 F52(Q1). TEAM 업무 권한 원천(직무 표시값은 권한 아님)",
        [
            person(),
            col(
                "role_key",
                "권한",
                "varchar(30)",
                rule="ORG_ADMIN / ROUTE_ADMIN / BOARD_PUBLISHER / SECURITY_ADMIN / AUDITOR",
            ),
            col("is_active", "사용 여부", "boolean", default="true"),
            subject("changed_by_subject", "변경 계정"),
            col("reason", "사유", "varchar(500)"),
            col("version", "버전", "integer", default="1"),
        ],
    ),
    table(
        DR,
        "문서 열람 권한",
        "team",
        "DSN-31 F52(Q1). 기밀 결재 문서의 추가 열람자. 읽기만, 결재 권한 아님",
        [
            col("document_id", "결재 문서", "bigint"),
            person(),
            col("is_active", "사용 여부", "boolean", default="true"),
            subject("granted_by_subject", "부여 계정"),
            col("reason", "사유", "varchar(500)"),
            col("version", "버전", "integer", default="1"),
        ],
    ),
    table(
        SA,
        "결재 재배정",
        "team",
        "DSN-31 F52(Q1). 퇴사·장기 부재 시 단계 담당자 재배정 사건. 원 단계 person_id는 바꾸지 않고 최신 회차를 읽는다",
        [
            col("document_id", "결재 문서", "bigint"),
            col("step_id", "결재 단계", "bigint"),
            person(),
            col("assignment_seq", "재배정 회차", "integer"),
            col("reason", "사유", "varchar(500)"),
            subject("assigned_by_subject", "배정 계정"),
        ],
    ),
]

CORE_TABLES = [
    core_table(
        WM,
        "공간 멤버십",
        "DSN-31 F51(Q1, 실제 도입). TEAM 공간 회원·역할. 세대 복사 대상 아님. 마지막 OWNER 제거 금지(SERVICE)",
        [
            col("workspace_id", "공간", "bigint"),
            col("user_id", "계정", "bigint"),
            col(
                "platform_role",
                "공간 역할",
                "varchar(10)",
                rule="OWNER / ADMIN / MEMBER",
            ),
            col(
                "status",
                "상태",
                "varchar(12)",
                default="'ACTIVE'",
                rule="ACTIVE / SUSPENDED / LEFT",
            ),
            col("version", "버전", "integer", default="1"),
            col("joined_at", "가입 시각", "timestamptz", default="now()"),
            col("changed_at", "변경 시각", "timestamptz", default="now()"),
            col("ended_at", "탈퇴 시각", "timestamptz", nullable=True),
        ],
    ),
    core_table(
        WI,
        "공간 초대",
        "DSN-31 F51(Q1). 기존 계정 대상 초대. token은 해시만 저장, 1회·만료·철회·재발급",
        [
            col("workspace_id", "공간", "bigint"),
            col("target_user_id", "초대 대상", "bigint"),
            col("invited_by_user_id", "초대한 계정", "bigint"),
            col("accepted_by_user_id", "수락 계정", "bigint", nullable=True),
            col("token_hash", "토큰 해시", "varchar(64)"),
            col(
                "state",
                "상태",
                "varchar(12)",
                default="'PENDING'",
                rule="PENDING / ACCEPTED / REVOKED / EXPIRED",
            ),
            col("version", "버전", "integer", default="1"),
            col("created_at", "생성 시각", "timestamptz", default="now()"),
            col("expires_at", "만료 시각", "timestamptz"),
            col("closed_at", "종결 시각", "timestamptz", nullable=True),
        ],
    ),
    core_table(
        TR,
        "TEAM 생성 영수증",
        "DSN-31 F51(Q1). TEAM 생성 멱등(아직 S가 없어 계정 기준). 개인 공간 초기화와 무관하게 유지",
        [
            col("user_id", "계정", "bigint"),
            col("request_key", "요청 키", "varchar(100)"),
            col("request_hash", "요청 해시", "varchar(64)"),
            col("team_workspace_id", "만든 TEAM 공간", "bigint"),
            col("created_at", "생성 시각", "timestamptz", default="now()"),
        ],
    ),
]

ERP_TABLES = [
    {
        **_table(
            EP,
            "결재 확정 통제",
            "control",
            "DSN-31 F44(Q6). ERP 문서 종류별 GW 승인 필수 정책(ERP 소유). 기본 OFF, 적용일 이후 새 확정만, 과거 확정본 소급 없음",
            [
                col(
                    "document_kind",
                    "ERP 문서 종류",
                    "varchar(20)",
                    rule="PURCHASE_INVOICE / PURCHASE_ORDER / EXPENSE_CLAIM",
                ),
                col(
                    "mode",
                    "정책",
                    "varchar(10)",
                    default="'OFF'",
                    rule="OFF / REQUIRED",
                ),
                col("policy_version", "정책 버전", "integer"),
                col("effective_from", "적용 시작 월", "varchar(7)", rule="'YYYY-MM'"),
                col("reason", "변경 사유", "varchar(500)"),
            ],
        ),
        "phase": "DSN-31",
    },
    {
        **_table(
            EV,
            "결재 확정 증빙",
            "control",
            "DSN-31 F44(Q6). REQUIRED 정책으로 확정할 때 ERP가 GW 승인을 읽어 검사한 결과(ERP 트랜잭션 안에서 저장). GW에는 쓰지 않는다",
            [
                col("document_kind", "ERP 문서 종류", "varchar(20)"),
                col("document_no", "ERP 문서 번호", "varchar(40)"),
                col("policy_version", "정책 버전", "integer"),
                col("gw_document_no", "GW 문서 번호", "varchar(40)", rule="스냅샷"),
                col("gw_round_no", "GW 회차", "integer"),
                col("gw_final_event_seq", "GW 최종 사건 순번", "integer"),
                col("approval_digest", "승인 digest", "varchar(64)"),
                col("verified_at", "검사 시각", "timestamptz", default="now()"),
            ],
        ),
        "phase": "DSN-31",
    },
]

EXT_COLUMNS = {
    "gw.person": [
        col(
            "organization_unit_id",
            "현재 조직",
            "bigint",
            nullable=True,
            rule="DSN-31 D81 — HR 부서 스냅샷",
        )
    ],
    "gw.route_step": [
        col(
            "participant_role",
            "참여 구분",
            "varchar(10)",
            default="'APPROVER'",
            rule="DSN-31 Q3 " + " / ".join(ROLES),
        )
    ],
    "gw.approval_step": [
        col(
            "participant_role",
            "참여 구분",
            "varchar(10)",
            default="'APPROVER'",
            rule="DSN-31 Q3 " + " / ".join(ROLES),
        ),
        col(
            "organization_code",
            "상신 당시 조직 코드",
            "varchar(30)",
            nullable=True,
            rule="DSN-31 스냅샷",
        ),
        col("organization_name", "상신 당시 조직명", "varchar(100)", nullable=True),
    ],
    "gw.approval_document": [
        col(
            "policy_version",
            "결재 정책 버전",
            "smallint",
            default="1",
            rule="DSN-31 1 순차 단일 / 2 병렬·합의·전결·위임",
        ),
        col("authority_rule_id", "적용 전결 규칙", "bigint", nullable=True),
        col(
            "auth_mode",
            "인증 방식",
            "varchar(12)",
            default="'SIMULATION'",
            rule="DSN-31 SIMULATION 체험 역할 / IDENTITY 실제 계정(TEAM)",
        ),
        col("drafter_org_code", "기안 당시 조직 코드", "varchar(30)", nullable=True),
        col("drafter_org_name", "기안 당시 조직명", "varchar(100)", nullable=True),
    ],
    "gw.approval_event": [
        col(
            "on_behalf_of_person_id",
            "위임한 원 담당자",
            "bigint",
            nullable=True,
            rule="DSN-31 Q3 위임 결재",
        ),
        col(
            "details",
            "상세",
            "jsonb",
            nullable=True,
            rule="재배정 전후 담당자 코드·회차 등",
        ),
    ],
    "gw.board_post": [
        col(
            "visibility",
            "게시 범위",
            "varchar(12)",
            default="'WORKSPACE'",
            rule="DSN-31 WORKSPACE / ORG",
        ),
        col("audience_org_id", "대상 조직", "bigint", nullable=True),
    ],
    "core.app_user": [
        col(
            "subject_key",
            "계정 주체 키",
            "uuid",
            default="gen_random_uuid()",
            rule="DSN-31 서버 생성·불변. 업무 테이블은 이 값을 스냅샷",
        )
    ],
    "core.workspace": [
        col(
            "name", "공간 이름", "varchar(100)", nullable=True, rule="DSN-31 TEAM 필수"
        ),
        col(
            "access_version",
            "접근 버전",
            "bigint",
            default="1",
            rule="멤버십·권한이 바뀌면 +1",
        ),
    ],
    "core.auth_session": [
        col(
            "active_workspace_id",
            "활성 공간",
            "bigint",
            nullable=True,
            rule="DSN-31 공간 전환",
        ),
        col("context_version", "문맥 버전", "bigint", default="1"),
        col(
            "assurance_level",
            "인증 강도",
            "varchar(20)",
            default="'PASSWORD'",
            rule="PASSWORD / VERIFIED_MFA / MOCK_MFA",
        ),
        col("assurance_provider", "추가 인증 공급자", "varchar(80)", nullable=True),
        col("assurance_verified_at", "추가 인증 시각", "timestamptz", nullable=True),
        col("assurance_expires_at", "추가 인증 만료", "timestamptz", nullable=True),
    ],
}

CONSTRAINTS = []
for t in TABLES + ERP_TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t in CORE_TABLES:
    CONSTRAINTS.append(c(t["name"], "PK", ["id"], reason="기본키"))
kinds = q(KINDS)
CONSTRAINTS += [
    # 전결·위임
    c(AR, "UK", S + ["code", "version"], reason="코드·버전 유일"),
    c(
        AR,
        "CHECK",
        [
            "code",
            "document_kind",
            "amount_from",
            "amount_to",
            "final_seq",
            "effective_to",
        ],
        f"code {CODE} AND document_kind IN ({kinds})",
        "코드·문서 유형",
    ),
    c(
        AR,
        "CHECK",
        [
            "amount_from",
            "amount_to",
            "final_seq",
            "effective_from",
            "effective_to",
            "currency",
        ],
        "effective_from ~ '^[0-9]{4}-(0[1-9]|1[0-2])$' AND (effective_to IS NULL OR (effective_to ~ '^[0-9]{4}-(0[1-9]|1[0-2])$' AND effective_to >= effective_from)) AND amount_from >= 0 AND (amount_to IS NULL OR amount_to > amount_from) AND final_seq BETWEEN 1 AND 3 AND currency ~ '^[A-Z]{3}$' AND version > 0",
        "금액 구간·단계·기간",
    ),
    c(
        AR,
        "SERVICE/DB_POLICY",
        ["final_seq"],
        "상신 때 (문서 유형, 통화, 금액, 상신 월)에 맞는 활성 규칙 1건을 찾아 문서에 고정, final_seq 뒤 단계는 SKIPPED. 겹치는 활성 규칙은 저장 거부. 다른 통화 자동 비교 금지, 규칙 없으면 전 단계",
        "전결 적용(Q3)",
    ),
    c(
        DG,
        "CHECK",
        [
            "delegator_person_id",
            "delegate_person_id",
            "starts_at",
            "ends_at",
            "max_amount",
            "reason",
        ],
        "delegator_person_id <> delegate_person_id AND ends_at > starts_at AND (max_amount IS NULL OR max_amount > 0) AND char_length(btrim(reason)) >= 2 AND version > 0",
        "자기 위임 금지·기간",
    ),
    c(
        DG,
        "SERVICE/DB_POLICY",
        ["delegate_person_id"],
        "결재 처리 순간 DB 시각으로 유효(회수 전·기간 안·유형·한도) 재검사. 연쇄 위임(수임자가 다시 위임)·기안자 본인 문서 대리 결재 금지. 회수와 결재는 문서 잠금으로 직렬화. 사건에 원 담당자(on_behalf_of)와 수행자 모두 기록",
        "위임 결재(Q3)",
    ),
    c(DG, "INDEX", S + ["delegator_person_id", "starts_at"], reason="유효 위임 조회"),
    # 댓글
    c(
        CM,
        "CHECK",
        ["target_kind", "post_id", "document_id", "status", "deleted_at", "body"],
        "target_kind IN ('POST', 'DOCUMENT') AND ((target_kind = 'POST') = (post_id IS NOT NULL)) AND ((target_kind = 'DOCUMENT') = (document_id IS NOT NULL)) AND status IN ('ACTIVE', 'DELETED') AND ((status = 'DELETED') = (deleted_at IS NOT NULL)) AND char_length(btrim(body)) >= 1 AND revision_no > 0 AND version > 0",
        "대상·상태",
    ),
    c(CM, "INDEX", S + ["post_id"], reason="게시글 댓글"),
    c(CM, "INDEX", S + ["document_id"], reason="문서 댓글"),
    c(CR, "UK", S + ["comment_id", "revision_no"], reason="댓글·revision 유일"),
    # 일정
    c(CE, "UK", S + ["event_no"], reason="일정 번호 유일"),
    c(
        CE,
        "CHECK",
        ["scope", "organization_unit_id", "starts_at", "ends_at", "status"],
        "scope IN ('PERSONAL', 'DEPARTMENT') AND ((scope = 'DEPARTMENT') = (organization_unit_id IS NOT NULL)) AND ends_at > starts_at AND status IN ('ACTIVE', 'CANCELLED') AND version > 0",
        "공개 범위·기간",
    ),
    c(CE, "INDEX", S + ["starts_at"], reason="기간 조회"),
    c(EA, "UK", S + ["event_id", "person_id"], reason="일정·참석자 1행"),
    c(
        EA,
        "CHECK",
        ["response", "responded_at"],
        "response IN ('PENDING', 'ACCEPTED', 'DECLINED') AND ((response = 'PENDING') = (responded_at IS NULL))",
        "응답",
    ),
    # 알림
    c(NT, "UK", S + ["recipient_id", "event_key"], reason="받는 사람·사건 1건(중복 0)"),
    c(
        NT,
        "CHECK",
        ["kind", "ref_kind"],
        "kind IN ('APPROVAL_ARRIVED', 'APPROVAL_DONE', 'REJECTED', 'WITHDRAWN', 'NOTICE', 'COMMENT', 'EVENT', 'MENTION') AND ref_kind IN ('DOCUMENT', 'POST', 'EVENT', 'CHANNEL')",
        "종류",
    ),
    c(NT, "INDEX", S + ["recipient_id", "read_at"], reason="안 읽은 알림"),
    c(
        NT,
        "SERVICE/DB_POLICY",
        ["event_key"],
        "결재·게시·댓글·일정 변경과 같은 트랜잭션에서 생성. 받는 사람이 그 대상을 읽을 권한이 없으면 만들지 않는다(TEAM ACL)",
        "알림 생성",
    ),
    # 채팅
    c(CH, "UK", S + ["code"], reason="대화방 코드 유일"),
    c(
        CH,
        "CHECK",
        ["code", "channel_kind", "last_seq"],
        f"code {CODE} AND channel_kind IN ('DIRECT', 'GROUP') AND last_seq >= 0",
        "코드·구분",
    ),
    c(CHM, "UK", S + ["channel_id", "person_id"], reason="대화방·참여자 1행"),
    c(
        CHM,
        "CHECK",
        ["joined_at", "left_at", "last_read_seq"],
        "(left_at IS NULL OR left_at >= joined_at) AND last_read_seq >= 0",
        "참여 기간",
    ),
    c(CHG, "UK", S + ["channel_id", "seq"], reason="대화방·순번 유일"),
    c(
        CHG,
        "UK",
        S + ["channel_id", "author_id", "client_key"],
        reason="재전송 중복 제거",
    ),
    c(
        CHG,
        "CHECK",
        ["seq", "body"],
        "seq > 0 AND char_length(btrim(body)) >= 1",
        "순번·내용",
    ),
    c(
        CHG,
        "SERVICE/DB_POLICY",
        ["seq"],
        "순번 = 대화방 last_seq + 1(대화방 행 잠금). 나간 참여자는 보낼 수 없고 나간 뒤 메시지를 받지 않는다. 다른 공간 대화방 id 접근 거부",
        "메시지 순번",
    ),
    # 조직(D81)
    c(OU, "UK", S + ["code"], reason="부서 코드 유일"),
    c(
        OU,
        "CHECK",
        ["code", "parent_id"],
        f"code {CODE} AND (parent_id IS NULL OR parent_id <> id) AND version > 0",
        "코드·자기 상위 금지",
    ),
    c(
        OU,
        "SERVICE/DB_POLICY",
        ["code"],
        "fs.hr.interface.departments()를 'HR에서 가져오기'로 반영(코드 = HR 부서 코드, 자동 동기화 없음). 순환·비활성 상위 금지. HR 꺼짐이면 마지막 가져온 값 유지(D81)",
        "조직 = HR 스냅샷",
    ),
    # 실제 도입 A(GW)
    c(CS, "UK", S, reason="공간·세대당 설정 1건"),
    c(CS, "CHECK", ["authz_version"], "authz_version > 0", "권한 버전"),
    c(IB, "UK", S + ["person_id"], reason="직원당 연결 1건"),
    c(IB, "UK", S + ["subject_key"], reason="계정당 연결 1건"),
    c(
        IB,
        "CHECK",
        ["state", "activated_at", "closed_at"],
        "(state = 'PENDING' AND activated_at IS NULL AND closed_at IS NULL) OR (state = 'ACTIVE' AND activated_at IS NOT NULL AND closed_at IS NULL) OR (state = 'SUSPENDED' AND activated_at IS NOT NULL AND closed_at IS NOT NULL) OR (state = 'CANCELLED' AND activated_at IS NULL AND closed_at IS NOT NULL)",
        "상태별 시각",
    ),
    c(RG, "UK", S + ["person_id", "role_key"], reason="직원·권한 1행"),
    c(
        RG,
        "CHECK",
        ["role_key", "reason"],
        "role_key IN ('ORG_ADMIN', 'ROUTE_ADMIN', 'BOARD_PUBLISHER', 'SECURITY_ADMIN', 'AUDITOR') AND char_length(btrim(reason)) >= 2 AND version > 0",
        "권한·사유",
    ),
    c(DR, "UK", S + ["document_id", "person_id"], reason="문서·열람자 1행"),
    c(DR, "INDEX", S + ["person_id", "is_active"], reason="열람 가능 문서"),
    c(
        "gw.approval_step",
        "UK",
        S + ["document_id", "id"],
        reason="DSN-31 재배정 복합 참조 대상",
    ),
    c(SA, "UK", S + ["step_id", "assignment_seq"], reason="단계·회차 유일"),
    c(
        SA,
        "CHECK",
        ["assignment_seq", "reason"],
        "assignment_seq > 0 AND char_length(btrim(reason)) >= 2",
        "회차·사유",
    ),
    c(
        SA,
        "SERVICE/DB_POLICY",
        ["person_id"],
        "진행 중 결재선 편집 금지. 퇴사·장기 부재만 관리자 사유로 재배정, 이미 승인된 단계는 바꾸지 않는다. 사건 STEP_REASSIGNED와 같은 트랜잭션",
        "재배정",
    ),
    # 실제 도입 A(core)
    c(WM, "UK", ["workspace_id", "user_id"], reason="공간·계정 1행"),
    c(
        WM,
        "CHECK",
        ["platform_role", "status", "ended_at", "version"],
        "platform_role IN ('OWNER', 'ADMIN', 'MEMBER') AND status IN ('ACTIVE', 'SUSPENDED', 'LEFT') AND ((status = 'LEFT') = (ended_at IS NOT NULL)) AND version > 0",
        "역할·상태",
    ),
    c(WM, "INDEX", ["user_id", "status"], reason="내 공간 목록"),
    c(
        WM,
        "SERVICE/DB_POLICY",
        ["status"],
        "TEAM 공간에만 생성(개인·게스트에는 만들지 않음). 마지막 OWNER 제거 금지. 회수와 결재 경합은 공간 잠금으로 직렬화 — 회수가 먼저 commit되면 후속 결재 거부. 변경 시 core.workspace.access_version +1",
        "멤버십(Q1)",
    ),
    c(WI, "UK", ["token_hash"], reason="토큰 해시 유일"),
    c(
        WI,
        "UK_PARTIAL",
        ["workspace_id", "target_user_id"],
        "UNIQUE (workspace_id, target_user_id) WHERE state = 'PENDING'",
        "대상당 대기 초대 1건",
    ),
    c(
        WI,
        "CHECK",
        ["state", "closed_at", "accepted_by_user_id", "expires_at"],
        "state IN ('PENDING', 'ACCEPTED', 'REVOKED', 'EXPIRED') AND expires_at > created_at AND ((state = 'PENDING') = (closed_at IS NULL)) AND ((state = 'ACCEPTED') = (accepted_by_user_id IS NOT NULL)) AND (accepted_by_user_id IS NULL OR accepted_by_user_id = target_user_id) AND version > 0",
        "상태·만료·수락자",
    ),
    c(TR, "UK", ["user_id", "request_key"], reason="계정·요청 키 유일"),
    # core 기존 표 보강
    c("core.app_user", "UK", ["subject_key"], reason="DSN-31 주체 키 유일"),
    c(
        "core.workspace",
        "CHECK",
        ["access_version"],
        "access_version > 0",
        "DSN-31 접근 버전",
    ),
    c(
        "core.auth_session",
        "CHECK",
        [
            "context_version",
            "assurance_level",
            "assurance_provider",
            "assurance_verified_at",
            "assurance_expires_at",
        ],
        "context_version > 0 AND assurance_level IN ('PASSWORD', 'VERIFIED_MFA', 'MOCK_MFA') AND ((assurance_verified_at IS NULL) = (assurance_expires_at IS NULL)) AND (assurance_expires_at IS NULL OR assurance_expires_at > assurance_verified_at) AND (assurance_level = 'PASSWORD' OR (assurance_provider IS NOT NULL AND assurance_verified_at IS NOT NULL))",
        "DSN-31 문맥·추가 인증",
    ),
    c(
        "core.auth_session",
        "SERVICE/DB_POLICY",
        ["active_workspace_id"],
        "공간 선택 API는 클라이언트가 준 workspaceId를 믿지 않고 활성 멤버십(TEAM) 또는 소유(MEMBER)를 확인. 전환 시 context_version +1, 화면 캐시 폐기. 초기 TEAM 공간에서는 GW만 허용, 미검증 솔루션 API는 공통 스코프에서 차단",
        "DSN-31 공간 전환(Q1)",
    ),
    # GW 기존 표 보강
    c(
        "gw.route_step",
        "CHECK",
        ["participant_role"],
        f"participant_role IN ({q(ROLES)})",
        "DSN-31 참여 구분",
    ),
    c(
        "gw.approval_step",
        "CHECK",
        ["participant_role"],
        f"participant_role IN ({q(ROLES)})",
        "DSN-31 참여 구분",
    ),
    c(
        "gw.approval_document",
        "CHECK",
        ["policy_version", "auth_mode", "authority_rule_id"],
        "policy_version IN (1, 2) AND auth_mode IN ('SIMULATION', 'IDENTITY') AND (policy_version = 2 OR authority_rule_id IS NULL)",
        "DSN-31 정책 버전·인증 방식",
    ),
    c(
        "gw.approval_document",
        "SERVICE/DB_POLICY",
        ["policy_version"],
        "v2: 같은 단계(seq)의 APPROVER 전원 승인 시 다음 단계, 한 명 반려면 종결(나머지 SKIPPED). CONSENT 반대는 반려, REFERENCE는 승인 조건 아님(종결 시 미응답 SKIPPED). 동시 마지막 승인도 완료 사건 1개. v1 문서는 기존 규칙 그대로(자동 v2 전환 없음). TEAM(IDENTITY)은 서버 인증 주체 → 직원 연결로 담당자 결정, 클라이언트 담당자 선택 금지",
        "DSN-31 결재 정책 v2(Q3)·인증 방식(Q1)",
    ),
    c(
        "gw.board_post",
        "CHECK",
        ["visibility", "audience_org_id"],
        "visibility IN ('WORKSPACE', 'ORG') AND ((visibility = 'ORG') = (audience_org_id IS NOT NULL))",
        "DSN-31 게시 범위",
    ),
    # ERP 확정 통제
    c(EP, "UK", S + ["document_kind", "policy_version"], reason="종류·버전 유일"),
    c(
        EP,
        "CHECK",
        ["document_kind", "mode", "policy_version", "reason"],
        "effective_from ~ '^[0-9]{4}-(0[1-9]|1[0-2])$' AND document_kind IN ('PURCHASE_INVOICE', 'PURCHASE_ORDER', 'EXPENSE_CLAIM') AND mode IN ('OFF', 'REQUIRED') AND policy_version >= 1 AND char_length(btrim(reason)) >= 2",
        "종류·정책",
    ),
    c(
        EP,
        "SERVICE/DB_POLICY",
        ["mode"],
        "적용 정책 = 그 종류의 적용 시작 월 ≤ 이번 달인 최신 버전. REQUIRED면 모든 확정 경로(화면·API·배치)에서 fs.gw.interface.approvals()로 최종 승인·상신 digest = 현재 원문 digest를 확인, 미승인·진행·반려·원문 변경·GW 꺼짐·조회 실패면 확정 거부(우회 없음). 정책 변경은 권한·사유·감사, 과거 확정본은 그대로",
        "ERP 확정 통제(Q6)",
    ),
    c(
        EV,
        "UK",
        S + ["document_kind", "document_no", "gw_document_no", "gw_round_no"],
        reason="문서·GW 회차 1건",
    ),
    c(
        EV,
        "CHECK",
        ["approval_digest", "gw_round_no", "gw_final_event_seq"],
        "approval_digest ~ '^[0-9a-f]{64}$' AND gw_round_no > 0 AND gw_final_event_seq > 0",
        "digest·회차",
    ),
]
for t, cols_ in [
    (CR, ["comment_id"]),
    (EA, ["person_id"]),
    (CHM, ["person_id"]),
    (OU, ["parent_id"]),
    (SA, ["document_id"]),
    (EV, ["document_kind", "document_no"]),
]:
    CONSTRAINTS.append(c(t, "INDEX", S + cols_, reason="조회"))

RELATIONS = [
    dict(
        source=t["name"],
        columns=S,
        target="core.data_generation",
        target_columns=["workspace_id", "id"],
        on_delete="RESTRICT",
        on_update="RESTRICT",
        note="같은 참조 범위 유지",
    )
    for t in TABLES + ERP_TABLES
]
PS = "gw.person"
RELATIONS += [
    r(DG, ["delegator_person_id"], PS, "위임자"),
    r(DG, ["delegate_person_id"], PS, "수임자"),
    r(CM, ["post_id"], "gw.board_post", "게시글"),
    r(CM, ["document_id"], "gw.approval_document", "결재 문서"),
    r(CM, ["author_id"], PS, "작성자"),
    r(CR, ["comment_id"], CM, "댓글"),
    r(CE, ["owner_id"], PS, "등록자"),
    r(CE, ["organization_unit_id"], OU, "부서"),
    r(EA, ["event_id"], CE, "일정"),
    r(EA, ["person_id"], PS, "참석자"),
    r(NT, ["recipient_id"], PS, "받는 사람"),
    r(CH, ["created_by_id"], PS, "만든 사람"),
    r(CHM, ["channel_id"], CH, "대화방"),
    r(CHM, ["person_id"], PS, "참여자"),
    r(CHG, ["channel_id"], CH, "대화방"),
    r(CHG, ["author_id"], PS, "보낸 사람"),
    r(OU, ["parent_id"], OU, "상위 부서"),
    r(IB, ["person_id"], PS, "직원"),
    r(RG, ["person_id"], PS, "직원"),
    r(DR, ["document_id"], "gw.approval_document", "결재 문서"),
    r(DR, ["person_id"], PS, "열람자"),
    r(SA, ["person_id"], PS, "새 담당자"),
    dict(
        source=SA,
        columns=S + ["document_id", "step_id"],
        target="gw.approval_step",
        target_columns=S + ["document_id", "id"],
        on_delete="RESTRICT",
        on_update="RESTRICT",
        note="단계가 그 문서 소속",
    ),
    r(PS, ["organization_unit_id"], OU, "현재 조직(D81)"),
    r("gw.approval_document", ["authority_rule_id"], AR, "적용 전결 규칙"),
    r("gw.approval_event", ["on_behalf_of_person_id"], PS, "위임한 원 담당자"),
    r("gw.board_post", ["audience_org_id"], OU, "대상 조직"),
]


def core_r(source, column, target, note):
    return dict(
        source=source,
        columns=[column],
        target=target,
        target_columns=["id"],
        on_delete="RESTRICT",
        on_update="RESTRICT",
        note=note,
    )


RELATIONS += [
    core_r(WM, "workspace_id", "core.workspace", "공간"),
    core_r(WM, "user_id", "core.app_user", "계정"),
    core_r(WI, "workspace_id", "core.workspace", "공간"),
    core_r(WI, "target_user_id", "core.app_user", "초대 대상"),
    core_r(WI, "invited_by_user_id", "core.app_user", "초대한 계정"),
    core_r(WI, "accepted_by_user_id", "core.app_user", "수락 계정"),
    core_r(TR, "user_id", "core.app_user", "계정"),
    core_r(TR, "team_workspace_id", "core.workspace", "만든 TEAM"),
    core_r("core.auth_session", "active_workspace_id", "core.workspace", "활성 공간"),
]
STATES = [
    dict(
        table=IB,
        column="state",
        values=["PENDING", "ACTIVE", "SUSPENDED", "CANCELLED"],
        default="PENDING",
        transition="PENDING→ACTIVE|CANCELLED; ACTIVE→SUSPENDED→ACTIVE",
    ),
    dict(
        table=WM,
        column="status",
        values=["ACTIVE", "SUSPENDED", "LEFT"],
        default="ACTIVE",
        transition="ACTIVE↔SUSPENDED; ACTIVE|SUSPENDED→LEFT; LEFT→ACTIVE(재가입)",
    ),
    dict(
        table=WI,
        column="state",
        values=["PENDING", "ACCEPTED", "REVOKED", "EXPIRED"],
        default="PENDING",
        transition="PENDING→ACCEPTED|REVOKED|EXPIRED",
    ),
    dict(
        table=CM,
        column="status",
        values=["ACTIVE", "DELETED"],
        default="ACTIVE",
        transition="ACTIVE→DELETED",
    ),
    dict(
        table=CE,
        column="status",
        values=["ACTIVE", "CANCELLED"],
        default="ACTIVE",
        transition="ACTIVE→CANCELLED",
    ),
]

# 기존 제약 교체 — (표, 종류, 찾을 문자열, 바꾸는 함수). 하나라도 개수가 다르면 아무것도 바꾸지 않는다.
SRC_OLD = "(kind='ERP_PURCHASE' AND source_kind IS NOT NULL AND source_kind='PURCHASE_INVOICE' AND"
SRC_NEW = (
    "(kind<>'GENERAL' AND source_kind IS NOT NULL AND source_kind = CASE kind "
    + " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in SOURCE.items())
    + " END AND"
)
WS_KIND_OLD = "workspace_kind IN ('MEMBER','GUEST','TEMPLATE')"
WS_SHAPE_OLD = "OR (workspace_kind = 'TEMPLATE' AND owner_user_id IS NULL AND guest_session_key IS NULL AND expires_at IS NULL AND guest_actor_key IS NULL)"
REPLACE = [
    (
        "gw.approval_document",
        "CHECK",
        "kind IN ('GENERAL','ERP_PURCHASE')",
        lambda e: e.replace(
            "kind IN ('GENERAL','ERP_PURCHASE')",
            "kind IN ('GENERAL','ERP_PURCHASE','ERP_PO','ERP_EXPENSE','PLM_ECO')",
        ),
    ),
    ("gw.approval_document", "CHECK", SRC_OLD, lambda e: e.replace(SRC_OLD, SRC_NEW)),
    (
        "gw.approval_document",
        "CHECK",
        "source_status IN ('draft','confirmed','cancelled')",
        lambda e: (
            "source_status IS NULL OR char_length(btrim(source_status)) BETWEEN 1 AND 20"
        ),
    ),
    (
        "gw.approval_document",
        "UK_PARTIAL",
        "AND kind='ERP_PURCHASE'",
        lambda e: e.replace("AND kind='ERP_PURCHASE'", "AND kind<>'GENERAL'"),
    ),
    (
        "gw.approval_event",
        "CHECK",
        "event_type IN ('CREATED',",
        lambda e: e.replace(
            "'RESUBMISSION_CREATED')",
            "'RESUBMISSION_CREATED','CONSENTED','OPPOSED','SKIPPED','STEP_REASSIGNED','READER_GRANTED','READER_REVOKED')",
        ),
    ),
    (
        "gw.approval_event",
        "CHECK",
        "event_type NOT IN ('REJECTED','WITHDRAWN')",
        lambda e: e.replace("('REJECTED','WITHDRAWN')", REASON_EVENTS),
    ),
    (
        "gw.approval_event",
        "CHECK",
        "(event_type IN ('APPROVED','REJECTED') AND step_seq",
        lambda e: e.replace("('APPROVED','REJECTED')", STEP_EVENTS),
    ),
    (
        "core.workspace",
        "CHECK",
        WS_KIND_OLD,
        lambda e: e.replace(
            WS_KIND_OLD, "workspace_kind IN ('MEMBER','GUEST','TEMPLATE','TEAM')"
        ),
    ),
    (
        "core.workspace",
        "CHECK",
        WS_SHAPE_OLD,
        lambda e: e.replace(
            WS_SHAPE_OLD,
            WS_SHAPE_OLD
            + " OR (workspace_kind = 'TEAM' AND owner_user_id IS NULL AND guest_session_key IS NULL AND expires_at IS NULL AND guest_actor_key IS NULL AND name IS NOT NULL AND char_length(btrim(name)) BETWEEN 1 AND 100)",
        ),
    ),
]
# 병렬 결재(Q3): 같은 단계 여러 명 → 단계 순번 유일 키를 없앤다(사람 유일 키는 유지)
DROP = [
    ("gw.route_step", ["route_id", "seq"]),
    ("gw.approval_step", ["document_id", "seq"]),
]


def _apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn31은 schema-target.json에만 적용한다")
    tables = {t["name"]: t for t in d["tables"]}
    if "hr.employee" not in tables:
        raise SystemExit("apply_dsn30을 먼저 적용한다")
    planned_names = {t["name"] for t in TABLES + CORE_TABLES + ERP_TABLES}
    if planned_names <= set(tables):
        return False
    if AR in tables:
        # GW-a implements the demo subset, not the TEAM/ERP design. Rebuild the
        # planned GW from its canonical initial definition, then carry forward
        # extra implemented columns (e.g. the HR employee code snapshot).
        implemented = {n: t for n, t in tables.items() if n.startswith(P)}
        allowed = {t["name"] for t in apply_fs030a.TABLES + TABLES}
        if set(implemented) - allowed:
            raise SystemExit("미지원 GW 확장이 있어 목표 설계 재생성을 중단한다")
        candidate = copy.deepcopy(d)
        candidate["tables"] = [
            t for t in candidate["tables"] if not t["name"].startswith(P)
        ] + copy.deepcopy(apply_fs030a.TABLES)
        candidate["constraints"] = [
            c for c in candidate["constraints"] if not c["table"].startswith(P)
        ] + copy.deepcopy(apply_fs030a.CONSTRAINTS)
        candidate["relations"] = [
            r for r in candidate["relations"] if not r["source"].startswith(P)
        ] + copy.deepcopy(apply_fs030a.RELATIONS)
        candidate["states"] = [
            s for s in candidate["states"] if not s["table"].startswith(P)
        ] + copy.deepcopy(apply_fs030a.STATES)
        apply(candidate)
        for t in candidate["tables"]:
            if t["name"] in implemented:
                names = {c["name"] for c in t["columns"]}
                extra = [
                    c
                    for c in implemented[t["name"]]["columns"]
                    if c["name"] not in names
                ]
                at = (
                    len(t["columns"]) - 1
                    if t["columns"][-1]["name"] == "created_at"
                    else len(t["columns"])
                )
                t["columns"][at:at] = copy.deepcopy(extra)
        d.clear()
        d.update(candidate)
        return True
    missing = set(EXT_COLUMNS) - set(tables)
    hits = [
        [
            x
            for x in d["constraints"]
            if x["table"] == t and x["kind"] == k and needle in x.get("expression", "")
        ]
        for t, k, needle, _ in REPLACE
    ]
    drops = [
        [
            x
            for x in d["constraints"]
            if x["table"] == t and x["kind"] == "UK" and x["columns"] == S + cols
        ]
        for t, cols in DROP
    ]
    bad = [REPLACE[i][2][:40] for i, h in enumerate(hits) if len(h) != 1] + [
        DROP[i] for i, h in enumerate(drops) if len(h) != 1
    ]
    if missing or bad:
        raise SystemExit(f"대상이 없다: 표 {missing}, 제약 {bad}")
    for name, columns in EXT_COLUMNS.items():
        cols = tables[name]["columns"]
        at = len(cols) - 1 if cols[-1]["name"] == "created_at" else len(cols)
        cols[at:at] = [dict(x) for x in columns]
    for (t, k, needle, fn), (x,) in zip(REPLACE, hits):
        x["expression"] = fn(x["expression"])
    for (x,) in drops:
        d["constraints"].remove(x)
    for code in d["code_lists"]:
        if (
            code["target"] == "core.workspace"
            and code["column"] == "workspace_kind"
            and "TEAM" not in code["values"]
        ):
            code["values"] = [*code["values"], "TEAM"]
    d["tables"].extend(TABLES + CORE_TABLES + ERP_TABLES)
    d["constraints"].extend(CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"].extend(STATES)
    d.update(version="target-0.19.0", task="DSN-31", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.19.0",
            task="DSN-31",
            date="2026-10-05",
            change="GW 보강: 체험(전결 규칙·위임·댓글·일정·알림·채팅 10테이블, 결재 대상 ERP 발주·지출결의·PLM ECO, 병렬·합의 — 단계 순번 유일 키 제거·참여 구분) + 조직 단위(HR 스냅샷, D81) + 실제 도입 A 설계(GW 협업 설정·직원 계정 연결·업무 권한·문서 열람·재배정, core TEAM 공간·멤버십·초대·생성 영수증·세션 활성 공간·추가 인증) + ERP 확정 통제(정책·증빙). 업무 스키마 간 FK 0",
            status="설계 전용(실제 도입 A는 별도 트랙에서 개발)",
        )
    )
    return True


def apply(d):
    """회사 근태 COMPANY를 보존하면서 미구현 TEAM 목표 설계를 확장한다."""
    company_kind = "workspace_kind IN ('MEMBER','GUEST','TEMPLATE','COMPANY')"
    company_shape = "OR (workspace_kind IN ('TEMPLATE','COMPANY') AND owner_user_id IS NULL AND guest_session_key IS NULL AND expires_at IS NULL AND guest_actor_key IS NULL)"
    constraints = d["constraints"]
    if not any(
        c["table"] == "core.workspace" and c.get("expression") == company_kind
        for c in constraints
    ):
        return _apply(d)
    candidate = copy.deepcopy(d)
    for c in candidate["constraints"]:
        if c["table"] != "core.workspace":
            continue
        c["expression"] = (
            c.get("expression", "")
            .replace(company_kind, WS_KIND_OLD)
            .replace(company_shape, WS_SHAPE_OLD)
        )
    changed = _apply(candidate)
    if not changed:
        return False
    for c in candidate["constraints"]:
        if c["table"] != "core.workspace":
            continue
        e = c.get("expression", "")
        if "workspace_kind IN ('MEMBER','GUEST','TEMPLATE','TEAM')" in e:
            c["expression"] = e.replace(
                "'TEMPLATE','TEAM')", "'TEMPLATE','TEAM','COMPANY')"
            )
        elif WS_SHAPE_OLD in e:
            c["expression"] = e.replace(WS_SHAPE_OLD, company_shape)
    d.clear()
    d.update(candidate)
    return True


def main():
    d = json.loads(TARGET.read_text(encoding="utf-8"))
    changed = apply(d)
    if changed:
        TARGET.write_text(
            json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    gw = [t for t in d["tables"] if t["name"].startswith(P)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                gw_tables=len(gw),
                constraints=len(d["constraints"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
