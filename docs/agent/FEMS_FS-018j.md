# FS-018j 완료 보고 — F-06 원단위 분석

작성일: 2026-09-25 · 브랜치 `fs-018j-intensity` (main `78e1206`) · 작업자 Claude Code

## 범위

생산량(F-05)을 분모로 에너지 원단위를 조회 시 계산한다. 함께 테스트가 날짜 변경에 깨지던 원인(업무 기준일)과, 로컬 HTTP용 `COOKIE_SECURE` 변경의 결함을 고쳤다. FEMS 진행 11/14.

## API — `GET /api/v1/fems/intensity?from&to`

- 기본 기간: 최근 계측일까지 31일. 최대 92일. 결과를 저장하지 않는다(FS-010 §7).
- **기록별**: 생산 구간에 완전히 들어가는 설비 일별 배분(현재 결과, invalid 제외) ÷ 생산량. 단위별(kWh/EA·m3/EA)을 합치지 않고 따로, TOE/EA는 PRIMARY 환산(용수 제외). 생산량 0 → `NO_PRODUCTION`, 배분 없음 → `NO_ENERGY`. 원천 키별 최신 확정 버전만, 초안 제외.
- **품목별**: 원천 키 `MES:<LOT>:<공정>`으로 LOT를 묶는다. 모든 공정 기록이 기간 안이고 검사(`equipment_type='INS'`)까지 끝난 LOT만. 분자 = LOT 전 공정 전력, 분모 = 검사 양품(FS-005g 5.5 D-2). 직접 입력(MAN-)은 품목 원단위에서 제외.
- 확정 기준선(초안 제외) 대비 증감률. **시드 기준선 3품목을 소수 6자리까지 재현**(핵심 검증).

## 업무 기준일 `FS_TODAY` — `backend/src/fs/common/clock.py`

- 원인: 날짜가 09-25로 바뀌자 테스트 17개 실패. 테스트는 09-24 템플릿을 만드는데 게스트 복사는 "오늘"로 데이터를 옮겼다. GitHub CI의 `78e1206` 실패도 같은 이유로 보인다(코드 결함 아님).
- `business_today()` = `FS_TODAY` 또는 실제 KST 날짜. 게스트 생성·세대 초기화가 쓴다. 운영에서는 설정하지 않는다.
- `guest_expires_at()`은 **실제** 생성일 다음 날 00:00 KST. 날짜를 과거로 고정해도 게스트가 만들자마자 만료되지 않는다.
- FEMS 테스트 fixture에 `FS_TODAY=2026-09-24`, 스모크는 템플릿·서버 모두 `SMOKE_DATE=2026-09-24`.

## `COOKIE_SECURE` (다른 작성자 변경, 사용자 결정 ③으로 함께 수정)

- 로컬 HTTP에서 쿠키를 쓰도록 `COOKIE_SECURE`(기본 true)를 `_set_cookie`·만료 쿠키 삭제에 반영한 변경.
- 결함: 오류 핸들러가 `get_settings()`를 불러 SESSION_SECRET이 없으면 무세션 요청이 401 대신 500이 됐다(`test_list_requires_session` 실패).
- 수정: `config.cookie_secure()`를 환경 변수만 읽는 함수로 분리하고 오류 핸들러는 그것만 쓴다.

## 화면 — `frontend/src/fems/Intensity.tsx`

계산 규칙 안내, 기간 조회(첫 조회는 서버 기간), 품목 원단위와 기준선·증감(악화/개선/같음), 기록별 에너지원 나란히 표시, 계산 불가 사유, 확정 기준선·생산량이 없을 때 안내.

## 테스트

- `backend/tests/test_fems_intensity.py` **20개**(시드 기준선 재현 3품목 포함), `test_clock.py` **3개**.
- `frontend/src/fems/intensity.test.tsx` **13개**, Playwright F-06 + 360px.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 220 passed |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest | 267 passed (11분 20초) |
| `tools/run_portal_smoke.py` | 41 passed (360px F-06 가로 스크롤 없음 포함) |
| tools unittest / db:validate / audit / git diff --check | unittest 44 OK · 통과 |

schema.json·마이그레이션·conftest·test_common·test_seed 변경 0.

## 남은 것

F-13 → F-12 → F-09. backend 테스트가 11분을 넘었다 — Codex의 conftest 단축 작업은 이 브랜치가 main에 들어간 뒤 시작한다.
