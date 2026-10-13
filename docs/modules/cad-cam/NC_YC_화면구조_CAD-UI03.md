# CAD-UI03 NC·YC Figma 화면 구조 시안 (2026-10-13)

사용자가 NC 우선 시안→공통 구조→CAD/CAM 확장 방향을 확인했다. 이번 ID는 Figma 검토 시안·설계 기록만이며 제품 코드/DB/배포 변경은 없다. 전체 시안 확인 전 제품 적용을 시작하지 않는다.

## 결과
- [Figma Design](https://www.figma.com/design/Z9reC31WUdfLMhfC02VM2m?node-id=6-532): 황경호의 팀 유일 계획을 사용하여 생성.
- 1440×960, 5개 상태/7개 화면: 입력 전6:532, 준비6:595, YC대기6:663, 비교6:733, 3번재생6:845, 1번6:915, 2번6:985.
- 왼쪽220px 준비 단계, 중앙860px 작업 영역, 오른쪽280px 속성/YC. 헤더·문서 도구·하단 고정 재생·범위 안내. 준비 상태와 상세 설정을 분리하는 구조.
- 공통5가족/17variants: Button3, Step4, Field2, YC5, Proposal3. 20변수(원색·별칭·간격·반경), 공통텍스트스타일3. 화면113instance, 수정 전 총35개 실제navigation 반응. 시작화면 지정. 마지막 초기요청 제거 후34개 예상이며 최종 반응 재집계는 도구한도로 미실행.
- 기존 웹은 Arial/Noto Sans KR/sans-serif. Figma Arial미제공, 기존 한글 대체글꼴 Noto Sans KR Regular/Medium/Bold 사용. 백자/먹색/쪽빛 유지, 장식그림자 없음.
- 제안시간523.7/823.7/233.7초는 기존 합성예제 검증을 기준으로 표시. 경로는 편집 가능한 SVG 도식으로 명시했으며 실제 STEP/NC 렌더링이 아니다. kWh는 임의 숫자를 넣지 않고 실제 계산 범위와 연동하는 영역으로 설계했다. 실제 품질·안전/실측/장비동작 보증 없음.

## Figma 작업·검증
현재 제품 정적 빌드 복사본을 localhost5262에서 capture.js로 Figma 캡처했다. 기존 실행환경/제품 HTML에는 스크립트를 추가하지 않았다. 공통컴포넌트 search결과 없음→프로젝트 전용 foundation/instance 구성. 비교용 capture3:2는 최종화면에서 삭제하여 raw-frame 중복 제거. 구성용 컴포넌트는 검토 화면 바깥x4700으로 이동.
- 7화면 구조검사에서 패널 자식넘침0·Noto Sans KR 불일치0·navigation35 확인. 공식 Figma screenshot으로 다섯 상태를 캡처했고 입력 전/준비/YC/카드/3번확대 이미지 확인. normal상태의 항상표시오류는 삭제했다.
- 마지막 보정: Active Step 쪽빛, Complete 라벨에 완료 명시, 최초화면 미준비 제안 Disabled/반응 제거. 해당 mutation은 성공/ID반환. 이후 screenshot3개는 Starter MCP tool call limit으로 모두 거절됐다. **최종보정후 화면캡처/넘침/반응집계는 미검증**. 보관이미지는 바로 전 버전이라 마지막색상/완료라벨/초기버튼과 차이가 있다.
- 첫 foundation마무리 PAGE.x 오류, discovery출력20KiB초과, 자기화면NAVIGATE오류 발생. 실패mutation rollback 상태를 조회/반환범위 축소/자기이동제외로 보정하여 전체 작성 재성공. 오류를 숨기고 무검증 완료라 표시하지 않는다.
- assets/cad-ui03/figma-ledger.json에 file/node/component/variable/style ID, 초기구조검증. 스크린 PNG와 작성script도 보관. 짧은 수명의 asset URL은 기록하지 않는다.

## 범위·다음
시안의 클릭은 준비/음성 흐름 예시이며 실제 파일업로드·음성인식·가공재생이 아니다. 실제 제품의 기존 검증/Worker/취소/권한 경계를 보존해서 추후 이식한다. 이번실마이크/제품테스트/모바일시안/최종보정캡처/운영 적용 미실행. 데스크톱 NC부터 검토하며 CAD설계/CAM의 상세화면은 후속, 상단모드 표시는 공통셸 방향이다.
다음 사용자 Figma 시안 확인 및 도구사용 가능 시 최종보정 검증→전체디자인확인→제품UI 작업별도. 자동 개발/다른 ID 착수 없음. GitHub 결제 차단과 Figma Starter도구한도는 서로 다른 제한이다.

