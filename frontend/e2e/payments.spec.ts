import { expect, test } from "@playwright/test";
import { apiAs, registerOrg } from "./helpers";

test("pay application: claim by percent and amount, submit, certify with a cut, short payment → outstanding", async ({ page }) => {
  await registerOrg(page, "Billing Co");
  const today = new Date().toISOString().slice(0, 10);
  const project = await apiAs(page, "POST", "/projects", { number: "26-500", name: "Lakeside Clinic", status: "active", sector: "institutional", delivery_method: "design_bid_build", contract_type: "lump_sum" });
  let pc = await apiAs(page, "POST", `/projects/${project.id}/contracts`, { title: "Prime", contract_form: "lump_sum", retention_percent: "10", payment_terms_days: 30 });
  pc = await apiAs(page, "POST", `/contracts/${pc.id}/lines`, { description: "Substructure", amount: "600000.00" });
  pc = await apiAs(page, "POST", `/contracts/${pc.id}/lines`, { description: "Superstructure", amount: "400000.00" });
  await apiAs(page, "POST", `/contracts/${pc.id}/execute`, { executed_date: today, version: pc.version });
  let co = await apiAs(page, "POST", "/change-orders", { target_type: "contract", target_id: pc.id, title: "Added canopy" });
  co = await apiAs(page, "POST", `/change-orders/${co.id}/lines`, { description: "Canopy", amount: "50000.00" });
  co = await apiAs(page, "POST", `/change-orders/${co.id}/submit`, { version: co.version });
  await apiAs(page, "POST", `/change-orders/${co.id}/approve`, { version: co.version, notes: "Agreed" });

  await page.goto(`/projects/${project.id}?tab=payments`);
  await page.getByRole("button", { name: "New pay application" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Start draft" }).click();
  await expect(page).toHaveURL(/\/payment-applications\//);
  await expect(page.getByRole("heading", { name: /Pay application 1/ })).toBeVisible();
  await expect(page.getByText("CO-001")).toBeVisible();

  await page.getByRole("row", { name: "Edit 1 Substructure" }).click();
  let d = page.getByRole("dialog");
  await d.getByRole("radio", { name: "Percent complete to date" }).click();
  await d.getByLabel(/^Percent complete to date/).fill("50");
  await d.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Line updated")).toBeVisible();

  await page.getByRole("row", { name: "Edit 2 Superstructure" }).click();
  d = page.getByRole("dialog");
  await d.getByLabel(/^Work this period/).fill("10000");
  await d.getByLabel(/^Materials presently stored/).fill("5000");
  await d.getByRole("button", { name: "Save" }).click();
  // completed 315,000; retention 10% = 31,500; due 283,500
  await expect(page.getByRole("row", { name: /Current payment due/ })).toContainText("$283,500.00");

  await page.getByRole("button", { name: "Submit" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Submit" }).click();
  await expect(page.getByText("Submitted", { exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "Record certificate" }).click();
  d = page.getByRole("dialog");
  await d.getByLabel(/^Certified amount/).fill("280000.00");
  await d.getByRole("button", { name: "Record certificate" }).click();
  await expect(d.getByText("Explain why the certified amount differs")).toBeVisible();
  await d.getByLabel(/^Reason for any difference/).fill("Stored materials not verified");
  await d.getByRole("button", { name: "Record certificate" }).click();
  await expect(page.getByText("Certificate recorded")).toBeVisible();

  await page.getByRole("button", { name: "Record payment" }).click();
  d = page.getByRole("dialog");
  await d.getByLabel(/^Amount received/).fill("270000.00");
  await d.getByRole("button", { name: "Record payment" }).click();
  await expect(page.getByText("Payment recorded")).toBeVisible();
  await expect(page.getByText("Paid", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("$10,000.00").first()).toBeVisible(); // outstanding after short payment

  await page.goto(`/projects/${project.id}?tab=payments`);
  await expect(page.getByText("Certified to date")).toBeVisible();
  await expect(page.getByText("$280,000.00").first()).toBeVisible();

  await page.getByRole("link", { name: "Executive Dashboard" }).click();
  await expect(page.getByText("Outstanding payments")).toBeVisible();
  await expect(page.getByText(/Certified, not yet paid/)).toBeVisible();
});
