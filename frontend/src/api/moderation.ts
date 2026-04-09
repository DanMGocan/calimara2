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
  content_type: string;
  content_id: number;
  title?: string;
  content: string;
  author: string;
  toxicity_score: number;
  moderation_status: string;
  created_at: string;
}

export interface ModerationLog {
  id: number;
  content_type: string;
  content_id: number;
  user_id: number;
  toxicity_score: number;
  ai_decision: string;
  ai_reason: string;
  human_decision: string | null;
  human_reason: string | null;
  needs_human_review: boolean;
  created_at: string;
}

export function fetchModerationStats(): Promise<ModerationStats> {
  return api.get("/api/moderation/stats");
}

export function fetchPendingContent(): Promise<ModerationItem[]> {
  return api.get("/api/moderation/content/pending");
}

export function fetchFlaggedContent(): Promise<ModerationItem[]> {
  return api.get("/api/moderation/content/flagged");
}

export function moderateContent(type: string, id: number, action: string, reason?: string): Promise<{ message: string }> {
  return api.post(`/api/moderation/moderate/${type}/${id}`, { action, reason });
}

export function fetchModerationQueue(): Promise<ModerationItem[]> {
  return api.get("/api/moderation/queue");
}

export function fetchModerationLogs(page = 1): Promise<{ logs: ModerationLog[]; has_more: boolean }> {
  return api.get(`/api/moderation/logs?page=${page}`);
}

export function reviewModerationLog(logId: number, decision: string, reason: string): Promise<{ message: string }> {
  return api.post(`/api/moderation/review/${logId}`, { decision, reason });
}

export function searchModerationUsers(q: string): Promise<{ id: number; username: string; is_suspended: boolean }[]> {
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
