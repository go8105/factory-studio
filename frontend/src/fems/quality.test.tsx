// FEMS-1d 화면: F-15 계측 품질(결측·보정·CSV)과 F-05 MES 가져오기.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { App } from "../app/App";

const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2099-01-01T00:00:00+09:00",
  csrfToken: "test-csrf",
};
const meters = [
  {
    id: 1,
    meterCode: "MT-01",
    name: "수전",
    channels: [{ id: 5, channelCode: "CH-KWH", name: "유효전력량" }],
  },
];
const quality = {
  channel: { id: 5, channelCode: "CH-KWH", name: "유효전력량", unit: "kWh" },
  period: { from: "2026-09-17", to: "2026-09-23" },
  readingCount: 168,
  issues: [
    {
      kind: "MISSING",
      periodStart: "2026-09-20T03:00:00+09:00",
      value: null,
      note: "계측값이 없습니다.",
    },
    {
      kind: "ZERO_RUN",
      periodStart: "2026-09-21T01:00:00+09:00",
      value: "0",
      note: "0이 5시간 이어집니다.",
    },
  ],
  corrections: [
    {
      id: 9,
      channelCode: "CH-KWH",
      periodStart: "2026-09-19T05:00:00+09:00",
      originalValue: null,
      correctedValue: "12.000000",
      method: "INTERPOLATE",
      reason: "앞뒤 값으로 보간",
      correctedAt: "2026-09-24T01:00:00+09:00",
    },
  ],
};

function mount(path: string, overrides: Record<string, unknown> = {}) {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input).split("?")[0];
      const key = `${init?.method ?? "GET"} ${url}`;
      if (key in overrides)
        return new Response(JSON.stringify({ data: overrides[key] }), {
          status: 200,
        });
      if (url.endsWith("/sessions/current"))
        return new Response(JSON.stringify({ data: session }));
      if (url.endsWith("/fems/meters"))
        return new Response(JSON.stringify({ data: meters }));
      if (url.endsWith("/fems/reading-quality"))
        return new Response(JSON.stringify({ data: quality }));
      return new Response(JSON.stringify({ data: [] }));
    });
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
  return fetcher;
}
const sent = (f: ReturnType<typeof mount>, method: string, suffix: string) =>
  f.mock.calls.filter(
    ([url, init]) =>
      (init?.method ?? "GET") === method &&
      String(url).split("?")[0].endsWith(suffix),
  );

it("이상값마다 판단 근거를 함께 보인다", async () => {
  mount("/fems/reading-quality");
  expect(await screen.findByText("계측값이 없습니다.")).toBeInTheDocument();
  expect(screen.getByText("0이 5시간 이어집니다.")).toBeInTheDocument();
  expect(screen.getByText("결측")).toBeInTheDocument();
  expect(screen.getByText("0 연속")).toBeInTheDocument();
});

it("보정은 사유 없이는 저장되지 않는다", async () => {
  mount("/fems/reading-quality");
  fireEvent.click((await screen.findAllByRole("button", { name: "보정" }))[0]);
  const save = screen.getByRole("button", { name: "보정 저장" });
  fireEvent.change(screen.getByLabelText(/보정 값/), {
    target: { value: "10" },
  });
  expect(save).toBeDisabled();
  fireEvent.change(screen.getByLabelText("사유"), {
    target: { value: "앞뒤 값으로 보간" },
  });
  expect(save).toBeEnabled();
});

it("보정은 원 계측을 지우지 않는다고 알린다", async () => {
  mount("/fems/reading-quality");
  fireEvent.click((await screen.findAllByRole("button", { name: "보정" }))[0]);
  expect(screen.getByText(/원 계측은 지우지 않습니다/)).toBeInTheDocument();
});

it("결측을 메운 이력은 원래 값이 '없음'이다", async () => {
  mount("/fems/reading-quality");
  expect(await screen.findByText(/없음 → 12/)).toBeInTheDocument();
});

it("CSV는 머리글을 건너뛰고 행만 보낸다", async () => {
  const fetcher = mount("/fems/reading-quality", {
    "POST /api/v1/fems/reading-uploads": {
      acceptedCount: 2,
      rejectedCount: 0,
      rejected: [],
    },
  });
  const input = (await screen.findByLabelText(
    "CSV 올리기",
  )) as HTMLInputElement;
  const file = new File(
    [
      "채널코드,구간시작,값\nCH-KWH,2026-09-25T01:00:00+09:00,11\nCH-KWH,2026-09-25T02:00:00+09:00,12\n",
    ],
    "a.csv",
    { type: "text/csv" },
  );
  fireEvent.change(input, { target: { files: [file] } });
  const button = await screen.findByRole("button", { name: /2행 올리기/ });
  fireEvent.click(button);
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/reading-uploads")).toHaveLength(1),
  );
  const body = JSON.parse(
    String(sent(fetcher, "POST", "/reading-uploads")[0][1]?.body),
  );
  expect(body.fileName).toBe("a.csv");
  expect(body.rows).toHaveLength(2);
  expect(body.rows[0].channelCode).toBe("CH-KWH");
});

it("F-05는 월을 골라 MES에서 가져온다", async () => {
  const fetcher = mount("/fems/production", {
    "POST /api/v1/fems/production-records/import": {
      month: "2026-09",
      imported: 12,
      skipped: ["INJ-02: FEMS에 같은 코드의 설비가 없습니다."],
    },
  });
  fireEvent.change(await screen.findByLabelText("가져올 월"), {
    target: { value: "2026-09" },
  });
  fireEvent.click(screen.getByRole("button", { name: "MES에서 가져오기" }));
  await waitFor(() =>
    expect(sent(fetcher, "POST", "/production-records/import")).toHaveLength(1),
  );
  expect(
    await screen.findByText(/12건을 초안으로 가져왔습니다/),
  ).toBeInTheDocument();
  expect(screen.getByText(/건너뛴 1건/)).toBeInTheDocument();
});
