# Factory Flow — Work OS 독립 시스템

작업 ID: FLOW-01. 2026-10-10. 상태: **FLOW-02a 독립 진입·기존 보드 이관 구현, 날짜별 업무일지 후속**.

사용자 요청: GW 프로젝트 보드를 독립 시스템으로 분리하고, 제공 React 코드·이미지를 기준으로 UI 개선 및 팀 업무일지를 추가한다. 2026-10-10 사용자가 앱 런처 진입·/work-os·기존 보드 분리 구현을 승인했다. 이번 FLOW-02a는 기존10표 이관/API/독립메뉴/UI색상에 한정한다. 날짜별 일지8표/신규권한은 후속 FLOW-02b이며 구현 완료로 표시하지 않는다.

- [전체 설계](Factory_Flow_독립시스템_업무일지_FLOW-01.md)
- [DB 명세 원본](flow-design.json)
- [모듈 ERD](flow-design.mmd)
- [DB 설계 Excel](Factory_Flow_DB_설계_FLOW-01.xlsx)
- [UI 검토 시제품](ui-preview.html)
- 기존 구현 기준: [GW 프로젝트 보드](../gw/GW_프로젝트업무보드_설계초안_GW-PROJECT-01.md)

구현 schema0.24.1/headflow_split: flow10표·gw19표, 전체191표2074컬럼464FK. flow-design.json/ERD/별도Excel은 후속8표를 포함한 전체 설계로 현재 구현 스키마와 구별한다.

구현 API /api/v1/flow, 기존 /api/v1/gw/projects alias 유지. 기존 gw.projects.* 멱등 operation namespace는 예전 요청 재시도 보존을 위해 유지하며 데이터/엔티티 소유는 flow다. /work-os 진입은 보드목록으로 연결한다. 기존 GW URL query/hash·즐겨찾기 순서 보존. 실행 SQL이 적용된 migration은 수정하지 않는다.
