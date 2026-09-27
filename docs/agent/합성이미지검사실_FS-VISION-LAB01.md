# 합성 이미지 검사실 — FS-VISION-LAB01

사용자 승인: 합성 시나리오만. C++ OpenCV 검사 엔진, C# 장비 통신, 실장비는 후속.

## 체험

3D 공장 → 비전검사 설비 선택 → 합성 이미지 검사실 열기. 직접 경로 `/factory/vision-lab`도 기존 세션 인증 안에서 제공한다.

- 정상 / 이물 / 조명 변화의 결정론적 160×100 이미지. 정상에도 비결함 잡음 4픽셀이 있다.
- 전체/중앙 ROI, 이진화 임계값(픽셀 값 < 임계값), 최소 연결 면적(픽셀 수 ≥ 최소 면적).
- 4방향 연결 영역 검사. 기본 이물은 80px²·36px² 두 영역. minArea=100에서 둘 다 미검출. 조명 변화 threshold=130에서는 그림자 4000픽셀 오검출.
- 원본/이진화 전환, 검사 ROI·검출 상자, 영역 수·면적, 정답 마스크 대비 오검출/미검출/ROI 밖 결함 픽셀 수.
- 결과는 산업 정확도 지표·실측 치수·실장비 상태가 아니다. 합성 운전 시나리오 및 기존 AI 설명 API와 연결하지 않았다.
- 레시피·결과를 JSON으로 다운로드. 서버·MES·DB 저장, 사용자 이미지 업로드, 카메라 권한, 외부 호출 없음.

## 후속 엔진 연결 지점

`frontend/src/factory/inspection.ts`의 `InspectionRequest` / `InspectionResult` / `inspect`가 경계다. 요청 v1은 sample ID와 recipe, 결과 v1은 synthetic source와 판정·영역 좌표·검증 픽셀 수를 가진다. UI와 알고리즘은 분리되어 있다.

현재 동기 순수 함수를 나중에 비동기 원격 어댑터로 교체할 수 있다. 실제 영상 전달 시에는 이미지/프레임 ID, 원본 크기, 레시피 버전, 요청 ID, 타임스탬프·오류 계약을 추가하고 이전 응답 폐기·타임아웃 처리를 구현해야 한다. C++/C# 엔진이 지금 연결된 것은 아니다. 정답 없는 실영상에는 합성 평가 필드를 그대로 사용하지 않는다.

OpenCV contourArea는 이번 연결 픽셀 수와 다를 수 있으므로 결과 비교 시 면적 정의를 맞춰야 한다. px를 mm로 임의 변환하지 않는다.

## 재현

Node 24, `factory-studio-codex`에서:

```sh
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend test -- --maxWorkers=2
npm --prefix frontend run build
npm --prefix frontend run test:factory-browser -- --grep '합성 검사실'
```

브라우저 검증은 5186·모의 세션 API. 공용 backend/DB 스모크는 이번 프런트 전용 변경에서 사용하지 않는다. 기준 커밋 `0f16bb6`, 브랜치 `codex/vision-ai`; 이전 AI 설명 커밋에 이어 적용. push·운영 배포는 하지 않는다.


## 2026-09-27 합성 이미지 검사실 (FS-VISION-LAB01)

- 사용자 승인 범위 구현: 정상/이물/조명 변화 샘플, 전체/중앙 ROI, 임계값·최소 연결 면적 조절, 원본/이진화 화면과 검출 영역, OK/NG 및 오검출·미검출·영역 밖 결함 픽셀 수. 레시피·결과 JSON 다운로드.
- `/factory/vision-lab`, 비전검사 설비 상세에서 진입. 브라우저 순수 함수의 요청/결과 v1 계약 분리. OpenCV·C++·C#·실장비·AI 분석은 연결하지 않음. 새 서버·DB·의존성 없음.
- `codex/vision-ai`, 기준 `0f16bb6`에 후속 구현. 프런트 425 tests / 47 files 통과, typecheck/lint/format/build 통과. 모의 API·5186에서 신규 Chromium 진입/조건 변경/JSON 다운로드/모바일 가로 넘침 검사 통과. 공용 DB 스모크·실장비·Safari 미검증.
- 상세 설계·후속 연결 계약·재현 명령: `docs/agent/합성이미지검사실_FS-VISION-LAB01.md`. 이번 합성 범위 완료. 다음은 통합 검토와 사용자 체험이며 C++/C# 엔진은 별도 후속 범위. 원격 push·운영 배포 없음.
