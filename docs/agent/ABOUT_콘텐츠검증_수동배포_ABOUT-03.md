# ABOUT-03 — 공개 콘텐츠 검증·누적 main 수동 배포

2026-11-08 · 사용자 ABOUT-02 확인 후 ABOUT-03·로컬 main 병합·수동 배포 요청.

## 결과

- ABOUT-02·03 완료(2/6). 운영 [자기소개](https://eip.hugh-d.com/about) 공개. ABOUT-04~07은 미착수이며 다음 단계는 사용자 확인 후 진행한다.
- 제품 변경 `98a34d1`, 로컬 main fast-forward 반영. 운영 배포 커밋 **`d932345`**, 원격 main push 후 표준 `tools/deploy.sh --skip-ci-check` 실행. 그 뒤 최종 기록 커밋은 문서만이며 운영 제품과 구분한다.
- 기존 운영 `6df6e71`/`gw_wms_merge`에서 **`bems1`**, 실제 DDL **262표·2960열·644FK**로 승격. 운영과 누적 main의 차이를 설명하고 사용자에게 **누적 main 전체 배포**를 명시적으로 승인받았다. ABOUT만 격리해서 배포한 것이 아니다.

## ABOUT-03 변경

- `content/about/profile.json`: 설계서 4장의 소개·경력2·프로젝트17 본문·스택6그룹·수상/교육12 항목 대조. 이지스의 누락된 `시연 요청 시`를 `linkLabel`로 보완.
- `frontend/src/portal/About.tsx`: 펼친 카드에서 JSON 시연 안내 표시, document.title도 profile 문안 사용. 개인정보를 담은 원본 자료·PDF 추가 없음.
- `frontend/src/portal/about.test.tsx`: 실제 개인 분류/카드 전환으로 시연 안내 렌더링 확인. 소개 테스트 7건.
- ABOUT-02의 Figma 차이는 유지: 코드의 기존 Pretendard 글꼴, 설계서 전체 문안·17카드·6스택 그룹을 우선해 줄바꿈/높이 차이. 노트0편·PDF없음으로 숨김. 공통 CSS·백엔드·스키마 구현 변경 없음.

## 배포 전 실제 검증

- 프런트 typecheck/lint/format:check/test/build 모두 성공. **100파일854건**.
- 새 고유 `_test` DB를 만든 뒤 `FS_CI_WORKERS=0 TEST_DB=factory_studio_ci_about03_20261108_test bash tools/ci_local.sh` 전체 1~5단계 성공. 병렬 불안정 이력 때문에 직렬로 실행했다.
- 도구144건, Ruff/포맷, 새 DB migration/실DDL 대조0, backend **2830 pass/54 skip/1 deselected**, perf **1 pass**, `downgrade base → upgrade head`/DDL 대조0, 프런트 854건·빌드/정리까지 성공. 18:19~19:50 KST. backend 직렬만 87분17초.
- 54 skip은 해당 실행의 조건부 미실행이며 통과로 합산하지 않는다. SQLAlchemy/Starlette 경고, 기존 CAD/WASM·500kB 청크 경고, jsdom 문서 이동 안내가 있었지만 최종 종료0.
- 제품 소스 기준98a34d1 이후 실행 중 WIP 커밋들은 문서와 읽기 전용 검증 스크립트만 추가. 배포 전 frontend/backend/content/deploy.sh 차이0 확인.
- GitHub Actions 결과는 배포 게이트로 사용하지 않았다. `--skip-ci-check`는 위 실제 전체 로컬CI로 게이트를 대체한 것이며 GitHub CI 성공으로 기록하지 않는다.

## 보호 백업과 배포 과정

- 백업은 서버에만 보관. 최초 `/srv/factory-studio/backups/20261108-about03-98a34d1`, 최종 `/srv/factory-studio/backups/20261108-about03-final-r2`(디렉터리700/파일600). DB custom dump·복원목록·기존 프런트/비공개 자산 tar·체크섬·코드 기준·테이블 건수 기록. 실제 DB/환경값을 로컬이나 Git으로 반출하지 않음.
- Factory Studio API/정리 타이머·서비스를 중지한 뒤 최종 DB dump. 이지스 서비스·DB·Nginx 설정은 변경하지 않음.
- **실행 중 보정:** SSH `bash -s`의 표준 입력을 `docker compose exec -T ... pg_dump`가 소비해 백업 뒤 TOC/tar/건수 명령 일부가 실행되지 않았다. DB dump 자체는 변경 전에 완료됐다. 발견 후 배포 프로세스를 일시 정지했지만 당시 마이그레이션은 이미 완료된 상태였다. TOC·tar·체크섬 검사를 보완했다.
- 정확한 변경 전 기준을 얻기 위해 최종 dump를 새 고유 검증 DB에 실제 복원하고 원본12스키마의 테이블 건수를 다시 산출했다. 검증 DB는 삭제했다. **운영 DB를 과거로 복원하거나 덮어쓰지 않았다.** 향후 SSH 스크립트에서 입력이 필요 없는 docker exec 명령은 `< /dev/null`로 표준 입력을 닫는다.
- 이후 표준 배포 재개: 앱 소유자로 코드 fast-forward/의존성·alembic head, 시드 일치 확인, 관리자 자산 웹 루트 밖 업로드, API 재시작, 프런트 업로드. 시드 `sv-20261018-wms1` 동일해 **템플릿 재생성 없음**. 19:53 KST 배포 완료.
- 별도 생성 빌드 worktree 자동 제거. 로컬 CI DB 및 서버 복원검증 DB 삭제 확인. FS API/정리 타이머 재가동 확인.

## 배포 후 실제 확인

- 운영 HEAD d932345·alembic bems1·작업 트리 깨끗함. 원점/공개200, 실DDL 대조0, 배포 직후 최근2분5xx0.
- 변경 전 dump에서 복원한 **기존210표 모두 건수 감소 없음**. 이는 건수 대조이며 모든 행의 값 동일성을 증명한 것으로 표현하지 않는다.
- FS API/정리 타이머·secretary-api/secretary-scheduler/nginx active, 이지스 office200. 이지스 업무 데이터 조회/변경 없음.
- `node docs/agent/assets/about03/public-check.mjs` 실제 공개 URL Chromium 성공: 1440×900 본문880px·Hero·탭·펼침/접힘·시연 안내·목차 현재 항목·노트0편 숨김·전화 패턴없음·소개 API 요청0, 390×900 목차숨김/가로넘침없음, 기존 진입 화면 표시, pageerror0. 운영 캡처를 눈으로 확인했다. 출력은 기본 `work/about-03-public/` 임시 파일이다.

## 남은 것

- ABOUT-04 기술 노트 glob·목록·본문·없는 slug, ABOUT-05 로그인 링크, ABOUT-06 OG/Nginx 블록 보고, ABOUT-07 공개 PDF 버튼은 미구현. 이번 Nginx 변경 없음.
- 사용자 공개 PDF·실제 노트 원고 없음. 로그인한 운영 사용자별 전 솔루션 업무·실회사10인/GW 외부 보관/전체 회수 인수는 이번에 검증하지 않았다. 기존 GW ready=false/PARTIAL 등 인수 제한을 해제하지 않는다.
- 재현: 위 전체CI 명령(새 고유 테스트 DB 사용), `node docs/agent/assets/about03/public-check.mjs`. 배포 후 검사는 공개 화면 읽기 전용이며 로그인·업무 쓰기를 하지 않는다.
