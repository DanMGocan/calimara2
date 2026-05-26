import { api } from "./client.js";

export function fetchNotifications() {
  return api.get("/api/notificari");
}

export function fetchUnreadNotificationCount() {
  return api.get("/api/notificari/necitite");
}

export function markNotificationRead(notificationId) {
  return api.put(`/api/notificari/${encodeURIComponent(notificationId)}/citita`, {});
}

export function markNotificationUnread(notificationId) {
  return api.put(`/api/notificari/${encodeURIComponent(notificationId)}/necitita`, {});
}

export function deleteNotification(notificationId) {
  return api.delete(`/api/notificari/${encodeURIComponent(notificationId)}`);
}

export function markAllNotificationsRead() {
  return api.put("/api/notificari/citeste-toate", {});
}
