import { expect, test } from "@playwright/test";
import { expectHeading, loginByApi, users } from "./helpers.js";

test("users directory loads metrics and seeded users", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/utilizatori");
  await expectHeading(page, "Utilizatori");
  await expect(page.getByRole("link", { name: /@e2e_reader/ })).toBeVisible();
  await expect(page.getByLabel("Statistici utilizator").first()).toBeVisible();
});

test("friends page shows incoming and accepted relationships", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/prieteni");
  await expectHeading(page, "Prieteni");
  await expect(page.getByText("cereri primite")).toBeVisible();
  await expect(page.getByRole("link", { name: /@e2e_reader/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /@e2e_target/ })).toBeVisible();
});

test("messages page opens deterministic conversation", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/mesaje");
  await expectHeading(page, "Conversații");
  await expect(page.getByText("e2e_reader")).toBeVisible();
  await expect(page.getByText("Mesaj E2E necitit")).toBeVisible();
});

test("forum list and thread detail render seeded discussion", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/discutii");
  await expectHeading(page, "Discuții");
  await expect(page.getByText("E2E Forum Thread")).toBeVisible();

  await page.goto("/discutii/e2e-forum-thread");
  await expectHeading(page, "E2E Forum Thread");
  await expect(page.getByText("Răspuns E2E")).toBeVisible();
});

test("club list and club detail render member workspace", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/cluburi");
  await expectHeading(page, "Cluburi literare");
  await expect(page.getByRole("link", { name: "E2E Club", exact: true })).toBeVisible();

  await page.goto("/cluburi/e2e-club");
  await expect(page.locator("h1", { hasText: "E2E Club" })).toBeVisible();
  await expect(page.getByText("Anunț E2E")).toBeVisible();
});
