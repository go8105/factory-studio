# 비전검사 AI 설명과 세 시나리오 — FS-3D-AI01

2026-09-27 · Codex · 기준 `origin/main 8851772` · `codex/vision-ai`.

## 변경

사용자 승인: 비전검사 설비의 AI 설명 버튼 + 정상/불합격 증가/정지 시나리오 3개.

- 기존 1인칭/조감도 설비 상세에 세 시나리오 버튼을 추가했다. 정상(50개 중 1개 불합격), 증가(5개 중 1개), 정지(검사·이송·링 조명 정지). 증가 상황에는 황색 상태등, 정지에는 적색 상태등을 표시한다.
- 시나리오 전환 시 현재 시연 누계는 초기화한다. 고정된 비교 구간(직전/최근 각 10분)은 현재 애니메이션 누계와 구분한다. 정지 구간의 50개는 정지 전 처리분을 포함한 합성 비교 자료이며 화면의 초기 누계가 아니다.
- 정상 2%→2%, 증가 2%→20%(+18%p), 정지 100개→50개/불합격률 2% 유지. 수치는 코드가 계산하고 원인 가능성과 확인 항목은 설명에서 구분한다.
- `AI 설명`은 현재 선택 시나리오의 비교 자료를 설명한다. 실제 카메라 이미지·업무 DB·센서값을 조회하지 않는다.
- 시나리오 변경이나 상세 닫기 시 이전 요청을 취소하고 응답을 폐기한다. 네트워크 오류 시 준비된 설명으로 대체하지만 출처를 표시한다. 인증 만료는 기존 세션 처리로 전달하고 권한 오류를 숨기지 않는다.

## 서버 연결

- POST `/api/v1/factory/vision/explanation`, JSON `{ "scenario": "normal" | "reject-rise" | "stopped" }`.
- 기존 세션/CSRF 필요. 자유 입력·다른 workspace ID·사용자 수치는 받지 않는다. 신규 DB 테이블/마이그레이션/업무 쓰기 없음.
- 응답 data: `scenario`, `mode`(ai/demo), `reason`, `model`, `evidence`, `narrative`(summary/hypotheses/checks).
- 서버 `OPENAI_API_KEY` 설정 시 `gpt-6-astra` Responses API 호출. 구조화 출력, `store:false`, 25초 제한, 최대 출력 1800토큰. 프런트 대기는 30초 제한.
- 키 미설정은 `demo/not_configured`. 공급자 오류·불완전 응답·형식 오류는 데모로 대체하며 공급자 오류 원문이나 키를 노출하지 않는다.
- 프로세스 수명 동안 공개 합성 자료의 성공 설명을 세 시나리오별 공유 캐시. 동시 외부 요청 1개, 실패 후 60초 대기. 키를 프런트/번들에 넣지 않는다. 여러 워커/재시작의 비용은 각각 발생할 수 있다.
- 기준 JSON은 `backend/src/fs/factory/scenarios.json` 한 곳. backend 패키지 리소스와 frontend 정적 import가 공유한다. Vite 개발 허용 경로에 해당 리소스 디렉터리만 추가했다.
- 외부 API SDK 등 새 의존성 없이 기존 FastAPI/Pydantic 및 Python 표준 HTTP 기능 사용.

## 운영 인계

통합 후 **백엔드 재시작과 프런트 재빌드가 모두 필요**하다. 기존 UI 작업 브랜치는 보존했고 이번 브랜치에 포함하지 않았다. 메인 폴더·Antigravity checkout은 수정하지 않았다.

실제 AI 응답을 사용하려면 배포 서버의 비밀 환경 설정에 `OPENAI_API_KEY`를 넣고 API를 재시작한다. 키를 채팅·프런트 환경변수·Git 파일에 붙이지 않는다. 키가 없으면 표시된 데모 모드로 동작한다.

검증 당시 개발 환경에는 키가 없어 **실제 OpenAI 호출·응답 품질·모델 계정 접근은 미검증**이다. API 요청 구성과 성공·오류·캐시·동시 클릭은 모의 공급자로 검증한다. 운영 활성화 후 세 시나리오의 실제 설명을 한 번씩 확인해야 한다.

## 검증 명령

Node 24 PATH, 전용 `factory-studio-codex`에서:

```sh
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
npm --prefix frontend test -- --maxWorkers=2
npm --prefix frontend run test:factory-browser
backend/.venv/bin/python -m pytest backend/tests/test_factory_explanation.py -q
backend/.venv/bin/ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
backend/.venv/bin/ruff format --check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
```

브라우저는 5186·모의 API, 서버 테스트는 DB 없이 auth/provider만 대체한다. 공용 8000/5173·DB 스모크는 실행하지 않는다. 통합 담당자의 공식 스모크는 별도다.

## 참고

- 설계: `docs/modules/factory/README.md`
- OpenAI 공식 문서: https://developers.openai.com/api/docs/guides/structured-outputs
- 실제 모델: https://developers.openai.com/api/docs/models/gpt-6-astra


### 최종 검증 (FS-3D-AI01)

- Node 24 typecheck/lint/format:check/build 통과, Vitest **420 passed / 46 files**.
- DB 없는 backend 설명 테스트 **13 passed**, Ruff check/format 통과. wheel에 `fs/factory/scenarios.json` 포함 확인.
- Chromium 기존 회귀 13개 통과. 신규 시나리오·모바일 2개는 최종 분리 실행 **2 passed**. 전체 실행에서는 한 테스트가 접힌 비교 자료의 중복 문구를 찾아 실패했으나, 보이는 설명 문구를 선택하도록 수정한 후 재검증했다. 총 15개 시나리오 검증, 최종 단일 전체 실행은 반복하지 않았다.
- 1440×900 1인칭 설명 화면과 390px 모바일 패널 캡처 직접 확인. 모바일 가로 넘침 없음. 빌드의 기존 3D 청크 크기 경고와 THREE.Clock 사용 중단 예정 경고는 남아 있다.
- 실제 모델 요청과 공용 DB 스모크는 실행하지 않았다. 작업 폴더 `factory-studio-codex`, 브랜치 `codex/vision-ai`. 결과물은 이번 완료 커밋에 포함되며 원격 push/배포는 하지 않았다.
