import { api } from "./client.js";

export function fetchClubs() {
  return api.get("/api/cluburi?limit=50");
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

