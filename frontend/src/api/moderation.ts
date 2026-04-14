import { api } from "./client";

export interface ModerationStats {
  pending_count: number;
  flagged_count: number;
  suspended_count: number;
  today_actions: number;
  posts_pending: number;
  posts_flagged: number;
  comments_pending: number;
  comments_flagged: number;
}

export interface ModerationItem {
  id: number;
  type: string;
  content_type?: string; // Some endpoints might use this instead
  content_id?: number;
  title?: string;
  content: string;
  author: string;
  toxicity_score: number;
  moderation_status: string;
  created_at: string;
}

export interface ModerationQueueItem {
  log_id: number;
  content_type: string;
  content: {
    id: number;
    title?: string;
    content: string;
    author: string;
    created_at: string;
  };
  ai_analysis: {
    decision: string;
    toxicity_score: number;
    harassment_score: number;
    hate_speech_score: number;
    reason: string;
  };
  flagged_at: string;
}

export interface ModerationLog {
  id: number;
  content_type: string;
  content_id: number;
  content_title: string;
  content_preview: string;
  content_author: string;
  toxicity_score: number;
  ai_decision: string;
  ai_reason: string;
  human_decision: string | null;
  human_reason: string | null;
  moderator: string | null;
  moderated_at: string | null;
  created_at: string;
  needs_review: boolean;
}

export interface ModerationUser {
  id: number;
  username: string;
  email: string;
  is_suspended: boolean;
  suspension_reason: string;
  created_at: string;
  is_admin: boolean;
  is_moderator: boolean;
}

export function fetchModerationStats(): Promise<ModerationStats> {
  return api.get("/api/moderation/stats");
}

export function fetchPendingContent(): Promise<{ content: ModerationItem[] }> {
  return api.get("/api/moderation/content/pending");
}

export function fetchFlaggedContent(): Promise<{ content: ModerationItem[] }> {
  return api.get("/api/moderation/content/flagged");
}

export function moderateContent(type: string, id: number, action: string, reason?: string): Promise<{ message: string }> {
  return api.post(`/api/moderation/moderate/${type}/${id}`, { action, reason });
}

export function fetchModerationQueue(): Promise<{ queue: ModerationQueueItem[] }> {
  return api.get("/api/moderation/queue");
}

export function fetchModerationLogs(page = 1): Promise<{ logs: ModerationLog[]; total: number }> {
  return api.get(`/api/moderation/logs?page=${page}`);
}

export function reviewModerationLog(logId: number, action: string, reason: string): Promise<{ message: string }> {
  return api.post(`/api/moderation/review/${logId}`, { action, reason });
}

export function searchModerationUsers(q: string): Promise<{ users: ModerationUser[] }> {
  return api.get(`/api/moderation/users/search?q=${encodeURIComponent(q)}`);
}

export function suspendUser(userId: number, reason: string): Promise<{ message: string }> {
  return api.post(`/api/moderation/users/${userId}/suspend`, { reason });
}

export function unsuspendUser(userId: number): Promise<{ message: string }> {
  return api.post(`/api/moderation/users/${userId}/unsuspend`);
}

export function fetchExtendedStats(): Promise<Record<string, unknown>> {
  return api.get("/api/moderation/stats/extended");
}
