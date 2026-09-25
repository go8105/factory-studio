# FS-018l 완료 보고 — F-12 계측기·채널

작성일: 2026-09-25 · 브랜치 `fs-018l-f12` (main `a5209b6`) · 작업자 Claude Code

## 범위

계측값이 쌓이는 계측기와 채널의 기준정보 화면(설계서 §6 "F-12만의 구조": 마스터-디테일, 배수 ≠ 1 강조). FEMS 진행 13/14.

## API — `/api/v1/fems/meters`

| 메서드·경로 | 동작 |
|---|---|
| `GET /meters` | **기존 F-02용 응답을 확장**: 계측기 전체 + `channels`. 계측기에 `locationId`·`equipmentId`·`parentMeterId`·`scopeKind`·`channelCount`·`observed`, 채널에 `measurementKind`·`isActive`·`observed` 추가(기존 필드 유지) |
| `GET /meters/{id}` | 단건(채널 제외) |
| `POST` · `PATCH /{id}` · `DELETE /{id}` | 계측기 |
| `POST /meters/{id}/channels` · `PATCH`·`DELETE /meters/{id}/channels/{cid}` | 채널 |

별도 채널 목록 GET은 두지 않았다(목록 응답에 포함). 변경은 CSRF + `Idempotency-Key`, `write_scope` 뒤.

## 규칙 (schema.json SERVICE/DB_POLICY 구현)

- **사업장은 서버가 정한다**: 공간의 `site_id`. 설비는 **같은 공간**만, 상위 계측기는 **같은 사업장**만(복합 FK와 같은 조건을 400 필드 오류로 먼저 알린다).
- **부모 순환 방지**: 지정하려는 상위 계측기의 조상(재귀 CTE)에 자신이 있으면 400 `fields.parentMeterId`. 자기 자신도 같은 오류.
- **사용 중 = 채널에 계측값 또는 배분 결과가 있음**(`observed`).
  - 사용 중 계측기의 공간·설비·**상위 계측기** 변경 409 `PRECONDITION_NOT_MET` `reason=METER_IN_USE` + `fields`·`references`. 상위 계측기를 넣은 이유: 최상위 여부가 배출량·대시보드 합계 대상을 정하므로 바꾸면 지난 합계가 달라진다.
  - 사용 중 채널의 에너지원·측정 종류·단위 변경 409 `reason=CHANNEL_IN_USE`.
  - 이름·코드·범위·배수·사용 여부는 바꿀 수 있다.
- **누적 채널 단위 = 에너지원 계측 단위**(400 `fields.unit`). 환산·배출·요금이 누적 채널 값을 계측 단위로 보기 때문. 순시(kW 등)만 다른 단위 허용.
- 배수 > 0(소수 6자리), 채널 코드는 계측기 안에서 유일, 계측기 코드는 전체에서 유일.
- 삭제 RESTRICT 409 `REFERENCED_BY_OTHERS` + 건수: 계측기 ← 하위 계측기·채널, 채널 ← 계측값·배분.

## 화면 — `frontend/src/fems/Meters.tsx`

- 위: 계측기 목록 + 등록/수정 패널. 목록의 "채널 N" 버튼으로 계측기를 고르면 아래에 그 계측기의 채널 목록 + 채널 패널. 새 계측기를 등록하면 바로 채널 관리로 넘어간다.
- 배수 ≠ 1은 목록에서 경고 배지(`× 80`), 입력 중에는 "합계·요금·배출량이 함께 바뀐다" 안내.
- 사용 중인 계측기·채널은 잠긴 필드를 비활성화하고 이유를 적는다. 설비 선택지는 고른 공간의 설비만.
- 누적 채널은 에너지원을 바꾸면 단위가 계측 단위로 따라간다.
- 도움말 `content/help/fems/f-12.md`를 구현에 맞게 수정(설비는 채널이 아니라 계측기에 연결, 계측기에는 활성 여부가 없음, 잠금·순환·단위 규칙 추가).

## 테스트

- `backend/tests/test_fems_meters.py` **25개**. 기존 `test_fems_readings.py`(F-02가 쓰는 목록 응답)도 그대로 통과.
- `frontend/src/fems/meters.test.tsx` **12개**, Playwright +1(M-MAIN 채널 단위 잠금, 배수 2 저장 → 배지) + 360px F-12.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 243 passed |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest | 312 passed (12분 19초) |
| `tools/run_portal_smoke.py` | 45 passed (360px F-12 포함) |

첫 스모크에서 2건 실패 → 수정 후 재실행 통과:
- 새 e2e의 행 선택 `/M-MAIN/`이 상위 계측기 열 때문에 9행에 걸림 → `/^M-MAIN/`.
- 기존 F-03 "추정 1일" 테스트: 날짜 입력 직후 첫 조회 응답이 서버 기본 기간으로 입력을 덮어쓰는 경쟁(이번 변경과 무관, 간헐). 테스트가 첫 로드를 기다린 뒤 입력하도록 고쳤다. 실제 화면에서도 로드 전에 입력하면 같은 일이 생길 수 있다(Allocations.tsx `range` 적용 조건).

schema.json·마이그레이션·conftest·test_common·test_seed 변경 0.

## 판단이 필요할 수 있는 것

- **사용 중 채널의 배수 변경을 허용했다.** 정책(SERVICE)이 금지하지 않고, 설치 오류를 바로잡는 정정이 필요하다. 다만 배수는 조회 시 곱해지므로 **지난 합계도 함께 바뀐다**. 화면에서 경고만 한다. 금지하거나 이력을 남기려면 결정이 필요하다.

## 남은 것

F-09 사업장·공간(FEMS 마지막 화면).
