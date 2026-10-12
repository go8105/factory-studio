# W2a-1b2-rest — MES 공정 경로(M-14)·BOM(M-15) 보강

> antigravity용 프롬프트. 공통 규칙·폴더 지도는 [ANTIGRAVITY_인계.md](ANTIGRAVITY_인계.md).

Factory Studio 저장소에서 W2a-1b2-rest를 개발한다.
`/Users/hwang-kyoungho/projects/factory-studio`

## 0. 읽을 것 (폴더로 찾는다. 추측 금지)

- `AGENTS.md` — 작업 규칙 전부. §3 설계 불변 규칙
- `docs/plan/` — `현재기획_진행현황.md`(현재 상태 기준본), `독립솔루션_전환결정_FS-013.md`(아키텍처 전제)
- `docs/modules/mes/` — `MES_보강설계_DSN-12.md`의 **F16 대체 자재**·공정 경로 장, 그리고 4장 DB·5장 화면 목록
- `docs/db/schema-metadata/` — `schema.json`에서 `mes.route_step`·`mes.bom_line`·`mes.bom_substitute` **칼럼 정의**. 이 작업에서 **DB는 바꾸지 않는다**(아래 §3 첫 줄)
- `backend/src/fs/mes/` — `repository.py`(`STEP`·`LINE`·`Master`), `service.py`(`ROUTES`/`BOMS`·`set_children`·`validate_steps`·`validate_lines`·`replace_children`), `schema.py`(`RouteSteps`·`BomLineIn`), `router.py`(`PUT /routes/{id}/steps`·`PUT /boms/{id}/lines`)
- `backend/src/fs/common/` — `engine.py`·`master.py`. 새로 만들지 말고 이걸 쓴다
- `frontend/src/mes/` — `Routes.tsx`·`Boms.tsx`(고칠 화면), `versions.test.tsx`(함께 고칠 테스트)
- `backend/tests/` — `mes` 버전/경로/BOM 테스트
- `docs/agent/HANDOFF.md` 맨 위 · `docs/progress.md` 최신 몇 항목

## 1. 범위

표와 칼럼은 **이미 DB에 있다**(W2a-1a 마이그레이션 `backend/alembic/versions/20261008_w2a1_mes.py`에서 만들었다). 아무도 안 쓰고 있을 뿐이다. 이번 작업은 **응용 계층만** 만든다.

### M-14 공정 경로 — 단계별 속성

`mes.route_step`의 `standard_cycle_sec`(numeric 10,2, NULL) · `setup_minutes`(int, NULL) · `is_subcontract`(bool, NOT NULL) · `subcontractor_code`(varchar 40, NULL)를 쓰게 한다.

- `repository.STEP`의 컬럼 목록에 네 칼럼을 더한다.
- `schema.RouteSteps`를 `processIds: number[]`에서 **단계 객체 목록**으로 바꾼다:
  `steps: [{ processId, standardCycleSec?, setupMinutes?, isSubcontract, subcontractorCode? }]`
- `service.validate_steps`가 새 칸을 검사하고 `sequence_no`를 요청 순서대로 다시 매긴다. 외주가 아니면 `subcontractorCode`는 비운다.
- `Routes.tsx`에서 단계마다 네 칸을 넣고 편집한다.

### M-15 BOM — 투입 공정 + 대체 자재

- `mes.bom_line.issue_process_id`(NULL): 그 자재를 **어느 공정에서 투입**하는지. `repository.LINE`·`BomLineIn`·`validate_lines`·`Boms.tsx`에 더한다. 비우면 "공정 지정 안 함".
- `mes.bom_substitute`(대체 자재, DSN-12 F16): `bom_line_id`·`substitute_item_id`·`priority`·`ratio`. 구성 자재 한 줄의 **자식**으로 편집한다.

### 범위에서 뺀다

- **마이그레이션·`schema.json`·ERD·`schema-target.json` 변경 없음.** 이미 맞다. 손대면 되돌려야 한다.
- 오투입 검사(F42)에서 대체 자재를 **실제로 쓰는** 동작은 이번이 아니다. 지금은 **목록을 만들어 두는 것까지**.
- 다단 BOM 전개는 하지 않는다(설계상 1단계 전개만).
- 시드 변경은 하지 않는다 — 새 칸은 전부 NULL 허용이거나 기본값이 있다. (`SEED_VERSION`을 올리면 다음 배포가 길어진다.)

## 2. 단계 (하나씩 끝내고 보고, 확인 전 다음 단계 금지)

| ID | 내용 |
|---|---|
| R-1 | M-14 백엔드: `STEP` 컬럼·`RouteSteps` 본문·`validate_steps`·테스트 |
| R-2 | M-14 화면: `Routes.tsx` 단계별 칸 + `versions.test.tsx` 수정 |
| R-3 | M-15 백엔드: `bom_line.issue_process_id` (`LINE`·`BomLineIn`·`validate_lines`) |
| R-4 | M-15 대체 자재: `bom_substitute` 조회·편집 API |
| R-5 | M-15 화면: `Boms.tsx` 투입 공정 + 대체 자재 |

## 3. 이 작업에서 특히 조심할 것

1. **요청 본문 모양이 바뀐다.** `RouteSteps.processIds: number[]` → 객체 목록. 이걸 보내는 곳이 화면·테스트·(있다면) 시드에 흩어져 있다. **먼저 `processIds`를 전부 grep해서 목록을 만든 뒤** 고치기 시작한다. 하나 빠지면 조용히 400이 난다.
2. **대체 자재는 손자다.** `bom_substitute`는 `bom_version` → `bom_line` → `bom_substitute`로 **두 단계 아래**다. 기존 `service.set_children`/`repo.replace_children`은 **부모–자식 한 단계만** 다룬다. 구성 자재를 통째로 갈아끼우면 `bom_line.id`가 바뀌어 대체 자재가 날아가거나 FK에 걸린다.
   → **`PUT /boms/{id}/lines`로 대체 자재까지 같이 보내지 말 것.** 대체 자재는 `/boms/{id}/lines/{lineId}/substitutes`처럼 **별도 경로**로 다룬다. 그리고 구성 자재 교체가 대체 자재를 어떻게 처리하는지(같이 지운다 / 교체를 막는다) **결정해서 보고**한다. 설계서에 답이 없으면 만들지 말고 물어본다.
3. **게시·폐기된 버전은 못 고친다**(`VERSION_LOCKED`). 대체 자재도 똑같이 초안에서만 편집해야 한다 — 새 경로에서 이 검사를 빠뜨리기 쉽다.
4. **버전 조회 응답에 자식이 실린다**(`service._with_children`가 `steps`/`lines`를 붙인다). 새 칸이 여기로도 나가는지 확인한다.
5. `is_subcontract`는 **NOT NULL**이다. 등록 본문에 기본값을 실어 보낸다(`_values(..., full=True)`). 안 그러면 NOT NULL에 걸린다.
6. `issue_process_id`는 MES 안의 `mes.process`를 가리킨다 — 다른 솔루션 값이 아니다. 업무 스키마 간 FK 금지 규칙과 무관하다.
7. `numeric`·비율은 **문자열로 주고받는다**(기존 `qtyPerUnit`·`lossRate`와 같은 방식). float로 바꾸지 않는다.
8. **기존에 실패하던 테스트가 하나 있다**: `backend/tests/test_gw_projects.py::test_flow_migration_roundtrip_preserves_records_and_favorites`. 깨끗한 트리에서도 실패한다. 네 탓이 아니니 고치려 들지 말고 보고만 한다.
9. 다 만든 뒤 **브라우저로 `/mes/routes`·`/mes/boms`를 실제로 열어** 등록·수정·게시까지 해 본다. 테스트 통과만으로 완료 처리하지 않는다.

## 4. 공통 규칙

→ `docs/agent/ANTIGRAVITY_인계.md` §3

## 5. 끝낼 때

→ `docs/agent/ANTIGRAVITY_인계.md` §4. 특히 2번의 결정(구성 자재 교체 시 대체 자재 처리)을 `docs/modules/mes/`의 결정 기록에 남긴다.
