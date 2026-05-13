import { api } from "./client.js";

export function fetchFollowStatus(userId) {
  return api.get(`/api/urmariri/status/${encodeURIComponent(userId)}`);
}

export function followUser(userId) {
  return api.post(`/api/urmariri/${encodeURIComponent(userId)}`, {});
}

export function unfollowUser(userId) {
  return api.delete(`/api/urmariri/${encodeURIComponent(userId)}`);
}

export function fetchFollowers(username) {
  return api.get(`/api/utilizatori/${encodeURIComponent(username)}/urmaritori`);
}

export function fetchFollowing(username) {
  return api.get(`/api/utilizatori/${encodeURIComponent(username)}/urmariti`);
}
