# CMMS — 설비보전

## 현재 기준 (2026-10-01, FS-029)

- 상태: **설계 중** — 결정서 확정(2026-10-01), 모듈·화면 설계 초안 · 전체 설계 확인 대기. 로드맵 2번.
- 설계: [CMMS 모듈 설계서](CMMS_모듈설계_FS-029.md) · [결정서 FS-029](../../plan/CMMS도입_설비보전_결정_FS-029.md) · [화면 설계](../../ui/화면설계_CMMS_FS-029.md)
- 읽는 조회: MES `equipment`(추가 예정) · BEMS `hvac_units`·`active_alarms`(신규 예정) · SPC `equipment_signals`(추가 예정)

### 제공 조회 함수 (`backend/src/fs/cmms/interface.py`, 예정)

| 함수 | 돌려주는 것 | 쓰는 곳 |
|---|---|---|
| `enabled()` | 사용 여부 | — |
| `equipment_in_maintenance(codes)` | 진행 중 고장 작업지시가 있는 MES 설비 코드 집합 | MES(M-05·M-11 "보전 중" 배지) |

모든 함수의 앞 두 인자는 `(connection, scoped)`이고, 이 솔루션이 꺼져 있으면 `None`을 돌려준다.

## 규칙

- 설계 확인 전에는 `schema.json`·마이그레이션·제품 코드를 만들지 않는다. 확인 뒤 FS-029a(DB) → b(API·화면) → c(시드·도움말·통합 검증). 절차는 [새 솔루션 킷](../../plan/새솔루션_킷.md).
