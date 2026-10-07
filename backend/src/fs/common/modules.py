"""업무 솔루션 목록 한 곳 (W1b).

시드 복사·게스트 공간 정리·시드 검증이 모두 이 목록을 쓴다. 여기 빠뜨리면
새 솔루션의 행이 공간 정리를 막거나(FK RESTRICT) 시드가 복사되지 않는다.
새 솔루션을 만들 때는 **이 목록만** 고친다.
"""

BUSINESS_SCHEMAS = (
    "mes",
    "erp",
    "fems",
    "qms",
    "wms",
    "bems",
    "spc",
    "gw",
    "cmms",
    "hr",
)
# core는 업무 스키마가 아니지만 모듈 행은 함께 만든다(인증·공간·세대).
MODULE_KEYS = ("core", *BUSINESS_SCHEMAS)
