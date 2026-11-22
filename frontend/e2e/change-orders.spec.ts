import { expect, test } from "@playwright/test";
import { apiAs, registerOrg } from "./helpers";

test("change order: raise from contract → price addition and omission → submit → approve → revised sum", async ({ page }) => {
  await registerOrg(page, "Changes Co");
  const project = await apiAs(page, "POST", "/projects", { number: "26-300", name: "Harbor Lofts", status: "active", sector: "multifamily", delivery_method: "cm_at_risk", contract_type: "gmp" });
  const client = await apiAs(page, "POST", "/companies", { name: "Harbor Owner LLC", company_type: "owner" });
  let pc = await apiAs(page, "POST", `/projects/${project.id}/contracts`, { title: "GMP agreement", contract_form: "gmp", client_company_id: client.id });
  pc = await apiAs(page, "POST", `/contracts/${pc.id}/lines`, { description: "Work", amount: "1000000.00" });
  await apiAs(page, "POST", `/contracts/${pc.id}/execute`, { executed_date: new Date().toISOString().slice(0, 10), version: pc.version });

  await page.goto(`/contracts/${pc.id}`);
  await expect(page.getByText("Revised", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "New change order" }).click();
  const d = page.getByRole("dialog");
  await d.getByLabel(/^Title/).fill("Upgrade lobby finishes");
  await d.getByLabel("Reference").fill("CCD-3");
  await d.getByRole("button", { name: "Create draft" }).click();
  await expect(page.getByRole("heading", { name: /CO-001 Upgrade lobby finishes/ })).toBeVisible();

  await page.getByRole("button", { name: "Add line" }).first().click();
  let l = page.getByRole("dialog");
  await l.getByLabel(/^Description/).fill("Stone tile in lieu of VCT");
  await l.getByLabel(/^Amount/).fill("18500");
  await l.getByLabel(/^Budget adjustment/).fill("15200");
  await l.getByRole("button", { name: "Save line" }).click();
  await expect(page.getByText("Line added")).toBeVisible();
  await page.getByRole("button", { name: "Add line" }).first().click();
  l = page.getByRole("dialog");
  await l.getByLabel(/^Description/).fill("Omit carpet");
  await l.getByLabel(/^Amount/).fill("-3250.50");
  await l.getByRole("button", { name: "Save line" }).click();
  await expect(page.getByText("$15,249.50").first()).toBeVisible();

  await page.getByRole("button", { name: "Submit" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Submit" }).click();
  await expect(page.getByText("Submitted — awaiting a decision")).toBeVisible();
  await expect(page.getByRole("button", { name: "Add line" })).toHaveCount(0);

  await page.getByRole("button", { name: "Approve" }).click();
  await page.getByRole("dialog").getByLabel(/^Notes/).fill("Owner signed CCD-3");
  await page.getByRole("dialog").getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText(/^Approved /)).toBeVisible();

  await page.getByRole("link", { name: /GMP agreement/ }).click();
  await expect(page.getByText("$1,015,249.50")).toBeVisible();
  await page.goto(`/projects/${project.id}`);
  await page.getByRole("tab", { name: "Cost summary" }).click();
  await expect(page.getByRole("cell", { name: "$15,200.00" }).first()).toBeVisible();
});
