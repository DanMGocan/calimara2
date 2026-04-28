class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, options = {}) {
  const headers = {
    Accept: "application/json",
    ...options.headers
  };

  let body = options.body;
  if (body && typeof body === "object" && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }

  const response = await fetch(path, {
    credentials: "include",
    ...options,
    headers,
    body
  });

  if (!response.ok) {
    const text = await response.text();
    let message = text || `Cererea a eșuat (${response.status}).`;
    try {
      const json = JSON.parse(text);
      message = json.detail ?? json.message ?? message;
    } catch {
      // Keep the server response text.
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", body }),
  put: (path, body) => request(path, { method: "PUT", body }),
  delete: (path) => request(path, { method: "DELETE" })
};

export const AUTH_GOOGLE_PATH = "/auth/google";
export const AUTH_GOOGLE_CALLBACK_PATH = "/auth/google/callback";
export const AUTH_SETUP_PATH = "/auth/setup";

export function fetchMe() {
  return api.get("/api/user/me");
}

export function updateMe(data) {
  return api.put("/api/user/me", data);
}

export function updateSocialLinks(data) {
  return api.put("/api/user/social-links", data);
}

export function updateBestFriends(friends) {
  return api.put("/api/user/best-friends", { friends });
}

export function searchUsers(query) {
  return api.get(`/api/users/search?q=${encodeURIComponent(query)}`);
}

export function fetchPublicProfile(username) {
  return api.get(`/api/user/${encodeURIComponent(username)}/profile`);
}

export function updateFeaturedPosts(postIds) {
  return api.put("/api/user/featured-posts", { post_ids: postIds });
}

export function fetchLanding(category) {
  return api.get(`/api/landing?category=${encodeURIComponent(category)}`);
}

export function fetchCategory(categoryKey, sortBy = "newest") {
  return api.get(`/api/categories/${encodeURIComponent(categoryKey)}?sort_by=${encodeURIComponent(sortBy)}`);
}

export function fetchBlog(username) {
  return api.get(`/api/blog/${encodeURIComponent(username)}`);
}

export function fetchPostDetail(username, slug) {
  return api.get(`/api/blog/${encodeURIComponent(username)}/post/${encodeURIComponent(slug)}`);
}

export function postPdfUrl(username, slug) {
  return `/api/blog/${encodeURIComponent(username)}/post/${encodeURIComponent(slug)}/pdf`;
}

export function fetchPostAudioStatus(postId) {
  return api.get(`/api/audio/posts/${encodeURIComponent(postId)}`);
}

export function fetchRandomUser() {
  return api.get("/api/users/random");
}

export function fetchClubs() {
  return api.get("/api/clubs?limit=50");
}

export function fetchRandomClub() {
  return api.get("/api/clubs/random");
}

export function fetchClub(slug) {
  return api.get(`/api/clubs/${encodeURIComponent(slug)}`);
}

export function fetchArchive() {
  return api.get("/api/posts/archive");
}

export function fetchPostMonths() {
  return api.get("/api/posts/months");
}

export function fetchRandomPosts(category) {
  const params = category ? `?category=${encodeURIComponent(category)}` : "";
  return api.get(`/api/posts/random${params}`);
}

export function createPost(data) {
  return api.post("/api/posts/", data);
}

export function updatePost(postId, data) {
  return api.put(`/api/posts/${encodeURIComponent(postId)}`, data);
}

export function deletePost(postId) {
  return api.delete(`/api/posts/${encodeURIComponent(postId)}`);
}

export function createComment(postId, data) {
  return api.post(`/api/posts/${encodeURIComponent(postId)}/comments`, data);
}

export function approveComment(commentId) {
  return api.put(`/api/comments/${encodeURIComponent(commentId)}/approve`, {});
}

export function deleteComment(commentId) {
  return api.delete(`/api/comments/${encodeURIComponent(commentId)}`);
}

export function likePost(postId) {
  return api.post(`/api/posts/${encodeURIComponent(postId)}/likes`, {});
}

export function fetchLikeCount(postId) {
  return api.get(`/api/posts/${encodeURIComponent(postId)}/likes/count`);
}

export function fetchConversations() {
  return api.get("/api/messages/conversations");
}

export function fetchConversation(conversationId) {
  return api.get(`/api/messages/conversations/${encodeURIComponent(conversationId)}`);
}

export function sendConversationMessage(conversationId, data) {
  return api.post(`/api/messages/conversations/${encodeURIComponent(conversationId)}`, data);
}

export function sendMessage(data) {
  return api.post("/api/messages/send", data);
}

export function fetchUnreadMessageCount() {
  return api.get("/api/messages/unread-count");
}

export function deleteConversation(conversationId) {
  return api.delete(`/api/messages/conversations/${encodeURIComponent(conversationId)}`);
}

export function searchConversations(query) {
  return api.get(`/api/messages/search?q=${encodeURIComponent(query)}`);
}

export function fetchNotifications() {
  return api.get("/api/notifications");
}

export function fetchUnreadNotificationCount() {
  return api.get("/api/notifications/unread-count");
}

export function markNotificationRead(notificationId) {
  return api.put(`/api/notifications/${encodeURIComponent(notificationId)}/read`, {});
}

export function markAllNotificationsRead() {
  return api.put("/api/notifications/read-all", {});
}

export function fetchPostStats(postId) {
  return api.get(`/api/stats/post/${encodeURIComponent(postId)}`);
}

export function fetchAuthorStats(username) {
  return api.get(`/api/stats/author/${encodeURIComponent(username)}`);
}

export function fetchCategoryStats(categoryKey) {
  return api.get(`/api/stats/category/${encodeURIComponent(categoryKey)}`);
}

export function fetchOverviewStats() {
  return api.get("/api/stats/overview");
}

export function fetchMyStats() {
  return api.get("/api/stats/my");
}

export function createCollection(data) {
  return api.post("/api/collections/", data);
}

export function fetchRandomCollection() {
  return api.get("/api/collections/random");
}

export function fetchCollection(slug) {
  return api.get(`/api/collections/${encodeURIComponent(slug)}`);
}

export function collectionPdfUrl(slug) {
  return `/api/collections/${encodeURIComponent(slug)}/pdf`;
}

export function fetchUserCollections(username) {
  return api.get(`/api/users/${encodeURIComponent(username)}/collections`);
}

export function updateCollection(collectionId, data) {
  return api.put(`/api/collections/${encodeURIComponent(collectionId)}`, data);
}

export function deleteCollection(collectionId) {
  return api.delete(`/api/collections/${encodeURIComponent(collectionId)}`);
}

export function addPostToCollection(collectionId, data) {
  return api.post(`/api/collections/${encodeURIComponent(collectionId)}/posts`, data);
}

export function respondCollectionEntry(collectionId, postId, data) {
  return api.post(`/api/collections/${encodeURIComponent(collectionId)}/posts/${encodeURIComponent(postId)}/respond`, data);
}

export function removeCollectionEntry(collectionId, postId) {
  return api.delete(`/api/collections/${encodeURIComponent(collectionId)}/posts/${encodeURIComponent(postId)}`);
}

export function fetchMyCollections() {
  return api.get("/api/user/collections");
}

export function fetchManagedCollection(collectionId) {
  return api.get(`/api/user/collections/${encodeURIComponent(collectionId)}/manage`);
}

export function fetchPendingCollectionApprovals() {
  return api.get("/api/user/collections/pending");
}

export function fetchPostCollections(postId) {
  return api.get(`/api/posts/${encodeURIComponent(postId)}/collections`);
}

export function fetchForumThreads(section = "general") {
  const params = section && section !== "toate" ? `?section=${encodeURIComponent(section)}` : "";
  return api.get(`/api/forum/threads${params}`);
}

export function fetchForumSections() {
  return api.get("/api/forum/sections");
}

export function fetchForumThread(slug) {
  return api.get(`/api/forum/threads/${encodeURIComponent(slug)}`);
}

export function createForumThread(data) {
  return api.post("/api/forum/threads", data);
}

export function createForumReply(threadId, data) {
  return api.post(`/api/forum/threads/${encodeURIComponent(threadId)}/replies`, data);
}

export function deleteForumThread(threadId) {
  return api.delete(`/api/forum/threads/${encodeURIComponent(threadId)}`);
}

export function deleteForumReply(replyId) {
  return api.delete(`/api/forum/replies/${encodeURIComponent(replyId)}`);
}

export function updateForumThreadState(threadId, action) {
  return api.post(`/api/forum/threads/${encodeURIComponent(threadId)}/state`, { action });
}

export function createClub(data) {
  return api.post("/api/clubs/", data);
}

export function updateClub(clubId, data) {
  return api.put(`/api/clubs/${encodeURIComponent(clubId)}`, data);
}

export function deleteClub(clubId) {
  return api.delete(`/api/clubs/${encodeURIComponent(clubId)}`);
}

export function applyToClub(clubId, data = {}) {
  return api.post(`/api/clubs/${encodeURIComponent(clubId)}/apply`, data);
}

export function inviteToClub(clubId, data) {
  return api.post(`/api/clubs/${encodeURIComponent(clubId)}/invite`, data);
}

export function fetchClubRequests(clubId) {
  return api.get(`/api/clubs/${encodeURIComponent(clubId)}/requests`);
}

export function respondClubRequest(clubId, requestId, data) {
  return api.post(`/api/clubs/${encodeURIComponent(clubId)}/requests/${encodeURIComponent(requestId)}/respond`, data);
}

export function removeClubMember(clubId, userId) {
  return api.delete(`/api/clubs/${encodeURIComponent(clubId)}/members/${encodeURIComponent(userId)}`);
}

export function updateClubMemberRole(clubId, userId, data) {
  return api.put(`/api/clubs/${encodeURIComponent(clubId)}/members/${encodeURIComponent(userId)}/role`, data);
}

export function fetchMyClubs() {
  return api.get("/api/user/clubs");
}

export function fetchMyClubInvitations() {
  return api.get("/api/user/clubs/pending");
}

export function fetchClubBoard(clubId) {
  return api.get(`/api/clubs/${encodeURIComponent(clubId)}/board`);
}

export function createClubBoardMessage(clubId, data) {
  return api.post(`/api/clubs/${encodeURIComponent(clubId)}/board`, data);
}

export function deleteClubBoardMessage(clubId, messageId) {
  return api.delete(`/api/clubs/${encodeURIComponent(clubId)}/board/${encodeURIComponent(messageId)}`);
}

export function setClubFeatured(clubId, data) {
  return api.post(`/api/clubs/${encodeURIComponent(clubId)}/featured`, data);
}

export function clearClubFeatured(clubId) {
  return api.delete(`/api/clubs/${encodeURIComponent(clubId)}/featured`);
}

export function addSuperLike(postId) {
  return api.post(`/api/posts/${encodeURIComponent(postId)}/super-likes`, {});
}

export function removeSuperLike(postId) {
  return api.delete(`/api/posts/${encodeURIComponent(postId)}/super-likes`);
}

export function fetchSuperLikeQuota() {
  return api.get("/api/users/me/super-likes/quota");
}

export function fetchShopState() {
  return api.get("/api/shop/me");
}

export function purchaseShopItem(itemId) {
  return api.post(`/api/shop/items/${encodeURIComponent(itemId)}/purchase`, {});
}

export function equipInventoryItem(itemId) {
  return api.post("/api/inventory/equip", { item_id: itemId });
}

export function unequipInventorySlot(slot) {
  return api.delete(`/api/inventory/equipped/${encodeURIComponent(slot)}`);
}

export function fetchAdminShopItems() {
  return api.get("/api/admin/shop/items");
}

export function createAdminShopItem(data) {
  return api.post("/api/admin/shop/items", data);
}

export function updateAdminShopItem(itemId, data) {
  return api.put(`/api/admin/shop/items/${encodeURIComponent(itemId)}`, data);
}

export function startPremiumCheckout(tier = "premium") {
  return api.post("/api/premium/checkout", { tier });
}

export function openPremiumPortal() {
  return api.post("/api/premium/portal", {});
}

export function fetchAudioConversionQuota() {
  return api.get("/api/audio/conversion-quota");
}

export function requestTtsConversions(postIds) {
  return api.post("/api/audio/tts-requests", { post_ids: postIds });
}

export function fetchCollectionAudioPlaylist(collectionId) {
  return api.get(`/api/audio/collections/${encodeURIComponent(collectionId)}/playlist`);
}

export function fetchRandomAudio(category) {
  if (!category) return api.get("/api/audio/random");
  return api.get(`/api/audio/random?category=${encodeURIComponent(category)}`);
}

export function audioStreamUrl(audioId) {
  return `/api/audio/stream/${encodeURIComponent(audioId)}`;
}

export function uploadPostAudioRecording(postId, file) {
  const form = new FormData();
  form.append("file", file);
  return api.post(`/api/posts/${encodeURIComponent(postId)}/audio-recording`, form);
}

export function fetchModerationStats() {
  return api.get("/api/moderation/stats");
}

export function fetchPendingModerationContent(contentType = "all") {
  const params = contentType && contentType !== "all" ? `?content_type=${encodeURIComponent(contentType)}` : "";
  return api.get(`/api/moderation/content/pending${params}`);
}

export function fetchFlaggedModerationContent() {
  return api.get("/api/moderation/content/flagged");
}

export function moderateContent(contentType, contentId, data) {
  return api.post(`/api/moderation/moderate/${encodeURIComponent(contentType)}/${encodeURIComponent(contentId)}`, data);
}

export function searchModerationUsers(query) {
  return api.get(`/api/moderation/users/search?q=${encodeURIComponent(query)}`);
}

export function suspendUser(userId, data) {
  return api.post(`/api/moderation/users/${encodeURIComponent(userId)}/suspend`, data);
}

export function unsuspendUser(userId) {
  return api.post(`/api/moderation/users/${encodeURIComponent(userId)}/unsuspend`, {});
}

export function fetchModerationLogs({ decision = "", limit = 100, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (decision) params.set("decision", decision);
  if (limit) params.set("limit", String(limit));
  if (offset) params.set("offset", String(offset));
  const query = params.toString();
  return api.get(`/api/moderation/logs${query ? `?${query}` : ""}`);
}

export function fetchModerationQueue() {
  return api.get("/api/moderation/queue");
}

export function reviewModerationLog(logId, data) {
  return api.post(`/api/moderation/review/${encodeURIComponent(logId)}`, data);
}

export function fetchExtendedModerationStats() {
  return api.get("/api/moderation/stats/extended");
}

export function completeAuthSetup(data) {
  return api.post("/api/auth/complete-setup", data);
}

export function logout() {
  return api.get("/api/logout");
}
