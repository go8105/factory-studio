/* global process, URL, setTimeout, document, innerWidth, console */
// Synthetic local security acceptance. Never use production account credentials.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { chromium } from "@playwright/test";
const root = path.resolve(import.meta.dirname, "../..");
const privatePath = process.env.GW_SECURITY_BROWSER_CREDENTIALS;
if (!privatePath)
  throw new Error("GW_SECURITY_BROWSER_CREDENTIALS is required");
const credentials = JSON.parse(await fs.readFile(privatePath, "utf8"));
assert(credentials.login.startsWith("synthetic-"), "synthetic accounts only");
const base = process.env.GW_SECURITY_BROWSER_ORIGIN || "http://localhost:5362";
assert(
  ["localhost", "127.0.0.1"].includes(new URL(base).hostname),
  "local acceptance only",
);
const out = path.resolve(
  process.env.GW_SECURITY_BROWSER_OUTPUT ||
    path.join(root, "work/gw-readiness-02/screens"),
);
await fs.mkdir(out, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
function otp(seed) {
  return execFileSync(
    path.join(root, "backend/.venv/bin/python"),
    ["-c", "import sys,pyotp;print(pyotp.TOTP(sys.stdin.read()).now())"],
    { input: seed, encoding: "utf8" },
  ).trim();
}
async function nextOtp(seed, used) {
  for (let n = 0; n < 40; n++) {
    const code = otp(seed);
    if (code !== used) return code;
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("next OTP did not arrive");
}
async function login() {
  await page.goto(base + "/");
  await page.getByRole("button", { name: "계정이 있다면 로그인" }).click();
  await page.getByLabel("아이디", { exact: true }).fill(credentials.login);
  await page.getByLabel("비밀번호", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "로그인", exact: true }).click();
}
try {
  await login();
  await page.waitForURL("**/home");
  await page.getByRole("link", { name: "내 계정 보안", exact: true }).click();
  await page.getByLabel("현재 비밀번호").fill(credentials.password);
  await page.getByRole("button", { name: "설정 키 받기" }).click();
  const seed = await page.getByLabel("인증 앱 설정 키").inputValue();
  const used = otp(seed);
  await page.getByLabel("인증 앱 번호", { exact: true }).fill(used);
  await page.getByRole("button", { name: "번호 확인하고 등록" }).click();
  await page
    .getByRole("heading", { name: "복구 코드를 지금 보관하세요" })
    .waitFor();
  const codes = await page
    .locator(".account-security li code")
    .allTextContents();
  assert.equal(codes.length, 8);
  assert(
    await page.getByRole("button", { name: "로그인 화면으로" }).isDisabled(),
  );
  await page.getByLabel("코드 8개를 안전하게 보관했습니다").check();
  await page.getByRole("button", { name: "로그인 화면으로" }).click();
  await login();
  await page
    .getByLabel("인증 앱 번호", { exact: true })
    .fill(await nextOtp(seed, used));
  await page.getByRole("button", { name: "확인하고 계속" }).click();
  await page.waitForURL("**/home");
  await page.goto(base + "/account/security");
  await page.getByRole("heading", { name: "인증 앱 등록됨" }).waitFor();
  await page.screenshot({
    path: path.join(out, "account-security-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: path.join(out, "account-security-mobile.png"),
    fullPage: true,
  });
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  if (credentials.company) {
    await page.goto(base + "/gw/operations?companyId=" + credentials.company);
    await page
      .getByRole("heading", { name: "운영 준비", exact: true })
      .waitFor();
    await page.getByRole("button", { name: "운영 기준 검토·적용" }).click();
    const reason = page.getByLabel("적용 사유");
    await reason.fill("합성 회사 운영 기준 검토");
    await reason.press("Escape");
    await page.getByRole("button", { name: "계속 편집" }).click();
    assert(await reason.evaluate((el) => el === document.activeElement));
    await page.getByLabel("변경 내용과 영향을 검토했습니다").check();
    await page.getByRole("button", { name: "새 버전으로 적용" }).click();
    await page
      .getByRole("heading", { name: "보관·복구 기준 · 1번째 버전" })
      .waitFor();
    await page.screenshot({
      path: path.join(out, "operations-policy-mobile.png"),
      fullPage: true,
    });
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
  }

  const section = page.locator('section[aria-label="보관 검토"]');
  async function apply(name, reason) {
    await section.getByRole("button", { name, exact: true }).click();
    await page.getByLabel("보관 검토 처리 사유").fill(reason);
    await page.getByLabel("처리 범위와 원본 유지 안내를 확인했습니다").check();
    await page.getByRole("button", { name: "사유 확인하고 적용" }).click();
    await page.getByRole("dialog").waitFor({ state: "hidden" });
  }
  await apply("검토 대상 갱신", "합성 기한 도달 자료 검토");
  await section.getByText(/검토 1건 추가/).waitFor();
  await section
    .getByRole("button", { name: "보관 준비", exact: true })
    .waitFor();
  await apply("회사 전체 보존 중지", "합성 조사 자료 보존");
  await section.getByText(/회사 전체 보존 중지: 적용 중/).waitFor();
  assert.equal(
    await section
      .getByRole("button", { name: "보관 준비", exact: true })
      .count(),
    0,
  );
  await apply("회사 보존 중지 해제", "합성 조사 종료 검토");
  await apply("보관 준비", "합성 원문 확인 후 준비");
  await section.getByText(/게시글 #[0-9]+ · 보관 준비/).waitFor();
  await apply("개별 보류", "합성 개별 자료 보존");
  await section.getByText(/게시글 #[0-9]+ · 개별 보류/).waitFor();
  await apply("개별 보류 해제", "합성 개별 보류 종료 검토");
  await section.getByText(/게시글 #[0-9]+ · 검토 대기/).waitFor();
  const events = page.locator('section[aria-label="보관 검토 변경 이력"]');
  await events.getByText(/사유: 합성 조사 자료 보존/).waitFor();
  await events.getByText(/사유: 합성 조사 종료 검토/).waitFor();
  await page.screenshot({
    path: path.join(out, "retention-mobile.png"),
    fullPage: true,
  });
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: path.join(out, "retention-desktop.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "운영 기준 검토·적용" }).click();
  await page.getByLabel("적용 사유").fill("합성 보존 중지 후 기준 연속 적용");
  await page.getByLabel("변경 내용과 영향을 검토했습니다").check();
  await page.getByRole("button", { name: "새 버전으로 적용" }).click();
  await page
    .getByRole("heading", { name: "보관·복구 기준 · 2번째 버전" })
    .waitFor();
  const link = section.getByRole("link", { name: "원문 열기" });
  await link.click();
  await page
    .getByText("합성 보관 검토 공지", { exact: true })
    .first()
    .waitFor();
  assert.deepEqual(errors, []);
  const report = {
    synthetic: true,
    realDevice: false,
    pageErrors: errors,
    checks: [
      "TOTP login",
      "policy apply",
      "due target refresh",
      "company hold blocks prepare",
      "company release",
      "policy apply after hold updates",
      "archive prepare only",
      "individual hold and release",
      "reason history",
      "original source navigation",
      "390px no overflow",
    ],
  };
  await fs.writeFile(
    path.join(out, "browser-report.json"),
    JSON.stringify(report, null, 2),
  );
  console.log(JSON.stringify(report));
} finally {
  await browser.close();
}
