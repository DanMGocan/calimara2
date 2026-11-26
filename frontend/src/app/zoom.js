// Effective CSS zoom of an element (the desktop page scale from `--page-zoom` in index.css).
// getBoundingClientRect(), event coordinates and window.innerWidth are in window pixels,
// while px written to an element's style are multiplied by its zoom. Divide window-pixel
// values by this before writing them to style.
export function cssZoomOf(element) {
  const zoom = element?.currentCSSZoom;
  return typeof zoom === "number" && zoom > 0 ? zoom : 1;
}
