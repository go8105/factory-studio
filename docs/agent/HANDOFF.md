# Factory Studio 작업 인계

갱신: 2026-09-30 (Claude Code). **다음 세션은 이 문서의 "지금 상태"부터 읽는다.** 다음 작업자는 Codex 또는 Claude Code일 수 있다.

## Codex 최신 상태 — 2026-10-04 FS-030b 완료

- 아래 main 운영/Claude 기록은 보존한다. GW의 이전 a/WIP 상태는 이 항목으로 대체한다.
- 위치 `/Users/hwang-kyoungho/projects/factory-studio-codex`, branch `codex/fs-030-gw`. main8531c05 fast-forward 후 구현 WIP2a80375, 최종 커밋은 `git log -1`. push·배포·main 병합 없음.
- G01~07/API·ERP 조회계약/E11 배지·런처/전환 구현 완료. DB v0.17.0/headfs029b_cmms_module·시드14,687 유지. 교차쓰기 없음.
- 검증: GW20·Vitest518(+마지막 관련11)·tools73·브라우저17 후 업무5 재검사(고유18)·Ruff163·빌드/타입/lint/format·설계/격리/DDL 오류0. 전체pytest839통과/성능1실패(3.426초>2초), 해당 검사 단독1통과. 기준 변경 없음. 실행 상세·미실행·재현: [FS-030b 보고](GW_API화면_FS-030b.md).
- 다음은 **사용자 b 확인 후 c**: GW69행·게스트복사 검증·g01~07 도움말·참고문서·흐름맵·통합. 최신main의 CMMS/시드/head 확인부터. c는 아직 시작하지 않았다.
- 전용DB factory_studio_codex_fs030b_test/full_test/browser_test, 포트8030/5230만 사용. `.env`/`work/` 스테이징 금지. Safari·운영·전체 솔루션 브라우저 미검증.

## 지금 상태 (2026-09-30)

- **운영** https://eip.hugh-d.com — **서버는 main `a4baf30`(2026-10-04 배포: FS-030b GW API·화면, DB 변경 없음)**. head `fs029b_cmms_module`, 템플릿 14,687. 확인: 진입 화면에 GW / 그룹웨어, 게스트 201, `/api/v1/gw/dashboard` 200(`needsPerson`), `/gw` 200. GW는 체험 시드·도움말이 없어 처음엔 담당자 등록부터(c는 일괄 개발 때). **Claude의 운영 SSH는 자동 모드 권한 검사가 막는다 → 서버 명령·rsync는 사용자가 실행. 안내 명령에 `git log`를 넣을 때는 `git --no-pager`(페이지 보기에서 멈춤).**
- **최근 완료**: FS-025 BEMS(API·화면·시드) · DOC-03/04 참고 문서 4구역(설계 8·따라하기 3·개념 19) · MAP-02 P-03 보기 3종 · 홈 제목 "제조 현장의 올인원 시스템" · FS-027 게스트 별칭 필수·P-07 "게스트 접속"(별칭 90일) · UI-04 앱 안 링크 이동 미저장 보호 · 새 로고·파비콘.
- **마지막 전체 검증**: pytest 727 passed · 1 skipped, vitest 492, 전체 스모크 231 passed(+재실행 167), db:validate·격리 R1~R6 0.
- **FS-026 WMS 확장 main 병합(2026-09-30, Claude)**: Codex `codex/vision-ai` `f65044b`(입고 예정·도착·검수 W-08, 예약·소진 W-09, 3D 트럭 도착, 시드 +22, 도움말)을 main에 병합. 순서 FS-028a(SPC) → FS-026a: schema **v0.14.0 / 103테이블**, 마이그레이션 `fs026a_wms_receiving_reservation`의 down_revision을 `fs028b_spc_module`로 옮김(제약 이름은 분기 때 번호 그대로 — DDL 대조는 구조 비교). 템플릿 11,933(WMS +22, spc 모듈 행 +1), 복사 11,931. `wms-extension.spec.ts`에 FS-027 별칭 입력 추가.
- **배포 방법**: Claude가 `ssh root@158.247.236.136`·`rsync`로 직접 할 수 있다(사용자 허락, 2026-09-29~30). 순서: 프런트 빌드(별도 worktree) → rsync·chown → 서버 `git pull` → 백엔드가 바뀌었으면 `uv sync`·`systemctl restart factory-studio-api` → 시드가 바뀌었으면 `seed.cli template`. 반영 후 외부 curl 확인은 권한 분류기가 막을 때가 있다.
- **주의**: 다른 Claude 세션("EIP 포토폴리오 개발_vN")이 같은 폴더·main을 쓴다 → `git add`는 파일 지정. 스모크는 8000·5173을 쓰며 다른 세션 개발 서버가 막을 수 있다. 스모크 도중 frontend 파일을 고치지 않는다. 로컬 개발 DB는 만료 게스트가 쌓여 `.claude/launch.json`이 `GUEST_LIMIT=1000`으로 띄운다.

### 사용자 결정 (2026-09-30) — 17개 시스템 전체 구현
- 카탈로그 17개를 **모두 구현**한다(제외였던 그룹웨어·RWS 포함). 그룹웨어는 **"GW"**로 표기. 깊이는 **모두 BEMS 수준**(결정서 → 모듈·화면 설계 승인 → a DB / b API·화면 6~7 / c 시드·도움말). 다 만든 뒤에는 기능을 계속 덧붙인다.
- 방식: 큰 틀(로드맵)을 고정하고, 끝난 솔루션은 동결, 남은 것을 **하나씩** 설계·개발한다. 매 세션은 로드맵 + 대상 솔루션 + 이웃 조회 계약만 읽는다.
- 순서(ROADMAP-01 확정): 1 SPC → 2 CMMS → 3 POP → 4 TMS(FS-026 뒤) → 5 PLM → 6 CRM → 7 SCM → 8 ELB/MRO → 9 EIP → 10 GW → 11 RWS.
- **ROADMAP-01 확정(2026-09-30, 제안대로)** — `docs/plan/로드맵_17개시스템_ROADMAP-01.md`·`docs/plan/새솔루션_킷.md`. **지금: FS-028 SPC** — 설계 확정, **FS-028a DB 완료**(v0.13.0, 로컬 head `fs028b_spc_module`, pytest 727). **FS-028b 진행 중**(API `/api/v1/spc`·`fs/spc/interface.py`·MES `operation_runs`·QMS 배지·S-01~07·홈 분야별 묶음). D 다음 D45, AC 다음 AC-185.
- **Codex에 전달**: FS-026은 main에 병합됐다. 다음 작업은 새 main에서 새 브랜치로 시작한다(`codex/vision-ai`는 병합 끝). 게스트 생성 테스트는 `json={"nickname": …}`, e2e는 별칭 입력 필수(FS-027).
- **FS-028 SPC a·b·c 완료(2026-10-01, 로컬 main)** — c: 시드 `_spc`(부분군 456·측정값 2,280·이상 3: LT-0017 미조치 2·LT-0010 지그 조치 1, 공정능력 충분4·주의1·부족1), `seed/validate.py` V13, 템플릿 14,685·복사 14,683(중앙값 0.813초), 도움말 s-01~07·개념 c-20·21, 흐름 맵 `process_control`(18·21), e2e QMS 배지. **남은 것: 운영 반영**(main에 다른 세션의 `cb3fba4 WIP FS-040` 런처 평가가 함께 있다 — 같이 배포할지 사용자 확인) → README "운영 · 동결" → 로드맵 2번 CMMS 결정서(D45·AC-185부터).
- **GW(로드맵 10번)는 Codex가 병행(FS-030, 2026-10-01 사용자 지시)** — 지시서 `docs/agent/Codex_작업지시_GW_FS-030.md`(브랜치 `codex/fs-030-gw`, 번호 범위 D60~69·AC-220~239·화면 G, 스키마 버전은 병합 때 Claude가 정한다). Claude 쪽 CMMS는 D45·AC-185부터.
- **FS-030a GW DB main 병합(2026-10-01, Claude)**: Codex `codex/fs-030-gw` `cd8b619`. 충돌 4곳(시드 합계·진행 기록)만 해결 — 템플릿 14,686·복사 14,684(SPC +2,752 + gw 모듈 행 +1). 임시 버전 `0.15.0-gw` → **v0.16.0**(FS-040이 0.15.0). 검증: db:validate 0·격리 0·tools 69·실제 DB base↔head·DDL 대조 0(112·FK 258)·pytest 관련 72(seed·common·spc·gw_schema·schema_verifier·reviews)·ruff. Codex 다음은 FS-030b(API·화면) — 새 main에서 rebase.
- **지금(Claude): ROADMAP-02 전체 설계 우선** — 개발 중지. 18개(HR 신설 D79) 설계 → DSN-90 → DSN-99 → 일괄 개발. DSN-00·01 완료. **기존 7개 보강 설계 완료(확인 대기): DSN-11 ERP · 12 MES · 13 WMS · 14 QMS · 15 FEMS · 16 BEMS · 17 SPC** — 목표 DB 228테이블. 바코드 스캔(생산·창고)은 POP, 휴일 달력은 core.holiday. 목표 DB 재생성 `python3 tools/rebuild_target.py`(새 DSN 스크립트는 STEPS에). **DSN-21 CMMS 재점검 완료(6→12, 신호 출처 확장 제외) · DSN-22 POP 신규 완료(7테이블, 지연 가져오기) · DSN-23 TMS 신규 완료(10테이블, 조달 운송 포함)**. **다음: PLM**·PLM·CRM·SCM·ELB·EIP·RWS·HR, GW는 Codex. 각 문서 6장 "넘길 것"이 입력.

- **FS-040 런처 평가 완료(2026-10-01, 로컬 main, push·배포 안 함)** — `core.app_review`·`/api/v1/core/reviews`·P-02 평점 줄+패널. schema **v0.15.0 / 104테이블**, head **`fs040_app_review`**(down `fs026a`). **FS-028c·GW(FS-030) 병합 때 주의**: 다음 schema 버전은 v0.16.0, 새 마이그레이션 down_revision은 `fs040_app_review`, 새 제약 번호는 C868·R237부터. `validate_db_design`의 작업 집합에 새 작업 ID를 FS-040과 함께 넣는다. 운영 반영 시 `alembic upgrade head`만(시드 변경 없음). 남은 것: p-02 도움말에 평가 안내, e2e.
- 재현: `python3 tools/apply_fs040.py` → `npm run db:validate` → (전용 DB) `alembic upgrade head` → `tools/verify_ddl_matches_schema.py` → `pytest backend/tests/test_reviews.py`.

### 다음 후보 (사용자 결정)
1. Codex FS-026b2 결과 검토 → W-08·W-09 화면·트럭·시드 → main 병합·배포.
2. 브라우저 뒤로·앞으로 가기 미저장 보호(UI-04 한계) — 데이터 라우터 전환이 필요해 비용이 큼.
3. Safari·실기기 확인, 운영 부하 시험(미실행).
4. FS-021 범위 밖 9건(구세대 정리·`statement_timeout` 등) — Codex 영역.


## Git·작업 위치

- 저장소(메인 폴더, Claude Code 전용): `/Users/hwang-kyoungho/projects/factory-studio`
- **Codex는 `/Users/hwang-kyoungho/projects/factory-studio-codex`만 사용**, 브랜치 `codex/*`. 메인 폴더를 열거나 수정하지 않는다. antigravity worktree·브랜치도 건드리지 않는다.
- main·origin: `0addc2e`(FS-019b) 이후 ERP 하위 ID를 순서대로 ff. 매출·채권 생성은 `erp/revenue.py`(019c)에 있고 019d~e가 이어 쓴다.
- Codex의 `codex/fs-019a-erp-master`에는 **이미 main에 통합된 커밋만** 남아 있다(FS-019a는 `5da9019`·`945a78a`, 런처·3D는 `a0f71ae`·`7c83bc7`·`c3f3213`으로 통합). **Codex는 다음 작업을 새 main에서 새 브랜치로 시작**한다.
- `gh` CLI 로그인 완료(go8105). CI는 `gh run list --branch <b>` / `gh run watch <id> --exit-status`.

## 현재 진행

| 영역 | 상태 |
|---|---|
| 포털 | 7/7 + 3D 공장(`/factory`) + **P-02 홈 UI 정돈 통합(`d93b757`, Codex `086f4d7`): 흰 헤더·F 마크·4타일(QMS 포함)·호버/`i` 안내, 하단 WMS·BEMS·SCM 링크 유지** — 제목 "네 시스템", 운영 배포 |
| FEMS | 14/14 (FS-018a~m) |
| MES | 15/15 (FS-020a~g) — `docs/agent/MES_FS-020*.md` |
| ERP | 18/18 (019a 기준정보 E-15~18, 019b 영업 E-02~04, 019c 출하 E-05~06 + 매출·채권 생성, 019d 매출·세금계산서 E-07~08, 019e 채권·수금·소명 E-09~10, 019f 매입·채무·지급 E-11~13, 019g 분개 미리보기 E-14, 019h 대시보드 E-01) — **FS-019 종료** — 계획 `docs/agent/MES_ERP_작업계획_FS-019_020.md` §3, 보고 `docs/agent/ERP_FS-019*.md` |
| FS-021 | 완료 `docs/agent/통합검증_FS-021.md` — 정책 7건 통과, AC-35~80 검증 33·부분 5·미구현 4·폐기 4(나머지는 1차 범위 밖), AC-63 결함 수정, 로컬 실측(동시 생성 지연은 현행 유지) |
| FS-022 | **완료 — https://eip.hugh-d.com**. 이지스 서버 공존(Nginx 443 이름 기반, uvicorn 127.0.0.1:8021, PG18 Docker 55432, Cloudflare 프록시 + Origin CA). 절차·업데이트·걷어내기 `docs/deploy/배포절차_FS-022.md`. 서버 접속: 맥북 `ssh root@158.247.236.136`(키) |
| UI-01 | 완료 `docs/ui/디자인시스템_UI-01.md` — main 통합·서버 배포(2026-09-26). 공통 토큰·`SolutionLayout`(접기·서랍)·넓은 업무 화면·3D 캔버스 확보. 393·10·107 통과 |
| 운영 | 443은 Cloudflare IP만, 이지스는 https://aegis.hugh-d.com(Cloudflare Access)·:8000 외부 차단, 운영자 계정은 `tools/create_member.py`(서버에서 실행), DB는 SSH 터널(§12-5) |
| UI-02 | **완료(A1~A6 전체 37화면 완료)** `docs/ui/공통UI규약_UI-02.md` — A1 대시보드(M-01, E-01), A2 조회 목록(M-09, E-07, E-14, P-07), A3 보고서형 조회(F-03, F-04, F-06, F-07, F-08, E-09·12), A4 FEMS 기준정보(F-09, F-10, F-11, F-13, F-14), A5 MES 기준정보 및 계획(M-02, M-03, M-06, M-08, M-10, M-11, M-12, M-13), A6 ERP 계획·출하·전표·기준정보(E-03, E-05, E-06, E-08, E-10·13, E-11, E-15~18) 완료 (누적 완료 40, 대기 0, Claude 선행 8, 유지 7 = 55), vitest 402 통과 |
| UI-02 검토 | Claude 검토·수정 후 main 통합(`86e729f` 이후 문서 커밋). 회귀 5건 수정·e2e 11건 갱신, 스모크 159 passed |
| QMS | FS-023a DB·023b API·화면(운영 배포) + **FS-023c 시드 113행(`sv-20260927-1`, 템플릿 7,583)·복사 월/번호 재계산·도움말 Q-01~06·흐름 맵 업무 노드(로컬, 미배포)**. 시드 LOT: LT-0017 검사 대기, LT-0015 작성 중, LT-0016 보류 중(+재검사 초안), LT-0008 특채 해제. 교차 조회는 `fs/<솔루션>/interface.py`만(R6) |
| UI-03 | **8화면 전체 완료·운영 배포** — Claude F-12·M-04·M-05·M-07·E-04(`a35e895` 배포), Antigravity B1(M-14·M-15) + B2(E-02 견적) — 브랜치 `antigravity/ui03-b2`, 스모크 171/171 통과. E-02: `FormPanel wide`(등록)·`DetailPanel wide`(상세·라인편집·확정·제출·수주 전환 통합). main 병합 완료 |
| 다음 | **FS-027 게스트 별칭 필수·P-07 게스트 접속(운영 반영). 게스트를 만드는 테스트는 `json={"nickname": …}` 필수.** 운영 `653d438` 반영 완료(2026-09-29, 프런트 de1892c 빌드). 현황 문서 정비 완료. Codex FS-026b2 진행 중. 다른 세션과 같은 폴더를 쓰므로 `git add`는 파일 지정. Codex FS-026b1 검토 완료(충돌 없음) — b2 승인 여부 사용자 결정.** 운영: `6508599`·head `fs025b_bems_module`·템플릿 11,910행(2026-09-29 반영 완료). Codex FS-026a(`521ad76`) 검토 완료: 진행 가능, 조건 = 422→400 규약, digest 날짜 제외, 시드 전 rebase — 운영은 `fs025a_bems`·`fs025b_bems_module` 마이그레이션 + 템플릿 재생성(11,910행) 필요. **Codex FS-026(WMS 확장)** 결정서를 기다린다 — Codex 새 WMS 설계(`fad0c3a`)는 기존 WMS와 겹쳐 병합 금지. FS-025c 완료: 시드 `_bems`(모델과 같은 시뮬레이션), 도움말 b-01~07, 흐름 맵 업무 노드, BEMS 카드 삭제, `CO2_IDLE` −30. 로컬 개발 DB는 만료 게스트 291개로 상한 20에 걸린다(`GUEST_LIMIT`을 올려 띄우거나 만료 공간 정리 필요). FS-025b 완료: API(`/api/v1/bems`, `fs/fems/interface.py`, `fs/bems/simulation.py`, 계약서 16장) + 화면 `frontend/src/bems/` B-01~07·포털 6타일·"여섯 시스템"(화면 설계 6장). 도움말 링크는 아직 404. 수동 명령도 시뮬레이션 시계로 기록한다. 스모크는 `smoke.sh`처럼 Node 24 PATH + fs017 DB URL을 넘긴다. 설계 확정(결정서·모듈·화면 설계 FS-025). FS-025a 완료: schema.json v0.12.0(93테이블), 로컬 head `fs025b_bems_module`(운영 미적용), 로컬 개발 DB·템플릿 반영. 025b: `fs/fems/interface.py` 신규, `/api/v1/bems`, `fs/bems/simulation.py`(모델 상수 한 곳), B-01~07. **로컬 개발 DB도 새 마이그레이션·시드 때 함께 올린다.** Codex는 `codex/vision-ai`(공장 컨셉·CNC) — 마이그레이션 head 겹치지 않게 조율 |

## 다음 할 일

- **운영 반영 완료(2026-09-27, `be87546`)**. Claude Code의 운영 SSH(`ssh root@158.247.236.136`)는 자동 모드 권한 분류기에 막혀 서버 명령은 사용자가 실행했다. 다음 배포도 같은 순서(배포절차 8장 → 시드가 바뀌면 템플릿 → 6장): 서버 pull·API 재시작·프런트 빌드 → **`seed.cli template --date 오늘` 재실행**(배포절차 4-3 아래 "시드가 바뀐 배포"). 마이그레이션 변경 없음(head `fs023b_qms_module` 유지). 운영 게스트로 Q-03에 LT-0017, M-08에 LT-0016 "QMS 보류" 배지 확인.
- `test_qms.py`의 API 테스트는 `qms` fixture가 게스트 QMS 시드를 지우고 시작한다. 시드에 의존하는 검사는 `seeded` fixture를 쓴다.

1. ERP 분담 확정(2026-09-26): **FS-019b~h 전부 Claude Code**(메인 폴더, `fs-019<x>-*`). Codex는 ERP를 하지 않는다.
2. E-G07 결정(2026-09-26): **0원 매출 세금계산서 발급 금지** — 019d에서 구현(409 `ZERO_AMOUNT_SALE`, 발급 대상 목록에서 제외).
0. **UI-02(2026-09-27)**: 브랜치 `ui-02-common-patterns` — 코드 `0875482` 뒤에 문서 커밋, main 통합(OPS `88d584f` 위 rebase). 화면은 대시보드(F-01)·조회 목록(F-02)·목록+패널(F-05) 세 패턴 중 하나로 만든다. `master-grid`는 레거시. Antigravity 작업은 `docs/agent/Antigravity_작업지시_UI-02.md`(기준 커밋 `0875482`이 main에 있어야 시작). 예외 8화면(F-12·M-04·M-05·M-07·M-14·M-15·E-02·E-04)은 Claude가 UI-03에서 대표 구현을 먼저 확정한다. 로컬 검증 스크립트(`work/ui02/*.mjs`, Git 제외)는 5173·8000 개발 서버와 `work/ui02/state.json` 게스트 세션을 쓴다 — 공식 검증은 `e2e/layout.spec.ts`.
3. **UI는 `shared/styles.css` 토큰·공통 클래스만 쓴다(UI-01).** 솔루션 메뉴는 `*Screens` 배열만 고친다. ERP 화면 모양을 FEMS·MES와 맞춘다: 관리 버튼 `link-button`, 등록 폼 select는 `.field` 안 전체 폭. 019b부터 ERP 화면은 `erp/common.tsx`(shared/hooks 위 ERP 접두사)와 `SalesOrders.tsx`의 `LineEditor`를 재사용한다.
4. 후속: (UI-01에서 360px 상단 메뉴 해소) 인라인 폼 미저장 변경 보호. 사용 중 채널 배수 변경 허용 유지 여부(FEMS_FS-018l).
5. **새 업무 테스트는 `guest_space` fixture**, 스모크는 8000·5173·`factory_studio_fs017_test`를 고정 사용하므로 **동시에 한 명만** 돌린다. 사용자가 개발 서버(8000·5173)를 켜 두면 스모크가 멈춘다 — 종료를 요청한다.
6. 판단 기록: MES `/work-orders/{id}/lot` 추가(020c), `/executions/{id}/finish`를 `/result`로 통합(020d), MES 업무 시각 `clock_timestamp()`(020g).

## 재현·주의점

- DB: Claude Code는 `factory_studio_fs016_test`(pytest)·`factory_studio_fs017_test`(스모크), Codex는 `factory_studio_codex_test`만. 같은 DB에 pytest를 동시에 돌리지 않는다.
- Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6. backend 테스트는 `.env` 없이 DATABASE_URL·TEST_DATABASE_URL·PATH·HOME만.
- **ruff는 CI 범위로만**: `ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py` + 같은 범위 `format --check`.
- schema.json·마이그레이션은 작업 ID 범위에서만(이미 적용한 revision 수정 금지). pytest DB는 새 head가 생기면 `alembic upgrade head`를 먼저 돌린다(`test_schema_verifier` 기준선). `test_common.py`·`test_seed.py`는 antigravity 소유, `conftest.py`는 Codex 소유.
- 확정·게시 데이터 불변, 업무 쓰기는 `write_scope` 뒤, 결측(invalid)은 합계에서 제외.
- 30분마다 WIP 커밋, 종료 시 이 문서 갱신·커밋. `.env`·`work/`·`node_modules`는 스테이징하지 않는다. `git push --mirror` 금지.

```sh
cd /Users/hwang-kyoungho/projects/factory-studio
export PATH="/opt/homebrew/opt/node@24/bin:$PWD/backend/.venv/bin:$PATH"
npm --prefix frontend run typecheck && npm --prefix frontend run lint && npm --prefix frontend run format:check
npm --prefix frontend run build && npm --prefix frontend test
# backend: CI 환경 변수 네 개만 전달 (접속 URL은 출력하지 않는다)
env -i HOME="$HOME" PATH="$PATH" DATABASE_URL="$db_url" TEST_DATABASE_URL="$test_db_url" \
  uv run --project backend pytest backend/tests -q
uv run --project backend --env-file .env python tools/run_portal_smoke.py   # 8000·5173 비어 있어야 함
python -m unittest discover -s tools && npm run db:validate && python tools/audit_schema_isolation.py && git diff --check
```


## Codex — FS-019a (2026-09-25)

- 브랜치: `codex/fs-019a-erp-master`, 전용 `factory-studio-codex`만 사용.
- 마지막 커밋: `5ad511d WIP FS-019a`(보존 커밋 d47b8a4를 6bcbe1e 위로 rebase한 결과). 이 절과 최종 결과는 후속 `FS-019a: ERP 기준정보 구현 및 회귀 검증` 커밋에 포함한다. 최신 커밋은 `git log -1`로 확인한다.
- 끝난 것: ERP E-15~18 API·화면·도움말·API 계약, guest_space 기반 ERP 회귀 78개, 프론트 ERP 테스트 20개. MES/ERP 라우트를 모두 보존했고 Home은 세 솔루션 화면 진입으로 변경. Field children 제거, select 직접 렌더링, checkbox inline-check 적용.
- 검증: 최종 frontend 5종(314 tests), CI Ruff 2종, db:validate, audit_schema_isolation, diff --check exit 0. backend 전체 510 passed, 580.736초, exit 0(CI 환경 네 변수만, 전용 DB).
- 다음: 사용자 승인 후 공용 포트/DB 스모크 실행 및 ERP 360px 스크린샷 직접 확인. 아직 실행 승인이 없어 미실행. FS-019a 완료 판정은 이 검증 뒤이며 FS-019b 착수·push·main 병합은 사용자 확인 뒤.
- 주의: pytest DB는 `factory_studio_codex_test`, 스모크는 `factory_studio_fs017_test` + 8000/5173(Claude Code와 공유). 동시 실행 금지. schema.json·마이그레이션·test_common.py·test_seed.py·conftest 변경 없음. 새 의존성 없음.
- 보고서: `docs/agent/ERP_FS-019a.md`(명령·exit·런타임·남은 검증).

```sh
cd /Users/hwang-kyoungho/projects/factory-studio-codex
export PATH="/opt/homebrew/opt/node@24/bin:$PWD/backend/.venv/bin:/opt/homebrew/bin:/usr/bin:/bin"
npm --prefix frontend run typecheck && npm --prefix frontend run lint && npm --prefix frontend run format:check
npm --prefix frontend run build && npm --prefix frontend test
# task_test_url은 factory_studio_codex_test 접속 URL. .env 없이 네 변수만 전달.
env -i HOME="$HOME" PATH="$PATH" DATABASE_URL="$task_test_url" TEST_DATABASE_URL="$task_test_url" uv run --project backend pytest backend/tests -q --durations=15
uv run --project backend ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
uv run --project backend ruff format --check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
npm run db:validate
uv run --project backend python tools/audit_schema_isolation.py
git diff --check
# 스모크는 사용자 승인 후 tools/run_portal_smoke.py 실행.
```


## Codex — P-02 런처 크기 조정 (2026-09-25)

- 브랜치 `codex/fs-019a-erp-master`, 기준 마지막 커밋 `4e2bc74`. 후속 `P-02: 솔루션 런처 아이콘 타일 크기 조정` 커밋에 이 인계 포함(`git log -1`로 확인).
- 끝난 것: 사용자 두 번째 이미지의 작은 아이콘 타일/하단 이름 배치 적용. Home.tsx·Home.css 변경, 기존 색상·동작 보존.
- 검증: Node 24.21.0, frontend typecheck/lint/format:check/build/test(314 passed) 및 diff --check 모두 exit 0.
- 다음: Claude Code가 새 main 통합 뒤 스모크·360px(ERP 및 런처 포함) 직접 검증. Codex는 사용자 지시로 스모크를 실행하지 않는다. 결과에 따른 수정 요청 대기. backend 검증 미실행(UI만 변경).
- 재현: 전용 factory-studio-codex에서 Node 24 PATH 지정 후 `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint`, `npm --prefix frontend run format:check`, `npm --prefix frontend run build`, `npm --prefix frontend test`.
- 메인 폴더 미사용, push·main 병합 없음. .env·work/·node_modules 제외.

## Codex — 3D 공장 둘러보기 (2026-09-26)

- 브랜치 `codex/fs-019a-erp-master`, 마지막 보존 커밋 `5593693 WIP: 3D 공장 둘러보기 구현 보존`(기준 f9eb879). 이 인계·최종 수정은 후속 `3D 공장: 조감도와 3인칭 현장 둘러보기` 커밋에 포함한다. 최종 해시는 `git log -1`.
- 끝난 것: 사용자 승인한 조감도·3인칭 이동, 일반 조립/비전검사/포장 설비 3대·키오스크, 1층 현장사무실 1명·바코드 프린터, 2층 사무실 2명, 현장 순회 1명 + 사용자 캐릭터. `/factory`, 상단 앱 런처 오른쪽 메뉴. 상세 `docs/agent/3D공장_구현.md`.
- Node 24.21.0. 최종 frontend typecheck/lint/format:check/build/test(330 passed) 및 독립 브라우저 7개(20.0초), diff --check 각각 exit 0. 스크린샷 직접 확인. backend·DB·공용 스모크 미실행.
- 새 의존성은 package-lock에 고정. 통합 시 `npm --prefix frontend ci`. three/Fiber/Drei와 @types/three. 공장 화면에만 lazy load. 코드 생성 모델로 외부 모델 자산 없음.
- 재현: 전용 폴더에서 Node 24 PATH를 지정한 후 `npm --prefix frontend run test:factory-browser`. 전용 5186을 시작/종료하며 API는 모두 모의 응답한다. 공용 8000·5173·스모크 DB를 사용하지 않는다.
- 다음: Claude Code가 새 main 통합 뒤 전체 스모크·360px 실행. 사용자는 Codex의 공용 스모크 실행을 금지했으므로 실행하지 않는다. 통합 시 ERP(4e2bc74)·런처(f9eb879)·3D(WIP+후속)의 범위를 구분한다. 수정 요청 대기.
- 메인 폴더·antigravity 미사용. push/main 병합 없음. .env·work/·node_modules 제외. 별도 테스트 서버는 종료한다.


## 2026-09-26 Blender 비전검사 설비 (Codex)

- 사용자 "참고자료 없이 바로 진행" 승인. `codex/factory-vision-blender`에서 기존 공장의 비전검사 1대를 Blender 원본/GLB로 교체.
- 카메라·링 조명·컨베이어·경광등, 6초 검사 주기·5번째 불합격, 상태/수량 패널·가까이 보기·이상 정지/해제·MES 대시보드 진입. 합성 시연이며 업무 데이터에 저장하지 않음.
- Node 24.21.0: frontend typecheck/lint/format:check/build/test(345 passed), 독립 Chromium 브라우저 8개 통과(exit 0). 360px/데스크톱 직접 확인. Blender 5.2.2 GLB 생성 성공.
- DB/API 변경·새 의존성 없음. backend/DB/공용 통합 스모크 미실행. main 병합·push 없음.
- 원본 `assets/blender/vision-cell.blend`, 재생성 `tools/blender/build_vision.py`, 상세 보고 `docs/agent/3D공장_Blender_비전검사.md`.
- 다음: 시각 피드백·통합 담당자 main 통합. MES 실제 레코드 연결 및 FEMS는 후속 설계.


## 2026-09-26 3D 공장 공간 고도화 (Codex, 완료)

- 브랜치 `codex/factory-building`, 기준 `b352514`(비전검사). 사용자 우선순위 진행 및 이어서 진행 승인.
- Blender 건물 외관/내부 전환, 지붕·패널·창문·하역장·공조기·철골·덕트·천장 조명. 조립·포장 설비도 Blender 모델로 교체하고 프레스·실링바 시연.
- 바닥 질감·환경 반사·그림자, 자재 선반/공구대/소방함 및 충돌. MES/ERP/FEMS 기존 화면 진입 카드. 업무 API/DB·실제 데이터 연동 없음.
- Node 24.21.0: typecheck/lint/format:check/build exit 0. 전체 테스트는 자원 경합을 줄인 `npm --prefix frontend test -- --maxWorkers=2`로 346개 통과. 독립 Chromium 브라우저 10개 통과(2.1분, exit 0). 외관/내부/모바일 스크린샷 직접 확인.
- Blender 5.2.2 LTS. 생성 스크립트와 .blend/GLB를 저장. 새 npm 의존성 없음. 상세 `docs/agent/3D공장_공간고도화.md`.
- backend/DB/공용 통합 스모크·Safari/실기기 성능은 미실행. main 병합·push 없음. 다음: 사용자 시각 피드백 및 통합 담당자 main 통합. 최종 커밋은 이 인계를 포함한 `3D 공장: 건물·재질·생산라인 공간 고도화`이며 `git log -1`로 확인.

## Antigravity — UI-02 A1 (2026-09-27)
- 브랜치: `antigravity/ui02-a1` / 기준 커밋: `ed9f438cbbd1f2aacec67a3029304020e3d7865e` (main) / 마지막 커밋: `ce731ab`
- 옮긴 화면: M-01(`frontend/src/mes/Dashboard.tsx`), E-01(`frontend/src/erp/Dashboard.tsx`)
- 내용:
  - 별도 `filter-bar`의 조회 월 입력을 `PageTitle`의 `actions`로 이동
  - 카드 순서·내용 및 2×2 유지, 쿼리 파라미터 및 KPI 보존
  - `frontend/e2e/layout.spec.ts`에 M-01 및 E-01 조회 월 위치 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음

## Antigravity — UI-02 A2 (2026-09-27)
- 브랜치: `antigravity/ui02-a2` / 기준 커밋: `ce731ab` (`antigravity/ui02-a1`) / 마지막 커밋: `26e9ab3`
- 옮긴 화면: M-09(`frontend/src/mes/Receipts.tsx`), E-07(`frontend/src/erp/SalesRecords.tsx`), E-14(`frontend/src/erp/Journal.tsx`), P-07(`frontend/src/portal/Records.tsx`)
- 내용:
  - 각 화면 루트에 `.page-fill` 적용
  - P-07: 상단 탭을 `DataTable`의 `leading` prop으로 전달 (F-02 기준 화면 구조 준수)
  - 안내문 `<p className="muted" role="note">` 규약 정비 및 `Loading delay={300}` 적용
  - P-07의 ADMIN 권한 분기 및 API 계약 보존
  - `frontend/e2e/layout.spec.ts`에 A2 화면들(`.page-fill`) 레이아웃 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음

## Antigravity — UI-02 A3 (2026-09-27)
- 브랜치: `antigravity/ui02-a3` / 기준 커밋: `26e9ab3` (`antigravity/ui02-a2`) / 마지막 커밋: `ad54b6c`
- 대상 화면: F-03(`fems/Allocations.tsx`), F-04(`fems/Emissions.tsx`), F-06(`fems/Intensity.tsx`), F-07(`fems/Targets.tsx`), F-08(`fems/Billing.tsx`), E-09·12(`erp/Receivables.tsx`)
- 내용:
  - `.page-fill`을 쓰지 않고 자연스러운 문서 스크롤 유지 (합계·근거·표 복합 구조)
  - 직접 쓴 표 숫자 열에 `th.num`, `td.num` 클래스 적용 (F-04 배출량·소비량, F-06 원단위·생산량, F-07 달성률·목표·실적, F-08 요금, E-09/12 채권·채무 원금·소명액·잔액)
  - 합계 계산 표시, 계산 근거 펼침(`basis-panel`), 결측 제외 문구, 목표 초과 배지 글자 보존
  - 안내문 `<p className="muted" role="note">` 및 `Loading delay={300}` 공통 규약 정비
  - `frontend/e2e/layout.spec.ts`에 R 패턴 화면들(.page-fill 미사용) 레이아웃 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음

## Antigravity — UI-02 A4 (2026-09-27)
- 브랜치: `antigravity/ui02-a4` / 기준 커밋: `ad54b6c` (`antigravity/ui02-a3`) / 마지막 커밋: `e6c9fd9`
- 대상 화면: F-09(`fems/Sites.tsx`), F-10(`fems/Equipments.tsx`), F-11(`fems/EnergySources.tsx`), F-13(`fems/Factors.tsx`), F-14(`fems/Tariffs.tsx`)
- 내용:
  - 레거시 `master-grid` 제거 및 `.page-fill` + `.split-view` + `FormPanel` + `useDiscardGuard` 표준 S 패턴 전환
  - F-09: 사업장과 공간 2개 섹션 블록 및 공통 FormPanel 적용
  - F-13: DataTable leading 탭 구조 및 FormPanel 통합
  - `frontend/e2e/layout.spec.ts`에 A4 화면들(.page-fill) 및 에너지원 패널 열기/닫기 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음

## Antigravity — UI-02 A5 (2026-09-27)
- 브랜치: `antigravity/ui02-a5` / 기준 커밋: `e6c9fd9` (`antigravity/ui02-a4`)
- 대상 화면 8개:
  - M-02 생산계획: `frontend/src/mes/Plans.tsx` (FormPanel 적용, RevealAnchor 제거)
  - M-03 작업지시: `frontend/src/mes/Orders.tsx` (FormPanel 적용, ?line= 프리셋 패널 자동 열림)
  - M-06 자재 투입: `frontend/src/mes/Materials.tsx` (FormPanel title="자재 투입 등록", inner form 제거)
  - M-08 패킹: `frontend/src/mes/Packing.tsx` (FormPanel 적용, inner form 제거)
  - M-10 사업장·공간: `frontend/src/mes/Sites.tsx` (2개 섹션 블록 + FormPanel S 패턴)
  - M-11 설비: `frontend/src/mes/Equipments.tsx` (FormPanel S 패턴)
  - M-12 품목: `frontend/src/mes/Items.tsx` (FormPanel S 패턴, RevealAnchor 제거)
  - M-13 공정: `frontend/src/mes/Processes.tsx` (FormPanel S 패턴)
- 내용:
  - 모든 컴포넌트에서 React Rules of Hooks 준수: `useDiscardGuard`를 early return (`moduleOff`) 이전에 무조건 호출하도록 구조 정리
  - `FormPanel` 내 중첩 `<form>` 제거로 브라우저 경고 및 파싱 오류 방지
  - `planning.test.tsx`, `master.test.tsx`에서 패널 오픈 버튼 클릭 후 폼 조회하도록 단위 테스트 동기화
  - `frontend/e2e/layout.spec.ts`에 8개 MES 화면 `.page-fill` 검사 및 설비 패널 열기/닫기 E2E 테스트 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음. A6(ERP 계획·출하·전표·기준정보 화면)으로 이어짐

## Antigravity — UI-02 A6 (2026-09-27)
- 브랜치: `antigravity/ui02-a6` / 기준 커밋: `cd0c1d7` (`antigravity/ui02-a5`)
- 대상 화면 10개 (11개 메뉴):
  - E-15~18 기준정보: `frontend/src/erp/Master.tsx` (`Partners.tsx` E-15, `Items.tsx` E-16, `Prices.tsx` E-17, `Accounts.tsx` E-18 공용). `children` prop 지원, `FormPanel` 전환, `Accounts.tsx` split-view + 매핑 이유 aside 패널 결합.
  - E-03 판매계획: `frontend/src/erp/SalesPlans.tsx` (`master-grid` 및 `RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("판매계획 만들기")`).
  - E-05 출하지시: `frontend/src/erp/ShipmentOrders.tsx` (`RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("출하지시 만들기")`, 미출하 취소 동작 유지).
  - E-06 출하: `frontend/src/erp/Shipments.tsx` (`RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("출하 확정")`, 수기 패킹번호 동작 유지).
  - E-08 세금계산서: `frontend/src/erp/TaxInvoices.tsx` (등록·발급 두 폼을 `FormPanel` 모드 전환으로 S 패턴 통합, 0원 매출 발급 방지 및 409 안내 유지).
  - E-10·E-13 수금·지급 등록·소명: `frontend/src/erp/Receipts.tsx` (수금·지급 공용 컴포넌트, `master-grid` 및 `RevealAnchor` 제거, `FormPanel` 등록 전환, 409 LIMIT_EXCEEDED 오류 안내 유지).
  - E-11 매입 전표: `frontend/src/erp/PurchaseInvoices.tsx` (`master-grid` 및 `RevealAnchor` 제거, 등록·취소 두 패널을 `FormPanel` 모드 전환으로 통합).
- 내용:
  - React Rules of Hooks 준수: `useDiscardGuard`를 early return (`moduleOff`) 이전에 호출하여 조건부 훅 오류 원천 차단
  - E2E 및 단위 테스트 최신화: 패널 오픈 버튼 클릭 후 폼을 조회하도록 테스트 보강 (`Prices.test.tsx`, `Partners.test.tsx`, `Items.test.tsx`, `shipping.test.tsx`, `revenue.test.tsx`, `purchases.test.tsx`)
  - `frontend/e2e/layout.spec.ts`에 전체 ERP 화면 `.page-fill` 검사 및 ERP 거래처 등록 패널 열기/닫기 E2E 테스트 추가
  - **Antigravity UI-02 작업 묶음 A1~A6 (총 37개 화면) 전체 완료** (완료 40, 대기 0, Claude 선행 8, 유지 7 = 총 55개 화면).
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음. 사용자 확인 및 Claude 선행 8개 화면(UI-03: F-12, M-04, M-05, M-07, M-14, M-15, E-02, E-04) 진행 대기

## Claude Code — UI-02 검토·main 통합 (2026-09-27)

- Claude 검토(2026-09-27): 공식 스모크를 처음 돌려 11건 실패를 찾았다(Antigravity 묶음 검증에는 스모크 없음). 실제 회귀 5건 수정 — M-06 BOM 제안량 표가 겹침 패널에 가려 채울 수 없음(→ 패널 안으로), M-12 '환산'이 등록 패널을 자동으로 열어 목록을 가림(→ 목록만, 등록은 버튼), E-05·E-06·E-10/13 저장 직후 새 행 선택이 미저장 보호에 막힘(→ 가드 없는 `choose()`), E-18 설명 패널이 표와 겹침(→ main 구조·R 패턴 복원), F-09 인라인 style·정의 없는 `section-block`(→ 공통 `.section-block` 추가). 나머지 6건은 e2e 흐름 갱신. 레이아웃 e2e를 '클래스 존재' → '1440×900 문서 높이'로 강화.
- 검증: typecheck·lint·format:check·build, vitest 402, 스모크 **159 passed**(7.6분, exit 0), 55경로 × 1440·1600·390 전후 비교(가로 넘침·오류 0), S 화면 24개 패널 열기·저장 버튼·Esc(행 선택형 M-06·M-08 포함).
- 통합: `antigravity/ui02-a6` + 검토 커밋(`e8b0d71`·`86e729f`)을 main에 fast-forward. push·서버 배포 전.
- 주의(다음 Antigravity 지시에 반영): 묶음마다 **공식 스모크(`tools/run_portal_smoke.py`)** 를 돌려야 한다. 단위 테스트는 패널 뒤 목록이 가려지는 문제를 잡지 못한다. 기본 e2e 뷰포트 1280px은 패널 겹침 모드다.
- 배포(2026-09-27): origin push `88d584f..0378bf6`, 서버 `git pull --ff-only`(백엔드·마이그레이션 변경 없음 → API 재시작 없음), 맥북 별도 worktree에서 `0378bf6` 프런트 빌드 → rsync. 확인: Cloudflare 경유 200·새 번들 해시 일치·API 5xx 0, 운영 게스트로 F-02·F-05·M-12·E-15 1440×900 문서 900px, F-01 1600 하단 2×2, F-05 패널 열림, 페이지 오류 0.
- UI-03 예외 패턴(2026-09-27, Claude Code): 공통 `DetailPanel`(폼 없는 패널)·`wide`(640px, 1920px 이상 붙음·이하 겹침)를 `SidePanel` 하나로 구현. 기준 화면 — 읽기 전용 상세 M-04, 부모-자식 F-12(채널 상세 ↔ 채널 폼), 넓은 행 편집 E-04(등록·상세·편집), 상태 전이 M-05·M-07(`ResultForm`을 패널로). 규약 8장·적용표(완료 45, Antigravity 대기 3: M-14·M-15·E-02 → 지시서 UI-03 B1·B2).
  - 검증: typecheck·lint·format·build, vitest 402, 대표 화면 5개 × 1920·1600·1440·390 패널 모드·문서 높이·가로 넘침 확인, e2e(layout·fems·mes·portal) 151 passed / 2 failed(F-03 배분 추정·F-01 전월 목표 초과 — 이번에 바꾸지 않은 화면, e2e를 여러 번 돌려 로컬 개발 DB가 바뀐 데이터 의존 실패로 판단). **공식 스모크는 미실행**: 같은 메인 폴더에서 다른 세션(DOC-01)이 동시에 작업 중이라 8000·5173을 점유하는 스모크를 돌리지 않았다.
  - 주의: 이 폴더에서 다른 세션이 동시에 커밋 중(DOC-01 `238a7a0`이 UI-03 WIP 사이에 있음). 스테이징은 경로를 지정한다. push·배포 전.
- UI-03 스모크·배포(2026-09-27): 공식 스모크 **164 passed**(7.7분, exit 0 — 로컬에서 실패하던 F-03·F-01도 통과, 데이터 의존 실패 확인). origin push `6e22e00..a35e895`(DOC-01·DOC-02 포함), 서버 pull(백엔드 변경 없음, API 재시작 없음) → `a35e895` 프런트 빌드·rsync. 확인: 새 번들 해시 일치·200·API 5xx 0, 운영 게스트 1920×1080에서 M-04·F-12·E-04 넓은 패널(640) 붙음, M-05·M-07 패널(380), 문서 1080px, 오류 0.

## Antigravity — UI-03 B1 (2026-09-27)

- 브랜치: `antigravity/ui03-b1` / 기준 커밋: `24179d1`
- 대상 화면 (2개):
  - M-14 공정 경로: `frontend/src/mes/Routes.tsx` (F-12 부모-자식 패턴 적용: 경로 버전 목록 → 단계 목록 `DetailPanel wide` → 단계 폼 `FormPanel`, 게시한 버전 불변, '개정'·'게시' 동작 유지, `RevealAnchor` 제거)
  - M-15 BOM: `frontend/src/mes/Boms.tsx` (BOM 목록 → 자재 라인 `DetailPanel wide` → 라인 폼 `FormPanel`, 게시한 버전 불변, 개정 새 코드 `FormPanel`, `RevealAnchor` 제거)
- 테스트 갱신 및 추가:
  - `src/mes/versions.test.tsx`: BOM 라인 폼 전환에 따른 라벨·버튼 접근자 갱신 (8 tests passed)
  - `e2e/mes.spec.ts`: 공정 경로 개정 흐름 갱신(패널 열림 확인 → 순서 편집 → 저장 → 패널 닫기 후 목록에서 게시)
  - `e2e/layout.spec.ts`: M-14 공정 경로 단계 패널 및 M-15 BOM 자재 패널 1440×900 문서 높이 ≤ 900 및 Esc 닫기 검사 추가
- 검증:
  - `npm --prefix frontend run typecheck`: exit 0
  - `npm --prefix frontend run lint`: exit 0
  - `npm --prefix frontend run format:check`: exit 0
  - `npm --prefix frontend run build`: exit 0
  - `npm --prefix frontend test`: 44개 파일 410개 테스트 통과 (exit 0)
  - `git diff --check`: exit 0
  - `uv run --project backend --env-file .env python tools/run_portal_smoke.py`: 공식 스모크 **166 passed** (8.0분, exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음. 사용자 확인 후 UI-03 B2 (E-02 견적 넓은 행 편집 화면) 진행 대기

## 2026-09-27 1인칭 비전검사 체험 (FS-3D-FP01, Codex 완료)

- 브랜치 `codex/factory-building`, 기준 `d3eaf31`. 사용자 승인한 웹 1인칭 검사 구역 데모 구현.
- `/factory`의 1인칭 체험 진입, 눈높이 이동·드래그 시선·충돌, 직접 클릭/탭·E 선택, 데스크톱 옆 패널/모바일 아래 패널. 작업자 1명·태블릿·안전 구획·조명 보강.
- 상태·판정·검사/합격/불합격 수량·링 조명·시연 설정값. 합성 시뮬레이션이며 실제 업무 API/계측/DB 연결 없음. 실사 품질 인물·재질은 후속 개선 대상.
- Node 24: typecheck/lint/format:check/build exit 0. Vitest 348개/36파일 통과. 기존 Chromium 회귀 10개 통과, 새 1인칭 3개는 최종 분리 실행에서 모두 통과(1.9분). 처음 한 테스트에 선택·이동·스크린샷을 묶어 60초 제한을 초과한 것은 테스트를 분리해 해소. 화면 직접 확인.
- 5186·모의 API만 사용, backend/DB/공용 스모크·실기기 FPS·Safari/WebXR 미검증. main 병합·push·운영 배포 없음.
- 보고서 `docs/agent/3D공장_1인칭_비전검사.md`. 다음: 통합 담당자가 현재 main/UI 변경과 대조해 3D 커밋 반영 여부 확인 후 사용자 체험. 실제 데이터 매핑과 실사 자산은 별도 후속 범위.
- 통합(2026-09-27, Claude Code): Antigravity UI-03 B1(`2cda062`, M-14 공정 경로·M-15 BOM 부모-자식 패턴) fast-forward + Codex 1인칭 비전검사 체험(`2a739c2` → cherry-pick `941a50d`). Codex 브랜치는 UI-01 이전 코드 기준이라 `Factory.tsx`·`Factory.css` 충돌 — main 파일을 기준으로 Codex 변경 13가지(체험 상태·진입/나가기·포커스 가둠·툴바·조준점·E 선택·이동 패드·설비 상태/설정 패널 등)를 다시 적용하고 CSS 블록은 원본과 동일함을 확인. 보정 `bf8c8e9`: 1인칭에서 설비 상세가 UI-01 겹침 규칙 때문에 장면과 6px 겹치던 것 → 옆 칸 배치.
  - 검증: typecheck·lint·format·build, vitest 412, 3D 브라우저 13 passed(1인칭 신규 3 포함), 1인칭 1440·390 설비 선택·상세·Esc 해제 직접 확인, M-14·M-15 넓은 패널 1440 한 화면, 공식 스모크 **169 passed**(9.6분, exit 0).
  - 참고: DOC-02는 직전 배포(`a35e895`)에 포함되어 이미 운영에 반영됨(작성 세션의 현황 기록은 '배포 보류'였음).
- 배포(2026-09-27): push `24179d1..ad199c1`, 서버 pull(백엔드 변경 없음, API 재시작 없음) → 프런트 빌드·rsync. 확인: 새 번들 해시 일치·API 5xx 0, 운영 게스트 M-14·M-15 넓은 패널 1440 한 화면, 1인칭 체험 설비 상세 열림, 오류 0(첫 방문은 3D 모델 내려받기 대기 필요).
- FS-023 QMS 설계(2026-09-27, Claude Code): 사용자 결정 "QMS 먼저, 읽기 전용 조회" 반영. 산출물 — 결정서 `docs/plan/QMS도입_교차조회_결정_FS-023.md`(D8 QMS 구현 편입·출하 전 최종검사, D9 읽기 전용 조회 인터페이스 X1~X6·격리 규칙 R6, D10 보류는 표시만, D11 스냅샷 보관, D12 독립 동작), 모듈 설계 `docs/modules/qms/QMS_모듈설계_FS-023.md`(qms 6테이블 컬럼·제약·UK_PARTIAL, 상태 전이, TX-Q1~Q3, 인터페이스 함수, API, 시드 약 126행, AC-97~110), 화면 설계 `docs/ui/화면설계_QMS_FS-023.md`(Q-01~06, 기존 D·L·S·P·V·W 패턴만 사용, MES M-08·M-04 배지). 문서 정리: 현황 5장 교체, QMS·WMS README의 'core 소유' 표현 정정.
  - 검증: 설계 문서 정적 대조만(schema.json 테이블 수 71 = mes 21·erp 27·fems 13·core 10 확인). schema.json·마이그레이션·Excel·ERD·코드 변경 없음(승인 후 FS-023a). `npm run db:validate` 미실행(메타데이터 미변경).
  - 다음: 사용자 승인(결정서 6장 3문항 + 모듈 설계 13장 3문항) → FS-023a.
- FS-023a QMS DB 반영(2026-09-27, Claude Code): 사용자 승인(D8~D12·범위·순서·발번·기본 월·패킹 무관 보류 모두 권장안). `schema.json` v0.10.0 — qms 6테이블(불량 유형·검사 기준·검사 항목·검사·측정값·품질 보류), `core.workspace_module` module_key에 qms. 적용 스크립트 `tools/apply_fs023a.py`(멱등, 새 제약·관계는 끝에 붙여 기존 C·R 번호 유지). 마이그레이션 `20260927_fs023a_qms_schema.py`(revision `fs023a_qms`, 실행 시 JSON 미참조 고정 SQL, 제약 이름 = C·R 번호). 검증 도구: `audit_schema_isolation.py` BUSINESS에 qms + **R6**(다른 솔루션은 `fs.<B>.interface`만 import, AST 검사), `validate_db_design.py` FS-023a 엔티티 목록(설계서 표)·`validate_qms`, `verify_ddl_matches_schema.py`·Excel·ERD 생성기에 qms. Excel 23시트·ERD `qms.mmd` 재생성.
  - 수치: 77테이블 · 785컬럼 · FK 175 · 제약/정책 587(DB 제약: PK 77·UK 178·CHECK 183·INDEX 46·UNIQUE_INDEX 11, SERVICE 정책 92).
  - 검증: `npm run db:validate` 오류 0, 격리 검사 R1~R6 오류 0, 도구 단위 테스트 49 OK(신규 `test_fs023a.py` 5), pytest DB에서 alembic upgrade head → verify_ddl 오류 0 → downgrade -1 → downgrade base → upgrade head → verify 오류 0, 로컬 개발 DB upgrade·verify 오류 0, backend pytest **648 passed**(13분 45초), ruff check·format 통과.
  - 미실행: 공식 스모크(프런트·API 변경 없음, 스모크는 실행 시 head를 자체 적용), 운영 서버 마이그레이션(배포 전).
  - 주의: 새 공간의 `qms` 모듈 행 생성·게스트 세대 복사/정리 순서에 qms 추가는 FS-023b·c. 현재 qms 테이블은 비어 있어 기존 복사·회수에 영향 없음(pytest로 확인).
  - 다음: FS-023b — `fs/mes/interface.py`·`fs/qms/interface.py`, `/api/v1/qms` API(TX-Q1~Q3), Q-01~06 화면, MES 배지.


## 2026-09-27 비전검사 AI 설명·세 시나리오 (FS-3D-AI01, 로컬 구현)

- 브랜치 `codex/vision-ai`, 기준 `origin/main 8851772`. 기존 `codex/home-ui-polish` 작업은 보존하고 통합된 1인칭 코드에서 시작했다.
- 정상/불합격 증가/정지 전환, 상태등·판정 주기·검사 정지 연동, AI 설명 버튼 구현. 확인된 사실 / 원인 가능성 / 다음 확인 항목을 구분한다. 활성 시나리오 재선택은 누계를 보존한다.
- 고정 합성 비교 자료: 정상 2%→2%, 증가 2%→20%(+18%p), 정지 처리량 100→50개. 실시간 애니메이션 누계·실제 검사 이미지·업무 센서값과 구분한다.
- 인증·CSRF가 필요한 읽기 전용 설명 API, 서버 전용 OpenAI Responses 어댑터, 성공 캐시·동시 호출 제한·실패 대기 구현. 키 미설정/공급자 오류는 출처가 표시된 데모 설명으로 대체한다. DB·스키마·업무 데이터 변경 없음.
- 프런트 420개/46파일, typecheck/lint/format/build 통과. 서버 DB 없는 모의 공급자 테스트 13개, Ruff 검사/포맷 통과. 배포 wheel의 시나리오 JSON 포함 확인.
- 실제 OPENAI_API_KEY가 없어 실제 Astra 호출·응답 품질·계정 접근은 미검증. 공용 DB 스모크·Safari·실기기 성능은 미실행. main 병합·push·운영 배포 없음.
- 남은 통합 작업: 커밋 반영 검토 → 공식 스모크 → 백엔드 재시작·프런트 재빌드. 실제 AI를 활성화할 경우 서버 비밀 설정에 키를 추가하고 세 시나리오 응답 확인. 운영 반영 여부와 무관하게 키 없이 데모 체험 가능.
- 설계 `docs/modules/factory/README.md`, 상세 인계·재현 명령 `docs/agent/3D공장_AI설명_FS-3D-AI01.md`. 이번 범위 구현 완료, 운영 통합과 실제 모델 검증은 남음.


### 최종 검증 (FS-3D-AI01)

- Node 24 typecheck/lint/format:check/build 통과, Vitest **420 passed / 46 files**.
- DB 없는 backend 설명 테스트 **13 passed**, Ruff check/format 통과. wheel에 `fs/factory/scenarios.json` 포함 확인.
- Chromium 기존 회귀 13개 통과. 신규 시나리오·모바일 2개는 최종 분리 실행 **2 passed**. 전체 실행에서는 한 테스트가 접힌 비교 자료의 중복 문구를 찾아 실패했으나, 보이는 설명 문구를 선택하도록 수정한 후 재검증했다. 총 15개 시나리오 검증, 최종 단일 전체 실행은 반복하지 않았다.
- 1440×900 1인칭 설명 화면과 390px 모바일 패널 캡처 직접 확인. 모바일 가로 넘침 없음. 빌드의 기존 3D 청크 크기 경고와 THREE.Clock 사용 중단 예정 경고는 남아 있다.
- 실제 모델 요청과 공용 DB 스모크는 실행하지 않았다. 작업 폴더 `factory-studio-codex`, 브랜치 `codex/vision-ai`. 결과물은 이번 완료 커밋에 포함되며 원격 push/배포는 하지 않았다.


## 2026-09-27 합성 이미지 검사실 (FS-VISION-LAB01)

- 사용자 승인 범위 구현: 정상/이물/조명 변화 샘플, 전체/중앙 ROI, 임계값·최소 연결 면적 조절, 원본/이진화 화면과 검출 영역, OK/NG 및 오검출·미검출·영역 밖 결함 픽셀 수. 레시피·결과 JSON 다운로드.
- `/factory/vision-lab`, 비전검사 설비 상세에서 진입. 브라우저 순수 함수의 요청/결과 v1 계약 분리. OpenCV·C++·C#·실장비·AI 분석은 연결하지 않음. 새 서버·DB·의존성 없음.
- `codex/vision-ai`, 기준 `0f16bb6`에 후속 구현. 프런트 425 tests / 47 files 통과, typecheck/lint/format/build 통과. 모의 API·5186에서 신규 Chromium 진입/조건 변경/JSON 다운로드/모바일 가로 넘침 검사 통과. 공용 DB 스모크·실장비·Safari 미검증.
- 상세 설계·후속 연결 계약·재현 명령: `docs/agent/합성이미지검사실_FS-VISION-LAB01.md`. 이번 합성 범위 완료. 다음은 통합 검토와 사용자 체험이며 C++/C# 엔진은 별도 후속 범위. 원격 push·운영 배포 없음.
- 통합·배포(2026-09-27, Claude Code): main에 FS-023b + UI-03 B2(`d194cb9`) + Codex 비전검사 AI 설명(`0f16bb6`)·합성 이미지 검사실(`da2f02a`) 병합(`2ef0578`). 검증: ruff·격리 R1~R6 0, vitest 435, 백엔드 설명 테스트 13, 공식 스모크 **187 passed**(11.8분). push `8851772..2ef0578`, 서버 pull·`alembic upgrade head`(→ `fs023b_qms_module`)·API 재시작, 프런트 빌드·rsync(번들 `index-aVsvqfGf.js` 일치). 운영 게스트 확인: QMS Q-01~06·MES 패킹·E-02 견적 패널·`/factory/vision-lab` 열림, 페이지 오류 0·5xx 0. OPENAI_API_KEY 미설정 → AI 설명은 데모 응답.


## 2026-09-27 P-02 홈 UI 정돈 (Codex)

- 작업 폴더 `factory-studio-codex`만 사용. 브랜치 `codex/home-ui-polish`, 기준/마지막 이전 커밋 `8851772`(origin/main). 이 인계는 `P-02: Figma 참고 홈 UI 정돈` 커밋에 포함하며 최종 해시는 `git log -1`로 확인한다. 기존 `codex/factory-building`은 그대로 보존.
- 끝난 것: 흰색 홈 헤더·로고, 중앙 본문/배너, 기본 아이콘·이름·분류만 노출, 설명/상태 호버·포커스·터치 안내, 미구현 영역 제거. 현재 공간·도움말·실제 진입·역할 메뉴 유지. 보고서 `docs/agent/홈_UI_정돈.md`.
- 검증: Node 24.21.0 PATH. typecheck/lint/format:check/build/test(418개/45파일) 및 독립 Chromium 8개, diff --check 각각 exit 0. 데스크톱/호버/360px 직접 확인. backend·DB·공용 포털 스모크 미실행.
- 재현: 전용 폴더에서 `export PATH="/opt/homebrew/opt/node@24/bin:/opt/homebrew/bin:/usr/bin:/bin"`, `npm --prefix frontend run test:home-browser`. 5187 포트·모의 API만 사용, 테스트 서버 자동 종료. 공용 8000/5173과 DB는 사용하지 않는다.
- 새 의존성 없음. package.json은 검증 스크립트만 추가. 공통 CSS·업무/3D·스키마 변경 없음. .env/work/node_modules 제외.
- 다음: 사용자 시각 검토 후 통합 담당자가 main에 반영·운영 확인. Codex는 push/main 병합/배포 없이 멈춘다.


## 2026-09-27 연속 검사 모드 (FS-VISION-RUN01 완료)

- 사용자 확인한 연속 검사 범위 구현. `codex/vision-ai`, 기준 `da2f02a`. 기존 3종 20회 반복, 500/200ms, 시작/일시정지/재개/종료, 시작 시 레시피 고정.
- OK/NG/합격률/평균 알고리즘 시간, 샘플별 NG, 누적 오검출·미검출·ROI 밖 픽셀. NG 당시 원본/이진화·좌표·면적 조건 재조회, 실행 기록 JSON 다운로드.
- 비동기 어댑터 경계와 세대별 늦은 응답 폐기, 화면 이탈 정리. 설정 이동/탭 숨김 일시정지. 한 배치 20건 메모리 보관, 새 배치·화면 이탈 시 교체/소멸.
- Node 24: typecheck/lint/format/build 통과, Vitest 431 tests / 48 files. Chromium 기존 합성 검사실 1개 + 신규 배치·JSON/라이프사이클 2개 통과(최종 신규 2개 재실행 통과). 1440·390 캡처 직접 확인, 360·390 가로 넘침 없음.
- 실장비·PLC·C++/C#·backend/DB 스모크·Safari 미검증. 기존 3D 청크·Clock 경고 유지. push/운영 배포 없음.
- 다음: 사용자 체험·통합 검토, 이후 별도 작업으로 가상 PLC 상태 머신. 설계 `docs/modules/factory/README.md`, 상세 계약·재현 `docs/agent/연속검사모드_FS-VISION-RUN01.md`.


## 2026-09-27 가상 PLC 핸드셰이크 (FS-VISION-PLC01 완료)

- 사용자 후속 진행 승인. `codex/vision-ai`, 기준 `74a4ec2`. 연속 검사에 선택형 PLC 모드 추가, Ready/Trigger/Busy/Done/OK·NG/Interlock 신호, 요청 ID별 이벤트 로그.
- 300ms 검사 제한·1000ms 확인 제한, 1회 지연/확인 누락 주입, 수동 확인, 중복 트리거 차단, 결과 래치, 명시적 리셋·새 배치 복구. 타임아웃/취소 후 늦은 응답 무효화.
- PLC 수량은 확인까지 끝난 거래만 반영. 확인 실패 결과는 PLC 진단 스냅샷에 보존하고 NG 수량과 분리. 0건 실패 배치도 신호/알람/로그 JSON 다운로드 가능.
- Node 24 최종 typecheck(빌드 포함)/lint/format/build 통과. Vitest **443 tests / 49 files**. Chromium 관련 5개 통과, 로그 ID·알람 표시 보정 후 신규 PLC 2개 재실행 통과. 1440·390 캡처 직접 확인, 모바일 가로 넘침 없음.
- 브라우저 모의 프로토콜. Ready_Req ON 고정, Recipe_ID=RUN_SNAPSHOT. 실제 PLC·통신 SDK·C++/C#·MES·backend/DB 스모크·Safari 미검증. 기존 3D 청크/Clock 경고 유지. push·운영 배포 없음.
- 다음: 사용자 체험/통합 검토 후 C++ OpenCV 코어 분리 및 동일 입력의 결과 비교. 상세 `docs/agent/가상PLC_FS-VISION-PLC01.md`, 공통 설계 `docs/modules/factory/README.md`.


## 2026-09-27 C++ OpenCV 검사 코어 (FS-VISION-CORE01 완료)

- 사용자 후속 진행 승인. `codex/vision-ai`, 기준 `7ec4519`. `native/inspection_core`에 C++17 정적 라이브러리·CLI·CMake·예제·비교 테스트 구현.
- 기존 요청 v1과 검사실 {request,result} JSON 입력, stdin/파일/NDJSON 지원. 결과 source=synthetic-opencv-cpp-v1. 임계값 `<`, 연결 4/SAUF, 픽셀 면적 `>=`, ROI·영역 순서·정답 평가를 웹과 일치시킴.
- CTest 2개 프로그램 통과(8.72초). 원본 TS 엔진 직접 실행과 19,968개 입력 비교: 불일치 0. C++ 핵심 사례, 입력 타입·범위·JSON 오류, NDJSON 오류 후 복구, 파일 입력 검증 통과. 예제 이물 결과 80/36px²·NG 확인.
- 검증 환경: macOS arm64, Apple Clang 21, CMake 4.4.3(Homebrew로 이번 설치), Node24, OpenCV4.13.0·nlohmann-json3.12.0 소스 빌드. 제3자 소스/빌드/로그는 work/에만 보관. CMake4와 OpenCV 내부 정책 경고는 남으나 최종 빌드·테스트 성공.
- 웹/서버/PLC 패널은 기존 브라우저 엔진 유지. 실행 연결·실영상·C#·Windows/Linux·실장비·배포 미검증/미구현. 프런트 코드를 바꾸지 않아 기존 443개 테스트/브라우저 스모크는 이번에 재실행하지 않음. push·운영 배포 없음.
- 다음: 사용자 체험 후 C# 프로세스/통신 어댑터 또는 웹 서버의 네이티브 호출 연결 범위 확정. 요청 ID·취소·시간 제한·출력 검증 계약 필요.
- 재현: `cmake -S native/inspection_core -B work/inspection-core -DINSPECTION_FETCH_DEPS=ON -DCMAKE_BUILD_TYPE=Release -DNODE_EXECUTABLE=/opt/homebrew/opt/node@24/bin/node`; `cmake --build work/inspection-core --parallel 4`; `ctest --test-dir work/inspection-core --output-on-failure`.
- 상세: `native/inspection_core/README.md`, `docs/agent/C++검사코어_FS-VISION-CORE01.md`.


## 2026-09-27 C++ 웹 호출·사용자 참고 문서 (FS-VISION-CONNECT01 완료)

- 사용자 요청한 C++ 호출 연결과 도움말 반영 완료. `codex/vision-ai`, 기준 `848778b`. 운영 배포는 사용자가 직접 진행하며 이번에 push·main 통합·운영 접속/재시작/배포 없음.
- 인증/CSRF POST /api/v1/factory/vision/inspect, 서버 고정 절대경로 VISION_CORE_EXECUTABLE 실행. 2초·동시4개/프로세스·출력1MiB 제한, 요청/결과 모델 검증, 오류503/429/502/504, 브라우저 대체 없음. C++ --timed 추가(기본 CLI 출력 유지).
- 검사실 C++ 단건/JSON, 연속 검사 엔진 선택, PLC 선택 엔진 호출·취소. 엔진 출처·고정 레시피·요청 ID 연결, 순수 C++ 시간 표시. 클라이언트 취소/늦은 응답 폐기.
- 도움말 사용자 참고 문서/포털에 `portal/vision-lab` 추가, 전체 사용 흐름·설정·20회 배치·PLC 장애/복구·JSON·한계 집필. 검사실 왕복 링크·검색·모바일 확인.
- 최종 검증: 프런트 448 tests/50 files, 타입(빌드)/lint/format/build 통과. DB 없는 서버 27 tests(실제 C++·인증/CSRF·검증·미설정·출력오류/상한·시간제한·동시제한·취소) 통과, Ruff check/format 통과. CTest2개 통과, 웹 비교19,968개 불일치0.
- Chromium 관련6개 최종 단일 실행 통과(1.3분). 모의 인증·실제 API·실제 C++ 바이너리로 단건/20회/PLC20회 및 JSON·도움말 확인. 기존 모의 API 회귀 포함. 실제 화면 캡처 확인, 도움말390px 가로 넘침 없음.
- 공용 DB/운영인증/운영배포·Windows/Linux·실장비 미검증. 기존 3D 청크/Clock 경고와 Python 테스트 클라이언트 사용중단 경고 유지.
- 배포 인계: `docs/agent/C++웹연결_FS-VISION-CONNECT01.md`. 서버 OS에서 바이너리 빌드/검증 → 서비스 환경 VISION_CORE_EXECUTABLE 절대경로 설정 → 백엔드 반영·재시작 → 프런트 재빌드·반영 → 게스트C++/PLC/도움말 확인. tests/factory_native_preview.py는 모의 인증이므로 운영 사용 금지.


## 2026-09-29 Codex FS-026b1 진행 중 (main 내용 유지 후 추가)

- 작업 위치 factory-studio-codex, 브랜치 codex/vision-ai. origin/main `6508599`로 rebase 완료. 이전 HEAD `521ad76`은 `backup/vision-ai-before-fs026b1-20260929` 보존. rebase 직후 HEAD `df6014e`. main의 BEMS 시드 템플릿 11,910 / 복사 11,908행 유지.
- FS-026a 완료: migration head `fs026a_wms_receiving_reservation`, metadata v0.13.0 /98테이블·1022컬럼·225 FK. 기존 migration 변경 없음. 이전 상세 보고 docs/agent/WMS확장_DB_FS-026a.md.
- 현재 b1: receiving.py/receiving_schema.py, 입고 예정/도착/검수/원천 선점 API와 기존 sync 연계, NORMAL/QUARANTINE 마스터 보호, snapshot 날짜만 복사·digest 불변 구현 중. 입력400/멱등422, 신규 처리 시각 DB clock_timestamp 통일.
- 아직 검증 완료 아님. 신규 테스트 실패 수정 중이며 전체 pytest/ruff/격리 감사는 최종 실행 필요. 완료 후 보고를 갱신한다. 실행: 전용 *_test DB에 DATABASE_URL/TEST_DATABASE_URL 설정 후 `backend/.venv/bin/pytest backend/tests --tb=short -q`, `uv run --project backend ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py`, `python3 tools/audit_schema_isolation.py`. 비밀값은 저장/출력하지 않는다.
- 사용자 지정 단계: b1(TX-W4~7/AC140~150) 보고 후 사용자 확인 대기. b2 예약·소진·가용(TX-W8~9/AC151~158)은 아직 시작 금지. 이후 화면/트럭/시드·도움말도 별도. push·배포 미승인.

### FS-026b1 검증 중간 갱신
- 입고 API23개 통과(별도 PG 연결 경합, 전량 부족, 취소/원천변경, 환산/복사/격리, 멱등, 줄 순서 오류 경로, 초안 삭제 뒤 발번 포함). 전량 부족 sync 영수증은 전표가 없으므로 inbound_notice ID로 저장한다.
- 기존 W-03 새 상태 및 검수 전표 이름의 최소 표시 호환 추가. WMS 프런트10개·typecheck·변경 ESLint 통과. 입고 전용 화면은 미구현.
- 전체 백엔드 pytest 재실행 중. ruff check/format134파일 통과, R1~R6 감사 오류0, db:validate 오류0. 최종 전체 결과 전에는 완료로 인계하지 않는다.


## 2026-09-29 FS-026b1 최종 완료 — 다음은 사용자 확인 후 b2

- 위 중간 WIP 상태를 이 항목으로 대체한다. 브랜치 codex/vision-ai, 기준 main6508599, 마지막 구현 a832fa8(16045ae 포함), 마지막 보고커밋은 git log -1. main 본문은 보존했다.
- 입고 예정·도착·검수·원천선점/해제/사후대사와 기존 ERP sync 단일 경로 완료. 400 필드오류/422 멱등, 날짜 제외 digest, 복사 confirmedAt 날짜만 이동·digest 불변, 신규 서버 시각 통일. 기존 W-03 새 상태/NULL 전표 호환 포함.
- 최종 검증: **backend 전체755 passed, 2 warnings, 1204.94초**; 신규 입고23 포함. tools58+subtests13, WMS 프런트10, typecheck·변경 ESLint, CI ruff check/format134파일, R1~R6 감사0, db:validate0. 자동 탐색 ruff의 기존18 I001 파일은 main과 동일하며 CI 명령은 통과했다.
- 전용 factory_studio_codex_fs026b1_final_test DB에서 실행. head fs026a_wms_receiving_reservation 유지. 공유 개발/운영DB·migration·schema/Excel/ERD·BEMS 시드11,910 기준 변경 없음. .env/work 스테이징 없음. push·배포 없음.
- b2 예약·소진·가용 조회(TX-W8~W9/AC151~158)는 **사용자 b1 확인 전 시작하지 않는다**. AC141의 예약가능95 조회도 b2에 남는다. 이후 입고 화면/3D 트럭/시드·도움말·브라우저 검증. 신규 입고 화면은 아직 없으며 프로젝트 전체 완료가 아니다.
- 상세 및 재현 명령: docs/agent/WMS확장_API_FS-026b1.md. 테스트에 필요한 전용 *_test DB 환경만 주입하면 표준 pytest 명령으로 재현되며 work 임시 도구에 의존하지 않는다.


## 2026-09-30 FS-026b2 WIP — 예약·소진·가용

- 사용자가 다음 진행 방향 1번(b2)을 승인했다. 브랜치 codex/vision-ai, 기준 3f5039c/main6508599. TX-W8~W9, AC151~158 구현. 예약 생성/해제, ERP 확정 출하 전량 소진, 원장·예약 경합 직렬화, 격리 제외/위치별 부족 보존, ERP off 가용 계산.
- ERP 조회는 interface.py만 사용. 신규 처리 시각 clock_timestamp, FS_TODAY 미사용. 게스트 예약 번호 날짜 이동/FK 재매핑. 기존 W-01/02 가용 표시 호환만 반영; W-08/09 미구현.
- 현재 관련 API60개(신규22 포함), WMS 프런트10개/typecheck/변경 ESLint 통과. CI ruff138파일, R1~R6 감사0, db:validate0. 전체 pytest 전용 factory_studio_codex_fs026b2_final_test에서 실행 중. 최종 결과 전 완료 아님.
- migration/schema/Excel/ERD 변경 없음. 템플릿11,910 유지. .env/work 스테이징 금지, push·배포 없음. b2 최종 보고 후 사용자 확인을 기다린다.
- 재현: 전용 *_test DB의 DATABASE_URL/TEST_DATABASE_URL을 환경으로 제공한 뒤 backend/.venv/bin/pytest backend/tests -q --tb=short. Ruff는 backend/pyproject.toml 명시(CI 명령). 상세 docs/agent/WMS확장_API_FS-026b2.md.


## 2026-09-30 FS-026b2 완료 — 다음은 사용자 확인 후 화면

- 위 b2 WIP 상태를 이 항목으로 대체한다. 사용자 후속 1번 승인에 따라 TX-W8~W9/AC151~158 완료. 브랜치 codex/vision-ai, 기준 main6508599/3f5039c, 구현 0d639b7. 최종 보고 커밋은 git log -1.
- 예약 생성·해제·ERP 확정 출하 전량 소진, 동일 원천 단일 전표, sync 경합, 정상 현재고−활성 예약, 격리 제외, 위치별 부족 보존, ERP off 가용 계산. AC141 예약가능95 조회도 검증 완료.
- 입력400/멱등422, clock_timestamp 처리 시각 통일, FS_TODAY 미사용. ERP interface 조회만 사용, 게스트 예약 날짜/FK 복사. 기존 W-01/02 화면·도움말 새 계산식 호환. 신규 W-08/09 화면은 아직 없음.
- 최종 검증: **backend 전체777 passed, 2 warnings, 1414.37초**(신규22 포함). 관련 WMS60, 프런트 전체490/56파일, 도구58+subtests13, typecheck/build/변경 ESLint 통과. CI ruff check/format138파일, R1~R6 감사98테이블/225FK 오류0, db:validate 오류0. 기존 사용중단 경고2와 프런트 청크 경고 유지.
- 전용 factory_studio_codex_fs026b2_final_test에서 실행. migration head fs026a_wms_receiving_reservation 유지; schema/Excel/ERD·시드 기준11,910/복사11,908 및 seed/validate.py·test_seed/test_common 변경 없음. 공유 개발/운영DB 변경·push·배포 없음, .env/work 스테이징 없음.
- 다음: **사용자 b2 확인 후** W-08 입고 예정/도착/검수와 W-09 예약 화면 및 브라우저 흐름 검증. 이후 3D 트럭 도착·체험 시드·종합 사용자 도움말·통합 점검. 신규 화면/브라우저/운영 검증은 이번에 하지 않았다.
- 상세 API/AC 근거 및 비밀값 없는 표준 재현 명령: docs/agent/WMS확장_API_FS-026b2.md. 전용 *_test DB 환경을 주입하고 pytest backend/tests 실행, Ruff는 backend/pyproject.toml 명시. main HANDOFF 본문은 보존했다.


## 2026-09-30 FS-026 후속 UI·트럭·시드·도움말 통합 WIP

- 사용자 b2 후속 전체 승인: 화면 → 3D 트럭 → 시드/도움말 → 통합 검증까지 중간 확인 대기 없이 진행. push·배포는 제외. 기준 9c66cf1, codex/vision-ai.
- W-08/09, 읽기 전용 출하 대조 미리보기·날짜/예약부족 필터, 기존 W-01~07 연결, 3D 도착 API, 정상/격리 위치, 포털 사용자 흐름 문서 구현 중.
- 새 템플릿 sv-20260930-1: WMS22행 추가, 총11,932/복사11,930. BEMS4,218행 그대로. 기존5품목, R-Q01/F-Q01, 예정/도착/95·3·2 검수/전량부족/취소, 활성/해제/소진 예약. 소진 시드는 기존 역사 출고 전표를 새 템플릿의 소진 예약 이력으로 연결하며 추가 차감하지 않는다. PI-0004/SH-0004 미반영 유지. 운영 기존 템플릿은 수정하지 않는다.
- 관련 backend76개 통과(새 preview/filter 테스트 추가 검증 중). 실 API 브라우저 트럭도착→원장0→검수95/3/2 및 새로고침 통과. 다른 브라우저 시나리오/전체 회귀는 진행 중이며 완료 아님.
- 로컬 전용 fs026_ui_test / fs026_browser_test 사용. 브라우저용 API localhost8000은 현재 실행 중(합성 시크릿, 로컬 쿠키). 테스트 종료 후 중지 예정. .env/work 스테이징 금지.
- 다음: 브라우저 실패 수정·모바일/3D 캡처 확인, 전체 pytest/프런트·ruff·격리 감사·도움말 링크·문서 갱신. 최종 커밋/인계 후 종료.

### 2026-09-30 FS-026 후속 최종 검증 중간 갱신

- W-08/09 저장 응답의 최신 version을 즉시 상세에 반영해 연속 조작 경합을 보완했다. 3D 외관·트럭 패널, W-01 수량 표시도 최종 정리.
- 실제 API Chromium 통합10개 전부 통과(1.2분). 프런트 전체491개(57파일, maxWorkers=2), 전체 ESLint/Prettier/typecheck/build 통과. Ruff139파일, R1~R6 오류0, DB 검증 오류0.
- 전체 백엔드는 깨끗한 별도 DB에서 실행 중이다. 최종 완료 항목 전까지 완료로 판단하지 않는다. 보고: `docs/agent/WMS확장_화면트럭통합_FS-026.md`.

## 2026-09-30 FS-026 후속 통합 완료 — 입고·예약 화면 / 트럭 / 시드·도움말

- 앞선 후속 WIP 상태를 대체한다. 사용자의 후속 전체 승인 범위 완료. `codex/vision-ai`, main6508599 기준 유지, 구현 `cd41b04`, 연속 조작 보완 `0ad25ee`. 마지막 문서 커밋은 `git log -1`.
- W-08 입고 예정·도착·검수·원천 연결, W-09 예약·출하 대조·소진, 기존 W-01~07 정상/격리/예약/가용 표시·동선 확장. 저장 응답의 최신 version을 즉시 반영하여 빠른 다음 조작의 이전 버전 사용을 방지한다.
- 3D 트럭은 서버 도착 상태만 변경한다. 검수 때만 재고 증가, 예약 때 원장 불변, 소진 시 기존 출하 원천과 중복 차감 방지. 통신 실패/재시도/응답 유실 복구/미저장 보호 포함. CNC 수량·GPS/실차·실장비 연결 제외.
- 시드 sv-20260930-1: 템플릿11,932 / 게스트11,930, 기존 품목·BEMS4,218 유지. WMS22행 추가. 새 migration 없음(head fs026a_wms_receiving_reservation), metadata98테이블/1022컬럼/225FK 유지. 기존 템플릿·운영 DB 수정 없음.
- 최종 검증: 전체 backend **779 passed**(23분39초, 기존 경고2), frontend **491 passed /57파일**(maxWorkers=2), 실제 API Chromium **10 passed**(1.2분). 전체 typecheck/lint/format/build 통과, Ruff139파일 통과, R1~R6 격리 감사0·db:validate0, tools58+subtests13 통과. 기본 병렬 프런트 실행의 기존 ERP 테스트 일시 실패·재검증 및 경고는 통합 보고에 기록.
- 도움말 W-08/09, 기존 W-01~07, 사용자 참고 `/help/portal/wms-flow` 반영. 360px와 트럭 외관 캡처 확인. 보고·재현·AC 증거: `docs/agent/WMS확장_화면트럭통합_FS-026.md`.
- 검증용 API/Vite 종료. `.env`·work 스테이징 없음. **push·운영 배포 없음. 이번 승인 범위 남은 개발 없음.** 다음은 사용자의 통합/운영 반영: 백엔드·프런트를 함께 적용하고 새 템플릿 생성·검증 후 새 게스트에서 체험한다. 기존 기록을 소급 변경하지 않는다.

## 2026-10-01 FS-030 GW 결정서 — 승인 대기

- 사용자 GW 별도 담당 지시에 따라 fetch 후 최신 origin/main7a2d70f(67540be 후속)에서 `codex/fs-030-gw` 생성. 작업 폴더 factory-studio-codex만 사용, vision-ai에서 이어 개발하지 않음.
- `docs/plan/GW도입_전자결재_결정_FS-030.md` 작성. D60~D69, AC220~239 범위 유지. 합성 담당자/실제 인증 주체 구분, 순차 결재·회수·재상신 불변 이력, 원문 변경·off·최신 회차 배지, 글 포함/댓글·첨부 제외 해석을 승인안으로 보완.
- 권장: ERP 매입 전표 한 종류+일반 기안, E-11 읽기 전용 배지 포함. ERP 교차 쓰기/확정 통제 없음. 결정은 아직 승인되지 않음.
- 킷의 공용 개발 DB 적용 지시는 이번 전용 DB 지시로 제외. 적용 migration 불변과 병합 head 변경 충돌은 DB 착수 전 재확인 및 새 연결 방식 조율로 기록. 현재 head fs026a_wms_receiving_reservation, metadata v0.14.0/103테이블 유지.
- 검증: 문서 상대 링크5개·D번호10개·AC20개·현황173/200줄 정적 검사 통과(exit0), git diff --check 통과(exit0). 제품 코드/스키마 변경이 없어 pytest·프런트·브라우저·migration·시드·격리 감사는 미실행. DB 접속/공용 서버 실행 없음.
- 다음: **사용자 결정서 승인 후** GW 모듈/README·G-01~07 화면 설계. 전체 설계 승인 전 schema.json·migration·제품 코드 작성 금지. 이후 a/b/c 각각 보고 후 대기. push·배포·main 병합 없음. 최종 문서 커밋은 git log -1로 확인.

## 2026-10-01 FS-030 GW 전체 설계 작성 — 승인 대기

- 사용자 “진행해줘”를 결정서 권장안 4항목 승인으로 기록(D60~69). 브랜치 codex/fs-030-gw, main7a2d70f/선행 결정커밋 b873543.
- 새 문서: docs/modules/gw/GW_모듈설계_FS-030.md, 같은 폴더 README.md(현재 기준/조회 계약), docs/ui/화면설계_GW_FS-030.md. 결정서·로드맵·현황 갱신.
- gw8테이블, G01~07+E11 읽기 배지, TX-G1~6/API/권한/잠금/오류/불변 이력·재상신·원문 digest/복사·시드69행(+모듈행1 별도) 설계. AC220~239 연결. source digest는 ERP 소유 정규화 함수로 일원화; 제공 interface 사이 재귀 호출 금지.
- 검사: 문서4개 상대 링크17개·테이블8·화면7·AC20·시드합69·현황173/200줄 정적 검사 통과(exit0), git diff --check 통과(exit0). 최초 임시 검사 정규식이 interface 함수까지 테이블로 세어 실패했으며 식별자 패턴 보정 후 통과. 제품 검증 결과가 아님.
- 미실행: pytest·vitest·브라우저·DB migration·시드 생성·격리 감사. 문서만 작성했고 제품 코드/schema.json/Excel/ERD/migration 변경 및 DB 접속 없음.
- 다음: **사용자 모듈·화면 전체 설계 확인 후 FS-030a DB**. a 착수 전 최신 main/head/공통 파일·SPC/CMMS 시드 합계 재확인. 적용 migration 수정 금지, Codex 전용 DB/포트만 사용. a/b/c 각각 보고 후 대기. push·배포·main 병합 없음. 최종 문서 커밋은 git log -1.

## 2026-10-01 FS-030a DB WIP

- 사용자 “구현 진행해줘”로 모듈·화면 전체 설계 승인. origin/main6350697(FS-040 포함) 위 rebase 완료, codex/fs-030-gw. GW 8테이블·스키마 목록·복사·모듈 기본행 및 Excel/ERD 구현. head fs030b_gw_module, down fs040_app_review.
- 전용 factory_studio_codex_fs030_test: DB 제약·시드·공통 회귀45 passed, 도구69 passed, 실제 DDL 대조/설계 검증/격리 감사 오류0. 전체 backend/UI/browser 미실행. downgrade 왕복·기존 공간 backfill 검증과 최종 문서 정리 남음.
- FS-030b API/화면은 아직 시작하지 않음. a 최종 보고 후 사용자 확인 대기. push·배포·main 병합 없음. .env/work 스테이징 금지. 상세 표준 재현 명령은 최종 a 보고에 남긴다.

## 2026-10-01 FS-030a DB 완료 — 다음은 사용자 확인 후 b

- 앞선 GW WIP/승인대기 상태를 대체한다. 전체 설계 “구현 진행해줘” 승인. main6350697에 rebase한 codex/fs-030-gw, 구현15f9398·최종커밋 git log -1.
- 신규8테이블·복사/초기화·모듈행/평가모듈CHECK, schema/Excel/ERD 일치. 임시0.15.0-gw,112테이블·1,225컬럼·258FK, headfs030b_gw_module(fs040 뒤). 템플릿11,934/복사11,932. 적용 기존migration 변경 없음.
- 전용DB pytest45/도구69 통과, Ruff154파일·격리/DDL/정적 오류0, 빈DB 왕복·기존공간GW true/ERP false·유데이터 downgrade 거부/전체롤백 통과. Excel39시트/GW4미리보기 확인. 전체backend/UI/browser 미실행.
- 상세 변경파일·검증/미실행·재현은 docs/agent/GW_DB_FS-030a.md. SERVICE 정책/권한/결재 로직은 아직 b 미구현이며 DB 제약과 구분한다.
- b 사용자 확인 후 API·G01~07·ERP조회계약/E11배지·런처/평가 gw 허용·전환/문서/e2e. c69업무행/도움말/흐름맵/전체검증. push·배포·main 병합 없음. Codex전용DB만 적용, 공유DB/8000/5173 서버 사용 없음. .env/work 스테이징 없음.

## 2026-10-03 FS-030b API·화면 WIP

- 사용자 “이어서 진행해줘”로 b 승인. main8531c05까지 fast-forward(GW a 병합·SPC 시드·CMMS DB/운영 기록 유지), branch codex/fs-030-gw. 스키마 v0.17.0/headfs029b_cmms_module 그대로.
- GW 서비스/읽기 interface/ERP 조회계약, G01~07·ERP 배지·런처 연결 구현 중. 순차 결재·반려/재상신·회수·게시정정·역할 검사·멱등·스냅샷 불변. ERP 코드 조회만, 교차쓰기 없음.
- 첫 관련 API11개 통과 후 경합/ERP 배지/원문변경 등을 확장 검사 중. typecheck 통과. 전체pytest·frontend·실제브라우저는 아직 완료 아님. 전용 factory_studio_codex_fs030b_test만 사용.
- 다음: 추가 회귀·브라우저 검증/오류 보정·문서/최종보고. c업무69행/도움말은 사용자 b 확인 뒤. push·배포 없음. .env/work 스테이징 금지.
