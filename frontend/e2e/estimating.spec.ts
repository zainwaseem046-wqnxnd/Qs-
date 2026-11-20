import { expect, test } from "@playwright/test";
import { registerOrg } from "./helpers";

test("cost codes → estimate with build-up → issue → approve → budget → dashboard", async ({ page }) => {
  await registerOrg(page, "Precon Workflow Co");

  // Project
  await page.goto("/projects/new");
  await page.getByLabel("Project number").fill("26-100");
  await page.getByLabel("Project name").fill("Northgate Clinic");
  await page.getByLabel("Status").selectOption("active");
  await page.getByLabel("Sector").selectOption("commercial");
  await page.getByLabel("Delivery method").selectOption("design_bid_build");
  await page.getByLabel("Contract type").selectOption("lump_sum");
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByRole("heading", { name: /Northgate Clinic/ })).toBeVisible();

  // Cost code structure in the customer's own format + CSV import
  await page.getByRole("link", { name: "Cost Codes" }).click();
  await page.getByRole("button", { name: "New structure" }).click();
  await page.getByLabel("Name").fill("Company codes");
  await page.getByLabel("Starting point").selectOption("custom");
  await page.getByLabel("Levels").fill("Package > Item");
  await page.getByRole("button", { name: "Create structure" }).click();
  await expect(page.getByText("Package › Item")).toBeVisible();
  await page.getByRole("button", { name: "Import CSV" }).click();
  await page.getByLabel("CSV file").setInputFiles({
    name: "codes.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("code,title,parent_code,unit\n03,Concrete,,\n03-100,Slab on grade,03,SF\n"),
  });
  await page.getByRole("dialog").getByRole("button", { name: "Import" }).click();
  await expect(page.getByText("2 codes imported into Company codes")).toBeVisible();
  await expect(page.getByText("Slab on grade")).toBeVisible();

  // Estimate
  await page.getByRole("link", { name: "Estimating" }).click();
  await page.getByRole("button", { name: "New estimate" }).click();
  await page.getByLabel("Project").selectOption({ label: "26-100 — Northgate Clinic" });
  await page.getByRole("dialog").getByLabel(/^Name/).fill("Bid estimate");
  await page.getByRole("button", { name: "Create estimate" }).click();
  await expect(page.getByRole("heading", { name: "Bid estimate" })).toBeVisible();

  await page.getByRole("button", { name: "Add line" }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel(/^Description/).fill("Slab on grade 5in");
  await dialog.getByLabel("Cost code").selectOption({ label: " 03-100 — Slab on grade" });
  await dialog.getByLabel(/^Quantity/).fill("1000");
  await dialog.getByLabel(/^Unit/).fill("SF");
  await dialog.getByLabel("Labor hours per unit").fill("0.025");
  await dialog.getByLabel("Labor rate per hour").fill("60");
  await dialog.getByLabel("Material rate", { exact: true }).fill("4.10");
  await dialog.getByLabel("Material waste %").fill("5");
  // live server-side build-up: labor 0.025 x 60 = 1.50/SF -> 1,500.00; material 4.10 x 1.05 = 4.305 -> 4,305.00
  await expect(dialog.getByText("$5,805.00")).toBeVisible();
  await dialog.getByRole("button", { name: "Add line" }).click();
  await expect(page.getByText("Line added")).toBeVisible();

  await page.getByRole("button", { name: "Markups" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Add markup" }).click();
  await page.getByLabel("Markup 1 name").fill("Contingency");
  await page.getByLabel("Markup 1 percent").fill("10");
  await page.getByRole("button", { name: "Save markups" }).click();
  await expect(page.getByText("Markups saved")).toBeVisible();
  await expect(page.getByText("$6,385.50")).toBeVisible(); // 5,805.00 + 580.50

  await page.getByRole("button", { name: "Issue version" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Issue" }).click();
  await expect(page.getByText("Issued — locked")).toBeVisible();
  await page.getByRole("button", { name: "Approve" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Approved — locked")).toBeVisible();

  // Budget from approved estimate
  await page.getByRole("link", { name: /26-100 Northgate Clinic/ }).click();
  await page.getByRole("tab", { name: "Budget" }).click();
  await page.getByRole("button", { name: "Create budget" }).click();
  await page.getByLabel("Source").selectOption({ index: 1 });
  await page.getByRole("button", { name: "Create draft budget" }).click();
  await expect(page.getByText("Markup: Contingency")).toBeVisible();
  await expect(page.getByRole("cell", { name: "$6,385.50" })).toBeVisible();
  await page.getByRole("button", { name: "Approve" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Approved original budget", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Executive Dashboard" }).click();
  await expect(page.getByText("Approved original budgets")).toBeVisible();
  await expect(page.getByText("1 live project budgeted")).toBeVisible();
});
