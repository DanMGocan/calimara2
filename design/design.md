# calimara.ro — Design System

A minimal editorial design system for a Romanian poetry and short-prose platform. Modern, sleek, near-monochrome with an atmospheric WW1 visual motif (stormy sky + shelled forest) fading behind clean white paper.

Use this document as the single source of truth for all pages beyond the landing. Every new screen (author page, reader, archive, collection, profile, auth, about, 404, etc.) must follow these rules.

---

## 1. Brand voice

- **Tone**: quiet, literary, contemplative. Romanian first — do not translate to English.
- **Copy style**: concise, lowercase labels where possible, serif for reading, sans for UI chrome.
- **Imagery metaphor**: early 20th-century Romanian literary journals; the WW1 background is atmospheric, never illustrative or decorative filler.

---

## 2. Layout

### Container

A single centered container, Bootstrap `container-xl` equivalent:

```css
max-width: 1140px;
width: 100%;
margin: 0 auto;
padding: 0 48px; /* 36px @ ≤1180, 24px @ ≤820 */
```

Applied identically to: nav, main stage, footer inner. Content is horizontally centered; left and right gutters are equal at every viewport.

### Stage grid

Default two-column for reading surfaces:

```css
.stage {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 72px;
  padding: 72px 48px 140px;
}
```

- Left column: sticky actions + secondary content (stats, related, TOC).
- Right column: primary content, fills the remaining width edge-to-edge.
- Collapse to a single column at `max-width: 820px`.

### Navbar

- Height: 64px.
- Sticky top, z-index: 20, transparent background (no border).
- Left: home icon (22px line-art house) + brand `călimara` (serif 24px) + `.ro` (mono 12px, same black).
- Right: 44px icon buttons, transparent, no border, no circular background. SVG glyphs at 22px. Profile icon + burger.
- No logo image.

### Footer

Three-column grid (`1fr auto 1fr`):
- Left: legal links (Politica de confidențialitate / Termeni și condiții / Contact) — underline-on-hover, muted ink.
- Center: `© 2026 călimara.ro`
- Right: social icons — 34px white circles, 2px black border, black icon inside. Hover inverts to solid black + white icon + 1px lift.

---

## 3. Typography

```css
--serif: 'Roboto Serif', 'Newsreader', Georgia, serif;
--sans:  'Roboto', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif;
--mono:  'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace;
```

Load from Google Fonts: Roboto 400/500/600/700, Roboto Serif 400/500/600, JetBrains Mono 400/500.

### Roles

| Role | Family | Size | Weight | Notes |
|---|---|---|---|---|
| Page title / piece title | serif | clamp(40px, 5.2vw, 68px) | 500 | `letter-spacing: -0.02em`, `line-height: 1.05`, `text-wrap: balance` |
| Section heading | serif | 28px | 500 | |
| Body prose / poem | serif | 20px | 400 | `line-height: 1.65` |
| UI label / button | sans | 12–13px | 500 | |
| Meta / author / date | sans | 12–13px | 400 | `--ink-mute` color |
| Kicker / overline | mono | 10–11px | 400 | `text-transform: uppercase`, `letter-spacing: 0.14em` |
| Reading count / number | mono | 11px | 500 | |

Never use Inter, system-ui, or emoji as typographic elements.

---

## 4. Color

Near-monochrome with a single warm accent.

```css
:root {
  color-scheme: light only;
  --paper:          #ffffff;
  --paper-2:        #fafaf8;
  --paper-3:        #f3f2ee;
  --ink:            #111111;
  --ink-soft:       #2a2a2e;
  --ink-mute:       #555559;
  --ink-faint:      #8a8a8f;
  --hairline:       #e4e4e0;
  --hairline-strong:#c9c9c4;
  --accent:         #b84a2a; /* ember — used sparingly */
  --like:           #d93838; /* heart-filled state only */
}
```

Rules:
- Default page background: `--paper`.
- No gradients as decoration. The only gradients allowed are CSS masks (image fades, scroll masks).
- `color-scheme: light only` on `:root` to prevent dark-mode inversion.
- Accent is reserved for hover affordance on links and the rare active tab/badge. Never as large fills.

---

## 5. Spacing, radii, borders

- Spacing scale (px): 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 72, 96, 140.
- Border radius: `8px` for all buttons, inputs, and cards. `10px` for content cards (comments, articles). `0` for the nav and full-bleed rules.
- Borders: always 1px. `--hairline` for dividers, `--hairline-strong` for input outlines, `--ink-faint` for button outlines. No drop shadows on standard surfaces.

---

## 6. Components

### Button (unified style for all action buttons)

```css
display: inline-flex; align-items: center; gap: 8px;
height: 34px; padding: 0 14px;
border: 1px solid var(--ink-faint);
border-radius: 8px;
background: transparent;
font: 500 12px/1 var(--sans);
color: var(--ink-soft);
letter-spacing: 0.01em;
transition: color 160ms, border-color 160ms, background 160ms;
```

Hover: `color: var(--ink)`, `border-color: var(--ink)`, `background: rgba(0,0,0,0.04)`.
Active state: adds `transform: translateY(1px)` on `:active`.

Toggled state (`.on`): `color: var(--ink); border-color: var(--ink); background: rgba(0,0,0,0.04)`.

Special: `.react-like.on` uses `--like` for color + border + 5% bg wash.

All buttons include an SVG glyph (12–14px, 1.2px stroke, currentColor) on the left. Never use filled pill shapes or bold weights.

### Icon-only button (nav)

- 44×44 click target, no background, no border, SVG 22px `currentColor`.
- Hover: `translateY(-1px)`.

### Input

- Height 40px, 1px `--hairline-strong` border, 8px radius, white background.
- Focus: `border-color: var(--ink)`, no glow.

### Card

- `padding: 14–20px`, 1px `--hairline` border, 10px radius, `rgba(255,255,255,0.6)` background.
- No shadow. Hover-raisable cards add `translateY(-1px)` + `border-color: var(--ink-faint)`.

### Meta row

```
<Author> · <Year> · <Optional tag>
```
Sans 13px `--ink-mute`, dots are 3px circles (`--ink-faint`), `gap: 10px`.

### Kind badge

Small uppercase mono kicker above a title — `11px`, `letter-spacing: 0.14em`, `--ink-faint`. Used to label page type (Poezie, Proză scurtă, Autor, Colecție, etc.).

### Reveal text (for literary reading views)

Line-by-line fade + 4px rise, stagger `0.035s` per line, starting at `0.08s`. Preserves source `\n` as explicit `<div class="reveal-line">`. Blank lines render as `.reveal-blank`. Poems keep their line breaks verbatim; prose paragraphs separated by blank lines.

### Scroll mask

For long-form reading panels, apply CSS `mask-image` to the scrollable body, not a white overlay:

```css
mask-image: linear-gradient(180deg, transparent 0, #000 100px, #000 calc(100% - 100px), transparent 100%);
```

Modify via `.at-top` / `.at-bottom` state classes to drop the corresponding fade when at the edge.

### Comments panel

- Expands below the action row (not between action rows) with a max-height unfurl animation, 420ms cubic-bezier(0.2,0.7,0.2,1).
- List: `gap: 14px`, each comment is a card (see above).
- Head row: `author` (sans 13px 600) on the left, `time` (sans 11px `--ink-faint`) on the right.
- Body: serif 14px `--ink-soft`, `line-height: 1.55`.

---

## 7. Background atmosphere

Global fixed overlay behind all content. Two raster PNG layers with CSS masks:

```css
.bg-atmos { position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden; }

.bg-sky {
  position: absolute; top: 0; left: 0; right: 0; height: 48%;
  background: url('/assets/bg-sky.png') top center / cover no-repeat;
  mask-image: linear-gradient(180deg, #000 0%, #000 50%, transparent 100%);
  opacity: 0.35; filter: grayscale(1) contrast(0.9); mix-blend-mode: multiply;
}

.bg-forest {
  position: absolute; bottom: 0; left: 0; right: 0; height: 26%;
  background: url('/assets/bg-forest.png') bottom center / cover no-repeat;
  mask-image: linear-gradient(0deg, #000 0%, #000 50%, transparent 100%);
  opacity: 0.4; filter: grayscale(1) contrast(0.9); mix-blend-mode: multiply;
}
```

- Sky = stormy WW1 scene (biplane silhouette, crows).
- Forest = shattered trees, barbed wire, muddy craters.
- Both assets are monochrome PNGs with transparency fading to white. Never SVG — raster gives the painterly quality.
- The middle band (~26% of viewport) is clean white — this is where headlines and primary content live.

Every page must include this background. It is the literal visual signature of the platform.

---

## 8. Motion

- Duration tokens: `140ms` (micro), `200ms` (standard), `320–420ms` (panels, reveals).
- Easing: `cubic-bezier(0.2, 0.7, 0.2, 1)` for entrances, `ease` for micro-transitions.
- Hover translateY never exceeds 1–2px.
- Page transitions between pieces: 320ms opacity + 8px translateY on the whole `.piece-wrap`.
- Respect `prefers-reduced-motion` — disable all transforms and fades, keep opacity instant.

---

## 9. Accessibility

- Minimum text size 12px for meta, 16px for body, 20px for reading prose.
- Focus ring: `outline: 2px solid var(--ink); outline-offset: 2px` (only on `:focus-visible`).
- Every interactive icon has `aria-label` in Romanian.
- Contrast: body text is `--ink` on `--paper` (AAA); muted text is `--ink-mute` (AA).
- Comments, modals, menus are keyboard-reachable; Escape closes overlays.

---

## 10. Page patterns

### Reading surface (poem / story)

```
[ nav ]
[ stage grid ]
  ├─ left-col (sticky): primary actions — "Poezie la întâmplare" / "Proză la întâmplare"
  └─ piece-wrap
        ├─ kind badge (mono kicker)
        ├─ title (serif display)
        ├─ meta row (author · year)
        ├─ scrollable body with mask + derulează arrow
        ├─ reactions row (Apreciază / Distribuie / Comentarii)
        ├─ actions row (PDF / Collection)
        └─ comments panel (collapsible, below both rows)
[ footer ]
```

### Index / archive / list

- Stage grid as above, left column becomes filters (kind, author, decade, collection).
- Right column: card list, each card mirrors the meta row + a 2-line serif excerpt. 10px radius, hover raises.
- Pagination: simple `‹ 1 2 … 12 ›` mono numerals, ember accent on current page.

### Author / collection page

- Hero: large serif title, mono kicker ("Autor" / "Colecție"), 1–2 line bio in serif 18px.
- Body: vertical list of pieces sharing the card pattern.

### Profile / auth

- Single centered card (max 480px), 1px hairline border, 10px radius, 32px padding.
- Sans 13px labels above inputs. Primary button matches the unified button style (no filled variant needed — this is a quiet platform).

### Modals / menus

- Burger menu: right-side slide-in panel, 320px wide, white, hairline left border, fade-in scrim at 40% black.
- Dialogs: same card pattern centered with scrim.

---

## 11. Print / PDF

All reading surfaces must print cleanly via `window.print()`:

```css
@media print {
  @page { margin: 20mm 18mm; size: A4; }
  html, body { background: #fff !important; }
  .bg-atmos, .nav, .left-col, .site-foot,
  .tweaks-panel, .menu-panel, .menu-scrim,
  .scroll-hint-wrap, .piece-reactions, .piece-actions,
  .piece-comments { display: none !important; }
  .stage { display: block !important; padding: 0 !important; max-width: 100% !important; }
  .piece-wrap { max-width: 100% !important; }
  .piece-scroll-wrap { height: auto !important; max-height: none !important; overflow: visible !important; }
  .piece-scroll { position: static !important; overflow: visible !important; mask-image: none !important; }
  .reveal-text, .reveal-line { opacity: 1 !important; animation: none !important; transform: none !important; }
}
```

Every page with readable content must include a "PDF" button that triggers `window.print()`.

---

## 12. Implementation notes

- **No build step**: React 18 + Babel Standalone inline, one CSS file per page group, one or two JSX files per page. Load order: React → ReactDOM → Babel → content data → JSX.
- **Split JSX** into `lib/<page>.jsx` (components) and `lib/<page>-content.js` (data on `window`). Keep files under ~600 lines.
- **Global styles** in `lib/landing.css` — new pages add their CSS by `@import`-ing or extending this file; do not duplicate tokens.
- **Cache-bust** URLs with `?v=N` when iterating on dev, but never bump gratuitously in production.
- **Images**: `/assets/bg-sky.png`, `/assets/bg-forest.png`. Any new imagery must be monochrome PNG with transparent edges.

---

## 13. Anti-patterns (do not do)

- Do not use Inter, system-ui, Poppins, or generic Google slab/serif stacks other than Roboto Serif.
- Do not add emoji, gradient fills, glass-morphism, drop shadows, or "colorful" backgrounds.
- Do not invent new accent colors. One accent only — ember (#b84a2a).
- Do not add "hero sections" with large stock photography. The WW1 background IS the visual identity.
- Do not use dark mode — the platform is intentionally light-only.
- Do not add filler stats ("1,248 authors · 9,712 texts") unless they directly serve navigation. No data slop.
- Do not translate Romanian UI strings to English.
- Do not center prose body paragraphs; left-align only. Titles and kickers may center contextually, but reading copy is always left.
- Do not scale buttons with hover — only `translateY(1–2px)` is allowed.
- Do not rely on SVG illustration for the atmospheric background. PNG only.
