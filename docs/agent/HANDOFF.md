# Factory Studio 작업 인계

갱신: 2026-09-25 (Codex backend 테스트 시간 단축 진행 중). 다음 작업자는 Codex 또는 Claude Code일 수 있다.

## Git·작업 위치

- **Codex는 `/Users/hwang-kyoungho/projects/factory-studio-codex`만 사용**, 브랜치 `codex/test-speed`. 메인 폴더는 Claude Code가 사용하므로 열거나 수정하지 않는다. antigravity worktree·브랜치도 건드리지 않는다.
- `git fetch origin` 후 `origin/main 70951d4`(FS-018l F-12까지)로 rebase 완료. 측정 기준 커밋도 `70951d4`다.
- 마지막 기준 커밋 `70951d4`. 진행 중 보존 커밋 제목 `WIP test-speed: 공유 템플릿 적용 및 1차 전체 검증`; 현재 해시는 `git log -1 --oneline codex/test-speed`로 확인한다.
- main 병합·push하지 않는다. push는 사용자 확인 뒤. 병행 작업의 후속 rebase는 Claude Code가 맡는 기존 규칙을 유지한다.

## 끝난 것·진행 중

- 유효한 개선 전 전체 측정: 312 passed, exit 0, 782.272초(13분 2초). 예전 `78e1206`의 228 passed / 16 failed 측정은 날짜 고정 전이므로 무효.
- `conftest.py`: 공유 `guest_template`은 세션당 1회, `guest_space`는 실제 guest API로 테스트마다 새 공간을 만든다. `FS_TODAY=2026-09-24`·`GUEST_LIMIT=10000` 고정. 게스트만 자식 → 부모 순서로 정리하고 템플릿 보존.
- 전체 DB를 TRUNCATE하는 legacy 테스트를 먼저, 공유 템플릿 테스트를 마지막으로 안정 정렬한다. 둘을 한 테스트의 fixture로 섞으면 수집 오류. 템플릿 내용 불변·게스트 잔여 0을 세션 종료 때 검사한다.
- FEMS fixture 13개만 연결 변경. 테스트 본문 261개/보조 함수 AST 동일. `test_common.py`·`test_seed.py` 바이트 동일. 업무 코드·seed·마이그레이션·schema.json 변경 없음. 새 의존성 없음.
- 혼합 순서·격리·초기화 선택 검증 6 passed, CI 범위 Ruff check/format 모두 exit 0.
- 개선 후 전체 1회: 312 passed, exit 0, 368.737초(6분 9초). **2회차는 현재 실행 중, 아직 완료로 보고하지 않는다.**
- 상세: [테스트 시간 단축](테스트시간단축.md). 로컬 원문 로그는 Git 제외 `work/speed-before-70951d4.*`, `work/speed-after-1.*`, `work/speed-after-2.*`.

## 다음 할 일

1. 실행 중인 두 번째 전체 pytest의 종료·시간·312 passed 확인. 실패하면 수정 후 최종 코드에서 두 번 연속 다시 실행한다.
2. 보고서·현재기획 진행현황·progress·이 HANDOFF를 최종 결과로 갱신하고 `git diff --check`, 보호 파일·스테이징 제외 확인 후 커밋. 보고하고 멈춘다.
3. Claude Code의 FEMS 다음 화면은 F-09 사업장·공간. FS-018l F-12의 사용 중 채널 배수 변경 정책 후보는 `FEMS_FS-018l.md` 참조.
4. 사용자가 지정한 `docs/agent/MES_ERP_작업계획_FS-019_020.md`는 `70951d4`와 그 origin/main 트리에 없어서 읽지 못했다. 사용자에게 위치/커밋을 요청한 상태이며 메인 폴더를 열어 찾지 않았다. MES/ERP 구현은 이번 범위가 아니다.

## 재현·주의점

- **DB는 `factory_studio_codex_test`만.** `factory_studio_fs016_test`, `factory_studio_fs017_test`는 Claude Code가 사용하므로 Codex는 사용하지 않는다.
- Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6. `.env` 없이 CI 환경 변수 네 개만 전달한다. 합성 SESSION_SECRET과 업무 날짜는 fixture에서 설정한다.
- 접속 URL을 로그·Git에 넣지 않는다. `task_test_url`에 전용 DB 접속 URL을 지정한 뒤 아래 명령을 두 번 연속 실행한다. 같은 DB에 pytest를 동시에 실행하지 않는다.

```sh
cd /Users/hwang-kyoungho/projects/factory-studio-codex
env -i HOME="$HOME" PATH="/opt/homebrew/opt/node@24/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  DATABASE_URL="$task_test_url" TEST_DATABASE_URL="$task_test_url" \
  uv run --project backend pytest backend/tests -q --durations=15
uv run --project backend ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
uv run --project backend ruff format --config backend/pyproject.toml --check backend tools/verify_ddl_matches_schema.py
git diff --check
```

- Ruff는 위 CI 범위로만 실행한다(`tools` 전체 아님). schema.json·마이그레이션·backend/src·test_common.py·test_seed.py 수정 금지. conftest.py는 Codex 소유.
- 업무 구현의 확정·게시 데이터 불변, `write_scope`, 결측(invalid) 합계 제외 규칙은 그대로다.
- 30분마다 WIP 커밋, 종료 시 이 문서 갱신·커밋. `.env`·`work/`·`node_modules`는 스테이징하지 않는다.
