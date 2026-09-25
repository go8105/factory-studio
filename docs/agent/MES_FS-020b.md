# FS-020b 완료 보고 — M-14 공정 경로 · M-15 BOM

작성일: 2026-09-25 · 브랜치 `fs-020b-mes-route-bom` (main `8294164` = FS-020a) · 작업자 Claude Code

## 범위

기준정보의 마지막 두 화면. 둘 다 **버전 관리**(초안 → 게시 → 폐기)다. FS-020 진행 2/7, MES 기준정보 M-10~M-15 완료.

## API — `/api/v1/mes`

| 경로 | 동작 |
|---|---|
| `GET /routes` · `GET /boms` | 버전 전체 + `steps` / `lines` |
| `POST /routes` `{itemId, routeCode}` · `POST /boms` `{itemId, bomCode}` | 새 초안. 경로 번호는 경로 코드별, BOM 번호는 품목별 다음 번호 |
| `POST /{routes,boms}/{id}/revise` | 게시·폐기 버전을 복사해 다음 번호 초안. BOM은 `{bomCode}` 필수(코드가 버전마다 유일) |
| `PUT /routes/{id}/steps` `{processIds}` · `PUT /boms/{id}/lines` `{lines}` | 초안의 공정 순서 / 구성 자재를 요청 순서대로 통째로 교체(순서 번호 1, 2, 3 … 서버 부여) |
| `POST /{routes,boms}/{id}/publish` · `/retire` | draft → published(`published_at`) → retired(경로만 `retired_at`) |
| `DELETE /{routes,boms}/{id}` | 초안만, 참조(작업지시·자재 투입) 없을 때. 자식 함께 삭제 |

## 규칙 (schema.json SERVICE 구현)

- **게시·폐기 버전 불변**: 단계·구성 교체 409 `VERSION_LOCKED`. 초안 개정 409 `IS_DRAFT`, 같은 경로 코드(BOM은 같은 품목)에 초안이 있으면 409 `DRAFT_EXISTS`.
- 게시·폐기는 정해진 순서만(409 `INVALID_TRANSITION`), 자식이 없으면 게시 409 `EMPTY_VERSION`.
- 경로 코드가 이미 있으면 새로 만들지 않고 개정한다(400 `fields.routeCode`). 같은 공정을 두 번 거치는 경로(재검사)는 허용.
- BOM 자재: 만들 품목 자신 금지(SERVICE 자기 참조), 같은 자재 중복 금지(UK), **단위는 자재 기준 단위 또는 등록된 환산 단위**, 소요량 > 0, 손실률 0 이상 100 미만. 오류는 400 `fields.lines` = "N번째 자재: …".
- 게시된 버전을 새로 게시해도 이전 게시 버전은 자동 폐기하지 않는다(명시적 폐기). 작업지시가 어느 게시 버전을 고를지는 FS-020c에서 다룬다.
- 버전 흐름 두 종류를 `service.Versioned` 명세 하나로 공통 처리. 게시·폐기 엔드포인트는 클로저로 대상 상태를 고정했다(함수 인자로 두면 FastAPI가 쿼리 파라미터로 받아 `?target=`으로 상태를 바꿀 수 있었다 — 작성 중 발견해 수정).

## 화면

- `Routes.tsx`(M-14): 버전 목록(상태 배지, 상태별 작업 버튼), 새 경로 폼, 선택한 버전의 공정 순서 표. 초안이면 위로·아래로·빼기·공정 추가·순서 저장.
- `Boms.tsx`(M-15): 버전 목록, 새 BOM / 개정 폼(다음 코드 `…-V2` 제안), 구성 자재 표. 초안이면 자재·소요량·단위(기준+환산만)·손실률 편집.
- `common.tsx`: `StatusBadge`, `versionButtons`(초안: 게시·삭제 / 게시: 개정·폐기 / 폐기: 개정). 공통 CSS 추가 없음(순서도 기존 표 사용).
- 도움말 m-14(없는 "순서 번호 중복 거부" → 자동 번호·초안 규칙), m-15(자재·단위·코드 규칙) 수정.

## 테스트

- `backend/tests/test_mes_route_bom.py` **24개**(자재 규칙 5개 매개변수 포함).
- `frontend/src/mes/versions.test.tsx` **8개**, Playwright +2(RT-C100 개정 → 순서 변경 → 게시, 게시된 BOM 잠금) + 360px 2화면.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 274 passed |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest | 384 passed (6분 28초) |
| `tools/run_portal_smoke.py` | 58 passed |
| tools unittest / db:validate / audit / git diff --check | 통과 |

schema.json·마이그레이션·conftest·test_common·test_seed 변경 0.

## 다음

FS-020c M-02 생산계획 · M-03 작업지시(배정 합계 ≤ 계획수량, 게시된 경로·BOM만, 발행 시 LOT 생성, 취소 사유).
