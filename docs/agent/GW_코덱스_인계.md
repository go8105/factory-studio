# GW 코덱스 인계 (2026-10-09, D83)

AGENTS.md §8의 D82(Codex 업무 중단)를 **GW에 한해** 되돌린 결정이다.
Codex가 DSN-31 체험 범위를 `codex/gw-*` 브랜치에서 맡고, Claude Code는 W2a 이후를 이어간다.
**ERP 확정 통제(F44, `erp.approval_policy`·`approval_evidence`)는 ERP 소유라 W2b에서 Claude가 한다.**

아래를 그대로 Codex에 붙여 넣는다.

---

Factory Studio 저장소에서 GW(그룹웨어) 보강 개발을 맡는다.
`/Users/hwang-kyoungho/projects/factory-studio`

## 0. 먼저 읽는다 (추측 금지)

1. `AGENTS.md` — 프로젝트 작업 규칙 전부
2. `docs/plan/현재기획_진행현황.md` — 현재 상태의 단일 기준본
3. `docs/plan/독립솔루션_전환결정_FS-013.md` — 아키텍처 전제(충돌 시 우선)
4. `docs/agent/HANDOFF.md` 맨 위 몇 항목 — 최근 함정들
5. `docs/modules/gw/GW_보강설계_DSN-31.md` — 이번 작업의 설계서
6. `docs/plan/통합검증_DSN-90.md` §7-1·7-2 — GW 교차 조회 계약

## 1. 범위

DSN-31 "체험 범위"만. 지금 gw 8테이블 → 목표 24테이블, 화면 G-01~07 → G-13.

**없는 표 16개**: `authority_rule`, `delegation`, `organization_unit`, `person_identity_binding`,
`role_grant`, `step_assignment`, `document_reader`, `comment`, `comment_revision`,
`calendar_event`, `event_attendee`, `notification`, `chat_channel`, `chat_member`,
`chat_message`, `collaboration_settings`

**기존 표 칼럼 추가 6개**
- `approval_document` + auth_mode·authority_rule_id·drafter_org_code·drafter_org_name·policy_version
- `approval_event` + details·on_behalf_of_person_id
- `approval_step` + organization_code·organization_name·participant_role
- `board_post` + audience_org_id·visibility
- `person` + hr_employee_code·organization_unit_id
- `route_step` + participant_role

**신규 화면 6개**: G-08 전결 규칙, G-09 위임, G-10 조직도, G-11 일정, G-12 알림함, G-13 채팅
**기존 화면 확장 7개**: G-01~07

### 범위에서 뺀다
- **ERP 확정 통제(F44)** — ERP 소유라 W2b에서 Claude가 한다. 건드리지 않는다.
- **실제 도입 A 트랙**(TEAM 공간·멤버십·초대·권한, 화면 9개) — DSN-99 Q4대로 별도 트랙. 목표 DB에만 있고 개발하지 않는다.

## 2. 단계 (하나씩 끝내고 보고, 확인 전 다음 단계 금지)

| ID | 내용 |
|---|---|
| GW-a | DB: 표 16 + 기존 6표 칼럼 + 제약·FK, 마이그레이션 1 revision |
| GW-b | 결재 확장: G-02·03·04·06 · G-08 전결 · G-09 위임 (병렬·합의·전결·위임) |
| GW-c | 조직·사람: G-07·G-10, HR `employees()`·`departments()`로 "HR에서 가져오기" |
| GW-d | 협업: G-05 댓글, G-11 일정, G-12 알림함, G-13 채팅 |
| GW-e | 시드·도움말: 합성 시드 + `content/help/gw/g-08~13.md` |

## 3. 반드시 지킬 것

### 브랜치
- **별도 브랜치**(예: `codex/gw-dsn31`). main에 직접 커밋·푸시하지 않는다.
- 같은 폴더를 다른 세션이 동시에 쓴다. **디렉터리 단위 `git add` 금지** — 파일 경로를 하나씩 스테이징한다. `.env`·`work/`는 절대 넣지 않는다.
- `git push --mirror` 금지. 원격 push는 사용자 확인 후.

### DB (여기서 제일 많이 틀린다)
- 설계는 `docs/db/schema-metadata/schema-target.json`에 **이미 있다**. 손으로 표를 쓰지 말고 `tools/apply_w2a1.py`를 본떠 `tools/apply_gw_a.py`를 만들어 목표에서 그대로 옮긴다.
- **제약 이름은 `schema.json`의 `constraints` 배열 순번이다**(`c342_check`의 342). 새 제약은 **반드시 배열 끝에만** 붙인다. 중간에 끼우면 이미 적용된 운영 DB의 제약 이름이 전부 어긋난다. 정의가 바뀌는 제약만 **제자리에서** 고친다.
- 마이그레이션은 손으로 쓰지 않는다:
  ```
  git show HEAD:docs/db/schema-metadata/schema.json > /tmp/prev.json
  python3 tools/build_migration.py --revision gw_a_dsn31 --down w2a1_mes \
      --tables 'gw.*' --previous /tmp/prev.json \
      --out backend/alembic/versions/2026MMDD_gw_a_dsn31.py --title "GW-a DSN-31 스키마"
  ```
- 기존 표에 더하는 칼럼은 **NULL 허용이거나 기본값이 있어야 한다**(운영에 데이터가 있다).
- **업무 스키마 간 FK 금지**(FS-013 §6). HR·ERP 값은 코드 문자열 스냅샷. 유일한 예외는 `core.workspace`·`core.data_generation` 범위 앵커.
- 범위 키는 `S = (workspace_id, generation_id)`. 모든 업무 FK는 `(S, 참조id)` 복합 참조, 삭제는 RESTRICT.
- 연·월·주차는 정수가 아니라 문자열(`'YYYY-MM'`, `'YYYY-Www'`)로 저장하고 CHECK로 형식을 강제한다.
- **서로를 가리키는 FK(고리)를 만들면** 게스트 정리(`fs/core/service.py::_cleanup_plan`)와 시드 복사(`seed/copy.py::_table_order`)가 깨진다. 만들어야 한다면 그 칼럼을 NULL 허용으로 두고 두 곳이 고리를 끊는지 반드시 테스트한다.
- 같은 작업에서 함께 갱신: `npm run db:validate` → `npm run db:build` → `python3 tools/build_erd.py`.
  적용한 DB 대조: `DATABASE_URL=... python tools/verify_ddl_matches_schema.py` (오류 0이어야 한다)

### 코드
- 백엔드 공통 엔진을 쓴다: `fs/common/engine.py`(조회 트랜잭션·쓰기 한 건·CSRF/멱등 키), `fs/common/master.py`(기준정보 선언형 CRUD). 복사해 새로 만들지 않는다.
- 프런트 기준정보 화면은 `shared/master.tsx`의 `MasterScreen`. 특수 화면(달력·채팅·조직도 트리)만 직접 만든다.
- 등록(POST) 본문은 `_values(payload, full=True)`로 넘긴다 — 아니면 pydantic 기본값이 DB에 가지 않아 NOT NULL에 걸린다.
- 다른 솔루션 값은 **읽기 전용 `fs/<솔루션>/interface.py`** 함수로만 읽는다. 쓰기·직접 SQL 금지. 제공 솔루션이 꺼졌거나 시드가 아직 없으면 `None`(0건과 구분).
- GW가 읽는 것: HR `employees(status?)`·`departments()`, ERP `approval_documents`·`approval_document`·`approval_source_digest` — 모두 이미 있다.
- UI: 백자 `#F7F7F6`, 먹색 `#1A1C1E`, 쪽빛 `#1F2D3D`, 단색 SVG 라인 아이콘, 그림자 최대 4%, 저채도 상태 배지. 사용자가 고친 UI 파일을 임의로 덮어쓰지 않는다.
- 사용자 대상 텍스트는 전부 한글.

### 테스트
- 빈 공간을 전제하는 테스트는 모듈에 `EMPTY_MODULES = ("gw",)`를 선언한다. 안 하면 화면을 처음 열 때 지연 복사가 시드를 넣어 깨진다.
- 백엔드: `cd backend && TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/ -q -m "not perf" -n 4`
  (DB 접속값은 저장소 루트 `.env`. `set -a && . ./.env && set +a`)
- 프런트: `npx --prefix frontend vitest run src` · `tsc --noEmit` · `eslint src`
- 린트: `backend/.venv/bin/ruff check --config backend/pyproject.toml backend` + `ruff format --check`
- **미실행 검증을 통과로 적지 않는다.** 무엇을 검증했고 무엇을 안 했는지 명시한다.
- 시제품·문법 검사만으로 완료 처리하지 않는다. 브라우저로 실제 결과를 확인한다
  (`.claude/launch.json`의 backend 8000 · frontend 5173. uvicorn에 `--reload`가 없어 백엔드를 고치면 다시 띄운다).

### 시드
- 시드를 바꾸면 `backend/seed/common.py`의 `SEED_VERSION`을 올린다 → **다음 배포에서 템플릿을 다시 만든다**(배포가 길어진다).
- 행 수가 기준일에 따라 달라지는 표는 `seed/validate.py`의 `DATE_VARYING`에 넣고 수 비교 대신 규칙으로 본다.
- 합성 데이터만. 실제 회사·고객 데이터, 비밀정보를 파일·로그·Git에 넣지 않는다.

## 4. 끝낼 때

- `docs/plan/현재기획_진행현황.md`와 `docs/progress.md`를 **반드시 함께** 갱신한다. 갱신하지 않은 작업은 완료가 아니다.
- `docs/agent/HANDOFF.md`에 브랜치·마지막 커밋·끝난 것·다음 할 일·주의점·재현 명령을 남긴다.
- 30분 작업마다 WIP 커밋.
- 답변은 [기획 의도 검토] → [예상 문제점/제약] → [질문] → [권장안] 순서로. 설계·방향 지시를 받으면 바로 만들지 말고 누락·모순·리스크를 먼저 분석하고 역으로 질문한다.
- 구현 불가능한 라이브러리나 없는 기능을 있는 것처럼 제안하지 않는다.
