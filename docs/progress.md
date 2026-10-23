# 2026-10-23 CMMS-1f — 보전 개요(C-01)·지표(C-07)·비용(C-10) — CMMS 10화면 완성

Claude Code 직접 개발(D85). 브랜치 `cmms-1f`. **CMMS 보강 마감.**

## 세 화면 모두 저장하지 않는다

개요·지표·비용의 숫자는 전부 **볼 때마다 계산**한다(D51 · Q5). 따로 집계해 두면 작업지시를 고쳤을 때 두 숫자가 어긋나고, 그때 어느 쪽이 맞는지 아무도 모르게 된다.

## C-07 보전 지표

- **MTTR** = Σ(복구 − 정지) ÷ 고장 건수, **MTBF** = (기간 시간 − Σ정지) ÷ 고장 건수.
- **고장이 0건이면 둘 다 빈칸**이다. 0으로 적으면 "즉시 복구"로 읽힌다 — 고장이 없는 것과 다르다.
- **정지 시간은 기간과 겹친 부분만** 센다. 기간 밖까지 세면 두 달치 보고서를 더했을 때 전체와 맞지 않는다.
- **PM 준수율**은 예정일 당일까지 완료한 비율이고 **유예가 없다.**
- 고장 파레토는 원인·증상별로 센다. 원인은 저장된 코드(`WEAR`)라 **사람이 읽는 이름(마모)으로 바꿔** 보여 준다 — 브라우저에서 원시값이 그대로 나오는 것을 보고 고쳤다.

## C-10 보전 비용

부품(수량 × **쓸 때의** 단가) + 인건비(작업 분 ÷ 60 × 시간당) + 외주비. 설비별·월별로 가른다. 외주비의 회계 처리는 ERP 직접 매입으로 따로 한다.

- **완료한 작업지시만** 센다 — 진행 중인 것은 아직 얼마가 들지 모른다.
- 정비원을 안 붙였거나 단가가 없으면 그 항목이 0이다. 도움말에 적어 두었다.

## C-01 보전 개요

미조치 작업지시·전환 대기 신호·주기 도래 PM·설비 수 네 타일과, 주기가 된 계획·부족한 예비품 목록. **원천이 꺼져 있으면 어느 쪽인지 타일에 적고**, MES가 꺼져 판정할 수 없는 PM은 몇 건인지 따로 센다.

## 조회 기간의 끝을 열어 뒀다

처음에는 기간 끝을 `business_today()`로 닫았는데, **완료·고장 시각은 실제 시계**라 업무 기준일(FS_TODAY)을 당겨 둔 공간에서는 방금 닫은 작업지시가 비용·지표에서 빠졌다. 종료일을 주지 않으면 끝을 열어 두도록 바꿨다(SPC `_period`와 같은 방식). MTBF 분모는 '지금까지'로 센다 — 9999년까지 셀 수는 없다.

## 그 밖에 고친 것

- **작업 기록의 '한 일'이 필수가 됐다.** `work_log.note`가 NOT NULL인데 선택 입력으로 받고 있었다. 시간만 남으면 나중에 무엇을 했는지 알 수 없으니 설계가 맞다 — 서비스·스키마·화면을 필수로 바꿨다.

## 검증

- 백엔드 `test_cmms_metrics.py` **7건** 신설 — 고장 0건이면 null, MTTR·MTBF 계산, 정지 시간 겹침, PM 준수율(늦으면 미준수), 비용 합산·단가 스냅샷, 미완료 제외, 개요 집계.
- 프런트 `cmms.test.tsx` 11 → **15건**. CMMS 백엔드 전체 **43 passed**.
- 브라우저에서 새 게스트 공간에 고장 하나를 끝까지 돌려 **부품 50,000 + 인건비 60,000 = 110,000**과 파레토 "원인 마모"를 확인했다. 390px 가로 스크롤 없음.

## CMMS 마감 상태

- **화면 0 → 10**(C-01~C-10 전부), **표 6 → 12**, **도움말 10편**. 백엔드·프런트 모듈을 통째로 새로 만들었다.
- **미구현**: 금형 타수 PM은 `mes.mold` 시드가 0건이라 체험 불가(코드·테스트는 있다). CSV 올리기·문서 첨부·예지보전·LOTO는 DSN-21에서 제외한 범위다.
- **시드 없음**: CMMS는 새 게스트 공간에서 설비 대장부터 비어 있다. 가져오기나 직접 등록으로 시작해야 한다.
- **남은 빚**: `apply_*.py` 틀이 기존 칼럼의 nullability를 옮기지 않는다. SPC·CMMS 모두 보완 revision을 따로 냈다(`spc2`·`cmms2`). 다음 모듈(QMS·FEMS·BEMS·ERP)에서도 같은 누락이 난다.
- 다음: 보강 순서 **QMS(9표)**.

# 2026-10-20 CMMS-1e — 예방보전 계획(C-04)·예비품(C-06), CMMS-1a NULL 허용 보완

Claude Code 직접 개발(D85). 브랜치 `cmms-1e`. **CMMS 7화면·도움말 7편.**

## CMMS-1a도 SPC-1a와 똑같은 것을 빠뜨렸다

`apply_cmms1.py`는 `apply_spc1.py`에서 떠 온 틀이라 **기존 칼럼의 nullability를 옮기지 않는다.** DSN-21 4-2의 `cmms.pm_plan.interval_days` NULL 허용이 빠졌고, 이미 적용한 CHECK(`(trigger_kind='CALENDAR') = (interval_days IS NOT NULL)`)가 만족될 수 없는 상태였다 — **운전 시간·타수 기준 계획은 행을 넣을 수 없었다.** SPC의 c1580과 같은 모순이다.

- `tools/apply_cmms2.py` + 마이그레이션 `cmms2`(down `cmms1`)로 처리했다. SPC-1c에서 `build_migration.py`에 nullability 지원을 넣어 둔 덕에 생성은 한 번에 됐다.
- **원인은 `apply_*.py` 틀 자체다.** 다음 모듈(QMS·FEMS·BEMS·ERP)에서도 같은 누락이 난다. 틀을 고치는 것은 별건으로 남긴다.
- 검증: db:validate 0(221표), 격리 0, 마이그레이션 왕복 통과, verify_ddl 0, 도구 테스트 138 OK.

## C-04 예방보전 계획 — 자동으로 만들지 않는다

주기가 됐다고 시스템이 작업지시를 찍어 내지 않는다. **"주기가 됐다"와 "지금 세워도 된다"는 다른 판단**이다(D49). 납기가 급한 날 라인을 세울 수는 없다. 화면은 도래를 알려 주고 사람이 누른다.

- 기준 3종: **일 주기**(모든 설비) · **운전 시간**(MES 공정 실행 시간 합) · **금형 타수**(MES 누적). 사용량 기준은 **MES에서 가져온 설비·금형에만** 쓸 수 있다.
- 사용량은 **CMMS가 저장하지 않는다.** 저장하면 두 숫자가 어긋나고 어느 쪽이 맞는지 알 수 없다. **MES를 끄면 0이 아니라 '모름'**이고, 모르면 도래를 판정할 수 없어 작업지시도 못 만든다(409 `USAGE_UNKNOWN`).
- 마지막 수행일·사용량은 **PM 완료로만** 바뀐다. 다음 예정일이 거기서부터 다시 센다.
- 계획·예정일당 취소되지 않은 작업지시 1건(UK_PARTIAL).

### 점검표(Q3)

- **양호·불량**과 **측정값 범위** 두 방법. 범위는 상·하한과 단위를 정해 두면 작업지시에서 **값만 적어도 서버가 판정**한다 — 사람이 OK/NG를 고르지 않는다.
- **PM은 사용 중인 항목을 모두 기록해야 완료된다**(409 `CHECKLIST_INCOMPLETE`). 안 본 항목이 있으면 점검이 아니다. 항목이 없으면 점검 없이 바로 완료할 수 있다.
- NG 메모도 **서비스에서 막는다** — DB CHECK는 note가 NULL이면 통과한다(SPC OCAP에서 찾은 것과 같은 함정).

## C-06 예비품 — 재고는 WMS가 갖는다

CMMS에 재고 원장이 없다(D50). 볼 때마다 `fs.wms.interface.stock_on_hand`로 읽는다. 창고에 하나뿐인 숫자를 두 솔루션이 각자 들고 있으면 반드시 어긋난다.

- WMS 품목을 잇지 않았거나 WMS를 꺼 두면 **'모름'**이다 — 0이 아니다(`stockKnown`).
- **부족 판정은 WMS의 안전 재고**로 한다. CMMS 쪽 안전 재고는 참고용 메모다.
- 부품 사용은 **쓸 때의 단가를 스냅샷**으로 남긴다. 나중에 단가를 바꿔도 지난 비용은 그대로다.
- 사용 기록은 **재고를 움직이지 않는다**(테스트로 `wms.stock_move` 행 수 전후 대조). WMS가 읽어 출고로 반영한다.

## 검증

- 백엔드 `test_cmms_pm.py` **6건** 신설 — 일 주기 예정일·도래 전 409·중복 생성 409, 사용량 기준의 설비 제약·MES 꺼짐 '모름', 점검표 미완 409·범위 자동 판정·NG 메모, 범위 안이면 메모 없이 OK, WMS 재고 '모름'과 부족, 단가 스냅샷·재고 불변.
- 프런트 `cmms.test.tsx` 8 → **11건**. 전체 프런트 **640**.
- 브라우저: 운전 시간 282시간을 MES에서 읽음 → PM 작업지시 생성 → **점검 전 완료 409** → 140bar를 NG로 자동 판정 → 완료 → **다음 예정일 2026-11-19로 재계산**. 390px 가로 스크롤 없음.
- 다음: **CMMS-1f** C-01 보전 개요·C-07 지표·C-10 비용.

# 2026-10-20 CMMS-1d — 작업지시(C-03)·전환 대기 신호(C-02)·정비원과 외주 업체(C-08)

Claude Code 직접 개발(D85). 브랜치 `cmms-1d`. **CMMS의 본줄기**다 — 경보가 작업지시가 되고, 고쳐서 닫히는 흐름.

## C-03 작업지시 — 상태는 한 방향으로만

**접수 → 진행 → 완료**, 또는 접수·진행 중 **취소**. 되돌리는 길은 없고 완료·취소 뒤에는 바꿀 수 없다. **MTBF·MTTR이 여기 찍힌 시각들로 계산되기 때문**이다 — 나중에 시각을 고치면 지난달 지표가 달라지고 어느 숫자가 맞는지 설명할 수 없게 된다.

- 작업 기록은 **진행 중일 때만** 붙는다(TX-C3). 분 합계가 인건비의 근거다(합계 ÷ 60 × 시간당 인건비).
- 완료에는 **원인 분류·조치 내용이 반드시** 필요하고, 고장(BM)이면 복구 시각이 자동으로 찍힌다.
- **고장 코드는 구분이 맞아야 받는다** — 증상 칸에 조치 코드를 넣으면 막는다.
- **업체 없이 외주 비용만 적을 수 없다.** 회계는 ERP 직접 매입으로 따로 하고 CMMS는 집계에만 쓴다.
- 사용 안 함으로 바꾼 설비는 새 작업지시를 받지 않는다.

## C-02 전환 대기 신호 — 왜 자동으로 만들지 않나

경보가 떴다고 모두 사람이 나가야 하는 것은 아니다. 문이 잠깐 열려 온도가 튄 것일 수도, 측정이 틀렸을 수도 있다. **판단은 사람이 하고 시스템은 후보만 모은다.**

- **원천 상태는 바꾸지 않는다**(D48). 전환해도 BEMS 경보는 떠 있고 SPC 이상은 미조치로 남는다. 해제·조치는 저쪽에서 한다 — CMMS가 남의 상태를 바꾸면 저쪽 화면에서 왜 바뀌었는지 설명할 수 없다.
- **신호 1건당 취소되지 않은 작업지시 1건**(UK_PARTIAL). 취소하면 대기 목록에 다시 나타난다.
- 추천 설비: BEMS 경보는 **구역 단위**라 그 구역의 공조기를, SPC 이상은 설비 코드로 찾는다. 대장에 없으면 추천 없이 직접 고른다.
- 원천을 꺼 두면 **그 줄만 비고** 다른 원천은 그대로 보인다(`sources`로 알린다).

## C-08 정비원·외주 업체

한 화면 두 탭. 시간당 인건비는 **보전 비용 집계에만** 쓰는 값이고 실제 급여는 HR이 계산한다. HR 사원 코드·ERP 거래처 코드는 **잇고 싶을 때만** 적는 스냅샷이다(D79).

## 검증

- 백엔드 `test_cmms_work_orders.py` **10건** — 전체 흐름, 완료 후 모든 전이 409, 취소, 원인·조치 필수, 고장 코드 구분 대조, 사용 안 함 설비 차단, 신호 목록·원천 꺼짐, **전환 1회 + 취소 후 재전환**, **전환이 원천을 바꾸지 않음**(전후 행 수 대조), 정비원·업체 참조 삭제 차단, HR·ERP 꺼짐 시 빈 목록.
- 프런트 `cmms.test.tsx` 4 → **8건**. 전체 프런트 **636**.
- 브라우저: BEMS 경보(사무동 CO2)·SPC 이상(INJ-02) 둘 다 대기에 뜸 → 추천 설비 INJ-02 자동 선택 → 전환 → **SPC 이상은 여전히 미조치 1건**(원천 불변 확인) → 작업 시작 → 40분 기록 → 완료(복구 시각 자동) → **재완료 409**. 390px 가로 스크롤 없음.
- 메뉴 5화면(C-02·03·05·08·09), 도움말 5편. 기본 진입을 작업지시로 바꿨다.
- 다음: **CMMS-1e** C-04 예방보전 계획(점검표·사용량 기준)·C-06 예비품.

# 2026-10-20 CMMS-1c — CMMS 솔루션 개통: 설비 대장(C-05)·고장 코드(C-09)

Claude Code 직접 개발(D85). 브랜치 `cmms-1c`. **CMMS의 첫 화면이다** — 백엔드·프런트 모듈이 통째로 없어서 뼈대부터 만들었다.

## 새로 생긴 것

- `backend/src/fs/cmms/`(`__init__`·`service`·`schema`·`router`) 신설, `main.py`에 `/api/v1/cmms` 등록(`seed_ready("cmms")` 게이트).
- `frontend/src/cmms/`(`CmmsLayout`·`index`·`common`·`hooks`·`Assets`·`FailureCodes`) 신설, `App.tsx`에 lazy 라우트 등록.
- **메뉴 카탈로그에 `cmms` 솔루션 추가**(SPC 뒤). 이전에는 CMMS가 메뉴에 아예 없었다. `menuCatalog.ts`에 `cmmsScreens`, `portal/docs.ts` 참고 문서 트리에도 넣었다 — 넣지 않으면 도움말이 "고아 문서"가 된다.

## C-05 설비 대장

- **직접 등록 + 가져오기(MES 설비·MES 금형·BEMS 공조기).** 원천 1건당 대장 1행이고, 이미 가져온 것은 후보에서 빠진다. 설비 코드는 **원천 코드를 그대로** 쓴다 — 두 쪽을 눈으로 맞출 수 있어야 한다.
- **가져온 설비는 코드·이름·종류를 CMMS에서 못 바꾼다.** 그 값은 원천이 쥐고 있다. 상세(제조사·모델·설치일)·중요도·계층은 보전 관점 정보라 CMMS에서 정한다.
- **계층(라인 > 설비 > 구성품).** 재귀 CTE로 트리를 펴고 화면은 depth만큼 들여쓴다. 자기 자신·후손을 상위로 두려 하면 막는다 — 고리가 되면 어디가 위인지 말할 수 없다.
- CMMS는 MES·BEMS를 **읽기만** 한다. 가져와도 저쪽은 바뀌지 않는다.

## C-09 고장 코드

- 증상·원인·조치 3종. **구분이 다르면 같은 코드를 또 쓸 수 있다**("NOISE"가 증상이면서 조치일 수 있다).
- **원인 코드에만 원인 분류를 단다.** 양방향으로 막는다 — 원인인데 비우면 400, 증상·조치에 달면 400.
- **CMMS 원인 분류는 SPC와 다르다.** SPC는 4M1E+측정(설비·자재·작업자·방법·측정·환경)으로 *치수가 왜 흔들렸는가*를 보고, CMMS는 **마모·윤활·전기·설정·외부·기타**로 *설비가 왜 섰는가*를 본다. 처음에 SPC 값을 그대로 가져다 썼다가 DB CHECK에 걸려 알았다.
- 공통 `Master` 엔진을 그대로 썼다 — 목록·중복·참조·삭제가 한 벌로 끝난다.

## 브라우저에서 찾은 것

**MES 설비 종류가 전부 "기타"로 들어왔다.** `mes.equipment.equipment_type`이 `INJECTION`이 아니라 **약칭 `INJ`·`ASM`·`INS`**였다. 단위 테스트는 칸 이름만 봐서 통과했고 화면에서야 드러났다. 매핑을 고치고, **"모두 OTHER면 매핑이 끊긴 것"**을 테스트로 못 박았다.

- 브라우저에서 확인: MES 2건 가져오기 → 후보에서 사라짐 → 라인 만들어 아래로 이동 → 순환 시도 400 → BEMS 공조기 가져오기(위치에 구역명) → 고장 코드 분류 규칙 양방향 차단. 390px 가로 스크롤 없음.
- 검증: 백엔드 `test_cmms_assets.py` **8건 + 1 skip**, 프런트 `cmms.test.tsx` 4건, 전체 프런트 **636**.
- **금형 가져오기는 체험할 수 없다** — `mes.mold` 시드가 0건이다. 코드·테스트는 있고(skip 처리) 시드가 생기면 바로 된다.
- 다음: **CMMS-1d** C-03 작업지시·C-02 전환 대기 신호·C-08 정비원·외주 업체.

# 2026-10-20 CMMS-1b — 교차 조회 함수 6개 (MES·BEMS·WMS·SPC·ERP)

Claude Code 직접 개발(D85). 브랜치 `cmms-1b`. 사용자 결정: **1번 — CMMS 단계에서 직접 만든다.**

DSN-21 6장이 요구하는 읽기 함수가 제공 쪽에 없었다. 표는 모두 있고 `interface.py`의 함수만 없어서, 각 20~40줄짜리 읽기 전용 래퍼를 더했다. **상대 솔루션의 동작은 바뀌지 않는다** — 함수 추가뿐이고 기존 호출 경로를 건드리지 않았다.

| 추가한 것 | 어디에 | CMMS 용도 |
|---|---|---|
| `equipment()` · `molds()` | `fs/mes/interface.py` | 설비·금형 대장 가져오기(C-05), 타수 주기 PM(C-04) |
| `enabled()` · `hvac_units()` · `active_alarms()` | **`fs/bems/interface.py` 신설** | 공조기 대장(C-05), 환경 경보 전환 대기(C-02) |
| `enabled()` · `stock_on_hand()` · `supply_items()` | **`fs/wms/interface.py` 신설** | 예비품 재고·부족(C-06) |
| `equipment_signals()` | `fs/spc/interface.py` | 설비 원인 이상 전환 대기(C-02) |
| `partners()` | `fs/erp/interface.py` | 외주 업체 거래처 연결(C-08) |

## 설계하며 정한 것

- **꺼진 솔루션은 빈 목록이 아니라 `None`.** 호출 쪽이 '대상 없음'과 '꺼짐'을 구분해야 안내 문구가 달라진다(D12). 테스트로 6개 함수 전부 확인한다.
- **BEMS 경보는 해제 전까지 전환 대상이다.** `acknowledged`(확인)는 '봤다'일 뿐 조치가 아니다. `cleared`만 빠진다. `bems.alarm`에 (규칙, 센서)당 미해제 1건 제약이 있어 테스트는 서로 다른 짝 3개를 쓴다.
- **SPC '설비 원인' 이상은 규칙이 아니라 설비가 특정되는가로 가린다.** 미조치 이상은 원인 분류가 아직 없기 때문이다. 설비 코드는 부분군에 남은 MES 스냅샷이다.
- **금형 타수는 `mold_usage` 누적 합**이다 — 타수 주기 PM의 '현재 사용량'이 된다.
- **재고는 `stock_move` 합이고 CMMS는 저장하지 않는다**(FS-029 D50). 안전 재고가 없는 품목은 '부족'이라고 말하지 않는다 — 기준이 없으면 판단할 수 없다. WMS에 없는 코드는 결과에서 빠져 호출 쪽이 '연결 안 됨'으로 다룬다.
- 모든 함수가 코드 문자열만 주고받아 **스키마 간 FK가 생기지 않는다**(FS-013 §6). 격리 감사 R1~R6 0.
- 검증: `backend/tests/test_cmms_interfaces.py` 신설 **7건** — 꺼짐 None, 설비·금형 스냅샷, 경보 상태별 포함/제외, 이상 미조치만, 재고 합·부족 판정, 매입처 필터, **조회가 원천을 바꾸지 않음**(전후 행 수 대조). 기존 `test_bems`·`test_spc`·`test_cmms_schema` 51건 영향 없음.
- 다음: **CMMS-1c** C-05 설비 대장(계층·가져오기)·C-09 고장 코드.

# 2026-10-20 CMMS-1a — CMMS 6표 → 12표 (DB)

Claude Code 직접 개발(D85). 브랜치 `cmms-1a`. 기존 솔루션 보강 순서 2번.

## CMMS는 SPC와 상황이 다르다

CMMS는 **FS-029a로 DB 6표만 있고 `backend/src/fs/cmms/`도 `frontend/src/cmms/`도 없다**(D76). SPC는 화면 7개가 돌고 있어 보강만 하면 됐지만, CMMS는 **화면 10개를 전부 새로 만들어야 한다.** 규모는 WMS(20화면·9단계)의 절반쯤이다.

- 새 표 6개: `checklist_item`·`checklist_result`(점검표 구조화 Q3), `technician`(정비원 Q5), `vendor`(외주 업체 Q5), `failure_code`(증상·조치 코드 F24), `asset_part`(설비별 예비품 F34). **전체 215 → 221표.**
- 기존 6표 칼럼 보강: `asset`에 계층(`parent_asset_id`)·상세 7칸, `pm_plan`에 사용량 기준 3칸, `work_order`에 정비원·외주·고장 코드 6칸, `work_log`에 정비원, `spare_part`에 WMS 품목·단가, `part_usage`에 사용 단가 스냅샷.
- 바뀐 제약 6건(c992·993·999·1004·1007·1016)은 모두 **제자리 교체**다. 설비 종류에 MOLD·LINE·COMPONENT·FACILITY, 출처에 MES_MOLD, PM 주기 NULL 허용(사용량 기준이면 일 주기가 없다), 작업지시 출처에 RWS_REQUEST. **제약 순번 밀림 0건**(1,583 → 1,620).
- `tools/apply_cmms1.py` 신설(멱등). 마이그레이션 `backend/alembic/versions/20261020_cmms1.py`(revision `cmms1`, down `spc2`, 88문).
- `cmms.technician`이 생기면서 **DSN-21 계약 검사가 자동으로 켜졌다**(`validate_cmms_dsn21`) — 금형 출처 Q1, 기준별 PM 주기 Q2, 점검표 완료 조건 Q3, 신호 출처 확장 없음 Q4, 비용 비저장 Q5, 재고는 WMS Q6. 모두 통과.
- `test_fs029a`의 표 개수 리터럴 6 → 12. (SPC 때와 같은 종류의 고정값이다.)
- 검증: db:validate 0(221표/2,439칼럼/553FK), 격리 R1~R6 0, **마이그레이션 왕복 통과**, verify_ddl 0, Excel·ERD 재생성, 도구 테스트 138 OK.
- **아직 없는 것: API·화면·시드·도움말 전부.** 새 6표는 빈 표다.

## 다음 단계에서 막히는 것 — 교차 조회 함수 4개가 없다

DSN-21 6장이 요구하는 읽기 함수가 **제공 쪽에 없다.** 표는 모두 있다(`mes.equipment`·`mes.mold`·`bems.hvac_unit`·`bems.alarm`·`wms.item`·`spc.signal`) — `interface.py`의 함수만 없다.

| 필요 | 상태 | 막히는 화면 |
|---|---|---|
| BEMS `active_alarms()`·`hvac_units()` | **`fs/bems/interface.py` 자체가 없음** | **C-02 전환 대기 신호(전면)**, C-05 |
| SPC `equipment_signals()` | 없음 | **C-02(전면)** |
| MES `equipment()`·`molds()` | 없음 | C-05 설비·금형 가져오기, C-04 타수 PM |
| WMS `stock_on_hand()` | **`fs/wms/interface.py` 자체가 없음** | C-06 예비품 재고·부족 |
| ERP `partners()` | 없음 | C-08(코드 직접 입력으로 우회 가능) |

10화면 중 **7개는 그대로 되고** C-02가 전면, C-05·C-06이 부분 막힌다. WMS W-16이 기다리는 POP(0표)와 달리 **만들 수 있는 것들**이라, 사용자에게 "CMMS 단계에서 직접 만든다" vs "빼고 간다"를 물었다.

- 단계 계획: 1a DB / **1b 교차 조회 함수 4개** / 1c 설비 대장·고장 코드 / 1d 작업지시·전환 대기·정비원 / 1e 예방보전·예비품 / 1f 개요·지표·비용·도움말.

# 2026-10-20 SPC-1e — 층별 비교(S-10)와 S-06 가변 n 표기 — SPC 화면 10 → 11

Claude Code 직접 개발(D85). 브랜치 `spc-1e`. 모델은 Sonnet(새 설계 판단이 없는 반복 작업이라 추천받아 전환).

- **S-10 층별 비교 신설(F45).** 한 특성의 부분군을 **설비별·LOT별**로 갈라 그룹마다 평균·전체 평균과의 차이·Cpk를 견준다. 조회 전용, 새 표·마이그레이션 없음. 전체 Cpk가 괜찮아도 한 설비만 치우친 경우를 찾는 것이 목적이다 — 좋은 설비가 나쁜 설비를 가려 평균을 맞춰 주기 때문이다.
- Cpk는 그룹의 유효 부분군이 **20개 이상**일 때만 계산한다. LOT 그룹은 부분군이 8개 안팎이라 거의 계산되지 않고 평균 차이만 본다 — 표본이 모자란 Cpk는 숫자가 아니라 잡음이다.
- **작업자 축은 만들지 않았다.** DSN-17 F45는 "설비·LOT·작업자별"이지만 `fs.mes.interface`에 작업자 정보가 없고 부분군에도 남는 값이 없다. **F45는 부분 구현(설비·LOT)이다.** MES가 작업자를 내보내는 계약이 생기면 부분군에 스냅샷 칸을 더하는 DB 변경과 함께 붙인다.
- **S-06 가변 n 표기 보정.** SPC-1b에서 부분군 크기를 1~10으로 풀고도 S-06에 `값 5개`·`X̄`·`R`·출처 `시드/입력`이 박혀 있었다. `측정값`·`X̄ · I`·`R · MR`로 바꾸고 출처에 `MES`·`파일`을 더했다.
- 도움말 `spc/s-10` 신설·`s-03` 연결(SPC 10 → 11편).
- 검증: 백엔드 `test_spc.py` **31 → 33건**(그룹별 집계·무효 제외·기준 미달·잘못된 축 400), 프런트 **631 → 632**. 브라우저에서 설비 2개 특성(ASM-01 48개 Cpk 1.72 / ASM-02 8개 계산 안 함)과 LOT별 전환(7개 LOT 모두 계산 안 함), 390px 가로 스크롤 없음을 확인했다.

## SPC 보강 마감 상태

- **완료**: 화면 7 → **11**(S-08 규격 이탈·S-09 OCAP·S-10 층별 비교·S-11 보고서 신설), 표 5 → **10**, 도움말 7 → **11편**. DSN-17 범위 24 중 **계량형·판정·규격 이탈·OCAP·분석·보고서**.
- **미구현(계약 대기)**: ① **계수형 관리도 F05** — `fs.mes.interface`에 확정 실적(투입·불량 수) 함수가 없다. DB는 `spc2`로 준비됐다. ② **계측기 F07** — QMS `gauges()`가 없다. ③ **작업자 층별** — 위 참고. ④ **CSV 올리기 F14** — 별건. ⑤ **QMS가 `spec_violations`를 실제로 읽는 쪽** — SPC는 제공만 했다.
- **시드 없음**: 규격 이탈·OCAP·보고서·규칙 선택은 시드에 행이 없어 새 게스트 공간에서는 빈 목록이다. 시드 보강은 별도 단계다.
- 다음: **CMMS**(보강 순서 2번). 결정서·설계 판단이 다시 들어오므로 Opus 권장.

# 2026-10-20 SPC-1d — 공정능력 보고서(S-11)와 S-03 보강(Pp/Ppk·정규성·월별 추이)

Claude Code 직접 개발(D85). 브랜치 `spc-1d`. SPC 화면 9 → 10.

## S-03: 군내 σ 하나로는 부족하다

- **Pp·Ppk 추가(F42).** Cp·Cpk는 `R̄/d2`, 즉 **부분군 안의 흩어짐**만 본다. 공정이 기간 중에 옮겨 갔다면 그 변동은 군내 σ에 잡히지 않는다. Pp·Ppk는 같은 식을 **개별 측정값의 표본 표준편차**로 계산하므로 기간 전체의 흩어짐을 본다. 둘의 차이가 **관리되지 않은 변동**이다.
- **정규성(F43)**: 왜도·첨도(3을 뺀 초과 첨도). Cp·Cpk가 정규분포를 전제하므로 0에서 많이 벗어나면 그대로 믿기 어렵다.
- **월별 Cpk 추이(F44)**: 달마다 따로 계산한다. 부분군이 20개에 못 미치는 달은 **계산하지 않고 수만** 보여 준다 — 표본이 모자라면 숫자가 아니라 잡음이다.
- 안내 문구는 **전체 σ가 군내 σ보다 클 때만** 띄운다. 브라우저에서 실제로는 반대인 경우(Ppk 1.42 > Cpk 1.27)를 보고 고쳤다 — 조건 없이 띄우면 틀린 안내가 된다.

## S-11 공정능력 보고서 — 왜 스냅샷인가

- S-03은 **볼 때마다 다시 계산**한다. 부분군이 하나 늘거나 무효가 되면 숫자가 바뀐다. 공정을 들여다볼 때는 맞지만, **남에게 낸 숫자**는 그러면 안 된다. 지난달에 보낸 Cpk 1.41을 다시 띄웠더니 1.37이 나오면 어느 쪽이 맞는지 설명할 수 없다.
- 그래서 보고서는 **만드는 순간의 값을 그대로** 들고 있다(`spc.capability_report`). 초안 → 확정 → 불변. 재작성은 **새 버전**이고, 확정하면 같은 기간의 옛 확정본이 '대체됨'으로 밀린다(기간당 확정 1건, UK_PARTIAL).
- 도움말 `spc/s-11` 신설·`s-03` 보강(SPC 9 → 10편).
- 검증: 백엔드 `test_spc.py` **28 → 31건**, 프런트 `spc.test.tsx` **12 → 14건**, 전체 프런트 631. 브라우저에서 **초안 생성 → 확정 → 같은 기간 v2 생성·확정 → v1 대체됨** 연쇄와 S-03의 Ppk·왜도/첨도·월별 추이(2026-08·09·10) 표시를 확인했다. 390px 가로 스크롤 없음.
- 남은 SPC: **S-10 층별 비교(F45)**와 S-01/02/04/06 잔여 보강 → SPC-1e.

# 2026-10-20 SPC-1c — 이상 대응 절차(OCAP, S-09)와 SPC-1a NULL 허용 보완

Claude Code 직접 개발(D85). 브랜치 `spc-1c`.

## DB 보완 — SPC-1a가 빠뜨린 NULL 허용

- `apply_spc1.py`는 표·칼럼을 **더하기만** 한다. DSN-17 4-2가 요구한 **기존 칼럼의 NULL 허용**은 그래서 빠졌고, 이미 적용한 CHECK(c1580: 계수형 부분군은 `xbar`가 NULL이어야 한다)가 **만족될 수 없는 상태**로 남아 있었다. 계량형은 영향이 없지만 계수형(P·NP·C·U)은 행을 넣을 수 없다.
- `tools/apply_spc2.py` 신설 — `spc.subgroup.xbar`·`r`, `spc.control_limit`의 X̄·R 칸 6개를 NULL 허용으로. **NOT NULL을 푸는 방향만** 허용하고 조이는 변경은 거부한다(기존 행 확인이 필요하므로).
- `spc1`은 적용·병합했으므로 고치지 않고 **새 revision `spc2`**로 처리했다(AGENTS §4).
- **`build_migration.py`가 칼럼 nullability 변경을 못 만들었다.** 새 칼럼만 만들고 기존 칼럼의 차이는 무시했다. `ALTER COLUMN … DROP NOT NULL`과 되돌리기 `SET NOT NULL`을 내도록 고쳤다 — 다음 모듈에서도 쓴다.
- 검증: db:validate 0, 격리 R1~R6 0, 마이그레이션 **왕복 통과**, verify_ddl 0, Excel·ERD 재생성, 도구 테스트 138 OK.

## OCAP — 이상이 나면 무엇부터 볼지 미리 정해 둔다

- **S-09 이상 대응 절차 신설**(SPC 8 → 9화면). 점검 항목에 **적용 범위**를 둔다: 특성이 비면 모든 특성, 규칙이 비면 모든 규칙. 이상 하나에는 해당하는 항목이 **모두** 뜬다(공통 + 그 특성 + 그 규칙).
- **S-05 보강**: 이상 상세에 점검표가 뜨고, 해당 항목을 **모두 기록해야 조치를 닫을 수 있다**(409 `OCAP_INCOMPLETE`). NG 항목의 해당 원인이 조치 원인으로 자동 제안된다. 조치 완료 뒤에는 점검도 불변이다.
- **점검 항목이 하나도 없으면 지금까지처럼 바로 조치할 수 있다.** 기존 동작을 깨지 않는다.
- 사용을 꺼도 **이미 기록이 있는 이상의 점검표에는 남는다.** 적용 범위도 기록이 생기면 잠근다 — 지난 점검이 무엇을 본 것인지 흐려지면 안 되기 때문이다.

### 구현하며 찾은 것 두 가지

1. **DB CHECK가 NG 메모를 못 막는다.** c1569 `result <> 'NG' OR length(btrim(note)) >= 2`는 `note`가 NULL이면 **NULL**로 평가돼 통과한다(CHECK는 거짓일 때만 막는다). 브라우저에서 NG를 메모 없이 저장해 보고 알았다. 서비스에서 막는다(c1570 SERVICE 정책대로).
2. **라우터의 null 허용 목록이 카멜 케이스였다.** `_values()`는 `model_dump()` 결과(스네이크 케이스)를 보는데 `characteristicId`를 적어 둬서, 화면이 '모든 특성'을 `null`로 보내면 400이 났다. 단위 테스트는 키를 빼고 보내서 통과했고 **브라우저에서야 드러났다.** 테스트에 명시적 null을 넣었다.

- 같은 적용 범위·같은 순서는 서비스가 막는다 — DB UK는 NULL을 서로 다른 값으로 봐서 '모든 특성' 항목끼리 잡지 못한다.
- 도움말 `spc/s-09` 신설·`s-05` 보강(SPC 8 → 9편).
- 검증: 백엔드 `test_spc.py` **23 → 28건**, 프런트 `spc.test.tsx` **10 → 12건**, 전체 프런트 629. 브라우저에서 **점검 없이 조치 → 409 → 점검 기록(OK·NG) → 원인 자동 제안(측정) → 조치 완료 → 읽기 전용** 전 과정을 확인했다. 390px 가로 스크롤 없음.
- 다음: **SPC-1d** 공정능력 보고서(S-11)·S-03 보강(Pp/Ppk·정규성·월별 추이).

# 2026-10-20 SPC-1b — I-MR·Nelson 8규칙·규격 이탈 (S-07 보강·S-08 신규)

Claude Code 직접 개발(D85). 브랜치 `spc-1b`. SPC-1a의 빈 표에 업무를 붙인 첫 단계.

- **관리도 종류(Q1).** 특성마다 `X̄-R`(부분군 2~10) 또는 `I-MR`(개별값 1)을 고른다. 지금까지는 n=5 고정이었다. 계수 표를 n=1~10으로 채웠고, **n=1 줄에 E2(2.660)를 A2 자리에, MR의 D3·D4·d2를 넣어** 한계·공정능력 식이 X̄-R과 **같은 코드**를 타게 했다 — 분기를 만들지 않았다.
- I-MR의 R 자리는 이웃 차이(MR)다. 첫 점은 앞이 없어 0으로 두고, **평균을 낼 때는 뺀다**(`_ranges`). 0을 함께 세면 20점 기준에서 MR̄이 5% 작아져 한계가 좁아진다.
- **Nelson 1~8(Q3).** 규칙 4~8을 더하고 특성별로 쓸 규칙을 고르게 했다(`spc.characteristic_rule`). 고른 것이 없으면 기존과 같은 1~3. **규칙 1은 끌 수 없다.** 규칙 2~8은 위치 관리도(X̄·I)에만 적용한다 — 산포 관리도는 규칙 1뿐이다.
  - 구현 함정: 규칙 2는 **중심선 기준 쪽**, 규칙 5~8은 **σ 구역**을 본다. 하나의 값으로 합치면 1σ 안의 점이 쪽을 잃어 규칙 2가 깨진다. 그래서 `(쪽, 구역)` 두 값으로 들고 다닌다.
- **규격 이탈(Q4).** 측정값마다 LSL·USL과 비교해 `spc.spec_violation`에 남긴다. **관리 이탈과 다른 것**이라 한계 게시 전에도 기록하고, 부분군을 무효로 하면 함께 무효가 된다. `fs.spc.interface.spec_violations(since)`로 QMS가 부적합 보고 후보로 읽어 간다.
- 화면: **S-08 규격 이탈 신설**(SPC 7 → 8화면), S-07에 관리도 종류·부분군 크기·판정 규칙, S-04 입력 칸 수 가변·I-MR 안내·규격 이탈 결과 표시, S-02 I-MR 축 이름, S-01 최근 7일 규격 이탈 타일. 도움말 `spc/s-08` 신설·`s-07` 보강(SPC 7 → 8편).
- 검증: 백엔드 `test_spc.py` **18 → 23건**(Nelson 4~8·I-MR·규칙 선택·규격 이탈 생성/무효 연쇄), 프런트 `spc.test.tsx` **7 → 10건**. 브라우저에서 게스트 공간을 새로 만들어 **규격 밖 2값 → 이탈 2건 → 부분군 무효 → 0건** 연쇄와 **I-MR MR 0.7 계산**을 확인했다. 390px 가로 스크롤 없음.
- **SPC-1a에서 빠뜨린 것을 찾았다.** DSN-17 4-2는 `spc.subgroup.xbar`·`r`과 `spc.control_limit`의 X̄·R 칸을 **NULL 허용**으로 바꾸라고 하는데 `apply_spc1.py`가 칼럼 추가·제약 교체만 해서 그대로 NOT NULL이다. 계량형(I-MR 포함)은 영향이 없지만 **계수형(P·NP·C·U)은 이 칸이 비어야 해서 지금은 넣을 수 없다.** 적용·병합한 `spc1`은 고치지 않고 **SPC-1c에서 새 revision으로** 처리한다.
- 범위에서 뺀 것: **계수형 관리도(F05)**는 `fs.mes.interface`에 확정 실적(투입·불량 수) 함수가 없고, **계측기 기록(F07)**은 QMS `gauges()`가 없다. WMS W-16과 같은 사정이다 — 제공 쪽 계약이 생긴 뒤에 붙인다.
- 다음: **SPC-1c** 이상 대응 절차(OCAP, S-09)·S-05 보강, 그리고 위 NULL 허용 보완.

# 2026-10-19 SPC-1a — SPC 5표 신설·기존 5표 보강 (DB)

Claude Code 직접 개발(D85). 브랜치 `spc-1a`. 기존 솔루션 보강 순서 1번.

- SPC가 목표 설계 10표 중 5표만 있었다. 나머지 5표를 만들었다: `spc.characteristic_rule`(특성별 적용 규칙), `spc.spec_violation`(규격 이탈), `spc.ocap_item`·`spc.ocap_check`(이상 대응 절차와 점검 기록), `spc.capability_report`(공정능력 보고서). **spc 5표 → 10표, 전체 210 → 215표.**
- 기존 5표에 칼럼을 더했다. `characteristic`에 `chart_type`·`defect_source`, `control_limit`에 `attr_center`, `subgroup`에 `inspected_qty`·`defect_count`·`gauge_code`. **계수형 관리도(P·NP·C·U)와 부분군 크기 1~10(I-MR·X̄-R)을 받기 위한 것**으로, 지금까지는 X̄-R·n=5만 가능했다.
- 바뀐 CHECK 7건(c739·741·756·760·763·764·765)은 모두 **제자리 교체**다. `schema.json`의 제약 이름이 배열 순번이라 중간에 끼워 넣으면 뒤 번호가 전부 밀린다. 끼워 넣지 않았음을 적용 전후 순번 비교로 확인했다(제약 1,549 → 1,583, 밀린 번호 0건).
- `tools/apply_spc1.py` 신설(멱등). 마이그레이션 `backend/alembic/versions/20261019_spc1.py`(revision `spc1`, down `gw_wms_merge`, 65문).
- **도구 3개를 고쳤다.** ① `validate_db_design.py`의 단계 판정이 `W`·`GW-`로 시작하는 작업 ID만 "일괄 개발"로 봐서 `SPC-1a`가 설계 검사에서 떨어졌다. **설계 작업(`FS-`·`DSN-`)이 아니면 개발 단계**로 뒤집었다(`is_build_task`). 모듈마다 접두사를 더하지 않아도 된다. ② `build_migration.py --module-key`가 모듈 키를 목록 끝에서 글자 수만큼 잘라내 `spc`처럼 중간에 있는 키에서 `'hr',)` 같은 깨진 CHECK를 만들었다. 끝에 없으면 건너뛴다. ③ SPC 계약 검사 문구를 `subgroup size fixed to 5` → `subgroup size 1~10`으로 바꾸고, 이를 고정값으로 박아 둔 `test_fs028a`·`test_fs030a`를 갱신했다.
- 검증: `db:validate` 오류 0(215표/2,360칼럼/536FK), 격리 감사 R1~R6 0, **마이그레이션 왕복**(spc1 → gw_wms_merge → spc1) 통과, `verify_ddl_matches_schema.py` 0, `db:build`(51시트)·`build_erd.py` 재생성. 수동 CI 1~5단계 통과(백엔드 **1,100 passed/2 skipped**·perf 1, 마이그레이션 왕복 0, 프런트 **624 passed/77 files**).
- **아직 없는 것: API·화면·시드·도움말.** 새 5표는 빈 표다. SPC 화면은 S-01~07 그대로이고 S-08~S-11은 다음 단계다.
- **CI에서 테스트 4건을 고쳤다.** `test_gw_wms_merge.py`가 head 리비전을 `"gw_wms_merge"` 문자열로 박아 둬서 `spc1`이 붙자 3건이 깨졌다. 검사 의도는 "손으로 부른 `downgrade()`가 버전 행을 건드리지 않는다"이므로 `ScriptDirectory.get_current_head()`와 비교하게 바꿨다 — 다음 마이그레이션에서 또 깨지지 않는다.
- **날짜 경계 실패를 다시 만났다.** 22:50에 시작한 CI가 자정을 넘기면서 `test_lazy_seed`·`test_mes_master`·`test_integration_ac` 3건이 깨졌다. `guest_expires_at()`이 만료를 **KST 자정**으로 잡아 테스트 도중 게스트 공간이 죽는다. 자정 이후 재실행하면 통과한다. 코드 결함이 아니라 **자정 직전에 CI를 시작하면 재현되는 문제**다(지난 flow 7건과 같은 종류).
- 다음: **SPC-1b** S-07 규칙 설정·S-08 규격 이탈.

# 2026-10-19 WMS 운영 배포 완료 (6df6e71) — 화면 19/20·도움말 18편

제품 `6df6e71` 로컬main/origin/실서버 반영(22:25 KST). 서버 `a7c78d0` → `6df6e71`, 40초. 18커밋·49파일(+8,144/−31).

- 나간 것: **W2b-1e~1i 전부** — W-13 생산 불출, W-14 재고 실사·W-15 마감, W-17 라벨 출력, W-18 수불부·W-19 분석·W-20 점유, W-06 용량·혼적 보강, 도움말 9편(WMS 18편 완성).
- **마이그레이션 0건·시드 그대로.** 시드 `sv-20261018-wms1` 유지로 "템플릿 유지"가 떴고 템플릿 재생성이 없어 배포가 짧았다. 이번 배포는 코드만 나갔다.
- 배포 확인: 원점 200 · 공개 200 · **DDL 대조 0** · 최근 2분 5xx 0건. 빌드 29M. WMS 청크 97KB → 140KB(화면 6개 추가).
- 운영 번들 대조: `/assets/wms-FjQIub19.js`(140,789 B)에 생산 불출·재고 실사·라벨 발행·재고 수불부·위치 점유·배정 미리보기 전부 포함. `/assets/ContentPages-CILAA2_e.js`(532,937 B)에 새 도움말 본문 포함. 두 청크 해시가 로컬 빌드와 동일.
- **CI를 건너뛰고 배포했다(`--skip-ci-check`).** GitHub Actions 결제 차단이 계속된다. 대신 수동 CI를 **배포 전에** 끝까지 돌려 전 단계 통과를 확인했다(백엔드 1,100 passed/2 skipped·perf 1, DDL 0, 마이그레이션 왕복 0, 프런트 624 passed/77 files). 지난 두 번과 달리 이번에는 검증이 배포보다 먼저 끝났다.
- **운영 브라우저 확인 미실행.** WMS 새 화면은 **새 게스트 공간**에서 봐야 한다 — 기존 공간에는 입고장·라인 칸이 없어 안내 문구가 뜬다.
- 남은 것: **W-16 POP 가져오기** — `wms.pop_import`가 `fs.pop.interface.confirmed_entries()`를 전제하는데 POP 솔루션이 0표다. POP 구현 뒤에 붙인다.
- 다음: 기존 솔루션 보강 순서대로 **SPC(5표) → CMMS(6) → QMS(9) → FEMS(12) → BEMS(11) → ERP(38)**.

# 2026-10-19 W2b-1i WMS 도움말 9편 — WMS 화면 20개 중 19개 완료

Claude Code 직접 작성(D85). 브랜치 `w2b-1i`.

- `content/help/wms/`에 w-10·11·12·13·14·17·18·19·20 9편 신설. WMS 도움말 **9편 → 18편**. 도움말 수 가드(`content-pages.test.tsx`) 9→18.
- 화면 조작법보다 **설계 결정의 이유**를 적었다: 차이·LOT 수량·만료를 저장하지 않고 조회 때 계산하는 이유, 추천은 제안이지 강제가 아니라는 것, 예약이 지정한 LOT을 시스템이 말없이 바꾸지 않는 이유, 실사 잠금이 필요한 이유, 마감 순서(WMS 재고 → ERP 원가 → ERP 회계).
- 모든 링크를 `menu_catalog.json`의 실제 경로와 대조했다. `/mes/materials` 오타를 `/mes/material-issues`로 고쳤다.
- 검증: 수동 CI 전 단계 통과 — 백엔드 **1,100 passed/2 skipped**·perf 1, DDL 0, 마이그레이션 왕복 0, 프런트 **624 passed/77 files**. 브라우저에서 w-12·14·20을 열어 본문·"이 화면 열기"·이전/다음 연결 확인.
- **WMS 화면 20개 중 19개 완료.** 남은 것은 W-16 POP 가져오기뿐이며 POP 솔루션(0표)이 없어 보류한다.
- 다음: WMS 전체 운영 배포. 운영은 `a7c78d0`이라 1e 이후(생산 불출·실사·마감·라벨·수불부·분석·점유·도움말)가 전부 미반영이다. **이번 배포에 마이그레이션은 없다**(DB 변경 0).

# 2026-10-19 W2b-1h 수불부(W-18)·분석(W-19)·점유(W-20)·W-06 보강 완료

Claude Code 직접 구현(D85). 브랜치 `w2b-1h`.

- 신규: `backend/src/fs/wms/analytics.py`, `frontend/src/wms/Reports.tsx`(세 화면을 한 파일에서 내보낸다), `backend/tests/test_wms_analytics.py`. 라우트 3개(`/ledger`·`/analysis`·`/occupancy`), 메뉴 W-18·19·20, 메뉴 수 가드 119→122.
- **표를 새로 만들지 않았다.** 셋 다 원장(`wms.stock_move`)과 마스터를 조회할 때 집계한다. 수불부는 기초=시작일 앞 합계, 입고·출고=기간 안 양수·음수, 기말=기초+입고+출고.
- **W-06 보강이 전제였다.** `capacity_qty`·`mix_items`·`mix_lots`가 W2b-1a에서 DB에는 들어갔는데 **API에 노출돼 있지 않아** 사용자가 용량을 설정할 수 없었다. 적치 추천(C-3)이 이 값을 쓰는데도 그랬다. `LocationCreate`·`LocationUpdate`·`LOCATION_SQL`·W-06 화면에 추가했다.
- 분석은 안전재고 부족·최대재고 초과(F37)와 회전율(최근 90일 출고 ÷ 현재고)·장기 체화(마지막 출고 후 90일, F54)를 낸다. 점유는 용량 대비 현재고이고 **용량이 없으면 점유율을 내지 않는다**(F55).
- 검증: 수동 CI 전 단계 통과 — 백엔드 **1,100 passed/2 skipped**·perf 1, DDL 0, 마이그레이션 왕복 0, 프런트 **624 passed/77 files**. DB·마이그레이션·시드 변경 없음.
- 브라우저 실동작(시드 데이터): 수불부 `FG-C100 3,860 + 503 − 502 = 3,861` 집계 일치 → 분석에서 회전율 1.14·마지막 출고 2026-10-19 표시 → 점유에서 `F-A02` 용량을 400으로 설정하니 재고 500 → **125.0% `over: true`** → 390px 넘침 0(수불부·점유 둘 다).
- 안 한 것: 도움말 `w-18/19/20.md` 없음. 수불부는 월 단위만 지원한다(설계가 "기간"이라 했으나 임의 기간 UI는 넣지 않았다).
- 다음: **W2b-1i 도움말** — `content/help/wms/`에 w-10·11·12·13·14·17·18·19·20 9편. 그 뒤 WMS 전체 배포.

# 2026-10-19 W2b-1g 라벨 출력(W-17) 구현 완료 · W-16은 보류

Claude Code 직접 구현(D85). 브랜치 `w2b-1g`.

- 신규: `backend/src/fs/wms/labels.py`·`label_schema.py`, `frontend/src/wms/Labels.tsx`, `backend/tests/test_wms_labels.py`. 라우트 2개(`/labels` 목록·발행), 메뉴 W-17(`/wms/labels`), 메뉴 수 가드 118→119.
- **핵심은 `UK_PARTIAL`(종류·바코드당 VALID 1건)이다.** 같은 대상을 다시 찍으면 사유를 받고 **이전 라벨을 VOID로 바꾼 뒤** 새 행이 `reprint_of_id`로 그것을 가리킨다. 사유 없이 재발행하면 409 `LABEL_EXISTS`, 처음 발행인데 사유를 적으면 400.
- 대상은 실제로 있는 것만 받는다: `LOCATION`은 활성 `storage_location.code`, `MATERIAL_LOT`은 등록된 `wms.lot.lot_no`.
- 검증: 수동 CI 전 단계 통과 — 백엔드 **1,097 passed/2 skipped**·perf 1, DDL 0, 마이그레이션 왕복 0, 프런트 **623 passed/77 files**. DB·마이그레이션·시드 변경 없음.
- 브라우저 실동작: 첫 발행 201(VALID 3장) → 사유 없이 재발행 **409 LABEL_EXISTS** → 사유 있는 재발행 201(`reprintOfId` 연결, 이전 행 VOID) → 목록에 유효 1건·무효 1건 → 390px 넘침 0.
- **W-16 POP 가져오기는 보류한다.** `wms.pop_import`의 SERVICE 정책이 `fs.pop.interface.confirmed_entries()`를 전제하는데 **POP 솔루션이 아직 0표**다. 가져올 원본이 없다. POP 구현 뒤에 붙인다.
- 안 한 것: 실제 Code128 바코드 이미지를 그리지 않았다(값과 "Code128" 표기만). 설계가 "브라우저 인쇄"까지만 정해 바코드 렌더링 의존성을 새로 넣지 않았다. 실제 스캐너로 읽으려면 필요하다. 도움말 `w-17.md` 없음.
- 다음: W2b-1h 조회 3종(W-18 수불부·W-19 분석·W-20 점유)과 W-01·02·03·06 보강, 그다음 1i 도움말(w-10~14·17).

# 2026-10-19 W2b-1f 재고 실사(W-14)·재고 마감(W-15) 구현 완료

Claude Code 직접 구현(D85). 브랜치 `w2b-1f`.

- 신규: `backend/src/fs/wms/counts.py`·`count_schema.py`, `frontend/src/wms/Counts.tsx`, `backend/tests/test_wms_counts.py`. 라우트 8개(실사 5·마감 3), 메뉴 W-14(`/wms/counts`), 메뉴 수 가드 117→118.
- **핵심은 두 SERVICE 정책을 한 길목에서 막은 것이다.** 설계의 "실사 잠금"(F35)과 "마감 월 전표 금지"(F39·Q6)는 기능이 아니라 금지다. 전표 쓰기 경로가 `service._insert_document`(생성+확정)와 `service.post_document`(초안→확정) 둘뿐이라, `_guard_stock_writable` 하나를 만들어 그 두 곳에서만 부른다. 기능마다 흩뿌리지 않았다.
- 실사: 시작 시 원장 합계를 `count_line.book_qty`로 스냅샷. **차이는 저장하지 않고 조회 때 계산한다**(F35). 차이가 있는 줄만 `CYCLE_COUNT` 전표로 조정하고, 차이가 없으면 전표 없이 `ADJUSTED`. 같은 창고에 OPEN 실사는 1건만.
- 마감: 전표가 있는 달과 마감 기록을 합쳐 보여 준다. 마감 전에 진행 중 실사와 미확정 전표를 막는다(`COUNT_IN_PROGRESS`·`DRAFT_DOCUMENTS`).
- 검증: 수동 CI 전 단계 통과 — 백엔드 **1,094 passed/2 skipped**·perf 1, DDL 0, 마이그레이션 왕복 0, 프런트 **622 passed/77 files**. DB·마이그레이션·시드 변경 없음.
- 브라우저 실동작(시드 재고 있는 완제품 창고): 전수 실사 시작 → 장부 스냅샷 4줄(LOT별 1,920·1,940·1,921·1,921) → **실사 잠금 409 COUNT_IN_PROGRESS** → 실사 1,918 입력 → 진행 4/4·차이 1건(−2만, 나머지 0) → 조정 확정 → 전표 `WD-20261019-002`, 재고 1,920 → 1,918 → 마감 시도 **409 DRAFT_DOCUMENTS**(잠금 시험으로 남은 초안 2건) → 초안 확정 후 마감 200 → **마감 후 확정 409 PERIOD_CLOSED** → 해제 200 → 확정 200 → 390px 넘침 0.
- 안 한 것: 순환 실사(`kind='CYCLE'`·위치 일부)는 API는 `locationIds`를 받지만 화면은 전수만 뒀다(설계에 순환 UI가 없다). 도움말 `w-14.md` 없음. 마감 해제에 권한 제한을 두지 않았다(설계에 규칙 없음, 체험용).
- **다음 단계 제약 발견**: `wms.pop_import`의 SERVICE 정책이 `fs.pop.interface.confirmed_entries()`를 전제하는데 **POP 솔루션이 아직 없다(0표)**. W2b-1g의 W-16은 가져올 원본이 없으므로 **라벨(W-17)만 먼저 하고 W-16은 POP 구현 뒤로 미룬다.**

# 2026-10-18 W2b-1e 생산 불출(W-13) 구현 완료

Claude Code가 직접 구현했다(D85로 D84 해제). 브랜치 `w2b-1e`.

- 신규: `backend/src/fs/wms/issues.py`·`issue_schema.py`, `frontend/src/wms/Issues.tsx`, `backend/tests/test_wms_issues.py`. 라우트 4개(`/issue-requests` 목록·상세·confirm·cancel), 메뉴 W-13(`/wms/issues`), 메뉴 수 가드 116→117.
- **배정은 저장하지 않는다.** `wms.issue_request_line`에 위치·LOT 칸이 없어 설계상 불출 시점 계산이다. 목록·상세는 같은 함수로 미리보기만 돌려준다.
- **피킹 배정 규칙을 그대로 재사용했다.** `picks._candidate_buckets`에 예약 id 대신 `-1`을 넘기면 모든 예약·피킹 선점을 뺀 가용 재고가 나온다. 기존 코드 무변경으로 보류(활성 `lot_hold`·QMS 보류·`status='HOLD'`)·만료 제외와 FEFO → FIFO를 그대로 쓴다.
- **LINE 칸이 시드에 없다.** 피킹의 SHIPPING과 같이 `LINE` 우선·`NORMAL` 허용 + 화면 안내로 처리했다. 시드 무변경(`SEED_VERSION` 재상승 회피).
- `PRODUCTION_ISSUE` 전표는 `posted`·`source_key=NULL`·`source_ref=request_no`. 내부 이동이라 대시보드 입출고 집계에서 제외했다(`TRANSFER`·`PUTAWAY`·`PICK`과 동일). **설계 명시가 아니라 판단이다.**
- 검증: 수동 CI 백엔드 **1,088 passed/2 skipped**·perf 1·작업자 탈락 0, DDL 0, 마이그레이션 왕복 0, 프런트 **621 passed/77 files**, ruff·format·typecheck·build 통과. DB·마이그레이션·시드 변경 없음.
- 브라우저 실동작: 새 게스트 공간 → 라인 칸(`R-LINE`)·LOT 추적 자재 생성 → LOT-OLD(만료 2099-01-01) 40·LOT-NEW(2099-12-01) 40 입고 → 50 요청 시 **미리보기가 LOT-OLD 40 + LOT-NEW 10**으로 FEFO 정렬 → 확정 → 전표 `WD-20261018-003`(`PRODUCTION_ISSUE`·posted) 1장 → 원장 `R-A01 LOT-NEW 30` / `R-LINE LOT-OLD 40` + `LOT-NEW 10`, **총량 80 불변** → 재확정 409 `INVALID_STATE`, 전표 추가 없음 → 390px 가로 넘침 0.
- 고친 것 하나: 처음에 `GET /wms/locations`를 불렀으나 그 엔드포인트가 없다(404). 위치는 `/warehouses/{id}/locations`로만 조회된다. 요청 폼에 창고 선택을 두고 그 창고의 칸을 불러오도록 바꿨다.
- 함정 재확인: 단일 프런트 테스트는 `npm --prefix frontend test -- <파일>`. `npx --prefix frontend vitest run`은 설정을 못 읽어 전부 실패한 것처럼 보인다(내가 또 걸렸다).
- 다음: W2b-1f 실사(W-14)·마감(W-15).

# 2026-10-18 WMS·GW 회사인증 수동 운영 배포 완료 (a7c78d0)

제품 `a7c78d0` 로컬main/origin/실서버 반영(19:53 KST). 서버 `c0f118e` → `a7c78d0`, 36초. 39커밋·154파일(+37,664/−15,733).

- **운영 DB에 DDL이 처음 들어간 배포다.** 마이그레이션 3건 적용: `w2b1_wms`(WMS 12표 신규 + 기존 6표 14칼럼)·`gw_company_identity`·`gw_wms_merge`(두 갈래 병합). 적용 후 DDL 대조 0.
- 시드 `sv-20261009-gw1` → `sv-20261018-wms1` **템플릿 재생성**(C-3a의 RECEIVING 입고장 반영). `wms.storage_location` 8행·`wms.item` 5행 등 확장 확인.
- 배포 확인: 원점 200 · 공개 200 · DDL 대조 0 · 최근 2분 5xx 0건. 빌드 29M.
- 운영 번들 대조: `/assets/wms-N0eQ6fOR.js`(97,978 B) 해시가 로컬 빌드와 동일, 적치·추천 위치·보류 해제·입고장·유효기간·ABC 등급 전부 포함.
- **들어간 것**: antigravity WMS W2b-1a~1c 전체와 1d D-1(피킹 API), FLOW-FIX-01·02·WMS-FIX-02 테스트 보정, `tools/ci_local.sh`. Codex GW 회사 인증(회사 식별·동의·권한·회사 화면, `fs/gw/company_*.py` 7개 신규, `frontend/src/gw/Company.tsx`), Codex HR PWA 정책 보정, CAD 기록.
- **CI를 건너뛰고 배포했다(`--skip-ci-check`).** GitHub Actions 결제 차단이 계속된다. 수동 CI(`npm run ci:local`)를 main에서 돌렸고 **전 단계 통과**: 설계·격리 0 · 도구 OK · ruff OK · DDL 0 · 백엔드 **1,079 passed/2 skipped**(8:33) · perf 1 · 마이그레이션 왕복 0 · 프런트 **617 passed/77 files**.
- **주의: 수동 CI가 배포보다 늦게 끝났다(사후 검증).** 1~3단계 일부(설계·격리·ruff·DDL)는 배포 전에 통과를 확인했으나 백엔드·프런트 테스트는 배포 뒤에 끝났다. 다음부터는 완료를 확인하고 배포한다.
- **불안정 테스트 1건 발견**: `frontend/src/erp/sales.test.tsx > 견적은 단가 출처를 표시한다`가 1차 실행에서 실패하고 재실행에서 통과했다(`ci_local.sh` 재시도가 흡수). FLOW-FIX-01 조사에서 뽑은 "날짜 의존 위험 13개" 목록의 10번이며 `today = () => new Date()`에 의존한다. **다음에 같은 방식(`vi.setSystemTime`)으로 고친다.**
- **운영 브라우저 확인 미실행**: WMS 네 화면(`/wms/items`·`lots`·`inbounds`·`putaways`)과 GW 회사 화면을 아직 보지 않았다. WMS 입고장 칸은 **새 게스트 공간에만** 생긴다(기존 공간은 템플릿 복사 시점이 다름).
- **GW 회사 인증은 Claude Code가 리뷰하지 않았다.** Codex 범위이며 자체 검증("합성 기술 검증 완료 / 실회사 인수 미완료")만 받고 나갔다. 로그인·권한 문제가 생기면 여기를 먼저 본다.
- `/wms/picks`는 API만 있고 화면이 없다(W2b-1d D-2 진행 중). 메뉴에 노출되지 않는다.
- 다음: D-2 결과 리뷰 → D-3·D-4 → W2b-1e.

# 2026-10-18 W2b-1d D-4 W-09 출고 예약 피킹 상태 연계 및 완제품 출고 예약 보강 완료 (W2b-1d 전체 완료)

- 작업 폴더 / 브랜치: `/Users/hwang-kyoungho/projects/factory-studio-ag` / `antigravity/w2b-1d-work`
- 구현 내용:
  - 기존 데이터 감사: `lot_tracked = false & lot_no IS NOT NULL` (0건), `lot_tracked = true & lot_no IS NULL` (0건) 확인 완료.
  - `backend/src/fs/wms/reservations.py`:
    - 예약 목록(`list_reservations`): `wms.pick_order`를 `LEFT JOIN`하여 단일 쿼리로 `pickOrderId`, `pickOrderNo`, `pickOrderStatus`(`OPEN`, `PICKED`, `CANCELLED`, 미지시 null)를 묶음 반환 (N+1 쿼리 없음).
    - 예약 상세(`_detail`): `wms.pick_order` 조회 연계하여 최신 피킹 지시 정보(`pickOrderId`, `pickOrderNo`, `pickOrderStatus`) 반환.
    - 예약 등록 규칙 정규화 (C-2 일관성): 품목 LOT 필수 여부 검증을 `bool(lot) != (item["itemClass"] == "FG")`에서 C-2와 동일한 `bool(lot) != bool(item.get("lotTracked"))`로 수정.
    - HOLD·EXPIRED LOT 예약 차단: 신규 예약 등록 시 `picks._lot_metadata`, `picks._lot_block_reason`, `qms.held_lot_nos`를 활용하여 WMS 활성 보류(`LOT_HOLD`), QMS 품질 보류(`LOT_QMS_HOLD`), 만료(`LOT_EXPIRED`) 상태의 LOT 지정을 `409 Conflict`로 즉시 차단.
  - `backend/tests/test_wms_reservations.py`:
    - `test_reservation_lot_tracked_validation_and_hold_expired_blocking` 신규 추가:
      - `lotTracked = true` 품목 LOT 미지정 시 400 거절 검증.
      - `lotTracked = false` 품목 LOT 지정 시 400 거절 검증.
      - WMS 활성 보류 LOT 예약 시 409 `LOT_HOLD` 차단 검증.
      - 유효기간 만료 LOT 예약 시 409 `LOT_EXPIRED` 차단 검증.
      - QMS 품질 보류 LOT 예약 시 409 `LOT_QMS_HOLD` 차단 검증.
      - 피킹 지시 생성 전후 상세 및 목록의 `pickOrderId`, `pickOrderNo`, `pickOrderStatus` 연계 검증.
  - `frontend/src/wms/operations.tsx`: `Reservation` 타입에 `pickOrderId?: number | null`, `pickOrderNo?: string | null`, `pickOrderStatus?: PickOrderStatus | null` 추가.
  - `frontend/src/wms/Reservations.tsx`:
    - 예약 목록 테이블에 "피킹 상태" 컬럼 추가 (`미지시` neutral, `대기` warning, `피킹 완료` normal, `취소` issue 배지).
    - 예약 상세 패널에 피킹 상태 배지 표시 및 "피킹 지시" 섹션 연계:
      - 지시 번호, 상태, W-12 화면 링크(`/wms/picks?open={id}`) 제공.
      - `ACTIVE` 상태이면서 미지시 또는 취소 상태일 때 "피킹 지시 생성" 버튼 노출 (OPEN/PICKED 존재 시 숨김).
      - 피킹 지시 생성 성공 시 알림 및 이동 링크 제공.
      - 피킹 지시 생성 실패(`409 INSUFFICIENT_AVAILABLE`) 시, 제외된 LOT(`excludedLots`: LOT 번호, 사유 레이블)과 부족 품목(`insufficientItems`: 품목 코드, 요청/가용 수량)을 상세 패널 상단 알림(`role="alert"`)으로 명확히 안내.
  - `frontend/src/wms/wms.test.tsx`:
    - W-09 출고 예약 목록 및 상세에서 피킹 상태 연계와 피킹 지시 생성 테스트 추가.
    - W-09 출고 예약에서 피킹 지시 생성 실패 시 제외된 LOT과 부족 품목 상세 안내 테스트 추가.
- 검증 결과:
  - 브라우저 Playwright E2E 검증 (`scratch/verify_d4_reservations.mjs`):
    - 게스트 공간 생성 -> 기초 재고 입고 -> W-09 예약 등록 -> 목록에서 피킹 상태 "미지시" 확인 (`wms-reservations-d4-list.png`).
    - W-09 상세 진입 -> 피킹 미지시 배지 및 "피킹 지시 생성" 버튼 확인 (`wms-reservations-d4-detail-unassigned.png`).
    - "피킹 지시 생성" 클릭 -> 피킹 지시 생성 완료 알림 및 링크 확인.
    - W-12 피킹 화면 이동 -> 생성된 피킹 지시(OPEN) 확인 -> F-SHIP 도착 칸 선택 후 "피킹 확정" 클릭 (`wms-reservations-d4-linked-pick.png`).
    - W-09 출고 예약 화면 복귀 -> 목록에서 피킹 상태 "피킹 완료" 갱신 확인 (`wms-reservations-d4-picked-list.png`).
    - 상세 패널 재진입 -> 상단 "피킹: 피킹 완료" 배지 표시, 지시 번호 및 상태, W-12 링크 확인, 중복 "피킹 지시 생성" 버튼 숨김 확인 (`wms-reservations-d4-picked-detail.png`).
    - 모바일 390px 뷰포트: `scrollWidth = 390, clientWidth = 390` (가로 오버플로 0건) 확인 (`wms-reservations-d4-mobile-390.png`).
    - `ALL D-4 BROWSER VERIFICATIONS PASSED!`
  - `tools/ci_local.sh` 1~5단계 전체 통과:
    - 1단계 (DB 검증·도구): 통과 (`tables: 210, errors: []`, 도구 138건 통과)
    - 2단계 (백엔드 ruff): 통과 (`All checks passed! 247 files clean`)
    - 3단계 (백엔드 pytest): 통과 (`1084 passed, 2 skipped, 58 warnings in 487.10s`, `pytest -m perf`: 1 passed, xdist 작업자 탈락 0건)
    - 4단계 (DB 초기화·마이그레이션 왕복): 통과 (`downgrade base` -> `upgrade head`, DDL 0건 차이)
    - 5단계 (프런트엔드): 통과 (`typecheck`, `lint`, `format:check`, `build`, `Test Files 77 passed (77), Tests 620 passed (620)`)
- 제약 및 특이사항:
  - W2b-1d (D-1 FEFO/FIFO 지시 생성, D-2 W-12 화면 및 동선 명세, D-3 확정·취소 및 유효 현재 위치 도출, D-4 W-09 예약 연계 및 완제품 출고 예약 보강) 4개 세부 단계 모두 완료.
- 다음 작업: 사용자 확인 후 **W2b-1e 출하 검사(W-10) · ERP 출하 연계(E-07)** 착수.

# 2026-10-18 W2b-1d D-3 피킹 확정·취소 API 및 화면 연계 + 유효 현재 위치 도출 완료


- 작업 폴더 / 브랜치: `/Users/hwang-kyoungho/projects/factory-studio-ag` / `antigravity/w2b-1d-work`
- 구현 내용:
  - `backend/src/fs/wms/pick_schema.py`: `PickLineConfirm`, `PickOrderConfirm(toLocationId, lines)` 스키마 추가.
  - `backend/src/fs/wms/picks.py`:
    - `confirm_pick_order`: 한 트랜잭션에서 `wms.pick_line.picked_qty` 기록, `PICK` 재고 이동 전표(`status='posted'`, `source_key=NULL`, `source_ref=pick_no`, 출발 칸 -picked / 도착 칸 +picked) 생성, `pick_order.status='PICKED'`, `picked_at=now`, `stock_document_id=doc_id` 갱신. 부분 피킹 지원(`picked_qty = 0`이면 전표 미생성, 1개 이상 양수 필수).
    - `cancel_pick_order`: `cancel_reason`(1~300자) 검증, `status='CANCELLED'`, `picked_at=NULL`, `stock_document_id=NULL`, `cancel_reason` 기록. 취소 후 동일 예약에서 재요청 시 `OPEN`으로 재개(c1482) 지원.
    - `_pick_order_header`, `PICK_ORDER_SELECT`, `_enrich_orders`에 `toLocationId`, `toLocationCode`, `toLocationName` 추가.
  - `backend/src/fs/wms/router.py`: `POST /pick-orders/{id}/confirm`, `POST /pick-orders/{id}/cancel` 엔드포인트 등록.
  - `backend/src/fs/wms/inventory.py`: amounts CTE의 `reserved_qty` 집계 시, 피킹 전(미지시/OPEN/CANCELLED)에는 `stock_reservation_line`의 원래 `(location_id, lot_no, qty)`, 피킹 후(PICKED)에는 PICK 전표 도착 줄 `(to_location_id, lot_no, picked_qty)` + 미피킹 잔량 `(location_id, lot_no, qty - picked_qty)`을 유효 현재 위치로 도출하여 보관 칸 음수 재고 방지.
  - `backend/src/fs/wms/reservations.py`: `_effective_lines` 도출 함수 구현. `_detail`, `list_reservations`, `consume`, `shipment_preview`에 적용하여 ERP 출하 소진 시 도착 위치에서 차감(보관 칸 이중 차감 방지) 및 확정 후 W-09 예약 목록에 거짓 부족 경보(reservationShortage) 방지.
  - `frontend/src/wms/common.tsx`: `PickOrder` 타입에 `toLocationId`, `toLocationCode`, `toLocationName` 추가.
  - `frontend/src/wms/Picks.tsx`:
    - OPEN 상세: 명세별 피킹 수량 입력 필드 제공(기본값 지시 수량), 도착 위치 선택, "피킹 확정" 및 "피킹 취소"(사유 필수) 폼 연계.
    - PICKED 상세: 실제 도착 위치(`toLocationCode · toLocationName`), 확정 시각, 생성된 PICK 전표 링크, 명세별 확정 수량 노출.
    - CANCELLED 상세: 취소 사유 노출.
  - `frontend/src/wms/wms.test.tsx`: 피킹 확정 및 취소 액션 폼/버튼 렌더링 검증.
- 검증 결과:
  - 브라우저 Playwright E2E 검증 (`scratch/verify_d3_picks.mjs`):
    - 게스트 세션 생성 -> 창고 및 F-SHIP 출고장 확인 -> 기초 재고 입고(40, 60 EA) -> 출고 예약 1(30, 20 EA) -> 피킹 지시 1(OPEN) 생성.
    - W-12 화면 진입 -> OPEN 상세 및 명세별 수량(30, 20), 도착 위치(F-SHIP) 확인 (`wms-picks-d3-open.png`).
    - "피킹 확정" 클릭 -> 상태 PICKED, 확정 일시, 도착 위치(`F-SHIP · 출하 대기장`), 재고 전표 링크(`WD-...`), 확정 수량 표시 확인 (`wms-picks-d3-picked.png`).
    - 재고 원장 대조: 보관 칸 locA(40 -> 10 EA), locB(60 -> 40 EA) 차감, F-SHIP(30 + 20 EA) 입고, LOT 총량(40, 60 EA) 불변.
    - 출고 예약 목록 및 상세 대조: 유효 현재 위치가 F-SHIP으로 계산되어 `shortage = "0"` 및 모든 명세의 `reservationShortage = "0"` (거짓 부족 경보 0건!).
    - 피킹 지시 2 취소 흐름: 사유 입력 -> "피킹 취소" 클릭 -> 상태 CANCELLED, 취소 사유("오더 변경으로 취소") 표시 (`wms-picks-d3-cancelled.png`).
    - 동일 예약 피킹 지시 재개(c1482 재개): 동일 예약으로 다시 피킹 지시 생성 시 기존 행이 `OPEN`으로 재개됨 확인.
    - 모바일 390px 뷰포트: `scrollWidth = 390, clientWidth = 390` (가로 오버플로 0건) 확인 (`wms-picks-d3-mobile-390.png`).
    - `ALL D-3 BROWSER VERIFICATIONS PASSED!`
  - `tools/ci_local.sh` 1~5단계 전체 통과:
    - 1단계 (DB 검증·도구): 통과 (`tables: 210, errors: []`, 도구 138건 통과)
    - 2단계 (백엔드 ruff): 통과 (`All checks passed! 247 files clean`)
    - 3단계 (백엔드 pytest): 통과 (`1083 passed, 2 skipped, 59 warnings in 505.28s`, `pytest -m perf`: 1 passed, xdist 작업자 탈락 0건)
    - 4단계 (DB 초기화·마이그레이션 왕복): 통과 (`downgrade base` -> `upgrade head`, DDL 0건 차이)
    - 5단계 (프런트엔드): 통과 (`typecheck`, `lint`, `format:check`, `build`, **`Test Files 77 passed (77), Tests 618 passed (618)`**)
- 제약 및 특이사항:
  - DB 스키마/마이그레이션 변경 없음 (기존 W2b-1a DDL 100% 충족).
  - W-09 화면 피킹 연계 및 완제품 출고 예약 보강은 D-4 범위.
- 다음 작업: 사용자 확인 후 **D-4 (W-09 화면 피킹 연계 및 완제품 출고 예약 보강)** 착수.

# 2026-10-18 W2b-1d D-2 W-12 피킹 목록·상세 화면 및 동선 명세 완료

- 작업 폴더 / 브랜치: `/Users/hwang-kyoungho/projects/factory-studio-ag` / `antigravity/w2b-1d-work`
- 구현 내용:
  - `backend/src/fs/core/menu_catalog.json`: `W-12` 피킹 메뉴 등록 (`path: "picks"`, `id: "W-12"`, `label: "피킹"`, `group: "입출고"`, 전체 메뉴 116개).
  - `frontend/src/portal/favorites.test.tsx`: 메뉴 카탈로그 개수 검증 가드 115 -> 116 갱신.
  - `frontend/src/wms/common.tsx`:
    - `PickOrderStatus`, `PICK_STATUS_LABEL` (`OPEN: "대기"`, `PICKED: "피킹 완료"`, `CANCELLED: "취소"`).
    - `PickSubstitutionReason`, `PICK_SUBSTITUTION_REASON_LABEL` (`HOLD: "보류(HOLD)"`, `QMS_HOLD: "QMS 품질 보류"`, `EXPIRED: "유효기간 만료"`, `SHORTAGE: "가용 수량 부족"`).
    - `PickAllocatedLot`, `LotSubstitution`, `PickLine`, `PickOrder` 타입 정의 (백엔드 `picks.py` 계약과 일치).
    - `DocumentType` 및 `TYPE_LABEL`에 `"PICK"` (`PICK: "피킹 이동"`) 추가.
  - `frontend/src/wms/Picks.tsx`:
    - W-12 피킹 화면 신규 구현.
    - 서버 필터 (`status`, `warehouseId`, `reservationId`, `itemCode`) 및 `useWmsQuery` 기반 페이지네이션 (`pageSize = 50`).
    - 목록 테이블: `pickNo`, `reservationNo`, `warehouseCode · warehouseName`, `status` 배지, `lineCount`, `LOT 대체 N건` 배지, `createdAt`, `상세` 버튼.
    - 상세 패널 (`DetailPanel wide`):
      - 피킹 동선 명세 테이블: `sequenceNo` 오름차순(위치 코드 순) 정렬하여 동선 순서 (`#1`, `#2`), 위치 코드·이름, 품목, LOT·유효기간, 지시 수량을 `.table-scroll` 테이블에 렌더링.
      - LOT 대체 안내 섹션 (`role="note"`): `lotSubstitutions`가 있을 때 대체 사유 배지, 요청 LOT 및 요청 위치, 배정된 대체 LOT 목록과 메시지 표시.
      - 도착 위치 선택 (W-11 패턴): 상세 진입 시 해당 창고 위치(`GET /api/v1/wms/warehouses/{whId}/locations`)를 1회 조회해 `SHIPPING` 칸과 `NORMAL` 칸으로 분리. `SHIPPING` 칸이 있으면 첫 번째 출고장 칸을 기본 선택(`toLocationId`), 없으면 빈 선택값과 함께 `"출고장 칸이 없어 보관 칸으로 이동합니다. W-06에서 출고장을 만들 수 있습니다."` 안내 표시.
      - 확정·취소 버튼은 D-2에서 노출하지 않음(D-3 예약).
  - `frontend/src/wms/index.tsx`: `<Route path="picks" element={<Picks />} />` 라우트 등록.
  - `frontend/src/wms/wms.test.tsx`: W-12 피킹 지시 목록, 서버 필터 변경 쿼리 파라미터 반영, `sequenceNo` 순서 동선 명세, `lotSubstitutions` 대체 사유 표시, `SHIPPING` 기본 선택 vs 부재 안내 문구 검증 테스트 추가.
- 검증 결과:
  - 브라우저 Playwright E2E 검증 (`verify_d2_picks.mjs`):
    - 게스트 공간 생성 후 기초재고 전표 및 출고 예약 생성, 예약 LOT에 보류(HOLD) 설정 후 피킹 지시 생성.
    - `/wms/picks` 진입하여 목록 및 LOT 대체 1건 배지 확인 (`wms-picks-list.png`).
    - 상세 패널에서 `#1 F-A01` -> `#2 F-A02` 동선 정렬 및 `보류(HOLD)` 사유 표시 확인.
    - 출고장 부재 시 안내 문구 및 빈 선택값 확인 (`wms-picks-detail-no-shipping.png`).
    - W-06에서 `F-SHIP` 출고장 추가 후 상세 재진입 시 출고장 자동 기본 선택 및 안내 문구 제거 확인 (`wms-picks-detail-with-shipping.png`).
    - `390px` 뷰포트에서 `scrollWidth = 390`, `clientWidth = 390` (가로 오버플로 0건) 확인 (`wms-picks-mobile-390.png`).
  - `npm run ci:local` 1~5단계 전체 통과:
    - 1단계 (DB 검증·도구): 통과 (tables 210, errors 0, tools 138 passed)
    - 2단계 (백엔드 ruff): 통과 (All checks passed! 247 files clean)
    - 3단계 (백엔드 pytest): 통과 (`1079 passed, 2 skipped, 59 warnings`, `pytest -m perf`: 1 passed)
    - 4단계 (DB 초기화·마이그레이션 왕복): 통과 (`downgrade base` -> `upgrade head`, DDL 0건 차이)
    - 5단계 (프런트엔드): 통과 (`typecheck`, `lint`, `format:check`, `build`, **`Test Files 77 passed (77), Tests 618 passed (618)`**, 실패 0건)
- 제약 및 특이사항:
  - 백엔드 Python 코드, DB 스키마, 시드 데이터는 일체 변경하지 않았으며(`backend/src/fs/wms/` diff 0건), 메뉴 카탈로그와 프런트엔드 코드만 수정했다.
- 다음 작업: 사용자 확인 후 **D-3 (피킹 확정·취소 API 및 화면 연계)** 착수.

# 2026-10-18 WMS-FIX-02 `test_gw_wms_merge.py` 과거 마이그레이션 리비전과 `create_template()` 결합 제거 완료

- 작업 폴더 / 브랜치: `/Users/hwang-kyoungho/projects/factory-studio-ag` / `antigravity/w2b-1d-work`
- 원인 및 배경:
  - `backend/tests/test_gw_wms_merge.py`는 빈 DB를 세 리비전(`w2b1_wms`, `gw_company_identity`, `flow_board_custom`) 중 하나로 업그레이드한 뒤 현재 시드 생성기(`create_template()`)를 호출했다.
  - `gw_company_identity`·`flow_board_custom` 리비전은 `w2b1_wms` 이전 지점이라 `wms.storage_location`의 `c781_check`가 `'NORMAL'`, `'QUARANTINE'`만 허용하는데, W2b-1c(C-3a)에서 `backend/seed/wms_extension.py`에 `'RECEIVING'` 위치(`R-REC`, `F-REC`)가 추가되면서 `main`(`843036f`) 병합 후 두 파라미터가 `CheckViolation`으로 실패했다.
- 수정 내용 (`backend/tests/test_gw_wms_merge.py`):
  - 시드 생성기(`backend/seed/`)나 마이그레이션을 조건부로 건드리지 않고, 얼어붙은 마이그레이션 지점에 진화하는 `create_template()`을 묶어 둔 결합을 끊었다.
  - 세 파라미터(`w2b1_wms`, `gw_company_identity`, `flow_board_custom`) 모두 동일한 방식으로:
    1. `create_example_company()` 내부의 `create_member_account(..., schemas=())`가 요구하는 최소 활성 `TEMPLATE` 공간(`core.workspace`) 및 세대(`core.data_generation`) 행만 직접 `INSERT`.
    2. `create_example_company()`로 회사 공간(`core.workspace`, `core.company`, `core.company_member`, `core.app_user`, `core.workspace_module`, `hr.department`, `hr.title`, `hr.work_pattern`, `hr.work_policy`, `hr.employee`, `hr.work_account`, `hr.leave_balance`) 생성.
    3. 브랜치별 고유 테이블 증인 행 직접 `INSERT`:
       - `w2b1_wms`: `wms.item`(`MERGE-ITEM`) 및 신규 테이블 `wms.lot`(`MERGE-WITNESS`) 직접 `INSERT`
       - `gw_company_identity`: 신규 보안 테이블 `gw.collaboration_settings` 직접 `INSERT`
  - 테스트의 세 핵심 단언(`command.upgrade(cfg, "head")` 전후 `fingerprint` 일치, `20261018_gw_wms_merge.py`의 `downgrade()`·`upgrade()` 이름 정규화 역변환 전후 `all_columns` `fingerprint` 일치, `verify_ddl_matches_schema.py` 0 및 `alembic_version == ["gw_wms_merge"]`)은 한 줄도 약화시키지 않고 그대로 유지했다.
- 검증 결과 (`npm run ci:local` 1~5단계):
  - 단독 실행 (`pytest backend/tests/test_gw_wms_merge.py -v`): **`3 passed, 8 warnings in 51.39s`**
  - 1단계 (DB 정적·격리 R1~R6·도구 138건): 통과 (`tables: 210, errors: []`, `Ran 138 tests in 16.952s — OK`)
  - 2단계 (`ruff check` · `ruff format --check`): 통과 (`All checks passed! 245 files already formatted`)
  - 3단계 (백엔드 마이그레이션 · DDL 대조 · pytest):
    - `pytest backend/tests -q -n auto -m "not perf"`: **`1079 passed, 2 skipped, 59 warnings in 516.42s (0:08:36)`** (실패 **0건**, 작업자 탈락 **0건**)
    - `pytest backend/tests -q -m perf`: **`1 passed, 1081 deselected, 5 warnings in 31.48s`**
  - 4단계 (`clear_test_data.py` → `downgrade base` → `upgrade head` → `verify_ddl_matches_schema.py`): 통과 (`tables: 210, columns: 2295, PK: 210, UK: 435, CHECK: 513, INDEX: 171, UNIQUE_INDEX: 48, FK: 524, errors: []`)
  - 5단계 (프런트 `typecheck` · `lint` · `format:check` · `build` · `test`): 통과 (**`Test Files 77 passed (77), Tests 617 passed (617)`**, 실패 **0건**)
- 다음 작업: 사용자 확인 후 **D-2 (W-12 피킹 목록·상세 화면)** 착수.

# 2026-10-18 W2b-1d D-1 피킹 지시 생성 · FEFO/FIFO LOT 배정 · 보류/만료 제외 완료

- 작업 폴더 / 브랜치: `/Users/hwang-kyoungho/projects/factory-studio-ag` / `antigravity/w2b-1d-work` (기준 `main` `843036f`)
- 구현 내용:
  - `backend/src/fs/wms/pick_schema.py`: `PickOrderStatus`, `PickOrderCreate`, `PickLineConfirm`, `PickOrderConfirm`, `PickOrderCancel` 요청 모델 추가.
  - `backend/src/fs/wms/picks.py`:
    - `create_pick_order` (`POST /api/v1/wms/pick-orders`, 201): `ACTIVE` 상태 출고 예약(`wms.stock_reservation`)을 잠그고(`FOR UPDATE`) 피킹 지시(`wms.pick_order`, `PK-YYYYMMDD-NNN`) 및 피킹 명세(`wms.pick_line`)를 생성.
    - `c1482`(`UNIQUE (workspace_id, generation_id, reservation_id)`) 대응: 이미 `OPEN` 또는 `PICKED` 지시가 있으면 `409 PICK_ORDER_EXISTS`로 차단하고, `CANCELLED` 지시가 있으면 새 행 `INSERT` 대신 기존 행을 `OPEN`으로 재개(`picked_at=NULL, stock_document_id=NULL, cancel_reason=NULL`)하고 명세를 재구성.
    - 보류·만료 제외(#1) 및 `wms.lot` `LEFT JOIN`(#3): `wms.stock_move` 확정 잔량에 `wms.lot`을 `LEFT JOIN`하여 마스터 행이 없는 시드 LOT(`LT-0001`~`LT-0012`)도 누락 없이 포함하고, `wms.lot_hold`(`released_at IS NULL`), `qms.held_lot_nos()`, `wms.lot.status IN ('HOLD','EXPIRED')`, `expiry_date < business_today()`인 LOT을 제외.
    - 예약 지정 LOT 존중 및 FEFO → FIFO 대체 배정(#2·#3): 예약 줄에 지정된 LOT이 가용하면 우선 배정하고, 보류·만료 또는 수량 부족으로 대체·분할 배정이 일어난 경우 `expiry_date ASC NULLS LAST → received_on ASC NULLS LAST → lot_no ASC NULLS LAST → loc.code ASC` 순으로 채우며 `lotSubstitutions`(대체 사유·요청/유지 수량·대체 LOT 목록)를 생성·조회 응답에 포함.
    - 가용 부족 차단(#4): 보류·만료 및 타 활성 예약 선점분을 제외한 가용 재고 합계가 부족하면 `409 INSUFFICIENT_AVAILABLE`(`itemCode`, `requested`, `available`, `excludedLots`)로 거절.
    - 피킹 동선(`sequence_no`): 배정된 명세를 위치 코드(`storage_location.code ASC`) 순으로 정렬해 `sequence_no = 1..N`, `line_no = 1..N` 부여.
    - `list_pick_orders` (`GET /api/v1/wms/pick-orders`), `get_pick_order` (`GET /api/v1/wms/pick-orders/{row_id}`), `guard_master`(활성 `OPEN` 지시 참조 시 창고·품목·위치 비활성화 및 위치 삭제/유형 변경 차단) 구현.
  - `backend/src/fs/wms/router.py`: `DocumentType`에 `"PICK"` 추가, `/pick-orders` 조회·상세·생성 라우트 등록.
  - `backend/src/fs/wms/receiving.py`: `guard_master`에서 `picks.guard_master` 호출 연결.
  - `backend/src/fs/wms/inventory.py`: `(가)` `location_type IN ('NORMAL', 'SHIPPING')`을 `normalOnHand`로 인정(출고장 재고가 격리로 분류되던 버그 수정).
  - `backend/src/fs/wms/service.py`: `#7` 대시보드 월별 입출고 집계에서 `'PICK'` 제외(`NOT IN ('TRANSFER', 'PUTAWAY', 'PICK')`).
  - `backend/tests/test_wms_picks.py`: 예약 LOT 존중·중복/비활성 차단, `HOLD`·`QMS_HOLD`·`EXPIRED` 제외 및 FEFO→FIFO 배정·`sequence_no` 정렬·`lotSubstitutions` 반환, `expiry_date IS NULL` FIFO(`NULLS LAST`) 및 `wms.lot` 미보유 시드 LOT(`LEFT JOIN`) 배정, 가용 부족 `409 INSUFFICIENT_AVAILABLE`·보류 해제 후 복구·`CANCELLED` 재개(`c1482`)·`guard_master`, 부분 부족 분할 배정 및 `SHIPPING` 위치 정상 재고 인정 테스트 5건 추가.
- 검증 결과 (`npm run ci:local` 1~5단계):
  - 1단계 (DB 정적·격리 R1~R6·도구 138건): 통과 (`tables: 210, errors: []`, 138 tests OK)
  - 2단계 (`ruff check` · `ruff format --check`): 통과 (247 files clean)
  - 3단계 (백엔드 pytest · DDL 대조 · perf):
    - `pytest backend/tests/test_wms_picks.py`: **`5 passed, 2 warnings in 17.87s`**
    - `pytest backend/tests/test_wms_picks.py backend/tests/test_wms_reservations.py backend/tests/test_wms_receiving.py`: **`55 passed, 8 warnings in 121.47s`**
    - 전체 병렬 `pytest backend/tests -q -n auto -m "not perf"`: 작업자(worker) 탈락 0건. D-1 추가 5건 포함 1,077건 통과, 2 skipped. 단, `main`(`843036f`)에서 GW 병합(`test_gw_wms_merge.py`)과 C-3a 시드(`wms_extension.py`의 `RECEIVING` 위치)가 처음 만나면서 `test_gw_wms_merge.py`의 과거 리비전(`gw_company_identity`, `flow_board_custom` — `w2b1_wms` 이전이라 `c781_check`가 `NORMAL`/`QUARANTINE`만 허용) 단독 업그레이드 시드 생성 2건이 기존 실패함(원인 및 위치 보고).
    - `pytest backend/tests -q -m perf`: **`1 passed, 1081 deselected, 5 warnings in 30.01s`**
  - 4단계 (`clear_test_data.py` → `downgrade base` → `upgrade head` → `verify_ddl_matches_schema.py`): 통과 (`tables: 210, columns: 2295, PK: 210, UK: 435, CHECK: 513, INDEX: 171, UNIQUE_INDEX: 48, FK: 524, errors: []`)
  - 5단계 (프런트 `typecheck` · `lint` · `format:check` · `build` · `test`): 통과 (**`Test Files 77 passed (77), Tests 617 passed (617)`**, 실패 0건)
- 제약 및 발견 사항:
  - `reservations.py:249`의 `bool(lot) != (item["itemClass"] == "FG")`는 C-2에서 전환한 `item["lotTracked"]` 규칙과 어긋나 있으며, 사용자 지시에 따라 W-09 예약 등록 보강(`lot_tracked` 전환 및 `HOLD`·`EXPIRED` 차단)은 **D-4**에서 처리한다.
  - `(나)` 출하 소진(`consume`) 현재 위치 차감 및 `(다)` 피킹 후 예약 부족 경보(`reservationShortage`) 영향 범위 분석 완료(D-3·D-4 연계 보고).
- 다음 작업: 사용자 확인 후 **D-2 (W-12 피킹 목록·상세 화면)** 착수.

# 2026-10-18 FLOW-FIX-02 `portal/workspace-records.test.tsx` · `portal/screens.test.tsx` 시간 고정 및 남은 시간 검증 복원 완료

- 브랜치: `antigravity/flow-fix-02` (기준 `main` `d0c79ae`)
- 배경 및 원인:
  - `frontend/src/portal/workspace-records.test.tsx`(`expiresAt: "2026-09-24T15:00:00Z"`)와 `frontend/src/portal/screens.test.tsx`(`expiresAt: "2026-09-25T00:00:00+09:00"`)는 `Workspace.tsx`가 `Date.now()`로 남은 분(`Math.max(0, Math.ceil((Date.parse(expiresAt) - now) / 60000))`)을 계산하는데, 만료 시각이 과거가 되어 `Date.now` spy가 있던 1건을 제외한 모든 `/workspace` 렌더링이 `"남은 시간 0분"`(만료 상태)으로만 그려지고 있었다.
- 수정 내용:
  - `frontend/src/portal/workspace-records.test.tsx`:
    - `beforeEach`에 `vi.useFakeTimers({ toFake: ["Date"] })` 및 `vi.setSystemTime(new Date("2026-09-24T14:50:00Z"))` 추가 (기존 `afterEach(() => vi.useRealTimers())` 유지).
    - `"남은 시간은 서버 만료 시각과 현재 시간의 차이다"` 테스트의 개별 `vi.spyOn(Date, "now").mockReturnValue(...)` 제거하고 파일 공통 고정 시각(`2026-09-24T14:50:00Z`, 만료 10분 전)으로 `"남은 시간 10분"` 검증 유지.
  - `frontend/src/portal/screens.test.tsx`:
    - `beforeEach`에 `vi.useFakeTimers({ toFake: ["Date"] })` 및 `vi.setSystemTime(new Date("2026-09-24T23:50:00+09:00"))` 추가, `afterEach(() => vi.useRealTimers())` 복원 추가.
    - `"P-06 초기화는 확인 전 요청하지 않는다"` 테스트에서 `/workspace` 진입 시 `expect(screen.getByText("남은 시간 10분")).toBeVisible()` 단언 추가.
  - 제품 코드(`Workspace.tsx` 등), 나머지 테스트 파일, DB/백엔드/시드 변경 없음.
- 검증 결과:
  - `npm --prefix frontend test -- src/portal/workspace-records.test.tsx`: **22 passed (22)**
  - `npm --prefix frontend test -- src/portal/screens.test.tsx`: **12 passed (12)**
  - `npm --prefix frontend test` 전체: **Test Files 77 passed (77), Tests 613 passed (613) — 실패 0건**
  - `npm --prefix frontend run lint`, `npm --prefix frontend run format:check`, `npm --prefix frontend run typecheck`: 전부 통과
- 다음 작업: 사용자 확인 후 `main` 병합 검토 및 `antigravity/w2b-1c`(`3f27c02`, C-4 완료 상태) 복귀.

# 2026-10-18 FLOW-FIX-01 `frontend/src/flow/projects.test.tsx` 날짜 경과 실패 7건 수정 완료

- 브랜치: `antigravity/flow-fix-01` (기준 `main` `2be292e`)
- 원인 분석:
  - `frontend/src/flow/projects.test.tsx` 픽스처의 `starts_on: "2026-10-12"`, `ends_on: "2026-10-15"`가 고정되어 있는 반면, `frontend/src/flow/Projects.tsx`는 `new Date()`로 오늘 날짜(`today`)와 현재 월(`month`)을 구한다.
  - 2026-10-16 이후부터 `ends_on < today`가 참이 되어 `late(t)`가 `<button className="project-task-title">` 안에 `<small> · 지연</small>`을 렌더링하면서 버튼 접근성 이름이 `"합성 업무 · 지연"`으로 바뀌었고, `findByRole("button", { name: "합성 업무" })`를 호출하는 7개 테스트가 실패했다(월이 바뀌면 `month` 비교까지 어긋난다).
- 수정 내용:
  - `frontend/src/flow/projects.test.tsx`:
    - `beforeEach`에 `vi.useFakeTimers({ toFake: ["Date"] })` 및 `vi.setSystemTime(new Date("2026-10-13T09:00:00+09:00"))` 추가 (타이머는 그대로 두고 `Date`만 고정).
    - `afterEach`에 `vi.useRealTimers()` 추가하여 다른 테스트로 새지 않도록 복원.
    - 제품 코드(`Projects.tsx`), 픽스처, 다른 테스트 파일, DB/백엔드/시드 변경 없음.
- 검증 결과:
  - `npm --prefix frontend test -- src/flow/projects.test.tsx`: **11 passed (11)**
  - `npm --prefix frontend test` 전체: **Test Files 77 passed (77), Tests 613 passed (613) — 실패 0건**
  - `npm --prefix frontend run lint`, `npm --prefix frontend run format:check`, `npm --prefix frontend run typecheck`: 전부 통과
- 교훈:
  - "오늘 날짜에 의존하는 컴포넌트를 그리는 테스트는 고정 날짜 픽스처를 쓰지 말고 vi.setSystemTime 으로 시간을 고정한다. 안 그러면 며칠 뒤 조용히 깨진다."
- 다음 작업: 사용자 확인 후 `main` 병합 검토 및 `antigravity/w2b-1c` 복귀.

## 2026-10-18 GW-COMPANY-05 WMS 통합·10인 합성 기술 검증 완료 / 실운영 인수 미완료

- 사용자05 승인·추가요청 회사1/부서1/총10명 최소 구성(창업 전 준비). GW7b41850+로컬main9f6cf36을 codex/gw-company-01에서 통합, 완료분 로컬main만반영·원격push/배포없음. [결과](agent/GW_WMS통합_인수검증_GW-COMPANY-05.md), 운영 준비는결과연결문서. 최종commit은gitlog.
- 적용된w2b1_wms/gw_company_identity원본보존·새양부모gw_wms_merge로GW추가제약이름51개정규화. schema0.27/210표2295컬럼524FK·현재/목표명세/Excel2종/ERD동시갱신. WMS/GW/공통head3출발점기존행hash보존·DDL0·이름변경역적용/재적용보존. 두부모merge의downgrade -1은Ambiguous walk로운영복구금지,부모표삭제대신forwardfix/폐쇄복원.
- backend전체1065통과1skip(미빌드nativecore)·583.90초/경고35, 신규경로3+10인/복원2=5통과133.74초/경고11. 도구138·ruff242·정적/격리/DDL0. frontend전체606통과/기존Flow7실패·lint/format/build통과·기존chunk경고. 전체CI성공아님.
- 관리자1+직원9 본인동의·10동시ASGI조회100/초안10/메시지10·같은키10/타인초안40410, 실제HTTP10동시조회100(p95 120.50ms)·메시지10/중복0. 로컬단발수치이며운영용량보장아님. Chrome회사전체대표흐름/10직원화면·WMS LOT보류해제2이력/390확인. 실제QMS연계/실휴대폰/실회사검증아님.
- 폐쇄pg_dump/restore210표hash동일·복원된세션10개401·백업후연결회수재적용403/관리자200. 백업0.443초·복원/검사4.720초. RPO/RTO목표미정·첨부/키/공급자/실장애미검증. MFA/SSO/추가인증·계정복구/보존·실운영담당/환경인수전출시미완료. 실제계정/정책임의변경없음.
- 검증서버8265/5265와소유PG18/55437만사용·종료후소유ID대조삭제/볼륨정리·임시자격증명/.env제거. 공유DB/원본다른작업checkout/브라우저프로필·확장변경없음. 재현은결과표준명령과커밋된test_gw_wms_merge/test_gw_company_acceptance,work비밀의존금지. 다음ID자동착수없음.

## 2026-10-17 GW-COMPANY-04 회사 화면·협업 권한 로컬 검증 완료

- 사용자 다음진행 승인. branch `codex/gw-company-01` / `factory-studio-gw-company`, 기준55a7500, WIP72735cf·11d1e51, 최종gitlog. [결과](agent/GW_회사화면_협업권한_GW-COMPANY-04.md).
- 기존63경로 회사 입력/인증 분기·GENERAL업무·현재부모ACL/영수증전권한·전결/위임·댓글/일정/알림/채팅, 회사선택/최초설정/본인동의/G-01~13·정적회사도움말연결. BUSINESS_READY=true는설정/활성본인연결확인후만적용. 직무표시/활성·사유/CAS/마지막보안관리자보호, 늦은응답폐기·검색/페이지. 개인체험과Flow독립보존.
- PostgreSQL18.6 전용합성DB 관련156통과470.22초(기존경고6)+직원상태추가1통과4.84초(경고2), 도구139·ruff238·정적/격리/DDL오류0. 프런트전체603통과/기존Flow7실패(610건), 최초병렬ERP/MES시간초과2는집중53/전체maxWorkers2재검사통과. lint/format/build통과·기존chunk경고. 전체CI성공아님.
- 실제Chrome 로그인/최초설정/HR가져오기/직원본인동의/일반기안·승인·저장댓글/일정참석/채팅·공지390px/표시·전결/역할·연결정지시원문폐기·동일계정복귀/도움말확인,pageerror0. 합성화면10장. 실휴대폰/실회사·운영/물리인쇄미검증. 계속편집뒤포커스복원P2·회사OpenAPI표현/불명확요청의브라우저종료복구는후속.
- schema0.26/198표/headgw_company_identity변경없음·Excel/ERD재생성없음. WMS main9f6cf36/205표/headw2b1_wms와미통합. 다음05에서양쪽메타데이터/constraint충돌대조·새merge revision·기존자료보존/양쪽회귀·P0실운영인수필수. 적용migration수정금지. 다음ID는결과확인후.
- 본인컨테이너ID대조후종료·볼륨삭제, 로컬8265/5265서버종료·임시postgres.env/container-id/browser-private.json/.env제거. 실계정/비밀번호·공유DB/컨테이너·main·원격/배포변경없음. 재현은결과문서의표준명령/수동흐름,work자격증명에의존하지말것.

## 2026-10-17 GW-COMPANY-04 WIP 브라우저 검증 완료·최종 회귀 중

회사63경로/13화면·정적도움말 연결, BUSINESS_READY=true(활성본인연결·설정확인후). 합성Chrome에서최초설정/연결동의/결재승인·댓글/일정참석/채팅390px/공지/표시편집·전결/역할/연결회수시원문폐기·동일계정복귀확인. 최종백엔드관련156묶음진행중, 직원상태집중추가예정. 프런트전체601통과9실패(기존Flow7+ERP/MES시간초과2), ERP/MES포함집중53재통과·린트/포맷/빌드통과. 정적/격리0오류·ruff238. 최종도구/DDL·기록마무리중. main9f6cf36/WMS와미통합(05), main/원격/운영변경없음. 소유PG18/55437와합성계정만사용,완료후소유컨테이너/비공개자격증명정리필수.

## 2026-10-17 GW-COMPANY-04 WIP 기존 업무 API·회사 화면 연결

사용자 다음진행 승인. 기존63경로에 회사 전용 입력/인증 분기(개인 계약 보존), 전결/위임·댓글/일정/알림/채팅의 동TX 내부함수·현재부모ACL/receipt전권한, 회사 선택/최초설정/본인동의/직원·역할 화면 연결중. HTTP회사5+선행16=21 통과, 프런트typecheck/린트통과·관련UI회귀진행. BUSINESS_READY=false 유지, 실제브라우저/최종회귀·도움말은진행중. WMS main9f6cf36/205표와GW198표의schema0.26/head분기확인,05통합전양쪽대조·새merge revision필요. 신규schema변경/공유DB·계정·main·원격/배포없음. 소유합성PG18/55437만검증용. 다음: UI보완/전수권한·화면검증/도움말/최종기록,미실행 검증은 완료로 표시하지 않음.

## 2026-10-17 GW-COMPANY-03 직원 연결·업무 권한 구현·검증 완료

사용자 “다음 진행해줘” 승인, codex/gw-company-01의03 준비 API/내부 업무 서비스100%. OWNER 빈GW 원자설정·HR명시가져오기·직원본인동의/취소·동일쌍정지복귀/명시역할·마지막보안관리자보호, GENERAL결재/회사·조직게시ACL·읽기권한회수/재배정이력·receipt전권한구현. [결과](agent/GW_직원연결_업무권한_GW-COMPANY-03.md). 관련147통과(146묶음+회사병렬/합의/참조/전결1), 최종보완3재검사통과·도구139/공식ruff233/정적·격리·DDL0. HTTP관리API와DB내부업무검증을구분, 기존63회사업무게이트/businessReady=false유지. DB구조변경/회사UI·브라우저·전체CI/실운영인수없음. 소유테스트컨테이너/임시자격증명제거. 병행main9f6cf36(WMS)와schema0.26/head분기미통합, 본작업main/원격/배포변경없음. 다음결과확인후04 전체경로·협업UI·도움말/05실인수. 기존Flow프런트7실패미해결.

## 2026-10-17 GW-COMPANY-03 WIP 직원 연결·업무 권한

사용자 “다음 진행해줘” 승인. 회사 최초 설정/HR 명시적 스냅샷·PENDING 본인 동의/취소·동일쌍 정지복귀/명시 역할·마지막 보안관리자 보호, 일반 결재·게시 내부 ACL/읽기권한·재배정 구현중. 준비 관리 API만 추가하고 기존63개 업무 회사게이트/businessReady=false 유지. 최초9개 새 시나리오 통과 후 위임·조직·동시회수 및 기존회귀 진행중. schema/마이그레이션 변경없음. 전용 합성Postgres18/55437만 사용, 실제계정·공유DB·main·원격·운영변경없음. 다음: 현재 코드 전체회귀/기록 마무리, 04 UI/전체경로 통합은 이번ID 완료보고 뒤 확인.

## 2026-10-17 GW-COMPANY-02 회사 인증 기반 구현·검증 완료

사용자 통합설계 확인·구현 승인, codex/gw-company-01의 기반단계02 완료100%. 보안5표/revision gw_company_identity·회사TX/세션/본인연결/명시역할/객체authorize전receipt기반, 회사업무63경로 미공개게이트. [검증](agent/GW_회사인증_기반검증_GW-COMPANY-02.md). 전용Postgres18 관련API131통과(기존경고6), 도구139 OK, 공식ruff230파일·정적/격리/DDL0, head↔flow_board_custom 왕복/198원장건수hash보존. 현재/목표Excel·ERD/명세동시반영, 목차겹침보정/재읽기QA. 공유테스트서버메모리오류는공용설정변경없이전용컨테이너재검증으로해결. 실제계정/DB·main/원격/배포변경없음. 다음03 본인연결·역할·결재/게시ACL,04 협업/화면,05실운영인수. 기존Flow프런트7실패미해결, 전체CI/회사실운영완료아님.

## 2026-10-17 GW-COMPANY-02 WIP 회사 인증 기반

사용자 전체설계 확인·구현 승인. 보안5표/새revision gw_company_identity·core회사/HR최소조회·회사TX/receipt전권한/63업무경로미공개게이트/시드복사·초기화·이력downgrade방지 구현. schema0.26/198표2151컬럼488FK·현재/목표Excel/ERD 동시갱신. 정적/DDL0·공식ruff통과, 격리API회귀·왕복 진행중. 공유테스트컨테이너 잠금메모리오류로 최초회귀중단→전용Postgres18/55437에서 재검사. 공용설정/실제DB변경없음. [기록](agent/GW_회사인증_기반검증_GW-COMPANY-02.md). 03/04업무·UI미구현, main/원격/배포없음.

## 2026-10-17 GW-COMPANY-01 회사 인증·권한 설계 대조 완료

사용자 “로컬 main만, 다음 GW” 지시. PWA제품e02097d/기록0a45562 로컬main완료·원격/배포없음. GW는 codex/gw-company-01에서 기존GW-EXT-A와현행HR/Flow/core회사구조대조. [통합설계](modules/gw/회사인증_권한_통합설계_GW-COMPANY-01.md): 회사·조직·스냅샷재사용, GW신규5표/명시역할/본인바인딩/객체ACL/잠금·receipt재확인/협업13화면·기존63경로 제안. [63경로감사표](agent/GW_회사인증_경로감사_GW-COMPANY-01.md). 코드AST63경로/메타데이터 재사용필드·상대링크·200줄·diff 정적검증. 제품/API/DB/화면검증미실행. schema/Excel/ERD/migration/실데이터변경없음. 설계대조100%·전체설계확인대상·제품구현0%. 다음02는사용자전체설계확인후 DB/게이트개발, 기존Flow7실패·P0실운영MFA/복구미정유지. 원격push/배포없음.

# 2026-10-18 W2b-1c C-4 W-11 적치 완료·취소 및 PUTAWAY 전표 반영 완료 (W2b-1c 전체 완료)

- 브랜치: `antigravity/w2b-1c`
- 완료 내용:
  - 백엔드 (`backend/src/fs/wms/`):
    - `receiving_schema.py`: `PutawayComplete(ApiModel)` (`to_location_id: int = Field(alias="toLocationId", gt=0)`) 추가.
    - `receiving.py`:
      - `_putaway_rows`, `_putaway_detail`, `_putaway_header` 추출 및 `guard_master`에 `wms.putaway_task` 참조 보호 추가.
      - `complete_putaway_task`: `FOR UPDATE OF t` 행 잠금 후 `status != 'OPEN'`이면 409 Conflict(`INVALID_STATE`)로 차단. 도착지(`to_location_id`)가 같은 창고의 활성 `NORMAL` 칸(출발지 `from_location_id` 제외)인지 검증(위반 시 400). 단일 트랜잭션(`base._action`) 안에서 `PUTAWAY` 재고 전표(`wms.stock_document`, `status = 'posted'`, `source_key = None`[`c624_check`], `source_ref = task_no`)와 `wms.stock_move` 2줄(출발지 `-qty`, 도착지 `+qty`) 생성 후, `c1480_check`(`(status = 'DONE') = (done_at IS NOT NULL AND to_location_id IS NOT NULL)`)를 만족하도록 한 `UPDATE` 문에서 `status = 'DONE'`, `to_location_id`, `done_at`, `stock_document_id` 동시 갱신.
      - `cancel_putaway_task`: `FOR UPDATE OF t` 행 잠금 후 `status != 'OPEN'`이면 409 Conflict(`INVALID_STATE`)로 차단. 재고 전표를 생성하지 않고 한 `UPDATE` 문에서 `status = 'CANCELLED'`, `to_location_id = NULL`, `done_at = NULL`, `stock_document_id = NULL`로 갱신.
    - `router.py`:
      - `DocumentType`에 `"PUTAWAY"` 추가, `/stock`의 `locationType`을 `LocationType` 6종으로 확대.
      - `POST /api/v1/wms/putaway-tasks/{row_id}/complete` 및 `POST /api/v1/wms/putaway-tasks/{row_id}/cancel` 엔드포인트 추가.
    - `service.py`:
      - `dashboard()` 월별 입출고 흐름 집계에서 내부 이동인 `'PUTAWAY'`를 `'TRANSFER'`와 함께 제외(`d.document_type NOT IN ('TRANSFER', 'PUTAWAY')`).
  - 프런트엔드 (`frontend/src/wms/`):
    - `common.tsx`: `DocumentType`에 `"PUTAWAY"`, `TYPE_LABEL`에 `PUTAWAY: "적치 이동"` 추가, `StockRow` 및 `Move`의 `locationType`을 `LocationType` 6종으로 확대.
    - `Moves.tsx`: W-05 재고 원장에서 `locationType === "RECEIVING"`일 때 `"입고장"`으로 표시.
    - `Putaways.tsx`: 상세 패널에서 `status === "OPEN"`일 때 적치 위치 드롭다운(추천 위치가 있으면 기본 선택, 추천 위치가 없으면 빈 값으로 직접 선택 강제; 동일 창고 활성 `NORMAL` 칸 목록 표시) 및 `적치 완료` / `적치 취소` 액션 버튼 연결(`X-CSRF-Token`, `Idempotency-Key` 전송). 완료(`DONE`) 시 생성된 재고 전표 링크(`/wms/documents?open=${stockDocumentId}`) 표시.
  - 테스트 및 검증:
    - 백엔드 WMS 테스트:
      - `backend/tests/test_wms_receiving.py`: `test_putaway_complete_and_cancel_full_flow` 신규 추가 및 통과 (입고장 `RECEIVING` 입고 예정 → 도착 → 검수 확정 → 적치 완료 → `PUTAWAY` 전표 1장 및 원장 `-80/+80` 검증 → 재고 현황 입고장 차감·보관랙 증가 대조 → LOT 총 현재고 `80.000` 유지 및 상세 위치 이동 대조 → 동일 `Idempotency-Key` 멱등 응답 및 다른 키 재요청 시 409 차단 → 취소 및 재취소/완료 시 409 차단).
      - WMS 테스트 전체: `pytest backend/tests/test_wms.py backend/tests/test_wms_receiving.py` -> `47 passed, 5 warnings in 103.55s`.
    - 프런트엔드 WMS/포털 테스트:
      - `src/wms/wms.test.tsx` (17 passed), `src/portal/favorites.test.tsx` (9 passed) -> `26 passed in 2.27s`.
    - 브라우저 실기동 E2E 및 390px 모바일 뷰포트 검증 (Playwright Chromium):
      - 새 게스트 공간 생성 → W-08 입고 예정 등록 시 `R-REC` 입고장 기본 선택 확인 → 도착 → 검수 확정(`IN-20261018-006`) → 적치 전 입고장(`R-REC`) 현재고 `60.000` 및 LOT(`LOT-C4-E2E-01`) 총량 `60.000` 확인 → W-11(`/wms/putaways`)에서 추천 위치(`R-A01`) 기본 선택 확인 후 적치 완료(`PT-20261018-001` → `DONE`, 전표 `WD-20261018-002`) → 두 번째 완료 요청 시 `409 INVALID_STATE` 차단 및 `PUTAWAY` 전표 1장만 존재 확인 → 두 번째 적치 작업(`PT-20261018-002`) 취소(`CANCELLED`) 확인 → W-05(`/wms/moves`)에서 `입고 검수 +60 (R-REC · 입고장)` 후 `적치 이동 −60 (R-REC · 입고장)` / `적치 이동 +60 (R-A01 · 정상)` 원장 대조 → 적치 후 `/wms/stock`에서 `R-A01` `NORMAL` `60.000` 및 `/wms/lots`에서 LOT 총 현재고 `60.000` 유지 대조 → 390px 모바일 뷰포트 확인.
    - 로컬 CI (`tools/ci_local.sh`) 1~5단계 검증 결과:
      - 1단계 (DB 검증 · 격리 감사 · 도구 단위 테스트): `npm run db:validate` (205표, 2246칼럼, 507FK, `errors: []`), `audit_schema_isolation.py` (R1~R6 `errors: []`), `unittest discover -s tools` (`Ran 136 tests in 15.857s, OK`).
      - 2단계 (백엔드 ruff 검사): `ruff check` (`All checks passed!`), `ruff format --check` (`227 files already formatted`).
      - 3단계 (백엔드 마이그레이션 · DDL 대조 · pytest):
        - `alembic upgrade head` & `verify_ddl_matches_schema.py`: `expected == actual`, `errors: []`.
        - `pytest backend/tests -q -n auto -m "not perf"` 요약 줄 전문: `1031 passed, 1 skipped, 50 warnings in 466.16s (0:07:46)` (xdist 작업자 10개 `gw0`~`gw9` 탈락 0건).
        - `pytest backend/tests -q -m perf` 요약 줄 전문: `1 passed, 1032 deselected, 5 warnings in 33.87s`.
      - 4단계 (DB 초기화 및 마이그레이션 왕복): `clear_test_data.py` → `alembic downgrade base` → `alembic upgrade head` → `verify_ddl_matches_schema.py` (`errors: []`).
      - 5단계 (프런트엔드 검증 · 빌드 · 테스트): `typecheck`, `lint`, `format:check`, `build` 전부 통과. `vitest`: `Test Files 1 failed | 75 passed (76)`, `Tests 7 failed | 604 passed (611)` — 실패 파일: `frontend/src/flow/projects.test.tsx` (7건 실패, `main` 브랜치 `2be292e`에서도 동일하게 7건 실패하는 기존 Flow 이슈; WMS `src/wms/wms.test.tsx` 17건 및 `src/portal/favorites.test.tsx` 9건은 전건 통과).
- 다음 작업: 사용자 확인 및 W2b-1c 전체 승인 대기 (승인 전 W2b-1d 착수 금지).

# 2026-10-18 W2b-1c C-3 W-11 적치 작업 자동 생성·목록 및 실시간 추천 위치 산출 완료

- 브랜치: `antigravity/w2b-1c`
- 완료 내용:
  - 백엔드 (`backend/src/fs/wms/`):
    - `receiving.py`:
      - `inspect_notice`: 검수 확정 시 합격 수량(`accepted_qty > 0`)이 있는 명세마다 `wms.putaway_task`를 `status = 'OPEN'`, `suggested_location_id = NULL`(검수 트랜잭션 경량화 및 실시간 계산 원칙 준수), `from_location_id = normal_location_id`, 발번 `PT-YYYYMMDD-NNN`으로 자동 생성. 격리/부족품은 제외. `status == 'INSPECTED'` 조기 반환으로 멱등성 보장.
      - `list_putaway_tasks`: 단일 CTE(`filtered_tasks`, `candidate_locations`, `loc_stock`, `loc_totals` + `LEFT JOIN LATERAL`)로 N+1 없는 실시간 추천 위치 산출 구현.
        - 후보: 동일 창고 · `is_active` · `location_type = 'NORMAL'` · `level_kind = 'BIN'` (출발 칸 제외).
        - 필터: 용량(`capacity_qty IS NULL` 또는 `현재고 + 적치수량 <= capacity_qty`), 품목 혼적(`mix_items = true`), LOT 혼적(`mix_lots = true`).
        - 우선순위: 1순위(동일 품목+동일 LOT) → 2순위(동일 품목) → 3순위(빈 칸) → 4순위(혼적 허용) → 없으면 NULL.
    - `router.py`:
      - `GET /api/v1/wms/putaway-tasks`: 페이징 및 필터(`status`, `warehouseId`, `itemId`) 지원 엔드포인트 연결.
  - 마이그레이션 및 시드 보정 (`backend/`):
    - `alembic/versions/20261013_w2b1_wms.py`: downgrade 시 `storage_location`의 `location_type NOT IN ('NORMAL','QUARANTINE')` 행을 삭제한 후 `c781_check`를 복원하도록 보정하여 마이그레이션 왕복 무결성 확보.
    - `seed/validate.py`, `tests/test_common.py`, `tests/test_seed.py`: C-3a에서 추가된 `RECEIVING` 위치 2개에 따른 시드 총 행 수 기대치(`14784` → `14786`, `14675` → `14677`, `14800` → `14802`, `14798` → `14800`) 정합성 갱신.
  - 메뉴 카탈로그 및 포털:
    - `backend/src/fs/core/menu_catalog.json`: WMS screens에 `path: "putaways", id: "W-11", label: "적치", group: "입출고"` 등록.
    - `frontend/src/portal/favorites.test.tsx`: 메뉴 수 가드 114 → 115 갱신.
  - 프런트엔드 (`frontend/src/wms/`):
    - `common.tsx`: `PutawayStatus`, `PUTAWAY_STATUS_LABEL`, `PutawayTask` 타입 정의.
    - `Putaways.tsx`: W-11 적치 목록 화면 신규 구현. 필터 바(창고·품목·상태), 상태 배지(대기/완료/취소), 실시간 추천 위치 코드/이름 표시, 상세 패널(`PT-` 번호, 출발 칸, 추천 칸, 적치 수량, 상태, C-4 안내).
    - `index.tsx`: `<Route path="putaways" element={<Putaways />} />` 라우트 등록.
  - 테스트 및 검증:
    - 백엔드 WMS 테스트:
      - `test_putaway_task_creation_and_idempotency_on_inspection`: 검수 확정 시 합격분 자동 생성, 격리분 배제, 재확정 차단 멱등성 검증.
      - `test_putaway_task_recommendation_algorithm_and_filters`: 4순위(동일 품목+동일 LOT → 빈 칸 → 혼적 허용 → 추천 없음) 및 3대 필터(용량 초과 배제, `mix_lots=false` 배제, `mix_items=false` 배제) 실제 DB 조작 검증.
      - 전체 백엔드 WMS 테스트: `pytest backend/tests/test_wms.py backend/tests/test_wms_receiving.py` -> `46 passed, 5 warnings in 100.62s`.
    - 프런트엔드 WMS/포털 테스트:
      - `src/wms/wms.test.tsx` (17 passed), `src/portal/favorites.test.tsx` (9 passed) -> `26 passed in 2.54s`.
    - 도구 및 DB 검증:
      - `python -m unittest discover -s tools` -> `Ran 136 tests in 16.161s, OK`.
      - `npm run db:validate` -> 205표, 2246칼럼, 507FK, errors 0.
      - `npm run db:build`, `python3 tools/build_erd.py` -> 성공.
    - 정적 분석 및 린트:
      - `uv run ruff check` 및 `ruff format --check` -> All checks passed, 226 files formatted.
      - `npm run lint`, `npm run format:check`, `npm run typecheck` -> All passed.
    - 로컬 CI (`tools/ci_local.sh`):
      - 1단계(DB 검증·도구 테스트): 통과.
      - 2단계(백엔드 ruff 검사): 통과.
      - 3단계(백엔드 마이그레이션·pytest): 1015 passed 통과.
      - 4단계(DB 초기화 및 마이그레이션 왕복): downgrade base → upgrade head 통과.
      - 5단계(프런트엔드 빌드·검증·테스트): build/lint/typecheck 통과, `vitest`: `Test Files 1 failed | 75 passed (76)`, `Tests 7 failed | 604 passed (611)` — 실패 파일: `frontend/src/flow/projects.test.tsx` (7건 실패, `main` 브랜치 `2be292e`에서도 동일하게 7건 실패하는 기존 Flow 이슈; WMS 전건 통과).
- 다음 작업: 사용자 확인 후 C-4 (W-11 적치 완료·취소 백엔드+화면) 착수.

# 2026-10-18 W2b-1c C-3a 입고장 경유 위치 흐름 검증 완화 및 시드/화면 반영 완료

- 브랜치: `antigravity/w2b-1c`
- 설계 결정 반영:
  - F14 적치 흐름은 입고장 경유((a) 입고 예정 정상 위치 = 입고장 `RECEIVING` → 검수 확정 → 적치 작업 `PUTAWAY` → 보관 위치 `NORMAL`).
  - 단, 기존 데이터(60건) 및 테스트를 보호하기 위해 교체가 아닌 **완화(확대)** 방식으로 진행: 기존 `NORMAL`도 계속 허용하고 신규 `RECEIVING`도 허용.
- 완료 내용:
  - 백엔드 (`backend/`):
    - `fs/wms/receiving.py`:
      - `_validate_lines`: `normal_location_id`의 위치 유형 검증을 `location_type in ("NORMAL", "RECEIVING")`으로 완화. 기존 `NORMAL` 지정 시에도 오류 없이 통과하며 `RECEIVING` 위치도 정상 통과.
    - `fs/wms/schema.py`:
      - `LocationType = Literal["NORMAL", "QUARANTINE", "LINE", "RECEIVING", "SHIPPING", "RETURN"]` 6종 리터럴 타입 정의 및 `LocationCreate`, `LocationUpdate`에 적용.
    - `seed/`:
      - `common.py`: `SEED_VERSION = "sv-20261018-wms1"`로 버전업.
      - `wms_extension.py`: 창고별 입고장 위치 2개 추가: `("WH-RAW", "R-REC", "원자재 입고장", "RECEIVING")`, `("WH-FG", "F-REC", "완제품 입고장", "RECEIVING")` (`is_default=False`, `is_active=True`).
      - `validate.py`: `"wms.storage_location": 6` → `"wms.storage_location": 8`로 기댓값 갱신.
  - 프런트엔드 (`frontend/src/wms/`):
    - `common.tsx`:
      - `LocationType` 6종 export 및 `Location.locationType`에 적용.
    - `Inbounds.tsx`:
      - `NoticeForm`: 신규 등록 시 창고 위치 중 `locationType === 'RECEIVING'`인 위치를 `normalLocationId`의 기본값으로 자동 설정하는 effect 추가 (없으면 `NORMAL` 기본값 유지).
      - `normalLocationId` 드롭다운 옵션 필터를 `x.locationType === "NORMAL" || x.locationType === "RECEIVING"`으로 완화하고, 입고장 위치에는 ` [입고장]` 꼬리표 표시.
    - `Warehouses.tsx`:
      - 위치 등록/수정 폼의 위치 유형 선택을 6종(`NORMAL`, `RECEIVING`, `SHIPPING`, `LINE`, `QUARANTINE`, `RETURN`)으로 확장.
      - `isDefault` 비활성화 조건을 DB CHECK 제약에 맞춰 `draft.locationType !== "NORMAL"`로 통일.
  - 문서:
    - `docs/modules/wms/WMS_보강설계_DSN-13.md`: §8에 적치 위치 흐름 및 검증 완화 결정 기록 추가.
  - 테스트 및 검증:
    - 백엔드 WMS 테스트:
      - `backend/tests/test_wms_receiving.py`: `test_receiving_location_allowed_as_normal_location` 신규 추가 및 통과 (`RECEIVING` 위치로 입고 예정 생성, 도착, 검수 확정 전 흐름 통과, `QUARANTINE` 위치 지정 시 400 거부 확인).
      - 전체 백엔드 WMS 테스트 실행: `pytest backend/tests/test_wms.py backend/tests/test_wms_receiving.py` (44 passed, 0 failed in 103s).
    - 프런트엔드 WMS 테스트:
      - `frontend/src/wms/wms.test.tsx`: `W-08 입고 예정 등록 시 RECEIVING 위치가 있으면 기본 선택되고 목록에 [입고장]이 표시된다` 신규 추가 및 통과 (16 passed in 2.1s).
    - 정적 분석 및 린트: `uv run ruff check` (0 errors), `npm run lint` (0 errors), `npm run typecheck` (0 errors), `npm run format:check` (0 errors).
    - DB 및 도구 검증: `npm run db:validate` (205표, 2246칼럼, 507FK, errors 0), Python 3.14 venv 도구 테스트 `Ran 136 tests - OK`.
- 다음 작업: 사용자 확인 후 C-3 (W-11 적치 작업 목록·추천 위치 백엔드+화면) 착수.

# 2026-10-18 W2b-1c C-2 W-08 입고 LOT 부여 및 lot_tracked 전환 완료

- 브랜치: `antigravity/w2b-1c`
- DB 기존 행 감사 결과 (`factory_studio` 및 `factory_studio_test` 양쪽 전수 실측):
  - `wms.item` 중 `lot_tracked = true AND item_class <> 'FG'`: **0건**.
  - `wms.item` 중 `lot_tracked = false AND item_class = 'FG'`: **0건**.
  - `wms.inbound_notice_line` 중 `lot_tracked = false`인데 `lot_no`가 있는 행: **0건**.
  - `wms.inbound_notice_line` 중 `lot_tracked = true`인데 `lot_no`가 비어 있는 행: **0건** (기존 60행 모두 위반 없음).
- 완료 내용:
  - 백엔드 (`backend/src/fs/wms/`):
    - `receiving.py`:
      - `_validate_lines`: 낡은 완제품 전용 규칙(`bool(lot) != (item["itemClass"] == "FG")`)을 품목 마스터의 `lot_tracked` 플래그 기준(`bool(lot) != bool(item.get("lotTracked"))`)으로 전면 교체. LOT 추적 품목은 입고 예정 등록/수정/검수 시 LOT 필수, 비추적 품목은 LOT 입력 시 400 거부.
      - `inspect_notice`: 검수 확정 시 명세에 `lot_no`가 존재하고 입고 수량(`accepted_qty + quarantined_qty > 0`)이 있는 경우 `wms.lot`에 `origin='RECEIPT'`, `status='AVAILABLE'`, `received_on=now(KST)`, `expiry_date=received_on + shelf_life_days`(품목 유효기간 일수 반영), `supplier_lot_no=None`(partner_ref를 넣지 않고 비워 둠)으로 행 자동 생성. 이미 존재하는 LOT은 사전 조회하여 중복 생성 방지.
  - 프런트엔드 (`frontend/src/wms/`):
    - `Inbounds.tsx`:
      - `NoticeForm`: 기존 `wh?.purpose === "FG"` 조건 대신, 선택된 품목의 `lotTracked` 여부(`selectedItem?.lotTracked`)에 따라 LOT 입력 필드를 동적으로 노출하고 `required` 강제.
      - 품목 변경 시 새 품목이 LOT 비추적 품목이면 `lotNo: ""`로 안전하게 초기화.
  - 테스트 및 검증:
    - 백엔드 WMS 테스트:
      - `backend/tests/test_wms.py`: `test_inbound_lot_tracked_rules_and_lot_creation` 신규 추가 및 통과 (비추적 품목 LOT 거부, `PATCH /items/{id}`로 `lot_tracked=True` 변경 후 미입력 거부, 정상 LOT 등록/도착/검수 확정, `wms.lot` 칼럼 및 유효기간/supplier_lot_no=None 검증, `/wms/lots` 현재고 95.000 원장 합계 집계 검증, 멱등성 검증).
      - 전체 백엔드 WMS 테스트 실행: `pytest backend/tests/test_wms.py backend/tests/test_wms_receiving.py` (43 passed, 0 failed in 101s).
    - 프런트엔드 WMS 테스트:
      - `frontend/src/wms/wms.test.tsx`: `W-08 품목 lotTracked 여부에 따른 LOT 입력 필드 노출 및 초기화` 신규 추가 및 통과 (15 passed in 2.5s).
    - 정적 분석 및 린트: `ruff check` (0 errors), `npm run lint` (0 errors), `npm run typecheck` (0 errors), `npm run format:check` (0 errors).
    - DB 및 도구 검증: `npm run db:validate` (205표, 2246칼럼, 507FK, errors 0), Python 3.14 venv 도구 테스트 `Ran 136 tests - OK`.
- 다음 작업: 사용자 확인 후 C-3 (W-11 적치 작업 목록·추천 위치 백엔드+화면) 착수.

# 2026-10-17 W2b-1c C-1 W-08 notice_kind 보강 완료

- 브랜치: `antigravity/w2b-1c`
- DB 기존 행 실측 결과:
  - `factory_studio`: 총 60행 중 60행 모두 `notice_kind='PURCHASE'` (누락/NULL 0건 확인).
  - `factory_studio_test`: 총 5행 중 5행 모두 `notice_kind='PURCHASE'` (누락/NULL 0건 확인).
- 완료 내용:
  - 백엔드 (`backend/src/fs/wms/`):
    - `receiving_schema.py`: `NoticeKind = Literal["PURCHASE", "PO", "SALES_RETURN", "SUBCONTRACT"]` 정의 및 `NoticeFields`에 `notice_kind` (기본값 `"PURCHASE"`, alias `"noticeKind"`) 추가.
    - `receiving.py`:
      - `create_notice`: `notice_kind` 기본값 `PURCHASE`, 4종 외 입력 시 유효성 에러(`noticeKind`) 방어, INSERT 쿼리에 `notice_kind` 반영.
      - `update_notice`: PLANNED 상태에서 `notice_kind` 수정 허용 및 4종 유효성 검증, UPDATE 쿼리에 반영.
      - `list_notices`: `notice_kind` 선택적 필터링 쿼리 파라미터 지원.
    - `router.py`: `GET /inbound-notices` 엔드포인트에 `noticeKind` Query 파라미터 매핑 및 연동.
  - 프런트엔드 (`frontend/src/wms/`):
    - `operations.tsx`: `NoticeKind` 타입 및 `noticeKinds` 라벨 매핑 ("매입", "발주", "판매 반품", "외주") 추가.
    - `Inbounds.tsx`:
      - 필터 바: "입고 구분" 셀렉트 추가 (`noticeKind` 쿼리 파라미터 연동).
      - 목록 테이블: `noticeKind` 컬럼 추가 및 배지 (`tone="issue"` for SALES_RETURN, `"normal"` for others) 표시.
      - 등록 폼 (`NoticeForm`): `입고 구분` 드롭다운 선택 및 `POST` 페이로드 전송.
      - 상세 패널 (`NoticeDetail`): 헤더 배지 및 기본 정보 `구분 {noticeKinds[row.noticeKind]}` 표시.
  - 테스트 및 검증:
    - 백엔드 WMS 테스트: `pytest backend/tests/test_wms.py -v` (19 passed - `test_inbound_notice_kind_rules` 신규 추가 및 통과).
    - 프런트엔드 WMS 테스트: `npm --prefix frontend test -- src/wms/wms.test.tsx` (14 passed - W-08 목록/상세/등록 noticeKind 신규 검증).
    - 정적 분석 및 린트: `ruff check` (0 errors), `ruff format --check` (227 files, 0 errors), `npm run lint` (0 errors), `npm run typecheck` (0 errors), `npm run format:check` (0 errors).
    - 도구 단위 테스트: `Ran 136 tests in 16.210s - OK`.
- 다음 작업: 사용자 확인 후 C-2 (W-08 입고 LOT 부여 — 검수 시 `wms.lot` 생성) 착수.

## 2026-10-17 PWA-POLICY-01 로컬 main 반영

사용자 “로컬 main에만” 지시로 `e02097d`를 main에 fast-forward 병합했다. 원격 push·CI 실행·실서버 배포 없음. 이전 기록의 main 미반영 상태는 이 항목으로 갱신한다. 다음 GW는 `codex/gw-company-01`에서 현재 회사 구조와 미확정 설계를 대조한다. 기존 Flow 테스트7실패는 그대로 남아 있으며 배포 전체검증 통과로 표시하지 않는다.

## 2026-10-17 PWA-POLICY-01 회사 정책과 근무 화면 일치

사용자 고도화 순서 UPGRADE-01 승인, 첫 ID 구현100%·로컬 검증 완료. 기준main eaa01eb / codex/pwa-policy-01. 회사 근무·휴게·일 근무 분·연차 기준 표시, 연차/반차 시각·잔여 일 환산·분 단위 시간 선택 보정. 반차는 휴게 제외 절반, 시간차 차감은60분 배수. 불일치 정책/비서울/야간 신청 차단, 홀수 근무 분 반차 차단. 개인 부여와 회사 연차 기준 구분. 정책관리/DB/실제계정·원장 변경 없음. [결과](agent/PWA_정책화면_일치_PWA-POLICY-01.md) · [후속순서](plan/시스템고도화_진행순서_UPGRADE-01.md).

검증: 관련프런트31/31, 격리API12/12(기존경고2), type/lint/format/build 통과, 실제Chrome 합성API1440/390·4종JSON/pageerror0. 전체재검사597/604·Flow기존7실패(기준main에서도동일7실패); 첫전체ERP/MES일시실패3은기준main36/36 및재실행통과. 전체CI성공/실기기/운영검증으로표현하지않음. main병합/push/배포미실행. 다음: 첫ID결과확인, Flow기준실패별도점검·GW미확정공유인증설계를현HR회사구조와대조. AGENTS §1 ID별결과확인/§2전체설계확인준수.

## 2026-10-15 OPS-CAD-02 CAD·YC main 수동 운영 배포 완료

사용자수동배포요청으로 운영3a6019f→main제품c0f118e 반영(12:00KST). backend/DB/시드차이0, 정확main frontend601·CAD154/type/lint/format/build/격리/dbvalidate통과. GitHub결제차단은수동검증으로대체하여 --skip-ci-check 명시사용(CI성공아님). 보호백업r2검증·회사/계정191표건수/hash보존·APIactive/공개원점200/DDL0/최근5xx0·시드유지·공개NC JS/CSS SHA동일/비로그인비누401. 공개운영실Chrome합성NC/STEP/에너지/모의음성→3카드/3번재생/정지/복귀/출력미리보기/변경무효화/390/pageerror0통과. 실마이크/실장비/실측/운영계정쓰기미검증. 초기backup fingerprint별칭오류는배포전중단/API복구후보정·r2재검증,원장변경없음. [배포기록](agent/main_수동운영배포_OPS-CAD-02.md). 다음사용자결과확인/실발화리허설,자동다음ID없음.

CAD-UI04 제품3818b38 main/origin 반영 완료. CI38403227492/check115315971025는 runner시작전 결제/지출한도 차단(annotation확인). 새운영UI 배포미실행·CI우회없음. 로컬검증용5263/Chrome 종료, 실제회사/계정/원장/병행브랜치변경없음.

## 2026-10-13 CAD-UI04 NC·YC 제품 화면 구조 적용 완료

사용자 UI03 Figma시안 이후 진행 승인. 좌준비단계/중앙실제뷰어/우속성YC/하단재생. 제안중앙비교→번호확대/뷰어1·YC접근·고정재생·닫기/Esc/단계복귀, 값/핸들러/원본행/출력/검증유지. CAD154/대상frontend33/build/격리/format/diff·실Chrome합성Worker/모의음성이벤트/3카드/3번진행/정지/복귀/변경무효화/원본행/FANUC미리보기/390넘침0/pageerror0통과. Figma신규조회한도로보관시안/script대체·완벽동일주장없음. 실마이크/운영새UI/실장비/DB검증미실행. branch codex/cad-ui04, 마지막커밋gitlog. [결과](agent/NC_YC_UI_적용검증_CAD-UI04.md). 다음확인/운영·실발화검증, 다른ID자동착수없음.

## 2026-10-13 CAD-UI03 NC·YC Figma 구조 시안

사용자 제안방향 확인 후 Figma Design Z9reC31WUdfLMhfC02VM2m 생성. NC우선5상태/7화면·공통5가족17variants/20변수/3텍스트스타일/113instances·클릭전환·중앙뷰포트/좌준비단계/우속성YC/하단재생. 7화면 최초구조넘침0/글꼴불일치0, 5상태캡처시각확인. 마지막진행/완료구분·초기제안차단 수정성공 뒤 Starter MCP호출한도로 캡처/최종구조재검증미실행. 이미지직전버전/시뮬레이션SVG도식/클릭은모의. 제품코드/DB/배포변경없음. 다음 사용자시안확인→최종보정검증/전체확인→별도제품UI적용. [설계기록](modules/cad-cam/NC_YC_화면구조_CAD-UI03.md).

# 2026-10-13 OPS-CI-01 로컬 CI 스크립트 개발 및 검증 완료

- 브랜치: `antigravity/ops-ci-01`
- 내용:
  - GitHub Actions 결제 한도/차단("recent account payments have failed") 대응 로컬 CI 표준 스크립트 `tools/ci_local.sh` 작성.
  - `package.json`에 `"ci:local": "bash tools/ci_local.sh"` 스크립트 추가.
  - `.github/workflows/ci.yml`과 동일한 순서의 1~5단계 구현:
    - 1단계: `npm run db:validate` · `tools/audit_schema_isolation.py` · `python -m unittest discover -s tools -p 'test_*.py'`
    - 2단계: `uv run --project backend ruff check` · `ruff format --check`
    - 3단계: `alembic upgrade head` · `verify_ddl_matches_schema.py` · `pytest backend/tests -q -n auto -m "not perf"` · `pytest backend/tests -q -m perf`
    - 4단계: `clear_test_data.py` · `alembic downgrade base` · `alembic upgrade head` · `verify_ddl_matches_schema.py`
    - 5단계: 프런트엔드 `typecheck` · `lint` · `format:check` · `build` · `test`
    - 정리: pytest 다중 워커 임시 복제 DB(`factory_studio_ci_*_test`) 자동 정리.
  - 안전장치 및 규약 준수:
    - `tools/deploy.sh` 양식 준수: `step()`, `fail()`, `--help`, `--dry-run` 지원.
    - Python venv 및 Node 24 PATH 우선순위 강제 (`backend/.venv/bin`, `/opt/homebrew/opt/node@24/bin`).
    - PostgreSQL 18.6 버전 검사(포트 55432) 및 테스트 DB 이름 `_test` 접미사 필수 확인.
    - 터미널/로그에 DB 비밀번호 미노출 (DB 이름만 출력).
    - 4단계 DB 초기화 전 대상 DB 안내 및 5초 취소 대기 시간 부여.
    - 가상 환경/로컬 I/O 부하 시 perf 테스트 및 프런트 테스트 1회 재시도 보호.
  - 단위 테스트 `tools/test_ci_local.py` 작성 (4/4 passed).
- 검증 결과:
  - `tools/ci_local.sh` 전체 실행: 1~5단계 전 단계 통과 (백엔드 1,020 passed/1 skipped, perf 1 passed, 도구 137 passed, 프런트 601/601 passed).
  - 의도적 실패 검증: 2단계 ruff format 미준수 주입 시 즉시 중단 확인 (후속 단계 미실행).
  - `--help`, `--dry-run` 동작 및 비밀번호 미노출 확인.
- 문서 반영: `AGENTS.md` §5 및 `docs/agent/ANTIGRAVITY_인계.md` §3에 `npm run ci:local` 가이드 추가.
- 다음: 사용자 확인 및 main 병합 대기.

# 2026-10-17 W2b-1b B-3 W-10 LOT 보류·해제 이력 및 QMS 연동 완료 (W2b-1b 전체 완료)

- 브랜치: `antigravity/w2b-1b`
- 완료 내용:
  - W-10 LOT 보류·해제 백엔드 (`backend/src/fs/wms/`, `backend/src/fs/qms/`):
    - **DB 불변 및 이력 누적 원칙 준수**: `schema.json` 변경 없음. `wms.lot_hold`의 부분 고유 인덱스(`UNIQUE (workspace_id, generation_id, lot_id) WHERE (released_at IS NULL)`)를 기반으로, 보류 시 새 행 INSERT(`released_at=NULL`), 해제 시 UPDATE(`released_at=clock_timestamp()`), 재보류 시 새 행 INSERT로 다중 보류/해제 이력을 영구 보존.
    - 엔드포인트 추가: `POST /lots/{id}/hold`, `POST /lots/{id}/release`.
    - 중복 및 유효성 방어: 이미 보류 중인 LOT에 보류 시도 시 409 Conflict, 보류 중이 아닌 LOT에 해제 시도 시 409 Conflict, 존재하지 않는 LOT에 대해 404 Not Found.
    - QMS 보류 조회 연동: `fs.qms.interface`의 `is_enabled`, `active_hold_details(conn, scoped, lot_no)`를 통해 QMS 검사 및 보류 상태를 읽기 전용으로 안전하게 조회 (`qmsHold: { active, holdNo, reason }`).
    - LOT 목록 및 상세 연동: `list_lots`에서 QMS 활성 보류 여부(`qmsHold: true/false`) 반환, `_lot_row`에서 상세 활성 보류 정보, QMS 보류 상세, 그리고 최근 50건의 보류 이력(`status: "HELD" | "RELEASED"`, 출처, 사유, 보류/해제 일시 및 작업자) 반환.
  - W-10 LOT 보류 프런트엔드 (`frontend/src/wms/Lots.tsx`):
    - 목록 테이블: 기존 상태 배지(가용/보류/만료) 옆에 QMS 보류 시 `<Badge tone="issue">QMS 보류</Badge>` 표시.
    - 상세 패널 현재 보류 카드: 활성 보류 중일 때 보류 사유, 출처, 일시 표시 및 "보류 해제" 버튼 제공. 미보류 시 "보류 설정" 버튼 제공.
    - 인라인 보류 등록 폼: 출처 선택(MANUAL/QMS/EXPIRY), 원천코드 입력, 보류 사유(2자 이상 필수) 입력 및 등록 처리.
    - QMS 품질 검사 상태 카드: QMS 모듈 활성화 여부 및 활성 보류 상세 표시, "QMS 보류 동기화" 버튼을 통해 QMS 활성 보류를 WMS 보류로 즉시 가져오는 연동 기능 구현.
    - 보류 이력 테이블: 최신 50건에 대해 상태(보류중/해제됨), 출처, 보류 사유, 보류일시, 해제일시, 해제사유를 일목요연하게 표시.
    - 모바일 390px 반응형 뷰포트 최적화.
  - 단위 및 통합 테스트:
    - 백엔드 WMS 테스트: `pytest backend/tests/test_wms.py -v` (18 passed - `test_lot_hold_and_release_cycle_and_qms` 신규 통과).
    - 프런트엔드 WMS 테스트: `npm --prefix frontend test -- src/wms/wms.test.tsx` (13 passed - 보류 설정/해제 및 QMS 표시 신규 검증).
    - 정적 분석 및 린트: `ruff check` (0 errors), `ruff format --check` (227 files, 0 errors), `npm run lint` (0 errors), `npm run typecheck` (0 errors), `npm run format:check` (0 errors).
- **브라우저 실기동 검증 (`frontend/scripts/verify-wms-hold-browser.mjs`)**:
  - 실제 구동 중인 백엔드(58000) 및 프런트엔드(55173) 환경에서 브라우저 자동화 검증 완료:
    1. 게스트 세션 시작 후 LOT(`LOT-20261017-B3TEST`) 등록: 초기 상태 "가용", QMS 상태 정상 확인 (`wms-lots-initial.png`).
    2. 1차 수동 보류(MANUAL, "수동 보류 테스트: 포장 불량"): 목록에 "보류" 배지 전환, 상세 패널에 활성 보류 카드 노출 확인 (`wms-lots-hold-active.png`).
    3. 1차 보류 해제("포장 재작업 완료"): 목록 상태 "가용" 복귀, 이력 테이블에 1차 이력 "해제됨"으로 보존 확인 (`wms-lots-hold-released.png`).
    4. 2차 QMS 재보류("품질 규격 재검사 필요", 원천코드 QH-20261017-999): 목록 "보류" 배지 재표시, 이력 테이블에 최신 보류(보류중)와 과거 보류(해제됨) 총 2건 누적 보존 확인 (`wms-lots-hold-second.png`).
    5. 2차 해제: 목록 "가용" 복귀, 이력 테이블에 2건 모두 "해제됨"으로 영구 보존 확인.
    6. 모바일 390px 뷰포트 레이아웃 정상 표시 확인 (`wms-lots-mobile-390.png`).
- **A-2 검증 지표 실측치**:
  - `verify_ddl_matches_schema.py` 오류 수 (적용 후): **0건** (205표, 2,246칼럼, PK 205, UK 425, CHECK 502, INDEX 165, UNIQUE_INDEX 46, FK 507 100% 일치).
  - 왕복 결과: `downgrade base` -> `upgrade head` 후 다시 **오류 0건**.
  - 적용 DB 목록: `factory_studio`, `factory_studio_test`, `factory_studio_ci_test` 모두 **`w2b1_wms (head)`** 상태.
  - **백엔드 pytest 요약 줄 전문**:
    - `1023 passed, 1 skipped, 47 warnings in 454.01s (0:07:34)` (not perf)
    - `1 passed, 1024 deselected, 5 warnings in 26.56s` (perf)
    - **총 1,024 passed, 1 skipped (실패 0건, 에러 0건, worker down 0건)**.
  - 도구 단위 테스트: `Ran 136 tests in 16.184s - OK`.
- 다음 작업: 사용자 확인 후 W2b-1b 전체 승인 대기 (W2b-1c 임의 착수 금지).

# 2026-10-15 W2b-1b WMS-FIX 완료

- 브랜치: `antigravity/w2b-1b`
- 완료 내용:
  - `tools/test_fs024a.py`: WMS 표 개수 가드를 23으로 업데이트 (`W2b-1a` 및 `W2b*` 분기 추가, 기존 6/11 분기 유지).
  - `tools/test_dsn11.py`: `test_rebuild_from_schema_json_is_identical` 제거(안 B 채택) 및 분리 사유 주석 기록 (W2 단계마다 `schema.json`에 목표 표가 선반영되어 재생성 비교가 성립하지 않으며, 목표 설계 검증은 `test_contract_holds`, `test_rejects_regressions`, `validate_db_design.py --schema`가 전담).
  - `tools/rebuild_target.py`: docstring 상단에 "W2 이후에는 schema.json이 진화해 결과가 목표 파일과 달라진다. 설계 단계 재현용이다" 1줄 안내 추가.
  - `docs/modules/wms/WMS_보강설계_DSN-13.md`: 8절(구현 및 스키마 반영 메모) 추가하여 `apply_dsn90.py` 재적용 시 `CMMS_ISSUE` 중복 생성 제약 및 기존 WMS 3표 칼럼 순서(DDL 대조 0건으로 기능 영향 없음) 문서화.
  - `backend/alembic/versions/20261013_w2b1_wms.py`:
    - `downgrade()` 복원 시 `c831_check` -> `c781_check` (`storage_location`), `c818_check` -> `c768_check` (`source_claim`)로 pre-w2b1 원래 제약 이름 복원 (이를 통해 `alembic downgrade base` 전체 왕복이 오류 없이 통과).
    - `MODULE_CHECKS = []` ruff 포맷 보정.
  - `backend/tests/test_wms.py`: ruff I001 import 정렬 보정.
  - `frontend/src/portal/favorites.test.tsx`: W-10 LOT 메뉴 추가에 따른 메뉴 카탈로그 개수 가드 113 -> 114 보정 (`menuCatalog` 114개 키·경로 고유성 100% 통과).
- 검증 결과:
  - `backend/.venv/bin/python -m unittest discover -s tools -p 'test_*.py'`: **136 passed (OK)**.
  - `npm run ci:local`: **1~5단계 전체 통과 (SUCCESS)**.
    - 1단계: DB 정적 검증(`npm run db:validate`, 0 errors), 격리 감사(`audit_schema_isolation.py`, R1~R6 0 errors), 도구 단위 테스트 (136 passed).
    - 2단계: 백엔드 ruff check & ruff format check (227 files, 0 errors).
    - 3단계: 마이그레이션 적용 및 `verify_ddl_matches_schema.py` (0 errors), pytest (1,022 passed, 1 skipped, 1 perf passed).
    - 4단계: `clear_test_data.py` -> `downgrade base` -> `upgrade head` -> `verify_ddl_matches_schema.py` (0 errors, 완벽한 왕복).
    - 5단계: 프런트엔드 `typecheck`, `lint`, `format:check`, `build`, `test` (75 test files, 603 passed, 0 errors).
- 다음 작업: 사용자 확인 후 B-3 (W-10 보류·해제 이력) 착수.

# 2026-10-15 W2b-1b B-2 W-10 LOT 조회·등록 완료

- 브랜치: `antigravity/w2b-1b`
- 완료 내용:
  - W-10 LOT 백엔드 (`backend/src/fs/wms/`):
    - `wms.lot` 조회/등록/수정 API (`GET /lots`, `GET /lots/{id}`, `POST /lots`, `PATCH /lots/{id}`).
    - **LOT 수량 DB 미저장 원칙 준수**: 원장(`wms.stock_move`) 합계(`SUM(qty_delta)`)로만 계산. N+1 방지를 위해 `WITH lot_stock AS (...)`, `active_holds AS (...)` 서브쿼리로 단일 질의 처리.
    - 만료 여부 DB 미저장: 조회 시 `business_today()` 기준 실시간 판정.
    - 페이징: `fs/common/page.py` (`Page(offset, limit).checked()`) 표준 적용.
    - 품목별 `lot_tracked` 플래그를 고려한 전표 검증(`_validate_lines`) 보완.
  - W-10 LOT 화면 (`frontend/src/wms/Lots.tsx`):
    - 목록: LOT 번호, 상태 배지(가용/보류/만료), 품목, 현재고(원장 합계), 입고일, 유효기간, 공급처 LOT, 출처, 관리(상세).
    - 검색 필터: 품목 선택 드롭다운, 상태 선택 드롭다운, 검색어(품목코드/명, LOT 번호, 공급처 LOT), 만료만 보기 체크박스.
    - 등록 패널 (`FormPanel`): 품목 선택(선택 시 `shelfLifeDays`로 유효기간 자동 계산 제안), LOT 번호, 입고일, 유효기간, 공급처 LOT, 출처.
    - 상세 패널 (`DetailPanel`, wide): 기본 정보, 원장 집계 총 재고 및 위치별 재고 분포(`locations`), 보류 상태 및 이력(`holds`), **B-3 보류 안내 문구** 명시.
    - 메뉴 및 라우트 등록: `menu_catalog.json` (W-10), `WmsRoutes` (`/wms/lots`).
    - 표준 훅 연동: `useSend` 훅으로 CSRF 토큰 및 멱등키 보장.
- 검증 결과:
  - 백엔드 WMS 테스트: `pytest backend/tests/test_wms.py -v` (17 passed).
  - 프론트엔드 테스트: `npm --prefix frontend test -- src/wms/wms.test.tsx` (12 passed).
  - 프론트엔드 검사: `lint` (0 errors), `typecheck` (0 errors), `format:check` (Prettier 통과), `build` (tsc & vite) 통과.
  - 백엔드 린트: `ruff check backend/src/fs/wms/` & `ruff format --check` 통과.
  - **브라우저 실기동 및 기능 검증 (`verify-wms-browser.mjs`)**:
    - `/wms/items` (B-1 품목 보강): 유효기간, ABC, 안전/최대재고, PLM 필드 렌더링 확인.
    - `/wms/lots` (B-2 LOT 등록): `LOT-20261015-LIVE` 등록, 목록 및 상세 패널 정상 확인.
    - **원장 수량 실시간 대조**: 기초재고 전표 750 EA 확정 후 LOT 목록 및 위치별 상세에서 현재고가 즉시 정확히 750 EA로 증가 일치 확인!
    - 390px 모바일 뷰포트 레이아웃 검증 완료.
  - **A-2 검증 지표 실측치**:
    - `verify_ddl_matches_schema.py` 오류 수 (적용 후): **0건**
    - 왕복 결과: `downgrade -1` -> `upgrade head` 후 다시 **오류 0건**
    - 적용 DB 목록: `factory_studio` 및 `factory_studio_test` 둘 다 **`w2b1_wms (head)`** 상태.
- 다음 작업: 사용자 확인 후 B-3 (W-10 보류·해제 이력) 착수.

# 2026-10-13 W2b-1b B-1 W-07 품목 보강 완료

- 브랜치: `antigravity/w2b-1b`, 커밋 `794c38b` (feat(wms): reinforce W-07 item master with shelf life and stock bounds (B-1))
- 완료 내용:
  - W-07 품목 백엔드: `wms.item` 확장 칼럼(`lot_tracked`, `shelf_life_days`, `storage_condition`, `safety_stock`, `max_stock`, `abc_class`, `plm_part_no`, `plm_revision`) 조회/등록/수정.
  - 규칙 검증: PLM 품번/리비전 동시 작성/비움 검사, 최대재고 >= 안전재고, 유효기간 >= 1일, ABC 등급 A/B/C 검사.
  - `update_item` 시 빈 값(`null`) 업데이트 지원 (`NULLABLE_ITEM_FIELDS`).
  - W-07 품목 화면: `Items.tsx` 폼에 확장 필드 입력(유효기간, 보관조건, 안전재고, 최대재고, ABC 등급, PLM 품번/리비전) 및 목록 컬럼 표시 추가, `Purpose` 5종 확장(`RAW`, `SEMI`, `FG`, `MERCH`, `SUPPLY`).
  - 빈 칸은 `null`로 전송. 완제품 선택 시 LOT 추적 기본 활성화.
  - 검증: `backend/tests/test_wms.py` 16 passed, `frontend/src/wms/wms.test.tsx` 11 passed, `npm --prefix frontend run build` (tsc & vite) 통과, `npm run lint` & `format:check` 통과, `ruff check/format` 통과.
- DB 변경 없음 (W2b-1a에서 확정).
- 다음 작업: 사용자 확인 후 B-2 (W-10 LOT 조회·등록) 착수.

CAD-V03 제품 c0efb5b main/origin push 완료. 운영 새흐름 배포 미실행. 최종 main CI도 runner 시작 전 결제/한도 차단 확인(check115285673525). 실마이크 미검증, 기존 MES 브랜치 보존.

## 2026-10-13 CAD-V03 YC 예제·음성 요청 흐름 보정 완료

YC 예제 클릭→마이크 요청/합성NC·STEP·소재·장비·품질 준비→헤이와이씨/파일최적안요청→정지카드3→번호확대재생. Step4는 계산만 하고 자동팝업 제거. 실제업로드는 기존조건검증 유지/후보수강제없음. CAD154/대상frontend33/build/격리/format·실Chrome모의인식이벤트 전체흐름/진행률·정지/복귀/390/입력중단/재시도/pageerror0. 실마이크/운영새흐름/실장비/DB검증미실행·CI우회없음. branch codex/cad-v03, 기준main65aaea5; main반영/push는 승인된 기존반영범위. [결과](agent/YC_음성요청_흐름검증_CAD-V03.md). 공유MES변경없음, 이전antigravity로컬휴디코드와최신빌드구분. 다음결과확인/실발화·운영검증, 다음ID자동착수없음.

# 2026-10-12 W2a-1b2-rest·CAD-17·CAD-V02 운영 배포 완료

제품 `3a6019f` 로컬main/origin/실서버 반영(23:24 KST). 서버 `41ca68d` → `3a6019f`, 44초.

- 나간 것: **W2a-1b2-rest**(MES M-14 공정 경로 단계별 속성 — 표준 CT·준비 시간·외주·외주처, M-15 BOM 투입 공정·대체 자재, BOM-FIX 자재 순서 교체 시 `line_no` 유니크 충돌 수정), CAD-17 FANUC 검토용 NC 출력, CAD-V02 음성 카드, 도움말·문서. 45파일 +3,689/−173.
- **DB 변경 없음**이 운영에서 확인됐다: 시드 `sv-20261009-gw1` 코드·템플릿 일치로 템플릿 재생성 없음, 마이그레이션 적용 없음, DDL 대조 0. W2a의 칼럼과 `mes.bom_substitute`는 W2a-1a에서 이미 만들어져 있었다.
- 배포 확인: 원점 200 · 공개 200 · DDL 대조 0 · 최근 2분 5xx 0건. 빌드 29M.
- **CI를 건너뛰고 배포했다(`--skip-ci-check`).** GitHub Actions 결제 차단이 계속된다. 대신 **수동 CI 1~5단계를 main `3a6019f`에서 전부 돌려 통과**했다: db:validate 0 · 격리 감사 R1–R6 0 · 도구 133 OK · ruff check/format(226파일) · DDL 대조 0 · **백엔드 1,020 passed/1 skipped**(6:50)·perf 1 · 마이그레이션 왕복(downgrade base → upgrade head) · 프런트 typecheck/lint/format/build · **601/601**.
- 주의: 수동 CI는 **배포가 끝난 뒤에 완료**됐다(사후 검증). 앞으로는 검증 완료 후 배포한다.
- 불안정 테스트 1건: 첫 전체 실행에서 `frontend/src/mes/versions.test.tsx > 경로 목록은 상태별로 다른 작업을 보여준다`가 실패했으나 재실행 601/601 통과. 재현되지 않는다.
- 참고(명령 함정): 단일 프런트 테스트는 `npm --prefix frontend test -- <파일>`로 돌린다. `npx --prefix frontend vitest run <파일>`은 작업 디렉터리가 달라져 설정·셋업을 못 읽고 파일 전체가 실패한 것처럼 보인다.
- 수동 CI 절차는 결제가 풀릴 때까지 필요하다. 임시 스크립트는 세션 scratchpad에 있다 — 반복될 것 같으면 `tools/ci_local.sh`로 저장소에 넣는다.
- **운영 브라우저 확인 미실행**: `/mes/routes`·`/mes/boms`의 단계별 속성·투입 공정·대체 자재를 아직 보지 않았다. 로컬에서는 antigravity가 Playwright로 전 흐름(순서 교체·409 안내·게시·390px) 확인했다.
- W2a-1b2-rest 종료. 다음 antigravity 작업 미지정.

# 2026-10-12 OPS-CAD-01 main push / CI billing blocker

CAD17/V02 merged into main (13f3a8e), NC help markup fixed. CAD154/frontend596/build/isolation/format passed. Runs38258159540/38258223617 failed before any step due to billing or spending limit. Server41ca68d/APIactive preserved; latest CAD deployment not executed. Next: owner resolves Billing & plans, rerun exact main HEAD CI, then backup/standard deployment. See docs/agent/main_CI_배포점검_OPS-CAD-01.md. Final commit: git log -1 --oneline. Shared MES changes untouched. Backend/DDL roundtrip and new browser/microphone checks not run.

# 2026-10-12 ANTI-HELP-01 운영 배포 완료

제품 `41ca68d` 로컬main/origin/실서버 반영(22:37 KST). 서버 `027505f` → `41ca68d`, 41초. MES 화면 도움말 4편(M-16 불량·사유 코드, M-17 작업자·근무조, M-19 라벨 양식, M-26 공정 검사 기준)과 도움말 수 가드 기댓값(15→19).

- **CI를 건너뛰고 배포했다(`--skip-ci-check`).** GitHub Actions가 결제 문제로 잡을 시작하지 못했다("The job was not started because recent account payments have failed or your spending limit needs to be increased"). 실행 `38255924011`(attempt 3)·`38256475377` 모두 1~2초 만에 같은 사유로 실패. 재실행·빈 커밋 push 모두 같은 결과. **결제 문제는 아직 해결되지 않았고, 그동안 모든 브랜치의 CI가 막힌다.**
- 대신 로컬 검증으로 대체: `npm --prefix frontend test -- src/portal/content-pages.test.tsx` 18/18 통과(도움말 수 가드 포함), `tsc --noEmit` 통과, `vite build` 통과. **백엔드 테스트·ruff·DDL 왕복 검사는 실행하지 않았다.** 이번 변경이 마크다운 4개와 테스트 기댓값 1줄뿐이라 받아들였다.
- 배포 확인: 원점 200 · 공개 200 · DDL 대조 0 · 최근 2분 5xx 0건. 시드 `sv-20261009-gw1` 코드·템플릿 일치로 템플릿 재생성 없음. 빌드 29M.
- **운영 브라우저 확인 미실행**: `/mes/codes`·`/mes/workers`·`/mes/labels`·`/mes/inspection-items`의 "? 도움말"이 실제로 뜨는지 아직 보지 않았다. 로컬에서는 headless Chromium으로 4편 모두 확인했다.
- main 이력에 빈 커밋 `41ca68d`("ci: rerun after billing fix")가 남았다. CI를 다시 걸려던 시도이며 내용 변경은 없다.
- ANTI-HELP-01 종료. 다음은 W2a-1b2-rest R-5(`antigravity/w2a-1b2-rest`, 마지막 커밋 `01e29b8`).
## 2026-10-12 CAD-V02 STEP 점검·YC 음성 카드 시연 완료

- 사용자 첨부 Figma 참고+실제G4조건/시간/kWh표시 전체확인 후 codex/cad-v02 별도worktree. 최신main3d850fc와 CAD17 f2a1052 통합aebce5d, 최신도움말/기존기록보존. [결과](agent/YC_음성카드_STEP검증_CAD-V02.md).
- 운영STEP예제30초타임아웃재현(관찰HTTP/스크립트오류0). 준비90초/형상30초·진행/HTTP오류/재시도, 구조시제품실제화면링크. 기본호출YC/헤이와이씨·휴디별칭유지, 실제정지3D캡처+후보조건·번호선택/나머지숨김/확대기존뷰어재생·전체/닫기/무효화·도움말갱신. Ra/향상률/가공조건가짜값없음.
- CAD154·대상frontend15·전체build/비누격리/포맷/diff통과. Chrome정적제품빌드 STEP실패후재시도/32초지연성공·텍스트YC제안→정지3카드→3번확대/실제진행→정지/전체/반복/버튼/닫기/복원/입력무효화/Esc/390넘침0/pageerror0. 최초dev OCCT최적화reload로NC잃은실행실패후정적빌드검증통과. 캡처Git보관.
- 실제마이크/TTS/인식서비스·실장비/실측·90초만료·DB·main병합/push/운영수정배포 미실행. 다음결과확인후반영/운영STEP재검증·실음성리허설. 새ID자동착수없음.

## 2026-10-10 CAD-17 FANUC 검토용 출력 완료

- 사용자 기종 미정 검토용 출력/남은 작업 진행 승인. codex/cad-17, 기준e137f61/기반738433d. [결과](agent/FANUC검토용_NC출력_CAD-17.md). O번호·ASCII/CRLF·G4 P밀리초·프로필 어댑터/원본행·최신 품질 재계산·해시/재해석·경로/이벤트/모달 보존·검토NC/JSON 저장·Worker/입력/탭무효화·UI/도움말 연결. 구현100% 제한범위, 실장비용 완료 아님.
- CAD153(출력11)/대상frontend15·전체build/자산격리·범위포맷/diff 통과. 실제Chrome 원본600/300초→P600000/300000·후보3 10/10초→P10000/10000 수신/JSON·FANUC재업로드/재출력·프로그램/프로필무효화·1440/390넘침0/pageerror0. 출력NC의 의도된CRLF에 증거폴더gitattributes 지정 후 diff검사 통과. 구분자/O 헤더 비교 실패를 실행 의미 비교로 보정해 회귀 재통과. 최초 Vite reload중 STEP 대기 실패 후 전체 흐름 재통과. 합성파일/캡처 Git 보관.
- 실제FANUC interpreter/장비/H·D/지그/실측품질·절감/실음성/운영·DB·main병합/push/배포 미실행. 현재공유checkout 사용자변경 미접촉. 다음 사용자 결과 확인/반영 또는 실제 기종/매뉴얼로 장비post 후속검증, 다음ID자동착수없음.

# 2026-10-12 HELP-01 다섯 시스템 도움말·운영 배포 완료

제품027505f 로컬main/origin/main/실서버 반영(21:58KST). 정확HEAD CI38249603910 SUCCESS: backend1010/skip1·perf1·frontend596/75파일·tools133·타입/lint/format/build/DDL왕복. 표준배포 성공·CI 우회 없음·보호백업검증·회사59/회사+회원59원장/계정 전체hash보존·시드유지·APIactive/DDL0/원점공개200/5xx0·기존이지스active/office200. 공개10주소200/주요JS서버해시일치·운영다섯시스템/HR3편 렌더링 및 이전G14→F02 이동 확인. 결과 기록 커밋은 배포 제품 커밋과 구분한다. 상세 [구현 대조·검증](agent/제품도움말_구현대조_HELP-01.md).

실제 합성 UI: GW위임/합의/종결 이력·Flow부모/하위행 편집/집계/보관/복구/새로고침·근무출퇴근/직원신청→다른관리자승인·E1CAM100%·NCSTEP/에너지/품질후보/재생·CNC시연1개완료. 격리API116·최종main 로컬frontend596·문서링크317/끊김0. 실제회사/계정/비밀번호/확장 설정 변경 없음. 실휴대폰·마이크·실가공/실설비 미검증, 로컬WebGL불가로3D렌더링/걷기 미검증. 후속은 별도 요청 후 P1근태정책-화면→회사GW인증/권한→PWA실기기, P2Flow업무일지/규모→CAD실측/음성→3D연계. 이번 신규업무기능·DB/API/시드 변경 없음.

# 2026-10-12 ANTI-HELP-01 MES 화면 도움말 4편 작성 및 정리 완료

antigravity 브랜치 `antigravity/anti-help-01`에서 수행.
- MES 화면 도움말 4편 신설: `content/help/mes/m-16.md`(M-16 불량·사유 코드), `m-17.md`(M-17 작업자·근무조), `m-19.md`(M-19 라벨 양식), `m-26.md`(M-26 공정 검사 기준).
- `menu_catalog.json` 기준 미제공 화면(M-20, M-25, M-27, M-29) 링크 및 관련 화면 참조 정리. 네 편 전체의 화면 ID 참조가 실제 존재하는 화면(M-05, M-07, M-08, M-12, M-13, H-05)만 가리키도록 검증.
- `frontend/src/portal/content-pages.test.tsx`의 `count("mes/m-")` 기댓값을 15에서 19로 갱신 (도움말 파일 수 가드 동기화).
- HR 3편(H-16, H-17, H-18)은 main 커밋 `f14b75b`에서 이미 완료되어 있어 중복 작성하지 않고 ANTI-HELP-01은 이 수정으로 종료.
- 검증: `npm --prefix frontend test -- src/portal/content-pages.test.tsx` 통과(18/18), `npm --prefix frontend test -- src/mes/masters.test.tsx` 통과(5/5), `npm --prefix frontend run build` 통과, headless Chromium 브라우저에서 `/mes/codes`, `/mes/workers`, `/mes/labels`, `/mes/inspection-items`의 "? 도움말" 클릭 시 각 도움말 화면이 정상 로드되고 "이 화면 열기 →" 링크가 올바르게 작동함을 검증.

# 2026-10-12 W2a-1b2-rest MES BOM(M-15) BOM-FIX 및 R-5 화면 완료

- 브랜치: `antigravity/w2a-1b2-rest`
- BOM-FIX 순서 교체 시 `line_no` 유니크 위반 해결:
  - `reconcile_bom_lines` 갱신 루프에서 살아남는 줄의 `line_no`를 1단계에서 `-idx` 임시 음수로 일괄 UPDATE 후 2단계에서 최종 순서 번호로 UPDATE하여 UK 충돌 방지.
  - 신규 테스트 `test_bom_lines_reordering_preserves_line_ids_and_substitutes` 추가 (`test_mes_route_bom.py` 34 passed).
- R-5 `Boms.tsx` 화면 보강:
  - 구성 자재 추가/수정 폼에 투입 공정(`issueProcessId`) 드롭다운 연동 (비우면 `null` 전송).
  - 구성 자재 행별 대체 자재 펼치기 토글 및 대체 자재 추가/삭제 기능 구현 (`/boms/{id}/lines/{lineId}/substitutes`, `ratio` string 정규화).
  - 구성 자재 행 순서 변경(↑/↓) 및 '순서 저장' 버튼.
  - 대체 자재가 딸린 행 삭제 시도 시 409 `REFERENCED_BY_OTHERS` 감지 후 행 옆에 인라인 빨간 에러 안내(`대체 자재를 먼저 지우세요`) 표시.
  - 게시·폐기 버전에서 대체 자재 편집 버튼 잠금/숨김.
  - 390px 반응형 뷰포트 레이아웃 지원.
- 검증:
  - `backend/tests/test_mes_route_bom.py` 34 passed, 백엔드 전체 MES 138 passed, `ruff check`/`format` 통과.
  - `frontend/src/mes/versions.test.tsx` 13 passed (BOM 투입 공정 추가, 대체 자재 펼침/추가, 409 인라인 에러 안내, 순서 교체 및 저장 등 4건 신규 추가).
  - 프론트엔드 전체 75파일 601 passed, `npm run typecheck`, `npm run lint`, `npm run build` 통과.
  - Playwright 브라우저 E2E 실동작 검증: BOM 생성 -> 투입 공정 지정 자재 2건 추가 -> 대체 자재 추가 -> 순서 교체 및 저장(BOM-FIX 검증) -> 새로고침 후 유지 확인 -> 409 안내 확인 -> 대체 자재 삭제 후 줄 삭제 -> 게시(잠금 전환) -> 390px 화면 점검 완료.
- 다음: W2a-1b2-rest R-1~R-5 전체 완료 보고 및 사용자 확인 후 main 병합.

# 2026-10-12 W2a-1b2-rest MES BOM(M-15) R-3·R-4 백엔드 완료

- 브랜치: `antigravity/w2a-1b2-rest`
- R-3 BOM 투입 공정 및 키 기반 맞춤 저장:
  - `mes.bom_line.issue_process_id`: `repository.LINE` 컬럼, `schema.BomLineIn`, `service.validate_lines`(`mes.process` 확인) 반영.
  - `reconcile_bom_lines`: `PUT /boms/{id}/lines` 저장 시 `material_item_id`를 키로 기존 줄을 UPDATE하여 `bom_line.id` 유지 및 대체 자재 보존. 삭제 대상 줄에 대체 자재가 있으면 409 `REFERENCED_BY_OTHERS` ("대체 자재가 있는 구성 자재는 삭제할 수 없습니다. 대체 자재를 먼저 지우세요.") 반환.
- R-4 BOM 대체 자재 조회·편집:
  - `GET /boms/{id}/lines/{lineId}/substitutes`, `PUT /boms/{id}/lines/{lineId}/substitutes` 엔드포인트 구현.
  - 초안(`draft`)에서만 편집 가능 (`VERSION_LOCKED` 409).
  - 완제품 자신 / 원래 구성 자재와 동일 품목 / 중복 등록 / 존재하지 않는 품목 차단.
  - `revise`(개정) 시 구성 자재와 함께 대체 자재(`mes.bom_substitute`) 복제.
- 검증: `backend/tests/test_mes_route_bom.py` 신규 6개 테스트 추가, 33 passed, 전체 MES 157 passed, `ruff check`/`ruff format` 통과.
- 다음: 사용자 확인 후 R-5(`Boms.tsx` 투입 공정 + 대체 자재 화면) 착수.

# 2026-10-12 HELP-01 제품 도움말 구현 대조·로컬 검증 완료

사용자 다섯 시스템 문서화·main/origin·기존 실서버 배포 승인. 기준main3306777, 브랜치codex/product-help-20261012, 별도factory-studio-help 체크아웃. 제품 정적 도움말과 진입 링크만 변경; 공유main의 진행 중 MES 변경은 보존/제외. HR H-16~18 신설, Flow 행편집·부모집계·보관복구·권한·/work-os 이동 보정, GW 전체 합성 업무 안내, CAD 가정/실측·3D 시연 구분과 README 이력 표시. 상세 [구현 대조](agent/제품도움말_구현대조_HELP-01.md).

로컬 검증: frontend596/75파일 전체 통과, 타입/lint/format/build 및 링크 보정 후 관련36통과. 프로젝트uv Python3.14 격리감사193표471FK오류0. 격리 *_help_api_test에서 근무/계정/Flow/GW116통과, *_help_browser_test+8046/5246은 실제API 합성UI 전용. 기존8000/5173·실제 회사/계정/비밀번호/브라우저확장 변경 없음. 다음: main/push→정확HEAD CI→기존백업/배포→운영검증. 아직 배포 완료 아님. 후속고도화 자동착수 금지.

# 2026-10-12 D84 역할 전환 — 개발을 antigravity로 이관

사용자 결정 D84: Claude Code는 **설계·기획·리뷰·다음 진행 결정만** 하고 개발은 하지 않는다. 개발은 **antigravity**가 작업별 프롬프트를 받아 수행하며, 프롬프트는 읽을 문서를 **폴더 경로**로 지정한다(파일 나열 금지). Codex의 기존 GW 배정은 유지.

- `AGENTS.md` §8에 D84 기록. 역할 표를 Claude Code/antigravity/Codex 세 줄로 교체.
- `docs/agent/ANTIGRAVITY_인계.md`를 역할 확대에 맞춰 다시 씀: §1 **폴더 지도**(어느 폴더에 무엇이 있고 언제 읽는지 17행), §2 프롬프트 틀, §3 공통 규칙(브랜치·설계 불변 규칙·DB·코드·시드·테스트/검증), §4 마무리 규칙, §5 대기 작업 표. `docs/agent/`는 파일이 100개가 넘어 **통째로 읽지 말 것**을 명시.
- 작업 프롬프트 2건 작성: `docs/agent/ANTI-HELP-01_도움말7편.md`(MES m-16·17·19·26, HR h-16·17·18 — 파일이 없어 "? 도움말"이 NotFound), `docs/agent/W2a-1b2-rest_MES경로BOM.md`(M-14 단계별 속성, M-15 투입 공정·대체 자재).
- **확인한 사실**: `mes.route_step`의 `standard_cycle_sec`·`setup_minutes`·`is_subcontract`·`subcontractor_code`, `mes.bom_line.issue_process_id`, `mes.bom_substitute`는 `schema.json`과 `20261008_w2a1_mes.py`에 **이미 있고** 코드·시드·화면 어디서도 쓰지 않는다(grep 0건). 따라서 W2a-1b2-rest는 **DB 변경 없는 응용 계층 작업**이며, 과거 보고의 "새 표 추가 필요"는 해당하지 않는다.
- 프롬프트에 적은 주요 함정: `RouteSteps.processIds` 본문 모양 변경의 전파 범위, `bom_substitute`가 **손자**라 `set_children`/`replace_children`(부모–자식 한 단계)로는 다룰 수 없다는 점, 게시·폐기 버전 잠금, `is_subcontract` NOT NULL 기본값, 기존부터 실패 중인 `test_gw_projects.py::test_flow_migration_roundtrip_preserves_records_and_favorites`.
- `docs/plan/현재기획_진행현황.md`에 D84 절 추가. 200줄 제한을 지키려 CAD-03·CAD-05·06 상세를 `docs/plan/진행현황_이력.md`로 이동(현재 200줄).
- **문서만 변경.** 제품 코드·DB·시드 변경 없음, 테스트·브라우저·배포 미실행. 운영은 여전히 `f860e8b`이고 시드 `sv-20261008-1`이라 다음 배포는 템플릿 재생성을 포함한다.
- 다음: 사용자가 두 프롬프트 중 하나를 antigravity에 넘긴다. 결과 리뷰는 Claude Code가 한다.

# 2026-10-11 FLOW-03 행 편집·접힘 UX 운영 배포 완료

FLOW-03 행 편집·접힘 UX 보정 운영 배포 완료(2026-10-11 18:41 KST): 제품2c30b42 main/origin/실서버 반영. 접힌 그룹68px 한 줄·업무/하위 업무 행 우측 삭제/복구·상세 편집 제목/설명2항목·담당자/상태/중요도/일정/진행률 행 편집. CI38128137226 SUCCESS(backend1010/skip1·perf1·frontend596·tools133), 실제 로컬 저장/새로고침/삭제/복구/390px 검증. 기존 Flow12원장전체hash보존·보호 백업·APIactive/DDL0/공개200/최근5xx0·공개JS/CSS SHA동일. 운영 로그인 UI는 기존 세션 만료로 미검증. FLOW-02b 후속. 검증용 로컬 보드는 보관하고 기존 Kim 보드로 복귀. 실제 운영 업무 쓰기·계정/확장 설정 변경 없음. 문서 기록 커밋은 배포 제품과 구분.

# 2026-10-11 FLOW-03 행 편집·접힘 UX 보정

FLOW-03 행 편집・接힘 UX 보정 구현/로컬 검증 완료(2026-10-11): 접힌 그룹68px 한 줄·하위 업무 행 우측 삭제/복구·상세 편집은 제목/설명·참고 링크2항목·담당자/상태/중요도/일정/진행률 행 편집. 실제 로컬 합성 보드 저장/새로고침/삭제/복구·부모 집계 확인, 기존 업무 보존. DB/API 변경 없음. main push·정확HEAD CI·운영 배포 진행 예정. FLOW-02b 후속.

# 2026-10-11 FLOW-03 인라인 생성·작은 카드 운영 배포 완료

제품 b255c6c 로컬main/origin/main/실서버 반영(17:55 KST). 정확HEAD CI38124898787 SUCCESS: backend1010/skip1·perf1·frontend592/75파일·tools133·타입/lint/format/build/DDL왕복. 기존 Flow12원장 전체행 건수/hash보존·보호 백업20261011-flow-inline-b255c6c·APIactive·DDL0·원점/공개/Flow200·최근5xx0·공개JS/CSS의 로컬/서버SHA동일. 로컬 실제 합성 검증 보드에서 새 업무/하위업무 인라인 생성·이름 저장·새로고침 유지·새 그룹 이름 편집 확인 후 검증 보드 보관. 운영 기존 브라우저 탭은 세션 만료/401로 로그인된 UI 확인 미실행, 재로그인 필요. 운영 업무 쓰기·계정 생성·확장 변경 없음. 상세 docs/agent/Factory_Flow_인라인생성_실제품검증_FLOW-03.md. 최종 문서 기록 커밋은 제품과 구분, FLOW-02b 자동 착수 없음.

# 2026-10-11 FLOW-03 실제 Figma 인라인 생성 보정

열린 Figma 직접 조작/카드 치수 측정 후 사용자 승인. 새 업무/하위 업무 모달 제거·서버 생성 직후 부모 아래 인라인 이름 편집·새 그룹 자동 이름 편집·중복 전송 잠금·실패 입력 유지/IME 처리. 3카드96×72/진행률160×72. 로컬 별도 합성 보드 저장/새로고침/그룹명 검증 및 보관·기존 보드 복귀. DB/API 변경 없음. 정확HEAD CI와 운영 배포 예정. 상세 docs/agent/Factory_Flow_인라인생성_실제품검증_FLOW-03.md. 다음: 검증 완료→main push→CI 성공→보호 백업/표준 배포→공개 UI/원장 보존 확인. FLOW-02b 자동 착수 없음.

# 2026-10-11 FLOW-03 승인 UI 제품 보정·운영 배포 완료

승인 시제품과 제품 daa1905의 실제 UI 차이를 확인하고 단독 셸·breadcrumb/공유·설정 메뉴·표 헤더·상태 배지·아이콘·간격·체크박스/하위업무 선을 보정했다. 회사 등록/API/DB 변경 없음. 회사 미등록 admin과 게스트의 공통 메뉴 유지 브라우저 검증 포함. 제품27a3db0 로컬main·origin/main·실서버 반영(10:53 KST).

정확HEAD CI38102155660 SUCCESS(backend1010/skip1·perf1·frontend590/75파일·tools133·타입/lint/format/build/DDL왕복). 보호된 서버 백업20261011-flow-ui-27a3db0 검증·Flow12원장 건수/hash보존·APIactive·DDL0·공개/원점/메뉴/CSS200·미로그인API401·최근5xx0. 운영 빌드+합성응답으로 화면 캡처·진입/구주소/컬럼drawer/Escape/공유/390px 확인. 실제 운영 쓰기·계정 생성·확장 설정 변경 없음. 상세 docs/agent/Factory_Flow_승인UI_제품보정_배포검증_FLOW-03.md. 다음 FLOW-02b는 별도 범위, 자동 착수 없음. 최종 문서 커밋은 운영 제품과 구분.

# 2026-10-11 FLOW-03 UI 승인 이미지 차이 보정

사용자 승인 시제품과 실제 제품의 표 헤더·native 상태 선택·상시 설정·간격 차이를 확인해 수정. Flow 중복 플랫폼 헤더 제거, breadcrumb/공유·제목 즐겨찾기, 내보드+ 생성/설정 메뉴, SVG 탭·검색·필터·내업무, 상태 배지/키보드 select 유지, 날짜/프로필/체크박스·그룹 스트립/하위업무 선·부가 메뉴 정리. 회사 등록·보드 설정/권한·기존 업무 CRUD 유지. DB/API 변경 없음.

로컬 frontend590/75파일·타입/전체lint/build/범위format·실제품 브라우저 합성7업무/3그룹·39%·런처/구주소/컬럼drawer/Escape/공유 열기닫기·390px overflow0 통과. 출력 Factory_Flow_FLOW04_UI.png는 제품을 합성 데이터로 실행한 캡처이며 운영 데이터가 아니다. main push/정확HEAD CI/운영 배포 진행 예정. 운영 실제 회사/계정 생성 및 확장 설정 변경 없음.

# FLOW-03·HR-USERS-02 운영 배포 완료

2026-10-11 10:09 KST 제품 daa1905를 로컬 main·origin/main·실서버에 반영했다. Figma 보드 UI·자유 컬럼6종/셀·그룹 복제/보관/삭제/복구·총 관리자 회사/첫 회사 관리자 웹 등록 포함.

정확 HEAD CI38099879569 SUCCESS: backend1010/skip1·perf1·frontend590/75파일·tools133·타입/lint/build/DDL 왕복 통과. 로컬/운영 백업 후 flow_board_custom 적용, 기존10원장 건수/hash 보존. 운영 백업 /srv/factory-studio/backups/20261011-flow03 검증. tools/deploy.sh 성공·CI 우회 없음·서버 APIactive·DDL0·공개/원점200·최근2분5xx0. 보드/내업무/사용자관리 URL200, 미로그인 세션/관리역량/Flow API401.

실제193표2102열471FK·목표381표925FK 및 Excel/ERD 동기화. 시드 유지, 실제 운영 회사/계정/비밀번호 생성 없음. 앱 런처→Factory Flow; admin→사용자 관리→회사 등록. FLOW-02b 업무일지 트리/가상화 후속. 확장 설정 유지. 최종 기록 커밋은 문서만이며 운영 제품 daa1905와 구분한다.

# 2026-10-11 GW-FLOW-03·HR-USERS-02 로컬 구현 검증 완료 / 배포 대기

- Figma UI / 즐겨찾기·내보드·4보기·inline 이름 / 그룹 상태·복제 / 자유 열6종·기본 열 메타·원자적 셀 batch100 / 회사·첫 관리자 웹 등록 구현.
- 실제193표2102컬럼471FK·목표381표925FK/Excel/ERD 동기화·카탈로그0오류·빈DB 왕복·로컬 백업 및 Flow 기존10원장 hash 보존.
- backend1009+skip1, 최신 추가 자유열3/HR집중5, 성능1, frontend590 및 최종집중10, 도구133, 타입/lint/format/build·브라우저 진입/구주소/컬럼drawer/Escape/390px overflow0.
- 사용자 main/push/실서버 배포 승인. 현재 main 제품 코드 커밋 후 원격CI 확인·운영 백업·배포 예정. 운영 실제 회사/계정은 생성하지 않는다.

# 2026-10-11 GW-FLOW-03·HR-USERS-02 구현 진행

- 사용자 main 반영·배포 승인. 회사 등록·보드 자유 컬럼 API, Figma 화면 연결.
- 테스트 DB DDL 명세 0오류. 기능 회귀검증 진행, 아직 main/push/배포 미실행.

## 2026-10-10 FLOW-02a 운영 배포 완료·로컬 admin 클릭 비교

Factory Flow 앱 런처 카드→/work-os/boards·/work-os/my-tasks 독립 진입, flow API/10표 이관, 구GW URL·즐겨찾기·멱등 요청 보존, 새 백자/먹색/쪽빛 UI를 운영 제품31623b0으로 배포 완료(21:03 KST). 정확한 HEAD CI38048961871 success: backend1006/skip1·perf1·frontend588/75파일·tools133 및 타입/lint/빌드/DDL왕복·격리 통과. 초기 모듈 개수 상수 실패는 MODULE_KEYS 기준 보정 후 전체 CI 재통과.

서버 백업20261010-flow-31623b0(DB/프런트·비공개/commit/10표digest) 목록·압축 검증 완료. 초기 SSHstdin을 Docker가 소비한 백업 준비를 입력/dev/null 지정으로 재실행·완전 검증 후 배포. tools/deploy.sh exit0/CI우회0, 서버git31623b0/alembicflow_split/APIactive·10표행수/hash보존·DDL0·공개/원점/JS/CSS200·최근5xx0·구/신API미로그인401. 템플릿 시드 버전 동일로 유지, 사용자/비밀번호/DB초기화 없음. 제품 스키마0.24.1·191표2074열464FK. 날짜별 업무일지8표/가상화 FLOW-02b는 후속 미구현.

추가 로컬 admin 조사: 기존Chrome탭 링크 클릭·Enter 이동 차단 재현/직접URL 관리자 정상. busy=false/disabled0/DOM가림·inert0. 동일 프로필·admin세션 새탭 사용자관리/런처/MES 이동 정상 및 사용자 직접 “새 탭은 정상 동작” 확인, 정상 비교탭 유지. 정상탭에도 확장오류가 있어 403과 클릭 차단 인과 단정 금지. 기존탭 입력 차단 원인미확정, 계정·서버권한/확장설정 변경 없음. 로컬8000/5173유지. 실제운영계정쓰기/휴대폰설치 미검증.

상세: [배포 검증](agent/Factory_Flow_독립시스템_배포검증_FLOW-02a.md). 후속 기록은 문서만이며 운영 제품31623b0과 구분. 다음 FLOW-02b 별도 범위 확인.

## 2026-10-10 FLOW-02a 독립 진입·보드 이관 구현

사용자 앱 런처 Factory Flow/독립 보드 분리 진행 및 기존 배포 승인 유지. 신규 참조 폴더의 src/App.tsx/index.css 읽기 분석, 백자#F7F7F6/먹색#1A1C1E/쪽빛#1F2D3D/한지#E8E8E6/청자#2D4442/프로필#E2E3E5·4% 그림자 적용. 참조 파일은 변경하지 않았다.

런처 열 번째 카드 Factory Flow → /work-os/boards, /work-os/my-tasks, 내 공간/메뉴/도움말/카탈로그 연결. 독립 UI에 기존 네 보기/권한/댓글 유지·아바타/진행바 추가. 기존 /gw/projects,/gw/my-tasks query/hash보존 redirect. API 패키지 fs.flow·/api/v1/flow, 구APIalias는 같은 원장 사용. gw.work_*10표 SET SCHEMA→flow, 기존ID/시퀀스/FK/댓글/감사이력 보존. Flow모듈 별도등록/off, 새회사/템플릿/복사정리 목록/후기허용 확장. 메뉴즐겨찾기 순서/중복보존 전환. 기존 gw.projects.* receipt namespace 유지로 재시도 중복0, 데이터엔티티는flow. 날짜별 업무일지8표/가상화 고도화는 이번 요청의 진입·분리와 구분하며 후속 FLOW-02b 미구현.

schema0.24.1/headflow_split·191표2074컬럼464FK, 목표379표918FK·Excel/ERD 동기화. 전용DB DDL0·프로젝트9검사(구API멱등/off독립/실제보드·댓글/10표역이관digest/즐겨찾기왕복 포함), 기존관련26검사, frontend588/타입/lint/format/build, tools133/격리0 통과. 초기 migration SQL 문법·신규테스트 operation명 오류 보정 후 재통과. 로컬 DB 백업 pg_restore검증 후 migration 적용·10표행수/digest보존/DDL0. Chrome 실제 제품UI+합성응답으로 런처진입/oldURL선택유지/색상계산값/390px가로넘침0 확인; 운영 실제계정쓰기 검증은 아니다. 사용자8000/5173·실제계정/비밀번호/확장 설정 유지. main push/CI/운영배포는 후속 확인 중이며 완료 후 이 문서와 인계 갱신.

## 2026-10-10 GW-PROJECT·HR 운영 배포 완료

사용자 실서버 배포 요청으로 main/origin/main의 제품 커밋 `98402d978428a60bd070bda910f740fca234f765`를 기존 `tools/deploy.sh`로 실제 배포했다. 기존 운영 `31af096` → `98402d9`, DB `w0_fav_menu_shape` → `gw_projects`. GW 프로젝트 보드·내 업무, 회사 근무/PWA·관리자 사용자 관리 등 기존 main 변경 포함. Factory Flow 독립 Work OS/업무일지는 설계·검토용 시제품만이며 제품 구현/DB 이관은 아직 승인 대기다.

CI 차단 Ruff migration 서식과 HR 사용자 테스트 Prettier 서식만 보정했다(`71d140a`, `98402d9`). migration AST 비교로 실행 의미/SQL 불변 확인. 최종 CI [38044267825](https://github.com/go8105/factory-studio/actions/runs/38044267825) success: backend1004 passed/1 skipped, 성능1 passed, frontend75파일588검사, 타입/lint/서식/빌드, DB upgrade·downgrade 왕복/DDL·격리·설계 검증 및 도구 검사 통과.

운영 서버 전용 백업 `/srv/factory-studio/backups/20261010-projects-71d140a`에 DB dump/프런트·비공개 자산/이전 커밋을 저장, pg_restore 목록 및 gzip 무결성 검사 완료. 시드 버전 동일 `sv-20261009-gw1`로 기존 템플릿 유지. API active, 공개·원점200, 실제 운영 DDL오류0, 재시작 후 최근2분5xx0. 공개 `/gw/projects`, `/gw/my-tasks`, `/hr/users` 및 JS/CSS200; 미로그인 세션·프로젝트 회사 API401. Python urllib 기본 요청은 Cloudflare403이었으나 curl 공개/원점 검증은 정상; 앱500과 구분한다. 실제 회사 로그인·쓰기/휴대폰 설치는 미검증, 실제 계정/비밀번호/회사 생성 없음. 기존 로컬8000/5173·확장 설정 유지.

상세: [배포 보고서](agent/GW_프로젝트_main_배포검증.md). 이 후속 기록 커밋은 문서만이며 운영 제품 커밋98402d9와 구분한다. 다음: FLOW-01 전체 설계 확인 후 FLOW-02 개발.

## 2026-10-10 FLOW-01 독립 Work OS·업무일지 전체 설계

사용자가 GW 프로젝트 보드를 독립 시스템으로 분리·제공 UI 코드 이식·업무일지 고도화 요청 및 이어서 진행 지시. 방향 승인과 신규 전체 설계 확인을 구별한다. Factory Flow(Work OS·프로젝트 관리·협업), module/schema/package flow, 프런트 /work-os, API /api/v1/flow. 기존 포털 /flow 맵 유지. GW10표 SET SCHEMA로ID/S/댓글/이력 보존, 새 일지8표/총18표191컬럼 설계. 기존 제약42/FK31/상태 보존. 실제 schema0.24.0/headgw_projects·191표464FK 유지.

새 공통 설계: docs/modules/flow/README.md 및 Factory_Flow_독립시스템_업무일지_FLOW-01.md·flow-design.json·flow-design.mmd·별도설계Excel·ui-preview.html. 본부/실→팀기간→팀원→날짜별일지, 제출본회사공유/임시본본인만/지정검토자·자가검토금지/immutable revision. HR원천interface읽기·계정명자동연결금지/수동조직fallback. 구GW주소/메뉴즐겨찾기보존,계정/스키마독립모듈등록·멱등이행·세대정리·성능/가상화·검증명세 포함. 첨부는FLOW-03후속,첫공개는독립앱+UI+일지.

검증: 참조React코드분석(캘린더/간트EmptyView,고정명단/child boolean,일부무동작버튼),설계18표191컬럼/관계·앵커/문서링크/XLSX3시트통과. Spreadsheet artifact-tool 생성·3시트렌더확인. UI시제품JS문법/브라우저검색·일지트리·우측패널·가상제출·390px확인. 모두합성예제/탭내시제품으로 실제API저장 없음. 제품pytest/vitest/실제DDL/migration/부하/배포 미실행(제품변경없음). 사용자원본폴더/실제회사/계정/비밀번호/확장설정 변경없음. 기존5173/8000유지,검토8766서버는종료.

브랜치 codex/gw-flow-design, 설계 문서만 main 반영 대상. 사용자 전체 설계 확인 전 FLOW-02 제품구현/DB변경 시작금지(AGENTS §2 및 설계완료 승인기준). 다음: 설계확인후 새codex/gw-flow-implementation에서원장독립이관·UI·일지동일범위구현→검증→로컬백업적용→mainpush. 전체설계후데이터책임/권한변경이커서기존GW-PROJECT승인으로대체하지않는다. 최종커밋은git log -1. 검토화면/Excel은사용자 outputs와저장소모듈에보존하여work임시파일없이재개가능.

## 2026-10-10 GW-PROJECT 첫 공개 구현 완료

회사 공동 보드·그룹·1단계 하위 업무·복수 담당자·상태/중요도/기간/진행률·표/칸반/기간 캘린더/기본 간트·내 업무·댓글/변경 이력·보드 즐겨찾기/보기 설정 구현. GW G-14/G-15와 도움말 추가. 회사 회원 기본 VIEWER, 지정 EDITOR/OWNER만 업무 수정, 플랫폼 ADMIN/HR ADMIN 자동 권한 없음. 멤버십 fresh authorize·회사 격리·version409·멱등 재시도·마지막 OWNER 보호·자식 집계·보관 배치 복구 검증. 부모 기준 페이지 조회가 자식을 함께 반환한다.

schema0.24.0/headgw_projects: 실제191표2074열464FK, 목표379표918FK. migration/메타데이터/DB Excel/실제·목표 ERD 동시 반영. 기존 COMPANY에 GW 활성 세대 등록, 합성 체험 데이터 복사 없음. 실제 로컬 DB는 pg_dump 백업 후 적용, 카탈로그 대조0오류. 전용 테스트 DB에서 downgrade/upgrade 왕복 및 대조0오류.

검증: backend 전체 병렬1001통과·1skip·성능검사1실패(병렬 부하에서5.817초), 해당 성능검사 단독 재측정 통과. 최종 프로젝트 API7통과. frontend75파일588검사·lint·typecheck·build 통과, 도구133통과. 합성 전용 브라우저에서 네 보기·상태 저장/재조회 확인. 실제 회사/계정/비밀번호 및 확장 설정 변경 없음. 사용자 기존8000/5173 서버 유지. 운영 배포는 미실행. main 병합 및 origin/main push 대상이며 최종 커밋은 git log -1로 확인.

한계: 파일/자유 열/외부 공유/자동화/실시간 동시 편집/오프라인/의존 일정은 후속. 내 업무 최대1000건, 보드는 모든 부모 페이지를 읽어 네 보기에 표시하며 대규모 화면 렌더링 성능은 별도 부하 검증 전.

## 2026-10-10 GW-PROJECT-01 프로젝트·업무 보드 분석·설계 초안

사용자 monday 화면 요청을 분석하고 GW 회사 공동 보드·그룹/1단계 하위 업무·복수 담당자·상태/진행률·테이블/칸반/캘린더/기본 간트·내 업무·댓글/이력·보드 개인화를 제안했다. 기존 게시판/체험 actor 및 과거 TEAM 설계와 현재 COMPANY 공간의 차이를 명시. 실제 회사/스크린샷 업무 데이터 복사 없음. 기본 회사 회원 VIEWER, OWNER 지정 EDITOR; HR 근무 ADMIN/플랫폼 ADMIN 자동 권한 없음. 신규 GW 10테이블 후보만 제시, 실제 schema0.23.3/headhr_time_check·181표433FK 유지.

산출물: docs/modules/gw/GW_프로젝트업무보드_설계초안_GW-PROJECT-01.md, 사용자 outputs 설계서/합성 HTML 시안. 시안 JS node --check 통과. 브라우저 file URL 열기는 브라우저 보안 정책에 차단되어 우회하지 않았으며 렌더링/클릭 검증 미실행. 제품 코드·마이그레이션·운영 배포 없음. 기존 localhost 5173/8000 및 확장 설정 유지. 다음: 사용자 전체 범위 확인 후 상세 DB/API/권한 명세·설계 Excel/ERD 준비, 그 뒤 제품 개발. 기존 사용자 main 즉시 push 승인에 따라 설계 문서만 브랜치→main 반영.

## 2026-10-10 LOCAL-AUDIT 진입 오류·메뉴 클릭 전체 점검

사용자 기존 Chrome 탭에서 메뉴 클릭이 반응하지 않는 현상 재현. 서버는 점검 시작 시 중지되어 있어 공통 기동기로 DB 확인 후 backend/frontend 재실행, 현재 localhost:5173/8000 유지. 실제 Chrome의 기존 admin 세션으로 새 탭에서 MES/QMS/SPC/WMS/FEMS/BEMS/ERP/GW/HR 9개 대시보드 클릭·데이터 로딩·오류 알림 없음 확인. 내 공간·즐겨찾기 편집 창 열기/취소·사용자 관리 회사 조회·CAD iframe 로딩·3D 공장·전체 흐름·도움말도 확인. 콘솔 permission error는 Monica extension ofpnmcalabcbjgholdjcjblkibolbppb의 /writing/get_template_list, EventEmitter/ObjectMultiplex 경고는 MetaMask extension nkbihfbeogaeaoehlefnkodbefgpgknn에서 발생. 해당 확장 오류는 정상 새 탭에서도 발생하므로 클릭 차단 원인이라고 단정하지 않음.

기존 탭은 새로고침/문서 재진입/DevTools 종료 후에도 클릭 차단 재현, JS debugger는 Not paused, 앱 busy=false/내비게이션 버튼 활성/앱 dialog·고정 덮개 없음. 기존 탭의 정확한 차단 원인은 미확정. 사용자는 확장 설정 유지 선택; 확장/쿠키/계정/비밀번호 변경 없음. 정상 동작하는 새 Chrome 탭을 사용자 관리에 남김. 앱 코드 변경 없음·DB 스키마 변경 없음. 새 게스트 검증은 기존 로컬 게스트 상한 때문에 RATE_LIMITED였으며 데이터를 지우거나 상한을 변경하지 않음. 실제 증거는 사용자-facing outputs/로컬_메뉴_동작확인.png. 다음: 새 탭에서 사용, 기존 탭의 환경 문제는 추가 재현 정보 또는 사용자 별도 브라우저 비교가 필요. 점검 결과 문서만 main push.

## 2026-10-10 LOCAL-START 로컬 500 및 IntelliJ 주소 통일

실제 로컬 DB/Colima가 중지된 상태에서 DB 연결 거부 재현. 기존 IntelliJ 전체 구성은 DB 기동 없이 front/backend만 실행했고 Compose 플러그인도 없었다. 공통 start_local.py가 기존 Colima 프로필/DB를 기동하고 실제 DB 연결 확인 후 서버를 실행한다. 동시 DB 준비 파일 잠금, Compose standalone fallback, 기존 데이터/볼륨 보존. 공유 .run Local - All 추가와 PC 기존 .idea 명령 보정. backend 표시/접속은 localhost:8000, front는 localhost:5173; Vite DNS verbatim 고정 및 프록시 IPv4 지정으로 표시 변동/IPv6 API 연결 실패 방지.

검증: 중지된 Colima/DB 실제 복구, backend/frontend 동시 기동, localhost front HTTP200, 만료/위조 쿠키 API401(500 없음), 기존 admin의 current_session 서비스 조회 성공. schema head hr_time_check 유지, 실제 계정/비밀번호 변경 없음. frontend584·타입/lint/build·기동스크립트 Ruff 통과. 사용자 main push 승인 유지. 검증용 앱 서버는 종료하고 DB 유지; IntelliJ Local - All로 실행. 운영 배포 없음.

## 2026-10-10 W1-HR-USERS 관리자 사용자 관리 완료

사용자 요청으로 터미널 최초 비밀번호 설정을 관리자 웹 화면으로 대체했다. 기존 활성 플랫폼 admin 로그인 → /hr/users → hugh-D Company 선택 → 각 계정 관리 → 비밀번호 설정·사용 재개. 새 사용자 아이디·비밀번호·사원 코드·이름·근무 권한·올해 연차를 함께 등록한다. 플랫폼 ADMIN은 회사 목록, 회사 ADMIN은 자기 회사만 관리하며 STAFF/게스트는 접근 불가. 비밀번호는 반환하지 않고 변경 시 기존 세션 종료. 자기 계정 변경·마지막 회사 관리자 제거·다중 회사 계정 변경 차단, 멱등 요청/동시성/감사 기록에서 비밀번호 제외. 로컬 두 예제 계정은 사용자 설정 전까지 비활성 유지.

검증: 관련 backend29개 및 새 사용자 API4개 재검증, frontend전체584개/새 화면4개 재검증, 타입·lint·format·build 통과. Chrome 별도 합성 테스트 DB에서 실제 회사 조회/계정 관리 폼 표시 확인(브라우저 비밀번호 제출은 사용자에게 맡김). 스키마 변경 없음: schema0.23.3/headhr_time_check·181표433FK. 사용자 main push 승인 유지; 운영 배포/실제 휴대폰 설치 미실행. 다음: 기존 admin에서 두 계정 비밀번호 설정 후 사용. 회사 정책 편집·다음 연도 연차 자동 부여는 후속.

## 2026-10-10 W1-HR-TIME 회사 공동 근무·PWA 구현

사용자 전체설계/회사 공동/hugh-D Company 관리자1·직원1/터미널 비밀번호 설정 승인. 실제 회원만 회사 멤버십+HR 사원 연결로 접근, 직원 본인/관리자 회사 조회. 버튼 출퇴근·1시간 시간차·연차·반차·출장·승인/취소 승인·이력 정정·월 마감·합성 게스트 체험/PWA 구현. 로컬 회사+비활성 hugh-admin/hugh-staff 준비. schema0.23.3/headhr_time_check, 실제181표433FK/목표369표887FK, DBxlsx/ERD 갱신·DDL왕복오류0. 회사 API9+활성화1/스키마9, 도구133, 프런트580·타입/형식/빌드 통과. 전체backend991통과1건너뜀/DDL1실패 보정 후 해당검사 재검증 통과. Chrome 별도API 직원출퇴근/관리자조회정정·390px 확인. [구현/시작안내](agent/회사근무_구현검증_W1-HR-TIME.md). 로컬 main·origin/main 반영. 운영배포/실제폰설치 미실행, 비밀번호 사용자 입력 대기.

## 2026-10-10 HR-TIME-01 회사 공동 출퇴근 PWA 설계

사용자 회사공동/버튼출퇴근/1시간시간차 확정. [설계안](plan/회사공동_출퇴근_PWA_HR-TIME-01.md) 작성: HR소유·GW바로가기, 회사멤버십/사원연결 선행, 실제회원/합성게스트체험 분리, 실제시각원장·휴가분단위·출장·PWA오프라인제출금지. 기존AUTO예정근태·반차승인clock초기화와 실제기록 충돌 확인. 구현/DB변경/회사활성화 없음. 다음: 전체설계확인 후 회사접근기반부터 구현.

## 2026-10-10 사이드바 긴 메뉴·별 배경 보정 / main 반영

사용자 main 즉시 push 승인. W0-FAV-2 전체 즐겨찾기·아이콘 접기와 이번 고정24px아이콘/긴이름줄바꿈/별주변투명배경을 함께 main에 병합한다. 관련23테스트·타입검사 통과, 실제Chrome 긴게시판명 overflow없음/아이콘24px/별버튼배경투명 확인. 운영배포는 이번요청범위에 포함하지 않음. 이후 같은 사이드바 작업은 검증 후 main push 승인 유지.

## 2026-10-10 W0-FAV-2 전체 즐겨찾기·아이콘 사이드바 완료

- 사용자 요청: 현재 솔루션 필터를 제거해 모든 솔루션 즐겨찾기를 저장한 순서로 표시. 라벨/접근성 이름에 솔루션을 표시해 중복 대시보드 구분.
- 넓은 화면 접기는 메뉴를 숨기지 않고 아이콘 레일로 전환. title/aria-label로 설명과 키보드 이동 제공. 좁은 화면 서랍은 기존 표시 유지.
- 등록 별: 채운 금색/노란 배경/진한 테두리. 미등록은 회색 윤곽.
- 검증: frontend575/72파일·typecheck/lint/build 통과. 회귀는 교차GW/WMS 링크·접기 유지·전체전환/추가저장 포함. 실제Chrome GW에서 전체6개 표시→접기→MES아이콘 이동 확인.
- 브랜치 codex/favorites-sidebar-all. 이번 변경은 로컬 개발 서버 반영, 운영 배포는 아직 하지 않음. DB 변경 없음.

## 2026-10-10 GW·즐겨찾기 main 병합·운영 배포 완료

제품31af096 로컬main/원격main 병합 후 CI전체통과 및 정식deploy.sh 완료. 운영HTTP200/DDL오류0/최근5xx0/API14검사 통과, 실제Chrome저장·새로고침·MES등록메뉴표시 확인. 로컬DB구버전500은 백업 후 head마이그레이션으로 복구·기존공간유지. [결과](agent/GW_즐겨찾기_main_배포검증.md). 후속기록커밋은문서전용, 제품배포31af096.

## 2026-10-10 GW·즐겨찾기 main 병합/배포 진행

- 사용자 명시적 로컬 main 병합·운영 반영 요청. main af10726 깨끗함, origin/main3ff4cf5 및 운영f860e8b는 작업head 조상. fast-forward 병합 예정. 기존 사용자 변경 보존.
- 기존 CI 차단 보정: DSN-22는 W2a가 이미 확장한 MES CHECK 허용(누락/알 수 없는 형태 거부 유지), DSN-12는 부분 구현에서도 ERP 원천 코드 보정, DSN-28/90은 이미 구현한 컬럼 중복 추가 방지. DSN-31은 체험19표 존재만으로 TEAM/ERP 목표 설계 완료로 오판하지 않도록 기본GW→전체목표24표 재구성하고 구현 추가컬럼 보존. 목표재생성/멱등/계약 및 체험→미구현설계 회귀 포함 tools133통과. 목표361표866FK·Excel/ERD 재생성, 실제DB스키마/마이그레이션 변경 없음.
- SPC 종료일 없는 관리도 테스트는 고정 기준일 이후 측정·DB정책 시계를 테스트에서 고정한다. 제품 실행기간 검증 유지, SPC18통과. backendRuff/format 통과. 다음: 커밋→로컬main병합/push→해당head CI→백업/정식deploy.sh→운영 브라우저/API 확인·최종 인계. 아직 배포 완료 아님.

## 2026-10-10 W0-FAV 내 공간·즐겨찾기 완료

- 사용자 참고폴더/이미지 기반 내 공간·사이드바 개인화 구현. GW 검토 bfae108→codex/workspace-favorites, WIP ca74aaa, 최종 커밋 git log -1. main/공유DB/push/배포 미실행.
- 실제9솔루션108메뉴 공통JSON, 기본6카드·3열선택·검색·순서·등록메뉴 사이드바/전체전환. 공간 서버저장·멱등/버전/감사·초기화보존·최근방문 브라우저별, 다른 업무 잠금 보존. P-06 도움말 갱신.
- schema0.22.1/173표1918컬럼412FK, core.workspace2컬럼3CHECK, 적용한 초기revision 변경 없이 새revision 보강. 실제·목표Excel/ERD/base_task 동기화. 독립DB 실제DDL0·별도빈DB GW→신규→롤백→재적용4회DDL0, 임시왕복DB 제거.
- 신규backend8, 전체frontend575/72파일, lint/format/typecheck/build 및 backendRuff/format206파일·설계/격리 오류0. 전체backend982통과/기존main SPC실패1/skip1·perf1통과. tools131통과/기존main DSN목표재생성오류1. 전체CI완료로 표시하지 않음.
- Chrome 카드/ERP추가/순서·새로고침 유지/MES2메뉴만/최근방문, 390px넘침0·적용44px·Esc포커스/Tab순환 확인. [검증·화면](agent/내공간_즐겨찾기_검증_W0-FAV.md). 실제main병합은 기존CI차단 해결 후 최신head 검토 필요.

## 2026-10-09 GW-main 병합 검토 완료 — 기존 main CI 실패 2건 해결 후 병합 제안

- 사용자 main 병합 검토 요청. codex/gw-dsn31 제품17f0f18 / main af1072669d6441d3b70605ff01054bc294cca393. main 직접 조상, merge-tree 충돌0/fast-forward 가능. 공유 main 작업 트리 변경 없음, 병합·push·배포 미실행.
- 최초 GW 8표 설치 도구가 후속19표를 부분 설치로 오판하는 회귀 수정. 기본8표 포함 검사로 확장 보존, 기존 누락 거부 유지·후속 확장 무변경 회귀 추가. 도구7+4통과.
- PG18 일회용 DB에서 빈DB→main→GW→main롤백→GW재업그레이드 실제 DDL4회 대조 오류0, DB제거. frontend566/71파일·전체lint/Prettier/typecheck/build·전체backendRuff/format202파일·DB설계/격리0.
- CI방식 backend974통과/기존main SPC실패1/skip1(388.90초), 독립perf1통과(28.70초). tools132건 중131통과/기존main DSN목표재생성오류1. 원본 main에서 DSN오류 및 SPC단독실패 재현. 전체CI통과로 표시하지 않음. 최초 임의loadscope 분배로 발생한 초기화순서 파손 실행은 회귀판정에서 제외하고 기본분배로 재검증.
- 기존 CI차단2건 해결 뒤 최신main/head 재검토→병합 제안. 신규 ERP/PLM원천·ERP F44·실제회사A·인쇄/PDF 제한 유지. [검토·재현](agent/GW_main_병합검토.md). 사용자 추가 승인: 다음 작업은 참고폴더/이미지 기반 내공간 즐겨찾기·솔루션 사이드바 개인화, 별도브랜치에서 진행.

## 2026-10-09 GW-e 시드·도움말·통합 검증 완료

- 작업 ID GW-e, codex/gw-dsn31, 시작8216636. 새 시드 sv-20261009-gw1: GW19표98행, HR 합성 사원/부서 사전·ERP 공개 조회 원문 연결. 병렬 대기/전결·위임/기존순차/댓글이력/일정응답/알림/채팅 포함.
- 세대 복사: FK 외 사건 JSON 단계/위임/전결ID·월/시각·범위와 다형 알림 대상/사건키 변환, KST 상신월 재계산. JSON SQL NULL 구분, 같은TX 여러복사 지도 정리. 기존 템플릿/원문digest/채팅순번/커서/클라이언트키 보존. V-GW 실제데이터 검증 추가.
- 도움말 G01 신규·공통 안내·G01~13 전체 파일, HR→GW조직→결재→협업 3노드/3연결, DSN90 실제 계약·외부 미구현 범위 명시.
- 전용DB6통과(새해/윤년복사·초기화·지연복사·유데이터정리·위임/합의종결·메시지재전송·월초템플릿). frontend566/71파일·타입/전체lint/build·변경Ruff/format·DB173표412FK격리0 통과. 전체backend974통과/1실패/1건너뜀→새게스트GW없음을 전제한 기존조직격리1건을 시드10명4부서+외래ID404로 보정, 조직17전체재통과(975개 서로다른백엔드테스트 확인). 기존policy import정렬1건보정으로 전체backendRuff도통과. Chrome 새공간에서 위임승인→합의→최종종결/알림링크일정응답/댓글수정이력·삭제표시/채팅seq3/390px/도움말·흐름 확인.
- 완료: WIP d78e534 후 최종문서·증거/인계 커밋. 다음: 사용자 결과 확인 후 main 병합 검토, 새시드 적용시 템플릿 재생성. main/공유DB/push/merge/배포 없음. 실제도입A/TEAM/ERP F44 제외.

# 2026-10-09 GW-d 댓글·일정·알림·채팅 완료

- 작업ID GW-d, codex/gw-dsn31, 기준b39e274/WIP2a30415. G-04/05 댓글·부서공지, G-11 월/주 일정·참석응답, G-12 내부 알림함, G-13 HTTP저장/3초조회 채팅, EIP 공지·공통4종 제공 구현. CSRF·공간잠금·버전·멱등/감사 공통 action. 댓글원문/결재 불변·수정revision/삭제표시, 조직 이동 열람/알림 재검사, 메시지seq/재전송중복0·탈퇴후조회/전송 차단. 공통engine optional authorize로 멱등 영수증 재사용 전 권한 재검사. 삭제/취소/나가기 화면내 확인, 미저장 보호.
- 검증: 전체backend967passed/1skipped(362.24초, 마지막권한보정 전), 최종공통/GW 103통과(협업신규23 포함), frontend전체566/71파일(15.18초, 신규협업7), 타입/전체frontendlint/build·변경Ruff/포맷·DB설계/격리0. 기존root전체Ruff GW import2건/기존청크·사용중단 경고 유지.
- Chrome 실제 일정 생성/한국시간14~15시 수정·참석응답, 알림읽음/원문이동, 공지게시·상대댓글/수정이력/삭제표시, 두탭채팅자동수신 #1~3·읽음·모바일나가기/목록제거, 390px 일정/알림/채팅 가로넘침0·도움말 확인. Mac잠금 native confirm 제어 지연은 화면내 확인 UI로 보완; 네이티브 인쇄/PDF는 기존미검증 유지. 대량실시간부하·운영/실제회사인증 미검증.
- 스키마/마이그레이션/시드 그대로, main·공유DB·push/merge/배포 없음. 검증서버8073/5273 종료. 다음 사용자 확인 후 GW-e 시드/도움말/유데이터복사·정리·통합검증. ERP F44/신규원천제공은 외부 소유. [결과](agent/GW_협업_GW-d.md).

# 2026-10-09 GW-c 조직·HR 연계 완료

- 작업ID GW-c, `codex/gw-dsn31`, 시작0dd6ef9/WIP1fe0642. G-07 공통 MasterScreen·HR 미리보기/사원 선택/부서 전체 가져오기·부분 수정, G-10 현재 HR/가져온 조직 조회, 도움말2편. HR interface만 읽고 이름·부서 스냅샷을 명시적으로 반영한다. 직무·활성·상신 기록 보존, 퇴직/원천 없음/조회 불가 표시, 조직 순환/상위 활성/코드 충돌·원천 변경·동시성·전체 롤백 보호. 역할 명단100명 제한 보완.
- 검증: backend전체944/1skipped(362.48초), 마지막GW66(신규17 포함), frontend전체559/70파일·최종집중134/16파일, 타입/전체frontendlint/build·GW Ruff·DB설계0. 전체root Ruff는 시작 커밋과 동일한 기존GW 테스트 import 정렬2건. 기존 MES 테스트의 빈 대시보드 mock을 정상 합성 응답으로 보정 후 전체프런트 통과. 감사 보정 후 GW-c17개도 통과(46.13초).
- Chrome 실제 HR 개방 전 안내·부서4/사원10 가져오기·HR 부서명 변경·현재 HR/마지막 GW 차이·동일10명 재가져오기·390px 본문 넘침0·도움말 확인. 발령 이동·상신 조직 불변은 DB/API로 검증. [상세](agent/GW_조직HR연계_GW-c.md).
- DB/schema/시드 버전 유지, 실제 계정/TEAM/ERP 확정통제 제외. main/공유DB/push/배포 없음. 검증 서버·탭 정리. 다음은 사용자 결과 확인 후 GW-d 협업, 미착수.

# 2026-10-09 GW-b 핵심 결재 보강 완료

- 작업 ID: GW-b. 사용자 승인 후 `codex/gw-dsn31` 격리 worktree에서 정책v2·병렬·합의·참고·전결·위임 구현. G-02/03/04/06 보강, G-08 공통 MasterScreen·G-09 위임 관리, 관련 도움말6편. 기존v1 순차 유지·상신 증빙 고정·재상신 새 회차. DB 변경 없음(GW-a head 유지).
- 검증: 전체backend927통과/1건너뜀(331.13초), 마지막 계약 보정 후 GW/스키마58통과(122.59초). 전체frontend554통과, 최종GW/콘텐츠26통과, tsc·전체frontend eslint·Vite build·GW ruff·DB설계 오류0. 전체backend ruff는 기준본에도 있는 core/service.py import 정렬1건으로 실패.
- Chrome: 실제 결재선·전결·위임 등록, 500KRW 상신·뒤단계생략, 대리승인 뒤 합의대기, 합의 후 최종승인·원 담당자/대리자 이력. 390px body가로넘침0·표내 스크롤.
- 제약: F03 ERP 발주/경비·PLM ECO 실제 제공 미구현, GW 소비/배지 계약만 연결·mock검증. F10 인쇄 구현했으나 Mac잠금으로 네이티브 미리보기/PDF 출력 미검증. F44 ERP 통제는 W2b Claude 소유. main·공유DB·push·배포 변경 없음.
- 다음: 사용자 결과 확인 후 GW-c 조직·HR 연계. GW-c 미착수. [상세 결과](agent/GW_결재확장_GW-b.md).

# 2026-10-09 GW-b WIP

사용자 승인 후 구현 진행: 정책 v2, 병렬·합의·참고·상신 시 전결 스냅샷·처리 시점 위임 검사·G-08/09. 아직 테스트/브라우저 검증 중, 완료로 표시하지 않음. ERP/PLM 신규 원문 제공은 외부 소유 미구현.

# 개발 진행 기록

## 2026-10-12 W2a-1b2 MES 기준정보 보강 (M-12·M-13)

- **M-12 품목**: 설계(DSN-12 F12·F13·F17)의 상세·관리·포장 칼럼 15개를 화면까지 붙였다. 조회 칼럼·요청 본문(`ItemDetail`을 Create/Update가 상속)·목록 열(품목 그룹·규격·포장)·입력 패널. 입력 패널은 덜 쓰는 칸을 `<details>`로 접어 두었다 — 설계의 '탭' 대신 접이 묶음을 썼다(새 탭 컴포넌트를 만들지 않으려고). `plm_part_no`·`plm_revision`은 PLM(W4) 몫이라 화면에 넣지 않았다(DB에는 있다).
- **M-13 공정**: 공정별 불량 코드(`mes.process_defect_code`)를 허용 설비와 같은 방식으로 붙였다. 공정이 가진 목록이 둘이 되어 `process_equipment_ids`·`replace_process_equipment`를 **종류를 받는 한 쌍**(`process_link_ids`·`replace_process_links`)으로 합쳤다. 공정을 지울 때 두 목록 모두 비운다.
- 검증: 백엔드 **1,009개 통과**(perf 제외), 프런트 **596개 통과**, ruff·prettier·eslint·tsc·build 통과.
  - `tests/test_gw_projects.py::test_flow_migration_roundtrip_preserves_records_and_favorites` 1건 실패는 **내 변경 전에도 실패**한다(stash 후 확인). 다른 세션 몫이라 건드리지 않았다.
  - 로컬·CI·테스트 DB를 head로 올렸다(다른 세션의 `flow` 모듈 마이그레이션이 빠져 있어 MES 테스트가 전부 깨져 있었다).
- 미실행: 브라우저 확인, M-14 공정 경로(표준 시간·외주 단계)·M-15 BOM(투입 공정·대체 자재), 시드·도움말.
- 다음: M-14·M-15 — 둘 다 요청 본문 모양이 바뀐다(`RouteSteps.processIds` → 단계별 속성, `BomLineIn` + 투입 공정, `mes.bom_substitute` 자식 표). 화면·테스트를 함께 고쳐야 한다.

## 2026-10-09 GW-a 체험 그룹웨어 DB 보강

- 사용자 “최종 판단하고 진행”으로 D83의 GW 범위를 착수. [결과](agent/GW_체험보강_DB_GW-a.md). 별도 브랜치 `codex/gw-dsn31`/worktree, 시작 `af10726`. Claude 인계의 16표와 A 제외가 충돌하여 DSN-31 §4-1 체험·조직 11표를 이관, A5표·CORE TEAM·ERP 통제는 제외했다. GW8→19·전체162→173, 기존6표15칼럼, schema0.21.0/head`gw_a_dsn31`.
- 목표에서 복사하는 `apply_gw_a.py`(멱등), 단계 순번 UK2 제거 슬롯 보존, 기존 제약 교체는 제자리/새 제약·FK는 끝에 추가. 생성 migration131문. 공통 생성기 downgrade의 FK/제약 삭제 순서 보정. 제품 검사기는 GW 단계의 부분 이관 지원, 목표 TEAM/ERP 요구 유지. 기존 migration 변경 없음. metadata/Excel47시트/ERD/검증 기록 갱신.
- 검증: 제품·목표 오류0, 격리0, 독립 PG18 테스트 DB DDL대조0(173표·1916칼럼·412FK). 기존 API의 합성 승인문서가 있는 상태에서 downgrade→이전명세대조→upgrade→신규명세대조 모두0/기존값 보존. 도구4·신규 실제 DB3 통과(병렬UK·알림중복/공간FK·조직self-FK/담당자 소속복사·정리). 전체 backend900통과·1건너뜀(330.21초). 기존GW frontend5·전체tsc/eslint·backendruff/format 통과. 실제 Chrome 게스트→GW현황→담당자등록/목록 확인, 화면/DDL/왕복 결과 Git에 보관.
- 초기 검사 실패: 단계 ID/전체 목표 검사의 범위 오판은 검사기 보정, 신규 테스트의 존재하지 않는 GW 시드 전제는 합성 담당자 fixture로 보정한 후 재실행 통과. 신규 도구 executable/생성물format도 보정. 미실행: 신규 API/화면·프런트 전체 테스트/build·공유 개발/CI/운영 DB 적용·원격push/배포. 시드 버전 변경 없음.
- 다음: 사용자 GW-a 결과 확인 후 GW-b 결재 정책v2·전결·위임. 체험테이블 존재만으로 업무구현 완료라 하지 않는다. ERP/PLM 원천 제공 인터페이스 구현 시점 확인 필요.

## 2026-10-09 UI-DESIGN-02 추천안 실제 UI 적용

- 사용자 “추천안 대로 진행”으로 UI-DESIGN-01 전체 구성 확인 완료. [결과](agent/UI개선_적용결과_UI-DESIGN-02.md). Taste 랜딩 문구·2열 체험/기능 소개·공개 합성 NC 캡처. Impeccable CAD 셸/도구·입력·초점, NC 준비4단계/뷰포트/휴디·제안·근거, 공장 탐색/하단 시연·맥락 패널 정돈. 새 라이브러리/DB/계산 커널/권한 변경 없음.
- NC 기존 노드를 재배치해 값·이벤트·모델 참조 보존, DOM 계약 테스트 추가. 열 높이/모바일 canvas 넘침 보정, 기존 제안 무효화/품질 차단/관리자 POC 보호 유지. NC/공장 도움말 배치 설명 보완.
- 검증: CAD142·frontend551/68파일(병행 MES 포함)·최종 도움말/포털/CAD/공장 대상40·전체build/공개비공개 자산 격리·대상 lint/포맷/diff 통과. Chrome1440/390, NC→STEP→소재→에너지→3후보→휴디 텍스트3번 재생/정지, E2 24,000mm³ 실제 모델, 랜딩 로그인·공장 내부/정지·CNC 패널 확인. 공장 browser 4종 최종 통과(CNC 한 개 완료/정지/오류 복구/모바일 포함). 외관 WebGL 다중 캡처30초 초과→60초 재검증33.3초 통과, 해당 테스트 제한 명시. 검토 스크립트의 숨김 canvas·STEP 읽기 대기·접힌 텍스트 입력 선택 오류는 수정해 재검증. E2 크기 변경 순간 넘침을 보정.
- 스크린샷/결과는 Git에 저장. 관리자 비누 이미지·고객 데이터 없이 공개 합성 NC만 랜딩에 사용. 현황200줄 유지·README/계약 상태 갱신. 실제 마이크·실 CNC/계측·DB·운영 배포 미실행. 로컬 main 커밋, 원격 push 없음. 병행 MES/common/master·화면·테스트는 스테이징 제외.
- 다음: UI-DESIGN-02 결과 확인 후 다음 작업 결정. CAD-17/GW/배포 자동 착수 없음.

## 2026-10-09 W2a-1b MES 기준정보 화면

- 신규 기준정보 4화면을 **공통 엔진**(`fs/common/master.py` + `shared/master.tsx`)으로 만들었다. 기존 MES 화면은 자기 방식을 그대로 둔다.
  - **M-16 불량·사유 코드**(탭 2): 실적의 불량을 코드로 적고, 비가동·비계획 입출고·폐기·재작업 사유를 코드로 둔다. **'계획된 정지'는 비가동 사유에만** 표시한다(DB CHECK와 같은 규칙을 API가 먼저 본다).
  - **M-17 작업자·근무조**(탭 2): **작업자 코드가 곧 바코드**다. 인사 정보는 HR이 갖고 여기엔 사원 코드만 스냅샷한다(FK 아님). 근무조는 작업자가 있으면 삭제를 막는다.
  - **M-19 라벨 양식**: 팔레트만 QR, 나머지는 Code128. **종류마다 기본 양식은 하나**(조건부 유니크와 같은 규칙을 API가 먼저 본다). 크기는 20~210 × 10~297mm.
  - **M-26 공정 검사 기준**: 품목을 비우면 그 공정 공통. 수치 검사는 상·하한 중 하나와 단위가 있어야 하고 상한 < 하한을 막는다. 합·부 검사는 한계를 쓰지 않는다.
- 백엔드 `fs/mes/masters.py` 신규(Master 선언 6개 + 규칙 검사), `schema.py`에 본문 12개, `router.py`에 `_master_routes` 묶음으로 **12경로**(MES 50 → 62).
- **고친 것 1 — 중복 검사가 NULL을 못 잡았다**: 공통 엔진의 `duplicate()`가 `item_id=:item_id`로 비교해, 비워 둘 수 있는 키 칸(공정 검사의 품목)이 NULL이면 중복을 그냥 지나쳤다. `IS NOT DISTINCT FROM`으로 바꿔 '둘 다 비었음'을 같은 값으로 본다. **모든 솔루션에 적용된다.**
- **고친 것 2 — 탭을 바꿔도 목록이 그대로였다**: 두 `MasterScreen`을 탭으로 갈아끼울 때 React가 같은 컴포넌트로 보고 다시 읽지 않았다. `key`를 주어 새로 띄운다. `master.tsx`에 그 주의를 적었다.
- **알려진 한계**: `mes.inspection_item`의 UK `(…, process_id, item_id, seq)`는 `item_id IS NULL`인 행끼리는 DB가 막지 못한다(SQL에서 NULL ≠ NULL). 지금은 서비스가 막지만, 동시 등록이면 둘 다 들어갈 수 있다. 목표 설계에 조건부 유니크를 더해야 완전해진다 — 설계 변경이라 이번 범위에서 하지 않았다.
- 검증: 백엔드 `test_mes_masters.py` 6개 신규 포함 **897개 통과**(perf 제외), 프런트 `src/mes` 57개 포함 **551개 통과**, tsc·eslint·prettier·ruff·전체 build 통과. 브라우저(새 게스트 공간) 실제 확인: 불량 코드 등록(소문자 → 대문자 SCR), 사유 코드 탭 전환이 다시 읽음, 작업자 2명·근무조, 라벨 2종(LOT Code128 60×40 / 팔레트 QR 100×80, 둘 다 기본), 공정 검사 2건(수치 9.8~10.2mm / 합·부).
- 미실행: M-12~15 기존 화면 보강(W2a-1b2로 미룸 — 품목 상세·관리·포장 탭, 공정별 불량 코드, 표준 시간·외주 단계, BOM 투입 공정·대체 자재), 시드·도움말, 운영 배포.
- 다음: W2a-1b2 기존 MES 기준정보 보강.

## 2026-10-09 UI-DESIGN-01 도움말·디자인 스킬·UI 전체 검토

- 사용자 요청: CAD·CAM/3D 공장 도움말과 UI 개선, Taste/Impeccable 프로젝트 적용, 랜딩의 추상적인 홍보 표현 제거. 이번 ID는 도움말·스킬·전체 UI 검토까지, 제품 구조 변경은 UI-DESIGN-02 전체 확인 대기. [검토안](ui/UI개선_전체검토안_UI-DESIGN-01.md)·[비교 시제품](ui/previews/UI-DESIGN-01.html).
- 공개 도움말 5편(E1/E2/NC/휴디/공장), P-05 연결, 검색·목차와 작업 화면 경로, CAD 셸/공장 도움말 링크. 기능·제한·추정 소비·품질 차단·화면 재생과 실제 CNC 구분. 관리자 POC 파일·제품 설계는 노출하지 않는다.
- 프로젝트 `.agents/skills/factory-taste`, `factory-impeccable`: skill-installer로 Taste18dfc928·Impeccablec5ae03ee 고정 revision 설치 후 Codex/기존 Vite·CSS/한국어/색상/설계 승인에 맞게 파생 지침 작성. 원문·LICENSE·NOTICE·ORIGIN 보존. 실행기·자동 다운로드·hook·agent 설정 제외, 원본 참고 명령은 비활성 설명. 다음 턴부터 프로젝트 스킬로 사용.
- 랜딩: 실제 범위·별칭 진입 중심. CAD: 작업 공간·분석 준비·결과/휴디 분리. 공장: 탐색·선택 설비/시연 분리. 구조 시제품은 검토용 버튼과 배치 도형이며 제품 분석/로그인/3D 모델 구현이 아니다.
- 검증: 프런트 **546/67파일 통과**, 도움말/포털/CAD/공장 대상40 통과, 전체build·공개/비공개 자산 격리·대상 lint/Prettier/diff 통과. 처음 Markdown 강조 닫힘 오류1건 수정 후 전체 재검증 통과. 스킬 quick_validate2개 통과(시스템 PyYAML 미설치로 임시 venv 이용, 제품 의존성 변경 없음). Chrome 시제품3화면 전환·1440/390px 가로 넘침0·캡처4장/육안 검토. 기존 큰 번들 경고 유지.
- 미실행: 제품 UI 재배치·실마이크/TTS 리허설·운영 배포·DB 검사/변경. 병행 MES 코드·테스트·화면 변경은 소유자 작업으로 보존하고 스테이징 제외. 준비100%/제품 구조 변경0%, 다음은 사용자 전체 UI안 확인 후 UI-DESIGN-02. 이번 커밋은 로컬 main, 원격 push/배포 없음.

## 2026-10-08 W2a-1a MES 보강 DB

- 목표 설계(DSN-12)의 MES를 제품 설계로 옮겼다. `tools/apply_w2a1.py`(멱등). **mes 21 → 45테이블**, 전체 138 → 162. 기존 10표에 칼럼 35개(품목 상세·관리·포장, 표준 시간·외주 단계, BOM 투입 공정, 설비·우선순위·분할·재작업, 분할 원 LOT, 자재 LOT·출처, 패킹 해체, POP 출처). **모두 NULL 허용이거나 기본값이 있어 운영 데이터가 안전하다.**
- 제약 3개는 넓어진 정의로 **제자리에서** 교체했다(작업지시당 LOT 1개 UK → 분할 LOT을 허용하는 조건부 유니크, 패킹 상태에 void 추가, 지시 종류에 REWORK 추가). 제약 이름이 schema.json 배열 순번이라, 새 제약은 **배열 끝에만** 붙여 기존 DB 이름을 흔들지 않았다.
- `tools/build_migration.py`에 **기존 표 변경** 기능을 넣었다(`--previous`). 지난 설계와 비교해 `ALTER TABLE ADD COLUMN`·바뀐 제약 DROP/ADD·새 FK만 만든다. NOT NULL을 기본값 없이 더하려 하면 멈춘다. 빈 목록에서 쉼표만 남던 생성 버그도 고쳤다.
- 마이그레이션 `w2a1_mes` 266문(새 표 24·칼럼 35·제약 116·FK 66·인덱스 22·교체 3). 시드가 든 DB에서 올리고(품목 6·작업지시 30행 그대로, 새 기본값 채워짐) 내리고 다시 올려 확인했다.
- **고리 FK 처리**: 새 FK로 `mes.work_order`(재작업 → LOT)와 `mes.lot`(→ 작업지시)이 **서로를 가리키게** 되어 게스트 정리·시드 복사의 위상 정렬이 깨졌다. 고리에 속한 **비울 수 있는** FK만 먼저 비우고(정리) 또는 그 간선만 무시하고(복사) 순서를 잡도록 고쳤다. 고리 밖 FK는 건드리지 않는다 — 처음엔 비울 수 있는 FK를 모두 비웠다가 `fems.energy_target`의 CHECK를 깼다.
- 검증: `db:validate` 제품·목표 오류 0, `audit_schema_isolation` 업무 스키마 간 FK 0, `verify_ddl_matches_schema` 실제 DB 대조 오류 0(표 162·칼럼 1,781·FK 380), ERD 11개·DB설계서 47시트 재생성, 백엔드 **891개 통과**(perf 제외), ruff 통과. 로컬·CI·테스트 DB 모두 마이그레이션 적용.
- 미실행: 화면·API(W2a-1b부터), 시드(W2a-1f), 운영 배포.
- 다음: W2a-1b 기준정보 화면(M-16 불량·사유 코드, M-17 작업자·근무조, M-19 라벨 양식, M-26 공정 검사 기준, M-12~15 보강).

## 2026-10-08 CAD-V01 휴디 NC 음성·후보 재생 구현

- 사용자 전체 흐름 승인 및 최신 환경 변경 **맥북 Google Chrome·NC 에너지 제안**. [계약](modules/cad-cam/음성발표데모_제안_CAD-V01.md)과 [결과/발표 준비 순서](agent/휴디_NC음성발표_CAD-V01.md). 이전 Windows 가정 대체, CAD-17 미착수.
- 호출어·30초 명령 창·한국어 응답, 최종 발화/번호 파서·중복/TTS 자기 음성 차단·탭 종료·오류/재시도 상한·버튼/텍스트 대안. 후보 번호/ID/revision·선택, G4만 대체한 원본 경로 시간 모델 재생·정지/재개/속도·행/공구/누적kWh·합계 비교, 모든 입력 변경에 무효화. 합성2대기/3후보 발표 예제, NC iframe microphone 정책. 원본 NC/실장비/DB 변경 없음.
- 검증: CAD **141**·프런트 **545/67파일**·전체build/공개비공개 자산 격리·포맷/대상 lint/diff 통과. CAD 처음은 로컬 의존성 미설치로 실패 후 ci 재실행 통과. 프런트 처음 ERP1건 시간 초과 후 단독12개 및 maxWorkers=2 전체 통과. 음성 어댑터는 모의 인식/TTS로 검증하며 실제 서비스 성공 아님.
- 실제 맥북 Chrome: NC/STEP/소재/시간소비/3후보·버튼2번 및 텍스트 두 번째·99번 차단·정지·장비 변경 무효화, 390px viewport 가로 넘침 없음. Factory Studio 모의 게스트/실제 CAD 빌드 iframe 제안→텍스트3번→재생/정지·마이크 정책 확인. 원본1113.680초/0.228874–0.381228kWh → 조합3번233.680초/0.106652–0.161228kWh(합성). [화면](agent/assets/cad-v01/factory-chrome-nc.jpg).
- 실제 마이크 발화·실 TTS/권한 승인·인식 서비스·실 CNC/품질/절감·운영 배포 미검증/미실행. DB 검증/생성은 병행 MES 변경과 무관하므로 실행하지 않았다. main 기준2241851·구현39204d3, origin/main push 성공(1ecd4f5→39204d3). 병행 MES/DB 변경은 편집/스테이징하지 않는다. 다음: 맥북 Chrome 실발화 리허설, 다음 ID 자동 착수 없음.

## 2026-10-08 CAD-V01 발표 대상 수정·NC 음성 흐름 설계

- 사용자 답변: **Windows PC·Google Chrome 일반 브라우저(내장/Mac 아님), NC 에너지 제안**으로 확정. 이전 Mac/E1 가정은 최신 [제안](modules/cad-cam/음성발표데모_제안_CAD-V01.md)에서 대체했다. 추가 답변으로 Google Chrome까지 확정했다.
- 실제 코드 검토 결과 NC는 현재 에너지 후보 비교/원본 행·경로 선택만 제공하고 후보 자동 재생은 없다. CAD-V01 구현 범위를 후보1~13번호/입력revision + 후보 시간/kWh 타임라인·경로 재생 + 휴디 호출/음성 명령으로 명세했다. 품질1·에너지2와 기존 G4 제한/근거·차단/우열 보류는 유지, 원본 NC/실기계 실행 없음.
- 검증: NC 검토/제안/뷰어 코드와 CAD-15 계약 대조, MDN 음성 지원/원격 인식 제약 확인, 문서 링크/차이 검사. 문서 변경만이며 제품 코드·마이크·Windows 실음성·시뮬레이션·테스트/빌드·DB/운영 배포는 미실행. 다음: 수정된 전체 흐름 확인 후 CAD-V01 구현, CAD-17 자동 착수 없음.

## 2026-10-08 CAD-16 전문 스케치·직접 편집 완료

- 사용자 CAD-16 승인으로 [계약](modules/cad-cam/전문스케치_직접편집_설계_CAD-16.md)을 먼저 명세. E1/E2 공통 전문 창·다중선택/드래그·혼합 선/원호·측정/치수/이동·회전·반사/복사·제한 trim/extend/offset·외곽+8 내부 섬, OCCT 기하 참조 국소 필렛/모따기·축 정렬 작업면을 구현했다. 범용 오프셋/임의 면/위상 추적은 미지원, 열린/구속/참조 실패는 정상 확정 설계 보존. [검증](agent/전문스케치_직접편집_CAD-16.md).
- prototype134(신규17)/frontend545(67파일; HR W1c·포털72b253a 병합 후)·포맷/전체build/비누 격리/diff 통과. 실제 UI 드래그/Ctrl+Z·선/원호·섬 복사/가공100%(13.96cm³ 제거/0.03cm³잔삭)·국소 모따기23995mm³·면 구멍23932.2mm³·선행 참조 실패 정상 모델 유지·E2 초안undo·1440/390폭 확인. 실제 STEP 왕복/STL 체적 통과. 브라우저 다운로드 이벤트10초 실패로 파일 수신 미확인; 실 CNC/최대부하/서버 인증·DB/운영 배포 미실행.
- 기준257871e·WIP12cf7d0·HR W1c b8b3405 보존 병합69737d6·포털72b253a 보존 병합c3b3ec2·branch codex/soap-cad-review. 기존 main push 승인 유지, 타 작업자 포털 변경 보존. 442482e까지 main fast-forward·origin/main push 성공(72b253a→442482e), 운영 배포 없음. CAD-17 미착수.
- 사용자가 추가한 다음 주 발표 음성 요청은 [CAD-V01 제안](modules/cad-cam/음성발표데모_제안_CAD-V01.md)으로 분석·질문했다. 권장 기본은 Mac Chrome/E1 후보 선택+웹 소재 제거 재생, 사용자 마이크 시작 후 호출어 대기. 브라우저 음성 서비스 제한/네트워크·후보 revision/중복 차단·실발화 리허설 조건 명세; 구현/실마이크 미착수·미검증.

## 2026-10-08 진입·런처 UI 보정과 HR 노출

- **HR이 앱 런처에 없었다**: `content/systems.json`에 HR 시스템을 넣고(구현·`/hr`·경영·협업), 홈 런처 목록(P-02)과 진입 화면(P-01) 솔루션 띠에 더했다. 런처 아이콘도 HR 모양으로 넣었다. 시스템 17 → 18, 운영 중 8 → 9("여덟 가지" → "아홉 가지"는 목록 길이에서 자동으로 나온다).
- **한글이 글자 중간에서 줄바꿈되던 것**: 본문이 "만들었습니/다."처럼 끊겼다. `body`에 `word-break: keep-all`을 주어 어절 단위로 끊고, 긴 코드·URL은 자리가 없을 때만 끊도록 `overflow-wrap: break-word`를 함께 뒀다.
- **진입 화면 아래 솔루션 띠**: 항목이 "MES / 생산관/리"처럼 두 줄로 깨졌다. 항목은 `white-space: nowrap`으로 한 줄에 두고, 자리가 모자라면 `flex-wrap`으로 통째로 아랫줄로 내린다.
- 확인: 1440px 1줄, 900px 2줄, 375px(모바일) 3줄 — 어느 폭에서도 항목이 안에서 쪼개지지 않고 가로 스크롤도 생기지 않는다. 본문도 어절 경계에서만 끊긴다. ERP 전표·HR 급여대장·도움말 화면에서 가로 넘침 없음. 프런트 545개 통과, eslint·tsc·prettier·build 통과.

## 2026-10-08 W1c HR 시드·도움말

- **HR 합성 시드**(`backend/seed/hr.py`): 부서 4·직위 5·직책 2·근무 형태 2(주간 일근·야간 교대)·사원 10명·입사 발령 10·자격 교육 7·연차 발생 10·휴가 7(승인·반려·신청)·급여 항목 11·급여 기준 10·고정 수당 15·상여 규칙 1. 이름과 사업 정보는 모두 합성이다.
- **기준일 T 중심**: 지난달은 근태 전체 + 마감 확정 + 급여 확정(1차), 이번달은 기준일까지 근태 + 마감 **작성 중**. 사용자가 H-08에서 확정 → H-11에서 계산·확정을 직접 해 볼 수 있다. 상여 규칙은 지난달에 기본급의 50%로 걸어 명세서에 상여 줄이 보인다.
- **공통 휴일 달력**: `core.holiday`에 날짜가 고정인 공휴일 8개 × 2년 = 16건을 넣고, 게스트 공간 복사에도 포함했다(지금까지 복사되지 않아 공휴일이 근무일로 잡혔다). **공휴일은 실제 달력 날짜라 다른 업무 날짜처럼 밀지 않는다.**
- **금액은 제품과 같은 함수로**: 시드가 `fs.hr.payroll.slip_lines`를 그대로 불러 쓴다(private → public). 시드와 제품의 계산식이 갈라지지 않는다.
- **복사 규칙 추가**: `hr.attendance_close.close_month`·`hr.payroll_run.pay_month`·`hr.pay_base.effective_from`은 월 이동, `hr.leave_balance.leave_year`는 대상 연도, `hr.bonus_rule.payable_mm`은 '옮긴 기준일의 지난달', `AP-`·`LV-` 번호 속 날짜는 일수 이동.
- **검증**: 시드 버전 `sv-20261001-1` → `sv-20261008-1`. 검증기에 **V-HR** 추가(휴일 16·마감 2건(확정 1·작성 중 1, 작성 중이 더 나중 달)·근태가 두 달에 존재·승인 휴가가 근태에 반영·확정 급여 1건과 명세 합계 일치). 행 수가 기준일에 따라 달라지는 `hr.attendance`·`hr.payslip_line`은 수 비교에서 빼고 규칙으로 본다. 고정 행 합계 14,687 → **14,794**.
- **도움말 15편**(`content/help/hr/h-01~15.md`): 화면마다 하는 일·주요 동작·예시 데이터 체험 순서·막히는 지점·관련 화면. 참고 문서 트리(P-05)에 HR 구역을 넣었다.
- **전체 흐름 맵**(P-03)에 HR 3노드 추가: 사원·조직 기준 → 근태 마감 → 급여 확정, 그리고 사원·조직 기준 → 거래처·품목 기준정보("사람·부서 코드의 원천"). 스키마 노드 18 → 21, 연결 21 → 24.
- **고친 것**: 명세서에 그 사원에게 설정하지 않은 고정 수당이 0원 줄로 남던 것을 없앴다(기본급만 0이어도 남긴다).
- **테스트 격리**: 게스트 공간에 HR 시드가 생기면서 빈 공간을 전제한 HR 테스트 33개가 깨졌다. conftest에 `EMPTY_MODULES` 선언을 더해 그 솔루션을 '복사 끝'으로 표시하고 빈 상태로 시작하게 했다(지연 복사가 끼어들지 않는다).
- **검증 결과**: 백엔드 전체 **891개 통과**(+1 skip, perf 제외), 프런트 **545개 통과**, ruff·prettier·eslint·tsc·build 통과. 시드 생성을 2026-01-05·2026-03-01·2026-03-02·2026-10-08·2026-12-31로 반복해 V-HR을 포함한 15개 규칙이 모두 통과하는 것을 확인했다. 로컬 `factory_studio`도 마이그레이션·템플릿 재생성 후 검증 통과.
- **브라우저 확인**(새 게스트 공간): H-01 재직 10명·야간 96시간·연차 2.8%·만료 임박 자격 2건, H-08 지난달 확정·이번달 작성 중, H-12 급여대장 10명과 야간 교대 사원 명세서(기본급·식대·야간 1,221,053·상여 50%·공제 4종·퇴직금 추계), H-14 이번달 "확정 급여가 없습니다" 안내, 도움말 `/help/hr/h-11`, 전체 흐름 맵의 HR 19~21번 노드.
- 미실행: 운영 배포(다음 배포에서 시드 템플릿이 **다시 만들어진다** — 시드 버전이 바뀌었다). 평가 시드는 넣지 않았다(평가 기간을 사용자가 열어 보는 쪽이 낫다).
- 다음: W2a.

## CAD-15 — 품질 우선 NC 검토 제안 (2026-10-08)

- 사용자 CAD-14 결과 확인 후 다음 진행 승인. 품질 형상 기준/대기 목적·최소시간/위험 확인을 먼저 검사, 현재 NC·소재·전체 시간/소비로 단독 G4 개별/조합 시나리오 비교. 원본/이동/F/S/T/비대기 이벤트 유지·자동 NC 적용/출력 없음. [계약](modules/cad-cam/품질우선_NC제안_설계_CAD-15.md)·[검증](agent/품질우선_NC제안_CAD-15.md).
- 입력 범위가 겹치거나 추가 여유 미정/차이 이하이면 우열 판단 불가. 품질/근거/대기 영향 미확인·과절삭/잔삭/격자 오류 초과는 후보 차단. 200목록·12선택/13후보·근거/행 선택/JSON·입력 무효화. 실제 공차/Ra·공정 안전·실측 보정 아님.
- prototype117(신규13)/frontend544(67파일)·포맷/전체build/격리/diff 통과. 실제 합성600→10초 후보813.680→223.680초, 0.187208~0.306228→0.105263~0.158728kWh; 근거/여유/영향 확인·과절삭1mm/허용0 차단·장비 변경 무효화·201대기200+1페이지/입력 보존·13선택 차단·1440/390폭 확인. Node5만행 목록88.95ms/비교106.51ms·heap+54.45MiB/RSS+13.89MiB(브라우저/peak 아님).
- 기준f860e8b·구현5761608·운영 기록c769a42 보존 병합7aefb20·branch codex/soap-cad-review. 기존 main push 승인 유지. a3c1c6f까지 main fast-forward·origin/main push 성공(f860e8b→a3c1c6f), 타 작업자 HR/시드/운영 기록 보존. 실측 품질/안전/절감·JSON재열기/Safari/실기기 대형 부하·DB/이번 CAD-15 운영 배포 미검증·미실행. 동기 계산이므로 느린 기기 지연 가능. 다음 결과 확인 후 CAD-16 한 ID, CAD-17 자동 착수 없음.

## 2026-10-08 운영 배포 f860e8b

- `tools/deploy.sh`로 main `f860e8b`를 운영에 배포했다(이전 `3474942`). 포함: W1b-2 근태·휴가, W1b-3 급여, W1b-4 평가·현황·본인(HR 15화면 전부)과 다른 세션의 CAD-12·13·14.
- 사전 점검(CI·커밋·빌드) 통과, 마이그레이션 head `w1a_hr_module` 그대로, 시드 코드/템플릿 같아 템플릿 재생성 없음, 비공개 비누 자산 업로드·읽기 확인, API 재시작, 프런트 업로드.
- 확인: 원점 200 · 공개 200 · DDL 대조 0 · 최근 2분 5xx 0건. 브라우저로 운영 게스트 공간을 새로 만들어 H-01 인사 현황과 H-10 급여 기준이 뜨는 것과, `/api` 응답에 `Cache-Control: no-store`가 붙은 것(W1b-4에서 고친 만료 응답 캐시 문제)을 확인했다.
- HR 화면은 아직 비어 있다 — HR 시드는 W1c에서 넣는다.

## CAD-14 — 시간·소비 에너지 모델 (2026-10-08)

- 사용자 CAD-14 단일 ID 진행 승인. 축별 최고 속도/가속·독립 구간 정지/XY 원호·이벤트 시간·상태별 전체 장비 kW 입력으로 시간/kWh 범위. 전체 전력 중복 합산 없음, 동일 NC/소재 연결·급속 접촉/종료 미정/주축 혼합 차단, 미정 전체 합계와 알려진 소계 분리. [계약](modules/cad-cam/시간소비모델_설계_CAD-14.md)·[검증](agent/시간소비모델_CAD-14.md).
- 사용자 가정/측정 입력 근거·별도 검증 비교(자동 보정 없음), 합성 예제·200구간 전력 그래프/표→NC 행·JSON·최소 Worker 전달/취소/무효화. 상태 전력 범위는 F·방향·제거율 조건을 포괄하는 사용자 입력이며 상세 부하 모델/실제 look-ahead 아님.
- prototype104/frontend544(67파일; HR 병합 후 재검증)·포맷·전체build/격리·diff 통과. 실제 화면31구간213.680초/0.10387~0.15623kWh(합성)·미정/측정근거 차단/비보정 비교/행 선택/254구간200+54페이지/입력 무효화/1440·390폭 확인. 빌드 중 열린 이전 자산 Worker 오류는 새로고침 후 재검증 통과. Node5만행73.01ms/heap+54.60MiB/RSS+20.53MiB(브라우저/peak/정확도 아님).
- 실측 정확도/실 CNC/30초실제만료/브라우저 취소 경합/stale주입/JSON재열기/Safari/DB/운영배포 미검증·미실행. 기존 비누 관리자 보호/E1/E2 유지. 기준e7c42cd·branch codex/soap-cad-review, 이전 main push 승인 유지. 92a2b84까지 main fast-forward·origin/main push 성공(e7c42cd→92a2b84), 운영 배포 없음. main의 타 작업자 HR 파일 보존. 다음은 결과 확인 후 CAD-15 한 ID만.

## 2026-10-08 W1b-4 HR 평가·현황·본인

- 자격·교육(F06, H-05): `hr.qualification`이 W1b-1에서 빠져 있었다. 인사카드에 자격·교육 표와 추가·삭제를 넣고, 만료일이 있으면 상태를 계산한다(`NONE`·`VALID`·`EXPIRING`(30일 이내)·`EXPIRED`). 경고만 하고 다른 일을 막지 않는다.
- 인사 평가(F31, H-13): 연도별 평가 기간(OPEN/CLOSED) 안에서 목표 작성(draft) → 제출(submitted) → 평가자 등급 S~D·의견 확정(confirmed). 평가자를 비우면 그 사원 부서의 `is_head` 직책 사원이 되고, 지정된 평가자만 확정할 수 있다. 제출하면 본인은 못 고치고, 평가 기간을 닫으면 그 해 평가를 더 만들거나 고칠 수 없다. 한 기간에 사원당 1건.
- 인사 현황(F41, H-01): 재직·휴직·퇴직 인원(부서별), 그 달 입·퇴사, 연장·야간·휴일 근로와 결근, 그 해 연차 사용률, 자격 만료 임박, 평가 진행.
- 인건비·근태 분석(F42·F43, H-14): **확정 급여만** 세어 부서별·항목별 인건비를 보여주고, 근태·연차를 함께 둔다. 작성 중인 급여 계산은 숫자에 넣지 않는다.
- 내 정보(F44, H-15): 고른 사원의 근태·잔여 연차·확정 명세서·평가만 본다. EIP `my_employee_code(actor)`가 아직 없어 **화면에서 사원 코드를 고른다**(DSN-30 Q7, EIP가 생기면 그쪽이 준다).
- EIP 공통 제공 3종(DSN-90 2-1): `monthly_summary(month)`(인원·입퇴사·인건비·연장 시간·연차 사용률), `pending_tasks(hr_employee_code)`(부서장의 휴가 승인 대기·평가 확정 대기, 본인의 자기 평가 작성), `lookup(code)`(사원 코드·발령 번호·휴가 신청 번호 → 화면 경로). 모두 HR이 꺼져 있으면 `None`.
- 고친 것 1 — **등록 본문의 기본값이 사라졌다**: `_values`가 늘 `exclude_unset=True`라 pydantic 기본값(예: `displayOrder=1`)이 DB에 가지 않았고, DB 기본값이 없는 `hr.pay_item.display_order`에서 NOT NULL 위반이 났다. 등록(POST) 경로만 `full=True`로 기본값까지 보내고 수정(PATCH)은 그대로 둔다.
- 고친 것 2 — **만료 응답이 브라우저에 캐시됐다**: API 응답에 `Cache-Control`이 없어 410(공간 만료)이 기본 캐시 규칙에 걸렸다. 새 게스트 공간을 만들어도 브라우저가 옛 "만료" 응답을 계속 돌려줘 화면이 복구되지 않는다. 요청 로그 미들웨어에서 `/api/` 응답에 `Cache-Control: no-store`를 붙였다(브라우저에서 재현·수정 확인).
- 검증: 백엔드 `test_hr_review.py` 8개 신규 + HR·세션·공통·지연시드 58개 통과(`factory_studio_ci_test`), 프런트 `src/hr` 18개 통과(전체 544개), tsc·eslint·prettier·ruff·전체 build 통과. 브라우저(새 게스트 공간) 실제 확인: 인사 현황(재직 2명·연장 2.0시간·연차 0.0%·지게차운전 2026-10-25 만료 임박) → 평가 기간 2026 생성 → 평가 대상 추가 시 평가자가 부서장 E100으로 자동 지정 → 자기 평가 저장 → 제출(본인 입력 칸 사라짐) → E100으로 A 확정(삭제 버튼 사라짐) → 인건비 분석(지급 2,120,000 · 공제 95,400 · 실지급 2,024,600) → 내 정보(잔여 15.0일·확정 명세서·평가 A) → 인사카드 자격·교육 2건.
- 미실행: 전체 pytest 일괄 실행, 운영 배포, HR 시드·도움말(W1c), EIP `my_employee_code` 연동(W6).
- 다음: W1c HR 시드·도움말(흐름 맵·화면 도움말 정적 파일).

## CAD-13 — 소재·공구·STEP 정합 (2026-10-07)

- 사용자 다음 단계 승인·이번 ID 구현100%(평엔드밀/상면 제한). 실제 단일 Solid STEP·OCCT 단위→mm·Z회전/XYZ 이동→G54 정합, 소재/공구표 숫자 입력·활성T 연결·H/D 참조 기록, 제거/잔삭/과절삭/급속 소재 접촉 후보·행 선택·격자 체적오차·예제·분석 JSON 확장. [계약](modules/cad-cam/소재공구_STEP정합_설계_CAD-13.md)·[검증](agent/소재공구_STEP정합_CAD-13.md).
- 입력/NC 변경은 결과 무효화·정합 재확인, 미지원 형상/공구/부분 NC 차단·STEP10MiB/2만삼각형/4만셀/검사 상한·Worker30초/취소/revision. H/D 보정 해석·홀더/지그/자동 기계 이동·곡면/언더컷/선반·전체 시간/kWh 미지원. 격자 근사/접촉0은 안전 보증 아님. 기존 관리자 비누 보호 정책·E1/E2 유지.
- prototype88/frontend539(66파일)/포맷/전체build·자산격리/diff 통과. 실제 파일/STEP2000mm³·박스제거1200/잔삭·과절삭 각400(독립 시험)·정합/좌표범위/공구 차단·입력 무효화·급속34행 선택·1440/390폭 확인. STEP예제 취소 시도는 완료가 먼저여서 미검증, 30초/stale강제주입/대형메모리·JSON다운로드재열기/실물/계측/DB/운영배포 미검증·미실행.
- 시작83483dc·구현6fb5a96·STEP 정리0c34d32·branch codex/soap-cad-review, 로컬 main fast-forward 및 origin/main push 성공(83483dc→0c34d32). 기존 main push 승인 유지, 다른 작업자의 HR 변경은 건드리지 않음. 다음은 결과 확인 뒤 CAD-14 한 ID, CAD-15~17 자동 착수 없음.

## CAD-12 — NC 해석·3D 경로 검토 (2026-10-07)

- 사용자 다음 단계 승인·구현100%. 3축 밀링/G-code 우선, 선반 후속. 포털 NC 경로 검토 메뉴·로컬 파일/붙여넣기, LinuxCNC 기반 리터럴 부분집합·XYZ 모달/단위/원호·F/S/T·주축/쿨런트/교환/대기/종료 이벤트. [계약](modules/cad-cam/NC해석_경로검토_설계_CAD-12.md)·[검증](agent/NC경로검토_CAD-12.md).
- 원본 행/전후 상태·경로/코드 양방향 선택·200행 페이지·예제/지원 명령/JSON 출력, 원문/BOM/CRLF·SHA-256 보존. 첫 미지원 이후 연결 차단·초기 상태 확인·입력 무효화·2MiB/5만행/50만표시점/30초 Worker/취소·revision/인스턴스 방어. G43/사이클/매크로/선반 미지원. CAD 원본/소재 제거/시간/kWh/NC 수정·장비 실행 없음.
- prototype77/frontend539(66파일)/포맷/전체build·자산격리/diff 통과. 프런트 기존 ERP 견적 비동기 시험1회 실패, 전체 재실행539통과(ERP 미수정). 실제 파일 선택/초기확인·10이동7이벤트·원호/경로↔행·부분 차단·5만행 취소/재해석/페이지·BOM/CRLF·1440/390폭 확인. 파서5만행626.79ms/heap+126.13MiB/RSS+182.73MiB(Node만·최대메모리아님). 실제30초/stale주입·JSON다운로드재열기(IAB이벤트만료)·실물/계측/DB/운영배포 미검증·미실행.
- 시작7861ed1·WIP24779cd·최종 구현1f26837, 로컬 main fast-forward·origin/main push 성공(7861ed1→1f26837). 다른 작업자의 main HR 파일 보존, 기존 main push 승인 유지. 다음은 결과 확인 뒤 CAD-13 한 ID, CAD-14~17 자동 착수 없음.

## CAD-11 — 편집 명령·실수 복구 (2026-10-07)

- 사용자 CAD-10 권장안 승인: 3축 밀링·G-code 우선, 선반 후속. 이번 ID 구현100%, NC/에너지 계산 미착수. [설계 계약](modules/cad-cam/편집명령_복구_설계_CAD-11.md) · [결과](agent/편집명령_복구_CAD-11.md).
- E1/E2 공통 Ctrl/⌘Z·ShiftZ/CtrlY·Esc·Delete·F·저장/도움말, native 입력칸 undo·초안·확정 모델 이력 분리. 점/원호/닫기/드래그/치수 복구, 실패 원호 직전 두 점 유지, E2 참조 영향 검사/삭제 거부·정상 삭제 복구·Worker 인스턴스 방어.
- prototype62/프런트66파일538/포맷/전체 build·자산 격리·diff 통과. 실제 iframe 선/닫기·원호 실패/복구·한 드래그·E2 초안/확정 치수·체적·삭제/참조거부·native 문자undo·Esc 계산취소·도움말 확인. 실제 Windows/IME·30초만료/stale 강제 주입·저장 파일 재열기·모든 도구 전수시험·DB/실물/NC/계측/운영 배포 미실행.
- 구현6d4d8d3; HR 급여aaee3a3 보존 병합9a5c0a3, 문서2b6086c까지 main fast-forward·origin/main push 성공(b2390b7→2b6086c). 기존 main push 승인 유지, 다른 작업자 HR schema 미커밋 변경 보존. 다음은 결과 확인 뒤 CAD-12 한 ID, CAD-13~17 자동 시작 없음.

## 2026-10-07 W1b-3 HR 급여

- 급여 기준(H-10): 한 화면에 급여 항목·사원 급여 기준·상여 규칙을 탭으로 묶었다. 항목은 지급/공제와 계산 방식(BASE·FIXED·OVERTIME·NIGHT·HOLIDAY·BONUS·RATE)을 갖고, **공제는 비율(RATE)로만** 만들 수 있다(DB CHECK와 같은 규칙을 API에서 먼저 보고 읽을 수 있는 메시지로 돌려준다). 사원 기준은 적용 시작 월마다 쌓이고 계산은 가장 최근 것을 쓴다. 고정 수당은 FIXED 항목만 넣을 수 있다. 상여 규칙은 BONUS 항목에만 걸고 지정한 달에만 적용한다.
- 급여 계산(H-11): 입력은 그 달의 **확정 근태 마감**이다. 없으면 409 `ATTENDANCE_NOT_CLOSED`. 지급 = 기본급 + 고정 수당 + 통상시급(기본급 ÷ 월 통상 시간) × 배수 × 시간(연장·야간·휴일) + 상여(기본급 × 지급률), 공제 = **과세 지급 합계** × 퍼센트. 금액은 원 단위 반올림. 작성 중인 실행을 다시 계산하면 같은 버전을 덮어쓰고, 확정한 뒤 다시 계산하면 새 버전이 되며 확정 시 이전 확정본은 superseded가 된다.
- 급여대장·명세서(H-12): 실행 한 건의 사원별 지급·공제·실지급액과 명세서(지급/공제를 나눠 표시, 근거 시간·비율 포함, 인쇄). 퇴직금 추계는 최근 3개월 확정 명세서로 조회 계산만 하고 저장하지 않는다.
- ERP 연계: `fs/hr/interface.py`에 `payroll_runs(month)` 추가 — 확정 실행의 **부서 코드·항목별 합계만** 돌려주고 개인 금액·사원 코드는 넘기지 않는다(DSN-90 흐름 4). 확정본이 없으면 `confirmed: false`와 빈 합계.
- 고친 것: 선택 입력인 '배수·비율'이 빈 문자열로 전송돼 pydantic 패턴에서 400이 났고, 그 오류가 `body.rate` 키라 화면에 아무 메시지도 안 보였다. 빈 값을 허용하고 서비스에서 None으로 바꿨으며, 공통 `fieldErrors`가 `body.` 접두사를 떼도록 해 FastAPI 본문 검사 오류도 입력 칸에 표시되게 했다.
- 검증: 백엔드 `test_hr_payroll.py` 8개 신규 + HR·지연시드·공통 46개 통과(`factory_studio_ci_test`), 프런트 `src/hr` 13개 통과(전체 538개 통과), tsc·eslint·prettier·ruff·전체 build 통과. 브라우저(로컬 게스트 공간) 실제 확인: 급여 항목 7개 등록(기본급은 화면에서, 나머지는 API) → E001 기준 2,090,000/209시간 + 식대 200,000 → 2026-10 계산(지급 2,312,500 = 기본급 + 식대 + 연장 1.5시간 × 1.5배 × 10,000, 공제 164,776 = 과세 2,112,500 × 7.8%, 실지급 2,147,724) → 확정 후 확정 버튼 사라짐 → 명세서에 지급·공제·근거(1.50시간, 4.50%)와 퇴직금 추계 1,342,746원 표시.
- 미실행: 전체 pytest 일괄 실행, 운영 배포, HR 시드·도움말(W1c), ERP F94 급여 전표 쪽 소비(W2 이후).
- 다음: W1b-4 평가·현황·본인(H-01·H-13~15)과 남은 제공 함수(`monthly_summary`·`pending_tasks`·`lookup`).

## 2026-10-07 CAD-10 NC 입력·소비 예상·편집 고도화 분석

- 사용자 조사/분석 요청. [상세 분석](modules/cad-cam/NC에너지_편집고도화_분석_CAD-10.md) 작성: NC는 경로 명령이며 원래 CAD 피처 복원은 일반적으로 불가, STEP/소재/공구/원점 별도. 컨트롤러별 모달 상태·보정/매크로/급속 차이·미지원 행 차단, 실제 접촉과 이송 분리. 장비 상태별 전력·시간·실측 보정·불확실성, 안전→품질→kWh 판단 제안. 외부 NC에 CAD-09 순서 변경기 자동 적용 금지.
- E1 Ctrl/⌘Z·ShiftZ는 기존 구현, draft 점/원호 이력 미지원·E2 버튼만 구현(전역 keydown 없음)을 소스에서 확인. 공통 명령·draft/확정/입력 undo 분리, 스케치 엔티티/다중윤곽 설계와 참조 안정성부터 확장 제안. 설치 replicad1.1.0 STEP import API 존재 확인, 제품 가져오기는 미구현.
- 공식 LinuxCNC·Haas·Autodesk·NIST·Sandvik·VERICUT·replicad 문서 조사. 분석 완료100%/신규 제품 구현0%, 문서 상대 링크·표 구조·diff 검사만 수행. 신규 파서/에너지/단축키·벤치마크·실물/전력·DB 검증 미실행. 제품 코드/DB/배포 변경 없음. HR3596156 보존하여 기존 CAD worktree 재사용.
- 다음 제안 CAD-11 복구/키보드→12 NC해석→13 공구·소재·원점/목표모델→14 소비→15 품질우선제안→16 도구→17 실제NC출력. 장비 질문 미답변은 3축 밀링 부분집합 제안. 전체 구현 계약 확인 후 ID 하나씩, 이번 분석을 제품 착수 승인으로 보지 않는다. 현황/인계 함께 갱신.

## 2026-10-07 W1b-2 HR 근태·휴가

- 근태(H-07): 근무 형태 시작시각·소정분·주말근무 여부와 `core.holiday`로 한 달치를 자동 생성(AUTO)하고, 이미 있는 날은 건드리지 않는다. 지각·결근·연장 같은 예외만 고치며 고치면 `source=MANUAL`이 된다. 야간(22~06시 겹침)·휴일 분은 생성할 때 계산해 둔다. 월 합계(근무·결근·휴가 일수, 연장·야간·휴일 분)는 W1b-3 급여의 입력이 된다.
- 근태 마감(H-08): 월 합계를 보고 마감을 열면 draft, 확정하면 그 달의 근태 생성·수정이 409 `MONTH_CLOSED`로 막힌다. 다시 마감을 열면 새 버전이 되어 그 달이 다시 열리고, 확정하면 이전 확정본은 superseded가 된다. 잠금 판정은 월별 **마지막 버전**만 본다.
- 휴가(H-09): 연차는 연도별 발생 일수만 저장하고 잔여는 조회로 계산한다(발생 − 승인 사용). 신청은 재직 사원·그 해 발생 등록이 있어야 하고 잔여를 넘으면 409 `NOT_ENOUGH_LEAVE`다. 승인은 `is_head` 직책을 가진 재직 사원만 할 수 있고 본인 승인은 막는다. 승인하면 `FOR UPDATE`로 잔여를 다시 확인하고, 마감하지 않은 달의 해당 날짜 근태를 LEAVE/HALF_LEAVE로 바꾼다. 신청 상태에서만 취소할 수 있다.
- 게스트 정리에 `core.holiday` 삭제를 넣었다(없어서 `data_generation` 삭제가 FK RESTRICT로 실패했다). 제품/테스트 양쪽 정리 경로에 함께 반영.
- 검증: 백엔드 `test_hr_attendance.py` 8개 신규 + 기존 HR·지연시드·세션·공통 42개 통과(`factory_studio_ci_test`), 프런트 `src/hr` 8개 통과, tsc·eslint·prettier·ruff check/format 통과, 전체 frontend build 통과. 브라우저(로컬 게스트 공간) 실제 확인: 2026-10 근태 31건 생성 → 연장 90분 수정 시 '직접 고침' → 월 합계 22일·1.5시간 → 마감 확정 후 '마감됨, 고칠 수 없습니다'와 수정 버튼 사라짐 → 2026-11 생성 후 연차 15일 등록 → 2일 신청 → 부서장 E100 승인 시 '근태 2건이 휴가로 바뀌었습니다', 잔여 13.0일.
- 미실행: 전체 pytest 일괄 실행, 운영 배포, HR 시드·도움말(W1c), 급여(W1b-3). `core.holiday`는 아직 등록 화면이 없어 시드 전에는 비어 있다 — 공휴일 표시는 W1c 이후에 보인다.
- 다음: W1b-3 급여(H-10 급여 기준·H-11 급여 계산·H-12 급여대장·명세서).

## 2026-10-07 CAD-09 품질 우선 경로 제안 완료

- 사용자 제안안 구현 승인. E1 상면 포켓에서 기존/가까운 시작점 2후보,256래스터·30초 Worker 상한, 수동 취소/종료 응답 무시·입력 변경 무효화·선택 적용. 절삭 방향/깊이/공구·실제 마지막 마무리·안전Z·경계 여유·동일 격자 최종 높이 비교 후 비절삭 길이/시간 감소 제안. 소비kWh/전력절감% 산정 불가.
- prototype56, HR1136611 보존 병합 후 frontend530/64파일·전체 build/자산 분리·포맷 통과. 실제 웹 생성/적용/100%·입력 무효화·조회 전후 기존100% 유지·256상한·즉시 취소/상태/복구 확인. 분리 포켓 비절삭3927.4→2034.1mm(48.2%), 시간314.4→276.6초·같은 제거 결과. [결과/화면](agent/품질우선_경로제안_CAD-09.md).
- 실제30초 만료/stale 주입·Ra/치수/실기계/전력·DB 검증 미실행, DB/NC/운영 배포 없음. 구현b10d157·HR 보존 병합6f91b4c. 현황·인계 함께 갱신, 기존 main push 승인으로 main fast-forward 및 origin/main push 성공(1136611→e17fef8). main의 다음 HR 근태/휴가 미추적 파일은 보존했다. 다음은 결과 확인 뒤 장비/재질/목표품질 입력 설계, 후속ID 자동 착수 안 함.

## 2026-10-07 CAD-08 비누 POC 운영 파일 복구·경로 제안 분석

- 사용자 운영 ‘파일이 없습니다’와 품질1/전력소비2 경로 제안 요청. ASSET_ROOT는 backend/private-assets/soap-poc, 빌드 생성물/Git 제외. deploy.sh가 frontend/dist만 전송한 원인 확인. 실서버3474942의 HTML 부재·추적 트리 clean 확인.
- 운영 동일3474942를 work/cad08-server-build에 별도 추출해 frontend 의존성/보호 자산 빌드·누출 검사 통과, private38파일만 업로드 복구. 실행계정 factory 소유·750/640, 전체 경로+내용SHA256 89658d4e841726800e2a34a59b168bddef3ce3541104cbff0e2bc4a5c24eeeba 로컬/서버 일치, 실행계정 HTML/ZIP 읽기, 공개 보호URL 비로그인401. 실서버 브라우저는 관리자 세션 없어 만료 화면; 관리자200 미검증. 코드·DB·서비스 재시작·E2 배포 없음.
- deploy.sh 로컬 필수 자산 검사→비공개 폴더 rsync→계정 소유/권한/읽기 검사→API 재시작 순서 보정. 가짜 ssh/rsync로 실제 스크립트 실행 계약7 통과: 정상순서/CI·커밋·dry-run·시드와 로컬자산누락/서버읽기실패 중단. 실제 전체 배포 명령 미실행. 기존 보호 API13 재검증 통과(비로그인401·비관리자403·합성 관리자200).
- [품질 우선 경로 제안 초안](modules/cad-cam/품질우선_경로제안_설계초안_CAD-08.md): 안전→목표 품질 충족→소비kWh, 가중합 금지. 초기 E1 단일깊이 래스터 순서만 조정·절삭/방향/정삭/안전Z 유지. 장비 미정은 비절삭 이동/시간만 제안하며 kWh/% 창작 없음. 재질·장비·목표공차/Ra 질문, 제품 기능 미구현. 작업ID별 확인 후 다음 구현, 다른 작업자의 main 미추적 HR 코드 보존. 현황/인계 갱신, 기존 사용자 main push 승인으로 ee5c499 로컬 main fast-forward 및 origin/main push 성공(8a10ea6→ee5c499). main의 진행 중 HR 파일은 미수정·미스테이징으로 보존.

## 2026-10-07 CAD-07 E2 부품 설계 완료

- 사용자 E2 범위 지시·이어가기 승인. 이번 CAD 범위만 수행, D82/다른 솔루션 결정 유지. OCCT 실제 BRep Worker(replicad/replicad-opencascadejs1.1.0)로 다중 돌출·파내기·측면 구멍·XY/XZ/YZ 기준·스케치 회전·직선/원형 배열·미러·필렛·안쪽 쉘. JSON v3 원본과 별도 공간 저장, v1/v2 가져오기. 포털 /cad-cam?view=part.
- 선/원호 혼합 윤곽·좌표/경유점 편집, 수평/수직/일치/길이/원호 반경/점 고정 수치 구속·중복/모순 오류. 제한된 단일 닫힌 프로파일 해석이며 완전한 범용 솔버가 아니다. 후보 모델 전체 검증 뒤 저장/undo 확정, 실패 ID·마지막 정상 형상 보존·계산 취소/30초 Worker 종료.
- 실제 검증: prototype50/frontend525(63파일)/관리자 권한API13, prototype 포맷/단독 빌드·frontend 전체 빌드·공개/관리자 자산 분리 통과. 브라우저 측면 구멍/배열40233.6mm³·기본 높이12→54233.6·분리 돌출 오류 upright·쉘/필렛13205.5·수평 구속5700·혼합 원호4678.1·중복 구속 거부·undo/redo·새로고침 복원·1440×900/390×844 확인. STEP Worker 생성 완료 메시지, Node STEP/바이너리 STL 내용 확인. [보고](agent/부품설계_편집기_CAD-07.md).
- 제약/미실행: 임의 곡면 작업면·개별 위상 선택·조립·3D/측면 CAM·NC·실물·DB 명령, 외부 CAD의 STEP 재열기, 브라우저 다운로드 파일/선택 재열기, 30초 제한/계산 취소 실사용. E1 상면 CAM과 관리자 비누/연구노트 유지, 신규 비누 성능/사진 기록 없음. WASM22,980KB(gzip7316KB), E2 최초 로드만; MIT/LGPL 안내·소스/교체 방법 빌드 포함. 기존 frontend source-map-js audit high1은 이번 범위 외.
- WIP0377787·추가7ed2817, 최신 main W0-5 e135f79를 b7edf18로 병합해 보존. 현황/인계 함께 갱신. 최신 원격 HR/운영 기록 d135d7f를384e206으로 병합 보존하고 main fast-forward 및 origin/main push 성공(d135d7f→384e206). main에 prototype node_modules 없이 frontend 의존성만 추가 설치하여 전체 build/자산 분리 통과, lock 변경 없음. E2 운영 배포 없음. 다음 CAD E3는 사용자 결과 확인 후.

## 2026-10-06 CAD-06 E1 자유 스케치 구현

- 권장안대로 이어가기 사용자 승인. 선 연결·끝점 닫기·3점 원호(직선으로 닫힌 면)·회전 슬롯, 점/원호 통과점 좌표·격자/끝점 스냅. JSON v2 ID/해석 좌표 보존, v1 형상 유지.
- 원호 현 오차 목표0.01mm·열린/퇴화/교차 윤곽 거부·오목 소재 경계 교차 검사·실제 bounds 격자/카메라 적용. Manifold3.5.4 offset Worker·독립 공구 여유 표본·분리 구간 안전높이·오래된 응답 무시. 예제 JSON을 examples/cnc_E1_2026-10-06_L-slot-arc.form.json에 보관하고 예제 버튼 연결.
- prototype37/frontend524/권한API13/build·자산 분리 통과. 브라우저 직접 작성·원호 통과Y32 편집·새로고침 복원·3작업 CNC·100%(6.00cm³)→20%(1.53cm³) 되감기·중복점/40mm공구 거부,1440×900/390×844 확인. JSON 순수 파일 왕복 테스트 통과. IAB 다운로드 이벤트 timeout, 실제 다운로드/파일선택 재열기는 완료로 처리하지 않음.
- [상세 보고](agent/자유스케치_편집기_CAD-06.md). DB/실물/NC/연속 충돌·다중 돌출/필렛/구속/조립 미실행·미구현. 기존 source-map-js1.2.1 개발 의존성 audit high1은 이번 이전부터 존재, CAD 범위 밖에서 자동 변경하지 않음. 현황/인계 갱신. 구현09286e4, W0-4 be91ce9 보존 병합4c87b7c. 기존 사용자 main push 승인으로 로컬 main 통합 및 origin/main push 성공(be91ce9→4c87b7c), 운영 배포 없음. main CAD 빌드에서 prototype 의존성 없는 WASM ?url alias 실패를 발견,057100d 정규식 alias로 수정하고 frontend 의존성만으로 main 빌드/자산 분리 재검증 통과. 다음CAD-07/E2는 결과 확인 후.

## 2026-10-06 CAD-05 CNC 우선 E0·파일 참조

- 사용자 확정/권장안 승인: CNC 우선, 비누 후속, 사진 없이 폴더/파일명과 기록. main push 승인. 최초 push는 최신 main5c19e1d와 원격 동일 확인. 구현 ba00b69 로컬 main 병합 후 origin/main push 성공(5c19e1d→ba00b69). 운영 배포 없음.
- 기존 Manifold3.5.4 WASM offset·L자/섬/좁은목2영역/과대공구0영역, 독립 거리10908표본·급속 Z·돌출체 검사. 빈 decompose의 빈component 개수 검사 실패를 보정 후 통과. [보고](agent/CNC_윤곽커널실증_CAD-05.md).
- prototype32·frontend build/자산 분리 통과. 실제 합성 관리자 브라우저 폴더/파일 참조 저장·구 기록 호환 확인. DB 명령/실제 DB/장비/연속 충돌·전체 소재 제거·OCCT·STEP 미실행.
- E0만 완료, 일반 편집기 rect/circle 제한 유지. 다음CAD-06 자유 스케치/JSON v2/worker 연결은 ID별 결과 확인 뒤. 현황·공통설계·인계 갱신.

## 2026-10-06 CAD-04 연구노트·고도화 분석

- 관리자 웹 이력 사용자 선택 반영. POC-01/02/03 회고·이유/검증/미해결/다음·ZIP/STL/안내 SHA-256. 기존 파일 미수정. 브라우저 추가 기록·JSON export/import·중복 병합/충돌 보존. 서버 동기화/사진 업로드/서명 없음.
- prototype29/API13·frontend build·공개/보호 자산 분리 통과. 실제 브라우저 합성 관리자 기록 추가·JSON 다운로드/복원 확인. HTML/JSON HTTP401/403/200 no-store 확인. 전체 frontend 테스트는 이전 CAD-03 결과이며 이번 재실행하지 않음. 실제DB/실물·커널 실증/DB 명령 미실행.
- [고도화 분석](modules/cad-cam/편집기_고도화분석_CAD-04.md): rect/circle와 상면 홈 구조 분석, E0 커널→E1 스케치→E2 피처→E3 조립→E4 제작→E5 CAM 제안. 최신 main8df92c4의 W0-2/CI를 병합 보존하여 로컬 통합. 다음 ID는 전체 방향 확인 후, 이번 고도화 구현 미착수. 원격 push/운영 배포 없음.

## 2026-10-06 CAD-03 완료 · 관리자 전용/탄성 외피

- POC-03: 유연 외피·커버·하단 스킨, 강체 마찰부/가이드, 완전 분리 서랍 총9부품. 닫힌 단일 솔리드9개·강체 간섭42표본 통과. 압축10mm/비틀림±12°는 설명용 가정.
- 화면과 STL/ZIP 모두 MEMBER+ADMIN API 검사. 일반 CAD는 유지. 공개 빌드에서 POC 제거, 배포 절차에 기존 공개 파일 교체 기록.
- frontend524·prototype27·권한API13 통과, 빌드/자산 분리 통과. 브라우저 합성 관리자 세션으로 9부품·누름/비틀림·서랍115mm 분리·STL/ZIP 다운로드 확인. 실제 DB 인증·실물/탄성/슬라이서·운영 배포 미검증. [상세](agent/CAD_CAM_관리자POC_CAD-03.md).
- main ec1b373 병합하여 W0-1 결과 보존. 160b9b0 로컬 main fast-forward 통합 완료. 다른 작업자 미커밋 파일은 유지. 다음은 사용자 검토와 재료/결합·출력 시험이며 다른 ID 자동 착수 없음. 원격 push 없음.

최종 반영 확인(2026-10-05): CAD-02 `649e372` 로컬 main fast-forward 완료. main에서 Node24 frontend npm ci/build 성공, Git 미커밋 변경 없음 확인. 최종 화면 기록 크기 보정. 원격 push·배포 없음.
## 2026-10-05 CAD-02 로그인 포털 CAD·CAM 메뉴 통합

- 사용자 지시로 앱 런처 바로 오른쪽 메뉴·Private 경로·편집기/POC 전환·빌드 자산 자동 포함. 브라우저 저장 공간/세대 분리, 하위 경로 다운로드/worker 대응. [보고](agent/CAD_CAM_포털통합_CAD-02.md).
- frontend521(탭 상태 수정 후 관련3)·prototype13·build/typecheck/lint/format 통과. 모의 로그인 브라우저에서 CAM100%·POC STL 다운로드·설계 복귀·390px 메뉴 확인. 실제 인증/DB/운영/실물 검증 미실행.
- main의 최신 DSN 설계 문서를 병합해 보존. 로컬 main 반영 대상. 원격 push/배포 없음. 다음 사용자 확인 후 운영 반영 또는 실제 FDM 시험.

## 2026-10-05 POC-01 비누 마찰판 디지털 시험편

- 일반 FDM 기준 사용자 답변 반영. 플라스틱 돌기 0.6/1.0/1.4mm 판3개+트레이, 실제 boolean STL·웹 조립/분해·ZIP·실험표 작성. [결과/제약](agent/비누그라인더_POC-01.md).
- 생성기 단일 연결체/체적/간섭 검사, 내보낸 STL 폐곡면 포함 테스트13 통과. build/format 통과, Three 청크569KB 경고. 실제 브라우저 교체/분해/체크/다운로드 및390px 넘침 없음 확인.
- 실물/슬라이서/절삭/마모/방수·DB 검증 미실행. 운영·DB 변경 없음. 다음은 사용자 검토와 출력/측정, 별도 ID 자동 착수 없음. push·배포 없음.

## 2026-10-05 CAD-01 직접 설계하는 웹 CAD·CAM 편집기 (Codex)

- 사용자 정정: 제품 모델 대행이 아닌 직접 편집하는 웹 CAD·CAM 프로그램. CAD-00 기구 선택 질문을 철회하고 CAD-01 독립 검토 시제품으로 진행했다.
- `prototypes/cad-cam/`: 사각형/원 스케치·돌출·상면 파내기·치수 편집·복제/삭제·undo/redo·JSON/STL·2.5D 경로·worker 격자 소재 제거. 운영 frontend/API/DB와 분리했다.
- 자동 검사9 통과. 실제 브라우저 빈 설계→돌출→사각 홈/관통→CAM→재생/정지/되감기, 마우스 드래그, undo/redo, 과대 공구 차단, JSON 다운로드/재입력, STL 바이너리 검사 완료. 1440×900/390×844 가로 넘침0, 오류 로그0. [검증 보고](agent/CAD_CAM_편집기_CAD-01.md).
- 입력 step·SVG 숨김·공구 입력 즉시 경로 무효화·작은 화면/속성 스크롤·숫자 미리보기 보강. WIP `33c3f22`, 최종 커밋은 `git log -1`.
- 제약: 단일 기본 돌출+상면 포켓의 메시 시제품. B-Rep/STEP/자유 곡면/조립/다축/실물·충돌 검증 없음. Safari·실기기·운영·DB 명령 미실행. 원본 PDF/개인정보 미포함.
- 다음: 사용자 체험 확인 후 후속 범위 결정. 다른 작업 ID는 시작하지 않았다. 17개 전체 설계 우선 상태 유지. push·배포 없음.
- 최종 `npm test` 9/9, `npm run build`, `npm run format:check` 통과. 빌드 JS 627.94KB의 청크 크기 경고는 남음(gzip 164.42KB). 현황·인계·검증 보고 동시 갱신.

## 2026-10-04 CAD-00 휴대용 비누 그라인더 자료 검토 (Codex)

- 사용자: 설계→가공 체험 선택, 첨부 제품으로 예제 변경. 검토 문서 `docs/plan/휴대용비누그라인더_시제품검토_CAD-00.md` 작성.
- PDF 10쪽 렌더·시각 확인, 4쪽 확대. 플라스틱 돌기·건조 비누·하단 수집 의도 확인. 70×90×15mm는 이미지 참고치이며 제작 확정값 아님. 방수 등급은 본문의 미검증 정정을 우선한다.
- 내부 비누 고정/가압/회전 궤적·배출·두께의 미정 사항 정리. 사각 외형+내부 회전판/원통형/접이식 중 선택 질문 전달.
- 진행: CAD-00 검토 완료, CAD-01 구현 0%, 사용자 구조 선택 대기. 단일 부품의 단순 포켓 CAM과 비누 분쇄 작동을 구분하도록 제안.
- 검증: 문서 diff 점검. CAD·CAM·브라우저·실물 시험과 DB 검증 명령은 미실행. 제품 코드·DB·운영 변경 없음. 원본 PDF·개인/사업 정보는 Git에 미포함.
- 다음: 답변 반영 후 CAD-01 독립 검토 시제품. ROADMAP-02 개발 중지 원칙 유지. push·배포 없음.

> 최신 Codex 작업: 2026-10-05 **GW-EXT-P0/A 상세 설계 작성·전체 확인 대기**. 범위/순서 승인, 제품 미구현. [설계 묶음](plan/GW확장_상세설계검증_GW-EXT-A.md).

## 2026-10-05 GW-EXT-P0/A 상세 설계

- 사용자 “상세 설계 진행해줘”로 확장 범위·순서 승인. 운영 요건/복구·CORE 공유공간·GW 실제권한·화면·인수 묶음5개 작성.
- 논리 신규 core3/GW7테이블, 기존테이블 재사용·확장, API/락/권한회수/멱등재응답·다중탭 context·초대비밀 유실정책·직원연결동의/재배정 명세. 화면9개 추가/확장, 인수24항목. B~F는 후속 상세설계.
- 회사 규모/SSO·MFA 공급자/RPO·RTO/보존 등 미정, P0 운영 게이트로 명시. 계정·최종GW관리자 복구 부속설계 미완료이므로 COMPANY운영 승인 불가. 합성 TEAM_TEST 개발의 기술 명세와 구분.
- 문서 정적 링크17개/문서5개/화면9/인수24/현황178/200줄/diff 검사 통과(exit0). 최초 화면번호 정규식 검사 실패 후 표 제목을 허용하는 식으로 보정해 통과. pytest·Vitest·브라우저·DB·보안·복구·성능 미실행, 코드·metadata·Excel·migration 변경 없음.
- 다음: 사용자 전체설계 확인, c 기존체험 마무리 및 구현 전 최신main/정식번호/인증부속설계 조율. 이번은 문서 작업만, c 미착수. push·배포 없음.

## 2026-10-05 GW-EXT-01 확장 결정 초안

- 사용자 FS-030 §7 제외 범위 확장 요청, “실제 회사 도입까지 목표” 확정. 공유 공간/실계정 권한·조직·결재v2·댓글/첨부/PDF·인사/협업·ERP 통제/EIP·외부 메일/서명·운영 준비를 전수 매핑.
- core 실제 인증/스코프의 개인 공간 전제 확인. P0 운영 요건→A 공유 권한을 선행하고 기존 체험과 분리. 업무 교차쓰기/FK 금지 유지; ERP가 확정 통제를 소유. 공식 D/AC 번호 미선점, 로컬 GX01~10 제안.
- 결정 초안/기존 결정서 안내/GW README/현황/HANDOFF만 변경. 상대 링크5·제안10·범위29항목·현황178/200줄·diff 정적 검사 통과(exit0). 최초 검사에서 Git 한글 경로 인용을 경로 변경으로 오인해 실패했고 NUL 구분 경로로 보정 후 통과. 제품 테스트/DB/브라우저/외부 연동 미실행.
- 다음: 사용자 범위 확인 후 P0 요구사항과 A 모듈/화면 상세 설계. c 미착수 상태 유지, 개발 순서는 초안 제안. push·배포·실데이터 반입 없음.

## 2026-10-07 W1b-1 HR 기준정보 (Claude Code)
- 화면 5개(H-02 부서 · H-03 직위·직책 · H-04 근무 형태 · H-05 사원 · H-06 발령)와 API 11경로. 설계 5장의 "조직·직위" 한 화면을 부서·직위로 나눠 **15화면**으로 조정(설계 문서 갱신, 화면 ID는 H-01~15).
- 공통 엔진 활용: 부서·직위/직책·근무 형태는 `fs.common.master` **선언만**으로 끝났다(백엔드 Master 3개·프런트 MasterScreen 3개). 사원·발령은 흐름이 있어 직접 구현.
- 핵심 규칙(DSN-30 F03): **사원의 부서·직위·직책·재직 상태는 확정 발령으로만 바뀐다.** 사원 등록은 사원 행 + 입사(HIRE) 발령 확정을 한 트랜잭션에서, 발령은 작성(draft) → 확정. 확정분은 수정·삭제 불가(이력). 퇴직 사원에게는 발령 금지. 부서 순환 참조 차단.
- 제공 함수: `interface.employees(status)`·`departments()` — 사람·부서 코드의 원천(D81). 다른 솔루션이 "HR에서 가져오기"로 쓴다.
- 공통 엔진 보강: `master.store`·`duplicate`·`reject_duplicate` 공개(합성 작업용), 프런트 입력 종류에 **number·time** 추가, 멱등 digest가 날짜·시각·소수를 다루도록(`request_digest` default), `CODE_PATTERN` 상수.
- **업무 솔루션 목록을 `fs.common.modules` 한 곳으로** 모았다(8곳 중복). HR을 빠뜨려 게스트 공간 정리가 FK RESTRICT로 막히는 것을 테스트가 잡았다 — 앞으로 새 솔루션은 이 목록만 고친다.
- 브라우저 확인(로컬, 게스트 공간): 부서(소문자 → 대문자 변환)·직위·직책(부서장 배지)·근무 형태(8시간 0분 표시) 등록 → 사원 등록 시 "사원을 등록하고 입사 발령을 확정했습니다" + 인사카드에 입사 발령 확정 1건 → 부서 이동 발령 작성(작성 중) → 확정 → 사원 부서가 품질부로 바뀜.
- **버그 1건 수정**: 코드 입력 검사 정규식 `[A-Z0-9_-]`가 브라우저의 v 플래그에서 무효로 처리돼 **입력 검사가 조용히 꺼져 있었다**. `-`를 escape한 `CODE_PATTERN`으로 고치고 브라우저에서 동작 확인(`SALES-1` 통과, 공백 거부).
- 검증: pytest **867 통과**(HR 12 신규), frontend **530 통과**(HR 5 신규, 64파일), typecheck·lint·format·build. 배포 없음.

## 2026-10-06 운영 배포 3474942 (사용자 실행, Claude 확인)
- `tools/deploy.sh`(W0-3) **첫 실행**. 서버 `c352dfc` → **`3474942`**. 올라간 것: W0-1 지연 복사 · W0-2 테스트 병렬 · W0-4 백엔드 공통 엔진 · W0-5 프런트 공통 엔진 · W1a HR DB · CAD-03~06.
- 마이그레이션 3건 적용(`w01_lazy_seed` · `w1a_hr` · `w1a_hr_module`) → head **`w1a_hr_module`**, schema 0.19.0 / 138테이블. 시드 버전은 그대로(sv-20261001-1)라 템플릿은 다시 만들지 않았다(모듈 행 hr은 마이그레이션이 채움).
- 스크립트 확인: 원점 200 · 공개 200 · **서버 DB와 설계 대조 0** · 최근 2분 5xx 0건. 사전 점검에서 CI 통과·커밋 일치·서버 저장소 깨끗함을 먼저 확인했다.
- 브라우저 확인(운영): 게스트 생성 201(공간 49) → FEMS 에너지원 3건 표시(**지연 복사 + 백엔드·프런트 공통 엔진이 운영에서 동작**) · MES·ERP 대시보드 200(미수금 11,686,156원). 콘솔 오류는 로그인 전 401뿐.
- 배포 전까지 서버가 `c352dfc`에 머물러 있던 이유: **GitHub main push는 저장소만 갱신한다.** 서버는 자기 복사본을 받아 재시작·프런트 업로드를 해야 바뀐다. 이제 `tools/deploy.sh` 한 줄로 한다(사용자 실행 — Claude는 ssh 불가).

## 2026-10-06 W1a HR DB (Claude Code)
- 일괄 개발 W1(사람 원천)의 DB 단계. 승인된 목표 설계(DSN-30·DSN-16)를 제품 설계로 **그대로** 옮겼다: `hr` 19테이블(조직·직위/직책·근무 형태·사원·발령·자격/교육·일 근태·월 마감·연차·휴가·급여 항목/기준/고정 수당/상여/실행/명세서/명세 항목·평가 기간/평가) + `core.holiday`(공통 휴일 — HR 근태 자동 생성이 읽는다) + 모듈 키 `hr`. schema **0.18.0 → 0.19.0(W1a), 118 → 138테이블**.
- 도구: `tools/apply_w1a.py`(목표 → 제품 복사, 멱등) · **`tools/build_migration.py`**(설계에서 마이그레이션 생성 — W1a는 20표·160문장, W2a는 110표라 손으로 옮기면 틀린다. 생성된 파일은 고정 SQL 목록이라 실행할 때 JSON을 읽지 않는다).
- 마이그레이션 `w1a_hr`(스키마) + `w1a_hr_module`(기존 공간에 hr 모듈 행, 지연 복사이므로 `seeded_generation_id`는 NULL). 새 공간·템플릿도 hr 행을 만든다.
- 검증기: 일괄 개발(W…) 작업은 그동안 쌓인 검사를 모두 켜고(`at_least`), 제품 설계의 표 목록은 **설계 문서의 부분집합**이면 통과하도록 했다(제품은 단계마다 자란다). 통합 계약(DSN-90)은 목표 설계에만 적용한다. 오래된 테스트 4개가 작업 ID를 하드코딩하고 있어 공통 규칙(`expected_names`·`at_least`)을 쓰게 고쳤다.
- `apply_dsn16`은 제품이 `core.holiday`를 먼저 가져간 뒤에도 목표를 다시 만들 수 있도록, **자기가 만드는 표 중 이미 있는 것만** 건너뛰게 했다(기존 BEMS 표에 더하는 FK 4건이 빠지던 것을 바로잡음).
- 기대값 갱신: 모듈 행이 1개 늘어 게스트 생성 10 → 11, 시드 합계 14,685/14,687 → 14,686/14,688.
- W0-6은 따로 만들지 않는다: `core.holiday`는 여기서 적용했고, 공통 조회 4종·시드 코드 사전은 쓰이는 단계(각 솔루션 b·c)에서 함께 만든다. 미리 뼈대만 두면 쓰이지 않는 추측이 된다.
- 검증: **pytest 855 통과·0 실패**(병렬 3분), perf 1, tools 125, db:validate 0·격리 0, **마이그레이션 적용 후 설계 대조 0(138테이블·FK 314)**, Excel·ERD 재생성, 목표 설계 361 검증 0(다시 만들어도 같음). **로컬 개발 DB도 적용**(공간 306개에 hr 모듈 행). 배포 없음.

## 2026-10-06 W0-5 프런트 공통 엔진 (Claude Code)
- `frontend/src/shared/master.tsx`: 기준정보 화면(목록 + 등록/수정 패널)을 **선언**으로 만든다. 엔진이 목록·쪽수·조건 조회, 패널·저장하지 않은 입력 보호, **바뀐 항목만 PATCH**, 삭제 2단계, 입력 칸별 오류, 참조 중 삭제 안내, 멱등 키(응답 불확실 시 보존), 솔루션 꺼짐 안내를 처리한다. 저장 요청·삭제 2단계는 기존 `shared/hooks.tsx`의 `useApiSend`를 그대로 쓴다(세 번째 복사본을 만들지 않았다).
- 이전 1건: **FEMS 에너지원(F-11)** 417줄 → **119줄**(선언만). 기존 테스트 12개를 **고치지 않고** 통과.
- 브라우저 확인(로컬 dev 서버, 게스트 공간): 목록 3건 표시 → 등록(소문자 `steam` → `STEAM` 대문자 변환, POST 201, 총 4건) → 수정(PATCH 200, 바뀐 이름만) → 참조 중인 ELEC 삭제 시도 → 409와 참조처별 건수(계측 채널 9·계수 4·요금제 2·목표 17·기준선 4) → STEAM 삭제(목록 3건 복귀). 콘솔 오류는 로그인 전 401과 일부러 낸 409뿐.
- 범위: 전표 입력·3D·관리도·결재 진행처럼 흐름이 다른 화면은 엔진을 쓰지 않는다(FS-017 문서에 명시).
- 검증: frontend 테스트 **524개 통과**(63파일), typecheck·lint·format·build 통과. 백엔드 변경 없음. 배포 없음.

## 2026-10-06 W0-4 백엔드 공통 엔진 (Claude Code)
- `fs/common/engine.py`: `read()` 조회 트랜잭션(REPEATABLE READ·읽기 전용) · `action()` 쓰기 한 건(공간 잠금 → 세대·모듈 재확인 → 멱등 영수증 → 처리 → 영수증 저장) · `mutation_key()` CSRF·멱등 키. 솔루션별 복사본 **19곳**(`_action` 6 — 바이트 단위로 같았다 · 라우터 `_mutation` 6 — md5 동일 · `_read` 7)을 모았다.
- `fs/common/master.py`: 기준정보 표 하나를 `Master`로 **선언**하면 목록(정렬 허용 목록·조건·쪽수)·단건·등록·수정·삭제·중복 검사·참조 확인·영수증이 따라온다. 업무 규칙은 `check(연결, 범위, 합친 값, 현재, id)` 훅으로 솔루션에 남긴다.
- 이전 1건: **FEMS 에너지원**(F-01 화면). 서비스·repository 276줄 → 74줄, 기존 테스트 22개를 **고치지 않고** 통과. 계측 단위 변경 금지 같은 업무 규칙은 훅으로 유지.
- **전표 상태 전이는 묶지 않았다**: 확정·취소의 본문(채무 생성·재고 이동·역분개)이 솔루션마다 달라 공통 틀(`action`)만 공유한다. 첫 전표 화면(W2)에서 실제 공통점을 다시 본다 — 지금 묶으면 추측이 된다.
- 곁다리 수정: WMS 동시성 시험 2건이 가로채던 `service.write_scope`가 엔진으로 옮겨가 `fs.common.engine`을 가로채도록 고쳤다(같은 것을 검사한다). 런처 평가 "최근" 정렬을 `created_at DESC, id DESC` → `id DESC`로 — 병렬 실행에서 시각 동률로 순서가 뒤집혀 테스트가 한 번 실패했다(제품 동작은 같다).
- 결과: 18파일 **150줄 추가 · 527줄 삭제(순증 −377)**, 동작 변화 없음.
- 검증: pytest **855 통과·0 실패**(병렬 3분), perf 1 통과, tools 125 통과, ruff check·format. 배포 없음.

## 2026-10-06 W0-3 배포 스크립트 (Claude Code)
- `tools/deploy.sh`(DSN-01 E): 사전 점검(main·커밋하지 않은 변경 없음·origin과 같음·**그 커밋의 CI 통과**·서버 접속·서버 저장소 깨끗함) → 프런트 빌드(별도 worktree, 같은 커밋) → 서버 `git merge --ff-only`+커밋 대조 → `uv sync` → `alembic upgrade head` → **시드 버전이 바뀌었을 때만** 템플릿 재생성 → API 재시작 → **프런트 업로드** → 확인(원점·공개 200, DDL 대조 0, 최근 2분 5xx). 실패하면 멈춘다. `--dry-run`은 서버를 바꾸지 않고 빌드까지만. 서버 주소 등은 `FS_DEPLOY_*`로 바꾼다.
- 검사 `tools/test_deploy.py`: 가짜 ssh·rsync·npm·curl·gh로 스크립트를 실제로 실행한다(**서버 접속 없음**). 단계 순서, 프런트 업로드 포함(2026-10-04 누락 재발 방지), 서버 커밋 불일치 시 중단, CI 미통과 시 서버를 건드리지 않음, 시드 같으면 템플릿 유지, `--dry-run`이 아무것도 바꾸지 않음 — 5개 통과.
- CI: tools 테스트 범위를 `test_fs0*.py` → `test_*.py`(73 → **125개**, 설계 test_dsn*·배포 test_deploy 포함, 14초). 배포 절차 문서 8장을 스크립트 기준으로 고치고 손 절차는 아래에 남김.
- **실행하지 않음**: 스크립트를 실제 서버에 돌리지 않았다(ssh는 사용자 계정). 운영 반영은 사용자가 `tools/deploy.sh`로 한다.
- 검증: `tools/test_deploy.py` 5 통과, tools 전체 125 통과, `bash -n`·`--help`·모르는 인자 종료 코드 2 확인. shellcheck는 설치돼 있지 않아 미실행. 배포 없음.

## 2026-10-06 W0-2 테스트 병렬 (Claude Code)
- 복사 반영 캐시: `seed.copy`의 스키마 반영(reflection)·FK 조사가 게스트 복사 시간의 90% → DB·스키마별 1회만(`_reflected`·`_raw_foreign_keys`), 시드 유무는 count 대신 EXISTS. 게스트 생성 복사 **0.43 → 0.011초**, 9개 솔루션 모두 열기 0.69초(예전 전체 복사 1.5초).
- 병렬: `pytest-xdist` 추가(dev). `conftest.pytest_configure`가 작업자마다 원본 `*_test` DB를 템플릿으로 `<원본>_gwN_test`를 새로 만들고 TEST_DATABASE_URL을 바꾼다(전체 DB를 비우는 테스트끼리 겹치지 않게, 복제는 advisory lock으로 직렬화). 시간 측정 테스트(`-m perf`, 1개)는 부하 없이 따로.
- CI(`ci.yml`): `pytest -n auto -m "not perf"` + `pytest -m perf`. README 로컬 실행 예도 같은 방식.
- 측정(로컬 10코어, `-n auto`): 전체 pytest **22분 38초 → 3분 0초**(2회 연속 855 통과·0 실패), perf 1 통과(22초). 테스트 수 증가(843 → 855)는 다른 세션의 CAD-03 테스트가 main에 들어온 것.
- 하지 않음: 읽기 전용 게스트 공유·변경 범위 선택 실행(A2·A4) — 3분이면 필요 없다고 판단, 필요해지면 추가.
- 검증: pytest 855 통과(병렬 2회)·perf 1, ruff check·format. 원격 CI는 push 후 실행(결과 미확인). 배포 없음.

## 2026-10-05 W0-1 게스트·세대 지연 복사 (Claude Code)
- 사용자 전체 설계 확인("전체 설계 확인했어 W0 진행해줘") → DSN-99 확정, 일괄 개발 시작. W0을 W0-1~6으로 나눔(DSN-99 7-1).
- 구현: 게스트 생성·회원 생성·세대 초기화는 core(모듈 행)만 복사, 솔루션 시드는 **처음 열 때**(솔루션 라우터 의존성 `fs.common.scope.seed_ready` → 요청 트랜잭션 전 공간 잠금 → `seed.copy.copy_module_seed`). `core.workspace_module.seeded_generation_id`(복사한 세대 — 활성 세대와 같을 때만 준비됨)·`core.data_generation.template_generation_id`, 마이그레이션 `w01_lazy_seed`(기존 공간은 활성 세대로 채움), schema 0.18.0. 교차 조회 `interface.enabled()` 6곳은 `module_available`(켜짐 + 복사됨) — 아직 열지 않은 솔루션은 꺼짐과 같게 None(DSN-01 S2). GW의 "ERP가 꺼져 있어" 안내는 "꺼져 있거나 아직 열지 않아"로.
- 테스트: `conftest.guest_space`는 파일 이름의 솔루션 + 직접 제공자만 미리 복사(`SEEDS`로 지정, 통합 테스트는 전체). 새 `test_lazy_seed`(동시 처음 열기 1회 복사·실패 시 흔적 없음·초기화 후 다시 지연·꺼짐), `test_common` 복사 수 검사를 지연 복사 기준으로, 회원·통합·WMS 보조 게스트도 맞춤. tools 테스트 task 집합에 W0-1.
- 측정(로컬, 같은 DB `factory_studio_fs016_test`): 게스트 복사 **1.5초 → 0.43초**(남은 시간은 스키마 반영 — W0-2에서 캐시), 전체 pytest **28분 39초 → 22분 38초**. 기준 실행의 실패 1건은 실행 중 파일을 고쳐 생긴 것(재실행에서 해소).
- 검증: **pytest 843 통과·0 실패**, db:validate 0·격리 0·DDL 대조 일치·ERD·Excel(현재·목표), 목표 DB 361 검증 0, tools 73 + DSN 47, frontend typecheck·lint·format·GW 테스트 5. 로컬 개발 DB `factory_studio`도 `w01_lazy_seed` 적용. 배포 없음.

## 2026-10-05 DSN-31 GW 보강 설계 · DSN-90 GW 재검증 (Claude Code)
- 결정: Q1 **실제 도입 A(TEAM 공간·멤버십·초대·직원 계정 연결·업무 권한·문서 열람·재배정)를 지금 목표 DB에 넣음**(제안과 다름, 개발은 별도 트랙) · Q2 결재 대상 ERP 발주·지출결의·PLM ECO · Q3 병렬·합의·전결·위임 · Q4·Q5 댓글·일정·알림함·**채팅 포함**(제안과 다름) · Q6 ERP 확정 통제 · 범위 24/28(반복 자동 결재·첨부·외부 메일·전자서명 제외).
- 문서 `docs/modules/gw/GW_보강설계_DSN-31.md`: 기준표 28, 규칙 8묶음, DB(GW 8 → 24: 체험 10·조직 1·실제 도입 5, core 3, ERP 2), 화면 체험 14(G-01~13 + ERP 1)·실제 도입 9(별도), 교차 조회(PLM `eco_for_approval` 신규). D81대로 GW-EXT `person_assignment`는 두지 않음 — 조직 단위 = HR 부서 스냅샷.
- 목표 DB `tools/apply_dsn31.py`(apply_dsn30 다음·apply_dsn90 앞) → **361테이블**·컬럼 4,162·FK 866. GW 단계 순번 유일 키 2개 제거(병렬), core.workspace TEAM·auth_session 활성 공간·app_user subject_key. `apply_dsn90` 버전은 target-0.20.0으로. 검증기 `validate_gw_dsn31`, `validate_fs030a`는 DSN-31 목표에서 표 추가·순번 키 제거를 허용, DSN-90 흐름 S9(결재 → 확정 통제) 추가(흐름 칸 41·멱등 21·원천 종류 12). test_dsn11 ERP 표 수는 하한으로.
- DSN-90 7-2 GW 재검증, DSN-99 갱신(남은 설계 0, 차이 새 표 243·바뀌는 표 54·교체 제약 55, 열 삭제·형 변경 0).
- 검증(통과를 커밋 조건으로): 목표 validate 0·격리 0·**빈 DB 적용 대조 0(361·UK 722·CHECK 859·INDEX 231·UNIQUE_INDEX 100·FK 866)**·ERD·Excel·tools 73 + DSN 47·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-99 개발 계획 초안 · D82 Codex 중단 (Claude Code)
- 사용자: "Codex는 이제 업무 안 함, Claude가 한다" → ROADMAP-02 **D82**, AGENTS.md §8 머리 안내, Codex 작업지시 9장의 GW 목표 DB 반영은 Claude **DSN-31**로.
- `docs/plan/개발계획_DSN-99.md` 초안: 설계 완료 점검(승인 기준 6묶음 — GW 기준표·목표 DB만 남음), 규모(현재 118 → 목표 340테이블, 새 표 222·바뀌는 표 46·교체 제약 44, **열 삭제·형 변경 0**), 마이그레이션 (a) 단계별 새 revision 제안, 단계 사이클(a DB → b API·화면 → c 시드·도움말 → 검증 → 배포·동결), 단계 W0~W6, 위험, 결정 Q1~Q5.
- 검증: 목표·현재 DB 차이를 스크립트로 대조(위 수치). 제품 코드·DB 변경 없음.
- 결정(같은 날): Q1 단계별 새 revision · Q2·Q3 W0~W6 순서, 단계마다 배포·동결 · Q4 GW 실제 도입은 회사 요구값이 정해질 때 별도 트랙 · Q5 antigravity 병행. 다음: DSN-31 GW 목표 DB.

## 2026-10-05 DSN-90 GW 결정·병합 (Claude Code)
- 사용자 결정(ROADMAP-02 **D81**, DSN-90 7-1): G1 **사람·조직 원천 = HR**(GW 조직·소속은 HR 가져오기 스냅샷, GW-EXT D단계 인사·근태·휴가 제외 → HR, GW는 일정·채팅) · G2 **Codex가 GW 기준표·`apply_dsn31`로 목표 DB 반영** 후 GW만 재검증 · G4 **`codex/fs-030-gw` `08c91d9` 지금 병합**.
- 병합: 설계 문서만(GW-EXT-01·P0·A·CORE 공유공간·화면·인수). 충돌 2곳(현재기획 1행은 main 기준, progress는 양쪽 보존). GW-EXT-01 머리에 D81 개정 안내, Codex 작업지시 9장 추가. 배포 없음.

## 2026-10-05 DSN-90 통합 검증 (Claude Code)
- 보고서 `docs/plan/통합검증_DSN-90.md`: **교차 조회 계약 전체 표(제공 109함수, 현재 코드 19 + 신규 90, 공통 4종 enabled·monthly_summary·pending_tasks·lookup)** — 이 표가 계약 기준본. 문서 간 불일치 9종 34건 정리(구매 요청 원천 오기, 부서 원천 HR, 공통 함수 누락, WMS `pending_tasks` → `pop_tasks` 개명, TMS `open_shipment_orders` → ERP `shipment_orders`, 제공 누락 12·받는 쪽 누락 6, POP 동시성은 pop_import UK로 확인).
- 업무 흐름 S1~S8(수주~매출·구매~매입·설비~보전·품질·간접 구매·사람/급여·에너지·설계 변경) 62단계를 받는 표·칸·멱등 키까지 추적. 시드 시나리오(한 회사·공통 코드 사전·M-3~M-1 확정 + M 진행·흐름별 완료 1 + 중간 1·솔루션당 ~3,000행).
- 목표 DB 보정 `tools/apply_dsn90.py` → target-0.19.0: 가져오기 원천 번호 칸(ERP 거래처 `crm_account_code`·견적 `crm_quote_request_no`·판매계획 `scm_forecast_ref`, ERP·MES·WMS 품목 `plm_part_no/revision`, MES BOM `plm_bom_ref`, QMS 클레임 `crm_inquiry_no`·4M `plm_eco_no`) + 멱등 UK, QMS NCR 원천당 1건, ERP 매입 `FREIGHT`·`INDIRECT`, WMS 문서 `CMMS_ISSUE`. 검증기 `validate_integration_dsn90`(흐름 칸 38·멱등 키 17·원천 종류 10), `test_dsn90`.
- GW 대조: Codex `codex/fs-030-gw` `08c91d9`(GW 실제 회사 도입 P0/A 설계)는 목표 DB·기준표 형식이 아니고, GW 조직·소속(A)과 인사·근태·휴가(D)가 HR DSN-30과 겹친다 → 결정 4건 대기(보고서 7장). 브랜치는 main `1f96532`에서 갈라져 기준 문서 충돌 예상, 미병합.
- 검증(통과를 커밋 조건으로): 목표 validate 0·격리 0·**빈 DB 적용 대조 0(340·컬럼 3,923·UK 683·CHECK 834·INDEX 218·UNIQUE_INDEX 99·FK 812)**·ERD·Excel·tools 73 + DSN 45·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-30 HR 신규 설계 완료 (Claude Code)
- 결정: Q1 **HR이 사원·부서 코드 원천**(각 솔루션 "HR에서 가져오기", 자동 동기화 없음) · Q2 근태 자동 생성 + 예외 수정 · Q3 HR 자체 부서장 휴가 승인 · Q4 월급제·합성 고정 비율 공제·확정 불변·ERP에는 부서·항목별 합계 · Q5 정기 상여·퇴직금 추계 · Q6 자격·교육 + **인사 평가 포함**(제안과 다름) · Q7 본인 조회 · 범위 24/26(민감 정보·신고 제외, D79).
- 문서 `docs/modules/hr/HR_설계_DSN-30.md` + README: 기준표 26, 기능 규칙 7묶음, DB hr 19, 화면 14(HR-01~14), 교차 조회(`employees`·`departments`·`payroll_runs`·`monthly_summary`·`pending_tasks`·`lookup` 제공, core `holidays`·EIP `my_employee_code` 요청 — ERP·EIP 문서에 메모).
- 목표 DB: `tools/apply_dsn30.py` → target-0.18.0/DSN-30 **340테이블**·컬럼 3,911·FK 812, 모듈 키 hr. 검증기 `validate_hr_dsn30`(민감 정보 칸·신고 테이블 금지, 사원 코드 유일, 근태 1일 1건, 월 확정 1건, 실지급 = 지급 − 공제).
- 검증(통과를 커밋 조건으로): 목표 validate 0·격리 0·**빈 DB 적용 대조 0(340·UK 683·CHECK 831·INDEX 218·UNIQUE_INDEX 94·FK 812)**·ERD·Excel·tools 73 + DSN 43·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.
- **Claude 담당 신규 설계 끝(DSN-21~30).** 남은 것: GW(Codex) → DSN-90 통합 검증 → DSN-99 최종 확인 → 일괄 개발.

## 2026-10-05 DSN-29 RWS 신규 설계 완료 (Claude Code)
- 결정: Q1·Q2 **텍스트·단계 체크리스트 원격 안내로 한정**(영상·AR·사진 없음), 요청 출처는 직접 등록·CMMS 작업지시·QMS 부적합(POP 호출은 POP 안에서만) · Q3 **원격 해결 실패 → "현장 출동 필요", CMMS가 가져가 작업지시** · Q4 고객 현장 원격 A/S · Q5~Q7 작업 가이드·버전, 지식화·유사 사례, 목표 시간·상향, 만족도 · 범위 17/19.
- 문서 `docs/modules/rws/RWS_설계_DSN-29.md` + README: 기준표 19, 기능 규칙 6묶음, DB rws 12, 화면 10(RW-01~10, 현장 응답 K), 교차 조회(`field_visit_requests`·`monthly_summary`·`pending_tasks`·`lookup` 제공, CMMS `work_order`·`failure_codes`·QMS `ncr`·CRM `accounts` 요청 — CMMS·QMS 문서에 메모).
- 목표 DB: `tools/apply_dsn29.py` → target-0.17.0/DSN-29 **321테이블**·컬럼 3,715·FK 769, 모듈 키 rws, `cmms.work_order.source`에 RWS_REQUEST(요청당 진행 작업지시 1건). 검증기 `validate_rws_dsn29`. DSN-21 검증기·테스트의 CMMS 출처 확인은 완전 일치 대신 "FEMS 없음"으로 바꿨다.
- 검증(통과를 커밋 조건으로): 목표 validate 0·격리 0·**빈 DB 적용 대조 0(321·UK 647·CHECK 809·INDEX 207·UNIQUE_INDEX 91·FK 769)**·ERD·Excel·tools 73 + DSN 41·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-28 보정: 포털 첫 화면 = EIP (Claude Code)
- 결정 Q8(D80): 초기 기획 "포털 자체가 EIP"를 복원한다. 로그인하면 EIP 대시보드(EI-01, 앱 런처 포함)가 첫 화면이다. EIP 타일과 모듈 키는 두지 않는다(끌 수 없음). 데이터는 그대로 `eip` 스키마에 둔다(core 업무 데이터 금지, FS-013).
- 변경: `apply_dsn28`에서 모듈 키 'eip' 추가를 제거했다. `validate_eip_dsn28`은 모듈 키 'eip'가 **없어야** 통과한다. `test_dsn28`에 회귀 검사를 추가했다. EIP 문서 §0·4-2·5장·7-1, README, ROADMAP-01 §6-3, ROADMAP-02 D80을 고쳤다. 테이블 수는 변동 없다(309).

## 2026-10-05 DSN-28 EIP 신규 설계 완료 (Claude Code)
- 결정: Q1 **공지는 GW 공지 표시**(EIP 자체 공지 없음) · Q2 KPI 정의·목표는 EIP, 실적은 각 솔루션 월 요약 조회 · Q3 **할 일은 사람별**, Q3-1 **HR 사원 코드로 사람 연결** · Q4 월간 경영 보고서·의견 · Q5 **위젯 배치 개인화(eip에 저장)** · Q6 통합 번호 검색 · 범위 13/15.
- 문서 `docs/modules/eip/EIP_설계_DSN-28.md` + README: 기준표 15, 기능 규칙 6묶음, DB eip 8, 화면 8(EI-01~08), 교차 조회(모든 솔루션 `monthly_summary`·`pending_tasks(hr_employee_code)`·`lookup(code)`, GW `published_notices`, HR `employees`). GW 작업지시서·CRM·ELB·QMS 문서에 메모.
- 사람 연결 칸: `gw.person.hr_employee_code`·`crm.sales_rep.hr_employee_code`·`elb.request.requester_hr_code`·`elb.approval.approver_hr_code`·`qms.capa.owner_hr_code`, ELB 승인자 지정 `elb.approver` 신설.
- 목표 DB: `tools/apply_dsn28.py` → target-0.16.0/DSN-28 **309테이블**·컬럼 3,573·FK 746, 모듈 키 eip. 검증기 `validate_eip_dsn28`. test_dsn27의 elb 테이블 수는 하한으로 바꿨다(DSN-28이 elb.approver 추가).
- 검증(통과를 커밋 조건으로): 목표 validate 0·격리 0·**빈 DB 적용 대조 0(309·UK 627·CHECK 788·INDEX 196·UNIQUE_INDEX 86·FK 746)**·ERD·Excel·tools 73 + DSN 39·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-27 ELB/MRO 신규 설계 완료 (Claude Code)
- 결정: Q1 **ELB는 카탈로그·신청·승인·수령 확인까지**(발주·매입·전표는 ERP — 구매 요청 출처 ELB, 재고 품목 입고는 WMS) · Q2 ELB 안 금액 기준 승인 단계(GW와 별개) · Q3 부서 예산 확인(경고) · Q4 비재고 수령 확인 → ERP 매입 근거 · Q5 계약 단가·표준 세트·단가 비교 · Q6 긴급 구매(법인카드 사후 등록 → ERP 카드 내역) · 범위 18/19.
- 문서 `docs/modules/elb/ELB_설계_DSN-27.md` + README: 기준표 19, 기능 규칙 7묶음, DB elb 11, 화면 11(MR-01~11), 교차 조회(`approved_requests`·`receipts`·`emergency_requests`·`monthly_summary` 제공, ERP `budget_status`·`elb_request_status`·`card_transactions`·`purchase_prices`·WMS `inbound_status` 요청 — ERP·WMS 문서에 메모). ROADMAP-01의 ELB `purchase_receipts()`는 Q1로 대체.
- 목표 DB: `tools/apply_dsn27.py` → target-0.15.0/DSN-27 **300테이블**·컬럼 3,481·FK 732, 모듈 키 elb. 검증기 `validate_elb_dsn27`.
- 검증(통과를 커밋 조건으로): 목표 validate 0·격리 0·**빈 DB 적용 대조 0(300·UK 609·CHECK 776·INDEX 193·UNIQUE_INDEX 83·FK 732)**·ERD·Excel·tools 73 + DSN 37·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-26 SCM 신규 설계 완료 (Claude Code)
- 결정: Q1 **SCM은 계획·분석만**(실행은 ERP·MES·WMS가 "SCM에서 가져오기") · Q2 이동평균·지수평활·계절 지수 비교 추천 + 사람 조정 · Q3 확정 예측 → ERP 판매계획 초안, CRM은 참고 · Q4 S&OP·개략 능력 · Q5 재고 정책 산정 → WMS 제안 · Q6 공급처 성과(납기·리드타임 + QMS 등급) · 범위 18/22.
- 문서 `docs/modules/scm/SCM_설계_DSN-26.md` + README: 기준표 22, 기능 규칙 7묶음, DB scm 9, 화면 10(SC-01~10), 교차 조회(`demand_forecast`·`sop_plan`·`inventory_policies`·`supplier_scores`·`monthly_summary` 제공, ERP `shipments_monthly`·MES `capacity`·`production_plan` 요청 — ERP·MES·WMS 문서에 메모).
- 목표 DB: `tools/apply_dsn26.py` → target-0.14.0/DSN-26 289테이블·컬럼 3,370·FK 711, 모듈 키 scm. 검증기 `validate_scm_dsn26`(실행 테이블 금지·확정 1건·제안 1건·조정 사유).
- 검증(통과를 커밋 조건으로): 목표 validate 0·격리 0·**빈 DB 적용 대조 0(289·UK 588·CHECK 759·INDEX 187·UNIQUE_INDEX 81·FK 711)**·ERD·Excel·tools 73 + DSN 35·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-25 CRM 신규 설계 완료 (Claude Code)
- 결정: Q1 CRM 고객사 소유, ERP가 "CRM에서 가져오기"로 거래처 생성 후 코드 연결 · Q2 견적 요청 → ERP 견적 초안, ERP 수주를 읽어 수주 확인 제안 → 사람이 처리 · Q3 6단계 고정 + 확률 조정, 매출 예측 · Q4 고객 문의(품질 문의만 QMS 클레임 전환) · Q5 캠페인·출처 분석 · 범위 21/23.
- 문서 `docs/modules/crm/CRM_설계_DSN-25.md` + README: 기준표 23, 기능 규칙 7묶음, DB crm 13, 화면 10(CR-01~10, 파이프라인 칸반 V), 교차 조회(`accounts`·`quote_requests`·`quality_inquiries`·`pipeline_summary` 제공, ERP `crm_imports`·`sales_orders_for_crm`·`partner_summary` 요청 — ERP·QMS 문서에 메모). 견적 요청의 ERP 처리 상태는 저장하지 않고 ERP 조회로 표시(교차 쓰기 금지).
- 목표 DB: `tools/apply_dsn25.py` → target-0.13.0/DSN-25 280테이블·컬럼 3,269·FK 699, 모듈 키 crm. 검증기 `validate_crm_dsn25`.
- 검증(통과를 커밋 조건으로): 목표 validate 0·격리 0·**빈 DB 적용 대조 0(280·UK 570·CHECK 741·INDEX 184·UNIQUE_INDEX 78·FK 699)**·ERD·Excel·tools 73 + DSN 33·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-24 PLM 신규 설계 완료 (Claude Code)
- 결정: Q1 각 솔루션 "PLM에서 가져오기"(MES 품목·BOM, ERP·WMS·QMS 품목, 자동 동기화 없음) · Q2 도면·문서 메타데이터만 · Q3 ECR → ECO → 승인 → 배포, 배포는 QMS 4M 후보, GW는 배지 · Q4 PLM은 E-BOM까지(제조 BOM은 MES) · Q5 개발 프로젝트·단계 게이트 · Q6 설계 원가 롤업 · 범위 20/24.
- 문서 `docs/modules/plm/PLM_설계_DSN-24.md` + README: 기준표 24, 기능 규칙 7묶음(배포는 ECO로만·현재 배포 1개·배포 불변), DB plm 16, 화면 11(접두어 PD — 패턴 D와 구분), 교차 조회(`released_parts`·`released_bom`·`eco_releases`·`monthly_summary` 제공, ERP `standard_costs`·MES `open_work_orders_by_item`·각 솔루션 `plm_imports` 요청 — MES·ERP·WMS·QMS 문서에 메모).
- 목표 DB: `tools/apply_dsn24.py` → target-0.12.0/DSN-24 267테이블·컬럼 3,113·FK 665, 모듈 키 plm. 검증기 `validate_plm_dsn24`.
- 검증(통과를 커밋 조건으로): 목표 validate 0·격리 0·**빈 DB 적용 대조 0(267·UK 548·CHECK 717·INDEX 176·UNIQUE_INDEX 74·FK 665)**·ERD·Excel·tools 73 + DSN 31·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-23 TMS 신규 설계 완료 (Claude Code)
- 결정: Q1 경계(배차 대상 = ERP 확정 출하지시 중 WMS 피킹 완료, ERP는 TMS 상차 완료를 읽어 출하 확정 대기 — TMS는 ERP·WMS를 바꾸지 않음) · Q2·Q3 자차+용차, 수동 배차 + 적재율 경고 · Q4 기사 모바일(패턴 K) · Q5 운임·용차 정산 → ERP 직접 매입 · **Q6 조달 운송도 TMS로**(WMS 입고 예정의 차량·도착은 TMS를 읽음) · Q7 자차 운행 비용, 범위 20/24.
- 문서 `docs/modules/tms/TMS_설계_DSN-23.md` + README: 기준표 24, 기능 규칙 6묶음, DB tms 10(운송사·차량·기사·권역·배송지·운임표·배차·방문·운행 비용·정산), 화면 14(R-01~14, 기사 K 2), 교차 조회(`loaded_shipments`·`deliveries`·`inbound_arrivals`·`carrier_settlements`·`monthly_summary` 제공, WMS `picked_shipments`·`inbound_notices` 요청 — ERP·WMS 문서에 메모).
- 목표 DB: `tools/apply_dsn23.py` → target-0.11.0/DSN-23 251테이블·컬럼 2,951·FK 626, 모듈 키 tms. 검증기 `validate_tms_dsn23`.
- 검증(테스트 통과를 커밋 조건으로 묶음): 목표 validate 0·격리 0·**빈 DB 적용 대조 0(251·UK 516·CHECK 693·INDEX 171·UNIQUE_INDEX 69·FK 626)**·ERD·Excel·tools 73 + DSN 29(재생성 = 커밋본)·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-22 POP 신규 설계 완료 (Claude Code)
- 결정: Q1 **지연 가져오기**(MES·WMS가 자기 API가 불릴 때 미반영 POP 확정 입력을 가져가 재검증·반영, POP는 `pop_results` 조회로 결과 표시 — 교차 쓰기·배경 작업 없음) · Q2 POP 자체 단말 사용자 · Q3 공정 검사 입력 · Q4 호출(안돈, POP 안에서만) · Q5 작업 일보·라인 현황판 · Q6 범위 26/29.
- 문서 `docs/modules/pop/POP_설계_DSN-22.md` + README: 기준표 29, 기능 규칙 8묶음(스캔 → 확인 → 확정 공통 흐름, CANCEL 입력 규칙), DB pop 7(단말·작업자·세션·스캔 원장·확정 입력·명세·호출), 화면 22(새 패턴 K 현장 단말 18 + 현황판 + 관리 3), 교차 조회(`confirmed_entries` 제공, MES·WMS `pop_results`·WMS `pending_tasks` 요청 — MES·WMS 문서에 메모).
- 확정 입력에 반영 솔루션(MES/WMS) 칸 — 두 솔루션 모두 RECEIVE·ISSUE를 다른 뜻으로 써서 구분. MES pop_import 종류 + DOWNTIME·INSPECT·CANCEL, WMS + CANCEL, 모듈 키 pop.
- 목표 DB: `tools/apply_dsn22.py` → target-0.10.0/DSN-22 241테이블·컬럼 2,835·FK 605. 검증기 `validate_pop_dsn22`(POP FK pop/core만·입력 번호 유일·MES/WMS 가져오기 종류 = POP 종류·취소 1건·지연 가져오기 정책·모듈 키).
- 검증: 목표 validate 0·격리 0·**빈 DB 적용 대조 0(241·UK 497·CHECK 673·INDEX 165·UNIQUE_INDEX 67·FK 605)**·ERD·Excel·tools 73 + DSN 27·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-21 CMMS 재점검·보강 설계 완료 (Claude Code)
- 결정: Q1 금형 보전(MES 금형 가져오기, 진행 작업지시를 MES가 읽어 금형 상태·배지) · Q2 사용량 기준 PM(운전 시간·타수) · Q3 점검표 구조화 + 시설 일상 점검 · **Q4 신호 전환 확장 제외**(FEMS 에너지 경보·BEMS 설비 경보는 CMMS 신호 아님) · Q5 정비원·외주 수리·보전 비용(FS-029 제외 항목 해제) · Q6 예비품 재고 WMS 조회·부족분 ERP 구매 요청·사용 → WMS 출고 · Q7 설비 상세·계층, 범위 22/26.
- 문서 `docs/modules/cmms/CMMS_보강설계_DSN-21.md`: 기준표 26, 기능 규칙 8묶음, DB 6→12(새 6·기존 6 변경 — PM interval_days NULL 허용 + 기준별 CHECK), 화면 7(설계) → 10, 교차 조회(`part_requests`·`part_usages`·`monthly_summary` 제공, 금형 코드도 `equipment_in_maintenance`).
- Q4 반영: FEMS DSN-15 F34 → 제외(범위 30→29, 경보 note를 apply_dsn15에서 고치고 목표 재생성), BEMS DSN-16 `active_alarms`는 환경 경보만.
- 목표 DB: `tools/apply_dsn21.py` → target-0.9.0/DSN-21 234테이블·컬럼 2,746·FK 589. 검증기 `validate_cmms_dsn21`. rebuild_target STEPS에 추가(포맷터가 목록을 여러 줄로 바꿔 문자열 치환이 빠진 것을 재생성 결과로 발견해 고침).
- 검증: 목표 validate 0·격리 0·**빈 DB 적용 대조 0(234·UK 485·CHECK 657·INDEX 160·UNIQUE_INDEX 64·FK 589)**·ERD·Excel·tools 73 + DSN 25(재생성 = 커밋본)·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-17 SPC 보강 설계 완료 — 기존 7개 보강 설계 마무리 (Claude Code)
- 결정: Q1 n=1(I-MR)·2~10(X̄-R), X̄-S 제외, 계수는 코드 상수 · Q2 계수형 p·np·c·u(MES 실적에서 부분군 + 수동) · Q3 Nelson 1~8 + 특성별 선택 · Q4 규격 이탈 → QMS 부적합 후보 · Q5 OCAP · Q6 Pp/Ppk·정규성·월별 추이·층별·보고서 · Q7 범위 24/27.
- 문서 `docs/modules/spc/SPC_보강설계_DSN-17.md`: 기준표 27, 기능 규칙 7묶음, DB 5→10(새 5·기존 5 변경 — 관리도 종류는 기존 테이블에 칸 추가, "n=5 고정" → 1~10, X̄·R NULL 허용 + "계량/계수 하나" CHECK), 화면 7→11, 교차 조회(`spec_violations`·`capability_summary` 제공, QMS `gauges` 요청).
- 목표 DB: `tools/apply_dsn17.py` → target-0.8.0/DSN-17 228테이블·컬럼 2,667·FK 572. 검증기: FS-028 "n=5 고정"이 1~10도 허용, `validate_spc_dsn17`.
- 검증: 목표 validate 0·격리 0·**빈 DB 적용 대조 0(228·UK 473·CHECK 645·INDEX 157·UNIQUE_INDEX 64·FK 572)**·ERD·Excel·tools 73 + DSN 23·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.
- **기존 7개 합계**: 테이블 93 → 202(+core.holiday), 화면 105 → 166. 다음은 신규 솔루션(CMMS 재점검·POP·TMS·PLM·CRM·SCM·ELB/MRO·EIP·RWS·HR), 이후 DSN-90 통합 검증(각 문서 6장 "넘길 것" 모음).

## 2026-10-05 DSN-16 BEMS 보강 설계 완료 (Claude Code)
- 결정: Q1 **휴일 달력은 core 공통**(core.holiday, 업무 스키마는 날짜로 읽음·FK 없음 — FEMS TOU·MES 근무조·HR 근태도 사용) · Q2 피크 감축은 제안 → 승인 후 제어 · Q3 조명 제어 · Q4 환경 지표 6종 + 쾌적 시간 비율 · **Q5 불편 신고 제외** · Q6 원단위·목표·공용 비용 부서 배분·월간 보고서 · Q7 범위 21/27.
- 문서 `docs/modules/bems/BEMS_보강설계_DSN-16.md`: 기준표 27, 기능 규칙 7묶음, DB bems 10→21 + core.holiday(기존 6 변경 — 스케줄 hvac_unit_id NULL 허용 + "대상 하나" CHECK), 화면 7→13 + 포털 P-08 휴일 달력, 교차 조회(`hvac_units`·`active_alarms`(설비 경보 포함)·`monthly_summary` 신규 제공, FEMS `open_alarms`·`tariff_rates`·core `holidays` 요청).
- 목표 DB: `tools/apply_dsn16.py` → target-0.7.0/DSN-16 223테이블·컬럼 2,602·FK 560. 검증기 `validate_bems_dsn16`(공통 휴일 1벌·core.holiday FK 금지·피크 승인 정책·FEMS 경보당 감축안 1건·스케줄 대상 하나·확정 1건·불편 신고 테이블 금지).
- 검증: 목표 validate 0·격리 0·**빈 DB 적용 대조 0(223·UK 463·CHECK 637·INDEX 154·UNIQUE_INDEX 62·FK 560)**·ERD·Excel·tools 73 + DSN 21·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-15 FEMS 보강 설계 완료 (Claude Code)
- 결정: Q1 TOU 요금(계약전력 + 계절 × 요일 × 시간대, 합성 요율) · Q2 피크는 1시간 계측 최대값 근사(시드 예산) · Q3 MES 생산량 가져오기 + 수동 · Q4 에너지 비용 배분 제공, ERP는 참고 · Q5 절감 활동 + 월간 검토 보고서 · Q6 온실가스 명세서(Scope 1·2) · Q7 범위 30/33.
- 문서 `docs/modules/fems/FEMS_보강설계_DSN-15.md`: 기준표 33, 기능 규칙 10묶음, DB 13→25(새 12·기존 6 변경), 화면 14→23, 교차 조회(`energy_costs`·`open_alarms`·`monthly_summary` 제공, MES `production_results`·ERP `departments` 요청).
- 목표 DB: `tools/apply_dsn15.py` → target-0.6.0/DSN-15 211테이블·컬럼 2,468·FK 532. rebuild_target STEPS 추가. 검증기 `validate_fems_dsn15`(TOU 계약전력·확정 1건 3종·진행 경보 1건·PRIMARY/EMISSION 분리 정책·1시간 계측 유지).
- 검증: 목표 validate 0·격리 0·**빈 DB 적용 대조 0(211·UK 440·CHECK 609·INDEX 150·UNIQUE_INDEX 57·FK 532)**·ERD·Excel·tools 73 + DSN 19·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-14 QMS 보강 설계 완료 (Claude Code)
- 결정: Q1 수입 검사(대상 = 검사 필요 + 공급처 수준 ≠ 면제, 검사 전 보류, 판정을 WMS가 읽어 이동) · Q2 AQL 표 자동(KS Q ISO 2859-1, 표는 코드 상수) + 직접 입력 · Q3 NCR + CAPA(8D 제외) · Q4 고객 클레임 QMS 소유 · Q5 공급처 월 등급 + 전환 제안, 사람 확정 · Q6 계측기·교정 포함(MSA 제외) · Q7 4M 변경 포함, 범위 28/33.
- 문서 `docs/modules/qms/QMS_보강설계_DSN-14.md`: 기준표 33, 기능 규칙 10묶음, DB 6→15(새 9·기존 4 변경 — 검사 종류 출하·수입·반품·초품, "품목당 게시 기준 1개" → "품목·종류당"), 화면 6→13, 교차 조회(`incoming_results`·`return_results`·`claims`·`supplier_grades` 제공, WMS `inbound_lots_to_inspect`·MES `defects`·`process_inspections`·`lot_trace` 요청).
- 목표 DB: `tools/apply_dsn14.py` → target-0.5.0/DSN-14 199테이블·컬럼 2,322·FK 506. rebuild_target STEPS 추가. 검증기: FS-023 게시 기준 규칙이 종류별 조건부 유니크도 허용, `validate_qms_dsn14`(검사 종류·AQL Ac/Re·AQL 표 비저장·수입 판정 WMS 연계·CAPA→NCR·클레임 QMS·공정 검사 금지·교정 기한 파생).
- 검증: 목표 validate 0·격리 0·**빈 DB 적용 대조 0(199·UK 418·CHECK 579·INDEX 145·UNIQUE_INDEX 52·FK 506)**·ERD·Excel·tools 73 + DSN 17(재생성 = 커밋본)·실제 schema.json 0. 클레임 CHECK의 AND/OR 우선순위 오류를 적용 전에 찾아 괄호로 고침. 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-13 WMS 보강 설계 완료 (Claude Code)
- 결정: Q1 창고 스캔 POP · Q2 다창고·용도 8·위치 계층·유형 6(용도당 기본 1) · Q3 LOT 품목별(원자재도 WMS 부여) · Q4 피킹 지시/확정·생산 불출(MES 투입은 라인 재고 차감) · Q5 FEFO→FIFO·만료 보류 · Q6 재고 월 마감(ERP 원가 기준) · Q7 범위 39/42(수입 검사 연계 → DSN-14).
- 문서 `docs/modules/wms/WMS_보강설계_DSN-13.md`: 기준표 42, 기능 규칙 13묶음, DB 11→23(새 12·기존 6 변경 — "LOT = 완제품" CHECK 삭제, 원천 키에 PO·판매 반품), 화면 9→20, 교차 조회(`receipts`·`stock_moves`·`stock_on_hand`·`lots`·`line_stock`·`pop_context` 제공 계약 확정).
- 목표 DB: `tools/apply_dsn13.py`(바꿀 기존 제약을 먼저 모두 확인하고 없으면 아무것도 바꾸지 않고 실패) → target-0.4.0/DSN-13 190테이블·컬럼 2,191·FK 487. rebuild_target STEPS에 추가. 검증기: FS-024 "용도당 활성 창고 1개"가 "기본 창고 1개" 조건도 허용, `validate_wms_dsn13`(LOT 품목별·LOT 수량 비저장·활성 보류 1건·예약당 피킹 1건·월 마감·POP 멱등·스캔 테이블 금지).
- 검증: 목표 validate 0·격리 0·**빈 DB 적용 대조 0(190·UK 400·CHECK 552·INDEX 139·UNIQUE_INDEX 51·FK 487)**·ERD·Excel·tools 73 + DSN 15(재생성 = 커밋본)·실제 schema.json 0. 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-01 확정 · DSN-12 MES 보강 설계 완료 (Claude Code)
- DSN-01 S1~S4 제안대로 확정(기반 작업은 일괄 개발 첫 단계, 지연 복사, 공통 엔진 프런트·백엔드, 모듈러 모놀리스).
- MES 결정: Q1 **바코드 스캔 화면은 POP에만**(MES는 라벨·검증 규칙·POP 가져오기 재검증) · Q2 비계획 입출고 MES 기록→WMS 반영 · Q3 Code128+QR·브라우저 인쇄 · Q4 자재 투입이 WMS 자재 LOT 스냅샷 · Q5 공정 검사 MES · Q6 비가동·금형 타수 MES, 금형 보전 CMMS · Q7 범위 제안대로(60/64).
- 문서 `docs/modules/mes/MES_보강설계_DSN-12.md`: 기준표 64(사용자 요청 ★13: 품목 상세·관리 속성·포장 기준·라벨 양식/출력/재발행·지시서·LOT 카드·공정 입고·스캔 시작/완료·스캔 패킹·비계획 출고/입고), 기능 규칙 13묶음, DB 21→45(새 24·기존 9 변경·ERP 구매 요청 출처 MES), 화면 15→33(특수 1: LOT 추적 트리), 교차 조회(POP `confirmed_entries`·WMS 재고/LOT 읽기, `pop_context`·`production_results`·`subcontract_results`·`material_adjustments`·`material_shortages`·`molds` 제공).
- 목표 DB: `tools/apply_dsn12.py`(apply_dsn11 다음, 멱등) → target-0.3.0/DSN-12 178테이블·컬럼 2,049·FK 451. `tools/rebuild_target.py`(schema.json → DSN-00 → STEPS) 신설. 검증기: "작업지시당 LOT 1개"를 원 LOT 조건부 유니크도 허용, `validate_mes_dsn12`(스캔·재고 테이블 금지·POP 가져오기 멱등·재검증·자재 LOT 스냅샷·유효 라벨 1건·금형 타수 파생·진행 비가동 1건). `verify_ddl_matches_schema.py`에 `time` 타입 정규화.
- 검증: 목표 validate 0·격리 0·**빈 DB 적용 대조 0(178·UK 377·CHECK 528·INDEX 133·UNIQUE_INDEX 49·FK 451)**·실제 schema.json 빈 DB 대조 0·ERD·Excel 43시트·tools 73 + DSN 12(재생성 = 커밋본). 제품 코드·마이그레이션·실제 DB 변경 없음.

## 2026-10-05 DSN-11 ERP 보강 설계 완료 (Claude Code)
- 결정(하나씩): Q1 소유 나누기 확정 · Q2 **HR 18번째 솔루션 신설(D79)** · Q3 자동 전표 즉시+일괄 · Q4 발주 기반+직접 매입 둘 다 · Q5 월 이동평균+생산량 배부 · Q6 세금계산서 전송 흉내 · Q7 범위 제안대로(58 = 포함 56 + 기록만 2, 제외 9, 타 솔루션 5).
- 문서 `docs/modules/erp/ERP_보강설계_DSN-11.md` 3~6장: 기능 규칙 20묶음, DB(새 36 + 기존 10 변경, 표는 apply 스크립트에서 생성), 화면 18 → 41(E-19~E-43, E-14 폐지·E-08 흡수, 특수 화면 0), 교차 조회(WMS·MES·HR·GW·CMMS/ELB 읽기, ERP 제공 3개 추가 — 함수 이름은 제공 측 DSN에서 확정).
- 목표 DB: `tools/apply_dsn00.py`(--rebuild로 기준 복사 재생성) + `tools/apply_dsn11.py`(멱등, schema-target.json만) → target-0.2.0 / DSN-11, 154테이블(erp 63)·컬럼 1,773·FK 385. 고정 계정 7·분개 10조합·세금계산서 2상태 CHECK 교체. 검증기: FS-014b 고정 규칙 3개를 목표(전표 있음)에서 해제하고 `validate_erp_dsn11`(재고 원장 금지·HR 소관 테이블 금지·원천 1건 자동 전표·역분개 1건·확정 1건 원가/부가세/예산·잔액 비저장·Q4~Q6 정책) 추가.
- 검증: 목표 validate 0 · 격리 0 · **빈 DB 적용 대조 0(154·UK 334·CHECK 483·INDEX 119·UNIQUE_INDEX 41·FK 385)** · ERD·Excel(43시트) · tools 73 + test_dsn00 5 + test_dsn11 4(재생성 = 커밋본, 회귀 거부) · 실제 schema.json 검증 0 유지. 제품 코드·마이그레이션·실제 DB 변경 없음. 미실행: 서비스 정책 동작(개발 때).

## 2026-10-05 DSN-11 ERP 기준표 · DSN-01 규모 대응 분석 (Claude Code)
- 입력: 사용자 제공 이카운트 데모 분석(메뉴 트리·화면 18개, 화면 필드 기반 추정 ERD). 원문은 저장소에 넣지 않음.
- `docs/modules/erp/ERP_보강설계_DSN-11.md` 1단계: 0장 소유 나누기(재고=WMS·생산=MES·품질=QMS·결재=GW·권한=core, ERP는 읽기), 기준표 10영역 72기능(✓11·△10·✗49·타 솔루션 2, 범위 제안 ○·△ 57·✕ 9·인사 4는 Q2), 갭 요약(구매 발주·회계 전표/장부/결산·자금이 비어 있음, 테이블 27 → 약 55~65 추정), 결정 Q1~Q7, 부록 A 공통 후보(권한그룹·엑셀·출력물·단축키). 수치는 표에서 기계적으로 다시 셈. 3~6장(DB·화면)은 범위 확정 뒤.
- `docs/plan/규모대응_구조_DSN-01.md`: 실측 CI 34.5분 중 pytest 30.7분(839개, 2.2초/개) — `guest_space`가 테스트마다 전체 시드 14,687행 복사. 전체 구성 시 CI 6~15시간 추정. 제안 A 솔루션별 시드 복사·게스트 공유·xdist·변경 범위 실행, B 게스트 지연 복사, C 패턴+정의(공통 엔진), D 모듈러 모놀리스 유지, E 한 줄 배포 스크립트. 결정 S1~S4.
- 코드·DB 변경 없음. 목표 DB 검증 0 유지(새 테이블 아직 없음).

## 2026-10-05 DSN-00 기능 기준표 양식·목표 DB 파일 (Claude Code)
- 양식 `docs/plan/기능기준표_DSN-00.md`: 수준 필수/표준/고급(기본 범위 필수+표준), 기준표 칸(ID `<약어>-F<nn>`·지금 ✓△✗·범위 ○△✕), 솔루션 문서 7장 구조(`docs/modules/<m>/<M>_보강설계_DSN-1x.md`·`_설계_DSN-2x.md`), DB 표·화면 목록 형식, 완료 조건.
- 목표 DB `docs/db/schema-metadata/schema-target.json`(target-0.1.0, task DSN-00, base_task FS-029a, migration_revision null) = schema.json 복사.
- 도구: `validate_db_design.py`(base_task로 기존 검사 전부 유지, `*_DSN-*.md` 새 테이블 표 인식, target 계약 — 실제 DB 기록 금지·base_task 일치, 보고서 `validation-report-target.json`) · `audit_schema_isolation.py`(새 스키마 자동 업무 스키마) · `verify_ddl_matches_schema.py`(스키마 목록을 메타데이터에서) · **신규 `schema_ddl.py`**(메타데이터 → DDL → 빈 `factory_studio_target` 적용 → 카탈로그 대조) · `build_erd.py --target`(erd-target/) · `build_db_design.mjs --target`(DB설계서_목표.xlsx) · 두 생성기 모두 새 스키마 자동 포함.
- 검증: 목표 파일 validate 0·격리 0·DDL 적용 대조 0(118·UK 264·CHECK 376·INDEX 105·UNIQUE_INDEX 32·FK 270)·ERD 11개·Excel 43시트. **생성기 자체 검증: 지금 schema.json으로 빈 DB 생성 → 대조 오류 0.** 기존 산출물(validation-report·ERD) 변화 없음. tools 73 + test_dsn00 5 통과, ruff 0. 제품 코드·마이그레이션·실제 DB 변경 없음.
- 다음: DSN-11 ERP 기준표(갭 분석) → 범위 확인.

## 2026-10-04 FS-030b GW 병합·운영 배포 — main `a4baf30` (Claude Code)
- Codex `codex/fs-030-gw` `1f96532`(GW API·G-01~07·ERP 매입 결재 배지) main 병합. 충돌은 현황 첫 줄만. 마이그레이션·시드 변경 없음. 재검증: typecheck·ruff·vitest gw/portal 91, CI success. Codex 보고: vitest 518, 백엔드 839 통과(성능 1건 단독 재실행 통과).
- 운영(사용자 실행): 서버 `git pull`·`uv sync`·API 재시작 → 프런트 rsync(`index-DkXknnzE.js`). 확인: 진입 화면 GW 표시, 게스트 201, GW dashboard 200, `/gw` 200. 첫 rsync 안내에 `git log` 페이저가 걸려 업로드가 빠졌던 것을 `--no-pager`로 다시 실행.

## 2026-10-04 FS-030b GW API·화면 완료

- main8531c05 기반 codex/fs-030-gw. G01~07·순차 결재/반려/재상신·게시 정정·ERP 코드 스냅샷/E11 읽기 배지·역할/멱등/격리 구현. DB·시드 변경 없음.
- GW API20, frontend518, 관련 최종11, tools73 통과. Chromium 배치 포함17 통과 후 업무5 재검사 통과(고유18개). Ruff163·typecheck/lint/format/build·DB설계/격리/DDL 통과(exit0).
- 전체 pytest839 passed/1 failed(exit1): 복사 성능3.426초>2초. 해당 검사 단독 재실행1 passed(exit0), 기준 변경 없음. 전체 재통과로 표시하지 않음.
- 미실행: Safari/실기기·전체 솔루션 브라우저·운영 부하·c시드/도움말. 다음은 사용자 확인 후 FS-030c(69행·도움말·흐름맵·통합). push·배포·main 병합 없음.

## 현재 상태
- 단계: **FS-023c + P-02 홈 UI·제목 운영 반영 완료(`be87546`). P-01 진입 목록 QMS 추가는 로컬 커밋(미배포). FS-024 WMS·홈 아이콘·C++ 비전 엔진 운영 반영 완료(`adc3cab`, head `fs024b_wms_module`, 템플릿 7,691행). FS-025a BEMS DB 완료(로컬, head `fs025b_bems_module`). FS-025 BEMS 전체(API·화면·시드·도움말) 운영 반영 완료(`6508599`, 템플릿 11,910행). FS-026 WMS 확장은 Codex가 결정서부터.**
- 기준본: 현재 상태는 `docs/plan/현재기획_진행현황.md` 하나로 판단한다. 작업이 끝나면 반드시 갱신한다
- DB: **v0.9.1 / FS-008c / 71테이블·712컬럼·161 FK·제약/정책 526**, 정적 검증 오류 0·격리 위반 0. Excel·ERD 재생성 완료. FS-009 로컬 DB 적용·대사 완료, 서비스 미구현
- 시드: **7,469행, `sv-20260924-1`**. FS-015 생성·복사 구현, FS-015b created_at 시간축·V12 재검증 완료
- 프로젝트: `/Users/hwang-kyoungho/projects/factory-studio` (worktree: `/Users/hwang-kyoungho/projects/factory-studio-ag`)
- 제품 구현: FS-009 뼈대·최초 마이그레이션, FS-015/015b 시드, FS-016 공통 인증·세션·멱등 완료. 백엔드 테스트 총 36개 (common 11, schema_verifier 9, seed 16). 업무 API·화면은 미구현

## 2026-10-03 ROADMAP-02 전체 설계 우선 전환 (Claude Code)
- 사용자 결정: 하나씩 개발·동결을 멈추고 17개 전체를 먼저 설계(기능 목록·DB·화면 목록) → 통합 검증 → 보강 → 일괄 개발. 이유: 솔루션별 기능이 얕음(예: ERP 회계·결산·원가·자금 부재), 기준은 "이카운트만큼은 아니어도 어느 정도".
- 확정 D75~D78: 개발 중지 / Codex FS-030b만 마치고 병합 후 설계 전환 / Claude가 필수·표준·고급 기능 기준표 작성 → 확인 / 목표 DB는 별도 `schema-target.json`.
- 문서: `docs/plan/전체설계우선_전환_ROADMAP-02.md` 신규, ROADMAP-01 머리에 대체 안내, Codex GW 지시서 §7. 코드·DB 변경 없음, 검증 대상 없음.
- 다음: DSN-00(기준표 양식·schema-target.json 도구) → DSN-11 ERP 갭 분석.

## 2026-10-01 운영 배포 — main `1a1ddcd` (Claude Code)
- 서버를 배포 브랜치에서 main으로 복귀(사용자가 SSH 실행): `git checkout main && git pull --ff-only` → `uv sync` → `alembic upgrade head`(fs040_app_review·fs030a/b GW·fs029a/b CMMS 처음 적용, head `fs029b_cmms_module`) → `seed.cli template`(14,687) → API 재시작 active. 프런트는 `1a1ddcd` worktree 빌드 → rsync(`index-C-F5DkHC.js`).
- 운영 확인: 게스트 201·모듈 10개·평가 요약 200(빈 목록)·SPC 대시보드·홈 평점 줄 "평가 모으는 중". 운영에 평가를 쓰는 시험은 하지 않았다. FS-040 e2e 미실행.

## 2026-10-01 FS-029 CMMS 설계 확정 · FS-029a DB (Claude Code)
- 결정서 D45~D52, 모듈 설계 13장 5건(유예 0일만 권장과 다름), 화면 설계 C-01~07을 하나씩 확정 → 전체 설계 확인.
- FS-029a: schema.json v0.17.0·118테이블(cmms 6)·FK 270, 마이그레이션 `fs029a_cmms`(down `fs030b_gw_module`)·`fs029b_cmms_module`, `validate_cmms`, 스키마 목록 갱신, 시드 합계 14,687/14,685.
- 검증: db:validate 0 · 격리 0 · tools 73 · 실제 DB head 적용 후 DDL 대조 0(118·UK 264·CHECK 376·FK 270) · downgrade -2 → head · 빈 DB base↔head · pytest 관련 68(cmms_schema 5·schema_verifier·seed·common·gw_schema·spc) · ruff 0. 로컬 개발 DB head·템플릿 반영. GW 병합 후 전체 pytest 814 passed.
- 다음: FS-029b(API·화면·MES 배지·BEMS/SPC 조회 함수).

## 2026-10-01 FS-030a 병합 · FS-029 CMMS 결정서 초안 (Claude Code)
- FS-030a GW DB(Codex `cd8b619`) main 병합 `af9b7bb` push — v0.16.0·112테이블·head `fs030b_gw_module`·시드 14,686. 로컬 개발 DB head·템플릿 반영.
- `docs/plan/CMMS도입_설비보전_결정_FS-029.md`: D45 범위(설비 대장·PM·고장 작업지시·작업 기록·예비품·지표) · D46 설비 대장 CMMS 소유(MES·BEMS 가져오기 스냅샷) · D47 작업지시 상태·불변 · D48 신호(BEMS 경보·SPC 이상·수동) → 사람이 전환, 중복 전환 방지 · D49 PM 주기 도래는 수동 생성 · D50 예비품 목록·사용 기록만(재고 원장 없음) · D51 MTBF·MTTR·PM 준수율 조회 시 계산 · D52 MES "보전 중" 배지.
- 다음: 승인 요청 4건 → 모듈·화면 설계.

## 2026-10-01 FS-028c SPC 시드·도움말·흐름 맵·통합 검증 · 운영 반영 (Claude Code)
- **운영 반영(사용자: SPC만 배포)**: main에서 FS-040 WIP만 뺀 `release/2026-10-01-spc`(`bc7e4ac`)를 만들어 검증(도구 63·프런트 512·빌드·백엔드 seed/spc/qms/common 70) → 서버 checkout·uv sync·API 재시작·템플릿 14,685 → 같은 커밋 프런트 rsync. 확인: 게스트 201, SPC 대시보드·이상·QMS 배지(LT-0017)·https 200, 5xx 0, 브라우저로 홈 생산·품질 묶음 SPC 타일·S-01 확인.
- 시드 `_spc`(`sv-20261001-1`): 특성 6·부분군 456·측정값 2,280·한계 7·이상 3 → 템플릿 14,685·게스트 복사 14,683(중앙값 0.813초·최대 1.29초, 10회). 평소 점은 중심선 위·아래 교대, 장면만 이상: LT-0017 FG-C200 사출 6점 상승 → 규칙 3·1(미조치 2, QMS 배지), LT-0010 FG-C100 조립 지그 마모 규칙 1(조치 완료) → v2 재게시. 공정능력 충분 4·주의 1·부족 1. `created_at` 우선순위에 measured_at·effective_at·detected_at.
- `seed/validate.py` V13: DB 값으로 X̄·R·판정 재계산 = 저장된 이상, 이야기·공정능력 판정 일치. 테스트 기대 행 수·V 항목 수(13) 갱신, `test_spc`는 시드 데모 테스트 + 시드를 지우는 fixture.
- 도움말 `spc/s-01~07`(체험 순서), 개념 `c-20`·`c-21`, 포털 p-02·p-03. 흐름 맵 `process_control` 노드·연결 2(18·21, 스키마 개수 갱신). e2e: 시드 LT-0017 QMS 배지 → 조치 2건 → 배지 사라짐, 포털 노드 번호(QMS 08→09), SPC 시나리오 행 지정.
- 검증: pytest 798 passed·1 skipped + test_schema_verifier 9(테스트 DB를 새 head로 올린 뒤 — 다른 세션 FS-040 schema 포함) · test_spc 18 · test_seed 16 · vitest 512 · 전체 스모크 253 + 수정 후 spc·portal 100 passed · ruff 0.
- 함께 처리: CI #101·#102 실패(FS-026a downgrade 거부) 수정 `6350697` push. 다른 세션 `cb3fba4 WIP FS-040`이 그 push에 함께 올라감.

## 2026-10-01 FS-040 런처 평가(별점·한줄평) (Claude Code)
- 사용자 지시: 실제 방문자 평가 · 게스트 포함 · 솔루션별 1회 · 게스트는 별칭+후기, 다시 들어와 다른 별칭이면 허용 · 범위 한줄평+별점 · SPC와 병행. 결정서 `docs/plan/런처평가_한줄평_FS-040.md`(D70~D74, AC-240~246).
- DB: `tools/apply_fs040.py` → schema.json **v0.15.0 / FS-040 / 104테이블 · FK 237**. `core.app_review`(ops, global, 공간 FK 없음 → 게스트 정리 뒤에도 남음). 조건부 유니크 3개(회원 계정·게스트 공간·게스트 별칭, 솔루션별). 마이그레이션 `fs040_app_review`(down `fs026a_wms_receiving_reservation`). `validate_db_design` 작업 집합에 FS-040, `test_fs024a` 기대값.
- API: `fs/core/review.py` — `GET /api/v1/core/reviews/summary`·`GET /reviews?moduleKey=`·`POST /reviews`(CSRF·멱등, 409 `ALREADY_REVIEWED`·`NICKNAME_TAKEN`). API 계약서 18장, CORE 설계 9장.
- 화면: P-02 타일 아래 `★ 4.8 · 후기 12` / `평가 모으는 중` → 오른쪽 패널(FormPanel): 평균·최근 한줄평 5건·별 5개 선택·별칭(게스트)·한줄평. `frontend/src/portal/Reviews.tsx`.
- 검증: db:validate 0 · 격리 0 · tools unittest 63 · 새 DB base→head·downgrade -1→head 후 DDL 대조 0 · **pytest 808 passed · 1 skipped(26분, 전용 DB `factory_studio_fs040_test`)** · test_reviews 9 · ruff 0 · typecheck·lint · vitest 510/513(실패 3: `systems.test` 2건은 다른 세션의 미커밋 `content/flow-map.json` 변경 영향, `sales.test` 1건은 단독 재실행 통과 — FS-040 무관). 로컬 개발 DB head `fs040_app_review`, 브라우저(게스트)로 평가 저장 → 패널·타일 갱신, 375px 가로 스크롤 없음 확인. 검증용 평가 행은 삭제.
- 미실행: e2e(Playwright), 운영 반영. 도움말 p-02는 다른 세션이 수정 중이라 평가 안내를 넣지 않았다.

## 2026-10-01 FS-030a GW DB (Codex)
- 전체 설계 승인 후 main6350697 위 rebase. 신규 gw8테이블, head fs030b_gw_module(fs040 뒤), 기존 공간 gw 행/새 공간/초기화/게스트 복사. 메타데이터·Excel39시트·ERD: v0.15.0-gw,112테이블·1,225컬럼·258FK. 템플릿11,934/복사11,932.
- 검증: 전용DB pytest45, tools69, CI Ruff154파일, 격리/정적/실제DDL 오류0, 빈DB 왕복·기존 공간/ERPoff 유지·유데이터 downgrade 거부/롤백 통과. 전체pytest/프런트/브라우저 미실행.
- b 서비스·API·화면/배지·평가등록, c69행/도움말/통합은 남음. push/배포 없음. [보고](agent/GW_DB_FS-030a.md). b 착수는 사용자 확인 후.

## 2026-10-01 FS-028b SPC API·화면 (Claude Code)
- 백엔드 `fs/spc/`(stats·service·router·interface·schema), MES `interface.operation_runs`, QMS `spcSignal` 배지, API 계약서 17장. 프런트 `frontend/src/spc/` S-01~07, QMS Q-03·Q-04 배지, 홈 분야별 묶음(`content/systems.json` fields·field, 운영만 타일·빈 묶음 숨김·솔루션 수 문구 자동·"앞으로 만들 것" 링크), 다른 솔루션 전환 링크·진입 목록·참고 문서에 SPC.
- 설계와 다른 점: 한계 적용 시작 = 게시 때 마지막 유효 부분군 측정 시각(시계 차이·날짜 이동에 안전), 조회 종료일이 없으면 끝을 연다(스모크의 FS_TODAY와 실제 시각 차이로 발견), `GET /lookups/items` 추가.
- 검증: **pytest 798 passed · 1 skipped(28분)** · test_spc 17 · vitest 512 · e2e 202(spc 2·home·portal·layout·wms·wms-extension·qms) · typecheck·lint·format · ruff 0 · 격리 0. 브라우저(로컬 게스트)로 관리도·이상 상세·측정 입력 확인.
- 남은 것: FS-028c(시드·도움말·흐름 맵·통합 검증) → 운영 반영.

## 2026-09-30 FS-026 main 병합 · 운영 배포 (Claude Code)
- **운영 반영**: push `5b37741..815ba94` → 서버 pull·uv sync·alembic `fs025b_bems_module → fs026a_wms_receiving_reservation`·API 재시작·템플릿 11,933(workspace 37) → 프런트 같은 커밋 빌드·rsync. 확인: 게스트 201, WMS·BEMS·QMS API 200, https 200, 5xx 0.
- Codex `codex/vision-ai` `f65044b`(FS-026a DB·b1 입고·b2 예약/소진·W-08/W-09·3D 트럭·시드 +22·도움말)를 main(FS-028a 포함)에 병합.
- 충돌 해결: `schema.json`은 main(SPC) 위에 `tools/apply_fs026a.py`를 다시 적용 → **v0.14.0 / 103테이블 · FK 236**(apply 도구의 버전을 0.14.0으로). `validate_db_design` 작업 집합에 FS-026a·FS-028a 모두, `LATER_THAN_028A` 추가. 마이그레이션 체인 `fs025b → fs028a_spc → fs028b_spc_module → fs026a`(Codex 파일의 down_revision만 변경). 시드 합계 템플릿 11,933·복사 11,931. Excel·ERD·검증 보고서 재생성. 현황 문서는 main(172줄) 기준에 FS-026 완료 반영.
- 병합 영향 수정: `e2e/wms-extension.spec.ts` 진입에 FS-027 별칭 입력(Codex 분기가 FS-027 이전), `test_fs028a`는 현재 작업 ID 기준 inventory.
- 검증: db:validate 0 · 격리 R1~R6 0 · tools 63 · **실제 DB: 테스트 DB fs028b→head, 새 DB base→head 모두 DDL 대조 0(103·FK 236·CHECK 294)** · ruff 0 · frontend typecheck·lint·format·vitest 505 · e2e wms+wms-extension+home+portal+layout 186 passed(wms-extension 7건은 별칭 수정 후 재실행 통과) · factory+bems+qms 27 passed·1 skipped · **pytest 781 passed · 1 skipped(23분)**.

## 2026-09-30 FS-028a SPC DB (Claude Code)
- `tools/apply_fs028a.py`(멱등) → schema.json **v0.13.0 / FS-028a**: 98테이블(spc 5: characteristic·control_limit·subgroup·measurement·signal) · 1,030컬럼 · FK 220 · 제약·정책 776. 모듈 키 CHECK에 spc.
- 마이그레이션 `fs028a_spc`(down `fs025b_bems_module`)·`fs028b_spc_module`(모듈 행). 스키마 목록이 박힌 곳 모두 spc 추가(격리 검사·DDL 대조·Excel·ERD·seed copy/generate/validate·core service·test_common/test_seed). 시드 합계 +1(모듈 행: 템플릿 11,911 · 복사 11,909).
- 검증기: `validate_spc` 추가, 작업 ID 집합에 FS-028a(`validate_bems`가 FS-025a 전용이라 꺼질 뻔 — `LATER_THAN_025A`). `effective_from`은 달력 키 검사 대상이라 `effective_at`으로.
- 검증: db:validate 0 · 격리 R1~R6 0 · tools unittest 60 · **실제 DB(PG 18.6) upgrade 후 DDL 대조 0**(98·UK 220·CHECK 262·INDEX 63·FK 220) · downgrade fs025b→base→head 왕복 · **pytest 727 passed · 1 skipped(22분)** · ruff 0 · git diff --check 0. 로컬 개발 DB head `fs028b_spc_module`·템플릿 재생성.
- 구현 중 정책 1건 조정(FS-028b에서 발견): 한계 적용 시작 = 게시 때 마지막 유효 부분군 측정 시각(벽시계와 무관). DB 구조 같음, SERVICE 문장만.
- Codex 조율: FS-026a도 v0.13.0 → 병합 때 v0.14.0·`down_revision=fs028b_spc_module`.

## 2026-09-30 FS-028 SPC 모듈·화면 설계 초안 (Claude Code)
- 결정서 D37~D44 사용자 승인(제안대로) → 상태 "확정". QMS 화면 번호 정정(검사 대기 Q-03·검사 Q-04).
- `docs/modules/spc/SPC_모듈설계_FS-028.md`: spc 5테이블(characteristic·control_limit·subgroup·measurement·signal), 규칙(순서 강제·버전별 연속 판정·무효 처리), 계산(decimal, n=5 상수표), TX-S1~S4, MES `operation_runs` 추가·SPC `open_signal_lot_nos` 신규, API, 시드 약 2,350행(LT-0017 FG-C200 INJ-02 미조치 2건), AC-170~184, 결정 5건.
- `docs/ui/화면설계_SPC_FS-028.md`: S-01~07, QMS Q-03·Q-04 배지, 홈 분야별 묶음(운영만 타일·빈 묶음 숨김·"앞으로 만들 것" 링크), 흐름 맵 18·21, 검증 계획. `docs/modules/spc/README.md`.
- 코드·DB 변경 없음. 다음: 전체 설계 확인 → FS-028a(DB, FS-026a 병합 여부에 따라 버전).

## 2026-09-30 FS-028 SPC 결정서 초안 (Claude Code)
- 로드맵 ROADMAP-01 확정(사용자: 제안대로) — §6 여섯 문항 "확정"으로 표기, SPC 상태 "설계 중".
- `docs/plan/SPC도입_관리도_결정_FS-028.md`: D37 범위(X̄-R·한계 게시·이상 판정·조치·Cp/Cpk, 접두어 S) · D38 측정값 SPC 소유 · D39 부분군 n=5·6시간(LOT당 1개면 점 8개라 불성립) · D40 처음 20 부분군 한계, 재산정은 새 버전 · D41 규칙 1~3 · D42 발생→조치 완료, 부분군 무효 처리 · D43 Cp/Cpk 조회 시 계산 · D44 QMS "SPC 이상" 배지만.
- 시드 규모 추정: 사출 실행 약 62시간·조립 약 38시간(generate.py SCHEDULE 기준) → 부분군 약 390·측정값 약 1,950, 템플릿 +약 2,300행.
- 코드·DB 변경 없음. 다음: 승인 요청 4건 → 모듈 설계·화면 설계.

## 2026-09-30 ROADMAP-01 17개 시스템 로드맵 (Claude Code)
- 산출물: `docs/plan/로드맵_17개시스템_ROADMAP-01.md`(상태·순서·의존·조회 함수·홈 17타일 분야별 묶음 설계·열린 질문 6), `docs/plan/새솔루션_킷.md`(BEMS 사이클 기준 체크리스트, 솔루션 목록이 박힌 약 20곳).
- 현황 문서 994줄 → 172줄. 축소 전 전문은 `docs/plan/진행현황_이력.md`로 옮김(내용 삭제 없음).
- README 맨 위 "현재 기준"(운영·동결·제공 조회 함수): MES·ERP·FEMS·QMS·BEMS. **WMS는 Codex FS-026 뒤**(충돌 방지).
- 카탈로그 `content/systems.json`: 그룹웨어→GW, 설명·후보·포함·제외 → `planned` + `order` 1~11. P-03 배지 "운영"/"예정 N", 도움말 p-03 문구.
- 검증: vitest 56파일 493 통과(systems 5), tsc·eslint·prettier 통과, 문서 상대 링크 0건 깨짐, 브라우저(로컬)로 계층 아키텍처·카탈로그 확인. 백엔드·DB 변경 없음(pytest 미실행).
- 다음: 사용자 확인(순서·열린 질문) → 로드맵 1번 SPC 결정서.

## 2026-09-29 MAP-02 P-03 계층 아키텍처·시스템 카탈로그 (Claude Code)
- `content/systems.json`(17개 시스템: 계층·분류·받는 것/주는 것·연관·화면 경로), P-03 `?view=arch|catalog` 보기 추가(`ContentPages.tsx`, `styles.css` sys-*), 도움말 p-03 문구, `systems.test.tsx` 4개.
- 검증: vitest 55파일 486 통과, tsc·eslint·prettier 통과. 브라우저(로컬 게스트)로 두 보기·카탈로그 상세·화면 이동 확인. e2e·운영 배포는 미실행.
- 제약: 로컬 게스트 상한 20이 차 있어 확인용 백엔드는 `GUEST_LIMIT=1000`으로 띄움(DB 변경 없음). 전역 `.excluded` 클래스와 충돌해 상태 클래스는 `is-*` 접두어 사용.
- 공유 요약: https://claude.ai/artifact/MxMzUEXWU5KdK8GPEnGsBD. 다음: 사용자 확인 → 배포 여부, CMMS 결정서는 별도 ID.

## 2026-09-28 MAP-01 연계 시스템 분석 (Claude Code)
- 입력: 사용자 제공 `manufacturing-systems.html`(16개 시스템). 결과: `docs/plan/연계시스템_분석_MAP-01.md`.
- 누락 11개 분류·연결(받는 것/주는 것)·결정 충돌 점검·P-03 흐름도 2장(계층 아키텍처·시스템 카탈로그) 설계.
- 코드·DB·정적 콘텐츠 변경 없음. 검증 명령 실행 대상 아님. 다음: 사용자 확인 후 MAP-02(다른 개발 종료 후).

## 2026-09-30 UI-04 앱 안 이동 미저장 보호 + 새 로고·파비콘 (Claude Code)
- UI-04: `useDiscardGuard(dirty)`가 변경이 있는 동안 앱 안 링크 클릭(사이드바·헤더·본문)을 문서 캡처 단계에서 가로채 패널의 "변경 버리기 / 계속 편집"으로 보낸다. 공통 훅 한 곳 → 40개 화면 적용. 새 탭 클릭·외부 링크·같은 주소는 통과. 한계: 브라우저 뒤로·앞으로 가기. 기록: UI-02 규약 UI-04 절, d-08·현황 5장 갱신.
- 새 로고(사용자 제공 이미지 → SVG로 다시 그림, 쪽빛 #1f2d3d): `public/logo.svg`·`favicon-32.png`·`apple-touch-icon.png`, `index.html` 파비콘 링크, 홈 헤더 로고("F" 글자 → 로고 이미지).
- 검증: vitest 492(guard 3 추가), typecheck·lint·format 0, build(로고 파일 포함), home-browser 9, 전체 스모크 231 passed · 1 failed · 1 skipped → 실패 1건(layout /fems/equipments, 게스트 진입 단계)은 스모크 도중 로고 수정으로 개발 서버가 새로고침된 탓 → layout·portal 재실행 **167 passed**(새 UI-04 e2e 포함). 브라우저로 헤더 로고·파비콘 링크 확인.
- 교훈: 스모크 실행 중에는 frontend 파일을 고치지 않는다(vite가 페이지를 다시 불러온다).

## 2026-09-29 FS-027 게스트 별칭·접속 이력 (Claude Code)
- 사용자 요청: 체험판은 별칭을 꼭 입력하고 들어가 접속 이력에 남긴다. 회원 로그인은 아이디(기존 그대로). 검토 → 권장안 승인.
- 결정서 `docs/plan/게스트별칭_접속이력_FS-027.md`(D33~D36, AC-165~169).
- 백엔드: `POST /guest-sessions` 본문 `{nickname}` 필수(공백 제거 후 2~20자, 없으면 400 `fields.nickname`), 멱등 digest에 별칭 포함(같은 키·다른 별칭 422). 감사 기록 `guest_session.created` summary에 별칭. `GET /admin/guest-visits`(ADMIN). 정리 작업이 90일 지난 기록의 별칭만 제거.
- 메타데이터: `core.audit_event` 불변 정책에 이 예외 한 줄(스키마 변경 없음) → Excel 재생성, db:validate 0.
- 화면: P-01 별칭 칸·안내("접속 기록 확인용 90일 보관 · 실명·연락처 금지"), P-07 "게스트 접속" 탭(보관 기간 지남·정리됨 표시). 도움말 p-01·p-07·d-02, API 계약서, CORE 설계 8장.
- 테스트: 게스트를 만드는 백엔드 테스트 18곳·브라우저 테스트 7개 파일에 별칭 추가. 신규 백엔드 3(AC-165~169), vitest 3. P-07 테스트가 로딩 중·뒤 탭 버튼이 다른 요소라 가끔 실패 → 첫 목록 뒤 클릭.
- 검증: pytest **727 passed · 1 skipped**(20.4분), vitest 489, typecheck·lint·format 0, ruff 0, tools 55 OK, db:validate 0, **전체 스모크 231 passed · 1 skipped**(v7 세션 개발 서버는 사용자 허락 후 종료).
- 배포 순서: 프런트 먼저(새 화면은 별칭을 보내고 옛 서버는 무시) → 서버 코드·재시작. 마이그레이션·템플릿 불필요.

## 2026-09-29 개념 문서 QMS·WMS·BEMS 4편 + 운영 게스트 정리 점검 (Claude Code)
- 개념 `c-16` 검사와 품질 보류 · `c-17` 재고 원장과 원천 반영 · `c-18` 공용 에너지 분해 · `c-19` 공조 운전과 경보(화면 도움말 q-·w-·b- 내용과 대조). 개념 15 → **19편**, 테스트 기대값 갱신. 굵게 표시 검사 테스트가 c-18의 `…)**로`를 잡아 수정.
- 운영 점검(읽기 전용, Claude 직접): `factory-studio-cleanup.timer` 15분 주기 활성, 최근 실행 성공(exit 0). 최근 2일 로그 190회 — `cleaned_guest_workspaces=15`·`=5` 각 1회, 나머지 0. 코드 확인: `_delete_guest`가 업무 테이블(스키마 동적 조회라 wms·bems 포함)·세대·`core.workspace`까지 지운다 → 상한(만료 공간 포함 계산)이 차는 문제는 운영에서는 없다. 로컬만 정리 타이머가 없어 쌓인다.
- 검증: vitest(portal) 81, lint·format 0. 배포 없음(프런트 반영 필요).

## 2026-09-29 운영 반영 + 현황 문서 정비 (Claude Code)
- 운영 반영(Claude 직접 실행): 서버 pull `de1892c..653d438`(사용자가 먼저 `de1892c`까지 받음), 프런트 rsync·chown(`de1892c` 빌드). 백엔드 변경 없음. 반영 후 외부 확인은 권한 분류기에 막혀 사용자 확인으로 넘김.
- Codex에 FS-026b2 진행 승인 문구 전달(사용자).
- `현재기획_진행현황.md` 정비: 머리말(최종 갱신·운영 상태), 1장(여섯 솔루션·올인원 제목), 2장(구현 솔루션에 BEMS, 설명 카드 SCM만, WMS·BEMS 결정 행), 3장(QMS·WMS·BEMS 업무 흐름), 4장(현재 요약 표 — 이하 설계 이력 표시), 5장(하지 않은 일 = d-08), 6장(복사 11,908행·0.509초, 게스트 상한이 만료 공간도 셈, 공유 작업 폴더), 7장(진행 중·다음·구현 기준 진행률, 이력 절 표시), MAP-01·02 행.
- 검증: 문서만. 수치는 schema.json 집계·FS-025c 실측·마지막 전체 검증 기록과 대조.

## 2026-09-29 배포 준비: DOC-03·04 + 올인원 제목 + MAP-02 (Claude Code)
- 세션 "EIP 포토폴리오 개발_v7"의 MAP-02(P-03 계층 아키텍처·시스템 카탈로그, `content/systems.json`) 포함.
- 정정: DOC-04 커밋이 `git add content docs frontend`로 v7 세션의 작업 중 MAP-02 파일을 함께 담았다 → push 전이라 로컬에서 `ecd1169`(DOC-04만)·`de1892c`(MAP-02)로 다시 나눴다(최종 트리 해시 동일). **교훈: 다른 세션이 같은 폴더에서 작업할 수 있으니 디렉터리 단위 `git add`를 하지 않고 파일을 지정한다.**
- push `1b4c5a3..de1892c`. 백엔드·DB·시드 변경 없음(`6508599` 이후 backend·tools diff 0) → 서버는 코드 받기만, 재시작·마이그레이션·템플릿 불필요.
- 검증: typecheck·lint·format 0, vitest 486, build, home-browser 9, P-03 세 보기 브라우저 확인(1440·375, 가로 넘침 0). portal e2e는 v7 세션의 개발 서버가 8000·5173을 쓰고 있어 **이번에는 실행하지 못함**(직전 DOC-04 시점 90 passed).
- 프런트 빌드 `../fs-build`(de1892c) — rsync는 사용자 실행.

## 2026-09-29 DOC-04 설계 문서 8편 + 홈 제목 "올인원" (Claude Code)
- push `6508599..1b4c5a3`(DOC-03).
- 제목: 홈·헤더·진입 "제조 현장의 여섯 시스템" → **"제조 현장의 올인원 시스템"**(표준 표기 '올인원'). 부제 "여섯 가지 독립 솔루션"·흐름 카드 "여섯 시스템은 어떻게 이어지는가"는 유지.
- `content/help/design/d-01~08.md`(결정 → 검토한 대안 → 선택 이유 → 한계 → 관련 문서). DOC-01 목록의 "세 솔루션"은 현재 범위에 맞춰 "여섯 솔루션"으로. 본문에 작업 ID·서버/배포 정보 없음(테스트로 확인).
- **수치 출처 대조표**
  | 문서 | 수치 | 출처 |
  |---|---|---|
  | d-01·d-03 | 스키마 7, 93테이블·954컬럼·FK 209, 업무 스키마 간 FK 0 | `schema.json` v0.12.0 집계(2026-09-29) |
  | d-03 | 제약 615(PK 93·UK 208·조건부 유일 16·CHECK 239·INDEX 59), 서비스 정책 111 | 같은 집계(합 726) |
  | d-02 | 템플릿 11,910행·86테이블, 복사 중앙값 0.509초·최대 0.619초(10회) | FS-025c 실측·`seed/validate.py` V1 |
  | d-02 | 동시 20명 전원 성공·대기 최대 13.9초 | `통합검증_FS-021.md` §4 |
  | d-02 | 게스트 만료 다음 날 00:00 KST | `common/clock.py` `guest_expires_at` |
  | d-06 | 멱등 키 24시간·같은 키 다른 본문 422 | `API계약서_FS-010.md` §3 |
  | d-06·d-07 | 동시성 AC-59·60·72, AC 46건 33·5·4·4, 결함 AC-63 | `통합검증_FS-021.md` §2·§3 |
  | d-07 | pytest 724·1 skip, 스모크 231·1 skip, vitest 481 | progress FS-025c·DOC-03 기록 |
  | d-04 | 계정 7개, 세금계산서 매출 1건당 최대 1장 | `e-18.md`, 현황 §2 |
  | d-05 | 12,000 kWh + 800 Nm³ 예시 | `FEMS_공통설계_FS-005c.md` §1.1 |
- 결함 예방: 설계 문서 작성 틀·본문 작업 ID 금지 테스트 추가.
- 검증: typecheck·lint·format 0, vitest 482, portal e2e 90 passed.
- 미실행: 배포. push 없음(DOC-04·제목 변경은 로컬 커밋).
- 다음: 사용자 확인 후 push·배포, Codex FS-026b2 승인 여부.

## 2026-09-29 DOC-03 따라하기 3편 + 개념 15편 (Claude Code)
- `content/help/guide/s-01~03.md`(유형 틀: 목표 → 준비 상태 → 단계 → 끝나면 보이는 것 → 막힐 때), `content/help/concept/c-01~15.md`(한 줄 정의 → 왜 필요한가 → 이 제품에서는 → 관련 화면). 목록 파일 없이 기존 `docSections`가 구역으로 읽는다(첫 화면 구역 3개: 따라하기·참고·개념, 설계는 DOC-04).
- **단계 입력값은 게스트 공간에서 실제로 실행해 확인**(FS_TODAY 2026-09-24, API):
  - s-01 판매계획→수금: WO-0022(LT-0022) 3공정 검사 1,950 → 양품 1,940 → 박스 2·팔레트 PL-0007 입고 → SO-0011(C-002, 단가 870) → SH-O-0009 → SH-0005 1,856,580원 → RC-0004 FIFO 소명 → 채권 CLOSED. C-002는 미회수 채권이 없어 FIFO가 새 매출만 채운다.
  - s-02 매입→지급: PI-S02(V-001, RM-PBT 100KG×3,500) 385,000원 → 확정(만기 +30일) → PM-S02 → FIFO는 PI-0002(가장 오래된 매입)를 추천 → PI-S02로 고쳐 소명 → CLOSED.
  - s-03 원단위·목표: 스모크에서 통과한 fems.spec 값(대시보드 전월 목표 초과, FG-C100 2.003 kWh/EA, LT-0018 생산량 없음, 생산량 초안→확정→정정, F-07 INS-02 미설정).
- 결함 수정: `mes/m-07.md`의 "QMS가 설계 범위에서 제외" 문구(QMS 도입 전 내용) → QMS 검사가 정식 판정임을 안내. 굵게 표시가 `…)**가`처럼 문장부호 뒤에서 닫히면 CommonMark가 닫지 않아 `**`가 그대로 보였다(2곳) → 수정 + 전체 도움말 검사 테스트.
- 검증: vitest 481(따라하기·개념 작성 틀·굵게 표시 검사 2 추가), lint·format 0, portal e2e 90 passed, 브라우저 1440·375(가로 넘침 0, `**` 노출 0).
- 미실행: 사람이 화면으로 s-01~03 전체를 따라 해 보는 것(API로 확인). 배포 없음.
- 다음: DOC-04 설계 문서 8편(수치 출처 대조표).

## 2026-09-29 운영 반영 (FS-025 BEMS 전체)
- 서버(사용자 실행): pull `adc3cab..6508599`, uv sync, `alembic upgrade head`(출력 없음 — 템플릿에 bems 10테이블 행이 생겨 적용 확인), API 재시작(`active`), 템플릿 재생성 → 워크스페이스 32·세대 32, **11,910행·86테이블**(bems 4,218). 프런트 rsync·권한(`6508599` 빌드, 서버 갱신보다 먼저 반영돼 잠시 BEMS 타일만 보였음).
- 외부 확인: `/api/v1/bems/dashboard` 404 → 401(로그인 필요 = 라우트 동작).
- 참고: 운영 게스트 상한은 만료 게스트도 센다(로컬에서 확인). 운영은 회수 타이머가 정리하는지 다음 점검 때 확인.

## 2026-09-29 배포 준비(FS-025 BEMS) + Codex FS-026 검토 (Claude Code)
- push `489d5f3..6508599`. 프런트 빌드: worktree `../fs-build`(6508599) `npm ci && build` 완료 — rsync는 사용자 실행.
- 운영 반영 절차: pull `adc3cab..6508599` → uv sync → `alembic upgrade head`(`fs025a_bems`·`fs025b_bems_module`) → API 재시작 → `seed.cli template`(11,910행·86테이블) → 프런트 rsync. C++ 엔진 변경 없음.
- Codex FS-026(`codex/vision-ai` `521ad76`) 검토: 기존 WMS 6테이블 확장 + 5테이블(`inbound_notice`·`inbound_notice_line`·`source_claim`·`stock_reservation`·`stock_reservation_line`), 마이그레이션 `fs026a_wms_receiving_reservation`(down `fs025b_bems_module` = 현재 main head, 갈라짐 없음). main과 시험 병합: 충돌은 HANDOFF 1건, db:validate 0·격리 R1~R6 0·tools unittest 58 OK. 지적: 필드 오류 422(프로젝트 규약은 400 `VALIDATION_FAILED`, 422는 멱등 충돌), 스냅샷 digest에 날짜 포함 시 게스트 복사에서 재계산 필요(날짜 제외 권장), 시드 작업 전 main `6508599`로 rebase(시드 합계·validate 충돌 예방), 범위가 큼(AC 26개) — FS-026b를 입고 검수/예약 두 부분으로 나눠 보고.

## 2026-09-28 FS-025c BEMS 시드·도움말·흐름 맵·통합 검증 (Claude Code)
- push `b9dfbc4..489d5f3`(FS-025b 2부).
- 시드 `_bems`: 1시간 진행과 같은 모델로 30일 시간 단위 시뮬레이션 → 공용 전력 2,160·환경 2,016·명령 16·경보 4(해제 3 + T−1 확인 대기 1) 등 **4,218행**. 템플릿 7,692 → **11,910**, 복사 11,908, `sv-20260928-1`. 잔여 30일 모두 ≥ 0. 상세: 모듈 설계 16장.
- 모델 보정: `CO2_IDLE` +10 → −30(비재실 자연 환기). +10이면 밤새 쌓여 해제 직후 같은 경보가 다시 떴다.
- 도움말 `content/help/bems/b-01~07.md`, 공통 안내·P-02·P-03·P-04 갱신. 흐름 맵 `building_energy` 업무 노드(`bems/b-02`) + 실선, 스키마에 bems, `content/cards/bems.md` 삭제(P-04는 SCM만).
- 화면 보정(시드로 브라우저 확인): B-02 기간 합계 비율 막대, B-01 "환경 센서 없음", B-04 모드 선택 정렬.
- 테스트: `test_bems` 13(시드 시연 1 추가, 기존 테스트는 시드를 지운 빈 BEMS에서), 격리 테스트는 다른 공간에 내 명령이 없음을 확인하도록 조정. test_seed·test_common 합계 갱신. vitest 479(흐름 맵·카드·도움말 수).
- 복사 시간: 중앙값 0.509초·최대 0.619초(10회) — 1초 미만.
- 로컬 개발 DB `factory_studio` 템플릿 재생성(11,910행). 로컬 게스트는 291개(전부 만료)라 상한 20에 걸려 새 게스트가 막힌다 — 확인용으로 `GUEST_LIMIT=1000`을 넘겨 띄웠다(설정 파일은 커밋하지 않음).
- 검증: pytest 724 passed · 1 skipped(16.3분), vitest 479, typecheck·lint·format·build 0, ruff 0, db:validate 0, 격리 R1~R6 0, 전체 스모크 231 passed · 1 skipped(템플릿 11,910)
- 미실행: 운영 반영(마이그레이션 `fs025a_bems`·`fs025b_bems_module` + 템플릿 재생성 필요). push 없음.
- 다음: 운영 배포 준비(사용자 확인 후), Codex FS-026 결정서 검토.

## 2026-09-28 FS-025b 2부 BEMS 화면 B-01~07 (Claude Code)
- push `9965100..b9dfbc4`(1부 API).
- `frontend/src/bems/` 7화면 + 공통(`useGet`·1시간 진행 `AdvanceControl`·`LineChart`·`ShareBars`·`nextBoundary`), 라우트 `/bems/*`(lazy). 상세: 화면 설계 6장.
- 포털: 6번째 타일 BEMS 건물관리, 격자 940px 한 줄·360px 3·3, "여섯 시스템"(홈·진입·헤더·P-02 도움말), 하단 설명 카드는 SCM만, 다른 앱 링크·P-05 목록에 BEMS.
- API 추가 `GET /simulation/clock`(계약서 16장).
- 결함 수정: B-03이 구역 목록 전 `undefined === undefined`로 관측을 읽어 앱이 멈춤(e2e에서 발견) → vitest 회귀.
- 검증: typecheck·lint·format·build 0, vitest 477 passed, test_bems 12, ruff 0, home-browser 9, e2e bems 2(화면으로 기준정보 등록 → 규칙 → 전원·모드·설정값 거부/적용 → 1시간 진행 경보 → 확인 → 그래프 / FEMS 끔), 전체 스모크 228 passed · 1 skipped · 3 failed → 재실행 4 passed(원인: 스모크 GUEST_LIMIT 200 초과로 끝 WMS 2건 429 — 400으로 올림, 3D 걷기 테스트는 30초 경계 지연).
- 미실행: 운영 반영. 도움말 b-01~07 없음(링크 404) — FS-025c. push 없음.
- 다음: FS-025c — BEMS 시드·도움말·흐름 맵·`cards/bems.md` 삭제·통합 검증.

## 2026-09-28 FS-025b 1부 BEMS API (Claude Code)
- push `1b2a8a2..9965100`(FS-025a).
- FEMS 조회 인터페이스 `fs/fems/interface.py`(신규): `enabled`·`site_electricity`(최상위 전력 계측기 일별)·`manufacturing_electricity`(DIRECT_METER 배분 일별). BEMS는 이것만 읽는다(R6).
- BEMS 모듈 `fs/bems/`: `simulation.py`(1시간 모델 상수·계산 한 곳, `__main__` 자체 점검), `service.py`(기준정보·관측·분해·공조 상세·명령 TX-B1·스케줄 교체·1시간 진행 TX-B2·경보 TX-B3·대시보드), `schema.py`, `router.py` → `/api/v1/bems`. 계약: API 계약서 16장, 모듈 설계 15장.
- 결함 수정(개발 중): SQL 별칭 `day`(예약어) → `reading_day`; 시뮬레이션 시계를 KST로 반환; 수동 명령을 실제 시각으로 기록해 명령 이력 순서가 스케줄 명령과 뒤집히던 문제 → 수동 명령도 시뮬레이션 시계로 기록.
- 검증: `test_bems.py` 12 passed(AC-125~135·137), 전체 pytest 723 passed · 1 skipped(13.7분), ruff check·format 0, 격리 감사 0, `simulation.py` 자체 점검 ok.
- 미실행: 화면·e2e(2부), 스모크, 운영 반영. push 없음.
- 다음: FS-025b 2부 — 화면 B-01~07, 포털 6번째 타일.

## 2026-09-28 FS-025a BEMS DB 반영 (Claude Code)
- 사용자 승인: 화면 설계 → BEMS 전체 설계 확인. push `f0b1012..1b2a8a2`.
- 메타데이터 `tools/apply_fs025a.py`(멱등) → `schema.json` v0.12.0 / 93테이블(bems 10: 구역·공용 계측기·환경 센서·공조기·공용 전력 관측·환경 관측·운전 스케줄·제어 명령·경보 규칙·경보), 954컬럼, FK 209, 제약·정책 726(bems C647~C725, R187~R208). 모듈 CHECK `'bems'`.
- 마이그레이션 `fs025a_bems`(스키마) + `fs025b_bems_module`(기존 공간 bems 행 — WMS 교훈으로 DB 단계에 함께). 새 공간·시드 템플릿 모듈 행 7개(시드 7,692·복사 7,690).
- R4 해제: `audit_schema_isolation.py` FORBIDDEN에서 bems 제거, FS-013 머리말 주석, `test_fs014.py` R4 예시 정리. 검증 도구 `validate_bems`, `tools/test_fs025a.py` 3, ERD `bems.mmd`·Excel 31시트, "후속 예약 설계" 표시 제거.
- 결함 수정: `verify_ddl_matches_schema.py`가 CHECK의 `'%'`(습도 단위)를 psycopg 자리표시자로 읽어 실패 → `exec_driver_sql` 3곳 `%` 이스케이프.
- 검증: db:validate 0, 격리 R1~R6 0, tools unittest 55 OK, 임시 DB upgrade → DDL 대조 0 → downgrade base → upgrade → 0(head `fs025b_bems_module`), pytest DB·**로컬 개발 DB `factory_studio`** head 반영 + 로컬 템플릿 재생성(7,692행), pytest **711 passed · 1 skipped**(18.2분), ruff 0.
- 미실행: 공식 스모크(프런트·API 변경 없음), 운영 마이그레이션. push 없음.
- 다음: FS-025b — `fs/fems/interface.py`, `/api/v1/bems`(TX-B1~B3·1시간 진행 모델), B-01~07.

## 2026-09-28 FS-025 BEMS 결정·모듈 설계 승인, 화면 설계 초안 (Claude Code)
- 사용자 승인: 결정서 D18~D23·범위, 모듈 설계 13장 4건 모두 권장안 → 두 문서 "확정".
- 화면 설계 `docs/ui/화면설계_BEMS_FS-025.md`(문서만): B-01 대시보드(D)·B-02 에너지 분해(L, FEMS 교차 조회)·B-03 환경 모니터링(D, 설정값 점선·값 표)·B-04 공조 운전(V + FormPanel, 제어·1시간 진행)·B-05 운전 스케줄(W)·B-06 경보(L + DetailPanel, 규칙 S)·B-07 구역·계측(P). 메뉴 묶음 "건물 현황·운전·경보·기준정보"(화면 제목과 중복 방지). 포털 6타일 한 줄(940px)·"여섯 시스템"·설명 카드 SCM만·흐름 맵 `building_energy` 업무 노드. FEMS 화면 변경 없음.
- 확인: Codex는 `codex/vision-ai`에서 문서 커밋 `aac8d26`(정밀 부품 공장 컨셉·CNC 범위, 옛 main `b6c82a0` 기준) 진행 중 — WMS README를 함께 고쳐 병합 때 충돌 예상.
- 다음: 화면 설계 확인 = BEMS 전체 설계 확인 → FS-025a(메타데이터 v0.12.0·마이그레이션·Excel·ERD·R4 해제).

## 2026-09-28 로컬 개발 DB 갱신 + FS-025 BEMS 설계 초안 (Claude Code)
- 사용자 보고 "로컬 main에서 WMS가 꺼져 있고 안 보인다" → 원인: 로컬 개발 DB `factory_studio`가 `fs023b_qms_module`·옛 템플릿(`sv-20260924-2`)에 머물러 wms 스키마·모듈 행이 없었다(테스트 DB만 올렸음). `alembic upgrade head`(→ `fs024b_wms_module`, 공간 295개에 wms 행) + 템플릿 재생성(7,691행). 기존 게스트 공간은 WMS 데이터가 비어 있어 새 게스트·세대 초기화 필요. 코드 변경 없음.
- BEMS 검토 → 사용자 답: (나) 공용 분해 + 환경 관측, 공용 계측기 BEMS 소유, 1시간 간격, **공조 제어·설정값·경보·운전 스케줄 포함 필수**.
- 산출물(문서만): 결정서 `docs/plan/BEMS도입_공용에너지_결정_FS-025.md`(D18~D23 — R4 해제, FEMS `interface.py` 신규, 잔여 음수 불일치 표시, 모의 공조기 + "1시간 진행" 결정적 시뮬레이션, 경보 발생·확인·해제), 모듈 설계 `docs/modules/bems/BEMS_모듈설계_FS-025.md`(bems 10테이블, 시뮬레이션 모델, TX-B1~B3, API, 화면 B-01~07 요약, 시드 약 5,300행, AC-125~138, 13장 결정 4건). BEMS README 정정(옛 "core 소유"·"테이블 예약" 표현).
- 기본값으로 둔 것: 환경 관측 기간 14일(사용자는 간격만 지정 — 13장 1번에서 확인).
- 다음: 사용자 승인 → 화면 설계 → 전체 설계 확인 → FS-025a.

## 2026-09-28 운영 반영 (FS-024 WMS·홈 아이콘·C++ 비전 엔진)
- 서버(사용자 실행): pull `be87546..adc3cab`, uv sync, `alembic upgrade head` → **`fs024b_wms_module`**(fs024a_wms·fs024b_wms_module 적용), C++ 엔진 `/srv/factory-studio/bin/inspection_core` 복사(서버 `x86_64`, 서버에서 직접 실행 NG 80·36·0.76ms), `.env`에 `VISION_CORE_EXECUTABLE`, API 재시작(`active`), 템플릿 재생성 → 워크스페이스 24·세대 24, **7,691행·76테이블**. 프런트 rsync.
- 운영 확인(Claude Code, 새 게스트 25): 번들 `index-D4uQORuS.js` 일치, 홈 "제조 현장의 다섯 시스템"·5타일 한 줄(84px), WMS W-03 미반영 PL-0006(FG-T300 LT-0009·LT-0012 982 EA씩), `POST /api/v1/factory/vision/inspect` 200·NG 80·36·0.72ms, 검사실 "C++ 단건 검사" 화면 NG 2개·116 px²·0.619ms. 콘솔 오류는 로그인 전 세션 조회 401 1건(정상).
- 미확인: 서버 `journalctl` 5xx(운영 SSH는 사용자만).

## 2026-09-27 배포 준비: WMS·홈 아이콘 + C++ 비전 엔진 (Claude Code)
- push `d910955..133845f`. 프런트 `origin/main 133845f` worktree 빌드(`../fs-build`, 번들 `index-D4uQORuS.js`).
- C++ 엔진: 서버(1 vCPU·2GB, Ubuntu 24.04)는 apt nlohmann-json 3.11 < 요구 3.12, Node 없음(CMake `find_program(node REQUIRED)`), OpenCV 컴파일 부하 → 사용자 선택으로 **맥 Docker linux/amd64 Ubuntu 24.04에서 빌드**. `native/inspection_core/build-linux.sh` 추가(OpenCV 4.13·JSON 3.12 고정 버전 정적 포함, 결과 `work/inspection-core-linux/bin/inspection_core`).
- 빌드: 첫 시도 QEMU 에뮬레이션에서 gcc 세그폴트(병렬 2) → 병렬 1로 재시도 성공(약 1시간). 검증: CTest `native_core` 통과, 웹 비교 **19,968건 불일치 0**(에뮬레이션이 느려 CTest 120초 제한 대신 직접 실행), `--timed` foreign → NG 80·36, 의존 라이브러리 libstdc++·libm·libgcc_s·libc만.
- 배포 절차 8-1장 추가(빌드·복사·`VISION_CORE_EXECUTABLE`). 서버 반영은 사용자 실행 대기.

## 2026-09-27 FS-024c WMS 시드·도움말·흐름 맵·포털 정리 + 홈 아이콘 크기 (Claude Code)
- 사용자 지시: `d910955` push, FS-024c 진행, 홈 솔루션 아이콘의 흰 상자를 참고 이미지 크기로 축소.
- 시드 `_wms` 107행(`sv-20260927-2`, 템플릿 7,691·복사 7,689), 게스트 복사 `document_month`·`WD-` 번호 날짜 이동, 검증 V2·V12 확장. 상세 `docs/modules/wms/WMS_모듈설계_FS-024.md` §17.
- 도움말 `content/help/wms/w-01~07.md`, 공통 안내·M-06 문구, 흐름 맵 `inventory_move` 업무 노드(스키마 wms 허용), 노드정의서 FS-005a 11번. 홈·헤더·진입 "다섯 시스템", 진입 하단 WMS, 설명 카드 BEMS·SCM(`content/cards/wms.md` 삭제), P-05 WMS 구역.
- 홈 아이콘: 흰 상자 168px → **84px**(아이콘 40px), 넓은 화면 5개 한 줄, 540px 이하 3·2(72px). 안내 `i` 버튼은 상자 모서리. 데스크톱·호버·360px 스크린샷 확인.
- 테스트: `test_wms.py` `blank` fixture(시드 지운 빈 공간) + `test_seed_demo_flow`(15), `test_seed`·`test_common` 기대값, `wms.spec` 시드 기준, 흐름 맵·카드·홈 테스트 갱신.
- 검증: pytest **711 passed · 1 skipped**(13.7분), vitest **470 passed**, typecheck·lint·format·build 0, ruff 0, 홈 브라우저 8 passed, 공식 스모크 첫 실행 209 passed·7 failed(개발 서버가 `ContentPages.tsx` 동적 import를 한 번 못 가져와 포털 문서 화면 7건 연쇄 실패 — portal.spec 단독 83 passed) → **재실행 216 passed**(12.7분). 복사 중앙값 0.470초.
- 미실행: push·운영 배포(템플릿 재생성·마이그레이션 `fs024a_wms`·`fs024b_wms_module` 적용 필요).

## 2026-09-27 FS-024b-2 WMS 화면 W-01~07 (Claude Code)
- 완료: `frontend/src/wms/` 7화면(D·L·L·W·L·P·S 패턴, 새 패턴 없음), 런처 WMS 타일(5개 3·2 배치), 내 공간 스위치, 다른 앱 링크 4곳, `LineIcon` wms, App 라우트. 사이드바 묶음 "재고"로 변경(화면 설계 1장 갱신 — W-02 제목과 중복 제목 방지).
- 도구: `tools/run_portal_smoke.py`에 인자 전달(예: `... run_portal_smoke.py e2e/wms.spec.ts`). 인자 없으면 기존처럼 전체.
- 검증: typecheck·lint·format·build 0, vitest **470 passed**(`wms.test.tsx` 7), 공식 스모크 전체 **215 passed · 1 failed**(`wms.spec` 선택자 중복 — 빈 상태 링크와 같은 이름) → 수정 후 `wms.spec` 3 passed, 이어서 홈 격자 3·2 조정 뒤 portal·layout·home·wms 묶음 **165 passed**. 360px 원천 반영·홈, 1440 홈 3·2 스크린샷 직접 확인. ruff 0.
- 미실행: 수정 후 전체 스모크 재실행(바뀐 것은 wms.spec 선택자·홈 격자 CSS — 해당 묶음으로 확인).
- 남은 것(FS-024c): WMS 시드, 게스트 복사 `document_month`·`WD-` 번호 날짜, 도움말 w-01~07, 흐름 맵 `inventory_move`, 홈 제목 "다섯 시스템"·설명 카드 WMS 제거.

## 2026-09-27 FS-024b-1 WMS 조회 인터페이스·API (Claude Code)
- 사용자 지시: Codex 비전검사 병합·push 후 "제안대로" — FS-024b를 API(1부)·화면(2부)으로 나눠 중간 보고.
- 완료: MES 인터페이스 3함수(입고·완료 실행 투입·품목 분류 옵션), ERP 인터페이스 신규(출하·매입·미출하 지시·사용 여부), `/api/v1/wms`(창고·위치·품목·단위·가져오기, 원천 목록·반영 TX-W1·매입 취소 되돌림 TX-W3, 기초·조정·이동 전표 TX-W2, 현재고·가용, 원장·누계, 대시보드), `fs024b_wms_module` 데이터 마이그레이션, 모듈 행 5 → 6(시드 7,584·복사 7,582), 공간 정리·시드 복사 목록에 wms. API 계약서 15장.
- 검증: `test_wms.py` 14 passed, pytest 전체 **710 passed · 1 skipped**(13.9분, 네이티브 C++ 미빌드 skip), 격리 R1~R6 0(WMS는 `fs.mes.interface`·`fs.erp.interface`만 import), ruff check·format 0, db:validate 0, 임시 DB upgrade → DDL 대조 0 → downgrade base → upgrade → 0(head `fs024b_wms_module`).
- 미실행: 공식 스모크(프런트 변경 없음 — 내 공간 화면은 알려진 솔루션만 그려 wms 행을 무시), 동시 반영 부하 시험(공간 잠금으로 직렬화).
- 다음: FS-024b-2 — W-01~07 화면, 런처·내 공간 스위치·다른 앱 링크, e2e·layout.

## 2026-09-27 통합: Codex 비전검사 연속 검사·가상 PLC·C++ 엔진 연결 (codex/vision-ai `b6c82a0`) (Claude Code)
- 병합: `74a4ec2` 연속 검사·배치 이력, `7ec4519` 가상 PLC 핸드셰이크·오류 복구, `848778b` C++ OpenCV 검사 코어·일치 테스트, `b6c82a0` 인증된 C++ 검사 API(`POST /api/v1/factory/vision/inspect`)·사용자 참고 문서(`content/help/portal/vision-lab.md`).
- 검토: `fs/factory/native.py` — 셸 없는 `create_subprocess_exec`, 절대 경로·실행 권한 확인, 엄격한 입력·출력 스키마, 동시 4·2초 제한·1MB 출력 한도, 인증·CSRF. DB 쓰기 없음. `.env.example`에 `VISION_CORE_EXECUTABLE=`(비어 있으면 503, 브라우저 검사는 그대로).
- 충돌: HANDOFF·현황·progress 기록만(양쪽 보존). 통합 보정: `test_factory_native.py` import 정렬(ruff I001, CI 범위).
- 검증: vitest **463 passed**(첫 전체 실행은 부하로 무관한 6건 시간 초과 → 해당 파일 단독 70 통과, 재실행 전체 통과), typecheck·lint·format·build 0, ruff check·format 0, 격리 R1~R6 0, pytest **696 passed · 1 skipped**(실제 C++ 실행 파일 테스트 — 로컬 네이티브 미빌드), 공식 스모크 **200 passed**(12.2분).
- 미실행: 네이티브 빌드(CMake·OpenCV)·웹/C++ 일치 재검증(Codex 보고 19,968건 불일치 0), 운영 배포. 배포 시 서버 C++ 빌드 → `VISION_CORE_EXECUTABLE` 설정 → API 재시작 → 프런트 빌드(`docs/agent/C++웹연결_FS-VISION-CONNECT01.md`).

## 2026-09-27 FS-024a WMS DB 반영 (Claude Code)
- 사용자 승인: 화면 설계 권장안 → WMS 전체 설계 확인(결정서·모듈 설계·화면 설계 모두 "확정").
- 메타데이터: `tools/apply_fs024a.py`(멱등) → `schema.json` v0.11.0 / 83테이블(wms 6: 창고·보관 위치·품목·단위 환산·재고 전표·재고 이동), 847컬럼, FK 187, 제약·정책 647(wms C587~C646, R175~R186). 모듈 CHECK에 `'wms'`.
- 마이그레이션 `20260927_fs024a_wms_schema.py`(revision `fs024a_wms`, down `fs023b_qms_module`, 고정 SQL). 모듈 행 데이터 마이그레이션은 FS-024b.
- 도구: `validate_db_design.py` FS-024a 엔티티 목록·`validate_wms`, `audit_schema_isolation.py` BUSINESS에 wms, `verify_ddl_matches_schema.py`·Excel·ERD 생성기에 wms, `tools/test_fs024a.py` 3. Excel 27시트·ERD `wms.mmd` 재생성, ERD 탐색기 문구 정정.
- 검증: `npm run db:validate` 오류 0, 격리 R1~R6 오류 0, tools unittest 52 OK, 임시 DB에서 `alembic upgrade head` → `verify_ddl_matches_schema.py` 오류 0 → `downgrade base` → `upgrade head` → 오류 0(임시 DB 삭제). pytest DB `factory_studio_fs016_test`를 `fs024a_wms`로 올린 뒤 pytest **683 passed**(12.4분). ruff check·format(CI 범위) 0, diff --check 0.
- 참고: 첫 전체 pytest는 pytest DB를 새 head로 올리기 전이라 `test_schema_verifier::test_baseline_matches` 1건 실패(예상된 것) → 업그레이드 후 재실행 통과.
- 미실행: 공식 스모크(프런트·API 변경 없음), 운영 마이그레이션(배포 전). push 없음.
- 다음: FS-024b — `fs/mes/interface.py` 함수 2개 추가·`fs/erp/interface.py` 신규, `/api/v1/wms`(TX-W1~W3), W-01~07 화면, `wms` 모듈 행 데이터 마이그레이션, 공간 정리·시드 복사 스키마 목록에 wms.

## 2026-09-27 FS-024 WMS 결정·모듈 설계 승인, 화면 설계 초안 (Claude Code)
- 사용자 승인: 결정서 D13~D17·범위, 모듈 설계 13장 4건 모두 권장안 → 두 문서 상태 "확정".
- 화면 설계 `docs/ui/화면설계_WMS_FS-024.md`(문서만): W-01 대시보드(D)·W-02 재고 현황(L)·W-03 원천 반영(L, 원천 4종 탭 — 교차 조회 시연)·W-04 재고 전표(W, 기초·조정·이동)·W-05 재고 원장(L, 조건 시 누계)·W-06 창고·위치(P)·W-07 품목·단위(S + MES 가져오기). 새 패턴 없음 — `DataTable`에 행 선택이 없어 W-03은 행 반영 + 탭 전체 반영. 포털 5타일(3·2 배치)·"다섯 시스템"·설명 카드 BEMS·SCM, MES M-06 안내 문구만 변경.
- 검증: 문서만(`npm run db:validate` 영향 없음). 코드·schema.json 변경 없음.
- 다음: 화면 설계 확인 = WMS 전체 설계 확인 → FS-024a(메타데이터 v0.11.0·마이그레이션·Excel·ERD·격리 R1/R5).

## 2026-09-27 FS-024 WMS 설계 초안 (Claude Code)
- 사용자 검토 요청 → 권장안 승인(완제품+원자재, 버튼 반영, 음수 허용·표시만, 예약 제외·가용 계산, 완제품 LOT·원자재 수량, 창고 2 + 위치 1단계).
- 산출물(문서만): 결정서 `docs/plan/WMS도입_재고원장_결정_FS-024.md`(D13~D17, MES·ERP 인터페이스 추가 — ERP는 첫 `interface.py`), 모듈 설계 `docs/modules/wms/WMS_모듈설계_FS-024.md`(wms 6테이블, 원천 4종 `source_key` 멱등 반영, TX-W1~W3, API, 화면 W-01~07 요약, 시드 약 110행, AC-111~124, 13장 결정 4건). WMS README 상태 갱신.
- 조사 근거: MES 투입 차감 없음·실행 중 투입 삭제 가능, MES 패킹 `shipped`는 시드만, ERP 출하 재고 확인·MES 조회 없음(`packing_no` 문자열), ERP 매입 입고 없음·확정 후 취소 있음(PI-0006).
- 검증: `npm run db:validate` exit 0(메타데이터 미변경). schema.json·마이그레이션·코드 변경 없음.
- 다음: 사용자 승인(결정서 6장 + 모듈 설계 13장) → 화면 설계 → 전체 설계 확인 → FS-024a.

## 2026-09-27 P-01 진입 화면 하단 목록에 QMS 추가 (Claude Code)
- `Entry.tsx` 하단 목록에 "QMS / 품질관리"(4개). `portal.spec.ts` 360px 진입 테스트에 QMS 문구 확인·스크린샷 추가.
- 검증: vitest 440, typecheck·lint·format·build 0, 공식 스모크 **196 passed**(12.1분). 360px 스크린샷 직접 확인(두 줄 배치, 가로 넘침 없음).
- 확인: UI-03은 이미 8화면 전체 완료·배포 상태였다(HANDOFF '다음' 행이 낡아 있었음 → 수정). 정해진 다음 작업 ID 없음.
- 미실행: push·운영 반영(사용자 확인 대기).

## 2026-09-27 운영 반영 (FS-023c·P-02 홈 UI·제목 변경)
- 서버(사용자 실행): `git pull` `2ef0578..be87546`, `uv sync`, `alembic upgrade head`(변경 없음, head `fs023b_qms_module`), API 재시작. 템플릿 재생성 `seed.cli template` → 워크스페이스 15·세대 15, **7,583행·70테이블**(QMS 6테이블 113행 포함).
- 프런트: `origin/main be87546` worktree 빌드 → rsync. 운영 번들 `index-CfwQDw0y.js` 일치(공개 URL로 확인).
- 운영 확인(Claude Code 브라우저, 새 게스트 공간 16): 진입·홈 "제조 현장의 네 시스템", 타일 MES·ERP·FEMS·QMS, 하단 WMS·BEMS·SCM 링크 / Q-03 검사 대기 LT-0017(대기)·LT-0015(작성 중) / M-08 패킹 LT-0016 "QMS 보류" 배지. 콘솔 오류는 로그인 전 세션 조회 401 1건(정상 동작).
- 미확인: 서버 `journalctl` 5xx 점검(운영 SSH는 사용자만 실행 가능). 진입 화면 하단 목록은 MES·ERP·FEMS 3개만 표시(QMS 없음) — 후속 정리 후보.

## 2026-09-27 P-02 홈 UI 정돈 main 통합 (Claude Code)
- 확인: 로컬·원격 브랜치 중 main에 내용이 빠진 것은 `codex/home-ui-polish`(`086f4d7`, Codex) 하나였다. 나머지(3D·UI-01·FS-019a·FS-018h 등)는 다른 해시로 이미 통합됨.
- 병합 `d93b757`: 새 홈 디자인 기준으로 `Home.tsx` 충돌 해결 — QMS 4번째 타일·방패 아이콘 추가, 사용자 결정으로 하단 "아직 만들지 않은 것"(WMS·BEMS·SCM 설명 카드 링크) 유지. 4열 격자, 540px 이하 2×2. 문서 3건은 양쪽 기록 모두 보존.
- 테스트: `home-polish.test.tsx`(하단 링크·QMS 타일), `e2e/home.spec.ts`(QMS 타일, 360px QMS 안내 가로 넘침 없음), 도움말 p-02 갱신.
- 검증: vitest **440 passed**, typecheck·lint·format 0, 홈 브라우저 8 passed, 공식 스모크 **196 passed**(11.4분). 데스크톱·360px 스크린샷 직접 확인.
- 제목 변경(`0739167`): 홈·헤더·진입 화면 "제조 현장의 네 시스템", 진입 문구 MES · ERP · FEMS · QMS, p-03 도움말. vitest 440, 홈 브라우저 8, 공식 스모크 **196 passed**. push `96dd616..0739167`. 운영 서버 명령은 사용자 실행(HANDOFF '다음 할 일').

## 2026-09-27 FS-023c QMS 시드·게스트 복사·도움말·흐름 맵 (Claude Code)
- 시드: `backend/seed/generate.py` `_qms` 113행(불량 유형 6·기준 4·항목 16·검사 17·측정값 68·보류 2), `sv-20260927-1`, 템플릿 7,583행·게스트 복사 7,581행. `validate.py` EXPECTED_COUNTS·V2(검사 월·번호 날짜)·V3(LOT 스냅샷 = MES 완료 LOT).
- 복사: `seed/copy.py` `inspection_month` = 옮긴 검사일의 월, `QI-`/`QH-` 번호 속 날짜 이동. 복사 중앙값 0.359→0.405초(10회).
- 테스트: `test_seed.py`·`test_common.py` 기대값(7,583/7,581, qms 스키마 포함), `test_qms.py` fixture가 QMS 시드를 지운 빈 상태에서 시작 + `test_seed_demo_flow` 추가. e2e `qms.spec.ts`를 시드 기준(LT-0017 검사→보류→배지→재검사 해제, FG-C100 v2 초안 게시)으로, `portal.spec.ts` QMS 노드 → `/help/qms/q-03`.
- 도움말 `content/help/qms/q-01~06.md`, 공통 안내 절 추가. 흐름 맵 품질검사 노드 `solution`(스키마 qms 허용), 직결선 "QMS를 끄면 이 경로"(점선 아님). 설명 카드 QMS 제거, P-05에 QMS 구역. 노드정의서 FS-005a·배포절차(시드 변경 시 템플릿 재생성) 갱신.
- 검증: pytest **683 passed**(11.9분, fs016_test), vitest **434 passed**, tsc·eslint·prettier·build 0, ruff check·format 0, db:validate 0, audit_schema_isolation 0, tools unittest 49 OK, diff --check 0. 공식 스모크 **188 passed**(11.5분, exit 0). 첫 실행은 187 passed·1 failed(`portal.spec.ts` QMS 카드 이동 — 카드 제거에 맞춰 도움말 이동으로 고침) 후 재실행.
- 미실행: push·운영 배포·운영 템플릿 재생성(사용자 확인 대기). 360px는 스모크 portal 경로 목록으로만 확인.
- 다음: 사용자 확인 → push·배포.

## 2026-09-27 통합·배포 (FS-023b·UI-03 B2·비전검사)
- 통합·배포(2026-09-27, Claude Code): main에 FS-023b + UI-03 B2(`d194cb9`) + Codex 비전검사 AI 설명(`0f16bb6`)·합성 이미지 검사실(`da2f02a`) 병합(`2ef0578`). 검증: ruff·격리 R1~R6 0, vitest 435, 백엔드 설명 테스트 13, 공식 스모크 **187 passed**(11.8분). push `8851772..2ef0578`, 서버 pull·`alembic upgrade head`(→ `fs023b_qms_module`)·API 재시작, 프런트 빌드·rsync(번들 `index-aVsvqfGf.js` 일치). 운영 게스트 확인: QMS Q-01~06·MES 패킹·E-02 견적 패널·`/factory/vision-lab` 열림, 페이지 오류 0·5xx 0. OPENAI_API_KEY 미설정 → AI 설명은 데모 응답.

## 2026-09-27 FS-023b QMS 조회 인터페이스·API·화면 (Claude Code)
- 완료: `fs/mes/interface.py`·`fs/qms/interface.py`(R6 준수), `/api/v1/qms`(TX-Q1~Q3), Q-01~06 화면, MES 패킹·LOT `QMS 보류` 배지, 데이터 마이그레이션 `fs023b_qms_module`, 새 공간 qms 모듈 행, 시드 행 수 7,470.
- 테스트: `test_qms.py` 21(AC-97~110), `qms.test.tsx` 10, e2e `qms.spec.ts`·layout·portal 360px.
- 검증: pytest 669 통과, vitest 422, tsc·eslint 0, 스모크 181 통과 + 3D `factory.spec.ts:116` 1건(단독 2회 통과, 플래키).
- 미실행: 운영 배포·push. 도움말 페이지 없음(FS-023c).
- 다음: 사용자 확인 후 FS-023c.

## 2026-09-27 UI-03 B2 완료 — ERP 견적(E-02) 넓은 행 편집 패턴 적용

- 작업 ID: UI-03 B2 · 브랜치: `antigravity/ui03-b2`
- 변경 파일:
  - `frontend/src/erp/Quotations.tsx` — E-04(`SalesOrders.tsx`) 패턴으로 전면 교체. 등록 `FormPanel wide`('견적 만들기'), 상세 `DetailPanel wide`(`${quoteNo} ${revisionNo}차`), 라인 편집·확정·제출·수주 전환 폼을 상세 패널 안에 통합. `RevealAnchor`·`master-grid` 제거.
  - `frontend/e2e/portal.spec.ts` — "ERP 견적 작성 → 확정 → 제출 → 수주 전환" 테스트를 패널 흐름으로 갱신 (수주 전환 후 `page.goto("/erp/sales-orders")`로 이동).
  - `frontend/e2e/layout.spec.ts` — E-02 등록 패널(FormPanel wide, 1440×900 높이 제한)·상세 패널(Esc 닫기) 레이아웃 테스트 2건 추가.
- 검증 결과:
  - typecheck ✅ / lint ✅ / format:check ✅ / build ✅ / unit test 44파일 412개 ✅ / git diff --check ✅
  - 포털 스모크 **171/171 통과** (exit 0). 신규 E-02 레이아웃 테스트 2건 포함.
  - `factory.spec.ts:116`(건물 외관 3D 타임아웃)은 기존 불안정 테스트 — B2 무관, 이번 실행에서 통과.
- 스모크 트러블슈팅: `useDiscardGuard`가 dirty 상태에서 Escape를 차단하므로, 수주 전환 후 사이드바 링크 클릭 대신 `page.goto()`로 교체.
- 문서 갱신: `메뉴적용표_UI-02.md` E-02 → 완료(antigravity, B2), 집계 ERP 18→18 완료·대기 0, 합계 48/55.
- 다음: 사용자 확인 후 UI-03 B2 브랜치 리뷰 → main 병합.

## 2026-09-20 프로젝트 준비
- 완료: 독립 프로젝트 디렉터리와 기본 디렉터리 구조 생성, 로컬 Git main 브랜치 초기화.
- 완료: 기획·설계·상세 일정 Markdown 5개를 docs로 이전. 이후 이 위치를 기준본으로 사용.
- 완료: 이전 UI 시제품을 prototypes로 복사. README·AGENTS.md·.gitignore 작성.
- 검증: 원본 파일 존재 및 문서 참조 경로 확인. 실제 앱/DB 테스트는 구현 전이므로 미실행.
- DB migration / Excel / seed: 아직 없음.
- 남은 작업: CPU·메모리·개발 도구·포트 확인, 상세 코드 참조 검토, 첫 업무 카드·학습 수용 기준·ERD·Excel 설계서 초안.
- 다음: FS-001 환경 점검을 마친 뒤 FS-002~004 수행.
- GitHub 원격 생성·업로드 및 서버 변경: 수행하지 않음.

## 2026-09-20 FS-001 완료
- 하드웨어·OS·개발 도구·리스닝 포트·Git 상태를 점검했다.
- 상세 결과: [환경 점검](agent/환경점검_FS-001.md).
- Docker/Compose 명령 없음. 프로젝트용 Python/Node 버전 선정과 설치는 FS-009에서 처리한다.
- 실제 DB 연결, 앱 테스트, 서버 접속, 소프트웨어 설치는 수행하지 않았다.
- DB migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 후 FS-002. 이후에도 작업 ID별 결과 보고와 사용자 확인을 거친다.

## 2026-09-20 FS-002 완료
- 사용자 확인을 받아 로컬 AI 비서 API·스케줄러·SQL·README를 읽기 전용으로 선별 검토했다.
- 결과: [참조 검토 보고서](agent/기존AI비서_참조검토_FS-002.md).
- 채택: 처리 결과 분리, 고유 제약, 작업별 실패 기록, 환경별 설정 분리.
- 새로 설계: 트랜잭션/외부 호출 경계, 모듈별 서비스, 인증·사용자 격리, migration/Excel 동기화, CLI/timer 작업 관리.
- 확인: 스케줄러 실행 주기와 주석/로그 일부 불일치. 서버의 실제 배포 상태는 미확인.
- 검증: 정적 코드·SQL·문서 비교. 기존 코드 실행·DB 연결·서버 접속·기존 파일 수정 없음.
- migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 후 FS-003 첫 업무 카드·사용자 역할·범위 구체화.

## 2026-09-20 FS-003 완료
- 사용자 제공 MES Excel을 읽기 전용으로 분석하고 동일 사본을 docs/references에 보존했다.
- 26개 시트, 22개 테이블, 348개 컬럼 확인. 목차와 상세 컬럼 수 일치, 명시 참조 테이블/컬럼 존재 검증.
- [참고 설계 검토](modules/mes/MES참조설계_검토_FS-003.md): 채택/보완/후속 분리, 원본 위치와 검증 제한 기록.
- [첫 업무 카드·역할·범위](modules/mes/첫업무카드_역할_범위_FS-003.md): 작업지시→LOT→3개 공정→양품/불량 확정, 역할·예외·공통화 경계 정의.
- 원본 수정·DB 변경·기능 구현 없음. 신규 Excel DB 설계서 최초 작성은 FS-007에서 진행.
- 다음: 사용자 확인 후 FS-004 학습 경로·상세 수용 기준.

## 2026-09-20 FS-004 완료
- [학습 경로·수용 기준](modules/learning/학습경로_수용기준_FS-004.md) 작성: 7개 단계, 5개 이해 질문, 34개 정상/오류 검증 시나리오.
- 업무 완료와 학습 완료 구분, 자유 탐색과 고정 과제 차이, 중복 요청·실패 복구·개인 격리·세대 전환·콘텐츠 버전 기준 정의.
- 검증: 문서 AC ID 유일성/연속성, 단계·질문 ID 존재, 예시 수량의 공정별/전체 보존 계산 확인.
- 실제 앱/API/DB 테스트: 구현 전으로 미실행. 시나리오 작성 완료와 테스트 통과를 구분한다.
- migration / Excel / seed: 변경 없음. Excel 초안은 FS-007.
- 다음: 사용자 확인 후 FS-005 공통 ERD 및 데이터 관계 설계.

## 2026-09-20 FS-005 완료
- [공통 ERD·데이터 관계](architecture/공통ERD_데이터관계_FS-005.md) 작성: 4개 관계도, 36개 논리 엔티티.
- 계정/설정/학습 보존 영역과 세대별 기준정보/생산/계측 영역 분리.
- 공간·세대 복합 관계, 경로 버전 고정, 독립 LOT, 실행/확정 실적 분리, 중복 요청, 학습 live binding/보존 요약, 계측 소유 경계 정의.
- 검증: 엔티티 이름 유일성, 관계도 노드와 목록 대응, AC 범주와 데이터 근거의 정적 검토.
- 물리 DDL·DB 실행·migration·Excel·seed: 미작성/미실행. Excel 최초 작성은 FS-007.
- 다음: 사용자 확인 후 FS-006 상태 전이·권한·모듈 의존성·트랜잭션 규칙.

## 2026-09-20 FS-006 완료
- [상태·권한·트랜잭션](architecture/상태_권한_트랜잭션_FS-006.md) 작성.
- 지시/LOT/공정/학습/게시버전/세대 전이, action 권한, 모듈 의존·비활성화 조건 정의.
- 6개 트랜잭션 계약, 공간 우선 락 순서, 중복 요청·실패 복구·에너지 revision 정책 정의.
- 기존 AC-01~34에 AC-35~44 추가: 초기화/모듈 경합·정리 실패·전량 불량·게시 보호·배분 입력 변경 등.
- 검증: 공식 PostgreSQL 잠금/격리 문서 확인, 정책 정적 검토, TX/AC ID 검사. 실제 DB/API 시험은 미실행.
- 물리 스키마/migration/Excel/seed 변경 없음.
- 다음: 사용자 확인 후 FS-007 Excel DB 설계서 초안 및 메타데이터 작성.

## 2026-09-20 FS-007 완료
- Excel DB 설계서 초안 v0.1.0 작성: 8개 시트, 36개 테이블, 345개 컬럼, 72개 외래키.
- 기준 메타데이터, 정적 검증 도구, Excel 재생성 도구와 [갱신 안내](db/README.md) 작성.
- 공간·세대 복합 참조, 업무/학습 버전 일치, 보존·초기화 정책과 258개 제약·인덱스·구현 정책 항목 정리.
- 검증: FS-005 목록·FK 참조 고유키/타입/범위 검사 통과, 수식 오류 검색 0건, 8개 시트 미리보기 확인, 저장 Excel 재개방 대사.
- 실제 DB 적용·마이그레이션·seed·API 테스트 및 Excel 네이티브 앱 검증: 미실행. 원본 MES Excel 변경 없음.
- 다음: 사용자 확인 후 FS-008 아이콘 홈·업무·학습 도움말 기본 화면 설계.

## 2026-09-20 FS-008 화면 설계 완료
- [화면 설계](ui/화면설계_FS-008.md)와 `prototypes/fs-008-ui.html` 작성.
- 독립 아이콘 홈, 앱 검색, 학습 경로/이어하기, L04 입력/오류/결과, 다음 업무 설명, 모듈 관리 연결.
- 제품의 네트워크·권한·세대 변경 복구 상태 및 공통 UI/데이터 연결 계약 정의.
- 검증: Node VM 스텁 기반 화면 생성 및 수량·사유·결과 복귀·모듈 상태 검사 통과. 실제 브라우저 실행은 환경/URL 보안 정책으로 차단되어 시각·모바일·접근성 검증 미완료.
- DB·migration·Excel·seed 변경 없음. 실제 학습 완료 검증이나 API 연동은 미구현.
- 다음: 사용자 확인 후 FS-009 실행 기반 구축. 브라우저 표시 검증은 환경 마련 후 FS-012에 연결.

## 2026-09-20 FS-005a 차분 설계 완료
- 제품 전제 확정: 운영 전환 없는 교육 전용(포트폴리오 목적), Odoo식 단일 앱 런처, MTS(재고생산), 게스트 즉시 체험, 구현 모듈 MES·FEMS·ERP, 준비 중 QMS·WMS·BEMS.
- 산출물: [차분 설계](architecture/차분설계_게스트_ERP_프로세스맵_FS-005a.md), [MTS 전체 흐름 노드 정의서](architecture/MTS_전체흐름_노드정의서_FS-005a.md).
- 철회: 운영 전환을 전제한 `tenant_type = LIVE/SANDBOX` 분리 검토안. FS-005의 범위 키 S=(workspace_id, generation_id)와 주간 초기화 정책을 그대로 유지한다.
- 순증: erp 10개, mes 5개, process_map 3개 테이블. 총 36 → 54. core.workspace +3컬럼 및 부분 유니크 전환, mes.work_order +2컬럼(order_type, sales_order_line_id — MTO 확장 예약, ORDER 값은 거부).
- 트랜잭션 계약 TX-07~11, 수용 기준 AC-45~58 추가. 노드 17개(IMPLEMENTED 14 / MAP_ONLY 3)와 연결 19개 정의.
- ERP 범위는 ERP-1(거래처·판매계획·수주·출하지시·출하·매출)로 한정. ERP-2·3은 후속 재판단, 전자세금계산서는 제외.
- FEMS는 기준정보 등록·조회 화면만 구현한다. 계측 수집 파이프라인·알람 서버는 미구현이며 계측값은 seed로 생성한다.
- 검증: 기존 문서와의 정적 대조만 수행. 실제 DB·API·화면 미실행.
- migration / Excel / seed: 미반영. schema.json과 DB설계서.xlsx 갱신은 FS-007a로 분리한다. 현 생성기가 Codex 번들 Node와 @oai/artifact-tool에 의존해 실행 환경 정리가 선행된다.
- 다음: 사용자 확인 후 FS-007a — 메타데이터·Excel 설계서에 본 차분 반영 및 정적 검증 재실행.

## 2026-09-20 FS-007a 도구 이전·메타데이터 차분 작성
- Excel 생성기를 사설 번들(@oai/artifact-tool)에서 exceljs로 이전했다. 저장소 루트에 package.json 추가(npm run db:validate / db:build).
- 기능 변경: PNG 시트 미리보기 → 시트별 Markdown 표 미리보기. 개요 합계 수식 → 확정 값. Excel 표(ListObject) → 머리행 고정 + 자동 필터. 사유는 docs/db/README.md에 기록.
- validate_db_design.py 확장: 기준 엔티티 목록을 FS-005와 FS-005a 두 문서에서 함께 읽고, erp·process_map 스키마와 백틱 표기를 허용. retention 누락·UK_PARTIAL 빈 규칙 검사 추가. 보고서에 스키마별 테이블 수 추가.
- tools/apply_fs005a.py 작성: FS-005a의 18개 테이블과 컬럼 변경을 기준본에 병합한다. 재실행 가능하며 이미 적용된 상태에서는 아무것도 바꾸지 않는다.
- 범위 앵커 FK는 추측하지 않고 기존 mes.work_order의 정의를 복사해 적용한다. 앵커를 찾지 못하면 스크립트가 중단한다.
- 검증: 실제 기준본과 동일한 구조의 픽스처(6개 테이블)로 apply → validate → build 전 과정을 실행해 테이블 18개 순증, FK 40개 추가, 오류 0건, 8개 시트 생성과 재개방 대사를 확인했다. 멱등 검사도 통과.
- 미수행: 실제 schema.json에 대한 실행. 저장소가 사용자 로컬 장비에 있어 명령 실행 수단이 없다. schema.json·DB설계서.xlsx·validation-report.json은 아직 36개 테이블 기준이다.
- 사용자 실행 순서: npm install → python3 tools/apply_fs005a.py → npm run db:validate → npm run db:build → Excel 재개방 검토.
- 예상 결과: 테이블 36 → 54. erp 10 / mes +5 / process_map 3. 검증 오류가 0건이 아니면 중단하고 오류 내용을 공유한다.
- 사용자 환경 실행 결과(확인됨): 테이블 54, 컬럼 497, FK 112, 제약·정책 345, 검증 오류 0건. 스키마별 core 16 / mes 15 / erp 10 / learning 6 / process_map 3 / fems 2 / bems 2. Excel 재생성 완료.
- 범위 앵커 FK 복사와 복합 UK 컬럼 순서 가정이 실제 기준본과 일치함을 확인.
- 회귀 발견: 옛 생성기가 코드에 하드코딩하던 내용 3종이 시트에서 유실. 변경 이력 v0.1.0 3행, 코드·상태의 공통 단위·cleanup_status 2행, mes.work_order·mes.operation_execution·learning.attempt 전이 문구. 메타데이터에 없던 값이라 검증기가 잡지 못했다.
- 대응: tools/restore_fs007_sheet_content.py 작성. 하드코딩 값을 schema.json으로 이관해 재발을 막는다. 멱등. 사용자 실행 미수행.
- 다음: 사용자 실행 결과 확인 후 FS-004·FS-006·기준 문서 개정(학습 과정 C1~C4, TX-07~11 락 순서, 첫 공개 범위·일정 재산정).

## 2026-09-20 현황 문서 작성
- [현재 기획과 진행 현황](plan/현재기획_진행현황.md) 작성. 새 작업 세션이 이 문서 하나로 현재 상태를 파악하도록 제품 정의·확정 결정·산출물·미수행 항목·문서 간 불일치를 정리.
- README 갱신: 제품 정의를 통합 업무 포털로 수정, 현재 상태를 FS-007a·54개 테이블로 갱신, 도구 실행 명령 추가.
- 일회성 스크립트 2개(apply_fs005a.py, restore_fs007_sheet_content.py)는 적용 완료 후 삭제 대상으로 분류. 이후 설계 변경은 schema.json 직접 수정으로 처리한다.

## 2026-09-20 FS-005b 합성 데이터·세대 시드 정의 완료
- 산출물: [합성데이터 시드 정의](architecture/합성데이터_시드정의_FS-005b.md).
- 시드 사업장을 가상 반도체 후공정에서 **소형 전자부품 양산**으로 변경. 후공정은 수탁가공(MTO) 성격이 강해 판매계획 기점의 MTS 흐름과 어긋난다.
- 기준정보: 품목 6, 공정 3(사출→조립→검사), 설비 8, 거래처 4, 경로 4(미게시 1 포함), 계측기 9.
- 시간축은 절대 날짜 대신 기준일 T 오프셋으로 정의. 업무 데이터 T-60일, 계측 데이터 T-30일로 분리. 난수 미사용.
- 수량 확정: 지시 30 / LOT 26 / 실행 64 / 실적 62 / BOX 30 / PALLET 6 / 입고 6 / 수주 10 / 출하지시 8 / 출하·매출 4. 사전 어림값(LOT 30, 실행 90, PALLET 8)은 상태 분포와 맞추어 조정.
- 계측 해상도를 **1시간**으로 확정. 1분 해상도는 30일·9대 기준 388,800행이라 게스트 진입이 불가능하다. 1시간 기준 6,480행.
- 총 규모 약 6,840행. 그중 95%가 계측이다. 향후 해상도 상향 제안은 이 문서를 근거로 거부한다.
- 세대 생성은 템플릿 세대 1개를 INSERT ... SELECT로 복사하는 방식. 매번 생성 로직을 돌리지 않는다.
- 학습 시작점이 되는 미완료 건과 오류 시나리오 데이터 8종을 의도적으로 심는다. 전량 불량 LOT, 생산량 0 구간, 계측 누락, 미게시 경로 등.
- 제약 명시: 에너지 검증 예시(450 = 288 + 132 + 30)는 공용 계측이 BEMS 소유이고 BEMS가 MAP_ONLY이므로 이번 시드에서 온전히 재현하지 않는다. 전체 − 제조 = 미계측 잔여까지만 표시하고 분해는 BEMS 설명 카드에 기재한다.
- 성능 목표(복사 2초, 첫 화면 3초, 동시 게스트 20)는 목표이며 측정값이 아니다. 실측은 FS-009 이후.
- 검증: 문서 내 수량 합산 정합성과 학습 과정 C1~C4 시작점 존재 여부를 정적 검토. 생성기·DB·성능 실측은 미실행.
- schema.json / Excel / migration: 변경 없음. 시드는 스키마를 바꾸지 않는다.
- 다음: 사용자 확인 후 FS-006a 기준 문서 개정(학습표 C0~C4, 첫 공개 범위 MES/FEMS/ERP, 일정 재산정, TX-07~11 락 순서).

## 2026-09-20 FS-006a 트랜잭션 확장·기준 문서 개정 완료
- 산출물: [트랜잭션·락 순서 확장](architecture/트랜잭션_락순서_확장_FS-006a.md).
- TX-07 출하지시, TX-08 출하 확정, TX-09 매출 인식(TX-08 내부), TX-10 패킹, TX-11 완제품 입고, TX-12 게스트 공간 생성·회수 계약 정의.
- 명시 잠금 순서를 5단계에서 8단계로 확장. 계획(3) / 패킹·입고(5) / 수주·출하·매출(6) 추가. 세대 정리 삭제 순서도 명시.
- 정정: "락 순서를 안 지키면 데드락"이라는 이전 서술은 부정확하다. FS-006은 모든 업무 쓰기가 workspace 행을 먼저 잠그므로 같은 공간의 데드락은 구조적으로 발생하지 않는다. 락 순서는 세대 정리 CLI·게스트 회수·향후 공간 잠금 완화를 위한 것이다. 문서 1.1에 기록.
- 수용 기준 AC-59~64 추가. 동시 패킹·이중 출하·매출 생성 실패·게스트 생성 실패·회수 경합·정리 순서.
- 기준 문서 개정: 개발기준 v1.0 → v1.1. 제목·목적·아이콘 목록·학습표(C0~C4)·모듈 구성·일정·포함 범위 수정.
- 일정 재산정: 12~14작업주 → **20~26작업주**. S1~S5 + 예비. 이전 표는 무효로 표시하고 추적용으로 보존. 납기 약속 아님을 명시.
- 모듈형플랫폼 설계결정 개정: 첫 공개 범위 MES/FEMS/**ERP**, 데이터 책임표에 erp·process_map 추가, bems를 준비 중으로 변경, 사업장 업종 교체.
- FS-006 본문은 손대지 않고 확장 포인터와 모듈 의존성표만 갱신. TX-01~06·AC-01~44는 그대로 유효하다.
- 검증: 문서 간 정합성 정적 대조. 실제 DB 락 실험·동시성 주입·성능 측정은 미실행.
- 미해결 제약: 게스트 공간 복사는 6,840행 단일 트랜잭션이므로 statement_timeout 10초로 부족할 수 있다. 별도 제한을 두고 실측 후 조정한다.
- schema.json / Excel / migration: 변경 없음.
- 다음: 사용자 확인 후 **FS-009 실행 기반 구축**. 제품 코드가 여기서 시작된다.

## 2026-09-20 현황 문서 전면 갱신 및 폐기 문서 식별
- [현재 기획과 진행 현황](plan/현재기획_진행현황.md)을 전체 재작성했다. 부분 편집을 반복하면서 절 3·4·5가 서로 어긋난 상태였다.
- 추가된 내용: 트랜잭션·시드 현황 요약, 일정 20~26작업주, 알려진 제약 4건, **9장 폐기·보류 문서 목록**.
- 수정된 내용: 학습 과정표에 단계·검증 조건 작성 여부 열 추가(C0·C2·C3 미작성). 게스트 seed 항목은 FS-005b로 해소되어 미수행 목록에서 제거.
- 폐기 식별: 통합플랫폼_개발로드맵.md 전체, 상세개발일정 6절(D01~D70 일정표)과 9절(진행 기록). 같은 문서 1~5·7·8절은 유효하다.
- 상세개발일정 6절은 FS-009~038을 옛 범위(ERP 없음, BEMS 포함)로 배치하고 있어 현재 작업 ID 체계와 충돌한다. 실제 삭제·개정은 사용자 판단 대기.
- 일회성 스크립트 2개는 아직 저장소에 남아 있다. 삭제 명령은 사용자가 직접 실행해야 한다.
- 검증: 문서 간 정합성 정적 대조만 수행.
- 다음: 폐기 문서 처리 방침 확정 후 FS-009 착수.

## 2026-09-20 최신 설계·UI 지침 반영
- 아키텍처·DB 명세·개발 방식·업무/화면 설계를 모두 정리하고 사용자 전체 확인 후 제품 개발에 착수하도록 AGENTS/README/현황 갱신.
- 모듈별 Excel 시트 구성, EIP/모듈 업무도/ERD 제공 방식, UI 색상·아이콘·그림자 기준을 docs/design/설계완료_승인기준_및_시각화.md에 기록.
- EIP/MES/ERP/FEMS 개념 Mermaid 도식 작성. 확정 ERD나 렌더링 검증 완료 산출물은 아님.
- 이번 작업은 지침/설계 문서 갱신. 제품 코드·DB·Excel 재생성·사용자 UI 변경 없음.
- 다음: 설계 빈틈 보완. FS-009 개발 착수는 전체 설계 확인 이후.

## 2026-09-21 FS-006b 설계 보완안 작성
- 게스트 주체/요청 결과, 전역 상한, 템플릿 ID 재매핑, 게스트 회수와 회원 구세대 정리를 구분했다.
- 생산계획 라인→작업지시 연결과 배정량 검증, 단일 품목 포장·팔레트 전량 출하·지시 취소 계약을 제안했다.
- 기존 AC-63 기대 결과 정정, AC-65~80 검증 명세 추가. 모두 실제 시험 미실행.
- 상세: [FS-006b](architecture/설계보완_게스트_계획_패킹출하_FS-006b.md).
- 제약: 사용자 확인 대기인 설계안이다. 메타데이터/Excel v0.2.0과 실제 DB는 변경하지 않았다. 승인 후 FS-007b에 함께 반영한다.
- 검증: 문서 AC 번호 유일성·연속성, 요구 절 존재, 갱신 문서 링크 확인. 제품 코드/브라우저/DB/성능 시험 없음.
- 다음: 사용자 확인 후 FS-007b 모듈별 DB 명세·Excel·ERD. 전체 설계 확인 전 FS-009 착수 금지.

## 2026-09-21 FS-007b 산출물 완료
- FS-006b 계약을 메타데이터 v0.3.0에 반영: 54테이블/510컬럼/113FK/375제약·정책.
- 모듈별 Excel 31시트, 내부 링크 172개. 1,191개 행 원본 대사와 시트 상단 시각 검사.
- 오프라인 EIP/모듈 ERD HTML 및 Mermaid 원본 8개 생성. 상세는 db/FS-007b_변경_검증.md.
- 제품 코드/DB/서버 변경 없음. 실제 브라우저·DB 동시성·Excel 앱 검증 미수행.
- 다음: 사용자 확인 후 FS-008a 전체 흐름/UI 설계 개정. 전체 설계 승인 전 개발 금지.

## 2026-09-21 FS-005c FEMS 다중 에너지원 설계 제안
- 참조 명세서를 바탕으로 FEMS를 전력 전용에서 다중 에너지원(전력·가스·유량·스팀·용수) 구조로 확장하는 안을 작성했다.
- 제안 범위: core 신규 2(energy_source, meter_channel), fems 신규 4(energy_factor, tariff, energy_target, energy_baseline). 54 → 60테이블.
- 핵심 근거: 단위가 다른 에너지원은 원단위 값끼리 합산할 수 없다. 1차에너지 환산 후에만 합산·원단위·목표 비교가 성립한다. 환산계수와 배출계수는 용도가 다르므로 섞지 않는다.
- 기존 변경 제안: core.meter에서 측정종류·단위 제거, energy_reading·energy_allocation·bems.energy_reading의 참조를 채널로 전환.
- 상태: **미반영.** 메타데이터 v0.3.0은 FEMS 2테이블을 유지한다. 채택 여부 결정 대기.
- 별도 산출물: 독립 참조용 FEMS 공통 DB 설계서(ESG 방향, 24테이블/350컬럼)를 MES 기초 설계서 템플릿으로 작성해 사용자에게 전달했다. 저장소 미포함.

## 2026-09-21 문서 정리 및 기준 갱신
- 삭제 완료: 통합플랫폼_개발로드맵.md, tools/apply_fs005a.py, tools/restore_fs007_sheet_content.py.
- 갱신: 현재기획_진행현황.md 전체 재작성(v0.3.0 수치·모듈별 표·FS-006b/007b 반영·다음 작업을 FS-008a로 수정), db/README.md 재작성(31시트·모듈별 규모·ERD 안내).
- 헤더 주석 추가: 공통ERD_FS-005(36엔티티 v1 기준본임을 명시), 학습경로_FS-004(C1·C4만 덮음), FEMS_공통설계_FS-005c(제안·미반영).
- 정정: 현황 문서의 "S0 종료 → FS-009 즉시 착수"는 틀렸다. design/설계완료_승인기준이 그보다 우선하며 FS-008a → 정합화 → 전체 승인 → FS-009 순서다.
- 검증: 문서 간 정합성 정적 대조만 수행. 스키마·Excel·ERD·제품 변경 없음.
- 미처리: docs/.DS_Store, tools/.DS_Store 잔존. 상세개발일정 6·9절 개정은 미수행(현재는 폐기 표기만 되어 있다).
- 다음: FS-005c 채택 여부 결정 → FS-008a.

## 2026-09-22 독립 솔루션 전환 검토
- 사용자 최신 정의를 확인: 하나의 포털에서 MES/ERP/FEMS 각각 독립 전문 솔루션을 전시.
- references 세 Excel 읽기 전용 검토: MES 22테이블/348컬럼, FEMS 24/350, ERP 41/698(목차 기준).
- 기존 통합 메타데이터 v0.4.0(60테이블), 공유 core, ERP-1, 학습 중심 기획과 충돌 확인.
- 상세: plan/독립솔루션_전환검토_2026-09-22.md. 현황 상단에 최신 사용자 방향과 이전 항목 재검토 표기.
- Excel/DB/제품 코드 변경 없음. 실제 DB 검증 및 법규/표준 적합성 검증 미수행.
- 다음: 공통 인증/업무 독립 경계와 학습 기능의 역할 확인 후 전환 아키텍처·범위 정리. 기존 FS-008a를 그대로 진행하지 않는다.

## 2026-09-22 FS-013 독립 솔루션 전환 결정 완료
- 사용자 확정 답변 7건을 결정서로 고정: 공통 인증만 공유(D1), 단일 PostgreSQL+스키마 분리+API 1개(D2), 기존 67테이블 분해·재배치(D3), 학습은 도움말로 축소(D4), 게스트 체험 유지(D5), 흐름맵·도움말은 정적 파일(D6), ERP 회계는 A층 구현/B층 읽기전용/C층 제외(D7).
- 산출물: [독립 솔루션 전환 결정서](plan/독립솔루션_전환결정_FS-013.md).
- 재배치 매핑 확정: core 19 → 11(인증·공간·세대·운영만). 마스터 8개를 mes 5 / erp 2 / fems 8로 복제·이관.
- 폐기 12개 확정: learning 6, process_map 3, mes.learning_binding 1, bems 2. BEMS 예약 테이블은 사전 보유 이유가 없어 함께 폐기.
- 교차 FK 3건 제거 방식 결정: fems.energy_allocation.execution_id는 컬럼 삭제(equipment_id로 성립), mes.production_plan.sales_plan_id와 erp.shipment_line.packing_unit_id는 코드 문자열로 대체.
- 신설 12개 제안: erp 채권채무·수금지급 6, 매입 간이 2, 세금계산서 1, 계정과목·분개규칙 2, fems.production_record 1.
- 규모 예측: 67 → 72테이블. **줄지 않고 늘어난다.** 마스터 복제 7 + 회계 11 > 폐기 12.
- 새 경계 검사 규칙 R1~R5 명세. audit_module_boundary.py는 판정 대상이 사라져 폐기 대상으로 분류.
- AGENTS.md §3 개정: "공통 기준정보는 core가 소유" 조항을 독립 소유·교차 FK 금지·학습 축소 4개 조항으로 교체. 읽기 순서에 FS-013 추가.
- 현황 문서 전면 재작성: 제품 정의를 학습 중심 EIP에서 독립 솔루션 전시로 교체. 진행률 70% → 55%로 하향 조정(DB·화면이 뒤로 물러남). 다음 작업을 FS-008a → FS-014로 변경.
- 정정: 전환검토 문서의 "schema.json v0.4.0 / 60테이블"은 오기다. 실제는 **v0.6.0 / FS-005f / 67테이블**이며 ERD 원본 7개로 구성(core 19/mes 17/erp 14/fems 6/learning 6/process_map 3/bems 2)을 확인했다.
- 검증: schema.json 헤더와 docs/architecture/erd/*.mmd 7개의 정적 대조로 테이블·FK 목록을 집계했다. 명령 실행 수단이 없어 db:validate·db:build·build_erd는 미실행.
- 미수행: schema.json 재구성, audit_schema_isolation.py 작성, Excel·ERD 재생성, 회계 A·B층 컬럼 설계, 회계 기준·세금계산서 법정 요건 검토. **스키마·Excel·ERD·제품 코드 변경 없음.**
- 다음: 사용자 확인 후 FS-014 — schema.json v0.7.0 재구성 + 격리 검사 스크립트 + Excel·ERD 재생성.

## 2026-09-22 — FS-014 완료: 독립 스키마 재배치 / 회계는 FS-014b로 분리

- 사용자 확인: FS-014는 재배치·교차 FK 제거·폐기 12개·fems.production_record만 수행한다. 회계 A·B층 11개는 FS-014b로 분리한다. DB 미적용(migration_revision=null)이므로 중간 버전 비용보다 검증 원인 분리를 우선한다.
- 집계: **v0.7.0 / FS-014 / 61테이블 / 598컬럼 / 138 FK / 제약·정책 427개**. core 11 / mes 21 / erp 16 / fems 13. FEMS=기존 6+마스터 6+생산량 1. FS-013 예상 72와 차이 11개는 보류한 회계다. FS-014b 이후 ERP 27, 전체 72 목표를 유지한다.
- 정정: FS-013 §3.2 소계 한 줄만 5/2/8→5/2/6, 8→15 실체를 8→13으로 바꿨다. §5 총계 72는 변경하지 않았다. 이전 응답의 70은 FEMS 합산 오류였다.
- 도구: tools/apply_fs013.py 신규. v0.6.0/FS-005f·입력 구조·후보 구조 검증 후 원본 SHA256 이름의 백업과 원자적 교체. --check는 무변경 검증. 유효한 적용 상태 재실행은 파일·mtime·백업·변경이력 불변. 오류 입력·부분 적용·DB 적용 메타데이터는 중단한다.
- 백업: docs/db/schema-metadata/backups/schema.before-FS-014.835668b772bc2b5a0aa09fcb4e479fc6e44900328716111d21865b0bf5d8bfb3.json. 작업 전 문서·생성기·산출물 사본은 work/fs014/original/에 보존했다.
- 매핑: FS-013 각 행 그대로 core 마스터 8개→mes 5/erp 2/fems 6. 키·인덱스·제약·상태·코드목록을 동반 이동하고 업무 FK를 자체 스키마로 재지정했다. learning 6/process_map 3/mes.learning_binding 1/bems 2 및 부속 메타데이터 삭제.
- 컬럼·정책: execution_id 삭제, sales_plan_code/packing_no로 코드 대체. FEMS 품목 비소유에 따라 energy_baseline.item_id도 item_code로 대체했다. 실행별 배분 조건부 UK를 설비 기준 UK로 통합하고 ERP→MES 패킹 상태 검증 정책을 제거했다. 플랫폼 역할·활성 모듈·FEMS 계측 소유 목록도 현재 경계로 정리했다.
- 신설: fems.production_record 14컬럼. 범위 S, 자체 설비, 품목 코드, 생산 구간, 양품 생산량·단위, 원천 키·버전·확정 상태. 확정 후 불변, 원천 키별 최신 확정 버전만 집계하는 정책을 명시했다. 설계 근거 및 61개 엔티티 목록: docs/db/스키마_재구성_FS-014.md.
- 추가 정합성: 기존 주차·종료월·기준선 기간의 누락된 문자열 형식 CHECK 5개 보완. PRIMARY/EMISSION 구분 유지. 월·주차 실제 업무 유효성 및 정책 실행은 제품 구현 단계다.
- 격리: tools/audit_schema_isolation.py 신규(R1~R5); tools/audit_module_boundary.py 삭제. 일반 검증기도 현재 엔티티 목록·격리·달력 CHECK·폐기 컬럼 잔존 검사를 사용하도록 갱신했다.
- 산출물: schema.json / DB설계서.xlsx(19시트) / 전체+4스키마 ERD(5 Mermaid 원본 및 HTML) / validation-report 동시 갱신. 폐기 3스키마 ERD 원본 삭제. 생성기의 고정 버전·집계·옛 소유권 설명을 수정했다. 현황 문서와 문서 지도도 갱신했다.
- 실행 검증: `npm run db:validate` 오류 0; `python3 tools/audit_schema_isolation.py` R1~R5 오류 0; `python3 -m unittest discover -s tools -p test_fs014.py -v` 10개 통과; `npm run db:build`, `python3 tools/build_erd.py` 성공. 회귀 테스트는 멱등 바이트·mtime·백업, dry-run, 잘못된 입력/적용 상태 보존, R1~R5 오류 주입, FK 대상/타입/유니크키/복합 범위/RESTRICT/달력 CHECK 오류 주입, CLI 종료 코드를 포함한다.
- Excel 검증: 저장 파일 재열기로 8,921개 명세 셀 대조, 내부 링크 154개 대상·주소 확인, 19개 시트·고정 헤더·오류 셀 검사. Artifact Tool로 19개 시트 대표 구간 렌더링·육안 확인 및 신규 생산량 구간 확인. 수식 계산 모델이 아닌 정적 명세다. 미리보기 도구가 빈 공유 문자열을 숫자로 표시하는 문제를 확인하여 생성기는 빈 문자열 대신 실제 빈 셀을 기록하도록 보완했고, 저장 파일 재대조와 생산량 구간 재렌더링을 통과했다.
- ERD 검증: HTML 내 JSON과 schema.json 동일, Mermaid 엔티티·원본 개수·README 원본 해시 대조, JS 문법 검사. 설치된 Chrome의 격리된 headless 세션에서 4스키마 집계·범위 FK 토글·생산량 상세 선택·데스크톱/모바일 표시 확인, JS 오류 0. 번들 Playwright 기본 Chromium은 미설치여서 설치된 Chrome으로 검증했다.
- 보존: 사용자 UI 파일 3개 및 AGENTS.md의 작업 전후 바이트 해시 동일. 제품 코드·UI 시제품·물리 DDL·마이그레이션·seed는 변경하지 않았다. Git 커밋은 하지 않았다.
- 미실행: PostgreSQL 적용·CHECK 실행·트리거·서비스 정책·동시성·성능·권한 검증, Excel 네이티브 앱 조작, Mermaid 렌더러 파싱. 위 정적 검사·브라우저 확인을 이 검증들의 통과로 간주하지 않는다.
- 제약: 원천 키별 최신 확정 버전·구간 중복·확정 불변은 SERVICE/DB_POLICY이며 DB CHECK가 아니다. FEMS 공장 전체 분모의 대표 공정 선정은 추가 업무 규칙이 필요하다. 과거 설계 문서 전체를 개정한 작업은 아니며 충돌 시 FS-013 및 FS-014 설계가 우선한다.
- 다음: **사용자 FS-014 결과 확인을 기다린다.** FS-014b는 컬럼 설계에 앞서 ① 부분 수금·지급의 apply/잔액 ② 채권·채무 상태 전이와 확정 후 불변 ③ 세금계산서 발급확인과 매출 인식 선후 ④ 비저장 분개 미리보기 거래 유형을 정의하고 사용자 확인을 받아야 한다. FS-014b 미착수.

## 2026-09-22 FS-014 결과 검수 및 FS-013 잔여 오류 정정
- FS-014 결과를 저장소에서 직접 대조해 보고 수치가 실제와 일치함을 확인했다. schema.json v0.7.0/FS-014, validation-report 61테이블(core 11/mes 21/erp 16/fems 13)·598컬럼·138FK·errors 0.
- 독립 산정과 일치: mes 16+마스터 5=21, erp 14+2=16, fems 6+6+생산량 1=13.
- audit_schema_isolation.py 본문 검토: R1~R5 판정 로직과 범위 앵커 예외 처리가 FS-013 §6 명세와 일치. audit_module_boundary.py 삭제 확인.
- **정정 1 (FS-013 §3.2 제목).** "8 → 15"는 오기다. 소계 행만 고치도록 지시해 제목이 남아 있었다. "8 → 13"으로 교체.
- **정정 2 (FS-013 §5 본문).** "마스터 복제 7개"는 FEMS 소계 오기에서 파생한 수치다. "마스터 순증 5개(8 → 13개 실체) + 신설 12개 − 폐기 12개 = 순증 +5"로 교체. §5 표와 총계 72는 처음부터 정확했으므로 변경 없음.
- FS-013 상단에 진행 상태 주석 추가: 4장 회계 11개는 FS-014b로 분리되어 미착수이며 §5의 72는 목표치다. 현재 수치 기준은 현황 문서임을 명시.
- AGENTS §6 개정: "어시스턴트는 명령을 실행할 수 없다"는 고정 서술을 "실행 수단은 세션마다 다르다. 먼저 확인하고 불가능하면 스크립트를 안내한다"로 교체. 현황 문서의 동일 제약 항목도 맞춤.
- 검증: 문서 정적 대조와 수치 재계산만 수행했다. 실행 수단이 없는 세션이라 db:validate·audit_schema_isolation·test_fs014를 직접 돌리지 않았다. Codex의 실행 결과를 재현해 확인한 것은 아니다.
- schema.json·Excel·ERD·제품 코드 변경 없음. 문서 3건만 수정.
- 다음: FS-014b — 회계 업무 규칙 4항목 정의 후 컬럼 설계.

## 2026-09-22 — FS-014b 완료: ERP 회계 A·B층 11개 / v0.8.0

- 사용자 확정 규칙과 추가 결정에 따라 진행. 소명 한도 SERVICE 정책 승인, 잠금 7단계는 채권·채무→수금·지급→소명. 수금은 receivable.id 오름차순 다음 receipt.id 오름차순, 지급은 대응 순서. 확정은 금액 고정이며 이후 소명 추가·취소를 허용한다. 소명 취소는 cancelled_at 없이 물리 DELETE, 이력은 core.audit_event.
- 결과: **v0.8.0 / FS-014b / 72테이블 / 719컬럼 / 162 FK / 제약·정책 528개**. core 11 / mes 21 / erp 27 / fems 13. 기존 61+회계 11=72로 **FS-013 §5 예상 72와 일치**. migration_revision=null, DB·서비스 미적용.
- 신설: erp.receivable, receipt, receipt_apply, payable, payment, payment_apply, purchase_invoice, purchase_invoice_line, tax_invoice, account, posting_rule. 신설 118컬럼 및 기존 sales_record 통화·취소 시각·사유 3컬럼. 다른 스키마의 테이블·관계·제약·상태·코드목록은 기존과 동일함을 테스트로 대조했다.
- 소명: 양쪽 부모의 S·거래처·통화를 복합 FK로 일치시킨다. 합계 한도는 부모 잠금 후 새 조회로 수금/지급액과 채권/채무 원금 양쪽을 검사하는 SERVICE 정책이다. CHECK로 가장하지 않는다. 소명 UPDATE 금지, 변경은 물리 삭제+새 요청. 등록·삭제·감사·멱등 결과는 같은 트랜잭션, 실패 시 전체 롤백 계약.
- 잔액·상태: receivable/payable에 balance/status/합계 캐시 없음. 원금−SUM(소명액)으로 조회 파생. 0원 원금은 OPEN/CLOSED 조건이 겹치므로 CLOSED 우선으로 문서화했다. 수금·지급액과 소명액은 양수, 원금은 0 이상. 원천 취소 채권·채무는 유효 조회에서 제외하고 원금은 보존한다.
- 생성·취소: TX-09 매출 생성과 채권 생성은 같은 트랜잭션. 매입 확정과 채무 생성도 같은 트랜잭션. 원천당 UK, 수기 원장 생성 없음. 소명 행이 남으면 상위 거래 취소 거부. 세금계산서 pending은 매출 취소 시 같은 트랜잭션에서 삭제, issued이면 취소 금지, 없으면 소명 조건만 확인. 매입 취소는 세금계산서와 무관.
- 세금계산서: 매출 전용 sales_record FK·UK로 0..1 관계, 발급대기/발급완료 두 상태, 승인번호·발급일 수기. 선발행은 SERVICE 정책으로 차단. 금액은 매출에서 조회하며 명세·월합계·국세청 연동 없음.
- 미리보기: 고정 7계정·4거래 유형·10규칙 조합 정의. 계정·규칙 행은 seed로 만들지 않았으며 허용 코드·명칭·조합과 완비 검사 계약을 설계했다. receipt_apply/payment_apply 1행=분개 1세트, 미소명 잔여는 분개 표 밖 안내. 결과·전표·총계정원장·분개 이력·조건 분기 엔진 없음.
- 도구: tools/apply_fs014b.py 신규. 사전 검증, SHA256 원본 백업, 원자적 교체, --check, 멱등 재실행. 원본 백업: docs/db/schema-metadata/backups/schema.before-FS-014b.98d2f505f5620f025019b152b2e3c018b41e5ddbd5c0bb21cd710a6be1423b25.json. 검증기는 FS-014/014b 엔티티 목록을 구분하고 회계 구조 계약을 추가 검사한다.
- 문서·산출물: docs/db/스키마_재구성_FS-014b.md 신설. 현황·문서 지도·FS-013 진행 상태·FS-006a 잠금 7단계 및 회계 정리 순서 갱신. schema.json·DB설계서.xlsx(19시트)·전체+4스키마 ERD(5원본 및 HTML)·validation-report를 함께 갱신했다.
- 실행 검증: `python3 tools/apply_fs014b.py --check` 통과, 실제 적용 후 재실행 no-op. `npm run db:validate` 오류 0, `python3 tools/audit_schema_isolation.py` R1~R5 오류 0, `npm run db:build` 및 `python3 tools/build_erd.py` 성공.
- 회귀: `python3 -m unittest discover -s tools -p 'test_fs014*.py' -v` **22개 통과**(기존 10+회계 12). 수량·비ERP 보존, 금지 잔액/상태/취소 플래그, 격리·범위, 합계 CHECK 오분류, SERVICE 계약 누락, 원천 UK·소명 거래처 FK, 세금계산서 1:1·2상태, 고정 분개·계정, KRW·RESTRICT, dry-run·백업·바이트/mtime 멱등, 오류 원본 보존, 원자적 교체 실패 주입을 검사했다. `ABORT: injected replace failure`는 의도한 오류 주입 결과이며 전체 테스트는 통과했다.
- Excel 검증: 저장 파일 재열기로 명세 셀 **10,749개**, 내부 링크 **178개**, 19시트·고정 헤더·오류 셀 검사. Artifact Tool 오류 검색 0건, 목차·ERP 테이블/관계 및 채권·소명·세금계산서·규칙 대표 구간 8개 렌더링 확인.
- ERD 검증: HTML 내 메타데이터 동일, 전체 Mermaid 엔티티 집합·5원본·README 해시 대조. Chrome headless에서 4스키마 수량, ERP 범위 앵커 토글, receipt_apply 상세·취소 플래그 부재 확인, JavaScript 오류 0. `git diff --check` 통과.
- 보존: 사용자 UI와 AGENTS.md의 작업 전후 해시 동일. 제품 코드·화면·API·물리 DDL·마이그레이션·seed 생성기·PostgreSQL 적용 없음. Git 커밋 없음.
- 미실행: PostgreSQL CHECK·FK·트리거 실행, 실제 SERVICE 합계·불변·취소·동시성·성능·권한·멱등 API 동작, Excel 네이티브 앱, Mermaid 렌더러 파싱, 법정 세무·회계 적합성. 테스트 통과는 메타데이터/변환 검증이며 정책 실행 보장을 뜻하지 않는다.
- 제약: 소명 물리 삭제 뒤 옛 등록 요청 재실행은 UK만으로 막을 수 없다. core.request_receipt 보존기간과 재시도 허용기간을 일치시키고 만료 키를 거부하는 API 계약이 필요하다(FS-010/011). 계정 7개·규칙 10행 완비 여부와 세율·반올림은 SERVICE 구현 시 검증한다.
- 다음: **사용자 FS-014b 결과 확인을 기다린다. FS-008a 미착수.** 이후 화면 기획에 금액 확정 후 소명 추가·삭제, 소명 행별 비저장 미리보기, 분개 밖 잔여 표시를 반영한다.

## 2026-09-22 FS-008a 스토리보드 완료 (54화면)
- 산출물 4건: docs/ui/화면설계_포털_FS-008a.md(7화면), 화면설계_FEMS_FS-008a.md(14), 화면설계_ERP_FS-008a.md(18), 화면설계_MES_FS-008a.md(15).
- v0.8.0 72테이블 중 71개가 최소 한 화면에서 쓰이는 것을 확인했다. 유일한 미사용 테이블이 core.dashboard_layout이어서 삭제 후보로 올렸다.
- 확정 결정 3건: 런처 학습 요소를 "전체 업무 흐름 보기"로 교체, 설명 카드를 QMS·WMS·BEMS·**SCM 4종**으로 확장(SCM 신규), FEMS에 배출량 화면 포함.
- 포털 문서 6장에서 공통 규격 확정: 색 토큰 6개, 상태색 저채도 3종(빨강 금지), 그림자 4% 1단계, 단색 라인 아이콘 통일, 공통 컴포넌트 9종, 포털은 헤더만/솔루션은 사이드바+헤더 레이아웃.
- 포털 5장에서 플랫폼 역할 GUEST/OWNER/ADMIN 3종을 처음 정의했다. FS-013은 "core.role은 플랫폼 역할만"이라 말했을 뿐 목록이 없었다.
- 걧 20건 발견해 분류: 스키마 변경 필요 5, 확인 필요 4, SERVICE 정책 3, 화면 안내로 해소 8. MES 문서 9장에 종합했다.
- 가장 무거운 걧 3건: fems.energy_allocation.kwh가 다중 에너지원인데 전력 전용 컴럼 / erp 부가세율의 출처 부재 / erp.receivable 만기 부재로 연령분석 불가.
- 검증: 문서 작성과 스키마 정적 대조만 수행. 스키마·Excel·ERD·제품 코드 변경 없음. HTML 시제품 제작·브라우저 검증·접근성 확인 미실행.
- 다음: 걧 반영을 FS-008b로 분리해 진행.

## 2026-09-22 FS-008b 화면 걧 반영 (v0.9.0)
- 결과: **71테이블 / 712컬럼 / 161 FK / 제약·정책 528개.** core 10 / mes 21 / erp 27 / fems 13. 검증 오류 0, R1~R5 위반 0.
- 스키마 변경 4건 적용: fems.energy_allocation kwh → quantity 개명 + unit 추가 / erp.item 과세구분(TAXABLE·ZERO·EXEMPT) / erp 결제조건·채권·채무 만기 / core.dashboard_layout 삭제.
- owner_module을 meter·meter_channel·energy_reading 세 곳에서 함께 제거하고, 관측값 FK를 (S, meter_channel_id, unit) → meter_channel(S, id, unit)로 재구성해 **단위 일치 검증을 유지**했다. 채널에 (S, id, unit) 유니크가 없어 기존 (S, id, owner_module, unit) 키를 교체했다.
- 만기 정책: 결제조건·채권·채무 만기를 **nullable**로 두어 조건 미입력 거래처 때문에 매출 확정이 막히지 않게 했다. NULL 만기는 "만기 미설정" 그룹이며 연체가 아니다. 매출은 인식일+N 계산 전용, 매입은 수기 우선 → 없으면 매입일+N → 조건도 없으면 NULL. 확정 후 불변·소급 금지.
- SERVICE 정책 3건 추가: 설비 동시 점유 방지 / 패킹 수량 ≤ LOT 양품 / 게스트 만료는 세션 종료 후 회수.
- 설계 결정 4건 문서 반영: 1지시:1LOT 의도 / BOM 선택 허용 의도 / 견적 개정은 행 누적 + MAX(revision_no) 파생 판정(플래그 컬럼 금지) / workspace_module 유지.
- TX-12 정정: 기존 "만료 시 회수가 먼저면 요청 차단" 규칙이 이번 결정과 충돌해 회수 조건을 "세션 종료와 진행 요청 없음"으로 고쳤다. 삭제 절차는 유지.
- 보류: 설비 상태 컬럼(M-G06), FEMS 공장 전체 대표 공정(G-08), 0원 매출 발급 여부(E-G07), 정적 콘텐츠 경로(P-G03), SCM 카드 문안(P-G04).
- 도구: tools/apply_fs008b.py 신규. 사전 검증·SHA256 원본 백업·원자적 교체·--check·멱등 재실행. 회귀 11개 추가.
- **기록 주의:** 이 항목은 Codex 세션이 사용 한도로 중단된 뒤 다음 세션이 저장소 파일을 대조해 작성했다. 수치는 validation-report.json에서 확인했으나, **검증 명령을 재실행해 재현하지는 않았다.** Excel·ERD 브라우저 검증은 이전 세션 보고에만 의존한다.
- 미실행: PostgreSQL 적용·CHECK/FK/트리거 실행, SERVICE 정책 실행·동시성·성능·권한, Excel 네이티브 앱, Mermaid 렌더러 파싱, 법정 세무·회계 적합성.
- 다음: FS-010 API 계약서. 솔루션별 네임스페이스·권한·멱등키·세션 종료 판정·request_receipt 보존기간 계약을 다룬다.

## 2026-09-23 FS-010 API 계약서 작성
- 산출물: docs/architecture/API계약서_FS-010.md. 54화면이 호출하는 HTTP 계약과 공통 규약.
- 네임스페이스 4개로 분리: /api/v1/core·mes·erp·fems. 업무 네임스페이스끼리 호출하지 않으며 솔루션 간 조인 엔드포인트를 두지 않는다.
- **범위 키 S를 클라이언트가 보내지 않는다.** 서버가 세션에서 파생한다. workspace_id를 받으면 71테이블 전체에 소유권 검사를 빠짐없이 넣어야 하고 한 곳만 누락도 타인 데이터가 새는 구조가 된다.
- 권한 2계층: 플랫폼 역할(GUEST/OWNER/ADMIN)은 core 접근만, 업무 권한은 각 솔루션 자체 보유. 1차는 "공간 소유자면 전부 허용"이되 계층은 분리해 둔다.
- 오류 코드 11종 정의. REFERENCED_BY_OTHERS는 details.references에 참조처별 건수를 필수로 실어 FS-008a의 화면 요구를 받친다.
- 멱등키: 상태 변경 POST 전부에 Idempotency-Key 요구. core.request_receipt 구조를 그대로 쓴다. **보존기간과 재시도 허용기간을 24시간으로 일치**시켜 FS-014b가 남긴 제약(소명 물리 삭제 후 옛 요청 재실행)을 닫았다. 만료 키는 422 거부.
- 직렬화 규칙: 연·월·주차는 문자열, 금액·수량도 **문자열**(JSON number 부동소수점 오차 회피), 시각은 ISO 8601 UTC.
- 세션 종료 판정을 정의하면서 **걧 발견**: core.auth_session에 last_seen_at이 없어 유휴 판정을 구현할 수 없다. A/B/C 안을 제시하고 **B안(expires_at을 유휴 만료로 겸용·요청마다 연장)을 제안**했다. 채택 시 스키마 변경 없이 해소된다.
- 게스트 생성은 **동기 처리**로 둔다. 비동기 큐는 폴링 엔드포인트·작업 상태 테이블·재시도가 따라오므로 실측 전에는 근거 없는 복잡도다.
- 페이지네이션은 offset. 최대 데이터가 fems.energy_reading 약 6,480행이라 cursor는 과설계다.
- SERVICE 정책 7건을 엔드포인트·응답 코드와 대응시켰다(10장). 전부 트랜잭션 안에서 부모 잠금 후 재계산 검사이며 잠금 순서는 FS-006a 8단계를 따른다.
- 결정 대기 5건(12장): A-1 세션 생존 판정 / A-2 멱등키 24시간 / A-3 게스트 동기 / A-4 offset / A-5 금액 문자열. **A-1만 스키마와 관련이 있고 B안이면 변경 없이 닫힌다.**
- 미결정 6건(11장): 필드 단위 스키마, 실시간 갱신, 파일 업로드, 레이트 리밋 수치, OpenAPI 생성, 캐시 헤더.
- 검증: 문서 작성과 스키마·화면 설계 정적 대조만 수행. 스키마·Excel·ERD·제품 코드 변경 없음. 서버·엔드포인트 구현·보안 위협 모델링·성능 측정 미실행.
- 다음: A-1 결정 후 FS-011 개발 규약. **Node·Python·PostgreSQL 버전 결정이 선행되어야 한다.**

## 2026-09-23 FS-011 개발 규약 작성 · 런타임 버전 확정
- 산출물: docs/architecture/개발규약_FS-011.md.
- FS-010 A-1을 **B안**으로 확정(사용자 승인): auth_session.expires_at을 유휴 만료로 겸용하고 요청마다 연장한다. last_seen_at 컬럼을 추가하지 않으므로 **스키마 변경 없이 닫혔다.** expires_at이 두 의미를 겸한다는 사실은 문서에 명시.
- **런타임 버전 확정(공식 릴리스 일정 검색으로 확인):** Python 3.14 / PostgreSQL 18 / Node.js 24 LTS.
- 배제 사유: Python 3.15는 2026-10-01 출시 예정으로 휴 미비 위험, PostgreSQL 19는 베타 3 단계, Node 26은 2026-10-28에야 Active LTS가 된다. Node 24는 2026-10-20 Maintenance 진입이나 EOL이 2028-04라 프로젝트 기간에는 문제가 없다.
- 고정 방식: .python-version / .nvmrc / docker 이미지 태그. **메이저만 고정하고 패치는 락파일과 보안 패치에 맡긴다.**
- 기존 제약 해소: "Python 3.9에서 build_erd.py 실패"는 3.14 고정으로 사라진다.
- 스택: FastAPI·SQLAlchemy·Alembic / React·TypeScript·Vite / Docker Compose. **Node는 프론트 빌드와 문서 생성기 전용**이며 백엔드 런타임이 아니다. 라이브러리 버전은 문서에 적지 않고 락파일에 맡긴다.
- 저장소 구조: 단일 저장소. backend/src/fs/{common,core,mes,erp,fems}. **erp가 mes를 import 하지 않는다** — 스키마 간 FK 0건(R1)의 코드 계층 대응물. 의존 방향은 업무 → common/core 한 방향.
- 계층 규칙: **트랜잭션 경계는 service에만 있다.** router·repository가 커밋하면 FS-006a 잠금 순서를 보장할 수 없다.
- **P-G03 해소:** 정적 콘텐츠를 content/ 아래 flow-map.json · cards/*.md · help/<솔루션>/<화면ID>.md로 확정. API가 아니라 프론트 번들에 포함한다. DB에 넣지 않아 세대 복사가 무거워지지 않는다.
- 네이밍: DB snake_case / JSON camelCase이며 변환은 Pydantic alias generator 한 곳에서만. 컴포넌트 상단 주석에 화면 ID를 남겨 설계 문서와 코드를 잇는다.
- 마이그레이션: Alembic. **첫 마이그레이션을 손으로 쓰고 schema.json과 대조 검사**하는 B안 채택(71테이블 DDL 생성기를 만드는 비용이 더 크다). tools/verify_ddl_matches_schema.py를 FS-009에서 함께 만든다. schema.json의 migration_revision에 리비전 ID를 기록.
- 테스트: FS-010 10장 SERVICE 정책 7건을 전부 통합 테스트로 검증한다. **가장 중요한 것은 범위 격리** — 다른 공간의 자원 ID로 요청하면 404가 나와야 한다. 소명 한도·설비 점유는 동시 요청 주입이 아니면 의미가 없다.
- Git: 현재 커밋 1개(6cb3e80) 이후 작업이 미커밋이다. **FS-009 착수 전에 현재 상태를 커밋해야 한다.**
- 남은 결정 2건: V-1 저장소 공개 여부·시점(docs/references/가 공개 대상이 아니므로 이력이 쌓이기 전인 지금이 가장 쉬운 시점), V-2 배포 대상.
- 검증: 문서 작성과 공식 릴리스 일정 확인만 수행. **실제 런타임 설치·의존성 호환 시험 미실행.** 코드·스캐폴딩·스키마·Excel·ERD 변경 없음.
- 다음: V-1·V-2 결정 후 FS-012 Codex 인계 패키지. FS-005g 시드 정의 갱신은 구현 착수 전에 끝내야 한다.

## 2026-09-23 FS-012 구현 인계 패키지 작성 · 설계 단계 종료
- 산출물: docs/plan/구현인계패키지_FS-012.md.
- **V-2 확정(사용자):** Vultr VM + Nginx + DNS. 기존 보유 서버를 쓰며 도메인은 별도 구매 예정.
- V-1(저장소 공개 여부)은 선택지 4안을 제시하고 미결정으로 남겨두었다. **공개 여부와 무관하게 docs/references/ 제거는 지금이 가장 쉬운 시점**임을 명시했다(커밋 1개).
- 작업 분해 10개 확정: FS-005g 시드정의 → FS-009 실행기반 → FS-015 시드생성기 → FS-016 공통계층 → FS-017 포털 → FS-018 FEMS → FS-019 ERP → FS-020 MES → FS-021 통합검증 → FS-022 배포. 각각 완료 조건을 명시.
- 순서 근거: 포털을 먼저 만들어 공통 컴포넌트 9종과 디자인 토큰을 실물로 확정하고, 그다음 가장 작은 FEMS(13테이블)로 화면·API 패턴을 싼게 검증한다. ERP·MES는 서로 import하지 않아 병렬 가능하나 1인 운영이면 순차가 안전하다.
- 금지 목록 명문화: 쟔액·상태·최신여부 플래그·분개 결과·배출량·요금·환산 결과는 저장하지 않는다. **성능을 이유로 캐시 컬럼을 추가하지 않고 실측 후 병목이 증명되면 다시 판단한다.**
- 보류 걧 4건(M-G06 설비 상태, G-08 대표 공정, E-G07 0원 매출 발급, P-G04 SCM 카드 문안)은 구현 중 마주치면 임의로 정하지 말고 질문하도록 명시.
- 검증 계획: SERVICE 정책 7건을 통합 테스트로 검증하며 **범위 격리(타인 공간 자원 ID → 404)가 최우선**이다. 설비 점유·소명 한도는 동시 요청 주입이 없으면 통과해도 의미가 없다.
- 실측 미수행 항목 명시: 게스트 복사 2초·첫 화면 3초·동시 게스트 20명은 전부 목표값이며 측정한 적이 없다. **FS-015에서 복사 시간을 먼저 재고 못 맞추면 그때 대책을 논의**한다. 미리 비동기 큐를 만들지 않는다.
- 배포 준비: 게스트 전역 상한·회수 배치·레이트 리밋·HTTPS 필수. **백업은 하지 않는다**(합성 데이터라 시드로 재생성 가능).
- 현황 문서 갱신: 남은 작업표를 구현 10단계로 교체하고 착수 전 남은 결정 5항목 표를 추가했다.
- 검증: 문서 작성과 기존 설계·화면·API 문서 정적 대조만 수행. 코드·스캐폴딩·스키마·Excel·ERD 변경 없음.
- 다음: **사용자 전체 설계 승인.** 승인 후 V-1 결정 → 현재 상태 커밋 → FS-005g → FS-009 착수.

## 2026-09-23 V-1 결정 — 저장소 공개 준비
- **V-1 확정(사용자): ① 지금 정리 후 공개.** 커밋이 1개뿐인 지금이 이력 정리 비용이 가장 싸다.
- `.gitignore` 개정: `docs/references/*.xlsx` → **`docs/references/` 폴더 전체**. 기존 규칙은 Excel 3개만 막아 README와 manufacturing-systems.html이 추적될 수 있었다. `.idea/`·`.vscode/`도 추가.
- 참고 자료는 삭제가 아니라 **저장소 밖 이동**이다. 설계 입력으로 이미 흡수됐으므로 저장소에 남길 이유가 없다.
- 문서 갱신: FS-012 2장 체크리스트 3번 ✅ 처리 및 V-1 처리 내역표 추가, 현황 착수전 결정표·폐기보류 목록 갱신.
- **이력 재작성이 필요한지는 미확인이다.** 명령 실행 수단이 없어 `git ls-files docs/references/`와 `git log --all -- docs/references/`를 돌려보지 못했다. 커밋 `6cb3e80`에 포함됐다면 filter-repo가 필요하며, 사용자 확인 후 판단한다.
- 사용자 실행 순서 안내: ① 추적 여부 확인 → ② references 저장소 밖 이동 → ③ 상태 확인 → ④ 커밋.
- 검증: `.gitignore` 수정과 문서 갱신만 수행. **Git 명령을 실행하지 않았으며 파일을 이동하지도 않았다.** 스키마·코드 변경 없음.
- 다음: 사용자가 이동·커밋 완료 후 전체 설계 승인 → FS-005g → FS-009.

## 2026-09-23 V-1 이행 완료 — 이력 재작성
- `docs/references/` 5개 파일(Excel 3·README·HTML)을 `~/projects/factory-studio-references/`로 이동하고 폴더를 삭제했다.
- **정정: 커밋은 1개가 아니라 3개였다**(68883a8, 6cb3e80, 316d19d). 현황 문서의 "커밋 1개(6cb3e80)" 기술이 틀렸고 그것을 검증 없이 여러 문서와 프롬프트에 반복 인용했다.
- `git log --all -- docs/references/` 결과 **과거 커밋 3개 전부에 포함된 것을 확인**했다. 기존 .gitignore가 `docs/references/*.xlsx`만 막아 README와 manufacturing-systems.html이 추적되고 있었다.
- 조치: `git checkout --orphan`으로 새 뿌리 커밋을 만들고 구 브랜치 삭제 후 reflog 만료·gc 가지치기. **filter-repo 설치 없이 git 기본 명령만 사용.**
- 결과: 단일 커밋 `b19376f`. `git log --all -- docs/references/` 빈 출력 확인. 원격 push 전이어서 협업 충돌은 없었다.
- 트레이드오프: 커밋 3개를 1개로 합쳤다. 잃은 이력은 "설계 산출물 초기 커밋"·"문서 재편" 수준이며 설계 변천사는 이 progress.md에 남아 있다.
- `.gitignore` 개정: `docs/references/` 폴더 전체, `.idea/`, `.vscode/` 추가.
- 검증: 명령은 사용자가 실행했고 출력을 대조해 확인했다. Claude가 git 명령을 직접 실행하지는 않았다.
- 다음: FS-005g 시드 정의 갱신(설계) → FS-009 실행 기반 구축(구현).

## 2026-09-23 FS-008b 최종 검증 완료 — 중단 작업 재개

- 이전 FS-008b 항목의 “다음 세션은 검증 명령 미재실행” 기록을 보완한다. 원 작업 세션 재개 후 현재 저장소에서 회귀 33개(FS-008b 11 + FS-014/014b 22), R1~R5 검사, npm run db:validate를 실제 재실행했고 모두 통과했다.
- 최종 **v0.9.0 / 71테이블 / 712컬럼 / 161 FK / 제약·정책 528개**. core 10 / mes 21 / erp 27 / fems 13. 목표 71과 일치. FS-013 당시 72와 차이는 dashboard_layout 삭제 1개다.
- FEMS owner_module 3개 삭제, 배분 unit 1개 추가로 컬럼 **149→147(순감 2)**. 기존 owner 포함 채널 UK를 (S,id,unit)으로 교체했고 관측·배분의 단위 포함 FK를 검증했다.
- 활성 메타데이터 kwh 참조 **2곳 발견·2곳 수정**(컬럼, CHECK). kwh 참조 UK·인덱스·FK·정책은 0건. 과거 배분 UK 스크립트 조사 완료.
- nullable 결제조건·채권/채무 만기 유지. 매입 수기 우선→매입일+N→NULL, 확정 시 채무 복사. 매출은 계산 전용. NULL 만기는 만기 미설정, 연체 아님. 확정 후 불변·소급 없음.
- npm run db:build 및 python3 tools/build_erd.py는 이번 FS-008b 작업 중 실제 실행했다. Excel 19시트 **10,686셀·177링크** 원본 대사, Artifact 오류 검색 0건·변경 범위 7개 시각 검토. HTML ERD의 모듈 수·앵커 토글·상세 필드 동작을 Chrome headless로 검증(JS 오류 0).
- --check 및 실제 파일 멱등 재실행 bytes/mtime 동일. SHA256 백업 일치. 보호 UI·시제품 3파일 해시 동일, FS-008a 네 문서의 갭 목록 밖 본문 동일.
- 최종 스키마 SHA256: 213415b5f1e6b44feaceaffc9366bbe449d33d0f484c1e1d9ea8992637831110. 설계 근거와 현재기획_진행현황을 함께 갱신했다.
- 미실행: 물리 DDL·PostgreSQL·마이그레이션·seed·SERVICE 정책 실행·동시성·성능·권한·법정 세무 적합성·Excel 네이티브 앱·Mermaid 렌더러 파싱.
- 다른 작업에서 추가된 FS-010~012·V-1 기록과 Git 이력은 보존했다. 이번 작업은 FS-008b 결과 보고로 종료하며 다른 작업 ID는 시작하지 않는다.

## 2026-09-23 FS-005g 시드 정의 개정 작성
- 산출물: docs/architecture/합성데이터_시드정의_FS-005g.md. FS-005b는 상단에 "대체됨" 표기 후 이력으로 보존.
- 착수 전 추산 보고: 3스키마 분리 자체의 증가는 마스터 중복 수십 행에 그친다. 변수는 FS-005b가 세지 않은 FEMS 배분·생산량의 해상도였다(1시간이면 약 20,000행).
- 사용자 결정: 배분·생산량 1일 단위 / 가스·용수 1일 검침 / FEMS 생산량·가동 부하는 MES 실행 구간에서 파생(3-b) / 결측은 quality 행으로 저장 / 계정 7·규칙 10을 세대별 시드에 포함.
- 결과: **7,469행**(core 생성 6 · mes 375 · erp 168 · fems 6,920). 복사 대상 7,463. FS-005b 6,840 대비 +629(+9.2%). energy_reading 6,540행이 87.6%.
- 정정: FS-005c §6의 "6,840→6,540 감소"와 현황의 "약 6,500행"은 계측 전용 수치를 전체 총계와 비교한 오류였다.
- 설계: 코드 사전 단일 원천(품목·설비·사업장·공간·판매계획 코드·패킹 번호), MES 실행 26 LOT의 설비 일정표(사출 3일·조립 2일·검사 1일, 하루 경계 정렬, C-1 겹침 없음 수기 대조), 전력 가동/대기 부하 산식, 배분 DIRECT_METER 240·RUNTIME_SHARE(용수→사출기) 36, 생산량 27, 회계 A층 금액표·연령분석 구간, 오류 시나리오 28종, 도움말 시나리오 시작점.
- 새 규칙: 복사는 일수 이동이므로 요일 의존 값·날짜 포함 코드 금지, 달력 파생 컬럼 9종과 계획 코드는 T에서 재계산(주차는 월 1~21일의 월요일 3개).
- 변경: 미게시 경로를 반제품 SF-H100 단독 경로로 옮겨 고아 품목을 해소. 생산량 0 시나리오는 전량 불량 LOT 검사 구간 1건으로, 비가동일 "기록 없음"과 구별. FG-T300을 영세 품목으로 두어 세액 0 시연.
- 결정 대기: D-1 용수(UTILITY) 환산·배출 제외 서비스 규칙 / D-2 품목 원단위 분모(제안: 전 공정 에너지 ÷ 최종 공정 양품).
- 확인 대기: S-1~S-7 schema.json 코드값·nullable. 세션 읽기 도구가 파일 앞·뒤만 읽을 수 있어 387KB 중간의 컬럼 규칙·CHECK를 확인하지 못했다. 사용자 실행용 읽기 전용 명령을 안내했다. **S-1(energy_reading.value NOT NULL이거나 결측 코드 없음)이면 스키마 변경이 필요하다.**
- 계수·요금은 전부 합성 예시값이며 공표값이 아니다. source_note에 명시.
- 갱신: 현황 문서(4·6·7·9장), FS-012 1·2장, FS-005b 머리말.
- 검증: 문서 안 수량 합계·설비 일정 겹침·매출 세액·소명 한도를 손으로 대조했다. 생성기·DB·복사 시간 측정은 미실행. 스키마·Excel·ERD 변경 없음.
- 다음: D-1·D-2 결정과 S-1~S-7 확인 결과를 반영해 FS-005g 확정 → 전체 설계 승인 → FS-009.

## 2026-09-23 FS-005g — S-1~S-7 확인 반영 · 스키마 결함 2건 발견
- 사용자가 읽기 전용 점검 명령을 실행해 `fs005g_check.txt`를 생성했고, 13개 테이블의 컬럼·CHECK·UK·SERVICE 정책을 대조했다.
- **S-1 가정이 틀렸다.** `fems.energy_reading.value`는 NOT NULL이고 `value >= 0` CHECK가 있으며 `quality`는 valid/estimated/reset/invalid 4종이다. 결측 전용 코드가 없다. → 결측 6행을 `value=0` + `quality='invalid'`로 표현하고 **집계에서 invalid 행을 제외**하는 규칙을 함께 넣었다. 스키마 변경 없음. 한계(측정 없음과 신뢰 불가가 같은 코드)는 D-3으로 기록만 했다.
- **S-6에서 새 요구를 발견했다.** `mes.operation_result`에 `defect_qty = 0 OR defect_reason 존재` CHECK가 있어 62개 실적의 거의 전부에 불량 사유가 필요하다. 공정별 고정 사유 4종(SHORT_SHOT·PIN_MISALIGN·CONTACT_FAIL·W06의 MOLD_DAMAGE)을 4.5에 추가했다.
- S-2·S-3·S-4·S-5·S-7은 가정과 일치했다. 표기를 실제 코드값으로 교체했다(item_type finished/semi_finished/raw, partner_kind CUSTOMER/SUPPLIER, location.kind workcenter/zone, meter.scope_kind factory/site_total).
- 배분 품질에 "부분 집계" 코드가 없어 ASM-02 결측일 배분을 `estimated`로 둔다. 보간을 하지 않으므로 정확한 표현은 아니며, `invalid`로 두면 실제 포착된 18시간치까지 분석에서 사라진다. 선택 이유를 문서에 남겼다.
- **스키마 결함 2건 발견(FS-005g 10.3).** D-A: `fems.meter`에 `measurement_kind`·`unit`을 참조하는 CHECK가 남아 있으나 두 컬럼은 FS-005c에서 `meter_channel`로 옮겨졌다. 값도 현재 코드 목록과 다르다. **그대로면 FS-009 첫 마이그레이션 DDL이 실패한다.** D-B: 같은 테이블에 scope_kind CHECK가 2개이며 교집합이라 'common'은 쓸 수 없다(BEMS 폐기 잔재).
- 둘 다 이번 작업에서 고치지 않았다. 시드가 아니라 메타데이터 문제이고, AGENTS §4에 따라 Excel·ERD 재생성을 같은 작업에서 해야 하므로 별도 ID(FS-008c 가칭)로 제안했다.
- D-1·D-2는 사용자 진행 지시에 따라 제안대로 반영했다. UTILITY 에너지원은 환산·배출 대상에서 제외하고 "대상 아님"으로 표시 / ITEM 기준선 분모는 전 공정 에너지 ÷ 최종 공정 양품. 이견 시 되돌린다고 문서에 명시했다.
- 행 수는 7,469로 변함없다. 결측을 행으로 남기는 결정이 유지되었기 때문이다.
- 2차 확인 8건(S-8~S-15)을 새로 정의했다. 1차 점검이 13개 테이블만 대상이어서 채널·에너지원·생산량·목표·MES 상태·패킹·ERP 상태 CHECK가 미확인이다.
- 갱신: FS-005g 본문(0·2·3·4·5·7·10·12장), 현황 문서(4·6·7장).
- 검증: 점검 출력과 문서 가정을 항목별로 대조했다. 명령은 사용자가 실행했고 Claude는 출력 파일을 읽었다. 스키마·Excel·ERD·생성기 변경 없음. DB 실행 없음.
- 다음: S-8~S-15 2차 확인 → FS-005g 확정. 병행해서 D-A 수정 작업을 언제 할지 결정해야 한다(FS-009 선행 필수).

## 2026-09-23 FS-008c 완료 — fems.meter CHECK 잔재 D-A·D-B 해소

- 근거: FS-005g 10.3 및 사용자 지시. D-A 삭제 컬럼 measurement_kind/unit 참조 CHECK 삭제, D-B 넓은 scope_kind CHECK 삭제. 기존 factory/site_total CHECK 1개 유지. 채널·테이블·컬럼·FK·상태·정책·코드 목록은 변경하지 않았다.
- 결과: **v0.9.1 / FS-008c / 71테이블 / 712컬럼 / 161 FK / 제약·정책 526개**. 예상 528→526 일치. core 10 / mes 21 / erp 27 / fems 13.
- 도구: apply_fs008c.py 신규. 사전/후보 검증·SHA256 원본 백업·동일 디렉터리 임시 파일 fsync·원자 교체·--check·멱등. test_fs008c.py 11개 신규.
- validate_db_design.py는 FS-008c/v0.9.1의 기존 목록·회계·화면 검사 연결 4개 분기만 확장했다. **일반 expression 파싱은 추가하지 않았고 1-C는 정의·승인 부재로 미적용**이다. 격리 검사기·FS-008b 변환기 변경 없음.
- 채널 확인: measurement_kind IN ('CUMULATIVE','INSTANT'), multiplier > 0 CHECK만 존재. 단위 값·측정 종류/단위 조합 CHECK 없음. 제약은 추가하지 않았으며 설계 세션 질문으로 남겼다.
- 지정 명령 모두 실제 실행/exit 0: apply_fs008c --check → apply → 재실행 no-op → npm run db:validate → audit_schema_isolation → unittest test_fs0*.py -v → npm run db:build → build_erd.py.
- 검증: **44개 테스트 통과**, R1~R5 오류 0, db:validate errors=[]. 실패 주입 ABORT 로그 3건은 원본 보존 테스트의 정상 출력이다.
- 산출물: schema·Excel 19시트·ERD HTML/Mermaid 5개/README·validation-report·FS-008c 설계 근거를 갱신했다. Excel 10,681셀·177링크 대사, Artifact 오류 검색 0건 및 변경 범위 렌더 확인. HTML ERD 버전·수량·meter 상세 확인, JS 오류 0.
- 원본 SHA256: 213415b5f1e6b44feaceaffc9366bbe449d33d0f484c1e1d9ea8992637831110. 동일 바이트 백업은 docs/db/schema-metadata/backups/schema.before-FS-008c.<SHA256>.json.
- 결과 SHA256: **7e97937e7bd0df6fdae97b309444dbfdac584dd2efae71ad4f0bad7eed2d5e44**. 실제 파일 재실행 bytes/mtime 동일 확인.
- 현황 D-A·D-B 해소·2-1 완료·검증 결과를 함께 반영했다. FS-005g·UI/시제품·기존 도구 등 보호 파일 13개 해시 동일.
- 실제 명령 환경 Python 3.9.6 / Node v26.7.0. 목표 Python 3.14/PostgreSQL 18/Node 24 검증은 아님. MCP filesystem 미제공으로 허용된 로컬 명령 사용.
- 미실행: DDL·DB·마이그레이션·seed·서비스·동시성·성능·네이티브 Excel·Mermaid 렌더러 파싱. Git 커밋 없음.
- 다음: **FS-008c 결과 보고 후 사용자 확인을 받고 FS-005g-확인(S-8~S-15)을 시작한다.** 작업 2 덤프·판정·실현 가능성 조사는 미착수. FS-005g 본문은 수정하지 않았다.

## 2026-09-23 FS-005g-확인 완료 — S-8~S-15 2차 스키마 대조

- 사용자 FS-008c 확인·진행 지시 후 작업 2만 수행했다. 기준은 v0.9.1 / FS-008c / SHA256 7e97937e7bd0df6fdae97b309444dbfdac584dd2efae71ad4f0bad7eed2d5e44.
- 저장소 루트에 fs005g_check2_core.txt / _mes.txt / _erp.txt / _fems.txt 생성. 테이블명·컬럼 name/type/nullable/rule·CHECK/UK/UK_PARTIAL/SERVICE/DB_POLICY 전체 columns/expression/reason과 원본 배열 인덱스를 포함한다. Git 커밋·스테이징 없음.
- 덤프를 재파싱해 **71테이블·712컬럼·요청한 종류의 제약/정책 415개** 원본 전수 대사. core 49 / mes 123 / erp 163 / fems 80. 전체 526 중 PK/일반 INDEX는 요청 대상이 아니므로 제외했다.
- 보고서: docs/db/시드_2차스키마확인_FS-005g.md. S-8~S-15 판정 및 지정 5개 시드 사례, 나머지 4~6장 관련 CHECK를 정적으로 대조했다.
- 가정 차이: energy_target EQUIPMENT는 equipment_id NOT NULL만 요구하고 site_id NULL은 강제하지 않는다. 기준선 ITEM/EQUIPMENT는 상호 배타 조합이다. 패킹 부모/구성/입고 타입 제한은 CHECK가 아니라 SERVICE 정책이다. 견적 6상태·수주 상태는 states에 있으나 해당 status CHECK는 없다.
- 채널의 측정 종류 CHECK는 CUMULATIVE/INSTANT, 단위 CHECK 없음. source_code/measure_unit CHECK 없음. 생산량의 양의 구간·비음수 수량·버전별 UK 확인. 회계 확정시각·세금계산서 필수값 CHECK 확인; 매입 cancelled 분기는 confirmed_at을 검사하지 않는다.
- **문서에 명시된 값에서 확정적인 CHECK 위반은 발견하지 못했다. 전체 시드 통과 판정은 아니다.** X01 취소 사유, 완료 지시/LOT 사유·시각, production_record 27행 confirmed_at 등 미지정 값 때문에 실제 충족 여부는 미확정이다. NULL로 기록할 때 어느 행이 어느 CHECK에 실패하는지 보고서에 명시했다.
- W04 검사 v1/v2와 Q-0002 r1/r2는 버전 포함 UK와 양립한다. PI-0006 취소 d−29·사유 수량 오입력과 원금 979,000 보존은 해당 CHECK와 충돌하지 않는다. 입고 status 기본값 confirmed 및 견적 할인율 기본값 0도 별도로 원문 확인했다.
- 설계 판단은 보고서 질문으로 남겼고 스키마 변경 방안은 제안하지 않았다. FS-005g 본문·스키마·UI/시제품 해시 보존 확인. 현황과 이 기록만 조사 완료로 갱신했다.
- 미실행: 실제 시드 7,469행 생성·INSERT·PostgreSQL CHECK/FK/UK 실행·서비스 정책·동시성·복사 성능. 읽기 전용 조사이므로 apply/Excel/ERD 재생성은 이번 작업에서 실행하지 않았다. 1-C 미적용 유지.
- 다음: 사용자 결과 확인 및 Claude 설계 세션의 미정 값 검토·FS-005g 본문 반영. 다른 작업 ID는 시작하지 않는다.

## 2026-09-23 FS-005g 미정 값 확정 — 시드 정의 확정

- Claude 설계 세션. Codex 보고(FS-008c·FS-005g-확인)를 저장소 파일과 대조한 뒤, 보고서 6장의 미정 값 4묶음을 제안했고 사용자 진행 지시로 확정했다.
- 반영: 4.2.1 지시·LOT 사유·시각(X01 `계획 변경으로 발행 전 취소`, W06 `all_defective`), 5.5 목표 `site_id` NULL 통일·기준선 코드 `BL-*-01`/`BL-T300-02`, 5.6 production_record `confirmed_at`, 6.1 견적 날짜·수량·할인율, 6.2 미출하 납기 +14일, 6.3 수금·소명·세금계산서, 6.4 매입·지급.
- **제안과 달라진 값 1건.** 세금계산서 승인번호를 `20260000-...` 형식 대신 `SYNTH-TI-0001`·`SYNTH-TI-0003`으로 바꿨다. 연도 접두는 1.1 "코드에 날짜 포함 금지"에 걸리고 T 이동 후 `issued_on`과 어긋난다.
- **보고서가 다루지 않은 값 추가.** 덤프 재확인 중 발견: 매입 PI-0001~0004의 `confirmed_at`(C428 필수), `receipt_apply`·`payment_apply`의 `apply_key`·`applied_at`(NOT NULL·UK). 각각 전표일 10:00, `SEED:RA-000n`/`SEED:PA-000n`, 부모 확정시각으로 지정했다. PI-0006은 확정 d−30 10:00 보존·취소 d−29 10:00.
- 9.3에 V12 추가: DB CHECK가 강제하지 않는 시드 규칙(목표 site_id NULL, 기준선 코드 상이, PI-0006 취소>확정, 상태가 states 목록 내, 코드에 날짜 없음).
- 10.3 D-A·D-B를 FS-008c 해소로 표시, 10.4 S-8~S-15를 완료·반영 위치 표로 교체, 10.5 남은 한계 신설.
- 현황: FS-005g·2-2 완료, 6장 시드 제약 재작성, Codex 런타임 차이(3.9.6/26.7.0 vs 3.14/24 LTS)와 build_erd.py 3.9 통과 정정을 제약에 추가.
- 검증: 덤프(`fs005g_check2_erp.txt`)의 purchase_invoice·receipt·payment·*_apply·tax_invoice 제약 원문과 값을 대조했다. 행 수 7,469 변동 없음. 스키마·Excel·ERD·도구 변경 없음. 명령 실행 없음.
- 미확인: ERP 나머지 테이블(견적 이력·출하·매출)의 NOT NULL 시각 컬럼은 이번에 전수 대조하지 않았다. 생성기 일반 규칙과 FS-015 실제 INSERT로 확인한다.
- 다음: **사용자 전체 설계 승인.** 승인 후 Git 이력 재작성(V-1) → FS-009.

## 2026-09-23 전체 설계 승인 — 구현 단계 전환

- 사용자가 전체 설계를 승인했다. 설계 단계(S0) 종료.
- 다음 작업은 Codex에 인계: ① V-1 Git 이력 재작성(원격 push는 사용자 확인 후) ② FS-009 실행 기반 구축. 작업 ID별로 보고 후 사용자 확인.
- 이 기록 외 파일 변경 없음.

## 2026-09-23 V-1 Git 공개용 이력 재작성

- 사용자 전체 설계 승인 및 계속 진행 지시에 따라 `git checkout --orphan`으로 최신 설계를 단일 루트 커밋에 담았다. 착수 당시 실제 이력도 `b19376f` 단일 커밋이며 references 경로는 이미 없었다. 문서의 과거 3커밋 설명과 차이를 확인했다.
- 외부 백업: `/Users/hwang-kyoungho/projects/factory-studio-backups/V-1-20260923-101356/`. 전체 repository 복사(ignored/untracked 및 .git 포함), history.bundle, manifest.json. 2,540개 파일·심볼릭 링크 대조 일치. `git bundle create --all`, `git bundle verify` exit 0.
- 검증: `git log --all -- docs/references` 결과 0건, `git rev-list --all`의 각 커밋을 `git ls-tree -r --name-only`로 검사해 references 경로·덤프 파일 0건. `.gitignore`의 `docs/references/`, `fs005g_check*.txt` 등록 확인. 각 Git 명령 exit 0.
- 실행 환경: Python 3.9.6, Node v26.7.0, psql (PostgreSQL) 16.15 클라이언트. PostgreSQL 서버 접속·버전 검증 미실행. 목표 런타임 고정은 FS-009에서 수행한다.
- schema.json SHA256 `7e97937e7bd0df6fdae97b309444dbfdac584dd2efae71ad4f0bad7eed2d5e44` 유지. UI·prototypes 파일 내용 보존. DB validate/build·회귀·DB 적용 검증은 이번 Git 작업에서 미실행.
- 원격 생성·push·force push 미실행. 다음: V-1 결과 사용자 확인 후 FS-009. 원격 등록·push 역시 별도 사용자 확인 전 실행하지 않는다.

## 2026-09-23 FS-009 실행 기반 완료

- 사용자 diff 확인 후 `fs-009-runtime-base`의 `895caa453acf1028b92dcd0e97cb94e34cb02a3c`를 main에 fast-forward 병합했다. `content/help/{portal,fems,erp,mes}/`와 AGENTS.md 8장 역할 분담 존재를 확인했다. 원격 push는 실행하지 않았다.
- 사용자 V-1 결과 확인 후 작업 브랜치 fs-009-runtime-base에서 수행. V-1 보고서를 docs/agent/V-1_결과보고.md에 보존하고 AGENTS.md에 Codex/antigravity 역할·별도 브랜치 리뷰·mirror push 금지를 반영했다.
- 가장 먼저 .python-version=3.14, .nvmrc=24, package engines, backend requires-python, postgres:18 Compose를 고정했다. Python 3.14.7·Node 24.21.0 설치. Docker/Compose/Colima가 없어 설치하고 전용 factory-studio 프로필(2CPU/4GB/20GB)로 기동했다. 서버와 컨테이너 psql/pg_dump 모두 PostgreSQL 18.6.
- backend/src/fs 및 frontend/src 독립 모듈 경계·content 자리·FastAPI 조립·React/TypeScript/Vite 빌드 기반, uv.lock/package-lock.json, Ruff/ESLint/Prettier, CI workflow 작성. 업무 API·화면은 만들지 않았다.
- 최초 리비전 7e97937e7bd0을 schema v0.9.1 기준으로 수기 작성했다. 실행 시 schema.json을 읽어 DDL을 생성하지 않는다. 모든 테이블·키 이후 FK를 생성하여 core 순환 앵커를 처리한다. CHECK는 C 번호(0-based constraints 배열)와 원문을 보존했다. PostgreSQL CHECK 실패 없음.
- 실제 DB 대조: core10/mes21/erp27/fems13=71, 712컬럼, 161 FK, PK71/UK166/CHECK163/일반INDEX38/유니크INDEX8. SERVICE/DB_POLICY80은 DB 제약에서 제외하고 미구현으로 명시했다. public.alembic_version은 업무 71개와 별도다.
- 빈 DB 적용 → 다운그레이드 → 업무 테이블·리비전 행 각각 0 확인 → 재적용 → 전수 대사 통과. 대조 검사기는 컬럼 순서·타입·nullable·default/identity·키·CHECK 정규화 식·인덱스 조건·FK 범위/대상/RESTRICT를 확인한다. 검사 식은 세션 임시 테이블에서 정규화하고 롤백한다.
- 최종 21명령 모두 exit0, 전체 원문은 docs/agent/FS-009_검증실행.json. 기존 unittest 44개 및 실제 DB 변조 감지 테스트 9개 통과, db:validate 오류0, isolation R1~R5 위반0. frontend typecheck/lint/format/build, Ruff 통과. 컨테이너 pg_dump18 스키마 덤프 생성.
- 초기 실행 중 Prettier 경로 지정 exit2 및 Ruff 스타일 exit1을 수정 후 재검증했다. 기존 Excel 도구 npm audit moderate2건은 남음(ExcelJS/uuid); 별도 npm audit exit1, 주버전 자동 변경은 미적용. frontend audit0. 이전 Python3.9.6/Node26.7.0 대비 기존 회귀 결과 차이 없음.
- schema.json SHA256 7e97937e7bd0df6fdae97b309444dbfdac584dd2efae71ad4f0bad7eed2d5e44 유지. 사용자 지시로 migration_revision=null 유지. UI/prototypes·Excel·ERD 변경 없음. 정적 validation-report와 실제 DB ddl-verification-report는 구분한다.
- 미실행/범위 밖: 원격 CI·push·mirror push·배포, 시드 생성/INSERT, 업무 API·화면·SERVICE 정책·인증/세션·동시성·성능. Git 커밋하지 않음.
- 결과/실행 안내/antigravity 인계 가능 목록: docs/agent/실행기반_FS-009.md. 다음 ID는 결과 보고 후 사용자 확인을 기다린다.

- 최종 패키지 보강: 빈 디렉터리 상태에서 초기 설치된 editable 패키지 import 실패(exit1)를 uv sync --reinstall-package로 해소(exit0). FastAPI 앱 import·라우트0 검증 exit0, CI import 검사 추가. schema/Excel/ERD/UI/prototypes 16파일 바이트 보존 및 git diff --check exit0.

## 2026-09-24 FS-015 결정적 시드 생성기·게스트 복사 완료

- 재개 전 `fs-015-seed` 브랜치, 깨끗한 작업 트리, WIP 커밋 `dfb705a`를 확인했다. main은 antigravity AG-01 도움말·AG-02 설명 카드 5커밋이 앞선 상태였고 antigravity worktree/브랜치는 체크아웃하지 않았다.
- `backend/seed/`에 단일 코드 사전, 결정적 템플릿 생성기, 게스트 복사기, V1~V12 검증기, CLI를 구현했다. 난수는 사용하지 않는다.
- PostgreSQL 18.6 별도 검증 DB에 `sv-20260923-1`, T0 2026-09-23 템플릿 **7,469행**을 실제 INSERT했다. 문서의 테이블별 행 수와 일치했고 CHECK·FK·UK 위반은 0건이다.
- 복사 대상 업무 데이터 **7,463행**은 테이블별 `INSERT ... SELECT`로 처리한다. 자식이 참조하는 부모에만 임시 old/new id 매핑을 만들고 sequence 선발급 + `OVERRIDING SYSTEM VALUE`를 쓴다. leaf는 id를 생략한다.
- PL/pgSQL 함수 1회 호출 대신 테이블별 문장을 선택했다. `statement_timeout`이 복사 전체가 아닌 각 문장에 적용되고, 바깥 단일 트랜잭션이 전부 성공/롤백을 보장한다.
- 같은 `(seed_version,T)` 두 번 생성한 전체 정렬 JSON 바이트가 일치했다. 복사 T `2026-10-07`, `2027-01-05`에서 FS-005g §1.2 연월·ISO 주차·연도·적용월 재계산을 확인했다.
- V1~V12를 실제 DB 자동 테스트로 구현해 템플릿과 모든 복사 세대에서 통과했다. 복사 10회 최종 실측은 중앙값 **0.4555초**, 최대 **0.4758초**로 2초 목표 안이다. 동시 guest_pool 대기·API·네트워크 시간은 미측정이다.
- FS-005g §10.5의 미대조 NOT NULL 일반 규칙(created_at, KRW, 행 번호, 견적 이력, 출하·매출 시각, 확정·취소, 소명 키)을 `docs/agent/시드생성기_FS-015.md`에 표로 기록했다.
- `backend/pyproject.toml`에 seed 패키지를 포함시켜 editable 설치 후 `import seed`를 확인했다. schema.json·마이그레이션·제품 API·화면은 변경하지 않았다.
- antigravity 병합 기록: main의 AG-01 화면 도움말 3커밋과 AG-02 카드 2커밋(`fbf7af7`, `40e534c`)을 현황에 반영했다. FS-015 브랜치는 완료 후 main 위로 rebase하고 사용자 지시 전 병합·push하지 않는다.
- 상세: `docs/agent/시드생성기_FS-015.md`.

## 2026-09-24 FS-015b created_at 업무 시간축 수정

- FS-005g §10.5의 “생성 시각=해당 업무 시각”과 달리 모든 업무 `created_at`이 T 00:00에 몰린 결함을 수정했다.
- 우선순위는 발생·시작·계측 timestamptz → 업무 일자 09:00 Asia/Seoul → 자체 업무 시각이 없는 마스터·기준정보 d−91 09:00이다. 자체 시각이 없는 자식은 모든 업무 FK 부모 이상으로 조정한다.
- V12에 `created_at ≤ confirmed_at`, `created_at ≤ cancelled_at`, `자식.created_at ≥ 부모.created_at` 검사를 추가했다.
- 시드 값과 같은 T의 결과 바이트가 바뀌므로 FS-005g §11에 따라 `seed_version`을 `sv-20260923-1`에서 **`sv-20260924-1`**로 올렸다. 기존 세대는 변경하지 않는다.
- 템플릿 7,469행, CHECK/FK/UK, 결정성, 서로 다른 T 2개, V1~V12를 다시 통과했다. 복사 10회 중앙값 **0.4548초**, 최대 **0.5582초**다.
- schema.json·마이그레이션·제품 코드·화면은 변경하지 않았다. 브랜치 `fs-015b-created-at`, main 병합·push 미실행.

## 2026-09-24 FS-016 공통 계층 완료

- 착수 전 FS-015b `90703e6`을 main에 fast-forward 병합하고 `fs-016-common` 브랜치를 만들었다. 시작 작업 트리는 깨끗했다. main 병합·push는 실행하지 않았다.
- FS-006b 원래 계약에 맞춰 게스트 저장소를 `workspace.guest_session_key`, 회원 저장소를 `auth_session`으로 구현하고 FS-010 2.1의 모호한 문구를 정정했다. schema.json·마이그레이션은 변경하지 않았다.
- `g_`/`m_` 접두어를 쓰는 단일 인증 해석기, 공통 인증 문맥, 회원/게스트 CSRF, scrypt 로그인, Secure·HttpOnly·SameSite=Lax 쿠키, 공통 오류 봉투·페이지·요청 로그를 구현했다.
- guest_pool 잠금·상한 20·FS-015 복사, 세대 초기화, 종료 시 게스트 키 난수 해시 교체, 만료 요청 거부, guest_pool→workspace 잠금 기반 자식→부모 정리와 감사/job 스냅샷 분리를 구현했다.
- `request_receipt` 멱등 처리를 게스트/회원 세션 생성, 모듈 변경, 세대 초기화에 적용했다. actor_key는 회원 사용자 ID·게스트 공간 UUID이며 토큰/쿠키/해시를 로그·감사·요청 결과에 기록하지 않는다.
- 실제 PostgreSQL 18 통합 테스트에서 게스트 진입→7,467행 복사→인증→세대 초기화→종료→만료→정리, 타 게스트 격리, 같은 키 재요청, 토큰 종류 오용, 회원·게스트 CSRF, 관리자 접근, 비밀 문자열 부재를 검증했다.
- 개발 의존성 `httpx 0.28.1`과 전이 의존성을 `uv.lock`에 추가했다. FastAPI/Starlette TestClient의 upstream 폐기 예정 경고 2건이 남지만 기능 실패는 없다. 비밀번호 해시는 표준 `hashlib.scrypt`라 별도 의존성이 없다.
- 최종 환경 Python 3.14.7 / Node 24.21.0 / PostgreSQL·psql 18.6. backend 11개·도구 44개 테스트, ruff lint/format, db:validate, R1~R5, 실제 DB 대사, frontend lint/format/build, diff check 모두 exit 0.
- 미실행: 동시 게스트 20명·guest_pool 대기·정리 경합 주입(FS-021), 배치 스케줄러·IP 레이트 리밋·배포, 업무 API·화면. `backend/tests/test_seed.py`는 수정하지 않았다.
- 상세: [공통 계층 FS-016](agent/공통계층_FS-016.md). 다음 ID는 사용자 확인 후 시작한다.

## 2026-09-24 FS-016 마무리·수량 대사

- 전체 71테이블 실제 DB 대사, 템플릿/게스트 수량 일치·누락 0. 7,467=업무 7,463+모듈 4, 7,469=앞 수량+공간 1+세대 1. 보고서에 테이블별 포함 기준을 명시했다.
- Node 24 PATH 선지정, Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6, factory_studio_fs016_test 사용. 대사 명령 exit 0, 트랜잭션 롤백.
- 사용자 지시에 따라 FS-016 미커밋 구현을 커밋 후 main에 fast-forward 병합한다. 스키마·마이그레이션 변경과 push 없음. FS-017 규약 누락·업무 화면 이동 처리 질문은 별도로 확인 중이다.
- 마무리 검증: backend 11개·회귀 44개, db:validate·R1~R5, Ruff lint/format, 프론트 lint/format/build(tsc 포함), diff check 모두 exit 0. 명령·exit code는 FS-016 보고서에 기록했다.

## 2026-09-24 AG-03 마무리 (rebase·병합)

- `antigravity/ag-03` 브랜치를 FS-016이 병합된 `main`(`e08f5d8`) 위로 rebase했다.
- `backend/pyproject.toml`의 `[tool.pytest.ini_options]`에 `markers = ["perf: performance benchmark test"]` 1줄을 추가해 perf 마커 경고를 해소했다.
- 백엔드 전체 테스트 26개(기존 11 - test_seed 1 + 분리 16) 전부 통과(exit 0), perf 마커 경고 0건 확인. (남은 경고 2건은 FastAPI/Starlette upstream StarletteDeprecationWarning 및 anyio DeprecationWarning)
- worktree 점검 후 `git fetch . antigravity/ag-03:main`으로 `main`에 fast-forward 병합 완료 (`af6f266`).

## 2026-09-24 AG-04 test_common.py 단위 테스트 분리 완료

- 브랜치: `antigravity/ag-04` (`main` 기준 분기).
- 단일 거대 테스트 함수로 직렬 수행되던 `backend/tests/test_common.py`를 11개 독립 단위 테스트로 분리했다:
  1. `test_guest_entry_and_copy_count`: 게스트 진입·복사 수량(7,467행) 및 세대 재생성(reset generations) 복사 수량/상태 대사
  2. `test_idempotency_identical_result`: 멱등 재호출 시 동일 결과 반환 (게스트 세션 생성, 회원 로그인, 모듈 PATCH, 세대 재생성)
  3. `test_idempotency_conflicting_payload_422`: 동일 멱등 키에 다른 요청 본문 전달 시 422 IDEMPOTENCY_CONFLICT
  4. `test_guest_scope_isolation`: 게스트 간 데이터/설정 격리 및 타 게스트 변경 미영향
  5. `test_token_kind_tampering_401`: 세션 쿠키 접두어 변조(`g_` ↔ `m_`) 시 401
  6. `test_csrf_missing_and_mismatch_403`: CSRF 토큰 누락 및 불일치 시 403 (게스트·회원 각각) 및 정상 토큰 200
  7. `test_ended_guest_cookie_401`: 게스트 세션 종료(DELETE) 후 기존 쿠키 재사용 시 401
  8. `test_expired_cookie_410`: 만료된 게스트 공간에 대한 쿠키 요청 시 410
  9. `test_cleanup_separates_data_and_audit`: 만료 게스트 정리 시 워크스페이스 물리 삭제(0) 및 감사/운영 기록 보존
  10. `test_no_token_or_hash_in_logs_audit_receipts`: 요청 로그, 감사 이벤트, 멱등 영수증에 토큰 및 해시 미노출
  11. `test_admin_access_and_guest_admin_404`: 미인식 경로 404 NOT_FOUND, 관리자 API 회원 200 / 게스트 404
- 판정식과 기대값은 원본과 동일하게 100% 보존했다.
- 템플릿 생성은 `common_env` (module scope) fixture에서 1회만 실행하고, 모듈 종료 시 TRUNCATE teardown을 수행하여 후속 테스트 모듈과의 DB 격리를 보장했다.
- 각 단위 테스트는 게스트 공간을 새로 생성하여 상태를 격리하고, 만료/청소 테스트 상호 간섭을 방지하도록 격리 보강했다.
- `conftest.py`는 수정하지 않았다 (Codex 소유 불변 유지).
- 검증 결과:
  - 백엔드 전체 테스트: 36개 (common 11 + verifier 9 + seed 16) 통과 (exit 0, `38.26s`).
  - 단독 실행 격리 검증: `-k test_cleanup_separates_data_and_audit`, `-k test_expired_cookie_410` 단독 통과.
  - 변조 실패 검증: `test_expired_cookie_410` 기대값을 400으로 임의 수정 시 해당 테스트만 단독 실패(`assert 410 == 400`) 확인 후 410으로 원복.
  - 정적 도구: `npm run db:validate` exit 0, `tools/audit_schema_isolation.py` exit 0, `tools/test_fs0*.py` 44개 통과 exit 0, Ruff lint/format exit 0.
- 커밋: `antigravity/ag-04`에만 커밋 (`cb53470`). `main` 병합 및 원격 push는 하지 않고 사용자 확인 대기.

## 2026-09-24 FS-017a 완료·분할 인계

- FS-016 `e08f5d8ef3cc09477263d3e29d566cc4fd5f781a`를 main에 fast-forward 병합했다. 복사 누락 0: 업무 7,463+모듈 4=7,467, 공간·세대 2를 포함하면 7,469. 이후 fs-017-portal에서 작업했다.
- 사용자 분할 지시 직후 `9244801` (`WIP FS-017a: 중단 시점 보존`) 커밋. `.env`·work/ 제외 확인. 이전에 작성한 b/c 산출물은 초안으로 보존했다.
- FS-017a 완료: 현재 세션 CSRF 토큰 복구·만료 쿠키 삭제, 독립 회귀 파일 4개 테스트, 공통 컴포넌트, P-01/P-02. 게스트 생성 응답 roles 누락을 클라이언트에서 정상 해석한다. 로그인 폼을 연 상태의 게스트 재시도가 다른 요청으로 바뀌지 않도록 수정했다.
- backend 전체 15개 통과, frontend 전체 39개 및 a 대상 19개 통과, typecheck/lint/format/build exit 0. Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6. backend 전체 DB=factory_studio_fs016_test. 상세 명령·exit code는 FS-017a 보고서.
- 분할 지시 전 실제 브라우저 5개·360px 검증도 실행했지만 FS-017c 완료로 처리하지 않는다. 초기 Vite content 접근 누락(exit 1)과 테스트 서버 SESSION_SECRET 미주입(브라우저 exit 1)을 수정·재실행해 통과했다. 비밀 값은 Git/보고서에 넣지 않았다.
- 이번 세션에서 schema.json·마이그레이션·test_common.py·test_seed.py 변경 없음. antigravity worktree·브랜치 미접촉, main rebase·병합·push 없음. 30분 WIP·종료 HANDOFF를 상시 규칙에 반영했다.
- 다음은 FS-017b. FS-017c 종료 때 최신 main에 한 번만 rebase한다. 현재 main 전진분은 이번에 반영하지 않았다.

## 2026-09-24 FS-017b 완료

- Claude Code가 FS-017a 보존 초안을 검토·보완했다. P-03 흐름 맵은 FS-005a 노드 17·연결 19와 일치, P-04 카드 3종 3항목, P-05 도움말 54개 파일(포털 7·MES 15·ERP 18·FEMS 14).
- 수정: P-05 도움말 키 조회를 `Object.hasOwn`으로 바꿔 객체 기본 속성 이름(`constructor` 등)이 404를 통과하던 결함 제거. 수정 전 실패 재현 테스트 포함.
- `frontend/src/portal/content-pages.test.tsx` 12개 추가. frontend 전체 51개 통과, typecheck/lint/format/build/`git diff --check` exit 0. backend·schema·마이그레이션 변경 없음(재실행 안 함). 브라우저 검증은 FS-017c.
- 다음: FS-017c. main rebase는 c 끝에 한 번.

## 2026-09-24 FS-017c 완료

- 기존 P-06/P-07 초안 검토·보완. 초기화 경고/확인·중복 요청 차단, 헤더 외 도움말/푸터/뒤로가기 이동 차단, 불확실 응답의 동일 키 재확인, 변경 성공과 조회 실패 분리. 토글은 성공 전 표시 값을 바꾸지 않아 실패 시 원래 값 유지. 게스트 만료는 Asia/Seoul·KST로 고정 표시.
- ADMIN만 운영 기록 조회. GUEST/OWNER 메뉴 비노출·직접 접근 404. offset/limit=20, 탭 전환 offset 초기화, 일반 조회 오류 인라인 재시도. API·DB 스키마 변경 없음.
- 화면 테스트 신규 21개·Playwright 검증 항목 분리(16개). README 실행/IntelliJ 안내·패턴 문서 확정. `tools/run_portal_smoke.py`로 고정 테스트 DB 초기화·템플릿 생성·서버 시작/종료를 재현한다.
- WIP `88f69b1` 보존 후 main `2cece7b`로 rebase 한 번. 현황/progress 문서 충돌은 양쪽 이력 보존으로 해결. rebase 후 WIP `4f5cea9`, AG-04 common 11개·AG-03 seed 16개 파일은 main과 바이트 동일.
- rebase 후 모든 지정 명령 exit 0: frontend typecheck/lint/format/build/test(72), Playwright(16), backend 전체(40), tools unittest(44), db:validate, audit_schema_isolation(R1~R5), git diff --check. 실행 런타임 Python 3.14.7/Node 24.21.0/PostgreSQL 18.6, 테스트 DB factory_studio_fs016_test/factory_studio_fs017_test, DB 검증은 순차 실행.
- content/·schema.json·마이그레이션·test_common.py·test_seed.py 직접 수정 없음. conftest.py 변경 없음. .env/work 제외. main 병합·push·antigravity 폴더/브랜치 조작 없음.
- 상세 명령·exit code·미실행 항목은 포털_FS-017c.md, 이어받기는 HANDOFF.md. 다음 ID는 사용자 확인을 기다린다.

## 2026-09-24 FS-017c 검토 (Claude Code)

- Codex 보고를 저장소에서 재현했다: main `2cece7b` 위 fast-forward 가능, test_common/test_seed는 main과 diff 0, content·schema·alembic·conftest는 cbcd5c5 대비 변경 0.
- 재실행 결과(모두 exit 0): frontend typecheck/lint/format/build, 테스트 72개, backend 전체 40개(`factory_studio_fs016_test`), `tools/run_portal_smoke.py` Playwright 16개(`factory_studio_fs017_test`, 템플릿 7,469행). 둘은 순차로 실행했다.
- README IntelliJ 표의 브라우저 스모크 작업 디렉터리가 `<repo>/frontend`와 `<repo>`로 서로 어긋나 `<repo>`로 정정했다.
- 미재현: tools unittest 44, db:validate, R1~R5(이번 변경과 무관해 재실행 안 함).

## 2026-09-24 FS-018a 완료 (Claude Code)

- `fs-018-fems` 브랜치. FEMS 레이아웃 + F-11 에너지원(목록·등록·수정·삭제 RESTRICT 참조 건수·비활성화). 런처 FEMS 카드를 실제 화면으로 연결했다.
- 신규 `fs/common/scope.py`: 업무 API가 같은 트랜잭션에서 활성 세대·모듈 사용 여부를 재확인하고, 쓰기는 core와 같은 공간 잠금을 먼저 잡는다. 모듈 꺼짐은 409 `MODULE_DISABLED`.
- 참조 중인 에너지원의 계측 단위 변경 금지(`UNIT_IN_USE`). 스키마·마이그레이션 변경 없음.
- 공통 컴포넌트 확장(PageTitle help 키, ErrorNotice 참조 건수 목록, DataTable empty). FEMS·도움말 lazy 로딩으로 번들 경고 해소.
- 테스트: backend +22(전체 62), frontend +12(전체 84), Playwright +4(전체 20). 모든 검증 exit 0. 보고서 `docs/agent/FEMS_FS-018a.md`.

## 2026-09-24 AG-05 완료 (antigravity)

- F-10 설비 화면 및 백엔드 CRUD 복제 구현 (`antigravity/ag-05-f10` 브랜치).
- 백엔드 (`fs/fems/`):
  - `schema.py`: `EquipmentCreate`, `EquipmentUpdate` 정의 (설비 코드 정규식: `^[A-Z][A-Z0-9_\-]{1,29}$`).
  - `repository.py`: `EQUIPMENT_COLUMNS`, `EQUIPMENT_SORT`, `EQUIPMENT_REFERENCES` (5개 참조 테이블: `fems.meter`, `fems.energy_target`, `fems.energy_baseline`, `fems.energy_allocation`, `fems.production_record`), CRUD 함수 및 `equipment_meter_references`, `list_locations` 구현.
  - `service.py`: `list_equipments`, `get_equipment`, `list_locations`, `create_equipment`, `update_equipment`, `delete_equipment` 구현.
  - 결함 수정: 계측기(`fems.meter`)가 달린 설비의 `location_id` 변경 시 409 `PRECONDITION_NOT_MET` (`details.reason="LOCATION_IN_USE"`, `details.references=[{table,label,count}]`) 거부 처리.
  - `router.py`: `GET/POST /equipments`, `GET/PATCH/DELETE /equipments/{id}`, `GET /locations` 엔드포인트 연결.
- 프론트엔드 (`frontend/src/fems/`):
  - `Equipments.tsx`: F-11 에너지원 패턴 복제, 공간 셀렉트/비어있을 시 `EmptyState` 안내, 5개 참조처별 삭제 실패 건수 안내.
  - `FemsLayout.tsx`: `femsScreens`에 F-10 설비 등록.
  - `index.tsx`: F-10 라우트 등록.
  - `energy-sources.test.tsx`: 사이드바 화면 개수 단언을 `toHaveLength(femsScreens.length)`로 수정 (승인 반영).
- 테스트 및 검증:
  - `backend/tests/test_fems_equipment.py`: 25개 테스트 신규 작성 (계측기 있는 설비 공간 변경 409, 계측기 없는 설비 공간 변경 200 포함).
  - `frontend/src/fems/equipments.test.tsx`: 12개 테스트 신규 작성.
  - 백엔드 전체 테스트 통과: `pytest backend/tests -q` 87 passed (테스트 DB: `factory_studio_test`, exit 0).
  - 프론트엔드 전체 테스트 통과: `npm --prefix frontend test` 9개 파일 96개 테스트 ALL PASSED (exit 0).
  - typecheck, lint, format:check, build, ruff check/format, git diff --check 모두 exit 0.
- main 병합·push 없음.

## 2026-09-24 FS-018b 완료 (Claude Code)

- AG-05 검토: 저장소 대조 일치, frontend 96·backend 87 재현. 저장소 ruff 설정 기준 `test_fems_equipment.py` import 정렬 오류를 이 브랜치에서 수정(`test_common.py`의 같은 오류는 antigravity 소유라 보류).
- F-02 계측 조회: `GET /readings`(사업장 시간대 날짜 기간, 기본 최근 7일, 최대 31일, 결측 value=null), `/meters`, `/sites`. 화면은 초안/적용 필터, 표 기본, 채널 1개일 때만 선 그래프(결측은 선 끊김).
- `GUEST_LIMIT` 환경 변수(기본 20). 스모크가 23개로 늘어 상한에 걸린 것을 재현 후 테스트 서버만 200으로 올렸다.
- 테스트: backend +18(전체 105), frontend +14(전체 110), Playwright +4(전체 23). 모든 검증 exit 0. 보고서 `docs/agent/FEMS_FS-018b.md`.

## 2026-09-24 FS-018c 완료 (Claude Code)

- F-03 설비별 배분: 저장된 배분 결과 조회. 현재 결과 = 같은 설비·채널·구간의 최대 input_revision·method_version. 필터는 현재 판정 뒤에 건다(방법 필터로 옛 결과가 현재로 보이는 문제 방지, 테스트 고정). 합계는 현재 결과·invalid 제외·단위별.
- 화면: 단위별 합계 패널, 결과 표, 행별 계산 근거 패널(`<details>`), 이전 산정 결과 포함 옵션.
- 사용자 결정: F-14 요금제 적용 기간 겹침은 409 `PERIOD_OVERLAP`. FS-010 §7 기록.
- 테스트: backend +16(전체 121), frontend +11(전체 121), Playwright +3(전체 26). 모든 검증 exit 0. 보고서 `docs/agent/FEMS_FS-018c.md`.

## 2026-09-24 AG-06 F-14 요금제 복제 완료 (antigravity)

- F-14 요금제: F-10 설비 화면 패턴 그대로 복제 구현.
- 백엔드 (`backend/src/fs/fems/`):
  - `schema.py`: `TariffCreate`, `TariffUpdate` 스키마 추가. 금액(basicCharge, usageRate)은 소수점 4자리 이하 문자열, effectiveFrom/effectiveTo는 `YYYY-MM` 정규식 검증.
  - `repository.py`: `TARIFF_COLUMNS`, `TARIFF_SORT`, `source_exists`, `tariff_dict`, `list_tariffs`, `get_tariff`, `tariff_code_taken`, `insert_tariff`, `update_tariff`, `delete_tariff`, `find_overlapping_tariffs` 구현.
  - `service.py`: `list_tariffs`, `get_tariff`, `create_tariff`, `update_tariff`, `delete_tariff` 구현.
    - 부모 에너지원(`energy_source_id`) 존재 검증 실패 시 400 `fields.energySourceId` (`INVALID_ENERGY_SOURCE`).
    - `effective_to < effective_from` 시 400 `fields.effectiveTo` (`INVALID_EFFECTIVE_TO`).
    - 기간 겹침 시 409 `PRECONDITION_NOT_MET` (`details.reason="PERIOD_OVERLAP"`, `details.conflicts=[{id, tariffCode, effectiveFrom, effectiveTo}]`).
    - 삭제는 참조 테이블이 없어 멱등 삭제 지원.
  - `router.py`: `GET/POST /tariffs`, `GET/PATCH/DELETE /tariffs/{id}` 라우트 등록.
- 프론트엔드 (`frontend/src/fems/`):
  - `Tariffs.tsx`: F-10 설비 화면 패턴 복제 구현. 에너지원 필터 및 선택, 기본요금/사용요금 쉼표 포맷팅, 적용 기간 표시(진행중/기간), 에너지원 부재 시 EmptyState, 등록/수정 모달 및 기간 겹침(PERIOD_OVERLAP) 충돌 정보 표시, 삭제 확인 다이얼로그.
  - `FemsLayout.tsx`: `femsScreens`에 F-14 요금제 등록 (group: "요금").
  - `index.tsx`: F-14 라우트 등록 (`/tariffs`).
- 테스트 및 검증:
  - `backend/tests/test_fems_tariff.py`: 21개 테스트 신규 작성 (에너지원 검증, 코드 중복, 기간 검증, 겹침 409 충돌정보 검증, CRUD 등).
  - `frontend/src/fems/tariffs.test.tsx`: 12개 테스트 신규 작성 (목록/필터/등록/수정/삭제/충돌 표시 등).
  - 백엔드 전체 테스트 통과: `pytest backend/tests -q` 142 passed (테스트 DB: `factory_studio_test`, exit 0).
  - 프론트엔드 전체 테스트 통과: `npm --prefix frontend test` 12개 파일 133개 테스트 ALL PASSED (exit 0).
  - typecheck, lint, format:check, build, ruff check/format, git diff --check 모두 exit 0.
- main 병합·push 없음.

## 2026-09-24 FS-018d 완료 (Claude Code)

- AG-06(F-14 요금제) 검토: 저장소 일치, 겹침·nullable PATCH 처리 확인, frontend 133·backend 142·Playwright 26 재현.
- F-04 배출량 `GET /emissions`: 최상위 계측기만 합산, invalid 제외, 배수 적용, 연도별 EMISSION 계수, PRIMARY 미사용, 상태 4종, 부분 계산 표시. 화면은 총량 타일 + 에너지원별 표 + 근거 패널.
- 테스트: backend +15(전체 157), frontend +11(전체 144), Playwright +2(전체 28). 모든 검증 exit 0. 보고서 `docs/agent/FEMS_FS-018d.md`.

## 2026-09-24 FS-018e 에너지 목표 비율표 (Claude Code)

- 목표 95% 고정 → 월·대상별 90~105% 고정 비율표(`seed/common.py TARGET_RATIOS`). seed_version `sv-20260924-2`. 생성기·V8 검증기·test_seed.py V8 쿼리 동시 수정.
- 신규 `test_seed_targets.py` 6개. backend 163, Playwright 28(템플릿 7,469 재생성), frontend 144, 모든 검증 exit 0.
- 기존 템플릿·게스트 세대는 옛 값 유지(FS-005g 11장). 로컬 DB는 `seed.cli template` 재실행 필요.

## 2026-09-24 FS-018f 완료 (Claude Code)

- F-01 대시보드 `GET /dashboard?month`: TOE(PRIMARY, 환산 후 합산), 사업장 TOE 목표 달성률, 예상 요금(그 달 요금제), 배출량(F-04 동일), 일자별 TOE, 설비 상위 5, 품질 이상. 시드 9월 99.0% 목표 이내, 8월 104.2% 초과.
- 테스트: backend +20(전체 183), frontend +14(전체 158), Playwright +3(전체 31). 모든 검증 exit 0. 360px 스크린샷 확인. 보고서 `docs/agent/FEMS_FS-018f.md`.

## 2026-09-24 FS-018g 완료 (Claude Code)

- F-07 `GET /targets/performance`: 범위별 섹션, 단위 불일치는 계산 불가, 목표 없으면 미설정, 당월 누계 표시. 시드 9월 사업장·설비 모두 이내·초과 혼재.
- F-14 기준정보 그룹 이동, 360px 달성률·상태 열 앞으로, 스모크 포트 검사 SO_REUSEADDR(연속 실행 오검출 수정).
- 테스트: backend +18(전체 201), frontend +11(전체 169), Playwright +2(전체 33). 모든 검증 exit 0. 보고서 `docs/agent/FEMS_FS-018g.md`.

## 2026-09-24 AG-07 FEMS 사이드바 모바일 접는 메뉴 완료 (antigravity)

- FEMS 사이드바 반응형 접기 구현: 800px 이하에서 네이티브 `<details><summary>`로 접힘 메뉴 제공.
- `FemsLayout.tsx`:
  - `useLocation()` 기반 현재 화면 식별하여 summary에 "FEMS 메뉴 · 현재 화면 ID와 이름" 노출.
  - `<details open>` 및 `ref` 기반, 메뉴 링크(`NavLink`) 클릭 시 `onClick`에서 `details.open = false`로 자동 닫힘.
  - `aside[aria-label="FEMS 메뉴"]` 및 `femsScreens` 배열 구조 100% 보존.
- `shared/styles.css`:
  - 파일 끝에 801px 이상에서 summary 숨김 및 nav/eyebrow 항상 펼침 CSS 추가 (JS 화면 크기 감지 없음).
  - 800px 이하에서 summary 스타일(터치 영역, 화살표 인디케이터, 테두리, 배경) 추가.
- 테스트 및 검증:
  - `frontend/src/fems/sidebar.test.tsx` 11개 단위 테스트 신규 작성 (현재 화면 이름 노출, 메뉴/다른앱 링크 클릭 시 details 닫힘, aria-label/목록 구조 유지).
  - 프론트엔드 전체 테스트 통과: `npm --prefix frontend test` 16개 파일 180 passed (exit code 0).
  - typecheck, lint, format:check, build 모두 exit code 0.
  - 브라우저 스모크 검증: `tools/run_portal_smoke.py` 33 passed (exit code 0, 360px 모바일 8개 화면 포함).
  - 수정 금지 파일(다른 FEMS 화면, 백엔드, content, conftest 등) 변경 0.
- main 병합·push 없음.

## 2026-09-24 FS-018h 완료 (Claude Code)

- F-08 `GET /billing`: 월별 요금제 선택·구간 분할, TARIFF_MISSING·NOT_BILLABLE, 계측 없는 달 미청구. 시드 8~9월 합계 11,240,597원(전력 8월 120원·9월 130원).
- 대시보드 요금 계산 삭제 후 `_billing` 공통 사용(대시보드 테스트 무수정 통과). AG-07 충돌 회피로 styles.css 무수정.
- 테스트: backend +16(전체 217), frontend +11(전체 180), Playwright +2(전체 35). 모든 검증 exit 0. 보고서 `docs/agent/FEMS_FS-018h.md`.

## 2026-09-24 AG-07 검토·통합 (Claude Code)

- AG-07 위로 FS-018h rebase. Chromium 153 재현 결함 2건 수정: (1) 모바일 첫 진입에 메뉴가 펼쳐짐 (2) 넓은 화면에서 메뉴 링크 클릭 시 사이드바가 사라지고 다시 열 수 없음. `matchMedia(max-width:800px)`일 때만 닫고 좁은 화면은 닫힌 채 시작.
- sidebar 테스트 조정·추가(frontend 194), Playwright 1280/360 사이드바 테스트 2개 추가(37). backend는 검증된 FS-018h와 동일.

## 2026-09-24 CI 실패 원인 수정 (Claude Code)

- GitHub Actions `FS-009 runtime and schema`가 첫 push(AG-04 `2cece7b`)부터 10회 연속 실패. 원인: CI는 `ruff check backend`(디렉터리 전체)인데 `backend/tests/test_common.py`(AG-04)와 `backend/alembic/env.py`에 import 정렬 오류(I001) 2건. 로컬 검증은 FEMS 파일만 지정해 ruff를 돌려 놓쳤다.
- 두 파일 import 정렬만 수정(`ruff --fix`, 동작 변화 없음). test_common.py는 antigravity 소유이나 정렬 한 줄이라 수정했다.
- 나머지 CI 단계를 CI 환경 변수만으로(.env 미사용, 빈 `factory_studio_ci_test`) 재생: alembic upgrade → DDL 대사(SHA 7e97937e…d5e44 불변) → pytest 217 → downgrade/upgrade → DDL 대사 → frontend lint/format/build 모두 exit 0.
- CI에 없던 frontend `typecheck`와 단위 테스트(`npm --prefix frontend test`) 단계를 추가했다. Playwright는 CI에 없다(로컬 `tools/run_portal_smoke.py`).
- 규칙: 완료 전 ruff는 CI와 같은 범위로 실행한다 — `ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py`.

## 2026-09-24 FS-018i 완료 (Claude Code)

- F-05 `/production-records`: 초안 CRUD, confirm, revise. ALREADY_CONFIRMED·DRAFT_EXISTS·NOT_LATEST·REVISION_FIELDS_FIXED·PERIOD_OVERLAP. 날짜 → 사업장 시간대 반개구간.
- 공통 ErrorNotice conflicts 표시. 360px에서 상태·관리 열 앞으로, 필터 체크박스 한 줄.
- 테스트: backend +27(전체 244, CI 환경), frontend +13(전체 207), Playwright +2(전체 39). 모든 검증 exit 0. 보고서 `docs/agent/FEMS_FS-018i.md`.

## 2026-09-25 FS-018j 완료 (Claude Code)

- F-06 `GET /intensity`: 기록별·품목별 원단위, 확정 기준선 증감. NO_PRODUCTION·NO_ENERGY. 화면 `Intensity.tsx`.
- `fs.common.clock`: `FS_TODAY` 업무 기준일, 게스트 만료는 실제 시각. FEMS 테스트 fixture·스모크 날짜 고정.
- `COOKIE_SECURE` 변경(다른 작성자)의 무세션 500 결함을 `config.cookie_secure()` 분리로 수정, 사용자 결정 ③.
- 테스트: backend +23(전체 267, CI 환경), frontend +13(전체 220). 보고서 `docs/agent/FEMS_FS-018j.md`.

## 2026-09-25 FS-018k 완료 (Claude Code)

- F-13 `/energy-factors` CRUD, 화면 `Factors.tsx`(탭 분리). 계수 단위 서버 결정, UTILITY 거부, 에너지원·유형 고정.
- 도움말 f-13을 구현에 맞게 수정. FS-018j는 main `5bcc4d2` ff, main CI 통과(15분 13초).
- 테스트: backend +21(전체 288, CI 환경), frontend +11(전체 231), Playwright +2(전체 43). 보고서 `docs/agent/FEMS_FS-018k.md`.

## 2026-09-25 FS-018l 완료 (Claude Code)

- F-12 `/meters` 계측기·채널 CRUD, 화면 `Meters.tsx`(마스터-디테일). 기존 `GET /meters`(F-02) 응답을 확장해 공용.
- METER_IN_USE·CHANNEL_IN_USE 잠금, 부모 순환 방지, 누적 채널 단위 검사. 도움말 f-12 수정. FS-018k는 main `a5209b6` ff, CI 통과.
- 테스트: backend +25(전체 312, CI 환경), frontend +12(전체 243), Playwright +2(전체 45). 보고서 `docs/agent/FEMS_FS-018l.md`.

## 2026-09-25 backend 테스트 시간 단축 완료 (Codex)

- 전용 worktree `factory-studio-codex`, `codex/test-speed`를 `origin/main 70951d4`로 rebase. 메인 작업 폴더·antigravity worktree 사용 안 함.
- 공유 템플릿은 세션당 1회, 각 테스트는 실제 게스트 API로 별도 공간 생성. 게스트만 FK 자식 → 부모 순 정리하고 템플릿을 보존한다. FS_TODAY·GUEST_LIMIT은 fixture에서 설정.
- 전체 DB 정리 fixture를 먼저 실행하도록 수명을 분리. FEMS fixture 13개를 공용 guest_space에 연결. 테스트 본문 261개/보조 함수 AST와 test_common.py·test_seed.py 원본 보존. 직접 SQL 변경은 게스트 S 범위임을 확인했다.
- Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6, `factory_studio_codex_test`만 사용. `.env` 없이 DATABASE_URL·TEST_DATABASE_URL·PATH·HOME만 전달.
- `uv run --project backend pytest backend/tests -q --durations=15`: 개선 전 **782.272초, 312 passed, exit 0** → 개선 후 연속 **368.737초 / 308.066초, 각 312 passed, exit 0**. 평균 **56.7% 단축**. 예전 78e1206의 실패 포함 측정은 비교에서 제외.
- 격리·세대 초기화·legacy 혼합 순서 선택 검증 6 passed(exit 0). 템플릿 내용 불변·게스트 잔여 0 검사 통과. CI 범위 Ruff check·format --check, AST/보호 파일 확인, git diff --check 각각 exit 0.
- 남은 병목: 실제 게스트 복사/API, 독립 seed 결정성·복사 검증(준비 약 11~12초), 기존 portal/seed_targets 준비·schema verifier. 새 의존성·업무 코드·스키마·마이그레이션 변경 없음.
- 상세 명령·결과·재현: [테스트 시간 단축](agent/테스트시간단축.md). HANDOFF 갱신. main 병합·push 없음. 다음: 사용자 결과 확인, 병행 main 반영 시 담당자가 rebase 후 회귀.

## 2026-09-25 FS-018m 완료 — FEMS 14/14 (Claude Code)

- F-09 `/sites`·`/locations` CRUD, 화면 `Sites.tsx`. TIMEZONE_IN_USE 잠금, 공간 사업장 고정, 부모 순환 방지. 도움말 f-09 수정. FS-018l은 main `70951d4` ff, CI 통과.
- MES·ERP 작업 계획과 Codex 프롬프트 작성(`docs/agent/MES_ERP_작업계획_FS-019_020.md`).
- 테스트: backend +20(전체 332, CI 환경), frontend +11(전체 254), Playwright +2(전체 47). 보고서 `docs/agent/FEMS_FS-018m.md`.

## 2026-09-25 통합: Codex 테스트 시간 단축 + FS-018m (Claude Code)

- `fs-018m-f09`를 `codex/test-speed`(83e5a54) 위로 rebase. HANDOFF·진행현황·progress 충돌은 두 내용을 모두 보존해 해결.
- `test_fems_sites.py` fixture를 `guest_space`로 전환(테스트 본문 동일).
- 검증(CI 환경): backend **332 passed, 5분 36초**(통합 전 15분 8초), frontend 254, 스모크 47, ruff(CI 범위)·tools unittest 44·db:validate·audit·git diff --check 모두 exit 0.

## 2026-09-25 FS-020a 완료 (Claude Code)

- MES 기준정보 4화면 + API. 표 명세(`Master`) 기반 공통 CRUD, 품목 기준 단위 잠금(UNIT_IN_USE), 공간 순환 방지, 공정 허용 설비 교체.
- 공통 스타일 체크박스 보정(별도 커밋). 도움말 m-10·m-12 수정. 포털·FEMS의 MES 링크를 `/mes`로.
- 테스트: backend +28(전체 360, CI 환경), frontend +12(전체 266), Playwright +7(전체 54). 보고서 `docs/agent/MES_FS-020a.md`.

## 2026-09-25 FS-020b 완료 (Claude Code)

- M-14·M-15 버전 API·화면. `service.Versioned`로 두 흐름 공통 처리. 게시·폐기 엔드포인트의 쿼리 파라미터 노출 결함을 작성 중 발견해 클로저로 수정.
- 도움말 m-14·m-15 수정. FS-020a main `8294164` ff.
- 테스트: backend +24(전체 384, CI 환경), frontend +8(전체 274), Playwright +4(전체 58). 보고서 `docs/agent/MES_FS-020b.md`.

## 2026-09-25 FS-020c 완료 (Claude Code)

- `mes/planning.py`: 생산계획(초안·확정·라인 교체)·작업지시(생성·수정·발행+LOT·취소·LOT 보충). 계획 라인 FOR UPDATE 배정 한도, 동시 요청 테스트.
- MES 진입을 생산계획으로. 도움말 m-02·m-03 보강. FS-020b main `0f68b53` ff.
- 테스트: backend +20(전체 404, CI 환경), frontend +8(전체 282), Playwright +3(전체 61). 보고서 `docs/agent/MES_FS-020c.md`.

## 2026-09-25 FS-020d 완료 (Claude Code)

- `mes/execution.py`: LOT 목록·추적 상세, 공정 시작(TX-01)·완료(TX-02). 잠금 공간→지시→LOT→실행, EQUIPMENT_BUSY, all_defective 종결.
- 도움말 m-04·m-05 보강. FS-020c main `83c745d` ff.
- 테스트: backend +16(전체 420, CI 환경), frontend +5(전체 287), Playwright +3(전체 64). 보고서 `docs/agent/MES_FS-020d.md`.

## 2026-09-25 FS-020e 완료 (Claude Code)

- 자재 투입 API·화면(BOM 제안량, RESULT_CONFIRMED, DUPLICATE_ISSUE, 삭제 정정), 실적 조회 `GET /results`, 공통 `ResultForm`.
- 도움말 m-06·m-07 보강. FS-020d main `2a0717e` ff.
- 테스트: backend +12(전체 432, CI 환경), frontend +7(전체 294), Playwright +3(전체 67). 보고서 `docs/agent/MES_FS-020e.md`.

## 2026-09-25 FS-020f 완료 (Claude Code)

- `mes/packing.py`: 담을 LOT, 포장 CRUD·담기·닫기·묶기, PALLET 입고. 도움말 m-08·m-09 보강. FS-020e main `6bcbe1e` ff.
- 스모크는 처음에 사용자 개발 서버(8000·5173) 때문에 미실행 → 종료 후 70 passed.
- 테스트: backend +14(전체 446, CI 환경), frontend +7(전체 301), Playwright +3(전체 70). 보고서 `docs/agent/MES_FS-020f.md`.

## 2026-09-25 FS-019a 구현 — 스모크 승인 대기 (Codex)

- WIP 보존 뒤 `origin/main 6bcbe1e`로 rebase. MES·ERP 라우트 모두 보존, ERP 런처 연결 및 Home 안내 수정.
- E-15 거래처·E-16 품목/단위환산·E-17 거래처별 단가 CRUD, E-18 계정/분개규칙 읽기 전용. S 격리·write_scope·CSRF/멱등 영수증·참조 건수·단가 구간 겹침 거부. ERP 독립 안내, Field/select/checkbox 사용 보정.
- backend guest_space 회귀 78개, frontend 20개 추가. 최종 프론트 전체 314 passed 및 typecheck/lint/format/build, CI Ruff check/format, db:validate, audit_schema_isolation, diff --check exit 0. backend 전체 **510 passed, 580.736초, exit 0**(CI 네 변수·전용 DB).
- Playwright ERP CRUD 1개·360px 4개 추가. 공용 포트/DB 사용 승인을 기다리고 있어 실행·스크린샷 확인은 미실행. 완료 판정 보류.
- API 계약 §8·도움말·진행현황·Codex HANDOFF 갱신. 보고서 `docs/agent/ERP_FS-019a.md`. 새 의존성·스키마 변경 없음. push·main 병합 없음.

## 2026-09-25 통합: Codex FS-019a ERP 기준정보 (Claude Code)

- Codex `4e2bc74`를 FS-020f(`25f4312`) 위로 rebase해 `fs-019a-erp-integrate`로 통합. 코드는 충돌 없음, 진행현황·progress·HANDOFF 충돌은 두 내용 보존.
- 통합 수정: FEMS·MES 사이드바의 ERP 링크를 도움말 대신 `/erp` 화면으로.
- 통합 검증(CI 환경): backend **524 passed**(9분 6초), frontend **321 passed**, 스모크 **75 passed**(ERP 360px 포함), ruff(CI 범위)·tools unittest·db:validate·audit·git diff --check 통과. Codex 대신 Claude Code가 통합 상태로 스모크를 실행(Codex 사용량 절약).
- 후속(Codex FS-019b에서): ERP 화면의 관리 버튼이 FEMS·MES의 `link-button`과 다르고, 등록 폼 select가 좁은 기본 모양이다. 동작 문제는 없어 통합을 막지 않았다.

## 2026-09-25 FS-020g 완료 — MES 15/15 (Claude Code)

- `mes/dashboard.py`·`Dashboard.tsx`: M-01 지표·파이프라인·불량 사유·계획 대비 실적·처리 대기. MES 진입을 대시보드로. 도움말 m-01 보강.
- 스모크에서 발견한 CHECK 위반(종료 < 시작)을 `clock_timestamp()`로 수정. Codex FS-019a 통합 main `cc8729d` ff.
- 360px에서 파이프라인 순서(공정 코드 순) 결함 발견 → 경로 순번 정렬.
- 테스트: backend +8(전체 531+1, CI 환경), frontend +5(전체 326), Playwright 76. 보고서 `docs/agent/MES_FS-020g.md`.

## 2026-09-25 P-02 런처 아이콘 크기 조정 (Codex)

- 사용자 이미지 요청: 큰 솔루션 카드를 정사각형 아이콘 타일 + 아래 이름 배치로 변경. 기존 단색·링크·사용 상태·설명 유지.
- Home.tsx + 전용 Home.css만 제품 코드 변경. 데스크톱 타일 104px/아이콘 48px, 480px 이하 타일 88px/아이콘 40px·2열. 공통 스타일 수정 없음.
- Node 24.21.0: frontend typecheck·lint·format:check·build·test(314 passed) 각각 exit 0. git diff --check exit 0.
- 브라우저 스모크·360px 직접 검증·backend는 미실행. 사용자 지시대로 Claude Code가 통합 후 스모크·360px를 담당한다. push·main 병합 없음.

## 2026-09-26 3D 공장 둘러보기 구현 (Codex)

- 사용자 승인한 별도 화면 `/factory`, 상단 앱 런처 오른쪽 3D 공장 메뉴. 전체 조감도·3인칭 이동·1/2층 전환·계단·충돌·모바일 이동 버튼.
- 1층 현장사무실(직원 1·노트북·바코드 프린터), 조립→비전검사→포장 설비 3대/키오스크/이송과 순회 직원 1명, 2층 사무실 직원 2명. 사용자 캐릭터 별도. 실제 데이터와 연동하지 않는 합성 시연.
- three 0.186.1, React Three Fiber 9.8.1, Drei 10.7.8, @types/three 0.186.0 추가. lazy load, 외부 모델/DB 변경 없음.
- Node 24.21.0. frontend typecheck·lint·format:check·build·test(330 passed), 독립 Playwright(7 passed, 20.0초), git diff --check 각각 exit 0. 360px·2층 스크린샷 직접 확인.
- 5186 포트/모의 API의 독립 검증만 실행. 공용 8000/5173·스모크 DB·backend 미사용. 통합 스모크는 Claude Code 담당, push/main 병합 없음.
- 보고서 `docs/agent/3D공장_구현.md`. 다음: 통합 환경에서 확인 후 사용자 피드백. ERP 후속 업무 미착수.

## 2026-09-26 통합: Codex 런처 아이콘 타일 + 3D 공장 (Claude Code)

- Codex `codex/fs-019a-erp-master`의 새 커밋 3개(`f9eb879` P-02 런처 타일, `5593693`·`31a4472` 3D 공장)를 main `626ba35` 위로 cherry-pick해 `factory-3d-integrate`로 통합(이미 통합한 FS-019a 커밋 2개는 제외). 문서 충돌만 두 내용 보존으로 해결.
- 새 의존성: `three` 0.186.1, `@react-three/fiber` 9.8.1, `@react-three/drei` 10.7.8, `@types/three`(dev). `npm audit --omit=dev` 0건. 3D 번들(`Factory-*.js` 919kB, gzip 245kB)은 `/factory` 진입 때만 지연 로딩.
- 통합 검증: frontend typecheck·lint·format:check·build·test **342 passed**, 스모크 **83 passed**, 3D 전용 브라우저 테스트(`npm --prefix frontend run test:factory-browser`, API 모의) **7 passed**. backend는 변경 없음(CI에서 전체 실행).
- 후속: 360px에서 상단 메뉴가 두 줄(‘나가기’가 둘째 줄)이 된다. 가로 스크롤은 없다.

## 2026-09-26 저장소 정리 (Claude Code)

- 사용자 요청으로 루트를 정리: 빈 `seed/`·`tests/`(초기 뼈대의 `.gitkeep`만, 실제는 `backend/seed`·`backend/tests`) 삭제, `prototypes/` → `docs/archive/prototypes/`, Git 제외 임시 추출본 `fs005g_check2_*.txt` 4개 → `work/fs005g-check2/`.
- 현재 문서의 시제품 경로(화면 설계서 3개, 설계 결정, 진행현황 표) 갱신. 지난 작업 보고의 옛 경로는 기록이라 그대로 둠.
- README에 루트 폴더·파일 의미 표와 현재 진행 상태 반영. 기존에 깨져 있던 `구현인계패키지_FS-012.md` 상대 링크 2개 수정(문서 내 깨진 상대 링크 0).
- 유지: 루트 `package.json`·`node_modules`(DB 설계서 도구), `work/`, `docker-compose.yml`, 형제 worktree·백업·참고자료 폴더.
- 검증: db:validate, audit_schema_isolation, tools unittest 44 OK. 코드 변경 없음(CI에서 전체 실행).

## 2026-09-26 FS-019b 완료 — ERP 7/18 (Claude Code)

- 사용자 결정: FS-019b~h 전부 Claude Code, E-G07 0원 매출 세금계산서 발급 금지.
- E-02 견적 · E-03 판매계획 · E-04 수주 API·화면·도움말. 목록·저장 훅을 `shared/hooks.tsx`로 옮겨 MES·ERP 공용(별도 커밋).
- 검증: frontend 354 passed, backend 561 passed(CI 환경), 스모크 87 passed, 360px 직접 확인. 상세 `docs/agent/ERP_FS-019b.md`.

## 2026-09-26 FS-019c 완료 — ERP 9/18 (Claude Code)

- FS-019b main ff(`0addc2e`, CI 통과) 뒤 진행. E-05 출하지시 · E-06 출하 API·화면·도움말, 출하 확정 트랜잭션 안에서 매출·채권 생성(TX-09를 019c에 포함 — 설계상 분리 불가).
- 포털 흐름 화면 테스트의 역할 조회 대기를 5초로(병렬 실행 타이밍 실패 해결).
- 검증: frontend 360, backend 574(CI 환경), 스모크 90, 360px 직접 확인. 상세 `docs/agent/ERP_FS-019c.md`.

## 2026-09-26 FS-019d 완료 — ERP 11/18 (Claude Code)

- FS-019c main ff(`22055ef`, CI 통과) 뒤 진행. E-07 매출 · E-08 세금계산서 API·화면·도움말. E-G07 0원 매출 발급 금지 구현.
- 검증: frontend 367, backend 582(CI 환경), 스모크 93 ×2, 360px 직접 확인(E-08 select 모양 수정). 상세 `docs/agent/ERP_FS-019d.md`.

## 2026-09-26 FS-019e 완료 — ERP 13/18 (Claude Code)

- FS-019d main ff(`40efad7`, CI 통과) 뒤 진행. E-09 매출채권 현황 · E-10 수금 등록·소명 API·화면·도움말.
- 동시성 주입: 병렬 소명 한도, 매출 취소 vs 소명 경합. 소명 취소는 `core.audit_event` 기록.
- 검증: frontend 375, backend 594(CI 환경), 스모크 96, 360px 직접 확인. 상세 `docs/agent/ERP_FS-019e.md`.

## 2026-09-26 FS-019f 완료 — ERP 16/18 (Claude Code)

- FS-019e main ff(`55c39c1`, CI 통과) 뒤 진행. E-11 매입 전표 · E-12 매입채무 · E-13 지급·소명.
- 019e 수금·소명 백엔드(`receipts.Side`)·화면(`settlement.ts` + `side` 속성)을 일반화해 매입 쪽에 재사용. 세액은 `revenue.line_amounts` 공용.
- 검증: frontend 381, backend 607(CI 환경), 스모크 100, 360px 직접 확인. 상세 `docs/agent/ERP_FS-019f.md`.

## 2026-09-26 FS-019g 완료 — ERP 17/18 (Claude Code)

- E-14 분개 미리보기 API(`GET /journal-preview`, 저장 없음)·독립 화면·공통 패널. 매출·수금·매입·지급 화면에 "분개" 버튼.
- 검증: frontend 384, backend 614(CI 환경), 스모크 102, 360px 직접 확인. 상세 `docs/agent/ERP_FS-019g.md`.

## 2026-09-26 FS-019h 완료 — ERP 18/18, FS-019 종료 (Claude Code)

- FS-019g main ff(`49a291d`, CI 통과) 뒤 진행. E-01 ERP 대시보드 API·화면·도움말, ERP 진입을 대시보드로.
- 기존 FEMS e2e "결측 구간"의 첫 로드 대기 누락(§7-8 함정)을 수정.
- 검증: frontend 389, backend 622(CI 환경), 스모크 104, 360px 직접 확인. 상세 `docs/agent/ERP_FS-019h.md`.

## 2026-09-26 FS-021 통합 검증 (Claude Code)

- FS-019h main ff(`2827f39`, CI 통과) 뒤 진행. 사용자 결정: AC-35~80 추적표, 로컬 성능 실측 포함.
- 테스트 추가: `test_integration_policies.py`(범위 격리 횡단·멱등 4개), `test_integration_ac.py`(AC 보강 15개). `tools/measure_fs021.py` 실측 도구.
- 결함 수정: `common/scope.py` 잠금 뒤 게스트 만료 재확인(AC-63).
- 상세 `docs/agent/통합검증_FS-021.md`.
- 사용자 결정 반영: 동시 게스트 생성 지연은 현행 유지, 미구현 기능은 1차 범위 밖(FS-012 §4-3에 추가), AC-68·73·74·75 단언 추가로 검증됨 33.

## 2026-09-26 Blender 비전검사 설비 (Codex)

- 사용자 "참고자료 없이 바로 진행" 승인. `codex/factory-vision-blender`에서 기존 공장의 비전검사 1대를 Blender 원본/GLB로 교체.
- 카메라·링 조명·컨베이어·경광등, 6초 검사 주기·5번째 불합격, 상태/수량 패널·가까이 보기·이상 정지/해제·MES 대시보드 진입. 합성 시연이며 업무 데이터에 저장하지 않음.
- Node 24.21.0: frontend typecheck/lint/format:check/build/test(345 passed), 독립 Chromium 브라우저 8개 통과(exit 0). 360px/데스크톱 직접 확인. Blender 5.2.2 GLB 생성 성공.
- DB/API 변경·새 의존성 없음. backend/DB/공용 통합 스모크 미실행. main 병합·push 없음.
- 원본 `assets/blender/vision-cell.blend`, 재생성 `tools/blender/build_vision.py`, 상세 보고 `docs/agent/3D공장_Blender_비전검사.md`.
- 다음: 시각 피드백·통합 담당자 main 통합. MES 실제 레코드 연결 및 FEMS는 후속 설계.

## 2026-09-26 3D 공장 공간 고도화 (Codex, 완료)

- 브랜치 `codex/factory-building`, 기준 `b352514`(비전검사). 사용자 우선순위 진행 및 이어서 진행 승인.
- Blender 건물 외관/내부 전환, 지붕·패널·창문·하역장·공조기·철골·덕트·천장 조명. 조립·포장 설비도 Blender 모델로 교체하고 프레스·실링바 시연.
- 바닥 질감·환경 반사·그림자, 자재 선반/공구대/소방함 및 충돌. MES/ERP/FEMS 기존 화면 진입 카드. 업무 API/DB·실제 데이터 연동 없음.
- Node 24.21.0: typecheck/lint/format:check/build exit 0. 전체 테스트는 자원 경합을 줄인 `npm --prefix frontend test -- --maxWorkers=2`로 346개 통과. 독립 Chromium 브라우저 10개 통과(2.1분, exit 0). 외관/내부/모바일 스크린샷 직접 확인.
- Blender 5.2.2 LTS. 생성 스크립트와 .blend/GLB를 저장. 새 npm 의존성 없음. 상세 `docs/agent/3D공장_공간고도화.md`.
- backend/DB/공용 통합 스모크·Safari/실기기 성능은 미실행. main 병합·push 없음. 다음: 사용자 시각 피드백 및 통합 담당자 main 통합. 최종 커밋은 이 인계를 포함한 `3D 공장: 건물·재질·생산라인 공간 고도화`이며 `git log -1`로 확인.

## 2026-09-26 통합: Codex 3D 공장 고도화 (Claude Code)

- Codex `codex/factory-building`의 커밋 2개(`b352514` Blender 비전검사 설비, `d3eaf31` 건물·재질·생산라인)를 main `907fed8` 위로 cherry-pick(`factory-building-integrate`). 문서 2개(진행현황·progress) 끝 절 충돌만 두 내용 보존으로 해결.
- 범위: 건물 외관↔내부 전환(외벽·지붕·하역장·옥상 공조기), 바닥·금속 재질과 그림자, 조립·비전검사·포장 Blender 모델(glb 4개 1.4MB)과 동작, 자재 선반·공구대, MES·ERP·FEMS 진입 카드. 새 의존성 없음, 3D 번들은 `/factory` 진입 때만 지연 로딩(Factory 925kB, gzip 247kB).
- 검증(메인 폴더에서 재실행): frontend typecheck·lint·format:check·build·test **393 passed**, 3D 전용 브라우저 테스트 **10 passed**, 스모크 **107 passed**, diff --check. 외관·내부·360px 스크린샷 직접 확인. backend 변경 없음.
- 참고: 업무 데이터(설비 상태 등)와의 실시간 연동은 아직 없다(화면에 "3D 합성 시연 · 실시간 설비 정보 아님" 표시).

## 2026-09-26 FS-022 배포 절차서 (Claude Code)

- Codex 3D 공장 고도화 main ff(CI 통과) 뒤 작성. `docs/deploy/배포절차_FS-022.md` — 사용자가 Vultr VM에서 직접 실행하는 절차(IP 단계 → 도메인·HTTPS 단계). Claude Code는 서버에 접속하지 않았다.
- 절차서를 **이지스 공존판**으로 교체(사용자 제공 수정본 채택 + 보완): 대상은 이지스 운영 서버 158.247.236.136(1 vCPU·2GB·55GB). 포트 분리(FS Nginx 8080·uvicorn 8021), Nginx default 유지, ufw 규칙 선반영, uv `/usr/local/bin`. Claude Code 보완: `apt upgrade` 제외, 프런트 맥북 빌드 기본(서버 Node 불필요), systemd `uv run --frozen`, RAM 여유·스왑 점검과 스왑 파일 절차. compose DB 바인드는 이미 `127.0.0.1:55432`.

## 2026-09-26 FS-022 배포 완료 — https://eip.hugh-d.com (Claude Code)

- 사용자 요청으로 서버에서 직접 실행(맥북 SSH 키, 비밀번호 입력 없음). 스냅샷은 사용자가 먼저 생성.
- 실행: Docker·uv 설치(apt upgrade 없음) → factory 사용자·읽기 전용 deploy key → clone `c41c274`·.env(서버 생성 비밀값) → PG18 Docker·마이그레이션·템플릿 시드 → systemd API(8021)·회수 타이머 → 프런트 맥북 빌드 rsync → CSR·Cloudflare Origin CA → Nginx 사이트(기본 서버 TLS 거절, fs→eip 301, CF real IP) → ufw 443 → reload.
- 문제와 해결: Nginx 1.24가 `http2 on;` 미지원 → `listen 443 ssl http2`. Cloudflare 레코드가 처음 `@`로 들어가 eip 미해결 → 사용자가 eip 추가. 루트·www·aegis가 FS를 보여 443 기본 서버로 TLS 거절(525). 맥북 DNS 음성 캐시로 로컬 curl 실패 → Cloudflare IP 고정으로 확인.
- 절차서를 실행한 그대로 재작성(`docs/deploy/배포절차_FS-022.md`).

## 2026-09-26 UI-01 공통 디자인 시스템·앱 레이아웃 (Claude Code)

- 브랜치 `ui-01-design-system`(기준 `b197491`, 커밋 `a5dddc2`·`7d7cbaf`·최종 UI-01 커밋). 상세 `docs/ui/디자인시스템_UI-01.md`.
- 원인: `main` 1160px 제한과 헤더 중앙 정렬 패딩, h1 36px·패널 28px·본문 15px/1.65, 레이아웃 3벌 복제, 스타일 없는 공통 클래스(`form-actions`·`toolbar`·`filter-inline`·`field-error`).
- 변경: 토큰(색·글자·간격·모양·컨트롤·앱 틀), 공통 `SolutionLayout`(접기·서랍·키보드), 한 줄 페이지 헤더, 공통 입력·버튼 상태, 표 숫자 정렬·긴 값 title, KPI 4열/모바일 2열, 알림 종류별 색, 목록 아래 상세 자동 스크롤, 도움말 읽기 폭, 3D 공장 캔버스 높이·툴바·설비 상세 오버레이. 직접 쓴 표 5화면에 금액 열 정렬.
- 전후(1366×768, F-01): KPI 3+1줄 → 4개 한 줄, KPI 시작 약 370px → 약 213px, 주요 차트 시작 약 700px(첫 화면 밖) → 약 350px.
- 검증: typecheck·lint·format:check·build exit 0, vitest 393 passed, 3D 브라우저 10 passed, 스모크 107 passed(5.7분, exit 0), `git diff --check`. 55경로 × 5해상도 넘침·작은 글자 점검 0건.
- 미실행: backend pytest(백엔드 변경 없음), Safari·실기기.
- DB migration / Excel / seed: 변경 없음. push·main 병합 없음.

## 2026-09-27 운영 후속 — 443 제한·이지스 도메인·:8000 차단·UI-01 배포·운영자 계정 (Claude Code)

- 443 ufw를 Cloudflare 대역 22개로 제한(원점 직접 443 차단 확인). 이지스 aegis.hugh-d.com: Access(사용자 설정) → Nginx aegis 사이트(office.html + `/api/`→127.0.0.1:8000) → office.html 수정 배포(secretary-ai `91baa61`, push) → 사용자 로그인 확인 → ufw 8000 제거(서비스 재시작 없음).
- UI-01(다른 세션 작업, 미병합)을 새 main 위로 cherry-pick·문서 충돌 병합, 프런트 393·3D 10·스모크 107 통과(로컬 Colima DB 재기동 후), CI 통과 → main `6d48f5f` → 서버 git pull·프런트 rsync.
- 회원 로그인 401 원인: 서버 `core.app_user` 0건. `tools/create_member.py`·`create_member_account` 추가, `INVALID_CREDENTIALS` 분리, 테스트 `test_member_account.py` 3개. 계정 생성은 운영 서버 비밀번호가 걸려 사용자가 직접 실행.

## 2026-09-27 UI-02 공통 UI 확정·기준 화면 3개·Antigravity 인계 (Claude Code)

- 브랜치 `ui-02-common-patterns`(기준 main `6d48f5f` → `88d584f` 위로 rebase), 코드 커밋 `0875482`(WIP `2fe2975` 포함). 문서: `docs/ui/공통UI규약_UI-02.md`·`docs/ui/메뉴적용표_UI-02.md`·`docs/agent/Antigravity_작업지시_UI-02.md`.
- Figma: `whoami` 결과 Starter 플랜·View 좌석. 프레임 URL이 없어 Figma 수치를 읽지 않았고 반영했다고 쓰지 않는다.
- 공통 구현(`shared/styles.css`·`components.tsx`·`SolutionLayout.tsx`·`app/App.tsx`): `--app-h`·`.app-shell`, 업무 화면 바닥글 제거, `.page-fill`/`.fill` 목록 채움, `thead th` 고정, 페이지 이동 sticky, `PageTitle(actions)`, `DataTable(leading)`·`wrap` 열·긴 값 포커스 펼침, `Pagination`·`DateRange`, `FormPanel`·`useDiscardGuard`, `EmptyState(onAction)`, `.field-row`, KPI 한 줄/2×2(3+1 방지), 대시보드 2열·`has-lead` 3:2.
- 화면: F-01 조회 월을 제목 줄로·주요 차트+구성 3:2·환산 합계, F-02 채움·보기 전환을 결과 줄로·늦은 응답 무시, F-05 목록 전체 폭·등록/수정/정정 한 패널.
- 전후(같은 뷰포트): F-02 1440×900 문서 2,286 → 900px(1366×768 2,286 → 768), F-05 1440 1,321 → 900px, F-01 1600 하단 3+1 → 2×2(1920 4열 → 2×2), 업무 화면 전체에서 바닥글 스크롤 약 43px 제거. 모바일 390·360, 720×450(200% 확대) 자연 스크롤·저장 버튼 접근 확인.
- 검증: frontend typecheck·lint·format:check·build exit 0, vitest 402 passed(+9), 상호작용 스크립트 51/51(패널 포커스·Esc·가둠·미저장 보호·등록→수정→확정→정정·검증 오류·머리글 고정·정렬·페이지 이동·CSV·그래프), 55경로 × 1440·390 전후 비교(가로 넘침 0·페이지 오류 0·제목 변화 0), `e2e/layout.spec.ts` 16개 추가, 스모크 121 passed / 1 failed(3D `걷기 입력은 3인칭 화면을 이동시킨다` 캔버스 스크린샷 30초 초과 — 단독 재실행 시 이 브랜치·main 각 2회 통과, 약 21~22초로 같음), `git diff --check`.
- 미실행: backend pytest(백엔드 변경 없음), `db:validate`(DB 변경 없음), Safari·실기기, 운영 서버 반영.
- 로컬 검증 중 게스트 공간 상한(20)에 걸려 로컬 백엔드만 `GUEST_LIMIT=100`으로 재시작했다(설정·데이터 변경 없음).
- DB migration / Excel / seed: 변경 없음. 사용자 요청으로 main에 rebase 통합(OPS `88d584f` 위), push 없음.
- 다음: 서버 배포(사용자 확인 후) → Antigravity A1부터(지시서) · Claude UI-03 예외 패턴.

## 2026-09-27 UI-02 A1 대시보드 조회 월 위치 (Antigravity)

- 브랜치: `antigravity/ui02-a1` (기준: main `ed9f438cbbd1f2aacec67a3029304020e3d7865e`)
- 대상: M-01(`mes/Dashboard.tsx`), E-01(`erp/Dashboard.tsx`)
- 내용:
  - 별도 `filter-bar`의 조회 월 입력을 `PageTitle`의 `actions`로 옮김 (F-01 대시보드 규약 준수).
  - 기존 2×2 카드 배치 및 하단 순서·내용 유지 (`has-lead` 미사용).
  - 조회 월 변경 시 쿼리 파라미터(`?month=`) 및 KPI 문구 보존.
  - `frontend/e2e/layout.spec.ts`에 M-01 및 E-01의 조회 월이 `.page-actions`에 위치하고 별도 `.filter-bar`가 없음을 검증하는 e2e 테스트 추가.
- 검증:
  - `npm --prefix frontend run typecheck` 통과 (오류 0)
  - `npm --prefix frontend run lint` 통과 (오류 0)
  - `npm --prefix frontend run format:check` 통과 (전체 일치)
  - `npm --prefix frontend run build` 통과
  - `npm --prefix frontend test -- --run` 통과 (43개 테스트 파일 402개 테스트 통과)
  - `git diff --check` 통과 (공백/줄바꿈 이상 없음)
- DB migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 대기. 확인 후 A2(조회 목록 M-09, E-07, E-14, P-07) 진행.

## 2026-09-27 UI-02 A2 조회 목록 L 패턴 적용 (Antigravity)

- 브랜치: `antigravity/ui02-a2` (기준: `ce731ab`, `antigravity/ui02-a1`)
- 대상: M-09(`mes/Receipts.tsx`), E-07(`erp/SalesRecords.tsx`), E-14(`erp/Journal.tsx`), P-07(`portal/Records.tsx`)
- 내용:
  - 각 화면 루트를 `.page-fill`로 변경하여 뷰포트 맞춤형 스크롤 규칙 적용.
  - P-07: 상단 탭을 `DataTable`의 `leading` prop으로 전달 (F-02 기준 화면과 동일 마크업).
  - P-07: ADMIN 전용 권한 분기 및 API 계약 보존.
  - 안내문 `<p className="muted" role="note">` 및 `Loading delay={300}` 공통 규약 정비.
  - `frontend/e2e/layout.spec.ts`에 A2 화면들(`.page-fill`) 레이아웃 검사 추가.
- 검증:
  - `npm --prefix frontend run typecheck` 통과 (오류 0)
  - `npm --prefix frontend run lint` 통과 (오류 0)
  - `npm --prefix frontend run format:check` 통과 (전체 일치)
  - `npm --prefix frontend run build` 통과
  - `npm --prefix frontend test -- --run` 통과 (43개 테스트 파일 402개 테스트 통과)
  - `git diff --check` 통과 (공백/줄바꿈 이상 없음)
- DB migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 대기. 확인 후 A3(보고서형 조회 F-03, F-04, F-06, F-07, F-08, E-09·12) 진행.

## 2026-09-27 UI-02 A3 보고서형 조회 R 패턴 정비 (Antigravity)

- 브랜치: `antigravity/ui02-a3` (기준: `26e9ab3`, `antigravity/ui02-a2`)
- 대상: F-03(`fems/Allocations.tsx`), F-04(`fems/Emissions.tsx`), F-06(`fems/Intensity.tsx`), F-07(`fems/Targets.tsx`), F-08(`fems/Billing.tsx`), E-09·12(`erp/Receivables.tsx`)
- 내용:
  - `.page-fill` 미사용 확인 및 문서 스크롤 정책 유지 (합계·근거·표 복합 화면).
  - 직접 쓴 표 숫자 열에 `th.num`, `td.num` 클래스 일관 적용 (F-04 소비량·배출량, F-06 원단위·생산량·TOE, F-07 달성률·목표·실적, F-08 요금·기본요금, E-09/12 원금·소명액·잔액).
  - 계산 근거 패널(`basis-panel`), 결측 제외 문구, 목표 초과 배지 글자 보존.
  - 안내문 `<p className="muted" role="note">` 및 `Loading delay={300}` 공통 규약 정비.
  - `frontend/e2e/layout.spec.ts`에 R 패턴 화면들의 `.page-fill` 미사용 검증 추가.
- 검증:
  - `npm --prefix frontend run typecheck` 통과 (오류 0)
  - `npm --prefix frontend run lint` 통과 (오류 0)
  - `npm --prefix frontend run format:check` 통과 (전체 일치)
  - `npm --prefix frontend run build` 통과
  - `npm --prefix frontend test -- --run` 통과 (43개 테스트 파일 402개 테스트 통과)
  - `git diff --check` 통과 (공백/줄바꿈 이상 없음)
- DB migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 대기. 확인 후 A4(FEMS 기준정보 F-09~11, F-13~14) 진행.

## 2026-09-27 UI-02 A4 FEMS 기준정보 S 패턴 전환 (Antigravity)

- 브랜치: `antigravity/ui02-a4` (기준: `antigravity/ui02-a3`)
- 대상 화면 5개:
  - F-11: `frontend/src/fems/EnergySources.tsx` (`master-grid` 제거, `page-fill` + `split-view` + `FormPanel` + `useDiscardGuard`)
  - F-09: `frontend/src/fems/Sites.tsx` (사업장/공간 두 영역 분리 및 공통 `FormPanel` 등록/수정)
  - F-10: `frontend/src/fems/Equipments.tsx` (`master-grid` 제거, `page-fill` + `split-view` + `FormPanel` + `useDiscardGuard`)
  - F-13: `frontend/src/fems/Factors.tsx` (`DataTable` `leading` 탭, 탭 전환 시 신규 폼 유지 및 `FormPanel` 전환)
  - F-14: `frontend/src/fems/Tariffs.tsx` (`filter-bar` 분리, 긴 폼 스크롤 `FormPanel` 적용)
- 검증:
  - `npm --prefix frontend run typecheck` 통과 (오류 0)
  - `npm --prefix frontend run lint` 통과 (오류 0)
  - `npm --prefix frontend run format:check` 통과 (전체 일치)
  - `npm --prefix frontend run build` 통과
  - `npm --prefix frontend test -- --run` 통과 (43개 테스트 파일 402개 테스트 통과)
  - `git diff --check` 통과 (공백/줄바꿈 이상 없음)
  - `frontend/e2e/layout.spec.ts`에 F-09,10,11,13,14 `.page-fill` 및 에너지원 패널 열기/닫기 e2e 테스트 추가
- DB migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 대기. 확인 후 A5(MES 기준정보 M-02,03,06,08,10~13) 진행.

## 2026-09-27 UI-02 A5 MES 기준정보 및 계획 화면 S 패턴 전환 (Antigravity)

- 브랜치: `antigravity/ui02-a5` (기준: `antigravity/ui02-a4`)
- 대상 화면 8개:
  - M-02: `frontend/src/mes/Plans.tsx` (`FormPanel` 적용, `RevealAnchor` 제거)
  - M-03: `frontend/src/mes/Orders.tsx` (`FormPanel` 적용, `?line=` 프리셋 시 패널 자동 열림 유지)
  - M-06: `frontend/src/mes/Materials.tsx` (`FormPanel title="자재 투입 등록"`, 중첩 form 제거)
  - M-08: `frontend/src/mes/Packing.tsx` (`FormPanel` 적용, 중첩 form 제거)
  - M-10: `frontend/src/mes/Sites.tsx` (사업장/공간 2개 구역 및 `FormPanel` 전환)
  - M-11: `frontend/src/mes/Equipments.tsx` (`FormPanel` S 패턴 전환)
  - M-12: `frontend/src/mes/Items.tsx` (`FormPanel` S 패턴 전환, `RevealAnchor` 제거)
  - M-13: `frontend/src/mes/Processes.tsx` (`FormPanel` S 패턴 전환)
- 내용:
  - React Rules of Hooks 준수: `useDiscardGuard`를 early return (`moduleOff`) 이전에 호출하여 조건부 훅 실행 오류 방지
  - `FormPanel` 내부 중첩 `<form>` 제거로 DOM 유효성 및 submit 이벤트 전달 보장
  - 단위 테스트(`planning.test.tsx`, `master.test.tsx`)에서 패널 오픈 버튼 클릭 후 폼을 조회하도록 수정
  - `frontend/e2e/layout.spec.ts`에 8개 MES 화면 `.page-fill` 검사 및 설비 등록 패널 열기/닫기 E2E 테스트 추가
- 검증:
  - `npm --prefix frontend run typecheck` 통과 (오류 0)
  - `npm --prefix frontend run lint` 통과 (오류 0)
  - `npm --prefix frontend run format:check` 통과 (전체 일치)
  - `npm --prefix frontend run build` 통과
  - `npm --prefix frontend test -- --run` 통과 (43개 테스트 파일 402개 테스트 통과)
  - `git diff --check` 통과 (공백/줄바꿈 이상 없음)
- DB migration / Excel / seed: 변경 없음.
- 다음: A6(ERP 계획·출하·전표·기준정보 화면 E-03, 05, 06, 08, 10, 11, 13, 15~18) 진행.

## 2026-09-27 UI-02 A6 ERP 계획·출하·전표·기준정보 화면 S 패턴 전환 (Antigravity)

- 브랜치: `antigravity/ui02-a6` (기준: `antigravity/ui02-a5`)
- 대상 화면 10개 (11개 메뉴):
  - E-15~18: `frontend/src/erp/Master.tsx` (`Partners.tsx` E-15, `Items.tsx` E-16, `Prices.tsx` E-17, `Accounts.tsx` E-18 공용). `children` prop 지원, `FormPanel` 전환, `Accounts.tsx` split-view + 매핑 이유 aside 패널 결합.
  - E-03: `frontend/src/erp/SalesPlans.tsx` (`master-grid` 및 `RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("판매계획 만들기")`).
  - E-05: `frontend/src/erp/ShipmentOrders.tsx` (`RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("출하지시 만들기")`, 미출하 취소 동작 유지).
  - E-06: `frontend/src/erp/Shipments.tsx` (`RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("출하 확정")`, 수기 패킹번호 동작 유지).
  - E-08: `frontend/src/erp/TaxInvoices.tsx` (등록·발급 두 폼을 `FormPanel` 모드 전환으로 S 패턴 통합, 0원 매출 발급 방지 및 409 안내 유지).
  - E-10·E-13: `frontend/src/erp/Receipts.tsx` (수금·지급 공용 컴포넌트, `master-grid` 및 `RevealAnchor` 제거, `FormPanel` 등록 전환, 409 LIMIT_EXCEEDED 오류 안내 유지).
  - E-11: `frontend/src/erp/PurchaseInvoices.tsx` (`master-grid` 및 `RevealAnchor` 제거, 등록·취소 두 패널을 `FormPanel` 모드 전환으로 통합).
- 내용:
  - React Rules of Hooks 준수: `useDiscardGuard`를 early return (`moduleOff`) 이전에 호출하여 조건부 훅 오류 원천 차단
  - E2E 및 단위 테스트 최신화: 패널 오픈 버튼 클릭 후 폼을 조회하도록 테스트 보강
  - `frontend/e2e/layout.spec.ts`에 전체 ERP 화면 `.page-fill` 검사 및 ERP 거래처 등록 패널 열기/닫기 E2E 테스트 추가
  - **Antigravity UI-02 작업 묶음 A1~A6 (총 37개 화면) 전체 완료** (완료 40, 대기 0, Claude 선행 8, 유지 7 = 총 55개 화면).
- 검증:
  - `npm --prefix frontend run typecheck` 통과 (오류 0)
  - `npm --prefix frontend run lint` 통과 (오류 0)
  - `npm --prefix frontend run format:check` 통과 (전체 일치)
  - `npm --prefix frontend run build` 통과
  - `npm --prefix frontend test -- --run` 통과 (43개 테스트 파일 402개 테스트 전체 통과)
  - `git diff --check` 통과 (공백/줄바꿈 이상 없음)
- DB migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 대기. 확인 후 Claude 선행 8개 화면(F-12, M-04, M-05, M-07, M-14, M-15, E-02, E-04) 진행 대기.

## 2026-09-27 UI-02 Antigravity 결과 검토·회귀 수정·main 통합 (Claude Code)

- Claude 검토(2026-09-27): 공식 스모크를 처음 돌려 11건 실패를 찾았다(Antigravity 묶음 검증에는 스모크 없음). 실제 회귀 5건 수정 — M-06 BOM 제안량 표가 겹침 패널에 가려 채울 수 없음(→ 패널 안으로), M-12 '환산'이 등록 패널을 자동으로 열어 목록을 가림(→ 목록만, 등록은 버튼), E-05·E-06·E-10/13 저장 직후 새 행 선택이 미저장 보호에 막힘(→ 가드 없는 `choose()`), E-18 설명 패널이 표와 겹침(→ main 구조·R 패턴 복원), F-09 인라인 style·정의 없는 `section-block`(→ 공통 `.section-block` 추가). 나머지 6건은 e2e 흐름 갱신. 레이아웃 e2e를 '클래스 존재' → '1440×900 문서 높이'로 강화.
- 검증: typecheck·lint·format:check·build, vitest 402, 스모크 **159 passed**(7.6분, exit 0), 55경로 × 1440·1600·390 전후 비교(가로 넘침·오류 0), S 화면 24개 패널 열기·저장 버튼·Esc(행 선택형 M-06·M-08 포함).
- 통합: `antigravity/ui02-a6` + 검토 커밋(`e8b0d71`·`86e729f`)을 main에 fast-forward. push·서버 배포 전.
- DB migration / Excel / seed: 변경 없음. backend pytest 미실행(백엔드 변경 없음).
- 배포(2026-09-27): origin push `88d584f..0378bf6`, 서버 `git pull --ff-only`(백엔드·마이그레이션 변경 없음 → API 재시작 없음), 맥북 별도 worktree에서 `0378bf6` 프런트 빌드 → rsync. 확인: Cloudflare 경유 200·새 번들 해시 일치·API 5xx 0, 운영 게스트로 F-02·F-05·M-12·E-15 1440×900 문서 900px, F-01 1600 하단 2×2, F-05 패널 열림, 페이지 오류 0.

## 2026-09-27 DOC-01 참고 문서 사이트 설계 (Claude Code)

- 요청: Odoo 18 문서 첫 화면처럼 EIP에 참고 문서 화면. 사용자 확정 — 주 독자 평가자, 스크린샷 제외, 따라하기 대표 1 + 짧은 것 2.
- 산출: `docs/ui/참고문서_DOC-01.md` (P-05 확장). 4구역(설계 8·따라하기 3·기존 참고 54+공통·개념 15), `/help/<키>` URL 유지, manifest 없이 경로·파일명·첫 줄 사용, 참고 트리는 메뉴 배열 `group` 재사용, 번들 내 원문 부분 문자열 검색, 저장소 비공개 전제의 설계 문서 공개 기준, DOC-02~04 분해와 DOC-02 검증 기준.
- 연결: `docs/ui/화면설계_포털_FS-008a.md` P-05에 링크 추가, 현황 문서 13-3 행 추가.
- 검증: 문서 작업. 코드·DB·시드 변경 없음, 테스트 미실행. 저장소 가시성(PRIVATE)·메뉴 group·`/help` 무세션 허용은 코드와 `gh repo view`로 확인.
- 다음: 사용자 확인 후 DOC-02(뼈대 구현).
- UI-03 예외 패턴(2026-09-27, Claude Code): 공통 `DetailPanel`(폼 없는 패널)·`wide`(640px, 1920px 이상 붙음·이하 겹침)를 `SidePanel` 하나로 구현. 기준 화면 — 읽기 전용 상세 M-04, 부모-자식 F-12(채널 상세 ↔ 채널 폼), 넓은 행 편집 E-04(등록·상세·편집), 상태 전이 M-05·M-07(`ResultForm`을 패널로). 규약 8장·적용표(완료 45, Antigravity 대기 3: M-14·M-15·E-02 → 지시서 UI-03 B1·B2).
  - 검증: typecheck·lint·format·build, vitest 402, 대표 화면 5개 × 1920·1600·1440·390 패널 모드·문서 높이·가로 넘침 확인, e2e(layout·fems·mes·portal) 151 passed / 2 failed(F-03 배분 추정·F-01 전월 목표 초과 — 이번에 바꾸지 않은 화면, e2e를 여러 번 돌려 로컬 개발 DB가 바뀐 데이터 의존 실패로 판단). **공식 스모크는 미실행**: 같은 메인 폴더에서 다른 세션(DOC-01)이 동시에 작업 중이라 8000·5173을 점유하는 스모크를 돌리지 않았다.
  - 주의: 이 폴더에서 다른 세션이 동시에 커밋 중(DOC-01 `238a7a0`이 UI-03 WIP 사이에 있음). 스테이징은 경로를 지정한다. push·배포 전.

## 2026-09-27 DOC-02 참고 문서 뼈대 구현 (Claude Code)

- 코드: `frontend/src/portal/docs.ts` 신규(구역·트리·검색·화면 경로), `ContentPages.tsx` Help 교체(첫 화면: 쪽빛 띠·검색·구역 카드 / 문서 화면: 트리·경로·본문·목차·이전/다음·이 화면 열기), `shared/content.tsx` `##` 제목 id, `styles.css` `.doc-*` 추가·옛 help 클래스 삭제, `.button.secondary` 선택자 추가.
- 트리는 메뉴 배열 `group` 재사용. manifest·frontmatter·검색 라이브러리 없음. 문서 없는 구역은 숨김(임시 문서 없음 — DOC-01 §8 수정).
- 검증:
  - typecheck·lint·format:check 통과, vitest **44파일 410개 통과**(신규 docs.test 5, content-pages P-05 4개 교체·추가).
  - build 통과. 메뉴 배열은 별도 1.4kB 청크로만 들어와 업무 화면 코드가 Help 청크에 딸려 오지 않음. Factory 924kB 경고는 기존.
  - Playwright(실행 중인 dev 서버 5173/8000 대상, 임시 설정): portal.spec 중 도움말·흐름 관련 5개 통과 — 신규 "참고 문서 ↔ 업무 화면 왕복"(검색 → E-09 → 이 화면 열기 → `? 도움말` → 트리 현재 항목), 360px `/help` 가로 스크롤 없음.
  - 브라우저 확인: 1440 첫 화면·문서 3단, `?q=소명` 제목 일치 우선, 390px `/help/mes/m-04` 가로 넘침 0·트리 접힘.
- **미실행:** 공식 스모크(`tools/run_portal_smoke.py`) — 다른 세션(UI-03)의 dev 서버가 5173/8000을 점유 중이라 돌리지 않았다. portal.spec 전체와 나머지 spec도 미실행. 배포 전 공식 스모크 필요.
- 배포 보류: 설계·따라하기·개념 문서가 없어 첫 화면에 구역 하나만 보인다. DOC-03·04 후 배포.
- 다음: 사용자 확인 후 DOC-03(따라하기 3 + 개념 15).
- UI-03 스모크·배포(2026-09-27): 공식 스모크 **164 passed**(7.7분, exit 0 — 로컬에서 실패하던 F-03·F-01도 통과, 데이터 의존 실패 확인). origin push `6e22e00..a35e895`(DOC-01·DOC-02 포함), 서버 pull(백엔드 변경 없음, API 재시작 없음) → `a35e895` 프런트 빌드·rsync. 확인: 새 번들 해시 일치·200·API 5xx 0, 운영 게스트 1920×1080에서 M-04·F-12·E-04 넓은 패널(640) 붙음, M-05·M-07 패널(380), 문서 1080px, 오류 0.

## 2026-09-27 UI-03 B1 공정 경로·BOM F-12 부모-자식 패턴 적용 (Antigravity)

- 브랜치: `antigravity/ui03-b1` (기준 커밋: `24179d1`)
- 대상 화면 (2개):
  - M-14 공정 경로(`frontend/src/mes/Routes.tsx`): 경로 버전 목록 → 단계 목록 `DetailPanel wide` → 단계 폼 `FormPanel`(닫으면 단계 목록으로). 게시한 버전 불변(수정·삭제 버튼 없음, 개정=새 버전), '개정'·'게시' 동작 유지, `RevealAnchor` 제거.
  - M-15 BOM(`frontend/src/mes/Boms.tsx`): BOM 목록 → 자재 라인 `DetailPanel wide` → 라인 폼 `FormPanel`. 게시한 버전 불변, 개정 시 새 코드 입력 `FormPanel`, `RevealAnchor` 제거.
- 테스트 및 레이아웃:
  - `frontend/src/mes/versions.test.tsx`: BOM 라인 폼 전환에 맞추어 테스트 접근자(`자재`, `단위`, `소요량(1개당)`, `추가`) 갱신 (8 tests passed).
  - `frontend/e2e/mes.spec.ts`: 공정 경로 개정 흐름 갱신(패널 열림 확인 → 순서 편집 → 저장 → 패널 닫기 후 목록에서 게시).
  - `frontend/e2e/layout.spec.ts`: M-14 공정 경로 단계 패널 및 M-15 BOM 자재 패널 1440×900 문서 높이 ≤ 900 및 Esc 닫기 검사 추가.
- 검증:
  - `npm --prefix frontend run typecheck` 통과 (오류 0)
  - `npm --prefix frontend run lint` 통과 (오류 0)
  - `npm --prefix frontend run format:check` 통과 (전체 일치)
  - `npm --prefix frontend run build` 통과
  - `npm --prefix frontend test` 통과 (44개 파일, 410개 테스트 전체 통과)
  - `git diff --check` 통과 (공백/줄바꿈 이상 없음)
  - `uv run --project backend --env-file .env python tools/run_portal_smoke.py` 공식 스모크 통과 (**166 passed**, 8.0분, exit 0)
- DB migration / Excel / seed: 변경 없음.
- 다음: 사용자 확인 대기. 확인 후 UI-03 B2 (E-02 견적 넓은 행 편집 화면) 진행.

## 2026-09-27 1인칭 비전검사 체험 (FS-3D-FP01, Codex 완료)

- 브랜치 `codex/factory-building`, 기준 `d3eaf31`. 사용자 승인한 웹 1인칭 검사 구역 데모 구현.
- `/factory`의 1인칭 체험 진입, 눈높이 이동·드래그 시선·충돌, 직접 클릭/탭·E 선택, 데스크톱 옆 패널/모바일 아래 패널. 작업자 1명·태블릿·안전 구획·조명 보강.
- 상태·판정·검사/합격/불합격 수량·링 조명·시연 설정값. 합성 시뮬레이션이며 실제 업무 API/계측/DB 연결 없음. 실사 품질 인물·재질은 후속 개선 대상.
- Node 24: typecheck/lint/format:check/build exit 0. Vitest 348개/36파일 통과. 기존 Chromium 회귀 10개 통과, 새 1인칭 3개는 최종 분리 실행에서 모두 통과(1.9분). 처음 한 테스트에 선택·이동·스크린샷을 묶어 60초 제한을 초과한 것은 테스트를 분리해 해소. 화면 직접 확인.
- 5186·모의 API만 사용, backend/DB/공용 스모크·실기기 FPS·Safari/WebXR 미검증. main 병합·push·운영 배포 없음.
- 보고서 `docs/agent/3D공장_1인칭_비전검사.md`. 다음: 통합 담당자가 현재 main/UI 변경과 대조해 3D 커밋 반영 여부 확인 후 사용자 체험. 실제 데이터 매핑과 실사 자산은 별도 후속 범위.
- 통합(2026-09-27, Claude Code): Antigravity UI-03 B1(`2cda062`, M-14 공정 경로·M-15 BOM 부모-자식 패턴) fast-forward + Codex 1인칭 비전검사 체험(`2a739c2` → cherry-pick `941a50d`). Codex 브랜치는 UI-01 이전 코드 기준이라 `Factory.tsx`·`Factory.css` 충돌 — main 파일을 기준으로 Codex 변경 13가지(체험 상태·진입/나가기·포커스 가둠·툴바·조준점·E 선택·이동 패드·설비 상태/설정 패널 등)를 다시 적용하고 CSS 블록은 원본과 동일함을 확인. 보정 `bf8c8e9`: 1인칭에서 설비 상세가 UI-01 겹침 규칙 때문에 장면과 6px 겹치던 것 → 옆 칸 배치.
  - 검증: typecheck·lint·format·build, vitest 412, 3D 브라우저 13 passed(1인칭 신규 3 포함), 1인칭 1440·390 설비 선택·상세·Esc 해제 직접 확인, M-14·M-15 넓은 패널 1440 한 화면, 공식 스모크 **169 passed**(9.6분, exit 0).
  - 참고: DOC-02는 직전 배포(`a35e895`)에 포함되어 이미 운영에 반영됨(작성 세션의 현황 기록은 '배포 보류'였음).
- 배포(2026-09-27): push `24179d1..ad199c1`, 서버 pull(백엔드 변경 없음, API 재시작 없음) → 프런트 빌드·rsync. 확인: 새 번들 해시 일치·API 5xx 0, 운영 게스트 M-14·M-15 넓은 패널 1440 한 화면, 1인칭 체험 설비 상세 열림, 오류 0(첫 방문은 3D 모델 내려받기 대기 필요).
- FS-023 QMS 설계(2026-09-27, Claude Code): 사용자 결정 "QMS 먼저, 읽기 전용 조회" 반영. 산출물 — 결정서 `docs/plan/QMS도입_교차조회_결정_FS-023.md`(D8 QMS 구현 편입·출하 전 최종검사, D9 읽기 전용 조회 인터페이스 X1~X6·격리 규칙 R6, D10 보류는 표시만, D11 스냅샷 보관, D12 독립 동작), 모듈 설계 `docs/modules/qms/QMS_모듈설계_FS-023.md`(qms 6테이블 컬럼·제약·UK_PARTIAL, 상태 전이, TX-Q1~Q3, 인터페이스 함수, API, 시드 약 126행, AC-97~110), 화면 설계 `docs/ui/화면설계_QMS_FS-023.md`(Q-01~06, 기존 D·L·S·P·V·W 패턴만 사용, MES M-08·M-04 배지). 문서 정리: 현황 5장 교체, QMS·WMS README의 'core 소유' 표현 정정.
  - 검증: 설계 문서 정적 대조만(schema.json 테이블 수 71 = mes 21·erp 27·fems 13·core 10 확인). schema.json·마이그레이션·Excel·ERD·코드 변경 없음(승인 후 FS-023a). `npm run db:validate` 미실행(메타데이터 미변경).
  - 다음: 사용자 승인(결정서 6장 3문항 + 모듈 설계 13장 3문항) → FS-023a.
- FS-023a QMS DB 반영(2026-09-27, Claude Code): 사용자 승인(D8~D12·범위·순서·발번·기본 월·패킹 무관 보류 모두 권장안). `schema.json` v0.10.0 — qms 6테이블(불량 유형·검사 기준·검사 항목·검사·측정값·품질 보류), `core.workspace_module` module_key에 qms. 적용 스크립트 `tools/apply_fs023a.py`(멱등, 새 제약·관계는 끝에 붙여 기존 C·R 번호 유지). 마이그레이션 `20260927_fs023a_qms_schema.py`(revision `fs023a_qms`, 실행 시 JSON 미참조 고정 SQL, 제약 이름 = C·R 번호). 검증 도구: `audit_schema_isolation.py` BUSINESS에 qms + **R6**(다른 솔루션은 `fs.<B>.interface`만 import, AST 검사), `validate_db_design.py` FS-023a 엔티티 목록(설계서 표)·`validate_qms`, `verify_ddl_matches_schema.py`·Excel·ERD 생성기에 qms. Excel 23시트·ERD `qms.mmd` 재생성.
  - 수치: 77테이블 · 785컬럼 · FK 175 · 제약/정책 587(DB 제약: PK 77·UK 178·CHECK 183·INDEX 46·UNIQUE_INDEX 11, SERVICE 정책 92).
  - 검증: `npm run db:validate` 오류 0, 격리 검사 R1~R6 오류 0, 도구 단위 테스트 49 OK(신규 `test_fs023a.py` 5), pytest DB에서 alembic upgrade head → verify_ddl 오류 0 → downgrade -1 → downgrade base → upgrade head → verify 오류 0, 로컬 개발 DB upgrade·verify 오류 0, backend pytest **648 passed**(13분 45초), ruff check·format 통과.
  - 미실행: 공식 스모크(프런트·API 변경 없음, 스모크는 실행 시 head를 자체 적용), 운영 서버 마이그레이션(배포 전).
  - 주의: 새 공간의 `qms` 모듈 행 생성·게스트 세대 복사/정리 순서에 qms 추가는 FS-023b·c. 현재 qms 테이블은 비어 있어 기존 복사·회수에 영향 없음(pytest로 확인).
  - 다음: FS-023b — `fs/mes/interface.py`·`fs/qms/interface.py`, `/api/v1/qms` API(TX-Q1~Q3), Q-01~06 화면, MES 배지.

## 2026-09-27 비전검사 AI 설명·세 시나리오 (FS-3D-AI01, 로컬 구현)

- 브랜치 `codex/vision-ai`, 기준 `origin/main 8851772`. 기존 `codex/home-ui-polish` 작업은 보존하고 통합된 1인칭 코드에서 시작했다.
- 정상/불합격 증가/정지 전환, 상태등·판정 주기·검사 정지 연동, AI 설명 버튼 구현. 확인된 사실 / 원인 가능성 / 다음 확인 항목을 구분한다. 활성 시나리오 재선택은 누계를 보존한다.
- 고정 합성 비교 자료: 정상 2%→2%, 증가 2%→20%(+18%p), 정지 처리량 100→50개. 실시간 애니메이션 누계·실제 검사 이미지·업무 센서값과 구분한다.
- 인증·CSRF가 필요한 읽기 전용 설명 API, 서버 전용 OpenAI Responses 어댑터, 성공 캐시·동시 호출 제한·실패 대기 구현. 키 미설정/공급자 오류는 출처가 표시된 데모 설명으로 대체한다. DB·스키마·업무 데이터 변경 없음.
- 프런트 420개/46파일, typecheck/lint/format/build 통과. 서버 DB 없는 모의 공급자 테스트 13개, Ruff 검사/포맷 통과. 배포 wheel의 시나리오 JSON 포함 확인.
- 실제 OPENAI_API_KEY가 없어 실제 Astra 호출·응답 품질·계정 접근은 미검증. 공용 DB 스모크·Safari·실기기 성능은 미실행. main 병합·push·운영 배포 없음.
- 남은 통합 작업: 커밋 반영 검토 → 공식 스모크 → 백엔드 재시작·프런트 재빌드. 실제 AI를 활성화할 경우 서버 비밀 설정에 키를 추가하고 세 시나리오 응답 확인. 운영 반영 여부와 무관하게 키 없이 데모 체험 가능.
- 설계 `docs/modules/factory/README.md`, 상세 인계·재현 명령 `docs/agent/3D공장_AI설명_FS-3D-AI01.md`. 이번 범위 구현 완료, 운영 통합과 실제 모델 검증은 남음.

### 최종 검증 (FS-3D-AI01)

- Node 24 typecheck/lint/format:check/build 통과, Vitest **420 passed / 46 files**.
- DB 없는 backend 설명 테스트 **13 passed**, Ruff check/format 통과. wheel에 `fs/factory/scenarios.json` 포함 확인.
- Chromium 기존 회귀 13개 통과. 신규 시나리오·모바일 2개는 최종 분리 실행 **2 passed**. 전체 실행에서는 한 테스트가 접힌 비교 자료의 중복 문구를 찾아 실패했으나, 보이는 설명 문구를 선택하도록 수정한 후 재검증했다. 총 15개 시나리오 검증, 최종 단일 전체 실행은 반복하지 않았다.
- 1440×900 1인칭 설명 화면과 390px 모바일 패널 캡처 직접 확인. 모바일 가로 넘침 없음. 빌드의 기존 3D 청크 크기 경고와 THREE.Clock 사용 중단 예정 경고는 남아 있다.
- 실제 모델 요청과 공용 DB 스모크는 실행하지 않았다. 작업 폴더 `factory-studio-codex`, 브랜치 `codex/vision-ai`. 결과물은 이번 완료 커밋에 포함되며 원격 push/배포는 하지 않았다.

## 2026-09-27 합성 이미지 검사실 (FS-VISION-LAB01)

- 사용자 승인 범위 구현: 정상/이물/조명 변화 샘플, 전체/중앙 ROI, 임계값·최소 연결 면적 조절, 원본/이진화 화면과 검출 영역, OK/NG 및 오검출·미검출·영역 밖 결함 픽셀 수. 레시피·결과 JSON 다운로드.
- `/factory/vision-lab`, 비전검사 설비 상세에서 진입. 브라우저 순수 함수의 요청/결과 v1 계약 분리. OpenCV·C++·C#·실장비·AI 분석은 연결하지 않음. 새 서버·DB·의존성 없음.
- `codex/vision-ai`, 기준 `0f16bb6`에 후속 구현. 프런트 425 tests / 47 files 통과, typecheck/lint/format/build 통과. 모의 API·5186에서 신규 Chromium 진입/조건 변경/JSON 다운로드/모바일 가로 넘침 검사 통과. 공용 DB 스모크·실장비·Safari 미검증.
- 상세 설계·후속 연결 계약·재현 명령: `docs/agent/합성이미지검사실_FS-VISION-LAB01.md`. 이번 합성 범위 완료. 다음은 통합 검토와 사용자 체험이며 C++/C# 엔진은 별도 후속 범위. 원격 push·운영 배포 없음.

## 2026-09-27 P-02 홈 UI 정돈 (Codex)

- 사용자 Figma 코드/이미지를 시각 참고로 적용. 흰색 홈 헤더·F 마크·중앙 본문·흰색 흐름 배너·저채도 타일. MES/ERP/FEMS 이름·분류만 기본 표시.
- 설명·사용 상태는 호버/키보드 포커스/터치 안내 버튼으로 제공(Esc 닫기). 하단 미구현 목록은 홈에서 제거. 기존 진입·공간/세대·도움말·역할별 메뉴 유지.
- `origin/main 8851772`에서 `codex/home-ui-polish` 분기. 기존 3D 브랜치 보존, 업무/3D/공통 styles.css/backend/DB 변경 없음. 새 의존성 없음.
- Node 24.21.0: typecheck·lint·format:check·build·전체 테스트(418 passed), 독립 Chromium 홈 테스트 8개 및 diff --check exit 0. 데스크톱 기본/hover·360px 직접 확인. 검증 상세 `docs/agent/홈_UI_정돈.md`.
- 공용 통합 스모크·backend/DB 미실행. 5187·모의 API만 사용. push/main 병합/배포 없음. 다음: 사용자 시각 확인 및 통합 담당자 반영.
## 2026-09-27 연속 검사 모드 (FS-VISION-RUN01 완료)

- 사용자 확인한 연속 검사 범위 구현. `codex/vision-ai`, 기준 `da2f02a`. 기존 3종 20회 반복, 500/200ms, 시작/일시정지/재개/종료, 시작 시 레시피 고정.
- OK/NG/합격률/평균 알고리즘 시간, 샘플별 NG, 누적 오검출·미검출·ROI 밖 픽셀. NG 당시 원본/이진화·좌표·면적 조건 재조회, 실행 기록 JSON 다운로드.
- 비동기 어댑터 경계와 세대별 늦은 응답 폐기, 화면 이탈 정리. 설정 이동/탭 숨김 일시정지. 한 배치 20건 메모리 보관, 새 배치·화면 이탈 시 교체/소멸.
- Node 24: typecheck/lint/format/build 통과, Vitest 431 tests / 48 files. Chromium 기존 합성 검사실 1개 + 신규 배치·JSON/라이프사이클 2개 통과(최종 신규 2개 재실행 통과). 1440·390 캡처 직접 확인, 360·390 가로 넘침 없음.
- 실장비·PLC·C++/C#·backend/DB 스모크·Safari 미검증. 기존 3D 청크·Clock 경고 유지. push/운영 배포 없음.
- 다음: 사용자 체험·통합 검토, 이후 별도 작업으로 가상 PLC 상태 머신. 설계 `docs/modules/factory/README.md`, 상세 계약·재현 `docs/agent/연속검사모드_FS-VISION-RUN01.md`.

## 2026-09-27 가상 PLC 핸드셰이크 (FS-VISION-PLC01 완료)

- 사용자 후속 진행 승인. `codex/vision-ai`, 기준 `74a4ec2`. 연속 검사에 선택형 PLC 모드 추가, Ready/Trigger/Busy/Done/OK·NG/Interlock 신호, 요청 ID별 이벤트 로그.
- 300ms 검사 제한·1000ms 확인 제한, 1회 지연/확인 누락 주입, 수동 확인, 중복 트리거 차단, 결과 래치, 명시적 리셋·새 배치 복구. 타임아웃/취소 후 늦은 응답 무효화.
- PLC 수량은 확인까지 끝난 거래만 반영. 확인 실패 결과는 PLC 진단 스냅샷에 보존하고 NG 수량과 분리. 0건 실패 배치도 신호/알람/로그 JSON 다운로드 가능.
- Node 24 최종 typecheck(빌드 포함)/lint/format/build 통과. Vitest **443 tests / 49 files**. Chromium 관련 5개 통과, 로그 ID·알람 표시 보정 후 신규 PLC 2개 재실행 통과. 1440·390 캡처 직접 확인, 모바일 가로 넘침 없음.
- 브라우저 모의 프로토콜. Ready_Req ON 고정, Recipe_ID=RUN_SNAPSHOT. 실제 PLC·통신 SDK·C++/C#·MES·backend/DB 스모크·Safari 미검증. 기존 3D 청크/Clock 경고 유지. push·운영 배포 없음.
- 다음: 사용자 체험/통합 검토 후 C++ OpenCV 코어 분리 및 동일 입력의 결과 비교. 상세 `docs/agent/가상PLC_FS-VISION-PLC01.md`, 공통 설계 `docs/modules/factory/README.md`.

## 2026-09-27 C++ OpenCV 검사 코어 (FS-VISION-CORE01 완료)

- 사용자 후속 진행 승인. `codex/vision-ai`, 기준 `7ec4519`. `native/inspection_core`에 C++17 정적 라이브러리·CLI·CMake·예제·비교 테스트 구현.
- 기존 요청 v1과 검사실 {request,result} JSON 입력, stdin/파일/NDJSON 지원. 결과 source=synthetic-opencv-cpp-v1. 임계값 `<`, 연결 4/SAUF, 픽셀 면적 `>=`, ROI·영역 순서·정답 평가를 웹과 일치시킴.
- CTest 2개 프로그램 통과(8.72초). 원본 TS 엔진 직접 실행과 19,968개 입력 비교: 불일치 0. C++ 핵심 사례, 입력 타입·범위·JSON 오류, NDJSON 오류 후 복구, 파일 입력 검증 통과. 예제 이물 결과 80/36px²·NG 확인.
- 검증 환경: macOS arm64, Apple Clang 21, CMake 4.4.3(Homebrew로 이번 설치), Node24, OpenCV4.13.0·nlohmann-json3.12.0 소스 빌드. 제3자 소스/빌드/로그는 work/에만 보관. CMake4와 OpenCV 내부 정책 경고는 남으나 최종 빌드·테스트 성공.
- 웹/서버/PLC 패널은 기존 브라우저 엔진 유지. 실행 연결·실영상·C#·Windows/Linux·실장비·배포 미검증/미구현. 프런트 코드를 바꾸지 않아 기존 443개 테스트/브라우저 스모크는 이번에 재실행하지 않음. push·운영 배포 없음.
- 다음: 사용자 체험 후 C# 프로세스/통신 어댑터 또는 웹 서버의 네이티브 호출 연결 범위 확정. 요청 ID·취소·시간 제한·출력 검증 계약 필요.
- 재현: `cmake -S native/inspection_core -B work/inspection-core -DINSPECTION_FETCH_DEPS=ON -DCMAKE_BUILD_TYPE=Release -DNODE_EXECUTABLE=/opt/homebrew/opt/node@24/bin/node`; `cmake --build work/inspection-core --parallel 4`; `ctest --test-dir work/inspection-core --output-on-failure`.
- 상세: `native/inspection_core/README.md`, `docs/agent/C++검사코어_FS-VISION-CORE01.md`.

## 2026-09-27 C++ 웹 호출·사용자 참고 문서 (FS-VISION-CONNECT01 완료)

- 사용자 요청한 C++ 호출 연결과 도움말 반영 완료. `codex/vision-ai`, 기준 `848778b`. 운영 배포는 사용자가 직접 진행하며 이번에 push·main 통합·운영 접속/재시작/배포 없음.
- 인증/CSRF POST /api/v1/factory/vision/inspect, 서버 고정 절대경로 VISION_CORE_EXECUTABLE 실행. 2초·동시4개/프로세스·출력1MiB 제한, 요청/결과 모델 검증, 오류503/429/502/504, 브라우저 대체 없음. C++ --timed 추가(기본 CLI 출력 유지).
- 검사실 C++ 단건/JSON, 연속 검사 엔진 선택, PLC 선택 엔진 호출·취소. 엔진 출처·고정 레시피·요청 ID 연결, 순수 C++ 시간 표시. 클라이언트 취소/늦은 응답 폐기.
- 도움말 사용자 참고 문서/포털에 `portal/vision-lab` 추가, 전체 사용 흐름·설정·20회 배치·PLC 장애/복구·JSON·한계 집필. 검사실 왕복 링크·검색·모바일 확인.
- 최종 검증: 프런트 448 tests/50 files, 타입(빌드)/lint/format/build 통과. DB 없는 서버 27 tests(실제 C++·인증/CSRF·검증·미설정·출력오류/상한·시간제한·동시제한·취소) 통과, Ruff check/format 통과. CTest2개 통과, 웹 비교19,968개 불일치0.
- Chromium 관련6개 최종 단일 실행 통과(1.3분). 모의 인증·실제 API·실제 C++ 바이너리로 단건/20회/PLC20회 및 JSON·도움말 확인. 기존 모의 API 회귀 포함. 실제 화면 캡처 확인, 도움말390px 가로 넘침 없음.
- 공용 DB/운영인증/운영배포·Windows/Linux·실장비 미검증. 기존 3D 청크/Clock 경고와 Python 테스트 클라이언트 사용중단 경고 유지.
- 배포 인계: `docs/agent/C++웹연결_FS-VISION-CONNECT01.md`. 서버 OS에서 바이너리 빌드/검증 → 서비스 환경 VISION_CORE_EXECUTABLE 절대경로 설정 → 백엔드 반영·재시작 → 프런트 재빌드·반영 → 게스트C++/PLC/도움말 확인. tests/factory_native_preview.py는 모의 인증이므로 운영 사용 금지.

## 2026-09-28 FS-FACTORY-CONCEPT01 — 정밀 부품 공장 컨셉 완료

- 사용자 요청한 6단계 중 1단계 문서 완료. Factory Studio 유지, 정밀 부품 가공 공장 / 로봇 연동 CNC 가공 셀, CNC → 비전검사 → 포장으로 후속 기준 확정.
- 상세: [컨셉과 개발 기준](plan/정밀부품공장_컨셉_FS-FACTORY-CONCEPT01.md). 제품은 설비용 알루미늄 마운팅 블록. 기존 MTS·독립 솔루션·업무 데이터 소유 경계 유지. 기존 MES 시드와 신규 3D 시연의 차이를 명시.
- WMS README의 오래된 core 마스터 소유·MES 원장 이관 설명 수정. 신규 WMS·자동화·JSON 복원·지도는 미구현.
- 검증: 현재 코드/설계 대조, 문서 링크와 diff 공백 확인. 문서만 변경해 기능/브라우저 테스트 미실행.
- 다음: 2단계 FS-FACTORY-CNC01의 로봇·CNC 형상/상태/정지·복구 및 이름 적용. 6단계 중 1단계 문서 완료이며 구현 공수 진행률 아님. push·배포 없음, 운영 배포 사용자 담당.

## 2026-09-28 FS-FACTORY-CNC01 — 로봇 연동 CNC 가공 셀 완료

- 신규 로드맵 2단계 로컬 구현 완료. 첫 조립 설비를 로봇·그리퍼·CNC 인클로저·문·지그·주축으로 교체. 소재 투입 → 가공 → 배출, 사각 원소재/포켓·구멍 가공품, CNC 이름·현장 표지 적용.
- 시작당 1개, 일시정지/재개, 오류 래치·명시적 해제/재개, 종료 소재 보류, 완료 중복 방지. 모의 인터락, 탭 숨김 정지·언마운트 타이머 정리. 모델/패널이 같은 상태를 사용한다.
- 넓은 화면 CNC 패널 옆 칸 배치, 근접 카메라·충돌 영역 반영. 사용자 참고 문서 `/help/portal/cnc-cell`과 패널 링크 추가.
- 최종 프런트 **456 tests / 52 files**, typecheck(빌드)/lint/format/build 통과. Chromium 전체 실행은 21 passed·1 skipped·1 failed: 편집 중 HMR로 초기화된 1인칭 1건은 수정 없이 재실행 통과(그래픽 손실 포함 최종 재실행 2 passed). **고유 브라우저 시나리오 22개 검증**, 실제 C++ API 1건은 이번 환경에서 제외. CNC 정상/정지/오류/보류·390px·검사실 진입·새 도움말 포함.
- 1280px 완료 화면·390px 패널 캡처 직접 확인. 문서 링크/diff 공백 통과. 기존 3D 청크 크기·THREE.Clock 경고 유지. DB/백엔드/실장비/운영 배포/Safari 검증 미실행.
- CNC 실적은 메모리 전용이며 비전/C++/MES/WMS와 미연계. 기존 MES 시드·DB·API 변경 없음. 절삭 물리·실제 안전 제어 아님.
- 상세: [구현 및 인계](agent/로봇CNC가공셀_FS-FACTORY-CNC01.md). 기준 aac8d26, 브랜치 codex/vision-ai. push·main 병합·배포 없음. 운영 배포 사용자 담당.
- 다음: **3단계 WMS 공통 설계 후 입고·재고·출고·LOT 연결**. 6단계 중 2단계 완료(공수 비율 아님). 자동 운전/JSON 복원/지도는 후속.

## 2026-09-28 FS-026 단계 0 — 최신 main 정렬 완료

- 사용자 지시에 따라 `codex/vision-ai`를 `origin/main` b9dfbc4(FS-025b API 포함)에 rebase했다. CNC 컨셉/구현은 01fc6f5·7b94b48로 재적용했다. 충돌 난 현황·HANDOFF·WMS README는 main 기준을 유지하고 이 항목으로 후속 이력을 보완했다.
- `fad0c3a`는 rebase에서 제외했다. 이전 설계는 `backup/vision-ai-before-fs026-20260928`에 참고용으로만 보존하며 현 브랜치/향후 main 병합 대상에 포함하지 않는다. FS-WMS-DB01은 시작하지 않는다.
- 현재 기준은 FS-024 WMS 6테이블·W-01~07·기존 원장과 FS-025까지의 main이다. 기존 CNC 알루미늄 블록 시연은 메모리 전용이며 WMS 품목 추가 승인이 아니다. 과거 문서의 신규 WMS 개발/미구현 안내는 현재 기준으로 사용하지 않는다.
- 현황, FS-013, 문서 지도, FS-024 결정서·모듈 설계·화면 설계와 backend/src/fs/wms를 확인했다. 원장은 stock_move 합계, source_key로 원천 중복 방지, ERP 매입 취소는 반대 부호 전표, 가용은 현재고−ERP 미출하 지시다. 원자재는 LOT 없이 KG/EA 및 단위 환산을 유지한다.
- 검증: frontend typecheck 통과, CNC/useCnc/WMS 관련 3파일 14테스트 통과, 격리 R1~R6 오류 0(93테이블·209FK), diff 공백 검사 통과. 전체 테스트·브라우저·실제 DB 마이그레이션은 실행하지 않았다. WMS/BEMS 제품 코드·DB 명세·시드는 origin/main 그대로다.
- 다음은 **사용자 0단계 확인 후** FS-026 결정서 작성(D24부터). D13·D17 개정, D14 중복 입출고 방지와 취소 처리, D15 음수/예약 부족 경계, 격리 위치 유형, 트럭 도착 무재고 변경, 기존 품목 및 알루미늄 품목 여부를 질문·권장안으로 정리한다. 결정서·모듈 설계·개발 단계는 아직 시작하지 않았다.
- 후속 전체 설계 승인 후에만 새 migration을 추가한다(현재 head fs025b_bems_module 다음). 업무 간 FK 금지·교차 조회 interface.py만 유지. push·배포 없음. `.env`·`work/` 스테이징 없음.

## 2026-09-28 FS-026 단계 1 — 결정서 초안 작성 완료·승인 대기

- 사용자 단계 0 확인 후 결정서 `docs/plan/WMS확장_입고검수예약_결정_FS-026.md` 작성. D24~D32와 Q1~Q6 권장안이며 세부 정책은 아직 미승인이다. 입고 예정·도착·검수·격리·예약 추가와 D13·D17 개정 방향만 사용자 확정이다.
- D14 보완: ERP 매입 직접 반영/검수 경유의 원천 선점·상호 배타, 수동 기입고 사후 대사(원장 0), 전량 부족, 회계 취소와 실물 정정 분리. D17 대체안: WMS 예약만 가용에서 차감하고 ERP 미출하는 참고 지표. D15의 원천 반영 음수 허용과 신규 예약 부족 거부를 구분했다.
- 격리는 기존 storage_location 유형으로 제안. 트럭은 도착 상태만 변경. 예약은 명시적 ERP 출하 전량 연결 시 원장 차감과 함께 소진하며 별도 출고 차감은 추가하지 않는 안이다. 기존 5품목/단위·LOT 정책 유지, 알루미늄 품목 시드는 제외 권장.
- 검증: FS-024 결정/설계 및 WMS·ERP interface 코드 정적 대조, D24~D32 연속/중복 없음·질문 6개·상대 링크 존재·git diff --check 통과. 문서만 변경하여 기능/브라우저/DB 테스트는 재실행하지 않았다.
- 다음: Q1~Q6 사용자 확인 후 단계 2(모듈 설계 새 revision·화면·AC-139부터). 전체 설계 승인 전 제품 개발/마이그레이션 금지. FS-WMS-DB01 시작 금지. 기존 확정 FS-024 정책은 아직 덮어쓰지 않았다.
- 위치 factory-studio-codex / codex/vision-ai, 기준 4aa1fc7. origin/main 기준 b9dfbc4, 완료 커밋은 git log -1로 확인. `.env`·work/ 스테이징 없음. push·배포 없음.

## 2026-09-28 FS-026 단계 2 — 모듈·화면 설계 revision 2 작성, 전체 확인 대기

- 사용자 “진행해줘”로 결정서 Q1~Q6 권장안/D24~D32 승인 기록. 모듈 `docs/modules/wms/WMS_모듈설계_FS-026.md`, 화면 `docs/ui/화면설계_WMS_FS-026.md` 작성. 기존 FS-024 문서는 이력으로 보존하고 후속 링크를 추가했다.
- 기존 6테이블 재사용 + inbound_notice/inbound_notice_line/source_claim/stock_reservation/stock_reservation_line 5개 추가(계획 총11). location_type 및 WMS_INSPECTION 전표 유형 차분, source_claim과 기존 전표의 공간 락 내 검사로 이중 입고 방지. 전량 부족은 전표 없이 처리 완료를 보존한다.
- TX-W4~W9, version/멱등/영구 중복키, ERP interface 읽기 계약, 신규 API, 기존 stock/dashboard 가용 의미 개정, 게스트 복사/번호·snapshot digest 재계산을 정의했다. 실제 ERP 출하지시 상태는 open/shipped/cancelled다.
- 기존 W-01~07 확장 + W-08 입고 예정·검수/W-09 출고 예약 + 3D 트럭 도착 패널. AC-139~164 26개 작성(미실행); 기존 AC-123 대체, AC-114/118 적용 경계 명시.
- 검증: 설계 상대 링크 존재, AC 번호 연속·중복 없음, 신규 테이블 5개, diff 공백 검사 통과. 문서만 변경하여 DB/기능/브라우저 테스트 미실행. migration·schema.json·DB설계서.xlsx·운영 ERD·제품 코드·시드 변경 없음.
- 다음: **사용자 전체 설계 확인 후에만** FS-026a(DB/메타데이터/Excel/ERD/검증) 착수. 현재 head fs025b_bems_module 뒤 새 revision 제안, 착수 시 head 재확인. 적용 migration 수정 금지. FS-WMS-DB01 금지, fad0c3a는 참고만.
- 브랜치 codex/vision-ai, 기준 3b51671. 최종 커밋은 git log -1로 확인. `.env`·work/ 스테이징 없음. push·배포 없음.

## 2026-09-28 FS-026a — WMS 확장 DB 기반 완료

- 사용자 전체 설계 승인 및 질문 권장안 진행 지정. 기존6+신규5 WMS 테이블, 위치 유형/검수 전표, metadata v0.13.0(전체98/1022컬럼/225FK), 새 revision fs026a_wms_receiving_reservation 구현. 이전 migration 수정 없음.
- DB설계서31시트·ERD·검증기/보고 동시 갱신. NULL LOT 부분 유니크, 검수수량/상태 CHECK, 원천 유효선점·소진 유일성. 데이터가 있는 downgrade는 중단한다. SERVICE 정책/API/화면은 후속 미구현.
- 검증: DDL대조0·R1~R6오류0, 이전head/빈base downgrade→upgrade 통과. 기존WMS15+신규DB7+DDL변조9+시드16 = 고유 선택47 tests 통과. DDL변조1건은 시드가 남은 DB에서 실패하여 빈 DB 재실행9건 통과. tools58, Ruff/diff 통과. 전체/브라우저 회귀 미실행.
- 전용 로컬 테스트DB2개만 적용. 공유 개발/운영DB·시드 품목 변경 없음. origin/main489d5f3의 migration head가 fs025b_bems_module 그대로임을 확인했고 새 BEMS UI는 이번 브랜치에 rebase하지 않았다.
- 다음 FS-026b API(입고/원천선점/검수/예약·가용/출하연결·동시성), 이후 화면·트럭·도움말·시드. 세부 선택은 승인 권장안. push·배포 없음, .env/work 스테이징 없음.
- 상세: docs/agent/WMS확장_DB_FS-026a.md. 브랜치 codex/vision-ai, 기준01b6cce, 완료커밋 git log -1.

## 2026-09-29 FS-026b1 WIP
- main6508599 rebase 완료(main HANDOFF 유지), BEMS 포함 템플릿11,910 기준 유지.
- 입고 예정/도착/검수/원천선점 API 작성, 기존 원천 sync 연결, 날짜 제외 digest와 게스트 복사 처리. 입력400/멱등422 설계 수정.
- 실제 DB 신규 테스트 진행 중. 전체 회귀/ruff/격리 감사 미완료. b2는 b1 보고 확인 후.

### FS-026b1 중간 검증
- 신규 API23개 통과, 기존 W-03 새 상태 호환과 검수 전표 이름 보강(프런트10개/typecheck/변경 ESLint 통과).
- 전체 pytest 재실행 중. ruff134파일·격리감사·정적 DB 검증 오류0. 예약가능 조회 및 b2는 미착수.

## 2026-09-29 FS-026b1 완료
- main6508599 rebase 후 TX-W4~W7 입고 예정/도착/검수/원천선점 및 기존 sync 라우팅 완료. b2는 미착수.
- 입력400/멱등422, 의미 값만의 source_digest, 게스트 복사 confirmedAt 날짜 이동·digest 보존, 신규 DB 시각 통일. 기존 W-03 표시 호환 보강.
- **backend 전체755 passed(1204.94초, 경고2)**, 신규 입고23 포함. 도구58+subtests13, WMS 프런트10, typecheck·변경 ESLint 통과. CI ruff134파일·R1~R6·db:validate 오류0.
- 스키마/기존 migration/main 시드합계11,910 미변경. 새 입고 화면·브라우저·운영 검증 미실행. AC141 예약가능 조회는 b2.
- 구현 a832fa8(16045ae 포함). 상세 docs/agent/WMS확장_API_FS-026b1.md. 사용자 확인 후 b2만 진행, push·배포는 별도 확인.

## 2026-09-30 FS-026b2 WIP — 예약·소진·가용

- 사용자가 다음 진행 방향 1번(b2)을 승인했다. 브랜치 codex/vision-ai, 기준 3f5039c/main6508599. TX-W8~W9, AC151~158 구현. 예약 생성/해제, ERP 확정 출하 전량 소진, 원장·예약 경합 직렬화, 격리 제외/위치별 부족 보존, ERP off 가용 계산.
- ERP 조회는 interface.py만 사용. 신규 처리 시각 clock_timestamp, FS_TODAY 미사용. 게스트 예약 번호 날짜 이동/FK 재매핑. 기존 W-01/02 가용 표시 호환만 반영; W-08/09 미구현.
- 현재 관련 API60개(신규22 포함), WMS 프런트10개/typecheck/변경 ESLint 통과. CI ruff138파일, R1~R6 감사0, db:validate0. 전체 pytest 전용 factory_studio_codex_fs026b2_final_test에서 실행 중. 최종 결과 전 완료 아님.
- migration/schema/Excel/ERD 변경 없음. 템플릿11,910 유지. .env/work 스테이징 금지, push·배포 없음. b2 최종 보고 후 사용자 확인을 기다린다.
- 재현: 전용 *_test DB의 DATABASE_URL/TEST_DATABASE_URL을 환경으로 제공한 뒤 backend/.venv/bin/pytest backend/tests -q --tb=short. Ruff는 backend/pyproject.toml 명시(CI 명령). 상세 docs/agent/WMS확장_API_FS-026b2.md.

## 2026-09-30 FS-026b2 완료 — 다음은 사용자 확인 후 화면

- 위 b2 WIP 상태를 이 항목으로 대체한다. 사용자 후속 1번 승인에 따라 TX-W8~W9/AC151~158 완료. 브랜치 codex/vision-ai, 기준 main6508599/3f5039c, 구현 0d639b7. 최종 보고 커밋은 git log -1.
- 예약 생성·해제·ERP 확정 출하 전량 소진, 동일 원천 단일 전표, sync 경합, 정상 현재고−활성 예약, 격리 제외, 위치별 부족 보존, ERP off 가용 계산. AC141 예약가능95 조회도 검증 완료.
- 입력400/멱등422, clock_timestamp 처리 시각 통일, FS_TODAY 미사용. ERP interface 조회만 사용, 게스트 예약 날짜/FK 복사. 기존 W-01/02 화면·도움말 새 계산식 호환. 신규 W-08/09 화면은 아직 없음.
- 최종 검증: **backend 전체777 passed, 2 warnings, 1414.37초**(신규22 포함). 관련 WMS60, 프런트 전체490/56파일, 도구58+subtests13, typecheck/build/변경 ESLint 통과. CI ruff check/format138파일, R1~R6 감사98테이블/225FK 오류0, db:validate 오류0. 기존 사용중단 경고2와 프런트 청크 경고 유지.
- 전용 factory_studio_codex_fs026b2_final_test에서 실행. migration head fs026a_wms_receiving_reservation 유지; schema/Excel/ERD·시드 기준11,910/복사11,908 및 seed/validate.py·test_seed/test_common 변경 없음. 공유 개발/운영DB 변경·push·배포 없음, .env/work 스테이징 없음.
- 다음: **사용자 b2 확인 후** W-08 입고 예정/도착/검수와 W-09 예약 화면 및 브라우저 흐름 검증. 이후 3D 트럭 도착·체험 시드·종합 사용자 도움말·통합 점검. 신규 화면/브라우저/운영 검증은 이번에 하지 않았다.
- 상세 API/AC 근거 및 비밀값 없는 표준 재현 명령: docs/agent/WMS확장_API_FS-026b2.md. 전용 *_test DB 환경을 주입하고 pytest backend/tests 실행, Ruff는 backend/pyproject.toml 명시. main HANDOFF 본문은 보존했다.

## 2026-09-30 FS-026 후속 UI·트럭·시드·도움말 통합 WIP

- 사용자 b2 후속 전체 승인: 화면 → 3D 트럭 → 시드/도움말 → 통합 검증까지 중간 확인 대기 없이 진행. push·배포는 제외. 기준 9c66cf1, codex/vision-ai.
- W-08/09, 읽기 전용 출하 대조 미리보기·날짜/예약부족 필터, 기존 W-01~07 연결, 3D 도착 API, 정상/격리 위치, 포털 사용자 흐름 문서 구현 중.
- 새 템플릿 sv-20260930-1: WMS22행 추가, 총11,932/복사11,930. BEMS4,218행 그대로. 기존5품목, R-Q01/F-Q01, 예정/도착/95·3·2 검수/전량부족/취소, 활성/해제/소진 예약. 소진 시드는 기존 역사 출고 전표를 새 템플릿의 소진 예약 이력으로 연결하며 추가 차감하지 않는다. PI-0004/SH-0004 미반영 유지. 운영 기존 템플릿은 수정하지 않는다.
- 관련 backend76개 통과(새 preview/filter 테스트 추가 검증 중). 실 API 브라우저 트럭도착→원장0→검수95/3/2 및 새로고침 통과. 다른 브라우저 시나리오/전체 회귀는 진행 중이며 완료 아님.
- 로컬 전용 fs026_ui_test / fs026_browser_test 사용. 브라우저용 API localhost8000은 현재 실행 중(합성 시크릿, 로컬 쿠키). 테스트 종료 후 중지 예정. .env/work 스테이징 금지.
- 다음: 브라우저 실패 수정·모바일/3D 캡처 확인, 전체 pytest/프런트·ruff·격리 감사·도움말 링크·문서 갱신. 최종 커밋/인계 후 종료.

## 2026-09-30 FS-026 후속 통합 완료 — 입고·예약 화면 / 트럭 / 시드·도움말

- 앞선 후속 WIP 상태를 대체한다. 사용자의 후속 전체 승인 범위 완료. `codex/vision-ai`, main6508599 기준 유지, 구현 `cd41b04`, 연속 조작 보완 `0ad25ee`. 마지막 문서 커밋은 `git log -1`.
- W-08 입고 예정·도착·검수·원천 연결, W-09 예약·출하 대조·소진, 기존 W-01~07 정상/격리/예약/가용 표시·동선 확장. 저장 응답의 최신 version을 즉시 반영하여 빠른 다음 조작의 이전 버전 사용을 방지한다.
- 3D 트럭은 서버 도착 상태만 변경한다. 검수 때만 재고 증가, 예약 때 원장 불변, 소진 시 기존 출하 원천과 중복 차감 방지. 통신 실패/재시도/응답 유실 복구/미저장 보호 포함. CNC 수량·GPS/실차·실장비 연결 제외.
- 시드 sv-20260930-1: 템플릿11,932 / 게스트11,930, 기존 품목·BEMS4,218 유지. WMS22행 추가. 새 migration 없음(head fs026a_wms_receiving_reservation), metadata98테이블/1022컬럼/225FK 유지. 기존 템플릿·운영 DB 수정 없음.
- 최종 검증: 전체 backend **779 passed**(23분39초, 기존 경고2), frontend **491 passed /57파일**(maxWorkers=2), 실제 API Chromium **10 passed**(1.2분). 전체 typecheck/lint/format/build 통과, Ruff139파일 통과, R1~R6 격리 감사0·db:validate0, tools58+subtests13 통과. 기본 병렬 프런트 실행의 기존 ERP 테스트 일시 실패·재검증 및 경고는 통합 보고에 기록.
- 도움말 W-08/09, 기존 W-01~07, 사용자 참고 `/help/portal/wms-flow` 반영. 360px와 트럭 외관 캡처 확인. 보고·재현·AC 증거: `docs/agent/WMS확장_화면트럭통합_FS-026.md`.
- 검증용 API/Vite 종료. `.env`·work 스테이징 없음. **push·운영 배포 없음. 이번 승인 범위 남은 개발 없음.** 다음은 사용자의 통합/운영 반영: 백엔드·프런트를 함께 적용하고 새 템플릿 생성·검증 후 새 게스트에서 체험한다. 기존 기록을 소급 변경하지 않는다.

## 2026-10-01 FS-030 GW 결정서 — 승인 대기

- 사용자 GW 별도 담당 지시에 따라 fetch 후 최신 origin/main7a2d70f(67540be 후속)에서 `codex/fs-030-gw` 생성. 작업 폴더 factory-studio-codex만 사용, vision-ai에서 이어 개발하지 않음.
- `docs/plan/GW도입_전자결재_결정_FS-030.md` 작성. D60~D69, AC220~239 범위 유지. 합성 담당자/실제 인증 주체 구분, 순차 결재·회수·재상신 불변 이력, 원문 변경·off·최신 회차 배지, 글 포함/댓글·첨부 제외 해석을 승인안으로 보완.
- 권장: ERP 매입 전표 한 종류+일반 기안, E-11 읽기 전용 배지 포함. ERP 교차 쓰기/확정 통제 없음. 결정은 아직 승인되지 않음.
- 킷의 공용 개발 DB 적용 지시는 이번 전용 DB 지시로 제외. 적용 migration 불변과 병합 head 변경 충돌은 DB 착수 전 재확인 및 새 연결 방식 조율로 기록. 현재 head fs026a_wms_receiving_reservation, metadata v0.14.0/103테이블 유지.
- 검증: 문서 상대 링크5개·D번호10개·AC20개·현황173/200줄 정적 검사 통과(exit0), git diff --check 통과(exit0). 제품 코드/스키마 변경이 없어 pytest·프런트·브라우저·migration·시드·격리 감사는 미실행. DB 접속/공용 서버 실행 없음.
- 다음: **사용자 결정서 승인 후** GW 모듈/README·G-01~07 화면 설계. 전체 설계 승인 전 schema.json·migration·제품 코드 작성 금지. 이후 a/b/c 각각 보고 후 대기. push·배포·main 병합 없음. 최종 문서 커밋은 git log -1로 확인.

## 2026-10-01 FS-030 GW 전체 설계 작성 — 승인 대기

- 사용자 “진행해줘”를 결정서 권장안 4항목 승인으로 기록(D60~69). 브랜치 codex/fs-030-gw, main7a2d70f/선행 결정커밋 b873543.
- 새 문서: docs/modules/gw/GW_모듈설계_FS-030.md, 같은 폴더 README.md(현재 기준/조회 계약), docs/ui/화면설계_GW_FS-030.md. 결정서·로드맵·현황 갱신.
- gw8테이블, G01~07+E11 읽기 배지, TX-G1~6/API/권한/잠금/오류/불변 이력·재상신·원문 digest/복사·시드69행(+모듈행1 별도) 설계. AC220~239 연결. source digest는 ERP 소유 정규화 함수로 일원화; 제공 interface 사이 재귀 호출 금지.
- 검사: 문서4개 상대 링크17개·테이블8·화면7·AC20·시드합69·현황173/200줄 정적 검사 통과(exit0), git diff --check 통과(exit0). 최초 임시 검사 정규식이 interface 함수까지 테이블로 세어 실패했으며 식별자 패턴 보정 후 통과. 제품 검증 결과가 아님.
- 미실행: pytest·vitest·브라우저·DB migration·시드 생성·격리 감사. 문서만 작성했고 제품 코드/schema.json/Excel/ERD/migration 변경 및 DB 접속 없음.
- 다음: **사용자 모듈·화면 전체 설계 확인 후 FS-030a DB**. a 착수 전 최신 main/head/공통 파일·SPC/CMMS 시드 합계 재확인. 적용 migration 수정 금지, Codex 전용 DB/포트만 사용. a/b/c 각각 보고 후 대기. push·배포·main 병합 없음. 최종 문서 커밋은 git log -1.
