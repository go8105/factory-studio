# 문서 지도

2026-10-25 **GW-READY-02 56차**: 신뢰 이력 내보내기·별도 최신 원장/지문으로 새 폴더 원본 복구. [실회사 절차 §30](operations/GW_실회사_인수절차_10인_GW-READY-02.md). 기존 손상/최신 회수 상태 보존·입력 전 보류/동일 재개. 외부 독립성·서버 설치/실인수는 후속이며 ready=false·실제 복원 PARTIAL 유지.

2026-10-25 **GW-READY-02 55차**: 목록 키 상태의 로컬 영구 이력·설정 후퇴/회수 복원 차단. [실회사 절차 §29](operations/GW_실회사_인수절차_10인_GW-READY-02.md). 명시 CAS 설치/회수와 완성 중단 재개, 목록 환경의 보존 설정 필수. 외부 독립 원장/전체 복제본 롤백·유실 복구는 후속이며 ready=false·실제 복원 PARTIAL 유지.

2026-10-25 **GW-READY-02 54차**: 여러 차례 목록 키 교체의 정확한 이관 연결·현재 회수/중간 키 자기 이관 대조. [실회사 절차 §28](operations/GW_실회사_인수절차_10인_GW-READY-02.md). 오래된 개인키 없이 최대8연결을 검증하며 독립 영구 회수 원장·실환경 인수는 후속. ready=false·실제 복원 PARTIAL 유지.

2026-10-25 **GW-READY-02 53차**: 목록 키 한 단계 정상 교체·정확한 과거 원본/복구 근거 검증과 현재 회수 우선. [실회사 절차 §27](operations/GW_실회사_인수절차_10인_GW-READY-02.md). 여러 단계 이관/독립 영구 회수 원장·실환경 인수는 후속이며 ready=false·실제 복원 PARTIAL 유지.

2026-10-25 **GW-READY-02 52차**: 큰 목록 이력의 분할 전달·같은 명세의 진행점 복구/최종 단일 활성화. [실회사 절차 §26](operations/GW_실회사_인수절차_10인_GW-READY-02.md). 중간 수신은 운영 근거로 사용하지 않으며 ready=false·실제 복원 PARTIAL 유지. 과거 키 이관/외부 독립 인수는 후속.

2026-10-24 **GW-READY-02 51차**: 발행 공백의 서명 복구·수신 기준점 연결/불완전 원본 보존. [실회사 절차 §25](operations/GW_실회사_인수절차_10인_GW-READY-02.md). 큰 이력 분할/근거 없는 유실·외부 독립 인수는 후속이며 ready=false·실제 복원 PARTIAL 유지.

2026-10-24 **GW-READY-02 50차**: 별도 수신 기준점·보존 서명 이력 전달/보류 재시도·미수신 버전 따라잡기. [실회사 절차 §24](operations/GW_실회사_인수절차_10인_GW-READY-02.md). 발행 공백/원본 유실·외부 독립 인수는 후속이며 ready=false·실제 복원 PARTIAL 유지.

2026-10-24 **GW-READY-02 49차**: 로컬 목록 발행·원자 핀 교체/중단 차단·새 PARTIAL 복구. [실회사 절차 §23](operations/GW_실회사_인수절차_10인_GW-READY-02.md). 수신자 전달/외부 인수는 후속이며 ready=false·실제 복원 PARTIAL 유지.

2026-10-19 **[GW-READY-02 실사용 구현 진행](agent/GW_실사용구현_GW-READY-02.md)**: 계정보호·긴급복구·운영증거·보관검토와 서버용 암호화백업/격리복원·확인된 제한 재적용 구현/합성 검증. 회사 업무·공통 인증/HR 주요 변경 경로의 암호화 기록·DB 감사 지문 대조까지 구현했다. 백업 시점 DB 확인 지문과 이후/미확인 기록의 격리 복원 제한 연결도 추가했다. 미확인 인수 진단 보고와 제한 유지 기준까지 추가했다. 암호화 기록 사본 내보내기·오프라인 인증도 추가했다. 기존 지문을 유지한 새 기록 폴더 교체 도구도 추가했다. 전달 확인 기록과 백업 자동 지문 입력도 추가했다. 운영 준비에 최신 증거별 현재 조건과 차단 근거도 표시한다. 새 증거 원본 보존·서명 재검증도 연결했다. 전체 완전성·과거 원본 없는 기록/미확인 해소·외부 보관 인수/실환경 복구·최종 운영 전환/SSO·최종 인수는 남아 있으며 복원PARTIAL·main/원격/운영 미반영.

2026-10-18 **[GW-READY-01 실사용 보안·운영·UI 설계](agent/GW_실사용설계_UI검토_GW-READY-01.md)**: GitHub GW 비교·10인 기본안·MFA/복구/선택형 SSO·운영 기준·DB/API/제안 Excel·검토 화면 완료. 전체 설계 확인 대기이며 제품 미구현. 로컬 main 2be292e·현재 DB 유지, 원격/배포 없음.


2026-10-18 **[GW-COMPANY-05 WMS 통합·10인 인수 검증](agent/GW_WMS통합_인수검증_GW-COMPANY-05.md)**: schema0.27/210표·merge head·데이터 보존/폐쇄 복원·10인 HTTP·전체 회귀 확인. 로컬 main 반영, 원격/배포 없음. 실제 회사 인수는 MFA·복구/보존·담당자/환경 조건 미충족으로 미완료. 아래04의 WMS 미통합 안내는 당시 이력이다.

2026-10-17 **[GW-COMPANY-04 회사 화면·협업 권한](agent/GW_회사화면_협업권한_GW-COMPANY-04.md)**: 회사63경로·G-01~13·도움말 연결, 합성 Chrome 대표 업무와390px/연결회수 확인. 로컬 GW 브랜치 검증이며 main/WMS 통합·실운영 인수는05 후속, 원격/배포 없음. 아래03의 업무 미공개 안내는 당시 상태다.

2026-10-17 [고도화 진행 순서](plan/시스템고도화_진행순서_UPGRADE-01.md) · [GW 회사 인증·권한 승인 설계](modules/gw/회사인증_권한_통합설계_GW-COMPANY-01.md) · [기반 구현·검증 GW-COMPANY-02](agent/GW_회사인증_기반검증_GW-COMPANY-02.md)(로컬 검증 완료·회사 업무/UI 후속) · [직원 연결·업무 권한 GW-COMPANY-03](agent/GW_직원연결_업무권한_GW-COMPANY-03.md)(관리 API/내부 서비스·회사 업무 공개 전) · [63경로 감사표](agent/GW_회사인증_경로감사_GW-COMPANY-01.md).

2026-10-12 다섯 시스템의 [제품 도움말·구현/제한·검증·후속 순서 기준](agent/제품도움말_구현대조_HELP-01.md): CAD/CAM, GW, 독립 Factory Flow, 3D 공장, PWA 내 근무. 사용자 도움말은 `content/help/`의 정적 문서이며 개발 설계/시제품과 구분한다.

[Factory Flow 독립 Work OS·업무일지 전체 설계](modules/flow/README.md) — FLOW-02a 독립 진입·기존 보드 이관·UI 운영 배포 완료, 날짜별 일지는 후속.

이 폴더의 구조와 각 폴더가 담는 것.
**무엇부터 읽을지 모르겠다면 [현재 기획과 진행 현황](plan/현재기획_진행현황.md) 하나만 읽으면 된다.** **2026-10-04부터는 전체 설계 우선**([ROADMAP-02](plan/전체설계우선_전환_ROADMAP-02.md))이다 — 솔루션 설계는 [기능 기준표 양식 DSN-00](plan/기능기준표_DSN-00.md)을 따른다. 17개 목록·교차 조회 규칙은 [ROADMAP-01](plan/로드맵_17개시스템_ROADMAP-01.md).

## 폴더 구성

| 폴더 | 담는 것 |
|---|---|
| `plan/` | 기획 — 현황, 개발 기준, 일정, 설계 승인 기준 |
| `agent/` | 작업 규칙 — 환경 점검, 참조 프로젝트 검토 |
| `architecture/` | **모듈 횡단** 설계 — 공통 ERD, 상태·권한·트랜잭션, 전체 업무 흐름, 시드 |
| `architecture/erd/` | 모듈별 관계도 (HTML 탐색기 + Mermaid 원본) — 실제 DB(`schema.json`) 기준 |
| `architecture/erd-target/` | 목표 설계(`schema-target.json`) 관계도 — DSN 설계 기간 |
| `modules/` | **모듈별** 설계 — core / mes / erp / fems / learning / qms / wms / bems |
| `db/` | 메타데이터 기준본(`schema.json` = 실제 DB, `schema-target.json` = 목표 설계), Excel 설계서(`DB설계서.xlsx`·`DB설계서_목표.xlsx`), 검증 보고서(`*-target.json` = 목표) |
| `ui/` | 화면 설계 |
| `operations/` | 배포·백업·초기화·장애 대응 (구현 단계에서 작성) |
| `references/` | 사용자 제공 참고 자료. **공개 저장소 업로드 대상 아님** |
| `progress.md` | 작업 진행 기록. 작업이 끝날 때마다 추가한다 |

## architecture 와 modules 의 경계

한 모듈 안에서 닫히면 `modules/`, 여러 모듈에 걸치면 `architecture/`다.

- 공통 ERD, 트랜잭션·락 순서, 게스트 공간, 전체 업무 흐름, 시드 정의 → `architecture/`
- FEMS 다중 에너지원 설계, MES 업무 카드, 학습 경로 → `modules/`

## 모듈 문서 규칙

**`modules/<모듈>/`에 공통 설계서가 없으면 그 모듈은 개발 착수 대상이 아니다.**
설계를 먼저 확정하고 사용자 확인을 받은 뒤 구현에 들어간다. 각 모듈의 상태는 그 폴더의 `README.md`에 있다.

업무 마스터는 MES·ERP·FEMS가 독립 소유한다. `core`는 인증·공간·세대·운영만 소유한다. 업무 간 FK는 금지하며 범위 앵커만 공유한다. 현재 엔티티는 [FS-014 기본 목록](db/스키마_재구성_FS-014.md)과 [FS-014b 회계 확장](db/스키마_재구성_FS-014b.md) 및 [FS-008b 화면 갭 반영](db/스키마_재구성_FS-008b.md)을 따른다. 현재 71테이블이다.

## 초기 모듈 상태 이력

아래 표는 초기 FS-013 시점의 이력이며 현재 구현 상태가 아니다. 현재 상태는 현황 문서와 각 README 상단을 따른다.

| 모듈 | 상태 | 모듈 설계서 |
|---|---|---|
| core | 구현 대상 | 공통 ERD가 대신한다 |
| mes | 구현 대상 | 참조 분석·업무 카드만 있음 |
| erp | 구현 대상 (ERP-1) | **없음 — 작성 필요** |
| fems | 구현 대상 | FS-005c (반영 완료) |
| learning | 과정·진도·채점 폐기 | 업무 설명 문안만 도움말 원천으로 보존 |
| qms · wms | 준비 중 | 없음. 테이블도 없음 |
| bems | 정적 설명 카드만 | 예약 테이블은 FS-014에서 삭제 |

## 문서를 옮겼다면

경로가 바뀌면 상대 링크와 검증기 경로가 함께 깨진다. 이동 후 반드시 실행한다.

```
python3 tools/fix_doc_links.py            # 미리보기
python3 tools/fix_doc_links.py --write    # 반영
npm run db:validate                        # 검증기 경로 확인
```

`tools/validate_db_design.py`는 설계 문서에서 엔티티 목록을 읽는다. 그 문서를 옮기면 스크립트 안의 경로도 함께 고쳐야 한다.

## 합성 비전 검사 네이티브 코어

- [C++ OpenCV 빌드·실행·JSON 계약·웹 비교](../native/inspection_core/README.md)
- [3D 공장·합성 검사 공통 설계](modules/factory/README.md)

## 정밀 부품 공장 확장

- [1단계 제품·공정 컨셉 및 명칭](plan/정밀부품공장_컨셉_FS-FACTORY-CONCEPT01.md) — 2026-09-28 문서 완료, 로봇/CNC 구현은 다음 단계.

- [2단계 로봇 연동 CNC 가공 셀 구현·검증](agent/로봇CNC가공셀_FS-FACTORY-CNC01.md) — 로컬 구현 완료, 다음 WMS 설계.

- [FS-026 WMS 확장 결정서](plan/WMS확장_입고검수예약_결정_FS-026.md) — 기존 FS-024 확장, D24~D32 승인.

- [WMS 모듈 revision 3](modules/wms/WMS_모듈설계_FS-026.md) · [화면 revision 2](ui/화면설계_WMS_FS-026.md) — 전체 설계 승인, AC-139~164(업무 기능 검증은 후속).

- [FS-026a WMS DB 구현·검증](agent/WMS확장_DB_FS-026a.md) — API·화면은 후속.

- [FS-026b1 WMS 입고 API 구현·검증](agent/WMS확장_API_FS-026b1.md) — 입고 예정·도착·검수·원천 선점, 입고 API 완료.
- [FS-026b2 WMS 예약 API 구현·검증](agent/WMS확장_API_FS-026b2.md) — 예약·소진·가용 완료, 전체 pytest777 통과.

- FS-026 WMS 후속: [입고·예약 화면, 3D 트럭, 시드·도움말 통합](agent/WMS확장_화면트럭통합_FS-026.md).

## CAD·CAM·공장 UI와 디자인 스킬

- [UI 전체 검토안 UI-DESIGN-01](ui/UI개선_전체검토안_UI-DESIGN-01.md)·[구조 시제품](ui/previews/UI-DESIGN-01.html): 랜딩·CAD·CAM·3D 공장 제안. 사용자 추천안 확인 후 [UI-DESIGN-02 적용](agent/UI개선_적용결과_UI-DESIGN-02.md).
- [프로젝트 디자인 스킬](../.agents/skills/README.md): Taste는 랜딩, Impeccable은 작업 화면과 도움말.
- 공개 사용자 안내는 `content/help/portal/{cad-cam,part-design,nc-review,hugh-d,factory}.md`에 있다. 관리자 비공개 POC 설계를 공개 도움말에 싣지 않는다.

- GW-READY-02 [관리자 긴급 복구 운영 절차](operations/GW_긴급관리자복구_GW-READY-02.md): 개발 구현·합성 검사 기준, 실환경 인수 미완료.

- GW-READY-02 [운영 증거 등록·서버 설정](operations/GW_운영증거등록_GW-READY-02.md): 서명 기록 등록/조회 구현, 백업 실행기·실환경 인수 미완료.

- GW-READY-02 [보관 검토·보존 중지 계약](operations/GW_보관검토_보존중지_GW-READY-02.md): 원본 삭제/보관 완료 없이 검토·보류·원문 ACL·변경 이력 구현.

- GW-READY-02 [암호화 백업·격리 복원 서버 절차](operations/GW_암호화백업_격리복원_GW-READY-02.md): 로컬 실제PG 왕복·부분복원, 스케줄은 미설치 템플릿.
- GW-READY-02 [직원 연결·역할 변경 기록](operations/GW_직원연결_역할변경기록_GW-READY-02.md): 설정 환경의 GW·공통 인증/HR 변경 의도 기록·체인/최신 지문·DB 감사 지문 대조. 백업 기준/미확인 이력의 제한 연결 구현, 전체 완전성/실인수는 미완료.


GW-READY-02 10차: [거래 취소 판정과 제한 유지 조건](operations/GW_직원연결_역할변경기록_GW-READY-02.md), [새 격리 복원 절차](operations/GW_암호화백업_격리복원_GW-READY-02.md). 실운영 준비 완료를 뜻하지 않는다.

[GW 보안 변경 수집 경로 검증](operations/GW_보안변경_수집경로검증_GW-READY-02.md): 로그인 요청·거부 누락 보완과 전체 회수 인수의 남은 범위.

GW-READY-02 18차: [초기 설정 도구 기록·세션 재생 제외 근거](operations/GW_보안변경_수집경로검증_GW-READY-02.md). 실제 운영 계정이나 설정은 변경하지 않았다.

GW-READY-02 19차: [운영 경로 v1과 격리 복원 인증 거부 검증](operations/GW_보안변경_수집경로검증_GW-READY-02.md). 합성 검증과 실제 운영 전환을 구분한다.

GW-READY-02 20차: 운영 준비의12조건을 확인/조치/미확인으로 구분하고 현재 책임자 연결·원본 서명 증거를 대조한다. 외부·실회사·최종 전환은 계속 미확인이다.

[GW 10인 실회사 인수 절차와 남은 작업](operations/GW_실회사_인수절차_10인_GW-READY-02.md):21차 제품 인수 근거 안내·현재 구현/미확인 증거 연결/실환경 전환 구분.
