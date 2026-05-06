import { api } from "./client.js";

export function fetchPremiumPlans() {
  return api.get("/api/premium/planuri");
}

export function startPremiumCheckout(tier = "trubadur") {
  return api.post("/api/premium/plata", { tier });
}

export function openPremiumPortal() {
  return api.post("/api/premium/portal", {});
}
