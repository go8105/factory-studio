import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { Organization, People, flattenTree } from "./Organization";
import { RoleContext, type HrPreview } from "./common";
vi.mock("../app/session", () => ({
  useSession: () => ({
    session: { workspaceId: 1, generationId: 1, csrfToken: "synthetic" },
    fail: vi.fn(),
  }),
}));
const data: HrPreview = {
  available: true,
  digest: "a".repeat(64),
  departments: [
    {
      code: "ROOT",
      name: "합성 본부",
      parentCode: null,
      isActive: true,
      headEmployeeCode: null,
    },
    {
      code: "TEAM",
      name: "생산팀",
      parentCode: "ROOT",
      isActive: true,
      headEmployeeCode: "E01",
    },
  ],
  employees: [
    {
      employeeCode: "E01",
      name: "합성 사원",
      departmentCode: "TEAM",
      departmentName: "생산팀",
      status: "ACTIVE",
      gradeName: "과장",
      dutyName: null,
      isHead: false,
    },
  ],
  organizations: [
    {
      id: "5",
      code: "OLD",
      name: "이전 조직",
      parentId: null,
      isActive: true,
      hrSyncedAt: "2026-10-01T00:00:00Z",
    },
  ],
  people: [],
};
function reply(value: unknown, page?: unknown) {
  return new Response(JSON.stringify({ data: value, page }), { status: 200 });
}
function show(node: React.ReactNode) {
  return render(
    <MemoryRouter>
      <RoleContext.Provider
        value={{
          person: "",
          setPerson: vi.fn(),
          people: [],
          reload: vi.fn(),
          busy: false,
          setBusy: vi.fn(),
        }}
      >
        {node}
      </RoleContext.Provider>
    </MemoryRouter>,
  );
}
it("reviews selected HR employees and sends source digest once confirmed", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (url, options) => {
      if (String(url).includes("people-master")) return reply([], { total: 0 });
      if (options?.method === "POST")
        return reply({ created: 1, updated: 0, departments: 2 });
      return reply(data);
    });
  show(<People />);
  fireEvent.click(screen.getByRole("button", { name: "HR에서 가져오기" }));
  const employee = await screen.findByRole("checkbox", { name: /합성 사원/ });
  expect(fetch.mock.calls.some(([, o]) => o?.method === "POST")).toBe(false);
  fireEvent.click(employee);
  expect(screen.getByText("담당자 1명 신규 / 0명 갱신")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "확인한 내용 가져오기" }));
  await screen.findByText(/담당자 신규 1명·갱신 0명 반영/);
  const writes = fetch.mock.calls.filter(([, o]) => o?.method === "POST");
  expect(writes).toHaveLength(1);
  expect(JSON.parse(String(writes[0][1]?.body))).toEqual({
    previewDigest: data.digest,
    employeeCodes: ["E01"],
  });
});
it("HR off shows last snapshot and does not claim an empty current HR tree", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    reply({
      ...data,
      available: false,
      departments: null,
      employees: null,
      digest: null,
    }),
  );
  show(<Organization />);
  await screen.findByText("이전 조직");
  expect(screen.getByText(/HR 조회 불가/)).toBeInTheDocument();
  expect(screen.queryByText("표시할 조직이 없습니다.")).not.toBeInTheDocument();
});
it("switches between current HR and imported GW without a write", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(data));
  show(<Organization />);
  await screen.findByText("합성 본부");
  fireEvent.click(
    screen.getByRole("checkbox", { name: "가져온 GW 조직 보기" }),
  );
  await screen.findByText("이전 조직");
  expect(screen.queryByText("합성 본부")).not.toBeInTheDocument();
  expect(
    fetch.mock.calls.every(([, o]) => !o?.method || o.method === "GET"),
  ).toBe(true);
});
it("standard person master keeps version and hides unsupported deletion", async () => {
  const row = {
    id: "12",
    code: "LOCAL",
    name: "합성",
    jobRole: "STAFF",
    isActive: true,
    version: 7,
    hrEmployeeCode: null,
    organizationName: null,
    hrStatus: "UNLINKED",
  };
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (_url, options) =>
      options?.method === "PATCH" ? reply(row) : reply([row], { total: 1 }),
    );
  show(<People />);
  fireEvent.click(await screen.findByRole("button", { name: "수정" }));
  expect(
    screen.queryByRole("button", { name: "삭제" }),
  ).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("직무"), {
    target: { value: "MANAGER" },
  });
  fireEvent.click(screen.getByRole("button", { name: "수정 저장" }));
  await waitFor(() =>
    expect(fetch.mock.calls.some(([, o]) => o?.method === "PATCH")).toBe(true),
  );
  const body = fetch.mock.calls.find(([, o]) => o?.method === "PATCH")![1]
    ?.body;
  expect(JSON.parse(String(body))).toEqual({
    jobRole: "MANAGER",
    expectedVersion: 7,
  });
});
it("tree handles deep hierarchy and rejects cycles and missing parents", () => {
  expect(flattenTree(data.departments!)?.map((n) => n.depth)).toEqual([0, 1]);
  expect(
    flattenTree([{ ...data.departments![0], parentCode: "ROOT" }]),
  ).toBeNull();
  expect(
    flattenTree([{ ...data.departments![0], parentCode: "MISSING" }]),
  ).toBeNull();
  const deep = Array.from({ length: 2000 }, (_, i) => ({
    code: String(i),
    name: String(i),
    parentCode: i ? String(i - 1) : null,
    isActive: true,
    headEmployeeCode: null,
  }));
  expect(flattenTree(deep)?.at(-1)?.depth).toBe(1999);
});
