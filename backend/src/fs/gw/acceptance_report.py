"""Unsigned operator report from one read-only snapshot; never release evidence."""

from uuid import uuid4

from sqlalchemy import text

from fs.gw.acceptance_execution import execute
from fs.gw.acceptance_preflight import read_transaction, snapshot, validate_request
from fs.gw.launch_gate import build
from fs.gw.operating_contract import OperatingPolicy, timestamp

# References are a review map, never proof that a test ran against this company.
DENIAL_REVIEW = (
    (
        "OLD_SESSIONS",
        "FUNCTION_DENIAL",
        "test_backup_journal_restore.py::test_actual_history_bound_restore_restricts_without_changing_source",
        "옛 관리자·직원 토큰의 인증 판별401; 실제 접속/기기 인수는 별도",
    ),
    (
        "PENDING_AUTHENTICATION",
        "FUNCTION_DENIAL",
        "test_backup_journal_restore.py::test_actual_history_bound_restore_restricts_without_changing_source",
        "복원본의 미완료 인증401; 실제 기기 진행 중 요청은 별도",
    ),
    (
        "CORE_ACCOUNT",
        "STATE_ONLY",
        "test_backup_journal_restore.py::test_actual_history_bound_restore_restricts_without_changing_source",
        "합성 계정 제한 상태; 회수 계정의 새 로그인 거부는 별도",
    ),
    (
        "HR_AUTHORITY",
        "STATE_ONLY",
        "test_security_checkpoint.py::test_hr_role_downgrade_never_restores_old_management_access",
        "HR 하향 상태 재적용; 복원본의 업무 API 권한 거부는 별도",
    ),
    (
        "GW_BINDING",
        "SOURCE_HTTP_DENIAL",
        "test_gw_identity_route_probes.py::test_binding_transition_storage_rollback_and_access",
        "원본의 연결 취소/재개 HTTP 허용·거부; 복원본의 새 인증 후 접근은 별도",
    ),
    (
        "GW_ROLE",
        "SOURCE_HTTP_DENIAL",
        "test_gw_identity_route_probes.py::test_role_transition_storage_rollback_and_access",
        "원본의 역할 부여/회수 HTTP 허용·거부; 복원본의 새 인증 후 접근은 별도",
    ),
    (
        "DOCUMENT_ACL",
        "QUARANTINE_ONLY",
        "test_security_checkpoint.py::test_uncertain_acl_or_hold_change_keeps_scope_quarantined",
        "불확실 ACL/보존 변경의 격리; 문서별 실제 읽기/쓰기 거부는 별도",
    ),
    (
        "COMPANY_MEMBERSHIP",
        "UNCONNECTED",
        None,
        "회사 멤버십 회수 후 복원본의 새 인증·다른 회사 접근 거부 근거는 미연결",
    ),
)


def denial_review():
    return {
        "version": 1,
        "scope": "SELECTED_REVOCATION_BOUNDARIES",
        "coverageComplete": False,
        "result": "UNVERIFIED",
        "executionState": "NOT_EXECUTED",
        "revocationsComplete": False,
        "checks": [
            {
                "code": code,
                "existingScope": scope,
                "testReference": reference,
                "remainingScope": remaining,
                "executionState": "NOT_EXECUTED",
            }
            for code, scope, reference, remaining in DENIAL_REVIEW
        ],
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
