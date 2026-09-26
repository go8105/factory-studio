# 3D 공장 — Blender 비전검사 설비 1대

2026-09-26 · Codex · `codex/factory-vision-blender`

## 승인·범위

사용자: 참고자료 없이 즉시 진행. 기존 공장에 비전검사 모델 1대, 검사 동작·상태등·클릭 패널·MES 진입을 적용한다. 기존 3인칭 이동과 층 전환 유지. 업무 API·DB·실제 설비 연동은 변경하지 않는다.

## 결과

- 직접 제작한 카메라·렌즈·링 조명·컨베이어·프레임·후면 안전 패널·제어판·비상 버튼·3색 경광등. 전면은 내부가 보이는 개방형 시연 모형이며 실제 안전 설계가 아니다.
- `assets/blender/vision-cell.blend`: 편집 원본. `frontend/public/models/vision-cell.glb`: 약 265 KiB의 웹 모델. 외부 에셋·텍스처 없음.
- `tools/blender/build_vision.py`: Blender 5.2.2 LTS에서 재생성. 웹 좌표를 Blender 좌표로 변환하고 glTF Y-up으로 내보냄. 기존 설비 충돌 영역 안에 배치.
- 6초 주기 투입→검사→판정→배출. 5번째 제품마다 불합격. 시연 시간 한 곳에서 위치·조명·판정·수량을 계산. 일시정지·이상 정지 시 검사 시간이 멈춘다.
- 모델 선택/기존 공정 버튼으로 상세 패널. 가까이 보기, 이상 시연/해제, 검사·불합격 수량. MES 버튼은 `/mes` 대시보드 진입이며 특정 설비/작업지시 연동이 아니다.
- FEMS, PLC, MQTT, DB, 업무 레코드 쓰기 없음. 기존 reduced-motion 및 전체 오류 안내 유지. 모델 로딩 실패는 기존 3D 오류 경계가 안내한다.
- 새 npm 의존성 없음. MCP 없이 설치된 Blender의 background Python으로 제작했다.

## 재생성

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --python tools/blender/build_vision.py
```

저장된 원본의 수동 수정은 위 스크립트 재실행 시 덮어써지므로 별도 이름으로 보존한다.

## 검증

Node 24.21.0 · Blender 5.2.2 LTS. frontend typecheck, lint, format:check, build, test 각각 exit 0. 단위/화면 테스트 345개 통과. `test:factory-browser` 독립 Chromium 8개 통과(API 모의, 5186).

새 검증: GLB 서명·HTTP 로드, 검사 수량 증가, 이상 정지와 재개, 일시정지, MES 링크, 상세 패널 열린 360px 가로 넘침 없음. 검사 시 중앙 정지와 판정 시 수량 집계·5번째 불합격 규칙 단위 검증. 데스크톱/360px 스크린샷 직접 확인.

초기 내보내기에서 한국어 노드 이름 문제 발생 → BSDF 노드 타입으로 조회하도록 수정 후 성공. Three.Clock deprecation 및 기존 3D 청크 크기 경고는 남음. backend·DB·공용 통합 스모크·Safari·실기기 성능 측정은 미실행. 60fps를 보장하지 않는다.

다음: 사용자 시각 피드백 및 통합 담당자의 main 통합. 실제 MES 설비 연결/FEMS 조회는 별도 설계 대상. main 병합·push 없음.
