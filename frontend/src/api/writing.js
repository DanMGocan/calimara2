import { api } from "./client.js";

export function addDiacritics(data) {
  return api.post("/api/scriere/diacritice", data);
}

