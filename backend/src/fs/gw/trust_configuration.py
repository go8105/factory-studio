"""Allowlisted operator guidance. Never expose configuration values or exception text."""

ISSUES = {
    "VERIFIER_CONFIGURATION": (
        "실행 증거 검증 설정을 확인해야 합니다",
        "검증 키·허용 회사/용도 또는 제품 버전을 확인하지 못했습니다.",
        "현재 회사에 허용한 검증 키와 제품·DB 버전을 대조한 뒤 다시 점검하세요.",
    ),
    "CATALOG_LIFECYCLE": (
        "목록 키의 교체·회수 근거를 확인해야 합니다",
        "현재 키 상태 또는 고정한 이관 원본을 검증하지 못했습니다.",
        "현재 회수 상태와 정확한 이관 원본·허용 범위를 확인하세요. 옛 승인으로 회수를 되돌리지 마세요.",
    ),
    "TRUST_STORE_REQUIRED": (
        "목록 신뢰 이력의 보존 설정이 필요합니다",
        "현재 목록 권한에 필요한 보존 경로가 설정되지 않았습니다.",
        "기존 보존 이력의 위치와 최신 기준을 확인하세요. 사용하던 원장을 새 빈 원장으로 대신하지 마세요.",
    ),
    "TRUST_STORE_UNAVAILABLE": (
        "보존한 신뢰 원본을 읽거나 대조하지 못했습니다",
        "보존 경로·권한 또는 원본과 현재 기준점의 대조를 완료하지 못했습니다.",
        "손상 원본을 보존하고 별도로 확인한 최신 기준과 대조하세요. 복구가 필요하면 새 폴더에 같은 원본을 재구성하세요.",
    ),
    "TRUST_SETTINGS_MISMATCH": (
        "현재 키 설정과 보존 이력이 다릅니다",
        "현재 설정을 보존한 최신 키 상태·승인 연결과 일치시키지 못했습니다.",
        "현재 설정과 보존한 회수·은퇴 상태를 대조하세요. 정상 변경은 확인한 현재 지문으로 설치하고 과거 설정으로 되돌리지 마세요.",
    ),
    "TRUST_UPDATE_PENDING": (
        "신뢰 이력의 기록 마무리가 필요합니다",
        "새 기록의 현재 기준점 반영이 끝나지 않았습니다.",
        "완성한 같은 원본과 확인한 지문으로 기록을 마무리하세요. 잘린 원본을 덮거나 이전 기준점으로 초기화하지 마세요.",
    ),
    "TRUST_RECOVERY_PENDING": (
        "신뢰 이력 복구가 아직 진행 중입니다",
        "현재 보존 폴더에 완료되지 않은 수신·복구 기록이 있습니다.",
        "같은 최신 기준·패키지·기존 원본으로 복구를 마무리하세요. 손상 폴더를 보존하고 완료 후 현재 권한을 다시 대조하세요.",
    ),
}


class TrustConfigurationError(ValueError):
    def __init__(self, code):
        self.code = code if code in ISSUES else "VERIFIER_CONFIGURATION"
        super().__init__("catalog lifecycle trust unavailable")


def guidance(code):
    code = (
        code if isinstance(code, str) and code in ISSUES else "VERIFIER_CONFIGURATION"
    )
    title, detail, action = ISSUES[code]
    return {
        "code": code,
        "title": title,
        "detail": detail,
        "owner": "SERVER_OPERATOR",
        "nextAction": action,
    }
