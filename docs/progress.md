# 개발 진행 기록

> 최신 후속 작업: 2026-09-28 FS-FACTORY-CNC01 로컬 구현 완료. 신규 로드맵 2/6단계; 다음은 WMS 공통 설계. 상세는 문서 마지막 항목 참조.

## 현재 상태
- 단계: **FS-023c + P-02 홈 UI·제목 운영 반영 완료(`be87546`). P-01 진입 목록 QMS 추가는 로컬 커밋(미배포). FS-024 WMS·홈 아이콘·C++ 비전 엔진 운영 반영 완료(`adc3cab`, head `fs024b_wms_module`, 템플릿 7,691행). FS-025a BEMS DB 완료(로컬, head `fs025b_bems_module`). FS-025 BEMS 전체(API·화면·시드·도움말) 완료(로컬, main `489d5f3`까지 push). FS-026 WMS 확장은 Codex가 결정서부터.**
- 기준본: 현재 상태는 `docs/plan/현재기획_진행현황.md` 하나로 판단한다. 작업이 끝나면 반드시 갱신한다
- DB: **v0.9.1 / FS-008c / 71테이블·712컬럼·161 FK·제약/정책 526**, 정적 검증 오류 0·격리 위반 0. Excel·ERD 재생성 완료. FS-009 로컬 DB 적용·대사 완료, 서비스 미구현
- 시드: **7,469행, `sv-20260924-1`**. FS-015 생성·복사 구현, FS-015b created_at 시간축·V12 재검증 완료
- 프로젝트: `/Users/hwang-kyoungho/projects/factory-studio` (worktree: `/Users/hwang-kyoungho/projects/factory-studio-ag`)
- 제품 구현: FS-009 뼈대·최초 마이그레이션, FS-015/015b 시드, FS-016 공통 인증·세션·멱등 완료. 백엔드 테스트 총 36개 (common 11, schema_verifier 9, seed 16). 업무 API·화면은 미구현

## 2026-09-28 MAP-01 연계 시스템 분석 (Claude Code)
- 입력: 사용자 제공 `manufacturing-systems.html`(16개 시스템). 결과: `docs/plan/연계시스템_분석_MAP-01.md`.
- 누락 11개 분류·연결(받는 것/주는 것)·결정 충돌 점검·P-03 흐름도 2장(계층 아키텍처·시스템 카탈로그) 설계.
- 코드·DB·정적 콘텐츠 변경 없음. 검증 명령 실행 대상 아님. 다음: 사용자 확인 후 MAP-02(다른 개발 종료 후).

## 2026-09-28 FS-025c BEMS 시드·도움말·흐름 맵·통합 검증 (Claude Code)
- push `b9dfbc4..489d5f3`(FS-025b 2부).
- 시드 `_bems`: 1시간 진행과 같은 모델로 30일 시간 단위 시뮬레이션 → 공용 전력 2,160·환경 2,016·명령 16·경보 4(해제 3 + T−1 확인 대기 1) 등 **4,218행**. 템플릿 7,692 → **11,910**, 복사 11,908, `sv-20260928-1`. 잔여 30일 모두 ≥ 0. 상세: 모듈 설계 16장.
- 모델 보정: `CO2_IDLE` +10 → −30(비재실 자연 환기). +10이면 밤새 쌓여 해제 직후 같은 경보가 다시 떴다.
- 도움말 `content/help/bems/b-01~07.md`, 공통 안내·P-02·P-03·P-04 갱신. 흐름 맵 `building_energy` 업무 노드(`bems/b-02`) + 실선, 스키마에 bems, `content/cards/bems.md` 삭제(P-04는 SCM만).
- 화면 보정(시드로 브라우저 확인): B-02 기간 합계 비율 막대, B-01 "환경 센서 없음", B-04 모드 선택 정렬.
- 테스트: `test_bems` 13(시드 시연 1 추가, 기존 테스트는 시드를 지운 빈 BEMS에서), 격리 테스트는 다른 공간에 내 명령이 없음을 확인하도록 조정. test_seed·test_common 합계 갱신. vitest 479(흐름 맵·카드·도움말 수).
- 복사 시간: 중앙값 0.509초·최대 0.619초(10회) — 1초 미만.
- 로컬 개발 DB `factory_studio` 템플릿 재생성(11,910행). 로컬 게스트는 291개(전부 만료)라 상한 20에 걸려 새 게스트가 막힌다 — 확인용으로 `GUEST_LIMIT=1000`을 넘겨 띄웠다(설정 파일은 커밋하지 않음).
- 검증: pytest 724 passed · 1 skipped(16.3분), vitest 479, typecheck·lint·format·build 0, ruff 0, db:validate 0, 격리 R1~R6 0, 전체 스모크 231 passed · 1 skipped(템플릿 11,910)
- 미실행: 운영 반영(마이그레이션 `fs025a_bems`·`fs025b_bems_module` + 템플릿 재생성 필요). push 없음.
- 다음: 운영 배포 준비(사용자 확인 후), Codex FS-026 결정서 검토.

## 2026-09-28 FS-025b 2부 BEMS 화면 B-01~07 (Claude Code)
- push `9965100..b9dfbc4`(1부 API).
- `frontend/src/bems/` 7화면 + 공통(`useGet`·1시간 진행 `AdvanceControl`·`LineChart`·`ShareBars`·`nextBoundary`), 라우트 `/bems/*`(lazy). 상세: 화면 설계 6장.
- 포털: 6번째 타일 BEMS 건물관리, 격자 940px 한 줄·360px 3·3, "여섯 시스템"(홈·진입·헤더·P-02 도움말), 하단 설명 카드는 SCM만, 다른 앱 링크·P-05 목록에 BEMS.
- API 추가 `GET /simulation/clock`(계약서 16장).
- 결함 수정: B-03이 구역 목록 전 `undefined === undefined`로 관측을 읽어 앱이 멈춤(e2e에서 발견) → vitest 회귀.
- 검증: typecheck·lint·format·build 0, vitest 477 passed, test_bems 12, ruff 0, home-browser 9, e2e bems 2(화면으로 기준정보 등록 → 규칙 → 전원·모드·설정값 거부/적용 → 1시간 진행 경보 → 확인 → 그래프 / FEMS 끔), 전체 스모크 228 passed · 1 skipped · 3 failed → 재실행 4 passed(원인: 스모크 GUEST_LIMIT 200 초과로 끝 WMS 2건 429 — 400으로 올림, 3D 걷기 테스트는 30초 경계 지연).
- 미실행: 운영 반영. 도움말 b-01~07 없음(링크 404) — FS-025c. push 없음.
- 다음: FS-025c — BEMS 시드·도움말·흐름 맵·`cards/bems.md` 삭제·통합 검증.

## 2026-09-28 FS-025b 1부 BEMS API (Claude Code)
- push `1b2a8a2..9965100`(FS-025a).
- FEMS 조회 인터페이스 `fs/fems/interface.py`(신규): `enabled`·`site_electricity`(최상위 전력 계측기 일별)·`manufacturing_electricity`(DIRECT_METER 배분 일별). BEMS는 이것만 읽는다(R6).
- BEMS 모듈 `fs/bems/`: `simulation.py`(1시간 모델 상수·계산 한 곳, `__main__` 자체 점검), `service.py`(기준정보·관측·분해·공조 상세·명령 TX-B1·스케줄 교체·1시간 진행 TX-B2·경보 TX-B3·대시보드), `schema.py`, `router.py` → `/api/v1/bems`. 계약: API 계약서 16장, 모듈 설계 15장.
- 결함 수정(개발 중): SQL 별칭 `day`(예약어) → `reading_day`; 시뮬레이션 시계를 KST로 반환; 수동 명령을 실제 시각으로 기록해 명령 이력 순서가 스케줄 명령과 뒤집히던 문제 → 수동 명령도 시뮬레이션 시계로 기록.
- 검증: `test_bems.py` 12 passed(AC-125~135·137), 전체 pytest 723 passed · 1 skipped(13.7분), ruff check·format 0, 격리 감사 0, `simulation.py` 자체 점검 ok.
- 미실행: 화면·e2e(2부), 스모크, 운영 반영. push 없음.
- 다음: FS-025b 2부 — 화면 B-01~07, 포털 6번째 타일.

## 2026-09-28 FS-025a BEMS DB 반영 (Claude Code)
- 사용자 승인: 화면 설계 → BEMS 전체 설계 확인. push `f0b1012..1b2a8a2`.
- 메타데이터 `tools/apply_fs025a.py`(멱등) → `schema.json` v0.12.0 / 93테이블(bems 10: 구역·공용 계측기·환경 센서·공조기·공용 전력 관측·환경 관측·운전 스케줄·제어 명령·경보 규칙·경보), 954컬럼, FK 209, 제약·정책 726(bems C647~C725, R187~R208). 모듈 CHECK `'bems'`.
- 마이그레이션 `fs025a_bems`(스키마) + `fs025b_bems_module`(기존 공간 bems 행 — WMS 교훈으로 DB 단계에 함께). 새 공간·시드 템플릿 모듈 행 7개(시드 7,692·복사 7,690).
- R4 해제: `audit_schema_isolation.py` FORBIDDEN에서 bems 제거, FS-013 머리말 주석, `test_fs014.py` R4 예시 정리. 검증 도구 `validate_bems`, `tools/test_fs025a.py` 3, ERD `bems.mmd`·Excel 31시트, "후속 예약 설계" 표시 제거.
- 결함 수정: `verify_ddl_matches_schema.py`가 CHECK의 `'%'`(습도 단위)를 psycopg 자리표시자로 읽어 실패 → `exec_driver_sql` 3곳 `%` 이스케이프.
- 검증: db:validate 0, 격리 R1~R6 0, tools unittest 55 OK, 임시 DB upgrade → DDL 대조 0 → downgrade base → upgrade → 0(head `fs025b_bems_module`), pytest DB·**로컬 개발 DB `factory_studio`** head 반영 + 로컬 템플릿 재생성(7,692행), pytest **711 passed · 1 skipped**(18.2분), ruff 0.
- 미실행: 공식 스모크(프런트·API 변경 없음), 운영 마이그레이션. push 없음.
- 다음: FS-025b — `fs/fems/interface.py`, `/api/v1/bems`(TX-B1~B3·1시간 진행 모델), B-01~07.

## 2026-09-28 FS-025 BEMS 결정·모듈 설계 승인, 화면 설계 초안 (Claude Code)
- 사용자 승인: 결정서 D18~D23·범위, 모듈 설계 13장 4건 모두 권장안 → 두 문서 "확정".
- 화면 설계 `docs/ui/화면설계_BEMS_FS-025.md`(문서만): B-01 대시보드(D)·B-02 에너지 분해(L, FEMS 교차 조회)·B-03 환경 모니터링(D, 설정값 점선·값 표)·B-04 공조 운전(V + FormPanel, 제어·1시간 진행)·B-05 운전 스케줄(W)·B-06 경보(L + DetailPanel, 규칙 S)·B-07 구역·계측(P). 메뉴 묶음 "건물 현황·운전·경보·기준정보"(화면 제목과 중복 방지). 포털 6타일 한 줄(940px)·"여섯 시스템"·설명 카드 SCM만·흐름 맵 `building_energy` 업무 노드. FEMS 화면 변경 없음.
- 확인: Codex는 `codex/vision-ai`에서 문서 커밋 `aac8d26`(정밀 부품 공장 컨셉·CNC 범위, 옛 main `b6c82a0` 기준) 진행 중 — WMS README를 함께 고쳐 병합 때 충돌 예상.
- 다음: 화면 설계 확인 = BEMS 전체 설계 확인 → FS-025a(메타데이터 v0.12.0·마이그레이션·Excel·ERD·R4 해제).

## 2026-09-28 로컬 개발 DB 갱신 + FS-025 BEMS 설계 초안 (Claude Code)
- 사용자 보고 "로컬 main에서 WMS가 꺼져 있고 안 보인다" → 원인: 로컬 개발 DB `factory_studio`가 `fs023b_qms_module`·옛 템플릿(`sv-20260924-2`)에 머물러 wms 스키마·모듈 행이 없었다(테스트 DB만 올렸음). `alembic upgrade head`(→ `fs024b_wms_module`, 공간 295개에 wms 행) + 템플릿 재생성(7,691행). 기존 게스트 공간은 WMS 데이터가 비어 있어 새 게스트·세대 초기화 필요. 코드 변경 없음.
- BEMS 검토 → 사용자 답: (나) 공용 분해 + 환경 관측, 공용 계측기 BEMS 소유, 1시간 간격, **공조 제어·설정값·경보·운전 스케줄 포함 필수**.
- 산출물(문서만): 결정서 `docs/plan/BEMS도입_공용에너지_결정_FS-025.md`(D18~D23 — R4 해제, FEMS `interface.py` 신규, 잔여 음수 불일치 표시, 모의 공조기 + "1시간 진행" 결정적 시뮬레이션, 경보 발생·확인·해제), 모듈 설계 `docs/modules/bems/BEMS_모듈설계_FS-025.md`(bems 10테이블, 시뮬레이션 모델, TX-B1~B3, API, 화면 B-01~07 요약, 시드 약 5,300행, AC-125~138, 13장 결정 4건). BEMS README 정정(옛 "core 소유"·"테이블 예약" 표현).
- 기본값으로 둔 것: 환경 관측 기간 14일(사용자는 간격만 지정 — 13장 1번에서 확인).
- 다음: 사용자 승인 → 화면 설계 → 전체 설계 확인 → FS-025a.

## 2026-09-28 운영 반영 (FS-024 WMS·홈 아이콘·C++ 비전 엔진)
- 서버(사용자 실행): pull `be87546..adc3cab`, uv sync, `alembic upgrade head` → **`fs024b_wms_module`**(fs024a_wms·fs024b_wms_module 적용), C++ 엔진 `/srv/factory-studio/bin/inspection_core` 복사(서버 `x86_64`, 서버에서 직접 실행 NG 80·36·0.76ms), `.env`에 `VISION_CORE_EXECUTABLE`, API 재시작(`active`), 템플릿 재생성 → 워크스페이스 24·세대 24, **7,691행·76테이블**. 프런트 rsync.
- 운영 확인(Claude Code, 새 게스트 25): 번들 `index-D4uQORuS.js` 일치, 홈 "제조 현장의 다섯 시스템"·5타일 한 줄(84px), WMS W-03 미반영 PL-0006(FG-T300 LT-0009·LT-0012 982 EA씩), `POST /api/v1/factory/vision/inspect` 200·NG 80·36·0.72ms, 검사실 "C++ 단건 검사" 화면 NG 2개·116 px²·0.619ms. 콘솔 오류는 로그인 전 세션 조회 401 1건(정상).
- 미확인: 서버 `journalctl` 5xx(운영 SSH는 사용자만).

## 2026-09-27 배포 준비: WMS·홈 아이콘 + C++ 비전 엔진 (Claude Code)
- push `d910955..133845f`. 프런트 `origin/main 133845f` worktree 빌드(`../fs-build`, 번들 `index-D4uQORuS.js`).
- C++ 엔진: 서버(1 vCPU·2GB, Ubuntu 24.04)는 apt nlohmann-json 3.11 < 요구 3.12, Node 없음(CMake `find_program(node REQUIRED)`), OpenCV 컴파일 부하 → 사용자 선택으로 **맥 Docker linux/amd64 Ubuntu 24.04에서 빌드**. `native/inspection_core/build-linux.sh` 추가(OpenCV 4.13·JSON 3.12 고정 버전 정적 포함, 결과 `work/inspection-core-linux/bin/inspection_core`).
- 빌드: 첫 시도 QEMU 에뮬레이션에서 gcc 세그폴트(병렬 2) → 병렬 1로 재시도 성공(약 1시간). 검증: CTest `native_core` 통과, 웹 비교 **19,968건 불일치 0**(에뮬레이션이 느려 CTest 120초 제한 대신 직접 실행), `--timed` foreign → NG 80·36, 의존 라이브러리 libstdc++·libm·libgcc_s·libc만.
- 배포 절차 8-1장 추가(빌드·복사·`VISION_CORE_EXECUTABLE`). 서버 반영은 사용자 실행 대기.

## 2026-09-27 FS-024c WMS 시드·도움말·흐름 맵·포털 정리 + 홈 아이콘 크기 (Claude Code)
- 사용자 지시: `d910955` push, FS-024c 진행, 홈 솔루션 아이콘의 흰 상자를 참고 이미지 크기로 축소.
- 시드 `_wms` 107행(`sv-20260927-2`, 템플릿 7,691·복사 7,689), 게스트 복사 `document_month`·`WD-` 번호 날짜 이동, 검증 V2·V12 확장. 상세 `docs/modules/wms/WMS_모듈설계_FS-024.md` §17.
- 도움말 `content/help/wms/w-01~07.md`, 공통 안내·M-06 문구, 흐름 맵 `inventory_move` 업무 노드(스키마 wms 허용), 노드정의서 FS-005a 11번. 홈·헤더·진입 "다섯 시스템", 진입 하단 WMS, 설명 카드 BEMS·SCM(`content/cards/wms.md` 삭제), P-05 WMS 구역.
- 홈 아이콘: 흰 상자 168px → **84px**(아이콘 40px), 넓은 화면 5개 한 줄, 540px 이하 3·2(72px). 안내 `i` 버튼은 상자 모서리. 데스크톱·호버·360px 스크린샷 확인.
- 테스트: `test_wms.py` `blank` fixture(시드 지운 빈 공간) + `test_seed_demo_flow`(15), `test_seed`·`test_common` 기대값, `wms.spec` 시드 기준, 흐름 맵·카드·홈 테스트 갱신.
- 검증: pytest **711 passed · 1 skipped**(13.7분), vitest **470 passed**, typecheck·lint·format·build 0, ruff 0, 홈 브라우저 8 passed, 공식 스모크 첫 실행 209 passed·7 failed(개발 서버가 `ContentPages.tsx` 동적 import를 한 번 못 가져와 포털 문서 화면 7건 연쇄 실패 — portal.spec 단독 83 passed) → **재실행 216 passed**(12.7분). 복사 중앙값 0.470초.
- 미실행: push·운영 배포(템플릿 재생성·마이그레이션 `fs024a_wms`·`fs024b_wms_module` 적용 필요).

## 2026-09-27 FS-024b-2 WMS 화면 W-01~07 (Claude Code)
- 완료: `frontend/src/wms/` 7화면(D·L·L·W·L·P·S 패턴, 새 패턴 없음), 런처 WMS 타일(5개 3·2 배치), 내 공간 스위치, 다른 앱 링크 4곳, `LineIcon` wms, App 라우트. 사이드바 묶음 "재고"로 변경(화면 설계 1장 갱신 — W-02 제목과 중복 제목 방지).
- 도구: `tools/run_portal_smoke.py`에 인자 전달(예: `... run_portal_smoke.py e2e/wms.spec.ts`). 인자 없으면 기존처럼 전체.
- 검증: typecheck·lint·format·build 0, vitest **470 passed**(`wms.test.tsx` 7), 공식 스모크 전체 **215 passed · 1 failed**(`wms.spec` 선택자 중복 — 빈 상태 링크와 같은 이름) → 수정 후 `wms.spec` 3 passed, 이어서 홈 격자 3·2 조정 뒤 portal·layout·home·wms 묶음 **165 passed**. 360px 원천 반영·홈, 1440 홈 3·2 스크린샷 직접 확인. ruff 0.
- 미실행: 수정 후 전체 스모크 재실행(바뀐 것은 wms.spec 선택자·홈 격자 CSS — 해당 묶음으로 확인).
- 남은 것(FS-024c): WMS 시드, 게스트 복사 `document_month`·`WD-` 번호 날짜, 도움말 w-01~07, 흐름 맵 `inventory_move`, 홈 제목 "다섯 시스템"·설명 카드 WMS 제거.

## 2026-09-27 FS-024b-1 WMS 조회 인터페이스·API (Claude Code)
- 사용자 지시: Codex 비전검사 병합·push 후 "제안대로" — FS-024b를 API(1부)·화면(2부)으로 나눠 중간 보고.
- 완료: MES 인터페이스 3함수(입고·완료 실행 투입·품목 분류 옵션), ERP 인터페이스 신규(출하·매입·미출하 지시·사용 여부), `/api/v1/wms`(창고·위치·품목·단위·가져오기, 원천 목록·반영 TX-W1·매입 취소 되돌림 TX-W3, 기초·조정·이동 전표 TX-W2, 현재고·가용, 원장·누계, 대시보드), `fs024b_wms_module` 데이터 마이그레이션, 모듈 행 5 → 6(시드 7,584·복사 7,582), 공간 정리·시드 복사 목록에 wms. API 계약서 15장.
- 검증: `test_wms.py` 14 passed, pytest 전체 **710 passed · 1 skipped**(13.9분, 네이티브 C++ 미빌드 skip), 격리 R1~R6 0(WMS는 `fs.mes.interface`·`fs.erp.interface`만 import), ruff check·format 0, db:validate 0, 임시 DB upgrade → DDL 대조 0 → downgrade base → upgrade → 0(head `fs024b_wms_module`).
- 미실행: 공식 스모크(프런트 변경 없음 — 내 공간 화면은 알려진 솔루션만 그려 wms 행을 무시), 동시 반영 부하 시험(공간 잠금으로 직렬화).
- 다음: FS-024b-2 — W-01~07 화면, 런처·내 공간 스위치·다른 앱 링크, e2e·layout.

## 2026-09-27 통합: Codex 비전검사 연속 검사·가상 PLC·C++ 엔진 연결 (codex/vision-ai `b6c82a0`) (Claude Code)
- 병합: `74a4ec2` 연속 검사·배치 이력, `7ec4519` 가상 PLC 핸드셰이크·오류 복구, `848778b` C++ OpenCV 검사 코어·일치 테스트, `b6c82a0` 인증된 C++ 검사 API(`POST /api/v1/factory/vision/inspect`)·사용자 참고 문서(`content/help/portal/vision-lab.md`).
- 검토: `fs/factory/native.py` — 셸 없는 `create_subprocess_exec`, 절대 경로·실행 권한 확인, 엄격한 입력·출력 스키마, 동시 4·2초 제한·1MB 출력 한도, 인증·CSRF. DB 쓰기 없음. `.env.example`에 `VISION_CORE_EXECUTABLE=`(비어 있으면 503, 브라우저 검사는 그대로).
- 충돌: HANDOFF·현황·progress 기록만(양쪽 보존). 통합 보정: `test_factory_native.py` import 정렬(ruff I001, CI 범위).
- 검증: vitest **463 passed**(첫 전체 실행은 부하로 무관한 6건 시간 초과 → 해당 파일 단독 70 통과, 재실행 전체 통과), typecheck·lint·format·build 0, ruff check·format 0, 격리 R1~R6 0, pytest **696 passed · 1 skipped**(실제 C++ 실행 파일 테스트 — 로컬 네이티브 미빌드), 공식 스모크 **200 passed**(12.2분).
- 미실행: 네이티브 빌드(CMake·OpenCV)·웹/C++ 일치 재검증(Codex 보고 19,968건 불일치 0), 운영 배포. 배포 시 서버 C++ 빌드 → `VISION_CORE_EXECUTABLE` 설정 → API 재시작 → 프런트 빌드(`docs/agent/C++웹연결_FS-VISION-CONNECT01.md`).

## 2026-09-27 FS-024a WMS DB 반영 (Claude Code)
- 사용자 승인: 화면 설계 권장안 → WMS 전체 설계 확인(결정서·모듈 설계·화면 설계 모두 "확정").
- 메타데이터: `tools/apply_fs024a.py`(멱등) → `schema.json` v0.11.0 / 83테이블(wms 6: 창고·보관 위치·품목·단위 환산·재고 전표·재고 이동), 847컬럼, FK 187, 제약·정책 647(wms C587~C646, R175~R186). 모듈 CHECK에 `'wms'`.
- 마이그레이션 `20260927_fs024a_wms_schema.py`(revision `fs024a_wms`, down `fs023b_qms_module`, 고정 SQL). 모듈 행 데이터 마이그레이션은 FS-024b.
- 도구: `validate_db_design.py` FS-024a 엔티티 목록·`validate_wms`, `audit_schema_isolation.py` BUSINESS에 wms, `verify_ddl_matches_schema.py`·Excel·ERD 생성기에 wms, `tools/test_fs024a.py` 3. Excel 27시트·ERD `wms.mmd` 재생성, ERD 탐색기 문구 정정.
- 검증: `npm run db:validate` 오류 0, 격리 R1~R6 오류 0, tools unittest 52 OK, 임시 DB에서 `alembic upgrade head` → `verify_ddl_matches_schema.py` 오류 0 → `downgrade base` → `upgrade head` → 오류 0(임시 DB 삭제). pytest DB `factory_studio_fs016_test`를 `fs024a_wms`로 올린 뒤 pytest **683 passed**(12.4분). ruff check·format(CI 범위) 0, diff --check 0.
- 참고: 첫 전체 pytest는 pytest DB를 새 head로 올리기 전이라 `test_schema_verifier::test_baseline_matches` 1건 실패(예상된 것) → 업그레이드 후 재실행 통과.
- 미실행: 공식 스모크(프런트·API 변경 없음), 운영 마이그레이션(배포 전). push 없음.
- 다음: FS-024b — `fs/mes/interface.py` 함수 2개 추가·`fs/erp/interface.py` 신규, `/api/v1/wms`(TX-W1~W3), W-01~07 화면, `wms` 모듈 행 데이터 마이그레이션, 공간 정리·시드 복사 스키마 목록에 wms.

## 2026-09-27 FS-024 WMS 결정·모듈 설계 승인, 화면 설계 초안 (Claude Code)
- 사용자 승인: 결정서 D13~D17·범위, 모듈 설계 13장 4건 모두 권장안 → 두 문서 상태 "확정".
- 화면 설계 `docs/ui/화면설계_WMS_FS-024.md`(문서만): W-01 대시보드(D)·W-02 재고 현황(L)·W-03 원천 반영(L, 원천 4종 탭 — 교차 조회 시연)·W-04 재고 전표(W, 기초·조정·이동)·W-05 재고 원장(L, 조건 시 누계)·W-06 창고·위치(P)·W-07 품목·단위(S + MES 가져오기). 새 패턴 없음 — `DataTable`에 행 선택이 없어 W-03은 행 반영 + 탭 전체 반영. 포털 5타일(3·2 배치)·"다섯 시스템"·설명 카드 BEMS·SCM, MES M-06 안내 문구만 변경.
- 검증: 문서만(`npm run db:validate` 영향 없음). 코드·schema.json 변경 없음.
- 다음: 화면 설계 확인 = WMS 전체 설계 확인 → FS-024a(메타데이터 v0.11.0·마이그레이션·Excel·ERD·격리 R1/R5).

## 2026-09-27 FS-024 WMS 설계 초안 (Claude Code)
- 사용자 검토 요청 → 권장안 승인(완제품+원자재, 버튼 반영, 음수 허용·표시만, 예약 제외·가용 계산, 완제품 LOT·원자재 수량, 창고 2 + 위치 1단계).
- 산출물(문서만): 결정서 `docs/plan/WMS도입_재고원장_결정_FS-024.md`(D13~D17, MES·ERP 인터페이스 추가 — ERP는 첫 `interface.py`), 모듈 설계 `docs/modules/wms/WMS_모듈설계_FS-024.md`(wms 6테이블, 원천 4종 `source_key` 멱등 반영, TX-W1~W3, API, 화면 W-01~07 요약, 시드 약 110행, AC-111~124, 13장 결정 4건). WMS README 상태 갱신.
- 조사 근거: MES 투입 차감 없음·실행 중 투입 삭제 가능, MES 패킹 `shipped`는 시드만, ERP 출하 재고 확인·MES 조회 없음(`packing_no` 문자열), ERP 매입 입고 없음·확정 후 취소 있음(PI-0006).
- 검증: `npm run db:validate` exit 0(메타데이터 미변경). schema.json·마이그레이션·코드 변경 없음.
- 다음: 사용자 승인(결정서 6장 + 모듈 설계 13장) → 화면 설계 → 전체 설계 확인 → FS-024a.

## 2026-09-27 P-01 진입 화면 하단 목록에 QMS 추가 (Claude Code)
- `Entry.tsx` 하단 목록에 "QMS / 품질관리"(4개). `portal.spec.ts` 360px 진입 테스트에 QMS 문구 확인·스크린샷 추가.
- 검증: vitest 440, typecheck·lint·format·build 0, 공식 스모크 **196 passed**(12.1분). 360px 스크린샷 직접 확인(두 줄 배치, 가로 넘침 없음).
- 확인: UI-03은 이미 8화면 전체 완료·배포 상태였다(HANDOFF '다음' 행이 낡아 있었음 → 수정). 정해진 다음 작업 ID 없음.
- 미실행: push·운영 반영(사용자 확인 대기).

## 2026-09-27 운영 반영 (FS-023c·P-02 홈 UI·제목 변경)
- 서버(사용자 실행): `git pull` `2ef0578..be87546`, `uv sync`, `alembic upgrade head`(변경 없음, head `fs023b_qms_module`), API 재시작. 템플릿 재생성 `seed.cli template` → 워크스페이스 15·세대 15, **7,583행·70테이블**(QMS 6테이블 113행 포함).
- 프런트: `origin/main be87546` worktree 빌드 → rsync. 운영 번들 `index-CfwQDw0y.js` 일치(공개 URL로 확인).
- 운영 확인(Claude Code 브라우저, 새 게스트 공간 16): 진입·홈 "제조 현장의 네 시스템", 타일 MES·ERP·FEMS·QMS, 하단 WMS·BEMS·SCM 링크 / Q-03 검사 대기 LT-0017(대기)·LT-0015(작성 중) / M-08 패킹 LT-0016 "QMS 보류" 배지. 콘솔 오류는 로그인 전 세션 조회 401 1건(정상 동작).
- 미확인: 서버 `journalctl` 5xx 점검(운영 SSH는 사용자만 실행 가능). 진입 화면 하단 목록은 MES·ERP·FEMS 3개만 표시(QMS 없음) — 후속 정리 후보.

## 2026-09-27 P-02 홈 UI 정돈 main 통합 (Claude Code)
- 확인: 로컬·원격 브랜치 중 main에 내용이 빠진 것은 `codex/home-ui-polish`(`086f4d7`, Codex) 하나였다. 나머지(3D·UI-01·FS-019a·FS-018h 등)는 다른 해시로 이미 통합됨.
- 병합 `d93b757`: 새 홈 디자인 기준으로 `Home.tsx` 충돌 해결 — QMS 4번째 타일·방패 아이콘 추가, 사용자 결정으로 하단 "아직 만들지 않은 것"(WMS·BEMS·SCM 설명 카드 링크) 유지. 4열 격자, 540px 이하 2×2. 문서 3건은 양쪽 기록 모두 보존.
- 테스트: `home-polish.test.tsx`(하단 링크·QMS 타일), `e2e/home.spec.ts`(QMS 타일, 360px QMS 안내 가로 넘침 없음), 도움말 p-02 갱신.
- 검증: vitest **440 passed**, typecheck·lint·format 0, 홈 브라우저 8 passed, 공식 스모크 **196 passed**(11.4분). 데스크톱·360px 스크린샷 직접 확인.
- 제목 변경(`0739167`): 홈·헤더·진입 화면 "제조 현장의 네 시스템", 진입 문구 MES · ERP · FEMS · QMS, p-03 도움말. vitest 440, 홈 브라우저 8, 공식 스모크 **196 passed**. push `96dd616..0739167`. 운영 서버 명령은 사용자 실행(HANDOFF '다음 할 일').

## 2026-09-27 FS-023c QMS 시드·게스트 복사·도움말·흐름 맵 (Claude Code)
- 시드: `backend/seed/generate.py` `_qms` 113행(불량 유형 6·기준 4·항목 16·검사 17·측정값 68·보류 2), `sv-20260927-1`, 템플릿 7,583행·게스트 복사 7,581행. `validate.py` EXPECTED_COUNTS·V2(검사 월·번호 날짜)·V3(LOT 스냅샷 = MES 완료 LOT).
- 복사: `seed/copy.py` `inspection_month` = 옮긴 검사일의 월, `QI-`/`QH-` 번호 속 날짜 이동. 복사 중앙값 0.359→0.405초(10회).
- 테스트: `test_seed.py`·`test_common.py` 기대값(7,583/7,581, qms 스키마 포함), `test_qms.py` fixture가 QMS 시드를 지운 빈 상태에서 시작 + `test_seed_demo_flow` 추가. e2e `qms.spec.ts`를 시드 기준(LT-0017 검사→보류→배지→재검사 해제, FG-C100 v2 초안 게시)으로, `portal.spec.ts` QMS 노드 → `/help/qms/q-03`.
- 도움말 `content/help/qms/q-01~06.md`, 공통 안내 절 추가. 흐름 맵 품질검사 노드 `solution`(스키마 qms 허용), 직결선 "QMS를 끄면 이 경로"(점선 아님). 설명 카드 QMS 제거, P-05에 QMS 구역. 노드정의서 FS-005a·배포절차(시드 변경 시 템플릿 재생성) 갱신.
- 검증: pytest **683 passed**(11.9분, fs016_test), vitest **434 passed**, tsc·eslint·prettier·build 0, ruff check·format 0, db:validate 0, audit_schema_isolation 0, tools unittest 49 OK, diff --check 0. 공식 스모크 **188 passed**(11.5분, exit 0). 첫 실행은 187 passed·1 failed(`portal.spec.ts` QMS 카드 이동 — 카드 제거에 맞춰 도움말 이동으로 고침) 후 재실행.
- 미실행: push·운영 배포·운영 템플릿 재생성(사용자 확인 대기). 360px는 스모크 portal 경로 목록으로만 확인.
- 다음: 사용자 확인 → push·배포.

## 2026-09-27 통합·배포 (FS-023b·UI-03 B2·비전검사)
- 통합·배포(2026-09-27, Claude Code): main에 FS-023b + UI-03 B2(`d194cb9`) + Codex 비전검사 AI 설명(`0f16bb6`)·합성 이미지 검사실(`da2f02a`) 병합(`2ef0578`). 검증: ruff·격리 R1~R6 0, vitest 435, 백엔드 설명 테스트 13, 공식 스모크 **187 passed**(11.8분). push `8851772..2ef0578`, 서버 pull·`alembic upgrade head`(→ `fs023b_qms_module`)·API 재시작, 프런트 빌드·rsync(번들 `index-aVsvqfGf.js` 일치). 운영 게스트 확인: QMS Q-01~06·MES 패킹·E-02 견적 패널·`/factory/vision-lab` 열림, 페이지 오류 0·5xx 0. OPENAI_API_KEY 미설정 → AI 설명은 데모 응답.

## 2026-09-27 FS-023b QMS 조회 인터페이스·API·화면 (Claude Code)
- 완료: `fs/mes/interface.py`·`fs/qms/interface.py`(R6 준수), `/api/v1/qms`(TX-Q1~Q3), Q-01~06 화면, MES 패킹·LOT `QMS 보류` 배지, 데이터 마이그레이션 `fs023b_qms_module`, 새 공간 qms 모듈 행, 시드 행 수 7,470.
- 테스트: `test_qms.py` 21(AC-97~110), `qms.test.tsx` 10, e2e `qms.spec.ts`·layout·portal 360px.
- 검증: pytest 669 통과, vitest 422, tsc·eslint 0, 스모크 181 통과 + 3D `factory.spec.ts:116` 1건(단독 2회 통과, 플래키).
- 미실행: 운영 배포·push. 도움말 페이지 없음(FS-023c).
- 다음: 사용자 확인 후 FS-023c.

## 2026-09-27 UI-03 B2 완료 — ERP 견적(E-02) 넓은 행 편집 패턴 적용

- 작업 ID: UI-03 B2 · 브랜치: `antigravity/ui03-b2`
- 변경 파일:
  - `frontend/src/erp/Quotations.tsx` — E-04(`SalesOrders.tsx`) 패턴으로 전면 교체. 등록 `FormPanel wide`('견적 만들기'), 상세 `DetailPanel wide`(`${quoteNo} ${revisionNo}차`), 라인 편집·확정·제출·수주 전환 폼을 상세 패널 안에 통합. `RevealAnchor`·`master-grid` 제거.
  - `frontend/e2e/portal.spec.ts` — "ERP 견적 작성 → 확정 → 제출 → 수주 전환" 테스트를 패널 흐름으로 갱신 (수주 전환 후 `page.goto("/erp/sales-orders")`로 이동).
  - `frontend/e2e/layout.spec.ts` — E-02 등록 패널(FormPanel wide, 1440×900 높이 제한)·상세 패널(Esc 닫기) 레이아웃 테스트 2건 추가.
- 검증 결과:
  - typecheck ✅ / lint ✅ / format:check ✅ / build ✅ / unit test 44파일 412개 ✅ / git diff --check ✅
  - 포털 스모크 **171/171 통과** (exit 0). 신규 E-02 레이아웃 테스트 2건 포함.
  - `factory.spec.ts:116`(건물 외관 3D 타임아웃)은 기존 불안정 테스트 — B2 무관, 이번 실행에서 통과.
- 스모크 트러블슈팅: `useDiscardGuard`가 dirty 상태에서 Escape를 차단하므로, 수주 전환 후 사이드바 링크 클릭 대신 `page.goto()`로 교체.
- 문서 갱신: `메뉴적용표_UI-02.md` E-02 → 완료(antigravity, B2), 집계 ERP 18→18 완료·대기 0, 합계 48/55.
- 다음: 사용자 확인 후 UI-03 B2 브랜치 리뷰 → main 병합.

## 2026-09-20 프로젝트 준비
- 완료: 독립 프로젝트 디렉터리와 기본 디렉터리 구조 생성, 로컬 Git main 브랜치 초기화.
- 완료: 기획·설계·상세 일정 Markdown 5개를 docs로 이전. 이후 이 위치를 기준본으로 사용.
- 완료: 이전 UI 시제품을 prototypes로 복사. README·AGENTS.md·.gitignore 작성.
- 검증: 원본 파일 존재 및 문서 참조 경로 확인. 실제 앱/DB 테스트는 구현 전이므로 미실행.
- DB migration / Excel / seed: 아직 없음.
- 남은 작업: CPU·메모리·개발 도구·포트 확인, 상세 코드 참조 검토, 첫 업무 카드·학습 수용 기준·ERD·Excel 설계서 초안.
- 다음: FS-001 환경 점검을 마친 뒤 FS-002~004 수행.
- GitHub 원격 생성·업로드 및 서버 변경: 수행하지 않음.

## 2026-09-20 FS-001 완료
- 하드웨어·OS·개발 도구·리스닝 포트·Git 상태를 점검했다.
- 상세 결과: [환경 점검](agent/환경점검_FS-001.md).
- Docker/Compose 명령 없음. 프로젝트용 Python/Node 버전 선정과 설치는 FS-009에서 처리한다.
- 실제 DB 연결, 앱 테스트, 서버 접속, 소프트웨어 설치는 수행하지 않았다.
- DB migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 후 FS-002. 이후에도 작업 ID별 결과 보고와 사용자 확인을 거친다.

## 2026-09-20 FS-002 완료
- 사용자 확인을 받아 로컬 AI 비서 API·스케줄러·SQL·README를 읽기 전용으로 선별 검토했다.
- 결과: [참조 검토 보고서](agent/기존AI비서_참조검토_FS-002.md).
- 채택: 처리 결과 분리, 고유 제약, 작업별 실패 기록, 환경별 설정 분리.
- 새로 설계: 트랜잭션/외부 호출 경계, 모듈별 서비스, 인증·사용자 격리, migration/Excel 동기화, CLI/timer 작업 관리.
- 확인: 스케줄러 실행 주기와 주석/로그 일부 불일치. 서버의 실제 배포 상태는 미확인.
- 검증: 정적 코드·SQL·문서 비교. 기존 코드 실행·DB 연결·서버 접속·기존 파일 수정 없음.
- migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 후 FS-003 첫 업무 카드·사용자 역할·범위 구체화.

## 2026-09-20 FS-003 완료
- 사용자 제공 MES Excel을 읽기 전용으로 분석하고 동일 사본을 docs/references에 보존했다.
- 26개 시트, 22개 테이블, 348개 컬럼 확인. 목차와 상세 컬럼 수 일치, 명시 참조 테이블/컬럼 존재 검증.
- [참고 설계 검토](modules/mes/MES참조설계_검토_FS-003.md): 채택/보완/후속 분리, 원본 위치와 검증 제한 기록.
- [첫 업무 카드·역할·범위](modules/mes/첫업무카드_역할_범위_FS-003.md): 작업지시→LOT→3개 공정→양품/불량 확정, 역할·예외·공통화 경계 정의.
- 원본 수정·DB 변경·기능 구현 없음. 신규 Excel DB 설계서 최초 작성은 FS-007에서 진행.
- 다음: 사용자 확인 후 FS-004 학습 경로·상세 수용 기준.

## 2026-09-20 FS-004 완료
- [학습 경로·수용 기준](modules/learning/학습경로_수용기준_FS-004.md) 작성: 7개 단계, 5개 이해 질문, 34개 정상/오류 검증 시나리오.
- 업무 완료와 학습 완료 구분, 자유 탐색과 고정 과제 차이, 중복 요청·실패 복구·개인 격리·세대 전환·콘텐츠 버전 기준 정의.
- 검증: 문서 AC ID 유일성/연속성, 단계·질문 ID 존재, 예시 수량의 공정별/전체 보존 계산 확인.
- 실제 앱/API/DB 테스트: 구현 전으로 미실행. 시나리오 작성 완료와 테스트 통과를 구분한다.
- migration / Excel / seed: 변경 없음. Excel 초안은 FS-007.
- 다음: 사용자 확인 후 FS-005 공통 ERD 및 데이터 관계 설계.

## 2026-09-20 FS-005 완료
- [공통 ERD·데이터 관계](architecture/공통ERD_데이터관계_FS-005.md) 작성: 4개 관계도, 36개 논리 엔티티.
- 계정/설정/학습 보존 영역과 세대별 기준정보/생산/계측 영역 분리.
- 공간·세대 복합 관계, 경로 버전 고정, 독립 LOT, 실행/확정 실적 분리, 중복 요청, 학습 live binding/보존 요약, 계측 소유 경계 정의.
- 검증: 엔티티 이름 유일성, 관계도 노드와 목록 대응, AC 범주와 데이터 근거의 정적 검토.
- 물리 DDL·DB 실행·migration·Excel·seed: 미작성/미실행. Excel 최초 작성은 FS-007.
- 다음: 사용자 확인 후 FS-006 상태 전이·권한·모듈 의존성·트랜잭션 규칙.

## 2026-09-20 FS-006 완료
- [상태·권한·트랜잭션](architecture/상태_권한_트랜잭션_FS-006.md) 작성.
- 지시/LOT/공정/학습/게시버전/세대 전이, action 권한, 모듈 의존·비활성화 조건 정의.
- 6개 트랜잭션 계약, 공간 우선 락 순서, 중복 요청·실패 복구·에너지 revision 정책 정의.
- 기존 AC-01~34에 AC-35~44 추가: 초기화/모듈 경합·정리 실패·전량 불량·게시 보호·배분 입력 변경 등.
- 검증: 공식 PostgreSQL 잠금/격리 문서 확인, 정책 정적 검토, TX/AC ID 검사. 실제 DB/API 시험은 미실행.
- 물리 스키마/migration/Excel/seed 변경 없음.
- 다음: 사용자 확인 후 FS-007 Excel DB 설계서 초안 및 메타데이터 작성.

## 2026-09-20 FS-007 완료
- Excel DB 설계서 초안 v0.1.0 작성: 8개 시트, 36개 테이블, 345개 컬럼, 72개 외래키.
- 기준 메타데이터, 정적 검증 도구, Excel 재생성 도구와 [갱신 안내](db/README.md) 작성.
- 공간·세대 복합 참조, 업무/학습 버전 일치, 보존·초기화 정책과 258개 제약·인덱스·구현 정책 항목 정리.
- 검증: FS-005 목록·FK 참조 고유키/타입/범위 검사 통과, 수식 오류 검색 0건, 8개 시트 미리보기 확인, 저장 Excel 재개방 대사.
- 실제 DB 적용·마이그레이션·seed·API 테스트 및 Excel 네이티브 앱 검증: 미실행. 원본 MES Excel 변경 없음.
- 다음: 사용자 확인 후 FS-008 아이콘 홈·업무·학습 도움말 기본 화면 설계.

## 2026-09-20 FS-008 화면 설계 완료
- [화면 설계](ui/화면설계_FS-008.md)와 `prototypes/fs-008-ui.html` 작성.
- 독립 아이콘 홈, 앱 검색, 학습 경로/이어하기, L04 입력/오류/결과, 다음 업무 설명, 모듈 관리 연결.
- 제품의 네트워크·권한·세대 변경 복구 상태 및 공통 UI/데이터 연결 계약 정의.
- 검증: Node VM 스텁 기반 화면 생성 및 수량·사유·결과 복귀·모듈 상태 검사 통과. 실제 브라우저 실행은 환경/URL 보안 정책으로 차단되어 시각·모바일·접근성 검증 미완료.
- DB·migration·Excel·seed 변경 없음. 실제 학습 완료 검증이나 API 연동은 미구현.
- 다음: 사용자 확인 후 FS-009 실행 기반 구축. 브라우저 표시 검증은 환경 마련 후 FS-012에 연결.

## 2026-09-20 FS-005a 차분 설계 완료
- 제품 전제 확정: 운영 전환 없는 교육 전용(포트폴리오 목적), Odoo식 단일 앱 런처, MTS(재고생산), 게스트 즉시 체험, 구현 모듈 MES·FEMS·ERP, 준비 중 QMS·WMS·BEMS.
- 산출물: [차분 설계](architecture/차분설계_게스트_ERP_프로세스맵_FS-005a.md), [MTS 전체 흐름 노드 정의서](architecture/MTS_전체흐름_노드정의서_FS-005a.md).
- 철회: 운영 전환을 전제한 `tenant_type = LIVE/SANDBOX` 분리 검토안. FS-005의 범위 키 S=(workspace_id, generation_id)와 주간 초기화 정책을 그대로 유지한다.
- 순증: erp 10개, mes 5개, process_map 3개 테이블. 총 36 → 54. core.workspace +3컬럼 및 부분 유니크 전환, mes.work_order +2컬럼(order_type, sales_order_line_id — MTO 확장 예약, ORDER 값은 거부).
- 트랜잭션 계약 TX-07~11, 수용 기준 AC-45~58 추가. 노드 17개(IMPLEMENTED 14 / MAP_ONLY 3)와 연결 19개 정의.
- ERP 범위는 ERP-1(거래처·판매계획·수주·출하지시·출하·매출)로 한정. ERP-2·3은 후속 재판단, 전자세금계산서는 제외.
- FEMS는 기준정보 등록·조회 화면만 구현한다. 계측 수집 파이프라인·알람 서버는 미구현이며 계측값은 seed로 생성한다.
- 검증: 기존 문서와의 정적 대조만 수행. 실제 DB·API·화면 미실행.
- migration / Excel / seed: 미반영. schema.json과 DB설계서.xlsx 갱신은 FS-007a로 분리한다. 현 생성기가 Codex 번들 Node와 @oai/artifact-tool에 의존해 실행 환경 정리가 선행된다.
- 다음: 사용자 확인 후 FS-007a — 메타데이터·Excel 설계서에 본 차분 반영 및 정적 검증 재실행.

## 2026-09-20 FS-007a 도구 이전·메타데이터 차분 작성
- Excel 생성기를 사설 번들(@oai/artifact-tool)에서 exceljs로 이전했다. 저장소 루트에 package.json 추가(npm run db:validate / db:build).
- 기능 변경: PNG 시트 미리보기 → 시트별 Markdown 표 미리보기. 개요 합계 수식 → 확정 값. Excel 표(ListObject) → 머리행 고정 + 자동 필터. 사유는 docs/db/README.md에 기록.
- validate_db_design.py 확장: 기준 엔티티 목록을 FS-005와 FS-005a 두 문서에서 함께 읽고, erp·process_map 스키마와 백틱 표기를 허용. retention 누락·UK_PARTIAL 빈 규칙 검사 추가. 보고서에 스키마별 테이블 수 추가.
- tools/apply_fs005a.py 작성: FS-005a의 18개 테이블과 컬럼 변경을 기준본에 병합한다. 재실행 가능하며 이미 적용된 상태에서는 아무것도 바꾸지 않는다.
- 범위 앵커 FK는 추측하지 않고 기존 mes.work_order의 정의를 복사해 적용한다. 앵커를 찾지 못하면 스크립트가 중단한다.
- 검증: 실제 기준본과 동일한 구조의 픽스처(6개 테이블)로 apply → validate → build 전 과정을 실행해 테이블 18개 순증, FK 40개 추가, 오류 0건, 8개 시트 생성과 재개방 대사를 확인했다. 멱등 검사도 통과.
- 미수행: 실제 schema.json에 대한 실행. 저장소가 사용자 로컬 장비에 있어 명령 실행 수단이 없다. schema.json·DB설계서.xlsx·validation-report.json은 아직 36개 테이블 기준이다.
- 사용자 실행 순서: npm install → python3 tools/apply_fs005a.py → npm run db:validate → npm run db:build → Excel 재개방 검토.
- 예상 결과: 테이블 36 → 54. erp 10 / mes +5 / process_map 3. 검증 오류가 0건이 아니면 중단하고 오류 내용을 공유한다.
- 사용자 환경 실행 결과(확인됨): 테이블 54, 컬럼 497, FK 112, 제약·정책 345, 검증 오류 0건. 스키마별 core 16 / mes 15 / erp 10 / learning 6 / process_map 3 / fems 2 / bems 2. Excel 재생성 완료.
- 범위 앵커 FK 복사와 복합 UK 컬럼 순서 가정이 실제 기준본과 일치함을 확인.
- 회귀 발견: 옛 생성기가 코드에 하드코딩하던 내용 3종이 시트에서 유실. 변경 이력 v0.1.0 3행, 코드·상태의 공통 단위·cleanup_status 2행, mes.work_order·mes.operation_execution·learning.attempt 전이 문구. 메타데이터에 없던 값이라 검증기가 잡지 못했다.
- 대응: tools/restore_fs007_sheet_content.py 작성. 하드코딩 값을 schema.json으로 이관해 재발을 막는다. 멱등. 사용자 실행 미수행.
- 다음: 사용자 실행 결과 확인 후 FS-004·FS-006·기준 문서 개정(학습 과정 C1~C4, TX-07~11 락 순서, 첫 공개 범위·일정 재산정).

## 2026-09-20 현황 문서 작성
- [현재 기획과 진행 현황](plan/현재기획_진행현황.md) 작성. 새 작업 세션이 이 문서 하나로 현재 상태를 파악하도록 제품 정의·확정 결정·산출물·미수행 항목·문서 간 불일치를 정리.
- README 갱신: 제품 정의를 통합 업무 포털로 수정, 현재 상태를 FS-007a·54개 테이블로 갱신, 도구 실행 명령 추가.
- 일회성 스크립트 2개(apply_fs005a.py, restore_fs007_sheet_content.py)는 적용 완료 후 삭제 대상으로 분류. 이후 설계 변경은 schema.json 직접 수정으로 처리한다.

## 2026-09-20 FS-005b 합성 데이터·세대 시드 정의 완료
- 산출물: [합성데이터 시드 정의](architecture/합성데이터_시드정의_FS-005b.md).
- 시드 사업장을 가상 반도체 후공정에서 **소형 전자부품 양산**으로 변경. 후공정은 수탁가공(MTO) 성격이 강해 판매계획 기점의 MTS 흐름과 어긋난다.
- 기준정보: 품목 6, 공정 3(사출→조립→검사), 설비 8, 거래처 4, 경로 4(미게시 1 포함), 계측기 9.
- 시간축은 절대 날짜 대신 기준일 T 오프셋으로 정의. 업무 데이터 T-60일, 계측 데이터 T-30일로 분리. 난수 미사용.
- 수량 확정: 지시 30 / LOT 26 / 실행 64 / 실적 62 / BOX 30 / PALLET 6 / 입고 6 / 수주 10 / 출하지시 8 / 출하·매출 4. 사전 어림값(LOT 30, 실행 90, PALLET 8)은 상태 분포와 맞추어 조정.
- 계측 해상도를 **1시간**으로 확정. 1분 해상도는 30일·9대 기준 388,800행이라 게스트 진입이 불가능하다. 1시간 기준 6,480행.
- 총 규모 약 6,840행. 그중 95%가 계측이다. 향후 해상도 상향 제안은 이 문서를 근거로 거부한다.
- 세대 생성은 템플릿 세대 1개를 INSERT ... SELECT로 복사하는 방식. 매번 생성 로직을 돌리지 않는다.
- 학습 시작점이 되는 미완료 건과 오류 시나리오 데이터 8종을 의도적으로 심는다. 전량 불량 LOT, 생산량 0 구간, 계측 누락, 미게시 경로 등.
- 제약 명시: 에너지 검증 예시(450 = 288 + 132 + 30)는 공용 계측이 BEMS 소유이고 BEMS가 MAP_ONLY이므로 이번 시드에서 온전히 재현하지 않는다. 전체 − 제조 = 미계측 잔여까지만 표시하고 분해는 BEMS 설명 카드에 기재한다.
- 성능 목표(복사 2초, 첫 화면 3초, 동시 게스트 20)는 목표이며 측정값이 아니다. 실측은 FS-009 이후.
- 검증: 문서 내 수량 합산 정합성과 학습 과정 C1~C4 시작점 존재 여부를 정적 검토. 생성기·DB·성능 실측은 미실행.
- schema.json / Excel / migration: 변경 없음. 시드는 스키마를 바꾸지 않는다.
- 다음: 사용자 확인 후 FS-006a 기준 문서 개정(학습표 C0~C4, 첫 공개 범위 MES/FEMS/ERP, 일정 재산정, TX-07~11 락 순서).

## 2026-09-20 FS-006a 트랜잭션 확장·기준 문서 개정 완료
- 산출물: [트랜잭션·락 순서 확장](architecture/트랜잭션_락순서_확장_FS-006a.md).
- TX-07 출하지시, TX-08 출하 확정, TX-09 매출 인식(TX-08 내부), TX-10 패킹, TX-11 완제품 입고, TX-12 게스트 공간 생성·회수 계약 정의.
- 명시 잠금 순서를 5단계에서 8단계로 확장. 계획(3) / 패킹·입고(5) / 수주·출하·매출(6) 추가. 세대 정리 삭제 순서도 명시.
- 정정: "락 순서를 안 지키면 데드락"이라는 이전 서술은 부정확하다. FS-006은 모든 업무 쓰기가 workspace 행을 먼저 잠그므로 같은 공간의 데드락은 구조적으로 발생하지 않는다. 락 순서는 세대 정리 CLI·게스트 회수·향후 공간 잠금 완화를 위한 것이다. 문서 1.1에 기록.
- 수용 기준 AC-59~64 추가. 동시 패킹·이중 출하·매출 생성 실패·게스트 생성 실패·회수 경합·정리 순서.
- 기준 문서 개정: 개발기준 v1.0 → v1.1. 제목·목적·아이콘 목록·학습표(C0~C4)·모듈 구성·일정·포함 범위 수정.
- 일정 재산정: 12~14작업주 → **20~26작업주**. S1~S5 + 예비. 이전 표는 무효로 표시하고 추적용으로 보존. 납기 약속 아님을 명시.
- 모듈형플랫폼 설계결정 개정: 첫 공개 범위 MES/FEMS/**ERP**, 데이터 책임표에 erp·process_map 추가, bems를 준비 중으로 변경, 사업장 업종 교체.
- FS-006 본문은 손대지 않고 확장 포인터와 모듈 의존성표만 갱신. TX-01~06·AC-01~44는 그대로 유효하다.
- 검증: 문서 간 정합성 정적 대조. 실제 DB 락 실험·동시성 주입·성능 측정은 미실행.
- 미해결 제약: 게스트 공간 복사는 6,840행 단일 트랜잭션이므로 statement_timeout 10초로 부족할 수 있다. 별도 제한을 두고 실측 후 조정한다.
- schema.json / Excel / migration: 변경 없음.
- 다음: 사용자 확인 후 **FS-009 실행 기반 구축**. 제품 코드가 여기서 시작된다.

## 2026-09-20 현황 문서 전면 갱신 및 폐기 문서 식별
- [현재 기획과 진행 현황](plan/현재기획_진행현황.md)을 전체 재작성했다. 부분 편집을 반복하면서 절 3·4·5가 서로 어긋난 상태였다.
- 추가된 내용: 트랜잭션·시드 현황 요약, 일정 20~26작업주, 알려진 제약 4건, **9장 폐기·보류 문서 목록**.
- 수정된 내용: 학습 과정표에 단계·검증 조건 작성 여부 열 추가(C0·C2·C3 미작성). 게스트 seed 항목은 FS-005b로 해소되어 미수행 목록에서 제거.
- 폐기 식별: 통합플랫폼_개발로드맵.md 전체, 상세개발일정 6절(D01~D70 일정표)과 9절(진행 기록). 같은 문서 1~5·7·8절은 유효하다.
- 상세개발일정 6절은 FS-009~038을 옛 범위(ERP 없음, BEMS 포함)로 배치하고 있어 현재 작업 ID 체계와 충돌한다. 실제 삭제·개정은 사용자 판단 대기.
- 일회성 스크립트 2개는 아직 저장소에 남아 있다. 삭제 명령은 사용자가 직접 실행해야 한다.
- 검증: 문서 간 정합성 정적 대조만 수행.
- 다음: 폐기 문서 처리 방침 확정 후 FS-009 착수.

## 2026-09-20 최신 설계·UI 지침 반영
- 아키텍처·DB 명세·개발 방식·업무/화면 설계를 모두 정리하고 사용자 전체 확인 후 제품 개발에 착수하도록 AGENTS/README/현황 갱신.
- 모듈별 Excel 시트 구성, EIP/모듈 업무도/ERD 제공 방식, UI 색상·아이콘·그림자 기준을 docs/design/설계완료_승인기준_및_시각화.md에 기록.
- EIP/MES/ERP/FEMS 개념 Mermaid 도식 작성. 확정 ERD나 렌더링 검증 완료 산출물은 아님.
- 이번 작업은 지침/설계 문서 갱신. 제품 코드·DB·Excel 재생성·사용자 UI 변경 없음.
- 다음: 설계 빈틈 보완. FS-009 개발 착수는 전체 설계 확인 이후.

## 2026-09-21 FS-006b 설계 보완안 작성
- 게스트 주체/요청 결과, 전역 상한, 템플릿 ID 재매핑, 게스트 회수와 회원 구세대 정리를 구분했다.
- 생산계획 라인→작업지시 연결과 배정량 검증, 단일 품목 포장·팔레트 전량 출하·지시 취소 계약을 제안했다.
- 기존 AC-63 기대 결과 정정, AC-65~80 검증 명세 추가. 모두 실제 시험 미실행.
- 상세: [FS-006b](architecture/설계보완_게스트_계획_패킹출하_FS-006b.md).
- 제약: 사용자 확인 대기인 설계안이다. 메타데이터/Excel v0.2.0과 실제 DB는 변경하지 않았다. 승인 후 FS-007b에 함께 반영한다.
- 검증: 문서 AC 번호 유일성·연속성, 요구 절 존재, 갱신 문서 링크 확인. 제품 코드/브라우저/DB/성능 시험 없음.
- 다음: 사용자 확인 후 FS-007b 모듈별 DB 명세·Excel·ERD. 전체 설계 확인 전 FS-009 착수 금지.

## 2026-09-21 FS-007b 산출물 완료
- FS-006b 계약을 메타데이터 v0.3.0에 반영: 54테이블/510컬럼/113FK/375제약·정책.
- 모듈별 Excel 31시트, 내부 링크 172개. 1,191개 행 원본 대사와 시트 상단 시각 검사.
- 오프라인 EIP/모듈 ERD HTML 및 Mermaid 원본 8개 생성. 상세는 db/FS-007b_변경_검증.md.
- 제품 코드/DB/서버 변경 없음. 실제 브라우저·DB 동시성·Excel 앱 검증 미수행.
- 다음: 사용자 확인 후 FS-008a 전체 흐름/UI 설계 개정. 전체 설계 승인 전 개발 금지.

## 2026-09-21 FS-005c FEMS 다중 에너지원 설계 제안
- 참조 명세서를 바탕으로 FEMS를 전력 전용에서 다중 에너지원(전력·가스·유량·스팀·용수) 구조로 확장하는 안을 작성했다.
- 제안 범위: core 신규 2(energy_source, meter_channel), fems 신규 4(energy_factor, tariff, energy_target, energy_baseline). 54 → 60테이블.
- 핵심 근거: 단위가 다른 에너지원은 원단위 값끼리 합산할 수 없다. 1차에너지 환산 후에만 합산·원단위·목표 비교가 성립한다. 환산계수와 배출계수는 용도가 다르므로 섞지 않는다.
- 기존 변경 제안: core.meter에서 측정종류·단위 제거, energy_reading·energy_allocation·bems.energy_reading의 참조를 채널로 전환.
- 상태: **미반영.** 메타데이터 v0.3.0은 FEMS 2테이블을 유지한다. 채택 여부 결정 대기.
- 별도 산출물: 독립 참조용 FEMS 공통 DB 설계서(ESG 방향, 24테이블/350컬럼)를 MES 기초 설계서 템플릿으로 작성해 사용자에게 전달했다. 저장소 미포함.

## 2026-09-21 문서 정리 및 기준 갱신
- 삭제 완료: 통합플랫폼_개발로드맵.md, tools/apply_fs005a.py, tools/restore_fs007_sheet_content.py.
- 갱신: 현재기획_진행현황.md 전체 재작성(v0.3.0 수치·모듈별 표·FS-006b/007b 반영·다음 작업을 FS-008a로 수정), db/README.md 재작성(31시트·모듈별 규모·ERD 안내).
- 헤더 주석 추가: 공통ERD_FS-005(36엔티티 v1 기준본임을 명시), 학습경로_FS-004(C1·C4만 덮음), FEMS_공통설계_FS-005c(제안·미반영).
- 정정: 현황 문서의 "S0 종료 → FS-009 즉시 착수"는 틀렸다. design/설계완료_승인기준이 그보다 우선하며 FS-008a → 정합화 → 전체 승인 → FS-009 순서다.
- 검증: 문서 간 정합성 정적 대조만 수행. 스키마·Excel·ERD·제품 변경 없음.
- 미처리: docs/.DS_Store, tools/.DS_Store 잔존. 상세개발일정 6·9절 개정은 미수행(현재는 폐기 표기만 되어 있다).
- 다음: FS-005c 채택 여부 결정 → FS-008a.

## 2026-09-22 독립 솔루션 전환 검토
- 사용자 최신 정의를 확인: 하나의 포털에서 MES/ERP/FEMS 각각 독립 전문 솔루션을 전시.
- references 세 Excel 읽기 전용 검토: MES 22테이블/348컬럼, FEMS 24/350, ERP 41/698(목차 기준).
- 기존 통합 메타데이터 v0.4.0(60테이블), 공유 core, ERP-1, 학습 중심 기획과 충돌 확인.
- 상세: plan/독립솔루션_전환검토_2026-09-22.md. 현황 상단에 최신 사용자 방향과 이전 항목 재검토 표기.
- Excel/DB/제품 코드 변경 없음. 실제 DB 검증 및 법규/표준 적합성 검증 미수행.
- 다음: 공통 인증/업무 독립 경계와 학습 기능의 역할 확인 후 전환 아키텍처·범위 정리. 기존 FS-008a를 그대로 진행하지 않는다.

## 2026-09-22 FS-013 독립 솔루션 전환 결정 완료
- 사용자 확정 답변 7건을 결정서로 고정: 공통 인증만 공유(D1), 단일 PostgreSQL+스키마 분리+API 1개(D2), 기존 67테이블 분해·재배치(D3), 학습은 도움말로 축소(D4), 게스트 체험 유지(D5), 흐름맵·도움말은 정적 파일(D6), ERP 회계는 A층 구현/B층 읽기전용/C층 제외(D7).
- 산출물: [독립 솔루션 전환 결정서](plan/독립솔루션_전환결정_FS-013.md).
- 재배치 매핑 확정: core 19 → 11(인증·공간·세대·운영만). 마스터 8개를 mes 5 / erp 2 / fems 8로 복제·이관.
- 폐기 12개 확정: learning 6, process_map 3, mes.learning_binding 1, bems 2. BEMS 예약 테이블은 사전 보유 이유가 없어 함께 폐기.
- 교차 FK 3건 제거 방식 결정: fems.energy_allocation.execution_id는 컬럼 삭제(equipment_id로 성립), mes.production_plan.sales_plan_id와 erp.shipment_line.packing_unit_id는 코드 문자열로 대체.
- 신설 12개 제안: erp 채권채무·수금지급 6, 매입 간이 2, 세금계산서 1, 계정과목·분개규칙 2, fems.production_record 1.
- 규모 예측: 67 → 72테이블. **줄지 않고 늘어난다.** 마스터 복제 7 + 회계 11 > 폐기 12.
- 새 경계 검사 규칙 R1~R5 명세. audit_module_boundary.py는 판정 대상이 사라져 폐기 대상으로 분류.
- AGENTS.md §3 개정: "공통 기준정보는 core가 소유" 조항을 독립 소유·교차 FK 금지·학습 축소 4개 조항으로 교체. 읽기 순서에 FS-013 추가.
- 현황 문서 전면 재작성: 제품 정의를 학습 중심 EIP에서 독립 솔루션 전시로 교체. 진행률 70% → 55%로 하향 조정(DB·화면이 뒤로 물러남). 다음 작업을 FS-008a → FS-014로 변경.
- 정정: 전환검토 문서의 "schema.json v0.4.0 / 60테이블"은 오기다. 실제는 **v0.6.0 / FS-005f / 67테이블**이며 ERD 원본 7개로 구성(core 19/mes 17/erp 14/fems 6/learning 6/process_map 3/bems 2)을 확인했다.
- 검증: schema.json 헤더와 docs/architecture/erd/*.mmd 7개의 정적 대조로 테이블·FK 목록을 집계했다. 명령 실행 수단이 없어 db:validate·db:build·build_erd는 미실행.
- 미수행: schema.json 재구성, audit_schema_isolation.py 작성, Excel·ERD 재생성, 회계 A·B층 컬럼 설계, 회계 기준·세금계산서 법정 요건 검토. **스키마·Excel·ERD·제품 코드 변경 없음.**
- 다음: 사용자 확인 후 FS-014 — schema.json v0.7.0 재구성 + 격리 검사 스크립트 + Excel·ERD 재생성.

## 2026-09-22 — FS-014 완료: 독립 스키마 재배치 / 회계는 FS-014b로 분리

- 사용자 확인: FS-014는 재배치·교차 FK 제거·폐기 12개·fems.production_record만 수행한다. 회계 A·B층 11개는 FS-014b로 분리한다. DB 미적용(migration_revision=null)이므로 중간 버전 비용보다 검증 원인 분리를 우선한다.
- 집계: **v0.7.0 / FS-014 / 61테이블 / 598컬럼 / 138 FK / 제약·정책 427개**. core 11 / mes 21 / erp 16 / fems 13. FEMS=기존 6+마스터 6+생산량 1. FS-013 예상 72와 차이 11개는 보류한 회계다. FS-014b 이후 ERP 27, 전체 72 목표를 유지한다.
- 정정: FS-013 §3.2 소계 한 줄만 5/2/8→5/2/6, 8→15 실체를 8→13으로 바꿨다. §5 총계 72는 변경하지 않았다. 이전 응답의 70은 FEMS 합산 오류였다.
- 도구: tools/apply_fs013.py 신규. v0.6.0/FS-005f·입력 구조·후보 구조 검증 후 원본 SHA256 이름의 백업과 원자적 교체. --check는 무변경 검증. 유효한 적용 상태 재실행은 파일·mtime·백업·변경이력 불변. 오류 입력·부분 적용·DB 적용 메타데이터는 중단한다.
- 백업: docs/db/schema-metadata/backups/schema.before-FS-014.835668b772bc2b5a0aa09fcb4e479fc6e44900328716111d21865b0bf5d8bfb3.json. 작업 전 문서·생성기·산출물 사본은 work/fs014/original/에 보존했다.
- 매핑: FS-013 각 행 그대로 core 마스터 8개→mes 5/erp 2/fems 6. 키·인덱스·제약·상태·코드목록을 동반 이동하고 업무 FK를 자체 스키마로 재지정했다. learning 6/process_map 3/mes.learning_binding 1/bems 2 및 부속 메타데이터 삭제.
- 컬럼·정책: execution_id 삭제, sales_plan_code/packing_no로 코드 대체. FEMS 품목 비소유에 따라 energy_baseline.item_id도 item_code로 대체했다. 실행별 배분 조건부 UK를 설비 기준 UK로 통합하고 ERP→MES 패킹 상태 검증 정책을 제거했다. 플랫폼 역할·활성 모듈·FEMS 계측 소유 목록도 현재 경계로 정리했다.
- 신설: fems.production_record 14컬럼. 범위 S, 자체 설비, 품목 코드, 생산 구간, 양품 생산량·단위, 원천 키·버전·확정 상태. 확정 후 불변, 원천 키별 최신 확정 버전만 집계하는 정책을 명시했다. 설계 근거 및 61개 엔티티 목록: docs/db/스키마_재구성_FS-014.md.
- 추가 정합성: 기존 주차·종료월·기준선 기간의 누락된 문자열 형식 CHECK 5개 보완. PRIMARY/EMISSION 구분 유지. 월·주차 실제 업무 유효성 및 정책 실행은 제품 구현 단계다.
- 격리: tools/audit_schema_isolation.py 신규(R1~R5); tools/audit_module_boundary.py 삭제. 일반 검증기도 현재 엔티티 목록·격리·달력 CHECK·폐기 컬럼 잔존 검사를 사용하도록 갱신했다.
- 산출물: schema.json / DB설계서.xlsx(19시트) / 전체+4스키마 ERD(5 Mermaid 원본 및 HTML) / validation-report 동시 갱신. 폐기 3스키마 ERD 원본 삭제. 생성기의 고정 버전·집계·옛 소유권 설명을 수정했다. 현황 문서와 문서 지도도 갱신했다.
- 실행 검증: `npm run db:validate` 오류 0; `python3 tools/audit_schema_isolation.py` R1~R5 오류 0; `python3 -m unittest discover -s tools -p test_fs014.py -v` 10개 통과; `npm run db:build`, `python3 tools/build_erd.py` 성공. 회귀 테스트는 멱등 바이트·mtime·백업, dry-run, 잘못된 입력/적용 상태 보존, R1~R5 오류 주입, FK 대상/타입/유니크키/복합 범위/RESTRICT/달력 CHECK 오류 주입, CLI 종료 코드를 포함한다.
- Excel 검증: 저장 파일 재열기로 8,921개 명세 셀 대조, 내부 링크 154개 대상·주소 확인, 19개 시트·고정 헤더·오류 셀 검사. Artifact Tool로 19개 시트 대표 구간 렌더링·육안 확인 및 신규 생산량 구간 확인. 수식 계산 모델이 아닌 정적 명세다. 미리보기 도구가 빈 공유 문자열을 숫자로 표시하는 문제를 확인하여 생성기는 빈 문자열 대신 실제 빈 셀을 기록하도록 보완했고, 저장 파일 재대조와 생산량 구간 재렌더링을 통과했다.
- ERD 검증: HTML 내 JSON과 schema.json 동일, Mermaid 엔티티·원본 개수·README 원본 해시 대조, JS 문법 검사. 설치된 Chrome의 격리된 headless 세션에서 4스키마 집계·범위 FK 토글·생산량 상세 선택·데스크톱/모바일 표시 확인, JS 오류 0. 번들 Playwright 기본 Chromium은 미설치여서 설치된 Chrome으로 검증했다.
- 보존: 사용자 UI 파일 3개 및 AGENTS.md의 작업 전후 바이트 해시 동일. 제품 코드·UI 시제품·물리 DDL·마이그레이션·seed는 변경하지 않았다. Git 커밋은 하지 않았다.
- 미실행: PostgreSQL 적용·CHECK 실행·트리거·서비스 정책·동시성·성능·권한 검증, Excel 네이티브 앱 조작, Mermaid 렌더러 파싱. 위 정적 검사·브라우저 확인을 이 검증들의 통과로 간주하지 않는다.
- 제약: 원천 키별 최신 확정 버전·구간 중복·확정 불변은 SERVICE/DB_POLICY이며 DB CHECK가 아니다. FEMS 공장 전체 분모의 대표 공정 선정은 추가 업무 규칙이 필요하다. 과거 설계 문서 전체를 개정한 작업은 아니며 충돌 시 FS-013 및 FS-014 설계가 우선한다.
- 다음: **사용자 FS-014 결과 확인을 기다린다.** FS-014b는 컬럼 설계에 앞서 ① 부분 수금·지급의 apply/잔액 ② 채권·채무 상태 전이와 확정 후 불변 ③ 세금계산서 발급확인과 매출 인식 선후 ④ 비저장 분개 미리보기 거래 유형을 정의하고 사용자 확인을 받아야 한다. FS-014b 미착수.

## 2026-09-22 FS-014 결과 검수 및 FS-013 잔여 오류 정정
- FS-014 결과를 저장소에서 직접 대조해 보고 수치가 실제와 일치함을 확인했다. schema.json v0.7.0/FS-014, validation-report 61테이블(core 11/mes 21/erp 16/fems 13)·598컬럼·138FK·errors 0.
- 독립 산정과 일치: mes 16+마스터 5=21, erp 14+2=16, fems 6+6+생산량 1=13.
- audit_schema_isolation.py 본문 검토: R1~R5 판정 로직과 범위 앵커 예외 처리가 FS-013 §6 명세와 일치. audit_module_boundary.py 삭제 확인.
- **정정 1 (FS-013 §3.2 제목).** "8 → 15"는 오기다. 소계 행만 고치도록 지시해 제목이 남아 있었다. "8 → 13"으로 교체.
- **정정 2 (FS-013 §5 본문).** "마스터 복제 7개"는 FEMS 소계 오기에서 파생한 수치다. "마스터 순증 5개(8 → 13개 실체) + 신설 12개 − 폐기 12개 = 순증 +5"로 교체. §5 표와 총계 72는 처음부터 정확했으므로 변경 없음.
- FS-013 상단에 진행 상태 주석 추가: 4장 회계 11개는 FS-014b로 분리되어 미착수이며 §5의 72는 목표치다. 현재 수치 기준은 현황 문서임을 명시.
- AGENTS §6 개정: "어시스턴트는 명령을 실행할 수 없다"는 고정 서술을 "실행 수단은 세션마다 다르다. 먼저 확인하고 불가능하면 스크립트를 안내한다"로 교체. 현황 문서의 동일 제약 항목도 맞춤.
- 검증: 문서 정적 대조와 수치 재계산만 수행했다. 실행 수단이 없는 세션이라 db:validate·audit_schema_isolation·test_fs014를 직접 돌리지 않았다. Codex의 실행 결과를 재현해 확인한 것은 아니다.
- schema.json·Excel·ERD·제품 코드 변경 없음. 문서 3건만 수정.
- 다음: FS-014b — 회계 업무 규칙 4항목 정의 후 컬럼 설계.

## 2026-09-22 — FS-014b 완료: ERP 회계 A·B층 11개 / v0.8.0

- 사용자 확정 규칙과 추가 결정에 따라 진행. 소명 한도 SERVICE 정책 승인, 잠금 7단계는 채권·채무→수금·지급→소명. 수금은 receivable.id 오름차순 다음 receipt.id 오름차순, 지급은 대응 순서. 확정은 금액 고정이며 이후 소명 추가·취소를 허용한다. 소명 취소는 cancelled_at 없이 물리 DELETE, 이력은 core.audit_event.
- 결과: **v0.8.0 / FS-014b / 72테이블 / 719컬럼 / 162 FK / 제약·정책 528개**. core 11 / mes 21 / erp 27 / fems 13. 기존 61+회계 11=72로 **FS-013 §5 예상 72와 일치**. migration_revision=null, DB·서비스 미적용.
- 신설: erp.receivable, receipt, receipt_apply, payable, payment, payment_apply, purchase_invoice, purchase_invoice_line, tax_invoice, account, posting_rule. 신설 118컬럼 및 기존 sales_record 통화·취소 시각·사유 3컬럼. 다른 스키마의 테이블·관계·제약·상태·코드목록은 기존과 동일함을 테스트로 대조했다.
- 소명: 양쪽 부모의 S·거래처·통화를 복합 FK로 일치시킨다. 합계 한도는 부모 잠금 후 새 조회로 수금/지급액과 채권/채무 원금 양쪽을 검사하는 SERVICE 정책이다. CHECK로 가장하지 않는다. 소명 UPDATE 금지, 변경은 물리 삭제+새 요청. 등록·삭제·감사·멱등 결과는 같은 트랜잭션, 실패 시 전체 롤백 계약.
- 잔액·상태: receivable/payable에 balance/status/합계 캐시 없음. 원금−SUM(소명액)으로 조회 파생. 0원 원금은 OPEN/CLOSED 조건이 겹치므로 CLOSED 우선으로 문서화했다. 수금·지급액과 소명액은 양수, 원금은 0 이상. 원천 취소 채권·채무는 유효 조회에서 제외하고 원금은 보존한다.
- 생성·취소: TX-09 매출 생성과 채권 생성은 같은 트랜잭션. 매입 확정과 채무 생성도 같은 트랜잭션. 원천당 UK, 수기 원장 생성 없음. 소명 행이 남으면 상위 거래 취소 거부. 세금계산서 pending은 매출 취소 시 같은 트랜잭션에서 삭제, issued이면 취소 금지, 없으면 소명 조건만 확인. 매입 취소는 세금계산서와 무관.
- 세금계산서: 매출 전용 sales_record FK·UK로 0..1 관계, 발급대기/발급완료 두 상태, 승인번호·발급일 수기. 선발행은 SERVICE 정책으로 차단. 금액은 매출에서 조회하며 명세·월합계·국세청 연동 없음.
- 미리보기: 고정 7계정·4거래 유형·10규칙 조합 정의. 계정·규칙 행은 seed로 만들지 않았으며 허용 코드·명칭·조합과 완비 검사 계약을 설계했다. receipt_apply/payment_apply 1행=분개 1세트, 미소명 잔여는 분개 표 밖 안내. 결과·전표·총계정원장·분개 이력·조건 분기 엔진 없음.
- 도구: tools/apply_fs014b.py 신규. 사전 검증, SHA256 원본 백업, 원자적 교체, --check, 멱등 재실행. 원본 백업: docs/db/schema-metadata/backups/schema.before-FS-014b.98d2f505f5620f025019b152b2e3c018b41e5ddbd5c0bb21cd710a6be1423b25.json. 검증기는 FS-014/014b 엔티티 목록을 구분하고 회계 구조 계약을 추가 검사한다.
- 문서·산출물: docs/db/스키마_재구성_FS-014b.md 신설. 현황·문서 지도·FS-013 진행 상태·FS-006a 잠금 7단계 및 회계 정리 순서 갱신. schema.json·DB설계서.xlsx(19시트)·전체+4스키마 ERD(5원본 및 HTML)·validation-report를 함께 갱신했다.
- 실행 검증: `python3 tools/apply_fs014b.py --check` 통과, 실제 적용 후 재실행 no-op. `npm run db:validate` 오류 0, `python3 tools/audit_schema_isolation.py` R1~R5 오류 0, `npm run db:build` 및 `python3 tools/build_erd.py` 성공.
- 회귀: `python3 -m unittest discover -s tools -p 'test_fs014*.py' -v` **22개 통과**(기존 10+회계 12). 수량·비ERP 보존, 금지 잔액/상태/취소 플래그, 격리·범위, 합계 CHECK 오분류, SERVICE 계약 누락, 원천 UK·소명 거래처 FK, 세금계산서 1:1·2상태, 고정 분개·계정, KRW·RESTRICT, dry-run·백업·바이트/mtime 멱등, 오류 원본 보존, 원자적 교체 실패 주입을 검사했다. `ABORT: injected replace failure`는 의도한 오류 주입 결과이며 전체 테스트는 통과했다.
- Excel 검증: 저장 파일 재열기로 명세 셀 **10,749개**, 내부 링크 **178개**, 19시트·고정 헤더·오류 셀 검사. Artifact Tool 오류 검색 0건, 목차·ERP 테이블/관계 및 채권·소명·세금계산서·규칙 대표 구간 8개 렌더링 확인.
- ERD 검증: HTML 내 메타데이터 동일, 전체 Mermaid 엔티티 집합·5원본·README 해시 대조. Chrome headless에서 4스키마 수량, ERP 범위 앵커 토글, receipt_apply 상세·취소 플래그 부재 확인, JavaScript 오류 0. `git diff --check` 통과.
- 보존: 사용자 UI와 AGENTS.md의 작업 전후 해시 동일. 제품 코드·화면·API·물리 DDL·마이그레이션·seed 생성기·PostgreSQL 적용 없음. Git 커밋 없음.
- 미실행: PostgreSQL CHECK·FK·트리거 실행, 실제 SERVICE 합계·불변·취소·동시성·성능·권한·멱등 API 동작, Excel 네이티브 앱, Mermaid 렌더러 파싱, 법정 세무·회계 적합성. 테스트 통과는 메타데이터/변환 검증이며 정책 실행 보장을 뜻하지 않는다.
- 제약: 소명 물리 삭제 뒤 옛 등록 요청 재실행은 UK만으로 막을 수 없다. core.request_receipt 보존기간과 재시도 허용기간을 일치시키고 만료 키를 거부하는 API 계약이 필요하다(FS-010/011). 계정 7개·규칙 10행 완비 여부와 세율·반올림은 SERVICE 구현 시 검증한다.
- 다음: **사용자 FS-014b 결과 확인을 기다린다. FS-008a 미착수.** 이후 화면 기획에 금액 확정 후 소명 추가·삭제, 소명 행별 비저장 미리보기, 분개 밖 잔여 표시를 반영한다.

## 2026-09-22 FS-008a 스토리보드 완료 (54화면)
- 산출물 4건: docs/ui/화면설계_포털_FS-008a.md(7화면), 화면설계_FEMS_FS-008a.md(14), 화면설계_ERP_FS-008a.md(18), 화면설계_MES_FS-008a.md(15).
- v0.8.0 72테이블 중 71개가 최소 한 화면에서 쓰이는 것을 확인했다. 유일한 미사용 테이블이 core.dashboard_layout이어서 삭제 후보로 올렸다.
- 확정 결정 3건: 런처 학습 요소를 "전체 업무 흐름 보기"로 교체, 설명 카드를 QMS·WMS·BEMS·**SCM 4종**으로 확장(SCM 신규), FEMS에 배출량 화면 포함.
- 포털 문서 6장에서 공통 규격 확정: 색 토큰 6개, 상태색 저채도 3종(빨강 금지), 그림자 4% 1단계, 단색 라인 아이콘 통일, 공통 컴포넌트 9종, 포털은 헤더만/솔루션은 사이드바+헤더 레이아웃.
- 포털 5장에서 플랫폼 역할 GUEST/OWNER/ADMIN 3종을 처음 정의했다. FS-013은 "core.role은 플랫폼 역할만"이라 말했을 뿐 목록이 없었다.
- 걧 20건 발견해 분류: 스키마 변경 필요 5, 확인 필요 4, SERVICE 정책 3, 화면 안내로 해소 8. MES 문서 9장에 종합했다.
- 가장 무거운 걧 3건: fems.energy_allocation.kwh가 다중 에너지원인데 전력 전용 컴럼 / erp 부가세율의 출처 부재 / erp.receivable 만기 부재로 연령분석 불가.
- 검증: 문서 작성과 스키마 정적 대조만 수행. 스키마·Excel·ERD·제품 코드 변경 없음. HTML 시제품 제작·브라우저 검증·접근성 확인 미실행.
- 다음: 걧 반영을 FS-008b로 분리해 진행.

## 2026-09-22 FS-008b 화면 걧 반영 (v0.9.0)
- 결과: **71테이블 / 712컬럼 / 161 FK / 제약·정책 528개.** core 10 / mes 21 / erp 27 / fems 13. 검증 오류 0, R1~R5 위반 0.
- 스키마 변경 4건 적용: fems.energy_allocation kwh → quantity 개명 + unit 추가 / erp.item 과세구분(TAXABLE·ZERO·EXEMPT) / erp 결제조건·채권·채무 만기 / core.dashboard_layout 삭제.
- owner_module을 meter·meter_channel·energy_reading 세 곳에서 함께 제거하고, 관측값 FK를 (S, meter_channel_id, unit) → meter_channel(S, id, unit)로 재구성해 **단위 일치 검증을 유지**했다. 채널에 (S, id, unit) 유니크가 없어 기존 (S, id, owner_module, unit) 키를 교체했다.
- 만기 정책: 결제조건·채권·채무 만기를 **nullable**로 두어 조건 미입력 거래처 때문에 매출 확정이 막히지 않게 했다. NULL 만기는 "만기 미설정" 그룹이며 연체가 아니다. 매출은 인식일+N 계산 전용, 매입은 수기 우선 → 없으면 매입일+N → 조건도 없으면 NULL. 확정 후 불변·소급 금지.
- SERVICE 정책 3건 추가: 설비 동시 점유 방지 / 패킹 수량 ≤ LOT 양품 / 게스트 만료는 세션 종료 후 회수.
- 설계 결정 4건 문서 반영: 1지시:1LOT 의도 / BOM 선택 허용 의도 / 견적 개정은 행 누적 + MAX(revision_no) 파생 판정(플래그 컬럼 금지) / workspace_module 유지.
- TX-12 정정: 기존 "만료 시 회수가 먼저면 요청 차단" 규칙이 이번 결정과 충돌해 회수 조건을 "세션 종료와 진행 요청 없음"으로 고쳤다. 삭제 절차는 유지.
- 보류: 설비 상태 컬럼(M-G06), FEMS 공장 전체 대표 공정(G-08), 0원 매출 발급 여부(E-G07), 정적 콘텐츠 경로(P-G03), SCM 카드 문안(P-G04).
- 도구: tools/apply_fs008b.py 신규. 사전 검증·SHA256 원본 백업·원자적 교체·--check·멱등 재실행. 회귀 11개 추가.
- **기록 주의:** 이 항목은 Codex 세션이 사용 한도로 중단된 뒤 다음 세션이 저장소 파일을 대조해 작성했다. 수치는 validation-report.json에서 확인했으나, **검증 명령을 재실행해 재현하지는 않았다.** Excel·ERD 브라우저 검증은 이전 세션 보고에만 의존한다.
- 미실행: PostgreSQL 적용·CHECK/FK/트리거 실행, SERVICE 정책 실행·동시성·성능·권한, Excel 네이티브 앱, Mermaid 렌더러 파싱, 법정 세무·회계 적합성.
- 다음: FS-010 API 계약서. 솔루션별 네임스페이스·권한·멱등키·세션 종료 판정·request_receipt 보존기간 계약을 다룬다.

## 2026-09-23 FS-010 API 계약서 작성
- 산출물: docs/architecture/API계약서_FS-010.md. 54화면이 호출하는 HTTP 계약과 공통 규약.
- 네임스페이스 4개로 분리: /api/v1/core·mes·erp·fems. 업무 네임스페이스끼리 호출하지 않으며 솔루션 간 조인 엔드포인트를 두지 않는다.
- **범위 키 S를 클라이언트가 보내지 않는다.** 서버가 세션에서 파생한다. workspace_id를 받으면 71테이블 전체에 소유권 검사를 빠짐없이 넣어야 하고 한 곳만 누락도 타인 데이터가 새는 구조가 된다.
- 권한 2계층: 플랫폼 역할(GUEST/OWNER/ADMIN)은 core 접근만, 업무 권한은 각 솔루션 자체 보유. 1차는 "공간 소유자면 전부 허용"이되 계층은 분리해 둔다.
- 오류 코드 11종 정의. REFERENCED_BY_OTHERS는 details.references에 참조처별 건수를 필수로 실어 FS-008a의 화면 요구를 받친다.
- 멱등키: 상태 변경 POST 전부에 Idempotency-Key 요구. core.request_receipt 구조를 그대로 쓴다. **보존기간과 재시도 허용기간을 24시간으로 일치**시켜 FS-014b가 남긴 제약(소명 물리 삭제 후 옛 요청 재실행)을 닫았다. 만료 키는 422 거부.
- 직렬화 규칙: 연·월·주차는 문자열, 금액·수량도 **문자열**(JSON number 부동소수점 오차 회피), 시각은 ISO 8601 UTC.
- 세션 종료 판정을 정의하면서 **걧 발견**: core.auth_session에 last_seen_at이 없어 유휴 판정을 구현할 수 없다. A/B/C 안을 제시하고 **B안(expires_at을 유휴 만료로 겸용·요청마다 연장)을 제안**했다. 채택 시 스키마 변경 없이 해소된다.
- 게스트 생성은 **동기 처리**로 둔다. 비동기 큐는 폴링 엔드포인트·작업 상태 테이블·재시도가 따라오므로 실측 전에는 근거 없는 복잡도다.
- 페이지네이션은 offset. 최대 데이터가 fems.energy_reading 약 6,480행이라 cursor는 과설계다.
- SERVICE 정책 7건을 엔드포인트·응답 코드와 대응시켰다(10장). 전부 트랜잭션 안에서 부모 잠금 후 재계산 검사이며 잠금 순서는 FS-006a 8단계를 따른다.
- 결정 대기 5건(12장): A-1 세션 생존 판정 / A-2 멱등키 24시간 / A-3 게스트 동기 / A-4 offset / A-5 금액 문자열. **A-1만 스키마와 관련이 있고 B안이면 변경 없이 닫힌다.**
- 미결정 6건(11장): 필드 단위 스키마, 실시간 갱신, 파일 업로드, 레이트 리밋 수치, OpenAPI 생성, 캐시 헤더.
- 검증: 문서 작성과 스키마·화면 설계 정적 대조만 수행. 스키마·Excel·ERD·제품 코드 변경 없음. 서버·엔드포인트 구현·보안 위협 모델링·성능 측정 미실행.
- 다음: A-1 결정 후 FS-011 개발 규약. **Node·Python·PostgreSQL 버전 결정이 선행되어야 한다.**

## 2026-09-23 FS-011 개발 규약 작성 · 런타임 버전 확정
- 산출물: docs/architecture/개발규약_FS-011.md.
- FS-010 A-1을 **B안**으로 확정(사용자 승인): auth_session.expires_at을 유휴 만료로 겸용하고 요청마다 연장한다. last_seen_at 컬럼을 추가하지 않으므로 **스키마 변경 없이 닫혔다.** expires_at이 두 의미를 겸한다는 사실은 문서에 명시.
- **런타임 버전 확정(공식 릴리스 일정 검색으로 확인):** Python 3.14 / PostgreSQL 18 / Node.js 24 LTS.
- 배제 사유: Python 3.15는 2026-10-01 출시 예정으로 휴 미비 위험, PostgreSQL 19는 베타 3 단계, Node 26은 2026-10-28에야 Active LTS가 된다. Node 24는 2026-10-20 Maintenance 진입이나 EOL이 2028-04라 프로젝트 기간에는 문제가 없다.
- 고정 방식: .python-version / .nvmrc / docker 이미지 태그. **메이저만 고정하고 패치는 락파일과 보안 패치에 맡긴다.**
- 기존 제약 해소: "Python 3.9에서 build_erd.py 실패"는 3.14 고정으로 사라진다.
- 스택: FastAPI·SQLAlchemy·Alembic / React·TypeScript·Vite / Docker Compose. **Node는 프론트 빌드와 문서 생성기 전용**이며 백엔드 런타임이 아니다. 라이브러리 버전은 문서에 적지 않고 락파일에 맡긴다.
- 저장소 구조: 단일 저장소. backend/src/fs/{common,core,mes,erp,fems}. **erp가 mes를 import 하지 않는다** — 스키마 간 FK 0건(R1)의 코드 계층 대응물. 의존 방향은 업무 → common/core 한 방향.
- 계층 규칙: **트랜잭션 경계는 service에만 있다.** router·repository가 커밋하면 FS-006a 잠금 순서를 보장할 수 없다.
- **P-G03 해소:** 정적 콘텐츠를 content/ 아래 flow-map.json · cards/*.md · help/<솔루션>/<화면ID>.md로 확정. API가 아니라 프론트 번들에 포함한다. DB에 넣지 않아 세대 복사가 무거워지지 않는다.
- 네이밍: DB snake_case / JSON camelCase이며 변환은 Pydantic alias generator 한 곳에서만. 컴포넌트 상단 주석에 화면 ID를 남겨 설계 문서와 코드를 잇는다.
- 마이그레이션: Alembic. **첫 마이그레이션을 손으로 쓰고 schema.json과 대조 검사**하는 B안 채택(71테이블 DDL 생성기를 만드는 비용이 더 크다). tools/verify_ddl_matches_schema.py를 FS-009에서 함께 만든다. schema.json의 migration_revision에 리비전 ID를 기록.
- 테스트: FS-010 10장 SERVICE 정책 7건을 전부 통합 테스트로 검증한다. **가장 중요한 것은 범위 격리** — 다른 공간의 자원 ID로 요청하면 404가 나와야 한다. 소명 한도·설비 점유는 동시 요청 주입이 아니면 의미가 없다.
- Git: 현재 커밋 1개(6cb3e80) 이후 작업이 미커밋이다. **FS-009 착수 전에 현재 상태를 커밋해야 한다.**
- 남은 결정 2건: V-1 저장소 공개 여부·시점(docs/references/가 공개 대상이 아니므로 이력이 쌓이기 전인 지금이 가장 쉬운 시점), V-2 배포 대상.
- 검증: 문서 작성과 공식 릴리스 일정 확인만 수행. **실제 런타임 설치·의존성 호환 시험 미실행.** 코드·스캐폴딩·스키마·Excel·ERD 변경 없음.
- 다음: V-1·V-2 결정 후 FS-012 Codex 인계 패키지. FS-005g 시드 정의 갱신은 구현 착수 전에 끝내야 한다.

## 2026-09-23 FS-012 구현 인계 패키지 작성 · 설계 단계 종료
- 산출물: docs/plan/구현인계패키지_FS-012.md.
- **V-2 확정(사용자):** Vultr VM + Nginx + DNS. 기존 보유 서버를 쓰며 도메인은 별도 구매 예정.
- V-1(저장소 공개 여부)은 선택지 4안을 제시하고 미결정으로 남겨두었다. **공개 여부와 무관하게 docs/references/ 제거는 지금이 가장 쉬운 시점**임을 명시했다(커밋 1개).
- 작업 분해 10개 확정: FS-005g 시드정의 → FS-009 실행기반 → FS-015 시드생성기 → FS-016 공통계층 → FS-017 포털 → FS-018 FEMS → FS-019 ERP → FS-020 MES → FS-021 통합검증 → FS-022 배포. 각각 완료 조건을 명시.
- 순서 근거: 포털을 먼저 만들어 공통 컴포넌트 9종과 디자인 토큰을 실물로 확정하고, 그다음 가장 작은 FEMS(13테이블)로 화면·API 패턴을 싼게 검증한다. ERP·MES는 서로 import하지 않아 병렬 가능하나 1인 운영이면 순차가 안전하다.
- 금지 목록 명문화: 쟔액·상태·최신여부 플래그·분개 결과·배출량·요금·환산 결과는 저장하지 않는다. **성능을 이유로 캐시 컬럼을 추가하지 않고 실측 후 병목이 증명되면 다시 판단한다.**
- 보류 걧 4건(M-G06 설비 상태, G-08 대표 공정, E-G07 0원 매출 발급, P-G04 SCM 카드 문안)은 구현 중 마주치면 임의로 정하지 말고 질문하도록 명시.
- 검증 계획: SERVICE 정책 7건을 통합 테스트로 검증하며 **범위 격리(타인 공간 자원 ID → 404)가 최우선**이다. 설비 점유·소명 한도는 동시 요청 주입이 없으면 통과해도 의미가 없다.
- 실측 미수행 항목 명시: 게스트 복사 2초·첫 화면 3초·동시 게스트 20명은 전부 목표값이며 측정한 적이 없다. **FS-015에서 복사 시간을 먼저 재고 못 맞추면 그때 대책을 논의**한다. 미리 비동기 큐를 만들지 않는다.
- 배포 준비: 게스트 전역 상한·회수 배치·레이트 리밋·HTTPS 필수. **백업은 하지 않는다**(합성 데이터라 시드로 재생성 가능).
- 현황 문서 갱신: 남은 작업표를 구현 10단계로 교체하고 착수 전 남은 결정 5항목 표를 추가했다.
- 검증: 문서 작성과 기존 설계·화면·API 문서 정적 대조만 수행. 코드·스캐폴딩·스키마·Excel·ERD 변경 없음.
- 다음: **사용자 전체 설계 승인.** 승인 후 V-1 결정 → 현재 상태 커밋 → FS-005g → FS-009 착수.

## 2026-09-23 V-1 결정 — 저장소 공개 준비
- **V-1 확정(사용자): ① 지금 정리 후 공개.** 커밋이 1개뿐인 지금이 이력 정리 비용이 가장 싸다.
- `.gitignore` 개정: `docs/references/*.xlsx` → **`docs/references/` 폴더 전체**. 기존 규칙은 Excel 3개만 막아 README와 manufacturing-systems.html이 추적될 수 있었다. `.idea/`·`.vscode/`도 추가.
- 참고 자료는 삭제가 아니라 **저장소 밖 이동**이다. 설계 입력으로 이미 흡수됐으므로 저장소에 남길 이유가 없다.
- 문서 갱신: FS-012 2장 체크리스트 3번 ✅ 처리 및 V-1 처리 내역표 추가, 현황 착수전 결정표·폐기보류 목록 갱신.
- **이력 재작성이 필요한지는 미확인이다.** 명령 실행 수단이 없어 `git ls-files docs/references/`와 `git log --all -- docs/references/`를 돌려보지 못했다. 커밋 `6cb3e80`에 포함됐다면 filter-repo가 필요하며, 사용자 확인 후 판단한다.
- 사용자 실행 순서 안내: ① 추적 여부 확인 → ② references 저장소 밖 이동 → ③ 상태 확인 → ④ 커밋.
- 검증: `.gitignore` 수정과 문서 갱신만 수행. **Git 명령을 실행하지 않았으며 파일을 이동하지도 않았다.** 스키마·코드 변경 없음.
- 다음: 사용자가 이동·커밋 완료 후 전체 설계 승인 → FS-005g → FS-009.

## 2026-09-23 V-1 이행 완료 — 이력 재작성
- `docs/references/` 5개 파일(Excel 3·README·HTML)을 `~/projects/factory-studio-references/`로 이동하고 폴더를 삭제했다.
- **정정: 커밋은 1개가 아니라 3개였다**(68883a8, 6cb3e80, 316d19d). 현황 문서의 "커밋 1개(6cb3e80)" 기술이 틀렸고 그것을 검증 없이 여러 문서와 프롬프트에 반복 인용했다.
- `git log --all -- docs/references/` 결과 **과거 커밋 3개 전부에 포함된 것을 확인**했다. 기존 .gitignore가 `docs/references/*.xlsx`만 막아 README와 manufacturing-systems.html이 추적되고 있었다.
- 조치: `git checkout --orphan`으로 새 뿌리 커밋을 만들고 구 브랜치 삭제 후 reflog 만료·gc 가지치기. **filter-repo 설치 없이 git 기본 명령만 사용.**
- 결과: 단일 커밋 `b19376f`. `git log --all -- docs/references/` 빈 출력 확인. 원격 push 전이어서 협업 충돌은 없었다.
- 트레이드오프: 커밋 3개를 1개로 합쳤다. 잃은 이력은 "설계 산출물 초기 커밋"·"문서 재편" 수준이며 설계 변천사는 이 progress.md에 남아 있다.
- `.gitignore` 개정: `docs/references/` 폴더 전체, `.idea/`, `.vscode/` 추가.
- 검증: 명령은 사용자가 실행했고 출력을 대조해 확인했다. Claude가 git 명령을 직접 실행하지는 않았다.
- 다음: FS-005g 시드 정의 갱신(설계) → FS-009 실행 기반 구축(구현).


## 2026-09-23 FS-008b 최종 검증 완료 — 중단 작업 재개

- 이전 FS-008b 항목의 “다음 세션은 검증 명령 미재실행” 기록을 보완한다. 원 작업 세션 재개 후 현재 저장소에서 회귀 33개(FS-008b 11 + FS-014/014b 22), R1~R5 검사, npm run db:validate를 실제 재실행했고 모두 통과했다.
- 최종 **v0.9.0 / 71테이블 / 712컬럼 / 161 FK / 제약·정책 528개**. core 10 / mes 21 / erp 27 / fems 13. 목표 71과 일치. FS-013 당시 72와 차이는 dashboard_layout 삭제 1개다.
- FEMS owner_module 3개 삭제, 배분 unit 1개 추가로 컬럼 **149→147(순감 2)**. 기존 owner 포함 채널 UK를 (S,id,unit)으로 교체했고 관측·배분의 단위 포함 FK를 검증했다.
- 활성 메타데이터 kwh 참조 **2곳 발견·2곳 수정**(컬럼, CHECK). kwh 참조 UK·인덱스·FK·정책은 0건. 과거 배분 UK 스크립트 조사 완료.
- nullable 결제조건·채권/채무 만기 유지. 매입 수기 우선→매입일+N→NULL, 확정 시 채무 복사. 매출은 계산 전용. NULL 만기는 만기 미설정, 연체 아님. 확정 후 불변·소급 없음.
- npm run db:build 및 python3 tools/build_erd.py는 이번 FS-008b 작업 중 실제 실행했다. Excel 19시트 **10,686셀·177링크** 원본 대사, Artifact 오류 검색 0건·변경 범위 7개 시각 검토. HTML ERD의 모듈 수·앵커 토글·상세 필드 동작을 Chrome headless로 검증(JS 오류 0).
- --check 및 실제 파일 멱등 재실행 bytes/mtime 동일. SHA256 백업 일치. 보호 UI·시제품 3파일 해시 동일, FS-008a 네 문서의 갭 목록 밖 본문 동일.
- 최종 스키마 SHA256: 213415b5f1e6b44feaceaffc9366bbe449d33d0f484c1e1d9ea8992637831110. 설계 근거와 현재기획_진행현황을 함께 갱신했다.
- 미실행: 물리 DDL·PostgreSQL·마이그레이션·seed·SERVICE 정책 실행·동시성·성능·권한·법정 세무 적합성·Excel 네이티브 앱·Mermaid 렌더러 파싱.
- 다른 작업에서 추가된 FS-010~012·V-1 기록과 Git 이력은 보존했다. 이번 작업은 FS-008b 결과 보고로 종료하며 다른 작업 ID는 시작하지 않는다.

## 2026-09-23 FS-005g 시드 정의 개정 작성
- 산출물: docs/architecture/합성데이터_시드정의_FS-005g.md. FS-005b는 상단에 "대체됨" 표기 후 이력으로 보존.
- 착수 전 추산 보고: 3스키마 분리 자체의 증가는 마스터 중복 수십 행에 그친다. 변수는 FS-005b가 세지 않은 FEMS 배분·생산량의 해상도였다(1시간이면 약 20,000행).
- 사용자 결정: 배분·생산량 1일 단위 / 가스·용수 1일 검침 / FEMS 생산량·가동 부하는 MES 실행 구간에서 파생(3-b) / 결측은 quality 행으로 저장 / 계정 7·규칙 10을 세대별 시드에 포함.
- 결과: **7,469행**(core 생성 6 · mes 375 · erp 168 · fems 6,920). 복사 대상 7,463. FS-005b 6,840 대비 +629(+9.2%). energy_reading 6,540행이 87.6%.
- 정정: FS-005c §6의 "6,840→6,540 감소"와 현황의 "약 6,500행"은 계측 전용 수치를 전체 총계와 비교한 오류였다.
- 설계: 코드 사전 단일 원천(품목·설비·사업장·공간·판매계획 코드·패킹 번호), MES 실행 26 LOT의 설비 일정표(사출 3일·조립 2일·검사 1일, 하루 경계 정렬, C-1 겹침 없음 수기 대조), 전력 가동/대기 부하 산식, 배분 DIRECT_METER 240·RUNTIME_SHARE(용수→사출기) 36, 생산량 27, 회계 A층 금액표·연령분석 구간, 오류 시나리오 28종, 도움말 시나리오 시작점.
- 새 규칙: 복사는 일수 이동이므로 요일 의존 값·날짜 포함 코드 금지, 달력 파생 컬럼 9종과 계획 코드는 T에서 재계산(주차는 월 1~21일의 월요일 3개).
- 변경: 미게시 경로를 반제품 SF-H100 단독 경로로 옮겨 고아 품목을 해소. 생산량 0 시나리오는 전량 불량 LOT 검사 구간 1건으로, 비가동일 "기록 없음"과 구별. FG-T300을 영세 품목으로 두어 세액 0 시연.
- 결정 대기: D-1 용수(UTILITY) 환산·배출 제외 서비스 규칙 / D-2 품목 원단위 분모(제안: 전 공정 에너지 ÷ 최종 공정 양품).
- 확인 대기: S-1~S-7 schema.json 코드값·nullable. 세션 읽기 도구가 파일 앞·뒤만 읽을 수 있어 387KB 중간의 컬럼 규칙·CHECK를 확인하지 못했다. 사용자 실행용 읽기 전용 명령을 안내했다. **S-1(energy_reading.value NOT NULL이거나 결측 코드 없음)이면 스키마 변경이 필요하다.**
- 계수·요금은 전부 합성 예시값이며 공표값이 아니다. source_note에 명시.
- 갱신: 현황 문서(4·6·7·9장), FS-012 1·2장, FS-005b 머리말.
- 검증: 문서 안 수량 합계·설비 일정 겹침·매출 세액·소명 한도를 손으로 대조했다. 생성기·DB·복사 시간 측정은 미실행. 스키마·Excel·ERD 변경 없음.
- 다음: D-1·D-2 결정과 S-1~S-7 확인 결과를 반영해 FS-005g 확정 → 전체 설계 승인 → FS-009.

## 2026-09-23 FS-005g — S-1~S-7 확인 반영 · 스키마 결함 2건 발견
- 사용자가 읽기 전용 점검 명령을 실행해 `fs005g_check.txt`를 생성했고, 13개 테이블의 컬럼·CHECK·UK·SERVICE 정책을 대조했다.
- **S-1 가정이 틀렸다.** `fems.energy_reading.value`는 NOT NULL이고 `value >= 0` CHECK가 있으며 `quality`는 valid/estimated/reset/invalid 4종이다. 결측 전용 코드가 없다. → 결측 6행을 `value=0` + `quality='invalid'`로 표현하고 **집계에서 invalid 행을 제외**하는 규칙을 함께 넣었다. 스키마 변경 없음. 한계(측정 없음과 신뢰 불가가 같은 코드)는 D-3으로 기록만 했다.
- **S-6에서 새 요구를 발견했다.** `mes.operation_result`에 `defect_qty = 0 OR defect_reason 존재` CHECK가 있어 62개 실적의 거의 전부에 불량 사유가 필요하다. 공정별 고정 사유 4종(SHORT_SHOT·PIN_MISALIGN·CONTACT_FAIL·W06의 MOLD_DAMAGE)을 4.5에 추가했다.
- S-2·S-3·S-4·S-5·S-7은 가정과 일치했다. 표기를 실제 코드값으로 교체했다(item_type finished/semi_finished/raw, partner_kind CUSTOMER/SUPPLIER, location.kind workcenter/zone, meter.scope_kind factory/site_total).
- 배분 품질에 "부분 집계" 코드가 없어 ASM-02 결측일 배분을 `estimated`로 둔다. 보간을 하지 않으므로 정확한 표현은 아니며, `invalid`로 두면 실제 포착된 18시간치까지 분석에서 사라진다. 선택 이유를 문서에 남겼다.
- **스키마 결함 2건 발견(FS-005g 10.3).** D-A: `fems.meter`에 `measurement_kind`·`unit`을 참조하는 CHECK가 남아 있으나 두 컬럼은 FS-005c에서 `meter_channel`로 옮겨졌다. 값도 현재 코드 목록과 다르다. **그대로면 FS-009 첫 마이그레이션 DDL이 실패한다.** D-B: 같은 테이블에 scope_kind CHECK가 2개이며 교집합이라 'common'은 쓸 수 없다(BEMS 폐기 잔재).
- 둘 다 이번 작업에서 고치지 않았다. 시드가 아니라 메타데이터 문제이고, AGENTS §4에 따라 Excel·ERD 재생성을 같은 작업에서 해야 하므로 별도 ID(FS-008c 가칭)로 제안했다.
- D-1·D-2는 사용자 진행 지시에 따라 제안대로 반영했다. UTILITY 에너지원은 환산·배출 대상에서 제외하고 "대상 아님"으로 표시 / ITEM 기준선 분모는 전 공정 에너지 ÷ 최종 공정 양품. 이견 시 되돌린다고 문서에 명시했다.
- 행 수는 7,469로 변함없다. 결측을 행으로 남기는 결정이 유지되었기 때문이다.
- 2차 확인 8건(S-8~S-15)을 새로 정의했다. 1차 점검이 13개 테이블만 대상이어서 채널·에너지원·생산량·목표·MES 상태·패킹·ERP 상태 CHECK가 미확인이다.
- 갱신: FS-005g 본문(0·2·3·4·5·7·10·12장), 현황 문서(4·6·7장).
- 검증: 점검 출력과 문서 가정을 항목별로 대조했다. 명령은 사용자가 실행했고 Claude는 출력 파일을 읽었다. 스키마·Excel·ERD·생성기 변경 없음. DB 실행 없음.
- 다음: S-8~S-15 2차 확인 → FS-005g 확정. 병행해서 D-A 수정 작업을 언제 할지 결정해야 한다(FS-009 선행 필수).


## 2026-09-23 FS-008c 완료 — fems.meter CHECK 잔재 D-A·D-B 해소

- 근거: FS-005g 10.3 및 사용자 지시. D-A 삭제 컬럼 measurement_kind/unit 참조 CHECK 삭제, D-B 넓은 scope_kind CHECK 삭제. 기존 factory/site_total CHECK 1개 유지. 채널·테이블·컬럼·FK·상태·정책·코드 목록은 변경하지 않았다.
- 결과: **v0.9.1 / FS-008c / 71테이블 / 712컬럼 / 161 FK / 제약·정책 526개**. 예상 528→526 일치. core 10 / mes 21 / erp 27 / fems 13.
- 도구: apply_fs008c.py 신규. 사전/후보 검증·SHA256 원본 백업·동일 디렉터리 임시 파일 fsync·원자 교체·--check·멱등. test_fs008c.py 11개 신규.
- validate_db_design.py는 FS-008c/v0.9.1의 기존 목록·회계·화면 검사 연결 4개 분기만 확장했다. **일반 expression 파싱은 추가하지 않았고 1-C는 정의·승인 부재로 미적용**이다. 격리 검사기·FS-008b 변환기 변경 없음.
- 채널 확인: measurement_kind IN ('CUMULATIVE','INSTANT'), multiplier > 0 CHECK만 존재. 단위 값·측정 종류/단위 조합 CHECK 없음. 제약은 추가하지 않았으며 설계 세션 질문으로 남겼다.
- 지정 명령 모두 실제 실행/exit 0: apply_fs008c --check → apply → 재실행 no-op → npm run db:validate → audit_schema_isolation → unittest test_fs0*.py -v → npm run db:build → build_erd.py.
- 검증: **44개 테스트 통과**, R1~R5 오류 0, db:validate errors=[]. 실패 주입 ABORT 로그 3건은 원본 보존 테스트의 정상 출력이다.
- 산출물: schema·Excel 19시트·ERD HTML/Mermaid 5개/README·validation-report·FS-008c 설계 근거를 갱신했다. Excel 10,681셀·177링크 대사, Artifact 오류 검색 0건 및 변경 범위 렌더 확인. HTML ERD 버전·수량·meter 상세 확인, JS 오류 0.
- 원본 SHA256: 213415b5f1e6b44feaceaffc9366bbe449d33d0f484c1e1d9ea8992637831110. 동일 바이트 백업은 docs/db/schema-metadata/backups/schema.before-FS-008c.<SHA256>.json.
- 결과 SHA256: **7e97937e7bd0df6fdae97b309444dbfdac584dd2efae71ad4f0bad7eed2d5e44**. 실제 파일 재실행 bytes/mtime 동일 확인.
- 현황 D-A·D-B 해소·2-1 완료·검증 결과를 함께 반영했다. FS-005g·UI/시제품·기존 도구 등 보호 파일 13개 해시 동일.
- 실제 명령 환경 Python 3.9.6 / Node v26.7.0. 목표 Python 3.14/PostgreSQL 18/Node 24 검증은 아님. MCP filesystem 미제공으로 허용된 로컬 명령 사용.
- 미실행: DDL·DB·마이그레이션·seed·서비스·동시성·성능·네이티브 Excel·Mermaid 렌더러 파싱. Git 커밋 없음.
- 다음: **FS-008c 결과 보고 후 사용자 확인을 받고 FS-005g-확인(S-8~S-15)을 시작한다.** 작업 2 덤프·판정·실현 가능성 조사는 미착수. FS-005g 본문은 수정하지 않았다.


## 2026-09-23 FS-005g-확인 완료 — S-8~S-15 2차 스키마 대조

- 사용자 FS-008c 확인·진행 지시 후 작업 2만 수행했다. 기준은 v0.9.1 / FS-008c / SHA256 7e97937e7bd0df6fdae97b309444dbfdac584dd2efae71ad4f0bad7eed2d5e44.
- 저장소 루트에 fs005g_check2_core.txt / _mes.txt / _erp.txt / _fems.txt 생성. 테이블명·컬럼 name/type/nullable/rule·CHECK/UK/UK_PARTIAL/SERVICE/DB_POLICY 전체 columns/expression/reason과 원본 배열 인덱스를 포함한다. Git 커밋·스테이징 없음.
- 덤프를 재파싱해 **71테이블·712컬럼·요청한 종류의 제약/정책 415개** 원본 전수 대사. core 49 / mes 123 / erp 163 / fems 80. 전체 526 중 PK/일반 INDEX는 요청 대상이 아니므로 제외했다.
- 보고서: docs/db/시드_2차스키마확인_FS-005g.md. S-8~S-15 판정 및 지정 5개 시드 사례, 나머지 4~6장 관련 CHECK를 정적으로 대조했다.
- 가정 차이: energy_target EQUIPMENT는 equipment_id NOT NULL만 요구하고 site_id NULL은 강제하지 않는다. 기준선 ITEM/EQUIPMENT는 상호 배타 조합이다. 패킹 부모/구성/입고 타입 제한은 CHECK가 아니라 SERVICE 정책이다. 견적 6상태·수주 상태는 states에 있으나 해당 status CHECK는 없다.
- 채널의 측정 종류 CHECK는 CUMULATIVE/INSTANT, 단위 CHECK 없음. source_code/measure_unit CHECK 없음. 생산량의 양의 구간·비음수 수량·버전별 UK 확인. 회계 확정시각·세금계산서 필수값 CHECK 확인; 매입 cancelled 분기는 confirmed_at을 검사하지 않는다.
- **문서에 명시된 값에서 확정적인 CHECK 위반은 발견하지 못했다. 전체 시드 통과 판정은 아니다.** X01 취소 사유, 완료 지시/LOT 사유·시각, production_record 27행 confirmed_at 등 미지정 값 때문에 실제 충족 여부는 미확정이다. NULL로 기록할 때 어느 행이 어느 CHECK에 실패하는지 보고서에 명시했다.
- W04 검사 v1/v2와 Q-0002 r1/r2는 버전 포함 UK와 양립한다. PI-0006 취소 d−29·사유 수량 오입력과 원금 979,000 보존은 해당 CHECK와 충돌하지 않는다. 입고 status 기본값 confirmed 및 견적 할인율 기본값 0도 별도로 원문 확인했다.
- 설계 판단은 보고서 질문으로 남겼고 스키마 변경 방안은 제안하지 않았다. FS-005g 본문·스키마·UI/시제품 해시 보존 확인. 현황과 이 기록만 조사 완료로 갱신했다.
- 미실행: 실제 시드 7,469행 생성·INSERT·PostgreSQL CHECK/FK/UK 실행·서비스 정책·동시성·복사 성능. 읽기 전용 조사이므로 apply/Excel/ERD 재생성은 이번 작업에서 실행하지 않았다. 1-C 미적용 유지.
- 다음: 사용자 결과 확인 및 Claude 설계 세션의 미정 값 검토·FS-005g 본문 반영. 다른 작업 ID는 시작하지 않는다.


## 2026-09-23 FS-005g 미정 값 확정 — 시드 정의 확정

- Claude 설계 세션. Codex 보고(FS-008c·FS-005g-확인)를 저장소 파일과 대조한 뒤, 보고서 6장의 미정 값 4묶음을 제안했고 사용자 진행 지시로 확정했다.
- 반영: 4.2.1 지시·LOT 사유·시각(X01 `계획 변경으로 발행 전 취소`, W06 `all_defective`), 5.5 목표 `site_id` NULL 통일·기준선 코드 `BL-*-01`/`BL-T300-02`, 5.6 production_record `confirmed_at`, 6.1 견적 날짜·수량·할인율, 6.2 미출하 납기 +14일, 6.3 수금·소명·세금계산서, 6.4 매입·지급.
- **제안과 달라진 값 1건.** 세금계산서 승인번호를 `20260000-...` 형식 대신 `SYNTH-TI-0001`·`SYNTH-TI-0003`으로 바꿨다. 연도 접두는 1.1 "코드에 날짜 포함 금지"에 걸리고 T 이동 후 `issued_on`과 어긋난다.
- **보고서가 다루지 않은 값 추가.** 덤프 재확인 중 발견: 매입 PI-0001~0004의 `confirmed_at`(C428 필수), `receipt_apply`·`payment_apply`의 `apply_key`·`applied_at`(NOT NULL·UK). 각각 전표일 10:00, `SEED:RA-000n`/`SEED:PA-000n`, 부모 확정시각으로 지정했다. PI-0006은 확정 d−30 10:00 보존·취소 d−29 10:00.
- 9.3에 V12 추가: DB CHECK가 강제하지 않는 시드 규칙(목표 site_id NULL, 기준선 코드 상이, PI-0006 취소>확정, 상태가 states 목록 내, 코드에 날짜 없음).
- 10.3 D-A·D-B를 FS-008c 해소로 표시, 10.4 S-8~S-15를 완료·반영 위치 표로 교체, 10.5 남은 한계 신설.
- 현황: FS-005g·2-2 완료, 6장 시드 제약 재작성, Codex 런타임 차이(3.9.6/26.7.0 vs 3.14/24 LTS)와 build_erd.py 3.9 통과 정정을 제약에 추가.
- 검증: 덤프(`fs005g_check2_erp.txt`)의 purchase_invoice·receipt·payment·*_apply·tax_invoice 제약 원문과 값을 대조했다. 행 수 7,469 변동 없음. 스키마·Excel·ERD·도구 변경 없음. 명령 실행 없음.
- 미확인: ERP 나머지 테이블(견적 이력·출하·매출)의 NOT NULL 시각 컬럼은 이번에 전수 대조하지 않았다. 생성기 일반 규칙과 FS-015 실제 INSERT로 확인한다.
- 다음: **사용자 전체 설계 승인.** 승인 후 Git 이력 재작성(V-1) → FS-009.


## 2026-09-23 전체 설계 승인 — 구현 단계 전환

- 사용자가 전체 설계를 승인했다. 설계 단계(S0) 종료.
- 다음 작업은 Codex에 인계: ① V-1 Git 이력 재작성(원격 push는 사용자 확인 후) ② FS-009 실행 기반 구축. 작업 ID별로 보고 후 사용자 확인.
- 이 기록 외 파일 변경 없음.

## 2026-09-23 V-1 Git 공개용 이력 재작성

- 사용자 전체 설계 승인 및 계속 진행 지시에 따라 `git checkout --orphan`으로 최신 설계를 단일 루트 커밋에 담았다. 착수 당시 실제 이력도 `b19376f` 단일 커밋이며 references 경로는 이미 없었다. 문서의 과거 3커밋 설명과 차이를 확인했다.
- 외부 백업: `/Users/hwang-kyoungho/projects/factory-studio-backups/V-1-20260923-101356/`. 전체 repository 복사(ignored/untracked 및 .git 포함), history.bundle, manifest.json. 2,540개 파일·심볼릭 링크 대조 일치. `git bundle create --all`, `git bundle verify` exit 0.
- 검증: `git log --all -- docs/references` 결과 0건, `git rev-list --all`의 각 커밋을 `git ls-tree -r --name-only`로 검사해 references 경로·덤프 파일 0건. `.gitignore`의 `docs/references/`, `fs005g_check*.txt` 등록 확인. 각 Git 명령 exit 0.
- 실행 환경: Python 3.9.6, Node v26.7.0, psql (PostgreSQL) 16.15 클라이언트. PostgreSQL 서버 접속·버전 검증 미실행. 목표 런타임 고정은 FS-009에서 수행한다.
- schema.json SHA256 `7e97937e7bd0df6fdae97b309444dbfdac584dd2efae71ad4f0bad7eed2d5e44` 유지. UI·prototypes 파일 내용 보존. DB validate/build·회귀·DB 적용 검증은 이번 Git 작업에서 미실행.
- 원격 생성·push·force push 미실행. 다음: V-1 결과 사용자 확인 후 FS-009. 원격 등록·push 역시 별도 사용자 확인 전 실행하지 않는다.

## 2026-09-23 FS-009 실행 기반 완료

- 사용자 diff 확인 후 `fs-009-runtime-base`의 `895caa453acf1028b92dcd0e97cb94e34cb02a3c`를 main에 fast-forward 병합했다. `content/help/{portal,fems,erp,mes}/`와 AGENTS.md 8장 역할 분담 존재를 확인했다. 원격 push는 실행하지 않았다.
- 사용자 V-1 결과 확인 후 작업 브랜치 fs-009-runtime-base에서 수행. V-1 보고서를 docs/agent/V-1_결과보고.md에 보존하고 AGENTS.md에 Codex/antigravity 역할·별도 브랜치 리뷰·mirror push 금지를 반영했다.
- 가장 먼저 .python-version=3.14, .nvmrc=24, package engines, backend requires-python, postgres:18 Compose를 고정했다. Python 3.14.7·Node 24.21.0 설치. Docker/Compose/Colima가 없어 설치하고 전용 factory-studio 프로필(2CPU/4GB/20GB)로 기동했다. 서버와 컨테이너 psql/pg_dump 모두 PostgreSQL 18.6.
- backend/src/fs 및 frontend/src 독립 모듈 경계·content 자리·FastAPI 조립·React/TypeScript/Vite 빌드 기반, uv.lock/package-lock.json, Ruff/ESLint/Prettier, CI workflow 작성. 업무 API·화면은 만들지 않았다.
- 최초 리비전 7e97937e7bd0을 schema v0.9.1 기준으로 수기 작성했다. 실행 시 schema.json을 읽어 DDL을 생성하지 않는다. 모든 테이블·키 이후 FK를 생성하여 core 순환 앵커를 처리한다. CHECK는 C 번호(0-based constraints 배열)와 원문을 보존했다. PostgreSQL CHECK 실패 없음.
- 실제 DB 대조: core10/mes21/erp27/fems13=71, 712컬럼, 161 FK, PK71/UK166/CHECK163/일반INDEX38/유니크INDEX8. SERVICE/DB_POLICY80은 DB 제약에서 제외하고 미구현으로 명시했다. public.alembic_version은 업무 71개와 별도다.
- 빈 DB 적용 → 다운그레이드 → 업무 테이블·리비전 행 각각 0 확인 → 재적용 → 전수 대사 통과. 대조 검사기는 컬럼 순서·타입·nullable·default/identity·키·CHECK 정규화 식·인덱스 조건·FK 범위/대상/RESTRICT를 확인한다. 검사 식은 세션 임시 테이블에서 정규화하고 롤백한다.
- 최종 21명령 모두 exit0, 전체 원문은 docs/agent/FS-009_검증실행.json. 기존 unittest 44개 및 실제 DB 변조 감지 테스트 9개 통과, db:validate 오류0, isolation R1~R5 위반0. frontend typecheck/lint/format/build, Ruff 통과. 컨테이너 pg_dump18 스키마 덤프 생성.
- 초기 실행 중 Prettier 경로 지정 exit2 및 Ruff 스타일 exit1을 수정 후 재검증했다. 기존 Excel 도구 npm audit moderate2건은 남음(ExcelJS/uuid); 별도 npm audit exit1, 주버전 자동 변경은 미적용. frontend audit0. 이전 Python3.9.6/Node26.7.0 대비 기존 회귀 결과 차이 없음.
- schema.json SHA256 7e97937e7bd0df6fdae97b309444dbfdac584dd2efae71ad4f0bad7eed2d5e44 유지. 사용자 지시로 migration_revision=null 유지. UI/prototypes·Excel·ERD 변경 없음. 정적 validation-report와 실제 DB ddl-verification-report는 구분한다.
- 미실행/범위 밖: 원격 CI·push·mirror push·배포, 시드 생성/INSERT, 업무 API·화면·SERVICE 정책·인증/세션·동시성·성능. Git 커밋하지 않음.
- 결과/실행 안내/antigravity 인계 가능 목록: docs/agent/실행기반_FS-009.md. 다음 ID는 결과 보고 후 사용자 확인을 기다린다.

- 최종 패키지 보강: 빈 디렉터리 상태에서 초기 설치된 editable 패키지 import 실패(exit1)를 uv sync --reinstall-package로 해소(exit0). FastAPI 앱 import·라우트0 검증 exit0, CI import 검사 추가. schema/Excel/ERD/UI/prototypes 16파일 바이트 보존 및 git diff --check exit0.

## 2026-09-24 FS-015 결정적 시드 생성기·게스트 복사 완료

- 재개 전 `fs-015-seed` 브랜치, 깨끗한 작업 트리, WIP 커밋 `dfb705a`를 확인했다. main은 antigravity AG-01 도움말·AG-02 설명 카드 5커밋이 앞선 상태였고 antigravity worktree/브랜치는 체크아웃하지 않았다.
- `backend/seed/`에 단일 코드 사전, 결정적 템플릿 생성기, 게스트 복사기, V1~V12 검증기, CLI를 구현했다. 난수는 사용하지 않는다.
- PostgreSQL 18.6 별도 검증 DB에 `sv-20260923-1`, T0 2026-09-23 템플릿 **7,469행**을 실제 INSERT했다. 문서의 테이블별 행 수와 일치했고 CHECK·FK·UK 위반은 0건이다.
- 복사 대상 업무 데이터 **7,463행**은 테이블별 `INSERT ... SELECT`로 처리한다. 자식이 참조하는 부모에만 임시 old/new id 매핑을 만들고 sequence 선발급 + `OVERRIDING SYSTEM VALUE`를 쓴다. leaf는 id를 생략한다.
- PL/pgSQL 함수 1회 호출 대신 테이블별 문장을 선택했다. `statement_timeout`이 복사 전체가 아닌 각 문장에 적용되고, 바깥 단일 트랜잭션이 전부 성공/롤백을 보장한다.
- 같은 `(seed_version,T)` 두 번 생성한 전체 정렬 JSON 바이트가 일치했다. 복사 T `2026-10-07`, `2027-01-05`에서 FS-005g §1.2 연월·ISO 주차·연도·적용월 재계산을 확인했다.
- V1~V12를 실제 DB 자동 테스트로 구현해 템플릿과 모든 복사 세대에서 통과했다. 복사 10회 최종 실측은 중앙값 **0.4555초**, 최대 **0.4758초**로 2초 목표 안이다. 동시 guest_pool 대기·API·네트워크 시간은 미측정이다.
- FS-005g §10.5의 미대조 NOT NULL 일반 규칙(created_at, KRW, 행 번호, 견적 이력, 출하·매출 시각, 확정·취소, 소명 키)을 `docs/agent/시드생성기_FS-015.md`에 표로 기록했다.
- `backend/pyproject.toml`에 seed 패키지를 포함시켜 editable 설치 후 `import seed`를 확인했다. schema.json·마이그레이션·제품 API·화면은 변경하지 않았다.
- antigravity 병합 기록: main의 AG-01 화면 도움말 3커밋과 AG-02 카드 2커밋(`fbf7af7`, `40e534c`)을 현황에 반영했다. FS-015 브랜치는 완료 후 main 위로 rebase하고 사용자 지시 전 병합·push하지 않는다.
- 상세: `docs/agent/시드생성기_FS-015.md`.

## 2026-09-24 FS-015b created_at 업무 시간축 수정

- FS-005g §10.5의 “생성 시각=해당 업무 시각”과 달리 모든 업무 `created_at`이 T 00:00에 몰린 결함을 수정했다.
- 우선순위는 발생·시작·계측 timestamptz → 업무 일자 09:00 Asia/Seoul → 자체 업무 시각이 없는 마스터·기준정보 d−91 09:00이다. 자체 시각이 없는 자식은 모든 업무 FK 부모 이상으로 조정한다.
- V12에 `created_at ≤ confirmed_at`, `created_at ≤ cancelled_at`, `자식.created_at ≥ 부모.created_at` 검사를 추가했다.
- 시드 값과 같은 T의 결과 바이트가 바뀌므로 FS-005g §11에 따라 `seed_version`을 `sv-20260923-1`에서 **`sv-20260924-1`**로 올렸다. 기존 세대는 변경하지 않는다.
- 템플릿 7,469행, CHECK/FK/UK, 결정성, 서로 다른 T 2개, V1~V12를 다시 통과했다. 복사 10회 중앙값 **0.4548초**, 최대 **0.5582초**다.
- schema.json·마이그레이션·제품 코드·화면은 변경하지 않았다. 브랜치 `fs-015b-created-at`, main 병합·push 미실행.

## 2026-09-24 FS-016 공통 계층 완료

- 착수 전 FS-015b `90703e6`을 main에 fast-forward 병합하고 `fs-016-common` 브랜치를 만들었다. 시작 작업 트리는 깨끗했다. main 병합·push는 실행하지 않았다.
- FS-006b 원래 계약에 맞춰 게스트 저장소를 `workspace.guest_session_key`, 회원 저장소를 `auth_session`으로 구현하고 FS-010 2.1의 모호한 문구를 정정했다. schema.json·마이그레이션은 변경하지 않았다.
- `g_`/`m_` 접두어를 쓰는 단일 인증 해석기, 공통 인증 문맥, 회원/게스트 CSRF, scrypt 로그인, Secure·HttpOnly·SameSite=Lax 쿠키, 공통 오류 봉투·페이지·요청 로그를 구현했다.
- guest_pool 잠금·상한 20·FS-015 복사, 세대 초기화, 종료 시 게스트 키 난수 해시 교체, 만료 요청 거부, guest_pool→workspace 잠금 기반 자식→부모 정리와 감사/job 스냅샷 분리를 구현했다.
- `request_receipt` 멱등 처리를 게스트/회원 세션 생성, 모듈 변경, 세대 초기화에 적용했다. actor_key는 회원 사용자 ID·게스트 공간 UUID이며 토큰/쿠키/해시를 로그·감사·요청 결과에 기록하지 않는다.
- 실제 PostgreSQL 18 통합 테스트에서 게스트 진입→7,467행 복사→인증→세대 초기화→종료→만료→정리, 타 게스트 격리, 같은 키 재요청, 토큰 종류 오용, 회원·게스트 CSRF, 관리자 접근, 비밀 문자열 부재를 검증했다.
- 개발 의존성 `httpx 0.28.1`과 전이 의존성을 `uv.lock`에 추가했다. FastAPI/Starlette TestClient의 upstream 폐기 예정 경고 2건이 남지만 기능 실패는 없다. 비밀번호 해시는 표준 `hashlib.scrypt`라 별도 의존성이 없다.
- 최종 환경 Python 3.14.7 / Node 24.21.0 / PostgreSQL·psql 18.6. backend 11개·도구 44개 테스트, ruff lint/format, db:validate, R1~R5, 실제 DB 대사, frontend lint/format/build, diff check 모두 exit 0.
- 미실행: 동시 게스트 20명·guest_pool 대기·정리 경합 주입(FS-021), 배치 스케줄러·IP 레이트 리밋·배포, 업무 API·화면. `backend/tests/test_seed.py`는 수정하지 않았다.
- 상세: [공통 계층 FS-016](agent/공통계층_FS-016.md). 다음 ID는 사용자 확인 후 시작한다.

## 2026-09-24 FS-016 마무리·수량 대사

- 전체 71테이블 실제 DB 대사, 템플릿/게스트 수량 일치·누락 0. 7,467=업무 7,463+모듈 4, 7,469=앞 수량+공간 1+세대 1. 보고서에 테이블별 포함 기준을 명시했다.
- Node 24 PATH 선지정, Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6, factory_studio_fs016_test 사용. 대사 명령 exit 0, 트랜잭션 롤백.
- 사용자 지시에 따라 FS-016 미커밋 구현을 커밋 후 main에 fast-forward 병합한다. 스키마·마이그레이션 변경과 push 없음. FS-017 규약 누락·업무 화면 이동 처리 질문은 별도로 확인 중이다.
- 마무리 검증: backend 11개·회귀 44개, db:validate·R1~R5, Ruff lint/format, 프론트 lint/format/build(tsc 포함), diff check 모두 exit 0. 명령·exit code는 FS-016 보고서에 기록했다.

## 2026-09-24 AG-03 마무리 (rebase·병합)

- `antigravity/ag-03` 브랜치를 FS-016이 병합된 `main`(`e08f5d8`) 위로 rebase했다.
- `backend/pyproject.toml`의 `[tool.pytest.ini_options]`에 `markers = ["perf: performance benchmark test"]` 1줄을 추가해 perf 마커 경고를 해소했다.
- 백엔드 전체 테스트 26개(기존 11 - test_seed 1 + 분리 16) 전부 통과(exit 0), perf 마커 경고 0건 확인. (남은 경고 2건은 FastAPI/Starlette upstream StarletteDeprecationWarning 및 anyio DeprecationWarning)
- worktree 점검 후 `git fetch . antigravity/ag-03:main`으로 `main`에 fast-forward 병합 완료 (`af6f266`).

## 2026-09-24 AG-04 test_common.py 단위 테스트 분리 완료

- 브랜치: `antigravity/ag-04` (`main` 기준 분기).
- 단일 거대 테스트 함수로 직렬 수행되던 `backend/tests/test_common.py`를 11개 독립 단위 테스트로 분리했다:
  1. `test_guest_entry_and_copy_count`: 게스트 진입·복사 수량(7,467행) 및 세대 재생성(reset generations) 복사 수량/상태 대사
  2. `test_idempotency_identical_result`: 멱등 재호출 시 동일 결과 반환 (게스트 세션 생성, 회원 로그인, 모듈 PATCH, 세대 재생성)
  3. `test_idempotency_conflicting_payload_422`: 동일 멱등 키에 다른 요청 본문 전달 시 422 IDEMPOTENCY_CONFLICT
  4. `test_guest_scope_isolation`: 게스트 간 데이터/설정 격리 및 타 게스트 변경 미영향
  5. `test_token_kind_tampering_401`: 세션 쿠키 접두어 변조(`g_` ↔ `m_`) 시 401
  6. `test_csrf_missing_and_mismatch_403`: CSRF 토큰 누락 및 불일치 시 403 (게스트·회원 각각) 및 정상 토큰 200
  7. `test_ended_guest_cookie_401`: 게스트 세션 종료(DELETE) 후 기존 쿠키 재사용 시 401
  8. `test_expired_cookie_410`: 만료된 게스트 공간에 대한 쿠키 요청 시 410
  9. `test_cleanup_separates_data_and_audit`: 만료 게스트 정리 시 워크스페이스 물리 삭제(0) 및 감사/운영 기록 보존
  10. `test_no_token_or_hash_in_logs_audit_receipts`: 요청 로그, 감사 이벤트, 멱등 영수증에 토큰 및 해시 미노출
  11. `test_admin_access_and_guest_admin_404`: 미인식 경로 404 NOT_FOUND, 관리자 API 회원 200 / 게스트 404
- 판정식과 기대값은 원본과 동일하게 100% 보존했다.
- 템플릿 생성은 `common_env` (module scope) fixture에서 1회만 실행하고, 모듈 종료 시 TRUNCATE teardown을 수행하여 후속 테스트 모듈과의 DB 격리를 보장했다.
- 각 단위 테스트는 게스트 공간을 새로 생성하여 상태를 격리하고, 만료/청소 테스트 상호 간섭을 방지하도록 격리 보강했다.
- `conftest.py`는 수정하지 않았다 (Codex 소유 불변 유지).
- 검증 결과:
  - 백엔드 전체 테스트: 36개 (common 11 + verifier 9 + seed 16) 통과 (exit 0, `38.26s`).
  - 단독 실행 격리 검증: `-k test_cleanup_separates_data_and_audit`, `-k test_expired_cookie_410` 단독 통과.
  - 변조 실패 검증: `test_expired_cookie_410` 기대값을 400으로 임의 수정 시 해당 테스트만 단독 실패(`assert 410 == 400`) 확인 후 410으로 원복.
  - 정적 도구: `npm run db:validate` exit 0, `tools/audit_schema_isolation.py` exit 0, `tools/test_fs0*.py` 44개 통과 exit 0, Ruff lint/format exit 0.
- 커밋: `antigravity/ag-04`에만 커밋 (`cb53470`). `main` 병합 및 원격 push는 하지 않고 사용자 확인 대기.


## 2026-09-24 FS-017a 완료·분할 인계

- FS-016 `e08f5d8ef3cc09477263d3e29d566cc4fd5f781a`를 main에 fast-forward 병합했다. 복사 누락 0: 업무 7,463+모듈 4=7,467, 공간·세대 2를 포함하면 7,469. 이후 fs-017-portal에서 작업했다.
- 사용자 분할 지시 직후 `9244801` (`WIP FS-017a: 중단 시점 보존`) 커밋. `.env`·work/ 제외 확인. 이전에 작성한 b/c 산출물은 초안으로 보존했다.
- FS-017a 완료: 현재 세션 CSRF 토큰 복구·만료 쿠키 삭제, 독립 회귀 파일 4개 테스트, 공통 컴포넌트, P-01/P-02. 게스트 생성 응답 roles 누락을 클라이언트에서 정상 해석한다. 로그인 폼을 연 상태의 게스트 재시도가 다른 요청으로 바뀌지 않도록 수정했다.
- backend 전체 15개 통과, frontend 전체 39개 및 a 대상 19개 통과, typecheck/lint/format/build exit 0. Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6. backend 전체 DB=factory_studio_fs016_test. 상세 명령·exit code는 FS-017a 보고서.
- 분할 지시 전 실제 브라우저 5개·360px 검증도 실행했지만 FS-017c 완료로 처리하지 않는다. 초기 Vite content 접근 누락(exit 1)과 테스트 서버 SESSION_SECRET 미주입(브라우저 exit 1)을 수정·재실행해 통과했다. 비밀 값은 Git/보고서에 넣지 않았다.
- 이번 세션에서 schema.json·마이그레이션·test_common.py·test_seed.py 변경 없음. antigravity worktree·브랜치 미접촉, main rebase·병합·push 없음. 30분 WIP·종료 HANDOFF를 상시 규칙에 반영했다.
- 다음은 FS-017b. FS-017c 종료 때 최신 main에 한 번만 rebase한다. 현재 main 전진분은 이번에 반영하지 않았다.

## 2026-09-24 FS-017b 완료

- Claude Code가 FS-017a 보존 초안을 검토·보완했다. P-03 흐름 맵은 FS-005a 노드 17·연결 19와 일치, P-04 카드 3종 3항목, P-05 도움말 54개 파일(포털 7·MES 15·ERP 18·FEMS 14).
- 수정: P-05 도움말 키 조회를 `Object.hasOwn`으로 바꿔 객체 기본 속성 이름(`constructor` 등)이 404를 통과하던 결함 제거. 수정 전 실패 재현 테스트 포함.
- `frontend/src/portal/content-pages.test.tsx` 12개 추가. frontend 전체 51개 통과, typecheck/lint/format/build/`git diff --check` exit 0. backend·schema·마이그레이션 변경 없음(재실행 안 함). 브라우저 검증은 FS-017c.
- 다음: FS-017c. main rebase는 c 끝에 한 번.



## 2026-09-24 FS-017c 완료

- 기존 P-06/P-07 초안 검토·보완. 초기화 경고/확인·중복 요청 차단, 헤더 외 도움말/푸터/뒤로가기 이동 차단, 불확실 응답의 동일 키 재확인, 변경 성공과 조회 실패 분리. 토글은 성공 전 표시 값을 바꾸지 않아 실패 시 원래 값 유지. 게스트 만료는 Asia/Seoul·KST로 고정 표시.
- ADMIN만 운영 기록 조회. GUEST/OWNER 메뉴 비노출·직접 접근 404. offset/limit=20, 탭 전환 offset 초기화, 일반 조회 오류 인라인 재시도. API·DB 스키마 변경 없음.
- 화면 테스트 신규 21개·Playwright 검증 항목 분리(16개). README 실행/IntelliJ 안내·패턴 문서 확정. `tools/run_portal_smoke.py`로 고정 테스트 DB 초기화·템플릿 생성·서버 시작/종료를 재현한다.
- WIP `88f69b1` 보존 후 main `2cece7b`로 rebase 한 번. 현황/progress 문서 충돌은 양쪽 이력 보존으로 해결. rebase 후 WIP `4f5cea9`, AG-04 common 11개·AG-03 seed 16개 파일은 main과 바이트 동일.
- rebase 후 모든 지정 명령 exit 0: frontend typecheck/lint/format/build/test(72), Playwright(16), backend 전체(40), tools unittest(44), db:validate, audit_schema_isolation(R1~R5), git diff --check. 실행 런타임 Python 3.14.7/Node 24.21.0/PostgreSQL 18.6, 테스트 DB factory_studio_fs016_test/factory_studio_fs017_test, DB 검증은 순차 실행.
- content/·schema.json·마이그레이션·test_common.py·test_seed.py 직접 수정 없음. conftest.py 변경 없음. .env/work 제외. main 병합·push·antigravity 폴더/브랜치 조작 없음.
- 상세 명령·exit code·미실행 항목은 포털_FS-017c.md, 이어받기는 HANDOFF.md. 다음 ID는 사용자 확인을 기다린다.

## 2026-09-24 FS-017c 검토 (Claude Code)

- Codex 보고를 저장소에서 재현했다: main `2cece7b` 위 fast-forward 가능, test_common/test_seed는 main과 diff 0, content·schema·alembic·conftest는 cbcd5c5 대비 변경 0.
- 재실행 결과(모두 exit 0): frontend typecheck/lint/format/build, 테스트 72개, backend 전체 40개(`factory_studio_fs016_test`), `tools/run_portal_smoke.py` Playwright 16개(`factory_studio_fs017_test`, 템플릿 7,469행). 둘은 순차로 실행했다.
- README IntelliJ 표의 브라우저 스모크 작업 디렉터리가 `<repo>/frontend`와 `<repo>`로 서로 어긋나 `<repo>`로 정정했다.
- 미재현: tools unittest 44, db:validate, R1~R5(이번 변경과 무관해 재실행 안 함).

## 2026-09-24 FS-018a 완료 (Claude Code)

- `fs-018-fems` 브랜치. FEMS 레이아웃 + F-11 에너지원(목록·등록·수정·삭제 RESTRICT 참조 건수·비활성화). 런처 FEMS 카드를 실제 화면으로 연결했다.
- 신규 `fs/common/scope.py`: 업무 API가 같은 트랜잭션에서 활성 세대·모듈 사용 여부를 재확인하고, 쓰기는 core와 같은 공간 잠금을 먼저 잡는다. 모듈 꺼짐은 409 `MODULE_DISABLED`.
- 참조 중인 에너지원의 계측 단위 변경 금지(`UNIT_IN_USE`). 스키마·마이그레이션 변경 없음.
- 공통 컴포넌트 확장(PageTitle help 키, ErrorNotice 참조 건수 목록, DataTable empty). FEMS·도움말 lazy 로딩으로 번들 경고 해소.
- 테스트: backend +22(전체 62), frontend +12(전체 84), Playwright +4(전체 20). 모든 검증 exit 0. 보고서 `docs/agent/FEMS_FS-018a.md`.

## 2026-09-24 AG-05 완료 (antigravity)

- F-10 설비 화면 및 백엔드 CRUD 복제 구현 (`antigravity/ag-05-f10` 브랜치).
- 백엔드 (`fs/fems/`):
  - `schema.py`: `EquipmentCreate`, `EquipmentUpdate` 정의 (설비 코드 정규식: `^[A-Z][A-Z0-9_\-]{1,29}$`).
  - `repository.py`: `EQUIPMENT_COLUMNS`, `EQUIPMENT_SORT`, `EQUIPMENT_REFERENCES` (5개 참조 테이블: `fems.meter`, `fems.energy_target`, `fems.energy_baseline`, `fems.energy_allocation`, `fems.production_record`), CRUD 함수 및 `equipment_meter_references`, `list_locations` 구현.
  - `service.py`: `list_equipments`, `get_equipment`, `list_locations`, `create_equipment`, `update_equipment`, `delete_equipment` 구현.
  - 결함 수정: 계측기(`fems.meter`)가 달린 설비의 `location_id` 변경 시 409 `PRECONDITION_NOT_MET` (`details.reason="LOCATION_IN_USE"`, `details.references=[{table,label,count}]`) 거부 처리.
  - `router.py`: `GET/POST /equipments`, `GET/PATCH/DELETE /equipments/{id}`, `GET /locations` 엔드포인트 연결.
- 프론트엔드 (`frontend/src/fems/`):
  - `Equipments.tsx`: F-11 에너지원 패턴 복제, 공간 셀렉트/비어있을 시 `EmptyState` 안내, 5개 참조처별 삭제 실패 건수 안내.
  - `FemsLayout.tsx`: `femsScreens`에 F-10 설비 등록.
  - `index.tsx`: F-10 라우트 등록.
  - `energy-sources.test.tsx`: 사이드바 화면 개수 단언을 `toHaveLength(femsScreens.length)`로 수정 (승인 반영).
- 테스트 및 검증:
  - `backend/tests/test_fems_equipment.py`: 25개 테스트 신규 작성 (계측기 있는 설비 공간 변경 409, 계측기 없는 설비 공간 변경 200 포함).
  - `frontend/src/fems/equipments.test.tsx`: 12개 테스트 신규 작성.
  - 백엔드 전체 테스트 통과: `pytest backend/tests -q` 87 passed (테스트 DB: `factory_studio_test`, exit 0).
  - 프론트엔드 전체 테스트 통과: `npm --prefix frontend test` 9개 파일 96개 테스트 ALL PASSED (exit 0).
  - typecheck, lint, format:check, build, ruff check/format, git diff --check 모두 exit 0.
- main 병합·push 없음.

## 2026-09-24 FS-018b 완료 (Claude Code)

- AG-05 검토: 저장소 대조 일치, frontend 96·backend 87 재현. 저장소 ruff 설정 기준 `test_fems_equipment.py` import 정렬 오류를 이 브랜치에서 수정(`test_common.py`의 같은 오류는 antigravity 소유라 보류).
- F-02 계측 조회: `GET /readings`(사업장 시간대 날짜 기간, 기본 최근 7일, 최대 31일, 결측 value=null), `/meters`, `/sites`. 화면은 초안/적용 필터, 표 기본, 채널 1개일 때만 선 그래프(결측은 선 끊김).
- `GUEST_LIMIT` 환경 변수(기본 20). 스모크가 23개로 늘어 상한에 걸린 것을 재현 후 테스트 서버만 200으로 올렸다.
- 테스트: backend +18(전체 105), frontend +14(전체 110), Playwright +4(전체 23). 모든 검증 exit 0. 보고서 `docs/agent/FEMS_FS-018b.md`.

## 2026-09-24 FS-018c 완료 (Claude Code)

- F-03 설비별 배분: 저장된 배분 결과 조회. 현재 결과 = 같은 설비·채널·구간의 최대 input_revision·method_version. 필터는 현재 판정 뒤에 건다(방법 필터로 옛 결과가 현재로 보이는 문제 방지, 테스트 고정). 합계는 현재 결과·invalid 제외·단위별.
- 화면: 단위별 합계 패널, 결과 표, 행별 계산 근거 패널(`<details>`), 이전 산정 결과 포함 옵션.
- 사용자 결정: F-14 요금제 적용 기간 겹침은 409 `PERIOD_OVERLAP`. FS-010 §7 기록.
- 테스트: backend +16(전체 121), frontend +11(전체 121), Playwright +3(전체 26). 모든 검증 exit 0. 보고서 `docs/agent/FEMS_FS-018c.md`.

## 2026-09-24 AG-06 F-14 요금제 복제 완료 (antigravity)

- F-14 요금제: F-10 설비 화면 패턴 그대로 복제 구현.
- 백엔드 (`backend/src/fs/fems/`):
  - `schema.py`: `TariffCreate`, `TariffUpdate` 스키마 추가. 금액(basicCharge, usageRate)은 소수점 4자리 이하 문자열, effectiveFrom/effectiveTo는 `YYYY-MM` 정규식 검증.
  - `repository.py`: `TARIFF_COLUMNS`, `TARIFF_SORT`, `source_exists`, `tariff_dict`, `list_tariffs`, `get_tariff`, `tariff_code_taken`, `insert_tariff`, `update_tariff`, `delete_tariff`, `find_overlapping_tariffs` 구현.
  - `service.py`: `list_tariffs`, `get_tariff`, `create_tariff`, `update_tariff`, `delete_tariff` 구현.
    - 부모 에너지원(`energy_source_id`) 존재 검증 실패 시 400 `fields.energySourceId` (`INVALID_ENERGY_SOURCE`).
    - `effective_to < effective_from` 시 400 `fields.effectiveTo` (`INVALID_EFFECTIVE_TO`).
    - 기간 겹침 시 409 `PRECONDITION_NOT_MET` (`details.reason="PERIOD_OVERLAP"`, `details.conflicts=[{id, tariffCode, effectiveFrom, effectiveTo}]`).
    - 삭제는 참조 테이블이 없어 멱등 삭제 지원.
  - `router.py`: `GET/POST /tariffs`, `GET/PATCH/DELETE /tariffs/{id}` 라우트 등록.
- 프론트엔드 (`frontend/src/fems/`):
  - `Tariffs.tsx`: F-10 설비 화면 패턴 복제 구현. 에너지원 필터 및 선택, 기본요금/사용요금 쉼표 포맷팅, 적용 기간 표시(진행중/기간), 에너지원 부재 시 EmptyState, 등록/수정 모달 및 기간 겹침(PERIOD_OVERLAP) 충돌 정보 표시, 삭제 확인 다이얼로그.
  - `FemsLayout.tsx`: `femsScreens`에 F-14 요금제 등록 (group: "요금").
  - `index.tsx`: F-14 라우트 등록 (`/tariffs`).
- 테스트 및 검증:
  - `backend/tests/test_fems_tariff.py`: 21개 테스트 신규 작성 (에너지원 검증, 코드 중복, 기간 검증, 겹침 409 충돌정보 검증, CRUD 등).
  - `frontend/src/fems/tariffs.test.tsx`: 12개 테스트 신규 작성 (목록/필터/등록/수정/삭제/충돌 표시 등).
  - 백엔드 전체 테스트 통과: `pytest backend/tests -q` 142 passed (테스트 DB: `factory_studio_test`, exit 0).
  - 프론트엔드 전체 테스트 통과: `npm --prefix frontend test` 12개 파일 133개 테스트 ALL PASSED (exit 0).
  - typecheck, lint, format:check, build, ruff check/format, git diff --check 모두 exit 0.
- main 병합·push 없음.

## 2026-09-24 FS-018d 완료 (Claude Code)

- AG-06(F-14 요금제) 검토: 저장소 일치, 겹침·nullable PATCH 처리 확인, frontend 133·backend 142·Playwright 26 재현.
- F-04 배출량 `GET /emissions`: 최상위 계측기만 합산, invalid 제외, 배수 적용, 연도별 EMISSION 계수, PRIMARY 미사용, 상태 4종, 부분 계산 표시. 화면은 총량 타일 + 에너지원별 표 + 근거 패널.
- 테스트: backend +15(전체 157), frontend +11(전체 144), Playwright +2(전체 28). 모든 검증 exit 0. 보고서 `docs/agent/FEMS_FS-018d.md`.

## 2026-09-24 FS-018e 에너지 목표 비율표 (Claude Code)

- 목표 95% 고정 → 월·대상별 90~105% 고정 비율표(`seed/common.py TARGET_RATIOS`). seed_version `sv-20260924-2`. 생성기·V8 검증기·test_seed.py V8 쿼리 동시 수정.
- 신규 `test_seed_targets.py` 6개. backend 163, Playwright 28(템플릿 7,469 재생성), frontend 144, 모든 검증 exit 0.
- 기존 템플릿·게스트 세대는 옛 값 유지(FS-005g 11장). 로컬 DB는 `seed.cli template` 재실행 필요.

## 2026-09-24 FS-018f 완료 (Claude Code)

- F-01 대시보드 `GET /dashboard?month`: TOE(PRIMARY, 환산 후 합산), 사업장 TOE 목표 달성률, 예상 요금(그 달 요금제), 배출량(F-04 동일), 일자별 TOE, 설비 상위 5, 품질 이상. 시드 9월 99.0% 목표 이내, 8월 104.2% 초과.
- 테스트: backend +20(전체 183), frontend +14(전체 158), Playwright +3(전체 31). 모든 검증 exit 0. 360px 스크린샷 확인. 보고서 `docs/agent/FEMS_FS-018f.md`.

## 2026-09-24 FS-018g 완료 (Claude Code)

- F-07 `GET /targets/performance`: 범위별 섹션, 단위 불일치는 계산 불가, 목표 없으면 미설정, 당월 누계 표시. 시드 9월 사업장·설비 모두 이내·초과 혼재.
- F-14 기준정보 그룹 이동, 360px 달성률·상태 열 앞으로, 스모크 포트 검사 SO_REUSEADDR(연속 실행 오검출 수정).
- 테스트: backend +18(전체 201), frontend +11(전체 169), Playwright +2(전체 33). 모든 검증 exit 0. 보고서 `docs/agent/FEMS_FS-018g.md`.

## 2026-09-24 AG-07 FEMS 사이드바 모바일 접는 메뉴 완료 (antigravity)

- FEMS 사이드바 반응형 접기 구현: 800px 이하에서 네이티브 `<details><summary>`로 접힘 메뉴 제공.
- `FemsLayout.tsx`:
  - `useLocation()` 기반 현재 화면 식별하여 summary에 "FEMS 메뉴 · 현재 화면 ID와 이름" 노출.
  - `<details open>` 및 `ref` 기반, 메뉴 링크(`NavLink`) 클릭 시 `onClick`에서 `details.open = false`로 자동 닫힘.
  - `aside[aria-label="FEMS 메뉴"]` 및 `femsScreens` 배열 구조 100% 보존.
- `shared/styles.css`:
  - 파일 끝에 801px 이상에서 summary 숨김 및 nav/eyebrow 항상 펼침 CSS 추가 (JS 화면 크기 감지 없음).
  - 800px 이하에서 summary 스타일(터치 영역, 화살표 인디케이터, 테두리, 배경) 추가.
- 테스트 및 검증:
  - `frontend/src/fems/sidebar.test.tsx` 11개 단위 테스트 신규 작성 (현재 화면 이름 노출, 메뉴/다른앱 링크 클릭 시 details 닫힘, aria-label/목록 구조 유지).
  - 프론트엔드 전체 테스트 통과: `npm --prefix frontend test` 16개 파일 180 passed (exit code 0).
  - typecheck, lint, format:check, build 모두 exit code 0.
  - 브라우저 스모크 검증: `tools/run_portal_smoke.py` 33 passed (exit code 0, 360px 모바일 8개 화면 포함).
  - 수정 금지 파일(다른 FEMS 화면, 백엔드, content, conftest 등) 변경 0.
- main 병합·push 없음.

## 2026-09-24 FS-018h 완료 (Claude Code)

- F-08 `GET /billing`: 월별 요금제 선택·구간 분할, TARIFF_MISSING·NOT_BILLABLE, 계측 없는 달 미청구. 시드 8~9월 합계 11,240,597원(전력 8월 120원·9월 130원).
- 대시보드 요금 계산 삭제 후 `_billing` 공통 사용(대시보드 테스트 무수정 통과). AG-07 충돌 회피로 styles.css 무수정.
- 테스트: backend +16(전체 217), frontend +11(전체 180), Playwright +2(전체 35). 모든 검증 exit 0. 보고서 `docs/agent/FEMS_FS-018h.md`.

## 2026-09-24 AG-07 검토·통합 (Claude Code)

- AG-07 위로 FS-018h rebase. Chromium 153 재현 결함 2건 수정: (1) 모바일 첫 진입에 메뉴가 펼쳐짐 (2) 넓은 화면에서 메뉴 링크 클릭 시 사이드바가 사라지고 다시 열 수 없음. `matchMedia(max-width:800px)`일 때만 닫고 좁은 화면은 닫힌 채 시작.
- sidebar 테스트 조정·추가(frontend 194), Playwright 1280/360 사이드바 테스트 2개 추가(37). backend는 검증된 FS-018h와 동일.

## 2026-09-24 CI 실패 원인 수정 (Claude Code)

- GitHub Actions `FS-009 runtime and schema`가 첫 push(AG-04 `2cece7b`)부터 10회 연속 실패. 원인: CI는 `ruff check backend`(디렉터리 전체)인데 `backend/tests/test_common.py`(AG-04)와 `backend/alembic/env.py`에 import 정렬 오류(I001) 2건. 로컬 검증은 FEMS 파일만 지정해 ruff를 돌려 놓쳤다.
- 두 파일 import 정렬만 수정(`ruff --fix`, 동작 변화 없음). test_common.py는 antigravity 소유이나 정렬 한 줄이라 수정했다.
- 나머지 CI 단계를 CI 환경 변수만으로(.env 미사용, 빈 `factory_studio_ci_test`) 재생: alembic upgrade → DDL 대사(SHA 7e97937e…d5e44 불변) → pytest 217 → downgrade/upgrade → DDL 대사 → frontend lint/format/build 모두 exit 0.
- CI에 없던 frontend `typecheck`와 단위 테스트(`npm --prefix frontend test`) 단계를 추가했다. Playwright는 CI에 없다(로컬 `tools/run_portal_smoke.py`).
- 규칙: 완료 전 ruff는 CI와 같은 범위로 실행한다 — `ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py`.

## 2026-09-24 FS-018i 완료 (Claude Code)

- F-05 `/production-records`: 초안 CRUD, confirm, revise. ALREADY_CONFIRMED·DRAFT_EXISTS·NOT_LATEST·REVISION_FIELDS_FIXED·PERIOD_OVERLAP. 날짜 → 사업장 시간대 반개구간.
- 공통 ErrorNotice conflicts 표시. 360px에서 상태·관리 열 앞으로, 필터 체크박스 한 줄.
- 테스트: backend +27(전체 244, CI 환경), frontend +13(전체 207), Playwright +2(전체 39). 모든 검증 exit 0. 보고서 `docs/agent/FEMS_FS-018i.md`.

## 2026-09-25 FS-018j 완료 (Claude Code)

- F-06 `GET /intensity`: 기록별·품목별 원단위, 확정 기준선 증감. NO_PRODUCTION·NO_ENERGY. 화면 `Intensity.tsx`.
- `fs.common.clock`: `FS_TODAY` 업무 기준일, 게스트 만료는 실제 시각. FEMS 테스트 fixture·스모크 날짜 고정.
- `COOKIE_SECURE` 변경(다른 작성자)의 무세션 500 결함을 `config.cookie_secure()` 분리로 수정, 사용자 결정 ③.
- 테스트: backend +23(전체 267, CI 환경), frontend +13(전체 220). 보고서 `docs/agent/FEMS_FS-018j.md`.

## 2026-09-25 FS-018k 완료 (Claude Code)

- F-13 `/energy-factors` CRUD, 화면 `Factors.tsx`(탭 분리). 계수 단위 서버 결정, UTILITY 거부, 에너지원·유형 고정.
- 도움말 f-13을 구현에 맞게 수정. FS-018j는 main `5bcc4d2` ff, main CI 통과(15분 13초).
- 테스트: backend +21(전체 288, CI 환경), frontend +11(전체 231), Playwright +2(전체 43). 보고서 `docs/agent/FEMS_FS-018k.md`.

## 2026-09-25 FS-018l 완료 (Claude Code)

- F-12 `/meters` 계측기·채널 CRUD, 화면 `Meters.tsx`(마스터-디테일). 기존 `GET /meters`(F-02) 응답을 확장해 공용.
- METER_IN_USE·CHANNEL_IN_USE 잠금, 부모 순환 방지, 누적 채널 단위 검사. 도움말 f-12 수정. FS-018k는 main `a5209b6` ff, CI 통과.
- 테스트: backend +25(전체 312, CI 환경), frontend +12(전체 243), Playwright +2(전체 45). 보고서 `docs/agent/FEMS_FS-018l.md`.

## 2026-09-25 backend 테스트 시간 단축 완료 (Codex)

- 전용 worktree `factory-studio-codex`, `codex/test-speed`를 `origin/main 70951d4`로 rebase. 메인 작업 폴더·antigravity worktree 사용 안 함.
- 공유 템플릿은 세션당 1회, 각 테스트는 실제 게스트 API로 별도 공간 생성. 게스트만 FK 자식 → 부모 순 정리하고 템플릿을 보존한다. FS_TODAY·GUEST_LIMIT은 fixture에서 설정.
- 전체 DB 정리 fixture를 먼저 실행하도록 수명을 분리. FEMS fixture 13개를 공용 guest_space에 연결. 테스트 본문 261개/보조 함수 AST와 test_common.py·test_seed.py 원본 보존. 직접 SQL 변경은 게스트 S 범위임을 확인했다.
- Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6, `factory_studio_codex_test`만 사용. `.env` 없이 DATABASE_URL·TEST_DATABASE_URL·PATH·HOME만 전달.
- `uv run --project backend pytest backend/tests -q --durations=15`: 개선 전 **782.272초, 312 passed, exit 0** → 개선 후 연속 **368.737초 / 308.066초, 각 312 passed, exit 0**. 평균 **56.7% 단축**. 예전 78e1206의 실패 포함 측정은 비교에서 제외.
- 격리·세대 초기화·legacy 혼합 순서 선택 검증 6 passed(exit 0). 템플릿 내용 불변·게스트 잔여 0 검사 통과. CI 범위 Ruff check·format --check, AST/보호 파일 확인, git diff --check 각각 exit 0.
- 남은 병목: 실제 게스트 복사/API, 독립 seed 결정성·복사 검증(준비 약 11~12초), 기존 portal/seed_targets 준비·schema verifier. 새 의존성·업무 코드·스키마·마이그레이션 변경 없음.
- 상세 명령·결과·재현: [테스트 시간 단축](agent/테스트시간단축.md). HANDOFF 갱신. main 병합·push 없음. 다음: 사용자 결과 확인, 병행 main 반영 시 담당자가 rebase 후 회귀.

## 2026-09-25 FS-018m 완료 — FEMS 14/14 (Claude Code)

- F-09 `/sites`·`/locations` CRUD, 화면 `Sites.tsx`. TIMEZONE_IN_USE 잠금, 공간 사업장 고정, 부모 순환 방지. 도움말 f-09 수정. FS-018l은 main `70951d4` ff, CI 통과.
- MES·ERP 작업 계획과 Codex 프롬프트 작성(`docs/agent/MES_ERP_작업계획_FS-019_020.md`).
- 테스트: backend +20(전체 332, CI 환경), frontend +11(전체 254), Playwright +2(전체 47). 보고서 `docs/agent/FEMS_FS-018m.md`.

## 2026-09-25 통합: Codex 테스트 시간 단축 + FS-018m (Claude Code)

- `fs-018m-f09`를 `codex/test-speed`(83e5a54) 위로 rebase. HANDOFF·진행현황·progress 충돌은 두 내용을 모두 보존해 해결.
- `test_fems_sites.py` fixture를 `guest_space`로 전환(테스트 본문 동일).
- 검증(CI 환경): backend **332 passed, 5분 36초**(통합 전 15분 8초), frontend 254, 스모크 47, ruff(CI 범위)·tools unittest 44·db:validate·audit·git diff --check 모두 exit 0.

## 2026-09-25 FS-020a 완료 (Claude Code)

- MES 기준정보 4화면 + API. 표 명세(`Master`) 기반 공통 CRUD, 품목 기준 단위 잠금(UNIT_IN_USE), 공간 순환 방지, 공정 허용 설비 교체.
- 공통 스타일 체크박스 보정(별도 커밋). 도움말 m-10·m-12 수정. 포털·FEMS의 MES 링크를 `/mes`로.
- 테스트: backend +28(전체 360, CI 환경), frontend +12(전체 266), Playwright +7(전체 54). 보고서 `docs/agent/MES_FS-020a.md`.

## 2026-09-25 FS-020b 완료 (Claude Code)

- M-14·M-15 버전 API·화면. `service.Versioned`로 두 흐름 공통 처리. 게시·폐기 엔드포인트의 쿼리 파라미터 노출 결함을 작성 중 발견해 클로저로 수정.
- 도움말 m-14·m-15 수정. FS-020a main `8294164` ff.
- 테스트: backend +24(전체 384, CI 환경), frontend +8(전체 274), Playwright +4(전체 58). 보고서 `docs/agent/MES_FS-020b.md`.

## 2026-09-25 FS-020c 완료 (Claude Code)

- `mes/planning.py`: 생산계획(초안·확정·라인 교체)·작업지시(생성·수정·발행+LOT·취소·LOT 보충). 계획 라인 FOR UPDATE 배정 한도, 동시 요청 테스트.
- MES 진입을 생산계획으로. 도움말 m-02·m-03 보강. FS-020b main `0f68b53` ff.
- 테스트: backend +20(전체 404, CI 환경), frontend +8(전체 282), Playwright +3(전체 61). 보고서 `docs/agent/MES_FS-020c.md`.

## 2026-09-25 FS-020d 완료 (Claude Code)

- `mes/execution.py`: LOT 목록·추적 상세, 공정 시작(TX-01)·완료(TX-02). 잠금 공간→지시→LOT→실행, EQUIPMENT_BUSY, all_defective 종결.
- 도움말 m-04·m-05 보강. FS-020c main `83c745d` ff.
- 테스트: backend +16(전체 420, CI 환경), frontend +5(전체 287), Playwright +3(전체 64). 보고서 `docs/agent/MES_FS-020d.md`.

## 2026-09-25 FS-020e 완료 (Claude Code)

- 자재 투입 API·화면(BOM 제안량, RESULT_CONFIRMED, DUPLICATE_ISSUE, 삭제 정정), 실적 조회 `GET /results`, 공통 `ResultForm`.
- 도움말 m-06·m-07 보강. FS-020d main `2a0717e` ff.
- 테스트: backend +12(전체 432, CI 환경), frontend +7(전체 294), Playwright +3(전체 67). 보고서 `docs/agent/MES_FS-020e.md`.

## 2026-09-25 FS-020f 완료 (Claude Code)

- `mes/packing.py`: 담을 LOT, 포장 CRUD·담기·닫기·묶기, PALLET 입고. 도움말 m-08·m-09 보강. FS-020e main `6bcbe1e` ff.
- 스모크는 처음에 사용자 개발 서버(8000·5173) 때문에 미실행 → 종료 후 70 passed.
- 테스트: backend +14(전체 446, CI 환경), frontend +7(전체 301), Playwright +3(전체 70). 보고서 `docs/agent/MES_FS-020f.md`.


## 2026-09-25 FS-019a 구현 — 스모크 승인 대기 (Codex)

- WIP 보존 뒤 `origin/main 6bcbe1e`로 rebase. MES·ERP 라우트 모두 보존, ERP 런처 연결 및 Home 안내 수정.
- E-15 거래처·E-16 품목/단위환산·E-17 거래처별 단가 CRUD, E-18 계정/분개규칙 읽기 전용. S 격리·write_scope·CSRF/멱등 영수증·참조 건수·단가 구간 겹침 거부. ERP 독립 안내, Field/select/checkbox 사용 보정.
- backend guest_space 회귀 78개, frontend 20개 추가. 최종 프론트 전체 314 passed 및 typecheck/lint/format/build, CI Ruff check/format, db:validate, audit_schema_isolation, diff --check exit 0. backend 전체 **510 passed, 580.736초, exit 0**(CI 네 변수·전용 DB).
- Playwright ERP CRUD 1개·360px 4개 추가. 공용 포트/DB 사용 승인을 기다리고 있어 실행·스크린샷 확인은 미실행. 완료 판정 보류.
- API 계약 §8·도움말·진행현황·Codex HANDOFF 갱신. 보고서 `docs/agent/ERP_FS-019a.md`. 새 의존성·스키마 변경 없음. push·main 병합 없음.

## 2026-09-25 통합: Codex FS-019a ERP 기준정보 (Claude Code)

- Codex `4e2bc74`를 FS-020f(`25f4312`) 위로 rebase해 `fs-019a-erp-integrate`로 통합. 코드는 충돌 없음, 진행현황·progress·HANDOFF 충돌은 두 내용 보존.
- 통합 수정: FEMS·MES 사이드바의 ERP 링크를 도움말 대신 `/erp` 화면으로.
- 통합 검증(CI 환경): backend **524 passed**(9분 6초), frontend **321 passed**, 스모크 **75 passed**(ERP 360px 포함), ruff(CI 범위)·tools unittest·db:validate·audit·git diff --check 통과. Codex 대신 Claude Code가 통합 상태로 스모크를 실행(Codex 사용량 절약).
- 후속(Codex FS-019b에서): ERP 화면의 관리 버튼이 FEMS·MES의 `link-button`과 다르고, 등록 폼 select가 좁은 기본 모양이다. 동작 문제는 없어 통합을 막지 않았다.

## 2026-09-25 FS-020g 완료 — MES 15/15 (Claude Code)

- `mes/dashboard.py`·`Dashboard.tsx`: M-01 지표·파이프라인·불량 사유·계획 대비 실적·처리 대기. MES 진입을 대시보드로. 도움말 m-01 보강.
- 스모크에서 발견한 CHECK 위반(종료 < 시작)을 `clock_timestamp()`로 수정. Codex FS-019a 통합 main `cc8729d` ff.
- 360px에서 파이프라인 순서(공정 코드 순) 결함 발견 → 경로 순번 정렬.
- 테스트: backend +8(전체 531+1, CI 환경), frontend +5(전체 326), Playwright 76. 보고서 `docs/agent/MES_FS-020g.md`.


## 2026-09-25 P-02 런처 아이콘 크기 조정 (Codex)

- 사용자 이미지 요청: 큰 솔루션 카드를 정사각형 아이콘 타일 + 아래 이름 배치로 변경. 기존 단색·링크·사용 상태·설명 유지.
- Home.tsx + 전용 Home.css만 제품 코드 변경. 데스크톱 타일 104px/아이콘 48px, 480px 이하 타일 88px/아이콘 40px·2열. 공통 스타일 수정 없음.
- Node 24.21.0: frontend typecheck·lint·format:check·build·test(314 passed) 각각 exit 0. git diff --check exit 0.
- 브라우저 스모크·360px 직접 검증·backend는 미실행. 사용자 지시대로 Claude Code가 통합 후 스모크·360px를 담당한다. push·main 병합 없음.


## 2026-09-26 3D 공장 둘러보기 구현 (Codex)

- 사용자 승인한 별도 화면 `/factory`, 상단 앱 런처 오른쪽 3D 공장 메뉴. 전체 조감도·3인칭 이동·1/2층 전환·계단·충돌·모바일 이동 버튼.
- 1층 현장사무실(직원 1·노트북·바코드 프린터), 조립→비전검사→포장 설비 3대/키오스크/이송과 순회 직원 1명, 2층 사무실 직원 2명. 사용자 캐릭터 별도. 실제 데이터와 연동하지 않는 합성 시연.
- three 0.186.1, React Three Fiber 9.8.1, Drei 10.7.8, @types/three 0.186.0 추가. lazy load, 외부 모델/DB 변경 없음.
- Node 24.21.0. frontend typecheck·lint·format:check·build·test(330 passed), 독립 Playwright(7 passed, 20.0초), git diff --check 각각 exit 0. 360px·2층 스크린샷 직접 확인.
- 5186 포트/모의 API의 독립 검증만 실행. 공용 8000/5173·스모크 DB·backend 미사용. 통합 스모크는 Claude Code 담당, push/main 병합 없음.
- 보고서 `docs/agent/3D공장_구현.md`. 다음: 통합 환경에서 확인 후 사용자 피드백. ERP 후속 업무 미착수.

## 2026-09-26 통합: Codex 런처 아이콘 타일 + 3D 공장 (Claude Code)

- Codex `codex/fs-019a-erp-master`의 새 커밋 3개(`f9eb879` P-02 런처 타일, `5593693`·`31a4472` 3D 공장)를 main `626ba35` 위로 cherry-pick해 `factory-3d-integrate`로 통합(이미 통합한 FS-019a 커밋 2개는 제외). 문서 충돌만 두 내용 보존으로 해결.
- 새 의존성: `three` 0.186.1, `@react-three/fiber` 9.8.1, `@react-three/drei` 10.7.8, `@types/three`(dev). `npm audit --omit=dev` 0건. 3D 번들(`Factory-*.js` 919kB, gzip 245kB)은 `/factory` 진입 때만 지연 로딩.
- 통합 검증: frontend typecheck·lint·format:check·build·test **342 passed**, 스모크 **83 passed**, 3D 전용 브라우저 테스트(`npm --prefix frontend run test:factory-browser`, API 모의) **7 passed**. backend는 변경 없음(CI에서 전체 실행).
- 후속: 360px에서 상단 메뉴가 두 줄(‘나가기’가 둘째 줄)이 된다. 가로 스크롤은 없다.

## 2026-09-26 저장소 정리 (Claude Code)

- 사용자 요청으로 루트를 정리: 빈 `seed/`·`tests/`(초기 뼈대의 `.gitkeep`만, 실제는 `backend/seed`·`backend/tests`) 삭제, `prototypes/` → `docs/archive/prototypes/`, Git 제외 임시 추출본 `fs005g_check2_*.txt` 4개 → `work/fs005g-check2/`.
- 현재 문서의 시제품 경로(화면 설계서 3개, 설계 결정, 진행현황 표) 갱신. 지난 작업 보고의 옛 경로는 기록이라 그대로 둠.
- README에 루트 폴더·파일 의미 표와 현재 진행 상태 반영. 기존에 깨져 있던 `구현인계패키지_FS-012.md` 상대 링크 2개 수정(문서 내 깨진 상대 링크 0).
- 유지: 루트 `package.json`·`node_modules`(DB 설계서 도구), `work/`, `docker-compose.yml`, 형제 worktree·백업·참고자료 폴더.
- 검증: db:validate, audit_schema_isolation, tools unittest 44 OK. 코드 변경 없음(CI에서 전체 실행).

## 2026-09-26 FS-019b 완료 — ERP 7/18 (Claude Code)

- 사용자 결정: FS-019b~h 전부 Claude Code, E-G07 0원 매출 세금계산서 발급 금지.
- E-02 견적 · E-03 판매계획 · E-04 수주 API·화면·도움말. 목록·저장 훅을 `shared/hooks.tsx`로 옮겨 MES·ERP 공용(별도 커밋).
- 검증: frontend 354 passed, backend 561 passed(CI 환경), 스모크 87 passed, 360px 직접 확인. 상세 `docs/agent/ERP_FS-019b.md`.

## 2026-09-26 FS-019c 완료 — ERP 9/18 (Claude Code)

- FS-019b main ff(`0addc2e`, CI 통과) 뒤 진행. E-05 출하지시 · E-06 출하 API·화면·도움말, 출하 확정 트랜잭션 안에서 매출·채권 생성(TX-09를 019c에 포함 — 설계상 분리 불가).
- 포털 흐름 화면 테스트의 역할 조회 대기를 5초로(병렬 실행 타이밍 실패 해결).
- 검증: frontend 360, backend 574(CI 환경), 스모크 90, 360px 직접 확인. 상세 `docs/agent/ERP_FS-019c.md`.

## 2026-09-26 FS-019d 완료 — ERP 11/18 (Claude Code)

- FS-019c main ff(`22055ef`, CI 통과) 뒤 진행. E-07 매출 · E-08 세금계산서 API·화면·도움말. E-G07 0원 매출 발급 금지 구현.
- 검증: frontend 367, backend 582(CI 환경), 스모크 93 ×2, 360px 직접 확인(E-08 select 모양 수정). 상세 `docs/agent/ERP_FS-019d.md`.

## 2026-09-26 FS-019e 완료 — ERP 13/18 (Claude Code)

- FS-019d main ff(`40efad7`, CI 통과) 뒤 진행. E-09 매출채권 현황 · E-10 수금 등록·소명 API·화면·도움말.
- 동시성 주입: 병렬 소명 한도, 매출 취소 vs 소명 경합. 소명 취소는 `core.audit_event` 기록.
- 검증: frontend 375, backend 594(CI 환경), 스모크 96, 360px 직접 확인. 상세 `docs/agent/ERP_FS-019e.md`.

## 2026-09-26 FS-019f 완료 — ERP 16/18 (Claude Code)

- FS-019e main ff(`55c39c1`, CI 통과) 뒤 진행. E-11 매입 전표 · E-12 매입채무 · E-13 지급·소명.
- 019e 수금·소명 백엔드(`receipts.Side`)·화면(`settlement.ts` + `side` 속성)을 일반화해 매입 쪽에 재사용. 세액은 `revenue.line_amounts` 공용.
- 검증: frontend 381, backend 607(CI 환경), 스모크 100, 360px 직접 확인. 상세 `docs/agent/ERP_FS-019f.md`.

## 2026-09-26 FS-019g 완료 — ERP 17/18 (Claude Code)

- E-14 분개 미리보기 API(`GET /journal-preview`, 저장 없음)·독립 화면·공통 패널. 매출·수금·매입·지급 화면에 "분개" 버튼.
- 검증: frontend 384, backend 614(CI 환경), 스모크 102, 360px 직접 확인. 상세 `docs/agent/ERP_FS-019g.md`.

## 2026-09-26 FS-019h 완료 — ERP 18/18, FS-019 종료 (Claude Code)

- FS-019g main ff(`49a291d`, CI 통과) 뒤 진행. E-01 ERP 대시보드 API·화면·도움말, ERP 진입을 대시보드로.
- 기존 FEMS e2e "결측 구간"의 첫 로드 대기 누락(§7-8 함정)을 수정.
- 검증: frontend 389, backend 622(CI 환경), 스모크 104, 360px 직접 확인. 상세 `docs/agent/ERP_FS-019h.md`.

## 2026-09-26 FS-021 통합 검증 (Claude Code)

- FS-019h main ff(`2827f39`, CI 통과) 뒤 진행. 사용자 결정: AC-35~80 추적표, 로컬 성능 실측 포함.
- 테스트 추가: `test_integration_policies.py`(범위 격리 횡단·멱등 4개), `test_integration_ac.py`(AC 보강 15개). `tools/measure_fs021.py` 실측 도구.
- 결함 수정: `common/scope.py` 잠금 뒤 게스트 만료 재확인(AC-63).
- 상세 `docs/agent/통합검증_FS-021.md`.
- 사용자 결정 반영: 동시 게스트 생성 지연은 현행 유지, 미구현 기능은 1차 범위 밖(FS-012 §4-3에 추가), AC-68·73·74·75 단언 추가로 검증됨 33.


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

## 2026-09-26 통합: Codex 3D 공장 고도화 (Claude Code)

- Codex `codex/factory-building`의 커밋 2개(`b352514` Blender 비전검사 설비, `d3eaf31` 건물·재질·생산라인)를 main `907fed8` 위로 cherry-pick(`factory-building-integrate`). 문서 2개(진행현황·progress) 끝 절 충돌만 두 내용 보존으로 해결.
- 범위: 건물 외관↔내부 전환(외벽·지붕·하역장·옥상 공조기), 바닥·금속 재질과 그림자, 조립·비전검사·포장 Blender 모델(glb 4개 1.4MB)과 동작, 자재 선반·공구대, MES·ERP·FEMS 진입 카드. 새 의존성 없음, 3D 번들은 `/factory` 진입 때만 지연 로딩(Factory 925kB, gzip 247kB).
- 검증(메인 폴더에서 재실행): frontend typecheck·lint·format:check·build·test **393 passed**, 3D 전용 브라우저 테스트 **10 passed**, 스모크 **107 passed**, diff --check. 외관·내부·360px 스크린샷 직접 확인. backend 변경 없음.
- 참고: 업무 데이터(설비 상태 등)와의 실시간 연동은 아직 없다(화면에 "3D 합성 시연 · 실시간 설비 정보 아님" 표시).

## 2026-09-26 FS-022 배포 절차서 (Claude Code)

- Codex 3D 공장 고도화 main ff(CI 통과) 뒤 작성. `docs/deploy/배포절차_FS-022.md` — 사용자가 Vultr VM에서 직접 실행하는 절차(IP 단계 → 도메인·HTTPS 단계). Claude Code는 서버에 접속하지 않았다.
- 절차서를 **이지스 공존판**으로 교체(사용자 제공 수정본 채택 + 보완): 대상은 이지스 운영 서버 158.247.236.136(1 vCPU·2GB·55GB). 포트 분리(FS Nginx 8080·uvicorn 8021), Nginx default 유지, ufw 규칙 선반영, uv `/usr/local/bin`. Claude Code 보완: `apt upgrade` 제외, 프런트 맥북 빌드 기본(서버 Node 불필요), systemd `uv run --frozen`, RAM 여유·스왑 점검과 스왑 파일 절차. compose DB 바인드는 이미 `127.0.0.1:55432`.

## 2026-09-26 FS-022 배포 완료 — https://eip.hugh-d.com (Claude Code)

- 사용자 요청으로 서버에서 직접 실행(맥북 SSH 키, 비밀번호 입력 없음). 스냅샷은 사용자가 먼저 생성.
- 실행: Docker·uv 설치(apt upgrade 없음) → factory 사용자·읽기 전용 deploy key → clone `c41c274`·.env(서버 생성 비밀값) → PG18 Docker·마이그레이션·템플릿 시드 → systemd API(8021)·회수 타이머 → 프런트 맥북 빌드 rsync → CSR·Cloudflare Origin CA → Nginx 사이트(기본 서버 TLS 거절, fs→eip 301, CF real IP) → ufw 443 → reload.
- 문제와 해결: Nginx 1.24가 `http2 on;` 미지원 → `listen 443 ssl http2`. Cloudflare 레코드가 처음 `@`로 들어가 eip 미해결 → 사용자가 eip 추가. 루트·www·aegis가 FS를 보여 443 기본 서버로 TLS 거절(525). 맥북 DNS 음성 캐시로 로컬 curl 실패 → Cloudflare IP 고정으로 확인.
- 절차서를 실행한 그대로 재작성(`docs/deploy/배포절차_FS-022.md`).

## 2026-09-26 UI-01 공통 디자인 시스템·앱 레이아웃 (Claude Code)

- 브랜치 `ui-01-design-system`(기준 `b197491`, 커밋 `a5dddc2`·`7d7cbaf`·최종 UI-01 커밋). 상세 `docs/ui/디자인시스템_UI-01.md`.
- 원인: `main` 1160px 제한과 헤더 중앙 정렬 패딩, h1 36px·패널 28px·본문 15px/1.65, 레이아웃 3벌 복제, 스타일 없는 공통 클래스(`form-actions`·`toolbar`·`filter-inline`·`field-error`).
- 변경: 토큰(색·글자·간격·모양·컨트롤·앱 틀), 공통 `SolutionLayout`(접기·서랍·키보드), 한 줄 페이지 헤더, 공통 입력·버튼 상태, 표 숫자 정렬·긴 값 title, KPI 4열/모바일 2열, 알림 종류별 색, 목록 아래 상세 자동 스크롤, 도움말 읽기 폭, 3D 공장 캔버스 높이·툴바·설비 상세 오버레이. 직접 쓴 표 5화면에 금액 열 정렬.
- 전후(1366×768, F-01): KPI 3+1줄 → 4개 한 줄, KPI 시작 약 370px → 약 213px, 주요 차트 시작 약 700px(첫 화면 밖) → 약 350px.
- 검증: typecheck·lint·format:check·build exit 0, vitest 393 passed, 3D 브라우저 10 passed, 스모크 107 passed(5.7분, exit 0), `git diff --check`. 55경로 × 5해상도 넘침·작은 글자 점검 0건.
- 미실행: backend pytest(백엔드 변경 없음), Safari·실기기.
- DB migration / Excel / seed: 변경 없음. push·main 병합 없음.

## 2026-09-27 운영 후속 — 443 제한·이지스 도메인·:8000 차단·UI-01 배포·운영자 계정 (Claude Code)

- 443 ufw를 Cloudflare 대역 22개로 제한(원점 직접 443 차단 확인). 이지스 aegis.hugh-d.com: Access(사용자 설정) → Nginx aegis 사이트(office.html + `/api/`→127.0.0.1:8000) → office.html 수정 배포(secretary-ai `91baa61`, push) → 사용자 로그인 확인 → ufw 8000 제거(서비스 재시작 없음).
- UI-01(다른 세션 작업, 미병합)을 새 main 위로 cherry-pick·문서 충돌 병합, 프런트 393·3D 10·스모크 107 통과(로컬 Colima DB 재기동 후), CI 통과 → main `6d48f5f` → 서버 git pull·프런트 rsync.
- 회원 로그인 401 원인: 서버 `core.app_user` 0건. `tools/create_member.py`·`create_member_account` 추가, `INVALID_CREDENTIALS` 분리, 테스트 `test_member_account.py` 3개. 계정 생성은 운영 서버 비밀번호가 걸려 사용자가 직접 실행.

## 2026-09-27 UI-02 공통 UI 확정·기준 화면 3개·Antigravity 인계 (Claude Code)

- 브랜치 `ui-02-common-patterns`(기준 main `6d48f5f` → `88d584f` 위로 rebase), 코드 커밋 `0875482`(WIP `2fe2975` 포함). 문서: `docs/ui/공통UI규약_UI-02.md`·`docs/ui/메뉴적용표_UI-02.md`·`docs/agent/Antigravity_작업지시_UI-02.md`.
- Figma: `whoami` 결과 Starter 플랜·View 좌석. 프레임 URL이 없어 Figma 수치를 읽지 않았고 반영했다고 쓰지 않는다.
- 공통 구현(`shared/styles.css`·`components.tsx`·`SolutionLayout.tsx`·`app/App.tsx`): `--app-h`·`.app-shell`, 업무 화면 바닥글 제거, `.page-fill`/`.fill` 목록 채움, `thead th` 고정, 페이지 이동 sticky, `PageTitle(actions)`, `DataTable(leading)`·`wrap` 열·긴 값 포커스 펼침, `Pagination`·`DateRange`, `FormPanel`·`useDiscardGuard`, `EmptyState(onAction)`, `.field-row`, KPI 한 줄/2×2(3+1 방지), 대시보드 2열·`has-lead` 3:2.
- 화면: F-01 조회 월을 제목 줄로·주요 차트+구성 3:2·환산 합계, F-02 채움·보기 전환을 결과 줄로·늦은 응답 무시, F-05 목록 전체 폭·등록/수정/정정 한 패널.
- 전후(같은 뷰포트): F-02 1440×900 문서 2,286 → 900px(1366×768 2,286 → 768), F-05 1440 1,321 → 900px, F-01 1600 하단 3+1 → 2×2(1920 4열 → 2×2), 업무 화면 전체에서 바닥글 스크롤 약 43px 제거. 모바일 390·360, 720×450(200% 확대) 자연 스크롤·저장 버튼 접근 확인.
- 검증: frontend typecheck·lint·format:check·build exit 0, vitest 402 passed(+9), 상호작용 스크립트 51/51(패널 포커스·Esc·가둠·미저장 보호·등록→수정→확정→정정·검증 오류·머리글 고정·정렬·페이지 이동·CSV·그래프), 55경로 × 1440·390 전후 비교(가로 넘침 0·페이지 오류 0·제목 변화 0), `e2e/layout.spec.ts` 16개 추가, 스모크 121 passed / 1 failed(3D `걷기 입력은 3인칭 화면을 이동시킨다` 캔버스 스크린샷 30초 초과 — 단독 재실행 시 이 브랜치·main 각 2회 통과, 약 21~22초로 같음), `git diff --check`.
- 미실행: backend pytest(백엔드 변경 없음), `db:validate`(DB 변경 없음), Safari·실기기, 운영 서버 반영.
- 로컬 검증 중 게스트 공간 상한(20)에 걸려 로컬 백엔드만 `GUEST_LIMIT=100`으로 재시작했다(설정·데이터 변경 없음).
- DB migration / Excel / seed: 변경 없음. 사용자 요청으로 main에 rebase 통합(OPS `88d584f` 위), push 없음.
- 다음: 서버 배포(사용자 확인 후) → Antigravity A1부터(지시서) · Claude UI-03 예외 패턴.

## 2026-09-27 UI-02 A1 대시보드 조회 월 위치 (Antigravity)

- 브랜치: `antigravity/ui02-a1` (기준: main `ed9f438cbbd1f2aacec67a3029304020e3d7865e`)
- 대상: M-01(`mes/Dashboard.tsx`), E-01(`erp/Dashboard.tsx`)
- 내용:
  - 별도 `filter-bar`의 조회 월 입력을 `PageTitle`의 `actions`로 옮김 (F-01 대시보드 규약 준수).
  - 기존 2×2 카드 배치 및 하단 순서·내용 유지 (`has-lead` 미사용).
  - 조회 월 변경 시 쿼리 파라미터(`?month=`) 및 KPI 문구 보존.
  - `frontend/e2e/layout.spec.ts`에 M-01 및 E-01의 조회 월이 `.page-actions`에 위치하고 별도 `.filter-bar`가 없음을 검증하는 e2e 테스트 추가.
- 검증:
  - `npm --prefix frontend run typecheck` 통과 (오류 0)
  - `npm --prefix frontend run lint` 통과 (오류 0)
  - `npm --prefix frontend run format:check` 통과 (전체 일치)
  - `npm --prefix frontend run build` 통과
  - `npm --prefix frontend test -- --run` 통과 (43개 테스트 파일 402개 테스트 통과)
  - `git diff --check` 통과 (공백/줄바꿈 이상 없음)
- DB migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 대기. 확인 후 A2(조회 목록 M-09, E-07, E-14, P-07) 진행.

## 2026-09-27 UI-02 A2 조회 목록 L 패턴 적용 (Antigravity)

- 브랜치: `antigravity/ui02-a2` (기준: `ce731ab`, `antigravity/ui02-a1`)
- 대상: M-09(`mes/Receipts.tsx`), E-07(`erp/SalesRecords.tsx`), E-14(`erp/Journal.tsx`), P-07(`portal/Records.tsx`)
- 내용:
  - 각 화면 루트를 `.page-fill`로 변경하여 뷰포트 맞춤형 스크롤 규칙 적용.
  - P-07: 상단 탭을 `DataTable`의 `leading` prop으로 전달 (F-02 기준 화면과 동일 마크업).
  - P-07: ADMIN 전용 권한 분기 및 API 계약 보존.
  - 안내문 `<p className="muted" role="note">` 및 `Loading delay={300}` 공통 규약 정비.
  - `frontend/e2e/layout.spec.ts`에 A2 화면들(`.page-fill`) 레이아웃 검사 추가.
- 검증:
  - `npm --prefix frontend run typecheck` 통과 (오류 0)
  - `npm --prefix frontend run lint` 통과 (오류 0)
  - `npm --prefix frontend run format:check` 통과 (전체 일치)
  - `npm --prefix frontend run build` 통과
  - `npm --prefix frontend test -- --run` 통과 (43개 테스트 파일 402개 테스트 통과)
  - `git diff --check` 통과 (공백/줄바꿈 이상 없음)
- DB migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 대기. 확인 후 A3(보고서형 조회 F-03, F-04, F-06, F-07, F-08, E-09·12) 진행.

## 2026-09-27 UI-02 A3 보고서형 조회 R 패턴 정비 (Antigravity)

- 브랜치: `antigravity/ui02-a3` (기준: `26e9ab3`, `antigravity/ui02-a2`)
- 대상: F-03(`fems/Allocations.tsx`), F-04(`fems/Emissions.tsx`), F-06(`fems/Intensity.tsx`), F-07(`fems/Targets.tsx`), F-08(`fems/Billing.tsx`), E-09·12(`erp/Receivables.tsx`)
- 내용:
  - `.page-fill` 미사용 확인 및 문서 스크롤 정책 유지 (합계·근거·표 복합 화면).
  - 직접 쓴 표 숫자 열에 `th.num`, `td.num` 클래스 일관 적용 (F-04 소비량·배출량, F-06 원단위·생산량·TOE, F-07 달성률·목표·실적, F-08 요금·기본요금, E-09/12 원금·소명액·잔액).
  - 계산 근거 패널(`basis-panel`), 결측 제외 문구, 목표 초과 배지 글자 보존.
  - 안내문 `<p className="muted" role="note">` 및 `Loading delay={300}` 공통 규약 정비.
  - `frontend/e2e/layout.spec.ts`에 R 패턴 화면들의 `.page-fill` 미사용 검증 추가.
- 검증:
  - `npm --prefix frontend run typecheck` 통과 (오류 0)
  - `npm --prefix frontend run lint` 통과 (오류 0)
  - `npm --prefix frontend run format:check` 통과 (전체 일치)
  - `npm --prefix frontend run build` 통과
  - `npm --prefix frontend test -- --run` 통과 (43개 테스트 파일 402개 테스트 통과)
  - `git diff --check` 통과 (공백/줄바꿈 이상 없음)
- DB migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 대기. 확인 후 A4(FEMS 기준정보 F-09~11, F-13~14) 진행.

## 2026-09-27 UI-02 A4 FEMS 기준정보 S 패턴 전환 (Antigravity)

- 브랜치: `antigravity/ui02-a4` (기준: `antigravity/ui02-a3`)
- 대상 화면 5개:
  - F-11: `frontend/src/fems/EnergySources.tsx` (`master-grid` 제거, `page-fill` + `split-view` + `FormPanel` + `useDiscardGuard`)
  - F-09: `frontend/src/fems/Sites.tsx` (사업장/공간 두 영역 분리 및 공통 `FormPanel` 등록/수정)
  - F-10: `frontend/src/fems/Equipments.tsx` (`master-grid` 제거, `page-fill` + `split-view` + `FormPanel` + `useDiscardGuard`)
  - F-13: `frontend/src/fems/Factors.tsx` (`DataTable` `leading` 탭, 탭 전환 시 신규 폼 유지 및 `FormPanel` 전환)
  - F-14: `frontend/src/fems/Tariffs.tsx` (`filter-bar` 분리, 긴 폼 스크롤 `FormPanel` 적용)
- 검증:
  - `npm --prefix frontend run typecheck` 통과 (오류 0)
  - `npm --prefix frontend run lint` 통과 (오류 0)
  - `npm --prefix frontend run format:check` 통과 (전체 일치)
  - `npm --prefix frontend run build` 통과
  - `npm --prefix frontend test -- --run` 통과 (43개 테스트 파일 402개 테스트 통과)
  - `git diff --check` 통과 (공백/줄바꿈 이상 없음)
  - `frontend/e2e/layout.spec.ts`에 F-09,10,11,13,14 `.page-fill` 및 에너지원 패널 열기/닫기 e2e 테스트 추가
- DB migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 대기. 확인 후 A5(MES 기준정보 M-02,03,06,08,10~13) 진행.

## 2026-09-27 UI-02 A5 MES 기준정보 및 계획 화면 S 패턴 전환 (Antigravity)

- 브랜치: `antigravity/ui02-a5` (기준: `antigravity/ui02-a4`)
- 대상 화면 8개:
  - M-02: `frontend/src/mes/Plans.tsx` (`FormPanel` 적용, `RevealAnchor` 제거)
  - M-03: `frontend/src/mes/Orders.tsx` (`FormPanel` 적용, `?line=` 프리셋 시 패널 자동 열림 유지)
  - M-06: `frontend/src/mes/Materials.tsx` (`FormPanel title="자재 투입 등록"`, 중첩 form 제거)
  - M-08: `frontend/src/mes/Packing.tsx` (`FormPanel` 적용, 중첩 form 제거)
  - M-10: `frontend/src/mes/Sites.tsx` (사업장/공간 2개 구역 및 `FormPanel` 전환)
  - M-11: `frontend/src/mes/Equipments.tsx` (`FormPanel` S 패턴 전환)
  - M-12: `frontend/src/mes/Items.tsx` (`FormPanel` S 패턴 전환, `RevealAnchor` 제거)
  - M-13: `frontend/src/mes/Processes.tsx` (`FormPanel` S 패턴 전환)
- 내용:
  - React Rules of Hooks 준수: `useDiscardGuard`를 early return (`moduleOff`) 이전에 호출하여 조건부 훅 실행 오류 방지
  - `FormPanel` 내부 중첩 `<form>` 제거로 DOM 유효성 및 submit 이벤트 전달 보장
  - 단위 테스트(`planning.test.tsx`, `master.test.tsx`)에서 패널 오픈 버튼 클릭 후 폼을 조회하도록 수정
  - `frontend/e2e/layout.spec.ts`에 8개 MES 화면 `.page-fill` 검사 및 설비 등록 패널 열기/닫기 E2E 테스트 추가
- 검증:
  - `npm --prefix frontend run typecheck` 통과 (오류 0)
  - `npm --prefix frontend run lint` 통과 (오류 0)
  - `npm --prefix frontend run format:check` 통과 (전체 일치)
  - `npm --prefix frontend run build` 통과
  - `npm --prefix frontend test -- --run` 통과 (43개 테스트 파일 402개 테스트 통과)
  - `git diff --check` 통과 (공백/줄바꿈 이상 없음)
- DB migration / Excel / seed: 변경 없음.
- 다음: A6(ERP 계획·출하·전표·기준정보 화면 E-03, 05, 06, 08, 10, 11, 13, 15~18) 진행.

## 2026-09-27 UI-02 A6 ERP 계획·출하·전표·기준정보 화면 S 패턴 전환 (Antigravity)

- 브랜치: `antigravity/ui02-a6` (기준: `antigravity/ui02-a5`)
- 대상 화면 10개 (11개 메뉴):
  - E-15~18: `frontend/src/erp/Master.tsx` (`Partners.tsx` E-15, `Items.tsx` E-16, `Prices.tsx` E-17, `Accounts.tsx` E-18 공용). `children` prop 지원, `FormPanel` 전환, `Accounts.tsx` split-view + 매핑 이유 aside 패널 결합.
  - E-03: `frontend/src/erp/SalesPlans.tsx` (`master-grid` 및 `RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("판매계획 만들기")`).
  - E-05: `frontend/src/erp/ShipmentOrders.tsx` (`RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("출하지시 만들기")`, 미출하 취소 동작 유지).
  - E-06: `frontend/src/erp/Shipments.tsx` (`RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("출하 확정")`, 수기 패킹번호 동작 유지).
  - E-08: `frontend/src/erp/TaxInvoices.tsx` (등록·발급 두 폼을 `FormPanel` 모드 전환으로 S 패턴 통합, 0원 매출 발급 방지 및 409 안내 유지).
  - E-10·E-13: `frontend/src/erp/Receipts.tsx` (수금·지급 공용 컴포넌트, `master-grid` 및 `RevealAnchor` 제거, `FormPanel` 등록 전환, 409 LIMIT_EXCEEDED 오류 안내 유지).
  - E-11: `frontend/src/erp/PurchaseInvoices.tsx` (`master-grid` 및 `RevealAnchor` 제거, 등록·취소 두 패널을 `FormPanel` 모드 전환으로 통합).
- 내용:
  - React Rules of Hooks 준수: `useDiscardGuard`를 early return (`moduleOff`) 이전에 호출하여 조건부 훅 오류 원천 차단
  - E2E 및 단위 테스트 최신화: 패널 오픈 버튼 클릭 후 폼을 조회하도록 테스트 보강
  - `frontend/e2e/layout.spec.ts`에 전체 ERP 화면 `.page-fill` 검사 및 ERP 거래처 등록 패널 열기/닫기 E2E 테스트 추가
  - **Antigravity UI-02 작업 묶음 A1~A6 (총 37개 화면) 전체 완료** (완료 40, 대기 0, Claude 선행 8, 유지 7 = 총 55개 화면).
- 검증:
  - `npm --prefix frontend run typecheck` 통과 (오류 0)
  - `npm --prefix frontend run lint` 통과 (오류 0)
  - `npm --prefix frontend run format:check` 통과 (전체 일치)
  - `npm --prefix frontend run build` 통과
  - `npm --prefix frontend test -- --run` 통과 (43개 테스트 파일 402개 테스트 전체 통과)
  - `git diff --check` 통과 (공백/줄바꿈 이상 없음)
- DB migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 대기. 확인 후 Claude 선행 8개 화면(F-12, M-04, M-05, M-07, M-14, M-15, E-02, E-04) 진행 대기.

## 2026-09-27 UI-02 Antigravity 결과 검토·회귀 수정·main 통합 (Claude Code)

- Claude 검토(2026-09-27): 공식 스모크를 처음 돌려 11건 실패를 찾았다(Antigravity 묶음 검증에는 스모크 없음). 실제 회귀 5건 수정 — M-06 BOM 제안량 표가 겹침 패널에 가려 채울 수 없음(→ 패널 안으로), M-12 '환산'이 등록 패널을 자동으로 열어 목록을 가림(→ 목록만, 등록은 버튼), E-05·E-06·E-10/13 저장 직후 새 행 선택이 미저장 보호에 막힘(→ 가드 없는 `choose()`), E-18 설명 패널이 표와 겹침(→ main 구조·R 패턴 복원), F-09 인라인 style·정의 없는 `section-block`(→ 공통 `.section-block` 추가). 나머지 6건은 e2e 흐름 갱신. 레이아웃 e2e를 '클래스 존재' → '1440×900 문서 높이'로 강화.
- 검증: typecheck·lint·format:check·build, vitest 402, 스모크 **159 passed**(7.6분, exit 0), 55경로 × 1440·1600·390 전후 비교(가로 넘침·오류 0), S 화면 24개 패널 열기·저장 버튼·Esc(행 선택형 M-06·M-08 포함).
- 통합: `antigravity/ui02-a6` + 검토 커밋(`e8b0d71`·`86e729f`)을 main에 fast-forward. push·서버 배포 전.
- DB migration / Excel / seed: 변경 없음. backend pytest 미실행(백엔드 변경 없음).
- 배포(2026-09-27): origin push `88d584f..0378bf6`, 서버 `git pull --ff-only`(백엔드·마이그레이션 변경 없음 → API 재시작 없음), 맥북 별도 worktree에서 `0378bf6` 프런트 빌드 → rsync. 확인: Cloudflare 경유 200·새 번들 해시 일치·API 5xx 0, 운영 게스트로 F-02·F-05·M-12·E-15 1440×900 문서 900px, F-01 1600 하단 2×2, F-05 패널 열림, 페이지 오류 0.

## 2026-09-27 DOC-01 참고 문서 사이트 설계 (Claude Code)

- 요청: Odoo 18 문서 첫 화면처럼 EIP에 참고 문서 화면. 사용자 확정 — 주 독자 평가자, 스크린샷 제외, 따라하기 대표 1 + 짧은 것 2.
- 산출: `docs/ui/참고문서_DOC-01.md` (P-05 확장). 4구역(설계 8·따라하기 3·기존 참고 54+공통·개념 15), `/help/<키>` URL 유지, manifest 없이 경로·파일명·첫 줄 사용, 참고 트리는 메뉴 배열 `group` 재사용, 번들 내 원문 부분 문자열 검색, 저장소 비공개 전제의 설계 문서 공개 기준, DOC-02~04 분해와 DOC-02 검증 기준.
- 연결: `docs/ui/화면설계_포털_FS-008a.md` P-05에 링크 추가, 현황 문서 13-3 행 추가.
- 검증: 문서 작업. 코드·DB·시드 변경 없음, 테스트 미실행. 저장소 가시성(PRIVATE)·메뉴 group·`/help` 무세션 허용은 코드와 `gh repo view`로 확인.
- 다음: 사용자 확인 후 DOC-02(뼈대 구현).
- UI-03 예외 패턴(2026-09-27, Claude Code): 공통 `DetailPanel`(폼 없는 패널)·`wide`(640px, 1920px 이상 붙음·이하 겹침)를 `SidePanel` 하나로 구현. 기준 화면 — 읽기 전용 상세 M-04, 부모-자식 F-12(채널 상세 ↔ 채널 폼), 넓은 행 편집 E-04(등록·상세·편집), 상태 전이 M-05·M-07(`ResultForm`을 패널로). 규약 8장·적용표(완료 45, Antigravity 대기 3: M-14·M-15·E-02 → 지시서 UI-03 B1·B2).
  - 검증: typecheck·lint·format·build, vitest 402, 대표 화면 5개 × 1920·1600·1440·390 패널 모드·문서 높이·가로 넘침 확인, e2e(layout·fems·mes·portal) 151 passed / 2 failed(F-03 배분 추정·F-01 전월 목표 초과 — 이번에 바꾸지 않은 화면, e2e를 여러 번 돌려 로컬 개발 DB가 바뀐 데이터 의존 실패로 판단). **공식 스모크는 미실행**: 같은 메인 폴더에서 다른 세션(DOC-01)이 동시에 작업 중이라 8000·5173을 점유하는 스모크를 돌리지 않았다.
  - 주의: 이 폴더에서 다른 세션이 동시에 커밋 중(DOC-01 `238a7a0`이 UI-03 WIP 사이에 있음). 스테이징은 경로를 지정한다. push·배포 전.

## 2026-09-27 DOC-02 참고 문서 뼈대 구현 (Claude Code)

- 코드: `frontend/src/portal/docs.ts` 신규(구역·트리·검색·화면 경로), `ContentPages.tsx` Help 교체(첫 화면: 쪽빛 띠·검색·구역 카드 / 문서 화면: 트리·경로·본문·목차·이전/다음·이 화면 열기), `shared/content.tsx` `##` 제목 id, `styles.css` `.doc-*` 추가·옛 help 클래스 삭제, `.button.secondary` 선택자 추가.
- 트리는 메뉴 배열 `group` 재사용. manifest·frontmatter·검색 라이브러리 없음. 문서 없는 구역은 숨김(임시 문서 없음 — DOC-01 §8 수정).
- 검증:
  - typecheck·lint·format:check 통과, vitest **44파일 410개 통과**(신규 docs.test 5, content-pages P-05 4개 교체·추가).
  - build 통과. 메뉴 배열은 별도 1.4kB 청크로만 들어와 업무 화면 코드가 Help 청크에 딸려 오지 않음. Factory 924kB 경고는 기존.
  - Playwright(실행 중인 dev 서버 5173/8000 대상, 임시 설정): portal.spec 중 도움말·흐름 관련 5개 통과 — 신규 "참고 문서 ↔ 업무 화면 왕복"(검색 → E-09 → 이 화면 열기 → `? 도움말` → 트리 현재 항목), 360px `/help` 가로 스크롤 없음.
  - 브라우저 확인: 1440 첫 화면·문서 3단, `?q=소명` 제목 일치 우선, 390px `/help/mes/m-04` 가로 넘침 0·트리 접힘.
- **미실행:** 공식 스모크(`tools/run_portal_smoke.py`) — 다른 세션(UI-03)의 dev 서버가 5173/8000을 점유 중이라 돌리지 않았다. portal.spec 전체와 나머지 spec도 미실행. 배포 전 공식 스모크 필요.
- 배포 보류: 설계·따라하기·개념 문서가 없어 첫 화면에 구역 하나만 보인다. DOC-03·04 후 배포.
- 다음: 사용자 확인 후 DOC-03(따라하기 3 + 개념 15).
- UI-03 스모크·배포(2026-09-27): 공식 스모크 **164 passed**(7.7분, exit 0 — 로컬에서 실패하던 F-03·F-01도 통과, 데이터 의존 실패 확인). origin push `6e22e00..a35e895`(DOC-01·DOC-02 포함), 서버 pull(백엔드 변경 없음, API 재시작 없음) → `a35e895` 프런트 빌드·rsync. 확인: 새 번들 해시 일치·200·API 5xx 0, 운영 게스트 1920×1080에서 M-04·F-12·E-04 넓은 패널(640) 붙음, M-05·M-07 패널(380), 문서 1080px, 오류 0.

## 2026-09-27 UI-03 B1 공정 경로·BOM F-12 부모-자식 패턴 적용 (Antigravity)

- 브랜치: `antigravity/ui03-b1` (기준 커밋: `24179d1`)
- 대상 화면 (2개):
  - M-14 공정 경로(`frontend/src/mes/Routes.tsx`): 경로 버전 목록 → 단계 목록 `DetailPanel wide` → 단계 폼 `FormPanel`(닫으면 단계 목록으로). 게시한 버전 불변(수정·삭제 버튼 없음, 개정=새 버전), '개정'·'게시' 동작 유지, `RevealAnchor` 제거.
  - M-15 BOM(`frontend/src/mes/Boms.tsx`): BOM 목록 → 자재 라인 `DetailPanel wide` → 라인 폼 `FormPanel`. 게시한 버전 불변, 개정 시 새 코드 입력 `FormPanel`, `RevealAnchor` 제거.
- 테스트 및 레이아웃:
  - `frontend/src/mes/versions.test.tsx`: BOM 라인 폼 전환에 맞추어 테스트 접근자(`자재`, `단위`, `소요량(1개당)`, `추가`) 갱신 (8 tests passed).
  - `frontend/e2e/mes.spec.ts`: 공정 경로 개정 흐름 갱신(패널 열림 확인 → 순서 편집 → 저장 → 패널 닫기 후 목록에서 게시).
  - `frontend/e2e/layout.spec.ts`: M-14 공정 경로 단계 패널 및 M-15 BOM 자재 패널 1440×900 문서 높이 ≤ 900 및 Esc 닫기 검사 추가.
- 검증:
  - `npm --prefix frontend run typecheck` 통과 (오류 0)
  - `npm --prefix frontend run lint` 통과 (오류 0)
  - `npm --prefix frontend run format:check` 통과 (전체 일치)
  - `npm --prefix frontend run build` 통과
  - `npm --prefix frontend test` 통과 (44개 파일, 410개 테스트 전체 통과)
  - `git diff --check` 통과 (공백/줄바꿈 이상 없음)
  - `uv run --project backend --env-file .env python tools/run_portal_smoke.py` 공식 스모크 통과 (**166 passed**, 8.0분, exit 0)
- DB migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 대기. 확인 후 UI-03 B2 (E-02 견적 넓은 행 편집 화면) 진행.

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


## 2026-09-27 P-02 홈 UI 정돈 (Codex)

- 사용자 Figma 코드/이미지를 시각 참고로 적용. 흰색 홈 헤더·F 마크·중앙 본문·흰색 흐름 배너·저채도 타일. MES/ERP/FEMS 이름·분류만 기본 표시.
- 설명·사용 상태는 호버/키보드 포커스/터치 안내 버튼으로 제공(Esc 닫기). 하단 미구현 목록은 홈에서 제거. 기존 진입·공간/세대·도움말·역할별 메뉴 유지.
- `origin/main 8851772`에서 `codex/home-ui-polish` 분기. 기존 3D 브랜치 보존, 업무/3D/공통 styles.css/backend/DB 변경 없음. 새 의존성 없음.
- Node 24.21.0: typecheck·lint·format:check·build·전체 테스트(418 passed), 독립 Chromium 홈 테스트 8개 및 diff --check exit 0. 데스크톱 기본/hover·360px 직접 확인. 검증 상세 `docs/agent/홈_UI_정돈.md`.
- 공용 통합 스모크·backend/DB 미실행. 5187·모의 API만 사용. push/main 병합/배포 없음. 다음: 사용자 시각 확인 및 통합 담당자 반영.
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

## 2026-09-28 FS-FACTORY-CONCEPT01 — 정밀 부품 공장 컨셉 완료

- 사용자 요청한 6단계 중 1단계 문서 완료. Factory Studio 유지, 정밀 부품 가공 공장 / 로봇 연동 CNC 가공 셀, CNC → 비전검사 → 포장으로 후속 기준 확정.
- 상세: [컨셉과 개발 기준](plan/정밀부품공장_컨셉_FS-FACTORY-CONCEPT01.md). 제품은 설비용 알루미늄 마운팅 블록. 기존 MTS·독립 솔루션·업무 데이터 소유 경계 유지. 기존 MES 시드와 신규 3D 시연의 차이를 명시.
- WMS README의 오래된 core 마스터 소유·MES 원장 이관 설명 수정. 신규 WMS·자동화·JSON 복원·지도는 미구현.
- 검증: 현재 코드/설계 대조, 문서 링크와 diff 공백 확인. 문서만 변경해 기능/브라우저 테스트 미실행.
- 다음: 2단계 FS-FACTORY-CNC01의 로봇·CNC 형상/상태/정지·복구 및 이름 적용. 6단계 중 1단계 문서 완료이며 구현 공수 진행률 아님. push·배포 없음, 운영 배포 사용자 담당.

## 2026-09-28 FS-FACTORY-CNC01 — 로봇 연동 CNC 가공 셀 완료

- 신규 로드맵 2단계 로컬 구현 완료. 첫 조립 설비를 로봇·그리퍼·CNC 인클로저·문·지그·주축으로 교체. 소재 투입 → 가공 → 배출, 사각 원소재/포켓·구멍 가공품, CNC 이름·현장 표지 적용.
- 시작당 1개, 일시정지/재개, 오류 래치·명시적 해제/재개, 종료 소재 보류, 완료 중복 방지. 모의 인터락, 탭 숨김 정지·언마운트 타이머 정리. 모델/패널이 같은 상태를 사용한다.
- 넓은 화면 CNC 패널 옆 칸 배치, 근접 카메라·충돌 영역 반영. 사용자 참고 문서 `/help/portal/cnc-cell`과 패널 링크 추가.
- 최종 프런트 **456 tests / 52 files**, typecheck(빌드)/lint/format/build 통과. Chromium 전체 실행은 21 passed·1 skipped·1 failed: 편집 중 HMR로 초기화된 1인칭 1건은 수정 없이 재실행 통과(그래픽 손실 포함 최종 재실행 2 passed). **고유 브라우저 시나리오 22개 검증**, 실제 C++ API 1건은 이번 환경에서 제외. CNC 정상/정지/오류/보류·390px·검사실 진입·새 도움말 포함.
- 1280px 완료 화면·390px 패널 캡처 직접 확인. 문서 링크/diff 공백 통과. 기존 3D 청크 크기·THREE.Clock 경고 유지. DB/백엔드/실장비/운영 배포/Safari 검증 미실행.
- CNC 실적은 메모리 전용이며 비전/C++/MES/WMS와 미연계. 기존 MES 시드·DB·API 변경 없음. 절삭 물리·실제 안전 제어 아님.
- 상세: [구현 및 인계](agent/로봇CNC가공셀_FS-FACTORY-CNC01.md). 기준 aac8d26, 브랜치 codex/vision-ai. push·main 병합·배포 없음. 운영 배포 사용자 담당.
- 다음: **3단계 WMS 공통 설계 후 입고·재고·출고·LOT 연결**. 6단계 중 2단계 완료(공수 비율 아님). 자동 운전/JSON 복원/지도는 후속.

## 2026-09-28 FS-026 단계 0 — 최신 main 정렬 완료

- 사용자 지시에 따라 `codex/vision-ai`를 `origin/main` b9dfbc4(FS-025b API 포함)에 rebase했다. CNC 컨셉/구현은 01fc6f5·7b94b48로 재적용했다. 충돌 난 현황·HANDOFF·WMS README는 main 기준을 유지하고 이 항목으로 후속 이력을 보완했다.
- `fad0c3a`는 rebase에서 제외했다. 이전 설계는 `backup/vision-ai-before-fs026-20260928`에 참고용으로만 보존하며 현 브랜치/향후 main 병합 대상에 포함하지 않는다. FS-WMS-DB01은 시작하지 않는다.
- 현재 기준은 FS-024 WMS 6테이블·W-01~07·기존 원장과 FS-025까지의 main이다. 기존 CNC 알루미늄 블록 시연은 메모리 전용이며 WMS 품목 추가 승인이 아니다. 과거 문서의 신규 WMS 개발/미구현 안내는 현재 기준으로 사용하지 않는다.
- 현황, FS-013, 문서 지도, FS-024 결정서·모듈 설계·화면 설계와 backend/src/fs/wms를 확인했다. 원장은 stock_move 합계, source_key로 원천 중복 방지, ERP 매입 취소는 반대 부호 전표, 가용은 현재고−ERP 미출하 지시다. 원자재는 LOT 없이 KG/EA 및 단위 환산을 유지한다.
- 검증: frontend typecheck 통과, CNC/useCnc/WMS 관련 3파일 14테스트 통과, 격리 R1~R6 오류 0(93테이블·209FK), diff 공백 검사 통과. 전체 테스트·브라우저·실제 DB 마이그레이션은 실행하지 않았다. WMS/BEMS 제품 코드·DB 명세·시드는 origin/main 그대로다.
- 다음은 **사용자 0단계 확인 후** FS-026 결정서 작성(D24부터). D13·D17 개정, D14 중복 입출고 방지와 취소 처리, D15 음수/예약 부족 경계, 격리 위치 유형, 트럭 도착 무재고 변경, 기존 품목 및 알루미늄 품목 여부를 질문·권장안으로 정리한다. 결정서·모듈 설계·개발 단계는 아직 시작하지 않았다.
- 후속 전체 설계 승인 후에만 새 migration을 추가한다(현재 head fs025b_bems_module 다음). 업무 간 FK 금지·교차 조회 interface.py만 유지. push·배포 없음. `.env`·`work/` 스테이징 없음.

## 2026-09-28 FS-026 단계 1 — 결정서 초안 작성 완료·승인 대기

- 사용자 단계 0 확인 후 결정서 `docs/plan/WMS확장_입고검수예약_결정_FS-026.md` 작성. D24~D32와 Q1~Q6 권장안이며 세부 정책은 아직 미승인이다. 입고 예정·도착·검수·격리·예약 추가와 D13·D17 개정 방향만 사용자 확정이다.
- D14 보완: ERP 매입 직접 반영/검수 경유의 원천 선점·상호 배타, 수동 기입고 사후 대사(원장 0), 전량 부족, 회계 취소와 실물 정정 분리. D17 대체안: WMS 예약만 가용에서 차감하고 ERP 미출하는 참고 지표. D15의 원천 반영 음수 허용과 신규 예약 부족 거부를 구분했다.
- 격리는 기존 storage_location 유형으로 제안. 트럭은 도착 상태만 변경. 예약은 명시적 ERP 출하 전량 연결 시 원장 차감과 함께 소진하며 별도 출고 차감은 추가하지 않는 안이다. 기존 5품목/단위·LOT 정책 유지, 알루미늄 품목 시드는 제외 권장.
- 검증: FS-024 결정/설계 및 WMS·ERP interface 코드 정적 대조, D24~D32 연속/중복 없음·질문 6개·상대 링크 존재·git diff --check 통과. 문서만 변경하여 기능/브라우저/DB 테스트는 재실행하지 않았다.
- 다음: Q1~Q6 사용자 확인 후 단계 2(모듈 설계 새 revision·화면·AC-139부터). 전체 설계 승인 전 제품 개발/마이그레이션 금지. FS-WMS-DB01 시작 금지. 기존 확정 FS-024 정책은 아직 덮어쓰지 않았다.
- 위치 factory-studio-codex / codex/vision-ai, 기준 4aa1fc7. origin/main 기준 b9dfbc4, 완료 커밋은 git log -1로 확인. `.env`·work/ 스테이징 없음. push·배포 없음.

## 2026-09-28 FS-026 단계 2 — 모듈·화면 설계 revision 2 작성, 전체 확인 대기

- 사용자 “진행해줘”로 결정서 Q1~Q6 권장안/D24~D32 승인 기록. 모듈 `docs/modules/wms/WMS_모듈설계_FS-026.md`, 화면 `docs/ui/화면설계_WMS_FS-026.md` 작성. 기존 FS-024 문서는 이력으로 보존하고 후속 링크를 추가했다.
- 기존 6테이블 재사용 + inbound_notice/inbound_notice_line/source_claim/stock_reservation/stock_reservation_line 5개 추가(계획 총11). location_type 및 WMS_INSPECTION 전표 유형 차분, source_claim과 기존 전표의 공간 락 내 검사로 이중 입고 방지. 전량 부족은 전표 없이 처리 완료를 보존한다.
- TX-W4~W9, version/멱등/영구 중복키, ERP interface 읽기 계약, 신규 API, 기존 stock/dashboard 가용 의미 개정, 게스트 복사/번호·snapshot digest 재계산을 정의했다. 실제 ERP 출하지시 상태는 open/shipped/cancelled다.
- 기존 W-01~07 확장 + W-08 입고 예정·검수/W-09 출고 예약 + 3D 트럭 도착 패널. AC-139~164 26개 작성(미실행); 기존 AC-123 대체, AC-114/118 적용 경계 명시.
- 검증: 설계 상대 링크 존재, AC 번호 연속·중복 없음, 신규 테이블 5개, diff 공백 검사 통과. 문서만 변경하여 DB/기능/브라우저 테스트 미실행. migration·schema.json·DB설계서.xlsx·운영 ERD·제품 코드·시드 변경 없음.
- 다음: **사용자 전체 설계 확인 후에만** FS-026a(DB/메타데이터/Excel/ERD/검증) 착수. 현재 head fs025b_bems_module 뒤 새 revision 제안, 착수 시 head 재확인. 적용 migration 수정 금지. FS-WMS-DB01 금지, fad0c3a는 참고만.
- 브랜치 codex/vision-ai, 기준 3b51671. 최종 커밋은 git log -1로 확인. `.env`·work/ 스테이징 없음. push·배포 없음.

## 2026-09-28 FS-026a — WMS 확장 DB 기반 완료

- 사용자 전체 설계 승인 및 질문 권장안 진행 지정. 기존6+신규5 WMS 테이블, 위치 유형/검수 전표, metadata v0.13.0(전체98/1022컬럼/225FK), 새 revision fs026a_wms_receiving_reservation 구현. 이전 migration 수정 없음.
- DB설계서31시트·ERD·검증기/보고 동시 갱신. NULL LOT 부분 유니크, 검수수량/상태 CHECK, 원천 유효선점·소진 유일성. 데이터가 있는 downgrade는 중단한다. SERVICE 정책/API/화면은 후속 미구현.
- 검증: DDL대조0·R1~R6오류0, 이전head/빈base downgrade→upgrade 통과. 기존WMS15+신규DB7+DDL변조9+시드16 = 고유 선택47 tests 통과. DDL변조1건은 시드가 남은 DB에서 실패하여 빈 DB 재실행9건 통과. tools58, Ruff/diff 통과. 전체/브라우저 회귀 미실행.
- 전용 로컬 테스트DB2개만 적용. 공유 개발/운영DB·시드 품목 변경 없음. origin/main489d5f3의 migration head가 fs025b_bems_module 그대로임을 확인했고 새 BEMS UI는 이번 브랜치에 rebase하지 않았다.
- 다음 FS-026b API(입고/원천선점/검수/예약·가용/출하연결·동시성), 이후 화면·트럭·도움말·시드. 세부 선택은 승인 권장안. push·배포 없음, .env/work 스테이징 없음.
- 상세: docs/agent/WMS확장_DB_FS-026a.md. 브랜치 codex/vision-ai, 기준01b6cce, 완료커밋 git log -1.


## 2026-09-29 FS-026b1 WIP
- main6508599 rebase 완료(main HANDOFF 유지), BEMS 포함 템플릿11,910 기준 유지.
- 입고 예정/도착/검수/원천선점 API 작성, 기존 원천 sync 연결, 날짜 제외 digest와 게스트 복사 처리. 입력400/멱등422 설계 수정.
- 실제 DB 신규 테스트 진행 중. 전체 회귀/ruff/격리 감사 미완료. b2는 b1 보고 확인 후.
