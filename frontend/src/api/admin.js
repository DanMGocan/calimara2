import { api, buildQuery } from "./client.js";

export function fetchAdminOverview(params = {}) {
  return api.get(`/api/admin/overview${buildQuery(params)}`);
}

export function rollupAdminMetrics(date) {
  return api.post(`/api/admin/metrics/rollup${buildQuery({ date })}`, {});
}

export function fetchAdminUsers(params = {}) {
  return api.get(`/api/admin/users${buildQuery(params)}`);
}

export function fetchAdminUser(userId) {
  return api.get(`/api/admin/users/${encodeURIComponent(userId)}`);
}

export function updateAdminUserRoles(userId, data) {
  return api.put(`/api/admin/users/${encodeURIComponent(userId)}/roles`, data);
}

export function suspendAdminUser(userId, reason) {
  return api.post(`/api/admin/users/${encodeURIComponent(userId)}/suspend`, { reason });
}

export function reactivateAdminUser(userId, reason) {
  return api.post(`/api/admin/users/${encodeURIComponent(userId)}/reactivate`, { reason });
}

export function updateAdminUserPremium(userId, data) {
  return api.put(`/api/admin/users/${encodeURIComponent(userId)}/premium`, data);
}

export function adjustAdminUserGologani(userId, data) {
  return api.post(`/api/admin/users/${encodeURIComponent(userId)}/gologani-adjustments`, data);
}

export function deleteAdminUser(userId, reason) {
  return api.delete(`/api/admin/users/${encodeURIComponent(userId)}`, { reason });
}

export function fetchAdminContent(params = {}) {
  return api.get(`/api/admin/content${buildQuery(params)}`);
}

export function updateAdminContent(contentType, contentId, data) {
  return api.put(`/api/admin/content/${encodeURIComponent(contentType)}/${encodeURIComponent(contentId)}`, data);
}

export function moderateAdminContent(contentType, contentId, data) {
  return api.post(`/api/admin/content/${encodeURIComponent(contentType)}/${encodeURIComponent(contentId)}/moderate`, data);
}

export function deleteAdminContent(contentType, contentId, reason) {
  return api.delete(`/api/admin/content/${encodeURIComponent(contentType)}/${encodeURIComponent(contentId)}`, { reason });
}

export function fetchAdminJobs(params = {}) {
  return api.get(`/api/admin/jobs${buildQuery(params)}`);
}

export function fetchAdminIntegrations() {
  return api.get("/api/admin/integrations");
}

export function fetchAdminPerformanceLive() {
  return api.get("/api/admin/performance/live");
}

export function fetchAdminPerformanceHistory(params = {}) {
  return api.get(`/api/admin/performance/history${buildQuery(params)}`);
}

export function retryAdminJob(jobId, reason) {
  return api.post(`/api/admin/jobs/${encodeURIComponent(jobId)}/retry`, { reason });
}

export function cancelAdminJob(jobId, reason) {
  return api.post(`/api/admin/jobs/${encodeURIComponent(jobId)}/cancel`, { reason });
}

export function fetchAdminAuditLog(params = {}) {
  return api.get(`/api/admin/audit-log${buildQuery(params)}`);
}

export function fetchAdminStorageObjects(params = {}) {
  return api.get(`/api/admin/storage/objects${buildQuery(params)}`);
}

export function presignAdminStorageObject(key) {
  return api.post("/api/admin/storage/objects/presign", { key });
}

export function deleteAdminStorageObject(key, reason) {
  return api.delete("/api/admin/storage/objects", { key, reason });
}

export function cleanupAdminStorageObject(key, reason) {
  return api.post("/api/admin/storage/objects/cleanup", { key, reason });
}

export function fetchAdminSiteFeedback(params = {}) {
  return api.get(`/api/admin/site-feedback${buildQuery(params)}`);
}

export function fetchAdminQaReport(params = {}) {
  return api.get(`/api/admin/referinta/raport-qa${buildQuery(params)}`);
}

export function updateAdminSiteFeedback(feedbackId, data) {
  return api.put(`/api/admin/site-feedback/${encodeURIComponent(feedbackId)}`, data);
}

export function fetchAdminSiteFeedbackThread(feedbackId) {
  return api.get(`/api/admin/site-feedback/${encodeURIComponent(feedbackId)}/thread`);
}

export function replyAdminSiteFeedback(feedbackId, data) {
  return api.post(`/api/admin/site-feedback/${encodeURIComponent(feedbackId)}/reply`, data);
}

export function fetchAdminPlatformAccess() {
  return api.get("/api/admin/platform-access");
}

export function updateAdminPlatformAccess(data) {
  return api.put("/api/admin/platform-access", data);
}

export function addAdminPlatformAllowedEmail(data) {
  return api.post("/api/admin/platform-access/emails", data);
}

export function deleteAdminPlatformAllowedEmail(emailId) {
  return api.delete(`/api/admin/platform-access/emails/${encodeURIComponent(emailId)}`);
}

export function fetchAdminInvitations() {
  return api.get("/api/admin/invitatii");
}

export function createAdminInvitations(data) {
  return api.post("/api/admin/invitatii", data);
}

export function resendAdminInvitation(invitationId) {
  return api.post(`/api/admin/invitatii/${encodeURIComponent(invitationId)}/retrimite`, {});
}

export function revokeAdminInvitation(invitationId) {
  return api.post(`/api/admin/invitatii/${encodeURIComponent(invitationId)}/revoca`, {});
}

export function previewAdminEmail(data) {
  return api.post("/api/admin/email/preview", data);
}

export function createAdminEmailCampaign(data) {
  return api.post("/api/admin/email/campaigns", data);
}

export function processAdminEmailOutbox(params = {}) {
  return api.post(`/api/admin/email/outbox/process${buildQuery(params)}`, {});
}

export function sendAdminNotificationTestEmail() {
  return api.post("/api/admin/email/test-notification", {});
}

export function fetchAdminEmailCampaigns(params = {}) {
  return api.get(`/api/admin/email/campaigns${buildQuery(params)}`);
}
