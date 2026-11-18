import { expect, test } from "@playwright/test";
import { PASSWORD, uniqueEmail } from "./helpers";

test("a UK organization works in GBP, metric units, UK dates and postcodes", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Company name").fill("Thames Commercial QS Ltd");
  await page.getByLabel("Country").selectOption("GB");
  await expect(page.getByLabel("Home state")).toHaveCount(0);
  await page.getByLabel("Your full name").fill("Alex Surveyor");
  await page.getByLabel("Work email").fill(uniqueEmail("uk"));
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create organization" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.goto("/projects/new");
  await expect(page.getByLabel("State")).toHaveCount(0);
  await expect(page.getByLabel("Prevailing wage applies")).toHaveCount(0);
  await page.getByLabel("Project number").fill("UK-001");
  await page.getByLabel("Project name").fill("Canary Wharf Office Fit-Out");
  await page.getByLabel("Sector").selectOption("commercial");
  await page.getByLabel("Delivery method").selectOption("design_build");
  await page.getByLabel("Contract type").selectOption("lump_sum");
  await page.getByLabel("City").fill("London");
  await page.getByLabel("Postcode").fill("12345");
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByText("Enter a valid UK postcode, e.g. SW1A 1AA")).toBeVisible();
  await page.getByLabel("Postcode").fill("e14 5ab");
  await page.getByLabel("Start date").fill("2027-03-01");
  await page.getByLabel("Original contract value").fill("4250000");
  await page.getByLabel("Retention %").fill("3");
  await page.getByRole("button", { name: "Create project" }).click();

  await expect(page.getByRole("heading", { name: /Canary Wharf Office Fit-Out/ })).toBeVisible();
  await expect(page.getByText("£4,250,000.00")).toBeVisible();
  await expect(page.getByText("London · E14 5AB")).toBeVisible();
  await expect(page.getByText("01/03/2027")).toBeVisible();
  await expect(page.getByText("Retention", { exact: true })).toBeVisible();
});

test("forgot password never reveals whether an account exists", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("link", { name: "Forgot password?" }).click();
  await page.waitForURL(/forgot-password/);
  await page.waitForLoadState("networkidle");
  await page.getByLabel("Work email").fill(uniqueEmail("nobody"));
  await page.getByRole("button", { name: "Send reset link" }).click();
  await expect(page.getByText("Check your email")).toBeVisible();
});

test("an invalid reset link is rejected", async ({ page }) => {
  await page.goto("/reset-password/not-a-real-token-0123456789abcdef");
  await page.waitForLoadState("networkidle");
  await page.getByLabel(/^New password/).fill("Brand-New-Passphrase-42");
  await page.getByLabel("Confirm new password").fill("Brand-New-Passphrase-42");
  await page.getByRole("button", { name: "Update password" }).click();
  await expect(page.getByText(/invalid or has expired/)).toBeVisible();
});
