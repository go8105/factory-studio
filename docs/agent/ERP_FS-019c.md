# FS-019c 완료 보고 — E-05 출하지시 · E-06 출하 (ERP 9/18)

작성일: 2026-09-26 · 브랜치 `fs-019c-erp-shipping` (main `0addc2e` FS-019b 위) · 작업자 Claude Code

## 범위 판단

- **TX-09 매출 인식을 019c에 포함했다.** FS-006a·FS-014b가 "출하 확정 트랜잭션 안에서 매출·채권 1건씩 생성, 출하만 되고 매출이 없는 상태 금지"로 정하고 있어 떼어 낼 수 없다. 019d는 E-07 매출 목록·취소와 E-08 세금계산서(E-G07 0원 발급 금지)를 맡는다.
- 출하는 **등록 = 확정**이다. `shipment.status`의 draft는 쓰지 않는다(FS-006b "지시별 전량 1회 출하", 작성 단계가 필요한 규칙 없음).
- FS-006a TX-08의 PALLET 잠금·입고 상태 검사는 FS-013 독립 결정(`packing_no` 수기 코드, FK 없음)으로 대상이 없다. ERP 안의 중복 패킹번호만 막는다(E-G04, 부분 유니크 인덱스와 서비스 검사).

## API (구현: `erp/shipping.py`, `erp/revenue.py`)

계약 요약은 FS-010 §8 "출하지시·출하 (FS-019c)".

| 항목 | 규칙 |
|---|---|
| TX-07 출하지시 | 수주 → 수주 명세 `FOR UPDATE` 뒤 명세별 Σ(취소 안 된 지시) + 신규 ≤ 수주수량. 부분 지시 허용, 초과 409 `ORDER_QTY_EXCEEDED`(+행 번호·남은 수량). 미출하 지시만 사유와 함께 취소 |
| TX-08 출하 | 수주 → 명세 → 출하지시 → 지시 명세 순서로 잠금. 지시 전 명세를 지시 수량 그대로 출하. 지시 → shipped |
| TX-09 매출 | `revenue.recognize` 한 곳에서만 계산. TAXABLE 10%·ZERO/EXEMPT 0%(E-G01 상수), 명세별 1원 사사오입. 채권 원금 = 합계, 만기 = 인식일(KST) + 결제일수 또는 NULL. `python -m fs.erp.revenue` 자체 점검 |
| 수주 상태 | 수량 변경과 같은 트랜잭션에서 open/shipping/closed 재계산(`refresh_order_status`) |

업무 시각(`shipped_at`=`recognized_at`)은 `clock_timestamp()`.

## 화면

- `ShipmentOrders.tsx` E-05: 지시 목록·명세, 사유 입력 취소, 새 지시(수주 선택 → 명세별 "지시 가능" 수량 기본값).
- `Shipments.tsx` E-06: 출하 목록·명세(패킹번호, 인식 매출 공급가액·세액·합계), 출하 확정(미출하 지시 선택, 명세별 패킹번호 선택 입력). 패킹번호 수기 입력 이유(E-G04)를 화면에 적었다.
- 사이드바 "출하·매출" 그룹. 도움말 e-05·e-06을 실제 동작에 맞게 고쳤다(전량 1회 출하, 매출·채권 동시 생성, 막히는 경우).

## 테스트

- backend `test_erp_shipping.py` **13개**: 시드 조회, 부분 지시 → shipping, 초과 거부, **동시성 주입**(두 지시 병렬 → 201·409, 누계 초과 없음), 다른 수주 명세 거부, 취소분 누계 제외·취소 지시 출하 불가, 취소 수주 거부, 영세율 매출·채권 만기(결제조건 60일), 과세 10%, 전 명세 출하 → closed, 패킹번호 중복 롤백, 출하 완료 지시 재출하·취소 거부, 멱등 재전송 시 매출 1건.
- frontend `erp/shipping.test.tsx` **6개**. Playwright: 출하지시 → 출하 확정 → 수주 완료 흐름 + 360px 2화면.
- 처음 테스트 1건이 SQL 별칭 `day`(예약어) 때문에 실패 → `AS day`로 고침.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 통과, **360 passed** |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest | **574 passed** (9분 56초) |
| `tools/run_portal_smoke.py` | **90 passed** (3.4분) |
| tools unittest / db:validate / audit_schema_isolation / git diff --check | 통과 |

- 포털 `screens.test.tsx` "P-03 품질검사 노드" 1건이 전체 실행에서 반복 실패(019b에서도 1회). 부하 없이도 1004ms로 실패 — 흐름 화면의 `findByRole` 기본 대기 1초 초과. 테스트 파일이 늘어 병렬 워커가 느려진 타이밍 문제라 해당 조회만 5초 대기로 늘렸다(연속 2회 360 passed).

360px 스크린샷(E-05·E-06) 직접 확인: 가로 스크롤 없음, 관리 열은 코드 바로 뒤. schema.json·마이그레이션·conftest·test_common·test_seed 변경 0. 새 의존성 0.

## 다음

FS-019d E-07 매출(목록·취소: 소명 0행 전제, 발급대기 계산서 함께 삭제, 발급완료면 거부) · E-08 세금계산서(발급, **0원 매출 발급 금지 E-G07**).
