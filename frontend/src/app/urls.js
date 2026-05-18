export function safeExternalUrl(url) {
  const value = String(url || "").trim();
  if (!value) return "";
  const candidate = /^[a-z][a-z0-9+.-]*:/i.test(value)
    ? value
    : value.startsWith("//")
      ? `https:${value}`
      : `https://${value}`;
  try {
    const parsed = new URL(candidate);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : "";
  } catch {
    return "";
  }
}
