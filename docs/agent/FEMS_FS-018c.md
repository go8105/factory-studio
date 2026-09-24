# FS-018c 완료 보고 — F-03 설비별 배분

작성일: 2026-09-24 · 브랜치 `fs-018c-fems` (main `b1e4f20`에서 분기) · 작업자 Claude Code

## 범위

저장된 `fems.energy_allocation` 결과를 조회하는 첫 계산 계열 화면이다. 배분을 새로 계산하지 않는다(TX-06 재산정 작업은 범위 밖). FEMS 진행 4/14(F-02·F-03·F-10·F-11).

## API — `GET /api/v1/fems/allocations`

파라미터: `from`·`to`, `equipmentId`, `energySourceId`, `methodKey`, `includeSuperseded`(기본 false), offset 페이지. 응답: `data`, `page`, `range`, `summary`.

확정한 규칙:

- **기간**: 배분 구간은 사업장 시간대 `[D 00:00, D+1 00:00)`(설비 → 공간 → 사업장). 기본 최근 배분일까지 7일, 최대 31일. 기간 검증은 F-02와 같은 함수(`_check_period`)를 쓴다.
- **현재 결과**: 같은 설비·채널·구간에 결과가 여러 개면 `input_revision`, `method_version`이 가장 큰 행이 현재 결과(`isLatest`)다. 기본은 현재 결과만, `includeSuperseded=true`면 이전 결과도 보여 준다(FS-008a F-03, FS-006 TX-06 "현재 방법 버전 하나만 기본 결과").
- **필터는 현재 결과 판정 뒤에 건다.** 판정 안에서 걸면, 예를 들어 `methodKey=DIRECT_METER`로 거를 때 다른 방법으로 재산정된 날의 옛 DIRECT_METER 결과가 현재로 보인다. 이 경우를 테스트로 고정했다.
- **합계(`summary`)**: 현재 결과만, `quality='invalid'` 제외, **설비 × 단위별로 따로 합한다**(kWh와 m3를 더하지 않는다). 일수와 추정(`estimated`) 일수를 함께 준다.
- `basis`(jsonb)는 그대로 전달한다. 화면이 라벨을 붙인다.

## 화면 — `frontend/src/fems/Allocations.tsx`

- 필터: 기간·설비·에너지원·배분 방법·"이전 산정 결과 포함". 조회 버튼을 눌러야 요청한다(F-02와 같은 패턴).
- **설비별 합계**: 단위마다 별도 패널(`설비별 합계 · kWh`, `· m3`). 추정일이 있으면 "추정 N일" 배지.
- **배분 결과 표**: 날짜·설비·채널·배분량·단위·방법(한국어 이름)·품질 배지, 이전 결과 포함 시 "현재/이전" 열.
- **계산 근거 패널**(공통 규격 6-4): 행마다 `<details>`로 접어 둔다. 배분 방법·버전, 입력 버전, basis 항목(합산 시간·결측 시간·가동 시간·공용 미배분량·가동 설비 수).
- `BasisPanel`·`AllocationSummary`·`METHODS`·`BASIS_LABELS`를 export했다. F-01·F-06이 재사용한다.

## 테스트 (항목별 분리)

- `backend/tests/test_fems_allocations.py` **16개**: 기본 기간 / DIRECT_METER 7일 56행 / 하루 경계 / estimated 근거 / RUNTIME_SHARE 근거 키 / 수량 문자열 / 이전 결과 기본 숨김 / 이전 결과 포함 / **방법 필터 후에도 현재 판정 유지** / 합계는 현재 결과만 / 합계 invalid 제외 / 합계 추정 일수 / 합계 단위 분리 / 역순 기간 400 / 다른 공간 0건 / 모듈 꺼짐 409. 이전 결과는 테스트에서 행을 직접 추가해 재현한다.
- `frontend/src/fems/allocations.test.tsx` **11개**: 사이드바 / 기간 채움 / 단위별 합계 표 / 추정 일수 배지 / 방법 한국어 이름 / 근거 패널 접힘 / 근거 라벨 / 방법·입력 버전 / 기본 조회에 이전 결과 없음 / 이전 결과 포함 요청과 결과 열 / 조건 전달.
- Playwright `fems.spec.ts` +2(단위별 합계·근거 펼침, 09-07 추정 1일) + 360px F-03.

## 실행 검증

Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6. backend `factory_studio_fs016_test`, 브라우저 `factory_studio_fs017_test`, 순차 실행. 모두 exit 0.

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build | 통과, 번들 경고 없음 |
| `npm --prefix frontend test` | 121 passed |
| ruff check / format --check | 통과 |
| backend 전체 pytest | 121 passed |
| `tools/run_portal_smoke.py` | Playwright 26 passed |
| tools unittest / db:validate / audit_schema_isolation / git diff --check | 44 passed / 통과 / 통과 / 통과 |

schema.json·마이그레이션·content·conftest·test_common·test_seed 변경 0.

## 남은 것

- F-01 대시보드, F-04 배출량, F-06 원단위, F-07 목표 대비 실적(목표=실적×95% 사용자 판단), F-08 요금(F-14 요금제 필요), F-05 생산량 등록.
- F-12 계측기·채널, F-13 환산·배출계수, F-09 사업장·공간.
