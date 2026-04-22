import { api } from "./client";

export type ClubSpeciality = "poezie" | "proza_scurta";
export type ClubMemberRole = "owner" | "admin" | "member";

export interface ClubOwner {
  id: number;
  username: string;
  avatar_seed: string | null;
}

export interface ClubMember {
  id: number;
  user_id: number;
  username: string;
  avatar_seed: string | null;
  role: ClubMemberRole;
  joined_at: string;
  contribution_count: number;
}

export interface ClubFeatured {
  post_id: number;
  post_title: string;
  post_slug: string;
  post_author: ClubOwner | null;
  featured_until: string;
}

export interface ClubBoardAuthor {
  id: number;
  username: string;
  avatar_seed: string | null;
  role: ClubMemberRole | null;
}

export interface ClubBoardMessage {
  id: number;
  club_id: number;
  parent_id: number | null;
  content: string;
  created_at: string;
  updated_at: string;
  author: ClubBoardAuthor | null;
  replies: ClubBoardMessage[];
}

export interface ClubSummary {
  id: number;
  owner_id: number;
  title: string;
  slug: string;
  description: string | null;
  motto: string | null;
  avatar_seed: string | null;
  theme: string | null;
  speciality: ClubSpeciality;
  member_count: number;
  owner: ClubOwner | null;
  created_at: string;
  updated_at: string;
}

export interface ClubDetail extends ClubSummary {
  members: ClubMember[];
  featured: ClubFeatured | null;
  recent_messages: ClubBoardMessage[];
  my_role: ClubMemberRole | null;
  my_pending_request_status: "application" | "invitation" | null;
  pending_request_count: number | null;
}

export interface ClubJoinRequest {
  id: number;
  club_id: number;
  user: ClubOwner | null;
  direction: "application" | "invitation";
  status: "pending" | "approved" | "rejected";
  initiator_id: number;
  created_at: string;
  responded_at: string | null;
}

export interface ClubPendingItem {
  request: ClubJoinRequest;
  club: ClubSummary;
  direction: "application" | "invitation";
}

export interface ClubCreateData {
  title: string;
  speciality: ClubSpeciality;
  description?: string | null;
  motto?: string | null;
  theme?: string | null;
  avatar_seed?: string | null;
}

export type ClubUpdateData = Partial<ClubCreateData>;

// ----- public reads -----

export function fetchClubs(params?: {
  speciality?: ClubSpeciality;
  theme?: string;
  limit?: number;
  offset?: number;
}): Promise<{ clubs: ClubSummary[] }> {
  const q = new URLSearchParams();
  if (params?.speciality) q.set("speciality", params.speciality);
  if (params?.theme) q.set("theme", params.theme);
  if (params?.limit !== undefined) q.set("limit", String(params.limit));
  if (params?.offset !== undefined) q.set("offset", String(params.offset));
  const qs = q.toString();
  return api.get(`/api/clubs${qs ? `?${qs}` : ""}`);
}

export function fetchRandomClub(): Promise<ClubSummary> {
  return api.get("/api/clubs/random");
}

export function fetchClubBySlug(slug: string): Promise<ClubDetail> {
  return api.get(`/api/clubs/${encodeURIComponent(slug)}`);
}

export function fetchClubBoard(
  clubId: number,
  params?: { limit?: number; offset?: number },
): Promise<{ messages: ClubBoardMessage[] }> {
  const q = new URLSearchParams();
  if (params?.limit !== undefined) q.set("limit", String(params.limit));
  if (params?.offset !== undefined) q.set("offset", String(params.offset));
  const qs = q.toString();
  return api.get(`/api/clubs/${clubId}/board${qs ? `?${qs}` : ""}`);
}

// ----- authenticated reads -----

export function fetchUserClubs(): Promise<{ clubs: ClubSummary[] }> {
  return api.get("/api/user/clubs");
}

export function fetchUserPendingClubInvitations(): Promise<{ items: ClubPendingItem[] }> {
  return api.get("/api/user/clubs/pending");
}

export function fetchClubRequests(clubId: number): Promise<{ requests: ClubJoinRequest[] }> {
  return api.get(`/api/clubs/${clubId}/requests`);
}

// ----- mutations -----

export function createClub(data: ClubCreateData): Promise<ClubSummary> {
  return api.post("/api/clubs/", data);
}

export function updateClub(clubId: number, data: ClubUpdateData): Promise<ClubSummary> {
  return api.put(`/api/clubs/${clubId}`, data);
}

export function deleteClub(clubId: number): Promise<void> {
  return api.delete(`/api/clubs/${clubId}`);
}

export function applyToClub(clubId: number): Promise<ClubJoinRequest> {
  return api.post(`/api/clubs/${clubId}/apply`);
}

export function inviteToClub(clubId: number, username: string): Promise<ClubJoinRequest> {
  return api.post(`/api/clubs/${clubId}/invite`, { username });
}

export function respondClubRequest(
  clubId: number,
  requestId: number,
  action: "approve" | "reject",
): Promise<ClubJoinRequest> {
  return api.post(`/api/clubs/${clubId}/requests/${requestId}/respond`, { action });
}

export function kickClubMember(clubId: number, userId: number): Promise<void> {
  return api.delete(`/api/clubs/${clubId}/members/${userId}`);
}

export function updateClubMemberRole(
  clubId: number,
  userId: number,
  role: "admin" | "member",
): Promise<{ id: number; user_id: number; role: ClubMemberRole; joined_at: string }> {
  return api.put(`/api/clubs/${clubId}/members/${userId}/role`, { role });
}

export function postClubBoardMessage(
  clubId: number,
  data: { content: string; parent_id?: number | null },
): Promise<ClubBoardMessage> {
  return api.post(`/api/clubs/${clubId}/board`, data);
}

export function deleteClubBoardMessage(clubId: number, messageId: number): Promise<void> {
  return api.delete(`/api/clubs/${clubId}/board/${messageId}`);
}

export function setClubFeatured(clubId: number, postId: number): Promise<ClubFeatured> {
  return api.post(`/api/clubs/${clubId}/featured`, { post_id: postId });
}

export function clearClubFeatured(clubId: number): Promise<void> {
  return api.delete(`/api/clubs/${clubId}/featured`);
}
