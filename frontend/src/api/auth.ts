import { api } from "./client";

export interface CurrentUser {
  id: number;
  username: string;
  email: string;
  subtitle: string | null;
  avatar_seed: string;
  is_admin: boolean;
  is_moderator: boolean;
  is_suspended: boolean;
}

interface MeResponse {
  authenticated: boolean;
  user: CurrentUser | null;
}

export function fetchCurrentUser(): Promise<MeResponse> {
  return api.get<MeResponse>("/api/user/me");
}

export interface SetupData {
  username: string;
  subtitle?: string;
  avatar_seed: string;
}

export function completeSetup(data: SetupData): Promise<{ message: string; username: string }> {
  return api.post("/api/auth/complete-setup", data);
}
