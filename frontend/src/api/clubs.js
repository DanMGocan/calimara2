import { api, buildQuery } from "./client.js";

export function fetchClubs(params = {}) {
  return api.get(`/api/cluburi${buildQuery({ limit: 50, ...params })}`);
}

export function fetchRandomClub() {
  return api.get("/api/cluburi/aleatoriu");
}

export function fetchClub(slug) {
  return api.get(`/api/cluburi/${encodeURIComponent(slug)}`);
}

export function createClub(data) {
  return api.post("/api/cluburi/", data);
}

export function updateClub(clubId, data) {
  return api.put(`/api/cluburi/${encodeURIComponent(clubId)}`, data);
}

export function deleteClub(clubId) {
  return api.delete(`/api/cluburi/${encodeURIComponent(clubId)}`);
}

export function applyToClub(clubId, data = {}) {
  return api.post(`/api/cluburi/${encodeURIComponent(clubId)}/inscriere`, data);
}

export function inviteToClub(clubId, data) {
  return api.post(`/api/cluburi/${encodeURIComponent(clubId)}/invita`, data);
}

export function fetchClubRequests(clubId) {
  return api.get(`/api/cluburi/${encodeURIComponent(clubId)}/cereri`);
}

export function respondClubRequest(clubId, requestId, data) {
  return api.post(`/api/cluburi/${encodeURIComponent(clubId)}/cereri/${encodeURIComponent(requestId)}/raspunde`, data);
}

export function removeClubMember(clubId, userId) {
  return api.delete(`/api/cluburi/${encodeURIComponent(clubId)}/membri/${encodeURIComponent(userId)}`);
}

export function updateClubMemberRole(clubId, userId, data) {
  return api.put(`/api/cluburi/${encodeURIComponent(clubId)}/membri/${encodeURIComponent(userId)}/rol`, data);
}

export function fetchMyClubs() {
  return api.get("/api/utilizator/cluburi");
}

export function fetchMyClubInvitations() {
  return api.get("/api/utilizator/cluburi/in-asteptare");
}

export function fetchClubBoard(clubId) {
  return api.get(`/api/cluburi/${encodeURIComponent(clubId)}/tabla`);
}

export function createClubBoardMessage(clubId, data) {
  return api.post(`/api/cluburi/${encodeURIComponent(clubId)}/tabla`, data);
}

export function deleteClubBoardMessage(clubId, messageId) {
  return api.delete(`/api/cluburi/${encodeURIComponent(clubId)}/tabla/${encodeURIComponent(messageId)}`);
}

export function setClubFeatured(clubId, data) {
  return api.post(`/api/cluburi/${encodeURIComponent(clubId)}/creatia-saptamanii`, data);
}

export function clearClubFeatured(clubId) {
  return api.delete(`/api/cluburi/${encodeURIComponent(clubId)}/creatia-saptamanii`);
}

export function uploadClubMedia(clubId, kind, file) {
  const form = new FormData();
  form.append("file", file);
  return api.post(`/api/cluburi/${encodeURIComponent(clubId)}/media/${encodeURIComponent(kind)}`, form);
}

export function deleteClubMedia(clubId, kind) {
  return api.delete(`/api/cluburi/${encodeURIComponent(clubId)}/media/${encodeURIComponent(kind)}`);
}
