import { api } from "./client.js";

export function fetchFriendsState() {
  return api.get("/api/prieteni");
}

export function fetchFriendshipStatus(userId) {
  return api.get(`/api/prieteni/status/${encodeURIComponent(userId)}`);
}

export function sendFriendRequest(userId) {
  return api.post(`/api/prieteni/cereri/${encodeURIComponent(userId)}`, {});
}

export function acceptFriendRequest(friendshipId) {
  return api.post(`/api/prieteni/cereri/${encodeURIComponent(friendshipId)}/accepta`, {});
}

export function deleteFriendRequest(friendshipId) {
  return api.delete(`/api/prieteni/cereri/${encodeURIComponent(friendshipId)}`);
}

export function removeFriend(userId) {
  return api.delete(`/api/prieteni/${encodeURIComponent(userId)}`);
}
