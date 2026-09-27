# 문서 지도

이 폴더의 구조와 각 폴더가 담는 것.
**무엇부터 읽을지 모르겠다면 [현재 기획과 진행 현황](plan/현재기획_진행현황.md) 하나만 읽으면 된다.**

## 폴더 구성

| 폴더 | 담는 것 |
|---|---|
| `plan/` | 기획 — 현황, 개발 기준, 일정, 설계 승인 기준 |
| `agent/` | 작업 규칙 — 환경 점검, 참조 프로젝트 검토 |
| `architecture/` | **모듈 횡단** 설계 — 공통 ERD, 상태·권한·트랜잭션, 전체 업무 흐름, 시드 |
| `architecture/erd/` | 모듈별 관계도 (HTML 탐색기 + Mermaid 원본) |
| `modules/` | **모듈별** 설계 — core / mes / erp / fems / learning / qms / wms / bems |
| `db/` | 메타데이터 기준본, Excel 설계서, 검증 보고서 |
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

## 현재 모듈 상태

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
