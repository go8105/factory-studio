// FS-018b F-02 계측 조회. 검증 항목별로 테스트를 나눈다.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";
import { ReadingChart, type Reading } from "./Readings";
const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const reading = (id: number, value: string | null): Reading => ({
  id,
  observedAt: `2026-09-07T0${id}:00:00+00:00`,
  periodStart: null,
  timezone: "Asia/Seoul",
  meterCode: "M-ASM-02",
  channelId: 6,
  channelCode: "CH-ASM-02-KWH",
  channelName: "조립기 2호 전력",
  energySourceCode: "ELEC",
  value,
  unit: "kWh",
  quality: value === null ? "invalid" : "valid",
});
const rows = [reading(1, "12.5"), reading(2, null), reading(3, "11.0")];
const meters = [
  {
    id: 1,
    meterCode: "M-MAIN",
    name: "수전",
    channels: [{ id: 1, channelCode: "CH-MAIN-KWH", name: "수전 전력" }],
  },
  {
    id: 6,
    meterCode: "M-ASM-02",
    name: "조립기 2호",
    channels: [
      { id: 6, channelCode: "CH-ASM-02-KWH", name: "조립기 2호 전력" },
    ],
  },
];
type Reply = { status: number; body: unknown };
function mockApi(readings?: Reply) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes("/fems/readings") && readings)
      return new Response(JSON.stringify(readings.body), {
        status: readings.status,
      });
    const data = url.endsWith("/sessions/current")
      ? session
      : url.includes("/fems/meters")
        ? meters
        : url.includes("/fems/energy-sources")
          ? []
          : rows;
    return new Response(
      JSON.stringify({
        data,
        page: { offset: 0, limit: 50, total: 3 },
        range: { from: "2026-09-17", to: "2026-09-23" },
      }),
      { status: 200 },
    );
  });
}
const readingCalls = (fetcher: ReturnType<typeof mockApi>) =>
  fetcher.mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.includes("/fems/readings"));
function show(path = "/fems/readings") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}
it("FEMS 진입은 F-02 계측 조회로 이동한다", async () => {
  mockApi();
  show("/fems");
  expect(
    await screen.findByRole("heading", { name: "계측 조회" }),
  ).toBeVisible();
});
it("사이드바에 에너지 현황 그룹과 F-02가 있다", async () => {
  mockApi();
  show();
  expect(
    await screen.findByRole("link", { name: /F-02 계측 조회/ }),
  ).toHaveAttribute("href", "/fems/readings");
  expect(screen.getByRole("heading", { name: "에너지 현황" })).toBeVisible();
});
it("첫 조회는 기간 없이 요청하고 서버가 정한 기간을 입력 칸에 보여준다", async () => {
  const fetcher = mockApi();
  show();
  await waitFor(() =>
    expect(screen.getByLabelText("시작일")).toHaveValue("2026-09-17"),
  );
  expect(readingCalls(fetcher)[0]).not.toContain("from=");
});
it("첫 조회 후 같은 조회를 다시 요청하지 않는다", async () => {
  const fetcher = mockApi();
  show();
  await screen.findAllByRole("cell", { name: "조립기 2호 전력" });
  expect(readingCalls(fetcher)).toHaveLength(1);
});
it("결측 행은 0이 아니라 결측으로 표시한다", async () => {
  mockApi();
  show();
  expect(
    (await screen.findAllByRole("cell", { name: "결측" })).length,
  ).toBeGreaterThan(0);
  expect(screen.queryByRole("cell", { name: "0" })).not.toBeInTheDocument();
});
it("품질은 텍스트 배지로 표시한다", async () => {
  mockApi();
  show();
  expect((await screen.findAllByText("정상")).length).toBeGreaterThan(0);
});
it("조건을 바꿔도 조회 버튼 전에는 요청하지 않는다", async () => {
  const fetcher = mockApi();
  show();
  await screen.findAllByRole("cell", { name: "결측" });
  fireEvent.change(screen.getByLabelText("품질"), {
    target: { value: "invalid" },
  });
  expect(readingCalls(fetcher)).toHaveLength(1);
});
it("조회 버튼은 선택한 조건으로 요청한다", async () => {
  const fetcher = mockApi();
  show();
  await screen.findAllByRole("cell", { name: "결측" });
  fireEvent.change(screen.getByLabelText("채널"), { target: { value: "6" } });
  fireEvent.change(screen.getByLabelText("품질"), {
    target: { value: "invalid" },
  });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() => expect(readingCalls(fetcher)).toHaveLength(2));
  const url = readingCalls(fetcher)[1];
  expect(url).toContain("channelId=6");
  expect(url).toContain("quality=invalid");
  expect(url).toContain("from=2026-09-17");
});
it("계측기를 고르면 그 계측기의 채널만 선택지에 남는다", async () => {
  mockApi();
  show();
  await screen.findAllByRole("cell", { name: "결측" });
  fireEvent.change(screen.getByLabelText("계측기"), { target: { value: "1" } });
  const options = Array.from(
    (screen.getByLabelText("채널") as HTMLSelectElement).options,
  ).map((o) => o.text);
  expect(options).toEqual(["전체", "수전 전력"]);
});
it("선 그래프 보기는 한 번에 200건까지 요청한다", async () => {
  const fetcher = mockApi();
  show();
  await screen.findAllByRole("cell", { name: "결측" });
  fireEvent.click(screen.getByRole("button", { name: "선 그래프" }));
  await waitFor(() =>
    expect(readingCalls(fetcher).at(-1)).toContain("limit=200"),
  );
});
it("채널을 고르지 않으면 선 그래프 대신 안내를 보여준다", () => {
  render(<ReadingChart rows={rows} channelSelected={false} />);
  expect(screen.getByText(/채널을 하나 고르고/)).toBeVisible();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});
it("결측 구간에서 선을 끊는다", () => {
  const { container } = render(<ReadingChart rows={rows} channelSelected />);
  const d = container.querySelector("path.series")?.getAttribute("d") ?? "";
  expect(d.match(/M/g)).toHaveLength(2);
  expect(screen.getByText(/결측 1건은 선을 끊어 표시/)).toBeVisible();
});
it("기간 오류는 날짜 입력 칸에 표시한다", async () => {
  mockApi({
    status: 400,
    body: {
      error: {
        code: "VALIDATION_FAILED",
        message: "조회 기간이 너무 깁니다.",
        details: { fields: { to: "최대 31일까지 조회합니다." } },
      },
    },
  });
  show();
  await waitFor(() =>
    expect(screen.getByLabelText("종료일")).toHaveAttribute(
      "aria-invalid",
      "true",
    ),
  );
});
it("FEMS를 끈 공간은 내 공간으로 안내한다", async () => {
  mockApi({
    status: 409,
    body: {
      error: {
        code: "PRECONDITION_NOT_MET",
        message: "사용하지 않도록 설정되어 있습니다.",
        details: { reason: "MODULE_DISABLED", moduleKey: "fems" },
      },
    },
  });
  show();
  expect(
    await screen.findByRole("link", { name: /내 공간으로/ }),
  ).toHaveAttribute("href", "/workspace");
});
