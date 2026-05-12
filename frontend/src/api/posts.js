import { api, buildQuery } from "./client.js";

export function fetchArchive(params = {}) {
  return api.get(`/api/postari/arhiva${buildQuery(params)}`);
}

export function fetchPostMonths() {
  return api.get("/api/postari/luni");
}

export function fetchRandomPosts(category) {
  const params = category ? `?category=${encodeURIComponent(category)}` : "";
  return api.get(`/api/postari/aleatoriu${params}`);
}

export function createPost(data) {
  return api.post("/api/postari/", data);
}

export function fetchPostDrafts(params = {}) {
  return api.get(`/api/postari/ciorne${buildQuery(params)}`);
}

export function fetchPostDraft(draftId) {
  return api.get(`/api/postari/ciorne/${encodeURIComponent(draftId)}`);
}

export function createPostDraft(data) {
  return api.post("/api/postari/ciorne", data);
}

export function updatePostDraft(draftId, data) {
  return api.put(`/api/postari/ciorne/${encodeURIComponent(draftId)}`, data);
}

export function deletePostDraft(draftId) {
  return api.delete(`/api/postari/ciorne/${encodeURIComponent(draftId)}`);
}

export function updatePost(postId, data) {
  return api.put(`/api/postari/${encodeURIComponent(postId)}`, data);
}

export function deletePost(postId) {
  return api.delete(`/api/postari/${encodeURIComponent(postId)}`);
}

export function fetchOwnedPostForEdit(postId) {
  return api.get(`/api/postari/${encodeURIComponent(postId)}/editare`);
}

export function createComment(postId, data) {
  return api.post(`/api/postari/${encodeURIComponent(postId)}/comentarii`, data);
}

export function reportPost(postId, data) {
  return api.post(`/api/postari/${encodeURIComponent(postId)}/raportari`, data);
}

export function approveComment(commentId) {
  return api.put(`/api/comentarii/${encodeURIComponent(commentId)}/aproba`, {});
}

export function deleteComment(commentId) {
  return api.delete(`/api/comentarii/${encodeURIComponent(commentId)}`);
}

export function likePost(postId) {
  return api.post(`/api/postari/${encodeURIComponent(postId)}/aprecieri`, {});
}

export function fetchLikeCount(postId) {
  return api.get(`/api/postari/${encodeURIComponent(postId)}/aprecieri/numar`);
}
