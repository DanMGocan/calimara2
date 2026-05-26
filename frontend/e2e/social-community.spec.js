import { expect, test } from "@playwright/test";
import { expectHeading, loginByApi, users } from "./helpers.js";

function userBlogUrl(username) {
  const url = new URL("/", process.env.E2E_BASE_URL || "http://localhost:18173");
  url.hostname = `${username}.${url.hostname}`;
  return url.toString();
}

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

  await page.getByRole("button", { name: /@e2e_reader/ }).click();
  await expect(page.getByText("Conversație privată")).toBeVisible();
  await expect(page.locator(".message-bubble", { hasText: "Mesaj E2E necitit" })).toBeVisible();

  await page.getByLabel("Scrie un mesaj").fill("Răspuns E2E privat");
  await page.locator(".message-reply-form").getByRole("button", { name: /Trimite/ }).click();
  await expect(page.locator(".message-bubble", { hasText: "Răspuns E2E privat" })).toBeVisible();

  await page.getByRole("button", { name: "Mesaj nou" }).click();
  await expect(page.getByRole("dialog", { name: "Mesaj nou" })).toBeVisible();
  await page.locator(".message-modal").getByLabel("Destinatar").fill("e2e_target");
  await page.getByRole("button", { name: /Alege @e2e_target/ }).click();
  await page.locator(".message-modal").getByRole("textbox", { name: "Mesaj", exact: true }).fill("Mesaj nou E2E");
  await page.locator(".message-modal").getByRole("button", { name: /Trimite/ }).click();
  await expect(page.getByRole("dialog", { name: "Mesaj nou" })).toHaveCount(0);
  await expect(page.locator(".messages-list").getByRole("button", { name: /@e2e_target/ })).toBeVisible();
  await expect(page.locator(".message-chat-user").getByText("@e2e_target", { exact: true })).toBeVisible();
  await expect(page.locator(".message-bubble", { hasText: "Mesaj nou E2E" })).toBeVisible();
});

test("public profile separates action rows and sends private message", async ({ page }) => {
  const profileUrl = userBlogUrl(users.reader.username);
  await loginByApi(page, users.author, { loginBaseUrl: profileUrl, returnTo: profileUrl });
  await expect(page.locator(".profile-social-row")).toBeVisible();
  await expect(page.locator(".profile-action-row")).toBeVisible();

  await page.locator(".profile-action-row").getByRole("button", { name: "Trimite mesaj privat" }).click();
  await expect(page.getByRole("dialog", { name: /Mesaj către @e2e_reader/ })).toBeVisible();
  await page.locator(".profile-message-modal").getByRole("textbox", { name: "Mesaj", exact: true }).fill("Mesaj din profil E2E");
  await page.locator(".profile-message-modal").getByRole("button", { name: /Trimite/ }).click();
  await expect(page.getByText("Mesajul a fost trimis.")).toBeVisible();
});

test("forum list and thread detail render seeded discussion", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/discutii");
  await expectHeading(page, "Discuții");
  await expect(page.getByRole("button", { name: "Anunțuri" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Discuții generale" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Impresii" })).toHaveCount(0);
  await expect(page.getByText("E2E Forum Thread")).toBeVisible();

  await page.goto("/discutii/e2e-forum-thread");
  await expectHeading(page, "E2E Forum Thread");
  await expect(page.locator(".forum-author-avatar").first()).toBeVisible();
  await expect(page.getByLabel("Statistici autor").first()).toBeVisible();
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
