import { expect, test } from "@playwright/test";
import { apiAs, registerOrg } from "./helpers";

test("costs and forecast: post, import, reverse → forecast → approve → dashboard margin", async ({ page }) => {
  await registerOrg(page, "Forecast Co");
  const today = new Date().toISOString().slice(0, 10);
  const project = await apiAs(page, "POST", "/projects", { number: "26-400", name: "Riverside Garage", status: "active", sector: "commercial", delivery_method: "design_build", contract_type: "lump_sum" });
  const b = await apiAs(page, "POST", `/projects/${project.id}/budgets`, { name: "Original budget" });
  await apiAs(page, "POST", `/budgets/${b.id}/lines`, { description: "All work", amount: "800000.00" });
  await apiAs(page, "POST", `/budgets/${b.id}/approve`, {});
  let pc = await apiAs(page, "POST", `/projects/${project.id}/contracts`, { title: "Prime", contract_form: "lump_sum" });
  pc = await apiAs(page, "POST", `/contracts/${pc.id}/lines`, { description: "Contract sum", amount: "1000000.00" });
  await apiAs(page, "POST", `/contracts/${pc.id}/execute`, { executed_date: today, version: pc.version });

  await page.goto(`/projects/${project.id}`);
  await page.getByRole("tab", { name: "Costs" }).click();
  await page.getByRole("button", { name: "Post cost" }).click();
  const d = page.getByRole("dialog");
  await d.getByLabel(/^Description/).fill("Wrong invoice");
  await d.getByLabel(/^Amount/).fill("5000");
  await d.getByRole("button", { name: "Post" }).click();
  await expect(page.getByText("Cost posted")).toBeVisible();

  await page.getByRole("button", { name: "Import CSV" }).click();
  await page.getByLabel(/^CSV file/).setInputFiles({ name: "gl.csv", mimeType: "text/csv", buffer: Buffer.from(`date,cost_code,description,amount,reference\n${today},,Concrete,"200,000.00",INV-1\n${today},,Steel,"150,000.00",INV-2\n`) });
  await page.getByRole("dialog").getByRole("button", { name: "Import" }).click();
  await expect(page.getByText("2 entries imported ($350,000.00)")).toBeVisible();

  await page.getByRole("button", { name: "Reverse Wrong invoice" }).click();
  await page.getByRole("dialog").getByLabel(/^Reason/).fill("Posted to the wrong project");
  await page.getByRole("dialog").getByRole("button", { name: "Post reversal" }).click();
  await expect(page.getByText("Reversing entry posted")).toBeVisible();
  await expect(page.getByText("total $350,000.00")).toBeVisible();

  await page.getByRole("tab", { name: "Forecast" }).click();
  await page.getByRole("button", { name: "New forecast" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Start draft" }).click();
  await expect(page.getByText("Draft — live figures")).toBeVisible();
  // FFC = 350,000 + max(800,000 - 350,000, 0) = 800,000; GP = 200,000; margin 20%
  await expect(page.getByText("$800,000.00").first()).toBeVisible();
  await expect(page.getByText("Margin 20%")).toBeVisible();
  await page.getByRole("button", { name: "Approve forecast" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText(/^Approved /).first()).toBeVisible();

  await page.getByRole("link", { name: "Executive Dashboard" }).click();
  await expect(page.getByText("Forecast gross profit")).toBeVisible();
  await expect(page.getByText("Margin 20%")).toBeVisible();
});
