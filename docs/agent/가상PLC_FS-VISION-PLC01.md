# 가상 PLC 핸드셰이크 — FS-VISION-PLC01

## 실행과 범위

3D 공장 → 비전검사 설비 → 합성 이미지 검사실 → 연속 검사 → **PLC 모드 사용** 체크 → 새 배치 시작.

기존 직접 실행 모드는 유지한다. 이번 구현은 브라우저 내부의 모의 신호 교환이며 실제 PLC·Serial·Ethernet·산업 프로토콜·안전 인터락·C++/C# 연결이 아니다. 서버·DB 변경, 새 의존성, 원격 push·운영 배포 없음.

## 프로토콜 synthetic-handshake-v1

| 상태 | Trigger | Ready | Busy | Done | 결과 | Interlock |
|---|---|---|---|---|---|---|
| 준비 | OFF | ON | OFF | OFF | OFF | OFF |
| 검사 중 | ON | OFF | ON | OFF | OFF | OFF |
| 결과 확인 대기 | ON | OFF | OFF | ON | OK 또는 NG | OFF |
| 검사 응답 오류 | ON | OFF | OFF | OFF | OFF | ON |
| 확인 응답 오류 | ON | OFF | OFF | ON | 마지막 판정 유지 | ON |
| 확인 성공 / 명시적 리셋 | OFF | ON | OFF | OFF | OFF | OFF |

- Vision_Ready_Req는 이 시뮬레이터에서 ON으로 고정한다. 별도 Ready 요청 제어/연결 협상은 없다.
- Recipe_ID=RUN_SNAPSHOT: 현재 배치 시작 시 고정한 사용자 레시피를 의미한다. PLC 숫자 주소나 1~3번 프리셋을 가장하지 않는다.
- Defect_Code는 DARK_REGION 또는 NONE. Alarm_Code는 INSPECTION_TIMEOUT / ACK_TIMEOUT / ENGINE_ERROR 또는 NONE. 조명 변화 샘플 이름으로 불량 원인을 분류하지 않는다.
- 완료 판정은 알고리즘에서 가져온다. OK와 NG는 동시에 켜지지 않는다. Busy/Ready 역시 상호 배타적이다.
- 검사 응답 제한 300ms, PLC 확인 제한 1000ms. 정상 표시 지연 80ms, 자동 확인 120ms. 시각화용 지연은 inspectionMs에 포함하지 않는다. 브라우저 스케줄링은 실시간 보장이 아니다.
- 다음 검사 지연 주입: 450ms 대기를 예약해 300ms 타임아웃 유발. 다음 결과 확인 누락: 자동 확인을 1회 생략. 예약은 시작되는 다음 거래에서 소비된다.
- 자동 확인 생략 시 제한 전 `PLC 결과 확인`으로 수동 완료할 수 있다. 중복 Trigger는 검사 중/확인 대기 중 새 검사로 수용하지 않는다.
- 오류 후에는 PLC 리셋이 필요하며 배치 자동 재개 없음. 새 배치로 재시작한다. 단순 종료는 오류 래치를 해제하지 않는다.

## 실행 기록과 수량

- `PlcHandshake.execute(request, inspectionId)`는 결과 확인 성공 후에만 기존 Engine Promise를 resolve한다. 요청 ID는 `runId:순번`이며 배치 기록과 이벤트 로그가 동일 ID를 사용한다.
- PLC 모드의 완료 수·OK/NG는 **확인까지 끝난 거래**만 포함한다. 검사 결과가 있어도 확인 실패한 거래는 수량에 포함하지 않는다. 상태와 전체 요청/결과는 `plc.inspection`에 남아 JSON에서 확인 가능하다.
- 마지막 검사 원본 요청·결과 스냅샷은 정상 확인 뒤에도 진단용으로 남으며 다음 검사/새 배치/리셋 때 교체된다. 결과 신호 비트는 확인 즉시 해제된다.
- 배치 JSON은 기존 실행 기록에 `plc` 확장 필드를 포함한다. version=1, protocol, 배치에서의 사용 여부, 현재 상태, 장애 예약, 마지막 검사, 최근 200개 이벤트와 각 신호 스냅샷 포함. 0건 실패 배치도 다운로드 가능하다.
- PLC 모드와 투입 간격은 운전/일시정지 중 변경할 수 없다. 일시정지·설정 이동·탭 숨김은 진행 거래를 마무리하고 다음 거래를 보류한다. 숨겨진 탭 지연에 따라 타임아웃이 생길 수 있으며 장비 지연으로 해석하지 않는다.
- 배치 종료/화면 이탈은 어댑터 cancel과 타이머 해제, 세대 토큰 무효화를 실행한다. 종료·타임아웃 후 늦은 결과는 무시한다.

## 구현 경계

- `frontend/src/factory/plcHandshake.ts`: 상태 머신·신호·지연/확인/오류·로그.
- `frontend/src/factory/PlcPanel.tsx`: 신호 표시와 주입/수동 확인/리셋.
- `inspectionRun.ts`: Engine에 inspectionId 전달, 취소 콜백 추가. 직접 검사 어댑터 export.
- `VisionRun.tsx`: 선택형 PLC 어댑터 연결 및 JSON 확장.

이 모델은 특정 PLC 제조사의 프로토콜 표준이 아니다. 향후 C# 통신 시뮬레이터와 연결할 때 주소·워드 타입·엔디언·접속/재접속·전송 확인·중복 ID 정책은 별도 계약이 필요하다. 다음 단계는 C++ OpenCV 코어에서 현재 4방향 연결 픽셀 면적/임계값 `<`/최소 면적 `≥`를 동일하게 구현하고 고정 입력 결과를 비교하는 작업이다.

## 재현

Node 24, factory-studio-codex:

```sh
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend test -- --maxWorkers=2
npm --prefix frontend run build
npm --prefix frontend run test:factory-browser -- --grep '가상 PLC|연속 검사|합성 검사실'
```

최종 검증 결과는 HANDOFF 최신 FS-VISION-PLC01 항목에 기록한다. Chromium 모의 API·5186 사용. 공용 DB 스모크·backend·Safari·실장비는 이번 프런트 변경에서 검증하지 않는다.


## 2026-09-27 가상 PLC 핸드셰이크 (FS-VISION-PLC01 완료)

- 사용자 후속 진행 승인. `codex/vision-ai`, 기준 `74a4ec2`. 연속 검사에 선택형 PLC 모드 추가, Ready/Trigger/Busy/Done/OK·NG/Interlock 신호, 요청 ID별 이벤트 로그.
- 300ms 검사 제한·1000ms 확인 제한, 1회 지연/확인 누락 주입, 수동 확인, 중복 트리거 차단, 결과 래치, 명시적 리셋·새 배치 복구. 타임아웃/취소 후 늦은 응답 무효화.
- PLC 수량은 확인까지 끝난 거래만 반영. 확인 실패 결과는 PLC 진단 스냅샷에 보존하고 NG 수량과 분리. 0건 실패 배치도 신호/알람/로그 JSON 다운로드 가능.
- Node 24 최종 typecheck(빌드 포함)/lint/format/build 통과. Vitest **443 tests / 49 files**. Chromium 관련 5개 통과, 로그 ID·알람 표시 보정 후 신규 PLC 2개 재실행 통과. 1440·390 캡처 직접 확인, 모바일 가로 넘침 없음.
- 브라우저 모의 프로토콜. Ready_Req ON 고정, Recipe_ID=RUN_SNAPSHOT. 실제 PLC·통신 SDK·C++/C#·MES·backend/DB 스모크·Safari 미검증. 기존 3D 청크/Clock 경고 유지. push·운영 배포 없음.
- 다음: 사용자 체험/통합 검토 후 C++ OpenCV 코어 분리 및 동일 입력의 결과 비교. 상세 `docs/agent/가상PLC_FS-VISION-PLC01.md`, 공통 설계 `docs/modules/factory/README.md`.
