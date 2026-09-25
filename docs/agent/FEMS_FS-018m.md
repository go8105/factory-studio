# FS-018m 완료 보고 — F-09 사업장·공간 (FEMS 14/14)

작성일: 2026-09-25 · 브랜치 `fs-018m-f09` (main `70951d4` + 문서 커밋 `a32e86b`) · 작업자 Claude Code

## 범위

FEMS 마지막 화면. 설비(F-10)·계측기(F-12)가 놓이는 사업장과 공간. **이로써 FS-018 FEMS 14화면이 모두 구현됐다.**

## API

| 메서드·경로 | 동작 |
|---|---|
| `GET /sites` | 기존(F-02 등) 그대로 — `id·siteCode·name·timezone` |
| `POST /sites` · `PATCH /sites/{id}` · `DELETE /sites/{id}` | 사업장. 시간대 기본 `Asia/Seoul` |
| `GET /locations` | 기존(F-10 설비) 응답에 `siteId`·`parentLocationId` 추가(기존 필드 유지) |
| `POST /locations` · `PATCH /locations/{id}` · `DELETE /locations/{id}` | 공간 |

변경은 CSRF + `Idempotency-Key`, `write_scope` 뒤.

## 규칙

- **시간대는 IANA 이름만**(`zoneinfo.available_timezones`) → 400 `fields.timezone`.
- **기록이 있는 사업장은 시간대 변경 금지** 409 `reason=TIMEZONE_IN_USE` + 건수(계측값·배분·생산 실적). 이 세 기록의 날짜 경계를 모두 사업장 시간대로 정하므로, 바꾸면 지난 일별 합계가 조용히 달라진다. schema.json에 없는 정책이며 F-12의 `METER_IN_USE`와 같은 판단으로 추가했다.
- **공간의 사업장은 등록 후 고정**(PATCH 스키마에 없음 → 400). `fems.meter`가 (공간, 사업장)을 함께 참조하므로 옮기면 복합 FK가 깨진다.
- 상위 공간은 같은 사업장만, **부모 순환 금지**(schema.json SERVICE, 재귀 CTE) → 400 `fields.parentLocationId`.
- 사업장 코드는 전체, 공간 코드는 사업장 안에서 유일 → 400.
- 삭제 RESTRICT 409 `REFERENCED_BY_OTHERS` + 건수: 사업장 ← 공간·계측기·에너지 목표, 공간 ← 하위 공간·설비·계측기.

## 화면 — `frontend/src/fems/Sites.tsx`

- 위: 사업장 목록 + 패널(시간대가 날짜 경계를 정한다는 안내). 아래: 공간 목록(사업장·상위 공간 표시) + 패널.
- 공간 수정 시 사업장 잠금, 상위 공간 선택지는 같은 사업장의 다른 공간만. "MES 사업장·공간과 별개" 안내.
- 도움말 `content/help/fems/f-09.md`를 구현에 맞게 수정(없는 "비활성화" 제거, 시간대·사업장 고정·순환 규칙 추가).

## 테스트

- `backend/tests/test_fems_sites.py` **20개**. 기존 `test_fems_equipment.py`(공간 목록 사용) 함께 통과.
- `frontend/src/fems/sites.test.tsx` **11개**, Playwright +1(S01 시간대 잠금 · L-INJ 삭제 시 "설비 N건") + 360px F-09.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 254 passed |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest | 332 passed (15분 8초) |
| `tools/run_portal_smoke.py` | 47 passed (360px F-09 포함) |

첫 스모크에서 새 e2e 1건 실패 → 수정 후 재실행 통과: 폼의 고정 안내 문구도 "시간대를 바꿀 수 없습니다"를 포함해 서버 응답 전에 확인이 통과했고, 늦게 온 응답이 삭제 확인 상태를 지웠다. 서버 메시지에만 있는 문구로 기다리게 했다.

backend 전체가 15분을 넘었다(FS-018l 12분 19초). Codex의 conftest 단축이 급해지고 있다.

schema.json·마이그레이션·conftest·test_common·test_seed 변경 0.

## FS-018 FEMS 종료 요약

| 하위 ID | 화면 |
|---|---|
| 018a~h | F-11·F-10·F-14(기준정보) · F-02 계측 · F-03 배분 · F-04 배출 · F-01 대시보드 · F-07 목표 · F-08 요금 |
| 018i | F-05 생산량 |
| 018j | F-06 원단위 + 업무 기준일 `FS_TODAY` |
| 018k | F-13 환산·배출계수 |
| 018l | F-12 계측기·채널 |
| 018m | F-09 사업장·공간 |

남은 사용자 결정: 사용 중 채널의 배수 변경 허용 유지 여부(`FEMS_FS-018l.md`). `content/help/fems/f-14.md`의 없는 "비활성화" 문구(도움말 담당 확인).
다음: FS-019 ERP(Codex) · FS-020 MES — `docs/agent/MES_ERP_작업계획_FS-019_020.md`.
