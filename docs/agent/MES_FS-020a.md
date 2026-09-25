# FS-020a 완료 보고 — MES 뼈대와 기준정보(M-10~M-13)

작성일: 2026-09-25 · 브랜치 `fs-020a-mes-master` (main `9d896fd`) · 작업자 Claude Code
병행: Codex는 `../factory-studio-codex`에서 FS-019 ERP 진행.

## 범위

MES 첫 작업. `/api/v1/mes` 라우터, `frontend/src/mes` 모듈·사이드바, 기준정보 4화면. FS-020 진행 1/7.
포털 홈의 MES 바로가기와 FEMS 사이드바의 MES 링크를 도움말에서 실제 화면(`/mes` → M-10)으로 바꿨다.

## API — `/api/v1/mes`

| 경로 | 동작 |
|---|---|
| `/sites` · `/locations` · `/equipments` | 목록(페이지 없음, 사업장 규모) · 단건 · 등록 · 수정 · 삭제 |
| `/items` | 위와 같음. 목록에 `conversions` 포함 |
| `/items/{id}/conversions` | 단위 환산 등록 · 수정 · 삭제 |
| `/processes` | 위와 같음. 목록·응답에 `equipmentIds`(허용 설비), 등록·수정 본문에 `equipmentIds`를 주면 통째로 교체 |

변경은 CSRF + `Idempotency-Key`, `write_scope("mes")` 뒤, 멱등 영수증. 입력 오류 400 `fields`, 삭제 409 `REFERENCED_BY_OTHERS` + 건수.

**구조**: 다섯 종류가 같은 흐름이라 `mes/repository.py`의 표 명세(`Master`: 테이블·컬럼·코드·코드 범위·삭제 참조)와 `mes/service.py`의 공통 create/update/delete로 처리하고, 화면마다 다른 검사만 `check_*` 함수로 넘긴다. 라우터는 `_register`로 목록·단건·등록·수정·삭제를 한 번에 등록한다(이 모듈만 `from __future__ import annotations`를 쓰지 않는다 — FastAPI가 본문 타입을 실제 클래스로 읽어야 한다). `fems/`는 import하지 않는다(FS-011 §3).

## 규칙

- 사업장: 시간대 IANA 이름만. MES 기록은 시각(timestamptz)으로 저장하고 사업장 시간대로 날짜를 묶는 계산이 아직 없어 FEMS의 `TIMEZONE_IN_USE` 잠금은 두지 않았다(M-01 대시보드 등에서 필요해지면 추가).
- 공간: 사업장은 등록 후 고정(상위 공간 복합 FK), 상위 공간은 같은 사업장·순환 금지(SERVICE), 코드는 사업장 안에서 유일.
- 설비: 공간 존재 확인. 사용 여부(`isActive`)는 이후 공정 실행의 "활성 설비" 검사(SERVICE)에 쓰인다. 삭제 ← 공정 허용 설비·공정 실행.
- 품목: **기준 단위 변경은 단위 환산·작업지시가 있으면 409 `UNIT_IN_USE`**(복합 FK (품목, 단위) → item(id, base_unit)). 삭제 ← 단위 환산·공정 경로·BOM·BOM 자재·생산계획·작업지시·자재 투입.
- 단위 환산: 결과 단위는 서버가 품목 기준 단위로 정한다. 환산 전 단위 ≠ 기준 단위, 품목당 한 번, 계수 > 0. 다른 품목 경로로 삭제하면 404.
- 공정: 허용 설비는 존재하는 설비만. 삭제 ← 공정 경로 단계, 허용 설비 연결은 함께 지운다.

## 화면 — `frontend/src/mes/`

- `common.tsx`: 목록 불러오기(`useLists`), 저장·삭제(`useSend`, CSRF·멱등 키·삭제 2단계), 등록 순서, 모듈 꺼짐 안내.
- M-10 `Sites.tsx`(FEMS와 별개 안내), M-11 `Equipments.tsx`(사용 안 함 배지), M-12 `Items.tsx`(ERP와 별개 안내, 품목 → 단위 환산 마스터-디테일, "1 BOX = 10,000 EA"), M-13 `Processes.tsx`(허용 설비 체크 목록, 없으면 경고 배지).
- 도움말: m-10(없는 "비활성화" 제거, 사업장 고정·순환 규칙), m-12(기준 단위 잠금·환산 규칙) 수정. m-11·m-13은 실제 동작과 일치.
- **공통 스타일 수정(별도 커밋)**: 360px 스크린샷에서 폼 체크박스가 글자와 분리돼 보였다. 전역 `input { width: 100% }`와 `.field label { display: block }`이 원인. `.inline-check` 전체로 보정을 넓혔다(FEMS 폼의 "사용" 체크박스도 함께 고쳐짐).

## 테스트

- `backend/tests/test_mes_master.py` **28개**(`guest_space` fixture).
- `frontend/src/mes/master.test.tsx` **12개**, `entry-home.test.tsx` MES 링크 기대값 갱신. Playwright `e2e/mes.spec.ts` 3개 + 360px 4화면.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 266 passed |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest | 360 passed (6분 11초) |
| `tools/run_portal_smoke.py` (스타일 수정 후 재실행) | 54 passed |
| tools unittest / db:validate / audit / git diff --check | 통과 |

schema.json·마이그레이션·conftest·test_common·test_seed 변경 0.

## 다음

FS-020b M-14 공정 경로 · M-15 BOM(게시 버전 불변, 새 버전으로 개정).
