import { expect, test } from "@playwright/test";

const hintText = "Dublu click sau dublu tap ca să treci la postarea următoare.";

function mockPost(id, title) {
  const body = Array.from(
    { length: 28 },
    (_, index) => `<p>Text E2E pentru ${title}, fragmentul ${index + 1}. Acesta verifică gestul de schimbare și indicatorul de derulare.</p>`
  ).join("");
  return {
    id,
    user_id: 9100,
    title,
    slug: `gesture-${id}`,
    content: body,
    explanatory_note: "",
    category: "poezie",
    category_name: "Poezie",
    view_count: 3,
    vizualizari: 3,
    seconds_listened: 0,
    likes_count: 0,
    viewer_liked: false,
    comments_count: 0,
    super_likes_count: 0,
    viewer_super_liked: false,
    viewer_promoted: false,
    moderation_status: "approved",
    created_at: "2026-05-19T10:00:00",
    updated_at: "2026-05-19T10:00:00",
    owner: {
      id: 9100,
      username: "gesture_author",
      avatar_seed: "gesture-author-shapes",
      subtitle: "",
      is_premium: false,
      premium_tier: "free"
    }
  };
}

async function mockAuthenticatedUser(page) {
  await page.route("**/api/utilizator/eu", (route) => route.fulfill({
    json: {
      authenticated: true,
      user: {
        id: 9200,
        username: "reaction_reader",
        is_premium: true,
        premium_tier: "rapsod",
        has_audio_access: true,
        has_author_audio_access: true
      }
    }
  }));
}

async function mockLandingFeed(page) {
  const posts = [mockPost(9101, "Gesture Poem One"), mockPost(9102, "Gesture Poem Two")];
  let landingCalls = 0;

  await page.route("**/api/audio/postari/**", (route) => route.fulfill({
    json: {
      available: false,
      can_listen: false,
      requires_audio_tier: false,
      status: null,
      source: null,
      audio_id: null,
      playback_url: null,
      content_type: null,
      title: null,
      author_username: null,
      message: "Nu există audio pentru acest text."
    }
  }));

  await page.route("**/api/prima-pagina?**", (route) => {
    const post = landingCalls < 2 ? posts[0] : posts[1];
    landingCalls += 1;
    return route.fulfill({
      json: {
        random_posts: [post],
        stats: {
          total_posts: posts.length,
          total_authors: 1
        }
      }
    });
  });

  return {
    calls: () => landingCalls,
    titles: posts.map((post) => post.title)
  };
}

async function mockReactionLanding(page) {
  await mockAuthenticatedUser(page);
  const post = mockPost(9201, "Reaction Poem");

  await page.route("**/api/audio/postari/**", (route) => route.fulfill({
    json: {
      available: false,
      can_listen: false,
      requires_audio_tier: false,
      status: null,
      source: null,
      audio_id: null,
      playback_url: null,
      content_type: null,
      title: null,
      author_username: null,
      message: "Nu există audio pentru acest text."
    }
  }));

  await page.route("**/api/prima-pagina?**", (route) => route.fulfill({
    json: {
      random_posts: [{ ...post }],
      stats: {
        total_posts: 1,
        total_authors: 1
      }
    }
  }));

  await page.route("**/api/postari/9201/aprecieri", (route) => {
    if (route.request().method() === "POST") {
      post.viewer_liked = true;
      post.likes_count = 1;
      return route.fulfill({
        json: {
          id: 1,
          post_id: post.id,
          user_id: 9200,
          ip_address: null,
          created_at: "2026-05-19T10:01:00"
        }
      });
    }
    if (route.request().method() === "DELETE") {
      post.viewer_liked = false;
      post.likes_count = 0;
      return route.fulfill({ status: 204, body: "" });
    }
    return route.continue();
  });

  await page.route("**/api/postari/9201/super-aprecieri", (route) => {
    if (route.request().method() === "POST") {
      post.viewer_super_liked = true;
      post.super_likes_count = 1;
      return route.fulfill({
        status: 201,
        json: {
          id: 1,
          post_id: post.id,
          user_id: 9200,
          created_at: "2026-05-19T10:02:00"
        }
      });
    }
    if (route.request().method() === "DELETE") {
      post.viewer_super_liked = false;
      post.super_likes_count = 0;
      return route.fulfill({ status: 204, body: "" });
    }
    return route.continue();
  });

  return { post };
}

async function mockAudioSecondsLanding(page) {
  await mockAuthenticatedUser(page);
  const post = mockPost(9301, "Audio Seconds Poem");
  const recordedSeconds = [];

  await page.route("**/api/audio/postari/**", (route) => route.fulfill({
    json: {
      available: true,
      can_listen: true,
      requires_audio_tier: false,
      status: "ready",
      source: "tts",
      audio_id: 9301,
      playback_url: "/api/audio/redare/9301",
      content_type: "audio/mpeg",
      title: post.title,
      author_username: post.owner.username,
      message: null
    }
  }));

  await page.route("**/api/audio/asculta/secunde", async (route) => {
    const payload = route.request().postDataJSON();
    recordedSeconds.push(payload);
    return route.fulfill({
      json: {
        recorded: true,
        audio_id: payload.audio_id,
        post_id: post.id,
        seconds: payload.seconds,
        mode: payload.mode,
        total_post_seconds: payload.seconds,
        total_author_seconds: payload.seconds
      }
    });
  });

  await page.route("**/api/prima-pagina?**", (route) => route.fulfill({
    json: {
      random_posts: [{ ...post }],
      stats: {
        total_posts: 1,
        total_authors: 1
      }
    }
  }));

  return { recordedSeconds };
}

test("landing reader keeps metadata centered and moves the dismissible double-tap hint above the text", async ({ page }) => {
  await mockLandingFeed(page);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Gesture Poem One" })).toBeVisible();

  const hint = page.locator(".piece-text-hint").getByText(hintText);
  await expect(hint).toBeVisible();
  await expect(page.locator(".piece-meta .piece-next-hint")).toHaveCount(0);
  await expect(page.locator(".piece-body-inner > .piece-text-hint + .piece-text-gesture-zone")).toHaveCount(1);
  await expect(page.locator(".piece-text-hint")).toHaveCSS("border-bottom-style", "solid");
  await expect(page.locator(".scroll-hint-wrap")).toBeVisible();
  await expect(page.locator(".scroll-hint-wrap")).toContainText("derulează");
  await expect(page.locator(".scroll-progress")).toHaveText(/\(\d+%\)/);
  const hintGap = await page.locator(".piece-text-hint").evaluate((hintElement) => {
    const meta = document.querySelector(".piece-meta");
    if (!meta) return Number.POSITIVE_INFINITY;
    return hintElement.getBoundingClientRect().top - meta.getBoundingClientRect().bottom;
  });
  expect(hintGap).toBeLessThanOrEqual(38);

  const metaCenter = await page.locator(".piece-meta").evaluate((meta) => {
    const children = Array.from(meta.children).map((child) => child.getBoundingClientRect());
    const left = Math.min(...children.map((box) => box.left));
    const right = Math.max(...children.map((box) => box.right));
    return (left + right) / 2;
  });
  const columnCenter = await page.locator(".piece-col").evaluate((column) => {
    const box = column.getBoundingClientRect();
    return box.left + box.width / 2;
  });
  expect(Math.abs(metaCenter - columnCenter)).toBeLessThanOrEqual(2);

  await page.waitForTimeout(3_500);
  await expect(hint).toBeVisible();

  await page.getByLabel("Ascunde indiciul de dublu click").click();
  await expect(page.locator(".piece-text-hint.is-dismissing")).toHaveCount(1);
  await expect(hint).toBeHidden();
  await expect.poll(() => page.evaluate(() => window.sessionStorage.getItem("calimara.reader.textGestureHintDismissed"))).toBe("1");

  await page.reload();
  await expect(page.getByRole("heading", { name: "Gesture Poem Two" })).toBeVisible();
  await expect(page.locator(".piece-text-hint")).toHaveCount(0);
  await expect(page.locator(".scroll-hint-wrap")).toBeVisible();
});

test("landing reader double click changes the displayed work", async ({ page }) => {
  const feed = await mockLandingFeed(page);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: feed.titles[0] })).toBeVisible();

  const textZone = page.locator("[data-reader-text-zone='landing-shuffle']");
  const callsAfterLoad = feed.calls();
  await textZone.click();
  await expect(page.getByRole("heading", { name: feed.titles[0] })).toBeVisible();
  expect(feed.calls()).toBe(callsAfterLoad);

  await textZone.dblclick({ position: { x: 40, y: 40 } });
  await expect(page.getByRole("heading", { name: feed.titles[1] })).toBeVisible();
  expect(feed.calls()).toBe(callsAfterLoad + 1);
});

test("landing reader double tap changes the displayed work", async ({ page }) => {
  const feed = await mockLandingFeed(page);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: feed.titles[0] })).toBeVisible();

  const textZone = page.locator("[data-reader-text-zone='landing-shuffle']");
  const tap = async () => {
    await textZone.dispatchEvent("pointerdown", {
      bubbles: true,
      pointerId: 11,
      pointerType: "touch",
      isPrimary: true,
      button: 0,
      clientX: 56,
      clientY: 56
    });
    await textZone.dispatchEvent("pointerup", {
      bubbles: true,
      pointerId: 11,
      pointerType: "touch",
      isPrimary: true,
      button: 0,
      clientX: 56,
      clientY: 56
    });
  };

  await tap();
  await expect(page.getByRole("heading", { name: feed.titles[0] })).toBeVisible();
  const callsAfterFirstTap = feed.calls();

  await tap();
  await expect(page.getByRole("heading", { name: feed.titles[1] })).toBeVisible();
  expect(feed.calls()).toBe(callsAfterFirstTap + 1);
});

test("reader reaction buttons use active colors and persist viewer state after reload", async ({ page }) => {
  await mockReactionLanding(page);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Reaction Poem" })).toBeVisible();

  const likeButton = page.locator(".react-like");
  const superButton = page.locator(".react-super");

  await likeButton.hover();
  await expect(likeButton).toHaveCSS("background-color", "rgb(184, 74, 42)");
  await expect(likeButton.locator(".react-symbol")).toHaveCSS("color", "rgb(255, 255, 255)");
  await expect(likeButton.locator(".react-count")).toHaveCSS("color", "rgb(255, 255, 255)");

  await likeButton.click();
  await expect(likeButton).toHaveClass(/on/);
  await expect(likeButton).toHaveAttribute("aria-pressed", "true");
  await expect(likeButton.locator(".react-count")).toHaveText("1");
  await expect(likeButton).toHaveCSS("background-color", "rgb(184, 74, 42)");
  await expect(likeButton).toBeDisabled();

  await page.reload();
  await expect(page.getByRole("heading", { name: "Reaction Poem" })).toBeVisible();
  await expect(page.locator(".react-like")).toHaveClass(/on/);
  await expect(page.locator(".react-like")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".react-like")).toBeDisabled();
  await expect(page.locator(".react-like .react-count")).toHaveText("1");

  await superButton.hover();
  await expect(superButton).toHaveCSS("background-color", "rgb(184, 135, 0)");
  await expect(superButton.locator(".react-symbol")).toHaveCSS("color", "rgb(255, 255, 255)");
  await expect(superButton.locator(".react-count")).toHaveCSS("color", "rgb(255, 255, 255)");

  await superButton.click();
  await expect(superButton).toHaveClass(/on/);
  await expect(superButton).toHaveAttribute("aria-pressed", "true");
  await expect(superButton.locator(".react-count")).toHaveText("1");
  await expect(superButton).toHaveCSS("background-color", "rgb(184, 135, 0)");
  await expect(superButton).toBeDisabled();

  await page.reload();
  await expect(page.getByRole("heading", { name: "Reaction Poem" })).toBeVisible();
  await expect(page.locator(".react-super")).toHaveClass(/on/);
  await expect(page.locator(".react-super")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".react-super")).toBeDisabled();
  await expect(page.locator(".react-super .react-count")).toHaveText("1");
});

test("inline post audio records listened seconds", async ({ page }) => {
  const audio = await mockAudioSecondsLanding(page);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Audio Seconds Poem" })).toBeVisible();
  await expect(page.locator(".post-audio-inline audio")).toHaveAttribute("src", "/api/audio/redare/9301");

  await page.evaluate(() => {
    const audioElement = document.querySelector(".post-audio-inline audio");
    audioElement.currentTime = 0;
    audioElement.dispatchEvent(new Event("play", { bubbles: true }));
    audioElement.currentTime = 45.3;
    audioElement.dispatchEvent(new Event("timeupdate", { bubbles: true }));
    audioElement.dispatchEvent(new Event("pause", { bubbles: true }));
  });

  await expect.poll(() => audio.recordedSeconds.length).toBe(1);
  expect(audio.recordedSeconds[0]).toMatchObject({
    audio_id: 9301,
    seconds: 45,
    mode: "poezie"
  });
});
