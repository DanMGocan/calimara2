import { api } from "./client.js";

export function addSuperLike(postId) {
  return api.post(`/api/postari/${encodeURIComponent(postId)}/super-aprecieri`, {});
}

export function removeSuperLike(postId) {
  return api.delete(`/api/postari/${encodeURIComponent(postId)}/super-aprecieri`);
}

export function fetchSuperLikeQuota() {
  return api.get("/api/utilizatori/eu/super-aprecieri/cota");
}

