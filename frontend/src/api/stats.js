import { api } from "./client.js";

export function fetchPostStats(postId) {
  return api.get(`/api/statistici/postare/${encodeURIComponent(postId)}`);
}

export function fetchAuthorStats(username) {
  return api.get(`/api/statistici/autor/${encodeURIComponent(username)}`);
}

export function fetchCategoryStats(categoryKey) {
  return api.get(`/api/statistici/categorie/${encodeURIComponent(categoryKey)}`);
}

export function fetchOverviewStats() {
  return api.get("/api/statistici/ansamblu");
}

export function fetchMyStats() {
  return api.get("/api/statistici/ale-mele");
}

