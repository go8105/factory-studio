# C++ 웹 호출 연결·사용자 참고 문서 — FS-VISION-CONNECT01

## 구현 완료 범위

- 검사실 레시피 설정 아래 C++ 단건 검사 및 네이티브 결과 JSON.
- 연속 검사에서 브라우저/C++ 엔진 선택. 배치 중 엔진 변경 차단, 레시피 스냅샷과 요청 ID 유지.
- 가상 PLC가 선택한 엔진을 호출. 완료 확인 후 집계, 타임아웃/종료 후 늦은 응답 폐기와 HTTP abort.
- 인증·CSRF API `POST /api/v1/factory/vision/inspect`, 고정 경로 C++ subprocess 호출.
- 도움말 사용자 참고 문서 → 포털 → 합성 비전 검사실 · 연속 검사 · PLC · C++. `/help/portal/vision-lab`. 검사실 도움말 링크·문서의 검사실 진입 링크·검색/트리 포함.

## 사용 흐름

3D 공장 → 비전검사 설비 → 합성 이미지 검사실 → 조건 설정 → 브라우저 결과 확인 → C++ 단건 검사로 비교 → 연속 검사에서 엔진 선택 → 필요하면 가상 PLC 사용 → 20회 배치 → NG 이력·정답 오류 확인 → JSON 보관.

C++ 실행 경로: 웹 요청(요청 ID·샘플·레시피) → 인증/CSRF 검사 → 동시 실행 슬롯 → 서버 고정 실행 파일의 --timed → OpenCV 검사 → JSON 모델 검증 → 요청 ID 확인 → UI 결과 표시. PLC 모드에서는 앞뒤로 Trigger/Busy, Done/결과 확인 단계가 붙음.

단건 C++ 실패와 배치 실패를 브라우저 결과로 대체하지 않음. 브라우저 기본 모드는 계속 사용 가능. 합성 검사 기록은 메모리에만 보관, MES·DB 쓰기 없음. 3D 시나리오 누계·AI 설명은 별도 합성 데이터이며 이번 결과로 자동 갱신되지 않음.

## 운영 배포 인계 — 사용자가 직접 진행

이번 작업은 로컬 커밋만 수행한다. 원격 push, main 통합, 운영 서버 접속·설정·재시작·배포는 실행하지 않았다.

1. 배포할 소스에 합성 검사실부터 이번 호출 연결까지의 커밋과 도움말을 함께 반영한다. 코드 위치는 factory-studio-codex의 codex/vision-ai 브랜치다.
2. **운영 서버 OS/아키텍처에서** 네이티브 바이너리를 빌드한다. 이 Mac의 arm64 실행 파일을 Linux 서버로 복사하지 않는다. C++17 컴파일러·CMake 3.24+·Node24 준비 후 저장소 루트에서:

```sh
cmake -S native/inspection_core -B work/inspection-core \
  -DINSPECTION_FETCH_DEPS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build work/inspection-core --parallel 4
ctest --test-dir work/inspection-core --output-on-failure
work/inspection-core/bin/inspection_core native/inspection_core/examples/foreign.json
work/inspection-core/bin/inspection_core --timed < native/inspection_core/examples/foreign.json
```

3. API 서비스 환경에 `VISION_CORE_EXECUTABLE`을 위 실행 파일의 **절대 경로**로 지정하고 서비스 실행 계정의 실행 권한을 확인한다. `.env.example`에 설정 설명을 추가했다. C++ 바이너리가 포함되지 않는 Python wheel만 교체해서는 엔진이 준비되지 않는다. work/는 Git에 없으므로 서버마다 빌드하거나 별도 배포 아티팩트로 관리해야 한다.
4. 백엔드 코드와 실행 환경을 반영하고 API 서비스를 재시작한다. 도움말 Markdown은 프런트 번들에 포함되므로 프런트도 다시 빌드·반영한다.
5. 정상 게스트 세션에서 C++ 단건 이물 결과(NG, 80·36px²), C++ 20회 배치(OK10/NG10), 가상 PLC·리셋·JSON·도움말 링크를 확인한다.

서버 바이너리 미설정은 503, 처리 중인 네이티브 요청이 프로세스당 4개면 429, 엔진/출력 문제는 502, 2초 초과는 504. 브라우저 제한은 3초, PLC 검사 제한은 300ms. 네트워크/기동 지연이 커지면 PLC 타임아웃이 날 수 있으며 실제 장비 처리 성능을 의미하지 않는다. 브라우저 취소 시 서버 작업은 즉시 멈추지 않을 수 있지만 서버 제한 시간 내 정리된다.

**backend/tests/factory_native_preview.py는 로컬 E2E 전용 모의 인증 서버다. 운영 진입점으로 사용하지 않는다.** 운영은 기존 fs.main:app과 기존 인증/CSRF를 사용한다.

## 로컬 재현과 검증

```sh
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
npm --prefix frontend test -- --maxWorkers=2
backend/.venv/bin/pytest backend/tests/test_factory_native.py backend/tests/test_factory_explanation.py -q
backend/.venv/bin/ruff check backend/src/fs/factory backend/tests/test_factory_native.py backend/tests/factory_native_preview.py
VISION_NATIVE_E2E=1 npm --prefix frontend run test:factory-browser -- --grep '합성 검사실|연속 검사|가상 PLC|C\+\+ 실제'
```

로컬 실제 C++ 통합 테스트는 5186(Vite)·5187(모의 인증, 실제 API·실제 C++ 바이너리)을 사용한다. 공용 DB 스모크·운영 세션·Windows/Linux·실장비 검증은 별도다. 최종 결과는 HANDOFF 최신 FS-VISION-CONNECT01 기록을 참조한다.


## 2026-09-27 C++ 웹 호출·사용자 참고 문서 (FS-VISION-CONNECT01 완료)

- 사용자 요청한 C++ 호출 연결과 도움말 반영 완료. `codex/vision-ai`, 기준 `848778b`. 운영 배포는 사용자가 직접 진행하며 이번에 push·main 통합·운영 접속/재시작/배포 없음.
- 인증/CSRF POST /api/v1/factory/vision/inspect, 서버 고정 절대경로 VISION_CORE_EXECUTABLE 실행. 2초·동시4개/프로세스·출력1MiB 제한, 요청/결과 모델 검증, 오류503/429/502/504, 브라우저 대체 없음. C++ --timed 추가(기본 CLI 출력 유지).
- 검사실 C++ 단건/JSON, 연속 검사 엔진 선택, PLC 선택 엔진 호출·취소. 엔진 출처·고정 레시피·요청 ID 연결, 순수 C++ 시간 표시. 클라이언트 취소/늦은 응답 폐기.
- 도움말 사용자 참고 문서/포털에 `portal/vision-lab` 추가, 전체 사용 흐름·설정·20회 배치·PLC 장애/복구·JSON·한계 집필. 검사실 왕복 링크·검색·모바일 확인.
- 최종 검증: 프런트 448 tests/50 files, 타입(빌드)/lint/format/build 통과. DB 없는 서버 27 tests(실제 C++·인증/CSRF·검증·미설정·출력오류/상한·시간제한·동시제한·취소) 통과, Ruff check/format 통과. CTest2개 통과, 웹 비교19,968개 불일치0.
- Chromium 관련6개 최종 단일 실행 통과(1.3분). 모의 인증·실제 API·실제 C++ 바이너리로 단건/20회/PLC20회 및 JSON·도움말 확인. 기존 모의 API 회귀 포함. 실제 화면 캡처 확인, 도움말390px 가로 넘침 없음.
- 공용 DB/운영인증/운영배포·Windows/Linux·실장비 미검증. 기존 3D 청크/Clock 경고와 Python 테스트 클라이언트 사용중단 경고 유지.
- 배포 인계: `docs/agent/C++웹연결_FS-VISION-CONNECT01.md`. 서버 OS에서 바이너리 빌드/검증 → 서비스 환경 VISION_CORE_EXECUTABLE 절대경로 설정 → 백엔드 반영·재시작 → 프런트 재빌드·반영 → 게스트C++/PLC/도움말 확인. tests/factory_native_preview.py는 모의 인증이므로 운영 사용 금지.
