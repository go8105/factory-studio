# FS-018b 완료 보고 — F-02 계측 조회 (조회 화면 패턴)

작성일: 2026-09-24 · 브랜치 `fs-018b-fems` (AG-05 `00df47e`에서 분기) · 작업자 Claude Code

## 범위

FEMS 조회 화면 패턴의 기준 구현으로 F-02 계측 조회를 만들었다. AG-05(F-10 설비) 검토·재현도 이 브랜치에 포함된다. FEMS 진행 3/14(F-02·F-10·F-11).

## 구현

### API

| 경로 | 내용 |
|---|---|
| `GET /api/v1/fems/readings` | `from`·`to`(사업장 시간대 날짜), `siteId`·`meterId`·`channelId`·`energySourceId`·`quality`, `sort=observedAt:asc|desc`, offset 페이지. 응답에 `range` |
| `GET /api/v1/fems/meters` | 계측기 + 채널 목록(필터 선택지) |
| `GET /api/v1/fems/sites` | 사업장 목록(읽기 전용. F-09 CRUD가 이 경로를 확장한다) |

확정한 규칙:

- **기간 경계**: 계측값은 구간 끝 시각(`observed_at`)에 기록된다. 날짜 `D`는 `(D 00:00, D+1 00:00]`(계측기 사업장 `timezone`)이다. 00:00 관측값은 전날 23~24시다.
- **기간 기본값**: 기간을 주지 않으면 가장 최근 계측일까지 7일. 빈 화면으로 시작하지 않는다. `from`만 또는 `to`만 주면 400, 역순 400, 31일 초과 400(`details.fields`).
- **결측**: 시드는 결측을 `value=0, quality='invalid'`로 저장한다(FS-005g 5.2). API는 **`invalid` 행의 `value`를 `null`로 내보낸다.** 0이 소비량으로 합산되는 경로를 API 경계에서 끊는다. 행 자체는 남긴다(채널 1일 = 24행).
- 값은 문자열(FS-010 §3-5), 조회는 REPEATABLE READ 읽기 전용, 모듈 꺼짐 409.

### 화면 (`frontend/src/fems/Readings.tsx`)

- 필터 한 줄: 시작일·종료일(`<input type="date">`), 계측기, 채널(계측기에 종속), 에너지원, 품질. **초안과 적용값을 분리**해 조회 버튼을 눌러야 요청한다.
- 첫 진입은 기간 없이 요청하고 서버가 정한 기간을 입력 칸에 채운다(같은 조회를 두 번 보내지 않는다).
- 표(기본): 관측 시각(사업장 시간대 표시)·계측기·채널·에너지원·값(결측은 "결측")·단위·품질 배지(정상/추정/리셋/결측, 텍스트 병기).
- 선 그래프: **채널을 하나 골랐을 때만** 그린다(단위가 다른 채널을 한 축에 그리지 않는다). 결측 구간은 선을 끊고 캡션에 건수를 적는다. 쪽빛 2px 단일 선, 십자선 + 시각·값 안내. 한 번에 200건 요청.
- FEMS 진입(`/fems`)은 F-02로 간다(F-01 대시보드 전까지). 사이드바에 "에너지 현황" 그룹 추가.
- 사업장 필터 UI는 두지 않았다. 시드 사업장이 1개라 선택지가 의미 없다. API는 `siteId`를 받는다. 사업장이 2개 이상이 되면 선택지를 추가한다.
- 해상도 선택기 없음(FS-008a F-02: 1시간 고정).

### 그 밖의 변경

- `GUEST_LIMIT` 환경 변수(기본 20, 제품 동작 불변). 브라우저 스모크가 테스트마다 새 게스트를 만들어 23개가 되자 전역 상한 20에 걸렸다(20 통과 후 3개 실패를 실제로 재현). `tools/run_portal_smoke.py`는 테스트 서버에만 200을 준다. `.env.example`에 주석 추가.
- AG-05 후속: `test_fems_equipment.py` import 정렬(저장소 ruff 설정 기준 I001), `equipments.test.tsx` 사이드바 개수를 `femsScreens.length`로(F-02 추가로 2→3이 되어 실패하던 것). `energy-sources.test.tsx`의 "FEMS 진입" 테스트는 진입 화면이 F-02로 바뀌어 F-11 직접 경로로 고쳤다.

## AG-05 검토 결과

- 보고와 저장소 일치: 11파일, 설비 CRUD + `/locations`, `LOCATION_IN_USE` 수정과 테스트 2개. main에서 ff 가능.
- 재현: frontend 96, backend 87 통과.
- **보고와 다른 점**: 저장소 설정(`--config backend/pyproject.toml`)으로 ruff를 돌리면 `test_fems_equipment.py` I001이 난다. 보고서의 ruff는 설정 없이 실행한 결과로 보인다. 같은 I001이 `test_common.py`(AG-04)에도 있으나 antigravity 소유라 수정하지 않았다.

## 테스트 (항목별 분리)

- `backend/tests/test_fems_readings.py` **18개**: 기본 기간 / 기본 기간 행 수(9×7×24+7+7) / 하루 = 사업장 시간대 경계 / 결측 null / 채널 목록에 결측 행 유지 / 값 문자열 / 채널 필터 / 에너지원 필터 / 품질 enum / from만 400 / 역순 400 / 31일 초과 400 / 내림차순 / 정렬 화이트리스트 / 다른 공간 채널 0건 / 모듈 꺼짐 409 / 계측기·채널 목록 / 사업장 목록.
- `frontend/src/fems/readings.test.tsx` **14개**: 진입 리다이렉트 / 사이드바 그룹 / 첫 조회 기간 채움 / 중복 조회 없음 / 결측 표시 / 품질 배지 / 조회 전 무요청 / 조회 조건 전달 / 계측기→채널 종속 / 그래프 200건 / 채널 미선택 안내 / 결측 선 끊김 / 기간 오류 표시 / 모듈 꺼짐.
- Playwright `fems.spec.ts` +3(런처→F-02 기간 채움, 결측 6건 표시, 채널 선 그래프) + 360px F-02.

## 실행 검증

Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6. backend `factory_studio_fs016_test`, 브라우저 `factory_studio_fs017_test`, 순차 실행.

| 명령 | exit | 결과 |
|---|---:|---|
| frontend typecheck / lint / format:check / build | 0 / 0 / 0 / 0 | 번들 경고 없음 |
| `npm --prefix frontend test` | 0 | 110 passed |
| ruff check / format --check (backend/src, FEMS 테스트 3개, 스모크 도구) | 0 / 0 | |
| backend 전체 pytest | 0 | 105 passed |
| `tools/run_portal_smoke.py` | 0 | Playwright 23 passed |
| tools unittest | 0 | 44 passed |
| db:validate / audit_schema_isolation / git diff --check | 0 / 0 / 0 | |

실패 이력: (1) 새 화면 테스트 5개가 "결측" 셀 2개(값·배지)에 단수 조회를 써서 실패 → 복수 조회로 수정. (2) 스모크 20 통과 후 3개가 게스트 상한으로 실패 → `GUEST_LIMIT`. (3) 직후 재실행이 "port 8000 사용 중"으로 중단(직전 종료 소켓) → 재실행 통과.

schema.json·마이그레이션·content·conftest·test_common·test_seed 변경 0.

## 조회 화면 복제 가이드 (F-03 등 후속)

1. API: repository에 `FROM ... JOIN`을 S 조건 포함으로 정의하고 필터는 화이트리스트 dict(`READING_FILTERS`)로 붙인다. 날짜 기간은 사업장 시간대 기준으로 서버에서 변환한다. 기본 기간을 서버가 정해 `range`로 돌려준다.
2. 품질이 `invalid`인 값은 API에서 `null`. 합계를 내는 화면(F-01·F-03·F-06)은 **서버 집계에서 invalid를 제외**한다(FS-005g 5.2).
3. 화면: 초안/적용값 분리 필터, 표 기본, 그래프는 단위가 하나일 때만.

## 남은 것

- 계산 화면 F-01·F-03~F-08(TX-06·계수·요금 규칙). F-07은 목표=실적×95% 문제를 사용자 판단.
- antigravity 후보: F-14 요금제는 적용 기간 겹침 정책 결정 후. F-09는 공간 계층(자기 참조) 때문에 Claude Code/Codex.
