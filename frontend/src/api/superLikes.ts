import { api } from "./client";

export interface SuperLike {
  id: number;
  post_id: number;
  user_id: number;
  created_at: string;
}

export interface SuperLikeQuota {
  weekly_quota: number;
  used_this_week: number;
  remaining: number;
  week_resets_at: string;
  is_premium: boolean;
}

export const superLikePost = (postId: number) =>
  api.post<SuperLike>(`/api/posts/${postId}/super-likes`);

export const unSuperLikePost = (postId: number) =>
  api.delete<void>(`/api/posts/${postId}/super-likes`);

export const fetchSuperLikeQuota = () =>
  api.get<SuperLikeQuota>("/api/users/me/super-likes/quota");
