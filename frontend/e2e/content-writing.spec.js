import { expect, test } from "@playwright/test";
import { expectHeading, fillRichText, loginByApi, users } from "./helpers.js";

async function pasteIntoPostEditor(page, { text, html = "" }) {
  const editor = page.locator("#post-content");
  await expect(editor).toBeVisible();
  await editor.click();
  await editor.evaluate((node, payload) => {
    const data = new DataTransfer();
    data.setData("text/plain", payload.text);
    if (payload.html) data.setData("text/html", payload.html);
    node.dispatchEvent(new ClipboardEvent("paste", {
      clipboardData: data,
      bubbles: true,
      cancelable: true
    }));
  }, { text, html });
}

async function postEditorHtml(page) {
  return page.locator("#post-content").evaluate((node) => node.innerHTML);
}

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

test("post editor cleans pasted prose hard wraps", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/scrie");
  await page.getByLabel("Categorie").selectOption("proza_scurta");
  await pasteIntoPostEditor(page, {
    text: "Primul rând copiat\nse continuă fără pauză.\n\nAl doilea paragraf."
  });

  await expect(page.locator("#post-content")).toContainText("Primul rând copiat se continuă fără pauză.");
  const html = await postEditorHtml(page);
  expect(html).not.toContain("<span");
  expect(html).not.toContain("style=");
});

test("post editor preserves pasted poetry line breaks", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/scrie");
  await page.getByLabel("Categorie").selectOption("poezie");
  await pasteIntoPostEditor(page, {
    text: "vers unu\nvers doi\n\nstrofa a doua"
  });

  const html = await postEditorHtml(page);
  expect(html).toContain("<br");
  await expect(page.locator("#post-content")).toContainText("vers unu");
  await expect(page.locator("#post-content")).toContainText("vers doi");
  await expect(page.locator("#post-content")).toContainText("strofa a doua");
});

test("post editor strips pasted styles but keeps safe emphasis", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.goto("/scrie");
  await pasteIntoPostEditor(page, {
    text: "Salut tare\n\nAlt paragraf",
    html: '<p style="margin:0;line-height:42px"><span style="font-family:Papyrus">Salut <strong style="color:red">tare</strong></span></p><p>Alt paragraf</p>'
  });

  const html = await postEditorHtml(page);
  expect(html).toContain("<strong>tare</strong>");
  expect(html).not.toContain("<span");
  expect(html).not.toContain("style=");
});

test("post editor applies AI formatting result", async ({ page }) => {
  await loginByApi(page, users.author);
  await page.route("**/api/scriere/formatare-ai", async (route) => {
    const payload = route.request().postDataJSON();
    expect(payload.category).toBe("proza_scurta");
    expect(payload.content.replace(/&nbsp;|\u00a0/g, " ")).toContain("vers unu");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        category: "poezie",
        content: "<p>vers unu<br>vers doi</p>",
        changed: true
      })
    });
  });

  await page.goto("/scrie");
  await page.getByLabel("Categorie").selectOption("proza_scurta");
  await fillRichText(page, "#post-content", "vers unu\nvers doi");
  await page.getByRole("button", { name: "Curăță formatarea cu AI" }).click();

  await expect(page.getByLabel("Categorie")).toHaveValue("poezie");
  await expect(page.locator("#post-content")).toContainText("vers unu");
  const html = await postEditorHtml(page);
  expect(html).toContain("<br");
});
