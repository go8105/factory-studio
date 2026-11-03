# GW-READY-02 77차 — 현재 브랜치 분할 회귀와 main 읽기 검토

2026-11-03, 시작fceb68f. 제품 소스와 적용 migration은 바꾸지 않고 검사2곳/안전 실행기/문서만 변경했다. 실제 계정·preview DB/브라우저·다른checkout/WMS/main·원격push/배포 변경 없음.

- segmented-review.json: 현재 수집1601 고유 node ID와 전체 재실행/후속 실행을 대조한1600pass/1skip·누락0. **분할 결과이며 보정 후 단일 전체 실행 통과가 아니다.** DB fixture299pass/1skip·DB fixture 없는1301pass. DB 중 소유 백업 fixture46pass는 중복 범주다.
- initial-run.json: 첫 전체 선택949pass/1fail/1skip에서중단. Flow전체체인 역적용의 정상 보안이력 보호 거부. 적용 migration을 바꾸지 않고 Flow 함수 왕복/전체체인거부·이력보존 검사를 보정했다.
- focused-flow.json: 보정 집중1pass. 반복 합산하지 않는다.
- full-rerun.json: 전체 재실행1494pass/1fail/1skip에서중단. GW/WMS 정규화 검사에 고정 옛head 기대값이 있어 현재head/왕복전후유지로 보정했다.
- remaining-run.json: 수정 모듈/실패·미실행·skip107건을 새DB에서 실행해106pass/1skip. 두 실패는 보정 뒤 통과했으며 최종 고유case에서 미해결 실패0이다. 전체 순서/단일프로세스·통합소스/전체CI 검증을 대신하지 않는다.
- collection-scope.json: fixture 기준 수집 분류. 별도 인수 증거가 아니다.
- ddl-review.json: 새DB에 현브랜치 migration을 적용한219표2409열543FK 실제 카탈로그 대조 오류0. SERVICE/DB_POLICY172개는 DB제약으로 세지 않는다.
- owner-rejection.json/resources.json: 잘못된owner 거부와 소유자/loopback 재검증·생성 원본4DB삭제/preview DB존재 확인. preview업무 행을 읽거나 변경하지 않았다. 각 실행의 예상밖새DB0. full logs/JUnit/접속정보는 Git제외 work에만 보관한다.
- main-review.json: 조회/재조회 main783a2c1, 시작GW85/main90커밋 분기와 양쪽변경15경로, 읽기3-way텍스트8파일14구간/Excel1충돌. 실제 병합/index/브랜치 변경 없음. 합집합 migration heads는 gw_readiness/fems1이다.
- current-merge-review.json:77차 GW/WMS 검사 보정까지 포함한 원본/기준/main 복사본을 git merge-file -p로 재대조했다. 현재16경로, 텍스트9파일15구간/Excel1충돌이다. 실제 소스/index/브랜치를 병합하지 않았다.

skip1은 구형10인폐쇄복원 검사의 PG_TEST_CONTAINER/전용이름 규칙 미설정이다. 최신백업fixture나 과거성공으로 대체하지 않는다. 이 unsigned 보고서를 실제 인수/전경로·전체회수·외부독립성/실회사10인 PASS로 사용할 수 없다. ready=false/최종4UNVERIFIED·실제복원PARTIAL/ACCEPTANCE PASS거부 유지.

재현과 남은 통합 설계/승격 검증 범위는 [상세 문서](../../docs/agent/GW_통합회귀_main차이_GW-READY-02_77.md)를 따른다. 보정 후 단일 전체 실행과 통합 main/기존main DB승격·전체CI·실API브라우저/실인증·실기기/실회사 인수는 남아 있다.
