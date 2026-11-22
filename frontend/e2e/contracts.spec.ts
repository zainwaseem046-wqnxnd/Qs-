import { expect, test } from "@playwright/test";
import { registerOrg } from "./helpers";

test("subcontract: create → measured line → execute (locked) → cost summary and dashboard", async ({ page }) => {
  await registerOrg(page, "Commitments Co");
  await page.goto("/projects/new");
  await page.getByLabel("Project number").fill("26-200");
  await page.getByLabel("Project name").fill("Eastside Warehouse");
  await page.getByLabel("Status").selectOption("active");
  await page.getByLabel("Sector").selectOption("industrial");
  await page.getByLabel("Delivery method").selectOption("design_build");
  await page.getByLabel("Contract type").selectOption("lump_sum");
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByRole("heading", { name: /Eastside Warehouse/ })).toBeVisible();

  await page.goto("/directory");
  await page.getByRole("button", { name: "Add company" }).click();
  await page.getByRole("dialog").getByLabel(/^Company name/).fill("Gulf Coast Steel");
  await page.getByRole("dialog").getByRole("button", { name: "Add company" }).click();
  await expect(page.getByText("Gulf Coast Steel added")).toBeVisible();

  await page.getByRole("link", { name: "Subcontracts & POs" }).click();
  await page.getByRole("button", { name: "New subcontract / PO" }).click();
  const d = page.getByRole("dialog");
  await d.getByLabel(/^Project/).selectOption({ label: "26-200 — Eastside Warehouse" });
  await d.getByLabel(/^Subcontractor/).selectOption({ label: "Gulf Coast Steel" });
  await d.getByLabel(/^Title/).fill("Structural steel package");
  await d.getByLabel(/^Contract form/).selectOption("aia_a401");
  await d.getByLabel("Retainage %").fill("10");
  await d.getByRole("button", { name: "Create draft" }).click();
  await expect(page.getByRole("heading", { name: /SC-001 Structural steel package/ })).toBeVisible();

  await page.getByRole("button", { name: "Add line" }).first().click();
  const l = page.getByRole("dialog");
  await l.getByLabel(/^Description/).fill("Fabricate and erect");
  await l.getByLabel("Measured (quantity × rate)").check();
  await l.getByLabel(/^Quantity/).fill("142.5");
  await l.getByLabel(/^Unit$|^Unit\*/).fill("ton");
  await l.getByLabel(/^Unit rate/).fill("2950.333333");
  await l.getByRole("button", { name: "Save line" }).click();
  await expect(page.getByText("Line added")).toBeVisible();
  await expect(page.getByRole("cell", { name: "$420,422.50" }).first()).toBeVisible();

  await page.getByRole("button", { name: "Execute" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Execute" }).click();
  await expect(page.getByText("Terms and lines are locked")).toBeVisible();
  await expect(page.getByRole("button", { name: "Add line" })).toHaveCount(0);
  await expect(page.getByText("Original commitment value, fixed at execution")).toBeVisible();

  await page.getByRole("link", { name: /26-200 Eastside Warehouse/ }).click();
  await page.getByRole("tab", { name: "Cost summary" }).click();
  await expect(page.getByText("No approved original budget yet")).toBeVisible();
  await expect(page.getByRole("cell", { name: "$420,422.50" }).first()).toBeVisible();

  await page.getByRole("link", { name: "Executive Dashboard" }).click();
  await expect(page.getByText("Committed cost", { exact: true })).toBeVisible();
  await expect(page.getByText("$420K")).toBeVisible();
});
