// AG-07 FEMS 사이드바 모바일 접는 메뉴 테스트. 항목별로 나눈다.
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { FemsLayout, femsScreens } from "./FemsLayout";

const session = {
  actorKind: "GUEST",
  workspaceId: 10,
  generationId: 20,
  roles: ["GUEST"],
  expiresAt: "2026-09-25T00:00:00+09:00",
  csrfToken: "test-csrf",
};

function mockApi() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const data = url.endsWith("/sessions/current")
      ? session
      : url.endsWith("/workspace/modules")
        ? ["core", "mes", "erp", "fems"].map((moduleKey) => ({
            moduleKey,
            enabled: true,
            updatedAt: null,
          }))
        : [];
    return new Response(
      JSON.stringify({ data, page: { offset: 0, limit: 20, total: 0 } }),
      { status: 200 },
    );
  });
}

function show(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/fems" element={<FemsLayout />}>
          <Route path="dashboard" element={<div>대시보드 본문</div>} />
          <Route path="readings" element={<div>계측 조회 본문</div>} />
          <Route path="allocations" element={<div>설비별 배분 본문</div>} />
          <Route path="emissions" element={<div>배출량 현황 본문</div>} />
          <Route path="targets" element={<div>목표 대비 실적 본문</div>} />
          <Route path="equipments" element={<div>설비 본문</div>} />
          <Route path="energy-sources" element={<div>에너지원 본문</div>} />
          <Route path="tariffs" element={<div>요금제 본문</div>} />
        </Route>
        <Route path="/home" element={<div>포털 홈 본문</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

it("aside의 aria-label='FEMS 메뉴'와 femsScreens 항목들을 그대로 유지한다", () => {
  mockApi();
  const { container } = show("/fems/dashboard");
  const aside = screen.getByRole("complementary", { name: "FEMS 메뉴" });
  expect(aside).toBeInTheDocument();
  const links = container.querySelectorAll('a[href^="/fems/"]');
  expect(links).toHaveLength(femsScreens.length);
});

it("summary에 현재 화면 이름(ID와 라벨)이 보인다 - 대시보드", () => {
  mockApi();
  const { container } = show("/fems/dashboard");
  const summary = container.querySelector("summary");
  expect(summary).toBeInTheDocument();
  expect(summary?.textContent).toBe("FEMS 메뉴 · F-01 대시보드");
});

it("summary에 현재 화면 이름(ID와 라벨)이 보인다 - 계측 조회", () => {
  mockApi();
  const { container } = show("/fems/readings");
  const summary = container.querySelector("summary");
  expect(summary?.textContent).toBe("FEMS 메뉴 · F-02 계측 조회");
});

it("summary에 현재 화면 이름(ID와 라벨)이 보인다 - 설비별 배분", () => {
  mockApi();
  const { container } = show("/fems/allocations");
  const summary = container.querySelector("summary");
  expect(summary?.textContent).toBe("FEMS 메뉴 · F-03 설비별 배분");
});

it("summary에 현재 화면 이름(ID와 라벨)이 보인다 - 배출량 현황", () => {
  mockApi();
  const { container } = show("/fems/emissions");
  const summary = container.querySelector("summary");
  expect(summary?.textContent).toBe("FEMS 메뉴 · F-04 배출량 현황");
});

it("summary에 현재 화면 이름(ID와 라벨)이 보인다 - 목표 대비 실적", () => {
  mockApi();
  const { container } = show("/fems/targets");
  const summary = container.querySelector("summary");
  expect(summary?.textContent).toBe("FEMS 메뉴 · F-07 목표 대비 실적");
});

it("summary에 현재 화면 이름(ID와 라벨)이 보인다 - 설비", () => {
  mockApi();
  const { container } = show("/fems/equipments");
  const summary = container.querySelector("summary");
  expect(summary?.textContent).toBe("FEMS 메뉴 · F-10 설비");
});

it("summary에 현재 화면 이름(ID와 라벨)이 보인다 - 에너지원", () => {
  mockApi();
  const { container } = show("/fems/energy-sources");
  const summary = container.querySelector("summary");
  expect(summary?.textContent).toBe("FEMS 메뉴 · F-11 에너지원");
});

it("summary에 현재 화면 이름(ID와 라벨)이 보인다 - 요금제", () => {
  mockApi();
  const { container } = show("/fems/tariffs");
  const summary = container.querySelector("summary");
  expect(summary?.textContent).toBe("FEMS 메뉴 · F-14 요금제");
});

it("메뉴 링크를 누르면 details가 닫힌다", () => {
  mockApi();
  const { container } = show("/fems/dashboard");
  const details = container.querySelector("details") as HTMLDetailsElement;
  expect(details).toBeInTheDocument();
  expect(details.open).toBe(true);

  // 메뉴 링크(계측 조회)를 누른다
  const targetLink = screen.getByRole("link", { name: /F-02/ });
  fireEvent.click(targetLink);

  // details가 닫힌다
  expect(details.open).toBe(false);
});

it("다른 앱 링크를 눌러도 details가 닫힌다", () => {
  mockApi();
  const { container } = show("/fems/dashboard");
  const details = container.querySelector("details") as HTMLDetailsElement;
  expect(details.open).toBe(true);

  const homeLink = screen.getByRole("link", { name: "포털 홈" });
  fireEvent.click(homeLink);

  expect(details.open).toBe(false);
});
