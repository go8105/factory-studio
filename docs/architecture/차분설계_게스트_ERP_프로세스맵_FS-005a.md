# FS-005a 차분 설계 — 게스트 체험 · ERP-1 · 프로세스 맵

작성일: 2026-09-20. 상태: 논리 설계 차분 확정, 물리 DDL·메타데이터·Excel 미반영.
기준: [FS-005 공통 ERD](공통ERD_데이터관계_FS-005.md), [FS-006 상태·권한·트랜잭션](상태_권한_트랜잭션_FS-006.md), [FS-007 DB 설계서](../db/README.md).
성격: FS-005~007을 **대체하지 않는 순증 차분**이다. 기존 36개 테이블과 AC-01~44는 유효하며 이 문서는 그 위에 더한다.

---

## 1. 제품 전제 변경 (FS-005 대비)

FS-005 작성 시점 이후 사용자 확인으로 아래가 확정되었다.

| 항목 | FS-005 시점 | 확정 내용 |
|---|---|---|
| 최종 목적 | 실습 플랫폼 | **포트폴리오 제출용 교육 전용.** 실제 운영 데이터 투입 없음 |
| 진입 구조 | 아이콘 홈 | **Odoo식 단일 앱 런처로 전 모듈 통합 진입** 확정 |
| 생산 방식 | 미정 | **MTS(재고생산)** 확정. MTO는 확장 지점만 예약 |
| 업무 범위 | 작업지시→LOT→3공정 | **판매계획 → 출하·매출 전 구간** |
| 구현 모듈 | MES/FEMS/BEMS | **MES · FEMS · ERP · learning · 관리자** |
| 준비 중 모듈 | QMS/WMS/ERP | **QMS · WMS · BEMS** (설명 카드 필수) |
| 게스트 진입 | 없음 | **가입 없이 즉시 체험 가능** |
| 마감 기한 | 12~14작업주 추정 | 기한 없음. 범위 우선 |

### 1.1 철회한 검토안

운영 전환을 전제로 검토했던 `tenant_type = LIVE / SANDBOX` 분리는 **철회한다.** 운영 데이터가 유입되지 않으므로 FS-005의 범위 키 `S = (workspace_id, generation_id)`와 주간 세대 초기화 정책은 그대로 유지한다. 전 테이블 키 재작업은 발생하지 않는다.

### 1.2 ERP 범위 단계 구분

| 단계 | 범위 | 이번 결정 |
|---|---|---|
| ERP-1 | 거래처, 판매계획, 수주, 출하지시, 출하, 매출 | **이번 차분에 포함** |
| ERP-2 | 매입, 채권채무, 수금/지급 배분, 잔액·연령 | 후속 재판단 |
| ERP-3 | 계정과목, 전표, 전기, 역분개, 시산표 | 보류 |
| 전자세금계산서 | 팝빌 연동, 모의/테스트 발행 | **제외.** 사업자 등록·계약·인증 선행 조건이 충족되지 않고 투입 대비 회수가 낮다 |

`아키텍처_및_ERP_확장기획.md`의 ERP v1 전체 범위는 요구사항 추적용으로 보존하되, 현재 구현 약속은 ERP-1이다.

---

## 2. 차분 A — 게스트 체험 공간

### 2.1 설계 목적

포트폴리오 심사자가 회원가입 없이 3분 안에 업무 화면에 도달해야 한다. FS-005의 `core.workspace.owner_user_id UNIQUE`(계정 1개당 공간 1개)만으로는 이 경로가 성립하지 않는다.

### 2.2 core.workspace 변경

| 컬럼 | 변경 | 내용 |
|---|---|---|
| `owner_user_id` | **NULL 허용으로 변경** | 게스트 공간은 계정이 없다 |
| `workspace_kind` | **신규** | `MEMBER` / `GUEST`. 정책 분기의 단일 기준 |
| `guest_session_key` | **신규, nullable** | 게스트 식별용 난수 해시. 쿠키 세션과 대응 |
| `expires_at` | **신규, nullable** | 게스트 공간 만료 시각 |

제약:

- `owner UNIQUE`는 전체 UNIQUE에서 **부분 유니크 인덱스**로 전환한다. `UNIQUE (owner_user_id) WHERE workspace_kind = 'MEMBER'`.
- `guest_session_key`도 부분 유니크로 둔다. `UNIQUE (guest_session_key) WHERE workspace_kind = 'GUEST'`.
- CHECK: `MEMBER`는 `owner_user_id NOT NULL` 그리고 `guest_session_key IS NULL` / `expires_at IS NULL`. `GUEST`는 그 반대.
- 기존 업무 행의 범위 키 `S`는 변하지 않는다. 게스트 공간도 일반 workspace이므로 세대·격리 정책을 그대로 받는다.

### 2.3 게스트 정책

| 행위 | 게스트 | 회원 | 관리자 |
|---|---|---|---|
| 업무·학습 실행 | 허용 (본인 공간) | 허용 | 허용 |
| 모듈 활성/비활성 | 허용 (본인 공간) | 허용 | 허용 |
| 학습 진도 저장 | 허용, 만료 시 소멸 | 보존 | 보존 |
| 관리자 대시보드 | 차단 | 차단 | 허용 |
| 콘텐츠 수정·게시 | 차단 | 차단 | 허용 |
| 타 공간 접근 | 차단 | 차단 | 명시 권한 + 감사 필요 |

### 2.4 게스트 공간 생성과 정리

- 생성: "데모로 둘러보기" 요청 시 workspace + 초기 세대 + seed 데이터를 **하나의 트랜잭션**으로 준비하고, 검증 후 `active_generation_id`를 설정한다. FS-006의 세대 전환 계약을 재사용한다.
- 만료: 기본 24시간. `expires_at` 경과분을 정리 작업이 회수한다.
- 정리 작업: **신규 테이블을 만들지 않고** `core.job_run`에 `job_kind = 'guest_cleanup'`으로 기록한다. 실행 키는 정리 대상 일자로 두어 중복 실행을 막는다.
- 삭제 순서는 FS-007의 RESTRICT 설계에 따라 자식 → 부모 순으로 수행한다.
- 동시 게스트 공간 수 상한을 둔다. 상한 초과 시 만료 임박 공간부터 회수하고, 그래도 부족하면 생성을 거부하고 사유를 표시한다.

### 2.5 범위 외 (명시)

- **게스트 → 회원 승격 시 데이터 이관은 구현하지 않는다.** 가입 시 새 공간을 만든다. 이관은 공간·세대 재바인딩과 학습 근거 이전이 필요해 비용 대비 가치가 낮다.
- 게스트에게 이메일·개인정보를 요구하지 않는다. 수집 항목이 없으므로 저장도 없다.

---

## 3. 차분 B — ERP-1 (신규 10개 테이블)

스키마 `erp`. 모든 업무 행은 범위 키 `S`를 가지며 FK는 `(S, 참조id)` 복합 참조를 따른다.

| 엔티티 | 주요 속성 | 고유성·책임 |
|---|---|---|
| `erp.partner` | S, partner_code, 이름, 구분(고객/공급처), 활성 | (S,partner_code) UNIQUE |
| `erp.sales_plan` | S, plan_code, 대상 연월, 상태(작성/확정), 확정 시각 | (S,plan_code) UNIQUE. 확정 후 라인 변경 금지 |
| `erp.sales_plan_line` | S, sales_plan_id, item_id, 계획수량, 단위 | (S,plan,item) UNIQUE. 수량 ≥ 0 |
| `erp.sales_order` | S, order_no, partner_id, 수주일, 납기, 상태 | (S,order_no) UNIQUE |
| `erp.sales_order_line` | S, sales_order_id, 행번호, item_id, 수주수량, 단위, 단가 | (S,order,행번호) UNIQUE |
| `erp.shipment_order` | S, ship_order_no, sales_order_id, 지시일, 상태 | (S,ship_order_no) UNIQUE |
| `erp.shipment_order_line` | S, shipment_order_id, sales_order_line_id, 지시수량 | (S,shipment_order,sales_order_line) UNIQUE |
| `erp.shipment` | S, shipment_no, shipment_order_id, 출하 시각, 상태 | (S,shipment_no), (S,shipment_order) UNIQUE |
| `erp.shipment_line` | S, shipment_id, shipment_order_line_id, packing_unit_id, 출하수량 | (S,shipment,packing_unit) UNIQUE |
| `erp.sales_record` | S, shipment_id, partner_id, 공급가액, 세액, 합계, 인식 시각 | **(S,shipment_id) UNIQUE** |

### 3.1 정합성 계약

- **TX-07 출하지시 생성**: 수주 라인별 `Σ 지시수량 ≤ 수주수량`. 초과 지시를 거부한다.
- **TX-08 출하 확정**: 출하 라인의 packing_unit이 ① 완제품 입고 완료 상태이고 ② 다른 출하에 이미 사용되지 않았음을 같은 트랜잭션에서 검증한다. `erp.shipment_line`의 `(S, packing_unit_id)` UNIQUE로 이중 출하를 차단한다.
- **TX-09 매출 인식**: 출하 확정과 **같은 트랜잭션**에서 `sales_record` 1건을 생성한다. `(S, shipment_id)` UNIQUE가 중복 인식을 막는다.
- 금액은 NUMERIC을 사용한다. 세액 계산·반올림 규칙은 단일 정책 함수로 관리한다.
- `sales_plan`은 계획이며 재고를 구속하지 않는다. 계획 대비 실적 비교는 조회 계산으로 처리하고 별도 합계 컬럼을 중복 저장하지 않는다.
- WMS 미구현 상태이므로 **재고 차감의 근거는 `mes.finished_goods_receipt`와 출하 이력의 대사**다. 별도 재고 원장을 만들지 않는다. WMS 도입 시 원장 소유를 WMS로 이관한다.

---

## 4. 차분 C — MES 순증 (신규 5개 테이블 + 컬럼 2개)

| 엔티티 | 주요 속성 | 고유성·책임 |
|---|---|---|
| `mes.production_plan` | S, plan_code, 대상 연월, 상태, 근거 sales_plan_id | (S,plan_code) UNIQUE |
| `mes.production_plan_line` | S, production_plan_id, item_id, 계획수량, 계획 주차 | (S,plan,item,주차) UNIQUE |
| `mes.packing_unit` | S, packing_no, 유형(BOX/PALLET), parent_packing_unit_id, 상태 | (S,packing_no) UNIQUE. 자기참조 순환 금지, BOX의 부모는 PALLET만 |
| `mes.packing_member` | S, packing_unit_id, lot_id, 수량 | (S,packing_unit,lot) UNIQUE |
| `mes.finished_goods_receipt` | S, packing_unit_id, 입고 시각, 상태 | (S,packing_unit) UNIQUE |

`mes.work_order` 컬럼 추가:

| 컬럼 | 내용 |
|---|---|
| `order_type` | `STOCK` / `ORDER`. **이번 구현은 STOCK만 허용**하고 ORDER는 CHECK로 차단한다 |
| `sales_order_line_id` | nullable. MTO 확장 예약 지점. STOCK에서는 NULL |

> MTO 확장 질문("왜 MTS인가")에 대한 답을 컬럼 2개 비용으로 설계에 남긴다. 구현하지 않은 값을 선택 가능한 것처럼 표시하지 않는다.

### 4.1 정합성 계약

- **TX-10 패킹**: `Σ packing_member.수량 ≤ 해당 LOT의 확정 양품수량 − 이미 패킹된 수량`. 확정 실적이 없는 LOT은 패킹할 수 없다.
- **TX-11 완제품 입고**: PALLET 입고 시 하위 BOX가 모두 패킹 완료 상태여야 한다. 입고 후 구성 변경을 금지한다.
- 바코드는 별도 테이블을 만들지 않는다. `lot_no`와 `packing_no`를 표시 코드로 사용하고 **발행은 화면 기능**으로 처리한다. 코드 생성 규칙은 seed·서비스 정책으로 관리한다.

---

## 5. 차분 D — 프로세스 맵 (신규 3개 테이블)

스키마 `process_map`. **업무 데이터가 아니라 콘텐츠**이므로 범위 키 `S`를 갖지 않는다. learning 콘텐츠와 같은 보존 정책을 따른다.

| 엔티티 | 주요 속성 | 고유성·보존 |
|---|---|---|
| `process_map.map_version` | map_key, version, 제목, 게시 상태 | (map_key,version) UNIQUE. 게시 후 불변 |
| `process_map.node` | map_version_id, node_key, 표시 순서, 소유 모듈, 구현 수준, 업무 카드 본문 | (map_version,node_key) UNIQUE |
| `process_map.edge` | map_version_id, from_node_id, to_node_id, 연결 설명 | (map_version,from,to) UNIQUE. 자기 연결 금지 |

- `구현 수준`은 `IMPLEMENTED` / `MAP_ONLY` 두 값이다. `MAP_ONLY` 노드를 클릭하면 **빈 화면이 아니라 역할·연결·향후 계획 카드**를 표시한다. 준비 중 모듈이 미완성이 아니라 설계된 확장 지점으로 읽히게 하는 장치다.
- 노드 본문 항목은 FS-003 업무 카드 규격(목적, 수행자, 시작 조건, 입력/기준정보, 정상 순서, 산출물, 다음 업무, 자주 발생하는 오류, 완료 기준)을 재사용한다.
- 노드와 실제 화면의 연결은 `node_key → 라우트 키` 매핑으로 두고, 업무 테이블에 FK를 걸지 않는다. 세대 교체·모듈 비활성화가 맵을 깨뜨리지 않아야 한다.

노드 정의 내용은 [MTS 전체 흐름 노드 정의서](MTS_전체흐름_노드정의서_FS-005a.md)를 기준으로 한다.

---

## 6. 차분 E — 관리자 역할 (테이블 추가 없음)

FS-005의 `core.role` / `core.user_role`을 그대로 사용하고 `role_key = 'platform_admin'`을 배포 시 등록한다.

관리자 화면 범위는 **목록·진도·차단 검증**으로 제한한다.

| 화면 | 포함 | 제외 |
|---|---|---|
| 사용자 목록 | 계정, 공간 종류, 최근 활동 시각 | 개인 식별 상세 |
| 학습 진도 | 과정·단계별 완료/중단 위치, 오류 유형 | **학습자 개인 순위** (FS 기준 문서에서 금지) |
| 접근 감사 | `core.audit_event` 조회 | 타 사용자 업무 데이터 직접 열람 |

관리자의 타 공간 업무 데이터 접근은 기본 미허용을 유지한다. 지원 목적 접근이 필요해지면 별도 명시 권한과 감사 기록을 함께 설계한다.

---

## 7. 수용 기준 순증 (AC-45 ~ AC-58)

FS-004/FS-006의 AC-01~44에 이어서 번호를 부여한다.

| ID | 수용 기준 |
|---|---|
| AC-45 | 가입하지 않은 방문자가 데모 진입 후 업무 화면에 도달하고 첫 업무를 실행할 수 있다 |
| AC-46 | 게스트 공간 생성 중 실패하면 부분 생성물이 남지 않고 사유를 표시한다 |
| AC-47 | 서로 다른 게스트 세션의 업무·학습 데이터가 상호 조회되지 않는다 |
| AC-48 | 만료된 게스트 공간이 정리되고, 같은 일자 정리 작업이 중복 실행되지 않는다 |
| AC-49 | 동시 게스트 공간 상한 초과 시 생성이 거부되고 사유가 표시된다 |
| AC-50 | 게스트가 관리자 화면과 콘텐츠 게시 API에 접근할 수 없다 |
| AC-51 | 수주수량을 초과하는 출하지시가 거부된다 |
| AC-52 | 이미 출하된 패킹 단위를 다른 출하에 사용할 수 없다 |
| AC-53 | 출하 확정 시 매출이 정확히 1건 생성되고, 같은 요청 재전송으로 2건이 생기지 않는다 |
| AC-54 | 확정 양품수량을 초과하는 패킹 수량이 거부된다 |
| AC-55 | 입고 완료된 팔레트의 구성 변경이 거부된다 |
| AC-56 | `order_type = ORDER` 작업지시 생성이 거부된다 |
| AC-57 | `MAP_ONLY` 노드 선택 시 설명 카드가 표시되며 미구현 화면으로 이동하지 않는다 |
| AC-58 | 모듈 비활성화 또는 세대 교체 후에도 프로세스 맵이 정상 표시된다 |

---

## 8. 테이블 총계 변화

| 구분 | 수 |
|---|---|
| FS-007 기준 | 36 |
| erp 신규 | 10 |
| mes 신규 | 5 |
| process_map 신규 | 3 |
| **합계** | **54** |

컬럼 변경만 발생하는 테이블: `core.workspace`(+3, 제약 변경), `mes.work_order`(+2).

---

## 9. 미반영 항목과 검증 한계

- **`docs/db/schema-metadata/schema.json`과 `DB설계서.xlsx`는 이번 차분을 반영하지 않았다.** AGENTS.md의 "같은 작업에서 설계서를 갱신한다" 규칙에 따라 **FS-007a로 분리해 후속 수행**한다. 현 Excel 생성기는 Codex 번들 Node와 `@oai/artifact-tool` 의존이 있어 실행 환경 정리가 선행되어야 한다.
- 물리 DDL, migration, seed, API, 실제 PostgreSQL 검증은 모두 미수행이다. 본 문서는 논리 설계 차분이다.
- FS-006의 트랜잭션 계약 TX-01~06에 TX-07~11을 더했으나, 락 순서·격리 수준 재검토는 FS-006 개정 시 수행한다.
- 컬럼별 타입·NULL·CHECK 확정은 FS-007a 범위다.
- ERP-2/ERP-3 편입 여부는 ERP-1 완료 후 재판단한다. 현재 일정에 포함하지 않는다.

## 10. 다음 작업

FS-007a — 메타데이터·Excel 설계서에 본 차분 반영 및 정적 검증 재실행. 사용자 확인 후 착수한다.
