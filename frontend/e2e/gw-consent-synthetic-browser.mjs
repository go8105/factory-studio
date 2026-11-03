/* global process, URL, document, innerWidth, console, setTimeout, clearTimeout */
// Product UI with deny-by-default synthetic API interception; no account/DB access.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { chromium, expect } from "@playwright/test";

const root = path.resolve(import.meta.dirname, "../..");
const port = 5365;
const base = `http://localhost:${port}`;
const out = path.join(root, "outputs/gw-readiness-02-phase76");
await fs.mkdir(out, { recursive: true });
// Refuse reuse of an existing listener. Only stop the child created below.
const probe = createServer();
await new Promise((resolve, reject) => {
  probe.once("error", reject);
  probe.listen(port, "localhost", resolve);
});
await new Promise((resolve) => probe.close(resolve));
const vite = spawn(process.execPath, ["node_modules/vite/bin/vite.js"], {
  cwd: path.join(root, "frontend"),
  env: {
    ...process.env,
    FS_SMOKE_WEB_PORT: String(port),
    FS_SMOKE_API_PORT: "9",
  },
  stdio: ["ignore", "pipe", "pipe"],
});
let browser;
const report = {
  kind: "GW_SYNTHETIC_CONSENT_BROWSER_REVIEW",
  version: 1,
  syntheticApi: true,
  realApi: false,
  realAuthentication: false,
  realDevice: false,
  signedEvidence: false,
  ready: false,
  liveCompanyAcceptance: false,
  releaseAuthorized: false,
  checks: [],
};
try {
  await new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error("owned Vite startup timeout")),
      30000,
    );
    vite.once("exit", () => {
      clearTimeout(timer);
      reject(new Error("owned Vite failed to start"));
    });
    vite.stdout.on("data", (data) => {
      if (String(data).includes(`localhost:${port}`)) {
        clearTimeout(timer);
        resolve();
      }
    });
  });
  browser = await chromium.launch({ channel: "chrome", headless: true });
  for (const width of [1440, 390]) {
    const context = await browser.newContext({
      viewport: { width, height: width === 390 ? 844 : 1000 },
      serviceWorkers: "block",
    });
    const unexpected = [];
    const pageErrors = [];
    const calls = [];
    const state = {
      id: "77",
      version: 1,
      binding: "PENDING",
      mode: "conflict",
      readError: false,
      stepUp: false,
      held: undefined,
    };
    const envelope = (route, data, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(status < 400 ? { data } : { error: data }),
      });
    context.on("page", (p) => {
      p.on("pageerror", (e) => pageErrors.push(e.message));
      p.on("dialog", (d) => d.accept());
    });
    await context.route("**/*", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.origin !== base) {
        unexpected.push("remote request blocked");
        return route.abort();
      }
      if (!url.pathname.startsWith("/api/")) return route.continue();
      const pathname = url.pathname;
      const method = request.method();
      if (pathname === "/api/v1/core/sessions/current" && method === "GET")
        return envelope(route, {
          actorKind: "MEMBER",
          workspaceId: 1,
          generationId: 2,
          roles: [],
          csrfToken: "synthetic-only",
          expiresAt: null,
        });
      if (pathname === "/api/v1/core/workspace/menus" && method === "GET")
        return envelope(route, { menuIds: [], sidebarMode: "all", version: 1 });
      if (pathname === "/api/v1/core/security/me" && method === "GET")
        return envelope(route, {
          mfaRegistered: true,
          recoveryCodesRemaining: 8,
          assurance: "MFA",
        });
      if (pathname === "/api/v1/core/security/step-up" && method === "POST") {
        state.stepUp = true;
        return envelope(route, {});
      }
      if (pathname === "/api/v1/gw/companies" && method === "GET")
        return envelope(route, [
          { id: 11, name: "합성 동의 검증 회사" },
          { id: 12, name: "합성 다른 회사" },
        ]);
      if (pathname === "/api/v1/gw/me" && method === "GET")
        return envelope(route, {
          company: {
            id: Number(url.searchParams.get("companyId")),
            name: "합성 동의 검증 회사",
          },
          person: { id: "501", name: "합성 직원", isActive: true },
          bindingStatus: state.binding,
          roles: [],
          authzVersion: 1,
          setupRequired: false,
          companyOwner: false,
          businessReady: true,
        });
      if (pathname === "/api/v1/gw/me/binding" && method === "GET")
        return state.readError
          ? envelope(
              route,
              {
                code: "SYNTHETIC_READ_FAILURE",
                message: "합성 요청 조회 실패",
              },
              500,
            )
          : envelope(route, {
              id: state.id,
              version: state.version,
              state: state.binding,
              name: "합성 직원",
              hrEmployeeCode: "SYN-501",
              organizationName: "합성 부서",
            });
      if (pathname === "/api/v1/gw/me/binding/accept" && method === "POST") {
        calls.push({
          url: url.pathname + url.search,
          body: request.postData(),
          key: request.headers()["idempotency-key"],
        });
        if (state.mode === "network") return route.abort("failed");
        if (state.mode === "deferred") {
          await new Promise((resolve) => {
            state.held = resolve;
          });
          // Replay of the older command must not turn the newer request ACTIVE.
          return envelope(route, { id: "78" });
        }
        return envelope(
          route,
          state.mode === "step-up"
            ? { code: "STEP_UP_REQUIRED", message: "합성 추가 본인 확인 필요" }
            : { code: "VERSION_CONFLICT", message: "합성 요청 버전 충돌" },
          state.mode === "step-up" ? 403 : 409,
        );
      }
      unexpected.push(`${method} ${pathname}`);
      return envelope(
        route,
        {
          code: "SYNTHETIC_UNEXPECTED_ROUTE",
          message: "허용되지 않은 합성 경로",
        },
        501,
      );
    });
    const page = await context.newPage();
    const checkbox = page.getByLabel("위 사번·이름이 본인임을 확인했습니다.");
    const accept = page.getByRole("button", {
      name: "본인 연결 동의",
      exact: true,
    });
    const refresh = page.getByRole("button", {
      name: "본인 연결 요청 다시 확인",
      exact: true,
    });
    const retry = page.getByRole("button", {
      name: "같은 동의 요청 결과 확인",
      exact: true,
    });
    async function keyActivate(locator, key = "Enter") {
      await locator.focus();
      await expect(locator).toBeFocused();
      await locator.press(key);
    }
    async function capture(name) {
      if (await checkbox.count()) {
        const box = await checkbox.boundingBox();
        assert.ok(
          box && box.width <= 24 && box.height <= 24,
          "compact consent checkbox",
        );
      }
      await expect
        .poll(() =>
          page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        )
        .toBe(true);
      await page.screenshot({
        path: path.join(out, `${width}-${name}.png`),
        fullPage: true,
      });
    }
    await page.goto(base + "/gw/dashboard?companyId=11&open=old&filter=keep");
    await expect(checkbox).toBeVisible();
    await expect(accept).toBeDisabled();
    await checkbox.focus();
    await page.keyboard.press("Shift+Tab");
    await expect(refresh).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(checkbox).toBeFocused();
    await page.keyboard.press("Space");
    await page.keyboard.press("Tab");
    await expect(accept).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(
      page.getByText(/연결 요청이 변경되어 동의하지 못했습니다/),
    ).toBeVisible();
    await expect(checkbox).not.toBeChecked();
    await expect(accept).toBeDisabled();
    await capture("conflict");
    state.id = "78";
    state.version = 2;
    state.mode = "network";
    await keyActivate(refresh);
    await expect(checkbox).toBeEnabled();
    await keyActivate(checkbox, "Space");
    await keyActivate(accept);
    await expect(retry).toBeVisible();
    assert.equal(calls.length, 2);
    const original = calls[1];
    assert.ok(original.key);
    assert.notEqual(original.key, calls[0].key);
    state.id = "79";
    state.version = 3;
    state.readError = true;
    await keyActivate(refresh);
    await expect(
      page.getByText("합성 요청 조회 실패", { exact: true }),
    ).toBeVisible();
    await expect(checkbox).toHaveCount(0);
    await expect(retry).toBeEnabled();
    state.readError = false;
    await keyActivate(refresh);
    await expect(checkbox).toBeVisible();
    await expect(checkbox).not.toBeChecked();
    await expect(checkbox).toBeDisabled();
    assert.equal(calls.length, 2, "GET must not resend acceptance");
    await keyActivate(
      page.locator("summary").filter({ hasText: "사용 공간 선택" }),
    );
    const other = page.getByRole("link", {
      name: "합성 다른 회사",
      exact: true,
    });
    await keyActivate(other);
    await keyActivate(
      page.getByRole("button", { name: "변경 버리기", exact: true }),
    );
    assert.equal(new URL(page.url()).searchParams.get("companyId"), "11");
    await capture("uncertain");
    state.mode = "step-up";
    await keyActivate(retry);
    const securityLink = page.getByRole("link", {
      name: "다른 탭에서 내 계정 보안 열기",
    });
    await expect(securityLink).toBeVisible();
    await capture("step-up");
    const popupPromise = context.waitForEvent("page");
    await keyActivate(securityLink);
    const security = await popupPromise;
    await security.waitForLoadState("domcontentloaded");
    await expect(
      security.getByRole("heading", { name: "인증 앱 등록됨" }),
    ).toBeVisible();
    await security.getByLabel("추가 확인 번호", { exact: true }).fill("123456");
    await keyActivate(
      security.getByRole("button", { name: "본인 확인", exact: true }),
    );
    await expect(
      security.getByText("본인 확인을 마쳤습니다. 5분 안에 처리하세요."),
    ).toBeVisible();
    assert.equal(state.stepUp, true);
    await security.close();
    await page.bringToFront();
    state.mode = "deferred";
    await keyActivate(retry);
    await expect.poll(() => !!state.held).toBe(true);
    await expect(retry).toBeDisabled();
    await expect(refresh).toBeDisabled();
    await expect(checkbox).toBeDisabled();
    await keyActivate(other);
    if (
      await page
        .getByRole("button", { name: "변경 버리기", exact: true })
        .isVisible()
    )
      await keyActivate(
        page.getByRole("button", { name: "변경 버리기", exact: true }),
      );
    assert.equal(new URL(page.url()).searchParams.get("companyId"), "11");
    assert.equal(calls.length, 4);
    state.held();
    await expect(retry).toHaveCount(0);
    await expect(checkbox).toBeEnabled();
    await expect(checkbox).not.toBeChecked();
    assert.equal(state.binding, "PENDING");
    for (const call of calls.slice(1)) assert.deepEqual(call, original);
    await capture("replay-current-pending");
    // A fresh command after replay has a different key and current ID/version.
    state.mode = "step-up";
    await keyActivate(checkbox, "Space");
    await keyActivate(accept);
    await expect(
      page.getByText(/추가 본인 확인이 필요합니다. 내 계정 보안/),
    ).toBeVisible();
    await expect(checkbox).toBeChecked();
    assert.notEqual(calls[4].key, original.key);
    assert.deepEqual(JSON.parse(calls[4].body), {
      bindingId: "79",
      expectedVersion: 3,
    });
    state.binding = "CANCELLED";
    await keyActivate(
      page.getByRole("button", { name: "회사 연결 다시 확인", exact: true }),
    );
    await expect(checkbox).toHaveCount(0);
    await expect(accept).toHaveCount(0);
    await expect(
      page.getByText(/GW 조직 관리자에게 직원 연결 요청을 문의하세요/),
    ).toBeVisible();
    await capture("cancelled");
    assert.deepEqual(unexpected, []);
    assert.deepEqual(pageErrors, []);
    report.checks.push({
      viewport: width,
      keyboard: true,
      tabOrder: true,
      compactConsentLayout: true,
      conflict: true,
      getDoesNotResubmit: true,
      changedRequestCannotReplacePendingCommand: true,
      sameBodyAndKey: true,
      companySelectionBlocked: true,
      pendingInputsBlocked: true,
      syntheticPopupStepUp: true,
      realStepUpVerified: false,
      replayDoesNotActivateNewRequest: true,
      cancellationHidesConsent: true,
      overflow: false,
      pageErrors: 0,
      unexpectedRequests: 0,
    });
    await context.close();
  }
  await fs.writeFile(
    path.join(out, "report.json"),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(
    "Synthetic browser review passed: 1440/390; real API/authentication not verified.",
  );
} finally {
  await browser?.close();
  vite.kill("SIGTERM");
  if (vite.exitCode === null)
    await new Promise((resolve) => vite.once("exit", resolve));
}
