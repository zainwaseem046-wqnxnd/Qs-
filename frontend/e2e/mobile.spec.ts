import { expect, test } from "@playwright/test";
import { registerOrg } from "./helpers";

test("mobile layout: navigation drawer works and no horizontal overflow", async ({ page }) => {
  await registerOrg(page, "Mobile Field Co");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBe(false);
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("dialog", { name: "Navigation" }).getByRole("link", { name: "Projects" }).click();
  await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
});
