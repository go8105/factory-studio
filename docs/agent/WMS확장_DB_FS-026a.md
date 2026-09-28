# FS-026a WMS 확장 DB 구현·검증 인계

2026-09-28. 브랜치 codex/vision-ai, 시작 01b6cce. 사용자가 전체 설계를 승인하고 후속 질문은 권장안으로 진행하도록 지정했다. **DB 기반 구현 완료, 입고/예약 API·W-08/09·트럭 기능은 후속 작업이다.**

## 구현

- schema.json v0.13.0: 전체98테이블·1022컬럼·225FK, WMS11테이블. 기존6테이블을 유지하고 입고 예정/명세·원천선점·예약/배분 5개 추가.
- 새 revision `fs026a_wms_receiving_reservation` → down `fs025b_bems_module`. 고정 SQL이며 실행 중 schema.json을 읽지 않는다. 기존 적용 migration 수정 없음.
- storage_location에 NORMAL/QUARANTINE 추가(기존 행 NORMAL), stock_document에 WMS_INSPECTION 유형 추가. 기존 CHECK c620/c624만 허용 유형 확장. 기존 C/R 번호 및 업무 관계 보존. 새 참조는 WMS 내부+core 범위 앵커뿐이다.
- NULL LOT 중복은 NULL/NOT NULL 부분 유니크 두 개로 차단한다. 검수 수량 동시 입력·합계, 격리 위치, 차이 사유, 상태/시각, 선점 유효 연결, 예약 소진 전표/원천 동시 기록을 DB 제약으로 검증한다.
- 원천 선점과 직접 반영의 상호 배타·예약 부족·위치 품목 검증은 SERVICE 정책이다. **DB 적용만으로 해당 업무 정책이 실행되는 것은 아니다.** 후속 API가 기존 sync 경로까지 함께 수정해야 한다.
- downgrade는 신규 업무 행/검수 전표/격리 위치가 있으면 중단한다. 업무 이력을 자동 삭제하지 않는다. 빈 확장 상태에서만 기존 revision으로 되돌릴 수 있다.
- DB설계서31시트·WMS/전체 Mermaid·오프라인 ERD·정적/DDL 검증 보고 갱신. ERD는 nullable unique FK의 조건부 유일성도 반영한다.

## 검증 결과

| 검증 | 결과 |
|---|---|
| 정적 DB 명세·R1~R6 | 오류0 |
| PostgreSQL18.6 카탈로그 vs metadata | 오류0, PK98/UK219/CHECK271/유니크인덱스25/인덱스74/FK225 |
| 새 revision upgrade→이전 head downgrade→upgrade | 통과 |
| 전용 빈 DB downgrade base→upgrade head | 통과, 최종 DDL 대조0 |
| 기존 WMS API/시드 테스트 | 15 passed |
| 신규 DB 제약·downgrade 보호 | 7 passed |
| 스키마 변조 탐지 | 9 passed(빈 DB 재실행) |
| 기존 시드/세대 복사 테스트 | 16 passed |
| tools unittest | 58 passed |
| 새 migration/DB테스트 Ruff check·format | 통과 |
| Excel | artifact-tool 생성/재계산/오류검색0, 31시트 값 대조, WMS4시트 변경 영역 시각검사, 무관 모듈 값 보존, 내부링크284 |

총 고유 선택 백엔드 테스트는47개다(15+7+9+16). 첫 스키마 변조 묶음은 기존 테스트가 남긴 ERP partner NULL 값 때문에 NOT NULL 변조 실행1건이 실패했다. 빈 전용 DDL DB에서 코드 수정 없이 해당 파일9건을 재실행해 통과했다. 도구 테스트 로그의 injected failure/ABORT는 기존 실패 주입 테스트의 예상 출력이며 unittest 결과는 OK다.

전체 백엔드 회귀/프런트·브라우저/운영/Excel 네이티브 앱은 실행하지 않았다. AC-139의 DB 구조 부분을 검증했으며 AC-140~164 업무 기능 통과로 간주하지 않는다. 기존 테스트 클라이언트 사용중단 경고2개 유지.

## 환경과 재현

- 전용 로컬 DB `factory_studio_codex_fs026_test`(API/시드), `factory_studio_codex_fs026_ddl_test`(빈 DB DDL 검사)를 사용했다. 공유 개발 DB·운영 DB는 변경하지 않았다. 병행 BEMS 작업과 데이터 충돌을 피했다.
- fetch에서 origin/main은489d5f3(BEMS 화면)까지 전진했으나 migration head는 변함없음을 확인했다. 이번 작업의 기반 main은 b9dfbc4이고 새 BEMS UI는 재적용하지 않았다. 통합 시 최신 main으로 정렬한다.
- test DB 접속 URL은 외부 환경 변수로 주입하고 출력/커밋하지 않는다. `.env`·work/는 스테이징하지 않는다.

```sh
python3 tools/apply_fs026a.py
npm run db:validate
python3 -m unittest discover -s tools -p 'test_*.py'
# 전용 *_test DATABASE_URL/TEST_DATABASE_URL 주입 후:
(cd backend && .venv/bin/alembic upgrade head)
backend/.venv/bin/python tools/verify_ddl_matches_schema.py --output docs/db/ddl-verification-report.json
backend/.venv/bin/pytest backend/tests/test_wms_extension_schema.py backend/tests/test_wms.py -q
# 스키마 변조 검사는 별도의 빈 *_test DB에서 실행
backend/.venv/bin/pytest backend/tests/test_schema_verifier.py -q
backend/.venv/bin/pytest backend/tests/test_seed.py -q
npm run db:build
python3 tools/build_erd.py
```

Excel 실제 작업은 기존 생성기의 --artifact 경로를 사용했다. 일반 npm run db:build는 기존 ExcelJS 경로이며 새 의존성을 추가하지 않았다. 신규 업무 시드는 이번 단계에 넣지 않았고 기존 품목·시드를 그대로 유지했다.

## 다음

FS-026b API: source_claim 선점/검수/대사와 기존 ERP 매입 sync 라우팅, 예약/ERP 출하 전량 소진, 가용 수량·위치 정책, interface 계약, 동시성·멱등 테스트. 이어 W-08/09·기존 화면·트럭·도움말·신규 합성 시드. 사용자가 권장안 진행을 지정했으므로 범위 안 세부 선택은 재질문하지 않는다. push·운영 배포는 별도 사용자 확인 전 실행하지 않는다.
