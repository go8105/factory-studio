# GW-READY-02 79차 — 로컬 main 병합·전체 로컬 CI 완료 (2026-11-06)

사용자가 ‘진행 전에 로컬 main에 병합’을 승인했다. GW 저장소의 b71ad85와 로컬 main1815db2를0ac0727에서 통합하고, 로컬 main도 해당 커밋으로 fast-forward했다. 병합 기록 ce06e84도 main에 반영했다. GW 개발은 계속 `factory-studio-gw-company` / `codex/gw-company-01`에서 한다. 공유 main의 코드 추가 개발·원격 push·배포·운영 DB 적용은 하지 않는다.

main 추가9커밋은 FEMS-1f/1g와 브라우저 결함 수정이다. 기존 변경을 모두 보존했고, 충돌은 HANDOFF/progress2개만 발생했다. 진행 이력을 합치고 최신 main 인계는 [참조본](main_인계_1815db2_통합참조.md)에 접속 URL을 비공개 처리해 보존했다. FEMS 완료·다음BEMS/Claude 담당과 Codex GW 담당을 구분한다. 새 schema 변경0이므로 현재251표·2833열·617FK, metadata/Excel/ERD·gw_main_ready02_merge를 그대로 유지했다.

이번 통합 소스로 정적DB/R1~R6·타입·Ruff, 프런트847pass/0skip와build0, 도구144pass를 확인했다. 이 결과를 과거822건이나 부분 backend 실행과 합산하지 않는다. 실제 API 로그인 후 브라우저·실회사10인 인수는 별도다.

소유 PG의 DB 생성 없는20회 시각 표본은 최대67.873ms,400회 표본은69.258ms/DB·host역전0이었다. 과거 약2초 불일치와 구분한다. 250ms 하네스 기준 안이지만 연속 안정성이나 실환경 인수를 증명하지 않는다. 시각·Docker·서버 설정·재시작은 하지 않았다. 전체CI를 새UUID 시험DB에서 단일 실행했고 아래 결과로 완료했다. 시각/서버설정 변경 없이 이번 검증 구간에서 보호를 통과한 것이며 향후 연속 안정성을 보증하지 않는다.

[공개 검증 요약](../../outputs/gw-readiness-02-main-20261106/validation.json). 원문 로그/JUnit/접속값·키는 무시되는 work/gw-readiness-02-main-20261106/에 둔다. 이전 [79차 보고서](GW_통합적용_승격검증_GW-READY-02_79.md)의 실패는 2026-11-05 이력으로 보존하고 이번 새 실행과 합산하지 않는다.

ready=false/최종4UNVERIFIED·실제복원PARTIAL·ACCEPTANCE PASS거부 유지. 공급자 선택·외부 독립성/전체 권한 회수·실회사10인 인수·실API브라우저·운영전환은 아직 미완료다. 다른 ID를 자동 시작하지 않는다.

## 이번 단일 전체 로컬 CI 결과

- migration·실DDL·local-ci 모두exit0. backend **2873pass/2skip/0fail**, perf **1pass/0skip**, frontend **99파일/847pass/0skip**. 도구144건, type/lint/format/build, 정적DB/R1~R6, 별도 빈DB의 downgrade base→upgrade head·실DDL까지 모두 통과했다. 성능/프런트 재시도는 없었다. 실제 GitHub Actions 실행 결과는 아니다.
- backend skip2는 `test_factory_native::test_real_binary`(native core binary 미빌드), `test_cmms_assets::test_mold_import_sets_type_mold`(시드에 금형 없음)이다. 통과 건수로 세지 않았다. GW의 예전10인 폐쇄복원 skip은 이번 실행에서 해제되어 통과했다.
- 고정pin 승격9건과 선행3분기3건도 전체 실행 안에서 모두 통과/skip0을 JUnit으로 확인했다. 전체 backend 시간은1시간30분9초였다.
- sourceDigestBefore/After는 `e1548ad488e22bb83fd9bd5554567048598de59a71f28f5c41ec10472f2993ca`로 같다. 실행 중 추가한WIP는 문서뿐이며 코드·테스트·metadata 변경0이다.
- 추가DB잔존0·생성rootDB/별도왕복DB 모두 제거. 실제소유/loopback 확인 후 기록된2개 DB 잔존0과 pin 임시폴더0을 읽기 재확인했다. 다른 자원은 삭제하지 않았다. 미리보기/운영DB·실계정/비밀번호/MFA/브라우저 설정 변경은 없다.

79차의 통합 구현·전체 로컬 기술 검증을 완료했다. 이것은 운영 준비/실회사 인수 완료가 아니다. ready=false/최종4UNVERIFIED·실제복원PARTIAL·ACCEPTANCE PASS거부를 유지한다. 현재 main에 실제DB migration을 적용하거나 원격push/운영배포하지 않았다. 기존metadata/Excel/ERD는 구조변경0이므로 다시 생성하지 않았다.

## 다음 작업

다음 제안은 별도 소유 격리 환경에서 실제API 로그인→회사 선택→운영 준비→권한 거부/연결 재확인까지 브라우저1440/390·키보드 동선을 확인하는 단계다. 기존 미리보기 계정의 생성/이름변경·비밀번호/MFA 초기화를 임의로 하지 않는다. 현재 연결1/예정10의 미리보기를 실회사10인 인수 환경으로 취급하지 않는다. 공급자/독립 최신성·전체회수와 실회사 인수는 별도다. 결과 보고 후 다른ID는 자동 시작하지 않는다. 인증/복구·회사범위·권한경계가 얽힌 작업이므로 GPT-6 Astra + High를 제안한다(모델 자동 변경 없음).

재현은 GW 저장소에서 새 private-output 경로를 사용한다. owner/전체ID/running·단일loopback/PG18과 시각가드는 유지한다. source pin 검사를 위해 Git 이력이 필요하며 checkout fetch-depth0을 사용한다.

```sh
backend/.venv/bin/python tools/gw_integration_check.py --container fs-gw-ready02-preview --expected-id-file work/gw-readiness-02-preview/container-id --owner gw-ready-02-preview --port 55439 --private-output work/gw-readiness-02-main-20261106/reproduce-ci --ci
```
