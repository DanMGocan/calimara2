import { api } from "./client.js";

export function createSiteFeedback(data) {
  return api.post("/api/site-feedback", data);
}
