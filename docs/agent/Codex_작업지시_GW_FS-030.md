# Codex 작업 지시 — GW 그룹웨어 (FS-030)

작성: 2026-10-01 (Claude Code, 사용자 지시 "GW는 코덱스에게 따로 맡긴다")
기준: main `67540be` 이후(FS-026 WMS 확장·FS-028a/b SPC 포함). **새 main에서 새 브랜치 `codex/fs-030-gw`로 시작한다.**

아래 "프롬프트" 절을 Codex에 그대로 붙여 넣는다.

---

## 프롬프트

너는 Factory Studio 저장소에서 **GW(그룹웨어) 솔루션**을 새로 설계·구현한다. 작업 ID는 **FS-030**이다. 다른 작업자(Claude Code)가 같은 시기에 SPC 마무리(FS-028c)와 CMMS(로드맵 2번)를 진행하므로, 아래 번호 범위와 경계를 반드시 지킨다.

### 0. 작업 위치와 Git

- 작업 폴더는 `/Users/hwang-kyoungho/projects/factory-studio-codex`만 쓴다. 메인 폴더(`factory-studio`)는 열거나 수정하지 않는다.
- `git fetch` 후 **origin/main 최신**에서 `codex/fs-030-gw` 브랜치를 만든다. 예전 `codex/vision-ai`는 main에 병합이 끝났다. 거기서 이어 쓰지 않는다.
- push·운영 배포는 하지 않는다. main 병합은 사용자 확인 뒤 Claude Code가 한다.
- 30분마다 WIP 커밋을 한다. `.env`·`work/`는 스테이징하지 않는다. `git add`에는 파일을 지정한다.

### 1. 먼저 읽을 것(이 순서)

1. `AGENTS.md`
2. `docs/plan/현재기획_진행현황.md`
3. `docs/plan/로드맵_17개시스템_ROADMAP-01.md` — 특히 §1 상태 표, §3 공통 규칙, **§6-3 EIP·GW·포털 경계(확정)**
4. `docs/plan/새솔루션_킷.md` — 새 솔루션 한 사이클의 체크리스트(이 문서대로 진행한다)
5. `docs/plan/독립솔루션_전환결정_FS-013.md` §6, `docs/plan/QMS도입_교차조회_결정_FS-023.md` D9~D12(교차 조회 규칙)
6. 참고 사례: SPC `docs/plan/SPC도입_관리도_결정_FS-028.md` · `docs/modules/spc/SPC_모듈설계_FS-028.md` · `docs/ui/화면설계_SPC_FS-028.md`(가장 최근에 같은 절차로 만든 솔루션)
7. 이웃 계약: `docs/modules/erp/README.md` 맨 위 "제공 조회 함수"

### 2. 확정된 범위(로드맵 §6-3)

- **GW = 전자결재·게시판.** 스키마 `gw`, 모듈 키 `gw`, 라우트 `/gw/*`, API `/api/v1/gw`.
- **EIP(로드맵 9번)는 전사 요약 대시보드·공지**이고, 포털(core)은 인증·앱 런처만 맡는다. GW에 전사 대시보드를 만들지 않는다. **core에 업무 테이블을 넣지 않는다.**
- 결재 대상 예시는 **ERP 문서**(예: 매입 전표·견적·출하지시)다. GW는 ERP 문서를 **코드 스냅샷**(문서 종류·번호·금액·거래처)으로 받아 결재선·결재 이력을 기록한다.
- **교차 쓰기 금지**: GW는 ERP를 바꾸지 않는다. 결재 결과로 ERP 확정을 막거나 진행시키지 않는다. ERP가 필요하면 `fs.gw.interface`를 읽어 "결재 상태" 배지만 보여 준다(QMS의 "SPC 이상" 배지와 같은 방식, FS-028 D44 참고). ERP 배지를 이번 사이클에 넣을지는 결정서에서 사용자에게 묻는다.
- ERP에서 읽을 값이 없으면 `fs/erp/interface.py`에 **읽기 전용 함수만** 추가한다. ERP는 동결 상태이며, 동결 중에도 조회 함수 추가는 허용된다(로드맵 §3). 추가하면 `docs/modules/erp/README.md` "제공 조회 함수" 표를 같은 커밋에서 갱신한다.
- 게시판: 공지·자유 게시판 수준(글·댓글·첨부 없음). 사용자 계정은 core 인증만 쓴다. 게스트 공간마다 체험 데이터가 있어야 한다(합성 데이터만).

### 3. 진행 절차 — 단계마다 멈추고 보고한다

1. **결정서** `docs/plan/GW도입_전자결재_결정_FS-030.md` — 배경, 결정 표, 교차 조회, 바뀌는 문서·값, 하지 않는 것, 승인 요청. **여기서 멈추고 사용자 승인을 받는다.**
2. **모듈 설계** `docs/modules/gw/GW_모듈설계_FS-030.md` + `docs/modules/gw/README.md`(맨 위 "현재 기준"), **화면 설계** `docs/ui/화면설계_GW_FS-030.md`(화면 6~7개, UI-02 패턴만 사용, 새 패턴 금지). **전체 설계 확인을 받기 전에는 schema.json·마이그레이션·코드를 만들지 않는다.**
3. **FS-030a DB**: `tools/apply_fs030a.py`(멱등) + `tools/test_fs030a.py`, 마이그레이션 2개(`fs030a_gw` 스키마, `fs030b_gw_module` 모듈 행). 새 솔루션 킷 a의 "스키마 목록이 박혀 있는 곳"을 전부 고친다. `validate_db_design.py`의 작업 ID 집합에 FS-030a를 넣고, `validate_gw`를 추가한다.
4. **FS-030b API·화면**: 킷 b 목록 전체(라우트·홈 타일·아이콘·진입 목록·참고 문서·다른 솔루션 전환 링크·`content/systems.json`의 gw `status`/`to`·e2e).
5. **FS-030c 시드·도움말·통합 검증**: `seed/generate.py`의 `_gw`, `validate.py`, 도움말 `content/help/gw/g-01~`, 흐름 맵 노드, 전체 검증.

### 4. 번호·이름 범위(충돌 방지 — 꼭 지킨다)

| 항목 | GW(FS-030, Codex) | 참고: Claude 쪽 |
|---|---|---|
| 결정 번호 | **D60~D69** | SPC D37~D44, CMMS는 D45부터 |
| 수용 기준 | **AC-220~AC-239** | SPC AC-170~184, CMMS AC-185부터 |
| 화면 접두어 | **G** (`G-01`~) · 도움말 키 `gw/g-01` | SPC `S`, CMMS `C` 예정 |
| 스키마 버전 | 작업 중에는 **v0.15.0-gw**로 표기하고, main 병합 때 Claude가 최종 번호로 맞춘다 | 현재 main v0.14.0 |
| 마이그레이션 | `down_revision`은 작업 시작 시점 main의 head(현재 `fs026a_wms_receiving_reservation`). main에 새 head가 생기면 병합 전에 rebase하고 down_revision을 옮긴다 | — |

### 5. 지켜야 할 규칙(자주 틀리는 곳)

- 업무 FK는 `(workspace_id, generation_id, 참조 id)` 복합 참조, 삭제는 RESTRICT. **다른 업무 스키마로 FK 금지**(격리 검사 R1·R6).
- 연·월·주차 컬럼은 `'YYYY-MM'` 같은 문자열 + 형식 CHECK. 컬럼 이름이 `effective_from`·`effective_to`·`period_from`·`period_to`·`*_month`·`*_year`·`*_week`면 검증기가 달력 문자열로 검사한다. 시각이면 다른 이름(`*_at`)을 쓴다.
- 확정·결재 완료된 기록은 바꾸지 않는다. 정정은 새 기록(반려 후 재상신 등)으로 한다.
- 시각 비교를 DB 시계와 API 시계 사이에 걸지 않는다(SPC에서 몇 초 차이로 판정이 빠진 사례). 업무 기준일(`FS_TODAY`)과 실제 시각은 다를 수 있다.
- **게스트 생성 테스트는 `json={"nickname": …}` 필수**, e2e 진입은 `page.getByLabel("별칭").fill(...)` 후 "가입 없이 둘러보기"(FS-027).
- 새 화면 CSS 클래스에는 `gw-` 접두어를 붙인다(전역 `.excluded` 충돌 사례).
- 홈은 분야별 묶음이다(`content/systems.json`의 `field`). GW는 "경영·협업" 묶음에 들어간다. 솔루션 수 문구는 자동이니 고치지 않는다.
- 테스트 DB는 **`factory_studio_codex_test` 등 Codex 전용 DB만** 쓴다. 공용 개발 DB(`factory_studio`)·Claude 테스트 DB(`*_fs016_test`·`*_fs017_test`·`*_fs028_test`)·운영 DB는 건드리지 않는다. 스모크(8000·5173)는 Claude와 동시에 돌리지 않는다.

### 6. 단계별 보고에 넣을 것

작업 ID, 바뀐 파일, 실행한 검증과 실제 결과(통과 수·exit code), **실행하지 않은 검증**, 남은 일. 미실행 검증을 완료로 적지 않는다. 각 단계 끝에 `docs/plan/현재기획_진행현황.md`(200줄 이내 유지)·`docs/progress.md`·`docs/agent/HANDOFF.md`를 갱신한다.

### 7. 2026-10-03 방침 변경 (ROADMAP-02)

- **FS-030b(API·화면)만 끝까지 마치고 보고한다.** Claude가 main에 병합한다.
- 그 뒤 GW는 FS-030c(시드·도움말)로 가지 않는다. 전체 설계 우선 단계로 전환한다 — [ROADMAP-02](../plan/전체설계우선_전환_ROADMAP-02.md). GW 기능 기준표·목표 DB(`schema-target.json`)·화면 목록은 DSN-00 양식이 나온 뒤 따로 지시한다.

### 8. 2026-10-05 EIP 설계(DSN-28)에서 GW에 넘긴 것

- `gw.person`에 `hr_employee_code`(HR 사원 코드 스냅샷, NULL 허용) — 목표 DB(`schema-target.json`)에 반영됨. EIP "내 할 일"이 결재 대기를 사람별로 묻는다.
- 조회 함수 추가 계약: `published_notices(limit)`(EIP 공지 표시 — EIP 자체 공지 없음), `pending_tasks(hr_employee_code)`, `lookup(code)`. 개발은 일괄 개발 때.

### 9. 2026-10-05 DSN-90 통합 검증 뒤 GW 확장(GW-EXT)에 대한 결정·요청

> **같은 날 D82: Codex 업무 중단 → 아래 2~4는 Claude가 DSN-31로 수행한다.**

결정(ROADMAP-02 **D81**, [DSN-90 7-1](../plan/통합검증_DSN-90.md)) — `codex/fs-030-gw` `08c91d9`는 main에 병합했다.

1. **사람·조직 원천은 HR**(`docs/modules/hr/HR_설계_DSN-30.md`). GW-EXT A의 `organization_unit`·`person_assignment`는 HR `departments()`·`employees()`를 "HR에서 가져오기"한 스냅샷(부서 코드·사원 코드 = HR 코드, 문서 권한 판정용)으로 고친다. GW-EXT D단계의 인사 기초·근태·휴가는 빼고(HR 소유), GW D는 일정·채팅만. 계정 ↔ 직원 연결(`person_identity_binding`)·`role_grant`·문서 권한은 GW 그대로.
2. **GW 설계를 같은 양식으로**: [DSN-00](../plan/기능기준표_DSN-00.md) 기준표(GW 전체 기능, 범위 ○/✕) + `tools/apply_dsn31.py`로 목표 DB(`docs/db/schema-metadata/schema-target.json`)에 core TEAM 공간 3 + GW 7 테이블·기존 표 변경을 반영한다. `tools/rebuild_target.py` STEPS에서 `apply_dsn30` 다음·`apply_dsn90` 앞. 검증기 `validate_gw_dsn31` + `test_dsn31`. 검증 5종(`validate_db_design --schema …target`·`audit_schema_isolation`·`schema_ddl --apply`·`build_erd --target`·`build_db_design --target`)과 `test_dsn*`·`test_fs0*` 통과를 커밋 조건으로.
3. **교차 조회 계약**은 [DSN-90 2장](../plan/통합검증_DSN-90.md)이 기준본이다. GW 제공: 기존 `approvals(doc_ref)`, `published_notices(limit)`(권한 필터), 공통 4종 `enabled`·`monthly_summary`·`pending_tasks(hr_employee_code)`·`lookup(code)`. GW 읽기: HR `employees`·`departments`.
4. 끝나면 Claude가 GW 부분만 DSN-90 재검증 → DSN-99.

