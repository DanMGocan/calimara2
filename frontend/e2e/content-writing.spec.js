import { expect, test } from "@playwright/test";
import { expectHeading, fillRichText, loginByApi, users } from "./helpers.js";

test("writer can save a draft from the rich-text editor", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/scrie");
  await expectHeading(page, "Text nou");
  await page.getByLabel("Titlu").fill(`E2E Draft ${Date.now()}`);
  await fillRichText(page, "#post-content", "Vers E2E scris în browser.");
  await page.getByRole("button", { name: "Salvează ca ciornă" }).click();
  await expect(page.getByText(/Ciornă salvată|Salvat automat|Ciorna este deja salvată/)).toBeVisible();
});

test("free user can submit a new post without premium diacritics flow", async ({ page }) => {
  await loginByApi(page, users.participant);
  await page.goto("/scrie");
  await page.getByLabel("Titlu").fill(`E2E Publicare ${Date.now()}`);
  await fillRichText(page, "#post-content", "Text E2E publicat fără diacritice automate.");
  await page.getByRole("button", { name: "Publică" }).click();
  await expect(page).toHaveURL(/e2e_participant\.localhost|\/$/);
});

test("archive and seeded post data are reachable", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/api/postari/arhiva");
  await expect(page.locator("body")).toContainText("e2e-poem");
});

test("draft resume list includes deterministic seed draft", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/scrie");
  await expect(page.getByRole("link", { name: /^E2E Draft Poezie/ })).toBeVisible();
});
