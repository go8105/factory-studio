# FS-019 ERP · FS-020 MES 작업 계획과 인계 프롬프트

작성일: 2026-09-25 · 작성 Claude Code · 기준 main `70951d4` (FEMS 13/14)

이 문서는 FEMS 마지막 화면(F-09)을 진행하는 동안 **Codex가 ERP·MES를 이어받을 수 있도록** 작업 순서·분배·병행 규칙·프롬프트를 정한다. 설계 근거는 아래 문서이며, 이 문서와 충돌하면 설계 문서가 우선한다.

| 영역 | 근거 문서 |
|---|---|
| 화면 | `docs/ui/화면설계_ERP_FS-008a.md` (18화면), `docs/ui/화면설계_MES_FS-008a.md` (15화면) |
| 모듈 | `docs/modules/erp/ERP_모듈설계_FS-005e.md`, `docs/modules/mes/MES_모듈설계_FS-005f.md` |
| API | `docs/architecture/API계약서_FS-010.md` §8 ERP, §9 MES |
| 트랜잭션 | FS-006(TX-01·02), FS-006a(TX-07~11, 락 순서), FS-006b(계획·패킹출하), FS-014b(회계 7단계 잠금·소명·취소) |
| 스키마 | `docs/db/schema-metadata/schema.json` v0.9.1 (erp 27 · mes 21 테이블). **변경 금지** |
| 규약 | `AGENTS.md`, `docs/architecture/개발규약_FS-011.md`, `docs/plan/구현인계패키지_FS-012.md` §4~6 |

---

## 1. 분배 (제안)

| 담당 | 작업 | 이유 |
|---|---|---|
| **Claude Code** (메인 폴더) | F-09 사업장·공간 → FS-018 종료 보고 → **FS-020 MES** | FEMS 패턴을 만든 쪽이 가장 가까운 MES로 옮긴다 |
| **Codex** (`../factory-studio-codex`, `codex/*`) | 테스트 시간 단축(conftest) → **FS-019 ERP** | ERP는 회계 7단계 잠금·소명 한도·취소 규칙 등 SERVICE 정책과 동시성 검증 밀도가 가장 높다(AGENTS §8 Codex 역할) |
| antigravity (선택) | ERP·MES 기준정보 화면 테스트 보강·도움말 문구 정합 | 사용자가 배정할 때만 |

FS-012 §3: ERP와 MES는 코드가 서로를 참조하지 않으므로 병렬 가능하다. **1인 운영으로 순차가 필요하면 Codex가 FS-019 → FS-020 순으로 모두 맡는다.**

## 2. 전체 순서

```
지금 ─ Claude: F-09 (fs-018m-f09) ────────┐
      Codex : conftest 단축 (codex/test-speed) ─┤→ 먼저 끝난 쪽 main ff, 나중 쪽 rebase
                                               ↓
      Codex : FS-019a → b → c → d → e → f → g → h   (ERP)
      Claude: FS-018 종료 보고 → FS-020a → b → c → d → e → f → g   (MES)
                                               ↓
      FS-021 통합 검증 (SERVICE 정책 7건·동시성·AC) → FS-022 배포
```

- 각 하위 ID는 **하나씩** 끝내고 보고 → 사용자 확인 → push → CI 통과 → main ff. 확인 전 다음 ID를 시작하지 않는다.
- conftest 단축은 FEMS 테스트 fixture를 건드린다. **ERP·MES 테스트 파일이 늘기 전에** 먼저 병합하는 것이 싸다.

## 3. FS-019 ERP 분해 (Codex)

| ID | 화면 | 핵심 규칙 | 완료 조건(공통 외) |
|---|---|---|---|
| **019a** | 뼈대 + E-15 거래처 · E-16 품목(단위환산) · E-17 거래처별 단가 · E-18 계정과목·분개규칙(읽기) | `fs/erp/{router,service,repository,schema}.py`, `main.py`에 `/api/v1/erp`, `frontend/src/erp/` + App 라우트 + ERP 사이드바. E-16 상단 "MES 품목과 독립" 안내. 단가 적용 구간 겹침 거부. 삭제 RESTRICT + 건수 | 사이드바·도움말 연결, 기준정보 CRUD 테스트 |
| **019b** | E-02 견적 · E-03 판매계획 · E-04 수주 | 견적 개정은 행 누적, 최신 = `MAX(revision_no)` 파생(플래그 저장 금지, E-G03). 판매계획 확정 불변. MES 사용 여부를 모른다는 단방향 안내(E-G06) | 개정 이력 조회, 확정 후 수정 409 |
| **019c** | E-05 출하지시 · E-06 출하 | TX-07·TX-08. `shipment_line.packing_no`는 수기 코드(FK 없음, 오타 한계 안내 E-G04) | 락 순서 테스트 |
| **019d** | E-07 매출 · E-08 세금계산서 | TX-09. **채권은 매출 인식과 같은 트랜잭션에서 파생.** 세율 10% 상수(E-G01, 코드에 박혀 있음을 문서화). 매출 취소는 소명 0행 전제, 발급대기 계산서 함께 삭제, 발급완료면 취소 금지. **E-G07(0원 매출 발급) 미정 → 착수 전 질문** | 취소 규칙 테스트 |
| **019e** | E-09 매출채권 현황 · E-10 수금 등록·소명 | 잔액 = 원금 − Σ소명(저장 금지), 상태 OPEN/PARTIAL/CLOSED 파생. 7단계 잠금(채권 → 수금 → 소명, id 오름차순). 잠금 뒤 합계 재계산으로 수금액·원금 양쪽 한도, 초과 시 전체 롤백 + 어느 채권인지. FIFO는 버튼 제안만. 과입금 허용(미소명). 소명 취소 = 물리 DELETE + audit_event | **동시성 주입 테스트**(두 소명이 한도를 넘지 못함) |
| **019f** | E-11 매입 전표 · E-12 매입채무 · E-13 지급·소명 | 019d·e의 대칭. 채무는 매입 확정과 같은 트랜잭션. 매입 취소는 소명 조건만 | 대칭 테스트 |
| **019g** | E-14 분개 미리보기 | 4거래 유형·7계정·10규칙, 수금/지급 소명 1행당 분개 1세트. **결과·전표·원장 저장 금지**, 미소명 잔여는 표 밖 안내 | 규칙별 금액 테스트 |
| **019h** | E-01 대시보드 | 앞 화면의 계산을 재사용(두 번 구현하지 않는다). 만기 NULL은 "미설정" 그룹(E-G02) | 다른 화면 값과 일치 테스트 |

## 4. FS-020 MES 분해 (Claude Code, 순차 운영이면 Codex)

| ID | 화면 | 핵심 규칙 |
|---|---|---|
| **020a** | 뼈대 + M-10 사업장·공간 · M-11 설비 · M-12 품목 · M-13 공정 | `/api/v1/mes`, `frontend/src/mes/`. **FEMS 사업장·설비와 독립 데이터**(코드가 같아도 별개) 안내 |
| **020b** | M-14 공정 경로 · M-15 BOM | 게시된 경로·확정 BOM 불변, 새 버전으로 개정 |
| **020c** | M-02 생산계획 · M-03 작업지시 | `sales_plan_code` 수기 문자열. 배정 합계 ≤ 계획수량(FS-006b), 게시된 `route_version`만. BOM 선택(M-G05). 발행 시 LOT 생성(1지시:1LOT, M-G04). 취소 사유 필수 |
| **020d** | M-04 LOT 현황 · M-05 공정 실행 | TX-01 시작 / TX-02 완료. **같은 설비 미종료 실행이 있으면 시작 거부**(M-G07) |
| **020e** | M-06 자재 투입 · M-07 실적 확정 | 재고 차감 없음(WMS 소유, M-G01). `material_lot_id` NULL 중복 SERVICE 검사(M-G02). 양품·불량 수기(M-G03) |
| **020f** | M-08 패킹 · M-09 완제품 입고 | TX-10·TX-11. Σ포장수량 ≤ LOT 양품: 부모 잠금 → 합계 재조회 → 초과 롤백(M-G08) |
| **020g** | M-01 대시보드 | 가동률 없음(M-G06 보류, 설비 상태 컬럼 없음 — 화면에 사유 안내) |

## 5. 병행 규칙 (같은 폴더를 쓰지 않는다)

- Codex는 **메인 폴더를 쓰지 않는다.** 전용 worktree `../factory-studio-codex`, 브랜치 `codex/<ID>`.
- 공유 파일은 **자기 줄만** 추가한다. 충돌은 나중에 병합하는 쪽이 rebase로 해결(현재 규칙: rebase는 Claude Code).

| 공유 파일 | 규칙 |
|---|---|
| `backend/src/fs/main.py` | `include_router` 한 줄씩 |
| `frontend/src/app/App.tsx` | 모듈 라우트 한 줄씩 |
| `frontend/e2e/portal.spec.ts` 360px 목록 · `tools/run_portal_smoke.py` | 자기 모듈 항목만 추가 |
| `frontend/src/shared/*` (공통 컴포넌트·스타일) | 바꿔야 하면 **별도 작은 커밋** + 보고서에 명시. 다른 모듈 화면을 깨지 않는지 frontend 전체 테스트 |
| `backend/tests/conftest.py` | Codex 소유. Claude는 수정하지 않는다. 새 테스트는 `guest_space` fixture 사용 |
| `tools/run_portal_smoke.py` 실행 | 8000·5173 포트와 스모크 DB를 고정 사용 → **동시에 실행하지 않는다.** Codex는 실행 전 사용자에게 묻는다 |
| `test_common.py`·`test_seed.py` | antigravity 소유 |
| `docs/plan/현재기획_진행현황.md`·`docs/progress.md`·`docs/agent/HANDOFF.md` | 자기 ID 절만 추가. HANDOFF는 담당자별 절을 나눈다 |

## 6. 착수 전 사용자 결정

| # | 질문 | 언제 |
|---|---|---|
| D-1 | 분배: 병렬(Codex ERP · Claude MES) / 순차(Codex가 둘 다) | 지금 |
| D-2 | E-G07 0원 매출의 세금계산서 발급 허용 여부 | FS-019d 전 |
| D-3 | antigravity 투입 여부와 범위 | FS-019a 뒤 |
| D-4 | (FEMS에서 남은 것) 사용 중 채널 배수 변경 허용 유지 여부 | 아무 때나 |

## 7. FEMS 14화면에서 확인된 함정 (그대로 반복하지 않는다)

1. **ruff는 CI와 같은 범위**: `ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py` + 같은 범위 `format --check`. 파일 몇 개만 돌리면 CI에서 깨진다.
2. **backend 테스트는 CI 환경 변수만**(DATABASE_URL·TEST_DATABASE_URL·PATH·HOME). `.env`를 쓰면 SESSION_SECRET이 섞여 결과가 달라진다.
3. **날짜 고정**: 게스트를 만드는 테스트 fixture는 `FS_TODAY=2026-09-24`. 날짜가 바뀌면 17개가 깨졌던 원인.
4. **이미 있는 엔드포인트부터 찾는다**: F-12 때 `GET /meters`가 F-02용으로 이미 있었다. 새로 만들지 말고 필드를 추가해 공용.
5. **도움말(`content/help/<모듈>/*.md`)은 스키마에 없는 기능을 적어 둔 경우가 많다**("비활성화", "참조 중 삭제 불가"). 구현하면서 실제 동작에 맞게 고친다.
6. **SERVICE 정책은 400 필드 오류(`details.fields`) / 409(`reason` + `references` 건수)** 형식을 따른다. 참조 삭제는 `REFERENCED_BY_OTHERS` + 건수.
7. **360px 스크린샷을 직접 연다**: 관리 열(수정·삭제)이 가로 스크롤 뒤에 숨는 문제가 두 번 나왔다. 관리 열은 코드 바로 뒤에 둔다.
8. **e2e 선택자는 고정**: `getByRole("row", { name: /^CODE/ })`처럼 앞을 고정한다(부모 열에 같은 코드가 있으면 여러 행에 걸린다). 조회 조건을 입력하기 전에 첫 로드를 기다린다(서버 기본 기간이 입력을 덮어쓴다).
9. **CI는 `gh`로 직접 확인**: `gh run list --branch <b>` / `gh run watch <id> --exit-status`. push는 사용자 확인 뒤, `git push --mirror` 금지.
10. **30분마다 WIP 커밋, 세션 종료 시 HANDOFF 갱신·커밋.** 스테이징에서 `.env`·`work/` 제외 확인.
11. **스키마 갭을 만나면 임의로 정하지 않는다.** schema.json·마이그레이션을 바꾸지 말고 질문한다.

## 8. 매 하위 ID 완료 조건 (공통)

- 화면이 실제 시드 데이터로 렌더링("준비 중" 0), API는 FS-010 형식(`data`·`page`·오류 코드).
- 테스트: backend 항목별 분리 파일, frontend `<화면>.test.tsx`, Playwright 흐름 1개 + 360px 가로 스크롤 없음.
- 검증 명령(모두 exit 0): frontend typecheck·lint·format:check·build·test / ruff(CI 범위) / backend 전체(CI 환경) / `tools/run_portal_smoke.py` / `npm run db:validate` / `python tools/audit_schema_isolation.py` / `git diff --check`.
- 문서: `docs/agent/<모듈>_FS-019x.md` 보고서, FS-010 해당 절, `현재기획_진행현황.md`(진행률·완료 ID·다음), `progress.md`, `HANDOFF.md`.

---

## 9. 프롬프트

### 9-A. Codex — 지금 (test-speed 재측정 → 개선)

```
../factory-studio-codex에서 작업한다. 메인 폴더는 쓰지 않는다.
먼저 docs/agent/HANDOFF.md와 docs/agent/MES_ERP_작업계획_FS-019_020.md를 읽어라.

1. codex/test-speed 브랜치를 origin/main(70951d4 이후)으로 rebase하라. 아직 커밋이 없으면 reset으로 맞춰도 된다.
2. 개선 전 기준을 다시 잰다. 이전 측정(78e1206, 228 passed / 16 failed)은 날짜 고정(FS_TODAY) 전이라 무효다.
   환경 변수는 DATABASE_URL·TEST_DATABASE_URL·PATH·HOME만, DB는 factory_studio_codex_test만.
3. 네가 제안한 순서대로 개선한다: 세션당 템플릿 1회 생성 → 테스트별 게스트 공간 → 게스트 데이터만 정리.
   FS_TODAY 고정은 유지하고, test_seed.py·test_common.py의 정리 방식과 충돌하지 않게 fixture 수명을 나눈다.
4. 전체 테스트를 두 번 연속 실행해 시간과 통과 수를 비교한다(전·후 모두 전체 통과여야 한다).
5. ruff는 CI 범위(backend tools/verify_ddl_matches_schema.py)로 check·format --check.
6. 결과(전·후 시간, 통과 수, 바꾼 fixture, 남은 병목)를 보고하고 멈춘다. push는 사용자 확인 뒤.
```

### 9-B. Codex — ERP 착수 (FS-019a)

```
../factory-studio-codex, 브랜치 codex/fs-019a-erp-master (origin/main에서 분기).
읽을 것: AGENTS.md, docs/agent/HANDOFF.md, docs/agent/MES_ERP_작업계획_FS-019_020.md(특히 §3·§5·§7·§8),
docs/ui/화면설계_ERP_FS-008a.md, docs/modules/erp/ERP_모듈설계_FS-005e.md, docs/architecture/API계약서_FS-010.md §8,
그리고 패턴 참고로 backend/src/fs/fems/(router·service·repository·schema)와 frontend/src/fems/(FemsLayout·EnergySources·Tariffs·Factors).

FS-019a를 구현한다: ERP 뼈대(/api/v1/erp, frontend/src/erp, App 라우트, ERP 사이드바) +
E-15 거래처 · E-16 품목(단위환산) · E-17 거래처별 단가 · E-18 계정과목·분개규칙(읽기 전용).
- 모든 질의에 S=(workspace_id, generation_id). 쓰기는 write_scope 뒤, CSRF + Idempotency-Key, 멱등 영수증.
- 입력 오류는 400 VALIDATION_FAILED + details.fields, 정책 위반은 409 + reason/references, 참조 삭제는 REFERENCED_BY_OTHERS + 건수.
- E-16 상단에 "MES 품목과 독립" 안내. 도움말 content/help/erp/e-15~18.md가 실제 동작과 다르면 고친다.
- schema.json·마이그레이션은 바꾸지 않는다. 갭을 만나면 멈추고 질문한다.
공유 파일(main.py, App.tsx, portal.spec.ts 360px 목록)은 ERP 줄만 추가한다. conftest.py는 네 소유다.

완료 조건과 검증 명령은 계획서 §8. 끝나면 docs/agent/ERP_FS-019a.md 보고서,
FS-010 §8, 현재기획_진행현황.md, progress.md, HANDOFF.md(Codex 절)를 갱신하고 커밋한 뒤 보고하고 멈춘다.
push·main 병합은 사용자 확인 뒤. 결정이 필요한 것은 [기획 의도 검토] → [예상 문제점/제약] → [질문] → [권장안] 순서로 묻는다.
```

### 9-C. Codex — 이어가기 (FS-019b 이후 매번)

```
../factory-studio-codex에서 FS-019<x>를 진행한다. 브랜치 codex/fs-019<x>-<이름> (최신 origin/main에서 분기).
먼저 docs/agent/HANDOFF.md, 계획서 §3의 019<x> 행, 해당 화면 설계 절, 관련 TX 문서(FS-006a/FS-014b)를 읽는다.
이전 하위 ID가 main에 병합됐는지 확인하고, 아니면 멈추고 보고한다.
계획서 §7 함정과 §8 완료 조건을 그대로 적용한다. 동시성 규칙이 있는 화면은 동시성 주입 테스트를 포함한다.
끝나면 보고서·문서 갱신·커밋 후 보고하고 멈춘다. push는 사용자 확인 뒤.
```

### 9-D. Claude Code — MES 착수 (F-09 종료 뒤)

```
docs/agent/HANDOFF.md와 docs/agent/MES_ERP_작업계획_FS-019_020.md를 먼저 읽고 FS-020a를 진행해줘.
메인 폴더, 브랜치 fs-020a-mes-master. Codex는 ../factory-studio-codex에서 ERP를 진행 중이다.
공유 파일은 계획서 §5 규칙대로 MES 줄만 추가하고, conftest.py는 수정하지 않는다. 답변은 한국어로.
```
