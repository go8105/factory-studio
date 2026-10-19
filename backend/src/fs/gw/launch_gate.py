"""Explicit evidence boundaries; no checkbox or caller-supplied release override."""

from fs.gw.acceptance_requirements import for_condition


def build(*, policy, connected, enrolled, departments, responsible_active, evidence):
    checks = []

    def measured(code, label, passed, detail, action):
        checks.append(
            {
                "code": code,
                "label": label,
                "state": "CONFIRMED" if passed else "BLOCKED",
                "detail": detail,
                "nextAction": "" if passed else action,
            }
        )

    measured(
        "POLICY",
        "운영 기준",
        policy is not None,
        "현재 적용된 운영 기준이 있습니다."
        if policy
        else "적용된 운영 기준이 없습니다.",
        "책임자와 인원·보관·복구 기준을 검토해 적용하세요.",
    )
    measured(
        "RESPONSIBLE",
        "담당자 연결",
        policy is not None and responsible_active is True,
        "현재 담당자의 활성 직원 연결을 확인했습니다."
        if responsible_active
        else "담당자의 활성 계정·회사 멤버십·직원 연결이 필요합니다.",
        "현재 기준의 담당자가 회사 직원으로 연결돼 있는지 확인하세요.",
    )
    measured(
        "DEPARTMENTS",
        "조직 등록",
        policy is not None and departments >= policy.expected_departments,
        f"활성 조직 {departments}개"
        + (f" / 예정 {policy.expected_departments}개" if policy else ""),
        "예정 부서 수와 활성 조직을 확인하세요.",
    )
    measured(
        "PEOPLE",
        "직원 연결",
        policy is not None and connected >= policy.expected_people,
        f"활성 직원 연결 {connected}명"
        + (f" / 예정 {policy.expected_people}명" if policy else ""),
        "예정 직원의 계정·회사 멤버십·본인 연결을 마치세요.",
    )
    measured(
        "MFA",
        "직원 인증 앱",
        connected > 0 and enrolled == connected,
        f"활성 연결 {connected}명 중 인증 앱 등록 {enrolled}명",
        "연결된 모든 직원의 인증 앱 등록을 확인하세요.",
    )
    for kind, label in (
        ("BACKUP", "백업 증거"),
        ("RESTORE", "복원 증거"),
        ("ACCEPTANCE", "실환경 인수 증거"),
    ):
        rows = [r for r in evidence if r.get("kind") == kind]
        row = rows[0] if len(rows) == 1 else None
        valid = (
            row is not None
            and row.get("state") == "RECORDED_PASS"
            and row.get("signatureVerified") is True
        )
        measured(
            kind,
            label,
            valid,
            row["detail"] if row else "최신 검증 결과를 확인할 수 없습니다.",
            "현재 기준으로 실행한 원본 서명 증거를 등록하고 미통과 항목을 해결하세요.",
        )
    for code, label, action in (
        (
            "EXTERNAL_STORAGE",
            "외부 저장소 장애·복구",
            "독립 저장 위치·키 분리·단절 후 복구 근거를 인수하세요.",
        ),
        (
            "JOURNAL_COVERAGE",
            "전체 변경 수집·권한 회수",
            "운영 경로 목록과 누락 검증·복원 후 전체 회수 근거를 인수하세요.",
        ),
        (
            "LIVE_COMPANY",
            "실제 회사 대표 업무",
            "실제 환경에서 관리자·직원과 예정 인원의 대표 업무를 검증하세요.",
        ),
        (
            "FINAL_RELEASE",
            "운영 전환 최종 승인",
            "남은 조건과 책임자 확인 뒤 별도 운영 전환 절차를 수행하세요.",
        ),
    ):
        checks.append(
            {
                "code": code,
                "label": label,
                "state": "UNVERIFIED",
                "detail": "현재 제품에 인수 완료를 판정할 근거가 연결되지 않았습니다.",
                "nextAction": action,
                **for_condition(code, policy.expected_people if policy else 10),
            }
        )
    return {
        "version": 1,
        "ready": all(c["state"] == "CONFIRMED" for c in checks),
        "confirmedCount": sum(c["state"] == "CONFIRMED" for c in checks),
        "blockedCount": sum(c["state"] == "BLOCKED" for c in checks),
        "unverifiedCount": sum(c["state"] == "UNVERIFIED" for c in checks),
        "checks": checks,
    }
