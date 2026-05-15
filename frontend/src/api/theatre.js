import { api } from "./client.js";

export function fetchTheatrePlays() {
  return api.get("/api/teatru?limit=50");
}

export function fetchTheatrePlay(slug) {
  return api.get(`/api/teatru/${encodeURIComponent(slug)}`);
}

export function createTheatrePlay(data) {
  return api.post("/api/teatru", data);
}

export function updateTheatrePlay(playId, data) {
  return api.put(`/api/teatru/${encodeURIComponent(playId)}`, data);
}

export function deleteTheatrePlay(playId) {
  return api.delete(`/api/teatru/${encodeURIComponent(playId)}`);
}

export function applyToTheatrePlay(playId, data) {
  return api.post(`/api/teatru/${encodeURIComponent(playId)}/cereri`, data);
}

export function inviteToTheatrePlay(playId, data) {
  return api.post(`/api/teatru/${encodeURIComponent(playId)}/invita`, data);
}

export function fetchTheatreRequests(playId) {
  return api.get(`/api/teatru/${encodeURIComponent(playId)}/cereri`);
}

export function respondTheatreRequest(playId, requestId, data) {
  return api.post(`/api/teatru/${encodeURIComponent(playId)}/cereri/${encodeURIComponent(requestId)}/raspunde`, data);
}

export function createTheatreCharacter(playId, data) {
  return api.post(`/api/teatru/${encodeURIComponent(playId)}/personaje`, data);
}

export function deleteTheatreCharacter(playId, characterId) {
  return api.delete(`/api/teatru/${encodeURIComponent(playId)}/personaje/${encodeURIComponent(characterId)}`);
}

export function reviewTheatreCharacter(playId, characterId, data) {
  return api.post(`/api/teatru/${encodeURIComponent(playId)}/personaje/${encodeURIComponent(characterId)}/raspunde`, data);
}

export function assignTheatreCharacter(playId, characterId, data) {
  return api.post(`/api/teatru/${encodeURIComponent(playId)}/personaje/${encodeURIComponent(characterId)}/atribuie`, data);
}

export function startTheatreScene(playId, data) {
  return api.post(`/api/teatru/${encodeURIComponent(playId)}/scene`, data);
}

export function createTheatreReply(playId, sceneId, data) {
  return api.post(`/api/teatru/${encodeURIComponent(playId)}/scene/${encodeURIComponent(sceneId)}/replici`, data);
}

export function createTheatreStageDirection(playId, sceneId, data) {
  return api.post(`/api/teatru/${encodeURIComponent(playId)}/scene/${encodeURIComponent(sceneId)}/indicatii`, data);
}

export function overrideTheatreTurn(playId, data) {
  return api.post(`/api/teatru/${encodeURIComponent(playId)}/rand`, data);
}

export function endTheatreScene(playId, sceneId, data = {}) {
  return api.post(`/api/teatru/${encodeURIComponent(playId)}/scene/${encodeURIComponent(sceneId)}/incheie`, data);
}

export function fetchMyTheatrePlays() {
  return api.get("/api/utilizator/teatru");
}

export function fetchMyTheatreInvitations() {
  return api.get("/api/utilizator/teatru/in-asteptare");
}

export function theatrePdfUrl(slug) {
  return `/api/teatru/${encodeURIComponent(slug)}/pdf`;
}
