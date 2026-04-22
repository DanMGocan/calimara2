# Super-Apreciez — Design Spec

**Date:** 2026-04-22
**Status:** Approved, ready for implementation planning

## Summary

Add a scarce "super-like" reaction called **Super-apreciez** to Calimara. Every registered user gets a small weekly quota of super-apreciez which they can spend on other users' posts. Posts that have received at least one super-apreciez are visually distinguished with a gold accent under the title. Users who want more super-apreciez per week can pay for a **Premium** subscription via Stripe.

## Feature rules (locked)

- **Free users:** weekly quota = **1** super-apreciez.
- **Premium users:** weekly quota = **3** super-apreciez.
- **Weekly reset:** every Monday 00:00 UTC, the wallet is **hard reset** to the user's quota. Unused super-apreciez from the previous week are lost. Max a user can hold at any time = their weekly quota.
- **No self-super-apreciez:** a user cannot super-apreciez their own post.
- **One per user per post:** a user cannot super-apreciez the same post more than once (enforced by a DB unique constraint).
- **Toggle semantics:** clicking a second time within the same ISO week *undoes* the super-apreciez and returns the credit. Undoing in a later week does nothing to quota (the credit has already reset away).
- **Golden border:** any post with `super_likes_count >= 1` is rendered with a gold accent beneath the title in all contexts (detail page, feed cards, category pages, search, collections).
- **Premium tier:** €3.99/month recurring, Stripe-hosted checkout. Billing management via the Stripe-hosted Customer Portal. No one-off super-apreciez purchases.

## Architecture choices

### 1. Quota is derived, not stored
Remaining quota is computed on demand as:

```
weekly_quota(user) - count(SuperLike where user_id=u and created_at >= start_of_iso_week_utc())
```

No `super_like_wallet` table, no cron job, no counter drift. The `SuperLike` rows are the single source of truth.

### 2. Premium status is stored locally, reconciled by Stripe webhook
Stored on `User`: `stripe_customer_id`, `stripe_subscription_id`, `premium_until`. The `is_premium` property is `premium_until is not None and premium_until > utcnow()`. This survives Stripe outages and webhook latency.

### 3. Stripe integration uses hosted Checkout + Customer Portal
We never touch card data. Stripe hosts the upgrade flow and the "manage subscription" page. Minimum PCI scope, minimum code.

## Data model

### New table `super_likes`

```
super_likes
  id              PK
  post_id         FK posts.id  ON DELETE CASCADE
  user_id         FK users.id  ON DELETE CASCADE     -- always set, never anonymous
  created_at      TIMESTAMP DEFAULT now()
  UNIQUE (user_id, post_id)                          -- enforces "one per user per post"
  INDEX (user_id, created_at)                        -- fast weekly-count lookups
  INDEX (post_id)                                    -- fast count aggregation
```

Semantically parallel to `likes`, but separate because the rules differ: no anonymous/IP super-likes, quota enforcement, no self-giving.

### New table `stripe_events`

```
stripe_events
  id              TEXT PK                            -- Stripe event.id
  type            TEXT NOT NULL
  received_at     TIMESTAMP DEFAULT now()
```

Exists solely for webhook idempotency — replayed events are no-ops.

### `Post` additions

- `super_likes` relationship (`List[SuperLike]`)
- `@hybrid_property super_likes_count` — mirrors the existing `likes_count` pattern (Python-side `len(self.super_likes)`, SQL expression using `select(func.count)...`)

### `User` additions

- `stripe_customer_id: Optional[str]` — set on first checkout, reused forever thereafter
- `stripe_subscription_id: Optional[str]` — the current active subscription, if any
- `premium_until: Optional[datetime]` — source of truth for "is premium right now"
- `@property is_premium` — `premium_until is not None and premium_until > utcnow()`
- `super_likes_given` relationship

### Week boundary

ISO week in **UTC, Monday 00:00**. Romania is UTC+2 / UTC+3 (DST); this maps to 02:00 / 03:00 Romania time — i.e., well inside "Monday morning." Avoids DST transition bugs entirely.

## API

### Super-apreciez endpoints (new `app/routers/super_like_routes.py`)

```
POST /api/posts/{post_id}/super-likes
  Auth:   required
  201:    SuperLike created, returned in body
  401:    "Trebuie să fii autentificat pentru a super-aprecia."
  403:    "Nu îți poți super-aprecia propria postare."
  404:    "Postarea nu a fost găsită."
  409:    "Ai super-apreciat deja această postare."
  403 (error code `quota_exhausted`):
          "Ai epuizat super-aprecierile pentru această săptămână."

DELETE /api/posts/{post_id}/super-likes
  Auth:   required
  204:    Success (row removed, quota returned if same ISO week)
  401:    as above
  404:    no existing super-like from this user on this post

GET /api/users/me/super-likes/quota
  Auth:   required
  200: {
    "weekly_quota": 3,
    "used_this_week": 2,
    "remaining": 1,
    "week_resets_at": "2026-04-27T00:00:00Z",
    "is_premium": true
  }
```

### Post-list response enrichment

Every endpoint that currently returns posts (home feed, category, blog, search, collection, post detail) gains two response fields:

- `super_likes_count: int`
- `viewer_super_liked: bool` — `false` for unauthenticated callers

This is what the frontend needs to render the golden border and the button's `active` state without a second round-trip per post.

### Server-side enforcement (in `crud.create_super_like`)

All inside a single transaction:

1. Reject if unauthenticated.
2. Load post; 404 if missing.
3. Reject if `post.user_id == user.id` (self).
4. Reject if a `SuperLike(user_id, post_id)` row already exists.
5. Count `SuperLike` rows for this user with `created_at >= start_of_iso_week_utc()`; reject if `>= weekly_quota(user)`.
6. Insert. The `UNIQUE (user_id, post_id)` constraint is the last-line race-condition guard.

### Stripe endpoints (new `app/routers/premium_routes.py`)

```
POST /api/premium/checkout
  Auth:   required
  Behavior: Creates (or reuses) Stripe Customer for the user, creates a
            Checkout Session in "subscription" mode with STRIPE_PRICE_ID_PREMIUM_MONTHLY,
            passes metadata={"user_id": str(user.id)} and client_reference_id=user.id.
  200: { "url": "https://checkout.stripe.com/..." }

POST /api/premium/portal
  Auth:   required; user must have stripe_customer_id
  Behavior: Creates a Billing Portal Session; returns redirect URL.
  200: { "url": "https://billing.stripe.com/..." }

POST /api/stripe/webhook
  Auth:   signature-verified via STRIPE_WEBHOOK_SECRET
  Behavior: Verifies, de-duplicates via stripe_events table, handles:
    - customer.subscription.created  -> set stripe_subscription_id,
                                        premium_until = sub.current_period_end
    - customer.subscription.updated  -> premium_until = sub.current_period_end
                                        (handles renewals, plan changes, pauses)
    - customer.subscription.deleted  -> leave premium_until as-is (user keeps paid time;
                                        is_premium flips false automatically when it passes);
                                        clear stripe_subscription_id
    - invoice.payment_failed         -> create a Notification (optional but recommended)
  200 fast, even on unknown event types (Stripe best practice).

GET /premium/success
  Thin page: polls /api/users/me every 1s (max 10s) until is_premium flips true,
  then redirects to /dashboard. Does NOT trust the redirect itself to grant premium;
  the webhook is the source of truth.

GET /premium/cancel
  Friendly "Nicio problemă, poate altă dată." page.
```

### Webhook security & correctness

- Signature verification via `stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)`.
- Idempotency via `stripe_events.id` — if we've seen the event ID, return 200 without reprocessing.
- User lookup order: `stripe_customer_id` match (preferred), then `client_reference_id` fallback from the Checkout Session.
- Return 200 even on unhandled event types so Stripe doesn't retry.

## Configuration (.env)

New required variables (added to the project's env-loading layer, with clear fail-fast if `STRIPE_ENABLED=True` and any of the dependent vars are missing):

```
STRIPE_ENABLED=True
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_PREMIUM_MONTHLY=price_...
STRIPE_SUCCESS_URL=https://calimara.ro/premium/success?session_id={CHECKOUT_SESSION_ID}
STRIPE_CANCEL_URL=https://calimara.ro/premium/cancel
STRIPE_CUSTOMER_PORTAL_RETURN_URL=https://calimara.ro/dashboard
```

The Stripe Price and Product are configured **in the Stripe dashboard, not in code** — one-time operator setup; the resulting Price ID goes into `.env`. Currency is **EUR**, amount **3.99**, interval **month**.

Dependency: `stripe>=10.0.0` added to `requirements.txt`.

## Frontend

### New API clients

- `frontend/src/api/superLikes.ts` — `superLikePost(postId)`, `unSuperLikePost(postId)`, `fetchQuota()`
- `frontend/src/api/premium.ts` — `startCheckout()` (redirects to Stripe), `openCustomerPortal()` (redirects to Stripe)

### `<SuperLikeButton>` component

Location: `frontend/src/components/ui/super-like-button.tsx`, sibling of the existing `reaction-button.tsx`.

- Star icon — gold fill when active, outline when inactive. Small count badge. Same visual grammar as `ReactionButton` so it sits cleanly next to the existing like button.
- Uses TanStack Query `useMutation` with optimistic update: on click, immediately toggle `viewer_super_liked` and increment/decrement `super_likes_count`; rollback on error.
- Quota fetched once per session via `useQuery(['super-like-quota'])`, invalidated after every mutation.
- Disabled states with tooltips:
  - **not logged in** — "Autentifică-te pentru a super-aprecia"
  - **own post** — "Nu îți poți super-aprecia propria postare"
  - **no quota left, free user** — "Ai folosit super-aprecierea săptămâna aceasta. Următoarea: luni. Upgrade la Premium pentru 3 pe săptămână."
  - **no quota left, premium** — "Ai folosit toate super-aprecierile săptămâna aceasta. Următoarele: luni."
- Tooltip on hover when enabled: "Îți mai rămân {N} super-aprecieri săptămâna aceasta."

### Golden border

- CSS class `has-super-like` added to the post card / post detail root whenever `super_likes_count >= 1`.
- Styling: gold (`#D4AF37`) bar directly beneath the title. Implemented either as a `border-bottom` on the title container or a `::after` pseudo-element sitting under the `<h1>`/`<h2>`. Height ~2px. Optional subtle inner glow (`box-shadow: inset 0 -4px 12px -8px #D4AF37`).
- Applied uniformly in: `PostDetailPage`, post cards on `LandingPage`, `BlogHomePage`, `CategoryPage`, `CollectionDetailPage`, and search results.

### `<PremiumPage />` — route `/premium`

- "Ce primești cu Premium" section: "3 super-aprecieri pe săptămână" (vs 1), small golden star as flavor.
- Price: **3.99 € / lună**.
- Single CTA button: "Devino Premium" → `startCheckout()`.
- If user is already premium: shows "Ești Premium până la {premium_until}" and a "Gestionează abonamentul" button → `openCustomerPortal()`.
- Entry points from elsewhere in the app:
  - Link in `SideMenu`
  - Subtle banner on `DashboardPage` for free users
  - "No quota left" tooltip on the `SuperLikeButton` for free users includes an "Upgrade la Premium" link

### `/premium/success` and `/premium/cancel`

- **Success**: "Mulțumim! Contul tău este acum Premium." Polls `/api/users/me` every 1s (max 10s) until `is_premium` flips true, then redirects to `/dashboard`.
- **Cancel**: "Nicio problemă, poate altă dată."

## Out of scope (explicit non-goals)

- One-off super-apreciez purchases (dropped — transaction fees don't make €0.49 viable).
- Tax/VAT handling beyond Stripe defaults (can be toggled on in Stripe Tax later, no code change).
- Proration on plan changes (only one plan exists).
- Yearly billing, coupons, free trials, promo codes.
- A "super-apreciez leaderboard" or discovery ranking based on super-likes. The golden border is the only discovery affordance in this cut.
- Email receipts (Stripe sends these automatically by default).

## Success criteria

- A free user can super-apreciez one post per ISO week, not their own, not the same post twice. Undoing within the same week restores their quota.
- A premium user can super-apreciez three posts per ISO week, same rules.
- A post that has received at least one super-apreciez shows a gold accent under its title on every page it appears.
- A free user can click "Devino Premium", complete Stripe Checkout with a test card, and within ~2 seconds see their quota go from 1 to 3 (after the webhook fires).
- A premium user can click "Gestionează abonamentul" and cancel via the Stripe Customer Portal. Their `premium_until` remains set to the end of the billing period they already paid for; `is_premium` remains true until that date passes.
- Webhook endpoint correctly verifies signatures, is idempotent on replayed events, and returns 200 on unhandled event types.
