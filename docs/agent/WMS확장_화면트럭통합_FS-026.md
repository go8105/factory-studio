# FS-026 후속 통합 — 입고·예약 화면, 3D 트럭, 체험 시드와 도움말

2026-09-30. **구현 후 최종 통합 검증 중.** 브랜치 `codex/vision-ai`, b2 기준 `9c66cf1`, 후속 구현 `cd41b04`. 사용자는 b2 후 “바로 3D 트럭 연결, 시드·도움말·통합 검증까지”를 승인했다. 중간 확인 대기 없이 후속 전체를 진행하며 push와 운영 배포는 제외한다.

## 사용 흐름

입고 예정 등록(W-08) → W-08 도착 처리 또는 3D 트럭 도착 → 합격·격리·부족 검수 확정 → 정상/격리 재고 확인(W-02) → 출고 예약(W-09) → ERP 확정 출하 대조 → 출하 연결·소진 → 전표(W-04)/원장(W-05).

트럭은 도착 상태만 기록한다. 정상95·격리3·부족2 KG 검수 시 전체 현재고98/예약 대상 정상95가 증가한다. 예약은 원장을 움직이지 않으며 정상 현재고에서 활성 예약만 차감한다. ERP 수요를 다시 차감하지 않는다. 원자재는 예약/해제까지만, 고객 출하 소진은 완제품만 지원한다.

## 구현

- W-08 `/wms/inbounds`: 상태/창고/예정일 범위/페이지, URL `open` 상세 복원, 다중 명세 등록·예정 편집·취소, ERP 연결/해제 및 수동 검수 후 대사, 도착, 수량 요약 후 검수 확정. 소수3자리 부족 계산은 BigInt 정수 연산을 사용한다. 실패 입력 보존, 서버 재조회, 미저장 닫기 보호, 전량 부족/ERP off 안내.
- W-09 `/wms/reservations`: 상태/품목/부족/페이지, 정상 위치·LOT별 가용 비교와 예약 등록, 해제, 출하지시 참고 비교, 확정 출하 대조 미리보기와 소진. 부분/자동 소진 없음. 서버 미리보기와 실제 소진은 같은 대조 함수를 쓰고, 소진은 기존 공간 잠금 안에서 다시 검사한다.
- 기존 W-01~07: 입고·검수 대기/예약 부족 링크, 정상·격리·예약·가용 표시, 위치 유형 필터, 검수 원천→W-08/전표→검수 링크, 원장 위치 유형, 격리 위치 등록·수정. 마스터 보호·수량 오류는 기존 서버 규약으로 안내.
- 3D 공장: 트럭 입고 패널에서 예정 선택 → 4초 모의 진입 → 서버 arrive. 시연/저장 중 선택 잠금, 탭 숨김/일시정지 대응, 화면 이탈 시 애니메이션 정리. 실패는 성공으로 바꾸지 않으며 재조회·동일 요청 재시도 제공. 재진입은 서버 도착 상태로 정차 복원. 외관 옆 패널과 트럭 모델을 함께 표시한다.
- 서버 조회 보강: 입고 `expectedFrom/expectedTo`, 예약 `shortageOnly`, 재고 `locationType`, GET `/reservations/{id}/shipment-preview?sourceKey=...`, 전표 상세 `noticeId`, 원장 `locationType`, 대시보드 대기/부족 건수. 쓰기 수량·시각·원천 선점 규약은 b1/b2 유지.
- 시드 `sv-20260930-1`: 기존11,910행에 WMS22행 추가 → 템플릿11,932/게스트복사11,930. BEMS4,218행과 기존 품목 유지. R-Q01/F-Q01, 예정/도착/95·3·2 검수/전량부족/취소, 활성/해제/소진 예약. 소진 예시는 기존 역사 출고 전표와 예약 이력을 연결하며 원장을 더 차감하지 않는다. PI-0004/SH-0004 미반영 체험 유지.
- 도움말: W-08/09 신설, W-01~07 개정, 포털 사용자 참고 문서 `portal/wms-flow`. 직접 반영과 검수 경유, ERP 취소와 실물 정정, 가용과 현재고, 원자재 예약, 트럭의 한계를 설명한다. 메뉴에서 참고 문서 트리가 자동 생성된다.

## 검증 기록

- b2까지 전체 backend777 통과. 후속 관련 backend76 통과, 이후 preview/filter 포함 예약24 통과. 후속 전체 backend는 별도 깨끗한 DB에서 실행 중이며 아직 성공으로 표시하지 않는다.
- 프런트 전체491/57파일 통과. 타입 검사/빌드, 전체 ESLint·Prettier 통과. CI ruff check/format139파일, R1~R6 격리 감사98테이블/225FK 오류0, db:validate0. tools58 및 subtests13 통과.
- 실제 API 브라우저: 트럭 도착 시 원장0/새로고침/95·3·2 검수, 예약 부족 입력 보존·해제, 전량 출하 소진+sync 중복방지, ERP off·모바일 도움말, 기존 WMS3개 회귀 포함 **10개 모두 통과(1.2분)**. 매입 연결 직후 도착·검수 연속 조작도 통과했다.
- 브라우저 검증에서 매입 연결 직후 도착 처리 시 상세 재조회 전 이전 버전을 사용할 수 있는 문제를 발견했다. W-08/09는 저장 응답을 즉시 상세 상태로 반영하고 목록/상세를 재조회하도록 수정했다. 미저장 보호 테스트는 확인창 종료 후 차량 입력란에 포커스를 두고 Escape를 입력한다.
- 전체 프런트 기본 병렬 실행에서 기존 ERP 단가 테스트 1개가 일시 실패했다. 제품 코드 변경 없이 maxWorkers=2로 재실행하고, 최종 UI 수정 후에도 전체491개를 다시 통과했다. 최초 등록 테스트의 기본 창고/선택자 문제를 보정했다. 반복 생성으로 전용 DB의 게스트20개 한도에 도달해 로컬 검증 서버만 GUEST_LIMIT=200으로 재시작했다. 제품 기본20 및 운영 설정 변경 없음.
- 새 API/시드/화면을 실제 로컬 PG18·Chromium으로 검증한다. 작업 중 사용한 DB는 factory_studio_codex_fs026_ui_test, factory_studio_codex_fs026_browser_test, factory_studio_codex_fs026_integrated_final_test이며 공유 개발/운영 DB를 수정하지 않았다.

## 인수 기준 연결

| AC | 증거 |
|---|---|
| 139 | 기존 migration head 유지, metadata98/1022/225 및 정적·격리 감사 |
| 140~150 | b1 API23개 회귀, W-08 도착·95/3/2·전량부족·취소·ERP 연결/응답유실 브라우저 |
| 151~158 | b2 API22개 및 후속 preview/filter2개, W-09 부족·등록·해제·출하 대조·소진+sync 브라우저 |
| 159 | b1 격리 이동/유형 보호 API, W-06 유형 조작 지원 |
| 160 | API 모듈 off 회귀, ERP off 수동 UI/기존 MES off 브라우저 |
| 161~162 | 공간/세대·초기화·복사 전체 회귀, 새 시드 FK/날짜 이동 및 기존 snapshot digest 불변 |
| 163 | 360px 가로 넘침·키보드 미저장 닫기·트럭 통신 실패/재시도·서버 도착 복원 |
| 164 | API version/멱등/확정 재요청, 검수 저장 응답 유실 후 GET 재조회 브라우저 |

테스트 수는 AC 수와 같지 않다. 실제 PLC/GPS/차량 관제, 운영 부하/모든 브라우저 검증, 배송 지도 및 CNC 수량→WMS 자동 연결은 포함하지 않는다.

## 재현과 사용자 배포 인계

1. FS-026a가 적용된 별도 PostgreSQL 테스트 DB와 DATABASE_URL/TEST_DATABASE_URL을 준비한다. 비밀값은 문서/로그에 기록하지 않는다.
2. 저장소 루트에서 `backend/.venv/bin/alembic -c backend/alembic.ini upgrade head` 후 `PYTHONPATH=backend:backend/src backend/.venv/bin/python -m seed.cli template --date YYYY-MM-DD`로 새 템플릿을 생성한다. 이미 사용 중인 기존 템플릿·게스트를 덮어쓰지 않는다. 새 템플릿 검증은 반환 workspace/generation을 seed.cli validate에 전달한다.
3. 로컬 HTTP 브라우저 검증만 COOKIE_SECURE=false, 합성 SESSION_SECRET, GUEST_LIMIT=200으로 API `fs.main:app`을 127.0.0.1:8000에 실행한다. 운영 설정으로 복사하지 않는다.
4. `cd frontend && npx playwright test --config playwright.wms-extension.config.ts`로 실제 API WMS 시나리오를 검증한다. 이 설정은 개발서버5173을 실행한다.
5. 전체 검증: `backend/.venv/bin/pytest backend/tests -q --tb=short`, `backend/.venv/bin/pytest tools -q`, CI ruff에 `--config backend/pyproject.toml` 명시, `python3 tools/audit_schema_isolation.py`, `npm run db:validate`, frontend typecheck/test/build.
6. 사용자가 배포할 때 백엔드·프런트를 함께 반영한다. 이번 후속에는 새 migration이 없지만 FS-026a head가 선행되어야 한다. 새 체험 예시는 새 템플릿 생성 후 새 게스트/초기화에서 사용하며 기존 기록에 소급 추가하지 않는다.

운영 배포와 push는 실행하지 않았다. 최종 체크아웃·커밋·테스트 결과는 아래 최종 갱신 및 HANDOFF를 따른다.
