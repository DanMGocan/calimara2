import { api } from "./client";
import type { BlogUser } from "./posts";

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

export function searchUsers(q: string): Promise<{ username: string; subtitle: string | null }[]> {
  return api.get(`/api/users/search?q=${encodeURIComponent(q)}`);
}

export function fetchRandomUser(): Promise<BlogUser> {
  return api.get("/api/users/random");
}
