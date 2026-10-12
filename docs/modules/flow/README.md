# Factory Flow — Work OS 독립 시스템

## 현재 도움말 기준 · 2026-10-12

현재 FLOW-03까지 구현·2026-10-11 제품2c30b42 운영 배포 완료. flow12표, 전체193표2102열471FK, head flow_board_custom. 독립 /work-os·행 편집·보관/복구·자유컬럼6종 구현. 날짜별 업무일지 FLOW-02b 미구현. 아래 FLOW-01/02a 수치와 FLOW-03 승인 대기 문장은 당시 설계 이력이다. [제품 도움말 구현 대조](../../agent/제품도움말_구현대조_HELP-01.md).

작업 ID: FLOW-01. 2026-10-10. 상태: **FLOW-02a 독립 진입·기존 보드 이관·새 UI 운영 배포 완료, 날짜별 업무일지 후속**.

사용자 요청: GW 프로젝트 보드를 독립 시스템으로 분리하고, 제공 React 코드·이미지를 기준으로 UI 개선 및 팀 업무일지를 추가한다. 2026-10-10 사용자가 앱 런처 진입·/work-os·기존 보드 분리 구현을 승인했다. 이번 FLOW-02a는 기존10표 이관/API/독립메뉴/UI색상에 한정한다. 날짜별 일지8표/신규권한은 후속 FLOW-02b이며 구현 완료로 표시하지 않는다.

- [전체 설계](Factory_Flow_독립시스템_업무일지_FLOW-01.md)
- [DB 명세 원본](flow-design.json)
- [모듈 ERD](flow-design.mmd)
- [DB 설계 Excel](Factory_Flow_DB_설계_FLOW-01.xlsx)
- [UI 검토 시제품](ui-preview.html)
- 기존 구현 기준: [GW 프로젝트 보드](../gw/GW_프로젝트업무보드_설계초안_GW-PROJECT-01.md)

구현 schema0.24.1/headflow_split: flow10표·gw19표, 전체191표2074컬럼464FK. flow-design.json/ERD/별도Excel은 후속8표를 포함한 전체 설계로 현재 구현 스키마와 구별한다.

구현 API /api/v1/flow, 기존 /api/v1/gw/projects alias 유지. 기존 gw.projects.* 멱등 operation namespace는 예전 요청 재시도 보존을 위해 유지하며 데이터/엔티티 소유는 flow다. /work-os 진입은 보드목록으로 연결한다. 기존 GW URL query/hash·즐겨찾기 순서 보존. 실행 SQL이 적용된 migration은 수정하지 않는다.

운영 진입: [Factory Flow](https://eip.hugh-d.com/work-os). 제품31623b0 배포·10표 보존/DDL0 확인. [배포 검증](../../agent/Factory_Flow_독립시스템_배포검증_FLOW-02a.md).

## FLOW-03 간결 보드·총 관리자 관리

[전체 설계](Factory_Flow_간결보드_FLOW-03.md) · [검토 UI](ui-simple-board-preview.html) · [DB 명세](Factory_Flow_간결보드_DB명세.xlsx) · [ERD](flow-simple-board-design.mmd). 2026-10-11 전체 확인 대기. 신규 2표는 설계 후보이며 실제 제품 스키마에 적용하지 않았다.

최신 UI 기준(2026-10-11): [사용자 Figma 원본 스냅샷](figma-reference/README.md). 요약 카드·4보기·즐겨찾기/내보드·둥근 그룹 카드·하단 점선 새그룹 버튼 유지. 초기 사각표 시제품보다 FLOW-03의 Figma 기준 변경 절이 우선한다.
