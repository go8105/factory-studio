# FS-018g 완료 보고 — F-07 목표 대비 실적

작성일: 2026-09-24 · 브랜치 `fs-018g-targets` (main `db52e23`) · 작업자 Claude Code

## 범위

`GET /api/v1/fems/targets/performance?month=YYYY-MM`(FS-010 §7 경로). FEMS 진행 8/14.

## 규칙

- **범위별 섹션, 합산하지 않는다**(FS-008a F-07): 사업장(에너지원별 + 1차에너지 환산 TOE) / 설비(전력 kWh).
- 사업장 에너지원 실적 = 최상위 계측기 소비량(invalid 제외, 배수 적용). 용수는 m3로 m3 목표와 비교한다(환산하지 않는다).
- 사업장 TOE 실적 = F-01과 같은 PRIMARY 환산 합계(테스트로 두 API 값 일치). 환산이 불완전하면 계산 불가.
- 설비 실적 = F-03 현재 결과 합계(invalid 제외). 추정 일수를 함께 준다.
- 상태: `WITHIN`(달성률 ≤ 100) / `EXCEEDED` / `UNSET`(목표 없음, 달성률 없음) / `NOT_CALCULABLE`(목표는 있으나 실적 없음 또는 **목표 단위와 실적 단위가 다름** — 단위 환산을 추측하지 않는다).
- 기간: 당월은 최근 계측일까지 누계(`monthToDate=true`), 지난달은 월 전체. FS-018e에서 남긴 질문의 답으로, 화면에 "당월 누계 기준. 목표도 같은 기간 기준으로 정했습니다"를 표시한다.
- 목표가 없는 설비도 실적이 있으면 행을 두고 "미설정"(시드 INS-02 당월).

시드 결과: 9월 사업장 전력 98.0% 이내, 가스 102.0% 초과, 용수 105.3% 초과, TOE 99.0% 이내 / 설비 ASM-02 111.1% 초과(추정 1일), INJ-02 95.2% 이내, INS-02 미설정.

## 함께 고친 것

- **사이드바 그룹**: F-14 요금제를 FS-008a 메뉴대로 "기준정보"로 옮겼다(AG-06 프롬프트에서 제가 "요금"으로 잘못 지시했다). "요금" 그룹은 F-08 몫이다.
- **360px 표 열 순서**: 스크린샷에서 달성률·상태가 표 가로 스크롤 뒤에 숨는 것을 보고 대상 → 달성률 → 상태 → 목표 → 실적 순으로 바꿨다.
- **스모크 도구 포트 검사**: 직전 실행 직후 재실행하면 TIME_WAIT 소켓 때문에 "port 8000 사용 중"으로 중단되던 문제(FS-018b 이후 두 번째). 검사 소켓에 `SO_REUSEADDR`를 켰다. LISTEN 중인 서버는 여전히 감지함을 확인했고, 연속 2회 실행이 모두 통과했다.

## 테스트 (항목별 분리)

- `backend/tests/test_fems_targets.py` **18개**: 사업장 섹션 구성 / 전력 실적 = 수전 합(SQL) / 달성률 공식 / TOE = 대시보드 / 사업장 이내·초과 혼재 / 용수 자기 단위 비교 / 단위 불일치 계산 불가 / 설비 목표 없음 미설정 / 설비 실적 = 배분 합(SQL) / 설비 이내·초과 혼재 / 추정 일수 / 실적 없는 목표 계산 불가 / 설비 섹션 kWh만 / 당월 누계 / 전월 전체 / 전월 INS-02 목표 있음 / 월 형식 400 / 모듈 꺼짐 409.
- `frontend/src/fems/targets.test.tsx` **11개**: 사이드바 그룹 / 요금제 기준정보 그룹 / 섹션 분리 / 첫 조회 1회 / 월 변경 / 당월 누계 안내 / 전월 전체 안내 / 달성률·상태 텍스트 / 미설정 / 추정 일수 / 빈 상태.
- Playwright +1(섹션·INS-02 미설정·이내/초과 혼재) + 360px F-07.

## 실행 검증 (모두 exit 0)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build | 통과 |
| `npm --prefix frontend test` | 169 passed |
| ruff check / format --check | 통과 |
| backend 전체 pytest | 201 passed (7분 9초) |
| `tools/run_portal_smoke.py` (열 순서·포트 수정 후, 연속 2회) | 33 passed / 33 passed |
| tools unittest / db:validate / audit / git diff --check | 통과 |

schema.json·마이그레이션·content·conftest·test_common·test_seed 변경 0.
