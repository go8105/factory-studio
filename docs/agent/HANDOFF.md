# Factory Studio 작업 인계

갱신: 2026-09-24 (FS-018h 완료, Claude Code). 다음 작업자는 Codex 또는 Claude Code일 수 있다.

## Git 상태

- 저장소: `/Users/hwang-kyoungho/projects/factory-studio` **메인 폴더만 사용**.
- 브랜치: **`fs-018h-billing`**, main `dc4071f`(FS-018g까지 origin push 완료)에서 분기. AG-07(`6f99461`) 위로 rebase했고 사이드바 결함 2건을 이 브랜치에서 고쳤다. `git fetch . fs-018h-billing:main`이 AG-07까지 함께 ff한다.
- 구현·인계 커밋: `FS-018h: F-08 요금 산정`. WIP `1a31436` 포함. 최종 HEAD는 `git log -1 --oneline`.
- main 병합·push는 사용자만 한다(`git fetch . fs-018-fems:main`, ff만).
- `../factory-studio-ag`는 main `2cece7b` 기준이다. antigravity 작업 전 최신 main에서 새 `antigravity/*` 브랜치를 만들어야 한다.

## FS-018h에서 끝난 것

- F-08 요금 산정(`GET /billing`, `frontend/src/fems/Billing.tsx`). 대시보드 요금도 `service._billing`을 쓴다.

## FS-018g에서 끝난 것

- F-07 목표 대비 실적(`GET /targets/performance`, `frontend/src/fems/Targets.tsx`). F-14 사이드바 그룹 기준정보로 이동. 스모크 포트 검사 수정.

## FS-018f에서 끝난 것

- F-01 대시보드(`GET /dashboard`, `frontend/src/fems/Dashboard.tsx`). FEMS 진입 화면. 계산 규칙은 FS-010 §7, `docs/agent/FEMS_FS-018f.md`.

## FS-018e에서 끝난 것

- 에너지 목표 = 월 실적 × 월·대상별 90~105% 비율표(`backend/seed/common.py TARGET_RATIOS`). seed `sv-20260924-2`. `test_seed.py` V8 쿼리 1개 수정(antigravity에 알릴 것).
- 로컬 개발 DB의 기존 템플릿은 옛 값. 새 비율을 보려면 `seed.cli template` 재실행.

## FS-018d에서 끝난 것

- F-04 배출량(`GET /emissions`, `frontend/src/fems/Emissions.tsx`). 규칙은 FS-010 §7과 `docs/agent/FEMS_FS-018d.md`. F-01은 이 계산(service.emissions)을 재사용한다.
- AG-06 F-14 요금제 검토 완료.

## FS-018c에서 끝난 것

- F-03 설비별 배분(`GET /allocations`, `frontend/src/fems/Allocations.tsx`). 현재 결과 판정·이전 결과 토글·단위별 합계·계산 근거 패널. 상세 `docs/agent/FEMS_FS-018c.md`.
- 사용자 결정: F-14 요금제 적용 기간 겹침은 409 `PERIOD_OVERLAP`(FS-010 §7).

## FS-018b에서 끝난 것

- F-02 계측 조회(`GET /readings`·`/meters`·`/sites`, `frontend/src/fems/Readings.tsx`). 조회 패턴과 복제 가이드: `docs/agent/FEMS_FS-018b.md`.
- 결측(`quality=invalid`)은 API에서 `value=null`. 합계 화면은 서버 집계에서 invalid를 제외해야 한다.
- `GUEST_LIMIT` 환경 변수(기본 20). 스모크 테스트 서버만 200.
- AG-05(F-10) 검토·재현, ruff import 정렬 1건 수정.

## FS-018a에서 끝난 것

- FEMS 레이아웃(좌측 사이드바, `femsScreens`에 구현 화면만) + F-11 에너지원 CRUD. 런처 FEMS 카드 → `/fems`.
- `backend/src/fs/common/scope.py`: 업무 API의 세대·모듈 재확인과 공간 잠금. **ERP·MES도 이것을 쓴다.**
- `backend/src/fs/fems/`: router/schema/service/repository. 규칙은 FS-010 §7 "FS-018a에서 확정한 업무 API 공통 규칙".
- 공통 컴포넌트: `PageTitle help`, `ErrorNotice` 참조 건수 목록, `DataTable empty`. `api()`는 `/api/`로 시작하는 경로를 그대로 호출.
- FEMS·도움말 lazy 로딩(번들 경고 해소).
- 상세·antigravity 복제 가이드: `docs/agent/FEMS_FS-018a.md`.

## 다음 할 일

1. 남은 FEMS 화면(사용자 승인 순서): F-05 생산량 등록(확정 불변·새 버전) → F-06 원단위(생산량 0이면 "생산량 없음") → F-09 사업장·공간(자기 참조 계층), F-12 계측기·채널(마스터-디테일), F-13 환산·배출계수(PRIMARY/EMISSION 탭).
2. 제안: 모바일 FEMS 사이드바 접기(작은 작업, antigravity 가능), backend 테스트 시간 단축(conftest, Codex).

## 주의점

- schema.json·마이그레이션 변경 금지. `test_common.py`·`test_seed.py`는 antigravity 소유, `conftest.py`는 Codex 소유.
- 업무 쓰기는 반드시 `write_scope` 뒤에 한다. 세션의 generation_id를 그대로 쓰지 않는다(초기화 경합).
- 마스터 CRUD는 audit_event를 남기지 않는다(결정 보류, FS-021).
- 흐름 맵 `energy_master` 노드는 아직 도움말 연결. content 계약 변경은 FEMS 화면이 더 생긴 뒤.
- `.env`에 SESSION_SECRET(32자 이상)이 필요하다. 테스트는 프로세스에 합성 값을 주입한다.

## 실제 검증 (FS-018h 최종 코드)

Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6. 모두 exit 0: frontend typecheck/lint/format/build/test(194), ruff check/format, backend 전체 pytest 217(`factory_studio_fs016_test`), `tools/run_portal_smoke.py` Playwright 37(`factory_studio_fs017_test`), tools unittest 44, db:validate, audit_schema_isolation, git diff --check. pytest와 브라우저는 순차 실행.

## 재현 명령

```sh
cd /Users/hwang-kyoungho/projects/factory-studio
export PATH="/opt/homebrew/opt/node@24/bin:$PWD/backend/.venv/bin:$PATH"
uv sync --project backend --python 3.14 --locked
npm --prefix frontend ci
python --version
node --version
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
npm --prefix frontend test
```

기존 마이그레이션이 적용된 별도 `_test` DB로 백엔드를 검증한다. 접속 URL은 출력하지 않는다.

```sh
uv run --project backend --env-file .env python - <<'PY'
import os, subprocess
from sqlalchemy.engine import make_url
url = make_url(os.environ['DATABASE_URL']).set(database='factory_studio_fs016_test')
assert url.database.endswith('_test')
os.environ['TEST_DATABASE_URL'] = url.render_as_string(hide_password=False)
subprocess.run(['uv', 'run', '--project', 'backend', 'pytest', 'backend/tests', '-q'], check=True)
PY
python -m unittest discover -s tools -v
npm run db:validate
python tools/audit_schema_isolation.py
npm --prefix frontend exec -- playwright install chromium
uv run --project backend --env-file .env python tools/run_portal_smoke.py
git diff --check
```

브라우저 runner는 **factory_studio_fs017_test만 매 실행 초기화**한 뒤 템플릿 7,469행과 테스트 서버를 준비한다. 제품 DB는 변경하지 않는다. 8000/5173에 기존 서버가 있으면 먼저 사용자가 종료해야 하며, runner는 기존 프로세스를 종료하지 않는다. PostgreSQL/새 테스트 DB 준비와 IntelliJ 작업 디렉터리·환경변수는 README 참조. 검증 원문은 work/fs017c/post-rebase-verification.json에 있으나 Git 제외이며 위 명령으로 재현 가능하다.

브라우저 스모크(전용 DB 초기화·서버 시작/종료 포함, 8000·5173 포트가 비어 있어야 함):

```sh
uv run --project backend --env-file .env python tools/run_portal_smoke.py
```
