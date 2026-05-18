import { api, buildQuery } from "./client.js";

export function fetchStafetaWorks(params = {}) {
  return api.get(`/api/stafeta${buildQuery(params)}`);
}

export function fetchStafetaWork(slug) {
  return api.get(`/api/stafeta/${encodeURIComponent(slug)}`);
}

export function createStafetaWork(data) {
  return api.post("/api/stafeta", data);
}

export function updateStafetaParticipation(participates, desiredSlots) {
  const payload = { participates };
  if (desiredSlots !== undefined) payload.desired_slots = desiredSlots;
  return api.put("/api/stafeta/participare", payload);
}

export function respondStafetaAssignment(workId, assignmentId, data) {
  return api.post(`/api/stafeta/${encodeURIComponent(workId)}/invitatie/${encodeURIComponent(assignmentId)}/raspunde`, data);
}

export function sendStafetaForward(workId, data) {
  return api.post(`/api/stafeta/${encodeURIComponent(workId)}/trimite`, data);
}

export function assignStafetaSpecific(workId, data) {
  return api.post(`/api/stafeta/${encodeURIComponent(workId)}/atribuie`, data);
}

export function assignStafetaRandom(workId) {
  return api.post(`/api/stafeta/${encodeURIComponent(workId)}/aleatoriu`, {});
}

export function publishStafeta(workId) {
  return api.post(`/api/stafeta/${encodeURIComponent(workId)}/publica`, {});
}

export function cancelStafeta(workId) {
  return api.delete(`/api/stafeta/${encodeURIComponent(workId)}`);
}
