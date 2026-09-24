# FS-018d 완료 보고 — F-04 배출량 현황 (+ AG-06 F-14 검토)

작성일: 2026-09-24 · 브랜치 `fs-018d-fems` (AG-06 `2159103` 위) · 작업자 Claude Code

## AG-06 (F-14 요금제) 검토

- 저장소와 보고 일치(11파일). main `734d5cc`에서 ff 가능.
- 겹침 판정: 같은 에너지원, 자기 제외, `to_A < from_B or to_B < from_A`가 아니면 겹침. NULL(계속 적용) 처리 맞음.
- PATCH에서 `effectiveTo`·`contractType`만 null로 비울 수 있게 `non_null_fields`로 구분했고 테스트가 있다(F-11 복제 시 흔한 실수를 피했다).
- 재현: frontend 133, backend 142, Playwright 26 통과.
- 보고서의 "F-12 배분 규칙, F-13 목표 관리"는 화면 이름이 틀렸다. 설계상 F-12는 계측기·채널, F-13은 환산·배출계수다.

## F-04 범위

`GET /api/v1/fems/emissions?from&to` — 조회 시 계산, 저장하지 않는다(FS-010 §7, G-04). FEMS 진행 6/14(F-02·F-03·F-04·F-10·F-11·F-14).

## 확정한 계산 규칙

1. **소비량은 최상위 계측기만**(`meter.parent_meter_id IS NULL`). 설비 계측기 8대는 수전(M-MAIN)의 하위라 더하면 이중 합산이다.
2. 결측(`quality='invalid'`)은 소비량에서 빼고 `excludedReadings`로 센다. **계기 배수(`multiplier`)를 곱한다.**
3. **연도 분할**: 계측값의 연도(사업장 시간대, 구간 끝 시각 기준)마다 그 연도의 EMISSION 계수를 적용한다(`segments`). 기간이 연도를 걸치면 구간별 다른 계수.
4. **배출계수(EMISSION)만 조회한다.** PRIMARY가 있어도 EMISSION이 없으면 계산하지 않는다(테스트 고정).
5. 에너지원 상태 4종:
   - `CALCULATED`
   - `NOT_APPLICABLE` — `source_kind='UTILITY'`, 용수 (FS-005g D-1)
   - `FACTOR_MISSING` — 계수 없음, 계산 불가
   - `UNIT_MISMATCH` — 계수 단위의 분모가 계측 단위와 다름(예: tCO2eq/MWh vs kWh). 조용히 1000배 틀리는 것을 막는다
6. **총량은 계산된 에너지원만 합한다.** 대상인데 계산 불가가 있으면 `complete=false`.
7. 기본 기간: 최근 계측일이 속한 달의 1일 ~ 그날(당월 누계). 최대 366일. 수치는 소수 6자리 문자열.
8. 응답의 계수에 `kind`·`year`·`value`·`unit`·`source`(source_note)를 싣는다 — 화면이 계수 출처를 값 옆에 표시한다(FS-008a F-04).

## 화면 — `frontend/src/fems/Emissions.tsx`

- 핵심 수치 타일: 총 배출량 tCO2eq. 계산 불가가 있으면 "일부 에너지원은 계산 불가 · 합계에서 빠졌습니다". "1차에너지 환산계수와 다른 계수" 안내.
- 에너지원별 표: 소비량(단위), 배출량, 상태 배지(계산됨 / 대상 아님 / 계수 없음 · 계산 불가 / 계수 단위 불일치 · 계산 불가), 근거 패널(연도·소비량·계수·출처·배출량, 제외한 결측 건수).
- 대상 아님은 근거 표 대신 "에너지가 아니어서 배출 산정 대상이 아닙니다".
- 차트는 두지 않았다. 핵심은 수치 1개와 에너지원 2~3행이라 표가 더 정확하다.

## 테스트 (항목별 분리)

- `backend/tests/test_fems_emissions.py` **15개**: 기본 기간(당월 누계) / 전력은 수전만 / 전력 2026 계수 / 가스 계산 / 용수 대상 아님 / 총량 = 계산 합 / 계수 없음 / PRIMARY 미사용 / 단위 불일치 / 결측 제외·건수 / 배수 적용 / **연도 걸친 기간의 연도별 계수**(2025=0.047000, 2026=0.046000) / 문자열 / 366일 초과 400 / 모듈 꺼짐 409. 기대값은 API를 거치지 않고 채널 계측값을 SQL로 직접 합해 만든다.
- `frontend/src/fems/emissions.test.tsx` **11개**: 사이드바 / 기간 채움 / 총량·단위 / 계산 불가 알림 / 대상 아님 / 계수 없음 문구 구별 / 근거 계수·출처 / 결측 건수 / 대상 아님 설명 / 조회 기간 전달 / 계측값 없음 안내.
- Playwright +1(총량·용수 대상 아님·전력 근거 계수 단위) + 360px F-04.

## 실행 검증

Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6. 모두 exit 0.

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build | 통과, 번들 경고 없음 |
| `npm --prefix frontend test` | 144 passed |
| ruff check / format --check | 통과 |
| backend 전체 pytest (`factory_studio_fs016_test`) | 157 passed (5분 45초) |
| `tools/run_portal_smoke.py` (`factory_studio_fs017_test`) | Playwright 28 passed |
| tools unittest / db:validate / audit / git diff --check | 44 / 통과 / 통과 / 통과 |

schema.json·마이그레이션·content·conftest·test_common·test_seed 변경 0.

## 제안·남은 것

- **backend 전체 테스트가 5분 45초로 길어졌다.** FEMS 테스트마다 템플릿 세대를 새로 만들기 때문이다. 세션 범위 템플릿 + 테스트별 게스트 복사로 바꾸면 크게 줄어든다. `conftest.py`는 Codex 소유라 제안만 한다.
- 다음: F-01 대시보드(F-04 계산 재사용 + 1차에너지 환산 총량 + 목표 대비). F-07 목표=실적×95% 판단 필요.
