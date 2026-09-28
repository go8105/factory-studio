import { expect, test, type Page } from "@playwright/test";

// FS-025b BEMS 실제 API 흐름. BEMS 시드(FS-025c) 전이라 기준정보를 화면에서 만든다.
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /가입 없이 둘러보기/ }).click();
  await expect(page).toHaveURL("/home");
});

async function register(page: Page, dialog: string, fill: () => Promise<void>) {
  const form = page.getByRole("dialog", { name: dialog });
  await fill();
  await form.getByRole("button", { name: "등록" }).click();
  await expect(form).toBeHidden();
}

test("구역·계측 등록 → 경보 규칙 → 공조 수동 운전·설정값 → 1시간 진행 → 경보 확인", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await page.goto("/bems/zones");
  await page.getByRole("button", { name: "구역 등록", exact: true }).click();
  await register(page, "구역 등록", async () => {
    await page.getByLabel("코드").fill("Z-OFF");
    await page.getByLabel("이름").fill("사무동");
  });
  await page
    .getByRole("row", { name: /Z-OFF/ })
    .getByRole("button", { name: /계측/ })
    .click();
  const detail = page.getByRole("dialog", { name: "사무동 계측" });
  await detail.getByRole("button", { name: "계측기 추가" }).click();
  await register(page, "공용 계측기 추가 · 사무동", async () => {
    await page.getByLabel("코드").fill("BM-HVAC");
    await page.getByLabel("이름").fill("사무동 공조 전력");
    await page.getByLabel("용도").selectOption("HVAC");
  });
  for (const [code, metric] of [
    ["S-TEMP", "TEMP"],
    ["S-CO2", "CO2"],
  ]) {
    await detail.getByRole("button", { name: "센서 추가" }).click();
    await register(page, "환경 센서 추가 · 사무동", async () => {
      await page.getByLabel("코드").fill(code);
      await page.getByLabel("항목").selectOption(metric);
    });
  }
  await detail.getByRole("button", { name: "공조기 추가" }).click();
  await register(page, "공조기 추가 · 사무동", async () => {
    await page.getByLabel("코드").fill("AHU-OFF");
    await page.getByLabel("이름").fill("사무동 공조기");
    await page
      .getByLabel("공조 전력 계측기")
      .selectOption({ label: "BM-HVAC 사무동 공조 전력" });
    await page.getByLabel("정격 kW").fill("12");
  });
  await expect(detail.getByRole("table", { name: "공조기" })).toContainText(
    "AHU-OFF",
  );

  await page.goto("/bems/alarms");
  await page.getByRole("button", { name: "규칙", exact: true }).click();
  await page.getByRole("button", { name: "규칙 등록", exact: true }).click();
  await register(page, "경보 규칙 등록", async () => {
    await page.getByLabel("항목").selectOption("CO2");
    await page.getByLabel(/한계값/).fill("400");
    await page.getByLabel(/지속 시간/).fill("1");
  });

  await page.goto("/bems/hvac");
  await page
    .getByRole("row", { name: /AHU-OFF/ })
    .getByRole("button", { name: "상세" })
    .click();
  const unit = page.getByRole("dialog", { name: "AHU-OFF 사무동 공조기" });
  await unit.getByRole("button", { name: "전원 켜기" }).click();
  await expect(unit.getByText(/적용: 전원 켜기/)).toBeVisible();
  await unit.getByLabel("모드").selectOption("COOL");
  await unit.getByRole("button", { name: "모드 적용" }).click();
  await expect(unit.getByText(/적용: 모드 변경 · 냉방/)).toBeVisible();
  // 범위 밖 설정값은 거부되고 폼에 남는다.
  await unit.getByRole("button", { name: "설정값 변경" }).click();
  const setpoint = page.getByRole("dialog", { name: "AHU-OFF 설정값 변경" });
  await setpoint.getByLabel(/값 \(℃/).fill("31");
  await setpoint.getByRole("button", { name: "적용" }).click();
  await expect(
    setpoint.getByText(/거부됨: 냉방 설정 31℃ — 허용 범위 밖/),
  ).toBeVisible();
  await setpoint.getByLabel(/값 \(℃/).fill("23");
  await setpoint.getByRole("button", { name: "적용" }).click();
  await expect(page.getByText(/적용: 냉방 설정 23℃/)).toBeVisible();
  await expect(unit.getByRole("table", { name: "최근 명령" })).toContainText(
    "거부 · 허용 범위 밖",
  );

  await page.keyboard.press("Escape"); // 좁은 화면은 패널이 겹쳐 열린다
  await expect(unit).toBeHidden();
  await page.getByRole("button", { name: "진행", exact: true }).click();
  await expect(page.getByText(/1시간 진행 · 관측 3건 생성/)).toContainText(
    "경보 발생 1",
  );
  await expect(page.getByRole("row", { name: /AHU-OFF/ })).toContainText("kWh");

  await page.goto("/bems/alarms");
  await page.getByRole("button", { name: "상세 · 확인" }).click();
  await page.getByLabel("확인 메모(선택)").fill("환기 지시");
  await page.getByRole("button", { name: "확인", exact: true }).click();
  await expect(page.getByText(/환기 지시\)/)).toBeVisible();

  await page.goto("/bems/environment");
  await expect(page.getByRole("figure", { name: "실내 온도" })).toBeVisible();
  await expect(page.getByRole("figure", { name: "CO₂" })).toContainText(
    "CO₂ 상한",
  );
});

test("FEMS를 끄면 에너지 분해는 안내로 바뀌고 공조 운전은 그대로 열린다", async ({
  page,
}) => {
  await page.goto("/bems/breakdown");
  await expect(page.getByRole("table", { name: "에너지 분해" })).toBeVisible();
  await page.goto("/workspace");
  await page.getByRole("switch", { name: "FEMS 사용" }).click();
  await expect(page.getByRole("switch", { name: "FEMS 사용" })).toHaveAttribute(
    "aria-checked",
    "false",
  );
  await page.goto("/bems/breakdown");
  await expect(
    page.getByText(/FEMS를 사용하지 않도록 설정했습니다/),
  ).toBeVisible();
  await page.goto("/bems/hvac");
  await expect(page.getByRole("heading", { name: "공조 운전" })).toBeVisible();
});
