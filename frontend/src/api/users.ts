import { api } from "./client";

export interface UserProfile {
  id: number;
  username: string;
  subtitle: string | null;
  avatar_seed: string;
  facebook_url: string | null;
  tiktok_url: string | null;
  instagram_url: string | null;
  x_url: string | null;
  bluesky_url: string | null;
  patreon_url: string | null;
  paypal_url: string | null;
  buymeacoffee_url: string | null;
}

export function fetchUserProfile(username: string): Promise<UserProfile> {
  return api.get(`/api/user/${username}/profile`);
}

export interface UserUpdateData {
  subtitle?: string;
  avatar_seed?: string;
}

export function updateUser(data: UserUpdateData): Promise<UserProfile> {
  return api.put("/api/user/me", data);
}

export interface SocialLinksData {
  facebook_url?: string;
  tiktok_url?: string;
  instagram_url?: string;
  x_url?: string;
  bluesky_url?: string;
  buymeacoffee_url?: string;
}

export function updateSocialLinks(data: SocialLinksData): Promise<UserProfile> {
  return api.put("/api/user/social-links", data);
}

export function updateBestFriends(friends: (string | null)[]): Promise<{ message: string }> {
  return api.put("/api/user/best-friends", { friends });
}

export function updateFeaturedPosts(post_ids: (number | null)[]): Promise<{ message: string }> {
  return api.put("/api/user/featured-posts", { post_ids });
}

export function searchUsers(q: string): Promise<{ username: string; subtitle: string | null }[]> {
  return api.get(`/api/users/search?q=${encodeURIComponent(q)}`);
}
