# 연속 검사 모드 — FS-VISION-RUN01

## 범위와 실행

3D 공장 → 비전검사 설비 → 합성 이미지 검사실 → 연속 검사.
기존 레시피 설정 후 새 배치를 시작한다. 정상/이물/정상/조명 변화 순으로 5회, 총 20회. 기본 500ms, 선택 200ms. 동일한 기존 3종 반복이며 서로 다른 20장 이미지가 아니다.

- 시작 시 레시피·간격 고정, 다음 배치에서 설정 변경 반영.
- 일시정지는 진행 중 결과까지 수용하고 다음 투입 보류. 설정 모드 이동·탭 숨김도 일시정지, 수동 재개.
- 종료/화면 이탈/새 배치는 generation으로 오래된 응답 폐기. 단일 진행 검사만 허용. 느린 처리 후 밀린 타이머 몰아 실행 없음.
- 새 배치는 이전 기록 교체. 화면 이탈/새로고침 시 기록 소멸. JSON 다운로드로 보존 가능.
- NG 선택은 당시 요청/결과를 표시. 원본/이진화·검출 좌표·영역별 면적·최소 면적 비교·검사 시각·처리 ms.
- 기본 레시피는 20 완료, OK 10/NG 10. minArea=100은 OK 20/NG 0이지만 미검출 누적 1160px. 합격률은 품질 정확도나 생산 수율이 아니다.
- 샘플별 NG 집계는 원인 분류가 아니다. 조명 변화 샘플에도 이물 2개 포함.

## 연결 경계

`inspection.ts`의 요청/결과 v1은 유지. `inspectionRun.ts`의 실행 기록 v1이 runId, inspectionId, 순번, 시작/완료 ISO 시각, 알고리즘 처리 ms, 요청/결과를 감싼다. `VisionRun.tsx`는 구독으로 표시, `InspectionView.tsx`는 설정/이력 화면 공통 렌더러.

기본 어댑터는 기존 inspect 함수 전후 performance.now()만 측정한다. 대기/렌더링 제외. 미래 비동기 엔진 어댑터는 엔진에서 측정한 시간을 반환해야 한다. 타임아웃/PLC handshake/실장비/C++/C#/MES 저장은 이번 범위 아님. 오류는 NG로 집계하지 않고 별도 오류 상태로 멈춘다. PNG 영구 저장이나 실제 영상 전송은 구현하지 않았다.

## 검증

Node 24, factory-studio-codex:

```sh
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend test -- --maxWorkers=2
npm --prefix frontend run build
npm --prefix frontend run test:factory-browser -- --grep '합성 검사실|연속 검사'
```

431 tests / 48 files 통과. typecheck/lint/format/build 통과. Chromium 모의 API·5186 사용. 기존 합성 검사실 회귀와 신규 배치/이력/JSON 테스트 통과. 설정 이동 일시정지·종료·화면 이탈 초기화 브라우저 테스트도 통과. 최종 신규 2개 재실행 통과. 1440·390 캡처 직접 확인, 360·390 가로 넘침 없음.

backend/DB/공용 스모크·Safari·실장비 미검증. 기존 3D 청크 크기 경고와 THREE.Clock 경고 유지. 원격 push·운영 배포 없음.
