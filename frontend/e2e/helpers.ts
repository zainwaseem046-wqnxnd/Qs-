import { expect, type Page } from "@playwright/test";

export const PASSWORD = "Correct-Horse-Battery-9";

export function uniqueEmail(prefix = "e2e"): string {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
}

export async function registerOrg(page: Page, org: string, email = uniqueEmail()): Promise<string> {
  await page.goto("/register");
  await page.getByLabel("Company name").fill(org);
  await page.getByLabel("Home state").selectOption("TX");
  await page.getByLabel("Your full name").fill("Morgan Estimator");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create organization" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  return email;
}
