# BEMS — 건물 에너지

## 현재 기준 (2026-09-30, ROADMAP-01)

- 상태: **보강 중(DSN-16)** — 9화면(B-01~08·B-10) + 포털 P-08 휴일 달력. 기능 추가는 [로드맵](../../plan/로드맵_17개시스템_ROADMAP-01.md)의 "살 붙이기" 단계에서만 한다. 다른 솔루션이 요청하는 **조회 함수 추가는 동결 중에도 허용**한다.
- 설계: [BEMS 모듈 설계서](BEMS_모듈설계_FS-025.md) · **보강 설계: [DSN-16](BEMS_보강설계_DSN-16.md)**(ROADMAP-02 — 27기능 중 21 범위, 10 → 21테이블 + core.holiday, 화면 13. 휴일 달력·조명·피크 감축·쾌적도·건물 에너지 보고. 설계 완료·**DB 반영 완료(BEMS-1a, 2026-11-07, 마이그레이션 `bems1`)**. **1b 교차 조회·1c 휴일·조명·건물·1d 쾌적도·지표 6종·설비 경보 완료, 1e 피크 감축부터 남음**) · [결정서 FS-025](../../plan/BEMS도입_공용에너지_결정_FS-025.md)
- 읽는 조회: FEMS `site_electricity`·`manufacturing_electricity`·`tariff_rates(month)`·`open_alarms()` · core `holidays(from, to)` · HR `departments()`(구역 사용 부서)

### 제공 조회 함수 (`backend/src/fs/bems/interface.py`)

`hvac_units()`·`active_alarms()`(CMMS가 읽는다, 환경 경보만) · `monthly_summary(month)`(확정한 월간 보고서의 공용 kWh·EUI·비용·목표 달성·쾌적 비율, EIP용 — BEMS-1b). BEMS가 읽는 것: FEMS `tariff_rates(month)`(시간별 전력 단가, TOU·휴일 해석은 FEMS가 끝낸 값)·`open_alarms()`, core `holidays(from, to)`(`fs/core/interface.py`).

> 아래는 작성 당시 메모다. 위 "현재 기준"과 다르면 위가 우선한다.

- 업무 범위: 공용 계측, 환경 관측, 공용 에너지 집계
- 이 폴더의 문서: [BEMS 모듈 설계서 FS-025](BEMS_모듈설계_FS-025.md) · 결정서 [FS-025](../../plan/BEMS도입_공용에너지_결정_FS-025.md)

## 메모

- `bems` 10테이블은 schema.json v0.12.0·마이그레이션 `fs025a_bems`·`fs025b_bems_module`에 반영. R4 금지는 FS-025 D18로 해제. 서비스·화면은 아직 없다.
- FEMS와 계측 소유·집계 범위를 분리한다. 사업장 전체 = 제조 + 공용 + 미계측 잔여.
- 공용/미계측 분해 예시는 BEMS 설명 카드에 기재한다.

## 규칙

이 폴더에 모듈 공통 설계서가 없으면 해당 모듈은 개발 착수 대상이 아니다.
설계를 먼저 확정하고 사용자 확인을 받은 뒤 구현에 들어간다.

기준정보(건물·구역·계측기·센서·공조기·조명 회로·쾌적 기준·설비 경보 규칙)는 BEMS가 독립 소유한다(FS-013 D1). 환경 센서는 지표 6종(온도·습도·CO₂·미세먼지·조도·재실)이지만 **환경 경보 규칙은 3종**이고, **설비 경보는 공조기만** 본다(표에 `hvac_unit_id`만 있다). 휴일 달력은 core가 가지고 날짜로만 읽는다(DSN-16 Q1). 구역 사용 부서는 HR 코드 문자열이라 FK를 두지 않는다. FEMS 값은 FS-023 D9의 읽기 전용 조회 인터페이스로만 읽는다.

전체 현황은 [현재 기획과 진행 현황](../../plan/현재기획_진행현황.md)을 본다.
