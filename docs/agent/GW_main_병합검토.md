# GW main 병합 검토 (2026-10-09)

판정: **코드·스키마는 충돌 없이 병합할 수 있으나, 기존 main의 CI 도구 실패를 해결한 뒤 병합하는 것을 제안한다.** main 병합·push·배포는 실행하지 않았다.

## 검토 기준

- main: `af1072669d6441d3b70605ff01054bc294cca393`, 작업 트리 변경 없음.
- GW 제품 기준: `17f0f18`, 브랜치 `codex/gw-dsn31`. 이번 검토 보정·문서 커밋은 `git log -1 --oneline`로 확인한다.
- merge-base가 main과 같고 `git merge-tree --write-tree main HEAD` 성공. GW-a~e 9개 커밋의 변경만 추가되며 fast-forward 가능. 공유 main 폴더는 읽기만 했다.
- 검토 중 main 기준이 바뀌면 해당 변경과 migration head를 다시 검토해야 한다. 원격 최신 상태는 fetch하지 않았으며, 이 판정은 로컬 main 기준이다.

## 발견 사항

1. **P1 / 기존 main CI 차단 — 목표 설계 재생성**: `tools/test_dsn11.py::ErpTargetTest.test_rebuild_from_schema_json_is_identical`에서 `apply_dsn22`가 MES `pop_import`의 이전 CHECK를 찾지 못한다. 같은 실패를 원본 main에서 읽기 전용 테스트로 재현했다(main DSN-11 4건 중 3통과/1오류). 제품 MES가 이미 확장된 상태에서 초기 DSN 순서를 재적용하는 전제와 관련된 것으로 판단한다. 목표 설계 재생성의 기준·단계 멱등성을 정리해야 하며 테스트를 건너뛰어 숨기지 않는다. MES/전체 DSN 도구 변경은 이번 GW 보정에 포함하지 않았다. `.github/workflows/ci.yml`의 전체 tools unittest 단계가 실패하므로 CI 전체 통과로 보고할 수 없다.
2. **P2 / GW 회귀 — 최초 GW 설치 도구 재적용, 수정 완료**: `apply_fs030a.apply()`가 GW 표 집합을 최초 8개와 정확히 같아야 한다고 검사하여, GW-a의 19개 표가 있으면 완전한 설치도 부분 설치로 오판했다. 최초 8개가 모두 있는지 검사하도록 변경해 후속 확장을 보존한다. 기존 기본 표 누락 거부 테스트를 유지하고 후속 표 추가 후 재실행이 원본을 바꾸지 않는 회귀 테스트를 추가했다. FS-030a 7건 및 GW-a 도구 4건 통과.
3. **P1 / 기존 main SPC 테스트 실패**: `test_chart_without_end_date_includes_measurements_after_business_day`에서 호스트 현재 시각으로 입력한 측정이 공정 실행 기간 밖으로 판정되어 HTTP 400이 반환된다. 기본 분배 전체 재실행에서도 재현되며, 원본 main 코드의 해당 테스트를 같은 독립 테스트 DB에서 단독 실행해 동일 실패를 확인했다(7.39초). 테스트는 호스트 시각, 입력 상한 정책은 DB 시각을 사용한다. 두 시계와 실행 기간 전제를 점검해야 한다. GW 변경으로 유입된 실패로 판정하지 않으며, SPC 제품 정책을 이번 GW 작업에서 변경하지 않았다.

## 공통 기능과 경계 검토

- `common.engine.action`의 `authorize`는 선택적 keyword-only 인자다. 기존 호출은 동일하게 동작하며 GW는 공간 잠금 후 멱등 영수증 반환 전에 현재 열람 권한을 다시 검사한다. 탈퇴 후 채팅 응답·부서 이동 후 공지 알림 응답 재생 차단 테스트가 있다.
- `shared/master.tsx`의 검색·새로고침·삭제 금지·부분 PATCH는 선택 기능이며 기존 MES/FEMS 호출 기본값을 유지한다. MES 테스트 수정은 현재 dashboard 호출 mock 보정이고 MES 제품 코드 변경은 없다.
- 시드 복사 변경은 GW에만 JSON/다형 참조 재매핑을 적용한다. 공통 임시 ID 지도 정리는 복사 마지막에 실행하며 같은 트랜잭션의 반복 복사를 검증했다. 승인 원본·금액·코드·조직 스냅샷·원문 digest를 보존한다.
- HR은 읽기 전용 interface로 조회하고 GW가 가져온 조직·사람을 소유한다. ERP 매입 시드는 실제 공개 조회 결과를 고정한다. 업무 스키마 간 FK/쓰기 추가 없음.
- 실제 회사 계정·TEAM·운영 권한은 A 트랙 미구현이다. ERP 확정 통제 F44 및 신규 ERP 발주/경비·PLM ECO 원천 제공은 외부 담당 범위다. 결재 담당자 선택은 합성 체험 방식이다.

## 마이그레이션·배포 준비

- 단일 head: `gw_a_dsn31`, 부모 `w2a1_mes`. 기존 공유 migration 수정 없음. 제품 schema 0.21.0, 173표/1,916컬럼/412FK. Excel·ERD와 함께 제공된다.
- 별도 일회용 PostgreSQL 18 DB에서 빈 DB→main, main→GW, GW→main 롤백, 재업그레이드의 **4회 실제 카탈로그 대조 모두 오류 0**. 검증 후 해당 DB를 삭제했다. 공유 개발·운영 DB는 변경하지 않았다. 채워진 기존 결재 왕복 증거는 GW-a 결과에 있다.
- 시드 버전 `sv-20261009-gw1`. 배포 스크립트는 migration 후 코드/활성 템플릿 버전이 다르면 새 템플릿을 생성한다. 병합만으로 기존 게스트 데이터가 98행 체험 시드로 바뀌지는 않는다. 운영 배포 전 새 템플릿·새 게스트 체험 확인이 필요하다.

## 검증

- backend: CI 방식의 기본 분배 `-n 4 -m 'not perf'`로 **974통과/기존 main SPC 실패1/건너뜀1**(388.90초). GW 관련 및 공통·시드 테스트는 통과했다. 성능 테스트는 독립 실행으로 **1통과/976미선택**(28.70초). 전체 backend 통과로 표시하지 않는다.
- frontend: 전체 **566 passed /71파일**. 전체 ESLint·Prettier·typecheck/build 통과. 기존 대형 번들 경고는 유지.
- 전체 backend Ruff check 및 format: 통과(202파일), DDL 대조 도구 Ruff도 통과.
- 제품/목표 DB 설계 검사 및 R1~R6 격리 감사: 오류 0.
- tools 전체: **132건 중 131통과/기존 main 오류 1**. GW 보정 후 추가 실패 없음.
- 최초 backend 검증에서 임의로 추가한 `--dist loadscope`가 전역 DB 초기화 테스트와 공유 템플릿 테스트 순서를 깨뜨려 3실패/202오류를 만들었다. 해당 실행은 정상 회귀 결과로 사용하지 않는다. 기본 분배와 성능 테스트 분리 방식으로 다시 실행했다.
- 이번 검토에서 브라우저·인쇄/PDF·운영 환경을 다시 실행하지 않았다. GW-e 실제 브라우저 증거를 유지하며 인쇄/PDF 미검증 제한도 유지한다. 원격 CI는 실행하지 않았다.

## 재현·다음 단계

독립 PG18 `_test` DB의 접속값을 환경으로 주입한다. URL을 Git/보고서에 기록하지 않는다. xdist 복제 중 원본 DB 접속과 동일 DB의 독립 pytest 동시 실행을 피한다.

```sh
export PYTHONPATH="$PWD/backend/src:$PWD/backend"
python -m unittest discover -s tools -p 'test_*.py'
pytest backend/tests -q -n 4 -m 'not perf'
pytest backend/tests -q -m perf
npm --prefix frontend test -- --maxWorkers=2
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
python tools/validate_db_design.py
python tools/audit_schema_isolation.py
```

권장 순서: 기존 DSN 재생성 오류·SPC 테스트 실패 해결 → tools/백엔드 전체 통과 → 최신 main과 다시 비교 → main 로컬 병합 → 사용자 승인 범위에 따라 push/배포. 이번 작업의 범위는 병합 검토이며 main을 이동하지 않았다.
