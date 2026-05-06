import { api } from "./client.js";

export function fetchLanding(category) {
  return api.get(`/api/prima-pagina?category=${encodeURIComponent(category)}`);
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

