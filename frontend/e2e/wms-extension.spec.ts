import { expect, test, type Page } from "@playwright/test";
const W = "/api/v1/wms";
async function data(page: Page, path: string) {
  const r = await page.request.get(path);
  expect(r.ok()).toBeTruthy();
  return (await r.json()).data;
}
async function command(page: Page, path: string, body: unknown) {
  const s = await data(page, "/api/v1/core/sessions/current");
  const r = await page.request.post(W + path, {
    data: body,
    headers: {
      "X-CSRF-Token": s.csrfToken,
      "Idempotency-Key": crypto.randomUUID(),
    },
  });
  expect(r.ok(), await r.text()).toBeTruthy();
  return (await r.json()).data;
}
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
});

test("3D 도착은 원장0, 검수95/3/2와 새로고침 복구", async ({ page }) => {
  const n = (await data(page, W + "/inbound-notices")).rows.find(
    (x: { status: string }) => x.status === "PLANNED",
  );
  const before = await data(page, W + "/stock?itemCode=RM-PBT");
  await page.goto(`/factory?inbound=${n.id}`);
  const start = page.getByRole("button", { name: "트럭 도착 시연" });
  await expect(start).toBeEnabled({ timeout: 20000 });
  await start.click();
  await expect(
    page.getByRole("link", { name: "도착 기록·검수 열기" }),
  ).toBeVisible({ timeout: 15000 });
  expect(await data(page, W + "/stock?itemCode=RM-PBT")).toEqual(before);
  await page.reload();
  await expect(
    page.getByRole("link", { name: "도착 기록·검수 열기" }),
  ).toBeVisible();
  await expect(page.getByText("3D 공간 준비 중…", { exact: true })).toHaveCount(
    0,
  );
  await page.screenshot({
    path: "../work/fs026/truck-desktop.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "도착 기록·검수 열기" }).click();
  const p = page.getByRole("dialog", { name: n.noticeNo });
  await p.getByLabel("합격", { exact: true }).fill("95");
  await p.getByLabel("격리", { exact: true }).fill("3");
  await p.getByLabel("검수 사유").fill("합성 이물·운송 부족");
  await p.getByRole("button", { name: "검수 결과 확인" }).click();
  await expect(p).toContainText("부족 2.000");
  await p.getByRole("button", { name: "검수 확정", exact: true }).click();
  await expect(p.getByRole("link", { name: "검수 전표 보기" })).toBeVisible();
  const after = await data(page, W + "/stock?itemCode=RM-PBT");
  expect(
    Number(after.totals[0].normalOnHand) -
      Number(before.totals[0].normalOnHand),
  ).toBe(95);
  expect(
    Number(after.totals[0].quarantinedOnHand) -
      Number(before.totals[0].quarantinedOnHand),
  ).toBe(3);
  await page.reload();
  await expect(page.getByRole("dialog", { name: n.noticeNo })).toContainText(
    "검수 완료",
  );
});

test("예정 등록·편집·전량 부족, 응답 유실 뒤 서버 복구", async ({ page }) => {
  await page.goto("/wms/inbounds");
  await page
    .getByRole("button", { name: "입고 예정 등록", exact: true })
    .click();
  const p = page.getByRole("dialog");
  await p.getByLabel("업무 중복 방지 번호").fill("BROWSER-INBOUND");
  await p
    .getByRole("combobox", { name: "품목", exact: true })
    .selectOption({ label: "RM-PBT · KG" });
  await p.getByLabel("예정 수량").fill("100");
  await p
    .getByRole("combobox", { name: "정상 위치", exact: true })
    .selectOption({ label: "R-A01 원자재 기본 보관" });
  await p.getByRole("button", { name: "예정 등록", exact: true }).click();
  await p.getByRole("button", { name: "예정 편집" }).click();
  await page.getByLabel("차량", { exact: true }).fill("합성차량");
  await page.getByRole("button", { name: "예정 저장" }).click();
  await p.getByRole("button", { name: "도착 처리", exact: true }).click();
  await p.getByLabel("합격", { exact: true }).fill("0");
  await p.getByLabel("검수 사유").fill("전량 미도착");
  await p.getByRole("button", { name: "검수 결과 확인" }).click();
  await expect(p).toContainText("입고 재고 0");
  await page.route(
    "**/inbound-notices/*/inspect",
    async (route) => {
      await route.fetch();
      await route.abort("failed");
    },
    { times: 1 },
  );
  await p.getByRole("button", { name: "검수 확정", exact: true }).click();
  await expect(p).toContainText("응답을 확인하지 못했습니다");
  await p.getByRole("button", { name: "서버 상태 다시 확인" }).click();
  await expect(p).toContainText("검수 완료");
  await expect(p.getByRole("link", { name: "검수 전표 보기" })).toHaveCount(0);
});

test("예약 부족 입력 보존·등록·해제", async ({ page }) => {
  const r = (await data(page, W + "/stock")).rows.find(
    (x: { itemCode: string; locationType: string }) =>
      x.itemCode === "RM-PBT" && x.locationType === "NORMAL",
  );
  await page.goto("/wms/reservations");
  await page.getByRole("button", { name: "예약 등록", exact: true }).click();
  const p = page.getByRole("dialog", { name: "예약 등록" });
  await p.getByLabel("업무 중복 방지 번호").fill("BROWSER-RESERVE");
  await p
    .getByLabel("품목·위치·LOT")
    .selectOption(`${r.itemId}:${r.locationId}:`);
  await p.getByLabel("예약 수량").fill("999999999");
  await p.getByRole("button", { name: "예약 등록", exact: true }).click();
  await expect(p).toContainText("예약 가능한 수량이 부족");
  await expect(p.getByLabel("예약 수량")).toHaveValue("999999999");
  await p.getByLabel("예약 수량").fill("5");
  await p.getByRole("button", { name: "예약 등록", exact: true }).click();
  const d = page.getByRole("dialog");
  await expect(d).toContainText("원자재 예약은 등록·해제만");
  await d.getByLabel("예약 해제 사유").fill("일정 변경");
  await d.getByRole("button", { name: "예약 해제", exact: true }).click();
  await expect(d).toContainText("일정 변경");
  await expect(
    d.getByRole("button", { name: "예약 해제", exact: true }),
  ).toHaveCount(0);
});

test("완제품 예약 대조·소진과 sync 중복 차감 방지", async ({ page }) => {
  const src = (await data(page, W + "/reservation-sources")).shipments.find(
    (s: { shipmentNo: string }) => s.shipmentNo === "SH-0004",
  );
  for (const packing of new Set<string>(
    src.lines.map((l: { packingNo: string }) => l.packingNo).filter(Boolean),
  ))
    await command(page, "/sources/sync", {
      kind: "MES_RECEIPT",
      sourceKeys: ["MES:RECEIPT:" + packing],
    });
  const receipts = await data(page, W + "/sources?kind=MES_RECEIPT&state=all");
  const lots = new Set<string>(
    receipts.rows
      .filter((s: { sourceRef: string }) =>
        src.lines.some(
          (l: { packingNo: string }) => l.packingNo === s.sourceRef,
        ),
      )
      .flatMap((s: { lines: { lotNo: string }[] }) =>
        s.lines.map((l) => l.lotNo),
      ),
  );
  const rows = (await data(page, W + "/stock")).rows.filter(
    (r: { lotNo: string; onHand: string }) =>
      lots.has(r.lotNo) && Number(r.onHand) > 0,
  );
  const r = await command(page, "/reservations", {
    businessKey: "BROWSER-CONSUME",
    shipmentOrderRef: src.shipmentOrderNo,
    lines: rows.map(
      (x: {
        itemId: number;
        locationId: number;
        lotNo: string;
        onHand: string;
      }) => ({
        itemId: x.itemId,
        locationId: x.locationId,
        lotNo: x.lotNo,
        quantity: x.onHand,
      }),
    ),
  });
  await page.goto(`/wms/reservations?open=${r.id}`);
  const p = page.getByRole("dialog");
  await p.getByLabel("확정 출하").selectOption(src.sourceKey);
  await expect(p).toContainText("전량 대조 일치");
  await p.getByRole("button", { name: "출하 연결·반영 확정" }).click();
  await expect(p.getByRole("link", { name: "출고 전표 보기" })).toBeVisible();
  const after = await data(page, W + "/stock");
  await command(page, "/sources/sync", {
    kind: "ERP_SHIPMENT",
    sourceKeys: [src.sourceKey],
  });
  expect(await data(page, W + "/stock")).toEqual(after);
});

test("ERP 꺼짐·수동 취소·모바일 도움말", async ({ page }) => {
  const s = await data(page, "/api/v1/core/sessions/current");
  expect(
    (
      await page.request.patch("/api/v1/core/workspace/modules/erp", {
        data: { enabled: false },
        headers: {
          "X-CSRF-Token": s.csrfToken,
          "Idempotency-Key": crypto.randomUUID(),
        },
      })
    ).ok(),
  ).toBeTruthy();
  await page.setViewportSize({ width: 360, height: 844 });
  const n = (await data(page, W + "/inbound-notices")).rows.find(
    (n: { status: string }) => n.status === "ARRIVED",
  );
  await page.goto(`/wms/inbounds?open=${n.id}`);
  const p = page.getByRole("dialog");
  await expect(p).toContainText("수동 입고는 가능합니다");
  await p.getByLabel("취소·연결 해제 사유").fill("운송 취소");
  await p.getByRole("button", { name: "입고 예정 취소" }).click();
  await expect(p.getByRole("button", { name: "입고 예정 취소" })).toHaveCount(
    0,
  );
  await page.screenshot({
    path: "../work/fs026/inbound-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.goto("/help/portal/wms-flow");
  await expect(
    page.getByRole("heading", {
      name: "입고부터 출고까지 · WMS와 3D 트럭 체험",
      exact: true,
    }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("트럭 도착 통신 실패는 성공 표시 없이 재조회·재시도", async ({ page }) => {
  const n = (await data(page, W + "/inbound-notices")).rows.find(
    (x: { status: string }) => x.status === "PLANNED",
  );
  await page.goto(`/factory?inbound=${n.id}`);
  await page.route("**/inbound-notices/*/arrive", (r) => r.abort("failed"), {
    times: 1,
  });
  const start = page.getByRole("button", { name: "트럭 도착 시연" });
  await expect(start).toBeEnabled({ timeout: 20000 });
  await start.click();
  await expect(
    page.getByRole("combobox", { name: "입고 예정", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByText("도착 저장 확인 필요", { exact: true }),
  ).toBeVisible({ timeout: 10000 });
  await expect(
    page.getByRole("link", { name: "도착 기록·검수 열기" }),
  ).toHaveCount(0);
  expect((await data(page, W + `/inbound-notices/${n.id}`)).status).toBe(
    "PLANNED",
  );
  await page.getByRole("button", { name: "같은 도착 요청 다시 확인" }).click();
  await expect(
    page.getByRole("link", { name: "도착 기록·검수 열기" }),
  ).toBeVisible();
});

test("미저장 편집 보호와 검수 매입 연결·중복 반영 방지", async ({ page }) => {
  const houses = await data(page, W + "/warehouses");
  const wh = houses.find((x: { purpose: string }) => x.purpose === "RAW");
  const items = await data(page, W + "/items");
  const locs = await data(page, W + `/warehouses/${wh.id}/locations`);
  const src = (
    await data(page, W + "/sources?kind=ERP_PURCHASE&state=all")
  ).rows.find((s: { sourceRef: string }) => s.sourceRef === "PI-0004");
  const n = await command(page, "/inbound-notices", {
    businessKey: "BROWSER-LINK",
    warehouseId: wh.id,
    expectedOn: "2026-09-30",
    lines: src.lines.map(
      (l: { itemCode: string; qty: string; unit: string }) => {
        const i = items.find(
          (i: { itemCode: string }) => i.itemCode === l.itemCode,
        );
        const factor =
          l.unit === i.baseUnit
            ? 1
            : Number(
                i.conversions.find(
                  (c: { fromUnit: string }) => c.fromUnit === l.unit,
                ).factor,
              );
        return {
          itemId: i.id,
          expectedQty: String(Number(l.qty) * factor),
          normalLocationId: locs.find(
            (l: { isDefault: boolean }) => l.isDefault,
          ).id,
        };
      },
    ),
  });
  await page.goto(`/wms/inbounds?open=${n.id}`);
  const p = page.getByRole("dialog");
  await p.getByRole("button", { name: "예정 편집" }).click();
  await p.getByLabel("차량", { exact: true }).fill("미저장");
  await p.press("Escape");
  await expect(p).toContainText("저장하지 않은 변경");
  await p.getByRole("button", { name: "계속 편집" }).click();
  await expect(p.getByRole("button", { name: "변경 버리기" })).toHaveCount(0);
  await p.getByLabel("차량", { exact: true }).press("Escape");
  await p.getByRole("button", { name: "변경 버리기" }).click();
  await expect(p.getByRole("button", { name: "도착 처리" })).toBeVisible();
  await p
    .getByRole("combobox", { name: "확정 매입", exact: true })
    .selectOption(src.sourceKey);
  await p.getByRole("button", { name: "매입 연결", exact: true }).click();
  await p.getByRole("button", { name: "도착 처리" }).click();
  await p.getByRole("button", { name: "검수 결과 확인" }).click();
  await p.getByRole("button", { name: "검수 확정", exact: true }).click();
  await expect(p.getByRole("link", { name: "검수 전표 보기" })).toBeVisible();
  const after = await data(page, W + "/stock");
  const synced = await command(page, "/sources/sync", {
    kind: "ERP_PURCHASE",
    sourceKeys: [src.sourceKey],
  });
  expect(synced.inspected).toBe(1);
  expect(await data(page, W + "/stock")).toEqual(after);
});
