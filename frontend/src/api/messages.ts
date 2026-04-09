import { api } from "./client";

export interface Conversation {
  id: number;
  other_user: {
    id: number;
    username: string;
    avatar_seed: string;
  };
  latest_message: {
    content: string;
    sender_id: number;
    created_at: string;
    is_read: boolean;
  } | null;
  unread_count: number;
  updated_at: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  sender_id: number;
  content: string;
  is_read: boolean;
  created_at: string;
}

export function fetchConversations(): Promise<Conversation[]> {
  return api.get("/api/messages/conversations");
}

export function fetchConversation(id: number, page = 1): Promise<{ messages: Message[]; has_more: boolean }> {
  return api.get(`/api/messages/conversations/${id}?page=${page}`);
}

export function sendMessageInConversation(id: number, content: string): Promise<Message> {
  return api.post(`/api/messages/conversations/${id}`, { content });
}

export function sendNewMessage(username: string, content: string): Promise<{ conversation_id: number; message: Message }> {
  return api.post("/api/messages/send", { username, content });
}

export function fetchUnreadCount(): Promise<{ unread_count: number }> {
  return api.get("/api/messages/unread-count");
}

export function deleteConversation(id: number): Promise<void> {
  return api.delete(`/api/messages/conversations/${id}`);
}

export function searchConversations(q: string): Promise<Conversation[]> {
  return api.get(`/api/messages/search?q=${encodeURIComponent(q)}`);
}
