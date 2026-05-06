export function isIPv4(hostname) {
  return /^\d{1,3}(\.\d{1,3}){3}$/.test(hostname);
}
export function rootHost() {
  const host = window.location.hostname;
  if (host.endsWith(".localhost")) return "localhost";
  if (host === "localhost" || isIPv4(host)) return host;
  const parts = host.replace(/^www\./, "").split(".");
  return parts.length > 2 ? parts.slice(-2).join(".") : parts.join(".");
}
export function subdomainUsername() {
  const host = window.location.hostname;
  if (host.endsWith(".localhost") && host !== "localhost") {
    return host.slice(0, -".localhost".length);
  }
  if (host === "localhost" || isIPv4(host) || host.startsWith("www.")) return null;
  const parts = host.split(".");
  return parts.length > 2 ? parts[0] : null;
}
export function mainUrl() {
  const subdomain = subdomainUsername();
  if (!subdomain) return "";
  const port = window.location.port ? `:${window.location.port}` : "";
  return `${window.location.protocol}//${rootHost()}${port}`;
}
export function mainPath(path) {
  return `${mainUrl()}${path}`;
}
export function blogUrl(username) {
  const port = window.location.port ? `:${window.location.port}` : "";
  return `${window.location.protocol}//${username}.${rootHost()}${port}`;
}
export function canUseAuthorSubdomains() {
  const host = rootHost();
  return host !== "localhost" && !isIPv4(host);
}
export function authorPath(user, path) {
  if (!user?.username || !canUseAuthorSubdomains()) return mainPath(path);
  return `${blogUrl(user.username)}${path}`;
}
export function avatarPreviewUrl(seed, size = 96) {
  const backgroundColor = "f1f4f8,d1fae5,dbeafe,fce7f3,f3e8ff";
  return `https://api.dicebear.com/7.x/shapes/svg?seed=${encodeURIComponent(seed)}&backgroundColor=${backgroundColor}&size=${size}`;
}
export function coverPreviewUrl(seed, size = 1600) {
  const backgroundColor = "f1f4f8,dbeafe,d1fae5,fce7f3,f3e8ff,fff7ed";
  const params = new URLSearchParams({
    seed,
    backgroundColor,
    backgroundType: "gradientLinear",
    size: String(size)
  });
  return `https://api.dicebear.com/7.x/shapes/svg?${params.toString()}`;
}
export function profileAvatarUrl(user, size = 160) {
  if (user?.profile_photo_url) return user.profile_photo_url;
  if (user?.avatar_url) return user.avatar_url;
  return avatarPreviewUrl(user?.avatar_seed || `${user?.username || "calimara"}-shapes`, size);
}
export function profileCoverUrl(user, size = 1600) {
  if (user?.cover_url) return user.cover_url;
  return coverPreviewUrl(user?.cover_seed || `${user?.username || "calimara"}-cover-sky`, size);
}
