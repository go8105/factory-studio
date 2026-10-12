# antigravity 인계 (2026-10-12)

AGENTS.md §8의 antigravity 몫: **확립된 패턴의 반복 화면(조회·단순 CRUD)·설정·도움말/흐름맵 정적 파일·테스트 보강.**
별도 브랜치에서 작업하고 Codex 또는 사용자 리뷰 후 main에 병합한다.

아래를 그대로 antigravity에 붙여 넣는다.

---

Factory Studio 저장소에서 작업한다. `/Users/hwang-kyoungho/projects/factory-studio`

## 0. 먼저 읽는다 (추측 금지)

| 순서 | 문서 | 왜 |
|---|---|---|
| 1 | `AGENTS.md` | 프로젝트 작업 규칙 전부. §7 UI 기준, §8 네 역할 |
| 2 | `docs/plan/현재기획_진행현황.md` | **현재 상태의 단일 기준본** |
| 3 | `docs/plan/독립솔루션_전환결정_FS-013.md` | 아키텍처 전제(충돌하면 이쪽이 우선) |
| 4 | `docs/README.md` | 문서 지도 |
| 5 | `docs/progress.md` 최신 몇 항목 | 최근 작업 이력 |
| 6 | `docs/agent/HANDOFF.md` 맨 위 | 최근 함정 |

화면 도움말을 쓸 때 더 읽는 것:
- 그 솔루션의 설계서 `docs/modules/<솔루션>/*_설계_*.md`·`*_보강설계_*.md`의 **5장 화면 목록**
- 이미 있는 도움말 2~3편 (`content/help/mes/m-13.md`, `content/help/spc/s-01.md`) — **형식을 그대로 따른다**
- 그 화면의 코드 (`frontend/src/<솔루션>/*.tsx`) — 실제로 되는 것만 쓴다

## 1. 첫 작업: 빠진 화면 도움말 7편

메뉴에는 있는데 도움말 파일이 없어 **"? 도움말"을 누르면 '찾을 수 없음'이 뜬다.**

| 파일 | 화면 | 경로 | 설계서 |
|---|---|---|---|
| `content/help/mes/m-16.md` | M-16 불량·사유 코드 | `/mes/codes` | `docs/modules/mes/MES_보강설계_DSN-12.md` |
| `content/help/mes/m-17.md` | M-17 작업자·근무조 | `/mes/workers` | 〃 |
| `content/help/mes/m-19.md` | M-19 라벨 양식 | `/mes/labels` | 〃 |
| `content/help/mes/m-26.md` | M-26 공정 검사 기준 | `/mes/inspection-items` | 〃 |
| `content/help/hr/h-16.md` | H-16 내 근무 | `/hr/work` | `docs/modules/hr/HR_설계_DSN-30.md` |
| `content/help/hr/h-17.md` | H-17 근무 체험 | `/hr/work-demo` | 〃 |
| `content/help/hr/h-18.md` | H-18 사용자 관리 | `/hr/users` | 〃 |

### 형식 (기존 도움말과 똑같이)

```markdown
# 화면 이름

## 이 화면에서 하는 일
한두 문장. 무엇을 하는 자리인지.

## 주요 동작
- **항목**: 설명. 규칙이 있으면 규칙을 적는다.

## 체험 순서(예시 데이터)
1. 게스트 공간의 예시 데이터로 따라갈 수 있는 순서.

## 이럴 때 막힙니다
- **증상**: 왜 막히는지와 어디서 푸는지(화면 ID).

## 관련 화면
- M-07 실적 확정 · M-13 공정

<!-- sources: MES_보강설계_DSN-12.md §5(M-16), 영역 01 -->
```

### 지킬 것
- **실제로 되는 것만 쓴다.** 화면 코드를 열어 확인하고, 없는 버튼·없는 기능을 쓰지 않는다.
- 첫 줄 `# 제목`이 목록에 그대로 쓰인다. 제목은 화면 이름과 같게.
- 한글로 쓴다. '제언'·'권고' 대신 '제안'.
- **굵게 표시를 문장부호 바로 뒤에서 닫고 글자를 붙이지 않는다** — `**…)**가`는 CommonMark에서 안 닫힌다. `**…**(…)가`로 쓴다. 검사하는 테스트가 있다.
- 검증: `npx --prefix frontend vitest run src/portal` (도움말 계약 테스트가 여기 있다)

## 2. 그다음 (사용자 확인 후 하나씩)

- 흐름 맵 보강: `content/flow-map.json` + `content/flow-map.schema.json` + `frontend/src/portal/flow.test.ts`를 **함께** 고친다(노드 수가 스키마와 테스트에 박혀 있다).
- 확립된 패턴의 조회·단순 CRUD 화면: 반드시 `frontend/src/shared/master.tsx`의 `MasterScreen`에 **선언만 넘긴다**. 새로 만들지 않는다. 본보기: `frontend/src/hr/Departments.tsx`, `frontend/src/mes/Labels.tsx`.
- 테스트 보강.

## 3. 반드시 지킬 것

### 브랜치
- **별도 브랜치**(예: `antigravity/help-docs`). main에 직접 커밋·푸시하지 않는다. 병합은 리뷰 후.
- 같은 폴더를 다른 세션이 동시에 쓴다. **디렉터리 단위 `git add` 금지** — 파일 경로를 하나씩 스테이징한다. `.env`·`work/`는 절대 넣지 않는다.
- `git push --mirror` 금지. 원격 push는 사용자 확인 후.

### 하지 않는 것 (네 몫이 아니다)
- 마이그레이션·`docs/db/schema-metadata/*.json`·DB 스키마 변경
- 인증·세션·멱등 키·SERVICE 정책·트랜잭션이 있는 화면·동시성
- 각 유형의 첫 구현(패턴이 아직 없는 것)
- 사용자가 고친 UI 파일 덮어쓰기

이런 것이 필요해 보이면 **만들지 말고 보고한다.**

### 코드를 건드릴 때
- 프런트 기준정보 화면은 `shared/master.tsx`의 `MasterScreen`. 탭으로 여러 `MasterScreen`을 갈아끼우면 **`key`를 준다** — 안 그러면 목록이 그대로 남는다.
- 백엔드는 `fs/common/engine.py`(조회 트랜잭션·쓰기 한 건·CSRF/멱등 키)와 `fs/common/master.py`(선언형 CRUD)를 쓴다. 복사해 새로 만들지 않는다.
- 다른 솔루션 값은 읽기 전용 `fs/<솔루션>/interface.py`로만 읽는다. 업무 스키마 간 FK 금지(FS-013 §6).
- UI: 백자 `#F7F7F6`, 먹색 `#1A1C1E`, 쪽빛 `#1F2D3D`, 단색 SVG 라인 아이콘, 그림자 최대 4%, 저채도 상태 배지.

### 검증
- 프런트: `npx --prefix frontend vitest run src` · `tsc --noEmit -p frontend/tsconfig.json` · `eslint src` · `npm --prefix frontend run build`
- 백엔드(건드렸을 때만): `cd backend && TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/ -q -m "not perf" -n 4`
  (접속값은 저장소 루트 `.env`. `set -a && . ./.env && set +a`)
- 린트: `backend/.venv/bin/ruff check --config backend/pyproject.toml backend` + `ruff format --check`
- **미실행 검증을 통과로 적지 않는다.** 무엇을 검증했고 무엇을 안 했는지 명시한다.
- 문법 검사만으로 완료 처리하지 않는다. 브라우저로 실제 화면을 확인한다
  (`.claude/launch.json`의 backend 8000 · frontend 5173. uvicorn에 `--reload`가 없어 백엔드를 고치면 다시 띄운다).

## 4. 끝낼 때

- `docs/plan/현재기획_진행현황.md`와 `docs/progress.md`를 **반드시 함께** 갱신한다. 갱신하지 않은 작업은 완료가 아니다.
- `docs/agent/HANDOFF.md`에 브랜치·마지막 커밋·끝난 것·다음 할 일·주의점·재현 명령을 남긴다.
- 30분 작업마다 WIP 커밋.
- 작업 ID 하나씩 끝내고 보고한 뒤 사용자 확인을 기다린다. 확인 전 다음 ID를 시작하지 않는다.
- 답변은 [기획 의도 검토] → [예상 문제점/제약] → [질문] → [권장안] 순서로.
