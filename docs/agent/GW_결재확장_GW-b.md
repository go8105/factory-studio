# GW-b 결재 확장·전결·위임 결과

2026-10-09 · `codex/gw-dsn31` · GW-a `19e8f9e` 이후 · WIP `6ce757c` 이후 최종 커밋은 `git log -1 --oneline`으로 확인.

사용자가 GW-a 제안대로 진행 및 GW-b 착수를 승인했다. DSN-31 체험 범위의 결재 정책 v2·병렬·합의·참고·전결·위임 핵심을 구현했다. 원문 제공 소유자의 미구현 의존성과 인쇄 시각 검증은 별도로 남겨 두었다. main·공유 개발/운영 DB·원격 push·배포를 변경하지 않았다.

## 구현과 판단

| 대상 | 결과 |
|---|---|
| G-02 기안·G-06 결재선 / F05·F06 | 1~3단계, 참여자 최대30명. 같은 단계 병렬 결재·필수 합의·참고. 각 단계 결재 필수, 연속 단계·중복·자기 결재·비활성 검사. 템플릿 변경은 기존 문서에 자동 반영되지 않음 |
| G-03 결재·G-04 기록 / F04·F06 | 필수 결재·합의 모두 완료 후 이동. 참고는 진행을 막지 않고 단계 종료 시 생략. 합의 반대는 반려. 원 담당자·역할·대리 담당자·위임 번호·생략 원인이 이력으로 보존됨 |
| G-08 전결 / F07 | 공통 MasterScreen 사용. 종류·통화·금액 하한 포함/상한 미포함·시작/종료 월 포함·활성 규칙. 겹침 차단. 서울 기준 상신 월로 선정해 SUBMITTED 이력에 고정하고 뒤 단계는 SKIPPED. 사용된 규칙은 비활성 처리만 허용 |
| G-09 위임 / F08 | 원 담당자가 등록·해제. 시작 포함/종료 미포함, 종류·금액 조건, 자기·연쇄·겹친 위임 차단. 기안자·해당 문서의 다른 참여자 대리 처리 차단. 여러 원 담당자는 stepId 선택. 처리 시점에 재검사 |
| 기존 v1 호환 | 기존 문서는 v1 유지, 전결·위임 미적용. 신규 문서만 서버에서 v2 지정. 상신본·처리 이력 불변, 재상신은 새 회차·새 상신에서 전결 재선정 |
| F03·F41 원문/배지 계약 | GW 소비·읽기 제공을 ERP 발주·경비·PLM ECO로 확장. 실제 제공 미구현 종류는 UNIMPLEMENTED로 명시. 현재 실제 연계는 기존 ERP 매입만 가능. 신규3종 GW 계약은 mock 제공자를 붙여 검증 |
| F10 인쇄 | 브라우저 인쇄 버튼과 인쇄 CSS 구현: 문서번호·상신 시각·본문·단계·전결·이력. 네이티브 인쇄 미리보기는 Mac 잠금 때문에 직접 확인하지 못함. PDF 출력 결과 미검증 |
| 도움말 | 이번에 바뀐 G-02/03/04/06/08/09 6편 추가. 전체 시드·나머지 도움말·흐름맵은 GW-e 범위 |

위임 한도 DB에는 통화가 없다. 금액 한도가 있는 위임은 KRW 금액 문서에만 허용하고 UI에도 KRW를 명시했다. 금액 없는 문서·다른 통화는 한도가 있는 위임으로 처리할 수 없다. 한도 없는 위임은 종류·기간 조건으로 검사한다.

새 쓰기는 공통 engine.action의 공간 잠금·세대/모듈 확인·멱등 영수증과 감사 이력을 사용한다. G-08 수정은 공통 MasterScreen의 선택적 updateBody 훅으로 expectedVersion을 전송한다. 다른 기준정보 화면의 기본 동작은 유지한다. DB 구조는 GW-a 그대로이며 GW-b에는 신규 마이그레이션이 없다.

## 검증

- 전체 백엔드: **927 통과, 1 건너뜀**, PostgreSQL 독립 테스트 DB·4개 작업자, 331.13초. 마지막 코드 계약 보정 뒤 GW API·정책·스키마 집중 재검증 **58 통과**, 122.59초.
- 전체 프런트: **554 통과**. 마지막 UI/도움말 보정 뒤 GW·포털 콘텐츠 **26 통과**. TypeScript·프런트 전체 ESLint·Vite build 통과.
- GW 코드·관련 테스트 Ruff 통과. 전체 백엔드 Ruff는 기존 `core/service.py` import 정렬 1건으로 실패하며 WIP 기준본에서도 같은 오류가 재현됨. GW 범위 밖 파일은 수정하지 않았다.
- DB 설계 검증 오류0. 이번 단계는 schema/DDL 변경 없음. GW-a DDL·마이그레이션 증빙은 [이전 결과](GW_체험보강_DB_GW-a.md).
- 실제 API 검사: 병렬/합의/참고·반대·v1·전결 경계/겹침/불변/재상신·위임 조건/기간/해제/자기/연쇄/기안자/중복 참여자·복수 대리 선택·멱등·병렬 승인 경합·위임 해제와 승인 경합·전결 등록 경합. 신규 원문은 명시적으로 mock 제공자 사용.
- Chrome 실제 입력: 결재선 등록 → 전결 등록 → 위임 등록 → 500 KRW 기안 → 상신/후속 단계 생략 → 대리 승인/합의 대기 → 합의 → 최종 승인/이력. 390px 초기 진입 확인, body 폭390·두 표는 내부333px에서 각각600/784px 가로 스크롤.
- 인쇄 미리보기·실제 PDF·실제 회사 신원/권한·공유 공간·ERP 확정 통제·운영 적용 미검증/범위 밖. 원문 제공 미구현은 완료로 표시하지 않음.

[검증 요약](assets/gw-b/verification.txt) · [최종 승인 화면](assets/gw-b/approval-complete.png) · [위임 화면](assets/gw-b/delegation.png) · [모바일 화면](assets/gw-b/approval-mobile.png)

## 재현과 인계

작업 경로: `git worktree list`에서 `codex/gw-dsn31` 항목. venv는 기존 저장소 것을 재사용할 수 있으나 `PYTHONPATH=backend/src:backend`로 해당 worktree 코드를 사용한다. PG18 마이그레이션 head는 `gw_a_dsn31`, schema0.21.0·GW19/전체173표. 비밀 DB URL은 Git에 넣지 않는다.

```sh
PYTHONPATH=backend/src:backend python -m pytest backend/tests -q -m 'not perf' -n 4
PYTHONPATH=backend/src:backend python -m pytest backend/tests/test_gw_policy.py backend/tests/test_gw.py backend/tests/test_gw_schema.py backend/tests/test_gw_a_schema.py -q
cd frontend
npm test
npm run typecheck
npm run lint
```

테스트에는 `TEST_DATABASE_URL`로 `_test` 접미사의 별도 DB를 사용한다. 동일 DB에 독립 pytest 프로세스를 동시에 실행하지 않는다. 브라우저 검증 전후 백엔드/프런트 미리보기는 중지했고 테스트용 의존성 링크는 커밋에서 제외했다.

ERP 담당에게 `APPROVAL_KINDS` 선언과 PURCHASE_ORDER·EXPENSE_CLAIM 원문 계약을, PLM 담당에게 `eco_for_approval` 계약을 연결 요청해야 한다. 배지 제공은 단일 종류에 기존 번호 키, 혼합 종류에 `종류:번호` 키를 사용한다. 외부 솔루션 직접 쓰기·교차 FK 없음. ERP 확정 통제 F44는 Claude의 W2b 소유다.

다음 단계는 사용자 결과 확인 후 **GW-c 조직·HR 연계**. GW-c를 이번 작업에서 시작하지 않았다. 실제 도입 A 트랙은 계속 별도이며 다른 브랜치와 병합 시 GW-a metadata/마이그레이션 부모·제약 순번·버전을 다시 대조한다.
