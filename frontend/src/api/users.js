import { api } from "./client.js";

export function fetchMe() {
  return api.get("/api/utilizator/eu");
}

export function updateMe(data) {
  return api.put("/api/utilizator/eu", data);
}

export function updateProfileSettings(data) {
  return api.put("/api/utilizator/profil", data);
}

export function fetchEmailPreferences() {
  return api.get("/api/utilizator/email-preferinte");
}

export function updateEmailPreferences(data) {
  return api.put("/api/utilizator/email-preferinte", data);
}

export function updateSocialLinks(data) {
  return api.put("/api/utilizator/linkuri-sociale", data);
}

export function uploadProfileMedia(kind, file) {
  const form = new FormData();
  form.append("file", file);
  return api.post(`/api/utilizator/media/${encodeURIComponent(kind)}`, form);
}

export function deleteProfileMedia(kind) {
  return api.delete(`/api/utilizator/media/${encodeURIComponent(kind)}`);
}

export function updateBestFriends(friends) {
  return api.put("/api/utilizator/prieteni-apropiati", { friends });
}

export function searchUsers(query) {
  return api.get(`/api/utilizatori/cauta?q=${encodeURIComponent(query)}`);
}

export function fetchUsersDirectory(params = {}) {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.relationship) search.set("relationship", params.relationship);
  if (params.sort) search.set("sort", params.sort);
  if (params.offset != null) search.set("offset", String(params.offset));
  if (params.limit != null) search.set("limit", String(params.limit));
  const query = search.toString();
  return api.get(`/api/utilizatori${query ? `?${query}` : ""}`);
}

export function fetchPublicProfile(username) {
  return api.get(`/api/utilizator/${encodeURIComponent(username)}/profil`);
}

export function updateFeaturedPosts(postIds) {
  return api.put("/api/utilizator/postari-recomandate", { post_ids: postIds });
}

export function fetchPromotions() {
  return api.get("/api/utilizator/promovari");
}

export function updatePromotions(data) {
  return api.put("/api/utilizator/promovari", data);
}

export function searchPromotions(query) {
  return api.get(`/api/utilizator/promovari/cauta?q=${encodeURIComponent(query)}`);
}

export function promotePost(postId) {
  return api.post(`/api/utilizator/promovari/postari/${encodeURIComponent(postId)}`, {});
}

export function unpromotePost(postId) {
  return api.delete(`/api/utilizator/promovari/postari/${encodeURIComponent(postId)}`);
}

export function promoteAuthor(authorId) {
  return api.post(`/api/utilizator/promovari/autori/${encodeURIComponent(authorId)}`, {});
}

export function unpromoteAuthor(authorId) {
  return api.delete(`/api/utilizator/promovari/autori/${encodeURIComponent(authorId)}`);
}

export function fetchRandomUser() {
  return api.get("/api/utilizatori/aleatoriu");
}
