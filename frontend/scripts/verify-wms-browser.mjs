import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const ARTIFACT_DIR = process.env.ARTIFACT_DIR || "/tmp";

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();

  console.log("1. 홈 접속 및 게스트 로그인");
  await page.goto("http://localhost:5173/");
  await page.getByLabel("별칭").fill("W2b 검증자");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await page.waitForURL("**/home");
  console.log("   홈 진입 성공");

  console.log("2. /wms/items (B-1 품목 보강 확인)");
  await page.goto("http://localhost:5173/wms/items");
  await page.waitForSelector("table");
  
  // B-1 품목 보강 필드 헤더 확인
  const thTexts = await page.$$eval("th", (ths) => ths.map((th) => th.textContent?.trim()));
  console.log("   품목 테이블 헤더:", thTexts.filter(Boolean).join(" | "));

  // 등록 패널 열어서 새 필드 확인
  await page.getByRole("button", { name: "품목 등록" }).click();
  const itemDialog = page.getByRole("dialog", { name: "품목 등록" });
  await itemDialog.waitFor();
  
  const hasShelfLife = await itemDialog.getByLabel("유효기간 (일)").isVisible();
  const hasAbcClass = await itemDialog.getByLabel("ABC 등급").isVisible();
  const hasSafetyStock = await itemDialog.getByLabel("안전재고").isVisible();
  const hasMaxStock = await itemDialog.getByLabel("최대재고").isVisible();
  const hasPlmPart = await itemDialog.getByLabel("PLM 품번").isVisible();
  const hasPlmRev = await itemDialog.getByLabel("PLM 리비전").isVisible();
  console.log("   품목 등록 폼 필드 확인:", {
    hasShelfLife,
    hasAbcClass,
    hasSafetyStock,
    hasMaxStock,
    hasPlmPart,
    hasPlmRev,
  });

  await page.screenshot({ path: path.join(ARTIFACT_DIR, "wms-items.png") });
  console.log("   /wms/items 스크린샷 캡처 완료");

  // 패널 닫기
  await itemDialog.getByRole("button", { name: "취소" }).click();

  console.log("3. /wms/lots (B-2 LOT 조회 및 등록 확인)");
  await page.goto("http://localhost:5173/wms/lots");
  await page.waitForSelector(".filter-bar");
  console.log("   /wms/lots 진입 성공");

  // LOT 등록 모달 열기
  await page.getByRole("button", { name: "LOT 등록", exact: true }).click();
  const lotDialog = page.getByRole("dialog", { name: "LOT 등록" });
  await lotDialog.waitFor();

  // 품목 선택 (첫 번째 품목)
  await lotDialog.getByLabel("품목").selectOption({ index: 1 });
  await lotDialog.getByLabel("LOT 번호", { exact: true }).fill("LOT-20261015-LIVE");
  await lotDialog.getByLabel("공급처 LOT 번호").fill("SUP-LIVE-001");
  
  // 등록 제출
  await lotDialog.getByRole("button", { name: "등록" }).click();
  await page.waitForSelector("table tbody tr");
  console.log("   LOT-20261015-LIVE 등록 완료");

  // 목록에서 등록된 행 확인
  const lotRow = page.getByRole("row", { name: /LOT-20261015-LIVE/ });
  await lotRow.waitFor();
  const lotRowText = await lotRow.innerText();
  console.log("   등록된 LOT 행 텍스트:", lotRowText.replace(/\n/g, " | "));

  // 상세 패널 열기
  await lotRow.getByRole("button", { name: "상세" }).click();
  const detailPanel = page.getByRole("dialog", { name: /LOT-20261015-LIVE 상세/ });
  await detailPanel.waitFor();
  const detailText = await detailPanel.innerText();
  console.log("   상세 패널 확인 (원장 집계 및 보류 안내):", {
    hasLedgerSummary: detailText.includes("원장 집계 현재고"),
    hasHoldNotice: detailText.includes("보류 설정 및 해제 기능은 다음 단계(B-3)에서 제공됩니다"),
    initialQty: detailText.includes("0 EA") || detailText.includes("보유 중인 위치가 없습니다"),
  });

  await page.screenshot({ path: path.join(ARTIFACT_DIR, "wms-lots-detail.png") });
  console.log("   /wms/lots 상세 스크린샷 캡처 완료");
  await detailPanel.getByLabel("패널 닫기").click();

  console.log("4. 원장 수량 대조: 기초재고 전표 작성 후 LOT 수량 증가 검증");
  await page.goto("http://localhost:5173/wms/documents");
  await page.getByLabel("전표 만들기").selectOption("OPENING");
  const docDialog = page.getByRole("dialog", { name: "기초재고 전표 작성" });
  await docDialog.waitFor();

  await docDialog.getByLabel("1번 줄 품목").selectOption({ index: 1 });
  await docDialog.getByLabel("1번 줄 LOT").fill("LOT-20261015-LIVE");
  await docDialog.getByLabel("1번 줄 위치").selectOption({ index: 1 });
  await docDialog.getByLabel("1번 줄 수량").fill("750");
  await docDialog.getByRole("button", { name: "확정" }).click();
  await page.waitForSelector("text=확정");
  console.log("   기초재고 750 전표 확정 완료");

  console.log("5. /wms/lots로 돌아와 LOT 수량 원장 대조 확인");
  await page.goto("http://localhost:5173/wms/lots");
  await page.waitForSelector("table tbody tr");
  
  const updatedLotRow = page.getByRole("row", { name: /LOT-20261015-LIVE/ });
  await updatedLotRow.waitFor();
  const updatedRowText = await updatedLotRow.innerText();
  console.log("   업데이트된 LOT 행 텍스트:", updatedRowText.replace(/\n/g, " | "));
  
  const has750 = updatedRowText.includes("750 EA");
  console.log("   원장 재고 750 EA 반영 여부:", has750);

  // 상세 패널 재확인 (위치별 수량 확인)
  await updatedLotRow.getByRole("button", { name: "상세" }).click();
  const updatedDetail = page.getByRole("dialog", { name: /LOT-20261015-LIVE 상세/ });
  await updatedDetail.waitFor();
  const updatedDetailText = await updatedDetail.innerText();
  console.log("   상세 위치별 재고 확인:", {
    totalQty750: updatedDetailText.includes("750 EA"),
    locationFA01: updatedDetailText.includes("F-A01"),
    warehouseWHFG: updatedDetailText.includes("WH-FG"),
  });

  await page.screenshot({ path: path.join(ARTIFACT_DIR, "wms-lots-verified-750.png") });
  console.log("   /wms/lots 수량 대조 스크린샷 캡처 완료");

  console.log("6. 390px 모바일 뷰포트 확인");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "wms-lots-mobile-390.png") });
  console.log("   모바일 390px 스크린샷 캡처 완료");

  await browser.close();
  console.log("모든 브라우저 검증 완료!");
}

main().catch((err) => {
  console.error("오류 발생:", err);
  process.exit(1);
});
