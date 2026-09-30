# UI-02 공통 UI 규약 — 기준 화면 3개로 확정한 패턴

작성: 2026-09-27 (Claude Code) · 브랜치 `ui-02-common-patterns`
선행: [UI-01 디자인 시스템](디자인시스템_UI-01.md) — 토큰·버튼·입력·배지 규칙은 UI-01을 그대로 쓴다. 이 문서는 **앱 틀의 스크롤 소유권과 화면 패턴 3종**을 확정한다.
적용표: [전체 메뉴 적용표](메뉴적용표_UI-02.md) · 작업 지시: [Antigravity 작업 지시서](../agent/Antigravity_작업지시_UI-02.md)

## 0. Figma

- 연결 계정: Figma Starter 플랜, **View 좌석**. 이번 작업에는 프레임 URL이 없었다.
- 따라서 **Figma 수치(Auto Layout·간격·타이포그래피)를 읽어 반영하지 않았다.** 아래 기준은 현재 사이트와 코드(UI-01 토큰)에서 정리했다.
- 프레임이 생기면 이 표에 링크와 대응 컴포넌트를 추가한다. Fill은 `minmax(0, 1fr)`·`flex: 1`, Hug는 내용 크기, Fixed는 토큰(`--panel-w` 등)으로 옮기고 픽셀을 그대로 복사하지 않는다.

| Figma 프레임 | 대응 코드 |
|---|---|
| (없음) | — |

## 1. 파일 위치

| 무엇 | 경로 |
|---|---|
| 토큰·공통 클래스 전부 | `frontend/src/shared/styles.css` (`:root` 토큰, 화면별 CSS 파일을 만들지 않는다) |
| 공통 컴포넌트 | `frontend/src/shared/components.tsx` — `PageTitle`·`DataTable`·`Pagination`·`DateRange`·`FormPanel`·`useDiscardGuard`·`EmptyState`·`ErrorNotice`·`Loading`·`Badge`·`Field` |
| 솔루션 틀(사이드바) | `frontend/src/shared/SolutionLayout.tsx` |
| 앱 틀(헤더·본문·바닥글) | `frontend/src/app/App.tsx` `Layout` |
| 기준 화면 | 대시보드 `fems/Dashboard.tsx`(F-01) · 조회 목록 `fems/Readings.tsx`(F-02) · 목록+패널 `fems/Production.tsx`(F-05) |

## 2. 앱 틀과 스크롤 소유권

| 요소 | 규칙 |
|---|---|
| 높이 토큰 | `--header-h` 52px. 헤더 아래 남은 높이는 **`--app-h` 하나**만 쓴다(`100dvh − 헤더`, `100vh` fallback). 다른 픽셀을 빼는 높이 계산을 만들지 않는다. |
| 앱 틀 | `.app-shell`(세로 flex, `min-height: 100dvh`) → 헤더(고정) → `main`(`flex: 1`) → 바닥글. |
| 바닥글 | **포털 화면에만** 둔다. `/fems`·`/mes`·`/erp` 업무 화면에는 없다(불필요한 페이지 스크롤 제거). "공통 이용 안내" 링크는 사이드바 "다른 앱" 끝으로 옮겼다. |
| 사이드바 | 헤더 아래 고정·자체 스크롤(`height: var(--app-h)`), 넓은 화면 접기(52px 레일), 800px 이하 서랍. |
| 본문 | `.solution-content`는 `min-width: 0`. `body { overflow: hidden }`을 쓰지 않는다. |
| 목록 채움 | 화면 루트에 `.page-fill`을 두면 **1025px 이상 + 높이 600px 이상**에서 본문 높이가 `--app-h`로 고정되고 결과 영역만 스크롤한다. 그보다 좁거나 낮거나 확대하면 자연스러운 세로 스크롤로 돌아간다. 내용이 남은 높이보다 크면 넘친 만큼 문서가 스크롤된다(잘리지 않음). |

### 화면 유형별 스크롤 정책

| 유형 | 데스크톱(≥1025 × ≥600) | 모바일·낮은 화면·확대 |
|---|---|---|
| 대시보드 | 문서 스크롤(자연). 한 화면에 억지로 맞추지 않는다. | 자연 스크롤, 1열 |
| 조회 목록 | `.page-fill`: 제목·조건·결과 수·페이지 이동 고정, **표 컨테이너만 스크롤**, 머리글 고정 | 자연 스크롤, 페이지 이동은 화면 아래에 붙음(sticky) |
| 목록+패널 | `.page-fill` + `.split-view`: 목록만 스크롤, 패널은 필드 영역만 스크롤 | 패널은 겹침(≤1599px)·전체 화면(≤600px) |
| 예외(상세·흐름·3D·도움말) | 문서 스크롤 | 자연 스크롤 |

## 3. 컴포넌트 사용법

### PageTitle — 제목 줄

```tsx
<PageTitle
  id="F-05"
  title="생산량 등록"
  subtitle="한 줄 설명"
  help="fems/f-05"
  actions={<button onClick={openNew}>생산량 등록</button>}  // 주요 행동·조회 월
/>
```

- 제목 22px + 화면 ID + 한 줄 설명. 오른쪽에 `actions`(주요 버튼 1개 또는 조회 월)와 도움말.
- 대시보드의 조회 월은 `actions`에 둔다(별도 필터 줄을 만들지 않는다).

### 조회 목록 (F-02 기준)

```tsx
return (
  <div className="page-fill">
    <PageTitle … />
    <form className="filter-bar" onSubmit={submit}>…<button type="submit">조회</button></form>
    <ErrorNotice error={error} retry={retry} />
    <DataTable
      leading={viewTabs}        // 표/그래프 전환 등. 결과 수·CSV와 같은 줄
      rows={rows} columns={columns} caption="계측값"
      offset={offset} total={total} limit={50} onPage={setOffset}
      empty={<EmptyState reason="…" to="…" action="…" />}
    />
  </div>
);
```

- 순서: 제목 → 조건(`.filter-bar`, 한 줄에 넘치면 줄바꿈) → 보기 전환·결과 수·CSV → 결과 → 페이지 이동.
- 그래프처럼 표가 아닌 결과는 `<section className="fill">` 안에 `.table-toolbar`(같은 보기 전환·결과 수) + 차트를 둔다.
- `DataTable` 루트는 `.data-table.fill`이다. `.page-fill` 안에서는 저절로 남은 높이를 쓴다.

### 목록 + 등록·수정 패널 (F-05 기준)

```tsx
const [panel, setPanel] = useState<{ row: Row | null } | null>(null);
const dirty = !!panel && changed(draft, initial);
const guard = useDiscardGuard(dirty);          // 미저장 변경 보호(+새로고침 경고, 앱 안 링크 이동도 확인 — UI-04)

<div className="page-fill">
  <PageTitle … actions={<button onClick={() => guard.guard(() => open(null))}>등록</button>} />
  <div className="split-view fill">
    <section className="fill">
      <div className="filter-bar">…</div>
      <DataTable … />
    </section>
    {panel && (
      <FormPanel
        key={panel.row?.id ?? "new"}
        title={panel.row ? "… 수정" : "… 등록"}
        guard={guard}
        onClose={close}
        onSubmit={submit}
        actions={<><button type="submit">저장</button><button type="button" className="secondary" onClick={() => guard.guard(close)}>취소</button></>}
      >
        <ErrorNotice error={formLevelError} />   {/* 필드 오류가 아닌 저장 오류는 패널 안 */}
        <Field … />
        <div className="field-row"><Field … /><Field … /></div>  {/* 짧은 두 입력 한 줄 */}
      </FormPanel>
    )}
  </div>
</div>
```

- 목록이 기본 작업이다. 패널은 **열 때만** 나타난다(등록 버튼·행의 수정·정정).
- 폭 `--panel-w`(380px). **1600px 이상**은 목록 오른쪽에 붙는다(1600에서 목록 약 920px, 가로 스크롤 없음). **1599px 이하**는 오른쪽에서 겹쳐 열린다(배경 클릭 닫기, 포커스 가둠, `aria-modal`). **600px 이하**는 전체 화면.
- 패널 높이는 내용만큼이다(표 높이에 맞춰 늘리지 않는다). 필드가 길면 `.form-panel-body`만 스크롤하고 저장·취소(`.form-panel-foot`)는 항상 보인다.
- 열면 첫 입력으로 포커스, 닫으면 연 버튼으로 돌아간다(버튼이 사라졌으면 본문). Esc·✕·배경·취소는 `guard`를 거친다. 변경이 있으면 패널 아래에 "저장하지 않은 변경이 있습니다 · 변경 버리기 · 계속 편집"을 보여 준다.
- 다른 행을 수정·정정하려 할 때도 `guard.guard(…)`로 감싼다. 서버에 쓰기가 일어나는 행동(정정=새 버전 생성)은 반드시 확인 뒤 실행한다.
- 저장 성공 → 패널 닫기 + 페이지 위 `role="status"` 안내. 필드 오류 → 입력 아래 `small`. 그 밖의 저장 오류 → 패널 안 `ErrorNotice`(패널이 닫혀 있으면 페이지 위).

### 대시보드 (F-01 기준)

```tsx
<PageTitle … actions={<label>조회 월 <input type="month" … /></label>} />
<div className="kpi-grid">{/* stat-tile 4개 */}</div>
<div className="dashboard-grid has-lead">   {/* 주요 차트가 있으면 has-lead(3:2), 없으면 2×2 */}
  <DailyChart />  <Composition />  <TopList />  <IssueList />
</div>
```

- KPI는 본문 폭 640px 이상이면 한 줄, 그보다 좁으면 2×2. **3+1로 떨어지지 않는다.**
- 하단은 1100px 이상에서 2열, 그보다 좁으면 1열. 폭이 넓어져도 3열·4열로 늘지 않고 읽는 순서(DOM 순서)가 같다. `has-lead`는 3:2로 첫 카드를 넓게 둔다. 같은 열의 카드 외곽이 위아래로 맞는다.
- 카드 높이를 늘려 균형을 맞추지 않는다. 차트 비율·목록 행 수(상위 5)·합계 줄로 조정한다.

## 4. 표·텍스트 규칙

| 내용 | 처리 | 방법 |
|---|---|---|
| 수량·금액 | 한 줄, 오른쪽 정렬, 고정폭 숫자 | 숫자 열 자동(`id`·`*Id` 제외). 직접 쓴 표는 `th/td.num` |
| 단위·짧은 상태 배지·코드 | 한 줄 | 기본(`white-space: nowrap`), `Badge` |
| 날짜 범위 | 칸이 좁으면 시작일 / "~ 종료일" 두 줄 | `<DateRange from to />` |
| 긴 이름·코드(28자 초과, 렌더러 없음) | 줄임표 + 전체 값 확인 | 자동 `td.clip`: 칸이 **포커스 가능**(탭·터치)하고, 포커스·호버하면 줄바꿈해 전체를 보여 준다. `title`은 보조 |
| 설명·메모 | 자연스러운 줄바꿈(16~48ch) | 열 정의에 `wrap: true` |
| 검증 오류·안내 | 자연스러운 줄바꿈 | `.field small`, `.notice`(`overflow-wrap: anywhere`) |

- 표 머리글은 표 스크롤 컨테이너 안에서 고정된다(`thead th` sticky, 첫 열은 가로 고정). `tbody`를 `display: block`으로 바꾸지 않는다.
- 가로 스크롤은 표 컨테이너(`.table-scroll`) 안으로 한정한다. 페이지 전체가 가로로 넘치면 결함이다.
- 페이지 이동은 여러 페이지일 때만 보인다. 자연 스크롤에서는 목록이 보이는 동안 화면 아래에 붙는다.

## 5. 페이지 폭·여백·타이포그래피

- 업무 화면 폭 제한 없음. 좌우 여백 `--gutter` 24px(모바일 16px). 읽기 중심(도움말 본문)만 880px.
- 제목 22px(모바일 20) · 섹션 16 · 본문 14 · 보조 13 · 최소 12. KPI 숫자 24(모바일 20). 글자 축소·`zoom`·`transform`으로 맞추지 않는다.
- 간격 토큰 `--s1`~`--s6`(4·8·12·16·20·24)만 쓴다. 패널 안쪽 16/20px, 필드 간격 12px.
- 화면 안내문은 `<p className="muted" role="note">` — 아래 요소와 12px 간격.

## 6. 상태 표시

| 상태 | 표시 |
|---|---|
| 로딩 | `Loading`(목록은 `delay={300}`로 깜빡임 방지) |
| 빈 상태 | `EmptyState` — 사유 + 다음 행동. 같은 화면의 행동이면 `onAction`(버튼), 다른 화면이면 `to`(링크) |
| 오류 | `ErrorNotice`(코드·상세·다시 시도). 필드 오류는 입력 아래 |
| 모듈 꺼짐 | `EmptyState` "내 공간에서 다시 켤 수 있습니다" (기존 유지) |
| 세션 만료 | `SessionExpired` (기존 유지) |
| 권한 제한 | 메뉴를 숨기고 직접 접근은 `NotFound`(P-07 방식). 화면 안 행동 제한은 버튼 `disabled` + 안내 문구 |
| 확정·게시된 행 | 수정·삭제 버튼 대신 정정(새 버전) — 업무 규칙이므로 UI에서 바꾸지 않는다 |

## 7. 반응형 기준점

| 폭 | 변화 |
|---|---|
| ≤400 | 필터 칸 한 줄씩 |
| ≤600 | 패널 전체 화면 |
| ≤800 | 사이드바 서랍, 헤더 두 줄, 여백 16 |
| ≤1024 | 목록 채움 끔(자연 스크롤), 레거시 `master-grid` 패널이 목록 아래로 |
| ≥1100 | 대시보드 하단 2열 |
| ≥1600 | 패널을 목록 옆에 붙임 |
| 높이 <600 | 목록 채움 끔 |

200% 확대(1440×900 → CSS 720×450)는 모바일 규칙으로 동작한다. 저장 버튼·오류·필수 정보가 잘리지 않음을 확인했다.

## 8. UI-03 예외 패턴 (2026-09-27)

공통 컴포넌트: `DetailPanel`(폼 없는 패널)·`FormPanel`/`DetailPanel`의 `wide`(640px, `--panel-w-wide`). 둘 다 `FormPanel`과 같은 틀(포커스·Esc·배경·가둠·guard)을 쓴다.

| 패널 | 붙음 | 겹침 | 전체 화면 |
|---|---|---|---|
| 기본 380px | ≥1600 | ≤1599 | ≤600 |
| 넓은 640px(`wide`) | ≥1920 | ≤1919 | ≤600 |

### 읽기 전용 상세 — M-04 `mes/Lots.tsx`

```tsx
{selectedId && (
  <DetailPanel wide key={selectedId} title={`${lot.lotNo} 이력`} onClose={() => setSelectedId(undefined)}>
    <p>상태 배지</p><p className="muted">요약</p>
    <DataTable … caption={`${lot.lotNo} 공정 이력`} />
  </DetailPanel>
)}
```

### 부모-자식 상세 — F-12 `fems/Meters.tsx`

- 패널 상태 하나: `{kind:"meter",row}` · `{kind:"channels",meterId}` · `{kind:"channel",meterId,row}`. 한 번에 패널 하나만 연다.
- 부모 행의 "채널 N" → 자식 목록 `DetailPanel wide`(foot에 "채널 등록"). 자식 "수정"·"채널 등록" → 같은 자리에 자식 `FormPanel`. 자식 폼의 닫기·취소·저장 성공은 **자식 목록으로 돌아간다**(`onClose={() => openChannels(id)}`).
- 새 부모를 등록하면 바로 그 부모의 자식 목록을 연다.
- 미저장 보호는 부모·자식 폼 draft와 열 때의 initial을 비교한 `dirty` 하나로 `useDiscardGuard`.

### 넓은 행 편집 — E-04 `erp/SalesOrders.tsx`

- 등록: 제목 줄 "수주 등록" → `FormPanel wide`(기본 정보는 `.field-row` 두 칸 + `LineEditor`). 저장 성공 → 새 행의 상세.
- 상세: 행의 "명세 N" → `DetailPanel wide`(요약·명세 표, foot에 "명세 편집"은 편집 가능할 때만).
- 편집: 같은 자리에 `FormPanel wide`, 닫기·취소·저장 성공은 상세로 돌아간다.
- **저장 직후의 선택·전환은 guard를 거치지 않는다**(`openDetail` 직접 호출). guard는 사용자가 다른 행·버튼을 누를 때만 쓴다 — 저장 직후에는 폼이 아직 '변경됨'으로 보여 확인창이 잘못 뜬다(UI-02 검토에서 E-05·E-06·E-10에서 발견).

### 상태 전이 — M-05 `mes/Executions.tsx`, M-07 `mes/Results.tsx`

- 목록 여러 개는 `.section-block`으로 쌓는다. 시작·실적 확정은 기본 `FormPanel`. 실적 확정은 공통 `ResultForm`(내부에 guard).
- 폼 이름(패널 제목)은 테스트·접근성 이름으로 쓰이므로 행동 이름('공정 시작'·'실적 확정')으로 두고, LOT·공정 같은 대상은 본문 `h3`에 쓴다.

### 패널 안 목록 버튼 규칙

- 패널을 연 채로 눌러야 하는 버튼(제안량 채우기 등)은 **패널 안**에 둔다. 1599px 이하에서는 목록이 패널 배경에 가려진다.
- 행 버튼이 패널을 자동으로 열어 방금 보려던 목록을 가리지 않게 한다(M-12 '환산' 사례).

## 9. 레거시 패턴과 이전 방법

- `.master-grid`(항상 오른쪽 360px 폼)는 **레거시**다. 새 화면에 쓰지 않는다. 기존 화면은 적용표 순서대로 `split-view` + `FormPanel`로 옮긴다.
- 화면별로 스타일을 새로 만들거나 기준 화면 코드를 복사해 따로 관리하지 않는다. 부족한 기능은 공통 컴포넌트 확장으로 요청한다(Claude 담당).
- 예외 패턴 3종은 UI-03에서 확정했다(8장). 남은 M-14·M-15·E-02는 지시서 UI-03 B1·B2.

## UI-04 앱 안 이동의 미저장 보호 (2026-09-30)

- `useDiscardGuard(dirty)`가 변경이 있는 동안 **문서 캡처 단계에서 앱 안 링크 클릭**(사이드바·헤더·본문 링크)을 가로채 같은 패널의 "변경 버리기 / 계속 편집" 확인으로 보낸다. 버리면 같은 링크를 한 번 다시 눌러 이동한다(React Router `Link` 처리를 그대로 탄다).
- 가로채지 않는 것: ⌘/Ctrl/Shift/Alt 클릭·가운데 버튼(새 탭), `target=_blank`, 다른 사이트, 현재 주소와 같은 링크.
- 이유: `BrowserRouter`라 `useBlocker`를 쓸 수 없다. 데이터 라우터로 바꾸면 모든 테스트의 `MemoryRouter` 구성이 바뀌어 비용이 크다. 이 방식은 공통 훅 한 곳만 바꿔 40개 화면에 적용된다.
- 한계: 브라우저 뒤로·앞으로 가기(popstate)는 막지 않는다.
- 검증: `src/shared/discard-guard.test.tsx` 3, e2e `layout.spec.ts` F-05 생산량 입력 중 사이드바 F-06 클릭.
