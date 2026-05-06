import { api } from "./client.js";

export function createSeries(data) {
  return api.post("/api/serii/", data);
}

export function fetchRandomSeries() {
  return api.get("/api/serii/aleatoriu");
}

export function fetchSeries(slug) {
  return api.get(`/api/serii/${encodeURIComponent(slug)}`);
}

export function seriesPdfUrl(slug) {
  return `/api/serii/${encodeURIComponent(slug)}/pdf`;
}

export function fetchUserSeries(username) {
  return api.get(`/api/utilizatori/${encodeURIComponent(username)}/serii`);
}

export function updateSeries(seriesId, data) {
  return api.put(`/api/serii/${encodeURIComponent(seriesId)}`, data);
}

export function deleteSeries(seriesId) {
  return api.delete(`/api/serii/${encodeURIComponent(seriesId)}`);
}

export function addPostToSeries(seriesId, data) {
  return api.post(`/api/serii/${encodeURIComponent(seriesId)}/postari`, data);
}

export function reorderSeriesPosts(seriesId, postIds) {
  return api.put(`/api/serii/${encodeURIComponent(seriesId)}/postari/ordine`, { post_ids: postIds });
}

export function removePostFromSeries(seriesId, postId) {
  return api.delete(`/api/serii/${encodeURIComponent(seriesId)}/postari/${encodeURIComponent(postId)}`);
}

export function fetchMySeries() {
  return api.get("/api/utilizator/serii");
}

export function fetchManagedSeries(seriesId) {
  return api.get(`/api/utilizator/serii/${encodeURIComponent(seriesId)}/gestioneaza`);
}

export function fetchPostSeries(postId) {
  return api.get(`/api/postari/${encodeURIComponent(postId)}/serie`);
}

