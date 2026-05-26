import { api } from "./client.js";

export function fetchMyReferrals() {
  return api.get("/api/recomandari/eu");
}
