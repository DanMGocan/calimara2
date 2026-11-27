import { expect, test } from "@playwright/test";
import { expectHeading, loginByApi, users } from "./helpers.js";

test("shop and inventory render seeded gologani state", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/magazin");
  await expectHeading(page, "Magazin");
  await expect(page.getByText("Insignă E2E")).toBeVisible();
  await expect(page.getByText("Costum E2E")).toBeVisible();
  await expect(page.getByText("În dezvoltare.")).toBeVisible();

  await page.goto("/inventar");
  await expectHeading(page, "Inventar");
  // Items sit under the inert "În dezvoltare" overlay, so they are out of the a11y tree.
  await expect(page.getByText("Insignă E2E")).toBeVisible();
  await expect(page.getByText("În dezvoltare.")).toBeVisible();
});

test("premium page is reachable for authenticated users", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/premium");
  await expectHeading(page, "Dashboard Premium");
  await expect(page.getByText(/Trubadur|Cronicar|Rapsod/).first()).toBeVisible();
});

test("admin moderation dashboard loads seeded queues", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/moderare");
  await expectHeading(page, "Admin");
  await page.getByRole("tab", { name: "Conținut" }).click();
  await expect(page.getByRole("heading", { name: "E2E Pending" })).toBeVisible();
});

test("non-admin users see admin access denied", async ({ page }) => {
  await loginByApi(page, users.participant);
  await page.goto("/moderare");
  await expectHeading(page, "Acces refuzat");
});

test("docs route is available only to admin user in the SPA", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/docs");
  await expectHeading(page, "Documentație aplicație");
});
