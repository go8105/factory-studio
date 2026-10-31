"""Unsigned operator report from one read-only snapshot; never release evidence."""

from uuid import uuid4

from sqlalchemy import text

from fs.gw.acceptance_execution import execute
from fs.gw.acceptance_preflight import read_transaction, snapshot, validate_request
from fs.gw.denial_catalog import CATALOG_VERSION, DENIAL_PROBES, FAMILIES, review_cases
from fs.gw.launch_gate import build
from fs.gw.operating_contract import OperatingPolicy, timestamp
from fs.gw.restored_denial import (
    CALENDAR_CASES,
    CHAT_CASES,
    DELEGATION_BOUND_CASES,
    DELEGATION_CASES,
    DELEGATION_RELATION_CASES,
    POST_CASES,
    STORED_DELEGATION_CASES,
)

# References are available synthetic tests, never current-company execution proof.
DENIAL_REVIEW = (
    ("OLD_SESSIONS", "LEGACY_FUNCTION_REFERENCE", ()),
    ("PENDING_AUTHENTICATION", "LEGACY_FUNCTION_REFERENCE", ()),
    ("CORE_ACCOUNT", "FIXED_SYNTHETIC_FRESH_AUTH", ("CORE_ACCOUNT",)),
    ("HR_AUTHORITY", "FIXED_SYNTHETIC_FRESH_AUTH", ("HR_AUTHORITY",)),
    ("GW_BINDING", "FIXED_SYNTHETIC_FRESH_AUTH", ("GW_BINDING",)),
    ("GW_ROLE", "FIXED_SYNTHETIC_FRESH_AUTH", ("GW_ROLE",)),
    ("DOCUMENT_ACL", "FIXED_SYNTHETIC_OBJECT_ACL", ("DOCUMENT_READER",)),
    (
        "COMPANY_MEMBERSHIP",
        "FIXED_SYNTHETIC_COMPANY_SCOPE",
        ("COMPANY_MEMBERSHIP", "FOREIGN_SCOPE"),
    ),
    ("POST_VISIBILITY", "FIXED_SYNTHETIC_POST_SCOPE", tuple(POST_CASES)),
    ("CHAT_MEMBERSHIP", "FIXED_SYNTHETIC_CHAT_SCOPE", tuple(CHAT_CASES)),
    ("CALENDAR_AUTHORIZATION", "FIXED_SYNTHETIC_CALENDAR_SCOPE", tuple(CALENDAR_CASES)),
    (
        "DELEGATION",
        "FIXED_SYNTHETIC_DELEGATION_BOUNDARIES",
        tuple(
            DELEGATION_CASES
            | DELEGATION_BOUND_CASES
            | DELEGATION_RELATION_CASES
            | STORED_DELEGATION_CASES
        ),
    ),
)
LEGACY_REFERENCE = "backend/tests/test_backup_journal_restore.py::test_actual_history_bound_restore_restricts_without_changing_source[False]"
LEGACY_REFERENCES = {
    key: LEGACY_REFERENCE for key in ("OLD_SESSIONS", "PENDING_AUTHENTICATION")
}
REMAINING = {
    "OLD_SESSIONS": "기존 합성 복원 시험의 옛 토큰 401 참조만 제공한다. 현재 회사·실접속/기기 세션 인수는 미실행이다.",
    "PENDING_AUTHENTICATION": "기존 합성 복원 시험의 미완료 인증 401 참조다. 실제 기기의 진행 중 인증·재시도 인수는 미실행이다.",
    "CORE_ACCOUNT": "새 닫힌 합성 복원본의 회수 계정 로그인 401 참조다. 실제 계정 회수 절차/SSO·실기기·현재 회사 인수는 미실행이다.",
    "HR_AUTHORITY": "새MFA 뒤 합성 복원본의 HR 권한 거부 참조다. 실제 HR 변경 수집의 무누락/직접SQL·운영도구·현재 회사 인수는 별도다.",
    "GW_BINDING": "새MFA 뒤 합성 복원본의 GW 연결 거부 참조다. 모든 연결 전이/실기기·현재 회사 회수 인수는 미실행이다.",
    "GW_ROLE": "새MFA 뒤 합성 복원본의 GW 역할 거부 참조다. 전체 역할/운영도구·현재 회사 회수 인수는 미실행이다.",
    "DOCUMENT_ACL": "합성 문서 참조자 회수의 상세/쓰기·목록검색 대조 참조다. 다른 회사 범위는 COMPANY_MEMBERSHIP에 분리했다. 전체 문서·현재 회사 인수는 미실행이다.",
    "COMPANY_MEMBERSHIP": "합성 회사 멤버십 회수·실제 두 번째 합성 회사 문서 범위 참조가 연결돼 있다. 현재 회사 멤버십/다른 회사·실기기 인수는 미실행이다.",
    "POST_VISIBILITY": "합성 조직 공개 필터와 백업 뒤 공개 범위 변경의 회사격리 참조다. 정정/재게시·모든 공개 조합·현재 회사 인수는 별도다.",
    "CHAT_MEMBERSHIP": "나간 합성 채널의 조회/전송·읽음/영수증과 회사격리 참조다. 재가입/동시성·읽음만의 guard 정책·현재 회사 인수는 별도다.",
    "CALENDAR_AUTHORIZATION": "합성 소유자/참석자 제외와 과거 응답 영수증·회사격리 참조다. 부서공개/응답만의 guard 정책·현재 회사 인수는 별도다.",
    "DELEGATION": "명시적 회수/과거 이력·원본 기간/금액/관계·저장 결함의 정책함수/회사ACL 참조다. 복원 전체위임회수를 원본 범위 판정으로 대신하지 않는다. fixture 삽입은 API 등록 성공이 아니며 ERP연동/동시성·전경로/현재 회사 인수는 미실행이다.",
}


def denial_review():
    checks = []
    for code, scope, cases in DENIAL_REVIEW:
        synthetic = review_cases(cases)
        references = (
            [item["testReference"] for item in synthetic]
            if cases
            else [LEGACY_REFERENCES[code]]
        )
        checks.append(
            {
                "code": code,
                "existingScope": scope,
                "testReference": references[0],
                "testReferences": references,
                "syntheticCases": synthetic,
                "remainingScope": REMAINING[code],
                "executionState": "NOT_EXECUTED",
                "currentCompanyVerified": False,
            }
        )
    return {
        "version": 2,
        "scope": "SELECTED_REVOCATION_BOUNDARIES",
        "coverageComplete": False,
        "result": "UNVERIFIED",
        "executionState": "NOT_EXECUTED",
        "revocationsComplete": False,
        "currentCompanyVerified": False,
        "syntheticExecutionImported": False,
        "referenceCatalog": {
            "version": CATALOG_VERSION,
            "fixedSyntheticCaseCount": len(DENIAL_PROBES),
            "observationFamilyCount": len(FAMILIES),
            "observationVersions": [family.observation_version for family in FAMILIES],
            "executionProfile": "RESTORED_DENIAL_ONLY",
            "executionScope": "NEW_OWNED_SYNTHETIC_DATABASE",
        },
        "checks": checks,
    }


def collect(engine, *, company_id, code_revision, public_keys, admin_login="admin"):
    validate_request(
        company_id=company_id, code_revision=code_revision, admin_login=admin_login
    )
    with read_transaction(engine) as c:
        current, preflight = snapshot(
            c,
            company_id=company_id,
            code_revision=code_revision,
            admin_login=admin_login.strip().lower(),
        )
        params = {"w": company_id, "g": current["generationId"]}
        policy_id = c.execute(
            text("""SELECT current_policy_revision_id FROM gw.operating_settings
            WHERE workspace_id=:w AND generation_id=:g"""),
            params,
        ).scalar_one()
        rows = (
            c.execute(
                text("""SELECT DISTINCT ON (kind) * FROM gw.operating_evidence
            WHERE workspace_id=:w AND generation_id=:g AND kind IN ('BACKUP','RESTORE','ACCEPTANCE')
            ORDER BY kind,recorded_at DESC,id DESC"""),
                params,
            )
            .mappings()
            .all()
        )
        policy = OperatingPolicy.model_validate(current["policy"])
        pair, evidence = execute(
            rows,
            connection=c,
            policy_id=policy_id,
            workspace_id=current["workspaceId"],
            generation_id=current["generationId"],
            policy=policy,
            code_revision=current["codeRevision"],
            db_revision=current["dbRevision"],
            public_keys=public_keys,
            now=timestamp(preflight["observedAt"]),
        )
        counts = preflight["counts"]
        gate = build(
            policy=policy,
            connected=counts["connectedPeople"],
            enrolled=counts["mfaPeople"],
            departments=counts["activeDepartments"],
            responsible_active=counts["responsibleConnected"],
            evidence=evidence,
        )
        return current, {
            "version": 1,
            "kind": "GW_ACCEPTANCE_EXECUTION_REPORT",
            "runId": str(uuid4()),
            **{
                name: preflight[name]
                for name in (
                    "observedAt",
                    "workspaceId",
                    "generationId",
                    "policyDigest",
                    "codeRevision",
                    "dbRevision",
                    "contextDigest",
                    "codeRevisionSource",
                    "executionRevisionVerified",
                )
            },
            "result": "BLOCKED"
            if preflight["result"] == "BLOCKED" or gate["blockedCount"]
            else "PARTIAL",
            "ready": False,
            "liveCompanyAcceptance": False,
            "releaseAuthorized": False,
            "signedEvidence": False,
            "preflight": preflight,
            "checks": gate["checks"],
            "launchGate": gate,
            "backupRestoreCollection": pair,
            "evidenceChecks": evidence,
            "revocationCoverage": denial_review(),
            "remainingConditions": preflight["remainingConditions"],
        }
