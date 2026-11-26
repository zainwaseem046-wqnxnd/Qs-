import { expect, test } from "@playwright/test";
import { PASSWORD, registerOrg } from "./helpers";

test("register, create a project, upload a drawing, see it on the dashboard, sign out and back in", async ({ page }) => {
  const email = await registerOrg(page, "Lone Star Builders E2E");
  await expect(page.getByRole("heading", { name: "Executive Dashboard" })).toBeVisible();
  await expect(page.getByText(/Welcome, Morgan/)).toBeVisible();

  // Client-side validation blocks an invalid project
  await page.getByRole("link", { name: "New project" }).first().click();
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByText("Enter a project name")).toBeVisible();

  await page.getByLabel("Project number").fill("24-017");
  await page.getByLabel("Project name").fill("Riverside Medical Office Building");
  await page.getByLabel("Status").selectOption("active");
  await page.getByLabel("Sector").selectOption("commercial");
  await page.getByLabel("Delivery method").selectOption("cm_at_risk");
  await page.getByLabel("Contract type").selectOption("gmp");
  await page.getByLabel("City").fill("Austin");
  await page.getByLabel("ZIP code").fill("78701");
  await page.getByLabel("Original contract value").fill("12,500,000.10");
  await page.getByLabel("Retainage %").fill("12.345");
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByText("Enter 0–100 with up to 2 decimals")).toBeVisible();
  await page.getByLabel("Retainage %").fill("10");
  await page.getByRole("button", { name: "Create project" }).click();

  await expect(page.getByRole("heading", { name: /Riverside Medical Office Building/ })).toBeVisible();
  await expect(page.getByText("$12,500,000.10")).toBeVisible();
  await expect(page.getByText("Austin, TX · 78701")).toBeVisible();

  // Edit with audit trail
  await page.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Original contract value").fill("12750000");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("$12,750,000.00")).toBeVisible();
  await page.getByRole("tab", { name: "Activity" }).click();
  await expect(page.getByText("12500000.10")).toBeVisible();
  await expect(page.getByText("12750000.00")).toBeVisible();

  // Phase
  await page.getByRole("tab", { name: "Phases" }).click();
  await page.getByLabel("New phase").fill("Sitework");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByText("Sitework", { exact: true })).toBeVisible();

  // Document upload + version history + download
  await page.getByRole("tab", { name: "Documents" }).click();
  await page.getByRole("button", { name: "Upload" }).click();
  const pdf = Buffer.from("%PDF-1.7\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n");
  await page.getByLabel("File").setInputFiles({ name: "A-101 Floor Plan.pdf", mimeType: "application/pdf", buffer: pdf });
  await page.getByLabel("Document / sheet number").fill("A-101");
  await page.getByLabel("Revision label").fill("IFC");
  await page.getByRole("dialog").getByRole("button", { name: "Upload" }).click();
  await expect(page.getByText("“A-101 Floor Plan” uploaded")).toBeVisible();
  await page.getByRole("cell", { name: /A-101 Floor Plan/ }).click();
  await expect(page.getByText("Version history")).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download version 1" }).click();
  expect((await download).suggestedFilename()).toBe("A-101 Floor Plan.pdf");
  await page.keyboard.press("Escape");

  // Dashboard reflects the recorded contract value
  await page.getByRole("link", { name: "Executive Dashboard" }).click();
  await expect(page.getByText("$12.8M")).toBeVisible();
  await expect(page.getByRole("link", { name: /Riverside Medical Office Building/ })).toBeVisible();

  // Unbuilt modules are labelled, not clickable
  await expect(page.locator('[aria-disabled="true"]', { hasText: "Procurement" })).toContainText("Phase 3");

  // Sign out and back in
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto("/projects");
  await expect(page).toHaveURL(/\/login\?next=%2Fprojects/);
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill("wrong-password-xyz");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Invalid email or password")).toBeVisible();
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.getByRole("link", { name: "Riverside Medical Office Building" })).toBeVisible();
});

test("organizations are isolated from each other in the UI", async ({ browser }) => {
  const a = await browser.newContext();
  const b = await browser.newContext();
  const pa = await a.newPage();
  const pb = await b.newPage();
  await registerOrg(pa, "Alpha Isolation Co");
  await pa.goto("/projects/new");
  await pa.getByLabel("Project number").fill("A-1");
  await pa.getByLabel("Project name").fill("Alpha Secret Tower");
  await pa.getByLabel("Sector").selectOption("commercial");
  await pa.getByLabel("Delivery method").selectOption("design_build");
  await pa.getByLabel("Contract type").selectOption("lump_sum");
  await pa.getByRole("button", { name: "Create project" }).click();
  await expect(pa.getByRole("heading", { name: /Alpha Secret Tower/ })).toBeVisible();
  const url = pa.url();

  await registerOrg(pb, "Bravo Isolation Co");
  await pb.goto(url.replace(/^https?:\/\/[^/]+/, ""));
  await expect(pb.getByText("Project not found")).toBeVisible();
  await pb.goto("/projects");
  await expect(pb.getByText("No projects yet")).toBeVisible();
  await a.close();
  await b.close();
});
