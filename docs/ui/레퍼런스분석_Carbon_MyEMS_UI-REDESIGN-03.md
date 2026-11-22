# UI-REDESIGN-03 — 레퍼런스 분석: Carbon · MyEMS

2026-11-22 · Claude Code · **분석 문서. 제품 코드 변경 없음.**

사용자 질문: "시중 올인원 광고는 많은데, 깃허브에 이런 게 아직 없나?" → 있다. 그리고 **화면 구도를 배울 게 있다.**

대상: [crbnos/carbon](https://github.com/crbnos/carbon)(ERP+MRP+MES+QMS, AGPL-3.0, 별 2.9k) · [MyEMS/myems](https://github.com/MyEMS/myems)(에너지, 별 764)

> **라이선스 경고.** Carbon은 **AGPL-3.0**이다. 보고 배우는 것은 되지만 **코드를 가져오면 전염된다.** 이 제품은 공개 포트폴리오라 특히 그렇다. 이 문서는 화면 **구도**만 다룬다.

---

## 1. 두 제품의 규모

| | 이 제품 | Carbon | MyEMS |
|---|---:|---|---|
| 범위 | MES·ERP·WMS·QMS·FEMS·BEMS·SPC·CMMS·HR·GW | ERP·MRP·MES·QMS | 에너지·탄소 |
| 화면 | **152** | 모듈 15군(화면 수 미확인) | **약 88**(에너지만) |
| 앱 분리 | 하나의 포털 | **`apps/erp`(사무) + `apps/mes`(현장 태블릿)** 별도 앱·별도 포트 | 웹 UI + 관리 UI + 대형 화면 대시보드 |

**우리 FEMS 23 + BEMS 7 = 30화면. MyEMS는 에너지 하나로 88화면이다.** 범위는 우리가 넓고 깊이는 저쪽이 깊다.

---

## 2. Carbon 목록 화면 — 우리 표와 무엇이 다른가

판매주문 목록(`sales-orders-light.webp`)을 우리 ERP 견적(E-02)과 나란히 놓고 봤다.

| # | Carbon | 이 제품 | 평가 |
|---|---|---|---|
| 1 | **행마다 품목 썸네일 이미지**, 거래처마다 색 아바타 | 100% 글자 | **가장 큰 차이.** 표가 글자만이면 어떤 레이아웃도 단조롭다 |
| 2 | **Jobs 열에 연결된 업무 칩**(`1 JOB ⋮`) 또는 **⚠ 경고 아이콘** | 표는 자기 데이터만 보여 준다 | **두 번째로 큰 차이.** 행에서 다른 솔루션의 상태가 보인다 |
| 3 | 검색 한 칸 + **`Filter` 버튼 하나** | 조건 드롭다운을 늘어놓음 | 우리가 R2 2차 `FilterMore`로 간 방향과 **같다** ✔ |
| 4 | 표 우측 도구 아이콘 4개(정렬·**열 선택**·그룹·내보내기) | CSV 버튼 + (신규) 빈 열 접기 | 같은 계열 ✔ · **그룹**은 없다 |
| 5 | 상단 **브레드크럼** `Carbon Development / Sales / Orders` | 없음 | 152화면에 계층 단서가 없다 |
| 6 | 좌측 **아이콘 레일 사이드바(약 44px)** | 텍스트 사이드바 232px | 본문 폭 190px 차이 |
| 7 | 열 머리글에 아이콘(☆ Status, $ Order Total) | 글자만 | 작지만 스캔 속도가 다르다 |
| 8 | 상태 배지 4색 · 하단 `100 rows` + `1-24 of 24` | 배지 3톤 · 총 건수 | 비슷함 |

**결론: 우리 표가 단조로운 이유는 레이아웃이 아니라 셀에 담긴 것이 글자뿐이기 때문이다.**

---

## 3. Carbon 추적 화면 — 표가 아닌 화면

`traceability-light.webp`. **이게 "단조롭지 않음"의 실체다.**

- 상단에 **`Graph | Table` 토글** — 같은 데이터를 그래프로도 표로도 본다
- 노드 그래프: `Receive`(마름모) → `Split` → LOT 노드(원) → `Consume` → 완성품
- **엣지에 수량**(3000 / 2269 / 731 / 100)이 적혀 흐름이 보인다
- 우측 상세 패널: 상태 `CONSUMED` · 수량 · Serial/Batch · **`PRODUCED BY`** · **`CONSUMED BY`** · 속성
- 상단 컨트롤: `1 hop`(깊이), 방향, 레이아웃, `SPACING`

우리 WMS LOT 이력·MES LOT 이력(M-04)은 **표와 패널뿐**이다.

### 여기서 가장 중요한 발견

**`lot_trace`가 이미 구현돼 있다** — `backend/src/fs/mes/interface.py:557`. QMS-1e에서 만들었고 투입 자재와 계보를 양방향으로 돌려준다. 지금 소비처는 `qms/service.py` 하나뿐이다.

> **데이터는 이미 있고 화면만 없다.** 계보 그래프 한 장은 백엔드 작업 0으로 만들 수 있다. 비용 대비 효과가 이 문서에서 가장 크다.

---

## 4. MyEMS — 88화면의 비밀은 매트릭스

화면이 많은 게 아니라 **생성 규칙**이 있다.

```
대상 7종 × 분석 약 10종 = 88화면
대상: Meter · Space · Equipment · Tenant · Store · Shopfloor · Combined Equipment
분석: Dashboard · Energy Category · Energy Item · Carbon · Cost · Output ·
      Income · Efficiency · Load · Statistics · Comparison · Batch Analysis
```

우리 FEMS 23화면은 **기능을 하나씩 나열한 것**이다. MyEMS는 **(대상 × 분석) 격자**다. 그래서 "설비별 원단위"가 있으면 "구역별 원단위"도, "테넌트별 원단위"도 당연히 있다. **사용자가 다음 화면을 예측할 수 있다.**

### 최상위에 표가 아닌 화면을 둔다

`Energy Dashboard` · **`Energy Flow Diagram`**(산키) · **`Distribution System`**(단선도) · `Work Order Management` · `Knowledge Base`

### KPI 타일에 비교 기준이 있다

대시보드 KPI 6장이 각각 **증감 배지(`+0.12%` 등)** 와 **`Per Unit Area` · `Per Capita` 원단위**를 함께 쓴다.
우리 KPI는 숫자 + 설명뿐이라 **"이게 좋은 건지 나쁜 건지"를 말해 주지 않는다.** 대시보드가 밋밋한 큰 이유다.

---

## 5. Carbon 모듈 중 우리에게 없는 개념

`Projects` · `Service`(서비스/수리) · `Fulfillment`(출하를 Inventory와 분리) · `Automation & alerts` · `Configurator`(제품 구성) · `Change notices`(설계 변경) · `Supersession`(대체품)

이 중 **Change notices·Supersession**은 제조에서 흔한 업무인데 우리 MES·ERP에 없다. 범위 결정이지 결함은 아니다.

---

## 6. 제안 — 비용 대비 효과 순

| # | 할 일 | 비용 | 효과 |
|---|---|---|---|
| **1** | **LOT 계보 그래프 화면** — `lot_trace`가 이미 있다. `Graph \| Table` 토글, 엣지에 수량, 우측에 투입/산출 패널 | 중(프런트만) | **가장 큼.** 표가 아닌 화면이 하나도 없다 |
| **2** | **행에 맥락 넣기** — 행에 다른 솔루션 상태 칩. 예) MES 작업지시 행에 `QMS 보류`, WMS 재고 행에 `예약 2건`. 교차 조회 함수는 이미 많다 | 중 | 큼. 표가 살아난다 |
| **3** | **KPI에 비교 기준** — 전월·전년 대비 증감 배지 + 원단위. `stat-tile` 공통 변경이라 **10개 대시보드 일괄** | 소 | 큼 |
| **4** | **브레드크럼** — `SolutionLayout`에 한 줄. 152화면에 계층을 준다 | 소 | 중 |
| **5** | **FEMS를 (대상 × 분석) 격자로 재편** | 대 | 중(구조가 설명 가능해진다) |
| 6 | 행 썸네일·아바타 | 대(이미지 자산이 없다) | 중 |

**1·3·4는 백엔드 변경 0이다.**

---

## 7. 확인하지 못한 것

- Carbon의 **스키마 분리 방식** — README·문서에 없다. `packages/database`를 읽어야 안다. 우리 FS-013(스키마 분리·업무 FK 금지)과 비교할 지점이다
- Carbon 문서 사이드바는 대분류 15군만 보이고 **하위 화면 목록이 펼쳐지지 않았다**. 화면 수 비교 불가
- 두 저장소의 **최근 커밋 날짜·최신 릴리스** 미확인
- MyEMS **라이선스 명시 미확인**(README에 없음, LICENSE 파일 직접 확인 필요). README에 기본 계정이 그대로 적혀 있다
- Carbon 화면은 **README 스크린샷 4장**만 봤다. 실제 제품을 띄워 보지 않았다
