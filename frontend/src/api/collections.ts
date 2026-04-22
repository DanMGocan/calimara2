import { api } from "./client";

export interface CollectionAuthor {
  id: number;
  username: string;
  avatar_seed: string | null;
}

export interface CollectionSummary {
  id: number;
  owner_id: number;
  title: string;
  slug: string;
  description: string | null;
  owner: CollectionAuthor | null;
  post_count: number;
  pending_count: number;
  created_at: string;
  updated_at: string;
}

export interface CollectionPostRef {
  id: number;
  title: string;
  slug: string;
  category: string | null;
  super_likes_count?: number;
  owner: CollectionAuthor | null;
}

export interface CollectionEntry {
  id: number;
  collection_id: number;
  post_id: number;
  initiator_id: number;
  status: "pending" | "accepted" | "rejected";
  position: number | null;
  created_at: string;
  responded_at: string | null;
  post: CollectionPostRef | null;
}

export interface CollectionDetail extends CollectionSummary {
  posts: CollectionEntry[];
}

export interface CollectionManageView extends CollectionSummary {
  accepted: CollectionEntry[];
  pending: CollectionEntry[];
}

export interface PendingApprovalItem {
  entry: CollectionEntry;
  direction: "invitation" | "suggestion";
  collection: CollectionSummary;
  post: CollectionPostRef;
}

export interface CollectionMembership {
  id: number;
  title: string;
  slug: string;
  owner: CollectionAuthor;
}

export interface CollectionCreateData {
  title: string;
  description?: string | null;
}

export interface CollectionUpdateData {
  title?: string;
  description?: string | null;
}

// Public endpoints
export function fetchCollectionBySlug(slug: string): Promise<CollectionDetail> {
  return api.get(`/api/collections/${encodeURIComponent(slug)}`);
}

export function fetchUserCollections(username: string): Promise<{ collections: CollectionSummary[] }> {
  return api.get(`/api/users/${encodeURIComponent(username)}/collections`);
}

export function fetchPostCollections(postId: number): Promise<{ collections: CollectionMembership[] }> {
  return api.get(`/api/posts/${postId}/collections`);
}

// Authenticated (owner) endpoints
export function fetchMyCollections(): Promise<{ collections: CollectionSummary[] }> {
  return api.get("/api/user/collections");
}

export function fetchMyPendingApprovals(): Promise<{ items: PendingApprovalItem[] }> {
  return api.get("/api/user/collections/pending");
}

export function fetchMyCollectionManage(collectionId: number): Promise<CollectionManageView> {
  return api.get(`/api/user/collections/${collectionId}/manage`);
}

export function createCollection(data: CollectionCreateData): Promise<CollectionSummary> {
  return api.post("/api/collections/", data);
}

export function updateCollection(collectionId: number, data: CollectionUpdateData): Promise<CollectionSummary> {
  return api.put(`/api/collections/${collectionId}`, data);
}

export function deleteCollection(collectionId: number): Promise<void> {
  return api.delete(`/api/collections/${collectionId}`);
}

export function addPostToCollection(collectionId: number, postId: number): Promise<CollectionEntry> {
  return api.post(`/api/collections/${collectionId}/posts`, { post_id: postId });
}

export function respondCollectionEntry(
  collectionId: number,
  postId: number,
  action: "accept" | "reject",
): Promise<CollectionEntry> {
  return api.post(`/api/collections/${collectionId}/posts/${postId}/respond`, { action });
}

export function removeCollectionEntry(collectionId: number, postId: number): Promise<void> {
  return api.delete(`/api/collections/${collectionId}/posts/${postId}`);
}

export interface RandomCollection {
  id: number;
  title: string;
  slug: string;
  description: string | null;
  owner: CollectionAuthor | null;
}

export function fetchRandomCollection(): Promise<RandomCollection> {
  return api.get("/api/collections/random");
}
