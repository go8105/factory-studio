# FLOW-03 승인 이미지와 실제 제품 UI 차이 보정

사용자가 승인한 시제품(09:21 Figma 기준 검토 이미지)과 제품 daa1905 사이에 실제 차이가 있었다. 배포 누락이나 사용자 브라우저 캐시로 단정하지 않는다. 제품 CSS/상시 controls를 승인 이미지에 충분히 맞추지 못한 구현 차이를 이번 수정으로 보정한다.

제품 커밋: 27a3db0 (UI27d153b + 회사 미등록/게스트 공통 메뉴 유지 보정). 기존 제품 대비 DB/API/회사 등록 권한 변경 없음.

- Factory Flow 경로의 중복 Factory Studio 상단바 제거. 기존 전체 솔루션/사용자 관리/내 공간 진입 유지.
- breadcrumb·제목 즐겨찾기·공유, SVG 탭/검색/내업무/필터, 요약 카드 4개, 내보드+와 부가 설정 메뉴.
- 상시 보기 저장/새로고침·보관/생성 허용 controls는 메뉴로 정리. 기능 삭제 없음.
- 표 헤더 투명 버튼, 상태 저채도 배지(native select의 키보드/스크린리더·실제 저장 유지), 프로필·짧은 날짜·진행률·둥근 체크박스.
- 그룹 짧은 색 스트립·카운트·팝오버·하위 업무 연결선 및 간격.

검증: frontend590/75파일·집중5·타입/전체lint/build/범위format·diff 공백 통과. Playwright 실제 제품 코드에 합성 회원/7업무/3그룹 API 응답을 제공, 7/3/1/39% 실제 집계·런처→Flow·구주소 query보존·컬럼drawer/Escape·공유 설정 열기닫기·390px overflow0 확인. 추가 브라우저 검증: 회사 미등록 admin 사용자관리 진입·게스트 체험의 공통 메뉴 유지 통과. 운영 실제 계정/회사 생성·브라우저 확장 설정 변경 없음. 참조 Figma 파일 변경 없음.

제품 캡처: /Users/hwang-kyoungho/Documents/Codex/2026-10-09/gw/outputs/Factory_Flow_FLOW04_UI.png (별도 시제품 HTML이 아닌 실제 제품 실행; 합성 데이터).

정확 HEAD CI: [38102155660](https://github.com/go8105/factory-studio/actions/runs/38102155660) SUCCESS. backend1010/skip1·perf1·frontend590/75파일·tools133, 타입/lint/format/build·DDL 왕복 통과.
운영 배포: 2026-10-11 10:53 KST 제품27a3db0, tools/deploy.sh exit0·CI 우회 없음. 보호된 서버 백업 /srv/factory-studio/backups/20261011-flow-ui-27a3db0(DB dump·화면/비공개 자산·commit·12원장 digest) 검증. 기존 Flow12원장 건수/digest 동일·APIactive·DDL0·공개/원점200·최근2분5xx0. 보드/내업무/사용자관리 URL200·세션/관리역량/Flow 미로그인401. 공개 flow-DDOnyUuL.css HTTP200 및 flow-status-control/flow-board-list-heading/조건부 공통헤더 selector 확인.

운영 빌드 Chrome 검증: 운영 사이트의 실제 JS/CSS를 로드하고 API는 합성 회원/업무 응답으로 대체(실제 운영 쓰기 없음). 런처 진입·구주소 query보존·컬럼drawer/Escape·공유 열기닫기·390px overflow0·정확 팔레트 확인. 실제 계정 권한/회사 등록 쓰기 테스트를 의미하지 않는다. 운영 빌드 캡처 Factory_Flow_FLOW04_운영빌드_합성검증_UI.png를 직접 시각 확인했다. urllib 자산 조회403은 curl/Chrome 동일 공개 자산200으로 추가 비교했으며 원인은 단정하지 않는다.

최종 기록 커밋은 문서만이며 운영 제품27a3db0과 구분한다.
