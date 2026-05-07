import { CATEGORY_LABELS, CONTENT_TYPE_LABELS, FORUM_SECTIONS, MODERATION_LABELS, SHOP_SLOT_LABELS } from "./constants.js";

export function htmlToText(html) {
  if (!html) return "";
  const normalized = String(html)
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|blockquote|li|h[1-6])>/gi, "\n");
  if (typeof DOMParser !== "undefined") {
    const doc = new DOMParser().parseFromString(normalized, "text/html");
    return (doc.body.textContent || "").replace(/\u00a0/g, " ").replace(/\n{3,}/g, "\n\n").trim();
  }
  return normalized.replace(/<[^>]*>/g, "").replace(/\u00a0/g, " ").trim();
}
export function draftFingerprint(title, content) {
  return `${(title || "").trim()}\n${content || ""}`;
}
export function draftHasContent(title, content) {
  return Boolean((title || "").trim() || htmlToText(content));
}
export function hasHtml(value) {
  return /<[a-zA-Z][^>]*>/.test(value || "");
}
export function usernameHandle(username) {
  const value = String(username ?? "").trim();
  if (!value) return "";
  return value.startsWith("@") ? value : `@${value}`;
}
export function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ro-RO", {
    day: "2-digit",
    month: "short",
    year: "numeric"
  }).format(date);
}
export function categoryLabel(category) {
  return CATEGORY_LABELS[category] ?? category ?? "Text";
}
export function moderationLabel(status) {
  if (!status || status === "approved") return "";
  return MODERATION_LABELS[status] ?? status;
}
export function contentTypeLabel(type) {
  return CONTENT_TYPE_LABELS[type] ?? type ?? "Conținut";
}
export function decisionLabel(value) {
  if (!value) return "n/a";
  if (value === "approved") return "aprobat";
  if (value === "flagged") return "marcat";
  if (value === "rejected") return "respins";
  if (value === "pending") return "în așteptare";
  if (value === "open") return "deschis";
  if (value === "resolved") return "rezolvat";
  if (value === "dismissed") return "închis";
  return value;
}
export function formatScore(value) {
  if (value === null || value === undefined || value === "") return "0%";
  const score = Number(value);
  if (Number.isNaN(score)) return String(value);
  return `${Math.round(score * 100)}%`;
}
export function forumSectionLabel(section) {
  return FORUM_SECTIONS.find((item) => item.key === section)?.label ?? section ?? "Discuții";
}
export function slotLabel(slot) {
  return SHOP_SLOT_LABELS[slot] ?? slot ?? "Cosmetic";
}
export function formatGologani(value) {
  return `${Number(value ?? 0).toLocaleString("ro-RO")} Gologani`;
}
export function formatNumber(value) {
  return Number(value ?? 0).toLocaleString("ro-RO");
}
export function audioStatusLabel(status) {
  if (status === "ready") return "audio disponibil";
  if (status === "pending") return "în coada de generare";
  if (status === "processing") return "se generează";
  if (status === "failed") return "generare eșuată";
  if (status === "rejected") return "audio respins";
  if (status === "flagged") return "în revizuire";
  if (status === "cancelled") return "generare oprită";
  return "fără audio";
}
export function formatAudioTime(value) {
  if (!Number.isFinite(value) || value < 0) return "0:00";
  const totalSeconds = Math.floor(value);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}
