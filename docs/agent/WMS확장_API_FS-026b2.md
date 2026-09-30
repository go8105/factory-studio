# FS-026b2 예약·출하 소진·가용 수량

2026-09-30. **구현 완료·전체 회귀 검증 중.** 브랜치 `codex/vision-ai`, 기준 `3f5039c` / `origin/main 6508599`.

## 범위와 흐름

사용자의 “진행방향 정해서 가자 1번부터” 승인에 따라 TX-W8~W9, AC-151~158을 구현했다. 기존 FS-026a 테이블을 사용하며 마이그레이션·schema.json·Excel·ERD는 변경하지 않았다. BEMS 포함 템플릿11,910 / 게스트복사11,908행 기준을 유지한다.

입고 검수 → 정상/격리 현재고 → 정상 위치의 품목·LOT별 예약 → ERP 확정 출하와 전량 대조 → 예약 위치에서 출고 원장 1회 생성 + 예약 CONSUMED가 기본 흐름이다. 취소할 예약은 사유를 적어 RELEASED로 바꾸면 원장 이동 없이 가용 수량이 복원된다.

- 가용 = 정상 위치 현재고 − ACTIVE 예약. ERP 미출하 수요는 비교 참고이며 다시 차감하지 않는다. 격리 재고는 별도 표시하고 예약할 수 없다.
- 새 예약은 가용 부족 시 409로 거부한다. 이후 기존 직접 출하·조정으로 재고가 줄어도 확정 사실은 D15대로 반영한다. 정상95/예약40에서 미예약 출하70이면 정상25/예약40/가용−15다. 위치·LOT별 부족을 다른 위치의 여유로 숨기지 않는다.
- 예약 생성·원장 쓰기·소진은 기존 workspace advisory lock 안에서 처리한다. 동시 예약 두 건이 같은 수량을 중복 선점할 수 없다.
- ERP 출하와 품목/기본단위 환산 수량 전량이 같아야 소진한다. 참고 출하지시가 있으면 번호도 같아야 한다. packingNo가 있으면 MES 입고 원장의 LOT 배분과 대조한다. 혼합·중복 팔레트 등 모호한 연결은 거부한다. RAW 예약은 생성/해제만 지원하고 고객 출하 소진은 FG만 지원한다.
- 기존 sync가 먼저 반영하면 소진은 SOURCE_ALREADY_POSTED 409, 예약은 ACTIVE로 유지한다. 소진이 먼저면 뒤 sync는 같은 ERP_SHIPMENT를 반환한다. 소진 재시도는 기존 결과를 반환한다. 부분 소진은 없다.
- ERP 비활성에도 수동 예약·해제·가용 조회는 동작한다. ERP 수요만 null이고 출하지시 비교는 unavailable이다. 상세에는 unlinked/missing/환산 불가/match/mismatch 비교 상태도 제공한다.
- ACTIVE 예약이 참조하는 마스터 비활성화를 막는다. 예약 이력이 참조하는 위치의 삭제/유형 변경도 보호한다.
- 입력·수량 오류는 400 VALIDATION_FAILED, details.fields.<경로>. 공통 모델 오류는 body.<경로>. 422는 IDEMPOTENCY_CONFLICT 전용이다. 부족·상태 충돌은 기존 409 규약을 쓴다.
- 처리 시각은 DB clock_timestamp. 소진 closedAt/postedAt/movedAt은 같은 시각이고 전표 날짜·번호는 그 서울 날짜다. ERP shippedAt은 참고 시각이며 FS_TODAY를 명령에 섞지 않는다. 기존 직접 sync의 원천 발생일 정책은 유지한다.
- 게스트 복사는 RSV 번호 날짜를 이동하고 예약·문서·품목·위치 FK를 새 세대로 재매핑한다. businessKey·출하 sourceKey는 보존한다. b1 snapshot 날짜 이동/digest 불변 정책은 유지한다.
- ERP 교차 조회는 fs/erp/interface.py만 사용한다. 업무 스키마 간 FK는 없다.

## API와 화면 호환

아래는 `/api/v1/wms` 상대 경로다. 쓰기는 기존 인증·CSRF·Idempotency-Key 규약을 따른다.

| 경로 | 내용 |
|---|---|
| GET/POST /reservations | 상태/품목 필터, 페이지 조회와 예약 생성 |
| GET /reservations/{id} | 줄별 현재 잔량/예약/가용, 출하지시 참고 비교 |
| POST /reservations/{id}/release | expectedVersion·reason으로 해제 |
| POST /reservations/{id}/consume-shipment | expectedVersion·sourceKey로 확정 출하 전량 소진 |
| GET /reservation-sources | ERP 사용 여부, 출하지시, 아직 반영하지 않은 확정 출하 |
| GET /stock | locationId 필터 추가; NORMAL/QUARANTINE/예약/가용/부족 |
| GET /dashboard | 현재 잔량·가용은 조회 월과 무관; 월별 흐름은 기존 유지 |

기존 W-01/02 화면에 정상/격리/예약/가용 및 부족 표시를 호환시켰다. ERP off 상태에서도 가용 숫자를 표시한다. 신규 입고 W-08/예약 W-09 조작 화면은 후속 단계다.

## 검증

현재 관련 WMS API **60 passed**(기존·b1 포함, b2 신규22), WMS 프런트10개·typecheck·변경 ESLint 통과. CI ruff check/format138파일, R1~R6 감사98테이블/225FK 오류0, db:validate 오류0. **전체 백엔드 pytest는 진행 중이며 아직 통과로 간주하지 않는다.**

| AC | 검증 근거 |
|---|---|
| 151 | 정상95/격리3에서 예약40 → 가용55; ERP 수요40 중복 차감 없음; AC141 가용 조회 보완 |
| 152 | 실제 PostgreSQL PID 두 개/barrier로 60+60 경합 → 한 성공/한 부족409 |
| 153 | 격리·FG LOT 누락·RAW LOT·정밀도·0·중복·후속 줄 부족 거부, 헤더/줄 원자성 |
| 154 | 정상95/예약40/직접출하70 → 정상25/예약40/가용−15; 신규 예약 거부 |
| 155 | 해제·다른 멱등키 재해제 시 원장0, version/시각/사유 보존 |
| 156 | 소진과 재시도·뒤 sync 전표1개; 재고 감소 후 소진도 허용하고 음수 경고 |
| 157 | 다른 출하키·수량·LOT·참고지시·혼합 팔레트 불일치 거부, 부분 반영0 |
| 158 | 별도 DB 연결 sync/소진 경합 → 출하 전표1개, 선행 경로별 상태 확인 |

추가로 ERP off, 마스터 보호, 게스트/세대 격리, 예약된 0현재고 행 유지, 다른 위치 여유가 부족을 숨기지 않는 집계, 조회 월 독립성, FS_TODAY와 무관한 서버 시각, ACTIVE/RELEASED/CONSUMED 게스트 복사를 검증했다.

재현(격리된 로컬 `*_test` DB URL을 DATABASE_URL/TEST_DATABASE_URL 환경에 제공; 비밀값 기록 금지):

```sh
backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/pytest backend/tests -q --tb=short
uv run --project backend ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
uv run --project backend ruff format --config backend/pyproject.toml --check backend tools/verify_ddl_matches_schema.py
python3 tools/audit_schema_isolation.py
npm run db:validate
npm --prefix frontend run typecheck
npm --prefix frontend test -- src/wms/wms.test.tsx
```

## 남은 작업

b2 최종 보고 후 사용자 확인을 기다린다. 다음은 W-08 입고 예정·도착·검수/W-09 예약 화면과 브라우저 업무 흐름 검증, 이후 3D 트럭 도착 연출, 합성 체험 시드·도움말·통합 점검이다. 새 UI의 브라우저 검증·운영 검증은 이번 범위에 포함하지 않았다. 공유 개발/운영 DB 변경, push·배포는 하지 않았다.
