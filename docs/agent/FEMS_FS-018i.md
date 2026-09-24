# FS-018i 완료 보고 — F-05 생산량 등록

작성일: 2026-09-24 · 브랜치 `fs-018i-production` (main `95ae521`, CI 통과 확인 후) · 작업자 Claude Code

## 범위

FEMS 첫 입력 업무 화면. 원단위(F-06)의 분모가 되는 생산량을 초안 → 확정 → 정정(새 버전) 흐름으로 관리한다. FEMS 진행 10/14.

## API — `/api/v1/fems/production-records`

| 메서드·경로 | 동작 |
|---|---|
| `GET` | 원천 키별 최신 버전(기본) / `includeHistory=true`면 모든 버전. `equipmentId`·`itemCode`·`status` 필터 |
| `GET /{id}` | 단건 |
| `POST` | 초안(v1) 등록. 원천 키 `MAN-YYYYMMDD-NNN` 자동 발번 |
| `PATCH /{id}` | 초안만 수정 |
| `DELETE /{id}` | 초안만 삭제 |
| `POST /{id}/confirm` | 초안 → 확정 |
| `POST /{id}/revise` | 최신 확정 버전에서 다음 버전 초안 생성 |

모든 변경은 CSRF + `Idempotency-Key`, `write_scope`(공간 잠금·세대 재확인) 뒤 대상 행 `FOR UPDATE`.

## 규칙 (schema.json SERVICE/DB_POLICY 구현)

- **확정 불변**: 확정 행의 PATCH·DELETE·재확정은 409 `ALREADY_CONFIRMED`.
- **정정 = 같은 원천 키의 새 버전 초안**. 최신 확정 버전에서만 만들 수 있다. 초안이 이미 있으면 409 `DRAFT_EXISTS`, 옛 버전에서 시도하면 409 `NOT_LATEST`.
- **정정 버전은 설비·품목·단위를 바꿀 수 없다** → 409 `REVISION_FIELDS_FIXED`(생산량·기간은 가능).
- **확정 시 구간 중복 거부**: 다른 원천 키의 현재 확정 기록 중 같은 설비·품목·단위이고 기간이 겹치면 409 `PERIOD_OVERLAP` + `conflicts`. 붙어 있는 기간, 다른 품목은 허용. 초안끼리는 겹쳐도 된다(확정 때 검사).
- **현재 결과(`isEffective`)**: 원천 키별 최대 확정 버전. 원단위는 이것만 쓴다. 초안 제외.
- 기간 입력은 날짜(시작·종료 포함). 서버가 설비 사업장 시간대로 `[시작 00:00, 종료+1 00:00)`에 저장한다. 최대 366일.
- 생산량 0 허용(numeric(18,3), 소수 3자리). 품목은 코드 문자열(FEMS 품목 마스터 없음, FS-013 §3.5).
- 마스터와 같이 audit_event는 남기지 않는다(FS-021 판단 유지).

## 화면 — `frontend/src/fems/Production.tsx`

- 설계서 안내 문구: "MES를 쓰는 환경이라면 생산실적에서 자동으로 넘어오는 값…".
- 목록: 원천 키·버전, 상태(초안 / 확정 · 원단위 반영 / 확정 · 이전 버전), 관리, 생산량, 설비, 품목, 기간. 초안은 수정·확정·삭제(2단계), 최신 확정은 정정, 이전 버전은 작업 없음.
- 등록/수정 패널: 정정 초안은 설비·품목·단위 입력을 잠그고 이유를 적는다.
- 공통 `ErrorNotice`가 `conflicts`를 "원천 키 · 시작 · 종료"처럼 읽히게 보여 준다(F-14 요금제 겹침에도 적용).
- 360px 스크린샷으로 두 가지를 고쳤다: 상태·관리 열을 앞으로(가로 스크롤 뒤에 숨던 문제), 필터 줄 체크박스 한 줄 배치(F-03에도 적용).

## 테스트 (항목별 분리)

- `backend/tests/test_fems_production.py` **27개**: 최신 버전 목록 26 / 이력 27 / 현재 결과 판정 / 생산량 0 유지 / 초안 v1·MAN 키 / 사업장 시간대 경계 / 순번 증가 / 멱등 재전송 / CSRF / 종료<시작 / 다른 공간 설비 / 음수 / 소수 4자리 / 초안 수정 / 확정 수정 409 / 초안 삭제 / 확정 삭제 409 / 확정 시각 / 겹침 409·conflicts / 인접 허용 / 다른 품목 허용 / 정정 v2 초안 / 이중 정정 DRAFT_EXISTS / 옛 버전 NOT_LATEST / 설비 고정 / 정정 확정 후 현재 결과 전환 / 모듈 꺼짐.
- `frontend/src/fems/production.test.tsx` **13개**, Playwright +1(초안 등록 → 확정 → 정정 초안, 설비 입력 잠금) + 360px F-05.

## 실행 검증 (모두 exit 0)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 207 passed |
| ruff check / format --check (**CI와 같은 범위** `backend tools/verify_ddl_matches_schema.py`) | 통과 |
| backend 전체 pytest (**CI 환경 변수만, .env 미사용**) | 244 passed (9분 24초) |
| `tools/run_portal_smoke.py` (360px 수정 후 재실행) | 39 passed |
| tools unittest / db:validate / audit / git diff --check | 통과 |

schema.json·마이그레이션·content·conftest·test_seed 변경 0.

## 남은 것

F-06 원단위(생산량 0 → "생산량 없음", 기준선 대비). 그다음 F-13·F-12·F-09. backend 테스트가 9분을 넘었다 — 테스트 준비 속도 개선(conftest, Codex)을 다음 Codex 작업으로 제안한다.
