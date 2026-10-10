# GW·HR main 운영 배포 검증 — 2026-10-10

- 사용자 승인: 현재 main을 실서버에 배포하도록 명시 요청.
- 제품 커밋: `98402d978428a60bd070bda910f740fca234f765`; 이전 운영 `31af096`.
- 공개 서비스: https://eip.hugh-d.com
- 실행: `FS_DEPLOY_BUILD_DIR=work/deploy-build-98402d9 tools/deploy.sh` (실제 실행 시 절대 경로 사용). CI 우회 없음, 스크립트 exit0.
- 완료 시각: 2026-10-10 19:33 KST.

## 반영 범위

GW 회사 공동 프로젝트 보드·네 보기·내 업무, HR 회사 공동 근무/PWA·사용자 관리 및 앞서 main에 포함된 변경을 배포했다. Factory Flow 독립 시스템·계층 업무일지는 설계 문서/HTML 시제품 단계이며 운영 제품으로 구현된 기능이 아니다. FLOW-01 전체 설계 확인 후 FLOW-02 개발 예정.

## 배포 전 검사

CI https://github.com/go8105/factory-studio/actions/runs/38044267825 success. backend1004 passed/1 skipped, 별도 perf1 passed; frontend75파일588 passed. DB 설계/격리/Ruff/서식/upgrade/DDL/downgrade base/upgrade 왕복/도구 검사와 프런트 타입/lint/서식/빌드 통과.

기존 CI 실패 원인인 `20261010_gw_projects.py` Ruff 서식과 `Users.test.tsx` Prettier 서식만 보정했다. migration AST/SQL 의미 변경 없음. 테스트 파일 보정 후 해당4검사·전체 서식·빌드도 로컬 재검증했다.

## 백업과 실제 반영

서버 백업 경로 `/srv/factory-studio/backups/20261010-projects-71d140a`: `database.dump`, `frontend-private.tar.gz`, `commit.txt`. 디렉터리700·파일600, pg_restore 목록/gzip 검사 성공. 백업 이후 운영 변경 전까지 서버는31af096이었으므로 후속 서식 커밋에도 동일 백업을 사용했다. 데이터/비밀번호는 이 문서에 포함하지 않는다.

서버 코드를98402d9로 fast-forward, 의존성 동기화, alembic `gw_projects` 적용, 프런트·비공개 자산 업로드, API 재시작 완료. 코드/운영 템플릿 시드가 모두 `sv-20261009-gw1`이라 템플릿을 재생성하지 않았다. 빌드 worktree는 스크립트 종료 시 제거했다.

## 운영 검증과 한계

API 서비스 active, 실제 서버 git98402d9/alembic gw_projects. 원점·공개 HTTP200, 운영 DDL 대조0오류, 배포 직후 최근2분5xx0. curl에서 `/`, `/gw/projects`, `/gw/my-tasks`, `/hr/users` 및 index JS/CSS200. 미로그인 `/api/v1/core/sessions/current`, `/api/v1/gw/projects/companies`401으로 인증 보호 확인. SPA 경로200은 로그인 후 업무 동작 검증을 대신하지 않는다.

Python urllib 기본 요청은 Cloudflare403이었고 curl 공개/원점 확인은 정상이다. 운영 실제 계정 로그인·쓰기·실제 휴대폰 PWA 설치는 미검증. 실제 회사/사용자/비밀번호 변경 없음, 사용자 로컬 서버8000/5173와 브라우저 확장 유지.

후속 배포 기록 커밋은 문서만 main에 push하며 운영 제품98402d9와 구분한다. 실패 시 백업 복구는 별도 작업으로 서버 중지·DB/파일 일관성 확인 후 수행하며 이번 배포에서는 복구 불필요.
