# FS-019b 완료 보고 — E-02 견적 · E-03 판매계획 · E-04 수주 (ERP 7/18)

작성일: 2026-09-26 · 브랜치 `fs-019b-erp-sales` (main `cc6201d` 위) · 작업자 Claude Code

## 결정 (사용자, 2026-09-26)

- FS-019b~h는 **Claude Code가 전부** 메인 폴더에서 순차 진행한다(Codex는 ERP를 하지 않음).
- E-G07: **0원 매출 세금계산서 발급 금지**(0원 매출 자체는 허용). FS-019d에서 409로 구현한다.

## API (구현: `backend/src/fs/erp/sales.py`, 라우트는 `erp/router.py`에 추가)

계약 요약은 FS-010 §8 "영업 (FS-019b)". 핵심만:

| 화면 | 규칙 |
|---|---|
| E-02 견적 | draft → confirmed → sent → accepted/rejected, 종결 전 cancelled(거절·취소 사유 필수). 최신 = `MAX(revision_no)` **조회 시 파생**(플래그 저장 없음, E-G03). 확정 이후 내용 변경은 `revise`로 다음 차수 draft(라인 복사), 이전 차수 읽기 전용(`NOT_LATEST_REVISION`). 상태 이력은 추가만 하므로 **견적 삭제 없음**(취소로 대신). `convert`: sent·accepted 최신 견적 → 할인 반영 단가로 수주 생성, sent면 accepted, 견적당 1회 |
| 단가 | 라인 단가를 비우면 기준일(견적일/수주일)이 속한 달의 사용 중 SALE 거래처 단가를 **복사**. 없으면 400. 출처(`priceSource`)는 저장하지 않고 현재 단가표 값(`masterPrice`)과 비교해 파생 — 단가표가 나중에 바뀌면 "수동 입력(단가표 값)"으로 보인다(도움말에 명시) |
| 금액 | 수량 × 단가 × (100 − 할인율)%, 원 단위 반올림. 전환 수주 단가는 소수 4자리 반올림 |
| E-03 판매계획 | draft만 수정·라인 교체·삭제, 확정 시 `confirmed_at`, 빈 계획 확정 409. 품목당 1행, 단위 = 품목 기준 단위. MES 사용 여부를 모른다는 단방향 안내(E-G06) |
| E-04 수주 | 직접 등록(머리글 + 명세)이 정상 경로. 라인별 `instructedQty`(취소 안 된 출하지시)·`shippedQty`(확정 출하)로 진행률. 유효 출하지시가 있으면 머리글·명세·단가 불변·취소 불가(`ORDER_LOCKED`, FS-006b). 견적 전환 수주는 거래처 변경 불가 |

고객(CUSTOMER·사용 중) 거래처, 사용 중 품목만 받는다. 업무 시각(`confirmed_at`, 이력 `changed_at`)은 `clock_timestamp()`(MES 020g와 같은 이유). 동시성: 같은 공간 쓰기는 `write_scope` 공간 잠금으로 직렬화되며, 019b에는 한도 규칙이 없어 별도 동시성 주입 테스트는 두지 않았다(한도 규칙은 019c 출하지시부터).

목록은 페이지 없이 전체(`data`만). 게스트 공간 규모에서는 충분하다.

## 화면 (`frontend/src/erp/`)

- `Quotations.tsx` E-02: 최신 개정본 목록, 명세 편집(단가 비우면 거래처 단가·할인율), 단가 출처 배지, 상태 버튼(확정·제출·수락·거절·취소·개정), 수주 전환 폼, 상태 이력, 개정 이력(이전 차수 읽기 전용 열기).
- `SalesPlans.tsx` E-03, `SalesOrders.tsx` E-04(명세 편집 공용 `LineEditor`, 진행률 "10개 중 6개 출하 (60%)").
- ERP 진입(`/erp`)을 E-02 견적으로 바꾸고 사이드바에 "영업" 그룹 추가.
- **공통 변경(별도 커밋 `1092e83`)**: MES 전용이던 목록·저장 훅을 `shared/hooks.tsx`(`useApiLists`·`useApiSend`, 접두사 인자)로 옮겼다. MES는 접두사만 붙인 기존 이름 그대로, 동작 변경 없음(MES 테스트 52개 통과).
- 도움말 e-02·e-03·e-04를 실제 동작(단가 복사·출처 파생·상태 흐름·막히는 경우)에 맞게 고쳤다.

## 테스트

- backend: `test_erp_quotations.py` 15, `test_erp_sales_plans.py` 6, `test_erp_sales_orders.py` 8 (guest_space).
- frontend: `erp/sales.test.tsx` 12. Playwright: 견적 작성 → 확정 → 제출 → 수주 전환 흐름 1개 + 360px 3화면, ERP 진입 URL 갱신.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 통과, **354 passed** |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest (`factory_studio_fs016_test`) | **561 passed** (11분 13초) |
| `tools/run_portal_smoke.py` | **87 passed** (3.3분) |
| tools unittest / db:validate / audit_schema_isolation / git diff --check | 통과 |

- 첫 frontend 전체 실행에서 포털 `screens.test.tsx` 1건이 backend pytest와 동시 실행 중 실패, 단독·재실행 통과(부하 타이밍). 
- 스모크 전 사용자 개발 서버(8000 uvicorn --reload, 5173 vite)를 규칙대로 종료했다.
- 360px 스크린샷(E-02·03·04) 직접 확인: 가로 스크롤 없음, 관리 열은 코드 바로 뒤.

schema.json·마이그레이션·conftest·test_common·test_seed 변경 0. 새 의존성 0.

## 다음

FS-019c E-05 출하지시 · E-06 출하 (TX-07·08, 출하지시 수량 한도 동시성 주입 테스트, `packing_no` 수기 코드 E-G04). 출하 확정 시 수주 상태 open → shipping → closed 전이도 019c에서.
