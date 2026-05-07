import { api } from "./client.js";

export function fetchModerationStats() {
  return api.get("/api/moderare/statistici");
}

export function fetchPendingModerationContent(contentType = "all") {
  const params = contentType && contentType !== "all" ? `?content_type=${encodeURIComponent(contentType)}` : "";
  return api.get(`/api/moderare/continut/in-asteptare${params}`);
}

export function fetchFlaggedModerationContent() {
  return api.get("/api/moderare/continut/marcate");
}

export function moderateContent(contentType, contentId, data) {
  return api.post(`/api/moderare/modereaza/${encodeURIComponent(contentType)}/${encodeURIComponent(contentId)}`, data);
}

export function searchModerationUsers(query) {
  return api.get(`/api/moderare/utilizatori/cauta?q=${encodeURIComponent(query)}`);
}

export function suspendUser(userId, data) {
  return api.post(`/api/moderare/utilizatori/${encodeURIComponent(userId)}/suspenda`, data);
}

export function unsuspendUser(userId) {
  return api.post(`/api/moderare/utilizatori/${encodeURIComponent(userId)}/reactiveaza`, {});
}

export function fetchModerationLogs({ decision = "", limit = 100, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (decision) params.set("decision", decision);
  if (limit) params.set("limit", String(limit));
  if (offset) params.set("offset", String(offset));
  const query = params.toString();
  return api.get(`/api/moderare/jurnal${query ? `?${query}` : ""}`);
}

export function fetchModerationQueue() {
  return api.get("/api/moderare/coada");
}

export function reviewModerationLog(logId, data) {
  return api.post(`/api/moderare/revizie/${encodeURIComponent(logId)}`, data);
}

export function fetchPostReports({ status = "open", limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (limit) params.set("limit", String(limit));
  if (offset) params.set("offset", String(offset));
  const query = params.toString();
  return api.get(`/api/moderare/raportari${query ? `?${query}` : ""}`);
}

export function reviewPostReport(reportId, data) {
  return api.post(`/api/moderare/raportari/${encodeURIComponent(reportId)}/revizie`, data);
}

export function fetchExtendedModerationStats() {
  return api.get("/api/moderare/statistici/extinse");
}
