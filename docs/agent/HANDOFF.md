# 2026-10-30 QMS-1f 완료 — SPC·CMMS·QMS 보강 진행 중 (다음: QMS-1g)

- **작업 폴더 / 브랜치**: `/Users/hwang-kyoungho/projects/factory-studio` / `qms-1f` (병합 뒤 `main`)
- **마지막 커밋**: `git log --oneline -3` 참조. 원격 `origin/main`과 동기.
- **담당**: Claude Code가 설계·개발·검증·병합을 모두 한다(D85). Codex는 GW 범위만.

## 이번 구간에 끝낸 것 (2026-10-19 ~ 10-30)

보강 순서 **SPC → CMMS → QMS**를 따라왔고, 세 솔루션이 모두 화면까지 끝났다.

| 솔루션 | 결과 | 마이그레이션 |
|---|---|---|
| SPC | 7 → **11화면**, 5 → 10표 | `spc1`, `spc2` |
| CMMS | 0 → **10화면**(솔루션 개통), 6 → 12표 | `cmms1`, `cmms2` |
| QMS | 6 → **12화면**, 6 → 15표 | `qms1` |

QMS 단계별: **1a** DB 15표 / **1b** WMS·MES 교차 조회 함수 5개 / **1c** 계측기·교정(Q-11)·4M 변경(Q-12) / **1d** 부적합 보고(Q-07)·시정예방조치(Q-08) / **1e** 클레임(Q-09)·공급처 품질(Q-10) / **1f** 검사 종류·AQL 샘플링·수입 검사.

**1b에서 만든 교차 조회 함수가 전부 소비자를 얻었다** — `defects`는 Q-07 공정 부적합이, `lot_trace`는 Q-09 LOT 역추적이, `inbound_lots_to_inspect`는 Q-03 수입 탭이 쓴다. 죽은 코드로 남지 않았다.

## 곁들여 고친 것 (QMS 작업과 무관한 선재 문제)

1. **테스트 정리가 PostgreSQL 잠금표를 바닥냈다** — 게스트 정리가 230개 표를 한 트랜잭션에서 지워 `out of shared memory`. `conftest._delete_test_guests`를 40개 표마다 커밋하도록 바꿨다.
2. **프런트 기본 대기 1초가 빠듯했다** — 파일이 늘자 ERP 테스트가 병렬 부하에서 재현성 있게 깨졌다. `src/test/setup.ts`에서 `asyncUtilTimeout` 5초로.
3. **시드 복사 성능 기준(사용자 결정)** — 2초 약속을 최대값이 아니라 **중앙값**에 건다(최대 3초 상한). FS-015 때 0.456초였던 중앙값이 표 230개에서 1.67초다. **표가 381로 가면 기준이 아니라 복사 자체를 고쳐야 한다.**

## 다음 작업 — QMS-1g

1f 설계 범위(검사 보강·지표)가 커서 **수입 검사 라인 완성**만 1f로 하고 나머지를 1g로 넘겼다.

| 할 일 | 설계 | 메모 |
|---|---|---|
| 검사 값에 **계측기 기록** | F27 | `qms.inspection_value.gauge_id`. Q-11은 1c에 있다. 교정 만료·수리 중 계측기면 경고(차단 아님) |
| **검사 성적서(COA)** 브라우저 인쇄 | F25 | 확정 검사의 항목·측정값·판정·계측기 |
| **Q-13 품질 지표** 신규 화면 | F72 | 파레토·PPM 추이. 1f로 수입 데이터가 생겨 이제 의미가 있다 |
| Q-01 대시보드 카드 보강 | F71 | 수입 대기·미결 NCR/CAPA·클레임·교정 도래 |
| 반품 검사·처분 | F42 | **막힘** — `erp.sales_return`이 목표 설계에만 있다. ERP 단계까지 대기 |

## 그 뒤 로드맵

**기존 솔루션 보강**: SPC ✔ → CMMS ✔ → QMS(1g 남음) → **FEMS(12표)** → **BEMS(11표)** → **ERP(38표)**
**그 뒤 새 솔루션**: POP(7표)부터

## 주의점

- **`apply_*.py` 틀이 nullability를 옮기지 않는다.** SPC·CMMS에서 각각 `spc2`·`cmms2`를 따로 만들어 보완했다. FEMS·BEMS·ERP에서도 난다.
- **다른 세션이 같은 폴더의 main을 쓴다.** QMS-1d 커밋이 브랜치가 아니라 main에 직행한 적이 있다(reflog상 외부 checkout). 커밋 직전 `git branch --show-current`를 확인할 것.
- **git add는 파일 경로로.** 디렉터리 단위로 넣지 않는다.
- `git push --mirror` 금지. 원격 push는 사용자 확인 후.
- **AQL 강화 검사 표(ISO Table 2-B)는 구현하지 않았다.** "한 단계 엄격한 AQL" 규칙으로 대신하며 코드·도움말에 명시돼 있다. 진짜 2-B가 필요해지면 그때 넣는다.
- 월 평가 등급 기준(불합격 비율 0/5/10%, 시정 요구 있으면 한 단계 하향)은 **설계에 수치가 없어 내가 정한 값**이다.

## 환경

- **colima VM이 내려가 있을 수 있다**(일주일 만의 세션에서 겪었다). `colima start --profile factory-studio --cpu 2 --memory 4 --disk 20 --vm-type vz --runtime docker` 뒤 `docker start factory-studio-db-1`.
- PostgreSQL 18.6 / 포트 55432 / Python 3.14 / Node 24(`/opt/homebrew/opt/node@24/bin`).
- 재현 명령:
  - 전체: `tools/ci_local.sh`
  - QMS만: `TEST_DATABASE_URL="$(grep -o 'DATABASE_URL=.*' .env | sed 's/^DATABASE_URL=//; s#/factory_studio$#/factory_studio_ci_test#')" backend/.venv/bin/pytest backend/tests -q -k qms`
  - 프런트: `npm --prefix frontend test -- --run`

## 배포

**운영은 `gw_wms_merge`까지다. `spc1`·`spc2`·`cmms1`·`cmms2`·`qms1` 5건이 미배포다.** 운영 반영은 사용자 승인 뒤 `docs/deploy/배포절차_FS-022.md`를 따른다. GitHub Actions가 결제 문제로 막혀 있어 `--skip-ci-check`와 수동 `ci_local.sh`가 필요하다.

# 2026-10-18 W2b-1d D-4 W-09 출고 예약 피킹 상태 연계 및 완제품 출고 예약 보강 완료 (W2b-1d 전체 완료)

- **작업 폴더 / 브랜치**: `/Users/hwang-kyoungho/projects/factory-studio-ag` / `antigravity/w2b-1d-work`
- **마지막 커밋**: `git log -1 --oneline` 참조
- **끝난 것 (W2b-1d D-4 & W2b-1d 전체 완료)**:
  - 기존 데이터 감사: `lot_tracked = false & lot_no IS NOT NULL` (0건), `lot_tracked = true & lot_no IS NULL` (0건) 확인 완료.
  - `backend/src/fs/wms/reservations.py`:
    - `list_reservations`: `wms.pick_order`를 `LEFT JOIN`하여 단일 쿼리로 `pickOrderId`, `pickOrderNo`, `pickOrderStatus`(`OPEN`, `PICKED`, `CANCELLED`, 미지시 null) 반환 (N+1 방지).
    - `_detail`: `wms.pick_order` 조회 연계하여 최신 피킹 지시 정보(`pickOrderId`, `pickOrderNo`, `pickOrderStatus`) 반환.
    - 예약 등록 규칙 정규화 (C-2 일관성): 품목 LOT 필수 여부 검증을 `bool(lot) != (item["itemClass"] == "FG")`에서 C-2와 동일한 `bool(lot) != bool(item.get("lotTracked"))`로 수정.
    - HOLD·EXPIRED LOT 예약 차단: 신규 예약 등록 시 `picks._lot_metadata`, `picks._lot_block_reason`, `qms.held_lot_nos`를 활용하여 WMS 활성 보류(`LOT_HOLD`), QMS 품질 보류(`LOT_QMS_HOLD`), 만료(`LOT_EXPIRED`) 상태의 LOT 지정을 `409 Conflict`로 즉시 차단.
  - `backend/tests/test_wms_reservations.py`:
    - `test_reservation_lot_tracked_validation_and_hold_expired_blocking` 신규 추가 (lotTracked 불일치 400 거절, WMS 보류 409, 유효기간 만료 409, QMS 보류 409 차단, 피킹 지시 생성 전후 상세/목록 연계 검증).
  - `frontend/src/wms/operations.tsx`: `Reservation` 타입에 `pickOrderId?: number | null`, `pickOrderNo?: string | null`, `pickOrderStatus?: PickOrderStatus | null` 추가.
  - `frontend/src/wms/Reservations.tsx`:
    - 예약 목록 테이블에 "피킹 상태" 컬럼 추가 (`미지시` neutral, `대기` warning, `피킹 완료` normal, `취소` issue 배지).
    - 예약 상세 패널에 피킹 상태 배지 표시 및 "피킹 지시" 섹션 연계:
      - 지시 번호, 상태, W-12 화면 링크(`/wms/picks?open={id}`) 제공.
      - `ACTIVE` 상태이면서 미지시 또는 취소 상태일 때 "피킹 지시 생성" 버튼 노출 (OPEN/PICKED 존재 시 숨김).
      - 피킹 지시 생성 성공 시 알림 및 이동 링크 제공.
      - 피킹 지시 생성 실패(`409 INSUFFICIENT_AVAILABLE`) 시, 제외된 LOT(`excludedLots`: LOT 번호, 사유 레이블)과 부족 품목(`insufficientItems`: 품목 코드, 요청/가용 수량)을 상세 패널 상단 알림(`role="alert"`)으로 명확히 안내.
  - `frontend/src/wms/wms.test.tsx`:
    - W-09 출고 예약 목록 및 상세에서 피킹 상태 연계와 피킹 지시 생성 테스트 추가.
    - W-09 출고 예약에서 피킹 지시 생성 실패 시 제외된 LOT과 부족 품목 상세 안내 테스트 추가.
- **검증 결과**:
  - 브라우저 Playwright E2E 검증 (`scratch/verify_d4_reservations.mjs`):
    - 게스트 공간 생성 -> 기초 재고 입고 -> W-09 예약 등록 -> 목록에서 피킹 상태 "미지시" 확인 (`wms-reservations-d4-list.png`).
    - W-09 상세 진입 -> 피킹 미지시 배지 및 "피킹 지시 생성" 버튼 확인 (`wms-reservations-d4-detail-unassigned.png`).
    - "피킹 지시 생성" 클릭 -> 피킹 지시 생성 완료 알림 및 링크 확인.
    - W-12 피킹 화면 이동 -> 생성된 피킹 지시(OPEN) 확인 -> F-SHIP 도착 칸 선택 후 "피킹 확정" 클릭 (`wms-reservations-d4-linked-pick.png`).
    - W-09 출고 예약 화면 복귀 -> 목록에서 피킹 상태 "피킹 완료" 갱신 확인 (`wms-reservations-d4-picked-list.png`).
    - 상세 패널 재진입 -> 상단 "피킹: 피킹 완료" 배지 표시, 지시 번호 및 상태, W-12 링크 확인, 중복 "피킹 지시 생성" 버튼 숨김 확인 (`wms-reservations-d4-picked-detail.png`).
    - 모바일 390px 뷰포트: `scrollWidth = 390, clientWidth = 390` (가로 오버플로 0건) 확인 (`wms-reservations-d4-mobile-390.png`).
    - `ALL D-4 BROWSER VERIFICATIONS PASSED!`
  - `tools/ci_local.sh` 1~5단계 전체 통과:
    - 1단계 (DB 검증·도구): 통과 (`tables: 210, errors: []`, 도구 138건 통과)
    - 2단계 (백엔드 ruff): 통과 (`All checks passed! 247 files clean`)
    - 3단계 (백엔드 pytest): 통과 (`1084 passed, 2 skipped, 58 warnings in 487.10s`, `pytest -m perf`: 1 passed, xdist 작업자 탈락 0건)
    - 4단계 (DB 초기화·마이그레이션 왕복): 통과 (`downgrade base` -> `upgrade head`, DDL 0건 차이)
    - 5단계 (프런트엔드): 통과 (`typecheck`, `lint`, `format:check`, `build`, `Test Files 77 passed (77), Tests 620 passed (620)`)
- **다음 할 일**:
  - 사용자 확인 후 **W2b-1e (출하 검사 W-10 · ERP 출하 연계 E-07)** 착수.
- **주의점**:
  - 모든 작업은 `/Users/hwang-kyoungho/projects/factory-studio-ag` (`antigravity/w2b-1d-work`)에서 수행한다 (`/Users/hwang-kyoungho/projects/factory-studio`는 `main` 전용).
  - `main`을 끌어오거나 원격 push 하지 않는다.
- **재현 명령**:
  - `cd /Users/hwang-kyoungho/projects/factory-studio-ag && npm run ci:local`

# 2026-10-18 W2b-1d D-3 피킹 확정·취소 API 및 화면 연계 + 유효 현재 위치 도출 완료 (D-4 대기)


- **작업 폴더 / 브랜치**: `/Users/hwang-kyoungho/projects/factory-studio-ag` / `antigravity/w2b-1d-work` (기준 `main` `843036f` + D-1 `cc8cfaf` + WMS-FIX-02 `4b32578` + D-2 `bf2f69e`)
- **마지막 커밋**: `git log -1 --oneline` 참조
- **끝난 것 (W2b-1d D-3)**:
  - `backend/src/fs/wms/pick_schema.py`:
    - `PickLineConfirm(lineId, pickedQty)` 및 `PickOrderConfirm(toLocationId, lines)` 스키마 추가.
  - `backend/src/fs/wms/picks.py`:
    - `confirm_pick_order`: 한 트랜잭션에서 `wms.pick_line.picked_qty` 기록, `PICK` 재고 이동 전표(`status='posted'`, `source_key=NULL`, `source_ref=pick_no`, 출발 칸 -picked / 도착 칸 +picked) 생성, `pick_order.status='PICKED'`, `picked_at=now`, `stock_document_id=doc_id` 갱신. 부분 피킹 지원(`picked_qty = 0`이면 전표 미생성, 1개 이상 양수 필수).
    - `cancel_pick_order`: `cancel_reason`(1~300자) 검증, `status='CANCELLED'`, `picked_at=NULL`, `stock_document_id=NULL`, `cancel_reason` 기록. 취소 후 동일 예약에서 재요청 시 `OPEN`으로 재개(c1482) 지원.
    - `_pick_order_header`, `PICK_ORDER_SELECT`, `_enrich_orders`에 `toLocationId`, `toLocationCode`, `toLocationName` 추가.
  - `backend/src/fs/wms/router.py`:
    - `POST /pick-orders/{row_id}/confirm`, `POST /pick-orders/{row_id}/cancel` 엔드포인트 등록.
  - `backend/src/fs/wms/inventory.py`:
    - amounts CTE의 `reserved_qty` 집계 시, 피킹 전(미지시/OPEN/CANCELLED)에는 `stock_reservation_line`의 원래 `(location_id, lot_no, qty)`, 피킹 후(PICKED)에는 PICK 전표 도착 줄 `(to_location_id, lot_no, picked_qty)` + 미피킹 잔량 `(location_id, lot_no, qty - picked_qty)`을 유효 현재 위치로 도출하여 보관 칸 음수 재고 방지.
  - `backend/src/fs/wms/reservations.py`:
    - `_effective_lines` 도출 함수 구현. `_detail`, `list_reservations`, `consume`, `shipment_preview`에 적용하여 ERP 출하 소진 시 도착 위치에서 차감(보관 칸 이중 차감 방지) 및 확정 후 W-09 예약 목록에 거짓 부족 경보(reservationShortage) 방지.
  - `frontend/src/wms/common.tsx`:
    - `PickOrder` 타입에 `toLocationId`, `toLocationCode`, `toLocationName` 추가.
  - `frontend/src/wms/Picks.tsx`:
    - OPEN 상세: 명세별 피킹 수량 입력 필드 제공(기본값 지시 수량), 도착 위치 선택, "피킹 확정" 및 "피킹 취소"(사유 필수) 폼 연계.
    - PICKED 상세: 실제 도착 위치(`toLocationCode · toLocationName`), 확정 시각, 생성된 PICK 전표 링크, 명세별 확정 수량 노출.
    - CANCELLED 상세: 취소 사유 노출.
  - `frontend/src/wms/wms.test.tsx`:
    - 피킹 확정 및 취소 액션 폼/버튼 렌더링 검증 테스트 추가.
- **검증 결과**:
  - 브라우저 Playwright E2E 검증 (`scratch/verify_d3_picks.mjs`):
    - 게스트 세션 생성 -> 창고 및 F-SHIP 출고장 확인 -> 기초 재고 입고(40, 60 EA) -> 출고 예약 1(30, 20 EA) -> 피킹 지시 1(OPEN) 생성.
    - W-12 화면 진입 -> OPEN 상세 및 명세별 수량(30, 20), 도착 위치(F-SHIP) 확인 (`wms-picks-d3-open.png`).
    - "피킹 확정" 클릭 -> 상태 PICKED, 확정 일시, 도착 위치(`F-SHIP · 출하 대기장`), 재고 전표 링크(`WD-...`), 확정 수량 표시 확인 (`wms-picks-d3-picked.png`).
    - 재고 원장 대조: 보관 칸 locA(40 -> 10 EA), locB(60 -> 40 EA) 차감, F-SHIP(30 + 20 EA) 입고, LOT 총량(40, 60 EA) 불변.
    - 출고 예약 목록 및 상세 대조: 유효 현재 위치가 F-SHIP으로 계산되어 `shortage = "0"` 및 모든 명세의 `reservationShortage = "0"` (거짓 부족 경보 0건!).
    - 피킹 지시 2 취소 흐름: 사유 입력 -> "피킹 취소" 클릭 -> 상태 CANCELLED, 취소 사유("오더 변경으로 취소") 표시 (`wms-picks-d3-cancelled.png`).
    - 동일 예약 피킹 지시 재개(c1482 재개): 동일 예약으로 다시 피킹 지시 생성 시 기존 행이 `OPEN`으로 재개됨 확인.
    - 모바일 390px 뷰포트: `scrollWidth = 390, clientWidth = 390` (가로 오버플로 0건) 확인 (`wms-picks-d3-mobile-390.png`).
    - `ALL D-3 BROWSER VERIFICATIONS PASSED!`
  - `tools/ci_local.sh` 1~5단계 전체 통과:
    - 1단계 (DB 검증·도구): 통과 (`tables: 210, errors: []`, 도구 138건 통과)
    - 2단계 (백엔드 ruff): 통과 (`All checks passed! 247 files clean`)
    - 3단계 (백엔드 pytest): 통과 (`1083 passed, 2 skipped, 59 warnings in 505.28s`, `pytest -m perf`: 1 passed, xdist 작업자 탈락 0건)
    - 4단계 (DB 초기화·마이그레이션 왕복): 통과 (`downgrade base` -> `upgrade head`, DDL 0건 차이)
    - 5단계 (프런트엔드): 통과 (`typecheck`, `lint`, `format:check`, `build`, **`Test Files 77 passed (77), Tests 618 passed (618)`**)
- **다음 할 일**:
  - 사용자 확인 후 **D-4 (W-09 출고 예약 화면 피킹 상태 연계 및 완제품 출고 예약 보강, HOLD/EXPIRED 예약 차단)** 착수.
- **주의점**:
  - 모든 작업은 `/Users/hwang-kyoungho/projects/factory-studio-ag` (`antigravity/w2b-1d-work`)에서 수행한다 (`/Users/hwang-kyoungho/projects/factory-studio`는 `main` 전용).
  - `main`을 끌어오거나 원격 push 하지 않는다.
- **재현 명령**:
  - `cd /Users/hwang-kyoungho/projects/factory-studio-ag && npm run ci:local`

# 2026-10-18 W2b-1d D-2 W-12 피킹 목록·상세 화면 완료 (D-3 대기)

- **작업 폴더 / 브랜치**: `/Users/hwang-kyoungho/projects/factory-studio-ag` / `antigravity/w2b-1d-work` (기준 `main` `843036f` + D-1 `cc8cfaf` + WMS-FIX-02 `4b32578`)
- **마지막 커밋**: `git log -1 --oneline` 참조
- **끝난 것 (W2b-1d D-2)**:
  - `backend/src/fs/core/menu_catalog.json`: `W-12` 피킹 메뉴 등록 (`group: "입출고"`, 전체 메뉴 116개).
  - `frontend/src/portal/favorites.test.tsx`: 메뉴 카탈로그 개수 검증 가드 115 -> 116 갱신.
  - `frontend/src/wms/common.tsx`:
    - `PickOrderStatus`, `PICK_STATUS_LABEL` (`OPEN: "대기"`, `PICKED: "피킹 완료"`, `CANCELLED: "취소"`).
    - `PickSubstitutionReason`, `PICK_SUBSTITUTION_REASON_LABEL` (`HOLD: "보류(HOLD)"`, `QMS_HOLD: "QMS 품질 보류"`, `EXPIRED: "유효기간 만료"`, `SHORTAGE: "가용 수량 부족"`).
    - `PickAllocatedLot`, `LotSubstitution`, `PickLine`, `PickOrder` 타입 정의 (백엔드 `picks.py` 계약과 일치).
    - `DocumentType` 및 `TYPE_LABEL`에 `"PICK"` (`PICK: "피킹 이동"`) 추가.
  - `frontend/src/wms/Picks.tsx`:
    - W-12 피킹 화면 신규 구현.
    - 서버 필터 (`status`, `warehouseId`, `reservationId`, `itemCode`) 및 `useWmsQuery` 기반 페이지네이션 (`pageSize = 50`).
    - 목록 테이블: `pickNo`, `reservationNo`, `warehouseCode · warehouseName`, `status` 배지, `lineCount`, `LOT 대체 N건` 배지, `createdAt`, `상세` 버튼.
    - 상세 패널 (`DetailPanel wide`):
      - 피킹 동선 명세 테이블: `sequenceNo` 오름차순(위치 코드 순) 정렬하여 동선 순서 (`#1`, `#2`), 위치 코드·이름, 품목, LOT·유효기간, 지시 수량을 `.table-scroll` 테이블에 렌더링.
      - LOT 대체 안내 섹션 (`role="note"`): `lotSubstitutions`가 있을 때 대체 사유 배지, 요청 LOT 및 요청 위치, 배정된 대체 LOT 목록과 메시지 표시.
      - 도착 위치 선택 (W-11 패턴): 상세 진입 시 해당 창고 위치(`GET /api/v1/wms/warehouses/{whId}/locations`)를 1회 조회해 `SHIPPING` 칸과 `NORMAL` 칸으로 분리. `SHIPPING` 칸이 있으면 첫 번째 출고장 칸을 기본 선택(`toLocationId`), 없으면 빈 선택값과 함께 `"출고장 칸이 없어 보관 칸으로 이동합니다. W-06에서 출고장을 만들 수 있습니다."` 안내 표시.
      - 확정·취소 버튼은 D-2에서 노출하지 않음(D-3 예약).
  - `frontend/src/wms/index.tsx`: `<Route path="picks" element={<Picks />} />` 라우트 등록.
  - `frontend/src/wms/wms.test.tsx`: W-12 피킹 지시 목록, 서버 필터 변경 쿼리 파라미터 반영, `sequenceNo` 순서 동선 명세, `lotSubstitutions` 대체 사유 표시, `SHIPPING` 기본 선택 vs 부재 안내 문구 검증 테스트 추가.
- **검증 결과**:
  - 브라우저 Playwright E2E 검증 (`verify_d2_picks.mjs`):
    - 게스트 공간 생성 후 기초재고 전표 및 출고 예약 생성, 예약 LOT에 보류(HOLD) 설정 후 피킹 지시 생성.
    - `/wms/picks` 진입하여 목록 및 LOT 대체 1건 배지 확인 (`wms-picks-list.png`).
    - 상세 패널에서 `#1 F-A01` -> `#2 F-A02` 동선 정렬 및 `보류(HOLD)` 사유 표시 확인.
    - 출고장 부재 시 안내 문구 및 빈 선택값 확인 (`wms-picks-detail-no-shipping.png`).
    - W-06에서 `F-SHIP` 출고장 추가 후 상세 재진입 시 출고장 자동 기본 선택 및 안내 문구 제거 확인 (`wms-picks-detail-with-shipping.png`).
    - `390px` 뷰포트에서 `scrollWidth = 390`, `clientWidth = 390` (가로 오버플로 0건) 확인 (`wms-picks-mobile-390.png`).
  - `npm run ci:local` 1~5단계 전체 통과:
    - 1단계 (DB 검증·도구): 통과 (tables 210, errors 0, tools 138 passed)
    - 2단계 (백엔드 ruff): 통과 (All checks passed! 247 files clean)
    - 3단계 (백엔드 pytest): 통과 (`1079 passed, 2 skipped, 59 warnings`, `pytest -m perf`: 1 passed)
    - 4단계 (DB 초기화·마이그레이션 왕복): 통과 (`downgrade base` -> `upgrade head`, DDL 0건 차이)
    - 5단계 (프런트엔드): 통과 (`typecheck`, `lint`, `format:check`, `build`, **`Test Files 77 passed (77), Tests 618 passed (618)`**, 실패 0건)
- **다음 할 일**:
  - 사용자 확인 후 **D-3 (피킹 확정 → `PICK` 전표, 취소, 예약 유효 현재 위치 연동)** → **D-4 (W-09 출고 예약에 피킹 상태 연결 및 `lot_tracked`·보류/만료 예약 차단)** 순차 진행.
- **주의점**:
  - 모든 작업은 `/Users/hwang-kyoungho/projects/factory-studio-ag` (`antigravity/w2b-1d-work`)에서 수행한다 (`/Users/hwang-kyoungho/projects/factory-studio`는 `main` 전용).
  - `main`을 끌어오거나 원격 push 하지 않는다.
- **재현 명령**:
  - `cd /Users/hwang-kyoungho/projects/factory-studio-ag && npm run ci:local`

# 2026-10-18 WMS-FIX-02 `test_gw_wms_merge.py` 회귀 수정 및 W2b-1d D-1 완료 (D-2 대기)

- **작업 폴더 / 브랜치**: `/Users/hwang-kyoungho/projects/factory-studio-ag` / `antigravity/w2b-1d-work` (기준 `main` `843036f`)
- **마지막 커밋**: `git log -1 --oneline` 참조
- **끝난 것 (WMS-FIX-02 및 W2b-1d D-1)**:
  - `backend/tests/test_gw_wms_merge.py` (WMS-FIX-02):
    - 과거 리비전(`gw_company_identity`, `flow_board_custom` — `c781_check`가 `'NORMAL'`, `'QUARANTINE'`만 허용)과 진화하는 `create_template()` 시드(`RECEIVING` 위치 포함)의 결합을 제거하고, 세 파라미터(`w2b1_wms`, `gw_company_identity`, `flow_board_custom`) 모두 최소 활성 `TEMPLATE` 공간·세대 행 직접 `INSERT` + `create_example_company()` + 브랜치별 직접 `INSERT`(`w2b1_wms`: `wms.item` + `wms.lot`; `gw_company_identity`: `gw.collaboration_settings`)로 통일.
    - 병합 전후 `fingerprint` 보존, `20261018_gw_wms_merge.py`의 `downgrade()`·`upgrade()` 역변환 `fingerprint` 보존, `verify_ddl_matches_schema.py` 0 단언 그대로 유지.
    - `pytest backend/tests/test_gw_wms_merge.py` 3건 전건 통과 및 `npm run ci:local` 1~5단계 **실패 0건(`1079 passed, 2 skipped`)** 확인.
  - `backend/src/fs/wms/pick_schema.py` & `backend/src/fs/wms/picks.py` (D-1):
    - `POST /api/v1/wms/pick-orders`, `GET /api/v1/wms/pick-orders`, `GET /api/v1/wms/pick-orders/{row_id}` 구현.
    - `wms.stock_move` 잔량 집계에 `wms.lot`을 `LEFT JOIN`하여 마스터 행이 없는 시드 LOT(`LT-0001`~`LT-0012`) 포함, `wms.lot_hold`(`released_at IS NULL`)·`qms.held_lot_nos()`·`wms.lot.status IN ('HOLD','EXPIRED')`·`expiry_date < business_today()` 제외.
    - 예약 줄 지정 LOT이 가용하면 우선 존중하고, 보류·만료·수량 부족 시에만 `expiry_date ASC NULLS LAST → received_on ASC NULLS LAST → lot_no ASC NULLS LAST → loc.code ASC`(FEFO→FIFO)로 대체 배정하며 `lotSubstitutions` 반환.
    - 가용 재고 부족 시 `409 INSUFFICIENT_AVAILABLE` 거절, `CANCELLED` 피킹 지시 재생성 시 `c1482` UNIQUE 위반 없이 기존 행 `OPEN` 재개, 위치 코드 순 `sequence_no = 1..N` 부여, `guard_master` 연동.
  - `backend/src/fs/wms/inventory.py`: `location_type IN ('NORMAL', 'SHIPPING')`을 `normalOnHand`로 인정.
  - `backend/src/fs/wms/service.py`: 대시보드 월별 입출고 집계에서 `'PICK'` 제외.
  - `backend/tests/test_wms_picks.py`: D-1 핵심 시나리오 5건 추가 및 전체 통과.
- **다음 할 일**:
  - 사용자 확인 후 **D-2 (W-12 피킹 목록·상세 화면)** → **D-3 (피킹 확정 → `PICK` 전표, 취소, 예약 유효 현재 위치 연동)** → **D-4 (W-09 출고 예약에 피킹 상태 연결 및 `lot_tracked`·보류/만료 예약 차단)** 순차 진행.
- **주의점**:
  - 모든 작업은 `/Users/hwang-kyoungho/projects/factory-studio-ag` (`antigravity/w2b-1d-work`)에서 수행한다 (`/Users/hwang-kyoungho/projects/factory-studio`는 `main` 전용).
  - `main`을 끌어오거나 원격 push 하지 않는다.
  - `reservations.py:249`의 `item["itemClass"] == "FG"` 규칙 불일치 수정과 `HOLD`/`EXPIRED` 예약 차단은 D-4에서 수행한다.
- **재현 명령**:
  - `cd /Users/hwang-kyoungho/projects/factory-studio-ag && npm run ci:local`

# 2026-10-18 FLOW-FIX-02 `portal/workspace-records.test.tsx` · `portal/screens.test.tsx` 시간 고정 완료

- **브랜치**: `antigravity/flow-fix-02` (기준 `main` `d0c79ae`; 병행 `antigravity/w2b-1c` `3f27c02`는 C-4까지 100% 완료된 상태로 보존)
- **마지막 커밋**: `git log -1 --oneline` 참조
- **끝난 것 (FLOW-FIX-02)**:
  - `frontend/src/portal/workspace-records.test.tsx`:
    - `beforeEach`에 `vi.useFakeTimers({ toFake: ["Date"] })` + `vi.setSystemTime(new Date("2026-09-24T14:50:00Z"))` 설정 및 기존 `afterEach(() => vi.useRealTimers())` 유지.
    - `"남은 시간은 서버 만료 시각과 현재 시간의 차이다"` 테스트의 중복 `vi.spyOn(Date, "now")`를 걷어내고 공통 고정 시각으로 `"남은 시간 10분"` 검증.
  - `frontend/src/portal/screens.test.tsx`:
    - `beforeEach`에 `vi.useFakeTimers({ toFake: ["Date"] })` + `vi.setSystemTime(new Date("2026-09-24T23:50:00+09:00"))` 설정 및 `afterEach(() => vi.useRealTimers())` 복원 추가.
    - `"P-06 초기화는 확인 전 요청하지 않는다"` 테스트에 `expect(screen.getByText("남은 시간 10분")).toBeVisible()` 단언 추가.
  - 검증 결과:
    - `npm --prefix frontend test -- src/portal/workspace-records.test.tsx`: **22 passed (22)**
    - `npm --prefix frontend test -- src/portal/screens.test.tsx`: **12 passed (12)**
    - `npm --prefix frontend test`: **Test Files 77 passed (77), Tests 613 passed (613) — 실패 0건**
    - `npm --prefix frontend run lint`, `npm --prefix frontend run format:check`, `npm --prefix frontend run typecheck`: 모두 통과 (0 errors)
- **다음 할 일**: 사용자 확인 후 `antigravity/flow-fix-02` 병합 및 `antigravity/w2b-1c`(`3f27c02`, C-4 완료 커밋) 리뷰/마무리.
- **주의점**:
  - 원격 push 금지 (로컬 커밋만 유지).
- **재현 명령**:
  - `PATH="/opt/homebrew/opt/node@24/bin:$PATH" npm --prefix frontend test -- src/portal/workspace-records.test.tsx src/portal/screens.test.tsx`
  - `PATH="/opt/homebrew/opt/node@24/bin:$PATH" npm --prefix frontend test`
  - `PATH="/opt/homebrew/opt/node@24/bin:$PATH" npm --prefix frontend run lint && PATH="/opt/homebrew/opt/node@24/bin:$PATH" npm --prefix frontend run format:check && PATH="/opt/homebrew/opt/node@24/bin:$PATH" npm --prefix frontend run typecheck`

# 2026-10-18 FLOW-FIX-01 `frontend/src/flow/projects.test.tsx` 날짜 경과 실패 7건 수정 완료

- **브랜치**: `antigravity/flow-fix-01` (기준 `main` `2be292e`; 병행 `antigravity/w2b-1c` `3f27c02`는 그대로 보존)
- **마지막 커밋**: `git log -1 --oneline` 참조
- **끝난 것 (FLOW-FIX-01)**:
  - `frontend/src/flow/projects.test.tsx`:
    - `beforeEach`에 `vi.useFakeTimers({ toFake: ["Date"] })` 및 `vi.setSystemTime(new Date("2026-10-13T09:00:00+09:00"))` 설정, `afterEach`에 `vi.useRealTimers()` 복원 추가.
    - `Projects.tsx` 등 제품 코드, 픽스처, 다른 테스트 파일 변경 없음.
  - 검증 결과:
    - `npm --prefix frontend test -- src/flow/projects.test.tsx`: **11 passed (11)**
    - `npm --prefix frontend test`: **Test Files 77 passed (77), Tests 613 passed (613) — 실패 0건**
    - `npm --prefix frontend run lint`, `npm --prefix frontend run format:check`, `npm --prefix frontend run typecheck`: 모두 통과 (0 errors)
  - 날짜가 박힌 다른 테스트 파일(51개) 및 `new Date()`/`Date.now()` 의존 컴포넌트 렌더링 테스트 목록 조사 완료(수정은 하지 않고 보고).
- **다음 할 일**: 사용자 확인 후 `antigravity/flow-fix-01` 병합 여부 결정 및 `antigravity/w2b-1c`(`3f27c02`)로 복귀.
- **주의점**:
  - 오늘 날짜(`new Date()`, `Date.now()`)에 의존하는 컴포넌트를 그리는 테스트는 고정 날짜 픽스처만 두지 말고 `vi.setSystemTime`으로 시간을 고정하고 `afterEach`에서 복원한다.
  - 원격 push 금지 (로컬 커밋만 유지).
- **재현 명령**:
  - `PATH="/opt/homebrew/opt/node@24/bin:$PATH" npm --prefix frontend test -- src/flow/projects.test.tsx`
  - `PATH="/opt/homebrew/opt/node@24/bin:$PATH" npm --prefix frontend test`
  - `PATH="/opt/homebrew/opt/node@24/bin:$PATH" npm --prefix frontend run lint && PATH="/opt/homebrew/opt/node@24/bin:$PATH" npm --prefix frontend run format:check && PATH="/opt/homebrew/opt/node@24/bin:$PATH" npm --prefix frontend run typecheck`

## 2026-10-18 GW-COMPANY-05 WMS 통합·10인 합성 기술 검증 완료 / 실운영 인수 미완료

- 사용자05 승인·추가요청 회사1/부서1/총10명 최소 구성(창업 전 준비). GW7b41850+로컬main9f6cf36을 codex/gw-company-01에서 통합, 완료분 로컬main만반영·원격push/배포없음. [결과](GW_WMS통합_인수검증_GW-COMPANY-05.md), 운영 준비는결과연결문서. 최종commit은gitlog.
- 적용된w2b1_wms/gw_company_identity원본보존·새양부모gw_wms_merge로GW추가제약이름51개정규화. schema0.27/210표2295컬럼524FK·현재/목표명세/Excel2종/ERD동시갱신. WMS/GW/공통head3출발점기존행hash보존·DDL0·이름변경역적용/재적용보존. 두부모merge의downgrade -1은Ambiguous walk로운영복구금지,부모표삭제대신forwardfix/폐쇄복원.
- backend전체1065통과1skip(미빌드nativecore)·583.90초/경고35, 신규경로3+10인/복원2=5통과133.74초/경고11. 도구138·ruff242·정적/격리/DDL0. frontend전체606통과/기존Flow7실패·lint/format/build통과·기존chunk경고. 전체CI성공아님.
- 관리자1+직원9 본인동의·10동시ASGI조회100/초안10/메시지10·같은키10/타인초안40410, 실제HTTP10동시조회100(p95 120.50ms)·메시지10/중복0. 로컬단발수치이며운영용량보장아님. Chrome회사전체대표흐름/10직원화면·WMS LOT보류해제2이력/390확인. 실제QMS연계/실휴대폰/실회사검증아님.
- 폐쇄pg_dump/restore210표hash동일·복원된세션10개401·백업후연결회수재적용403/관리자200. 백업0.443초·복원/검사4.720초. RPO/RTO목표미정·첨부/키/공급자/실장애미검증. MFA/SSO/추가인증·계정복구/보존·실운영담당/환경인수전출시미완료. 실제계정/정책임의변경없음.
- 검증서버8265/5265와소유PG18/55437만사용·종료후소유ID대조삭제/볼륨정리·임시자격증명/.env제거. 공유DB/원본다른작업checkout/브라우저프로필·확장변경없음. 재현은결과표준명령과커밋된test_gw_wms_merge/test_gw_company_acceptance,work비밀의존금지. 다음ID자동착수없음.

## 2026-10-17 GW-COMPANY-04 회사 화면·협업 권한 로컬 검증 완료

- 사용자 다음진행 승인. branch `codex/gw-company-01` / `factory-studio-gw-company`, 기준55a7500, WIP72735cf·11d1e51, 최종gitlog. [결과](GW_회사화면_협업권한_GW-COMPANY-04.md).
- 기존63경로 회사 입력/인증 분기·GENERAL업무·현재부모ACL/영수증전권한·전결/위임·댓글/일정/알림/채팅, 회사선택/최초설정/본인동의/G-01~13·정적회사도움말연결. BUSINESS_READY=true는설정/활성본인연결확인후만적용. 직무표시/활성·사유/CAS/마지막보안관리자보호, 늦은응답폐기·검색/페이지. 개인체험과Flow독립보존.
- PostgreSQL18.6 전용합성DB 관련156통과470.22초(기존경고6)+직원상태추가1통과4.84초(경고2), 도구139·ruff238·정적/격리/DDL오류0. 프런트전체603통과/기존Flow7실패(610건), 최초병렬ERP/MES시간초과2는집중53/전체maxWorkers2재검사통과. lint/format/build통과·기존chunk경고. 전체CI성공아님.
- 실제Chrome 로그인/최초설정/HR가져오기/직원본인동의/일반기안·승인·저장댓글/일정참석/채팅·공지390px/표시·전결/역할·연결정지시원문폐기·동일계정복귀/도움말확인,pageerror0. 합성화면10장. 실휴대폰/실회사·운영/물리인쇄미검증. 계속편집뒤포커스복원P2·회사OpenAPI표현/불명확요청의브라우저종료복구는후속.
- schema0.26/198표/headgw_company_identity변경없음·Excel/ERD재생성없음. WMS main9f6cf36/205표/headw2b1_wms와미통합. 다음05에서양쪽메타데이터/constraint충돌대조·새merge revision·기존자료보존/양쪽회귀·P0실운영인수필수. 적용migration수정금지. 다음ID는결과확인후.
- 본인컨테이너ID대조후종료·볼륨삭제, 로컬8265/5265서버종료·임시postgres.env/container-id/browser-private.json/.env제거. 실계정/비밀번호·공유DB/컨테이너·main·원격/배포변경없음. 재현은결과문서의표준명령/수동흐름,work자격증명에의존하지말것.

## 2026-10-17 GW-COMPANY-04 WIP 브라우저 검증 완료·최종 회귀 중

회사63경로/13화면·정적도움말 연결, BUSINESS_READY=true(활성본인연결·설정확인후). 합성Chrome에서최초설정/연결동의/결재승인·댓글/일정참석/채팅390px/공지/표시편집·전결/역할/연결회수시원문폐기·동일계정복귀확인. 최종백엔드관련156묶음진행중, 직원상태집중추가예정. 프런트전체601통과9실패(기존Flow7+ERP/MES시간초과2), ERP/MES포함집중53재통과·린트/포맷/빌드통과. 정적/격리0오류·ruff238. 최종도구/DDL·기록마무리중. main9f6cf36/WMS와미통합(05), main/원격/운영변경없음. 소유PG18/55437와합성계정만사용,완료후소유컨테이너/비공개자격증명정리필수.

## 2026-10-17 GW-COMPANY-04 WIP 기존 업무 API·회사 화면 연결

사용자 다음진행 승인. 기존63경로에 회사 전용 입력/인증 분기(개인 계약 보존), 전결/위임·댓글/일정/알림/채팅의 동TX 내부함수·현재부모ACL/receipt전권한, 회사 선택/최초설정/본인동의/직원·역할 화면 연결중. HTTP회사5+선행16=21 통과, 프런트typecheck/린트통과·관련UI회귀진행. BUSINESS_READY=false 유지, 실제브라우저/최종회귀·도움말은진행중. WMS main9f6cf36/205표와GW198표의schema0.26/head분기확인,05통합전양쪽대조·새merge revision필요. 신규schema변경/공유DB·계정·main·원격/배포없음. 소유합성PG18/55437만검증용. 다음: UI보완/전수권한·화면검증/도움말/최종기록,미실행 검증은 완료로 표시하지 않음.

## 2026-10-17 GW-COMPANY-03 로컬 검증 완료 — 회사 업무 공개 전

- 사용자 다음진행 승인, branch codex/gw-company-01 / factory-studio-gw-company. 기준824c4de, WIPe35eaa3, 최종gitlog. [결과](GW_직원연결_업무권한_GW-COMPANY-03.md).
- company_identity.py/company_work.py/company_router.py: OWNER bootstrap/HR snapshot·PENDING본인동의/취소·같은쌍정지복귀·명시역할/CAS/마지막보안관리자/보안사건, GENERAL결재·게시ACL/SQL목록필터·읽기권한·재배정. 기존organization.import_snapshot를동일TX재사용, 기존정책/문서함수는명시company_mode인자(개인기본false)로유효배정/활성회사계정확인. 직무문자열을역할로임시변조하지않음.
- 준비관리API만공개. 기존63개회사업무게이트/businessReady=false/capabilities=[] 유지. 실제HTTP는설정/연결/역할/관리 검증, 결재·게시전체흐름은DB내부서비스검증. UI/회사선택·협업전체ACL/도움말은04, 실운영P0/복구·MFA인수는05. 다음ID는결과확인후.
- 전용Postgres18/55437 관련147통과(146묶음401.63초·기존경고6+회사병렬/합의/참조/전결1개6.14초), 최종3집중재검사16.89초통과. 도구139/공식ruff233·dbvalidate/R1R6/DDL0. 새시나리오16개. 스키마변경/새migration없음(schema0.26/headgw_company_identity 유지), Excel/ERD재생성없음. 전체backend/frontend/브라우저/실기기/실운영미검증·기존Flow프런트7실패미해결.
- 테스트컨테이너 factory-studio-codex-gw-company-test 본인ID검증후종료·볼륨제거, 임시postgres.env/container-id/.env없음. 공유DB·실제계정·비밀번호·main·원격·운영변경없음. 표준재현명령은결과문서, work의비공개파일에의존하지말것.
- **통합주의**: 병행main은다른작업에서9f6cf36으로전진(PWA포함·WMS205표/schema0.26/w2b1_wms). 이GW는198표/schema0.26/gw_company_identity. 양쪽head가flow_board_custom에서분기. 04/통합전양쪽schema버전·추가표·제약/기존자료보존·새merge revision을대조/재검증하고 적용migration수정금지. 이번147은최신WMS main과통합된검증아님. 원본다른작업자checkout보존. 원격push/배포없음.

## 2026-10-17 GW-COMPANY-03 WIP 직원 연결·업무 권한

사용자 “다음 진행해줘” 승인. 회사 최초 설정/HR 명시적 스냅샷·PENDING 본인 동의/취소·동일쌍 정지복귀/명시 역할·마지막 보안관리자 보호, 일반 결재·게시 내부 ACL/읽기권한·재배정 구현중. 준비 관리 API만 추가하고 기존63개 업무 회사게이트/businessReady=false 유지. 최초9개 새 시나리오 통과 후 위임·조직·동시회수 및 기존회귀 진행중. schema/마이그레이션 변경없음. 전용 합성Postgres18/55437만 사용, 실제계정·공유DB·main·원격·운영변경없음. 다음: 현재 코드 전체회귀/기록 마무리, 04 UI/전체경로 통합은 이번ID 완료보고 뒤 확인.

## 2026-10-17 GW-COMPANY-02 기반 구현·로컬 검증 완료

- branch codex/gw-company-01 / factory-studio-gw-company. 기준06e4a70, WIP35be30e, 최종커밋gitlog. 사용자전체설계/구현승인. main은PWA e02097d/기록0a45562 그대로, 원격/운영미반영.
- 보안5표·새revision gw_company_identity(head flow_board_custom 뒤), schema0.26/198표2151컬럼488FK·현재/목표Excel/ERD. 회사잠금→계정잠금→세션행검증·principal/명시역할·receipt전authorize, HR읽기계약·관리회수재검증. /gw/companies,/me만상태조회·businessReady=false. 기존63업무회사요청은409,person가장400. 공개본인연결/역할/업무ACL/화면은03/04후속.
- 전용Postgres18 관련API131/기존경고6·도구139·공식ruff230파일·정적/격리/DDL0. 왕복 head→flow_board_custom→head와198테스트원장건수/hash동일. 이력있는downgrade거부·복합FK·회수경합·receipt재노출차단·시드/초기화보호 확인. [결과/재현](GW_회사인증_기반검증_GW-COMPANY-02.md). 실브라우저/실휴대폰/회사실운영/전체CI미실행, 기존Flow프런트7실패유지.
- 최초공유테스트컨테이너에서메모리부족으로중단한결과는성공아님. 별도컨테이너로131재검증완료. 검증전용컨테이너/임시자격증명은종료시제거,공용DB설정변경없음. 다음재현시새 `_test` DB/임시자격증명준비. work/env/node_modules스테이징금지.
- 다음은ID별결과확인후03(bootstrap/본인연결동의/명시역할/결재·게시/읽기·재배정ACL). 현재게이트를부분해제하지말것. P0 MFA/계정복구/보존/RPO·RTO는별도실인수미정. 원격push/실서버배포금지.

## 2026-10-17 GW-COMPANY-02 WIP 기반 구현

- 사용자 전체설계·구현 승인. branch codex/gw-company-01 / factory-studio-gw-company, 기준06e4a70, 마지막커밋gitlog. 실제DB/계정/원격/운영/main변경없음.
- 신규5표·revision gw_company_identity/명세198표2151컬럼488FK·현재/목표Excel/ERD. 회사TX/세션/권한/receipt기반, HR읽기계약, /gw/companies,/me 상태조회. 회사업무63경로는409로닫음(후속03/04), 본인대신person입력400. 시드복사/초기화·이력있는downgrade보호. [검증](GW_회사인증_기반검증_GW-COMPANY-02.md).
- 정적/DDL0·공식ruff/ExcelQA완료. 관련API/최종도구/왕복진행중. 최초공유Postgres _test 회귀는 out-of-shared-memory로중단(30통과/오류1·중단). 다른작업의공용설정변경없이 **소유컨테이너 factory-studio-codex-gw-company-test:55437** 새로생성, factory_studio_gw_company_test에서 재검사. 임시자격증명work/gw-company/postgres.env(비공개), 테스트runner/log는work/gw-company. 실제DB URL인계금지. 컨테이너정리는검증완료후본인생성분만.
- Node24/기존Python3.14 venv사용, repo임시.env는CI dry-run용합성주소(실제연결정보아님), work/db-design/node_modules는bundled artifact symlink. env/work/node_modules스테이징금지. 최종결과기록·커밋필수. 다음03은ID별결과확인후, P0인수·실기기·업무UI완료아님.

## 2026-10-17 GW-COMPANY-01 설계 대조 완료 · 제품 미착수

- branch codex/gw-company-01, folder factory-studio-gw-company, 기준PWA제품e02097d+main기록0a45562, 마지막커밋gitlog. main에는PWA만반영, 원격/운영없음. 원본antigravity보존.
- [통합설계](../modules/gw/회사인증_권한_통합설계_GW-COMPANY-01.md)/[63경로](GW_회사인증_경로감사_GW-COMPANY-01.md): 회사/조직중복없음, 신규GW5표·6권한·본인연결·GENERAL결재/협업ACL·회사query/늦은응답/receipt·회수잠금제안. 구GW-EXT-A/화면/CORE에개정안연결. 전체설계확인대상·제품/DB미적용.
- 정적검증: 기존router AST63경로와감사표63행일치, 재사용컬럼확인, 문서상대링크0오류·현황200줄·diff공백0.  제품테스트/브라우저/DB미실행. 기존PWA31/API12/전체597/604·Flow7baseline실패는이전검증이며GW검증으로재사용금지.
- 다음사용자전체설계확인→GW-COMPANY-02(DB설계/마이그레이션/게이트). spec §7 잠금순서회사16→전역user관리→세션행과계정/세션회수전수검사, 63경로+신규경로ACL·개인체험보존필수. P0실운영MFA/복구/보존미정은회사지시없이채우지않음. 원격push/운영배포금지(이번사용자범위는로컬main만).

# 2026-10-18 W2b-1c C-4 W-11 적치 완료·취소 및 PUTAWAY 전표 반영 완료 (W2b-1c 전체 완료)

- **브랜치**: `antigravity/w2b-1c`
- **마지막 커밋**: `git log -1 --oneline` 참조
- **끝난 것 (C-4 및 W2b-1c 전체)**:
  - W-11 적치 완료·취소 백엔드 (`backend/src/fs/wms/`):
    - `receiving_schema.py`: `PutawayComplete` (`toLocationId`) 정의.
    - `receiving.py`:
      - `complete_putaway_task`: `FOR UPDATE OF t` 잠금, `status != 'OPEN'`이면 409 Conflict(`INVALID_STATE`), 목적지가 동일 창고의 활성 `NORMAL` 위치(출발 칸 제외)인지 검증(위반 시 400). 단일 트랜잭션(`base._action`) 안에서 `PUTAWAY` 재고 전표(`wms.stock_document`, `status = 'posted'`, `source_key = None`[`c624_check`], `source_ref = task_no`)와 `wms.stock_move` 2줄(출발지 `-qty`, 도착지 `+qty`) 생성 후 `c1480_check` 준수를 위해 단일 `UPDATE`로 `status = 'DONE'`, `to_location_id`, `done_at`, `stock_document_id` 동시 반영.
      - `cancel_putaway_task`: `FOR UPDATE OF t` 잠금, `status != 'OPEN'`이면 409 Conflict(`INVALID_STATE`), 단일 `UPDATE`로 `status = 'CANCELLED'`, `to_location_id = NULL`, `done_at = NULL`, `stock_document_id = NULL` 반영(재고 전표 미생성).
      - `guard_master`: `wms.putaway_task` 참조 시 창고·위치·품목 비활성화/변경 보호.
    - `router.py`: `POST /api/v1/wms/putaway-tasks/{row_id}/complete`, `POST /api/v1/wms/putaway-tasks/{row_id}/cancel` 추가 및 `DocumentType`에 `"PUTAWAY"` 추가, `/stock`의 `locationType`을 6종으로 확대.
    - `service.py`: `dashboard()` 월별 입출고 흐름 집계에서 내부 이동인 `'PUTAWAY'`를 `'TRANSFER'`와 함께 제외.
  - W-11 적치 완료·취소 프런트엔드 (`frontend/src/wms/`):
    - `common.tsx`: `DocumentType`에 `"PUTAWAY"`, `TYPE_LABEL`에 `PUTAWAY: "적치 이동"` 추가, `StockRow`·`Move`의 `locationType` 6종 확대.
    - `Moves.tsx`: `locationType === "RECEIVING"`일 때 `"입고장"`으로 표시.
    - `Putaways.tsx`: `OPEN` 상태 상세 패널에 적치 위치 선택 드롭다운(추천 위치가 있으면 기본 선택, 없으면 빈 값으로 직접 선택 강제; 동일 창고 활성 `NORMAL` 칸 목록) 및 `적치 완료` / `적치 취소` 버튼(`X-CSRF-Token`, `Idempotency-Key` 포함) 구현. `DONE` 상태에서 생성된 재고 전표 링크(`/wms/documents?open=${stockDocumentId}`) 표시.
  - 검증 결과:
    - 백엔드 WMS 테스트: `backend/tests/test_wms_receiving.py`의 `test_putaway_complete_and_cancel_full_flow` 포함 `pytest backend/tests/test_wms.py backend/tests/test_wms_receiving.py` -> `47 passed, 5 warnings in 103.55s`.
    - 프런트엔드 WMS 및 포털 테스트: `npm --prefix frontend test -- src/wms/wms.test.tsx src/portal/favorites.test.tsx` -> `26 passed in 2.27s`.
    - 브라우저 실기동 E2E 및 390px 모바일 폭 검증 (Playwright Chromium): 입고장(`R-REC`) 입고 예정 → 도착 → 검수 확정 → 적치 전 입고장 현재고 `60.000` / LOT 총량 `60.000` 확인 → W-11 추천 위치(`R-A01`) 기본 선택 및 적치 완료(`DONE`, `PUTAWAY` 전표 `WD-20261018-002`) → 재완료 시 409 차단 및 전표 1장 유지 → 취소(`CANCELLED`) → W-05 원장(`+60 R-REC 입고장`, `-60 R-REC 입고장`, `+60 R-A01 정상`) 및 W-04 재고 현황 / W-10 LOT 현재고(`60.000` 유지, 위치 `R-A01` 이동) 대조 → 390px 모바일 폭 확인.
    - 로컬 CI (`tools/ci_local.sh`) 1~5단계:
      - 1단계: `npm run db:validate` (`errors: []`), `audit_schema_isolation.py` (`errors: []`), `unittest discover -s tools` (`Ran 136 tests in 15.857s, OK`).
      - 2단계: `ruff check` (`All checks passed!`), `ruff format --check` (`227 files already formatted`).
      - 3단계: `alembic upgrade head` & `verify_ddl_matches_schema.py` (`errors: []`), `pytest backend/tests -q -n auto -m "not perf"` (`1031 passed, 1 skipped, 50 warnings in 466.16s (0:07:46)`, xdist 작업자 탈락 0건), `pytest backend/tests -q -m perf` (`1 passed, 1032 deselected, 5 warnings in 33.87s`).
      - 4단계: `clear_test_data.py` → `alembic downgrade base` → `alembic upgrade head` → `verify_ddl_matches_schema.py` (`errors: []`).
      - 5단계: 프런트엔드 `typecheck`, `lint`, `format:check`, `build` 통과. `vitest`: `Test Files 1 failed | 75 passed (76)`, `Tests 7 failed | 604 passed (611)` — 실패 파일: `frontend/src/flow/projects.test.tsx` (7건 실패, `main` 브랜치 `2be292e`에서도 동일하게 7건 실패하는 기존 Flow 이슈).
- **다음 할 일**: 사용자 확인 및 **W2b-1c 전체 승인** 대기 (승인 후 main 병합 또는 W2b-1d 착수).
- **주의점**:
  - 사용자 확인 전까지 **W2b-1d 착수 금지** (작업 ID 하나씩 수행 후 확인 대기 규칙).
  - 원격 push 금지 (로컬 커밋만 유지).
  - 프런트엔드 전체 테스트 실행 시 기존 실패(`frontend/src/flow/projects.test.tsx`, 7 failed, `main` `2be292e`에서도 동일 실패)는 파일 이름·건수·main 동일 여부를 항상 명시한다.
- **재현 명령**:
  - `TEST_DATABASE_URL="postgresql+psycopg://factory_studio:factory_studio@127.0.0.1:55432/factory_studio_test" backend/.venv/bin/pytest backend/tests/test_wms.py backend/tests/test_wms_receiving.py -q`
  - `npm --prefix frontend test -- src/wms/wms.test.tsx src/portal/favorites.test.tsx`
  - `npm run ci:local`

# 2026-10-18 W2b-1c C-3 W-11 적치 작업 자동 생성·목록 및 실시간 추천 위치 산출 완료

- **브랜치**: `antigravity/w2b-1c`
- **끝난 것 (C-3)**:
  - 검수 확정 시 합격분 적치 작업(`wms.putaway_task`) 자동 생성:
    - `receiving.py`: `inspect_notice`에서 `accepted_qty > 0`인 명세마다 발번 `PT-YYYYMMDD-NNN`, `status='OPEN'`, `suggested_location_id=NULL`(검수 트랜잭션 경량화 및 실시간 계산 원칙), `from_location_id=normal_location_id`로 자동 생성. 격리/부족분 배제 및 멱등성 보장.
  - 단일 CTE 쿼리를 통한 실시간 추천 위치 동적 산출:
    - `receiving.py`: `list_putaway_tasks`에서 CTE(`filtered_tasks`, `candidate_locations`, `loc_stock`, `loc_totals` + `LEFT JOIN LATERAL`)로 N+1 없는 실시간 추천 위치 산출.
    - 후보 위치: 동일 창고 · `is_active` · `location_type = 'NORMAL'` · `level_kind = 'BIN'` (출발 칸 제외).
    - 제외 조건: 용량 초과(`현재고 + 적치수량 > capacity_qty`), 다른 품목 혼적 불가(`mix_items = false`), 다른 LOT 혼적 불가(`mix_lots = false`).
    - 우선순위: 1순위(동일 품목+동일 LOT) → 2순위(동일 품목) → 3순위(빈 칸) → 4순위(혼적 허용) → 없으면 NULL.
  - API 엔드포인트:
    - `router.py`: `GET /api/v1/wms/putaway-tasks` 연결 (페이징, 상태/창고/품목 필터).
  - W-11 적치 목록 화면:
    - `frontend/src/wms/Putaways.tsx`: 적치 작업 테이블, 상태 배지(대기/완료/취소), 필터 바, 실시간 추천 위치 코드/이름 표시, 상세 패널 표시.
    - `index.tsx`: 라우트 등록.
    - `backend/src/fs/core/menu_catalog.json`: WMS screens에 W-11 적치 등록.
  - 검증 결과:
    - 백엔드 WMS 테스트: `backend/tests/test_wms_receiving.py` 신규 테스트(`test_putaway_task_creation_and_idempotency_on_inspection`, `test_putaway_task_recommendation_algorithm_and_filters`) 포함 WMS 전체 46개 테스트 통과 (`pytest backend/tests/test_wms.py backend/tests/test_wms_receiving.py` -> 46 passed, 5 warnings in 100.62s).
    - 프런트엔드 WMS 및 메뉴 테스트: `npm --prefix frontend test -- src/wms/wms.test.tsx src/portal/favorites.test.tsx` 26개 테스트 통과.
    - 백엔드 정적 분석: `uv run ruff check` 및 `uv run ruff format --check` 통과 (226 files formatted).
    - 프런트엔드 정적 분석: `npm run lint`, `npm run format:check`, `npm run typecheck` 통과.
    - DB 및 도구 검증: `npm run db:validate` (205표, 2246칼럼, 507FK, errors 0), Python 3.14 도구 단위 테스트 136개 통과.
- **다음 할 일**: 사용자 확인 후 **C-4 (W-11 적치 완료·취소 백엔드+화면)** 착수.
- **주의점**:
  - 사용자 확인 전까지 **C-4 착수 금지** (작업 ID 하나씩 수행 후 확인 대기 규칙).
  - C-4 적치 완료 처리 시:
    - `status = 'DONE'`, `to_location_id` 저장, `done_at = now(KST)`.
    - `PUTAWAY` 전표(`wms.stock_document`, `document_type = 'PUTAWAY'`, `status = 'posted'`) 및 `wms.stock_move` 생성하여 재고 원장에 출발지(`from_location_id`)에서 목적지(`to_location_id`)로 이동 반영.
    - 취소(`CANCELLED`) 처리 지원.
  - 스키마 불변 (`schema.json`, 마이그레이션 변경 금지).
  - 원격 push 금지 (로컬 커밋만 유지).
- **재현 명령**:
  - `TEST_DATABASE_URL="postgresql+psycopg://factory_studio:factory_studio@127.0.0.1:55432/factory_studio_test" backend/.venv/bin/pytest backend/tests/test_wms.py backend/tests/test_wms_receiving.py -q`
  - `npm --prefix frontend test -- src/wms/wms.test.tsx src/portal/favorites.test.tsx`
  - `npm --prefix frontend run lint && npm --prefix frontend run format:check && npm --prefix frontend run typecheck`

# 2026-10-18 W2b-1c C-3a 입고장 경유 위치 흐름 검증 완화 및 시드/화면 반영 완료

- **브랜치**: `antigravity/w2b-1c`
- **끝난 것 (C-3a)**:
  - F14 적치 흐름 지원을 위한 위치 유형 완화:
    - 백엔드 (`receiving.py`): `_validate_lines`에서 `normal_location_id`의 검증을 `location_type in ("NORMAL", "RECEIVING")`으로 완화. 기존 `NORMAL`도 계속 통과하고 신규 `RECEIVING`도 허용.
    - 백엔드 스키마 (`schema.py`): `LocationType` 6종 리터럴 타입 정의 및 `LocationCreate`, `LocationUpdate`에 적용.
    - 시드 (`seed/`):
      - `common.py`: `SEED_VERSION = "sv-20261018-wms1"`
      - `wms_extension.py`: 창고별 입고장 위치 2개 추가: `("WH-RAW", "R-REC", "원자재 입고장", "RECEIVING")`, `("WH-FG", "F-REC", "완제품 입고장", "RECEIVING")` (`is_default=False`, `is_active=True`).
      - `validate.py`: `"wms.storage_location": 8` 갱신.
    - 프런트엔드 (`Inbounds.tsx`, `Warehouses.tsx`, `common.tsx`):
      - `common.tsx`: `LocationType` 6종 export 및 `Location.locationType` 적용.
      - `Inbounds.tsx`: 새 입고 예정 등록 시 창고의 `RECEIVING` 위치를 `normalLocationId` 기본값으로 자동 설정 (없으면 `NORMAL` 기본값 유지). `normalLocationId` select 옵션에서 `NORMAL` 및 `RECEIVING` 모두 허용 및 ` [입고장]` 꼬리표 표시.
      - `Warehouses.tsx`: 위치 등록/수정 폼에서 6종 위치 유형 선택 지원, `isDefault` 비활성화 조건을 DB CHECK 제약에 맞춰 `draft.locationType !== "NORMAL"`로 통일.
  - 검증 결과:
    - 백엔드 WMS 테스트: `backend/tests/test_wms_receiving.py`에 `test_receiving_location_allowed_as_normal_location` 신규 추가 포함 WMS 전체 44개 테스트 통과 (`pytest backend/tests/test_wms.py backend/tests/test_wms_receiving.py` -> 44 passed, 0 failed in 103s).
    - 프런트엔드 WMS 테스트: `npm --prefix frontend test -- src/wms/wms.test.tsx` 16개 테스트 통과 (`W-08 입고 예정 등록 시 RECEIVING 위치가 있으면 기본 선택되고 목록에 [입고장]이 표시된다` 신규 검증 포함).
    - 백엔드 정적 분석: `uv run --project backend ruff check --config backend/pyproject.toml backend` (0 errors).
    - 프런트엔드 정적 분석: `npm run lint` (0 errors), `npm run typecheck` (0 errors), `npm run format:check` (0 errors).
    - DB 및 도구 검증: `npm run db:validate` (205표, 2246칼럼, 507FK, errors 0), Python 3.14 도구 단위 테스트 136개 통과.
- **다음 할 일**: 사용자 확인 후 **C-3 (W-11 적치 작업 목록·추천 위치 백엔드+화면)** 착수.
- **주의점**:
  - 사용자 확인 전까지 **C-3 착수 금지** (작업 ID 하나씩 수행 후 확인 대기 규칙).
  - C-3 적치 작업 목록 및 추천 위치 계산 시:
    - 검수 확정 시 `wms.putaway_task`는 `suggested_location_id = NULL`로 생성(검수 트랜잭션 무거움 방지).
    - 추천 위치는 W-11 목록 조회 시 동적으로 계산.
    - 추천 기준은 실제 칼럼(`storage_location.level_kind = 'BIN'`, `mix_items`, `mix_lots`, `capacity_qty`) 활용.
    - 시험 시 `mix_items=false`, `capacity_qty`, `mix_lots=false` 세 갈래의 필터링 방어 테스트 필수.
  - 스키마 불변 (`schema.json`, 마이그레이션 변경 금지).
  - 원격 push 금지 (로컬 커밋만 유지).
- **재현 명령**:
  - `TEST_DATABASE_URL="postgresql+psycopg://factory_studio:factory_studio@127.0.0.1:55432/factory_studio_test" backend/.venv/bin/pytest backend/tests/test_wms.py backend/tests/test_wms_receiving.py -q`
  - `npm --prefix frontend test -- src/wms/wms.test.tsx`
  - `npm --prefix frontend run lint && npm --prefix frontend run format:check && npm --prefix frontend run typecheck`

# 2026-10-18 W2b-1c C-2 W-08 입고 LOT 부여 및 lot_tracked 전환 완료

- **브랜치**: `antigravity/w2b-1c`
- **끝난 것 (C-2)**:
  - 기존 데이터 감사 (`factory_studio` 및 `factory_studio_test` 전수 확인):
    - `wms.item` 중 `lot_tracked = true AND item_class <> 'FG'`: **0건**.
    - `wms.item` 중 `lot_tracked = false AND item_class = 'FG'`: **0건**.
    - `wms.inbound_notice_line` 중 `lot_tracked = false`인데 `lot_no` 존재: **0건**.
    - `wms.inbound_notice_line` 중 `lot_tracked = true`인데 `lot_no` 비어 있음: **0건** (기존 60행 전건 무결).
  - 입고 LOT 부여 및 `lot_tracked` 플래그 전환:
    - 백엔드 (`receiving.py`):
      - `_validate_lines`: `itemClass == "FG"` 검사를 `item.get("lotTracked")` 검사로 교체하여 LOT 추적 품목 필수, 비추적 품목 차단(400) 구현.
      - `inspect_notice`: 검수 확정 시 명세에 `lot_no`가 있고 `accepted_qty + quarantined_qty > 0`인 경우 `wms.lot` 행 자동 생성(`origin='RECEIPT'`, `status='AVAILABLE'`, 유효기간 자동계산, `supplier_lot_no=None`으로 비워 둠, 중복 방어).
    - 프런트엔드 (`Inbounds.tsx`):
      - `NoticeForm`: 선택된 품목의 `lotTracked` 여부에 따라 LOT 입력 필드 동적 표시 및 필수(`required`) 처리, 품목 변경 시 비추적 품목이면 `lotNo: ""` 초기화.
  - 검증 결과:
    - 백엔드 WMS 테스트: `backend/tests/test_wms.py` 신규 테스트(`test_inbound_lot_tracked_rules_and_lot_creation`) 포함 WMS 전체 43개 테스트 통과 (`pytest backend/tests/test_wms.py backend/tests/test_wms_receiving.py` -> 43 passed, 0 failed in 101s).
    - 프런트엔드 WMS 테스트: `npm --prefix frontend test -- src/wms/wms.test.tsx` 15개 테스트 통과 (`W-08 품목 lotTracked 여부에 따른 LOT 입력 필드 노출 및 초기화` 신규 검증 포함).
    - 백엔드 정적 분석: `uv run --project backend ruff check --config backend/pyproject.toml backend` (0 errors).
    - 프런트엔드 정적 분석: `npm run lint` (0 errors), `npm run typecheck` (0 errors), `npm run format:check` (0 errors).
    - DB 및 도구 검증: `npm run db:validate` (205표, 2246칼럼, 507FK, errors 0), Python 3.14 도구 단위 테스트 136개 통과.
- **다음 할 일**: 사용자 확인 후 **C-3 (W-11 적치 작업 목록·추천 위치 백엔드+화면)** 착수.
- **주의점**:
  - C-3/C-4에서 검수 확정 시 생성되는 적치 작업(`wms.putaway_task`)은 추천 위치(`suggested_location_id`)를 NULL로 생성하고 W-11 목록 조회 시 동적으로 계산(합의된 설계 원칙 준수).
  - 격리품(`quarantined_qty > 0`) 및 부족품(`shortage_qty`)은 적치 대상 제외 (`accepted_qty > 0`인 명세만 적치 대상).
  - DB 변경 없음 (`schema.json` 불변, 마이그레이션 변경 금지).
- **재현 명령**:
  - `TEST_DATABASE_URL="postgresql+psycopg://factory_studio:factory_studio@127.0.0.1:55432/factory_studio_test" backend/.venv/bin/pytest backend/tests/test_wms.py backend/tests/test_wms_receiving.py -q`
  - `npm --prefix frontend test -- src/wms/wms.test.tsx`

# 2026-10-17 W2b-1c C-1 W-08 notice_kind 보강 완료

- **브랜치**: `antigravity/w2b-1c`
- **끝난 것 (C-1)**:
  - `wms.inbound_notice.notice_kind` NOT NULL 기본값 및 4종 검증 지원:
    - 백엔드: `NoticeKind` 리터럴 타입 및 `NoticeFields` 기본값(`"PURCHASE"`), `create_notice`/`update_notice` 4종 유효성 검사 및 SQL INSERT/UPDATE 반영, `list_notices` `noticeKind` 필터링 지원.
    - 프런트엔드: `Inbounds.tsx` 필터 바 구분 셀렉트, 목록 `noticeKind` 컬럼 및 배지(`tone="issue"` for SALES_RETURN, `"normal"` for others), 등록 폼 `입고 구분` 선택 및 전송, 상세 패널 헤더 배지 및 정보 표시.
  - DB 기존 행 실측:
    - `factory_studio`: 총 60행 모두 `notice_kind='PURCHASE'` (누락 0건).
    - `factory_studio_test`: 총 5행 모두 `notice_kind='PURCHASE'` (누락 0건).
  - 검증 결과:
    - 백엔드 WMS 테스트: `pytest backend/tests/test_wms.py -v` (19 passed).
    - 프런트엔드 WMS 테스트: `npm --prefix frontend test -- src/wms/wms.test.tsx` (14 passed).
    - 백엔드 정적 분석: `ruff check` (0 errors), `ruff format --check` (227 files formatted).
    - 프런트엔드 정적 분석: `npm run lint` (0 errors), `npm run typecheck` (0 errors), `npm run format:check` (0 errors).
    - 도구 단위 테스트: `Ran 136 tests in 16.210s - OK`.
- **다음 할 일**: 사용자 확인 후 **C-2 (W-08 입고 LOT 부여 — 검수 시 `wms.lot` 생성)** 착수.
- **주의점**:
  - C-2에서 `receiving.py::_validate_lines`의 `itemClass == "FG"` 검사를 `lot_tracked` 기준으로 변경 (LOT 추적 품목 필수, 비추적 품목 제외).
  - 검수 확정 시 적치 작업(`putaway_task`) 생성 시 `suggested_location_id`는 NULL로 두고 W-11 목록 조회 시 동적 계산.
  - 격리품(`quarantined_qty > 0`) 및 부족품은 적치 작업 생성에서 제외 (`accepted_qty > 0`인 명세만 생성).
- **재현 명령**:
  - `TEST_DATABASE_URL="postgresql+psycopg://factory_studio:factory_studio@127.0.0.1:55432/factory_studio_test" backend/.venv/bin/pytest backend/tests/test_wms.py -v`
  - `npm --prefix frontend test -- src/wms/wms.test.tsx`

## 2026-10-17 PWA-POLICY-01 로컬 main 반영 · GW 설계 대조 시작

사용자 지시로 PWA `e02097d`를 로컬 main에 ff 병합. 원격/실서버 변경 없음. main 폴더는 factory-studio-help-main, 새 GW 브랜치는 codex/gw-company-01 / factory-studio-gw-company. 다음은 기존 GW-EXT-A와 core.company/HR/Flow 인증·조직 재사용 대조이며 제품DB 적용 전 전체설계 확인 필요. 기존 Flow 회귀7실패 보존. 이전 아래 항목의 main 미반영 표시는 이 기록으로 갱신한다.

## 2026-10-17 PWA-POLICY-01 완료 · 당시 main/운영 미반영

- 브랜치 `codex/pwa-policy-01`, 폴더 `/Users/hwang-kyoungho/projects/factory-studio-pwa-policy`, 기준main `eaa01eb`. 마지막 커밋은 `git log -1 --oneline`. 원본 `antigravity/w2b-1b` 및 main 보존.
- 사용자 고도화 순서 승인. 첫 ID는 기존 승인 HR-TIME-01의 회사 정책 적용 보정: 요약/잔여 일 환산/연차·반차 제출/분 단위 선택. [검증](PWA_정책화면_일치_PWA-POLICY-01.md), [순서](../plan/시스템고도화_진행순서_UPGRADE-01.md). 시간대 Seoul·당일1휴게, 잘못된 정책/홀수 반차 차단. 새정책화면·DB·실제계정/정책/원장변경없음.
- 검증 관련31/31·격리근무API12/12·type/lint/format/build·Chrome모의API1440/390/4종제출JSON/pageerror0. 전체597/604·Flow기존7실패. main에서도해당7동일실패, ERP/MES재검사통과. 전체성공아님. main/push/운영/실기기미실행. `work/` 로그·스크린샷은임시, 보고서에재현절차/실패근거기록.
- 다음: AGENTS §1 ID별결과확인, 기존Flow회귀실패별도점검, GW-EXT-A는전체확인대기설계이고현재core.company와중복/차이있어최신대조먼저. 실제회사운영/실기기/장비조건을임의확정하지않음. 이전문서배포승인을새회사인증운영승인으로확대하지않음.
- 재현 Node24: `npm --prefix frontend test -- src/hr/Work.test.tsx src/hr/workPolicy.test.ts src/hr/Users.test.tsx src/portal/content-pages.test.tsx`. 격리 `_test` DB를 새로 준비하고Python3.14로head적용후 `pytest backend/tests/test_hr_work.py -q`. `.env`/비밀번호/`work`/node_modules스테이징금지.

## 2026-10-15 OPS-CAD-02 CAD·YC main 수동 운영 배포 완료

사용자수동배포요청으로 운영3a6019f→main제품c0f118e 반영(12:00KST). backend/DB/시드차이0, 정확main frontend601·CAD154/type/lint/format/build/격리/dbvalidate통과. GitHub결제차단은수동검증으로대체하여 --skip-ci-check 명시사용(CI성공아님). 보호백업r2검증·회사/계정191표건수/hash보존·APIactive/공개원점200/DDL0/최근5xx0·시드유지·공개NC JS/CSS SHA동일/비로그인비누401. 공개운영실Chrome합성NC/STEP/에너지/모의음성→3카드/3번재생/정지/복귀/출력미리보기/변경무효화/390/pageerror0통과. 실마이크/실장비/실측/운영계정쓰기미검증. 초기backup fingerprint별칭오류는배포전중단/API복구후보정·r2재검증,원장변경없음. [배포기록](main_수동운영배포_OPS-CAD-02.md). 다음사용자결과확인/실발화리허설,자동다음ID없음.

- branch main factory-studio-help-main. 운영제품c0f118e/기록커밋gitlog분리. 보호백업 /srv/factory-studio/backups/20261015-cad-c0f118e-r2. 공개검증script/명령/실행범위는배포기록참조. GitHub결제gate수동대체명시·계정/DB초기화없음·진행중antigravity미병합.

CAD-UI04 제품3818b38 main/origin 반영 완료. CI38403227492/check115315971025는 runner시작전 결제/지출한도 차단(annotation확인). 새운영UI 배포미실행·CI우회없음. 로컬검증용5263/Chrome 종료, 실제회사/계정/원장/병행브랜치변경없음.

## 2026-10-13 CAD-UI04 NC·YC 제품 화면 구조 적용 완료

사용자 UI03 Figma시안 이후 진행 승인. 좌준비단계/중앙실제뷰어/우속성YC/하단재생. 제안중앙비교→번호확대/뷰어1·YC접근·고정재생·닫기/Esc/단계복귀, 값/핸들러/원본행/출력/검증유지. CAD154/대상frontend33/build/격리/format/diff·실Chrome합성Worker/모의음성이벤트/3카드/3번진행/정지/복귀/변경무효화/원본행/FANUC미리보기/390넘침0/pageerror0통과. Figma신규조회한도로보관시안/script대체·완벽동일주장없음. 실마이크/운영새UI/실장비/DB검증미실행. branch codex/cad-ui04, 마지막커밋gitlog. [결과](NC_YC_UI_적용검증_CAD-UI04.md). 다음확인/운영·실발화검증, 다른ID자동착수없음.

- 기준main ee9555a+설계b60a2a4, 별도factory-studio-cad-ui04. 기존업무/DB/계정/원장/antigravity변경없음. 재현명령/script/PNG는결과참조. main승인범위로반영후CI확인, 우회없음. 마지막커밋 git log -1.

## 2026-10-13 CAD-UI03 NC·YC Figma 구조 시안

사용자 제안방향 확인 후 Figma Design Z9reC31WUdfLMhfC02VM2m 생성. NC우선5상태/7화면·공통5가족17variants/20변수/3텍스트스타일/113instances·클릭전환·중앙뷰포트/좌준비단계/우속성YC/하단재생. 7화면 최초구조넘침0/글꼴불일치0, 5상태캡처시각확인. 마지막진행/완료구분·초기제안차단 수정성공 뒤 Starter MCP호출한도로 캡처/최종구조재검증미실행. 이미지직전버전/시뮬레이션SVG도식/클릭은모의. 제품코드/DB/배포변경없음. 다음 사용자시안확인→최종보정검증/전체확인→별도제품UI적용. [설계기록](../modules/cad-cam/NC_YC_화면구조_CAD-UI03.md).

- branch codex/cad-ui03-design / factory-studio-cad-ui03, 기준main ee9555a. 마지막커밋 git log -1. Figma URL/node·작성script·ledger·PNG는기록폴더참조. 제품변경없음/원장계정보존. 마지막후캡처미검증을완료표시하지말것. 도구한도는Figma플랜/GitHubCI와구분.

# 2026-10-13 OPS-CI-01 로컬 CI 스크립트 개발 및 전 단계 검증 완료

- 브랜치: `antigravity/ops-ci-01`
- 마지막 커밋: `git log -1 --oneline`
- 끝난 것:
  - `tools/ci_local.sh`: `.github/workflows/ci.yml`과 동일한 순서의 1~5단계 로컬 CI 스크립트 작성.
  - `package.json`: `"ci:local": "bash tools/ci_local.sh"` 추가.
  - `tools/test_ci_local.py`: `--help`, `--dry-run`, 미지원 옵션, `_test` 접미사 검사 단위 테스트 작성 (4/4 passed).
  - 안전장치 구현:
    - Node 24 (`/opt/homebrew/opt/node@24/bin`) 및 Python 3.14 (`backend/.venv/bin`) PATH 우선 적용.
    - PostgreSQL 18.6 버전 검증 및 테스트 DB `_test` 접미사 강제.
    - 터미널/로그에 비밀번호 미노출 (DB명만 출력).
    - 4단계 DB 초기화 전 대상 안내 및 5초 취소 대기 시간 부여.
    - pytest 병렬 워커 임시 복제 DB(`factory_studio_ci_*_test`) 자동 정리.
    - 가상 환경 디스크/I/O 지연 대응: `pytest -m perf` 및 `npm test` 1회 재시도 보호.
  - 검증 완료:
    - `tools/ci_local.sh` 전체 실행: 1~5단계 전체 통과 (백엔드 1,020 passed/1 skipped, perf 1 passed, 도구 137 passed, 프런트 601/601 passed).
    - 의도적 실패 검증: 2단계 ruff format 미준수 주입 시 즉시 중단 확인.
    - `--help`, `--dry-run` 무해성 및 비밀번호 미노출 확인.
- 다음 할 일:
  - 사용자 최종 리뷰 후 `main` 병합.
  - GitHub Actions 결제 해결 전까지 배포 전 로컬 검증 표준으로 활용 (`npm run ci:local`).
- 주의점:
  - `tools/ci_local.sh` 실행 시 포트 55432의 PostgreSQL 18 컨테이너가 켜져 있어야 한다 (`uv run --project backend --env-file .env python tools/start_local.py db`).
  - 단일 프런트엔드 테스트 실행 시 반드시 `npm --prefix frontend test -- <파일>`을 사용한다 (`npx vitest run` 사용 금지).
- 재현 명령:
  - `npm run ci:local -- --help`
  - `npm run ci:local -- --dry-run`
  - `npm run ci:local`

# 2026-10-17 W2b-1b B-3 W-10 LOT 보류·해제 이력 및 QMS 연동 완료 (W2b-1b 전체 완료)

- **브랜치**: `antigravity/w2b-1b`
- **끝난 것 (B-3 및 W2b-1b 전체)**:
  - W-10 LOT 보류·해제 백엔드 (`backend/src/fs/wms/`, `backend/src/fs/qms/`):
    - **DB 불변 및 이력 누적 원칙 준수**: `schema.json` 변경 없음. `wms.lot_hold`의 부분 고유 인덱스(`UNIQUE (workspace_id, generation_id, lot_id) WHERE (released_at IS NULL)`)를 기반으로, 보류 시 새 행 INSERT(`released_at=NULL`), 해제 시 UPDATE(`released_at=clock_timestamp()`), 재보류 시 새 행 INSERT로 다중 보류/해제 이력을 영구 보존.
    - 엔드포인트: `POST /lots/{id}/hold`, `POST /lots/{id}/release`.
    - 중복 및 유효성 방어: 보류 중인 LOT에 보류 시도 시 409 Conflict, 미보류 LOT 해제 시도 시 409 Conflict.
    - QMS 보류 조회 연동: `fs.qms.interface`의 `is_enabled`, `active_hold_details(conn, scoped, lot_no)`를 통해 QMS 검사 및 보류 상태를 읽기 전용으로 안전하게 조회 (`qmsHold: { active, holdNo, reason }`).
    - LOT 목록 및 상세 연동: `list_lots`에서 QMS 활성 보류 여부(`qmsHold: true/false`) 반환, `_lot_row`에서 활성 보류 정보, QMS 보류 상세, 최근 50건 보류 이력(`status: "HELD" | "RELEASED"`) 반환.
  - W-10 LOT 보류 프런트엔드 (`frontend/src/wms/Lots.tsx`):
    - 목록 테이블: LOT 상태 배지 옆에 QMS 보류 시 `<Badge tone="issue">QMS 보류</Badge>` 표시.
    - 상세 패널 현재 보류 카드: 활성 보류 중일 때 보류 사유, 출처, 일시 표시 및 "보류 해제" 버튼 제공. 미보류 시 "보류 설정" 버튼 제공.
    - 인라인 보류 등록 폼: 출처(MANUAL/QMS/EXPIRY), 원천코드, 보류 사유(2자 이상 필수) 입력 및 등록 처리.
    - QMS 품질 검사 상태 카드: QMS 모듈 활성화 여부 및 활성 보류 상세 표시, "QMS 보류 동기화" 버튼 연동.
    - 보류 이력 테이블: 최신 50건 상태(보류중/해제됨), 출처, 보류 사유, 보류일시, 해제일시, 해제사유 표시.
    - 모바일 390px 반응형 뷰포트 최적화.
  - 브라우저 실기동 자동화 검증 완료 (`frontend/scripts/verify-wms-hold-browser.mjs`):
    - 게스트 세션 시작 → LOT 등록 → 1차 수동 보류(MANUAL) → 1차 해제 → 2차 QMS 재보류 → 2차 해제 전 과정 통과 및 이력 2건 영구 보존 확인.
    - 스크린샷 5종 보존 (`wms-lots-initial.png`, `wms-lots-hold-active.png`, `wms-lots-hold-released.png`, `wms-lots-hold-second.png`, `wms-lots-mobile-390.png`).
  - A-2 검증 지표 실측치:
    - `verify_ddl_matches_schema.py` 오류 수: **0건** (205표, 2,246칼럼, PK 205, UK 425, CHECK 502, INDEX 165, UNIQUE_INDEX 46, FK 507 100% 일치).
    - 왕복 결과: `downgrade base` -> `upgrade head` 후 다시 **오류 0건**.
    - 적용 DB 목록: `factory_studio`, `factory_studio_test`, `factory_studio_ci_test` 모두 **`w2b1_wms (head)`** 상태.
    - **백엔드 pytest 요약 줄 전문**:
      - `1023 passed, 1 skipped, 47 warnings in 454.01s (0:07:34)` (not perf)
      - `1 passed, 1024 deselected, 5 warnings in 26.56s` (perf)
      - **총 1,024 passed, 1 skipped (실패 0건, 에러 0건, worker down 0건)**.
    - 도구 단위 테스트: `Ran 136 tests in 16.184s - OK`.
- **다음 할 일**: 사용자 확인 및 **W2b-1b 전체 승인** 대기 (승인 전 W2b-1c 임의 착수 금지).
- **주의점**:
  - `wms.lot`에 수량 및 만료 여부를 컬럼으로 저장하지 않는다 (원장 집계 및 실시간 판정 원칙).
  - `wms.lot_hold`는 부분 인덱스를 활용해 활성 1건만 유지하되 과거 해제 이력을 삭제하지 않고 유지한다.
- **재현 명령**:
  - `backend/.venv/bin/pytest backend/tests/test_wms.py -v`
  - `npm --prefix frontend test -- src/wms/wms.test.tsx`
  - `npm run ci:local`

# 2026-10-15 W2b-1b WMS-FIX 완료

- **브랜치**: `antigravity/w2b-1b`
- **끝난 것 (WMS-FIX)**:
  - `tools/test_fs024a.py`: WMS 표 개수 가드 23으로 업데이트 (`W2b-1a` 및 `W2b*` 분기 추가, 이전 6/11 분기 유지).
  - `tools/test_dsn11.py`: `test_rebuild_from_schema_json_is_identical` 분리·제거(안 B 채택) 및 사유 주석 기록 (W2 단계마다 `schema.json`에 목표 표가 선반영되어 재생성 비교가 성립하지 않으며, 목표 설계 검증은 `test_contract_holds`, `test_rejects_regressions`, `validate_db_design.py --schema`가 전담).
  - `tools/rebuild_target.py`: docstring 상단에 "W2 이후에는 schema.json이 진화해 결과가 목표 파일과 달라진다. 설계 단계 재현용이다" 안내 추가.
  - `docs/modules/wms/WMS_보강설계_DSN-13.md`: 8절(구현 및 스키마 반영 메모) 추가하여 `apply_dsn90.py` 재적용 시 `CMMS_ISSUE` 중복 생성 제약 및 기존 WMS 3표 칼럼 순서(DDL 대조 0건으로 기능 영향 없음) 문서화.
  - `backend/alembic/versions/20261013_w2b1_wms.py`:
    - `downgrade()` 복원 시 `c831_check` -> `c781_check` (`storage_location`), `c818_check` -> `c768_check` (`source_claim`)로 pre-w2b1 원래 제약 이름 복원 (`alembic downgrade base` 전체 왕복 성공).
    - `MODULE_CHECKS = []` ruff 포맷 보정.
  - `backend/tests/test_wms.py`: ruff I001 import 정렬 보정.
  - `frontend/src/portal/favorites.test.tsx`: W-10 LOT 메뉴 추가에 따른 메뉴 카탈로그 개수 가드 113 -> 114 보정 (`menuCatalog` 114개 키·경로 고유성 100% 통과).
- **검증 결과**:
  - `python -m unittest discover -s tools -p 'test_*.py'`: **136 passed (OK)**.
  - `npm run ci:local`: **1~5단계 전체 통과 (SUCCESS)**.
    - 1단계: DB 정적 검증(`npm run db:validate`, 0 errors), 격리 감사(`audit_schema_isolation.py`, R1~R6 0 errors), 도구 단위 테스트 (136 passed).
    - 2단계: 백엔드 ruff check & ruff format check (227 files, 0 errors).
    - 3단계: 마이그레이션 적용 및 `verify_ddl_matches_schema.py` (0 errors), pytest (1,022 passed, 1 skipped, 1 perf passed).
    - 4단계: `clear_test_data.py` -> `downgrade base` -> `upgrade head` -> `verify_ddl_matches_schema.py` (0 errors, 완벽한 왕복).
    - 5단계: 프런트엔드 `typecheck`, `lint`, `format:check`, `build`, `test` (75 test files, 603 passed, 0 errors).
- **다음 할 일**: 사용자 확인 후 **B-3 (W-10 보류·해제 이력)** 착수.
- **주의점**:
  - `lot_hold`는 이력 표: 해제 시 UPDATE 금지, 행 새로 쌓기 (`status='HELD'` / `'RELEASED'`).
  - 현재 보류 여부는 최신 행으로 판정 (`active_holds` CTE 검증).
  - 브라우저에서 보류 걸기 → 해제 → 재보류 흐름 검증 필수.
  - QMS 보류 조회 연동(읽기 전용, `fs/qms/interface.py`).
- **재현 명령**:
  - `python -m unittest discover -s tools -p 'test_*.py'`
  - `npm run ci:local`

# 2026-10-15 W2b-1b B-2 W-10 LOT 조회·등록 완료

- **브랜치**: `antigravity/w2b-1b`
- **끝난 것 (B-2)**:
  - W-10 LOT 백엔드 (`backend/src/fs/wms/`):
    - `wms.lot` 조회/등록/수정 API (`GET /lots`, `GET /lots/{id}`, `POST /lots`, `PATCH /lots/{id}`).
    - **LOT 수량 DB 미저장 원칙 준수**: 단일 출처는 재고 이동 원장(`wms.stock_move`). N+1 방지를 위해 `WITH lot_stock AS (...)`, `active_holds AS (...)` 단일 질의로 현재고(`qty_on_hand`) 및 활성 보류 산출.
    - 만료 여부 DB 미저장: `business_today()` 기준 조회 시 실시간 판정 (`isExpired`).
    - 페이징: `fs/common/page.py` (`Page(offset, limit).checked()`) 표준 적용.
    - 품목별 `lot_tracked` 플래그 반영 전표 줄 검증(`_validate_lines`).
  - W-10 LOT 화면 (`frontend/src/wms/Lots.tsx`):
    - 목록: LOT 번호, 상태 배지(가용/보류/만료), 품목, 현재고(원장 합계), 입고일, 유효기간, 공급처 LOT, 출처, 관리(상세).
    - 필터: 품목 드롭다운, 상태 드롭다운, 키워드 검색, 만료만 보기 토글.
    - 등록 패널 (`FormPanel`): 품목 선택(선택 시 `shelfLifeDays`로 유효기간 자동 제안), LOT 번호, 입고일, 유효기간, 공급처 LOT, 출처.
    - 상세 패널 (`DetailPanel`, wide): 기본 정보, 원장 집계 총 재고 및 위치별 재고 분포(`locations`), 보류 상태/이력(`holds`), **B-3 보류 안내 문구** 명시.
    - 메뉴 및 라우트 등록: `menu_catalog.json` (W-10 LOT·보류), `WmsRoutes` (`/wms/lots`).
    - 표준 훅: `useSend` 훅으로 CSRF 토큰 및 멱등키 보장.
  - 검증 결과:
    - 백엔드 WMS 테스트: `pytest backend/tests/test_wms.py -v` (17 passed).
    - 프론트엔드 테스트: `npm --prefix frontend test -- src/wms/wms.test.tsx` (12 passed).
    - 프론트엔드 검사: `npm run lint` (0 errors), `npm run typecheck` (0 errors), `npm run format:check` (Prettier 통과), `npm run build` (tsc & vite) 통과.
    - 백엔드 린트: `ruff check backend/src/fs/wms/` & `ruff format --check` 통과.
    - **브라우저 실기동 및 기능 검증 (`verify-wms-browser.mjs`)**:
      - `/wms/items` (B-1 품목 보강 확인): 테이블 컬럼 및 등록 폼에 유효기간, ABC, 안전/최대재고, PLM 필드 노출 확인.
      - `/wms/lots` (B-2 LOT 등록): `LOT-20261015-LIVE` 등록, 목록 및 상세 패널 정상 확인.
      - **원장 수량 실시간 대조**: 기초재고 전표 750 EA 확정 후 LOT 목록 및 상세에서 현재고가 즉시 정확히 750 EA로 증가 일치 확인!
      - 390px 모바일 뷰포트 레이아웃 검증 완료.
    - **A-2 검증 지표 실측치**:
      - `verify_ddl_matches_schema.py` 오류 수 (적용 후): **0건**
      - 왕복 결과: `downgrade -1` -> `upgrade head` 후 다시 **오류 0건**
      - 적용 DB 목록: `factory_studio` 및 `factory_studio_test` 둘 다 **`w2b1_wms (head)`** 상태.
- **다음 할 일**: 사용자 확인 후 **B-3 (W-10 보류·해제 이력)** 착수.
- **주의점**:
  - B-3 사용자 확인 전 착수 금지.
  - DB 변경 없음 (W2b-1a 확정분 유지).
- **재현 명령**:
  - `TEST_DATABASE_URL="..." pytest backend/tests/test_wms.py -v`
  - `npm --prefix frontend test -- src/wms/wms.test.tsx`
  - `npm --prefix frontend run lint && npm --prefix frontend run typecheck && npm --prefix frontend run build`
  - `node frontend/scripts/verify-wms-browser.mjs`

# 2026-10-13 W2b-1b B-1 품목 보강 (W-07) 완료
CAD-V03 제품 c0efb5b main/origin push 완료. 운영 새흐름 배포 미실행. 최종 main CI도 runner 시작 전 결제/한도 차단 확인(check115285673525). 실마이크 미검증, 기존 MES 브랜치 보존.

## 2026-10-13 CAD-V03 YC 예제·음성 요청 흐름 보정 완료

YC 예제 클릭→마이크 요청/합성NC·STEP·소재·장비·품질 준비→헤이와이씨/파일최적안요청→정지카드3→번호확대재생. Step4는 계산만 하고 자동팝업 제거. 실제업로드는 기존조건검증 유지/후보수강제없음. CAD154/대상frontend33/build/격리/format·실Chrome모의인식이벤트 전체흐름/진행률·정지/복귀/390/입력중단/재시도/pageerror0. 실마이크/운영새흐름/실장비/DB검증미실행·CI우회없음. branch codex/cad-v03, 기준main65aaea5; main반영/push는 승인된 기존반영범위. [결과](YC_음성요청_흐름검증_CAD-V03.md). 공유MES변경없음, 이전antigravity로컬휴디코드와최신빌드구분. 다음결과확인/실발화·운영검증, 다음ID자동착수없음.

- 재현: Node24 prototype npm ci/test, frontend npm ci/build 및 대상33검사, 정적빌드5260+assets/cad-v03/voice-flow-check.mjs. 마지막커밋 git log -1. 실마이크는모의인식과구분. 계정/DB/원장/비밀번호변경없음.

# 2026-10-12 OPS-CAD-01 main push / CI billing blocker

CAD17/V02 merged into main (13f3a8e), NC help markup fixed. CAD154/frontend596/build/isolation/format passed. Runs38258159540/38258223617 failed before any step due to billing or spending limit. Server41ca68d/APIactive preserved; latest CAD deployment not executed. Next: owner resolves Billing & plans, rerun exact main HEAD CI, then backup/standard deployment. See docs/agent/main_CI_배포점검_OPS-CAD-01.md. Final commit: git log -1 --oneline. Shared MES changes untouched. Backend/DDL roundtrip and new browser/microphone checks not run.

## 2026-10-12 CAD-V02 STEP·YC 카드 완료 인계

- branch codex/cad-v02, `/Users/hwang-kyoungho/projects/factory-studio-cadv02`, 최신main3d850fc+CAD17f2a1052 통합aebce5d, 구현커밋8e47eb9, 최종인계커밋 `git log -1 --oneline`. [결과](YC_음성카드_STEP검증_CAD-V02.md)/[계약](../modules/cad-cam/음성카드_시연_설계_CAD-V02.md).
- 완료: 운영STEP30초초과재현→커널준비90/읽기30/진행/재시도·시제품기능안내, 기본호출헤이와이씨/YC+휴디별칭, 정지3D캡처후보카드→번호선택/나머지숨김/확대기존뷰어재생→전체/닫기/復元/무효화. 실제계산조건만표시, Ra가짜값없음. CAD154/프런트대상15/build/격리/포맷·Chrome정적빌드STEP재시도/32초지연·전체카드/3번진행/정지/반복/복귀/Esc/390통과.
- 다음사용자결과확인후main/push/배포/운영STEP재검증·맥북Chrome실발화리허설. 실마이크/실장비/품질전력/90초만료/DB/운영수정배포 미검증. 공유MES5파일·main보존, backend/secretary/계정변경없음. 다음ID자동착수없음.
- Node24 테스트/build·빌드정적NC화면 재현은 결과보고참조. 새검증서버5258/5259·headless Chrome 종료, dependency공유symlink제거·work/env스테이징제외. 원본첨부App.tsx는UI참고만하고실행하지않음.

## 2026-10-10 CAD-17 FANUC 검토용 완료 인계

- branch codex/cad-17, `/Users/hwang-kyoungho/projects/factory-studio-cad17`, 기준main e137f61/내부기반738433d, 구현커밋 dcf7a8f, 최종인계커밋 `git log -1 --oneline`. 사용자기종미정 검토용출력 승인. [결과](FANUC검토용_NC출력_CAD-17.md)/[계약](../modules/cad-cam/NC출력_설계_CAD-17.md).
- 완료: FANUC review profile/O1~7999/G4 P밀리초·기존 NC→출력/다시열기·재해석/원본행매핑/의미보존·품질후보재계산·UI다운로드/JSON·30초취소/무효화/도움말. 검토용100%, 실장비용아님. CAD153/프런트대상15/build/격리·Chrome 실제다운로드/재업로드/재출력/1440·390 통과. 합성 파일/캡처 docs/agent/assets/cad-17.
- 다음: 사용자 결과 확인 후 반영 또는 기종/매뉴얼확정 후 실제post/장비 검증. FANUC 실제 interpreter/H·D/실기계/실측/음성/운영/DB 미검증. main병합/push/배포 없음. 다른 작업자 사이드바 코드 보존.
- 재현: Node24에서 prototype test/frontend대상test/build, nc-review.html의 도움말/출력 순서. node_modules 공유 symlink는검증후제거; 필요시npm ci. 새 로컬Vite5257 검증종료, Chromeheadless닫음. work/env스테이징없음. 다음ID자동착수없음.

# 2026-10-12 HELP-01 다섯 시스템 도움말·운영 배포 완료

제품027505f main/origin/실서버 반영(21:58KST), 정확HEAD CI38249603910 SUCCESS: backend1010/skip1·perf1·frontend596·tools133·타입/lint/format/build/DDL왕복. 표준배포 성공·CI우회 없음·보호백업20261012-help-f14b75b 검증·회사59/회사+회원59원장/계정 전체hash보존·템플릿sv-20261009-gw1유지·APIactive/DDL0/공개원점200/5xx0·기존이지스active/office200·공개10주소200/JS해시일치·운영 도움말 렌더링/관련이동 확인. 배포 후 결과 기록 커밋은 제품과 구분한다. 상세 [구현 대조·검증](제품도움말_구현대조_HELP-01.md).

이번 작업 정적도움말·진입링크/문서경로·검사/기록30파일, 업무기능·DB/API/시드 변경 없음. HR H16~18·Flow사이드바/행편집/집계/보관복구/G14·15 현행연결·GW합성/실회사·CAD가정/실측·3D시연 구분. 격리API116·최종main 로컬frontend596·링크317/끊김0. 실제 합성 GW/Flow/근무직원신청→관리자승인/E1CAM/NC후보재생/CNC시연 확인. 실제 회사쓰기·계정/비밀번호/확장 설정 변경 없음. 실휴대폰·마이크·실가공/실설비 및 로컬WebGL불가 3D렌더링/걷기 미검증.

통합은 별도factory-studio-help-main의main에서 수행; 원래 체크아웃의 병행antigravity 브랜치·MES 미추적 도움말 보존. 검증 서버/탭 종료, 기존8000/5173 유지. 다음은 사용자 요청 후에만 P1근태정책-화면일치→실회사GW인증/권한→PWA실기기, P2Flow업무일지/규모→CAD실측/음성→3D실데이터. 재현: Node24 frontend npm test/typecheck/lint/format:check/build, db:validate, 프로젝트uv Python3.14 격리감사. pytest는 격리 *_test DB만 사용. 후속 개발 자동 착수 금지.

# 2026-10-12 ANTI-HELP-01 MES 화면 도움말 4편 작성 및 정리 완료

- **브랜치**: `antigravity/anti-help-01`
- **마지막 커밋**: `12162f3` (ANTI-HELP-01 완료 문서 갱신 커밋)
- **끝난 것**:
  - `content/help/mes/m-16.md` (M-16 불량·사유 코드)
  - `content/help/mes/m-17.md` (M-17 작업자·근무조)
  - `content/help/mes/m-19.md` (M-19 라벨 양식)
  - `content/help/mes/m-26.md` (M-26 공정 검사 기준)
  - `backend/src/fs/core/menu_catalog.json` 기준 미제공 화면(M-20, M-25, M-27, M-29) 링크 및 관련 화면 참조 정리
  - `frontend/src/portal/content-pages.test.tsx:50`의 `count("mes/m-")` 기댓값 15 → 19 갱신
  - HR 3편(H-16, H-17, H-18)은 main 커밋 `f14b75b`에서 이미 완료되어 있어 중복 작성하지 않고 ANTI-HELP-01은 종료
- **검증**:
  - `npx --prefix frontend vitest run src/portal/content-pages.test.tsx` (18/18 통과)
  - `npm --prefix frontend test -- src/mes/masters.test.tsx` (5/5 통과)
  - `npm --prefix frontend run build` (통과)
  - Playwright Chromium 브라우저에서 `/mes/codes`, `/mes/workers`, `/mes/labels`, `/mes/inspection-items`의 "? 도움말" 클릭 시 4개 문서 정상 로드 및 "이 화면 열기 →" 링크 동작 검증 완료
- **다음 할 일**: 사용자 확인 후 `antigravity/anti-help-01` 브랜치를 main에 병합 검토. 후속 W2a-1b2-rest 작업 착수는 사용자 지시 대기.
- **주의점**: 다른 antigravity 세션과의 충돌 방지를 위해 임의로 브랜치를 checkout하지 않고 `antigravity/anti-help-01` 브랜치에 그대로 두고 대기한다.
- **재현 명령**:
  - `npm --prefix frontend test -- src/portal/content-pages.test.tsx`
  - `npm --prefix frontend run build`

# 2026-10-12 W2a-1b2-rest MES 공정 경로(M-14)·BOM(M-15) R-1~R-5 전체 완료

- 브랜치: `antigravity/w2a-1b2-rest`
- 마지막 커밋: `d64a95f` (style(mes): format Routes.tsx and versions.test.tsx with prettier)
- 진행 상태: **R-1 ~ R-5 전체 완료 — 사용자 최종 확인 및 main 병합 대기**
- 작업 내용:
  - R-1: `mes.route_step` 컬럼 확장(표준 CT, 준비 분, 외주 여부, 외주처), `schema.RouteSteps` 객체 목록 변경, `validate_steps` 검증 및 정규화, 백엔드 테스트 통과.
  - R-2: `Routes.tsx` 단계별 4개 속성 편집 폼 및 목록 컬럼 추가, 외주 체크 해제 시 외주처 코드 비움/감춤, 빈 칸 null 정규화, `versions.test.tsx` 갱신 및 신규 속성 추가 테스트(9 passed), 전체 프론트엔드 597테스트/typecheck/lint/build 통과, Playwright 브라우저 실동작 검증 완료.
  - R-3: `bom_line.issue_process_id` 추가 (`repository.LINE` 컬럼, `schema.BomLineIn`, `service.validate_lines`에서 `mes.process` 검증). `PUT /boms/{id}/lines`를 `service.set_bom_lines`로 연결하여 `material_item_id` 키 기반 맞춤 저장(UPDATE/INSERT/DELETE) 구현. 기존 줄 UPDATE로 `bom_line.id` 보존 및 하위 대체 자재 유지. 삭제 대상에 대체 자재가 딸려 있으면 409 `REFERENCED_BY_OTHERS` 반환.
  - R-4: `mes.bom_substitute` 조회·편집 API (`GET /boms/{id}/lines/{lineId}/substitutes`, `PUT /boms/{id}/lines/{lineId}/substitutes`). 초안(`draft`)에서만 편집 가능 (`VERSION_LOCKED` 409). 완제품 자신/원래 구성 자재와 동일 품목/중복 등록/미존재 품목 차단. BOM 개정(`revise`) 시 새 버전의 구성 자재 라인 아래로 대체 자재 자동 복제.
  - BOM-FIX: 자재 순서 교체 시 `UK(workspace_id, generation_id, bom_version_id, line_no)` 위반 해결. `reconcile_bom_lines`에서 살아남는 줄의 `line_no`를 1단계에서 `-idx` 임시 음수로 일괄 업데이트 후 2단계에서 최종 순서 번호로 업데이트하여 충돌 방지. 자재 순서 교체 시 `bom_line.id` 및 하위 대체 자재 보존 테스트(`test_bom_lines_reordering_preserves_line_ids_and_substitutes`) 추가 및 34 passed 통과.
  - R-5: `Boms.tsx` 화면 보강:
    - 구성 자재 등록/수정 시 투입 공정(`issueProcessId`) 선택 드롭다운 (비우면 `null` 전송, "공정 지정 안 함").
    - 구성 자재 행별 대체 자재 펼치기/접기 토글 및 대체 자재 추가/삭제 기능 연동 (`PUT /boms/{id}/lines/{lineId}/substitutes`, `ratio` string 정규화).
    - 자재 순서 변경(↑/↓) 및 "순서 저장" 버튼.
    - 대체 자재가 딸린 구성 자재 삭제 시도 시 409 `REFERENCED_BY_OTHERS` 응답을 감지하여 해당 행 옆에 인라인 에러 안내(`대체 자재를 먼저 지우세요`) 표시.
    - 게시·폐기 버전에서는 대체 자재 추가/삭제/관리 버튼 비활성화/숨김.
    - 390px 반응형 뷰포트 지원.
  - 검증:
    - 백엔드: `backend/tests/test_mes_route_bom.py` 34 passed, 전체 MES 138 passed (전체 통과), `ruff check`/`ruff format` 통과.
    - 프론트엔드: `npm run typecheck`, `npm run lint`, `npm run build` 통과, `versions.test.tsx` 13 passed, 프론트엔드 전체 75파일 601 passed.
    - 브라우저 E2E 실동작 검증(Playwright): 포털 접속 -> 게스트 로그인 -> `/mes/boms` -> 신규 BOM 생성 -> 투입 공정 지정 자재 2건 추가 -> 대체 자재 추가 -> 순서 교체 및 저장(BOM-FIX 확인) -> 페이지 새로고침 후 순서 및 대체 자재 유지 확인 -> 대체 자재 있는 줄 삭제 시도 시 409 인라인 안내 표시 확인 -> 대체 자재 삭제 후 줄 삭제 -> 게시(게시 상태 잠금 전환) -> 390px 뷰포트 확인까지 전체 통과 확인.
- 주의: main 브랜치 병합은 수행하지 않고 사용자 확인을 기다린다.

---

# 2026-10-12 HELP-01 제품 도움말 구현 대조·로컬 검증 완료

사용자 다섯 시스템 문서화·main/origin·기존 실서버 배포 승인. 기준main3306777, 브랜치codex/product-help-20261012, 별도factory-studio-help 체크아웃. 제품 정적 도움말과 진입 링크만 변경; 공유main의 진행 중 MES 변경은 보존/제외. HR H-16~18 신설, Flow 행편집·부모집계·보관복구·권한·/work-os 이동 보정, GW 전체 합성 업무 안내, CAD 가정/실측·3D 시연 구분과 README 이력 표시. 상세 [구현 대조](제품도움말_구현대조_HELP-01.md).

로컬 검증: frontend596/75파일 전체 통과, 타입/lint/format/build 및 링크 보정 후 관련36통과. 프로젝트uv Python3.14 격리감사193표471FK오류0. 격리 *_help_api_test에서 근무/계정/Flow/GW116통과, *_help_browser_test+8046/5246은 실제API 합성UI 전용. 기존8000/5173·실제 회사/계정/비밀번호/브라우저확장 변경 없음. 다음: main/push→정확HEAD CI→기존백업/배포→운영검증. 아직 배포 완료 아님. 후속고도화 자동착수 금지.

# FLOW-03 행 편집·접힘 UX 운영 배포 완료

브랜치 main/origin main. FLOW-03 행 편집·접힘 UX 보정 운영 배포 완료(2026-10-11 18:41 KST): 제품2c30b42 main/origin/실서버 반영. 접힌 그룹68px 한 줄·업무/하위 업무 행 우측 삭제/복구·상세 편집 제목/설명2항목·담당자/상태/중요도/일정/진행률 행 편집. CI38128137226 SUCCESS(backend1010/skip1·perf1·frontend596·tools133), 실제 로컬 저장/새로고침/삭제/복구/390px 검증. 기존 Flow12원장전체hash보존·보호 백업·APIactive/DDL0/공개200/최근5xx0·공개JS/CSS SHA동일. 운영 로그인 UI는 기존 세션 만료로 미검증. FLOW-02b 후속.

보호 백업: /srv/factory-studio/backups/20261011-flow-row-2c30b42. 재현: frontend Node24 npm test / typecheck / lint / build / format:check. 상세 [행 편집 검증](Factory_Flow_행편집_검증_FLOW-03.md). 최종 문서 기록 커밋은 운영 제품과 구분, 다음 ID 자동 착수 없음.

# FLOW-03 행 편집·접힘 UX 보정 (2026-10-11)

브랜치 main. FLOW-03 행 편집・接힘 UX 보정 구현/로컬 검증 완료(2026-10-11): 접힌 그룹68px 한 줄·하위 업무 행 우측 삭제/복구·상세 편집은 제목/설명·참고 링크2항목·담당자/상태/중요도/일정/진행률 행 편집. 실제 로컬 합성 보드 저장/새로고침/삭제/복구·부모 집계 확인, 기존 업무 보존. DB/API 변경 없음. main push·정확HEAD CI·운영 배포 진행 예정. FLOW-02b 후속.

검증 명령: frontend에서 Node24 PATH로 npm run typecheck / npm run lint / npm test / npm run build / npm run format:check. 운영 배포는 기존 tools/deploy.sh의 정확 HEAD CI 성공 확인 후 보호 백업을 먼저 한다. 실제 계정/비밀번호/확장 설정 변경 없음. 운영 로그인 UI는 세션 만료로 미검증 상태를 유지한다. 상세: [행 편집 검증](Factory_Flow_행편집_검증_FLOW-03.md).

# 2026-10-11 FLOW-03 인라인 생성·작은 카드 운영 배포 완료

제품 b255c6c 로컬main/origin/main/실서버 반영(17:55 KST). 정확HEAD CI38124898787 SUCCESS: backend1010/skip1·perf1·frontend592/75파일·tools133·타입/lint/format/build/DDL왕복. 기존 Flow12원장 전체행 건수/hash보존·보호 백업20261011-flow-inline-b255c6c·APIactive·DDL0·원점/공개/Flow200·최근5xx0·공개JS/CSS의 로컬/서버SHA동일. 로컬 실제 합성 검증 보드에서 새 업무/하위업무 인라인 생성·이름 저장·새로고침 유지·새 그룹 이름 편집 확인 후 검증 보드 보관. 운영 기존 브라우저 탭은 세션 만료/401로 로그인된 UI 확인 미실행, 재로그인 필요. 운영 업무 쓰기·계정 생성·확장 변경 없음. 상세 docs/agent/Factory_Flow_인라인생성_실제품검증_FLOW-03.md. 최종 문서 기록 커밋은 제품과 구분, FLOW-02b 자동 착수 없음.

# 2026-10-11 FLOW-03 실제 Figma 인라인 생성 보정

열린 Figma 직접 조작/카드 치수 측정 후 사용자 승인. 새 업무/하위 업무 모달 제거·서버 생성 직후 부모 아래 인라인 이름 편집·새 그룹 자동 이름 편집·중복 전송 잠금·실패 입력 유지/IME 처리. 3카드96×72/진행률160×72. 로컬 별도 합성 보드 저장/새로고침/그룹명 검증 및 보관·기존 보드 복귀. DB/API 변경 없음. 정확HEAD CI와 운영 배포 예정. 상세 docs/agent/Factory_Flow_인라인생성_실제품검증_FLOW-03.md. 다음: 검증 완료→main push→CI 성공→보호 백업/표준 배포→공개 UI/원장 보존 확인. FLOW-02b 자동 착수 없음.

# 2026-10-11 FLOW-03 승인 UI 제품 보정·운영 배포 완료

승인 시제품과 제품 daa1905의 실제 UI 차이를 확인하고 단독 셸·breadcrumb/공유·설정 메뉴·표 헤더·상태 배지·아이콘·간격·체크박스/하위업무 선을 보정했다. 회사 등록/API/DB 변경 없음. 회사 미등록 admin과 게스트의 공통 메뉴 유지 브라우저 검증 포함. 제품27a3db0 로컬main·origin/main·실서버 반영(10:53 KST).

정확HEAD CI38102155660 SUCCESS(backend1010/skip1·perf1·frontend590/75파일·tools133·타입/lint/format/build/DDL왕복). 보호된 서버 백업20261011-flow-ui-27a3db0 검증·Flow12원장 건수/hash보존·APIactive·DDL0·공개/원점/메뉴/CSS200·미로그인API401·최근5xx0. 운영 빌드+합성응답으로 화면 캡처·진입/구주소/컬럼drawer/Escape/공유/390px 확인. 실제 운영 쓰기·계정 생성·확장 설정 변경 없음. 상세 docs/agent/Factory_Flow_승인UI_제품보정_배포검증_FLOW-03.md. 다음 FLOW-02b는 별도 범위, 자동 착수 없음. 최종 문서 커밋은 운영 제품과 구분.

# 2026-10-11 FLOW-03 UI 승인 이미지 차이 보정

사용자 승인 시제품과 실제 제품의 표 헤더·native 상태 선택·상시 설정·간격 차이를 확인해 수정. Flow 중복 플랫폼 헤더 제거, breadcrumb/공유·제목 즐겨찾기, 내보드+ 생성/설정 메뉴, SVG 탭·검색·필터·내업무, 상태 배지/키보드 select 유지, 날짜/프로필/체크박스·그룹 스트립/하위업무 선·부가 메뉴 정리. 회사 등록·보드 설정/권한·기존 업무 CRUD 유지. DB/API 변경 없음.

로컬 frontend590/75파일·타입/전체lint/build/범위format·실제품 브라우저 합성7업무/3그룹·39%·런처/구주소/컬럼drawer/Escape/공유 열기닫기·390px overflow0 통과. 출력 Factory_Flow_FLOW04_UI.png는 제품을 합성 데이터로 실행한 캡처이며 운영 데이터가 아니다. main push/정확HEAD CI/운영 배포 진행 예정. 운영 실제 회사/계정 생성 및 확장 설정 변경 없음.

# FLOW-03·HR-USERS-02 운영 배포 완료

2026-10-11 10:09 KST 제품 daa1905를 로컬 main·origin/main·실서버에 반영했다. Figma 보드 UI·자유 컬럼6종/셀·그룹 복제/보관/삭제/복구·총 관리자 회사/첫 회사 관리자 웹 등록 포함.

정확 HEAD CI38099879569 SUCCESS: backend1010/skip1·perf1·frontend590/75파일·tools133·타입/lint/build/DDL 왕복 통과. 로컬/운영 백업 후 flow_board_custom 적용, 기존10원장 건수/hash 보존. 운영 백업 /srv/factory-studio/backups/20261011-flow03 검증. tools/deploy.sh 성공·CI 우회 없음·서버 APIactive·DDL0·공개/원점200·최근2분5xx0. 보드/내업무/사용자관리 URL200, 미로그인 세션/관리역량/Flow API401.

실제193표2102열471FK·목표381표925FK 및 Excel/ERD 동기화. 시드 유지, 실제 운영 회사/계정/비밀번호 생성 없음. 앱 런처→Factory Flow; admin→사용자 관리→회사 등록. FLOW-02b 업무일지 트리/가상화 후속. 확장 설정 유지. 최종 기록 커밋은 문서만이며 운영 제품 daa1905와 구분한다.

# 2026-10-11 GW-FLOW-03 배포 진행

- 현재 작업 디렉터리 /Users/hwang-kyoungho/projects/factory-studio, branch main (사용자 main 반영·push·배포 승인). 이전 WIP 9f0baa8.
- 구현·검증은 docs/modules/flow/Factory_Flow_간결보드_FLOW-03.md 최신 기록. 새 head flow_board_custom, 로컬 적용/원장10표보존 완료.
- 다음: exact HEAD origin/main push → FS-009 CI 통과 → 서버 백업/기존 tools/deploy.sh → 공개/DDL/원장 hash/5xx 확인 → 배포 기록 커밋/push.
- 운영 실제 회사·계정·비밀번호 자동 생성 금지. 사용자 admin → 사용자 관리 → 회사 등록에서 입력.
- 재현: uv run --project backend --env-file .env python tools/verify_ddl_matches_schema.py; npm --prefix frontend run build/test; uv run --project backend python -m unittest discover -s tools -p 'test_*.py'. 테스트는 별도 *_test DB를 지정한다.

# 2026-10-11 진행 중 인계

- branch: codex/gw-flow-simple-design. 사용자 전체 구현/main/push/배포 승인.
- FLOW-03 자유 컬럼/셀+그룹 상태/복제, HR-USERS-02 웹 회사 등록, Figma UI 구현 중.
- 테스트 DB DDL 일치, 프런트 집중 8 통과. 전체 기능/CI 검증과 실제 배포 미완료.
- 다음: 테스트 수정/통과, Excel/ERD 동기화, 로컬 main 반영/CI/백업/배포.
- 실제 계정 비밀번호 생성 금지, 예제/운영 원장 초기화 금지.

## 2026-10-10 FLOW-02a 운영 배포 완료·로컬 admin 클릭 비교

Factory Flow 앱 런처 카드→/work-os/boards·/work-os/my-tasks 독립 진입, flow API/10표 이관, 구GW URL·즐겨찾기·멱등 요청 보존, 새 백자/먹색/쪽빛 UI를 운영 제품31623b0으로 배포 완료(21:03 KST). 정확한 HEAD CI38048961871 success: backend1006/skip1·perf1·frontend588/75파일·tools133 및 타입/lint/빌드/DDL왕복·격리 통과. 초기 모듈 개수 상수 실패는 MODULE_KEYS 기준 보정 후 전체 CI 재통과.

서버 백업20261010-flow-31623b0(DB/프런트·비공개/commit/10표digest) 목록·압축 검증 완료. 초기 SSHstdin을 Docker가 소비한 백업 준비를 입력/dev/null 지정으로 재실행·완전 검증 후 배포. tools/deploy.sh exit0/CI우회0, 서버git31623b0/alembicflow_split/APIactive·10표행수/hash보존·DDL0·공개/원점/JS/CSS200·최근5xx0·구/신API미로그인401. 템플릿 시드 버전 동일로 유지, 사용자/비밀번호/DB초기화 없음. 제품 스키마0.24.1·191표2074열464FK. 날짜별 업무일지8표/가상화 FLOW-02b는 후속 미구현.

추가 로컬 admin 조사: 기존Chrome탭 링크 클릭·Enter 이동 차단 재현/직접URL 관리자 정상. busy=false/disabled0/DOM가림·inert0. 동일 프로필·admin세션 새탭 사용자관리/런처/MES 이동 정상 및 사용자 직접 “새 탭은 정상 동작” 확인, 정상 비교탭 유지. 정상탭에도 확장오류가 있어 403과 클릭 차단 인과 단정 금지. 기존탭 입력 차단 원인미확정, 계정·서버권한/확장설정 변경 없음. 로컬8000/5173유지. 실제운영계정쓰기/휴대폰설치 미검증.

상세: [배포 검증](Factory_Flow_독립시스템_배포검증_FLOW-02a.md). 후속 기록은 문서만이며 운영 제품31623b0과 구분. 다음 FLOW-02b 별도 범위 확인.

재현: main 정확한 HEAD CI success→tools/deploy.sh 사전점검/실행, gh run view38048961871. 백업은 서버에만 유지하고 Git/outputs로 복사하지 않는다. 브랜치 codex/gw-flow-deploy-report의 후속 기록을 main ff병합/push; 마지막 커밋 git log -1. 제품 배포31623b0은 기록 커밋과 구분.

## 2026-10-10 FLOW-02a 독립 진입·보드 이관 인계

사용자 앱 런처 Factory Flow/독립 보드 분리 진행 및 기존 배포 승인 유지. 신규 참조 폴더의 src/App.tsx/index.css 읽기 분석, 백자#F7F7F6/먹색#1A1C1E/쪽빛#1F2D3D/한지#E8E8E6/청자#2D4442/프로필#E2E3E5·4% 그림자 적용. 참조 파일은 변경하지 않았다.

런처 열 번째 카드 Factory Flow → /work-os/boards, /work-os/my-tasks, 내 공간/메뉴/도움말/카탈로그 연결. 독립 UI에 기존 네 보기/권한/댓글 유지·아바타/진행바 추가. 기존 /gw/projects,/gw/my-tasks query/hash보존 redirect. API 패키지 fs.flow·/api/v1/flow, 구APIalias는 같은 원장 사용. gw.work_*10표 SET SCHEMA→flow, 기존ID/시퀀스/FK/댓글/감사이력 보존. Flow모듈 별도등록/off, 새회사/템플릿/복사정리 목록/후기허용 확장. 메뉴즐겨찾기 순서/중복보존 전환. 기존 gw.projects.* receipt namespace 유지로 재시도 중복0, 데이터엔티티는flow. 날짜별 업무일지8표/가상화 고도화는 이번 요청의 진입·분리와 구분하며 후속 FLOW-02b 미구현.

schema0.24.1/headflow_split·191표2074컬럼464FK, 목표379표918FK·Excel/ERD 동기화. 전용DB DDL0·프로젝트9검사(구API멱등/off독립/실제보드·댓글/10표역이관digest/즐겨찾기왕복 포함), 기존관련26검사, frontend588/타입/lint/format/build, tools133/격리0 통과. 초기 migration SQL 문법·신규테스트 operation명 오류 보정 후 재통과. 로컬 DB 백업 pg_restore검증 후 migration 적용·10표행수/digest보존/DDL0. Chrome 실제 제품UI+합성응답으로 런처진입/oldURL선택유지/색상계산값/390px가로넘침0 확인; 운영 실제계정쓰기 검증은 아니다. 사용자8000/5173·실제계정/비밀번호/확장 설정 유지. main push/CI/운영배포는 후속 확인 중이며 완료 후 이 문서와 인계 갱신.

다음: 정확한main제품커밋 CI success 확인→실서버DB/파일백업→API쓰기중지→기존배포스크립트→10표digest/DDL/publicassets검증. 데이터삭제/초기화 금지. 로컬8000/5173유지.

## 2026-10-10 FLOW-02a 독립 진입·보드 이관 WIP

사용자 앱 런처 Factory Flow·/work-os·기존 보드 분리 구현 및 배포 승인. codex/gw-flow-entry에서 작업 중. Flow 패키지/API와10표 SET SCHEMA·메뉴/즐겨찾기 이전 구현, 검증 진행 중. 날짜별 일지8표/FLOW-02b는 미구현으로 구분한다. 첫 마이그레이션 SQL 문법 검사 실패를 수정 중이며 운영/로컬 실DB에는 아직 미적용. 기존8000/5173 유지. 다음: 전용 테스트DB·역이관 보존/권한/alias·UI검증 후 main push, CI 통과 뒤 백업·쓰기 중지·운영배포. 제품 완료로 표시하지 않는다.

## 2026-10-10 GW-PROJECT·HR 운영 배포 완료

사용자 실서버 배포 요청으로 main/origin/main의 제품 커밋 `98402d978428a60bd070bda910f740fca234f765`를 기존 `tools/deploy.sh`로 실제 배포했다. 기존 운영 `31af096` → `98402d9`, DB `w0_fav_menu_shape` → `gw_projects`. GW 프로젝트 보드·내 업무, 회사 근무/PWA·관리자 사용자 관리 등 기존 main 변경 포함. Factory Flow 독립 Work OS/업무일지는 설계·검토용 시제품만이며 제품 구현/DB 이관은 아직 승인 대기다.

CI 차단 Ruff migration 서식과 HR 사용자 테스트 Prettier 서식만 보정했다(`71d140a`, `98402d9`). migration AST 비교로 실행 의미/SQL 불변 확인. 최종 CI [38044267825](https://github.com/go8105/factory-studio/actions/runs/38044267825) success: backend1004 passed/1 skipped, 성능1 passed, frontend75파일588검사, 타입/lint/서식/빌드, DB upgrade·downgrade 왕복/DDL·격리·설계 검증 및 도구 검사 통과.

운영 서버 전용 백업 `/srv/factory-studio/backups/20261010-projects-71d140a`에 DB dump/프런트·비공개 자산/이전 커밋을 저장, pg_restore 목록 및 gzip 무결성 검사 완료. 시드 버전 동일 `sv-20261009-gw1`로 기존 템플릿 유지. API active, 공개·원점200, 실제 운영 DDL오류0, 재시작 후 최근2분5xx0. 공개 `/gw/projects`, `/gw/my-tasks`, `/hr/users` 및 JS/CSS200; 미로그인 세션·프로젝트 회사 API401. Python urllib 기본 요청은 Cloudflare403이었으나 curl 공개/원점 검증은 정상; 앱500과 구분한다. 실제 회사 로그인·쓰기/휴대폰 설치는 미검증, 실제 계정/비밀번호/회사 생성 없음. 기존 로컬8000/5173·확장 설정 유지.

상세: [배포 보고서](GW_프로젝트_main_배포검증.md). 이 후속 기록 커밋은 문서만이며 운영 제품 커밋98402d9와 구분한다. 다음: FLOW-01 전체 설계 확인 후 FLOW-02 개발.

재현: main에서 `tools/deploy.sh`(정확한 HEAD CI success 필요), `gh run view 38044267825`, 공개 `https://eip.hugh-d.com`. 브랜치 codex/gw-deploy-report → main으로 문서 보고서만 병합/push. DB 초기화·실제 사용자 생성·비밀번호 설정은 하지 않는다. 백업은 서버에만 보관하고 Git/outputs로 복사하지 않는다.

## 2026-10-10 FLOW-01 독립 Work OS·업무일지 전체 설계

사용자가 GW 프로젝트 보드를 독립 시스템으로 분리·제공 UI 코드 이식·업무일지 고도화 요청 및 이어서 진행 지시. 방향 승인과 신규 전체 설계 확인을 구별한다. Factory Flow(Work OS·프로젝트 관리·협업), module/schema/package flow, 프런트 /work-os, API /api/v1/flow. 기존 포털 /flow 맵 유지. GW10표 SET SCHEMA로ID/S/댓글/이력 보존, 새 일지8표/총18표191컬럼 설계. 기존 제약42/FK31/상태 보존. 실제 schema0.24.0/headgw_projects·191표464FK 유지.

새 공통 설계: docs/modules/flow/README.md 및 Factory_Flow_독립시스템_업무일지_FLOW-01.md·flow-design.json·flow-design.mmd·별도설계Excel·ui-preview.html. 본부/실→팀기간→팀원→날짜별일지, 제출본회사공유/임시본본인만/지정검토자·자가검토금지/immutable revision. HR원천interface읽기·계정명자동연결금지/수동조직fallback. 구GW주소/메뉴즐겨찾기보존,계정/스키마독립모듈등록·멱등이행·세대정리·성능/가상화·검증명세 포함. 첨부는FLOW-03후속,첫공개는독립앱+UI+일지.

검증: 참조React코드분석(캘린더/간트EmptyView,고정명단/child boolean,일부무동작버튼),설계18표191컬럼/관계·앵커/문서링크/XLSX3시트통과. Spreadsheet artifact-tool 생성·3시트렌더확인. UI시제품JS문법/브라우저검색·일지트리·우측패널·가상제출·390px확인. 모두합성예제/탭내시제품으로 실제API저장 없음. 제품pytest/vitest/실제DDL/migration/부하/배포 미실행(제품변경없음). 사용자원본폴더/실제회사/계정/비밀번호/확장설정 변경없음. 기존5173/8000유지,검토8766서버는종료.

브랜치 codex/gw-flow-design, 설계 문서만 main 반영 대상. 사용자 전체 설계 확인 전 FLOW-02 제품구현/DB변경 시작금지(AGENTS §2 및 설계완료 승인기준). 다음: 설계확인후 새codex/gw-flow-implementation에서원장독립이관·UI·일지동일범위구현→검증→로컬백업적용→mainpush. 전체설계후데이터책임/권한변경이커서기존GW-PROJECT승인으로대체하지않는다. 최종커밋은git log -1. 검토화면/Excel은사용자 outputs와저장소모듈에보존하여work임시파일없이재개가능.

## 2026-10-10 GW-PROJECT 첫 공개 구현 완료

회사 공동 보드·그룹·1단계 하위 업무·복수 담당자·상태/중요도/기간/진행률·표/칸반/기간 캘린더/기본 간트·내 업무·댓글/변경 이력·보드 즐겨찾기/보기 설정 구현. GW G-14/G-15와 도움말 추가. 회사 회원 기본 VIEWER, 지정 EDITOR/OWNER만 업무 수정, 플랫폼 ADMIN/HR ADMIN 자동 권한 없음. 멤버십 fresh authorize·회사 격리·version409·멱등 재시도·마지막 OWNER 보호·자식 집계·보관 배치 복구 검증. 부모 기준 페이지 조회가 자식을 함께 반환한다.

schema0.24.0/headgw_projects: 실제191표2074열464FK, 목표379표918FK. migration/메타데이터/DB Excel/실제·목표 ERD 동시 반영. 기존 COMPANY에 GW 활성 세대 등록, 합성 체험 데이터 복사 없음. 실제 로컬 DB는 pg_dump 백업 후 적용, 카탈로그 대조0오류. 전용 테스트 DB에서 downgrade/upgrade 왕복 및 대조0오류.

검증: backend 전체 병렬1001통과·1skip·성능검사1실패(병렬 부하에서5.817초), 해당 성능검사 단독 재측정 통과. 최종 프로젝트 API7통과. frontend75파일588검사·lint·typecheck·build 통과, 도구133통과. 합성 전용 브라우저에서 네 보기·상태 저장/재조회 확인. 실제 회사/계정/비밀번호 및 확장 설정 변경 없음. 사용자 기존8000/5173 서버 유지. 운영 배포는 미실행. main 병합 및 origin/main push 대상이며 최종 커밋은 git log -1로 확인.

한계: 파일/자유 열/외부 공유/자동화/실시간 동시 편집/오프라인/의존 일정은 후속. 내 업무 최대1000건, 보드는 모든 부모 페이지를 읽어 네 보기에 표시하며 대규모 화면 렌더링 성능은 별도 부하 검증 전.

# GW-PROJECT-01 인계 — 2026-10-10

브랜치 codex/gw-project-design → main. 설계 문서만 반영하며 최종 커밋은 git log -1로 확인. 프로젝트 보드 신규 범위는 사용자 전체 설계 확인 전. 회사 공유·기본 VIEWER/지정 EDITOR·네 보기·10개 신규 테이블 후보. 기존 GW 체험 actor/seed_ready와 회사 프로젝트 경로를 분리한다. 실제 데이터/비밀번호 복사 금지. 상세 DB/API/권한 명세와 설계 Excel/ERD 후 개발 가능. HTML 시안 JS 문법 검사만 완료, 브라우저 file URL 정책 차단으로 렌더링 미검증. 기존 5173/8000 서버·확장 설정 유지.

## 2026-10-10 LOCAL-AUDIT 진입 오류·메뉴 클릭 전체 점검

사용자 기존 Chrome 탭에서 메뉴 클릭이 반응하지 않는 현상 재현. 서버는 점검 시작 시 중지되어 있어 공통 기동기로 DB 확인 후 backend/frontend 재실행, 현재 localhost:5173/8000 유지. 실제 Chrome의 기존 admin 세션으로 새 탭에서 MES/QMS/SPC/WMS/FEMS/BEMS/ERP/GW/HR 9개 대시보드 클릭·데이터 로딩·오류 알림 없음 확인. 내 공간·즐겨찾기 편집 창 열기/취소·사용자 관리 회사 조회·CAD iframe 로딩·3D 공장·전체 흐름·도움말도 확인. 콘솔 permission error는 Monica extension ofpnmcalabcbjgholdjcjblkibolbppb의 /writing/get_template_list, EventEmitter/ObjectMultiplex 경고는 MetaMask extension nkbihfbeogaeaoehlefnkodbefgpgknn에서 발생. 해당 확장 오류는 정상 새 탭에서도 발생하므로 클릭 차단 원인이라고 단정하지 않음.

기존 탭은 새로고침/문서 재진입/DevTools 종료 후에도 클릭 차단 재현, JS debugger는 Not paused, 앱 busy=false/내비게이션 버튼 활성/앱 dialog·고정 덮개 없음. 기존 탭의 정확한 차단 원인은 미확정. 사용자는 확장 설정 유지 선택; 확장/쿠키/계정/비밀번호 변경 없음. 정상 동작하는 새 Chrome 탭을 사용자 관리에 남김. 앱 코드 변경 없음·DB 스키마 변경 없음. 새 게스트 검증은 기존 로컬 게스트 상한 때문에 RATE_LIMITED였으며 데이터를 지우거나 상한을 변경하지 않음. 실제 증거는 사용자-facing outputs/로컬_메뉴_동작확인.png. 다음: 새 탭에서 사용, 기존 탭의 환경 문제는 추가 재현 정보 또는 사용자 별도 브라우저 비교가 필요. 점검 결과 문서만 main push.

- 최종 커밋은 git log -1. 점검용 서버 8000/5173을 현재 유지했다. IntelliJ에서 재기동하려면 기존 서버를 먼저 종료해야 하며 사용자 실행 서버와 구별할 것. 정상 새 탭과 기존 문제 탭을 혼동하지 말 것. 이전 LOCAL-START의 API500과 이번 extension403/클릭 차단은 별개다.

## 2026-10-10 LOCAL-START 로컬 500 및 IntelliJ 주소 통일

실제 로컬 DB/Colima가 중지된 상태에서 DB 연결 거부 재현. 기존 IntelliJ 전체 구성은 DB 기동 없이 front/backend만 실행했고 Compose 플러그인도 없었다. 공통 start_local.py가 기존 Colima 프로필/DB를 기동하고 실제 DB 연결 확인 후 서버를 실행한다. 동시 DB 준비 파일 잠금, Compose standalone fallback, 기존 데이터/볼륨 보존. 공유 .run Local - All 추가와 PC 기존 .idea 명령 보정. backend 표시/접속은 localhost:8000, front는 localhost:5173; Vite DNS verbatim 고정 및 프록시 IPv4 지정으로 표시 변동/IPv6 API 연결 실패 방지.

검증: 중지된 Colima/DB 실제 복구, backend/frontend 동시 기동, localhost front HTTP200, 만료/위조 쿠키 API401(500 없음), 기존 admin의 current_session 서비스 조회 성공. schema head hr_time_check 유지, 실제 계정/비밀번호 변경 없음. frontend584·타입/lint/build·기동스크립트 Ruff 통과. 사용자 main push 승인 유지. 검증용 앱 서버는 종료하고 DB 유지; IntelliJ Local - All로 실행. 운영 배포 없음.

- 브랜치 codex/local-startup → main fast-forward/push, 최종 커밋은 git log -1. 재현: uv run --project backend --env-file .env python tools/start_local.py backend 또는 frontend. 공유 .run 구성은 IntelliJ 프로젝트를 다시 로드하면 표시된다. 사용자 PC의 기존 .idea 구성도 보정했으며 .idea 자체는 Git 제외다.

## 2026-10-10 W1-HR-USERS 관리자 사용자 관리 완료

사용자 요청으로 터미널 최초 비밀번호 설정을 관리자 웹 화면으로 대체했다. 기존 활성 플랫폼 admin 로그인 → /hr/users → hugh-D Company 선택 → 각 계정 관리 → 비밀번호 설정·사용 재개. 새 사용자 아이디·비밀번호·사원 코드·이름·근무 권한·올해 연차를 함께 등록한다. 플랫폼 ADMIN은 회사 목록, 회사 ADMIN은 자기 회사만 관리하며 STAFF/게스트는 접근 불가. 비밀번호는 반환하지 않고 변경 시 기존 세션 종료. 자기 계정 변경·마지막 회사 관리자 제거·다중 회사 계정 변경 차단, 멱등 요청/동시성/감사 기록에서 비밀번호 제외. 로컬 두 예제 계정은 사용자 설정 전까지 비활성 유지.

검증: 관련 backend29개 및 새 사용자 API4개 재검증, frontend전체584개/새 화면4개 재검증, 타입·lint·format·build 통과. Chrome 별도 합성 테스트 DB에서 실제 회사 조회/계정 관리 폼 표시 확인(브라우저 비밀번호 제출은 사용자에게 맡김). 스키마 변경 없음: schema0.23.3/headhr_time_check·181표433FK. 사용자 main push 승인 유지; 운영 배포/실제 휴대폰 설치 미실행. 다음: 기존 admin에서 두 계정 비밀번호 설정 후 사용. 회사 정책 편집·다음 연도 연차 자동 부여는 후속.

- 브랜치 codex/hr-user-management → main fast-forward/push 반영, 마지막 커밋은 git log -1 참조. 이전 터미널 활성화 안내는 이번 사용자 요청으로 대체됨. 실제 비밀번호를 요청/기록하지 말 것. 재현: frontend에서 npm exec vitest -- run src/hr/Users.test.tsx, backend TEST_DATABASE_URL에 독립 테스트 DB 지정 후 pytest backend/tests/test_hr_users.py.

## 2026-10-10 W1-HR-TIME 구현 완료 / 최초 비밀번호 사용자 입력 대기

- 브랜치 codex/hr-time-company, WIP cd46db4 이후 최종 커밋은 git log -1. 사용자 main 즉시 push 지시 유지, 로컬 main·origin/main 반영. 운영 배포는 미실행.
- [검증/시작안내](회사근무_구현검증_W1-HR-TIME.md). 회사 멤버십+HR 사원 연결, 실제 원장은 기존 개인 AUTO 근태와 분리. 게스트 실제API403, 합성 체험만 허용. schema0.23.3/headhr_time_check. 회사 코드/정책/직원 2명은 로컬 DB에 생성됨. 계정 hugh-admin/hugh-staff는 disabled, 사용자 터미널 getpass 활성화 대기. 비밀번호를 요청하거나 문서에 기록하지 말 것.
- 활성화: 저장소에서 `uv run --project backend --env-file .env python tools/create_work_company.py --activate`. 예제회사 두 비활성 계정만 최초 활성화, 기존 활성 계정 비밀번호는 덮어쓰지 않음.
- 검증: 회사API9+활성화1, 도구133, 프런트580, 스키마9, DDL왕복오류0·Chrome 별도 테스트DB 실제직원 출퇴근/관리자 기록정정. 최초 전체backend991통과/1skip/DDL1실패는 후속 CHECK 재생성으로 고쳐 해당 스키마9 검사 재통과. 기존 적용 migration SQL 변경 없음.
- 다음: 사용자가 PC 터미널 비밀번호 입력→두 계정 실제 사용 확인. 운영 반영을 진행할 경우 현재 head CI 확인/정식 deploy.sh·서버 백업·운영 회사/계정 별도 준비 및 사용자 터미널 비밀번호 설정·HTTPS Android/iPhone 실제 설치검증. 로컬DB 계정 데이터를 운영에 복제하지 않음. 추가 직원 초대/다음 연도 연차 부여/정책 설정 UI는 별도 후속.
- 테스트 DB factory_studio_hr_time_test만 검증 데이터 초기화에 사용. 사용자 로컬 factory_studio는 백업 후 새 revision만 적용, 초기화하지 않음. 별도8001/5181/5182 검증 서버 정리, 사용자8000/5173 유지.

## 2026-10-10 HR-TIME-01 회사 공동 출퇴근 PWA 설계

사용자 회사공동/버튼출퇴근/1시간시간차 확정. [설계안](../plan/회사공동_출퇴근_PWA_HR-TIME-01.md) 작성: HR소유·GW바로가기, 회사멤버십/사원연결 선행, 실제회원/합성게스트체험 분리, 실제시각원장·휴가분단위·출장·PWA오프라인제출금지. 기존AUTO예정근태·반차승인clock초기화와 실제기록 충돌 확인. 구현/DB변경/회사활성화 없음. 다음: 전체설계확인 후 회사접근기반부터 구현.

## 2026-10-10 사이드바 긴 메뉴·별 배경 보정 / main 반영

사용자 main 즉시 push 승인. W0-FAV-2 전체 즐겨찾기·아이콘 접기와 이번 고정24px아이콘/긴이름줄바꿈/별주변투명배경을 함께 main에 병합한다. 관련23테스트·타입검사 통과, 실제Chrome 긴게시판명 overflow없음/아이콘24px/별버튼배경투명 확인. 운영배포는 이번요청범위에 포함하지 않음. 이후 같은 사이드바 작업은 검증 후 main push 승인 유지.

## 2026-10-10 W0-FAV-2 전체 즐겨찾기·아이콘 사이드바 완료

- 사용자 요청: 현재 솔루션 필터를 제거해 모든 솔루션 즐겨찾기를 저장한 순서로 표시. 라벨/접근성 이름에 솔루션을 표시해 중복 대시보드 구분.
- 넓은 화면 접기는 메뉴를 숨기지 않고 아이콘 레일로 전환. title/aria-label로 설명과 키보드 이동 제공. 좁은 화면 서랍은 기존 표시 유지.
- 등록 별: 채운 금색/노란 배경/진한 테두리. 미등록은 회색 윤곽.
- 검증: frontend575/72파일·typecheck/lint/build 통과. 회귀는 교차GW/WMS 링크·접기 유지·전체전환/추가저장 포함. 실제Chrome GW에서 전체6개 표시→접기→MES아이콘 이동 확인.
- 브랜치 codex/favorites-sidebar-all. 이번 변경은 로컬 개발 서버 반영, 운영 배포는 아직 하지 않음. DB 변경 없음.

## 2026-10-10 GW·즐겨찾기 main 병합·운영 배포 완료

제품31af096 로컬main/원격main 병합 후 CI전체통과 및 정식deploy.sh 완료. 운영HTTP200/DDL오류0/최근5xx0/API14검사 통과, 실제Chrome저장·새로고침·MES등록메뉴표시 확인. 로컬DB구버전500은 백업 후 head마이그레이션으로 복구·기존공간유지. [결과](GW_즐겨찾기_main_배포검증.md). 후속기록커밋은문서전용, 제품배포31af096.

# GW·즐겨찾기 main 병합/배포 진행 (2026-10-10)

- 사용자 로컬main병합/운영배포 명시승인, 원격push 포함. 기존CI실패2건 보정: 목표재생성 partial 구현 호환·목표361표866FK/전체미구현설계 보존, tools133통과. SPC 테스트 시계만 고정·정책무변경, SPC18통과. 실제schema0.22.1/headw0_fav_menu_shape 유지.
- 현재 codex/workspace-favorites, 최종커밋git log -1. 로컬mainaf10726·originmain3ff4cf5·운영f860e8b 모두조상/깨끗함. 다음 로컬mainfast-forward→origin/mainpush→해당headCI통과→운영백업/정식deploy.sh(우회옵션없음)→공개사이트실제메뉴저장/사이드바/API/DDL확인→최종문서. 아직배포완료아님.
- 서버 158.247.236.136 /srv/factory-studio/app, service factory-studio-api, 공개 https://eip.hugh-d.com. 다른서비스/secretary DB 미접촉·초기화없음. 서버.env 읽거나출력하지 않음.

# W0-FAV 즐겨찾기 완료 인계 (2026-10-10)

- 사용자 이미지2장·참고React 분석→실제9솔루션108메뉴 연결. codex/workspace-favorites, 시작GW검토bfae108/WIPca74aaa, 최종커밋git log -1. [검증과화면](내공간_즐겨찾기_검증_W0-FAV.md), [계약](../ui/내공간_즐겨찾기_W0-FAV.md).
- 내 공간 카드/3열선택·검색·순서·임시선택취소, 사이드바등록메뉴/전체전환·별버튼. 공간 서버저장·초기화보존·게스트격리·회원다른세션공유. 최근브라우저별. 미확인응답멱등재시도/실제GET·다른업무잠금보존.
- schema0.22.1/headw0_fav_menu_shape/core.workspace2컬럼3CHECK(173표1918컬럼412FK). 실제·목표Excel/ERD/base_task동기화. 독립 factory_studio_favorites_test만 적용, 최초revision적용후무변경·JSONnullCHECK새revision. 별도왕복DB4회DDL0·삭제완료.
- frontend575/72파일·최종lint/format/typecheck/build, Ruff/format206·설계격리0. backend신규8/전체982통과·기존SPC실패1/skip1·독립perf1. tools131통과·기존DSN목표재생성오류1. 두기존main실패근거는GW_main_병합검토.md. 전체CI통과아님.
- Chrome6카드/ERP추가/순서저장·새로고침유지/MES등록2메뉴만/최근메뉴, 390px가로넘침0·44px적용·Esc포커스/Tab순환 확인. 회원실기기간UI/실마우스드래그는미검증(두회원로그인API/버튼순서검증).
- 공유main af1072669d6441d3b70605ff01054bc294cca393 깨끗함. main병합/push/운영배포/공유DB적용없음. 다음 반영 시 기존CI차단 해결 후 최신main재검토, 두플랫폼마이그레이션과프런트함께배포. 새업무자동착수없음.
- 재현: 독립 *_test DB+PYTHONPATH=backend/src:backend, xdist원본복제중접속금지·동일DBpytest동시금지. 로컬검증서버/생성브라우저탭종료, node_modules공유symlink제거·work/env스테이징제외.

## 이전 GW 병합 검토 인계

# GW-main 병합 검토 완료 인계 (2026-10-09)

- codex/gw-dsn31, 제품17f0f18, 최종검토커밋은 `git log -1 --oneline`. main af10726 직접조상/충돌0·fast-forward 가능. 실제 main 병합/push/배포 없음. [검토](GW_main_병합검토.md).
- 수정: tools/apply_fs030a.py 초기8표 포함 검사로 후속19표 보존, test_fs030a.py 확장 무변경 회귀. 기본표 누락 거부 유지. 도구7+4통과.
- 검증: PG18 빈DB/main/GW/rollback/reupgrade 카탈로그4회0·frontend566/71파일·lint/format/typecheck/build·Ruff202파일·DB설계/격리0. backend974통과/기존main SPC실패1/skip1, 독립perf1통과. tools131통과/기존main DSN재생성오류1. 원본main에서 둘다재현. 처음loadscope실행은 공유템플릿 초기화순서파손으로 무효, 기본분배 재실행 결과가 최종.
- 다음: DSN목표재생성·SPC측정시각 테스트 CI차단 해결 후 최신main재대조/병합. 새시드 배포시새템플릿 필요. 실제회사A/ERP확정통제/신규원천/인쇄PDF는 기존제한 유지.
- 사용자 새 요청: 참고 React시제품·이미지 기반 내공간 메뉴 추가/순서편집 및 MES/ERP 등 즐겨찾기만 표시하는 사이드바. 다음 별도 codex 브랜치에서 구현. GW 검토를 제품 전체CI통과로 인계하지 않는다.
- 재현: 독립 PG18 `_test` DB 환경 주입, PYTHONPATH=backend/src:backend, `pytest backend/tests -q -n 4 -m 'not perf'`, 이후 `pytest backend/tests -q -m perf`; tools 전체unittest/프런트 명령은 검토문서 참조. 비밀 접속값 Git에 없음.

## 이전 GW-e 완료 인계

# GW-e 완료 인계 (2026-10-09)

- codex/gw-dsn31, 시작8216636/WIPd78e534, 마지막커밋 `git log -1 --oneline`. worktree `/Users/hwang-kyoungho/Documents/Codex/2026-10-09/gw/work/factory-studio-gw`. [결과](GW_시드도움말_GW-e.md).
- 완료: GW19표98행/sv-20261009-gw1(HR4부서10담당자·일반/ERP매입초안·병렬대기·전결/위임/기존순차이력·댓글/일정/알림/채팅). ERP공개조회 snapshot 연결, JSON SQL NULL구분·GW사건시각 보존. 복사 FK외 JSON단계/위임/전결ID·범위/월/시각 및 알림refId/eventKey변환, KST상신월재계산, 같은TX지도정리. 원본/digest/코드금액조직·채팅seq/clientKey/readCursor보존. V-GW검증, 도움말13+공통안내·정적흐름3노드3연결·DSN90실제계약.
- 검증: DB신규6통과. 전체backend974통과/1실패/1skip(379.71s), 다른새공간GW빈가정 조직격리1건 테스트만 보정→조직17전체 재통과(37.85s), 총975서로다른테스트확인(보정후전체재실행은안함). frontend566/71files·최종타입/build/전체ESLint·전체backendRuff/변경format/diff·DB설계/173표412FK격리0. rootRuff기존policy import1건보정. Chrome새guest11/gen13 시드10명·기안현황2/1/2, 실제위임→합의→종결, 알림링크→일정응답, 댓글revision/삭제, 채팅seq1/2→3,390px/도움말/흐름, 처리후V-GW통과. 증거 docs/agent/assets/gw-e.
- 다음: 사용자 결과 확인 후 **main과 병합 검토**. main공통엔진optional authorize·MasterScreen·MES테스트mock·seedversion·migrationparent/schemametadata·current/progress/HANDOFF충돌을 재대조할 것. 아직push/merge/배포 없음. 새시드배포는 새템플릿생성 필요(기존운영템플릿수정금지). 실제도입A/TEAM계정ACL·ERP F44 및 ERP발주/경비·PLMECO원천제공은 별도후속. 네이티브인쇄PDF/대량운영부하 미검증 유지.
- 재현: 전용 *_test DB만 사용, mainvenv재사용시 PYTHONPATH=backend/src:backend 필수. 같은DB의 독립pytest 동시실행금지; -n4 원본DB복제중preview접속금지, 끝난workerDB집중검증가능. API8073/Vite5273·검증탭 종료, viewport복원·node_modules 심볼릭링크 정리. 접속값은Git/문서/로그에 넣지 않았다.

## 이전 GW-d 기록

# GW-d 협업 인계 (2026-10-09)

- 브랜치 codex/gw-dsn31, 기준b39e274, WIP2a30415, 마지막커밋 git log -1 --oneline. worktree `/Users/hwang-kyoungho/Documents/Codex/2026-10-09/gw/work/factory-studio-gw`. [결과](GW_협업_GW-d.md). main/공유DB/push/merge/배포 없음.
- 완료: 댓글revision/삭제표시·부서공지/현재조직열람, 개인/부서 월/주 일정·응답/수정/취소, 알림 동일TX recipient/event_key중복0·읽음/현재열람, 채팅 1:1/그룹·HTTP저장/활성3초조회·seq/clientKey·탈퇴차단. G-04/05보강·G-11/12/13, 도움말4신규+G04보강. EIP전체공간공지·공통4종제공(None off/빈결과구분). commonengine optional authorize를 공간잠금후/멱등재사용전에 실행, 기존호출 기본None.
- 검증: 전체backend967/1skipped(마지막권한보정전), 최종공통/GW 103통과(협업23), frontend566/71파일, 최종타입/전체lint/build·범위Ruff/format·DB설계/격리0. 실제Chrome 일정/응답·알림/공지댓글/삭제·두탭자동채팅/읽음/탈퇴·390px/도움말 확인. 대량부하/네이티브인쇄PDF/실제회사권한/운영 미검증, 기존rootRuff GW import2건 유지.
- DB schema0.21.0/GW19·전체173/headgw_a_dsn31, 시드버전 변경없음. 실제도입A/CORE TEAM/ERP F44 제외. 신규ERP발주/경비·PLMECO 원천제공은 외부미구현, GW계약 유지.
- 다음: 사용자 결과 확인 후 GW-e 시드·도움말·통합 검증. 아직 착수안함. 전결rule/위임/approval_event.details/조직 및 협업 댓글revision·일정attendee·알림event_key·chatseq/clientKey/readCursor 유데이터의 세대 복사/날짜/내부ID·정리 검증. 일반/부서공지·결재알림대기·채팅·일정 체험시드와 공통도움말/DSN90 계약 정리.
- 재현은 결과문서 표준명령. 기존 main venv/node_modules/Node24 재사용 가능하나 PYTHONPATH=backend/src:backend 필수. 독립 *_test DB만, 같은DB 독립pytest 병렬금지; 전체 -n4 초기원본복제 동안 preview연결금지. 최종집중은 원본preview와 별도작업자DB사용. 서버8073/5273 종료, 의존성 심볼릭링크 최종정리. mac잠금native창은제어지연, 화면내확인으로검증완료. work/비밀정보스테이징금지.

## 이전 GW-c 기록

# GW-c 조직·HR 연계 인계 (2026-10-09)

- 완료: 사용자 후속 승인 범위 GW-c(G-07·G-10/F21~23). `codex/gw-dsn31`, 시작0dd6ef9/WIP1fe0642, 최종커밋 `git log -1 --oneline`. 격리 worktree `/Users/hwang-kyoungho/Documents/Codex/2026-10-09/gw/work/factory-studio-gw`. [결과](GW_조직HR연계_GW-c.md).
- G-07 공통 MasterScreen·HR 미리보기/선택/명시적 가져오기, G-10 현재 HR/마지막 조직 조회, 도움말2편. HR interface만 읽는다. 이름/부서만 갱신·동일 사원 ID 유지, 기존 GW 직무/활성·상신 조직/이력 보존. 퇴직/원천 없음/조회 불가 구분. 조직 순환·비활성 상위·누락·중복·코드 충돌·원천 변경·동시성·롤백 보호. 신규 STAFF·최대1,000명/회·부서만 가져오기 가능. 전체 역할 조회로100명 이후 누락 방지.
- 검증: 전체 backend944/1skipped(362.48초), 최종 GW66/신규17(107.36초), 감사 보정 후 신규17(46.13초). 전체 frontend559/70파일·최종집중134/16파일, 타입/빌드/전체frontend ESLint·GW Ruff·DB설계0. root 전체Ruff는 시작과 동일한 기존 test_gw.py·test_gw_policy.py import 정렬2건. import 분류는 실행 위치에 영향을 받으므로 결과문서의 명령/위치를 함께 재현한다.
- 실제 Chrome: HR 미개방→개방→부서4/사원10 가져오기, HR 명칭 변경 뒤 현재HR/마지막GW 차이, 신규0·갱신10 재가져오기,390px 본문 넘침0·표 내부 스크롤·도움말. 발령/조직 불변은 실제HR API+DB로 검증(브라우저 발령 재연 없음). 모바일 체크박스 공통 inline-check 보정. 기존 MES 진입 테스트의 빈 dashboard mock만 정상 합성 응답으로 수정해 전체 프런트 회귀 안정화; MES 제품 코드 변경 없음.
- 상태: DB/schema/시드 버전은 GW-a 그대로. main/공유DB/push/배포 없음. API8073/Vite5273·검증탭 종료, viewport복원, 의존성 symlink 제외/정리. 최종 브라우저는127.0.0.1(기본 localhost의 인증 쿠키와 분리). 접속값은 인계 문서/로그/Git에 넣지 않았다.
- 재현: 독립 `_test` DB에 TEST_DATABASE_URL, `PYTHONPATH=backend/src:backend`, main venv와Node24 사용 가능. 전체pytest `-m 'not perf' -n4`, GW파일3개 집중, 프런트 전체/build·결과문서 명령. 같은DB에서 독립pytest 동시 실행 금지. xdist 복제 중 원본 DB에 접속하지 않는다.
- 다음: 사용자 결과 확인 후 **GW-d 협업**(댓글/일정/알림/채팅). 미착수. 이후 GW-e 시드/도움말, 채워진 rule/delegation/event.details 복사·날짜·ID·증빙 검증 보강. EIP published_notices/공통4조회 실제 제공 상태도 후속 재대조. ERP F44/신규원천제공은 외부 담당자 소유, 실제 도입 A트랙은 제외. GW-b 인쇄 미리보기/PDF 미검증은 유지.

## 이전 GW-b 인계 기록

# GW-b 인계 (2026-10-09)

- 브랜치 `codex/gw-dsn31`, 시작GW-a `19e8f9e`, WIP `6ce757c`, 마지막 커밋 `git log -1 --oneline`. 격리 worktree: `/Users/hwang-kyoungho/Documents/Codex/2026-10-09/gw/work/factory-studio-gw`. main/공유DB/push/배포 없음. [결과](GW_결재확장_GW-b.md).
- 완료: 신규문서 정책2·병렬/합의/참고·상신전결고정·처리시점 위임조건/해제 재검사. G-02/03/04/06·G-08/09, 브라우저인쇄 코드·도움말6편. 기존policy1은 전결/위임 제외·순차 유지. 공통action/master사용, 버전/멱등/공간잠금/감사.
- 검증: 전체backend927/1skipped, 마지막보정 GW58, 전체frontend554·최종GW/콘텐츠26, tsc/전체frontendeslint/build/GWruff/DB검증0. Chrome결재선·전결·위임등록→상신→대리승인→합의→최종승인, 390px 넘침없음. 전체backendruff 기존core/service.py I001(기준본 재현), 인쇄 미리보기/PDF는 Mac잠금으로 미검증.
- 외부 의존: ERP PURCHASE_ORDER·EXPENSE_CLAIM 제공미구현, PLM eco_for_approval 없음. GW종류/소비/배지계약은 구현·mock검증. ERP는 APPROVAL_KINDS 선언, PLM은 ECO번호직접입력 지원. approvals 단일종류 번호키/혼합종류 `종류:번호` 키. 실제 회사 신원/공유공간/A트랙 및 F44 ERP 확정통제 제외.
- 다음: 사용자 결과 확인 후 GW-c 조직·HR 연계. 시작하지 않았다. GW-e 시드에서 rule/delegation/approval_event.details가 채워지면 날짜 이동·내부ID·증빙 스냅샷의 복사/정리 검증을 보강할 것.
- 재현: `TEST_DATABASE_URL`은 독립 `_test` DB, `PYTHONPATH=backend/src:backend`, 기존 backend venv/Node24 재사용 가능. 결과 문서 명령 참고. 동일DB에 여러 독립pytest를 동시 실행하지 않는다. 브라우저용8073/5273 프로세스 중지, 의존성심볼릭링크는제외/정리. `work/`에만 다음작업의 필수정보를 두지 않았다.
- DB는 GW-a schema0.21.0/headgw_a_dsn31/GW19·전체173 그대로. 병합 시 main MESmetadata·부모revision·제약순번/버전을 재대조할 것. GW-b schema migration 추가 없음.

## 이전 GW-a 인계 기록

## GW-a 체험 그룹웨어 DB (2026-10-09)

- branch `codex/gw-dsn31`, 시작 `af10726`, 마지막 커밋 `git log -1 --oneline`. 작업 경로는 `git worktree list`의 해당 브랜치. main/다른 세션 폴더는 수정하지 않았다. [결과](GW_체험보강_DB_GW-a.md).
- 완료: DSN-31 체험·조직11표 + 기존6표15칼럼, GW19/전체173, schema0.21.0/head`gw_a_dsn31`. 실제 도입A5표·CORE TEAM·ERP통제 제외. metadata/Excel/ERD/현황/progress 동시 갱신. `apply_gw_a.py` 멱등·제약순번보존; `build_migration.py` rollback FK/제약→칼럼→표→옛제약복원으로 보정. 이전 migration은 수정하지 않았다.
- 독립 `factory_studio_gw_a_test`에만 적용. 공유개발·CI원본·운영DB 미적용. 기존승인문서 왕복/DDL대조0, 도구4/실DB신규3·기존GWfrontend5/tsc/eslint/ruff/브라우저담당자등록 통과. 전체 backend900통과·1건너뜀(330.21초). 코드/API/신규화면은 미구현, 원격push/배포 없음.
- 당시 다음 단계: GW-b(사용자 승인 후 위 최신 기록처럼 구현 완료). 기존policy_version1 기본값으로 v1 순차결재 유지. ERP 발주/지출결의·PLM ECO 제공 인터페이스 존재 확인. A를 GW-a16표로 다시 넣지 않는다(인계프롬프트의 A 제외와 충돌).
- 재현: 결과문서의 명령. 새 DB는 PG18 및 `_test` 접미사. venv/node_modules는 main 것 재사용 가능하나 `PYTHONPATH=backend/src:backend`로 현재 worktree의 코드 사용. 테스트는 `EMPTY_MODULES=("gw",)`로 빈모듈 표시. 목표 `base_task`는 GW-a; main MES 진행과 병합할 때 schema/migration 부모/제약순번/버전을 다시 대조해야 한다. worktree branch의 단일 head는 w2a1_mes→gw_a_dsn31. 시드버전 변경 없음.

## UI-DESIGN-02 실제 UI 적용 (2026-10-09)

- branch main, 시작 기준66e3001, UI 구현 커밋 **0d34ec5**. 마지막 인계 커밋은 `git log -1 --oneline`. 사용자 전체 추천안 확인 후 구현100%. 로컬 커밋만, 원격 push/운영 배포 없음. 병행 MES/common/master·shared/master·MES 화면/테스트는 다른 작업자의 변경이며 보존/스테이징 제외.
- 끝난 것: Taste Entry.tsx+Entry.css/합성 NC 이미지, CAD 셸, E1/E2 공통 UI, nc-layout.js 기존 DOM 재배치/4준비단계·뷰포트/휴디·결과/접기, 공장 하단 시연·맥락 패널·초점. 현재 도움말/설계안/현황/progress 상태도 갱신. [결과와 캡처](UI개선_적용결과_UI-DESIGN-02.md).
- 검증: CAD142/frontend551(68파일)·최종 대상40·build/격리·대상 lint/format/diff. Chrome NC 전체 분석/3후보/텍스트3번재생정지, E2 체적24,000mm³, 랜딩 로그인·공장/1440·390. 공장 browser4종 통과: CNC1개 완료·정지·오류 복구·모바일 포함; 외관33.3초로 기존30초 초과, 60초 재검증 통과/테스트 제한 보정. 실제 음성 발화·운영/DB/실장비·계측은 미검증/미실행.
- 다음: 사용자 결과 확인. 다음 ID·운영 배포·원격 push 자동 진행 없음. NC 모델/품질 차단/후보revision/보호POC/iframe microphone 정책 유지. 스킬은 정적 프로젝트 지침이며 launcher/hook 사용하지 않는다.
- 재현: Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; `npm --prefix prototypes/cad-cam test`; `npm --prefix frontend test -- --maxWorkers=2`; `npm --prefix frontend run build`; `npm --prefix frontend run test:factory-browser -- --grep '공장 장면은|건물|CNC'`. 3D 소프트웨어 렌더 캡처는 시간이 걸린다. 이 세션의 검토 Vite는5194, 기존 다른 포트/DB는 건드리지 않았다. 재실행은 `npm --prefix frontend run dev -- --host 127.0.0.1 --port 5194 --strictPort`; Git의 합성 예제·문서·캡처를 사용하고 work/tmp에 의존하지 않는다.

## W2a-1b MES 기준정보 화면 완료 (2026-10-09)

- branch main. M-16 불량·사유 코드, M-17 작업자·근무조, M-19 라벨 양식, M-26 공정 검사 기준. MES OpenAPI 경로 50 → 62.
- 새 파일 `backend/src/fs/mes/masters.py`, `backend/tests/test_mes_masters.py`, `frontend/src/mes/{Codes,Workers,Labels,InspectionItems}.tsx`, `frontend/src/mes/masters.test.tsx`. 수정: mes/{schema,router}.py, `fs/common/master.py`, `frontend/src/shared/master.tsx`, mes/{index,MesLayout}.tsx.
- 주의점: `MasterScreen`을 **탭으로 갈아끼울 때는 `key`를 준다** — 같은 컴포넌트라 목록·입력이 그대로 남는다. 공통 엔진의 중복 검사는 이제 `IS NOT DISTINCT FROM`이라 NULL 키 칸도 잡는다.
- MES 라우터는 `_values(payload, nullable, full=True)`가 등록용이다(기본값까지 보낸다). 기존 `_register`는 옛 `repository.Master`용이라 섞지 않는다.
- **남은 결함**: `mes.inspection_item`의 UK는 `item_id IS NULL`인 행끼리 DB가 막지 못한다. 서비스가 막지만 동시 등록이면 뚫린다. 목표 설계에 조건부 유니크를 더해야 한다.
- 재현: `cd backend && TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_mes_masters.py -q`; `npx --prefix frontend vitest run src/mes`.
- 미실행: M-12~15 보강, 시드·도움말, 운영 배포(운영 `f860e8b`). 다음: W2a-1b2.

## UI-DESIGN-01 도움말·스킬·전체 UI 검토 (2026-10-09)

- branch main, 시작 기준 bb3b1bd, 구현/검토 자료 커밋 **fc7e3f1**. 인계 문서의 최종 커밋은 `git log -1 --oneline`로 확인한다. 로컬 커밋, 원격 push/운영 배포 없음. 병행 작업자의 common/master·MES backend/화면/테스트 파일은 건드리거나 스테이징하지 않는다.
- 완료: 공개 도움말5편·P-05·검색/목차/화면 경로·CAD/공장 직접 도움말. `.agents/skills/`의 factory-taste/factory-impeccable 고정 원본+프로젝트 파생 지침/라이선스/출처. CLI/hook/자동 다운로드/별도 agent 설정 미설치. 다음 턴부터 프로젝트 스킬 사용 가능.
- [전체 UI 검토안](../ui/UI개선_전체검토안_UI-DESIGN-01.md)·[구조 시제품](../ui/previews/UI-DESIGN-01.html)·PNG4장. 시제품은 배치·문구 검토용이며 실제 CAD/3D 엔진·분석·세션 생성 없음. 도움말 링크 외 제품 UI 재배치 미착수. 사용자 전체 확인 후 UI-DESIGN-02만 진행, 자동 다음 ID 착수 없음.
- 검증: frontend546/67파일·대상40, 전체build/자산 격리·대상 lint/format/diff, 스킬 frontmatter2개, Chrome3탭구성/1440·390폭/가로 넘침0·육안. 처음 도움말 Markdown 강조 오류는 수정 후 재검증. 시스템 YAML 미설치→임시 검증 venv, 제품 패키지 변경 없음. 기존 번들 경고 유지.
- 주의: 관리자 비누 POC를 공개 도움말/랜딩 이미지로 사용하지 않는다. NC 계산/품질/권한/파일 저장 동작과 3D 시연 안전 상태 유지. CAD-V01 실제 음성 리허설은 여전히 미검증. DB·장비·운영 배포 미실행.
- 재현: Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; `npm --prefix frontend test -- --maxWorkers=2`; `npm --prefix frontend run build`. 시제품은 HTML을 Chrome에서 열어 상단 랜딩/CAD·CAM/3D공장 전환. 검토 자료와 스킬은 Git에 저장되며 work/tmp에 의존하지 않는다.

## W2a-1a MES 보강 DB 완료 (2026-10-08)

- branch main. mes 21 → 45테이블, 전체 162. 마이그레이션 **`w2a1_mes`**(head). schema.json 0.20.0 / W2a-1a.
- 새 파일 `tools/apply_w2a1.py`. `tools/build_migration.py`에 `--previous`(기존 표 변경) 추가.
- 주의점: 제약 이름은 **schema.json `constraints` 배열의 순번**이다. 새 제약은 반드시 **배열 끝에** 붙이고, 바꾸는 제약만 제자리에서 고친다 — 중간에 끼우면 운영 DB의 제약 이름과 어긋난다.
- `mes.work_order` ↔ `mes.lot`이 서로를 가리키는 **고리 FK**다. 게스트 정리(`fs/core/service.py::_cleanup_plan`)는 고리 안의 비울 수 있는 FK만 먼저 비우고, 시드 복사(`seed/copy.py::_table_order`)는 그 간선만 무시한다. **고리 밖 nullable FK를 비우면 안 된다**(fems.energy_target CHECK가 깨진다). 시드가 그 칼럼을 채우게 되면 복사 뒤 UPDATE 단계가 필요하다(`ponytail:` 주석).
- 재현: `backend/.venv/bin/python tools/apply_w2a1.py`; `... tools/build_migration.py --revision w2a1_mes --down w1a_hr_module --tables 'mes.*' --previous <git show HEAD:schema.json> --out ...`; `npm run db:validate`; `npm run db:build`; `python3 tools/build_erd.py`; `DATABASE_URL=... python tools/verify_ddl_matches_schema.py`.
- 미실행: 화면·API·시드, 운영 배포(운영은 `f860e8b`, 다른 세션 미커밋 문서 때문에 배포 보류 중). 다음: W2a-1b.

## CAD-V01 구현·로컬 검증 완료 (2026-10-08)

- branch main, 기준2241851·구현39204d3, origin/main push 성공(1ecd4f5→39204d3), 마지막 커밋 git log -1. 사용자 전체 흐름 구현 승인·최신 환경은 **맥북 Google Chrome/NC 에너지 제안**. 아래 Windows 설계 항목은 이전 이력이다. [계약](../modules/cad-cam/음성발표데모_제안_CAD-V01.md)·[검증/발표 준비](휴디_NC음성발표_CAD-V01.md).
- 끝난 것: 휴디 호출/한국어 명령/응답·후보 번호/ID/revision·G4 시간 모델 재생/정지/누적kWh·기존 품질 차단·입력 무효화·음성 실패 대안·합성 발표 예제. CAD141/frontend545·전체build/격리/포맷/대상 lint/diff·실 Chrome/모의 게스트 포털 iframe 흐름·390폭 확인. 실제 인증/DB 아닌 합성 세션이다.
- **남은 검증: 맥북 실제 마이크 발화·TTS 리허설**. 코드와 모의 음성 테스트 통과를 실제 음성 서비스 성공으로 소개하지 않는다. 발표자는 Chrome/macOS 마이크 권한과 인터넷을 확인한다. 운영 배포/실 CNC/실측 품질·절감 미실행/미검증. CAD-17 자동 착수 없음.
- 재현: Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm --prefix prototypes/cad-cam ci/test/format:check; npm --prefix frontend test -- --maxWorkers=2; npm --prefix frontend run build. 핵심 파일·합성 NC·캡처는 리포지토리에 저장, work/tmp에만 의존하지 않는다.
- 로컬 검토: frontend/scripts/cad-preview-api.mjs(8042)와 FS_SMOKE_API_PORT=8042 frontend Vite(5244), 합성 게스트. 이 세션이 시작했던 별도 frontend5243·prototype5245 검토 서버는 종료했다. 실제 backend/공유 DB를 시작하지 않았다. 병행 작업자의 MES migration·schema·ERD·시드·service 변경은 그대로 보존하고 커밋에서 제외한다.

## CAD-V01 발표 대상 확정·설계 수정 (2026-10-08)

- branch main, 기준1ecd4f5. 마지막 커밋은 git log -1. 문서만 변경: [음성 발표 제안](../modules/cad-cam/음성발표데모_제안_CAD-V01.md), 현재 현황, 진행 기록. 타 작업자 파일 변경 없음.
- 사용자 확정: **Windows·Google Chrome 일반 브라우저·NC 에너지 제안**. Mac/E1 가정으로 구현하지 않는다. 발표 브라우저 Google Chrome 확정. NC 현재 코드는 후보 비교/행 선택뿐이고 자동 재생이 없으므로 번호/revision 선택+후보 G4 시간 모델의 경로/시간/kWh 재생을 음성과 함께 구현할 전체 제안으로 작성했다.
- 다음: 전체 수정 흐름 확인 후 CAD-V01 구현. Windows 실마이크/발화 검증 필요. 문서 검사만 수행했으며 음성/재생 제품 코드·테스트/build·DB/운영 배포 미실행. 기존 CAD-16 완료/main push1ecd4f5 유지; CAD-17 자동 착수 없음.
- 재현: NC 코드 `prototypes/cad-cam/src/{nc-review,nc-proposal-review,nc-proposals,nc-viewer}.js`와 CAD-15 계약 대조. 문서 상대 링크 검사와 git diff --check. work/tmp에만 의존하지 않는다.

## CAD-16 완료 (2026-10-08)

- branch codex/soap-cad-review, 기준257871e·WIP12cf7d0·HR W1c b8b3405 보존 병합69737d6·포털72b253a 보존 병합c3b3ec2. 마지막 커밋 git log -1. 442482e까지 main fast-forward·origin/main push 성공(72b253a→442482e), 운영 배포 없음. 타 작업자 main 포털/UI 수정은 편집/스테이징하지 않는다.
- 끝난 것: E1/E2 공통 전문 스케치/섬 영역·국소 필렛/모따기/선택 면 기하 참조, 파일 상한/모달 키보드 격리. [계약](../modules/cad-cam/전문스케치_직접편집_설계_CAD-16.md)·[검증](전문스케치_직접편집_CAD-16.md). prototype134/frontend545·포맷/전체build/격리·실 UI/1440·390폭 통과. STEP 커널 왕복/STL 체적 통과, 브라우저 다운로드 수신은 시간 초과로 미확인. DB/실 CNC/운영 배포 미실행.
- 다음: 사용자 결과 확인 후 CAD-17 또는 **추가 요청 [CAD-V01 음성 발표 제안](../modules/cad-cam/음성발표데모_제안_CAD-V01.md)** 범위 확정. 최신 제안은 Windows Google Chrome/NC 에너지 대상 확정. 마이크·음성 구현 미착수. 자동으로 다음 ID를 시작하지 않는다.
- 재현: Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm --prefix prototypes/cad-cam test; npm --prefix prototypes/cad-cam run format:check; npm --prefix frontend test; npm --prefix frontend run build. localhost5243/8043은 모의 관리자 fixture. Git 예제 JSON/PNG/보고와 tests/{sketch-edit,direct-edit}.test.js를 사용한다. 임시 work/tmp 파일에 의존하지 않는다.

## W1c HR 시드·도움말 완료 (2026-10-08)

- branch main. 끝난 것: HR 합성 시드(`backend/seed/hr.py`), 공통 휴일 달력(`core.holiday` 16건 + 게스트 복사), 검증 규칙 V-HR, 도움말 15편(`content/help/hr/`), 전체 흐름 맵 HR 3노드.
- **시드 버전 `sv-20261001-1` → `sv-20261008-1`.** 다음 배포에서 시드 템플릿이 다시 만들어져 배포가 길어진다.
- 주의점: 시드는 기준일 T 기준으로 **지난달 = 마감·급여 확정 / 이번달 = 기준일까지 근태 + 마감 작성 중**이다. V-HR은 복사본에서도 통과하도록 **절대 월이 아니라 달 사이 관계**로 본다. 금액은 제품의 `fs.hr.payroll.slip_lines`를 그대로 쓴다 — 계산식을 고치면 시드도 같이 바뀐다. 공휴일은 복사할 때 **날짜를 밀지 않는다**(실제 달력).
- 행 수가 기준일에 따라 달라지는 `hr.attendance`·`hr.payslip_line`은 `seed.validate.DATE_VARYING`으로 빼고 규칙으로 본다. 고정 합계 **14,794**(검증기) / **14,811**(writer, core.holiday 포함) / **14,809**(복사본).
- 빈 공간을 전제하는 테스트는 모듈에 `EMPTY_MODULES = ("hr",)`를 선언한다. 선언하지 않으면 화면을 처음 열 때 지연 복사가 시드를 넣는다.
- 재현: `cd backend && DATABASE_URL=... PYTHONPATH=src .venv/bin/python -m seed.cli template --date $(TZ=Asia/Seoul date +%F)` 후 `... validate --date ... --workspace N --generation M`. 테스트는 `pytest -m "not perf" -n 4`.
- 미실행: 운영 배포. 다음: W2a.

## CAD-15 품질 우선 NC 검토 제안 완료 (2026-10-08)

- branch codex/soap-cad-review, 기준f860e8b·구현5761608·운영 기록c769a42 보존 병합7aefb20, 최종 커밋 git log -1. 기존 main push 승인 유지. a3c1c6f까지 main fast-forward·origin/main push 성공(f860e8b→a3c1c6f)·이번 CAD-15 운영 배포 없음. HR/시드 등 main 타 작업자 수정은 소유자 작업이므로 스테이징/편집하지 않는다. [계약](../modules/cad-cam/품질우선_NC제안_설계_CAD-15.md)·[검증](품질우선_NC제안_CAD-15.md).
- `/cad-cam?view=nc`: 전체 에너지 분석 후 품질 우선 개선 제안 → 대기 목록/품질 기준·최소시간·목적/영향 확인 → 소비 비교. 단독 G4만, 품질 미달/근거 없음 차단·범위/여유 미정 우열 보류. 원본/경로/F/S/T 보존·NC 자동 적용/출력 없음. JSON 근거·200대기/12선택·입력 무효화. 합성 예제 버튼으로만 가정 입력.
- prototype117/frontend544·포맷/build/격리/diff·실제 후보/근거/과절삭 차단·행 선택/무효화/201페이지/상한·1440/390폭 통과. Node5만행 목록88.95/비교106.51ms, 동기 계산 느린 기기 지연 가능. 실측 품질/안전/절감·JSON재열기/Safari/실기기 대형 부하/DB/이번 운영 배포 미검증.
- 다음은 사용자 결과 확인 후 CAD-16 한 ID. Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm --prefix prototypes/cad-cam test; npm --prefix prototypes/cad-cam run format:check; npm --prefix frontend test; npm --prefix frontend run build; node --expose-gc prototypes/cad-cam/experiments/nc-proposal-benchmark.mjs. localhost5243/8043 합성 관리자 fixture. Git 예제/보고/PNG/benchmark 사용, work/tmp 의존 없음.

## 운영 배포 (2026-10-08)

- 운영 https://eip.hugh-d.com = main **`f860e8b`** (이전 3474942). W1b-2·3·4 HR 전체 + CAD-12~14 포함. 마이그레이션 head `w1a_hr_module`, 시드 템플릿 변경 없음.
- 확인: 원점/공개 200 · DDL 대조 0 · 5xx 0건 · 운영 브라우저에서 H-01·H-10 표시 · `/api` 응답 `Cache-Control: no-store`.
- 배포는 `./tools/deploy.sh` 한 줄(먼저 `--dry-run`).

## CAD-14 시간·소비 모델 완료 (2026-10-08)

- branch codex/soap-cad-review, 기준e7c42cd·구현8e5b19e·HR b16e721 보존 병합854a3c8. 최종 커밋은 git log -1. 기존 사용자 main push 승인 유지. 92a2b84까지 main fast-forward·origin/main push 성공(e7c42cd→92a2b84), 운영 배포 없음. main 진행 중 HR 파일은 타 작업자 소유이며 건드리지 않는다. [계약](../modules/cad-cam/시간소비모델_설계_CAD-14.md)·[검증](시간소비모델_CAD-14.md).
- `/cad-cam?view=nc` 현재 NC/소재 → 상태표 → 장비 축 제한·전체 kW·이벤트 시간 → 시간/kWh. 빈칸 미정/알려진 소계, 출처/별도 비교 비보정, 합성 예제, 200구간/행 선택/JSON·Worker. 실제 CNC/계측/정확도·안전/부하 보정/DB/운영배포 미검증. CAD-15 자동 착수 금지, 사용자 결과 확인 뒤 한 ID.
- prototype104/frontend544(67파일; HR 병합 후 재검증)·포맷/build/격리/diff·실제 계산/미정/비교/행 선택/200페이지/1440·390폭 확인. Node5만행73.01ms(브라우저/peak 아님). 빌드 중 이전 Worker 자산 오류는 새로고침 후 통과; 실30초/브라우저취소 경합/stale주입/다운로드재열기 미검증.
- Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm --prefix prototypes/cad-cam test; npm --prefix prototypes/cad-cam run format:check; npm --prefix frontend test; npm --prefix frontend run build; node --expose-gc prototypes/cad-cam/experiments/nc-energy-benchmark.mjs. localhost5243/8043은 합성 관리자 fixture. Git 보고/PNG/benchmark에 결과 저장, work/tmp 의존 없음.

## W1b-4 HR 평가·현황·본인 완료 (2026-10-08)

- branch main. 끝난 것: 자격·교육(H-05 인사카드), 인사 현황(H-01), 인사 평가(H-13), 인건비·근태 분석(H-14), 내 정보(H-15), EIP 공통 제공 `monthly_summary`·`pending_tasks`·`lookup`. **HR 15화면이 모두 구현됐다.** HR OpenAPI 경로 48개.
- 새 파일 backend/src/fs/hr/{review,analytics}.py, backend/tests/test_hr_review.py, frontend/src/hr/{Overview,Reviews,Cost,Me}.tsx, frontend/src/hr/review.test.tsx. 수정: hr/{schema,router,service,interface}.py, backend/src/fs/common/request_logging.py, frontend/src/hr/{Employees,index,HrLayout}.tsx.
- 주의점: 평가자는 코드 문자열(`reviewer_code`)이고 FK가 아니다. 확정은 `status='confirmed' = (confirmed_at IS NOT NULL AND grade IS NOT NULL)` CHECK를 지켜야 해서 한 UPDATE로 처리한다. 평가 기간을 닫으면 그 해 평가를 더 만들거나 고칠 수 없다(409 `CYCLE_CLOSED`). 인건비·`monthly_summary`의 인건비는 **확정 급여만** 센다. H-15는 EIP 연동 전까지 화면에서 사원 코드를 고른다.
- 라우터 `_values(payload, full=True)`가 등록용이다. 기본값이 있는 새 등록 본문을 만들면 **반드시 `full=True`**로 넘겨야 한다(DB 기본값이 없는 칸에서 NOT NULL 위반).
- 재현: `set -a && . ./.env && set +a`; `cd backend && TEST_DATABASE_URL="postgresql+psycopg://factory_studio:$POSTGRES_PASSWORD@127.0.0.1:$POSTGRES_PORT/factory_studio_ci_test" .venv/bin/python -m pytest tests/test_hr_review.py -q`; `npx --prefix frontend vitest run src/hr`. 로컬 미리보기는 .claude/launch.json의 backend(8000)·frontend(5173), uvicorn에 --reload가 없어 백엔드를 고치면 preview를 다시 띄운다.
- 로컬 게스트 공간은 생성 다음 날 00:00 KST에 만료된다. 만료된 공간으로 브라우저 검증을 이어가려면 새로 만들거나 `core.workspace.expires_at`을 미뤄야 한다(로컬 전용).
- 미실행: 전체 pytest 일괄 실행, 운영 배포(운영은 아직 `3474942`). 다음: W1c HR 시드·도움말, 그 뒤 W2a.

## CAD-13 소재·공구·STEP 정합 완료 (2026-10-07)

- branch codex/soap-cad-review, 시작83483dc·구현6fb5a96·STEP 정리0c34d32. 로컬 main fast-forward·origin/main push 성공(83483dc→0c34d32), 마지막 인계 커밋은 git log -1. 기존 사용자 main push 승인 유지·운영 배포 없음. main 진행 중 HR 파일은 타 작업자 소유이므로 스테이징/편집하지 않는다. [계약](../modules/cad-cam/소재공구_STEP정합_설계_CAD-13.md)·[검증](소재공구_STEP정합_CAD-13.md).
- `/cad-cam?view=nc` 소재/평엔드밀 T·H/D참조·단일 STEP→G54 정합/겹침·제거/잔삭/과절삭/급속 접촉 후보 행·숫자 공구표·예제. 비교는 수평/수직 면의 바닥부터 이어지는 상면만, 곡면/중공/언더컷·H/D보정·홀더/지그/기계 안전·전력은 미지원. 입력 변경은 정합/분석 무효화. 샘플 NC→해석→STEP예제→정합/상면 확인→소재 검토 실행.
- prototype88/frontend539·포맷·전체build/격리/diff·실제 NC/STEP/정합 차단/급속34행/입력 무효화/1440·390폭 확인. STEP취소 시도는 먼저 완료돼 미검증, 실제30초/stale강제주입·대형메모리/다운로드재열기·DB/실물/계측/운영 배포 미검증·미실행. 다음은 결과 확인 뒤 CAD-14 한 ID만, 이번에 시간/kWh 계산 없음.
- 재현 PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm --prefix prototypes/cad-cam test; npm --prefix prototypes/cad-cam run format:check; npm --prefix frontend test; npm --prefix frontend run build. fixtures 생성: node prototypes/cad-cam/experiments/nc-cad13-fixtures.mjs. 작업 화면 localhost5243/8043은 worktree 합성 관리자 fixture, 운영 DB 아님. 화면/샘플은 Git 기록, work 임시 파일 의존 없음.

## CAD-12 NC 경로 검토 완료 (2026-10-07)

- branch codex/soap-cad-review, 시작7861ed1·WIP24779cd·최종 구현/검증1f26837. 로컬 main fast-forward·origin/main push 성공(7861ed1→1f26837), 마지막 인계 commit은 git log -1. 기존 main push 승인 유지, 운영 배포 없음. [계약](../modules/cad-cam/NC해석_경로검토_설계_CAD-12.md)·[검증](NC경로검토_CAD-12.md). main의 진행 중 HR 변경은 별도 작업자 소유이며 스테이징하지 않는다.
- NC 메뉴 `/cad-cam?view=nc`, 3축 LinuxCNC 기반 제한 프로필·로컬 파일/붙여넣기·코드/경로 동기·이벤트/모달 전후 상태·첫 미지원 차단·200행페이지·원문/해시·Worker취소/상한. 초기좌표 확인 필요, G43/사이클/매크로/선반 미지원. M6/M30 기계 자동 동작 미정, 실제 장비 전체 재현 아님. 파일 메모리만·새로고침 소멸; DB/기존 E1/E2/비누 권한 정책 변경 없음.
- prototype77/frontend66파일539/포맷·전체build/자산격리·실제 파일/BOM/CRLF·행↔경로·5만행 취소/재실행·390/1440폭 통과. 기존 ERP 비동기시험1회실패→전체재실행통과(미수정). 파서Node5만626.79ms/heap+126.13MiB/RSS+182.73MiB, browser/GPU/peak 제외. 다운로드 이벤트만료·다운로드재열기/30초만료/stale강제주입/실장비/계측/DB/운영배포 미검증.
- 다음: 결과 확인 뒤 CAD-13 공구·소재·원점/목표 STEP 정합, CAD-14 시간/소비, CAD-15 품질우선제안. CAD-13~17 자동 착수 없음. 컨트롤러 실제 모델 미정, 현재부분집합을 실제 장비 호환으로 오인하지 않도록 유지한다.
- 재현: Node24 PATH 적용; npm --prefix prototypes/cad-cam test; npm --prefix prototypes/cad-cam run format:check; npm --prefix frontend test; npm --prefix frontend run build; node --expose-gc prototypes/cad-cam/experiments/nc-benchmark.mjs. 예제 examples/cnc_CAD12_2026-10-07_milling.ngc, 검증 PNG/benchmarkJSON은 docs/agent/assets/cad-12. 로컬5243/8043 합성fixture, 운영 아님. work/tmp 파일에 의존하지 않는다.

## CAD-11 편집 복구 완료 (2026-10-07)

- branch codex/soap-cad-review, 구현6d4d8d3·HR 급여aaee3a3 보존 병합9a5c0a3. 문서2b6086c까지 로컬 main fast-forward·origin/main push 성공(b2390b7→2b6086c). 최종 인계 commit은 git log -1. 기존 사용자 main push 승인 유지, 운영 배포 없음. [계약](../modules/cad-cam/편집명령_복구_설계_CAD-11.md)·[검증](편집명령_복구_CAD-11.md).
- 3축 밀링/G-code 우선·선반 후속 사용자 확정. E1/E2 키·초안/확정/nativeundo 분리, 점/원호/닫기/드래그·치수 복구, Esc취소, 참조 목록·삭제 보호. 저장은 확정 모델만. E2 취소Worker인스턴스 방어. JSON/DB/비누권한 정책 변경 없음.
- 실제 prototype62/프런트66파일538/포맷/전체build·자산격리·웹키입력/드래그·형상체적/삭제 복구 통과. Windows/IME기기·30초만료/stale주입·저장재열기·전수도구·DB/NC/실물/계측/운영배포 미검증. 기본커널약23MB/chunk 경고 유지.
- 다음: 결과 확인 뒤 CAD-12 G-code 부분집합/모달상태/원본행/경로/미지원차단·취소상한. 컨트롤러 모델 미정, 전체 NC 분석/장비 실행 보장하지 않는다. CAD-13~17 자동 착수 금지. 다른 작업자 main HR schema 미커밋 수정은 보존한다.
- 재현: PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm --prefix prototypes/cad-cam test; npm --prefix prototypes/cad-cam run format:check; npm --prefix frontend test; npm --prefix frontend run build. 로컬5243/8043 합성 관리자 fixture, 실제 운영 아님. 증거 PNG는 docs/agent/assets/cad-11, work 임시파일에 의존하지 않는다.

## W1b-3 HR 급여 완료 (2026-10-07)

- branch main. 끝난 것: 급여 항목·사원 기준·고정 수당·상여 규칙(H-10), 계산 → 검토 → 확정(H-11), 급여대장·명세서·퇴직금 추계(H-12), ERP용 `payroll_runs(month)`. HR OpenAPI 경로 36개.
- 새 파일 backend/src/fs/hr/payroll.py, backend/tests/test_hr_payroll.py, frontend/src/hr/{PayStandards,Payroll,Payslips}.tsx, frontend/src/hr/payroll.test.tsx. 수정: hr/{schema,router,interface}.py, frontend/src/shared/hooks.tsx(`fieldErrors`가 `body.` 접두사 제거), hr/{index,HrLayout}.tsx.
- 주의점: 계산 입력은 그 달의 **확정 근태 마감**이다. 공제는 `calc_kind='RATE'`만이고 과세 지급 합계에만 건다(DB CHECK가 `item_kind='DEDUCTION' = (calc_kind='RATE')`). `rate`는 계산 방식에 따라 뜻이 다르다 — 연장·야간·휴일은 배수(1.5), 공제는 퍼센트(4.5). 작성 중 실행을 다시 계산하면 같은 버전을 **지우고 다시 만든다**(id가 바뀐다). 확정 후 재계산만 새 버전이다. 퇴직금 추계와 ERP 합계는 저장하지 않는 조회 계산이다.
- 재현: `set -a && . ./.env && set +a`; `cd backend && TEST_DATABASE_URL="postgresql+psycopg://factory_studio:$POSTGRES_PASSWORD@127.0.0.1:$POSTGRES_PORT/factory_studio_ci_test" .venv/bin/python -m pytest tests/test_hr_payroll.py -q`; `npx --prefix frontend vitest run src/hr`. 로컬 미리보기는 .claude/launch.json의 backend(8000)·frontend(5173) — uvicorn에 --reload가 없어서 백엔드를 고치면 preview를 다시 띄워야 한다.
- 미실행: 전체 pytest 일괄 실행, 운영 배포(운영은 아직 `3474942`). 다음: W1b-4 평가·현황·본인(H-01·H-13~15) + `monthly_summary`·`pending_tasks`·`lookup`, 그 뒤 W1c 시드·도움말.

## CAD-10 NC·소비·편집 고도화 분석 (2026-10-07)

- branch codex/soap-cad-review, 시작9b54a29에 HR3596156 fast-forward 보존. 최종 commit은 git log -1. [상세 분석](../modules/cad-cam/NC에너지_편집고도화_분석_CAD-10.md), 이번은 문서만·제품 구현0%, 분석100%. main push 기존 승인 유지, 운영 배포 없음.
- NC=경로/기계 상태 명령, CAD 이력 원본과 분리. 초기 3축 밀링·한 컨트롤러 부분집합 제안, 미지원 의미 명령은 전체 시간/kWh/최적화 차단. 공구/소재/초기XYZ/원점·장비 전력/실측 필요, G1을 곧바로 접촉으로 취급하지 않는다. CAD-09 방문 재배열을 외부 NC에 적용하지 않는다.
- E1 확정 모델 CtrlZ는 있지만 그리는 중 점 이력 없음, E2 undo 버튼은 있지만 keydown 없음. 공통 명령·draft와 확정 undo·필드 native undo 분리부터 제안. STEP import API는 설치된 replicad에 있으나 제품 연결/실증 미착수.
- 검증은 공식 문서/코드 조사·문서 링크/표/diff 검사, 신규 기능 시험·계측/DB/배포 미실행. 다음: 컨트롤러 질문 답변과 전체 구현 계약 확인 후 CAD-11 한 ID. CAD-12~17 자동 착수 금지. 재현: rg -n 'keydown|undo|redo' prototypes/cad-cam/src/{main,part-editor}.js; 분석 문서 출처 직접 확인. 다른 작업자의 HR 진행은 보존한다.

## W1b-2 HR 근태·휴가 완료 (2026-10-07)

- branch main. 끝난 것: 근태 자동 생성·예외 수정(H-07), 월 마감 draft→확정→재마감 새 버전(H-08), 연차 발생·잔여 계산·신청·부서장 승인/반려/취소(H-09). 승인하면 마감하지 않은 달의 해당 날짜 근태가 LEAVE/HALF_LEAVE가 된다. HR OpenAPI 경로 23개.
- 새 파일 backend/src/fs/hr/{attendance,leave}.py, frontend/src/hr/{Attendance,AttendanceCloses,Leaves}.tsx, backend/tests/test_hr_attendance.py, frontend/src/hr/attendance.test.tsx. 수정: hr/{schema,router}.py, fs/core/service.py(게스트 정리에 core.holiday), backend/tests/conftest.py(같은 이유), hr/{index,HrLayout}.tsx.
- 주의점: 월 잠금 판정은 `hr.attendance_close`의 **월별 마지막 버전**만 본다(확정만 보면 재마감해도 안 열린다). 근태 수정은 항상 `source=MANUAL`로 바꾼다. 휴가 승인은 `is_head` 직책 재직 사원만, 본인 승인 불가, 잔여는 `FOR UPDATE`로 재확인. `core.holiday`는 등록 화면이 없어 W1c 시드 전에는 비어 있다(공휴일이 휴무로 안 잡힘).
- 재현: `set -a && . ./.env && set +a`; `cd backend && TEST_DATABASE_URL="postgresql+psycopg://factory_studio:$POSTGRES_PASSWORD@127.0.0.1:$POSTGRES_PORT/factory_studio_ci_test" .venv/bin/python -m pytest tests/test_hr_attendance.py tests/test_hr_master.py -q`; `npx --prefix frontend vitest run src/hr`; `ruff check --config backend/pyproject.toml backend`. 로컬 미리보기는 .claude/launch.json의 backend(8000)·frontend(5173).
- 미실행: 전체 pytest 일괄 실행, 운영 배포(운영은 아직 `3474942`). 다음: W1b-3 급여(H-10~12), 그 뒤 W1b-4·W1c.

## CAD-09 품질 우선 경로 제안 (2026-10-07 완료)

- branch codex/soap-cad-review, 구현b10d157·HR1136611 보존 병합6f91b4c. 최신 기록commit은 git log -1. 기존 사용자 main push 승인으로 e17fef8까지 로컬 main fast-forward·origin/main push 성공(1136611→e17fef8). 다음 HR 근태/휴가 미추적 파일 보존. 다른 작업자 변경은 스테이징하지 않는다.
- E1 상면 포켓 순서 후보2개·256래스터 상한, 절삭/방향/깊이/실제 마지막 마무리/경계·안전Z·같은격자 보존, 기존보다 개선되면 제안. 선택 적용만 경로 변경, 입력 변경 후보 무효화, Worker30초/수동취소·revision/종료 Worker 응답 방어. 장비 미정 kWh/전력절감% 없음. [검증 보고](품질우선_경로제안_CAD-09.md).
- 실제 prototype56/frontend530(64파일)/전체build·자산 분리·포맷·웹 적용/100%·기존진행률/무효화·상한·수동취소/복구 확인. 실제30초만료/stale강제주입·Ra/실물/전력·DB명령 미검증. 운영 배포 없음. 다음은 결과 확인 뒤 장비/목표품질 입력 설계. E3 자동 시작 안 함.
- 재현 PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm --prefix prototypes/cad-cam test; npm --prefix prototypes/cad-cam run format:check; npm --prefix frontend test; npm --prefix frontend run build. 로컬5243/8043 합성 관리자 preview만 검증, 운영관리자200은 이전 CAD-08도 미검증. 보호 비누 파일은 빌드시 backend/private-assets/soap-poc에 생성하며 Git에 넣지 않는다.

## CAD-08 운영 비누 파일 복구·경로 제안 분석 (2026-10-07)

- branch codex/soap-cad-review, 시작8a10ea6. deploy.sh 비공개 업로드 누락 수정: 필수 로컬 자산/서버 실행계정 읽기 검사, 보호 폴더 전송·750/640, 공개경로 추가 없음. 가짜 도구 계약7·기존 보호 API13 통과, 전체 실배포 스크립트 미실행. 구현 ee5c499 로컬 main fast-forward 및 origin/main push 성공(8a10ea6→ee5c499). 최종 기록commit은 git log -1, main의 진행 중 HR 파일 보존.
- 운영은3474942. 같은 커밋의 별도 archive 빌드로 private38파일만 복구, 전체 경로/내용해시 일치·factory 읽기·비로그인401 확인. 관리자 브라우저200은 세션 없어 미검증. E2/코드/DB 배포·API 재시작 안 함. work/cad08-server-build는 재현 가능한 임시 빌드이며 인계 의존 대상 아님.
- 품질1·소비2 [설계초안](../modules/cad-cam/품질우선_경로제안_설계초안_CAD-08.md), 제품 구현 미착수. 재질/장비/목표품질 질문 답변 전 미정. 기존 E1의 절삭/방향/마무리·안전Z를 유지하며 래스터 방문만 조정하는 초기 제안. 장비 미정은 실제kWh/%를 표시하지 않음. 다음은 사용자 확인 뒤 경로 제안 구현, E3는 자동 시작 안 함.
- 재현: python3 tools/test_deploy.py; bash -n tools/deploy.sh; backend .venv/bin/python -m pytest tests/test_cad_private_assets.py -q. main 미추적 backend/src/fs/hr는 다른 작업자 진행 중이므로 건드리지 않는다.

## CAD-07 E2 완료 (2026-10-07)

- branch codex/soap-cad-review, 시작3f6b244. WIP0377787·포털/입력7ed2817, main W0-5 e135f79 보존 병합b7edf18. 최신 원격 d135d7f(HR/운영 기록)를384e206으로 병합 보존. 로컬 main fast-forward 및 origin/main push 성공(d135d7f→384e206), 최종 기록 commit은 git log -1. 기존 사용자 main push 승인, E2 운영 배포 없음. main prototype node_modules 없이 frontend 단독 의존성 설치/전체 build·자산 분리 재검증 통과, lock 변경 없음.
- E2 OCCT1.1.0 단일 부품·기준3평면·다중 돌출·측면 구멍·배열/미러·필렛/쉘·제한된 점/원호 구속. 포털 view=part. JSON v3 별도 scope 키, legacy base/cut 변환. 형상 실패에 마지막 정상 원본/표시 유지, 30초 종료/수동 취소. [보고](부품설계_편집기_CAD-07.md).
- prototype50/frontend525/API13·포맷·단독/전체 build·자산 분리, 실제 합성 관리자 브라우저 치수/구속/오류/undo/redo/복원/STEP 생성·1440/390폭 통과. DB/실물/NC/외부 STEP 읽기·브라우저 파일 다운로드/재열기·취소/타임아웃 실사용 미검증. E1 CAM 전용이며 E2를 평면 CAM으로 자동 변환하지 않음.
- 재현 Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; prototype npm ci && npm test && npm run build; frontend npm ci && npm run build && npm test; backend .venv/bin/python -m pytest tests/test_cad_private_assets.py -q. frontend 단독 설치 빌드 alias (?url regex) 유지. licenses를 public cad-cam-app/licenses로 복사. WASM22,980KB·gzip7316KB 별도 Worker 최초 진입만.
- 예제 prototypes/cad-cam/examples/cnc_E2_2026-10-06_{bracket,shell-fillet}.part.json. 기존 비누 연구노트·파일 참조 유지, 사진 업로드 없음. 5243/8043은 worktree 모의 세션 fixture(운영 아님). 기존 개발 의존성 source-map-js audit high1 별도 대응. 다음 E3는 사용자의 이번 결과 확인 후, 다른 솔루션 역할은 D82 유지.

## CAD-06 E1 완료 (2026-10-06)

- branch codex/soap-cad-review, 기준 c663114, 구현09286e4·W0-4 be91ce9 병합4c87b7c. 로컬 main fast-forward 및 origin/main push 성공(be91ce9→4c87b7c). WASM ?url 경로 alias 보정057100d, frontend 의존성만 설치된 main CAD 빌드/자산 분리 재검증 통과. 최종 기록 커밋은 git log -1. 기존 사용자 main push 승인, 다른 작업자 변경 보존, 운영 배포 없음.
- 선 연결·3점 원호(닫는 직선 포함)·회전 슬롯·좌표 치수·끝점/격자 스냅·JSON v2/v1 읽기·Manifold offset Worker·안전 높이 분리 이동. 단일 XY 영역/돌출·상면 포켓. 섬 편집/구속 해석/다중 돌출/필렛/STEP/NC 미구현.
- prototype37/frontend524/관리자 권한API13/build·공개/관리자 자산 분리 통과. 실제 브라우저 직접 윤곽·치수 편집·가공·되감기·오류 거부·390/1440폭 확인. 예제 JSON: prototypes/cad-cam/examples/cnc_E1_2026-10-06_L-slot-arc.form.json. [상세](자유스케치_편집기_CAD-06.md).
- 재현: Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; prototypes/cad-cam에서 npm ci && npm test; frontend에서 npm ci && npm run build && npm test. frontend/prototype 각각 manifold3.5.4 런타임 의존성·빌드 alias 포함. 브라우저 WASM worker 실행 확인, node:module externalized 빌드 경고는 Node 분기용.
- CAD 로컬 서버는 worktree frontend5243/backend8043 합성 인증 fixture. DB·실물·NC 미검증. IAB Blob 다운로드 이벤트 timeout으로 실파일 다운로드/선택 재열기 검증 미완료(순수 JSON 왕복 통과). 기존 개발 source-map-js1.2.1 audit high1 별도 대응 필요.
- 다음: 사용자 이번 결과 확인 후 CAD-07/E2. 비누 심화는 창업 후속 때. 연구노트는 기존 관리자 기록/폴더·파일명만 유지, 사진 업로드 없음.

## CAD-05 CNC E0 완료 (2026-10-06)

- branch codex/soap-cad-review, 구현 ba00b69 로컬 main 병합 및 origin/main push 성공. 최종 기록 커밋 git log -1. 사용자 main push 승인, 운영 배포 없음. CNC 우선·비누 심화 후속·사진 없이 폴더/파일명 기록 확정.
- experiments/cnc-offset-e0.mjs: L자/섬/좁은목/과대공구 offset·영역 분리·독립 여유10908표본·안전Z·돌출 검사 통과. Node24 실증, 브라우저 커널 성능/전체 제거·NC·장비 미검증.
- 연구노트 폴더/파일명 입력/JSON 유지·구 백업 호환. 사용자 방향과 현재ZIP 경로를 합성 관리자 브라우저에 실제 기록. 파일 생성·존재 확인 기능 아님.
- prototype32/빌드·자산 분리 통과. 재현 prototype npm run cnc:experiment && npm test; frontend(Node24) npm run build. 재실증 출력 work/cnc-e0, 커밋 기준자료 docs/agent/assets/cnc-e0는 자동 덮어쓰기 금지.
- [보고](CNC_윤곽커널실증_CAD-05.md). 다음 CAD-06 자유 스케치·JSON v2·CNC worker 연결, AGENTS.md 작업ID별 결과 확인 후. 다른 솔루션 업무/DB 미변경.

## CAD-04 완료 (2026-10-06)

- branch codex/soap-cad-review, 구현 11131e8, 최신 main8df92c4(W0-2/CI) 병합 보존. 최종 커밋은 git log -1. 사용자 관리자 웹 연구노트 확인; 기존 보호 API 안에서 research-notebook.html과 research-history.json을 제공.
- POC01→03 회고/파일 해시·추가 노트 scope별 브라우저 저장·JSON 백업/복원. 미실행 값을 창작하지 않음. 기록은 전자서명/서버 동기화/사진 업로드 없음.
- 검증 prototype29/API13, frontend build·공개자산 분리, 실제 브라우저 저장/JSON 다운로드·복원과 HTTP401/403/200 통과. 실제 DB/실물/커널 후보 실증은 미실행.
- 재현: prototype npm test, frontend(Node24) npm run build, backend uv run pytest tests/test_cad_private_assets.py -q. 5243/8043 합성 로그인 검토 서버는 기존 실행 유지. 연구노트는 비누 POC 안 링크.
- 다음: docs/modules/cad-cam/편집기_고도화분석_CAD-04.md 전체 방향 확인 후 E0커널 실증. 고도화 제품 구현 미착수. 다른 작업자 W0-2/CI 변경을 병합하여 보존, 원격 push/배포 없음.

## CAD-03 완료 (2026-10-06)

- branch `codex/soap-cad-review`, WIP d11471e, main ec1b373 병합 8dce56d. 구현/검증 160b9b0 로컬 main 통합 완료. 최종 기록 커밋은 `git log -1`. 최신 POC-03(유연 외피9부품)이 v2를 대체한다. 사용자 이번 요청만 수행, D82 다른 업무 중단 유지.
- frontend524/prototype27/API13 및 빌드 통과. 실제 브라우저 관리자 모델/서랍 분리/다운로드 검증. [결과](CAD_CAM_관리자POC_CAD-03.md). 실물·탄성·실제 DB 인증·운영 배포 미검증.
- 재현: `cd frontend && npm run build` (Node24), `cd prototypes/cad-cam && npm run poc:flex && npm test`, `uv run --directory backend pytest tests/test_cad_private_assets.py`.
- 5243/8043은 합성 인증+실제 보호 라우터의 검토 환경. 실행법은 docs/modules/cad-cam/README.md. 테스트 fixture를 운영에 실행하지 않는다.
- 보호 자료 backend/private-assets는 빌드 생성물. 공개 정적 경로로 노출 금지, 운영 배포시 오래된 public soap 파일도 교체. 원격 push·배포 없음.
- main의 backend/pyproject.toml·seed/copy.py·tests/conftest.py·uv.lock은 다른 작업자의 진행 중 변경으로 보존. 다음은 사용자 검토 후 재료/결합 방식·실물 시험.

## Codex 최신 상태 — 2026-10-05 CAD-02 포털 통합 완료

- branch `codex/soap-cad-review`, worktree `/Users/hwang-kyoungho/.codex/worktrees/soap-cad-review/factory-studio`. POC 커밋1a364f7, 최종 통합 커밋 `git log -1`; main의 DSN-29 기준표까지 병합 보존.
- 사용자 요청으로 앱 런처 바로 오른쪽 CAD·CAM, `/cad-cam` 로그인 경계, 편집기/POC 내장. [설계/실행](../modules/cad-cam/README.md) · [검증](CAD_CAM_포털통합_CAD-02.md).
- frontend521+최종 관련3, prototype13, build/lint/format 통과. 실제 브라우저 모의 게스트→CAM100%→POC STL→설계 복귀 확인. 실제 인증·운영·실물은 미검증.
- Node24 `cd frontend && npm ci && npm run build` 또는 `npm run dev`. prebuild/predev가 CAD 원본을 public/cad-cam-app에 생성하므로 별도5241 서버 불필요. CAD 소스 수정시 `npm run cad:build` 필요.
- 검토 중인5242 서버는8042 모의 API 연결이며 실제 업무 환경이 아니다. fixture 실행법은 공통 설계. 별도5241 POC 서버도 남아 있다.
- 다음: 사용자 검토 후 배포 또는 FDM 실험. 로컬 main 반영, 원격 push·배포 없음. ROADMAP-02 다른 솔루션 개발 재개 아님. 생성 public 자산·.env/work/원본 PDF는 커밋 제외.

## Codex 최신 상태 — 2026-10-05 POC-01 완료

- worktree `/Users/hwang-kyoungho/.codex/worktrees/soap-cad-review/factory-studio`, branch `codex/soap-cad-review`. 시작 ff5988d, 최종 커밋 `git log -1`.
- 일반 FDM 디지털 시험편: 판3종+트레이 STL, Manifold 생성기, soap-poc.html 검토 화면, ZIP/출력 안내/측정표. [보고](비누그라인더_POC-01.md).
- test13/build/format 통과, 실제 브라우저 조립/교체/ZIP 검증. 실물과 슬라이서 미실행. 웹에서 치수 변경은 아직 안 되며 생성 소스로 수정.
- 재현 `cd prototypes/cad-cam && npm ci && npm run poc:build && npm test && npm run build`; `npm run dev` localhost5241/soap-poc.html. 현재5241 서버 재사용. ZIP `python3 tools/package-soap-poc.py`.
- 다음: 사용자 검토 후 출력 프로파일 적용/실물 A/B/C 시험. 회전 본체·양산·포털 통합 미착수, ROADMAP-02 유지. PDF 원본/개인정보·.env/work 미포함. push 없음.

## Codex 최신 상태 — 2026-10-05 CAD-01 웹 CAD·CAM 시제품

- 위치 `/Users/hwang-kyoungho/.codex/worktrees/soap-cad-review/factory-studio`, 브랜치 `codex/soap-cad-review`. 시작 `a4baf30`, 검토 `ebfb787`, 구현 WIP `33c3f22`. 최종 문서/검증 커밋은 `git log -1 --oneline`로 확인한다.
- 사용자 의도: 직접 설계·가공하는 웹 프로그램. 아래 CAD-00의 제품 기구 선택 질문/답변 대기는 철회됐다. CAD-01 독립 검토 시제품을 제공한다.
- 구현 완료: `prototypes/cad-cam/` 스케치·돌출·파내기·치수/이력·JSON/STL·2.5D 공구 경로·worker 소재 제거. 상세 [검증 보고](CAD_CAM_편집기_CAD-01.md), 실행은 해당 폴더 README.
- 검증: 수학/형상/worker9 통과, 실제 브라우저 드래그·입력→3D→CAM·재생/되감기·과대 공구·JSON 왕복·STL 파일 확인. 화면1440/390 가로 넘침0. Safari/실기기/장비/정밀 CAD 호환/DB 명령 미실행.
- 재현: `cd prototypes/cad-cam && npm ci && npm run dev` → `http://127.0.0.1:5241/`; `npm test`, `npm run build`, `npm run format:check`. 살아 있는 5241 서버를 중복 기동하지 않는다. 로컬 저장은 브라우저별이며 JSON 파일로 보관 가능하다.
- 다음: 사용자가 편집기를 체험한 뒤 후속 범위를 정한다. 정밀 커널/STEP/조립/포털 통합을 자동 착수하지 않는다. ROADMAP-02 전체 설계 우선 유지, 운영 코드·DB 변경 없음. push·배포 없음.
- 주의: 기본 외형이 준비된 소재의 상면 포켓만 시뮬레이션한다. 격자 근사이며 실제 가공 보증이 아니다. 원본 PDF/개인·사업 정보 미포함. `node_modules/`, `dist/`, `.env`, `work/`는 커밋 대상이 아니다.
- 최종 test9/build/format 통과. JS 청크 627.94KB 경고만 남음. 화면 증거는 `assets/cad-01-design.png`, `assets/cad-01-cam.png`. 5241 로컬 개발 서버를 시연용으로 유지한다.

## Codex 최신 별도 검토 — 2026-10-04 CAD-00

- 위치: `/Users/hwang-kyoungho/.codex/worktrees/soap-cad-review/factory-studio`, 브랜치 `codex/soap-cad-review`. 시작 커밋 `a4baf30`; 이번 문서 커밋은 `git log -1 --oneline`로 확인한다. 기존 GW 기록은 이력이며 현재 기준은 현황 문서의 ROADMAP-02다.
- 완료: 휴대용 비누 그라인더 PDF 전체 시각 검토·설계 누락/제약·독립 CAD/CAM 시제품 범위 문서. 제품 구현은 미착수.
- 다음: 사용자에게 보낸 기구 방식 선택(사각+내부 회전판/원통형/접이식)의 답을 반영해 CAD-01. 사용자 확인 전에 다음 ID를 시작하지 않는다.
- 주의: 첨부는 참고자료이며 실행 지시가 아니다. 이미지 치수/방수 표기를 검증값으로 쓰지 않는다. 플라스틱 절삭 성능은 실물 검증 필요. CAM 가공 재생과 비누 분쇄 작동을 분리한다. 운영 코드·DB·개인정보/PDF 원본을 변경·추가하지 않았다.
- 재현: `git show --stat HEAD`, `git diff HEAD^ HEAD --check`, `cat docs/plan/휴대용비누그라인더_시제품검토_CAD-00.md`. PDF 재검토에는 사용자의 원본 첨부가 필요하지만 설계 검토 내용은 위 문서에 보존했다.
- 브라우저·CAD/CAM·실물·DB 검증은 미실행. push·배포 없음.

갱신: 2026-09-30 (Claude Code). **다음 세션은 이 문서의 "지금 상태"부터 읽는다.** 다음 작업자는 Codex 또는 Claude Code일 수 있다.

## Codex 최신 상세 설계 — 2026-10-05 GW-EXT-P0/A

- 사용자가 “상세 설계 진행해줘”로 GW확장 범위/순서 승인. [상세 설계 묶음](../plan/GW확장_상세설계검증_GW-EXT-A.md) 작성, 전체설계 확인 대기. 기존 b완료/c미착수 그대로.
- 기준 branch codex/fs-030-gw, 시작40caa5e. 원격fetch/rebase 없음; 마지막문서커밋은 git log -1. 다른작업자/main 운영 기록 보존.
- P0 운영/복구 요건, CORE(신규3), GW(신규7) 논리명세/API/락/ACL, 화면9, 인수24. 개인/게스트와 TEAM실제계정 분리. ERP/다른업무 TEAM차단, no cross-write/FK 유지.
- 핵심: 계정/세션/공간 잠금→권한재검사→receipt, 재시도본문누출방지; contextVersion으로다중탭오발송차단; token원문receipt저장금지; 실제계정바인딩은대상동의·재바인딩금지. 관리자도본문열람권한없음.
- 미정: 회사규모/배포/SSO·MFA·RPO/RTO/보존. 인증/계정복구·최종GW관리자복구 부속설계는환경확정후. 해당검증전 COMPANY출시불가. B~F 상세설계 미작성.
- 문서 정적검사만 수행, 제품/DB/브라우저/성능/복구검증 없음. schema/Excel/migration 변경 없음. 다음은사용자설계확인→기존c완료→최신main/공식번호조율→A구현단계. push·배포·실데이터반입 없음.

## Codex 최신 설계 — 2026-10-05 GW-EXT-01

- 사용자 기존 GW 제외 범위 확장 요청 및 **실제 회사 도입 목표** 확정. [결정 초안](../plan/GW확장_협업플랫폼_결정초안_GW-EXT-01.md) 작성; 기능 범위/구현은 아직 미승인. 이전 b완료/c미착수 상태 유지.
- 기준 codex/fs-030-gw / 1f96532. 이번 원격 fetch/rebase 없음, 문서만 변경. 마지막 문서 커밋은 git log -1. 기존 main/다른 작업자 기록 보존.
- P0 실제 운영 요건(규모/인증/보존/RPO/RTO/운영자 미정)→A 공유 공간/권한 우선. 전체 c→P0→A→B→C→D→E→F 순서 제안. 실회사 데이터는 별도 운영 환경에서 준비 완료 후만; 공개 체험 반입 금지.
- ERP 직접 교차쓰기 대신 ERP소유 확정 통제, EIP 집계 소유 유지. 공식 번호 충돌 방지 위해 GX01~10 로컬 제안. 전체 모듈/화면 설계 승인 전 schema/코드 변경 금지.
- 검증은 문서 정적검사만. 제품 pytest/Vitest/브라우저/DB/공급자 검증 없음. 사용자 범위 확인 후 상세 설계, 구현 전 최신main/CMMS/번호 조율. push·배포 없음.

## Codex 최신 상태 — 2026-10-04 FS-030b 완료

- 아래 main 운영/Claude 기록은 보존한다. GW의 이전 a/WIP 상태는 이 항목으로 대체한다.
- 위치 `/Users/hwang-kyoungho/projects/factory-studio-codex`, branch `codex/fs-030-gw`. main8531c05 fast-forward 후 구현 WIP2a80375, 구현/검증 160b9b0 로컬 main 통합 완료. 최종 기록 커밋은 `git log -1`. push·배포·main 병합 없음.
- G01~07/API·ERP 조회계약/E11 배지·런처/전환 구현 완료. DB v0.17.0/headfs029b_cmms_module·시드14,687 유지. 교차쓰기 없음.
- 검증: GW20·Vitest518(+마지막 관련11)·tools73·브라우저17 후 업무5 재검사(고유18)·Ruff163·빌드/타입/lint/format·설계/격리/DDL 오류0. 전체pytest839통과/성능1실패(3.426초>2초), 해당 검사 단독1통과. 기준 변경 없음. 실행 상세·미실행·재현: [FS-030b 보고](GW_API화면_FS-030b.md).
- 다음은 **사용자 b 확인 후 c**: GW69행·게스트복사 검증·g01~07 도움말·참고문서·흐름맵·통합. 최신main의 CMMS/시드/head 확인부터. c는 아직 시작하지 않았다.
- 전용DB factory_studio_codex_fs030b_test/full_test/browser_test, 포트8030/5230만 사용. `.env`/`work/` 스테이징 금지. Safari·운영·전체 솔루션 브라우저 미검증.

## 지금 상태 (2026-09-30)

- **운영** https://eip.hugh-d.com — **서버는 main `3474942`(2026-10-06 배포: `tools/deploy.sh` 첫 실행. W0-1 지연 복사 · W0-2 테스트 병렬 · W0-4·W0-5 공통 엔진 · W1a HR DB · CAD-03~06)**. head **`w1a_hr_module`**, schema 0.19.0 / 138테이블, 템플릿 14,688(모듈 행 hr 포함). 확인: 원점·공개 200, 서버 DDL 대조 0, 최근 5xx 0, 게스트 생성 201 → FEMS 에너지원 3건(지연 복사 + 공통 엔진)·MES·ERP 대시보드 200. 배포는 맥북에서 `tools/deploy.sh` 한 줄(사용자 실행 — Claude는 ssh 불가).
- **최근 완료**: FS-025 BEMS(API·화면·시드) · DOC-03/04 참고 문서 4구역(설계 8·따라하기 3·개념 19) · MAP-02 P-03 보기 3종 · 홈 제목 "제조 현장의 올인원 시스템" · FS-027 게스트 별칭 필수·P-07 "게스트 접속"(별칭 90일) · UI-04 앱 안 링크 이동 미저장 보호 · 새 로고·파비콘.
- **마지막 전체 검증**: pytest 727 passed · 1 skipped, vitest 492, 전체 스모크 231 passed(+재실행 167), db:validate·격리 R1~R6 0.
- **FS-026 WMS 확장 main 병합(2026-09-30, Claude)**: Codex `codex/vision-ai` `f65044b`(입고 예정·도착·검수 W-08, 예약·소진 W-09, 3D 트럭 도착, 시드 +22, 도움말)을 main에 병합. 순서 FS-028a(SPC) → FS-026a: schema **v0.14.0 / 103테이블**, 마이그레이션 `fs026a_wms_receiving_reservation`의 down_revision을 `fs028b_spc_module`로 옮김(제약 이름은 분기 때 번호 그대로 — DDL 대조는 구조 비교). 템플릿 11,933(WMS +22, spc 모듈 행 +1), 복사 11,931. `wms-extension.spec.ts`에 FS-027 별칭 입력 추가.
- **배포 방법**: Claude가 `ssh root@158.247.236.136`·`rsync`로 직접 할 수 있다(사용자 허락, 2026-09-29~30). 순서: 프런트 빌드(별도 worktree) → rsync·chown → 서버 `git pull` → 백엔드가 바뀌었으면 `uv sync`·`systemctl restart factory-studio-api` → 시드가 바뀌었으면 `seed.cli template`. 반영 후 외부 curl 확인은 권한 분류기가 막을 때가 있다.
- **주의**: 다른 Claude 세션("EIP 포토폴리오 개발_vN")이 같은 폴더·main을 쓴다 → `git add`는 파일 지정. 스모크는 8000·5173을 쓰며 다른 세션 개발 서버가 막을 수 있다. 스모크 도중 frontend 파일을 고치지 않는다. 로컬 개발 DB는 만료 게스트가 쌓여 `.claude/launch.json`이 `GUEST_LIMIT=1000`으로 띄운다.

### 사용자 결정 (2026-09-30) — 17개 시스템 전체 구현
- 카탈로그 17개를 **모두 구현**한다(제외였던 그룹웨어·RWS 포함). 그룹웨어는 **"GW"**로 표기. 깊이는 **모두 BEMS 수준**(결정서 → 모듈·화면 설계 승인 → a DB / b API·화면 6~7 / c 시드·도움말). 다 만든 뒤에는 기능을 계속 덧붙인다.
- 방식: 큰 틀(로드맵)을 고정하고, 끝난 솔루션은 동결, 남은 것을 **하나씩** 설계·개발한다. 매 세션은 로드맵 + 대상 솔루션 + 이웃 조회 계약만 읽는다.
- 순서(ROADMAP-01 확정): 1 SPC → 2 CMMS → 3 POP → 4 TMS(FS-026 뒤) → 5 PLM → 6 CRM → 7 SCM → 8 ELB/MRO → 9 EIP → 10 GW → 11 RWS.
- **ROADMAP-01 확정(2026-09-30, 제안대로)** — `docs/plan/로드맵_17개시스템_ROADMAP-01.md`·`docs/plan/새솔루션_킷.md`. **지금: FS-028 SPC** — 설계 확정, **FS-028a DB 완료**(v0.13.0, 로컬 head `fs028b_spc_module`, pytest 727). **FS-028b 진행 중**(API `/api/v1/spc`·`fs/spc/interface.py`·MES `operation_runs`·QMS 배지·S-01~07·홈 분야별 묶음). D 다음 D45, AC 다음 AC-185.
- **Codex에 전달**: FS-026은 main에 병합됐다. 다음 작업은 새 main에서 새 브랜치로 시작한다(`codex/vision-ai`는 병합 끝). 게스트 생성 테스트는 `json={"nickname": …}`, e2e는 별칭 입력 필수(FS-027).
- **FS-028 SPC a·b·c 완료(2026-10-01, 로컬 main)** — c: 시드 `_spc`(부분군 456·측정값 2,280·이상 3: LT-0017 미조치 2·LT-0010 지그 조치 1, 공정능력 충분4·주의1·부족1), `seed/validate.py` V13, 템플릿 14,685·복사 14,683(중앙값 0.813초), 도움말 s-01~07·개념 c-20·21, 흐름 맵 `process_control`(18·21), e2e QMS 배지. **남은 것: 운영 반영**(main에 다른 세션의 `cb3fba4 WIP FS-040` 런처 평가가 함께 있다 — 같이 배포할지 사용자 확인) → README "운영 · 동결" → 로드맵 2번 CMMS 결정서(D45·AC-185부터).
- **GW(로드맵 10번)는 Codex가 병행(FS-030, 2026-10-01 사용자 지시)** — 지시서 `docs/agent/Codex_작업지시_GW_FS-030.md`(브랜치 `codex/fs-030-gw`, 번호 범위 D60~69·AC-220~239·화면 G, 스키마 버전은 병합 때 Claude가 정한다). Claude 쪽 CMMS는 D45·AC-185부터.
- **FS-030a GW DB main 병합(2026-10-01, Claude)**: Codex `codex/fs-030-gw` `cd8b619`. 충돌 4곳(시드 합계·진행 기록)만 해결 — 템플릿 14,686·복사 14,684(SPC +2,752 + gw 모듈 행 +1). 임시 버전 `0.15.0-gw` → **v0.16.0**(FS-040이 0.15.0). 검증: db:validate 0·격리 0·tools 69·실제 DB base↔head·DDL 대조 0(112·FK 258)·pytest 관련 72(seed·common·spc·gw_schema·schema_verifier·reviews)·ruff. Codex 다음은 FS-030b(API·화면) — 새 main에서 rebase.
- **지금(Claude): ROADMAP-02 전체 설계 우선** — 개발 중지. 18개(HR 신설 D79) 설계 → DSN-90 → DSN-99 → 일괄 개발. DSN-00·01 완료. **기존 7개 보강 설계 완료(확인 대기): DSN-11 ERP · 12 MES · 13 WMS · 14 QMS · 15 FEMS · 16 BEMS · 17 SPC** — 목표 DB 228테이블. 바코드 스캔(생산·창고)은 POP, 휴일 달력은 core.holiday. 목표 DB 재생성 `python3 tools/rebuild_target.py`(새 DSN 스크립트는 STEPS에). **DSN-21 CMMS 재점검 완료(6→12, 신호 출처 확장 제외) · DSN-22 POP 신규 완료(7테이블, 지연 가져오기) · DSN-23 TMS 신규 완료(10테이블, 조달 운송 포함) · DSN-24 PLM 신규 완료(16테이블, 각 솔루션 가져오기) · DSN-25 CRM 신규 완료(13테이블) · DSN-26 SCM 신규 완료(9테이블, 계획·분석만) · DSN-27 ELB/MRO 신규 완료(11테이블, 발주는 ERP) · DSN-28 EIP 신규 완료(8테이블, 사람 연결은 HR 사원 코드, **포털 첫 화면 = EIP·모듈 키 없음 D80**) · DSN-29 RWS 신규 완료(12테이블, 현장 출동은 CMMS가 가져감) · DSN-30 HR 신규 완료(19테이블, 사람·부서 코드 원천)**. **Claude 신규 설계 끝 · DSN-90 통합 검증 완료**(`docs/plan/통합검증_DSN-90.md` 2장 = 교차 조회 계약 기준본, 목표 DB target-0.19.0). **GW-EXT 병합 완료, D81(사람·조직 원천 = HR), D82(Codex 중단 — 모든 역할 Claude). DSN-99 초안(`docs/plan/개발계획_DSN-99.md`, Q1~Q5 확정 — 단계별 revision·단계마다 배포·GW 실제 도입 별도·antigravity 병행). DSN-31 GW 보강 완료(목표 DB 361테이블, rebuild STEPS …dsn30 → dsn31 → dsn90), DSN-90 7-2 GW 재검증 완료. **설계 작업 끝 · 전체 설계 확인 완료 → 일괄 개발. W0-1 지연 복사 완료(head `w01_lazy_seed`, schema 0.18.0). W0-2 테스트 병렬 완료(`pytest -n auto -m "not perf"` 3분 + `-m perf`). W0-3 배포 스크립트 완료(`tools/deploy.sh` + `tools/test_deploy.py`, 실제 실행은 사용자). W0-4 백엔드 공통 엔진 완료(`fs/common/engine.py`·`master.py`). W0-5 프런트 공통 엔진 완료(`shared/master.tsx`). W1a HR DB 완료(schema 0.19.0/138테이블, head `w1a_hr_module`). W1b-1 HR 기준정보 완료(H-02~06, 화면 15개로 조정). 다음: W1b-2 근태·휴가**. 마이그레이션은 `tools/build_migration.py`로 설계에서 생성한다. 로컬 측정 스크립트 `work/w0/run_pytest*.sh`(DB `factory_studio_fs016_test`, 다른 테스트와 동시 실행 금지), GW는 Codex. 각 문서 6장 "넘길 것"이 입력.

- **FS-040 런처 평가 완료(2026-10-01, 로컬 main, push·배포 안 함)** — `core.app_review`·`/api/v1/core/reviews`·P-02 평점 줄+패널. schema **v0.15.0 / 104테이블**, head **`fs040_app_review`**(down `fs026a`). **FS-028c·GW(FS-030) 병합 때 주의**: 다음 schema 버전은 v0.16.0, 새 마이그레이션 down_revision은 `fs040_app_review`, 새 제약 번호는 C868·R237부터. `validate_db_design`의 작업 집합에 새 작업 ID를 FS-040과 함께 넣는다. 운영 반영 시 `alembic upgrade head`만(시드 변경 없음). 남은 것: p-02 도움말에 평가 안내, e2e.
- 재현: `python3 tools/apply_fs040.py` → `npm run db:validate` → (전용 DB) `alembic upgrade head` → `tools/verify_ddl_matches_schema.py` → `pytest backend/tests/test_reviews.py`.

### 다음 후보 (사용자 결정)
1. Codex FS-026b2 결과 검토 → W-08·W-09 화면·트럭·시드 → main 병합·배포.
2. 브라우저 뒤로·앞으로 가기 미저장 보호(UI-04 한계) — 데이터 라우터 전환이 필요해 비용이 큼.
3. Safari·실기기 확인, 운영 부하 시험(미실행).
4. FS-021 범위 밖 9건(구세대 정리·`statement_timeout` 등) — Codex 영역.

## Git·작업 위치

- 저장소(메인 폴더, Claude Code 전용): `/Users/hwang-kyoungho/projects/factory-studio`
- **Codex는 `/Users/hwang-kyoungho/projects/factory-studio-codex`만 사용**, 브랜치 `codex/*`. 메인 폴더를 열거나 수정하지 않는다. antigravity worktree·브랜치도 건드리지 않는다.
- main·origin: `0addc2e`(FS-019b) 이후 ERP 하위 ID를 순서대로 ff. 매출·채권 생성은 `erp/revenue.py`(019c)에 있고 019d~e가 이어 쓴다.
- Codex의 `codex/fs-019a-erp-master`에는 **이미 main에 통합된 커밋만** 남아 있다(FS-019a는 `5da9019`·`945a78a`, 런처·3D는 `a0f71ae`·`7c83bc7`·`c3f3213`으로 통합). **Codex는 다음 작업을 새 main에서 새 브랜치로 시작**한다.
- `gh` CLI 로그인 완료(go8105). CI는 `gh run list --branch <b>` / `gh run watch <id> --exit-status`.

## 현재 진행

| 영역 | 상태 |
|---|---|
| 포털 | 7/7 + 3D 공장(`/factory`) + **P-02 홈 UI 정돈 통합(`d93b757`, Codex `086f4d7`): 흰 헤더·F 마크·4타일(QMS 포함)·호버/`i` 안내, 하단 WMS·BEMS·SCM 링크 유지** — 제목 "네 시스템", 운영 배포 |
| FEMS | 14/14 (FS-018a~m) |
| MES | 15/15 (FS-020a~g) — `docs/agent/MES_FS-020*.md` |
| ERP | 18/18 (019a 기준정보 E-15~18, 019b 영업 E-02~04, 019c 출하 E-05~06 + 매출·채권 생성, 019d 매출·세금계산서 E-07~08, 019e 채권·수금·소명 E-09~10, 019f 매입·채무·지급 E-11~13, 019g 분개 미리보기 E-14, 019h 대시보드 E-01) — **FS-019 종료** — 계획 `docs/agent/MES_ERP_작업계획_FS-019_020.md` §3, 보고 `docs/agent/ERP_FS-019*.md` |
| FS-021 | 완료 `docs/agent/통합검증_FS-021.md` — 정책 7건 통과, AC-35~80 검증 33·부분 5·미구현 4·폐기 4(나머지는 1차 범위 밖), AC-63 결함 수정, 로컬 실측(동시 생성 지연은 현행 유지) |
| FS-022 | **완료 — https://eip.hugh-d.com**. 이지스 서버 공존(Nginx 443 이름 기반, uvicorn 127.0.0.1:8021, PG18 Docker 55432, Cloudflare 프록시 + Origin CA). 절차·업데이트·걷어내기 `docs/deploy/배포절차_FS-022.md`. 서버 접속: 맥북 `ssh root@158.247.236.136`(키) |
| UI-01 | 완료 `docs/ui/디자인시스템_UI-01.md` — main 통합·서버 배포(2026-09-26). 공통 토큰·`SolutionLayout`(접기·서랍)·넓은 업무 화면·3D 캔버스 확보. 393·10·107 통과 |
| 운영 | 443은 Cloudflare IP만, 이지스는 https://aegis.hugh-d.com(Cloudflare Access)·:8000 외부 차단, 운영자 계정은 `tools/create_member.py`(서버에서 실행), DB는 SSH 터널(§12-5) |
| UI-02 | **완료(A1~A6 전체 37화면 완료)** `docs/ui/공통UI규약_UI-02.md` — A1 대시보드(M-01, E-01), A2 조회 목록(M-09, E-07, E-14, P-07), A3 보고서형 조회(F-03, F-04, F-06, F-07, F-08, E-09·12), A4 FEMS 기준정보(F-09, F-10, F-11, F-13, F-14), A5 MES 기준정보 및 계획(M-02, M-03, M-06, M-08, M-10, M-11, M-12, M-13), A6 ERP 계획·출하·전표·기준정보(E-03, E-05, E-06, E-08, E-10·13, E-11, E-15~18) 완료 (누적 완료 40, 대기 0, Claude 선행 8, 유지 7 = 55), vitest 402 통과 |
| UI-02 검토 | Claude 검토·수정 후 main 통합(`86e729f` 이후 문서 커밋). 회귀 5건 수정·e2e 11건 갱신, 스모크 159 passed |
| QMS | FS-023a DB·023b API·화면(운영 배포) + **FS-023c 시드 113행(`sv-20260927-1`, 템플릿 7,583)·복사 월/번호 재계산·도움말 Q-01~06·흐름 맵 업무 노드(로컬, 미배포)**. 시드 LOT: LT-0017 검사 대기, LT-0015 작성 중, LT-0016 보류 중(+재검사 초안), LT-0008 특채 해제. 교차 조회는 `fs/<솔루션>/interface.py`만(R6) |
| UI-03 | **8화면 전체 완료·운영 배포** — Claude F-12·M-04·M-05·M-07·E-04(`a35e895` 배포), Antigravity B1(M-14·M-15) + B2(E-02 견적) — 브랜치 `antigravity/ui03-b2`, 스모크 171/171 통과. E-02: `FormPanel wide`(등록)·`DetailPanel wide`(상세·라인편집·확정·제출·수주 전환 통합). main 병합 완료 |
| 다음 | **FS-027 게스트 별칭 필수·P-07 게스트 접속(운영 반영). 게스트를 만드는 테스트는 `json={"nickname": …}` 필수.** 운영 `653d438` 반영 완료(2026-09-29, 프런트 de1892c 빌드). 현황 문서 정비 완료. Codex FS-026b2 진행 중. 다른 세션과 같은 폴더를 쓰므로 `git add`는 파일 지정. Codex FS-026b1 검토 완료(충돌 없음) — b2 승인 여부 사용자 결정.** 운영: `6508599`·head `fs025b_bems_module`·템플릿 11,910행(2026-09-29 반영 완료). Codex FS-026a(`521ad76`) 검토 완료: 진행 가능, 조건 = 422→400 규약, digest 날짜 제외, 시드 전 rebase — 운영은 `fs025a_bems`·`fs025b_bems_module` 마이그레이션 + 템플릿 재생성(11,910행) 필요. **Codex FS-026(WMS 확장)** 결정서를 기다린다 — Codex 새 WMS 설계(`fad0c3a`)는 기존 WMS와 겹쳐 병합 금지. FS-025c 완료: 시드 `_bems`(모델과 같은 시뮬레이션), 도움말 b-01~07, 흐름 맵 업무 노드, BEMS 카드 삭제, `CO2_IDLE` −30. 로컬 개발 DB는 만료 게스트 291개로 상한 20에 걸린다(`GUEST_LIMIT`을 올려 띄우거나 만료 공간 정리 필요). FS-025b 완료: API(`/api/v1/bems`, `fs/fems/interface.py`, `fs/bems/simulation.py`, 계약서 16장) + 화면 `frontend/src/bems/` B-01~07·포털 6타일·"여섯 시스템"(화면 설계 6장). 도움말 링크는 아직 404. 수동 명령도 시뮬레이션 시계로 기록한다. 스모크는 `smoke.sh`처럼 Node 24 PATH + fs017 DB URL을 넘긴다. 설계 확정(결정서·모듈·화면 설계 FS-025). FS-025a 완료: schema.json v0.12.0(93테이블), 로컬 head `fs025b_bems_module`(운영 미적용), 로컬 개발 DB·템플릿 반영. 025b: `fs/fems/interface.py` 신규, `/api/v1/bems`, `fs/bems/simulation.py`(모델 상수 한 곳), B-01~07. **로컬 개발 DB도 새 마이그레이션·시드 때 함께 올린다.** Codex는 `codex/vision-ai`(공장 컨셉·CNC) — 마이그레이션 head 겹치지 않게 조율 |

## 다음 할 일

- **운영 반영 완료(2026-09-27, `be87546`)**. Claude Code의 운영 SSH(`ssh root@158.247.236.136`)는 자동 모드 권한 분류기에 막혀 서버 명령은 사용자가 실행했다. 다음 배포도 같은 순서(배포절차 8장 → 시드가 바뀌면 템플릿 → 6장): 서버 pull·API 재시작·프런트 빌드 → **`seed.cli template --date 오늘` 재실행**(배포절차 4-3 아래 "시드가 바뀐 배포"). 마이그레이션 변경 없음(head `fs023b_qms_module` 유지). 운영 게스트로 Q-03에 LT-0017, M-08에 LT-0016 "QMS 보류" 배지 확인.
- `test_qms.py`의 API 테스트는 `qms` fixture가 게스트 QMS 시드를 지우고 시작한다. 시드에 의존하는 검사는 `seeded` fixture를 쓴다.

1. ERP 분담 확정(2026-09-26): **FS-019b~h 전부 Claude Code**(메인 폴더, `fs-019<x>-*`). Codex는 ERP를 하지 않는다.
2. E-G07 결정(2026-09-26): **0원 매출 세금계산서 발급 금지** — 019d에서 구현(409 `ZERO_AMOUNT_SALE`, 발급 대상 목록에서 제외).
0. **UI-02(2026-09-27)**: 브랜치 `ui-02-common-patterns` — 코드 `0875482` 뒤에 문서 커밋, main 통합(OPS `88d584f` 위 rebase). 화면은 대시보드(F-01)·조회 목록(F-02)·목록+패널(F-05) 세 패턴 중 하나로 만든다. `master-grid`는 레거시. Antigravity 작업은 `docs/agent/Antigravity_작업지시_UI-02.md`(기준 커밋 `0875482`이 main에 있어야 시작). 예외 8화면(F-12·M-04·M-05·M-07·M-14·M-15·E-02·E-04)은 Claude가 UI-03에서 대표 구현을 먼저 확정한다. 로컬 검증 스크립트(`work/ui02/*.mjs`, Git 제외)는 5173·8000 개발 서버와 `work/ui02/state.json` 게스트 세션을 쓴다 — 공식 검증은 `e2e/layout.spec.ts`.
3. **UI는 `shared/styles.css` 토큰·공통 클래스만 쓴다(UI-01).** 솔루션 메뉴는 `*Screens` 배열만 고친다. ERP 화면 모양을 FEMS·MES와 맞춘다: 관리 버튼 `link-button`, 등록 폼 select는 `.field` 안 전체 폭. 019b부터 ERP 화면은 `erp/common.tsx`(shared/hooks 위 ERP 접두사)와 `SalesOrders.tsx`의 `LineEditor`를 재사용한다.
4. 후속: (UI-01에서 360px 상단 메뉴 해소) 인라인 폼 미저장 변경 보호. 사용 중 채널 배수 변경 허용 유지 여부(FEMS_FS-018l).
5. **새 업무 테스트는 `guest_space` fixture**, 스모크는 8000·5173·`factory_studio_fs017_test`를 고정 사용하므로 **동시에 한 명만** 돌린다. 사용자가 개발 서버(8000·5173)를 켜 두면 스모크가 멈춘다 — 종료를 요청한다.
6. 판단 기록: MES `/work-orders/{id}/lot` 추가(020c), `/executions/{id}/finish`를 `/result`로 통합(020d), MES 업무 시각 `clock_timestamp()`(020g).

## 재현·주의점

- DB: Claude Code는 `factory_studio_fs016_test`(pytest)·`factory_studio_fs017_test`(스모크), Codex는 `factory_studio_codex_test`만. 같은 DB에 pytest를 동시에 돌리지 않는다.
- Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6. backend 테스트는 `.env` 없이 DATABASE_URL·TEST_DATABASE_URL·PATH·HOME만.
- **ruff는 CI 범위로만**: `ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py` + 같은 범위 `format --check`.
- schema.json·마이그레이션은 작업 ID 범위에서만(이미 적용한 revision 수정 금지). pytest DB는 새 head가 생기면 `alembic upgrade head`를 먼저 돌린다(`test_schema_verifier` 기준선). `test_common.py`·`test_seed.py`는 antigravity 소유, `conftest.py`는 Codex 소유.
- 확정·게시 데이터 불변, 업무 쓰기는 `write_scope` 뒤, 결측(invalid)은 합계에서 제외.
- 30분마다 WIP 커밋, 종료 시 이 문서 갱신·커밋. `.env`·`work/`·`node_modules`는 스테이징하지 않는다. `git push --mirror` 금지.

```sh
cd /Users/hwang-kyoungho/projects/factory-studio
export PATH="/opt/homebrew/opt/node@24/bin:$PWD/backend/.venv/bin:$PATH"
npm --prefix frontend run typecheck && npm --prefix frontend run lint && npm --prefix frontend run format:check
npm --prefix frontend run build && npm --prefix frontend test
# backend: CI 환경 변수 네 개만 전달 (접속 URL은 출력하지 않는다)
env -i HOME="$HOME" PATH="$PATH" DATABASE_URL="$db_url" TEST_DATABASE_URL="$test_db_url" \
  uv run --project backend pytest backend/tests -q
uv run --project backend --env-file .env python tools/run_portal_smoke.py   # 8000·5173 비어 있어야 함
python -m unittest discover -s tools && npm run db:validate && python tools/audit_schema_isolation.py && git diff --check
```

## Codex — FS-019a (2026-09-25)

- 브랜치: `codex/fs-019a-erp-master`, 전용 `factory-studio-codex`만 사용.
- 마지막 커밋: `5ad511d WIP FS-019a`(보존 커밋 d47b8a4를 6bcbe1e 위로 rebase한 결과). 이 절과 최종 결과는 후속 `FS-019a: ERP 기준정보 구현 및 회귀 검증` 커밋에 포함한다. 최신 커밋은 `git log -1`로 확인한다.
- 끝난 것: ERP E-15~18 API·화면·도움말·API 계약, guest_space 기반 ERP 회귀 78개, 프론트 ERP 테스트 20개. MES/ERP 라우트를 모두 보존했고 Home은 세 솔루션 화면 진입으로 변경. Field children 제거, select 직접 렌더링, checkbox inline-check 적용.
- 검증: 최종 frontend 5종(314 tests), CI Ruff 2종, db:validate, audit_schema_isolation, diff --check exit 0. backend 전체 510 passed, 580.736초, exit 0(CI 환경 네 변수만, 전용 DB).
- 다음: 사용자 승인 후 공용 포트/DB 스모크 실행 및 ERP 360px 스크린샷 직접 확인. 아직 실행 승인이 없어 미실행. FS-019a 완료 판정은 이 검증 뒤이며 FS-019b 착수·push·main 병합은 사용자 확인 뒤.
- 주의: pytest DB는 `factory_studio_codex_test`, 스모크는 `factory_studio_fs017_test` + 8000/5173(Claude Code와 공유). 동시 실행 금지. schema.json·마이그레이션·test_common.py·test_seed.py·conftest 변경 없음. 새 의존성 없음.
- 보고서: `docs/agent/ERP_FS-019a.md`(명령·exit·런타임·남은 검증).

```sh
cd /Users/hwang-kyoungho/projects/factory-studio-codex
export PATH="/opt/homebrew/opt/node@24/bin:$PWD/backend/.venv/bin:/opt/homebrew/bin:/usr/bin:/bin"
npm --prefix frontend run typecheck && npm --prefix frontend run lint && npm --prefix frontend run format:check
npm --prefix frontend run build && npm --prefix frontend test
# task_test_url은 factory_studio_codex_test 접속 URL. .env 없이 네 변수만 전달.
env -i HOME="$HOME" PATH="$PATH" DATABASE_URL="$task_test_url" TEST_DATABASE_URL="$task_test_url" uv run --project backend pytest backend/tests -q --durations=15
uv run --project backend ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
uv run --project backend ruff format --check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
npm run db:validate
uv run --project backend python tools/audit_schema_isolation.py
git diff --check
# 스모크는 사용자 승인 후 tools/run_portal_smoke.py 실행.
```

## Codex — P-02 런처 크기 조정 (2026-09-25)

- 브랜치 `codex/fs-019a-erp-master`, 기준 마지막 커밋 `4e2bc74`. 후속 `P-02: 솔루션 런처 아이콘 타일 크기 조정` 커밋에 이 인계 포함(`git log -1`로 확인).
- 끝난 것: 사용자 두 번째 이미지의 작은 아이콘 타일/하단 이름 배치 적용. Home.tsx·Home.css 변경, 기존 색상·동작 보존.
- 검증: Node 24.21.0, frontend typecheck/lint/format:check/build/test(314 passed) 및 diff --check 모두 exit 0.
- 다음: Claude Code가 새 main 통합 뒤 스모크·360px(ERP 및 런처 포함) 직접 검증. Codex는 사용자 지시로 스모크를 실행하지 않는다. 결과에 따른 수정 요청 대기. backend 검증 미실행(UI만 변경).
- 재현: 전용 factory-studio-codex에서 Node 24 PATH 지정 후 `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint`, `npm --prefix frontend run format:check`, `npm --prefix frontend run build`, `npm --prefix frontend test`.
- 메인 폴더 미사용, push·main 병합 없음. .env·work/·node_modules 제외.

## Codex — 3D 공장 둘러보기 (2026-09-26)

- 브랜치 `codex/fs-019a-erp-master`, 마지막 보존 커밋 `5593693 WIP: 3D 공장 둘러보기 구현 보존`(기준 f9eb879). 이 인계·최종 수정은 후속 `3D 공장: 조감도와 3인칭 현장 둘러보기` 커밋에 포함한다. 최종 해시는 `git log -1`.
- 끝난 것: 사용자 승인한 조감도·3인칭 이동, 일반 조립/비전검사/포장 설비 3대·키오스크, 1층 현장사무실 1명·바코드 프린터, 2층 사무실 2명, 현장 순회 1명 + 사용자 캐릭터. `/factory`, 상단 앱 런처 오른쪽 메뉴. 상세 `docs/agent/3D공장_구현.md`.
- Node 24.21.0. 최종 frontend typecheck/lint/format:check/build/test(330 passed) 및 독립 브라우저 7개(20.0초), diff --check 각각 exit 0. 스크린샷 직접 확인. backend·DB·공용 스모크 미실행.
- 새 의존성은 package-lock에 고정. 통합 시 `npm --prefix frontend ci`. three/Fiber/Drei와 @types/three. 공장 화면에만 lazy load. 코드 생성 모델로 외부 모델 자산 없음.
- 재현: 전용 폴더에서 Node 24 PATH를 지정한 후 `npm --prefix frontend run test:factory-browser`. 전용 5186을 시작/종료하며 API는 모두 모의 응답한다. 공용 8000·5173·스모크 DB를 사용하지 않는다.
- 다음: Claude Code가 새 main 통합 뒤 전체 스모크·360px 실행. 사용자는 Codex의 공용 스모크 실행을 금지했으므로 실행하지 않는다. 통합 시 ERP(4e2bc74)·런처(f9eb879)·3D(WIP+후속)의 범위를 구분한다. 수정 요청 대기.
- 메인 폴더·antigravity 미사용. push/main 병합 없음. .env·work/·node_modules 제외. 별도 테스트 서버는 종료한다.

## 2026-09-26 Blender 비전검사 설비 (Codex)

- 사용자 "참고자료 없이 바로 진행" 승인. `codex/factory-vision-blender`에서 기존 공장의 비전검사 1대를 Blender 원본/GLB로 교체.
- 카메라·링 조명·컨베이어·경광등, 6초 검사 주기·5번째 불합격, 상태/수량 패널·가까이 보기·이상 정지/해제·MES 대시보드 진입. 합성 시연이며 업무 데이터에 저장하지 않음.
- Node 24.21.0: frontend typecheck/lint/format:check/build/test(345 passed), 독립 Chromium 브라우저 8개 통과(exit 0). 360px/데스크톱 직접 확인. Blender 5.2.2 GLB 생성 성공.
- DB/API 변경·새 의존성 없음. backend/DB/공용 통합 스모크 미실행. main 병합·push 없음.
- 원본 `assets/blender/vision-cell.blend`, 재생성 `tools/blender/build_vision.py`, 상세 보고 `docs/agent/3D공장_Blender_비전검사.md`.
- 다음: 시각 피드백·통합 담당자 main 통합. MES 실제 레코드 연결 및 FEMS는 후속 설계.

## 2026-09-26 3D 공장 공간 고도화 (Codex, 완료)

- 브랜치 `codex/factory-building`, 기준 `b352514`(비전검사). 사용자 우선순위 진행 및 이어서 진행 승인.
- Blender 건물 외관/내부 전환, 지붕·패널·창문·하역장·공조기·철골·덕트·천장 조명. 조립·포장 설비도 Blender 모델로 교체하고 프레스·실링바 시연.
- 바닥 질감·환경 반사·그림자, 자재 선반/공구대/소방함 및 충돌. MES/ERP/FEMS 기존 화면 진입 카드. 업무 API/DB·실제 데이터 연동 없음.
- Node 24.21.0: typecheck/lint/format:check/build exit 0. 전체 테스트는 자원 경합을 줄인 `npm --prefix frontend test -- --maxWorkers=2`로 346개 통과. 독립 Chromium 브라우저 10개 통과(2.1분, exit 0). 외관/내부/모바일 스크린샷 직접 확인.
- Blender 5.2.2 LTS. 생성 스크립트와 .blend/GLB를 저장. 새 npm 의존성 없음. 상세 `docs/agent/3D공장_공간고도화.md`.
- backend/DB/공용 통합 스모크·Safari/실기기 성능은 미실행. main 병합·push 없음. 다음: 사용자 시각 피드백 및 통합 담당자 main 통합. 최종 커밋은 이 인계를 포함한 `3D 공장: 건물·재질·생산라인 공간 고도화`이며 `git log -1`로 확인.

## Antigravity — UI-02 A1 (2026-09-27)
- 브랜치: `antigravity/ui02-a1` / 기준 커밋: `ed9f438cbbd1f2aacec67a3029304020e3d7865e` (main) / 마지막 커밋: `ce731ab`
- 옮긴 화면: M-01(`frontend/src/mes/Dashboard.tsx`), E-01(`frontend/src/erp/Dashboard.tsx`)
- 내용:
  - 별도 `filter-bar`의 조회 월 입력을 `PageTitle`의 `actions`로 이동
  - 카드 순서·내용 및 2×2 유지, 쿼리 파라미터 및 KPI 보존
  - `frontend/e2e/layout.spec.ts`에 M-01 및 E-01 조회 월 위치 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음

## Antigravity — UI-02 A2 (2026-09-27)
- 브랜치: `antigravity/ui02-a2` / 기준 커밋: `ce731ab` (`antigravity/ui02-a1`) / 마지막 커밋: `26e9ab3`
- 옮긴 화면: M-09(`frontend/src/mes/Receipts.tsx`), E-07(`frontend/src/erp/SalesRecords.tsx`), E-14(`frontend/src/erp/Journal.tsx`), P-07(`frontend/src/portal/Records.tsx`)
- 내용:
  - 각 화면 루트에 `.page-fill` 적용
  - P-07: 상단 탭을 `DataTable`의 `leading` prop으로 전달 (F-02 기준 화면 구조 준수)
  - 안내문 `<p className="muted" role="note">` 규약 정비 및 `Loading delay={300}` 적용
  - P-07의 ADMIN 권한 분기 및 API 계약 보존
  - `frontend/e2e/layout.spec.ts`에 A2 화면들(`.page-fill`) 레이아웃 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음

## Antigravity — UI-02 A3 (2026-09-27)
- 브랜치: `antigravity/ui02-a3` / 기준 커밋: `26e9ab3` (`antigravity/ui02-a2`) / 마지막 커밋: `ad54b6c`
- 대상 화면: F-03(`fems/Allocations.tsx`), F-04(`fems/Emissions.tsx`), F-06(`fems/Intensity.tsx`), F-07(`fems/Targets.tsx`), F-08(`fems/Billing.tsx`), E-09·12(`erp/Receivables.tsx`)
- 내용:
  - `.page-fill`을 쓰지 않고 자연스러운 문서 스크롤 유지 (합계·근거·표 복합 구조)
  - 직접 쓴 표 숫자 열에 `th.num`, `td.num` 클래스 적용 (F-04 배출량·소비량, F-06 원단위·생산량, F-07 달성률·목표·실적, F-08 요금, E-09/12 채권·채무 원금·소명액·잔액)
  - 합계 계산 표시, 계산 근거 펼침(`basis-panel`), 결측 제외 문구, 목표 초과 배지 글자 보존
  - 안내문 `<p className="muted" role="note">` 및 `Loading delay={300}` 공통 규약 정비
  - `frontend/e2e/layout.spec.ts`에 R 패턴 화면들(.page-fill 미사용) 레이아웃 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음

## Antigravity — UI-02 A4 (2026-09-27)
- 브랜치: `antigravity/ui02-a4` / 기준 커밋: `ad54b6c` (`antigravity/ui02-a3`) / 마지막 커밋: `e6c9fd9`
- 대상 화면: F-09(`fems/Sites.tsx`), F-10(`fems/Equipments.tsx`), F-11(`fems/EnergySources.tsx`), F-13(`fems/Factors.tsx`), F-14(`fems/Tariffs.tsx`)
- 내용:
  - 레거시 `master-grid` 제거 및 `.page-fill` + `.split-view` + `FormPanel` + `useDiscardGuard` 표준 S 패턴 전환
  - F-09: 사업장과 공간 2개 섹션 블록 및 공통 FormPanel 적용
  - F-13: DataTable leading 탭 구조 및 FormPanel 통합
  - `frontend/e2e/layout.spec.ts`에 A4 화면들(.page-fill) 및 에너지원 패널 열기/닫기 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음

## Antigravity — UI-02 A5 (2026-09-27)
- 브랜치: `antigravity/ui02-a5` / 기준 커밋: `e6c9fd9` (`antigravity/ui02-a4`)
- 대상 화면 8개:
  - M-02 생산계획: `frontend/src/mes/Plans.tsx` (FormPanel 적용, RevealAnchor 제거)
  - M-03 작업지시: `frontend/src/mes/Orders.tsx` (FormPanel 적용, ?line= 프리셋 패널 자동 열림)
  - M-06 자재 투입: `frontend/src/mes/Materials.tsx` (FormPanel title="자재 투입 등록", inner form 제거)
  - M-08 패킹: `frontend/src/mes/Packing.tsx` (FormPanel 적용, inner form 제거)
  - M-10 사업장·공간: `frontend/src/mes/Sites.tsx` (2개 섹션 블록 + FormPanel S 패턴)
  - M-11 설비: `frontend/src/mes/Equipments.tsx` (FormPanel S 패턴)
  - M-12 품목: `frontend/src/mes/Items.tsx` (FormPanel S 패턴, RevealAnchor 제거)
  - M-13 공정: `frontend/src/mes/Processes.tsx` (FormPanel S 패턴)
- 내용:
  - 모든 컴포넌트에서 React Rules of Hooks 준수: `useDiscardGuard`를 early return (`moduleOff`) 이전에 무조건 호출하도록 구조 정리
  - `FormPanel` 내 중첩 `<form>` 제거로 브라우저 경고 및 파싱 오류 방지
  - `planning.test.tsx`, `master.test.tsx`에서 패널 오픈 버튼 클릭 후 폼 조회하도록 단위 테스트 동기화
  - `frontend/e2e/layout.spec.ts`에 8개 MES 화면 `.page-fill` 검사 및 설비 패널 열기/닫기 E2E 테스트 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음. A6(ERP 계획·출하·전표·기준정보 화면)으로 이어짐

## Antigravity — UI-02 A6 (2026-09-27)
- 브랜치: `antigravity/ui02-a6` / 기준 커밋: `cd0c1d7` (`antigravity/ui02-a5`)
- 대상 화면 10개 (11개 메뉴):
  - E-15~18 기준정보: `frontend/src/erp/Master.tsx` (`Partners.tsx` E-15, `Items.tsx` E-16, `Prices.tsx` E-17, `Accounts.tsx` E-18 공용). `children` prop 지원, `FormPanel` 전환, `Accounts.tsx` split-view + 매핑 이유 aside 패널 결합.
  - E-03 판매계획: `frontend/src/erp/SalesPlans.tsx` (`master-grid` 및 `RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("판매계획 만들기")`).
  - E-05 출하지시: `frontend/src/erp/ShipmentOrders.tsx` (`RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("출하지시 만들기")`, 미출하 취소 동작 유지).
  - E-06 출하: `frontend/src/erp/Shipments.tsx` (`RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("출하 확정")`, 수기 패킹번호 동작 유지).
  - E-08 세금계산서: `frontend/src/erp/TaxInvoices.tsx` (등록·발급 두 폼을 `FormPanel` 모드 전환으로 S 패턴 통합, 0원 매출 발급 방지 및 409 안내 유지).
  - E-10·E-13 수금·지급 등록·소명: `frontend/src/erp/Receipts.tsx` (수금·지급 공용 컴포넌트, `master-grid` 및 `RevealAnchor` 제거, `FormPanel` 등록 전환, 409 LIMIT_EXCEEDED 오류 안내 유지).
  - E-11 매입 전표: `frontend/src/erp/PurchaseInvoices.tsx` (`master-grid` 및 `RevealAnchor` 제거, 등록·취소 두 패널을 `FormPanel` 모드 전환으로 통합).
- 내용:
  - React Rules of Hooks 준수: `useDiscardGuard`를 early return (`moduleOff`) 이전에 호출하여 조건부 훅 오류 원천 차단
  - E2E 및 단위 테스트 최신화: 패널 오픈 버튼 클릭 후 폼을 조회하도록 테스트 보강 (`Prices.test.tsx`, `Partners.test.tsx`, `Items.test.tsx`, `shipping.test.tsx`, `revenue.test.tsx`, `purchases.test.tsx`)
  - `frontend/e2e/layout.spec.ts`에 전체 ERP 화면 `.page-fill` 검사 및 ERP 거래처 등록 패널 열기/닫기 E2E 테스트 추가
  - **Antigravity UI-02 작업 묶음 A1~A6 (총 37개 화면) 전체 완료** (완료 40, 대기 0, Claude 선행 8, 유지 7 = 총 55개 화면).
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음. 사용자 확인 및 Claude 선행 8개 화면(UI-03: F-12, M-04, M-05, M-07, M-14, M-15, E-02, E-04) 진행 대기

## Claude Code — UI-02 검토·main 통합 (2026-09-27)

- Claude 검토(2026-09-27): 공식 스모크를 처음 돌려 11건 실패를 찾았다(Antigravity 묶음 검증에는 스모크 없음). 실제 회귀 5건 수정 — M-06 BOM 제안량 표가 겹침 패널에 가려 채울 수 없음(→ 패널 안으로), M-12 '환산'이 등록 패널을 자동으로 열어 목록을 가림(→ 목록만, 등록은 버튼), E-05·E-06·E-10/13 저장 직후 새 행 선택이 미저장 보호에 막힘(→ 가드 없는 `choose()`), E-18 설명 패널이 표와 겹침(→ main 구조·R 패턴 복원), F-09 인라인 style·정의 없는 `section-block`(→ 공통 `.section-block` 추가). 나머지 6건은 e2e 흐름 갱신. 레이아웃 e2e를 '클래스 존재' → '1440×900 문서 높이'로 강화.
- 검증: typecheck·lint·format:check·build, vitest 402, 스모크 **159 passed**(7.6분, exit 0), 55경로 × 1440·1600·390 전후 비교(가로 넘침·오류 0), S 화면 24개 패널 열기·저장 버튼·Esc(행 선택형 M-06·M-08 포함).
- 통합: `antigravity/ui02-a6` + 검토 커밋(`e8b0d71`·`86e729f`)을 main에 fast-forward. push·서버 배포 전.
- 주의(다음 Antigravity 지시에 반영): 묶음마다 **공식 스모크(`tools/run_portal_smoke.py`)** 를 돌려야 한다. 단위 테스트는 패널 뒤 목록이 가려지는 문제를 잡지 못한다. 기본 e2e 뷰포트 1280px은 패널 겹침 모드다.
- 배포(2026-09-27): origin push `88d584f..0378bf6`, 서버 `git pull --ff-only`(백엔드·마이그레이션 변경 없음 → API 재시작 없음), 맥북 별도 worktree에서 `0378bf6` 프런트 빌드 → rsync. 확인: Cloudflare 경유 200·새 번들 해시 일치·API 5xx 0, 운영 게스트로 F-02·F-05·M-12·E-15 1440×900 문서 900px, F-01 1600 하단 2×2, F-05 패널 열림, 페이지 오류 0.
- UI-03 예외 패턴(2026-09-27, Claude Code): 공통 `DetailPanel`(폼 없는 패널)·`wide`(640px, 1920px 이상 붙음·이하 겹침)를 `SidePanel` 하나로 구현. 기준 화면 — 읽기 전용 상세 M-04, 부모-자식 F-12(채널 상세 ↔ 채널 폼), 넓은 행 편집 E-04(등록·상세·편집), 상태 전이 M-05·M-07(`ResultForm`을 패널로). 규약 8장·적용표(완료 45, Antigravity 대기 3: M-14·M-15·E-02 → 지시서 UI-03 B1·B2).
  - 검증: typecheck·lint·format·build, vitest 402, 대표 화면 5개 × 1920·1600·1440·390 패널 모드·문서 높이·가로 넘침 확인, e2e(layout·fems·mes·portal) 151 passed / 2 failed(F-03 배분 추정·F-01 전월 목표 초과 — 이번에 바꾸지 않은 화면, e2e를 여러 번 돌려 로컬 개발 DB가 바뀐 데이터 의존 실패로 판단). **공식 스모크는 미실행**: 같은 메인 폴더에서 다른 세션(DOC-01)이 동시에 작업 중이라 8000·5173을 점유하는 스모크를 돌리지 않았다.
  - 주의: 이 폴더에서 다른 세션이 동시에 커밋 중(DOC-01 `238a7a0`이 UI-03 WIP 사이에 있음). 스테이징은 경로를 지정한다. push·배포 전.
- UI-03 스모크·배포(2026-09-27): 공식 스모크 **164 passed**(7.7분, exit 0 — 로컬에서 실패하던 F-03·F-01도 통과, 데이터 의존 실패 확인). origin push `6e22e00..a35e895`(DOC-01·DOC-02 포함), 서버 pull(백엔드 변경 없음, API 재시작 없음) → `a35e895` 프런트 빌드·rsync. 확인: 새 번들 해시 일치·200·API 5xx 0, 운영 게스트 1920×1080에서 M-04·F-12·E-04 넓은 패널(640) 붙음, M-05·M-07 패널(380), 문서 1080px, 오류 0.

## Antigravity — UI-03 B1 (2026-09-27)

- 브랜치: `antigravity/ui03-b1` / 기준 커밋: `24179d1`
- 대상 화면 (2개):
  - M-14 공정 경로: `frontend/src/mes/Routes.tsx` (F-12 부모-자식 패턴 적용: 경로 버전 목록 → 단계 목록 `DetailPanel wide` → 단계 폼 `FormPanel`, 게시한 버전 불변, '개정'·'게시' 동작 유지, `RevealAnchor` 제거)
  - M-15 BOM: `frontend/src/mes/Boms.tsx` (BOM 목록 → 자재 라인 `DetailPanel wide` → 라인 폼 `FormPanel`, 게시한 버전 불변, 개정 새 코드 `FormPanel`, `RevealAnchor` 제거)
- 테스트 갱신 및 추가:
  - `src/mes/versions.test.tsx`: BOM 라인 폼 전환에 따른 라벨·버튼 접근자 갱신 (8 tests passed)
  - `e2e/mes.spec.ts`: 공정 경로 개정 흐름 갱신(패널 열림 확인 → 순서 편집 → 저장 → 패널 닫기 후 목록에서 게시)
  - `e2e/layout.spec.ts`: M-14 공정 경로 단계 패널 및 M-15 BOM 자재 패널 1440×900 문서 높이 ≤ 900 및 Esc 닫기 검사 추가
- 검증:
  - `npm --prefix frontend run typecheck`: exit 0
  - `npm --prefix frontend run lint`: exit 0
  - `npm --prefix frontend run format:check`: exit 0
  - `npm --prefix frontend run build`: exit 0
  - `npm --prefix frontend test`: 44개 파일 410개 테스트 통과 (exit 0)
  - `git diff --check`: exit 0
  - `uv run --project backend --env-file .env python tools/run_portal_smoke.py`: 공식 스모크 **166 passed** (8.0분, exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음. 사용자 확인 후 UI-03 B2 (E-02 견적 넓은 행 편집 화면) 진행 대기

## 2026-09-27 1인칭 비전검사 체험 (FS-3D-FP01, Codex 완료)

- 브랜치 `codex/factory-building`, 기준 `d3eaf31`. 사용자 승인한 웹 1인칭 검사 구역 데모 구현.
- `/factory`의 1인칭 체험 진입, 눈높이 이동·드래그 시선·충돌, 직접 클릭/탭·E 선택, 데스크톱 옆 패널/모바일 아래 패널. 작업자 1명·태블릿·안전 구획·조명 보강.
- 상태·판정·검사/합격/불합격 수량·링 조명·시연 설정값. 합성 시뮬레이션이며 실제 업무 API/계측/DB 연결 없음. 실사 품질 인물·재질은 후속 개선 대상.
- Node 24: typecheck/lint/format:check/build exit 0. Vitest 348개/36파일 통과. 기존 Chromium 회귀 10개 통과, 새 1인칭 3개는 최종 분리 실행에서 모두 통과(1.9분). 처음 한 테스트에 선택·이동·스크린샷을 묶어 60초 제한을 초과한 것은 테스트를 분리해 해소. 화면 직접 확인.
- 5186·모의 API만 사용, backend/DB/공용 스모크·실기기 FPS·Safari/WebXR 미검증. main 병합·push·운영 배포 없음.
- 보고서 `docs/agent/3D공장_1인칭_비전검사.md`. 다음: 통합 담당자가 현재 main/UI 변경과 대조해 3D 커밋 반영 여부 확인 후 사용자 체험. 실제 데이터 매핑과 실사 자산은 별도 후속 범위.
- 통합(2026-09-27, Claude Code): Antigravity UI-03 B1(`2cda062`, M-14 공정 경로·M-15 BOM 부모-자식 패턴) fast-forward + Codex 1인칭 비전검사 체험(`2a739c2` → cherry-pick `941a50d`). Codex 브랜치는 UI-01 이전 코드 기준이라 `Factory.tsx`·`Factory.css` 충돌 — main 파일을 기준으로 Codex 변경 13가지(체험 상태·진입/나가기·포커스 가둠·툴바·조준점·E 선택·이동 패드·설비 상태/설정 패널 등)를 다시 적용하고 CSS 블록은 원본과 동일함을 확인. 보정 `bf8c8e9`: 1인칭에서 설비 상세가 UI-01 겹침 규칙 때문에 장면과 6px 겹치던 것 → 옆 칸 배치.
  - 검증: typecheck·lint·format·build, vitest 412, 3D 브라우저 13 passed(1인칭 신규 3 포함), 1인칭 1440·390 설비 선택·상세·Esc 해제 직접 확인, M-14·M-15 넓은 패널 1440 한 화면, 공식 스모크 **169 passed**(9.6분, exit 0).
  - 참고: DOC-02는 직전 배포(`a35e895`)에 포함되어 이미 운영에 반영됨(작성 세션의 현황 기록은 '배포 보류'였음).
- 배포(2026-09-27): push `24179d1..ad199c1`, 서버 pull(백엔드 변경 없음, API 재시작 없음) → 프런트 빌드·rsync. 확인: 새 번들 해시 일치·API 5xx 0, 운영 게스트 M-14·M-15 넓은 패널 1440 한 화면, 1인칭 체험 설비 상세 열림, 오류 0(첫 방문은 3D 모델 내려받기 대기 필요).
- FS-023 QMS 설계(2026-09-27, Claude Code): 사용자 결정 "QMS 먼저, 읽기 전용 조회" 반영. 산출물 — 결정서 `docs/plan/QMS도입_교차조회_결정_FS-023.md`(D8 QMS 구현 편입·출하 전 최종검사, D9 읽기 전용 조회 인터페이스 X1~X6·격리 규칙 R6, D10 보류는 표시만, D11 스냅샷 보관, D12 독립 동작), 모듈 설계 `docs/modules/qms/QMS_모듈설계_FS-023.md`(qms 6테이블 컬럼·제약·UK_PARTIAL, 상태 전이, TX-Q1~Q3, 인터페이스 함수, API, 시드 약 126행, AC-97~110), 화면 설계 `docs/ui/화면설계_QMS_FS-023.md`(Q-01~06, 기존 D·L·S·P·V·W 패턴만 사용, MES M-08·M-04 배지). 문서 정리: 현황 5장 교체, QMS·WMS README의 'core 소유' 표현 정정.
  - 검증: 설계 문서 정적 대조만(schema.json 테이블 수 71 = mes 21·erp 27·fems 13·core 10 확인). schema.json·마이그레이션·Excel·ERD·코드 변경 없음(승인 후 FS-023a). `npm run db:validate` 미실행(메타데이터 미변경).
  - 다음: 사용자 승인(결정서 6장 3문항 + 모듈 설계 13장 3문항) → FS-023a.
- FS-023a QMS DB 반영(2026-09-27, Claude Code): 사용자 승인(D8~D12·범위·순서·발번·기본 월·패킹 무관 보류 모두 권장안). `schema.json` v0.10.0 — qms 6테이블(불량 유형·검사 기준·검사 항목·검사·측정값·품질 보류), `core.workspace_module` module_key에 qms. 적용 스크립트 `tools/apply_fs023a.py`(멱등, 새 제약·관계는 끝에 붙여 기존 C·R 번호 유지). 마이그레이션 `20260927_fs023a_qms_schema.py`(revision `fs023a_qms`, 실행 시 JSON 미참조 고정 SQL, 제약 이름 = C·R 번호). 검증 도구: `audit_schema_isolation.py` BUSINESS에 qms + **R6**(다른 솔루션은 `fs.<B>.interface`만 import, AST 검사), `validate_db_design.py` FS-023a 엔티티 목록(설계서 표)·`validate_qms`, `verify_ddl_matches_schema.py`·Excel·ERD 생성기에 qms. Excel 23시트·ERD `qms.mmd` 재생성.
  - 수치: 77테이블 · 785컬럼 · FK 175 · 제약/정책 587(DB 제약: PK 77·UK 178·CHECK 183·INDEX 46·UNIQUE_INDEX 11, SERVICE 정책 92).
  - 검증: `npm run db:validate` 오류 0, 격리 검사 R1~R6 오류 0, 도구 단위 테스트 49 OK(신규 `test_fs023a.py` 5), pytest DB에서 alembic upgrade head → verify_ddl 오류 0 → downgrade -1 → downgrade base → upgrade head → verify 오류 0, 로컬 개발 DB upgrade·verify 오류 0, backend pytest **648 passed**(13분 45초), ruff check·format 통과.
  - 미실행: 공식 스모크(프런트·API 변경 없음, 스모크는 실행 시 head를 자체 적용), 운영 서버 마이그레이션(배포 전).
  - 주의: 새 공간의 `qms` 모듈 행 생성·게스트 세대 복사/정리 순서에 qms 추가는 FS-023b·c. 현재 qms 테이블은 비어 있어 기존 복사·회수에 영향 없음(pytest로 확인).
  - 다음: FS-023b — `fs/mes/interface.py`·`fs/qms/interface.py`, `/api/v1/qms` API(TX-Q1~Q3), Q-01~06 화면, MES 배지.

## 2026-09-27 비전검사 AI 설명·세 시나리오 (FS-3D-AI01, 로컬 구현)

- 브랜치 `codex/vision-ai`, 기준 `origin/main 8851772`. 기존 `codex/home-ui-polish` 작업은 보존하고 통합된 1인칭 코드에서 시작했다.
- 정상/불합격 증가/정지 전환, 상태등·판정 주기·검사 정지 연동, AI 설명 버튼 구현. 확인된 사실 / 원인 가능성 / 다음 확인 항목을 구분한다. 활성 시나리오 재선택은 누계를 보존한다.
- 고정 합성 비교 자료: 정상 2%→2%, 증가 2%→20%(+18%p), 정지 처리량 100→50개. 실시간 애니메이션 누계·실제 검사 이미지·업무 센서값과 구분한다.
- 인증·CSRF가 필요한 읽기 전용 설명 API, 서버 전용 OpenAI Responses 어댑터, 성공 캐시·동시 호출 제한·실패 대기 구현. 키 미설정/공급자 오류는 출처가 표시된 데모 설명으로 대체한다. DB·스키마·업무 데이터 변경 없음.
- 프런트 420개/46파일, typecheck/lint/format/build 통과. 서버 DB 없는 모의 공급자 테스트 13개, Ruff 검사/포맷 통과. 배포 wheel의 시나리오 JSON 포함 확인.
- 실제 OPENAI_API_KEY가 없어 실제 Astra 호출·응답 품질·계정 접근은 미검증. 공용 DB 스모크·Safari·실기기 성능은 미실행. main 병합·push·운영 배포 없음.
- 남은 통합 작업: 커밋 반영 검토 → 공식 스모크 → 백엔드 재시작·프런트 재빌드. 실제 AI를 활성화할 경우 서버 비밀 설정에 키를 추가하고 세 시나리오 응답 확인. 운영 반영 여부와 무관하게 키 없이 데모 체험 가능.
- 설계 `docs/modules/factory/README.md`, 상세 인계·재현 명령 `docs/agent/3D공장_AI설명_FS-3D-AI01.md`. 이번 범위 구현 완료, 운영 통합과 실제 모델 검증은 남음.

### 최종 검증 (FS-3D-AI01)

- Node 24 typecheck/lint/format:check/build 통과, Vitest **420 passed / 46 files**.
- DB 없는 backend 설명 테스트 **13 passed**, Ruff check/format 통과. wheel에 `fs/factory/scenarios.json` 포함 확인.
- Chromium 기존 회귀 13개 통과. 신규 시나리오·모바일 2개는 최종 분리 실행 **2 passed**. 전체 실행에서는 한 테스트가 접힌 비교 자료의 중복 문구를 찾아 실패했으나, 보이는 설명 문구를 선택하도록 수정한 후 재검증했다. 총 15개 시나리오 검증, 최종 단일 전체 실행은 반복하지 않았다.
- 1440×900 1인칭 설명 화면과 390px 모바일 패널 캡처 직접 확인. 모바일 가로 넘침 없음. 빌드의 기존 3D 청크 크기 경고와 THREE.Clock 사용 중단 예정 경고는 남아 있다.
- 실제 모델 요청과 공용 DB 스모크는 실행하지 않았다. 작업 폴더 `factory-studio-codex`, 브랜치 `codex/vision-ai`. 결과물은 이번 완료 커밋에 포함되며 원격 push/배포는 하지 않았다.

## 2026-09-27 합성 이미지 검사실 (FS-VISION-LAB01)

- 사용자 승인 범위 구현: 정상/이물/조명 변화 샘플, 전체/중앙 ROI, 임계값·최소 연결 면적 조절, 원본/이진화 화면과 검출 영역, OK/NG 및 오검출·미검출·영역 밖 결함 픽셀 수. 레시피·결과 JSON 다운로드.
- `/factory/vision-lab`, 비전검사 설비 상세에서 진입. 브라우저 순수 함수의 요청/결과 v1 계약 분리. OpenCV·C++·C#·실장비·AI 분석은 연결하지 않음. 새 서버·DB·의존성 없음.
- `codex/vision-ai`, 기준 `0f16bb6`에 후속 구현. 프런트 425 tests / 47 files 통과, typecheck/lint/format/build 통과. 모의 API·5186에서 신규 Chromium 진입/조건 변경/JSON 다운로드/모바일 가로 넘침 검사 통과. 공용 DB 스모크·실장비·Safari 미검증.
- 상세 설계·후속 연결 계약·재현 명령: `docs/agent/합성이미지검사실_FS-VISION-LAB01.md`. 이번 합성 범위 완료. 다음은 통합 검토와 사용자 체험이며 C++/C# 엔진은 별도 후속 범위. 원격 push·운영 배포 없음.
- 통합·배포(2026-09-27, Claude Code): main에 FS-023b + UI-03 B2(`d194cb9`) + Codex 비전검사 AI 설명(`0f16bb6`)·합성 이미지 검사실(`da2f02a`) 병합(`2ef0578`). 검증: ruff·격리 R1~R6 0, vitest 435, 백엔드 설명 테스트 13, 공식 스모크 **187 passed**(11.8분). push `8851772..2ef0578`, 서버 pull·`alembic upgrade head`(→ `fs023b_qms_module`)·API 재시작, 프런트 빌드·rsync(번들 `index-aVsvqfGf.js` 일치). 운영 게스트 확인: QMS Q-01~06·MES 패킹·E-02 견적 패널·`/factory/vision-lab` 열림, 페이지 오류 0·5xx 0. OPENAI_API_KEY 미설정 → AI 설명은 데모 응답.

## 2026-09-27 P-02 홈 UI 정돈 (Codex)

- 작업 폴더 `factory-studio-codex`만 사용. 브랜치 `codex/home-ui-polish`, 기준/마지막 이전 커밋 `8851772`(origin/main). 이 인계는 `P-02: Figma 참고 홈 UI 정돈` 커밋에 포함하며 최종 해시는 `git log -1`로 확인한다. 기존 `codex/factory-building`은 그대로 보존.
- 끝난 것: 흰색 홈 헤더·로고, 중앙 본문/배너, 기본 아이콘·이름·분류만 노출, 설명/상태 호버·포커스·터치 안내, 미구현 영역 제거. 현재 공간·도움말·실제 진입·역할 메뉴 유지. 보고서 `docs/agent/홈_UI_정돈.md`.
- 검증: Node 24.21.0 PATH. typecheck/lint/format:check/build/test(418개/45파일) 및 독립 Chromium 8개, diff --check 각각 exit 0. 데스크톱/호버/360px 직접 확인. backend·DB·공용 포털 스모크 미실행.
- 재현: 전용 폴더에서 `export PATH="/opt/homebrew/opt/node@24/bin:/opt/homebrew/bin:/usr/bin:/bin"`, `npm --prefix frontend run test:home-browser`. 5187 포트·모의 API만 사용, 테스트 서버 자동 종료. 공용 8000/5173과 DB는 사용하지 않는다.
- 새 의존성 없음. package.json은 검증 스크립트만 추가. 공통 CSS·업무/3D·스키마 변경 없음. .env/work/node_modules 제외.
- 다음: 사용자 시각 검토 후 통합 담당자가 main에 반영·운영 확인. Codex는 push/main 병합/배포 없이 멈춘다.

## 2026-09-27 연속 검사 모드 (FS-VISION-RUN01 완료)

- 사용자 확인한 연속 검사 범위 구현. `codex/vision-ai`, 기준 `da2f02a`. 기존 3종 20회 반복, 500/200ms, 시작/일시정지/재개/종료, 시작 시 레시피 고정.
- OK/NG/합격률/평균 알고리즘 시간, 샘플별 NG, 누적 오검출·미검출·ROI 밖 픽셀. NG 당시 원본/이진화·좌표·면적 조건 재조회, 실행 기록 JSON 다운로드.
- 비동기 어댑터 경계와 세대별 늦은 응답 폐기, 화면 이탈 정리. 설정 이동/탭 숨김 일시정지. 한 배치 20건 메모리 보관, 새 배치·화면 이탈 시 교체/소멸.
- Node 24: typecheck/lint/format/build 통과, Vitest 431 tests / 48 files. Chromium 기존 합성 검사실 1개 + 신규 배치·JSON/라이프사이클 2개 통과(최종 신규 2개 재실행 통과). 1440·390 캡처 직접 확인, 360·390 가로 넘침 없음.
- 실장비·PLC·C++/C#·backend/DB 스모크·Safari 미검증. 기존 3D 청크·Clock 경고 유지. push/운영 배포 없음.
- 다음: 사용자 체험·통합 검토, 이후 별도 작업으로 가상 PLC 상태 머신. 설계 `docs/modules/factory/README.md`, 상세 계약·재현 `docs/agent/연속검사모드_FS-VISION-RUN01.md`.

## 2026-09-27 가상 PLC 핸드셰이크 (FS-VISION-PLC01 완료)

- 사용자 후속 진행 승인. `codex/vision-ai`, 기준 `74a4ec2`. 연속 검사에 선택형 PLC 모드 추가, Ready/Trigger/Busy/Done/OK·NG/Interlock 신호, 요청 ID별 이벤트 로그.
- 300ms 검사 제한·1000ms 확인 제한, 1회 지연/확인 누락 주입, 수동 확인, 중복 트리거 차단, 결과 래치, 명시적 리셋·새 배치 복구. 타임아웃/취소 후 늦은 응답 무효화.
- PLC 수량은 확인까지 끝난 거래만 반영. 확인 실패 결과는 PLC 진단 스냅샷에 보존하고 NG 수량과 분리. 0건 실패 배치도 신호/알람/로그 JSON 다운로드 가능.
- Node 24 최종 typecheck(빌드 포함)/lint/format/build 통과. Vitest **443 tests / 49 files**. Chromium 관련 5개 통과, 로그 ID·알람 표시 보정 후 신규 PLC 2개 재실행 통과. 1440·390 캡처 직접 확인, 모바일 가로 넘침 없음.
- 브라우저 모의 프로토콜. Ready_Req ON 고정, Recipe_ID=RUN_SNAPSHOT. 실제 PLC·통신 SDK·C++/C#·MES·backend/DB 스모크·Safari 미검증. 기존 3D 청크/Clock 경고 유지. push·운영 배포 없음.
- 다음: 사용자 체험/통합 검토 후 C++ OpenCV 코어 분리 및 동일 입력의 결과 비교. 상세 `docs/agent/가상PLC_FS-VISION-PLC01.md`, 공통 설계 `docs/modules/factory/README.md`.

## 2026-09-27 C++ OpenCV 검사 코어 (FS-VISION-CORE01 완료)

- 사용자 후속 진행 승인. `codex/vision-ai`, 기준 `7ec4519`. `native/inspection_core`에 C++17 정적 라이브러리·CLI·CMake·예제·비교 테스트 구현.
- 기존 요청 v1과 검사실 {request,result} JSON 입력, stdin/파일/NDJSON 지원. 결과 source=synthetic-opencv-cpp-v1. 임계값 `<`, 연결 4/SAUF, 픽셀 면적 `>=`, ROI·영역 순서·정답 평가를 웹과 일치시킴.
- CTest 2개 프로그램 통과(8.72초). 원본 TS 엔진 직접 실행과 19,968개 입력 비교: 불일치 0. C++ 핵심 사례, 입력 타입·범위·JSON 오류, NDJSON 오류 후 복구, 파일 입력 검증 통과. 예제 이물 결과 80/36px²·NG 확인.
- 검증 환경: macOS arm64, Apple Clang 21, CMake 4.4.3(Homebrew로 이번 설치), Node24, OpenCV4.13.0·nlohmann-json3.12.0 소스 빌드. 제3자 소스/빌드/로그는 work/에만 보관. CMake4와 OpenCV 내부 정책 경고는 남으나 최종 빌드·테스트 성공.
- 웹/서버/PLC 패널은 기존 브라우저 엔진 유지. 실행 연결·실영상·C#·Windows/Linux·실장비·배포 미검증/미구현. 프런트 코드를 바꾸지 않아 기존 443개 테스트/브라우저 스모크는 이번에 재실행하지 않음. push·운영 배포 없음.
- 다음: 사용자 체험 후 C# 프로세스/통신 어댑터 또는 웹 서버의 네이티브 호출 연결 범위 확정. 요청 ID·취소·시간 제한·출력 검증 계약 필요.
- 재현: `cmake -S native/inspection_core -B work/inspection-core -DINSPECTION_FETCH_DEPS=ON -DCMAKE_BUILD_TYPE=Release -DNODE_EXECUTABLE=/opt/homebrew/opt/node@24/bin/node`; `cmake --build work/inspection-core --parallel 4`; `ctest --test-dir work/inspection-core --output-on-failure`.
- 상세: `native/inspection_core/README.md`, `docs/agent/C++검사코어_FS-VISION-CORE01.md`.

## 2026-09-27 C++ 웹 호출·사용자 참고 문서 (FS-VISION-CONNECT01 완료)

- 사용자 요청한 C++ 호출 연결과 도움말 반영 완료. `codex/vision-ai`, 기준 `848778b`. 운영 배포는 사용자가 직접 진행하며 이번에 push·main 통합·운영 접속/재시작/배포 없음.
- 인증/CSRF POST /api/v1/factory/vision/inspect, 서버 고정 절대경로 VISION_CORE_EXECUTABLE 실행. 2초·동시4개/프로세스·출력1MiB 제한, 요청/결과 모델 검증, 오류503/429/502/504, 브라우저 대체 없음. C++ --timed 추가(기본 CLI 출력 유지).
- 검사실 C++ 단건/JSON, 연속 검사 엔진 선택, PLC 선택 엔진 호출·취소. 엔진 출처·고정 레시피·요청 ID 연결, 순수 C++ 시간 표시. 클라이언트 취소/늦은 응답 폐기.
- 도움말 사용자 참고 문서/포털에 `portal/vision-lab` 추가, 전체 사용 흐름·설정·20회 배치·PLC 장애/복구·JSON·한계 집필. 검사실 왕복 링크·검색·모바일 확인.
- 최종 검증: 프런트 448 tests/50 files, 타입(빌드)/lint/format/build 통과. DB 없는 서버 27 tests(실제 C++·인증/CSRF·검증·미설정·출력오류/상한·시간제한·동시제한·취소) 통과, Ruff check/format 통과. CTest2개 통과, 웹 비교19,968개 불일치0.
- Chromium 관련6개 최종 단일 실행 통과(1.3분). 모의 인증·실제 API·실제 C++ 바이너리로 단건/20회/PLC20회 및 JSON·도움말 확인. 기존 모의 API 회귀 포함. 실제 화면 캡처 확인, 도움말390px 가로 넘침 없음.
- 공용 DB/운영인증/운영배포·Windows/Linux·실장비 미검증. 기존 3D 청크/Clock 경고와 Python 테스트 클라이언트 사용중단 경고 유지.
- 배포 인계: `docs/agent/C++웹연결_FS-VISION-CONNECT01.md`. 서버 OS에서 바이너리 빌드/검증 → 서비스 환경 VISION_CORE_EXECUTABLE 절대경로 설정 → 백엔드 반영·재시작 → 프런트 재빌드·반영 → 게스트C++/PLC/도움말 확인. tests/factory_native_preview.py는 모의 인증이므로 운영 사용 금지.

## 2026-09-29 Codex FS-026b1 진행 중 (main 내용 유지 후 추가)

- 작업 위치 factory-studio-codex, 브랜치 codex/vision-ai. origin/main `6508599`로 rebase 완료. 이전 HEAD `521ad76`은 `backup/vision-ai-before-fs026b1-20260929` 보존. rebase 직후 HEAD `df6014e`. main의 BEMS 시드 템플릿 11,910 / 복사 11,908행 유지.
- FS-026a 완료: migration head `fs026a_wms_receiving_reservation`, metadata v0.13.0 /98테이블·1022컬럼·225 FK. 기존 migration 변경 없음. 이전 상세 보고 docs/agent/WMS확장_DB_FS-026a.md.
- 현재 b1: receiving.py/receiving_schema.py, 입고 예정/도착/검수/원천 선점 API와 기존 sync 연계, NORMAL/QUARANTINE 마스터 보호, snapshot 날짜만 복사·digest 불변 구현 중. 입력400/멱등422, 신규 처리 시각 DB clock_timestamp 통일.
- 아직 검증 완료 아님. 신규 테스트 실패 수정 중이며 전체 pytest/ruff/격리 감사는 최종 실행 필요. 완료 후 보고를 갱신한다. 실행: 전용 *_test DB에 DATABASE_URL/TEST_DATABASE_URL 설정 후 `backend/.venv/bin/pytest backend/tests --tb=short -q`, `uv run --project backend ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py`, `python3 tools/audit_schema_isolation.py`. 비밀값은 저장/출력하지 않는다.
- 사용자 지정 단계: b1(TX-W4~7/AC140~150) 보고 후 사용자 확인 대기. b2 예약·소진·가용(TX-W8~9/AC151~158)은 아직 시작 금지. 이후 화면/트럭/시드·도움말도 별도. push·배포 미승인.

### FS-026b1 검증 중간 갱신
- 입고 API23개 통과(별도 PG 연결 경합, 전량 부족, 취소/원천변경, 환산/복사/격리, 멱등, 줄 순서 오류 경로, 초안 삭제 뒤 발번 포함). 전량 부족 sync 영수증은 전표가 없으므로 inbound_notice ID로 저장한다.
- 기존 W-03 새 상태 및 검수 전표 이름의 최소 표시 호환 추가. WMS 프런트10개·typecheck·변경 ESLint 통과. 입고 전용 화면은 미구현.
- 전체 백엔드 pytest 재실행 중. ruff check/format134파일 통과, R1~R6 감사 오류0, db:validate 오류0. 최종 전체 결과 전에는 완료로 인계하지 않는다.

## 2026-09-29 FS-026b1 최종 완료 — 다음은 사용자 확인 후 b2

- 위 중간 WIP 상태를 이 항목으로 대체한다. 브랜치 codex/vision-ai, 기준 main6508599, 마지막 구현 a832fa8(16045ae 포함), 마지막 보고커밋은 git log -1. main 본문은 보존했다.
- 입고 예정·도착·검수·원천선점/해제/사후대사와 기존 ERP sync 단일 경로 완료. 400 필드오류/422 멱등, 날짜 제외 digest, 복사 confirmedAt 날짜만 이동·digest 불변, 신규 서버 시각 통일. 기존 W-03 새 상태/NULL 전표 호환 포함.
- 최종 검증: **backend 전체755 passed, 2 warnings, 1204.94초**; 신규 입고23 포함. tools58+subtests13, WMS 프런트10, typecheck·변경 ESLint, CI ruff check/format134파일, R1~R6 감사0, db:validate0. 자동 탐색 ruff의 기존18 I001 파일은 main과 동일하며 CI 명령은 통과했다.
- 전용 factory_studio_codex_fs026b1_final_test DB에서 실행. head fs026a_wms_receiving_reservation 유지. 공유 개발/운영DB·migration·schema/Excel/ERD·BEMS 시드11,910 기준 변경 없음. .env/work 스테이징 없음. push·배포 없음.
- b2 예약·소진·가용 조회(TX-W8~W9/AC151~158)는 **사용자 b1 확인 전 시작하지 않는다**. AC141의 예약가능95 조회도 b2에 남는다. 이후 입고 화면/3D 트럭/시드·도움말·브라우저 검증. 신규 입고 화면은 아직 없으며 프로젝트 전체 완료가 아니다.
- 상세 및 재현 명령: docs/agent/WMS확장_API_FS-026b1.md. 테스트에 필요한 전용 *_test DB 환경만 주입하면 표준 pytest 명령으로 재현되며 work 임시 도구에 의존하지 않는다.

## 2026-09-30 FS-026b2 WIP — 예약·소진·가용

- 사용자가 다음 진행 방향 1번(b2)을 승인했다. 브랜치 codex/vision-ai, 기준 3f5039c/main6508599. TX-W8~W9, AC151~158 구현. 예약 생성/해제, ERP 확정 출하 전량 소진, 원장·예약 경합 직렬화, 격리 제외/위치별 부족 보존, ERP off 가용 계산.
- ERP 조회는 interface.py만 사용. 신규 처리 시각 clock_timestamp, FS_TODAY 미사용. 게스트 예약 번호 날짜 이동/FK 재매핑. 기존 W-01/02 가용 표시 호환만 반영; W-08/09 미구현.
- 현재 관련 API60개(신규22 포함), WMS 프런트10개/typecheck/변경 ESLint 통과. CI ruff138파일, R1~R6 감사0, db:validate0. 전체 pytest 전용 factory_studio_codex_fs026b2_final_test에서 실행 중. 최종 결과 전 완료 아님.
- migration/schema/Excel/ERD 변경 없음. 템플릿11,910 유지. .env/work 스테이징 금지, push·배포 없음. b2 최종 보고 후 사용자 확인을 기다린다.
- 재현: 전용 *_test DB의 DATABASE_URL/TEST_DATABASE_URL을 환경으로 제공한 뒤 backend/.venv/bin/pytest backend/tests -q --tb=short. Ruff는 backend/pyproject.toml 명시(CI 명령). 상세 docs/agent/WMS확장_API_FS-026b2.md.

## 2026-09-30 FS-026b2 완료 — 다음은 사용자 확인 후 화면

- 위 b2 WIP 상태를 이 항목으로 대체한다. 사용자 후속 1번 승인에 따라 TX-W8~W9/AC151~158 완료. 브랜치 codex/vision-ai, 기준 main6508599/3f5039c, 구현 0d639b7. 최종 보고 커밋은 git log -1.
- 예약 생성·해제·ERP 확정 출하 전량 소진, 동일 원천 단일 전표, sync 경합, 정상 현재고−활성 예약, 격리 제외, 위치별 부족 보존, ERP off 가용 계산. AC141 예약가능95 조회도 검증 완료.
- 입력400/멱등422, clock_timestamp 처리 시각 통일, FS_TODAY 미사용. ERP interface 조회만 사용, 게스트 예약 날짜/FK 복사. 기존 W-01/02 화면·도움말 새 계산식 호환. 신규 W-08/09 화면은 아직 없음.
- 최종 검증: **backend 전체777 passed, 2 warnings, 1414.37초**(신규22 포함). 관련 WMS60, 프런트 전체490/56파일, 도구58+subtests13, typecheck/build/변경 ESLint 통과. CI ruff check/format138파일, R1~R6 감사98테이블/225FK 오류0, db:validate 오류0. 기존 사용중단 경고2와 프런트 청크 경고 유지.
- 전용 factory_studio_codex_fs026b2_final_test에서 실행. migration head fs026a_wms_receiving_reservation 유지; schema/Excel/ERD·시드 기준11,910/복사11,908 및 seed/validate.py·test_seed/test_common 변경 없음. 공유 개발/운영DB 변경·push·배포 없음, .env/work 스테이징 없음.
- 다음: **사용자 b2 확인 후** W-08 입고 예정/도착/검수와 W-09 예약 화면 및 브라우저 흐름 검증. 이후 3D 트럭 도착·체험 시드·종합 사용자 도움말·통합 점검. 신규 화면/브라우저/운영 검증은 이번에 하지 않았다.
- 상세 API/AC 근거 및 비밀값 없는 표준 재현 명령: docs/agent/WMS확장_API_FS-026b2.md. 전용 *_test DB 환경을 주입하고 pytest backend/tests 실행, Ruff는 backend/pyproject.toml 명시. main HANDOFF 본문은 보존했다.

## 2026-09-30 FS-026 후속 UI·트럭·시드·도움말 통합 WIP

- 사용자 b2 후속 전체 승인: 화면 → 3D 트럭 → 시드/도움말 → 통합 검증까지 중간 확인 대기 없이 진행. push·배포는 제외. 기준 9c66cf1, codex/vision-ai.
- W-08/09, 읽기 전용 출하 대조 미리보기·날짜/예약부족 필터, 기존 W-01~07 연결, 3D 도착 API, 정상/격리 위치, 포털 사용자 흐름 문서 구현 중.
- 새 템플릿 sv-20260930-1: WMS22행 추가, 총11,932/복사11,930. BEMS4,218행 그대로. 기존5품목, R-Q01/F-Q01, 예정/도착/95·3·2 검수/전량부족/취소, 활성/해제/소진 예약. 소진 시드는 기존 역사 출고 전표를 새 템플릿의 소진 예약 이력으로 연결하며 추가 차감하지 않는다. PI-0004/SH-0004 미반영 유지. 운영 기존 템플릿은 수정하지 않는다.
- 관련 backend76개 통과(새 preview/filter 테스트 추가 검증 중). 실 API 브라우저 트럭도착→원장0→검수95/3/2 및 새로고침 통과. 다른 브라우저 시나리오/전체 회귀는 진행 중이며 완료 아님.
- 로컬 전용 fs026_ui_test / fs026_browser_test 사용. 브라우저용 API localhost8000은 현재 실행 중(합성 시크릿, 로컬 쿠키). 테스트 종료 후 중지 예정. .env/work 스테이징 금지.
- 다음: 브라우저 실패 수정·모바일/3D 캡처 확인, 전체 pytest/프런트·ruff·격리 감사·도움말 링크·문서 갱신. 최종 커밋/인계 후 종료.

### 2026-09-30 FS-026 후속 최종 검증 중간 갱신

- W-08/09 저장 응답의 최신 version을 즉시 상세에 반영해 연속 조작 경합을 보완했다. 3D 외관·트럭 패널, W-01 수량 표시도 최종 정리.
- 실제 API Chromium 통합10개 전부 통과(1.2분). 프런트 전체491개(57파일, maxWorkers=2), 전체 ESLint/Prettier/typecheck/build 통과. Ruff139파일, R1~R6 오류0, DB 검증 오류0.
- 전체 백엔드는 깨끗한 별도 DB에서 실행 중이다. 최종 완료 항목 전까지 완료로 판단하지 않는다. 보고: `docs/agent/WMS확장_화면트럭통합_FS-026.md`.

## 2026-09-30 FS-026 후속 통합 완료 — 입고·예약 화면 / 트럭 / 시드·도움말

- 앞선 후속 WIP 상태를 대체한다. 사용자의 후속 전체 승인 범위 완료. `codex/vision-ai`, main6508599 기준 유지, 구현 `cd41b04`, 연속 조작 보완 `0ad25ee`. 마지막 문서 커밋은 `git log -1`.
- W-08 입고 예정·도착·검수·원천 연결, W-09 예약·출하 대조·소진, 기존 W-01~07 정상/격리/예약/가용 표시·동선 확장. 저장 응답의 최신 version을 즉시 반영하여 빠른 다음 조작의 이전 버전 사용을 방지한다.
- 3D 트럭은 서버 도착 상태만 변경한다. 검수 때만 재고 증가, 예약 때 원장 불변, 소진 시 기존 출하 원천과 중복 차감 방지. 통신 실패/재시도/응답 유실 복구/미저장 보호 포함. CNC 수량·GPS/실차·실장비 연결 제외.
- 시드 sv-20260930-1: 템플릿11,932 / 게스트11,930, 기존 품목·BEMS4,218 유지. WMS22행 추가. 새 migration 없음(head fs026a_wms_receiving_reservation), metadata98테이블/1022컬럼/225FK 유지. 기존 템플릿·운영 DB 수정 없음.
- 최종 검증: 전체 backend **779 passed**(23분39초, 기존 경고2), frontend **491 passed /57파일**(maxWorkers=2), 실제 API Chromium **10 passed**(1.2분). 전체 typecheck/lint/format/build 통과, Ruff139파일 통과, R1~R6 격리 감사0·db:validate0, tools58+subtests13 통과. 기본 병렬 프런트 실행의 기존 ERP 테스트 일시 실패·재검증 및 경고는 통합 보고에 기록.
- 도움말 W-08/09, 기존 W-01~07, 사용자 참고 `/help/portal/wms-flow` 반영. 360px와 트럭 외관 캡처 확인. 보고·재현·AC 증거: `docs/agent/WMS확장_화면트럭통합_FS-026.md`.
- 검증용 API/Vite 종료. `.env`·work 스테이징 없음. **push·운영 배포 없음. 이번 승인 범위 남은 개발 없음.** 다음은 사용자의 통합/운영 반영: 백엔드·프런트를 함께 적용하고 새 템플릿 생성·검증 후 새 게스트에서 체험한다. 기존 기록을 소급 변경하지 않는다.

## 2026-10-01 FS-030 GW 결정서 — 승인 대기

- 사용자 GW 별도 담당 지시에 따라 fetch 후 최신 origin/main7a2d70f(67540be 후속)에서 `codex/fs-030-gw` 생성. 작업 폴더 factory-studio-codex만 사용, vision-ai에서 이어 개발하지 않음.
- `docs/plan/GW도입_전자결재_결정_FS-030.md` 작성. D60~D69, AC220~239 범위 유지. 합성 담당자/실제 인증 주체 구분, 순차 결재·회수·재상신 불변 이력, 원문 변경·off·최신 회차 배지, 글 포함/댓글·첨부 제외 해석을 승인안으로 보완.
- 권장: ERP 매입 전표 한 종류+일반 기안, E-11 읽기 전용 배지 포함. ERP 교차 쓰기/확정 통제 없음. 결정은 아직 승인되지 않음.
- 킷의 공용 개발 DB 적용 지시는 이번 전용 DB 지시로 제외. 적용 migration 불변과 병합 head 변경 충돌은 DB 착수 전 재확인 및 새 연결 방식 조율로 기록. 현재 head fs026a_wms_receiving_reservation, metadata v0.14.0/103테이블 유지.
- 검증: 문서 상대 링크5개·D번호10개·AC20개·현황173/200줄 정적 검사 통과(exit0), git diff --check 통과(exit0). 제품 코드/스키마 변경이 없어 pytest·프런트·브라우저·migration·시드·격리 감사는 미실행. DB 접속/공용 서버 실행 없음.
- 다음: **사용자 결정서 승인 후** GW 모듈/README·G-01~07 화면 설계. 전체 설계 승인 전 schema.json·migration·제품 코드 작성 금지. 이후 a/b/c 각각 보고 후 대기. push·배포·main 병합 없음. 최종 문서 커밋은 git log -1로 확인.

## 2026-10-01 FS-030 GW 전체 설계 작성 — 승인 대기

- 사용자 “진행해줘”를 결정서 권장안 4항목 승인으로 기록(D60~69). 브랜치 codex/fs-030-gw, main7a2d70f/선행 결정커밋 b873543.
- 새 문서: docs/modules/gw/GW_모듈설계_FS-030.md, 같은 폴더 README.md(현재 기준/조회 계약), docs/ui/화면설계_GW_FS-030.md. 결정서·로드맵·현황 갱신.
- gw8테이블, G01~07+E11 읽기 배지, TX-G1~6/API/권한/잠금/오류/불변 이력·재상신·원문 digest/복사·시드69행(+모듈행1 별도) 설계. AC220~239 연결. source digest는 ERP 소유 정규화 함수로 일원화; 제공 interface 사이 재귀 호출 금지.
- 검사: 문서4개 상대 링크17개·테이블8·화면7·AC20·시드합69·현황173/200줄 정적 검사 통과(exit0), git diff --check 통과(exit0). 최초 임시 검사 정규식이 interface 함수까지 테이블로 세어 실패했으며 식별자 패턴 보정 후 통과. 제품 검증 결과가 아님.
- 미실행: pytest·vitest·브라우저·DB migration·시드 생성·격리 감사. 문서만 작성했고 제품 코드/schema.json/Excel/ERD/migration 변경 및 DB 접속 없음.
- 다음: **사용자 모듈·화면 전체 설계 확인 후 FS-030a DB**. a 착수 전 최신 main/head/공통 파일·SPC/CMMS 시드 합계 재확인. 적용 migration 수정 금지, Codex 전용 DB/포트만 사용. a/b/c 각각 보고 후 대기. push·배포·main 병합 없음. 최종 문서 커밋은 git log -1.

## 2026-10-01 FS-030a DB WIP

- 사용자 “구현 진행해줘”로 모듈·화면 전체 설계 승인. origin/main6350697(FS-040 포함) 위 rebase 완료, codex/fs-030-gw. GW 8테이블·스키마 목록·복사·모듈 기본행 및 Excel/ERD 구현. head fs030b_gw_module, down fs040_app_review.
- 전용 factory_studio_codex_fs030_test: DB 제약·시드·공통 회귀45 passed, 도구69 passed, 실제 DDL 대조/설계 검증/격리 감사 오류0. 전체 backend/UI/browser 미실행. downgrade 왕복·기존 공간 backfill 검증과 최종 문서 정리 남음.
- FS-030b API/화면은 아직 시작하지 않음. a 최종 보고 후 사용자 확인 대기. push·배포·main 병합 없음. .env/work 스테이징 금지. 상세 표준 재현 명령은 최종 a 보고에 남긴다.

## 2026-10-01 FS-030a DB 완료 — 다음은 사용자 확인 후 b

- 앞선 GW WIP/승인대기 상태를 대체한다. 전체 설계 “구현 진행해줘” 승인. main6350697에 rebase한 codex/fs-030-gw, 구현15f9398·최종커밋 git log -1.
- 신규8테이블·복사/초기화·모듈행/평가모듈CHECK, schema/Excel/ERD 일치. 임시0.15.0-gw,112테이블·1,225컬럼·258FK, headfs030b_gw_module(fs040 뒤). 템플릿11,934/복사11,932. 적용 기존migration 변경 없음.
- 전용DB pytest45/도구69 통과, Ruff154파일·격리/DDL/정적 오류0, 빈DB 왕복·기존공간GW true/ERP false·유데이터 downgrade 거부/전체롤백 통과. Excel39시트/GW4미리보기 확인. 전체backend/UI/browser 미실행.
- 상세 변경파일·검증/미실행·재현은 docs/agent/GW_DB_FS-030a.md. SERVICE 정책/권한/결재 로직은 아직 b 미구현이며 DB 제약과 구분한다.
- b 사용자 확인 후 API·G01~07·ERP조회계약/E11배지·런처/평가 gw 허용·전환/문서/e2e. c69업무행/도움말/흐름맵/전체검증. push·배포·main 병합 없음. Codex전용DB만 적용, 공유DB/8000/5173 서버 사용 없음. .env/work 스테이징 없음.

## 2026-10-03 FS-030b API·화면 WIP

- 사용자 “이어서 진행해줘”로 b 승인. main8531c05까지 fast-forward(GW a 병합·SPC 시드·CMMS DB/운영 기록 유지), branch codex/fs-030-gw. 스키마 v0.17.0/headfs029b_cmms_module 그대로.
- GW 서비스/읽기 interface/ERP 조회계약, G01~07·ERP 배지·런처 연결 구현 중. 순차 결재·반려/재상신·회수·게시정정·역할 검사·멱등·스냅샷 불변. ERP 코드 조회만, 교차쓰기 없음.
- 첫 관련 API11개 통과 후 경합/ERP 배지/원문변경 등을 확장 검사 중. typecheck 통과. 전체pytest·frontend·실제브라우저는 아직 완료 아님. 전용 factory_studio_codex_fs030b_test만 사용.
- 다음: 추가 회귀·브라우저 검증/오류 보정·문서/최종보고. c업무69행/도움말은 사용자 b 확인 뒤. push·배포 없음. .env/work 스테이징 금지.
