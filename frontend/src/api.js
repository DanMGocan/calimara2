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

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    throw new ApiError(
      response.status,
      "Serverul a răspuns cu pagina aplicației în loc de date JSON. Reîncarcă pagina."
    );
  }

  try {
    return await response.json();
  } catch {
    throw new ApiError(response.status, "Răspunsul serverului nu a fost JSON valid.");
  }
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", body }),
  put: (path, body) => request(path, { method: "PUT", body }),
  delete: (path) => request(path, { method: "DELETE" })
};

export const AUTH_GOOGLE_PATH = "/autentificare/google";
export const AUTH_GOOGLE_CALLBACK_PATH = "/autentificare/google/raspuns";
export const AUTH_SETUP_PATH = "/autentificare/configurare";

export function fetchMe() {
  return api.get("/api/utilizator/eu");
}

export function updateMe(data) {
  return api.put("/api/utilizator/eu", data);
}

export function updateProfileSettings(data) {
  return api.put("/api/utilizator/profil", data);
}

export function updateSocialLinks(data) {
  return api.put("/api/utilizator/linkuri-sociale", data);
}

export function uploadProfileMedia(kind, file) {
  const form = new FormData();
  form.append("file", file);
  return api.post(`/api/utilizator/media/${encodeURIComponent(kind)}`, form);
}

export function deleteProfileMedia(kind) {
  return api.delete(`/api/utilizator/media/${encodeURIComponent(kind)}`);
}

export function updateBestFriends(friends) {
  return api.put("/api/utilizator/prieteni-apropiati", { friends });
}

export function searchUsers(query) {
  return api.get(`/api/utilizatori/cauta?q=${encodeURIComponent(query)}`);
}

export function fetchPublicProfile(username) {
  return api.get(`/api/utilizator/${encodeURIComponent(username)}/profil`);
}

export function updateFeaturedPosts(postIds) {
  return api.put("/api/utilizator/postari-recomandate", { post_ids: postIds });
}

export function fetchLanding(category) {
  return api.get(`/api/prima-pagina?category=${encodeURIComponent(category)}`);
}

export function fetchCategory(categoryKey, sortBy = "newest") {
  return api.get(`/api/categorii/${encodeURIComponent(categoryKey)}?sort_by=${encodeURIComponent(sortBy)}`);
}

export function fetchBlog(username) {
  return api.get(`/api/bloguri/${encodeURIComponent(username)}`);
}

export function fetchPostDetail(username, slug) {
  return api.get(`/api/bloguri/${encodeURIComponent(username)}/postari/${encodeURIComponent(slug)}`);
}

export function postPdfUrl(username, slug) {
  return `/api/bloguri/${encodeURIComponent(username)}/postari/${encodeURIComponent(slug)}/pdf`;
}

export function fetchPostAudioStatus(postId) {
  return api.get(`/api/audio/postari/${encodeURIComponent(postId)}`);
}

export function fetchRandomUser() {
  return api.get("/api/utilizatori/aleatoriu");
}

export function fetchClubs() {
  return api.get("/api/cluburi?limit=50");
}

export function fetchRandomClub() {
  return api.get("/api/cluburi/aleatoriu");
}

export function fetchClub(slug) {
  return api.get(`/api/cluburi/${encodeURIComponent(slug)}`);
}

export function fetchArchive() {
  return api.get("/api/postari/arhiva");
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

export function fetchPostDrafts() {
  return api.get("/api/postari/ciorne");
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

export function addDiacritics(data) {
  return api.post("/api/scriere/diacritice", data);
}

export function createComment(postId, data) {
  return api.post(`/api/postari/${encodeURIComponent(postId)}/comentarii`, data);
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

export function fetchConversations() {
  return api.get("/api/mesaje/conversatii");
}

export function fetchConversation(conversationId) {
  return api.get(`/api/mesaje/conversatii/${encodeURIComponent(conversationId)}`);
}

export function sendConversationMessage(conversationId, data) {
  return api.post(`/api/mesaje/conversatii/${encodeURIComponent(conversationId)}`, data);
}

export function sendMessage(data) {
  return api.post("/api/mesaje/trimite", data);
}

export function fetchUnreadMessageCount() {
  return api.get("/api/mesaje/necitite");
}

export function deleteConversation(conversationId) {
  return api.delete(`/api/mesaje/conversatii/${encodeURIComponent(conversationId)}`);
}

export function searchConversations(query) {
  return api.get(`/api/mesaje/cauta?q=${encodeURIComponent(query)}`);
}

export function fetchNotifications() {
  return api.get("/api/notificari");
}

export function fetchUnreadNotificationCount() {
  return api.get("/api/notificari/necitite");
}

export function markNotificationRead(notificationId) {
  return api.put(`/api/notificari/${encodeURIComponent(notificationId)}/citita`, {});
}

export function markAllNotificationsRead() {
  return api.put("/api/notificari/citeste-toate", {});
}

export function fetchPostStats(postId) {
  return api.get(`/api/statistici/postare/${encodeURIComponent(postId)}`);
}

export function fetchAuthorStats(username) {
  return api.get(`/api/statistici/autor/${encodeURIComponent(username)}`);
}

export function fetchCategoryStats(categoryKey) {
  return api.get(`/api/statistici/categorie/${encodeURIComponent(categoryKey)}`);
}

export function fetchOverviewStats() {
  return api.get("/api/statistici/ansamblu");
}

export function fetchMyStats() {
  return api.get("/api/statistici/ale-mele");
}

export function createSeries(data) {
  return api.post("/api/serii/", data);
}

export function fetchRandomSeries() {
  return api.get("/api/serii/aleatoriu");
}

export function fetchSeries(slug) {
  return api.get(`/api/serii/${encodeURIComponent(slug)}`);
}

export function seriesPdfUrl(slug) {
  return `/api/serii/${encodeURIComponent(slug)}/pdf`;
}

export function fetchUserSeries(username) {
  return api.get(`/api/utilizatori/${encodeURIComponent(username)}/serii`);
}

export function updateSeries(seriesId, data) {
  return api.put(`/api/serii/${encodeURIComponent(seriesId)}`, data);
}

export function deleteSeries(seriesId) {
  return api.delete(`/api/serii/${encodeURIComponent(seriesId)}`);
}

export function addPostToSeries(seriesId, data) {
  return api.post(`/api/serii/${encodeURIComponent(seriesId)}/postari`, data);
}

export function reorderSeriesPosts(seriesId, postIds) {
  return api.put(`/api/serii/${encodeURIComponent(seriesId)}/postari/ordine`, { post_ids: postIds });
}

export function removePostFromSeries(seriesId, postId) {
  return api.delete(`/api/serii/${encodeURIComponent(seriesId)}/postari/${encodeURIComponent(postId)}`);
}

export function fetchMySeries() {
  return api.get("/api/utilizator/serii");
}

export function fetchManagedSeries(seriesId) {
  return api.get(`/api/utilizator/serii/${encodeURIComponent(seriesId)}/gestioneaza`);
}

export function fetchPostSeries(postId) {
  return api.get(`/api/postari/${encodeURIComponent(postId)}/serie`);
}

export function fetchForumThreads(section = "general") {
  const params = section && section !== "toate" ? `?section=${encodeURIComponent(section)}` : "";
  return api.get(`/api/forum/discutii${params}`);
}

export function fetchForumSections() {
  return api.get("/api/forum/sectiuni");
}

export function fetchForumThread(slug) {
  return api.get(`/api/forum/discutii/${encodeURIComponent(slug)}`);
}

export function createForumThread(data) {
  return api.post("/api/forum/discutii", data);
}

export function createForumReply(threadId, data) {
  return api.post(`/api/forum/discutii/${encodeURIComponent(threadId)}/raspunsuri`, data);
}

export function deleteForumThread(threadId) {
  return api.delete(`/api/forum/discutii/${encodeURIComponent(threadId)}`);
}

export function deleteForumReply(replyId) {
  return api.delete(`/api/forum/raspunsuri/${encodeURIComponent(replyId)}`);
}

export function updateForumThreadState(threadId, action) {
  return api.post(`/api/forum/discutii/${encodeURIComponent(threadId)}/stare`, { action });
}

export function createClub(data) {
  return api.post("/api/cluburi/", data);
}

export function updateClub(clubId, data) {
  return api.put(`/api/cluburi/${encodeURIComponent(clubId)}`, data);
}

export function deleteClub(clubId) {
  return api.delete(`/api/cluburi/${encodeURIComponent(clubId)}`);
}

export function applyToClub(clubId, data = {}) {
  return api.post(`/api/cluburi/${encodeURIComponent(clubId)}/inscriere`, data);
}

export function inviteToClub(clubId, data) {
  return api.post(`/api/cluburi/${encodeURIComponent(clubId)}/invita`, data);
}

export function fetchClubRequests(clubId) {
  return api.get(`/api/cluburi/${encodeURIComponent(clubId)}/cereri`);
}

export function respondClubRequest(clubId, requestId, data) {
  return api.post(`/api/cluburi/${encodeURIComponent(clubId)}/cereri/${encodeURIComponent(requestId)}/raspunde`, data);
}

export function removeClubMember(clubId, userId) {
  return api.delete(`/api/cluburi/${encodeURIComponent(clubId)}/membri/${encodeURIComponent(userId)}`);
}

export function updateClubMemberRole(clubId, userId, data) {
  return api.put(`/api/cluburi/${encodeURIComponent(clubId)}/membri/${encodeURIComponent(userId)}/rol`, data);
}

export function fetchMyClubs() {
  return api.get("/api/utilizator/cluburi");
}

export function fetchMyClubInvitations() {
  return api.get("/api/utilizator/cluburi/in-asteptare");
}

export function fetchClubBoard(clubId) {
  return api.get(`/api/cluburi/${encodeURIComponent(clubId)}/tabla`);
}

export function createClubBoardMessage(clubId, data) {
  return api.post(`/api/cluburi/${encodeURIComponent(clubId)}/tabla`, data);
}

export function deleteClubBoardMessage(clubId, messageId) {
  return api.delete(`/api/cluburi/${encodeURIComponent(clubId)}/tabla/${encodeURIComponent(messageId)}`);
}

export function setClubFeatured(clubId, data) {
  return api.post(`/api/cluburi/${encodeURIComponent(clubId)}/creatia-saptamanii`, data);
}

export function clearClubFeatured(clubId) {
  return api.delete(`/api/cluburi/${encodeURIComponent(clubId)}/creatia-saptamanii`);
}

export function addSuperLike(postId) {
  return api.post(`/api/postari/${encodeURIComponent(postId)}/super-aprecieri`, {});
}

export function removeSuperLike(postId) {
  return api.delete(`/api/postari/${encodeURIComponent(postId)}/super-aprecieri`);
}

export function fetchSuperLikeQuota() {
  return api.get("/api/utilizatori/eu/super-aprecieri/cota");
}

export function fetchShopState() {
  return api.get("/api/magazin/eu");
}

export function purchaseShopItem(itemId) {
  return api.post(`/api/magazin/obiecte/${encodeURIComponent(itemId)}/cumpara`, {});
}

export function equipInventoryItem(itemId) {
  return api.post("/api/inventar/echipeaza", { item_id: itemId });
}

export function unequipInventorySlot(slot) {
  return api.delete(`/api/inventar/echipate/${encodeURIComponent(slot)}`);
}

export function fetchAdminShopItems() {
  return api.get("/api/moderare/magazin/obiecte");
}

export function createAdminShopItem(data) {
  return api.post("/api/moderare/magazin/obiecte", data);
}

export function updateAdminShopItem(itemId, data) {
  return api.put(`/api/moderare/magazin/obiecte/${encodeURIComponent(itemId)}`, data);
}

export function startPremiumCheckout(tier = "premium") {
  return api.post("/api/premium/plata", { tier });
}

export function openPremiumPortal() {
  return api.post("/api/premium/portal", {});
}

export function fetchAudioConversionQuota() {
  return api.get("/api/audio/cota-conversie");
}

export function requestTtsConversions(postIds) {
  return api.post("/api/audio/cereri-tts", { post_ids: postIds });
}

export function fetchSeriesAudioPlaylist(seriesId) {
  return api.get(`/api/audio/serii/${encodeURIComponent(seriesId)}/lista-redare`);
}

export function fetchRandomAudio(category) {
  if (!category) return api.get("/api/audio/aleatoriu");
  return api.get(`/api/audio/aleatoriu?category=${encodeURIComponent(category)}`);
}

export function audioStreamUrl(audioId) {
  return `/api/audio/redare/${encodeURIComponent(audioId)}`;
}

export function audioDownloadUrl(audioId) {
  return `/api/audio/descarcare/${encodeURIComponent(audioId)}`;
}

export function uploadPostAudioRecording(postId, file) {
  const form = new FormData();
  form.append("file", file);
  return api.post(`/api/postari/${encodeURIComponent(postId)}/inregistrare-audio`, form);
}

export function fetchModerationStats() {
  return api.get("/api/moderare/statistici");
}

export function fetchPendingModerationContent(contentType = "all") {
  const params = contentType && contentType !== "all" ? `?content_type=${encodeURIComponent(contentType)}` : "";
  return api.get(`/api/moderare/continut/in-asteptare${params}`);
}

export function fetchFlaggedModerationContent() {
  return api.get("/api/moderare/continut/marcate");
}

export function moderateContent(contentType, contentId, data) {
  return api.post(`/api/moderare/modereaza/${encodeURIComponent(contentType)}/${encodeURIComponent(contentId)}`, data);
}

export function searchModerationUsers(query) {
  return api.get(`/api/moderare/utilizatori/cauta?q=${encodeURIComponent(query)}`);
}

export function suspendUser(userId, data) {
  return api.post(`/api/moderare/utilizatori/${encodeURIComponent(userId)}/suspenda`, data);
}

export function unsuspendUser(userId) {
  return api.post(`/api/moderare/utilizatori/${encodeURIComponent(userId)}/reactiveaza`, {});
}

export function fetchModerationLogs({ decision = "", limit = 100, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (decision) params.set("decision", decision);
  if (limit) params.set("limit", String(limit));
  if (offset) params.set("offset", String(offset));
  const query = params.toString();
  return api.get(`/api/moderare/jurnal${query ? `?${query}` : ""}`);
}

export function fetchModerationQueue() {
  return api.get("/api/moderare/coada");
}

export function reviewModerationLog(logId, data) {
  return api.post(`/api/moderare/revizie/${encodeURIComponent(logId)}`, data);
}

export function fetchExtendedModerationStats() {
  return api.get("/api/moderare/statistici/extinse");
}

export function completeAuthSetup(data) {
  return api.post("/api/autentificare/finalizeaza-configurarea", data);
}

export function logout() {
  return api.get("/api/deconectare");
}
