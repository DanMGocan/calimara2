// Build-time compensation for the desktop page scale (`html { zoom: var(--page-zoom) }`,
// switched on by installPageZoom() in src/app/zoom.js). Real browser zoom changes the CSS
// viewport; CSS zoom does not, so two things need fixing up:
//
// 1. Viewport units. Under CSS zoom they shrink with the page (100vh renders as 90% of the
//    window at zoom 0.9). Every viewport-unit length is divided by --page-zoom so full-height
//    layouts, modals and vw-based type keep filling the window.
// 2. Media queries. They keep testing the window, but the zoomed page holds 1/0.9 as many CSS
//    px. Each affected @media gets a zoom-aware twin: the original applies only without the
//    scale, the twin (thresholds x PAGE_ZOOM) only with it, so breakpoints track the page's
//    real width the way they do under Ctrl+-. Selectors are scoped with :where(), which adds
//    no specificity, so the cascade is unchanged.

import { DESKTOP_SCALE_QUERY, PAGE_ZOOM, PAGE_ZOOM_ACTIVE_CLASS } from "./src/app/zoom.js";

const VIEWPORT_UNIT = String.raw`[sdl]?v(?:h|w|min|max|i|b)`;
const VIEWPORT_LENGTH_RE = new RegExp(String.raw`(^|[^\w.-])(-?(?:\d+\.?\d*|\.\d+)(?:${VIEWPORT_UNIT}))(?![\w-])`, "gi");
// A value that mentions --page-zoom is compensated by hand and left alone entirely, e.g.
// `calc((100vh - 64px) / var(--page-zoom, 1))`.
const MANUAL_ZOOM_RE = /var\(\s*--page-zoom(?![\w-])/i;
const HAS_VIEWPORT_UNIT_RE = new RegExp(String.raw`\d(?:${VIEWPORT_UNIT})(?![\w-])`, "i");

// Splits a declaration value into parts that may be rewritten and parts that must be copied
// verbatim: quoted strings and url(...) arguments.
function splitProtected(value) {
  const parts = [];
  let plain = "";
  let i = 0;
  const pushProtected = (end) => {
    if (plain) parts.push({ text: plain, rewrite: true });
    plain = "";
    parts.push({ text: value.slice(i, end), rewrite: false });
    i = end;
  };
  while (i < value.length) {
    const ch = value[i];
    if (ch === '"' || ch === "'") {
      let j = i + 1;
      while (j < value.length && value[j] !== ch) j += value[j] === "\\" ? 2 : 1;
      pushProtected(Math.min(j + 1, value.length));
    } else if (/^url\(/i.test(value.slice(i, i + 4)) && !/[\w-]/.test(value[i - 1] || "")) {
      let j = i + 4;
      while (j < value.length && value[j] !== ")") {
        if (value[j] === '"' || value[j] === "'") {
          const quote = value[j];
          j += 1;
          while (j < value.length && value[j] !== quote) j += value[j] === "\\" ? 2 : 1;
        }
        j += 1;
      }
      pushProtected(Math.min(j + 1, value.length));
    } else {
      plain += ch;
      i += 1;
    }
  }
  if (plain) parts.push({ text: plain, rewrite: true });
  return parts;
}

export function divideViewportUnits(value) {
  if (MANUAL_ZOOM_RE.test(value)) return value;
  return splitProtected(value)
    .map(({ text, rewrite }) =>
      rewrite ? text.replace(VIEWPORT_LENGTH_RE, (_, lead, length) => `${lead}calc(${length} / var(--page-zoom, 1))`) : text
    )
    .join("");
}

// --- media queries -------------------------------------------------------------------

const MEDIA_SIZE_RE = /\(\s*(min|max)-(width|height)\s*:\s*(\d+(?:\.\d+)?)px\s*\)/gi;
// The scale is only on when the window is at least this wide, so width thresholds below it
// test the same either way. Height thresholds are always affected.
const SCALE_MIN_WIDTH = Number(/min-width:\s*(\d+)px/.exec(DESKTOP_SCALE_QUERY)[1]);

// Any other size test (range syntax like `(width <= 1200px)`, em/rem thresholds) would
// silently drift under the scale, so the build refuses it instead.
const SIZE_FEATURE_RE = /(?<![\w-])(?:min-|max-)?(?:width|height)(?![\w-])/i;

export function assertSupportedMediaParams(params) {
  if (SIZE_FEATURE_RE.test(params.replace(MEDIA_SIZE_RE, ""))) {
    throw new Error(
      `postcss-viewport-zoom: unsupported size media query "@media ${params}". ` +
        "Use (min-|max-)(width|height): <N>px so the desktop page scale can compensate it."
    );
  }
}

export function mediaNeedsZoomTwin(params) {
  assertSupportedMediaParams(params);
  for (const [, , axis, px] of params.matchAll(MEDIA_SIZE_RE)) {
    if (axis.toLowerCase() === "height" || Number(px) >= SCALE_MIN_WIDTH) return true;
  }
  return false;
}

export function scaleMediaParams(params, zoom = PAGE_ZOOM) {
  return params.replace(MEDIA_SIZE_RE, (_, bound, axis, px) => {
    const scaled = Math.round(Number(px) * zoom * 100) / 100;
    return `(${bound}-${axis}: ${scaled}px)`;
  });
}

// Selectors that do not start with html/:root get a descendant prefix, so inside a twinned
// @media they can no longer match <html> itself (e.g. a bare `*`). Start such selectors with
// `html` or `:root` explicitly if they need to.
export function scopeSelector(selector, active) {
  const state = active ? `.${PAGE_ZOOM_ACTIVE_CLASS}` : `:not(.${PAGE_ZOOM_ACTIVE_CLASS})`;
  const trimmed = selector.trim();
  const root = /^(:root|html)(?![\w-])/i.exec(trimmed);
  if (root) return `${root[1]}:where(${state})${trimmed.slice(root[1].length)}`;
  return `:where(html${state}) ${trimmed}`;
}

function insideKeyframes(node) {
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (parent.type === "atrule" && /keyframes$/i.test(parent.name)) return true;
  }
  return false;
}

function isAncestor(ancestor, node) {
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (parent === ancestor) return true;
  }
  return false;
}

function scopeRules(atRule, active) {
  atRule.walkRules((rule) => {
    if (insideKeyframes(rule)) return;
    rule.selectors = rule.selectors.map((selector) => scopeSelector(selector, active));
  });
}

export default function viewportZoom() {
  return {
    postcssPlugin: "calimara-viewport-zoom",
    Once(root) {
      const twins = [];
      root.walkAtRules(/^media$/i, (atRule) => {
        // A nested @media is handled with (and scoped by) its outermost affected ancestor.
        if (twins.some((outer) => isAncestor(outer, atRule))) return;
        if (mediaNeedsZoomTwin(atRule.params)) twins.push(atRule);
      });
      for (const atRule of twins) {
        const twin = atRule.clone({ params: scaleMediaParams(atRule.params) });
        twin.walkAtRules(/^media$/i, (nested) => {
          nested.params = scaleMediaParams(nested.params);
        });
        scopeRules(atRule, false);
        scopeRules(twin, true);
        atRule.after(twin);
      }
      root.walkDecls((decl) => {
        if (HAS_VIEWPORT_UNIT_RE.test(decl.value)) decl.value = divideViewportUnits(decl.value);
      });
    }
  };
}
viewportZoom.postcss = true;
