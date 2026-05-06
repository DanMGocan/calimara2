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

export function fetchPublicProfile(username) {
  return api.get(`/api/utilizator/${encodeURIComponent(username)}/profil`);
}

export function updateFeaturedPosts(postIds) {
  return api.put("/api/utilizator/postari-recomandate", { post_ids: postIds });
}

export function fetchRandomUser() {
  return api.get("/api/utilizatori/aleatoriu");
}

