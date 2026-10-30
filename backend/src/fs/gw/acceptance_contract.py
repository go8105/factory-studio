"""Versioned scope of the twelve gates; never an ACCEPTANCE PASS document.

Descriptions are a closed server-owned catalog. They accept neither uploaded
reports nor provider claims and cannot authorize access or deployment.
"""

CATALOG = {
    "POLICY": (
        "CURRENT_DB",
        "현재 적용된 운영 기준",
        "기준 내용의 실회사 적합성은 책임자가 검토합니다.",
        (),
    ),
    "RESPONSIBLE": (
        "CURRENT_DB",
        "활성 계정·회사 멤버십·직원 연결",
        "담당자의 실제 대응 가능 여부는 별도 확인합니다.",
        (),
    ),
    "DEPARTMENTS": (
        "CURRENT_DB",
        "활성 조직 수가 예정 수 이상인지",
        "정확히 부서1개·전원 부서 배치는 기존 사전점검에서 확인합니다.",
        (),
    ),
    "PEOPLE": (
        "CURRENT_DB",
        "활성 본인 연결 수가 예정 수 이상인지",
        "관리자1명·직원9명과 정확히10명 구성은 기존 사전점검에서 확인합니다.",
        (),
    ),
    "MFA": (
        "CURRENT_DB",
        "활성 연결 전원의 인증 앱 등록",
        "실제 기기 로그인·추가 인증·복구 사용은 실환경에서 확인합니다.",
        (),
    ),
    "BACKUP": (
        "CURRENT_SIGNED_SOURCE",
        "최신 등록 원본·현재 정책/버전·서명 권한·RPO",
        "파일과 서명만으로 외부 저장소의 독립성을 확인하지 않습니다.",
        (),
    ),
    "RESTORE": (
        "CURRENT_SIGNED_SOURCE",
        "최신 복원 원본의 현재성·서명·측정 계약",
        "기존 실제 복원은 PARTIAL이며 전체 권한 회수는 미확인입니다.",
        (),
    ),
    "ACCEPTANCE": (
        "CURRENT_SIGNED_SOURCE",
        "최신 인수 원본과 백업·복원·연결 관측 재검증",
        "PARTIAL/FAIL만 지원하며 최종 인수 PASS 계약은 열리지 않았습니다.",
        (),
    ),
    "EXTERNAL_STORAGE": (
        "LIVE_ENVIRONMENT",
        "사본 지문·서명/격리 복원은 기존 도구로 일부 대조 가능",
        "독립 장애 영역·키/접근 분리·원본 단절 복구는 공급자 선정 후 실환경 인수가 필요합니다.",
        ("BACKUP", "RESTORE"),
    ),
    "JOURNAL_COVERAGE": (
        "LIVE_ENVIRONMENT",
        "기존 경로 검사·거래 관측·원본/복원본·목록/회수 이력 대조",
        "전경로 무누락·독립 최신 기준·전체 권한 거부는 실제 운영 경로에서 인수해야 합니다.",
        ("RESTORE", "ACCEPTANCE"),
    ),
    "LIVE_COMPANY": (
        "LIVE_ENVIRONMENT",
        "기존 사전점검의10인·1부서·역할/MFA 구성과 동일 스냅샷 실행 보고",
        "실제10인 동시 업무·도메인/TLS·기기·복구 흐름은 별도 인수가 필요합니다.",
        ("POLICY", "RESPONSIBLE", "DEPARTMENTS", "PEOPLE", "MFA"),
    ),
    "FINAL_RELEASE": (
        "LIVE_ENVIRONMENT",
        "현재12조건과 최신 등록 원본의 미충족 항목 조회",
        "책임자 최종 검토·배포/되돌림·실제 접속 전환은 별도 절차이며 자동 실행하지 않습니다.",
        ("EXTERNAL_STORAGE", "JOURNAL_COVERAGE", "LIVE_COMPANY"),
    ),
}


TOOLS = {
    "CURRENT_DB": ["operations.read", "acceptance_preflight.collect"],
    "CURRENT_SIGNED_SOURCE": [
        "readiness.assess",
        "acceptance_collection.collect_registered",
    ],
    "EXTERNAL_STORAGE": ["acceptance_artifact.inspect_copy", "gw_backup.py restore"],
    "JOURNAL_COVERAGE": [
        "gw_route_verify.py",
        "journal_observation",
        "restore_recheck",
        "catalog_trust_store",
    ],
    "LIVE_COMPANY": ["acceptance_preflight.collect", "acceptance_report.collect"],
    "FINAL_RELEASE": ["launch_gate.build"],
}


def attach(checks):
    if len(checks) != len(CATALOG) or {c["code"] for c in checks} != set(CATALOG):
        raise ValueError("acceptance gate catalog mismatch")
    for check in checks:
        mode, automatic, remaining, dependencies = CATALOG[check["code"]]
        if mode == "LIVE_ENVIRONMENT" and check["state"] != "UNVERIFIED":
            raise ValueError("live acceptance adapter is not implemented")
        check["verification"] = {
            "mode": mode,
            "executionState": "NOT_EXECUTED"
            if mode == "LIVE_ENVIRONMENT"
            else check["state"],
            "existingTools": list(TOOLS.get(check["code"], TOOLS.get(mode, []))),
            "automaticScope": automatic,
            "remainingScope": remaining,
            "prerequisites": list(dependencies),
        }
    return {
        "version": 1,
        "kind": "GW_ACCEPTANCE_EXECUTION_BOUNDARY",
        "result": "BLOCKED"
        if any(c["state"] == "BLOCKED" for c in checks)
        else "PARTIAL",
        "passSupported": False,
        "liveCompanyAcceptance": False,
        "releaseAuthorized": False,
    }
