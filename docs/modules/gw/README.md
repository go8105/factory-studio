# GW — 전자결재·게시판

> **2026-10-05 DSN-31 보강 설계 중**(Claude, D82) — [GW_보강설계_DSN-31.md](GW_보강설계_DSN-31.md). 체험 GW(일괄 개발 W5)와 실제 도입 GW(GW-EXT, 별도 트랙)를 나눈다. 사람·조직 원천은 HR(D81).

## 현재 기준 (2026-10-04, FS-030b)

- 상태: **FS-030b API·G-01~07·ERP 배지 구현 완료, c 시작 확인 대기**. 로컬 미배포; 업무 시드/도움말은 c에서 추가.
- 기준 브랜치 `codex/fs-030-gw`, main `8531c05`(a 병합·SPC 시드·CMMS DB)까지 fast-forward. “진행해줘”로 결정서, “구현 진행해줘”로 전체 설계 승인을 기록했다.
- [결정 D60~D69](../../plan/GW도입_전자결재_결정_FS-030.md) · [모듈 설계](GW_모듈설계_FS-030.md) · [화면 G-01~07](../../ui/화면설계_GW_FS-030.md).
- 범위: 일반 기안/ERP 매입 스냅샷의 순차 결재, 합성 담당자 역할 체험, 공지·자유 글. 실제 직원 계정·전자서명·ERP 확정 통제 제외.
- DB 완료: gw 8테이블, 현재 전체 head `fs029b_cmms_module`(스키마 v0.17.0), b는 migration 변경 없음. [검증 보고](../../agent/GW_DB_FS-030a.md). 구현: API `/api/v1/gw`, UI `/gw/*`; 도움말 `gw/g-01~07`은 c 예정. [b 보고](../../agent/GW_API화면_FS-030b.md).

### 제공 조회 함수 — 구현됨

| 함수 | 반환 | 소비 |
|---|---|---|
| `enabled(connection, scoped)` | bool | ERP/EIP |
| `approvals(connection, scoped, document_refs)` | 원천 종류·번호별 진행 중 우선/최신 종결 결재, 비교용 상신 digest·상태. 꺼짐 None, 기록 없음 null | ERP E-11 상세 배지 |

### 읽는 조회 함수 — ERP 제공 구현됨

`fs.erp.interface.approval_documents` / `approval_document` / `approval_source_digest`. 원문 조회·정규화 계약은 ERP가 소유한다. 기존 WMS용 함수는 바꾸지 않는다. ERP README 제공 표는 **구현과 같은 커밋**에서 갱신한다. interface 사이 재귀 호출·교차 쓰기·교차 FK 없음.

### 다음 단계

FS-030b 결과 확인 → FS-030c 업무69행 시드/도움말/흐름맵/통합 검증. 각 단계 보고 후 확인 대기. Codex 전용 DB만 사용하며 push·운영 반영은 제외한다.

### 확장 설계 검토 (2026-10-05)

실제 회사 도입 목표의 [GW-EXT-01 결정 초안](../../plan/GW확장_협업플랫폼_결정초안_GW-EXT-01.md)을 작성했다. 공유 공간/권한·고급 결재·파일/PDF·인사/협업·ERP 통제/EIP 계약·외부 연동과 운영 준비를 단계화했다. 사용자 “상세 설계 진행해줘”로 범위/순서 승인. [P0/A 상세 설계 묶음](../../plan/GW확장_상세설계검증_GW-EXT-A.md)을 작성했고 전체 설계 확인 대상이다. 현재 구현 범위는 FS-030b 그대로이며 c도 아직 미착수다.
