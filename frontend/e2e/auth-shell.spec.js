import { expect, test } from "@playwright/test";
import { expectHeading, loginByApi, loginThroughModal, notificationsButton, users } from "./helpers.js";

test("public landing renders and logged-out protected pages show auth gate", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByLabel("Autentificare").first()).toBeVisible();

  await page.goto("/mesaje");
  await expectHeading(page, "Autentificare necesară");
  await expect(page.getByRole("main").getByRole("button", { name: "Autentificare" })).toBeVisible();
});

test("footer help route renders the public about page", async ({ page }) => {
  await page.goto("/ce-este-calimara");
  await expectHeading(page, "Ce este calimara.ro?");
});

test("password login works through the real modal", async ({ page }) => {
  await loginThroughModal(page, users.author);
  await expect(page.getByLabel("Călimara mea")).toBeVisible();
  await expect(notificationsButton(page)).toBeVisible();
});

test("notification shell opens and marks seeded notifications visible", async ({ page }) => {
  await loginByApi(page, users.author);
  await notificationsButton(page).click();
  await expect(page.locator("#profile-notification-panel")).toBeVisible();
  await expect(page.getByText("Notificare E2E")).toBeVisible();
});

test("mobile menu exposes core authenticated navigation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 820 });
  await loginByApi(page, users.author);
  await page.getByRole("button", { name: "Meniu" }).click();
  await expect(page.getByRole("link", { name: "Mesaje" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Ștafeta" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Teatru colaborativ" })).toBeVisible();
});
