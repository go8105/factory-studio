# C++ OpenCV 검사 코어 — FS-VISION-CORE01

기존 웹 검사와 같은 합성 영상 알고리즘을 독립 C++ 라이브러리/콘솔로 구현했습니다.

## 위치와 실행

저장소: /Users/hwang-kyoungho/Projects/factory-studio-codex
소스: native/inspection_core
실행 파일: work/inspection-core/bin/inspection_core

저장소 루트에서:

```sh
work/inspection-core/bin/inspection_core native/inspection_core/examples/foreign.json
ctest --test-dir work/inspection-core --output-on-failure
```

검사실에서 다운로드한 JSON 파일 경로를 첫 번째 인자로 전달해도 됩니다. `{request,result}` 중 request를 새로 검사합니다. 결과는 stdout, 성공 exit0/오류 exit2. `--ndjson`은 한 줄당 하나의 요청/응답을 처리합니다. 입력/줄 최대 64KiB.

## 결과

기본 이물: NG, 연결 영역 80·36px², 오검출 0·미검출 0·제외 0.
웹 비교: 3샘플 × 2 ROI × 256 임계값 × 13 최소 면적 = 19,968개. 출처 이름만 정규화하고 결과 전체를 엄격 비교해 불일치 0.

C++ API는 parseRequest와 inspect를 분리했고 CMake 정적 라이브러리로 제공합니다. 실제 웹 호출·카메라·C# 프로그램은 연결하지 않았습니다. 구현·정확한 JSON 계약·빌드 전제는 저장소 native/inspection_core/README.md에 있습니다.


## 2026-09-27 C++ OpenCV 검사 코어 (FS-VISION-CORE01 완료)

- 사용자 후속 진행 승인. `codex/vision-ai`, 기준 `7ec4519`. `native/inspection_core`에 C++17 정적 라이브러리·CLI·CMake·예제·비교 테스트 구현.
- 기존 요청 v1과 검사실 {request,result} JSON 입력, stdin/파일/NDJSON 지원. 결과 source=synthetic-opencv-cpp-v1. 임계값 `<`, 연결 4/SAUF, 픽셀 면적 `>=`, ROI·영역 순서·정답 평가를 웹과 일치시킴.
- CTest 2개 프로그램 통과(8.72초). 원본 TS 엔진 직접 실행과 19,968개 입력 비교: 불일치 0. C++ 핵심 사례, 입력 타입·범위·JSON 오류, NDJSON 오류 후 복구, 파일 입력 검증 통과. 예제 이물 결과 80/36px²·NG 확인.
- 검증 환경: macOS arm64, Apple Clang 21, CMake 4.4.3(Homebrew로 이번 설치), Node24, OpenCV4.13.0·nlohmann-json3.12.0 소스 빌드. 제3자 소스/빌드/로그는 work/에만 보관. CMake4와 OpenCV 내부 정책 경고는 남으나 최종 빌드·테스트 성공.
- 웹/서버/PLC 패널은 기존 브라우저 엔진 유지. 실행 연결·실영상·C#·Windows/Linux·실장비·배포 미검증/미구현. 프런트 코드를 바꾸지 않아 기존 443개 테스트/브라우저 스모크는 이번에 재실행하지 않음. push·운영 배포 없음.
- 다음: 사용자 체험 후 C# 프로세스/통신 어댑터 또는 웹 서버의 네이티브 호출 연결 범위 확정. 요청 ID·취소·시간 제한·출력 검증 계약 필요.
- 재현: `cmake -S native/inspection_core -B work/inspection-core -DINSPECTION_FETCH_DEPS=ON -DCMAKE_BUILD_TYPE=Release -DNODE_EXECUTABLE=/opt/homebrew/opt/node@24/bin/node`; `cmake --build work/inspection-core --parallel 4`; `ctest --test-dir work/inspection-core --output-on-failure`.
- 상세: `native/inspection_core/README.md`, `docs/agent/C++검사코어_FS-VISION-CORE01.md`.
