# GW — 전자결재·게시판

## 현재 기준 (2026-10-01, FS-030)

- 상태: **결정서 승인 완료, 모듈·화면 전체 설계 승인 대기**. 제품 코드·DB 미구현. 운영/동결 아님.
- 기준 브랜치 `codex/fs-030-gw`, main `7a2d70f`. 사용자 “진행해줘”를 결정서 권장안 4항목 승인으로 기록했다.
- [결정 D60~D69](../../plan/GW도입_전자결재_결정_FS-030.md) · [모듈 설계](GW_모듈설계_FS-030.md) · [화면 G-01~07](../../ui/화면설계_GW_FS-030.md).
- 범위: 일반 기안/ERP 매입 스냅샷의 순차 결재, 합성 담당자 역할 체험, 공지·자유 글. 실제 직원 계정·전자서명·ERP 확정 통제 제외.
- 예정: gw 8테이블, API `/api/v1/gw`, UI `/gw/*`, 도움말 `gw/g-01~07`.

### 제공 조회 함수 — 설계 계약, 아직 호출 불가

| 함수 | 반환 | 소비 |
|---|---|---|
| `enabled(connection, scoped)` | bool | ERP/EIP |
| `approvals(connection, scoped, document_refs)` | 원천 종류·번호별 진행 중 우선/최신 종결 결재, 비교용 상신 digest·상태. 꺼짐 None, 기록 없음 null | ERP E-11 상세 배지 |

### 읽는 조회 함수 — ERP에 추가 예정

`fs.erp.interface.approval_documents` / `approval_document` / `approval_source_digest`. 원문 조회·정규화 계약은 ERP가 소유한다. 기존 WMS용 함수는 바꾸지 않는다. ERP README 제공 표는 **구현과 같은 커밋**에서 갱신한다. interface 사이 재귀 호출·교차 쓰기·교차 FK 없음.

### 다음 단계

사용자 전체 설계 확인 → FS-030a 메타데이터/DB → FS-030b API/화면/E-11 배지 → FS-030c 시드/도움말/통합 검증. 각 단계 보고 후 확인 대기. Codex 전용 DB만 사용하며 push·운영 반영은 제외한다.
