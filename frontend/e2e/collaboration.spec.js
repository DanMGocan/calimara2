import { expect, test } from "@playwright/test";
import { expectHeading, fillRichText, loginByApi, users } from "./helpers.js";

test("theatre list and play detail expose collaborative state", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/teatru");
  await expectHeading(page, "Teatru colaborativ");
  await expect(page.getByText("E2E Teatru")).toBeVisible();

  await page.goto("/teatru/e2e-teatru");
  await expectHeading(page, "E2E Teatru");
  await expect(page.getByRole("heading", { name: "Scena E2E" })).toBeVisible();
  await expect(page.getByText("Narator").first()).toBeVisible();
});

test("theatre actor sees current turn controls", async ({ page }) => {
  await loginByApi(page, users.reader);
  await page.goto("/teatru/e2e-teatru");
  await expect(page.getByText("Este rândul tău")).toBeVisible();
  await expect(page.locator("#theatre-reply")).toBeVisible();
});

test("stafeta list and detail render creator controls", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/stafeta");
  await expectHeading(page, "Ștafeta");
  await expect(page.getByText("E2E Ștafeta")).toBeVisible();

  await page.goto("/stafeta/e2e-stafeta");
  await expectHeading(page, "E2E Ștafeta");
  await expect(page.getByText("Control creator")).toBeVisible();
  await expect(page.getByText("Rând curent")).toBeVisible();
});

test("stafeta current holder can write and choose handoff destination", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/stafeta/e2e-stafeta");
  await expect(page.getByText("Este rândul tău")).toBeVisible();
  await fillRichText(page, "#stafeta-contribution", "Continuare E2E în browser.");
  await expect(page.locator(".stafeta-char-count")).toContainText("/ 400");
  await expect(page.getByLabel("Aleatoriu")).toBeChecked();
  await expect(page.getByRole("button", { name: /Trimite Ștafeta/ })).toBeEnabled();
});

test("stafeta creation form exposes deadline and character limit controls", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/stafeta/nou");
  await expectHeading(page, "Ștafetă nouă");
  await expect(page.getByLabel("Timp la fiecare participant")).toBeVisible();
  await expect(page.getByLabel("Numărul maxim de caractere:")).toHaveValue("400");
  await expect(page.getByText("Aleatoriu din participanții înscriși")).toBeVisible();
  await expect(page.getByRole("button", { name: "Creează Ștafeta" })).toBeVisible();
});
