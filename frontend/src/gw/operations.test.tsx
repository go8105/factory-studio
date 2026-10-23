vi.mock("./RetentionReviews", () => ({
  RetentionReviews: () => <div>보관 검토</div>,
}));
vi.mock("./OperatingEvidence", () => ({
  OperatingEvidence: () => <div>운영 실행 기록</div>,
}));
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { Operations } from "./Operations";
import { CompanyContext, RoleContext } from "./common";
vi.mock("../app/session", () => ({
  useSession: () => ({
    session: { workspaceId: 1, generationId: 2, csrfToken: "synthetic-csrf" },
    fail: vi.fn(),
  }),
}));
const response = (data: unknown, status = 200) =>
  new Response(JSON.stringify(status < 400 ? { data } : { error: data }), {
    status,
  });
const initial = {
  administrator: true,
  canEdit: true,
  version: 0,
  rolloutState: "DRAFT",
  connectedPeople: 1,
  mfaPeople: 1,
  policy: null,
  revisionNo: null,
  ready: false,
  blockers: ["실제 복원 검증이 필요합니다."],
};
function show() {
  render(
    <MemoryRouter>
      <CompanyContext.Provider value={{ companyId: "10" }}>
        <RoleContext.Provider
          value={{
            person: "3",
            setPerson: () => {},
            people: [
              {
                id: "3",
                code: "SYN-001",
                name: "합성 책임자",
                isActive: true,
                jobRole: "",
                version: 1,
              },
            ],
            reload: () => {},
            companyId: "10",
            companyName: "합성 검증 회사",
            roles: ["SECURITY_ADMIN"],
          }}
        >
          <Operations />
        </RoleContext.Provider>
      </CompanyContext.Provider>
    </MemoryRouter>,
  );
}
beforeEach(() => vi.restoreAllMocks());
it("준비 미완료 사유와 기본안을 표시하고 계속 편집 시 입력 포커스를 복원한다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response(initial));
  show();
  await screen.findByText("실제 복원 검증이 필요합니다.");
  fireEvent.click(screen.getByRole("button", { name: "운영 기준 검토·적용" }));
  const reason = screen.getByLabelText("적용 사유");
  reason.focus();
  fireEvent.change(reason, { target: { value: "합성 운영 기준" } });
  fireEvent.click(screen.getByRole("button", { name: "취소" }));
  fireEvent.click(screen.getByRole("button", { name: "계속 편집" }));
  await waitFor(() => expect(reason).toHaveFocus());
  expect(reason).toHaveValue("합성 운영 기준");
  expect(screen.getByLabelText("예정 직원 수")).toHaveValue(10);
  expect(
    screen.getByRole("button", { name: "새 버전으로 적용" }),
  ).toBeDisabled();
});
it("직원 응답에는 관리자 정책 입력을 표시하지 않는다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    response({
      administrator: false,
      nextAction: "내 계정 보안에서 확인하세요.",
    }),
  );
  show();
  expect(await screen.findByText("내 계정 보안에서 확인하세요.")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "운영 기준 검토·적용" }),
  ).not.toBeInTheDocument();
});
it("추가 인증 오류 뒤 패널과 입력을 유지한다", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
    String(url).includes("/operating-policies")
      ? response(
          {
            code: "STEP_UP_REQUIRED",
            message: "내 계정 보안에서 다시 확인하세요.",
          },
          403,
        )
      : response(initial),
  );
  show();
  fireEvent.click(
    await screen.findByRole("button", { name: "운영 기준 검토·적용" }),
  );
  const reason = screen.getByLabelText("적용 사유");
  fireEvent.change(reason, { target: { value: "합성 사유 유지" } });
  fireEvent.click(screen.getByLabelText("변경 내용과 영향을 검토했습니다"));
  fireEvent.click(screen.getByRole("button", { name: "새 버전으로 적용" }));
  expect(
    await screen.findByText("내 계정 보안에서 다시 확인하세요."),
  ).toBeVisible();
  expect(reason).toHaveValue("합성 사유 유지");
  expect(fetch).toHaveBeenCalledTimes(2);
});
it("실행 증거별 결과를 표시해도 운영 준비 완료로 바꾸지 않는다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    response({
      ...initial,
      evidenceChecks: [
        {
          kind: "BACKUP",
          label: "백업 실행",
          state: "RECORDED_PASS",
          detail: "현재 기준의 등록된 통과입니다.",
        },
        {
          kind: "RESTORE",
          label: "복원 실행",
          state: "PARTIAL",
          detail: "일부 확인 상태입니다. 남은 검증을 마치세요.",
        },
      ],
    }),
  );
  show();
  expect(
    await screen.findByRole("heading", { name: "실행 증거 확인" }),
  ).toBeVisible();
  expect(screen.getByText("현재 기준의 등록된 통과입니다.")).toBeVisible();
  expect(
    screen.getByText("일부 확인 상태입니다. 남은 검증을 마치세요."),
  ).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "아직 운영 준비 중입니다" }),
  ).toBeVisible();
});
it("운영 전환 조건의 확인·조치·미확인과 다음 행동을 구분한다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    response({
      ...initial,
      launchGate: {
        ready: false,
        confirmedCount: 1,
        blockedCount: 1,
        unverifiedCount: 1,
        checks: [
          {
            code: "POLICY",
            label: "운영 기준",
            state: "CONFIRMED",
            detail: "기준이 적용됐습니다.",
            nextAction: "",
          },
          {
            code: "MFA",
            label: "직원 인증 앱",
            state: "BLOCKED",
            detail: "등록이 필요합니다.",
            nextAction: "직원의 인증 앱 등록을 확인하세요.",
          },
          {
            code: "EXTERNAL_STORAGE",
            label: "외부 저장소 장애·복구",
            state: "UNVERIFIED",
            detail: "인수 근거가 없습니다.",
            nextAction: "외부 사본 복구를 인수하세요.",
            acceptanceScope: "실제 외부 저장소에서 확인합니다.",
            requiredEvidence: ["원본 없이 외부 사본을 읽고 복구한 결과"],
          },
        ],
      },
    }),
  );
  show();
  expect(
    await screen.findByRole("heading", { name: "운영 전환 조건" }),
  ).toBeVisible();
  expect(screen.getByText("운영 기준 · 확인됨")).not.toBeVisible();
  fireEvent.click(screen.getByText("확인된 조건 1개 보기"));
  expect(screen.getByText("운영 기준 · 확인됨")).toBeVisible();
  expect(screen.getByText("직원 인증 앱 · 조치 필요")).toBeVisible();
  expect(screen.getByText("외부 저장소 장애·복구 · 미확인")).toBeVisible();
  expect(screen.getByText("외부 사본 복구를 인수하세요.")).toBeVisible();
  expect(
    screen.getByText("원본 없이 외부 사본을 읽고 복구한 결과"),
  ).not.toBeVisible();
  fireEvent.click(screen.getByText("필요한 인수 근거"));
  await waitFor(() =>
    expect(
      screen.getByText("원본 없이 외부 사본을 읽고 복구한 결과"),
    ).toBeVisible(),
  );
  expect(
    screen.getByText("이 안내는 제출된 증거나 완료 승인이 아닙니다."),
  ).toBeVisible();
  expect(screen.queryByText("실제 복원 검증이 필요합니다.")).toBeNull();
  expect(
    screen.getByRole("heading", { name: "아직 운영 준비 중입니다" }),
  ).toBeVisible();
});

it.each([true, false])(
  "최근 등록 증거의 연결 결과를 표시하고 운영 완료로 바꾸지 않는다: %s",
  async (paired) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({
        ...initial,
        backupRestoreCollection: {
          result: paired ? "PARTIAL" : "BLOCKED",
          source: "LATEST_REGISTRATIONS",
          backupRestorePairVerified: paired,
        },
      }),
    );
    show();
    await screen.findByRole("heading", { name: "백업·복원 연결 점검" });
    expect(
      screen.getByText(
        "더 최근 미통과 기록을 과거 성공 기록으로 대신하지 않습니다.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        paired
          ? "최근 등록한 백업·복원 증거가 같은 백업을 가리킵니다. 일부 확인이며 운영 인수 완료는 아닙니다."
          : "최근 등록한 백업·복원 증거의 연결을 확인하지 못했습니다. 위 실행 증거 결과와 등록한 파일 쌍을 확인하세요.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "아직 운영 준비 중입니다" }),
    ).toBeInTheDocument();
  },
);

it("일부 복원 검사의 확인·미충족·기록 없음을 구분하고 완료 처리하지 않는다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    response({
      ...initial,
      backupRestoreCollection: {
        result: "BLOCKED",
        source: "LATEST_REGISTRATIONS",
        backupRestorePairVerified: false,
        restoreMeasurements: {
          rowHashesMatch: true,
          foreignKeysValid: true,
          sessionsInvalidated: true,
          revocationsReapplied: false,
          twoAccountChecks: null,
          lossWindowSeconds: 60,
          elapsedSeconds: 120,
          restoreDiagnostics: {
            databaseClosed: true,
            dbRevisionMatches: true,
            checkpointRestrictionsApplied: true,
            checkpointCompletenessConfirmed: false,
            journalCandidateIntents: 6,
            journalUnconfirmedIntents: 1,
            journalQuarantinedScopes: 1,
          },
        },
      },
    }),
  );
  show();
  const summary = await screen.findByText("최근 복원 검사 내용");
  fireEvent.click(summary);
  expect(
    screen.getByText("전체 권한 회수 확인").parentElement,
  ).toHaveTextContent("미충족");
  expect(
    screen.getByText("관리자·직원 업무 확인").parentElement,
  ).toHaveTextContent("기록 없음");
  expect(screen.getByText(/미확인 변경 기록 1건/)).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "아직 운영 준비 중입니다" }),
  ).toBeInTheDocument();
});

it("현재 회사와 업무 복귀 경로를 유지하고 섹션 이동 대상을 연결한다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response(initial));
  show();
  await screen.findByRole("heading", { name: "아직 운영 준비 중입니다" });
  expect(screen.getByText("합성 검증 회사 · 보안 관리자")).toBeVisible();
  expect(
    screen.getByRole("link", { name: "GW 업무로 돌아가기" }),
  ).toHaveAttribute("href", "/gw/dashboard?companyId=10");
  expect(screen.getByRole("link", { name: "내 결재함" })).toHaveAttribute(
    "href",
    "/gw/pending?companyId=10",
  );
  const navigation = screen.getByRole("navigation", {
    name: "운영 준비 항목 바로가기",
  });
  for (const link of within(navigation).getAllByRole("link")) {
    const id = link.getAttribute("href")!.slice(1);
    expect(document.getElementById(id)).not.toBeNull();
  }
  expect(screen.getByLabelText("긴급 복구 문서 발급 사유")).not.toBeVisible();
  fireEvent.click(screen.getByText("본인 긴급 복구 문서 관리"));
  expect(screen.getByLabelText("긴급 복구 문서 발급 사유")).toBeVisible();
});

it("감사 역할은 조회 전용 안내와 업무 복귀만 제공하고 변경·복구 입력을 숨긴다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    response({ ...initial, canEdit: false }),
  );
  show();
  expect(
    await screen.findByText("합성 검증 회사 · 감사 · 조회 전용"),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "운영 기준 검토·적용" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByText("본인 긴급 복구 문서 관리"),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText(
      "현재는 조회 권한입니다. 기준 변경은 GW 보안 관리자에게 요청하세요.",
    ),
  ).toBeVisible();
});

it("긴급 복구 요청이 거부되어도 펼친 영역과 오류·입력을 유지한다", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
    String(url).includes("/emergency-kit")
      ? response(
          {
            code: "STEP_UP_REQUIRED",
            message: "복구 문서 발급 전에 본인 확인이 필요합니다.",
          },
          403,
        )
      : response(initial),
  );
  show();
  fireEvent.click(await screen.findByText("본인 긴급 복구 문서 관리"));
  const reason = screen.getByLabelText("긴급 복구 문서 발급 사유");
  fireEvent.change(reason, { target: { value: "합성 오류 표시 확인" } });
  fireEvent.click(
    screen.getByLabelText(
      "이전 문서·미사용 승인 파일 회수와 별도 보관 필요를 확인했습니다",
    ),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "본인 긴급 복구 문서 새로 발급" }),
  );
  expect(
    await screen.findByText("복구 문서 발급 전에 본인 확인이 필요합니다."),
  ).toBeVisible();
  expect(reason).toBeVisible();
  expect(reason).toHaveValue("합성 오류 표시 확인");
});
it.each(["PARTIAL", "FAILED"])(
  "현재 재대조한 관측의 %s 상세와 다음 조치를 기존 실행 영역에 표시한다",
  async (state) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({
        ...initial,
        evidenceChecks: [
          {
            kind: "ACCEPTANCE",
            label: "실환경 업무 인수",
            state,
            detail: state === "FAILED" ? "최근 관측 미통과" : "관측 일부 확인",
            journalObservation: {
              observedAt: "2026-10-23T03:00:00Z",
              scopeRecords: 8,
              auditConfirmed: 6,
              abortConfirmed: 1,
              unresolvedRecords: 1,
              missingTransactionProofs: 0,
            },
          },
        ],
      }),
    );
    show();
    const summary = await screen.findByText("회사 변경 기록 관측 내용");
    const detail = summary.closest("details")!;
    expect(detail.open).toBe(false);
    fireEvent.click(summary);
    expect(detail.open).toBe(true);
    expect(within(detail).getByText(/대조 대상 8건/)).toBeVisible();
    expect(within(detail).getByText(/미확인 거래 1건/)).toBeVisible();
    expect(
      within(detail).getByText(
        state === "FAILED"
          ? /미확인 기록을 조사한 뒤 새 관측/
          : /전체 변경 수집·권한 회수와 실제 회사 인수는 별도로/,
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "아직 운영 준비 중입니다" }),
    ).toBeVisible();
  },
);
it("복원 직후 제한 관측을 현재 복원본이나 전체 회수 완료로 표시하지 않는다", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    response({
      ...initial,
      backupRestoreCollection: {
        result: "BLOCKED",
        source: "LATEST_REGISTRATIONS",
        backupRestorePairVerified: false,
        restoreMeasurements: {
          rowHashesMatch: true,
          foreignKeysValid: true,
          sessionsInvalidated: true,
          revocationsReapplied: false,
          twoAccountChecks: false,
          restoreDiagnostics: {
            databaseClosed: true,
            checkpointCompletenessConfirmed: false,
            journalUnconfirmedIntents: 1,
            journalQuarantinedScopes: 1,
            executionObservation: {
              observedAt: "2026-10-23T04:00:00Z",
              unrevokedSessions: 0,
              pendingChallenges: 0,
              coreViolations: 0,
              gwViolations: 0,
              hrViolations: 0,
              journalUserViolations: 0,
            },
          },
        },
      },
    }),
  );
  show();
  fireEvent.click(await screen.findByText("최근 복원 검사 내용"));
  const observation = screen.getByRole("region", {
    name: "복원 직후 제한 재대조",
  });
  expect(within(observation).getByText(/회수되지 않은 세션 0건/)).toBeVisible();
  expect(
    within(observation).getByText(/현재 복원본 상태·전체 권한 회수/),
  ).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "아직 운영 준비 중입니다" }),
  ).toBeVisible();
});

it.each([true, false])(
  "복원본 재관측의 측정 여부 %s와 다음 조치를 표시한다",
  async (measured) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({
        ...initial,
        evidenceChecks: [
          {
            kind: "ACCEPTANCE",
            label: "실환경 업무 인수",
            state: "FAILED",
            detail: "재관측 미통과",
            restoreRecheck: {
              checkedAt: "2026-10-23T04:00:00Z",
              result: "BLOCKED",
              targetMeasured: measured,
              stateMatchesExecution: measured ? false : null,
              reason: measured ? "MEASURED" : "MEASUREMENT_UNAVAILABLE",
              ...(measured
                ? {
                    measurement: {
                      unrevokedSessions: 1,
                      pendingChallenges: 0,
                      coreViolations: 0,
                      gwViolations: 0,
                      hrViolations: 0,
                      journalUserViolations: 0,
                      connectionLimitZero: true,
                      publicConnectRevoked: true,
                    },
                  }
                : {}),
            },
          },
        ],
      }),
    );
    show();
    const summary = await screen.findByText("복원본 최근 재관측");
    fireEvent.click(summary);
    const detail = summary.closest("details")!;
    expect(within(detail).getByText(/유효 기한은 15분/)).toBeVisible();
    expect(
      within(detail).getByText(
        measured
          ? /회수되지 않은 세션 1건/
          : /측정값을 0건으로 간주하지 않습니다/,
      ),
    ).toBeVisible();
    expect(
      within(detail).getByText(/새 관측과 인수 점검을 등록/),
    ).toBeVisible();
    if (!measured) expect(within(detail).queryByText(/세션 0건/)).toBeNull();
    expect(
      screen.getByRole("heading", { name: "아직 운영 준비 중입니다" }),
    ).toBeVisible();
  },
);

it.each(["MATCH", "CHANGED", "MEASUREMENT_UNAVAILABLE"])(
  "원본 권한 대조 %s와 조치 범위를 표시한다",
  async (reason) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({
        ...initial,
        evidenceChecks: [
          {
            kind: "ACCEPTANCE",
            label: "실환경 업무 인수",
            state: reason === "MATCH" ? "PARTIAL" : "FAILED",
            detail: "원본 비교",
            restoreRecheck: {
              checkedAt: "2026-10-23T05:00:00Z",
              result: reason === "MATCH" ? "PARTIAL" : "BLOCKED",
              targetMeasured: false,
              stateMatchesExecution: null,
              reason: "MEASUREMENT_UNAVAILABLE",
              sourceObservation: {
                observedAt: "2026-10-23T05:00:00Z",
                sourceMeasured: reason !== "MEASUREMENT_UNAVAILABLE",
                contextMatches:
                  reason === "MEASUREMENT_UNAVAILABLE" ? null : true,
                changedGroups:
                  reason === "MEASUREMENT_UNAVAILABLE"
                    ? null
                    : { core: reason === "CHANGED" ? 1 : 0, gw: 0, hr: 0 },
                reason,
                result: reason === "MATCH" ? "PARTIAL" : "BLOCKED",
              },
            },
          },
        ],
      }),
    );
    show();
    fireEvent.click(await screen.findByText("복원본 최근 재관측"));
    const region = screen.getByRole("region", {
      name: "현재 원본과 복원 권한 대조 비교",
    });
    expect(
      within(region).getByText(
        reason === "MATCH"
          ? /관측 시점의 원본과 일치/
          : reason === "CHANGED"
            ? /새 권한 대조와 격리 복원을 진행/
            : /변경이 없다고 간주하지 않습니다/,
      ),
    ).toBeVisible();
    expect(within(region).getByText(/두 시점만 비교/)).toBeVisible();
    if (reason === "MEASUREMENT_UNAVAILABLE")
      expect(within(region).queryByText(/공통 0개/)).toBeNull();
    expect(
      screen.getByRole("heading", { name: "아직 운영 준비 중입니다" }),
    ).toBeVisible();
  },
);
