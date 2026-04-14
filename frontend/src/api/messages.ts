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

export interface ConversationDetail {
  conversation: {
    id: number;
    other_user: {
      id: number;
      username: string;
      subtitle: string | null;
      avatar_seed: string;
    };
  };
  messages: Message[];
}

export async function fetchConversations(): Promise<Conversation[]> {
  const response = await api.get<{ conversations: Conversation[] }>("/api/messages/conversations");
  return response.conversations;
}

export function fetchConversation(id: number, page = 1): Promise<ConversationDetail> {
  const limit = 50;
  const offset = (page - 1) * limit;
  return api.get(`/api/messages/conversations/${id}?limit=${limit}&offset=${offset}`);
}

export function sendMessageInConversation(id: number, content: string): Promise<Message> {
  return api.post(`/api/messages/conversations/${id}`, { content });
}

export function sendNewMessage(
  recipientUsername: string,
  content: string,
): Promise<{ message: string; conversation_id: number; message_id: number }> {
  return api.post("/api/messages/send", { recipient_username: recipientUsername, content });
}

export function fetchUnreadCount(): Promise<{ unread_count: number }> {
  return api.get("/api/messages/unread-count");
}

export function deleteConversation(id: number): Promise<void> {
  return api.delete(`/api/messages/conversations/${id}`);
}

export async function searchConversations(q: string): Promise<Conversation[]> {
  const response = await api.get<{ conversations: Conversation[] }>(
    `/api/messages/search?q=${encodeURIComponent(q)}`,
  );
  return response.conversations;
}
