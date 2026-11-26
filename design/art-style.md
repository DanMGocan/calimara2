# calimara.ro — Visual Art & Illustration Style Guide

**Approved Style:** *Tuș și laviu sepia* (Literary Sepia & Charcoal Ink Wash)
**Canonical Reference Asset:** [`design/assets/style-reference-ink-wash.png`](./assets/style-reference-ink-wash.png) (live preview: `/assets/style-mockups/manuscript-ink-wash.png`)
**Companion UI System:** [`design/design.md`](./design.md)
**Asset Pipeline Script:** [`scripts/prepare_art_asset.py`](../scripts/prepare_art_asset.py)

This document is the **single source of truth** for every future illustrated graphic on `calimara.ro`: shop items (*Magazin* / *Gologani*), clothing & costumes (*Costume*), artefacts & collectibles (*Artefacte*), profile badges (*Insigne*), avatar frames (*Rame*), atmospheric backgrounds (*Fundaluri*), and editorial spot illustrations.

Every human illustrator and every AI image-generation agent **must** follow this specification verbatim so that items created months apart look as though they were painted by the same hand for the same literary journal.

---

## 1. Artistic Identity & Aesthetic Philosophy

- **Visual lineage:** Early 20th-century Romanian & Central-European literary journals (*Viața Românească*, *Sămănătorul*, *Gândirea*, *fin-de-siècle* and interwar illustrated editions), paired with 19th-century archival manuscript engraving and studio watercolor notebooks.
- **Emotional register:** Quiet, tactile, contemplative, literary, weathered, hand-crafted. Never flashy, gamified, plastic, glossy, or loud.
- **Relationship to `calimara.ro`'s UI:** Per [`design/design.md`](./design.md), the platform is light-only, near-monochrome charcoal ink on clean white/warm paper (`#FFFFFF`, `#FAFAF8`, `#F3F2EE`) with a single ember accent (`#B84A2A`). Illustrated items must feel naturally drawn *onto* the editorial paper — never like foreign game icons pasted on top.
- **Core visual signature:** **Fine hand-drawn dip-pen sepia/charcoal linework + translucent warm sepia/umber ink-and-watercolor washes + at most ONE restrained ember-terracotta focal accent**, completely isolated on a true transparent background.

---

## 2. Canonical Reference Anchor

All future generations must be visually benchmarked against the approved Victorian manuscript reference:

- Repository path: `design/assets/style-reference-ink-wash.png`
- Served public asset: `frontend/public/assets/style-mockups/manuscript-ink-wash.png`

**Mandatory workflow rule for AI image generation:**
Whenever the image generation model or tool supports style/reference image input, attach `design/assets/style-reference-ink-wash.png` as a **style reference** (while explicitly instructing the model to keep only the medium, linework, ink wash, lighting, and palette — and to draw the new subject). Even when generating text-to-image only, every prompt must include the locked style block in Section 8.

---

## 3. Medium, Linework & Shading Rules

### 3.1 Dip-Pen Ink Linework (Primary Structure)
- **Tool feel:** Steel dip-pen or archival fountain nib on cotton rag paper.
- **Ink hue:** Warm iron-gall dark sepia (`#2B1D10` to `#43382B`) — **never** flat digital pure black (`#000000`) and **never** uniform vector strokes.
- **Weight modulation:**
  - Outer contours are crisp, confident, and continuous so the silhouette reads cleanly at `58×58px` without looking thick or cartoon-like.
  - Slightly heavier lines along undersides, overlapping folds, and cast-contact crevices; delicate tapered hairlines along lit top edges and inner details.
- **Hatching:** Short, parallel, slightly curved pen-and-ink hatching strokes describe curvature, rolled surfaces, fabric folds, wood grain, and deep shadow transitions. Avoid dense mechanical cross-hatching grids that turn muddy at small sizes.
- **Organic imperfection:** Subtle natural nib taper and minuscule hand tremor are welcome; sterile CAD/vector geometry is forbidden.

### 3.2 Translucent Sepia & Graphite Washes (Volume & Atmosphere)
- **Tool feel:** Diluted walnut/sepia ink and muted watercolor washes applied in 2–3 transparent layers over the line drawing.
- **Behavior:** Visible soft brush-wash transitions, gentle pigment pooling near dry edges, subtle watercolor bloom inside shaded planes, and light cold-press paper grain inside the painted object.
- **Restraint:** Washes must remain **strictly contained within the object's drawn contour**. Never let loose ink splatters, misty halos, or watercolor bleed float into the transparent background outside the silhouette.

### 3.3 Highlights & Surface Finish
- **Finish:** Strictly **matte** hand-painted pigment on rag paper.
- **Highlights:** Created by leaving warm bare parchment/cream paper (`#F9F3E4`–`#FDFBF1`) untouched or lightly lifted — **never** bright white plastic specular highlights, chrome reflections, bloom/glow effects, or 3D raytraced gloss.

---

## 4. Color Palette & Strict Color Budget

All hex values below are measured directly from the approved canonical reference (`manuscript-ink-wash.png`) and aligned with [`design/design.md`](./design.md).

### 4.1 Core Neutral Palette (85–95% of every graphic)

| Role | Hex Swatches | Usage |
|---|---|---|
| **Deepest Ink Crevices** | `#1A130A`, `#2B1D10` | Deepest interior curls, undersides, crispest pen accents |
| **Primary Dip-Pen Ink** | `#362A1D`, `#43382B`, `#443527` | Outer contour linework, parallel hatching, fine details |
| **Warm Umber / Graphite Shadow** | `#7A6D5C`, `#9D856D` | Core shadow washes, folds, aged patina, wood/leather mid-darks |
| **Midtone Sepia Wash** | `#BCAC95`, `#D6C8B1` | Secondary wash layers, weathered linen, parchment shading |
| **Parchment / Paper Body** | `#E6D4B8`, `#EEE0C7`, `#F6EAD5` | Primary sunlit body tone for light fabrics, paper, bone, ivory |
| **Warm Paper Highlight** | `#F9F3E4`, `#FBF8EC`, `#FDFBF1` | Lit top planes and delicate paper highlights (never pure `#FFFFFF` on outer edges) |

### 4.2 Signature Ember-Terracotta Accent (5–15% of every graphic)

Anchored to Călimara's UI accent `--accent: #b84a2a`:

| Role | Hex Swatches | Usage |
|---|---|---|
| **Ember Shadow** | `#592511`, `#83492F` | Deep rim/crevice shading of the focal accent |
| **Core Ember Terracotta** | `#A35735`, `#B36844`, `#B84A2A` | Primary focal accent fill (wax seal, ribbon, button, gem, flame) |
| **Ember Highlight** | `#BE734E`, `#CA8C6C` | Soft matte sunlit highlight on the focal accent |

### 4.3 Color Governance Rules (Non-Negotiable)
1. **The Single-Accent Rule:** Each isolated item may have **at most ONE** ember-terracotta focal accent area (typically 5–15% of total painted area) — e.g., a wax seal on a manuscript, a crimson-rust silk cravat on a coat, a terracotta bookmark tassel on a book, a ruby-ember clasp on a brooch, or a glowing candle ember in a lantern.
2. **Desaturated Secondary Mineral Exception (Use Sparingly):** If an object's material identity genuinely requires distinguishing metal, ink, or foliage (e.g., antique brass, oxidized verdigris, fountain-pen blue-black ink, dried laurel), you may introduce **at most ONE** heavily desaturated, sepia-harmonized mineral tint (saturation `< 25%`, e.g., tarnished brass `#9C8657`, slate-blue ink `#596670`, dried sage `#747B68`), occupying `< 10%` of the object, and still washed with sepia shadows.
3. **Never full-color rainbow palettes:** No bright blues, emerald greens, saturated purples, hot pinks, cyan magic glows, or gold-chrome gradients.
4. **No pure white outer borders:** Every outer edge of an object must be closed with warm ink (`#362A1D`–`#7A6D5C`) or toned wash (`#D6C8B1` or darker) so the item maintains crisp contrast against `calimara.ro`'s `#FFFFFF` page background and cleanly survives automated background extraction.

---

## 5. Lighting, Perspective & Composition

### 5.1 Unified Lighting Direction
- **Key light:** Soft, diffused studio/window daylight coming from **top-left (~45°)**.
- **Core shadow:** Falls gently toward **bottom-right**, built with layered warm umber washes (`#7A6D5C`, `#9D856D`) and fine curved pen hatching.
- **No external cast shadow:** Objects float cleanly with **zero ground shadow, zero drop shadow, and zero ambient occlusion puddle** outside their silhouette. All shading lives *on* the object itself.

### 5.2 Optical Framing & Silhouette
- **Single isolated subject** per file — no background scenery, no desk surface, no table edge, no decorative border/frame around the canvas (unless the item itself *is* a `frame` slot asset).
- **Scale & Safe Padding:** The object should fill **~80–84%** of the square canvas's longest axis, optically centered, leaving **8–10% transparent margin** on all four sides (`pad_ratio = 0.08`).
- **Diagonal energy (for handheld/tabletop artefacts):** Tilt elongated items (manuscripts, quills, pocket watches, pipes, letters, books) on a gentle **20–35° diagonal axis** matching the canonical manuscript — this maximizes perceived size inside a square thumbnail and feels natural rather than rigid.
- **Multi-size readability test:** Every item is displayed across three UI contexts on Călimara:
  - **58×58px** (`.cosmetic-preview` in `/magazin` and `/inventar`)
  - **32×32px** (inline profile chips & badges)
  - **240–768px** (showcase / admin preview / future inspect modal)
  Designs must rely on a **clear, unmistakable outer silhouette and 2–3 bold structural shapes**, never microscopic fine print that turns to noise below 64px.

### 5.3 Calligraphy & Inscriptions Inside Illustrations
- If an item naturally contains handwriting (manuscripts, letters, open books, diplomas), render it as **loose, delicate, suggestive antique cursive pen strokes** in faded sepia ink — **never** legible "Lorem ipsum", modern printed fonts, or accidental English filler words.
- If a specific Romanian word or monogram is intentionally requested (e.g., an initial `C` on a wax seal), specify it explicitly in quotes in the prompt and verify exact spelling before accepting the image.

---

## 6. Category-by-Category Guidelines (Călimara Shop Slots)

Călimara's economy schema (`app/schemas/economy.py`) defines five cosmetic slots (`profile_badge`, `costume`, `frame`, `background`, `title`), plus broader editorial/collectible artefacts:

### 6.1 Artefacts & Collectibles (Manuscripts, Inkwells, Quills, Books, Lamps, Pocket Watches, Spectacles)
- **Perspective:** Elevated **3/4 tabletop angle** (~30–40° tilt), slight diagonal composition.
- **Material translation:**
  - *Paper / parchment:* `#EEE0C7`–`#FBF8EC` washes with sepia edge ageing and delicate hatching inside curls.
  - *Leather / wood:* Richer walnut-sepia washes (`#7A6D5C`, `#9D856D`, `#443527`) with fine grain lines in dip-pen ink.
  - *Brass / iron / glass:* Sepia-tinted metallic shading with restrained paper-white rim flicks and ink contour lines (never glossy 3D chrome).
- **Accent placement:** Wax seal, bookmark ribbon, jewel/enamel inlay, glowing candle wick, or red-ochre ink drop (`#B84A2A`).

### 6.2 Clothing & Costumes (`costume` — Coats, Capes, Hats, Scarves, Gloves, Waistcoats, Traditional Romanian Pieces)
- **Presentation:** **Tailored empty-garment / invisible-mannequin front or slight 3/4 view** (like a 19th-century tailor's fashion plate or costume archive sketch). **Never** draw disembodied faces, heads, or floating hands unless explicitly creating a character portrait.
- **Silhouette:** Clear draped shoulders, collar, lapels, cuffs, or brim; bold, legible fold lines drawn with confident dip-pen hatching.
- **Theme fit:** 19th/early 20th-century Romanian & European literary dress — e.g., poet's frock coat (*redingotă*), velvet cape (*pelerină*), embroidered traditional *ie* with subtle sepia-and-ember geometric stitchwork, bowler/top hat (*joben*), wool scarf, fingerless writer's gloves, bohemian beret.
- **Accent placement:** A single ember-terracotta cravat, hatband, lapel flower, embroidered collar motif, or lining peek (`#B84A2A`).

### 6.3 Profile Badges & Emblems (`profile_badge` — Seals, Medallions, Laurel Crests, Literary Symbols)
- **Presentation:** **Front-facing, centered, balanced or symmetrical** emblem that reads crisply even at `32×32px`.
- **Detail density:** Lower micro-detail than large artefacts; stronger exterior dip-pen contour and high contrast between warm cream highlights and sepia ink shadows.
- **Accent placement:** Wax-seal body, small ribbon banner, or central heraldic motif in `#B84A2A`.

### 6.4 Avatar & Profile Frames (`frame`)
- **Presentation:** Front-facing symmetrical square or circular botanical/filigree ink-and-wash border with a **100% transparent interior cutout** (minimum 68% open inner aperture) and **100% transparent outer corners**.
- **Motifs:** Fine dip-pen botanical sprigs, antique bookplate corners, quill/laurel filigree, muted sepia wash shadows, tiny ember-terracotta corner berries/seals.

### 6.5 Atmospheric Backgrounds (`background`)
- **Presentation:** Follows both this guide and [`design/design.md`](./design.md) Section 7 (`bg-sky.png`, `bg-forest.png`).
- **Behavior:** Soft monochrome/sepia painterly ink wash that **fades smoothly to full transparency** toward content zones; low contrast (`opacity`-friendly) so black serif typography (`#111111`) always maintains AAA legibility over it.

### 6.6 Editorial Spot Illustrations (Articles, Empty States, Seasonal Headers)
- Same dip-pen & sepia wash medium, transparent background, 1:1 or 4:3 aspect ratio, restrained composition that breathes inside white editorial margins.

---

## 7. Technical Specifications & Transparency Pipeline

### 7.1 File Format & Dimensions

| Asset Type | Format | Target Resolution | Padding (`pad_ratio`) | Target File Size |
|---|---|---|---|---|
| Shop items (`costume`, `profile_badge`, artefacts) | 32-bit **RGBA PNG** | `768×768px` (1:1) | `8%` transparent margin (`~62px`) | `< 450 KB` |
| Avatar / profile frames (`frame`) | 32-bit **RGBA PNG** | `768×768px` or `1024×1024px` (1:1) | `4–6%` outer margin | `< 500 KB` |
| Atmospheric backgrounds (`background`) | 32-bit **RGBA PNG** | `1600×900px` (or `1200×600px`) | Edge-faded to alpha `0` | `< 700 KB` |
| Editorial spot illustrations | 32-bit **RGBA PNG** | `768×768px` or `1024×768px` | `8%` transparent margin | `< 500 KB` |

### 7.2 File Naming & Storage Convention
- Store built-in shop item assets under:
  `frontend/public/assets/items/<slot>/<slug>.png`
  (served at `/assets/items/<slot>/<slug>.png`, matching `ShopItem.slot` and `ShopItem.slug`).
- Lowercase ASCII kebab-case only (`a-z`, `0-9`, `-`), e.g.:
  - `frontend/public/assets/items/profile_badge/manuscris-victorian.png`
  - `frontend/public/assets/items/costume/redingota-poetului.png`
  - `frontend/public/assets/items/frame/rama-filigran-sepia.png`
- Never commit raw un-processed `.jpg` generation intermediates into `frontend/public/`.

### 7.3 Mandatory Background-Removal & Halo-Elimination Pipeline

**CRITICAL RULE:** Never ask an AI image generator to render a "transparent background" directly — image models frequently paint a fake grey-and-white checkerboard or leave opaque white halos.

Instead, **always follow this exact two-stage pipeline**:

1. **Generate** the illustration isolated on a **completely flat, uniform, pure solid white (`#FFFFFF`) background** with zero cast shadow, zero floor, zero frame, zero floating ink splatters, and closed sepia-ink outer contours.
2. **Post-process** the raw image using [`scripts/prepare_art_asset.py`](../scripts/prepare_art_asset.py):

```bash
/home/dan/calimara2/.venv/bin/python scripts/prepare_art_asset.py \
  path/to/raw-image.jpg \
  frontend/public/assets/items/<slot>/<slug>.png \
  --size 768 \
  --pad 0.08 \
  --verify /tmp/verify-<slug>.png
```

What `scripts/prepare_art_asset.py` guarantees:
- **Border-seeded flood-fill** from all four canvas edges (removes only exterior `#FFFFFF` background — interior light parchment highlights are never punctured).
- **4-ring smoothstep anti-aliased edge feathering** for silky smooth transitions.
- **White-matte color decontamination (un-premultiplication)** so edges show **zero white halo** even over dark charcoal (`#1A1A1D`).
- **Optical bounding-box crop & recentering** onto a uniform `768×768` RGBA canvas with consistent 8% transparent breathing room.
- **4-backdrop verification contact sheet** (`--verify`) rendering the PNG over checkerboard, pure white (`#FFFFFF`), warm paper (`#F3F2EE`), and dark charcoal (`#1A1A1D`) for visual inspection.
- **Automated compliance check** via `--check`:

```bash
/home/dan/calimara2/.venv/bin/python scripts/prepare_art_asset.py --check \
  frontend/public/assets/items/<slot>/<slug>.png
```

> **Note on enclosed background holes** (e.g., inside a handle loop, between arms/sleeves of a coat, or the center aperture of a `frame`): pass `--clear-holes` or inspect the verification sheet carefully — for items with intentional interior see-through gaps (like frames, teacup handles, or coat sleeves), verify those interior pure-white regions are also cleared to alpha `0`!

---

## 8. Master AI Image Generation Prompt Architecture

Every AI-generated graphic for Călimara **must** be built from the four locked blocks below. Change **only** `[SUBJECT]` (and adjust the perspective phrase for badges/clothing/frames). Keep the Style, Color Budget, and Isolation blocks intact.

### 8.1 Master Prompt Template

```text
Generate a single square (1:1) painterly illustration of [SUBJECT — clear description of one isolated Victorian / early 20th-century Romanian literary item, garment, or artefact, specifying the ONE small focal detail that carries the muted terracotta-ember accent].

Art Style (LOCKED — Tuș și laviu sepia):
Early 20th-century European literary journal illustration rendered in fine archival dip-pen ink linework and translucent sepia-and-charcoal watercolor washes. Crisp hand-drawn dark sepia ink contours (#362A1D) with delicate curved pen hatching in folds and shaded planes, layered with soft diluted sepia, warm umber (#7A6D5C, #9D856D), and aged parchment (#EEE0C7, #F6EAD5) ink washes with subtle organic wash transitions and matte cold-press rag paper texture inside the object. Soft diffused daylight from top-left (~45°), matte hand-painted finish (no glossy 3D speculars).

Color Budget (STRICT):
Near-monochrome warm sepia, aged ivory parchment, and charcoal-brown ink (85–95% of the item). The ONLY warm color accent is a single muted terracotta-ember (#B84A2A) focal detail (5–15% of the item). No bright or saturated colors, no rainbow palette, no neon glows.

Composition & Isolation (CRITICAL):
- Single isolated object only, [PERSPECTIVE: e.g., elevated 3/4 view tilted gently on a 25° diagonal / front-facing tailored garment on an invisible form / front-facing symmetrical emblem], centered neatly with generous empty margin on all four sides (object fills ~72% of the canvas).
- Placed on a completely flat, uniform, pure solid white (#FFFFFF) background.
- NO cast shadow on the background, NO table, NO floor, NO frame, NO border, NO vignette, NO floating ink splatters or wash smudges outside the object contour, NO checkerboard pattern, NO text labels, NO legible English or Lorem ipsum text, NO watermarks.
- Closed, cleanly defined outer silhouette in dark sepia ink contrasting clearly against the pure white background so it can be cleanly cut out to transparency.
```

### 8.2 Category Prompt Examples

#### Example A — Artefact (*Călimară de alamă și pană de gâscă*)
- **Subject:** `an antique 19th-century faceted glass and tarnished brass inkwell resting beside a curved goose-quill pen dipped in sepia ink, with a single small muted terracotta-ember (#B84A2A) wax drip and crimson-rust cord tied neatly around the neck of the inkwell`
- **Perspective:** `elevated 3/4 tabletop view arranged on a gentle diagonal`

#### Example B — Clothing (`costume`: *Redingotă de poet*)
- **Subject:** `a tailored late-19th-century Romanian poet's wool frock coat (redingotă) presented on an invisible mannequin form with crisp structured lapels, stitched seams, brass-toned buttons, and a single folded muted terracotta-ember (#B84A2A) silk cravat tucked at the collar; no head, no face, no hands`
- **Perspective:** `front-facing slight 3/4 tailor's fashion-plate view, upright and balanced`

#### Example C — Profile Badge (`profile_badge`: *Sigiliu cu lauri*)
- **Subject:** `a classic literary heraldic medallion featuring a fine dip-pen nib crossed with two delicate dried laurel twigs tied at the base, centered over a stamped circular muted terracotta-ember (#B84A2A) wax seal`
- **Perspective:** `front-facing symmetrical emblem centered cleanly for clear readability even as a small 58px icon`

#### Example D — Avatar Frame (`frame`: *Ramă filigran de carte*)
- **Subject:** `an ornate square Victorian bookplate portrait frame composed of fine dip-pen sepia ink filigree corners, slender intertwined laurel lines, subtle sepia wash shading, and tiny muted terracotta-ember (#B84A2A) wax-dot accents at the four corners, surrounding a completely empty pure white (#FFFFFF) inner square opening`
- **Perspective:** `flat front-facing symmetrical square border`

---

## 9. Anti-Patterns (Strict Prohibitions)

Reject and regenerate any asset that exhibits **any** of the following:

- **Wrong medium:** 3D CGI renders, Blender clay/plastic shaders, glossy mobile-RPG icons, flat SaaS vector art, pixel art, heavy thick-outlined comic/anime stickers, heavy impasto oil painting, or brightly saturated botanical watercolor.
- **Broken palette:** Multiple saturated hues, bright neon/cyan/purple/green accents, pure `#000000` harsh digital outlines, or absence of the sepia-parchment ink harmony.
- **Dirty isolation:** Cast shadows on the background, grey/beige paper background instead of true alpha `0`, fake Photoshop checkerboard patterns, floating ink droplets/splatters detached from the silhouette, or white halo fringes visible on `#1A1A1D` dark backdrop.
- **Illegible or broken details:** Readable "Lorem ipsum" or garbled English words inside manuscripts/books, tiny unreadable clutter that turns to mud at `58×58px`, cropped edges touching the canvas border, or AI signatures/watermarks.
- **Wrong clothing framing:** Disembodied mannequin heads, human faces/skin, or awkward cut-off torsos on `costume` items.

---

## 10. Pre-Commit Quality Assurance Checklist

Before committing any new graphic to `frontend/public/assets/` or registering it in the shop (`shop_items.asset_url`), confirm every box:

- [ ] **Style match:** Placed side-by-side with `design/assets/style-reference-ink-wash.png`, it looks drawn by the same artist (dip-pen sepia ink + translucent sepia wash + matte finish).
- [ ] **Color budget:** 85–95% sepia/parchment/charcoal neutral tones; at most ONE muted ember-terracotta (`#B84A2A`) accent focal point.
- [ ] **Lighting & framing:** Soft top-left light, centered with ~8% transparent padding on all sides, no cropped edges, no cast shadow on background.
- [ ] **No text artifacts:** Zero "Lorem ipsum", zero garbled English text, zero watermarks or signatures.
- [ ] **True transparency verified:** Processed through `scripts/prepare_art_asset.py` and visually inspected on the 4-backdrop verification sheet (checkerboard, `#FFFFFF`, `#F3F2EE`, `#1A1A1D`) with **zero white halos** and **zero unintended interior holes**.
- [ ] **Automated check passes:** `scripts/prepare_art_asset.py --check <file.png>` exits `0`.
- [ ] **Thumbnail check:** Remains clearly recognizable when downscaled to `58×58px` (`.cosmetic-preview`).
