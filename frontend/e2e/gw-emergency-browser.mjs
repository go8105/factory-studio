/* global process, URL, setTimeout, document, innerWidth, console */
// Synthetic local security acceptance. Never use production account credentials.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { chromium } from "@playwright/test";
const root = process.cwd();
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
  if (process.env.GW_EVIDENCE_SIGN_HELPER) {
    execFileSync(
      path.join(root, "backend/.venv/bin/python"),
      [process.env.GW_EVIDENCE_SIGN_HELPER, String(credentials.company)],
      { cwd: root, stdio: "pipe" },
    );
    await page
      .getByLabel("서명된 실행 증거 파일")
      .setInputFiles(
        path.join(root, "work/gw-readiness-02-evidence/evidence.json"),
      );
    await page.getByRole("button", { name: "실행 증거 확인·등록" }).click();
    await page
      .getByText("실행 기록을 등록했습니다. 운영 준비 완료를 뜻하지 않습니다.")
      .waitFor();
    await page.getByText(/백업 · 실패/).waitFor();
    await page.screenshot({
      path: path.join(out, "evidence-failure-mobile.png"),
      fullPage: true,
    });
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
  }
  await page
    .getByLabel("긴급 복구 문서 발급 사유")
    .fill("합성 브라우저 긴급 복구 검증");
  await page
    .getByLabel(
      "이전 문서·미사용 승인 파일 회수와 별도 보관 필요를 확인했습니다",
    )
    .check();
  await page
    .getByRole("button", { name: "본인 긴급 복구 문서 새로 발급" })
    .click();
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "긴급 복구 문서 파일 저장" }).click();
  const download = await downloadEvent;
  const kitPath = path.join(root, "work/gw-readiness-02-evidence/kit.json");
  const approvalPath = path.join(
    root,
    "work/gw-readiness-02-evidence/approval.json",
  );
  await download.saveAs(kitPath);
  await fs.chmod(kitPath, 0o600);
  const kit = JSON.parse(await fs.readFile(kitPath, "utf8"));
  await page.getByLabel("파일을 안전한 별도 장소에 보관했습니다").check();
  await page.getByRole("button", { name: "보관 확인하고 닫기" }).click();
  await page
    .getByText("유효한 긴급 복구 문서가 준비되어 있습니다.", { exact: false })
    .waitFor();
  await page.screenshot({
    path: path.join(out, "emergency-prepared-mobile.png"),
    fullPage: true,
  });
  execFileSync(
    path.join(root, "backend/.venv/bin/python"),
    [
      path.join(root, "tools/gw_emergency_recovery.py"),
      "--kit-file",
      kitPath,
      "--output",
      approvalPath,
      "--company-id",
      kit.companyId,
      "--user-id",
      kit.userId,
      "--reason",
      "합성 브라우저 복구 승인",
    ],
    { cwd: root, stdio: "pipe" },
  );
  await page.getByRole("button", { name: "나가기", exact: true }).click();
  await login();
  await page
    .getByRole("button", { name: "인증 앱과 복구 코드를 모두 잃었어요" })
    .click();
  await page.getByLabel("운영자 승인 파일 선택").setInputFiles(approvalPath);
  await page.getByRole("button", { name: "확인하고 계속" }).click();
  await page.waitForURL("**/account/recovery");
  await page.getByRole("button", { name: "새 설정 키 받기" }).waitFor();
  await page.screenshot({
    path: path.join(out, "recovery-limited-mobile.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "새 설정 키 받기" }).click();
  const replacement = await page.getByLabel("인증 앱 설정 키").inputValue();
  await page.getByLabel("인증 앱 번호", { exact: true }).fill(otp(replacement));
  await page.getByRole("button", { name: "번호 확인하고 등록" }).click();
  await page
    .getByRole("heading", { name: "복구 코드를 지금 보관하세요" })
    .waitFor();
  await page.getByLabel("코드 8개를 안전하게 보관했습니다").check();
  await page.getByRole("button", { name: "로그인 화면으로" }).click();
  await page.goto(base + "/help/portal/account-security");
  await page
    .getByRole("heading", { name: "내 계정 보안 · 인증 앱과 분실 복구" })
    .waitFor();
  await page.screenshot({
    path: path.join(out, "security-help-mobile.png"),
    fullPage: true,
  });
  assert.deepEqual(errors, []);
  const report = {
    synthetic: true,
    realDevice: false,
    pageErrors: errors,
    checks: [
      "password login",
      "TOTP enrollment",
      "one-time code acknowledgement",
      "MFA login",
      "390px no overflow",
      ...(process.env.GW_EVIDENCE_SIGN_HELPER
        ? ["signed failure evidence upload and history"]
        : []),
      "emergency kit download",
      "operator CLI approval",
      "approval file upload",
      "recovery limited session",
      "re-enrollment",
      "product help",
      ...(credentials.company
        ? ["company policy revision", "continue-edit focus"]
        : []),
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
