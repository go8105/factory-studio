# antigravity 개발 인계 (D84, 2026-10-12부터)

AGENTS.md §8 D84: **Claude Code는 설계·기획·리뷰·다음 진행만 하고, 개발은 antigravity가 한다.**
Claude Code가 작업마다 아래 **§2 틀**로 프롬프트를 만들어 준다. 이 문서는 그 틀과 **읽을 폴더 지도**다.

---

## 1. 읽을 폴더 지도

프롬프트는 파일을 하나씩 나열하지 않는다. **폴더를 가리키고 무엇을 찾을지** 적는다.

| 폴더 | 무엇이 있나 | 언제 읽나 |
|---|---|---|
| `AGENTS.md` (저장소 뿌리) | 작업 규칙 전부. §3 설계 불변 규칙, §4 변경 관리, §5 검증, §7 UI 기준, §8 역할 | **항상, 맨 먼저** |
| `docs/plan/` | 제품 기획·결정·단계 계획. **`현재기획_진행현황.md`가 현재 상태의 단일 기준본**, `독립솔루션_전환결정_FS-013.md`가 아키텍처 전제(충돌 시 우선), `개발계획_DSN-99.md`가 단계(W…) 계획 | **항상** — 기준본과 FS-013은 필수 |
| `docs/modules/<솔루션>/` | 그 솔루션의 설계서. `*_모듈설계_*.md`(기존)와 `*_보강설계_DSN-*.md`(확장). **4장 DB·5장 화면 목록·6장 교차 조회·7장 결정 기록**이 핵심 | 그 솔루션을 건드릴 때 |
| `docs/db/` | `schema-metadata/schema.json`(제품 설계·실제 DB와 1:1), `schema-metadata/schema-target.json`(승인된 목표 설계), `DB설계서.xlsx`, 검증 보고서 | DB를 건드릴 때 |
| `docs/architecture/` | 계층·ERD(`erd/`, `erd-target/`) | 표 사이 관계를 볼 때 |
| `docs/ui/` | `디자인시스템_UI-01.md`, `공통UI규약_UI-02.md`, 메뉴 적용표 | 화면을 만들 때 |
| `docs/agent/` | **작업별 구현·검증 보고서**(과거 이력). 파일이 100개가 넘으니 **통째로 읽지 말고** 프롬프트가 가리킨 것만. `HANDOFF.md`는 최근 함정 모음이라 맨 위 몇 항목은 항상 | 비슷한 과거 작업을 참고할 때 + HANDOFF는 항상 |
| `docs/progress.md` | 작업 이력. 최신 몇 항목 | **항상** |
| `content/help/<솔루션>/` | 화면 도움말 정적 파일(`<화면id 소문자>.md`) | 도움말을 쓸 때 |
| `content/` | `flow-map.json`·`flow-map.schema.json`(전체 흐름), `systems.json`(시스템 카탈로그), `cards/` | 흐름 맵·런처를 건드릴 때 |
| `backend/src/fs/common/` | 공통 엔진. `engine.py`(조회 트랜잭션·쓰기 한 건·CSRF/멱등), `master.py`(선언형 CRUD), `scope.py`, `page.py` | 백엔드를 만들 때 **먼저** |
| `backend/src/fs/<솔루션>/` | 그 솔루션 코드. `router.py`·`schema.py`·`service.py`·`interface.py`(읽기 전용 교차 조회) | 그 솔루션을 건드릴 때 |
| `backend/seed/` | 시드 생성기(`generate.py`·솔루션별 파일)·복사(`copy.py`)·검증(`validate.py`)·버전(`common.py`) | 시드를 건드릴 때 |
| `backend/tests/` | 테스트. 비슷한 파일을 본보기로 삼는다 | 항상 |
| `frontend/src/shared/` | `master.tsx`(기준정보 화면 엔진), `components.tsx`, `hooks.tsx`, `styles.css`, `menuCatalog.ts` | 화면을 만들 때 **먼저** |
| `frontend/src/<솔루션>/` | 그 솔루션 화면 | 그 솔루션을 건드릴 때 |
| `tools/` | `build_migration.py`(마이그레이션 생성), `apply_*.py`(목표 설계 → 제품 설계), `validate_db_design.py`, `build_erd.py`, `verify_ddl_matches_schema.py`, `deploy.sh` | DB·배포를 건드릴 때 |

**읽지 않아도 되는 곳**: `docs/archive/`, `work/`, `prototypes/`(시제품), `node_modules`.

---

## 2. 프롬프트 틀 (Claude Code가 작업마다 채운다)

```
Factory Studio 저장소에서 <작업 ID: 이름>을 개발한다.
/Users/hwang-kyoungho/projects/factory-studio

## 0. 읽을 것 (폴더로 찾는다. 추측 금지)
- `AGENTS.md` — 작업 규칙 전부
- `docs/plan/` — `현재기획_진행현황.md`(현재 상태 기준본), `독립솔루션_전환결정_FS-013.md`(아키텍처 전제)
- `docs/modules/<솔루션>/` — <어느 장을 왜 보는지>
- `docs/agent/HANDOFF.md` 맨 위 — 최근 함정
- `docs/progress.md` 최신 몇 항목
- <그 밖에 이 작업에 필요한 폴더와 찾을 것>

## 1. 범위
<무엇을 만드는지. 표·화면·API를 구체적으로.>

### 범위에서 뺀다
<하지 않을 것과 이유.>

## 2. 단계 (하나씩 끝내고 보고, 확인 전 다음 단계 금지)
| ID | 내용 |

## 3. 이 작업에서 특히 조심할 것
<Claude Code가 설계·리뷰에서 찾아낸 함정. 이게 이 프롬프트의 핵심이다.>

## 4. 공통 규칙
→ 아래 §3 그대로

## 5. 끝낼 때
→ 아래 §4 그대로
```

---

## 3. 공통 규칙 (모든 프롬프트에 붙인다)

### 브랜치
- **별도 브랜치**(예: `antigravity/<작업ID>`). main에 직접 커밋·푸시하지 않는다. 병합은 사용자 리뷰 후.
- 같은 폴더를 다른 세션이 동시에 쓴다. **디렉터리 단위 `git add` 금지** — 파일 경로를 하나씩 스테이징한다. `.env`·`work/`는 절대 넣지 않는다.
- `git push --mirror` 금지. 원격 push는 사용자 확인 후. 30분 작업마다 WIP 커밋.

### 설계 불변 규칙 (AGENTS.md §3, 어기면 되돌려야 한다)
- 범위 키는 `S = (workspace_id, generation_id)`. 모든 업무 FK는 `(S, 참조id)` 복합 참조, 삭제는 RESTRICT.
- **업무 스키마 간 FK 금지.** 타 솔루션 값은 코드 문자열 스냅샷. 예외는 `core.workspace`·`core.data_generation`뿐.
- `core`는 인증·공간·세대·운영만 소유한다. core → 업무 스키마 FK 금지.
- 연·월·주차는 정수가 아니라 문자열(`'YYYY-MM'`, `'YYYY-Www'`)로 저장하고 CHECK로 강제한다.
- 확정·게시·검증된 데이터는 바꾸지 않는다. 재산정은 새 버전.
- 도움말·흐름 맵은 DB가 아니라 리포지토리 정적 파일에 둔다.

### DB를 건드릴 때
- 설계는 `docs/db/schema-metadata/schema-target.json`에 **이미 있다**. 손으로 표를 쓰지 말고 `tools/apply_*.py`를 본떠 목표에서 그대로 옮긴다.
- **제약 이름은 `schema.json`의 `constraints` 배열 순번이다**(`c342_check`의 342). 새 제약은 **반드시 배열 끝에만** 붙인다. 중간에 끼우면 운영 DB의 제약 이름이 전부 어긋난다. 정의가 바뀌는 제약만 제자리에서 고친다.
- 마이그레이션은 손으로 쓰지 않는다: `git show HEAD:docs/db/schema-metadata/schema.json > /tmp/prev.json` 뒤 `python3 tools/build_migration.py --revision … --down … --tables '<스키마>.*' --previous /tmp/prev.json --out backend/alembic/versions/…`
- 기존 표에 더하는 칼럼은 **NULL 허용이거나 기본값이 있어야 한다**(운영에 데이터가 있다).
- **서로를 가리키는 FK(고리)를 만들면** 게스트 정리(`fs/core/service.py::_cleanup_plan`)와 시드 복사(`seed/copy.py::_table_order`)가 깨진다. 만들어야 하면 그 칼럼을 NULL 허용으로 두고 두 곳을 반드시 테스트한다.
- 같은 작업에서 함께 갱신: `npm run db:validate` → `npm run db:build` → `python3 tools/build_erd.py`. 적용한 DB 대조: `DATABASE_URL=… python tools/verify_ddl_matches_schema.py`(오류 0).

### 코드
- 백엔드는 `backend/src/fs/common/`의 `engine.py`·`master.py`를 쓴다. 복사해 새로 만들지 않는다.
- 프런트 기준정보 화면은 `frontend/src/shared/master.tsx`의 `MasterScreen`에 **선언만 넘긴다**. 본보기: `frontend/src/hr/Departments.tsx`, `frontend/src/mes/Labels.tsx`. 탭으로 여러 `MasterScreen`을 갈아끼우면 **`key`를 준다**(안 그러면 목록이 그대로 남는다).
- 등록(POST) 본문은 기본값까지 보낸다(`_values(payload, …, full=True)`). 안 그러면 DB 기본값이 없는 칸에서 NOT NULL에 걸린다.
- 다른 솔루션 값은 **읽기 전용 `fs/<솔루션>/interface.py`** 함수로만 읽는다. 쓰기·직접 SQL 금지. 꺼졌거나 시드가 없으면 `None`(0건과 구분).
- UI는 `docs/ui/디자인시스템_UI-01.md`를 따른다. 백자 `#F7F7F6`, 먹색 `#1A1C1E`, 쪽빛 `#1F2D3D`, 단색 SVG 라인 아이콘, 그림자 최대 4%, 저채도 상태 배지.
- 사용자 대상 텍스트는 전부 한글. 사용자가 고친 UI 파일을 임의로 덮어쓰지 않는다.

### 시드
- 시드를 바꾸면 `backend/seed/common.py`의 `SEED_VERSION`을 올린다 → **다음 배포에서 템플릿을 다시 만든다**(배포가 길어진다).
- 행 수가 기준일에 따라 달라지는 표는 `seed/validate.py`의 `DATE_VARYING`에.
- 합성 데이터만. 실제 회사·고객 데이터·비밀정보를 파일·로그·Git에 넣지 않는다.

### 테스트·검증
- 빈 공간을 전제하는 테스트는 모듈에 `EMPTY_MODULES = ("<솔루션>",)`를 선언한다. 안 하면 화면을 처음 열 때 지연 복사가 시드를 넣어 깨진다.
- 백엔드: `set -a && . ./.env && set +a` 뒤 `cd backend && TEST_DATABASE_URL=… .venv/bin/python -m pytest tests/ -q -m "not perf" -n 4`
- 프런트: `npx --prefix frontend vitest run src` · `tsc --noEmit -p frontend/tsconfig.json` · `eslint src` · `npm --prefix frontend run build`
- 린트: `backend/.venv/bin/ruff check --config backend/pyproject.toml backend` + `ruff format --check`
- GitHub Actions가 막히면 `npm run ci:local`
- **미실행 검증을 통과로 적지 않는다.** 무엇을 검증했고 무엇을 안 했는지 명시한다.
- 문법 검사만으로 완료 처리하지 않는다. **브라우저로 실제 화면을 확인한다**(`.claude/launch.json`의 backend 8000 · frontend 5173. uvicorn에 `--reload`가 없어 백엔드를 고치면 다시 띄운다).
- 테스트가 기존에 실패하고 있었는지 먼저 확인한다(`git stash` 후 재실행). 내 변경 탓이 아니면 건드리지 말고 보고한다.

---

## 4. 끝낼 때 (모든 프롬프트에 붙인다)

- `docs/plan/현재기획_진행현황.md`와 `docs/progress.md`를 **반드시 함께** 갱신한다. 갱신하지 않은 작업은 완료가 아니다.
- `docs/agent/HANDOFF.md`에 브랜치·마지막 커밋·끝난 것·다음 할 일·주의점·재현 명령을 남긴다.
- 작업 ID 하나씩 끝내고 보고한 뒤 사용자 확인을 기다린다. 확인 전 다음 ID를 시작하지 않는다.
- 보고는 **무엇을 만들었는지 · 무엇을 검증했는지 · 무엇을 안 했는지 · 남은 위험** 순서로.
- 설계와 다르게 만들어야 할 이유가 생기면 **만들지 말고 보고한다.**

---

## 5. 지금 쌓여 있는 작업

| 작업 ID | 내용 | 프롬프트 |
|---|---|---|
| ANTI-HELP-01 | 빠진 화면 도움말 7편(MES M-16·17·19·26, HR H-16·17·18) | [ANTI-HELP-01](ANTI-HELP-01_도움말7편.md) |
| W2a-1b2-rest | MES 공정 경로(M-14)·BOM(M-15) 보강 | [W2a-1b2-rest](W2a-1b2-rest_MES경로BOM.md) |
