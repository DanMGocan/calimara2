import { api } from "./client.js";

export function fetchForumThreads(section = "general") {
  const params = section && section !== "toate" ? `?section=${encodeURIComponent(section)}` : "";
  return api.get(`/api/forum/discutii${params}`);
}

export function fetchForumSections() {
  return api.get("/api/forum/sectiuni");
}

export function fetchForumThread(slug) {
  return api.get(`/api/forum/discutii/${encodeURIComponent(slug)}`);
}

export function createForumThread(data) {
  return api.post("/api/forum/discutii", data);
}

export function createForumReply(threadId, data) {
  return api.post(`/api/forum/discutii/${encodeURIComponent(threadId)}/raspunsuri`, data);
}

export function reportForumThread(threadId, data) {
  return api.post(`/api/forum/discutii/${encodeURIComponent(threadId)}/raportari`, data);
}

export function reportForumReply(replyId, data) {
  return api.post(`/api/forum/raspunsuri/${encodeURIComponent(replyId)}/raportari`, data);
}

export function deleteForumThread(threadId) {
  return api.delete(`/api/forum/discutii/${encodeURIComponent(threadId)}`);
}

export function deleteForumReply(replyId) {
  return api.delete(`/api/forum/raspunsuri/${encodeURIComponent(replyId)}`);
}

export function updateForumThreadState(threadId, action) {
  return api.post(`/api/forum/discutii/${encodeURIComponent(threadId)}/stare`, { action });
}
