# Synthetic inspection core — C++ / OpenCV

합성 이미지 검사실의 요청 v1을 처리하는 독립 C++17 라이브러리와 콘솔 프로그램입니다. 원본 웹 검사 코드는 `frontend/src/factory/inspection.ts`입니다. 웹 검사실의 C++ 단건/연속/가상 PLC 모드는 인증 API를 통해 이 실행 파일을 호출합니다. 카메라·실영상·C# 연결은 후속 범위입니다.

## 빌드

C++17 컴파일러, CMake 3.24 이상, Node.js 24(웹 비교 테스트)가 필요합니다. 저장소 루트에서 실행합니다.

설치된 OpenCV 4(core/imgproc), nlohmann-json 3.12 이상을 사용:

```sh
cmake -S native/inspection_core -B work/inspection-core -DCMAKE_BUILD_TYPE=Release
cmake --build work/inspection-core --parallel 4
ctest --test-dir work/inspection-core --output-on-failure
```

라이브러리가 없으면 고정 버전 OpenCV 4.13.0 / nlohmann-json 3.12.0을 SHA-256 확인 후 소스 빌드합니다. 첫 configure에는 인터넷이 필요합니다. 설치·전역 경로 변경 없이 빌드 폴더에 의존성을 둡니다.

```sh
cmake -S native/inspection_core -B work/inspection-core \
  -DINSPECTION_FETCH_DEPS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build work/inspection-core --parallel 4
ctest --test-dir work/inspection-core --output-on-failure
```

Node 24가 PATH의 기본 버전이 아니면 `-DNODE_EXECUTABLE=/절대/경로/node`를 configure에 추가합니다. 다중 구성 생성기(Visual Studio 등)는 build에 `--config Release`, ctest에 `-C Release`를 사용하고 실행 파일 경로의 `Release/`를 확인해야 합니다. Windows 빌드는 이번 검증 환경에 포함되지 않았습니다.

생성 타깃: `inspection_engine` 정적 라이브러리, `inspection_core` CLI, `inspection_core_tests`. C++ 헤더의 `parseRequest` / `inspect`를 통해 UI·프로세스 입출력과 알고리즘이 분리됩니다.

## 실행

```sh
work/inspection-core/bin/inspection_core native/inspection_core/examples/foreign.json
work/inspection-core/bin/inspection_core < native/inspection_core/examples/foreign.json
work/inspection-core/bin/inspection_core --ndjson < requests.ndjson
```

입력(JSON 문서 또는 NDJSON 한 줄):

```json
{"version":1,"sample":"foreign","recipe":{"threshold":90,"minArea":20,"roi":"full"}}
```

검사실에서 받은 `{ "request": {...}, "result": {...} }` JSON도 그대로 읽습니다. 이 경우 과거 `result`는 무시하고 새로 검사합니다. 연속 배치 JSON은 여러 요청을 포함하므로 각 `records[].request`를 추출해야 합니다.

성공 출력:

```json
{"version":1,"source":"synthetic-opencv-cpp-v1","status":"NG","regions":[{"x":55,"y":40,"width":10,"height":8,"area":80},{"x":120,"y":65,"width":6,"height":6,"area":36}],"falsePixels":0,"missedPixels":0,"excludedPixels":0}
```

JSON 키 순서는 의미가 없습니다. 영역 순서는 웹과 동일한 행 우선 스캔 순서입니다. 성공 exit code는 0, 오류는 2이며 오류 응답도 stdout의 JSON입니다. 입력 원문·파일 내용·내부 예외를 오류 메시지에 노출하지 않습니다.

```json
{"version":1,"error":{"code":"INVALID_REQUEST"}}
```

오류 코드: INVALID_REQUEST, INPUT_TOO_LARGE, INPUT_OPEN_FAILED, INPUT_READ_FAILED, INVALID_ARGUMENTS, INSPECTION_FAILED. 문서 또는 NDJSON 한 줄당 최대 65,536바이트. 빈 입력/줄·잘못된 JSON·범위 밖 숫자·잘못된 타입을 거부합니다. 정수값인 `90.0`은 JavaScript와 같이 허용하지만 문자열 `"90"`·불리언은 거부합니다.

NDJSON은 각 응답을 즉시 flush합니다. 잘못된 줄은 오류 응답 후 다음 줄로 진행하며 최종 exit2를 반환합니다. 크기 초과는 입력 소비를 중단하고 exit2. 파일 모드는 단일 JSON만 허용합니다.

## 웹 API 연결

서버 환경에 `VISION_CORE_EXECUTABLE`을 서버용 실행 파일의 절대 경로로 설정합니다. API 프로세스의 계정에 실행 권한이 있어야 합니다. macOS에서 만든 바이너리를 Linux 서버에 복사하지 말고 대상 서버에서 빌드하세요.

`POST /api/v1/factory/vision/inspect`는 인증·CSRF 확인 후 고정 실행 파일을 `--timed` 모드로 호출합니다. 요청은 `{requestId, request}`, 응답 data는 `{requestId, result, inspectionMs}`입니다. `--timed`는 stdin의 단일 JSON을 받고 `{result,inspectionMs}`를 반환합니다. 기존 CLI 기본 모드·NDJSON 결과 계약은 유지합니다.

서버는 프로세스당 최대 4개 동시 실행, 2초 제한, stdout/stderr 각각 1MiB 상한과 응답 모델 검증을 적용합니다. 클라이언트 제한은 3초이며 PLC 모드는 별도의 300ms 제한이 더 먼저 적용될 수 있습니다. 브라우저 취소 후 서버 작업이 즉시 취소되지 않을 수 있지만 서버 제한 시간 내 종료되며 화면에서는 늦은 응답을 폐기합니다. 검사 알고리즘 시간은 C++ steady_clock으로 측정하며 프로세스 기동·네트워크 지연은 제외합니다.

실행 파일 미설정 503, 과부하 429, 엔진 실패/잘못된 출력 502, 시간 초과 504를 반환합니다. 자동 브라우저 대체는 없습니다. DB·MES 기록을 만들지 않습니다.

로컬 통합 브라우저 검증은 빌드 후 `VISION_NATIVE_E2E=1 npm --prefix frontend run test:factory-browser -- --grep 'C\+\+ 실제'`를 실행합니다. 이때만 5187의 `backend/tests/factory_native_preview.py`를 사용합니다. 이 테스트 서버는 인증을 가짜로 대체하므로 운영에 배포하면 안 됩니다. 실제 API 라우터는 기존 인증·CSRF를 필수로 검사합니다.

## 검사 의미

- 원본 160×100 회색조 합성 이미지. 기존 샘플 3종(normal/foreign/lighting)과 정답 마스크를 동일하게 생성합니다.
- `pixel < threshold`는 `cv::compare(..., CMP_LT)`. 일반적인 이진화 함수의 경계값 차이를 피합니다.
- `connectedComponentsWithStats`의 연결 4, CCL_SAUF를 명시합니다. SAUF는 행 우선 라벨 순서를 사용합니다.
- 면적은 `CC_STAT_AREA`(연결 픽셀 수), 검출 기준은 `area >= minArea`입니다. contourArea나 mm²가 아닙니다.
- 중앙 ROI는 (40,20,80,60). ROI 바깥 정답은 excludedPixels로만 계산합니다.
- source는 native 출처로 바꾸고 나머지 모든 결과 값·영역 순서를 웹과 비교합니다. 실제 영상에서는 정답 마스크가 없으므로 이 합성 평가 필드를 그대로 적용하면 안 됩니다.

공식 API 근거: [OpenCV 연결 영역 통계](https://docs.opencv.org/4.13.0/d3/dc0/group__imgproc__shape.html).

## 검증

CTest는 두 검증 프로그램을 실행합니다.

1. C++ 핵심 사례: 면적 80·36, 임계값 경계, 최소 면적 경계, ROI 제외, 조명 오검출, 정상 잡음, 전면 검출, 잘못된 요청.
2. `tests/parity.mjs`: 현재 TS `inspect`를 직접 import하여 3종 × ROI 2종 × 임계값 256개 × 최소 면적 경계 13개 = **19,968개** 입력을 네이티브 결과와 비교. 출처 표시만 정규화하고 좌표/면적/영역 순서/판정/세 픽셀 오류 수는 엄격 비교합니다. CLI 입력 오류·NDJSON 오류 후 다음 줄 처리·다운로드 wrapper·파일 오류도 검증합니다.

직접 비교 실행:

```sh
node native/inspection_core/tests/parity.mjs work/inspection-core/bin/inspection_core
```

OpenCV는 Apache-2.0, nlohmann-json은 MIT 라이선스입니다. FetchContent 원본에 각 라이선스가 포함되며 바이너리를 재배포할 때 고지 파일도 함께 제공해야 합니다. 이 저장소에는 제3자 소스/바이너리나 로컬 빌드 산출물을 커밋하지 않습니다.
