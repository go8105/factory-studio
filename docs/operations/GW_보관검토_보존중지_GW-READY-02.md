# GW 보관 검토·보존 중지 · GW-READY-02

승인된 기존 retention_review/operating_settings에 API·UI를 연결했다. schema0.28/219표2409컬럼543FK 그대로이며 migration/Excel/ERD 추가 변경 없음. 원본 삭제/익명화/보관본 생성·보관 완료는 미구현이다. ready=false를 유지한다.

## 처리 계약

- GW 보안 관리자 또는 감사 역할만 목록·이력을 조회한다. 쓰기는 현재 보안 관리자+최근5분 MFA·CSRF/Origin·사유2~500자·멱등키가 필요하다. 총 관리자/회사 소유자 이름으로 원문을 우회하지 않는다.
- POST `gw/retention-reviews/refresh`: expectedVersion은 operating_settings 버전. 현재 정책에 따라 기한 도달 대상을 최대200건 추가, hasMore 안내. 일반 기안 GENERAL/APPROVED·REJECTED·WITHDRAWN의 closed_at, 게시글 PUBLISHED·WITHDRAWN의 published_at/withdrawn_at을 한국 날짜로 바꾸고 달력 월을 더한다. published_at 없는 게시글/closed_at 없는 기안/초안/진행 중/타 솔루션 자료는 제외한다. 정책별 기존 검토 기록은 덮어쓰지 않는다.
- GET `gw/retention-reviews`: offset0~100000/limit1~100, 상태 및 정확한 숫자 sourceId 검색. 관리자에게 식별자·기한·검토 사유·상태·정책 차수를 허용하지만 원문 제목/본문/소유자 이름/이전후속 링크를 반환하지 않는다. 원문 권한은 기존 company_work.visible로 매번 계산한다. 운영 사유에는 원문을 넣지 않는다는 안내가 있다.
- GET `gw/retention-reviews/{id}/source`: 회사 운영 역할과 기존 원문 ACL을 매번 검사한 후 종류·ID만 반환한다. 기존 제품 원문 화면도 자체 ACL을 다시 검사한다. CSV/원문 검색/전사 원문 내보내기 경로를 추가하지 않는다.
- POST `gw/retention-company-hold`: settings CAS, 회사 전체 중지 적용/해제·사유·시각 이력. 해제할 때까지 계속되며 자동 만료 예약은 없다. 기존 회사 중지를 정책 새 버전으로 지우지 않는다.
- POST `gw/retention-reviews/{id}/transition`: row CAS. DUE→HELD/ARCHIVE_PREPARED, HELD→DUE, ARCHIVE_PREPARED→DUE/HELD. 준비는 현재 정책·기존 원문 ACL·회사 중지 없음·동일 원문의 모든 정책에 HELD 없음을 요구한다. ACL/최근 인증은 성공 receipt보다 먼저 검사한다. 정책 변경으로 과거 HELD를 우회할 수 없다. ARCHIVED 입력은 거부한다.
- GET `gw/retention-events`: 현재 회사·세대의 감사 이벤트만 최소 정보로 페이지 조회. 전후 상태/회사 중지 값·사유·시각을 보존한다. core.audit_event에 generationId를 함께 기록해 같은 회사의 다른 세대 이력을 섞지 않는다. 직원명·원문·비밀을 추가 조회하지 않는다.

잠금은 기존 회사 쓰기 exclusive→계정/세션→현재 역할→설정/검토행 순서다. read도 회사 현재 세대를 확인한다. 관리자가 비공개 원문을 읽지 않고 보존 목적의 보류를 걸 수 있지만 준비는 할 수 없다. 개별 해제는 대기로 돌아가며 회사 전체 해제와 별개다. 준비는 수동 검토 표시일 뿐 실제 보관본 검증이 아니고 기존 archive_digest/reference도 임의 입력받지 않는다. 향후 실제 보관 처리는 현재 정책·원문 ACL·모든 보류와 실제 보관본 증거를 다시 검사해야 한다.

## 확인 및 남은 항목

백엔드 관련23개 통과(윤년1/31+1개월=2/29,203건200+3 분할/중복0,비공개 메타데이터/원문404,감사조회/쓰기거부,정책간보류/회사중지,최근인증/ACL회수 후 receipt거부,행CAS 경합,원본불변). 프런트 집중6개 통과. Chrome 실제 합성 제품의 갱신→회사중지/해제→준비→개별보류/해제→이력→원문,390px 넘침0/pageerror0. 실제 회사/실자료 인수는 미완료다.

[사용자 도움말](../../content/help/gw/operations.md), [전체 구현 기록](../agent/GW_실사용구현_GW-READY-02.md). 다음은 실제 암호화 백업·폐쇄 복원/독립 회수 이력 재적용, 운영 게이트·선택SSO·전체 회귀/10인·실환경 인수다. main/원격/운영 반영을 이 구현 완료와 혼동하지 않는다.
