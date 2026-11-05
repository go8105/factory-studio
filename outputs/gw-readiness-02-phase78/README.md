# GW-READY-02 78차 — 통합 설계 계산 근거

2026-11-05. GW4c898ac/main783a2c1/공통2be292e의 고정 Git 스냅샷을 읽었다. DB·실계정·공급자에 접속하지 않았다. 제품/정식metadata·migration·Excel·ERD·다른checkout/WMS/main/push/배포 변경 없음.

- integration-plan.json: main순서+GW추가분의 설계 후보251표2833열617FK/1845레코드(196SERVICE정책), 목표390표4464열950FK. GW73제약/인덱스+19FK 이름변경,main이름변경0의 전체명세. 예정revision/두부모·정식헤더제안/입력SHA·초안지문·기존UK중복쌍·목표차이를 포함한다. applied/candidateDdlValidated/canonicalMetadataChanged=false다.
- guard-checks.json: 기준제약삭제/동시표수정/CASCADE/새중복FK/새물리중복의 거부5건과 기존UK쌍보존을 실제함수호출로 확인했다. DB접속없음.

초안 JSON은 무시되는work에만 생성하며review_only=true/migration_revision=null이다. 동일명령으로재생성할수있고같은입력의결과파일바이트동일을확인했다. 이출력은서명인수/DB검증/PASS근거가아니다. ready=false/최종4UNVERIFIED·실제복원PARTIAL/PASS거부를해제하지않는다.

[설계·재현·U0/UG/UM/실패·역순 검증 계약](../../docs/agent/GW_통합설계_승격검증_GW-READY-02_78.md)을따른다. 실제병합·revision생성·정식artifact재생성·DB승격/전체CI·실회사10인인수는미실행이다. 77차분할1600pass/1skip을이번실행으로표시하지않는다.
