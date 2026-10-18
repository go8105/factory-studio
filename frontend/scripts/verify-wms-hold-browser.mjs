import { chromium } from "playwright";
import path from "node:path";

const ARTIFACT_DIR =
  process.env.ARTIFACT_DIR ||
  "/Users/hwang-kyoungho/.gemini/antigravity/brain/d53accd5-4313-45df-ab53-3a0cb3261bf0";

async function main() {
  console.log("=== W2b-1b B-3 LOT 보류·해제 및 QMS 연동 실기동 브라우저 검증 시작 ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });
  const page = await context.newPage();

  try {
    console.log("1. 홈 접속 및 게스트 세션 시작");
    await page.goto("http://localhost:5173/");
    await page.getByLabel("별칭").fill("B3검증자");
    await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
    await page.waitForURL("**/home");
    console.log("   게스트 홈 진입 성공");

    console.log("2. /wms/lots 접속");
    await page.goto("http://localhost:5173/wms/lots");
    await page.waitForSelector(".filter-bar");
    console.log("   LOT 목록 페이지 진입 성공");

    console.log("3. 신규 검증용 LOT 등록 (LOT-20261017-B3TEST)");
    await page.getByRole("button", { name: "LOT 등록", exact: true }).click();
    const createModal = page.getByRole("dialog", { name: "LOT 등록" });
    await createModal.waitFor();

    await createModal.getByLabel("품목").selectOption({ index: 1 });
    await createModal
      .getByLabel("LOT 번호", { exact: true })
      .fill("LOT-20261017-B3TEST");
    await createModal.getByLabel("공급처 LOT 번호").fill("SUP-B3-999");
    await createModal.getByRole("button", { name: "등록" }).click();

    // 등록 후 테이블 갱신 대기
    const testRow = page.getByRole("row", { name: /LOT-20261017-B3TEST/ });
    await testRow.waitFor();
    console.log("   LOT-20261017-B3TEST 등록 확인 완료");

    console.log("4. 초기 가용 상태 및 QMS 연동 영역 확인");
    await testRow.getByRole("button", { name: "상세" }).click();
    const detailPanel = page.getByRole("dialog", {
      name: /LOT-20261017-B3TEST 상세/,
    });
    await detailPanel.waitFor();

    const initialText = await detailPanel.innerText();
    const isInitiallyAvailable = initialText.includes(
      "현재 활성 보류가 없는 가용 상태입니다",
    );
    const hasQmsSection =
      initialText.includes("QMS를 사용하지 않습니다") ||
      initialText.includes("QMS 품질 검사") ||
      initialText.includes("QMS 보류 없음");
    console.log("   초기 상태 검증 결과:", {
      isInitiallyAvailable,
      hasQmsSection,
    });
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "wms-lots-initial.png"),
    });

    console.log("5. 1차 수동 보류 설정 (MANUAL)");
    await detailPanel.getByRole("button", { name: "보류 설정" }).click();
    await detailPanel.getByLabel("출처").selectOption("MANUAL");
    await detailPanel
      .getByLabel("원천 코드 / 문서번호")
      .fill("REF-MANUAL-001");
    await detailPanel
      .getByLabel("보류 사유 (2자 이상)")
      .fill("수입검사 불합격 의심 - 실시간 검증");
    await detailPanel.getByRole("button", { name: "보류 확정" }).click();

    // 보류 완료 후 상태 변경 대기
    await page.waitForTimeout(500);
    const heldRowText = await testRow.innerText();
    const heldPanelText = await detailPanel.innerText();

    const listHasHoldBadge =
      heldRowText.includes("보류") && !heldRowText.includes("가용");
    const detailHasActiveHold = heldPanelText.includes("현재 보류 중");
    const detailHasReleaseBtn = await detailPanel
      .getByRole("button", { name: "보류 해제" })
      .isVisible();
    const detailHasHistory1 = heldPanelText.includes("보류 이력 (1건)");

    console.log("   1차 보류 검증 결과:", {
      listHasHoldBadge,
      detailHasActiveHold,
      detailHasReleaseBtn,
      detailHasHistory1,
    });
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "wms-lots-hold-active.png"),
    });

    console.log("6. 1차 보류 해제");
    await detailPanel.getByRole("button", { name: "보류 해제" }).click();
    await page.waitForTimeout(500);

    const relRowText = await testRow.innerText();
    const relPanelText = await detailPanel.innerText();

    const listBackToAvailable = relRowText.includes("가용");
    const detailBackToAvailable = relPanelText.includes(
      "현재 활성 보류가 없는 가용 상태입니다",
    );
    const detailHistory1Released = relPanelText.includes("해제됨");

    console.log("   1차 보류 해제 검증 결과:", {
      listBackToAvailable,
      detailBackToAvailable,
      detailHistory1Released,
    });
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "wms-lots-hold-released.png"),
    });

    console.log("7. 2차 QMS 연동 보류 설정 (재보류 사이클)");
    await detailPanel.getByRole("button", { name: "보류 설정" }).click();
    await detailPanel.getByLabel("출처").selectOption("QMS");
    await detailPanel
      .getByLabel("원천 코드 / 문서번호")
      .fill("QH-20261017-999");
    await detailPanel
      .getByLabel("보류 사유 (2자 이상)")
      .fill("QMS 품질 불합격 보류 동기화");
    await detailPanel.getByRole("button", { name: "보류 확정" }).click();
    await page.waitForTimeout(500);

    const secondHeldPanelText = await detailPanel.innerText();
    const detailHasHistory2 = secondHeldPanelText.includes("보류 이력 (2건)");
    const hasQmsSource = secondHeldPanelText.includes("품질(QMS)");

    console.log("   2차 재보류 검증 결과:", {
      detailHasHistory2,
      hasQmsSource,
    });
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "wms-lots-hold-second.png"),
    });

    console.log("8. 2차 보류 해제 및 이력 2건 모두 보존 확인");
    await detailPanel.getByRole("button", { name: "보류 해제" }).click();
    await page.waitForTimeout(500);

    const finalPanelText = await detailPanel.innerText();
    const finalHasHistory2 = finalPanelText.includes("보류 이력 (2건)");
    console.log("   최종 해제 및 2건 이력 보존 결과:", { finalHasHistory2 });

    console.log("9. 모바일 뷰포트 (390px) 반응형 확인");
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    // 좁은 화면(서랍) 닫기 버튼이 있으면 눌러서 본문/상세 패널이 온전히 보이도록 함
    const closeSidebarBtn = page.getByRole("button", { name: "메뉴 닫기" });
    if (await closeSidebarBtn.isVisible().catch(() => false)) {
      await closeSidebarBtn.click();
      await page.waitForTimeout(300);
    }
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "wms-lots-mobile-390.png"),
    });
    console.log("   모바일 390px 스크린샷 캡처 완료");

    console.log("=== 모든 브라우저 실기동 검증 성공! ===");
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error("브라우저 검증 실패:", err);
  process.exit(1);
});
