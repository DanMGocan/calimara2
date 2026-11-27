import { api, buildQuery } from "./client.js";

export function fetchForumThreads({ section, q, sort, page, perPage } = {}) {
  const query = buildQuery({ section, q, sort, page, per_page: perPage });
  return api.get(`/api/forum/discutii${query}`);
}

export function fetchForumSections() {
  return api.get("/api/forum/sectiuni");
}

export function fetchForumThread(slug, { page, reply, unread } = {}) {
  const query = buildQuery({ page, reply, unread: unread ? 1 : undefined });
  return api.get(`/api/forum/discutii/${encodeURIComponent(slug)}${query}`);
}

export function createForumThread(data) {
  return api.post("/api/forum/discutii", data);
}

export function updateForumThread(threadId, data) {
  return api.put(`/api/forum/discutii/${encodeURIComponent(threadId)}`, data);
}

export function createForumReply(threadId, data) {
  return api.post(`/api/forum/discutii/${encodeURIComponent(threadId)}/raspunsuri`, data);
}

export function updateForumReply(replyId, data) {
  return api.put(`/api/forum/raspunsuri/${encodeURIComponent(replyId)}`, data);
}

export function followForumThread(threadId) {
  return api.post(`/api/forum/discutii/${encodeURIComponent(threadId)}/urmareste`, {});
}

export function unfollowForumThread(threadId) {
  return api.delete(`/api/forum/discutii/${encodeURIComponent(threadId)}/urmareste`);
}

export function likeForumReply(replyId) {
  return api.post(`/api/forum/raspunsuri/${encodeURIComponent(replyId)}/aprecieri`, {});
}

export function unlikeForumReply(replyId) {
  return api.delete(`/api/forum/raspunsuri/${encodeURIComponent(replyId)}/aprecieri`);
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

// action: "lock" | "unlock" | "pin" | "unpin" | "move" (move needs `section`).
export function updateForumThreadState(threadId, action, section) {
  return api.post(`/api/forum/discutii/${encodeURIComponent(threadId)}/stare`, section ? { action, section } : { action });
}

// action: "pin" | "unpin"
export function updateForumReplyState(replyId, action) {
  return api.post(`/api/forum/raspunsuri/${encodeURIComponent(replyId)}/stare`, { action });
}

// Admin: forum sections and thread tools.
export function fetchAdminForumSections() {
  return api.get("/api/admin/forum/sectiuni");
}

export function createAdminForumSection(data) {
  return api.post("/api/admin/forum/sectiuni", data);
}

export function updateAdminForumSection(sectionId, data) {
  return api.put(`/api/admin/forum/sectiuni/${encodeURIComponent(sectionId)}`, data);
}

export function reorderAdminForumSections(sectionIds) {
  return api.post("/api/admin/forum/sectiuni/ordine", { section_ids: sectionIds });
}

export function deleteAdminForumSection(sectionId, moveTo) {
  const query = buildQuery({ move_to: moveTo });
  return api.delete(`/api/admin/forum/sectiuni/${encodeURIComponent(sectionId)}${query}`);
}

export function fetchAdminForumThreads({ section, status, pinned, locked, q, page, perPage } = {}) {
  const query = buildQuery({ section, status, pinned, locked, q, page, per_page: perPage });
  return api.get(`/api/admin/forum/discutii${query}`);
}

export function bulkAdminForumThreads(threadIds, action, section) {
  return api.post("/api/admin/forum/discutii/actiuni", section ? { thread_ids: threadIds, action, section } : { thread_ids: threadIds, action });
}
