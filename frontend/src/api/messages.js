import { api } from "./client.js";

export function fetchConversations() {
  return api.get("/api/mesaje/conversatii");
}

export function fetchConversation(conversationId) {
  return api.get(`/api/mesaje/conversatii/${encodeURIComponent(conversationId)}`);
}

export function sendConversationMessage(conversationId, data) {
  return api.post(`/api/mesaje/conversatii/${encodeURIComponent(conversationId)}`, data);
}

export function sendMessage(data) {
  return api.post("/api/mesaje/trimite", data);
}

export function fetchUnreadMessageCount() {
  return api.get("/api/mesaje/necitite");
}

export function deleteConversation(conversationId) {
  return api.delete(`/api/mesaje/conversatii/${encodeURIComponent(conversationId)}`);
}

export function searchConversations(query) {
  return api.get(`/api/mesaje/cauta?q=${encodeURIComponent(query)}`);
}

