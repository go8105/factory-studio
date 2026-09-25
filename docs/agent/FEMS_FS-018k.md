# FS-018k 완료 보고 — F-13 환산·배출계수

작성일: 2026-09-25 · 브랜치 `fs-018k-f13` (main `5bcc4d2`) · 작업자 Claude Code

## 범위

F-04 배출량·F-01 대시보드·F-06 원단위가 쓰는 계수의 기준정보 화면. FEMS 진행 12/14.

## API — `/api/v1/fems/energy-factors`

| 메서드·경로 | 동작 |
|---|---|
| `GET` | `factorKind`(PRIMARY/EMISSION)·`energySourceId` 필터. 정렬 고정: 적용 연도 내림차순 |
| `GET /{id}` | 단건 |
| `POST` | 등록. `factorUnit`은 받지 않는다 |
| `PATCH /{id}` | 적용 연도·계수·출처만 |
| `DELETE /{id}` | 삭제 |

변경은 CSRF + `Idempotency-Key`, `write_scope` 뒤.

## 규칙

- **단위는 서버가 정한다**: `PRIMARY` → `TOE/<계측 단위>`, `EMISSION` → `tCO2eq/<계측 단위>`. 계산은 계수 단위 끝이 채널 단위와 같을 때만 계수를 쓰므로(`UNIT_MISMATCH`), 사용자가 단위를 잘못 적어 계산이 조용히 빠지는 일을 막는다. 에너지원 계측 단위는 참조 중이면 바꿀 수 없다(F-11 `UNIT_IN_USE`).
- **에너지원·유형은 등록 후 고정**: 바꾸면 단위와 탭이 함께 바뀐다. 새로 등록한다.
- **UTILITY(용수) 에너지원 거부** 400 `fields.energySourceId`: TOE 합산·배출량 계산에서 빠지는 에너지원이다.
- 에너지원·유형·연도별 1건 → 중복 400 `fields.effectiveYear`. 계수 `> 0`, 소수 6자리.
- **삭제는 자유**: energy_factor를 참조하는 테이블이 없다. 지우면 그 연도 계산은 추정 없이 `FACTOR_MISSING`(schema.json SERVICE 정책). 화면이 삭제 확인 때 이를 알린다.
- audit_event는 남기지 않는다(마스터 공통, FS-021 판단 유지).

## 화면 — `frontend/src/fems/Factors.tsx`

- 설계서대로 **탭 분리**(1차에너지 환산계수 / 온실가스 배출계수), 탭마다 용도 문구.
- 계수 입력란 라벨에 단위 미리보기(`계수 (tCO2eq/Nm3)`). 에너지원 선택지에서 용수 제외.
- 수정 시 에너지원 잠금. 삭제 2단계.
- 360px 스크린샷으로 관리 열이 가로 스크롤 뒤에 숨는 것을 확인해 적용 연도 바로 뒤로 옮겼다(F-05와 같은 처리).
- 도움말 `content/help/fems/f-13.md`를 구현에 맞게 고쳤다(없는 "비활성화"·"참조 중 삭제 불가" 제거, 단위·용수·삭제 후 계산 불가 추가).

## 테스트

- `backend/tests/test_fems_energy_factor.py` **21개**: 시드 8건 / 탭 필터 / 문자열 수치 / 단위 도출 / 단위 입력 거부 / 연도 중복 / 다른 유형 같은 연도 허용 / 0 거부 / 소수 7자리 / 연도 형식 / 용수 거부 / 다른 공간 에너지원 / 멱등 / CSRF / 수정 / 유형 변경 거부 / 수정 연도 중복 / null / 삭제 / **재등록한 계수를 배출량이 그대로 사용** / 모듈 꺼짐.
- `frontend/src/fems/factors.test.tsx` **11개**, Playwright +1(배출 탭 등록 → 서버 단위) + 360px F-13.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 231 passed |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest | 288 passed (10분 30초) |
| `tools/run_portal_smoke.py` | 43 passed (360px F-13 포함) |

schema.json·마이그레이션·conftest·test_common·test_seed 변경 0.

## 남은 것

F-12 계측기·채널(마스터-디테일, 배수 ≠ 1 강조) → F-09 사업장·공간. `content/help/fems/f-14.md`에도 없는 "비활성화"·"참조 중 삭제 불가" 문구가 있다(도움말 담당 antigravity 확인 필요).
