import { expect } from "@playwright/test";

export const E2E_PASSWORD = "e2e-password-123";

export const users = {
  author: { username: "e2e_author", email: "e2e_author@example.com" },
  reader: { username: "e2e_reader", email: "e2e_reader@example.com" },
  participant: { username: "e2e_participant", email: "e2e_participant@example.com" },
  target: { username: "e2e_target", email: "e2e_target@example.com" }
};

const cookieCache = new Map();

export function notificationsButton(page) {
  return page.getByRole("button", { name: "Notificări" });
}

export async function loginByApi(page, user = users.author) {
  const cachedCookies = cookieCache.get(user.email);
  if (cachedCookies?.length) {
    await page.context().addCookies(cachedCookies);
    await page.goto("/");
    await expect(notificationsButton(page)).toBeVisible();
    return;
  }

  const response = await page.context().request.post("/api/autentificare/parola/login", {
    data: {
      email: user.email,
      password: E2E_PASSWORD,
      return_to: "/"
    }
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  cookieCache.set(user.email, await page.context().cookies());
  await page.goto("/");
  await expect(notificationsButton(page)).toBeVisible();
}

export async function loginThroughModal(page, user = users.author) {
  await page.goto("/");
  await page.getByLabel("Autentificare").first().click();
  await expect(page.getByRole("dialog", { name: "Autentificare" })).toBeVisible();
  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Parolă").fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "Intră în cont" }).click();
  await expect(notificationsButton(page)).toBeVisible();
  cookieCache.set(user.email, await page.context().cookies());
}

export async function fillRichText(page, selector, text) {
  const editor = page.locator(selector);
  await expect(editor).toBeVisible();
  await editor.click();
  try {
    await editor.fill(text);
  } catch {
    await page.keyboard.press(process.platform === "darwin" ? "Meta+A" : "Control+A");
    await page.keyboard.type(text);
  }
}

export async function expectHeading(page, name) {
  await expect(page.getByRole("heading", { name })).toBeVisible();
}

export async function expectPageReady(page) {
  await expect(page.locator(".site")).toBeVisible();
  await expect(page.locator(".status-panel", { hasText: "Nu am putut" })).toHaveCount(0);
}
