import { api } from "./client.js";

export function addDiacritics(data) {
  return api.post("/api/scriere/diacritice", data);
}

export function formatPostWithAi(data) {
  return api.post("/api/scriere/formatare-ai", data);
}

export function fetchDiacriticsQuota() {
  return api.get("/api/scriere/diacritice/cota");
}
