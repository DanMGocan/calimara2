import { api } from "./client.js";

export function fetchLanding(category, postId = null) {
  const params = new URLSearchParams({ category });
  if (postId) params.set("post_id", String(postId));
  return api.get(`/api/prima-pagina?${params.toString()}`);
}

export function fetchCategory(categoryKey, sortBy = "newest") {
  return api.get(`/api/categorii/${encodeURIComponent(categoryKey)}?sort_by=${encodeURIComponent(sortBy)}`);
}

export function fetchBlog(username) {
  return api.get(`/api/bloguri/${encodeURIComponent(username)}`);
}

export function fetchAllWorks(username) {
  return api.get(`/api/bloguri/${encodeURIComponent(username)}/toate-operele`);
}

export function fetchPostDetail(username, slug) {
  return api.get(`/api/bloguri/${encodeURIComponent(username)}/postari/${encodeURIComponent(slug)}`);
}

export function postPdfUrl(username, slug) {
  return `/api/bloguri/${encodeURIComponent(username)}/postari/${encodeURIComponent(slug)}/pdf`;
}
