// The site is scaled down on desktop with `html { zoom: var(--page-zoom) }` (see the
// "Desktop scale" block in src/index.css). Under CSS zoom, viewport units shrink with the
// page (100vh renders as 90% of the window at zoom 0.9), unlike browser zoom where they
// keep meaning "the whole window". This plugin divides every viewport-unit length by
// --page-zoom so full-height layouts, modals and vw-based type keep filling the window.

const VIEWPORT_LENGTH_RE = /(^|[^\w.-])(-?(?:\d+\.?\d*|\.\d+)(?:[sdl]?v(?:h|w|min|max|i|b)))(?![\w-])/g;

export function divideViewportUnits(value) {
  if (value.includes("var(--page-zoom")) return value;
  return value.replace(VIEWPORT_LENGTH_RE, (_, lead, length) => `${lead}calc(${length} / var(--page-zoom, 1))`);
}

export default function viewportZoom() {
  return {
    postcssPlugin: "calimara-viewport-zoom",
    Once(root) {
      root.walkDecls((decl) => {
        if (/v(?:h|w|min|max|i|b)/.test(decl.value)) decl.value = divideViewportUnits(decl.value);
      });
    }
  };
}
viewportZoom.postcss = true;
