import { api } from "./client.js";

export function fetchPostAudioStatus(postId) {
  return api.get(`/api/audio/postari/${encodeURIComponent(postId)}`);
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

export function fetchListeningRandomAudio(mode = "toate") {
  return api.get(`/api/audio/asculta/aleatoriu?mode=${encodeURIComponent(mode)}`);
}

export function fetchAuthorListeningRandomAudio(username, mode = "toate") {
  return api.get(`/api/audio/autori/${encodeURIComponent(username)}/aleatoriu?mode=${encodeURIComponent(mode)}`);
}

export function fetchAudioPlaylists(postId = null) {
  if (postId) return api.get(`/api/audio/playlisturi?post_id=${encodeURIComponent(postId)}`);
  return api.get("/api/audio/playlisturi");
}

export function createAudioPlaylist(title) {
  return api.post("/api/audio/playlisturi", { title });
}

export function updateAudioPlaylist(playlistId, title) {
  return api.put(`/api/audio/playlisturi/${encodeURIComponent(playlistId)}`, { title });
}

export function deleteAudioPlaylist(playlistId) {
  return api.delete(`/api/audio/playlisturi/${encodeURIComponent(playlistId)}`);
}

export function fetchAudioPlaylist(playlistId) {
  return api.get(`/api/audio/playlisturi/${encodeURIComponent(playlistId)}`);
}

export function addPostToAudioPlaylist(playlistId, postId) {
  return api.post(`/api/audio/playlisturi/${encodeURIComponent(playlistId)}/postari`, { post_id: postId });
}

export function removePostFromAudioPlaylist(playlistId, postId) {
  return api.delete(`/api/audio/playlisturi/${encodeURIComponent(playlistId)}/postari/${encodeURIComponent(postId)}`);
}

export function fetchAudioPlaylistPlayback(playlistId) {
  return api.get(`/api/audio/playlisturi/${encodeURIComponent(playlistId)}/lista-redare`);
}

export function recordAudioListenSeconds({ eventId, audioId, seconds, mode = "toate" }) {
  return api.post("/api/audio/asculta/secunde", {
    event_id: eventId,
    audio_id: audioId,
    seconds,
    mode
  });
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
