# FS-026b1 입고 예정·도착·검수·원천 선점

2026-09-29. **FS-026b1 완료 — 사용자 확인 대기.** 브랜치 `codex/vision-ai`, 기준 `origin/main 6508599`.

## 범위

FS-026a 승인 후 사용자 지시에 따라 FS-026b를 분할했다. 이번 범위는 TX-W4~W7, AC-140~150의 입고 API다. b2(TX-W8~W9, AC-151~158)는 이번 보고 확인 이후 시작한다. 입고 전용 화면·3D 트럭·예약·가용 조회 개편·시드 확장은 아직 포함하지 않는다. 기존 W-03의 새 상태 수신 오류를 방지하는 표시 호환만 포함했다. AC-141의 정상95/격리3/전체98 원장은 이번에 검증하고, 예약가능95 조회는 b2에서 검증한다.

main `6508599`로 rebase했다. HANDOFF 충돌은 main 내용을 유지하고 FS-026 정보를 뒤에 추가했다. 기존 BEMS 시드 템플릿11,910행, 게스트 복사11,908행 기준을 유지했다. FS-026a migration과 schema.json/Excel/ERD는 이번에 변경하지 않는다.

## 구현과 규약

- `receiving.py`·`receiving_schema.py`: 예정 생성/전체 줄 수정, 조회/페이지, ERP 선점/해제/사후 대사, 도착/취소, 검수 확정.
- 예정 생성은 businessKey 공간·세대별 유일, 갱신은 expectedVersion 필요. 이미 도착한 동일 요청과 같은 내용의 검수 재요청은 기존 결과를 반환한다. 확정 이후 줄 변경은 불가하다.
- 검수는 모든 줄의 합격+격리+부족=예정을 확인한다. 합격은 NORMAL, 격리는 QUARANTINE에 증가한다. 전량 부족은 INSPECTED 및 COMPLETED이지만 전표는 NULL이다.
- 기존 WMS `write_scope` 공간 advisory lock 안에서 원천 직접 반영과 선점을 모두 검사한다. 검수 경유 원천에 기존 sync를 실행하면 `inspection_pending`/`inspected`/`inspected_cancelled`를 반환하고 원장을 추가하지 않는다. 직접 반영된 원천은 검수에 연결할 수 없다. 원천 취소 후 직접 반영 되돌림은 기존 정책을 유지한다.
- 수동 기입고 건은 **예정 수량**과 ERP 확정 수량을 대조하여 COMPLETED 연결만 기록한다. 추가 입고는 없다.
- 입력·수량 오류: `400 VALIDATION_FAILED`, `details.fields.<경로>`(공통 Pydantic 검증은 `body.<경로>`). `422`는 기존 `IDEMPOTENCY_CONFLICT` 전용. 정책 충돌은 `409 PRECONDITION_NOT_MET` + `details.reason`; 참조 삭제/변경은 기존 `REFERENCED_BY_OTHERS`.
- digest는 invoiceNo, 품목·기본단위·기본단위 수량, 원천 qty/unit/factor의 정렬된 의미 값만 포함한다. 날짜·시각과 표시 순서는 제외한다. Decimal 환산은 소수3자리 초과를 반올림하지 않고 거부한다.
- snapshot.confirmedAt은 표시용이다. 게스트 복사 시 이 날짜·시각은 기존 일수 오프셋만 적용하고 digest는 원문을 복사한다. IN/검수 전표 sourceKey/sourceRef 번호도 같이 이동한다. businessKey는 그대로 보존한다.
- 신규 명령 시각은 DB `clock_timestamp()`에서 얻는다. 검수의 inspectedAt/claim.closedAt/postedAt/movedAt은 한 번 얻은 시각을 공유한다. 전표일·월과 IN/WD 번호 날짜는 해당 시각의 서울 날짜다. expectedOn은 사용자 예정일이며 FS_TODAY를 신규 처리 시각에 사용하지 않는다.
- 기존 W-03은 inspection_pending/inspected/inspected_cancelled를 각각 검수 대기/완료/검수 후 원천 취소로 표시한다. 전표가 NULL인 전량 부족도 안전하게 표시하며 새 전표 유형 WMS_INSPECTION 이름을 지원한다. 입고 화면은 만들지 않았다.
- 삭제된 초안 번호 사이에 빈자리가 있어도 검수 전표가 기존 번호와 충돌하지 않도록 발번을 현재 최대 번호+1로 보강했다. 검수 요청 줄 순서가 바뀌어도 필드 오류는 실제 입력 위치를 가리킨다.
- 위치 유형 API 추가. 격리 위치는 기본 위치 불가. 진행 예정이 참조하는 마스터 비활성화 및 참조 위치 삭제/유형 변경을 막는다.

## API

아래 경로는 `/api/v1/wms` 상대 경로다. 쓰기는 기존 CSRF 및 Idempotency-Key가 필요하다.

| 경로 | 기능 |
|---|---|
| GET/POST /inbound-notices | 상태/창고 필터·page/pageSize, 예정 생성 |
| GET/PATCH /inbound-notices/{id} | 상세, PLANNED 전체 편집 |
| POST /inbound-notices/{id}/source-link | 확정 ERP 매입 연결 또는 사후 대사 |
| POST /inbound-notices/{id}/source-unlink | 검수 전 선점 해제 |
| POST /inbound-notices/{id}/arrive | 트럭/수동 도착 공용 서버 명령 |
| POST /inbound-notices/{id}/cancel | 예정 취소 및 선점 해제 |
| POST /inbound-notices/{id}/inspect | 검수 원자 확정 |

기존 sources/sync 응답에 deferred/inspected 수 추가. 검수 경유 응답의 documentId가 NULL일 수 있다. 기존 stock/dashboard의 가용 수량 의미 변경은 b2다.

## 검증

**백엔드 전체 pytest755개 통과(20분04초, 기존 사용중단 경고2개).** 도구 전체 pytest58개 및 subtests13개 통과. 신규 입고 API23개 통과, 기존 WMS 프런트 호환 테스트10개(신규3개 포함) 통과, TypeScript 타입 검사·변경 프런트 ESLint 통과. CI 범위 ruff check/format(134파일), 격리 감사 R1~R6(98테이블/225FK) 오류0, 정적 DB 검증 오류0. 신규 `test_wms_receiving.py`는 수량 원자성, 실제 두 PostgreSQL 연결 경합, ERP 취소/변경, 환산, 날짜 제외 digest, 복사, 범위 격리, 마스터 보호, 오류 규약과 멱등을 다룬다. 기존 test_wms.py가 직접 매입 취소의 1회 되돌림을 회귀 검증한다.

### 인수 기준 연결

| AC | 검증 근거 | 경계 |
|---|---|---|
| 140 | 도착 재요청·상세 재조회, 도착 원장0 | 3D 연출은 후속 |
| 141 | 100 예정→95/3/2, 전표 이동2줄·총98 | 예약가능95 조회는 b2 |
| 142 | 전량부족→COMPLETED·전표NULL, 후속 sync 증가0 | 검수 결과는 보존 |
| 143 | 합계/음수/정밀도/누락/중복/외부줄/사유 오류400, 원장·version·claim 불변 | 입력 줄 순서도 검증 |
| 144 | 별도 PostgreSQL PID 2개·barrier 경합: 직접sync vs 선점, sync vs 검수 | 중복 원장0 |
| 145 | 선점 건 deferred1 + 다른 매입 synced1 | 동일 배치에서 정상 건 처리 |
| 146 | 타 예정 선점 거부, 해제/취소 후 재연결, 직접반영 이력 연결 거부 | 공간 잠금 안에서 재검사 |
| 147 | 수동 검수 뒤 원천 대사 COMPLETED, 원장 불변·후속 sync 증가0 | 실수령 아닌 예정 수량 대조 |
| 148 | 원천 취소/수량/환산 변경 시 확정 보류, 원장 불변 | 시각 변경만 있으면 digest 동일 |
| 149 | 검수 후 ERP 취소 경고·원장 보존; 기존 직접매입 되돌림은 test_wms 회귀 | 자동 검수 되돌림 없음 |
| 150 | BOX→EA snapshot, 환산누락/자리수초과 거부, 소수0.125 KG·줄 순서 정규화 | 반올림 없음 |

추가: ERP 끄기/수동 검수, 타 공간·초기화 이전 ID404, 복사 날짜·번호·digest, 마스터 보호, stale version409·같은 멱등 키 다른 본문422를 검증했다. AC-159~164 전체 완료를 의미하지 않는다.

재현: migration head가 적용된 전용 `*_test` DB에 DATABASE_URL/TEST_DATABASE_URL을 안전하게 설정한 다음 저장소 루트에서 실행한다. 실제 운영 DB로 실행하지 않는다.

```sh
backend/.venv/bin/pytest backend/tests -q --tb=short
uv run --project backend ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
uv run --project backend ruff format --check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
python3 tools/audit_schema_isolation.py
```

미실행: 새 입고 화면/3D 브라우저 검증, 운영 migration·배포. push/배포하지 않았다. 다음은 **사용자 b1 확인 후 b2**다.

보조 확인: 설정 자동 탐색 ruff는 import 정렬 I001 18건을 보고했지만 해당 파일은 main6508599와 모두 동일하다. 저장소 CI(.github/workflows/ci.yml)·HANDOFF에 지정된 명시 설정 명령은 check/format 모두 통과했다. 이 작업과 무관한 main 파일은 변경하지 않았다.


최종 구현 커밋: `a832fa8`(앞선 WIP `16045ae` 포함). 최종 보고 커밋은 `git log -1`로 확인한다. 전용 테스트 DB `factory_studio_codex_fs026b1_final_test`에서 head 적용 후 전체 pytest를 실행했다. 공유 개발/운영 DB 변경은 없다.
