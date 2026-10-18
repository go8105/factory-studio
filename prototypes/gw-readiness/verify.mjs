import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "../../frontend/node_modules/playwright/index.mjs";
const out = path.resolve(
  process.env.GW_REVIEW_OUTPUT || "work/gw-readiness-01/screens",
);
await fs.mkdir(out, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
const external = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("request", (r) => {
  if (!r.url().startsWith("http://127.0.0.1:8371/")) external.push(r.url());
});
const go = async (view) => {
  await page.goto("http://127.0.0.1:8371/#" + view);
  const titles = {
    home: "내 업무",
    setup: "회사 시작 안내",
    people: "직원 연결",
    security: "내 계정 보안",
    operations: "운영 준비",
    policy: "보관·복구 기준",
    backup: "백업·복구 기록",
    retention: "보관 검토",
    recovery: "계정 복구",
    login: "로그인 단계 검토",
    help: "이 화면 사용 안내",
  };
  await page
    .getByRole("heading", { level: 1, name: titles[view], exact: true })
    .waitFor();
};
const shot = async (name) => {
  await page.evaluate(async () => {
    document.activeElement?.blur();
    window.scrollTo(0, 0);
    await new Promise(requestAnimationFrame);
    await new Promise(requestAnimationFrame);
  });
  return page.screenshot({
    path: path.join(out, name + ".png"),
    fullPage: true,
  });
};
try {
  await go("policy");
  await page.locator(".skip").focus();
  await page.keyboard.press("Enter");
  assert.equal(new URL(page.url()).hash, "#policy");
  assert.equal(
    await page.locator("#main").evaluate((e) => e === document.activeElement),
    true,
  );
  for (const view of [
    "home",
    "setup",
    "people",
    "security",
    "operations",
    "policy",
    "backup",
    "retention",
    "recovery",
    "login",
    "help",
  ]) {
    await go(view);
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
    );
    await shot("desktop-" + view);
  }
  await go("home");
  await page.getByRole("button", { name: "새 기안", exact: true }).click();
  await page.getByLabel("설명", { exact: true }).fill("유지할 합성 설명");
  await page
    .getByRole("button", { name: "초안 저장 흐름 보기", exact: true })
    .click();
  await page
    .getByText("제목을 입력하세요. 기존 설명은 유지됩니다.", { exact: true })
    .last()
    .waitFor();
  assert.equal(
    await page.getByLabel("설명", { exact: true }).inputValue(),
    "유지할 합성 설명",
  );
  await shot("draft-error");
  await page.getByLabel("제목", { exact: true }).fill("합성 기안");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "계속 편집", exact: true }).click();
  assert.equal(
    await page.getByLabel("제목", { exact: true }).inputValue(),
    "합성 기안",
  );
  assert.equal(
    await page
      .getByLabel("제목", { exact: true })
      .evaluate((e) => e === document.activeElement),
    true,
  );
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "변경 버리기", exact: true }).click();
  assert.equal(
    await page
      .getByRole("button", { name: "새 기안", exact: true })
      .evaluate((e) => e === document.activeElement),
    true,
  );
  await go("security");
  await page
    .getByRole("button", { name: "인증 앱 등록 흐름 보기", exact: true })
    .click();
  await page.getByLabel("인증 번호", { exact: true }).fill("12");
  await page
    .getByRole("button", { name: "등록 확인 흐름 보기", exact: true })
    .click();
  assert.equal(
    await page
      .getByLabel("인증 번호", { exact: true })
      .getAttribute("aria-invalid"),
    "true",
  );
  await shot("mfa-error");
  await page.getByLabel("인증 번호", { exact: true }).fill("123456");
  await page
    .getByRole("button", { name: "등록 확인 흐름 보기", exact: true })
    .click();
  await page.getByText("등록 완료 장면", { exact: true }).waitFor();
  await page
    .getByRole("button", { name: "백업 코드 보관 흐름 보기", exact: true })
    .click();
  assert.equal(
    await page
      .getByRole("button", { name: "보관 확인 흐름 마치기" })
      .isEnabled(),
    false,
  );
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "보관 확인 흐름 마치기" }).click();
  await go("policy");
  await page
    .getByRole("button", { name: "기준 검토·수정", exact: true })
    .click();
  await page.getByLabel("검토 사유", { exact: true }).fill("합성 정책 검토");
  await page.getByLabel("허용 데이터 손실 (분)", { exact: true }).fill("0");
  await page
    .getByRole("button", { name: "검토값을 화면에 반영", exact: true })
    .click();
  assert.equal(
    await page.getByLabel("검토 사유", { exact: true }).inputValue(),
    "합성 정책 검토",
  );
  await page.getByLabel("허용 데이터 손실 (분)", { exact: true }).fill("20");
  await page
    .getByRole("button", { name: "검토값을 화면에 반영", exact: true })
    .click();
  assert.equal(
    await page
      .getByLabel("백업 간격 (분)", { exact: true })
      .getAttribute("aria-invalid"),
    "true",
  );
  await shot("policy-error");
  await page.getByLabel("허용 데이터 손실 (분)", { exact: true }).fill("90");
  await page
    .getByRole("button", { name: "검토값을 화면에 반영", exact: true })
    .click();
  await page.getByText("90분 / 240분", { exact: true }).waitFor();
  await page.getByLabel("검토할 화면").selectOption("staff");
  await page
    .getByRole("heading", { name: "관리자에게 요청하세요", exact: true })
    .waitFor();
  assert.equal(
    await page
      .getByRole("navigation")
      .getByRole("link", { name: "운영 준비", exact: true })
      .count(),
    0,
  );
  await shot("staff-role-boundary");
  await page.getByLabel("검토할 화면").selectOption("admin");
  await page.setViewportSize({ width: 390, height: 844 });
  for (const view of [
    "home",
    "setup",
    "security",
    "operations",
    "policy",
    "retention",
  ]) {
    await go(view);
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
    );
    await shot("mobile-" + view);
  }
  await page.getByRole("button", { name: "GW 메뉴 열기", exact: true }).click();
  assert.equal(
    await page
      .getByRole("button", { name: "GW 메뉴 열기", exact: true })
      .getAttribute("aria-expanded"),
    "true",
  );
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "내 계정 보안", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "내 계정 보안", exact: true })
    .waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "GW 메뉴 열기", exact: true })
      .getAttribute("aria-expanded"),
    "false",
  );
  await page
    .getByRole("button", { name: "인증 앱 등록 흐름 보기", exact: true })
    .click();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Escape");
  await page
    .getByRole("heading", { name: "인증 앱 등록 · 검토용", exact: true })
    .waitFor({ state: "hidden" });
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
  console.log(
    JSON.stringify({
      prototypeOnly: true,
      desktopViews: 11,
      mobileViews: 6,
      checks: [
        "draft-error-preserves-values",
        "dirty-close-continue-focus",
        "discard-restores-trigger-focus",
        "otp-format-only",
        "backup-ack-required",
        "policy-range-and-cross-field",
        "staff-review-menu",
        "mobile-menu-keyboard",
        "no-global-horizontal-overflow",
        "no-external-requests",
      ],
      pageErrors: errors.length,
      externalRequests: external.length,
      output: out,
    }),
  );
} finally {
  await browser.close();
}
