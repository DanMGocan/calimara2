// Desktop page scale. The layout is sized for ~90% browser zoom on a 1920px screen, so on
// desktop pointers the whole page gets `html { zoom: var(--page-zoom) }` (see index.css).
//
// installPageZoom() decides when the scale is on and sets `--page-zoom` plus the
// `page-zoom-active` class on <html>. It only turns the scale on in browsers that expose
// `Element.currentCSSZoom` (Chrome 128+, Firefox 126+, recent Safari): older browsers either
// ignore CSS zoom or give JS no way to read it back, so they keep the unscaled layout.
//
// The same constants drive the build-time compensation in frontend/postcss-viewport-zoom.js
// (viewport units, and width media queries that the zoom would otherwise shift).
// Keep this module free of top-level DOM access: the Vite config imports it under Node.

export const PAGE_ZOOM = 0.9;
export const DESKTOP_SCALE_QUERY = "screen and (min-width: 1181px) and (hover: hover) and (pointer: fine)";
export const PAGE_ZOOM_ACTIVE_CLASS = "page-zoom-active";
export const PAGE_ZOOM_CHANGE_EVENT = "calimara:page-zoom-change";

// Effective CSS zoom of an element. getBoundingClientRect(), event coordinates and
// window.innerWidth are in window pixels, while px written to an element's style are
// multiplied by its zoom. Divide window-pixel values by this before writing them to style.
export function cssZoomOf(element) {
  const zoom = element?.currentCSSZoom;
  return typeof zoom === "number" && zoom > 0 ? zoom : 1;
}

export function supportsPageZoom(win) {
  return typeof win?.Element === "function" && "currentCSSZoom" in win.Element.prototype;
}

// Turns the desktop scale on/off as the desktop query starts or stops matching (window resize,
// mouse attached/detached). Dispatches PAGE_ZOOM_CHANGE_EVENT on window after every change so
// code that caches window-pixel geometry can re-measure. Returns a cleanup function.
export function installPageZoom(win = typeof window === "undefined" ? undefined : window) {
  if (!supportsPageZoom(win) || typeof win.matchMedia !== "function") return () => {};
  const root = win.document.documentElement;
  const query = win.matchMedia(DESKTOP_SCALE_QUERY);
  let active = null;
  const apply = () => {
    const next = Boolean(query.matches);
    if (next === active) return;
    active = next;
    root.classList.toggle(PAGE_ZOOM_ACTIVE_CLASS, next);
    if (next) root.style.setProperty("--page-zoom", String(PAGE_ZOOM));
    else root.style.removeProperty("--page-zoom");
    win.dispatchEvent(new win.Event(PAGE_ZOOM_CHANGE_EVENT));
  };
  apply();
  query.addEventListener("change", apply);
  return () => query.removeEventListener("change", apply);
}
