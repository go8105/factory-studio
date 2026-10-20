vi.mock("./RetentionReviews", () => ({
  RetentionReviews: () => <div>보관 검토</div>,
}));
vi.mock("./OperatingEvidence", () => ({
  OperatingEvidence: () => <div>운영 실행 기록</div>,
}));
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
