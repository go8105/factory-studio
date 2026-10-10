# GW·즐겨찾기 main 병합·운영 배포 결과

2026-10-10 KST. 사용자 요청에 따라 로컬 main과 origin/main에 병합하고 정식 tools/deploy.sh로 운영 반영했다.

- 제품 배포 커밋: `31af09603a769854fdb45e3902fffb41fc809774`.
- 운영: https://eip.hugh-d.com
- 해당 배포 커밋 CI: https://github.com/go8105/factory-studio/actions/runs/38006224353 — success.
- CI 백엔드 983 통과/1 skip, 독립 성능 1 통과, 프런트 575 통과, 도구 133 통과. 타입/lint/format/build, 마이그레이션 rollback/reapply 및 DDL 대조 통과.
- 운영 main fast-forward, DB head `w0_fav_menu_shape`, 새 합성 템플릿 `sv-20261009-gw1` 생성. 기존 사용자 공간과 데이터는 초기화하지 않았다.
- 배포 직후 원점/공개 HTTP 200, DDL 대조 오류 0, 최근 2분 5xx 0.
- 운영 API 14개 검사 통과: 즐겨찾기 조회·8개 저장·재조회·멱등 재전송, GW/MES/ERP 대시보드·조직 10명·게시판·일정·알림·채팅. 합성 검증 세션 종료 확인.
- 실제 Chrome에서 메뉴 6개→MES 작업지시 추가→7개 저장→새로고침 유지, MES 사이드바 등록된 대시보드/작업지시만 표시 확인.
- 서버 백업 `/srv/factory-studio/backups/20261010-gw-favorites-31af096`: DB dump와 화면/비공개 자산 압축 보관, 전체 읽기 및 gzip 검사 통과. 백업 내용과 환경변수는 외부 전달/커밋하지 않았다.

로컬 500 오류도 해결했다. 로컬 DB가 이전 `w2a1_mes`에 머물러 신규 즐겨찾기 테이블이 없었다. 로컬 DB를 백업하고 `upgrade head` 적용했다. 기존 사용자 공간 7·세대 7 유지, `/api/v1/core/workspace/menus` 200과 기본 6개 표시·편집 진입 확인. 로컬 API/프런트는 8000/5173으로 기동했다.

이 결과를 기록하는 후속 커밋은 문서 전용이다. 운영 제품 릴리스는 위 31af096이다.
