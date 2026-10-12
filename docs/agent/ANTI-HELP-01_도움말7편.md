# ANTI-HELP-01 — 빠진 화면 도움말 7편

> antigravity용 프롬프트. 공통 규칙·폴더 지도는 [ANTIGRAVITY_인계.md](ANTIGRAVITY_인계.md).

Factory Studio 저장소에서 ANTI-HELP-01을 개발한다.
`/Users/hwang-kyoungho/projects/factory-studio`

## 0. 읽을 것 (폴더로 찾는다. 추측 금지)

- `AGENTS.md` — 작업 규칙 전부
- `docs/agent/ANTIGRAVITY_인계.md` — §3 공통 규칙·§4 마무리. **그대로 지킨다**
- `content/help/` — **이미 있는 도움말 아무거나 서너 개**를 열어 형식·말투·길이를 그대로 따라한다. 이게 유일한 형식 기준이다
- `docs/modules/mes/`·`docs/modules/hr/` — 그 화면이 **무엇을 하는 화면인지**. `*_보강설계_DSN-12.md`(MES), `*_DSN-30.md`(HR)의 화면 목록 장
- `frontend/src/mes/`·`frontend/src/hr/` — 실제 화면 코드. **화면에 진짜 있는 버튼·칸만** 도움말에 쓴다
- `backend/seed/` — 체험 순서에 쓸 예시 데이터가 실제로 들어 있는지

## 1. 범위

`content/help/<솔루션>/<화면id 소문자>.md` 7개를 만든다. 지금은 파일이 없어서 화면의 "? 도움말"이 NotFound를 띄운다.

| 파일 | 화면 | 경로 |
|---|---|---|
| `content/help/mes/m-16.md` | M-16 불량·사유 코드 | `/mes/codes` |
| `content/help/mes/m-17.md` | M-17 작업자·근무조 | `/mes/workers` |
| `content/help/mes/m-19.md` | M-19 라벨 양식 | `/mes/labels` |
| `content/help/mes/m-26.md` | M-26 공정 검사 기준 | `/mes/inspection-items` |
| `content/help/hr/h-16.md` | H-16 내 근무 | `/hr/work` |
| `content/help/hr/h-17.md` | H-17 근무 체험 | `/hr/work-demo` |
| `content/help/hr/h-18.md` | H-18 사용자 관리 | `/hr/users` |

### 범위에서 뺀다

- 코드·DB·테스트 변경 없음. **`content/help/` 아래 7개 파일만 새로 만든다.**
- 이미 있는 도움말은 고치지 않는다.
- 흐름 맵(`content/flow-map.json`)은 건드리지 않는다.

## 2. 단계 (하나씩 끝내고 보고, 확인 전 다음 단계 금지)

| ID | 내용 |
|---|---|
| HELP-1 | MES 4편(m-16·17·19·26) |
| HELP-2 | HR 3편(h-16·17·18) |

## 3. 이 작업에서 특히 조심할 것

- **화면에 없는 기능을 쓰지 않는다.** 설계서에 적혀 있어도 아직 안 만든 것이 있다. 반드시 `frontend/src/<솔루션>/` 코드를 열어 버튼 이름·칸 이름을 그대로 베낀다.
- **파일 이름은 화면 id 소문자**(`m-16.md`). 화면 코드의 `help: "mes/m-16"` 값과 정확히 맞아야 열린다. 만든 뒤 브라우저로 "? 도움말"을 눌러 7개가 전부 뜨는지 본다.
- M-16은 한 화면 안에 **불량 코드·사유 코드 탭 두 개**다. 한 파일에 둘 다 설명한다.
- H-17 근무 체험은 체험용 화면이다 — 실제 근태와 무엇이 다른지 한 줄로 분명히 적는다.
- 사용자 대상 텍스트는 전부 한글. 실제 회사·고객 이름을 쓰지 않는다(합성 예시만).

## 4. 공통 규칙

→ `docs/agent/ANTIGRAVITY_인계.md` §3

## 5. 끝낼 때

→ `docs/agent/ANTIGRAVITY_인계.md` §4
