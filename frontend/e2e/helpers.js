import { expect } from "@playwright/test";

export const E2E_PASSWORD = "e2e-password-123";

export const users = {
  author: { username: "e2e_author", email: "e2e_author@example.com" },
  reader: { username: "e2e_reader", email: "e2e_reader@example.com" },
  participant: { username: "e2e_participant", email: "e2e_participant@example.com" },
  target: { username: "e2e_target", email: "e2e_target@example.com" }
};

const cookieCache = new Map();
const defaultBaseUrl = process.env.E2E_BASE_URL || "http://localhost:18173";

function absoluteUrl(pathOrUrl, baseUrl = defaultBaseUrl) {
  return new URL(pathOrUrl, baseUrl).toString();
}

export function notificationsButton(page) {
  // Logged-out visitors also see a locked Notificări icon (and an inert one while the session loads),
  // so only match the live one.
  return page.locator('.nav button[aria-label="Notificări"]:not(.is-locked):not([aria-disabled="true"])');
}

export async function loginByApi(page, user = users.author, options = {}) {
  const loginBaseUrl = absoluteUrl(options.loginBaseUrl || "/");
  const loginOrigin = new URL(loginBaseUrl).origin;
  const returnTo = absoluteUrl(options.returnTo || "/", loginOrigin);
  const cachedCookies = cookieCache.get(`${user.email}:${loginOrigin}`);
  if (cachedCookies?.length) {
    await page.context().addCookies(cachedCookies);
    await page.goto(returnTo);
    await expect(notificationsButton(page)).toBeVisible();
    return;
  }

  const response = await page.context().request.post(`${loginOrigin}/api/autentificare/parola/login`, {
    data: {
      email: user.email,
      password: E2E_PASSWORD,
      return_to: returnTo
    }
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  cookieCache.set(`${user.email}:${loginOrigin}`, await page.context().cookies());
  await page.goto(returnTo);
  await expect(notificationsButton(page)).toBeVisible();
}

export async function loginThroughModal(page, user = users.author) {
  await page.goto("/");
  await page.getByLabel("Autentificare").first().click();
  await expect(page.getByRole("dialog", { name: /Autentificare|Cont utilizator/ })).toBeVisible();
  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Parolă").fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "Intră în cont" }).click();
  await expect(notificationsButton(page)).toBeVisible();
  cookieCache.set(`${user.email}:${new URL(defaultBaseUrl).origin}`, await page.context().cookies());
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
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}

export async function expectPageReady(page) {
  await expect(page.locator(".site")).toBeVisible();
  await expect(page.locator(".status-panel", { hasText: "Nu am putut" })).toHaveCount(0);
}
